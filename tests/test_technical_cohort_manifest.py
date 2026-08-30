import os
import sys
import tempfile
import unittest

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import build_technical_cohort_manifest as technical  # noqa: E402


class TechnicalCohortManifestTests(unittest.TestCase):
    def build(self, root, shuffled=False):
        manifest = pd.DataFrame({"影像号": ["1", "2", "3", "4"],
                                 "排除": ["0", "0", "0", "0"]})
        scanner = pd.DataFrame({
            "影像号": ["1", "2", "3", "4"],
            "R1厂商": ["GE MEDICAL SYSTEMS", "GE MEDICAL SYSTEMS", "Other", "GE MEDICAL SYSTEMS"],
            "R1机型": ["DISCOVERY MR750", "DISCOVERY MR750", "X", "DISCOVERY MR750"],
            "R1场强": ["3.0", "3.0", "1.5", "3.0"],
        })
        if shuffled:
            scanner = scanner.sample(frac=1, random_state=5)
        paths = [os.path.join(root, name) for name in
                 ("manifest.csv", "scanner.csv", "lenient.csv", "strict.csv")]
        manifest.to_csv(paths[0], index=False, encoding="utf-8-sig")
        scanner.to_csv(paths[1], index=False, encoding="utf-8-sig")
        pd.DataFrame({"patient_id": ["1", "2", "3", "4"],
                      "lenient_pass": [1, 1, 1, 1]}).to_csv(paths[2], index=False,
                                                              encoding="utf-8-sig")
        pd.DataFrame({"patient_id": ["1", "2", "3", "4"],
                      "recommended_pass": [1, 0, 0, 1]}).to_csv(paths[3], index=False,
                                                                  encoding="utf-8-sig")
        return technical.build_tables(*paths)

    def test_counts_subset_and_order_independence(self):
        with tempfile.TemporaryDirectory() as left, tempfile.TemporaryDirectory() as right:
            lenient_1, strict_1 = self.build(left, False)
            lenient_2, strict_2 = self.build(right, True)
            self.assertEqual(lenient_1["影像号"].tolist(), ["1", "2", "4"])
            self.assertEqual(strict_1["影像号"].tolist(), ["1", "4"])
            self.assertTrue(set(strict_1["影像号"]).issubset(set(lenient_1["影像号"])))
            pd.testing.assert_frame_equal(lenient_1, lenient_2)
            pd.testing.assert_frame_equal(strict_1, strict_2)

    def test_no_prognosis_dependency(self):
        with open(technical.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("prognosis_analysis", source)


if __name__ == "__main__":
    unittest.main()
