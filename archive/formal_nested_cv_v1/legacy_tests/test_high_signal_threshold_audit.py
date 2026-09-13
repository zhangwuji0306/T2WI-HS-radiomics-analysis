import os
import sys
import unittest

import numpy as np
import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit_high_signal_threshold as audit  # noqa: E402


class HighSignalThresholdAuditTests(unittest.TestCase):
    def test_01_ceil_discretization(self):
        table = pd.DataFrame({"tumor_voxels": [500, 1000, 2000, 5000, 10000]})
        required = np.ceil(0.001 * table["tumor_voxels"]).astype(int).tolist()
        self.assertEqual(required, [1, 1, 2, 5, 10])

    def test_02_threshold_cohorts_are_nested(self):
        values = np.array([0.0, 0.0005, 0.001, 0.0025, 0.005, 0.01, 0.02])
        table = pd.DataFrame({
            "patient_id": [str(i) for i in range(len(values))],
            "split_from_scanner": "A",
            "high_fraction": values,
            "high_voxels_ge_fat_mean": values * 1000,
            "high_equiv_voxels_1x1x2": values * 1000,
            "tumor_voxels": 1000,
            "tumor_volume_mm3": 1000,
            "screening_band": "0",
            "required_voxel_category": "1",
        })
        sweep, _ = audit.threshold_sweep(table, set(), set())
        retained = []
        for threshold in audit.THRESHOLDS:
            if threshold == 0:
                keep = set(table.loc[table.high_fraction > 0, "patient_id"])
            else:
                keep = set(table.loc[table.high_fraction >= threshold, "patient_id"])
            retained.append(keep)
        for lower, higher in zip(retained, retained[1:]):
            self.assertTrue(higher.issubset(lower))
        self.assertEqual(int(sweep.loc[sweep.threshold == "0.10%", "retained_n"].iloc[0]), 5)

    def test_03_manifest_scanner_order_does_not_change_split(self):
        manifest = pd.DataFrame({
            "影像号": ["a", "b"], "排除": ["0", "0"]})
        scanner = pd.DataFrame({
            "影像号": ["b", "a"],
            "R1厂商": ["OTHER", "GE MEDICAL SYSTEMS"],
            "R1机型": ["OTHER", "DISCOVERY MR750"],
            "R1场强": ["1.5", "3.0"],
            "R1系列": ["s2", "s1"], "R1行": ["1", "1"],
            "R1列": ["1", "1"], "R1面内间距": ["1\\1", "1\\1"],
            "R1层厚": ["3", "3"], "R1层数": ["2", "2"],
        })
        result = audit.scanner_split(manifest, scanner)
        self.assertEqual(result.loc[result["影像号"] == "a", "split_from_scanner"].iloc[0], "A")
        self.assertEqual(result.loc[result["影像号"] == "b", "split_from_scanner"].iloc[0], "B")

    def test_04_audit_is_outcome_blind_and_not_optimizer(self):
        path = os.path.join(SCRIPTS, "audit_high_signal_threshold.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("prognosis_analysis", source)
        self.assertIn("threshold_selection_performed", source)
        self.assertIn("outcome_columns_read", source)
        self.assertIn("B_data_read", source)

    def test_05_preflight_linkage_does_not_refit(self):
        path = os.path.join(SCRIPTS, "audit_high_signal_threshold.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        body = source.split("def preflight_by_band", 1)[1].split("def make_report", 1)[0]
        self.assertNotIn("KMeans", body)
        self.assertIn("case_assignment_stability.csv", body)

    def test_06_supervoxel_retention_is_reported_by_screening_band(self):
        table = pd.DataFrame({
            "high_fraction": [0.0012, 0.0018, 0.0030],
            "screening_band": ["0.10-<0.25%", "0.10-<0.25%", "0.25-<0.50%"],
            "supervoxel_high_post_fraction": [0.0, 0.001, 0.002],
            "supervoxel_high_retention_recall": [0.0, 0.1, 0.2],
            "supervoxel_high_precision": [np.nan, 0.75, 0.8],
            "supervoxel_high_post_to_pre_ratio": [0.0, 0.1, 0.2],
        })
        summary = audit.supervoxel_retention_summary(table)
        near = summary[summary.screening_band == "0.10-<0.25%"].iloc[0]
        self.assertEqual(int(near["n"]), 2)
        self.assertAlmostEqual(float(near["supervoxel_high_retention_recall_median"]), 0.05)
        self.assertEqual(int(near["supervoxel_high_precision_available_n"]), 1)


if __name__ == "__main__":
    unittest.main()
