"""Local W08 A-only execution adapter.

This module is the controlled local bridge between the frozen W08 library and
the already-authorized A technical artifacts.  It never calls a B reader and
does not create the second-stage model-freeze lock.

The provider keeps the W08 library's fold boundary immutable.  SLIC labels are
computed once per A case from the frozen preprocessing configuration and are
cached locally; each outer-training fold fits its own patient-balanced K=2
centres, then reassigns those labels and extracts fold-specific global and
habitat radiomics features for both the training and held-out patients.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import operator
import os
import platform
import shutil
import subprocess
import sys
import time
import uuid

import numpy as np
import pandas as pd
from scipy import ndimage
from sklearn.cluster import KMeans

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)
FEATURE_SCRIPT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_ROOT)), "feature_extract", "scripts")
HABITAT_SCRIPT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_ROOT)), "habitat_analysis", "scripts")
for _script_root in (FEATURE_SCRIPT_ROOT, HABITAT_SCRIPT_ROOT):
    if _script_root not in sys.path:
        sys.path.insert(0, _script_root)

import w02_habitat_radiomics as w02  # noqa: E402
import w07_outer_splits as w07  # noqa: E402
import w08_nested_cv as w08  # noqa: E402
import provenance_reconciliation as provenance  # noqa: E402
import w08_technical_preflight_a as technical_preflight  # noqa: E402
from data_split_guard import read_technical_A  # noqa: E402
import technical_dry_run_A as technical  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
OUTPUT_ROOT = os.path.join(ROOT, "output", "w08_formal_A")
WORK_ROOT = os.path.join(OUTPUT_ROOT, "work")
SLIC_CACHE_ROOT = os.path.join(WORK_ROOT, "slic_cache")

MINIMUM_ROI_SIZE = 10
# PyRadiomics 3.0.1 treats its minimumROISize as a strict lower bound
# (``roiSize <= minimumROISize``).  W08 keeps the public P3B threshold at 10;
# this backend-only value disables the duplicated, off-by-one check after the
# provider has already classified the mask using the frozen contract.
_PYRADIOMICS_COMPATIBILITY_MINIMUM_ROI_SIZE = None
RADIOMICS_STATE_STRUCTURALLY_ABSENT = "structurally_absent"
RADIOMICS_STATE_TECHNICALLY_UNEXTRACTABLE_SMALL_ROI = \
    "technically_unextractable_small_ROI"
RADIOMICS_STATE_EXTRACTABLE = "radiomics_extractable"
RADIOMICS_SUPPORT_COLUMNS = (
    "R_low_voxel_count", "R_high_voxel_count", "R_low_state", "R_high_state",
    "R_low_structurally_defined", "R_high_structurally_defined",
    "R_low_technically_extractable", "R_high_technically_extractable",
)

W06_POPULATION = os.path.join(
    ROOT, "output", "A_modeling", "A_modeling_population.csv")
W03_LOW = os.path.join(
    ROOT, "output", "w03_habitat_radiomics_A", "R1_R_low_features.csv")
W03_HIGH = os.path.join(
    ROOT, "output", "w03_habitat_radiomics_A", "R1_R_high_features.csv")
SV_TABLE = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "output",
    "local_global_diagnostic_A_post_slic_fix", "supervoxel_mean_A.csv")
HABITAT_CONFIG = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "configs",
    "main_cross_case_kmeans_k2_4mm.json")
CLINICAL_A = os.path.join(
    ROOT, "output", "modeling_v2", "dataset_primary_raw_A.csv")
FEATURE_ROOT = os.path.join(
    PROJECT_ROOT, "feature_extract", "output", "features_v2", "muscle_f0.25")
W_BATCHES = (
    ("original", "features_original.csv",
     ("影像号", "读者", "split", "normalization", "f", "binWidth")),
    ("wavelet", "features_wavelet.csv",
     ("影像号", "读者", "split", "normalization", "f")),
    ("log", "features_log.csv",
     ("影像号", "读者", "split", "normalization", "f")),
)

W08_REQUIRED_OUTPUT_NAMES = (
    "predictions.csv", "fold_results.csv", "selection_results.csv",
    "audit.json", "run_metadata.json",
)
W08_OUTPUT_MANIFEST_NAME = "formal_output_manifest.json"
W08_FINAL_OUTPUT_NAMES = W08_REQUIRED_OUTPUT_NAMES + (W08_OUTPUT_MANIFEST_NAME,)
W08_RELEASE_GATE_NAME = "release_gate.json"
W08_RUN_STATE_NAME = "run_state.json"
W08_ATTEMPT_STATE_NAME = "attempt_state.json"
W08_P5_LEGACY_OUTPUT_RELATIVE = \
    "prognosis_analysis/output/p5_technical_preflight_A"
W08_P5_CURRENT_OUTPUT_RELATIVE = \
    "prognosis_analysis/output/p5_technical_preflight_A_G3R"
B_ACCESS_FLAGS = (
    "B_data_read", "B_reader_invoked", "B_source_opened",
    "B_statistics_generated",
)

PYRADIOMICS_VERSION = "3.0.1"
COMPATIBILITY_REASON = (
    "PyRadiomics 3.0.1 strict <= semantics and precheck count>=10")
PRECHECK_COUNT_THRESHOLD = ">=10"


class W08ReleaseGateError(RuntimeError):
    """Raised when formal W08 is not authorized by the release gate."""

    def __init__(self, result):
        self.result = result
        failures = result.get("failure_reasons", [])
        message = "W08 formal release gate failed"
        if failures:
            message += ": " + "; ".join(failures)
        super(W08ReleaseGateError, self).__init__(message)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _atomic_csv(frame, path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _compatibility_provenance():
    """Return the frozen public/backend ROI compatibility provenance."""
    return {
        "protocol_minimumROISize": MINIMUM_ROI_SIZE,
        "scientific_minimumROISize": MINIMUM_ROI_SIZE,
        "effective_backend_minimum_size":
            _PYRADIOMICS_COMPATIBILITY_MINIMUM_ROI_SIZE,
        "compatibility_reason": COMPATIBILITY_REASON,
        "precheck_count_threshold": PRECHECK_COUNT_THRESHOLD,
        "pyradiomics_version": PYRADIOMICS_VERSION,
    }


def _new_attempt_id():
    """Create a unique, path-safe identifier for one formal W08 attempt."""
    return "attempt_%d_%s" % (int(time.time() * 1000000),
                              uuid.uuid4().hex[:12])


def _canonical_output_paths(output_root):
    return dict((name, os.path.join(output_root, name))
                for name in W08_FINAL_OUTPUT_NAMES)


def _staging_dirs(output_root):
    attempts_root = os.path.join(output_root, "attempts")
    if not os.path.isdir(attempts_root):
        return []
    return sorted(
        os.path.join(attempts_root, name)
        for name in os.listdir(attempts_root)
        if name.endswith(".staging") and
        os.path.isdir(os.path.join(attempts_root, name)))


def _begin_attempt(output_root, code_commit, started_epoch):
    """Create an exclusive staging directory before any W08 model work."""
    output_root = os.path.abspath(os.fspath(output_root))
    os.makedirs(output_root, exist_ok=True)
    canonical = _canonical_output_paths(output_root)
    existing = [name for name, path in canonical.items()
                if os.path.exists(path)]
    if existing:
        raise RuntimeError(
            "canonical W08 outputs already exist; refusing rerun: %s" %
            ",".join(existing))
    stale_staging = _staging_dirs(output_root)
    if stale_staging:
        raise RuntimeError(
            "stale W08 staging attempt blocks rerun: %s" %
            ",".join(os.path.basename(path) for path in stale_staging))

    attempts_root = os.path.join(output_root, "attempts")
    os.makedirs(attempts_root, exist_ok=True)
    while True:
        attempt_id = _new_attempt_id()
        staging_root = os.path.join(attempts_root, attempt_id + ".staging")
        try:
            os.makedirs(staging_root)
            break
        except OSError:
            if os.path.exists(staging_root):
                continue
            raise
    _atomic_json(os.path.join(staging_root, W08_ATTEMPT_STATE_NAME), {
        "stage": "W08",
        "status": "staging",
        "attempt_id": attempt_id,
        "code_commit_at_attempt": code_commit,
        "started_at_epoch": started_epoch,
        "final_outputs_generated": False,
    })
    return {
        "attempt_id": attempt_id,
        "staging_root": staging_root,
        "output_root": output_root,
        "code_commit": code_commit,
        "started_at_epoch": started_epoch,
        "status": "staging",
    }


def _validate_manifest_hex(value, label):
    if not isinstance(value, str) or len(value) != 64 or \
            any(char not in "0123456789abcdefABCDEF" for char in value):
        raise RuntimeError("%s is not a SHA-256 digest" % label)


def _validate_formal_output_manifest(path, expected_attempt_id=None,
                                     expected_code_commit=None):
    """Validate the W08 commit marker and every promoted output digest."""
    path = os.path.abspath(os.fspath(path))
    manifest = _read_json_path(path, "formal W08 output manifest")
    if manifest.get("schema") != "w08_formal_output_manifest" or \
            manifest.get("schema_version") != "1.0":
        raise RuntimeError("formal W08 output manifest schema is invalid")
    if manifest.get("stage") != "W08" or \
            manifest.get("status") != "complete":
        raise RuntimeError("formal W08 output manifest is not complete")
    attempt_id = manifest.get("attempt_id")
    if not _nonempty_text(attempt_id) or "/" in attempt_id or "\\" in attempt_id:
        raise RuntimeError("formal W08 output manifest has an invalid attempt_id")
    if expected_attempt_id is not None and attempt_id != expected_attempt_id:
        raise RuntimeError("formal W08 output manifest attempt_id mismatch")
    code_commit = manifest.get("code_commit")
    if not isinstance(code_commit, str) or len(code_commit) != 40 or \
            any(char not in "0123456789abcdefABCDEF" for char in code_commit):
        raise RuntimeError("formal W08 output manifest has an invalid code commit")
    if expected_code_commit is not None and \
            code_commit.lower() != str(expected_code_commit).lower():
        raise RuntimeError("formal W08 output manifest code commit mismatch")

    compatibility = manifest.get("compatibility_provenance")
    expected_compatibility = _compatibility_provenance()
    if compatibility != expected_compatibility:
        raise RuntimeError("formal W08 compatibility provenance mismatch")
    protocol = manifest.get("protocol")
    if not isinstance(protocol, dict) or \
            protocol.get("minimumROISize") != MINIMUM_ROI_SIZE or \
            protocol.get("W04_protocol_sha256") != w08.W04_PROTOCOL_SHA256 or \
            protocol.get("W07_outer_split_sha256") != w08.W07_OUTER_SPLIT_SHA256:
        raise RuntimeError("formal W08 output protocol binding is invalid")

    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict) or \
            set(outputs) != set(W08_REQUIRED_OUTPUT_NAMES):
        raise RuntimeError("formal W08 output manifest list is incomplete")
    output_root = os.path.dirname(path)
    for name in W08_REQUIRED_OUTPUT_NAMES:
        entry = outputs.get(name)
        if not isinstance(entry, dict) or entry.get("path") != name:
            raise RuntimeError("formal W08 output manifest entry is invalid: %s" % name)
        digest = entry.get("sha256")
        _validate_manifest_hex(digest, "output %s" % name)
        output_path = os.path.join(output_root, name)
        if not os.path.isfile(output_path):
            raise RuntimeError("formal W08 output is missing: %s" % name)
        if _sha256(output_path).lower() != digest.lower():
            raise RuntimeError("formal W08 output SHA-256 mismatch: %s" % name)
        if entry.get("size_bytes") != os.path.getsize(output_path):
            raise RuntimeError("formal W08 output size mismatch: %s" % name)

    audit = _read_json_path(os.path.join(output_root, "audit.json"),
                            "formal W08 audit")
    metadata = _read_json_path(os.path.join(output_root, "run_metadata.json"),
                               "formal W08 metadata")
    for label, payload in (("audit", audit), ("metadata", metadata)):
        if payload.get("stage") != "W08" or \
                payload.get("status") != "formal_complete" or \
                payload.get("attempt_id") != attempt_id or \
                payload.get("code_commit") != code_commit:
            raise RuntimeError("formal W08 %s is not bound to the manifest" % label)
    if audit.get("compatibility_provenance") != expected_compatibility or \
            metadata.get("compatibility_provenance") != expected_compatibility:
        raise RuntimeError("formal W08 compatibility audit is incomplete")
    return manifest


def _write_attempt_failure(context, project_root, stage, exception):
    """Close a staging attempt as an explicit failed archive."""
    if not context or context.get("status") in ("failed", "promoted"):
        return
    staging_root = context.get("staging_root")
    if not staging_root or not os.path.isdir(staging_root):
        context["status"] = "failed"
        return
    output_root = context["output_root"]
    failure = {
        "attempt_id": context["attempt_id"],
        "stage": "W08",
        "status": "failed",
        "failure_stage": stage,
        "exception_summary": _safe_exception_text(
            exception, project_root, output_root),
        "code_commit_at_attempt": context.get("code_commit"),
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": False,
    }
    failed_state = {
        "stage": "W08",
        "status": "failed",
        "formal_run": True,
        "failure_stage": stage,
        "exception_class": exception.__class__.__name__,
        "failure_reason": _safe_exception_text(
            exception, project_root, output_root),
        "code_commit": context.get("code_commit"),
        "code_commit_at_attempt": context.get("code_commit"),
        "attempt_id": context["attempt_id"],
        "started_at_epoch": context.get("started_at_epoch"),
        "ended_at_epoch": time.time(),
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": False,
    }
    _atomic_json(os.path.join(staging_root, "failure_audit.json"), failure)
    _atomic_json(os.path.join(staging_root, W08_RUN_STATE_NAME), failed_state)
    _atomic_json(os.path.join(staging_root, W08_ATTEMPT_STATE_NAME), {
        "stage": "W08",
        "status": "failed",
        "attempt_id": context["attempt_id"],
        "code_commit_at_attempt": context.get("code_commit"),
        "failure_stage": stage,
        "final_outputs_generated": False,
    })
    failed_root = os.path.join(
        os.path.dirname(staging_root), context["attempt_id"] + "_failed")
    if os.path.exists(failed_root):
        raise RuntimeError("failed W08 attempt archive already exists")
    os.replace(staging_root, failed_root)
    context["status"] = "failed"
    context["failed_root"] = failed_root


def _promote_staged_outputs(context):
    """Promote validated files with the manifest moved last as commit marker."""
    staging_root = context["staging_root"]
    output_root = context["output_root"]
    manifest_path = os.path.join(staging_root, W08_OUTPUT_MANIFEST_NAME)
    _validate_formal_output_manifest(
        manifest_path, expected_attempt_id=context["attempt_id"],
        expected_code_commit=context.get("code_commit"))
    canonical = _canonical_output_paths(output_root)
    existing = [name for name, path in canonical.items()
                if os.path.exists(path)]
    if existing:
        raise RuntimeError(
            "canonical W08 outputs appeared during promotion: %s" %
            ",".join(existing))
    promoted = []
    try:
        for name in W08_REQUIRED_OUTPUT_NAMES + (W08_OUTPUT_MANIFEST_NAME,):
            os.replace(os.path.join(staging_root, name), canonical[name])
            promoted.append(name)
        _validate_formal_output_manifest(
            canonical[W08_OUTPUT_MANIFEST_NAME],
            expected_attempt_id=context["attempt_id"],
            expected_code_commit=context.get("code_commit"))
    except Exception:
        for name in promoted:
            try:
                os.remove(canonical[name])
            except OSError:
                pass
        raise
    context["status"] = "promoted"
    context["manifest"] = canonical[W08_OUTPUT_MANIFEST_NAME]
    try:
        shutil.rmtree(staging_root)
    except OSError:
        # The manifest is already validated and is the completion marker;
        # a cleanup failure must not turn a committed output into a failure.
        pass


def _project_path(project_root, relative_path):
    return os.path.join(project_root, *relative_path.split("/"))


def _read_json_path(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RuntimeError("%s cannot be read: %s" % (label, exc))
    if not isinstance(value, dict):
        raise RuntimeError("%s must contain a JSON object" % label)
    return value


def _git_head(project_root):
    try:
        value = subprocess.check_output(
            ["git", "-C", project_root, "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("current Git commit cannot be resolved: %s" % exc)
    commit = value.decode("ascii", "replace").strip().lower()
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise RuntimeError("current Git commit is not a 40-hex object ID")
    return commit


def _git_commit_resolves(project_root, commit):
    if not isinstance(commit, str) or len(commit) != 40:
        return False
    try:
        resolved = subprocess.check_output(
            ["git", "-C", project_root, "rev-parse", "--verify",
             commit + "^{commit}"],
            stderr=subprocess.STDOUT).decode("ascii", "replace").strip().lower()
    except (OSError, subprocess.CalledProcessError):
        return False
    return resolved == commit.lower()


def _safe_exception_text(exc, project_root=None, output_root=None):
    text = str(exc).replace("\r", " ").replace("\n", " ").strip()
    for path, replacement in ((project_root, "<project_root>"),
                              (output_root, "<output_root>")):
        if path:
            text = text.replace(os.path.abspath(path), replacement)
    return text[:1000]


def _environment_fingerprint(project_root):
    fingerprint_path = _project_path(
        project_root, "prognosis_analysis/G2_environment_fingerprint.json")
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "executable_name": os.path.basename(sys.executable),
        "platform": platform.system(),
        "G2_environment_fingerprint_sha256": (
            _sha256(fingerprint_path) if os.path.isfile(fingerprint_path) else None),
    }


def _validate_p4r_reconciliation(project_root):
    return provenance.validate_manifest(root=project_root)


def _validate_frozen_bindings(project_root):
    return technical_preflight.verify_frozen_bindings(project_root)


def _validate_w08_configuration():
    config = w08.load_config()
    w08._validate_config(config)
    return config


def _validate_execution_status(project_root):
    return provenance.validate_execution_status(root=project_root)


def _validate_technical_freeze(project_root):
    path = _project_path(project_root, "habitat_analysis/freeze_lock.json")
    payload = _read_json_path(path, "technical freeze lock")
    expected = {
        "freeze_schema_version": "1.0",
        "habitat_technical_freeze": True,
        "A_outcome_unlock": True,
        "B_unlock": False,
        "bootstrap_mode": "formal",
        "bootstrap_requested": 1000,
        "bootstrap_completed": 1000,
        "bootstrap_completion_status": "complete",
        "bootstrap_operational_pass": 1,
        "formal_eligible": 1,
        "outcome_columns_read": False,
        "B_data_read": False,
        "eligibility_threshold_fraction": 0.001,
        "eligibility_threshold_role": "minimum_imaging_presence",
        "threshold_selection_performed": False,
        "threshold_audit_conclusion": "NEUTRAL_WITH_TECHNICAL_CAUTION",
    }
    mismatches = [key for key, value in expected.items()
                  if type(payload.get(key)) is not type(value) or
                  payload.get(key) != value]
    if mismatches:
        raise RuntimeError(
            "technical freeze fields changed: %s" % ",".join(mismatches))
    if payload.get("git_commit") != provenance.TECHNICAL_FREEZE_GIT_COMMIT:
        raise RuntimeError("technical freeze Git binding changed")
    if _sha256(path).lower() != provenance.TECHNICAL_FREEZE_SHA256:
        raise RuntimeError("technical freeze SHA-256 changed")
    return payload


def _validate_w05_access_boundary(project_root):
    protocol_path = _project_path(
        project_root, "prognosis_analysis/modeling_protocol.json")
    protocol = _read_json_path(protocol_path, "W04 modeling protocol")
    if protocol.get("status") != "frozen_before_first_DFS_read":
        raise RuntimeError("W05 access boundary requires the frozen W04 protocol")
    access_gate = protocol.get("access_gate")
    if not isinstance(access_gate, dict):
        raise RuntimeError("W05 access boundary is missing")
    if access_gate.get("B_unlock") is not False:
        raise RuntimeError("W05 access boundary does not keep B locked")
    if access_gate.get("B_access_authority") != \
            "prognosis_analysis/model_freeze_lock.json only after W13 strict validation":
        raise RuntimeError("W05 B access authority changed")
    lock = access_gate.get("model_freeze_lock", {})
    if not isinstance(lock, dict) or lock.get("exists_at_W04_freeze") is not False or \
            lock.get("status_at_W04_freeze") != "not_generated":
        raise RuntimeError("W05 model-freeze boundary changed")
    first_stage = access_gate.get("A_only_gate_before_first_DFS_read", {})
    required = first_stage.get("required_in_order", []) if isinstance(first_stage, dict) else []
    if "W05 A-only reader and centralized split resolver pass" not in required:
        raise RuntimeError("W05 A-only reader requirement is not registered")
    if first_stage.get("first_DFS_read_stage") != "W06" or \
            first_stage.get("missing_requirement_action") != \
            "hard_fail_and_do_not_read_DFS":
        raise RuntimeError("W05 first-outcome-read boundary changed")
    reader_path = _project_path(
        project_root, "feature_extract/scripts/data_split_guard.py")
    if not os.path.isfile(reader_path):
        raise RuntimeError("W05 centralized access reader is absent")
    with open(reader_path, "r", encoding="utf-8") as handle:
        reader_source = handle.read()
    required_markers = (
        "def read_technical_A", "def read_A_outcomes",
        "def read_B_validation", "def require_a_outcome_unlock",
        "def require_b_unlock",
    )
    missing = [marker for marker in required_markers
               if marker not in reader_source]
    if missing:
        raise RuntimeError("W05 reader contract is incomplete: %s" % ",".join(missing))
    return {"status": "PASS", "reader": "data_split_guard"}


def _extract_certificate_code_commit(certificate):
    candidates = (
        ("code_commit", certificate.get("code_commit")),
        ("code_commit_at_release", certificate.get("code_commit_at_release")),
        ("binding.code_commit",
         certificate.get("binding", {}).get("code_commit")
         if isinstance(certificate.get("binding"), dict) else None),
        ("release_binding.code_commit",
         certificate.get("release_binding", {}).get("code_commit")
         if isinstance(certificate.get("release_binding"), dict) else None),
        ("verification.code_commit",
         certificate.get("verification", {}).get("code_commit")
         if isinstance(certificate.get("verification"), dict) else None),
    )
    present = [(label, value) for label, value in candidates if value is not None]
    if not present:
        raise RuntimeError("G3 release certificate has no code-commit binding")
    distinct = {str(value).lower() for _, value in present}
    if len(distinct) != 1:
        raise RuntimeError("G3 release certificate has conflicting code bindings")
    label, value = present[0]
    if not isinstance(value, str) or len(value) != 40 or \
            any(char not in "0123456789abcdefABCDEF" for char in value):
        raise RuntimeError("G3 release certificate %s is not a Git commit" % label)
    return value.lower()


def _p5_certificate_root(project_root):
    """Prefer the append-only current-code successor over the legacy P5 set."""
    candidates = (W08_P5_CURRENT_OUTPUT_RELATIVE,
                  W08_P5_LEGACY_OUTPUT_RELATIVE)
    for relative in candidates:
        root = _project_path(project_root, relative)
        if all(os.path.isfile(os.path.join(root, name)) for name in (
                "P5_release_gate.json", "P5_technical_preflight_summary.json")):
            return root
    return _project_path(project_root, W08_P5_LEGACY_OUTPUT_RELATIVE)


def _validate_g3_certificate(project_root, code_commit, binding_hashes):
    certificate_root = _p5_certificate_root(project_root)
    certificate_path = os.path.join(certificate_root, "P5_release_gate.json")
    summary_path = os.path.join(
        certificate_root, "P5_technical_preflight_summary.json")
    certificate = _read_json_path(certificate_path, "G3 release certificate")
    summary = _read_json_path(summary_path, "G3 technical summary")
    if certificate.get("stage") != "G3" or certificate.get("status") != "PASS":
        raise RuntimeError("G3 release certificate is not PASS")
    if certificate.get("P5_technical_preflight") != "PASS":
        raise RuntimeError("G3 technical preflight certificate is not PASS")
    for key in ("all_required_runs_estimable", "all_paired_populations_equal"):
        if certificate.get(key) is not True:
            raise RuntimeError("G3 certificate %s is not true" % key)
    for key in B_ACCESS_FLAGS + ("performance_generated", "patient_level_outputs_written"):
        if certificate.get(key) is not False:
            raise RuntimeError("G3 certificate %s is not false" % key)
    if summary.get("stage") != "P5" or \
            summary.get("status") != "technical_only_complete":
        raise RuntimeError("G3 technical summary is not complete")
    if summary.get("fold_units") != 50 or summary.get("run_rows") != 850 or \
            summary.get("required_runs") != 17 or summary.get("minimumROISize") != 10:
        raise RuntimeError("G3 technical summary coverage is incomplete")
    for key in B_ACCESS_FLAGS + ("performance_generated", "patient_level_outputs_written"):
        if summary.get(key) is not False:
            raise RuntimeError("G3 technical summary %s is not false" % key)
    if not isinstance(binding_hashes, dict) or \
            summary.get("binding_hashes") != dict(binding_hashes):
        raise RuntimeError("G3 binding manifest differs from frozen bindings")
    certificate_commit = _extract_certificate_code_commit(certificate)
    if certificate_commit != code_commit:
        raise RuntimeError(
            "G3 release certificate is bound to a stale code commit")
    if not _git_commit_resolves(project_root, certificate_commit):
        raise RuntimeError("G3 release certificate code commit does not resolve")
    if os.path.basename(os.path.normpath(certificate_root)) == \
            "p5_technical_preflight_A_G3R":
        if not isinstance(certificate.get("certificate_generated_at_utc"), str) or \
                not certificate.get("certificate_generated_at_utc").strip():
            raise RuntimeError("G3R release certificate lacks generation time")
        compatibility = certificate.get("compatibility_provenance")
        if not isinstance(compatibility, dict) or \
                compatibility.get("protocol_minimumROISize") != 10 or \
                compatibility.get("scientific_minimumROISize") != 10 or \
                compatibility.get("effective_backend_minimum_size") is not None or \
                compatibility.get("precheck_count_threshold") != ">=10" or \
                compatibility.get("pyradiomics_version") != PYRADIOMICS_VERSION:
            raise RuntimeError("G3R compatibility provenance is incomplete")
    return {
        "certificate": "P5_release_gate.json",
        "summary": "P5_technical_preflight_summary.json",
        "code_commit": certificate_commit,
    }


def _validate_model_freeze_absent(project_root):
    path = _project_path(project_root, "prognosis_analysis/model_freeze_lock.json")
    if os.path.exists(path):
        raise RuntimeError("model_freeze_lock.json exists; W08 formal is not authorized")
    return {"status": "absent"}


def _nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def _is_r0_archived_attempt_compat(attempt_id, failure, run_state):
    """Recognise the one R0 archive whose run state was captured mid-modeling."""
    required_run_state_keys = (
        "A_population", "B_data_read", "formal_run", "slic_cache_cases",
        "stage", "started_at_epoch", "status", "W_columns",
    )
    return (
        attempt_id == "attempt_001_failed" and
        failure.get("stage") == "W08" and
        failure.get("status") == "failed" and
        run_state.get("stage") == "W08" and
        run_state.get("status") == "modeling" and
        run_state.get("formal_run") is True and
        all(key in run_state for key in required_run_state_keys) and
        run_state.get("B_data_read") is False and
        "final_outputs_generated" not in run_state and
        all(run_state.get(key, False) is False for key in B_ACCESS_FLAGS
            if key in run_state)
    )


def _validate_archived_failure_schema(attempt_id, failure, run_state):
    required_failure_keys = (
        "attempt_id", "stage", "status", "failure_stage",
        "code_commit_at_attempt",
    ) + B_ACCESS_FLAGS + ("final_outputs_generated",)
    missing_failure = [key for key in required_failure_keys
                       if key not in failure]
    if missing_failure:
        raise RuntimeError(
            "failed attempt audit is missing fields for %s: %s" %
            (attempt_id, ",".join(missing_failure)))
    if failure.get("attempt_id") != attempt_id or \
            failure.get("stage") != "W08" or \
            failure.get("status") != "failed":
        raise RuntimeError("failed attempt identity/status mismatch: %s" % attempt_id)
    if not _nonempty_text(failure.get("failure_stage")):
        raise RuntimeError("failed attempt has no failure_stage: %s" % attempt_id)
    if not (_nonempty_text(failure.get("exception_summary")) or
            _nonempty_text(failure.get("failure_reason_summary"))):
        raise RuntimeError("failed attempt has no failure reason: %s" % attempt_id)
    for key in B_ACCESS_FLAGS + ("final_outputs_generated",):
        if type(failure.get(key)) is not bool or failure.get(key) is not False:
            raise RuntimeError("failed attempt %s has unsafe %s" % (attempt_id, key))

    if _is_r0_archived_attempt_compat(attempt_id, failure, run_state):
        return "r0_compat"

    required_run_state_keys = (
        "stage", "status", "formal_run", "failure_stage", "code_commit",
    ) + B_ACCESS_FLAGS + ("final_outputs_generated",)
    missing_run_state = [key for key in required_run_state_keys
                         if key not in run_state]
    if missing_run_state:
        raise RuntimeError(
            "failed attempt run state is missing fields for %s: %s" %
            (attempt_id, ",".join(missing_run_state)))
    if run_state.get("stage") != "W08" or \
            run_state.get("status") != "failed" or \
            run_state.get("formal_run") is not True:
        raise RuntimeError("failed attempt run state is not explicitly failed: %s" %
                           attempt_id)
    if run_state.get("failure_stage") != failure.get("failure_stage") or \
            run_state.get("code_commit") != failure.get("code_commit_at_attempt"):
        raise RuntimeError("failed attempt artifacts are not cross-reconciled: %s" %
                           attempt_id)
    for key in B_ACCESS_FLAGS + ("final_outputs_generated",):
        if type(run_state.get(key)) is not bool or run_state.get(key) is not False:
            raise RuntimeError("failed attempt run state %s is unsafe: %s" %
                               (key, attempt_id))
    return "explicit_failed"


def _validate_reconciled_attempts(project_root, output_root, status):
    final_paths = [name for name in W08_FINAL_OUTPUT_NAMES
                   if os.path.exists(os.path.join(output_root, name))]
    if final_paths:
        raise RuntimeError(
            "prior final outputs exist: %s" % ",".join(final_paths))

    stale_staging = _staging_dirs(output_root)
    if stale_staging:
        raise RuntimeError(
            "unfinalized W08 staging attempts exist: %s" %
            ",".join(os.path.basename(path) for path in stale_staging))

    root_run_state_path = os.path.join(output_root, W08_RUN_STATE_NAME)
    if os.path.isfile(root_run_state_path):
        root_run_state = _read_json_path(root_run_state_path, "W08 run state")
        if root_run_state.get("status") not in ("failed",):
            raise RuntimeError("prior W08 output state is incomplete or completed")
        if not root_run_state.get("failure_stage") or \
                root_run_state.get("final_outputs_generated") is not False:
            raise RuntimeError("prior W08 failed state is not fail-closed")

    attempts_root = os.path.join(output_root, "attempts")
    attempt_dirs = []
    if os.path.isdir(attempts_root):
        attempt_dirs = sorted(
            child for child in os.listdir(attempts_root)
            if os.path.isdir(os.path.join(attempts_root, child)))
    last_attempt = status.get("last_attempt", {}) if isinstance(status, dict) else {}
    execution = status.get("execution", {}) if isinstance(status, dict) else {}
    if attempt_dirs and (
            last_attempt.get("status") != "failed" or
            execution.get("last_attempt_status") != "failed"):
        raise RuntimeError("prior failed attempt is not explicitly reconciled")

    for attempt_id in attempt_dirs:
        if not attempt_id.endswith("_failed"):
            raise RuntimeError("unreconciled prior attempt: %s" % attempt_id)
        attempt_root = os.path.join(attempts_root, attempt_id)
        failure_path = os.path.join(attempt_root, "failure_audit.json")
        run_state_path = os.path.join(attempt_root, W08_RUN_STATE_NAME)
        if not os.path.isfile(failure_path) or not os.path.isfile(run_state_path):
            raise RuntimeError("failed attempt lacks reconciliation artifacts: %s" % attempt_id)
        failure = _read_json_path(failure_path, "failed attempt audit")
        run_state = _read_json_path(run_state_path, "failed attempt run state")
        if failure.get("attempt_id") != attempt_id or failure.get("status") != "failed":
            raise RuntimeError("failed attempt identity/status mismatch: %s" % attempt_id)
        _validate_archived_failure_schema(attempt_id, failure, run_state)
        failure_commit = failure.get("code_commit_at_attempt")
        if not _git_commit_resolves(project_root, failure_commit):
            raise RuntimeError("failed attempt code commit does not resolve: %s" % attempt_id)
        if last_attempt.get("attempt_id") != attempt_id or \
                last_attempt.get("code_commit_at_attempt") != failure_commit or \
                last_attempt.get("failure_stage") != failure.get("failure_stage"):
            raise RuntimeError("failed attempt is not reconciled in execution_status: %s" % attempt_id)
        if any(os.path.exists(os.path.join(attempt_root, name))
               for name in W08_FINAL_OUTPUT_NAMES):
            raise RuntimeError("failed attempt contains final outputs: %s" % attempt_id)
    if not attempt_dirs and last_attempt.get("status") == "failed":
        raise RuntimeError("execution_status records a failed attempt without an archive")
    return {"attempts_checked": attempt_dirs}


def _require_formal_release_authorization(release_gate):
    """Fail closed if a gate implementation returns a non-authorizing result."""
    if not isinstance(release_gate, dict):
        result = {
            "stage": "W08_FORMAL_RELEASE",
            "status": "FAIL",
            "formal_authorized": False,
            "checks": {},
            "failure_reasons": ["release gate returned a non-object result"],
            "B_access": dict((key, False) for key in B_ACCESS_FLAGS),
            "final_outputs_generated": False,
        }
        raise W08ReleaseGateError(result)

    result = dict(release_gate)
    raw_reasons = result.get("failure_reasons", [])
    if isinstance(raw_reasons, (list, tuple)):
        reasons = [str(reason) for reason in raw_reasons]
    elif raw_reasons is None:
        reasons = []
    else:
        reasons = ["release gate failure_reasons is not a list"]
    if result.get("status") != "PASS":
        reasons.append("release gate status is not PASS")
    if result.get("formal_authorized") is not True:
        reasons.append("release gate formal_authorized is not true")
    if not reasons:
        return result
    result["failure_reasons"] = list(dict.fromkeys(reasons))
    result.setdefault("stage", "W08_FORMAL_RELEASE")
    result.setdefault("B_access", dict((key, False) for key in B_ACCESS_FLAGS))
    result.setdefault("final_outputs_generated", False)
    raise W08ReleaseGateError(result)


def _run_gate_check(checks, failures, name, callback, project_root, output_root):
    try:
        value = callback()
    except Exception as exc:
        reason = "%s: %s" % (
            name, _safe_exception_text(exc, project_root, output_root))
        checks[name] = {"status": "FAIL", "reason": reason}
        failures.append(reason)
        return None
    checks[name] = {"status": "PASS"}
    return value


def validate_w08_release_gate(output_root=OUTPUT_ROOT, project_root=PROJECT_ROOT):
    """Validate every non-patient W08 release prerequisite before any A read."""
    project_root = os.path.abspath(project_root)
    output_root = os.path.abspath(os.fspath(output_root))
    checks = {}
    failures = []
    code_commit = _run_gate_check(
        checks, failures, "code_commit", lambda: _git_head(project_root),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "P4R_provenance_reconciliation",
        lambda: _validate_p4r_reconciliation(project_root),
        project_root, output_root)
    bindings = _run_gate_check(
        checks, failures, "frozen_W03_W04_W07_W07A_bindings",
        lambda: _validate_frozen_bindings(project_root),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "W08_configuration", _validate_w08_configuration,
        project_root, output_root)
    execution_status = _run_gate_check(
        checks, failures, "execution_status", lambda: _validate_execution_status(project_root),
        project_root, output_root)
    technical_freeze = _run_gate_check(
        checks, failures, "technical_freeze", lambda: _validate_technical_freeze(project_root),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "W05_access_boundary",
        lambda: _validate_w05_access_boundary(project_root),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "model_freeze_absent",
        lambda: _validate_model_freeze_absent(project_root),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "prior_attempts_reconciled",
        lambda: _validate_reconciled_attempts(project_root, output_root, execution_status),
        project_root, output_root)
    _run_gate_check(
        checks, failures, "G3_release_certificate",
        lambda: _validate_g3_certificate(project_root, code_commit, bindings),
        project_root, output_root)

    b_flags = dict((key, False) for key in B_ACCESS_FLAGS)
    if isinstance(execution_status, dict):
        recorded = execution_status.get("b_access", {})
        if isinstance(recorded, dict):
            for key in B_ACCESS_FLAGS:
                if recorded.get(key) is not False:
                    reason = "execution_status.%s is not false" % key
                    checks["B_access_flags"] = {"status": "FAIL", "reason": reason}
                    if reason not in failures:
                        failures.append(reason)
    if isinstance(technical_freeze, dict):
        for key in ("B_data_read",):
            if technical_freeze.get(key) is not False:
                reason = "technical_freeze.%s is not false" % key
                checks["B_access_flags"] = {"status": "FAIL", "reason": reason}
                if reason not in failures:
                    failures.append(reason)
    if "B_access_flags" not in checks:
        checks["B_access_flags"] = {"status": "PASS"}

    result = {
        "stage": "W08_FORMAL_RELEASE",
        "status": "PASS" if not failures else "FAIL",
        "formal_authorized": not bool(failures),
        "code_commit": code_commit,
        "checks": checks,
        "failure_reasons": failures,
        "B_access": b_flags,
        "final_outputs_generated": False,
    }
    if failures:
        raise W08ReleaseGateError(result)
    return result


def _normalise_ids(values):
    output = {str(value).strip() for value in values}
    if "" in output:
        raise RuntimeError("A-only allow-list contains a blank identifier")
    return output


def _six_neighbor_interface(habitat, roi, spacing_xyz):
    """Return 3-D six-neighbour habitat interface area in mm2."""
    areas = [spacing_xyz[0] * spacing_xyz[1],
             spacing_xyz[0] * spacing_xyz[2],
             spacing_xyz[1] * spacing_xyz[2]]
    total = 0.0
    for axis, area in enumerate(areas):
        left = np.take(habitat, indices=range(habitat.shape[axis] - 1), axis=axis)
        right = np.take(habitat, indices=range(1, habitat.shape[axis]), axis=axis)
        left_roi = np.take(roi, indices=range(roi.shape[axis] - 1), axis=axis)
        right_roi = np.take(roi, indices=range(1, roi.shape[axis]), axis=axis)
        total += float(((left >= 0) & (right >= 0) & left_roi & right_roi &
                        (left != right)).sum()) * area
    return total


def _radiomics_support_state(voxel_count):
    """Classify one fold-specific habitat mask by its voxel support."""
    if isinstance(voxel_count, bool):
        raise RuntimeError("radiomics mask voxel count must be an integer")
    try:
        voxel_count = operator.index(voxel_count)
    except TypeError:
        raise RuntimeError("radiomics mask voxel count must be an integer")
    if voxel_count < 0:
        raise RuntimeError("radiomics mask voxel count cannot be negative")
    if voxel_count == 0:
        return RADIOMICS_STATE_STRUCTURALLY_ABSENT
    if voxel_count < MINIMUM_ROI_SIZE:
        return RADIOMICS_STATE_TECHNICALLY_UNEXTRACTABLE_SMALL_ROI
    return RADIOMICS_STATE_EXTRACTABLE


def _backend_compatibility_settings(config):
    """Build backend settings without changing the frozen public threshold."""
    settings = w02.extractor_settings(config)
    if type(MINIMUM_ROI_SIZE) is not int or MINIMUM_ROI_SIZE != 10:
        raise w08.W08ValidationError(
            "W08 public minimumROISize is not the frozen value 10")
    setting = settings.get("setting")
    if not isinstance(setting, dict) or \
            setting.get("minimumROISize") != MINIMUM_ROI_SIZE:
        raise w08.W08ValidationError(
            "W08 public/config minimumROISize is inconsistent")
    backend = dict(settings)
    backend["setting"] = dict(setting)
    backend["setting"]["minimumROISize"] = \
        _PYRADIOMICS_COMPATIBILITY_MINIMUM_ROI_SIZE
    return backend


def _build_backend_compatible_extractor(config=None):
    """Create the locked PyRadiomics extractor with the boundary shim only."""
    if config is None:
        config = w02.load_config()
    settings = _backend_compatibility_settings(config)
    return w02.featureextractor.RadiomicsFeatureExtractor(settings)


def _mask_label_voxel_count(mask):
    """Count label-1 voxels without changing the SimpleITK mask."""
    mask_array = w02.sitk.GetArrayFromImage(mask)
    labels = np.unique(mask_array)
    if not np.isin(labels, [0, 1]).all():
        raise w08.W08ValidationError(
            "radiomics compatibility mask must be binary with label 1")
    return int(np.count_nonzero(mask_array == 1))


def _read_header(path):
    return list(pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns)


def _read_a_csv(path, allowed_ids, usecols=None):
    """Read an A-allowed technical CSV before any pandas frame is assembled."""
    frame = read_technical_A(
        path, allowed_ids=allowed_ids, dtype={"影像号": str}, usecols=usecols)
    if "影像号" not in frame.columns:
        raise RuntimeError("A technical source lacks 影像号: %s" % os.path.basename(path))
    frame["影像号"] = frame["影像号"].astype(str).str.strip()
    if "split" in frame.columns:
        split = frame["split"].astype(str).str.strip()
        if not split.eq("A").all():
            raise RuntimeError("non-A row admitted from %s" % os.path.basename(path))
    return frame


def _read_a_w_batch(batch_name, filename, metadata_columns, allowed_ids):
    path = os.path.join(FEATURE_ROOT, filename)
    header = _read_header(path)
    feature_columns = [column for column in header
                       if column not in set(metadata_columns)]
    if not feature_columns:
        raise RuntimeError("W batch has no feature columns: %s" % batch_name)
    usecols = list(metadata_columns) + feature_columns
    table = _read_a_csv(path, allowed_ids, usecols=usecols)
    table = table[table["读者"].astype(str).str.strip().eq("R1")].copy()
    if set(table["影像号"]) != set(allowed_ids):
        raise RuntimeError("W batch does not cover the W06 A population: %s" %
                           batch_name)
    if table["影像号"].duplicated().any():
        raise RuntimeError("W batch has duplicated A R1 IDs: %s" % batch_name)
    table = table[["影像号"] + feature_columns].set_index("影像号")
    table.columns = ["W__" + str(column) for column in table.columns]
    for column in table.columns:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    return table


def load_a_feature_frame(population):
    """Assemble a W08 frame from A-only reads and explicit availability flags."""
    allowed_ids = _normalise_ids(population["patient_id"])
    clinical_usecols = ["影像号", "split"] + list(w08.CLINICAL_COLUMNS)
    clinical = _read_a_csv(CLINICAL_A, allowed_ids, usecols=clinical_usecols)
    clinical = clinical[clinical["影像号"].isin(allowed_ids)].copy()
    clinical = clinical.set_index("影像号")
    if set(clinical.index) != allowed_ids:
        raise RuntimeError("A clinical feature frame does not cover W06 A")

    w_tables = [_read_a_w_batch(name, filename, metadata, allowed_ids)
                for name, filename, metadata in W_BATCHES]
    whole_tumour = pd.concat(w_tables, axis=1, join="inner")
    if len(whole_tumour.columns) != 1130:
        raise RuntimeError("W block must contain 1130 frozen features, got %d" %
                           len(whole_tumour.columns))
    if set(whole_tumour.index) != allowed_ids:
        raise RuntimeError("W block does not cover W06 A")

    low = _read_a_csv(
        W03_LOW, allowed_ids, usecols=["影像号", "habitat_present", "status"])
    high = _read_a_csv(
        W03_HIGH, allowed_ids, usecols=["影像号", "habitat_present", "status"])
    low = low.set_index("影像号")
    high = high.set_index("影像号")
    if set(low.index) != allowed_ids or set(high.index) != allowed_ids:
        raise RuntimeError("W03 A availability does not cover W06 A")

    data = population.copy()
    data["patient_id"] = data["patient_id"].astype(str).str.strip()
    data = data.set_index("patient_id")
    for column in w08.CLINICAL_COLUMNS:
        data[column] = clinical[column]
    data = data.join(whole_tumour, how="left")
    data["split"] = "A"
    data["technical_cohort"] = "A393"

    availability = {}
    for block, table in (("R_low", low), ("R_high", high)):
        present = pd.to_numeric(table["habitat_present"], errors="coerce")
        status = table["status"].astype(str).str.strip()
        if present.isna().any() or not present.isin([0, 1]).all():
            raise RuntimeError("invalid W03 %s structural availability" % block)
        availability[block + "_structurally_defined"] = present.astype(int)
        availability[block + "_technically_available"] = status.eq("extractable").astype(int)

    finite_w = np.isfinite(data[whole_tumour.columns].to_numpy(dtype=float)).all(axis=1)
    availability["W_structurally_defined"] = 1
    availability["W_technically_available"] = finite_w.astype(int)
    availability["W_available"] = finite_w.astype(int)

    # These columns are intentionally placeholders in the initial frame.
    # The formal provider replaces them from fold-specific masks before any
    # preprocessing or model fitting occurs.
    placeholders = {column: np.nan for column in w08.GLOBAL_COLUMNS}
    for block in ("R_low", "R_high"):
        for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
            placeholders[w08.RADIOMICS_PREFIXES[block] + feature] = np.nan
    data["split"] = "A"
    data["technical_cohort"] = "A393"
    extra = pd.concat([pd.DataFrame(availability, index=data.index),
                       pd.DataFrame(placeholders, index=data.index)], axis=1)
    data = pd.concat([data, extra], axis=1)
    return data.reset_index()


class AOnlyFoldFeatureProvider(w08.FoldFeatureProvider):
    """Fold-specific habitat/G/R provider backed only by the A technical data."""

    formal_capable = True
    fold_specific_habitat = True

    def __init__(self, frame, supervoxel_table, habitat_config=HABITAT_CONFIG,
                 cache_root=SLIC_CACHE_ROOT):
        self.frame = w08._normalise_frame(frame)
        self._by_id = self.frame.set_index("patient_id", drop=False)
        self._allowed_ids = set(self._by_id.index)
        self._sv = self._normalise_supervoxel_table(supervoxel_table)
        self._habitat_config = w07._read_json(habitat_config)
        self._cache_root = cache_root
        os.makedirs(self._cache_root, exist_ok=True)
        self._case_cache = {}
        self._state_cache = {}
        self.fit_calls = []
        self.transform_calls = []
        self._extractor = _build_backend_compatible_extractor()

    @staticmethod
    def _normalise_supervoxel_table(table):
        required = {"影像号", "reader", "sv_label", "n_tumor_voxels", "Mean"}
        if not required.issubset(table.columns):
            raise RuntimeError("A supervoxel table lacks required columns")
        table = table.copy()
        table["影像号"] = table["影像号"].astype(str).str.strip()
        if not table["reader"].astype(str).str.strip().eq("R1").all():
            raise RuntimeError("A supervoxel table contains a non-R1 reader")
        table["sv_label"] = pd.to_numeric(table["sv_label"], errors="coerce")
        table["n_tumor_voxels"] = pd.to_numeric(
            table["n_tumor_voxels"], errors="coerce")
        table["Mean"] = pd.to_numeric(table["Mean"], errors="coerce")
        if table[["sv_label", "n_tumor_voxels", "Mean"]].isna().any().any():
            raise RuntimeError("A supervoxel table contains invalid values")
        if table["sv_label"].duplicated().any():
            # Duplicates are allowed across cases but not within one case.
            duplicate = table.duplicated(["影像号", "sv_label"]).any()
            if duplicate:
                raise RuntimeError("A supervoxel table has duplicate case labels")
        return table

    def _sv_for_id(self, identifier):
        group = self._sv[self._sv["影像号"].eq(str(identifier))]
        if group.empty:
            raise RuntimeError("missing A supervoxel representation for %s" % identifier)
        return group.sort_values("sv_label").reset_index(drop=True)

    def _cache_path(self, identifier):
        return os.path.join(self._cache_root, str(identifier) + ".npz")

    def _prepare_case(self, identifier):
        identifier = str(identifier).strip()
        if identifier in self._case_cache:
            return self._case_cache[identifier]
        cache_path = self._cache_path(identifier)
        image_path = os.path.join(technical.PREP, identifier, "R1_image.nrrd")
        mask_path = os.path.join(technical.PREP, identifier, "R1_mask.nrrd")
        if not (os.path.isfile(image_path) and os.path.isfile(mask_path)):
            raise RuntimeError("A preprocessed image/ROI is missing for %s" % identifier)

        image = w02.sitk.ReadImage(w02.apath(image_path))
        roi_image = w02.sitk.ReadImage(w02.apath(mask_path))
        errors, arr, roi = technical.geom(image, roi_image)
        if errors:
            raise RuntimeError("A case %s failed geometry validation: %s" %
                               (identifier, ";".join(errors)))
        if os.path.isfile(cache_path):
            with np.load(cache_path) as cached:
                labels = cached["labels"].astype(np.int32, copy=False)
                cached_roi = cached["roi"].astype(bool, copy=False)
            if labels.shape != roi.shape or not np.array_equal(cached_roi, roi):
                raise RuntimeError("SLIC cache mismatch for A case %s" % identifier)
        else:
            labels = technical.slic_labels(image, self._habitat_config, True)
            if labels.shape != roi.shape:
                raise RuntimeError("SLIC label shape mismatch for A case %s" % identifier)
            temporary = cache_path + ".tmp"
            with open(temporary, "wb") as handle:
                np.savez_compressed(handle, labels=labels,
                                    roi=roi.astype(np.uint8))
            os.replace(temporary, cache_path)

        sv = self._sv_for_id(identifier)
        observed_values, observed_counts, observed_by_label = technical.sv_stats(
            arr, labels, roi)
        expected_by_label = dict(zip(
            sv["sv_label"].astype(int), sv["Mean"].to_numpy(dtype=float)))
        expected_counts_by_label = dict(zip(
            sv["sv_label"].astype(int),
            sv["n_tumor_voxels"].to_numpy(dtype=int)))
        if set(observed_by_label) != set(expected_by_label):
            raise RuntimeError("SLIC/supervoxel mean mismatch for A case %s" % identifier)
        if (not all(abs(float(observed_by_label[label]) -
                        float(expected_by_label[label])) <= 5e-6
                    for label in expected_by_label) or
                any(int(observed_counts[index]) != int(expected_counts_by_label[label])
                    for index, label in enumerate(sorted(observed_by_label)))):
            raise RuntimeError("SLIC/supervoxel support mismatch for A case %s" % identifier)
        self._case_cache[identifier] = {
            "image_path": image_path,
            "mask_path": mask_path,
            "labels": labels,
            "roi": roi,
            "spacing_xyz": tuple(float(x) for x in image.GetSpacing()),
            "sv": sv,
        }
        return self._case_cache[identifier]

    def prepare_all_cases(self):
        for identifier in sorted(self._allowed_ids):
            self._prepare_case(identifier)

    def _feature_sources(self, training_hash):
        required = w08._required_fold_specific_columns(list(w08.MODEL_SPECS))
        return {
            column: {
                "source": "fold_fit_regenerated",
                "fit_training_id_hash": training_hash,
                "validation_ids_used_for_fit": False,
            }
            for column in required
        }

    def fit(self, training_ids, seed):
        ids = sorted(str(value).strip() for value in training_ids)
        if not ids or not set(ids).issubset(self._allowed_ids):
            raise w08.W08ValidationError("provider training IDs are not in the A frame")
        self.fit_calls.append(tuple(ids))
        flattened = []
        weights = []
        for identifier in ids:
            self._prepare_case(identifier)
            group = self._sv_for_id(identifier)
            values = group["Mean"].to_numpy(dtype=float)
            if values.size == 0 or not np.isfinite(values).all():
                raise w08.W08ValidationError(
                    "missing/nonfinite A supervoxel input for %s" % identifier)
            flattened.append(values)
            weights.append(np.full(values.size, 1.0 / float(values.size)))
        values = np.concatenate(flattened)
        sample_weights = np.concatenate(weights)
        if np.unique(values).size < 2:
            raise w08.W08ValidationError("fold-specific K=2 habitat fit needs two distinct values")
        estimator = KMeans(n_clusters=2, random_state=int(seed), n_init=10)
        estimator.fit(values.reshape(-1, 1), sample_weight=sample_weights)
        centres = tuple(sorted(float(value)
                               for value in estimator.cluster_centers_.reshape(-1)))
        boundary = (centres[0] + centres[1]) / 2.0
        training_hash = w08.canonical_id_hash(ids)
        state = w08.FoldState(
            training_hash, int(seed), centres, boundary,
            metadata={
                "fold_specific_habitat": True,
                "patient_weighting": "each patient total supervoxel weight=1",
                "supervoxel_count": int(values.size),
                "representation_source": "A_preprocessed_R1_SLIC_supervoxel_mean",
                "feature_generation": "fold-specific habitat masks; G and R regenerated",
                "feature_sources": self._feature_sources(training_hash),
                "validation_ids_used_for_fit": False,
            })
        return state

    @staticmethod
    def _habitat_from_boundary(case, boundary):
        labels = case["labels"]
        roi = case["roi"]
        sv = case["sv"]
        habitat = np.full(labels.shape, -1, dtype=np.int8)
        for label, mean in zip(sv["sv_label"].astype(int), sv["Mean"]):
            habitat[labels == int(label)] = int(float(mean) >= float(boundary))
        habitat[~roi] = -1
        return habitat

    def _radiomics_for_mask(self, image, mask, block, expected_voxel_count):
        actual_voxel_count = _mask_label_voxel_count(mask)
        if type(expected_voxel_count) is not int or \
                actual_voxel_count != expected_voxel_count:
            raise w08.W08ValidationError(
                "radiomics compatibility mask voxel count is inconsistent")
        if _radiomics_support_state(actual_voxel_count) != \
                RADIOMICS_STATE_EXTRACTABLE:
            raise w08.W08ValidationError(
                "radiomics compatibility backend received an ineligible mask")
        result = self._extractor.execute(image, mask)
        output = {}
        for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
            value = result.get(feature, np.nan)
            try:
                output[w08.RADIOMICS_PREFIXES[block] + feature] = float(value)
            except (TypeError, ValueError):
                output[w08.RADIOMICS_PREFIXES[block] + feature] = np.nan
        return output

    def _transform_one(self, identifier, state):
        case = self._prepare_case(identifier)
        image = w02.sitk.ReadImage(w02.apath(case["image_path"]))
        roi = case["roi"]
        habitat = self._habitat_from_boundary(case, state.boundary)
        low_mask = roi & (habitat == 0)
        high_mask = roi & (habitat == 1)
        low_voxel_count = int(low_mask.sum())
        high_voxel_count = int(high_mask.sum())
        low_state = _radiomics_support_state(low_voxel_count)
        high_state = _radiomics_support_state(high_voxel_count)
        tumour_n = int(roi.sum())
        spacing_xyz = case["spacing_xyz"]
        voxel_volume = float(np.prod(spacing_xyz))
        tumour_volume = float(tumour_n * voxel_volume)
        values = case["sv"]["Mean"].to_numpy(dtype=float)
        high_fraction = float(high_mask.sum() / float(tumour_n))
        interface = _six_neighbor_interface(habitat, roi, spacing_xyz)
        connected, n_connected = ndimage.label(
            high_mask, ndimage.generate_binary_structure(3, 1))
        sizes = np.bincount(connected.ravel())[1:] if n_connected else np.array([])
        largest = int(sizes.max()) if len(sizes) else 0
        depth = ndimage.distance_transform_edt(roi, sampling=spacing_xyz[::-1])
        max_depth = float(depth[roi].max()) if roi.any() else 0.0
        radial = (float(depth[high_mask].sum() / (max_depth * tumour_n))
                  if high_mask.any() and max_depth > 0 else 0.0)
        row = {
            "patient_id": identifier,
            "R_low_voxel_count": low_voxel_count,
            "R_high_voxel_count": high_voxel_count,
            "R_low_state": low_state,
            "R_high_state": high_state,
            "R_low_structurally_defined": int(low_voxel_count > 0),
            "R_high_structurally_defined": int(high_voxel_count > 0),
            "R_low_technically_extractable": int(
                low_state == RADIOMICS_STATE_EXTRACTABLE),
            "R_high_technically_extractable": int(
                high_state == RADIOMICS_STATE_EXTRACTABLE),
            "H_high_fraction": high_fraction,
            "sv_median_minus_boundary": float(np.median(values) - state.boundary),
            "sv_IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "interface_density": float(interface / tumour_volume),
            "H_high_largest_component_tumor_fraction": float(largest / float(tumour_n)),
            "H_high_radial_burden": radial,
        }
        if low_state == RADIOMICS_STATE_EXTRACTABLE:
            low_image_mask = w02.make_habitat_mask(
                image, low_mask.astype(np.uint8), 1)
            row.update(self._radiomics_for_mask(
                image, low_image_mask, "R_low", low_voxel_count))
        else:
            row.update({w08.RADIOMICS_PREFIXES["R_low"] + feature: np.nan
                        for feature in w08.FROZEN_CANDIDATE_FEATURES["R_low"]})
        if high_state == RADIOMICS_STATE_EXTRACTABLE:
            high_image_mask = w02.make_habitat_mask(
                image, high_mask.astype(np.uint8), 1)
            row.update(self._radiomics_for_mask(
                image, high_image_mask, "R_high", high_voxel_count))
        else:
            row.update({w08.RADIOMICS_PREFIXES["R_high"] + feature: np.nan
                        for feature in w08.FROZEN_CANDIDATE_FEATURES["R_high"]})
        return row

    def transform(self, ids, state):
        identifiers = [str(value).strip() for value in ids]
        if not set(identifiers).issubset(self._allowed_ids):
            raise w08.W08ValidationError("provider transform IDs are not in the A frame")
        self.transform_calls.append((tuple(identifiers), state.training_id_hash))
        cache = self._state_cache.setdefault(state.training_id_hash, {})
        new_rows = []
        for identifier in identifiers:
            if identifier not in cache:
                cache[identifier] = self._transform_one(identifier, state)
            new_rows.append(cache[identifier])
        generated = pd.DataFrame(new_rows).set_index("patient_id")
        base = self._by_id.loc[identifiers].copy()
        for column in RADIOMICS_SUPPORT_COLUMNS:
            base[column] = generated.loc[identifiers, column].to_numpy()
        for column in w08.GLOBAL_COLUMNS:
            base[column] = generated.loc[identifiers, column].to_numpy()
        for block in ("R_low", "R_high"):
            for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
                column = w08.RADIOMICS_PREFIXES[block] + feature
                base[column] = generated.loc[identifiers, column].to_numpy()
        return base.reset_index(drop=True)


def _serialise_complex(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def write_results(result, config, population, started_epoch, output_root,
                  attempt=None, code_commit=None):
    """Write, validate, and transactionally promote the complete W08 result."""
    output_root = os.path.abspath(os.fspath(output_root))
    if code_commit is None:
        code_commit = _git_head(PROJECT_ROOT)
    if attempt is None:
        attempt = _begin_attempt(output_root, code_commit, started_epoch)
    elif os.path.abspath(attempt["output_root"]) != output_root:
        raise RuntimeError("W08 attempt output root mismatch")

    staging_root = attempt["staging_root"]
    try:
        _atomic_json(os.path.join(staging_root, W08_ATTEMPT_STATE_NAME), {
            "stage": "W08",
            "status": "writing",
            "attempt_id": attempt["attempt_id"],
            "code_commit_at_attempt": code_commit,
            "started_at_epoch": started_epoch,
            "final_outputs_generated": False,
        })
        predictions = result["predictions"].copy()
        fold_results = result["fold_results"].copy()
        selections = result["selection_results"].copy()

        prediction_columns = [
            "run_id", "model_id", "population", "repeat", "fold", "patient_id",
            "DFS_time", "DFS_event", "risk_score", "training_id_hash",
            "validation_id_hash", "outer_split_hash",
            "outer_validation_used_for_selection",
        ]
        _atomic_csv(predictions[prediction_columns],
                    os.path.join(staging_root, "predictions.csv"))

        complex_fold = ["centers", "representation_metadata", "preprocessing_audit",
                        "selected_features", "stability_actions",
                        "linear_predictor_clipping"]
        for column in complex_fold:
            if column in fold_results.columns:
                fold_results[column] = fold_results[column].map(_serialise_complex)
        _atomic_csv(fold_results, os.path.join(staging_root, "fold_results.csv"))

        if "inner_records" in selections.columns:
            selections["inner_records"] = selections["inner_records"].map(
                _serialise_complex)
        if "linear_predictor_clipping" in selections.columns:
            selections["linear_predictor_clipping"] = selections[
                "linear_predictor_clipping"].map(_serialise_complex)
        _atomic_csv(selections, os.path.join(staging_root, "selection_results.csv"))

        compatibility = _compatibility_provenance()
        outer_summary = result["audit"]["outer_split_validation"]
        audit = dict(result["audit"])
        audit.update({
            "stage": "W08",
            "status": "formal_complete",
            "formal_run": True,
            "attempt_id": attempt["attempt_id"],
            "code_commit": code_commit,
            "patient_level_outputs_written": True,
            "output_scope": "local_sensitive_prognosis_analysis_output_only",
            "W06_population_sha256": _sha256(W06_POPULATION),
            "W07_outer_split_sha256": w08.W07_OUTER_SPLIT_SHA256,
            "W04_protocol_sha256": w08.W04_PROTOCOL_SHA256,
            "n_population": int(len(population)),
            "prediction_rows_written": int(len(predictions)),
            "folds_expected": 50,
            "fold_results_expected": 650,
            "runs_expected": 13,
            "metrics_ready_schema": "prognosis_analysis/configs/w08_results_schema.json",
            "audit_schema": "prognosis_analysis/configs/w08_audit_schema.json",
            "created_at_epoch": time.time(),
            "started_at_epoch": started_epoch,
            "completed_at_epoch": time.time(),
            "outer_split_summary_copy": outer_summary,
            "model_freeze_lock_created": False,
            "compatibility_provenance": compatibility,
        })
        _atomic_json(os.path.join(staging_root, "audit.json"), audit)

        metadata = {
            "stage": "W08",
            "status": "formal_complete",
            "formal_run": True,
            "attempt_id": attempt["attempt_id"],
            "code_commit": code_commit,
            "runs": list(w08.FIXED_RUN_IDS),
            "models": list(w08.MODEL_SPECS),
            "outer_split_hash": w08.W07_OUTER_SPLIT_SHA256,
            "W04_protocol_sha256": w08.W04_PROTOCOL_SHA256,
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
            "outer_validation_used_for_selection": False,
            "patient_level_outputs_written": True,
            "compatibility_provenance": compatibility,
            "outputs": {
                "predictions": "predictions.csv",
                "fold_results": "fold_results.csv",
                "selection_results": "selection_results.csv",
                "audit": "audit.json",
                "run_metadata": "run_metadata.json",
                "formal_output_manifest": W08_OUTPUT_MANIFEST_NAME,
            },
        }
        _atomic_json(os.path.join(staging_root, "run_metadata.json"), metadata)

        outputs = {}
        for name in W08_REQUIRED_OUTPUT_NAMES:
            output_path = os.path.join(staging_root, name)
            if not os.path.isfile(output_path):
                raise RuntimeError("required W08 output was not staged: %s" % name)
            outputs[name] = {
                "path": name,
                "size_bytes": os.path.getsize(output_path),
                "sha256": _sha256(output_path),
            }
        manifest = {
            "schema": "w08_formal_output_manifest",
            "schema_version": "1.0",
            "stage": "W08",
            "status": "complete",
            "attempt_id": attempt["attempt_id"],
            "code_commit": code_commit,
            "created_at_epoch": time.time(),
            "promoted_at_epoch": time.time(),
            "outputs": outputs,
            "protocol": {
                "minimumROISize": MINIMUM_ROI_SIZE,
                "W04_protocol_sha256": w08.W04_PROTOCOL_SHA256,
                "W07_outer_split_sha256": w08.W07_OUTER_SPLIT_SHA256,
            },
            "compatibility_provenance": compatibility,
        }
        _atomic_json(os.path.join(staging_root, W08_OUTPUT_MANIFEST_NAME), manifest)
        _validate_formal_output_manifest(
            os.path.join(staging_root, W08_OUTPUT_MANIFEST_NAME),
            expected_attempt_id=attempt["attempt_id"],
            expected_code_commit=code_commit)
        _promote_staged_outputs(attempt)
        return _validate_formal_output_manifest(
            os.path.join(output_root, W08_OUTPUT_MANIFEST_NAME),
            expected_attempt_id=attempt["attempt_id"],
            expected_code_commit=code_commit)
    except Exception as exc:
        try:
            _write_attempt_failure(attempt, PROJECT_ROOT, "result_write", exc)
        except Exception:
            pass
        raise


def _load_population_and_provider(output_root=OUTPUT_ROOT):
    population = w08.load_frozen_a_population()
    frame = load_a_feature_frame(population)
    sv = pd.read_csv(SV_TABLE, encoding="utf-8-sig", dtype={"影像号": str})
    provider = AOnlyFoldFeatureProvider(
        frame, sv, cache_root=os.path.join(output_root, "work", "slic_cache"))
    return population, frame, provider


def smoke(output_root=OUTPUT_ROOT):
    """Validate one real A outer fold/provider transformation without fitting W08."""
    population, frame, provider = _load_population_and_provider(output_root)
    splits = w08.load_frozen_outer_splits(population)
    first = splits[(splits["repeat"] == 1) & (splits["fold"] == 1)]
    train_ids = sorted(first.loc[first["role"] == "train", "patient_id"].tolist())
    validation_ids = sorted(first.loc[first["role"] == "validation", "patient_id"].tolist())
    state = provider.fit(train_ids, 14346)
    train = provider.transform(train_ids[:2], state)
    validation = provider.transform(validation_ids[:2], state)
    required = w08._required_fold_specific_columns(list(w08.MODEL_SPECS))
    w08._validate_fold_provider_state(provider, state, train_ids, required)
    w08._validate_fold_provider_output(train, train_ids[:2], required, True)
    w08._validate_fold_provider_output(validation, validation_ids[:2], required, True)
    if not np.isfinite(train[list(w08.GLOBAL_COLUMNS)].to_numpy(dtype=float)).all():
        raise RuntimeError("smoke provider generated nonfinite global features")
    print(json.dumps({
        "stage": "W08",
        "status": "adapter_smoke_pass",
        "A_population": int(len(population)),
        "train_cases_checked": 2,
        "validation_cases_checked": 2,
        "B_data_read": False,
        "provider_formal_capable": bool(provider.formal_capable),
    }, ensure_ascii=False, sort_keys=True))


def preflight_fold(output_root=OUTPUT_ROOT):
    """Audit first-fold fold-specific mask sizes without radiomics/model fitting."""
    population, frame, provider = _load_population_and_provider(output_root)
    splits = w08.load_frozen_outer_splits(population)
    eligible = w08.eligible_ids(frame, "dual_radiomics")
    first = splits[(splits["repeat"] == 1) & (splits["fold"] == 1)]
    train_ids = sorted(set(first.loc[first["role"] == "train", "patient_id"]) & eligible)
    fold_ids = sorted(set(first["patient_id"]) & eligible)
    state = provider.fit(train_ids, 14346)
    sizes = []
    for identifier in fold_ids:
        case = provider._prepare_case(identifier)
        habitat = provider._habitat_from_boundary(case, state.boundary)
        sizes.append((identifier,
                      int((case["roi"] & (habitat == 0)).sum()),
                      int((case["roi"] & (habitat == 1)).sum())))
    subminimum = [row for row in sizes if row[1] < 10 or row[2] < 10]
    print(json.dumps({
        "stage": "W08",
        "status": "fold_mask_size_preflight_blocked",
        "population": "dual_radiomics",
        "eligible_cases": int(len(eligible)),
        "fold_cases": int(len(fold_ids)),
        "repeat": 1,
        "fold": 1,
        "boundary": float(state.boundary),
        "subminimum_cases": int(len(subminimum)),
        "min_low_mask_voxels": int(min(row[1] for row in sizes)),
        "min_high_mask_voxels": int(min(row[2] for row in sizes)),
        "locked_minimum_roi_size": 10,
        "B_data_read": False,
        "formal_run_started": False,
    }, ensure_ascii=False, sort_keys=True))


def _write_failure_state(output_root, project_root, stage, started_epoch,
                         formal_run_started, exception, attempt=None):
    """Persist a non-success state without ever emitting a running state."""
    output_root = os.path.abspath(os.fspath(output_root))
    project_root = os.path.abspath(project_root)
    if attempt is not None and attempt.get("status") not in ("failed", "promoted"):
        try:
            _write_attempt_failure(attempt, project_root, stage, exception)
        except Exception:
            pass
    try:
        code_commit = _git_head(project_root)
    except Exception:
        code_commit = None
    try:
        environment = _environment_fingerprint(project_root)
    except Exception as env_exc:
        environment = {"fingerprint_error": _safe_exception_text(
            env_exc, project_root, output_root)}
    partial_outputs = [name for name in W08_FINAL_OUTPUT_NAMES
                       if os.path.exists(os.path.join(output_root, name))]
    state = {
        "stage": "W08",
        "status": "failed",
        "formal_run": True,
        "formal_run_started": bool(formal_run_started),
        "started_at_epoch": started_epoch,
        "ended_at_epoch": time.time(),
        "failure_stage": stage,
        "exception_class": exception.__class__.__name__,
        "failure_reason": _safe_exception_text(
            exception, project_root, output_root),
        "code_commit": code_commit,
        "environment_fingerprint": environment,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": False,
        "partial_final_outputs": partial_outputs,
    }
    if attempt is not None:
        state["attempt_id"] = attempt.get("attempt_id")
        state["attempt_status"] = attempt.get("status")
        state["attempt_archive"] = os.path.relpath(
            attempt.get("failed_root", ""), output_root) \
            if attempt.get("failed_root") else None
    if isinstance(exception, W08ReleaseGateError):
        state["release_gate"] = exception.result
        try:
            os.makedirs(output_root, exist_ok=True)
            _atomic_json(os.path.join(output_root, W08_RELEASE_GATE_NAME),
                         exception.result)
        except Exception:
            pass
    try:
        os.makedirs(output_root, exist_ok=True)
        _atomic_json(os.path.join(output_root, W08_RUN_STATE_NAME), state)
    except Exception:
        # Preserve the original execution exception if the local status file
        # itself cannot be written.
        pass


def formal(output_root=OUTPUT_ROOT):
    output_root = os.path.abspath(os.fspath(output_root))
    started = time.time()
    stage = "release_gate"
    formal_run_started = False
    attempt = None
    try:
        release_gate = validate_w08_release_gate(
            output_root=output_root, project_root=PROJECT_ROOT)
        _require_formal_release_authorization(release_gate)
        os.makedirs(output_root, exist_ok=True)
        _atomic_json(os.path.join(output_root, W08_RELEASE_GATE_NAME), release_gate)

        stage = "initialisation"
        formal_run_started = True
        attempt = _begin_attempt(output_root, release_gate["code_commit"], started)
        _atomic_json(os.path.join(output_root, W08_RUN_STATE_NAME), {
            "stage": "W08", "status": "running", "formal_run": True,
            "B_data_read": False, "B_reader_invoked": False,
            "B_source_opened": False, "B_statistics_generated": False,
            "final_outputs_generated": False, "started_at_epoch": started,
            "code_commit": release_gate["code_commit"],
            "attempt_id": attempt["attempt_id"],
        })

        stage = "a_input_load"
        population, frame, provider = _load_population_and_provider(
            attempt["staging_root"])
        _atomic_json(os.path.join(output_root, W08_RUN_STATE_NAME), {
            "stage": "W08", "status": "modeling", "formal_run": True,
            "B_data_read": False, "B_reader_invoked": False,
            "B_source_opened": False, "B_statistics_generated": False,
            "final_outputs_generated": False, "started_at_epoch": started,
            "code_commit": release_gate["code_commit"],
            "attempt_id": attempt["attempt_id"],
            "A_population": int(len(population)), "W_columns": 1130,
            "slic_cache_cases": int(len(provider._case_cache)),
        })

        stage = "nested_cv_modeling"
        result = w08.run_w08(frame, provider)
        stage = "result_write"
        manifest = write_results(
            result, w08.load_config(), population, started, output_root,
            attempt=attempt, code_commit=release_gate["code_commit"])
        _atomic_json(os.path.join(output_root, W08_RUN_STATE_NAME), {
            "stage": "W08", "status": "complete", "formal_run": True,
            "B_data_read": False, "B_reader_invoked": False,
            "B_source_opened": False, "B_statistics_generated": False,
            "final_outputs_generated": True, "started_at_epoch": started,
            "completed_at_epoch": time.time(),
            "code_commit": release_gate["code_commit"],
            "attempt_id": attempt["attempt_id"],
            "formal_output_manifest": W08_OUTPUT_MANIFEST_NAME,
            "n_fold_results": int(len(result["fold_results"])),
            "n_predictions": int(len(result["predictions"])),
        })
        print(json.dumps({
            "stage": "W08", "status": "formal_complete",
            "n_fold_results": int(len(result["fold_results"])),
            "n_predictions": int(len(result["predictions"])),
            "B_data_read": False,
            "attempt_id": manifest["attempt_id"],
            "output_root": "prognosis_analysis/output/w08_formal_A",
            "elapsed_seconds": round(time.time() - started, 3),
        }, ensure_ascii=False, sort_keys=True))
    except Exception as exc:
        _write_failure_state(output_root, PROJECT_ROOT, stage, started,
                             formal_run_started, exc, attempt=attempt)
        raise


def main():
    parser = argparse.ArgumentParser(description="Local W08 A-only formal execution")
    parser.add_argument("--smoke", action="store_true",
                        help="validate one real A fold/provider transformation")
    parser.add_argument("--preflight-fold", action="store_true",
                        help="audit first-fold fold-specific mask sizes only")
    parser.add_argument("--output-root", default=OUTPUT_ROOT,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.smoke:
        smoke(args.output_root)
    elif args.preflight_fold:
        preflight_fold(args.output_root)
    else:
        formal(args.output_root)


if __name__ == "__main__":
    main()
