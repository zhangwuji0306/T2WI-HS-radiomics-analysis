import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import pandas as pd


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)
if TESTS_ROOT not in sys.path:
    sys.path.insert(0, TESTS_ROOT)

import w08_nested_cv as w08  # noqa: E402
from test_w08_nested_cv import (  # noqa: E402
    convergent_synthetic_frame, synthetic_splits)


class W08L5CheckpointTests(unittest.TestCase):
    def _config(self):
        return w08.load_config()

    def _runs(self):
        return [{"run_id": "M0", "model_id": "M0", "population": "main"}]

    def _contract(self):
        return w08._l5_checkpoint_contract(
            "attempt_synthetic", "a" * 40, "b" * 64,
            self._runs(), self._config())

    def _result(self, repeat=1, fold=1):
        row = {
            "run_id": "M0", "model_id": "M0", "population": "main",
            "repeat": repeat, "fold": fold, "coverage": {"source": "synthetic"},
            "candidate_attempts": 0, "candidate_failures": 0,
            "stability_actions": [],
            "linear_predictor_clipping": {"count": 0},
        }
        return {
            "predictions": pd.DataFrame([]),
            "fold_results": pd.DataFrame([row]),
            "selection_results": pd.DataFrame([dict(row)]),
            "audit": {},
        }

    def test_checkpoint_round_trip_and_tamper_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            path = w08._l5_write_checkpoint(
                root, 1, 1, self._result(), self._contract())
            self.assertTrue(os.path.isfile(path))
            loaded = w08._l5_read_checkpoint(
                path, 1, 1, self._contract(), self._runs())
            self.assertEqual(loaded["status"], "complete")
            with open(path, "r", encoding="utf-8") as handle:
                tampered = json.load(handle)
            tampered["result"]["fold_results"][0]["fold"] = 2
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(tampered, handle)
            with self.assertRaises(w08.W08ValidationError):
                w08._l5_read_checkpoint(
                    path, 1, 1, self._contract(), self._runs())

    def test_coordinator_resumes_only_valid_completed_fold(self):
        frame = pd.DataFrame({"patient_id": ["S001", "S002"]})
        splits = pd.DataFrame({
            "patient_id": ["S001", "S002"],
            "repeat": [1, 1], "fold": [1, 1],
            "role": ["train", "validation"], "seed": [12345, 12345],
        })
        runs = self._runs()

        def fake_worker(args):
            return self._result(*args[-2])

        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(w08, "_l5_worker_job",
                                   side_effect=fake_worker) as worker:
                first = w08._l5_run_fold_coordinator(
                    frame, splits, object(), self._config(), runs, False, False,
                    w08.LAMBDA_COUNT, 10, 1e-7, None, {}, "b" * 64, 1,
                    root, "attempt_synthetic", "a" * 40, False)
                self.assertEqual(len(first["fold_results"]), 1)
                self.assertEqual(worker.call_count, 1)
                worker.reset_mock()
                with self.assertRaisesRegex(
                        w08.W08ValidationError, "explicit resume"):
                    w08._l5_run_fold_coordinator(
                        frame, splits, object(), self._config(), runs, False, False,
                        w08.LAMBDA_COUNT, 10, 1e-7, None, {}, "b" * 64, 1,
                        root, "attempt_synthetic", "a" * 40, False)
                resumed = w08._l5_run_fold_coordinator(
                    frame, splits, object(), self._config(), runs, False, False,
                    w08.LAMBDA_COUNT, 10, 1e-7, None, {}, "b" * 64, 1,
                    root, "attempt_synthetic", "a" * 40, True)
                self.assertEqual(len(resumed["fold_results"]), 1)
                self.assertEqual(worker.call_count, 0)
                self.assertEqual(
                    resumed["audit"]["L5_execution"]["resumed_checkpoints"], 1)

    def test_worker_failure_leaves_no_completed_checkpoint(self):
        frame = pd.DataFrame({"patient_id": ["S001", "S002"]})
        splits = pd.DataFrame({
            "patient_id": ["S001", "S002"],
            "repeat": [1, 1], "fold": [1, 1],
            "role": ["train", "validation"], "seed": [12345, 12345],
        })
        with tempfile.TemporaryDirectory() as root:
            with mock.patch.object(
                    w08, "_l5_worker_job",
                    side_effect=RuntimeError("synthetic worker failure")):
                with self.assertRaisesRegex(RuntimeError, "synthetic worker failure"):
                    w08._l5_run_fold_coordinator(
                        frame, splits, object(), self._config(), self._runs(),
                        False, False, w08.LAMBDA_COUNT, 10, 1e-7, None, {},
                        "b" * 64, 1, root, "attempt_synthetic", "a" * 40,
                        False)
            self.assertFalse(os.path.exists(
                w08._l5_checkpoint_path(root, 1, 1)))
            self.assertFalse(any(name.endswith(".tmp")
                                 for _, _, names in os.walk(root)
                                 for name in names))

    def test_two_process_workers_match_serial_for_two_synthetic_folds(self):
        frame = convergent_synthetic_frame()
        _, splits = synthetic_splits(frame)
        serial_provider = w08.FrameFoldFeatureProvider(frame)
        parallel_provider = w08.FrameFoldFeatureProvider(frame)
        serial = w08.run_w08_in_memory(
            frame, splits, serial_provider, config=self._config(),
            models=["M0"], strict_schema=False, max_outer_folds=2,
            outer_fold_workers=1, solver_max_iter=60)
        parallel = w08.run_w08_in_memory(
            frame, splits, parallel_provider, config=self._config(),
            models=["M0"], strict_schema=False, max_outer_folds=2,
            outer_fold_workers=2, solver_max_iter=60)
        for name in ("predictions", "fold_results", "selection_results"):
            left = serial[name].reset_index(drop=True)
            right = parallel[name].reset_index(drop=True)
            pd.testing.assert_frame_equal(left, right, check_dtype=False,
                                          check_exact=False, rtol=1e-12,
                                          atol=1e-12)


if __name__ == "__main__":
    unittest.main()
