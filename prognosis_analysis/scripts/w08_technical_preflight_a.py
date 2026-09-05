"""Fail-closed, technical-only P5 preflight for the frozen A population.

This module is intentionally independent of the W08 model runner.  Its only
fold outputs are technical support states, de-identified population hashes,
and event/censor feasibility gates.  It never imports a model-fitting,
prediction, or metric implementation.

The production entry point verifies every frozen binding before opening an A
source.  ``run_technical_preflight`` is the in-memory core used by synthetic
regression tests; it accepts only already-normalised A-shaped frames and
returns aggregate records without patient identifiers.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import os
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.model_selection import StratifiedKFold


SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROGNOSIS_ROOT = os.path.dirname(SCRIPT_ROOT)
PROJECT_ROOT = os.path.dirname(PROGNOSIS_ROOT)

W04_PROTOCOL_SHA256 = "888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe"
W03_CANDIDATE_FREEZE_SHA256 = "ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2"
W07_CONFIG_SHA256 = "535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217"
W07_OUTER_SPLIT_SHA256 = "24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502"
W07A_PROTOCOL_SHA256 = "adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70"
W07A_AMENDMENT_JSON_SHA256 = "0ca857a7b22c5b948c675f9970cc07b5a908c3f486be3f5656c86e20b5479f14"
P4R_MANIFEST_SHA256 = "f5c6e14b098717d65b7709c6e8f10feb63c325b929fda64d3b2ccefa52a0cf6b"

MINIMUM_ROI_SIZE = 10
N_OUTER_REPEATS = 10
N_OUTER_FOLDS = 5
N_INNER_FOLDS = 5
BASE_SEED = 12345

SPLIT_COLUMNS = ["patient_id", "repeat", "fold", "role", "seed"]
POPULATION_ID_COLUMNS = ("patient_id", "影像号")
TECHNICAL_ID_COLUMNS = ("patient_id", "影像号")

DEFAULT_W06_POPULATION = os.path.join(
    PROGNOSIS_ROOT, "output", "A_modeling", "A_modeling_population.csv")
DEFAULT_SPLIT = os.path.join(PROGNOSIS_ROOT, "output", "outer_splits_A.csv")
DEFAULT_W07_CONFIG = os.path.join(
    PROGNOSIS_ROOT, "configs", "w07_outer_splits.json")
DEFAULT_W04 = os.path.join(PROGNOSIS_ROOT, "modeling_protocol.json")
DEFAULT_W03_CANDIDATE = os.path.join(
    PROGNOSIS_ROOT, "output", "w03_habitat_radiomics_A", "candidate_freeze.json")
DEFAULT_W07A_MD = os.path.join(
    PROGNOSIS_ROOT, "W07A_pre_W08_protocol_amendment.md")
DEFAULT_W07A_JSON = os.path.join(
    PROGNOSIS_ROOT, "W07A_pre_W08_protocol_amendment.json")
DEFAULT_P4R = os.path.join(
    PROGNOSIS_ROOT, "W07A_pre_W08_provenance_reconciliation.json")
DEFAULT_MODEL_FREEZE_LOCK = os.path.join(
    PROGNOSIS_ROOT, "model_freeze_lock.json")
DEFAULT_SUPERVOXELS = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "output",
    "local_global_diagnostic_A_post_slic_fix", "supervoxel_mean_A.csv")
DEFAULT_R_LOW = os.path.join(
    PROGNOSIS_ROOT, "output", "w03_habitat_radiomics_A",
    "R1_R_low_features.csv")
DEFAULT_R_HIGH = os.path.join(
    PROGNOSIS_ROOT, "output", "w03_habitat_radiomics_A",
    "R1_R_high_features.csv")
DEFAULT_W_FEATURES = (
    os.path.join(PROJECT_ROOT, "feature_extract", "output", "features_v2",
                 "muscle_f0.25", "features_original.csv"),
    os.path.join(PROJECT_ROOT, "feature_extract", "output", "features_v2",
                 "muscle_f0.25", "features_wavelet.csv"),
    os.path.join(PROJECT_ROOT, "feature_extract", "output", "features_v2",
                 "muscle_f0.25", "features_log.csv"),
)
DEFAULT_OUTPUT = os.path.join(
    PROGNOSIS_ROOT, "output", "p5_technical_preflight_A")

FROZEN_CANDIDATE_HASHES = {
    "R_low": "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0",
    "R_high": "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce",
}

RUN_DEFINITIONS = (
    {"run_id": "M0", "population": "main"},
    {"run_id": "M1", "population": "main"},
    {"run_id": "M2", "population": "main"},
    {"run_id": "M0_W_available", "population": "W_available"},
    {"run_id": "M5", "population": "W_available"},
    {"run_id": "M2_R_low", "population": "R_low"},
    {"run_id": "M3L", "population": "R_low"},
    {"run_id": "M2_R_high", "population": "R_high"},
    {"run_id": "M3H", "population": "R_high"},
    {"run_id": "M2_dual_radiomics", "population": "dual_radiomics"},
    {"run_id": "M3L_dual_radiomics", "population": "dual_radiomics"},
    {"run_id": "M3H_dual_radiomics", "population": "dual_radiomics"},
    {"run_id": "M4", "population": "dual_radiomics"},
    {"run_id": "M0-R", "population": "main"},
    {"run_id": "M1-R", "population": "main"},
    {"run_id": "M2-R", "population": "main"},
    {"run_id": "M3L_vs_M3H", "population": "dual_radiomics",
     "comparison_only": True},
)

PAIR_DEFINITIONS = (
    ("M0_W_available", "M5", "W_available"),
    ("M2_R_low", "M3L", "R_low"),
    ("M2_R_high", "M3H", "R_high"),
    ("M2_dual_radiomics", "M3L_dual_radiomics", "dual_radiomics"),
    ("M2_dual_radiomics", "M3H_dual_radiomics", "dual_radiomics"),
    ("M2_dual_radiomics", "M4", "dual_radiomics"),
    ("M3L_dual_radiomics", "M3H_dual_radiomics", "dual_radiomics"),
)

_BINDING_FILES = OrderedDict((
    ("W04_modeling_protocol", ("prognosis_analysis/modeling_protocol.json",
                                W04_PROTOCOL_SHA256)),
    ("W03_candidate_freeze", (
        "prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json",
        W03_CANDIDATE_FREEZE_SHA256)),
    ("W07_outer_split_config", (
        "prognosis_analysis/configs/w07_outer_splits.json", W07_CONFIG_SHA256)),
    ("W07_outer_split_artifact", (
        "prognosis_analysis/output/outer_splits_A.csv", W07_OUTER_SPLIT_SHA256)),
    ("W07A_protocol", (
        "prognosis_analysis/W07A_pre_W08_protocol_amendment.md",
        W07A_PROTOCOL_SHA256)),
    ("W07A_amendment_json", (
        "prognosis_analysis/W07A_pre_W08_protocol_amendment.json",
        W07A_AMENDMENT_JSON_SHA256)),
    ("P4R_reconciliation", (
        "prognosis_analysis/W07A_pre_W08_provenance_reconciliation.json",
        P4R_MANIFEST_SHA256)),
))


class P5ValidationError(ValueError):
    """Raised when a P5 technical or provenance gate fails."""


def _fail(run_id, repeat, fold, population_state, gate_type, detail):
    """Raise a non-identifying, contextual hard failure."""
    raise P5ValidationError(
        "P5 hard-fail: run_id=%s repeat=%s fold=%s population_state=%s "
        "gate_type=%s: %s" %
        (run_id, repeat, fold, population_state, gate_type, detail))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_id_hash(ids):
    """Hash a sorted identifier set without returning any identifier."""
    values = sorted(str(value).strip() for value in ids)
    if not values or any(not value for value in values):
        raise P5ValidationError("identifier hash received an empty set or blank ID")
    return _sha256_text("\n".join(values) + "\n")


def _candidate_hash(features):
    canonical = json.dumps(sorted(set(features)), ensure_ascii=False,
                            separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalise_root(root):
    return os.path.normcase(os.path.abspath(os.fspath(root)))


def _normalise_population(population):
    if not isinstance(population, pd.DataFrame):
        raise P5ValidationError("A modeling population must be a DataFrame")
    frame = population.copy()
    if "patient_id" not in frame.columns:
        if "影像号" in frame.columns:
            frame = frame.rename(columns={"影像号": "patient_id"})
        else:
            raise P5ValidationError("A modeling population lacks patient_id")
    required = {"patient_id", "DFS_time", "DFS_event"}
    if not required.issubset(frame.columns):
        raise P5ValidationError("A modeling population lacks DFS fields")
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if frame["patient_id"].eq("").any() or frame["patient_id"].duplicated().any():
        raise P5ValidationError("A modeling population has invalid identifiers")
    frame["DFS_time"] = pd.to_numeric(frame["DFS_time"], errors="coerce")
    frame["DFS_event"] = pd.to_numeric(frame["DFS_event"], errors="coerce")
    if (frame["DFS_time"].isna().any() or
            not np.isfinite(frame["DFS_time"].to_numpy(dtype=float)).all() or
            not frame["DFS_time"].gt(0).all()):
        raise P5ValidationError("A modeling population has invalid DFS_time")
    if frame["DFS_event"].isna().any() or not frame["DFS_event"].isin([0, 1]).all():
        raise P5ValidationError("A modeling population has invalid DFS_event")
    frame["DFS_time"] = frame["DFS_time"].astype(float)
    frame["DFS_event"] = frame["DFS_event"].astype(int)
    if "technical_cohort" in frame.columns and \
            not frame["technical_cohort"].astype(str).str.strip().eq("A393").all():
        raise P5ValidationError("P5 accepts only the frozen A393 cohort")
    return frame.reset_index(drop=True)


def _normalise_split(split_frame):
    if not isinstance(split_frame, pd.DataFrame) or \
            list(split_frame.columns) != SPLIT_COLUMNS:
        raise P5ValidationError("W07 split schema mismatch")
    frame = split_frame.copy()
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if frame["patient_id"].eq("").any() or frame.isna().any().any():
        raise P5ValidationError("W07 split contains invalid values")
    for column in ("repeat", "fold", "seed"):
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise P5ValidationError("W07 split contains invalid %s" % column)
        numeric = values.to_numpy(dtype=float)
        if not np.equal(numeric, np.floor(numeric)).all():
            raise P5ValidationError("W07 split contains non-integer %s" % column)
        frame[column] = values.astype(int)
    frame["role"] = frame["role"].astype(str).str.strip()
    if not frame["role"].isin(["train", "validation"]).all():
        raise P5ValidationError("W07 split contains an unknown role")
    return frame[SPLIT_COLUMNS].copy()


def _canonical_split_hash(split_frame):
    return hashlib.sha256(
        split_frame[SPLIT_COLUMNS].to_csv(
            index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def verify_split_frame(split_frame, population, expected_hash=None):
    """Verify the immutable 10-repeat x 5-fold plan without rebuilding it."""
    population = _normalise_population(population)
    split_frame = _normalise_split(split_frame)
    if expected_hash is not None and \
            _canonical_split_hash(split_frame).lower() != str(expected_hash).lower():
        raise P5ValidationError("W07 canonical split hash mismatch")
    if len(split_frame) != len(population) * N_OUTER_REPEATS * N_OUTER_FOLDS:
        raise P5ValidationError("W07 split row count mismatch")
    population_ids = set(population["patient_id"])
    if set(split_frame["patient_id"]) != population_ids:
        raise P5ValidationError("W07 split population differs from W06 A population")
    event_map = population.set_index("patient_id")["DFS_event"]
    fold_summaries = []
    for repeat in range(1, N_OUTER_REPEATS + 1):
        repeated = split_frame[split_frame["repeat"] == repeat]
        if len(repeated) != len(population) * N_OUTER_FOLDS:
            raise P5ValidationError("W07 repeat coverage mismatch")
        if not repeated[repeated["role"] == "validation"].groupby(
                "patient_id").size().eq(1).all():
            raise P5ValidationError("W07 validation role is not one per patient")
        if not repeated[repeated["role"] == "train"].groupby(
                "patient_id").size().eq(N_OUTER_FOLDS - 1).all():
            raise P5ValidationError("W07 training role is not four per patient")
        expected_seed = BASE_SEED + repeat - 1
        seeds = set(repeated["seed"])
        if seeds != {expected_seed}:
            raise P5ValidationError("W07 seed derivation mismatch")
        for fold in range(1, N_OUTER_FOLDS + 1):
            group = repeated[repeated["fold"] == fold]
            train = set(group.loc[group["role"] == "train", "patient_id"])
            validation = set(group.loc[group["role"] == "validation", "patient_id"])
            if len(group) != len(population) or train & validation or \
                    train | validation != population_ids:
                raise P5ValidationError("W07 fold role coverage mismatch")
            train_events = int(event_map.loc[sorted(train)].sum())
            validation_events = int(event_map.loc[sorted(validation)].sum())
            if train_events < 1 or validation_events < 1:
                raise P5ValidationError("W07 outer event gate failed")
            fold_summaries.append({
                "repeat": repeat,
                "fold": fold,
                "train_n": len(train),
                "validation_n": len(validation),
                "train_events": train_events,
                "validation_events": validation_events,
            })
    if len(fold_summaries) != N_OUTER_REPEATS * N_OUTER_FOLDS:
        raise P5ValidationError("W07 does not enumerate exactly 50 folds")
    return fold_summaries


def _validate_candidate_freeze(candidate):
    if candidate.get("freeze_status") != "complete" or \
            candidate.get("B_data_read") is not False or \
            candidate.get("outcome_columns_read") is not False:
        raise P5ValidationError("W03 candidate freeze is not outcome-blind and complete")
    for block, expected in FROZEN_CANDIDATE_HASHES.items():
        if candidate.get("%s_candidate_hash" % block, "").lower() != expected:
            raise P5ValidationError("W03 %s candidate hash mismatch" % block)
        features = candidate.get("candidate_features", {}).get(block)
        if not isinstance(features, list) or _candidate_hash(features) != expected:
            raise P5ValidationError("W03 %s candidate feature identities mismatch" % block)


def verify_frozen_bindings(project_root=PROJECT_ROOT):
    """Verify W03/W04/W07/W07A/P4R before any A source is opened."""
    root = _normalise_root(project_root)
    hashes = OrderedDict()
    for label, (relative, expected) in _BINDING_FILES.items():
        path = os.path.join(root, *relative.split("/"))
        if _sha256_file(path).lower() != expected.lower():
            raise P5ValidationError("frozen binding hash mismatch: %s" % label)
        hashes[label] = expected.lower()

    if os.path.exists(os.path.join(root, *"prognosis_analysis/model_freeze_lock.json".split("/"))):
        raise P5ValidationError("model_freeze_lock.json exists; P5 is not authorized")

    protocol = _json(os.path.join(root, *"prognosis_analysis/modeling_protocol.json".split("/")))
    if protocol.get("status") != "frozen_before_first_DFS_read" or \
            protocol.get("access_gate", {}).get("B_unlock") is not False:
        raise P5ValidationError("W04 modeling protocol access gate is not frozen")
    candidate = _json(os.path.join(
        root, *"prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json".split("/")))
    _validate_candidate_freeze(candidate)
    w07 = _json(os.path.join(root, *"prognosis_analysis/configs/w07_outer_splits.json".split("/")))
    outer = w07.get("outer_cv", {})
    if (w07.get("stage"), w07.get("status"), outer.get("n_splits"),
            outer.get("n_repeats"), outer.get("minimum_events_per_train_fold"),
            outer.get("minimum_events_per_validation_fold")) != (
                "W07", "frozen", 5, 10, 1, 1):
        raise P5ValidationError("W07 outer design is not the frozen 50-fold plan")
    amendment = _json(os.path.join(
        root, *"prognosis_analysis/W07A_pre_W08_protocol_amendment.json".split("/")))
    decisions = amendment.get("decisions", {})
    roi = decisions.get("small_roi_rule", {})
    if roi.get("minimumROISize") != MINIMUM_ROI_SIZE:
        raise P5ValidationError("W07A minimumROISize is not 10")
    if amendment.get("access_boundary", {}).get("B_data_read") is not False or \
            amendment.get("access_boundary", {}).get("B_reader_invoked") is not False:
        raise P5ValidationError("W07A A/B access boundary is not closed")
    if amendment.get("preserved_frozen_state", {}).get(
            "W04_protocol_sha256", "").lower() != W04_PROTOCOL_SHA256 or \
            amendment.get("preserved_frozen_state", {}).get(
                "W07_outer_split_sha256", "").lower() != W07_OUTER_SPLIT_SHA256:
        raise P5ValidationError("W07A preserved binding hashes mismatch")
    p4r = _json(os.path.join(
        root, *"prognosis_analysis/W07A_pre_W08_provenance_reconciliation.json".split("/")))
    if p4r.get("schema", {}).get("status") != "approved_reconciliation" or \
            p4r.get("global_invariants", {}).get("B_data_read") is not False or \
            p4r.get("global_invariants", {}).get("formal_W08_started") is not False:
        raise P5ValidationError("P4R reconciliation is not approved for P5")
    return hashes


def _normalise_supervoxels(supervoxels):
    if not isinstance(supervoxels, pd.DataFrame):
        raise P5ValidationError("A technical supervoxel table must be a DataFrame")
    frame = supervoxels.copy()
    if "patient_id" not in frame.columns:
        if "影像号" in frame.columns:
            frame = frame.rename(columns={"影像号": "patient_id"})
        else:
            raise P5ValidationError("technical table lacks patient_id")
    required = {"patient_id", "sv_label", "n_tumor_voxels", "Mean"}
    if not required.issubset(frame.columns):
        raise P5ValidationError("technical table lacks frozen supervoxel fields")
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if frame["patient_id"].eq("").any() or frame["sv_label"].isna().any():
        raise P5ValidationError("technical table contains invalid identifiers or labels")
    if "reader" in frame.columns and not frame["reader"].astype(str).str.strip().eq("R1").all():
        raise P5ValidationError("technical table contains a non-R1 reader")
    frame["sv_label"] = pd.to_numeric(frame["sv_label"], errors="coerce")
    frame["n_tumor_voxels"] = pd.to_numeric(frame["n_tumor_voxels"], errors="coerce")
    frame["Mean"] = pd.to_numeric(frame["Mean"], errors="coerce")
    if frame[["sv_label", "n_tumor_voxels", "Mean"]].isna().any().any() or \
            not np.isfinite(frame[["sv_label", "n_tumor_voxels", "Mean"]]
                            .to_numpy(dtype=float)).all():
        raise P5ValidationError("technical table contains nonfinite support or mean")
    if not np.equal(frame["sv_label"].to_numpy(dtype=float),
                    np.floor(frame["sv_label"].to_numpy(dtype=float))).all() or \
            not np.equal(frame["n_tumor_voxels"].to_numpy(dtype=float),
                        np.floor(frame["n_tumor_voxels"].to_numpy(dtype=float))).all():
        raise P5ValidationError("technical table contains non-integer labels or support")
    frame["sv_label"] = frame["sv_label"].astype(int)
    frame["n_tumor_voxels"] = frame["n_tumor_voxels"].astype(int)
    if not frame["n_tumor_voxels"].gt(0).all():
        raise P5ValidationError("technical table contains nonpositive voxel support")
    if frame.duplicated(["patient_id", "sv_label"]).any():
        raise P5ValidationError("technical table contains duplicate case labels")
    return frame


def _normalise_availability(availability, population_ids, supervoxels):
    if availability is None:
        required = {"R_low_available", "R_high_available", "W_available"}
        if not required.issubset(supervoxels.columns):
            raise P5ValidationError("technical availability frame is required")
        frame = supervoxels[["patient_id"] + sorted(required)].copy()
        if frame.groupby("patient_id")[sorted(required)].nunique().gt(1).any().any():
            raise P5ValidationError("technical availability is inconsistent within a case")
        frame = frame.drop_duplicates("patient_id")
    else:
        frame = availability.copy()
        if "patient_id" not in frame.columns:
            if "影像号" in frame.columns:
                frame = frame.rename(columns={"影像号": "patient_id"})
            else:
                raise P5ValidationError("availability frame lacks patient_id")
    required = {"patient_id", "R_low_available", "R_high_available", "W_available"}
    if not required.issubset(frame.columns):
        raise P5ValidationError("availability frame lacks required A-only blocks")
    frame = frame[["patient_id", "R_low_available", "R_high_available",
                   "W_available"]].copy()
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if frame["patient_id"].eq("").any() or frame["patient_id"].duplicated().any():
        raise P5ValidationError("availability frame has invalid identifiers")
    if set(frame["patient_id"]) != set(population_ids):
        raise P5ValidationError("availability frame is not exactly the A population")
    for column in ("R_low_available", "R_high_available", "W_available"):
        if frame[column].isna().any():
            raise P5ValidationError("availability frame has missing %s" % column)
        converted = []
        for value in frame[column].tolist():
            if isinstance(value, (bool, np.bool_)):
                converted.append(bool(value))
            elif isinstance(value, (int, float, np.integer, np.floating)) and \
                    np.isfinite(float(value)) and float(value) in (0.0, 1.0):
                converted.append(bool(int(value)))
            else:
                raise P5ValidationError("availability frame has a non-binary %s" % column)
        frame[column] = converted
    return frame.set_index("patient_id")


def support_state(voxel_count):
    """Return the locked 0 / 1-9 / >=10 support state."""
    count = int(voxel_count)
    if count < 0:
        raise P5ValidationError("voxel support cannot be negative")
    if count == 0:
        return "structural_absence"
    if count < MINIMUM_ROI_SIZE:
        return "technical_small_roi"
    return "extractable"


def classify_support(voxel_count):
    """Compatibility alias used by synthetic regression tests."""
    return support_state(voxel_count)


def fit_training_only_centres(supervoxels, training_ids, seed):
    """Fit patient-balanced K=2 centres using outer-training cases only."""
    frame = _normalise_supervoxels(supervoxels)
    ids = sorted(set(str(value).strip() for value in training_ids))
    if not ids or any(not value for value in ids):
        raise P5ValidationError("outer training IDs are empty or invalid")
    selected = frame[frame["patient_id"].isin(ids)].copy()
    if set(selected["patient_id"]) != set(ids):
        raise P5ValidationError("outer training IDs lack technical representations")
    values = selected["Mean"].to_numpy(dtype=float)
    if np.unique(values).size < 2:
        raise P5ValidationError("training-only K=2 fit lacks two distinct values")
    counts = selected.groupby("patient_id")["sv_label"].transform("count")
    weights = 1.0 / counts.to_numpy(dtype=float)
    estimator = KMeans(n_clusters=2, random_state=int(seed), n_init=10)
    estimator.fit(values.reshape(-1, 1), sample_weight=weights)
    centres = tuple(sorted(float(value) for value in estimator.cluster_centers_.reshape(-1)))
    if not np.isfinite(np.asarray(centres)).all() or centres[0] >= centres[1]:
        raise P5ValidationError("training-only K=2 fit returned invalid centres")
    boundary = float((centres[0] + centres[1]) / 2.0)
    return {"centres": centres, "boundary": boundary,
            "training_id_hash": canonical_id_hash(ids),
            "training_patient_count": len(ids),
            "validation_ids_used_for_fit": False}


def generate_fold_masks(supervoxels, boundary, case_ids=None):
    """Generate fold-specific low/high support counts from the training boundary."""
    frame = _normalise_supervoxels(supervoxels)
    if case_ids is not None:
        ids = set(str(value).strip() for value in case_ids)
        frame = frame[frame["patient_id"].isin(ids)].copy()
    rows = []
    for identifier, group in frame.groupby("patient_id", sort=True):
        low = int(group.loc[group["Mean"] < float(boundary), "n_tumor_voxels"].sum())
        high = int(group.loc[group["Mean"] >= float(boundary), "n_tumor_voxels"].sum())
        total = int(group["n_tumor_voxels"].sum())
        if low + high != total:
            raise P5ValidationError("fold-specific habitat mask support does not reconcile")
        rows.append({
            "patient_id": identifier,
            "R_low_voxel_count": low,
            "R_high_voxel_count": high,
            "R_low_state": support_state(low),
            "R_high_state": support_state(high),
        })
    return pd.DataFrame(rows, columns=[
        "patient_id", "R_low_voxel_count", "R_high_voxel_count",
        "R_low_state", "R_high_state"]).set_index("patient_id")


def _required_blocks(population_name):
    return {
        "main": (),
        "W_available": (),
        "R_low": ("R_low",),
        "R_high": ("R_high",),
        "dual_radiomics": ("R_low", "R_high"),
    }[population_name]


def _model_state(support, population_name, identifier):
    blocks = _required_blocks(population_name)
    if not blocks:
        return "not_applicable"
    states = []
    for block in blocks:
        states.append(support.loc[identifier, "%s_state" % block])
    if "structural_absence" in states:
        return "structural_absence"
    if "technical_small_roi" in states:
        return "technical_small_roi"
    if all(state == "extractable" for state in states):
        return "extractable"
    raise P5ValidationError("invalid model-level support state")


def _eligible_ids(population_name, ids, support, availability):
    ids = set(ids)
    if population_name == "main":
        return ids
    if population_name == "W_available":
        return ids & set(availability.index[availability["W_available"]])
    if population_name == "R_low":
        return set(identifier for identifier in ids
                   if support.loc[identifier, "R_low_state"] == "extractable" and
                   bool(availability.loc[identifier, "R_low_available"]))
    if population_name == "R_high":
        return set(identifier for identifier in ids
                   if support.loc[identifier, "R_high_state"] == "extractable" and
                   bool(availability.loc[identifier, "R_high_available"]))
    if population_name == "dual_radiomics":
        return set(identifier for identifier in ids
                   if _model_state(support, population_name, identifier) == "extractable" and
                   bool(availability.loc[identifier, "R_low_available"]) and
                   bool(availability.loc[identifier, "R_high_available"]))
    raise P5ValidationError("unknown frozen population: %s" % population_name)


def _event_counts(population, ids):
    if not ids:
        return 0, 0
    values = population.set_index("patient_id").loc[sorted(ids), "DFS_event"]
    events = int(values.sum())
    return events, int(len(values) - events)


def _inner_feasibility(population, training_ids, seed, run_id, repeat, fold,
                       population_name):
    ids = sorted(set(training_ids))
    events, censors = _event_counts(population, ids)
    if events < N_INNER_FOLDS or censors < N_INNER_FOLDS:
        _fail(run_id, repeat, fold, population_name, "inner_5fold_event_gate",
              "both event and censor classes need at least five training cases")
    labels = population.set_index("patient_id").loc[ids, "DFS_event"].to_numpy(dtype=int)
    splitter = StratifiedKFold(n_splits=N_INNER_FOLDS, shuffle=True,
                               random_state=int(seed))
    for inner_train, inner_validation in splitter.split(np.zeros(len(ids)), labels):
        if int(labels[inner_train].sum()) < 1 or int(labels[inner_validation].sum()) < 1:
            _fail(run_id, repeat, fold, population_name, "inner_5fold_event_gate",
                  "inner training/validation event requirement failed")
        if int((labels[inner_train] == 0).sum()) < 1 or \
                int((labels[inner_validation] == 0).sum()) < 1:
            _fail(run_id, repeat, fold, population_name, "inner_5fold_censor_gate",
                  "inner training/validation censor requirement failed")
    return True


def _state_counts(support, ids, population_name):
    if not _required_blocks(population_name):
        return {"structural_absence": 0, "technical_small_roi": 0,
                "extractable": 0, "not_applicable": len(ids)}
    values = [_model_state(support, population_name, identifier) for identifier in ids]
    return {"structural_absence": values.count("structural_absence"),
            "technical_small_roi": values.count("technical_small_roi"),
            "extractable": values.count("extractable"),
            "not_applicable": 0}


def _build_pair_lookup():
    pairs = {}
    for comparator, radiomics, population in PAIR_DEFINITIONS:
        pairs.setdefault(comparator, []).append((radiomics, population))
        pairs.setdefault(radiomics, []).append((comparator, population))
    return pairs


def _assert_frozen_runtime_constants():
    if (MINIMUM_ROI_SIZE, N_OUTER_REPEATS, N_OUTER_FOLDS,
            N_INNER_FOLDS, BASE_SEED) != (10, 10, 5, 5, 12345):
        raise P5ValidationError("P5 runtime constants differ from the frozen protocol")


def run_technical_preflight(population, split_frame, supervoxels,
                           availability=None, binding_hashes=None,
                           expected_split_hash=None):
    """Run all 50 synthetic/in-memory technical fold units.

    This function never opens a file and never returns patient identifiers.
    Production callers must obtain ``binding_hashes`` from
    :func:`verify_frozen_bindings` first.
    """
    _assert_frozen_runtime_constants()
    if not isinstance(binding_hashes, dict):
        raise P5ValidationError("P5 requires a verified frozen binding manifest")
    required_bindings = set(_BINDING_FILES)
    if not required_bindings.issubset(binding_hashes):
        raise P5ValidationError("P5 binding manifest is incomplete")
    population = _normalise_population(population)
    supervoxels = _normalise_supervoxels(supervoxels)
    population_ids = set(population["patient_id"])
    technical_ids = set(supervoxels["patient_id"])
    if technical_ids != population_ids:
        raise P5ValidationError("technical A representation is not exactly the A population")
    availability = _normalise_availability(availability, population_ids, supervoxels)
    split_frame = _normalise_split(split_frame)
    fold_units = verify_split_frame(split_frame, population, expected_split_hash)
    population_index = population.set_index("patient_id")
    rows = []
    pair_lookup = _build_pair_lookup()
    for unit in fold_units:
        repeat = int(unit["repeat"])
        fold = int(unit["fold"])
        group = split_frame[(split_frame["repeat"] == repeat) &
                            (split_frame["fold"] == fold)]
        train_ids = set(group.loc[group["role"] == "train", "patient_id"])
        validation_ids = set(group.loc[group["role"] == "validation", "patient_id"])
        fit_seed = BASE_SEED + 2000 + 10 * (repeat - 1) + fold
        try:
            fitted = fit_training_only_centres(supervoxels, train_ids, fit_seed)
        except P5ValidationError:
            raise
        except Exception as exc:
            _fail("all_required_runs", repeat, fold, "main", "training_only_center_fit",
                  "K=2 training-only fit failed: %s" % type(exc).__name__)
        support = generate_fold_masks(supervoxels, fitted["boundary"], population_ids)
        training_hash = canonical_id_hash(train_ids)
        validation_hash = canonical_id_hash(validation_ids)
        for definition in RUN_DEFINITIONS:
            run_id = definition["run_id"]
            population_name = definition["population"]
            eligible = _eligible_ids(population_name, population_ids, support, availability)
            eligible_train = train_ids & eligible
            eligible_validation = validation_ids & eligible
            state_train = _state_counts(support, sorted(train_ids), population_name)
            state_validation = _state_counts(support, sorted(validation_ids), population_name)
            train_events, train_censors = _event_counts(population, eligible_train)
            validation_events, validation_censors = _event_counts(
                population, eligible_validation)
            if train_events < 1:
                _fail(run_id, repeat, fold, population_name, "outer_training_event_gate",
                      "eligible outer training population has no event")
            if validation_events < 1:
                _fail(run_id, repeat, fold, population_name, "outer_validation_event_gate",
                      "eligible outer validation population has no event")
            inner_seed = BASE_SEED + 1000 + 10 * (repeat - 1) + fold
            _inner_feasibility(population, eligible_train, inner_seed, run_id,
                               repeat, fold, population_name)
            comparator = None
            paired = True
            if run_id in pair_lookup:
                comparator = pair_lookup[run_id][0][0]
                comparator_population = pair_lookup[run_id][0][1]
                if comparator_population != population_name:
                    _fail(run_id, repeat, fold, population_name, "paired_population",
                          "paired comparator population definition differs")
                expected = _eligible_ids(comparator_population, population_ids,
                                         support, availability)
                paired = (eligible_train == (train_ids & expected) and
                           eligible_validation == (validation_ids & expected))
                if not paired:
                    _fail(run_id, repeat, fold, population_name, "paired_population",
                          "paired comparator does not share the same fold population")
            if run_id == "M3L_vs_M3H":
                comparator = "M3H_dual_radiomics"
                expected = _eligible_ids("dual_radiomics", population_ids,
                                         support, availability)
                if eligible_train != (train_ids & expected) or \
                        eligible_validation != (validation_ids & expected):
                    _fail(run_id, repeat, fold, population_name, "paired_population",
                          "dual M3L/M3H comparison population is not identical")
            centers_json = json.dumps([float(value) for value in fitted["centres"]],
                                      separators=(",", ":"))
            row = {
                "run_id": run_id,
                "repeat": repeat,
                "fold": fold,
                "population": population_name,
                "population_state": ("comparison_only" if definition.get("comparison_only")
                                      else population_name),
                "training_id_hash": training_hash,
                "validation_id_hash": validation_hash,
                "eligible_training_id_hash": canonical_id_hash(eligible_train),
                "eligible_validation_id_hash": canonical_id_hash(eligible_validation),
                "centers": centers_json,
                "boundary": float(fitted["boundary"]),
                "n_train_before_eligibility": len(train_ids),
                "n_validation_before_eligibility": len(validation_ids),
                "n_train_after_eligibility": len(eligible_train),
                "n_validation_after_eligibility": len(eligible_validation),
                "train_events": train_events,
                "train_censors": train_censors,
                "validation_events": validation_events,
                "validation_censors": validation_censors,
                "train_structural_absence": state_train["structural_absence"],
                "train_small_roi_1_9": state_train["technical_small_roi"],
                "train_extractable": state_train["extractable"],
                "validation_structural_absence": state_validation["structural_absence"],
                "validation_small_roi_1_9": state_validation["technical_small_roi"],
                "validation_extractable": state_validation["extractable"],
                "n_structural_absence": state_train["structural_absence"] +
                state_validation["structural_absence"],
                "n_small_roi_1_9": state_train["technical_small_roi"] +
                state_validation["technical_small_roi"],
                "n_extractable": state_train["extractable"] +
                state_validation["extractable"],
                "inner_5fold_feasible": True,
                "paired_comparator_run_id": comparator or "none",
                "paired_population_equal": bool(paired),
                "R_low_candidate_hash": FROZEN_CANDIDATE_HASHES["R_low"],
                "R_high_candidate_hash": FROZEN_CANDIDATE_HASHES["R_high"],
                "B_data_read": False,
                "B_reader_invoked": False,
                "B_source_opened": False,
                "B_statistics_generated": False,
                "performance_generated": False,
            }
            for label, value in binding_hashes.items():
                row["binding_%s_sha256" % label] = str(value).lower()
            rows.append(row)
    result = pd.DataFrame(rows)
    if len(fold_units) != 50 or result[["repeat", "fold"]].drop_duplicates().shape[0] != 50:
        raise P5ValidationError("P5 did not complete all 50 frozen fold units")
    if len(result) != 50 * len(RUN_DEFINITIONS):
        raise P5ValidationError("P5 run coverage is incomplete")
    if not bool(result["inner_5fold_feasible"].all()):
        raise P5ValidationError("P5 inner feasibility aggregate failed")
    return {
        "summary": {
            "stage": "P5",
            "status": "technical_only_complete",
            "outer_repeats": N_OUTER_REPEATS,
            "outer_folds": N_OUTER_FOLDS,
            "fold_units": len(fold_units),
            "run_rows": len(result),
            "required_runs": len(RUN_DEFINITIONS),
            "all_required_runs_estimable": True,
            "all_paired_populations_equal": bool(result["paired_population_equal"].all()),
            "minimumROISize": MINIMUM_ROI_SIZE,
            "R_low_candidate_hash": FROZEN_CANDIDATE_HASHES["R_low"],
            "R_high_candidate_hash": FROZEN_CANDIDATE_HASHES["R_high"],
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
            "performance_generated": False,
            "patient_level_outputs_written": False,
            "aggregate_only": True,
            "binding_hashes": dict(binding_hashes),
        },
        "fold_feasibility": result,
        "release_gate": {
            "stage": "G3",
            "status": "PASS",
            "P5_technical_preflight": "PASS",
            "frozen_fold_units": 50,
            "completed_fold_units": 50,
            "all_required_runs_estimable": True,
            "all_paired_populations_equal": bool(result["paired_population_equal"].all()),
            "bindings_verified": True,
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
            "performance_generated": False,
            "patient_level_outputs_written": False,
        },
    }


def _read_authorized_a(path, allowed_ids=None, allow_full=False, usecols=None,
                       dtype=None):
    """Call the existing A-only streaming reader; no alternate callback is accepted."""
    feature_scripts = os.path.join(PROJECT_ROOT, "feature_extract", "scripts")
    if feature_scripts not in sys.path:
        sys.path.insert(0, feature_scripts)
    from data_split_guard import read_technical_A
    kwargs = {"allow_full": bool(allow_full)}
    if allowed_ids is not None:
        kwargs["allowed_ids"] = set(str(value).strip() for value in allowed_ids)
    if usecols is not None:
        kwargs["usecols"] = usecols
    if dtype is not None:
        kwargs["dtype"] = dtype
    return read_technical_A(path, **kwargs)


def _available_from_w03(path, allowed_ids):
    table = _read_authorized_a(
        path, allowed_ids=allowed_ids,
        usecols=["影像号", "reader", "status"],
        dtype={"影像号": str})
    table["影像号"] = table["影像号"].astype(str).str.strip()
    if "reader" in table.columns:
        table = table[table["reader"].astype(str).str.strip().eq("R1")]
    if table["影像号"].duplicated().any():
        raise P5ValidationError("W03 A-only availability has duplicate R1 identifiers")
    return set(table.loc[table["status"].astype(str).str.strip().eq("extractable"), "影像号"])


def _available_from_w_features(paths, allowed_ids):
    available = None
    for path in paths:
        table = _read_authorized_a(
            path, allowed_ids=allowed_ids,
            usecols=["影像号", "读者"], dtype={"影像号": str})
        table = table[table["读者"].astype(str).str.strip().eq("R1")]
        ids = set(table["影像号"].astype(str).str.strip())
        available = ids if available is None else available & ids
    return available or set()


def load_authorized_a_inputs(project_root=PROJECT_ROOT):
    """Load only frozen A technical/modeling inputs after binding verification."""
    root = _normalise_root(project_root)
    population_path = os.path.join(root, *"prognosis_analysis/output/A_modeling/A_modeling_population.csv".split("/"))
    split_path = os.path.join(root, *"prognosis_analysis/output/outer_splits_A.csv".split("/"))
    supervoxel_path = os.path.join(
        root, *"habitat_analysis/output/local_global_diagnostic_A_post_slic_fix/supervoxel_mean_A.csv".split("/"))
    w03_low = os.path.join(root, *"prognosis_analysis/output/w03_habitat_radiomics_A/R1_R_low_features.csv".split("/"))
    w03_high = os.path.join(root, *"prognosis_analysis/output/w03_habitat_radiomics_A/R1_R_high_features.csv".split("/"))
    w_features = tuple(os.path.join(root, *path.split("/")) for path in (
        "feature_extract/output/features_v2/muscle_f0.25/features_original.csv",
        "feature_extract/output/features_v2/muscle_f0.25/features_wavelet.csv",
        "feature_extract/output/features_v2/muscle_f0.25/features_log.csv"))
    population = _read_authorized_a(
        population_path, allow_full=True, usecols=[
            "影像号", "technical_cohort", "DFS_time", "DFS_event", "modeling_eligible"],
        dtype={"影像号": str})
    population = _normalise_population(population)
    ids = set(population["patient_id"])
    split_frame = pd.read_csv(split_path, dtype={"patient_id": str})
    supervoxels = _read_authorized_a(
        supervoxel_path, allowed_ids=ids,
        usecols=["影像号", "reader", "sv_label", "n_tumor_voxels", "Mean"],
        dtype={"影像号": str})
    supervoxels = _normalise_supervoxels(supervoxels)
    low_available = _available_from_w03(w03_low, ids)
    high_available = _available_from_w03(w03_high, ids)
    whole_tumour_available = _available_from_w_features(w_features, ids)
    availability = pd.DataFrame({
        "patient_id": sorted(ids),
        "R_low_available": [identifier in low_available for identifier in sorted(ids)],
        "R_high_available": [identifier in high_available for identifier in sorted(ids)],
        "W_available": [identifier in whole_tumour_available
                         for identifier in sorted(ids)],
    })
    return population, split_frame, supervoxels, availability


def _atomic_json(path, payload):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def write_outputs(result, output_root):
    """Write only aggregate P5 schemas; never write patient-level rows."""
    output_root = os.path.abspath(os.fspath(output_root))
    os.makedirs(output_root, exist_ok=True)
    names = ("P5_technical_preflight_summary.json", "P5_fold_feasibility.csv",
             "P5_release_gate.json")
    existing = [name for name in names if os.path.exists(os.path.join(output_root, name))]
    if existing:
        raise P5ValidationError("P5 output already exists: %s" % ",".join(existing))
    frame = result["fold_feasibility"].copy()
    if any(column == "patient_id" or "patient_id" in column for column in frame.columns):
        raise P5ValidationError("P5 aggregate output contains a patient-level field")
    frame.to_csv(os.path.join(output_root, names[1]), index=False, encoding="utf-8-sig")
    _atomic_json(os.path.join(output_root, names[0]), result["summary"])
    _atomic_json(os.path.join(output_root, names[2]), result["release_gate"])
    return [os.path.join(output_root, name) for name in names]


def run_production(output_root=DEFAULT_OUTPUT, project_root=PROJECT_ROOT):
    """Run the local protected A-only P5 entry point after all binding gates."""
    binding_hashes = verify_frozen_bindings(project_root)
    population, split_frame, supervoxels, availability = load_authorized_a_inputs(project_root)
    expected_split_hash = binding_hashes["W07_outer_split_artifact"]
    result = run_technical_preflight(
        population, split_frame, supervoxels, availability,
        binding_hashes=binding_hashes, expected_split_hash=expected_split_hash)
    write_outputs(result, output_root)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="P5 A-only 50-fold technical preflight; no formal model execution")
    parser.add_argument("--output", default=DEFAULT_OUTPUT,
                        help="local protected aggregate output directory")
    args = parser.parse_args(argv)
    result = run_production(args.output)
    print(json.dumps(result["release_gate"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
