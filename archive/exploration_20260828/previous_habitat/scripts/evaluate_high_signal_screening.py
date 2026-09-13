"""Evaluate high-signal screening scenarios on the outcome-blind R1/R2 pilot."""
from __future__ import annotations

import os
from typing import Dict

import numpy as np
import pandas as pd


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAB_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(HAB_ROOT)
OUT_ROOT = os.path.join(HAB_ROOT, "output", "high_signal_eligibility_audit")
FEATURES = os.path.join(OUT_ROOT, "patient_features.csv")
PAIR_METRICS = os.path.join(HAB_ROOT, "output", "technical_pilot_amended", "pair_metrics.csv")
SCANNER_MAP = os.path.join(PROJECT_ROOT, "feature_extract", "output", "scanner_map.csv")


SCENARIOS: Dict[str, Dict[str, float]] = {
    "any_ge_fat_mean": {"volume_mm3": 1e-12},
    "lenient": {"fraction": 0.001},
    "equiv_64vox": {"volume_mm3": 128.0},
    "fraction_0.1pct": {"fraction": 0.001},
    "fraction_0.25pct": {"fraction": 0.0025},
    "fraction_0.5pct": {"fraction": 0.005},
    "fraction_1pct": {"fraction": 0.01},
    "volume128_fraction0.5": {"volume_mm3": 128.0, "fraction": 0.005},
    "volume128_fraction1": {"volume_mm3": 128.0, "fraction": 0.01},
    "volume256_fraction0.5": {"volume_mm3": 256.0, "fraction": 0.005},
    "volume256_fraction1": {"volume_mm3": 256.0, "fraction": 0.01},
    "volume256_fraction1_core16": {"volume_mm3": 256.0, "fraction": 0.01,
                                    "core2_mm3": 16.0},
    "volume256_fraction1_lcc128": {"volume_mm3": 256.0, "fraction": 0.01,
                                    "lcc_mm3": 128.0},
    "fraction1_lcc128_core32": {"fraction": 0.01, "lcc_mm3": 128.0,
                                 "core2_mm3": 32.0},
    "volume128_fraction1_lcc128_core32": {"volume_mm3": 128.0, "fraction": 0.01,
                                           "lcc_mm3": 128.0, "core2_mm3": 32.0},
    "volume128_fraction0.5_lcc128_core32": {"volume_mm3": 128.0, "fraction": 0.005,
                                             "lcc_mm3": 128.0, "core2_mm3": 32.0},
    "volume256_fraction0.5_lcc128_core32": {"volume_mm3": 256.0, "fraction": 0.005,
                                             "lcc_mm3": 128.0, "core2_mm3": 32.0},
    "volume128_fraction0.5_core16": {"volume_mm3": 128.0, "fraction": 0.005,
                                      "core2_mm3": 16.0},
    "balanced": {"volume_mm3": 128.0, "fraction": 0.005, "lcc_mm3": 64.0,
                 "core2_mm3": 16.0, "lcc_core2_mm3": 8.0},
    "recommended": {"fraction": 0.01,
                    "lcc_mm3": 128.0, "core2_mm3": 32.0},
    "spatial_lenient": {"volume_mm3": 64.0, "fraction": 0.0025, "lcc_mm3": 32.0,
                        "core2_mm3": 8.0, "lcc_core2_mm3": 2.0},
    "strict": {"volume_mm3": 256.0, "fraction": 0.01, "lcc_mm3": 128.0,
               "core2_mm3": 32.0, "lcc_core2_mm3": 16.0},
}


def pass_mask(frame: pd.DataFrame, spec: Dict[str, float]) -> pd.Series:
    out = pd.Series(True, index=frame.index)
    out &= frame["high_volume_mm3"] >= spec.get("volume_mm3", 0.0)
    out &= frame["high_fraction"] >= spec.get("fraction", 0.0)
    out &= frame["high_lcc_volume_mm3"] >= spec.get("lcc_mm3", 0.0)
    out &= frame["high_core2_volume_mm3"] >= spec.get("core2_mm3", 0.0)
    out &= frame["high_lcc_core2_volume_mm3"] >= spec.get("lcc_core2_mm3", 0.0)
    return out.fillna(False)


def icc_2_1(x: np.ndarray, y: np.ndarray) -> float:
    data = np.column_stack([x, y]).astype(float)
    data = data[np.isfinite(data).all(axis=1)]
    n, k = data.shape if data.ndim == 2 else (0, 0)
    if n < 2 or k != 2:
        return np.nan
    grand = data.mean()
    row_means = data.mean(axis=1)
    col_means = data.mean(axis=0)
    ms_subject = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_rater = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = data - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    denom = ms_subject + (k - 1) * ms_error + k * (ms_rater - ms_error) / n
    return float((ms_subject - ms_error) / denom) if abs(denom) > 1e-12 else np.nan


def main() -> None:
    features = pd.read_csv(FEATURES, encoding="utf-8-sig", dtype={"patient_id": str})
    metrics = pd.read_csv(PAIR_METRICS, encoding="utf-8-sig", dtype={"影像号": str})
    metrics = metrics[metrics["变体"] == "patient_k2_1x1x2"].copy()
    r1 = features[features["reader"] == "R1"].set_index("patient_id")
    r2 = features[features["reader"] == "R2"].set_index("patient_id")
    cohort_rows = []
    paired_ids = sorted(set(r1.index[r1["same_sequence_R1_R2"] == 1]) & set(r2.index))
    for scenario, spec in SCENARIOS.items():
        p1 = pass_mask(r1, spec)
        p2 = pass_mask(r2, spec)
        row = {"scenario": scenario}
        row.update(spec)
        for split in ("ALL", "A", "B"):
            use = pd.Series(True, index=r1.index) if split == "ALL" else (r1["split"] == split)
            row[split + "_n"] = int(use.sum())
            row[split + "_pass_n"] = int((p1 & use).sum())
            row[split + "_pass_rate"] = float((p1 & use).sum() / use.sum()) if use.sum() else np.nan
        if paired_ids:
            a = p1.loc[paired_ids].to_numpy(dtype=bool)
            b = p2.loc[paired_ids].to_numpy(dtype=bool)
            pa, pb = float(a.mean()), float(b.mean())
            expected = pa * pb + (1.0 - pa) * (1.0 - pb)
            observed = float((a == b).mean())
            row["paired_same_sequence_n"] = len(paired_ids)
            row["paired_agreement"] = observed
            row["paired_kappa"] = ((observed - expected) / (1.0 - expected)
                                    if expected < 1.0 else np.nan)
            row["paired_R1_pass_n"] = int(a.sum())
            row["paired_R2_pass_n"] = int(b.sum())
            row["paired_both_pass_n"] = int((a & b).sum())
        cohort_rows.append(row)
    pd.DataFrame(cohort_rows).to_csv(
        os.path.join(OUT_ROOT, "threshold_scenarios_extended.csv"),
        index=False, encoding="utf-8-sig")

    scanner = pd.read_csv(SCANNER_MAP, encoding="utf-8-sig", dtype=str).fillna("")
    scanner = scanner.rename(columns={"影像号": "patient_id"}).set_index("patient_id")
    device = r1.join(scanner[["R1厂商", "R1机型", "R1场强"]], how="left")
    device_rows = []
    for scenario in ("volume128_fraction0.5", "balanced", "recommended", "strict"):
        passed = pass_mask(device, SCENARIOS[scenario])
        temp = device.copy()
        temp["passed"] = passed.astype(int)
        for keys, group in temp.groupby(["split", "R1厂商", "R1机型", "R1场强"], dropna=False):
            device_rows.append({
                "scenario": scenario, "split": keys[0], "manufacturer": keys[1],
                "model": keys[2], "field_strength_T": keys[3], "n": len(group),
                "pass_n": int(group["passed"].sum()),
                "pass_rate": float(group["passed"].mean()),
            })
    pd.DataFrame(device_rows).to_csv(
        os.path.join(OUT_ROOT, "device_screening_summary.csv"),
        index=False, encoding="utf-8-sig")

    decisions = r1.reset_index().copy()
    decisions["criterion_any_ge_fat_mean"] = (decisions["high_voxels_ge_fat_mean"] > 0).astype(int)
    decisions["criterion_high_fraction_ge_1pct"] = (decisions["high_fraction"] >= 0.01).astype(int)
    decisions["criterion_high_lcc_volume_ge_128mm3"] = (decisions["high_lcc_volume_mm3"] >= 128.0).astype(int)
    decisions["criterion_high_core2_volume_ge_32mm3"] = (decisions["high_core2_volume_mm3"] >= 32.0).astype(int)
    decisions["recommended_pass"] = pass_mask(decisions, SCENARIOS["recommended"]).astype(int)
    decisions["lenient_pass"] = pass_mask(decisions, SCENARIOS["lenient"]).astype(int)

    def failure_reason(row: pd.Series) -> str:
        reasons = []
        if row["criterion_any_ge_fat_mean"] == 0:
            reasons.append("无肿瘤体素达到脂肪均值")
        if row["criterion_high_fraction_ge_1pct"] == 0:
            reasons.append("高信号体素占比<1%")
        if row["criterion_high_lcc_volume_ge_128mm3"] == 0:
            reasons.append("最大26连通成分体积<128mm3")
        if row["criterion_high_core2_volume_ge_32mm3"] == 0:
            reasons.append("距肿瘤边界>=2mm的高信号体积<32mm3")
        return ";".join(reasons)

    decisions["failure_reasons"] = decisions.apply(failure_reason, axis=1)
    decisions["lenient_failure_reasons"] = ""
    decisions.loc[decisions["high_voxels_ge_fat_mean"] <= 0, "lenient_failure_reasons"] = "无肿瘤体素达到脂肪均值"
    decisions.loc[(decisions["high_voxels_ge_fat_mean"] > 0) &
                  (decisions["high_fraction"] < 0.001), "lenient_failure_reasons"] = "高信号体素占比<0.1%"
    keep_cols = [
        "patient_id", "split", "fat_mean", "tumor_voxels", "tumor_volume_mm3",
        "fat_voxels", "fat_volume_mm3", "high_voxels_ge_fat_mean",
        "high_volume_mm3", "high_equiv_voxels_1x1x2", "high_fraction",
        "high_lcc_voxels", "high_lcc_volume_mm3", "high_lcc_fraction",
        "high_core2_voxels", "high_core2_volume_mm3", "high_core2_fraction_of_high",
        "high_max_depth_mm", "high_lcc_max_depth_mm",
        "criterion_any_ge_fat_mean", "criterion_high_fraction_ge_1pct",
        "criterion_high_lcc_volume_ge_128mm3",
        "criterion_high_core2_volume_ge_32mm3", "recommended_pass",
        "lenient_pass", "failure_reasons", "lenient_failure_reasons",
    ]
    decisions[keep_cols].to_csv(
        os.path.join(OUT_ROOT, "recommended_screening_decisions.csv"),
        index=False, encoding="utf-8-sig")
    decisions.loc[decisions["recommended_pass"] == 1, keep_cols].to_csv(
        os.path.join(OUT_ROOT, "recommended_selected_cases.csv"),
        index=False, encoding="utf-8-sig")
    decisions[keep_cols].to_csv(
        os.path.join(OUT_ROOT, "lenient_screening_decisions.csv"),
        index=False, encoding="utf-8-sig")
    decisions.loc[decisions["lenient_pass"] == 1, keep_cols].to_csv(
        os.path.join(OUT_ROOT, "lenient_selected_cases.csv"),
        index=False, encoding="utf-8-sig")

    rows = []
    for scenario, spec in SCENARIOS.items():
        p1 = pass_mask(r1, spec)
        p2 = pass_mask(r2, spec)
        for selection_mode in ("R1_only", "both_readers"):
            if selection_mode == "R1_only":
                selected = set(p1[p1].index)
            else:
                selected = set(p1[p1].index) & set(p2[p2].index)
            for scale, group0 in metrics.groupby("尺度mm"):
                group = group0[group0["影像号"].isin(selected)].copy()
                x = pd.to_numeric(group["H-high_fraction_R1"], errors="coerce").to_numpy()
                y = pd.to_numeric(group["H-high_fraction_R2"], errors="coerce").to_numpy()
                rows.append({
                    "scenario": scenario,
                    "selection_mode": selection_mode,
                    "scale_mm": float(scale),
                    "n": len(group),
                    "H_low_Dice_median": pd.to_numeric(group["H-low_Dice"], errors="coerce").median(),
                    "H_high_Dice_median": pd.to_numeric(group["H-high_Dice"], errors="coerce").median(),
                    "H_high_fraction_ICC_2_1": icc_2_1(x, y),
                })
    pd.DataFrame(rows).to_csv(os.path.join(OUT_ROOT, "technical_subset_evaluation.csv"),
                              index=False, encoding="utf-8-sig")
    print("wrote:", os.path.join(OUT_ROOT, "technical_subset_evaluation.csv"))


if __name__ == "__main__":
    main()
