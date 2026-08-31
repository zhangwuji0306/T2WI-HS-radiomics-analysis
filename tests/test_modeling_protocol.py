import hashlib
import json
import os
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PROTOCOL_JSON = os.path.join(ROOT, "prognosis_analysis", "modeling_protocol.json")
PROTOCOL_MD = os.path.join(ROOT, "prognosis_analysis", "modeling_protocol.md")
W03_FREEZE = os.path.join(
    ROOT, "prognosis_analysis", "output", "w03_habitat_radiomics_A",
    "candidate_freeze.json")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelingProtocolFreezeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PROTOCOL_JSON, encoding="utf-8") as handle:
            cls.protocol = json.load(handle)
        with open(W03_FREEZE, encoding="utf-8") as handle:
            cls.w03 = json.load(handle)

    def test_protocol_markdown_and_json_are_present(self):
        self.assertTrue(os.path.isfile(PROTOCOL_JSON))
        self.assertTrue(os.path.isfile(PROTOCOL_MD))
        with open(PROTOCOL_MD, encoding="utf-8") as handle:
            self.assertIn("# W04 Modeling protocol freeze", handle.read())

    def test_models_and_comparisons_are_exactly_frozen(self):
        self.assertEqual(
            [model["id"] for model in self.protocol["models"]],
            ["M0", "M1", "M2", "M3L", "M3H", "M4", "M5"])
        self.assertEqual(
            [comparison["id"] for comparison in self.protocol["comparisons"]],
            ["M0_to_M1", "M1_to_M2", "M2_to_M3L", "M2_to_M3H",
             "M3L_vs_M3H", "M2_to_M4", "M0_to_M5"])
        self.assertEqual(
            self.protocol["predictor_blocks"]["C"]["variables"],
            ["年龄", "CEA_log", "mrT_4级", "mrN_3级", "MRF", "mrEMVI",
             "thickness", "EID", "活检病理非腺癌"])
        self.assertEqual(
            self.protocol["predictor_blocks"]["G"]["variables"],
            ["H_high_fraction", "sv_median_minus_boundary", "sv_IQR",
             "interface_density", "H_high_largest_component_tumor_fraction",
             "H_high_radial_burden"])

    def test_w03_candidates_and_technical_rules_are_bound(self):
        self.assertEqual(self.w03["freeze_status"], "complete")
        self.assertTrue(self.w03["outcome_blind"])
        self.assertFalse(self.w03["B_data_read"])
        for block, count, key in (
                ("R_low", 49, "R_low_candidate_hash"),
                ("R_high", 10, "R_high_candidate_hash")):
            candidate = self.protocol["predictor_blocks"][block]
            self.assertEqual(candidate["candidate_count"], count)
            self.assertEqual(candidate["candidate_hash"], self.w03[key])
            self.assertEqual(candidate["candidate_hash"],
                             self.protocol["predictor_blocks"][block]["candidate_hash"])

    def test_nested_cv_and_hyperparameters_are_fixed(self):
        cv = self.protocol["nested_cv"]
        self.assertEqual(cv["outer"]["folds"], 5)
        self.assertEqual(cv["outer"]["repeats"], 10)
        self.assertEqual(cv["outer"]["total_outer_validation_folds"], 50)
        self.assertEqual(cv["inner"]["folds"], 5)
        self.assertEqual(cv["randomness"]["base_seed"], 12345)
        self.assertEqual(
            self.protocol["training_only_pipeline"]["high_dimensional_model"]["alpha_grid"],
            [0.1, 0.5, 0.9, 1.0])
        self.assertEqual(
            self.protocol["training_only_pipeline"]["high_dimensional_model"]
            ["lambda_grid"]["selection"], "inner CV only")

    def test_access_gate_is_fail_closed_before_model_freeze(self):
        gate = self.protocol["access_gate"]
        self.assertFalse(gate["A_outcome_read_allowed_at_W04_freeze"])
        self.assertFalse(gate["B_unlock"])
        model_lock = gate["model_freeze_lock"]
        self.assertEqual(model_lock["status_at_W04_freeze"], "not_generated")
        self.assertFalse(model_lock["exists_at_W04_freeze"])
        self.assertTrue(model_lock["must_not_be_created_by_W04"])

    def test_source_revisions_match_local_files(self):
        for source in self.protocol["source_revisions"].values():
            path = os.path.join(ROOT, source["path"].replace("/", os.sep))
            self.assertTrue(os.path.isfile(path), source["path"])
            self.assertEqual(sha256(path), source["sha256"], source["path"])

    def test_primary_endpoint_and_secondary_scope(self):
        endpoint = self.protocol["endpoint"]
        self.assertEqual(endpoint["primary"]["name"], "DFS")
        self.assertEqual(endpoint["primary"]["horizons_years"], [3, 5])
        self.assertEqual(endpoint["secondary"]["names"], ["OS", "CSS"])
        self.assertTrue(endpoint["secondary"]["not_part_of_W04_primary_model_selection"])


if __name__ == "__main__":
    unittest.main()
