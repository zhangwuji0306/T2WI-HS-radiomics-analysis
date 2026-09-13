"""计算训练集 A 各滤波输出（Wavelet coif1 8 子带 / LoG σ=1,2,3 mm）肿瘤 ROI 合并标准差 σ_A，
为 Wavelet/LoG连续滤波输出提供固定箱宽与A参考范围（与Original的合并标准差法一致）。

滤波由 PyRadiomics 3.0.1 内部实现（radiomics.imageoperations.getWaveletImage /
getLoGImage）施加于未离散化的归一化图像；按肿瘤 ROI（掩膜标签 1）收集体素计算合并统计。
仅使用训练集 A（GE DISCOVERY MR750 3T，R1 读者）。
结果写入 configs/sigma_a_filters.json（副本 output/configs/）。

用法:
  python scripts/compute_sigma_a_filters.py [--ids ID1,ID2] [--limit N] [--workers 8]
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
from radiomics import imageoperations
from workflow_utils import atomic_write_csv, atomic_write_json
from sigma_guard import promote_complete_sigma
from data_split_guard import resolve_cohort_membership

radiomics.setVerbosity(logging.ERROR)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(OUT, "manifest.csv")
SCANNER = os.path.join(OUT, "scanner_map.csv")
OUT_JSON = os.path.join(ROOT, "configs", "sigma_a_filters.json")
ARMS = {"muscle": os.path.join(OUT, "preprocessed"),
        "zscore": os.path.join(OUT, "preprocessed_zscore")}
LOG_SIGMAS = [1.0, 2.0, 3.0]


def load_a_cases() -> pd.DataFrame:
    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    df = resolve_cohort_membership(man, sc)
    if "排除" in df.columns:
        df = df[df["排除"].fillna("0").astype(str).ne("1")]
    return df.loc[df["split"] == "A", ["影像号"]].drop_duplicates("影像号")


def roi_stats(img_out: sitk.Image, m: np.ndarray) -> tuple:
    arr = sitk.GetArrayFromImage(img_out)
    if arr.dtype != np.float64:
        arr = arr.astype(np.float64)
    v = arr[m == 1]
    return (int(v.size), float(v.sum()), float((v * v).sum()),
            float(v.min()), float(v.max()))


def prepass_task(task: tuple) -> dict:
    arm, pid, img_path, mask_path = task
    try:
        img = sitk.ReadImage(img_path)
        m_img = sitk.ReadImage(mask_path)
        m = sitk.GetArrayFromImage(m_img)
        out: dict = {}
        for im, name, _kw in imageoperations.getWaveletImage(img, m_img):
            out[name] = roi_stats(im, m)
        for im, name, _kw in imageoperations.getLoGImage(img, m_img, sigma=LOG_SIGMAS):
            out[name] = roi_stats(im, m)
        return {"ok": True, "arm": arm, "pid": pid, "stats": out}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "arm": arm, "pid": pid, "error": f"{type(e).__name__}: {e}"}


def main() -> None:
    ap = argparse.ArgumentParser(description="训练集A滤波输出固定箱宽与参考范围")
    ap.add_argument("--ids", help="逗号分隔影像号（缺省全队列 A）")
    ap.add_argument("--limit", type=int, help="仅处理前 N 例（测试用）")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    a = load_a_cases()
    ids = list(a["影像号"])
    if args.ids:
        sel = [x.strip() for x in args.ids.split(",") if x.strip()]
        ids = [x for x in ids if x in sel]
    if args.limit:
        ids = ids[:args.limit]
    print(f"训练集 A: {len(ids)} 例 × 2 通路")

    tasks = []
    for arm, prep in ARMS.items():
        for pid in ids:
            d = os.path.join(prep, pid)
            tasks.append((arm, pid, os.path.join(d, "R1_image.nrrd"),
                          os.path.join(d, "R1_mask.nrrd")))

    acc: dict[tuple, list] = {}
    n_fail = 0
    failures: list[dict] = []
    used_by_arm = {arm: set() for arm in ARMS}
    t0 = time.perf_counter()
    with multiprocessing.Pool(args.workers) as pool:
        for res in pool.imap_unordered(prepass_task, tasks, chunksize=4):
            if not res["ok"]:
                n_fail += 1
                failures.append({"arm": res["arm"], "patient_id": res["pid"],
                                 "failure_type": "filter_or_roi_failure",
                                 "error": res["error"]})
                print(f"[FAIL] {res['arm']} {res['pid']}: {res['error']}")
                continue
            if len(res["stats"]) != 11:
                n_fail += 1
                failures.append({"arm": res["arm"], "patient_id": res["pid"],
                                 "failure_type": "incomplete_filter_outputs",
                                 "error": "expected 11 filters, got %d" % len(res["stats"])})
                continue
            used_by_arm[res["arm"]].add(res["pid"])
            for k, (n, s, sq, mn, mx) in res["stats"].items():
                a0 = acc.setdefault((res["arm"], k), [0, 0.0, 0.0, math.inf, -math.inf])
                a0[0] += n
                a0[1] += s
                a0[2] += sq
                a0[3] = min(a0[3], mn)
                a0[4] = max(a0[4], mx)
    print(f"预扫描完成: {len(tasks) - n_fail}/{len(tasks)}，失败 {n_fail}，耗时 {time.perf_counter() - t0:.1f}s")

    arms_out: dict = {}
    for (arm, k), (n, s, sq, mn, mx) in sorted(acc.items()):
        mean = s / n
        var = max(sq / n - mean * mean, 0.0)
        sig = math.sqrt(var)
        arms_out.setdefault(arm, {})[k] = {"mean": round(mean, 6), "sigma": round(sig, 6),
                                           "min": round(mn, 6), "max": round(mx, 6),
                                           "n_voxels": n}
        print(f"\n[{arm}] {k}:  σ_A={sig:.4f}  范围 [{mn:.4f}, {mx:.4f}]  n={n:,}")
        for f in (0.1, 0.25):
            bw = f * sig
            nb = int(math.ceil((mx - mn) / bw)) if bw > 0 else 1
            print(f"    f={f}:  binWidth={bw:.4f}  网格 bin 数 ≈ {nb}")

    arm_complete = {arm: len(used_by_arm[arm]) == len(ids) for arm in ARMS}
    expected_filter_keys = 11
    filters_complete = all(len(arms_out.get(arm, {})) == expected_filter_keys
                           for arm in ARMS)
    complete_case_pass = (n_fail == 0 and all(arm_complete.values()) and
                          filters_complete and len(tasks) == len(ids) * len(ARMS))
    doc = {
        "method": "各滤波输出PyRadiomics固定箱宽；binWidth=f×σ_A(filt)；min/max仅作A参考范围；仅训练集A "
                  "（GE DISCOVERY MR750 3T，R1）肿瘤 ROI 合并统计；滤波 = PyRadiomics "
                  "imageoperations（Wavelet coif1 8 子带 / LoG σ=1,2,3 mm）",
        "n_cases": len(ids),
        "n_cases_expected": len(ids),
        "n_cases_used": min((len(values) for values in used_by_arm.values()), default=0),
        "n_cases_failed": n_fail,
        "complete_case_pass": bool(complete_case_pass),
        "n_filters_expected_per_arm": expected_filter_keys,
        "log_sigmas": LOG_SIGMAS,
        "f_values": [0.1, 0.25],
        "arms": arms_out,
    }
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    if not complete_case_pass:
        atomic_write_csv(pd.DataFrame(failures),
                         os.path.join(OUT, "configs", "sigma_a_filters_errors.csv"))
        raise RuntimeError("filtered sigma_A incomplete: formal JSON was not overwritten")
    promote_complete_sigma(doc, OUT_JSON,
                           os.path.join(OUT, "configs", "sigma_a_filters.json"))
    print(f"\n已写入 {OUT_JSON}")


if __name__ == "__main__":
    main()
