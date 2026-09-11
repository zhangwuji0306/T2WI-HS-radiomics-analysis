"""Synthetic and static FT02 contract tests."""
from __future__ import absolute_import

import hashlib
import inspect
import os
import sys
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT_ROOT = os.path.join(ROOT, "prognosis_analysis", "ft")
if FT_ROOT not in sys.path:
    sys.path.insert(0, FT_ROOT)
import ft02_runner as ft


def synthetic_frame(n=75):
    rng = np.random.RandomState(19)
    frame = pd.DataFrame({
        "patient_id": ["A%03d" % i for i in range(n)],
        "DFS_time": np.linspace(8.0, 120.0, n),
        "DFS_event": np.array([1 if i % 3 else 0 for i in range(n)], dtype=int),
        "split": ["A"] * n,
        "年龄": rng.normal(55, 8, n),
        "CEA_log": rng.normal(1.4, 0.4, n),
        "mrT_4级": rng.randint(1, 5, n),
        "mrN_3级": rng.randint(0, 4, n),
        "MRF": rng.randint(0, 2, n),
        "mrEMVI": rng.randint(0, 2, n),
        "thickness": rng.normal(12, 2, n),
        "EID": rng.normal(3, 1, n),
        "活检病理非腺癌": rng.randint(0, 2, n),
        "H_high_fraction": rng.uniform(0.1, 0.9, n),
        "R_low_structurally_defined": [0 if i in (2, 11) else 1 for i in range(n)],
        "R_low_technically_available": [0 if i in (2, 11, 17) else 1 for i in range(n)],
        "R_high_structurally_defined": [0 if i in (5, 23) else 1 for i in range(n)],
        "R_high_technically_available": [0 if i in (5, 23, 29) else 1 for i in range(n)],
        "W_Original_available": [0 if i in (31, 32) else 1 for i in range(n)],
    })
    extras = {}
    for column in ft.GLOBAL_COLUMNS:
        if column not in frame.columns:
            extras[column] = rng.normal(size=n)
    for block, names in (("R_low", ft.R_LOW_FEATURE_NAMES),
                         ("R_high", ft.R_HIGH_FEATURE_NAMES),
                         ("W_Original", ft.W_ORIGINAL_FEATURE_NAMES)):
        prefix = ft.BLOCK_PREFIXES[block]
        for index, name in enumerate(names):
            extras[prefix + name] = rng.normal(size=n) + index * 0.001
    return pd.concat([frame, pd.DataFrame(extras)], axis=1)


def synthetic_split(frame):
    rows = []
    ids = frame["patient_id"].tolist()
    for fold in range(1, 6):
        validation = [identifier for index, identifier in enumerate(ids) if index % 5 + 1 == fold]
        train = [identifier for identifier in ids if identifier not in validation]
        rows.extend({"patient_id": identifier, "repeat": 1, "fold": fold,
                     "role": "train", "seed": 24680} for identifier in train)
        rows.extend({"patient_id": identifier, "repeat": 1, "fold": fold,
                     "role": "validation", "seed": 24680} for identifier in validation)
    return pd.DataFrame(rows)


class FT02RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = synthetic_frame()
        cls.split = synthetic_split(cls.frame)
        cls.formal_guard = {}
        for relative in (
                "habitat_analysis/freeze_lock.json",
                "prognosis_analysis/modeling_protocol.json",
                "prognosis_analysis/execution_status.json",
                "prognosis_analysis/configs/w07_outer_splits.json",
                "prognosis_analysis/output/outer_splits_A.csv"):
            path = os.path.join(ROOT, relative)
            with open(path, "rb") as handle:
                cls.formal_guard[relative] = hashlib.sha256(handle.read()).hexdigest()

    def test_model_definitions_and_w_original_only(self):
        self.assertEqual(list(ft.FT_MODEL_SPECS), ["M0", "M1", "M2", "M3L", "M3H", "M4", "M5"])
        self.assertEqual(ft.FT_MODEL_SPECS["M5"]["blocks"], ("C", "W_Original"))
        self.assertEqual(len(ft.W_ORIGINAL_FEATURE_NAMES), 107)
        self.assertEqual(ft.W_ORIGINAL_ORDER_SHA256, "1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f")
        self.assertTrue(all(name.startswith("original_") for name in ft.W_ORIGINAL_FEATURE_NAMES))

    def test_frozen_split_is_reused_without_regeneration(self):
        split = ft.validate_frozen_split(self.split, self.frame)
        self.assertEqual(sorted(split["fold"].unique().tolist()), [1, 2, 3, 4, 5])
        self.assertEqual(set(split["repeat"].unique()), {1})
        with self.assertRaises(ft.FTValidationError):
            ft.validate_frozen_split(self.split.assign(repeat=2), self.frame)

    def test_training_only_preprocessing(self):
        train = self.frame.iloc[:50].copy()
        valid = self.frame.iloc[50:].copy()
        valid.loc[:, "年龄"] = 9999.0
        prep = ft.FTPreprocessor("M1").fit(train)
        mean_before = prep.clinical.means["年龄"]
        prep.transform(valid)
        self.assertEqual(mean_before, prep.clinical.means["年龄"])
        self.assertNotEqual(float(valid["年龄"].mean()), mean_before)

    def test_all_models_run_and_lambda_is_training_only(self):
        result = ft.run_ft02_a_for_testing(
            self.frame, self.split, lambda_count=3, max_iter=250)
        self.assertEqual(set(result["models"]), set(ft.FT_MODEL_SPECS))
        self.assertEqual(result["split_provenance"]["regenerated"], False)
        self.assertEqual(result["split_provenance"]["seed"], 24680)
        for model_id, record in result["models"].items():
            self.assertEqual(record["prediction_coverage"], record["eligible_n"])
            self.assertIn("survival_probability_36", result["predictions"][model_id])
            self.assertIn("survival_probability_60", result["predictions"][model_id])
            if ft.FT_MODEL_SPECS[model_id]["penalized"]:
                for fold in record["folds"]:
                    self.assertEqual(fold["selection"]["alpha"], 1.0)
                    self.assertFalse(fold["selection"]["outer_validation_used_for_lambda"])
                    self.assertEqual(fold["selection"]["lambda_selection_scope"],
                                     "outer_training_inner_5fold_only")
        paired = {row["comparison_id"]: row for row in result["paired_model_comparisons"]}
        expected = int(((self.frame.R_low_structurally_defined == 1) &
                        (self.frame.R_low_technically_available == 1) &
                        (self.frame.R_high_structurally_defined == 1) &
                        (self.frame.R_high_technically_available == 1) &
                        (self.frame.W_Original_available == 1)).sum())
        self.assertEqual(paired["M4_vs_M5"]["common_n"], expected)
        for comparison_id in ("M2_vs_M3L", "M2_vs_M3H", "M2_vs_M4",
                              "M3L_vs_M3H", "M4_vs_M5"):
            self.assertTrue(paired[comparison_id][
                "common_training_validation_are_identical"])
            self.assertEqual(len(paired[comparison_id]["folds"]), 5)
            for fold in paired[comparison_id]["folds"]:
                self.assertTrue(fold["training_id_hash"])
                self.assertTrue(fold["validation_id_hash"])
                self.assertTrue(fold["fold_assignment_hash"])

    def test_production_entry_point_is_w07_bound_and_fail_closed(self):
        with self.assertRaises(ft.FTValidationError):
            ft.run_ft02_a(self.frame, self.split)
        with self.assertRaises(ft.FTValidationError):
            ft.run_ft02_a(self.frame)
        frozen_split, frozen_population = ft.load_frozen_w07_repeat1()
        self.assertEqual(len(frozen_population), 393)
        self.assertEqual(len(frozen_split), 393 * 5)
        self.assertEqual(ft._canonical_split_hash(frozen_split),
                         ft.W07_REPEAT1_CANONICAL_SHA256)
        self.assertEqual(set(frozen_split["seed"]), {12345})
        self.assertEqual(set(frozen_split["role"]), {"train", "validation"})

    def test_common_pair_uses_same_training_and_validation_id_sets(self):
        result = ft.run_ft02_a_for_testing(
            self.frame, self.split, models=["M2", "M3L"],
            lambda_count=3, max_iter=250)
        pair = result["paired_model_comparisons"][0]
        common = set(self.frame.loc[
            (self.frame.R_low_structurally_defined == 1) &
            (self.frame.R_low_technically_available == 1), "patient_id"])
        for fold in range(1, 6):
            current = self.split[self.split.fold == fold]
            train_ids = sorted(set(current.loc[
                current.role == "train", "patient_id"]) & common)
            valid_ids = sorted(set(current.loc[
                current.role == "validation", "patient_id"]) & common)
            record = pair["folds"][fold - 1]
            self.assertEqual(record["n_train"], len(train_ids))
            self.assertEqual(record["n_validation"], len(valid_ids))
            self.assertEqual(record["training_id_hash"], ft._id_hash(train_ids))
            self.assertEqual(record["validation_id_hash"], ft._id_hash(valid_ids))

    def test_structural_absence_and_explicit_availability(self):
        valid = ft.validate_ft_frame(self.frame)
        self.assertEqual(int(ft.population_mask(valid, "dual_radiomics").sum()), 69)
        invalid = self.frame.drop(columns=["R_low_technically_available"])
        with self.assertRaises(ft.FTValidationError):
            ft.validate_ft_frame(invalid)
        invalid = self.frame.copy()
        invalid.loc[0, "R_low_structurally_defined"] = 0
        invalid.loc[0, "R_low_technically_available"] = 1
        with self.assertRaises(ft.FTValidationError):
            ft.validate_ft_frame(invalid)

    def test_frozen_p3b_structural_state_is_accepted(self):
        p3b = self.frame.drop(columns=[
            "R_low_structurally_defined", "R_low_technically_available",
            "R_high_structurally_defined", "R_high_technically_available"]).copy()
        for block in ("R_low", "R_high"):
            structural = self.frame[block + "_structurally_defined"].to_numpy()
            technical = self.frame[block + "_technically_available"].to_numpy()
            counts = np.where(structural == 0, 0, np.where(technical == 1, 20, 2))
            p3b[block + "_voxel_count"] = counts
            p3b[block + "_structurally_defined"] = (counts > 0).astype(int)
            p3b[block + "_technically_extractable"] = (counts >= 10).astype(int)
            p3b[block + "_state"] = np.where(
                counts == 0, "structural_absence",
                np.where(counts < 10, "technical_small_roi", "extractable"))
        checked = ft.validate_ft_frame(p3b)
        self.assertEqual(int(ft.population_mask(checked, "dual_radiomics").sum()), 69)

    def test_w_filtered_schema_and_b_row_or_path_rejection(self):
        bad = self.frame.copy()
        bad["W__wavelet_firstorder_Mean"] = 1.0
        with self.assertRaises(ft.FTValidationError):
            ft.validate_ft_frame(bad)
        bad = self.frame.copy()
        bad.loc[0, "split"] = "B"
        with self.assertRaises(ft.FTValidationError):
            ft.validate_ft_frame(bad)
        bad = self.frame.copy()
        bad["image_path"] = "B\\patient\\image.nii.gz"
        with self.assertRaises(ft.FTValidationError):
            ft.validate_ft_frame(bad)

    def test_metrics_and_bootstrap_hooks(self):
        time = self.frame["DFS_time"].to_numpy(dtype=float)
        event = self.frame["DFS_event"].to_numpy(dtype=int)
        risk = np.linspace(-1.0, 1.0, len(self.frame))
        c = ft.harrell_c_index_hook(time, event, risk)
        self.assertTrue(np.isfinite(c))
        self.assertTrue(np.isfinite(ft.uno_c_index_hook(time, event, time, event, risk)))
        self.assertTrue(np.isfinite(ft.auc_3_year_hook(self.frame, self.frame, risk)))
        self.assertTrue(np.isfinite(ft.auc_5_year_hook(self.frame, self.frame, risk)))
        survival = 1.0 / (1.0 + np.exp(risk))
        self.assertTrue(np.isfinite(ft.brier_score_hook(self.frame, self.frame, survival, 36)))
        self.assertTrue(np.isfinite(ft.brier_3_year_hook(self.frame, self.frame, survival)))
        self.assertTrue(np.isfinite(ft.brier_5_year_hook(self.frame, self.frame, survival)))
        self.assertIn("bins", ft.calibration_data_hook(self.frame, self.frame, survival, 36))
        self.assertIn("groups", ft.km_data_hook(self.frame, risk))
        self.assertIn("points", ft.dca_data_hook(self.frame, 1.0 - survival, 36))
        result = ft.bootstrap_ci_hook(lambda idx: float(np.mean(risk[idx])), len(risk),
                                      n_bootstrap=10, seed=7)
        self.assertEqual(result["seed"], 7)
        self.assertEqual(result["mode"], "case_resample")

    def test_fitted_state_survival_interface(self):
        context = ft._build_test_fit_context(self.frame, self.split)
        current = self.split[self.split.fold == 1]
        train_ids = set(current.loc[current.role == "train", "patient_id"])
        valid_ids = set(current.loc[current.role == "validation", "patient_id"])
        train = self.frame[self.frame.patient_id.isin(train_ids)]
        valid = self.frame[self.frame.patient_id.isin(valid_ids)]
        fit = ft._fit_fold_a(
            train, valid, "M0",
            fit_context=context, max_iter=250)
        output = ft.predict_risk_survival_hook(
            fit["model"], fit["preprocessor"], valid)
        self.assertEqual(len(output["risk"]), len(valid))
        for key in ("survival_probability_36_months",
                    "survival_probability_60_months"):
            self.assertIn(key, output)
            self.assertTrue(np.isfinite(output[key]).all())
            self.assertTrue(np.all((output[key] >= 0) & (output[key] <= 1)))

    def test_public_fold_fit_bypass_fails_closed(self):
        with self.assertRaises(ft.FTValidationError):
            ft.fit_fold_a(
                self.frame.iloc[:60], self.frame.iloc[60:], "M0",
                max_iter=250)
        with self.assertRaises(ft.FTValidationError):
            ft._fit_fold_a(
                self.frame.iloc[:60], self.frame.iloc[60:], "M0",
                fit_context=None, max_iter=250)

    def test_calibration_uses_survival_direction_at_horizon(self):
        frame = pd.DataFrame({
            "DFS_time": [12.0, 48.0],
            "DFS_event": [1, 0],
        })
        result = ft.calibration_data_hook(
            frame, frame, np.array([0.2, 0.8]), 36.0, bins=2)
        self.assertEqual(result["prediction_quantity"], "survival_probability")
        self.assertEqual(result["observed_quantity"], "survival_at_horizon")
        self.assertEqual(
            [row["observed_survival_fraction"] for row in result["bins"]],
            [0.0, 1.0])
        self.assertNotIn("observed_event_fraction", result["bins"][0])

    def test_static_ft_isolation(self):
        source = inspect.getsource(ft)
        self.assertNotIn("read_B_validation", source)
        self.assertNotIn("model_freeze_lock.json", source)
        self.assertNotIn("open(.*\\\"w\\\"", source)
        self.assertNotIn("json.dump(", source)
        self.assertIsNone(ft.run_ft02_a.__defaults__[0])
        for relative, digest in self.formal_guard.items():
            with open(os.path.join(ROOT, relative), "rb") as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), digest)
        self.assertFalse(os.path.exists(os.path.join(ROOT, "prognosis_analysis", "model_freeze_lock.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
