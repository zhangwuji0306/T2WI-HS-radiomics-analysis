"""FT05B-specific fail-closed authorization and aggregate B DFS access.

This adapter is the only outcome-access entry for the FT05B amendment.  It
validates the frozen FT04 lock, the accepted FT05A technical audit, the
ignored ``.finalize`` assets, and the FT_B_unlock receipt contract before it
touches the B outcome source.  It uses the existing source-level allow-list
and streaming primitive, but deliberately does not call the formal
``read_B_validation`` entry or ``require_b_unlock``.

FT05B is an access-only boundary.  B K-means fitting, model fitting, lambda
or cutoff tuning, feature selection, preprocessing-parameter estimation,
radiomics extraction, and radiomics re-extraction are explicitly prohibited.
FT06 prediction/evaluation is not executed here.
"""
from __future__ import absolute_import

import csv
import datetime
import hashlib
import json
import math
import os
import re
import subprocess
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_FEATURE_GUARD_ROOT = os.path.join(
    _PROJECT_ROOT, "feature_extract", "scripts")
if _FEATURE_GUARD_ROOT not in sys.path:
    sys.path.insert(0, _FEATURE_GUARD_ROOT)

try:  # package import
    from . import ft04_runner as ft04
    from . import ft05a_runner as ft05a
except ImportError:  # direct script execution
    import ft04_runner as ft04
    import ft05a_runner as ft05a
import data_split_guard


FT05B_STAGE = "FT05B"
FT_LABEL = "exploratory_fullA_habitat_non_nested_validation"
EXPECTED_LOCK_IDENTITY = (
    "10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e")
EXPECTED_FT05A_RUN_ID = "FT05A-20260912-01a08bf3"
EXPECTED_FT05A_RUN_IDENTITY = (
    "718f357176f704f42027669b47041d24b33e9116b010bceac07b574be84c00bd")
EXPECTED_FT05A_COHORT_SHA256 = (
    "642830a817c6c3e71845c32f9be64ab98514adc372d070570bba86f34ae5ba53")
EXPECTED_COMPLETION_EVIDENCE_SHA256 = (
    "1f70e474ef2dcf42c875630a309fd9f27d88bb9342d5ea60a44d7e1b85ecd585")
EXPECTED_TABLE_SHA256 = (
    "10b35d9d661da665bfe98e95dbefa34a6b0e9c0d911bae37a34f3d635ab5d804")
EXPECTED_MANIFEST_SHA256 = (
    "055bdf0e98d05ed4c4e0b8ae2c175d5e82d66ba484ebec30b4b8c04c9e0eb251")
EXPECTED_ROW_SCHEMA_SHA256 = (
    "3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19")
EXPECTED_R_LOW_CANDIDATE_SHA256 = (
    "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0")
EXPECTED_R_HIGH_CANDIDATE_SHA256 = (
    "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce")
EXPECTED_W_ASSET_SHA256 = (
    "462201e66d8e8989063f02f1d7f63865a23335883c582707dc7713f40d3e9649")
EXPECTED_W_ORDER_SHA256 = (
    "1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f")
EXPECTED_AUDIT_SHA256 = (
    "96758aec2949c58e1ed96ddcbb7072448a520b4598cfedf376e43b2197702778")
# Historical source commit recorded for the original FT05B access.  This is
# provenance for that access, not the commit containing this remediation.
HISTORICAL_ACCESS_SOURCE_COMMIT = (
    "5b2083ff85eb0565f795ae44988a0fe5f8c071ff")

FT04_LOCK_PATH = os.path.join(_HERE, "FT_model_freeze_lock.json")
FORMAL_MODEL_LOCK = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "model_freeze_lock.json")
FT05A_AMENDMENT_PATH = os.path.join(
    _HERE, "FT05A_scientific_freeze_amendment.md")
FT05A_TECHNICAL_AUDIT_PATH = os.path.join(
    _HERE, "FT05A_B_technical_generation_audit.md")
FT_B_UNLOCK_PATH = os.path.join(_HERE, "FT_B_unlock.json")
FT05B_RECEIPT_PATH = os.path.join(_HERE, "FT05B_unlock_receipt.json")

# These are the physical local assets.  The manifest's internal feature_table
# path names the pre-promotion canonical location, while the amendment binds
# the actual bytes to the ignored .finalize namespace.
FT05A_MANIFEST_RELATIVE_PATH = (
    "prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/"
    "FT05_B_feature_manifest.json")
FT05A_TABLE_RELATIVE_PATH = (
    "prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/"
    "FT05A_B_technical_features.csv")
FT05A_DECLARED_TABLE_RELATIVE_PATH = (
    "prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/"
    "FT05A_B_technical_features.csv")
OUTCOME_SOURCE_RELATIVE_PATH = (
    "prognosis_analysis/data/radiology_clinic_pathology_prognosis_data.xlsx")

FT05A_MANIFEST_PATH = os.path.join(_PROJECT_ROOT, *FT05A_MANIFEST_RELATIVE_PATH.split("/"))
FT05A_TABLE_PATH = os.path.join(_PROJECT_ROOT, *FT05A_TABLE_RELATIVE_PATH.split("/"))
OUTCOME_SOURCE_PATH = os.path.join(
    _PROJECT_ROOT, *OUTCOME_SOURCE_RELATIVE_PATH.split("/"))

B_OUTCOME_COLUMNS = ("影像号", "DFS_time", "DFS_event")
PROHIBITED_OPERATIONS = frozenset((
    "fit",
    "lambda_tuning",
    "feature_selection",
    "K-means_fit",
    "cutoff_optimization",
    "preprocessing_parameter_estimation",
    "radiomics_re-extraction",
))


class FT05BValidationError(ValueError):
    """Raised for any FT05B authorization or access-contract violation."""


class _GateContext(object):
    """Private in-memory authorization context; never serialized."""

    def __init__(self, summary, allowed_ids):
        self.summary = summary
        self.allowed_ids = tuple(allowed_ids)


def _fail(message):
    raise FT05BValidationError(message)


def _sha256_file(path):
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except (IOError, OSError) as exc:
        _fail("cannot hash %s: %s" % (path, exc))
    return digest.hexdigest()


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _read_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError, UnicodeError) as exc:
        _fail("cannot read %s: %s" % (label, exc))


def _read_text(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (IOError, OSError, UnicodeError) as exc:
        _fail("cannot read %s: %s" % (label, exc))


def _project_path(relative_path, label):
    if not isinstance(relative_path, str) or os.path.isabs(relative_path):
        _fail("%s must be a relative project path" % label)
    normalized = relative_path.replace("\\", "/")
    path = os.path.abspath(os.path.join(
        _PROJECT_ROOT, *normalized.split("/")))
    root = os.path.abspath(_PROJECT_ROOT)
    try:
        inside = os.path.commonpath((root, path)) == root
    except ValueError:
        inside = False
    if not inside:
        _fail("%s escapes the project root" % label)
    return path


def _require_exact_path(path, expected, label):
    if os.path.normcase(os.path.abspath(path)) != \
            os.path.normcase(os.path.abspath(expected)):
        _fail("%s must use the canonical FT05B allow-listed path" % label)
    return expected


def _require_sha(value, expected, label):
    if not re.match(r"^[0-9a-f]{64}$", str(value or "")) or \
            str(value).lower() != expected.lower():
        _fail("%s hash binding is invalid" % label)


def _git_commit_resolves(commit):
    """Return whether commit resolves to the same local Git commit object."""
    try:
        result = subprocess.run(
            ["git", "-C", os.path.abspath(_PROJECT_ROOT), "rev-parse",
             "--verify", "%s^{commit}" % commit],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, check=False, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and \
        result.stdout.strip().lower() == str(commit).lower()


def _marker(text, label, digest=True):
    size = 64 if digest else 40
    pattern = (r"(?im)^\s*(?:[-*]\s*)?`?%s`?\s*"
               r"(?:SHA-256)?\s*[:=]\s*`?([0-9a-f]{%d})`?\s*$") % (
                   re.escape(label), size)
    match = re.search(pattern, text)
    if not match:
        _fail("FT05B evidence is not bound to %s" % label)
    return match.group(1).lower()


def _validate_ft04_lock():
    if os.path.isfile(FORMAL_MODEL_LOCK):
        _fail("formal prognosis_analysis/model_freeze_lock.json exists")
    try:
        lock = ft04.validate_ft_model_freeze_lock(FT04_LOCK_PATH)
    except Exception as exc:
        _fail("FT04 lock is not valid: %s" % exc)
    if not isinstance(lock, dict) or \
            lock.get("artifact_id") != "FT_model_freeze_lock" or \
            lock.get("stage") != "FT04" or \
            lock.get("status") != "FROZEN" or \
            lock.get("lock_identity_sha256") != EXPECTED_LOCK_IDENTITY:
        _fail("FT04 lock identity/status is invalid")
    b_access = lock.get("b_access") or {}
    if b_access.get("state") != "locked" or \
            b_access.get("b_data_read") is not False or \
            b_access.get("b_outcome_read") is not False or \
            b_access.get("ft06_executed") is not False:
        _fail("FT04 lock does not keep B outcome access locked")
    formal_state = lock.get("formal_lock_at_freeze") or {}
    if formal_state.get("exists") is not False:
        _fail("FT04 lock records a formal model lock")
    if lock.get("formal_lock_path") != \
            "prognosis_analysis/model_freeze_lock.json":
        _fail("FT04 formal lock path binding is invalid")
    return lock


def _validate_scientific_amendment():
    text = _read_text(FT05A_AMENDMENT_PATH,
                      "FT05A scientific freeze amendment")
    if "SCIENTIFICALLY_FROZEN_WITH_ENGINEERING_FINALIZATION_EXCEPTION" not in text:
        _fail("FT05A scientific freeze amendment is not active")
    for value, label in (
            (FT05A_TABLE_RELATIVE_PATH, "FT05A table path"),
            (FT05A_MANIFEST_RELATIVE_PATH, "FT05A manifest path"),
            (EXPECTED_TABLE_SHA256, "FT05A table hash"),
            (EXPECTED_MANIFEST_SHA256, "FT05A manifest hash"),
            (EXPECTED_COMPLETION_EVIDENCE_SHA256, "completion evidence hash"),
            (EXPECTED_ROW_SCHEMA_SHA256, "row-schema hash"),
            (EXPECTED_LOCK_IDENTITY, "FT04 lock identity"),
            (EXPECTED_FT05A_RUN_IDENTITY, "FT05A run identity")):
        if value not in text:
            _fail("FT05A amendment is not bound to %s" % label)
    if "Completed unique B cases | `163/163`" not in text:
        _fail("FT05A amendment does not bind 163/163 unique B cases")


def _validate_technical_audit(manifest):
    text = _read_text(FT05A_TECHNICAL_AUDIT_PATH,
                      "FT05A accepted technical audit")
    if re.search(r"(?im)^\s*status\s*:\s*accepted\s*$", text) is None or \
            re.search(r"(?im)^\s*independent review\s*:\s*true\s*$", text) is None or \
            re.search(r"(?im)^\s*verdict\s*:\s*PASS\s*$", text) is None:
        _fail("FT05A technical audit is not accepted/PASS")
    expected = {
        "FT05A run identity SHA-256": EXPECTED_FT05A_RUN_IDENTITY,
        "FT05A cohort SHA-256": EXPECTED_FT05A_COHORT_SHA256,
        "FT05A case-completion evidence SHA-256": EXPECTED_COMPLETION_EVIDENCE_SHA256,
        "FT04 lock identity SHA-256": EXPECTED_LOCK_IDENTITY,
        "FT05A row-schema SHA-256": EXPECTED_ROW_SCHEMA_SHA256,
        "W_Original asset SHA-256": EXPECTED_W_ASSET_SHA256,
        "W_Original order SHA-256": EXPECTED_W_ORDER_SHA256,
    }
    for label, value in expected.items():
        if _marker(text, label) != value:
            _fail("FT05A technical audit %s mismatch" % label)
    if not re.search(r"(?im)^\s*technical case count\s*:\s*163\s*$", text):
        _fail("FT05A technical audit case count is not 163")
    for label, value in (("Outcome-blind", "true"),
                         ("Outcome accessed", "false"),
                         ("B K-means fit", "false"),
                         ("W_Original reused", "true"),
                         ("Repeat extraction", "false")):
        if re.search(r"(?im)^\s*%s\s*:\s*%s\s*$" % (
                re.escape(label), re.escape(value)), text) is None:
            _fail("FT05A technical audit safety marker %s is invalid" % label)
    if manifest.get("reviews", {}).get("technical_audit", {}).get(
            "sha256") != _sha256_file(FT05A_TECHNICAL_AUDIT_PATH):
        _fail("FT05A manifest technical-audit hash mismatch")


def _expected_technical_columns():
    columns = list(ft05a._technical_feature_columns(include_split=True))
    if _sha256_text(_canonical_json(columns)) != EXPECTED_ROW_SCHEMA_SHA256:
        _fail("FT05A technical row-schema implementation hash mismatch")
    return columns


def _validate_manifest(lock, unlock):
    _require_exact_path(FT05A_MANIFEST_PATH,
                        _project_path(FT05A_MANIFEST_RELATIVE_PATH,
                                      "FT05A manifest"),
                        "FT05A manifest")
    if not os.path.isfile(FT05A_MANIFEST_PATH):
        _fail("ignored FT05A .finalize manifest is missing")
    manifest_hash = _sha256_file(FT05A_MANIFEST_PATH)
    _require_sha(manifest_hash, EXPECTED_MANIFEST_SHA256,
                 "FT05A manifest bytes")
    _require_sha(unlock.get("feature_manifest_sha256"), manifest_hash,
                 "FT_B_unlock manifest")
    manifest = _read_json(FT05A_MANIFEST_PATH, "FT05A feature manifest")
    if manifest.get("artifact_id") != "FT05_B_feature_manifest" or \
            manifest.get("schema_version") != "1.0" or \
            manifest.get("stage") != "FT05A" or \
            manifest.get("status") != "frozen" or \
            manifest.get("purpose") != \
            "technical_only_outcome_blind_B_feature_table":
        _fail("FT05A manifest is not frozen technical-only output")
    if manifest.get("ft04_lock_identity_sha256") != \
            lock.get("lock_identity_sha256") or \
            manifest.get("run_identity") != EXPECTED_FT05A_RUN_IDENTITY:
        _fail("FT05A manifest is not bound to FT04/run identity")
    if manifest.get("technical_schema") != {
            "clinical_predictors_included": False,
            "clinical_predictors_join_stage": "authorized_outcome_stage"}:
        _fail("FT05A manifest technical schema is invalid")
    expected_hashes = lock.get("prediction_contract", {}).get(
        "expected_model_input_hashes")
    if manifest.get("model_input_hashes") != expected_hashes:
        _fail("FT05A model-input hash binding is invalid")

    completion = manifest.get("completion") or {}
    if completion.get("completed_case_count") != 163 or \
            completion.get("table_sha256") != EXPECTED_TABLE_SHA256 or \
            completion.get("case_completion_evidence_hash") != \
            EXPECTED_COMPLETION_EVIDENCE_SHA256:
        _fail("FT05A completion evidence is invalid")
    if manifest.get("run_identity") != unlock.get("ft05a_run_identity_sha256"):
        _fail("FT_B_unlock run identity binding is invalid")

    table_record = manifest.get("feature_table") or {}
    if table_record.get("path") != FT05A_DECLARED_TABLE_RELATIVE_PATH or \
            table_record.get("format") != "csv" or \
            table_record.get("complete") is not True or \
            table_record.get("row_count") != 163 or \
            table_record.get("patient_count") != 163 or \
            table_record.get("patient_id_column") != "patient_id" or \
            table_record.get("patient_ids_unique") is not True or \
            table_record.get("duplicate_patient_count") != 0 or \
            table_record.get("duplicate_extraction_count") != 0 or \
            table_record.get("extraction_count") != 163 or \
            table_record.get("sha256") != EXPECTED_TABLE_SHA256:
        _fail("FT05A table metadata is not the frozen technical contract")

    blocks = manifest.get("feature_blocks") or {}
    if set(blocks) != {"R_low", "R_high", "W_Original"}:
        _fail("FT05A feature-block set is invalid")
    for block, names, count, digest in (
            ("R_low", ft05a.R_LOW_FEATURE_NAMES, 49,
             EXPECTED_R_LOW_CANDIDATE_SHA256),
            ("R_high", ft05a.R_HIGH_FEATURE_NAMES, 10,
             EXPECTED_R_HIGH_CANDIDATE_SHA256)):
        record = blocks.get(block) or {}
        if record.get("feature_names") != list(names) or \
                record.get("count") != count or \
                record.get("candidate_hash") != digest:
            _fail("FT05A %s candidate/order contract mismatch" % block)
    w_record = blocks.get("W_Original") or {}
    frozen_w = lock.get("habitat_definition", {}).get("W_Original_asset") or {}
    if w_record.get("feature_names") != list(ft05a.W_ORIGINAL_FEATURE_NAMES) or \
            w_record.get("count") != 107 or \
            w_record.get("order_sha256") != EXPECTED_W_ORDER_SHA256 or \
            w_record.get("asset_sha256") != EXPECTED_W_ASSET_SHA256 or \
            w_record.get("reused_existing_asset") is not True or \
            w_record.get("reextracted") is not False or \
            w_record.get("asset_path") != frozen_w.get("path"):
        _fail("FT05A W_Original reuse/order contract mismatch")
    w_asset_path = _project_path(w_record.get("asset_path"),
                                 "FT05A W_Original asset")
    if not os.path.isfile(w_asset_path) or \
            _sha256_file(w_asset_path) != EXPECTED_W_ASSET_SHA256:
        _fail("FT05A W_Original asset hash mismatch")

    boundary = manifest.get("frozen_a_full_boundary") or {}
    expected_source_hashes = {
        key: (lock.get("provenance", {}).get("sources", {}).get(key) or {})
        .get("sha256")
        for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                    "w03_candidate_freeze")}
    if boundary.get("definition") != "accepted frozen full_A habitat" or \
            boundary.get("lock_identity_sha256") != lock.get("lock_identity_sha256") or \
            boundary.get("identity_sha256") != ft04._frozen_a_boundary_identity(lock) or \
            boundary.get("K") != 2 or boundary.get("n_init") != 100 or \
            boundary.get("no_refit") is not True or \
            boundary.get("source_hashes") != expected_source_hashes:
        _fail("FT05A frozen A-full boundary binding is invalid")
    if manifest.get("pyradiomics_provenance") != \
            lock.get("provenance", {}).get("pyradiomics") or \
            manifest.get("pyradiomics_matches_A_W03") is not True:
        _fail("FT05A PyRadiomics provenance binding is invalid")
    generation = manifest.get("generation") or {}
    required_false = (
        "outcome_accessed", "b_kmeans_fit", "repeat_extraction",
        "duplicate_extraction", "checkpoint_resume_repeated_extraction",
        "whole_tumor_reextraction", "formal_directory_mixing",
        "preprocessing_estimation")
    if generation.get("outcome_blind") is not True or \
            generation.get("one_time_first_extraction") is not True or \
            generation.get("projection") != "direct_frozen_A_full_boundary" or \
            generation.get("w_original_reused") is not True or \
            any(generation.get(key) is not False for key in required_false):
        _fail("FT05A generation safety contract is invalid")

    cohort = manifest.get("technical_cohort") or {}
    ordered_rows = cohort.get("ordered_rows") or []
    if cohort.get("row_count") != 163 or cohort.get("patient_count") != 163 or \
            cohort.get("patient_ids_unique") is not True or len(ordered_rows) != 163 or \
            cohort.get("source_frame_sha256") != EXPECTED_FT05A_COHORT_SHA256:
        _fail("FT05A technical cohort evidence is invalid")
    allowed_ids = []
    for record in ordered_rows:
        identifier = str(record.get("patient_id", "")).strip()
        if not identifier or record.get("split") != "B" or identifier in allowed_ids:
            _fail("FT05A technical cohort has invalid B identity/order")
        allowed_ids.append(identifier)
    if cohort.get("patient_id_hash") != _sha256_text("\n".join(allowed_ids)):
        _fail("FT05A technical cohort patient-order hash mismatch")
    _validate_technical_audit(manifest)
    return manifest, tuple(allowed_ids), manifest_hash


def _parse_float(value, label, allow_blank=False):
    text = "" if value is None else str(value).strip()
    if not text and allow_blank:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        _fail("%s is not numeric" % label)
    if not math.isfinite(number):
        _fail("%s is not finite" % label)
    return number


def _validate_feature_table(manifest, allowed_ids, unlock):
    _require_exact_path(FT05A_TABLE_PATH,
                        _project_path(FT05A_TABLE_RELATIVE_PATH,
                                      "FT05A table"),
                        "FT05A table")
    if not os.path.isfile(FT05A_TABLE_PATH):
        _fail("ignored FT05A .finalize feature table is missing")
    table_hash = _sha256_file(FT05A_TABLE_PATH)
    _require_sha(table_hash, EXPECTED_TABLE_SHA256, "FT05A table bytes")
    _require_sha(unlock.get("feature_table_sha256"), table_hash,
                 "FT_B_unlock table")
    columns = _expected_technical_columns()
    seen = []
    with open(FT05A_TABLE_PATH, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != columns:
            _fail("FT05A technical table schema/order mismatch")
        for row_number, row in enumerate(reader, 2):
            if None in row or any(row.get(column) is None for column in columns):
                _fail("FT05A technical table has malformed row %d" % row_number)
            identifier = str(row.get("patient_id", "")).strip()
            if not identifier or identifier in seen or identifier not in allowed_ids:
                _fail("FT05A technical table B identity/order mismatch")
            if len(seen) >= len(allowed_ids) or identifier != allowed_ids[len(seen)]:
                _fail("FT05A technical table row order mismatch")
            if str(row.get("split", "")).strip().upper() != "B":
                _fail("FT05A technical table contains a non-B row")
            r_low_available = _parse_float(
                row.get("R_low_technically_available"),
                "R_low_technically_available")
            r_high_available = _parse_float(
                row.get("R_high_technically_available"),
                "R_high_technically_available")
            w_available = _parse_float(
                row.get("W_Original_available"), "W_Original_available")
            for value, label in ((r_low_available, "R_low_technically_available"),
                                 (r_high_available, "R_high_technically_available"),
                                 (w_available, "W_Original_available")):
                if value not in (0.0, 1.0):
                    _fail("%s is not a binary availability marker" % label)
            if w_available != 1.0:
                _fail("W_Original is not available for every B technical row")
            for column in columns[2:]:
                if column in ("R_low_technically_available",
                              "R_high_technically_available",
                              "W_Original_available"):
                    continue
                is_r_low = column.startswith("R_low__")
                is_r_high = column.startswith("R_high__")
                allow_blank = (is_r_low and r_low_available == 0.0) or \
                    (is_r_high and r_high_available == 0.0)
                _parse_float(row.get(column), column, allow_blank=allow_blank)
            seen.append(identifier)
    if len(seen) != 163 or tuple(seen) != tuple(allowed_ids):
        _fail("FT05A technical table does not contain exactly 163 ordered B rows")
    return table_hash


def _validate_unlock(lock, manifest_hash, table_hash):
    if not os.path.isfile(FT_B_UNLOCK_PATH):
        _fail("FT_B_unlock.json is missing")
    unlock = _read_json(FT_B_UNLOCK_PATH, "FT_B_unlock.json")
    if unlock.get("schema_version") != "1.0" or \
            unlock.get("artifact_id") != "FT_B_unlock" or \
            unlock.get("status") != "authorized" or \
            unlock.get("unlock") is not True or \
            unlock.get("outcome_access") is not True or \
            unlock.get("ft_stage") != FT05B_STAGE or \
            unlock.get("scope") != "FT06 prediction/evaluation only":
        _fail("FT_B_unlock status/scope is invalid")
    if unlock.get("ft_label") != FT_LABEL or \
            unlock.get("ft04_lock_identity_sha256") != \
            lock.get("lock_identity_sha256") or \
            unlock.get("ft05a_run_id") != EXPECTED_FT05A_RUN_ID or \
            unlock.get("ft05a_run_identity_sha256") != EXPECTED_FT05A_RUN_IDENTITY or \
            unlock.get("ft05a_cohort_sha256") != EXPECTED_FT05A_COHORT_SHA256:
        _fail("FT_B_unlock FT04/FT05A identity binding is invalid")
    if unlock.get("feature_manifest_path") != FT05A_MANIFEST_RELATIVE_PATH or \
            unlock.get("feature_table_path") != FT05A_TABLE_RELATIVE_PATH:
        _fail("FT_B_unlock does not use the ignored .finalize assets")
    if unlock.get("feature_manifest_sha256") != manifest_hash or \
            unlock.get("ft05_manifest_sha256") != manifest_hash or \
            unlock.get("feature_table_sha256") != table_hash or \
            unlock.get("completion_evidence_sha256") != EXPECTED_COMPLETION_EVIDENCE_SHA256 or \
            unlock.get("row_schema_sha256") != EXPECTED_ROW_SCHEMA_SHA256:
        _fail("FT_B_unlock asset/schema hash binding is invalid")
    if unlock.get("candidate_hashes") != {
            "R_low": EXPECTED_R_LOW_CANDIDATE_SHA256,
            "R_high": EXPECTED_R_HIGH_CANDIDATE_SHA256}:
        _fail("FT_B_unlock candidate hashes are invalid")
    if unlock.get("W_Original") != {
            "count": 107, "asset_sha256": EXPECTED_W_ASSET_SHA256,
            "order_sha256": EXPECTED_W_ORDER_SHA256,
            "reused_existing_asset": True, "reextracted": False}:
        _fail("FT_B_unlock W_Original binding is invalid")
    if unlock.get("technical_audit_sha256") != \
            _sha256_file(FT05A_TECHNICAL_AUDIT_PATH):
        _fail("FT_B_unlock technical-audit hash is invalid")
    if unlock.get("B_data_read_before_unlock") is not False or \
            unlock.get("B_outcome_read_before_unlock") is not False:
        _fail("FT_B_unlock contains a prior B access claim")
    if set(unlock.get("prohibitions") or ()) != set(PROHIBITED_OPERATIONS):
        _fail("FT_B_unlock prohibition scope is incomplete")
    source_commit = unlock.get("source_commit")
    if not isinstance(source_commit, str) or \
            not re.match(r"^[0-9a-f]{40}$", source_commit):
        _fail("FT_B_unlock source commit is invalid")
    if source_commit != HISTORICAL_ACCESS_SOURCE_COMMIT:
        _fail("FT_B_unlock source commit does not match historical access provenance")
    if not _git_commit_resolves(source_commit):
        _fail("FT_B_unlock source commit does not resolve to a Git commit object")
    return unlock, _sha256_file(FT_B_UNLOCK_PATH)


def _build_context():
    lock = _validate_ft04_lock()
    _validate_scientific_amendment()
    unlock = _read_json(FT_B_UNLOCK_PATH, "FT_B_unlock.json") \
        if os.path.isfile(FT_B_UNLOCK_PATH) else {}
    manifest, allowed_ids, manifest_hash = _validate_manifest(lock, unlock)
    table_hash = _validate_feature_table(manifest, allowed_ids, unlock)
    unlock, unlock_hash = _validate_unlock(lock, manifest_hash, table_hash)
    summary = {
        "status": "AUTHORIZED",
        "ft_stage": FT05B_STAGE,
        "scope": "FT06 prediction/evaluation only",
        "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
        "feature_manifest_sha256": manifest_hash,
        "feature_table_sha256": table_hash,
        "ft_b_unlock_sha256": unlock_hash,
        "source_commit": unlock["source_commit"],
        "technical_case_count": len(allowed_ids),
        "requested_columns": list(B_OUTCOME_COLUMNS),
        "patient_level_frame_persisted": False,
        "b_data_read_before_unlock": False,
        "access_after_unlock": False,
        "ft06_executed": False,
    }
    return _GateContext(summary, allowed_ids)


def validate_ft05b_gate():
    """Validate authorization without touching the B outcome source."""
    return dict(_build_context().summary)


def _iso_timestamp():
    zone = datetime.timezone(datetime.timedelta(hours=8))
    return datetime.datetime.now(zone).isoformat(timespec="seconds")


def _write_receipt(path, receipt):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        _fail("receipt directory is missing")
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(receipt, handle, ensure_ascii=False, indent=2,
                      sort_keys=False)
            handle.write("\n")
    except (IOError, OSError, TypeError, ValueError, UnicodeError) as exc:
        _fail("cannot write FT05B unlock receipt: %s" % exc)


def read_b_dfs(outcome_path=None, receipt_path=None):
    """Read exactly the frozen DFS columns after the FT-specific gate.

    The source frame exists only during this call.  The public return value
    and receipt contain aggregate counts, never patient-level rows or values.
    A receipt already present is a hard stop to prevent a second controlled
    access from being mistaken for the first access.
    """
    receipt_path = FT05B_RECEIPT_PATH if receipt_path is None else receipt_path
    _require_exact_path(receipt_path, FT05B_RECEIPT_PATH,
                        "FT05B unlock receipt")
    context = _build_context()
    outcome_path = OUTCOME_SOURCE_PATH if outcome_path is None else outcome_path
    _require_exact_path(outcome_path, OUTCOME_SOURCE_PATH,
                        "B outcome source")
    if os.path.isfile(receipt_path):
        _fail("FT05B unlock receipt already exists; repeated outcome access is refused")
    if not os.path.isfile(outcome_path):
        _fail("B outcome source is missing")
    try:
        outcome = data_split_guard._authorized_read(
            outcome_path, None, set(context.allowed_ids), "影像号", False,
            usecols=list(B_OUTCOME_COLUMNS))
    except Exception as exc:
        _fail("B DFS source read failed: %s" % exc)
    if list(outcome.columns) != list(B_OUTCOME_COLUMNS):
        _fail("B DFS reader returned columns outside the frozen three-column schema")
    identifiers = outcome["影像号"].astype(str).str.strip()
    if identifiers.eq("").any() or identifiers.duplicated().any() or \
            set(identifiers) != set(context.allowed_ids):
        _fail("B DFS reader returned incomplete or non-unique authorized rows")
    times = []
    events = []
    for value in outcome["DFS_time"]:
        number = _parse_float(value, "DFS_time")
        if number <= 0:
            _fail("DFS_time must be positive")
        times.append(number)
    for value in outcome["DFS_event"]:
        number = _parse_float(value, "DFS_event")
        if number not in (0.0, 1.0):
            _fail("DFS_event must be binary")
        events.append(int(number))
    timestamp = _iso_timestamp()
    aggregate = {
        "row_count": int(len(outcome)),
        "unique_identifier_count": int(len(set(identifiers))),
        "event_count": int(sum(events)),
        "censor_count": int(len(events) - sum(events)),
    }
    del outcome
    receipt = {
        "schema_version": "1.0",
        "artifact_id": "FT05B_unlock_receipt",
        "status": "validated",
        "ft_stage": FT05B_STAGE,
        "scope": "FT06 prediction/evaluation only",
        "ft04_lock_identity_sha256": context.summary[
            "ft04_lock_identity_sha256"],
        "ft05a_manifest_sha256": context.summary["feature_manifest_sha256"],
        "ft05a_table_sha256": context.summary["feature_table_sha256"],
        "ft_b_unlock_sha256": context.summary["ft_b_unlock_sha256"],
        "unlock_committed_before_access": True,
        "unlock_validated_before_access": True,
        "access_timestamp": timestamp,
        "reader_entry": (
            "ft05b_runner.read_b_dfs -> "
            "data_split_guard._authorized_read"),
        "requested_columns": list(B_OUTCOME_COLUMNS),
        "aggregate": aggregate,
        "patient_level_frame_persisted": False,
        "b_data_read_before_unlock": False,
        "access_after_unlock": True,
        "ft06_executed": False,
        "source_commit": context.summary["source_commit"],
    }
    _write_receipt(receipt_path, receipt)
    result = dict(context.summary)
    result.update({
        "access_timestamp": timestamp,
        "aggregate": dict(aggregate),
        "access_after_unlock": True,
    })
    return result


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("validate", "read"):
        raise SystemExit("usage: ft05b_runner.py validate|read")
    if sys.argv[1] == "validate":
        print(json.dumps(validate_ft05b_gate(), ensure_ascii=False,
                         sort_keys=True))
    else:
        print(json.dumps(read_b_dfs(), ensure_ascii=False, sort_keys=True))
