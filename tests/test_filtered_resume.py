import os
import sys
import unittest

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from extract_features_filters import completion_keys  # noqa: E402


class FilteredResumeTests(unittest.TestCase):
    def test_only_fully_complete_rows_are_skippable(self):
        frame = pd.DataFrame([
            {"影像号": "A", "读者": "R1", "wavelet_ok": "1",
             "log_ok": "1", "diagnostics_ok": "1", "range_ok": "1",
             "status": "COMPLETE"},
            {"影像号": "B", "读者": "R1", "wavelet_ok": "1",
             "log_ok": "0", "diagnostics_ok": "1", "range_ok": "1",
             "status": "COMPLETE"},
            {"影像号": "C", "读者": "R1", "wavelet_ok": "1",
             "log_ok": "1", "diagnostics_ok": "1", "range_ok": "1",
             "status": "FAILED"},
        ])
        self.assertEqual(completion_keys(frame), {("A", "R1")})


if __name__ == "__main__":
    unittest.main()
