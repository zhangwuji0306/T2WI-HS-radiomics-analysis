"""Cohort split helpers and pre-freeze B-access guard."""
from __future__ import annotations

import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURE_ROOT = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(FEATURE_ROOT)
HABITAT_ROOT = os.path.join(PROJECT_ROOT, "habitat_analysis")
HABITAT_SCRIPTS = os.path.join(HABITAT_ROOT, "scripts")
if HABITAT_SCRIPTS not in sys.path:
    sys.path.insert(0, HABITAT_SCRIPTS)
from freeze_lock import validate_freeze_lock  # noqa: E402

PROGNOSIS_ROOT = os.path.join(PROJECT_ROOT, "prognosis_analysis")
PROGNOSIS_SCRIPTS = os.path.join(PROGNOSIS_ROOT, "scripts")
if PROGNOSIS_SCRIPTS not in sys.path:
    sys.path.insert(0, PROGNOSIS_SCRIPTS)
from model_freeze_lock import validate_model_freeze_lock  # noqa: E402

FREEZE_LOCK = os.path.join(HABITAT_ROOT, "freeze_lock.json")
# Kept as a compatibility name for callers that patch the old setting.  It is
# deliberately not consulted for authorization.
B_UNLOCK_LOCK = os.path.join(HABITAT_ROOT, "b_validation_unlock.json")
MODEL_FREEZE_LOCK = os.path.join(PROGNOSIS_ROOT, "model_freeze_lock.json")


def resolve_cohort_membership(manifest, scanner):
    """Assign A/B using the single project-wide scanner rule."""
    manifest = manifest.copy()
    scanner = scanner.copy()
    manifest["影像号"] = manifest["影像号"].astype(str).str.strip()
    scanner["影像号"] = scanner["影像号"].astype(str).str.strip()
    if manifest["影像号"].duplicated().any() or scanner["影像号"].duplicated().any():
        raise AssertionError("manifest/scanner identifiers must be unique")
    fields = ["影像号", "R1厂商", "R1机型", "R1场强"]
    merged = manifest.merge(scanner[fields], on="影像号", how="left",
                            validate="one_to_one", indicator=True)
    target = merged["排除"].fillna("0").ne("1") if "排除" in merged else pd.Series(True, index=merged.index)
    missing = merged.loc[target & merged["_merge"].ne("both"), "影像号"].tolist()
    if missing:
        raise AssertionError("target cases missing scanner mapping: %s" % missing[:5])
    field = pd.to_numeric(merged["R1场强"], errors="coerce")
    is_a = ((merged["R1厂商"] == "GE MEDICAL SYSTEMS") &
            (merged["R1机型"] == "DISCOVERY MR750") &
            (field.round(1) == 3.0))
    merged["split"] = "B"
    merged.loc[is_a, "split"] = "A"
    return merged.drop(columns=["_merge"])


def add_split(manifest, scanner):
    return resolve_cohort_membership(manifest, scanner)


def require_b_unlock():
    """Require both locks; the legacy B unlock file has no authority."""
    validate_freeze_lock(FREEZE_LOCK)
    return validate_model_freeze_lock(MODEL_FREEZE_LOCK)


def require_a_outcome_unlock():
    """Require the first-stage technical lock before A clinical/outcome reads."""
    return validate_freeze_lock(FREEZE_LOCK)


def read_technical_data(path, reader, *args, **kwargs):
    """Read an outcome-blind technical A artifact without an outcome lock."""
    return reader(path, *args, **kwargs)


def read_a_outcome(path, reader, *args, **kwargs):
    """Validate the first lock before invoking the physical A reader."""
    require_a_outcome_unlock()
    return reader(path, *args, **kwargs)


def read_b_data(path, reader, *args, **kwargs):
    """Validate both locks before invoking the physical B reader."""
    require_b_unlock()
    return reader(path, *args, **kwargs)


def read_b_csv(path, *args, **kwargs):
    reader = kwargs.pop("reader", pd.read_csv)
    return read_b_data(path, reader, *args, **kwargs)


def read_b_excel(path, *args, **kwargs):
    reader = kwargs.pop("reader", pd.read_excel)
    return read_b_data(path, reader, *args, **kwargs)


def select_split(frame, split):
    if split not in ("A", "B", "all"):
        raise ValueError("split must be A, B, or all")
    if split in ("B", "all"):
        require_b_unlock()
    return frame.copy() if split == "all" else frame[frame["split"] == split].copy()
