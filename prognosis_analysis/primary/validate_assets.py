"""Primary v2 contracts, frozen schemas, and fail-closed asset checks.

This module contains only de-identified contracts and in-memory input
validation.  It never discovers or opens a patient-level source by itself.
Production callers must provide an already authorised A frame and the frozen
repeat-1 split; B callers must use the explicit frozen-prediction gate in
``validate_external.py``.
"""
from __future__ import absolute_import

import hashlib
import json
import os
import re
from collections import OrderedDict

import numpy as np
import pandas as pd


_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PROTOCOL = os.path.join(_HERE, "protocol.json")
PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))

PROTOCOL_ID = "PRIMARY_ANALYSIS_V2"
PROTOCOL_VERSION = "2.0"
OUTER_REPEAT = 1
OUTER_FOLDS = 5
OUTER_SEED = 12345
INNER_FOLDS = 5
ALPHA = 1.0
LAMBDA_COUNT = 20
LAMBDA_MIN_RATIO = 1e-4
CORRELATION_THRESHOLD = 0.90
W07_ARTIFACT_SHA256 = (
    "24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502")
W07_REPEAT1_CANONICAL_SHA256 = (
    "774436340ce68cd70a2c6acd17acbb7fa484fd7f29989f12670dde519c9f376d")

FT_SOURCE_REF = "refs/heads/codex/ft-validation"
FT_SOURCE_COMMIT = "3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34"
A_COHORT_IDENTITY_TOKEN = "A393_W06_endpoint_QC_exact_frozen_modeling_population"
A_COHORT_IDENTITY_SHA256 = (
    "5fd90ac407400d59f4a8ae5f1d492de99b6b0e12eb62ff9bdb33800d9884afe3")
B_COHORT_IDENTITY_TOKEN = (
    "B163_FT06_authorized_frozen_compatible_external_validation_cohort")
B_COHORT_IDENTITY_SHA256 = (
    "0ab1af7a60e63d8d18e30e4db965757b27fefffad7df7e6ea3803f590bdb6583")

BASE_COLUMNS = ("patient_id", "DFS_time", "DFS_event")
CLINICAL_CONTINUOUS = ("年龄", "CEA_log", "thickness", "EID")
CLINICAL_CATEGORICAL = OrderedDict((
    ("mrT_4级", (1, 2, 3, 4)),
    ("mrN_3级", (0, 1, 2, 3)),
))
CLINICAL_BINARY = ("MRF", "mrEMVI", "活检病理非腺癌")
CLINICAL_COLUMNS = CLINICAL_CONTINUOUS + tuple(CLINICAL_CATEGORICAL) + \
    CLINICAL_BINARY
GLOBAL_COLUMNS = (
    "H_high_fraction",
    "sv_median_minus_boundary",
    "sv_IQR",
    "interface_density",
    "H_high_largest_component_tumor_fraction",
    "H_high_radial_burden",
)

R_LOW_FEATURE_NAMES = (
    "original_firstorder_10Percentile",
    "original_firstorder_90Percentile",
    "original_firstorder_Energy",
    "original_firstorder_Entropy",
    "original_firstorder_Mean",
    "original_firstorder_MeanAbsoluteDeviation",
    "original_firstorder_Median",
    "original_firstorder_RootMeanSquared",
    "original_firstorder_TotalEnergy",
    "original_firstorder_Uniformity",
    "original_glcm_Contrast",
    "original_glcm_DifferenceAverage",
    "original_glcm_DifferenceEntropy",
    "original_glcm_Id",
    "original_glcm_Idm",
    "original_glcm_Imc2",
    "original_glcm_InverseVariance",
    "original_glcm_JointEnergy",
    "original_glcm_JointEntropy",
    "original_glcm_MCC",
    "original_glcm_MaximumProbability",
    "original_glcm_SumEntropy",
    "original_gldm_DependenceNonUniformity",
    "original_gldm_DependenceNonUniformityNormalized",
    "original_gldm_DependenceVariance",
    "original_gldm_GrayLevelNonUniformity",
    "original_gldm_LargeDependenceEmphasis",
    "original_gldm_LargeDependenceLowGrayLevelEmphasis",
    "original_gldm_LowGrayLevelEmphasis",
    "original_gldm_SmallDependenceEmphasis",
    "original_glrlm_GrayLevelNonUniformity",
    "original_glrlm_GrayLevelNonUniformityNormalized",
    "original_glrlm_LongRunEmphasis",
    "original_glrlm_LongRunLowGrayLevelEmphasis",
    "original_glrlm_LowGrayLevelRunEmphasis",
    "original_glrlm_RunLengthNonUniformity",
    "original_glrlm_RunLengthNonUniformityNormalized",
    "original_glrlm_RunPercentage",
    "original_glrlm_RunVariance",
    "original_glrlm_ShortRunEmphasis",
    "original_glrlm_ShortRunLowGrayLevelEmphasis",
    "original_glszm_GrayLevelNonUniformityNormalized",
    "original_glszm_LargeAreaEmphasis",
    "original_glszm_LargeAreaHighGrayLevelEmphasis",
    "original_glszm_LargeAreaLowGrayLevelEmphasis",
    "original_glszm_ZoneEntropy",
    "original_glszm_ZonePercentage",
    "original_glszm_ZoneVariance",
    "original_ngtdm_Contrast",
)
R_HIGH_FEATURE_NAMES = (
    "original_firstorder_Mean",
    "original_firstorder_Median",
    "original_firstorder_RootMeanSquared",
    "original_glcm_Correlation",
    "original_gldm_GrayLevelNonUniformity",
    "original_glrlm_GrayLevelNonUniformity",
    "original_glszm_LargeAreaEmphasis",
    "original_glszm_LargeAreaHighGrayLevelEmphasis",
    "original_glszm_ZoneVariance",
    "original_ngtdm_Busyness",
)
W_ORIGINAL_FEATURE_NAMES = (
    "original_shape_Elongation", "original_shape_Flatness",
    "original_shape_LeastAxisLength", "original_shape_MajorAxisLength",
    "original_shape_Maximum2DDiameterColumn",
    "original_shape_Maximum2DDiameterRow",
    "original_shape_Maximum2DDiameterSlice",
    "original_shape_Maximum3DDiameter", "original_shape_MeshVolume",
    "original_shape_MinorAxisLength", "original_shape_Sphericity",
    "original_shape_SurfaceArea", "original_shape_SurfaceVolumeRatio",
    "original_shape_VoxelVolume", "original_firstorder_10Percentile",
    "original_firstorder_90Percentile", "original_firstorder_Energy",
    "original_firstorder_Entropy", "original_firstorder_InterquartileRange",
    "original_firstorder_Kurtosis", "original_firstorder_Maximum",
    "original_firstorder_MeanAbsoluteDeviation", "original_firstorder_Mean",
    "original_firstorder_Median", "original_firstorder_Minimum",
    "original_firstorder_Range",
    "original_firstorder_RobustMeanAbsoluteDeviation",
    "original_firstorder_RootMeanSquared", "original_firstorder_Skewness",
    "original_firstorder_TotalEnergy", "original_firstorder_Uniformity",
    "original_firstorder_Variance", "original_glcm_Autocorrelation",
    "original_glcm_ClusterProminence", "original_glcm_ClusterShade",
    "original_glcm_ClusterTendency", "original_glcm_Contrast",
    "original_glcm_Correlation", "original_glcm_DifferenceAverage",
    "original_glcm_DifferenceEntropy", "original_glcm_DifferenceVariance",
    "original_glcm_Id", "original_glcm_Idm", "original_glcm_Idmn",
    "original_glcm_Idn", "original_glcm_Imc1", "original_glcm_Imc2",
    "original_glcm_InverseVariance", "original_glcm_JointAverage",
    "original_glcm_JointEnergy", "original_glcm_JointEntropy",
    "original_glcm_MCC", "original_glcm_MaximumProbability",
    "original_glcm_SumAverage", "original_glcm_SumEntropy",
    "original_glcm_SumSquares", "original_glrlm_GrayLevelNonUniformity",
    "original_glrlm_GrayLevelNonUniformityNormalized",
    "original_glrlm_GrayLevelVariance",
    "original_glrlm_HighGrayLevelRunEmphasis",
    "original_glrlm_LongRunEmphasis",
    "original_glrlm_LongRunHighGrayLevelEmphasis",
    "original_glrlm_LongRunLowGrayLevelEmphasis",
    "original_glrlm_LowGrayLevelRunEmphasis", "original_glrlm_RunEntropy",
    "original_glrlm_RunLengthNonUniformity",
    "original_glrlm_RunLengthNonUniformityNormalized",
    "original_glrlm_RunPercentage", "original_glrlm_RunVariance",
    "original_glrlm_ShortRunEmphasis",
    "original_glrlm_ShortRunHighGrayLevelEmphasis",
    "original_glrlm_ShortRunLowGrayLevelEmphasis",
    "original_glszm_GrayLevelNonUniformity",
    "original_glszm_GrayLevelNonUniformityNormalized",
    "original_glszm_GrayLevelVariance",
    "original_glszm_HighGrayLevelZoneEmphasis",
    "original_glszm_LargeAreaEmphasis",
    "original_glszm_LargeAreaHighGrayLevelEmphasis",
    "original_glszm_LargeAreaLowGrayLevelEmphasis",
    "original_glszm_LowGrayLevelZoneEmphasis",
    "original_glszm_SizeZoneNonUniformity",
    "original_glszm_SizeZoneNonUniformityNormalized",
    "original_glszm_SmallAreaEmphasis",
    "original_glszm_SmallAreaHighGrayLevelEmphasis",
    "original_glszm_SmallAreaLowGrayLevelEmphasis",
    "original_glszm_ZoneEntropy", "original_glszm_ZonePercentage",
    "original_glszm_ZoneVariance", "original_gldm_DependenceEntropy",
    "original_gldm_DependenceNonUniformity",
    "original_gldm_DependenceNonUniformityNormalized",
    "original_gldm_DependenceVariance",
    "original_gldm_GrayLevelNonUniformity",
    "original_gldm_GrayLevelVariance",
    "original_gldm_HighGrayLevelEmphasis",
    "original_gldm_LargeDependenceEmphasis",
    "original_gldm_LargeDependenceHighGrayLevelEmphasis",
    "original_gldm_LargeDependenceLowGrayLevelEmphasis",
    "original_gldm_LowGrayLevelEmphasis",
    "original_gldm_SmallDependenceEmphasis",
    "original_gldm_SmallDependenceHighGrayLevelEmphasis",
    "original_gldm_SmallDependenceLowGrayLevelEmphasis",
    "original_ngtdm_Busyness", "original_ngtdm_Coarseness",
    "original_ngtdm_Complexity", "original_ngtdm_Contrast",
    "original_ngtdm_Strength",
)

FEATURE_NAMES = {
    "R_low": R_LOW_FEATURE_NAMES,
    "R_high": R_HIGH_FEATURE_NAMES,
    "W_Original": W_ORIGINAL_FEATURE_NAMES,
}
PREFIXES = {"R_low": "R_low__", "R_high": "R_high__", "W_Original": "W__"}
CANDIDATE_HASHES = {
    "R_low": "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0",
    "R_high": "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce",
}
W_ORIGINAL_ORDER_SHA256 = (
    "1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f")

MODEL_SPECS = OrderedDict((
    ("M0", {"blocks": ("C",), "population": "main", "penalized": False}),
    ("M1", {"blocks": ("C", "H_high_fraction"), "population": "main",
             "penalized": False}),
    ("M2", {"blocks": ("C", "G"), "population": "main", "penalized": False}),
    ("M3L", {"blocks": ("C", "G", "R_low"), "population": "R_low",
              "penalized": True}),
    ("M3H", {"blocks": ("C", "G", "R_high"), "population": "R_high",
              "penalized": True}),
    ("M4", {"blocks": ("C", "G", "R_low", "R_high"),
             "population": "dual_radiomics", "penalized": True}),
    ("M5", {"blocks": ("C", "W_Original"),
             "population": "W_Original_available", "penalized": True}),
))
POPULATION_RULES = {
    "main": (),
    "W_Original_available": ("W_Original",),
    "R_low": ("R_low",),
    "R_high": ("R_high",),
    "dual_radiomics": ("R_low", "R_high"),
}
RUN_DEFINITIONS = (
    {"run_id": "M0", "model_id": "M0", "population": "main"},
    {"run_id": "M1", "model_id": "M1", "population": "main"},
    {"run_id": "M2", "model_id": "M2", "population": "main"},
    {"run_id": "M0_W_Original", "model_id": "M0", "population": "W_Original_available"},
    {"run_id": "M5", "model_id": "M5", "population": "W_Original_available"},
    {"run_id": "M2_R_low", "model_id": "M2", "population": "R_low"},
    {"run_id": "M3L", "model_id": "M3L", "population": "R_low"},
    {"run_id": "M2_R_high", "model_id": "M2", "population": "R_high"},
    {"run_id": "M3H", "model_id": "M3H", "population": "R_high"},
    {"run_id": "M2_dual", "model_id": "M2", "population": "dual_radiomics"},
    {"run_id": "M3L_dual", "model_id": "M3L", "population": "dual_radiomics"},
    {"run_id": "M3H_dual", "model_id": "M3H", "population": "dual_radiomics"},
    {"run_id": "M4", "model_id": "M4", "population": "dual_radiomics"},
)
PAIRED_COMPARISONS = (
    ("M0_vs_M1", "M0", "M1", "main"),
    ("M0_vs_M2", "M0", "M2", "main"),
    ("M2_vs_M3L", "M2_R_low", "M3L", "R_low"),
    ("M2_vs_M3H", "M2_R_high", "M3H", "R_high"),
    ("M2_vs_M4", "M2_dual", "M4", "dual_radiomics"),
    ("M3L_vs_M3H", "M3L_dual", "M3H_dual", "dual_radiomics"),
    ("M4_vs_M5", "M4", "M5_dual", "dual_radiomics"),
)


class PrimaryValidationError(ValueError):
    """Raised for a contract, provenance, isolation, or schema violation."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json_hash(payload):
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"))
    return sha256_text(encoded)


def canonical_id_hash(ids):
    values = sorted(str(value).strip() for value in ids)
    if not values or any(not value for value in values):
        raise PrimaryValidationError("identifier hash received a blank ID")
    if len(values) != len(set(values)):
        raise PrimaryValidationError("identifier hash received duplicate IDs")
    return sha256_text("\n".join(values) + "\n")


def canonical_frame_hash(frame, columns=None):
    columns = list(columns or frame.columns)
    try:
        ordered = frame.loc[:, columns]
    except KeyError as exc:
        raise PrimaryValidationError("cannot hash missing columns: %s" % exc)
    # pandas 1.3.5 (the locked analysis environment) names this argument
    # ``line_terminator``; newer pandas releases also expose the spelling
    # ``lineterminator``.  The returned string is hashed directly, so the
    # explicit LF value preserves the canonical newline semantics across both.
    try:
        encoded = ordered.to_csv(index=False, line_terminator="\n")
    except TypeError:
        encoded = ordered.to_csv(index=False, lineterminator="\n")
    return sha256_text(encoded)


def load_protocol(path=DEFAULT_PROTOCOL):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise PrimaryValidationError("Primary v2 protocol is unavailable: %s" % exc)
    validate_protocol(payload)
    return payload


def validate_protocol(protocol):
    if not isinstance(protocol, dict):
        raise PrimaryValidationError("Primary v2 protocol must be an object")
    if protocol.get("protocol_id") != PROTOCOL_ID or \
            protocol.get("protocol_version") != PROTOCOL_VERSION:
        raise PrimaryValidationError("Primary v2 protocol identity mismatch")
    if protocol.get("status") != "transition_registered_scientific_contract":
        raise PrimaryValidationError("Primary v2 protocol is not active")
    habitat = protocol.get("habitat", {})
    if habitat.get("definition_scope") != "fixed full-A habitat" or \
            habitat.get("slic", {}).get("target_supervoxel_scale_mm") != 4 or \
            habitat.get("clustering", {}).get("K") != 2 or \
            habitat.get("clustering", {}).get("n_init") != 100:
        raise PrimaryValidationError("fixed full-A habitat contract mismatch")
    forbidden = set(habitat.get("refit_forbidden", []))
    if not {"CV outer fold", "B external validation", "DFS-based boundary adjustment"}.issubset(forbidden):
        raise PrimaryValidationError("habitat refit boundary is incomplete")
    model_ids = [item.get("id") for item in protocol.get("models", [])]
    if model_ids != list(MODEL_SPECS):
        raise PrimaryValidationError("Primary v2 model set/order mismatch")
    for item in protocol["models"]:
        expected = MODEL_SPECS[item["id"]]
        if tuple(item.get("predictor_blocks", [])) != expected["blocks"]:
            raise PrimaryValidationError("predictor blocks mismatch for %s" % item["id"])
        if expected["penalized"] and item.get("population") != expected["population"]:
            raise PrimaryValidationError("population mismatch for %s" % item["id"])
        if expected["penalized"] and item.get("alpha") != ALPHA:
            raise PrimaryValidationError("Primary v2 alpha is not fixed at 1")
        if not expected["penalized"] and "alpha" in item:
            raise PrimaryValidationError("unpenalized model declares alpha")
    validation = protocol.get("validation", {})
    if validation.get("A_design") != "fixed single-repeat 5-fold outer validation" or \
            validation.get("repeat") != OUTER_REPEAT or \
            validation.get("outer_fold_count") != OUTER_FOLDS or \
            validation.get("split_regeneration") is not False:
        raise PrimaryValidationError("Primary v2 outer validation contract mismatch")
    selection = validation.get("lambda_selection", {})
    if selection.get("scope") != "outer-training only" or \
            selection.get("method") != "inner 5-fold CV within each outer-training set" or \
            selection.get("outer_validation_used_for_lambda") is not False:
        raise PrimaryValidationError("lambda selection is not training-only")
    external = protocol.get("B_external_validation", {})
    if external.get("mode") != "frozen prediction only" or \
            external.get("B_model_freeze_precedes_evaluation") is not True:
        raise PrimaryValidationError("B external validation is not frozen-prediction-only")
    if protocol.get("guardrails", {}).get("A_B_isolation") is not True or \
            protocol.get("guardrails", {}).get("fail_closed_validation") is not True:
        raise PrimaryValidationError("A/B fail-closed guardrails are incomplete")
    timing = protocol.get("transition", {}).get("decision_timing", {})
    if timing.get("ft03_results_visible_at_decision") is not True or \
            timing.get("ft06_results_visible_at_decision") is not True or \
            timing.get("promotion_decision_after_ft06_results_available") is not True:
        raise PrimaryValidationError("post-FT transition timing is not recorded")
    for cohort_key in ("primary_A_modeling", "FT06_authorized_B"):
        _cohort_identity_entry(protocol, cohort_key)
    return True


def protocol_hash(path=DEFAULT_PROTOCOL):
    load_protocol(path)
    return sha256_file(path)


def _require_identity_value(value, expected, label):
    if not isinstance(value, str) or not value.strip():
        raise PrimaryValidationError("%s must be explicit" % label)
    if value != expected:
        raise PrimaryValidationError("%s does not match the frozen contract" % label)


def _require_identity_hash(value, expected, label):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise PrimaryValidationError("%s must be a SHA-256" % label)
    if value.lower() != str(expected).lower():
        raise PrimaryValidationError("%s does not match the frozen contract" % label)


def _cohort_identity_entry(protocol, cohort_key):
    entry = protocol.get("cohort_identities", {}).get(cohort_key, {})
    if not isinstance(entry, dict):
        raise PrimaryValidationError("missing frozen cohort identity: %s" % cohort_key)
    token = entry.get("identity_token")
    digest = entry.get("identity_sha256")
    if not isinstance(token, str) or not token or not isinstance(digest, str):
        raise PrimaryValidationError("frozen cohort identity is incomplete: %s" % cohort_key)
    return entry


def validate_frame_matches_frozen_ids(frame, split_frame, label):
    """Require an exact frame/split ID match without exposing the IDs."""
    if not isinstance(frame, pd.DataFrame) or "patient_id" not in frame.columns:
        raise PrimaryValidationError("%s frame lacks patient_id" % label)
    if not isinstance(split_frame, pd.DataFrame) or "patient_id" not in split_frame.columns:
        raise PrimaryValidationError("%s frozen identity lacks patient_id" % label)
    frame_ids = set(frame["patient_id"].astype(str).str.strip())
    frozen_ids = set(split_frame["patient_id"].astype(str).str.strip())
    if frame_ids != frozen_ids:
        raise PrimaryValidationError("%s frame ID set is not exactly the frozen cohort" % label)
    if len(frame_ids) != len(frame):
        raise PrimaryValidationError("%s frame contains duplicate IDs" % label)
    return True


def validate_a_cohort_binding(frame, split_frame, identity_token,
                              identity_hash, evidence_manifest,
                              protocol_path=DEFAULT_PROTOCOL):
    """Bind a production A frame to the exact frozen A393 identity."""
    protocol = load_protocol(protocol_path)
    expected = _cohort_identity_entry(protocol, "primary_A_modeling")
    _require_identity_value(identity_token, expected["identity_token"],
                            "A cohort identity token")
    _require_identity_hash(identity_hash, expected["identity_sha256"],
                           "A cohort identity hash")
    if not isinstance(evidence_manifest, dict):
        raise PrimaryValidationError("A production run requires the evidence manifest")
    validate_evidence_manifest(evidence_manifest, protocol_path)
    manifest_entry = evidence_manifest.get("cohort_identities", {}).get(
        "primary_A_modeling", {})
    manifest_hash = manifest_entry.get("identity_sha256")
    if manifest_entry.get("identity_token") != identity_token or \
            not isinstance(manifest_hash, str) or \
            manifest_hash.lower() != identity_hash.lower():
        raise PrimaryValidationError("A cohort identity is not bound to the manifest")
    validate_frame_matches_frozen_ids(frame, split_frame, "A production")
    if len(frame) != int(expected.get("n", 393)):
        raise PrimaryValidationError("A production frame is not the frozen A393 population")
    event_count = int(pd.to_numeric(frame["DFS_event"], errors="coerce").sum())
    if event_count != int(expected.get("DFS_events", 89)):
        raise PrimaryValidationError("A production event count is not frozen A393")
    return True


def validate_b_cohort_binding(identity_token, identity_hash, evidence_manifest,
                              external_registration,
                              protocol_path=DEFAULT_PROTOCOL):
    """Bind B predictors to the explicit FT06 authorized B=163 identity."""
    protocol = load_protocol(protocol_path)
    expected = _cohort_identity_entry(protocol, "FT06_authorized_B")
    _require_identity_value(identity_token, expected["identity_token"],
                            "B cohort identity token")
    _require_identity_hash(identity_hash, expected["identity_sha256"],
                           "B cohort identity hash")
    manifest_entry = evidence_manifest.get("cohort_identities", {}).get(
        "FT06_authorized_B", {}) if isinstance(evidence_manifest, dict) else {}
    registration_entry = external_registration.get("authorized_B_cohort", {}) \
        if isinstance(external_registration, dict) else {}
    for label, entry in (("manifest", manifest_entry),
                         ("external registration", registration_entry)):
        entry_hash = entry.get("identity_sha256")
        if entry.get("identity_token") != identity_token or \
                not isinstance(entry_hash, str) or \
                entry_hash.lower() != identity_hash.lower():
            raise PrimaryValidationError("B cohort identity is not bound to %s" % label)
    if manifest_entry.get("n") != 163 or registration_entry.get("n") != 163:
        raise PrimaryValidationError("B identity is not the authorized FT06 B=163 cohort")
    if manifest_entry.get("not_the_same_as_technical_screening_B107") is not True or \
            registration_entry.get("denominator_not_technical_screening_B107") is not True:
        raise PrimaryValidationError("FT06 B=163 and technical B=107 were not kept distinct")
    return True


def _reject_cohort_paths(frame, cohort):
    if "split" in frame.columns:
        values = frame["split"].astype(str).str.strip().str.upper()
        expected = str(cohort).upper()
        if values.ne(expected).any():
            raise PrimaryValidationError("frame contains rows outside %s cohort" % cohort)
    forbidden_prefixes = ("b__", "b_", "b-") if cohort == "A" else ("a__", "a_", "a-")
    for column in frame.columns:
        lowered = str(column).lower()
        if lowered.startswith(forbidden_prefixes):
            raise PrimaryValidationError("cross-cohort input column is not allowed: %s" % column)
        if lowered in {"path", "source_path", "image_path", "roi_path", "input_path", "file_path"}:
            for value in frame[column].dropna().astype(str):
                parts = [item for item in re.split(r"[\\/]", value.lower()) if item]
                if cohort == "A" and ("b" in parts or any(item.startswith(("b_", "b-")) for item in parts)):
                    raise PrimaryValidationError("B path is not allowed in A input")
                if cohort == "B" and ("a" in parts or any(item.startswith(("a_", "a-")) for item in parts)):
                    raise PrimaryValidationError("A path is not allowed in B input")


def _numeric_flag(frame, column):
    if column not in frame.columns:
        raise PrimaryValidationError("missing explicit availability flag: %s" % column)
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any() or not values.isin([0, 1]).all():
        raise PrimaryValidationError("availability flag must be binary: %s" % column)
    return values.astype(int).eq(1)


def availability_mask(frame, block):
    """Resolve technical eligibility without converting structural absence to NA."""
    if block == "W_Original":
        return _numeric_flag(frame, "W_Original_available")
    if block not in ("R_low", "R_high"):
        raise PrimaryValidationError("unknown availability block: %s" % block)
    p3b = {"%s_voxel_count" % block, "%s_state" % block,
           "%s_structurally_defined" % block,
           "%s_technically_extractable" % block}
    present = p3b & set(frame.columns)
    legacy_technical = "%s_technically_available" % block
    has_p3b_specific = any(column in frame.columns for column in (
        "%s_voxel_count" % block, "%s_state" % block,
        "%s_technically_extractable" % block))
    if present and has_p3b_specific:
        if present != p3b:
            raise PrimaryValidationError("%s structural-state fields are incomplete" % block)
        count = pd.to_numeric(frame["%s_voxel_count" % block], errors="coerce")
        structural = _numeric_flag(frame, "%s_structurally_defined" % block)
        technical = _numeric_flag(frame, "%s_technically_extractable" % block)
        state = frame["%s_state" % block].astype(str).str.strip()
        if count.isna().any() or (~np.isfinite(count.to_numpy(dtype=float))).any() or (count < 0).any():
            raise PrimaryValidationError("%s voxel count is invalid" % block)
        expected = pd.Series(np.where(count.eq(0), "structural_absence",
                                      np.where(count < 10, "technical_small_roi", "extractable")),
                             index=state.index)
        state_class = state.map({
            "structural_absence": "structural_absence",
            "structurally_absent": "structural_absence",
            "technical_small_roi": "technical_small_roi",
            "technically_unextractable_small_ROI": "technical_small_roi",
            "extractable": "extractable",
        })
        if state_class.isna().any() or not state_class.eq(expected).all():
            raise PrimaryValidationError("%s structural state disagrees with voxel count" % block)
        if technical.ne(state.eq("extractable")).any():
            raise PrimaryValidationError("%s technical extractability is inconsistent" % block)
        if structural.ne(count.gt(0)).any():
            raise PrimaryValidationError("%s structural definition is inconsistent" % block)
        return state.eq("extractable")
    structural = _numeric_flag(frame, "%s_structurally_defined" % block)
    technical_name = legacy_technical
    if technical_name not in frame.columns:
        technical_name = "%s_technically_extractable" % block
    technical = _numeric_flag(frame, technical_name)
    if (technical & ~structural).any():
        raise PrimaryValidationError("%s technical availability exceeds structure" % block)
    return structural & technical


def block_columns(frame, block):
    if block == "C":
        return list(CLINICAL_COLUMNS)
    if block == "G":
        return list(GLOBAL_COLUMNS)
    if block == "H_high_fraction":
        return ["H_high_fraction"]
    if block not in PREFIXES:
        raise PrimaryValidationError("unknown predictor block: %s" % block)
    expected = [PREFIXES[block] + name for name in FEATURE_NAMES[block]]
    actual = [str(column) for column in frame.columns
              if str(column).startswith(PREFIXES[block])]
    if actual != expected:
        raise PrimaryValidationError("%s feature order/identity is not frozen" % block)
    return expected


def validate_predictor_frame(frame, model_ids=None, cohort="A", require_outcome=True):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise PrimaryValidationError("predictor frame must be a non-empty DataFrame")
    frame = frame.copy()
    _reject_cohort_paths(frame, cohort)
    if "patient_id" not in frame.columns:
        raise PrimaryValidationError("patient_id is required")
    identifiers = frame["patient_id"].astype(str).str.strip()
    if identifiers.eq("").any() or identifiers.duplicated().any():
        raise PrimaryValidationError("patient_id must be nonempty and unique")
    if require_outcome:
        missing = sorted(set(BASE_COLUMNS) - set(frame.columns))
        if missing:
            raise PrimaryValidationError("missing endpoint columns: %s" % missing)
        time = pd.to_numeric(frame["DFS_time"], errors="coerce")
        event = pd.to_numeric(frame["DFS_event"], errors="coerce")
        if time.isna().any() or (~np.isfinite(time.to_numpy(dtype=float))).any() or (time <= 0).any():
            raise PrimaryValidationError("DFS_time must be finite and positive")
        if event.isna().any() or not event.isin([0, 1]).all():
            raise PrimaryValidationError("DFS_event must be binary")
    model_ids = list(MODEL_SPECS if model_ids is None else model_ids)
    needed_blocks = set()
    for model_id in model_ids:
        if model_id not in MODEL_SPECS:
            raise PrimaryValidationError("unknown Primary v2 model: %s" % model_id)
        needed_blocks.update(MODEL_SPECS[model_id]["blocks"])
    missing = sorted(set(CLINICAL_COLUMNS) - set(frame.columns))
    if missing:
        raise PrimaryValidationError("missing frozen clinical columns: %s" % missing)
    for block in needed_blocks:
        for column in block_columns(frame, block):
            if column not in frame.columns:
                raise PrimaryValidationError("missing frozen feature: %s" % column)
    for block in ("R_low", "R_high", "W_Original"):
        if block in needed_blocks:
            availability_mask(frame, block)
    for block in ("R_low", "R_high"):
        availability_fields = {
            "%s_voxel_count" % block, "%s_state" % block,
            "%s_structurally_defined" % block,
            "%s_technically_extractable" % block,
            "%s_technically_available" % block,
        }
        if availability_fields & set(frame.columns):
            availability_mask(frame, block)
    all_w = [str(column) for column in frame.columns if str(column).startswith("W__")]
    if all_w and all_w != ["W__" + name for name in W_ORIGINAL_FEATURE_NAMES]:
        raise PrimaryValidationError("filtered or reordered whole-tumor features are excluded")
    return frame


def eligibility_mask(frame, population):
    if population not in POPULATION_RULES:
        raise PrimaryValidationError("unknown Primary v2 population: %s" % population)
    mask = pd.Series(True, index=frame.index)
    for block in POPULATION_RULES[population]:
        mask &= availability_mask(frame, block)
    return mask


def validate_split(split_frame, frame=None, production=False):
    if not isinstance(split_frame, pd.DataFrame):
        raise PrimaryValidationError("frozen split must be a DataFrame")
    required = ["patient_id", "repeat", "fold", "role", "seed"]
    if not set(required).issubset(split_frame.columns):
        raise PrimaryValidationError("frozen split schema is incomplete")
    split = split_frame.loc[:, required].copy()
    split["patient_id"] = split["patient_id"].astype(str).str.strip()
    split["repeat"] = pd.to_numeric(split["repeat"], errors="coerce")
    split["fold"] = pd.to_numeric(split["fold"], errors="coerce")
    split["seed"] = pd.to_numeric(split["seed"], errors="coerce")
    if split[["repeat", "fold", "seed"]].isna().any().any():
        raise PrimaryValidationError("frozen split numeric fields are invalid")
    split["repeat"] = split["repeat"].astype(int)
    split["fold"] = split["fold"].astype(int)
    split["seed"] = split["seed"].astype(int)
    split["role"] = split["role"].astype(str).str.strip().str.lower()
    if set(split["repeat"]) != {OUTER_REPEAT}:
        raise PrimaryValidationError("Primary v2 accepts only repeat-1 split")
    if set(split["fold"]) != set(range(1, OUTER_FOLDS + 1)) or set(split["role"]) != {"train", "validation"}:
        raise PrimaryValidationError("frozen split must contain five train/validation folds")
    if set(split["seed"]) != {OUTER_SEED}:
        raise PrimaryValidationError("frozen split seed is not Primary v2 seed 12345")
    validation_ids = []
    split_ids = set(split["patient_id"])
    if not split_ids or "" in split_ids:
        raise PrimaryValidationError("frozen split contains a blank identifier")
    for fold in range(1, OUTER_FOLDS + 1):
        current = split[split["fold"].eq(fold)]
        train = current.loc[current["role"].eq("train"), "patient_id"]
        valid = current.loc[current["role"].eq("validation"), "patient_id"]
        if train.empty or valid.empty or train.duplicated().any() or valid.duplicated().any():
            raise PrimaryValidationError("fold %d train/validation IDs are invalid" % fold)
        if set(train) & set(valid):
            raise PrimaryValidationError("fold %d train/validation overlap" % fold)
        validation_ids.extend(valid.tolist())
    if len(validation_ids) != len(set(validation_ids)):
        raise PrimaryValidationError("validation IDs repeat within repeat 1")
    if frame is not None:
        frame_ids = set(frame["patient_id"].astype(str))
        if production and frame_ids != split_ids:
            raise PrimaryValidationError(
                "production A frame must equal the frozen A393 ID set exactly")
        if not production and not frame_ids.issubset(split_ids):
            raise PrimaryValidationError("frame contains IDs absent from frozen split")
    if production:
        if len(split_ids) != 393 or len(split) != 393 * OUTER_FOLDS:
            raise PrimaryValidationError("production repeat-1 split is not A393")
        if canonical_frame_hash(split, required) != W07_REPEAT1_CANONICAL_SHA256:
            raise PrimaryValidationError("production repeat-1 split hash mismatch")
    return split.reset_index(drop=True)


def validate_asset_record(record, label):
    if not isinstance(record, dict):
        raise PrimaryValidationError("%s source binding must be an object" % label)
    path = record.get("path")
    digest = record.get("sha256")
    if not isinstance(path, str) or not path or not isinstance(digest, str) or \
            not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        raise PrimaryValidationError("%s source binding lacks path/SHA-256" % label)
    return {"path": path, "sha256": digest.lower()}


def atomic_write_json(path, payload):
    """Write a JSON artifact transactionally to an explicitly selected path."""
    target = os.path.abspath(os.fspath(path))
    parent = os.path.dirname(target)
    if not parent or not os.path.isdir(parent):
        raise PrimaryValidationError("output parent does not exist: %s" % parent)
    temporary = target + ".tmp-primary-v2"
    encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass
        raise


def source_summary(path, digest, role, **extra):
    record = {"role": role, "path": path, "sha256": digest.lower()}
    record.update(extra)
    validate_asset_record({"path": path, "sha256": digest}, role)
    return record


def validate_evidence_manifest(manifest, protocol_path=DEFAULT_PROTOCOL):
    """Validate promotion metadata without opening any external patient asset."""
    protocol = load_protocol(protocol_path)
    if not isinstance(manifest, dict) or \
            manifest.get("artifact_id") != "PRIMARY_V2_EVIDENCE_MANIFEST" or \
            manifest.get("status") != "PROMOTED_WITHOUT_RECOMPUTATION":
        raise PrimaryValidationError("evidence manifest identity/status mismatch")
    if manifest.get("protocol_id") != protocol["protocol_id"] or \
            manifest.get("protocol_version") != protocol["protocol_version"] or \
            manifest.get("protocol_path") != "prognosis_analysis/primary/protocol.json":
        raise PrimaryValidationError("evidence manifest protocol identity mismatch")
    current_protocol_hash = sha256_file(protocol_path)
    if manifest.get("protocol_sha256") != current_protocol_hash:
        raise PrimaryValidationError("evidence manifest protocol hash mismatch")
    promotion = manifest.get("promotion", {})
    timing = promotion.get("decision_timing", {})
    if promotion.get("recomputation") is not False or \
            promotion.get("patient_level_material_copied") is not False or \
            timing != {
                "ft03_results_visible_at_decision": True,
                "ft06_results_visible_at_decision": True,
                "promotion_decision_after_ft06_results_available": True,
                "retrospective_prespecification_claim": False,
            }:
        raise PrimaryValidationError("evidence promotion is not metadata-only")
    expected_ref = protocol["evidence_registry"]["source_git_ref"]
    expected_commit = protocol["evidence_registry"]["source_git_commit"]
    source_git = manifest.get("source_git", {})
    if source_git.get("ref") != expected_ref or \
            source_git.get("commit") != expected_commit or \
            source_git.get("source_files_are_external_bindings") is not True:
        raise PrimaryValidationError("FT source binding is not the accepted commit")
    evidence = manifest.get("evidence", {})
    for stage in ("FT03", "FT04", "FT06"):
        if stage not in evidence:
            raise PrimaryValidationError("missing promoted evidence: %s" % stage)
    ft03_expected = protocol["evidence_registry"]["FT03"]
    ft03 = evidence["FT03"]
    if ft03.get("status") != ft03_expected.get("status"):
        raise PrimaryValidationError("FT03 status is not the accepted state")
    validate_asset_record(ft03.get("aggregate", {}), "FT03 aggregate")
    validate_asset_record(ft03.get("report", {}), "FT03 report")
    if ft03["aggregate"] != ft03_expected["aggregate_json"] or \
            ft03["report"] != ft03_expected["report"]:
        raise PrimaryValidationError("FT03 source path/hash binding mismatch")
    if ft03.get("A_identity") != {
        "n": 393, "DFS_events": 89, "DFS_censored": 304,
        "validation": "single repeat-1 outer five-fold; A-only",
        "identity_token": A_COHORT_IDENTITY_TOKEN,
        "identity_sha256": A_COHORT_IDENTITY_SHA256,
    }:
        raise PrimaryValidationError("FT03 A identity is incomplete")

    ft04_expected = protocol["evidence_registry"]["FT04"]
    ft04 = evidence["FT04"]
    if ft04.get("status") != "ACCEPTED / FROZEN":
        raise PrimaryValidationError("FT04 status is not the accepted frozen state")
    lock = evidence["FT04"].get("lock", {})
    validate_asset_record({"path": lock.get("path"),
                           "sha256": lock.get("serialized_sha256")}, "FT04 lock")
    validate_asset_record({"path": lock.get("attestation_path"),
                           "sha256": lock.get("attestation_sha256")}, "FT04 attestation")
    if lock.get("path") != ft04_expected["lock_path"] or \
            lock.get("serialized_sha256") != ft04_expected["serialized_lock_sha256"] or \
            lock.get("identity_sha256") != ft04_expected["lock_identity_sha256"] or \
            lock.get("attestation_path") != ft04_expected["lock_attestation_path"] or \
            lock.get("attestation_sha256") != ft04_expected["lock_attestation_sha256"]:
        raise PrimaryValidationError("FT04 source path/hash binding mismatch")

    ft06_expected = protocol["evidence_registry"]["FT06"]
    ft06 = evidence["FT06"]
    if ft06.get("status") != ft06_expected.get("status") or \
            ft06.get("final_disposition") != ft06_expected.get("final_disposition"):
        raise PrimaryValidationError("FT06 status/disposition is not accepted")
    validate_asset_record(ft06.get("aggregate", {}), "FT06 aggregate")
    validate_asset_record(ft06.get("report", {}), "FT06 report")
    if ft06["aggregate"] != ft06_expected["aggregate_json"] or \
            ft06["report"] != ft06_expected["report"]:
        raise PrimaryValidationError("FT06 source path/hash binding mismatch")
    expected_b = _cohort_identity_entry(protocol, "FT06_authorized_B")
    expected_b_identity = {
        "n": 163,
        "DFS_events": 42,
        "DFS_censored": 121,
        "identity_token": expected_b["identity_token"],
        "identity_sha256": expected_b["identity_sha256"],
        "source_identity": "FT06 authorized frozen-compatible B validation cohort",
        "technical_screening_B107_is_not_merged": True,
    }
    if ft06.get("authorized_B_identity") != expected_b_identity:
        raise PrimaryValidationError("FT06 B identity/timing binding is incomplete")

    for cohort_key, values in protocol.get("cohort_identities", {}).items():
        actual = manifest.get("cohort_identities", {}).get(cohort_key, {})
        for field in ("identity_token", "identity_sha256", "n"):
            if actual.get(field) != values.get(field):
                raise PrimaryValidationError("manifest cohort identity mismatch: %s" % cohort_key)
        for field in ("DFS_events", "DFS_censored"):
            if field in values and actual.get(field) != values[field]:
                raise PrimaryValidationError("manifest cohort counts mismatch: %s" % cohort_key)
    primary_a = manifest.get("cohort_identities", {}).get("primary_A_modeling", {})
    if primary_a.get("not_the_same_as_technical_screening_B107") is not None:
        raise PrimaryValidationError("A cohort identity contains an invalid B distinction")

    for block in ("R_low", "R_high"):
        entry = manifest.get("technical_assets", {}).get(block, {})
        validate_asset_record({"path": entry.get("candidate_freeze_path"),
                               "sha256": entry.get("candidate_freeze_sha256")},
                              block + " candidate freeze")
        expected_count = 49 if block == "R_low" else 10
        if entry.get("count") != expected_count or entry.get("candidate_sha256") != CANDIDATE_HASHES[block]:
            raise PrimaryValidationError("%s candidate identity is invalid" % block)
    whole = manifest.get("technical_assets", {}).get("W_Original", {})
    validate_asset_record({"path": whole.get("asset_path"),
                           "sha256": whole.get("asset_sha256")}, "W_Original asset")
    if whole.get("count") != 107 or whole.get("order_sha256") != W_ORIGINAL_ORDER_SHA256:
        raise PrimaryValidationError("W_Original identity is invalid")
    clinical = manifest.get("technical_assets", {}).get("clinical_schema", {})
    validate_asset_record({"path": clinical.get("path"),
                           "sha256": clinical.get("sha256")}, "clinical schema")
    isolation = manifest.get("isolation", {})
    expected_isolation = {
        "A_B_isolation": True,
        "B_prediction_frozen_before_evaluation": True,
        "B_frozen_prediction_only": True,
        "B_tuning": False,
        "B_refit": False,
        "B_cutoff_optimization": False,
        "B_habitat_refit": False,
        "B_radiomics_candidate_reselection": False,
        "B_to_A_feedback": False,
    }
    if isolation != expected_isolation:
        raise PrimaryValidationError("evidence isolation guard is incomplete")
    return True
