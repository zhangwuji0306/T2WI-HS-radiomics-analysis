"""Outcome-blind FT05A B technical generation.

The runner has one narrow responsibility: after the accepted FT04 freeze and
independent code audit, create the B technical habitat-radiomics table once.
Only image, ROI, and the already accepted W_Original technical asset are
read.  Clinical and endpoint inputs are rejected at the input boundary.

The public entry point accepts a small technical case processor.  The default
processor is included for the production path; tests can inject a synthetic
processor without opening an image or a W_Original asset.
"""
from __future__ import absolute_import

import argparse
import ast
import csv
import copy
import hashlib
import json
import os
import platform
import re
import sys
import time
import uuid
from collections import OrderedDict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import ft02_runner as ft02  # noqa: E402
import ft04_runner as ft04  # noqa: E402


FT05A_STAGE = "FT05A"
FT05A_SCHEMA_VERSION = "1.0"
FT_LABEL = "exploratory_fullA_habitat_non_nested_validation"
TECHNICAL_AUDIT_PENDING_STATUS = "generated_pending_review"
TECHNICAL_AUDIT_PENDING_VERDICT = "PENDING_REVIEW"
TECHNICAL_COMPLETE_PENDING_REVIEW = "TECHNICAL_COMPLETE_PENDING_REVIEW"
FT05A_CODE_PREP_CONTRACT_IDENTITY = "FT05A_code_prep_contract_v1"
FT05A_IDENTITY_MIGRATION_REASON = (
    "reviewed FT05A code/audit remediation continuation")
IDENTITY_PAYLOAD_FIELDS = frozenset((
    "artifact", "run_id", "ft04_lock_identity_sha256", "cohort_sha256",
    "candidate_hashes", "w_original_order_sha256", "w_original_asset_path",
    "w_original_asset_sha256", "code_audit_sha256", "output_root"))
MINIMUM_ROI_SIZE = 10
CANONICAL_OUTPUT_ROOT = os.path.abspath(os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3",
    "FT05A"))
DEFAULT_OUTPUT_ROOT = CANONICAL_OUTPUT_ROOT
DEFAULT_TECHNICAL_SOURCE_ROOT = os.path.join(DEFAULT_OUTPUT_ROOT, "sources")
DEFAULT_MANIFEST = os.path.join(_HERE, "FT05_B_feature_manifest.json")
DEFAULT_TECHNICAL_AUDIT = os.path.join(
    _HERE, "FT05A_B_technical_generation_audit.md")
DEFAULT_CODE_AUDIT = os.path.join(_HERE, "FT05A_code_audit.md")
DEFAULT_RUN_STATE = os.path.join(DEFAULT_OUTPUT_ROOT, "FT05A_run_state.json")
DEFAULT_CASE_ROOT = os.path.join(DEFAULT_OUTPUT_ROOT, "cases")
DEFAULT_FEATURE_TABLE = os.path.join(
    DEFAULT_OUTPUT_ROOT, "FT05A_B_technical_features.csv")
DEFAULT_LOCK = os.path.join(_HERE, "FT_model_freeze_lock.json")
DEFAULT_FT01_MANIFEST = os.path.join(_HERE, "FT01_asset_manifest.json")
DEFAULT_HABITAT_CONFIG = os.path.join(
    _PROJECT_ROOT, "habitat_analysis", "configs",
    "main_cross_case_kmeans_k2_4mm.json")
DEFAULT_W03_CONFIG = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "configs",
    "w03_habitat_radiomics.json")
FORMAL_MODEL_LOCK = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "model_freeze_lock.json")
DEFAULT_HABITAT_FREEZE = os.path.join(
    _PROJECT_ROOT, "habitat_analysis", "freeze_lock.json")
ASCII_ROOT = os.path.join(os.path.dirname(_PROJECT_ROOT), "radiomics26")

R_LOW_CANDIDATE_HASH = (
    "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0")
R_HIGH_CANDIDATE_HASH = (
    "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce")
W_ORIGINAL_ORDER_SHA256 = ft02.W_ORIGINAL_ORDER_SHA256

TECHNICAL_INPUT_COLUMNS = frozenset((
    "patient_id", "split", "image_path", "roi_path",
    "source_image_key", "source_roi_key", "w_original_path"))
PATH_INPUT_COLUMNS = frozenset(("image_path", "roi_path", "w_original_path"))
OUTCOME_COLUMN_MARKERS = frozenset((
    "dfs", "pfs", "os", "outcome", "clinical", "prognosis",
    "survival", "event", "censor", "followup", "endpoint", "response",
    "death", "risk", "time", "status"))
FORMAL_PATH_MARKERS = ("/formal/", "/w08/", "/l9/", "model_freeze_lock",
                       "execution_status", "modeling_protocol")
ALLOWED_TECHNICAL_ROOTS = (DEFAULT_TECHNICAL_SOURCE_ROOT,)
DISALLOWED_ROOTS = (
    os.path.join(_PROJECT_ROOT, "feature_extract", "output"),
    os.path.join(_PROJECT_ROOT, "habitat_analysis", "output"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "modeling_v2"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT01"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT02"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT03"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT04"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "W08"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "L9"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "w08_nested_cv"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "l9"),
    os.path.join(_PROJECT_ROOT, "prognosis_analysis", "model_freeze_lock.json"),
)

GLOBAL_COLUMNS = tuple(ft02.GLOBAL_COLUMNS)
R_LOW_FEATURE_NAMES = tuple(ft02.R_LOW_FEATURE_NAMES)
R_HIGH_FEATURE_NAMES = tuple(ft02.R_HIGH_FEATURE_NAMES)
W_ORIGINAL_FEATURE_NAMES = tuple(ft02.W_ORIGINAL_FEATURE_NAMES)
BLOCK_PREFIXES = {"R_low": "R_low__", "R_high": "R_high__",
                  "W_Original": "W__"}


class FT05AValidationError(ValueError):
    """Raised for a fail-closed FT05A contract violation."""


class FT05ARunError(RuntimeError):
    """Raised when a technical case or finalization fails."""


_PREFLIGHT_TOKEN = object()


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value):
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        if not np.isfinite(value):
            raise FT05AValidationError("non-finite value cannot enter an artifact")
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise FT05AValidationError("non-finite value cannot enter an artifact")
    return value


def _read_json(path, label="JSON artifact"):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise FT05AValidationError("cannot read %s: %s" % (label, exc))


def _write_json_atomic(path, payload, refuse_existing=False):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    raw = (json.dumps(_json_safe(payload), ensure_ascii=False, indent=2,
                      sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    if refuse_existing and os.path.exists(path):
        with open(path, "rb") as handle:
            if handle.read() != raw:
                raise FT05AValidationError("refusing to overwrite existing artifact: %s" % path)
        return
    temporary = "%s.tmp.%s" % (path, uuid.uuid4().hex)
    try:
        with open(temporary, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _write_text_atomic(path, text, refuse_existing=False):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    raw = text.encode("utf-8")
    if refuse_existing and os.path.exists(path):
        with open(path, "rb") as handle:
            if handle.read() != raw:
                raise FT05AValidationError(
                    "refusing to overwrite existing artifact: %s" % path)
        return
    temporary = "%s.tmp.%s" % (path, uuid.uuid4().hex)
    try:
        with open(temporary, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _relative(path):
    return os.path.relpath(os.path.abspath(path), _PROJECT_ROOT).replace("\\", "/")


def _ascii_path(path):
    """Route local SimpleITK reads through the configured ASCII junction."""
    absolute = os.path.abspath(path if os.path.isabs(path)
                               else os.path.join(_PROJECT_ROOT, path))
    project = os.path.abspath(_PROJECT_ROOT)
    if absolute.lower().startswith((project + os.sep).lower()):
        return os.path.join(ASCII_ROOT, absolute[len(project) + 1:])
    return absolute


def _absolute_project_path(path, label):
    if not isinstance(path, str) or not path.strip():
        raise FT05AValidationError("%s is blank" % label)
    if os.path.isabs(path):
        raise FT05AValidationError("%s must be a relative project path" % label)
    normalized = path.replace("\\", "/")
    candidate = os.path.realpath(os.path.join(_PROJECT_ROOT, normalized))
    project = os.path.realpath(_PROJECT_ROOT)
    if os.path.commonpath([candidate, project]) != project:
        raise FT05AValidationError("%s escapes the project root" % label)
    return candidate


def _contains_formal_path(value):
    lowered = str(value).replace("\\", "/").lower().strip("/")
    segments = set(lowered.split("/"))
    if segments.intersection(("formal", "w08", "l9", "ft01", "ft02",
                             "ft03", "ft04", "w08_nested_cv")):
        return True
    wrapped = "/" + lowered + "/"
    return any(marker in wrapped for marker in FORMAL_PATH_MARKERS)


def _is_outcome_name(value):
    text = str(value).lower()
    lowered = re.sub(r"[^a-z0-9]+", "", text)
    strong_markers = OUTCOME_COLUMN_MARKERS - {
        "os", "event", "censor", "followup", "risk", "time", "status"}
    if any(marker in lowered for marker in strong_markers):
        return True
    tokens = set(re.split(r"[^a-z0-9]+", text))
    return bool(tokens.intersection({
        "os", "event", "censor", "followup", "risk", "time", "status"}))


def _is_contained(path, root):
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == \
            os.path.realpath(root)
    except ValueError:
        return False


def _validate_technical_path(value, label, allowed_roots=None,
                             exact_paths=()):
    path = _absolute_project_path(value, label)
    normalized = path.replace("\\", "/").lower()
    if _contains_formal_path(normalized):
        raise FT05AValidationError("%s is in a formal namespace" % label)
    exact = {os.path.realpath(item) for item in exact_paths}
    is_exact = os.path.realpath(path) in exact
    if not is_exact and any(_is_contained(path, root) for root in DISALLOWED_ROOTS):
        raise FT05AValidationError("%s is in a disallowed analysis namespace" % label)
    roots = tuple(allowed_roots or ALLOWED_TECHNICAL_ROOTS)
    allowed = is_exact or any(
        _is_contained(path, root) for root in roots)
    if not allowed:
        raise FT05AValidationError("%s is outside the technical path allowlist" % label)
    for root in roots:
        if _is_contained(path, root):
            suffix = os.path.relpath(path, os.path.realpath(root)).replace("\\", "/")
            if _is_outcome_name(suffix):
                raise FT05AValidationError("%s contains a forbidden clinical/endpoint path marker" % label)
            break
    return path


def _canonical_output_root(output_root):
    if not isinstance(output_root, str) or not os.path.isabs(output_root):
        raise FT05AValidationError(
            "FT05A output root must be the exact absolute canonical spelling")
    if output_root != CANONICAL_OUTPUT_ROOT:
        raise FT05AValidationError(
            "FT05A output root must be the exact canonical FT05A run root")
    resolved = os.path.realpath(output_root)
    canonical_resolved = os.path.realpath(CANONICAL_OUTPUT_ROOT)
    if os.path.normcase(resolved) != os.path.normcase(canonical_resolved):
        raise FT05AValidationError(
            "FT05A output root resolves outside the canonical FT05A run root")
    return CANONICAL_OUTPUT_ROOT


def _validate_namespace_path(path, label, output_root, allow_ft_namespace=False):
    canonical_output = _canonical_output_root(output_root)
    if label == "FT05A output root":
        return _canonical_output_root(path)
    if not isinstance(path, str):
        raise FT05AValidationError("%s must be a path string" % label)
    if os.path.isabs(path):
        absolute = os.path.realpath(path)
    else:
        absolute = _absolute_project_path(path, label)
    if _contains_formal_path(absolute):
        raise FT05AValidationError("%s is in a formal namespace" % label)
    output_root = os.path.realpath(canonical_output)
    ft_root = os.path.realpath(_HERE)
    in_output = _is_contained(absolute, output_root)
    in_ft = _is_contained(absolute, ft_root)
    canonical_artifacts = {
        os.path.normcase(os.path.realpath(DEFAULT_MANIFEST)),
        os.path.normcase(os.path.realpath(DEFAULT_CODE_AUDIT)),
        os.path.normcase(os.path.realpath(DEFAULT_TECHNICAL_AUDIT)),
        os.path.normcase(os.path.realpath(DEFAULT_FEATURE_TABLE)),
    }
    normalized_absolute = os.path.normcase(absolute)
    canonical_tracked_artifacts = {
        os.path.normcase(os.path.realpath(DEFAULT_MANIFEST)),
        os.path.normcase(os.path.realpath(DEFAULT_CODE_AUDIT)),
        os.path.normcase(os.path.realpath(DEFAULT_TECHNICAL_AUDIT)),
    }
    if normalized_absolute in canonical_tracked_artifacts and \
            path not in (DEFAULT_MANIFEST, DEFAULT_CODE_AUDIT,
                         DEFAULT_TECHNICAL_AUDIT):
        raise FT05AValidationError(
            "%s must use the exact canonical tracked artifact path" % label)
    if os.path.normcase(output_root) == os.path.normcase(canonical_output) and \
            in_output and normalized_absolute not in canonical_artifacts:
        raise FT05AValidationError(
            "%s must use the canonical FT05A artifact path" % label)
    if not in_output and not (allow_ft_namespace and
                              (in_ft and normalized_absolute in canonical_artifacts)):
        raise FT05AValidationError("%s is outside the FT local namespace" % label)
    return absolute


def _candidate_hash(names):
    return _sha256_text(json.dumps(list(names), ensure_ascii=False,
                                   separators=(",", ":")))


def _technical_feature_columns(include_split=True):
    columns = ["patient_id"]
    if include_split:
        columns.append("split")
    columns.extend(GLOBAL_COLUMNS)
    for block, names in (("R_low", R_LOW_FEATURE_NAMES),
                         ("R_high", R_HIGH_FEATURE_NAMES)):
        columns.extend([block + "_structurally_defined",
                        block + "_technically_available"])
        columns.extend(BLOCK_PREFIXES[block] + name for name in names)
    columns.append("W_Original_available")
    columns.extend(BLOCK_PREFIXES["W_Original"] + name
                   for name in W_ORIGINAL_FEATURE_NAMES)
    return columns


def _normalise_ids(series):
    values = series.astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise FT05AValidationError("technical cohort patient IDs are not unique and nonblank")
    return values


def _validate_technical_columns(columns):
    columns = list(columns)
    for column in columns:
        if _is_outcome_name(column):
            raise FT05AValidationError("technical input contains a forbidden clinical/endpoint column: %s" % column)
    unknown = sorted(set(columns) - TECHNICAL_INPUT_COLUMNS)
    if unknown:
        raise FT05AValidationError("technical input contains non-allowlisted columns: %s" % unknown)
    required = {"patient_id", "image_path", "roi_path"}
    missing = sorted(required - set(columns))
    if missing:
        raise FT05AValidationError("technical cohort is missing columns: %s" % missing)


def load_technical_cohort(cohort, _preflight=None, technical_source_roots=None,
                          accepted_w_path=None):
    """Load only the allowlisted technical cohort columns.

    Header validation occurs before the data frame is assembled.  No reader
    for clinical or endpoint data is reachable from this function.
    """
    if isinstance(cohort, pd.DataFrame):
        frame = cohort.copy()
    elif isinstance(cohort, (list, tuple)):
        frame = pd.DataFrame(list(cohort))
    elif isinstance(cohort, str):
        if _preflight is not _PREFLIGHT_TOKEN:
            raise FT05AValidationError(
                "technical cohort file loading requires a validated FT05A preflight")
        path = _validate_technical_path(
            cohort, "technical cohort", allowed_roots=technical_source_roots)
        try:
            header = list(pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns)
        except (IOError, OSError, ValueError) as exc:
            raise FT05AValidationError("cannot read technical cohort header: %s" % exc)
        _validate_technical_columns(header)
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype=str,
                            usecols=header)
    else:
        raise FT05AValidationError("technical cohort must be a DataFrame, records, or CSV path")
    _validate_technical_columns(frame.columns)
    frame = frame.copy()
    if frame.empty:
        raise FT05AValidationError("technical cohort is empty")
    frame["patient_id"] = _normalise_ids(frame["patient_id"])
    if "split" in frame.columns:
        split = frame["split"].astype(str).str.strip().str.upper()
        if not split.eq("B").all():
            raise FT05AValidationError("technical cohort contains a non-B split")
    else:
        frame["split"] = "B"
    for column in PATH_INPUT_COLUMNS:
        if column not in frame.columns:
            continue
        values = frame[column].astype(str).str.strip()
        if values.eq("").any():
            raise FT05AValidationError("technical source paths are blank: %s" % column)
        exact_paths = (accepted_w_path,) if column == "w_original_path" and \
            accepted_w_path else ()
        checked = [_validate_technical_path(
            value, column, allowed_roots=technical_source_roots,
            exact_paths=exact_paths) for value in values]
        frame[column] = [os.path.relpath(path, _PROJECT_ROOT).replace("\\", "/")
                         for path in checked]
    image_keys = frame.get("source_image_key", frame["image_path"]).astype(str).str.strip()
    roi_keys = frame.get("source_roi_key", frame["roi_path"]).astype(str).str.strip()
    if image_keys.duplicated().any() or roi_keys.duplicated().any() or \
            pd.DataFrame({"image": image_keys, "roi": roi_keys}).duplicated().any():
        raise FT05AValidationError("technical cohort contains duplicate source mappings")
    frame["source_image_key"] = image_keys
    frame["source_roi_key"] = roi_keys
    return frame.reset_index(drop=True)


def _canonical_frame_hash(frame):
    return _sha256_text(frame.to_csv(index=False, line_terminator="\n"))


def _w_original_header(path, binding):
    try:
        header = list(pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns)
    except (IOError, OSError, ValueError) as exc:
        raise FT05AValidationError("cannot read W_Original header: %s" % exc)
    id_column = "patient_id" if "patient_id" in header else \
        "影像号" if "影像号" in header else None
    if id_column is None or "split" not in header:
        raise FT05AValidationError(
            "W_Original asset lacks patient_id/影像号 and split schema")
    metadata_columns = set(header) - set(W_ORIGINAL_FEATURE_NAMES)
    allowed_metadata = {id_column, "patient_id", "影像号", "split", "reader", "读者",
                        "normalization", "f", "binWidth"}
    unknown_metadata = sorted(metadata_columns - allowed_metadata)
    if unknown_metadata or any(_is_outcome_name(column) for column in metadata_columns):
        raise FT05AValidationError("W_Original asset contains nontechnical columns")
    reader_column = "reader" if "reader" in header else \
        "读者" if "读者" in header else None
    selected = [id_column, "split"]
    if reader_column:
        selected.append(reader_column)
    selected.extend(W_ORIGINAL_FEATURE_NAMES)
    missing = sorted(set(selected) - set(header))
    if missing:
        raise FT05AValidationError(
            "W_Original asset is missing frozen columns: %s" % missing)
    return header, id_column, reader_column, selected


def _canonical_w_original_value(raw_value):
    """Convert one accepted CSV value to the canonical stored representation."""
    value = pd.to_numeric(pd.Series([raw_value]), errors="coerce").iloc[0]
    try:
        canonical = float(value)
    except (TypeError, ValueError, OverflowError):
        raise FT05AValidationError(
            "W_Original contains a malformed frozen value")
    if not np.isfinite(canonical):
        raise FT05AValidationError(
            "W_Original contains nonfinite frozen values")
    return canonical


def _w_original_rows_from_csv(path, id_column, reader_column, selected_ids=None):
    """Load canonical W_Original rows while preserving the pilot stream path.

    The CSV is scanned one physical record at a time.  With ``selected_ids``
    set, non-selected records are reduced to selector fields and are never
    converted, retained, or hashed.  The full load uses this same parser and
    canonical value representation for every accepted B/R1 row.
    """
    if selected_ids is not None:
        selected_ids = set(str(value).strip() for value in selected_ids)
    rows = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise FT05AValidationError("W_Original asset has no CSV header")
        if len(header) != len(set(header)):
            raise FT05AValidationError("W_Original asset header contains duplicate columns")
        indices = {name: index for index, name in enumerate(header)}
        required = [id_column, "split"] + ([reader_column] if reader_column else []) + \
            list(W_ORIGINAL_FEATURE_NAMES)
        if any(name not in indices for name in required):
            raise FT05AValidationError("W_Original asset row schema is incomplete")
        for fields in reader:
            if len(fields) != len(header):
                raise FT05AValidationError("W_Original asset contains a malformed CSV row")
            patient_id = str(fields[indices[id_column]]).strip()
            if selected_ids is not None and patient_id not in selected_ids:
                continue
            split = str(fields[indices["split"]]).strip().upper()
            if split != "B":
                continue
            if reader_column and str(fields[indices[reader_column]]).strip() not in ("R1", "1"):
                continue
            if not patient_id:
                raise FT05AValidationError(
                    "W_Original accepted B rows must have nonblank patient IDs")
            values = OrderedDict()
            for name in W_ORIGINAL_FEATURE_NAMES:
                values[name] = _canonical_w_original_value(
                    fields[indices[name]])
            if patient_id in rows:
                raise FT05AValidationError(
                    "W_Original accepted B rows are not unique")
            rows[patient_id] = values
    missing = sorted(selected_ids - set(rows)) if selected_ids is not None else []
    if missing:
        raise FT05AValidationError(
            "W_Original asset does not cover selected B rows: %s" % missing)
    return rows


def _load_w_original_asset(lock, path_override=None, selected_patient_ids=None):
    binding = (lock.get("habitat_definition") or {}).get("W_Original_asset") or {}
    expected_path = binding.get("path")
    expected_hash = binding.get("asset_sha256")
    if path_override is not None and path_override != expected_path:
        raise FT05AValidationError("W_Original path does not match the accepted FT01/FT04 asset")
    path = _validate_technical_path(
        expected_path, "accepted W_Original asset", exact_paths=(expected_path,))
    if binding.get("feature_count") != 107 or \
            binding.get("order_sha256") != W_ORIGINAL_ORDER_SHA256 or \
            binding.get("reused_existing_asset") is not True or \
            binding.get("reextracted") is not False:
        raise FT05AValidationError("accepted W_Original binding is invalid")
    if not os.path.isfile(path):
        raise FT05AValidationError("accepted W_Original asset is missing")
    if selected_patient_ids is None:
        if _sha256_file(path) != expected_hash:
            raise FT05AValidationError("accepted W_Original asset hash mismatch")
    _, id_column, reader_column, selected = _w_original_header(path, binding)
    if selected_patient_ids is not None:
        records = _w_original_rows_from_csv(
            path, id_column, reader_column, selected_patient_ids)
    else:
        records = _w_original_rows_from_csv(
            path, id_column, reader_column, selected_ids=None)
    return {
        "path": _relative(path),
        "sha256": expected_hash,
        "feature_count": 107,
        "order_sha256": W_ORIGINAL_ORDER_SHA256,
        "rows": records,
    }


def _git_current_blob_hash(relative_path):
    value = ft04._git_text(["hash-object", relative_path])
    return value if re.match(r"^[0-9a-f]{40}$", str(value or "")) else None


def _git_commit_blob_hash(commit, relative_path):
    value = ft04._git_text(["rev-parse", "%s:%s" % (commit, relative_path)])
    return value if re.match(r"^[0-9a-f]{40}$", str(value or "")) else None


def _git_paths_after(commit):
    text = ft04._git_text(["log", "--format=", "--name-only", "%s..HEAD" % commit])
    return [line.strip().replace("\\", "/") for line in (text or "").splitlines()
            if line.strip()]


def _audit_marker(text, label):
    pattern = r"(?im)^\s*%s\s*[:：]\s*`?([^`\r\n]+?)`?\s*$" % \
        re.escape(label)
    match = re.search(pattern, text)
    if not match:
        raise FT05AValidationError(
            "FT05A technical audit is missing the %s marker" % label)
    return match.group(1).strip()


def _technical_audit_fields(text):
    fields = {
        "status": _audit_marker(text, "Status").lower(),
        "independent": _audit_marker(text, "Independent review").lower(),
        "verdict": _audit_marker(text, "Verdict").upper(),
        "run_identity_sha256": _audit_marker(
            text, "FT05A run identity SHA-256"),
        "cohort_sha256": _audit_marker(text, "FT05A cohort SHA-256"),
        "case_completion_evidence_hash": _audit_marker(
            text, "FT05A case-completion evidence SHA-256"),
        "technical_case_count": _audit_marker(text, "Technical case count"),
        "ft04_lock_identity_sha256": _audit_marker(
            text, "FT04 lock identity SHA-256"),
        "code_audit_sha256": _audit_marker(text, "FT05A code-audit SHA-256"),
        "runner_sha256": _audit_marker(text, "FT05A runner SHA-256"),
        "w_original_asset_sha256": _audit_marker(
            text, "W_Original asset SHA-256"),
        "w_original_order_sha256": _audit_marker(
            text, "W_Original order SHA-256"),
        "row_schema_sha256": _audit_marker(
            text, "FT05A row-schema SHA-256"),
        "outcome_blind": _audit_marker(text, "Outcome-blind").lower(),
        "outcome_accessed": _audit_marker(text, "Outcome accessed").lower(),
        "b_kmeans_fit": _audit_marker(text, "B K-means fit").lower(),
        "w_original_reused": _audit_marker(
            text, "W_Original reused").lower(),
        "repeat_extraction": _audit_marker(
            text, "Repeat extraction").lower(),
    }
    for key in ("run_identity_sha256", "cohort_sha256",
                "case_completion_evidence_hash", "code_audit_sha256",
                "runner_sha256", "w_original_asset_sha256",
                "w_original_order_sha256", "row_schema_sha256"):
        if not re.match(r"^[0-9a-f]{64}$", fields[key]):
            raise FT05AValidationError(
                "FT05A technical audit %s is not a SHA-256" % key)
    try:
        fields["technical_case_count"] = int(fields["technical_case_count"])
    except (TypeError, ValueError):
        raise FT05AValidationError(
            "FT05A technical audit case count is invalid")
    if fields["technical_case_count"] < 1:
        raise FT05AValidationError(
            "FT05A technical audit case count is invalid")
    return fields


def _validate_code_audit(path):
    if not os.path.isfile(path):
        raise FT05AValidationError("accepted independent FT05A code audit is required")
    text = _read_text(path, "FT05A code audit")
    if not re.search(r"(?im)^\s*Independent\s+review\s*:\s*true\s*$", text):
        raise FT05AValidationError("FT05A code audit is not independent")
    if not re.search(r"(?im)^\s*(?:verdict|status)\s*[:：]\s*(?:PASS|PASS_WITH_FINDINGS|accepted)\s*$", text):
        raise FT05AValidationError("FT05A code audit has no accepted verdict")
    reviewed_match = re.search(
        r"(?im)^\s*Reviewed(?:\s+FT05A)?\s+implementation\s+commit\s*:\s*`?([0-9a-f]{40})`?\s*$",
        text)
    runner_match = re.search(
        r"(?im)^\s*(?:Current\s+)?(?:FT05A\s+)?runner\s+SHA-256\s*:\s*`?([0-9a-f]{64})`?\s*$",
        text)
    contract_match = re.search(
        r"(?im)^\s*FT05A\s+(?:(?:code[- ]?)?preparation\s+)?contract(?:\s+identity)?\s*:\s*`?([^`\r\n]+?)`?\s*$",
        text)
    current_commit = ft04._git_head()
    reviewed_commit = reviewed_match.group(1) if reviewed_match else None
    runner_relative = _relative(__file__)
    audit_relative = _relative(DEFAULT_CODE_AUDIT)
    if not reviewed_commit or not current_commit or \
            not ft04._git_commit_is_ancestor(reviewed_commit):
        raise FT05AValidationError(
            "FT05A code audit is not bound to an ancestor implementation commit")
    if _git_current_blob_hash(runner_relative) != \
            _git_commit_blob_hash(reviewed_commit, runner_relative):
        raise FT05AValidationError(
            "FT05A runner changed after the reviewed implementation commit")
    post_review_paths = _git_paths_after(reviewed_commit)
    if any(item != audit_relative for item in post_review_paths):
        raise FT05AValidationError(
            "only the canonical FT05A audit report may change after review")
    if current_commit != reviewed_commit and \
            os.path.realpath(path) != os.path.realpath(DEFAULT_CODE_AUDIT):
        raise FT05AValidationError(
            "post-review code audits must use the canonical tracked report")
    if not runner_match or runner_match.group(1) != _sha256_file(__file__):
        raise FT05AValidationError(
            "FT05A code audit is not bound to the exact runner SHA-256")
    if not contract_match or contract_match.group(1).strip() != \
            FT05A_CODE_PREP_CONTRACT_IDENTITY:
        raise FT05AValidationError(
            "FT05A code audit is not bound to the exact preparation contract")
    return {"path": _relative(path), "sha256": _sha256_file(path),
            "status": "accepted", "independent": True,
            "verdict": "PASS" if re.search(r"(?im)^\s*verdict\s*[:：]\s*PASS\s*$", text) else "PASS_WITH_FINDINGS",
            "reviewed_commit": reviewed_match.group(1),
            "runner_sha256": runner_match.group(1),
            "contract_identity": contract_match.group(1).strip()}


def _validate_technical_audit(path):
    if not os.path.isfile(path):
        raise FT05AValidationError("accepted independent FT05A technical audit is required")
    text = _read_text(path, "FT05A technical audit")
    fields = _technical_audit_fields(text)
    if fields["status"] != "accepted" or \
            fields["independent"] != "true":
        raise FT05AValidationError("FT05A technical audit is not independent")
    if fields["verdict"] not in ("PASS", "PASS_WITH_FINDINGS"):
        raise FT05AValidationError("FT05A technical audit has no accepted verdict")
    if fields["outcome_blind"] != "true" or \
            fields["outcome_accessed"] != "false" or \
            fields["b_kmeans_fit"] != "false" or \
            fields["w_original_reused"] != "true" or \
            fields["repeat_extraction"] != "false":
        raise FT05AValidationError(
            "FT05A technical audit safety evidence is invalid")
    if fields["runner_sha256"] != _sha256_file(__file__):
        raise FT05AValidationError(
            "FT05A technical audit is bound to a different runner")
    return {"path": _relative(path), "sha256": _sha256_file(path),
            "status": "accepted", "independent": True,
            "verdict": fields["verdict"],
            "run_identity_sha256": fields["run_identity_sha256"],
            "cohort_sha256": fields["cohort_sha256"],
            "case_completion_evidence_hash": fields[
                "case_completion_evidence_hash"],
            "technical_case_count": fields["technical_case_count"],
            "ft04_lock_identity_sha256": fields["ft04_lock_identity_sha256"],
            "code_audit_sha256": fields["code_audit_sha256"],
            "runner_sha256": fields["runner_sha256"],
            "w_original_asset_sha256": fields["w_original_asset_sha256"],
            "w_original_order_sha256": fields["w_original_order_sha256"],
            "row_schema_sha256": fields["row_schema_sha256"]}


def _technical_audit_expected(run_state, cohort, contract, w_asset,
                              code_audit):
    return {
        "run_identity_sha256": run_state["run_identity_sha256"],
        "cohort_sha256": run_state["identity_payload"]["cohort_sha256"],
        "case_completion_evidence_hash": _sha256_text(_canonical_json(
            run_state.get("completed_case_artifact_hashes", {}))),
        "technical_case_count": int(len(cohort)),
        "ft04_lock_identity_sha256": contract["lock"][
            "lock_identity_sha256"],
        "code_audit_sha256": code_audit["sha256"],
        "runner_sha256": _sha256_file(__file__),
        "w_original_asset_sha256": w_asset["sha256"],
        "w_original_order_sha256": W_ORIGINAL_ORDER_SHA256,
        "row_schema_sha256": _row_schema_hash(),
    }


def _validate_technical_audit_binding(record, expected):
    for key, value in expected.items():
        if key in record and record[key] != value:
            raise FT05AValidationError(
                "FT05A technical audit is not bound to the completed run")


def _validate_generated_technical_audit(path, expected):
    if not os.path.isfile(path):
        raise FT05AValidationError(
            "FT05A generated technical audit is missing")
    fields = _technical_audit_fields(
        _read_text(path, "FT05A generated technical audit"))
    if fields["status"] != TECHNICAL_AUDIT_PENDING_STATUS or \
            fields["independent"] != "false" or \
            fields["verdict"] != TECHNICAL_AUDIT_PENDING_VERDICT:
        raise FT05AValidationError(
            "FT05A technical audit is neither accepted nor pending review")
    if fields["outcome_blind"] != "true" or \
            fields["outcome_accessed"] != "false" or \
            fields["b_kmeans_fit"] != "false" or \
            fields["w_original_reused"] != "true" or \
            fields["repeat_extraction"] != "false":
        raise FT05AValidationError(
            "FT05A generated technical audit safety evidence is invalid")
    _validate_technical_audit_binding(fields, expected)
    return {"path": _relative(path), "sha256": _sha256_file(path),
            "status": TECHNICAL_AUDIT_PENDING_STATUS, "independent": False,
            "verdict": TECHNICAL_AUDIT_PENDING_VERDICT,
            "run_identity_sha256": fields["run_identity_sha256"],
            "cohort_sha256": fields["cohort_sha256"],
            "case_completion_evidence_hash": fields[
                "case_completion_evidence_hash"],
            "technical_case_count": fields["technical_case_count"],
            "ft04_lock_identity_sha256": fields["ft04_lock_identity_sha256"],
            "code_audit_sha256": fields["code_audit_sha256"],
            "runner_sha256": fields["runner_sha256"],
            "w_original_asset_sha256": fields["w_original_asset_sha256"],
            "w_original_order_sha256": fields["w_original_order_sha256"],
            "row_schema_sha256": fields["row_schema_sha256"]}


def _read_text(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (IOError, OSError, UnicodeError) as exc:
        raise FT05AValidationError("cannot read %s: %s" % (label, exc))


def _load_locked_slic_config(lock):
    expected_ft01_hash = (lock.get("provenance", {}).get("sources", {})
                          .get("ft01_asset_manifest", {}).get("sha256"))
    if not expected_ft01_hash or _sha256_file(DEFAULT_FT01_MANIFEST) != expected_ft01_hash:
        raise FT05AValidationError("FT01 frozen A-full boundary source hash mismatch")
    ft01 = _read_json(DEFAULT_FT01_MANIFEST, "FT01 asset manifest")
    definition = ft01.get("frozen_definition") or {}
    method = definition.get("method_config_checks") or {}
    expected = {
        "k": 2, "n_init": 100, "slic_dimension": "3D",
        "slic_target_scale_mm": 4.0,
        "slic_supergrid_voxels_xyz": [4, 4, 2],
        "slic_actual_supergrid_mm_xyz": [4.0, 4.0, 4.0],
    }
    for key, value in expected.items():
        if definition.get(key) != value or method.get(key) != value:
            raise FT05AValidationError("frozen A-full habitat definition mismatch: %s" % key)
    centers = (definition.get("center_low"), definition.get("center_high"),
               definition.get("boundary"))
    if not all(isinstance(value, (int, float)) and np.isfinite(float(value))
               for value in centers) or not centers[0] < centers[2] < centers[1]:
        raise FT05AValidationError("frozen A-full centers/boundary are invalid")
    habitat = lock.get("habitat_definition") or {}
    if habitat.get("K") != 2 or habitat.get("n_init") != 100 or \
            habitat.get("no_refit") is not True:
        raise FT05AValidationError("FT04 lock does not bind the frozen no-refit habitat")
    if habitat.get("R_low") != 49 or habitat.get("R_high") != 10 or \
            habitat.get("W_Original") != 107 or \
            habitat.get("R_low_candidate_hash") != R_LOW_CANDIDATE_HASH or \
            habitat.get("R_high_candidate_hash") != R_HIGH_CANDIDATE_HASH or \
            habitat.get("W_Original_order_sha256") != W_ORIGINAL_ORDER_SHA256:
        raise FT05AValidationError("FT04 candidate/order binding is invalid")
    config_path = method.get("config_path") or _relative(DEFAULT_HABITAT_CONFIG)
    config_path = _absolute_project_path(config_path, "frozen SLIC config")
    if _sha256_file(config_path) != (lock.get("provenance", {}).get("sources", {})
                                     .get("habitat_freeze_lock", {}).get("sha256") or ""):
        freeze = _read_json(DEFAULT_HABITAT_FREEZE, "habitat freeze lock")
        expected_hash = freeze.get("slic_config_hash")
        if not expected_hash or _sha256_file(config_path) != expected_hash:
            raise FT05AValidationError("frozen SLIC config hash mismatch")
    config = _read_json(config_path, "frozen SLIC config")
    slic = config.get("slic") or {}
    clustering = config.get("clustering") or {}
    if slic.get("dimension") != "3D" or slic.get("target_scale_mm") != 4.0 or \
            slic.get("supergrid_voxels_xyz") != [4, 4, 2] or \
            slic.get("maximum_iterations") != 5 or \
            slic.get("spatial_proximity_weight") != 10 or \
            slic.get("enforce_connectivity") is not True or \
            clustering.get("k") != 2 or clustering.get("n_init") != 100:
        raise FT05AValidationError("frozen SLIC configuration is inconsistent")
    return ft01, config, OrderedDict((
        ("center_low", float(centers[0])),
        ("center_high", float(centers[1])),
        ("boundary", float(centers[2])),
        ("K", 2), ("n_init", 100),
        ("slic_dimension", "3D"),
        ("slic_target_scale_mm", 4.0),
        ("slic_supergrid_voxels_xyz", [4, 4, 2]),
        ("slic_actual_supergrid_mm_xyz", [4.0, 4.0, 4.0]),
    ))


def _load_locked_radiomics_config(lock):
    record = lock.get("provenance", {}).get("pyradiomics") or {}
    path = record.get("configuration_path") or _relative(DEFAULT_W03_CONFIG)
    path = _absolute_project_path(path, "A/W03 PyRadiomics config")
    if _sha256_file(path) != record.get("configuration_sha256"):
        raise FT05AValidationError("A/W03 PyRadiomics configuration hash mismatch")
    config = _read_json(path, "A/W03 PyRadiomics config")
    radiomics = config.get("radiomics") or {}
    expected_classes = ["firstorder", "shape", "glcm", "glrlm", "glszm", "gldm", "ngtdm"]
    if radiomics.get("image_type") != "Original" or \
            radiomics.get("bin_width") != 0.248808 or \
            radiomics.get("normalize") is not False or \
            radiomics.get("resampled_pixel_spacing") is not None or \
            radiomics.get("feature_classes") != expected_classes:
        raise FT05AValidationError("A/W03 PyRadiomics settings changed")
    return config, dict(record)


def _w_original_binding_from_lock(lock):
    """Return the W_Original binding supplied by an accepted FT04 lock."""
    binding = (lock.get("habitat_definition") or {}).get(
        "W_Original_asset") or {}
    required = {
        "path", "asset_sha256", "feature_count", "order_sha256",
        "reused_existing_asset", "reextracted",
    }
    if set(binding) != required or not isinstance(binding.get("path"), str) or \
            not re.match(r"^[0-9a-f]{64}$", str(binding.get("asset_sha256"))) or \
            binding.get("feature_count") != 107 or \
            binding.get("order_sha256") != W_ORIGINAL_ORDER_SHA256 or \
            binding.get("reused_existing_asset") is not True or \
            binding.get("reextracted") is not False:
        raise FT05AValidationError("accepted FT04 W_Original binding is invalid")
    return OrderedDict((
        ("path", binding["path"]),
        ("asset_sha256", binding["asset_sha256"]),
        ("feature_count", 107),
        ("order_sha256", W_ORIGINAL_ORDER_SHA256),
        ("reused_existing_asset", True),
        ("reextracted", False),
    ))


def _load_canonical_w_original_lock():
    """Load the canonical FT04 binding and cross-check its FT01 source."""
    lock = _read_json(DEFAULT_LOCK, "FT04 model-freeze lock")
    if lock.get("artifact_id") != "FT_model_freeze_lock" or \
            lock.get("stage") != "FT04" or lock.get("status") != "FROZEN":
        raise FT05AValidationError("canonical FT04 lock is not frozen")
    if lock.get("lock_identity_sha256") != ft04._lock_identity(lock):
        raise FT05AValidationError("canonical FT04 lock identity is invalid")
    locked_binding = _w_original_binding_from_lock(lock)
    try:
        accepted_ft01 = ft04._accepted_w_original_binding()
    except Exception as exc:
        raise FT05AValidationError(
            "accepted FT01 W_Original binding cannot be derived: %s" % exc)
    if dict(locked_binding) != dict(accepted_ft01):
        raise FT05AValidationError(
            "FT04 W_Original binding does not match accepted FT01 asset")
    return lock


def _frozen_boundary_identity(lock):
    return ft04._frozen_a_boundary_identity(lock)


def validate_ft05a_preflight(lock_path=DEFAULT_LOCK, code_audit_path=DEFAULT_CODE_AUDIT):
    """Validate every non-B prerequisite before any technical B read."""
    lock = ft04.validate_ft_model_freeze_lock(lock_path)
    ft04._validate_ft04_review(lock, lock_path)
    if lock.get("b_access", {}).get("state") != "locked" or \
            lock.get("b_access", {}).get("b_outcome_read") is not False or \
            lock.get("b_access", {}).get("b_data_read") is not False:
        raise FT05AValidationError("FT04 lock does not keep B locked")
    code_record = _validate_code_audit(code_audit_path)
    ft01, slic_config, boundary = _load_locked_slic_config(lock)
    w03_config, pyradiomics = _load_locked_radiomics_config(lock)
    if _candidate_hash(R_LOW_FEATURE_NAMES) != R_LOW_CANDIDATE_HASH or \
            _candidate_hash(R_HIGH_FEATURE_NAMES) != R_HIGH_CANDIDATE_HASH or \
            _candidate_hash(W_ORIGINAL_FEATURE_NAMES) != W_ORIGINAL_ORDER_SHA256:
        raise FT05AValidationError("candidate or W_Original order hash failed")
    if os.path.exists(FORMAL_MODEL_LOCK):
        raise FT05AValidationError("formal model lock exists; FT05A cannot proceed")
    w_binding = (lock.get("habitat_definition") or {}).get("W_Original_asset") or {}
    w_path = w_binding.get("path")
    if not w_path or not w_binding.get("asset_sha256"):
        raise FT05AValidationError("accepted W_Original binding is absent from the FT04 lock")
    return {
        "lock": lock,
        "ft01": ft01,
        "slic_config": slic_config,
        "frozen_boundary": boundary,
        "w03_config": w03_config,
        "pyradiomics": pyradiomics,
        "code_audit": code_record,
        "technical_source_roots": tuple(ALLOWED_TECHNICAL_ROOTS),
        "w_original_path": w_path,
    }


def static_validate():
    """Return static safety findings for the independent code audit."""
    source = _read_text(__file__, "FT05A runner source")
    tree = ast.parse(source, filename=__file__)
    findings = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "sklearn" + ".cluster":
            findings.append("B clustering import is present")
        if isinstance(node, ast.Name) and node.id == "K" + "Means":
            findings.append("B clustering implementation is present")
        if isinstance(node, ast.Attribute) and node.attr in ("fit", "fit" + "_predict"):
            findings.append("a model fitting call is present")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and \
                node.func.id in ("read_" + "B_validation", "read_b" + "_excel"):
            findings.append("a B data reader is present")
    return {"pass": not findings, "findings": findings,
            "technical_path_allowlist": [_relative(path) for path in ALLOWED_TECHNICAL_ROOTS],
            "outcome_column_denylist": sorted(OUTCOME_COLUMN_MARKERS),
            "whole_tumor_reextraction": False,
            "B_kmeans_fit": False,
            "outcome_accessed": False,
            "formal_directory_mixing": False}


def _case_identity(record):
    payload = OrderedDict((
        ("patient_id", str(record["patient_id"])),
        ("image_path", str(record["image_path"])),
        ("roi_path", str(record["roi_path"])),
        ("source_image_key", str(record["source_image_key"])),
        ("source_roi_key", str(record["source_roi_key"])),
    ))
    return _sha256_text(_canonical_json(payload))


def _case_filename(record):
    return os.path.join(DEFAULT_CASE_ROOT, _case_identity(record) + ".json")


def _case_result_path(case_root, record):
    return os.path.join(case_root, _case_identity(record) + ".json")


def _reject_sensitive_result_keys(value):
    if not isinstance(value, dict):
        if isinstance(value, (list, tuple)):
            for item in value:
                _reject_sensitive_result_keys(item)
        return
    for key, item in value.items():
        lowered = str(key).lower()
        if (_is_outcome_name(key) and lowered != "outcome_accessed") or \
                lowered.endswith("path") or lowered in (
                "source_path", "image_path", "roi_path"):
            raise FT05AValidationError("case result contains a forbidden clinical or source key")
        _reject_sensitive_result_keys(item)


def _validate_result_evidence(result, record, contract):
    if not isinstance(result, dict):
        raise FT05AValidationError("case processor did not return a mapping")
    _reject_sensitive_result_keys(result)
    evidence = result.get("extraction_evidence") or {}
    required_false = ("b_kmeans_fit", "outcome_accessed", "whole_tumor_reextraction",
                      "duplicate_extraction", "formal_directory_mixing")
    if evidence.get("projection") != "direct_frozen_A_full_boundary" or \
            evidence.get("pyradiomics_matches_A_W03") is not True or \
            evidence.get("w_original_reused") is not True or \
            any(evidence.get(key) is not False for key in required_false):
        raise FT05AValidationError("case extraction evidence violates FT05A safety contract")
    if evidence.get("boundary") != contract["frozen_boundary"]["boundary"]:
        raise FT05AValidationError("case did not use the frozen A boundary")
    if result.get("technical_failure"):
        raise FT05AValidationError("case processor reported a technical failure")
    for block, names in (("R_low", R_LOW_FEATURE_NAMES),
                         ("R_high", R_HIGH_FEATURE_NAMES)):
        block_values = result.get(block)
        if not isinstance(block_values, dict) or set(block_values) != set(names):
            raise FT05AValidationError("case result lacks %s values" % block)
        structurally_defined = result.get(block + "_structurally_defined")
        technically_available = result.get(block + "_technically_available")
        if not isinstance(structurally_defined, bool) or \
                not isinstance(technically_available, bool):
            raise FT05AValidationError("case %s lacks explicit structural/technical state" % block)
        if not structurally_defined and technically_available:
            raise FT05AValidationError("case %s is technically available without structural support" % block)
        expected_state = "available" if technically_available else \
            "technical_small_roi" if structurally_defined else "structurally_absent"
        state_key = block + "_state"
        if state_key in result and result[state_key] != expected_state:
            raise FT05AValidationError("case %s structural state is inconsistent" % block)
        if technically_available:
            for name in names:
                value = pd.to_numeric(pd.Series([block_values.get(name)]),
                                      errors="coerce").iloc[0]
                if not np.isfinite(float(value)):
                    raise FT05AValidationError("case %s contains a nonfinite frozen feature" % block)
        elif any(value is not None for value in block_values.values()):
            raise FT05AValidationError(
                "case %s unavailable features must remain undefined" % block)
    habitat = result.get("habitat") or {}
    for name in GLOBAL_COLUMNS:
        value = pd.to_numeric(pd.Series([habitat.get(name)]), errors="coerce").iloc[0]
        if not np.isfinite(float(value)):
            raise FT05AValidationError("case contains a nonfinite global habitat feature")


def _flatten_case_result(record, result, w_values, contract):
    _validate_result_evidence(result, record, contract)
    row = OrderedDict((
        ("patient_id", str(record["patient_id"])), ("split", "B")))
    habitat = result["habitat"]
    for name in GLOBAL_COLUMNS:
        row[name] = float(habitat[name])
    for block, names in (("R_low", R_LOW_FEATURE_NAMES),
                         ("R_high", R_HIGH_FEATURE_NAMES)):
        structurally_defined = result[block + "_structurally_defined"]
        technically_available = result[block + "_technically_available"]
        row[block + "_structurally_defined"] = int(structurally_defined)
        row[block + "_technically_available"] = int(technically_available)
        for name in names:
            value = result[block][name]
            row[BLOCK_PREFIXES[block] + name] = \
                float(value) if technically_available else None
    row["W_Original_available"] = 1
    for name in W_ORIGINAL_FEATURE_NAMES:
        row[BLOCK_PREFIXES["W_Original"] + name] = float(w_values[name])
    expected = _technical_feature_columns(include_split=True)
    if list(row) != expected:
        raise FT05AValidationError("case result does not match canonical technical column order")
    return row


def _processor_result_hash(result):
    return _sha256_text(_canonical_json(_json_safe(result)))


def _row_hash(row):
    return _sha256_text(_canonical_json(_json_safe(row)))


def _row_schema_hash():
    return _sha256_text(_canonical_json(_technical_feature_columns(True)))


def _w_original_row_hash(w_values):
    return _sha256_text(_canonical_json(_json_safe(w_values)))


def _source_record_hash(source_record):
    return _sha256_text(_canonical_json(_json_safe(source_record)))


def _validate_case_artifact(path, record, contract, w_values=None,
                            source_record=None, expected_artifact_sha256=None):
    if expected_artifact_sha256 is not None:
        if _sha256_file(path) != expected_artifact_sha256:
            raise FT05AValidationError("per-case artifact hash mismatch")
    artifact = _read_json(path, "per-case completion artifact")
    if artifact.get("schema_version") != FT05A_SCHEMA_VERSION or \
            artifact.get("artifact_id") != "FT05A_case" or \
            artifact.get("status") != "complete" or \
            artifact.get("case_identity_sha256") != _case_identity(record) or \
            str(artifact.get("patient_id")) != str(record["patient_id"]):
        raise FT05AValidationError("per-case completion artifact identity mismatch")
    if not isinstance(source_record, dict) or \
            artifact.get("input_source_record") != source_record or \
            artifact.get("input_source_record_sha256") != _source_record_hash(source_record):
        raise FT05AValidationError("per-case input source binding mismatch")
    row = artifact.get("row")
    expected_columns = _technical_feature_columns(True)
    if not isinstance(row, dict) or set(row) != set(expected_columns):
        raise FT05AValidationError("per-case completion row schema mismatch")
    artifact["row"] = OrderedDict((column, row[column]) for column in expected_columns)
    result = artifact.get("processor_result")
    _validate_result_evidence(result, record, contract)
    if w_values is None:
        raise FT05AValidationError("accepted W_Original row is required to validate a case")
    expected_row = _flatten_case_result(record, result, w_values, contract)
    if artifact.get("processor_result_sha256") != _processor_result_hash(result) or \
            artifact.get("flattened_row_sha256") != _row_hash(expected_row) or \
            artifact.get("row_schema_sha256") != _row_schema_hash() or \
            artifact.get("w_original_row_sha256") != _w_original_row_hash(w_values) or \
            artifact["row"] != expected_row:
        raise FT05AValidationError("per-case processor/result/flattened-row binding mismatch")
    return artifact


def _write_csv_atomic(frame, path):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    raw = frame.to_csv(index=False, line_terminator="\n").encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as handle:
            if handle.read() != raw:
                raise FT05AValidationError("refusing to overwrite canonical table with different bytes")
        return
    temporary = "%s.tmp.%s" % (path, uuid.uuid4().hex)
    try:
        with open(temporary, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)


def _validate_technical_table_frame(table, table_record=None):
    expected_columns = _technical_feature_columns(True)
    if list(table.columns) != expected_columns:
        raise FT05AValidationError("FT05A technical table column order mismatch")
    if table.empty or table["patient_id"].astype(str).str.strip().eq("").any() or \
            table["patient_id"].astype(str).duplicated().any():
        raise FT05AValidationError("FT05A technical table patient IDs are not unique")
    if not table["split"].astype(str).str.upper().eq("B").all():
        raise FT05AValidationError("FT05A technical table contains a non-B row")
    forbidden = [column for column in table.columns
                 if _is_outcome_name(column) or str(column).lower().endswith("path")]
    if forbidden:
        raise FT05AValidationError(
            "FT05A technical table contains a clinical or path column")
    for column in GLOBAL_COLUMNS + ("R_low_structurally_defined",
                                    "R_low_technically_available",
                                    "R_high_structurally_defined",
                                    "R_high_technically_available",
                                    "W_Original_available"):
        values = pd.to_numeric(table[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise FT05AValidationError("FT05A technical table contains nonfinite support values")
    for block in ("R_low", "R_high"):
        structural = pd.to_numeric(table[block + "_structurally_defined"], errors="coerce")
        available = pd.to_numeric(table[block + "_technically_available"], errors="coerce")
        if not structural.isin([0, 1]).all() or not available.isin([0, 1]).all() or \
                ((structural == 0) & (available == 1)).any():
            raise FT05AValidationError("FT05A %s structural/technical state is invalid" % block)
        for name in (R_LOW_FEATURE_NAMES if block == "R_low" else R_HIGH_FEATURE_NAMES):
            values = pd.to_numeric(table[BLOCK_PREFIXES[block] + name], errors="coerce")
            if ((available == 1) & values.isna()).any() or \
                    ((available == 0) & values.notna()).any():
                raise FT05AValidationError(
                    "FT05A %s undefined-feature state is invalid" % block)
    if table_record is not None:
        required = ("columns", "row_count", "patient_count", "patient_ids_unique",
                    "duplicate_patient_count", "duplicate_extraction_count",
                    "extraction_count")
        if any(key not in table_record for key in required) or \
                table_record["columns"] != expected_columns or \
                int(table_record["row_count"]) != len(table) or \
                int(table_record["patient_count"]) != len(table) or \
                table_record.get("patient_ids_unique") is not True or \
                int(table_record["duplicate_patient_count"]) != 0 or \
                int(table_record["duplicate_extraction_count"]) != 0 or \
                int(table_record["extraction_count"]) != len(table):
            raise FT05AValidationError("FT05A technical table completeness evidence is invalid")
    return table


def validate_ft05a_technical_manifest(
        manifest_or_path=DEFAULT_MANIFEST, output_root=DEFAULT_OUTPUT_ROOT,
        _table_override=None, _table_hash_path=None, _expected_w_asset=None,
        _expected_cohort=None, _expected_lock=None):
    """Validate the outcome-blind technical manifest before the later join.

    The private override arguments are used only while recovering an atomic
    finalization.  They validate the staged bytes while retaining the
    canonical final table path recorded by the manifest.
    """
    if isinstance(manifest_or_path, str):
        path = _validate_namespace_path(
            manifest_or_path, "FT05_B_feature_manifest", output_root,
            allow_ft_namespace=True)
        manifest = _read_json(path, "FT05 B technical manifest")
    elif isinstance(manifest_or_path, dict):
        manifest = manifest_or_path
    else:
        raise FT05AValidationError("FT05 technical manifest must be a mapping or path")
    trusted_lock = _expected_lock or _load_canonical_w_original_lock()
    trusted_w_binding = _w_original_binding_from_lock(trusted_lock)
    if manifest.get("ft04_lock_identity_sha256") != \
            trusted_lock.get("lock_identity_sha256"):
        raise FT05AValidationError("FT05 manifest is not bound to the accepted FT04 lock")
    if manifest.get("artifact_id") != "FT05_B_feature_manifest" or \
            manifest.get("schema_version") != FT05A_SCHEMA_VERSION or \
            manifest.get("status") != "frozen" or \
            manifest.get("purpose") != "technical_only_outcome_blind_B_feature_table":
        raise FT05AValidationError("FT05 technical manifest is not frozen and technical-only")
    if manifest.get("technical_schema") != {
            "clinical_predictors_included": False,
            "clinical_predictors_join_stage": "authorized_outcome_stage"}:
        raise FT05AValidationError("FT05 technical manifest does not defer clinical predictors")
    record = manifest.get("feature_table") or {}
    table_path = _validate_namespace_path(
        record.get("path"), "FT05A technical feature table", output_root)
    if record.get("format") != "csv" or record.get("complete") is not True or \
            not re.match(r"^[0-9a-f]{64}$", str(record.get("sha256", ""))):
        raise FT05AValidationError("FT05A technical table hash/completeness is invalid")
    hash_path = _table_hash_path or table_path
    if not os.path.isfile(hash_path) or _sha256_file(hash_path) != record.get("sha256"):
        raise FT05AValidationError("FT05A technical table hash/completeness is invalid")
    if _table_override is not None:
        table = _table_override.copy()
    else:
        try:
            table = pd.read_csv(table_path)
        except (IOError, OSError, ValueError) as exc:
            raise FT05AValidationError("cannot read FT05A technical table: %s" % exc)
    _validate_technical_table_frame(table, record)

    blocks = manifest.get("feature_blocks") or {}
    if set(blocks) != {"R_low", "R_high", "W_Original"}:
        raise FT05AValidationError("FT05 technical feature blocks are incomplete")
    if blocks["R_low"].get("feature_names") != list(R_LOW_FEATURE_NAMES) or \
            blocks["R_low"].get("count") != 49 or \
            blocks["R_low"].get("candidate_hash") != R_LOW_CANDIDATE_HASH or \
            blocks["R_high"].get("feature_names") != list(R_HIGH_FEATURE_NAMES) or \
            blocks["R_high"].get("count") != 10 or \
            blocks["R_high"].get("candidate_hash") != R_HIGH_CANDIDATE_HASH:
        raise FT05AValidationError("FT05 technical candidate contract is invalid")
    w_record = blocks["W_Original"]
    if w_record.get("feature_names") != list(W_ORIGINAL_FEATURE_NAMES) or \
            w_record.get("count") != 107 or \
            w_record.get("order_sha256") != W_ORIGINAL_ORDER_SHA256 or \
            w_record.get("reused_existing_asset") is not True or \
            w_record.get("reextracted") is not False or \
            not isinstance(w_record.get("asset_path"), str) or \
            not re.match(r"^[0-9a-f]{64}$", str(w_record.get("asset_sha256", ""))):
        raise FT05AValidationError("FT05 technical W_Original contract is invalid")
    if w_record.get("asset_path") != trusted_w_binding["path"] or \
            w_record.get("asset_sha256") != trusted_w_binding["asset_sha256"]:
        raise FT05AValidationError(
            "FT05 W_Original provenance is not bound to the accepted FT04 asset")
    w_path = _validate_technical_path(
        trusted_w_binding["path"], "FT05 W_Original asset",
        exact_paths=(trusted_w_binding["path"],))
    if _expected_w_asset is None:
        w_asset = _load_w_original_asset(trusted_lock)
    else:
        w_asset = _expected_w_asset
        if not isinstance(w_asset, dict) or \
                w_asset.get("path") != _relative(w_path) or \
                w_asset.get("sha256") != w_record.get("asset_sha256") or \
                w_asset.get("order_sha256") != W_ORIGINAL_ORDER_SHA256 or \
                w_asset.get("feature_count") != 107:
            raise FT05AValidationError("FT05 W_Original asset binding is invalid")
    if w_asset.get("path") != _relative(w_path) or \
            w_asset.get("sha256") != trusted_w_binding["asset_sha256"] or \
            w_record.get("asset_sha256") != trusted_w_binding["asset_sha256"]:
        raise FT05AValidationError("FT05 W_Original asset binding is invalid")

    source_records = manifest.get("source_records")
    required = ("patient_id", "split", "source_image_key", "source_roi_key",
                "case_identity_sha256", "image_path", "roi_path",
                "image_sha256", "roi_sha256", "w_original_asset_path",
                "w_original_asset_sha256", "w_original_row_sha256")
    if not isinstance(source_records, list) or len(source_records) != len(table):
        raise FT05AValidationError("FT05 technical source-record completeness is invalid")
    source_keys = set()
    source_patients = []
    seen_image_paths = set()
    seen_roi_paths = set()
    seen_image_keys = set()
    seen_roi_keys = set()
    seen_image_hashes = set()
    seen_roi_hashes = set()
    for index, source_record in enumerate(source_records):
        if not isinstance(source_record, dict) or any(
                key not in source_record for key in required):
            raise FT05AValidationError("FT05 technical source-record binding is invalid")
        case_key = str(source_record["case_identity_sha256"])
        if case_key in source_keys or not re.match(r"^[0-9a-f]{64}$", case_key):
            raise FT05AValidationError("FT05 technical source-record identity is invalid")
        if any(not re.match(r"^[0-9a-f]{64}$", str(source_record[key]))
               for key in ("image_sha256", "roi_sha256",
                           "w_original_asset_sha256", "w_original_row_sha256")):
            raise FT05AValidationError("FT05 technical source-record hash is invalid")
        if str(source_record["split"]).upper() != "B":
            raise FT05AValidationError("FT05 source record contains a non-B row")
        patient_id = str(source_record["patient_id"]).strip()
        source_image_key = str(source_record["source_image_key"]).strip()
        source_roi_key = str(source_record["source_roi_key"]).strip()
        if not patient_id or not source_image_key or not source_roi_key:
            raise FT05AValidationError("FT05 source-record mapping is blank")
        image_path = _validate_technical_path(
            source_record["image_path"], "FT05 source image",
            allowed_roots=ALLOWED_TECHNICAL_ROOTS)
        roi_path = _validate_technical_path(
            source_record["roi_path"], "FT05 source ROI",
            allowed_roots=ALLOWED_TECHNICAL_ROOTS)
        if not os.path.isfile(image_path) or not os.path.isfile(roi_path) or \
                _sha256_file(image_path) != source_record["image_sha256"] or \
                _sha256_file(roi_path) != source_record["roi_sha256"]:
            raise FT05AValidationError("FT05 technical source file binding is invalid")
        image_path_key = os.path.normcase(os.path.realpath(image_path))
        roi_path_key = os.path.normcase(os.path.realpath(roi_path))
        image_hash = str(source_record["image_sha256"])
        roi_hash = str(source_record["roi_sha256"])
        if image_path_key in seen_image_paths or roi_path_key in seen_roi_paths or \
                image_path_key in seen_roi_paths or roi_path_key in seen_image_paths or \
                source_image_key in seen_image_keys or source_roi_key in seen_roi_keys or \
                image_hash in seen_image_hashes or roi_hash in seen_roi_hashes:
            raise FT05AValidationError(
                "FT05 source records contain duplicate or aliased mappings")
        seen_image_paths.add(image_path_key)
        seen_roi_paths.add(roi_path_key)
        seen_image_keys.add(source_image_key)
        seen_roi_keys.add(source_roi_key)
        seen_image_hashes.add(image_hash)
        seen_roi_hashes.add(roi_hash)
        if _validate_technical_path(
                source_record["w_original_asset_path"], "FT05 source W_Original asset",
                exact_paths=(trusted_w_binding["path"],)) != w_path or \
                source_record["w_original_asset_path"] != trusted_w_binding["path"] or \
                source_record["w_original_asset_sha256"] != trusted_w_binding["asset_sha256"]:
            raise FT05AValidationError("FT05 source W_Original asset binding is invalid")
        case_record = {"patient_id": patient_id,
                       "image_path": str(source_record["image_path"]),
                       "roi_path": str(source_record["roi_path"]),
                       "source_image_key": source_image_key,
                       "source_roi_key": source_roi_key}
        if _case_identity(case_record) != case_key:
            raise FT05AValidationError("FT05 source case identity is forged")
        row = table.iloc[index]
        if str(row["patient_id"]) != case_record["patient_id"] or \
                str(row["split"]).upper() != "B":
            raise FT05AValidationError("FT05 source records are out of table order")
        if case_record["patient_id"] in source_patients:
            raise FT05AValidationError("FT05 source records contain duplicate patients")
        source_patients.append(case_record["patient_id"])
        w_values = w_asset.get("rows", {}).get(case_record["patient_id"])
        if not isinstance(w_values, dict) or \
                source_record["w_original_row_sha256"] != _w_original_row_hash(w_values):
            raise FT05AValidationError("FT05 W_Original row binding is invalid")
        for name in W_ORIGINAL_FEATURE_NAMES:
            value = pd.to_numeric(pd.Series([row[BLOCK_PREFIXES["W_Original"] + name]]),
                                  errors="coerce").iloc[0]
            if not np.isfinite(float(value)) or float(value) != float(w_values[name]):
                raise FT05AValidationError("FT05 table W_Original row binding is invalid")
        source_keys.add(case_key)

    technical = manifest.get("technical_cohort") or {}
    if technical.get("patient_id_hash") != _sha256_text("\n".join(source_patients)) or \
            technical.get("source_mapping_hash") != _sha256_text("\n".join(
                str(item["source_image_key"]) + "|" + str(item["source_roi_key"])
                for item in source_records)):
        raise FT05AValidationError("FT05 technical cohort ordering/binding is invalid")
    ordered_rows = technical.get("ordered_rows")
    frame_columns = technical.get("source_frame_columns")
    if not isinstance(ordered_rows, list) or not ordered_rows or \
            not isinstance(frame_columns, list) or \
            set(frame_columns) != set(ordered_rows[0]):
        raise FT05AValidationError("FT05 technical cohort frame binding is invalid")
    ordered_frame = pd.DataFrame(ordered_rows, columns=frame_columns)
    if technical.get("source_frame_sha256") != _canonical_frame_hash(ordered_frame):
        raise FT05AValidationError("FT05 technical cohort frame binding is invalid")
    if technical.get("row_count") != len(ordered_frame) or \
            technical.get("patient_count") != len(ordered_frame) or \
            technical.get("patient_ids_unique") is not True:
        raise FT05AValidationError("FT05 technical cohort counts are invalid")
    frame_lookup_columns = ("patient_id", "split", "image_path", "roi_path",
                            "source_image_key", "source_roi_key")
    if any(column not in ordered_frame.columns for column in frame_lookup_columns):
        raise FT05AValidationError("FT05 technical cohort source columns are invalid")
    for index, source_record in enumerate(source_records):
        frame_row = ordered_frame.iloc[index]
        for column, source_key in (("patient_id", "patient_id"),
                                   ("split", "split"),
                                   ("image_path", "image_path"),
                                   ("roi_path", "roi_path"),
                                   ("source_image_key", "source_image_key"),
                                   ("source_roi_key", "source_roi_key")):
            if str(frame_row[column]) != str(source_record[source_key]):
                raise FT05AValidationError(
                    "FT05 source record does not match the technical cohort frame")
        if "w_original_path" in ordered_frame.columns and \
                str(frame_row["w_original_path"]) != str(w_record["asset_path"]):
            raise FT05AValidationError(
                "FT05 technical cohort W_Original path binding is invalid")
    if _expected_cohort is not None and \
            technical.get("source_frame_sha256") != _canonical_frame_hash(_expected_cohort):
        raise FT05AValidationError("FT05 technical cohort does not match the run state")

    generation = manifest.get("generation") or {}
    if generation.get("outcome_blind") is not True or \
            generation.get("one_time_first_extraction") is not True or \
            any(generation.get(key) is not False for key in (
                "outcome_accessed", "b_kmeans_fit", "repeat_extraction",
                "duplicate_extraction", "checkpoint_resume_repeated_extraction",
                "whole_tumor_reextraction", "formal_directory_mixing")):
        raise FT05AValidationError("FT05 technical generation contract is invalid")
    return manifest, table, table_path


def _build_manifest(contract, cohort, table, table_path, table_hash, run_state,
                    w_asset, code_audit, technical_audit, source_records):
    lock = contract["lock"]
    boundary = contract["frozen_boundary"]
    feature_blocks = {
        "R_low": {"feature_names": list(R_LOW_FEATURE_NAMES), "count": 49,
                  "candidate_hash": R_LOW_CANDIDATE_HASH},
        "R_high": {"feature_names": list(R_HIGH_FEATURE_NAMES), "count": 10,
                   "candidate_hash": R_HIGH_CANDIDATE_HASH},
        "W_Original": {"feature_names": list(W_ORIGINAL_FEATURE_NAMES),
                       "count": 107, "order_sha256": W_ORIGINAL_ORDER_SHA256,
                       "asset_path": w_asset["path"],
                       "asset_sha256": w_asset["sha256"],
                       "reused_existing_asset": True, "reextracted": False},
    }
    source_hashes = {
        key: lock["provenance"]["sources"][key]["sha256"]
        for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                    "w03_candidate_freeze")}
    return {
        "schema_version": FT05A_SCHEMA_VERSION,
        "artifact_id": "FT05_B_feature_manifest",
        "stage": FT05A_STAGE,
        "status": "frozen",
        "purpose": "technical_only_outcome_blind_B_feature_table",
        "technical_schema": {
            "clinical_predictors_included": False,
            "clinical_predictors_join_stage": "authorized_outcome_stage",
        },
        "exploratory_label": FT_LABEL,
        "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
        "model_input_hashes": lock["prediction_contract"]["expected_model_input_hashes"],
        "feature_table": {
            "path": _relative(table_path), "sha256": table_hash,
            "format": "csv", "complete": True,
            "columns": list(table.columns), "row_count": int(len(table)),
            "patient_id_column": "patient_id", "patient_count": int(len(table)),
            "patient_ids_unique": True, "duplicate_patient_count": 0,
            "duplicate_extraction_count": 0, "extraction_count": int(len(table)),
        },
        "feature_blocks": feature_blocks,
        "frozen_a_full_boundary": {
            "definition": "accepted frozen full_A habitat",
            "lock_identity_sha256": lock["lock_identity_sha256"],
            "identity_sha256": _frozen_boundary_identity(lock),
            "center_low": boundary["center_low"],
            "center_high": boundary["center_high"],
            "boundary": boundary["boundary"], "K": 2, "n_init": 100,
            "no_refit": True, "source_hashes": source_hashes,
        },
        "slic": {"dimension": "3D", "target_scale_mm": 4.0,
                 "supergrid_voxels_xyz": [4, 4, 2],
                 "actual_supergrid_mm_xyz": [4.0, 4.0, 4.0],
                 "connectivity": True, "maximum_iterations": 5,
                 "spatial_proximity_weight": 10, "fit_source": "frozen_A_only"},
        "pyradiomics_provenance": contract["pyradiomics"],
        "pyradiomics_matches_A_W03": True,
        "generation": {
            "outcome_blind": True, "one_time_first_extraction": True,
            "projection": "direct_frozen_A_full_boundary",
            "w_original_reused": True, "b_kmeans_fit": False,
            "outcome_accessed": False, "repeat_extraction": False,
            "duplicate_extraction": False,
            "checkpoint_resume_repeated_extraction": False,
            "whole_tumor_reextraction": False,
            "formal_directory_mixing": False, "preprocessing_estimation": False,
        },
        "technical_cohort": {
            "row_count": int(len(cohort)), "patient_count": int(len(cohort)),
            "patient_ids_unique": True,
            "patient_id_hash": _sha256_text("\n".join(cohort["patient_id"].astype(str))),
            "source_mapping_hash": _sha256_text("\n".join(
                cohort["source_image_key"].astype(str) + "|" +
                cohort["source_roi_key"].astype(str))),
            "source_frame_sha256": _canonical_frame_hash(cohort),
            "source_frame_columns": list(cohort.columns),
            "ordered_rows": _json_safe(cohort.to_dict(orient="records")),
        },
        "source_records": source_records,
        "run_identity": run_state["run_identity_sha256"],
        "completion": {
            "completed_case_count": int(len(table)), "table_sha256": table_hash,
            "case_completion_evidence_hash": _sha256_text(_canonical_json(
                run_state.get("completed_case_artifact_hashes", {}))),
        },
        "reviews": {"technical_audit": technical_audit,
                    "code_audit": code_audit},
        "provenance": {
            "runner": _relative(__file__), "runner_sha256": _sha256_file(__file__),
            "wrapper": "tools/run_t2_radiomics.ps1",
            "environment_name": "t2_radiomics", "python": platform.python_version(),
            "numpy": np.__version__, "pandas": pd.__version__,
            "ft04_lock_path": _relative(DEFAULT_LOCK),
            "ft04_review_path": _relative(ft04.FT04_REVIEW),
            "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
            "ft04_lock_digest_path": (lock.get("provenance", {}).get(
                "git_binding", {}).get("current_file_bindings", {})
                .get("ft04_lock", {}).get("digest_attestation_path")),
            "slic_config": contract.get("slic_config"),
        },
    }


def _extract_habitat_features(extractor, image, mask, names, block_name,
                              voxel_count=None):
    """Apply the frozen PyRadiomics size boundary without imputation."""
    if voxel_count is None:
        if isinstance(mask, np.ndarray):
            voxel_count = int(np.count_nonzero(mask))
        else:
            import SimpleITK as sitk
            voxel_count = int(np.count_nonzero(sitk.GetArrayFromImage(mask)))
    if voxel_count == 0:
        return OrderedDict((name, None) for name in names), False, False, \
            "structurally_absent"
    if voxel_count < MINIMUM_ROI_SIZE:
        return OrderedDict((name, None) for name in names), True, False, \
            "technical_small_roi"
    try:
        result = extractor.execute(image, mask, label=1)
    except Exception as exc:
        raise FT05ARunError(
            "%s PyRadiomics extraction failed: %s" % (block_name, exc))
    if any(name not in result for name in names):
        raise FT05ARunError(
            "%s PyRadiomics result lacks a frozen candidate" % block_name)
    values = OrderedDict()
    for name in names:
        value = pd.to_numeric(pd.Series([result[name]]), errors="coerce").iloc[0]
        if not np.isfinite(float(value)):
            raise FT05ARunError(
                "%s PyRadiomics result contains a nonfinite candidate" % block_name)
        values[name] = float(value)
    return values, True, True, "available"


def _default_process_case(record, contract):
    """Process one preprocessed image/ROI with frozen A technical settings."""
    import SimpleITK as sitk
    from scipy import ndimage
    from radiomics import featureextractor

    image = sitk.ReadImage(_ascii_path(record["image_path"]))
    roi_image = sitk.ReadImage(_ascii_path(record["roi_path"]))
    if image.GetSize() != roi_image.GetSize() or \
            not np.allclose(image.GetSpacing(), roi_image.GetSpacing(), atol=1e-5, rtol=0) or \
            not np.allclose(image.GetOrigin(), roi_image.GetOrigin(), atol=1e-4, rtol=0) or \
            not np.allclose(image.GetDirection(), roi_image.GetDirection(), atol=1e-5, rtol=0):
        raise FT05ARunError("image/ROI geometry mismatch")
    image_array = sitk.GetArrayFromImage(image).astype(np.float32, copy=False)
    roi = sitk.GetArrayFromImage(roi_image)
    if not np.allclose(image.GetSpacing(), (1.0, 1.0, 2.0), atol=1e-6, rtol=0):
        raise FT05ARunError("preprocessed image spacing is not the frozen [1,1,2] mm")
    if not np.isin(np.unique(roi), [0, 1]).all() or not np.any(roi == 1):
        raise FT05ARunError("ROI is not binary and nonempty")
    if not np.isfinite(image_array[roi == 1]).all():
        raise FT05ARunError("image contains nonfinite ROI values")
    slic = contract["slic_config"]["slic"]
    filt = sitk.SLICImageFilter()
    filt.SetSuperGridSize([4, 4, 2])
    filt.SetMaximumNumberOfIterations(int(slic["maximum_iterations"]))
    filt.SetSpatialProximityWeight(float(slic["spatial_proximity_weight"]))
    filt.SetInitializationPerturbation(bool(slic["initialization_perturbation"]))
    filt.SetEnforceConnectivity(True)
    filt.SetNumberOfWorkUnits(int(slic["work_units"]))
    labels = sitk.GetArrayFromImage(
        filt.Execute(sitk.Cast(image, sitk.sitkFloat32))).astype(np.int32, copy=False)
    if labels.shape != roi.shape or np.any((labels < 0) & (roi == 1)):
        raise FT05ARunError("SLIC did not assign every ROI voxel")
    means = {}
    for label in np.unique(labels[roi == 1]):
        selected = (labels == label) & (roi == 1)
        if np.any(selected):
            means[int(label)] = float(image_array[selected].mean())
    boundary = contract["frozen_boundary"]["boundary"]
    habitat = np.full(labels.shape, -1, dtype=np.int8)
    for label, mean in means.items():
        habitat[labels == label] = int(mean >= boundary)
    habitat[roi == 0] = -1
    low_mask = (habitat == 0) & (roi == 1)
    high_mask = (habitat == 1) & (roi == 1)
    tumor_n = int(np.count_nonzero(roi == 1))
    spacing = tuple(float(value) for value in image.GetSpacing())
    voxel_volume = float(np.prod(spacing))
    interface = 0.0
    face_areas = (spacing[1] * spacing[2], spacing[0] * spacing[2],
                  spacing[0] * spacing[1])
    for axis, area in enumerate(face_areas):
        left = np.take(habitat, range(habitat.shape[axis] - 1), axis=axis)
        right = np.take(habitat, range(1, habitat.shape[axis]), axis=axis)
        left_roi = np.take(roi, range(roi.shape[axis] - 1), axis=axis)
        right_roi = np.take(roi, range(1, roi.shape[axis]), axis=axis)
        interface += float(np.count_nonzero((left >= 0) & (right >= 0) &
                                            (left_roi == 1) & (right_roi == 1) &
                                            (left != right))) * area
    connected, n_connected = ndimage.label(high_mask, ndimage.generate_binary_structure(3, 1))
    sizes = np.bincount(connected.ravel())[1:] if n_connected else np.array([], dtype=int)
    largest = int(sizes.max()) if len(sizes) else 0
    depth = ndimage.distance_transform_edt(roi == 1, sampling=spacing[::-1])
    max_depth = float(depth[roi == 1].max())
    radial = float(depth[high_mask].sum() / (max_depth * tumor_n)) if high_mask.any() and max_depth > 0 else 0.0
    values = np.asarray(list(means.values()), dtype=float)
    extractor_settings = {
        "imageType": {"Original": {}},
        "featureClass": {name: [] for name in contract["w03_config"]["radiomics"]["feature_classes"]},
        "setting": {"binWidth": 0.248808, "normalize": False,
                    "resampledPixelSpacing": None, "padDistance": 0,
                    "minimumROIDimensions": 2, "minimumROISize": MINIMUM_ROI_SIZE,
                    "label": 1},
    }
    extractor = featureextractor.RadiomicsFeatureExtractor(extractor_settings)
    low_image_mask = sitk.GetImageFromArray(low_mask.astype(np.uint8))
    high_image_mask = sitk.GetImageFromArray(high_mask.astype(np.uint8))
    low_image_mask.CopyInformation(image)
    high_image_mask.CopyInformation(image)
    low, low_defined, low_available, low_state = _extract_habitat_features(
        extractor, image, low_image_mask, R_LOW_FEATURE_NAMES, "R_low",
        voxel_count=int(np.count_nonzero(low_mask)))
    high, high_defined, high_available, high_state = _extract_habitat_features(
        extractor, image, high_image_mask, R_HIGH_FEATURE_NAMES, "R_high",
        voxel_count=int(np.count_nonzero(high_mask)))
    return {
        "habitat": {
            "H_high_fraction": float(high_mask.sum() / tumor_n),
            "sv_median_minus_boundary": float(np.median(values) - boundary),
            "sv_IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "interface_density": float(interface / (tumor_n * voxel_volume)),
            "H_high_largest_component_tumor_fraction": float(largest / tumor_n),
            "H_high_radial_burden": radial,
        },
        "R_low": low, "R_high": high,
        "R_low_structurally_defined": low_defined,
        "R_high_structurally_defined": high_defined,
        "R_low_technically_available": low_available,
        "R_high_technically_available": high_available,
        "R_low_state": low_state, "R_high_state": high_state,
        "extraction_evidence": {
            "projection": "direct_frozen_A_full_boundary",
            "boundary": boundary,
            "pyradiomics_matches_A_W03": True,
            "w_original_reused": True,
            "b_kmeans_fit": False, "outcome_accessed": False,
            "whole_tumor_reextraction": False,
            "duplicate_extraction": False, "formal_directory_mixing": False,
        },
    }


def _source_record(record, w_asset, technical_source_roots=None):
    roots = technical_source_roots or ALLOWED_TECHNICAL_ROOTS
    image_path = _validate_technical_path(
        record["image_path"], "image_path", allowed_roots=roots)
    roi_path = _validate_technical_path(
        record["roi_path"], "roi_path", allowed_roots=roots)
    if not os.path.isfile(image_path) or not os.path.isfile(roi_path):
        raise FT05ARunError("technical image/ROI source is missing")
    try:
        w_values = w_asset["rows"][str(record["patient_id"])]
    except KeyError:
        raise FT05AValidationError("accepted W_Original asset does not cover the technical cohort")
    return OrderedDict((
        ("patient_id", str(record["patient_id"])),
        ("split", str(record.get("split", "B")).upper()),
        ("source_image_key", str(record["source_image_key"])),
        ("source_roi_key", str(record["source_roi_key"])),
        ("case_identity_sha256", _case_identity(record)),
        ("image_path", record["image_path"]),
        ("roi_path", record["roi_path"]),
        ("image_sha256", _sha256_file(image_path)),
        ("roi_sha256", _sha256_file(roi_path)),
        ("w_original_asset_path", w_asset["path"]),
        ("w_original_asset_sha256", w_asset["sha256"]),
        ("w_original_row_sha256", _w_original_row_hash(w_values)),
    ))


def _source_records(cohort, w_asset, technical_source_roots=None):
    return [_source_record(record, w_asset, technical_source_roots)
            for _, record in cohort.iterrows()]


def _initial_run_state(run_id, cohort, lock, code_audit, output_root):
    w_binding = (lock.get("habitat_definition") or {}).get("W_Original_asset") or {}
    identity_payload = OrderedDict((
        ("artifact", "FT05A_one_time_run"), ("run_id", run_id),
        ("ft04_lock_identity_sha256", lock["lock_identity_sha256"]),
        ("cohort_sha256", _canonical_frame_hash(cohort)),
        ("candidate_hashes", {"R_low": R_LOW_CANDIDATE_HASH,
                              "R_high": R_HIGH_CANDIDATE_HASH}),
        ("w_original_order_sha256", W_ORIGINAL_ORDER_SHA256),
        ("w_original_asset_path", w_binding.get("path")),
        ("w_original_asset_sha256", w_binding.get("asset_sha256")),
        ("code_audit_sha256", code_audit["sha256"]),
        ("output_root", _relative(output_root)),
    ))
    return OrderedDict((
        ("schema_version", FT05A_SCHEMA_VERSION), ("artifact_id", "FT05A_run_state"),
        ("status", "RUNNING"), ("run_id", run_id),
        ("run_identity_sha256", _sha256_text(_canonical_json(identity_payload))),
        ("identity_payload", identity_payload),
        ("target_patient_count", int(len(cohort))),
        ("target_patient_ids_hash", _sha256_text("\n".join(cohort["patient_id"]))),
        ("completed_case_keys", []), ("completed_case_count", 0),
        ("completed_case_artifact_hashes", {}),
        ("failed_cases", []), ("pilot_case_keys", []),
        ("finalization", None),
        ("created_at_epoch", time.time()),
    ))


def _technical_audit_text(expected):
    return """# FT05A B Technical Generation Audit

Status: %s
Independent review: false
Verdict: %s

This is factual runtime evidence emitted by the FT05A runner. It is not an
independent review and does not authorize FT05B or FT06. An independent
Reviewer must inspect the completed technical artifacts and update this same
canonical report before the frozen feature manifest can be created.

FT05A run identity SHA-256: `%s`
FT05A cohort SHA-256: `%s`
FT05A case-completion evidence SHA-256: `%s`
Technical case count: %s
FT04 lock identity SHA-256: `%s`
FT05A code-audit SHA-256: `%s`
FT05A runner SHA-256: `%s`
W_Original asset SHA-256: `%s`
W_Original order SHA-256: `%s`
FT05A row-schema SHA-256: `%s`

Outcome-blind: true
Outcome accessed: false
B K-means fit: false
W_Original reused: true
Repeat extraction: false
""" % (
        TECHNICAL_AUDIT_PENDING_STATUS, TECHNICAL_AUDIT_PENDING_VERDICT,
        expected["run_identity_sha256"], expected["cohort_sha256"],
        expected["case_completion_evidence_hash"],
        expected["technical_case_count"],
        expected["ft04_lock_identity_sha256"], expected["code_audit_sha256"],
        expected["runner_sha256"], expected["w_original_asset_sha256"],
        expected["w_original_order_sha256"], expected["row_schema_sha256"])


def _ensure_technical_generation_audit(path, run_state, cohort, contract,
                                        w_asset, code_audit):
    expected = _technical_audit_expected(
        run_state, cohort, contract, w_asset, code_audit)
    if os.path.isfile(path):
        try:
            accepted = _validate_technical_audit(path)
        except FT05AValidationError:
            return _validate_generated_technical_audit(path, expected)
        _validate_technical_audit_binding(accepted, expected)
        return accepted
    _write_text_atomic(path, _technical_audit_text(expected),
                       refuse_existing=True)
    return _validate_generated_technical_audit(path, expected)


def _write_json_exclusive(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(directory):
        os.makedirs(directory)
    raw = (json.dumps(_json_safe(payload), ensure_ascii=False, indent=2,
                      sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    try:
        descriptor = os.open(path, flags)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = None
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        if descriptor is not None:
            os.close(descriptor)
    return True


def _process_is_alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _acquire_run_ownership(output_root, run_identity_sha256):
    path = os.path.join(output_root, "FT05A_run_owner.json")
    owner = OrderedDict((
        ("artifact_id", "FT05A_run_owner"),
        ("run_identity_sha256", run_identity_sha256),
        ("owner_id", uuid.uuid4().hex),
        ("pid", int(os.getpid())),
        ("created_at_epoch", time.time()),
    ))
    if _write_json_exclusive(path, owner):
        return path, owner
    try:
        existing = _read_json(path, "FT05A run owner")
    except FT05AValidationError:
        raise FT05AValidationError("FT05A run ownership record is unreadable")
    if existing.get("run_identity_sha256") != run_identity_sha256:
        raise FT05AValidationError("FT05A run has a conflicting active owner")
    if _process_is_alive(existing.get("pid")):
        raise FT05AValidationError("FT05A run is already owned by another active process")
    try:
        os.remove(path)
    except OSError:
        raise FT05AValidationError("FT05A stale run ownership cannot be reclaimed")
    if not _write_json_exclusive(path, owner):
        raise FT05AValidationError("FT05A run ownership was claimed concurrently")
    return path, owner


def _release_run_ownership(path, owner):
    try:
        current = _read_json(path, "FT05A run owner")
    except FT05AValidationError:
        return
    if current.get("owner_id") != owner.get("owner_id"):
        return
    try:
        os.remove(path)
    except OSError:
        pass


def _is_sha256(value):
    return bool(re.match(r"^[0-9a-f]{64}$", str(value or "")))


def _validate_run_state_structure(state, expected, cohort=None):
    """Validate persisted state before considering an identity migration."""
    if not isinstance(state, dict):
        raise FT05AValidationError("FT05A run state is not a mapping")
    required = {
        "schema_version", "artifact_id", "status", "run_id",
        "run_identity_sha256", "identity_payload", "target_patient_count",
        "target_patient_ids_hash", "completed_case_keys",
        "completed_case_count", "completed_case_artifact_hashes",
        "failed_cases", "pilot_case_keys", "finalization",
        "created_at_epoch",
    }
    allowed = required | {
        "identity_migration", "pilot_completed_at_epoch",
        "feature_table_path", "feature_table_sha256", "manifest_path",
        "manifest_sha256", "completed_at_epoch", "technical_audit_path",
        "technical_audit_sha256",
    }
    if set(state) - allowed or not required.issubset(set(state)):
        raise FT05AValidationError("FT05A run state structure is malformed")
    if state.get("schema_version") != FT05A_SCHEMA_VERSION or \
            state.get("artifact_id") != "FT05A_run_state":
        raise FT05AValidationError("FT05A run state schema is invalid")
    if state.get("status") not in (
            "RUNNING", "PILOT_COMPLETE", "FAILED", "FINALIZING",
            "COMPLETED", "FROZEN", TECHNICAL_COMPLETE_PENDING_REVIEW):
        raise FT05AValidationError("FT05A run state status is invalid")
    payload = state.get("identity_payload")
    expected_payload = expected.get("identity_payload") \
        if isinstance(expected, dict) else None
    if not isinstance(payload, dict) or not isinstance(expected_payload, dict) or \
            set(payload) != IDENTITY_PAYLOAD_FIELDS or \
            set(expected_payload) != IDENTITY_PAYLOAD_FIELDS:
        raise FT05AValidationError("FT05A run-state identity payload is malformed")
    if not _is_sha256(expected.get("run_identity_sha256")) or \
            expected.get("run_identity_sha256") != \
            _sha256_text(_canonical_json(expected_payload)):
        raise FT05AValidationError("FT05A expected identity digest is invalid")
    if not isinstance(state.get("run_id"), str) or \
            state.get("run_id") != payload.get("run_id"):
        raise FT05AValidationError("FT05A run-state run ID is inconsistent")
    if not _is_sha256(state.get("run_identity_sha256")) or \
            state.get("run_identity_sha256") != \
            _sha256_text(_canonical_json(payload)):
        raise FT05AValidationError("FT05A run-state identity digest is invalid")
    target_count = state.get("target_patient_count")
    if not isinstance(target_count, int) or isinstance(target_count, bool) or \
            target_count < 1:
        raise FT05AValidationError("FT05A run-state patient count is invalid")
    if not _is_sha256(state.get("target_patient_ids_hash")):
        raise FT05AValidationError("FT05A run-state patient hash is invalid")
    completed_keys = state.get("completed_case_keys")
    artifact_hashes = state.get("completed_case_artifact_hashes")
    if not isinstance(completed_keys, list) or \
            not all(isinstance(key, str) for key in completed_keys) or \
            not isinstance(artifact_hashes, dict) or \
            len(completed_keys) != len(set(completed_keys)) or \
            set(artifact_hashes) != set(completed_keys) or \
            any(not _is_sha256(key) for key in completed_keys) or \
            any(not _is_sha256(value) for value in artifact_hashes.values()) or \
            not isinstance(state.get("completed_case_count"), int) or \
            isinstance(state.get("completed_case_count"), bool) or \
            state.get("completed_case_count") != len(completed_keys):
        raise FT05AValidationError("FT05A run-state completion evidence is invalid")
    pilot_keys = state.get("pilot_case_keys")
    if not isinstance(pilot_keys, list) or \
            not all(isinstance(key, str) for key in pilot_keys) or \
            len(pilot_keys) != len(set(pilot_keys)) or \
            any(not _is_sha256(key) for key in pilot_keys):
        raise FT05AValidationError("FT05A run-state pilot evidence is invalid")
    if not set(pilot_keys).issubset(set(completed_keys)):
        raise FT05AValidationError(
            "FT05A pilot cases are not represented in completed cases")
    if state.get("status") == "PILOT_COMPLETE":
        if not pilot_keys or set(pilot_keys) != set(completed_keys) or \
                "pilot_completed_at_epoch" not in state or \
                state.get("failed_cases"):
            raise FT05AValidationError(
                "FT05A pilot-complete state lacks complete case evidence")
    if "pilot_completed_at_epoch" in state and not pilot_keys:
        raise FT05AValidationError(
            "FT05A pilot completion timestamp lacks pilot case evidence")
    if not isinstance(state.get("failed_cases"), list):
        raise FT05AValidationError("FT05A run-state failure evidence is invalid")
    technical_audit_fields = {"technical_audit_path", "technical_audit_sha256"}
    if state.get("status") == TECHNICAL_COMPLETE_PENDING_REVIEW:
        if technical_audit_fields - set(state) or \
                not isinstance(state.get("technical_audit_path"), str) or \
                not _is_sha256(state.get("technical_audit_sha256")) or \
                state.get("completed_case_count") != target_count or \
                len(completed_keys) != target_count or state.get("failed_cases"):
            raise FT05AValidationError(
                "FT05A pending technical-review state lacks complete case evidence")
    elif technical_audit_fields.intersection(set(state)):
        raise FT05AValidationError(
            "FT05A run state has unexpected technical-audit evidence")
    finalization = state.get("finalization")
    if state.get("status") == "FINALIZING":
        if not isinstance(finalization, dict):
            raise FT05AValidationError("FT05A finalization state is malformed")
    elif finalization is not None:
        raise FT05AValidationError("FT05A run-state has an unexpected finalization")
    created_at = state.get("created_at_epoch")
    if not isinstance(created_at, (int, float)) or isinstance(created_at, bool) or \
            not np.isfinite(float(created_at)):
        raise FT05AValidationError("FT05A run-state creation time is invalid")
    if "pilot_completed_at_epoch" in state:
        pilot_completed_at = state.get("pilot_completed_at_epoch")
        if not isinstance(pilot_completed_at, (int, float)) or \
                isinstance(pilot_completed_at, bool) or \
                not np.isfinite(float(pilot_completed_at)):
            raise FT05AValidationError("FT05A pilot completion time is invalid")
    completed_fields = {
        "feature_table_path", "feature_table_sha256", "manifest_path",
        "manifest_sha256", "completed_at_epoch",
    }
    if state.get("status") not in ("COMPLETED", "FROZEN") and \
            completed_fields.intersection(set(state)):
        raise FT05AValidationError(
            "FT05A run state has unexpected completed-run evidence")
    for key in ("feature_table_sha256", "manifest_sha256"):
        if key in state and not _is_sha256(state.get(key)):
            raise FT05AValidationError("FT05A completed artifact hash is invalid")
    migration = state.get("identity_migration")
    if migration is not None:
        if not isinstance(migration, dict) or \
                set(migration) != {"from_code_audit_sha256",
                                   "to_code_audit_sha256", "reason"} or \
                not _is_sha256(migration.get("from_code_audit_sha256")) or \
                not _is_sha256(migration.get("to_code_audit_sha256")) or \
                migration.get("from_code_audit_sha256") == \
                migration.get("to_code_audit_sha256") or \
                migration.get("reason") != FT05A_IDENTITY_MIGRATION_REASON:
            raise FT05AValidationError("FT05A identity migration evidence is invalid")
        if migration.get("to_code_audit_sha256") != \
                payload.get("code_audit_sha256"):
            raise FT05AValidationError("FT05A identity migration target is invalid")
    if cohort is not None:
        if target_count != len(cohort) or \
                state.get("target_patient_ids_hash") != _sha256_text(
                    "\n".join(cohort["patient_id"].astype(str))):
            raise FT05AValidationError("FT05A run-state cohort evidence is invalid")
        valid = {_case_identity(row) for _, row in cohort.iterrows()}
        if any(key not in valid for key in completed_keys + pilot_keys):
            raise FT05AValidationError("FT05A run-state case evidence is out of cohort")


def _identity_differs_only_by_audit(existing_payload, expected_payload):
    if not isinstance(existing_payload, dict) or \
            not isinstance(expected_payload, dict) or \
            set(existing_payload) != set(expected_payload):
        return False
    differences = [key for key in expected_payload
                   if existing_payload.get(key) != expected_payload.get(key)]
    return differences == ["code_audit_sha256"] and \
        existing_payload.get("code_audit_sha256") != \
        expected_payload.get("code_audit_sha256") and \
        _is_sha256(existing_payload.get("code_audit_sha256")) and \
        _is_sha256(expected_payload.get("code_audit_sha256"))


def _validate_current_code_audit_record(code_audit, expected_hash):
    if not isinstance(code_audit, dict) or \
            code_audit.get("status") != "accepted" or \
            code_audit.get("independent") is not True or \
            code_audit.get("verdict") not in ("PASS", "PASS_WITH_FINDINGS") or \
            code_audit.get("sha256") != expected_hash or \
            not _is_sha256(code_audit.get("sha256")) or \
            code_audit.get("path") != _relative(DEFAULT_CODE_AUDIT) or \
            code_audit.get("runner_sha256") != _sha256_file(__file__) or \
            not re.match(r"^[0-9a-f]{40}$",
                         str(code_audit.get("reviewed_commit") or "")) or \
            code_audit.get("contract_identity") != FT05A_CODE_PREP_CONTRACT_IDENTITY:
        raise FT05AValidationError(
            "FT05A identity migration requires the accepted current code audit")


def _load_or_create_state(path, expected, resume, code_audit=None, cohort=None,
                          manifest_path=None, migration_validator=None):
    if os.path.exists(path):
        state = _read_json(path, "FT05A run state")
        _validate_run_state_structure(state, expected, cohort=cohort)
        if state.get("status") in ("COMPLETED", "FROZEN"):
            raise FT05AValidationError("completed FT05A run cannot be rerun")
        if not resume:
            raise FT05AValidationError("existing FT05A run state requires explicit resume")
        if state.get("run_identity_sha256") == expected["run_identity_sha256"] and \
                state.get("identity_payload") == expected["identity_payload"]:
            return state
        if not _identity_differs_only_by_audit(
                state.get("identity_payload"), expected.get("identity_payload")):
            raise FT05AValidationError("conflicting FT05A run identity")
        if state.get("status") == TECHNICAL_COMPLETE_PENDING_REVIEW:
            raise FT05AValidationError(
                "FT05A technical-complete state cannot migrate code identity")
        if state.get("status") == "FINALIZING":
            raise FT05AValidationError(
                "FT05A finalization state cannot be migrated across code remediation")
        if manifest_path is not None:
            _refuse_existing_manifest(manifest_path, state)
        _validate_current_code_audit_record(
            code_audit, expected["identity_payload"]["code_audit_sha256"])
        if migration_validator is None:
            raise FT05AValidationError(
                "FT05A identity migration requires completed-case validation")
        migrated = copy.deepcopy(state)
        migration_validator(copy.deepcopy(migrated))
        old_audit_hash = state["identity_payload"]["code_audit_sha256"]
        migrated["run_identity_sha256"] = expected["run_identity_sha256"]
        migrated["identity_payload"] = copy.deepcopy(expected["identity_payload"])
        migrated["identity_migration"] = OrderedDict((
            ("from_code_audit_sha256", old_audit_hash),
            ("to_code_audit_sha256",
             expected["identity_payload"]["code_audit_sha256"]),
            ("reason", FT05A_IDENTITY_MIGRATION_REASON),
        ))
        _validate_run_state_structure(migrated, expected, cohort=cohort)
        _write_json_atomic(path, migrated)
        return migrated
    if _write_json_exclusive(path, expected):
        return expected
    return _load_or_create_state(
        path, expected, resume, code_audit=code_audit, cohort=cohort,
        manifest_path=manifest_path, migration_validator=migration_validator)


def _refuse_existing_manifest(path, state=None):
    if not os.path.exists(path):
        return
    transaction = (state or {}).get("finalization") or {}
    if (state or {}).get("status") == "FINALIZING" and \
            transaction.get("manifest_path") == _relative(path):
        return
    try:
        existing = _read_json(path, "existing FT05 manifest")
    except FT05AValidationError:
        raise FT05AValidationError("existing FT05 manifest path is not reusable")
    if existing.get("artifact_id") == "FT05_B_feature_manifest" and \
            existing.get("status") in ("frozen", "completed"):
        raise FT05AValidationError("completed/frozen FT05 manifest cannot be rerun")
    raise FT05AValidationError("existing FT05 manifest conflicts with this run")


def _update_state(path, state):
    _write_json_atomic(path, state)


def _validate_state_case_keys(state, cohort):
    valid = {_case_identity(row): row for _, row in cohort.iterrows()}
    keys = list(state.get("completed_case_keys", []))
    artifact_hashes = state.get("completed_case_artifact_hashes")
    if not isinstance(artifact_hashes, dict) or \
            set(artifact_hashes) != set(keys) or \
            any(not re.match(r"^[0-9a-f]{64}$", str(value))
                for value in artifact_hashes.values()) or \
            len(keys) != len(set(keys)) or any(key not in valid for key in keys):
        raise FT05AValidationError("run state contains invalid or duplicate completed cases")


def _reconcile_existing_cases(state, cohort, contract, w_asset, case_root):
    """Adopt only exact completed case artifacts after an interrupted run."""
    expected = {_case_identity(row): row for _, row in cohort.iterrows()}
    completed = set(state.get("completed_case_keys", []))
    artifact_hashes = state["completed_case_artifact_hashes"]
    source_records = {}
    for key in sorted(completed):
        record = expected[key]
        path = _case_result_path(case_root, record)
        if not os.path.isfile(path):
            raise FT05AValidationError("run state references a missing completed case")
        source_record = _source_record(
            record, w_asset, contract.get("technical_source_roots"))
        _validate_case_artifact(
            path, record, contract, w_asset["rows"][str(record["patient_id"])],
            source_record=source_record,
            expected_artifact_sha256=artifact_hashes[key])
        source_records[key] = source_record
    for name in os.listdir(case_root):
        path = os.path.join(case_root, name)
        if not os.path.isfile(path):
            continue
        if not name.endswith(".json"):
            raise FT05AValidationError("unexpected file in FT05A case namespace")
        key = name[:-5]
        if key not in expected:
            raise FT05AValidationError("case namespace contains an unknown extraction record")
        record = expected[key]
        source_record = _source_record(
            record, w_asset, contract.get("technical_source_roots"))
        expected_hash = artifact_hashes.get(key)
        _validate_case_artifact(
            path, record, contract, w_asset["rows"][str(record["patient_id"])],
            source_record=source_record,
            expected_artifact_sha256=expected_hash)
        completed.add(key)
        artifact_hashes[key] = _sha256_file(path)
        source_records[key] = source_record
    state["completed_case_keys"] = sorted(completed)
    state["completed_case_count"] = len(completed)
    return completed, source_records


def _install_staged_file(staged_path, target_path, expected_hash, label):
    if os.path.isfile(target_path):
        if _sha256_file(target_path) != expected_hash:
            raise FT05AValidationError("%s target has conflicting bytes" % label)
        return
    if not os.path.isfile(staged_path) or _sha256_file(staged_path) != expected_hash:
        raise FT05AValidationError("%s staged bytes are missing or corrupted" % label)
    os.replace(staged_path, target_path)


def _finalization_source(staged_path, target_path, expected_hash, label):
    candidates = [path for path in (staged_path, target_path)
                  if os.path.isfile(path)]
    if not candidates:
        raise FT05AValidationError("%s bytes are missing" % label)
    for path in candidates:
        if _sha256_file(path) != expected_hash:
            raise FT05AValidationError("%s bytes are corrupted" % label)
    if len(candidates) == 2 and _sha256_file(candidates[0]) != \
            _sha256_file(candidates[1]):
        raise FT05AValidationError("%s staged and installed bytes diverge" % label)
    return candidates[0]


def _assert_table_matches_cases(table, cohort, contract, w_asset, source_records,
                                artifact_hashes, case_root):
    expected_rows = []
    for _, record in cohort.iterrows():
        key = _case_identity(record)
        artifact = _validate_case_artifact(
            _case_result_path(case_root, record), record, contract,
            w_asset["rows"][str(record["patient_id"])],
            source_record=source_records[key],
            expected_artifact_sha256=artifact_hashes[key])
        expected_rows.append(artifact["row"])
    expected = pd.DataFrame(expected_rows, columns=_technical_feature_columns(True))
    if len(expected) != len(table):
        raise FT05AValidationError("finalization table/case count mismatch")
    for index, column in enumerate(_technical_feature_columns(True)):
        actual_values = table[column].tolist()
        expected_values = expected[column].tolist()
        for actual, wanted in zip(actual_values, expected_values):
            if wanted is None:
                if not pd.isna(actual):
                    raise FT05AValidationError(
                        "finalization table/case row binding mismatch")
            elif isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
                if not np.isfinite(float(actual)) or float(actual) != float(wanted):
                    raise FT05AValidationError(
                        "finalization table/case row binding mismatch")
            elif str(actual) != str(wanted):
                raise FT05AValidationError(
                    "finalization table/case row binding mismatch")


def _recover_finalization(state, state_path, contract=None, cohort=None,
                          w_asset=None, output_root=DEFAULT_OUTPUT_ROOT,
                          manifest_path=DEFAULT_MANIFEST):
    if contract is None or cohort is None or w_asset is None:
        raise FT05AValidationError(
            "FT05A finalization recovery requires a validated run context")
    transaction = state.get("finalization") or {}
    required = {
        "transaction_schema_version", "run_identity_sha256", "cohort_sha256",
        "staged_table_path", "staged_manifest_path", "table_path", "manifest_path",
        "table_sha256", "manifest_sha256", "completed_case_count",
        "completed_case_keys", "completed_case_artifact_hashes",
        "case_completion_evidence_hash", "w_original_asset_path",
        "w_original_asset_sha256", "w_original_order_sha256",
    }
    if state.get("status") != "FINALIZING" or set(transaction) != required or \
            transaction.get("transaction_schema_version") != "1":
        raise FT05AValidationError("FT05A finalization state is incomplete")
    output_root = _validate_namespace_path(
        output_root, "FT05A output root", output_root)
    manifest_path = _validate_namespace_path(
        manifest_path, "FT05_B_feature_manifest", output_root,
        allow_ft_namespace=True)
    canonical_table_path = os.path.realpath(
        os.path.join(output_root, "FT05A_B_technical_features.csv"))
    canonical_stage_root = os.path.realpath(os.path.join(output_root, ".finalize"))
    if not _is_contained(canonical_stage_root, output_root):
        raise FT05AValidationError("FT05 finalization stage escapes the FT05A namespace")
    canonical_stage_table = os.path.join(canonical_stage_root,
                                          "FT05A_B_technical_features.csv")
    canonical_stage_manifest = os.path.join(canonical_stage_root,
                                             "FT05_B_feature_manifest.json")
    path_values = {}
    for key, label in (("staged_table_path", "staged feature table"),
                       ("staged_manifest_path", "staged manifest"),
                       ("table_path", "final feature table"),
                       ("manifest_path", "final manifest")):
        path_values[key] = _absolute_project_path(transaction[key], label)
    if os.path.realpath(path_values["staged_table_path"]) != \
            os.path.realpath(canonical_stage_table) or \
            os.path.realpath(path_values["staged_manifest_path"]) != \
            os.path.realpath(canonical_stage_manifest) or \
            os.path.realpath(path_values["table_path"]) != canonical_table_path or \
            os.path.realpath(path_values["manifest_path"]) != os.path.realpath(manifest_path):
        raise FT05AValidationError("FT05 finalization paths are outside the canonical transaction")
    if os.path.isdir(canonical_stage_root):
        allowed_stage_names = {
            os.path.basename(canonical_stage_table),
            os.path.basename(canonical_stage_manifest),
        }
        if set(os.listdir(canonical_stage_root)) - allowed_stage_names:
            raise FT05AValidationError("FT05 finalization namespace contains unexpected files")
    if any(not re.match(r"^[0-9a-f]{64}$", str(transaction[key]))
           for key in ("table_sha256", "manifest_sha256", "run_identity_sha256",
                       "cohort_sha256", "case_completion_evidence_hash",
                       "w_original_asset_sha256")):
        raise FT05AValidationError("FT05 finalization hashes are invalid")

    expected_state = _initial_run_state(
        state.get("run_id"), cohort, contract["lock"], contract["code_audit"],
        output_root)
    if state.get("schema_version") != FT05A_SCHEMA_VERSION or \
            state.get("artifact_id") != "FT05A_run_state" or \
            state.get("run_identity_sha256") != expected_state["run_identity_sha256"] or \
            state.get("identity_payload") != expected_state["identity_payload"] or \
            transaction["run_identity_sha256"] != state.get("run_identity_sha256") or \
            transaction["cohort_sha256"] != expected_state["identity_payload"]["cohort_sha256"] or \
            state.get("target_patient_count") != len(cohort) or \
            state.get("target_patient_ids_hash") != _sha256_text(
                "\n".join(cohort["patient_id"].astype(str))):
        raise FT05AValidationError("FT05 finalization state identity is inconsistent")
    _validate_state_case_keys(state, cohort)
    expected_ordered_keys = [_case_identity(row) for _, row in cohort.iterrows()]
    expected_keys = sorted(expected_ordered_keys)
    if transaction["completed_case_keys"] != expected_keys or \
            state.get("completed_case_keys") != expected_keys or \
            int(transaction["completed_case_count"]) != len(expected_keys) or \
            int(state.get("completed_case_count", -1)) != len(expected_keys) or \
            transaction["completed_case_artifact_hashes"] != \
            state.get("completed_case_artifact_hashes") or \
            set(transaction["completed_case_artifact_hashes"]) != set(expected_keys):
        raise FT05AValidationError("FT05 finalization case-completion state is inconsistent")
    if any(not re.match(r"^[0-9a-f]{64}$", str(value))
           for value in transaction["completed_case_artifact_hashes"].values()):
        raise FT05AValidationError("FT05 finalization artifact hashes are invalid")
    evidence_hash = _sha256_text(_canonical_json(
        transaction["completed_case_artifact_hashes"]))
    if transaction["case_completion_evidence_hash"] != evidence_hash or \
            state.get("finalization", {}).get("case_completion_evidence_hash") != evidence_hash:
        raise FT05AValidationError("FT05 finalization completion evidence is inconsistent")
    if transaction["w_original_asset_path"] != w_asset.get("path") or \
            transaction["w_original_asset_sha256"] != w_asset.get("sha256") or \
            transaction["w_original_order_sha256"] != W_ORIGINAL_ORDER_SHA256:
        raise FT05AValidationError("FT05 finalization W_Original binding is inconsistent")

    case_root = os.path.realpath(os.path.join(output_root, "cases"))
    if not _is_contained(case_root, output_root):
        raise FT05AValidationError("FT05 case namespace escapes the FT05A namespace")
    completed, source_records = _reconcile_existing_cases(
        state, cohort, contract, w_asset, case_root)
    if sorted(completed) != expected_keys:
        raise FT05AValidationError("FT05 finalization is missing completed case evidence")
    staged_table = path_values["staged_table_path"]
    staged_manifest = path_values["staged_manifest_path"]
    table_source = _finalization_source(
        staged_table, canonical_table_path, transaction["table_sha256"],
        "feature table")
    manifest_source = _finalization_source(
        staged_manifest, path_values["manifest_path"], transaction["manifest_sha256"],
        "manifest")
    try:
        table = pd.read_csv(table_source)
    except (IOError, OSError, ValueError) as exc:
        raise FT05AValidationError("cannot read staged FT05 technical table: %s" % exc)
    _validate_technical_table_frame(table)
    manifest = _read_json(manifest_source, "staged FT05 manifest")
    checked, checked_table, _ = validate_ft05a_technical_manifest(
        manifest, output_root=output_root, _table_override=table,
        _table_hash_path=table_source, _expected_w_asset=w_asset,
        _expected_cohort=cohort, _expected_lock=contract["lock"])
    if checked.get("run_identity") != state["run_identity_sha256"] or \
            checked.get("feature_table", {}).get("path") != _relative(canonical_table_path) or \
            checked.get("feature_table", {}).get("sha256") != transaction["table_sha256"] or \
            checked.get("completion", {}).get("case_completion_evidence_hash") != evidence_hash or \
            checked.get("completion", {}).get("completed_case_count") != len(expected_keys) or \
            checked.get("source_records") != [source_records[key]
                                               for key in expected_ordered_keys]:
        raise FT05AValidationError("FT05 finalization table/manifest binding is inconsistent")
    _assert_table_matches_cases(
        checked_table, cohort, contract, w_asset, source_records,
        transaction["completed_case_artifact_hashes"], case_root)

    _install_staged_file(staged_table, canonical_table_path,
                         transaction["table_sha256"], "feature table")
    _install_staged_file(staged_manifest, path_values["manifest_path"],
                         transaction["manifest_sha256"], "manifest")
    manifest, _, _ = validate_ft05a_technical_manifest(
        path_values["manifest_path"], output_root=output_root,
        _expected_w_asset=w_asset, _expected_cohort=cohort,
        _expected_lock=contract["lock"])
    state["status"] = "COMPLETED"
    state["feature_table_path"] = _relative(canonical_table_path)
    state["feature_table_sha256"] = transaction["table_sha256"]
    state["manifest_path"] = _relative(path_values["manifest_path"])
    state["manifest_sha256"] = transaction["manifest_sha256"]
    state["completed_case_count"] = int(transaction["completed_case_count"])
    state["completed_at_epoch"] = time.time()
    state.pop("technical_audit_path", None)
    state.pop("technical_audit_sha256", None)
    state["finalization"] = None
    _update_state(state_path, state)
    for path in (staged_table, staged_manifest):
        if os.path.exists(path):
            os.remove(path)
    stage_root = os.path.dirname(staged_table)
    if os.path.isdir(stage_root) and not os.listdir(stage_root):
        os.rmdir(stage_root)
    return manifest


def _finalize_manifest(contract, cohort, records, run_state, output_root,
                       manifest_path, technical_audit_path, code_audit_path,
                       w_asset, state_path):
    code_audit = _validate_code_audit(code_audit_path)
    technical_audit = _validate_technical_audit(technical_audit_path)
    _validate_technical_audit_binding(
        technical_audit,
        _technical_audit_expected(
            run_state, cohort, contract, w_asset, code_audit))
    rows = []
    for _, record in cohort.iterrows():
        path = _case_result_path(os.path.join(output_root, "cases"), record)
        key = _case_identity(record)
        artifact = _validate_case_artifact(
            path, record, contract, w_asset["rows"][str(record["patient_id"])],
            source_record=records[key],
            expected_artifact_sha256=run_state["completed_case_artifact_hashes"][key])
        rows.append(artifact["row"])
    table = pd.DataFrame(rows, columns=_technical_feature_columns(True))
    if len(table) != len(cohort) or table["patient_id"].duplicated().any():
        raise FT05AValidationError("canonical table completeness/uniqueness failed")
    _validate_technical_table_frame(table)
    table_path = os.path.join(output_root, "FT05A_B_technical_features.csv")
    stage_root = os.path.join(output_root, ".finalize")
    if os.path.exists(stage_root):
        raise FT05AValidationError("unfinished FT05A finalization namespace exists")
    os.makedirs(stage_root)
    staged_table_path = os.path.join(stage_root, "FT05A_B_technical_features.csv")
    try:
        _write_csv_atomic(table, staged_table_path)
        table_hash = _sha256_file(staged_table_path)
        ordered_source_records = [records[_case_identity(record)]
                                  for _, record in cohort.iterrows()]
        manifest = _build_manifest(
            contract, cohort, table, table_path, table_hash, run_state, w_asset,
            code_audit, technical_audit, ordered_source_records)
        _validate_namespace_path(manifest_path, "FT05_B_feature_manifest",
                                 output_root, allow_ft_namespace=True)
        staged_manifest_path = os.path.join(stage_root, "FT05_B_feature_manifest.json")
        _write_json_atomic(staged_manifest_path, manifest, refuse_existing=True)
    except Exception:
        for path in (staged_table_path,
                     os.path.join(stage_root, "FT05_B_feature_manifest.json")):
            if os.path.exists(path):
                os.remove(path)
        if os.path.isdir(stage_root) and not os.listdir(stage_root):
            os.rmdir(stage_root)
        raise
    artifact_hashes = dict(run_state.get("completed_case_artifact_hashes", {}))
    completion_evidence_hash = _sha256_text(_canonical_json(artifact_hashes))
    transaction = OrderedDict((
        ("transaction_schema_version", "1"),
        ("run_identity_sha256", run_state["run_identity_sha256"]),
        ("cohort_sha256", run_state["identity_payload"]["cohort_sha256"]),
        ("staged_table_path", _relative(staged_table_path)),
        ("staged_manifest_path", _relative(staged_manifest_path)),
        ("table_path", _relative(table_path)),
        ("manifest_path", _relative(manifest_path)),
        ("table_sha256", table_hash),
        ("manifest_sha256", _sha256_file(staged_manifest_path)),
        ("completed_case_count", int(len(table))),
        ("completed_case_keys", sorted(artifact_hashes)),
        ("completed_case_artifact_hashes", artifact_hashes),
        ("case_completion_evidence_hash", completion_evidence_hash),
        ("w_original_asset_path", w_asset["path"]),
        ("w_original_asset_sha256", w_asset["sha256"]),
        ("w_original_order_sha256", w_asset["order_sha256"]),
    ))
    run_state["status"] = "FINALIZING"
    run_state["finalization"] = transaction
    _update_state(state_path, run_state)
    return _recover_finalization(
        run_state, state_path, contract=contract, cohort=cohort, w_asset=w_asset,
        output_root=output_root, manifest_path=manifest_path)


def run_ft05a(cohort, run_id, lock_path=DEFAULT_LOCK, output_root=DEFAULT_OUTPUT_ROOT,
              manifest_path=DEFAULT_MANIFEST, code_audit_path=DEFAULT_CODE_AUDIT,
              technical_audit_path=DEFAULT_TECHNICAL_AUDIT, processor=None,
              resume=False, pilot_case_ids=None, w_original_path=None,
              pilot_size=None):
    """Run or safely resume FT05A.

    ``pilot_case_ids`` is a non-overlapping technical pilot.  It records case
    completion in the same one-time state and never writes the frozen manifest
    until a later full invocation resumes the same run identity.
    """
    output_root = _validate_namespace_path(output_root, "FT05A output root",
                                           output_root, allow_ft_namespace=False)
    manifest_path = _validate_namespace_path(
        manifest_path, "FT05_B_feature_manifest", output_root,
        allow_ft_namespace=True)
    code_audit_path = _validate_namespace_path(
        code_audit_path, "FT05A code audit", output_root, allow_ft_namespace=True)
    technical_audit_path = _validate_namespace_path(
        technical_audit_path, "FT05A technical audit", output_root,
        allow_ft_namespace=True)
    # This is the only entry point that may turn a technical cohort into a
    # readable frame. The FT04 lock/review, code audit, and static safety
    # checks all complete before it is called.
    contract = validate_ft05a_preflight(lock_path, code_audit_path)
    static = static_validate()
    if not static["pass"]:
        raise FT05AValidationError("FT05A static safety validation failed: %s" % static["findings"])
    cohort_frame = load_technical_cohort(
        cohort, _preflight=_PREFLIGHT_TOKEN,
        technical_source_roots=contract.get("technical_source_roots",
                                            ALLOWED_TECHNICAL_ROOTS),
        accepted_w_path=contract.get("w_original_path"))
    if pilot_size is not None:
        if pilot_case_ids is not None or pilot_size <= 0 or \
                pilot_size > len(cohort_frame):
            raise FT05AValidationError(
                "pilot_size must be within the technical cohort")
        pilot_case_ids = list(cohort_frame["patient_id"].astype(str).head(pilot_size))
    output_root = os.path.realpath(CANONICAL_OUTPUT_ROOT)
    state_path = os.path.join(output_root, "FT05A_run_state.json")
    expected = _initial_run_state(run_id, cohort_frame, contract["lock"],
                                  contract["code_audit"], output_root)

    def validate_identity_migration(candidate):
        """Validate completed evidence before changing the persisted identity."""
        completed_before = list(candidate.get("completed_case_keys", []))
        hashes_before = copy.deepcopy(
            candidate.get("completed_case_artifact_hashes", {}))
        pilot_before = list(candidate.get("pilot_case_keys", []))
        case_root = os.path.join(output_root, "cases")
        if not completed_before:
            raise FT05AValidationError(
                "FT05A identity migration requires completed case evidence")
        if not os.path.isdir(case_root):
            raise FT05AValidationError(
                "FT05A migration cannot validate missing case namespace")
        if any(not os.path.isfile(os.path.join(case_root, name))
               for name in os.listdir(case_root)):
            raise FT05AValidationError(
                "FT05A migration found a non-file case artifact")
        # Migration must establish the accepted asset binding from the full
        # file before it can replace the persisted run identity.  Normal pilot
        # loading still passes selected_patient_ids and retains its streaming
        # subset behavior.
        migration_w_asset = _load_w_original_asset(
            contract["lock"], w_original_path)
        expected_w_binding = _w_original_binding_from_lock(contract["lock"])
        if migration_w_asset.get("path") != expected_w_binding["path"] or \
                migration_w_asset.get("sha256") != \
                expected_w_binding["asset_sha256"] or \
                migration_w_asset.get("feature_count") != 107 or \
                migration_w_asset.get("order_sha256") != \
                W_ORIGINAL_ORDER_SHA256:
            raise FT05AValidationError(
                "FT05A migration W_Original binding is inconsistent")
        expected_w_ids = set(cohort_frame["patient_id"].astype(str))
        if expected_w_ids - set(migration_w_asset.get("rows", {})):
            raise FT05AValidationError(
                "FT05A migration W_Original asset does not cover the cohort")
        checked = copy.deepcopy(candidate)
        _reconcile_existing_cases(
            checked, cohort_frame, contract, migration_w_asset, case_root)
        if checked.get("completed_case_keys") != completed_before or \
                checked.get("completed_case_count") != len(completed_before) or \
                checked.get("completed_case_artifact_hashes") != hashes_before or \
                checked.get("pilot_case_keys") != pilot_before:
            raise FT05AValidationError(
                "FT05A migration would change completed-case evidence")

    owner_path, owner = _acquire_run_ownership(
        output_root, expected["run_identity_sha256"])
    try:
        state = _load_or_create_state(
            state_path, expected, resume, code_audit=contract["code_audit"],
            cohort=cohort_frame, manifest_path=manifest_path,
            migration_validator=validate_identity_migration)
        if state.get("status") == TECHNICAL_COMPLETE_PENDING_REVIEW and \
                state.get("technical_audit_path") != _relative(technical_audit_path):
            raise FT05AValidationError(
                "FT05A pending state is bound to a different technical audit")
        _validate_state_case_keys(state, cohort_frame)
        _refuse_existing_manifest(manifest_path, state)
        if state.get("status") == "FINALIZING":
            if not resume:
                raise FT05AValidationError(
                    "unfinished FT05A finalization requires explicit resume")
            recovery_w_asset = _load_w_original_asset(contract["lock"], w_original_path)
            if sorted(set(cohort_frame["patient_id"]) -
                       set(recovery_w_asset["rows"])):
                raise FT05AValidationError(
                    "accepted W_Original asset does not cover the technical cohort")
            return _recover_finalization(
                state, state_path, contract=contract, cohort=cohort_frame,
                w_asset=recovery_w_asset, output_root=output_root,
                manifest_path=manifest_path)
        state["status"] = "RUNNING"
        _update_state(state_path, state)
        by_id = {str(row["patient_id"]): row
                 for _, row in cohort_frame.iterrows()}
        existing_pilot_keys = set(state.get("pilot_case_keys", []))
        if pilot_case_ids is None:
            selected_ids = list(cohort_frame["patient_id"].astype(str))
            pilot = False
        else:
            selected_ids = [str(value).strip() for value in pilot_case_ids]
            if not selected_ids or len(selected_ids) != len(set(selected_ids)) or \
                    not set(selected_ids).issubset(set(by_id)):
                raise FT05AValidationError(
                    "pilot case IDs are not a unique subset of the technical cohort")
            selected_keys = {_case_identity(by_id[value]) for value in selected_ids}
            if existing_pilot_keys and selected_keys != existing_pilot_keys:
                raise FT05AValidationError(
                    "pilot resume must use the original pilot case set")
            pilot = True
            state["pilot_case_keys"] = sorted(existing_pilot_keys | selected_keys)
        w_asset = _load_w_original_asset(
            contract["lock"], w_original_path,
            selected_patient_ids=selected_ids if pilot else None)
        required_w_ids = selected_ids if pilot else list(by_id)
        missing_w = sorted(set(required_w_ids) - set(w_asset["rows"]))
        if missing_w:
            raise FT05AValidationError(
                "accepted W_Original asset does not cover the technical cohort")
        case_root = os.path.join(output_root, "cases")
        os.makedirs(case_root, exist_ok=True)
        completed, source_record_map = _reconcile_existing_cases(
            state, cohort_frame, contract, w_asset, case_root)
        processor = processor or _default_process_case
        for patient_id in selected_ids:
            record = by_id[patient_id]
            key = _case_identity(record)
            case_path = _case_result_path(case_root, record)
            if key in completed:
                _validate_case_artifact(
                    case_path, record, contract, w_asset["rows"][patient_id],
                    source_record=source_record_map[key],
                    expected_artifact_sha256=state[
                        "completed_case_artifact_hashes"][key])
                continue
            started = time.time()
            try:
                source_record = _source_record(
                    record, w_asset, contract.get("technical_source_roots"))
                result = processor(dict(record), contract)
                row = _flatten_case_result(
                    record, result, w_asset["rows"][patient_id], contract)
                artifact = OrderedDict((
                    ("schema_version", FT05A_SCHEMA_VERSION),
                    ("artifact_id", "FT05A_case"),
                    ("status", "complete"), ("patient_id", patient_id),
                    ("case_identity_sha256", key), ("row", row),
                    ("processor_result", result),
                    ("processor_result_sha256", _processor_result_hash(result)),
                    ("flattened_row_sha256", _row_hash(row)),
                    ("row_schema_sha256", _row_schema_hash()),
                    ("w_original_row_sha256",
                     _w_original_row_hash(w_asset["rows"][patient_id])),
                    ("elapsed_seconds", float(time.time() - started)),
                    ("input_source_record", source_record),
                    ("input_source_record_sha256",
                     _source_record_hash(source_record)),
                ))
                _write_json_atomic(case_path, artifact, refuse_existing=True)
                artifact_hash = _sha256_file(case_path)
                completed.add(key)
                source_record_map[key] = source_record
                state["completed_case_keys"] = sorted(completed)
                state["completed_case_artifact_hashes"][key] = artifact_hash
                state["completed_case_count"] = len(completed)
                _update_state(state_path, state)
            except Exception as exc:
                state["status"] = "FAILED"
                state["failed_cases"] = list(state.get("failed_cases", [])) + [{
                    "case_identity_sha256": key,
                    "patient_id_hash": _sha256_text(patient_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }]
                _update_state(state_path, state)
                raise FT05ARunError(
                    "FT05A technical failure for one case: %s" % exc)
        if pilot:
            state["status"] = "PILOT_COMPLETE"
            state["pilot_completed_at_epoch"] = time.time()
            _update_state(state_path, state)
            return {"status": state["status"], "run_state": state,
                    "completed_case_count": int(state["completed_case_count"])}
        if len(completed) != len(cohort_frame):
            raise FT05ARunError(
                "FT05A cannot finalize with incomplete case completion")
        if set(source_record_map) != set(completed):
            raise FT05AValidationError("FT05A source-record completion is incomplete")
        technical_audit = _ensure_technical_generation_audit(
            technical_audit_path, state, cohort_frame, contract, w_asset,
            contract["code_audit"])
        if technical_audit["status"] != "accepted":
            state["status"] = TECHNICAL_COMPLETE_PENDING_REVIEW
            state["technical_audit_path"] = _relative(technical_audit_path)
            state["technical_audit_sha256"] = technical_audit["sha256"]
            _update_state(state_path, state)
            return {
                "status": TECHNICAL_COMPLETE_PENDING_REVIEW,
                "run_state": state,
                "technical_audit": technical_audit,
                "completed_case_count": int(state["completed_case_count"]),
            }
        manifest = _finalize_manifest(
            contract, cohort_frame, source_record_map, state, output_root,
            manifest_path, technical_audit_path, code_audit_path, w_asset,
            state_path)
        return manifest
    finally:
        _release_run_ownership(owner_path, owner)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("static-validate", "run"))
    parser.add_argument("--cohort")
    parser.add_argument("--run-id", default="FT05A-20260912")
    parser.add_argument("--lock", default=DEFAULT_LOCK)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--code-audit", default=DEFAULT_CODE_AUDIT)
    parser.add_argument("--technical-audit", default=DEFAULT_TECHNICAL_AUDIT)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pilot-size", type=int)
    args = parser.parse_args()
    if args.command == "static-validate":
        print(json.dumps(static_validate(), ensure_ascii=False, sort_keys=True))
        return
    if not args.cohort:
        raise SystemExit("--cohort is required for run")
    result = run_ft05a(
        args.cohort, args.run_id, lock_path=args.lock, output_root=args.output_root,
        manifest_path=args.manifest, code_audit_path=args.code_audit,
        technical_audit_path=args.technical_audit, resume=args.resume,
        pilot_size=args.pilot_size)
    payload = {"status": result.get("status", "COMPLETED"),
               "artifact_id": result.get("artifact_id"),
               "row_count": result.get("feature_table", {}).get("row_count")}
    if result.get("status") == TECHNICAL_COMPLETE_PENDING_REVIEW:
        payload["technical_audit"] = result.get("technical_audit", {}).get("path")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
