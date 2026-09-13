import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd


ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "prognosis_analysis" / "scripts" / \
    "validate_kmeans_n_init_equivalence.py"
SCRIPTS = str(ROOT / "prognosis_analysis" / "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
import validate_kmeans_n_init_equivalence as ninit  # noqa: E402


def synthetic_inputs():
    identifiers = ["S%02d" % index for index in range(10)]
    rows = []
    for index, identifier in enumerate(identifiers):
        # Two low and two high supervoxels make the weighted fit well-defined.
        for label, (mean, voxels) in enumerate(
                ((0.0, 5), (0.2, 5), (10.0, 5), (10.2, 5)), start=1):
            rows.append({
                "影像号": identifier,
                "reader": "R1",
                "sv_label": label,
                "Mean": mean + index * 0.001,
                "n_tumor_voxels": voxels,
            })
    supervoxels = pd.DataFrame(rows)
    split_rows = []
    for repeat in range(1, 11):
        for fold in range(1, 6):
            validation = {identifiers[2 * (fold - 1)],
                          identifiers[2 * (fold - 1) + 1]}
            for identifier in identifiers:
                split_rows.append({
                    "patient_id": identifier,
                    "repeat": repeat,
                    "fold": fold,
                    "role": "validation" if identifier in validation
                    else "train",
                    "seed": 12345 + repeat - 1,
                })
    return supervoxels, pd.DataFrame(split_rows)


def controlled_arm_factory(center_high_10=10.0, center_high_100=10.0,
                           boundary_10=5.0, boundary_100=5.0,
                           inertia_10=1.0, inertia_100=1.0):
    def fit(values, weights, seed, n_init):
        if n_init == 10:
            return {
                "center_low": 0.0, "center_high": center_high_10,
                "boundary": boundary_10, "inertia": inertia_10,
                "n_iter": 2,
            }
        return {
            "center_low": 0.0, "center_high": center_high_100,
            "boundary": boundary_100, "inertia": inertia_100,
            "n_iter": 2,
        }
    return fit


class KMeansNInitEquivalenceTests(unittest.TestCase):

    def test_exact_equivalence_completes_all_50_folds(self):
        supervoxels, splits = synthetic_inputs()
        with tempfile.TemporaryDirectory() as directory:
            summary = ninit.run_validation(
                supervoxels, splits, pathlib.Path(directory), workers=1)
            self.assertEqual(summary["status"], "EXACT_EQUIVALENCE")
            self.assertEqual(summary["folds_completed"], 50)
            self.assertEqual(summary["folds_exact_equal"], 50)
            self.assertFalse(summary["stopped_early"])
            comparison = pd.read_csv(
                pathlib.Path(directory) / "n_init_fold_comparison.csv")
            self.assertEqual(len(comparison), 50)

    def test_extra_initialisations_can_produce_a_better_solution(self):
        supervoxels, splits = synthetic_inputs()
        factory = controlled_arm_factory(
            center_high_10=8.0, center_high_100=10.0,
            boundary_10=4.0, boundary_100=5.0,
            inertia_10=8.0, inertia_100=2.0)
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(ninit, "_fit_arm", side_effect=factory):
            summary = ninit.run_validation(
                supervoxels, splits, pathlib.Path(directory), workers=1)
            self.assertEqual(summary["status"], "NOT_EQUIVALENT")
            self.assertEqual(summary["folds_completed"], 1)
            self.assertTrue(summary["stopped_early"])
            row = pd.read_csv(
                pathlib.Path(directory) / "n_init_fold_comparison.csv").iloc[0]
            self.assertLess(row["inertia_100"], row["inertia_10"])

    def test_boundary_change_without_label_change_changes_g_value(self):
        supervoxels, splits = synthetic_inputs()
        factory = controlled_arm_factory(
            center_high_10=10.0, center_high_100=12.0,
            boundary_10=5.0, boundary_100=5.5)
        with mock.patch.object(ninit, "_fit_arm", side_effect=factory):
            sv, split, _ = ninit.validate_inputs(supervoxels, splits)
            row, affected = ninit.compare_fold(sv, split, 1, 1)
        self.assertFalse(row["affected_supervoxels"])
        self.assertEqual(row["G_value_changes"], 10)
        self.assertGreater(row["affected_cases"], 0)
        self.assertFalse(affected.empty)

    def test_label_change_propagates_counts_states_and_populations(self):
        supervoxels, splits = synthetic_inputs()
        # This fold has a low-side support of 9 voxels at boundary 5.0 and
        # 14 voxels at boundary 5.5, so the support state crosses the gate.
        special = []
        for index, row in supervoxels.iterrows():
            if row["影像号"] == "S00":
                special.append({"Mean": [0.0, 4.9, 5.1, 10.0][index % 4],
                                "n_tumor_voxels": [5, 4, 5, 10][index % 4]})
            else:
                special.append({"Mean": row["Mean"],
                                "n_tumor_voxels": row["n_tumor_voxels"]})
        for index, values in enumerate(special):
            supervoxels.loc[index, "Mean"] = values["Mean"]
            supervoxels.loc[index, "n_tumor_voxels"] = values["n_tumor_voxels"]
        factory = controlled_arm_factory(
            center_high_10=10.0, center_high_100=11.0,
            boundary_10=5.0, boundary_100=5.5)
        with mock.patch.object(ninit, "_fit_arm", side_effect=factory):
            sv, split, _ = ninit.validate_inputs(supervoxels, splits)
            row, affected = ninit.compare_fold(sv, split, 1, 1)
        self.assertGreater(row["affected_supervoxels"], 0)
        self.assertGreater(row["support_state_changes"], 0)
        self.assertGreater(row["eligibility_changes"], 0)
        self.assertGreater(row["paired_population_changes"], 0)
        self.assertIn("S00", set(affected["patient_id"]))

    def test_validation_id_in_fit_is_rejected_before_estimator(self):
        supervoxels, splits = synthetic_inputs()
        bad = splits.copy()
        mask = ((bad["repeat"] == 1) & (bad["fold"] == 1) &
                (bad["patient_id"] == "S00"))
        bad.loc[mask, "role"] = "validation"
        with mock.patch.object(ninit, "_fit_arm",
                               side_effect=AssertionError("fit called")):
            with tempfile.TemporaryDirectory() as directory:
                summary = ninit.run_validation(
                    supervoxels, bad, pathlib.Path(directory), workers=1)
        self.assertEqual(summary["status"], "INCOMPLETE")
        self.assertEqual(summary["folds_completed"], 0)

    def test_patient_balanced_weights_sum_to_one(self):
        supervoxels, splits = synthetic_inputs()
        sv, split, _ = ninit.validate_inputs(supervoxels, splits)
        captured = {}

        def capture(values, weights, seed, n_init):
            captured.setdefault(n_init, (values.copy(), weights.copy()))
            return {"center_low": 0.0, "center_high": 10.0,
                    "boundary": 5.0, "inertia": 1.0, "n_iter": 1}

        with mock.patch.object(ninit, "_fit_arm", side_effect=capture):
            ninit.compare_fold(sv, split, 1, 1)
        values, weights = captured[10]
        self.assertEqual(len(values), 32)
        self.assertAlmostEqual(float(weights.sum()), 8.0)
        # Eight training cases, each with four supervoxels and total weight 1.
        self.assertTrue(np.allclose(weights, 0.25))

    def test_missing_fold_overlap_and_invalid_values_are_rejected(self):
        supervoxels, splits = synthetic_inputs()
        cases = []
        missing = splits[~((splits["repeat"] == 10) &
                           (splits["fold"] == 5))].copy()
        cases.append(missing)
        overlap = splits.copy()
        overlap.loc[(overlap["repeat"] == 1) & (overlap["fold"] == 1) &
                    (overlap["patient_id"] == "S00"), "role"] = "train"
        cases.append(overlap)
        invalid_mean = supervoxels.copy()
        invalid_mean.loc[0, "Mean"] = np.inf
        with tempfile.TemporaryDirectory() as directory:
            for index, bad_splits in enumerate(cases):
                summary = ninit.run_validation(
                    supervoxels, bad_splits,
                    pathlib.Path(directory) / ("case%d" % index),
                    workers=1)
                self.assertEqual(summary["status"], "INCOMPLETE")
            summary = ninit.run_validation(
                invalid_mean, splits,
                pathlib.Path(directory) / "invalid_mean", workers=1)
            self.assertEqual(summary["status"], "INCOMPLETE")
        invalid_voxels = supervoxels.copy()
        invalid_voxels["n_tumor_voxels"] = \
            invalid_voxels["n_tumor_voxels"].astype(float)
        invalid_voxels.loc[0, "n_tumor_voxels"] = 1.5
        sv, _, _ = ninit.validate_inputs(supervoxels, splits)
        with self.assertRaises(ninit.ValidationError):
            ninit.validate_inputs(invalid_voxels, splits)
        self.assertIsNotNone(sv)

    def test_early_stop_does_not_claim_50_folds(self):
        supervoxels, splits = synthetic_inputs()
        factory = controlled_arm_factory(boundary_10=5.0, boundary_100=6.0)
        with tempfile.TemporaryDirectory() as directory, \
                mock.patch.object(ninit, "_fit_arm", side_effect=factory):
            summary = ninit.run_validation(
                supervoxels, splits, pathlib.Path(directory), workers=1,
                stop_on_first_material_difference=True)
        self.assertEqual(summary["status"], "NOT_EQUIVALENT")
        self.assertLess(summary["folds_completed"], 50)
        self.assertTrue(summary["stopped_early"])

    def test_outputs_have_no_outcome_clinical_external_or_performance_fields(self):
        supervoxels, splits = synthetic_inputs()
        with tempfile.TemporaryDirectory() as directory:
            ninit.run_validation(supervoxels, splits, pathlib.Path(directory),
                                 workers=1)
            summary = json.loads(
                (pathlib.Path(directory) /
                 "n_init_equivalence_summary.json").read_text(
                     encoding="utf-8"))
            frame = pd.read_csv(pathlib.Path(directory) /
                                "n_init_fold_comparison.csv")
            text = (pathlib.Path(directory) /
                    "n_init_equivalence_report.md").read_text(
                        encoding="utf-8").lower()
        forbidden = {"dfs", "event", "time", "clinical", "prediction",
                     "auc", "c-index", "brier", "calibration"}
        self.assertFalse(forbidden.intersection(summary))
        self.assertFalse(forbidden.intersection(frame.columns))
        # The report states the isolation boundary but does not contain data
        # columns or patient-level detail.
        self.assertNotIn("patient_id", text)

    def test_source_has_no_formal_or_extraction_dependency(self):
        source = SCRIPT.read_text(encoding="utf-8").lower()
        for forbidden in ("w08_nested_cv", "w08_formal_run_a", "pyradiomics",
                          "simpleitk"):
            self.assertNotIn(forbidden, source)

    def test_cli_defaults_and_worker_limit(self):
        args = ninit.build_parser().parse_args([])
        self.assertEqual(args.workers, 2)
        self.assertTrue(args.stop_on_first_material_difference)
        self.assertTrue(str(args.output_dir).endswith(
            os.path.join("prognosis_analysis", "output",
                         "n_init_equivalence_A")))
        supervoxels, splits = synthetic_inputs()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                ninit.run_validation(supervoxels, splits,
                                     pathlib.Path(directory), workers=3)

    def test_two_worker_execution_path(self):
        supervoxels, splits = synthetic_inputs()
        with tempfile.TemporaryDirectory() as directory:
            summary = ninit.run_validation(
                supervoxels, splits, pathlib.Path(directory), workers=2)
        self.assertEqual(summary["status"], "EXACT_EQUIVALENCE")
        self.assertEqual(summary["folds_completed"], 50)


if __name__ == "__main__":
    unittest.main()
