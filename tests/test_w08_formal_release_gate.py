import json
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest import mock


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_formal_run_a as formal  # noqa: E402


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CURRENT_COMMIT = "a" * 40
OLD_COMMIT = "b" * 40
B_FLAGS = (
    "B_data_read", "B_reader_invoked", "B_source_opened",
    "B_statistics_generated",
)


def _status(b_data_read=False, failed=False, commit=CURRENT_COMMIT):
    if failed:
        execution = {
            "stage": "W08", "gate": "HOLD",
            "formal_w08_started": True, "last_attempt_status": "failed",
        }
        last_attempt = {
            "attempt_id": "attempt_001_failed", "status": "failed",
            "failure_stage": "nested_cv_modeling_radiomics_extraction",
            "failure_reason_summary": "synthetic failure",
            "code_commit_at_attempt": commit,
        }
    else:
        execution = {
            "stage": "W08", "gate": "HOLD",
            "formal_w08_started": False, "last_attempt_status": "not_started",
        }
        last_attempt = {
            "attempt_id": "none", "status": "not_started",
            "failure_stage": "none", "failure_reason_summary": "none",
            "code_commit_at_attempt": commit,
        }
    return {
        "execution": execution,
        "last_attempt": last_attempt,
        "b_access": dict((key, b_data_read if key == "B_data_read" else False)
                          for key in B_FLAGS),
    }


class W08ReleaseGateTests(unittest.TestCase):
    def _base_patches(self, status=None):
        status = status or _status()
        return status

    def _run_with_base_gate(self, output_root, status=None, **overrides):
        status = self._base_patches(status)
        values = {
            "_validate_p4r_reconciliation": {"status": "PASS"},
            "_validate_frozen_bindings": {"P4R_reconciliation": "1"},
            "_validate_w08_configuration": {"status": "implementation_ready"},
            "_validate_execution_status": status,
            "_validate_technical_freeze": {"B_data_read": False},
            "_validate_w05_access_boundary": {"status": "PASS"},
            "_validate_g3_certificate": {"code_commit": CURRENT_COMMIT},
        }
        values.update(overrides)
        with ExitStack() as stack:
            for name, value in values.items():
                if isinstance(value, BaseException):
                    patcher = mock.patch.object(
                        formal, name, side_effect=value)
                else:
                    patcher = mock.patch.object(
                        formal, name, return_value=value)
                stack.enter_context(patcher)
            with mock.patch.object(formal, "_git_head", return_value=CURRENT_COMMIT), \
                    mock.patch.object(formal, "_git_commit_resolves", return_value=True):
                return formal.validate_w08_release_gate(
                    output_root=output_root, project_root=ROOT)

    def test_gate_passes_without_patient_or_outcome_fixture(self):
        with tempfile.TemporaryDirectory() as output_root:
            result = self._run_with_base_gate(output_root)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["formal_authorized"])
        self.assertEqual(result["B_access"], dict((key, False) for key in B_FLAGS))

    def test_tampered_sop_or_provenance_fails_closed(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(
                    output_root,
                    _validate_p4r_reconciliation=RuntimeError(
                        "current successor SOP differs from approved provenance"))
        result = raised.exception.result
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("P4R_provenance_reconciliation", result["failure_reasons"][0])

    def test_stale_successor_or_release_binding_fails_closed(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(
                    output_root,
                    _validate_frozen_bindings=RuntimeError(
                        "stale successor/release binding"))
        self.assertIn("frozen_W03_W04_W07_W07A_bindings",
                      raised.exception.result["failure_reasons"][0])

    def test_g3_certificate_old_commit_is_rejected(self):
        with tempfile.TemporaryDirectory() as project_root:
            certificate_dir = os.path.join(
                project_root, "prognosis_analysis", "output",
                "p5_technical_preflight_A")
            os.makedirs(certificate_dir)
            certificate = {
                "stage": "G3", "status": "PASS",
                "P5_technical_preflight": "PASS",
                "all_required_runs_estimable": True,
                "all_paired_populations_equal": True,
                "code_commit": OLD_COMMIT,
            }
            summary = {
                "stage": "P5", "status": "technical_only_complete",
                "fold_units": 50, "run_rows": 850, "required_runs": 17,
                "minimumROISize": 10,
                "binding_hashes": {"P4R_reconciliation": "1"},
            }
            for key in B_FLAGS + ("performance_generated",
                                  "patient_level_outputs_written"):
                certificate[key] = False
                summary[key] = False
            for name, value in (("P5_release_gate.json", certificate),
                                ("P5_technical_preflight_summary.json", summary)):
                with open(os.path.join(certificate_dir, name), "w",
                          encoding="utf-8") as handle:
                    json.dump(value, handle)
            with mock.patch.object(formal, "_git_commit_resolves", return_value=True):
                with self.assertRaisesRegex(RuntimeError, "stale code commit"):
                    formal._validate_g3_certificate(
                        project_root, CURRENT_COMMIT,
                        {"P4R_reconciliation": "1"})

    def test_model_freeze_presence_blocks_formal_release(self):
        with tempfile.TemporaryDirectory() as output_root:
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(
                    output_root,
                    _validate_model_freeze_absent=RuntimeError(
                        "model_freeze_lock.json exists"))
        self.assertTrue(any("model_freeze_absent" in reason
                            for reason in raised.exception.result["failure_reasons"]))

    def test_nonfalse_b_flag_blocks_formal_release(self):
        with tempfile.TemporaryDirectory() as output_root:
            status = _status(b_data_read=True)
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(output_root, status=status)
        self.assertTrue(any("execution_status.B_data_read" in reason
                            for reason in raised.exception.result["failure_reasons"]))

    def test_incomplete_output_or_unreconciled_attempt_blocks_gate(self):
        with tempfile.TemporaryDirectory() as output_root:
            with open(os.path.join(output_root, "fold_results.csv"), "w",
                      encoding="utf-8") as handle:
                handle.write("incomplete\n")
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(output_root)
        self.assertTrue(any("prior final outputs" in reason
                            for reason in raised.exception.result["failure_reasons"]))

        with tempfile.TemporaryDirectory() as output_root:
            os.makedirs(os.path.join(output_root, "attempts", "attempt_001_failed"))
            with self.assertRaises(formal.W08ReleaseGateError) as raised:
                self._run_with_base_gate(
                    output_root, status=_status(failed=True))
        self.assertTrue(any("reconciliation artifacts" in reason
                            for reason in raised.exception.result["failure_reasons"]))

    def test_formal_gate_failure_never_calls_patient_loader_or_writes_running(self):
        with tempfile.TemporaryDirectory() as output_root:
            gate_result = {
                "stage": "W08_FORMAL_RELEASE", "status": "FAIL",
                "formal_authorized": False, "code_commit": CURRENT_COMMIT,
                "checks": {}, "failure_reasons": ["synthetic gate failure"],
                "B_access": dict((key, False) for key in B_FLAGS),
                "final_outputs_generated": False,
            }
            gate_error = formal.W08ReleaseGateError(gate_result)
            with mock.patch.object(formal, "validate_w08_release_gate",
                                   side_effect=gate_error), \
                    mock.patch.object(formal, "_load_population_and_provider",
                                      side_effect=AssertionError("patient loader called")) as loader:
                with self.assertRaises(formal.W08ReleaseGateError):
                    formal.formal(output_root)
            loader.assert_not_called()
            with open(os.path.join(output_root, "run_state.json"),
                      encoding="utf-8") as handle:
                state = json.load(handle)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["failure_stage"], "release_gate")
        self.assertEqual(state["exception_class"], "W08ReleaseGateError")
        self.assertFalse(state["formal_run_started"])
        self.assertFalse(state["final_outputs_generated"])
        for key in B_FLAGS:
            self.assertFalse(state[key])

    def test_runtime_exception_records_failed_state_without_completion(self):
        with tempfile.TemporaryDirectory() as output_root:
            release_gate = {
                "stage": "W08_FORMAL_RELEASE", "status": "PASS",
                "formal_authorized": True, "code_commit": CURRENT_COMMIT,
                "checks": {}, "failure_reasons": [],
                "B_access": dict((key, False) for key in B_FLAGS),
                "final_outputs_generated": False,
            }
            with mock.patch.object(formal, "validate_w08_release_gate",
                                   return_value=release_gate), \
                    mock.patch.object(formal, "_load_population_and_provider",
                                      side_effect=RuntimeError("synthetic input failure")), \
                    mock.patch.object(formal, "_git_head",
                                      return_value=CURRENT_COMMIT):
                with self.assertRaisesRegex(RuntimeError, "synthetic input failure"):
                    formal.formal(output_root)
            with open(os.path.join(output_root, "run_state.json"),
                      encoding="utf-8") as handle:
                state = json.load(handle)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["failure_stage"], "a_input_load")
        self.assertTrue(state["formal_run_started"])
        self.assertEqual(state["code_commit"], CURRENT_COMMIT)
        self.assertIn("python_version", state["environment_fingerprint"])
        self.assertFalse(state["final_outputs_generated"])
        for key in B_FLAGS:
            self.assertFalse(state[key])


if __name__ == "__main__":
    unittest.main()
