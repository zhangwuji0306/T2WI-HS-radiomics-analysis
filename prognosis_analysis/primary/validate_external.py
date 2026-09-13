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
    "B feature selection", "B lambda tuning", "B coefficient refit",
    "B cutoff optimization", "B habitat refit",
    "B radiomics candidate re-selection", "B to A feedback",
)


def load_canonical_lock(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            lock = json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise ExternalValidationError("canonical model lock is unavailable: %s" % exc)
    refit_freeze.validate_canonical_lock(lock)
    return lock


def validate_external_registration(registration, lock, evidence_manifest,
                                   protocol_path=va.DEFAULT_PROTOCOL):
    """Validate the complete non-patient-level FT06 provenance handoff."""
    protocol = va.load_protocol(protocol_path)
    va.validate_evidence_manifest(evidence_manifest, protocol_path)
    refit_freeze.validate_canonical_lock(lock, protocol_path)
    if not isinstance(registration, dict) or \
            registration.get("artifact_id") != \
            "PRIMARY_V2_EXTERNAL_VALIDATION_REGISTRATION" or \
            registration.get("status") != "REGISTERED_FT06_EVIDENCE":
        raise ExternalValidationError("external registration identity/status mismatch")
    if registration.get("protocol_sha256") != va.sha256_file(protocol_path):
        raise ExternalValidationError("external registration protocol hash mismatch")
    expected_registry = protocol["evidence_registry"]
    source = registration.get("source", {})
    if source.get("ref") != expected_registry["source_git_ref"] or \
            source.get("commit") != expected_registry["source_git_commit"] or \
            source.get("immutable") is not True or \
            source.get("patient_level_predictions_copied") is not False or \
            source.get("patient_level_metrics_copied") is not False:
        raise ExternalValidationError("external registration source binding mismatch")
    expected_ft06 = expected_registry["FT06"]
    if source.get("aggregate") != expected_ft06["aggregate_json"] or \
            source.get("report") != expected_ft06["report"]:
        raise ExternalValidationError("FT06 source path/hash mismatch")
    expected_lock_hash = va.canonical_json_hash(lock)
    model_freeze = registration.get("model_freeze", {})
    if model_freeze.get("canonical_lock_path") != \
            "prognosis_analysis/primary/model_freeze_lock.json" or \
            model_freeze.get("canonical_lock_sha256") != expected_lock_hash or \
            model_freeze.get("B_prediction_was_frozen_before_B_evaluation") is not True or \
            model_freeze.get("frozen_model_identity_source") != "promoted FT04 lock identity":
        raise ExternalValidationError("external registration model-freeze binding mismatch")
    expected_timing = {
        "Primary_v2_promotion_decision_occurred_after_FT_B_results_were_available": True,
        "FT03_results_visible_at_decision": True,
        "FT06_results_visible_at_decision": True,
        "retrospective_prespecification_claim": False,
    }
    if registration.get("promotion_timing") != expected_timing:
        raise ExternalValidationError("external registration promotion timing is invalid")
    expected_b = va._cohort_identity_entry(protocol, "FT06_authorized_B")
    if registration.get("authorized_B_cohort") != {
            "n": 163,
            "DFS_events": 42,
            "DFS_censored": 121,
            "identity_token": expected_b["identity_token"],
            "identity_sha256": expected_b["identity_sha256"],
            "identity_source": "FT06 aggregate cohort object",
            "technical_screening_reference_B_n": 107,
            "denominator_not_technical_screening_B107": True,
    }:
        raise ExternalValidationError("external registration B identity is invalid")
    if registration.get("allowed_sequence") != [
            "load frozen model", "load frozen-compatible B predictors",
            "predict", "evaluate"]:
        raise ExternalValidationError("external registration sequence is invalid")
    if registration.get("forbidden_actions") != list(FORBIDDEN_B_ACTIONS):
        raise ExternalValidationError("external registration forbidden actions were altered")
    if registration.get("patient_level_material_copied") is not False or \
            registration.get("predictions_and_metrics_recomputed") is not False:
        raise ExternalValidationError("external registration contains patient-level promotion")
    return True


def validate_frozen_b_predictors(feature_frame, model_id, lock,
                                 cohort_identity=None,
                                 cohort_identity_hash=None,
                                 external_registration=None,
                                 evidence_manifest=None,
                                 protocol_path=va.DEFAULT_PROTOCOL):
    """Validate B predictors only after a validated frozen model is supplied."""
    if model_id not in va.MODEL_SPECS:
        raise ExternalValidationError("unknown frozen model: %s" % model_id)
    try:
        validate_external_registration(
            external_registration, lock, evidence_manifest, protocol_path)
        va.validate_b_cohort_binding(
            cohort_identity, cohort_identity_hash, evidence_manifest,
            external_registration, protocol_path)
    except va.PrimaryValidationError as exc:
        raise ExternalValidationError(str(exc))
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


def _runtime_model_identity(model, state):
    keys = ("model_id", "population", "model_input_hash",
            "transformed_feature_order_sha256", "state_sha256")
    identity = getattr(model, "primary_v2_identity", None)
    if isinstance(identity, dict):
        return identity
    if all(hasattr(model, key) for key in keys):
        return {key: getattr(model, key) for key in keys}
    identity = state.get("runtime_model_identity") if isinstance(state, dict) else None
    if isinstance(identity, dict):
        return identity
    raise ExternalValidationError(
        "runtime model object lacks the complete Primary v2 identity")


def _validate_protected_state(state, model_id, lock):
    if not isinstance(state, dict):
        raise ExternalValidationError("protected frozen state must be a dict")
    expected = lock["models"][model_id]
    model = state.get("model")
    preprocessor = state.get("preprocessor")
    if model is None or preprocessor is None:
        raise ExternalValidationError("protected runtime model/preprocessor is required")
    identity = _runtime_model_identity(model, state)
    for field in ("model_id", "population", "model_input_hash",
                  "transformed_feature_order_sha256", "state_sha256"):
        if identity.get(field) != expected.get(field):
            raise ExternalValidationError(
                "protected runtime %s does not match frozen identity" % field)
    feature_names = getattr(preprocessor, "feature_names", None)
    if feature_names is not None and \
            va.canonical_json_hash(list(feature_names)) != \
            expected.get("transformed_feature_order_sha256"):
        raise ExternalValidationError("protected preprocessor feature order is not frozen")
    return model, preprocessor


def predict_frozen(feature_frame, model_id, protected_state, lock,
                   cohort_identity=None, cohort_identity_hash=None,
                   external_registration=None, evidence_manifest=None,
                   protocol_path=va.DEFAULT_PROTOCOL):
    """Predict with an already frozen model; no B fitting or outcome read occurs."""
    gate = validate_frozen_b_predictors(
        feature_frame, model_id, lock, cohort_identity, cohort_identity_hash,
        external_registration, evidence_manifest, protocol_path)
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
    output.attrs["cohort_identity_token"] = cohort_identity
    output.attrs["cohort_identity_sha256"] = cohort_identity_hash
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
                                source_commit=va.FT_SOURCE_COMMIT,
                                registration_date="2026-09-13",
                                protocol_path=va.DEFAULT_PROTOCOL):
    """Register FT06 without copying its patient-level predictions or metrics."""
    protocol = va.load_protocol(protocol_path)
    refit_freeze.validate_canonical_lock(lock, protocol_path)
    expected_registry = protocol["evidence_registry"]
    if source_ref != expected_registry["source_git_ref"] or \
            source_commit != expected_registry["source_git_commit"]:
        raise ExternalValidationError("FT06 source ref/commit is not the accepted binding")
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
    expected_ft06 = expected_registry["FT06"]
    aggregate_record = va.validate_asset_record({
        "path": "prognosis_analysis/ft/FT06_B_validation.json",
        "sha256": ft06_json_sha256,
    }, "FT06 aggregate")
    report_record = va.validate_asset_record({
        "path": "prognosis_analysis/ft/FT06_B_validation_report.md",
        "sha256": ft06_report_sha256,
    }, "FT06 report")
    if aggregate_record != expected_ft06["aggregate_json"] or \
            report_record != expected_ft06["report"]:
        raise ExternalValidationError("FT06 source path/hash is not the accepted binding")
    expected_b = va._cohort_identity_entry(protocol, "FT06_authorized_B")
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
        "protocol_sha256": va.sha256_file(protocol_path),
        "model_freeze": {
            "canonical_lock_path": "prognosis_analysis/primary/model_freeze_lock.json",
            "canonical_lock_sha256": va.canonical_json_hash(lock),
            "B_prediction_was_frozen_before_B_evaluation": True,
            "frozen_model_identity_source": "promoted FT04 lock identity",
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
            "identity_token": expected_b["identity_token"],
            "identity_sha256": expected_b["identity_sha256"],
            "identity_source": "FT06 aggregate cohort object",
            "technical_screening_reference_B_n": 107,
            "denominator_not_technical_screening_B107": True,
        },
        "allowed_sequence": [
            "load frozen model", "load frozen-compatible B predictors",
            "predict", "evaluate",
        ],
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
    parser.add_argument("--source-ref", default=va.FT_SOURCE_REF)
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
