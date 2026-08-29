"""第二批特征提取：Wavelet（coif1，8 子带）与 LoG（σ=1/2/3 mm）滤波特征。

滤波在 PyRadiomics 外部施加（radiomics.imageoperations，与 PyRadiomics 内部定义一致，
施加于未离散化的归一化图像）；各滤波输出的 binWidth = f × σ_A(filt) 仅由训练集 A
确定。连续滤波图像直接输入 PyRadiomics：first-order 使用连续强度，纹理由固定箱宽
离散化；B 超出 A 参考范围的强度仅报告、不裁剪。滤波图像不重复提取 Shape。
列名前缀与 PyRadiomics 命名一致
（wavelet-LLH_ / log-sigma-1-0-mm-3D_ 等）。

输出 output/features_v2/<normalization>_f<f>/：
  features_wavelet.csv / features_log.csv   特征表（影像号、读者、split、normalization、f + 特征列；
                                            每行 = 一个任务，列 = 全部滤波输出特征：
                                            Wavelet 8 子带 × 93 / LoG 3 个 σ × 93）
  grid_params.csv                           各滤波输出 binWidth / A参考范围 / 参考bin数
  diagnostics_filtered.csv                  PyRadiomics 诊断列（含 filter，不混入特征表）
  bin_range_filtered.csv                    ROI 越界报告（含 filter）
  bin_range_summary_filtered.csv            filter × split 分组汇总（测试集 B 与训练集 A 范围差异）
计时追加 output/qc/logs/features_filtered_timing.csv；异常写入 qc_report.csv（阶段 features）。
断点续跑：已完成 影像号+读者 自动跳过（features_wavelet.csv 为准）。

用法:
  python scripts/extract_features_filters.py --norm muscle --f 0.25 [--ids ...] [--limit N] [--workers 2] [--force]
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import multiprocessing
import os
import time

import numpy as np
import pandas as pd
import SimpleITK as sitk
import radiomics
import yaml
from radiomics import featureextractor, imageoperations

radiomics.setVerbosity(logging.ERROR)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(OUT, "manifest.csv")
SCANNER = os.path.join(OUT, "scanner_map.csv")
SIGMA_JSON = os.path.join(ROOT, "configs", "sigma_a_filters.json")
PARAMS_YAML = os.path.join(ROOT, "configs", "radiomics_params.yaml")
QC_REPORT = os.path.join(OUT, "qc", "qc_report.csv")
TIMING_CSV = os.path.join(OUT, "qc", "logs", "features_filtered_timing.csv")
PREP_DIRS = {"muscle": os.path.join(OUT, "preprocessed"),
             "zscore": os.path.join(OUT, "preprocessed_zscore")}
LOG_SIGMAS = [1.0, 2.0, 3.0]
FEATURE_CLASSES = ["firstorder", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]

META_COLS = ["影像号", "读者", "split", "normalization", "f"]
RANGE_COLS = ["影像号", "读者", "split", "filter", "n_roi", "n_below", "n_above",
              "frac_below", "frac_above", "roi_min", "roi_max"]


def extractor_params(bin_width: float) -> dict:
    with open(PARAMS_YAML, encoding="utf-8") as f:
        fx = yaml.safe_load(f)["featureExtraction"]
    setting = dict(fx["setting"])
    setting["resampledPixelSpacing"] = None
    setting["binWidth"] = float(bin_width)
    return {"imageType": {"Original": {}},
            "featureClass": {c: [] for c in FEATURE_CLASSES},
            "setting": setting}


# ---- 多进程 worker（spawn 模型，仅接收可 pickle 参数）----
_EXS: dict = {}
_REFERENCE_RANGES: dict = {}  # filter_key -> (A_min, A_max)


def init_worker(grids: dict) -> None:
    global _EXS, _REFERENCE_RANGES
    _EXS = {name: featureextractor.RadiomicsFeatureExtractor(extractor_params(g[2]))
            for name, g in grids.items()}
    _REFERENCE_RANGES = {name: (g[0], g[1]) for name, g in grids.items()}


def filtered_images(img: sitk.Image, m: sitk.Image) -> dict:
    out: dict = {}
    for im, name, _kw in imageoperations.getWaveletImage(img, m):
        out[name] = im
    for im, name, _kw in imageoperations.getLoGImage(img, m, sigma=LOG_SIGMAS):
        out[name] = im
    return out


def filter_task(task: tuple) -> dict:
    pid, reader, img_path, mask_path = task
    t0 = time.perf_counter()
    try:
        img = sitk.ReadImage(img_path)
        m = sitk.ReadImage(mask_path)
        m_arr = sitk.GetArrayFromImage(m)
        feats: dict = {}
        diags: dict = {}
        rngs: dict = {}
        for name, fim in filtered_images(img, m).items():
            a = sitk.GetArrayFromImage(fim)
            if a.dtype != np.float64:
                a = a.astype(np.float64)
            res = _EXS[name].execute(fim, m)
            pref = name + "_"
            feats[name] = {pref + k[len("original_"):]: v for k, v in res.items()
                           if k.startswith("original_")}
            diags[name] = {k: v for k, v in res.items() if k.startswith("diagnostics_")}
            roi = a[m_arr == 1]
            gmin, gmax = _REFERENCE_RANGES[name]
            below = int((roi < gmin - 1e-9).sum())
            above = int((roi > gmax + 1e-9).sum())
            rngs[name] = (int(roi.size), below, above, float(roi.min()), float(roi.max()))
        return {"ok": True, "pid": pid, "reader": reader, "feats": feats,
                "diags": diags, "rngs": rngs, "seconds": time.perf_counter() - t0}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "pid": pid, "reader": reader,
                "error": f"{type(e).__name__}: {e}", "seconds": time.perf_counter() - t0}


def main() -> None:
    ap = argparse.ArgumentParser(description="Wavelet/LoG 特征提取（连续强度 + 固定箱宽）")
    ap.add_argument("--norm", required=True, choices=["muscle", "zscore"])
    ap.add_argument("--f", required=True, type=float, choices=[0.1, 0.25])
    ap.add_argument("--ids", help="逗号分隔影像号（缺省全队列）")
    ap.add_argument("--limit", type=int, help="仅处理前 N 例（测试用）")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--out-root", help="特征输出根目录覆盖（缺省 output/features_v2）")
    args = ap.parse_args()

    sig = json.load(open(SIGMA_JSON, encoding="utf-8"))
    arm_stats = sig["arms"][args.norm]
    grids: dict = {}
    for k, st in arm_stats.items():
        bw = args.f * st["sigma"]
        nb = int(math.ceil((st["max"] - st["min"]) / bw)) if bw > 0 else 1
        grids[k] = (st["min"], st["max"], bw, nb)
    n_filt = len(grids)
    print(f"[{args.norm} f={args.f}] {n_filt} 个连续滤波输出，固定箱宽由 A 确定；"
          "B 越界仅报告、不裁剪；不提取滤波 Shape")

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
    prep = PREP_DIRS[args.norm]

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
    wav_csv = os.path.join(outdir, "features_wavelet.csv")
    log_csv = os.path.join(outdir, "features_log.csv")
    diag_csv = os.path.join(outdir, "diagnostics_filtered.csv")
    range_csv = os.path.join(outdir, "bin_range_filtered.csv")
    sum_csv = os.path.join(outdir, "bin_range_summary_filtered.csv")
    grid_csv = os.path.join(outdir, "grid_params.csv")

    pd.DataFrame([{"filter": k, "binWidth": round(g[2], 6), "n_bins_A_reference": g[3],
                   "grid_min": round(g[0], 6),
                   "grid_max": round(g[1], 6), "clip_to_A_range": False}
                  for k, g in sorted(grids.items())]).to_csv(
        grid_csv, index=False, encoding="utf-8-sig")

    done: set[tuple] = set()
    if not args.force and os.path.exists(wav_csv):
        try:
            old = pd.read_csv(wav_csv, dtype=str)
            done = set(zip(old["影像号"], old["读者"]))
        except Exception:  # noqa: BLE001
            done = set()
    todo = [t for t in tasks if (t[0], t[1]) not in done]
    print(f"任务 {len(tasks)}（待处理 {len(todo)}，已完成 {len(tasks) - len(todo)}）")

    wav_rows: list[dict] = []
    log_rows: list[dict] = []
    diag_rows: list[dict] = []
    range_rows: list[dict] = []
    t_rows: list[dict] = []
    qc_rows: list[dict] = []
    wav_cols: list[str] = []
    log_cols: list[str] = []
    diag_cols: list[str] = []

    def flush() -> None:
        if wav_rows:
            pd.DataFrame(wav_rows)[META_COLS + wav_cols].to_csv(
                wav_csv, mode="a", header=not os.path.exists(wav_csv),
                index=False, encoding="utf-8-sig")
            wav_rows.clear()
        if log_rows:
            pd.DataFrame(log_rows)[META_COLS + log_cols].to_csv(
                log_csv, mode="a", header=not os.path.exists(log_csv),
                index=False, encoding="utf-8-sig")
            log_rows.clear()
        if diag_rows:
            pd.DataFrame(diag_rows)[["影像号", "读者", "filter"] + diag_cols].to_csv(
                diag_csv, mode="a", header=not os.path.exists(diag_csv),
                index=False, encoding="utf-8-sig")
            diag_rows.clear()
        if range_rows:
            pd.DataFrame(range_rows)[RANGE_COLS].to_csv(
                range_csv, mode="a", header=not os.path.exists(range_csv),
                index=False, encoding="utf-8-sig")
            range_rows.clear()

    t0 = time.perf_counter()
    n_ok = n_err = 0
    with multiprocessing.Pool(args.workers, initializer=init_worker,
                              initargs=(grids,)) as pool:
        for res in pool.imap_unordered(filter_task, todo, chunksize=2):
            if not res["ok"]:
                n_err += 1
                qc_rows.append({"影像号": res["pid"], "阶段": "features", "级别": "ERROR",
                                "代码": "EXTRACT_FAIL",
                                "说明": f"{args.norm} f={args.f} {res['reader']}: {res['error']}"})
                continue
            n_ok += 1
            pid = res["pid"]
            row = df[df["影像号"] == pid].iloc[0]
            meta = {"影像号": pid, "读者": res["reader"], "split": row["split"],
                    "normalization": args.norm, "f": args.f}
            w_row = dict(meta)
            l_row = dict(meta)
            for name, fdict in res["feats"].items():
                if name.startswith("wavelet-"):
                    w_row.update(fdict)
                else:
                    l_row.update(fdict)
            if not wav_cols:
                wav_cols = [k for k in w_row if k not in META_COLS]
            if not log_cols:
                log_cols = [k for k in l_row if k not in META_COLS]
            wav_rows.append(w_row)
            log_rows.append(l_row)
            for name, ddict in res["diags"].items():
                if not diag_cols:
                    diag_cols = list(ddict.keys())
                diag_rows.append({"影像号": pid, "读者": res["reader"], "filter": name, **ddict})
            for name, (n, nb0, na, rmin, rmax) in res["rngs"].items():
                range_rows.append({"影像号": pid, "读者": res["reader"], "split": row["split"],
                                   "filter": name, "n_roi": n, "n_below": nb0, "n_above": na,
                                   "frac_below": nb0 / n if n else float("nan"),
                                   "frac_above": na / n if n else float("nan"),
                                   "roi_min": rmin, "roi_max": rmax})
            t_rows.append({"影像号": pid, "读者": res["reader"], "normalization": args.norm,
                           "f": args.f, "seconds": round(res["seconds"], 3)})
            if len(wav_rows) >= 50:
                flush()
    flush()

    if t_rows:
        tdf = pd.DataFrame(t_rows)
        tdf.to_csv(TIMING_CSV, mode="a", header=not os.path.exists(TIMING_CSV),
                   index=False, encoding="utf-8-sig")
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

    if os.path.exists(range_csv):
        rr = pd.read_csv(range_csv, dtype={"影像号": str})
        if len(rr):
            agg = rr.groupby(["filter", "split"]).agg(
                n=("影像号", "nunique"), frac_below_mean=("frac_below", "mean"),
                frac_above_mean=("frac_above", "mean"),
                n_any_below=("n_below", lambda s: int((s > 0).sum())),
                n_any_above=("n_above", lambda s: int((s > 0).sum())),
                roi_min=("roi_min", "min"), roi_max=("roi_max", "max")).reset_index()
            agg.to_csv(sum_csv, index=False, encoding="utf-8-sig")
            print("\n===== ROI 越界汇总（filter × split）=====")
            print(agg.to_string(index=False))

    print(f"\n完成: 成功 {n_ok}，失败 {n_err}，耗时 {time.perf_counter() - t0:.1f}s，"
          f"平均 {((time.perf_counter() - t0) / n_ok if n_ok else 0):.2f}s/例")
    print(f"输出目录: {outdir}")


if __name__ == "__main__":
    main()
