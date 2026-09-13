"""Primary v2 canonical model-freeze registration.

The current transition registers accepted FT04 full-A states; it does not
refit a patient-level model.  A future V2-08 refit may use the in-memory
``run_cv`` primitives after A validation, but this module deliberately keeps
promotion and refit as separate operations.
"""
from __future__ import absolute_import

import argparse
import copy
import json
import os
from collections import OrderedDict

try:
    from . import validate_assets as va
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    import validate_assets as va


class PrimaryFreezeError(va.PrimaryValidationError):
    """Raised when a frozen model identity cannot be registered safely."""


MODEL_IDENTITY_FIELDS = (
    "model_id", "population", "predictor_blocks", "eligible_n", "event_count",
    "model_input_hash", "transformed_feature_count",
    "transformed_feature_order_sha256", "state_sha256", "selection",
)


def _load_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise PrimaryFreezeError("%s is unavailable: %s" % (label, exc))
    if not isinstance(payload, dict):
        raise PrimaryFreezeError("%s must be a JSON object" % label)
    return payload


def _model_identity(summary, model_id):
    if not isinstance(summary, dict):
        raise PrimaryFreezeError("FT04 model summary is not an object: %s" % model_id)
    missing = [field for field in MODEL_IDENTITY_FIELDS if field not in summary]
    if missing:
        raise PrimaryFreezeError("FT04 model summary is incomplete for %s: %s" % (model_id, missing))
    if summary.get("model_id") != model_id:
        raise PrimaryFreezeError("FT04 model identity key mismatch: %s" % model_id)
    if summary.get("predictor_blocks") != list(va.MODEL_SPECS[model_id]["blocks"]):
        raise PrimaryFreezeError("FT04 predictor blocks differ for %s" % model_id)
    selection = summary["selection"]
    if not isinstance(selection, dict):
        raise PrimaryFreezeError("FT04 selection state is invalid for %s" % model_id)
    if va.MODEL_SPECS[model_id]["penalized"]:
        if selection.get("alpha") != va.ALPHA or \
                selection.get("lambda_selection_scope") != "outer_training_inner_5fold_only" or \
                selection.get("outer_validation_used_for_lambda") is not False:
            raise PrimaryFreezeError("FT04 penalized state is not Primary v2 compatible: %s" % model_id)
    else:
        if selection.get("alpha") is not None or \
                selection.get("outer_validation_used_for_lambda") is not False:
            raise PrimaryFreezeError("FT04 unpenalized state is not Primary v2 compatible: %s" % model_id)
    result = {field: copy.deepcopy(summary[field]) for field in MODEL_IDENTITY_FIELDS}
    result["coefficients_available_in_promoted_record"] = False
    result["coefficient_verification"] = "requires protected runtime verification"
    return result


def build_promoted_lock(ft04_lock, protocol_path=va.DEFAULT_PROTOCOL,
                        source_ref="refs/heads/codex/ft-validation",
                        source_commit="3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34",
                        serialized_lock_sha256=None,
                        lock_identity_sha256=None,
                        promotion_date="2026-09-13"):
    """Build a non-patient-level Primary v2 lock from an accepted FT04 lock."""
    protocol = va.load_protocol(protocol_path)
    if ft04_lock.get("status") != "FROZEN" or \
            ft04_lock.get("not_formal_model_freeze_lock") is not True:
        raise PrimaryFreezeError("source is not the accepted exploratory FT04 frozen state")
    if list(ft04_lock.get("model_order", [])) != list(va.MODEL_SPECS):
        raise PrimaryFreezeError("FT04 model order differs from Primary v2")
    if ft04_lock.get("validation", {}).get("b_data_read") is not False:
        raise PrimaryFreezeError("FT04 source does not prove B-blinded freeze")
    if ft04_lock.get("b_access", {}).get("state") != "locked":
        raise PrimaryFreezeError("FT04 B access was not locked at freeze")
    if not serialized_lock_sha256 or not lock_identity_sha256:
        raise PrimaryFreezeError("FT04 serialized and identity hashes are required")
    models = OrderedDict()
    for model_id in va.MODEL_SPECS:
        models[model_id] = _model_identity(ft04_lock["models"].get(model_id), model_id)
    return {
        "schema_version": "1.0",
        "artifact_id": "PRIMARY_V2_CANONICAL_MODEL_FREEZE",
        "status": "FROZEN_CANONICAL_PROMOTED",
        "source": "promoted_from_FT04",
        "source_ref": source_ref,
        "source_commit": source_commit,
        "original_FT04_hash": serialized_lock_sha256.lower(),
        "original_FT04_identity_sha256": lock_identity_sha256.lower(),
        "Primary_v2_protocol_hash": va.sha256_file(protocol_path),
        "promotion_date": promotion_date,
        "no_refit": True,
        "no_B_tuning": True,
        "model_order": list(va.MODEL_SPECS),
        "models": models,
        "verification": {
            "status": "requires protected runtime verification",
            "scope": "coefficients/features/lambda/model identity against FT04 protected states",
            "patient_level_coefficients_copied": False,
            "patient_level_predictions_copied": False,
            "no_coefficients_fabricated": True,
        },
        "provenance": {
            "protocol_path": os.path.relpath(protocol_path, va.PROJECT_ROOT).replace(os.sep, "/"),
            "source_lock_path": "prognosis_analysis/ft/FT_model_freeze_lock.json",
            "source_lock_serialized_sha256": serialized_lock_sha256.lower(),
            "source_lock_identity_sha256": lock_identity_sha256.lower(),
            "fixed_full_A_habitat": True,
            "outer_validation_design": "single repeat-1 five-fold",
            "alpha": va.ALPHA,
            "lambda_selection_scope": "outer-training_inner_5fold_only",
            "B_mode": "frozen prediction only",
        },
    }


def validate_canonical_lock(lock, protocol_path=va.DEFAULT_PROTOCOL):
    va.load_protocol(protocol_path)
    if lock.get("status") != "FROZEN_CANONICAL_PROMOTED" or \
            lock.get("source") != "promoted_from_FT04":
        raise PrimaryFreezeError("canonical lock identity/status mismatch")
    if lock.get("Primary_v2_protocol_hash") != va.sha256_file(protocol_path):
        raise PrimaryFreezeError("canonical lock is bound to a different Primary v2 protocol")
    if lock.get("no_refit") is not True or lock.get("no_B_tuning") is not True:
        raise PrimaryFreezeError("canonical lock does not declare no-refit/no-B-tuning")
    if lock.get("model_order") != list(va.MODEL_SPECS):
        raise PrimaryFreezeError("canonical lock model order mismatch")
    for model_id in va.MODEL_SPECS:
        _model_identity(lock.get("models", {}).get(model_id), model_id)
    return True


def promote_ft04_lock(ft04_lock_path, output_path, **kwargs):
    """Promote an explicitly selected non-patient-level FT04 lock atomically."""
    source = _load_json(ft04_lock_path, "FT04 lock")
    serialized_hash = kwargs.pop("serialized_lock_sha256", va.sha256_file(ft04_lock_path))
    lock = build_promoted_lock(
        source, serialized_lock_sha256=serialized_hash, **kwargs)
    validate_canonical_lock(lock, kwargs.get("protocol_path", va.DEFAULT_PROTOCOL))
    va.atomic_write_json(output_path, lock)
    return lock


def main(argv=None):  # pragma: no cover - explicit source path required
    parser = argparse.ArgumentParser(description="Promote accepted FT04 lock to Primary v2")
    parser.add_argument("--ft04-lock", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--serialized-sha256", required=True)
    parser.add_argument("--identity-sha256", required=True)
    args = parser.parse_args(argv)
    promote_ft04_lock(
        args.ft04_lock, args.output,
        serialized_lock_sha256=args.serialized_sha256,
        lock_identity_sha256=args.identity_sha256,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
