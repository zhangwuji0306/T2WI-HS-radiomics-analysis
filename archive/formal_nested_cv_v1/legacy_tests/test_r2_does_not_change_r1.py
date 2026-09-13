import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd
import SimpleITK as sitk


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import preprocess_core  # noqa: E402


class R2IsolationTests(unittest.TestCase):
    def test_r2_label_failure_keeps_r1_output(self):
        old_prep = preprocess_core.PREP_DIR
        try:
            with tempfile.TemporaryDirectory() as temp:
                preprocess_core.PREP_DIR = os.path.join(temp, "preprocessed")
                shape = (5, 12, 12)
                image_array = np.full(shape, 100.0, dtype=np.float32)
                mask_array = np.zeros(shape, dtype=np.uint8)
                mask_array[1:4, 2:10, 2:10] = 3
                mask_array[2:3, 5:8, 5:8] = 1
                r1_image = sitk.GetImageFromArray(image_array)
                r1_mask = sitk.GetImageFromArray(mask_array)
                r1_image.SetSpacing((1.0, 1.0, 2.0))
                r1_mask.CopyInformation(r1_image)

                r2_image = sitk.GetImageFromArray(image_array)
                r2_mask_array = np.zeros(shape, dtype=np.uint8)
                r2_mask_array[2:3, 5:8, 5:8] = 1
                r2_mask = sitk.GetImageFromArray(r2_mask_array)
                r2_image.SetSpacing((1.0, 1.0, 2.0))
                r2_mask.CopyInformation(r2_image)
                paths = {}
                for name, image in (("r1_image.nrrd", r1_image),
                                    ("r1_mask.nrrd", r1_mask),
                                    ("r2_image.nrrd", r2_image),
                                    ("r2_mask.nrrd", r2_mask)):
                    path = os.path.join(temp, name)
                    sitk.WriteImage(image, path)
                    paths[name] = path

                cfg = dict(preprocess_core.DEFAULTS)
                cfg["normalization"] = "muscle"
                row = pd.Series({
                    "影像号": "case",
                    "图像文件": paths["r1_image.nrrd"],
                    "掩膜文件": paths["r1_mask.nrrd"],
                    "是否双读者": "1",
                    "R2图像文件": paths["r2_image.nrrd"],
                    "R2掩膜文件": paths["r2_mask.nrrd"],
                    "R2肌肉标签状态": "missing",
                    "R2肌肉标签": "",
                })
                qc = {}
                status, _timing1, _timing2, metrics = preprocess_core.process(
                    "case", row, cfg, qc, force=True)
                outdir = os.path.join(preprocess_core.PREP_DIR, "case")
                self.assertEqual(status, "done_r2_failed")
                self.assertTrue(os.path.exists(os.path.join(outdir, "R1_image.nrrd")))
                self.assertTrue(os.path.exists(os.path.join(outdir, "R1_mask.nrrd")))
                self.assertFalse(os.path.exists(os.path.join(outdir, "R2_image.nrrd")))
                self.assertEqual(metrics["R1"]["normalization_status"], "success")
                self.assertEqual(metrics["R2"]["failure_code"],
                                 "R2_MUSCLE_LABEL_MISSING")
        finally:
            preprocess_core.PREP_DIR = old_prep


if __name__ == "__main__":
    unittest.main()
