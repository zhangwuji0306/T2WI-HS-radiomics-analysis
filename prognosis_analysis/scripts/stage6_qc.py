"""阶段六 v2：测量学质控与候选池冻结，不进行预测数据驱动筛选。

输入 feature_extract/output/features_v2。固定预筛选仅包括 A 内 22 对双读者
ICC(2,1)>0.75 和 A 内 R1 缺失检查。近零方差、跨特征族相关去重及标准化必须在
嵌套交叉验证的每个外层训练折内拟合，本脚本不提前执行。
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
EX_ROOT = os.path.join(PROJECT_ROOT, "feature_extract")
FEATURE_SCRIPTS = os.path.join(EX_ROOT, "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import read_b_csv, require_b_unlock  # noqa: E402
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(EX_ROOT, "output", "manifest.csv")
SCANNER = os.path.join(EX_ROOT, "output", "scanner_map.csv")
FEATURES = os.path.join(EX_ROOT, "output", "features_v2")
STAGE6 = os.path.join(OUT, "qc", "stage6_v2")

ICC_THRESHOLD = 0.75
BATCHES = {
    "original": ("features_original.csv", ["影像号", "读者", "split", "normalization", "f", "binWidth"]),
    "wavelet": ("features_wavelet.csv", ["影像号", "读者", "split", "normalization", "f"]),
    "log": ("features_log.csv", ["影像号", "读者", "split", "normalization", "f"]),
}
EXPECTED_FEATURES = {"original": 107, "wavelet": 8 * 93, "log": 3 * 93}
COMBOS = ["muscle_f0.25", "muscle_f0.1", "zscore_f0.1", "zscore_f0.25"]


def load_pairs() -> list[str]:
    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    df = man.merge(sc[["影像号", "R1机型"]], on="影像号", how="left")
    pairs = df.loc[df["是否双读者"] == "1", "影像号"].tolist()
    a_pairs = [x for x in pairs if df.loc[df["影像号"] == x, "R1机型"].iloc[0]
               == "DISCOVERY MR750"]
    return a_pairs


def icc21(pivot: pd.DataFrame) -> float:
    """ICC(2,1)：two-way random, absolute agreement, single measures。"""
    pivot = pivot.dropna()
    n, k = pivot.shape
    if n < 3 or k < 2:
        return float("nan")
    grand = float(pivot.values.mean())
    ss_subject = k * float(((pivot.mean(axis=1) - grand) ** 2).sum())
    ss_rater = n * float(((pivot.mean(axis=0) - grand) ** 2).sum())
    ss_total = float(((pivot - grand) ** 2).values.sum())
    ss_error = max(ss_total - ss_subject - ss_rater, 0.0)
    ms_subject = ss_subject / (n - 1)
    ms_rater = ss_rater / (k - 1)
    ms_error = max(ss_error / ((n - 1) * (k - 1)), 1e-12)
    return (ms_subject - ms_error) / (
        ms_subject + (k - 1) * ms_error + k * (ms_rater - ms_error) / n)


def process_table(combo: str, batch: str, a_pairs: list[str], split: str = "A") -> dict:
    if split not in ("A", "B", "all"):
        raise ValueError("split must be A, B, or all")
    if split in ("B", "all"):
        # The authorization check is deliberately before path validation and
        # before pandas is allowed to open a B QC/radiomics table.
        require_b_unlock()
    fname, meta = BATCHES[batch]
    path = os.path.join(FEATURES, combo, fname)
    if not os.path.exists(path):
        raise FileNotFoundError(f"缺少 v2 特征表：{path}；请先完成修正版特征重提取")
    df = read_b_csv(path, dtype={"影像号": str}) if split in ("B", "all") else pd.read_csv(
        path, dtype={"影像号": str})
    feat_cols = [c for c in df.columns if c not in meta]
    if len(feat_cols) != EXPECTED_FEATURES[batch]:
        raise AssertionError(
            f"{combo}/{batch} 特征数 {len(feat_cols)}，预期 {EXPECTED_FEATURES[batch]}；"
            "请检查是否仍含滤波 Shape 或旧版产物")
    if batch != "original" and any("_shape_" in c for c in feat_cols):
        raise AssertionError(f"{combo}/{batch} 仍含滤波 Shape，拒绝继续")

    readers = df[df["读者"].isin(["R1", "R2"])]
    rows = []
    for col in feat_cols:
        p_a = readers.loc[readers["影像号"].isin(a_pairs)].pivot(
            index="影像号", columns="读者", values=col)
        rows.append({"feature": col, "icc_A": icc21(p_a),
                     "n_A": int(p_a.dropna().shape[0])})
    icc = pd.DataFrame(rows)
    icc["pass_icc"] = icc["icc_A"] > ICC_THRESHOLD

    a_r1 = df[(df["split"] == "A") & (df["读者"] == "R1")]
    missing = a_r1[feat_cols].isna().sum()
    icc["n_missing_A_R1"] = icc["feature"].map(missing).astype(int)
    icc["candidate"] = icc["pass_icc"] & (icc["n_missing_A_R1"] == 0)
    dropped = icc.loc[~icc["candidate"],
                      ["feature", "icc_A", "n_A", "n_missing_A_R1"]].copy()
    dropped["reason"] = np.where(~icc.loc[~icc["candidate"], "pass_icc"].to_numpy(),
                                 "ICC_A<=0.75", "A_R1_missing")
    candidates = icc.loc[icc["candidate"], ["feature", "icc_A", "n_A"]].copy()
    candidates.insert(0, "batch", batch)
    return {"icc": icc, "dropped": dropped, "candidates": candidates,
            "n_total": len(feat_cols), "n_icc": int(icc["pass_icc"].sum()),
            "n_missing": int((icc["pass_icc"] & (icc["n_missing_A_R1"] > 0)).sum()),
            "n_candidates": len(candidates)}


def main() -> None:
    ap = argparse.ArgumentParser(description="阶段六 v2：ICC 固定预筛选")
    ap.add_argument("--combos", default=",".join(COMBOS))
    args = ap.parse_args()
    combos = [x.strip() for x in args.combos.split(",") if x.strip()]
    a_pairs = load_pairs()
    summaries = []

    for combo in combos:
        outdir = os.path.join(STAGE6, combo)
        os.makedirs(outdir, exist_ok=True)
        combined = []
        for batch in BATCHES:
            result = process_table(combo, batch, a_pairs)
            result["icc"].to_csv(os.path.join(outdir, f"{batch}_icc.csv"), index=False,
                                 encoding="utf-8-sig")
            result["dropped"].to_csv(os.path.join(outdir, f"{batch}_dropped.csv"), index=False,
                                     encoding="utf-8-sig")
            result["candidates"].to_csv(
                os.path.join(outdir, f"{batch}_candidate_features.csv"), index=False,
                encoding="utf-8-sig")
            combined.append(result["candidates"])
            summaries.append({"combo": combo, "batch": batch,
                              "n_total": result["n_total"], "n_icc_pass": result["n_icc"],
                              "n_missing_drop": result["n_missing"],
                              "n_candidates": result["n_candidates"]})
            print(f"[{combo}/{batch}] {result['n_total']} → ICC {result['n_icc']} "
                  f"→ 候选 {result['n_candidates']}")
        all_candidates = pd.concat(combined, ignore_index=True)
        if all_candidates["feature"].duplicated().any():
            dup = all_candidates.loc[all_candidates["feature"].duplicated(), "feature"].tolist()[:5]
            raise AssertionError(f"跨批次存在重复特征名：{dup}")
        all_candidates.to_csv(os.path.join(outdir, "candidate_features.csv"), index=False,
                              encoding="utf-8-sig")

    summary = pd.DataFrame(summaries)
    os.makedirs(STAGE6, exist_ok=True)
    summary.to_csv(os.path.join(STAGE6, "summary.csv"), index=False, encoding="utf-8-sig")
    lines = ["# 阶段六 v2 特征质控汇总", "",
             f"- A 内双读者 {len(a_pairs)} 对用于 ICC(2,1)>0.75；冻结前不读取或报告B集ICC。",
             "- v2 使用连续强度一阶特征、固定箱宽纹理；Shape 仅在 Original 提取一次。",
             "- 近零方差、跨三批次相关去重和标准化全部延后至嵌套 CV 外层训练折。",
             "", "| 情景 | 批次 | 总数 | ICC通过 | 缺失剔除 | 候选 |",
             "|---|---|---:|---:|---:|---:|"]
    for _, row in summary.iterrows():
        lines.append(f"| {row['combo']} | {row['batch']} | {row['n_total']} | "
                     f"{row['n_icc_pass']} | {row['n_missing_drop']} | {row['n_candidates']} |")
    with open(os.path.join(STAGE6, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
