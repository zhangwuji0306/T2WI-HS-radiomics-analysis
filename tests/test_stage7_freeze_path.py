import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

import numpy as np
import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)


class _SyntheticImage:
    def GetSpacing(self):
        return (1.0, 1.0, 1.0)

    def CopyInformation(self, other):
        return None


def _synthetic_sitk():
    module = types.ModuleType("SimpleITK")
    module.GetImageFromArray = lambda array: _SyntheticImage()

    def write_image(image, path, useCompression=True):
        del image, useCompression
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"synthetic nrrd payload")

    module.WriteImage = write_image
    return module


def _load_workflow():
    try:
        return importlib.import_module("revised_workflow_technical")
    except ModuleNotFoundError as error:
        if error.name != "SimpleITK":
            raise
        sys.modules["SimpleITK"] = _synthetic_sitk()
        sys.modules.pop("technical_dry_run_A", None)
        sys.modules.pop("revised_workflow_technical", None)
        return importlib.import_module("revised_workflow_technical")


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


class Stage7FreezePathTests(unittest.TestCase):
    def test_stage7_freeze_uses_imported_validator_with_synthetic_inputs(self):
        workflow = _load_workflow()
        synthetic_sitk = _synthetic_sitk()
        with tempfile.TemporaryDirectory() as tmp:
            root = tmp
            hab = os.path.join(root, "habitat_analysis")
            out = os.path.join(hab, "output")
            feature_root = os.path.join(root, "feature_extract")
            paths = {
                "ROOT": root,
                "HAB": hab,
                "OUT": out,
                "BASELINE": os.path.join(out, "baseline"),
                "STRUCT": os.path.join(out, "struct"),
                "LOCAL": os.path.join(out, "local"),
                "ROBUST": os.path.join(out, "robust"),
                "SENS": os.path.join(out, "sensitivity"),
                "BOOT_ROOT": os.path.join(out, "bootstrap"),
                "MAPS": os.path.join(out, "habitat_maps_A"),
                "FEATURES": os.path.join(out, "habitat_features_A"),
                "MAPS_STAGING": os.path.join(out, "habitat_maps_A_staging"),
                "FEATURES_STAGING": os.path.join(out, "habitat_features_A_staging"),
                "FREEZE_PREFLIGHT": os.path.join(out, "freeze_preflight_A"),
                "FEATURE_DICTIONARY": os.path.join(hab, "feature_dictionary.md"),
                "FEATURE_DICTIONARY_STAGING": os.path.join(hab, "feature_dictionary_staging.md"),
                "FREEZE_LOCK": os.path.join(hab, "freeze_lock.json"),
                "FREEZE_LOCK_STAGING": os.path.join(hab, "freeze_lock_staging.json"),
                "MAP_MANIFEST": os.path.join(out, "habitat_maps_A_manifest.csv"),
                "MAP_MANIFEST_STAGING": os.path.join(out, "habitat_maps_A_manifest_staging.csv"),
                "CONFIG": os.path.join(hab, "configs", "slic.json"),
            }
            ids = ["A%03d" % index for index in range(393)]
            cases = pd.DataFrame({"影像号": ids})
            sv = pd.DataFrame({"影像号": ids, "sv_label": [1] * len(ids),
                               "Mean": [0.8] * len(ids)})
            diag = pd.DataFrame({
                "影像号": ids, "algorithm_failure": [0] * len(ids),
                "unassigned_tumor_voxels": [0] * len(ids),
                "geometry_or_label_error": [0] * len(ids),
                "pass1_status": ["ok"] * len(ids), "pass2_status": ["ok"] * len(ids),
                "H_low_center": [0.4] * len(ids), "H_high_center": [0.8] * len(ids),
                "shared_boundary_b": [0.6] * len(ids), "H_low_voxels": [0] * len(ids),
                "H_high_voxels": [1] * len(ids), "tumor_voxels_current_grid": [1] * len(ids),
            })

            os.makedirs(paths["BASELINE"], exist_ok=True)
            pd.DataFrame([{"H_low": 0.4, "H_high": 0.8, "boundary_b": 0.6}]).to_csv(
                os.path.join(paths["BASELINE"], "global_centers.csv"), index=False)
            for directory, filename, column in (
                (paths["STRUCT"], "baseline_integrity.csv", "baseline_pass"),
                (paths["LOCAL"], "center_reproducibility.csv", "center_reproducibility_pass"),
                (paths["ROBUST"], "technical_robustness_summary.csv", "technical_robustness_pass"),
            ):
                os.makedirs(directory, exist_ok=True)
                pd.DataFrame([{column: 1}]).to_csv(os.path.join(directory, filename), index=False)
            os.makedirs(paths["SENS"], exist_ok=True)
            pd.DataFrame([{"strict_A137_exact_unique_pass": 1,
                           "strict_A137_subset_A393_pass": 1}]).to_csv(
                os.path.join(paths["SENS"], "strict_A137_assertions.csv"), index=False)

            technical_dir = os.path.join(out, "technical_cohort_manifest")
            os.makedirs(technical_dir, exist_ok=True)
            for name in ("cohort_A_lenient.csv", "cohort_A_strict.csv"):
                pd.DataFrame({"影像号": ids}).to_csv(os.path.join(technical_dir, name),
                                                       index=False, encoding="utf-8-sig")
            _write(os.path.join(technical_dir, "cohort_summary.json"),
                   json.dumps({"identity_audit_pass": 1, "A137_subset_A393": 1}))

            threshold_dir = os.path.join(out, "high_signal_threshold_audit")
            _write(os.path.join(threshold_dir, "outcome_blind_threshold_audit.md"), "synthetic threshold audit\n")
            _write(os.path.join(threshold_dir, "technical_confounding_decomposition.md"), "synthetic confounding audit\n")
            _write(os.path.join(out, "high_signal_eligibility_audit", "lenient_screening_decisions.csv"), "x\n")
            _write(os.path.join(out, "high_signal_eligibility_audit", "recommended_screening_decisions.csv"), "x\n")

            formal_dir = os.path.join(paths["BOOT_ROOT"], "formal")
            os.makedirs(formal_dir, exist_ok=True)
            pd.DataFrame([{
                "n_bootstrap_requested": 1000, "n_bootstrap_completed": 1000,
                "n_bootstrap_success": 1000, "bootstrap_mode": "formal",
                "completion_status": "complete", "bootstrap_operational_pass": 1,
                "formal_eligible": 1,
            }]).to_csv(os.path.join(formal_dir, "bootstrap_stability_summary.csv"), index=False)

            manifest_path = os.path.join(feature_root, "output", "manifest.csv")
            scanner_path = os.path.join(feature_root, "output", "scanner_map.csv")
            preprocess_path = os.path.join(feature_root, "configs", "radiomics_params.yaml")
            _write(manifest_path, "synthetic manifest\n")
            _write(scanner_path, "synthetic scanner map\n")
            _write(preprocess_path, "synthetic preprocessing config\n")
            _write(paths["CONFIG"], json.dumps({"synthetic": True}))

            cfg = {"analysis_id": "synthetic-stage7",
                   "slic": {"supergrid_voxels_xyz": [4, 4, 2],
                             "actual_supergrid_mm_xyz": [4.0, 4.0, 4.0]}}
            image = _SyntheticImage()
            roi = np.ones((1, 1, 1), dtype=bool)
            labels = np.ones((1, 1, 1), dtype=np.int32)

            with mock.patch.multiple(workflow, **paths), \
                    mock.patch.object(workflow, "load_cfg", return_value=cfg), \
                    mock.patch.object(workflow, "load_sv", return_value=sv), \
                    mock.patch.object(workflow, "load_diag", return_value=diag), \
                    mock.patch.object(workflow.base, "load_cases", return_value=cases), \
                    mock.patch.object(workflow, "read_case_with_labels",
                                      return_value=(image, None, roi, labels)), \
                    mock.patch.object(workflow.base, "apath", side_effect=lambda path: path), \
                    mock.patch.object(workflow, "sitk", synthetic_sitk), \
                    mock.patch.object(workflow.subprocess, "check_output",
                                      return_value="synthetic-commit\n"):
                self.assertTrue(workflow.stage7_freeze())

            from freeze_lock import validate_freeze_lock  # noqa: E402
            payload = validate_freeze_lock(paths["FREEZE_LOCK"])
            self.assertTrue(payload["habitat_technical_freeze"])
            self.assertTrue(payload["A_outcome_unlock"])
            self.assertFalse(payload["B_unlock"])
            self.assertEqual(payload["bootstrap_completed"], 1000)
            self.assertEqual(payload["artifact_paths"]["habitat_map_manifest_hash"]["map_root"],
                             "output/habitat_maps_A")
            self.assertEqual(len(pd.read_csv(paths["MAP_MANIFEST"])), 393)
            self.assertEqual(len(os.listdir(paths["MAPS"])), 393)


if __name__ == "__main__":
    unittest.main()
