import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd
from openpyxl import Workbook


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "prognosis_analysis", "scripts")
FEATURE_SCRIPTS = os.path.join(ROOT, "feature_extract", "scripts")
for path in (SCRIPTS, FEATURE_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import data_split_guard  # noqa: E402
import w06_endpoint_qc as w06  # noqa: E402


class W06EndpointTests(unittest.TestCase):
    def test_reverse_km_median_treats_censoring_as_event(self):
        median = w06.reverse_km_median_followup(
            [10.0, 20.0, 30.0, 40.0], [1, 0, 1, 0])
        self.assertEqual(median, 40.0)

    def test_endpoint_masks_keep_categories_separate(self):
        frame = pd.DataFrame({
            "DFS_time": [10, 0, None, "bad", 10],
            "DFS_event": [1, 0, 1, 0, 2],
        })
        _, _, missing, time_le_zero, conflict, valid = w06._event_time_masks(frame)
        self.assertEqual(int(missing.sum()), 1)
        self.assertEqual(int(time_le_zero.sum()), 1)
        self.assertEqual(int(conflict.sum()), 2)
        self.assertEqual(int(valid.sum()), 1)

    def test_w06_reads_only_requested_dfs_columns_after_id_allowlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "synthetic.xlsx")
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["影像号", "DFS_time", "DFS_event", "OS", "B_only_marker"])
            sheet.append(["A1", 10.0, 0, 20.0, "must-not-return"])
            sheet.append(["B1", 30.0, 1, 40.0, "must-not-return"])
            workbook.save(path)
            with mock.patch.object(data_split_guard, "validate_freeze_lock",
                                   return_value={"A_outcome_unlock": True,
                                                 "B_unlock": False}):
                result = data_split_guard.read_A_outcomes(
                    path, allowed_ids=["A1"],
                    usecols=["影像号", "DFS_time", "DFS_event"])
        self.assertEqual(list(result.columns), ["影像号", "DFS_time", "DFS_event"])
        self.assertEqual(result["影像号"].tolist(), ["A1"])
        self.assertNotIn("OS", result.columns)
        self.assertNotIn("B_only_marker", result.columns)

    def test_w06_main_rejects_b_and_all_before_source_access(self):
        for split in ("B", "all"):
            with self.subTest(split=split), \
                    mock.patch.object(sys, "argv",
                                      ["w06_endpoint_qc.py", "--split", split]), \
                    mock.patch.object(w06, "validate_freeze_lock",
                                      side_effect=AssertionError("source accessed")):
                with self.assertRaises(RuntimeError):
                    w06.main()

    def test_w06_hard_fails_if_second_lock_already_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_lock = os.path.join(tmp, "model.json")
            with open(model_lock, "w", encoding="utf-8") as handle:
                handle.write("{}")
            with mock.patch.object(w06, "FREEZE_LOCK", os.path.join(tmp, "freeze.json")), \
                    mock.patch.object(w06, "MODEL_FREEZE_LOCK", model_lock), \
                    mock.patch.object(w06, "validate_freeze_lock",
                                      return_value={"A_outcome_unlock": True,
                                                    "B_unlock": False}), \
                    mock.patch.object(w06, "load_frozen_a_ids",
                                      side_effect=AssertionError("source accessed")):
                with self.assertRaises(RuntimeError):
                    w06.run_w06("synthetic.xlsx", os.path.join(tmp, "output"))

    def test_run_w06_uses_a_only_and_writes_aggregate_outputs(self):
        outcomes = pd.DataFrame({
            "影像号": ["A1", "A2", "A3", "A4"],
            "DFS_time": [40.0, 70.0, 20.0, 80.0],
            "DFS_event": [1, 0, 1, 0],
        })
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(w06, "FREEZE_LOCK", os.path.join(tmp, "freeze.json")), \
                mock.patch.object(w06, "MODEL_FREEZE_LOCK", os.path.join(tmp, "model.json")), \
                mock.patch.object(w06, "validate_freeze_lock",
                                  return_value={"A_outcome_unlock": True,
                                                "B_unlock": False}), \
                mock.patch.object(w06, "load_frozen_a_ids",
                                  return_value={"A393": {"A1", "A2", "A3", "A4"},
                                                "A137": {"A1"}}), \
                mock.patch.object(w06, "read_A_outcomes", return_value=outcomes), \
                mock.patch.object(w06, "EXPECTED_A393", 4), \
                mock.patch.object(w06, "EXPECTED_A137", 1):
            summary = w06.run_w06("synthetic.xlsx", os.path.join(tmp, "output"))
            self.assertEqual(summary["counts"]["A393_total"], 4)
            self.assertEqual(summary["counts"]["DFS_event_count"], 2)
            self.assertEqual(summary["counts"]["censor_count"], 2)
            self.assertEqual(summary["counts"]["A_modeling_population"], 4)
            self.assertTrue(os.path.isfile(os.path.join(tmp, "output", "A_endpoint_qc",
                                                        "outcome_read_audit.json")))
            self.assertTrue(os.path.isfile(os.path.join(tmp, "output", "A_modeling",
                                                        "A_modeling_population.csv")))


if __name__ == "__main__":
    unittest.main()
