import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
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

    def _formal_release_gate(self):
        return {
            "stage": "W08_FORMAL_RELEASE",
            "status": "PASS",
            "formal_authorized": True,
            "code_commit": CURRENT_COMMIT,
            "checks": {},
            "failure_reasons": [],
            "B_access": dict((key, False) for key in formal.B_ACCESS_FLAGS),
            "final_outputs_generated": False,
        }

    def _run_synthetic_formal(self, output_root, run_side_effect=None,
                              atomic_json_wrapper=None,
                              write_progress_side_effect=None,
                              completed_attempt_side_effect=None,
                              promote_side_effect=None):
        source = self._write_synthetic_population_source(output_root)
        provider = SimpleNamespace(_case_cache={})
        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(formal, "W06_POPULATION", source))
            stack.enter_context(mock.patch.object(
                formal, "validate_w08_release_gate",
                return_value=self._formal_release_gate()))
            stack.enter_context(mock.patch.object(
                formal, "_git_head", return_value=CURRENT_COMMIT))
            stack.enter_context(mock.patch.object(
                formal, "_load_population_and_provider",
                return_value=(["synthetic-001"], None, provider)))
            stack.enter_context(mock.patch.object(
                formal.w08, "run_w08",
                side_effect=run_side_effect,
                return_value=None if run_side_effect is not None
                else _synthetic_result()))
            stack.enter_context(mock.patch.object(
                formal.w08, "load_config", return_value={}))
            if atomic_json_wrapper is not None:
                original_atomic_json = formal._atomic_json

                def wrapped_atomic_json(path, payload):
                    return atomic_json_wrapper(
                        original_atomic_json, path, payload)

                stack.enter_context(mock.patch.object(
                    formal, "_atomic_json", side_effect=wrapped_atomic_json))
            if write_progress_side_effect is not None:
                stack.enter_context(mock.patch.object(
                    formal, "_write_progress",
                    side_effect=write_progress_side_effect))
            if completed_attempt_side_effect is not None:
                stack.enter_context(mock.patch.object(
                    formal, "_write_completed_attempt_state",
                    side_effect=completed_attempt_side_effect))
            if promote_side_effect is not None:
                stack.enter_context(mock.patch.object(
                    formal, "_promote_staged_outputs",
                    side_effect=promote_side_effect))
            return formal.formal(output_root)

    def _terminal_states(self, output_root):
        with open(os.path.join(output_root, formal.W08_RUN_STATE_NAME),
                  encoding="utf-8") as handle:
            run_state = json.load(handle)
        with open(os.path.join(output_root, formal.W08_PROGRESS_NAME),
                  encoding="utf-8") as handle:
            progress = json.load(handle)
        attempt_path = os.path.join(output_root, formal.W08_ATTEMPT_STATE_NAME)
        if not os.path.isfile(attempt_path):
            attempts_root = os.path.join(output_root, "attempts")
            candidates = sorted(os.listdir(attempts_root))
            self.assertTrue(candidates)
            attempt_path = os.path.join(attempts_root, candidates[0],
                                        formal.W08_ATTEMPT_STATE_NAME)
        with open(attempt_path, encoding="utf-8") as handle:
            attempt_state = json.load(handle)
        return attempt_state, run_state, progress

    def _assert_failed_terminal_state(self, output_root):
        states = self._terminal_states(output_root)
        self.assertEqual([state["status"] for state in states],
                         ["failed", "failed", "failed"])
        for name in formal.W08_FINAL_OUTPUT_NAMES:
            self.assertFalse(os.path.exists(os.path.join(output_root, name)))
        attempts_root = os.path.join(output_root, "attempts")
        self.assertFalse(any(name.endswith(".staging")
                             for name in os.listdir(attempts_root)))

    def _run_formal_with_promotion_interrupt(self, output_root, filename,
                                              interrupt_after_move=False):
        original_replace = formal.os.replace
        triggered = [False]

        def injected_replace(source, destination):
            is_promotion = (
                os.path.basename(source) == filename and
                os.path.basename(os.path.dirname(source)).endswith(".staging"))
            if is_promotion and not triggered[0]:
                triggered[0] = True
                if interrupt_after_move:
                    original_replace(source, destination)
                raise KeyboardInterrupt("synthetic promotion interruption")
            return original_replace(source, destination)

        with mock.patch.object(formal.os, "replace",
                               side_effect=injected_replace):
            with self.assertRaises(KeyboardInterrupt):
                self._run_synthetic_formal(output_root)
        self.assertTrue(triggered[0])
        self._assert_failed_terminal_state(output_root)
        attempts_root = os.path.join(output_root, "attempts")
        failed = [name for name in os.listdir(attempts_root)
                  if name.endswith("_failed")]
        self.assertEqual(len(failed), 1)
        failed_root = os.path.join(attempts_root, failed[0])
        self.assertTrue(os.path.isfile(
            os.path.join(failed_root, "failure_audit.json")))
        self.assertTrue(os.path.isfile(
            os.path.join(failed_root, formal.W08_ATTEMPT_STATE_NAME)))
        context = formal._begin_attempt(output_root, CURRENT_COMMIT, 2.0)
        self.assertTrue(context["staging_root"].endswith(".staging"))
        return failed_root

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

    def test_failed_archive_serializes_deidentified_numerical_context(self):
        with tempfile.TemporaryDirectory() as output_root:
            context = formal._begin_attempt(output_root, CURRENT_COMMIT, 1.0)
            exception = formal.w08.W08NumericalFailure(
                "forced numerical failure", audit={
                    "failure_context": {
                        "run_id": "M3L",
                        "patient_id": "PATIENT-003",
                        "source_path": r"C:\private\patient-003\scan.nii.gz",
                        "failure_stage": "outer_final_refit",
                        "non_zero_coefficient_number": None,
                        "iterations": 11,
                    }})
            formal._write_attempt_failure(
                context, os.path.dirname(os.path.dirname(__file__)),
                "nested_cv_modeling", exception)
            failed_root = context["failed_root"]
            with open(os.path.join(failed_root, "failure_audit.json"),
                      encoding="utf-8") as handle:
                failure = json.load(handle)
            numerical = failure["numerical_failure_audit"]
            encoded = json.dumps(numerical, ensure_ascii=False)
            self.assertNotIn("PATIENT-003", encoded)
            self.assertNotIn("patient_id", encoded)
            self.assertNotIn("patient-003", encoded)
            self.assertNotIn("scan.nii.gz", encoded)
            self.assertEqual(
                numerical["audit"]["failure_context"]["failure_stage"],
                "outer_final_refit")
            self.assertEqual(
                numerical["audit"]["failure_context"]["iterations"], 11)
            self.assertIn(
                "non_zero_coefficient_number",
                numerical["audit"]["failure_context"])
            self.assertIsNone(
                numerical["audit"]["failure_context"][
                    "non_zero_coefficient_number"])

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
            original_write_progress = formal._write_progress
            completion_observation = {}

            def observe_completion_progress(root, started_epoch, payload=None):
                if payload and payload.get("status") == "complete":
                    with open(os.path.join(root, formal.W08_RUN_STATE_NAME),
                              encoding="utf-8") as handle:
                        run_state = json.load(handle)
                    with open(os.path.join(root, formal.W08_ATTEMPT_STATE_NAME),
                              encoding="utf-8") as handle:
                        attempt_state = json.load(handle)
                    completion_observation.update({
                        "manifest": os.path.isfile(os.path.join(
                            root, formal.W08_OUTPUT_MANIFEST_NAME)),
                        "run_state": run_state["status"],
                        "attempt_state": attempt_state["status"],
                        "run_outputs": run_state["final_outputs_generated"],
                        "attempt_outputs": attempt_state[
                            "final_outputs_generated"],
                    })
                return original_write_progress(root, started_epoch, payload)

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
                                       return_value={}), \
                    mock.patch.object(formal, "_write_progress",
                                      side_effect=observe_completion_progress):
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
            self.assertEqual(completion_observation, {
                "manifest": True,
                "run_state": "complete",
                "attempt_state": "complete",
                "run_outputs": True,
                "attempt_outputs": True,
            })
            with open(os.path.join(output_root, formal.W08_PROGRESS_NAME),
                      encoding="utf-8") as handle:
                progress = json.load(handle)
            self.assertEqual(progress["status"], "complete")

    def test_external_interrupt_before_promotion_closes_all_states_as_failed(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(KeyboardInterrupt):
                self._run_synthetic_formal(
                    output_root, run_side_effect=KeyboardInterrupt())
            self._assert_failed_terminal_state(output_root)

    def test_external_interrupt_after_predictions_before_next_promotion_is_archived(self):
        with tempfile.TemporaryDirectory() as output_root:
            failed_root = self._run_formal_with_promotion_interrupt(
                output_root, "fold_results.csv")
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "staging", "fold_results.csv")))
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "staging",
                             formal.W08_OUTPUT_MANIFEST_NAME)))
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "promoted_outputs",
                             "predictions.csv")))

    def test_external_interrupt_after_intermediate_promotion_is_archived(self):
        with tempfile.TemporaryDirectory() as output_root:
            failed_root = self._run_formal_with_promotion_interrupt(
                output_root, "audit.json", interrupt_after_move=True)
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "promoted_outputs", "audit.json")))
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "staging", "run_metadata.json")))
            self.assertTrue(os.path.isfile(
                os.path.join(failed_root, "staging",
                             formal.W08_OUTPUT_MANIFEST_NAME)))

    def test_external_interrupt_after_manifest_promotion_is_archived(self):
        with tempfile.TemporaryDirectory() as output_root:
            failed_root = self._run_formal_with_promotion_interrupt(
                output_root, formal.W08_OUTPUT_MANIFEST_NAME,
                interrupt_after_move=True)
            for name in formal.W08_FINAL_OUTPUT_NAMES:
                self.assertTrue(os.path.isfile(os.path.join(
                    failed_root, "promoted_outputs", name)))
            self.assertTrue(os.path.isfile(os.path.join(
                failed_root, "staging", formal.W08_ATTEMPT_STATE_NAME)))

    def test_attempt_state_write_failure_rolls_back_terminal_state(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(OSError):
                self._run_synthetic_formal(
                    output_root,
                    completed_attempt_side_effect=OSError(
                        "synthetic attempt-state failure"))
            self._assert_failed_terminal_state(output_root)

    def test_run_state_write_failure_rolls_back_terminal_state(self):
        calls = [0]

        def fail_complete_run_once(original, path, payload):
            if (os.path.basename(path) == formal.W08_RUN_STATE_NAME and
                    payload.get("status") == "complete" and calls[0] == 0):
                calls[0] += 1
                raise OSError("synthetic run-state failure")
            return original(path, payload)

        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(OSError):
                self._run_synthetic_formal(
                    output_root, atomic_json_wrapper=fail_complete_run_once)
            self._assert_failed_terminal_state(output_root)

    def test_final_progress_write_failure_rolls_back_terminal_state(self):
        original_write_progress = formal._write_progress

        def fail_complete_progress(root, started_epoch, payload=None):
            if payload and payload.get("status") == "complete":
                raise OSError("synthetic final progress failure")
            return original_write_progress(root, started_epoch, payload)

        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(formal.W08TerminalStateError):
                self._run_synthetic_formal(
                    output_root,
                    write_progress_side_effect=fail_complete_progress)
            self._assert_failed_terminal_state(output_root)

    def test_manifest_write_failure_never_publishes_formal_outputs(self):
        calls = [0]

        def fail_manifest_once(original, path, payload):
            if (os.path.basename(path) == formal.W08_OUTPUT_MANIFEST_NAME and
                    calls[0] == 0):
                calls[0] += 1
                raise OSError("synthetic manifest failure")
            return original(path, payload)

        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(OSError):
                self._run_synthetic_formal(
                    output_root, atomic_json_wrapper=fail_manifest_once)
            self._assert_failed_terminal_state(output_root)

    def test_promotion_failure_never_publishes_formal_outputs(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(OSError):
                self._run_synthetic_formal(
                    output_root,
                    promote_side_effect=OSError("synthetic promotion failure"))
            self._assert_failed_terminal_state(output_root)

if __name__ == "__main__":
    unittest.main()
