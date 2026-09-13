import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import revised_workflow_technical as workflow  # noqa: E402
from freeze_lock import validate_formal_bootstrap  # noqa: E402


class BootstrapModeTests(unittest.TestCase):
    def test_01_smoke_cannot_unlock_freeze(self):
        summary = {"bootstrap_mode": "smoke", "n_bootstrap_requested": 20,
                   "n_bootstrap_completed": 20, "completion_status": "complete",
                   "bootstrap_operational_pass": 1, "formal_eligible": 0}
        self.assertTrue(validate_formal_bootstrap(summary))

    def test_02_preflight_200_cannot_unlock_freeze(self):
        summary = {"bootstrap_mode": "preflight", "n_bootstrap_requested": 200,
                   "n_bootstrap_completed": 200, "completion_status": "complete",
                   "bootstrap_operational_pass": 1, "formal_eligible": 0}
        self.assertTrue(validate_formal_bootstrap(summary))

    def test_03_formal_requires_1000(self):
        partial = {"bootstrap_mode": "formal", "n_bootstrap_requested": 1000,
                   "n_bootstrap_completed": 999, "completion_status": "partial",
                   "bootstrap_operational_pass": 1, "formal_eligible": 0}
        complete = {"bootstrap_mode": "formal", "n_bootstrap_requested": 1000,
                    "n_bootstrap_completed": 1000, "completion_status": "complete",
                    "bootstrap_operational_pass": 1, "formal_eligible": 1}
        self.assertTrue(validate_formal_bootstrap(partial))
        self.assertEqual(validate_formal_bootstrap(complete), [])

    def test_04_resume_reproducibility(self):
        values = pd.DataFrame({
            "影像号": np.repeat(["1", "2", "3", "4", "5"], 3),
            "Mean": [0.8, 1.0, 1.2, 1.1, 1.3, 1.5, 1.7, 1.9, 2.1,
                     2.0, 2.2, 2.4, 2.5, 2.7, 2.9],
        })
        ids = np.array(["1", "2", "3", "4", "5"])
        cfg = {"random_seed": 12345, "clustering": {
            "k": 2, "initialization": "k-means++", "n_init": 2,
            "max_iter": 100, "tol": 1e-4}}
        one = workflow.bootstrap_center_rows(values, ids, cfg, range(200))
        resumed = (workflow.bootstrap_center_rows(values, ids, cfg, range(100)) +
                   workflow.bootstrap_center_rows(values, ids, cfg, range(100, 200)))
        self.assertEqual([row["seed"] for row in one], [row["seed"] for row in resumed])
        np.testing.assert_allclose([row["boundary_b"] for row in one],
                                   [row["boundary_b"] for row in resumed], rtol=0, atol=0)

    def test_05_output_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(workflow, "BOOT_ROOT", tmp):
                paths = [workflow.bootstrap_directory(mode)
                         for mode in ("smoke", "preflight", "formal")]
                self.assertEqual(len(set(paths)), 3)
                self.assertTrue(paths[0].endswith("smoke"))
                self.assertTrue(paths[1].endswith("preflight"))
                self.assertTrue(paths[2].endswith("formal"))


if __name__ == "__main__":
    unittest.main()
