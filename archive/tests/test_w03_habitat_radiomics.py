import inspect
import os
import sys
import unittest

import numpy as np

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                          "prognosis_analysis", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from w03_habitat_radiomics import (  # noqa: E402
    BLOCKS, candidate_decision, candidate_hash, finite_rate, icc_2_1,
    load_config,
)


class W03RadiomicsTests(unittest.TestCase):
    def test_icc_2_1_is_absolute_agreement_single_measure(self):
        values = np.asarray([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]])
        self.assertAlmostEqual(icc_2_1(values), 1.0)

    def test_icc_requires_two_reader_columns(self):
        with self.assertRaises(ValueError):
            icc_2_1(np.ones((10, 1)))

    def test_strict_icc_and_pair_gates(self):
        config = load_config()
        passed = candidate_decision(.7500001, 10, .95, 1.0, "main", config)
        self.assertEqual(passed[:3], ("pass", 1, 1))
        threshold_fail = candidate_decision(.75, 10, 1.0, 1.0, "main", config)
        self.assertEqual(threshold_fail[0], "icc_threshold_not_met")
        self.assertEqual(threshold_fail[2], 0)
        sample_fail = candidate_decision(.99, 9, 1.0, 1.0, "main", config)
        self.assertEqual(sample_fail[0], "insufficient reproducibility sample")
        self.assertEqual(sample_fail[2], 0)

    def test_finite_rate_threshold_is_inclusive(self):
        self.assertEqual(finite_rate([1.0] * 19 + [np.nan]), .95)
        self.assertLess(finite_rate([1.0] * 18 + [np.nan, np.nan]), .95)

    def test_candidate_hash_is_order_independent(self):
        self.assertEqual(candidate_hash(["b", "a", "a"]), candidate_hash(["a", "b"]))

    def test_low_high_share_one_symmetric_block_definition(self):
        self.assertEqual([name for name, _label in BLOCKS], ["R_low", "R_high"])

    def test_source_has_no_outcome_or_model_reader(self):
        source = inspect.getsource(sys.modules["w03_habitat_radiomics"])
        for forbidden in ("read_excel", "modeling_v2", "validation_B"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
