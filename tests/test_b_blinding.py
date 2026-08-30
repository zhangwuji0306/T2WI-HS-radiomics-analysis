import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd


PROGNOSIS_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                                 "prognosis_analysis", "scripts"))
FEATURE_SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                               "feature_extract", "scripts"))
for path in (PROGNOSIS_SCRIPTS, FEATURE_SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

import stage6_qc  # noqa: E402
import data_split_guard  # noqa: E402


class BBlindingTests(unittest.TestCase):
    def test_stage6_prefreeze_has_no_b_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            combo = "test"
            folder = os.path.join(tmp, combo)
            os.makedirs(folder)
            rows = []
            for pid in ("1", "2", "3"):
                for reader, offset in (("R1", 0.0), ("R2", 0.01)):
                    row = {"影像号": pid, "读者": reader, "split": "A",
                           "normalization": "muscle", "f": 0.25,
                           "binWidth": 0.2}
                    for index in range(107):
                        row["feature_%03d" % index] = float(pid) + offset + index / 100.0
                    rows.append(row)
            pd.DataFrame(rows).to_csv(os.path.join(folder, "features_original.csv"),
                                      index=False, encoding="utf-8-sig")
            with mock.patch.object(stage6_qc, "FEATURES", tmp):
                result = stage6_qc.process_table(combo, "original", ["1", "2", "3"])
            self.assertNotIn("icc_B", result["icc"].columns)
            self.assertNotIn("n_B", result["icc"].columns)

    def test_a_only_does_not_need_unlock(self):
        frame = pd.DataFrame({"split": ["A", "B"], "x": [1, 2]})
        selected = data_split_guard.select_split(frame, "A")
        self.assertEqual(selected["x"].tolist(), [1])

    def test_b_requires_unlock(self):
        frame = pd.DataFrame({"split": ["A", "B"], "x": [1, 2]})
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(data_split_guard, "FREEZE_LOCK", os.path.join(tmp, "missing.json")), \
                mock.patch.object(data_split_guard, "B_UNLOCK_LOCK", os.path.join(tmp, "missing_b.json")):
            with self.assertRaises(RuntimeError):
                data_split_guard.select_split(frame, "B")


if __name__ == "__main__":
    unittest.main()
