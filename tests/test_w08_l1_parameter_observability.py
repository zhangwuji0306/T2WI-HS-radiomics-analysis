import json
import os
import re
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

import w08_formal_run_a as formal  # noqa: E402
import w08_kmeans_parameters as parameters  # noqa: E402
import w08_nested_cv as nested  # noqa: E402
import w08_technical_preflight_a as preflight  # noqa: E402
import w07_outer_splits as w07  # noqa: E402


class W08L1ParameterObservabilityTests(unittest.TestCase):
    def test_all_three_entries_share_complete_frozen_parameter_object(self):
        expected = {
            "algorithm": "kmeans",
            "k": 2,
            "initialization": "k-means++",
            "n_init": 100,
            "max_iter": 300,
            "tol": 1e-4,
        }
        self.assertEqual(parameters.KMEANS_PARAMETERS.as_dict(), expected)
        self.assertIs(nested.KMEANS_PARAMETERS, parameters.KMEANS_PARAMETERS)
        self.assertIs(formal.KMEANS_PARAMETERS, parameters.KMEANS_PARAMETERS)
        self.assertIs(preflight.KMEANS_PARAMETERS, parameters.KMEANS_PARAMETERS)
        self.assertEqual(parameters.KMEANS_PARAMETERS.sklearn_kwargs(), {
            "n_clusters": 2,
            "init": "k-means++",
            "n_init": 100,
            "max_iter": 300,
            "tol": 1e-4,
        })

    def test_frozen_config_missing_type_or_value_fails_closed(self):
        with open(parameters.DEFAULT_HABITAT_CONFIG, "r", encoding="utf-8") as handle:
            source = json.load(handle)
        cases = {
            "missing": lambda value: value["clustering"].pop("tol"),
            "type": lambda value: value["clustering"].__setitem__("n_init", "100"),
            "algorithm": lambda value: value["clustering"].__setitem__("algorithm", "mini_batch_kmeans"),
            "k": lambda value: value["clustering"].__setitem__("k", 3),
            "initialization": lambda value: value["clustering"].__setitem__("initialization", "random"),
            "n_init": lambda value: value["clustering"].__setitem__("n_init", 10),
            "max_iter": lambda value: value["clustering"].__setitem__("max_iter", 301),
            "tol": lambda value: value["clustering"].__setitem__("tol", 1e-3),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp:
                path = os.path.join(temp, "config.json")
                payload = json.loads(json.dumps(source))
                mutate(payload)
                with open(path, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                with self.assertRaises(RuntimeError):
                    parameters.load_frozen_kmeans_parameters(path)

    def test_current_w08_production_sources_have_no_n_init_10(self):
        paths = (
            "w08_kmeans_parameters.py", "w08_formal_run_a.py",
            "w08_nested_cv.py", "w08_technical_preflight_a.py",
        )
        for name in paths:
            with self.subTest(name=name):
                path = os.path.join(SCRIPTS, name)
                with open(path, "r", encoding="utf-8") as handle:
                    source = handle.read()
                self.assertIsNone(re.search(r"n_init\s*=\s*10", source))

    def test_progress_schema_is_closed_and_b_flags_are_forced_false(self):
        with tempfile.TemporaryDirectory() as temp:
            progress = formal._write_progress(temp, 100.0, {
                "status": "running",
                "current_repeat": 1,
                "current_fold": 2,
                "current_run": "M0",
                "completed_outer_folds": 1,
                "total_outer_folds": 50,
                "completed_runs_in_fold": 3,
                "total_runs_in_fold": 13,
                "B_data_read": True,
                "B_reader_invoked": True,
                "B_source_opened": True,
                "B_statistics_generated": True,
            })
            self.assertEqual(set(progress), formal.W08_PROGRESS_ALLOWED_KEYS)
            for key in formal.B_ACCESS_FLAGS:
                self.assertFalse(progress[key])
            for forbidden in ("patient_id", "risk_score", "c_index", "performance_generated"):
                with self.subTest(forbidden=forbidden):
                    with self.assertRaises(ValueError):
                        formal._write_progress(temp, 100.0, {forbidden: "blocked"})
            with self.assertRaises(ValueError):
                formal._write_progress(temp, 100.0, {"formal_run": True})

    def test_progress_uses_atomic_replace_and_leaves_no_temp_file(self):
        with tempfile.TemporaryDirectory() as temp:
            replace = os.replace
            with mock.patch.object(formal.os, "replace", wraps=replace) as replaced:
                formal._write_progress(temp, 100.0, {"status": "running"})
            self.assertTrue(replaced.called)
            temporary, destination = replaced.call_args[0][:2]
            self.assertTrue(temporary.endswith("progress.json.tmp"))
            self.assertEqual(destination, os.path.join(temp, "progress.json"))
            self.assertFalse(os.path.exists(os.path.join(temp, "progress.json.tmp")))

    def test_callback_exception_does_not_change_in_memory_result(self):
        frame = _synthetic_clinical_frame()
        population = frame[["patient_id", "DFS_event"]].copy()
        config = json.loads(json.dumps(w07._read_json(w07.DEFAULT_CONFIG)))
        splits = w07.build_outer_splits(population, config)
        provider_a = nested.FrameFoldFeatureProvider(frame)
        provider_b = nested.FrameFoldFeatureProvider(frame)

        def failing_callback(_payload):
            raise RuntimeError("observer failure")

        expected = nested.run_w08_in_memory(
            frame, splits, provider_a, config=nested.load_config(), models=["M0"],
            strict_schema=False, max_outer_folds=1, solver_max_iter=60)
        actual = nested.run_w08_in_memory(
            frame, splits, provider_b, config=nested.load_config(), models=["M0"],
            strict_schema=False, max_outer_folds=1, solver_max_iter=60,
            progress_callback=failing_callback)
        for key in ("fold_results", "selection_results", "predictions"):
            pd.testing.assert_frame_equal(
                actual[key].sort_index(axis=1), expected[key].sort_index(axis=1),
                check_dtype=False)


def _synthetic_clinical_frame(n=50):
    indices = np.arange(n)
    frame = pd.DataFrame({
        "patient_id": ["L1-%03d" % index for index in indices],
        "DFS_time": indices.astype(float) + 2.0,
        "DFS_event": [1 if index < n // 2 else 0 for index in indices],
        "split": ["A"] * n,
        "technical_cohort": ["A393"] * n,
        "年龄": np.linspace(40.0, 75.0, n),
        "CEA_log": np.log1p(np.linspace(1.0, 20.0, n)),
        "mrT_4级": [1 + index % 4 for index in indices],
        "mrN_3级": [index % 4 for index in indices],
        "MRF": [index % 2 for index in indices],
        "mrEMVI": [(index + 1) % 2 for index in indices],
        "thickness": np.linspace(3.0, 12.0, n),
        "EID": np.linspace(0.5, 5.0, n),
        "活检病理非腺癌": [index % 2 for index in indices],
    })
    rng = np.random.RandomState(2026)
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
    return frame
