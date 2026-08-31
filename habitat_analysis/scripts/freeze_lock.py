"""Create and validate the technical-freeze lock for the habitat workflow."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
from datetime import datetime, timezone


FORMAL_BOOTSTRAPS = 1000
FREEZE_SCHEMA_VERSION = "1.0"
SHA256_LENGTH = 64

REQUIRED_FREEZE_FIELDS = {
    "freeze_schema_version": FREEZE_SCHEMA_VERSION,
    "habitat_technical_freeze": True,
    "A_outcome_unlock": True,
    "B_unlock": False,
    "bootstrap_mode": "formal",
    "bootstrap_requested": FORMAL_BOOTSTRAPS,
    "bootstrap_completed": FORMAL_BOOTSTRAPS,
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

REQUIRED_ARTIFACT_HASH_FIELDS = (
    "A393_id_hash",
    "A137_id_hash",
    "manifest_hash",
    "scanner_map_hash",
    "preprocessing_config_hash",
    "slic_config_hash",
    "high_signal_screen_hash",
    "formal_bootstrap_summary_hash",
    "global_descriptors_hash",
    "feature_qc_hash",
    "feature_dictionary_hash",
    "threshold_audit_hash",
    "threshold_confounding_audit_hash",
    "habitat_map_manifest_hash",
)


def _is_sha256(value):
    return (isinstance(value, str) and len(value) == SHA256_LENGTH and
            all(char in "0123456789abcdef" for char in value))


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def files_sha256(paths):
    digest = hashlib.sha256()
    for path in sorted(os.path.abspath(value) for value in paths):
        digest.update(os.path.basename(path).encode("utf-8"))
        digest.update(file_sha256(path).encode("ascii"))
    return digest.hexdigest()


def id_hash(values):
    normalized = sorted({str(value).strip() for value in values})
    return hashlib.sha256(("\n".join(normalized) + "\n").encode("utf-8")).hexdigest()


def _resolve_path(path, artifact_root):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("artifact path must be a non-empty string")
    if os.path.isabs(path):
        return os.path.abspath(path)
    return os.path.abspath(os.path.join(artifact_root, path))


def _read_id_column(path, column):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or column not in reader.fieldnames:
            raise ValueError("%s lacks identifier column %s" % (path, column))
        return [row[column] for row in reader]


def _validate_manifest_path(path, map_root):
    if not isinstance(path, str) or not path.strip():
        raise ValueError("manifest path must be a non-empty string")
    if os.path.isabs(path):
        raise ValueError("artifact paths in the lock must be relative")
    normalized = path.replace("\\", "/")
    if normalized in ("", ".") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("manifest path escapes the map root: %s" % path)
    resolved_root = os.path.abspath(map_root)
    resolved = os.path.abspath(os.path.join(resolved_root, *normalized.split("/")))
    try:
        inside = os.path.commonpath([resolved_root, resolved]) == resolved_root
    except ValueError:
        inside = False
    if not inside:
        raise ValueError("manifest path escapes the map root: %s" % path)
    return resolved


def write_habitat_map_manifest(map_root, manifest_path):
    """Write a deterministic patient/map-content manifest for a map directory."""
    map_root = os.path.abspath(map_root)
    rows = []
    if not os.path.isdir(map_root):
        raise RuntimeError("habitat map directory is missing: %s" % map_root)
    for current_root, directories, filenames in os.walk(map_root):
        directories.sort()
        for filename in sorted(filenames):
            path = os.path.join(current_root, filename)
            relative_path = os.path.relpath(path, map_root).replace(os.sep, "/")
            suffix = "_R1_habitat.nrrd"
            patient_id = filename[:-len(suffix)] if filename.endswith(suffix) else os.path.splitext(filename)[0]
            rows.append({"patient_id": patient_id, "relative_path": relative_path,
                         "sha256": file_sha256(path)})
    if not rows:
        raise RuntimeError("habitat map directory contains no files: %s" % map_root)
    rows.sort(key=lambda row: row["relative_path"])
    directory = os.path.dirname(os.path.abspath(manifest_path))
    os.makedirs(directory, exist_ok=True)
    temporary = manifest_path + ".tmp"
    try:
        with open(temporary, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["patient_id", "relative_path", "sha256"])
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, manifest_path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return manifest_path


def validate_habitat_map_manifest(manifest_path, map_root):
    """Validate manifest schema, map membership, and every listed map hash."""
    map_root = os.path.abspath(map_root)
    if not os.path.isdir(map_root):
        raise RuntimeError("habitat map directory is missing: %s" % map_root)
    with open(manifest_path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"patient_id", "relative_path", "sha256"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("habitat map manifest lacks required columns")
        rows = list(reader)
    if not rows:
        raise RuntimeError("habitat map manifest is empty")
    seen_paths = set()
    seen_ids = set()
    for row in rows:
        relative_path = row.get("relative_path", "")
        patient_id = row.get("patient_id", "")
        if relative_path in seen_paths or patient_id in seen_ids:
            raise RuntimeError("habitat map manifest contains duplicate entries")
        seen_paths.add(relative_path)
        seen_ids.add(patient_id)
        path = _validate_manifest_path(relative_path, map_root)
        if not os.path.isfile(path):
            raise RuntimeError("habitat map listed in manifest is missing: %s" % relative_path)
        expected = row.get("sha256", "")
        if not _is_sha256(expected) or file_sha256(path) != expected:
            raise RuntimeError("habitat map hash mismatch: %s" % relative_path)
    actual_paths = set()
    for current_root, directories, filenames in os.walk(map_root):
        directories.sort()
        for filename in sorted(filenames):
            actual_paths.add(os.path.relpath(os.path.join(current_root, filename), map_root).replace(os.sep, "/"))
    if actual_paths != seen_paths:
        raise RuntimeError("habitat map directory does not match its manifest")
    return rows


def _artifact_spec_paths(spec, artifact_root):
    if isinstance(spec, str):
        return [_resolve_path(spec, artifact_root)]
    if isinstance(spec, list) and spec and all(isinstance(value, str) for value in spec):
        return [_resolve_path(value, artifact_root) for value in spec]
    raise ValueError("artifact path specification must be a path or non-empty path list")


def _hash_artifact_spec(spec, artifact_root):
    if isinstance(spec, dict):
        kind = spec.get("kind", "file")
        if kind == "id_hash":
            path = _resolve_path(spec.get("path"), artifact_root)
            return id_hash(_read_id_column(path, spec.get("column", "影像号")))
        if kind == "habitat_map_manifest":
            path = _resolve_path(spec.get("path"), artifact_root)
            map_root = _resolve_path(spec.get("map_root"), artifact_root)
            validate_habitat_map_manifest(path, map_root)
            return file_sha256(path)
        raise ValueError("unsupported artifact kind: %s" % kind)
    paths = _artifact_spec_paths(spec, artifact_root)
    return file_sha256(paths[0]) if len(paths) == 1 else files_sha256(paths)


def compute_artifact_hashes(artifact_paths, artifact_root=None):
    """Compute the hashes represented by a lock's artifact path specifications."""
    artifact_root = os.path.abspath(artifact_root or os.getcwd())
    missing = [field for field in REQUIRED_ARTIFACT_HASH_FIELDS
               if field not in artifact_paths]
    if missing:
        raise RuntimeError("artifact path specifications missing: " + ", ".join(missing))
    return {field: _hash_artifact_spec(artifact_paths[field], artifact_root)
            for field in REQUIRED_ARTIFACT_HASH_FIELDS}


def validate_artifact_hashes(payload, artifact_paths, artifact_root=None):
    """Hard-fail unless every recorded freeze artifact hash matches its content."""
    try:
        actual = compute_artifact_hashes(artifact_paths, artifact_root)
    except (OSError, ValueError, RuntimeError) as exc:
        raise RuntimeError("artifact hash validation failed: %s" % exc)
    errors = ["%s does not match current artifact" % field
              for field, value in actual.items() if payload.get(field) != value]
    if errors:
        raise RuntimeError("artifact hash validation failed: " + "; ".join(errors))
    return payload


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def atomic_write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                                     suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def validate_formal_bootstrap(summary):
    required = {
        "bootstrap_mode": "formal",
        "n_bootstrap_requested": FORMAL_BOOTSTRAPS,
        "n_bootstrap_completed": FORMAL_BOOTSTRAPS,
        "completion_status": "complete",
        "bootstrap_operational_pass": 1,
        "formal_eligible": 1,
    }
    errors = []
    for key, expected in required.items():
        actual = summary.get(key)
        if isinstance(expected, int):
            try:
                actual = int(float(actual))
            except (TypeError, ValueError):
                pass
        if actual != expected:
            errors.append("%s=%r (expected %r)" % (key, actual, expected))
    return errors


def _strict_equal(actual, expected):
    if isinstance(expected, bool):
        return type(actual) is bool and actual is expected
    if isinstance(expected, int):
        return type(actual) is int and actual == expected
    if isinstance(expected, float):
        return (isinstance(actual, (int, float)) and not isinstance(actual, bool) and
                math.isclose(float(actual), expected, rel_tol=0, abs_tol=0))
    return type(actual) is type(expected) and actual == expected


def _schema_errors(payload):
    errors = []
    for key, expected in REQUIRED_FREEZE_FIELDS.items():
        if key not in payload:
            errors.append("missing required field: %s" % key)
        elif not _strict_equal(payload[key], expected):
            errors.append("%s=%r (expected %r)" % (key, payload[key], expected))
    for key in REQUIRED_ARTIFACT_HASH_FIELDS:
        if key not in payload:
            errors.append("missing required artifact hash: %s" % key)
        elif not _is_sha256(payload[key]):
            errors.append("%s is not a lowercase SHA-256" % key)
    paths = payload.get("artifact_paths")
    if not isinstance(paths, dict):
        errors.append("missing required artifact_paths mapping")
    else:
        for key in REQUIRED_ARTIFACT_HASH_FIELDS:
            if key not in paths:
                errors.append("missing artifact path specification: %s" % key)
    return errors


def validate_freeze_lock(path, expected=None, artifact_paths=None, artifact_root=None):
    if not os.path.exists(path):
        raise RuntimeError("freeze_lock.json is missing; outcome/B access remains locked")
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise RuntimeError("invalid freeze lock: top-level JSON value must be an object")
    errors = _schema_errors(payload)
    for key, value in (expected or {}).items():
        if payload.get(key) != value:
            errors.append("%s does not match current inputs" % key)
    if errors:
        raise RuntimeError("invalid freeze lock: " + "; ".join(errors))
    if artifact_paths is None:
        artifact_paths = payload.get("artifact_paths")
    if artifact_paths is not None:
        artifact_root = artifact_root or os.path.dirname(os.path.abspath(path))
        validate_artifact_hashes(payload, artifact_paths, artifact_root)
    return payload
