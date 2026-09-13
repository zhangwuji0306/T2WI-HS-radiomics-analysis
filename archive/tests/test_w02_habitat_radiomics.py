import os
import sys
import unittest

import numpy as np

SCRIPT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                          "prognosis_analysis", "scripts"))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from w02_habitat_radiomics import (  # noqa: E402
    BLOCKS, FEATURE_CLASSES, block_result, classify_habitat_state,
    extractor_settings, load_config, make_block_frame,
)


class W02RadiomicsTests(unittest.TestCase):
    def test_structural_states_are_explicit(self):
        self.assertEqual(classify_habitat_state(4, 6), "dual-habitat")
        self.assertEqual(classify_habitat_state(4, 0), "single-H-low")
        self.assertEqual(classify_habitat_state(0, 6), "single-H-high")
        self.assertEqual(classify_habitat_state(0, 0), "no-habitat")

    def test_structural_absence_is_not_technical_failure(self):
        result = block_result("single-H-low", False)
        self.assertEqual(result["status"], "structurally_undefined")
        self.assertEqual(result["failure_class"], "structural_absence")
        self.assertEqual(result["extractable"], 0)
        self.assertEqual(result["features"], {})

    def test_extraction_failure_is_distinct(self):
        result = block_result("dual-habitat", True, error="ValueError: synthetic")
        self.assertEqual(result["status"], "technical_failure")
        self.assertEqual(result["failure_class"], "technical_failure")
        self.assertEqual(result["failure_reason"], "ValueError: synthetic")

    def test_structural_undefined_features_are_not_zero_filled(self):
        rows = [{
            "影像号": "synthetic", "reader": "R1",
            "structural_state": "single-H-low",
            "H_low_present": 1, "H_high_present": 0,
            "blocks": {
                "R_low": block_result("single-H-low", True, {"original_glcm_Contrast": 2.0}),
                "R_high": block_result("single-H-low", False),
            },
        }]
        frame = make_block_frame(rows, "R_high", ["original_glcm_Contrast"])
        self.assertEqual(frame.loc[0, "status"], "structurally_undefined")
        self.assertEqual(frame.loc[0, "failure_class"], "structural_absence")
        self.assertTrue(np.isnan(frame.loc[0, "R_high__original_glcm_Contrast"]))

    def test_single_shared_parameter_set_and_symmetric_blocks(self):
        config = load_config()
        settings = extractor_settings(config)
        self.assertEqual(settings["imageType"], {"Original": {}})
        self.assertEqual(settings["setting"]["binWidth"], 0.248808)
        self.assertFalse(settings["setting"]["normalize"])
        self.assertIsNone(settings["setting"]["resampledPixelSpacing"])
        self.assertEqual(set(settings["featureClass"]), set(FEATURE_CLASSES))
        self.assertEqual([name for name, _label in BLOCKS], ["R_low", "R_high"])


if __name__ == "__main__":
    unittest.main()
