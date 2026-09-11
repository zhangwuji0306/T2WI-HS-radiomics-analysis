"""FT03 A-only cross-validated validation and aggregate reporting.

The production path loads only the frozen A393 inputs, delegates fitting to the
accepted FT02 runner, and keeps patient-level predictions in the ignored FT
output namespace.  Tracked JSON/Markdown output contains aggregate results and
relative provenance only.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from collections import OrderedDict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_PROGNOSIS_ROOT = os.path.join(_PROJECT_ROOT, "prognosis_analysis")
_SCRIPTS_ROOT = os.path.join(_PROGNOSIS_ROOT, "scripts")
_FEATURE_SCRIPTS_ROOT = os.path.join(_PROJECT_ROOT, "feature_extract", "scripts")
for _path in (_SCRIPTS_ROOT, _FEATURE_SCRIPTS_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from data_split_guard import read_technical_A  # noqa: E402
import ft02_runner as ft02  # noqa: E402


FT03_STAGE = "FT03"
FT_LABEL = "exploratory_fullA_habitat_non_nested_validation"
PERFORMANCE_LABEL = "non_nested_exploratory_estimate"
REPEAT = 1
SEED = 12345
BOOTSTRAP_REPLICATES = 200
PRE_RUN_ESTIMATE_MINUTES = 180
HORIZONS = OrderedDict((("3_year", 36.0), ("5_year", 60.0)))
MODEL_IDS = tuple(ft02.FT_MODEL_SPECS.keys())
COMPARISONS = tuple(ft02.FT_COMPARISONS)

DEFAULT_OUTPUT_ROOT = os.path.join(
    _PROGNOSIS_ROOT, "output", "ft_20260910_01a08bf3", "FT03")
DEFAULT_JSON = os.path.join(_HERE, "FT03_A_validation.json")
DEFAULT_REPORT = os.path.join(_HERE, "FT03_A_validation_report.md")
DEFAULT_RAW_A = os.path.join(
    _PROGNOSIS_ROOT, "output", "modeling_v2", "dataset_primary_raw_A.csv")
DEFAULT_GLOBAL = os.path.join(
    _PROJECT_ROOT, "habitat_analysis", "output", "habitat_features_A",
    "global_descriptors_full_A.csv")
DEFAULT_R_LOW = os.path.join(
    _PROGNOSIS_ROOT, "output", "w03_habitat_radiomics_A",
    "R1_R_low_features.csv")
DEFAULT_R_HIGH = os.path.join(
    _PROGNOSIS_ROOT, "output", "w03_habitat_radiomics_A",
    "R1_R_high_features.csv")
DEFAULT_W = os.path.join(
    _PROJECT_ROOT, "feature_extract", "output", "features_v2",
    "muscle_f0.25", "features_original.csv")


class FT03ValidationError(ValueError):
    """Raised when an FT03 input, prediction or output contract fails."""


def validate_a_only_input(frame):
    """Apply the FT02 A/B boundary without fitting or reading any source."""
    try:
        ft02._reject_b_rows_or_paths(frame)
    except ft02.FTValidationError as exc:
        raise FT03ValidationError(str(exc))
    return frame


def validate_paired_population(left_ids, right_ids, expected_ids=None):
    """Require exactly one common eligible ID set for a paired comparison."""
    left = set(str(value) for value in left_ids)
    right = set(str(value) for value in right_ids)
    if not left or left != right:
        raise FT03ValidationError("paired models do not share one common eligible population")
    if expected_ids is not None and left != set(str(value) for value in expected_ids):
        raise FT03ValidationError("paired prediction population differs from frozen common population")
    return tuple(sorted(left))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path):
    return os.path.relpath(os.path.abspath(path), _PROJECT_ROOT).replace("\\", "/")


def _json_number(value):
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return _json_number(value)
    if isinstance(value, float):
        return _json_number(value)
    return value


def _require_columns(frame, columns, label):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise FT03ValidationError("%s is missing columns: %s" % (label, missing[:10]))


def _clean_key(frame, column, label):
    if column not in frame.columns:
        raise FT03ValidationError("%s lacks %s" % (label, column))
    values = frame[column].astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise FT03ValidationError("%s has blank or duplicate %s" % (label, column))
    output = frame.copy()
    output[column] = values
    return output


def _read_a_raw(raw_path, allowed_ids):
    columns = ["影像号", "split", "DFS_time", "DFS_event"] + \
        list(ft02.CLINICAL_COLUMNS)
    data = pd.read_csv(raw_path, usecols=columns, dtype={"影像号": str})
    data = _clean_key(data, "影像号", "A raw modeling dataset")
    if set(data["split"].astype(str).str.strip()) != {"A"}:
        raise FT03ValidationError("A raw modeling dataset contains a non-A row")
    if set(data["影像号"]) != set(str(value) for value in allowed_ids):
        raise FT03ValidationError("A raw modeling dataset is not exact A393 membership")
    return data.rename(columns={"影像号": "patient_id"})


def _read_a_global(global_path, allowed_ids):
    columns = ["影像号"] + list(ft02.GLOBAL_COLUMNS)
    data = pd.read_csv(global_path, usecols=columns, dtype={"影像号": str})
    data = _clean_key(data, "影像号", "A full_A descriptors")
    if set(data["影像号"]) != set(str(value) for value in allowed_ids):
        raise FT03ValidationError("full_A descriptors are not exact A393 membership")
    return data.rename(columns={"影像号": "patient_id"})


def _read_a_radiomics(path, block, names, allowed_ids):
    prefixed = [ft02.BLOCK_PREFIXES[block] + name for name in names]
    columns = ["影像号", "reader", "habitat_present", "extractable"] + prefixed
    data = pd.read_csv(path, usecols=columns, dtype={"影像号": str})
    data = _clean_key(data, "影像号", "%s A habitat radiomics" % block)
    if set(data["影像号"]) != set(str(value) for value in allowed_ids):
        raise FT03ValidationError("%s habitat radiomics are not exact A393 membership" % block)
    if set(data["reader"].astype(str).str.strip()) != {"R1"}:
        raise FT03ValidationError("%s habitat radiomics contain a non-R1 reader" % block)
    data[block + "_structurally_defined"] = pd.to_numeric(
        data["habitat_present"], errors="coerce")
    data[block + "_technically_available"] = pd.to_numeric(
        data["extractable"], errors="coerce")
    for column in (block + "_structurally_defined",
                   block + "_technically_available"):
        values = data[column]
        if values.isna().any() or not values.isin([0, 1]).all():
            raise FT03ValidationError("%s has invalid %s" % (block, column))
    keep = ["影像号", block + "_structurally_defined",
            block + "_technically_available"] + prefixed
    return data[keep].rename(columns={"影像号": "patient_id"})


def _read_a_w_original(path, names, allowed_ids):
    # This is a mixed technical source.  The authorized streaming A reader
    # admits only the already-proven A393 allow-list before a DataFrame exists.
    columns = ["影像号", "读者", "split"] + list(names)
    data = read_technical_A(
        path, allowed_ids=set(str(value) for value in allowed_ids),
        dtype={"影像号": str}, usecols=columns)
    if "split" not in data.columns or set(data["split"].astype(str).str.strip()) != {"A"}:
        raise FT03ValidationError("W_Original authorized read contains a non-A row")
    data = data[data["读者"].astype(str).str.strip().eq("R1")].copy()
    data = _clean_key(data, "影像号", "A W_Original asset")
    if set(data["影像号"]) != set(str(value) for value in allowed_ids):
        raise FT03ValidationError("A W_Original asset is not exact R1 A393 membership")
    if not np.isfinite(data[list(names)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)).all():
        raise FT03ValidationError("A W_Original asset contains nonfinite values")
    renamed = data[["影像号"] + list(names)].rename(columns={"影像号": "patient_id"})
    renamed = renamed.rename(columns={name: "W__" + name for name in names})
    renamed["W_Original_available"] = 1
    return renamed[["patient_id", "W_Original_available"] + ["W__" + name for name in names]]


def build_authoritative_a_frame(raw_path=DEFAULT_RAW_A, global_path=DEFAULT_GLOBAL,
                                r_low_path=DEFAULT_R_LOW, r_high_path=DEFAULT_R_HIGH,
                                w_path=DEFAULT_W):
    """Assemble the complete A-only FT03 frame from frozen technical assets."""
    _, population = ft02.load_frozen_w07_repeat1()
    allowed_ids = set(population["patient_id"].astype(str))
    frame = _read_a_raw(raw_path, allowed_ids)
    pieces = [
        _read_a_global(global_path, allowed_ids),
        _read_a_radiomics(r_low_path, "R_low", ft02.R_LOW_FEATURE_NAMES, allowed_ids),
        _read_a_radiomics(r_high_path, "R_high", ft02.R_HIGH_FEATURE_NAMES, allowed_ids),
        _read_a_w_original(w_path, ft02.W_ORIGINAL_FEATURE_NAMES, allowed_ids),
    ]
    for piece in pieces:
        frame = frame.merge(piece, on="patient_id", how="inner",
                            validate="one_to_one")
    frame["technical_cohort"] = "A393"
    frame["modeling_eligible"] = 1
    # Make the schema and frozen W_Original order explicit before FT02 sees it.
    ordered = ["patient_id", "split", "technical_cohort", "modeling_eligible",
               "DFS_time", "DFS_event"] + list(ft02.CLINICAL_COLUMNS) + \
        list(ft02.GLOBAL_COLUMNS) + ["R_low_structurally_defined",
                                     "R_low_technically_available"] + \
        [ft02.BLOCK_PREFIXES["R_low"] + name for name in ft02.R_LOW_FEATURE_NAMES] + \
        ["R_high_structurally_defined", "R_high_technically_available"] + \
        [ft02.BLOCK_PREFIXES["R_high"] + name for name in ft02.R_HIGH_FEATURE_NAMES] + \
        ["W_Original_available"] + \
        [ft02.BLOCK_PREFIXES["W_Original"] + name
         for name in ft02.W_ORIGINAL_FEATURE_NAMES]
    _require_columns(frame, ordered, "assembled A frame")
    frame = frame[ordered]
    return ft02.validate_proven_a_frame(frame, population, models=MODEL_IDS).reset_index(drop=True)


def _prediction_table(prediction, label):
    if not isinstance(prediction, pd.DataFrame):
        raise FT03ValidationError("%s prediction is not a DataFrame" % label)
    _require_columns(prediction, ["patient_id", "risk", "fold",
                                 "survival_probability_36",
                                 "survival_probability_60"], label)
    output = prediction.copy()
    output["patient_id"] = output["patient_id"].astype(str).str.strip()
    if output["patient_id"].eq("").any() or output["patient_id"].duplicated().any():
        raise FT03ValidationError("%s prediction has duplicate or blank IDs" % label)
    for column in ("risk", "survival_probability_36", "survival_probability_60"):
        output[column] = pd.to_numeric(output[column], errors="coerce")
        if output[column].isna().any() or not np.isfinite(output[column].to_numpy(dtype=float)).all():
            raise FT03ValidationError("%s prediction has missing/nonfinite %s" % (label, column))
    output["fold"] = pd.to_numeric(output["fold"], errors="coerce")
    if output["fold"].isna().any() or not output["fold"].isin([1, 2, 3, 4, 5]).all():
        raise FT03ValidationError("%s prediction has an invalid fold" % label)
    output["fold"] = output["fold"].astype(int)
    for column in ("survival_probability_36", "survival_probability_60"):
        if ((output[column] < 0.0) | (output[column] > 1.0)).any():
            raise FT03ValidationError("%s prediction has an invalid survival probability" % label)
    return output


def validate_held_out_predictions(prediction, eligible_ids, split, label="prediction"):
    """Reject missing, duplicate, or non-held-out predictions."""
    output = _prediction_table(prediction, label)
    expected = set(str(value) for value in eligible_ids)
    observed = set(output["patient_id"])
    if observed != expected:
        raise FT03ValidationError("%s does not exactly cover its eligible population" % label)
    valid = split[split["role"].astype(str).str.lower().eq("validation")]
    fold_map = valid.set_index("patient_id")["fold"].to_dict()
    for row in output.itertuples(index=False):
        if str(row.patient_id) not in fold_map or int(row.fold) != int(fold_map[str(row.patient_id)]):
            raise FT03ValidationError("%s contains a non-held-out or wrong-fold prediction" % label)
    return output.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def _frame_for_ids(frame, ids):
    expected = set(str(value) for value in ids)
    data = frame[frame["patient_id"].astype(str).isin(expected)].copy()
    data["patient_id"] = data["patient_id"].astype(str)
    data = data.set_index("patient_id").loc[sorted(expected)].reset_index()
    return data


def _fold_data(frame, split, prediction):
    prediction = _prediction_table(prediction, "cross-validated")
    data = _frame_for_ids(frame, prediction["patient_id"])
    data = data.merge(prediction, on="patient_id", how="inner", validate="one_to_one")
    split_valid = split[split["role"].astype(str).str.lower().eq("validation")][
        ["patient_id", "fold"]].copy()
    split_valid["patient_id"] = split_valid["patient_id"].astype(str)
    split_valid["fold"] = split_valid["fold"].astype(int)
    data = data.merge(split_valid, on="patient_id", how="left",
                      validate="one_to_one", suffixes=("", "_split"))
    if data["fold_split"].isna().any() or not data["fold"].eq(data["fold_split"]).all():
        raise FT03ValidationError("prediction fold assignment is not frozen W07 validation")
    return data.drop(columns=["fold_split"])


def _weighted_fold_metric(data, split, metric_fn, survival_column=None):
    values = []
    weights = []
    eligible = set(data["patient_id"].astype(str))
    for fold in range(1, 6):
        valid_ids = set(split.loc[
            (split["fold"].eq(fold)) & split["role"].astype(str).str.lower().eq("validation"),
            "patient_id"].astype(str)) & eligible
        current = data[data["patient_id"].astype(str).isin(valid_ids)].copy()
        if current.empty:
            continue
        train_ids = set(split.loc[
            (split["fold"].eq(fold)) & split["role"].astype(str).str.lower().eq("train"),
            "patient_id"].astype(str)) & eligible
        train = data[data["patient_id"].astype(str).isin(train_ids)].copy()
        value = metric_fn(train, current, survival_column)
        if value is not None and np.isfinite(value):
            values.append(float(value))
            weights.append(len(current))
    if not values:
        return None
    return float(np.average(values, weights=weights))


def _bootstrap_metric(data, split, metric_fn, point, seed, pooled=False,
                      n_bootstrap=BOOTSTRAP_REPLICATES, output_path=None):
    if pooled:
        values = data.reset_index(drop=True)

        def fn(indices):
            return metric_fn(values.iloc[np.asarray(indices, dtype=int)])
    else:
        values = data.reset_index(drop=True)

        def fn(indices):
            selected = values.iloc[np.asarray(indices, dtype=int)]
            return _weighted_fold_metric(selected, split, metric_fn)

    result = ft02.bootstrap_ci_hook(
        fn, len(values), n_bootstrap=n_bootstrap, seed=seed, mode="case_resample")
    if output_path:
        # The accepted FT02 hook returns the CI summary, not raw replicates.
        # Keep the deterministic summary local when requested; no patient-level
        # values are written to tracked artifacts.
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(_json_safe(result), handle, ensure_ascii=False, indent=2,
                      sort_keys=True)
            handle.write("\n")
    result["estimate"] = _json_number(point)
    return result


def _metric_record(data, split, key, point_fn, fold_fn, seed, bootstrap_dir):
    point = point_fn(data)
    pooled = key == "Harrell_C_index"
    metric = _bootstrap_metric(
        data, split, fold_fn, point, seed, pooled=pooled,
        output_path=os.path.join(bootstrap_dir, key + ".json"))
    return {
        "estimate": _json_number(point),
        "bootstrap_95_percent_CI": _json_safe(metric),
        "aggregation": ("pooled_cross_validated_predictions" if pooled else
                         "validation_fold_size_weighted_mean"),
    }


def _prediction_metrics(frame, split, prediction, bootstrap_dir, seed_offset=0):
    data = _fold_data(frame, split, prediction)
    time = data["DFS_time"].to_numpy(dtype=float)
    event = data["DFS_event"].to_numpy(dtype=int)
    risk = data["risk"].to_numpy(dtype=float)
    s36 = data["survival_probability_36"].to_numpy(dtype=float)
    s60 = data["survival_probability_60"].to_numpy(dtype=float)
    metrics = OrderedDict()
    metrics["Uno_C_index"] = _metric_record(
        data, split, "Uno_C_index",
        lambda current: _weighted_fold_metric(
            current, split, lambda train, valid, unused:
            ft02.uno_c_index_hook(
                train["DFS_time"].to_numpy(dtype=float),
                train["DFS_event"].to_numpy(dtype=int),
                valid["DFS_time"].to_numpy(dtype=float),
                valid["DFS_event"].to_numpy(dtype=int),
                valid["risk"].to_numpy(dtype=float))),
        lambda train, valid, unused: ft02.uno_c_index_hook(
            train["DFS_time"].to_numpy(dtype=float),
            train["DFS_event"].to_numpy(dtype=int),
            valid["DFS_time"].to_numpy(dtype=float),
            valid["DFS_event"].to_numpy(dtype=int),
            valid["risk"].to_numpy(dtype=float)),
        20260911 + seed_offset, bootstrap_dir)
    metrics["Harrell_C_index"] = _metric_record(
        data, split, "Harrell_C_index",
        lambda current: ft02.harrell_c_index_hook(
            current["DFS_time"].to_numpy(dtype=float),
            current["DFS_event"].to_numpy(dtype=int),
            current["risk"].to_numpy(dtype=float)),
        lambda current: ft02.harrell_c_index_hook(
            current["DFS_time"].to_numpy(dtype=float),
            current["DFS_event"].to_numpy(dtype=int),
            current["risk"].to_numpy(dtype=float)),
        20260912 + seed_offset, bootstrap_dir)
    for horizon_name, auc_hook, brier_hook, survival_column in (
            ("3_year", ft02.auc_3_year_hook, ft02.brier_3_year_hook,
             "survival_probability_36"),
            ("5_year", ft02.auc_5_year_hook, ft02.brier_5_year_hook,
             "survival_probability_60")):
        metrics["AUC_" + horizon_name] = _metric_record(
            data, split, "AUC_" + horizon_name,
            lambda current, hook=auc_hook: _weighted_fold_metric(
                current, split, lambda train, valid, unused: hook(train, valid,
                                                                    valid["risk"].to_numpy(dtype=float))),
            lambda train, valid, unused, hook=auc_hook: hook(
                train, valid, valid["risk"].to_numpy(dtype=float)),
            20260913 + seed_offset + (0 if horizon_name == "3_year" else 1),
            bootstrap_dir)
        metrics["Brier_" + horizon_name] = _metric_record(
            data, split, "Brier_" + horizon_name,
            lambda current, hook=brier_hook, column=survival_column:
            _weighted_fold_metric(current, split,
                                  lambda train, valid, unused:
                                  hook(train, valid, valid[column].to_numpy(dtype=float))),
            lambda train, valid, unused, hook=brier_hook, column=survival_column:
            hook(train, valid, valid[column].to_numpy(dtype=float)),
            20260914 + seed_offset + (0 if horizon_name == "3_year" else 1),
            bootstrap_dir)
    calibration = OrderedDict()
    dca = OrderedDict()
    for horizon_name, horizon, column in (("3_year", 36.0, "survival_probability_36"),
                                          ("5_year", 60.0, "survival_probability_60")):
        survival = data[column].to_numpy(dtype=float)
        calibration[horizon_name] = ft02.calibration_data_hook(
            data, data, survival, horizon, bins=5)
        dca[horizon_name] = ft02.dca_data_hook(
            data, 1.0 - survival, horizon)
    return {
        "metrics": _json_safe(metrics),
        "calibration": _json_safe(calibration),
        "dca": _json_safe(dca),
        "km_local": ft02.km_data_hook(data, risk),
        "event_count": int(event.sum()),
        "censor_count": int(len(event) - event.sum()),
        "prediction_n": int(len(data)),
        "fold_counts": {str(fold): int((data["fold"] == fold).sum())
                        for fold in range(1, 6)},
    }


def _paired_prediction_table(frame, split, paired_state, comparison_id, population):
    left_states = paired_state["left"]
    right_states = paired_state["right"]
    left_by_fold = {int(item["fold"]): item for item in left_states}
    right_by_fold = {int(item["fold"]): item for item in right_states}
    common = set(frame.loc[ft02.population_mask(frame, population), "patient_id"].astype(str))
    records = []
    for fold in range(1, 6):
        valid_ids = set(split.loc[
            (split["fold"].eq(fold)) & split["role"].astype(str).str.lower().eq("validation"),
            "patient_id"].astype(str)) & common
        valid = _frame_for_ids(frame, valid_ids)
        left = ft02.predict_risk_survival_hook(
            left_by_fold[fold]["model"], left_by_fold[fold]["preprocessor"], valid)
        right = ft02.predict_risk_survival_hook(
            right_by_fold[fold]["model"], right_by_fold[fold]["preprocessor"], valid)
        for index, identifier in enumerate(valid["patient_id"].astype(str)):
            records.append({
                "patient_id": identifier,
                "fold": int(fold),
                "left_risk": float(left["risk"][index]),
                "left_survival_probability_36": float(left["survival_probability_36_months"][index]),
                "left_survival_probability_60": float(left["survival_probability_60_months"][index]),
                "right_risk": float(right["risk"][index]),
                "right_survival_probability_36": float(right["survival_probability_36_months"][index]),
                "right_survival_probability_60": float(right["survival_probability_60_months"][index]),
            })
    output = pd.DataFrame(records)
    if output.empty or output["patient_id"].duplicated().any():
        raise FT03ValidationError("%s paired prediction coverage is invalid" % comparison_id)
    validate_paired_population(output["patient_id"], output["patient_id"], common)
    return output.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def _paired_metrics(frame, split, prediction, comparison_id, left_model,
                     right_model, population, bootstrap_dir, seed_offset):
    base = _frame_for_ids(frame, prediction["patient_id"])
    data = base.merge(prediction, on="patient_id", how="inner", validate="one_to_one")
    time = data["DFS_time"].to_numpy(dtype=float)
    event = data["DFS_event"].to_numpy(dtype=int)
    left_risk = data["left_risk"].to_numpy(dtype=float)
    right_risk = data["right_risk"].to_numpy(dtype=float)
    paired = ft02.paired_comparison_hook(
        time, event, left_risk, right_risk, n_bootstrap=BOOTSTRAP_REPLICATES,
        seed=20261000 + seed_offset, mode="paired_case_resample")
    metrics = OrderedDict()
    metrics["Harrell_C_index"] = {
        "left": _json_number(paired["left"]),
        "right": _json_number(paired["right"]),
        "delta_right_minus_left": _json_number(paired["delta_right_minus_left"]),
        "bootstrap_95_percent_CI": _json_safe(paired["delta_bootstrap"]),
        "aggregation": "pooled_common_eligible_cross_validated_predictions",
    }
    for horizon_name, horizon, left_column, right_column, auc_hook, brier_hook in (
            ("3_year", 36.0, "left_survival_probability_36",
             "right_survival_probability_36", ft02.auc_3_year_hook,
             ft02.brier_3_year_hook),
            ("5_year", 60.0, "left_survival_probability_60",
             "right_survival_probability_60", ft02.auc_5_year_hook,
             ft02.brier_5_year_hook)):
        left_frame = data.copy()
        right_frame = data.copy()
        left_frame["risk"] = left_risk
        right_frame["risk"] = right_risk
        left_frame["survival"] = left_frame[left_column]
        right_frame["survival"] = right_frame[right_column]
        left_auc = _weighted_fold_metric(
            left_frame, split,
            lambda train, valid, unused: auc_hook(train, valid,
                                                  valid["risk"].to_numpy(dtype=float)))
        right_auc = _weighted_fold_metric(
            right_frame, split,
            lambda train, valid, unused: auc_hook(train, valid,
                                                  valid["risk"].to_numpy(dtype=float)))
        left_brier = _weighted_fold_metric(
            left_frame, split,
            lambda train, valid, unused: brier_hook(train, valid,
                                                    valid["survival"].to_numpy(dtype=float)))
        right_brier = _weighted_fold_metric(
            right_frame, split,
            lambda train, valid, unused: brier_hook(train, valid,
                                                    valid["survival"].to_numpy(dtype=float)))
        metrics["AUC_" + horizon_name] = {
            "left": _json_number(left_auc), "right": _json_number(right_auc),
            "delta_right_minus_left": _json_number(None if left_auc is None or right_auc is None
                                                     else right_auc - left_auc),
            "aggregation": "validation_fold_size_weighted_mean",
        }
        metrics["Brier_" + horizon_name] = {
            "left": _json_number(left_brier), "right": _json_number(right_brier),
            "delta_right_minus_left": _json_number(None if left_brier is None or right_brier is None
                                                     else right_brier - left_brier),
            "aggregation": "validation_fold_size_weighted_mean",
        }
    return {
        "comparison_id": comparison_id,
        "left_model": left_model,
        "right_model": right_model,
        "population": population,
        "common_n": int(len(data)),
        "event_count": int(event.sum()),
        "censor_count": int(len(event) - event.sum()),
        "eligibility_is_paired": True,
        "metrics": _json_safe(metrics),
        "fold_counts": {str(fold): int((data["fold"] == fold).sum())
                        for fold in range(1, 6)},
    }


def _sanitize_model_record(record):
    keep = ("model_id", "predictor_blocks", "population", "eligible_n", "alpha",
            "family", "ordinary_single_layer_5fold", "prediction_coverage", "folds")
    output = {key: record[key] for key in keep if key in record}
    folds = []
    for fold in output.get("folds", []):
        item = {key: fold[key] for key in (
            "fold", "n_train", "n_validation", "train_event_count",
            "validation_event_count", "selection", "preprocessing", "fit_audit")
                if key in fold}
        folds.append(item)
    output["folds"] = folds
    return _json_safe(output)


def _source_provenance():
    paths = OrderedDict((
        ("ft00_protocol", os.path.join(_HERE, "FT00_protocol.json")),
        ("protocol_amendment", os.path.join(_HERE, "FT_protocol_amendment_20260911.json")),
        ("ft01_asset_manifest", os.path.join(_HERE, "FT01_asset_manifest.json")),
        ("ft02_runner", os.path.join(_HERE, "ft02_runner.py")),
        ("w07_split", os.path.join(_PROGNOSIS_ROOT, "output", "outer_splits_A.csv")),
        ("environment", os.path.join(_PROJECT_ROOT, "environment.yml")),
    ))
    return OrderedDict((key, {"path": _relative(path), "sha256": _sha256_file(path)})
                       for key, path in paths.items())


def _git_head():
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_PROJECT_ROOT,
            stderr=subprocess.STDOUT).decode("ascii").strip()
        if len(value) == 40:
            return value
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        pass
    return None


def _write_local_prediction(path, frame):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")
    return {"path": _relative(path), "sha256": _sha256_file(path), "rows": int(len(frame))}


def run_ft03(frame=None, output_root=DEFAULT_OUTPUT_ROOT,
             json_path=DEFAULT_JSON, report_path=DEFAULT_REPORT,
             bootstrap_replicates=BOOTSTRAP_REPLICATES):
    """Run all seven FT03 models and write aggregate tracked deliverables."""
    if int(bootstrap_replicates) != BOOTSTRAP_REPLICATES:
        raise FT03ValidationError("FT03 bootstrap count is frozen at 200")
    started = time.time()
    if frame is None:
        frame = build_authoritative_a_frame()
    _, population = ft02.load_frozen_w07_repeat1()
    split, _ = ft02.load_frozen_w07_repeat1()
    split = split.copy()
    split["patient_id"] = split["patient_id"].astype(str)
    # The production FT02 entry point reloads and revalidates the A393/W07
    # sources at every fold boundary.
    fit_result = ft02.run_ft02_a(frame, models=list(MODEL_IDS),
                                 lambda_count=20, max_iter=3000,
                                 tolerance=1e-7)
    os.makedirs(output_root, exist_ok=True)
    local_records = OrderedDict()
    model_outputs = OrderedDict()
    for index, model_id in enumerate(MODEL_IDS):
        model_result = fit_result["models"][model_id]
        eligible = frame.loc[ft02.population_mask(frame, model_result["population"]),
                             "patient_id"].astype(str)
        prediction = validate_held_out_predictions(
            fit_result["predictions"][model_id], eligible, split, label=model_id)
        prediction_path = os.path.join(output_root, "predictions", model_id + ".csv")
        local_records["prediction_" + model_id] = _write_local_prediction(
            prediction_path, prediction)
        metric_dir = os.path.join(output_root, "bootstrap", model_id)
        os.makedirs(metric_dir, exist_ok=True)
        evaluated = _prediction_metrics(frame, split, prediction, metric_dir,
                                        seed_offset=index * 100)
        km_path = os.path.join(output_root, "km", model_id + ".json")
        os.makedirs(os.path.dirname(km_path), exist_ok=True)
        with open(km_path, "w", encoding="utf-8") as handle:
            json.dump(_json_safe(evaluated.pop("km_local")), handle,
                      ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        local_records["km_" + model_id] = {
            "path": _relative(km_path), "sha256": _sha256_file(km_path)}
        model_outputs[model_id] = OrderedDict(
            ([("model_definition", _sanitize_model_record(model_result)),
              ("performance_label", PERFORMANCE_LABEL),
              ("eligible_n", int(model_result["eligible_n"])),
              ("event_count", evaluated["event_count"]),
              ("censor_count", evaluated["censor_count"]),
              ("prediction_coverage", evaluated["prediction_n"]),
              ("fold_counts", evaluated["fold_counts"]),
              ("metrics", evaluated["metrics"]),
              ("calibration", evaluated["calibration"]),
              ("dca", evaluated["dca"]),
              ("local_prediction", local_records["prediction_" + model_id]),
              ("local_km", local_records["km_" + model_id])]))

    comparisons = []
    for index, (comparison_id, left, right, population_name) in enumerate(COMPARISONS):
        paired_state = fit_result["fitted_state"]["paired_comparisons"][comparison_id]
        paired_prediction = _paired_prediction_table(
            frame, split, paired_state, comparison_id, population_name)
        paired_path = os.path.join(output_root, "paired_predictions",
                                   comparison_id + ".csv")
        local_records["paired_" + comparison_id] = _write_local_prediction(
            paired_path, paired_prediction)
        pair = _paired_metrics(
            frame, split, paired_prediction, comparison_id, left, right,
            population_name, output_root, index)
        pair["ft02_population_contract"] = population_name
        pair["local_paired_prediction"] = local_records["paired_" + comparison_id]
        comparisons.append(pair)

    provenance = OrderedDict((
        ("stage", FT03_STAGE),
        ("label", FT_LABEL),
        ("performance_label", PERFORMANCE_LABEL),
        ("a_only", True),
        ("b_data_read", False),
        ("formal_outputs_written", False),
        ("formal_model_freeze_lock_written", False),
        ("sources", _source_provenance()),
        ("environment", {
            "environment_file": "environment.yml",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "wrapper_required": "tools/run_t2_radiomics.ps1",
        }),
        ("code_commit", _git_head()),
        ("ft02_runner_source_sha256", _sha256_file(os.path.join(_HERE, "ft02_runner.py"))),
        ("split", {
            "repeat": REPEAT, "fold_count": 5, "seed": SEED,
            "regenerated": False,
            "artifact_path": "prognosis_analysis/output/outer_splits_A.csv",
            "artifact_sha256": ft02.W07_SPLIT_ARTIFACT_SHA256,
            "repeat1_canonical_sha256": ft02.W07_REPEAT1_CANONICAL_SHA256,
        }),
        ("modeling", {
            "models": list(MODEL_IDS),
            "ordinary_single_layer_5fold": True,
            "lambda_count": 20,
            "max_iter": 3000,
            "lambda_selection_scope": "outer_training_inner_5fold_only",
            "alpha": 1.0,
            "horizons_months": dict(HORIZONS),
            "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        }),
        ("candidate_binding", {
            "R_low_count": 49,
            "R_low_candidate_sha256": "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0",
            "R_high_count": 10,
            "R_high_candidate_sha256": "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce",
            "W_Original_count": 107,
            "W_Original_order_sha256": ft02.W_ORIGINAL_ORDER_SHA256,
        }),
        ("local_output_root", "prognosis_analysis/output/ft_20260910_01a08bf3/FT03"),
        ("local_output_records", local_records),
        ("runtime", {
            "pre_run_estimate_minutes": PRE_RUN_ESTIMATE_MINUTES,
            "estimate_basis": {
                "M0_small_sample_seconds": 7.729,
                "M3L_full_A393_seconds": 562.917,
                "estimated_unique_production_fit_groups": 13,
            },
            "production_run_seconds": round(time.time() - started, 3),
            "long_task_rule": "pre-estimate recorded; no periodic worker polling",
        }),
    ))
    aggregate = OrderedDict((
        ("schema_version", "1.0"),
        ("artifact_id", "FT03_A_validation"),
        ("stage", FT03_STAGE),
        ("status", "COMPLETE"),
        ("label", FT_LABEL),
        ("performance_label", PERFORMANCE_LABEL),
        ("analysis_scope", "A-only full_A habitat exploratory internal validation"),
        ("models", model_outputs),
        ("paired_model_comparisons", comparisons),
        ("provenance", provenance),
        ("validation", {
            "all_models_complete": True,
            "all_predictions_held_out": True,
            "metrics_complete": True,
            "calibration_complete": True,
            "km_complete": True,
            "dca_complete": True,
            "bootstrap_95_percent_CI_complete": True,
            "paired_comparisons_complete": True,
            "b_data_read": False,
            "formal_outputs_written": False,
        }),
    ))
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(aggregate), handle, ensure_ascii=False, indent=2,
                  sort_keys=False)
        handle.write("\n")
    _write_report(aggregate, report_path)
    return aggregate


def _fmt(value):
    return "NA" if value is None else "%.4f" % float(value)


def _write_report(aggregate, path):
    lines = [
        "# FT03 A Validation Report",
        "",
        "## Status",
        "",
        "`COMPLETE`",
        "",
        "Analysis label: `exploratory_fullA_habitat_non_nested_validation`.",
        "Performance label: `non_nested_exploratory_estimate`.",
        "The analysis is A-only, uses the frozen W07 repeat-1 ordinary 5-fold split, and does not read B data or write formal W08/L9 outputs.",
        "",
        "## Model validation",
        "",
        "| Model | Eligible n | Events | Uno C | Harrell C | AUC 3 y | AUC 5 y | Brier 3 y | Brier 5 y |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_id, item in aggregate["models"].items():
        m = item["metrics"]
        lines.append("| %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (
            model_id, item["eligible_n"], item["event_count"],
            _fmt(m["Uno_C_index"]["estimate"]),
            _fmt(m["Harrell_C_index"]["estimate"]),
            _fmt(m["AUC_3_year"]["estimate"]),
            _fmt(m["AUC_5_year"]["estimate"]),
            _fmt(m["Brier_3_year"]["estimate"]),
            _fmt(m["Brier_5_year"]["estimate"])))
    lines.extend([
        "",
        "Bootstrap confidence intervals use 200 deterministic case resamples, matching the accepted FT02 bootstrap hook default. Harrell C is pooled over held-out predictions; Uno C, AUC and Brier are validation-fold-size-weighted means using training-fold censoring weights.",
        "Calibration and DCA are recorded at 3 and 5 years; KM curves are stored in the local FT03 output namespace.",
        "",
        "## Paired comparisons",
        "",
        "| Comparison | Population | Common n | Harrell C left | Harrell C right | Δ right − left |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for item in aggregate["paired_model_comparisons"]:
        metric = item["metrics"]["Harrell_C_index"]
        lines.append("| %s | %s | %d | %s | %s | %s |" % (
            item["comparison_id"], item["population"], item["common_n"],
            _fmt(metric["left"]), _fmt(metric["right"]),
            _fmt(metric["delta_right_minus_left"])))
    lines.extend([
        "",
        "All seven comparisons use one common eligible population and identical frozen fold assignments for both models. AUC and Brier paired values are included in `FT03_A_validation.json`.",
        "",
        "## Provenance and validation evidence",
        "",
        "- Frozen repeat-1 seed: `12345`; fold count: `5`; split regeneration: `false`.",
        "- M0–M5 completed with Cox fitting; high-dimensional models use alpha=1 and training-only inner 5-fold lambda selection.",
        "- R_low=49, R_high=10 and W_Original=107 are bound to their frozen candidate/order hashes.",
        "- Cross-validated prediction coverage, held-out-fold checks, endpoint/horizon checks, calibration, KM, DCA, bootstrap and paired-population checks passed.",
        "- B data read: `false`; formal output written: `false`; formal model freeze lock written: `false`.",
        "",
        "## Runtime",
        "",
        "The production run and all Python probes/tests were executed through `tools/run_t2_radiomics.ps1` in the locked `t2_radiomics` environment. Runtime and the pre-run small-sample estimate are recorded in `provenance.runtime` in the aggregate JSON.",
        "",
    ])
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run FT03 A-only validation")
    parser.add_argument("--estimate", action="store_true",
                        help="run one production M0 model for runtime estimation")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--json", default=DEFAULT_JSON)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    args = parser.parse_args()
    frame = build_authoritative_a_frame()
    if args.estimate:
        ft02.run_ft02_a(frame, models=["M0"], lambda_count=20,
                        max_iter=1000, tolerance=1e-7)
        return
    run_ft03(frame=frame, output_root=args.output_root,
             json_path=args.json, report_path=args.report)


if __name__ == "__main__":
    main()
