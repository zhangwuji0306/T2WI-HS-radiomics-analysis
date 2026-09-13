import inspect
import os
import sys
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_local_l6_probe as probe  # noqa: E402


class W08LocalL6ProbeTests(unittest.TestCase):
    def test_correctness_matrix_is_complete_and_bounded(self):
        matrix = probe._correctness_matrix()
        required = {
            "kmeans_centers_and_boundaries", "fold_seed",
            "representative_masks", "G_features", "R_low_features",
            "R_high_features", "P3B_support_states",
            "fold_specific_population", "paired_comparators",
            "ModelPreprocessor", "lambda_grid", "alpha_lambda_selection",
            "coefficient_convergence_failure_audit", "serial_parallel_ordering",
            "checkpoint_resume", "B_access_boundary",
        }
        self.assertTrue(required.issubset(set(matrix)))
        self.assertTrue(all(matrix[key].get("pass") for key in required))
        self.assertEqual(
            len(matrix["kmeans_centers_and_boundaries"]["centers_and_boundaries"]),
            50)
        self.assertEqual(matrix["lambda_grid"]["count_per_alpha"], 100)
        self.assertEqual(matrix["ModelPreprocessor"]["synthetic_shape"], [32, 68])

    def test_performance_keeps_raw_three_repeat_records_and_equivalence(self):
        summary = probe._performance_summary()
        self.assertEqual(summary["repeat_count"], 3)
        self.assertEqual(len(summary["raw_repeats"]), 3)
        self.assertTrue(summary["correctness_preserved"])
        self.assertEqual(summary["workload"]["candidate_count_per_fold"], 5)
        self.assertEqual(summary["workload"]["solver_max_iter"], 60)
        self.assertFalse(summary["workload"][
            "formal_100_point_3000_iteration_evidence"])
        self.assertGreaterEqual(
            summary["stages"]["technical_probe_baseline"][
                "pyradiomics_calls"]["median"],
            summary["stages"]["technical_probe_integrated"][
                "pyradiomics_calls"]["median"])
        self.assertGreater(
            summary["stages"]["technical_probe_integrated"][
                "mask_signature_reuse_rate"]["median"], 0.0)

    def test_source_is_outcome_blind_and_does_not_call_formal_writer(self):
        source = inspect.getsource(probe)
        self.assertNotIn("read_A_outcomes", source)
        self.assertNotIn("formal.formal(", source)
        self.assertNotIn("formal.write_results(", source)


if __name__ == "__main__":
    unittest.main()
