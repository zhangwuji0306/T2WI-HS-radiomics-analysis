import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MANIFEST_PATH = os.path.join(
    ROOT, "prognosis_analysis", "W07A_pre_W08_provenance_reconciliation.json")
SCRIPT_ROOT = os.path.join(ROOT, "prognosis_analysis", "scripts")
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

from provenance_reconciliation import (  # noqa: E402
    ProvenanceReconciliationError,
    _normalize_lf_bytes,
    _validate_revision_content,
    _validate_successor_content,
    validate_execution_status,
    validate_manifest,
)


class ProvenanceReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(MANIFEST_PATH, encoding="utf-8") as handle:
            cls.manifest = json.load(handle)

    def _validate_modified_manifest(self, mutate):
        manifest = copy.deepcopy(self.manifest)
        mutate(manifest)
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "manifest.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(manifest, handle, ensure_ascii=False, indent=2)
            with self.assertRaises(ProvenanceReconciliationError):
                validate_manifest(root=ROOT, manifest_path=path)

    def test_manifest_and_approved_successors_validate(self):
        result = validate_manifest(root=ROOT, manifest_path=MANIFEST_PATH)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["historical_recovery"]
                        ["w04_taskbook_exact_verification"])
        self.assertTrue(result["historical_recovery"]
                        ["w04_workflow_archive_exact_verification"])
        self.assertFalse(result["historical_recovery"]
                         ["w07a_workflow_exact_verification"])

    def test_w04_taskbook_git_object_and_successor_are_bound(self):
        item = self.manifest["reconciliations"]["w04_taskbook"]
        snapshot = item["historical_exact_recovery"]
        self.assertEqual(snapshot["git_commit"],
                         "78b0e8f48becd64413859027e8809e155ecded5e")
        self.assertEqual(snapshot["git_blob"],
                         "8a89c12b621b2560202902df3477aaa11acd0a5c")
        self.assertEqual(snapshot["verification_sha256"],
                         item["source_binding"]["sha256"])
        self.assertEqual(item["current_successor_id"],
                         "scientific_master_protocol")
        self.assertTrue(self.manifest["approved_successors"]
                        ["scientific_master_protocol"]["approved_successor"])
        validate_manifest(root=ROOT, manifest_path=MANIFEST_PATH)

    def test_w04_archive_path_migration_is_registered(self):
        item = self.manifest["reconciliations"]["w04_workflow_path_migration"]
        archive = item["archive_exact_recovery"]
        migration = item["migration"]
        self.assertEqual(archive["git_path"], migration["to_archive_path"])
        self.assertEqual(archive["verification_sha256"],
                         item["source_binding"]["sha256"])
        self.assertEqual(migration["rename_similarity"], "100%")
        self.assertEqual(item["current_successor_id"], "pre_w08_sop")
        validate_manifest(root=ROOT, manifest_path=MANIFEST_PATH)

    def test_w07a_unrecoverable_exception_is_explicit_and_not_exact_pass(self):
        item = self.manifest["reconciliations"]["w07a_workflow"]
        recovery = item["historical_exact_recovery"]
        exception = item["exception"]
        self.assertEqual(recovery["status"],
                         "historical_source_snapshot_unrecoverable")
        self.assertIsNone(recovery["git_commit"])
        self.assertFalse(recovery["exact_verification"])
        self.assertTrue(exception["required"])
        self.assertFalse(exception["exact_verification"])
        self.assertFalse(exception["byte_exact_pass"])
        validate_manifest(root=ROOT, manifest_path=MANIFEST_PATH)

    def test_missing_w07a_exception_fails_closed(self):
        def remove_exception(manifest):
            del manifest["reconciliations"]["w07a_workflow"]["exception"]

        self._validate_modified_manifest(remove_exception)

    def test_forged_w07a_exact_pass_fails_closed(self):
        def forge_exception(manifest):
            exception = manifest["reconciliations"]["w07a_workflow"]["exception"]
            exception["exact_verification"] = True
            exception["byte_exact_pass"] = True

        self._validate_modified_manifest(forge_exception)

    def test_w07a_byte_exact_refreeze_relationship_fails_closed(self):
        def forge_relationship(manifest):
            manifest["reconciliations"]["w07a_workflow"]["relationship"] = (
                "W07A byte-exact PASS and refreeze is approved.")

        self._validate_modified_manifest(forge_relationship)

    def test_w04_outcome_performance_protocol_change_conclusion_fails_closed(self):
        def forge_conclusion(manifest):
            manifest["reconciliations"]["w04_taskbook"]["semantic_review"][
                "conclusion"] = "Outcome/performance changed the protocol."

        self._validate_modified_manifest(forge_conclusion)

    def test_modified_successor_sha_fails_closed(self):
        def modify_successor(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["sha256"] = "0" * 64

        self._validate_modified_manifest(modify_successor)

    def test_previous_successor_revision_is_preserved_and_current_revision_is_registered(self):
        successor = self.manifest["approved_successors"]["pre_w08_sop"]
        self.assertEqual(successor["git_commit"],
                         "54e1b2ad75949bcdc06ee9dffd8138ea63654c69")
        self.assertEqual(successor["git_blob"],
                         "4f769bf481166eeced760e4946a9c4e4db6ccda4")
        self.assertEqual(successor["sha256"],
                         "b1d40dd24f586ba52c5832d1dc53761d5239699d25a76856b7abeac636f47c03")
        self.assertEqual(successor["git_snapshot_sha256"],
                         "85d03d86d3551ef8505234f3172482bc337b6c650c129724ae55adc31b6e6fc9")
        history = self.manifest["successor_revision_history"]["pre_w08_sop"]
        self.assertEqual(history[0]["status"], "historical")
        self.assertEqual(history[0]["git_blob"], successor["git_blob"])
        current = history[1]
        self.assertEqual(current["status"], "current")
        self.assertEqual(current["content_introducing_commit"],
                         "c35385265d08f77aa8d7bc5b2903c4bc0236e917")
        self.assertEqual(current["git_blob"],
                         "26bd8bff6cfd9a0bdc057099009cedb581d6f41d")
        self.assertNotEqual(current["content_introducing_commit"],
                            current["reviewed_repository_head"])

    def test_execution_status_is_the_failed_w08_hold_state(self):
        status = validate_execution_status(root=ROOT)
        self.assertEqual(status["execution"]["stage"], "W08")
        self.assertEqual(status["execution"]["gate"], "HOLD")
        self.assertTrue(status["execution"]["formal_w08_started"])
        self.assertEqual(status["last_attempt"]["status"], "failed")
        self.assertIn("minimum ROI", status["last_attempt"]["failure_reason_summary"])
        self.assertEqual(status["b_access"], {
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
        })
        self.assertFalse(status["model_freeze_lock"]["present"])
        self.assertFalse(status["outputs"]["final_outputs_generated"])

    def test_content_introducing_commit_is_distinct_from_later_review_head(self):
        revision = self.manifest["successor_revision_history"]["pre_w08_sop"][1]
        later_head = subprocess.check_output(
            ["git", "-C", ROOT, "rev-parse", "HEAD"]).decode("ascii").strip()
        self.assertNotEqual(revision["content_introducing_commit"], later_head)
        self.assertNotEqual(revision["reviewed_repository_head"],
                            revision["content_introducing_commit"])
        validate_manifest(root=ROOT, manifest_path=MANIFEST_PATH)

    def test_current_successor_path_commit_blob_and_raw_sha_mismatch_fail_closed(self):
        fields = ("path", "content_introducing_commit", "git_blob", "raw_sha256")
        mutations = {
            "path": "prognosis_analysis/W07A_pre_W08_protocol_amendment.md",
            "content_introducing_commit": "54e1b2ad75949bcdc06ee9dffd8138ea63654c69",
            "git_blob": "0" * 40,
            "raw_sha256": "0" * 64,
        }
        for field in fields:
            def mutate(manifest, field=field):
                manifest["successor_revision_history"]["pre_w08_sop"][1][field] = mutations[field]
            self._validate_modified_manifest(mutate)

    def test_current_successor_lf_crlf_compatibility_is_strict(self):
        revision = self.manifest["successor_revision_history"]["pre_w08_sop"][1]
        import provenance_reconciliation as reconciliation

        committed = reconciliation._git_blob_bytes(
            ROOT, revision["content_introducing_commit"], revision["path"])
        variants = (
            committed,
            committed.replace(b"\n", b"\r\n"),
            committed.replace(b"\n", b"\r\n", 1),
        )
        for current in variants:
            errors = []
            _validate_revision_content(current, committed, revision,
                                       "test", errors)
            self.assertEqual(errors, [])

    def test_current_successor_one_character_whitespace_title_and_paragraph_changes_fail(self):
        revision = self.manifest["successor_revision_history"]["pre_w08_sop"][1]
        import provenance_reconciliation as reconciliation

        committed = reconciliation._git_blob_bytes(
            ROOT, revision["content_introducing_commit"], revision["path"])
        mutations = (
            committed[:100] + b"x" + committed[100:],
            committed[:-1],
            committed.replace(b" ", b"\t", 1),
            committed.replace("工作流定位".encode("utf-8"),
                               "工作流标题".encode("utf-8"), 1),
            committed.replace("实际阶段状态".encode("utf-8"),
                               "实际阶段结果".encode("utf-8"), 1),
        )
        for mutated in mutations:
            errors = []
            _validate_revision_content(mutated, committed, revision,
                                       "test", errors)
            self.assertTrue(errors)

    def test_forged_current_revision_fields_fail_closed(self):
        for field, value in (("lf_normalized_sha256", "0" * 64),
                             ("revision_id", "forged"),
                             ("version", "forged"),
                             ("role", "forged")):
            def mutate(manifest, field=field, value=value):
                manifest["successor_revision_history"]["pre_w08_sop"][1][field] = value
            self._validate_modified_manifest(mutate)

    def test_historical_successor_revision_modification_fails_closed(self):
        def modify_historical_revision(manifest):
            manifest["successor_revision_history"]["pre_w08_sop"][0][
                "lf_normalized_sha256"] = "0" * 64

        self._validate_modified_manifest(modify_historical_revision)

    def test_w07a_historical_exception_rewrite_fails_closed(self):
        def rewrite_exception(manifest):
            manifest["reconciliations"]["w07a_workflow"][
                "historical_exact_recovery"]["status"] = "recoverable"

        self._validate_modified_manifest(rewrite_exception)

    def test_mutable_execution_status_change_does_not_change_sop_content_hash(self):
        sop_path = os.path.join(ROOT, self.manifest["successor_revision_history"][
            "pre_w08_sop"][1]["path"])
        with open(sop_path, "rb") as handle:
            before = hashlib.sha256(handle.read()).hexdigest()
        with open(os.path.join(ROOT, "prognosis_analysis", "execution_status.json"),
                  encoding="utf-8") as handle:
            status = json.load(handle)
        status["recorded_on"] = "2026-09-07"
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "execution_status.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(status, handle, ensure_ascii=False, indent=2)
            validate_execution_status(root=ROOT, status_path=path)
        with open(sop_path, "rb") as handle:
            after = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(before, after)

    def test_lf_and_crlf_variants_are_accepted_only_after_exact_normalization(self):
        successor = self.manifest["approved_successors"]["pre_w08_sop"]
        import provenance_reconciliation as reconciliation

        committed = reconciliation._git_blob_bytes(
            ROOT, successor["git_commit"], successor["path"])
        crlf = committed.replace(b"\n", b"\r\n")
        self.assertEqual(_normalize_lf_bytes(crlf, "test"), committed)
        self.assertEqual(_normalize_lf_bytes(committed, "test"), committed)
        for current in (committed, crlf):
            errors = []
            _validate_successor_content(current, committed, successor,
                                        "test", errors)
            self.assertEqual(errors, [])
        mixed = committed.replace(b"\n", b"\r\n", 1)
        errors = []
        _validate_successor_content(mixed, committed, successor, "test", errors)
        self.assertEqual(errors, [])

    def test_one_character_add_delete_and_non_eol_whitespace_fail_closed(self):
        successor = self.manifest["approved_successors"]["pre_w08_sop"]
        import provenance_reconciliation as reconciliation

        committed = reconciliation._git_blob_bytes(
            ROOT, successor["git_commit"], successor["path"])
        mutations = (
            committed[:100] + b"x" + committed[100:],
            committed[:-1],
            committed.replace(b" ", b"\t", 1),
        )
        for mutated in mutations:
            errors = []
            _validate_successor_content(mutated, committed, successor,
                                        "test", errors)
            self.assertTrue(errors)

    def test_bare_cr_fails_closed(self):
        with self.assertRaises(ValueError):
            _normalize_lf_bytes(b"line\rtext\n", "test")

    def test_modified_successor_git_snapshot_sha_fails_closed(self):
        def modify_successor(manifest):
            manifest["approved_successors"]["pre_w08_sop"][
                "git_snapshot_sha256"] = "0" * 64

        self._validate_modified_manifest(modify_successor)

    def test_successor_commit_blob_and_path_mismatch_fail_closed(self):
        def modify_commit(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["git_commit"] = (
                "21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2")

        def modify_blob(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["git_blob"] = "0" * 40

        def modify_path(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["path"] = (
                "prognosis_analysis/W07A_pre_W08_protocol_amendment.md")

        for mutation in (modify_commit, modify_blob, modify_path):
            self._validate_modified_manifest(mutation)

    def test_unapproved_successor_fails_closed(self):
        def unapprove_successor(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["approved_successor"] = False

        self._validate_modified_manifest(unapprove_successor)

    def test_unregistered_successor_revision_fails_closed(self):
        def introduce_unregistered_revision(manifest):
            manifest["approved_successors"]["pre_w08_sop"]["version"] = (
                "unregistered_synthetic_revision")

        self._validate_modified_manifest(introduce_unregistered_revision)

    def test_historical_git_object_mismatch_fails_closed(self):
        def modify_git_object(manifest):
            manifest["reconciliations"]["w04_taskbook"][
                "historical_exact_recovery"]["git_blob"] = "0" * 40

        self._validate_modified_manifest(modify_git_object)

    def test_historical_hash_modification_fails_closed(self):
        def modify_historical_hash(manifest):
            manifest["reconciliations"]["w04_taskbook"][
                "source_binding"]["sha256"] = "0" * 64

        self._validate_modified_manifest(modify_historical_hash)


if __name__ == "__main__":
    unittest.main()
