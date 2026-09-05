import json
import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


SCRIPTS = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_formal_run_a as formal  # noqa: E402


COMMIT = "a" * 40
OLD_COMMIT = "b" * 40


def _status(formal_started=False, attempt=None, b_flags=None):
    flags = {
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
    }
    if b_flags:
        flags.update(b_flags)
    return {
        "execution": {
            "stage": "W08",
            "formal_w08_started": formal_started,
        },
        "last_attempt": attempt or {},
        "b_access": flags,
        "model_freeze_lock": {"present": False, "status": "absent"},
        "outputs": {"final_outputs_generated": False},
    }


def _passing_certificate(code_commit):
    return {
        "stage": "G3R",
        "status": "PASS",
        "code_commit": code_commit,
        "P5_technical_preflight": "PASS",
        "frozen_fold_units": 50,
        "completed_fold_units": 50,
        "all_required_runs_estimable": True,
        "all_paired_populations_equal": True,
        "bindings_verified": True,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "performance_generated": False,
        "patient_level_outputs_written": False,
    }


class W08FormalReleaseGateTests(unittest.TestCase):
    def _patch_non_provenance_checks(self):
        return [
            patch.object(formal, "_git_commit", return_value=COMMIT),
            patch.object(formal, "_git_worktree_clean", return_value=True),
            patch.object(formal, "_check_hash", return_value=COMMIT),
            patch.object(formal, "_validate_w04_protocol",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_w07_bindings",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_candidate_hashes",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_technical_freeze",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_g3_release_certificate",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_w05_access_boundary",
                         return_value={"status": "PASS"}),
            patch.object(formal, "_validate_execution_status",
                         return_value={"status": "PASS"}),
        ]

    def test_tampered_sop_or_stale_successor_is_machine_reported(self):
        patches = self._patch_non_provenance_checks()
        for item in patches:
            item.start()
        try:
            with patch.object(
                    formal.p4r, "validate_manifest",
                    side_effect=ValueError("current successor revision is stale")):
                with self.assertRaises(formal.W08ReleaseGateError) as raised:
                    formal.run_release_gate(
                        output_root=tempfile.gettempdir(),
                        project_root=tempfile.gettempdir())
        finally:
            for item in reversed(patches):
                item.stop()
        result = raised.exception.result
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(result["failure_reasons"])
        self.assertTrue(any("stale" in reason for reason in
                            result["failure_reasons"]))
        self.assertEqual(
            result["checks"]["P4R_provenance_reconciliation"]["status"],
            "FAIL")

    def test_release_gate_pass_requires_every_check(self):
        patches = self._patch_non_provenance_checks()
        for item in patches:
            item.start()
        try:
            with patch.object(formal.p4r, "validate_manifest",
                              return_value={"status": "PASS"}):
                result = formal.run_release_gate(
                    output_root=tempfile.gettempdir(),
                    project_root=tempfile.gettempdir())
        finally:
            for item in reversed(patches):
                item.stop()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["code_commit"], COMMIT)
        self.assertFalse(result["failure_reasons"])
        self.assertTrue(all(value["status"] == "PASS"
                            for value in result["checks"].values()))

    def test_g3_certificate_bound_to_old_commit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "P5_release_gate.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_passing_certificate(OLD_COMMIT), handle)
            with self.assertRaisesRegex(RuntimeError,
                                        "different code commit"):
                formal._validate_g3_release_certificate(tmp, COMMIT, path)

    def test_stale_release_certificate_status_fails_closed(self):
        certificate = _passing_certificate(COMMIT)
        certificate["status"] = "FAIL"
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "P5_release_gate.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(certificate, handle)
            with self.assertRaisesRegex(RuntimeError,
                                        "status is not PASS"):
                formal._validate_g3_release_certificate(tmp, COMMIT, path)

    def test_model_freeze_presence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = os.path.join(tmp, "prognosis_analysis",
                                "model_freeze_lock.json")
            os.makedirs(os.path.dirname(lock))
            with open(lock, "w", encoding="utf-8") as handle:
                handle.write("{}\n")
            with patch.object(formal.p4r, "validate_execution_status",
                              return_value=_status()):
                with self.assertRaisesRegex(RuntimeError,
                                            "model_freeze_lock.json exists"):
                    formal._validate_execution_status(tmp, tmp, COMMIT)

    def test_non_false_b_flag_is_rejected(self):
        status = _status(b_flags={"B_source_opened": True})
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(formal.p4r, "validate_execution_status",
                              return_value=status):
                with self.assertRaisesRegex(RuntimeError,
                                            "B_source_opened is not false"):
                    formal._validate_execution_status(tmp, tmp, COMMIT)

    def test_existing_incomplete_output_and_unreconciled_attempt_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_path = os.path.join(tmp, formal.RUN_STATE_NAME)
            with open(state_path, "w", encoding="utf-8") as handle:
                json.dump({"stage": "W08", "status": "running"}, handle)
            with patch.object(formal.p4r, "validate_execution_status",
                              return_value=_status()):
                with self.assertRaisesRegex(RuntimeError,
                                            "prior incomplete"):
                    formal._validate_execution_status(tmp, tmp, COMMIT)

        attempt = {"status": "failed"}
        status = _status(formal_started=True, attempt=attempt)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(formal.p4r, "validate_execution_status",
                              return_value=status):
                with self.assertRaisesRegex(RuntimeError,
                                            "explicit reconciliation"):
                    formal._validate_execution_status(tmp, tmp, COMMIT)

    def test_archived_failed_attempt_can_be_explicitly_reconciled(self):
        attempt = {
            "attempt_id": "attempt_001_failed",
            "status": "failed",
            "failure_stage": "nested_cv_modeling_radiomics_extraction",
            "failure_reason_summary": "synthetic locked-boundary failure",
            "code_commit_at_attempt": OLD_COMMIT,
        }
        status = _status(formal_started=True, attempt=attempt)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(formal.p4r, "validate_execution_status",
                              return_value=status), \
                    patch.object(formal.p4r, "_git_commit_exists",
                                  return_value=True):
                result = formal._validate_execution_status(tmp, tmp, COMMIT)
        self.assertEqual(result["reconciliation"]["status"], "PASS")
        self.assertEqual(result["reconciliation"]["attempt_id"],
                         "attempt_001_failed")
        self.assertEqual(result["reconciliation"]["prior_code_commit"],
                         OLD_COMMIT)

    def test_formal_gate_precedes_any_patient_or_outcome_read(self):
        gate_result = {
            "stage": "W08", "gate": "FORMAL_W08_RELEASE",
            "status": "FAIL", "failure_reasons": ["tampered SOP"],
        }
        error = formal.W08ReleaseGateError("gate failed", gate_result)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(formal, "run_release_gate",
                              side_effect=error), \
                    patch.object(formal, "_load_population_and_provider") as loader, \
                    patch.object(formal.w08, "run_w08") as runner:
                with self.assertRaises(formal.W08ReleaseGateError):
                    formal.formal(tmp)
                loader.assert_not_called()
                runner.assert_not_called()
            with open(os.path.join(tmp, formal.RUN_STATE_NAME),
                      "r", encoding="utf-8") as handle:
                failed = json.load(handle)
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["failure_stage"], "release_gate")
            self.assertEqual(failed["exception_class"],
                             "W08ReleaseGateError")
            self.assertFalse(failed["final_outputs_generated"])
            self.assertFalse(failed["B_data_read"])
            with open(os.path.join(tmp, formal.RELEASE_GATE_RESULT_NAME),
                      "r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["status"], "FAIL")

    def test_modeling_exception_records_failed_state_and_no_final_outputs(self):
        gate_result = {
            "stage": "W08", "gate": "FORMAL_W08_RELEASE",
            "status": "PASS", "code_commit": COMMIT,
            "failure_reasons": [],
        }
        provider = SimpleNamespace(_case_cache={})
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(formal, "run_release_gate",
                              return_value=gate_result), \
                    patch.object(formal, "_load_population_and_provider",
                                  return_value=([], None, provider)), \
                    patch.object(formal.w08, "run_w08",
                                  side_effect=ValueError("synthetic fit failure")):
                with self.assertRaisesRegex(ValueError, "synthetic fit failure"):
                    formal.formal(tmp)
            with open(os.path.join(tmp, formal.RUN_STATE_NAME),
                      "r", encoding="utf-8") as handle:
                failed = json.load(handle)
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["failure_stage"], "nested_cv_modeling")
            self.assertEqual(failed["exception_class"], "ValueError")
            self.assertEqual(failed["code_commit"], COMMIT)
            self.assertIn("environment_fingerprint", failed)
            self.assertFalse(failed["final_outputs_generated"])
            for flag in formal.B_ACCESS_FLAGS:
                self.assertFalse(failed[flag])
            self.assertFalse(any(os.path.exists(os.path.join(tmp, name))
                                 for name in formal.FINAL_OUTPUT_NAMES))


if __name__ == "__main__":
    unittest.main()
