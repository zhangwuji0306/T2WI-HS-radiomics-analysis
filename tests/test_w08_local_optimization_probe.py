import json
import inspect
import os
import sys
import tempfile
import unittest


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
                    probe.run_probe(temp, repeats=3)
                with open(os.path.join(temp, probe.OUTPUT_NAME),
                          "r", encoding="utf-8") as handle:
                    summary = json.load(handle)
                self.assertEqual(summary["status"], "failed")
                self.assertEqual(summary["failure_stage_counts"][
                    "slic_cache_prepare_validate"], 3)
                self.assertNotIn("patient_id", json.dumps(summary))
            finally:
                probe._single_iteration = original

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
