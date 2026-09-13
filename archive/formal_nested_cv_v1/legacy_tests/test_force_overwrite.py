import os
import sys
import unittest

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from workflow_utils import merge_rows  # noqa: E402


class ForceOverwriteTests(unittest.TestCase):
    def test_replacing_a_key_removes_all_old_duplicates(self):
        base = pd.DataFrame([
            {"影像号": "A", "读者": "R1", "value": "old-1"},
            {"影像号": "A", "读者": "R1", "value": "old-2"},
            {"影像号": "B", "读者": "R1", "value": "keep"},
        ])
        new = pd.DataFrame([
            {"影像号": "A", "读者": "R1", "value": "new"},
        ])
        merged = merge_rows(base, new, ["影像号", "读者"])
        self.assertEqual(
            int(((merged["影像号"] == "A") & (merged["读者"] == "R1")).sum()),
            1)
        self.assertEqual(merged.loc[merged["影像号"] == "A", "value"].iloc[0],
                         "new")
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
