import os
import sys
import unittest

import numpy as np
import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import audit_threshold_confounding as audit  # noqa: E402


class ThresholdConfoundingTests(unittest.TestCase):
    def test_empirical_logit_handles_zero_and_nonzero_fraction(self):
        transformed = audit.empirical_logit([0.0, 0.001, 0.5])
        self.assertTrue(np.isfinite(transformed).all())
        self.assertLess(float(transformed[0]), float(transformed[1]))
        self.assertLess(float(transformed[1]), float(transformed[2]))

    def test_sequence_size_strata_preserve_case_counts(self):
        sequences = pd.DataFrame({
            "sequence_name": ["s1", "s2", "s3"],
            "n": [20, 10, 2],
            "main_pass_rate": [0.8, 1.0, 0.0],
            "adjusted_pass_probability_at_medians": [0.75, 0.9, 0.5],
        })
        strata = audit.sequence_size_strata(sequences)
        n20 = strata[strata.minimum_sequence_n == 20].iloc[0]
        n10 = strata[strata.minimum_sequence_n == 10].iloc[0]
        self.assertEqual(int(n20.sequence_levels), 1)
        self.assertEqual(int(n20.cases_covered), 20)
        self.assertEqual(int(n10.sequence_levels), 2)
        self.assertEqual(int(n10.cases_covered), 30)

    def test_decomposition_is_outcome_blind(self):
        path = os.path.join(SCRIPTS, "audit_threshold_confounding.py")
        with open(path, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("prognosis_analysis", source)
        self.assertIn("outcome_columns_read", source)
        self.assertIn("B_data_read", source)
        self.assertIn("sequence_name", source)


if __name__ == "__main__":
    unittest.main()
