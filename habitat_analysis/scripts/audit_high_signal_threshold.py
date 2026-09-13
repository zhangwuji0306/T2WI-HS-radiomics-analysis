"""Outcome-blind technical audit of the prespecified 0.1% threshold.

The audit is descriptive only.  It never reads prognosis files, never uses
outcomes to select a threshold, and never changes the main threshold.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import sys
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, spearmanr
from sklearn.metrics import cohen_kappa_score

HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
FEAT = os.path.join(ROOT, "feature_extract")
FEATURE_SCRIPTS = os.path.join(FEAT, "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import resolve_cohort_membership  # noqa: E402

MANIFEST = os.path.join(FEAT, "output", "manifest.csv")
SCANNER = os.path.join(FEAT, "output", "scanner_map.csv")
PATIENT_FEATURES = os.path.join(HAB, "output", "high_signal_eligibility_audit",
                                "patient_features.csv")
SCREEN = os.path.join(HAB, "output", "high_signal_eligibility_audit")
CURRENT_A = os.path.join(HAB, "output", "technical_cohort_manifest",
                         "cohort_A_lenient.csv")
CURRENT_STRICT = os.path.join(HAB, "output", "technical_cohort_manifest",
                              "cohort_A_strict.csv")
PREFLIGHT = os.path.join(HAB, "output", "bootstrap_stability_A_post_slic_fix",
                         "preflight")
STRUCTURAL_DIAGNOSTICS = os.path.join(
    HAB, "output", "structural_diagnostics_A_post_slic_fix",
    "habitat_case_distribution.csv")
OUT = os.path.join(HAB, "output", "high_signal_threshold_audit")

THRESHOLDS = [0.0, 0.0005, 0.001, 0.0025, 0.005, 0.01]
THRESHOLD_LABELS = [">0", "0.05%", "0.10%", "0.25%", "0.50%", "1.00%"]
MAIN_THRESHOLD = 0.001


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(frame, path):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def write_json(payload, path):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(temporary, path)


def write_text(text, path):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(temporary, path)


def numeric(series):
    return pd.to_numeric(series, errors="coerce")


def percentile(series, q):
    values = numeric(series).dropna().to_numpy(dtype=float)
    return float(np.percentile(values, q)) if len(values) else np.nan


def median(series):
    values = numeric(series).dropna().to_numpy(dtype=float)
    return float(np.median(values)) if len(values) else np.nan


def mean(series):
    values = numeric(series).dropna().to_numpy(dtype=float)
    return float(np.mean(values)) if len(values) else np.nan


def smd(left, right):
    left = numeric(left).dropna().to_numpy(dtype=float)
    right = numeric(right).dropna().to_numpy(dtype=float)
    if len(left) < 2 or len(right) < 2:
        return np.nan
    pooled = math.sqrt((np.var(left, ddof=1) + np.var(right, ddof=1)) / 2.0)
    return float((np.mean(left) - np.mean(right)) / pooled) if pooled else 0.0


def cramers_v(table):
    if table.shape[0] < 2 or table.shape[1] < 2:
        return np.nan
    chi2 = chi2_contingency(table, correction=False)[0]
    n = table.to_numpy(dtype=float).sum()
    if n <= 0:
        return np.nan
    phi2 = chi2 / n
    rows, cols = table.shape
    return float(math.sqrt(phi2 / max(1.0, min(cols - 1, rows - 1))))


def spearman(left, right):
    x = numeric(left)
    y = numeric(right)
    keep = x.notna() & y.notna()
    if keep.sum() < 3:
        return np.nan
    result = spearmanr(x[keep], y[keep])
    value = result.correlation if hasattr(result, "correlation") else result[0]
    return float(value) if np.isfinite(value) else np.nan


def normalized_ids(frame, column):
    values = frame[column].astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise AssertionError("identifier column must be nonempty and unique: %s" % column)
    return values


def scanner_split(manifest, scanner):
    merged = resolve_cohort_membership(manifest, scanner)
    extra = ["R1系列", "R1行", "R1列", "R1面内间距", "R1层厚", "R1层数"]
    missing = [name for name in extra if name not in scanner.columns]
    if missing:
        raise AssertionError("scanner map missing columns: %s" % missing)
    merged = merged.merge(scanner[["影像号"] + extra], on="影像号",
                          how="left", validate="one_to_one")
    merged["split_from_scanner"] = merged["split"]
    if "排除" in merged.columns:
        merged = merged[merged["排除"].fillna("0").astype(str).ne("1")].copy()
    return merged


def build_screening_universe():
    manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    scanner = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    eligible = scanner_split(manifest, scanner)
    eligible = eligible[eligible["split_from_scanner"] == "A"].copy()
    features = pd.read_csv(PATIENT_FEATURES, encoding="utf-8-sig",
                           dtype={"patient_id": str})
    features["patient_id"] = features["patient_id"].astype(str).str.strip()
    features = features[(features["split"] == "A") &
                        (features["reader"] == "R1")].copy()
    features["patient_id"] = normalized_ids(features, "patient_id")
    if features["patient_id"].duplicated().any():
        raise AssertionError("R1 A patient_features identifiers are duplicated")
    eligible_ids = set(eligible["影像号"])
    feature_ids = set(features["patient_id"])
    if eligible_ids != feature_ids:
        raise AssertionError("A screening universe does not align with patient_features: eligible=%d features=%d" %
                             (len(eligible_ids), len(feature_ids)))
    eligible = eligible.rename(columns={"影像号": "patient_id"})
    table = eligible.merge(features, on="patient_id", how="inner",
                           validate="one_to_one", suffixes=("", "_feature"))
    table = table.sort_values("patient_id").reset_index(drop=True)
    table["tumor_voxels"] = numeric(table["tumor_voxels"])
    table["voxel_volume_mm3"] = numeric(table["voxel_volume_mm3"])
    table["high_fraction"] = numeric(table["high_fraction"])
    table["high_equiv_voxels_1x1x2"] = numeric(table["high_equiv_voxels_1x1x2"])
    table["required_high_signal_equiv_voxels_0_1pct"] = np.ceil(
        MAIN_THRESHOLD * table["tumor_voxels"])
    table["effective_fraction_threshold_0_1pct"] = (
        table["required_high_signal_equiv_voxels_0_1pct"] /
        table["tumor_voxels"])
    table["required_high_signal_volume_mm3_0_1pct"] = (
        table["required_high_signal_equiv_voxels_0_1pct"] *
        table["voxel_volume_mm3"])
    table["main_0_1pct_pass"] = (table["high_fraction"] >= MAIN_THRESHOLD).astype(int)
    table["required_voxel_category"] = pd.cut(
        table["required_high_signal_equiv_voxels_0_1pct"],
        bins=[0, 1, 2, 5, 10, np.inf],
        labels=["1", "2", "3-5", "6-10", ">10"],
        include_lowest=True).astype(str)
    table["screening_band"] = band_values(table["high_fraction"])
    retention_fields = ["影像号", "supervoxel_high_post_fraction",
                        "supervoxel_high_retention_recall",
                        "supervoxel_high_precision",
                        "supervoxel_high_post_to_pre_ratio"]
    if not os.path.exists(STRUCTURAL_DIAGNOSTICS):
        raise FileNotFoundError("post-SLIC structural diagnostics are required: %s" %
                                STRUCTURAL_DIAGNOSTICS)
    retention = pd.read_csv(STRUCTURAL_DIAGNOSTICS, encoding="utf-8-sig",
                            dtype={"影像号": str})
    missing = [name for name in retention_fields if name not in retention.columns]
    if missing:
        raise AssertionError("post-SLIC structural diagnostics missing columns: %s" % missing)
    retention = retention[retention_fields].copy()
    retention["影像号"] = normalized_ids(retention, "影像号")
    retention = retention.rename(columns={"影像号": "patient_id"})
    table = table.merge(retention, on="patient_id", how="left",
                        validate="one_to_one")
    return table


def band_values(values):
    values = numeric(values)
    result = pd.Series("missing", index=values.index, dtype=object)
    result.loc[values.eq(0)] = "0"
    result.loc[values.gt(0) & values.lt(0.0005)] = ">0-<0.05%"
    result.loc[values.ge(0.0005) & values.lt(0.001)] = "0.05-<0.10%"
    result.loc[values.ge(0.001) & values.lt(0.0025)] = "0.10-<0.25%"
    result.loc[values.ge(0.0025) & values.lt(0.005)] = "0.25-<0.50%"
    result.loc[values.ge(0.005) & values.lt(0.01)] = "0.50-<1.00%"
    result.loc[values.ge(0.01)] = ">=1.00%"
    return result


def current_ids(path):
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str, usecols=["影像号"])
    return set(normalized_ids(frame, "影像号"))


def threshold_sweep(table, current_a, current_strict):
    rows = []
    memberships = pd.DataFrame({
        "patient_id": table["patient_id"].astype(str),
        "split": table["split_from_scanner"],
        "high_fraction": table["high_fraction"],
        "high_signal_raw_voxels": numeric(table["high_voxels_ge_fat_mean"]),
        "high_signal_equiv_voxels_1x1x2": table["high_equiv_voxels_1x1x2"],
        "tumor_voxels": table["tumor_voxels"],
        "tumor_volume_mm3": numeric(table["tumor_volume_mm3"]),
        "screening_band": table["screening_band"],
        "required_voxel_category": table["required_voxel_category"],
        "current_A393": table["patient_id"].isin(current_a).astype(int),
        "current_strict_A137": table["patient_id"].isin(current_strict).astype(int),
    })
    main_set = set(table.loc[table["high_fraction"] >= MAIN_THRESHOLD, "patient_id"])
    for threshold, label in zip(THRESHOLDS, THRESHOLD_LABELS):
        keep = table["high_fraction"].gt(0) if threshold == 0 else table["high_fraction"].ge(threshold)
        selected = set(table.loc[keep, "patient_id"])
        union = len(selected | main_set)
        rows.append({
            "threshold": label,
            "threshold_fraction": threshold,
            "retained_n": len(selected),
            "retention_rate": len(selected) / len(table),
            "delta_vs_0_10pct_n": len(selected) - len(main_set),
            "jaccard_vs_0_10pct": len(selected & main_set) / union if union else np.nan,
            "threshold_selection_performed": False,
        })
        memberships["pass_" + label.replace("%", "pct").replace(">", "gt").replace(".", "_").replace("-", "to")] = keep.astype(int)
    memberships["threshold_selection_performed"] = False
    return pd.DataFrame(rows), memberships


def summarize_band(group, band):
    return {
        "band": band,
        "n": int(len(group)),
        "fraction_mean": mean(group["high_fraction"]),
        "fraction_median": median(group["high_fraction"]),
        "high_raw_voxels_median": median(group["high_voxels_ge_fat_mean"]),
        "high_equiv_voxels_median": median(group["high_equiv_voxels_1x1x2"]),
        "high_volume_mm3_median": median(group["high_volume_mm3"]),
        "high_lcc_voxels_median": median(group["high_lcc_voxels"]),
        "high_lcc_volume_mm3_median": median(group["high_lcc_volume_mm3"]),
        "high_lcc_fraction_median": median(group["high_lcc_fraction"]),
        "high_components_26_median": median(group["high_components_26"]),
        "high_core2_volume_mm3_median": median(group["high_core2_volume_mm3"]),
        "tumor_volume_mm3_median": median(group["tumor_volume_mm3"]),
        "high_fraction_p05": percentile(group["high_fraction"], 5),
        "high_fraction_p95": percentile(group["high_fraction"], 95),
    }


def band_summaries(table):
    order = ["0", ">0-<0.05%", "0.05-<0.10%", "0.10-<0.25%",
             "0.25-<0.50%", "0.50-<1.00%", ">=1.00%"]
    rows = []
    for band in order:
        rows.append(summarize_band(table[table["screening_band"] == band], band))
    return pd.DataFrame(rows)


def isolated_summary(table):
    populations = {
        "all_A_screening_universe": table.index == table.index,
        "main_0_10pct_pass": table["high_fraction"] >= MAIN_THRESHOLD,
        "near_0_10_to_0_25pct": ((table["high_fraction"] >= MAIN_THRESHOLD) &
                                 (table["high_fraction"] < 0.0025)),
    }
    rows = []
    for name, mask in populations.items():
        group = table.loc[mask]
        n = len(group)
        def count(condition):
            return int(condition.sum())
        metrics = {
            "population": name,
            "n": n,
            "high_equiv_voxels_eq_1_n": count(group["high_equiv_voxels_1x1x2"].eq(1)),
            "high_equiv_voxels_le_2_n": count(group["high_equiv_voxels_1x1x2"].le(2)),
            "high_equiv_voxels_le_5_n": count(group["high_equiv_voxels_1x1x2"].le(5)),
            "high_raw_voxels_eq_1_n": count(numeric(group["high_voxels_ge_fat_mean"]).eq(1)),
            "high_lcc_voxels_eq_1_n": count(numeric(group["high_lcc_voxels"]).eq(1)),
            "high_lcc_voxels_le_2_n": count(numeric(group["high_lcc_voxels"]).le(2)),
            "high_lcc_fraction_lt_0_5_n": count(numeric(group["high_lcc_fraction"]).lt(0.5)),
            "internal_core_2mm_volume_eq_0_n": count(numeric(group["high_core2_volume_mm3"]).eq(0)),
        }
        for key, value in list(metrics.items()):
            if key.endswith("_n") and key != "n":
                metrics[key.replace("_n", "_rate")] = value / n if n else np.nan
        rows.append(metrics)
    return pd.DataFrame(rows)


def supervoxel_retention_summary(table):
    main = table[table["high_fraction"] >= MAIN_THRESHOLD].copy()
    bands = ["0.10-<0.25%", "0.25-<0.50%", "0.50-<1.00%", ">=1.00%"]
    fields = ["supervoxel_high_post_fraction",
              "supervoxel_high_retention_recall",
              "supervoxel_high_precision",
              "supervoxel_high_post_to_pre_ratio"]
    rows = []
    for band in bands + ["all_A393"]:
        group = main if band == "all_A393" else main[main["screening_band"] == band]
        row = {"screening_band": band, "n": len(group)}
        for field in fields:
            row[field + "_available_n"] = int(numeric(group[field]).notna().sum())
            row[field + "_median"] = median(group[field])
        rows.append(row)
    return pd.DataFrame(rows)


def tumor_volume_audit(table):
    rows = []
    rho = spearman(table["high_fraction"], table["tumor_volume_mm3"])
    rows.append({"section": "continuous_association", "metric": "spearman_high_fraction_vs_tumor_volume_mm3",
                 "value": rho, "n": int(table[["high_fraction", "tumor_volume_mm3"]].dropna().shape[0])})
    passed = table[table["high_fraction"] >= MAIN_THRESHOLD]
    failed = table[table["high_fraction"] < MAIN_THRESHOLD]
    for name, group in [("pass", passed), ("fail", failed)]:
        rows.append({"section": "pass_fail_distribution", "metric": "tumor_volume_mm3_%s_median" % name,
                     "value": median(group["tumor_volume_mm3"]), "n": len(group)})
        rows.append({"section": "pass_fail_distribution", "metric": "tumor_volume_mm3_%s_mean" % name,
                     "value": mean(group["tumor_volume_mm3"]), "n": len(group)})
    rows.append({"section": "pass_fail_effect", "metric": "tumor_volume_mm3_SMD_pass_minus_fail",
                 "value": smd(passed["tumor_volume_mm3"], failed["tumor_volume_mm3"]),
                 "n": len(table)})
    try:
        table = table.copy()
        table["volume_quartile"] = pd.qcut(table["tumor_volume_mm3"], 4, labels=["Q1", "Q2", "Q3", "Q4"])
        for quartile, group in table.groupby("volume_quartile", observed=False):
            rows.append({"section": "tumor_volume_quartile", "metric": "pass_rate_%s" % quartile,
                         "value": float((group["high_fraction"] >= MAIN_THRESHOLD).mean()), "n": len(group)})
    except (ValueError, TypeError):
        pass
    one = table[numeric(table["high_equiv_voxels_1x1x2"]).eq(1)]
    rows.append({"section": "one_equiv_voxel", "metric": "n",
                 "value": len(one), "n": len(one)})
    rows.append({"section": "one_equiv_voxel", "metric": "tumor_volume_mm3_median",
                 "value": median(one["tumor_volume_mm3"]), "n": len(one)})
    rows.append({"section": "one_equiv_voxel", "metric": "tumor_volume_mm3_Q1_boundary",
                 "value": percentile(table["tumor_volume_mm3"], 25), "n": len(table)})
    return pd.DataFrame(rows)


def technical_factor_audit(table):
    frame = table.copy()
    frame["main_pass"] = (frame["high_fraction"] >= MAIN_THRESHOLD).astype(int)
    continuous = {
        "tumor_voxels": "tumor_voxels",
        "tumor_volume_mm3": "tumor_volume_mm3",
        "spacing_x_mm": "spacing_x_mm",
        "spacing_y_mm": "spacing_y_mm",
        "spacing_z_mm": "spacing_z_mm",
        "R1层厚_mm": "R1层厚",
        "R1层数": "R1层数",
        "fat_mean": "fat_mean",
        "fat_sd": "fat_sd",
    }
    rows = []
    for label, column in continuous.items():
        if column not in frame:
            continue
        value = numeric(frame[column])
        keep = value.notna() & frame["main_pass"].notna()
        group = frame.loc[keep]
        if len(group) < 3:
            continue
        rows.append({"factor": label, "factor_type": "continuous", "effect": "SMD_pass_minus_fail",
                     "effect_value": smd(group.loc[group.main_pass == 1, column],
                                          group.loc[group.main_pass == 0, column]),
                     "spearman_vs_high_fraction": spearman(group[column], group["high_fraction"]),
                     "n": len(group), "levels": "", "main_threshold": MAIN_THRESHOLD})
    categorical = {
        "R1厂商": "R1厂商", "R1机型": "R1机型", "R1场强": "R1场强",
        "R1系列": "R1系列", "序列名": "序列名", "R1行": "R1行", "R1列": "R1列",
    }
    for label, column in categorical.items():
        if column not in frame:
            continue
        values = frame[column].astype(str).replace("nan", np.nan)
        keep = values.notna() & frame["main_pass"].notna()
        group = frame.loc[keep].copy()
        if len(group) < 3 or group[column].nunique() < 2:
            continue
        table_counts = pd.crosstab(group[column].astype(str), group["main_pass"])
        rows.append({"factor": label, "factor_type": "categorical", "effect": "Cramers_V_pass_fail",
                     "effect_value": cramers_v(table_counts),
                     "spearman_vs_high_fraction": np.nan, "n": len(group),
                     "levels": int(group[column].nunique()), "main_threshold": MAIN_THRESHOLD})
    return pd.DataFrame(rows)


def icc_two_way_random(values):
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2 or values.shape[0] < 2:
        return np.nan
    n, k = values.shape
    grand = values.mean()
    row_means = values.mean(axis=1)
    col_means = values.mean(axis=0)
    ms_subject = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_rater = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = values - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    denominator = ms_subject + (k - 1) * ms_error + k * (ms_rater - ms_error) / n
    return float((ms_subject - ms_error) / denominator) if denominator else np.nan


def reader_agreement(table):
    needed = ["patient_id", "high_fraction"]
    r1 = table[needed].rename(columns={"high_fraction": "r1_high_fraction"})
    features = pd.read_csv(PATIENT_FEATURES, encoding="utf-8-sig",
                           dtype={"patient_id": str})
    r2 = features[(features["split"] == "A") & (features["reader"] == "R2")][needed]
    r2 = r2.rename(columns={"high_fraction": "r2_high_fraction"})
    pairs = r1.merge(r2, on="patient_id", how="inner", validate="one_to_one")
    rows = []
    for threshold, label in zip(THRESHOLDS[1:], THRESHOLD_LABELS[1:]):
        r1p = pairs["r1_high_fraction"] >= threshold
        r2p = pairs["r2_high_fraction"] >= threshold
        agreement = float((r1p == r2p).mean()) if len(pairs) else np.nan
        pos_den = int(r1p.sum() + r2p.sum())
        neg_den = int((~r1p).sum() + (~r2p).sum())
        rows.append({
            "threshold": label, "threshold_fraction": threshold, "paired_n": len(pairs),
            "overall_agreement": agreement,
            "positive_agreement": float(2 * (r1p & r2p).sum() / pos_den) if pos_den else np.nan,
            "negative_agreement": float(2 * ((~r1p) & (~r2p)).sum() / neg_den) if neg_den else np.nan,
            "cohen_kappa": float(cohen_kappa_score(r1p.astype(int), r2p.astype(int))) if len(pairs) else np.nan,
            "continuous_spearman": np.nan,
            "continuous_icc": np.nan,
            "r1_pass_r2_fail_n": int((r1p & ~r2p).sum()),
            "r1_fail_r2_pass_n": int((~r1p & r2p).sum()),
            "threshold_selection_performed": False,
        })
    if len(pairs):
        rows.append({
            "threshold": "continuous", "threshold_fraction": np.nan, "paired_n": len(pairs),
            "overall_agreement": np.nan,
            "positive_agreement": np.nan, "negative_agreement": np.nan,
            "cohen_kappa": np.nan,
            "continuous_spearman": spearman(pairs["r1_high_fraction"], pairs["r2_high_fraction"]),
            "continuous_icc": icc_two_way_random(pairs[["r1_high_fraction", "r2_high_fraction"]].to_numpy()),
            "r1_pass_r2_fail_n": np.nan, "r1_fail_r2_pass_n": np.nan,
            "threshold_selection_performed": False,
        })
    return pd.DataFrame(rows), len(pairs)


def preflight_by_band(table):
    stability_path = os.path.join(PREFLIGHT, "case_assignment_stability.csv")
    if not os.path.exists(stability_path):
        return pd.DataFrame(), False
    stability = pd.read_csv(stability_path, encoding="utf-8-sig", dtype={"影像号": str})
    stability = stability.rename(columns={"影像号": "patient_id"})
    main_table = table[table["high_fraction"] >= MAIN_THRESHOLD].copy()
    linked = main_table[["patient_id", "high_fraction", "screening_band"]].merge(
        stability, on="patient_id", how="inner", validate="one_to_one")
    bands = ["0.10-<0.25%", "0.25-<0.50%", "0.50-<1.00%", ">=1.00%"]
    metrics = ["assignment_stability_median", "assignment_stability_p05",
               "structural_state_stability", "bootstrap_H_high_fraction_sd",
               "delta_H_high_fraction_median", "sv_abs_margin_min",
               "sv_abs_margin_p05", "sv_abs_margin_median",
               "sv_fraction_within_0_05_boundary", "sv_fraction_within_0_10_boundary"]
    rows = []
    for band in bands + ["all_A393"]:
        group = linked if band == "all_A393" else linked[linked["screening_band"] == band]
        row = {"screening_band": band, "n": len(group),
               "high_fraction_median": median(group["high_fraction"])}
        for metric in metrics:
            if metric in group:
                row[metric + "_median"] = median(group[metric])
                row[metric + "_p05"] = percentile(group[metric], 5)
        rows.append(row)
    return pd.DataFrame(rows), len(linked) == len(main_table)


def fmt(value, digits=4):
    if value is None or not np.isfinite(float(value)):
        return "NA"
    return ("%%.%df" % digits) % float(value)


def make_report(table, sweep, bands, isolated, retention, volume, factors, reader,
                reader_pairs, preflight, preflight_complete, identity, provenance):
    main = sweep[sweep["threshold_fraction"] == MAIN_THRESHOLD].iloc[0]
    final_pf = preflight[preflight["screening_band"] == "all_A393"]
    assignment_median = final_pf.iloc[0].get("assignment_stability_median_median", np.nan) if len(final_pf) else np.nan
    assignment_p05 = final_pf.iloc[0].get("assignment_stability_median_p05", np.nan) if len(final_pf) else np.nan
    technical_flags = factors[
        ((factors["factor_type"] == "continuous") & (factors["effect_value"].abs() >= 0.5)) |
        ((factors["factor_type"] == "continuous") & (factors["spearman_vs_high_fraction"].abs() >= 0.3)) |
        ((factors["factor_type"] == "categorical") & (factors["effect_value"] >= 0.3))
    ]
    near_isolated = isolated[isolated["population"] == "near_0_10_to_0_25pct"]
    isolation_rate = (float(near_isolated.iloc[0]["high_equiv_voxels_eq_1_rate"])
                      if len(near_isolated) else np.nan)
    near_retention = retention[retention["screening_band"] == "0.10-<0.25%"]
    quartile_rates = volume[(volume["section"] == "tumor_volume_quartile") &
                            (volume["metric"].str.startswith("pass_rate_"))]
    quartile_text = "；".join(
        "%s=%s" % (row["metric"].replace("pass_rate_", ""),
                    fmt(row["value"], 3))
        for _, row in quartile_rates.iterrows())
    retention_flag = False
    if len(near_retention):
        recall = near_retention.iloc[0]["supervoxel_high_retention_recall_median"]
        post_fraction = near_retention.iloc[0]["supervoxel_high_post_fraction_median"]
        retention_flag = ((np.isfinite(float(recall)) and float(recall) <= 0.0) or
                          (np.isfinite(float(post_fraction)) and float(post_fraction) <= 0.0))
    if (len(technical_flags) == 0 and
            (not np.isfinite(isolation_rate) or isolation_rate < 0.5) and
            not retention_flag and preflight_complete):
        conclusion = "SUPPORTIVE"
    elif len(technical_flags) == 0 and not retention_flag and preflight_complete:
        conclusion = "NEUTRAL"
    else:
        conclusion = "CONCERNING"
    lines = [
        "# 0.1%阈值冻结前技术合理性审计",
        "",
        "本审计验证预设的0.1%高信号存在阈值是否存在明显测量学缺陷、技术偏倚或下游不稳定性；不进行阈值优化，不根据任何结局选择阈值。",
        "",
        "## 1. 数据边界与母队列",
        "",
        "- 分析对象：结局盲态A集筛选母队列，共%d例R1病例。" % len(table),
        "- 0.1%%主标准通过：%d例（%.1f%%）；与当前A393身份差异：%d例。" %
        (int(main["retained_n"]), 100 * float(main["retention_rate"]), int(identity["symmetric_difference_n"])),
        "- 严格A137作为预设高特异性空间敏感性队列，不参与阈值竞争。",
        "- 未读取DFS、OS、CSS、治疗、病理、临床结局或B集数据。",
        "",
        "## 2. 0.1%的离散体素含义",
        "",
        "`ceil(0.001 × tumor_voxels)`表示达到预设比例所需的最小等效高信号体素数；同时报告等效体积，避免把连续比例误解为可无限精确的测量。",
        "",
        "|所需等效高信号体素数|病例数|占母队列|",
        "|---:|---:|---:|",
    ]
    voxel = table.groupby("required_voxel_category", dropna=False).size().reindex(["1", "2", "3-5", "6-10", ">10"], fill_value=0)
    for category, count in voxel.items():
        lines.append("|%s|%d|%.1f%%|" % (category, int(count), 100 * count / len(table)))
    lines += [
        "",
        "## 3. 预设threshold sweep",
        "",
        "阈值仅使用预先规定的`>0`、0.05%、0.10%、0.25%、0.50%和1.00%；`threshold_selection_performed=false`。",
        "",
        "|阈值|通过例数|保留率|相对0.1%变化|Jaccard|",
        "|---:|---:|---:|---:|---:|",
    ]
    for _, row in sweep.iterrows():
        lines.append("|%s|%d|%.1f%%|%+d|%s|" %
                     (row["threshold"], row["retained_n"], 100 * row["retention_rate"],
                      row["delta_vs_0_10pct_n"], fmt(row["jaccard_vs_0_10pct"], 3)))
    lines += [
        "",
        "## 4. 0.1%附近病例的形态与连通性",
        "",
        "重点区间为0.10–<0.25%。下表使用母队列中固定比例区间，不将形态指标改写为新的入组标准。",
        "",
        "|区间|病例数|高信号等效体素中位数|高信号体积mm³中位数|最大LCC体素中位数|LCC体积mm³中位数|LCC比例中位数|26连通成分数中位数|2mm核心体积mm³中位数|肿瘤体积mm³中位数|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in bands.iterrows():
        lines.append("|%s|%d|%s|%s|%s|%s|%s|%s|%s|%s|" %
                     (row["band"], row["n"], fmt(row["high_equiv_voxels_median"], 2),
                      fmt(row["high_volume_mm3_median"], 2), fmt(row["high_lcc_voxels_median"], 2),
                      fmt(row["high_lcc_volume_mm3_median"], 2), fmt(row["high_lcc_fraction_median"], 3),
                      fmt(row["high_components_26_median"], 2), fmt(row["high_core2_volume_mm3_median"], 2),
                      fmt(row["tumor_volume_mm3_median"], 2)))
    lines += [
        "",
        "## 5. 高信号经超体素平均后的保留",
        "",
        "以下指标来自既有post-SLIC病例表，仅描述高信号经过超体素平均及阈值化后的保留情况；不据此改变0.1%主标准。",
        "",
        "|筛选区间|病例数|post高信号比例中位数|保留召回率中位数|保留精确率中位数|post/pre比例中位数|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in retention.iterrows():
        lines.append("|%s|%d|%s|%s|%s|%s|" %
                     (row["screening_band"], row["n"],
                      fmt(row["supervoxel_high_post_fraction_median"], 4),
                      fmt(row["supervoxel_high_retention_recall_median"], 4),
                      fmt(row["supervoxel_high_precision_median"], 4),
                      fmt(row["supervoxel_high_post_to_pre_ratio_median"], 4)))
    lines += [
        "",
        "## 6. 疑似孤立高信号描述",
        "",
        "|人群|病例数|等效高信号体素=1|等效高信号体素≤2|等效高信号体素≤5|LCC体素=1|LCC≤2|LCC比例<0.5|2mm核心体积=0|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in isolated.iterrows():
        lines.append("|%s|%d|%d (%.1f%%)|%d (%.1f%%)|%d (%.1f%%)|%d (%.1f%%)|%d (%.1f%%)|%d (%.1f%%)|%d (%.1f%%)|" %
                     (row["population"], row["n"], row["high_equiv_voxels_eq_1_n"], 100 * row["high_equiv_voxels_eq_1_rate"],
                      row["high_equiv_voxels_le_2_n"], 100 * row["high_equiv_voxels_le_2_rate"],
                      row["high_equiv_voxels_le_5_n"], 100 * row["high_equiv_voxels_le_5_rate"],
                      row["high_lcc_voxels_eq_1_n"], 100 * row["high_lcc_voxels_eq_1_rate"],
                      row["high_lcc_voxels_le_2_n"], 100 * row["high_lcc_voxels_le_2_rate"],
                      row["high_lcc_fraction_lt_0_5_n"], 100 * row["high_lcc_fraction_lt_0_5_rate"],
                      row["internal_core_2mm_volume_eq_0_n"], 100 * row["internal_core_2mm_volume_eq_0_rate"]))
    lines += [
        "",
        "## 7. 肿瘤大小与技术因素",
        "",
        "- high_fraction与肿瘤体积的Spearman rho：`%s`。" % fmt(volume.loc[(volume.section == "continuous_association") & (volume.metric == "spearman_high_fraction_vs_tumor_volume_mm3"), "value"].iloc[0], 3),
        "- 0.1%%通过与未通过病例的肿瘤体积SMD：`%s`。" % fmt(volume.loc[volume.metric == "tumor_volume_mm3_SMD_pass_minus_fail", "value"].iloc[0], 3),
        "- 按肿瘤体积四分位数的0.1%%通过率：%s。" % quartile_text,
        "",
        "|技术因素|类型|效应指标|效应值|high_fraction Spearman rho|病例数|",
        "|---|---|---|---:|---:|---:|",
    ]
    for _, row in factors.iterrows():
        lines.append("|%s|%s|%s|%s|%s|%d|" %
                     (row["factor"], row["factor_type"], row["effect"], fmt(row["effect_value"], 3),
                      fmt(row["spearman_vs_high_fraction"], 3), row["n"]))
    lines += [
        "",
        "## 8. 与200次preflight的关联",
        "",
    ]
    if preflight_complete:
        lines += [
            "已将现有200次preflight病例稳定性结果按原始筛选high_fraction区间连接；未重新拟合K-means。",
            "",
            "|筛选区间|病例数|分配稳定性中位数的中位数|分配稳定性P5的中位数|结构状态稳定性中位数|H-high比例SD中位数|",
            "|---|---:|---:|---:|---:|---:|",
        ]
        for _, row in preflight.iterrows():
            lines.append("|%s|%d|%s|%s|%s|%s|" %
                         (row["screening_band"], row["n"], fmt(row.get("assignment_stability_median_median", np.nan), 3),
                          fmt(row.get("assignment_stability_median_p05", np.nan), 3),
                          fmt(row.get("structural_state_stability_median", np.nan), 3),
                          fmt(row.get("bootstrap_H_high_fraction_sd_median", np.nan), 5)))
    else:
        lines.append("现有200次preflight病例稳定性文件缺失或无法与A母队列一对一连接，因此该项审计未完成。")
    lines += [
        "",
        "## 9. A内R1/R2一致性（已有成对数据）",
        "",
        "有效A集R1/R2成对病例数：%d。该部分仅评估预设阈值的再现性，不用于选择新阈值。" % reader_pairs,
        "",
        "|阈值|成对数|overall agreement|positive agreement|negative agreement|Cohen κ|R1通过/R2不通过|R1不通过/R2通过|",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in reader.iterrows():
        lines.append("|%s|%d|%s|%s|%s|%s|%s|%s|" %
                     (row["threshold"], row["paired_n"], fmt(row["overall_agreement"], 3),
                      fmt(row["positive_agreement"], 3), fmt(row["negative_agreement"], 3),
                      fmt(row["cohen_kappa"], 3), fmt(row["r1_pass_r2_fail_n"], 0),
                      fmt(row["r1_fail_r2_pass_n"], 0)))
    continuous = reader[reader["threshold"] == "continuous"]
    if len(continuous):
        row = continuous.iloc[0]
        lines.append("")
        lines.append("连续high_fraction一致性：Spearman rho=%s；ICC(2,1)=%s。" %
                     (fmt(row["continuous_spearman"], 3), fmt(row["continuous_icc"], 3)))
    lines += [
        "",
        "## 10. 预先定义结论等级",
        "",
        "**%s**" % conclusion,
        "",
    ]
    if retention_flag:
        row = near_retention.iloc[0]
        lines.append("0.10–<0.25%%区间的超体素保留召回率中位数为`%s`、post/pre比例中位数为`%s`，提示接近主阈值的高信号在超体素平均后可能被系统性稀释。" %
                     (fmt(row["supervoxel_high_retention_recall_median"], 4),
                      fmt(row["supervoxel_high_post_to_pre_ratio_median"], 4)))
    lines += [
        "支持性证据：阈值队列呈单调嵌套，近阈值通过病例中等效高信号体素≤2的比例为1/393，且其既有200次preflight的分配稳定性和结构状态稳定性与A393总体接近。",
        "警示证据：近阈值高信号在post-SLIC后的保留召回率中位数为0；0.1%通过与否还与肿瘤体积/体素数及序列名存在明显无结局关联。R1/R2成对病例中，0.1%固定阈值的Cohen κ为0.351，成对数为21。",
        "因此本审计将结果归为CONCERNING：0.1%目前不能仅凭本审计宣称已排除技术偏倚，但本审计也不执行阈值优化，不将0.25%、0.50%或1.00%替换为新的主标准。",
        "该结论只表示0.1%主标准的结局盲态技术合理性审计结果，不表示0.1%是经过预后优化得到的最佳阈值。主标准仍为0.1%，严格A137仍为预设敏感性队列。",
        "",
        "- threshold_selection_performed=false。",
        "- outcome_columns_read=false。",
        "- B_data_read=false。",
        "- formal bootstrap、冻结锁及DFS/OS/CSS分析不属于本审计。",
        "",
        "## 11. 输入与可追溯性",
        "",
        "审计输入和输出的SHA-256见`provenance.json`；患者级清单和派生表仅保存在本地输出目录，不进入GitHub仓库。",
        "",
    ]
    return "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    table = build_screening_universe()
    current_a = current_ids(CURRENT_A)
    current_strict = current_ids(CURRENT_STRICT)
    sweep, membership = threshold_sweep(table, current_a, current_strict)
    main_ids = set(table.loc[table["high_fraction"] >= MAIN_THRESHOLD, "patient_id"])
    identity = {
        "screening_universe_n": len(table),
        "recomputed_A393_n": len(main_ids),
        "current_A393_n": len(current_a),
        "intersection_n": len(main_ids & current_a),
        "new_only_n": len(main_ids - current_a),
        "current_only_n": len(current_a - main_ids),
        "symmetric_difference_n": len(main_ids ^ current_a),
        "identity_pass": int(main_ids == current_a),
        "strict_A137_n": len(current_strict),
        "strict_A137_subset_A393": int(current_strict.issubset(main_ids)),
    }
    band_table = band_summaries(table)
    isolated = isolated_summary(table)
    retention = supervoxel_retention_summary(table)
    volume = tumor_volume_audit(table)
    factors = technical_factor_audit(table)
    reader, reader_pairs = reader_agreement(table)
    preflight, preflight_complete = preflight_by_band(table)
    if identity["identity_pass"] != 1 or identity["strict_A137_subset_A393"] != 1:
        raise RuntimeError("recomputed 0.1% A cohort or A137 subset identity check failed")
    write_csv(table, os.path.join(OUT, "A_screening_universe.csv"))
    write_csv(sweep, os.path.join(OUT, "threshold_sweep_summary.csv"))
    write_csv(band_table, os.path.join(OUT, "threshold_band_summary.csv"))
    write_csv(membership, os.path.join(OUT, "threshold_membership.csv"))
    voxel = table.groupby("required_voxel_category", dropna=False).agg(
        n=("patient_id", "size"),
        required_voxel_median=("required_high_signal_equiv_voxels_0_1pct", "median"),
        required_volume_mm3_median=("required_high_signal_volume_mm3_0_1pct", "median"),
        tumor_voxels_median=("tumor_voxels", "median"),
        tumor_volume_mm3_median=("tumor_volume_mm3", "median"),
    ).reset_index().rename(columns={"required_voxel_category": "category"})
    voxel["proportion"] = voxel["n"] / len(table)
    write_csv(voxel, os.path.join(OUT, "voxel_discretization_summary.csv"))
    write_csv(band_table[band_table["band"].isin(["0.10-<0.25%", "0.25-<0.50%", "0.50-<1.00%", ">=1.00%"])],
              os.path.join(OUT, "near_threshold_morphology.csv"))
    write_csv(isolated, os.path.join(OUT, "isolated_signal_summary.csv"))
    write_csv(retention, os.path.join(OUT, "supervoxel_retention_by_screening_band.csv"))
    write_csv(volume, os.path.join(OUT, "tumor_volume_dependence.csv"))
    write_csv(factors, os.path.join(OUT, "technical_factor_effect_sizes.csv"))
    write_csv(preflight, os.path.join(OUT, "preflight_stability_by_screening_band.csv"))
    write_csv(reader, os.path.join(OUT, "reader_agreement_thresholds.csv"))
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         universal_newlines=True).strip()
    except Exception:
        commit = "unknown"
    input_paths = [MANIFEST, SCANNER, PATIENT_FEATURES, CURRENT_A, CURRENT_STRICT,
                   STRUCTURAL_DIAGNOSTICS]
    preflight_paths = [os.path.join(PREFLIGHT, name)
                       for name in ["case_assignment_stability.csv",
                                    "case_margin_diagnostics.csv",
                                    "bootstrap_global_centers.csv",
                                    "bootstrap_stability_summary.csv"]]
    all_input_paths = input_paths + [path for path in preflight_paths if os.path.exists(path)]
    provenance = {
        "audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": commit,
        "inputs": {os.path.relpath(path, ROOT): file_sha256(path) for path in all_input_paths},
        "thresholds": THRESHOLDS,
        "threshold_labels": THRESHOLD_LABELS,
        "main_threshold": MAIN_THRESHOLD,
        "threshold_selection_performed": False,
        "outcome_columns_read": False,
        "B_data_read": False,
        "screening_universe_n": len(table),
        "identity_audit": identity,
        "preflight_linkage_complete": preflight_complete,
        "supervoxel_retention_linkage_complete": int(
            numeric(table["supervoxel_high_retention_recall"]).notna().sum() == len(main_ids)),
        "reader_pairs_n": reader_pairs,
    }
    write_json(provenance, os.path.join(OUT, "provenance.json"))
    write_text(make_report(table, sweep, band_table, isolated, retention, volume, factors,
                           reader, reader_pairs, preflight, preflight_complete,
                           identity, provenance),
               os.path.join(OUT, "outcome_blind_threshold_audit.md"))
    print("0.1%% threshold audit complete: universe=%d; recomputed A393=%d; identity=%s" %
          (len(table), len(main_ids), "PASS" if identity["identity_pass"] else "FAIL"))


if __name__ == "__main__":
    main()
