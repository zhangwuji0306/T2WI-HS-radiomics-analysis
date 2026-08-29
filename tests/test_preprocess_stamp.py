import os
import sys
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from preprocess_core import DEFAULTS, pipeline_stamp, preprocessing_config_sha256  # noqa: E402


class PreprocessStampTests(unittest.TestCase):
    def test_effective_preprocessing_parameters_change_stamp(self):
        cfg = dict(DEFAULTS)
        base_stamp = pipeline_stamp(cfg)
        base_config_hash = preprocessing_config_sha256(cfg)
        changed_n4 = dict(cfg, n4_downsample_factor=3.0)
        changed_minimum = dict(cfg, min_tumor_voxels=99)
        self.assertNotEqual(base_stamp, pipeline_stamp(changed_n4))
        self.assertNotEqual(base_stamp, pipeline_stamp(changed_minimum))
        self.assertNotEqual(base_config_hash,
                            preprocessing_config_sha256(changed_n4))


if __name__ == "__main__":
    unittest.main()
