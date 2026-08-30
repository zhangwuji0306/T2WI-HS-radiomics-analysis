"""Fail-fast promotion helper for fixed-bin-width sigma configurations."""
from __future__ import annotations

from workflow_utils import atomic_write_json


def completion_errors(document):
    errors = []
    expected = int(document.get("n_cases_expected", -1))
    used = int(document.get("n_cases_used", -2))
    failed = int(document.get("n_cases_failed", -1))
    if expected < 1:
        errors.append("n_cases_expected must be positive")
    if used != expected:
        errors.append("n_cases_used != n_cases_expected")
    if failed != 0:
        errors.append("n_cases_failed != 0")
    if document.get("complete_case_pass") is not True:
        errors.append("complete_case_pass is not true")
    return errors


def promote_complete_sigma(document, primary_path, archive_path):
    errors = completion_errors(document)
    if errors:
        raise RuntimeError("incomplete sigma configuration: " + "; ".join(errors))
    atomic_write_json(primary_path, document)
    atomic_write_json(archive_path, document)
