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
EXECUTION_COMMIT = "c" * 40
BINDING_COMMIT = "d" * 40
B_FLAGS = (
    "B_data_read", "B_reader_invoked", "B_source_opened",
    "B_statistics_generated",
)


def _status(b_data_read=False, failed=False, commit=CURRENT_COMMIT,
            attempt_id="attempt_001_failed"):
    if failed:
        execution = {
            "stage": "W08", "gate": "HOLD",
            "formal_w08_started": True, "last_attempt_status": "failed",
        }
        last_attempt = {
            "attempt_id": attempt_id, "status": "failed",
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


def _write_archived_attempt(output_root, attempt_id="attempt_002_failed",
                            run_status="failed", failure_status="failed",
                            b_overrides=None, final_outputs=False):
    attempt_root = os.path.join(output_root, "attempts", attempt_id)
    os.makedirs(attempt_root)
    failure = {
        "attempt_id": attempt_id,
        "stage": "W08",
        "status": failure_status,
        "failure_stage": "nested_cv_modeling_radiomics_extraction",
        "exception_summary": "synthetic failure",
        "code_commit_at_attempt": CURRENT_COMMIT,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": final_outputs,
    }
    if b_overrides:
        failure.update(b_overrides)
    with open(os.path.join(attempt_root, "failure_audit.json"), "w",
              encoding="utf-8") as handle:
        json.dump(failure, handle)
    run_state = {
        "stage": "W08",
        "status": run_status,
        "formal_run": True,
        "failure_stage": "nested_cv_modeling_radiomics_extraction",
        "code_commit": CURRENT_COMMIT,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": final_outputs,
    }
    with open(os.path.join(attempt_root, "run_state.json"), "w",
              encoding="utf-8") as handle:
        json.dump(run_state, handle)


def _write_r0_compatible_attempt(output_root):
    attempt_id = "attempt_001_failed"
    attempt_root = os.path.join(output_root, "attempts", attempt_id)
    os.makedirs(attempt_root)
    failure = {
        "attempt_id": attempt_id,
        "stage": "W08",
        "status": "failed",
        "failure_stage": "nested_cv_modeling_radiomics_extraction",
        "exception_summary": "synthetic failure",
        "code_commit_at_attempt": CURRENT_COMMIT,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "final_outputs_generated": False,
    }
    with open(os.path.join(attempt_root, "failure_audit.json"), "w",
              encoding="utf-8") as handle:
        json.dump(failure, handle)
    run_state = {
        "A_population": 393,
        "B_data_read": False,
        "formal_run": True,
        "slic_cache_cases": 0,
        "stage": "W08",
        "started_at_epoch": 1.0,
        "status": "modeling",
        "W_columns": 1130,
    }
    with open(os.path.join(attempt_root, "run_state.json"), "w",
              encoding="utf-8") as handle:
        json.dump(run_state, handle)


def _write_r5_successor_fixture(project_root, execution_commit=EXECUTION_COMMIT,
                                 binding_commit=BINDING_COMMIT):
    aggregate_path = os.path.join(
        project_root, "prognosis_analysis", "R5_P5_G3R_aggregate_evidence.json")
    audit_path = os.path.join(
        project_root, "prognosis_analysis", "R5_P5_G3R_audit.md")
    current_root = os.path.join(
        project_root, "prognosis_analysis", "output",
        "p5_technical_preflight_A_G3R")
    legacy_root = os.path.join(
        project_root, "prognosis_analysis", "output",
        "p5_technical_preflight_A")
    os.makedirs(os.path.dirname(aggregate_path))
    os.makedirs(current_root)
    os.makedirs(legacy_root)
    for root in (current_root, legacy_root):
        with open(os.path.join(root, "P5_release_gate.json"), "w",
                  encoding="utf-8") as handle:
            handle.write("aggregate-only")

    artifact_sha = formal._sha256(os.path.join(current_root, "P5_release_gate.json"))
    legacy_sha = formal._sha256(os.path.join(legacy_root, "P5_release_gate.json"))
    aggregate = {
        "schema": "P5_G3R_aggregate_evidence",
        "version": "1.0",
        "stage": "G3R",
        "status": "PASS",
        "certificate_generation": {"code_commit": execution_commit},
        "successor": {
            "current_output": "prognosis_analysis/output/p5_technical_preflight_A_G3R",
            "successor_of": "prognosis_analysis/output/p5_technical_preflight_A",
            "legacy_output_preserved": True,
            "legacy_artifact_sha256": {"P5_release_gate.json": legacy_sha},
        },
        "current_artifact_sha256": {"P5_release_gate.json": artifact_sha},
        "release_binding": {
            "schema": "P5_G3R_release_binding",
            "version": "1.0",
            "execution_code_commit": execution_commit,
            "current_evidence_binding_commit": binding_commit,
            "successor_mode": "evidence_only_append_only",
            "allowed_paths": list(formal.R5_ALLOWED_SUCCESSOR_PATHS),
        },
    }
    with open(aggregate_path, "w", encoding="utf-8") as handle:
        json.dump(aggregate, handle, indent=2, sort_keys=True)
    with open(audit_path, "w", encoding="utf-8") as handle:
        handle.write("# R5 technical release audit\n")
    aggregate_without_binding = dict(aggregate)
    aggregate_without_binding.pop("release_binding")
    return aggregate, aggregate_without_binding


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
                with self.assertRaisesRegex(RuntimeError, "code bindings differ"):
                    formal._validate_g3_certificate(
                        project_root, CURRENT_COMMIT,
                        {"P4R_reconciliation": "1"})

    def _validate_successor_fixture(self, project_root, diff=None,
                                     aggregate_overrides=None,
                                     resolves=True, ancestor=True):
        aggregate, snapshot = _write_r5_successor_fixture(project_root)
        if aggregate_overrides:
            aggregate["release_binding"].update(aggregate_overrides)
            with open(os.path.join(
                    project_root, "prognosis_analysis",
                    "R5_P5_G3R_aggregate_evidence.json"), "w",
                    encoding="utf-8") as handle:
                json.dump(aggregate, handle, indent=2, sort_keys=True)
        current_aggregate_path = os.path.join(
            project_root, "prognosis_analysis",
            "R5_P5_G3R_aggregate_evidence.json")
        current_audit_path = os.path.join(
            project_root, "prognosis_analysis", "R5_P5_G3R_audit.md")
        with open(current_aggregate_path, "rb") as handle:
            current_aggregate_bytes = handle.read()
        with open(current_audit_path, "rb") as handle:
            audit_bytes = handle.read()
        snapshot_bytes = json.dumps(
            snapshot, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
        certificate = {
            "compatibility_provenance": {
                "compatibility_code_path": "code.py",
                "compatibility_code_sha256": "1" * 64,
                "compatibility_config_path": "config.json",
                "compatibility_config_sha256": "2" * 64,
            }
        }

        def show_bytes(_root, commit, path):
            if path == formal.R5_AGGREGATE_EVIDENCE_RELATIVE:
                if commit == CURRENT_COMMIT:
                    return current_aggregate_bytes
                if commit == BINDING_COMMIT:
                    return snapshot_bytes
            if path == formal.R5_AUDIT_RELATIVE:
                if commit == CURRENT_COMMIT or commit == BINDING_COMMIT:
                    return audit_bytes
            if path in ("code.py", "config.json"):
                return b"frozen"
            raise AssertionError("unexpected Git snapshot: %s:%s" % (commit, path))

        with mock.patch.object(formal, "_git_commit_resolves",
                               side_effect=lambda _root, commit: resolves), \
                mock.patch.object(formal, "_git_commit_is_ancestor",
                                   return_value=ancestor), \
                mock.patch.object(formal, "_git_diff_name_status",
                                   return_value=(diff or [
                                       ("A", formal.R5_AGGREGATE_EVIDENCE_RELATIVE),
                                       ("A", formal.R5_AUDIT_RELATIVE)])), \
                mock.patch.object(formal, "_git_show_bytes",
                                   side_effect=show_bytes), \
                mock.patch.object(formal, "_git_snapshot_sha256",
                                   side_effect=lambda _root, _commit, path:
                                   certificate["compatibility_provenance"][
                                       "compatibility_code_sha256" if path == "code.py"
                                       else "compatibility_config_sha256"]):
            return formal._validate_r5_successor_binding(
                project_root, EXECUTION_COMMIT, CURRENT_COMMIT, certificate)

    def test_evidence_only_successor_accepts_strict_binding(self):
        with tempfile.TemporaryDirectory() as project_root:
            result = self._validate_successor_fixture(project_root)
        self.assertEqual(result["execution_code_commit"], EXECUTION_COMMIT)
        self.assertEqual(result["current_evidence_binding_commit"], BINDING_COMMIT)

    def test_successor_rejects_code_change(self):
        with tempfile.TemporaryDirectory() as project_root:
            with self.assertRaisesRegex(RuntimeError, "non-evidence changes"):
                self._validate_successor_fixture(
                    project_root,
                    diff=[("A", formal.R5_AGGREGATE_EVIDENCE_RELATIVE),
                          ("A", formal.R5_AUDIT_RELATIVE),
                          ("M", "prognosis_analysis/scripts/w08_formal_run_a.py")])

    def test_successor_rejects_wrong_execution_commit(self):
        with tempfile.TemporaryDirectory() as project_root:
            with self.assertRaisesRegex(RuntimeError, "execution commit"):
                self._validate_successor_fixture(
                    project_root,
                    aggregate_overrides={"execution_code_commit": OLD_COMMIT})

    def test_successor_rejects_forged_successor(self):
        with tempfile.TemporaryDirectory() as project_root:
            with self.assertRaisesRegex(RuntimeError, "binding commit"):
                self._validate_successor_fixture(project_root, resolves=False)

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

    def test_archived_failure_schema_accepts_explicit_failed_attempt(self):
        with tempfile.TemporaryDirectory() as output_root:
            _write_archived_attempt(output_root)
            result = self._run_with_base_gate(
                output_root,
                status=_status(failed=True, attempt_id="attempt_002_failed"))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["prior_attempts_reconciled"]["status"],
                         "PASS")

    def test_r0_archived_attempt_schema_remains_compatible(self):
        with tempfile.TemporaryDirectory() as output_root:
            _write_r0_compatible_attempt(output_root)
            result = self._run_with_base_gate(
                output_root, status=_status(failed=True))
        self.assertEqual(result["status"], "PASS")

    def test_archived_attempt_inflight_statuses_fail_closed(self):
        for run_status in ("running", "modeling", "incomplete", "unknown"):
            with self.subTest(run_status=run_status):
                with tempfile.TemporaryDirectory() as output_root:
                    _write_archived_attempt(
                        output_root, run_status=run_status)
                    with self.assertRaises(formal.W08ReleaseGateError) as raised:
                        self._run_with_base_gate(
                            output_root,
                            status=_status(
                                failed=True, attempt_id="attempt_002_failed"))
                self.assertTrue(any("explicitly failed" in reason
                                    for reason in raised.exception.result[
                                        "failure_reasons"]))

    def test_archived_attempt_missing_or_unsafe_fields_fail_closed(self):
        with tempfile.TemporaryDirectory() as output_root:
            _write_archived_attempt(
                output_root, b_overrides={"B_source_opened": True})
            with self.assertRaises(formal.W08ReleaseGateError):
                self._run_with_base_gate(
                    output_root,
                    status=_status(failed=True, attempt_id="attempt_002_failed"))

        with tempfile.TemporaryDirectory() as output_root:
            _write_archived_attempt(output_root, final_outputs=True)
            with self.assertRaises(formal.W08ReleaseGateError):
                self._run_with_base_gate(
                    output_root,
                    status=_status(failed=True, attempt_id="attempt_002_failed"))

        with tempfile.TemporaryDirectory() as output_root:
            _write_archived_attempt(output_root)
            failure_path = os.path.join(
                output_root, "attempts", "attempt_002_failed",
                "failure_audit.json")
            with open(failure_path, "r", encoding="utf-8") as handle:
                failure = json.load(handle)
            del failure["failure_stage"]
            with open(failure_path, "w", encoding="utf-8") as handle:
                json.dump(failure, handle)
            with self.assertRaises(formal.W08ReleaseGateError):
                self._run_with_base_gate(
                    output_root,
                    status=_status(failed=True, attempt_id="attempt_002_failed"))

    def test_formal_gate_returned_fail_never_calls_patient_loader_or_writes_running(self):
        with tempfile.TemporaryDirectory() as output_root:
            gate_result = {
                "stage": "W08_FORMAL_RELEASE", "status": "FAIL",
                "formal_authorized": False, "code_commit": CURRENT_COMMIT,
                "checks": {}, "failure_reasons": ["synthetic gate failure"],
                "B_access": dict((key, False) for key in B_FLAGS),
                "final_outputs_generated": False,
            }
            with mock.patch.object(formal, "validate_w08_release_gate",
                                   return_value=gate_result), \
                    mock.patch.object(formal, "_load_population_and_provider",
                                      side_effect=AssertionError("patient loader called")) as loader:
                with self.assertRaises(formal.W08ReleaseGateError):
                    formal.formal(output_root)
            loader.assert_not_called()
            with open(os.path.join(output_root, "run_state.json"),
                      encoding="utf-8") as handle:
                state = json.load(handle)
            with open(os.path.join(output_root, "release_gate.json"),
                      encoding="utf-8") as handle:
                persisted_gate = json.load(handle)
        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["failure_stage"], "release_gate")
        self.assertFalse(state["formal_run_started"])
        self.assertEqual(persisted_gate["status"], "FAIL")
        self.assertFalse(persisted_gate["formal_authorized"])

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
