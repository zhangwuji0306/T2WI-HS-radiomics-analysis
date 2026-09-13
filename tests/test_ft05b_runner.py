"""Synthetic FT05B gate and reader regression tests."""
from __future__ import absolute_import

import csv
import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

import pandas as pd

from prognosis_analysis.ft import ft05b_runner as ft


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


class FT05BRunnerTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = self.temp.name
        self.saved = {}
        self._build_fixture()

    def tearDown(self):
        for name, value in self.saved.items():
            if isinstance(name, tuple):
                target, attr, old_value = value
                setattr(target, attr, old_value)
            else:
                setattr(ft, name, value)
        self.temp.cleanup()

    def _patch(self, name, value):
        if name not in self.saved:
            self.saved[name] = getattr(ft, name)
        setattr(ft, name, value)

    def _patch_object(self, target, name, value):
        key = (id(target), name)
        if key not in self.saved:
            self.saved[key] = (target, name, getattr(target, name))
        setattr(target, name, value)

    def _write_json(self, path, value):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    def _build_fixture(self):
        self._patch("_PROJECT_ROOT", self.root)
        paths = {
            "FT04_LOCK_PATH": os.path.join(self.root, "ft04.json"),
            "FORMAL_MODEL_LOCK": os.path.join(self.root, "formal.json"),
            "FT05A_AMENDMENT_PATH": os.path.join(self.root, "amendment.md"),
            "FT05A_TECHNICAL_AUDIT_PATH": os.path.join(self.root, "audit.md"),
            "FT_B_UNLOCK_PATH": os.path.join(self.root, "unlock.json"),
            "FT05B_RECEIPT_PATH": os.path.join(self.root, "receipt.json"),
        }
        for name, path in paths.items():
            self._patch(name, path)
        rel = {
            "FT05A_MANIFEST_RELATIVE_PATH": "manifest.finalize.json",
            "FT05A_TABLE_RELATIVE_PATH": "table.finalize.csv",
            "FT05A_DECLARED_TABLE_RELATIVE_PATH": "table.csv",
        }
        for name, value in rel.items():
            self._patch(name, value)
        manifest_path = os.path.join(self.root, rel["FT05A_MANIFEST_RELATIVE_PATH"])
        table_path = os.path.join(self.root, rel["FT05A_TABLE_RELATIVE_PATH"])
        self._patch("FT05A_MANIFEST_PATH", manifest_path)
        self._patch("FT05A_TABLE_PATH", table_path)
        outcome_path = os.path.join(self.root, "outcomes.csv")
        identifiers = ["B%03d" % index for index in range(163)]
        with open(outcome_path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(list(ft.B_OUTCOME_COLUMNS))
            for index, identifier in enumerate(identifiers):
                writer.writerow([identifier, float(index + 12),
                                 1 if index < 42 else 0])
        self._patch("OUTCOME_SOURCE_PATH", outcome_path)

        columns = list(ft.ft05a._technical_feature_columns(include_split=True))
        rows = []
        for identifier in identifiers:
            row = {}
            for column in columns:
                if column == "patient_id":
                    row[column] = identifier
                elif column == "split":
                    row[column] = "B"
                elif column.endswith("_technically_available") or \
                        column.endswith("_structurally_defined") or \
                        column == "W_Original_available":
                    row[column] = 1
                else:
                    row[column] = 1.0
            rows.append(row)
        with open(table_path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        table_hash = _sha256_file(table_path)
        manifest_hash_placeholder = "0" * 64
        audit_path = paths["FT05A_TECHNICAL_AUDIT_PATH"]
        cohort_hash = "c" * 64
        w_asset_path = os.path.join(self.root, "w_asset.csv")
        with open(w_asset_path, "w", encoding="utf-8") as handle:
            handle.write("synthetic W_Original asset\n")
        w_asset_hash = _sha256_file(w_asset_path)
        audit_text = """# FT05A B Technical Generation Audit

Status: accepted
Independent review: true
Verdict: PASS
FT05A run identity SHA-256: `run-id`
FT05A cohort SHA-256: `cohort-hash`
FT05A case-completion evidence SHA-256: `completion-hash`
Technical case count: 163
FT04 lock identity SHA-256: `lock-id`
FT05A row-schema SHA-256: `row-schema`
W_Original asset SHA-256: `w-asset`
W_Original order SHA-256: `w-order`
Outcome-blind: true
Outcome accessed: false
B K-means fit: false
W_Original reused: true
Repeat extraction: false
""".replace("FT05A run identity SHA-256: `run-id`",
            "FT05A run identity SHA-256: `%s`" % ("b" * 64)).replace(
                "FT05A cohort SHA-256: `cohort-hash`",
                "FT05A cohort SHA-256: `%s`" % cohort_hash).replace(
                    "FT05A case-completion evidence SHA-256: `completion-hash`",
                    "FT05A case-completion evidence SHA-256: `%s`" % ("d" * 64)).replace(
                        "FT04 lock identity SHA-256: `lock-id`",
                        "FT04 lock identity SHA-256: `%s`" % ("a" * 64)).replace(
                            "FT05A row-schema SHA-256: `row-schema`",
                            "FT05A row-schema SHA-256: `%s`" % ft.EXPECTED_ROW_SCHEMA_SHA256).replace(
                                "W_Original asset SHA-256: `w-asset`",
                                "W_Original asset SHA-256: `%s`" % w_asset_hash).replace(
                                    "W_Original order SHA-256: `w-order`",
                                    "W_Original order SHA-256: `%s`" % ft.EXPECTED_W_ORDER_SHA256)
        with open(audit_path, "w", encoding="utf-8") as handle:
            handle.write(audit_text)
        audit_hash = _sha256_file(audit_path)

        self._patch("EXPECTED_LOCK_IDENTITY", "a" * 64)
        self._patch("EXPECTED_FT05A_RUN_IDENTITY", "b" * 64)
        self._patch("EXPECTED_FT05A_COHORT_SHA256", cohort_hash)
        self._patch("EXPECTED_COMPLETION_EVIDENCE_SHA256", "d" * 64)
        self._patch("EXPECTED_TABLE_SHA256", table_hash)
        self._patch("EXPECTED_MANIFEST_SHA256", manifest_hash_placeholder)
        self._patch("EXPECTED_W_ASSET_SHA256", w_asset_hash)
        self._patch("EXPECTED_AUDIT_SHA256", audit_hash)
        lock = {
            "artifact_id": "FT_model_freeze_lock",
            "stage": "FT04",
            "status": "FROZEN",
            "lock_identity_sha256": "a" * 64,
            "b_access": {"state": "locked", "b_data_read": False,
                          "b_outcome_read": False, "ft06_executed": False},
            "formal_lock_at_freeze": {"exists": False},
            "formal_lock_path": "prognosis_analysis/model_freeze_lock.json",
            "prediction_contract": {"expected_model_input_hashes": {
                model_id: "hash-%s" % model_id
                for model_id in ("M0", "M1", "M2", "M3L", "M3H", "M4", "M5")}},
            "habitat_definition": {"W_Original_asset": {
                "path": "w_asset.csv", "asset_sha256": w_asset_hash}},
            "provenance": {
                "sources": {key: {"sha256": "source-%s" % key}
                            for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                                        "w03_candidate_freeze")},
                "pyradiomics": {"configuration": "frozen"},
            },
        }
        self._write_json(paths["FT04_LOCK_PATH"], lock)
        with open(paths["FT05A_AMENDMENT_PATH"], "w", encoding="utf-8") as handle:
            handle.write("""Status: SCIENTIFICALLY_FROZEN_WITH_ENGINEERING_FINALIZATION_EXCEPTION
manifest.finalize.json
table.finalize.csv
%s
%s
%s
%s
%s
%s
Completed unique B cases | `163/163`
""" % (table_hash, manifest_hash_placeholder, "d" * 64,
       ft.EXPECTED_ROW_SCHEMA_SHA256, "a" * 64, "b" * 64))
        manifest = {
            "artifact_id": "FT05_B_feature_manifest",
            "schema_version": "1.0",
            "stage": "FT05A",
            "status": "frozen",
            "purpose": "technical_only_outcome_blind_B_feature_table",
            "ft04_lock_identity_sha256": "a" * 64,
            "run_identity": "b" * 64,
            "technical_schema": {"clinical_predictors_included": False,
                                 "clinical_predictors_join_stage": "authorized_outcome_stage"},
            "model_input_hashes": lock["prediction_contract"]["expected_model_input_hashes"],
            "completion": {"completed_case_count": 163,
                           "table_sha256": table_hash,
                           "case_completion_evidence_hash": "d" * 64},
            "feature_table": {"path": "table.csv", "sha256": table_hash,
                              "format": "csv", "complete": True,
                              "columns": columns, "row_count": 163,
                              "patient_id_column": "patient_id", "patient_count": 163,
                              "patient_ids_unique": True, "duplicate_patient_count": 0,
                              "duplicate_extraction_count": 0, "extraction_count": 163},
            "feature_blocks": {
                "R_low": {"feature_names": list(ft.ft05a.R_LOW_FEATURE_NAMES),
                          "count": 49, "candidate_hash": ft.EXPECTED_R_LOW_CANDIDATE_SHA256},
                "R_high": {"feature_names": list(ft.ft05a.R_HIGH_FEATURE_NAMES),
                           "count": 10, "candidate_hash": ft.EXPECTED_R_HIGH_CANDIDATE_SHA256},
                "W_Original": {"feature_names": list(ft.ft05a.W_ORIGINAL_FEATURE_NAMES),
                               "count": 107, "order_sha256": ft.EXPECTED_W_ORDER_SHA256,
                               "asset_path": "w_asset.csv", "asset_sha256": w_asset_hash,
                               "reused_existing_asset": True, "reextracted": False},
            },
            "frozen_a_full_boundary": {"definition": "accepted frozen full_A habitat",
                "lock_identity_sha256": "a" * 64,
                "identity_sha256": ft.ft04._frozen_a_boundary_identity(lock),
                "K": 2, "n_init": 100, "no_refit": True,
                "source_hashes": {key: "source-%s" % key for key in (
                    "ft01_asset_manifest", "habitat_freeze_lock", "w03_candidate_freeze")}},
            "pyradiomics_provenance": lock["provenance"]["pyradiomics"],
            "pyradiomics_matches_A_W03": True,
            "generation": {"outcome_blind": True,
                "one_time_first_extraction": True,
                "projection": "direct_frozen_A_full_boundary",
                "w_original_reused": True,
                "b_kmeans_fit": False, "outcome_accessed": False,
                "repeat_extraction": False, "duplicate_extraction": False,
                "checkpoint_resume_repeated_extraction": False,
                "whole_tumor_reextraction": False,
                "formal_directory_mixing": False,
                "preprocessing_estimation": False},
            "technical_cohort": {"row_count": 163, "patient_count": 163,
                "patient_ids_unique": True,
                "patient_id_hash": ft._sha256_text("\n".join(identifiers)),
                "source_frame_sha256": cohort_hash,
                "ordered_rows": [{"patient_id": identifier, "split": "B"}
                                 for identifier in identifiers]},
            "reviews": {"technical_audit": {"sha256": audit_hash}},
        }
        # The manifest hash is bound after serialization, so this fixture uses
        # a replacement expected hash to keep the contract fully synthetic.
        self._write_json(manifest_path, manifest)
        manifest_hash = _sha256_file(manifest_path)
        self._patch("EXPECTED_MANIFEST_SHA256", manifest_hash)
        with open(paths["FT05A_AMENDMENT_PATH"], "a", encoding="utf-8") as handle:
            handle.write("%s\n" % manifest_hash)
        unlock = {
            "schema_version": "1.0", "artifact_id": "FT_B_unlock",
            "status": "authorized", "unlock": True, "outcome_access": True,
            "ft_label": ft.FT_LABEL, "ft_stage": "FT05B",
            "scope": "FT06 prediction/evaluation only",
            "ft04_lock_identity_sha256": "a" * 64,
            "ft05a_run_id": ft.EXPECTED_FT05A_RUN_ID,
            "ft05a_run_identity_sha256": "b" * 64,
            "ft05a_cohort_sha256": cohort_hash,
            "feature_manifest_path": "manifest.finalize.json",
            "feature_manifest_sha256": manifest_hash,
            "ft05_manifest_sha256": manifest_hash,
            "feature_table_path": "table.finalize.csv",
            "feature_table_sha256": table_hash,
            "completion_evidence_sha256": "d" * 64,
            "row_schema_sha256": ft.EXPECTED_ROW_SCHEMA_SHA256,
            "candidate_hashes": {"R_low": ft.EXPECTED_R_LOW_CANDIDATE_SHA256,
                                 "R_high": ft.EXPECTED_R_HIGH_CANDIDATE_SHA256},
            "W_Original": {"count": 107, "asset_sha256": w_asset_hash,
                           "order_sha256": ft.EXPECTED_W_ORDER_SHA256,
                           "reused_existing_asset": True, "reextracted": False},
            "technical_audit_sha256": audit_hash,
            "B_data_read_before_unlock": False,
            "B_outcome_read_before_unlock": False,
            "prohibitions": list(ft.PROHIBITED_OPERATIONS),
            "source_commit": "0" * 40,
        }
        self._write_json(paths["FT_B_UNLOCK_PATH"], unlock)
        self._patch_object(ft.ft04, "validate_ft_model_freeze_lock",
                           mock.Mock(return_value=lock))

    def _read_unlock(self):
        with open(ft.FT_B_UNLOCK_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_unlock(self, unlock):
        self._write_json(ft.FT_B_UNLOCK_PATH, unlock)

    def test_valid_gate_authorizes_without_formal_lock_or_formal_reader(self):
        with mock.patch.object(ft.data_split_guard, "require_b_unlock",
                               side_effect=AssertionError("formal reader called")):
            result = ft.validate_ft05b_gate()
        self.assertFalse(os.path.exists(ft.FORMAL_MODEL_LOCK))
        self.assertEqual(result["status"], "AUTHORIZED")
        self.assertEqual(result["technical_case_count"], 163)
        self.assertFalse(result["b_data_read_before_unlock"])
        self.assertFalse(result["patient_level_frame_persisted"])

    def test_missing_unlock_fails_before_outcome_source_read(self):
        os.remove(ft.FT_B_UNLOCK_PATH)
        with mock.patch.object(ft.data_split_guard, "_authorized_read") as reader:
            with self.assertRaises(ft.FT05BValidationError):
                ft.read_b_dfs()
        reader.assert_not_called()

    def test_wrong_hash_old_path_and_disabled_status_fail_closed(self):
        cases = []
        bad_hash = self._read_unlock()
        bad_hash["feature_table_sha256"] = "0" * 64
        cases.append(bad_hash)
        old_path = self._read_unlock()
        old_path["feature_manifest_path"] = "prognosis_analysis/ft/FT05_B_feature_manifest.json"
        cases.append(old_path)
        disabled = self._read_unlock()
        disabled["outcome_access"] = False
        cases.append(disabled)
        for unlock in cases:
            with self.subTest(unlock=unlock):
                self._write_unlock(unlock)
                with mock.patch.object(ft.data_split_guard, "_authorized_read") as reader:
                    with self.assertRaises(ft.FT05BValidationError):
                        ft.read_b_dfs()
                reader.assert_not_called()
        self.assertFalse(os.path.exists(ft.FT05B_RECEIPT_PATH))

    def test_wrong_feature_column_order_fails_closed_before_outcome_read(self):
        with open(ft.FT05A_TABLE_PATH, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        lines[0] = lines[0].replace("patient_id,split", "split,patient_id", 1)
        with open(ft.FT05A_TABLE_PATH, "w", encoding="utf-8", newline="") as handle:
            handle.writelines(lines)
        with mock.patch.object(ft.data_split_guard, "_authorized_read") as reader:
            with self.assertRaises(ft.FT05BValidationError):
                ft.read_b_dfs()
        reader.assert_not_called()

    def test_formal_lock_presence_fails_closed(self):
        with open(ft.FORMAL_MODEL_LOCK, "w", encoding="utf-8") as handle:
            handle.write("{}");
        with self.assertRaises(ft.FT05BValidationError):
            ft.validate_ft05b_gate()

    def test_reader_uses_only_three_columns_and_returns_aggregate(self):
        identifiers = ["B%03d" % index for index in range(163)]
        frame = pd.DataFrame({"影像号": identifiers,
                              "DFS_time": [float(index + 12)
                                            for index in range(163)],
                              "DFS_event": [1 if index < 42 else 0
                                             for index in range(163)]})
        with mock.patch.object(ft.data_split_guard, "_authorized_read",
                               return_value=frame) as reader:
            result = ft.read_b_dfs()
        self.assertEqual(list(result["requested_columns"]), list(ft.B_OUTCOME_COLUMNS))
        self.assertEqual(result["aggregate"], {
            "row_count": 163, "unique_identifier_count": 163,
            "event_count": 42, "censor_count": 121})
        self.assertTrue(result["access_after_unlock"])
        self.assertFalse(result["patient_level_frame_persisted"])
        self.assertNotIn("frame", result)
        self.assertEqual(reader.call_args[0][3], "影像号")
        self.assertEqual(reader.call_args[1]["usecols"], list(ft.B_OUTCOME_COLUMNS))
        with open(ft.FT05B_RECEIPT_PATH, "r", encoding="utf-8") as handle:
            receipt = json.load(handle)
        self.assertEqual(receipt["requested_columns"], list(ft.B_OUTCOME_COLUMNS))
        self.assertFalse(receipt["patient_level_frame_persisted"])
        self.assertEqual(receipt["aggregate"]["event_count"], 42)

    def test_reader_refuses_second_access_after_receipt(self):
        with mock.patch.object(ft.data_split_guard, "_authorized_read",
                               return_value=pd.DataFrame({
                                   "影像号": ["B%03d" % index
                                              for index in range(163)],
                                   "DFS_time": [float(index + 12)
                                                 for index in range(163)],
                                   "DFS_event": [1 if index < 42 else 0
                                                  for index in range(163)]})):
            ft.read_b_dfs()
        with mock.patch.object(ft.data_split_guard, "_authorized_read") as reader:
            with self.assertRaises(ft.FT05BValidationError):
                ft.read_b_dfs()
        reader.assert_not_called()

    def test_source_has_no_formal_reader_call_and_declares_prohibitions(self):
        path = os.path.join(os.path.dirname(ft.__file__), "ft05b_runner.py")
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("require_b_unlock(", source)
        self.assertNotIn("read_B_validation(", source)
        for operation in ft.PROHIBITED_OPERATIONS:
            self.assertIn(operation, source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
