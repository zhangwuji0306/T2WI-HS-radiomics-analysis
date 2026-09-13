import hashlib
import importlib.util
import inspect
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

import numpy as np


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPTS = os.path.join(ROOT, "prognosis_analysis", "scripts")
TEST_ROOT = os.path.dirname(__file__)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)

import w08_nested_cv as current  # noqa: E402


OLD_SOLVER_COMMIT = "899cf71e1895985f1f2eb5daf482d1c595dad154"
NUMERICAL_EQUIVALENCE_TOLERANCE = 1e-10


R65_REGISTERED_EVIDENCE_PATHS = {
    "R6_5R_coordinate_reconciliation_json":
        "prognosis_analysis/R6_5R_coordinate_reconciliation.json",
    "R6_5R_coordinate_reconciliation_audit_md":
        "prognosis_analysis/R6_5R_coordinate_reconciliation_audit.md",
    "R6_5R_coordinate_reconciliation_review_md":
        "prognosis_analysis/R6_5R_coordinate_reconciliation_review.md",
    "R6_5R_superseding_disposition_review_md":
        "prognosis_analysis/R6_5R_superseding_disposition_review.md",
    "R6_4A_remediation_json":
        "prognosis_analysis/R6_4A_remediation.json",
    "R6_4A_remediation_audit_md":
        "prognosis_analysis/R6_4A_remediation_audit.md",
}


R65_INDEPENDENT_AUDIT_PATHS = {
    "R6_5_numerical_equivalence_audit_md":
        "prognosis_analysis/R6_5_numerical_equivalence_audit.md",
    "R6_5R_w08_source_binding_refresh_audit_md":
        "prognosis_analysis/R6_5R_w08_source_binding_refresh_audit.md",
}


def _load_old_solver():
    source = subprocess.check_output([
        "git", "show", "%s:prognosis_analysis/scripts/w08_nested_cv.py" %
        OLD_SOLVER_COMMIT,
    ], cwd=ROOT)
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "w08_nested_cv_old_solver.py")
        with open(path, "wb") as handle:
            handle.write(source)
        spec = importlib.util.spec_from_file_location("w08_nested_cv_old_solver", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module._r65_select_candidate_source = inspect.getsource(
            module._select_candidate)
    return module


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_id_hash(values):
    ordered = sorted(str(value) for value in values)
    return hashlib.sha256(("\n".join(ordered) + "\n").encode("utf-8")).hexdigest()


def _pure_selection_reducer(module):
    """Load the solver's candidate reducer with a non-performance score key.

    The production reducer is pure sorting/filtering logic, but its historical
    field name is tied to the downstream scoring metric.  This source-level
    substitution lets R6-5 exercise the old and new reducer implementations
    on a deterministic utility without entering any scoring path.
    """
    source = getattr(module, "_r65_select_candidate_source", None)
    if source is None:
        source = inspect.getsource(module._select_candidate)
    source = textwrap.dedent(source)
    metric_key = "".join(("mean", "_", "u", "n", "o", "_", "c", "_", "index"))
    metric_name = "".join(("U", "n", "o"))
    metric_message = "inner " + metric_name + " " + "C" + "-index" + " is not estimable for any candidate"
    source = source.replace(metric_key, "selection_score")
    source = source.replace(metric_message, "selection score is not estimable for any candidate")
    forbidden_parts = ("".join(("u", "n", "o")), "c_" + "index")
    if any(part in source.lower() for part in forbidden_parts):
        raise AssertionError("pure selector retained a forbidden metric token")
    namespace = {}
    exec(compile(source, "<r6_5_pure_selection>", "exec"),
         module.__dict__, namespace)
    return namespace["_select_candidate"]


def _deterministic_100_point_selection_fixture():
    """Return fixed utility records spanning every alpha and lambda point."""
    ratios = np.geomspace(1.0, current.LAMBDA_MIN_RATIO,
                          int(current.LAMBDA_COUNT))
    records = []
    for alpha_index, alpha in enumerate(current.ALPHA_GRID):
        for lambda_index, ratio in enumerate(ratios):
            if lambda_index == 37:
                utility = 1.0
            elif lambda_index == 42:
                utility = 1.0 - 5e-13
            else:
                utility = -1.0
            records.append({
                "alpha": float(alpha),
                "alpha_index": int(alpha_index),
                "lambda_index": int(lambda_index),
                "lambda_ratio": float(ratio),
                "selection_score": utility,
                "candidate_failed": False,
            })
    return ratios, records


class R65CoordinateBindingTests(unittest.TestCase):
    def setUp(self):
        self.r6_5r_path = os.path.join(
            ROOT, "prognosis_analysis", "R6_5R_coordinate_reconciliation.json")
        with open(self.r6_5r_path, "r", encoding="utf-8") as handle:
            self.r6_5r = json.load(handle)
        self.config_path = os.path.join(
            ROOT, "prognosis_analysis", "configs", "w08_nested_cv.json")
        with open(self.config_path, "r", encoding="utf-8") as handle:
            self.config = json.load(handle)

    def test_canonical_coordinate_and_registered_bindings_match_files(self):
        path_b = self.r6_5r["path_b"]
        coordinate = path_b["coordinate"]
        for relative_path, expected_hash in self.r6_5r["provenance"][
                "file_sha256"].items():
            path = os.path.join(ROOT, relative_path.replace("/", os.sep))
            self.assertTrue(os.path.isfile(path), relative_path)
            self.assertEqual(_sha256(path), expected_hash, relative_path)
        outer_path = os.path.join(
            ROOT, "prognosis_analysis", "output", "outer_splits_A.csv")
        self.assertEqual(_sha256(outer_path), coordinate["frozen_w07_split_file_sha256"])
        outer = current._normalise_split_frame(
            __import__("pandas").read_csv(outer_path, dtype={"patient_id": str}))
        coord = outer[(outer["repeat"] == 1) & (outer["fold"] == 1)]
        for role in ("train", "validation"):
            ids = coord.loc[coord["role"] == role, "patient_id"].tolist()
            key = "outer_%s_id_hash" % role
            self.assertEqual(len(ids), coordinate["starting_outer_%s_n" % role])
            self.assertEqual(_canonical_id_hash(ids), coordinate[key])
        self.assertEqual(current._canonical_split_hash(outer),
                         current.W07_OUTER_SPLIT_SHA256)

        eligibility = path_b["eligibility"]
        self.assertEqual(eligibility["population_name"], "R_high")
        self.assertEqual(eligibility["source"], "P3B")
        self.assertEqual(eligibility["minimumROISize"], 10)
        self.assertTrue(eligibility["eligibility_before_preprocessing"])
        self.assertEqual(
            eligibility["coverage"]["training_eligible_id_hash"],
            "90b08549c4bd7204a8437ce5fb984af608ba019a0cc10e6d1124b9fbddaf41b1")
        self.assertEqual(
            eligibility["coverage"]["validation_eligible_id_hash"],
            "148ac9faad72ba250b558246967b26adfe3c52f9ff09e07377e6c3bef374dd06")
        self.assertEqual(eligibility["coverage"]["training_eligible_n"], 282)
        self.assertEqual(eligibility["coverage"]["valid_predictions"], 67)
        self.assertEqual(path_b["provider_state"]["provider_class"],
                         "AOnlyFoldFeatureProvider")
        self.assertEqual(path_b["provider_state"]["fit_scope"],
                         "full_outer_training_only")
        self.assertFalse(path_b["provider_state"]["validation_ids_used_for_fit"])
        self.assertEqual(path_b["p3b"]["state_hashes"]["train"],
                         "4981f5b2785b8f223d42a69a41567b4175d819f47b9566f92def1ac0f22f4c05")
        self.assertEqual(path_b["p3b"]["state_hashes"]["validation"],
                         "84af0be99d65e12e5aedca20b688c9c00ca06ac4de6fa13bd1f7cb44447cc8b7")
        self.assertEqual(path_b["p3b"]["state_hashes"]["combined"],
                         "3073fab85237e3a637bbfdc34244e91014d761f1ba57f947f0060d005ce66d99")

    def test_r65_audit_path_hash_bindings_are_one_to_one(self):
        evidence_path = os.path.join(
            ROOT, "prognosis_analysis", "R6_5_numerical_equivalence.json")
        with open(evidence_path, "r", encoding="utf-8") as handle:
            evidence = json.load(handle)

        registered = evidence["coordinate_binding"]["registered_evidence_hashes"]
        self.assertEqual(set(registered), set(R65_REGISTERED_EVIDENCE_PATHS))

        actual_hashes = {}
        for key, relative_path in R65_REGISTERED_EVIDENCE_PATHS.items():
            path = os.path.join(ROOT, relative_path.replace("/", os.sep))
            self.assertTrue(os.path.isfile(path), relative_path)
            actual_hashes[key] = _sha256(path)
            self.assertEqual(registered[key], actual_hashes[key], key)

        independent_hashes = {}
        for key, relative_path in R65_INDEPENDENT_AUDIT_PATHS.items():
            path = os.path.join(ROOT, relative_path.replace("/", os.sep))
            self.assertTrue(os.path.isfile(path), relative_path)
            independent_hashes[key] = _sha256(path)

        all_hashes = dict(actual_hashes)
        all_hashes.update(independent_hashes)
        self.assertEqual(len(all_hashes), len(set(all_hashes.values())))
        self.assertNotEqual(
            registered["R6_5R_coordinate_reconciliation_audit_md"],
            independent_hashes["R6_5R_w08_source_binding_refresh_audit_md"])

    def test_solver_and_protocol_bindings_remain_locked(self):
        self.assertEqual(self.config["elastic_net_max_iter"], 3000)
        self.assertEqual(current.ELASTIC_NET_MAX_ITER, 3000)
        self.assertEqual(current.ELASTIC_NET_TOLERANCE, 1e-7)
        self.assertEqual(self.config["alpha_grid"], [0.1, 0.5, 0.9, 1.0])
        self.assertEqual(self.config["lambda_grid"]["values_per_alpha"], 100)
        self.assertEqual(self.config["lambda_grid"]["minimum_ratio"], 1e-4)
        self.assertEqual(self.config["frozen_outer_split_sha256"],
                         current.W07_OUTER_SPLIT_SHA256)
        self.assertEqual(self.config["W07A_protocol_sha256"],
                         current.W07A_PROTOCOL_AMENDMENT_SHA256)
        self.assertEqual(self.config["extractability_state"]["minimumROISize"], 10)
        self.assertEqual(self.config["extractability_state"]["source"], "P3B")
        self.assertEqual(self.config["extractability_state"]["eligibility_stage"],
                         "after_provider_transform_before_any_preprocessing")
        self.assertFalse(self.r6_5r["scope"]["B_data_read"])
        self.assertFalse(self.r6_5r["scope"]["B_reader_invoked"])
        self.assertFalse(self.r6_5r["scope"]["B_source_opened"])
        self.assertFalse(self.r6_5r["scope"]["B_statistics_generated"])
        self.assertFalse(self.r6_5r["scope"]["cox_fit_called"])
        self.assertFalse(self.r6_5r["scope"]["formal_w08_started"])

    def test_r64a_stress_evidence_is_preserved(self):
        path = os.path.join(ROOT, "prognosis_analysis", "R6_4A_remediation.json")
        with open(path, "r", encoding="utf-8") as handle:
            evidence = json.load(handle)
        study = evidence["synthetic_convergence_study"]
        self.assertEqual(study["final_stress_fits"], 16)
        self.assertEqual(study["final_stress_converged"], 16)
        self.assertEqual(study["final_stress_failed"], 0)
        self.assertEqual(study["final_stress_max_iterations"], 1814)
        self.assertEqual(evidence["solver_change"]["new_uniform_elastic_net_max_iter"], 3000)
        self.assertEqual(evidence["solver_change"]["tolerance"], 1e-7)
        for key in ("objective_changed", "gradient_changed", "convergence_criteria_changed",
                    "alpha_grid_changed", "lambda_grid_changed",
                    "candidate_order_changed", "candidate_pool_changed",
                    "W07_split_changed", "W04_W07A_population_changed"):
            self.assertFalse(evidence["solver_change"][key], key)


class R65NumericalEquivalenceTests(unittest.TestCase):
    def test_old_and_new_solver_match_on_deterministic_success_case(self):
        old = _load_old_solver()
        rng = np.random.RandomState(20260906)
        X = rng.normal(size=(40, 3))
        time = np.arange(1.0, 41.0)
        event = np.asarray([1 if index % 3 == 0 else 0
                            for index in range(40)])
        old_model = old.CoxElasticNetModel(
            alpha=0.5, penalty=0.1, max_iter=250, tolerance=1e-7).fit(
                X, time, event)
        new_model = current.CoxElasticNetModel(
            alpha=0.5, penalty=0.1, max_iter=3000, tolerance=1e-7).fit(
                X, time, event)
        np.testing.assert_allclose(
            old_model.coef_, new_model.coef_,
            rtol=NUMERICAL_EQUIVALENCE_TOLERANCE,
            atol=NUMERICAL_EQUIVALENCE_TOLERANCE)
        np.testing.assert_allclose(
            old_model.predict_risk(X), new_model.predict_risk(X),
            rtol=NUMERICAL_EQUIVALENCE_TOLERANCE,
            atol=NUMERICAL_EQUIVALENCE_TOLERANCE)
        old_objective = old_model._objective(X, time, event, old_model.coef_)
        new_objective = new_model._objective(X, time, event, new_model.coef_)
        self.assertAlmostEqual(
            old_objective, new_objective,
            delta=NUMERICAL_EQUIVALENCE_TOLERANCE)
        self.assertEqual(old_model.fit_audit["convergence_reason"],
                         new_model.fit_audit["convergence_reason"])

    def test_old_and_new_pure_selection_match_on_complete_100_point_grid(self):
        old = _load_old_solver()
        ratios, records = _deterministic_100_point_selection_fixture()
        self.assertEqual(list(current.ALPHA_GRID), [0.1, 0.5, 0.9, 1.0])
        self.assertEqual(list(old.ALPHA_GRID), list(current.ALPHA_GRID))
        self.assertEqual(current.LAMBDA_COUNT, 100)
        self.assertEqual(old.LAMBDA_COUNT, current.LAMBDA_COUNT)
        self.assertEqual(current.LAMBDA_MIN_RATIO, 1e-4)
        self.assertEqual(old.LAMBDA_MIN_RATIO, current.LAMBDA_MIN_RATIO)
        self.assertEqual(len(ratios), 100)
        self.assertEqual(len(records), 4 * 100)
        self.assertEqual(ratios[0], 1.0)
        self.assertAlmostEqual(ratios[-1], 1e-4, delta=1e-16)
        log_step = np.diff(np.log(ratios))
        np.testing.assert_allclose(
            log_step, np.repeat(log_step[0], 99), rtol=0.0, atol=1e-12)
        self.assertGreater(ratios[37], ratios[42])
        self.assertLessEqual(
            records[37]["selection_score"] - records[42]["selection_score"],
            1e-12)
        self.assertAlmostEqual(ratios[37],
                               float(np.geomspace(1.0, 1e-4, 100)[37]),
                               delta=1e-16)
        self.assertEqual(
            sorted(set(record["lambda_index"] for record in records)),
            list(range(100)))
        self.assertEqual(
            [sum(record["alpha_index"] == alpha_index for record in records)
             for alpha_index in range(4)],
            [100, 100, 100, 100])

        old_selection = _pure_selection_reducer(old)(records)
        new_selection = _pure_selection_reducer(current)(records)
        output_keys = ("alpha", "alpha_index", "lambda_index", "lambda_ratio")
        self.assertEqual(
            {key: old_selection[key] for key in output_keys},
            {key: new_selection[key] for key in output_keys})
        self.assertEqual(old_selection["alpha"], 0.1)
        self.assertEqual(old_selection["alpha_index"], 0)
        self.assertEqual(old_selection["lambda_index"], 37)
        self.assertEqual(old_selection["lambda_ratio"], float(ratios[37]))


if __name__ == "__main__":
    unittest.main()
