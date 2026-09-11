"""Unit tests for FT03 aggregate and boundary interfaces."""
from __future__ import absolute_import

import unittest
import os
import sys
import tempfile

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT_ROOT = os.path.join(ROOT, "prognosis_analysis", "ft")
if FT_ROOT not in sys.path:
    sys.path.insert(0, FT_ROOT)
import ft03_runner as ft03


def _split(ids):
    return pd.DataFrame({
        "patient_id": list(ids),
        "fold": [1, 2, 1][:len(ids)],
        "role": ["validation"] * len(ids),
    })


def _prediction(ids, folds=None):
    if folds is None:
        folds = [1, 2, 1][:len(ids)]
    return pd.DataFrame({
        "patient_id": list(ids),
        "risk": [0.1 + 0.1 * i for i in range(len(ids))],
        "fold": folds,
        "survival_probability_36": [0.8] * len(ids),
        "survival_probability_60": [0.7] * len(ids),
    })


class FT03RunnerTests(unittest.TestCase):

    def test_label_horizons_and_model_set_are_frozen(self):
        self.assertEqual(ft03.FT_LABEL,
                         "exploratory_fullA_habitat_non_nested_validation")
        self.assertEqual(ft03.PERFORMANCE_LABEL, "non_nested_exploratory_estimate")
        self.assertEqual(list(ft03.HORIZONS.items()),
                         [("3_year", 36.0), ("5_year", 60.0)])
        self.assertEqual(ft03.MODEL_IDS,
                         ("M0", "M1", "M2", "M3L", "M3H", "M4", "M5"))

    def test_held_out_prediction_requires_exact_coverage_and_folds(self):
        ids = ["synthetic-1", "synthetic-2", "synthetic-3"]
        split = _split(ids)
        accepted = ft03.validate_held_out_predictions(
            _prediction(ids), ids, split, label="synthetic")
        self.assertEqual(len(accepted), 3)
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_held_out_predictions(
                _prediction(ids[:2]), ids, split, label="missing")
        duplicate = pd.concat([_prediction(ids), _prediction([ids[0]])],
                              ignore_index=True)
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_held_out_predictions(duplicate, ids, split,
                                               label="duplicate")
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_held_out_predictions(
                _prediction(ids, folds=[2, 2, 1]), ids, split, label="wrong-fold")

    def test_paired_population_is_common_and_exact(self):
        self.assertEqual(
            ft03.validate_paired_population(["a", "b"], ["b", "a"], ["a", "b"]),
            ("a", "b"))
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_paired_population(["a"], ["a", "b"])
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_paired_population(["a"], ["a"], ["a", "b"])

    def test_a_boundary_rejects_b_rows_and_b_paths_or_columns(self):
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_a_only_input(pd.DataFrame({"split": ["B"]}))
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_a_only_input(pd.DataFrame({
                "split": ["A"], "b_feature": [1]}))
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_a_only_input(pd.DataFrame({
                "split": ["A"], "source_path": ["technical/B/input.csv"]}))

    def test_prediction_probability_and_fold_contracts_fail_closed(self):
        ids = ["synthetic-1", "synthetic-2", "synthetic-3"]
        split = _split(ids)
        bad_probability = _prediction(ids)
        bad_probability.loc[0, "survival_probability_36"] = 1.2
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_held_out_predictions(
                bad_probability, ids, split, label="probability")
        bad_fold = _prediction(ids)
        bad_fold.loc[0, "fold"] = 6
        with self.assertRaises(ft03.FT03ValidationError):
            ft03.validate_held_out_predictions(
                bad_fold, ids, split, label="fold")

    def test_metric_aggregation_emits_required_interfaces(self):
        ids = ["synthetic-%02d" % i for i in range(10)]
        frame = pd.DataFrame({
            "patient_id": ids,
            "DFS_time": [8.0 + 4.0 * i for i in range(10)],
            "DFS_event": [1, 0, 1, 1, 0, 1, 0, 1, 0, 1],
        })
        folds = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
        rows = []
        for fold in range(1, 6):
            for identifier, assigned in zip(ids, folds):
                rows.append({
                    "patient_id": identifier,
                    "fold": fold,
                    "role": "validation" if assigned == fold else "train",
                })
        split = pd.DataFrame(rows)
        prediction = _prediction(ids, folds=folds)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ft03._prediction_metrics(frame, split, prediction,
                                               temp_dir, seed_offset=1000)
        self.assertEqual(result["prediction_n"], 10)
        self.assertEqual(set(result["metrics"]), {
            "Uno_C_index", "Harrell_C_index", "AUC_3_year", "AUC_5_year",
            "Brier_3_year", "Brier_5_year"})
        self.assertEqual(set(result["calibration"]), {"3_year", "5_year"})
        self.assertEqual(set(result["dca"]), {"3_year", "5_year"})


if __name__ == "__main__":
    unittest.main()
