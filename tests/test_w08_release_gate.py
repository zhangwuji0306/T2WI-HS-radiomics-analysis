import json
import os
import sys
import tempfile
import unittest
from collections import OrderedDict
from unittest import mock


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_formal_run_a as formal  # noqa: E402


CODE_COMMIT = "a" * 40


def execution_status(b_flags=None, attempt_id="attempt_001_failed"):
    b_flags = dict(b_flags or {})
    return {
        "execution": {
            "stage": "W08",
            "gate": "HOLD",
            "formal_w08_started": True,
            "last_attempt_status": "failed",
        },
        "last_attempt": {
            "attempt_id": attempt_id,
            "status": "failed",
            "failure_stage": "nested_cv_modeling_radiomics_extraction",
            "failure_reason_summary": "synthetic prior failure",
            "code_commit_at_attempt": "b" * 40,
        },
        "b_access": {
            "B_data_read": b_flags.get("B_data_read", False),
            "B_reader_invoked": b_flags.get("B_reader_invoked", False),
            "B_source_opened": b_flags.get("B_source_opened", False),
            "B_statistics_generated": b_flags.get("B_statistics_generated", False),
        },
        "model_freeze_lock": {"present": False, "status": "absent"},
        "outputs": {"final_outputs_generated": False},
    }


def binding_manifest():
    return OrderedDict(
        (label, expected)
        for label, (_path, expected)
        in formal.preflight._BINDING_FILES.items())


def release_certificate(code_commit=CODE_COMMIT, **overrides):
    payload = {
        "stage": "G3",
        "status": "PASS",
        "P5_technical_preflight": "PASS",
        "code_commit": code_commit,
        "frozen_fold_units": 50,
        "completed_fold_units": 50,
        "all_required_runs_estimable": True,
        "all_paired_populations_equal": True,
        "bindings_verified": True,
        "performance_generated": False,
        "patient_level_outputs_written": False,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
    }
    payload.update(overrides)
    return payload


class W08ReleaseGateFixtureTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            mock.patch.object(formal, "_git_head", return_value=CODE_COMMIT),
            mock.patch.object(formal.provenance, "validate_manifest",
                              return_value={"status": "PASS"}),
            mock.patch.object(formal.provenance, "validate_execution_status",
                              return_value=execution_status()),
            mock.patch.object(formal.preflight, "verify_frozen_bindings",
                              return_value=binding_manifest()),
            mock.patch.object(formal, "_validate_w05_access_boundary",
                              return_value=True),
            mock.patch.object(
                formal, "_sha256",
                return_value=formal.provenance.TECHNICAL_FREEZE_SHA256),
        ]
        for patcher in self.patches:
            patcher.start()
        self.temp = tempfile.TemporaryDirectory()
        self.project_root = self.temp.name
        self.output_root = os.path.join(self.temp.name, "w08_output")
        self.certificate_path = os.path.join(self.temp.name, "P5_release_gate.json")
        freeze_path = os.path.join(self.project_root, "habitat_analysis",
                                   "freeze_lock.json")
        os.makedirs(os.path.dirname(freeze_path))
        with open(freeze_path, "w", encoding="utf-8") as handle:
            handle.write("synthetic technical freeze")
        with open(self.certificate_path, "w", encoding="utf-8") as handle:
            json.dump(release_certificate(), handle)

    def tearDown(self):
        self.temp.cleanup()
        for patcher in reversed(self.patches):
            patcher.stop()

    def gate(self, certificate_path=None):
        return formal.validate_formal_release_gate(
            output_root=self.output_root,
            project_root=self.project_root,
            release_certificate_path=certificate_path or self.certificate_path)

    def test_synthetic_release_gate_passes_without_patient_reads(self):
        result = self.gate()
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["formal_run_authorized"])
        self.assertEqual(result["code_commit"], CODE_COMMIT)
        self.assertEqual(result["B_data_read"], False)
        self.assertFalse(os.path.exists(self.output_root))

    def test_tampered_provenance_fails_closed(self):
        with mock.patch.object(
                formal.provenance, "validate_manifest",
                side_effect=ValueError("tampered successor provenance")):
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self.gate()
        self.assertEqual(raised.exception.result["status"], "FAIL")
        self.assertTrue(any("P4R_provenance_reconciliation" in reason
                            for reason in raised.exception.failure_reasons))

    def test_tampered_frozen_sop_binding_fails_closed(self):
        with mock.patch.object(
                formal.preflight, "verify_frozen_bindings",
                side_effect=ValueError("W07A protocol hash mismatch")):
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self.gate()
        self.assertTrue(any("frozen_bindings" in reason
                            for reason in raised.exception.failure_reasons))

    def test_stale_g3_release_certificate_commit_fails_closed(self):
        with open(self.certificate_path, "w", encoding="utf-8") as handle:
            json.dump(release_certificate(code_commit="c" * 40), handle)
        with self.assertRaises(formal.W08ReleaseGateError) as raised:
            self.gate()
        self.assertTrue(any("G3_release_certificate" in reason
                            for reason in raised.exception.failure_reasons))

    def test_model_freeze_presence_fails_closed(self):
        lock_path = os.path.join(self.project_root, "prognosis_analysis",
                                 "model_freeze_lock.json")
        os.makedirs(os.path.dirname(lock_path))
        with open(lock_path, "w", encoding="utf-8") as handle:
            handle.write("synthetic lock")
        with self.assertRaises(formal.W08ReleaseGateError) as raised:
            self.gate()
        self.assertTrue(any("model_freeze_absent" in reason
                            for reason in raised.exception.failure_reasons))

    def test_non_false_b_flag_fails_closed(self):
        status = execution_status({"B_source_opened": True})
        with mock.patch.object(formal.provenance, "validate_execution_status",
                               return_value=status):
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self.gate()
        self.assertTrue(any("B_access_closed" in reason
                            for reason in raised.exception.failure_reasons))

    def test_unreconciled_prior_attempt_fails_closed(self):
        status = execution_status(attempt_id="attempt_001")
        with mock.patch.object(formal.provenance, "validate_execution_status",
                               return_value=status):
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self.gate()
        self.assertTrue(any("prior_attempt_reconciled" in reason
                            for reason in raised.exception.failure_reasons))

    def test_existing_incomplete_output_fails_closed(self):
        os.makedirs(self.output_root)
        with open(os.path.join(self.output_root, "run_state.json"), "w",
                  encoding="utf-8") as handle:
            json.dump({"status": "running"}, handle)
        with self.assertRaises(formal.W08ReleaseGateError) as raised:
            self.gate()
        self.assertTrue(any("prior_final_outputs_absent" in reason
                            for reason in raised.exception.failure_reasons))


class W08FormalFailureStateTests(unittest.TestCase):
    def test_gate_failure_never_calls_patient_entry_or_writes_running(self):
        with tempfile.TemporaryDirectory() as temp:
            output_root = os.path.join(temp, "w08_output")
            gate_error = formal.W08ReleaseGateError(
                "synthetic gate failure", {
                    "stage": "W08", "gate": "FORMAL_W08_RELEASE",
                    "status": "FAIL", "failure_reasons": ["synthetic"]})
            with mock.patch.object(formal, "validate_formal_release_gate",
                                   side_effect=gate_error), \
                    mock.patch.object(formal, "_load_population_and_provider") as loader, \
                    mock.patch.object(formal.w08, "run_w08") as runner, \
                    mock.patch.object(formal, "write_results") as writer:
                with self.assertRaises(formal.W08ReleaseGateError):
                    formal.formal(output_root=output_root,
                                  project_root=temp,
                                  release_certificate_path=os.path.join(
                                      temp, "missing.json"))
            loader.assert_not_called()
            runner.assert_not_called()
            writer.assert_not_called()
            with open(os.path.join(output_root, "run_state.json"),
                      encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["failure_stage"], "release_gate")
            self.assertFalse(state["final_outputs_generated"])
            self.assertFalse(any(name == "running"
                                 for name in os.listdir(output_root)))

    def test_modeling_exception_writes_fail_closed_state(self):
        with tempfile.TemporaryDirectory() as temp:
            output_root = os.path.join(temp, "w08_output")
            gate_result = {
                "stage": "W08", "gate": "FORMAL_W08_RELEASE",
                "status": "PASS", "formal_run_authorized": True,
                "code_commit": CODE_COMMIT,
            }
            with mock.patch.object(formal, "validate_formal_release_gate",
                                   return_value=gate_result), \
                    mock.patch.object(formal, "_load_population_and_provider",
                                       side_effect=RuntimeError("synthetic load failure")):
                with self.assertRaises(RuntimeError):
                    formal.formal(output_root=output_root, project_root=temp)
            with open(os.path.join(output_root, "run_state.json"),
                      encoding="utf-8") as handle:
                state = json.load(handle)
            self.assertEqual(state["status"], "failed")
            self.assertEqual(state["failure_stage"], "a_input_loading")
            self.assertEqual(state["exception_class"], "RuntimeError")
            self.assertEqual(state["code_commit"], CODE_COMMIT)
            self.assertFalse(state["B_data_read"])
            self.assertFalse(state["B_reader_invoked"])
            self.assertFalse(state["B_source_opened"])
            self.assertFalse(state["B_statistics_generated"])
            self.assertFalse(state["final_outputs_generated"])


if __name__ == "__main__":
    unittest.main()
