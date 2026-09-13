"""Strict validation for the second-stage A-only model-freeze lock.

The lock is the only authorization source for any B-set read.  This module
does not create a lock; W13 is responsible for producing the real artifact.
"""
from __future__ import annotations

import json
import math
import os


MODEL_FREEZE_SCHEMA_VERSION = "1.0"
SHA256_LENGTH = 64
MODEL_FREEZE_LOCK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                 "model_freeze_lock.json")

REQUIRED_MODEL_FREEZE_FIELDS = (
    "model_freeze_schema_version",
    "A_modeling_population_hash",
    "A393_id_hash",
    "A137_id_hash",
    "freeze_lock_hash",
    "preprocessing_config_hash",
    "slic_config_hash",
    "global_center_low",
    "global_center_high",
    "global_boundary",
    "modeling_protocol_hash",
    "outer_split_hash",
    "outcome_definition_hash",
    "candidate_pool_hashes",
    "final_model_id",
    "final_model_family",
    "final_model_feature_list_hash",
    "final_model_coefficients_hash",
    "preprocessing_parameter_hash",
    "baseline_survival_hash",
    "final_model_artifact_hash",
    "A_model_development_complete",
    "A_model_frozen",
    "B_data_read",
    "B_validation_unlocked",
)

HASH_FIELDS = {
    "A_modeling_population_hash",
    "A393_id_hash",
    "A137_id_hash",
    "freeze_lock_hash",
    "preprocessing_config_hash",
    "slic_config_hash",
    "modeling_protocol_hash",
    "outer_split_hash",
    "outcome_definition_hash",
    "final_model_feature_list_hash",
    "final_model_coefficients_hash",
    "preprocessing_parameter_hash",
    "baseline_survival_hash",
    "final_model_artifact_hash",
}


def _is_sha256(value):
    return (isinstance(value, str) and len(value) == SHA256_LENGTH and
            all(char in "0123456789abcdef" for char in value))


def _required_field_errors(payload):
    errors = []
    for field in REQUIRED_MODEL_FREEZE_FIELDS:
        if field not in payload:
            errors.append("missing required field: %s" % field)
    if payload.get("model_freeze_schema_version") != MODEL_FREEZE_SCHEMA_VERSION:
        errors.append("model_freeze_schema_version=%r (expected %r)" % (
            payload.get("model_freeze_schema_version"), MODEL_FREEZE_SCHEMA_VERSION))
    for field in HASH_FIELDS:
        if field in payload and not _is_sha256(payload[field]):
            errors.append("%s is not a lowercase SHA-256" % field)
    candidate_hashes = payload.get("candidate_pool_hashes")
    if not isinstance(candidate_hashes, dict) or not candidate_hashes:
        errors.append("candidate_pool_hashes must be a non-empty mapping")
    elif any(not isinstance(key, str) or not _is_sha256(value)
             for key, value in candidate_hashes.items()):
        errors.append("candidate_pool_hashes values must be lowercase SHA-256 hashes")
    for field in ("global_center_low", "global_center_high", "global_boundary"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            errors.append("%s must be a finite number" % field)
    expected_booleans = {
        "A_model_development_complete": True,
        "A_model_frozen": True,
        "B_data_read": False,
        "B_validation_unlocked": True,
    }
    for field, expected in expected_booleans.items():
        if field in payload and (type(payload[field]) is not bool or payload[field] is not expected):
            errors.append("%s=%r (expected %r)" % (field, payload[field], expected))
    for field in ("final_model_id", "final_model_family"):
        if field in payload and (not isinstance(payload[field], str) or not payload[field].strip()):
            errors.append("%s must be a non-empty string" % field)
    return errors


def validate_model_freeze_lock(path=None):
    """Return a valid lock payload or hard-fail closed.

    The caller must invoke this function before opening any B clinical,
    outcome, radiomics, habitat, or QC file.
    """
    path = path or MODEL_FREEZE_LOCK
    if not os.path.exists(path):
        raise RuntimeError("model_freeze_lock.json is missing; B access remains locked")
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RuntimeError("invalid model freeze lock: %s" % exc)
    if not isinstance(payload, dict):
        raise RuntimeError("invalid model freeze lock: top-level JSON value must be an object")
    errors = _required_field_errors(payload)
    if errors:
        raise RuntimeError("invalid model freeze lock: " + "; ".join(errors))
    return payload
