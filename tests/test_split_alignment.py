import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import build_model_dataset as model_data  # noqa: E402


class SplitAlignmentTests(unittest.TestCase):
    def write_inputs(self, root, scanner):
        manifest_path = os.path.join(root, "manifest.csv")
        scanner_path = os.path.join(root, "scanner.csv")
        screen_root = os.path.join(root, "screen")
        os.makedirs(screen_root)
        pd.DataFrame({"影像号": ["1", "2", "3"], "排除": ["0", "0", "0"]}).to_csv(
            manifest_path, index=False, encoding="utf-8-sig")
        scanner.to_csv(scanner_path, index=False, encoding="utf-8-sig")
        pd.DataFrame({"patient_id": ["1", "2", "3"], "lenient_pass": [1, 1, 1]}).to_csv(
            os.path.join(screen_root, "lenient_screening_decisions.csv"), index=False,
            encoding="utf-8-sig")
        return manifest_path, scanner_path, screen_root

    def scanner(self):
        return pd.DataFrame({
            "影像号": ["1", "2", "3"],
            "R1厂商": ["GE MEDICAL SYSTEMS", "Other", "GE MEDICAL SYSTEMS"],
            "R1机型": ["DISCOVERY MR750", "X", "DISCOVERY MR750"],
            "R1场强": ["3.0", "1.5", "3.0"],
        })

    def test_01_order_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, scanner, screen = self.write_inputs(
                tmp, self.scanner().sample(frac=1, random_state=7))
            with mock.patch.object(model_data, "MANIFEST", manifest), \
                    mock.patch.object(model_data, "SCANNER", scanner), \
                    mock.patch.object(model_data, "SCREEN_ROOT", screen):
                result = model_data.cohort_table("lenient").set_index("影像号")["split"].to_dict()
            self.assertEqual(result, {"1": "A", "2": "B", "3": "A"})

    def test_02_duplicate_scanner_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            duplicate = pd.concat([self.scanner(), self.scanner().iloc[[0]]], ignore_index=True)
            manifest, scanner, screen = self.write_inputs(tmp, duplicate)
            with mock.patch.object(model_data, "MANIFEST", manifest), \
                    mock.patch.object(model_data, "SCANNER", scanner), \
                    mock.patch.object(model_data, "SCREEN_ROOT", screen):
                with self.assertRaises(AssertionError):
                    model_data.cohort_table("lenient")

    def test_03_missing_scanner_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest, scanner, screen = self.write_inputs(tmp, self.scanner().iloc[:2])
            with mock.patch.object(model_data, "MANIFEST", manifest), \
                    mock.patch.object(model_data, "SCANNER", scanner), \
                    mock.patch.object(model_data, "SCREEN_ROOT", screen):
                with self.assertRaises(AssertionError):
                    model_data.cohort_table("lenient")


if __name__ == "__main__":
    unittest.main()
