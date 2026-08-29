"""阶段 4：Original 特征提取（连续强度 + PyRadiomics 固定箱宽）。

binWidth = f × σ_A 固定自 configs/sigma_a.json（仅训练集 A 计算，见 compute_sigma_a.py）。
全部病例（A 与 B）均以连续的归一化图像输入 PyRadiomics。first-order 使用连续强度；
纹理以及 first-order Entropy/Uniformity 由 PyRadiomics 按固定 binWidth 离散化。
A 的强度范围仅用于分布外推报告，不裁剪 B。Shape 仅在 Original 图像提取一次。

输出 output/features_v2/<normalization>_f<f>/：
  features_original.csv   特征表（影像号、读者、split、normalization、f、binWidth + 特征列）
  diagnostics.csv         PyRadiomics diagnostics_ 列（掩膜体素数、计算时长等，不混入特征表）
  bin_range_report.csv    ROI 外推报告（低于/高于 A 参考范围的体素比例；不裁剪）
  bin_range_summary.csv   A/B 分组汇总（测试集 B 与训练集 A 范围差异报告）
计时追加 output/qc/logs/features_timing.csv；异常写入 qc_report.csv（阶段 features）。
断点续跑：仅当特征表、诊断表和范围报告均已有该 影像号+读者 时自动跳过。

用法:
  python scripts/extract_features.py --norm muscle --f 0.25 [--ids ID1,ID2] [--limit N] [--workers 2] [--force]
"""
from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import time
from typing import Dict, Iterable, Set, Tuple

import numpy as np

# On Windows, initialize NumPy's numeric backend before SimpleITK is loaded.
# Otherwise PyRadiomics 3D shape can fail inside numpy.dot with 0xC06D007F.
np.dot(np.eye(3), np.eye(3))

import SimpleITK as sitk

from workflow_utils import (
    atomic_write_csv, atomic_write_json, drop_keys, file_sha256, frame_keys,
    git_commit, merge_rows, read_csv_or_empty, update_stage_metadata, utc_now,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(OUT, "manifest.csv")
SCANNER = os.path.join(OUT, "scanner_map.csv")
SIGMA_JSON = os.path.join(ROOT, "configs", "sigma_a.json")
PARAMS_YAML = os.path.join(ROOT, "configs", "radiomics_params.yaml")
QC_REPORT = os.path.join(OUT, "qc", "qc_report.csv")
TIMING_CSV = os.path.join(OUT, "qc", "logs", "features_timing.csv")
PREP_DIRS = {"muscle": os.path.join(OUT, "preprocessed"),
             "zscore": os.path.join(OUT, "preprocessed_zscore")}
FEATURE_CLASSES = ["firstorder", "shape", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]

META_COLS = ["影像号", "读者", "split", "normalization", "f", "binWidth"]
RANGE_COLS = ["影像号", "读者", "split", "n_roi", "n_below", "n_above",
              "frac_below", "frac_above", "roi_min", "roi_max"]
KEY_COLS = ["影像号", "读者"]


def _empty_like(frame: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    return frame.iloc[0:0].copy() if not frame.empty or len(frame.columns) else pd.DataFrame(columns=list(columns))


def prepare_run_frame(path: str, key_cols: Iterable[str],
                      target_keys: Set[Tuple[str, ...]], force: bool,
                      full_reset: bool) -> pd.DataFrame:
    """Load existing output and remove exactly the rows this run owns."""
    old = read_csv_or_empty(path)
    if not force:
        return old
    if full_reset:
        return _empty_like(old, [])
    return drop_keys(old, list(key_cols), target_keys)


def completed_keys(feature_frames: Iterable[pd.DataFrame]) -> Set[Tuple[str, ...]]:
    frames = list(feature_frames)
    if not frames:
        return set()
    result = frame_keys(frames[0], KEY_COLS)
    for frame in frames[1:]:
        result &= frame_keys(frame, KEY_COLS)
    return result


def finalize_output(path: str, base: pd.DataFrame, tmp_path: str,
                    key_cols: Iterable[str], changed: bool) -> None:
    new = read_csv_or_empty(tmp_path) if os.path.exists(tmp_path) else pd.DataFrame()
    if not changed and new.empty:
        return
    merged = merge_rows(base, new, list(key_cols))
    if merged.empty and len(base.columns):
        merged = base.iloc[0:0].copy()
    atomic_write_csv(merged, path)
    if os.path.exists(tmp_path):
        os.remove(tmp_path)


def write_feature_metadata(path: str, norm: str, f_value: float,
                           bin_width: float) -> None:
    import radiomics

    payload = {
        "stage": "original",
        "created_at": utc_now(),
        "git_commit": git_commit(ROOT),
        "pyradiomics_version": getattr(radiomics, "__version__", "unknown"),
        "radiomics_params_sha256": file_sha256(PARAMS_YAML),
        "sigma_a_sha256": file_sha256(SIGMA_JSON),
        "normalization": norm,
        "f": f_value,
        "binWidth": bin_width,
    }
    update_stage_metadata(path, "original", payload)


def pyradiomics_params(bin_width: float) -> dict:
    """从唯一 YAML 配置源构建参数，并注入训练集 A 确定的固定箱宽。"""
    import yaml

    with open(PARAMS_YAML, encoding="utf-8") as f:
        fx = yaml.safe_load(f)["featureExtraction"]
    setting = dict(fx["setting"])
    setting["resampledPixelSpacing"] = None
    setting["binWidth"] = float(bin_width)
    return {"imageType": dict(fx["imageType"]),
            "featureClass": {c: [] for c in FEATURE_CLASSES},
            "setting": setting}


# ---- 多进程 worker（spawn 模型，仅接收可 pickle 参数）----
_EX = None
_REFERENCE_RANGE: tuple | None = None  # (A_min, A_max)，仅用于外推报告


def init_worker(params: dict, reference_range: tuple) -> None:
    import logging
    import radiomics
    from radiomics import featureextractor
    radiomics.setVerbosity(logging.ERROR)
    global _EX, _REFERENCE_RANGE
    _EX = featureextractor.RadiomicsFeatureExtractor(params)
    _REFERENCE_RANGE = reference_range


def extract_task(task: tuple) -> dict:
    pid, reader, img_path, mask_path = task
    t0 = time.perf_counter()
    try:
        img = sitk.ReadImage(img_path)
        m = sitk.ReadImage(mask_path)
        arr = sitk.GetArrayFromImage(img).astype(np.float64)
        res = _EX.execute(img, m)
        feat = {k: v for k, v in res.items() if not k.startswith("diagnostics_")}
        diag = {k: v for k, v in res.items() if k.startswith("diagnostics_")}
        ma = sitk.GetArrayFromImage(m) == 1
        roi = arr[ma]
        gmin, gmax = _REFERENCE_RANGE
        below = int((roi < gmin - 1e-9).sum())
        above = int((roi > gmax + 1e-9).sum())
        return {"ok": True, "pid": pid, "reader": reader, "feat": feat, "diag": diag,
                "n_roi": int(roi.size), "n_below": below, "n_above": above,
                "roi_min": float(roi.min()), "roi_max": float(roi.max()),
                "seconds": time.perf_counter() - t0}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "pid": pid, "reader": reader,
                "error": f"{type(e).__name__}: {e}", "seconds": time.perf_counter() - t0}


def main() -> None:
    import pandas as pd

    ap = argparse.ArgumentParser(description="Original 特征提取（连续强度 + 固定箱宽）")
    ap.add_argument("--norm", required=True, choices=["muscle", "zscore"])
    ap.add_argument("--f", required=True, type=float, choices=[0.1, 0.25])
    ap.add_argument("--ids", help="逗号分隔影像号（缺省全队列）")
    ap.add_argument("--limit", type=int, help="仅处理前 N 例（测试用）")
    ap.add_argument("--workers", type=int, default=2, help="并行进程数（缺省 2）")
    ap.add_argument("--force", action="store_true", help="忽略已存在输出，重新提取")
    ap.add_argument("--prep-dir", help="预处理产物目录覆盖（如 N4 试点 output/n4pilot/preprocessed）")
    ap.add_argument("--out-root", help="特征输出根目录覆盖（缺省 output/features_v2）")
    args = ap.parse_args()

    sig = json.load(open(SIGMA_JSON, encoding="utf-8"))
    st = sig["arms"][args.norm]
    bin_width = args.f * st["sigma"]
    nb = int(math.ceil((st["max"] - st["min"]) / bin_width)) if bin_width > 0 else 1
    reference_range = (st["min"], st["max"])
    print(f"[{args.norm} f={args.f}] binWidth = {bin_width:.4f}  "
          f"A 参考范围 [{st['min']:.4f}, {st['max']:.4f}] 约 {nb} bin"
          "（连续图像输入；B 越界仅报告、不裁剪）")

    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    df = man.merge(sc[["影像号", "R1厂商", "R1机型", "R1场强"]], on="影像号", how="left")
    df["_f"] = pd.to_numeric(df["R1场强"], errors="coerce")
    is_a = (df["R1厂商"] == "GE MEDICAL SYSTEMS") & (df["R1机型"] == "DISCOVERY MR750") & \
           (df["_f"].round(1) == 3.0)
    df["split"] = np.where(is_a, "A", "B")
    if args.ids:
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        df = df[df["影像号"].isin(ids)]
    df = df[df["排除"] != "1"]
    if args.limit:
        df = df.head(args.limit)
    prep = args.prep_dir if args.prep_dir else PREP_DIRS[args.norm]
    if not os.path.isabs(prep):
        prep = os.path.join(ROOT, prep)

    tasks: list[tuple] = []
    for _, row in df.iterrows():
        pid = row["影像号"]
        base = os.path.join(prep, pid)
        tasks.append((pid, "R1", os.path.join(base, "R1_image.nrrd"),
                      os.path.join(base, "R1_mask.nrrd")))
        if str(row.get("是否双读者", "")) == "1":
            r2i = os.path.join(base, "R2_image.nrrd")
            r2m = os.path.join(base, "R2_mask.nrrd")
            if os.path.exists(r2i) and os.path.exists(r2m):
                tasks.append((pid, "R2", r2i, r2m))

    out_root = args.out_root if args.out_root else os.path.join(OUT, "features_v2")
    if not os.path.isabs(out_root):
        out_root = os.path.join(ROOT, out_root)
    outdir = os.path.join(out_root, f"{args.norm}_f{args.f:g}")
    os.makedirs(outdir, exist_ok=True)
    feat_csv = os.path.join(outdir, "features_original.csv")
    diag_csv = os.path.join(outdir, "diagnostics.csv")
    range_csv = os.path.join(outdir, "bin_range_report.csv")
    sum_csv = os.path.join(outdir, "bin_range_summary.csv")

    target_keys = set((task[0], task[1]) for task in tasks)
    full_reset = bool(args.force and not args.ids and args.limit is None)
    base_frames = {
        "features": prepare_run_frame(
            feat_csv, KEY_COLS, target_keys, args.force, full_reset),
        "diagnostics": prepare_run_frame(
            diag_csv, KEY_COLS, target_keys, args.force, full_reset),
        "ranges": prepare_run_frame(
            range_csv, KEY_COLS, target_keys, args.force, full_reset),
    }
    done = set() if args.force else completed_keys(base_frames.values())
    todo = [t for t in tasks if (t[0], t[1]) not in done]
    print(f"任务 {len(tasks)}（待处理 {len(todo)}，已完成 {len(tasks) - len(todo)}）")

    tmp_paths = {
        "features": feat_csv + ".tmp",
        "diagnostics": diag_csv + ".tmp",
        "ranges": range_csv + ".tmp",
    }
    for path in tmp_paths.values():
        if os.path.exists(path):
            os.remove(path)
    if full_reset and os.path.exists(sum_csv):
        os.remove(sum_csv)

    feat_rows: list[dict] = []
    diag_rows: list[dict] = []
    range_rows: list[dict] = []
    t_rows: list[dict] = []
    qc_rows: list[dict] = []
    feat_cols: list[str] = []
    diag_cols: list[str] = []

    def flush() -> None:
        if feat_rows:
            fdf = pd.DataFrame(feat_rows)
            fdf = fdf[META_COLS + feat_cols]
            fdf.to_csv(tmp_paths["features"], mode="a",
                       header=not os.path.exists(tmp_paths["features"]),
                       index=False, encoding="utf-8-sig")
            feat_rows.clear()
        if diag_rows:
            ddf = pd.DataFrame(diag_rows)
            ddf = ddf[["影像号", "读者"] + diag_cols]
            ddf.to_csv(tmp_paths["diagnostics"], mode="a",
                       header=not os.path.exists(tmp_paths["diagnostics"]),
                       index=False, encoding="utf-8-sig")
            diag_rows.clear()
        if range_rows:
            pd.DataFrame(range_rows)[RANGE_COLS].to_csv(
                tmp_paths["ranges"], mode="a",
                header=not os.path.exists(tmp_paths["ranges"]),
                index=False, encoding="utf-8-sig")
            range_rows.clear()

    t0 = time.perf_counter()
    n_ok = n_err = 0
    with multiprocessing.Pool(args.workers, initializer=init_worker,
                              initargs=(pyradiomics_params(bin_width), reference_range)) as pool:
        for res in pool.imap_unordered(extract_task, todo, chunksize=4):
            if not res["ok"]:
                n_err += 1
                qc_rows.append({"影像号": res["pid"], "阶段": "features", "级别": "ERROR",
                                "代码": "EXTRACT_FAIL",
                                "说明": f"{args.norm} f={args.f} {res['reader']}: {res['error']}"})
                continue
            n_ok += 1
            pid = res["pid"]
            row = df[df["影像号"] == pid].iloc[0]
            fr = {"影像号": pid, "读者": res["reader"], "split": row["split"],
                  "normalization": args.norm, "f": args.f, "binWidth": bin_width}
            fr.update(res["feat"])
            if not feat_cols:
                feat_cols = list(res["feat"].keys())
            if not diag_cols:
                diag_cols = list(res["diag"].keys())
            feat_rows.append(fr)
            diag_rows.append({"影像号": pid, "读者": res["reader"], **res["diag"]})
            nr = res["n_roi"]
            range_rows.append({"影像号": pid, "读者": res["reader"], "split": row["split"],
                               "n_roi": nr, "n_below": res["n_below"], "n_above": res["n_above"],
                               "frac_below": res["n_below"] / nr if nr else float("nan"),
                               "frac_above": res["n_above"] / nr if nr else float("nan"),
                               "roi_min": res["roi_min"], "roi_max": res["roi_max"]})
            t_rows.append({"影像号": pid, "读者": res["reader"], "normalization": args.norm,
                           "f": args.f, "seconds": round(res["seconds"], 3)})
            if len(feat_rows) >= 100:
                flush()
    flush()

    changed = bool(args.force or any(os.path.exists(path) for path in tmp_paths.values()))
    finalize_output(feat_csv, base_frames["features"], tmp_paths["features"],
                    KEY_COLS, changed)
    finalize_output(diag_csv, base_frames["diagnostics"], tmp_paths["diagnostics"],
                    KEY_COLS, changed)
    finalize_output(range_csv, base_frames["ranges"], tmp_paths["ranges"],
                    KEY_COLS, changed)

    if t_rows:
        tdf = pd.DataFrame(t_rows)
    else:
        tdf = pd.DataFrame()
    timing_key_cols = ["影像号", "读者", "normalization", "f"]
    timing_keys = set(
        (pid, reader, args.norm, str(args.f)) for pid, reader in target_keys)
    if args.force:
        base_timing = prepare_run_frame(
            TIMING_CSV, timing_key_cols, timing_keys, True, full_reset)
        merged_timing = merge_rows(base_timing, tdf, timing_key_cols)
        atomic_write_csv(merged_timing, TIMING_CSV)
    elif not tdf.empty:
        merged_timing = merge_rows(
            read_csv_or_empty(TIMING_CSV), tdf, timing_key_cols)
        atomic_write_csv(merged_timing, TIMING_CSV)
    if qc_rows:
        seen: set[tuple] = set()
        rows = []
        if os.path.exists(QC_REPORT):
            try:
                rows = pd.read_csv(QC_REPORT, dtype=str).to_dict("records")
            except Exception:  # noqa: BLE001
                rows = []
        rows.extend(qc_rows)
        out = []
        for r in rows:
            k = (r.get("影像号"), r.get("阶段"), r.get("代码"), r.get("说明"))
            if k not in seen:
                seen.add(k)
                out.append(r)
        os.makedirs(os.path.dirname(QC_REPORT), exist_ok=True)
        pd.DataFrame(out).to_csv(QC_REPORT, index=False, encoding="utf-8-sig")

    # 越界汇总（A vs B 范围差异报告）
    if os.path.exists(range_csv):
        rr = pd.read_csv(range_csv, dtype={"影像号": str})
        if len(rr):
            agg = rr.groupby("split").agg(
                n=("影像号", "nunique"), frac_below_mean=("frac_below", "mean"),
                frac_above_mean=("frac_above", "mean"),
                n_any_below=("n_below", lambda s: int((s > 0).sum())),
                n_any_above=("n_above", lambda s: int((s > 0).sum())),
                roi_min=("roi_min", "min"), roi_max=("roi_max", "max")).reset_index()
            agg.to_csv(sum_csv, index=False, encoding="utf-8-sig")
            print(f"\n===== ROI 外推汇总（A参考范围 [{st['min']:.4f}, {st['max']:.4f}]，"
                  f"约 {nb} bin；不裁剪）=====")
            print(agg.to_string(index=False))

    write_feature_metadata(
        os.path.join(outdir, "feature_run_metadata.json"),
        args.norm, args.f, bin_width)

    print(f"\n完成: 成功 {n_ok}，失败 {n_err}，耗时 {time.perf_counter() - t0:.1f}s，"
          f"平均 {((time.perf_counter() - t0) / n_ok if n_ok else 0):.2f}s/例")
    print(f"输出目录: {outdir}")


if __name__ == "__main__":
    main()
