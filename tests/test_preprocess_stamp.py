import os
import sys
import json
import tempfile
import time
import unittest
from unittest import mock


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "feature_extract", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import preprocess_core  # noqa: E402
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

    def make_current_case(self, root, cfg):
        outdir = os.path.join(root, "out")
        os.makedirs(outdir)
        for name in ("R1_image.nrrd", "R1_mask.nrrd"):
            open(os.path.join(outdir, name), "wb").close()
        source = os.path.join(root, "input.nrrd")
        with open(source, "wb") as handle:
            handle.write(b"abc")
        stat = os.stat(source)
        stamp = preprocess_core.pipeline_stamp(cfg)
        with open(os.path.join(outdir, ".pipeline_stamp"), "w", encoding="ascii") as handle:
            handle.write(stamp)
        metadata = {
            "pipeline_stamp": stamp,
            "pipeline_code_sha256": preprocess_core.pipeline_code_sha256(),
            "inputs": {"R1_image": {"path": source, "size_bytes": stat.st_size,
                                      "mtime_ns": stat.st_mtime_ns}},
            "readers": {"R1": {"status": "success"}},
        }
        with open(os.path.join(outdir, "pipeline_metadata.json"), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle)
        return outdir, source

    def test_input_mtime_change_marks_stale(self):
        cfg = dict(DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            outdir, source = self.make_current_case(tmp, cfg)
            self.assertTrue(preprocess_core.case_is_current(outdir, cfg, False))
            stat = os.stat(source)
            os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            self.assertFalse(preprocess_core.case_is_current(outdir, cfg, False))

    def test_input_size_change_marks_stale(self):
        cfg = dict(DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            outdir, source = self.make_current_case(tmp, cfg)
            with open(source, "ab") as handle:
                handle.write(b"x")
            self.assertFalse(preprocess_core.case_is_current(outdir, cfg, False))

    def test_config_change_marks_stale(self):
        cfg = dict(DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self.make_current_case(tmp, cfg)
            self.assertFalse(preprocess_core.case_is_current(
                outdir, dict(cfg, crop_padding=cfg["crop_padding"] + 1), False))

    def test_pipeline_version_change_marks_stale(self):
        cfg = dict(DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self.make_current_case(tmp, cfg)
            with mock.patch.object(preprocess_core, "PIPELINE_VERSION", "changed"):
                self.assertFalse(preprocess_core.case_is_current(outdir, cfg, False))

    def test_unchanged_case_is_current(self):
        cfg = dict(DEFAULTS)
        with tempfile.TemporaryDirectory() as tmp:
            outdir, _ = self.make_current_case(tmp, cfg)
            self.assertTrue(preprocess_core.case_is_current(outdir, cfg, False))


if __name__ == "__main__":
    unittest.main()
