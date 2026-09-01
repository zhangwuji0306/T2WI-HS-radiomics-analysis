import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w07_outer_splits as w07  # noqa: E402
import w08_nested_cv as w08  # noqa: E402


def w08_config():
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                        "prognosis_analysis", "configs",
                                        "w08_nested_cv.json"))
    return w08.load_config(path)


def synthetic_frame(n=50):
    ids = ["S%03d" % index for index in range(n)]
    frame = pd.DataFrame({
        "patient_id": ids,
        "DFS_time": np.linspace(2.0, 100.0, n),
        "DFS_event": [1 if index < n // 2 else 0 for index in range(n)],
        "split": ["A"] * n,
        "technical_cohort": ["A393"] * n,
        "年龄": np.linspace(40.0, 75.0, n),
        "CEA_log": np.log1p(np.linspace(1.0, 20.0, n)),
        "mrT_4级": [1 + index % 4 for index in range(n)],
        "mrN_3级": [index % 4 for index in range(n)],
        "MRF": [index % 2 for index in range(n)],
        "mrEMVI": [(index + 1) % 2 for index in range(n)],
        "thickness": np.linspace(3.0, 12.0, n),
        "EID": np.linspace(0.5, 5.0, n),
        "活检病理非腺癌": [index % 2 for index in range(n)],
        "H_high_fraction": np.linspace(0.1, 0.9, n),
        "sv_median_minus_boundary": np.linspace(-0.4, 0.4, n),
        "sv_IQR": np.linspace(0.2, 1.2, n),
        "interface_density": np.linspace(0.05, 0.5, n),
        "H_high_largest_component_tumor_fraction": np.linspace(0.02, 0.7, n),
        "H_high_radial_burden": np.linspace(0.1, 0.8, n),
        "R_low_structurally_defined": [1] * n,
        "R_low_technically_available": [1] * n,
        "R_high_structurally_defined": [1] * n,
        "R_high_technically_available": [1] * n,
        "W_available": [1] * n,
    })
    # The first two low-habitat features are intentionally correlated so the
    # training-only correlation reduction is exercised.
    frame["R_low__f0"] = np.linspace(-1.0, 1.0, n)
    frame["R_low__f1"] = frame["R_low__f0"] * 0.99 + 0.001 * np.arange(n)
    frame["R_low__f2"] = np.sin(np.arange(n) / 3.0)
    frame["R_high__f0"] = np.cos(np.arange(n) / 4.0)
    frame["R_high__f1"] = np.linspace(1.0, 2.0, n)
    frame["W__f0"] = np.sin(np.arange(n) / 5.0) + np.arange(n) / n
    return frame


def synthetic_splits(frame):
    population = frame[["patient_id", "DFS_event"]].copy()
    config = json.loads(json.dumps(w07._read_json(w07.DEFAULT_CONFIG)))
    splits = w07.build_outer_splits(population, config)
    w07.validate_outer_splits(splits, population, config)
    return population, splits


def convergent_synthetic_frame(n=50):
    """Return a deterministic, non-separated fixture for fitted-model tests."""
    frame = synthetic_frame(n)
    rng = np.random.RandomState(2026)
    frame["DFS_time"] = np.arange(2.0, float(n) + 2.0)
    event = np.zeros(n, dtype=int)
    event[rng.choice(n, n // 2, replace=False)] = 1
    frame["DFS_event"] = event
    for column in ["年龄", "CEA_log", "thickness", "EID"]:
        frame[column] = rng.normal(size=n)
    for column, levels in [("mrT_4级", [1, 2, 3, 4]),
                           ("mrN_3级", [0, 1, 2, 3])]:
        frame[column] = rng.choice(levels, size=n)
    for column in ["MRF", "mrEMVI", "活检病理非腺癌"]:
        frame[column] = rng.randint(0, 2, size=n)
    for column in w08.GLOBAL_COLUMNS:
        frame[column] = rng.normal(size=n)
    return frame


class W08NestedCVTests(unittest.TestCase):
    def test_config_freezes_models_and_tuning_grid(self):
        config = w08_config()
        self.assertEqual(list(config["models"]), list(w08.MODEL_SPECS))
        self.assertEqual(config["alpha_grid"], list(w08.ALPHA_GRID))
        self.assertEqual(config["lambda_grid"]["values_per_alpha"], 100)
        self.assertEqual(config["lambda_grid"]["minimum_ratio"], 1e-4)
        self.assertEqual(config["frozen_outer_split_sha256"],
                         w08.W07_OUTER_SPLIT_SHA256)
        self.assertEqual(tuple(item["run_id"] for item in config["fixed_runs"]),
                         w08.FIXED_RUN_IDS)

    def test_one_synthetic_outer_fold_covers_all_w04_models(self):
        frame = convergent_synthetic_frame()
        population, splits = synthetic_splits(frame)
        values = {identifier: np.linspace(1.0 + (index % 3),
                                          3.0 + (index % 3), 6)
                  for index, identifier in enumerate(frame["patient_id"])}
        provider = w08.FrameFoldFeatureProvider(frame, values)
        result = w08.run_w08_in_memory(
            frame, splits, provider, config=w08_config(),
            models=list(w08.MODEL_SPECS), strict_schema=False,
            lambda_count=5, max_outer_folds=1, solver_max_iter=60)
        self.assertEqual(set(result["fold_results"]["model_id"]),
                         set(w08.MODEL_SPECS))
        self.assertEqual(len(result["fold_results"]), 7)
        self.assertEqual(len(result["selection_results"]), 7)
        for _, selection in result["selection_results"].iterrows():
            expected_failures = sum(
                record["candidate_failed"]
                for record in selection["inner_records"])
            self.assertEqual(int(selection["candidate_failures"]),
                             expected_failures)
        self.assertTrue((result["fold_results"]["outer_validation_used_for_selection"] == False).all())  # noqa: E712
        self.assertEqual(result["audit"]["B_data_read"], False)
        self.assertFalse(result["audit"]["patient_level_outputs_written"])
        # Five inner folds x four alphas x five synthetic lambda values.
        high_dim = result["selection_results"].loc[
            result["selection_results"]["model_id"].isin(["M3L", "M3H", "M4", "M5"])]
        self.assertTrue((high_dim["candidate_attempts"] == 100).all())
        for _, row in result["selection_results"].iterrows():
            inner_records = row["inner_records"]
            self.assertTrue(all(record["inner_validation_ids_hash"] !=
                                row["validation_id_hash"]
                                for record in inner_records))

    def test_provider_fit_receives_training_ids_only_and_reuses_boundary(self):
        frame = convergent_synthetic_frame()
        population, splits = synthetic_splits(frame)
        values = {identifier: np.asarray([1.0, 1.1, 1.2, 1.3])
                  for identifier in frame["patient_id"]}
        # Make the first validation group an extreme outlier.  A fold-specific
        # implementation must not move its boundary because of this value.
        first_validation = splits.loc[
            (splits["repeat"] == 1) & (splits["fold"] == 1) &
            (splits["role"] == "validation"), "patient_id"].iloc[0]
        values[first_validation] = np.asarray([100.0, 100.1, 100.2, 100.3])
        provider = w08.FrameFoldFeatureProvider(frame, values)
        result = w08.run_w08_in_memory(
            frame, splits, provider, config=w08_config(), models=["M0"],
            strict_schema=False, max_outer_folds=1, solver_max_iter=40)
        train_ids = set(splits.loc[
            (splits["repeat"] == 1) & (splits["fold"] == 1) &
            (splits["role"] == "train"), "patient_id"])
        self.assertEqual(set(provider.fit_calls[0]), train_ids)
        self.assertNotIn(first_validation, provider.fit_calls[0])
        self.assertGreater(len(provider.transform_calls), 0)
        self.assertEqual(result["fold_results"].iloc[0]["training_id_hash"],
                         w08.canonical_id_hash(train_ids))
        self.assertTrue(result["fold_results"].iloc[0]["outer_split_hash"])

    def test_split_hash_is_propagated_without_redefinition(self):
        frame = synthetic_frame()
        _, splits = synthetic_splits(frame)
        digest = hashlib.sha256(
            splits[w08.W07_SPLIT_COLUMNS].to_csv(
                index=False, lineterminator="\n").encode("utf-8")).hexdigest()
        self.assertEqual(w08._canonical_split_hash(splits), digest)
        self.assertNotEqual(digest, "")
        with self.assertRaises(w08.W08ValidationError):
            w08.run_w08_in_memory(
                frame, splits, w08.FrameFoldFeatureProvider(
                    frame, {pid: [1.0, 2.0] for pid in frame["patient_id"]}),
                config=w08_config(), models=["M0"], strict_schema=False,
                require_fixed_hash=True, max_outer_folds=1)

    def test_b_row_and_b_path_fail_before_any_read_or_fit(self):
        frame = synthetic_frame()
        frame.loc[0, "split"] = "B"
        provider = mock.Mock(spec=w08.FoldFeatureProvider)
        provider.fold_specific_habitat = True
        with self.assertRaises(w08.W08ValidationError):
            w08.run_w08_in_memory(
                frame, synthetic_splits(synthetic_frame())[1], provider,
                config=w08_config(), models=["M0"], strict_schema=False)
        provider.fit.assert_not_called()
        with mock.patch.object(w08.pd, "read_csv",
                               side_effect=AssertionError("must not read")) as reader:
            with self.assertRaises(w08.W08ValidationError):
                w08.load_frozen_outer_splits(
                    pd.DataFrame({"patient_id": [], "DFS_event": []}),
                    path=os.path.join("synthetic", "outer_splits_B.csv"))
        reader.assert_not_called()

    def test_low_penalty_path_attempts_every_candidate(self):
        frame = synthetic_frame()
        # A direct inner-tuning fixture keeps this test small while retaining
        # the production 5-fold/4-alpha logic.
        frame = frame.iloc[:30].reset_index(drop=True)
        frame["DFS_event"] = [1] * 15 + [0] * 15
        selection = w08.tune_elastic_net(
            frame, "M3L", inner_seed=22346, lambda_count=3,
            max_iter=45, tolerance=1e-6)
        self.assertEqual(selection["candidate_attempts"], 5 * 4 * 3)
        self.assertEqual(
            selection["candidate_failures"],
            sum(row["candidate_failed"] for row in selection["all_inner_records"]))
        self.assertTrue(selection["all_inner_records"])
        self.assertTrue(all(row["candidate_attempted"]
                            for row in selection["all_inner_records"]))
        self.assertTrue(selection["stability_actions"])

    def test_population_alignment_includes_dfs_time(self):
        frame = synthetic_frame()
        population, _ = synthetic_splits(frame)
        population["DFS_time"] = frame.set_index("patient_id").loc[
            population["patient_id"], "DFS_time"].to_numpy()
        changed = population.copy()
        changed.loc[0, "DFS_time"] = 999.0
        with self.assertRaises(w08.W08ValidationError):
            w08._validate_population_alignment(frame, changed)

    def test_split_normalisation_uses_string_patient_ids(self):
        frame = pd.DataFrame({
            "patient_id": [1, 2], "repeat": [1, 1], "fold": [1, 1],
            "role": ["train", "validation"], "seed": [12345, 12345],
        })
        normalised = w08._normalise_split_frame(frame)
        self.assertEqual(normalised["patient_id"].dtype, object)
        self.assertEqual(normalised["patient_id"].tolist(), ["1", "2"])

    def test_prefilled_frame_provider_cannot_be_formal_provider(self):
        frame = synthetic_frame()
        _, splits = synthetic_splits(frame)
        provider = w08.FrameFoldFeatureProvider(
            frame, {pid: [1.0, 2.0] for pid in frame["patient_id"]})
        with self.assertRaisesRegex(
                w08.W08ValidationError, "explicit fold-feature regeneration"):
            w08.run_w08_in_memory(
                frame, splits, provider, config=w08_config(), models=["M0"],
                strict_schema=False, require_fixed_hash=True)

    def test_formal_provider_must_audit_all_fold_specific_columns(self):
        class IncompleteFormalProvider(w08.FoldFeatureProvider):
            formal_capable = True

        provider = IncompleteFormalProvider()
        state = w08.FoldState(
            training_id_hash=w08.canonical_id_hash(["S001"]), seed=1,
            metadata={"feature_sources": {}})
        with self.assertRaisesRegex(
                w08.W08ValidationError, "audit every required"):
            w08._validate_fold_provider_state(
                provider, state, ["S001"], w08.FOLD_SPECIFIC_FEATURES)

    def test_strict_candidate_pool_rejects_same_count_substitution(self):
        frame = synthetic_frame()
        for block in ("R_low", "R_high"):
            for column in list(frame.columns):
                if column.startswith(w08.RADIOMICS_PREFIXES[block]):
                    frame = frame.drop(columns=[column])
            for index, feature in enumerate(w08.FROZEN_CANDIDATE_FEATURES[block]):
                frame[w08.RADIOMICS_PREFIXES[block] + feature] = \
                    np.linspace(0.1 + index, 1.1 + index, len(frame))
        w08.validate_feature_schema(frame, models=["M3L"], strict=True)
        original = (w08.RADIOMICS_PREFIXES["R_low"] +
                    w08.FROZEN_CANDIDATE_FEATURES["R_low"][0])
        frame = frame.rename(columns={original: "R_low__same_count_spoof"})
        with self.assertRaisesRegex(
                w08.W08ValidationError, "candidate feature identity"):
            w08.validate_feature_schema(frame, models=["M3L"], strict=True)

    def test_numerical_nonconvergence_has_no_successful_old_coefficients(self):
        X = np.asarray([[0.0], [1.0], [2.0], [3.0]])
        time = np.asarray([1.0, 2.0, 3.0, 4.0])
        event = np.asarray([1, 0, 1, 0])
        model = w08.CoxElasticNetModel(
            alpha=0.5, penalty=0.01, max_iter=1, tolerance=1e-12)
        with self.assertRaises(w08.W08NumericalFailure):
            model.fit(X, time, event)
        self.assertIsNone(model.coef_)
        self.assertFalse(model.fit_audit["converged"])
        self.assertEqual(model.fit_audit["fit_status"], "non_converged")

    def test_cox_ph_nonconvergence_clears_state_and_blocks_prediction(self):
        X = np.asarray([[0.0], [1.0], [2.0], [3.0]])
        time = np.asarray([1.0, 2.0, 3.0, 4.0])
        event = np.asarray([1, 0, 1, 0])
        model = w08.CoxPHModel(max_iter=1, tolerance=1e-12)
        with self.assertRaises(w08.W08NumericalFailure) as raised:
            model.fit(X, time, event)
        self.assertIsNone(model.coef_)
        self.assertIsNone(model.baseline_times_)
        self.assertIsNone(model.baseline_survival_)
        self.assertFalse(model.fit_audit["converged"])
        self.assertEqual(model.fit_audit["fit_status"], "non_converged")
        self.assertEqual(model.fit_audit["failure_reason"],
                         "iteration_budget_exhausted")
        self.assertEqual(raised.exception.audit, model.fit_audit)
        with self.assertRaises(w08.W08ValidationError):
            model.predict_risk(X)
        with self.assertRaises(w08.W08ValidationError):
            model.predict_survival(X, {"horizon": 3.0})

    def test_cox_ph_converged_path_still_produces_predictions(self):
        rng = np.random.RandomState(0)
        X = rng.normal(size=(40, 3))
        time = np.arange(1.0, 41.0)
        event = np.asarray([1 if index % 3 == 0 else 0
                            for index in range(40)])
        model = w08.CoxPHModel(max_iter=250, tolerance=1e-7).fit(
            X, time, event)
        self.assertTrue(model.fit_audit["converged"])
        self.assertEqual(model.fit_audit["fit_status"], "converged")
        self.assertEqual(model.predict_risk(X).shape, (40,))
        self.assertEqual(model.predict_survival(
            X, {"horizon": 3.0})["horizon"].shape, (40,))

    def test_outer_model_rejects_nonconverged_fit_before_prediction(self):
        frame = synthetic_frame()

        def return_nonconverged(model, X, time, event):
            model.coef_ = np.ones(X.shape[1], dtype=float)
            model.baseline_times_ = np.asarray([1.0])
            model.baseline_survival_ = np.asarray([0.5])
            model.fit_audit = {
                "converged": False,
                "fit_status": "non_converged",
                "failure_reason": "forced_test_failure",
            }
            return model

        with mock.patch.object(w08.CoxPHModel, "fit",
                               new=return_nonconverged):
            for model_id in ("M0", "M1", "M2"):
                with self.assertRaises(w08.W08NumericalFailure) as raised:
                    w08._fit_outer_model(
                        frame.iloc[:30].reset_index(drop=True),
                        frame.iloc[30:].reset_index(drop=True),
                        model_id, inner_seed=22346, max_iter=1)
                self.assertEqual(raised.exception.audit["failure_reason"],
                                 "forced_test_failure")
                self.assertFalse(raised.exception.audit["converged"])
                self.assertEqual(raised.exception.audit["fit_status"],
                                 "non_converged")

    def test_no_qualified_candidate_returns_auditable_failure(self):
        frame = synthetic_frame(30).iloc[:30].reset_index(drop=True)
        frame["DFS_event"] = [1] * 15 + [0] * 15
        original_fit = w08.CoxElasticNetModel.fit

        def fail_fit(model, X, time, event):
            audit = {
                "converged": False,
                "fit_status": "non_converged",
                "stability_actions": ["forced_test_failure"],
                "linear_predictor_clipping": w08._new_clipping_audit(),
            }
            model.coef_ = None
            model.fit_audit = audit
            raise w08.W08NumericalFailure("forced numerical failure", audit=audit)

        try:
            with mock.patch.object(w08.CoxElasticNetModel, "fit", new=fail_fit):
                with self.assertRaises(w08.W08CandidateSelectionFailure) as raised:
                    w08.tune_elastic_net(
                        frame, "M3L", inner_seed=22346, lambda_count=1,
                        max_iter=1, tolerance=1e-6)
        finally:
            w08.CoxElasticNetModel.fit = original_fit
        self.assertEqual(raised.exception.audit["candidate_attempts"], 20)
        self.assertEqual(raised.exception.audit["candidate_failures"], 20)
        self.assertTrue(all(
            row["candidate_failed"]
            for row in raised.exception.audit["candidate_records"]))


if __name__ == "__main__":
    unittest.main()
