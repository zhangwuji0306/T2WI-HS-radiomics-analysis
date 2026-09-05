import hashlib
import inspect
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

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

    def test_canonical_split_hash_is_lf_stable_and_pandas_compatible(self):
        frame = pd.DataFrame([
            ["S001", 1, 1, "train", 12345],
            ["S002", 1, 1, "validation", 12345],
        ], columns=p5.SPLIT_COLUMNS)
        expected_payload = (
            "patient_id,repeat,fold,role,seed\n"
            "S001,1,1,train,12345\n"
            "S002,1,1,validation,12345\n")
        expected = hashlib.sha256(expected_payload.encode("utf-8")).hexdigest()
        original = pd.DataFrame.to_csv

        def locked_to_csv(frame, *args, **kwargs):
            if "lineterminator" in kwargs or "line_terminator" in kwargs:
                raise TypeError("unsupported line terminator keyword")
            return original(frame, *args, **kwargs)

        with patch.object(pd.DataFrame, "to_csv", autospec=True,
                          side_effect=locked_to_csv) as writer:
            observed = p5._canonical_split_hash(frame)
        self.assertEqual(observed, expected)
        self.assertNotIn("lineterminator", writer.call_args.kwargs)
        self.assertNotIn("line_terminator", writer.call_args.kwargs)

    def test_canonical_split_hash_rejects_one_character_body_change(self):
        expected = p5._canonical_split_hash(self.splits)
        altered = self.splits.copy()
        altered.loc[0, "role"] = "validation"
        self.assertNotEqual(p5._canonical_split_hash(altered), expected)
        with self.assertRaisesRegex(p5.P5ValidationError, "canonical split hash"):
            p5.verify_split_frame(altered, self.population, expected_hash=expected)

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

    def test_every_frozen_binding_value_is_checked_exactly(self):
        for label in p5._BINDING_FILES:
            forged = synthetic_bindings()
            forged[label] = "0" * 64
            with self.subTest(binding=label):
                with self.assertRaisesRegex(p5.P5ValidationError, label):
                    p5.run_technical_preflight(
                        self.population, self.splits, self.supervoxels,
                        self.availability, binding_hashes=forged)

    def test_production_entry_rejects_forged_manifest_before_a_read(self):
        forged = synthetic_bindings()
        forged["W04_modeling_protocol"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(p5, "verify_frozen_bindings",
                              return_value=forged), \
                    patch.object(p5, "load_authorized_a_inputs") as loader:
                with self.assertRaisesRegex(p5.P5ValidationError, "binding"):
                    p5.run_production(tmp, project_root=tmp)
                loader.assert_not_called()
            with self.assertRaises(TypeError):
                p5.run_production(tmp, project_root=tmp,
                                  binding_hashes=synthetic_bindings())

    def test_loader_separates_outcomes_and_uses_authorized_frozen_split_read(self):
        feature_scripts = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "feature_extract", "scripts"))
        if feature_scripts not in sys.path:
            sys.path.insert(0, feature_scripts)
        import data_split_guard  # noqa: E402

        ids = list(self.population["patient_id"])
        technical_population = self.population.rename(
            columns={"patient_id": "影像号"})[
                ["影像号", "technical_cohort", "modeling_eligible"]]
        outcome_frame = self.population.rename(
            columns={"patient_id": "影像号"})[
                ["影像号", "DFS_time", "DFS_event"]]
        supervoxel_frame = self.supervoxels.rename(
            columns={"patient_id": "影像号"})
        availability_frame = pd.DataFrame({
            "影像号": ids, "reader": ["R1"] * len(ids),
            "status": ["extractable"] * len(ids),
        })
        whole_tumour_frame = pd.DataFrame({
            "影像号": ids, "读者": ["R1"] * len(ids),
        })
        technical_calls = []
        outcome_calls = []
        frozen_split_calls = []
        events = []

        def fake_technical(path, **kwargs):
            technical_calls.append((path, kwargs))
            events.append("technical")
            usecols = set(kwargs.get("usecols", []))
            if {"technical_cohort", "modeling_eligible"}.issubset(usecols):
                return technical_population.copy()
            if "sv_label" in usecols:
                return supervoxel_frame.copy()
            if {"reader", "status"}.issubset(usecols):
                return availability_frame.copy()
            if "读者" in usecols:
                return whole_tumour_frame.copy()
            raise AssertionError("unexpected technical reader call: %s" % kwargs)

        def fake_frozen_split(path, project_root, allowed_ids):
            frozen_split_calls.append((path, project_root, set(allowed_ids)))
            return self.splits.copy()

        def fake_outcomes(path, **kwargs):
            outcome_calls.append((path, kwargs))
            events.append("outcome")
            return outcome_frame.copy()

        root = os.path.join(tempfile.gettempdir(), "p5_loader_test_root")
        split_path = os.path.join(
            root, "prognosis_analysis", "output", "outer_splits_A.csv")
        os.makedirs(os.path.dirname(split_path), exist_ok=True)
        def fake_verify(project_root):
            events.append("bindings")
            return synthetic_bindings()

        try:
            with patch.object(p5, "verify_frozen_bindings", side_effect=fake_verify), \
                    patch.object(p5, "_canonical_split_hash",
                                 return_value=p5.W07_OUTER_SPLIT_SHA256), \
                    patch.object(data_split_guard, "read_technical_A",
                                 side_effect=fake_technical), \
                    patch.object(data_split_guard, "read_frozen_A_split",
                                 side_effect=fake_frozen_split), \
                    patch.object(data_split_guard, "read_A_outcomes",
                                 side_effect=fake_outcomes):
                loaded = p5.load_authorized_a_inputs(root)
        finally:
            try:
                os.remove(split_path)
                os.removedirs(os.path.dirname(split_path))
            except OSError:
                pass

        self.assertEqual(set(loaded[0]["patient_id"]), set(ids))
        self.assertIn("bindings", events)
        self.assertEqual(events[0], "bindings")
        self.assertLess(events.index("technical"), events.index("outcome"))
        self.assertTrue(outcome_calls)
        self.assertEqual(len(frozen_split_calls), 1)
        self.assertEqual(frozen_split_calls[0][2], set(ids))
        self.assertEqual(outcome_calls[0][1]["usecols"],
                         ["影像号", "DFS_time", "DFS_event"])
        for _, kwargs in technical_calls:
            self.assertFalse(set(kwargs.get("usecols", [])) &
                             {"DFS_time", "DFS_event"})
        self.assertNotIn("pd.read_csv", inspect.getsource(
            p5.load_authorized_a_inputs))
        self.assertNotIn("pd.read_csv", inspect.getsource(
            p5._load_frozen_split_authorized))

    def test_frozen_split_config_and_roi_tamper_fail_closed(self):
        altered = self.splits.copy()
        altered.loc[0, "fold"] = 2
        with self.assertRaises(p5.P5ValidationError):
            p5.run_technical_preflight(
                self.population, altered, self.supervoxels,
                self.availability, binding_hashes=synthetic_bindings(),
                expected_split_hash=p5.W07_OUTER_SPLIT_SHA256)

        original_json = p5._json

        def tampered_json(path):
            value = original_json(path)
            if os.path.basename(path) == "w07_outer_splits.json":
                value = dict(value)
                value["outer_cv"] = dict(value["outer_cv"])
                value["outer_cv"]["n_splits"] = 4
            return value

        with patch.object(p5, "_json", side_effect=tampered_json):
            with self.assertRaises(p5.P5ValidationError):
                p5.verify_frozen_bindings()
        with patch.object(p5, "MINIMUM_ROI_SIZE", 11):
            with self.assertRaises(p5.P5ValidationError):
                p5.verify_frozen_bindings()

    def test_aggregate_output_has_no_patient_or_prediction_material(self):
        result = self.run_preflight()
        self.assertEqual(result["release_gate"]["status"], "TEST_ONLY")
        self.assertFalse(result["release_gate"]["bindings_verified"])
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
