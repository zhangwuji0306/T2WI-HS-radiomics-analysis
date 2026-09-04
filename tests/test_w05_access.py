import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd
from openpyxl import Workbook


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
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "synthetic-outcome.csv")
            pd.DataFrame({"影像号": ["A"], "DFS_event": [0]}).to_csv(
                path, index=False, encoding="utf-8-sig")
            with mock.patch.object(data_split_guard, "validate_freeze_lock",
                                   return_value={"A_outcome_unlock": True}):
                result = data_split_guard.read_A_outcomes(
                    path, allowed_ids=["A"])
        self.assertEqual(result["影像号"].tolist(), ["A"])

    def test_arbitrary_custom_reader_is_rejected_before_b_row_materialization(self):
        calls = {"reader": 0, "b_rows": 0}

        def malicious_reader(*args, **kwargs):
            del args, kwargs
            calls["reader"] += 1
            calls["b_rows"] += 1
            return pd.DataFrame({"影像号": ["A", "B"], "value": [1, 99]})

        with mock.patch.object(data_split_guard, "validate_freeze_lock",
                               return_value={}), \
                mock.patch.object(data_split_guard, "validate_model_freeze_lock",
                                  return_value=_model_lock()):
            reader_calls = (
                lambda: data_split_guard.read_technical_A(
                    "synthetic.csv", reader=malicious_reader, allowed_ids=["A"]),
                lambda: data_split_guard.read_A_outcomes(
                    "synthetic.csv", reader=malicious_reader, allowed_ids=["A"]),
                lambda: data_split_guard.read_B_validation(
                    "synthetic.csv", reader=malicious_reader, allowed_ids=["B"]),
            )
            for attempt in reader_calls:
                with self.subTest(attempt=attempt):
                    with self.assertRaises(RuntimeError):
                        attempt()

        self.assertEqual(calls, {"reader": 0, "b_rows": 0})

    def test_compatibility_aliases_reject_arbitrary_reader_before_execution(self):
        calls = []

        def arbitrary_reader(*args, **kwargs):
            del args, kwargs
            calls.append("reader")
            return pd.DataFrame({"影像号": ["A", "B"]})

        with mock.patch.object(data_split_guard, "validate_freeze_lock",
                               return_value={}), \
                mock.patch.object(data_split_guard, "validate_model_freeze_lock",
                                  return_value=_model_lock()):
            attempts = (
                lambda: data_split_guard.read_technical_data(
                    "synthetic.csv", arbitrary_reader, allowed_ids=["A"]),
                lambda: data_split_guard.read_a_outcome(
                    "synthetic.csv", arbitrary_reader, allowed_ids=["A"]),
                lambda: data_split_guard.read_b_data(
                    "synthetic.csv", arbitrary_reader, allowed_ids=["B"]),
                lambda: data_split_guard.read_b_csv(
                    "synthetic.csv", reader=arbitrary_reader, allowed_ids=["B"]),
                lambda: data_split_guard.read_b_excel(
                    "synthetic.xlsx", reader=arbitrary_reader, allowed_ids=["B"]),
            )
            for attempt in attempts:
                with self.subTest(attempt=attempt):
                    with self.assertRaises(RuntimeError):
                        attempt()

        self.assertEqual(calls, [])

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
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = os.path.join(tmp, "model_freeze_lock.json")
            with open(lock_path, "w", encoding="utf-8") as handle:
                json.dump(_model_lock(), handle)
            source_path = os.path.join(tmp, "synthetic-b.csv")
            pd.DataFrame({"影像号": ["A", "B"], "DFS_event": [0, 1]}).to_csv(
                source_path, index=False, encoding="utf-8-sig")
            with mock.patch.object(data_split_guard, "FREEZE_LOCK",
                                   os.path.join(tmp, "technical.json")), \
                    mock.patch.object(data_split_guard, "MODEL_FREEZE_LOCK", lock_path), \
                    mock.patch.object(data_split_guard, "validate_freeze_lock",
                                       return_value={}):
                result = data_split_guard.read_B_validation(
                    source_path, allowed_ids=["B"])
        self.assertEqual(result["影像号"].tolist(), ["B"])

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

    def test_mixed_xlsx_skips_non_a_sensitive_cells_before_allowlist_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "synthetic.xlsx")
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["影像号", "DFS_time", "DFS_event", "OS", "B_forbidden"])
            # Put B first so a full-row reader would encounter the sentinel
            # before it can return the later A row.
            sheet.append(["B1", 30.0, 1, 40.0, "B_SENSITIVE_SENTINEL"])
            sheet.append(["A1", 10.0, 0, 20.0, "A_payload"])
            workbook.save(path)

            parsed_coordinates = []
            original_parse_cell = data_split_guard.WorkSheetParser.parse_cell

            def guarded_parse_cell(parser, element):
                coordinate = element.get("r")
                parsed_coordinates.append(coordinate)
                if coordinate == "E2":
                    raise AssertionError("non-A sensitive field was parsed")
                return original_parse_cell(parser, element)

            with mock.patch.object(data_split_guard, "validate_freeze_lock",
                                   return_value={"A_outcome_unlock": True}), \
                    mock.patch.object(data_split_guard.WorkSheetParser,
                                      "parse_cell", new=guarded_parse_cell):
                result = data_split_guard.read_A_outcomes(
                    path,
                    allowed_ids=["A1"],
                    usecols=["影像号", "DFS_time", "DFS_event"],
                )

        self.assertEqual(result["影像号"].tolist(), ["A1"])
        self.assertEqual(list(result.columns), ["影像号", "DFS_time", "DFS_event"])
        self.assertNotIn("E2", parsed_coordinates)
        self.assertEqual(
            {coordinate for coordinate in parsed_coordinates
             if coordinate and coordinate.endswith("2")},
            {"A2"},
        )

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


class Stage6QCTests(unittest.TestCase):
    @staticmethod
    def _synthetic_feature_table():
        rows = []
        target_values = {
            ("A1", "R1"): 1.0,
            ("A1", "R2"): 1.01,
            ("A2", "R1"): 2.0,
            ("A2", "R2"): 2.01,
            ("A3", "R1"): 3.0,
            ("A3", "R2"): 3.01,
            ("A4", "R1"): float("nan"),
            ("A4", "R2"): 7.0,
            ("A5", "R1"): 100.0,
            ("A5", "R2"): -100.0,
            ("B1", "R1"): 50.0,
        }
        subject_values = {"A1": 1.0, "A2": 2.0, "A3": 3.0,
                          "A4": 4.0, "A5": 5.0, "B1": 6.0}
        for patient_id, reader in target_values:
            row = {"影像号": patient_id, "读者": reader,
                   "split": "B" if patient_id == "B1" else "A",
                   "normalization": "muscle", "f": 0.25,
                   "binWidth": 0.2}
            for index in range(107):
                name = "feature_%03d" % index
                row[name] = (target_values[(patient_id, reader)] if index == 0
                             else float(index) + subject_values[patient_id] +
                             (0.01 if reader == "R2" else 0.0))
            rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _synthetic_membership():
        ids = ["A1", "A2", "A3", "A4", "A5", "B1"]
        manifest = pd.DataFrame({"影像号": ids})
        scanner = pd.DataFrame({
            "影像号": ids,
            "R1厂商": ["GE MEDICAL SYSTEMS"] * 5 + ["Other"],
            "R1机型": ["DISCOVERY MR750"] * 5 + ["Other"],
            "R1场强": ["3.0"] * 5 + ["1.5"],
        })
        return manifest, scanner

    def test_a_qc_reads_full_a_but_icc_and_missingness_have_separate_scopes(self):
        manifest, scanner = self._synthetic_membership()
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = os.path.join(tmp, "manifest.csv")
            scanner_path = os.path.join(tmp, "scanner.csv")
            feature_dir = os.path.join(tmp, "features", "synthetic")
            os.makedirs(feature_dir)
            manifest.to_csv(manifest_path, index=False)
            scanner.to_csv(scanner_path, index=False)
            self._synthetic_feature_table().to_csv(
                os.path.join(feature_dir, "features_original.csv"),
                index=False, encoding="utf-8-sig")
            with mock.patch.object(stage6_qc, "MANIFEST", manifest_path), \
                    mock.patch.object(stage6_qc, "SCANNER", scanner_path), \
                    mock.patch.object(stage6_qc, "FEATURES", os.path.join(tmp, "features")), \
                    mock.patch.object(stage6_qc, "read_technical_A",
                                      wraps=data_split_guard.read_technical_A) as reader:
                result = stage6_qc.process_table(
                    "synthetic", "original", ["A1", "A2", "A3"])

        self.assertEqual(reader.call_args[1]["allowed_ids"],
                         {"A1", "A2", "A3", "A4", "A5"})
        target = result["icc"].set_index("feature").loc["feature_000"]
        self.assertGreater(float(target["icc_A"]), stage6_qc.ICC_THRESHOLD)
        self.assertEqual(int(target["n_A"]), 3)
        self.assertTrue(bool(target["pass_icc"]))
        self.assertEqual(int(target["n_missing_A_R1"]), 1)
        self.assertFalse(bool(target["candidate"]))
        self.assertEqual(result["n_missing"], 1)
        self.assertEqual(result["n_candidates"], 106)
        self.assertNotIn("icc_B", result["icc"].columns)
        self.assertNotIn("n_B", result["icc"].columns)

    def test_b_qc_hard_fails_before_any_physical_read(self):
        table_reader = mock.Mock(side_effect=AssertionError("B QC table opened"))
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(stage6_qc, "FEATURES", tmp), \
                mock.patch.object(stage6_qc, "require_b_unlock",
                                   side_effect=RuntimeError("model freeze required")), \
                mock.patch.object(stage6_qc, "read_B_validation", table_reader):
            with self.assertRaises(RuntimeError):
                stage6_qc.process_table("synthetic", "original", [], split="B")
        table_reader.assert_not_called()


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
