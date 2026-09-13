"""Aggregate-only Primary v2 final report and basic metric helpers."""
from __future__ import absolute_import

import argparse
import json
import os
import sys

import numpy as np

try:
    from . import validate_assets as va
    from . import refit_freeze
    from . import validate_external
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    import validate_assets as va
    import refit_freeze
    import validate_external


class FinalReportError(va.PrimaryValidationError):
    """Raised when an aggregate report cannot be built from frozen records."""


def _engine():
    script_root = os.path.join(va.PROJECT_ROOT, "prognosis_analysis", "scripts")
    if script_root not in sys.path:
        sys.path.insert(0, script_root)
    try:
        import w08_nested_cv as engine
    except ImportError as exc:
        raise FinalReportError("canonical metric engine is unavailable: %s" % exc)
    return engine


def basic_survival_metrics(time, event, risk):
    """Return only compact discrimination metrics for a protected evaluation."""
    time = np.asarray(time, dtype=float)
    event = np.asarray(event, dtype=int)
    risk = np.asarray(risk, dtype=float)
    if not (len(time) == len(event) == len(risk)) or len(time) == 0:
        raise FinalReportError("metric vectors are not aligned")
    if not np.isfinite(time).all() or not np.isfinite(risk).all() or \
            not np.isin(event, [0, 1]).all():
        raise FinalReportError("metric vectors are invalid")
    engine = _engine()
    return {
        "Harrell_C_index": _number(engine.harrell_c_index(time, event, risk)),
        "metric_scope": "aggregate helper; censoring-weighted metrics require protected training reference",
    }


def _number(value):
    value = float(value)
    return None if not np.isfinite(value) else value


def _load_json(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise FinalReportError("%s is unavailable: %s" % (label, exc))
    if not isinstance(value, dict):
        raise FinalReportError("%s must be an object" % label)
    return value


def build_final_report(manifest, lock, external_registration):
    """Build a shareable report from aggregate metadata only."""
    protocol_path = va.DEFAULT_PROTOCOL
    va.validate_evidence_manifest(manifest, protocol_path)
    refit_freeze.validate_canonical_lock(lock, protocol_path)
    validate_external.validate_external_registration(
        external_registration, lock, manifest, protocol_path)
    ft03 = manifest.get("evidence", {}).get("FT03", {})
    ft04 = manifest.get("evidence", {}).get("FT04", {})
    ft06 = manifest.get("evidence", {}).get("FT06", {})
    return """# Primary Prognostic Analysis v2 — canonical evidence report

Status: **registered canonical transition; no patient-level recomputation**

## Scientific identity

- Fixed full-A habitat: 3D SLIC at 4 mm, cross-case K-means `K=2`, `n_init=100`.
- A validation: one repeat-1 outer five-fold design; all preprocessing and lambda selection are training-only.
- Penalized models use LASSO-Cox with `alpha=1`; M0–M5 remain registered.
- B is frozen-prediction-only, with no refit, tuning, cutoff optimization, habitat refit, candidate reselection, or B→A feedback.

## Promoted evidence

- FT03 A validation: `{ft03_status}`; source `{ft03_path}` (`{ft03_sha}`).
- FT04 model freeze: `{ft04_status}`; source identity `{ft04_identity}` and serialized hash `{ft04_serialized}`.
- FT06 B validation: `{ft06_status}`, disposition `{ft06_disposition}`; source `{ft06_path}` (`{ft06_sha}`).

The technical-screening reference B=107 and the FT06 authorized validation denominator B=163 are distinct source identities and are not merged.

## Timing disclosure

The B prediction was frozen before B evaluation. The Primary-v2 promotion decision occurred after FT B results were available; this is a post-FT protocol transition and is not described as retrospective prespecification.

## Freeze verification boundary

The canonical lock records accepted FT04 model identities, predictor order hashes, lambda-selection metadata, and model-state hashes. Coefficient-body verification requires the protected runtime state; no patient-level coefficients, predictions, or outcomes are copied into this report.
""".format(
        ft03_status=ft03.get("status", "UNKNOWN"),
        ft03_path=ft03.get("aggregate", {}).get("path", "UNKNOWN"),
        ft03_sha=ft03.get("aggregate", {}).get("sha256", "UNKNOWN"),
        ft04_status=ft04.get("status", "UNKNOWN"),
        ft04_identity=ft04.get("lock", {}).get("identity_sha256", "UNKNOWN"),
        ft04_serialized=ft04.get("lock", {}).get("serialized_sha256", "UNKNOWN"),
        ft06_status=ft06.get("status", "UNKNOWN"),
        ft06_disposition=ft06.get("final_disposition", "UNKNOWN"),
        ft06_path=ft06.get("aggregate", {}).get("path", "UNKNOWN"),
        ft06_sha=ft06.get("aggregate", {}).get("sha256", "UNKNOWN"),
    )


def main(argv=None):  # pragma: no cover - aggregate registration CLI
    parser = argparse.ArgumentParser(description="Build Primary v2 aggregate report")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--lock", required=True)
    parser.add_argument("--external", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    report = build_final_report(
        _load_json(args.manifest, "evidence manifest"),
        _load_json(args.lock, "canonical lock"),
        _load_json(args.external, "external registration"),
    )
    target = os.path.abspath(args.output)
    parent = os.path.dirname(target)
    if not os.path.isdir(parent):
        raise FinalReportError("output parent does not exist: %s" % parent)
    temporary = target + ".tmp-primary-v2"
    try:
        with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(report)
            if not report.endswith("\n"):
                handle.write("\n")
        os.replace(temporary, target)
    except Exception:
        if os.path.exists(temporary):
            os.remove(temporary)
        raise
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
