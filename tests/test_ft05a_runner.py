from __future__ import absolute_import

import os
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

import numpy as np
import pandas as pd

from prognosis_analysis.ft import ft05a_runner as ft


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PARENT = os.path.join(ROOT, "prognosis_analysis", "output")


def _relative(path):
    return os.path.relpath(path, ROOT).replace("\\", "/")


def _technical_frame(root, count=2):
    rows = []
    for index in range(count):
        image = os.path.join(root, "image_%d.bin" % index)
        roi = os.path.join(root, "roi_%d.bin" % index)
        with open(image, "wb") as handle:
            handle.write(("image-%d" % index).encode("ascii"))
        with open(roi, "wb") as handle:
            handle.write(("roi-%d" % index).encode("ascii"))
        rows.append({"patient_id": "B%d" % index,
                     "split": "B",
                     "image_path": _relative(image),
                     "roi_path": _relative(roi)})
    return pd.DataFrame(rows)


class FT05ARunnerTests(unittest.TestCase):

    def setUp(self):
        if not os.path.isdir(OUTPUT_PARENT):
            os.makedirs(OUTPUT_PARENT)
        self.tmp = tempfile.TemporaryDirectory(dir=OUTPUT_PARENT)
        self.root = self.tmp.name
        self.out = os.path.join(self.root, "FT05A")
        self.cohort = _technical_frame(self.root)
        self.code_audit = os.path.join(self.out, "FT05A_code_audit.md")
        self.technical_audit = os.path.join(self.out, "FT05A_technical_audit.md")
        if not os.path.isdir(self.out):
            os.makedirs(self.out)
        for path in (self.code_audit, self.technical_audit):
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write("Independent reviewer\nverdict: PASS\n")
        self.lock = {
            "lock_identity_sha256": "lock-identity",
            "b_access": {"state": "locked", "b_data_read": False,
                          "b_outcome_read": False},
            "prediction_contract": {"expected_model_input_hashes": {
                "M0": "m0", "M1": "m1", "M2": "m2", "M3L": "m3l",
                "M3H": "m3h", "M4": "m4", "M5": "m5"}},
            "habitat_definition": {"W_Original_asset": {
                "path": "feature_extract/output/synthetic_w_original.csv",
                "asset_sha256": "w-hash", "feature_count": 107,
                "order_sha256": ft.W_ORIGINAL_ORDER_SHA256,
                "reused_existing_asset": True, "reextracted": False}},
            "provenance": {"sources": {
                "ft01_asset_manifest": {"sha256": "ft01"},
                "habitat_freeze_lock": {"sha256": "habitat"},
                "w03_candidate_freeze": {"sha256": "candidate"}}}}
        self.contract = {
            "lock": self.lock,
            "frozen_boundary": {"center_low": 2.0, "center_high": 3.0,
                                 "boundary": 2.5},
            "slic_config": {}, "w03_config": {},
            "pyradiomics": {"configuration_sha256": "config"},
            "code_audit": {"path": _relative(self.code_audit),
                            "sha256": ft._sha256_file(self.code_audit),
                            "status": "accepted", "independent": True,
                            "verdict": "PASS"}}

    def tearDown(self):
        self.tmp.cleanup()

    def _w_asset(self):
        return {"path": self.lock["habitat_definition"]["W_Original_asset"]["path"],
                "sha256": "w-hash", "feature_count": 107,
                "order_sha256": ft.W_ORIGINAL_ORDER_SHA256,
                "rows": {"B%d" % i: {name: float(i + 1)
                                      for name in ft.W_ORIGINAL_FEATURE_NAMES}
                          for i in range(2)}}

    def _processor(self, calls=None, failure=None):
        def process(record, contract):
            if calls is not None:
                calls.append(record["patient_id"])
            if failure is not None:
                raise failure
            return {
                "habitat": {name: 1.0 for name in ft.GLOBAL_COLUMNS},
                "R_low": {name: 1.0 for name in ft.R_LOW_FEATURE_NAMES},
                "R_high": {name: 1.0 for name in ft.R_HIGH_FEATURE_NAMES},
                "R_low_structurally_defined": True,
                "R_high_structurally_defined": True,
                "R_low_technically_available": True,
                "R_high_technically_available": True,
                "extraction_evidence": {
                    "projection": "direct_frozen_A_full_boundary",
                    "boundary": contract["frozen_boundary"]["boundary"],
                    "pyradiomics_matches_A_W03": True,
                    "w_original_reused": True,
                    "b_kmeans_fit": False, "outcome_accessed": False,
                    "whole_tumor_reextraction": False,
                    "duplicate_extraction": False,
                    "formal_directory_mixing": False}}
        return process

    @contextmanager
    def _patches(self):
        with mock.patch.object(ft, "validate_ft05a_preflight",
                               return_value=self.contract), \
                mock.patch.object(ft, "_load_w_original_asset",
                                  return_value=self._w_asset()) as loader, \
                mock.patch.object(ft, "_frozen_boundary_identity",
                                  return_value="boundary-id"), \
                mock.patch.object(ft, "FORMAL_MODEL_LOCK",
                                  os.path.join(self.root, "formal_absent.json")):
            yield loader

    def test_static_audit_has_no_B_fit_or_reader_route(self):
        result = ft.static_validate()
        self.assertTrue(result["pass"], result["findings"])
        self.assertFalse(result["B_kmeans_fit"])
        self.assertFalse(result["outcome_accessed"])
        self.assertFalse(result["whole_tumor_reextraction"])

    def test_outcome_and_clinical_columns_fail_closed(self):
        for column in ("DFS_event", "DFS_time", "outcome", "clinical_status",
                       "PFS_event", "survival_time"):
            frame = self.cohort.copy()
            frame[column] = 1
            with self.assertRaises(ft.FT05AValidationError):
                ft.load_technical_cohort(frame)

    def test_outcome_and_clinical_paths_fail_closed(self):
        for marker in ("clinical", "DFS", "outcome", "survival"):
            frame = self.cohort.copy()
            frame.loc[0, "image_path"] = _relative(
                os.path.join(ROOT, "prognosis_analysis", "output", marker,
                             "image.nrrd"))
            with self.assertRaises(ft.FT05AValidationError):
                ft.load_technical_cohort(frame)

    def test_duplicate_patient_and_source_mappings_fail_closed(self):
        duplicate = self.cohort.copy()
        duplicate.loc[1, "patient_id"] = duplicate.loc[0, "patient_id"]
        with self.assertRaises(ft.FT05AValidationError):
            ft.load_technical_cohort(duplicate)
        duplicate = self.cohort.copy()
        duplicate.loc[1, "image_path"] = duplicate.loc[0, "image_path"]
        with self.assertRaises(ft.FT05AValidationError):
            ft.load_technical_cohort(duplicate)

    def test_exact_feature_order_and_counts_are_canonical(self):
        columns = ft._technical_feature_columns(True)
        self.assertEqual(columns[:2], ["patient_id", "split"])
        self.assertEqual(len(ft.R_LOW_FEATURE_NAMES), 49)
        self.assertEqual(len(ft.R_HIGH_FEATURE_NAMES), 10)
        self.assertEqual(len(ft.W_ORIGINAL_FEATURE_NAMES), 107)
        self.assertEqual(ft._candidate_hash(ft.R_LOW_FEATURE_NAMES),
                         ft.R_LOW_CANDIDATE_HASH)
        self.assertEqual(ft._candidate_hash(ft.R_HIGH_FEATURE_NAMES),
                         ft.R_HIGH_CANDIDATE_HASH)
        self.assertEqual(ft._candidate_hash(ft.W_ORIGINAL_FEATURE_NAMES),
                         ft.W_ORIGINAL_ORDER_SHA256)

    def test_successful_run_writes_one_table_manifest_and_completion_state(self):
        calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            manifest = ft.run_ft05a(
                self.cohort, "run-success", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(calls))
        self.assertEqual(calls, ["B0", "B1"])
        self.assertEqual(manifest["status"], "frozen")
        self.assertEqual(manifest["feature_table"]["row_count"], 2)
        table_path = os.path.join(self.out, "FT05A_B_technical_features.csv")
        self.assertTrue(os.path.isfile(table_path))
        self.assertEqual(ft._sha256_file(table_path),
                         manifest["feature_table"]["sha256"])
        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        self.assertEqual(state["status"], "COMPLETED")
        self.assertEqual(state["completed_case_count"], 2)
        self.assertTrue(all(column not in manifest["feature_table"]["columns"]
                            for column in ("DFS_time", "DFS_event", "clinical_status")))

    def test_resume_skips_completed_pilot_cases_without_recomputation(self):
        first_calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            pilot = ft.run_ft05a(
                self.cohort, "run-pilot", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(first_calls), pilot_case_ids=["B0"])
        self.assertEqual(pilot["status"], "PILOT_COMPLETE")
        self.assertEqual(first_calls, ["B0"])
        second_calls = []
        with self._patches():
            result = ft.run_ft05a(
                self.cohort, "run-pilot", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(second_calls), resume=True)
        self.assertEqual(second_calls, ["B1"])
        self.assertEqual(result["status"], "frozen")

    def test_completed_run_refuses_rerun_before_processor(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-once", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
            with self.assertRaises(ft.FT05AValidationError):
                ft.run_ft05a(
                    self.cohort, "run-once", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(failure=AssertionError("recomputed")),
                    resume=True)

    def test_conflicting_run_state_refuses_before_W_asset_load(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches() as loader:
            ft.run_ft05a(
                self.cohort, "run-a", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
            loader.reset_mock()
            with self.assertRaises(ft.FT05AValidationError):
                ft.run_ft05a(
                    self.cohort, "run-b", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(), resume=True)
            loader.assert_not_called()

    def test_synthetic_technical_failure_is_recorded_and_no_manifest_is_frozen(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            with self.assertRaises(ft.FT05ARunError):
                ft.run_ft05a(
                    self.cohort, "run-failure", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(failure=ValueError("synthetic failure")))
        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        self.assertEqual(state["status"], "FAILED")
        self.assertTrue(state["failed_cases"])
        self.assertFalse(os.path.exists(manifest_path))

    def test_formal_output_namespace_is_rejected(self):
        with self.assertRaises(ft.FT05AValidationError):
            ft.run_ft05a(
                self.cohort, "formal-run",
                output_root=os.path.join(ROOT, "prognosis_analysis", "output", "W08"),
                code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())


if __name__ == "__main__":
    unittest.main(verbosity=2)
