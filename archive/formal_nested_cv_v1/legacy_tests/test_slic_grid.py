import json
import os
import sys
import unittest

import SimpleITK as sitk


SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          "habitat_analysis", "scripts")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import technical_dry_run_A as dry_run  # noqa: E402


class SlicGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(dry_run.CONFIG, encoding="utf-8") as handle:
            cls.cfg = json.load(handle)

    def test_same_spacing_different_fov_has_same_supergrid(self):
        image_a = sitk.Image([80, 80, 40], sitk.sitkFloat32)
        image_b = sitk.Image([120, 90, 30], sitk.sitkFloat32)
        for image in (image_a, image_b):
            image.SetSpacing([1.0, 1.0, 2.0])

        meta_a = dry_run.slic_grid_metadata(image_a, self.cfg)
        meta_b = dry_run.slic_grid_metadata(image_b, self.cfg)

        self.assertEqual(meta_a["supergrid_voxels_xyz"], (4, 4, 2))
        self.assertEqual(meta_b["supergrid_voxels_xyz"], (4, 4, 2))
        self.assertEqual(meta_a["supergrid_voxels_xyz"],
                         meta_b["supergrid_voxels_xyz"])

    def test_four_mm_target_records_actual_physical_grid(self):
        image = sitk.Image([80, 80, 40], sitk.sitkFloat32)
        image.SetSpacing([1.0, 1.0, 2.0])

        meta = dry_run.slic_grid_metadata(image, self.cfg)

        self.assertEqual(meta["requested_scale_mm"], 4.0)
        self.assertEqual(meta["supergrid_voxels_xyz"], (4, 4, 2))
        self.assertEqual(meta["actual_supergrid_mm_xyz"], (4.0, 4.0, 4.0))


if __name__ == "__main__":
    unittest.main()
