import os
import sys
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from build_manifest import resolve_r2_muscle_label  # noqa: E402


class ManifestLabelTests(unittest.TestCase):
    def test_lower_mean_is_muscle(self):
        self.assertEqual(resolve_r2_muscle_label(20.0, 40.0),
                         ("2", "resolved", ""))
        self.assertEqual(resolve_r2_muscle_label(40.0, 20.0),
                         ("3", "resolved", ""))

    def test_single_or_equal_label_is_not_guessed(self):
        self.assertEqual(resolve_r2_muscle_label(20.0, float("nan")),
                         ("", "unresolved", "R2_MUSCLE_LABEL_UNRESOLVED"))
        self.assertEqual(resolve_r2_muscle_label(20.0, 20.0),
                         ("", "unresolved", "R2_MUSCLE_LABEL_UNRESOLVED"))
        self.assertEqual(resolve_r2_muscle_label(float("nan"), float("nan")),
                         ("", "missing", "R2_MUSCLE_LABEL_MISSING"))


if __name__ == "__main__":
    unittest.main()
