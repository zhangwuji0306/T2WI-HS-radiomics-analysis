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

import w08_formal_run_a as formal  # noqa: E402
import w08_nested_cv as w08  # noqa: E402


class W08FormalSerialContractTests(unittest.TestCase):
    def test_locked_config_records_effective_serial_formal_setting(self):
        config_path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "prognosis_analysis", "configs",
            "w08_nested_cv.json"))
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        execution = config["execution"]
        self.assertEqual(execution["historical_requested_outer_fold_workers"], 2)
        self.assertEqual(execution["outer_fold_workers"], 1)
        self.assertEqual(execution["formal_effective_outer_fold_workers"], 1)
        self.assertFalse(execution["complex_cache_and_parallel_enabled"])
        self.assertEqual(w08._validate_config(config), config)

    def test_formal_in_memory_rejects_non_effective_worker_setting(self):
        for workers in (2, 4):
            with self.subTest(workers=workers):
                with self.assertRaises(w08.W08ValidationError):
                    w08.run_w08_in_memory(
                        None, None, None, require_fixed_hash=True,
                        outer_fold_workers=workers)

    def test_formal_worker_does_not_initialise_worker_cache_root(self):
        cache_root = os.path.join(tempfile.gettempdir(),
                                   "w08-formal-worker-cache-must-not-exist")
        if os.path.exists(cache_root):
            self.fail("test cache root already exists: %s" % cache_root)
        provider = mock.Mock()
        provider._cache_root = cache_root
        provider._complex_cache_enabled = True
        with mock.patch.object(w08, "run_w08_in_memory",
                               return_value="worker-result") as runner:
            result = w08._l5_worker_job((
                None, None, provider, None, (), False, True,
                w08.LAMBDA_COUNT, 1, 1e-7, None, (1, 1), cache_root))
        self.assertEqual(result, "worker-result")
        self.assertFalse(os.path.exists(cache_root))
        runner.assert_called_once()
        self.assertFalse(runner.call_args[1]["complex_layer_enabled"])

    def test_formal_entry_uses_serial_contract_and_disables_complex_layer(self):
        self.assertEqual(w08.FORMAL_EFFECTIVE_OUTER_FOLD_WORKERS, 1)
        self.assertFalse(w08.FORMAL_COMPLEX_LAYER_ENABLED)
        source = inspect.getsource(formal.formal)
        self.assertIn("enable_complex_cache=False", source)
        self.assertIn("FORMAL_EFFECTIVE_OUTER_FOLD_WORKERS", source)


if __name__ == "__main__":
    unittest.main()
