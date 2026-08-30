import json
import os
import sys
import tempfile
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from sigma_guard import promote_complete_sigma  # noqa: E402


class SigmaCompleteTests(unittest.TestCase):
    def paths(self, root):
        return os.path.join(root, "sigma.json"), os.path.join(root, "archive.json")

    def assert_rejected_without_overwrite(self, payload):
        with tempfile.TemporaryDirectory() as tmp:
            primary, archive = self.paths(tmp)
            with open(primary, "w", encoding="utf-8") as handle:
                handle.write("sentinel")
            with self.assertRaises(RuntimeError):
                promote_complete_sigma(payload, primary, archive)
            with open(primary, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "sentinel")
            self.assertFalse(os.path.exists(archive))

    def test_missing_case_not_written(self):
        self.assert_rejected_without_overwrite({"n_cases_expected": 10, "n_cases_used": 9,
                                                "n_cases_failed": 0, "complete_case_pass": False})

    def test_empty_roi_not_written(self):
        self.assert_rejected_without_overwrite({"n_cases_expected": 10, "n_cases_used": 9,
                                                "n_cases_failed": 1, "complete_case_pass": False})

    def test_filter_failure_not_written(self):
        self.assert_rejected_without_overwrite({"n_cases_expected": 10, "n_cases_used": 10,
                                                "n_cases_failed": 1, "complete_case_pass": False})

    def test_complete_atomic_promotion(self):
        payload = {"n_cases_expected": 10, "n_cases_used": 10,
                   "n_cases_failed": 0, "complete_case_pass": True}
        with tempfile.TemporaryDirectory() as tmp:
            primary, archive = self.paths(tmp)
            promote_complete_sigma(payload, primary, archive)
            with open(primary, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), payload)
            with open(archive, encoding="utf-8") as handle:
                self.assertEqual(json.load(handle), payload)


if __name__ == "__main__":
    unittest.main()
