"""Fail-closed validation for the W04/W07A document provenance reconciliation.

This validator is deliberately limited to repository metadata, protocol
documents, JSON/configuration files, and Git objects.  It never opens cohort
CSV files or any other patient-level analysis artifact.  The reconciliation is
version-aware: the historical W04 records are verified against their declared
Git objects, while a current successor is accepted only when it is the exact
approved successor recorded here and in the reconciliation manifest.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys


SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROGNOSIS_ROOT = os.path.dirname(SCRIPT_ROOT)
PROJECT_ROOT = os.path.dirname(PROGNOSIS_ROOT)
DEFAULT_MANIFEST = os.path.join(
    PROGNOSIS_ROOT, "W07A_pre_W08_provenance_reconciliation.json")

MANIFEST_SCHEMA_ID = "W07A_pre_W08_provenance_reconciliation"
MANIFEST_SCHEMA_VERSION = "1.0"
APPROVED_SOURCE_COMMIT = "b35605c931b7a00bd1ef503120a5a26057be9a8e"

W04_MODELING_PROTOCOL_PATH = "prognosis_analysis/modeling_protocol.json"
W04_MODELING_PROTOCOL_SHA256 = (
    "888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe")
W07A_AMENDMENT_JSON_PATH = (
    "prognosis_analysis/W07A_pre_W08_protocol_amendment.json")
W07A_AMENDMENT_PATH = "prognosis_analysis/W07A_pre_W08_protocol_amendment.md"
W07A_AMENDMENT_SHA256 = (
    "adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70")
W07A_AMENDMENT_JSON_SHA256 = (
    "0ca857a7b22c5b948c675f9970cc07b5a908c3f486be3f5656c86e20b5479f14")
TECHNICAL_FREEZE_PATH = "habitat_analysis/freeze_lock.json"
TECHNICAL_FREEZE_SHA256 = (
    "0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262")
TECHNICAL_FREEZE_GIT_COMMIT = (
    "e1b21134dd5e5a4df6befb1d6f7ecab2e84cb1fb")
W07_CONFIG_PATH = "prognosis_analysis/configs/w07_outer_splits.json"
W07_CONFIG_SHA256 = (
    "535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217")
W07_SPLIT_PATH = "prognosis_analysis/output/outer_splits_A.csv"
W07_SPLIT_SHA256 = (
    "24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502")
R_LOW_CANDIDATE_SHA256 = (
    "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0")
R_HIGH_CANDIDATE_SHA256 = (
    "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce")

W04_TASKBOOK_PATH = "T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md"
W04_TASKBOOK_SHA256 = (
    "0ba96334e37b5729356b947ffa41bd2d52649cc84f8d760ba4bbc51a129ffc3c")
W04_WORKFLOW_PATH = "三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md"
W04_WORKFLOW_SHA256 = (
    "26be0bae34faf6dc0b22c7bb3f3e041988ed87cb85b5de1c72cfe8969bd1fd6d")
W07A_WORKFLOW_PATH = (
    "T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md")
W07A_WORKFLOW_SHA256 = (
    "ef3db6abb0c51765d0d34f15ede9a19931f7301633fac2da01934e8017c21fd3")

W04_SOURCE_REVISION_KEYS = (
    "taskbook", "technical_freeze", "W01_feature_dictionary",
    "W01_method_config", "W02_config", "W02_feature_schema",
    "W02_output_manifest", "W02_protocol", "W03_candidate_freeze",
    "W03_config", "W03_feature_schema", "W03_implementation",
    "W03_output_manifest", "W03_protocol",
    "whole_tumor_filtered_implementation",
    "whole_tumor_original_implementation", "whole_tumor_schema_config",
    "whole_tumor_technical_schema", "workflow")
W07A_SOURCE_PROVENANCE_KEYS = (
    "R_high_candidate_hash", "R_low_candidate_hash", "technical_freeze_lock",
    "W04_modeling_protocol", "W07_outer_split_artifact",
    "W07_outer_split_config", "workflow", "working_tree_head_before_amendment")

APPROVED_SUCCESSORS = {
    "scientific_master_protocol": {
        "path": W04_TASKBOOK_PATH,
        "version": "current_scientific_master_protocol_successor",
        "git_commit": APPROVED_SOURCE_COMMIT,
        "sha256": (
            "cc881c008629a1acc0a2b4e6570b4ef277faa27ed5c9f12f908ee947b42381dd"),
        "git_snapshot_sha256": (
            "cc881c008629a1acc0a2b4e6570b4ef277faa27ed5c9f12f908ee947b42381dd"),
        "role": (
            "current Scientific Master Protocol; W04 scientific and modeling "
            "freeze remains authoritative in modeling_protocol.json"),
    },
    "pre_w08_sop": {
        "path": W07A_WORKFLOW_PATH,
        "version": "current_authoritative_pre_w08_operational_sop",
        "git_commit": "54e1b2ad75949bcdc06ee9dffd8138ea63654c69",
        "git_blob": "4f769bf481166eeced760e4946a9c4e4db6ccda4",
        "sha256": (
            "b1d40dd24f586ba52c5832d1dc53761d5239699d25a76856b7abeac636f47c03"),
        "git_snapshot_sha256": (
            "85d03d86d3551ef8505234f3172482bc337b6c650c129724ae55adc31b6e6fc9"),
        "role": (
            "current authoritative operational SOP for post-freeze remediation "
            "and later gated stages"),
    },
}

APPROVED_RECONCILIATION_RELATIONSHIPS = {
    "w04_taskbook": (
        "W04 preserves the historical taskbook revision; the current same-path "
        "Scientific Master Protocol is an approved maintenance successor, while "
        "W04 scientific and modeling freeze authority remains the recorded "
        "modeling_protocol.json revision."),
    "w04_workflow_path_migration": (
        "The W04 root workflow binding is closed by an exact archive path "
        "migration; the archive remains historical and the current Pre-W08 SOP "
        "is the approved operational successor."),
    "w07a_workflow": (
        "The current authoritative Pre-W08 SOP is an approved successor to the "
        "recorded W07A workflow source; the historical source hash is retained "
        "and its unrecoverability is an explicit exception."),
}

APPROVED_SEMANTIC_REVIEW_CONCLUSIONS = {
    "w04_taskbook": (
        "The current successor adds document-role, status, use, and current-SOP "
        "metadata without changing the frozen scientific question, model "
        "hierarchy, technical parameters, or A/B access boundary."),
    "w04_workflow_path_migration": (
        "The archive preserves the W04 workflow bytes and historical role; the "
        "current successor SOP carries the later gated operational workflow "
        "without changing W04 frozen scientific or modeling parameters."),
    "w07a_workflow": (
        "The current successor's operational additions and restructuring do not "
        "alter the already-frozen W07A scientific decisions, technical "
        "parameters, or A/B access boundary; later P5 and governance text is "
        "not retroactively treated as W07A freeze content."),
}

APPROVED_W07A_UNRECOVERABLE_REASON = (
    "The exact pre-amendment byte snapshot is not present as a recoverable Git "
    "object/path in the available repository history; no byte-exact "
    "reconstruction is claimed.")


class ProvenanceReconciliationError(ValueError):
    """Raised when the reconciliation cannot be closed fail-closed."""


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_lf_bytes(data, label):
    """Normalize CRLF/LF bytes while rejecting bare CR bytes."""
    normalized = bytearray()
    index = 0
    while index < len(data):
        value = data[index]
        if value == 13:
            if index + 1 >= len(data) or data[index + 1] != 10:
                raise ValueError("%s contains a bare CR" % label)
            normalized.append(10)
            index += 2
            continue
        normalized.append(value)
        index += 1
    return bytes(normalized)


def _is_sha256(value):
    return isinstance(value, str) and re.match(r"^[0-9a-f]{64}$", value) is not None


def _is_git_object_id(value):
    return isinstance(value, str) and re.match(r"^[0-9a-f]{40}$", value) is not None


def _is_bool(value):
    return isinstance(value, bool)


def _exact_keys(value, expected, label, errors):
    if not isinstance(value, dict):
        errors.append("%s must be an object" % label)
        return False
    expected_set = set(expected)
    actual_set = set(value)
    missing = sorted(expected_set - actual_set)
    extra = sorted(actual_set - expected_set)
    if missing:
        errors.append("%s missing keys: %s" % (label, ", ".join(missing)))
    if extra:
        errors.append("%s has unregistered keys: %s" % (label, ", ".join(extra)))
    return not missing and not extra


def _expect_string(value, label, errors, nonempty=True):
    if not isinstance(value, str) or (nonempty and not value):
        errors.append("%s must be a non-empty string" % label)
        return False
    return True


def _expect_canonical_text(value, label, approved, errors):
    if not isinstance(value, str):
        errors.append("%s must be an approved canonical string" % label)
        return False
    if value not in approved:
        errors.append("%s is not an approved canonical value" % label)
        return False
    return True


def _expect_sha(value, label, errors, allow_null=False):
    if allow_null and value is None:
        return True
    if not _is_sha256(value):
        errors.append("%s must be a lowercase 64-hex SHA-256" % label)
        return False
    return True


def _expect_commit(value, label, errors, allow_null=False):
    if allow_null and value is None:
        return True
    if not _is_git_object_id(value):
        errors.append("%s must be a lowercase 40-hex Git object ID" % label)
        return False
    return True


def _repo_path(root, relative_path, label, errors):
    if not _expect_string(relative_path, label, errors):
        return None
    if (relative_path.startswith(("/", "\\")) or "\\" in relative_path or
            re.match(r"^[A-Za-z]:", relative_path) or
            ".." in relative_path.split("/")):
        errors.append("%s must be a repository-relative slash path" % label)
        return None
    candidate = os.path.abspath(os.path.join(root, *relative_path.split("/")))
    try:
        inside = os.path.commonpath([root, candidate]) == root
    except ValueError:
        inside = False
    if not inside:
        errors.append("%s escapes the repository root" % label)
        return None
    return candidate


def _run_git(root, args):
    try:
        process = subprocess.Popen(
            ["git", "-C", root] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
    except OSError as exc:
        raise RuntimeError("Git is unavailable: %s" % exc)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        detail = stderr.decode("utf-8", "replace").strip()
        raise RuntimeError("git %s failed: %s" % (" ".join(args), detail))
    return stdout


def _git_commit_exists(root, commit):
    resolved = _run_git(root, ["rev-parse", "--verify", commit + "^{commit}"])
    return resolved.decode("ascii").strip() == commit


def _git_blob_id(root, commit, path):
    value = _run_git(root, ["rev-parse", "%s:%s" % (commit, path)])
    return value.decode("ascii").strip()


def _git_blob_bytes(root, commit, path):
    return _run_git(root, ["cat-file", "blob", "%s:%s" % (commit, path)])


def _git_object_type(root, object_id):
    return _run_git(root, ["cat-file", "-t", object_id]).decode("ascii").strip()


def _validate_git_snapshot(root, snapshot, label, expected_status, errors):
    expected_keys = (
        "status", "git_commit", "git_path", "git_blob",
        "verification_sha256", "exact_verification", "verification_method")
    if not _exact_keys(snapshot, expected_keys, label, errors):
        return
    if snapshot.get("status") != expected_status:
        errors.append("%s status is not %s" % (label, expected_status))
    commit = snapshot.get("git_commit")
    path = snapshot.get("git_path")
    blob = snapshot.get("git_blob")
    verified_sha = snapshot.get("verification_sha256")
    _expect_commit(commit, label + ".git_commit", errors)
    _expect_string(path, label + ".git_path", errors)
    _expect_commit(blob, label + ".git_blob", errors)
    _expect_sha(verified_sha, label + ".verification_sha256", errors)
    if snapshot.get("exact_verification") is not True:
        errors.append("%s must declare exact_verification=true" % label)
    _expect_string(snapshot.get("verification_method"),
                   label + ".verification_method", errors)
    if not (_is_git_object_id(commit) and isinstance(path, str) and
            _is_git_object_id(blob) and _is_sha256(verified_sha)):
        return
    try:
        if not _git_commit_exists(root, commit):
            errors.append("%s Git commit does not resolve exactly" % label)
        actual_blob = _git_blob_id(root, commit, path)
        if actual_blob != blob:
            errors.append("%s Git blob mismatch" % label)
        if _git_object_type(root, actual_blob) != "blob":
            errors.append("%s Git object is not a blob" % label)
        actual_sha = _sha256_bytes(_git_blob_bytes(root, commit, path))
        if actual_sha != verified_sha:
            errors.append("%s verification SHA-256 mismatch" % label)
    except (OSError, RuntimeError) as exc:
        errors.append("%s Git verification failed: %s" % (label, exc))


def _validate_successor_content(current_bytes, committed_bytes, successor,
                                label, errors):
    """Require exact Git content, allowing only CRLF/LF representation changes."""
    committed_sha = _sha256_bytes(committed_bytes)
    if committed_sha != successor.get("git_snapshot_sha256"):
        errors.append("%s approved Git snapshot SHA-256 mismatch" % label)
    try:
        current_normalized = _normalize_lf_bytes(
            current_bytes, label + " current file")
        committed_normalized = _normalize_lf_bytes(
            committed_bytes, label + " Git snapshot")
        if committed_normalized != committed_bytes:
            errors.append("%s approved Git snapshot is not LF-only" % label)
        if current_normalized != committed_bytes:
            errors.append(
                "%s current file differs from approved Git snapshot "
                "outside CRLF/LF line endings" % label)
    except ValueError as exc:
        errors.append("%s line-ending validation failed: %s" % (label, exc))


def _validate_successor(root, successor_id, successor, errors):
    expected_keys = ("path", "version", "git_commit", "sha256",
                     "git_snapshot_sha256", "approved_successor", "role")
    if successor_id == "pre_w08_sop":
        expected_keys = ("path", "version", "git_commit", "git_blob", "sha256",
                         "git_snapshot_sha256", "approved_successor", "role")
    label = "approved_successors.%s" % successor_id
    if not _exact_keys(successor, expected_keys, label, errors):
        return
    expected = APPROVED_SUCCESSORS.get(successor_id)
    if expected is None:
        errors.append("%s is not a registered successor" % label)
        return
    approved_fields = ("path", "version", "git_commit", "sha256",
                       "git_snapshot_sha256", "role")
    if successor_id == "pre_w08_sop":
        approved_fields += ("git_blob",)
    for field in approved_fields:
        if successor.get(field) != expected[field]:
            errors.append("%s.%s differs from the approved successor" %
                          (label, field))
    if successor.get("approved_successor") is not True:
        errors.append("%s must declare approved_successor=true" % label)
    _expect_sha(successor.get("sha256"), label + ".sha256", errors)
    _expect_commit(successor.get("git_commit"), label + ".git_commit", errors)
    if successor_id == "pre_w08_sop":
        _expect_commit(successor.get("git_blob"), label + ".git_blob", errors)
    path = _repo_path(root, successor.get("path"), label + ".path", errors)
    if path is None or not os.path.isfile(path):
        errors.append("%s current file is absent" % label)
        return
    try:
        with open(path, "rb") as handle:
            current_bytes = handle.read()
        commit = successor.get("git_commit")
        if _is_git_object_id(commit):
            if not _git_commit_exists(root, commit):
                errors.append("%s Git commit does not resolve exactly" % label)
            actual_blob = _git_blob_id(root, commit, successor["path"])
            if (successor_id == "pre_w08_sop" and
                    actual_blob != successor.get("git_blob")):
                errors.append("%s Git blob mismatch" % label)
            committed_bytes = _git_blob_bytes(root, commit, successor["path"])
            _expect_sha(successor.get("git_snapshot_sha256"),
                        label + ".git_snapshot_sha256", errors)
            _validate_successor_content(current_bytes, committed_bytes,
                                         successor, label, errors)
    except (OSError, RuntimeError) as exc:
        errors.append("%s current/Git verification failed: %s" % (label, exc))


def _validate_semantic_review(review, label, reconciliation_id, errors):
    expected_keys = ("status", "conclusion", "scientific_parameters_changed",
                     "outcome_performance_informed")
    if not _exact_keys(review, expected_keys, label, errors):
        return
    if review.get("status") != "approved":
        errors.append("%s status must be approved" % label)
    approved = APPROVED_SEMANTIC_REVIEW_CONCLUSIONS.get(reconciliation_id)
    if approved is None:
        errors.append("%s has no registered reconciliation semantic conclusion" % label)
    else:
        _expect_canonical_text(review.get("conclusion"), label + ".conclusion",
                               (approved,), errors)
    if review.get("scientific_parameters_changed") is not False:
        errors.append("%s scientific_parameters_changed must be false" % label)
    if review.get("outcome_performance_informed") is not False:
        errors.append("%s outcome_performance_informed must be false" % label)


def _validate_source_binding(binding, label, expected_owner, expected_path,
                             expected_sha, errors):
    expected_keys = ("owner", "path", "sha256")
    if not _exact_keys(binding, expected_keys, label, errors):
        return
    for field, expected in (("owner", expected_owner), ("path", expected_path),
                            ("sha256", expected_sha)):
        if binding.get(field) != expected:
            errors.append("%s.%s differs from the frozen source binding" %
                          (label, field))
    _expect_sha(binding.get("sha256"), label + ".sha256", errors)


def _validate_w04_taskbook(root, item, successors, errors):
    label = "reconciliations.w04_taskbook"
    expected_keys = ("source_binding", "historical_exact_recovery",
                     "current_successor_id", "relationship", "semantic_review")
    if not _exact_keys(item, expected_keys, label, errors):
        return
    _validate_source_binding(
        item.get("source_binding"), label + ".source_binding",
        "prognosis_analysis/modeling_protocol.json:source_revisions.taskbook",
        W04_TASKBOOK_PATH, W04_TASKBOOK_SHA256, errors)
    _validate_git_snapshot(root, item.get("historical_exact_recovery"),
                           label + ".historical_exact_recovery", "recoverable",
                           errors)
    if item.get("current_successor_id") != "scientific_master_protocol":
        errors.append("%s current successor is not the approved taskbook successor" % label)
    approved_relationship = APPROVED_RECONCILIATION_RELATIONSHIPS.get("w04_taskbook")
    _expect_canonical_text(item.get("relationship"), label + ".relationship",
                           (approved_relationship,), errors)
    _validate_semantic_review(item.get("semantic_review"),
                              label + ".semantic_review", "w04_taskbook", errors)
    if isinstance(item.get("historical_exact_recovery"), dict):
        snapshot = item["historical_exact_recovery"]
        if snapshot.get("git_commit") != "78b0e8f48becd64413859027e8809e155ecded5e":
            errors.append("%s historical Git commit is not the approved W04 recovery" % label)
        if snapshot.get("git_path") != W04_TASKBOOK_PATH:
            errors.append("%s historical Git path is not the W04 taskbook path" % label)
        if snapshot.get("verification_sha256") != W04_TASKBOOK_SHA256:
            errors.append("%s historical SHA is not the recorded W04 SHA" % label)
    taskbook_successor = successors.get("scientific_master_protocol", {}) \
        if isinstance(successors, dict) else {}
    if (not isinstance(taskbook_successor, dict) or
            taskbook_successor.get("approved_successor") is not True):
        errors.append("%s requires the approved scientific master protocol successor" % label)


def _validate_w04_migration(root, item, successors, errors):
    label = "reconciliations.w04_workflow_path_migration"
    expected_keys = ("source_binding", "archive_exact_recovery", "migration",
                     "current_successor_id", "relationship", "semantic_review")
    if not _exact_keys(item, expected_keys, label, errors):
        return
    _validate_source_binding(
        item.get("source_binding"), label + ".source_binding",
        "prognosis_analysis/modeling_protocol.json:source_revisions.workflow",
        W04_WORKFLOW_PATH, W04_WORKFLOW_SHA256, errors)
    _validate_git_snapshot(root, item.get("archive_exact_recovery"),
                           label + ".archive_exact_recovery", "recoverable",
                           errors)
    migration = item.get("migration")
    migration_keys = ("from_path", "to_archive_path", "rename_commit",
                      "rename_similarity", "archive_role")
    if _exact_keys(migration, migration_keys, label + ".migration", errors):
        if migration.get("from_path") != W04_WORKFLOW_PATH:
            errors.append("%s migration.from_path differs from W04" % label)
        expected_archive = (
            "archive/protocol_history/三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md")
        if migration.get("to_archive_path") != expected_archive:
            errors.append("%s migration.to_archive_path is not the registered archive" % label)
        if migration.get("rename_commit") != "21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2":
            errors.append("%s migration.rename_commit is not the archive rename commit" % label)
        if migration.get("rename_similarity") != "100%":
            errors.append("%s migration.rename_similarity must be 100%%" % label)
        if migration.get("archive_role") != "historical_only_not_current_execution_input":
            errors.append("%s archive must remain historical-only" % label)
    if item.get("current_successor_id") != "pre_w08_sop":
        errors.append("%s current successor is not the approved Pre-W08 SOP" % label)
    approved_relationship = APPROVED_RECONCILIATION_RELATIONSHIPS.get(
        "w04_workflow_path_migration")
    _expect_canonical_text(item.get("relationship"), label + ".relationship",
                           (approved_relationship,), errors)
    _validate_semantic_review(
        item.get("semantic_review"), label + ".semantic_review",
        "w04_workflow_path_migration", errors)
    if isinstance(item.get("archive_exact_recovery"), dict):
        snapshot = item["archive_exact_recovery"]
        expected_archive = (
            "archive/protocol_history/三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md")
        if snapshot.get("git_commit") != "21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2":
            errors.append("%s archive Git commit is not the rename commit" % label)
        if snapshot.get("git_path") != expected_archive:
            errors.append("%s archive Git path is not the registered archive" % label)
        if snapshot.get("verification_sha256") != W04_WORKFLOW_SHA256:
            errors.append("%s archive SHA is not the recorded W04 workflow SHA" % label)
    old_path = _repo_path(root, W04_WORKFLOW_PATH,
                          label + ".source_binding.path", errors)
    if old_path is not None and os.path.isfile(old_path):
        errors.append("%s old root workflow path was unexpectedly restored" % label)
    sop_successor = successors.get("pre_w08_sop", {}) \
        if isinstance(successors, dict) else {}
    if (not isinstance(sop_successor, dict) or
            sop_successor.get("approved_successor") is not True):
        errors.append("%s requires the approved Pre-W08 SOP successor" % label)


def _validate_w07a_workflow(item, successors, errors):
    label = "reconciliations.w07a_workflow"
    expected_keys = ("source_binding", "historical_exact_recovery",
                     "current_successor_id", "relationship", "semantic_review",
                     "exception")
    if not _exact_keys(item, expected_keys, label, errors):
        return
    _validate_source_binding(
        item.get("source_binding"), label + ".source_binding",
        "prognosis_analysis/W07A_pre_W08_protocol_amendment.json:source_provenance.workflow",
        W07A_WORKFLOW_PATH, W07A_WORKFLOW_SHA256, errors)
    recovery = item.get("historical_exact_recovery")
    recovery_keys = ("status", "git_commit", "git_path", "git_blob",
                     "verification_sha256", "exact_verification",
                     "unrecoverable_reason")
    if _exact_keys(recovery, recovery_keys, label + ".historical_exact_recovery", errors):
        if recovery.get("status") != "historical_source_snapshot_unrecoverable":
            errors.append("%s historical status must be unrecoverable" % label)
        if (recovery.get("git_commit") is not None or
                recovery.get("git_path") is not None or
                recovery.get("git_blob") is not None or
                recovery.get("verification_sha256") is not None):
            errors.append("%s unrecoverable history must not claim a Git recovery" % label)
        if recovery.get("exact_verification") is not False:
            errors.append("%s exact_verification must be false" % label)
        _expect_canonical_text(
            recovery.get("unrecoverable_reason"),
            label + ".historical_exact_recovery.unrecoverable_reason",
            (APPROVED_W07A_UNRECOVERABLE_REASON,), errors)
    if item.get("current_successor_id") != "pre_w08_sop":
        errors.append("%s current successor is not the approved Pre-W08 SOP" % label)
    approved_relationship = APPROVED_RECONCILIATION_RELATIONSHIPS.get(
        "w07a_workflow")
    _expect_canonical_text(item.get("relationship"), label + ".relationship",
                           (approved_relationship,), errors)
    _validate_semantic_review(item.get("semantic_review"),
                              label + ".semantic_review", "w07a_workflow", errors)
    exception = item.get("exception")
    exception_keys = ("id", "required", "exact_verification",
                      "byte_exact_pass", "acceptance")
    if _exact_keys(exception, exception_keys, label + ".exception", errors):
        if exception.get("id") != "historical_source_snapshot_unrecoverable":
            errors.append("%s exception id is not registered" % label)
        if exception.get("required") is not True:
            errors.append("%s exception must be required" % label)
        if exception.get("exact_verification") is not False:
            errors.append("%s exception exact_verification must be false" % label)
        if exception.get("byte_exact_pass") is not False:
            errors.append("%s must never claim a W07A byte-exact PASS" % label)
        if exception.get("acceptance") != (
                "reconciliation_pass_with_explicit_exception_only; never a byte-exact PASS"):
            errors.append("%s exception acceptance text is not fail-closed" % label)
    sop_successor = successors.get("pre_w08_sop", {}) \
        if isinstance(successors, dict) else {}
    if (not isinstance(sop_successor, dict) or
            sop_successor.get("approved_successor") is not True):
        errors.append("%s requires the approved Pre-W08 SOP successor" % label)


def _validate_manifest_header(manifest, errors):
    top_keys = ("schema", "verification", "protocol_owner_approval",
                "global_invariants", "approved_successors", "reconciliations")
    if not _exact_keys(manifest, top_keys, "manifest", errors):
        return
    schema = manifest.get("schema")
    if _exact_keys(schema, ("id", "version", "status", "hash_algorithm", "scope"),
                   "manifest.schema", errors):
        expected_schema = {
            "id": MANIFEST_SCHEMA_ID,
            "version": MANIFEST_SCHEMA_VERSION,
            "status": "approved_reconciliation",
            "hash_algorithm": "SHA-256",
            "scope": "non_patient_level_document_provenance_only",
        }
        for key, expected in expected_schema.items():
            if schema.get(key) != expected:
                errors.append("manifest.schema.%s differs from the approved schema" % key)
    verification = manifest.get("verification")
    if _exact_keys(verification, ("source_commit", "source_commit_role", "git_required"),
                   "manifest.verification", errors):
        if verification.get("source_commit") != APPROVED_SOURCE_COMMIT:
            errors.append("manifest.verification.source_commit is not the approved base")
        if verification.get("source_commit_role") != "verification_base_and_approved_successor_snapshot":
            errors.append("manifest.verification.source_commit_role is not version-aware")
        if verification.get("git_required") is not True:
            errors.append("manifest.verification.git_required must be true")
    approval = manifest.get("protocol_owner_approval")
    approval_keys = ("status", "scope", "permits", "does_not_permit")
    if _exact_keys(approval, approval_keys, "manifest.protocol_owner_approval", errors):
        if approval.get("status") != "approved":
            errors.append("protocol-owner approval must be approved")
        if approval.get("scope") != "P4 document-provenance reconciliation only":
            errors.append("protocol-owner approval scope is too broad or changed")
        expected_permits = [
            "preserve W04 historical source revision and verify its exact Git recovery",
            "register W04 workflow archive path migration and current successor SOP",
            "register W07A unrecoverable historical snapshot as an explicit exception",
            "add this independent manifest and fail-closed validator",
            "update the P4 integrity audit with the reconciliation evidence",
        ]
        expected_denials = [
            "modify freeze_lock or any frozen scientific artifact",
            "modify modeling_protocol, W03 candidate freeze, W07 split, or W07A amendment",
            "change scientific or modeling parameters",
            "read B data or start formal W08",
            "start P5 implementation, G2R2, 50-fold P5, or G3",
        ]
        if approval.get("permits") != expected_permits:
            errors.append("protocol-owner approval permits are not the approved scope")
        if approval.get("does_not_permit") != expected_denials:
            errors.append("protocol-owner approval denials are not the approved scope")
    invariants = manifest.get("global_invariants")
    invariant_keys = ("outcome_performance_informed", "scientific_parameters_changed",
                      "B_data_read", "formal_W08_started")
    if _exact_keys(invariants, invariant_keys, "manifest.global_invariants", errors):
        for key in invariant_keys:
            if invariants.get(key) is not False:
                errors.append("manifest.global_invariants.%s must be false" % key)


def _validate_w04_protocol_sources(root, manifest, errors):
    """Validate the unchanged W04 source-revision contract.

    Only the two approved documentation mismatches are reconciled.  Every
    other W04 source revision remains a direct current-file SHA check.
    """
    protocol_path = _repo_path(root, W04_MODELING_PROTOCOL_PATH,
                               "W04 modeling protocol", errors)
    if protocol_path is None or not os.path.isfile(protocol_path):
        errors.append("W04 modeling protocol is absent")
        return
    try:
        if _sha256_file(protocol_path) != W04_MODELING_PROTOCOL_SHA256:
            errors.append("W04 modeling protocol SHA-256 changed")
        with open(protocol_path, "r", encoding="utf-8") as handle:
            protocol = json.load(handle)
    except (OSError, ValueError) as exc:
        errors.append("W04 modeling protocol cannot be read as JSON: %s" % exc)
        return
    source_revisions = protocol.get("source_revisions")
    if not _exact_keys(source_revisions, W04_SOURCE_REVISION_KEYS,
                       "W04 source_revisions", errors):
        return
    manifest_reconciliations = manifest.get("reconciliations", {})
    if not isinstance(manifest_reconciliations, dict):
        return
    taskbook = manifest_reconciliations.get("w04_taskbook", {})
    migration = manifest_reconciliations.get("w04_workflow_path_migration", {})
    if not isinstance(taskbook, dict):
        taskbook = {}
    if not isinstance(migration, dict):
        migration = {}
    for name in W04_SOURCE_REVISION_KEYS:
        source = source_revisions.get(name)
        label = "W04 source_revisions.%s" % name
        source_keys = ("path", "sha256")
        if name == "technical_freeze":
            source_keys = ("path", "sha256", "schema_version", "git_commit")
        if not _exact_keys(source, source_keys, label, errors):
            continue
        _expect_sha(source.get("sha256"), label + ".sha256", errors)
        if name == "technical_freeze":
            if source.get("path") != TECHNICAL_FREEZE_PATH:
                errors.append("W04 technical_freeze path changed")
            if source.get("sha256") != TECHNICAL_FREEZE_SHA256:
                errors.append("W04 technical_freeze SHA-256 changed")
            if source.get("schema_version") != "1.0":
                errors.append("W04 technical_freeze schema_version changed")
            if source.get("git_commit") != TECHNICAL_FREEZE_GIT_COMMIT:
                errors.append("W04 technical_freeze git_commit changed")
            _expect_commit(source.get("git_commit"),
                           label + ".git_commit", errors)
        if name == "taskbook":
            expected = taskbook.get("source_binding", {})
            if source != {"path": W04_TASKBOOK_PATH, "sha256": W04_TASKBOOK_SHA256}:
                errors.append("W04 taskbook binding changed outside reconciliation")
            if (expected.get("path") != source.get("path") or
                    expected.get("sha256") != source.get("sha256")):
                errors.append("W04 taskbook reconciliation does not mirror source_revision")
            continue
        if name == "workflow":
            expected = migration.get("source_binding", {})
            if source != {"path": W04_WORKFLOW_PATH, "sha256": W04_WORKFLOW_SHA256}:
                errors.append("W04 workflow binding changed outside reconciliation")
            if (expected.get("path") != source.get("path") or
                    expected.get("sha256") != source.get("sha256")):
                errors.append("W04 workflow reconciliation does not mirror source_revision")
            continue
        path = _repo_path(root, source.get("path"), label + ".path", errors)
        if path is None or not os.path.isfile(path):
            errors.append("%s current file is absent" % label)
            continue
        try:
            if _sha256_file(path) != source.get("sha256"):
                errors.append("%s current file SHA-256 mismatch" % label)
        except OSError as exc:
            errors.append("%s current file cannot be hashed: %s" % (label, exc))


def _validate_w07a_sources(root, manifest, errors):
    amendment_json_path = _repo_path(root, W07A_AMENDMENT_JSON_PATH,
                                     "W07A amendment JSON", errors)
    amendment_path = _repo_path(root, W07A_AMENDMENT_PATH,
                                "W07A amendment Markdown", errors)
    if amendment_json_path is None or not os.path.isfile(amendment_json_path):
        errors.append("W07A amendment JSON is absent")
        return
    if amendment_path is None or not os.path.isfile(amendment_path):
        errors.append("W07A amendment Markdown is absent")
    try:
        if _sha256_file(amendment_json_path) != W07A_AMENDMENT_JSON_SHA256:
            errors.append("W07A amendment JSON SHA-256 changed")
        with open(amendment_json_path, "r", encoding="utf-8") as handle:
            amendment = json.load(handle)
        if amendment_path is not None and os.path.isfile(amendment_path):
            if _sha256_file(amendment_path) != W07A_AMENDMENT_SHA256:
                errors.append("W07A amendment Markdown SHA-256 changed")
    except (OSError, ValueError) as exc:
        errors.append("W07A amendment provenance cannot be read: %s" % exc)
        return
    source_provenance = amendment.get("source_provenance")
    if not _exact_keys(source_provenance, W07A_SOURCE_PROVENANCE_KEYS,
                       "W07A source_provenance", errors):
        return
    reconciliations = manifest.get("reconciliations", {})
    if not isinstance(reconciliations, dict):
        return
    reconciliation = reconciliations.get("w07a_workflow", {})
    if not isinstance(reconciliation, dict):
        reconciliation = {}
    binding = reconciliation.get("source_binding", {})
    if not isinstance(binding, dict):
        binding = {}
    workflow = source_provenance.get("workflow")
    if not isinstance(workflow, dict):
        workflow = {}
    if workflow != {"path": W07A_WORKFLOW_PATH, "sha256": W07A_WORKFLOW_SHA256}:
        errors.append("W07A workflow provenance changed outside reconciliation")
    if (binding.get("path") != workflow.get("path") or
            binding.get("sha256") != workflow.get("sha256")):
        errors.append("W07A reconciliation does not mirror source_provenance.workflow")
    expected_values = {
        "R_high_candidate_hash": R_HIGH_CANDIDATE_SHA256,
        "R_low_candidate_hash": R_LOW_CANDIDATE_SHA256,
        "technical_freeze_lock": {
            "path": TECHNICAL_FREEZE_PATH, "sha256": TECHNICAL_FREEZE_SHA256},
        "W04_modeling_protocol": {
            "path": W04_MODELING_PROTOCOL_PATH,
            "sha256": W04_MODELING_PROTOCOL_SHA256},
        "W07_outer_split_artifact": {
            "path": W07_SPLIT_PATH, "sha256": W07_SPLIT_SHA256},
        "W07_outer_split_config": {
            "path": W07_CONFIG_PATH, "sha256": W07_CONFIG_SHA256},
        "working_tree_head_before_amendment":
            "bfdfc47aecd3a8c583d9e59450b17edc4bf1f333",
    }
    for key, expected in expected_values.items():
        if source_provenance.get(key) != expected:
            errors.append("W07A source_provenance.%s changed" % key)
        value = source_provenance.get(key)
        if isinstance(value, dict):
            _exact_keys(value, ("path", "sha256"),
                        "W07A source_provenance.%s" % key, errors)
            _expect_sha(value.get("sha256"),
                        "W07A source_provenance.%s.sha256" % key, errors)
        elif key.endswith("candidate_hash"):
            _expect_sha(value, "W07A source_provenance.%s" % key, errors)
        elif key == "working_tree_head_before_amendment":
            _expect_commit(value, "W07A source_provenance.%s" % key, errors)
    # The split artifact is deliberately not opened: it is a patient-level
    # CSV.  Its frozen path/SHA binding is checked as metadata only; the
    # document-provenance reconciliation does not need its contents.
    for key in ("technical_freeze_lock", "W04_modeling_protocol",
                "W07_outer_split_config"):
        item = source_provenance.get(key)
        if not isinstance(item, dict):
            continue
        path = _repo_path(root, item.get("path"),
                          "W07A source_provenance.%s.path" % key, errors)
        if path is None or not os.path.isfile(path):
            errors.append("W07A source_provenance.%s current file is absent" % key)
            continue
        try:
            if _sha256_file(path) != item.get("sha256"):
                errors.append("W07A source_provenance.%s current SHA-256 mismatch" % key)
        except OSError as exc:
            errors.append("W07A source_provenance.%s cannot be hashed: %s" % (key, exc))
    if source_provenance.get("W07_outer_split_artifact") != {
            "path": W07_SPLIT_PATH, "sha256": W07_SPLIT_SHA256}:
        errors.append("W07A W07 outer split binding is not the approved metadata")


def validate_manifest(root=None, manifest_path=None):
    """Validate the approved reconciliation and return a machine-readable report.

    Args:
        root: Project root. Defaults to the repository containing this script.
        manifest_path: Manifest path. Defaults to the project reconciliation.

    Raises:
        ProvenanceReconciliationError: if any schema, version, Git, file, or
            approval check fails.
    """
    root = os.path.abspath(root or PROJECT_ROOT)
    manifest_path = os.path.abspath(manifest_path or DEFAULT_MANIFEST)
    errors = []
    if not os.path.isfile(manifest_path):
        raise ProvenanceReconciliationError(
            "manifest is absent: %s" % manifest_path)
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ProvenanceReconciliationError("manifest cannot be read: %s" % exc)
    if not isinstance(manifest, dict):
        raise ProvenanceReconciliationError("manifest top level must be an object")

    _validate_manifest_header(manifest, errors)
    successors = manifest.get("approved_successors", {})
    if _exact_keys(successors, tuple(APPROVED_SUCCESSORS),
                   "manifest.approved_successors", errors):
        for successor_id in APPROVED_SUCCESSORS:
            _validate_successor(root, successor_id,
                                successors.get(successor_id), errors)
    reconciliations = manifest.get("reconciliations", {})
    reconciliation_keys = ("w04_taskbook", "w04_workflow_path_migration",
                           "w07a_workflow")
    if _exact_keys(reconciliations, reconciliation_keys,
                   "manifest.reconciliations", errors):
        _validate_w04_taskbook(root, reconciliations.get("w04_taskbook"),
                               successors, errors)
        _validate_w04_migration(root,
                                reconciliations.get("w04_workflow_path_migration"),
                                successors, errors)
        _validate_w07a_workflow(reconciliations.get("w07a_workflow"),
                                successors, errors)
    _validate_w04_protocol_sources(root, manifest, errors)
    _validate_w07a_sources(root, manifest, errors)

    verification = manifest.get("verification", {})
    source_commit = (verification.get("source_commit")
                     if isinstance(verification, dict) else None)
    if _is_git_object_id(source_commit):
        try:
            if not _git_commit_exists(root, source_commit):
                errors.append("verification source commit does not resolve")
            else:
                try:
                    _run_git(root, ["merge-base", "--is-ancestor", source_commit, "HEAD"])
                except RuntimeError as exc:
                    errors.append("verification source commit is not an ancestor of HEAD: %s" % exc)
        except (OSError, RuntimeError) as exc:
            errors.append("verification source commit check failed: %s" % exc)

    if errors:
        raise ProvenanceReconciliationError("\n".join(errors))
    return {
        "status": "PASS",
        "manifest_path": manifest_path,
        "verification_source_commit": source_commit,
        "historical_recovery": {
            "w04_taskbook_exact_verification": True,
            "w04_workflow_archive_exact_verification": True,
            "w07a_workflow_exact_verification": False,
            "w07a_exception": "historical_source_snapshot_unrecoverable",
        },
        "invariants": {
            "outcome_performance_informed": False,
            "scientific_parameters_changed": False,
            "B_data_read": False,
            "formal_W08_started": False,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validate the approved W04/W07A provenance reconciliation")
    parser.add_argument("--root", default=PROJECT_ROOT,
                        help="project repository root")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST,
                        help="reconciliation manifest path")
    args = parser.parse_args(argv)
    try:
        result = validate_manifest(root=args.root, manifest_path=args.manifest)
    except ProvenanceReconciliationError as exc:
        sys.stderr.write("PROVENANCE RECONCILIATION FAIL\n%s\n" % exc)
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
