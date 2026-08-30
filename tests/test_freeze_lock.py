import json
import os
import sys
import tempfile
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "habitat_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from freeze_lock import atomic_write_json, validate_freeze_lock  # noqa: E402


def valid_payload():
    return {
        "bootstrap_mode": "formal", "bootstrap_requested": 1000,
        "bootstrap_completed": 1000, "bootstrap_completion_status": "complete",
        "bootstrap_operational_pass": 1, "formal_eligible": 1,
        "outcome_columns_read": False, "B_data_read": False,
        "config_hash": "abc", "A393_id_hash": "ids",
    }


class FreezeLockTests(unittest.TestCase):
    def test_smoke_cannot_produce_valid_lock(self):
        payload = valid_payload()
        payload.update(bootstrap_mode="smoke", bootstrap_requested=20,
                       bootstrap_completed=20, formal_eligible=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lock.json")
            atomic_write_json(path, payload)
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(path)

    def test_preflight_cannot_produce_valid_lock(self):
        payload = valid_payload()
        payload.update(bootstrap_mode="preflight", bootstrap_requested=200,
                       bootstrap_completed=200, formal_eligible=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lock.json")
            atomic_write_json(path, payload)
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(path)

    def test_formal_incomplete_rejected(self):
        payload = valid_payload()
        payload.update(bootstrap_completed=999, bootstrap_completion_status="partial",
                       formal_eligible=0)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lock.json")
            atomic_write_json(path, payload)
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(path)

    def test_current_inputs_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "lock.json")
            atomic_write_json(path, valid_payload())
            self.assertEqual(validate_freeze_lock(path, {"config_hash": "abc"})["A393_id_hash"], "ids")
            with self.assertRaises(RuntimeError):
                validate_freeze_lock(path, {"config_hash": "changed"})


if __name__ == "__main__":
    unittest.main()
