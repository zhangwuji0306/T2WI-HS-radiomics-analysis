import os
import sys
import unittest
from unittest import mock

import numpy as np


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_nested_cv as w08  # noqa: E402


def _survival_fixture(seed=20260908, n=24, p=5, ties=False):
    rng = np.random.RandomState(seed)
    X = rng.normal(size=(n, p))
    if ties:
        time = np.asarray([float((index // 2) + 1) for index in range(n)])
    else:
        time = np.arange(1.0, n + 1.0)
    event = np.asarray([1 if index % 3 == 0 else 0 for index in range(n)])
    return X, time, event


def _legacy_cox_components(X, time, event, beta):
    """Reference implementation matching the pre-L3C calculation order."""
    order = np.argsort(-time, kind="mergesort")
    sorted_time = time[order]
    sorted_event = event[order]
    sorted_X = X[order]
    eta = np.clip(np.asarray(sorted_X.dot(beta), dtype=float), -50.0, 50.0)
    exp_eta = np.exp(eta)
    cumulative_risk = np.cumsum(exp_eta)
    cumulative_xrisk = np.cumsum(sorted_X * exp_eta[:, None], axis=0)
    loglik = 0.0
    gradient = np.zeros(X.shape[1], dtype=float)
    for current in np.unique(sorted_time[sorted_event == 1]):
        event_mask = (sorted_time == current) & (sorted_event == 1)
        last = int(np.searchsorted(-sorted_time, -current, side="right")) - 1
        risk_sum = float(cumulative_risk[last])
        event_count = int(np.sum(event_mask))
        event_x = np.sum(sorted_X[event_mask], axis=0)
        loglik += float(np.dot(event_x, beta)) - event_count * np.log(risk_sum)
        gradient += event_x - event_count * cumulative_xrisk[last] / risk_sum
    return float(loglik), gradient


class W08L3CCoxOptimizationTests(unittest.TestCase):
    def test_prepared_risk_geometry_matches_reference_with_and_without_ties(self):
        for ties in (False, True):
            X, time, event = _survival_fixture(ties=ties)
            beta = np.linspace(-0.2, 0.3, X.shape[1])
            layout = w08._prepare_cox_risk_layout(X, time, event)
            expected = _legacy_cox_components(X, time, event, beta)
            actual = w08._cox_components_from_layout(layout, beta)
            np.testing.assert_allclose(actual[0], expected[0], rtol=1e-12,
                                       atol=1e-12)
            np.testing.assert_allclose(actual[1], expected[1], rtol=1e-12,
                                       atol=1e-12)
            self.assertEqual(layout.event_count_total, int(np.sum(event)))
            self.assertEqual(len(layout.event_times),
                             len(np.unique(time[event == 1])))
            self.assertEqual(len(layout.risk_endpoints),
                             len(layout.event_counts))

    def test_smooth_uses_one_core_call_for_value_and_gradient(self):
        X, time, event = _survival_fixture(n=20, p=3, ties=True)
        layout = w08._prepare_cox_risk_layout(X, time, event)
        model = w08.CoxElasticNetModel(alpha=0.5, penalty=0.1)
        original = w08._cox_components_from_layout
        with mock.patch.object(w08, "_cox_components_from_layout",
                               wraps=original) as core:
            value, gradient = model._smooth_from_layout(layout, np.zeros(3))
        self.assertTrue(np.isfinite(value))
        self.assertEqual(gradient.shape, (3,))
        self.assertEqual(core.call_count, 1)

    def test_elastic_fit_prepares_risk_geometry_once_and_preserves_zero_start(self):
        X, time, event = _survival_fixture(n=36, p=4, ties=True)
        original = w08._prepare_cox_risk_layout
        with mock.patch.object(w08, "_prepare_cox_risk_layout",
                               wraps=original) as prepare:
            model = w08.CoxElasticNetModel(
                alpha=0.1, penalty=0.02, max_iter=3000, tolerance=1e-7).fit(
                X, time, event)
        self.assertTrue(model.fit_audit["converged"])
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(model.fit_audit["fit_status"], "converged")
        self.assertFalse(model.fit_audit.get("failure_reason"))

    def test_failed_fit_keeps_fail_closed_state_and_audit(self):
        X, time, event = _survival_fixture(n=16, p=2)
        model = w08.CoxElasticNetModel(
            alpha=0.9, penalty=0.01, max_iter=1, tolerance=1e-12)
        with self.assertRaises(w08.W08NumericalFailure) as raised:
            model.fit(X, time, event)
        self.assertIsNone(model.coef_)
        self.assertIsNone(model.baseline_times_)
        self.assertFalse(model.fit_audit["converged"])
        self.assertEqual(model.fit_audit["fit_status"], "non_converged")
        self.assertEqual(raised.exception.audit, model.fit_audit)

    def test_uno_layout_reuses_km_weights_and_comparable_pairs(self):
        train_time = np.asarray([1., 2., 3., 4., 5., 6.])
        train_event = np.asarray([1, 0, 1, 0, 1, 0])
        validation_time = np.asarray([1., 2., 2., 5., 7.])
        validation_event = np.asarray([1, 0, 1, 0, 1])
        risk = np.asarray([0.5, 0.1, 0.4, 0.3, 0.2])
        original = w08._km_censoring_survival
        with mock.patch.object(w08, "_km_censoring_survival",
                               wraps=original) as km:
            layout = w08._prepare_uno_c_index_layout(
                train_time, train_event, validation_time, validation_event)
            prepared_score = w08._uno_c_index_from_layout(layout, risk)
            calls_after_prepare = km.call_count
            repeated_score = w08._uno_c_index_from_layout(layout, risk[::-1])
        direct_score = w08.uno_c_index(
            train_time, train_event, validation_time, validation_event, risk)
        self.assertEqual(calls_after_prepare, int(np.sum(validation_event)))
        self.assertEqual(km.call_count, calls_after_prepare)
        self.assertAlmostEqual(prepared_score, direct_score, places=12)
        self.assertTrue(np.isfinite(repeated_score))
        self.assertTrue(layout.comparable_pairs)


if __name__ == "__main__":
    unittest.main()
