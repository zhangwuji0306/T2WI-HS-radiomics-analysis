"""W02: outcome-blind, symmetric H-low/H-high Original radiomics extraction.

The script consumes the already normalized/resampled R1 image, its tumor ROI,
and the frozen W01 habitat map. It never reads clinical, pathology, outcome,
or B-cohort data. Structural absence is represented as undefined features and
is kept separate from extraction failure.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
import time

import numpy as np
import pandas as pd

# Keep the Windows SimpleITK import order used by the upstream workflow.
np.dot(np.eye(3), np.eye(3))
import SimpleITK as sitk
import radiomics
from radiomics import featureextractor

radiomics.setVerbosity(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
PROGNOSIS = os.path.dirname(HERE)
ROOT = os.path.dirname(PROGNOSIS)
HABITAT = os.path.join(ROOT, "habitat_analysis")
CONFIG_PATH = os.path.join(PROGNOSIS, "configs", "w02_habitat_radiomics.json")
FREEZE_LOCK = os.path.join(HABITAT, "freeze_lock.json")
COHORT = os.path.join(HABITAT, "output", "technical_cohort_manifest",
                      "cohort_A_lenient.csv")
MAP_ROOT = os.path.join(HABITAT, "output", "habitat_maps_A")
MAP_MANIFEST = os.path.join(HABITAT, "output", "habitat_maps_A_manifest.csv")
PREP_ROOT = os.path.join(ROOT, "feature_extract", "output", "preprocessed")
DEFAULT_OUT = os.path.join(PROGNOSIS, "output", "w02_habitat_radiomics_A")
ASCII_ROOT = os.path.join(os.path.dirname(ROOT), "radiomics26")

FEATURE_CLASSES = ["firstorder", "shape", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]
BLOCKS = (("R_low", 0), ("R_high", 1))
BLOCK_META = ["影像号", "reader", "structural_state", "habitat_present",
              "extractable", "status", "failure_class", "failure_reason"]


def apath(path):
    """Route local project paths through the ASCII junction for SimpleITK."""
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
    """Build the only PyRadiomics parameter set used for both habitat blocks."""
    px = config["pyradiomics"]
    return {
        "imageType": {"Original": {}},
        "featureClass": {name: [] for name in FEATURE_CLASSES},
        "setting": {
            "binWidth": float(px["binWidth"]),
            "normalize": False,
            "resampledPixelSpacing": None,
            "padDistance": 0,
            "minimumROIDimensions": 2,
            "minimumROISize": 10,
            "label": 1,
        },
    }


def classify_habitat_state(low_count, high_count):
    if low_count and high_count:
        return "dual-habitat"
    if low_count:
        return "single-H-low"
    if high_count:
        return "single-H-high"
    return "no-habitat"


def block_result(structural_state, present, features=None, diagnostics=None,
                 error=None):
    """Return a common status record for either symmetric radiomics block."""
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


def _error_text(exc):
    text = str(exc).replace("\r", " ").replace("\n", " ")
    text = text.replace(os.path.abspath(ROOT), "<project>")
    return "%s: %s" % (type(exc).__name__, text[:1000])


def geometry_errors(image, mask, labels):
    errors = []
    if image.GetSize() != mask.GetSize() or image.GetSize() != labels.GetSize():
        errors.append("size_mismatch")
    if not np.allclose(image.GetSpacing(), mask.GetSpacing(), atol=1e-5, rtol=0):
        errors.append("image_roi_spacing_mismatch")
    if not np.allclose(image.GetSpacing(), labels.GetSpacing(), atol=1e-5, rtol=0):
        errors.append("image_map_spacing_mismatch")
    if not np.allclose(image.GetOrigin(), mask.GetOrigin(), atol=1e-4, rtol=0):
        errors.append("image_roi_origin_mismatch")
    if not np.allclose(image.GetOrigin(), labels.GetOrigin(), atol=1e-4, rtol=0):
        errors.append("image_map_origin_mismatch")
    if not np.allclose(image.GetDirection(), mask.GetDirection(), atol=1e-5, rtol=0):
        errors.append("image_roi_direction_mismatch")
    if not np.allclose(image.GetDirection(), labels.GetDirection(), atol=1e-5, rtol=0):
        errors.append("image_map_direction_mismatch")
    return errors


def validate_frozen_lock():
    """Validate W01 technical inputs before reading any case image."""
    script_dir = os.path.join(HABITAT, "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from freeze_lock import validate_freeze_lock

    return validate_freeze_lock(FREEZE_LOCK, artifact_root=HABITAT)


def load_case_ids():
    frame = pd.read_csv(COHORT, encoding="utf-8-sig", dtype=str,
                        usecols=["影像号"])
    ids = sorted(set(frame["影像号"].astype(str).str.strip()))
    if len(ids) != 393:
        raise RuntimeError("A lenient technical cohort has %d cases, expected 393" % len(ids))
    return ids


def load_map_rows():
    script_dir = os.path.join(HABITAT, "scripts")
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    from freeze_lock import validate_habitat_map_manifest

    rows = validate_habitat_map_manifest(MAP_MANIFEST, MAP_ROOT)
    return {str(row["patient_id"]).strip(): row for row in rows}


def make_habitat_mask(image, labels_array, value):
    mask_array = (labels_array == value).astype(np.uint8)
    mask = sitk.GetImageFromArray(mask_array)
    mask.CopyInformation(image)
    return mask


def run_case(pid, extractor, map_row):
    image_path = os.path.join(PREP_ROOT, pid, "R1_image.nrrd")
    roi_path = os.path.join(PREP_ROOT, pid, "R1_mask.nrrd")
    map_path = os.path.join(MAP_ROOT, map_row["relative_path"])
    base = {
        "影像号": pid,
        "reader": "R1",
        "structural_state": "technical_failure",
        "H_low_present": None,
        "H_high_present": None,
        "R_low_extractable": 0,
        "R_high_extractable": 0,
        "R_low_status": "technical_failure",
        "R_high_status": "technical_failure",
        "R_low_failure_class": "technical_failure",
        "R_high_failure_class": "technical_failure",
        "R_low_failure_reason": "",
        "R_high_failure_reason": "",
        "case_any_technical_failure": 1,
        "input_failure_reason": "",
        "blocks": {},
    }
    try:
        image = sitk.ReadImage(apath(image_path))
        roi_image = sitk.ReadImage(apath(roi_path))
        label_image = sitk.ReadImage(apath(map_path))
        errors = geometry_errors(image, roi_image, label_image)
        if errors:
            raise RuntimeError(";".join(errors))
        roi_array = sitk.GetArrayFromImage(roi_image)
        labels_array = sitk.GetArrayFromImage(label_image)
        valid_values = np.isin(np.unique(labels_array), [-1, 0, 1])
        if not valid_values.all():
            raise RuntimeError("frozen_map_has_unexpected_label")
        tumor = roi_array == 1
        if not tumor.any():
            raise RuntimeError("empty_tumor_roi")
        if np.any(labels_array[tumor] < 0) or np.any(labels_array[~tumor] != -1):
            raise RuntimeError("frozen_map_not_aligned_to_tumor_roi")
        low_count = int(np.sum(tumor & (labels_array == 0)))
        high_count = int(np.sum(tumor & (labels_array == 1)))
        if low_count + high_count != int(tumor.sum()):
            raise RuntimeError("tumor_voxel_not_assigned_to_frozen_habitat")
        state = classify_habitat_state(low_count, high_count)
        base.update(structural_state=state,
                    H_low_present=int(bool(low_count)),
                    H_high_present=int(bool(high_count)),
                    input_failure_reason="")
        for block_name, label in BLOCKS:
            present = bool(low_count if label == 0 else high_count)
            try:
                if not present:
                    result = block_result(state, False)
                else:
                    habitat_mask = make_habitat_mask(image, labels_array, label)
                    raw = extractor.execute(image, habitat_mask)
                    features = {key: value for key, value in raw.items()
                                if not key.startswith("diagnostics_")}
                    diagnostics = {key: value for key, value in raw.items()
                                   if key.startswith("diagnostics_")}
                    result = block_result(state, True, features, diagnostics)
            except Exception as exc:  # noqa: BLE001
                result = block_result(state, True, error=_error_text(exc))
            base["blocks"][block_name] = result
            base[block_name + "_extractable"] = result["extractable"]
            base[block_name + "_status"] = result["status"]
            base[block_name + "_failure_class"] = result["failure_class"]
            base[block_name + "_failure_reason"] = result["failure_reason"]
        base["case_any_technical_failure"] = int(any(
            value["failure_class"] == "technical_failure"
            for value in base["blocks"].values()))
        return base
    except Exception as exc:  # noqa: BLE001
        reason = _error_text(exc)
        base["input_failure_reason"] = reason
        for block_name, _label in BLOCKS:
            base["blocks"][block_name] = block_result(
                base["structural_state"], True, error=reason)
            base[block_name + "_failure_reason"] = reason
        return base


def _write_csv(path, frame):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def make_block_frame(rows, block_name, feature_names):
    output = []
    present_key = "H_low_present" if block_name == "R_low" else "H_high_present"
    for row in rows:
        result = row["blocks"][block_name]
        item = {
            "影像号": row["影像号"],
            "reader": row["reader"],
            "structural_state": row["structural_state"],
            "habitat_present": (int(row[present_key])
                                if row[present_key] is not None else np.nan),
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


def make_diagnostics_frame(rows, block_name, diagnostic_names):
    output = []
    for row in rows:
        result = row["blocks"][block_name]
        item = {
            "影像号": row["影像号"], "reader": row["reader"],
            "structural_state": row["structural_state"],
            "status": result["status"],
            "failure_class": result["failure_class"],
            "failure_reason": result["failure_reason"],
        }
        item.update({key: result["diagnostics"].get(key, np.nan)
                     for key in diagnostic_names})
        output.append(item)
    return pd.DataFrame(output, columns=["影像号", "reader", "structural_state",
                                         "status", "failure_class", "failure_reason"]
                        + list(diagnostic_names))


def summarize(rows, elapsed, feature_names, diagnostic_names):
    n = len(rows)
    summary = {
        "target_cases": n,
        "completed_case_records": len(rows),
        "dual_habitat_cases": sum(x["structural_state"] == "dual-habitat" for x in rows),
        "single_H_low_cases": sum(x["structural_state"] == "single-H-low" for x in rows),
        "single_H_high_cases": sum(x["structural_state"] == "single-H-high" for x in rows),
        "input_technical_failure_cases": sum(bool(x["input_failure_reason"]) for x in rows),
        "R_low_structural_absence_cases": sum(
            x["blocks"]["R_low"]["failure_class"] == "structural_absence" for x in rows),
        "R_high_structural_absence_cases": sum(
            x["blocks"]["R_high"]["failure_class"] == "structural_absence" for x in rows),
        "R_low_extractable_cases": sum(x["R_low_extractable"] == 1 for x in rows),
        "R_high_extractable_cases": sum(x["R_high_extractable"] == 1 for x in rows),
        "R_low_technical_failure_cases": sum(
            x["blocks"]["R_low"]["failure_class"] == "technical_failure" for x in rows),
        "R_high_technical_failure_cases": sum(
            x["blocks"]["R_high"]["failure_class"] == "technical_failure" for x in rows),
        "case_any_technical_failure_cases": sum(x["case_any_technical_failure"] for x in rows),
        "R_low_feature_count": len(feature_names),
        "R_high_feature_count": len(feature_names),
        "R_low_diagnostic_count": len(diagnostic_names),
        "R_high_diagnostic_count": len(diagnostic_names),
        "elapsed_seconds": round(float(elapsed), 3),
        "outcome_columns_read": False,
        "clinical_data_read": False,
        "B_data_read": False,
    }
    return pd.DataFrame([{"metric": key, "value": value}
                         for key, value in summary.items()])


def run(args):
    started = time.perf_counter()
    config = load_config()
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be positive")
    validate_frozen_lock()
    ids = load_case_ids()
    map_rows = load_map_rows()
    if set(ids) != set(map_rows):
        raise RuntimeError("A cohort and frozen map manifest are not identical")
    if args.ids:
        requested = [item.strip() for item in args.ids.split(",") if item.strip()]
        missing = sorted(set(requested) - set(ids))
        if missing:
            raise RuntimeError("requested IDs are not in A technical cohort")
        ids = sorted(set(requested))
    if args.limit is not None:
        ids = ids[:args.limit]
    out = os.path.abspath(args.out_root or DEFAULT_OUT)
    os.makedirs(out, exist_ok=True)
    extractor = featureextractor.RadiomicsFeatureExtractor(extractor_settings(config))
    rows = []
    for index, pid in enumerate(ids, 1):
        rows.append(run_case(pid, extractor, map_rows[pid]))
        if not args.quiet:
            print("processed %d/%d" % (index, len(ids)), flush=True)
    elapsed = time.perf_counter() - started
    feature_names = sorted(set(key for row in rows for block in row["blocks"].values()
                               for key in block["features"]))
    diagnostic_names = sorted(set(key for row in rows for block in row["blocks"].values()
                                  for key in block["diagnostics"]))

    availability_columns = [
        "影像号", "reader", "structural_state", "H_low_present", "H_high_present",
        "R_low_extractable", "R_high_extractable", "R_low_status", "R_high_status",
        "R_low_failure_class", "R_high_failure_class", "R_low_failure_reason",
        "R_high_failure_reason", "case_any_technical_failure", "input_failure_reason",
    ]
    availability = pd.DataFrame(rows, columns=availability_columns)
    _write_csv(os.path.join(out, "case_availability.csv"), availability)
    for block_name, _label in BLOCKS:
        _write_csv(os.path.join(out, block_name + "_features.csv"),
                   make_block_frame(rows, block_name, feature_names))
        _write_csv(os.path.join(out, block_name + "_diagnostics.csv"),
                   make_diagnostics_frame(rows, block_name, diagnostic_names))
    failures = []
    for row in rows:
        for block_name, _label in BLOCKS:
            result = row["blocks"][block_name]
            if result["failure_class"] == "technical_failure":
                failures.append({"影像号": row["影像号"], "reader": row["reader"],
                                 "block": block_name, "failure_class": "technical_failure",
                                 "failure_reason": result["failure_reason"]})
    _write_csv(os.path.join(out, "technical_failures.csv"), pd.DataFrame(
        failures, columns=["影像号", "reader", "block", "failure_class", "failure_reason"]))
    _write_csv(os.path.join(out, "summary.csv"),
               summarize(rows, elapsed, feature_names, diagnostic_names))

    metadata = {
        "stage": "W02",
        "analysis_id": config["analysis_id"],
        "created_at_epoch": time.time(),
        "pyradiomics_version": getattr(radiomics, "__version__", "unknown"),
        "config_sha256": sha256(CONFIG_PATH),
        "technical_freeze_lock_sha256": sha256(FREEZE_LOCK),
        "technical_cohort_manifest_sha256": sha256(COHORT),
        "habitat_map_manifest_sha256": sha256(MAP_MANIFEST),
        "target_cases": len(ids),
        "reader": "R1",
        "input_scope": "W01_frozen_muscle_normalized_T2WI_tumor_ROI_and_SLIC_labels",
        "outcome_blind": True,
        "clinical_data_read": False,
        "outcome_columns_read": False,
        "B_data_read": False,
        "re_normalization": False,
        "re_resampling": False,
        "bin_width_reestimated": False,
        "feature_classes": FEATURE_CLASSES,
        "feature_count_per_block": len(feature_names),
        "diagnostic_count_per_block": len(diagnostic_names),
    }
    with open(os.path.join(out, "run_metadata.json.tmp"), "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(os.path.join(out, "run_metadata.json.tmp"),
               os.path.join(out, "run_metadata.json"))
    with open(os.path.join(out, "feature_schema.json.tmp"), "w", encoding="utf-8") as handle:
        json.dump({"feature_classes": FEATURE_CLASSES,
                   "feature_names": feature_names,
                   "diagnostic_names": diagnostic_names,
                   "blocks": [name for name, _label in BLOCKS],
                   "structural_absence_value": None,
                   "technical_failure_value": None},
                  handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(os.path.join(out, "feature_schema.json.tmp"),
               os.path.join(out, "feature_schema.json"))
    output_names = ["case_availability.csv", "R_low_features.csv",
                    "R_high_features.csv", "R_low_diagnostics.csv",
                    "R_high_diagnostics.csv", "technical_failures.csv",
                    "summary.csv", "run_metadata.json", "feature_schema.json"]
    output_manifest = {"stage": "W02", "files": {}}
    for name in output_names:
        path = os.path.join(out, name)
        output_manifest["files"][name] = {
            "bytes": os.path.getsize(path),
            "sha256": sha256(path),
        }
    with open(os.path.join(out, "output_manifest.json.tmp"), "w", encoding="utf-8") as handle:
        json.dump(output_manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(os.path.join(out, "output_manifest.json.tmp"),
               os.path.join(out, "output_manifest.json"))
    print("W02 complete: cases=%d elapsed_seconds=%.1f output=%s" %
          (len(ids), elapsed, out))


def main():
    parser = argparse.ArgumentParser(description="Outcome-blind W02 H-low/H-high Original radiomics")
    parser.add_argument("--limit", type=int, help="process the first N A cases for timing/smoke testing")
    parser.add_argument("--ids", help="comma-separated A technical IDs for a controlled smoke test")
    parser.add_argument("--out-root", help="local output directory override")
    parser.add_argument("--quiet", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
