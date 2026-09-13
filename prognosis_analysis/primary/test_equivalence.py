"""Synthetic-only equivalence checks for the Primary v2 canonical path.

No repository output, protected cohort, B outcome, or real patient identifier
is read by this test.  Numerical equivalence to the protected FT04
coefficients/predictions is intentionally reported as not evaluated here.
"""
from __future__ import absolute_import

import json
import os
import sys

import numpy as np
import pandas as pd

try:
    from . import validate_assets as va
    from .run_cv import CanonicalPreprocessor, fit_canonical_model, run_cv_for_testing
except (ImportError, ValueError):  # pragma: no cover - direct script execution
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import validate_assets as va
    from run_cv import CanonicalPreprocessor, fit_canonical_model, run_cv_for_testing


def synthetic_frame(n=50):
    rng = np.random.RandomState(20260913)
    output = {
        "patient_id": ["SYNTH-A-%03d" % (index + 1) for index in range(n)],
        "DFS_time": np.linspace(8.0, 80.0, n),
        "DFS_event": np.asarray([(index % 3 == 0) for index in range(n)], dtype=int),
        "年龄": 45.0 + np.arange(n),
        "CEA_log": np.log1p(np.arange(n) + 1.0),
        "thickness": 3.0 + rng.normal(0.0, 0.2, n),
        "EID": 4.0 + rng.normal(0.0, 0.3, n),
        "mrT_4级": [1 + (index % 4) for index in range(n)],
        "mrN_3级": [index % 4 for index in range(n)],
        "MRF": [index % 2 for index in range(n)],
        "mrEMVI": [(index + 1) % 2 for index in range(n)],
        "活检病理非腺癌": [1 if index % 7 == 0 else 0 for index in range(n)],
    }
    for index, column in enumerate(va.GLOBAL_COLUMNS):
        output[column] = rng.normal(index, 0.4, n)
    for index, name in enumerate(va.R_LOW_FEATURE_NAMES):
        output["R_low__" + name] = rng.normal(index * 0.01, 1.0, n)
    output["R_low_structurally_defined"] = 1
    output["R_low_technically_available"] = 1
    # Two synthetic structural absences exercise the eligibility boundary.
    output["R_low_structurally_defined"] = np.asarray(
        [0 if index >= n - 2 else 1 for index in range(n)], dtype=int)
    output["R_low_technically_available"] = np.asarray(
        [0 if index >= n - 2 else 1 for index in range(n)], dtype=int)
    return pd.DataFrame(output)


def synthetic_split(frame):
    ids = frame["patient_id"].astype(str).tolist()
    rows = []
    for fold in range(1, va.OUTER_FOLDS + 1):
        validation_ids = ids[fold - 1::va.OUTER_FOLDS]
        validation_set = set(validation_ids)
        for identifier in ids:
            if identifier not in validation_set:
                rows.append({"patient_id": identifier, "repeat": 1,
                             "fold": fold, "role": "train", "seed": va.OUTER_SEED})
        for identifier in validation_ids:
            rows.append({"patient_id": identifier, "repeat": 1,
                         "fold": fold, "role": "validation", "seed": va.OUTER_SEED})
    return pd.DataFrame(rows, columns=["patient_id", "repeat", "fold", "role", "seed"])


def run_equivalence_checks():
    frame = synthetic_frame()
    split = synthetic_split(frame)
    va.validate_predictor_frame(frame, ["M3L"], cohort="A", require_outcome=True)
    checked_split = va.validate_split(split, frame=frame)
    feature_order_pass = va.block_columns(frame, "R_low") == [
        "R_low__" + name for name in va.R_LOW_FEATURE_NAMES]
    eligibility = va.eligibility_mask(frame, "R_low")
    eligibility_pass = int(eligibility.sum()) == 48 and not bool(eligibility.iloc[-2:].any())

    train = frame.iloc[:40].copy().reset_index(drop=True)
    valid = frame.iloc[40:].copy().reset_index(drop=True)
    preprocessor = CanonicalPreprocessor("M0").fit(train)
    train_means_before = dict(preprocessor.clinical.means)
    valid.loc[:, "年龄"] = 9999.0
    preprocessor.transform(valid)
    preprocessing_pass = train_means_before == preprocessor.clinical.means and \
        float(preprocessor.clinical.means["年龄"]) < 1000.0

    fitted_one = fit_canonical_model(train, "M3L", seed=va.OUTER_SEED,
                                     lambda_count=3, max_iter=3000)
    fitted_two = fit_canonical_model(train, "M3L", seed=va.OUTER_SEED,
                                     lambda_count=3, max_iter=3000)
    deterministic_lambda_pass = (
        fitted_one["selection"]["alpha"] == va.ALPHA and
        fitted_one["selection"]["inner_folds"] == va.INNER_FOLDS and
        fitted_one["selection"]["outer_validation_used_for_lambda"] is False and
        fitted_one["selection"]["lambda_ratio"] == fitted_two["selection"]["lambda_ratio"]
    )
    coefficient_repeatability_pass = np.allclose(
        fitted_one["model"].coef_, fitted_two["model"].coef_,
        rtol=1e-10, atol=1e-10)
    cv_result = run_cv_for_testing(
        frame, checked_split, model_ids=["M3L"], max_iter=3000,
        lambda_count=3)
    metric_repeatability_pass = (
        cv_result["runs"]["M3L"]["outer_fold_count"] == va.OUTER_FOLDS and
        all(not fold["outer_validation_used_for_selection"]
            for fold in cv_result["runs"]["M3L"]["folds"])
    )
    return {
        "schema_version": "1.0",
        "artifact_id": "PRIMARY_V2_SYNTHETIC_EQUIVALENCE",
        "fixture": {"rows": int(len(frame)), "eligible_R_low": int(eligibility.sum()),
                     "B_outcome_read": False, "patient_level_source": False},
        "checks": {
            "feature_order": "PASS" if feature_order_pass else "FAIL",
            "eligibility": "PASS" if eligibility_pass else "FAIL",
            "training_only_preprocessing": "PASS" if preprocessing_pass else "FAIL",
            "lambda_selection_behavior": "PASS" if deterministic_lambda_pass else "FAIL",
            "canonical_coefficient_repeatability": "PASS" if coefficient_repeatability_pass else "FAIL",
            "canonical_fold_metric_contract": "PASS" if metric_repeatability_pass else "FAIL",
            "cross_artifact_coefficients": "NOT EVALUATED — requires protected FT04 runtime fixture",
            "cross_artifact_risk_predictions": "NOT EVALUATED — requires protected FT04 runtime fixture",
            "cross_artifact_metrics": "NOT EVALUATED — requires protected FT04 runtime fixture",
        },
        "split": {
            "repeat": int(checked_split["repeat"].iloc[0]),
            "folds": sorted(checked_split["fold"].unique().tolist()),
            "seed": int(checked_split["seed"].iloc[0]),
            "regenerated": False,
        },
        "interpretation": "Synthetic canonical behavior is repeatable; protected FT04 numerical identity remains a downstream runtime verification item.",
    }


def main():
    result = run_equivalence_checks()
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    failed = [key for key, value in result["checks"].items()
              if value == "FAIL"]
    return 1 if failed else 0


def test_synthetic_equivalence():
    """Pytest-compatible assertion for the same synthetic-only entry point."""
    result = run_equivalence_checks()
    assert all(value != "FAIL" for value in result["checks"].values())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
