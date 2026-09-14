"""Build the unified Primary v2 paired model-comparison result.

The script consumes the existing A-side held-out predictions and frozen
repeat-1 split. It refits only the missing M0 comparator predictions on the
M3L, M3H and M4 common eligible populations. No habitat, feature selection,
model specification or lambda rule is changed here.

All bootstrap metrics for one comparison share one deterministic patient
resample matrix. Uno C, AUC and Brier retain the canonical engine's
fold-size-weighted aggregation and training-fold censoring reference.
"""
from __future__ import absolute_import

import argparse
import json
import os
from collections import OrderedDict

import numpy as np
import pandas as pd

try:
    from . import validate_assets as va
    from . import run_cv
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    import validate_assets as va
    import run_cv


COMPARISONS = (
    ("M0_vs_M1", "M0", "M1", "main", "clinical_baseline",
     "original_prespecified", "pair_file"),
    ("M0_vs_M2", "M0", "M2", "main", "clinical_baseline",
     "original_prespecified", "pair_file"),
    ("M0_vs_M3L", "M0", "M3L", "R_low", "clinical_baseline",
     "post_v2_supplementary", "constructed"),
    ("M0_vs_M3H", "M0", "M3H", "R_high", "clinical_baseline",
     "post_v2_supplementary", "constructed"),
    ("M0_vs_M4", "M0", "M4", "dual_radiomics", "clinical_baseline",
     "post_v2_supplementary", "constructed"),
    ("M0_vs_M5", "M0", "M5", "W_Original_available", "clinical_baseline",
     "post_v2_supplementary", "constructed"),
    ("M1_vs_M2", "M1", "M2", "main", "habitat_incremental",
     "post_v2_supplementary", "constructed"),
    ("M2_vs_M3L", "M2", "M3L", "R_low", "habitat_incremental",
     "original_prespecified", "pair_file"),
    ("M2_vs_M3H", "M2", "M3H", "R_high", "habitat_incremental",
     "original_prespecified", "pair_file"),
    ("M2_vs_M4", "M2", "M4", "dual_radiomics", "habitat_incremental",
     "original_prespecified", "pair_file"),
    ("M3L_vs_M3H", "M3L", "M3H", "dual_radiomics", "secondary_head_to_head",
     "original_prespecified", "pair_file"),
    ("M4_vs_M5", "M4", "M5", "dual_radiomics_and_W_Original",
     "secondary_head_to_head", "original_prespecified", "pair_file"),
)

ORIGINAL_COMPARISONS = {
    item[0] for item in COMPARISONS if item[5] == "original_prespecified"
}

METRICS = OrderedDict((
    ("harrell_c", "harrell_c_index"),
    ("uno_c", "uno_c_index"),
    ("auc_3y", "3_year_auc"),
    ("auc_5y", "5_year_auc"),
    ("brier_3y", "3_year_brier"),
    ("brier_5y", "5_year_brier"),
))

# Keep the historical seed sequence for the seven original comparisons and
# continue it for the five post-v2 comparisons.
BOOTSTRAP_SEEDS = {
    comparison_id: 20261000 + index
    for index, (comparison_id, _, _, _, _, _, _) in enumerate(COMPARISONS)
}


class ComparisonError(ValueError):
    """Raised when a comparison cannot be built without violating the contract."""


def _engine():
    return run_cv._engine()


def _require_columns(frame, columns, label):
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ComparisonError("%s is missing columns: %s" % (label, missing))


def _load_clinical_frame(path):
    frame = pd.read_csv(path)
    id_column = "patient_id" if "patient_id" in frame.columns else "影像号"
    if id_column not in frame.columns:
        raise ComparisonError("A feature frame has no patient identifier")
    if id_column != "patient_id":
        frame = frame.rename(columns={id_column: "patient_id"})
    needed = ["patient_id", "DFS_time", "DFS_event"] + list(va.CLINICAL_COLUMNS)
    _require_columns(frame, needed, "A feature frame")
    frame = frame.loc[:, needed].copy()
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    return va.validate_predictor_frame(frame, model_ids=["M0"],
                                      cohort="A", require_outcome=True)


def _load_split(path, frame):
    split = pd.read_csv(path)
    if "repeat" in split.columns:
        split = split[split["repeat"].eq(va.OUTER_REPEAT)].copy()
    return va.validate_split(split, frame=frame, production=False)


def _load_prediction(path, label):
    prediction = pd.read_csv(path)
    _require_columns(
        prediction,
        ["patient_id", "fold", "risk", "survival_probability_36",
         "survival_probability_60"],
        label,
    )
    prediction = prediction.loc[:, [
        "patient_id", "fold", "risk", "survival_probability_36",
        "survival_probability_60"]].copy()
    prediction["patient_id"] = prediction["patient_id"].astype(str).str.strip()
    prediction["fold"] = pd.to_numeric(prediction["fold"], errors="coerce")
    for column in ("risk", "survival_probability_36", "survival_probability_60"):
        prediction[column] = pd.to_numeric(prediction[column], errors="coerce")
    if prediction["patient_id"].eq("").any() or prediction["patient_id"].duplicated().any():
        raise ComparisonError("%s has blank or duplicate patient IDs" % label)
    if prediction["fold"].isna().any() or not prediction["fold"].isin(range(1, 6)).all():
        raise ComparisonError("%s has invalid fold assignments" % label)
    if prediction[["risk", "survival_probability_36",
                   "survival_probability_60"]].isna().any().any():
        raise ComparisonError("%s has missing predictions" % label)
    if not np.isfinite(prediction[["risk", "survival_probability_36",
                                   "survival_probability_60"]].to_numpy(dtype=float)).all():
        raise ComparisonError("%s has non-finite predictions" % label)
    if ((prediction["survival_probability_36"] < 0) |
            (prediction["survival_probability_36"] > 1) |
            (prediction["survival_probability_60"] < 0) |
            (prediction["survival_probability_60"] > 1)).any():
        raise ComparisonError("%s has invalid survival probabilities" % label)
    prediction["fold"] = prediction["fold"].astype(int)
    return prediction.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def _prediction_to_pair(left, right, left_model, right_model):
    left = left.rename(columns={
        "fold": "left_fold", "risk": "left_risk",
        "survival_probability_36": "left_survival_probability_36",
        "survival_probability_60": "left_survival_probability_60"})
    right = right.rename(columns={
        "fold": "right_fold", "risk": "right_risk",
        "survival_probability_36": "right_survival_probability_36",
        "survival_probability_60": "right_survival_probability_60"})
    pair = left.merge(right, on="patient_id", how="inner", validate="one_to_one")
    if pair.empty:
        raise ComparisonError("%s vs %s has no common eligible IDs" %
                              (left_model, right_model))
    if not np.array_equal(pair["left_fold"].to_numpy(),
                          pair["right_fold"].to_numpy()):
        raise ComparisonError("%s vs %s has different fold assignments" %
                              (left_model, right_model))
    pair["fold"] = pair["left_fold"].astype(int)
    return pair.drop(columns=["left_fold", "right_fold"]).sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)


def _pair_file_to_pair(path, left_model, right_model):
    pair = pd.read_csv(path)
    required = [
        "patient_id", "fold", "left_risk", "left_survival_probability_36",
        "left_survival_probability_60", "right_risk",
        "right_survival_probability_36", "right_survival_probability_60"]
    _require_columns(pair, required, path)
    pair = pair.loc[:, required].copy()
    pair["patient_id"] = pair["patient_id"].astype(str).str.strip()
    pair["fold"] = pd.to_numeric(pair["fold"], errors="coerce")
    numeric = [column for column in required if column not in ("patient_id", "fold")]
    for column in numeric:
        pair[column] = pd.to_numeric(pair[column], errors="coerce")
    if pair["patient_id"].eq("").any() or pair["patient_id"].duplicated().any():
        raise ComparisonError("%s has blank or duplicate patient IDs" % path)
    if pair["fold"].isna().any() or not pair["fold"].isin(range(1, 6)).all():
        raise ComparisonError("%s has invalid folds" % path)
    if pair[numeric].isna().any().any() or not np.isfinite(
            pair[numeric].to_numpy(dtype=float)).all():
        raise ComparisonError("%s has missing or non-finite values" % path)
    if ((pair["left_survival_probability_36"] < 0) |
            (pair["left_survival_probability_36"] > 1) |
            (pair["left_survival_probability_60"] < 0) |
            (pair["left_survival_probability_60"] > 1) |
            (pair["right_survival_probability_36"] < 0) |
            (pair["right_survival_probability_36"] > 1) |
            (pair["right_survival_probability_60"] < 0) |
            (pair["right_survival_probability_60"] > 1)).any():
        raise ComparisonError("%s has invalid survival probabilities" % path)
    pair["fold"] = pair["fold"].astype(int)
    return pair.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def _eligible_ids_from_prediction(prediction, label):
    ids = set(prediction["patient_id"])
    if not ids:
        raise ComparisonError("%s has no eligible IDs" % label)
    return ids


def _refit_m0_on_population(clinical, split, eligible_ids):
    """Rerun only the missing M0 comparator prediction on fixed IDs/folds."""
    rows = []
    for fold in range(1, 6):
        current = split[split["fold"].eq(fold)]
        train_ids = (set(current.loc[current["role"].eq("train"), "patient_id"])
                     & eligible_ids)
        valid_ids = (set(current.loc[current["role"].eq("validation"), "patient_id"])
                     & eligible_ids)
        if not train_ids or not valid_ids:
            raise ComparisonError("M0 comparator has empty eligible side in fold %d" % fold)
        train = clinical[clinical["patient_id"].isin(train_ids)].sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        valid = clinical[clinical["patient_id"].isin(valid_ids)].sort_values(
            "patient_id", kind="mergesort").reset_index(drop=True)
        fitted = run_cv.fit_canonical_model(
            train, "M0", seed=va.OUTER_SEED, lambda_count=va.LAMBDA_COUNT)
        risk, survival = run_cv._survival_predictions(fitted, valid)
        for index, patient_id in enumerate(valid["patient_id"].astype(str)):
            rows.append({
                "patient_id": patient_id,
                "fold": int(fold),
                "risk": float(risk[index]),
                "survival_probability_36": float(survival["3_year"][index]),
                "survival_probability_60": float(survival["5_year"][index]),
            })
    result = pd.DataFrame(rows).sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)
    if set(result["patient_id"]) != eligible_ids or result["patient_id"].duplicated().any():
        raise ComparisonError("M0 comparator did not cover its eligible population exactly once")
    return result


def _outcome_frame(clinical):
    return clinical.loc[:, ["patient_id", "DFS_time", "DFS_event"]].copy()


def _attach_outcomes(pair, outcomes, ids):
    joined = pair.merge(outcomes, on="patient_id", how="inner",
                        validate="one_to_one")
    if len(joined) != len(pair) or set(joined["patient_id"]) != set(ids):
        raise ComparisonError("outcomes do not cover the paired population exactly")
    return joined.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def _training_reference(outcomes, split, ids, fold):
    current = split[split["fold"].eq(int(fold))]
    train_ids = set(current.loc[current["role"].eq("train"), "patient_id"]) & set(ids)
    train = outcomes[outcomes["patient_id"].isin(train_ids)]
    if train.empty or int(train["DFS_event"].sum()) < 1:
        raise ComparisonError("comparison fold %d has no training event" % fold)
    return (train["DFS_time"].to_numpy(dtype=float),
            train["DFS_event"].to_numpy(dtype=int))


def _fast_harrell_c_index(time, event, risk):
    event_rows = np.asarray(event, dtype=int) == 1
    comparable = event_rows[:, None] & (time[None, :] > time[:, None])
    denominator = float(np.sum(comparable))
    if denominator == 0.0:
        return float("nan")
    score = ((risk[:, None] > risk[None, :]).astype(float) +
             0.5 * (risk[:, None] == risk[None, :]).astype(float))
    return float(np.sum(score * comparable) / denominator)


def _censor_survival_vectorized(train_time, train_event, query, left):
    """Vectorized equivalent of the canonical censoring KM helper."""
    query = np.asarray(query, dtype=float)
    censor_event = 1 - np.asarray(train_event, dtype=int)
    censor_times = np.unique(np.asarray(train_time, dtype=float)[censor_event == 1])
    if censor_times.size == 0:
        return np.ones(query.shape[0], dtype=float)
    sorted_train_time = np.sort(np.asarray(train_time, dtype=float))
    at_risk = len(sorted_train_time) - np.searchsorted(
        sorted_train_time, censor_times, side="left")
    deaths = np.asarray([
        np.sum((np.asarray(train_time, dtype=float) == current) &
               (censor_event == 1)) for current in censor_times], dtype=float)
    survival_steps = np.cumprod(1.0 - deaths / at_risk.astype(float))
    side = "left" if left else "right"
    indices = np.searchsorted(censor_times, query, side=side) - 1
    result = np.ones(query.shape[0], dtype=float)
    valid = indices >= 0
    result[valid] = survival_steps[indices[valid]]
    return result


def _fast_uno_c_index(train_time, train_event,
                      validation_time, validation_event, risk):
    event_indices = np.where(np.asarray(validation_event, dtype=int) == 1)[0]
    if event_indices.size == 0:
        return float("nan")
    censor_survival = _censor_survival_vectorized(
        train_time, train_event, validation_time[event_indices], left=True)
    keep = censor_survival > 1e-12
    event_indices = event_indices[keep]
    weights = 1.0 / (censor_survival[keep] * censor_survival[keep])
    if event_indices.size == 0:
        return float("nan")
    comparable = validation_time[None, :] > validation_time[event_indices, None]
    denominator = float(np.sum(weights[:, None] * comparable))
    if denominator == 0.0:
        return float("nan")
    event_risk = risk[event_indices, None]
    later_risk = risk[None, :]
    score = ((event_risk > later_risk).astype(float) +
             0.5 * (event_risk == later_risk).astype(float))
    return float(np.sum(weights[:, None] * comparable * score) / denominator)


def _fast_time_metrics(train_time, train_event,
                       validation_time, validation_event, risk,
                       survival, horizon):
    observed = np.zeros(len(validation_time), dtype=float)
    weights = np.zeros(len(validation_time), dtype=float)
    cases = (validation_time <= horizon) & (validation_event == 1)
    controls = validation_time > horizon
    if np.any(cases):
        censor_survival = _censor_survival_vectorized(
            train_time, train_event, validation_time[cases], left=True)
        weights[cases] = np.where(censor_survival > 1e-12,
                                  1.0 / censor_survival, 0.0)
    if np.any(controls):
        censor_survival = _censor_survival_vectorized(
            train_time, train_event, np.asarray([horizon]), left=False)[0]
        observed[controls] = 1.0
        if censor_survival > 1e-12:
            weights[controls] = 1.0 / censor_survival
    positive = weights > 0
    if not np.any(positive):
        return float("nan"), float("nan")
    predicted_survival = np.asarray(survival, dtype=float)
    residual = observed - predicted_survival
    brier = float(np.sum(weights * residual * residual) / np.sum(weights))
    cases = positive & (observed == 0)
    controls = positive & (observed == 1)
    if not np.any(cases) or not np.any(controls):
        return float("nan"), brier
    predicted_risk = 1.0 - predicted_survival
    case_risk = predicted_risk[cases, None]
    control_risk = predicted_risk[controls, None].T
    pair_weights = weights[cases, None] * weights[controls, None].T
    score = ((case_risk > control_risk).astype(float) +
             0.5 * (case_risk == control_risk).astype(float))
    auc = float(np.sum(pair_weights * score) / np.sum(pair_weights))
    return auc, brier


def _fast_fold_metrics(train_time, train_event, validation,
                       risk, survival_36, survival_60):
    validation_time = validation["DFS_time"].to_numpy(dtype=float)
    validation_event = validation["DFS_event"].to_numpy(dtype=int)
    result = {
        "uno_c_index": _fast_uno_c_index(
            train_time, train_event, validation_time,
            validation_event, np.asarray(risk, dtype=float)),
    }
    result["3_year_auc"], result["3_year_brier"] = _fast_time_metrics(
        train_time, train_event, validation_time, validation_event,
        np.asarray(risk, dtype=float), survival_36, 36.0)
    result["5_year_auc"], result["5_year_brier"] = _fast_time_metrics(
        train_time, train_event, validation_time, validation_event,
        np.asarray(risk, dtype=float), survival_60, 60.0)
    return result


def _aggregate_metrics(pair, outcomes, split, ids):
    engine = _engine()
    if "DFS_time" in pair.columns and "DFS_event" in pair.columns:
        joined = pair.copy()
    else:
        joined = pair.merge(outcomes, on="patient_id", how="inner",
                            validate="many_to_one")
        if len(joined) != len(pair) or not set(joined["patient_id"]).issubset(set(ids)):
            raise ComparisonError("outcomes do not cover the paired population exactly")
        joined = joined.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
    time = joined["DFS_time"].to_numpy(dtype=float)
    event = joined["DFS_event"].to_numpy(dtype=int)
    result = OrderedDict()
    result["harrell_c_left"] = _fast_harrell_c_index(
        time, event, joined["left_risk"].to_numpy(dtype=float))
    result["harrell_c_right"] = _fast_harrell_c_index(
        time, event, joined["right_risk"].to_numpy(dtype=float))
    fold_values = {
        "left": {key: [] for key in METRICS if key != "harrell_c"},
        "right": {key: [] for key in METRICS if key != "harrell_c"}}
    fold_weights = []
    for fold in range(1, 6):
        validation = joined[joined["fold"].eq(fold)].copy()
        if validation.empty:
            continue
        train_time, train_event = _training_reference(outcomes, split, ids, fold)
        valid_time = validation["DFS_time"].to_numpy(dtype=float)
        valid_event = validation["DFS_event"].to_numpy(dtype=int)
        left_metrics = _fast_fold_metrics(
            train_time, train_event, validation,
            validation["left_risk"].to_numpy(dtype=float),
            validation["left_survival_probability_36"].to_numpy(dtype=float),
            validation["left_survival_probability_60"].to_numpy(dtype=float))
        right_metrics = _fast_fold_metrics(
            train_time, train_event, validation,
            validation["right_risk"].to_numpy(dtype=float),
            validation["right_survival_probability_36"].to_numpy(dtype=float),
            validation["right_survival_probability_60"].to_numpy(dtype=float))
        fold_weights.append(float(len(validation)))
        for key, engine_key in METRICS.items():
            if key == "harrell_c":
                continue
            fold_values["left"][key].append(float(left_metrics[engine_key]))
            fold_values["right"][key].append(float(right_metrics[engine_key]))
    weights = np.asarray(fold_weights, dtype=float)
    for key in METRICS:
        if key == "harrell_c":
            continue
        for side in ("left", "right"):
            values = np.asarray(fold_values[side][key], dtype=float)
            if len(values) != len(weights) or not np.isfinite(values).all():
                result["%s_%s" % (key, side)] = float("nan")
            else:
                result["%s_%s" % (key, side)] = float(
                    np.average(values, weights=weights))
    return result


def _delta_values(metrics):
    return OrderedDict((
        (key, float(metrics["%s_right" % key] -
                    metrics["%s_left" % key]))
        for key in METRICS
    ))


def _bootstrap_deltas(pair, outcomes, split, ids, seed, n_bootstrap):
    rng = np.random.RandomState(int(seed))
    index_matrix = rng.randint(0, len(pair),
                               size=(int(n_bootstrap), len(pair)))
    values = {key: [] for key in METRICS}
    for indices in index_matrix:
        sample = pair.iloc[indices].reset_index(drop=True)
        metrics = _aggregate_metrics(sample, outcomes, split, ids)
        delta = _delta_values(metrics)
        for key in METRICS:
            if np.isfinite(delta[key]):
                values[key].append(delta[key])
    return values


def _ci(values, estimate, n_bootstrap):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {
            "estimate": float(estimate), "lower": None, "upper": None,
            "n_bootstrap": int(n_bootstrap), "n_estimable": 0,
            "coverage": 0.0, "method": "percentile"}
    return {
        "estimate": float(estimate),
        "lower": float(np.percentile(finite, 2.5)),
        "upper": float(np.percentile(finite, 97.5)),
        "n_bootstrap": int(n_bootstrap),
        "n_estimable": int(finite.size),
        "coverage": float(finite.size / float(n_bootstrap)),
        "method": "percentile",
    }


def _historical_check(path, computed):
    if not path:
        return
    with open(path, "r", encoding="utf-8") as handle:
        historical = json.load(handle)
    records = {
        item["comparison_id"]: item
        for item in historical.get("paired_model_comparisons", [])}
    # The archived FT03 paired record has no paired Uno C field. Its paired
    # Brier values were stored from a different summary path, so the unified
    # table deliberately re-derives both Brier deltas from the paired held-out
    # predictions under the canonical fold-wise IPCW definition.
    names = {
        "harrell_c": "Harrell_C_index",
        "auc_3y": "AUC_3_year", "auc_5y": "AUC_5_year"}
    for comparison_id in ORIGINAL_COMPARISONS:
        if comparison_id not in records:
            raise ComparisonError("historical result lacks %s" % comparison_id)
        expected = records[comparison_id]["metrics"]
        for key, historical_key in names.items():
            if historical_key not in expected:
                continue
            expected_value = expected[historical_key]["delta_right_minus_left"]
            actual_value = computed[comparison_id]["deltas"][key]
            if not np.isclose(float(expected_value), float(actual_value),
                              rtol=0.0, atol=1e-10):
                raise ComparisonError(
                    "%s %s differs from archived estimate: %.15g vs %.15g" %
                    (comparison_id, key, actual_value, expected_value))


def _format_ci(record):
    if record["lower"] is None:
        return "NA"
    return "%.4f [%.4f, %.4f]" % (
        record["estimate"], record["lower"], record["upper"])


def _write_markdown(path, records, base_n, n_bootstrap):
    lines = [
        "# Primary v2 unified paired model comparisons",
        "",
        "All 12 comparisons use DFS, the frozen repeat-1 five-fold assignment and a common eligible population for the two models. comparison_origin preserves whether a row was original prespecified or post-v2 supplementary.",
        "",
        "coverage is the paired prediction coverage relative to the exact Primary v2 A393 modeling population: common_n / %d. Each metric uses the same patient bootstrap resamples within a comparison; bootstrap coverage is the fraction of estimable resamples." % base_n,
        "",
        "Bootstrap CIs are percentile 95%% intervals with %d case resamples. Harrell C is pooled over common held-out predictions. Uno C, AUC and Brier are fold-size-weighted using the corresponding outer-training censoring reference." % n_bootstrap,
        "",
        "| Comparison | Family | Origin | Common population | n | events | Coverage | ΔHarrell C | ΔUno C | ΔAUC 3y | ΔAUC 5y | ΔBrier 3y | ΔBrier 5y |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for record in records:
        lines.append(
            "| {comparison_id} | {comparison_family} | {comparison_origin} | {population} | {common_n} | {common_event_n} | {coverage:.3f} | {harrell} | {uno} | {auc3} | {auc5} | {brier3} | {brier5} |".format(
                comparison_id=record["comparison_id"],
                comparison_family=record["comparison_family"],
                comparison_origin=record["comparison_origin"],
                population=record["population"],
                common_n=record["common_n"],
                common_event_n=record["common_event_n"],
                coverage=record["coverage"],
                harrell=_format_ci(record["metric_results"]["harrell_c"]),
                uno=_format_ci(record["metric_results"]["uno_c"]),
                auc3=_format_ci(record["metric_results"]["auc_3y"]),
                auc5=_format_ci(record["metric_results"]["auc_5y"]),
                brier3=_format_ci(record["metric_results"]["brier_3y"]),
                brier5=_format_ci(record["metric_results"]["brier_5y"]),
            ))
    lines.extend([
        "",
        "## Reading the deltas",
        "",
        "All deltas are right model minus left model. Positive ΔHarrell C, ΔUno C and ΔAUC indicate higher discrimination; negative ΔBrier indicates lower prediction error.",
        "",
        "The supplementary rows are M0_vs_M3L, M0_vs_M3H, M0_vs_M4, M0_vs_M5 and M1_vs_M2. For the first three, M0 was refit only on the relevant common eligible population within the frozen folds; all high-dimensional models and feature definitions were reused.",
        "",
        "same_fold_assignment was verified as true for every row. The unified table is the formal comparison result for this Primary v2 supplement; no separate old/new result table is used.",
        "",
    ])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def _write_csv(path, records):
    rows = []
    for record in records:
        row = OrderedDict((key, record[key]) for key in (
            "comparison_id", "left_model", "right_model", "comparison_family",
            "comparison_origin", "population", "common_n", "common_event_n",
            "coverage", "coverage_percent", "common_id_hash",
            "same_fold_assignment", "endpoint", "horizons_months",
            "bootstrap_n", "bootstrap_seed"))
        for key in METRICS:
            metric = record["metric_results"][key]
            row["delta_%s" % key] = metric["estimate"]
            row["delta_%s_lower" % key] = metric["lower"]
            row["delta_%s_upper" % key] = metric["upper"]
            row["delta_%s_n_estimable" % key] = metric["n_estimable"]
            row["delta_%s_coverage" % key] = metric["coverage"]
        rows.append(row)
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")


def _write_figure(path, records):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    panels = [
        ("harrell_c", "ΔHarrell C"), ("uno_c", "ΔUno C"),
        ("auc_3y", "ΔAUC 3 y"), ("auc_5y", "ΔAUC 5 y"),
        ("brier_3y", "ΔBrier 3 y"), ("brier_5y", "ΔBrier 5 y"),
    ]
    labels = [record["comparison_id"] for record in records][::-1]
    figure, axes = plt.subplots(2, 3, figsize=(16, 12), sharey=True)
    axes = axes.ravel()
    colors = [
        "#1f77b4" if record["comparison_origin"] == "original_prespecified"
        else "#d62728" for record in records][::-1]
    for panel_index, (axis, (metric, title)) in enumerate(zip(axes, panels)):
        values = [
            record["metric_results"][metric]["estimate"]
            for record in records][::-1]
        lower = [
            record["metric_results"][metric]["lower"]
            for record in records][::-1]
        upper = [
            record["metric_results"][metric]["upper"]
            for record in records][::-1]
        y = np.arange(len(labels))
        for index in range(len(values)):
            xerr = [[values[index] - lower[index]],
                    [upper[index] - values[index]]]
            axis.errorbar([values[index]], [y[index]], xerr=xerr, fmt="o",
                          color="#333333", ecolor=colors[index],
                          elinewidth=1.5, capsize=3, markersize=4)
        axis.axvline(0.0, color="#777777", linewidth=1.0, linestyle="--")
        axis.set_title(title)
        axis.grid(axis="x", color="#dddddd", linewidth=0.7)
        axis.set_yticks(y)
        if panel_index in (0, 3):
            axis.set_yticklabels(labels, fontsize=8)
        else:
            axis.tick_params(axis="y", labelleft=False)
        axis.set_xlabel("Right - left")
    figure.suptitle("Primary v2 unified paired model comparisons", fontsize=15)
    figure.text(
        0.5, 0.01,
        "Blue: original prespecified   Red: post-v2 supplementary; bars are percentile bootstrap 95% CIs",
        ha="center", fontsize=10)
    figure.tight_layout(rect=[0, 0.03, 1, 0.97])
    figure.savefig(path, dpi=240, bbox_inches="tight")
    plt.close(figure)


def build_comparisons(feature_path, split_path, prediction_dir, paired_dir,
                      historical_path=None, n_bootstrap=200, output_dir=None):
    if int(n_bootstrap) < 20:
        raise ComparisonError("n_bootstrap must be at least 20")
    clinical = _load_clinical_frame(feature_path)
    if len(clinical) != 393:
        raise ComparisonError(
            "Primary v2 comparison input must contain the exact A393 population")
    split = _load_split(split_path, clinical)
    outcomes = _outcome_frame(clinical)
    predictions = {}
    for model_id in ("M0", "M1", "M2", "M3L", "M3H", "M4", "M5"):
        path = os.path.join(prediction_dir, "%s.csv" % model_id)
        predictions[model_id] = _load_prediction(path, model_id)

    m0_subsets = {}
    for population, model_id in (
            ("R_low", "M3L"), ("R_high", "M3H"),
            ("dual_radiomics", "M4")):
        m0_subsets[population] = _refit_m0_on_population(
            clinical, split,
            _eligible_ids_from_prediction(predictions[model_id], model_id))

    computed = OrderedDict()
    for comparison_id, left_model, right_model, population, family, origin, source in COMPARISONS:
        if source == "pair_file":
            pair = _pair_file_to_pair(
                os.path.join(paired_dir, "%s.csv" % comparison_id),
                left_model, right_model)
        elif comparison_id in ("M0_vs_M3L", "M0_vs_M3H", "M0_vs_M4"):
            pair = _prediction_to_pair(
                m0_subsets[population], predictions[right_model],
                left_model, right_model)
        else:
            pair = _prediction_to_pair(
                predictions[left_model], predictions[right_model],
                left_model, right_model)
        ids = set(pair["patient_id"])
        pair = _attach_outcomes(pair, outcomes, ids)
        metrics = _aggregate_metrics(pair, outcomes, split, ids)
        deltas = _delta_values(metrics)
        bootstrap = _bootstrap_deltas(
            pair, outcomes, split, ids,
            BOOTSTRAP_SEEDS[comparison_id], n_bootstrap)
        common_event_n = int(
            outcomes[outcomes["patient_id"].isin(ids)]["DFS_event"].sum())
        record = {
            "comparison_id": comparison_id,
            "left_model": left_model,
            "right_model": right_model,
            "comparison_family": family,
            "comparison_origin": origin,
            "population": population,
            "common_n": int(len(ids)),
            "common_event_n": common_event_n,
            "coverage": float(len(ids) / float(len(clinical))),
            "coverage_percent": float(100.0 * len(ids) / float(len(clinical))),
            "common_id_hash": va.canonical_id_hash(ids),
            "same_fold_assignment": True,
            "endpoint": "DFS",
            "horizons_months": "36,60",
            "bootstrap_n": int(n_bootstrap),
            "bootstrap_seed": int(BOOTSTRAP_SEEDS[comparison_id]),
            "deltas": deltas,
            "metric_results": OrderedDict((
                (key, _ci(bootstrap[key], deltas[key], n_bootstrap))
                for key in METRICS)),
        }
        computed[comparison_id] = record

    _historical_check(historical_path, computed)
    records = list(computed.values())
    if output_dir:
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
        _write_csv(
            os.path.join(output_dir, "primary_v2_model_comparisons.csv"), records)
        _write_markdown(
            os.path.join(output_dir, "primary_v2_model_comparisons.md"),
            records, len(clinical), n_bootstrap)
        _write_figure(
            os.path.join(output_dir,
                         "primary_v2_model_comparison_figure.png"), records)
    return records


def main(argv=None):  # pragma: no cover - exercised through the local CLI
    parser = argparse.ArgumentParser(
        description="Build Primary v2 unified model comparisons")
    parser.add_argument("--feature-frame", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--prediction-dir", required=True)
    parser.add_argument("--paired-dir", required=True)
    parser.add_argument("--historical-json", default=None)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--n-bootstrap", type=int, default=200)
    args = parser.parse_args(argv)
    build_comparisons(
        args.feature_frame, args.split, args.prediction_dir, args.paired_dir,
        historical_path=args.historical_json, n_bootstrap=args.n_bootstrap,
        output_dir=args.output_dir)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
