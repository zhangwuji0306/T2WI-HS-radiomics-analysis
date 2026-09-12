"""Synthetic and artifact-bound FT04 contract tests."""
from __future__ import absolute_import

import hashlib
import inspect
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FT_ROOT = os.path.join(ROOT, "prognosis_analysis", "ft")
if FT_ROOT not in sys.path:
    sys.path.insert(0, FT_ROOT)
TEST_ROOT = os.path.join(ROOT, "tests")
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)

import ft04_runner as ft04  # noqa: E402
from test_ft02_runner import synthetic_frame  # noqa: E402


class FT04RunnerTests(unittest.TestCase):
    def test_full_fit_state_serialization_and_replay(self):
        state, model, prep, frame, original_risk = ft04._fit_full_model(
            synthetic_frame(), "M0")
        restored_model = ft04._restore_model(state)
        restored_prep = ft04._restore_preprocessor(state["preprocessor"])
        transformed = restored_prep.transform(frame)
        replay = restored_model.predict_risk(transformed)
        replay_survival = restored_model.predict_survival(transformed, ft04.HORIZONS)
        self.assertEqual(state["model_id"], "M0")
        self.assertEqual(state["raw_predictor_columns"],
                         ft04._raw_predictor_columns("M0"))
        self.assertEqual(len(state["transformed_feature_names"]),
                         len(state["model"]["coef"]))
        self.assertEqual(state["transformed_feature_names"],
                         restored_prep.feature_names)
        np.testing.assert_allclose(original_risk, replay, rtol=0, atol=1e-12)
        original_survival = model.predict_survival(
            prep.transform(frame), ft04.HORIZONS)
        for horizon in ft04.HORIZONS:
            np.testing.assert_allclose(original_survival[horizon],
                                       replay_survival[horizon],
                                       rtol=0, atol=1e-12)

    def test_prediction_contract_uses_exact_input_hash_and_nonoptimized_cutoff(self):
        state, unused_model, unused_prep, unused_frame, unused_risk = \
            ft04._fit_full_model(synthetic_frame(), "M0")
        expected = ft04._model_input_hash(
            "M0", state["raw_predictor_columns"], state["transformed_feature_names"])
        self.assertEqual(state["model_input_hash"], expected)
        self.assertFalse(state["cutoff"]["optimized"])
        self.assertEqual(state["cutoff"]["rule"],
                         "median_full_A_fitted_linear_predictor")

    def test_missing_or_forged_ft05_prerequisite_fails_closed(self):
        lock_path = os.path.join(ROOT, "prognosis_analysis", "ft",
                                 "FT_model_freeze_lock.json")
        if not os.path.isfile(lock_path):
            self.skipTest("FT04 production lock is not generated in this checkout")
        lock = ft04.validate_ft_model_freeze_lock(lock_path)
        frame = synthetic_frame().drop(columns=["DFS_time", "DFS_event"])
        frame["split"] = "B"
        with self.assertRaises(ft04.FT04ValidationError):
            ft04.predict_b_from_frozen(frame, "M0", lock_path=lock_path,
                                       manifest_path=os.path.join(
                                           ROOT, "prognosis_analysis", "ft",
                                           "missing_FT05_manifest.json"))
        with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "prognosis_analysis", "output")) as tmp:
            manifest_path = os.path.join(tmp, "FT05_B_feature_manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump({
                    "artifact_id": "FT05_B_feature_manifest",
                    "status": "frozen",
                    "ft04_lock_identity_sha256": "0" * 64,
                    "model_input_hashes": {},
                }, handle)
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.predict_b_from_frozen(
                    frame, "M0", lock_path=lock_path,
                    manifest_path=manifest_path)

            valid_manifest = {
                "artifact_id": "FT05_B_feature_manifest",
                "status": "frozen",
                "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
                "model_input_hashes": lock["prediction_contract"][
                    "expected_model_input_hashes"],
            }
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(valid_manifest, handle)
            bad_path_frame = frame.copy()
            bad_path_frame["image_path"] = "B\\private\\image.nii.gz"
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.predict_b_from_frozen(
                    bad_path_frame, "M0", lock_path=lock_path,
                    manifest_path=manifest_path)
            bad_outcome_frame = frame.copy()
            bad_outcome_frame["DFS_event"] = 0
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.predict_b_from_frozen(
                    bad_outcome_frame, "M0", lock_path=lock_path,
                    manifest_path=manifest_path)

    def test_tampered_model_state_is_rejected(self):
        lock_path = os.path.join(ROOT, "prognosis_analysis", "ft",
                                 "FT_model_freeze_lock.json")
        if not os.path.isfile(lock_path):
            self.skipTest("FT04 production lock is not generated in this checkout")
        lock = ft04.validate_ft_model_freeze_lock(lock_path)
        with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "prognosis_analysis", "output")) as tmp:
            original_path = os.path.join(ROOT, "prognosis_analysis", "output",
                                         "ft_20260910_01a08bf3", "FT04",
                                         "model_states", "M0.json")
            tampered_path = os.path.join(tmp, "M0.json")
            shutil.copyfile(original_path, tampered_path)
            with open(tampered_path, "a", encoding="utf-8") as handle:
                handle.write("\n")
            tampered_lock = json.loads(json.dumps(lock))
            tampered_lock["models"]["M0"]["path"] = os.path.relpath(
                tampered_path, ROOT).replace("\\", "/")
            lock_copy = os.path.join(tmp, "FT_model_freeze_lock.json")
            with open(lock_copy, "w", encoding="utf-8") as handle:
                json.dump(tampered_lock, handle)
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.validate_ft_model_freeze_lock(lock_copy)

    def test_prediction_function_has_no_fitting_or_extraction_route(self):
        source = inspect.getsource(ft04.predict_b_from_frozen)
        for token in ("_fit_full_model", "_inner_lambda_selection",
                      "KMeans", "extract_radiomics"):
            self.assertNotIn(token, source)

    def test_formal_lock_is_not_created_or_modified_by_ft04_module(self):
        source = inspect.getsource(ft04)
        self.assertIn("prognosis_analysis/model_freeze_lock.json", source)
        formal = os.path.join(ROOT, "prognosis_analysis", "model_freeze_lock.json")
        self.assertFalse(os.path.exists(formal))


if __name__ == "__main__":
    unittest.main(verbosity=2)
