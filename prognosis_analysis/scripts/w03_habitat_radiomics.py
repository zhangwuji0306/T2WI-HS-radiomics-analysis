"""W03: outcome-blind reader reproducibility QC and candidate freeze.

Only frozen technical inputs are read: the A technical cohort manifest, the
upstream normalized reader-specific images and masks, the fixed SLIC config,
and the frozen technical phenotype centers. No clinical, endpoint, model, or
validation input is part of this module's input graph.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

np.dot(np.eye(3), np.eye(3))
import SimpleITK as sitk
import radiomics
from radiomics import featureextractor

radiomics.setVerbosity(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
PROGNOSIS = os.path.dirname(HERE)
ROOT = os.path.dirname(PROGNOSIS)
HABITAT = os.path.join(ROOT, "habitat_analysis")
CONFIG_PATH = os.path.join(PROGNOSIS, "configs", "w03_habitat_radiomics.json")
COHORT_PATH = os.path.join(ROOT, "habitat_analysis", "output",
                           "technical_cohort_manifest", "cohort_A_lenient.csv")
PREP_ROOT = os.path.join(ROOT, "feature_extract", "output", "preprocessed")
CENTERS_PATH = os.path.join(
    ROOT, "habitat_analysis", "output", "feasibility_A_patient_balanced_post_slic_fix",
    "global_centers.csv")
DEFAULT_OUT = os.path.join(PROGNOSIS, "output", "w03_habitat_radiomics_A")
ASCII_ROOT = os.path.join(os.path.dirname(ROOT), "radiomics26")

BLOCKS = (("R_low", 0), ("R_high", 1))
FEATURE_CLASSES = ("firstorder", "shape", "glcm", "glrlm", "glszm", "gldm", "ngtdm")
BLOCK_META = ["影像号", "reader", "input_status", "pipeline_status",
              "structural_state", "habitat_present", "extractable", "status",
              "failure_class", "failure_reason"]
REPRO_COLUMNS = [
    "block", "feature", "feature_class", "candidate_level",
    "R1_habitat_present_cases", "R2_habitat_present_cases",
    "R1_finite_count", "R2_finite_count", "R1_finite_rate", "R2_finite_rate",
    "finite_rate_min", "pooled_finite_count", "pooled_finite_rate",
    "n_valid_pairs", "icc_2_1", "reproducibility_status",
    "finite_rate_gate_pass", "prediction_candidate", "exclusion_reason",
]


def apath(path):
    """Route local project paths through the configured ASCII junction."""
    absolute = os.path.abspath(path)
    root = os.path.abspath(ROOT)
    if absolute.lower().startswith((root + os.sep).lower()):
        return os.path.join(ASCII_ROOT, absolute[len(root) + 1:])
    return absolute


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def extractor_settings(config):
    """Return the one fixed, symmetric PyRadiomics parameter set."""
    px = config["radiomics"]
    return {
        "imageType": {"Original": {}},
        "featureClass": {name: [] for name in px["feature_classes"]},
        "setting": {
            "binWidth": float(px["bin_width"]),
            "normalize": False,
            "resampledPixelSpacing": None,
            "padDistance": 0,
            "minimumROIDimensions": 2,
            "minimumROISize": 10,
            "label": 1,
        },
    }


def geometry_errors(image, mask):
    errors = []
    if image.GetSize() != mask.GetSize():
        errors.append("image_mask_size_mismatch")
    if not np.allclose(image.GetSpacing(), mask.GetSpacing(), atol=1e-5, rtol=0):
        errors.append("image_mask_spacing_mismatch")
    if not np.allclose(image.GetOrigin(), mask.GetOrigin(), atol=1e-4, rtol=0):
        errors.append("image_mask_origin_mismatch")
    if not np.allclose(image.GetDirection(), mask.GetDirection(), atol=1e-5, rtol=0):
        errors.append("image_mask_direction_mismatch")
    return errors


def _error_text(exc):
    text = str(exc).replace("\r", " ").replace("\n", " ")
    text = text.replace(os.path.abspath(ROOT), "<project>")
    return "%s: %s" % (type(exc).__name__, text[:1000])


def classify_habitat_state(low_count, high_count):
    if low_count and high_count:
        return "dual-habitat"
    if low_count:
        return "single-H-low"
    if high_count:
        return "single-H-high"
    return "no-habitat"


def block_result(present, features=None, diagnostics=None, error=None):
    if not present:
        return {
            "extractable": 0,
            "status": "structurally_undefined",
            "failure_class": "structural_absence",
            "failure_reason": "structural_absence",
            "features": {},
            "diagnostics": {},
        }
    if error is not None:
        return {
            "extractable": 0,
            "status": "technical_failure",
            "failure_class": "technical_failure",
            "failure_reason": error,
            "features": {},
            "diagnostics": {},
        }
    return {
        "extractable": 1,
        "status": "extractable",
        "failure_class": "none",
        "failure_reason": "",
        "features": features or {},
        "diagnostics": diagnostics or {},
    }


def unavailable_block_result():
    return {
        "extractable": 0,
        "status": "not_available",
        "failure_class": "reader_input_unavailable",
        "failure_reason": "reader_input_missing",
        "features": {},
        "diagnostics": {},
    }


def load_case_ids(config):
    frame = pd.read_csv(COHORT_PATH, encoding="utf-8-sig", dtype=str,
                        usecols=[config["cohort"]["id_column"]])
    ids = sorted(set(frame[config["cohort"]["id_column"]].astype(str).str.strip()))
    expected = int(config["cohort"]["expected_unique_cases"])
    if len(ids) != expected:
        raise RuntimeError("technical A cohort has %d cases, expected %d" % (len(ids), expected))
    return ids


def load_frozen_phenotype(config):
    if not os.path.exists(CENTERS_PATH):
        raise RuntimeError("frozen technical centers are missing")
    frame = pd.read_csv(CENTERS_PATH, encoding="utf-8-sig")
    center_type = config["frozen_technical_phenotype"]["center_type"]
    required = {"center_type", "H_low", "H_high", "boundary_b"}
    if not required.issubset(frame.columns):
        raise RuntimeError("frozen technical centers lack required schema")
    frame = frame[frame["center_type"].astype(str) == center_type]
    if len(frame) != 1:
        raise RuntimeError("frozen technical center type is not unique")
    row = frame.iloc[0]
    values = {key: float(row[key]) for key in ("H_low", "H_high", "boundary_b")}
    if not np.isfinite(list(values.values())).all() or values["H_high"] <= values["H_low"]:
        raise RuntimeError("invalid frozen technical centers")
    if not (values["H_low"] < values["boundary_b"] < values["H_high"]):
        raise RuntimeError("frozen technical boundary is outside centers")
    return values


def load_slic_config(config):
    path = os.path.join(ROOT, config["slic"]["config"])
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_slic_functions():
    script_dir = os.path.join(HABITAT, "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from technical_dry_run_A import slic_grid_metadata, slic_labels
    return slic_grid_metadata, slic_labels


def make_habitat_mask(image, labels, value):
    mask = sitk.GetImageFromArray((labels == value).astype(np.uint8))
    mask.CopyInformation(image)
    return mask


def _numeric_features(raw):
    features = {}
    diagnostics = {}
    for key, value in raw.items():
        if key.startswith("diagnostics_"):
            diagnostics[key] = value
        else:
            try:
                number = float(value)
            except (TypeError, ValueError):
                number = np.nan
            features[key] = number if np.isfinite(number) else np.nan
    return features, diagnostics


def run_case(pid, reader, extractor, slic_config, slic_grid_metadata,
             slic_labels, phenotype):
    image_path = os.path.join(PREP_ROOT, pid, reader + "_image.nrrd")
    mask_path = os.path.join(PREP_ROOT, pid, reader + "_mask.nrrd")
    base = {
        "影像号": pid,
        "reader": reader,
        "input_status": "not_available",
        "pipeline_status": "not_available",
        "structural_state": "not_available",
        "H_low_present": np.nan,
        "H_high_present": np.nan,
        "n_supervoxels": np.nan,
        "H_low_voxels": np.nan,
        "H_high_voxels": np.nan,
        "input_failure_reason": "reader_input_missing",
        "blocks": {},
    }
    for block_name, _label in BLOCKS:
        base["blocks"][block_name] = unavailable_block_result()
    if not (os.path.exists(image_path) and os.path.exists(mask_path)):
        return base

    base.update(input_status="available", pipeline_status="technical_failure",
                input_failure_reason="")
    try:
        image = sitk.ReadImage(apath(image_path))
        roi_image = sitk.ReadImage(apath(mask_path))
        errors = geometry_errors(image, roi_image)
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
        if np.any(labels[tumor] < 0):
            raise RuntimeError("slic_unassigned_tumor_voxels")
        labels_inside = np.unique(labels[tumor])
        if not len(labels_inside):
            raise RuntimeError("slic_no_tumor_supervoxels")

        habitat = np.full(labels.shape, -1, dtype=np.int8)
        for label in labels_inside:
            inside = (labels == int(label)) & tumor
            mean = float(array[inside].mean())
            if not np.isfinite(mean):
                raise RuntimeError("nonfinite_supervoxel_mean")
            habitat[labels == int(label)] = int(mean >= phenotype["boundary_b"])
        habitat[~tumor] = -1
        if np.any(habitat[tumor] < 0):
            raise RuntimeError("unassigned_tumor_habitat")

        low_count = int(np.sum(tumor & (habitat == 0)))
        high_count = int(np.sum(tumor & (habitat == 1)))
        if low_count + high_count != int(tumor.sum()):
            raise RuntimeError("tumor_voxel_not_assigned_to_habitat")
        state = classify_habitat_state(low_count, high_count)
        grid = slic_grid_metadata(image, slic_config)
        base.update(
            pipeline_status="success",
            structural_state=state,
            H_low_present=int(bool(low_count)),
            H_high_present=int(bool(high_count)),
            n_supervoxels=int(len(labels_inside)),
            H_low_voxels=low_count,
            H_high_voxels=high_count,
            slic_spacing_mm_xyz=";".join("%.8g" % x for x in grid["spacing_mm_xyz"]),
            slic_supergrid_voxels_xyz=";".join(str(x) for x in grid["supergrid_voxels_xyz"]),
            slic_actual_supergrid_mm_xyz=";".join("%.8g" % x for x in grid["actual_supergrid_mm_xyz"]),
        )
        for block_name, label in BLOCKS:
            present = bool(low_count if label == 0 else high_count)
            if not present:
                base["blocks"][block_name] = block_result(False)
                continue
            try:
                mask = make_habitat_mask(image, habitat, label)
                raw = extractor.execute(image, mask)
                features, diagnostics = _numeric_features(raw)
                base["blocks"][block_name] = block_result(
                    True, features=features, diagnostics=diagnostics)
            except Exception as exc:  # noqa: BLE001
                base["blocks"][block_name] = block_result(
                    True, error=_error_text(exc))
        return base
    except Exception as exc:  # noqa: BLE001
        reason = _error_text(exc)
        base["input_failure_reason"] = reason
        for block_name, _label in BLOCKS:
            base["blocks"][block_name] = block_result(True, error=reason)
        return base


def make_feature_frame(rows, block_name, feature_names):
    present_key = "H_low_present" if block_name == "R_low" else "H_high_present"
    output = []
    for row in rows:
        result = row["blocks"][block_name]
        item = {
            "影像号": row["影像号"],
            "reader": row["reader"],
            "input_status": row["input_status"],
            "pipeline_status": row["pipeline_status"],
            "structural_state": row["structural_state"],
            "habitat_present": row[present_key],
            "extractable": result["extractable"],
            "status": result["status"],
            "failure_class": result["failure_class"],
            "failure_reason": result["failure_reason"],
        }
        item.update({block_name + "__" + key: result["features"].get(key, np.nan)
                     for key in feature_names})
        output.append(item)
    return pd.DataFrame(output, columns=BLOCK_META +
                        [block_name + "__" + key for key in feature_names])


def make_availability_frame(rows):
    columns = ["影像号", "reader", "input_status", "pipeline_status",
               "structural_state", "H_low_present", "H_high_present",
               "n_supervoxels", "H_low_voxels", "H_high_voxels",
               "slic_spacing_mm_xyz", "slic_supergrid_voxels_xyz",
               "slic_actual_supergrid_mm_xyz", "input_failure_reason"]
    return pd.DataFrame(rows, columns=columns)


def finite_rate(values):
    values = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    if not len(values):
        return np.nan
    return float(np.isfinite(values).mean())


def icc_2_1(values):
    """Two-way random-effects, absolute-agreement, single-measure ICC."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != 2:
        raise ValueError("ICC(2,1) requires an n x 2 matrix")
    values = values[np.isfinite(values).all(axis=1)]
    n, k = values.shape
    if n < 2:
        return np.nan
    grand = float(values.mean())
    row_means = values.mean(axis=1)
    col_means = values.mean(axis=0)
    msr = float(k * np.sum((row_means - grand) ** 2) / (n - 1))
    msc = float(n * np.sum((col_means - grand) ** 2) / (k - 1))
    residual = values - row_means[:, None] - col_means[None, :] + grand
    mse = float(np.sum(residual ** 2) / ((n - 1) * (k - 1)))
    denominator = msr + (k - 1) * mse + k * (msc - mse) / n
    if not np.isfinite(denominator) or denominator == 0:
        return np.nan
    return float((msr - mse) / denominator)


def feature_class(feature):
    prefix = "original_"
    if not feature.startswith(prefix):
        return "unknown"
    remainder = feature[len(prefix):]
    return remainder.split("_", 1)[0]


def candidate_level(feature, config):
    klass = feature_class(feature)
    levels = config["candidate_levels"]
    for level in ("main", "secondary", "exploratory_qc"):
        if klass in levels[level]:
            return level
    return "unclassified"


def candidate_decision(icc, n_valid_pairs, r1_rate, r2_rate, level, config):
    threshold = float(config["reproducibility"]["icc_threshold_exclusive"])
    min_pairs = int(config["reproducibility"]["minimum_valid_pairs"])
    min_rate = float(config["reproducibility"]["finite_feature_rate_min_inclusive"])
    reasons = []
    if n_valid_pairs < min_pairs:
        repro_status = "insufficient reproducibility sample"
        reasons.append("insufficient reproducibility sample")
    elif not np.isfinite(icc) or not (icc > threshold):
        repro_status = "icc_threshold_not_met"
        reasons.append("ICC_not_above_0.75")
    else:
        repro_status = "pass"
    finite_pass = (np.isfinite(r1_rate) and np.isfinite(r2_rate)
                   and r1_rate >= min_rate and r2_rate >= min_rate)
    if not finite_pass:
        reasons.append("finite_feature_rate_below_0.95")
    formal_level = level in config["candidate_levels"]["formal_prediction_pool"]
    if not formal_level:
        reasons.append("exploratory_qc_only")
    included = bool(repro_status == "pass" and finite_pass and formal_level)
    return repro_status, int(finite_pass), int(included), ";".join(reasons)


def candidate_hash(features):
    canonical = json.dumps(sorted(set(features)), ensure_ascii=False,
                            separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _finite_stats(frame, block_name):
    present = frame["habitat_present"] == 1
    rates = []
    for column in frame.columns:
        if not column.startswith(block_name + "__"):
            continue
        values = pd.to_numeric(frame.loc[present, column], errors="coerce")
        rates.append(float(np.isfinite(values.to_numpy(dtype=float)).mean())
                      if len(values) else np.nan)
    finite = np.asarray(rates, dtype=float)
    finite = finite[np.isfinite(finite)]
    if not len(finite):
        return {"feature_finite_rate_min": np.nan,
                "feature_finite_rate_median": np.nan,
                "feature_finite_rate_p95": np.nan,
                "features_finite_ge_95": 0}
    return {"feature_finite_rate_min": float(np.min(finite)),
            "feature_finite_rate_median": float(np.median(finite)),
            "feature_finite_rate_p95": float(np.percentile(finite, 95)),
            "features_finite_ge_95": int(np.sum(finite >= .95))}


def build_reproducibility(block_name, feature_names, frames, config):
    r1 = frames[("R1", block_name)].set_index("影像号")
    r2 = frames[("R2", block_name)].set_index("影像号")
    rows = []
    for feature in feature_names:
        column = block_name + "__" + feature
        r1_present = r1["habitat_present"] == 1
        r2_present = r2["habitat_present"] == 1
        r1_values = pd.to_numeric(r1.loc[r1_present, column], errors="coerce")
        r2_values = pd.to_numeric(r2.loc[r2_present, column], errors="coerce")
        r1_array = r1_values.to_numpy(dtype=float)
        r2_array = r2_values.to_numpy(dtype=float)
        r1_finite = np.isfinite(r1_array)
        r2_finite = np.isfinite(r2_array)
        paired_ids = sorted(set(r1.index[r1_present]) & set(r2.index[r2_present]))
        pair_values = []
        for pid in paired_ids:
            a = pd.to_numeric(pd.Series([r1.loc[pid, column]]), errors="coerce").iloc[0]
            b = pd.to_numeric(pd.Series([r2.loc[pid, column]]), errors="coerce").iloc[0]
            if np.isfinite(a) and np.isfinite(b):
                pair_values.append((float(a), float(b)))
        pair_matrix = np.asarray(pair_values, dtype=float)
        n_pairs = int(len(pair_matrix))
        icc = icc_2_1(pair_matrix) if n_pairs >= 2 else np.nan
        r1_rate = float(r1_finite.mean()) if len(r1_finite) else np.nan
        r2_rate = float(r2_finite.mean()) if len(r2_finite) else np.nan
        level = candidate_level(feature, config)
        repro_status, finite_pass, included, reason = candidate_decision(
            icc, n_pairs, r1_rate, r2_rate, level, config)
        pooled_denominator = len(r1_array) + len(r2_array)
        rows.append({
            "block": block_name,
            "feature": feature,
            "feature_class": feature_class(feature),
            "candidate_level": level,
            "R1_habitat_present_cases": int(r1_present.sum()),
            "R2_habitat_present_cases": int(r2_present.sum()),
            "R1_finite_count": int(r1_finite.sum()),
            "R2_finite_count": int(r2_finite.sum()),
            "R1_finite_rate": r1_rate,
            "R2_finite_rate": r2_rate,
            "finite_rate_min": (min(r1_rate, r2_rate)
                                 if np.isfinite(r1_rate) and np.isfinite(r2_rate)
                                 else np.nan),
            "pooled_finite_count": int(r1_finite.sum() + r2_finite.sum()),
            "pooled_finite_rate": (float((r1_finite.sum() + r2_finite.sum()) / pooled_denominator)
                                    if pooled_denominator else np.nan),
            "n_valid_pairs": n_pairs,
            "icc_2_1": icc,
            "reproducibility_status": repro_status,
            "finite_rate_gate_pass": finite_pass,
            "prediction_candidate": included,
            "exclusion_reason": reason,
        })
    return pd.DataFrame(rows, columns=REPRO_COLUMNS)


def coverage_summary(rows_by_reader, frames, feature_qc, feature_names):
    output = []
    for reader in ("R1", "R2"):
        rows = rows_by_reader[reader]
        target = len(rows)
        input_available = sum(row["input_status"] == "available" for row in rows)
        pipeline_success = sum(row["pipeline_status"] == "success" for row in rows)
        technical_failures = sum(row["pipeline_status"] == "technical_failure" for row in rows)
        for block_name, _label in BLOCKS:
            frame = frames[(reader, block_name)]
            feature_block = feature_qc[feature_qc["block"] == block_name]
            present = frame["habitat_present"] == 1
            output.append({
                "reader": reader,
                "block": block_name,
                "target_A_cases": target,
                "reader_input_available_cases": int(input_available),
                "pipeline_success_cases": int(pipeline_success),
                "pipeline_technical_failure_cases": int(technical_failures),
                "habitat_present_cases": int(present.sum()),
                "extractable_cases": int((frame["extractable"] == 1).sum()),
                "structural_absence_cases": int((frame["failure_class"] == "structural_absence").sum()),
                "technical_failure_cases": int((frame["failure_class"] == "technical_failure").sum()),
                "feature_count": len(feature_names),
                "finite_rate_min": (float(feature_block["R1_finite_rate"].min())
                                     if reader == "R1" else float(feature_block["R2_finite_rate"].min())),
                "finite_rate_median": (float(feature_block["R1_finite_rate"].median())
                                        if reader == "R1" else float(feature_block["R2_finite_rate"].median())),
                "features_finite_ge_95": int((feature_block["R1_finite_rate"] >= .95).sum()
                                               if reader == "R1" else
                                               (feature_block["R2_finite_rate"] >= .95).sum()),
            })
    return pd.DataFrame(output)


def exclusion_summary(feature_qc):
    rows = []
    for (block_name, level), group in feature_qc.groupby(
            ["block", "candidate_level"], sort=True):
        included = int((group["prediction_candidate"] == 1).sum())
        rows.append({"block": block_name, "candidate_level": level,
                     "reason": "included", "feature_count": included})
        excluded = group[group["prediction_candidate"] == 0]
        counts = {}
        for text in excluded["exclusion_reason"].fillna(""):
            for reason in str(text).split(";"):
                if reason:
                    counts[reason] = counts.get(reason, 0) + 1
        for reason, count in sorted(counts.items()):
            rows.append({"block": block_name, "candidate_level": level,
                         "reason": reason, "feature_count": int(count)})
    return pd.DataFrame(rows, columns=["block", "candidate_level", "reason",
                                       "feature_count"])


def _write_csv(path, frame):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _write_json(path, payload):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def run(args):
    started = time.perf_counter()
    config = load_config()
    ids = load_case_ids(config)
    if args.ids:
        requested = sorted(set(item.strip() for item in args.ids.split(",") if item.strip()))
        missing = sorted(set(requested) - set(ids))
        if missing:
            raise RuntimeError("requested IDs are not in A technical cohort")
        ids = requested
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        ids = ids[:args.limit]
    phenotype = load_frozen_phenotype(config)
    slic_config = load_slic_config(config)
    slic_grid_metadata, slic_labels = load_slic_functions()
    extractor = featureextractor.RadiomicsFeatureExtractor(extractor_settings(config))
    rows_by_reader = {}
    for reader in config["readers"]:
        rows = []
        for index, pid in enumerate(ids, 1):
            rows.append(run_case(pid, reader, extractor, slic_config,
                                 slic_grid_metadata, slic_labels, phenotype))
            if not args.quiet:
                print("%s processed %d/%d" % (reader, index, len(ids)), flush=True)
        rows_by_reader[reader] = rows

    feature_names = sorted(set(
        key for rows in rows_by_reader.values() for row in rows
        for block_name, _label in BLOCKS for key in row["blocks"][block_name]["features"]))
    if not feature_names:
        raise RuntimeError("no radiomics features were extracted")
    frames = {}
    for reader, rows in rows_by_reader.items():
        for block_name, _label in BLOCKS:
            frames[(reader, block_name)] = make_feature_frame(
                rows, block_name, feature_names)

    feature_qc = pd.concat([
        build_reproducibility(block_name, feature_names, frames, config)
        for block_name, _label in BLOCKS
    ], ignore_index=True)
    coverage = coverage_summary(rows_by_reader, frames, feature_qc, feature_names)
    exclusions = exclusion_summary(feature_qc)
    candidates = []
    candidate_hashes = {}
    candidate_features = {}
    for block_name, _label in BLOCKS:
        block_qc = feature_qc[feature_qc["block"] == block_name]
        names = sorted(block_qc.loc[block_qc["prediction_candidate"] == 1,
                                     "feature"].tolist())
        candidate_hashes[block_name] = candidate_hash(names)
        candidate_features[block_name] = names
        for _, row in block_qc.iterrows():
            candidates.append(row.to_dict())
    candidate_frame = pd.DataFrame(candidates, columns=REPRO_COLUMNS)

    out = os.path.abspath(args.out_root or DEFAULT_OUT)
    os.makedirs(out, exist_ok=True)
    _write_csv(os.path.join(out, "reader_case_availability.csv"), pd.concat([
        make_availability_frame(rows) for rows in rows_by_reader.values()
    ], ignore_index=True))
    for (reader, block_name), frame in frames.items():
        _write_csv(os.path.join(out, reader + "_" + block_name + "_features.csv"), frame)
    _write_csv(os.path.join(out, "icc_and_candidate_qc.csv"), feature_qc)
    _write_csv(os.path.join(out, "coverage_summary.csv"), coverage)
    _write_csv(os.path.join(out, "exclusion_summary.csv"), exclusions)
    technical_failures = []
    for reader, rows in rows_by_reader.items():
        for row in rows:
            for block_name, _label in BLOCKS:
                result = row["blocks"][block_name]
                if result["failure_class"] == "technical_failure":
                    technical_failures.append({
                        "影像号": row["影像号"], "reader": reader,
                        "block": block_name, "failure_class": "technical_failure",
                        "failure_reason": result["failure_reason"],
                    })
    _write_csv(os.path.join(out, "technical_failures.csv"), pd.DataFrame(
        technical_failures,
        columns=["影像号", "reader", "block", "failure_class", "failure_reason"]))

    summary_rows = []
    for block_name, _label in BLOCKS:
        block_qc = feature_qc[feature_qc["block"] == block_name]
        summary_rows.extend([
            {"block": block_name, "metric": "feature_count", "value": len(block_qc)},
            {"block": block_name, "metric": "n_valid_pairs_min", "value": int(block_qc["n_valid_pairs"].min())},
            {"block": block_name, "metric": "n_valid_pairs_median", "value": float(block_qc["n_valid_pairs"].median())},
            {"block": block_name, "metric": "features_n_valid_pairs_ge_10", "value": int((block_qc["n_valid_pairs"] >= 10).sum())},
            {"block": block_name, "metric": "features_icc_gt_0_75", "value": int((block_qc["icc_2_1"] > .75).sum())},
            {"block": block_name, "metric": "features_finite_rate_gate_pass", "value": int(block_qc["finite_rate_gate_pass"].sum())},
            {"block": block_name, "metric": "formal_prediction_candidate_count", "value": int(block_qc["prediction_candidate"].sum())},
            {"block": block_name, "metric": "candidate_hash", "value": candidate_hashes[block_name]},
        ])
    _write_csv(os.path.join(out, "summary.csv"), pd.DataFrame(summary_rows))

    metadata = {
        "stage": "W03",
        "analysis_id": config["analysis_id"],
        "created_at_epoch": time.time(),
        "pyradiomics_version": getattr(radiomics, "__version__", "unknown"),
        "config_sha256": sha256(CONFIG_PATH),
        "technical_cohort_manifest_sha256": sha256(COHORT_PATH),
        "slic_config_sha256": sha256(os.path.join(ROOT, config["slic"]["config"])),
        "frozen_technical_centers_sha256": sha256(CENTERS_PATH),
        "target_cases": len(ids),
        "reader_target_cases": {reader: len(rows) for reader, rows in rows_by_reader.items()},
        "reader_input_available_cases": {
            reader: sum(row["input_status"] == "available" for row in rows)
            for reader, rows in rows_by_reader.items()
        },
        "outcome_blind": True,
        "clinical_data_read": False,
        "outcome_columns_read": False,
        "B_data_read": False,
        "fixed_preprocessing": config["preprocessing"],
        "frozen_technical_phenotype": phenotype,
        "icc_model": config["reproducibility"]["icc"],
        "icc_threshold_exclusive": config["reproducibility"]["icc_threshold_exclusive"],
        "minimum_valid_pairs": config["reproducibility"]["minimum_valid_pairs"],
        "finite_rate_min_inclusive": config["reproducibility"]["finite_feature_rate_min_inclusive"],
        "feature_count_per_block": len(feature_names),
        "R_low_candidate_hash": candidate_hashes["R_low"],
        "R_high_candidate_hash": candidate_hashes["R_high"],
        "candidate_features": candidate_features,
        "candidate_counts": {
            block_name: int(feature_qc.loc[
                (feature_qc["block"] == block_name) &
                (feature_qc["prediction_candidate"] == 1)].shape[0])
            for block_name, _label in BLOCKS
        },
        "symmetry_check": bool(
            set(feature_qc.loc[feature_qc["block"] == "R_low", "feature"]) ==
            set(feature_qc.loc[feature_qc["block"] == "R_high", "feature"])),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    freeze = {
        "stage": "W03",
        "freeze_status": "complete" if not args.limit and not args.ids else "smoke_only",
        "outcome_blind": True,
        "technical_candidate_rules": {
            "icc": "ICC(2,1)",
            "icc_threshold": ">0.75",
            "minimum_valid_pairs": 10,
            "finite_feature_rate": ">=0.95_in_each_reader_among_habitat_present_cases",
        },
        "R_low_candidate_hash": candidate_hashes["R_low"],
        "R_high_candidate_hash": candidate_hashes["R_high"],
        "candidate_features": candidate_features,
        "R_low_candidate_count": int((feature_qc["block"].eq("R_low") & feature_qc["prediction_candidate"].eq(1)).sum()),
        "R_high_candidate_count": int((feature_qc["block"].eq("R_high") & feature_qc["prediction_candidate"].eq(1)).sum()),
        "candidate_level_order": ["main", "secondary", "exploratory_qc"],
        "feature_count_per_block": len(feature_names),
        "symmetry_check": metadata["symmetry_check"],
        "outcome_columns_read": False,
        "clinical_data_read": False,
        "B_data_read": False,
    }
    _write_json(os.path.join(out, "run_metadata.json"), metadata)
    _write_json(os.path.join(out, "candidate_freeze.json"), freeze)
    _write_json(os.path.join(out, "feature_schema.json"), {
        "blocks": [name for name, _label in BLOCKS],
        "feature_classes": list(FEATURE_CLASSES),
        "feature_names": feature_names,
        "candidate_levels": config["candidate_levels"],
        "structural_absence_value": None,
        "technical_failure_value": None,
    })
    output_names = [
        "reader_case_availability.csv", "R1_R_low_features.csv",
        "R1_R_high_features.csv", "R2_R_low_features.csv",
        "R2_R_high_features.csv", "icc_and_candidate_qc.csv",
        "coverage_summary.csv", "technical_failures.csv", "summary.csv",
        "exclusion_summary.csv",
        "run_metadata.json", "candidate_freeze.json", "feature_schema.json",
    ]
    manifest = {"stage": "W03", "files": {}}
    for name in output_names:
        path = os.path.join(out, name)
        manifest["files"][name] = {"bytes": os.path.getsize(path), "sha256": sha256(path)}
    _write_json(os.path.join(out, "output_manifest.json"), manifest)
    print("W03 complete: cases=%d R1_available=%d R2_available=%d elapsed_seconds=%.1f output=%s" % (
        len(ids), metadata["reader_input_available_cases"]["R1"],
        metadata["reader_input_available_cases"]["R2"], metadata["elapsed_seconds"], out))


def main():
    parser = argparse.ArgumentParser(description="Outcome-blind W03 ICC and candidate freeze")
    parser.add_argument("--limit", type=int, help="process first N A technical cases")
    parser.add_argument("--ids", help="comma-separated A technical IDs for a controlled smoke test")
    parser.add_argument("--out-root", help="local output directory override")
    parser.add_argument("--quiet", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
