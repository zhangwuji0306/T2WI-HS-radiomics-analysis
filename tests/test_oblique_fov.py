import math
import os
import sys
import unittest

import SimpleITK as sitk


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from workflow_utils import physical_points_inside_image  # noqa: E402


class ObliqueFovTests(unittest.TestCase):
    def test_physical_to_index_check_rejects_axis_bbox_false_positive(self):
        image = sitk.Image(10, 10, 10, sitk.sitkFloat32)
        c, s = math.sqrt(0.5), math.sqrt(0.5)
        image.SetDirection((c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0))
        valid = image.TransformIndexToPhysicalPoint((8, 1, 1))
        self.assertTrue(physical_points_inside_image(image, [valid]))
        # This point lies in the world-axis bounding box of the rotated image,
        # but maps to a negative continuous image index.
        self.assertFalse(physical_points_inside_image(image, [(6.0, 1.0, 1.0)]))


if __name__ == "__main__":
    unittest.main()
