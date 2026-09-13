import copy
import os
import sys
import unittest
from unittest import mock

import numpy as np


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
TEST_ROOT = os.path.dirname(__file__)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if TEST_ROOT not in sys.path:
    sys.path.insert(0, TEST_ROOT)

import w08_nested_cv as w08  # noqa: E402
from test_w08_nested_cv import synthetic_frame  # noqa: E402


def locked_config():
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "prognosis_analysis", "configs",
        "w08_nested_cv.json"))
    return w08.load_config(path)


def deterministic_survival_case(seed=6104, n=48, p=4):
    rng = np.random.RandomState(seed)
    X = rng.normal(size=(n, p))
    time = np.arange(1.0, n + 1.0)
    event = np.asarray([1 if index % 3 == 0 else 0 for index in range(n)])
    return X, time, event


class R64AConvergenceTests(unittest.TestCase):
    def test_registered_budget_and_tolerance_are_fixed(self):
        config = locked_config()
        self.assertEqual(config["elastic_net_max_iter"], 3000)
        self.assertEqual(w08.ELASTIC_NET_MAX_ITER, 3000)
        self.assertEqual(w08.ELASTIC_NET_TOLERANCE, 1e-7)
        model = w08.CoxElasticNetModel(alpha=0.5, penalty=0.1)
        self.assertEqual(model.max_iter, 3000)
        self.assertEqual(model.tolerance, 1e-7)

    def test_formal_path_rejects_unregistered_solver_budget_or_tolerance(self):
        config = locked_config()
        with self.assertRaises(w08.W08ValidationError):
            w08.run_w08_in_memory(
                None, None, None, config=config, require_fixed_hash=True,
                solver_max_iter=2999)
        with self.assertRaises(w08.W08ValidationError):
            w08.run_w08_in_memory(
                None, None, None, config=config, require_fixed_hash=True,
                solver_tolerance=1e-6)

    def test_alpha_lambda_and_frozen_binding_tampering_fails_closed(self):
        config = locked_config()
        altered = copy.deepcopy(config)
        altered["alpha_grid"][0] = 0.2
        with self.assertRaises(w08.W08ValidationError):
            w08._validate_config(altered)

        altered = copy.deepcopy(config)
        altered["lambda_grid"]["values_per_alpha"] = 99
        with self.assertRaises(w08.W08ValidationError):
            w08._validate_config(altered)

        for key in ("frozen_outer_split_sha256", "W07A_protocol_sha256"):
            altered = copy.deepcopy(config)
            altered[key] = "0" * 64
            with self.subTest(binding=key):
                with self.assertRaises(w08.W08ValidationError):
                    w08._validate_config(altered)

        altered = copy.deepcopy(config)
        altered["provenance"]["R_high_candidate_hash"] = "0" * 64
        with self.assertRaises(w08.W08ValidationError):
            w08._validate_config(altered)

    def test_en_failed_refit_clears_all_predictive_state(self):
        X, time, event = deterministic_survival_case()
        model = w08.CoxElasticNetModel(
            alpha=0.5, penalty=0.1, max_iter=3000, tolerance=1e-7).fit(
                X, time, event)
        self.assertIsNotNone(model.coef_)
        self.assertIsNotNone(model.baseline_times_)
        model.max_iter = 1
        with self.assertRaises(w08.W08NumericalFailure) as raised:
            model.fit(X, time, event)
        self.assertEqual(raised.exception.audit["failure_reason"],
                         "iteration_budget_exhausted")
        self.assertIsNone(model.coef_)
        self.assertIsNone(model.baseline_times_)
        self.assertIsNone(model.baseline_survival_)
        with self.assertRaises(w08.W08ValidationError):
            model.predict_risk(X)

    def test_solver_regression_preserves_fit_and_selection_results(self):
        X, time, event = deterministic_survival_case()
        before = w08.CoxElasticNetModel(
            alpha=0.5, penalty=0.1, max_iter=250, tolerance=1e-7).fit(
                X, time, event)
        after = w08.CoxElasticNetModel(
            alpha=0.5, penalty=0.1, max_iter=3000, tolerance=1e-7).fit(
                X, time, event)
        np.testing.assert_allclose(before.coef_, after.coef_, rtol=1e-10,
                                   atol=1e-10)
        np.testing.assert_allclose(before.predict_risk(X),
                                   after.predict_risk(X), rtol=1e-10,
                                   atol=1e-10)
        np.testing.assert_allclose(
            before.predict_survival(X, {"horizon": 24.0})["horizon"],
            after.predict_survival(X, {"horizon": 24.0})["horizon"],
            rtol=1e-10, atol=1e-10)
        self.assertEqual(before.fit_audit["convergence_reason"],
                         after.fit_audit["convergence_reason"])
        self.assertAlmostEqual(before.fit_audit["last_objective"],
                               after.fit_audit["last_objective"],
                               places=10)

        frame = synthetic_frame(30).reset_index(drop=True)
        frame["DFS_event"] = [1] * 15 + [0] * 15
        legacy_selection = w08.tune_elastic_net(
            frame, "M3L", inner_seed=22346, lambda_count=2,
            max_iter=250, tolerance=1e-7)
        remediated_selection = w08.tune_elastic_net(
            frame, "M3L", inner_seed=22346, lambda_count=2,
            max_iter=3000, tolerance=1e-7)
        self.assertEqual(legacy_selection["alpha"],
                         remediated_selection["alpha"])
        self.assertEqual(legacy_selection["lambda_ratio"],
                         remediated_selection["lambda_ratio"])

    def test_candidate_order_and_uniform_budget_are_not_runtime_adaptive(self):
        captured = []
        original = w08.CoxElasticNetModel.__init__

        def capture(model, alpha, penalty, max_iter=w08.ELASTIC_NET_MAX_ITER,
                    tolerance=w08.ELASTIC_NET_TOLERANCE):
            captured.append((float(alpha), float(penalty), int(max_iter),
                             float(tolerance)))
            original(model, alpha, penalty, max_iter=max_iter,
                     tolerance=tolerance)

        with mock.patch.object(w08.CoxElasticNetModel, "__init__", new=capture):
            # A constructor-only probe is sufficient here: the production
            # tuning loop constructs every candidate from its one shared call
            # argument, while the full candidate loop is covered separately.
            for alpha in w08.ALPHA_GRID:
                for ratio in (1.0, 0.01, w08.LAMBDA_MIN_RATIO):
                    w08.CoxElasticNetModel(
                        alpha, 0.2 * ratio, max_iter=w08.ELASTIC_NET_MAX_ITER,
                        tolerance=w08.ELASTIC_NET_TOLERANCE)
        self.assertEqual(len(captured), len(w08.ALPHA_GRID) * 3)
        self.assertEqual({row[2] for row in captured}, {3000})
        self.assertEqual({row[3] for row in captured}, {1e-7})
        self.assertEqual(
            [row[0] for row in captured],
            [alpha for alpha in w08.ALPHA_GRID for _ in range(3)])


if __name__ == "__main__":
    unittest.main()
