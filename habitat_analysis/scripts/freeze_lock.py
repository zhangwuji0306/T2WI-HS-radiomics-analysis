"""Create and validate the outcome-unlock lock for the habitat workflow."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone


FORMAL_BOOTSTRAPS = 1000


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


def validate_freeze_lock(path, expected=None):
    if not os.path.exists(path):
        raise RuntimeError("freeze_lock.json is missing; outcome/B access remains locked")
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    bootstrap = {
        "bootstrap_mode": payload.get("bootstrap_mode"),
        "n_bootstrap_requested": payload.get("bootstrap_requested"),
        "n_bootstrap_completed": payload.get("bootstrap_completed"),
        "completion_status": payload.get("bootstrap_completion_status"),
        "bootstrap_operational_pass": payload.get("bootstrap_operational_pass"),
        "formal_eligible": payload.get("formal_eligible"),
    }
    errors = validate_formal_bootstrap(bootstrap)
    if payload.get("outcome_columns_read") not in (False, 0):
        errors.append("outcome_columns_read is not false")
    if payload.get("B_data_read") not in (False, 0):
        errors.append("B_data_read is not false")
    for key, value in (expected or {}).items():
        if payload.get(key) != value:
            errors.append("%s does not match current inputs" % key)
    if errors:
        raise RuntimeError("invalid freeze lock: " + "; ".join(errors))
    return payload
