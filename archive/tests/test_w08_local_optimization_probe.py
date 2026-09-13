import json
import inspect
import os
import sys
import tempfile
import unittest
from unittest import mock


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_local_optimization_probe as probe  # noqa: E402
import w08_nested_cv as w08  # noqa: E402
from w08_kmeans_parameters import KMEANS_PARAMETERS  # noqa: E402


class W08LocalOptimizationProbeTests(unittest.TestCase):
    def test_frozen_bindings_are_explicit(self):
        self.assertEqual(KMEANS_PARAMETERS.n_init, 100)
        self.assertEqual(w08.LAMBDA_COUNT, 100)
        self.assertEqual(len(w08.ALPHA_GRID), 4)
        self.assertEqual(w08.ELASTIC_NET_MAX_ITER, 3000)
        self.assertEqual(w08.ELASTIC_NET_TOLERANCE, 1e-7)
        self.assertEqual(probe.STAGE_NAMES[-1], "uno_weights_and_bottom_call")

    def test_aggregate_safety_rejects_patient_or_endpoint_fields(self):
        payload = {"safety": dict((key, False) for key in probe.B_ACCESS_FLAGS)}
        payload["safety"]["formal_writer_invoked"] = False
        payload["patient_id"] = "synthetic-only-for-test"
        with self.assertRaises(probe.ProbeFailure):
            probe._validate_aggregate_safety(payload)

    def test_failed_probe_records_stage_counts_and_does_not_succeed(self):
        with tempfile.TemporaryDirectory() as temp:
            original = probe._single_iteration

            def failed_iteration(_temp_root):
                return [{"ok": False, "stage": stage,
                         "error_class": "SyntheticFailure"}
                        for stage in probe.STAGE_NAMES]

            try:
                probe._single_iteration = failed_iteration
                with self.assertRaises(probe.ProbeFailure):
                    probe.run_probe(temp, repeats=3, technical_inputs=False)
                with open(os.path.join(temp, probe.OUTPUT_NAME),
                          "r", encoding="utf-8") as handle:
                    summary = json.load(handle)
                self.assertEqual(summary["status"], "failed")
                self.assertEqual(summary["failure_stage_counts"][
                    "slic_cache_prepare_validate"], 3)
                self.assertNotIn("patient_id", json.dumps(summary))
            finally:
                probe._single_iteration = original

    def test_real_a_loader_calls_technical_boundary_without_outcome_columns(self):
        identifiers = {"synthetic-a-1", "synthetic-a-2"}
        metadata = probe.pd.DataFrame({
            "影像号": sorted(identifiers),
            "technical_cohort": ["A393", "A393"],
            "modeling_eligible": [1, 1],
        })
        features = probe.pd.DataFrame({
            "影像号": sorted(identifiers),
            "读者": ["R1", "R1"],
            "split": ["A", "A"],
        })
        supervoxels = probe.pd.DataFrame({
            "影像号": sorted(identifiers),
            "reader": ["R1", "R1"],
            "sv_label": [0, 0],
            "n_tumor_voxels": [10, 10],
            "Mean": [0.0, 0.0],
        })
        calls = []

        def technical_reader(path, **kwargs):
            calls.append((path, kwargs))
            usecols = set(kwargs.get("usecols", ()))
            self.assertFalse(usecols & {"DFS_time", "DFS_event"})
            if path == probe.formal.W06_POPULATION:
                return metadata.copy()
            return features.copy()

        with mock.patch.object(probe.formal, "read_technical_A",
                               side_effect=technical_reader), \
                mock.patch.object(
                    probe.formal.technical_preflight,
                    "_read_authorized_a_supervoxels",
                    return_value=supervoxels):
            context = probe._load_real_a_technical_inputs()

        self.assertEqual(len(calls), 2)
        self.assertEqual(context["input_metrics"], {
            "sample_count": 2,
            "successful_count": 2,
            "failure_count": 0,
        })

    def test_real_cache_probe_reports_hit_miss_and_validation_counters(self):
        with tempfile.TemporaryDirectory() as temp:
            existing = os.path.join(temp, "existing")
            os.makedirs(existing)
            npz_path = os.path.join(existing, "synthetic-a-1.npz")
            probe.np.savez_compressed(
                npz_path, labels=probe.np.ones((2, 2), dtype="int32"),
                roi=probe.np.ones((2, 2), dtype="uint8"))
            context = {
                "technical_ids": {"synthetic-a-1"},
                "supervoxels": probe.pd.DataFrame(),
            }

            class FakeProvider(object):
                def __init__(self, root):
                    self.root = root

                def _cache_path(self, identifier):
                    return os.path.join(self.root, identifier + ".npz")

                def _prepare_case(self, identifier):
                    path = self._cache_path(identifier)
                    if not os.path.isfile(path):
                        os.makedirs(self.root, exist_ok=True)
                        probe.np.savez_compressed(
                            path, labels=probe.np.ones((2, 2), dtype="int32"),
                            roi=probe.np.ones((2, 2), dtype="uint8"))
                        return
                    with probe.np.load(path) as cached:
                        if not bool(cached["roi"].flat[0]):
                            labels = cached["labels"].copy()
                            roi = probe.np.ones((2, 2), dtype="uint8")
                        else:
                            labels = None
                            roi = None
                    if labels is not None:
                        probe.np.savez_compressed(path, labels=labels, roi=roi)

            with mock.patch.object(probe, "_existing_slic_cache_root",
                                   return_value=existing), \
                    mock.patch.object(
                        probe, "_make_real_cache_provider",
                        side_effect=lambda _context, root: FakeProvider(root)):
                counters = probe._real_slic_cache_probe(context, temp)

        self.assertEqual(counters["hit_count"], 1)
        self.assertEqual(counters["miss_count"], 1)
        self.assertEqual(counters["validation_failure_count"], 1)
        self.assertEqual(counters["recomputed_count"], 2)

    def test_stale_complete_is_replaced_on_initialization_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            with open(os.path.join(temp, probe.OUTPUT_NAME), "w",
                      encoding="utf-8") as handle:
                json.dump({"status": "complete", "patient_id": "stale"},
                          handle)
            original = probe._make_synthetic_image
            try:
                probe._make_synthetic_image = mock.Mock(
                    side_effect=RuntimeError("secret absolute path"))
                with self.assertRaises(probe.ProbeFailure):
                    probe.run_probe(temp, repeats=3, technical_inputs=False)
            finally:
                probe._make_synthetic_image = original
            with open(os.path.join(temp, probe.OUTPUT_NAME),
                      "r", encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["failed_stage"], "initialization")
            self.assertEqual(summary["failure_stage_counts"]["initialization"], 3)
            self.assertNotIn("secret absolute path", json.dumps(summary))
            self.assertNotIn("patient_id", json.dumps(summary))

    def test_resource_sampling_failure_is_observable_and_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch.object(
                    probe, "resource_snapshot",
                    side_effect=RuntimeError("sampling path")):
                with self.assertRaises(probe.ProbeFailure):
                    probe.run_probe(temp, repeats=3, technical_inputs=False)
            with open(os.path.join(temp, probe.OUTPUT_NAME),
                      "r", encoding="utf-8") as handle:
                summary = json.load(handle)
            self.assertEqual(summary["status"], "failed")
            self.assertEqual(summary["failed_stage"], "a_input_load")
            self.assertEqual(summary["failure_stage_counts"]["a_input_load"], 3)

    def test_iteration_exception_is_observable_and_clean_success_can_follow(self):
        with tempfile.TemporaryDirectory() as temp:
            original = probe._single_iteration
            try:
                probe._single_iteration = mock.Mock(
                    side_effect=RuntimeError("iteration path"))
                with self.assertRaises(probe.ProbeFailure):
                    probe.run_probe(temp, repeats=3, technical_inputs=False)
                with open(os.path.join(temp, probe.OUTPUT_NAME),
                          "r", encoding="utf-8") as handle:
                    failed = json.load(handle)
                self.assertEqual(failed["status"], "failed")
                self.assertEqual(failed["failed_stage"], "iteration")

                good_record = {
                    "ok": True,
                    "stage": probe.STAGE_NAMES[0],
                    "seconds": 0.001,
                    "cpu_percent": 1.0,
                    "rss_bytes": 1,
                    "read_bytes": 0,
                    "write_bytes": 0,
                }
                probe._single_iteration = mock.Mock(
                    return_value=[dict(good_record, stage=stage)
                                  for stage in probe.STAGE_NAMES])
                summary = probe.run_probe(temp, repeats=3,
                                          technical_inputs=False)
            finally:
                probe._single_iteration = original
            self.assertEqual(summary["status"], "complete")
            self.assertEqual(summary["failure_stage_counts"], {})
            self.assertNotIn("failed_stage", summary)

    def test_resource_snapshot_has_required_aggregate_counters(self):
        snapshot = probe.resource_snapshot()
        self.assertTrue(set(("rss_bytes", "read_bytes", "write_bytes")) <=
                        set(snapshot))
        self.assertGreaterEqual(snapshot["rss_bytes"], 0)

    def test_safety_flags_are_closed_false(self):
        self.assertEqual(set(probe.B_ACCESS_FLAGS), {
            "B_data_read", "B_reader_invoked", "B_source_opened",
            "B_statistics_generated"})

    def test_synthetic_iteration_covers_every_required_stage(self):
        with tempfile.TemporaryDirectory() as temp:
            records = probe._single_iteration(temp)
        self.assertEqual([record["stage"] for record in records],
                         list(probe.STAGE_NAMES))
        self.assertTrue(all(record.get("ok") for record in records))

    def test_probe_source_has_no_formal_writer_call(self):
        source = inspect.getsource(probe)
        self.assertNotIn("formal.formal(", source)
        self.assertNotIn("formal.write_results(", source)


if __name__ == "__main__":
    unittest.main()
