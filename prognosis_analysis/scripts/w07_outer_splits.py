"""W07: freeze the A-only repeated outer cross-validation plan.

This stage consumes only the local W06 A modeling-population artifact.  It
does not open the clinical workbook, radiomics tables, B artifacts, or any
modeling input.  The split plan is outcome-aware only through the frozen
``DFS_event`` status required for stratification and event-count gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
OUTPUT_ROOT = os.path.join(ROOT, "output")
DEFAULT_POPULATION = os.path.join(
    OUTPUT_ROOT, "A_modeling", "A_modeling_population.csv")
DEFAULT_SPLITS = os.path.join(OUTPUT_ROOT, "outer_splits_A.csv")
DEFAULT_CONFIG = os.path.join(
    ROOT, "configs", "w07_outer_splits.json")

POPULATION_COLUMNS = [
    "影像号", "technical_cohort", "DFS_time", "DFS_event",
    "modeling_eligible",
]
SPLIT_COLUMNS = ["patient_id", "repeat", "fold", "role", "seed"]
ROLES = ("train", "validation")


class W07ValidationError(ValueError):
    """Raised when a frozen W07 input or split invariant is violated."""


def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_config(path: str = DEFAULT_CONFIG) -> dict:
    """Load and validate the immutable W07 design configuration."""
    config = _read_json(path)
    required = {"stage", "status", "input", "outer_cv", "populations",
                "forbidden_operations"}
    missing = sorted(required - set(config))
    if missing:
        raise W07ValidationError("W07 config missing keys: %s" % missing)
    if config["stage"] != "W07" or config["status"] != "frozen":
        raise W07ValidationError("W07 config must be frozen")

    input_cfg = config["input"]
    if input_cfg.get("expected_columns") != POPULATION_COLUMNS:
        raise W07ValidationError("W07 input schema is not the W06 schema")
    if input_cfg.get("technical_cohort") != "A393":
        raise W07ValidationError("W07 input must be A393")
    if input_cfg.get("expected_population") != 393:
        raise W07ValidationError("W07 expected population must be 393")
    if input_cfg.get("expected_events") != 89:
        raise W07ValidationError("W07 expected event count must be 89")
    if input_cfg.get("expected_censors") != 304:
        raise W07ValidationError("W07 expected censor count must be 304")

    outer = config["outer_cv"]
    if outer.get("n_splits") != 5 or outer.get("n_repeats") != 10:
        raise W07ValidationError("W07 requires 5 folds x 10 repeats")
    if outer.get("n_validation_folds") != 50:
        raise W07ValidationError("W07 must define 50 validation folds")
    if outer.get("stratify_by") != "DFS_event":
        raise W07ValidationError("W07 must stratify by DFS_event")
    if outer.get("seed_root") != 12345:
        raise W07ValidationError("W07 seed root must be 12345")
    if outer.get("minimum_events_per_train_fold") != 1 or \
            outer.get("minimum_events_per_validation_fold") != 1:
        raise W07ValidationError("W07 event gates must require one event")
    if list(outer.get("roles", [])) != list(ROLES):
        raise W07ValidationError("W07 roles must be train and validation")

    for name in ("main", "R_low", "R_high", "dual_radiomics"):
        if name not in config["populations"]:
            raise W07ValidationError("missing population eligibility: %s" % name)
    return config


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize_population(frame: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Validate the exact W06 A population and retain only split inputs."""
    if list(frame.columns) != POPULATION_COLUMNS:
        raise W07ValidationError(
            "A_modeling_population schema mismatch: expected %s, got %s" %
            (POPULATION_COLUMNS, list(frame.columns)))
    population = frame.copy()
    raw_ids = population["影像号"]
    if raw_ids.isna().any():
        raise W07ValidationError("A population contains missing patient IDs")
    population["patient_id"] = raw_ids.astype(str).str.strip()
    if population["patient_id"].eq("").any():
        raise W07ValidationError("A population contains blank patient IDs")
    if population["patient_id"].duplicated().any():
        raise W07ValidationError("A population contains duplicate patient IDs")

    cohort = population["technical_cohort"].astype(str).str.strip()
    if not cohort.eq(config["input"]["technical_cohort"]).all():
        raise W07ValidationError("W07 input is not exact A393")
    eligible = pd.to_numeric(population["modeling_eligible"], errors="coerce")
    if eligible.isna().any() or not eligible.eq(1).all():
        raise W07ValidationError("W07 input contains non-eligible rows")

    times = pd.to_numeric(population["DFS_time"], errors="coerce")
    if times.isna().any() or not np.isfinite(times.to_numpy(dtype=float)).all():
        raise W07ValidationError("W07 input contains invalid DFS_time")
    if not times.gt(0).all():
        raise W07ValidationError("W07 input contains DFS_time <= 0")
    events = pd.to_numeric(population["DFS_event"], errors="coerce")
    if events.isna().any() or not events.isin([0, 1]).all():
        raise W07ValidationError("W07 input contains non-binary DFS_event")

    expected_n = config["input"]["expected_population"]
    expected_events = config["input"]["expected_events"]
    expected_censors = config["input"]["expected_censors"]
    if len(population) != expected_n:
        raise W07ValidationError("W07 input population must contain %d rows" % expected_n)
    if int(events.eq(1).sum()) != expected_events:
        raise W07ValidationError("W07 input event count is not %d" % expected_events)
    if int(events.eq(0).sum()) != expected_censors:
        raise W07ValidationError("W07 input censor count is not %d" % expected_censors)

    normalized = pd.DataFrame({
        "patient_id": population["patient_id"],
        "DFS_event": events.astype(int),
    })
    return normalized.sort_values("patient_id", kind="mergesort").reset_index(drop=True)


def load_a_modeling_population(path: str = DEFAULT_POPULATION,
                               config: Optional[dict] = None) -> pd.DataFrame:
    """Read only the exact W06 A modeling-population CSV contract.

    The filename guard is intentional: W07 has no generic dataset reader and
    cannot be pointed at a clinical workbook, a radiomics table, or a B file.
    """
    if os.path.basename(os.path.normpath(path)) != "A_modeling_population.csv":
        raise W07ValidationError(
            "W07 accepts only A_modeling_population.csv as its input")
    if config is None:
        config = load_config()
    frame = pd.read_csv(path, dtype={"影像号": str})
    return _normalize_population(frame, config)


def _outer_seed(config: dict, repeat: int) -> int:
    return int(config["outer_cv"]["seed_root"] + repeat - 1)


def build_outer_splits(population: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Construct deterministic repeated, event-stratified outer split rows."""
    n_splits = int(config["outer_cv"]["n_splits"])
    n_repeats = int(config["outer_cv"]["n_repeats"])
    event_counts = population["DFS_event"].value_counts()
    if int(event_counts.min()) < n_splits:
        raise W07ValidationError(
            "each event class must have at least %d cases" % n_splits)

    rows: List[dict] = []
    ids = population["patient_id"].to_numpy()
    events = population["DFS_event"].to_numpy(dtype=int)
    for repeat in range(1, n_repeats + 1):
        seed = _outer_seed(config, repeat)
        splitter = StratifiedKFold(
            n_splits=n_splits, shuffle=True, random_state=seed)
        for fold, (train_idx, validation_idx) in enumerate(
                splitter.split(ids, events), start=1):
            for index in train_idx:
                rows.append({"patient_id": ids[index], "repeat": repeat,
                             "fold": fold, "role": "train", "seed": seed})
            for index in validation_idx:
                rows.append({"patient_id": ids[index], "repeat": repeat,
                             "fold": fold, "role": "validation", "seed": seed})

    result = pd.DataFrame(rows, columns=SPLIT_COLUMNS)
    role_order = {"train": 0, "validation": 1}
    result["_role_order"] = result["role"].map(role_order)
    result = result.sort_values(
        ["repeat", "fold", "_role_order", "patient_id"],
        kind="mergesort").drop(columns=["_role_order"]).reset_index(drop=True)
    result["repeat"] = result["repeat"].astype(int)
    result["fold"] = result["fold"].astype(int)
    result["seed"] = result["seed"].astype(int)
    return result[SPLIT_COLUMNS]


def validate_outer_splits(split_frame: pd.DataFrame, population: pd.DataFrame,
                          config: dict) -> dict:
    """Apply schema, coverage, duplicate, group, seed, and event gates."""
    if list(split_frame.columns) != SPLIT_COLUMNS:
        raise W07ValidationError("outer split schema mismatch")
    if split_frame.isna().any().any():
        raise W07ValidationError("outer split contains missing values")

    n = len(population)
    n_splits = int(config["outer_cv"]["n_splits"])
    n_repeats = int(config["outer_cv"]["n_repeats"])
    expected_rows = n * n_splits * n_repeats
    if len(split_frame) != expected_rows:
        raise W07ValidationError("outer split row count mismatch")
    if set(split_frame["patient_id"]) != set(population["patient_id"]):
        raise W07ValidationError("outer split contains an unknown or missing patient")
    if not set(split_frame["repeat"]) == set(range(1, n_repeats + 1)):
        raise W07ValidationError("outer split repeats are incomplete")
    if not set(split_frame["fold"]) == set(range(1, n_splits + 1)):
        raise W07ValidationError("outer split folds are incomplete")
    if set(split_frame["role"]) != set(ROLES):
        raise W07ValidationError("outer split roles are incomplete")
    if split_frame.duplicated(
            subset=["repeat", "fold", "role", "patient_id"]).any():
        raise W07ValidationError("outer split contains duplicate group rows")

    event_map = population.set_index("patient_id")["DFS_event"]
    fold_event_counts: List[dict] = []
    for repeat in range(1, n_repeats + 1):
        repeated = split_frame[split_frame["repeat"] == repeat]
        validation_counts = repeated[repeated["role"] == "validation"] \
            .groupby("patient_id").size()
        training_counts = repeated[repeated["role"] == "train"] \
            .groupby("patient_id").size()
        if not validation_counts.eq(1).all():
            raise W07ValidationError("each patient needs one validation fold per repeat")
        if not training_counts.eq(n_splits - 1).all():
            raise W07ValidationError("each patient needs four training folds per repeat")

        for fold in range(1, n_splits + 1):
            group = repeated[repeated["fold"] == fold]
            train = group[group["role"] == "train"]
            validation = group[group["role"] == "validation"]
            train_ids = set(train["patient_id"])
            validation_ids = set(validation["patient_id"])
            if train_ids & validation_ids:
                raise W07ValidationError("train/validation overlap detected")
            if train_ids | validation_ids != set(population["patient_id"]):
                raise W07ValidationError("fold does not cover the A population")
            train_events = int(event_map.loc[list(train_ids)].sum())
            validation_events = int(event_map.loc[list(validation_ids)].sum())
            if train_events < config["outer_cv"]["minimum_events_per_train_fold"]:
                raise W07ValidationError("training fold event gate failed")
            if validation_events < config["outer_cv"]["minimum_events_per_validation_fold"]:
                raise W07ValidationError("validation fold event gate failed")
            fold_event_counts.append({
                "repeat": repeat,
                "fold": fold,
                "train_events": train_events,
                "validation_events": validation_events,
                "event_gate_pass": True,
            })

    seed_values = split_frame.groupby("repeat")["seed"].unique().to_dict()
    for repeat in range(1, n_repeats + 1):
        if list(seed_values[repeat]) != [_outer_seed(config, repeat)]:
            raise W07ValidationError("seed derivation mismatch")

    return {
        "rows": int(len(split_frame)),
        "training_rows": int((split_frame["role"] == "train").sum()),
        "validation_rows": int((split_frame["role"] == "validation").sum()),
        "n_repeats": n_repeats,
        "n_folds": n_splits,
        "n_outer_validation_folds": len(fold_event_counts),
        "event_gate_pass": all(row["event_gate_pass"]
                                for row in fold_event_counts),
        "minimum_train_events": min(row["train_events"]
                                     for row in fold_event_counts),
        "minimum_validation_events": min(row["validation_events"]
                                          for row in fold_event_counts),
        "maximum_train_events": max(row["train_events"]
                                     for row in fold_event_counts),
        "maximum_validation_events": max(row["validation_events"]
                                          for row in fold_event_counts),
        "fold_event_counts": fold_event_counts,
    }


def _canonical_csv_bytes(split_frame: pd.DataFrame) -> bytes:
    return split_frame[SPLIT_COLUMNS].to_csv(
        index=False, lineterminator="\n").encode("utf-8")


def _write_atomic(path: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(
        prefix="." + os.path.basename(path) + ".", suffix=".tmp",
        dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def run_w07(population_path: str = DEFAULT_POPULATION,
            output_path: str = DEFAULT_SPLITS,
            config_path: str = DEFAULT_CONFIG) -> dict:
    """Freeze the W07 split artifact and return aggregate provenance."""
    config = load_config(config_path)
    population = load_a_modeling_population(population_path, config)
    split_frame = build_outer_splits(population, config)
    validation = validate_outer_splits(split_frame, population, config)
    payload = _canonical_csv_bytes(split_frame)
    _write_atomic(output_path, payload)
    output_hash = hashlib.sha256(payload).hexdigest()
    if _sha256_file(output_path) != output_hash:
        raise W07ValidationError("outer split hash failed after write")
    return {
        "stage": "W07",
        "population": int(len(population)),
        "events": int(population["DFS_event"].sum()),
        "censors": int((population["DFS_event"] == 0).sum()),
        "population_source_sha256": _sha256_file(population_path),
        "outer_split_hash": output_hash,
        "same_plan_for": config["outer_cv"]["same_plan_for"],
        "population_eligibility_recorded": sorted(config["populations"]),
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        **validation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="W07 A-only outer split freeze")
    parser.add_argument("--population", default=DEFAULT_POPULATION,
                        help=argparse.SUPPRESS)
    parser.add_argument("--output", default=DEFAULT_SPLITS,
                        help=argparse.SUPPRESS)
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    summary = run_w07(args.population, args.output, args.config)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
