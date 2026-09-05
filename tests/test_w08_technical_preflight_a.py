import hashlib
import json
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_technical_preflight_a as p5  # noqa: E402


def synthetic_inputs(n=50):
    ids = ["S%03d" % index for index in range(n)]
    population = pd.DataFrame({
        "patient_id": ids,
        "technical_cohort": ["A393"] * n,
        "DFS_time": np.arange(1, n + 1, dtype=float),
        "DFS_event": [1 if index < n // 2 else 0 for index in range(n)],
        "modeling_eligible": [1] * n,
    })

    rows = []
    # Each case has a frozen supervoxel representation.  The first four cases
    # deliberately cover 0, 1-9, and >=10 support in both habitat blocks.
    categories = ("low_absent", "low_small", "high_absent", "high_small")
    for index, identifier in enumerate(ids):
        category = categories[index] if index < len(categories) else "dual"
        if category == "low_absent":
            supports = ((3.0, 20),)
        elif category == "low_small":
            supports = ((1.0, 5), (3.0, 15))
        elif category == "high_absent":
            supports = ((1.0, 20),)
        elif category == "high_small":
            supports = ((1.0, 15), (3.0, 5))
        else:
            supports = ((1.0, 10), (3.0, 10))
        for label, (mean, voxel_count) in enumerate(supports, start=1):
            rows.append({
                "patient_id": identifier,
                "reader": "R1",
                "sv_label": label,
                "n_tumor_voxels": voxel_count,
                "Mean": mean,
            })
    supervoxels = pd.DataFrame(rows)
    availability = pd.DataFrame({
        "patient_id": ids,
        "R_low_available": [True] * n,
        "R_high_available": [True] * n,
        "W_available": [True] * n,
    })

    split_rows = []
    labels = population["DFS_event"].to_numpy(dtype=int)
    indices = np.arange(n)
    for repeat in range(1, 11):
        splitter = StratifiedKFold(n_splits=5, shuffle=True,
                                   random_state=p5.BASE_SEED + repeat - 1)
        for fold, (train, validation) in enumerate(
                splitter.split(indices, labels), start=1):
            seed = p5.BASE_SEED + repeat - 1
            for role, selected in (("train", train), ("validation", validation)):
                for position in selected:
                    split_rows.append({
                        "patient_id": ids[position], "repeat": repeat,
                        "fold": fold, "role": role, "seed": seed,
                    })
    split_frame = pd.DataFrame(split_rows, columns=p5.SPLIT_COLUMNS)
    return population, split_frame, supervoxels, availability


def synthetic_bindings():
    return {label: expected for label, (_, expected) in p5._BINDING_FILES.items()}


class TechnicalPreflightTests(unittest.TestCase):
    def setUp(self):
        self.population, self.splits, self.supervoxels, self.availability = synthetic_inputs()

    def run_preflight(self):
        return p5.run_technical_preflight(
            self.population, self.splits, self.supervoxels,
            self.availability, binding_hashes=synthetic_bindings())

    def test_frozen_plan_enumerates_all_50_units(self):
        fold_units = p5.verify_split_frame(self.splits, self.population)
        self.assertEqual(len(fold_units), 50)
        result = self.run_preflight()
        self.assertEqual(result["summary"]["fold_units"], 50)
        self.assertEqual(result["fold_feasibility"][["repeat", "fold"]]
                         .drop_duplicates().shape[0], 50)

    def test_support_states_are_exact_and_distinct(self):
        self.assertEqual(p5.support_state(0), "structural_absence")
        self.assertEqual(p5.support_state(1), "technical_small_roi")
        self.assertEqual(p5.support_state(9), "technical_small_roi")
        self.assertEqual(p5.support_state(10), "extractable")
        masks = p5.generate_fold_masks(self.supervoxels, 2.0)
        self.assertEqual(masks.loc["S000", "R_low_state"], "structural_absence")
        self.assertEqual(masks.loc["S001", "R_low_state"], "technical_small_roi")
        self.assertEqual(masks.loc["S002", "R_high_state"], "structural_absence")
        self.assertEqual(masks.loc["S003", "R_high_state"], "technical_small_roi")
        self.assertEqual(masks.loc["S004", "R_low_state"], "extractable")

    def test_model_specific_populations_and_paired_comparators(self):
        result = self.run_preflight()["fold_feasibility"]
        first = result[(result["repeat"] == 1) & (result["fold"] == 1)]
        by_run = first.set_index("run_id")
        self.assertEqual(by_run.loc["M0", "population"], "main")
        self.assertEqual(by_run.loc["M3L", "population"], "R_low")
        self.assertEqual(by_run.loc["M3H", "population"], "R_high")
        self.assertEqual(by_run.loc["M4", "population"], "dual_radiomics")
        self.assertEqual(by_run.loc["M3L", "n_validation_after_eligibility"],
                         by_run.loc["M2_R_low", "n_validation_after_eligibility"])
        self.assertEqual(by_run.loc["M3H", "eligible_validation_id_hash"],
                         by_run.loc["M2_R_high", "eligible_validation_id_hash"])
        self.assertTrue(bool(first["paired_population_equal"].all()))

    def test_boundary_fitting_is_training_only(self):
        first = self.splits[(self.splits["repeat"] == 1) &
                            (self.splits["fold"] == 1)]
        train_ids = set(first.loc[first["role"] == "train", "patient_id"])
        validation_ids = set(first.loc[first["role"] == "validation", "patient_id"])
        fitted_all = p5.fit_training_only_centres(
            self.supervoxels, train_ids, seed=14346)
        fitted_train = p5.fit_training_only_centres(
            self.supervoxels[self.supervoxels["patient_id"].isin(train_ids)],
            train_ids, seed=14346)
        self.assertEqual(fitted_all["training_id_hash"],
                         p5.canonical_id_hash(train_ids))
        self.assertFalse(set(validation_ids) & train_ids)
        self.assertEqual(fitted_all["centres"], fitted_train["centres"])
        self.assertEqual(fitted_all["boundary"], fitted_train["boundary"])
        self.assertFalse(fitted_all["validation_ids_used_for_fit"])

    def test_outer_and_inner_event_gates_hard_fail(self):
        no_events = self.population.copy()
        no_events["DFS_event"] = 0
        with self.assertRaisesRegex(p5.P5ValidationError, "outer event gate"):
            p5.run_technical_preflight(
                no_events, self.splits, self.supervoxels,
                self.availability, binding_hashes=synthetic_bindings())
        too_few_events = self.population.iloc[:20].copy()
        too_few_events["DFS_event"] = [1] * 4 + [0] * 16
        with self.assertRaisesRegex(p5.P5ValidationError, "inner_5fold_event_gate"):
            p5._inner_feasibility(too_few_events, set(too_few_events["patient_id"]),
                                  15346, "M3L", 1, 1, "R_low")

    def test_forbidden_states_and_bindings_fail_closed(self):
        with self.assertRaises(p5.P5ValidationError):
            p5.run_technical_preflight(
                self.population, self.splits, self.supervoxels,
                self.availability, binding_hashes={})
        malformed = self.supervoxels.copy()
        malformed.loc[0, "n_tumor_voxels"] = 0
        with self.assertRaises(p5.P5ValidationError):
            p5.fit_training_only_centres(malformed,
                                         set(self.population["patient_id"][:40]),
                                         14346)
        altered = self.splits.copy()
        altered.loc[0, "fold"] = 2
        with self.assertRaises(p5.P5ValidationError):
            p5.run_technical_preflight(
                self.population, altered, self.supervoxels,
                self.availability, binding_hashes=synthetic_bindings())

    def test_aggregate_output_has_no_patient_or_prediction_material(self):
        result = self.run_preflight()
        with tempfile.TemporaryDirectory() as tmp:
            paths = p5.write_outputs(result, tmp)
            self.assertEqual(len(paths), 3)
            for path in paths:
                with open(path, "r", encoding="utf-8-sig") as handle:
                    text = handle.read()
                self.assertNotIn("patient_id", text)
                self.assertNotIn("prediction", text.lower())
                self.assertNotIn("c_index", text.lower())
                self.assertNotIn("auc", text.lower())
                self.assertNotIn("brier", text.lower())
            with open(os.path.join(tmp, "P5_release_gate.json"),
                      "r", encoding="utf-8") as handle:
                gate = json.load(handle)
            self.assertFalse(gate["performance_generated"])
            self.assertFalse(gate["B_data_read"])

    def test_entry_point_is_structurally_isolated(self):
        path = os.path.join(SCRIPTS, "w08_technical_preflight_a.py")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("w08_formal_run_a", source)
        self.assertNotIn("w08_nested_cv", source)
        self.assertNotIn("read_B_validation", source)
        self.assertNotIn("build_outer_splits", source)
        self.assertNotIn("Cox", source)
        self.assertNotIn("c_index", source)


if __name__ == "__main__":
    unittest.main()
