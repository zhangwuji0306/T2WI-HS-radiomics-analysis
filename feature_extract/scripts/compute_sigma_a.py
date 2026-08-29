"""计算训练集 A 肿瘤 ROI 合并标准差 σ_A（binWidth = f × σ_A 的固定数据源）。

仅使用训练集 A（GE DISCOVERY MR750 3T，R1 读者）肿瘤 ROI（掩膜标签 1）体素，
分别在肌肉均值归一化（output/preprocessed/）与 Z-score（output/preprocessed_zscore/）
两套预处理产物上计算合并标准差 σ_A 与合并最小/最大值；σ_A用于固定箱宽，min/max仅作A参考范围。
结果写入 configs/sigma_a.json 并归档至 output/configs/；binWidth 由该文件固定，
提取阶段只读取、不重算。

用法:
  python scripts/compute_sigma_a.py
"""
from __future__ import annotations

import json
import math
import os
import shutil
import time

import numpy as np
import pandas as pd
import SimpleITK as sitk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(OUT, "manifest.csv")
SCANNER = os.path.join(OUT, "scanner_map.csv")
SIGMA_JSON = os.path.join(ROOT, "configs", "sigma_a.json")
ARMS = {"muscle": "output/preprocessed", "zscore": "output/preprocessed_zscore"}


def load_a_cases() -> pd.DataFrame:
    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    df = man.merge(sc[["影像号", "R1厂商", "R1机型", "R1场强"]], on="影像号", how="left")
    df["_f"] = pd.to_numeric(df["R1场强"], errors="coerce")
    a = df[(df["R1厂商"] == "GE MEDICAL SYSTEMS") & (df["R1机型"] == "DISCOVERY MR750") &
           (df["_f"].round(1) == 3.0) & (df["排除"] != "1")]
    return a[["影像号"]].drop_duplicates("影像号")


def arm_stats(ids: list[str], prep_dir: str) -> dict:
    n = 0
    s = 0.0
    sq = 0.0
    mn = math.inf
    mx = -math.inf
    missing: list[str] = []
    t0 = time.perf_counter()
    for pid in ids:
        d = os.path.join(prep_dir, pid)
        ip = os.path.join(d, "R1_image.nrrd")
        mp = os.path.join(d, "R1_mask.nrrd")
        if not (os.path.exists(ip) and os.path.exists(mp)):
            missing.append(pid)
            continue
        arr = sitk.GetArrayFromImage(sitk.ReadImage(ip)).astype(np.float64)
        m = sitk.GetArrayFromImage(sitk.ReadImage(mp))
        roi = arr[m == 1]
        if roi.size == 0:
            continue
        n += int(roi.size)
        s += float(roi.sum())
        sq += float((roi * roi).sum())
        mn = min(mn, float(roi.min()))
        mx = max(mx, float(roi.max()))
    mean = s / n if n else float("nan")
    var = max(sq / n - mean * mean, 0.0) if n else float("nan")
    std = math.sqrt(var) if n else float("nan")
    return {"n_cases": len(ids), "n_voxels": n, "mean": mean, "sigma": std,
            "min": mn, "max": mx, "missing": missing,
            "seconds": round(time.perf_counter() - t0, 1)}


def main() -> None:
    a = load_a_cases()
    ids = list(a["影像号"])
    print(f"训练集 A: {len(ids)} 例")
    out: dict = {}
    for arm, prep in ARMS.items():
        st = arm_stats(ids, os.path.join(ROOT, prep))
        out[arm] = {k: v for k, v in st.items() if k != "missing"}
        print(f"\n[{arm}] 病例 {st['n_cases']}  体素 {st['n_voxels']:,}  "
              f"mean={st['mean']:.4f}  σ_A={st['sigma']:.4f}  "
              f"min={st['min']:.4f}  max={st['max']:.4f}  耗时 {st['seconds']}s")
        if st["missing"]:
            print(f"  缺失文件 {len(st['missing'])} 例: {st['missing'][:10]}")
        for f in (0.1, 0.25):
            bw = f * st["sigma"]
            nb = int(math.ceil((st["max"] - st["min"]) / bw)) if bw > 0 else 1
            print(f"  f={f}: binWidth = {bw:.4f}  网格 bin 数 ≈ {nb}")
    doc = {
        "method": "PyRadiomics固定箱宽；binWidth=f×σ_A；min/max仅作A参考范围；不裁剪B",
        "n_cases": len(ids),
        "f_values": [0.1, 0.25],
        "main": {"normalization": "muscle", "f": 0.25},
        "arms": out,
    }
    with open(SIGMA_JSON, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
    shutil.copy2(SIGMA_JSON, os.path.join(OUT, "configs", "sigma_a.json"))
    print(f"\n已写入 {SIGMA_JSON}")


if __name__ == "__main__":
    main()
