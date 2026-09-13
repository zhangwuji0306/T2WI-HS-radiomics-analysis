"""Primary v2 frozen-prediction-only B registration and runtime gate."""
from __future__ import absolute_import

import argparse
import json
import os

import numpy as np
import pandas as pd

try:
    from . import validate_assets as va
    from . import refit_freeze
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    import validate_assets as va
    import refit_freeze


class ExternalValidationError(va.PrimaryValidationError):
    """Raised when the frozen B prediction boundary is not satisfied."""


FORBIDDEN_B_ACTIONS = (
    "feature_selection", "lambda_tuning", "coefficient_refit",
    "cutoff_optimization", "habitat_refit", "radiomics_candidate_reselection",
    "B_to_A_feedback",
)


def load_canonical_lock(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lock = json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise ExternalValidationError("canonical model lock is unavailable: %s" % exc)
    refit_freeze.validate_canonical_lock(lock)
    return lock


def validate_frozen_b_predictors(feature_frame, model_id, lock):
    """Validate B predictors only after a validated frozen model is supplied."""
    if model_id not in va.MODEL_SPECS:
        raise ExternalValidationError("unknown frozen model: %s" % model_id)
    refit_freeze.validate_canonical_lock(lock)
    if lock.get("models", {}).get(model_id, {}).get("coefficient_verification") != \
            "requires protected runtime verification":
        raise ExternalValidationError("model identity verification state is invalid")
    checked = va.validate_predictor_frame(
        feature_frame, [model_id], cohort="B", require_outcome=False)
    population = va.MODEL_SPECS[model_id]["population"]
    eligible = va.eligibility_mask(checked, population)
    if not eligible.any():
        raise ExternalValidationError("B has no eligible frozen predictors for %s" % model_id)
    return {
        "frame": checked,
        "eligible_mask": eligible,
        "eligible_n": int(eligible.sum()),
        "model_id": model_id,
        "population": population,
        "gate": {
            "frozen_model_validated_before_predict": True,
            "frozen_prediction_only": True,
            "outcome_required_for_predict": False,
            "B_tuning": False,
            "B_refit": False,
            "B_feature_selection": False,
            "B_cutoff_optimization": False,
            "B_habitat_refit": False,
            "B_radiomics_candidate_reselection": False,
            "B_to_A_feedback": False,
        },
    }


def _validate_protected_state(state, model_id, lock):
    if not isinstance(state, dict):
        raise ExternalValidationError("protected frozen state must be a dict")
    if state.get("model_id") != model_id:
        raise ExternalValidationError("protected state model identity mismatch")
    expected = lock["models"][model_id]
    state_order_hash = state.get("feature_order_sha256", state.get(
        "transformed_feature_order_sha256"))
    if state.get("model_input_hash") != expected.get("model_input_hash") or \
            state_order_hash != expected.get("transformed_feature_order_sha256"):
        raise ExternalValidationError("protected state does not match frozen identity")
    model = state.get("model")
    preprocessor = state.get("preprocessor")
    if model is None or preprocessor is None:
        raise ExternalValidationError("protected runtime model/preprocessor is required")
    return model, preprocessor


def predict_frozen(feature_frame, model_id, protected_state, lock):
    """Predict with an already frozen model; no B fitting or outcome read occurs."""
    gate = validate_frozen_b_predictors(feature_frame, model_id, lock)
    model, preprocessor = _validate_protected_state(protected_state, model_id, lock)
    selected = gate["frame"].loc[gate["eligible_mask"]].reset_index(drop=True)
    try:
        X = preprocessor.transform(selected)
        risk = np.asarray(model.predict_risk(X), dtype=float)
    except Exception as exc:
        raise ExternalValidationError("frozen B prediction failed: %s" % exc)
    if len(risk) != len(selected) or not np.isfinite(risk).all():
        raise ExternalValidationError("frozen B risk prediction is invalid")
    horizons = {"3_year": 36.0, "5_year": 60.0}
    survival = model.predict_survival(X, horizons)
    output = pd.DataFrame({
        "patient_id": selected["patient_id"].astype(str),
        "risk_score": risk,
        "survival_probability_36": np.asarray(survival["3_year"], dtype=float),
        "survival_probability_60": np.asarray(survival["5_year"], dtype=float),
    })
    if not np.isfinite(output.iloc[:, 1:].to_numpy(dtype=float)).all():
        raise ExternalValidationError("frozen B survival prediction is invalid")
    output.attrs["model_id"] = model_id
    output.attrs["frozen_prediction_only"] = True
    output.attrs["B_outcome_read_before_predict"] = False
    return output


def evaluate_frozen_predictions(predictions, outcome_frame, model_id, lock):
    """Evaluate predictions against B outcomes after the freeze gate."""
    refit_freeze.validate_canonical_lock(lock)
    if not isinstance(predictions, pd.DataFrame) or not predictions.attrs.get("frozen_prediction_only"):
        raise ExternalValidationError("evaluation requires predictions from predict_frozen")
    if predictions.attrs.get("model_id") != model_id:
        raise ExternalValidationError("prediction model identity mismatch")
    outcome = va.validate_predictor_frame(
        outcome_frame, [model_id], cohort="B", require_outcome=True)
    prediction_ids = set(predictions["patient_id"].astype(str))
    if prediction_ids != set(outcome.loc[va.eligibility_mask(outcome, va.MODEL_SPECS[model_id]["population"]), "patient_id"].astype(str)):
        raise ExternalValidationError("B outcome and frozen prediction eligibility do not match")
    merged = outcome.set_index(outcome["patient_id"].astype(str)).loc[
        sorted(prediction_ids)]
    aligned = predictions.set_index(predictions["patient_id"].astype(str)).loc[
        sorted(prediction_ids)]
    # Keep the actual metric implementation in the canonical A runner; this
    # registration function intentionally returns only non-patient-level state.
    try:
        from . import final_report
    except (ImportError, ValueError):  # pragma: no cover
        import final_report
    risk = aligned["risk_score"].to_numpy(dtype=float)
    time = merged["DFS_time"].to_numpy(dtype=float)
    event = merged["DFS_event"].to_numpy(dtype=int)
    metrics = final_report.basic_survival_metrics(time, event, risk)
    return {
        "model_id": model_id,
        "eligible_n": int(len(merged)),
        "DFS_events": int(event.sum()),
        "metrics": metrics,
        "gate": {
            "B_prediction_frozen_before_evaluation": True,
            "B_tuning": False,
            "B_refit": False,
            "B_to_A_feedback": False,
        },
    }


def build_external_registration(ft06_aggregate, ft06_json_sha256,
                                ft06_report_sha256, lock, source_ref,
                                source_commit="3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34",
                                registration_date="2026-09-13"):
    """Register FT06 without copying its patient-level predictions or metrics."""
    refit_freeze.validate_canonical_lock(lock)
    if not isinstance(ft06_aggregate, dict) or ft06_aggregate.get("status") != "COMPLETE":
        raise ExternalValidationError("FT06 source is not complete")
    if ft06_aggregate.get("final_disposition") != "FT-INCONCLUSIVE":
        raise ExternalValidationError("FT06 disposition is not the accepted source state")
    gate = ft06_aggregate.get("gate", {})
    safety = ft06_aggregate.get("safety", {})
    validation = ft06_aggregate.get("validation", {})
    required_true = (
        "no_fit", "no_lambda_tuning", "no_feature_selection", "no_cutoff_tuning",
        "no_habitat_refit", "no_radiomics_reextraction",
    )
    if gate.get("status") != "AUTHORIZED" or \
            any(gate.get(key) is not True for key in required_true) or \
            gate.get("b_to_a_feedback") is not False:
        raise ExternalValidationError("FT06 authorization gate is invalid")
    if safety.get("predict_only") is not True or \
            validation.get("all_predictions_frozen_state_only") is not True or \
            validation.get("b_outcome_read_after_gate") is not True:
        raise ExternalValidationError("FT06 frozen-prediction evidence is incomplete")
    cohort = ft06_aggregate.get("cohort", {})
    if cohort.get("n") != 163 or cohort.get("events") != 42 or cohort.get("censored") != 121:
        raise ExternalValidationError("FT06 authorized B cohort identity mismatch")
    va.validate_asset_record({"path": "prognosis_analysis/ft/FT06_B_validation.json",
                              "sha256": ft06_json_sha256}, "FT06 aggregate")
    va.validate_asset_record({"path": "prognosis_analysis/ft/FT06_B_validation_report.md",
                              "sha256": ft06_report_sha256}, "FT06 report")
    return {
        "schema_version": "1.0",
        "artifact_id": "PRIMARY_V2_EXTERNAL_VALIDATION_REGISTRATION",
        "status": "REGISTERED_FT06_EVIDENCE",
        "source": {
            "ref": source_ref,
            "commit": source_commit,
            "aggregate": {
                "path": "prognosis_analysis/ft/FT06_B_validation.json",
                "sha256": ft06_json_sha256.lower(),
            },
            "report": {
                "path": "prognosis_analysis/ft/FT06_B_validation_report.md",
                "sha256": ft06_report_sha256.lower(),
            },
            "immutable": True,
        },
        "protocol_sha256": lock["Primary_v2_protocol_hash"],
        "model_freeze": {
            "canonical_lock_artifact": "prognosis_analysis/primary/model_freeze_lock.json",
            "canonical_lock_hash": va.sha256_text(json.dumps(lock, ensure_ascii=False,
                                                               sort_keys=True, separators=(",", ":"))),
            "B_prediction_was_frozen_before_B_evaluation": True,
        },
        "promotion_timing": {
            "Primary_v2_promotion_decision_occurred_after_FT_B_results_were_available": True,
            "FT03_results_visible_at_decision": True,
            "FT06_results_visible_at_decision": True,
            "retrospective_prespecification_claim": False,
        },
        "authorized_B_cohort": {
            "n": 163,
            "DFS_events": 42,
            "DFS_censored": 121,
            "identity_source": "FT06 aggregate cohort object",
            "denominator_not_technical_screening_B107": True,
        },
        "patient_level_material_copied": False,
        "predictions_and_metrics_recomputed": False,
        "forbidden_actions": list(FORBIDDEN_B_ACTIONS),
        "registered_at": registration_date,
    }


def main(argv=None):  # pragma: no cover - requires explicit non-repository FT source
    parser = argparse.ArgumentParser(description="Register frozen FT06 evidence")
    parser.add_argument("--ft06-json", required=True)
    parser.add_argument("--ft06-report-sha256", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-ref", default="refs/heads/codex/ft-validation")
    args = parser.parse_args(argv)
    aggregate = json.load(open(args.ft06_json, "r", encoding="utf-8"))
    lock = load_canonical_lock(args.lock)
    registration = build_external_registration(
        aggregate, va.sha256_file(args.ft06_json), args.ft06_report_sha256,
        lock, args.source_ref)
    va.atomic_write_json(args.output, registration)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
