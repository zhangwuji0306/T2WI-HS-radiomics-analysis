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
from unittest import mock

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
    def _lock_path(self):
        return os.path.join(ROOT, "prognosis_analysis", "ft",
                            "FT_model_freeze_lock.json")

    def _lock(self):
        return ft04.validate_ft_model_freeze_lock(self._lock_path())

    def _write_json(self, path, payload):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2,
                      sort_keys=True)
            handle.write("\n")

    def _write_manifest(self, path, manifest):
        self._write_json(path, manifest)

    def _downstream_fixtures(self, lock):
        fixture_root = os.path.join(
            ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3",
            "FT05A")
        if not os.path.isdir(fixture_root):
            os.makedirs(fixture_root)
        temp = tempfile.TemporaryDirectory(dir=fixture_root)
        root = temp.name
        frame = synthetic_frame(8).copy()
        frame["patient_id"] = ["B%03d" % index for index in range(len(frame))]
        frame["split"] = "B"
        feature_frame = frame.drop(columns=["DFS_time", "DFS_event"])
        table_path = os.path.join(root, "features.csv")
        feature_frame.to_csv(table_path, index=False)
        w_path = os.path.join(root, "W_Original_reused_asset.bin")
        with open(w_path, "wb") as handle:
            handle.write(b"synthetic W_Original asset")
        ft04_review_path = os.path.join(root, "FT04_review.md")
        runner_sha = lock["provenance"]["git_binding"]["current_file_bindings"][
            "ft04_runner"]["sha256"]
        with open(ft04_review_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(
                "# Independent FT04 review\n\n"
                "## Disposition\n\n"
                "`accepted for downstream use`\n\n"
                "Independent review: true\n"
                "FT04 lock identity SHA-256: `%s`\n"
                "FT04 runner SHA-256: `%s`\n" % (
                    lock["lock_identity_sha256"], runner_sha))
        technical_review_path = os.path.join(
            root, "FT05A_B_technical_generation_audit.md")
        code_review_path = os.path.join(root, "FT05A_code_audit.md")
        for review_path in (technical_review_path, code_review_path):
            with open(review_path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("Independent review: true\nVerdict: PASS\n")

        manifest_path = os.path.join(root, "FT05_B_feature_manifest.json")
        manifest = {
            "schema_version": "1.0",
            "artifact_id": "FT05_B_feature_manifest",
            "status": "frozen",
            "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
            "model_input_hashes": lock["prediction_contract"][
                "expected_model_input_hashes"],
            "feature_table": {
                "path": ft04._relative(table_path),
                "sha256": ft04._sha256_file(table_path),
                "format": "csv",
                "complete": True,
                "columns": list(feature_frame.columns),
                "row_count": len(feature_frame),
                "patient_id_column": "patient_id",
                "patient_count": len(feature_frame),
                "patient_ids_unique": True,
                "duplicate_patient_count": 0,
                "duplicate_extraction_count": 0,
                "extraction_count": len(feature_frame),
            },
            "feature_blocks": {
                "R_low": {
                    "feature_names": list(ft04.ft02.R_LOW_FEATURE_NAMES),
                    "count": 49,
                    "candidate_hash": ft04.R_LOW_CANDIDATE_HASH,
                },
                "R_high": {
                    "feature_names": list(ft04.ft02.R_HIGH_FEATURE_NAMES),
                    "count": 10,
                    "candidate_hash": ft04.R_HIGH_CANDIDATE_HASH,
                },
                "W_Original": {
                    "feature_names": list(ft04.ft02.W_ORIGINAL_FEATURE_NAMES),
                    "count": 107,
                    "order_sha256": ft04.ft02.W_ORIGINAL_ORDER_SHA256,
                    "reused_existing_asset": True,
                    "reextracted": False,
                    "asset_path": ft04._relative(w_path),
                    "asset_sha256": ft04._sha256_file(w_path),
                },
            },
            "frozen_a_full_boundary": {
                "definition": "accepted frozen full_A habitat",
                "lock_identity_sha256": lock["lock_identity_sha256"],
                "identity_sha256": ft04._frozen_a_boundary_identity(lock),
                "K": 2,
                "n_init": 100,
                "no_refit": True,
                "source_hashes": {
                    key: lock["provenance"]["sources"][key]["sha256"]
                    for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                                "w03_candidate_freeze")
                },
            },
            "pyradiomics_matches_A_W03": True,
            "pyradiomics_provenance": lock["provenance"]["pyradiomics"],
            "generation": {
                "outcome_blind": True,
                "outcome_accessed": False,
                "b_kmeans_fit": False,
                "one_time_first_extraction": True,
                "repeat_extraction": False,
                "duplicate_extraction": False,
                "checkpoint_resume_repeated_extraction": False,
                "whole_tumor_reextraction": False,
                "w_original_reused": True,
                "formal_directory_mixing": False,
            },
            "reviews": {
                "technical_audit": {
                    "path": ft04._relative(technical_review_path),
                    "sha256": ft04._sha256_file(technical_review_path),
                    "status": "accepted",
                    "independent": True,
                    "verdict": "PASS",
                },
                "code_audit": {
                    "path": ft04._relative(code_review_path),
                    "sha256": ft04._sha256_file(code_review_path),
                    "status": "accepted",
                    "independent": True,
                    "verdict": "PASS",
                },
            },
        }
        self._write_manifest(manifest_path, manifest)
        unlock_path = os.path.join(root, "FT_B_unlock.json")
        self._write_json(unlock_path, {
            "schema_version": "1.0",
            "artifact_id": "FT_B_unlock",
            "status": "authorized",
            "outcome_access": True,
            "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
            "ft05_manifest_sha256": ft04._sha256_file(manifest_path),
        })
        patches = mock.patch.multiple(
            ft04,
            FT04_REVIEW=ft04_review_path,
            FT05_MANIFEST=manifest_path,
            FT_B_UNLOCK=unlock_path,
            FT05A_TECHNICAL_AUDIT=technical_review_path,
            FT05A_CODE_AUDIT=code_review_path)
        return temp, patches, feature_frame, manifest_path, unlock_path, manifest

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

    def test_lock_contains_and_validates_canonical_candidate_hashes(self):
        lock = self._lock()
        self.assertEqual(lock["habitat_definition"]["R_low_candidate_hash"],
                         ft04.R_LOW_CANDIDATE_HASH)
        self.assertEqual(lock["habitat_definition"]["R_high_candidate_hash"],
                         ft04.R_HIGH_CANDIDATE_HASH)
        self.assertEqual(lock["b_access"]["b_outcome_unlock"],
                         "prognosis_analysis/ft/FT_B_unlock.json")

    def test_git_binding_is_non_circular_and_current_runner_is_hashed(self):
        lock = self._lock()
        binding = lock["provenance"]["git_binding"]
        self.assertNotIn("code_commit", lock["provenance"])
        self.assertNotEqual(binding["implementation_source_commit"],
                            binding["attestation_parent_commit"])
        self.assertFalse(binding["final_attestation_commit"]["hash_embedded"])
        self.assertEqual(
            binding["current_file_bindings"]["ft04_runner"]["sha256"],
            ft04._sha256_file(os.path.join(FT_ROOT, "ft04_runner.py")))

    def test_lock_rejects_invalid_git_commit_binding(self):
        lock = self._lock()
        with tempfile.TemporaryDirectory(
                dir=os.path.join(ROOT, "prognosis_analysis", "output")) as tmp:
            copy_path = os.path.join(tmp, "FT_model_freeze_lock.json")
            tampered = json.loads(json.dumps(lock))
            tampered["provenance"]["git_binding"][
                "attestation_parent_commit"] = "0" * 40
            tampered["provenance"]["git_binding"]["final_attestation_commit"][
                "parent_commit"] = "0" * 40
            tampered["lock_identity_sha256"] = ft04._lock_identity(tampered)
            self._write_json(copy_path, tampered)
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.validate_ft_model_freeze_lock(copy_path)

    def test_lock_rejects_current_runner_hash_tampering(self):
        lock = self._lock()
        with tempfile.TemporaryDirectory(
                dir=os.path.join(ROOT, "prognosis_analysis", "output")) as tmp:
            copy_path = os.path.join(tmp, "FT_model_freeze_lock.json")
            tampered = json.loads(json.dumps(lock))
            tampered["provenance"]["git_binding"]["current_file_bindings"][
                "ft04_runner"]["sha256"] = "0" * 64
            tampered["provenance"]["sources"]["ft04_runner"]["sha256"] = "0" * 64
            tampered["lock_identity_sha256"] = ft04._lock_identity(tampered)
            self._write_json(copy_path, tampered)
            with self.assertRaises(ft04.FT04ValidationError):
                ft04.validate_ft_model_freeze_lock(copy_path)

    def test_missing_or_forged_ft04_review_fails_closed(self):
        lock = self._lock()
        with self.assertRaises(ft04.FT04ValidationError):
            ft04._validate_ft04_review(lock)

    def test_prediction_requires_complete_canonical_manifest_and_review(self):
        lock = self._lock()
        temp, patches, frame, manifest_path, unused_unlock, manifest = \
            self._downstream_fixtures(lock)
        try:
            with patches:
                prediction = ft04.predict_b_from_frozen(frame, "M0")
                self.assertEqual(len(prediction), len(frame))
                manifest["feature_table"].pop("complete")
                self._write_manifest(manifest_path, manifest)
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(frame, "M0")
        finally:
            temp.cleanup()

    def test_alternate_manifest_and_unlock_paths_are_rejected(self):
        lock = self._lock()
        temp, patches, frame, manifest_path, unlock_path, unused_manifest = \
            self._downstream_fixtures(lock)
        try:
            alternate_manifest = os.path.join(temp.name, "alternate_manifest.json")
            alternate_unlock = os.path.join(temp.name, "alternate_unlock.json")
            shutil.copyfile(manifest_path, alternate_manifest)
            shutil.copyfile(unlock_path, alternate_unlock)
            with patches:
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(
                        frame, "M0", manifest_path=alternate_manifest)
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(
                        frame, "M0", unlock_path=alternate_unlock)
                old_name = os.path.join(temp.name, "FT05B_outcome_unlock.json")
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(
                        frame, "M0", outcomes_requested=True,
                        unlock_path=old_name)
        finally:
            temp.cleanup()

    def test_feature_table_hash_and_patient_uniqueness_are_required(self):
        lock = self._lock()
        temp, patches, frame, manifest_path, unused_unlock, manifest = \
            self._downstream_fixtures(lock)
        try:
            with patches:
                table_path = ft04._absolute(manifest["feature_table"]["path"])
                table = pd.read_csv(table_path)
                table.loc[0, "patient_id"] = table.loc[1, "patient_id"]
                table.to_csv(table_path, index=False)
                manifest["feature_table"]["sha256"] = ft04._sha256_file(table_path)
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(frame, "M0")
        finally:
            temp.cleanup()

    def test_candidate_w_order_boundary_and_provenance_are_required(self):
        lock = self._lock()
        for mutation in ("candidate", "w_order", "boundary", "pyradiomics"):
            temp, patches, frame, manifest_path, unused_unlock, manifest = \
                self._downstream_fixtures(lock)
            try:
                if mutation == "candidate":
                    manifest["feature_blocks"]["R_low"]["candidate_hash"] = "0" * 64
                elif mutation == "w_order":
                    manifest["feature_blocks"]["W_Original"]["order_sha256"] = "0" * 64
                elif mutation == "boundary":
                    manifest["frozen_a_full_boundary"]["identity_sha256"] = "0" * 64
                else:
                    manifest["pyradiomics_provenance"]["configuration_sha256"] = "0" * 64
                self._write_manifest(manifest_path, manifest)
                with patches:
                    with self.assertRaises(ft04.FT04ValidationError):
                        ft04.predict_b_from_frozen(frame, "M0")
            finally:
                temp.cleanup()

    def test_generation_and_ft05a_review_flags_are_required(self):
        lock = self._lock()
        for key in ("b_kmeans_fit", "outcome_accessed", "formal_directory_mixing"):
            temp, patches, frame, manifest_path, unused_unlock, manifest = \
                self._downstream_fixtures(lock)
            try:
                manifest["generation"][key] = True
                self._write_manifest(manifest_path, manifest)
                with patches:
                    with self.assertRaises(ft04.FT04ValidationError):
                        ft04.predict_b_from_frozen(frame, "M0")
            finally:
                temp.cleanup()
        temp, patches, frame, manifest_path, unused_unlock, manifest = \
            self._downstream_fixtures(lock)
        try:
            manifest["reviews"]["code_audit"]["verdict"] = "FAIL"
            self._write_manifest(manifest_path, manifest)
            with patches:
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(frame, "M0")
        finally:
            temp.cleanup()

    def test_outcome_unlock_is_required_only_for_evaluation_and_uses_canonical_file(self):
        lock = self._lock()
        temp, patches, frame, manifest_path, unlock_path, unused_manifest = \
            self._downstream_fixtures(lock)
        try:
            outcomes = frame[["patient_id"]].copy()
            outcomes["DFS_time"] = np.linspace(8.0, 120.0, len(frame))
            outcomes["DFS_event"] = [1, 0, 1, 1, 0, 1, 1, 0]
            with patches:
                os.remove(unlock_path)
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.predict_b_from_frozen(
                        frame, "M0", outcomes_requested=True)
                self._write_json(unlock_path, {
                    "schema_version": "1.0",
                    "artifact_id": "FT_B_unlock",
                    "status": "authorized",
                    "outcome_access": True,
                    "ft04_lock_identity_sha256": lock["lock_identity_sha256"],
                    "ft05_manifest_sha256": ft04._sha256_file(manifest_path),
                })
                result = ft04.evaluate_b_from_frozen(frame, outcomes, "M0")
                self.assertEqual(result["n"], len(frame))
                old_name = os.path.join(temp.name, "FT05B_outcome_unlock.json")
                shutil.copyfile(unlock_path, old_name)
                with self.assertRaises(ft04.FT04ValidationError):
                    ft04.evaluate_b_from_frozen(
                        frame, outcomes, "M0", unlock_path=old_name)
        finally:
            temp.cleanup()

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
