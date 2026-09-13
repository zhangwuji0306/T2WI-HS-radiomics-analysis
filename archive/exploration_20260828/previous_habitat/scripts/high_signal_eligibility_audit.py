"""Outcome-blind audit of true fat-referenced T2-high tumor signal.

R1 defines cohort eligibility. R2 is calculated only for technical agreement
among double-reader cases. Survival outcomes and B-set model outputs are never
read. Absolute voxel counts are accompanied by physical volumes and equivalent
voxel counts on the project's 1 x 1 x 2 mm reference grid.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy import ndimage


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAB_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(HAB_ROOT)
FEATURE_ROOT = os.path.join(PROJECT_ROOT, "feature_extract")
MANIFEST = os.path.join(FEATURE_ROOT, "output", "manifest.csv")
SCANNER_MAP = os.path.join(FEATURE_ROOT, "output", "scanner_map.csv")
MODEL_A = os.path.join(PROJECT_ROOT, "prognosis_analysis", "output", "modeling_v2", "dataset_primary_raw_A.csv")
MODEL_B = os.path.join(PROJECT_ROOT, "prognosis_analysis", "output", "modeling_v2", "dataset_primary_raw_B.csv")
OUT_ROOT = os.path.join(HAB_ROOT, "output", "high_signal_eligibility_audit")
ASCII_PROJECT_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), "radiomics26")


def ascii_path(path: str) -> str:
    absolute = os.path.abspath(str(path))
    root = os.path.abspath(PROJECT_ROOT)
    if absolute.lower().startswith((root + os.sep).lower()):
        return os.path.join(ASCII_PROJECT_ROOT, absolute[len(root) + 1:])
    return absolute


def absolute_data_path(relative: str) -> str:
    return os.path.join(FEATURE_ROOT, str(relative).replace("/", os.sep).replace("\\", os.sep))


def normalize_sequence(value: str) -> str:
    return re.sub(r"[_\-\s]+", "", str(value or "").strip().lower())


def load_inputs() -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, bool]]:
    manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str).fillna("")
    manifest = manifest[manifest["排除"].astype(str).str.strip() != "1"].copy()
    a_ids = set(pd.read_csv(MODEL_A, encoding="utf-8-sig", dtype=str,
                            usecols=["影像号"])["影像号"].astype(str).str.strip())
    b_ids = set(pd.read_csv(MODEL_B, encoding="utf-8-sig", dtype=str,
                            usecols=["影像号"])["影像号"].astype(str).str.strip())
    split = {pid: "A" for pid in a_ids}
    split.update({pid: "B" for pid in b_ids})
    scanner = pd.read_csv(SCANNER_MAP, encoding="utf-8-sig", dtype=str).fillna("")
    same_sequence = {}
    for _, row in scanner.iterrows():
        pid = str(row["影像号"]).strip()
        s1 = normalize_sequence(row.get("R1系列", ""))
        s2 = normalize_sequence(row.get("R2系列", ""))
        same_sequence[pid] = bool(s1 and s2 and s1 == s2)
    return manifest, split, same_sequence


def robust_mean(values: np.ndarray) -> float:
    if values.size == 0:
        return np.nan
    lo, hi = np.percentile(values, [10.0, 90.0])
    kept = values[(values >= lo) & (values <= hi)]
    return float(kept.mean()) if kept.size else float(values.mean())


def crop_masks(tumor: np.ndarray, high: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    coords = np.argwhere(tumor)
    if coords.size == 0:
        return tumor, high
    lo = coords.min(axis=0)
    hi = coords.max(axis=0) + 1
    slices = tuple(slice(int(lo[i]), int(hi[i])) for i in range(3))
    return tumor[slices], high[slices]


def spatial_high_metrics(tumor: np.ndarray, high: np.ndarray,
                         spacing_zyx: Tuple[float, float, float],
                         voxel_mm3: float) -> Dict[str, float]:
    tumor_crop, high_crop = crop_masks(tumor, high)
    if not tumor_crop.any() or not high_crop.any():
        return {
            "high_components_26": 0,
            "high_lcc_voxels": 0,
            "high_lcc_volume_mm3": 0.0,
            "high_lcc_fraction": 0.0,
            "high_mean_depth_mm": 0.0,
            "high_max_depth_mm": 0.0,
            "high_core1_voxels": 0,
            "high_core1_volume_mm3": 0.0,
            "high_core2_voxels": 0,
            "high_core2_volume_mm3": 0.0,
            "high_core3_voxels": 0,
            "high_core3_volume_mm3": 0.0,
            "high_core2_fraction_of_high": 0.0,
            "high_lcc_core2_voxels": 0,
            "high_lcc_core2_volume_mm3": 0.0,
            "high_lcc_max_depth_mm": 0.0,
        }
    padded = np.pad(tumor_crop, 1, mode="constant", constant_values=False)
    distance = ndimage.distance_transform_edt(padded, sampling=spacing_zyx)[1:-1, 1:-1, 1:-1]
    structure = ndimage.generate_binary_structure(3, 3)
    labels, n_components = ndimage.label(high_crop, structure=structure)
    sizes = np.bincount(labels.ravel())[1:]
    largest_id = int(np.argmax(sizes)) + 1 if sizes.size else 0
    largest = labels == largest_id if largest_id else np.zeros_like(high_crop)
    high_n = int(high_crop.sum())
    lcc_n = int(largest.sum())
    core_counts = {d: int((high_crop & (distance >= float(d))).sum()) for d in (1, 2, 3)}
    lcc_depth = distance[largest] if lcc_n else np.asarray([], dtype=float)
    return {
        "high_components_26": int(n_components),
        "high_lcc_voxels": lcc_n,
        "high_lcc_volume_mm3": float(lcc_n * voxel_mm3),
        "high_lcc_fraction": float(lcc_n / high_n) if high_n else 0.0,
        "high_mean_depth_mm": float(distance[high_crop].mean()) if high_n else 0.0,
        "high_max_depth_mm": float(distance[high_crop].max()) if high_n else 0.0,
        "high_core1_voxels": core_counts[1],
        "high_core1_volume_mm3": float(core_counts[1] * voxel_mm3),
        "high_core2_voxels": core_counts[2],
        "high_core2_volume_mm3": float(core_counts[2] * voxel_mm3),
        "high_core3_voxels": core_counts[3],
        "high_core3_volume_mm3": float(core_counts[3] * voxel_mm3),
        "high_core2_fraction_of_high": float(core_counts[2] / high_n) if high_n else 0.0,
        "high_lcc_core2_voxels": int((largest & (distance >= 2.0)).sum()),
        "high_lcc_core2_volume_mm3": float((largest & (distance >= 2.0)).sum() * voxel_mm3),
        "high_lcc_max_depth_mm": float(lcc_depth.max()) if lcc_depth.size else 0.0,
    }


def calculate_case(pid: str, split: str, reader: str, image_path: str,
                   mask_path: str, fat_label: int, same_sequence: bool) -> Dict[str, object]:
    image = sitk.ReadImage(ascii_path(image_path))
    mask = sitk.ReadImage(ascii_path(mask_path))
    arr = sitk.GetArrayFromImage(image).astype(np.float32, copy=False)
    labels = sitk.GetArrayFromImage(mask)
    if arr.shape != labels.shape:
        raise RuntimeError("image/mask shape mismatch: %s vs %s" % (arr.shape, labels.shape))
    tumor = labels == 1
    fat = labels == int(fat_label)
    tumor_values = arr[tumor]
    fat_values = arr[fat]
    tumor_values = tumor_values[np.isfinite(tumor_values)]
    fat_values = fat_values[np.isfinite(fat_values)]
    if tumor_values.size == 0 or fat_values.size == 0:
        raise RuntimeError("empty tumor or fat ROI")
    spacing_xyz = tuple(float(x) for x in image.GetSpacing())
    spacing_zyx = spacing_xyz[::-1]
    voxel_mm3 = float(np.prod(spacing_xyz))
    fat_mean = float(fat_values.mean())
    fat_median = float(np.median(fat_values))
    fat_trim10 = robust_mean(fat_values)
    structure_xy = np.zeros((3, 3, 3), dtype=bool)
    structure_xy[1, :, :] = True
    fat_eroded = ndimage.binary_erosion(fat, structure=structure_xy, iterations=1, border_value=0)
    fat_eroded_values = arr[fat_eroded]
    fat_eroded_values = fat_eroded_values[np.isfinite(fat_eroded_values)]
    fat_eroded_mean = float(fat_eroded_values.mean()) if fat_eroded_values.size else np.nan
    high = tumor & np.isfinite(arr) & (arr >= fat_mean)
    high_trim = tumor & np.isfinite(arr) & (arr >= fat_trim10)
    high_eroded_ref = tumor & np.isfinite(arr) & (arr >= fat_eroded_mean) if np.isfinite(fat_eroded_mean) else np.zeros_like(tumor)
    high_count = int(high.sum())
    tumor_count = int(tumor.sum())
    fat_count = int(fat.sum())
    row: Dict[str, object] = {
        "patient_id": pid,
        "split": split,
        "reader": reader,
        "same_sequence_R1_R2": int(bool(same_sequence)),
        "image_path": os.path.relpath(image_path, PROJECT_ROOT),
        "mask_path": os.path.relpath(mask_path, PROJECT_ROOT),
        "fat_label": int(fat_label),
        "spacing_x_mm": spacing_xyz[0],
        "spacing_y_mm": spacing_xyz[1],
        "spacing_z_mm": spacing_xyz[2],
        "voxel_volume_mm3": voxel_mm3,
        "tumor_voxels": tumor_count,
        "tumor_volume_mm3": float(tumor_count * voxel_mm3),
        "fat_voxels": fat_count,
        "fat_volume_mm3": float(fat_count * voxel_mm3),
        "fat_mean": fat_mean,
        "fat_median": fat_median,
        "fat_trimmed_mean_10pct": fat_trim10,
        "fat_sd": float(fat_values.std(ddof=1)) if fat_values.size > 1 else 0.0,
        "fat_p10": float(np.percentile(fat_values, 10.0)),
        "fat_p90": float(np.percentile(fat_values, 90.0)),
        "fat_eroded_xy1_voxels": int(fat_eroded_values.size),
        "fat_eroded_xy1_mean": fat_eroded_mean,
        "tumor_mean": float(tumor_values.mean()),
        "tumor_median": float(np.median(tumor_values)),
        "tumor_p95": float(np.percentile(tumor_values, 95.0)),
        "tumor_p99": float(np.percentile(tumor_values, 99.0)),
        "tumor_max": float(tumor_values.max()),
        "tumor_p99_to_fat_mean": float(np.percentile(tumor_values, 99.0) / fat_mean) if fat_mean != 0 else np.nan,
        "high_voxels_ge_fat_mean": high_count,
        "high_volume_mm3": float(high_count * voxel_mm3),
        "high_equiv_voxels_1x1x2": float(high_count * voxel_mm3 / 2.0),
        "high_fraction": float(high_count / tumor_count) if tumor_count else np.nan,
        "high_voxels_ge_fat_trim10": int(high_trim.sum()),
        "high_fraction_ge_fat_trim10": float(high_trim.sum() / tumor_count) if tumor_count else np.nan,
        "high_voxels_ge_eroded_fat_mean": int(high_eroded_ref.sum()),
        "high_fraction_ge_eroded_fat_mean": float(high_eroded_ref.sum() / tumor_count) if tumor_count else np.nan,
    }
    row.update(spatial_high_metrics(tumor, high, spacing_zyx, voxel_mm3))
    return row


def cohen_kappa(a: np.ndarray, b: np.ndarray) -> float:
    if a.size == 0:
        return np.nan
    observed = float((a == b).mean())
    pa = float(a.mean())
    pb = float(b.mean())
    expected = pa * pb + (1.0 - pa) * (1.0 - pb)
    return float((observed - expected) / (1.0 - expected)) if expected < 1.0 else np.nan


def scenario_mask(df: pd.DataFrame, spec: Dict[str, float]) -> pd.Series:
    passed = pd.Series(True, index=df.index)
    passed &= pd.to_numeric(df["high_volume_mm3"], errors="coerce") >= spec.get("volume_mm3", 0.0)
    passed &= pd.to_numeric(df["high_fraction"], errors="coerce") >= spec.get("fraction", 0.0)
    passed &= pd.to_numeric(df["high_lcc_volume_mm3"], errors="coerce") >= spec.get("lcc_mm3", 0.0)
    passed &= pd.to_numeric(df["high_core2_volume_mm3"], errors="coerce") >= spec.get("core2_mm3", 0.0)
    passed &= pd.to_numeric(df["high_lcc_core2_volume_mm3"], errors="coerce") >= spec.get("lcc_core2_mm3", 0.0)
    return passed.fillna(False)


def summarize_scenarios(features: pd.DataFrame) -> pd.DataFrame:
    scenarios = [
        ("any_ge_fat_mean", {"volume_mm3": 1e-12}),
        ("equiv_64vox", {"volume_mm3": 128.0}),
        ("fraction_0.1pct", {"fraction": 0.001}),
        ("fraction_0.25pct", {"fraction": 0.0025}),
        ("fraction_0.5pct", {"fraction": 0.005}),
        ("fraction_1pct", {"fraction": 0.01}),
        ("volume128_fraction0.1", {"volume_mm3": 128.0, "fraction": 0.001}),
        ("volume128_fraction0.5", {"volume_mm3": 128.0, "fraction": 0.005}),
        ("volume128_fraction0.5_core_any", {"volume_mm3": 128.0, "fraction": 0.005, "core2_mm3": 1e-12}),
        ("volume128_fraction0.5_core16", {"volume_mm3": 128.0, "fraction": 0.005, "core2_mm3": 16.0}),
        ("balanced", {"volume_mm3": 128.0, "fraction": 0.005, "lcc_mm3": 64.0,
                      "core2_mm3": 16.0, "lcc_core2_mm3": 8.0}),
        ("recommended", {"fraction": 0.01,
                         "lcc_mm3": 128.0, "core2_mm3": 32.0}),
        ("lenient", {"volume_mm3": 64.0, "fraction": 0.0025, "lcc_mm3": 32.0,
                     "core2_mm3": 8.0, "lcc_core2_mm3": 2.0}),
        ("strict", {"volume_mm3": 256.0, "fraction": 0.01, "lcc_mm3": 128.0,
                    "core2_mm3": 32.0, "lcc_core2_mm3": 16.0}),
    ]
    r1 = features[features["reader"] == "R1"].copy()
    r2 = features[(features["reader"] == "R2") & (features["same_sequence_R1_R2"] == 1)].copy()
    paired_ids = sorted(set(r1["patient_id"]) & set(r2["patient_id"]))
    rows: List[Dict[str, object]] = []
    for name, spec in scenarios:
        p1 = scenario_mask(r1, spec)
        row: Dict[str, object] = {"scenario": name}
        row.update(spec)
        for split in ("ALL", "A", "B"):
            use = np.ones(len(r1), dtype=bool) if split == "ALL" else (r1["split"].to_numpy() == split)
            row[split + "_n"] = int(use.sum())
            row[split + "_pass_n"] = int((p1.to_numpy() & use).sum())
            row[split + "_pass_rate"] = float((p1.to_numpy() & use).sum() / use.sum()) if use.sum() else np.nan
        if paired_ids:
            x1 = r1.set_index("patient_id").loc[paired_ids]
            x2 = r2.set_index("patient_id").loc[paired_ids]
            a = scenario_mask(x1, spec).to_numpy(dtype=bool)
            b = scenario_mask(x2, spec).to_numpy(dtype=bool)
            row["paired_same_sequence_n"] = len(paired_ids)
            row["paired_agreement"] = float((a == b).mean())
            row["paired_kappa"] = cohen_kappa(a, b)
            row["paired_R1_pass_n"] = int(a.sum())
            row["paired_R2_pass_n"] = int(b.sum())
            row["paired_both_pass_n"] = int((a & b).sum())
        rows.append(row)
    return pd.DataFrame(rows)


def write_distribution_summary(r1: pd.DataFrame) -> None:
    variables = [
        "voxel_volume_mm3", "tumor_voxels", "tumor_volume_mm3", "fat_voxels",
        "fat_mean", "fat_median", "fat_trimmed_mean_10pct", "fat_eroded_xy1_mean",
        "high_voxels_ge_fat_mean", "high_volume_mm3", "high_equiv_voxels_1x1x2",
        "high_fraction", "high_lcc_volume_mm3", "high_lcc_fraction",
        "high_core2_volume_mm3", "high_core2_fraction_of_high", "high_max_depth_mm",
        "high_lcc_max_depth_mm",
    ]
    rows = []
    for split in ("ALL", "A", "B"):
        subset = r1 if split == "ALL" else r1[r1["split"] == split]
        for variable in variables:
            x = pd.to_numeric(subset[variable], errors="coerce").dropna()
            rows.append({
                "split": split, "variable": variable, "n": len(x),
                "min": float(x.min()) if len(x) else np.nan,
                "p01": float(x.quantile(0.01)) if len(x) else np.nan,
                "p05": float(x.quantile(0.05)) if len(x) else np.nan,
                "p10": float(x.quantile(0.10)) if len(x) else np.nan,
                "p25": float(x.quantile(0.25)) if len(x) else np.nan,
                "median": float(x.median()) if len(x) else np.nan,
                "p75": float(x.quantile(0.75)) if len(x) else np.nan,
                "p90": float(x.quantile(0.90)) if len(x) else np.nan,
                "p95": float(x.quantile(0.95)) if len(x) else np.nan,
                "p99": float(x.quantile(0.99)) if len(x) else np.nan,
                "max": float(x.max()) if len(x) else np.nan,
            })
    pd.DataFrame(rows).to_csv(os.path.join(OUT_ROOT, "distribution_summary.csv"),
                              index=False, encoding="utf-8-sig")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit R1 cases for timing/smoke testing; zero means all")
    args = parser.parse_args()
    os.makedirs(OUT_ROOT, exist_ok=True)
    manifest, split_map, same_sequence = load_inputs()
    if args.limit > 0:
        manifest = manifest.head(args.limit).copy()
    start = time.time()
    records: List[Dict[str, object]] = []
    errors: List[Dict[str, str]] = []
    for i, (_, row) in enumerate(manifest.iterrows(), start=1):
        pid = str(row["影像号"]).strip()
        try:
            records.append(calculate_case(
                pid, split_map.get(pid, ""), "R1",
                absolute_data_path(row["图像文件"]),
                absolute_data_path(row["掩膜文件"]), 2,
                same_sequence.get(pid, False)))
        except Exception as exc:
            errors.append({"patient_id": pid, "reader": "R1", "error": str(exc)})
        if str(row.get("是否双读者", "")).strip() == "1" and str(row.get("R2图像文件", "")).strip():
            muscle_label_text = str(row.get("R2肌肉标签", "3")).strip()
            muscle_label = int(muscle_label_text) if muscle_label_text in ("2", "3") else 3
            fat_label = 3 if muscle_label == 2 else 2
            try:
                records.append(calculate_case(
                    pid, split_map.get(pid, ""), "R2",
                    absolute_data_path(row["R2图像文件"]),
                    absolute_data_path(row["R2掩膜文件"]), fat_label,
                    same_sequence.get(pid, False)))
            except Exception as exc:
                errors.append({"patient_id": pid, "reader": "R2", "error": str(exc)})
        if i % 50 == 0:
            print("processed R1 cases:", i, "elapsed_seconds:", round(time.time() - start, 1), flush=True)
    features = pd.DataFrame(records)
    features.to_csv(os.path.join(OUT_ROOT, "patient_features.csv"), index=False,
                    encoding="utf-8-sig")
    pd.DataFrame(errors, columns=["patient_id", "reader", "error"]).to_csv(
        os.path.join(OUT_ROOT, "errors.csv"), index=False, encoding="utf-8-sig")
    r1 = features[features["reader"] == "R1"].copy()
    write_distribution_summary(r1)
    summarize_scenarios(features).to_csv(
        os.path.join(OUT_ROOT, "threshold_scenarios.csv"), index=False,
        encoding="utf-8-sig")
    elapsed = time.time() - start
    pd.DataFrame([{
        "R1_cases": int((features["reader"] == "R1").sum()),
        "R2_cases": int((features["reader"] == "R2").sum()),
        "errors": len(errors),
        "elapsed_seconds": round(elapsed, 3),
        "outcome_columns_read": False,
        "eligibility_defined_by": "R1",
        "R2_role": "technical_agreement_only",
    }]).to_csv(os.path.join(OUT_ROOT, "run_manifest.csv"), index=False,
               encoding="utf-8-sig")
    print("R1 cases:", int((features["reader"] == "R1").sum()))
    print("R2 cases:", int((features["reader"] == "R2").sum()))
    print("errors:", len(errors))
    print("elapsed seconds:", round(elapsed, 1))
    print("outputs:", OUT_ROOT)


if __name__ == "__main__":
    main()
