import os
import sys
import tempfile
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from freeze_lock import (  # noqa: E402
    FREEZE_SCHEMA_VERSION, atomic_write_json, compute_artifact_hashes,
    validate_artifact_hashes, validate_freeze_lock, write_habitat_map_manifest,
)


def _write(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _artifact_paths(tmp):
    os.makedirs(os.path.join(tmp, "maps"))
    _write(os.path.join(tmp, "a393.csv"), "影像号\nA001\n")
    _write(os.path.join(tmp, "a137.csv"), "影像号\nA001\n")
    for name in ("manifest.csv", "scanner_map.csv", "preprocessing.yaml",
                 "slic.json", "formal_summary.csv", "global.csv", "feature_qc.csv",
                 "feature_dictionary.md", "threshold.md", "confounding.md",
                 "screen_lenient.csv", "screen_strict.csv"):
        _write(os.path.join(tmp, name), name + "\n")
    _write(os.path.join(tmp, "maps", "A001_R1_habitat.nrrd"), "synthetic-map\n")
    map_manifest = os.path.join(tmp, "habitat_map_manifest.csv")
    write_habitat_map_manifest(os.path.join(tmp, "maps"), map_manifest)
    return {
        "A393_id_hash": {"kind": "id_hash", "path": "a393.csv", "column": "影像号"},
        "A137_id_hash": {"kind": "id_hash", "path": "a137.csv", "column": "影像号"},
        "manifest_hash": "manifest.csv",
        "scanner_map_hash": "scanner_map.csv",
        "preprocessing_config_hash": "preprocessing.yaml",
        "slic_config_hash": "slic.json",
        "high_signal_screen_hash": ["screen_lenient.csv", "screen_strict.csv"],
        "formal_bootstrap_summary_hash": "formal_summary.csv",
        "global_descriptors_hash": "global.csv",
        "feature_qc_hash": "feature_qc.csv",
        "feature_dictionary_hash": "feature_dictionary.md",
        "threshold_audit_hash": "threshold.md",
        "threshold_confounding_audit_hash": "confounding.md",
        "habitat_map_manifest_hash": {
            "kind": "habitat_map_manifest", "path": "habitat_map_manifest.csv",
            "map_root": "maps",
        },
    }


def valid_payload(tmp):
    artifacts = _artifact_paths(tmp)
    payload = {
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "habitat_technical_freeze": True,
        "A_outcome_unlock": True,
        "B_unlock": False,
        "bootstrap_mode": "formal",
        "bootstrap_requested": 1000,
        "bootstrap_completed": 1000,
        "bootstrap_completion_status": "complete",
        "bootstrap_operational_pass": 1,
        "formal_eligible": 1,
        "outcome_columns_read": False,
        "B_data_read": False,
        "eligibility_threshold_fraction": 0.001,
        "eligibility_threshold_role": "minimum_imaging_presence",
        "threshold_selection_performed": False,
        "threshold_audit_conclusion": "NEUTRAL_WITH_TECHNICAL_CAUTION",
        "config_hash": "abc",
        "artifact_paths": artifacts,
    }
    payload.update(compute_artifact_hashes(artifacts, tmp))
    return payload


class FreezeLockTests(unittest.TestCase):
    def write_lock(self, tmp, payload):
        path = os.path.join(tmp, "freeze_lock.json")
        atomic_write_json(path, payload)
        return path

    def test_valid_strict_schema_and_artifact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = valid_payload(tmp)
            path = self.write_lock(tmp, payload)
            validated = validate_freeze_lock(path)
            self.assertTrue(validated["A_outcome_unlock"])
            self.assertFalse(validated["B_unlock"])

    def test_missing_required_field_hard_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = valid_payload(tmp)
            del payload["threshold_audit_conclusion"]
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(self.write_lock(tmp, payload))

    def test_wrong_required_values_hard_fail(self):
        wrong_values = {
            "freeze_schema_version": "0.9",
            "habitat_technical_freeze": False,
            "A_outcome_unlock": False,
            "B_unlock": True,
            "bootstrap_mode": "smoke",
            "bootstrap_requested": 20,
            "bootstrap_completed": 999,
            "bootstrap_completion_status": "partial",
            "bootstrap_operational_pass": 0,
            "formal_eligible": 0,
            "outcome_columns_read": True,
            "B_data_read": True,
            "eligibility_threshold_fraction": 0.01,
            "eligibility_threshold_role": "selection_cutoff",
            "threshold_selection_performed": True,
            "threshold_audit_conclusion": "OUTCOME_INFORMED",
        }
        for key, value in wrong_values.items():
            with self.subTest(key=key):
                with tempfile.TemporaryDirectory() as tmp:
                    payload = valid_payload(tmp)
                    payload[key] = value
                    with self.assertRaises(RuntimeError):
                        validate_freeze_lock(self.write_lock(tmp, payload))

    def test_current_inputs_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write_lock(tmp, valid_payload(tmp))
            self.assertEqual(validate_freeze_lock(path, {"config_hash": "abc"})["config_hash"], "abc")
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(path, {"config_hash": "changed"})

    def test_artifact_hash_interface_validates_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = valid_payload(tmp)
            self.assertIs(validate_artifact_hashes(payload, payload["artifact_paths"], tmp), payload)

    def test_tampered_freeze_artifacts_hard_fail(self):
        tamper_cases = {
            "A393_identity_artifact": lambda tmp: _write(
                os.path.join(tmp, "a393.csv"), "影像号\nA002\n"),
            "A137_identity_artifact": lambda tmp: _write(
                os.path.join(tmp, "a137.csv"), "影像号\nA002\n"),
            "manifest": lambda tmp: _write(os.path.join(tmp, "manifest.csv"), "changed\n"),
            "scanner_map": lambda tmp: _write(
                os.path.join(tmp, "scanner_map.csv"), "changed\n"),
            "preprocessing_config": lambda tmp: _write(
                os.path.join(tmp, "preprocessing.yaml"), "changed\n"),
            "slic_config": lambda tmp: _write(
                os.path.join(tmp, "slic.json"), "changed\n"),
            "high_signal_screen_list_member": lambda tmp: _write(
                os.path.join(tmp, "screen_strict.csv"), "changed\n"),
            "formal_bootstrap_summary": lambda tmp: _write(
                os.path.join(tmp, "formal_summary.csv"), "changed\n"),
            "global_descriptors": lambda tmp: _write(os.path.join(tmp, "global.csv"), "changed\n"),
            "feature_qc": lambda tmp: _write(os.path.join(tmp, "feature_qc.csv"), "changed\n"),
            "feature_dictionary": lambda tmp: _write(os.path.join(tmp, "feature_dictionary.md"), "changed\n"),
            "threshold_audit": lambda tmp: _write(os.path.join(tmp, "threshold.md"), "changed\n"),
            "threshold_confounding_audit": lambda tmp: _write(
                os.path.join(tmp, "confounding.md"), "changed\n"),
            "map_manifest": lambda tmp: _write(os.path.join(tmp, "habitat_map_manifest.csv"), "changed\n"),
            "map_content_modified": lambda tmp: _write(
                os.path.join(tmp, "maps", "A001_R1_habitat.nrrd"), "changed\n"),
            "map_content_deleted": lambda tmp: os.remove(
                os.path.join(tmp, "maps", "A001_R1_habitat.nrrd")),
            "map_content_added": lambda tmp: _write(
                os.path.join(tmp, "maps", "A002_R1_habitat.nrrd"), "new map\n"),
        }
        for name, tamper in tamper_cases.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                payload = valid_payload(tmp)
                path = self.write_lock(tmp, payload)
                tamper(tmp)
                with self.assertRaises(RuntimeError):
                    validate_freeze_lock(path)
                with self.assertRaises(RuntimeError):
                    validate_artifact_hashes(payload, payload["artifact_paths"], tmp)


if __name__ == "__main__":
    unittest.main()
