import inspect
import os
import sys
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import preprocess_core  # noqa: E402


class NoFallbackTests(unittest.TestCase):
    def test_failed_muscle_reference_does_not_become_zscore(self):
        self.assertEqual(
            preprocess_core.muscle_failure({"total": 0, "eroded": 0}, "R1"),
            "R1_MUSCLE_LABEL_MISSING")
        row = preprocess_core.metric_row(
            "muscle", "failed", failure_code="R1_MUSCLE_LABEL_MISSING")
        self.assertEqual(row["normalization_applied"], "")
        self.assertEqual(row["normalization_status"], "failed")
        self.assertNotIn("zscore", str(row).lower())

    def test_preprocess_source_has_no_fallback_branch(self):
        source = inspect.getsource(preprocess_core)
        self.assertNotIn("zscore_fallback", source)
        self.assertNotIn("muscle -> zscore", source.lower())


if __name__ == "__main__":
    unittest.main()
