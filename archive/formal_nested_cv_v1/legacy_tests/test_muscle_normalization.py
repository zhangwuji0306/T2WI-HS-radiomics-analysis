import os
import sys
import unittest

import numpy as np
import SimpleITK as sitk


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from preprocess_core import metric_row, muscle_failure, muscle_stats  # noqa: E402


class MuscleNormalizationTests(unittest.TestCase):
    def test_label3_stats_are_explicit_and_valid(self):
        values = np.full((5, 12, 12), 100.0, dtype=np.float32)
        mask = np.zeros((5, 12, 12), dtype=np.uint8)
        mask[1:4, 2:10, 2:10] = 3
        image = sitk.GetImageFromArray(values)
        stats = muscle_stats(image, mask, 3, [1, 1, 0])
        self.assertEqual(muscle_failure(stats, "R1"), "")
        self.assertAlmostEqual(stats["mean"], 100.0)
        row = metric_row("muscle", "success", "muscle", "3", stats)
        self.assertEqual(row["reference_label"], "3")
        self.assertEqual(row["normalization_applied"], "muscle")
        self.assertEqual(row["normalization_status"], "success")

    def test_missing_or_empty_reference_is_a_failure(self):
        self.assertEqual(
            muscle_failure({"total": 0, "eroded": 0}, "R1"),
            "R1_MUSCLE_LABEL_MISSING")
        self.assertEqual(
            muscle_failure({"total": 20, "eroded": 0}, "R1"),
            "R1_MUSCLE_EROSION_EMPTY")


if __name__ == "__main__":
    unittest.main()
