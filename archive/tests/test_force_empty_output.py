import os
import sys
import tempfile
import unittest

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import extract_features  # noqa: E402
import extract_features_filters  # noqa: E402


class ForceEmptyOutputTests(unittest.TestCase):
    def test_original_empty_output(self):
        result = extract_features._empty_like(pd.DataFrame(), ["影像号", "读者"])
        self.assertEqual(result.columns.tolist(), ["影像号", "读者"])

    def test_filtered_empty_output(self):
        result = extract_features_filters._empty_like(pd.DataFrame(), ["影像号", "读者"])
        self.assertEqual(result.columns.tolist(), ["影像号", "读者"])

    def test_force_new_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "not_created.csv")
            result = extract_features.prepare_run_frame(path, ["影像号", "读者"],
                                                        set(), True, True)
            self.assertTrue(result.empty)


if __name__ == "__main__":
    unittest.main()
