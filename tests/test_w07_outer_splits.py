import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w07_outer_splits as w07  # noqa: E402


def synthetic_config():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                        "prognosis_analysis", "configs",
                                        "w07_outer_splits.json"))
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)
    return config


def synthetic_population(n=393, events=89):
    return pd.DataFrame({
        "影像号": ["S%03d" % i for i in range(n)],
        "technical_cohort": ["A393"] * n,
        "DFS_time": [float(i + 1) for i in range(n)],
        "DFS_event": [1] * events + [0] * (n - events),
        "modeling_eligible": [1] * n,
    })


def write_bound_w06_fixture(tmp):
    config = synthetic_config()
    population_dir = os.path.join(tmp, "A_modeling")
    audit_dir = os.path.join(tmp, "A_endpoint_qc")
    os.makedirs(population_dir)
    os.makedirs(audit_dir)

    population_path = os.path.join(population_dir,
                                    "A_modeling_population.csv")
    schema_path = os.path.join(population_dir,
                               "A_modeling_population_schema.json")
    audit_path = os.path.join(audit_dir, "endpoint_qc_summary.json")
    population = synthetic_population()
    population.to_csv(population_path, index=False)
    source_hash = w07._sha256_file(population_path)
    schema = {
        "file": "A_modeling_population.csv",
        "columns": w07.POPULATION_COLUMNS,
        "n_rows": len(population),
        "patient_level_local_sensitive": True,
        "eligibility_source": "W06 endpoint QC only",
    }
    with open(schema_path, "w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    audit = {
        "workflow_stage": "W06",
        "A_modeling_population_sha256": source_hash,
        "counts": {
            "A_modeling_population": 393,
            "DFS_event_count": 89,
            "censor_count": 304,
        },
    }
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    config["input"].update({
        "source": population_path,
        "schema": schema_path,
        "source_audit": audit_path,
        "source_sha256": source_hash,
        "schema_sha256": w07._sha256_file(schema_path),
        "source_audit_sha256": w07._sha256_file(audit_path),
    })
    return config, population_path


class W07OuterSplitTests(unittest.TestCase):
    def run_synthetic(self):
        config = synthetic_config()
        population = w07._normalize_population(synthetic_population(), config)
        splits = w07.build_outer_splits(population, config)
        validation = w07.validate_outer_splits(splits, population, config)
        return config, population, splits, validation

    def test_schema_hash_and_coverage(self):
        config, population, splits, validation = self.run_synthetic()
        self.assertEqual(list(splits.columns), w07.SPLIT_COLUMNS)
        self.assertEqual(len(splits), 393 * 5 * 10)
        self.assertEqual(validation["n_outer_validation_folds"], 50)
        self.assertTrue(validation["event_gate_pass"])
        self.assertEqual(set(splits["patient_id"]), set(population["patient_id"]))

    def test_custom_config_cannot_replace_w06_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, population_path = write_bound_w06_fixture(tmp)
            config_path = os.path.join(tmp, "w07.json")
            output_path = os.path.join(tmp, "outer_splits_A.csv")
            with open(config_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle)
            with mock.patch.object(
                    w07.pd, "read_csv",
                    side_effect=AssertionError("must not read source CSV")) as reader:
                with self.assertRaises(w07.W07ValidationError):
                    w07.run_w07(population_path, output_path, config_path)
            reader.assert_not_called()
            self.assertFalse(os.path.exists(output_path))

    def test_canonical_config_content_cannot_replace_w06_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, _ = write_bound_w06_fixture(tmp)
            with mock.patch.object(w07, "_read_json", return_value=config), \
                    mock.patch.object(
                        w07.pd, "read_csv",
                        side_effect=AssertionError("must not read source CSV")) as reader:
                with self.assertRaises(w07.W07ValidationError):
                    w07.load_config(w07.DEFAULT_CONFIG)
            reader.assert_not_called()

    def test_every_fold_has_events_and_roles_do_not_overlap(self):
        config, population, splits, validation = self.run_synthetic()
        self.assertEqual(len(validation["fold_event_counts"]), 50)
        self.assertTrue(all(row["train_events"] >= 1 and
                            row["validation_events"] >= 1
                            for row in validation["fold_event_counts"]))
        for repeat in range(1, 11):
            current = splits[splits["repeat"] == repeat]
            self.assertEqual(current[current["role"] == "validation"]
                             .groupby("patient_id").size().min(), 1)
            self.assertEqual(current[current["role"] == "train"]
                             .groupby("patient_id").size().max(), 4)

    def test_duplicate_and_missing_coverage_fail(self):
        config, population, splits, _ = self.run_synthetic()
        duplicate = pd.concat([splits, splits.iloc[[0]]], ignore_index=True)
        with self.assertRaises(w07.W07ValidationError):
            w07.validate_outer_splits(duplicate, population, config)
        missing = splits.iloc[1:].copy()
        with self.assertRaises(w07.W07ValidationError):
            w07.validate_outer_splits(missing, population, config)

    def test_event_gate_failure_is_hard(self):
        config, population, splits, _ = self.run_synthetic()
        changed = population.copy()
        changed["DFS_event"] = 0
        with self.assertRaises(w07.W07ValidationError):
            w07.validate_outer_splits(splits, changed, config)

    def test_b_named_input_is_rejected_before_read(self):
        with mock.patch.object(w07.pd, "read_csv",
                               side_effect=AssertionError("must not read")) as reader:
            with self.assertRaises(w07.W07ValidationError):
                w07.load_a_modeling_population("dataset_primary_raw_B.csv",
                                               synthetic_config())
        reader.assert_not_called()

    def test_untrusted_same_name_input_is_rejected_before_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            untrusted_dir = os.path.join(tmp, "untrusted_source")
            os.makedirs(untrusted_dir)
            path = os.path.join(untrusted_dir,
                                "A_modeling_population.csv")
            synthetic_population().to_csv(path, index=False)
            with mock.patch.object(w07.pd, "read_csv",
                                   side_effect=AssertionError("must not read")) as reader:
                with self.assertRaises(w07.W07ValidationError):
                    w07.load_a_modeling_population(path, synthetic_config())
            reader.assert_not_called()

    def test_same_name_replacement_at_authorized_path_fails_hash(self):
        with mock.patch.object(w07, "_sha256_file", return_value="0" * 64), \
                mock.patch.object(w07.pd, "read_csv",
                                  side_effect=AssertionError("must not read")) as reader:
            with self.assertRaises(w07.W07ValidationError):
                w07.load_a_modeling_population(w07.DEFAULT_POPULATION)
        reader.assert_not_called()

    def test_untrusted_schema_replacement_fails_before_csv_read(self):
        schema_path = os.path.join(
            w07.OUTPUT_ROOT, "A_modeling", "A_modeling_population_schema.json")
        original_hash = w07._sha256_file

        def hash_with_untrusted_schema(path):
            if w07._absolute_path(path) == w07._absolute_path(schema_path):
                return "0" * 64
            return original_hash(path)

        with mock.patch.object(w07, "_sha256_file",
                               side_effect=hash_with_untrusted_schema), \
                mock.patch.object(w07.pd, "read_csv",
                                  side_effect=AssertionError("must not read")) as reader:
            with self.assertRaises(w07.W07ValidationError):
                w07.load_a_modeling_population(w07.DEFAULT_POPULATION)
        reader.assert_not_called()

    def test_untrusted_audit_replacement_fails_before_csv_read(self):
        audit_path = os.path.join(
            w07.OUTPUT_ROOT, "A_endpoint_qc", "endpoint_qc_summary.json")
        original_hash = w07._sha256_file

        def hash_with_untrusted_audit(path):
            if w07._absolute_path(path) == w07._absolute_path(audit_path):
                return "0" * 64
            return original_hash(path)

        with mock.patch.object(w07, "_sha256_file",
                               side_effect=hash_with_untrusted_audit), \
                mock.patch.object(w07.pd, "read_csv",
                                  side_effect=AssertionError("must not read")) as reader:
            with self.assertRaises(w07.W07ValidationError):
                w07.load_a_modeling_population(w07.DEFAULT_POPULATION)
        reader.assert_not_called()

    def test_config_records_all_required_population_rules(self):
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                            "prognosis_analysis", "configs",
                                            "w07_outer_splits.json"))
        config = w07.load_config(path)
        self.assertEqual(set(config["populations"]),
                         {"main", "M5", "R_low", "R_high", "dual_radiomics"})
        self.assertEqual(config["outer_cv"]["same_plan_for"][0], "M0")
        self.assertFalse(config["exclusion_rule"]["performance_based_exclusion"])

    def test_output_hash_is_stable_for_same_frame(self):
        _, _, splits, _ = self.run_synthetic()
        first = hashlib.sha256(w07._canonical_csv_bytes(splits)).hexdigest()
        second = hashlib.sha256(w07._canonical_csv_bytes(splits.copy())).hexdigest()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
