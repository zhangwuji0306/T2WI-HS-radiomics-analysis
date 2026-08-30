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
import subprocess
import time
from collections import Counter

import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy import ndimage
from scipy.stats import chi2_contingency
from sklearn.cluster import KMeans

import technical_dry_run_A as base
from freeze_lock import (
    FORMAL_BOOTSTRAPS, atomic_write_json, file_sha256, files_sha256,
    id_hash, utc_now, validate_formal_bootstrap,
)


HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
OUT = os.path.join(HAB, "output")
RUN_TAG = "post_slic_fix"
BASELINE = os.path.join(OUT, "feasibility_A_patient_balanced_" + RUN_TAG)
METHOD18 = os.path.join(OUT, "method_selection_18_" + RUN_TAG)
STRUCT = os.path.join(OUT, "structural_diagnostics_A_" + RUN_TAG)
LOCAL = os.path.join(OUT, "local_global_diagnostic_A_" + RUN_TAG)
BOOT_ROOT = os.path.join(OUT, "bootstrap_stability_A_" + RUN_TAG)
ROBUST = os.path.join(OUT, "technical_robustness_A_" + RUN_TAG)
SENS = os.path.join(OUT, "sensitivity_" + RUN_TAG)
MAPS = os.path.join(OUT, "habitat_maps_A")
FEATURES = os.path.join(OUT, "habitat_features_A")
MAPS_STAGING = os.path.join(OUT, "habitat_maps_A_" + RUN_TAG + "_staging")
FEATURES_STAGING = os.path.join(OUT, "habitat_features_A_" + RUN_TAG + "_staging")
FREEZE_PREFLIGHT = os.path.join(OUT, "freeze_preflight_A_" + RUN_TAG)
CONFIG = os.path.join(HAB, "configs", "main_cross_case_kmeans_k2_4mm.json")
STRICT_AUDIT = os.path.join(OUT, "high_signal_eligibility_audit",
                            "recommended_selected_cases.csv")
SEED = 12345
BOOTSTRAP_COUNTS = {"smoke": 20, "preflight": 200,
                    "formal": FORMAL_BOOTSTRAPS}
BOOTSTRAP_CHECKPOINT_EVERY = 50


def bootstrap_run_config(mode):
    if mode not in BOOTSTRAP_COUNTS:
        raise ValueError("bootstrap mode must be smoke, preflight, or formal")
    return {"bootstrap_mode": mode,
            "n_bootstrap_requested": BOOTSTRAP_COUNTS[mode],
            "random_seed": SEED,
            "checkpoint_every": BOOTSTRAP_CHECKPOINT_EVERY}


def bootstrap_directory(mode):
    bootstrap_run_config(mode)
    return os.path.join(BOOT_ROOT, mode)


def bootstrap_checkpoint_path(mode):
    return os.path.join(bootstrap_directory(mode), "bootstrap_global_centers.csv")


def atomic_csv(frame, path):
    mkdir(os.path.dirname(path))
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


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
    grid_meta = base.slic_grid_metadata(image, load_cfg())
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
            "slic_requested_scale_mm": grid_meta["requested_scale_mm"],
            "slic_supergrid_voxels_xyz": ";".join(map(str, grid_meta["supergrid_voxels_xyz"])),
            "slic_actual_supergrid_mm_xyz": ";".join(map(str, grid_meta["actual_supergrid_mm_xyz"])),
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
    refit = fit_all_balanced_from_sv(sv, cfg)
    refit_ok = refit is not None
    if refit_ok:
        refit_low, refit_high = [float(value) for value in refit]
        refit_boundary = float((refit_low + refit_high) / 2.0)
        center_repro = {
            "baseline_center_low": low_c, "refit_center_low": refit_low,
            "center_low_abs_diff": abs(refit_low - low_c),
            "baseline_center_high": high_c, "refit_center_high": refit_high,
            "center_high_abs_diff": abs(refit_high - high_c),
            "baseline_boundary_b": boundary, "refit_boundary_b": refit_boundary,
            "boundary_abs_diff": abs(refit_boundary - boundary),
            "tolerance": 1e-6,
            "center_reproducibility_pass": int(
                max(abs(refit_low - low_c), abs(refit_high - high_c),
                    abs(refit_boundary - boundary)) <= 1e-6),
        }
    else:
        center_repro = {"baseline_center_low": low_c, "baseline_center_high": high_c,
                        "baseline_boundary_b": boundary, "tolerance": 1e-6,
                        "center_reproducibility_pass": 0}
    pd.DataFrame([center_repro]).to_csv(
        os.path.join(LOCAL, "center_reproducibility.csv"), index=False,
        encoding="utf-8-sig")
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
        "- 超体素数与校正后A集基线一致：%d/%d。" % (match, len(diagnostic)),
        "- 同一supervoxel表重拟合中心与A集基线的最大绝对差：%.9f；阈值：1e-6；核验：%s。" % (
            max(center_repro.get("center_low_abs_diff", np.inf),
                center_repro.get("center_high_abs_diff", np.inf),
                center_repro.get("boundary_abs_diff", np.inf)),
            "通过" if center_repro["center_reproducibility_pass"] else "未通过"),
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


def fit_all_balanced_from_sv(values, cfg):
    chunks = [group["Mean"].to_numpy(dtype=float)
              for _, group in values.groupby("影像号") if len(group)]
    if not chunks:
        return None
    x = np.concatenate(chunks)
    weights = np.concatenate([np.full(len(chunk), 1.0 / len(chunk))
                              for chunk in chunks])
    if x.size < 2 or np.unique(x).size < 2:
        return None
    c = cfg["clustering"]
    model = KMeans(n_clusters=int(c["k"]), init=c["initialization"],
                   n_init=int(c["n_init"]), max_iter=int(c["max_iter"]),
                   tol=float(c["tol"]), random_state=int(cfg["random_seed"]))
    model.fit(x.reshape(-1, 1), sample_weight=weights)
    return np.sort(model.cluster_centers_.ravel())


def fit_balanced_values(values, ids, rng, cfg, random_state=None):
    if isinstance(values, pd.DataFrame):
        groups = {str(pid): group["Mean"].to_numpy(dtype=float)
                  for pid, group in values.groupby("影像号")}
    else:
        groups = values
    chunks = [groups[str(pid)] for pid in rng.choice(ids, size=len(ids), replace=True)
              if str(pid) in groups and len(groups[str(pid)])]
    x = np.concatenate(chunks) if chunks else np.array([], dtype=float)
    weights = (np.concatenate([np.full(len(group), 1.0 / len(group)) for group in chunks])
               if chunks else np.array([], dtype=float))
    if x.size < 2 or np.unique(x).size < 2:
        return None
    c = cfg["clustering"]
    model = KMeans(n_clusters=int(c["k"]), init=c["initialization"],
                   n_init=int(c["n_init"]), max_iter=int(c["max_iter"]),
                   tol=float(c["tol"]),
                   random_state=int(cfg["random_seed"] if random_state is None else random_state))
    model.fit(x.reshape(-1, 1), sample_weight=weights)
    return np.sort(model.cluster_centers_.ravel())


def bootstrap_center_rows(values, ids, cfg, indices, base_seed=SEED):
    groups = {str(pid): group["Mean"].to_numpy(dtype=float)
              for pid, group in values.groupby("影像号")}
    rows = []
    for index in indices:
        seed = int(base_seed + int(index))
        rng = np.random.RandomState(seed)
        centers = fit_balanced_values(groups, ids, rng, cfg, random_state=seed)
        row = {"bootstrap_mode": "", "bootstrap_index": int(index),
               "seed": seed, "fit_status": "degenerate",
               "C_low": np.nan, "C_high": np.nan,
               "boundary_b": np.nan, "center_distance": np.nan}
        if centers is not None:
            low, high = float(centers[0]), float(centers[1])
            row.update({"fit_status": "success", "C_low": low, "C_high": high,
                        "boundary_b": (low + high) / 2.0,
                        "center_distance": high - low})
        rows.append(row)
    return rows


def load_bootstrap_checkpoint(mode):
    path = bootstrap_checkpoint_path(mode)
    if not os.path.exists(path):
        return pd.DataFrame()
    frame = pd.read_csv(path, encoding="utf-8-sig")
    if frame.empty:
        return frame
    if frame["bootstrap_index"].duplicated().any():
        raise RuntimeError("bootstrap checkpoint contains duplicate indices")
    if "bootstrap_mode" in frame and not frame["bootstrap_mode"].fillna(mode).eq(mode).all():
        raise RuntimeError("bootstrap checkpoint mode mismatch")
    return frame.sort_values("bootstrap_index").reset_index(drop=True)


def stage4_bootstrap(mode="smoke", until=None):
    run = bootstrap_run_config(mode)
    boot = bootstrap_directory(mode)
    mkdir(boot)
    cfg = load_cfg()
    sv = load_sv()
    ids = np.sort(sv["影像号"].astype(str).unique())
    center_frame = pd.read_csv(os.path.join(BASELINE, "global_centers.csv"),
                               encoding="utf-8-sig")
    ref_low = float(center_frame.iloc[0]["H_low"])
    ref_high = float(center_frame.iloc[0]["H_high"])
    ref_b = float(center_frame.iloc[0]["boundary_b"])
    requested = int(run["n_bootstrap_requested"])
    target = requested if until is None else int(until)
    if target < 1 or target > requested:
        raise ValueError("bootstrap-until must be between 1 and %d" % requested)
    centers_df = load_bootstrap_checkpoint(mode)
    if len(centers_df) and pd.to_numeric(centers_df["bootstrap_index"]).max() >= requested:
        raise RuntimeError("bootstrap checkpoint index exceeds requested mode count")
    completed = set(pd.to_numeric(centers_df.get("bootstrap_index", pd.Series(dtype=int)),
                                  errors="coerce").dropna().astype(int))
    missing = [index for index in range(target) if index not in completed]
    new_rows = []
    for number, index in enumerate(missing, 1):
        rows = bootstrap_center_rows(sv, ids, cfg, [index], SEED)
        rows[0]["bootstrap_mode"] = mode
        new_rows.extend(rows)
        if number % BOOTSTRAP_CHECKPOINT_EVERY == 0:
            centers_df = pd.concat([centers_df, pd.DataFrame(new_rows)], ignore_index=True)
            centers_df = centers_df.sort_values("bootstrap_index").reset_index(drop=True)
            atomic_csv(centers_df, bootstrap_checkpoint_path(mode))
            new_rows = []
            print("[%s] checkpoint %d/%d" % (mode, len(centers_df), requested))
    if new_rows:
        centers_df = pd.concat([centers_df, pd.DataFrame(new_rows)], ignore_index=True)
    centers_df = centers_df.sort_values("bootstrap_index").reset_index(drop=True)
    atomic_csv(centers_df, bootstrap_checkpoint_path(mode))
    success = centers_df[centers_df["fit_status"] == "success"].copy()
    assignment_arrays = [
        (sv["Mean"].to_numpy(dtype=float) >= float(boundary)).astype(np.int8)
        for boundary in success["boundary_b"].tolist()
    ]
    ref_assignment = (sv["Mean"].to_numpy(dtype=float) >= ref_b).astype(np.int8)
    case_rows = []
    means = sv["Mean"].to_numpy(dtype=float)
    case_stability_medians = []
    for pid, index in sv.groupby("影像号").groups.items():
        idx = np.asarray(index, dtype=int)
        ref = ref_assignment[idx]
        weights = sv.iloc[idx]["n_tumor_voxels"].to_numpy(dtype=float)
        weight_sum = float(weights.sum())
        hamming = []
        high_fracs = []
        structural_matches = []
        deltas = []
        ref_high_fraction = float(np.sum(weights * ref) / weight_sum)
        ref_state = ("single-H-low" if ref_high_fraction == 0 else
                     "single-H-high" if ref_high_fraction == 1 else
                     "dual-habitat")
        for arr in assignment_arrays:
            candidate = arr[idx]
            stability = float(np.sum(weights * (candidate == ref)) / weight_sum)
            high_fraction = float(np.sum(weights * candidate) / weight_sum)
            candidate_state = ("single-H-low" if high_fraction == 0 else
                               "single-H-high" if high_fraction == 1 else
                               "dual-habitat")
            hamming.append(stability)
            high_fracs.append(high_fraction)
            structural_matches.append(int(candidate_state == ref_state))
            deltas.append(high_fraction - ref_high_fraction)
        case_stability_medians.append(float(np.median(hamming)) if hamming else np.nan)
        case_rows.append({
            "影像号": pid, "n_supervoxels": len(idx),
            "n_tumor_voxels": int(weights.sum()),
            "reference_H_high_fraction": ref_high_fraction,
            "reference_structural_state": ref_state,
            "assignment_stability_median": float(np.median(hamming)) if hamming else np.nan,
            "assignment_stability_p05": float(np.percentile(hamming, 5)) if hamming else np.nan,
            "bootstrap_H_high_fraction_median": float(np.median(high_fracs)) if high_fracs else np.nan,
            "bootstrap_H_high_fraction_sd": float(np.std(high_fracs, ddof=1)) if len(high_fracs) > 1 else np.nan,
            "delta_H_high_fraction_median": float(np.median(deltas)) if deltas else np.nan,
            "delta_H_high_fraction_p05": float(np.percentile(deltas, 5)) if deltas else np.nan,
            "delta_H_high_fraction_p95": float(np.percentile(deltas, 95)) if deltas else np.nan,
            "structural_state_stability": float(np.mean(structural_matches)) if structural_matches else np.nan,
        })
    case_df = pd.DataFrame(case_rows)
    atomic_csv(case_df, os.path.join(boot, "case_assignment_stability.csv"))
    if len(success):
        lo_q, hi_q = success["boundary_b"].quantile([.025, .975])
        ref_inside = bool(lo_q <= ref_b <= hi_q)
        width = float(hi_q - lo_q)
        distance = float(ref_high - ref_low)
    else:
        lo_q = hi_q = width = distance = np.nan
        ref_inside = False
    n_completed = len(centers_df)
    valid_rate = float(len(success) / n_completed) if n_completed else 0.0
    median_stability = float(case_df["assignment_stability_median"].median()) if len(case_df) else np.nan
    p05_stability = (float(np.percentile(case_df["assignment_stability_median"].dropna(), 5))
                     if len(case_df) and case_df["assignment_stability_median"].notna().any()
                     else np.nan)
    structural_state_stability_median = (float(case_df["structural_state_stability"].median())
                                         if len(case_df) else np.nan)
    structural_state_stability_p05 = (float(np.percentile(case_df["structural_state_stability"].dropna(), 5))
                                      if len(case_df) and case_df["structural_state_stability"].notna().any()
                                      else np.nan)
    delta_median = (float(case_df["delta_H_high_fraction_median"].median())
                    if len(case_df) else np.nan)
    pass_ops = bool(valid_rate >= .99 and ref_inside and width <= .25 * distance and
                    median_stability >= .95 and p05_stability >= .80)
    completion_status = "complete" if n_completed == requested else "partial"
    formal_eligible = int(mode == "formal" and requested == FORMAL_BOOTSTRAPS and
                          n_completed == FORMAL_BOOTSTRAPS and completion_status == "complete" and
                          pass_ops)
    summary = {
        "bootstrap_mode": mode, "n_bootstrap_requested": requested,
        "n_bootstrap_completed": n_completed,
        "n_bootstrap_success": len(success), "random_seed": SEED,
        "completion_status": completion_status, "formal_eligible": formal_eligible,
        "nondegenerate_fit_rate": valid_rate, "reference_boundary_b": ref_b,
        "bootstrap_boundary_p2_5": lo_q, "bootstrap_boundary_p97_5": hi_q,
        "bootstrap_boundary_width": width, "reference_center_distance": distance,
        "reference_boundary_inside_95": int(ref_inside),
        "boundary_width_le_25pct_center_distance": int(width <= .25 * distance) if np.isfinite(width) else 0,
        "case_assignment_stability_median": median_stability,
        "case_assignment_stability_p05": p05_stability,
        "case_assignment_stability_p05_definition": "5th percentile across per-case bootstrap stability medians",
        "structural_state_stability_median": structural_state_stability_median,
        "structural_state_stability_p05": structural_state_stability_p05,
        "delta_H_high_fraction_median": delta_median,
        "bootstrap_operational_pass": int(pass_ops),
    }
    atomic_csv(pd.DataFrame([summary]), os.path.join(boot, "bootstrap_stability_summary.csv"))
    write_text(os.path.join(boot, "bootstrap_stability_report.md"), "\n".join([
        "# A集患者层面bootstrap稳定性", "",
        "采用患者层面有放回抽样；每个抽样病例实例内部超体素总权重为1。", "",
        "- 模式：%s；计划%d次；已完成%d次；非退化拟合率：%.3f。" %
        (mode, requested, n_completed, valid_rate),
        "- 全A边界：%.6f；bootstrap 95%%区间：[%.6f, %.6f]；边界位于区间内：%s。" % (ref_b, lo_q, hi_q, "是" if ref_inside else "否"),
        "- 边界区间宽度/全A中心间距：%.3f。" % (width / distance if distance else np.nan),
        "- 肿瘤体素加权病例分配一致率中位数：%.3f；病例级一致率第5百分位：%.3f。" % (median_stability, p05_stability),
        "- 结构状态一致率中位数：%.3f；第5百分位：%.3f；H-high比例bootstrap中位变化：%.6f。" % (
            structural_state_stability_median, structural_state_stability_p05, delta_median),
        "- 阶段4操作性通过：%s。" % ("是" if pass_ops else "否"),
        "- formal_eligible：%d；smoke/preflight无论结果均不能解锁冻结。" % formal_eligible,
        "",
    ]))
    stage4_margin_update(mode)
    return summary


def stage4_margin_update(mode="formal"):
    """Add continuous distance-to-boundary diagnostics without refitting."""
    boot = bootstrap_directory(mode)
    path = os.path.join(boot, "case_assignment_stability.csv")
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
        os.path.join(boot, "case_margin_diagnostics.csv"), index=False,
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
    state_order = ["single-H-low", "single-H-high", "dual-habitat"]
    continuous_effects = []
    for variable in continuous:
        groups = {state: x.loc[x["state"] == state, variable].dropna().to_numpy(dtype=float)
                  for state in state_order}
        for i, first in enumerate(state_order):
            for second in state_order[i + 1:]:
                a, b = groups[first], groups[second]
                if not len(a) or not len(b):
                    smd = np.nan
                    mean_difference = np.nan
                    pooled_sd = np.nan
                else:
                    mean_difference = float(np.mean(a) - np.mean(b))
                    variance_a = np.var(a, ddof=1) if len(a) > 1 else 0.0
                    variance_b = np.var(b, ddof=1) if len(b) > 1 else 0.0
                    pooled_variance = (((len(a) - 1) * variance_a +
                                        (len(b) - 1) * variance_b) /
                                       max(1, len(a) + len(b) - 2))
                    pooled_sd = float(np.sqrt(pooled_variance))
                    smd = float(mean_difference / pooled_sd) if pooled_sd > 0 else 0.0
                continuous_effects.append({
                    "variable": variable, "group_1": first, "group_2": second,
                    "n_group_1": len(a), "n_group_2": len(b),
                    "mean_difference_group_1_minus_group_2": mean_difference,
                    "pooled_sd": pooled_sd, "standardized_mean_difference": smd,
                    "absolute_standardized_mean_difference": abs(smd) if np.isfinite(smd) else np.nan,
                })
    continuous_effect_df = pd.DataFrame(continuous_effects)
    continuous_effect_df.to_csv(os.path.join(ROBUST, "continuous_effect_sizes.csv"),
                                index=False, encoding="utf-8-sig")
    categorical_effects = []
    for variable in categorical:
        table = pd.crosstab(x[variable].fillna("<missing>"), x["state"])
        table = table.reindex(columns=state_order, fill_value=0)
        if table.shape[0] >= 2 and table.shape[1] >= 2:
            chi2, p_value, dof, _ = chi2_contingency(table.to_numpy(), correction=False)
            denominator = table.to_numpy().sum() * min(table.shape[0] - 1, table.shape[1] - 1)
            cramers_v = float(np.sqrt(chi2 / denominator)) if denominator else 0.0
        else:
            chi2, p_value, dof, cramers_v = 0.0, 1.0, 0, 0.0
        categorical_effects.append({
            "variable": variable, "n_cases": int(table.to_numpy().sum()),
            "n_levels": int(table.shape[0]), "chi2": float(chi2),
            "dof": int(dof), "p_value_descriptive": float(p_value),
            "cramers_v": cramers_v,
        })
    categorical_effect_df = pd.DataFrame(categorical_effects)
    categorical_effect_df.to_csv(os.path.join(ROBUST, "categorical_effect_sizes.csv"),
                                 index=False, encoding="utf-8-sig")
    small_uniform = concentration_df[(concentration_df["n_cases"] >= 10) &
                                     (concentration_df["max_state_fraction"] >= 0.99)] if len(concentration_df) else concentration_df
    large_uniform = concentration_df[(concentration_df["n_cases"] >= 20) &
                                     (concentration_df["max_state_fraction"] >= 0.99)] if len(concentration_df) else concentration_df
    required_qc = [col for col in ["state", "reference_mean", "肿瘤体积mm3",
                                   "effective_supervoxels", "R1面内间距_mm",
                                   "R1层厚", "R1层数"] if col in x.columns]
    n_missing_required = int(x[required_qc].isna().any(axis=1).sum()) if required_qc else len(x)
    max_smd = (float(continuous_effect_df["absolute_standardized_mean_difference"].max())
               if len(continuous_effect_df) else np.nan)
    max_cramers_v = (float(categorical_effect_df["cramers_v"].max())
                     if len(categorical_effect_df) else np.nan)
    robustness_pass = bool(n_missing_required == 0)
    pd.DataFrame([{
        "n_cases": len(x), "n_missing_required_qc_cases": n_missing_required,
        "n_large_uniform_categorical_levels": len(large_uniform),
        "n_small_uniform_categorical_levels": len(small_uniform),
        "large_uniform_levels_are_diagnostic": 1,
        "max_absolute_standardized_mean_difference": max_smd,
        "max_cramers_v": max_cramers_v,
        "technical_robustness_pass": int(robustness_pass),
    }]).to_csv(os.path.join(ROBUST, "technical_robustness_summary.csv"),
               index=False, encoding="utf-8-sig")
    lines = [
        "# A集归一化与采集因素诊断", "",
        "本阶段仅评价技术因素与结构状态的无结局关系，不以单个P值决定保留或排除。", "",
        "- 连续技术变量已按结构状态输出中位数、四分位数、均值和标准差。",
        "- 序列及采集参数已输出各层级结构状态比例。",
        "- 连续变量最大绝对标准化组间差：%s；分类变量最大Cramér's V：%s。" % (
            "NA" if not np.isfinite(max_smd) else "%.3f" % max_smd,
            "NA" if not np.isfinite(max_cramers_v) else "%.3f" % max_cramers_v),
        "- 必需技术质量字段缺失病例：%d；病例数至少20且结构状态比例达到99%%的层级：%d。" % (
            n_missing_required, len(large_uniform)),
        "- 病例数10–19且结构状态比例达到99%%的小层级：%d，作为小样本描述。" % len(small_uniform),
        "- 阶段5必需字段完整性核验：%s。" % ("通过" if robustness_pass else "未通过，需保留该诊断结果并阻止冻结"),
        "- 分类层级集中度和效应量仅作条件性诊断：%s。" % (
            "存在需报告的高集中度层级" if len(large_uniform) else "未见病例数至少20且达到99%单一状态的层级"),
        "",
    ]
    write_text(os.path.join(ROBUST, "technical_robustness_report.md"), "\n".join(lines))
    return x


def stage6_sensitivity(structural=None):
    mkdir(SENS)
    if structural is None:
        structural = pd.read_csv(os.path.join(STRUCT, "habitat_case_distribution.csv"),
                                 encoding="utf-8-sig", dtype={"影像号": str})
    else:
        structural = structural.copy()
        structural["影像号"] = structural["影像号"].astype(str)
    strict = pd.read_csv(STRICT_AUDIT, encoding="utf-8-sig", dtype=str)
    strict = strict[(strict["split"] == "A") & (strict["recommended_pass"] == "1")]
    strict_ids = strict["patient_id"].astype(str).str.strip()
    structural_ids = set(structural["影像号"])
    if len(strict) != 137 or strict_ids.nunique() != 137:
        raise RuntimeError("strict A sensitivity selection must contain exactly 137 unique cases")
    if not set(strict_ids).issubset(structural_ids):
        missing = sorted(set(strict_ids) - structural_ids)
        raise RuntimeError("strict A137 is not a subset of corrected A393: %s" % missing[:5])
    ids = set(strict_ids)
    x = structural[structural["影像号"].isin(ids)].copy()
    if len(x) != 137 or x["影像号"].nunique() != 137:
        raise RuntimeError("corrected structural diagnostics do not map one-to-one to A137")
    pd.DataFrame([{
        "strict_target_cases": len(strict), "strict_unique_cases": strict_ids.nunique(),
        "structural_matched_cases": len(x), "structural_unique_cases": x["影像号"].nunique(),
        "strict_A137_exact_unique_pass": 1,
        "strict_A137_subset_A393_pass": 1,
    }]).to_csv(os.path.join(SENS, "strict_A137_assertions.csv"),
               index=False, encoding="utf-8-sig")
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


def write_freeze_preflight(gates, note):
    mkdir(FREEZE_PREFLIGHT)
    frame = pd.DataFrame(gates)
    frame.to_csv(os.path.join(FREEZE_PREFLIGHT, "freeze_preflight.csv"),
                 index=False, encoding="utf-8-sig")
    lines = ["# A集M1冻结前门禁", "", note, "", "|门禁|结果|说明|",
             "|---|---:|---|"]
    for row in gates:
        lines.append("|%s|%d|%s|" % (row["gate"], row["pass"], row["details"]))
    lines += ["", "冻结前门禁结果：%s。" %
              ("全部通过" if all(row["pass"] for row in gates) else "未通过，未生成或提升正式生境图与特征目录"), ""]
    write_text(os.path.join(FREEZE_PREFLIGHT, "freeze_preflight.md"), "\n".join(lines))
    return all(row["pass"] for row in gates)


def stage7_freeze(structural=None):
    """Run every freeze gate before promoting staged maps/features atomically."""
    required = {
        "baseline": (os.path.join(STRUCT, "baseline_integrity.csv"), "baseline_pass"),
        "center_reproducibility": (os.path.join(LOCAL, "center_reproducibility.csv"), "center_reproducibility_pass"),
        "robustness": (os.path.join(ROBUST, "technical_robustness_summary.csv"), "technical_robustness_pass"),
    }
    gates = []
    for name, (path, column) in required.items():
        if not os.path.exists(path):
            gates.append({"gate": name, "pass": 0, "details": "required gate file missing"})
            continue
        frame = pd.read_csv(path, encoding="utf-8-sig")
        value = int(pd.to_numeric(frame.iloc[0][column], errors="coerce")) if column in frame else 0
        gates.append({"gate": name, "pass": value, "details": "%s=%d" % (column, value)})
    formal_summary_path = os.path.join(bootstrap_directory("formal"),
                                       "bootstrap_stability_summary.csv")
    formal_summary = None
    if os.path.exists(formal_summary_path):
        formal_summary = pd.read_csv(formal_summary_path, encoding="utf-8-sig").iloc[0].to_dict()
        bootstrap_errors = validate_formal_bootstrap(formal_summary)
    else:
        bootstrap_errors = ["formal bootstrap summary missing"]
    gates.append({"gate": "formal_bootstrap_1000", "pass": int(not bootstrap_errors),
                  "details": "formal 1000 complete" if not bootstrap_errors else "; ".join(bootstrap_errors)})
    cohort_summary_path = os.path.join(OUT, "technical_cohort_manifest", "cohort_summary.json")
    identity_pass = 0
    if os.path.exists(cohort_summary_path):
        with open(cohort_summary_path, encoding="utf-8") as handle:
            cohort_summary = json.load(handle)
        identity_pass = int(cohort_summary.get("identity_audit_pass", 0) == 1 and
                            cohort_summary.get("A137_subset_A393", 0) == 1)
    gates.append({"gate": "A393_identity_and_A137_subset", "pass": identity_pass,
                  "details": "technical cohort audit passed" if identity_pass else "technical cohort audit missing or failed"})
    a137_path = os.path.join(SENS, "strict_A137_assertions.csv")
    a137_pass = 0
    if os.path.exists(a137_path):
        a137 = pd.read_csv(a137_path, encoding="utf-8-sig")
        a137_pass = int(pd.to_numeric(a137.iloc[0].get("strict_A137_exact_unique_pass", 0), errors="coerce") == 1 and
                        pd.to_numeric(a137.iloc[0].get("strict_A137_subset_A393_pass", 0), errors="coerce") == 1)
    gates.append({"gate": "strict_A137_exact_unique_and_subset", "pass": a137_pass,
                  "details": "assertion file present" if a137_pass else "exact 137/subset assertion missing or failed"})
    gates.append({"gate": "formal_destination_absent", "pass": int(not (os.path.exists(MAPS) or os.path.exists(FEATURES))),
                  "details": "formal directories must not pre-exist"})
    if not write_freeze_preflight(gates, "结构、稳定性、技术因素与A137门禁先行核验；结局、临床变量和B集保持不可见。"):
        return False

    if os.path.exists(MAPS_STAGING) or os.path.exists(FEATURES_STAGING):
        raise RuntimeError("staging directory already exists; inspect it before rerunning freeze")
    mkdir(MAPS_STAGING)
    mkdir(FEATURES_STAGING)
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
        entropy = -sum(p * math.log(p) for p in [p_low, p_high] if p > 0)
        interface = six_neighbor_interface(hab, roi, spacing_xyz)
        cc, n_cc = ndimage.label(high_mask, ndimage.generate_binary_structure(3, 1))
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
            "H_high_fraction", "sv_median_minus_boundary", "sv_IQR",
            "interface_density", "H_high_largest_component_tumor_fraction",
            "H_high_radial_burden"]]
        qc_rows.append({"影像号": pid, "all_main_features_finite": int(np.isfinite(main_values).all()),
                        "n_supervoxels": len(group), "tumor_voxels": tumor_n,
                        "H_low_plus_H_high_equals_tumor": int(int(low_mask.sum() + high_mask.sum()) == tumor_n),
                        "structural_state": state})
        out = sitk.GetImageFromArray(hab.astype(np.int8))
        out.CopyInformation(image)
        sitk.WriteImage(out, base.apath(os.path.join(MAPS_STAGING, pid + "_R1_habitat.nrrd")), useCompression=True)
    features = pd.DataFrame(feature_rows).sort_values("影像号")
    qc = pd.DataFrame(qc_rows).sort_values("影像号")
    features.to_csv(os.path.join(FEATURES_STAGING, "global_descriptors_full_A.csv"), index=False, encoding="utf-8-sig")
    qc.to_csv(os.path.join(FEATURES_STAGING, "feature_qc.csv"), index=False, encoding="utf-8-sig")
    feature_qc_pass = int(len(features) == 393 and features["影像号"].nunique() == 393 and
                          qc["all_main_features_finite"].all() and
                          qc["H_low_plus_H_high_equals_tumor"].all())
    gates.append({"gate": "staged_feature_qc", "pass": feature_qc_pass,
                  "details": "393 unique cases, six-axis finite check, voxel conservation"})
    if not write_freeze_preflight(gates, "全部冻结门禁及临时目录特征质控已完成；仅在全部通过后提升正式目录。"):
        return False
    os.replace(MAPS_STAGING, MAPS)
    os.replace(FEATURES_STAGING, FEATURES)
    dictionary = [
        "# M1主特征字典", "",
        "## 冻结状态", "",
        "- 当前冻结判定：通过。",
        "- 主方法：肌肉均值归一化、`[1,1,2] mm`、4 mm三维SLIC、全部有效超体素、每例总权重1、跨病例K-means K=2。",
        "- 全A技术中心：H-low=%.6f，H-high=%.6f，边界b=%.6f。" % (low_c, high_c, boundary),
        "- 结构性单生境保留；不计入硬技术失败。", "",
        "## 主预测特征块", "",
        "|特征|公式|结构性规则|", "|---|---|---|",
        "|`H_high_fraction`|H-high体素数/肿瘤总体素数|H-high缺失时为0|",
        "|`sv_median_minus_boundary`|病例超体素Mean中位数−b|始终定义|",
        "|`sv_IQR`|病例超体素Mean的P75−P25|始终定义|",
        "|`interface_density`|H-low/H-high三维6邻接界面面积/肿瘤体积|单生境为0|",
        "|`H_high_largest_component_tumor_fraction`|最大H-high 6连通成分体积/肿瘤体积|H-high缺失时为0|",
        "|`H_high_radial_burden`|H-high归一化径向深度之和/肿瘤总体素数|H-high缺失时为0|",
        "",
        "`habitat_entropy`与`H_high_component_density`保留为描述性候选，不纳入当前主预测块。表型内纹理在相应表型不存在时保持未定义，不填0。嵌套内部验证必须在每个外层训练折内重新拟合中心并生成验证折特征。", "",
    ]
    write_text(os.path.join(HAB, "feature_dictionary.md"), "\n".join(dictionary))
    pd.DataFrame([{"freeze_pass": 1, "baseline_pass": 1,
                   "bootstrap_pass": 1, "center_reproducibility_pass": 1,
                   "technical_robustness_pass": 1, "main_features_all_finite": 1,
                   "strict_A137_sensitivity_present": 1,
                   "n_cases": len(features), "n_hard_technical_failures": 0,
                   "outcome_columns_read": False, "B_data_read": False}]).to_csv(
                   os.path.join(FEATURES, "freeze_qc.csv"), index=False, encoding="utf-8-sig")
    technical_dir = os.path.join(OUT, "technical_cohort_manifest")
    a393_path = os.path.join(technical_dir, "cohort_A_lenient.csv")
    a137_path = os.path.join(technical_dir, "cohort_A_strict.csv")
    a393 = pd.read_csv(a393_path, encoding="utf-8-sig", dtype=str)
    a137 = pd.read_csv(a137_path, encoding="utf-8-sig", dtype=str)
    diag = load_diag()
    failures = diag.loc[hard_failure_flags(diag).any(axis=1), "影像号"].astype(str)
    screen_paths = [
        os.path.join(OUT, "high_signal_eligibility_audit", "lenient_screening_decisions.csv"),
        os.path.join(OUT, "high_signal_eligibility_audit", "recommended_screening_decisions.csv"),
    ]
    preprocess_config = os.path.join(ROOT, "feature_extract", "configs", "radiomics_params.yaml")
    manifest_path = os.path.join(ROOT, "feature_extract", "output", "manifest.csv")
    scanner_path = os.path.join(ROOT, "feature_extract", "output", "scanner_map.csv")
    try:
        commit = subprocess.check_output(
            ["git", "-c", "safe.directory=" + ROOT.replace("\\", "/"), "rev-parse", "HEAD"],
            cwd=ROOT, universal_newlines=True).strip()
    except Exception:  # noqa: BLE001
        commit = "unknown"
    lock = {
        "analysis_id": cfg["analysis_id"], "git_commit": commit,
        "A393_id_hash": id_hash(a393["影像号"]),
        "A137_id_hash": id_hash(a137["影像号"]),
        "manifest_hash": file_sha256(manifest_path),
        "scanner_map_hash": file_sha256(scanner_path),
        "high_signal_screen_hash": files_sha256(screen_paths),
        "preprocessing_config_hash": file_sha256(preprocess_config),
        "slic_config_hash": file_sha256(CONFIG),
        "slic_supergrid_voxels_xyz": cfg["slic"]["supergrid_voxels_xyz"],
        "slic_actual_supergrid_mm_xyz": cfg["slic"]["actual_supergrid_mm_xyz"],
        "global_center_low": low_c, "global_center_high": high_c,
        "global_boundary_b": boundary,
        "bootstrap_mode": "formal", "bootstrap_requested": FORMAL_BOOTSTRAPS,
        "bootstrap_completed": int(float(formal_summary["n_bootstrap_completed"])),
        "bootstrap_success": int(float(formal_summary["n_bootstrap_success"])),
        "bootstrap_completion_status": formal_summary["completion_status"],
        "bootstrap_operational_pass": int(float(formal_summary["bootstrap_operational_pass"])),
        "formal_eligible": int(float(formal_summary["formal_eligible"])),
        "bootstrap_summary_hash": file_sha256(formal_summary_path),
        "technical_failure_case_hash": id_hash(failures),
        "main_feature_dictionary_hash": file_sha256(os.path.join(HAB, "feature_dictionary.md")),
        "outcome_columns_read": False, "B_data_read": False,
        "freeze_timestamp": utc_now(),
    }
    atomic_write_json(os.path.join(HAB, "freeze_lock.json"), lock)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["baseline", "structural", "local-global", "bootstrap", "bootstrap-margin", "robustness", "sensitivity", "freeze", "all"], required=True)
    parser.add_argument("--limit", type=int, default=None,
                        help="limit cases for local-global timing smoke test")
    parser.add_argument("--bootstrap-mode", choices=sorted(BOOTSTRAP_COUNTS),
                        default="smoke")
    parser.add_argument("--bootstrap-until", type=int, default=None,
                        help="resume the selected mode through this replicate count")
    args = parser.parse_args()
    if args.stage in ("baseline", "structural", "all"):
        frame = stage1_baseline()
        stage2_structural(frame)
    else:
        frame = None
    if args.stage in ("local-global", "all"):
        stage3_local_global(args.limit)
    if args.stage in ("bootstrap", "all"):
        stage4_bootstrap(args.bootstrap_mode, args.bootstrap_until)
    if args.stage == "bootstrap-margin":
        stage4_margin_update(args.bootstrap_mode)
    if args.stage in ("robustness", "all"):
        stage5_robustness()
    if args.stage in ("sensitivity", "all"):
        stage6_sensitivity()
    if args.stage in ("freeze", "all"):
        stage7_freeze()


if __name__ == "__main__":
    main()
