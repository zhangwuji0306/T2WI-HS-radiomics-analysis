import hashlib
import inspect
import json
import os
import subprocess
import sys
import tempfile
import textwrap
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

    def test_successful_fold_is_checkpointed_before_later_failure(self):
        frame = pd.DataFrame({
            "patient_id": ["S001", "S002", "S003", "S004"]})
        splits = pd.DataFrame({
            "patient_id": ["S001", "S002", "S003", "S004"],
            "repeat": [1, 1, 1, 1], "fold": [1, 1, 2, 2],
            "role": ["train", "validation", "train", "validation"],
            "seed": [12345, 12345, 12345, 12345],
        })
        progress = []

        def fake_worker(args):
            repeat, fold = args[-2]
            if int(fold) == 2:
                raise RuntimeError("synthetic second-fold failure")
            return self._result(int(repeat), int(fold))

        with tempfile.TemporaryDirectory() as root:
            checkpoint_path = w08._l5_checkpoint_path(root, 1, 1)

            def callback(**payload):
                progress.append(dict(payload))
                if payload.get("completed_outer_folds") == 1:
                    self.assertTrue(os.path.isfile(checkpoint_path))

            with mock.patch.object(w08, "_l5_worker_job",
                                   side_effect=fake_worker):
                with self.assertRaisesRegex(
                        RuntimeError, "synthetic second-fold failure"):
                    w08._l5_run_fold_coordinator(
                        frame, splits, object(), self._config(), self._runs(),
                        False, False, w08.LAMBDA_COUNT, 10, 1e-7, None, {},
                        "b" * 64, 1, root, "attempt_synthetic", "a" * 40,
                        False, progress_callback=callback)

            self.assertTrue(os.path.isfile(checkpoint_path))
            loaded = w08._l5_read_checkpoint(
                checkpoint_path, 1, 1, self._contract(), self._runs())
            self.assertEqual(loaded["outer_fold_key"], "repeat_1_fold_1")
            self.assertFalse(os.path.exists(w08._l5_checkpoint_path(root, 1, 2)))
            self.assertEqual([item["completed_outer_folds"] for item in progress], [1])

    def test_import_sets_actual_threadpool_limits_before_numpy(self):
        source = inspect.getsource(w08)
        self.assertLess(
            source.index("_l5_prepare_worker_environment()\n\nimport numpy"),
            source.index("import numpy"))
        child = textwrap.dedent(
            """
            import json
            import sys
            sys.path.insert(0, %r)
            import w08_nested_cv
            from threadpoolctl import threadpool_info
            info = [item for item in threadpool_info()
                    if item.get("num_threads") is not None]
            print(json.dumps(info, sort_keys=True))
            """ % SCRIPTS)
        output = subprocess.check_output(
            [sys.executable, "-c", child], cwd=TESTS_ROOT,
            universal_newlines=True, stderr=subprocess.STDOUT)
        info = json.loads(output.strip().splitlines()[-1])
        self.assertTrue(info)
        self.assertTrue(all(int(item["num_threads"]) == 1 for item in info))

    def test_r65_and_r65r_w08_bindings_match_current_files(self):
        project_root = os.path.abspath(os.path.join(TESTS_ROOT, ".."))
        config_path = os.path.join(
            project_root, "prognosis_analysis", "configs", "w08_nested_cv.json")
        source_path = os.path.join(
            project_root, "prognosis_analysis", "scripts", "w08_nested_cv.py")
        r65_path = os.path.join(
            project_root, "prognosis_analysis", "R6_5_numerical_equivalence.json")
        r65r_path = os.path.join(
            project_root, "prognosis_analysis", "R6_5R_coordinate_reconciliation.json")
        coordinate_audit_path = os.path.join(
            project_root, "prognosis_analysis",
            "R6_5R_coordinate_reconciliation_audit.md")
        source_binding_audit_path = os.path.join(
            project_root, "prognosis_analysis",
            "R6_5R_w08_source_binding_refresh_audit.md")

        def sha256(path):
            digest = hashlib.sha256()
            with open(path, "rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            return digest.hexdigest()

        with open(r65_path, "r", encoding="utf-8") as handle:
            r65 = json.load(handle)
        with open(r65r_path, "r", encoding="utf-8") as handle:
            r65r = json.load(handle)
        config_hash = sha256(config_path)
        source_hash = sha256(source_path)
        self.assertEqual(r65["protocol_bindings"]["w08_config_sha256"],
                         config_hash)
        self.assertEqual(r65["protocol_bindings"]["w08_solver_source_sha256"],
                         source_hash)
        self.assertEqual(r65r["provenance"]["file_sha256"][
            "prognosis_analysis/configs/w08_nested_cv.json"], config_hash)
        self.assertEqual(r65r["provenance"]["file_sha256"][
            "prognosis_analysis/scripts/w08_nested_cv.py"], source_hash)
        self.assertEqual(
            r65["coordinate_binding"]["registered_evidence_hashes"][
                "R6_5R_coordinate_reconciliation_json"], sha256(r65r_path))
        self.assertEqual(
            r65["coordinate_binding"]["registered_evidence_hashes"][
                "R6_5R_coordinate_reconciliation_audit_md"],
            sha256(coordinate_audit_path))
        self.assertNotEqual(
            sha256(coordinate_audit_path), sha256(source_binding_audit_path))

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
