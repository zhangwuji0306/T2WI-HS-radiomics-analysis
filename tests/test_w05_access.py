import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd


FEATURE_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                "feature_extract", "scripts"))
PROGNOSIS_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                  "prognosis_analysis", "scripts"))
for path in (FEATURE_SCRIPTS, PROGNOSIS_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import build_model_dataset_a as builder  # noqa: E402
import data_split_guard  # noqa: E402
import stage6_qc  # noqa: E402


def _model_lock():
    digest = "b" * 64
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


class W05ReaderTests(unittest.TestCase):
    def test_a_outcome_missing_first_lock_fails_before_reader(self):
        reader = mock.Mock(side_effect=AssertionError("A outcome source opened"))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(data_split_guard, "FREEZE_LOCK",
                                   os.path.join(tmp, "missing-freeze.json")):
            with self.assertRaises(RuntimeError):
                data_split_guard.read_A_outcomes(
                    "synthetic-outcome.xlsx", reader=reader, allowed_ids=["A"])
        reader.assert_not_called()

    def test_valid_first_lock_allows_synthetic_a_outcome(self):
        reader = mock.Mock(return_value=pd.DataFrame({
            "影像号": ["A"], "DFS_event": [0]}))
        with mock.patch.object(data_split_guard, "validate_freeze_lock",
                               return_value={"A_outcome_unlock": True}):
            result = data_split_guard.read_A_outcomes(
                "synthetic-outcome.xlsx", reader=reader, allowed_ids=["A"])
        self.assertEqual(result["影像号"].tolist(), ["A"])
        reader.assert_called_once_with("synthetic-outcome.xlsx")

    def test_missing_model_lock_blocks_every_b_reader_before_physical_read(self):
        for kind in ("clinical", "outcome", "radiomics", "habitat", "qc"):
            reader = mock.Mock(side_effect=AssertionError("B source opened"))
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp, \
                    mock.patch.object(data_split_guard, "FREEZE_LOCK",
                                       os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK",
                                       os.path.join(tmp, "missing-model.json")), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock",
                                       return_value={}):
                with self.assertRaises(RuntimeError):
                    data_split_guard.read_B_validation(
                        "synthetic-b.csv", reader=reader, allowed_ids=["B"])
            reader.assert_not_called()

    def test_valid_model_lock_allows_synthetic_b_validation(self):
        reader = mock.Mock(return_value=pd.DataFrame({
            "影像号": ["B"], "DFS_event": [1]}))
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = os.path.join(tmp, "model_freeze_lock.json")
            with open(lock_path, "w", encoding="utf-8") as handle:
                json.dump(_model_lock(), handle)
            with mock.patch.object(data_split_guard, "FREEZE_LOCK",
                                   os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", lock_path), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock",
                                       return_value={}):
                result = data_split_guard.read_B_validation(
                    "synthetic-b.csv", reader=reader, allowed_ids=["B"])
        self.assertEqual(result["影像号"].tolist(), ["B"])
        reader.assert_called_once_with("synthetic-b.csv")

    def test_mixed_raw_feature_file_is_filtered_by_reader_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            qc = os.path.join(tmp, "qc", "synthetic")
            features = os.path.join(tmp, "features", "synthetic")
            os.makedirs(qc)
            os.makedirs(features)
            candidate = pd.DataFrame({"batch": ["original", "wavelet", "log"],
                                      "feature": ["f_original", "f_wavelet", "f_log"]})
            candidate.to_csv(os.path.join(qc, "candidate_features.csv"), index=False)
            for batch, filename, feature in (
                    ("original", "features_original.csv", "f_original"),
                    ("wavelet", "features_wavelet.csv", "f_wavelet"),
                    ("log", "features_log.csv", "f_log")):
                pd.DataFrame({
                    "影像号": ["A", "B"], "读者": ["R1", "R1"],
                    "split": ["A", "B"], feature: [1.0, 99.0],
                }).to_csv(os.path.join(features, filename), index=False,
                          encoding="utf-8-sig")
            with mock.patch.object(builder, "STAGE6", os.path.join(tmp, "qc")), \
                    mock.patch.object(builder, "FEATURES", os.path.join(tmp, "features")):
                result, _ = builder.load_features("synthetic", {"A"})
            self.assertEqual(result["影像号"].tolist(), ["A"])
            self.assertNotIn("B", result["影像号"].tolist())
            self.assertEqual(float(result.loc[0, "f_original"]), 1.0)

    def test_split_membership_is_shared_by_a_builder_and_qc(self):
        manifest = pd.DataFrame({"影像号": ["A", "B"], "排除": ["0", "0"]})
        scanner = pd.DataFrame({
            "影像号": ["A", "B"],
            "R1厂商": ["GE MEDICAL SYSTEMS", "Other"],
            "R1机型": ["DISCOVERY MR750", "Other"],
            "R1场强": ["3.0", "1.5"],
        })
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = os.path.join(tmp, "manifest.csv")
            scanner_path = os.path.join(tmp, "scanner.csv")
            screen_root = os.path.join(tmp, "screen")
            os.makedirs(screen_root)
            manifest.to_csv(manifest_path, index=False)
            scanner.to_csv(scanner_path, index=False)
            pd.DataFrame({"patient_id": ["A"], "lenient_pass": [1]}).to_csv(
                os.path.join(screen_root, "lenient_screening_decisions.csv"), index=False)
            with mock.patch.object(builder, "MANIFEST", manifest_path), \
                    mock.patch.object(builder, "SCANNER", scanner_path), \
                    mock.patch.object(builder, "SCREEN_ROOT", screen_root), \
                    mock.patch.object(stage6_qc, "MANIFEST", manifest_path), \
                    mock.patch.object(stage6_qc, "SCANNER", scanner_path):
                expected = data_split_guard.resolve_cohort_membership(manifest, scanner)
                builder_a = builder.cohort_table("lenient", {"A"})
                qc_ids = stage6_qc.load_cohort_ids()
        self.assertEqual(expected.set_index("影像号").loc["A", "split"], "A")
        self.assertEqual(builder_a["影像号"].tolist(), ["A"])
        self.assertEqual(qc_ids["A"], {"A"})
        self.assertEqual(qc_ids["B"], {"B"})


class W05BuilderTests(unittest.TestCase):
    @staticmethod
    def clinical_frame(ids):
        frame = {"影像号": ids}
        for column in builder.OUTCOMES + builder.PRIMARY_CLINICAL + builder.DESCRIPTIVE + builder.POSTOP:
            frame[column] = [0] * len(ids)
        frame["性别"] = ["男"] * len(ids)
        return pd.DataFrame(frame)

    def test_a_mode_emits_only_a_artifacts_and_a_statistics(self):
        clinical = self.clinical_frame(["A1", "A2"])
        features = pd.DataFrame({"影像号": ["A1", "A2"], "f": [1.0, 2.0]})
        candidates = pd.DataFrame({"batch": ["original"], "feature": ["f"]})
        cohort = pd.DataFrame({"影像号": ["A1", "A2"], "split": ["A", "A"]})
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(builder, "load_a_technical_ids",
                                   return_value={"lenient": {"A1", "A2"},
                                                 "strict": {"A1"}}), \
                mock.patch.object(builder, "read_A_outcomes", return_value=clinical), \
                mock.patch.object(builder, "load_features",
                                   return_value=(features, candidates)), \
                mock.patch.object(builder, "cohort_table", return_value=cohort):
            builder.build_a_datasets("synthetic", ["lenient"], tmp)
            names = {name for name in os.listdir(tmp)}
            with open(os.path.join(tmp, "report_A.md"), encoding="utf-8") as handle:
                report = handle.read()
        self.assertTrue(names)
        self.assertFalse(any(name.endswith("_B.csv") for name in names))
        self.assertFalse(any("B" in name for name in names))
        self.assertIn("A 样本量：2", report)
        self.assertNotIn("B", report)

    def test_b_and_all_modes_hard_fail_before_any_source_read(self):
        for split in ("B", "all"):
            with self.subTest(split=split), \
                    mock.patch.object(builder, "require_b_unlock",
                                       side_effect=RuntimeError("model freeze required")) as gate, \
                    mock.patch.object(builder, "load_a_technical_ids",
                                       side_effect=AssertionError("technical source opened")):
                with mock.patch.object(sys, "argv",
                                       ["build_model_dataset_a.py", "--split", split]):
                    with self.assertRaises(RuntimeError):
                        builder.main()
            gate.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
