import copy
import json
import os
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
    _validate_successor_content,
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

    def test_current_successor_revision_and_hashes_are_registered(self):
        successor = self.manifest["approved_successors"]["pre_w08_sop"]
        self.assertEqual(successor["git_commit"],
                         "54e1b2ad75949bcdc06ee9dffd8138ea63654c69")
        self.assertEqual(successor["git_blob"],
                         "4f769bf481166eeced760e4946a9c4e4db6ccda4")
        self.assertEqual(successor["sha256"],
                         "b1d40dd24f586ba52c5832d1dc53761d5239699d25a76856b7abeac636f47c03")
        self.assertEqual(successor["git_snapshot_sha256"],
                         "85d03d86d3551ef8505234f3172482bc337b6c650c129724ae55adc31b6e6fc9")

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
