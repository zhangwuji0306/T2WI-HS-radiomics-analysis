from __future__ import absolute_import

import csv
import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from unittest import mock

import numpy as np
import pandas as pd

from prognosis_analysis.ft import ft05a_runner as ft


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PARENT = os.path.join(
    ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT05A")


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
        if not os.path.isdir(ft.DEFAULT_TECHNICAL_SOURCE_ROOT):
            os.makedirs(ft.DEFAULT_TECHNICAL_SOURCE_ROOT)
        self.tmp = tempfile.TemporaryDirectory(dir=OUTPUT_PARENT)
        self._output_constants = {
            name: getattr(ft, name) for name in (
                "CANONICAL_OUTPUT_ROOT", "DEFAULT_OUTPUT_ROOT", "DEFAULT_MANIFEST",
                "DEFAULT_CODE_AUDIT", "DEFAULT_TECHNICAL_AUDIT",
                "DEFAULT_RUN_STATE", "DEFAULT_CASE_ROOT",
                "DEFAULT_FEATURE_TABLE")}
        self.source_tmp = tempfile.TemporaryDirectory(
            dir=ft.DEFAULT_TECHNICAL_SOURCE_ROOT)
        self.root = self.source_tmp.name
        self.out = self.tmp.name
        # Keep the fixture synthetic while exercising the production rule that
        # one invocation has exactly one canonical output root.
        ft.CANONICAL_OUTPUT_ROOT = self.out
        ft.DEFAULT_OUTPUT_ROOT = self.out
        ft.DEFAULT_MANIFEST = os.path.join(self.out, "FT05_B_feature_manifest.json")
        ft.DEFAULT_CODE_AUDIT = os.path.join(self.out, "FT05A_code_audit.md")
        ft.DEFAULT_TECHNICAL_AUDIT = os.path.join(
            self.out, "FT05A_technical_audit.md")
        ft.DEFAULT_RUN_STATE = os.path.join(self.out, "FT05A_run_state.json")
        ft.DEFAULT_CASE_ROOT = os.path.join(self.out, "cases")
        ft.DEFAULT_FEATURE_TABLE = os.path.join(
            self.out, "FT05A_B_technical_features.csv")
        self.cohort = _technical_frame(self.root)
        self.w_path = os.path.join(self.root, "w_original.csv")
        w_rows = []
        for index in range(2):
            row = {"patient_id": "B%d" % index, "split": "B"}
            row.update((name, float(index + 1))
                       for name in ft.W_ORIGINAL_FEATURE_NAMES)
            w_rows.append(row)
        pd.DataFrame(w_rows).to_csv(self.w_path, index=False)
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
                "path": _relative(self.w_path),
                "asset_sha256": ft._sha256_file(self.w_path), "feature_count": 107,
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
        self.source_tmp.cleanup()
        for name, value in self._output_constants.items():
            setattr(ft, name, value)

    def _w_asset(self):
        return {"path": self.lock["habitat_definition"]["W_Original_asset"]["path"],
                "sha256": self.lock["habitat_definition"]["W_Original_asset"]["asset_sha256"], "feature_count": 107,
                "order_sha256": ft.W_ORIGINAL_ORDER_SHA256,
                "rows": {"B%d" % i: {name: float(i + 1)
                                      for name in ft.W_ORIGINAL_FEATURE_NAMES}
                           for i in range(2)}}

    def _write_w_original_csv(self, rows, malformed_row=None):
        header = ["patient_id", "split"] + list(ft.W_ORIGINAL_FEATURE_NAMES)
        with open(self.w_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            for patient_id, split, values in rows:
                writer.writerow([patient_id, split] + list(values))
            if malformed_row is not None:
                writer.writerow(malformed_row)
        self.lock["habitat_definition"]["W_Original_asset"]["asset_sha256"] = \
            ft._sha256_file(self.w_path)

    def _validate_manifest(self, manifest_path, expected_w_asset=True):
        kwargs = {"output_root": self.out, "_expected_lock": self.lock}
        if expected_w_asset:
            kwargs["_expected_w_asset"] = self._w_asset()
        return ft.validate_ft05a_technical_manifest(manifest_path, **kwargs)

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
                mock.patch.object(ft, "_validate_code_audit",
                                  return_value=self.contract["code_audit"]), \
                mock.patch.object(ft, "_validate_technical_audit",
                                  return_value={"path": _relative(self.technical_audit),
                                                "sha256": ft._sha256_file(self.technical_audit),
                                                "status": "accepted",
                                                "independent": True,
                                                "verdict": "PASS"}), \
                mock.patch.object(ft, "_frozen_boundary_identity",
                                  return_value="boundary-id"), \
                mock.patch.object(ft, "FORMAL_MODEL_LOCK",
                                  os.path.join(self.root, "formal_absent.json")):
            yield loader

    def _strict_code_audit(self, audit_hash):
        return {
            "path": _relative(self.code_audit),
            "sha256": audit_hash,
            "status": "accepted",
            "independent": True,
            "verdict": "PASS",
            "reviewed_commit": ft.ft04._git_head(),
            "runner_sha256": ft._sha256_file(ft.__file__),
            "contract_identity": ft.FT05A_CODE_PREP_CONTRACT_IDENTITY,
        }

    @contextmanager
    def _runtime_patches_without_technical_audit(self):
        with mock.patch.object(ft, "validate_ft05a_preflight",
                               return_value=self.contract), \
                mock.patch.object(ft, "_load_w_original_asset",
                                  return_value=self._w_asset()), \
                mock.patch.object(ft, "_validate_code_audit",
                                  return_value=self.contract["code_audit"]), \
                mock.patch.object(ft, "_frozen_boundary_identity",
                                  return_value="boundary-id"), \
                mock.patch.object(ft, "FORMAL_MODEL_LOCK",
                                  os.path.join(self.root, "formal_absent.json")):
            yield

    def _write_state_fixture(self, path, state):
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2,
                      sort_keys=True)
            handle.write("\n")

    def _read_bytes(self, path):
        with open(path, "rb") as handle:
            return handle.read()

    def test_static_audit_has_no_B_fit_or_reader_route(self):
        result = ft.static_validate()
        self.assertTrue(result["pass"], result["findings"])
        self.assertFalse(result["B_kmeans_fit"])
        self.assertFalse(result["outcome_accessed"])
        self.assertFalse(result["whole_tumor_reextraction"])

    def test_code_audit_is_bound_to_runner_commit_and_contract(self):
        reviewed = ft.ft04._git_head()
        text = ("Independent review: true\nVerdict: PASS\n"
                "Reviewed implementation commit: `%s`\n"
                "FT05A runner SHA-256: `%s`\n"
                "FT05A preparation contract identity: `%s`\n" % (
                    reviewed, ft._sha256_file(ft.__file__),
                    ft.FT05A_CODE_PREP_CONTRACT_IDENTITY))
        with open(self.code_audit, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        record = ft._validate_code_audit(self.code_audit)
        self.assertEqual(record["reviewed_commit"], reviewed)
        for marker, replacement in (
                ("FT05A runner SHA-256", "0" * 64),
                ("FT05A preparation contract identity", "forged-contract")):
            with open(self.code_audit, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(text.replace(
                    text.split(marker + ": ")[1].split("\n")[0], replacement))
            with self.assertRaises(ft.FT05AValidationError):
                ft._validate_code_audit(self.code_audit)

    def test_code_audit_rejects_forged_marker_and_intervening_code_change(self):
        reviewed = ft.ft04._git_head()
        text = ("Independent review: true\nVerdict: PASS\n"
                "Reviewed implementation commit: `%s`\n"
                "FT05A runner SHA-256: `%s`\n"
                "FT05A preparation contract identity: `%s`\n" % (
                    reviewed, ft._sha256_file(ft.__file__),
                    ft.FT05A_CODE_PREP_CONTRACT_IDENTITY))
        with open(self.code_audit, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text.replace("Independent review: true", "independent review note"))
        with mock.patch.object(ft, "_git_current_blob_hash", return_value="blob"), \
                mock.patch.object(ft, "_git_commit_blob_hash", return_value="blob"), \
                mock.patch.object(ft, "_git_paths_after", return_value=[]):
            with self.assertRaises(ft.FT05AValidationError):
                ft._validate_code_audit(self.code_audit)
        with open(self.code_audit, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        with mock.patch.object(ft, "_git_current_blob_hash", return_value="blob"), \
                mock.patch.object(ft, "_git_commit_blob_hash", return_value="blob"), \
                mock.patch.object(ft, "_git_paths_after",
                                  return_value=[ft._relative(ft.__file__)]):
            with self.assertRaises(ft.FT05AValidationError):
                ft._validate_code_audit(self.code_audit)

    def test_code_audit_accepts_real_post_review_technical_audit_path(self):
        production = self._output_constants
        reviewed = "7777498aa6135fb635814e2f86719bcdccae9384"
        current = "7542f7a88c32267952615a813a82df2acad7ea36"
        runner_sha = "a" * 64
        text = ("Independent review: true\nVerdict: PASS\n"
                "Reviewed implementation commit: `%s`\n"
                "FT05A runner SHA-256: `%s`\n"
                "FT05A preparation contract identity: `%s`\n" % (
                    reviewed, runner_sha,
                    ft.FT05A_CODE_PREP_CONTRACT_IDENTITY))
        canonical_code_audit = production["DEFAULT_CODE_AUDIT"]
        canonical_technical_audit = production["DEFAULT_TECHNICAL_AUDIT"]
        canonical_paths = [
            _relative(canonical_code_audit),
            _relative(canonical_technical_audit)]

        def fake_sha256(path):
            return runner_sha

        with mock.patch.object(ft, "DEFAULT_CODE_AUDIT",
                               canonical_code_audit), \
                mock.patch.object(ft, "DEFAULT_TECHNICAL_AUDIT",
                                  canonical_technical_audit), \
                mock.patch.object(ft, "_read_text", return_value=text), \
                mock.patch.object(ft, "_sha256_file", side_effect=fake_sha256), \
                mock.patch.object(ft.ft04, "_git_head", return_value=current), \
                mock.patch.object(ft.ft04, "_git_commit_is_ancestor",
                                  return_value=True), \
                mock.patch.object(ft, "_git_current_blob_hash",
                                  return_value="blob"), \
                mock.patch.object(ft, "_git_commit_blob_hash",
                                  return_value="blob"), \
                mock.patch.object(ft, "_git_paths_after",
                                  return_value=canonical_paths):
            record = ft._validate_code_audit(canonical_code_audit)
        self.assertEqual(record["reviewed_commit"], reviewed)

        for disallowed in (
                _relative(ft.__file__),
                _relative(os.path.join(ROOT, "tests", "test_ft05a_runner.py")),
                _relative(os.path.join(
                    ROOT, "prognosis_analysis", "ft",
                    "FT05A_B_technical_generation_audit_copy.md"))):
            with mock.patch.object(ft, "DEFAULT_CODE_AUDIT",
                                   canonical_code_audit), \
                    mock.patch.object(ft, "DEFAULT_TECHNICAL_AUDIT",
                                      canonical_technical_audit), \
                    mock.patch.object(ft, "_read_text", return_value=text), \
                    mock.patch.object(ft, "_sha256_file",
                                      side_effect=fake_sha256), \
                    mock.patch.object(ft.ft04, "_git_head", return_value=current), \
                    mock.patch.object(ft.ft04, "_git_commit_is_ancestor",
                                      return_value=True), \
                    mock.patch.object(ft, "_git_current_blob_hash",
                                      return_value="blob"), \
                    mock.patch.object(ft, "_git_commit_blob_hash",
                                      return_value="blob"), \
                    mock.patch.object(ft, "_git_paths_after",
                                      return_value=canonical_paths + [disallowed]):
                with self.assertRaises(ft.FT05AValidationError):
                    ft._validate_code_audit(canonical_code_audit)

    def test_technical_cohort_file_requires_preflight_token(self):
        cohort_path = os.path.join(self.root, "cohort.csv")
        self.cohort.to_csv(cohort_path, index=False)
        with self.assertRaises(ft.FT05AValidationError):
            ft.load_technical_cohort(_relative(cohort_path))

    def test_resolved_disallowed_namespaces_and_noncanonical_output_fail_closed(self):
        disallowed = (
            os.path.join(ROOT, "habitat_analysis", "output", "synthetic.bin"),
            os.path.join(ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT03", "synthetic.bin"),
            os.path.join(ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT04", "synthetic.bin"),
            os.path.join(ROOT, "prognosis_analysis", "output", "w08_nested_cv", "synthetic.bin"),
            os.path.join(ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "L9", "synthetic.bin"),
        )
        for path in disallowed:
            with self.assertRaises(ft.FT05AValidationError):
                ft._validate_technical_path(_relative(path), "synthetic source")
        with self.assertRaises(ft.FT05AValidationError):
            ft._validate_namespace_path(
                os.path.join(ROOT, "prognosis_analysis", "output", "other"),
                "FT05A output root", os.path.join(ROOT, "prognosis_analysis", "output", "other"))

    def test_structural_absence_and_minimum_roi_boundary_are_frozen(self):
        class Extractor(object):
            def __init__(self):
                self.calls = 0

            def execute(self, image, mask, label=1):
                self.calls += 1
                return dict((name, 1.0) for name in ft.R_LOW_FEATURE_NAMES)

        extractor = Extractor()
        empty, defined, available, state = ft._extract_habitat_features(
            extractor, None, np.zeros(9, dtype=np.uint8),
            ft.R_LOW_FEATURE_NAMES, "R_low")
        self.assertFalse(defined)
        self.assertFalse(available)
        self.assertEqual(state, "structurally_absent")
        self.assertTrue(all(value is None for value in empty.values()))
        small, defined, available, state = ft._extract_habitat_features(
            extractor, None, np.ones(9, dtype=np.uint8),
            ft.R_LOW_FEATURE_NAMES, "R_low")
        self.assertTrue(defined)
        self.assertFalse(available)
        self.assertEqual(state, "technical_small_roi")
        self.assertEqual(extractor.calls, 0)
        full, defined, available, state = ft._extract_habitat_features(
            extractor, None, np.ones(ft.MINIMUM_ROI_SIZE, dtype=np.uint8),
            ft.R_LOW_FEATURE_NAMES, "R_low")
        self.assertTrue(defined)
        self.assertTrue(available)
        self.assertEqual(state, "available")
        self.assertEqual(extractor.calls, 1)
        self.assertEqual(full[ft.R_LOW_FEATURE_NAMES[0]], 1.0)

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

    def test_first_full_run_emits_factual_pending_audit_without_manifest(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        os.remove(self.technical_audit)
        calls = []
        with self._runtime_patches_without_technical_audit():
            result = ft.run_ft05a(
                self.cohort, "run-pending-review", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(calls))

        self.assertEqual(result["status"], ft.TECHNICAL_COMPLETE_PENDING_REVIEW)
        self.assertEqual(calls, ["B0", "B1"])
        self.assertTrue(os.path.isfile(self.technical_audit))
        self.assertFalse(os.path.exists(manifest_path))
        audit_text = self._read_bytes(self.technical_audit).decode("utf-8")
        self.assertIn("Status: generated_pending_review", audit_text)
        self.assertIn("Independent review: false", audit_text)
        self.assertIn("Verdict: PENDING_REVIEW", audit_text)
        self.assertNotIn("Independent review: true", audit_text)
        self.assertNotIn("Status: accepted", audit_text)
        with self.assertRaises(ft.FT05AValidationError):
            ft._validate_technical_audit(self.technical_audit)

        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        self.assertEqual(state["status"], ft.TECHNICAL_COMPLETE_PENDING_REVIEW)
        self.assertEqual(state["technical_audit_path"], _relative(self.technical_audit))
        self.assertEqual(state["technical_audit_sha256"],
                         ft._sha256_file(self.technical_audit))
        with mock.patch.object(ft.ft04, "FT05_MANIFEST", manifest_path):
            with self.assertRaises(ft.ft04.FT04ValidationError):
                ft.ft04._validate_b_feature_manifest(
                    self.lock, manifest_path=manifest_path)

    def test_reviewer_acceptance_resumes_pending_run_without_reextraction(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        os.remove(self.technical_audit)
        with self._runtime_patches_without_technical_audit():
            pending = ft.run_ft05a(
                self.cohort, "run-review-resume", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
        self.assertEqual(pending["status"], ft.TECHNICAL_COMPLETE_PENDING_REVIEW)
        with self._runtime_patches_without_technical_audit():
            still_pending = ft.run_ft05a(
                self.cohort, "run-review-resume", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(
                    failure=AssertionError("pending resume recomputed a case")),
                resume=True)
        self.assertEqual(still_pending["status"],
                         ft.TECHNICAL_COMPLETE_PENDING_REVIEW)

        with open(self.technical_audit, "r", encoding="utf-8") as handle:
            accepted_text = handle.read()
        accepted_text = accepted_text.replace(
            "Status: generated_pending_review", "Status: accepted")
        accepted_text = accepted_text.replace(
            "Independent review: false", "Independent review: true")
        accepted_text = accepted_text.replace(
            "Verdict: PENDING_REVIEW", "Verdict: PASS")
        with open(self.technical_audit, "w", encoding="utf-8",
                  newline="\n") as handle:
            handle.write(accepted_text)

        with self._runtime_patches_without_technical_audit():
            result = ft.run_ft05a(
                self.cohort, "run-review-resume", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(
                    failure=AssertionError("completed case was recomputed")),
                resume=True)

        self.assertEqual(result["status"], "frozen")
        self.assertEqual(result["reviews"]["technical_audit"]["status"],
                         "accepted")
        self.assertTrue(result["reviews"]["technical_audit"]["independent"])
        self.assertEqual(result["reviews"]["technical_audit"]["sha256"],
                         ft._sha256_file(self.technical_audit))
        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        self.assertEqual(state["status"], "COMPLETED")
        self.assertNotIn("technical_audit_path", state)
        self.assertNotIn("technical_audit_sha256", state)
        self._validate_manifest(manifest_path)

    def test_actual_technical_manifest_passes_canonical_technical_validator(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            manifest = ft.run_ft05a(
                self.cohort, "run-downstream-technical", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
        checked, table, checked_path = self._validate_manifest(manifest_path)
        self.assertEqual(checked["artifact_id"], manifest["artifact_id"])
        self.assertEqual(list(table.columns), ft._technical_feature_columns(True))
        self.assertEqual(checked_path, ft._absolute_project_path(
            manifest["feature_table"]["path"], "technical table"))
        self.assertNotIn("年龄", table.columns)

    def test_manifest_source_tamper_is_rejected_end_to_end(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-manifest-tamper", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
        manifest = ft._read_json(manifest_path)
        manifest["source_records"][0]["image_path"] = _relative(
            os.path.join(ROOT, "prognosis_analysis", "output", "W08",
                         "forged_image.bin"))
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        with self.assertRaises(ft.FT05AValidationError):
            self._validate_manifest(manifest_path)

    def test_manifest_cannot_self_authorize_alternate_w_original_provenance(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-w-provenance", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
        alternate = os.path.join(self.root, "w_original_alternate.csv")
        shutil.copyfile(self.w_path, alternate)
        manifest = ft._read_json(manifest_path)
        alternate_relative = _relative(alternate)
        w_record = manifest["feature_blocks"]["W_Original"]
        w_record["asset_path"] = alternate_relative
        w_record["asset_sha256"] = ft._sha256_file(alternate)
        for source_record in manifest["source_records"]:
            source_record["w_original_asset_path"] = alternate_relative
            source_record["w_original_asset_sha256"] = w_record["asset_sha256"]
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        with self.assertRaises(ft.FT05AValidationError):
            self._validate_manifest(manifest_path, expected_w_asset=False)

    def test_manifest_rejects_duplicate_persisted_source_mappings(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-duplicate-source-mapping", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor())
        manifest = ft._read_json(manifest_path)
        first = manifest["source_records"][0]
        second = manifest["source_records"][1]
        for key in ("image_path", "roi_path", "source_image_key", "source_roi_key",
                    "image_sha256", "roi_sha256"):
            second[key] = first[key]
        second["case_identity_sha256"] = ft._case_identity({
            "patient_id": second["patient_id"],
            "image_path": second["image_path"],
            "roi_path": second["roi_path"],
            "source_image_key": second["source_image_key"],
            "source_roi_key": second["source_roi_key"],
        })
        technical = manifest["technical_cohort"]
        for key in ("image_path", "roi_path", "source_image_key", "source_roi_key"):
            technical["ordered_rows"][1][key] = second[key]
        ordered = pd.DataFrame(technical["ordered_rows"],
                               columns=technical["source_frame_columns"])
        technical["source_frame_sha256"] = ft._canonical_frame_hash(ordered)
        technical["source_mapping_hash"] = ft._sha256_text("\n".join(
            str(item["source_image_key"]) + "|" + str(item["source_roi_key"])
            for item in manifest["source_records"]))
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        with self.assertRaises(ft.FT05AValidationError):
            self._validate_manifest(manifest_path)

    def test_pilot_w_original_loader_materializes_only_selected_rows(self):
        seen_hashes = []
        original_sha = ft._sha256_file

        def record_sha(path):
            seen_hashes.append(os.path.realpath(path))
            return original_sha(path)

        with mock.patch.object(ft, "_sha256_file", side_effect=record_sha), \
                mock.patch.object(ft, "_w_original_rows_from_csv",
                                  wraps=ft._w_original_rows_from_csv) as streamed, \
                mock.patch.object(ft.pd, "to_numeric", wraps=ft.pd.to_numeric) as numeric:
            asset = ft._load_w_original_asset(
                self.lock, selected_patient_ids=["B0"])
        self.assertEqual(set(asset["rows"]), {"B0"})
        self.assertNotIn(os.path.realpath(self.w_path), seen_hashes)
        self.assertEqual(set(streamed.call_args[0][3]), {"B0"})
        self.assertEqual(numeric.call_count, len(ft.W_ORIGINAL_FEATURE_NAMES))

    def test_selected_and_full_w_original_loads_have_identical_row_and_source_hashes(self):
        cohort = ft.load_technical_cohort(
            self.cohort, technical_source_roots=ft.ALLOWED_TECHNICAL_ROOTS,
            accepted_w_path=self.lock["habitat_definition"]["W_Original_asset"]["path"])
        full = ft._load_w_original_asset(self.lock)
        selected = ft._load_w_original_asset(self.lock, selected_patient_ids=["B0"])
        self.assertEqual(full["rows"]["B0"], selected["rows"]["B0"])
        self.assertEqual(ft._w_original_row_hash(full["rows"]["B0"]),
                         ft._w_original_row_hash(selected["rows"]["B0"]))
        full_source = ft._source_record(cohort.iloc[0], full)
        selected_source = ft._source_record(cohort.iloc[0], selected)
        self.assertEqual(full_source, selected_source)
        self.assertEqual(ft._source_record_hash(full_source),
                         ft._source_record_hash(selected_source))

    def test_resume_reconciles_pilot_artifact_after_full_w_original_loading(self):
        first_calls = []
        second_calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with mock.patch.object(ft, "validate_ft05a_preflight",
                               return_value=self.contract), \
                mock.patch.object(ft, "_validate_code_audit",
                                  return_value=self.contract["code_audit"]), \
                mock.patch.object(ft, "_validate_technical_audit",
                                  return_value={"path": _relative(self.technical_audit),
                                                "sha256": ft._sha256_file(self.technical_audit),
                                                "status": "accepted", "independent": True,
                                                "verdict": "PASS"}), \
                mock.patch.object(ft, "_frozen_boundary_identity",
                                  return_value="boundary-id"), \
                mock.patch.object(ft, "FORMAL_MODEL_LOCK",
                                  os.path.join(self.root, "formal_absent.json")):
            pilot = ft.run_ft05a(
                self.cohort, "run-loader-consistency", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(first_calls), pilot_case_ids=["B0"])
            result = ft.run_ft05a(
                self.cohort, "run-loader-consistency", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(second_calls), resume=True)
        self.assertEqual(pilot["status"], "PILOT_COMPLETE")
        self.assertEqual(first_calls, ["B0"])
        self.assertEqual(second_calls, ["B1"])
        self.assertEqual(result["status"], "frozen")

    def test_reviewed_audit_hash_only_migration_preserves_pilot_and_run_identity(self):
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        first_calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        self.contract["code_audit"] = old_audit
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-audit-migration", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(first_calls), pilot_case_ids=["B0"])
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        pilot_state = ft._read_json(state_path)
        pilot_key = pilot_state["completed_case_keys"][0]
        pilot_hash = pilot_state["completed_case_artifact_hashes"][pilot_key]
        pilot_keys = list(pilot_state["pilot_case_keys"])
        old_payload = copy.deepcopy(pilot_state["identity_payload"])
        old_run_identity = pilot_state["run_identity_sha256"]

        second_calls = []
        self.contract["code_audit"] = new_audit
        events = []
        real_loader = ft._load_w_original_asset
        real_case_validator = ft._validate_case_artifact
        real_state_writer = ft._write_json_atomic

        def record_loader(lock, path_override=None, selected_patient_ids=None):
            events.append(("load_w_original", selected_patient_ids))
            return real_loader(lock, path_override,
                               selected_patient_ids=selected_patient_ids)

        def record_case_validation(*args, **kwargs):
            events.append(("validate_case", args[0]))
            return real_case_validator(*args, **kwargs)

        def record_state_write(path, payload, *args, **kwargs):
            events.append(("write", path))
            return real_state_writer(path, payload, *args, **kwargs)

        with self._patches() as loader, \
                mock.patch.object(ft, "_validate_case_artifact",
                                  side_effect=record_case_validation), \
                mock.patch.object(ft, "_write_json_atomic",
                                  side_effect=record_state_write):
            loader.side_effect = record_loader
            result = ft.run_ft05a(
                self.cohort, "run-audit-migration", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(second_calls), resume=True)

        final_state = ft._read_json(state_path)
        self.assertEqual(result["status"], "frozen")
        self.assertEqual(second_calls, ["B1"])
        self.assertNotEqual(final_state["run_identity_sha256"], old_run_identity)
        self.assertEqual(final_state["identity_migration"], {
            "from_code_audit_sha256": "a" * 64,
            "to_code_audit_sha256": "b" * 64,
            "reason": ft.FT05A_IDENTITY_MIGRATION_REASON,
        })
        for key, value in old_payload.items():
            if key == "code_audit_sha256":
                continue
            self.assertEqual(final_state["identity_payload"][key], value)
        self.assertEqual(final_state["identity_payload"]["code_audit_sha256"],
                         "b" * 64)
        self.assertEqual(final_state["pilot_case_keys"], pilot_keys)
        self.assertEqual(
            final_state["completed_case_artifact_hashes"][pilot_key],
            pilot_hash)
        self.assertEqual(final_state["run_identity_sha256"],
                         result["run_identity"])
        self.assertEqual(events[0][0], "load_w_original")
        self.assertIsNone(events[0][1])
        first_state_write = next(index for index, event in enumerate(events)
                                 if event[0] == "write" and
                                 event[1].endswith("FT05A_run_state.json"))
        self.assertTrue(any(event[0] == "validate_case"
                            for event in events[:first_state_write]))
        self.assertEqual(
            [event[1] for event in events if event[0] == "load_w_original"],
            [None, None])

    def test_identity_migration_rejects_unselected_w_original_tamper_before_write(self):
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        self.contract["code_audit"] = old_audit
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-unselected-w-tamper", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(), pilot_case_ids=["B0"])
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        original_state = self._read_bytes(state_path)
        original_asset = self._read_bytes(self.w_path)
        try:
            with open(self.w_path, "wb") as handle:
                handle.write(original_asset.replace(b",2.0", b",999.0", 1))
            self.contract["code_audit"] = new_audit
            real_loader = ft._load_w_original_asset
            with self._patches() as loader:
                loader.side_effect = real_loader
                with self.assertRaises(ft.FT05AValidationError):
                    ft.run_ft05a(
                        self.cohort, "run-unselected-w-tamper",
                        output_root=self.out, manifest_path=manifest_path,
                        code_audit_path=self.code_audit,
                        technical_audit_path=self.technical_audit,
                        processor=self._processor(), resume=True)
            self.assertEqual(self._read_bytes(state_path), original_state)
        finally:
            with open(self.w_path, "wb") as handle:
                handle.write(original_asset)

    def test_malformed_pilot_complete_migration_is_rejected_before_write(self):
        cohort = ft.load_technical_cohort(
            self.cohort, technical_source_roots=ft.ALLOWED_TECHNICAL_ROOTS,
            accepted_w_path=self.lock["habitat_definition"][
                "W_Original_asset"]["path"])
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        state = ft._initial_run_state(
            "run-malformed-pilot", cohort, self.lock, old_audit, self.out)
        state["status"] = "PILOT_COMPLETE"
        state["pilot_case_keys"] = [ft._case_identity(cohort.iloc[0])]
        state["pilot_completed_at_epoch"] = 1.0
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        self._write_state_fixture(state_path, state)
        original = self._read_bytes(state_path)
        expected = ft._initial_run_state(
            "run-malformed-pilot", cohort, self.lock, new_audit, self.out)
        validator = mock.Mock()
        with self.assertRaises(ft.FT05AValidationError):
            ft._load_or_create_state(
                state_path, expected, True, code_audit=new_audit,
                cohort=cohort, migration_validator=validator)
        validator.assert_not_called()
        self.assertEqual(self._read_bytes(state_path), original)

    def test_identity_migration_rejects_any_non_audit_identity_change(self):
        cohort = ft.load_technical_cohort(
            self.cohort, technical_source_roots=ft.ALLOWED_TECHNICAL_ROOTS,
            accepted_w_path=self.lock["habitat_definition"][
                "W_Original_asset"]["path"])
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        old_state = ft._initial_run_state(
            "run-identity-fields", cohort, self.lock, old_audit, self.out)
        old_state["status"] = "RUNNING"
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        self._write_state_fixture(state_path, old_state)
        original = self._read_bytes(state_path)
        new_expected = ft._initial_run_state(
            "run-identity-fields", cohort, self.lock, new_audit, self.out)
        changes = {
            "artifact": "different-artifact",
            "run_id": "different-run",
            "ft04_lock_identity_sha256": "different-lock",
            "cohort_sha256": "0" * 64,
            "candidate_hashes": {"R_low": "different", "R_high": "different"},
            "w_original_order_sha256": "0" * 64,
            "w_original_asset_path": "different-asset.csv",
            "w_original_asset_sha256": "0" * 64,
            "output_root": "different-output",
        }
        for key, value in changes.items():
            candidate = copy.deepcopy(new_expected)
            candidate["identity_payload"][key] = value
            candidate["run_identity_sha256"] = ft._sha256_text(
                ft._canonical_json(candidate["identity_payload"]))
            with self.assertRaises(ft.FT05AValidationError):
                ft._load_or_create_state(
                    state_path, candidate, True, code_audit=new_audit,
                    cohort=cohort, migration_validator=lambda state: None)
            self.assertEqual(self._read_bytes(state_path), original)

    def test_identity_migration_rejects_completed_frozen_nonresume_unaccepted_and_manifest(self):
        cohort = ft.load_technical_cohort(
            self.cohort, technical_source_roots=ft.ALLOWED_TECHNICAL_ROOTS,
            accepted_w_path=self.lock["habitat_definition"][
                "W_Original_asset"]["path"])
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        expected_old = ft._initial_run_state(
            "run-migration-rejections", cohort, self.lock, old_audit, self.out)
        expected_new = ft._initial_run_state(
            "run-migration-rejections", cohort, self.lock, new_audit, self.out)
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        for status in ("COMPLETED", "FROZEN"):
            state = copy.deepcopy(expected_old)
            state["status"] = status
            self._write_state_fixture(state_path, state)
            with self.assertRaises(ft.FT05AValidationError):
                ft._load_or_create_state(
                    state_path, expected_new, True, code_audit=new_audit,
                    cohort=cohort, migration_validator=lambda value: None)

        state = copy.deepcopy(expected_old)
        state["status"] = "PILOT_COMPLETE"
        self._write_state_fixture(state_path, state)
        with self.assertRaises(ft.FT05AValidationError):
            ft._load_or_create_state(
                state_path, expected_new, False, code_audit=new_audit,
                cohort=cohort, migration_validator=lambda value: None)

        bad_audit = copy.deepcopy(new_audit)
        bad_audit["independent"] = False
        self._write_state_fixture(state_path, state)
        with self.assertRaises(ft.FT05AValidationError):
            ft._load_or_create_state(
                state_path, expected_new, True, code_audit=bad_audit,
                cohort=cohort, migration_validator=lambda value: None)

        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with open(manifest_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump({"artifact_id": "FT05_B_feature_manifest",
                       "status": "frozen"}, handle)
        self._write_state_fixture(state_path, state)
        with self.assertRaises(ft.FT05AValidationError):
            ft._load_or_create_state(
                state_path, expected_new, True, code_audit=new_audit,
                cohort=cohort, manifest_path=manifest_path,
                migration_validator=lambda value: None)

    def test_identity_migration_state_write_is_atomic_and_preserves_original_on_failure(self):
        cohort = ft.load_technical_cohort(
            self.cohort, technical_source_roots=ft.ALLOWED_TECHNICAL_ROOTS,
            accepted_w_path=self.lock["habitat_definition"][
                "W_Original_asset"]["path"])
        old_audit = self._strict_code_audit("a" * 64)
        new_audit = self._strict_code_audit("b" * 64)
        expected_old = ft._initial_run_state(
            "run-migration-atomic", cohort, self.lock, old_audit, self.out)
        expected_old["status"] = "RUNNING"
        expected_new = ft._initial_run_state(
            "run-migration-atomic", cohort, self.lock, new_audit, self.out)
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        self._write_state_fixture(state_path, expected_old)
        original = self._read_bytes(state_path)
        validator = mock.Mock()

        def mutate_candidate(candidate):
            candidate["pilot_case_keys"].append("0" * 64)

        validator.side_effect = mutate_candidate
        with mock.patch.object(ft, "_write_json_atomic",
                               side_effect=IOError("synthetic atomic failure")):
            with self.assertRaises(IOError):
                ft._load_or_create_state(
                    state_path, expected_new, True, code_audit=new_audit,
                    cohort=cohort, migration_validator=validator)
        validator.assert_called_once()
        self.assertEqual(self._read_bytes(state_path), original)
        self.assertFalse(any(name.startswith("FT05A_run_state.json.tmp.")
                             for name in os.listdir(self.out)))

    def test_w_original_loader_rejects_malformed_nonfinite_and_duplicate_rows(self):
        valid = ["1.0"] * len(ft.W_ORIGINAL_FEATURE_NAMES)
        malformed = [("B0", "B", valid), ("B1", "B", valid)]
        nonfinite = [("B0", "B", ["nan"] + valid[1:]),
                     ("B1", "B", valid)]
        duplicate = [("B0", "B", valid), ("B0", "B", valid),
                     ("B1", "B", valid)]
        for rows, malformed_row in (
                (malformed, ["B_extra", "B"]),
                (nonfinite, None),
                (duplicate, None)):
            self._write_w_original_csv(rows, malformed_row=malformed_row)
            for selected_ids in (["B0"], None):
                kwargs = {} if selected_ids is None else {
                    "selected_patient_ids": selected_ids}
                with self.assertRaises(ft.FT05AValidationError):
                    ft._load_w_original_asset(self.lock, **kwargs)

    def test_exclusive_owner_rejects_concurrent_start(self):
        owner_path, owner = ft._acquire_run_ownership(
            self.out, "synthetic-run-identity")
        try:
            with self.assertRaises(ft.FT05AValidationError):
                ft._acquire_run_ownership(self.out, "synthetic-run-identity")
        finally:
            ft._release_run_ownership(owner_path, owner)

    def test_descendant_output_invocation_is_rejected_before_processing(self):
        first_calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches() as loader:
            pilot = ft.run_ft05a(
                self.cohort, "run-global-owner", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(first_calls), pilot_case_ids=["B0"])
            self.assertEqual(pilot["status"], "PILOT_COMPLETE")
            self.assertEqual(first_calls, ["B0"])
            loader.reset_mock()
            second_calls = []
            descendant = os.path.join(self.out, "alternate_run_root")
            with self.assertRaises(ft.FT05AValidationError):
                ft.run_ft05a(
                    self.cohort, "run-global-owner", output_root=descendant,
                    manifest_path=os.path.join(
                        descendant, "FT05_B_feature_manifest.json"),
                    code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(second_calls),
                    pilot_case_ids=["B0"])
            self.assertEqual(second_calls, [])
            loader.assert_not_called()
            self.assertFalse(os.path.exists(descendant))

    def test_nonexact_output_root_spellings_fail_before_side_effects(self):
        canonical = ft.CANONICAL_OUTPUT_ROOT
        aliases = [
            os.path.relpath(canonical, ROOT),
            os.path.join(canonical, ".", "nested", ".."),
            os.path.join(canonical, "..", os.path.basename(canonical)),
            canonical + os.sep,
        ]
        aliases.append(canonical.upper())
        if os.name == "nt":
            aliases.extend((canonical.replace("\\", "/"),
                            canonical + ".", canonical + " "))
        for alias in aliases:
            calls = []
            with mock.patch.object(ft, "_acquire_run_ownership",
                                   side_effect=AssertionError("owner")), \
                    mock.patch.object(ft, "_load_w_original_asset",
                                      side_effect=AssertionError("W_Original")), \
                    mock.patch.object(ft, "load_technical_cohort",
                                      side_effect=AssertionError("cohort")), \
                    mock.patch.object(ft, "_write_json_exclusive",
                                      side_effect=AssertionError("owner writer")), \
                    mock.patch.object(ft, "_write_json_atomic",
                                      side_effect=AssertionError("output writer")), \
                    mock.patch.object(ft, "_sha256_file",
                                      side_effect=AssertionError("hash")):
                with self.assertRaises(ft.FT05AValidationError):
                    ft.run_ft05a(
                        self.cohort, "run-nonexact-root", output_root=alias,
                        manifest_path=self.code_audit,
                        code_audit_path=self.code_audit,
                        technical_audit_path=self.technical_audit,
                        processor=lambda record, contract: calls.append(record))
            self.assertEqual(calls, [])
            self.assertFalse(os.path.exists(os.path.join(
                os.path.dirname(canonical), "FT05A_run_owner.json")))

    def test_exact_canonical_output_root_is_accepted(self):
        self.assertEqual(
            ft._validate_namespace_path(
                ft.CANONICAL_OUTPUT_ROOT, "FT05A output root",
                ft.CANONICAL_OUTPUT_ROOT),
            ft.CANONICAL_OUTPUT_ROOT)

    def test_production_default_tracked_artifacts_use_canonical_namespace(self):
        production = self._output_constants
        with mock.patch.object(
                ft, "CANONICAL_OUTPUT_ROOT", production["CANONICAL_OUTPUT_ROOT"]), \
                mock.patch.object(ft, "DEFAULT_MANIFEST",
                                  production["DEFAULT_MANIFEST"]), \
                mock.patch.object(ft, "DEFAULT_CODE_AUDIT",
                                  production["DEFAULT_CODE_AUDIT"]), \
                mock.patch.object(ft, "DEFAULT_TECHNICAL_AUDIT",
                                  production["DEFAULT_TECHNICAL_AUDIT"]), \
                mock.patch.object(ft, "DEFAULT_FEATURE_TABLE",
                                  production["DEFAULT_FEATURE_TABLE"]):
            for path, label in (
                    (production["DEFAULT_MANIFEST"], "FT05_B_feature_manifest"),
                    (production["DEFAULT_CODE_AUDIT"], "FT05A code audit"),
                    (production["DEFAULT_TECHNICAL_AUDIT"],
                     "FT05A technical audit")):
                self.assertEqual(
                    ft._validate_namespace_path(
                        path, label, production["CANONICAL_OUTPUT_ROOT"],
                        allow_ft_namespace=True),
                    os.path.realpath(path))

    def test_production_tracked_artifact_aliases_fail_before_side_effects(self):
        production = self._output_constants
        tracked = (
            ("manifest_path", production["DEFAULT_MANIFEST"],
             "FT05_B_feature_manifest"),
            ("code_audit_path", production["DEFAULT_CODE_AUDIT"],
             "FT05A code audit"),
            ("technical_audit_path", production["DEFAULT_TECHNICAL_AUDIT"],
             "FT05A technical audit"),
        )
        with mock.patch.object(ft, "DEFAULT_MANIFEST",
                               production["DEFAULT_MANIFEST"]), \
                mock.patch.object(ft, "DEFAULT_CODE_AUDIT",
                                  production["DEFAULT_CODE_AUDIT"]), \
                mock.patch.object(ft, "DEFAULT_TECHNICAL_AUDIT",
                                  production["DEFAULT_TECHNICAL_AUDIT"]), \
                mock.patch.object(ft, "DEFAULT_FEATURE_TABLE",
                                  production["DEFAULT_FEATURE_TABLE"]):
            for argument_name, canonical, label in tracked:
                aliases = [
                    os.path.relpath(canonical, ROOT),
                    os.path.join(os.path.dirname(canonical), ".",
                                 os.path.basename(canonical)),
                    os.path.join(os.path.dirname(canonical), "..",
                                 os.path.basename(os.path.dirname(canonical)),
                                 os.path.basename(canonical)),
                    canonical + os.sep,
                    canonical + ".",
                    canonical + " ",
                    os.path.join(os.path.dirname(canonical),
                                 "alternate_" + os.path.basename(canonical)),
                ]
                if os.name == "nt":
                    aliases.extend((canonical.upper(),
                                    canonical.replace("\\", "/")))
                for alias in dict.fromkeys(
                        value for value in aliases if value != canonical):
                    kwargs = {
                        "manifest_path": production["DEFAULT_MANIFEST"],
                        "code_audit_path": production["DEFAULT_CODE_AUDIT"],
                        "technical_audit_path": production[
                            "DEFAULT_TECHNICAL_AUDIT"],
                    }
                    kwargs[argument_name] = alias
                    calls = []
                    before = set(os.listdir(self.out))
                    with mock.patch.object(
                            ft, "validate_ft05a_preflight",
                            side_effect=AssertionError("preflight")), \
                            mock.patch.object(
                                ft, "_acquire_run_ownership",
                                side_effect=AssertionError("owner")) as owner, \
                            mock.patch.object(
                                ft, "_load_w_original_asset",
                                side_effect=AssertionError("W_Original")) as w_loader, \
                            mock.patch.object(
                                ft, "load_technical_cohort",
                                side_effect=AssertionError("cohort")) as cohort_loader, \
                            mock.patch.object(
                                ft, "_write_json_exclusive",
                                side_effect=AssertionError("owner writer")) as owner_writer, \
                            mock.patch.object(
                                ft, "_write_json_atomic",
                                side_effect=AssertionError("output writer")) as output_writer, \
                            mock.patch.object(
                                ft, "_sha256_file",
                                side_effect=AssertionError("hash")) as hasher:
                        with self.assertRaises(ft.FT05AValidationError):
                            ft.run_ft05a(
                                self.cohort, "run-production-alias",
                                output_root=self.out, processor=lambda record,
                                contract: calls.append(record), **kwargs)
                    self.assertEqual(calls, [])
                    self.assertEqual(set(os.listdir(self.out)), before)
                    for instrument in (owner, w_loader, cohort_loader,
                                       owner_writer, output_writer, hasher):
                        self.assertFalse(instrument.called)

    def test_symlinked_output_escape_is_rejected(self):
        target = tempfile.TemporaryDirectory(dir=OUTPUT_PARENT)
        alias = os.path.join(self.out, "output_escape_link")
        try:
            try:
                os.symlink(target.name, alias, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest("synthetic directory symlink unavailable: %s" % exc)
            with self.assertRaises(ft.FT05AValidationError):
                ft._validate_namespace_path(
                    alias, "FT05A output root", alias)
        finally:
            if os.path.lexists(alias):
                os.unlink(alias)
            target.cleanup()

    def test_junction_output_alias_is_rejected_before_processing(self):
        if os.name != "nt":
            self.skipTest("Windows junction test")
        target = tempfile.TemporaryDirectory(dir=OUTPUT_PARENT)
        alias = os.path.join(OUTPUT_PARENT, "synthetic_ft05a_junction_alias")
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", alias, target.name],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode != 0:
                self.skipTest("synthetic directory junction unavailable")
            calls = []
            with mock.patch.object(ft, "_acquire_run_ownership",
                                   side_effect=AssertionError("owner")), \
                    mock.patch.object(ft, "_load_w_original_asset",
                                      side_effect=AssertionError("W_Original")), \
                    mock.patch.object(ft, "load_technical_cohort",
                                      side_effect=AssertionError("cohort")):
                with self.assertRaises(ft.FT05AValidationError):
                    ft.run_ft05a(
                        self.cohort, "run-junction-alias", output_root=alias,
                        manifest_path=self.code_audit,
                        code_audit_path=self.code_audit,
                        technical_audit_path=self.technical_audit,
                        processor=lambda record, contract: calls.append(record))
            self.assertEqual(calls, [])
        finally:
            if os.path.lexists(alias):
                os.rmdir(alias)
            target.cleanup()

    def test_pilot_hashes_only_selected_sources_and_resume_hashes_remaining(self):
        first_calls = []
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        seen = []
        original_sha = ft._sha256_file

        def record_sha(path):
            if os.path.realpath(path).startswith(
                    os.path.realpath(ft.DEFAULT_TECHNICAL_SOURCE_ROOT)):
                seen.append(os.path.realpath(path))
            return original_sha(path)

        with self._patches(), mock.patch.object(ft, "_sha256_file",
                                                side_effect=record_sha):
            ft.run_ft05a(
                self.cohort, "run-pilot-boundary", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(first_calls), pilot_case_ids=["B0"])
        expected_pilot = {
            os.path.realpath(os.path.join(self.root, "image_0.bin")),
            os.path.realpath(os.path.join(self.root, "roi_0.bin")),
        }
        self.assertEqual(set(seen), expected_pilot)
        second_calls = []
        seen[:] = []
        with self._patches(), mock.patch.object(ft, "_sha256_file",
                                                side_effect=record_sha):
            ft.run_ft05a(
                self.cohort, "run-pilot-boundary", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(second_calls), resume=True)
        expected_all = set()
        for index in range(2):
            expected_all.add(os.path.realpath(os.path.join(self.root, "image_%d.bin" % index)))
            expected_all.add(os.path.realpath(os.path.join(self.root, "roi_%d.bin" % index)))
        self.assertEqual(set(seen), expected_all)
        self.assertEqual(second_calls, ["B1"])

    def test_tampered_completed_artifact_is_rejected_on_resume(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches():
            ft.run_ft05a(
                self.cohort, "run-tamper", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(), pilot_case_ids=["B0"])
        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        key = state["completed_case_keys"][0]
        artifact_path = os.path.join(self.out, "cases", key + ".json")
        artifact = ft._read_json(artifact_path)
        artifact["row"]["W__" + ft.W_ORIGINAL_FEATURE_NAMES[0]] = 999.0
        with open(artifact_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(artifact, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        with self._patches():
            with self.assertRaises(ft.FT05AValidationError):
                ft.run_ft05a(
                    self.cohort, "run-tamper", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(failure=AssertionError("recomputed")),
                    resume=True)

    def test_finalization_recovers_after_interrupted_state_transition(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches(), mock.patch.object(
                ft, "_recover_finalization", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                ft.run_ft05a(
                    self.cohort, "run-finalize-recovery", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor())
        state = ft._read_json(os.path.join(self.out, "FT05A_run_state.json"))
        self.assertEqual(state["status"], "FINALIZING")
        with self._patches():
            manifest = ft.run_ft05a(
                self.cohort, "run-finalize-recovery", output_root=self.out,
                manifest_path=manifest_path, code_audit_path=self.code_audit,
                technical_audit_path=self.technical_audit,
                processor=self._processor(failure=AssertionError("recomputed")),
                resume=True)
        self.assertEqual(manifest["status"], "frozen")
        self.assertEqual(ft._read_json(os.path.join(
            self.out, "FT05A_run_state.json"))["status"], "COMPLETED")

    def test_finalization_rejects_tampered_transaction_before_install(self):
        manifest_path = os.path.join(self.out, "FT05_B_feature_manifest.json")
        with self._patches(), mock.patch.object(
                ft, "_recover_finalization", side_effect=RuntimeError("interrupted")):
            with self.assertRaises(RuntimeError):
                ft.run_ft05a(
                    self.cohort, "run-finalize-tamper", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor())
        state_path = os.path.join(self.out, "FT05A_run_state.json")
        state = ft._read_json(state_path)
        state["finalization"]["table_path"] = _relative(
            os.path.join(self.out, "arbitrary_table.csv"))
        with open(state_path, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        with self._patches():
            with self.assertRaises(ft.FT05AValidationError):
                ft.run_ft05a(
                    self.cohort, "run-finalize-tamper", output_root=self.out,
                    manifest_path=manifest_path, code_audit_path=self.code_audit,
                    technical_audit_path=self.technical_audit,
                    processor=self._processor(), resume=True)
        self.assertFalse(os.path.exists(manifest_path))

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
