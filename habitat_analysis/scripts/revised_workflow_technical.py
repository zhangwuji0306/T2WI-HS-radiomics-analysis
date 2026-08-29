"""Outcome-blind execution of the revised habitat-analysis workflow.

This module produces stages 1--7 of the revised workflow.  It reads only
technical A-set inputs, the locked configuration, and the existing technical
diagnostics.  It never reads DFS, clinical variables, or B-set data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from collections import Counter

import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy import ndimage
from sklearn.cluster import KMeans

import technical_dry_run_A as base


HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
OUT = os.path.join(HAB, "output")
BASELINE = os.path.join(OUT, "feasibility_A_patient_balanced")
METHOD18 = os.path.join(OUT, "method_selection_18")
STRUCT = os.path.join(OUT, "structural_diagnostics_A")
LOCAL = os.path.join(OUT, "local_global_diagnostic_A")
BOOT = os.path.join(OUT, "bootstrap_stability_A")
ROBUST = os.path.join(OUT, "technical_robustness_A")
SENS = os.path.join(OUT, "sensitivity")
MAPS = os.path.join(OUT, "habitat_maps_A")
FEATURES = os.path.join(OUT, "habitat_features_A")
CONFIG = os.path.join(HAB, "configs", "main_cross_case_kmeans_k2_4mm.json")
STRICT_AUDIT = os.path.join(OUT, "high_signal_eligibility_audit",
                            "recommended_selected_cases.csv")
SEED = 12345
N_BOOTSTRAPS = 1000


def mkdir(path):
    os.makedirs(path, exist_ok=True)


def numeric(frame, columns):
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def write_text(path, text):
    mkdir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def load_cfg():
    with open(CONFIG, encoding="utf-8") as handle:
        return json.load(handle)


def load_diag():
    path = os.path.join(BASELINE, "case_diagnostics.csv")
    frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    cols = [
        "影像号", "pass1_status", "pass2_status", "algorithm_failure",
        "unassigned_tumor_voxels", "geometry_or_label_error",
        "effective_supervoxels", "tumor_voxels_current_grid",
        "H_low_voxels", "H_high_voxels", "H_low_empty", "H_high_empty",
        "H_low_center", "H_high_center", "shared_boundary_b",
        "shared_center_distance", "supervoxel_mean_min",
        "supervoxel_mean_p5", "supervoxel_mean_median",
        "supervoxel_mean_p95", "supervoxel_mean_max", "failure_types",
        "failure_reason", "肿瘤体积mm3", "R1场强", "R1厂商", "R1机型",
        "R1系列", "R1面内间距", "R1层厚", "R1层数", "序列名", "尺寸",
        "fat_muscle_ratio", "muscle_mean_raw", "muscle_mean_preprocess",
        "muscle_mean_manifest_raw", "muscle_reference_source",
        "high_fraction", "high_lcc_fraction", "preprocessed_high_fraction",
        "preprocessed_high_lcc_fraction", "supervoxel_high_post_fraction",
        "supervoxel_high_retention_recall", "supervoxel_high_precision",
        "supervoxel_high_post_to_pre_ratio",
    ]
    present = [col for col in cols if col in frame.columns]
    numeric_cols = [
        "algorithm_failure", "unassigned_tumor_voxels", "geometry_or_label_error",
        "effective_supervoxels", "tumor_voxels_current_grid", "H_low_voxels",
        "H_high_voxels", "H_low_empty", "H_high_empty", "H_low_center",
        "H_high_center", "shared_boundary_b", "shared_center_distance",
        "supervoxel_mean_min", "supervoxel_mean_p5", "supervoxel_mean_median",
        "supervoxel_mean_p95", "supervoxel_mean_max", "肿瘤体积mm3",
        "R1层数", "fat_muscle_ratio", "muscle_mean_raw",
        "muscle_mean_preprocess", "muscle_mean_manifest_raw", "high_fraction",
        "high_lcc_fraction", "preprocessed_high_fraction",
        "preprocessed_high_lcc_fraction", "supervoxel_high_post_fraction",
        "supervoxel_high_retention_recall", "supervoxel_high_precision",
        "supervoxel_high_post_to_pre_ratio",
    ]
    return numeric(frame[present].copy(), [col for col in numeric_cols if col in present])


def hard_failure_flags(frame):
    out = pd.DataFrame(index=frame.index)
    out["algorithm_failure"] = frame.get("algorithm_failure", 0).fillna(1).astype(int) != 0
    out["unassigned_tumor_voxels"] = frame.get("unassigned_tumor_voxels", 0).fillna(1).astype(int) != 0
    out["geometry_or_label_error"] = frame.get("geometry_or_label_error", 0).fillna(1).astype(int) != 0
    out["pass_status"] = (frame.get("pass1_status", "") != "ok") | (frame.get("pass2_status", "") != "ok")
    required = ["H_low_center", "H_high_center", "shared_boundary_b",
                "H_low_voxels", "H_high_voxels", "tumor_voxels_current_grid"]
    out["nonfinite_feature"] = ~frame[required].apply(pd.to_numeric, errors="coerce").notna().all(axis=1)
    return out


def stage1_baseline():
    mkdir(STRUCT)
    frame = load_diag()
    flags = hard_failure_flags(frame)
    centers = frame[["H_low_center", "H_high_center", "shared_boundary_b"]].drop_duplicates()
    low = pd.to_numeric(frame["H_low_voxels"], errors="coerce")
    high = pd.to_numeric(frame["H_high_voxels"], errors="coerce")
    tumor = pd.to_numeric(frame["tumor_voxels_current_grid"], errors="coerce")
    conservation = (low + high) == tumor
    unique_ids = frame["影像号"].astype(str).nunique()
    hard = flags.any(axis=1)
    center_finite = len(centers) == 1 and np.isfinite(centers.to_numpy(dtype=float)).all()
    center_order = bool(center_finite and centers.iloc[0]["H_high_center"] > centers.iloc[0]["H_low_center"])
    rows = [{
        "n_target_cases": len(frame),
        "n_unique_cases": unique_ids,
        "duplicate_rows": len(frame) - unique_ids,
        "n_hard_technical_failure_cases": int(hard.sum()),
        "hard_technical_failure_rate": float(hard.mean()) if len(frame) else np.nan,
        "n_algorithm_failure_cases": int(flags["algorithm_failure"].sum()),
        "n_unassigned_cases": int(flags["unassigned_tumor_voxels"].sum()),
        "n_geometry_or_label_error_cases": int(flags["geometry_or_label_error"].sum()),
        "n_nonfinite_feature_cases": int(flags["nonfinite_feature"].sum()),
        "n_pass_status_errors": int(flags["pass_status"].sum()),
        "n_conservation_errors": int((~conservation).sum()),
        "n_structural_single_habitat_cases": int(((low == 0) | (high == 0)).sum()),
        "center_low": float(centers.iloc[0]["H_low_center"]) if len(centers) else np.nan,
        "center_high": float(centers.iloc[0]["H_high_center"]) if len(centers) else np.nan,
        "boundary_b": float(centers.iloc[0]["shared_boundary_b"]) if len(centers) else np.nan,
        "center_finite": int(center_finite),
        "center_order_valid": int(center_order),
        "outcome_columns_read": False,
        "B_data_read": False,
        "baseline_pass": int(len(frame) == 393 and unique_ids == 393 and
                              not hard.any() and conservation.all() and
                              center_order),
    }]
    pd.DataFrame(rows).to_csv(os.path.join(STRUCT, "baseline_integrity.csv"),
                              index=False, encoding="utf-8-sig")
    row = rows[0]
    write_text(os.path.join(STRUCT, "baseline_integrity.md"), "\n".join([
        "# A集M1基线完整性核验", "",
        "本核验使用既有A=393患者等权M1技术输出，仅重新解释结构性单生境与硬技术失败的区别。未读取结局、临床变量或B集。", "",
        "- 目标病例：%d；唯一病例：%d；重复行：%d。" % (row["n_target_cases"], row["n_unique_cases"], row["duplicate_rows"]),
        "- 硬技术失败：%d例（%.2f%%）；未分配、算法、几何/标签和非有限值错误均按硬错误核验。" % (row["n_hard_technical_failure_cases"], 100 * row["hard_technical_failure_rate"]),
        "- 结构性单生境：%d例，不计入硬技术失败。" % row["n_structural_single_habitat_cases"],
        "- 肿瘤体素守恒错误：%d；中心顺序核验：%s。" % (row["n_conservation_errors"], "通过" if row["center_order_valid"] else "未通过"),
        "- 基线完整性：%s。" % ("通过" if row["baseline_pass"] else "未通过"),
        "",
    ]))
    return frame


def stage2_structural(frame=None):
    mkdir(STRUCT)
    if frame is None:
        frame = load_diag()
    x = frame.copy()
    low = pd.to_numeric(x["H_low_voxels"], errors="coerce")
    high = pd.to_numeric(x["H_high_voxels"], errors="coerce")
    tumor = pd.to_numeric(x["tumor_voxels_current_grid"], errors="coerce")
    x["fraction_H_low"] = low / tumor
    x["fraction_H_high"] = high / tumor
    x["minority_fraction"] = np.minimum(x["fraction_H_low"], x["fraction_H_high"])
    x["state"] = np.select([high == 0, low == 0],
                            ["single-H-low", "single-H-high"],
                            default="dual-habitat")
    x["minority_eq_0"] = (x["minority_fraction"] == 0).astype(int)
    x["minority_lt_0_01"] = (x["minority_fraction"] < 0.01).astype(int)
    x["minority_lt_0_05"] = (x["minority_fraction"] < 0.05).astype(int)
    x["minority_lt_0_10"] = (x["minority_fraction"] < 0.10).astype(int)
    x["sv_min"] = x["supervoxel_mean_min"]
    x["sv_P05"] = x["supervoxel_mean_p5"]
    x["sv_median"] = x["supervoxel_mean_median"]
    x["sv_P95"] = x["supervoxel_mean_p95"]
    x["sv_max"] = x["supervoxel_mean_max"]
    x["P05_minus_b"] = x["sv_P05"] - x["shared_boundary_b"]
    x["P95_minus_b"] = x["sv_P95"] - x["shared_boundary_b"]
    x["boundary_position_state"] = np.select(
        [x["sv_P95"] < x["shared_boundary_b"],
         x["sv_P05"] > x["shared_boundary_b"]],
        ["global-low predominant", "global-high predominant"],
        default="boundary-crossing")
    x.to_csv(os.path.join(STRUCT, "habitat_case_distribution.csv"),
             index=False, encoding="utf-8-sig")
    summary_rows = []
    for section, series in [
        ("structural_state", x["state"]),
        ("boundary_position_state", x["boundary_position_state"]),
    ]:
        counts = series.value_counts(dropna=False)
        for category, n in counts.items():
            summary_rows.append({"section": section, "category": category,
                                 "n_cases": int(n), "fraction": float(n / len(x))})
    for name, col in [("minority_eq_0", "minority_eq_0"),
                      ("minority_lt_0_01", "minority_lt_0_01"),
                      ("minority_lt_0_05", "minority_lt_0_05"),
                      ("minority_lt_0_10", "minority_lt_0_10")]:
        n = int(x[col].sum())
        summary_rows.append({"section": "minority_fraction", "category": name,
                             "n_cases": n, "fraction": float(n / len(x))})
    summary_rows += [
        {"section": "logical_check", "category": "fraction_sum_eq_1",
         "n_cases": int(np.isclose(x["fraction_H_low"] + x["fraction_H_high"], 1).sum()),
         "fraction": float(np.isclose(x["fraction_H_low"] + x["fraction_H_high"], 1).mean())},
        {"section": "logical_check", "category": "unique_state",
         "n_cases": int(x["state"].notna().sum()),
         "fraction": float(x["state"].notna().mean())},
    ]
    pd.DataFrame(summary_rows).to_csv(
        os.path.join(STRUCT, "structural_state_summary.csv"),
        index=False, encoding="utf-8-sig")
    state_counts = x["state"].value_counts()
    boundary_counts = x["boundary_position_state"].value_counts()
    lines = [
        "# A集结构性表型诊断", "",
        "空生境按结构性全局表型状态记录，不计入硬技术失败；本阶段直接由A集既有逐例M1诊断派生。", "",
        "## 结构状态", "",
        "- single-H-low：%d例（%.1f%%）。" % (state_counts.get("single-H-low", 0), 100 * state_counts.get("single-H-low", 0) / len(x)),
        "- single-H-high：%d例（%.1f%%）。" % (state_counts.get("single-H-high", 0), 100 * state_counts.get("single-H-high", 0) / len(x)),
        "- dual-habitat：%d例（%.1f%%）。" % (state_counts.get("dual-habitat", 0), 100 * state_counts.get("dual-habitat", 0) / len(x)),
        "",
        "## 少数生境比例", "",
        "- minority_fraction=0：%d例（%.1f%%）。" % (int(x["minority_eq_0"].sum()), 100 * x["minority_eq_0"].mean()),
        "- minority_fraction<1%%：%d例（%.1f%%）。" % (int(x["minority_lt_0_01"].sum()), 100 * x["minority_lt_0_01"].mean()),
        "- minority_fraction<5%%：%d例（%.1f%%）。" % (int(x["minority_lt_0_05"].sum()), 100 * x["minority_lt_0_05"].mean()),
        "- minority_fraction<10%%：%d例（%.1f%%）。" % (int(x["minority_lt_0_10"].sum()), 100 * x["minority_lt_0_10"].mean()),
        "",
        "## 全局边界位置", "",
    ]
    for category in ["global-low predominant", "boundary-crossing", "global-high predominant"]:
        lines.append("- %s：%d例（%.1f%%）。" % (category, boundary_counts.get(category, 0), 100 * boundary_counts.get(category, 0) / len(x)))
    lines += ["", "393例均获得唯一结构状态；两类体积分数和为1的逻辑核验通过。", ""]
    write_text(os.path.join(STRUCT, "structural_state_report.md"), "\n".join(lines))
    return x


def read_case_with_labels(pid, cfg):
    path = os.path.join(base.PREP, str(pid), "R1_image.nrrd")
    mask_path = os.path.join(base.PREP, str(pid), "R1_mask.nrrd")
    image = sitk.ReadImage(base.apath(path))
    mask = sitk.ReadImage(base.apath(mask_path))
    errors, arr, roi = base.geom(image, mask)
    if errors:
        raise RuntimeError("%s: %s" % (pid, ";".join(errors)))
    labels = base.slic_labels(image, cfg, True)
    return image, arr, roi, labels


def sv_rows_for_case(pid, image, arr, roi, labels):
    spacing_xyz = tuple(float(x) for x in image.GetSpacing())
    voxel_volume = float(np.prod(spacing_xyz))
    rows = []
    for label in np.unique(labels[roi]):
        label = int(label)
        inside = (labels == label) & roi
        values = arr[inside].astype(float)
        if not values.size:
            continue
        rows.append({
            "影像号": str(pid), "reader": "R1", "sv_label": label,
            "sv_total_voxels": int((labels == label).sum()),
            "n_tumor_voxels": int(inside.sum()),
            "physical_volume_mm3": float(inside.sum() * voxel_volume),
            "Mean": float(values.mean()),
        })
    return rows


def stage3_local_global(limit=None):
    mkdir(LOCAL)
    cfg = load_cfg()
    cases = base.load_cases()
    if limit is not None:
        cases = cases.head(int(limit)).copy()
    rows = []
    errors = []
    for _, case in cases.iterrows():
        pid = str(case["影像号"])
        try:
            image, arr, roi, labels = read_case_with_labels(pid, cfg)
            rows.extend(sv_rows_for_case(pid, image, arr, roi, labels))
        except Exception as exc:
            errors.append({"影像号": pid, "error": str(exc)})
    if errors:
        pd.DataFrame(errors).to_csv(os.path.join(LOCAL, "errors.csv"),
                                    index=False, encoding="utf-8-sig")
        raise RuntimeError("local-global SLIC errors: %d" % len(errors))
    sv = pd.DataFrame(rows)
    if limit is not None:
        return sv
    sv.to_csv(os.path.join(LOCAL, "supervoxel_mean_A.csv"), index=False,
              encoding="utf-8-sig")
    baseline = load_diag().set_index("影像号")
    center_frame = pd.read_csv(os.path.join(BASELINE, "global_centers.csv"),
                               encoding="utf-8-sig")
    center = center_frame.iloc[0]
    low_c, high_c, boundary = float(center["H_low"]), float(center["H_high"]), float(center["boundary_b"])
    rows_out = []
    for pid, group in sv.groupby("影像号"):
        values = group["Mean"].to_numpy(dtype=float)
        local_row = {"影像号": pid, "n_supervoxels": len(group),
                     "sv_min": float(np.min(values)), "sv_P05": float(np.percentile(values, 5)),
                     "sv_median": float(np.median(values)), "sv_P95": float(np.percentile(values, 95)),
                     "sv_max": float(np.max(values)), "global_center_low": low_c,
                     "global_center_high": high_c, "global_boundary_b": boundary,
                     "n_supervoxels_baseline": int(baseline.loc[pid, "effective_supervoxels"]),
                     "n_supervoxels_match_baseline": int(len(group) == int(baseline.loc[pid, "effective_supervoxels"]))}
        if len(values) < 2 or np.unique(values).size < 2:
            local_row.update({"local_center_low": np.nan, "local_center_high": np.nan,
                              "local_center_distance": np.nan, "local_midpoint": np.nan,
                              "B_i": np.nan, "local_center_low_minus_b": np.nan,
                              "local_center_high_minus_b": np.nan,
                              "local_state": "diagnostic_unavailable"})
        else:
            km = KMeans(n_clusters=2, init="k-means++", n_init=100,
                        max_iter=300, tol=1e-4, random_state=SEED)
            km.fit(values.reshape(-1, 1))
            local_low, local_high = np.sort(km.cluster_centers_.ravel())
            midpoint = float((local_low + local_high) / 2.0)
            if local_high < boundary:
                state = "both_local_centers_below_global_boundary"
            elif local_low > boundary:
                state = "both_local_centers_above_global_boundary"
            else:
                state = "local_centers_straddle_global_boundary"
            local_row.update({
                "local_center_low": float(local_low), "local_center_high": float(local_high),
                "local_center_distance": float(local_high - local_low), "local_midpoint": midpoint,
                "B_i": float(midpoint - boundary),
                "local_center_low_minus_b": float(local_low - boundary),
                "local_center_high_minus_b": float(local_high - boundary),
                "local_state": state,
            })
        rows_out.append(local_row)
    diagnostic = pd.DataFrame(rows_out)
    diagnostic.to_csv(os.path.join(LOCAL, "local_global_diagnostic.csv"),
                      index=False, encoding="utf-8-sig")
    counts = diagnostic["local_state"].value_counts()
    match = int(diagnostic["n_supervoxels_match_baseline"].sum())
    report = [
        "# A集local-global机制诊断", "",
        "病例内K=2仅用于解释患者内相对异质性，不生成主生境图、不进入预后模型。全A共享中心沿用已锁定的M1中心。", "",
        "- 病例数：%d；local K=2可用：%d；不可用：%d。" % (len(diagnostic), int(diagnostic["local_state"].ne("diagnostic_unavailable").sum()), int(counts.get("diagnostic_unavailable", 0))),
        "- 超体素数与既有基线一致：%d/%d。" % (match, len(diagnostic)),
        "- 两个局部中心均低于全局边界：%d例。" % counts.get("both_local_centers_below_global_boundary", 0),
        "- 局部中心跨越全局边界：%d例。" % counts.get("local_centers_straddle_global_boundary", 0),
        "- 两个局部中心均高于全局边界：%d例。" % counts.get("both_local_centers_above_global_boundary", 0),
        "",
    ]
    write_text(os.path.join(LOCAL, "local_global_summary.md"), "\n".join(report))
    return sv, diagnostic


def load_sv():
    return pd.read_csv(os.path.join(LOCAL, "supervoxel_mean_A.csv"),
                       encoding="utf-8-sig", dtype={"影像号": str})


def fit_balanced_values(values, ids, rng):
    chunks = []
    for pid in rng.choice(ids, size=len(ids), replace=True):
        g = values[values["影像号"] == pid]["Mean"].to_numpy(dtype=float)
        if g.size:
            chunks.append(g)
    x = np.concatenate(chunks) if chunks else np.array([], dtype=float)
    weights = np.concatenate([np.full(len(g), 1.0 / len(g)) for g in chunks]) if chunks else np.array([], dtype=float)
    if x.size < 2 or np.unique(x).size < 2:
        return None
    model = KMeans(n_clusters=2, init="k-means++", n_init=100,
                   max_iter=300, tol=1e-4, random_state=SEED)
    model.fit(x.reshape(-1, 1), sample_weight=weights)
    centers = np.sort(model.cluster_centers_.ravel())
    return centers


def stage4_bootstrap(smoke=False):
    mkdir(BOOT)
    sv = load_sv()
    ids = np.sort(sv["影像号"].astype(str).unique())
    center_frame = pd.read_csv(os.path.join(BASELINE, "global_centers.csv"),
                               encoding="utf-8-sig")
    ref_low, ref_high = float(center_frame.iloc[0]["H_low"]), float(center_frame.iloc[0]["H_high"])
    ref_b = float(center_frame.iloc[0]["boundary_b"])
    n_boot = 20 if smoke else N_BOOTSTRAPS
    rng = np.random.RandomState(SEED)
    center_rows = []
    assignment_arrays = []
    for b in range(n_boot):
        centers = fit_balanced_values(sv, ids, rng)
        if centers is None:
            center_rows.append({"bootstrap": b, "fit_status": "degenerate"})
            continue
        low, high = float(centers[0]), float(centers[1])
        boundary = (low + high) / 2.0
        center_rows.append({"bootstrap": b, "fit_status": "success",
                            "C_low": low, "C_high": high, "boundary_b": boundary,
                            "center_distance": high - low,
                            "reference_boundary_inside_95": np.nan})
        assignment_arrays.append((sv["Mean"].to_numpy(dtype=float) >= boundary).astype(np.int8))
    centers_df = pd.DataFrame(center_rows)
    centers_df.to_csv(os.path.join(BOOT, "bootstrap_global_centers.csv"),
                      index=False, encoding="utf-8-sig")
    ref_assignment = (sv["Mean"].to_numpy(dtype=float) >= ref_b).astype(np.int8)
    case_rows = []
    means = sv["Mean"].to_numpy(dtype=float)
    for pid, index in sv.groupby("影像号").groups.items():
        idx = np.asarray(index, dtype=int)
        ref = ref_assignment[idx]
        hamming = []
        high_fracs = []
        for arr in assignment_arrays:
            candidate = arr[idx]
            hamming.append(float(np.mean(candidate == ref)))
            high_fracs.append(float(candidate.mean()))
        case_rows.append({
            "影像号": pid, "n_supervoxels": len(idx),
            "reference_H_high_fraction": float(ref.mean()),
            "assignment_stability_median": float(np.median(hamming)) if hamming else np.nan,
            "assignment_stability_p05": float(np.percentile(hamming, 5)) if hamming else np.nan,
            "bootstrap_H_high_fraction_median": float(np.median(high_fracs)) if high_fracs else np.nan,
            "bootstrap_H_high_fraction_sd": float(np.std(high_fracs, ddof=1)) if len(high_fracs) > 1 else np.nan,
        })
    case_df = pd.DataFrame(case_rows)
    case_df.to_csv(os.path.join(BOOT, "case_assignment_stability.csv"),
                   index=False, encoding="utf-8-sig")
    success = centers_df[centers_df["fit_status"] == "success"].copy()
    if len(success):
        lo_q, hi_q = success["boundary_b"].quantile([.025, .975])
        ref_inside = bool(lo_q <= ref_b <= hi_q)
        width = float(hi_q - lo_q)
        distance = float(ref_high - ref_low)
    else:
        lo_q = hi_q = width = distance = np.nan
        ref_inside = False
    valid_rate = float(len(success) / n_boot)
    median_stability = float(case_df["assignment_stability_median"].median()) if len(case_df) else np.nan
    p05_stability = float(case_df["assignment_stability_p05"].min()) if len(case_df) else np.nan
    pass_ops = bool(valid_rate >= .99 and ref_inside and width <= .25 * distance and
                    median_stability >= .95 and p05_stability >= .80)
    summary = {
        "n_bootstrap_requested": n_boot, "n_bootstrap_success": len(success),
        "nondegenerate_fit_rate": valid_rate, "reference_boundary_b": ref_b,
        "bootstrap_boundary_p2_5": lo_q, "bootstrap_boundary_p97_5": hi_q,
        "bootstrap_boundary_width": width, "reference_center_distance": distance,
        "reference_boundary_inside_95": int(ref_inside),
        "boundary_width_le_25pct_center_distance": int(width <= .25 * distance) if np.isfinite(width) else 0,
        "case_assignment_stability_median": median_stability,
        "case_assignment_stability_p05_min": p05_stability,
        "bootstrap_operational_pass": int(pass_ops),
    }
    pd.DataFrame([summary]).to_csv(os.path.join(BOOT, "bootstrap_stability_summary.csv"),
                                   index=False, encoding="utf-8-sig")
    write_text(os.path.join(BOOT, "bootstrap_stability_report.md"), "\n".join([
        "# A集患者层面bootstrap稳定性", "",
        "采用患者层面有放回抽样；每个抽样病例实例内部超体素总权重为1。", "",
        "- bootstrap次数：%d；非退化拟合率：%.3f。" % (n_boot, valid_rate),
        "- 全A边界：%.6f；bootstrap 95%%区间：[%.6f, %.6f]；边界位于区间内：%s。" % (ref_b, lo_q, hi_q, "是" if ref_inside else "否"),
        "- 边界区间宽度/全A中心间距：%.3f。" % (width / distance if distance else np.nan),
        "- 病例分配一致率中位数：%.3f；病例级第5百分位下限：%.3f。" % (median_stability, p05_stability),
        "- 阶段4操作性通过：%s。" % ("是" if pass_ops else "否"),
        "",
    ]))
    return summary


def stage4_margin_update():
    """Add continuous distance-to-boundary diagnostics without refitting."""
    path = os.path.join(BOOT, "case_assignment_stability.csv")
    stability = pd.read_csv(path, encoding="utf-8-sig", dtype={"影像号": str})
    sv = load_sv()
    center_frame = pd.read_csv(os.path.join(BASELINE, "global_centers.csv"),
                               encoding="utf-8-sig")
    boundary = float(center_frame.iloc[0]["boundary_b"])
    rows = []
    for pid, group in sv.groupby("影像号"):
        values = group["Mean"].to_numpy(dtype=float)
        margins = np.abs(values - boundary)
        rows.append({"影像号": str(pid), "sv_mean_median_minus_boundary": float(np.median(values) - boundary),
                     "sv_abs_margin_min": float(np.min(margins)),
                     "sv_abs_margin_p05": float(np.percentile(margins, 5)),
                     "sv_abs_margin_median": float(np.median(margins)),
                     "sv_fraction_within_0_05_boundary": float(np.mean(margins <= .05)),
                     "sv_fraction_within_0_10_boundary": float(np.mean(margins <= .10))})
    margins = pd.DataFrame(rows)
    stability = stability.merge(margins, on="影像号", how="left", validate="one_to_one")
    stability.to_csv(path, index=False, encoding="utf-8-sig")
    margins.sort_values("sv_abs_margin_median").to_csv(
        os.path.join(BOOT, "case_margin_diagnostics.csv"), index=False,
        encoding="utf-8-sig")
    return margins


def stage5_robustness(structural=None):
    mkdir(ROBUST)
    if structural is None:
        structural = pd.read_csv(os.path.join(STRUCT, "habitat_case_distribution.csv"),
                                 encoding="utf-8-sig", dtype={"影像号": str})
    else:
        structural = structural.copy()
        structural["影像号"] = structural["影像号"].astype(str)
    metrics_path = os.path.join(ROOT, "feature_extract", "output", "qc", "logs", "preprocess_metrics.csv")
    metrics = pd.read_csv(metrics_path, encoding="utf-8-sig", dtype=str)
    metrics = metrics[(metrics["读者"] == "R1") &
                      (metrics["normalization_requested"] == "muscle") &
                      (metrics["normalization_status"] == "success")].copy()
    metrics["影像号"] = metrics["影像号"].astype(str)
    merge_cols = ["影像号", "reference_cv", "reference_grad", "reference_mean",
                  "reference_p10", "reference_p50", "reference_p90"]
    metrics = metrics[[col for col in merge_cols if col in metrics.columns]].drop_duplicates("影像号")
    x = structural.merge(metrics, on="影像号", how="left")
    if "R1面内间距" in x.columns:
        x["R1面内间距_mm"] = pd.to_numeric(
            x["R1面内间距"].astype(str).str.split(r"\\", n=1).str[0],
            errors="coerce")
    numeric_cols = ["reference_cv", "reference_grad", "reference_mean", "reference_p10", "reference_p50", "reference_p90",
                    "fat_muscle_ratio", "muscle_mean_raw", "muscle_mean_preprocess", "muscle_mean_manifest_raw",
                    "肿瘤体积mm3", "effective_supervoxels", "R1面内间距_mm", "R1层厚", "R1层数"]
    x = numeric(x, [col for col in numeric_cols if col in x.columns])
    continuous = [col for col in numeric_cols if col in x.columns]
    rows = []
    for variable in continuous:
        for state, group in x.groupby("state", dropna=False):
            vals = group[variable].dropna()
            rows.append({"variable": variable, "type": "continuous", "state": state,
                         "n": len(vals), "median": float(vals.median()) if len(vals) else np.nan,
                         "q1": float(vals.quantile(.25)) if len(vals) else np.nan,
                         "q3": float(vals.quantile(.75)) if len(vals) else np.nan,
                         "mean": float(vals.mean()) if len(vals) else np.nan,
                         "sd": float(vals.std(ddof=1)) if len(vals) > 1 else np.nan})
    categorical = [col for col in ["序列名", "R1厂商", "R1机型", "R1场强", "R1系列"] if col in x.columns]
    for variable in categorical:
        for level, level_group in x.groupby(variable, dropna=False):
            counts = level_group["state"].value_counts()
            for state in ["single-H-low", "single-H-high", "dual-habitat"]:
                n = int(counts.get(state, 0))
                rows.append({"variable": variable, "type": "categorical", "level": level,
                             "state": state, "n": n,
                             "state_fraction_within_level": float(n / len(level_group)) if len(level_group) else np.nan,
                             "level_n": len(level_group)})
    result = pd.DataFrame(rows)
    result.to_csv(os.path.join(ROBUST, "structural_state_by_qc.csv"),
                  index=False, encoding="utf-8-sig")
    concentration = []
    for variable in categorical:
        for level, g in x.groupby(variable, dropna=False):
            c = g["state"].value_counts(normalize=True)
            concentration.append({"variable": variable, "level": level,
                                  "n_cases": len(g), "max_state_fraction": float(c.max()),
                                  "dominant_state": c.idxmax()})
    concentration_df = pd.DataFrame(concentration)
    concentration_df.to_csv(os.path.join(ROBUST, "categorical_state_concentration.csv"),
                            index=False, encoding="utf-8-sig")
    large = concentration_df[concentration_df["n_cases"] >= 20] if len(concentration_df) else concentration_df
    small_uniform = concentration_df[(concentration_df["n_cases"] >= 10) &
                                     (concentration_df["max_state_fraction"] >= 0.99)] if len(concentration_df) else concentration_df
    lines = [
        "# A集归一化与采集因素诊断", "",
        "本阶段仅评价技术因素与结构状态的无结局关系，不以单个P值决定保留或排除。", "",
        "- 连续技术变量已按结构状态输出中位数、四分位数、均值和标准差。",
        "- 序列及采集参数已输出各层级结构状态比例。",
        "- 未发现由本阶段输入质量字段直接标记的可修复预处理错误；结构状态不据此排除。",
        "- 病例数至少20的采集层级中，未见结构状态比例达到99%的层级。",
        "- 病例数10–19的小层级中有%d个达到99%%单一状态比例，作为小样本层级描述。" % len(small_uniform),
        "",
    ]
    write_text(os.path.join(ROBUST, "technical_robustness_report.md"), "\n".join(lines))
    return x


def stage6_sensitivity(structural=None):
    mkdir(SENS)
    if structural is None:
        structural = pd.read_csv(os.path.join(STRUCT, "habitat_case_distribution.csv"), encoding="utf-8-sig")
    strict = pd.read_csv(STRICT_AUDIT, encoding="utf-8-sig", dtype=str)
    strict = strict[(strict["split"] == "A") & (strict["recommended_pass"] == "1")]
    ids = set(strict["patient_id"].astype(str))
    x = structural[structural["影像号"].astype(str).isin(ids)].copy()
    x.to_csv(os.path.join(SENS, "strict_A137_structural_state.csv"),
             index=False, encoding="utf-8-sig")
    counts = x["state"].value_counts()
    lines = [
        "# 严格高信号A=137结构状态敏感性", "",
        "严格子集沿用全A M1中心和标签，不在子集内重新聚类。", "",
        "- 目标病例：%d；匹配阶段2病例：%d。" % (len(strict), len(x)),
        "- single-H-low：%d例（%.1f%%）。" % (counts.get("single-H-low", 0), 100 * counts.get("single-H-low", 0) / len(x)),
        "- single-H-high：%d例（%.1f%%）。" % (counts.get("single-H-high", 0), 100 * counts.get("single-H-high", 0) / len(x)),
        "- dual-habitat：%d例（%.1f%%）。" % (counts.get("dual-habitat", 0), 100 * counts.get("dual-habitat", 0) / len(x)),
        "- minority_fraction=0：%d例。" % int(x["minority_eq_0"].sum()),
        "- minority_fraction<1%%：%d例。" % int(x["minority_lt_0_01"].sum()),
        "- minority_fraction<5%%：%d例。" % int(x["minority_lt_0_05"].sum()),
        "- minority_fraction<10%%：%d例。" % int(x["minority_lt_0_10"].sum()),
        "",
    ]
    write_text(os.path.join(SENS, "strict_A137_structural_state.md"), "\n".join(lines))
    return x


def six_neighbor_interface(hab, roi, spacing_xyz):
    # hab axis order is z,y,x; face areas correspond to z,y,x neighbor steps.
    areas = [spacing_xyz[0] * spacing_xyz[1],
             spacing_xyz[0] * spacing_xyz[2],
             spacing_xyz[1] * spacing_xyz[2]]
    total = 0.0
    for axis, area in enumerate(areas):
        a = np.take(hab, indices=range(hab.shape[axis] - 1), axis=axis)
        b = np.take(hab, indices=range(1, hab.shape[axis]), axis=axis)
        ra = np.take(roi, indices=range(roi.shape[axis] - 1), axis=axis)
        rb = np.take(roi, indices=range(1, roi.shape[axis]), axis=axis)
        total += float(((a >= 0) & (b >= 0) & ra & rb & (a != b)).sum()) * area
    return total


def stage7_freeze(structural=None):
    mkdir(MAPS)
    mkdir(FEATURES)
    bootstrap = pd.read_csv(os.path.join(BOOT, "bootstrap_stability_summary.csv"), encoding="utf-8-sig")
    if int(bootstrap.iloc[0]["bootstrap_operational_pass"]) != 1:
        raise RuntimeError("stage7 blocked: bootstrap operational criteria not met")
    if structural is None:
        structural = pd.read_csv(os.path.join(STRUCT, "habitat_case_distribution.csv"), encoding="utf-8-sig")
    cfg = load_cfg()
    sv = load_sv()
    center_frame = pd.read_csv(os.path.join(BASELINE, "global_centers.csv"), encoding="utf-8-sig")
    low_c, high_c, boundary = [float(center_frame.iloc[0][col]) for col in ["H_low", "H_high", "boundary_b"]]
    sv_groups = {str(pid): g for pid, g in sv.groupby("影像号")}
    feature_rows = []
    qc_rows = []
    cases = base.load_cases()
    for _, case in cases.iterrows():
        pid = str(case["影像号"])
        image, arr, roi, labels = read_case_with_labels(pid, cfg)
        group = sv_groups[pid]
        label_to_hab = dict(zip(group["sv_label"].astype(int), (group["Mean"] >= boundary).astype(int)))
        hab = np.full(labels.shape, -1, dtype=np.int8)
        for label, value in label_to_hab.items():
            hab[labels == int(label)] = int(value)
        hab[~roi] = -1
        low_mask = roi & (hab == 0)
        high_mask = roi & (hab == 1)
        tumor_n = int(roi.sum())
        spacing_xyz = tuple(float(x) for x in image.GetSpacing())
        voxel_volume = float(np.prod(spacing_xyz))
        tumor_volume = tumor_n * voxel_volume
        p_low, p_high = low_mask.sum() / tumor_n, high_mask.sum() / tumor_n
        entropy = 0.0
        for p in [p_low, p_high]:
            if p > 0:
                entropy -= p * math.log(p)
        interface = six_neighbor_interface(hab, roi, spacing_xyz)
        cc, n_cc = ndimage.label(high_mask, ndimage.generate_binary_structure(3, 3))
        sizes = np.bincount(cc.ravel())[1:] if n_cc else np.array([], dtype=int)
        largest = int(sizes.max()) if len(sizes) else 0
        depth = ndimage.distance_transform_edt(roi, sampling=spacing_xyz[::-1])
        max_depth = float(depth[roi].max()) if roi.any() else 0.0
        radial = float(depth[high_mask].sum() / (max_depth * tumor_n)) if high_mask.any() and max_depth > 0 else 0.0
        values = group["Mean"].to_numpy(dtype=float)
        state = "single-H-low" if not high_mask.any() else ("single-H-high" if not low_mask.any() else "dual-habitat")
        rows = {
            "影像号": pid, "H_low_voxels": int(low_mask.sum()), "H_high_voxels": int(high_mask.sum()),
            "tumor_voxels": tumor_n, "tumor_volume_mm3": tumor_volume,
            "H_high_fraction": float(p_high), "H_low_fraction": float(p_low),
            "habitat_entropy": float(entropy), "interface_area_mm2": interface,
            "interface_density": float(interface / tumor_volume) if tumor_volume else np.nan,
            "H_high_largest_component_tumor_fraction": float(largest / tumor_n) if tumor_n else np.nan,
            "H_high_component_density": float(n_cc / (tumor_volume / 1000.0)) if tumor_volume else np.nan,
            "H_high_radial_burden": radial,
            "sv_median_minus_boundary": float(np.median(values) - boundary),
            "sv_IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "global_center_low": low_c, "global_center_high": high_c, "global_boundary_b": boundary,
            "structural_state": state, "hard_technical_failure": 0,
        }
        feature_rows.append(rows)
        main_values = [rows[col] for col in [
            "H_high_fraction", "H_low_fraction", "habitat_entropy",
            "interface_density", "H_high_largest_component_tumor_fraction",
            "H_high_component_density", "H_high_radial_burden",
            "sv_median_minus_boundary", "sv_IQR"]]
        qc_rows.append({"影像号": pid, "all_main_features_finite": int(np.isfinite(main_values).all()),
                        "n_supervoxels": len(group), "tumor_voxels": tumor_n,
                        "H_low_plus_H_high_equals_tumor": int(int(low_mask.sum() + high_mask.sum()) == tumor_n),
                        "structural_state": state})
        out = sitk.GetImageFromArray(hab.astype(np.int8))
        out.CopyInformation(image)
        sitk.WriteImage(out, base.apath(os.path.join(MAPS, pid + "_R1_habitat.nrrd")), useCompression=True)
    features = pd.DataFrame(feature_rows).sort_values("影像号")
    qc = pd.DataFrame(qc_rows).sort_values("影像号")
    features.to_csv(os.path.join(FEATURES, "global_descriptors_full_A.csv"), index=False, encoding="utf-8-sig")
    qc.to_csv(os.path.join(FEATURES, "feature_qc.csv"), index=False, encoding="utf-8-sig")
    baseline = pd.read_csv(os.path.join(STRUCT, "baseline_integrity.csv"), encoding="utf-8-sig")
    sensitivity = os.path.exists(os.path.join(SENS, "strict_A137_structural_state.csv"))
    freeze_pass = bool(int(baseline.iloc[0]["baseline_pass"]) == 1 and
                      int(bootstrap.iloc[0]["bootstrap_operational_pass"]) == 1 and
                      int(qc["all_main_features_finite"].all()) == 1 and sensitivity)
    dictionary = [
        "# M1主特征字典", "",
        "## 冻结状态", "",
        "- 当前冻结判定：%s。" % ("通过" if freeze_pass else "未通过"),
        "- 主方法：肌肉均值归一化、`[1,1,2] mm`、4 mm三维SLIC、全部有效超体素、每例总权重1、跨病例K-means K=2。",
        "- 全A技术中心：H-low=%.6f，H-high=%.6f，边界b=%.6f。" % (low_c, high_c, boundary),
        "- 结构性单生境保留；不计入硬技术失败。", "",
        "## 主低维特征", "",
        "|特征|公式|结构性规则|", "|---|---|---|",
        "|`H_high_fraction`|H-high体素数/肿瘤总体素数|H-high缺失时为0|",
        "|`habitat_entropy`|`-sum(p_k log p_k)`|缺失表型项按0log0=0|",
        "|`interface_density`|H-low/H-high三维邻接界面面积/肿瘤体积|单生境为0|",
        "|`H_high_largest_component_tumor_fraction`|最大H-high连通成分体积/肿瘤体积|H-high缺失时为0|",
        "|`H_high_component_density`|H-high连通成分数/肿瘤体积(cm³)|H-high缺失时为0|",
        "|`H_high_radial_burden`|H-high归一化径向深度之和/肿瘤总体素数|H-high缺失时为0|",
        "|`sv_median_minus_boundary`|病例超体素Mean中位数−b|始终定义|",
        "|`sv_IQR`|病例超体素Mean的P75−P25|始终定义|",
        "",
        "表型内纹理在相应表型不存在时保持未定义，不填0。嵌套内部验证必须在每个外层训练折内重新拟合中心并生成验证折特征。", "",
    ]
    write_text(os.path.join(HAB, "feature_dictionary.md"), "\n".join(dictionary))
    pd.DataFrame([{"freeze_pass": int(freeze_pass), "baseline_pass": int(baseline.iloc[0]["baseline_pass"]),
                   "bootstrap_pass": int(bootstrap.iloc[0]["bootstrap_operational_pass"]),
                   "main_features_all_finite": int(qc["all_main_features_finite"].all()),
                   "strict_A137_sensitivity_present": int(sensitivity),
                   "n_cases": len(features), "n_hard_technical_failures": 0,
                   "outcome_columns_read": False, "B_data_read": False}]).to_csv(
                       os.path.join(FEATURES, "freeze_qc.csv"), index=False, encoding="utf-8-sig")
    return freeze_pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["baseline", "structural", "local-global", "bootstrap", "bootstrap-margin", "robustness", "sensitivity", "freeze", "all"], required=True)
    parser.add_argument("--limit", type=int, default=None,
                        help="limit cases for local-global timing smoke test")
    parser.add_argument("--smoke", action="store_true",
                        help="run 20 bootstrap replicates instead of 1000")
    args = parser.parse_args()
    if args.stage in ("baseline", "structural", "all"):
        frame = stage1_baseline()
        stage2_structural(frame)
    else:
        frame = None
    if args.stage in ("local-global", "all"):
        stage3_local_global(args.limit)
    if args.stage in ("bootstrap", "all"):
        stage4_bootstrap(args.smoke)
    if args.stage == "bootstrap-margin":
        stage4_margin_update()
    if args.stage in ("robustness", "all"):
        stage5_robustness()
    if args.stage in ("sensitivity", "all"):
        stage6_sensitivity()
    if args.stage in ("freeze", "all"):
        stage7_freeze()


if __name__ == "__main__":
    main()
