"""Post-Primary-v2 threshold-free DFS sensitivity analysis on all 693 cases.

The script deliberately keeps the existing Primary-v2 A393 and FT05A B163
assets read-only.  It extends the frozen technical phenotype only for the
137 A cases outside A393, builds an expanded A-only outer split, performs the
same canonical M0--M5 modeling engine, and evaluates frozen expanded-A
models on B163 after the A refit is complete.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd
from scipy import ndimage
from sklearn.model_selection import StratifiedKFold


HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
PRIMARY_ROOT = os.path.join(PROJECT_ROOT, "prognosis_analysis", "primary")
if PRIMARY_ROOT not in sys.path:
    sys.path.insert(0, PRIMARY_ROOT)
SCRIPT_ROOT = os.path.join(PROJECT_ROOT, "prognosis_analysis", "scripts")
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

from prognosis_analysis.primary import run_cv as canonical  # noqa: E402
from prognosis_analysis.primary import validate_assets as va  # noqa: E402
import w03_habitat_radiomics as w03  # noqa: E402

try:
    import SimpleITK as sitk
    from radiomics import featureextractor
    import radiomics
except ImportError as exc:  # pragma: no cover - environment guard
    raise RuntimeError("t2_radiomics environment is required: %s" % exc)


DATA_XLSX = os.path.join(PROJECT_ROOT, "prognosis_analysis", "data",
                         "radiology_clinic_pathology_prognosis_data.xlsx")
MANIFEST = os.path.join(PROJECT_ROOT, "feature_extract", "output", "manifest.csv")
SCANNER = os.path.join(PROJECT_ROOT, "feature_extract", "output", "scanner_map.csv")
PREP_ROOT = os.path.join(PROJECT_ROOT, "feature_extract", "output", "preprocessed")
WHOLE_FEATURES = os.path.join(
    PROJECT_ROOT, "feature_extract", "output", "features_v2", "muscle_f0.25",
    "features_original.csv")
PRIMARY_A_IDS = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "output", "technical_cohort_manifest",
    "cohort_A_lenient.csv")
PRIMARY_GLOBAL = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "output", "habitat_features_A",
    "global_descriptors_full_A.csv")
PRIMARY_R_LOW = os.path.join(
    PROJECT_ROOT, "archive", "prognosis_analysis_output",
    "w03_habitat_radiomics_A", "R1_R_low_features.csv")
PRIMARY_R_HIGH = os.path.join(
    PROJECT_ROOT, "archive", "prognosis_analysis_output",
    "w03_habitat_radiomics_A", "R1_R_high_features.csv")
FROZEN_SPLIT = os.path.join(
    PROJECT_ROOT, "prognosis_analysis", "output", "outer_splits_A.csv")
B_TECHNICAL = os.path.join(
    PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3",
    "FT05A", ".finalize", "FT05A_B_technical_features.csv")
PRIMARY_A_FT03 = os.path.join(
    PROJECT_ROOT, "archive", "ft_validation_v1", "FT03_A_validation.json")
PRIMARY_B_FT06 = os.path.join(
    PROJECT_ROOT, "archive", "ft_validation_v1", "FT06_B_validation.json")

OUTPUT_ROOT = os.path.join(PROJECT_ROOT, "prognosis_analysis", "output",
                           "sensitivity_693")
CACHE_ROOT = os.path.join(PROJECT_ROOT, "habitat_analysis", "output",
                          "sensitivity_693_cache")
MAP_ROOT = os.path.join(CACHE_ROOT, "habitat_maps_R1")

SEED = 12345
RADIOMICS_FEATURES = tuple(
    "R_low__" + name for name in va.R_LOW_FEATURE_NAMES) + tuple(
    "R_high__" + name for name in va.R_HIGH_FEATURE_NAMES)
W_FEATURES = tuple("W__" + name for name in va.W_ORIGINAL_FEATURE_NAMES)

RUNS = (
    {"run_id": "M0", "model_id": "M0", "population": "main"},
    {"run_id": "M1", "model_id": "M1", "population": "main"},
    {"run_id": "M2", "model_id": "M2", "population": "main"},
    {"run_id": "M0_W_Original", "model_id": "M0", "population": "W_Original_available"},
    {"run_id": "M5", "model_id": "M5", "population": "W_Original_available"},
    {"run_id": "M2_R_low", "model_id": "M2", "population": "R_low"},
    {"run_id": "M3L", "model_id": "M3L", "population": "R_low"},
    {"run_id": "M2_R_high", "model_id": "M2", "population": "R_high"},
    {"run_id": "M3H", "model_id": "M3H", "population": "R_high"},
    {"run_id": "M2_dual", "model_id": "M2", "population": "dual_radiomics"},
    {"run_id": "M3L_dual", "model_id": "M3L", "population": "dual_radiomics"},
    {"run_id": "M3H_dual", "model_id": "M3H", "population": "dual_radiomics"},
    {"run_id": "M4", "model_id": "M4", "population": "dual_radiomics"},
    {"run_id": "M5_dual", "model_id": "M5", "population": "dual_radiomics"},
)

COMPARISON_DEFINITIONS = (
    {"comparison_id": "M0_vs_M3L", "left_model": "M0",
     "right_model": "M3L", "population": "R_low",
     "group": "primary_clinical_value"},
    {"comparison_id": "M0_vs_M3H", "left_model": "M0",
     "right_model": "M3H", "population": "R_high",
     "group": "primary_clinical_value"},
    {"comparison_id": "M0_vs_M1", "left_model": "M0",
     "right_model": "M1", "population": "main",
     "group": "primary_clinical_value_supporting"},
    {"comparison_id": "M0_vs_M2", "left_model": "M0",
     "right_model": "M2", "population": "main",
     "group": "primary_clinical_value_supporting"},
    {"comparison_id": "M0_vs_M4", "left_model": "M0",
     "right_model": "M4", "population": "dual_radiomics",
     "group": "primary_clinical_value_supporting"},
    {"comparison_id": "M0_vs_M5", "left_model": "M0",
     "right_model": "M5", "population": "W_Original_available",
     "group": "primary_clinical_value_supporting"},
    {"comparison_id": "M2_vs_M3L", "left_model": "M2",
     "right_model": "M3L", "population": "R_low",
     "group": "habitat_radiomics_incremental"},
    {"comparison_id": "M2_vs_M3H", "left_model": "M2",
     "right_model": "M3H", "population": "R_high",
     "group": "habitat_radiomics_incremental"},
    {"comparison_id": "M1_vs_M2", "left_model": "M1",
     "right_model": "M2", "population": "main",
     "group": "habitat_radiomics_incremental_supporting"},
    {"comparison_id": "M2_vs_M4", "left_model": "M2",
     "right_model": "M4", "population": "dual_radiomics",
     "group": "habitat_radiomics_incremental_supporting"},
    {"comparison_id": "M3L_vs_M3H", "left_model": "M3L",
     "right_model": "M3H", "population": "dual_radiomics",
     "group": "secondary_head_to_head"},
    {"comparison_id": "M4_vs_M5", "left_model": "M4",
     "right_model": "M5", "population": "dual_radiomics",
     "group": "secondary_head_to_head"},
)

COMPARISON_METRICS = (
    "harrell_c_index_pooled", "uno_c_index", "3_year_auc",
    "3_year_brier", "5_year_auc", "5_year_brier",
)


def _ensure_dirs():
    for path in (OUTPUT_ROOT, CACHE_ROOT, MAP_ROOT):
        os.makedirs(path, exist_ok=True)


def _write_csv(frame, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _write_json(payload, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path, **kwargs):
    return pd.read_csv(path, encoding="utf-8-sig", **kwargs)


def _fixed_split(manifest, scanner):
    """Apply the project-wide scanner rule without importing the broken guard."""
    manifest = manifest.copy()
    scanner = scanner.copy()
    manifest["影像号"] = manifest["影像号"].astype(str).str.strip()
    scanner["影像号"] = scanner["影像号"].astype(str).str.strip()
    if manifest["影像号"].duplicated().any() or scanner["影像号"].duplicated().any():
        raise RuntimeError("manifest/scanner identifiers are not unique")
    merged = manifest.merge(
        scanner[["影像号", "R1厂商", "R1机型", "R1场强"]],
        on="影像号", how="left", validate="one_to_one")
    strength = pd.to_numeric(merged["R1场强"], errors="coerce")
    is_a = ((merged["R1厂商"] == "GE MEDICAL SYSTEMS") &
            (merged["R1机型"] == "DISCOVERY MR750") &
            (strength.round(1) == 3.0))
    merged["split"] = "B"
    merged.loc[is_a, "split"] = "A"
    return merged


def _cohort_ids():
    manifest = _read_csv(MANIFEST, dtype=str)
    scanner = _read_csv(SCANNER, dtype=str)
    cohort = _fixed_split(manifest, scanner)
    if "排除" in cohort.columns:
        cohort = cohort[cohort["排除"].fillna("0").astype(str).ne("1")]
    if len(cohort) != 693 or cohort["影像号"].nunique() != 693:
        raise RuntimeError("threshold-free technical target is not exactly 693")
    counts = cohort["split"].value_counts().to_dict()
    if counts.get("A") != 530 or counts.get("B") != 163:
        raise RuntimeError("fixed A/B rule did not resolve to A530+B163: %s" % counts)
    primary = _read_csv(PRIMARY_A_IDS, dtype=str)["影像号"].astype(str).str.strip()
    primary_ids = set(primary)
    if len(primary_ids) != 393 or not primary_ids.issubset(
            set(cohort.loc[cohort["split"].eq("A"), "影像号"])):
        raise RuntimeError("Primary A393 identity is not a subset of full A530")
    return cohort, primary_ids


def _six_neighbor_interface(habitat, roi, spacing_xyz):
    areas = [spacing_xyz[0] * spacing_xyz[1],
             spacing_xyz[0] * spacing_xyz[2],
             spacing_xyz[1] * spacing_xyz[2]]
    total = 0.0
    for axis, area in enumerate(areas):
        a = np.take(habitat, range(habitat.shape[axis] - 1), axis=axis)
        b = np.take(habitat, range(1, habitat.shape[axis]), axis=axis)
        ra = np.take(roi, range(roi.shape[axis] - 1), axis=axis)
        rb = np.take(roi, range(1, roi.shape[axis]), axis=axis)
        total += float(((a >= 0) & (b >= 0) & ra & rb & (a != b)).sum()) * area
    return total


def _case_with_global(pid, extractor, slic_config, slic_grid_metadata,
                      slic_labels, phenotype, map_path):
    """Run the frozen R1 SLIC/phenotype/radiomics path for one new A case."""
    image_path = os.path.join(PREP_ROOT, pid, "R1_image.nrrd")
    mask_path = os.path.join(PREP_ROOT, pid, "R1_mask.nrrd")
    base = {
        "影像号": pid, "reader": "R1", "input_status": "not_available",
        "pipeline_status": "not_available", "structural_state": "not_available",
        "H_low_present": 0, "H_high_present": 0, "H_low_voxels": np.nan,
        "H_high_voxels": np.nan, "n_supervoxels": np.nan,
        "input_failure_reason": "reader_input_missing", "blocks": {},
    }
    for block_name, _label in w03.BLOCKS:
        base["blocks"][block_name] = w03.unavailable_block_result()
    if not (os.path.exists(image_path) and os.path.exists(mask_path)):
        return base, None
    base.update(input_status="available", pipeline_status="technical_failure",
                input_failure_reason="")
    try:
        image = sitk.ReadImage(w03.apath(image_path))
        roi_image = sitk.ReadImage(w03.apath(mask_path))
        errors = w03.geometry_errors(image, roi_image)
        if errors:
            raise RuntimeError(";".join(errors))
        array = sitk.GetArrayFromImage(image).astype(np.float32, copy=False)
        roi_array = sitk.GetArrayFromImage(roi_image)
        if array.shape != roi_array.shape:
            raise RuntimeError("image_mask_array_shape_mismatch")
        if not np.isin(np.unique(roi_array), [0, 1]).all():
            raise RuntimeError("nonbinary_preprocessed_mask")
        tumor = roi_array == 1
        if not tumor.any():
            raise RuntimeError("empty_tumor_roi")
        if not np.isfinite(array[tumor]).all():
            raise RuntimeError("nonfinite_image_inside_tumor")

        labels = slic_labels(image, slic_config, True)
        if labels.shape != tumor.shape:
            raise RuntimeError("slic_label_shape_mismatch")
        labels_inside = np.unique(labels[tumor])
        if not len(labels_inside) or np.any(labels[tumor] < 0):
            raise RuntimeError("slic_unassigned_or_empty_tumor_supervoxels")
        habitat = np.full(labels.shape, -1, dtype=np.int8)
        supervoxel_means = []
        for label in labels_inside:
            inside = (labels == int(label)) & tumor
            mean = float(array[inside].mean())
            if not np.isfinite(mean):
                raise RuntimeError("nonfinite_supervoxel_mean")
            supervoxel_means.append(mean)
            habitat[labels == int(label)] = int(mean >= phenotype["boundary_b"])
        habitat[~tumor] = -1
        if np.any(habitat[tumor] < 0):
            raise RuntimeError("unassigned_tumor_habitat")

        low_mask = tumor & (habitat == 0)
        high_mask = tumor & (habitat == 1)
        low_count = int(low_mask.sum())
        high_count = int(high_mask.sum())
        tumor_n = int(tumor.sum())
        if low_count + high_count != tumor_n:
            raise RuntimeError("tumor_voxel_not_assigned_to_habitat")
        state = w03.classify_habitat_state(low_count, high_count)
        spacing_xyz = tuple(float(value) for value in image.GetSpacing())
        voxel_volume = float(np.prod(spacing_xyz))
        tumor_volume = tumor_n * voxel_volume
        p_low = float(low_count) / tumor_n
        p_high = float(high_count) / tumor_n
        entropy = -sum(p * math.log(p) for p in (p_low, p_high) if p > 0)
        interface = _six_neighbor_interface(habitat, tumor, spacing_xyz)
        component_labels, n_components = ndimage.label(
            high_mask, ndimage.generate_binary_structure(3, 1))
        sizes = np.bincount(component_labels.ravel())[1:] if n_components else np.array([])
        largest = int(sizes.max()) if len(sizes) else 0
        depth = ndimage.distance_transform_edt(tumor, sampling=spacing_xyz[::-1])
        max_depth = float(depth[tumor].max()) if tumor.any() else 0.0
        radial = (float(depth[high_mask].sum() / (max_depth * tumor_n))
                  if high_count and max_depth > 0 else 0.0)
        values = np.asarray(supervoxel_means, dtype=float)
        global_row = {
            "影像号": pid, "H_low_voxels": low_count,
            "H_high_voxels": high_count, "tumor_voxels": tumor_n,
            "tumor_volume_mm3": tumor_volume,
            "H_high_fraction": p_high, "H_low_fraction": p_low,
            "habitat_entropy": float(entropy), "interface_area_mm2": interface,
            "interface_density": float(interface / tumor_volume),
            "H_high_largest_component_tumor_fraction": float(largest / tumor_n),
            "H_high_component_density": float(
                n_components / (tumor_volume / 1000.0)) if tumor_volume else np.nan,
            "H_high_radial_burden": radial,
            "sv_median_minus_boundary": float(np.median(values) - phenotype["boundary_b"]),
            "sv_IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "global_center_low": phenotype["H_low"],
            "global_center_high": phenotype["H_high"],
            "global_boundary_b": phenotype["boundary_b"],
            "structural_state": state, "hard_technical_failure": 0,
        }
        base.update(
            pipeline_status="success", structural_state=state,
            H_low_present=int(bool(low_count)), H_high_present=int(bool(high_count)),
            H_low_voxels=low_count, H_high_voxels=high_count,
            n_supervoxels=int(len(labels_inside)),
            slic_spacing_mm_xyz=";".join("%.8g" % x for x in
                                         slic_grid_metadata(image, slic_config)["spacing_mm_xyz"]),
        )
        for block_name, label in w03.BLOCKS:
            present = bool(low_count if label == 0 else high_count)
            if not present:
                base["blocks"][block_name] = w03.block_result(False)
                continue
            try:
                mask = w03.make_habitat_mask(image, habitat, label)
                raw = extractor.execute(image, mask)
                features, diagnostics = w03._numeric_features(raw)
                base["blocks"][block_name] = w03.block_result(
                    True, features=features, diagnostics=diagnostics)
            except Exception as exc:  # noqa: BLE001
                base["blocks"][block_name] = w03.block_result(
                    True, error=w03._error_text(exc))
        output = sitk.GetImageFromArray(habitat.astype(np.int8))
        output.CopyInformation(image)
        sitk.WriteImage(output, w03.apath(map_path), useCompression=True)
        return base, global_row
    except Exception as exc:  # noqa: BLE001
        reason = w03._error_text(exc)
        base["input_failure_reason"] = reason
        for block_name, _label in w03.BLOCKS:
            base["blocks"][block_name] = w03.block_result(True, error=reason)
        return base, None


def _new_block_frame(rows, block_name, feature_names):
    present_key = "H_low_present" if block_name == "R_low" else "H_high_present"
    records = []
    for row in rows:
        result = row["blocks"][block_name]
        item = {
            "影像号": row["影像号"], "reader": "R1",
            "input_status": row["input_status"],
            "pipeline_status": row["pipeline_status"],
            "structural_state": row["structural_state"],
            "habitat_present": row[present_key],
            "extractable": result["extractable"],
            "status": result["status"],
            "failure_class": result["failure_class"],
            "failure_reason": result["failure_reason"],
        }
        item.update({block_name + "__" + name: result["features"].get(name, np.nan)
                     for name in feature_names})
        records.append(item)
    return pd.DataFrame(records)


def run_t1():
    started = time.perf_counter()
    _ensure_dirs()
    cohort, primary_ids = _cohort_ids()
    a_ids = set(cohort.loc[cohort["split"].eq("A"), "影像号"])
    b_ids = set(cohort.loc[cohort["split"].eq("B"), "影像号"])
    new_a_ids = sorted(a_ids - primary_ids)

    cfg = w03.load_config()
    phenotype = w03.load_frozen_phenotype(cfg)
    slic_config = w03.load_slic_config(cfg)
    slic_grid_metadata, slic_labels = w03.load_slic_functions()
    extractor = featureextractor.RadiomicsFeatureExtractor(
        w03.extractor_settings(cfg))
    rows = []
    globals_ = []
    for index, pid in enumerate(new_a_ids, start=1):
        row, global_row = _case_with_global(
            pid, extractor, slic_config, slic_grid_metadata, slic_labels,
            phenotype, os.path.join(MAP_ROOT, pid + "_R1_habitat.nrrd"))
        rows.append(row)
        if global_row is not None:
            globals_.append(global_row)
        if index == 1 or index % 10 == 0 or index == len(new_a_ids):
            print("T1 R1 processed %d/%d" % (index, len(new_a_ids)), flush=True)

    feature_names = sorted(set(
        name for row in rows for block_name, _label in w03.BLOCKS
        for name in row["blocks"][block_name]["features"]))
    if not feature_names:
        raise RuntimeError("T1 extracted no radiomics features")
    for required in va.R_LOW_FEATURE_NAMES + va.R_HIGH_FEATURE_NAMES:
        if required not in feature_names:
            raise RuntimeError("T1 feature schema lacks %s" % required)
    low_frame = _new_block_frame(rows, "R_low", feature_names)
    high_frame = _new_block_frame(rows, "R_high", feature_names)
    _write_csv(low_frame, os.path.join(CACHE_ROOT, "new_A_R1_R_low_features.csv"))
    _write_csv(high_frame, os.path.join(CACHE_ROOT, "new_A_R1_R_high_features.csv"))
    _write_csv(pd.DataFrame(globals_), os.path.join(
        CACHE_ROOT, "new_A_global_descriptors.csv"))

    map_ids = {name.split("_R1_habitat.nrrd")[0] for name in os.listdir(MAP_ROOT)
               if name.endswith("_R1_habitat.nrrd")}
    manifest_rows = []
    for pid in sorted(cohort["影像号"].astype(str)):
        if pid in primary_ids:
            asset = "reused_primary_A393"
        elif pid in b_ids:
            asset = "reused_FT05A_B163"
        else:
            asset = "new_sensitivity_A_extension"
        row = next((item for item in rows if item["影像号"] == pid), None)
        manifest_rows.append({
            "patient_id": pid, "split": cohort.loc[
                cohort["影像号"].eq(pid), "split"].iloc[0],
            "habitat_asset": asset,
            "new_A_R1_input_status": row["input_status"] if row else "reused",
            "new_A_R1_pipeline_status": row["pipeline_status"] if row else "reused",
            "new_A_R1_structural_state": row["structural_state"] if row else "reused",
            "new_A_R1_map_written": int(pid in map_ids) if pid not in primary_ids else 1,
        })
    manifest = pd.DataFrame(manifest_rows)
    _write_csv(manifest, os.path.join(OUTPUT_ROOT,
                                      "sensitivity_693_cohort_manifest.csv"))
    technical_failures = manifest.loc[
        manifest["new_A_R1_pipeline_status"].eq("technical_failure")]
    states = manifest.loc[manifest["split"].eq("A"),
                          "new_A_R1_structural_state"].value_counts(dropna=False).to_dict()
    summary = {
        "stage": "T1", "status": "COMPLETE", "target_n": 693,
        "A_n": 530, "B_n": 163, "Primary_A_reused_n": 393,
        "new_A_extension_n": 137, "new_A_R1_processed_n": len(rows),
        "new_A_R1_success_n": int(sum(r["pipeline_status"] == "success" for r in rows)),
        "new_A_R1_technical_failure_n": int(len(technical_failures)),
        "new_A_structural_states": states,
        "new_A_map_n": len(map_ids),
        "fixed_phenotype": phenotype,
        "radiomics_version": getattr(radiomics, "__version__", "unknown"),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "primary_assets_read_only": True,
        "threshold_free": True,
    }
    _write_json(summary, os.path.join(OUTPUT_ROOT, "T1_summary.json"))
    return summary


def _clinical(ids, columns):
    usecols = ["影像号"] + [column for column in columns if column != "影像号"]
    frame = pd.read_excel(DATA_XLSX, sheet_name="Sheet1", usecols=usecols)
    frame["影像号"] = frame["影像号"].astype(str).str.strip()
    frame = frame[frame["影像号"].isin(set(str(x) for x in ids))].copy()
    if frame["影像号"].duplicated().any() or len(frame) != len(set(ids)):
        raise RuntimeError("clinical read did not return the exact authorized ID set")
    return frame


def _global_frame(primary_ids, new_ids):
    primary = _read_csv(PRIMARY_GLOBAL, dtype={"影像号": str})
    new = _read_csv(os.path.join(CACHE_ROOT, "new_A_global_descriptors.csv"),
                    dtype={"影像号": str})
    frame = pd.concat([primary, new], ignore_index=True, sort=False)
    frame["影像号"] = frame["影像号"].astype(str).str.strip()
    if len(frame) != 530 or frame["影像号"].nunique() != 530:
        raise RuntimeError("expanded A global descriptor frame is not A530")
    return frame


def _habitat_block(block, primary_ids, new_ids, block_name):
    path = PRIMARY_R_LOW if block_name == "R_low" else PRIMARY_R_HIGH
    primary = _read_csv(path, dtype={"影像号": str})
    new_path = os.path.join(CACHE_ROOT, "new_A_R1_%s_features.csv" % block_name)
    new = _read_csv(new_path, dtype={"影像号": str})
    for frame in (primary, new):
        frame["影像号"] = frame["影像号"].astype(str).str.strip()
    frame = pd.concat([primary, new], ignore_index=True, sort=False)
    if frame["影像号"].duplicated().any():
        raise RuntimeError("duplicate %s identifiers" % block_name)
    frame = frame.set_index("影像号")
    ids = sorted(set(primary_ids) | set(new_ids))
    if set(frame.index) != set(ids):
        raise RuntimeError("%s does not cover expanded A530" % block_name)
    output = pd.DataFrame(index=ids)
    output["%s_structurally_defined" % block_name] = pd.to_numeric(
        frame.loc[ids, "habitat_present"], errors="coerce").fillna(0).astype(int)
    output["%s_technically_available" % block_name] = pd.to_numeric(
        frame.loc[ids, "extractable"], errors="coerce").fillna(0).astype(int)
    for name in va.FEATURE_NAMES[block_name]:
        column = block_name + "__" + name
        if column not in frame.columns:
            raise RuntimeError("missing frozen feature %s" % column)
        output[column] = pd.to_numeric(frame.loc[ids, column], errors="coerce")
    output = output.reset_index()
    return output.rename(columns={"index": "patient_id"})


def _whole_frame(ids):
    whole = _read_csv(WHOLE_FEATURES, dtype={"影像号": str})
    whole = whole[(whole["读者"].astype(str) == "R1") &
                  whole["影像号"].astype(str).str.strip().isin(set(ids))].copy()
    whole["patient_id"] = whole["影像号"].astype(str).str.strip()
    if whole["patient_id"].duplicated().any() or len(whole) != len(set(ids)):
        raise RuntimeError("whole-tumor R1 features do not cover the authorized IDs")
    output = whole[["patient_id"] + list(va.W_ORIGINAL_FEATURE_NAMES)].copy()
    output = output.rename(columns={name: "W__" + name
                                    for name in va.W_ORIGINAL_FEATURE_NAMES})
    output["W_Original_available"] = (
        np.isfinite(output[list(W_FEATURES)].to_numpy(dtype=float)).all(axis=1).astype(int))
    return output


def _build_frame(ids, split, include_outcome=True):
    ids = sorted(str(x) for x in ids)
    clinical_columns = list(va.CLINICAL_COLUMNS)
    if include_outcome:
        clinical_columns += ["DFS_time", "DFS_event"]
    clinical = _clinical(ids, clinical_columns)
    clinical = clinical.rename(columns={"影像号": "patient_id"})
    clinical["patient_id"] = clinical["patient_id"].astype(str).str.strip()
    new_ids = set(ids) - set(_read_csv(PRIMARY_A_IDS, dtype=str)["影像号"].astype(str).str.strip())
    global_frame = _global_frame(
        set(ids) - new_ids if split == "A" else set(), new_ids if split == "A" else set())
    global_frame = global_frame[global_frame["影像号"].astype(str).isin(set(ids))].copy()
    global_frame = global_frame.rename(columns={"影像号": "patient_id"})
    low = _habitat_block(None, set(ids) - new_ids if split == "A" else set(),
                         new_ids if split == "A" else set(), "R_low")
    high = _habitat_block(None, set(ids) - new_ids if split == "A" else set(),
                          new_ids if split == "A" else set(), "R_high")
    whole = _whole_frame(ids)
    frame = clinical.merge(global_frame[["patient_id"] + list(va.GLOBAL_COLUMNS)],
                           on="patient_id", how="left", validate="one_to_one")
    frame = frame.merge(low, on="patient_id", how="left", validate="one_to_one")
    frame = frame.merge(high, on="patient_id", how="left", validate="one_to_one")
    frame = frame.merge(whole, on="patient_id", how="left", validate="one_to_one")
    frame.insert(1, "split", split)
    front = ["patient_id", "split"]
    if include_outcome:
        front += ["DFS_time", "DFS_event"]
    ordered = (front + list(va.CLINICAL_COLUMNS) + list(va.GLOBAL_COLUMNS) +
               ["R_low_structurally_defined", "R_low_technically_available"] +
               ["R_low__" + name for name in va.R_LOW_FEATURE_NAMES] +
               ["R_high_structurally_defined", "R_high_technically_available"] +
               ["R_high__" + name for name in va.R_HIGH_FEATURE_NAMES] +
               ["W_Original_available"] + list(W_FEATURES))
    missing = sorted(set(ordered) - set(frame.columns))
    if missing:
        raise RuntimeError("sensitivity frame missing columns: %s" % missing[:5])
    frame = frame[ordered].copy()
    if len(frame) != len(ids) or frame["patient_id"].nunique() != len(ids):
        raise RuntimeError("sensitivity frame ID coverage is invalid")
    return frame


def _make_extended_split(a_frame):
    frozen = _read_csv(FROZEN_SPLIT, dtype={"patient_id": str})
    existing = frozen[frozen["repeat"].astype(int).eq(1)].copy()
    existing["patient_id"] = existing["patient_id"].astype(str).str.strip()
    primary_ids = set(_read_csv(PRIMARY_A_IDS, dtype=str)["影像号"].astype(str).str.strip())
    if set(existing["patient_id"]) != primary_ids:
        raise RuntimeError("existing repeat-1 split does not equal Primary A393")
    new_ids = sorted(set(a_frame["patient_id"]) - primary_ids)
    extension = a_frame[a_frame["patient_id"].isin(new_ids)].sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)
    events = pd.to_numeric(extension["DFS_event"], errors="coerce").astype(int).to_numpy()
    splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    fold_by_id = {}
    for fold, (_train, valid) in enumerate(splitter.split(extension["patient_id"], events), 1):
        for index in valid:
            fold_by_id[str(extension.iloc[index]["patient_id"])] = fold
    rows = existing[["patient_id", "repeat", "fold", "role", "seed"]].to_dict("records")
    for pid in new_ids:
        validation_fold = fold_by_id[pid]
        for fold in range(1, 6):
            rows.append({"patient_id": pid, "repeat": 1, "fold": fold,
                         "role": "validation" if fold == validation_fold else "train",
                         "seed": SEED})
    split = pd.DataFrame(rows, columns=["patient_id", "repeat", "fold", "role", "seed"])
    split["repeat"] = split["repeat"].astype(int)
    split["fold"] = split["fold"].astype(int)
    split["seed"] = split["seed"].astype(int)
    role_order = {"train": 0, "validation": 1}
    split["_role_order"] = split["role"].map(role_order)
    split = split.sort_values(["fold", "_role_order", "patient_id"],
                              kind="mergesort").drop(columns=["_role_order"])
    split = split.reset_index(drop=True)
    va.validate_split(split, frame=a_frame, production=False)
    return split


def run_t2():
    started = time.perf_counter()
    cohort, primary_ids = _cohort_ids()
    a_ids = set(cohort.loc[cohort["split"].eq("A"), "影像号"])
    a_frame = _build_frame(a_ids, "A", include_outcome=True)
    va.validate_predictor_frame(a_frame, model_ids=list(va.MODEL_SPECS),
                               cohort="A", require_outcome=True)
    split = _make_extended_split(a_frame)
    _write_csv(a_frame, os.path.join(OUTPUT_ROOT, "sensitivity_693_dataset_A.csv"))
    _write_csv(split, os.path.join(OUTPUT_ROOT, "sensitivity_693_outer_split.csv"))
    split_audit = {
        "stage": "T2", "status": "COMPLETE", "A_n": len(a_frame),
        "A_events": int(a_frame["DFS_event"].sum()), "A_censored": int((a_frame["DFS_event"] == 0).sum()),
        "outer_folds": 5, "outer_repeat": 1, "seed": SEED,
        "existing_A393_assignments_preserved": True,
        "new_A_extension_n": int(len(a_frame) - len(primary_ids)),
        "split_sha256": _sha256(os.path.join(OUTPUT_ROOT, "sensitivity_693_outer_split.csv")),
        "frame_sha256": _sha256(os.path.join(OUTPUT_ROOT, "sensitivity_693_dataset_A.csv")),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    _write_json(split_audit, os.path.join(OUTPUT_ROOT, "T2_summary.json"))
    return a_frame, split, split_audit


def _fit_outer_detailed(frame, split, model_id, population):
    checked = va.validate_predictor_frame(frame, [model_id], cohort="A", require_outcome=True)
    checked_split = va.validate_split(split, frame=checked, production=False)
    eligible_ids = set(checked.loc[va.eligibility_mask(checked, population),
                                    "patient_id"].astype(str))
    if not eligible_ids:
        raise RuntimeError("empty eligible A population for %s/%s" % (model_id, population))
    prediction_rows = []
    fold_records = []
    engine = canonical._engine()
    for fold in range(1, 6):
        train, valid = canonical._fold_rows(checked, checked_split, fold, population)
        canonical._require_events(train, "sensitivity outer-training fold %d" % fold)
        canonical._require_events(valid, "sensitivity outer-validation fold %d" % fold)
        fitted = canonical.fit_canonical_model(train, model_id, seed=SEED)
        risk, survival = canonical._survival_predictions(fitted, valid)
        train_time = train["DFS_time"].to_numpy(dtype=float)
        train_event = train["DFS_event"].to_numpy(dtype=int)
        valid_time = valid["DFS_time"].to_numpy(dtype=float)
        valid_event = valid["DFS_event"].to_numpy(dtype=int)
        metrics = engine.evaluate_metrics(
            train_time, train_event, valid_time, valid_event, risk, survival)
        for index, pid in enumerate(valid["patient_id"].astype(str)):
            prediction_rows.append({
                "patient_id": pid, "DFS_time": float(valid_time[index]),
                "DFS_event": int(valid_event[index]), "fold": int(fold),
                "risk_score": float(risk[index]),
                "survival_probability_36": float(survival["3_year"][index]),
                "survival_probability_60": float(survival["5_year"][index]),
            })
        metric_record = {}
        for key, value in metrics.items():
            if key.endswith("_reason"):
                metric_record[key] = str(value)
            else:
                metric_record[key] = (None if not np.isfinite(float(value))
                                      else float(value))
        fold_records.append({
            "fold": int(fold), "n_train": int(len(train)),
            "n_validation": int(len(valid)),
            "train_event_count": int(train_event.sum()),
            "validation_event_count": int(valid_event.sum()),
            "training_id_hash": va.canonical_id_hash(train["patient_id"]),
            "validation_id_hash": va.canonical_id_hash(valid["patient_id"]),
            "selection": fitted["selection"],
            "preprocessing": fitted["preprocessing"],
            "fit_audit": fitted["fit_audit"],
            "metrics": metric_record,
            "outer_validation_used_for_selection": False,
            "outer_validation_used_for_lambda": False,
            "outer_validation_used_for_habitat_fit": False,
        })
    predictions = pd.DataFrame(prediction_rows).sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)
    if set(predictions["patient_id"]) != eligible_ids or predictions["patient_id"].duplicated().any():
        raise RuntimeError("expanded-A validation did not cover the eligible population exactly once")
    return {
        "run_id": None, "model_id": model_id,
        "predictor_blocks": list(va.MODEL_SPECS[model_id]["blocks"]),
        "population": population, "eligible_n": int(len(eligible_ids)),
        "DFS_events": int(predictions["DFS_event"].sum()),
        "prediction_coverage": int(len(predictions)), "folds": fold_records,
        "predictions": predictions,
    }


def _aggregate_metrics(record):
    output = {}
    keys = sorted(set(key for fold in record["folds"] for key in fold["metrics"]
                      if not key.endswith("_reason")))
    for key in keys:
        weighted = []
        for fold in record["folds"]:
            value = fold["metrics"].get(key)
            if value is not None and np.isfinite(float(value)):
                weighted.append((float(value), int(fold["n_validation"])))
        output[key] = (float(sum(value * n for value, n in weighted) /
                         sum(n for _value, n in weighted)) if weighted else None)
    pooled = record["predictions"]
    engine = canonical._engine()
    if len(pooled):
        output["harrell_c_index_pooled"] = float(engine.harrell_c_index(
            pooled["DFS_time"].to_numpy(dtype=float),
            pooled["DFS_event"].to_numpy(dtype=int),
            pooled["risk_score"].to_numpy(dtype=float)))
    return output


def _paired_records(predictions):
    paired = []
    for comparison_id, left_run, right_run, population in va.PAIRED_COMPARISONS:
        if left_run not in predictions or right_run not in predictions:
            continue
        left = predictions[left_run].set_index("patient_id")
        right = predictions[right_run].set_index("patient_id")
        ids = sorted(set(left.index) & set(right.index))
        if not ids:
            continue
        if not left.loc[ids, "fold"].equals(right.loc[ids, "fold"]):
            raise RuntimeError("paired fold assignments differ for %s" % comparison_id)
        paired.append({
            "comparison_id": comparison_id, "left_run": left_run,
            "right_run": right_run, "population": population,
            "common_n": len(ids), "common_id_hash": va.canonical_id_hash(ids),
            "fold_assignments_identical": True,
        })
    return paired


def _fit_full_a(a_frame):
    fitted = OrderedDict()
    freeze_rows = []
    for run in RUNS:
        key = (run["model_id"], run["population"])
        if key not in fitted:
            eligible = va.eligibility_mask(a_frame, run["population"])
            training = a_frame.loc[eligible].sort_values(
                "patient_id", kind="mergesort").reset_index(drop=True)
            fitted[key] = canonical.fit_canonical_model(
                training, run["model_id"], seed=SEED)
        state = fitted[key]
        freeze_rows.append({
            "run_id": run["run_id"], "model_id": run["model_id"],
            "population": run["population"],
            "eligible_n": int(va.eligibility_mask(a_frame, run["population"]).sum()),
            "event_count": int(a_frame.loc[
                va.eligibility_mask(a_frame, run["population"]), "DFS_event"].sum()),
            "selection": state["selection"], "preprocessing": state["preprocessing"],
            "fit_audit": state["fit_audit"],
            "model_input_hash": state["model_input_hash"],
            "transformed_feature_order_sha256": state["feature_order_sha256"],
            "runtime_coefficients_written": False,
            "B_prediction_frozen_before_B_evaluation": True,
        })
    return fitted, freeze_rows


def _build_b_predictors(cohort):
    b_ids = sorted(cohort.loc[cohort["split"].eq("B"), "影像号"].astype(str))
    clinical = _clinical(b_ids, list(va.CLINICAL_COLUMNS)).rename(
        columns={"影像号": "patient_id"})
    clinical["patient_id"] = clinical["patient_id"].astype(str).str.strip()
    technical = _read_csv(B_TECHNICAL, dtype={"patient_id": str})
    technical["patient_id"] = technical["patient_id"].astype(str).str.strip()
    if set(technical["patient_id"]) != set(b_ids) or len(technical) != 163:
        raise RuntimeError("FT05A B technical predictors are not exact B163")
    frame = clinical.merge(technical, on="patient_id", how="left", validate="one_to_one")
    frame["split"] = "B"
    ordered = ([("patient_id"), "split"] + list(va.CLINICAL_COLUMNS) +
               list(va.GLOBAL_COLUMNS) +
               ["R_low_structurally_defined", "R_low_technically_available"] +
               ["R_low__" + name for name in va.R_LOW_FEATURE_NAMES] +
               ["R_high_structurally_defined", "R_high_technically_available"] +
               ["R_high__" + name for name in va.R_HIGH_FEATURE_NAMES] +
               ["W_Original_available"] + list(W_FEATURES))
    missing = sorted(set(ordered) - set(frame.columns))
    if missing:
        raise RuntimeError("B predictor frame missing columns: %s" % missing[:5])
    frame = frame[ordered].copy()
    va.validate_predictor_frame(frame, model_ids=list(va.MODEL_SPECS),
                                cohort="B", require_outcome=False)
    return frame


def _load_b_outcomes(b_ids):
    return _clinical(b_ids, ["DFS_time", "DFS_event"]).rename(
        columns={"影像号": "patient_id"})


def _predict_b(fitted, b_predictors, a_frame, run):
    population = run["population"]
    eligible = va.eligibility_mask(b_predictors, population)
    selected = b_predictors.loc[eligible].sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)
    if selected.empty:
        raise RuntimeError("empty B eligible population for %s" % run["run_id"])
    state = fitted[(run["model_id"], population)]
    risk, survival = canonical._survival_predictions(state, selected)
    return pd.DataFrame({
        "patient_id": selected["patient_id"].astype(str),
        "risk_score": risk,
        "survival_probability_36": survival["3_year"],
        "survival_probability_60": survival["5_year"],
    })


def run_t3(a_frame, split, cohort):
    started = time.perf_counter()
    predictions_a = OrderedDict()
    validation_rows = []
    validation_records = {}
    for run in RUNS:
        print("T3 A %s" % run["run_id"], flush=True)
        record = _fit_outer_detailed(
            a_frame, split, run["model_id"], run["population"])
        record["run_id"] = run["run_id"]
        validation_records[run["run_id"]] = record
        predictions_a[run["run_id"]] = record["predictions"]
        aggregate = _aggregate_metrics(record)
        validation_rows.append({
            "run_id": run["run_id"], "model_id": run["model_id"],
            "population": run["population"], "eligible_n": record["eligible_n"],
            "total_target_n": 530,
            "coverage_percent": 100.0 * record["eligible_n"] / 530.0,
            "event_n": record["DFS_events"],
            "target_event_n": int(a_frame["DFS_event"].sum()),
            "event_coverage_percent": 100.0 * record["DFS_events"] /
            float(a_frame["DFS_event"].sum()),
            **aggregate,
        })
        _write_csv(record["predictions"], os.path.join(
            OUTPUT_ROOT, "T3_A_validation_%s.csv" % run["run_id"]))
    paired = _paired_records(predictions_a)
    _write_csv(pd.DataFrame(validation_rows), os.path.join(
        OUTPUT_ROOT, "T3_A_validation_metrics.csv"))
    _write_csv(pd.DataFrame(paired), os.path.join(
        OUTPUT_ROOT, "T3_A_paired_comparisons.csv"))

    fitted, freeze_rows = _fit_full_a(a_frame)
    _write_json({
        "stage": "T3", "status": "FROZEN_AFTER_EXPANDED_A_VALIDATION",
        "model_order": [run["run_id"] for run in RUNS],
        "models": freeze_rows, "A_data_read": True, "B_predictors_read": False,
        "B_outcomes_read": False, "outer_validation_used_for_refit": False,
        "B_prediction_before_B_evaluation": True,
    }, os.path.join(OUTPUT_ROOT, "T3_model_freeze.json"))

    b_predictors = _build_b_predictors(cohort)
    b_predictions = OrderedDict()
    b_rows = []
    for run in RUNS:
        print("T3 B frozen prediction %s" % run["run_id"], flush=True)
        pred = _predict_b(fitted, b_predictors, a_frame, run)
        b_predictions[run["run_id"]] = pred
        _write_csv(pred, os.path.join(
            OUTPUT_ROOT, "T3_B_frozen_prediction_%s.csv" % run["run_id"]))
    # The B endpoint is loaded only after every expanded-A model has been fitted
    # and the frozen-prediction files have been generated.
    b_outcomes = _load_b_outcomes(b_predictors["patient_id"].astype(str))
    b_eval = b_predictors.merge(b_outcomes, on="patient_id", how="left",
                                validate="one_to_one")
    va.validate_predictor_frame(b_eval, model_ids=list(va.MODEL_SPECS),
                                cohort="B", require_outcome=True)
    engine = canonical._engine()
    for run in RUNS:
        pred = b_predictions[run["run_id"]].sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        selected = b_eval[b_eval["patient_id"].isin(set(pred["patient_id"]))].sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        train = a_frame.loc[va.eligibility_mask(a_frame, run["population"])].sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        risk = pred["risk_score"].to_numpy(dtype=float)
        survival = {
            "3_year": pred["survival_probability_36"].to_numpy(dtype=float),
            "5_year": pred["survival_probability_60"].to_numpy(dtype=float),
        }
        metrics = engine.evaluate_metrics(
            train["DFS_time"].to_numpy(dtype=float),
            train["DFS_event"].to_numpy(dtype=int),
            selected["DFS_time"].to_numpy(dtype=float),
            selected["DFS_event"].to_numpy(dtype=int), risk, survival)
        row = {
            "run_id": run["run_id"], "model_id": run["model_id"],
            "population": run["population"], "eligible_n": len(pred),
            "total_target_n": 163, "coverage_percent": 100.0 * len(pred) / 163.0,
            "event_n": int(selected["DFS_event"].sum()), "target_event_n": 42,
            "event_coverage_percent": 100.0 * float(selected["DFS_event"].sum()) / 42.0,
        }
        row.update({key: (value if key.endswith("_reason") else
                          (None if not np.isfinite(float(value)) else float(value)))
                    for key, value in metrics.items()})
        b_rows.append(row)
    _write_csv(pd.DataFrame(b_rows), os.path.join(
        OUTPUT_ROOT, "T3_B_validation_metrics.csv"))
    summary = {
        "stage": "T3", "status": "COMPLETE", "A_validation_runs": len(RUNS),
        "B_frozen_prediction_runs": len(RUNS), "A_target_n": 530,
        "A_event_n": int(a_frame["DFS_event"].sum()), "B_target_n": 163,
        "B_event_n": 42, "B_outcomes_read_after_A_freeze": True,
        "B_tuning": False, "B_refit": False, "B_feature_selection": False,
        "B_habitat_refit": False, "B_to_A_feedback": False,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    _write_json(summary, os.path.join(OUTPUT_ROOT, "T3_summary.json"))
    return validation_rows, b_rows, summary


def _normalise_prediction_frame(frame, require_fold):
    frame = frame.copy()
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if require_fold:
        frame["fold"] = pd.to_numeric(frame["fold"], errors="raise").astype(int)
    for column in ("risk_score", "survival_probability_36",
                   "survival_probability_60"):
        frame[column] = pd.to_numeric(frame[column], errors="raise").astype(float)
    if frame["patient_id"].duplicated().any():
        raise RuntimeError("prediction identifiers are not unique")
    return frame


def _a_comparison_prediction(a_frame, split, model_id, population, cache):
    key = (model_id, population)
    if key in cache:
        return cache[key]
    for run in RUNS:
        if run["model_id"] == model_id and run["population"] == population:
            path = os.path.join(OUTPUT_ROOT, "T3_A_validation_%s.csv" % run["run_id"])
            if not os.path.exists(path):
                raise RuntimeError("missing A validation output: %s" % path)
            prediction = _normalise_prediction_frame(
                _read_csv(path, dtype={"patient_id": str}), require_fold=True)
            cache[key] = (prediction, run["run_id"], population)
            return cache[key]
    # The comparison-only M0 fits are required by the common-population rule.
    record = _fit_outer_detailed(a_frame, split, model_id, population)
    cache[key] = (
        record["predictions"], "%s_common_%s" % (model_id, population), population)
    return cache[key]


def _b_frozen_source(model_id, population):
    for run in RUNS:
        if run["model_id"] == model_id and run["population"] == population:
            return run
    # M0 does not need radiomics, so its expanded-A main freeze is valid for
    # the common B subset used by comparisons against habitat models.
    if model_id == "M0":
        for run in RUNS:
            if run["model_id"] == "M0" and run["population"] == "main":
                return run
    raise RuntimeError("no frozen B source for %s/%s" % (model_id, population))


def _b_comparison_prediction(model_id, population, cache):
    source = _b_frozen_source(model_id, population)
    run_id = source["run_id"]
    if run_id not in cache:
        path = os.path.join(OUTPUT_ROOT, "T3_B_frozen_prediction_%s.csv" % run_id)
        if not os.path.exists(path):
            raise RuntimeError("missing B frozen prediction output: %s" % path)
        cache[run_id] = _normalise_prediction_frame(
            _read_csv(path, dtype={"patient_id": str}), require_fold=False)
    return cache[run_id], run_id, source["population"]


def _weighted_metric_summary(metric_rows, pooled_predictions):
    summary = {}
    for metric in ("uno_c_index", "3_year_auc", "3_year_brier",
                   "5_year_auc", "5_year_brier"):
        values = [(row[metric], row["n_validation"])
                  for row in metric_rows
                  if row.get(metric) is not None and
                  np.isfinite(float(row[metric]))]
        summary[metric] = (float(sum(value * n for value, n in values) /
                           sum(n for _value, n in values)) if values else None)
    engine = canonical._engine()
    summary["harrell_c_index_pooled"] = float(engine.harrell_c_index(
        pooled_predictions["DFS_time"].to_numpy(dtype=float),
        pooled_predictions["DFS_event"].to_numpy(dtype=int),
        pooled_predictions["risk_score"].to_numpy(dtype=float)))
    return summary


def _a_common_metric_summary(prediction, a_frame, split, population, common_ids):
    common_ids = set(str(value) for value in common_ids)
    prediction = prediction[prediction["patient_id"].isin(common_ids)].copy()
    metric_rows = []
    engine = canonical._engine()
    for fold in range(1, 6):
        train, valid = canonical._fold_rows(a_frame, split, fold, population)
        valid = valid[valid["patient_id"].astype(str).isin(common_ids)].copy()
        fold_prediction = prediction[prediction["fold"].eq(fold)].copy()
        fold_prediction = fold_prediction.sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        valid = valid.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
        if set(fold_prediction["patient_id"]) != set(valid["patient_id"].astype(str)):
            raise RuntimeError("common A validation coverage mismatch for %s" % population)
        metrics = engine.evaluate_metrics(
            train["DFS_time"].to_numpy(dtype=float),
            train["DFS_event"].to_numpy(dtype=int),
            valid["DFS_time"].to_numpy(dtype=float),
            valid["DFS_event"].to_numpy(dtype=int),
            fold_prediction["risk_score"].to_numpy(dtype=float),
            {"3_year": fold_prediction["survival_probability_36"].to_numpy(dtype=float),
             "5_year": fold_prediction["survival_probability_60"].to_numpy(dtype=float)})
        metric_rows.append({})
        for key, value in metrics.items():
            if key.endswith("_reason"):
                continue
            metric_rows[-1][key] = (
                None if value is None or not np.isfinite(float(value))
                else float(value))
        metric_rows[-1]["n_validation"] = int(len(valid))
    pooled = prediction.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
    return _weighted_metric_summary(metric_rows, pooled)


def _b_common_metric_summary(prediction, b_eval, a_frame, train_population, common_ids):
    common_ids = set(str(value) for value in common_ids)
    selected = prediction[prediction["patient_id"].isin(common_ids)].copy()
    selected = selected.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
    outcomes = b_eval[["patient_id", "DFS_time", "DFS_event"]].copy()
    outcomes["patient_id"] = outcomes["patient_id"].astype(str)
    selected = selected.merge(outcomes, on="patient_id", how="left", validate="one_to_one")
    if selected[["DFS_time", "DFS_event"]].isna().any().any():
        raise RuntimeError("common B outcome coverage mismatch")
    train = a_frame.loc[va.eligibility_mask(a_frame, train_population)].copy()
    engine = canonical._engine()
    metrics = engine.evaluate_metrics(
        train["DFS_time"].to_numpy(dtype=float),
        train["DFS_event"].to_numpy(dtype=int),
        selected["DFS_time"].to_numpy(dtype=float),
        selected["DFS_event"].to_numpy(dtype=int),
        selected["risk_score"].to_numpy(dtype=float),
        {"3_year": selected["survival_probability_36"].to_numpy(dtype=float),
         "5_year": selected["survival_probability_60"].to_numpy(dtype=float)})
    summary = {}
    for key in COMPARISON_METRICS:
        raw_key = "harrell_c_index" if key == "harrell_c_index_pooled" else key
        value = metrics.get(raw_key)
        summary[key] = None if value is None or not np.isfinite(float(value)) else float(value)
    return summary


def _run_common_population_comparisons(a_frame, split, cohort):
    a_cache = {}
    b_cache = {}
    b_predictors = _build_b_predictors(cohort)
    b_outcomes = _load_b_outcomes(b_predictors["patient_id"].astype(str))
    b_eval = b_predictors.merge(b_outcomes, on="patient_id", how="left",
                                validate="one_to_one")
    va.validate_predictor_frame(b_eval, model_ids=list(va.MODEL_SPECS),
                                cohort="B", require_outcome=True)
    metric_rows = []
    coverage_rows = []
    for definition in COMPARISON_DEFINITIONS:
        comparison_id = definition["comparison_id"]
        population = definition["population"]
        left_a, left_a_source, left_a_population = _a_comparison_prediction(
            a_frame, split, definition["left_model"], population, a_cache)
        right_a, right_a_source, right_a_population = _a_comparison_prediction(
            a_frame, split, definition["right_model"], population, a_cache)
        a_expected = set(a_frame.loc[
            va.eligibility_mask(a_frame, population), "patient_id"].astype(str))
        left_a_ids = set(left_a["patient_id"])
        right_a_ids = set(right_a["patient_id"])
        if left_a_ids != a_expected or right_a_ids != a_expected:
            raise RuntimeError("common A population mismatch for %s" % comparison_id)
        left_folds = dict(zip(left_a["patient_id"], left_a["fold"].astype(int)))
        right_folds = dict(zip(right_a["patient_id"], right_a["fold"].astype(int)))
        if left_folds != right_folds:
            raise RuntimeError("common A fold assignments differ for %s" % comparison_id)
        a_left_metrics = _a_common_metric_summary(
            left_a, a_frame, split, population, a_expected)
        a_right_metrics = _a_common_metric_summary(
            right_a, a_frame, split, population, a_expected)
        for metric in COMPARISON_METRICS:
            left_value = a_left_metrics.get(metric)
            right_value = a_right_metrics.get(metric)
            metric_rows.append({
                "analysis_side": "A", "comparison_id": comparison_id,
                "comparison_group": definition["group"],
                "left_model": definition["left_model"],
                "right_model": definition["right_model"],
                "common_population": population,
                "common_n": len(a_expected),
                "common_event_n": int(a_frame.loc[
                    a_frame["patient_id"].isin(a_expected), "DFS_event"].sum()),
                "metric": metric, "left_estimate": left_value,
                "right_estimate": right_value,
                "delta_right_minus_left": (None if left_value is None or right_value is None
                                            else right_value - left_value),
                "left_source_run": left_a_source, "right_source_run": right_a_source,
                "left_training_population": left_a_population,
                "right_training_population": right_a_population,
                "fold_assignments_identical": True,
                "common_population_rule": True,
            })
        coverage_rows.append({
            "analysis_side": "A", "comparison_id": comparison_id,
            "comparison_group": definition["group"],
            "left_model": definition["left_model"], "right_model": definition["right_model"],
            "common_population": population, "left_eligible_n": len(left_a_ids),
            "right_eligible_n": len(right_a_ids), "common_eligible_n": len(a_expected),
            "total_target_n": 530, "coverage_percent": 100.0 * len(a_expected) / 530.0,
            "common_event_n": int(a_frame.loc[
                a_frame["patient_id"].isin(a_expected), "DFS_event"].sum()),
            "target_event_n": int(a_frame["DFS_event"].sum()),
            "event_coverage_percent": 100.0 * float(a_frame.loc[
                a_frame["patient_id"].isin(a_expected), "DFS_event"].sum()) /
            float(a_frame["DFS_event"].sum()),
            "fold_assignments_identical": True,
            "common_population_rule": True,
        })

        left_b, left_b_source, left_b_population = _b_comparison_prediction(
            definition["left_model"], population, b_cache)
        right_b, right_b_source, right_b_population = _b_comparison_prediction(
            definition["right_model"], population, b_cache)
        b_expected = set(b_eval.loc[
            va.eligibility_mask(b_eval, population), "patient_id"].astype(str))
        left_b_ids = set(left_b["patient_id"])
        right_b_ids = set(right_b["patient_id"])
        common_b = left_b_ids & right_b_ids
        if common_b != b_expected:
            raise RuntimeError("common B population mismatch for %s" % comparison_id)
        b_left_metrics = _b_common_metric_summary(
            left_b, b_eval, a_frame, left_b_population, common_b)
        b_right_metrics = _b_common_metric_summary(
            right_b, b_eval, a_frame, right_b_population, common_b)
        for metric in COMPARISON_METRICS:
            left_value = b_left_metrics.get(metric)
            right_value = b_right_metrics.get(metric)
            metric_rows.append({
                "analysis_side": "B", "comparison_id": comparison_id,
                "comparison_group": definition["group"],
                "left_model": definition["left_model"],
                "right_model": definition["right_model"],
                "common_population": population,
                "common_n": len(common_b),
                "common_event_n": int(b_eval.loc[
                    b_eval["patient_id"].isin(common_b), "DFS_event"].sum()),
                "metric": metric, "left_estimate": left_value,
                "right_estimate": right_value,
                "delta_right_minus_left": (None if left_value is None or right_value is None
                                            else right_value - left_value),
                "left_source_run": left_b_source, "right_source_run": right_b_source,
                "left_training_population": left_b_population,
                "right_training_population": right_b_population,
                "fold_assignments_identical": "not_applicable_external",
                "common_population_rule": True,
            })
        coverage_rows.append({
            "analysis_side": "B", "comparison_id": comparison_id,
            "comparison_group": definition["group"],
            "left_model": definition["left_model"], "right_model": definition["right_model"],
            "common_population": population, "left_eligible_n": len(left_b_ids),
            "right_eligible_n": len(right_b_ids), "common_eligible_n": len(common_b),
            "total_target_n": 163, "coverage_percent": 100.0 * len(common_b) / 163.0,
            "common_event_n": int(b_eval.loc[
                b_eval["patient_id"].isin(common_b), "DFS_event"].sum()),
            "target_event_n": 42,
            "event_coverage_percent": 100.0 * float(b_eval.loc[
                b_eval["patient_id"].isin(common_b), "DFS_event"].sum()) / 42.0,
            "fold_assignments_identical": "not_applicable_external",
            "common_population_rule": True,
        })
    comparison = pd.DataFrame(metric_rows)
    coverage = pd.DataFrame(coverage_rows)
    _write_csv(comparison, os.path.join(
        OUTPUT_ROOT, "T4_common_population_comparisons.csv"))
    _write_csv(coverage, os.path.join(
        OUTPUT_ROOT, "T4_common_population_eligibility.csv"))

    lines = [
        "# T4 模型比较框架：共同可分析人群",
        "",
        "按任务书第十、十一节完成12组预设模型比较；每组均在共同可分析人群中计算。",
        "A侧对比较所需的模型在人群限定后重新进行5-fold validation；B侧保持A冻结模型，仅在共同B人群中进行外部评价。",
        "",
    ]
    for side in ("A", "B"):
        lines += ["## %s侧" % side, ""]
        side_frame = comparison[comparison["analysis_side"].eq(side)]
        for definition in COMPARISON_DEFINITIONS:
            current = side_frame[side_frame["comparison_id"].eq(
                definition["comparison_id"])]
            if current.empty:
                continue
            first = current.iloc[0]
            parts = []
            for metric in COMPARISON_METRICS:
                row = current[current["metric"].eq(metric)].iloc[0]
                left_value = row["left_estimate"]
                right_value = row["right_estimate"]
                delta = row["delta_right_minus_left"]
                parts.append("%s %.4f→%.4f (Δ%+.4f)" % (
                    metric, float(left_value), float(right_value), float(delta)))
            lines.append("- %s [%s, n=%d, events=%d]: %s" % (
                first["comparison_id"], first["common_population"],
                int(first["common_n"]), int(first["common_event_n"]),
                "; ".join(parts)))
        lines.append("")
    lines += [
        "## 解释规则",
        "",
        "Harrell C、Uno C和AUC的正Δ表示右侧模型数值更高；Brier的负Δ表示右侧模型数值更优。",
        "共同人群的样本数、事件数和覆盖度详见 `T4_common_population_eligibility.csv`；逐指标结果详见 `T4_common_population_comparisons.csv`。",
        "",
    ]
    with open(os.path.join(OUTPUT_ROOT, "T4_model_comparison_summary.md.tmp"),
              "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    os.replace(os.path.join(OUTPUT_ROOT, "T4_model_comparison_summary.md.tmp"),
               os.path.join(OUTPUT_ROOT, "T4_model_comparison_summary.md"))
    return {"metric_rows": len(comparison), "coverage_rows": len(coverage),
            "comparison_groups": len(COMPARISON_DEFINITIONS)}


def _primary_metric(path, model_id, metric):
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    value = payload["models"][model_id].get("metrics", {}).get(metric, {})
    if isinstance(value, dict):
        value = value.get("estimate")
    return None if value is None else float(value)


def run_t4(cohort, a_frame, split):
    started = time.perf_counter()
    a = _read_csv(os.path.join(OUTPUT_ROOT, "T3_A_validation_metrics.csv"))
    b = _read_csv(os.path.join(OUTPUT_ROOT, "T3_B_validation_metrics.csv"))
    metrics = ["harrell_c_index_pooled", "uno_c_index", "3_year_auc",
               "3_year_brier", "5_year_auc", "5_year_brier"]
    primary_metric_names = {
        "harrell_c_index_pooled": "Harrell_C_index", "uno_c_index": "Uno_C_index",
        "3_year_auc": "AUC_3_year", "3_year_brier": "Brier_3_year",
        "5_year_auc": "AUC_5_year", "5_year_brier": "Brier_5_year",
    }
    rows = []
    for side, frame, primary_path in (("A", a, PRIMARY_A_FT03),
                                      ("B", b, PRIMARY_B_FT06)):
        for model_id in ("M0", "M1", "M2", "M3L", "M3H", "M4", "M5"):
            current = frame[frame["run_id"].eq(model_id)]
            if current.empty:
                continue
            current = current.iloc[0]
            for metric in metrics:
                sensitivity_column = ("harrell_c_index" if side == "B" and
                                      metric == "harrell_c_index_pooled" else metric)
                sensitivity = pd.to_numeric(pd.Series([current.get(sensitivity_column)]),
                                             errors="coerce").iloc[0]
                primary = _primary_metric(primary_path, model_id,
                                          primary_metric_names[metric])
                rows.append({
                    "analysis_side": side, "model_id": model_id,
                    "metric": metric, "primary_v2_estimate": primary,
                    "sensitivity_693_estimate": (None if pd.isna(sensitivity)
                                                  else float(sensitivity)),
                    "delta_sensitivity_minus_primary": (
                        None if primary is None or pd.isna(sensitivity)
                        else float(sensitivity) - primary),
                    "primary_v2_source": os.path.relpath(primary_path, PROJECT_ROOT).replace(os.sep, "/"),
                    "comparison_population": "A393_vs_A530" if side == "A" else "B163_vs_B163",
                })
    comparison = pd.DataFrame(rows)
    _write_csv(comparison, os.path.join(
        OUTPUT_ROOT, "T4_primary_vs_sensitivity_comparison.csv"))
    common_summary = _run_common_population_comparisons(a_frame, split, cohort)

    coverage_rows = []
    for frame, side, total, event_total in ((a, "A", 530, int(_read_csv(
            os.path.join(OUTPUT_ROOT, "sensitivity_693_dataset_A.csv"))["DFS_event"].sum())),
                                            (b, "B", 163, 42)):
        for _, row in frame.iterrows():
            coverage_rows.append({
                "analysis_side": side, "run_id": row["run_id"],
                "eligible_n": int(row["eligible_n"]), "total_target_n": total,
                "coverage_percent": float(row["coverage_percent"]),
                "event_n": int(row["event_n"]), "target_event_n": event_total,
                "event_coverage_percent": float(row["event_coverage_percent"]),
            })
    _write_csv(pd.DataFrame(coverage_rows), os.path.join(
        OUTPUT_ROOT, "T4_coverage.csv"))
    lines = ["# T4 Primary v2 vs 693例无准入门槛 DFS 敏感性分析", "",
             "- 目标队列：A=530、B=163，总计693例；仅移除高信号准入门槛。",
             "- Primary v2 A393 的既有折叠与冻结资产保持不变；A 扩展病例使用 seed=12345 按 DFS_event 分层确定性补充分折。",
             "- A 侧使用 expanded-A 5-fold validation 和 full-A refit；B 侧仅使用 A 冻结模型进行预测后评价。", ""]
    for side in ("A", "B"):
        lines += ["## %s 侧结果" % side, ""]
        current = comparison[comparison["analysis_side"].eq(side)]
        for model_id in ("M0", "M1", "M2", "M3L", "M3H", "M4", "M5"):
            values = current[current["model_id"].eq(model_id)]
            if values.empty:
                continue
            text = [model_id]
            for _, value in values.iterrows():
                s = value["sensitivity_693_estimate"]
                p = value["primary_v2_estimate"]
                if pd.isna(s) or pd.isna(p):
                    text.append("%s=NA" % value["metric"])
                else:
                    text.append("%s=%.4f (Δ%.4f)" % (
                        value["metric"], float(s),
                        float(value["delta_sensitivity_minus_primary"])))
            lines.append("- " + "; ".join(text))
        lines.append("")
    lines += ["## 覆盖度", "", "详见 `T4_coverage.csv`；每个模型均同时报告 eligible_n、总目标数、覆盖率、事件数和事件覆盖率。", "",
              "## 共同人群模型比较", "",
              "已完成任务书第十节规定的12组模型比较；每组均使用共同可分析人群。详见 `T4_model_comparison_summary.md`、`T4_common_population_comparisons.csv` 和 `T4_common_population_eligibility.csv`。", ""]
    _write_json({
        "stage": "T4", "status": "COMPLETE", "target_n": 693,
        "A_n": 530, "B_n": 163, "comparison_metrics": metrics,
        "common_population_comparison_groups": common_summary["comparison_groups"],
        "common_population_comparison_metric_rows": common_summary["metric_rows"],
        "common_population_comparison_coverage_rows": common_summary["coverage_rows"],
        "common_population_rule": True,
        "primary_v2_unchanged": True,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }, os.path.join(OUTPUT_ROOT, "T4_summary.json"))
    with open(os.path.join(OUTPUT_ROOT, "T4_summary.md.tmp"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    os.replace(os.path.join(OUTPUT_ROOT, "T4_summary.md.tmp"),
               os.path.join(OUTPUT_ROOT, "T4_summary.md"))
    return comparison


def run_finalize():
    """Write the final workflow index after T1--T4 have completed."""
    required = ["T1_summary.json", "T2_summary.json", "T3_summary.json",
                "T4_summary.json", "T3_model_freeze.json",
                "T3_A_validation_metrics.csv", "T3_B_validation_metrics.csv",
                "T4_primary_vs_sensitivity_comparison.csv", "T4_coverage.csv",
                "T4_common_population_comparisons.csv",
                "T4_common_population_eligibility.csv",
                "T4_model_comparison_summary.md"]
    missing = [name for name in required
               if not os.path.exists(os.path.join(OUTPUT_ROOT, name))]
    if missing:
        raise RuntimeError("cannot finalize; missing outputs: %s" % missing)
    with open(os.path.join(OUTPUT_ROOT, "T1_summary.json"), encoding="utf-8") as handle:
        t1 = json.load(handle)
    with open(os.path.join(OUTPUT_ROOT, "T2_summary.json"), encoding="utf-8") as handle:
        t2 = json.load(handle)
    with open(os.path.join(OUTPUT_ROOT, "T3_summary.json"), encoding="utf-8") as handle:
        t3 = json.load(handle)
    with open(os.path.join(OUTPUT_ROOT, "T4_summary.json"), encoding="utf-8") as handle:
        t4 = json.load(handle)
    comparison = _read_csv(os.path.join(
        OUTPUT_ROOT, "T4_primary_vs_sensitivity_comparison.csv"))
    common_comparison = _read_csv(os.path.join(
        OUTPUT_ROOT, "T4_common_population_comparisons.csv"))
    common_coverage = _read_csv(os.path.join(
        OUTPUT_ROOT, "T4_common_population_eligibility.csv"))
    final = {
        "workflow": "T1->T2->T3->T4", "status": "COMPLETE",
        "target_n": 693, "A_n": 530, "B_n": 163,
        "threshold_free": True, "primary_v2_modified": False,
        "reviewer_model_requested": "luna",
        "reviewer_reasoning_effort": "xhigh",
        "T1": t1, "T2": t2, "T3": t3, "T4": t4,
        "T4_comparison_rows": int(len(comparison)),
        "T4_common_comparison_groups": int(common_coverage["comparison_id"].nunique()),
        "T4_common_comparison_metric_rows": int(len(common_comparison)),
        "T4_common_comparison_coverage_rows": int(len(common_coverage)),
        "output_root": os.path.relpath(OUTPUT_ROOT, PROJECT_ROOT).replace(os.sep, "/"),
    }
    _write_json(final, os.path.join(OUTPUT_ROOT,
                                    "sensitivity_693_workflow_summary.json"))
    return final


def run_all():
    started = time.perf_counter()
    _ensure_dirs()
    t1 = run_t1()
    a_frame, split, t2 = run_t2()
    cohort, _primary = _cohort_ids()
    _a, _b, t3 = run_t3(a_frame, split, cohort)
    comparison = run_t4(cohort, a_frame, split)
    final = {
        "workflow": "T1->T2->T3->T4", "status": "COMPLETE",
        "target_n": 693, "A_n": 530, "B_n": 163,
        "threshold_free": True, "primary_v2_modified": False,
        "reviewer_model_requested": "luna", "reviewer_reasoning_effort": "xhigh",
        "T1": t1, "T2": t2, "T3": t3,
        "T4_comparison_rows": int(len(comparison)),
        "T4_common_comparison_groups": len(COMPARISON_DEFINITIONS),
        "T4_common_comparison_metric_rows": len(COMPARISON_DEFINITIONS) * 2 * len(COMPARISON_METRICS),
        "T4_common_comparison_coverage_rows": len(COMPARISON_DEFINITIONS) * 2,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    _write_json(final, os.path.join(OUTPUT_ROOT, "sensitivity_693_workflow_summary.json"))
    print("T workflow complete: A=530 B=163 output=%s" % OUTPUT_ROOT, flush=True)
    return 0


def run_compare():
    """Rebuild only the in-memory A frame and rerun the complete T4 comparison."""
    _ensure_dirs()
    cohort, _primary = _cohort_ids()
    a_ids = set(cohort.loc[cohort["split"].eq("A"), "影像号"])
    a_frame = _build_frame(a_ids, "A", include_outcome=True)
    va.validate_predictor_frame(a_frame, model_ids=list(va.MODEL_SPECS),
                               cohort="A", require_outcome=True)
    split = _make_extended_split(a_frame)
    comparison = run_t4(cohort, a_frame, split)
    final = run_finalize()
    print("T4 comparison complete: groups=%d metric_rows=%d output=%s" % (
        final["T4_common_comparison_groups"],
        final["T4_common_comparison_metric_rows"], OUTPUT_ROOT), flush=True)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="T1-T4 threshold-free 693-case DFS sensitivity workflow")
    parser.add_argument("--all", action="store_true", help="run T1 through T4 serially")
    parser.add_argument("--compare", action="store_true",
                        help="rerun T4 model comparisons from completed T1-T3 outputs")
    parser.add_argument("--finalize", action="store_true",
                        help="write the final index from completed T1--T4 outputs")
    args = parser.parse_args(argv)
    if sum(bool(value) for value in (args.all, args.compare, args.finalize)) > 1:
        parser.error("choose only one of --all, --compare or --finalize")
    if args.finalize:
        run_finalize()
        return 0
    if args.all:
        return run_all()
    if args.compare:
        return run_compare()
    parser.error("use --all, --compare or --finalize")


if __name__ == "__main__":
    raise SystemExit(main())
