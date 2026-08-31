import json
import os
import sys
import tempfile
import unittest
from unittest import mock


FEATURE_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                "feature_extract", "scripts"))
PROGNOSIS_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                  "prognosis_analysis", "scripts"))
for path in (FEATURE_SCRIPTS, PROGNOSIS_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import data_split_guard  # noqa: E402
import stage6_qc  # noqa: E402
import build_model_dataset  # noqa: E402
from model_freeze_lock import validate_model_freeze_lock  # noqa: E402


def _synthetic_model_lock():
    digest = "a" * 64
    return {
        "model_freeze_schema_version": "1.0",
        "A_modeling_population_hash": digest,
        "A393_id_hash": digest,
        "A137_id_hash": digest,
        "freeze_lock_hash": digest,
        "preprocessing_config_hash": digest,
        "slic_config_hash": digest,
        "global_center_low": 2.1,
        "global_center_high": 3.5,
        "global_boundary": 2.8,
        "modeling_protocol_hash": digest,
        "outer_split_hash": digest,
        "outcome_definition_hash": digest,
        "candidate_pool_hashes": {"R_low": digest, "R_high": digest},
        "final_model_id": "synthetic-model",
        "final_model_family": "elastic-net-cox",
        "final_model_feature_list_hash": digest,
        "final_model_coefficients_hash": digest,
        "preprocessing_parameter_hash": digest,
        "baseline_survival_hash": digest,
        "final_model_artifact_hash": digest,
        "A_model_development_complete": True,
        "A_model_frozen": True,
        "B_data_read": False,
        "B_validation_unlocked": True,
    }


class W00BAccessBoundaryTests(unittest.TestCase):
    def test_model_freeze_lock_requires_strict_w13_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "model_freeze_lock.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(_synthetic_model_lock(), handle)
            self.assertEqual(validate_model_freeze_lock(path)["A_model_frozen"], True)

            invalid = _synthetic_model_lock()
            invalid["B_data_read"] = True
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(invalid, handle)
            with self.assertRaises(RuntimeError):
                validate_model_freeze_lock(path)

    def test_every_b_reader_fails_before_physical_read_without_model_lock(self):
        calls = []

        def physical_reader(*args, **kwargs):
            del args, kwargs
            calls.append(True)
            raise AssertionError("B physical reader must not be called")

        reader_cases = {
            "clinical": lambda path: data_split_guard.read_b_excel(path, reader=physical_reader),
            "outcome": lambda path: data_split_guard.read_b_excel(path, reader=physical_reader),
            "radiomics": lambda path: data_split_guard.read_b_csv(path, reader=physical_reader),
            "habitat": lambda path: data_split_guard.read_b_csv(path, reader=physical_reader),
            "qc": lambda path: data_split_guard.read_b_csv(path, reader=physical_reader),
        }
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "technical.json")), \
                mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", os.path.join(tmp, "missing.json")), \
                mock.patch.object(data_split_guard, "validate_freeze_lock", return_value={}):
            for kind, attempt in reader_cases.items():
                with self.subTest(kind=kind):
                    with self.assertRaises(RuntimeError):
                        attempt(os.path.join(tmp, kind + ".synthetic"))
        self.assertEqual(calls, [])

    def test_invalid_model_lock_also_fails_before_physical_read(self):
        reader = mock.Mock(side_effect=AssertionError("invalid-lock B reader must not be called"))
        with tempfile.TemporaryDirectory() as tmp:
            model_path = os.path.join(tmp, "invalid-model-freeze-lock.json")
            with open(model_path, "w", encoding="utf-8") as handle:
                json.dump({"B_validation_unlocked": True}, handle)
            with mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", model_path), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock", return_value={}):
                with self.assertRaises(RuntimeError):
                    data_split_guard.read_b_data("synthetic-b-file", reader)
        reader.assert_not_called()

    def test_legacy_b_unlock_file_cannot_authorize_b(self):
        with tempfile.TemporaryDirectory() as tmp:
            legacy = os.path.join(tmp, "b_validation_unlock.json")
            with open(legacy, "w", encoding="utf-8") as handle:
                json.dump({"A_model_frozen": True, "B_validation_unlocked": True}, handle)
            with mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", os.path.join(tmp, "missing_model.json")), \
                    mock.patch.object(data_split_guard, "B_UNLOCK_LOCK", legacy), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock", return_value={}):
                with self.assertRaises(RuntimeError):
                    data_split_guard.read_b_data("does-not-exist", lambda path: path)

    def test_b_qc_entry_checks_lock_before_table_open(self):
        table_reader = mock.Mock(side_effect=AssertionError("B QC table must not be opened"))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(stage6_qc, "FEATURES", tmp), \
                mock.patch.object(stage6_qc, "require_b_unlock",
                                   side_effect=RuntimeError("model freeze required")), \
                mock.patch.object(stage6_qc.pd, "read_csv", table_reader):
            with self.assertRaises(RuntimeError):
                stage6_qc.process_table("synthetic", "original", [], split="B")
        table_reader.assert_not_called()

    def test_legacy_model_builder_fails_before_feature_or_clinical_read(self):
        feature_reader = mock.Mock(side_effect=AssertionError("B feature table must not be opened"))
        clinical_reader = mock.Mock(side_effect=AssertionError("B clinical workbook must not be opened"))
        with mock.patch.object(build_model_dataset, "require_b_unlock",
                               side_effect=RuntimeError("model freeze required")), \
                mock.patch.object(build_model_dataset, "load_features", feature_reader), \
                mock.patch.object(build_model_dataset.pd, "read_excel", clinical_reader), \
                mock.patch.object(sys, "argv", ["build_model_dataset.py"]):
            with self.assertRaises(RuntimeError):
                build_model_dataset.main()
        feature_reader.assert_not_called()
        clinical_reader.assert_not_called()

    def test_valid_second_lock_allows_reader_only_after_both_lock_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_path = os.path.join(tmp, "model_freeze_lock.json")
            with open(model_path, "w", encoding="utf-8") as handle:
                json.dump(_synthetic_model_lock(), handle)
            reader = mock.Mock(return_value="synthetic B payload")
            with mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", model_path), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock", return_value={}):
                result = data_split_guard.read_b_data("synthetic-b-file", reader)
            self.assertEqual(result, "synthetic B payload")
            reader.assert_called_once_with("synthetic-b-file")

    def test_a_outcome_fails_before_read_while_technical_reader_remains_available(self):
        outcome_reader = mock.Mock(side_effect=AssertionError("outcome reader must not be called"))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "missing.json")):
            with self.assertRaises(RuntimeError):
                data_split_guard.read_a_outcome("synthetic-outcome.xlsx", outcome_reader)
            technical_reader = mock.Mock(return_value="synthetic technical payload")
            result = data_split_guard.read_technical_data("synthetic-manifest.csv", technical_reader)
        self.assertEqual(result, "synthetic technical payload")
        outcome_reader.assert_not_called()
        technical_reader.assert_called_once_with("synthetic-manifest.csv")

    def test_invalid_first_lock_fails_before_a_outcome_read(self):
        outcome_reader = mock.Mock(side_effect=AssertionError("invalid-lock outcome reader must not be called"))
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = os.path.join(tmp, "invalid-freeze-lock.json")
            with open(lock_path, "w", encoding="utf-8") as handle:
                handle.write("{not-json")
            with mock.patch.object(data_split_guard, "FREEZE_LOCK", lock_path):
                with self.assertRaises(RuntimeError):
                    data_split_guard.read_a_outcome("synthetic-outcome.xlsx", outcome_reader)
        outcome_reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
