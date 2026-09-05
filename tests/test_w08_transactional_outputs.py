import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_formal_run_a as formal  # noqa: E402


CURRENT_COMMIT = "a" * 40


def _synthetic_result():
    prediction = {
        "run_id": "M0",
        "model_id": "M0",
        "population": "main",
        "repeat": 1,
        "fold": 1,
        "patient_id": "synthetic-001",
        "DFS_time": 12.0,
        "DFS_event": 0,
        "risk_score": 0.25,
        "training_id_hash": "train-hash",
        "validation_id_hash": "validation-hash",
        "outer_split_hash": "split-hash",
        "outer_validation_used_for_selection": False,
    }
    return {
        "predictions": pd.DataFrame([prediction]),
        "fold_results": pd.DataFrame([{"run_id": "M0", "fold": 1}]),
        "selection_results": pd.DataFrame([{"run_id": "M0", "fold": 1}]),
        "audit": {"outer_split_validation": {"status": "PASS"}},
    }


class W08TransactionalOutputTests(unittest.TestCase):
    def _write_synthetic_population_source(self, root):
        path = os.path.join(root, "synthetic_population.csv")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("synthetic_id\nsynthetic-001\n")
        return path

    def _write_success(self, output_root):
        source = self._write_synthetic_population_source(output_root)
        with mock.patch.object(formal, "W06_POPULATION", source), \
                mock.patch.object(formal, "_git_head",
                                   return_value=CURRENT_COMMIT):
            return formal.write_results(
                _synthetic_result(), {}, ["synthetic-001"], 1.0,
                output_root, code_commit=CURRENT_COMMIT)

    def test_complete_promotion_uses_manifest_commit_marker(self):
        with tempfile.TemporaryDirectory() as output_root:
            manifest = self._write_success(output_root)
            self.assertEqual(manifest["status"], "complete")
            self.assertEqual(manifest["attempt_id"].startswith("attempt_"), True)
            for name in formal.W08_FINAL_OUTPUT_NAMES:
                self.assertTrue(os.path.isfile(os.path.join(output_root, name)))
            attempts_root = os.path.join(output_root, "attempts")
            self.assertEqual(
                [name for name in os.listdir(attempts_root)
                 if name.endswith(".staging")], [])
            validated = formal._validate_formal_output_manifest(
                os.path.join(output_root, formal.W08_OUTPUT_MANIFEST_NAME),
                expected_attempt_id=manifest["attempt_id"],
                expected_code_commit=CURRENT_COMMIT)
            self.assertEqual(validated, manifest)

    def test_interrupted_staging_is_failed_and_never_published(self):
        with tempfile.TemporaryDirectory() as output_root:
            source = self._write_synthetic_population_source(output_root)
            original_atomic_csv = formal._atomic_csv
            calls = [0]

            def interrupt_after_first_csv(frame, path):
                calls[0] += 1
                if calls[0] == 2:
                    raise RuntimeError("synthetic interruption")
                return original_atomic_csv(frame, path)

            with mock.patch.object(formal, "W06_POPULATION", source), \
                    mock.patch.object(formal, "_git_head",
                                       return_value=CURRENT_COMMIT), \
                    mock.patch.object(formal, "_atomic_csv",
                                       side_effect=interrupt_after_first_csv):
                with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                    formal.write_results(
                        _synthetic_result(), {}, ["synthetic-001"], 1.0,
                        output_root, code_commit=CURRENT_COMMIT)
            self.assertFalse(os.path.exists(os.path.join(
                output_root, formal.W08_OUTPUT_MANIFEST_NAME)))
            self.assertFalse(os.path.exists(os.path.join(
                output_root, "predictions.csv")))
            attempts = os.listdir(os.path.join(output_root, "attempts"))
            self.assertEqual(len(attempts), 1)
            self.assertTrue(attempts[0].endswith("_failed"))
            failed_root = os.path.join(output_root, "attempts", attempts[0])
            with open(os.path.join(failed_root, "failure_audit.json"),
                      encoding="utf-8") as handle:
                failure = json.load(handle)
            self.assertEqual(failure["status"], "failed")
            self.assertFalse(failure["final_outputs_generated"])

    def test_stale_staging_and_partial_canonical_output_block_new_attempt(self):
        with tempfile.TemporaryDirectory() as output_root:
            stale = os.path.join(output_root, "attempts", "attempt_stale.staging")
            os.makedirs(stale)
            with self.assertRaisesRegex(RuntimeError, "stale W08 staging"):
                self._write_success(output_root)

        with tempfile.TemporaryDirectory() as output_root:
            with open(os.path.join(output_root, "fold_results.csv"), "w",
                      encoding="utf-8") as handle:
                handle.write("partial\n")
            with self.assertRaisesRegex(RuntimeError, "canonical W08 outputs"):
                self._write_success(output_root)

    def test_manifest_hash_attempt_binding_and_compatibility_provenance(self):
        with tempfile.TemporaryDirectory() as output_root:
            manifest = self._write_success(output_root)
            manifest_path = os.path.join(
                output_root, formal.W08_OUTPUT_MANIFEST_NAME)
            with open(os.path.join(output_root, "predictions.csv"), "ab") as handle:
                handle.write(b"tamper\n")
            with self.assertRaisesRegex(RuntimeError, "SHA-256 mismatch"):
                formal._validate_formal_output_manifest(manifest_path)

            compatibility = formal._compatibility_provenance()
            with open(os.path.join(output_root, "audit.json"),
                      encoding="utf-8") as handle:
                audit = json.load(handle)
            self.assertEqual(audit["compatibility_provenance"], compatibility)
            self.assertEqual(compatibility["protocol_minimumROISize"], 10)
            self.assertEqual(compatibility["scientific_minimumROISize"], 10)
            self.assertIsNone(compatibility["effective_backend_minimum_size"])
            self.assertEqual(
                compatibility["compatibility_reason"],
                "PyRadiomics 3.0.1 strict <= semantics and precheck count>=10")
            self.assertEqual(compatibility["precheck_count_threshold"], ">=10")
            self.assertEqual(compatibility["pyradiomics_version"], "3.0.1")

            with open(manifest_path, encoding="utf-8") as handle:
                tampered = json.load(handle)
            tampered["attempt_id"] = "attempt_other"
            with open(manifest_path, "w", encoding="utf-8") as handle:
                json.dump(tampered, handle)
            with self.assertRaisesRegex(RuntimeError, "attempt_id"):
                formal._validate_formal_output_manifest(
                    manifest_path, expected_attempt_id=manifest["attempt_id"])

    def test_formal_marks_complete_only_after_manifest_promotion(self):
        with tempfile.TemporaryDirectory() as output_root:
            source = self._write_synthetic_population_source(output_root)
            release_gate = {
                "stage": "W08_FORMAL_RELEASE",
                "status": "PASS",
                "formal_authorized": True,
                "code_commit": CURRENT_COMMIT,
                "checks": {},
                "failure_reasons": [],
                "B_access": dict((key, False) for key in formal.B_ACCESS_FLAGS),
                "final_outputs_generated": False,
            }
            provider = SimpleNamespace(_case_cache={})
            with mock.patch.object(formal, "W06_POPULATION", source), \
                    mock.patch.object(formal, "validate_w08_release_gate",
                                       return_value=release_gate), \
                    mock.patch.object(formal, "_git_head",
                                       return_value=CURRENT_COMMIT), \
                    mock.patch.object(
                        formal, "_load_population_and_provider",
                        return_value=(["synthetic-001"], None, provider)), \
                    mock.patch.object(formal.w08, "run_w08",
                                       return_value=_synthetic_result()), \
                    mock.patch.object(formal.w08, "load_config",
                                       return_value={}):
                formal.formal(output_root)
            with open(os.path.join(output_root, formal.W08_RUN_STATE_NAME),
                      encoding="utf-8") as handle:
                state = json.load(handle)
            with open(os.path.join(output_root, formal.W08_OUTPUT_MANIFEST_NAME),
                      encoding="utf-8") as handle:
                manifest = json.load(handle)
            self.assertEqual(state["status"], "complete")
            self.assertTrue(state["final_outputs_generated"])
            self.assertEqual(state["attempt_id"], manifest["attempt_id"])
            self.assertEqual(manifest["status"], "complete")


if __name__ == "__main__":
    unittest.main()
