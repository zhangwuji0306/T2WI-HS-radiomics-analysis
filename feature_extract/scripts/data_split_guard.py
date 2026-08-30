"""Cohort split helpers and pre-freeze B-access guard."""
from __future__ import annotations

import json
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

FREEZE_LOCK = os.path.join(HABITAT_ROOT, "freeze_lock.json")
B_UNLOCK_LOCK = os.path.join(HABITAT_ROOT, "b_validation_unlock.json")


def add_split(manifest, scanner):
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


def require_b_unlock():
    validate_freeze_lock(FREEZE_LOCK)
    if not os.path.exists(B_UNLOCK_LOCK):
        raise RuntimeError("B validation remains locked until the A model is frozen")
    with open(B_UNLOCK_LOCK, encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("A_model_frozen") is not True or payload.get("B_validation_unlocked") is not True:
        raise RuntimeError("B validation unlock is invalid")
    return payload


def select_split(frame, split):
    if split not in ("A", "B", "all"):
        raise ValueError("split must be A, B, or all")
    if split in ("B", "all"):
        require_b_unlock()
    return frame.copy() if split == "all" else frame[frame["split"] == split].copy()
