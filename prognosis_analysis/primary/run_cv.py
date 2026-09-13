"""Canonical Primary v2 A-only single-repeat five-fold validation.

The public production function accepts an authorised in-memory A feature frame
and a caller-loaded frozen repeat-1 split.  It does not regenerate splits,
fit habitat states, open B data, or use outer-validation rows for any
preprocessing or lambda decision.  The ``*_for_testing`` entry point is
limited to synthetic fixtures and is the only supported caller-supplied split
path for small tests.
"""
from __future__ import absolute_import

import argparse
import json
import os
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd

try:
    from . import validate_assets as va
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    import validate_assets as va


class PrimaryCVError(va.PrimaryValidationError):
    """Raised when a canonical A validation operation cannot complete."""


def _engine():
    script_root = os.path.join(va.PROJECT_ROOT, "prognosis_analysis", "scripts")
    if script_root not in sys.path:
        sys.path.insert(0, script_root)
    try:
        import w08_nested_cv as engine
    except ImportError as exc:
        raise PrimaryCVError("canonical Cox engine is unavailable: %s" % exc)
    return engine


def _model_spec(model_id):
    if model_id not in va.MODEL_SPECS:
        raise PrimaryCVError("unknown Primary v2 model: %s" % model_id)
    return va.MODEL_SPECS[model_id]


def raw_predictor_columns(frame, model_id):
    """Return the FT04-compatible raw predictor identity for one model."""
    columns = []
    for block in _model_spec(model_id)["blocks"]:
        if block == "C":
            columns.extend(va.CLINICAL_COLUMNS)
        elif block == "H_high_fraction":
            columns.append("H_high_fraction")
        elif block == "G":
            columns.extend(va.GLOBAL_COLUMNS)
        elif block in ("R_low", "R_high"):
            columns.extend([block + "_structurally_defined",
                            block + "_technically_available"])
            columns.extend(va.block_columns(frame, block))
        elif block == "W_Original":
            columns.append("W_Original_available")
            columns.extend(va.block_columns(frame, block))
        else:
            raise PrimaryCVError("unknown raw predictor block: %s" % block)
    return columns


class CanonicalPreprocessor(object):
    """FT-equivalent training-only preprocessing with Primary v2 schemas."""

    def __init__(self, model_id):
        self.model_id = model_id
        self.spec = _model_spec(model_id)
        self.clinical = None
        self.global_block = None
        self.radiomics = None
        self.feature_names = []

    def fit(self, frame):
        engine = _engine()
        self.clinical = engine.ClinicalPreprocessor().fit(frame)
        names = list(self.clinical.feature_names)
        blocks = self.spec["blocks"]
        extras = []
        if "H_high_fraction" in blocks:
            extras.append("H_high_fraction")
        if "G" in blocks:
            extras.extend(va.GLOBAL_COLUMNS)
        if extras:
            self.global_block = engine.NumericPreprocessor(extras).fit(frame)
            names.extend(extras)
        radiomics_columns = []
        for block in ("R_low", "R_high", "W_Original"):
            if block in blocks:
                radiomics_columns.extend(va.block_columns(frame, block))
        if radiomics_columns:
            self.radiomics = engine.RadiomicsPreprocessor(radiomics_columns).fit(frame)
            names.extend(self.radiomics.kept_columns)
        self.feature_names = list(names)
        if not self.feature_names:
            raise PrimaryCVError("training-only preprocessing retained no feature")
        return self

    def transform(self, frame):
        if not self.feature_names or self.clinical is None:
            raise PrimaryCVError("preprocessor is not fitted")
        pieces = [self.clinical.transform(frame).to_numpy(dtype=float)]
        if self.global_block is not None:
            pieces.append(self.global_block.transform(frame))
        if self.radiomics is not None:
            pieces.append(self.radiomics.transform(frame))
        output = np.column_stack(pieces)
        if output.shape[1] != len(self.feature_names) or not np.isfinite(output).all():
            raise PrimaryCVError("preprocessed matrix is invalid")
        return output

    def audit(self):
        return {
            "model_id": self.model_id,
            "feature_names": list(self.feature_names),
            "feature_order_sha256": va.canonical_json_hash(self.feature_names),
            "clinical_imputations": dict(self.clinical.imputations),
            "clinical_means": dict(self.clinical.means),
            "clinical_scales": dict(self.clinical.scales),
            "radiomics_input_count": 0 if self.radiomics is None else len(self.radiomics.input_columns),
            "radiomics_kept_columns": [] if self.radiomics is None else list(self.radiomics.kept_columns),
            "radiomics_dropped_all_nonfinite": [] if self.radiomics is None else list(self.radiomics.dropped_all_nonfinite),
            "radiomics_dropped_near_zero_variance": [] if self.radiomics is None else list(self.radiomics.dropped_near_zero_variance),
            "radiomics_dropped_correlation": [] if self.radiomics is None else list(self.radiomics.dropped_correlation),
        }


def _require_events(frame, label):
    count = int(pd.to_numeric(frame["DFS_event"], errors="coerce").sum())
    if count < 1:
        raise PrimaryCVError("%s contains no DFS event" % label)
    return count


def _fit_penalized(engine, X, frame, penalty, max_iter, tolerance):
    model = engine.CoxElasticNetModel(
        va.ALPHA, float(penalty), max_iter=int(max_iter), tolerance=float(tolerance))
    model.fit(
        X,
        frame["DFS_time"].to_numpy(dtype=float),
        frame["DFS_event"].to_numpy(dtype=int),
    )
    engine._require_converged_model(model, "Primary v2 Elastic-Net Cox")
    return model


def select_lambda(train_frame, model_id, seed, lambda_count=va.LAMBDA_COUNT,
                  max_iter=3000, tolerance=1e-7):
    """Select alpha=1 lambda using only inner folds of one outer-training set."""
    spec = _model_spec(model_id)
    if not spec["penalized"]:
        raise PrimaryCVError("lambda selection requested for unpenalized model")
    if int(lambda_count) < 2:
        raise PrimaryCVError("lambda_count must be at least two")
    engine = _engine()
    inner_splits = engine.make_inner_splits(train_frame, int(seed), folds=va.INNER_FOLDS)
    ratios = np.geomspace(1.0, va.LAMBDA_MIN_RATIO, int(lambda_count))
    scores = [[] for _ in ratios]
    attempts = 0
    failures = 0
    for train_idx, valid_idx in inner_splits:
        inner_train = train_frame.iloc[train_idx].reset_index(drop=True)
        inner_valid = train_frame.iloc[valid_idx].reset_index(drop=True)
        prep = CanonicalPreprocessor(model_id).fit(inner_train)
        X_train = prep.transform(inner_train)
        X_valid = prep.transform(inner_valid)
        maximum = float(engine._lambda_max(
            X_train,
            inner_train["DFS_time"].to_numpy(dtype=float),
            inner_train["DFS_event"].to_numpy(dtype=int),
            va.ALPHA,
        ))
        if not np.isfinite(maximum) or maximum <= 0:
            raise PrimaryCVError("inner-training lambda_max is nonpositive")
        for index, ratio in enumerate(ratios):
            attempts += 1
            try:
                candidate = _fit_penalized(
                    engine, X_train, inner_train, maximum * float(ratio),
                    max_iter, tolerance)
                score = engine.uno_c_index(
                    inner_train["DFS_time"].to_numpy(dtype=float),
                    inner_train["DFS_event"].to_numpy(dtype=int),
                    inner_valid["DFS_time"].to_numpy(dtype=float),
                    inner_valid["DFS_event"].to_numpy(dtype=int),
                    candidate.predict_risk(X_valid),
                )
                if np.isfinite(score):
                    scores[index].append(float(score))
                else:
                    failures += 1
            except (ValueError, va.PrimaryValidationError) as exc:
                # The solver's numerical exception is a ValueError subclass in
                # the locked engine.  Every attempted candidate is retained in
                # the audit and a selection with no estimable candidate fails.
                del exc
                failures += 1
    records = []
    for index, ratio in enumerate(ratios):
        finite = scores[index]
        records.append({
            "lambda_index": int(index),
            "lambda_ratio": float(ratio),
            "mean_inner_uno_c_index": float(np.mean(finite)) if finite else None,
            "n_estimable_inner_scores": int(len(finite)),
            "n_inner_scores": int(len(inner_splits)),
        })
    valid = [row for row in records if row["mean_inner_uno_c_index"] is not None]
    if not valid:
        raise PrimaryCVError("no estimable training-only lambda candidate")
    best = max(row["mean_inner_uno_c_index"] for row in valid)
    tied = [row for row in valid if best - row["mean_inner_uno_c_index"] <= 1e-12]
    selected = sorted(tied, key=lambda row: -row["lambda_ratio"])[0]
    return {
        "alpha": va.ALPHA,
        "lambda_ratio": selected["lambda_ratio"],
        "lambda_index": selected["lambda_index"],
        "mean_inner_uno_c_index": selected["mean_inner_uno_c_index"],
        "inner_folds": va.INNER_FOLDS,
        "lambda_count": int(lambda_count),
        "candidate_attempts": int(attempts),
        "candidate_failures": int(failures),
        "lambda_selection_scope": "outer_training_inner_5fold_only",
        "outer_validation_used_for_lambda": False,
        "outer_validation_used_for_selection": False,
        "all_inner_records": records,
    }


def fit_canonical_model(train_frame, model_id, seed=va.OUTER_SEED,
                        lambda_count=va.LAMBDA_COUNT, max_iter=3000,
                        tolerance=1e-7):
    """Fit one model on one A-only training set after eligibility resolution."""
    checked = va.validate_predictor_frame(train_frame, [model_id], cohort="A", require_outcome=True)
    _require_events(checked, "Primary v2 training set")
    engine = _engine()
    prep = CanonicalPreprocessor(model_id).fit(checked)
    X = prep.transform(checked)
    time = checked["DFS_time"].to_numpy(dtype=float)
    event = checked["DFS_event"].to_numpy(dtype=int)
    spec = _model_spec(model_id)
    selection = {
        "alpha": None,
        "lambda_selection_scope": "not_applicable_unpenalized",
        "outer_validation_used_for_lambda": False,
        "outer_validation_used_for_selection": False,
    }
    if spec["penalized"]:
        selection = select_lambda(
            checked, model_id, seed, lambda_count=lambda_count,
            max_iter=max_iter, tolerance=tolerance)
        reference = float(engine._lambda_max(X, time, event, va.ALPHA))
        if not np.isfinite(reference) or reference <= 0:
            raise PrimaryCVError("outer-training lambda_max is nonpositive")
        selection["outer_lambda_reference"] = reference
        selection["outer_lambda"] = reference * float(selection["lambda_ratio"])
        model = _fit_penalized(
            engine, X, checked, selection["outer_lambda"], max_iter, tolerance)
    else:
        model = engine.CoxPHModel(max_iter=int(max_iter), tolerance=float(tolerance)).fit(
            X, time, event)
        engine._require_converged_model(model, "Primary v2 Cox PH")
    return {
        "model_id": model_id,
        "model": model,
        "preprocessor": prep,
        "selection": selection,
        "preprocessing": prep.audit(),
        "fit_audit": dict(model.fit_audit),
        "feature_order_sha256": va.canonical_json_hash(prep.feature_names),
        "raw_predictor_columns": raw_predictor_columns(checked, model_id),
        "model_input_hash": va.canonical_json_hash({
            "model_id": model_id,
            "raw_predictor_columns": raw_predictor_columns(checked, model_id),
            "transformed_feature_names": prep.feature_names,
        }),
    }


def _fold_rows(frame, split, fold, population):
    eligible = frame.loc[va.eligibility_mask(frame, population), "patient_id"].astype(str)
    if eligible.empty:
        raise PrimaryCVError("empty eligible population: %s" % population)
    current = split[split["fold"].eq(int(fold))]
    eligible_set = set(eligible)
    train_ids = set(current.loc[current["role"].eq("train"), "patient_id"]) & eligible_set
    valid_ids = set(current.loc[current["role"].eq("validation"), "patient_id"]) & eligible_set
    if not train_ids or not valid_ids:
        raise PrimaryCVError("fold %d has an empty eligible side for %s" % (fold, population))
    train = frame[frame["patient_id"].astype(str).isin(train_ids)].copy()
    valid = frame[frame["patient_id"].astype(str).isin(valid_ids)].copy()
    train = train.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
    valid = valid.sort_values("patient_id", kind="mergesort").reset_index(drop=True)
    return train, valid


def _survival_predictions(fitted, frame):
    engine = _engine()
    X = fitted["preprocessor"].transform(frame)
    risk = np.asarray(fitted["model"].predict_risk(X), dtype=float)
    if not np.isfinite(risk).all():
        raise PrimaryCVError("nonfinite Primary v2 risk prediction")
    horizons = OrderedDict((("3_year", 36.0), ("5_year", 60.0)))
    survival = fitted["model"].predict_survival(X, horizons)
    for key in horizons:
        values = np.asarray(survival[key], dtype=float)
        if len(values) != len(frame) or not np.isfinite(values).all() or \
                np.any(values < 0) or np.any(values > 1):
            raise PrimaryCVError("invalid survival prediction: %s" % key)
    return risk, survival


def fit_outer_cv(frame, split, model_id, population, lambda_count=va.LAMBDA_COUNT,
                 max_iter=3000, tolerance=1e-7):
    """Fit exactly five outer folds using one immutable full-A habitat frame."""
    checked = va.validate_predictor_frame(frame, [model_id], cohort="A", require_outcome=True)
    split = va.validate_split(split, frame=checked, production=False)
    eligible_ids = set(checked.loc[va.eligibility_mask(checked, population), "patient_id"].astype(str))
    if not eligible_ids:
        raise PrimaryCVError("empty eligible population: %s" % population)
    prediction_rows = []
    folds = []
    for fold in range(1, va.OUTER_FOLDS + 1):
        train, valid = _fold_rows(checked, split, fold, population)
        train_events = _require_events(train, "outer-training fold %d" % fold)
        valid_events = _require_events(valid, "outer-validation fold %d" % fold)
        fitted = fit_canonical_model(
            train, model_id, seed=va.OUTER_SEED,
            lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance)
        risk, survival = _survival_predictions(fitted, valid)
        engine = _engine()
        time_valid = valid["DFS_time"].to_numpy(dtype=float)
        event_valid = valid["DFS_event"].to_numpy(dtype=int)
        risk_metrics = {
            "harrell_c_index": float(engine.harrell_c_index(time_valid, event_valid, risk)),
            "uno_c_index": float(engine.uno_c_index(
                train["DFS_time"].to_numpy(dtype=float),
                train["DFS_event"].to_numpy(dtype=int), time_valid, event_valid, risk)),
        }
        for index, identifier in enumerate(valid["patient_id"].astype(str)):
            prediction_rows.append({
                "patient_id": identifier,
                "DFS_time": float(time_valid[index]),
                "DFS_event": int(event_valid[index]),
                "fold": int(fold),
                "risk_score": float(risk[index]),
                "survival_probability_36": float(survival["3_year"][index]),
                "survival_probability_60": float(survival["5_year"][index]),
            })
        folds.append({
            "fold": int(fold),
            "n_train": int(len(train)),
            "n_validation": int(len(valid)),
            "train_event_count": train_events,
            "validation_event_count": valid_events,
            "training_id_hash": va.canonical_id_hash(train["patient_id"]),
            "validation_id_hash": va.canonical_id_hash(valid["patient_id"]),
            "selection": fitted["selection"],
            "preprocessing": fitted["preprocessing"],
            "fit_audit": fitted["fit_audit"],
            "metrics": risk_metrics,
            "eligibility_before_preprocessing": True,
            "outer_validation_used_for_selection": False,
            "outer_validation_used_for_lambda": False,
            "outer_validation_used_for_habitat_fit": False,
        })
    predictions = pd.DataFrame(prediction_rows).sort_values(
        "patient_id", kind="mergesort").reset_index(drop=True)
    if set(predictions["patient_id"]) != eligible_ids or predictions["patient_id"].duplicated().any():
        raise PrimaryCVError("outer validation did not cover eligible population exactly once")
    model_spec = _model_spec(model_id)
    record = {
        "model_id": model_id,
        "predictor_blocks": list(model_spec["blocks"]),
        "population": population,
        "eligible_n": int(len(eligible_ids)),
        "DFS_events": int(predictions["DFS_event"].sum()),
        "prediction_coverage": int(len(predictions)),
        "family": "LASSO-Cox" if model_spec["penalized"] else "unpenalized Cox PH",
        "alpha": va.ALPHA if model_spec["penalized"] else None,
        "outer_repeat": va.OUTER_REPEAT,
        "outer_fold_count": va.OUTER_FOLDS,
        "folds": folds,
    }
    return {"record": record, "predictions": predictions}


def _serializable_result(result):
    return {
        "schema_version": "1.0",
        "artifact_id": "PRIMARY_V2_A_VALIDATION",
        "stage": "V2-08-ready-canonical-runner",
        "status": "in_memory_result_summary",
        "protocol_sha256": result["protocol_sha256"],
        "split": result["split"],
        "provenance": result["provenance"],
        "runs": result["runs"],
        "paired_comparisons": result["paired_comparisons"],
        "patient_level_outputs_written": False,
    }


def run_cv(frame, split, model_ids=None, protocol_path=va.DEFAULT_PROTOCOL,
           production=False, output_path=None, include_paired=True,
           lambda_count=va.LAMBDA_COUNT, max_iter=3000, tolerance=1e-7):
    """Run the canonical A-only validation path on explicit in-memory inputs."""
    protocol = va.load_protocol(protocol_path)
    checked = va.validate_predictor_frame(
        frame, model_ids=model_ids, cohort="A", require_outcome=True)
    checked_split = va.validate_split(split, frame=checked, production=production)
    model_ids = list(va.MODEL_SPECS if model_ids is None else model_ids)
    if set(model_ids) == set(va.MODEL_SPECS):
        selected_runs = list(va.RUN_DEFINITIONS)
        if include_paired:
            selected_runs.append(
                {"run_id": "M5_dual", "model_id": "M5", "population": "dual_radiomics"})
    else:
        selected_runs = [
            {"run_id": model_id, "model_id": model_id,
             "population": va.MODEL_SPECS[model_id]["population"]}
            for model_id in model_ids]
    runs = OrderedDict()
    predictions = {}
    for run in selected_runs:
        fitted = fit_outer_cv(
            checked, checked_split, run["model_id"], run["population"],
            lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance)
        record = dict(fitted["record"])
        record["run_id"] = run["run_id"]
        runs[run["run_id"]] = record
        predictions[run["run_id"]] = fitted["predictions"]
    paired = []
    if include_paired:
        for comparison_id, left_run, right_run, population in va.PAIRED_COMPARISONS:
            if left_run not in predictions or right_run not in predictions:
                continue
            left = predictions[left_run].set_index("patient_id")
            right = predictions[right_run].set_index("patient_id")
            ids = sorted(set(left.index) & set(right.index))
            if not ids:
                raise PrimaryCVError("paired comparison has no common eligible IDs: %s" % comparison_id)
            if not left.loc[ids, "fold"].equals(right.loc[ids, "fold"]):
                raise PrimaryCVError("paired comparison fold assignments differ: %s" % comparison_id)
            paired.append({
                "comparison_id": comparison_id,
                "left_run": left_run,
                "right_run": right_run,
                "population": population,
                "common_n": int(len(ids)),
                "common_id_hash": va.canonical_id_hash(ids),
                "paired": True,
                "fold_assignments_identical": True,
                "outer_validation_used_for_selection": False,
            })
    result = {
        "protocol_sha256": va.sha256_file(protocol_path),
        "split": {
            "repeat": va.OUTER_REPEAT,
            "folds": list(range(1, va.OUTER_FOLDS + 1)),
            "seed": va.OUTER_SEED,
            "canonical_sha256": va.canonical_frame_hash(checked_split),
            "regenerated": False,
        },
        "runs": runs,
        "paired_comparisons": paired,
        "predictions": predictions,
        "provenance": {
            "stage": "V2-03",
            "a_only": True,
            "b_data_read": False,
            "fixed_full_A_habitat": True,
            "preprocessing_scope": "outer-training-only",
            "lambda_selection_scope": "outer-training_inner_5fold_only",
            "alpha": va.ALPHA,
            "outer_repeat": va.OUTER_REPEAT,
            "outer_fold_count": va.OUTER_FOLDS,
            "outer_validation_used_for_selection": False,
            "outer_validation_used_for_lambda": False,
            "outer_validation_used_for_habitat_fit": False,
        },
    }
    if output_path is not None:
        va.atomic_write_json(output_path, _serializable_result(result))
    return result


def run_cv_for_testing(frame, split, model_ids=None, **kwargs):
    """Synthetic-only helper; callers must not pass production=True."""
    if kwargs.get("production", False):
        raise PrimaryCVError("synthetic helper cannot run production validation")
    return run_cv(frame, split, model_ids=model_ids, include_paired=False, **kwargs)


run_primary_cv = run_cv


def main(argv=None):  # pragma: no cover - production CLI requires protected inputs
    parser = argparse.ArgumentParser(description="Primary v2 A-only CV")
    parser.add_argument("--frame", required=True, help="authorised local A feature CSV")
    parser.add_argument("--split", required=True, help="frozen repeat-1 split CSV")
    parser.add_argument("--output", required=True, help="local transactional aggregate output")
    args = parser.parse_args(argv)
    frame = pd.read_csv(args.frame)
    split = pd.read_csv(args.split)
    run_cv(frame, split, production=True, output_path=args.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
