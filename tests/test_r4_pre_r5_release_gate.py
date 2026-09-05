"""Synthetic R4 regression evidence for the pre-R5 W08 release hold.

These tests exercise the formal entry point with synthetic gate inputs only.
They do not read project patient, outcome, imaging, or B artifacts.
"""
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


CURRENT_COMMIT = "a" * 40
OLD_COMMIT = "b" * 40
B_FLAGS = (
    "B_data_read", "B_reader_invoked", "B_source_opened",
    "B_statistics_generated",
)
FROZEN_BINDINGS = {"P4R_reconciliation": "current-p4r"}
FINAL_OUTPUT_NAMES = formal.W08_FINAL_OUTPUT_NAMES


def _synthetic_execution_status():
    return {
        "execution": {
            "stage": "W08", "gate": "HOLD",
            "formal_w08_started": False, "last_attempt_status": "not_started",
        },
        "last_attempt": {
            "attempt_id": "none", "status": "not_started",
            "failure_stage": "none", "failure_reason_summary": "none",
            "code_commit_at_attempt": CURRENT_COMMIT,
        },
        "b_access": dict((key, False) for key in B_FLAGS),
    }


def _write_synthetic_g3_artifacts(project_root, summary_binding,
                                  certificate_code="present"):
    certificate_dir = os.path.join(
        project_root, "prognosis_analysis", "output",
        "p5_technical_preflight_A")
    os.makedirs(certificate_dir)
    certificate = {
        "stage": "G3", "status": "PASS",
        "P5_technical_preflight": "PASS",
        "all_required_runs_estimable": True,
        "all_paired_populations_equal": True,
    }
    if certificate_code == "present":
        certificate["code_commit"] = CURRENT_COMMIT
    elif certificate_code == "stale":
        certificate["code_commit"] = OLD_COMMIT
    for key in B_FLAGS + ("performance_generated",
                          "patient_level_outputs_written"):
        certificate[key] = False

    summary = {
        "stage": "P5", "status": "technical_only_complete",
        "fold_units": 50, "run_rows": 850, "required_runs": 17,
        "minimumROISize": 10,
        "binding_hashes": {"P4R_reconciliation": summary_binding},
    }
    for key in B_FLAGS + ("performance_generated",
                          "patient_level_outputs_written"):
        summary[key] = False

    for name, value in (("P5_release_gate.json", certificate),
                        ("P5_technical_preflight_summary.json", summary)):
        with open(os.path.join(certificate_dir, name), "w",
                  encoding="utf-8") as handle:
            json.dump(value, handle)


class PreR5ReleaseGateRegressionTests(unittest.TestCase):
    def _run_case(self, case_name, expected_check, p4r_error=None,
                  g3_mode="actual", summary_binding=None,
                  certificate_code=None):
        with tempfile.TemporaryDirectory() as project_root:
            output_root = os.path.join(project_root, "synthetic_w08_output")
            if summary_binding is not None:
                _write_synthetic_g3_artifacts(
                    project_root, summary_binding,
                    certificate_code=certificate_code or "present")

            patches = {
                "_validate_p4r_reconciliation": {"status": "PASS"},
                "_validate_frozen_bindings": FROZEN_BINDINGS,
                "_validate_w08_configuration": {
                    "status": "implementation_ready"},
                "_validate_execution_status": _synthetic_execution_status(),
                "_validate_technical_freeze": {"B_data_read": False},
                "_validate_w05_access_boundary": {"status": "PASS"},
                "_validate_model_freeze_absent": {"status": "absent"},
            }
            if p4r_error is not None:
                patches["_validate_p4r_reconciliation"] = p4r_error
            if g3_mode == "pass":
                patches["_validate_g3_certificate"] = {
                    "code_commit": CURRENT_COMMIT}

            with ExitStack() as stack:
                stack.enter_context(mock.patch.object(
                    formal, "PROJECT_ROOT", project_root))
                stack.enter_context(mock.patch.object(
                    formal, "_git_head", return_value=CURRENT_COMMIT))
                stack.enter_context(mock.patch.object(
                    formal, "_git_commit_resolves", return_value=True))
                for name, value in patches.items():
                    if isinstance(value, BaseException):
                        patcher = mock.patch.object(
                            formal, name, side_effect=value)
                    else:
                        patcher = mock.patch.object(
                            formal, name, return_value=value)
                    stack.enter_context(patcher)
                loader = stack.enter_context(mock.patch.object(
                    formal, "_load_population_and_provider",
                    side_effect=AssertionError(
                        "%s: patient loader called" % case_name)))
                run_w08 = stack.enter_context(mock.patch.object(
                    formal.w08, "run_w08",
                    side_effect=AssertionError(
                        "%s: model execution called" % case_name)))
                write_results = stack.enter_context(mock.patch.object(
                    formal, "write_results",
                    side_effect=AssertionError(
                        "%s: output writer called" % case_name)))
                begin_attempt = stack.enter_context(mock.patch.object(
                    formal, "_begin_attempt",
                    side_effect=AssertionError(
                        "%s: formal attempt started" % case_name)))

                with self.assertRaises(formal.W08ReleaseGateError) as raised:
                    formal.formal(output_root)

            result = raised.exception.result
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["formal_authorized"])
            self.assertEqual(
                result["checks"]["frozen_W03_W04_W07_W07A_bindings"]["status"],
                "PASS")
            self.assertTrue(any(expected_check in reason
                                for reason in result["failure_reasons"]))
            self.assertEqual(result["B_access"],
                             dict((key, False) for key in B_FLAGS))

            release_gate_path = os.path.join(output_root, "release_gate.json")
            run_state_path = os.path.join(output_root, "run_state.json")
            with open(release_gate_path, encoding="utf-8") as handle:
                persisted_gate = json.load(handle)
            with open(run_state_path, encoding="utf-8") as handle:
                run_state = json.load(handle)

            self.assertEqual(persisted_gate["status"], "FAIL")
            self.assertFalse(persisted_gate["formal_authorized"])
            self.assertEqual(run_state["status"], "failed")
            self.assertEqual(run_state["failure_stage"], "release_gate")
            self.assertFalse(run_state["formal_run_started"])
            self.assertFalse(run_state["final_outputs_generated"])
            for key in B_FLAGS:
                self.assertFalse(run_state[key])

            self.assertFalse(os.path.exists(
                os.path.join(output_root, "attempts")))
            for name in FINAL_OUTPUT_NAMES:
                self.assertFalse(os.path.exists(os.path.join(output_root, name)))
            loader.assert_not_called()
            run_w08.assert_not_called()
            write_results.assert_not_called()
            begin_attempt.assert_not_called()

    def test_pre_r5_hold_cases_are_fail_closed_at_formal_entry(self):
        cases = (
            {
                "name": "stale P4R reconciliation",
                "expected_check": "P4R_provenance_reconciliation",
                "p4r_error": RuntimeError(
                    "current P4R reconciliation hash differs from frozen binding"),
                "g3_mode": "pass",
            },
            {
                "name": "missing G3 release certificate",
                "expected_check": "G3_release_certificate",
            },
            {
                "name": "stale G3 summary binding",
                "expected_check": "G3_release_certificate",
                "summary_binding": "old-p4r",
            },
            {
                "name": "missing exact code binding",
                "expected_check": "G3_release_certificate",
                "summary_binding": "current-p4r",
                "certificate_code": "missing",
            },
            {
                "name": "stale exact code binding",
                "expected_check": "G3_release_certificate",
                "summary_binding": "current-p4r",
                "certificate_code": "stale",
            },
        )
        for case in cases:
            with self.subTest(case=case["name"]):
                case = dict(case)
                case["case_name"] = case.pop("name")
                self._run_case(**case)


if __name__ == "__main__":
    unittest.main()
