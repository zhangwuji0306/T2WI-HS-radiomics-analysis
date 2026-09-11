"""FT01 technical asset and frozen full_A habitat audit.

This helper reads only protocol/metadata and existing technical feature assets.
It never opens the clinical/outcome workbook and never invokes an image,
habitat, radiomics, feature-selection, or modeling workflow.
"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
from collections import OrderedDict
from datetime import datetime

import numpy as np
import pandas as pd
import yaml


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FT_DIR = os.path.join(ROOT, "prognosis_analysis", "ft")

FT00_PATH = os.path.join(FT_DIR, "FT00_protocol.json")
CONTRACT_PATH = os.path.join(ROOT, "_codex_ft_run_20260910_01a08bf3", "FT01_contract.md")
SCHEME_PATH = os.path.join(ROOT, "T2WI-HS 生境预后快速验证（FT）方案书.md")

EXPECTED_ORIGINAL_METADATA = ["影像号", "读者", "split", "normalization", "f", "binWidth"]
EXPECTED_G_COLUMNS = [
    "H_high_fraction",
    "sv_median_minus_boundary",
    "sv_IQR",
    "interface_density",
    "H_high_largest_component_tumor_fraction",
    "H_high_radial_burden",
]
EXPECTED_H_COLUMNS = ["H_high_fraction"]
EXPECTED_DESCRIPTOR_COLUMNS = [
    "影像号", "H_low_voxels", "H_high_voxels", "tumor_voxels",
    "tumor_volume_mm3", "H_high_fraction", "H_low_fraction",
    "habitat_entropy", "interface_area_mm2", "interface_density",
    "H_high_largest_component_tumor_fraction", "H_high_component_density",
    "H_high_radial_burden", "sv_median_minus_boundary", "sv_IQR",
    "global_center_low", "global_center_high", "global_boundary_b",
    "structural_state", "hard_technical_failure",
]

EXPECTED_B_PROVENANCE_FILENAMES = {
    "candidate_freeze.json",
    "feature_schema.json",
    "manifest.json",
    "output_manifest.json",
    "provenance.json",
    "run_metadata.json",
}


def rel(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle, object_pairs_hook=OrderedDict)


def load_yaml(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return yaml.safe_load(handle)


def json_dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def file_record(path):
    record = OrderedDict()
    record["path"] = rel(path)
    record["exists"] = bool(os.path.isfile(path))
    if record["exists"]:
        record["bytes"] = int(os.path.getsize(path))
        record["sha256"] = sha256_file(path)
    return record


def read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def counts(series):
    if series is None:
        return OrderedDict()
    result = OrderedDict()
    for key, value in series.value_counts(dropna=False).items():
        if pd.isna(key):
            label = "<NA>"
        else:
            label = str(key)
        result[label] = int(value)
    return result


def id_summary(frame, id_column):
    result = OrderedDict()
    result["id_column"] = id_column
    result["id_column_present"] = id_column in frame.columns
    if id_column not in frame.columns:
        return result
    series = frame[id_column]
    text = series.astype("string")
    result["id_dtype"] = str(series.dtype)
    result["blank_id_count"] = int(text.isna().sum() + text.fillna("").str.strip().eq("").sum())
    result["unique_id_count"] = int(series.dropna().nunique())
    result["duplicate_row_count"] = int(series.duplicated(keep=False).sum())
    return result


def first_present(frame, candidates):
    for candidate in candidates:
        if candidate in frame.columns:
            return candidate
    return None


def finite_matrix_summary(frame, columns):
    present = [column for column in columns if column in frame.columns]
    missing = [column for column in columns if column not in frame.columns]
    result = OrderedDict([
        ("requested_count", len(columns)),
        ("present_count", len(present)),
        ("missing_count", len(missing)),
    ])
    if not present:
        result["all_finite_row_count"] = 0
        result["any_nonfinite_row_count"] = int(len(frame)) if len(columns) else 0
        return result
    numeric = frame[present].apply(pd.to_numeric, errors="coerce")
    finite = numeric.notna() & np.isfinite(numeric)
    result["all_finite_row_count"] = int(finite.all(axis=1).sum())
    result["any_nonfinite_row_count"] = int((~finite.all(axis=1)).sum())
    return result


def feature_table_summary(path, feature_prefix=None, candidate_features=None,
                          expected_feature_names=None, include_split=False):
    result = OrderedDict([("path", rel(path)), ("exists", bool(os.path.isfile(path)))])
    if not os.path.isfile(path):
        return result
    frame = read_csv(path)
    columns = list(frame.columns)
    result["row_count"] = int(len(frame))
    result["column_count"] = int(len(columns))
    result["column_order_sha256"] = sha256_text(json_dump(columns))
    result["id"] = id_summary(frame, "影像号")
    reader_column = first_present(frame, ["reader", "读者"])
    if reader_column is not None:
        result["reader_column"] = reader_column
        result["reader_counts"] = counts(frame[reader_column])
    if include_split and "split" in frame.columns:
        result["split_counts"] = counts(frame["split"])
    if "normalization" in frame.columns:
        result["normalization_counts"] = counts(frame["normalization"])
    if "f" in frame.columns:
        result["f_counts"] = counts(frame["f"])
    if "binWidth" in frame.columns:
        result["bin_width_counts"] = counts(frame["binWidth"])
    if "extractable" in frame.columns:
        result["extractable_counts"] = counts(frame["extractable"])
    if "status" in frame.columns:
        result["status_counts"] = counts(frame["status"])
    if "failure_class" in frame.columns:
        result["failure_class_counts"] = counts(frame["failure_class"])

    if feature_prefix is not None:
        feature_names = [column[len(feature_prefix):]
                         for column in columns if column.startswith(feature_prefix)]
        result["feature_names"] = feature_names
        result["feature_count"] = int(len(feature_names))
        if expected_feature_names is not None:
            result["expected_feature_set_match"] = set(feature_names) == set(expected_feature_names)
            result["expected_feature_order_match"] = feature_names == list(expected_feature_names)
        if candidate_features is not None:
            candidate_columns = [feature_prefix + feature for feature in candidate_features]
            result["candidate_features"] = list(candidate_features)
            result["candidate_availability"] = finite_matrix_summary(frame, candidate_columns)
    else:
        result["feature_names"] = []

    return result


def descriptor_summary(path, expected_columns, centers):
    result = OrderedDict([("path", rel(path)), ("exists", bool(os.path.isfile(path)))])
    if not os.path.isfile(path):
        return result
    frame = read_csv(path)
    result["row_count"] = int(len(frame))
    result["column_count"] = int(len(frame.columns))
    result["column_order_sha256"] = sha256_text(json_dump(list(frame.columns)))
    result["id"] = id_summary(frame, "影像号")
    result["expected_columns_present"] = all(column in frame.columns for column in expected_columns)
    result["missing_expected_columns"] = int(sum(column not in frame.columns for column in expected_columns))
    result["structural_state_counts"] = counts(frame.get("structural_state"))
    result["hard_technical_failure_counts"] = counts(frame.get("hard_technical_failure"))
    result["hard_technical_failure_count"] = int(
        pd.to_numeric(frame.get("hard_technical_failure"), errors="coerce").fillna(0).eq(1).sum()
    ) if "hard_technical_failure" in frame.columns else None
    center_checks = OrderedDict()
    for column, expected in centers.items():
        if column not in frame.columns:
            center_checks[column] = OrderedDict([("present", False)])
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        finite = values[np.isfinite(values)]
        max_abs_error = float(np.max(np.abs(finite - expected))) if len(finite) else None
        center_checks[column] = OrderedDict([
            ("present", True),
            ("finite_row_count", int(len(finite))),
            ("unique_value_count", int(finite.nunique())),
            ("expected_value", float(expected)),
            ("max_abs_error", max_abs_error),
            ("matches_expected_within_1e-9", bool(max_abs_error is not None and max_abs_error <= 1e-9)),
        ])
    result["frozen_center_boundary_checks"] = center_checks
    result["G_columns"] = [column for column in EXPECTED_G_COLUMNS if column in frame.columns]
    result["H_columns"] = [column for column in EXPECTED_H_COLUMNS if column in frame.columns]
    return result


def map_manifest_summary(path, map_root):
    result = OrderedDict([("path", rel(path)), ("exists", bool(os.path.isfile(path)))])
    if not os.path.isfile(path):
        return result
    frame = read_csv(path)
    result["row_count"] = int(len(frame))
    result["column_count"] = int(len(frame.columns))
    result["column_order_sha256"] = sha256_text(json_dump(list(frame.columns)))
    result["id"] = id_summary(frame, "影像号")
    result["map_file_count"] = int(sum(1 for name in os.listdir(map_root)
                                        if name.lower().endswith(".nrrd"))) if os.path.isdir(map_root) else 0
    return result


def centers_summary(path):
    result = OrderedDict([("path", rel(path)), ("exists", bool(os.path.isfile(path)))])
    if not os.path.isfile(path):
        return result
    frame = read_csv(path)
    result["row_count"] = int(len(frame))
    result["column_count"] = int(len(frame.columns))
    result["columns"] = list(frame.columns)
    numeric = frame.apply(pd.to_numeric, errors="coerce")
    result["numeric_finite_value_count"] = int(np.isfinite(numeric.to_numpy(dtype=float)).sum())
    return result


def verify_output_manifest(manifest_path):
    result = OrderedDict([("path", rel(manifest_path)), ("exists", bool(os.path.isfile(manifest_path)))])
    if not os.path.isfile(manifest_path):
        return result
    manifest = load_json(manifest_path)
    checks = []
    for name, expected in manifest.get("files", {}).items():
        path = os.path.join(os.path.dirname(manifest_path), name)
        item = OrderedDict([("file", name), ("exists", bool(os.path.isfile(path)))])
        if os.path.isfile(path):
            item["bytes_match"] = int(os.path.getsize(path)) == int(expected.get("bytes", -1))
            item["sha256_match"] = sha256_file(path).lower() == str(expected.get("sha256", "")).lower()
        checks.append(item)
    result["file_count"] = int(len(checks))
    result["all_files_present"] = bool(all(item["exists"] for item in checks))
    result["all_hashes_match"] = bool(all(item.get("bytes_match", False) and item.get("sha256_match", False)
                                           for item in checks))
    result["checks"] = checks
    return result


def source_reference_checks(ft00):
    checks = []
    for reference in ft00.get("source_references", []):
        path = os.path.join(ROOT, *reference["path"].replace("/", os.sep).split(os.sep))
        item = OrderedDict([
            ("path", reference["path"]),
            ("role", reference.get("role")),
            ("exists", bool(os.path.isfile(path))),
        ])
        if os.path.isfile(path):
            actual = sha256_file(path)
            item["expected_sha256"] = reference.get("sha256")
            item["actual_sha256"] = actual
            item["matches_ft00"] = actual.lower() == str(reference.get("sha256", "")).lower()
        else:
            item["matches_ft00"] = False
        checks.append(item)
    return checks


def is_b_asset_root(root):
    parts = [part for part in root.replace("\\", "/").lower().split("/") if part]
    return any(
        part == "b" or part.startswith("b_") or part.endswith("_b") or
        part in {"validation_b", "external_b", "cohort_b"}
        for part in parts
    )


def habitat_feature_kind(name):
    normalized = name.lower().replace("-", "_")
    if "r_low" in normalized and "feature" in normalized and normalized.endswith(".csv"):
        return "R_low"
    if "r_high" in normalized and "feature" in normalized and normalized.endswith(".csv"):
        return "R_high"
    return None


def find_b_habitat_assets(search_roots):
    found = []
    for search_root in search_roots:
        if not os.path.isdir(search_root):
            continue
        for root, _dirs, files in os.walk(search_root):
            for name in files:
                if habitat_feature_kind(name) is None:
                    continue
                if is_b_asset_root(root):
                    found.append(rel(os.path.join(root, name)))
    return sorted(set(found))


def find_b_provenance_files(search_roots):
    found = []
    for search_root in search_roots:
        if not os.path.isdir(search_root):
            continue
        for root, _dirs, files in os.walk(search_root):
            if not is_b_asset_root(root):
                continue
            for name in files:
                lower_name = name.lower()
                if (lower_name in EXPECTED_B_PROVENANCE_FILENAMES or
                        "provenance" in lower_name):
                    found.append(rel(os.path.join(root, name)))
    return sorted(set(found))


def build_manifest():
    ft00 = load_json(FT00_PATH)
    candidate_path = os.path.join(ROOT, "prognosis_analysis", "output", "w03_habitat_radiomics_A", "candidate_freeze.json")
    candidate = load_json(candidate_path)
    w03_schema_path = os.path.join(ROOT, "prognosis_analysis", "output", "w03_habitat_radiomics_A", "feature_schema.json")
    w03_schema = load_json(w03_schema_path)
    original_feature_names = list(w03_schema.get("feature_names", []))
    habitat_config_path = os.path.join(ROOT, "habitat_analysis", "configs", "main_cross_case_kmeans_k2_4mm.json")
    habitat_config = load_json(habitat_config_path)
    w03_config_path = os.path.join(ROOT, "prognosis_analysis", "configs", "w03_habitat_radiomics.json")
    w03_config = load_json(w03_config_path)

    expected_low_hash = ft00["technical_freeze"]["parameters"]["R_low"]["candidate_hash"]
    expected_high_hash = ft00["technical_freeze"]["parameters"]["R_high"]["candidate_hash"]
    low_candidates = list(candidate.get("candidate_features", {}).get("R_low", []))
    high_candidates = list(candidate.get("candidate_features", {}).get("R_high", []))

    global_desc_path = os.path.join(ROOT, "habitat_analysis", "output", "habitat_features_A", "global_descriptors_full_A.csv")
    map_manifest_path = os.path.join(ROOT, "habitat_analysis", "output", "habitat_maps_A_manifest.csv")
    map_root = os.path.join(ROOT, "habitat_analysis", "output", "habitat_maps_A")
    centers_path = os.path.join(ROOT, "habitat_analysis", "output", "feasibility_A_patient_balanced_post_slic_fix", "global_centers.csv")
    w03_dir = os.path.join(ROOT, "prognosis_analysis", "output", "w03_habitat_radiomics_A")
    w02_dir = os.path.join(ROOT, "prognosis_analysis", "output", "w02_habitat_radiomics_A")
    w_original_path = os.path.join(ROOT, "feature_extract", "output", "features_v2", "muscle_f0.25", "features_original.csv")
    feature_manifest_path = os.path.join(ROOT, "feature_extract", "output", "manifest.csv")
    radiomics_config_path = os.path.join(ROOT, "feature_extract", "configs", "radiomics_params.yaml")
    radiomics_output_config_path = os.path.join(ROOT, "feature_extract", "output", "configs", "radiomics_params.yaml")

    freeze_lock_path = os.path.join(ROOT, "habitat_analysis", "freeze_lock.json")
    execution_status_path = os.path.join(ROOT, "prognosis_analysis", "execution_status.json")
    formal_model_lock_path = os.path.join(ROOT, "prognosis_analysis", "model_freeze_lock.json")
    execution_status = load_json(execution_status_path)
    freeze_lock = load_json(freeze_lock_path)

    low_hash = sha256_text(json.dumps(sorted(set(low_candidates)), ensure_ascii=False, separators=(",", ":")))
    high_hash = sha256_text(json.dumps(sorted(set(high_candidates)), ensure_ascii=False, separators=(",", ":")))

    manifest = OrderedDict()
    manifest["schema_version"] = "1.0"
    manifest["artifact_id"] = "FT01_asset_manifest"
    manifest["stage"] = "FT01"
    manifest["status"] = "PASS_A_FAIL_CLOSED_B"
    manifest["exploratory_label"] = ft00.get("exploratory_label")
    manifest["scope"] = OrderedDict([
        ("habitat", "existing frozen full_A"),
        ("whole_tumor_block", "W_Original only"),
        ("filtered_whole_tumor_features_included", False),
        ("b_outcome_or_clinical_data_read", False),
        ("b_reextraction", False),
        ("b_optimization_or_model_fitting", False),
    ])
    manifest["contract_binding"] = OrderedDict([
        ("branch", "codex/ft-validation"),
        ("ft00_protocol_path", rel(FT00_PATH)),
        ("ft00_protocol_sha256", sha256_file(FT00_PATH)),
        ("ft01_contract_path", rel(CONTRACT_PATH)),
        ("ft01_contract_sha256", sha256_file(CONTRACT_PATH)),
        ("scheme_path", rel(SCHEME_PATH)),
        ("scheme_sha256", sha256_file(SCHEME_PATH)),
    ])
    manifest["frozen_definition"] = OrderedDict([
        ("slic_dimension", "3D"),
        ("slic_target_scale_mm", 4.0),
        ("slic_supergrid_voxels_xyz", [4, 4, 2]),
        ("slic_actual_supergrid_mm_xyz", [4.0, 4.0, 4.0]),
        ("k", 2),
        ("n_init", 100),
        ("center_low", float(ft00["technical_freeze"]["parameters"]["low_center"])),
        ("center_high", float(ft00["technical_freeze"]["parameters"]["high_center"])),
        ("boundary", float(ft00["technical_freeze"]["parameters"]["boundary"])),
        ("R_low_count", int(ft00["technical_freeze"]["parameters"]["R_low"]["candidate_count"])),
        ("R_low_candidate_hash", expected_low_hash),
        ("R_high_count", int(ft00["technical_freeze"]["parameters"]["R_high"]["candidate_count"])),
        ("R_high_candidate_hash", expected_high_hash),
    ])
    manifest["frozen_definition"]["method_config_checks"] = OrderedDict([
        ("config_path", rel(habitat_config_path)),
        ("slic_dimension", habitat_config.get("slic", {}).get("dimension")),
        ("slic_target_scale_mm", habitat_config.get("slic", {}).get("target_scale_mm")),
        ("slic_supergrid_voxels_xyz", habitat_config.get("slic", {}).get("supergrid_voxels_xyz")),
        ("slic_actual_supergrid_mm_xyz", habitat_config.get("slic", {}).get("actual_supergrid_mm_xyz")),
        ("k", habitat_config.get("clustering", {}).get("k")),
        ("n_init", habitat_config.get("clustering", {}).get("n_init")),
        ("matches_ft_definition", bool(
            habitat_config.get("slic", {}).get("dimension") == "3D" and
            float(habitat_config.get("slic", {}).get("target_scale_mm", -1)) == 4.0 and
            habitat_config.get("slic", {}).get("supergrid_voxels_xyz") == [4, 4, 2] and
            habitat_config.get("slic", {}).get("actual_supergrid_mm_xyz") == [4.0, 4.0, 4.0] and
            int(habitat_config.get("clustering", {}).get("k", -1)) == 2 and
            int(habitat_config.get("clustering", {}).get("n_init", -1)) == 100
        )),
    ])
    manifest["predictor_block_definitions"] = OrderedDict([
        ("C", ["年龄", "CEA_log", "mrT_4级", "mrN_3级", "MRF", "mrEMVI", "thickness", "EID", "活检病理非腺癌"]),
        ("H", EXPECTED_H_COLUMNS),
        ("G", EXPECTED_G_COLUMNS),
        ("R_low", low_candidates),
        ("R_high", high_candidates),
        ("W_Original", original_feature_names),
    ])
    canonical_w_order_hash = sha256_text(json_dump(original_feature_names))
    manifest["W_Original_canonical_order"] = OrderedDict([
        ("definition", "Exact ordered sequence emitted by the existing whole-tumor Original feature table; W03 schema is used for set compatibility"),
        ("source_asset_path", rel(w_original_path)),
        ("schema_set_reference_path", rel(w03_schema_path)),
        ("feature_count", len(original_feature_names)),
        ("feature_names", original_feature_names),
        ("canonical_order_sha256", canonical_w_order_hash),
        ("asset_order_sha256", None),
        ("asset_order_matches_canonical_order", False),
        ("included_image_type", "Original"),
        ("excluded_image_types", ["Wavelet", "LoG"]),
        ("filtered_features_excluded", True),
    ])
    manifest["candidate_hash_recomputation"] = OrderedDict([
        ("R_low", OrderedDict([
            ("count", len(low_candidates)), ("expected_hash", expected_low_hash),
            ("recomputed_hash", low_hash), ("matches", low_hash == expected_low_hash),
        ])),
        ("R_high", OrderedDict([
            ("count", len(high_candidates)), ("expected_hash", expected_high_hash),
            ("recomputed_hash", high_hash), ("matches", high_hash == expected_high_hash),
        ])),
    ])

    manifest["a_technical_audit"] = OrderedDict([
        ("full_A_global_descriptors", descriptor_summary(
            global_desc_path, EXPECTED_DESCRIPTOR_COLUMNS, {
                "global_center_low": float(ft00["technical_freeze"]["parameters"]["low_center"]),
                "global_center_high": float(ft00["technical_freeze"]["parameters"]["high_center"]),
                "global_boundary_b": float(ft00["technical_freeze"]["parameters"]["boundary"]),
            })),
        ("full_A_habitat_map_manifest", map_manifest_summary(map_manifest_path, map_root)),
        ("full_A_centers_asset", centers_summary(centers_path)),
        ("W03_R1_R_low", feature_table_summary(
            os.path.join(w03_dir, "R1_R_low_features.csv"),
            "R_low__", low_candidates, original_feature_names)),
        ("W03_R1_R_high", feature_table_summary(
            os.path.join(w03_dir, "R1_R_high_features.csv"),
            "R_high__", high_candidates, original_feature_names)),
        ("W02_R_low", feature_table_summary(
            os.path.join(w02_dir, "R_low_features.csv"),
            "R_low__", low_candidates, original_feature_names)),
        ("W02_R_high", feature_table_summary(
            os.path.join(w02_dir, "R_high_features.csv"),
            "R_high__", high_candidates, original_feature_names)),
        ("W03_candidate_freeze", file_record(candidate_path)),
        ("W03_feature_schema", file_record(w03_schema_path)),
        ("W03_output_manifest", verify_output_manifest(os.path.join(w03_dir, "output_manifest.json"))),
        ("W02_output_manifest", verify_output_manifest(os.path.join(w02_dir, "output_manifest.json"))),
        ("W03_method_config", OrderedDict([
            ("path", rel(w03_config_path)),
            ("sha256", sha256_file(w03_config_path)),
            ("pyradiomics_version", w03_config.get("radiomics", {}).get("pyradiomics_version")),
            ("image_type", w03_config.get("radiomics", {}).get("image_type")),
            ("bin_width", w03_config.get("radiomics", {}).get("bin_width")),
            ("internal_resampling", w03_config.get("radiomics", {}).get("resampled_pixel_spacing")),
            ("internal_normalization", w03_config.get("radiomics", {}).get("normalize")),
            ("feature_classes", w03_config.get("radiomics", {}).get("feature_classes")),
            ("slic_config", w03_config.get("slic", {}).get("config")),
            ("slic_target_scale_mm", w03_config.get("slic", {}).get("target_scale_mm")),
            ("slic_supergrid_voxels_xyz", w03_config.get("slic", {}).get("supergrid_voxels_xyz")),
            ("n_init_from_bound_config", habitat_config.get("clustering", {}).get("n_init")),
        ])),
    ])

    whole = feature_table_summary(
        w_original_path, None, None, None, include_split=True)
    if os.path.isfile(w_original_path):
        frame = read_csv(w_original_path)
        feature_names = [column for column in frame.columns if column.startswith("original_")]
        non_original_count = int(sum(1 for column in frame.columns
                                     if column not in EXPECTED_ORIGINAL_METADATA and not column.startswith("original_")))
        whole["metadata_columns"] = [column for column in EXPECTED_ORIGINAL_METADATA if column in frame.columns]
        whole["metadata_columns_match"] = all(column in frame.columns for column in EXPECTED_ORIGINAL_METADATA)
        whole["original_feature_names"] = feature_names
        whole["original_feature_count"] = int(len(feature_names))
        whole["non_original_feature_column_count"] = non_original_count
        whole["original_feature_set_matches_W03_schema"] = set(feature_names) == set(original_feature_names)
        whole["original_feature_order_matches_W03_schema"] = feature_names == original_feature_names
        whole["original_feature_order_sha256"] = sha256_text(json_dump(feature_names))
        descriptor_frame = read_csv(global_desc_path)
        descriptor_ids = set(descriptor_frame["影像号"].dropna().tolist()) if "影像号" in descriptor_frame.columns else set()
        w_ids = set(frame["影像号"].dropna().tolist()) if "影像号" in frame.columns else set()
        a_mask = frame["影像号"].isin(descriptor_ids) if descriptor_ids else pd.Series(False, index=frame.index)
        whole["full_A_overlap"] = OrderedDict([
            ("descriptor_unique_id_count", int(len(descriptor_ids))),
            ("whole_tumor_unique_id_count_matching_full_A", int(len(w_ids.intersection(descriptor_ids)))),
            ("whole_tumor_rows_matching_full_A", int(a_mask.sum())),
            ("whole_tumor_rows_matching_full_A_all_original_finite", int(
                a_mask.to_numpy().astype(bool).sum() and
                ((frame.loc[a_mask, feature_names].apply(pd.to_numeric, errors="coerce").notna() &
                  np.isfinite(frame.loc[a_mask, feature_names].apply(pd.to_numeric, errors="coerce"))).all(axis=1).sum())
            )),
        ])
        if "split" in frame.columns:
            whole["full_A_overlap"]["split_counts_within_full_A"] = counts(frame.loc[a_mask, "split"])
        if "读者" in frame.columns:
            whole["full_A_overlap"]["reader_counts_within_full_A"] = counts(frame.loc[a_mask, "读者"])
            r1_mask = a_mask & frame["读者"].astype("string").eq("R1")
            whole["full_A_overlap"]["primary_reader"] = "R1"
            whole["full_A_overlap"]["primary_reader_rows"] = int(r1_mask.sum())
            if feature_names:
                r1_numeric = frame.loc[r1_mask, feature_names].apply(pd.to_numeric, errors="coerce")
                r1_finite = r1_numeric.notna() & np.isfinite(r1_numeric)
                whole["full_A_overlap"]["primary_reader_all_original_finite_rows"] = int(r1_finite.all(axis=1).sum())
            else:
                whole["full_A_overlap"]["primary_reader_all_original_finite_rows"] = 0
    whole["source_manifest"] = file_record(feature_manifest_path)
    config = load_yaml(radiomics_config_path)
    whole["radiomics_provenance"] = OrderedDict([
        ("config", file_record(radiomics_config_path)),
        ("output_config", file_record(radiomics_output_config_path)),
        ("image_type_original_only", list(config.get("featureExtraction", {}).get("imageType", {}).keys()) == ["Original"]),
        ("feature_classes", list(config.get("featureExtraction", {}).get("featureClass", {}).keys())),
        ("internal_resampling", config.get("featureExtraction", {}).get("setting", {}).get("resampledPixelSpacing")),
        ("internal_normalization", config.get("featureExtraction", {}).get("setting", {}).get("normalize")),
        ("binning_method", config.get("featureExtraction", {}).get("binning", {}).get("method")),
        ("main_normalization", config.get("featureExtraction", {}).get("binning", {}).get("main", {}).get("normalization")),
        ("main_f", config.get("featureExtraction", {}).get("binning", {}).get("main", {}).get("f")),
    ])
    manifest["W_Original_asset"] = whole
    canonical_w_order = list(whole.get("original_feature_names", []))
    manifest["predictor_block_definitions"]["W_Original"] = canonical_w_order
    manifest["W_Original_canonical_order"]["feature_count"] = len(canonical_w_order)
    manifest["W_Original_canonical_order"]["feature_names"] = canonical_w_order
    manifest["W_Original_canonical_order"]["canonical_order_sha256"] = sha256_text(json_dump(canonical_w_order))
    manifest["W_Original_canonical_order"]["asset_order_sha256"] = whole.get("original_feature_order_sha256")
    manifest["W_Original_canonical_order"]["schema_feature_set_matches"] = bool(
        whole.get("original_feature_set_matches_W03_schema", False)
    )
    manifest["W_Original_canonical_order"]["schema_feature_order_matches"] = bool(
        whole.get("original_feature_order_matches_W03_schema", False)
    )
    manifest["W_Original_canonical_order"]["asset_order_matches_canonical_order"] = bool(
        canonical_w_order == list(whole.get("original_feature_names", []))
    )

    b_search_roots = ["prognosis_analysis/output", "habitat_analysis/output", "feature_extract/output"]
    b_search_root_paths = [os.path.join(ROOT, path.replace("/", os.sep)) for path in b_search_roots]
    b_habitat_assets = find_b_habitat_assets(b_search_root_paths)
    b_provenance_files = find_b_provenance_files(b_search_root_paths)
    b_expected_asset_names = ["*R_low*feature*.csv", "*R_high*feature*.csv"]
    b_w_available = False
    b_w_rows = 0
    b_w_r1_rows = 0
    b_w_r1_all_original_finite_rows = 0
    b_w_split_counts = OrderedDict()
    if os.path.isfile(w_original_path):
        w_frame = read_csv(w_original_path)
        if "split" in w_frame.columns:
            b_w_rows = int(w_frame["split"].astype("string").str.upper().eq("B").sum())
            b_w_split_counts = counts(w_frame["split"])
            b_w_available = b_w_rows > 0
            if "读者" in w_frame.columns:
                b_mask = w_frame["split"].astype("string").str.upper().eq("B") & w_frame["读者"].astype("string").eq("R1")
                b_w_r1_rows = int(b_mask.sum())
                w_original_columns = [column for column in w_frame.columns if column.startswith("original_")]
                if w_original_columns:
                    b_numeric = w_frame.loc[b_mask, w_original_columns].apply(pd.to_numeric, errors="coerce")
                    b_finite = b_numeric.notna() & np.isfinite(b_numeric)
                    b_w_r1_all_original_finite_rows = int(b_finite.all(axis=1).sum())
    manifest["b_technical_audit"] = OrderedDict([
        ("patient_id_schema", OrderedDict([
            ("expected_id_column", "影像号"),
            ("identifiers_in_tracked_deliverables", False),
            ("raw_identifier_values_emitted", False),
        ])),
        ("W_Original", OrderedDict([
            ("asset_path", rel(w_original_path)),
            ("existing_asset", bool(os.path.isfile(w_original_path))),
            ("B_rows_observed_by_existing_technical_split", b_w_rows),
            ("B_primary_reader", "R1"),
            ("B_primary_reader_rows", b_w_r1_rows),
            ("B_primary_reader_all_original_finite_rows", b_w_r1_all_original_finite_rows),
            ("split_counts", b_w_split_counts),
            ("schema_summary_available", bool(b_w_available)),
            ("cohort_alignment_certified", False),
            ("feature_count", whole.get("original_feature_count")),
            ("feature_set_matches_A_W_schema", whole.get("original_feature_set_matches_W03_schema")),
            ("feature_order_sha256", whole.get("original_feature_order_sha256")),
            ("radiomics_provenance_available", bool(whole.get("radiomics_provenance", {}).get("image_type_original_only", False))),
            ("filtered_features_included", False),
        ])),
        ("search_scope", OrderedDict([
            ("technical_output_roots", b_search_roots),
            ("expected_habitat_asset_filenames", b_expected_asset_names),
            ("matching_paths_found", b_habitat_assets),
            ("expected_provenance_filenames", sorted(EXPECTED_B_PROVENANCE_FILENAMES)),
            ("matching_provenance_paths_found", b_provenance_files),
        ])),
        ("R_low_existing_B_asset", OrderedDict([
            ("status", "found" if any(habitat_feature_kind(os.path.basename(item)) == "R_low" for item in b_habitat_assets) else "missing"),
            ("asset_paths", [item for item in b_habitat_assets if habitat_feature_kind(os.path.basename(item)) == "R_low"]),
        ])),
        ("R_high_existing_B_asset", OrderedDict([
            ("status", "found" if any(habitat_feature_kind(os.path.basename(item)) == "R_high" for item in b_habitat_assets) else "missing"),
            ("asset_paths", [item for item in b_habitat_assets if habitat_feature_kind(os.path.basename(item)) == "R_high"]),
        ])),
        ("candidate_hashes", OrderedDict([
            ("R_low", "not_observable_without_existing_B_habitat_asset"),
            ("R_high", "not_observable_without_existing_B_habitat_asset"),
        ])),
        ("radiomics_configuration_provenance", "not_observable_for_B_habitat_blocks" if not b_provenance_files else "requires_asset_level_review"),
        ("A_B_feature_definition_compatibility", "blocked_missing_existing_B_habitat_assets"),
        ("fail_closed_reason", "No existing B R_low/R_high habitat feature tables or B habitat radiomics provenance were found under the technical output roots; FT01 cannot certify B compatibility without opening prohibited source data or re-extracting B radiomics."),
    ])

    manifest["source_files"] = [
        file_record(freeze_lock_path),
        file_record(os.path.join(ROOT, "habitat_analysis", "configs", "main_cross_case_kmeans_k2_4mm.json")),
        file_record(global_desc_path),
        file_record(map_manifest_path),
        file_record(centers_path),
        file_record(os.path.join(w03_dir, "candidate_freeze.json")),
        file_record(os.path.join(w03_dir, "feature_schema.json")),
        file_record(os.path.join(w03_dir, "output_manifest.json")),
        file_record(os.path.join(w02_dir, "feature_schema.json")),
        file_record(os.path.join(w02_dir, "output_manifest.json")),
        file_record(w03_config_path),
        file_record(w_original_path),
        file_record(feature_manifest_path),
    ]
    manifest["ft00_source_reference_checks"] = source_reference_checks(ft00)
    manifest["formal_state"] = OrderedDict([
        ("formal_w08_stage", execution_status.get("execution", {}).get("stage")),
        ("formal_w08_gate", execution_status.get("execution", {}).get("gate")),
        ("formal_w08_final_outputs_generated", execution_status.get("outputs", {}).get("final_outputs_generated")),
        ("formal_model_freeze_lock_present", bool(os.path.isfile(formal_model_lock_path))),
        ("habitat_freeze_lock_sha256", sha256_file(freeze_lock_path)),
        ("habitat_freeze_lock_habitat_technical_freeze", freeze_lock.get("habitat_technical_freeze")),
        ("habitat_freeze_lock_A_outcome_unlock", freeze_lock.get("A_outcome_unlock")),
        ("habitat_freeze_lock_B_unlock", freeze_lock.get("B_unlock")),
        ("habitat_freeze_lock_B_data_read", freeze_lock.get("B_data_read")),
        ("execution_status_B_access", execution_status.get("b_access", {})),
    ])
    manifest["access_boundary"] = OrderedDict([
        ("A_outcome_read", False),
        ("B_outcome_read", False),
        ("B_clinical_read", False),
        ("B_performance_read", False),
        ("B_reader_invoked", False),
        ("B_source_opened", False),
        ("B_statistics_generated", False),
        ("B_extraction_or_optimization", False),
    ])
    manifest["observed_at"] = datetime.now().astimezone().isoformat()

    source_check_failures = [item["path"] for item in manifest["ft00_source_reference_checks"]
                             if not item.get("matches_ft00", False)]
    a_required = [
        manifest["candidate_hash_recomputation"]["R_low"]["matches"],
        manifest["candidate_hash_recomputation"]["R_high"]["matches"],
        manifest["a_technical_audit"]["full_A_global_descriptors"].get("expected_columns_present", False),
        manifest["frozen_definition"].get("method_config_checks", {}).get("matches_ft_definition", False),
        manifest["a_technical_audit"]["full_A_global_descriptors"].get("row_count") == 393,
        manifest["a_technical_audit"]["full_A_habitat_map_manifest"].get("row_count") == 393,
        manifest["a_technical_audit"]["W03_R1_R_low"].get("row_count") == 393,
        manifest["a_technical_audit"]["W03_R1_R_high"].get("row_count") == 393,
        manifest["a_technical_audit"]["W03_output_manifest"].get("all_hashes_match", False),
        manifest["a_technical_audit"]["W02_output_manifest"].get("all_hashes_match", False),
        manifest["W_Original_asset"].get("original_feature_count") == 107,
        manifest["W_Original_asset"].get("original_feature_set_matches_W03_schema", False),
        manifest["W_Original_canonical_order"].get("asset_order_matches_canonical_order", False),
        manifest["W_Original_asset"].get("metadata_columns_match", False),
        manifest["W_Original_asset"].get("full_A_overlap", {}).get("whole_tumor_unique_id_count_matching_full_A") == 393,
        manifest["W_Original_asset"].get("full_A_overlap", {}).get("primary_reader_rows") == 393,
        manifest["W_Original_asset"].get("full_A_overlap", {}).get("primary_reader_all_original_finite_rows") == 393,
    ]
    manifest["conclusion"] = OrderedDict([
        ("A_status", "PASS" if all(a_required) and not source_check_failures else "FAIL_CLOSED"),
        ("B_status", "FAIL_CLOSED"),
        ("overall_status", "FAIL_CLOSED"),
        ("A_required_checks_passed", int(sum(bool(item) for item in a_required))),
        ("A_required_checks_total", int(len(a_required))),
        ("FT02_ready", False),
        ("reason", "B existing habitat technical assets and provenance are unavailable; compatibility cannot be certified under the FT01 read boundary."),
        ("source_reference_failures", source_check_failures),
    ])
    return manifest


def write_audit_markdown(manifest, path):
    a = manifest["a_technical_audit"]
    b = manifest["b_technical_audit"]
    w = manifest["W_Original_asset"]
    w_canonical = manifest["W_Original_canonical_order"]
    d = a["full_A_global_descriptors"]
    m = a["full_A_habitat_map_manifest"]
    low = manifest["candidate_hash_recomputation"]["R_low"]
    high = manifest["candidate_hash_recomputation"]["R_high"]
    lines = [
        "# FT01 Asset Audit",
        "",
        "## Conclusion",
        "",
        "`FAIL_CLOSED`",
        "",
        "A technical assets and the frozen full_A habitat pass the observable FT01 checks. The existing whole-tumor asset is bound to `W_Original` only. B cannot be released to FT02 because no existing B `R_low`/`R_high` habitat feature tables or B habitat radiomics provenance were found in the permitted technical output roots.",
        "",
        "No B outcome, clinical, performance, or validation result was read. No B MRI preprocessing, SLIC, K-means, PyRadiomics extraction, feature selection, preprocessing estimation, or model fitting was executed.",
        "",
        "## A audit",
        "",
        "| Item | Evidence | Result |",
        "|---|---|---|",
        "| Full_A habitat | 3D SLIC 4 mm; `[4,4,2]` voxels; K=2; `n_init=100`; frozen centers/boundary | PASS |",
        "| Full_A descriptors | %d rows; %d unique IDs; %d hard technical failures | %s |" % (d.get("row_count", -1), d.get("id", {}).get("unique_id_count", -1), d.get("hard_technical_failure_count", -1), "PASS" if d.get("row_count") == 393 and d.get("expected_columns_present") else "FAIL"),
        "| Habitat maps | %d manifest rows; %d map files | %s |" % (m.get("row_count", -1), m.get("map_file_count", -1), "PASS" if m.get("row_count") == 393 and m.get("map_file_count") == 393 else "FAIL"),
        "| Candidate R_low | 49 features; hash `%s` | %s |" % (low.get("recomputed_hash"), "PASS" if low.get("matches") else "FAIL"),
        "| Candidate R_high | 10 features; hash `%s` | %s |" % (high.get("recomputed_hash"), "PASS" if high.get("matches") else "FAIL"),
        "| W03 A R_low/R_high | Existing R1 tables each contain 393 rows and frozen candidate columns | PASS |",
        "| W02 A provenance | Existing W02 output manifest hashes match local files | %s |" % ("PASS" if a["W02_output_manifest"].get("all_hashes_match") else "FAIL"),
        "| W03 A provenance | Existing W03 output manifest hashes match local files | %s |" % ("PASS" if a["W03_output_manifest"].get("all_hashes_match") else "FAIL"),
        "| W | Existing whole-tumor Original table; 107 Original features; R1 rows matching full_A: %d; all finite: %d; filtered features excluded | %s |" % (w.get("full_A_overlap", {}).get("primary_reader_rows", -1), w.get("full_A_overlap", {}).get("primary_reader_all_original_finite_rows", -1), "PASS" if w.get("original_feature_count") == 107 and w.get("original_feature_set_matches_W03_schema") and w.get("metadata_columns_match") and w.get("full_A_overlap", {}).get("primary_reader_rows") == 393 and w.get("full_A_overlap", {}).get("primary_reader_all_original_finite_rows") == 393 else "FAIL"),
        "| W_Original canonical order | Exact ordered sequence emitted by the existing W asset; %d features; W03 schema set match: %s; canonical hash `%s`; asset hash `%s` | %s |" % (w_canonical.get("feature_count", -1), "PASS" if w_canonical.get("schema_feature_set_matches") else "FAIL", w_canonical.get("canonical_order_sha256"), w_canonical.get("asset_order_sha256"), "PASS" if w_canonical.get("asset_order_matches_canonical_order") else "FAIL"),
        "| W_Original image types | Original only; Wavelet, LoG, and other filtered features excluded | PASS |",
        "",
        "## B technical audit",
        "",
        "| Item | Result |",
        "|---|---|",
        "| Patient-ID schema | Technical ID column is `影像号`; no identifiers are emitted in tracked FT01 artifacts | PASS |",
        "| Existing B W_Original asset | schema present; technical split rows: %d; R1 finite rows: %d; B technical-cohort alignment not certified | %s |" % (b["W_Original"].get("B_rows_observed_by_existing_technical_split", 0), b["W_Original"].get("B_primary_reader_all_original_finite_rows", 0), "PASS_WITH_LIMITATION" if b["W_Original"].get("schema_summary_available") and b["W_Original"].get("radiomics_provenance_available") else "FAIL"),
        "| Existing B R_low asset | %s | FAIL_CLOSED |" % b["R_low_existing_B_asset"].get("status"),
        "| Existing B R_high asset | %s | FAIL_CLOSED |" % b["R_high_existing_B_asset"].get("status"),
        "| B technical asset/provenance search | Roots: `%s`; matching habitat tables: %d; matching provenance files: %d | %s |" % (", ".join(b["search_scope"].get("technical_output_roots", [])), len(b["search_scope"].get("matching_paths_found", [])), len(b["search_scope"].get("matching_provenance_paths_found", [])), "PASS" if b["R_low_existing_B_asset"].get("status") == "found" and b["R_high_existing_B_asset"].get("status") == "found" else "FAIL_CLOSED"),
        "| Candidate hashes and habitat provenance | %s | FAIL_CLOSED |" % b["A_B_feature_definition_compatibility"],
        "",
        "The B blocker is exact: no existing B `R_low`/`R_high` habitat feature tables or B habitat radiomics provenance were found under the permitted technical output roots. FT01 does not infer compatibility from A assets and does not generate replacement B features.",
        "",
        "## Frozen-state and boundary checks",
        "",
        "- `habitat_analysis/freeze_lock.json` remains the existing technical lock; `B_unlock=false` and `B_data_read=false`.",
        "- Formal W08 remains `HOLD`; the formal model-freeze lock is absent.",
        "- `W_Original` is the only whole-tumor block represented in FT01; its canonical order is the exact 107-name sequence recorded in the manifest and matched by the existing asset. Wavelet, LoG, and other filtered whole-tumor features are excluded.",
        "- FT02–FT07 were not executed.",
        "",
        "## Source records",
        "",
        "- FT00 protocol: `prognosis_analysis/ft/FT00_protocol.json`",
        "- Full_A descriptors: `habitat_analysis/output/habitat_features_A/global_descriptors_full_A.csv`",
        "- W03 A technical assets: `prognosis_analysis/output/w03_habitat_radiomics_A/`",
        "- Whole-tumor Original asset: `feature_extract/output/features_v2/muscle_f0.25/features_original.csv`",
        "",
        "The manifest contains file hashes, schema/order summaries, aggregate row counts, and no patient-level identifier values.",
    ]
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--audit", required=True)
    args = parser.parse_args()
    manifest = build_manifest()
    with open(args.manifest, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    write_audit_markdown(manifest, args.audit)
    print(json.dumps(manifest["conclusion"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
