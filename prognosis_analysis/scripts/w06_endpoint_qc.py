"""W06: first A-only DFS read, endpoint QC, and modeling-population freeze.

The first-stage technical freeze is validated before any source is opened. The
two frozen technical A ID lists are then used as the allow-list for a narrow
DFS-only read through the W05 A-outcome reader. No B reader, B source, or
legacy modeling builder is used here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from typing import Dict, Iterable, Set

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
DATA_XLSX = os.path.join(ROOT, "data", "radiology_clinic_pathology_prognosis_data.xlsx")
TECHNICAL_COHORT = os.path.join(PROJECT_ROOT, "habitat_analysis", "output",
                                "technical_cohort_manifest")
TECHNICAL_A393 = os.path.join(TECHNICAL_COHORT, "cohort_A_lenient.csv")
TECHNICAL_A137 = os.path.join(TECHNICAL_COHORT, "cohort_A_strict.csv")
FREEZE_LOCK = os.path.join(PROJECT_ROOT, "habitat_analysis", "freeze_lock.json")
MODEL_FREEZE_LOCK = os.path.join(ROOT, "model_freeze_lock.json")
OUTPUT_ROOT = os.path.join(ROOT, "output")
QC_ROOT = os.path.join(OUTPUT_ROOT, "A_endpoint_qc")
MODEL_ROOT = os.path.join(OUTPUT_ROOT, "A_modeling")
MODEL_POPULATION = os.path.join(MODEL_ROOT, "A_modeling_population.csv")

FEATURE_SCRIPTS = os.path.join(PROJECT_ROOT, "feature_extract", "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import read_A_outcomes, read_technical_A  # noqa: E402
from freeze_lock import validate_freeze_lock  # noqa: E402

ID_COLUMN = "影像号"
TIME_COLUMN = "DFS_time"
EVENT_COLUMN = "DFS_event"
OUTCOME_COLUMNS = [ID_COLUMN, TIME_COLUMN, EVENT_COLUMN]
HORIZONS_MONTHS = {"3_year": 36.0, "5_year": 60.0}
EXPECTED_A393 = 393
EXPECTED_A137 = 137


def _normalize_ids(frame: pd.DataFrame, label: str) -> Set[str]:
    if ID_COLUMN not in frame.columns:
        raise AssertionError("%s lacks %s" % (label, ID_COLUMN))
    values = frame[ID_COLUMN].astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise AssertionError("%s identifiers must be nonempty and unique" % label)
    return set(values)


def load_frozen_a_ids() -> Dict[str, Set[str]]:
    """Read the two frozen A technical ID lists, and nothing clinical."""
    a393 = read_technical_A(TECHNICAL_A393, allow_full=True,
                            dtype={ID_COLUMN: str})
    a137 = read_technical_A(TECHNICAL_A137, allow_full=True,
                            dtype={ID_COLUMN: str})
    ids = {"A393": _normalize_ids(a393, "A393 technical cohort"),
           "A137": _normalize_ids(a137, "A137 technical cohort")}
    if len(ids["A393"]) != EXPECTED_A393:
        raise AssertionError("A393 technical cohort must contain 393 unique IDs")
    if len(ids["A137"]) != EXPECTED_A137:
        raise AssertionError("A137 technical cohort must contain 137 unique IDs")
    if not ids["A137"].issubset(ids["A393"]):
        raise AssertionError("A137 technical cohort is not a subset of A393")
    return ids


def _raw_missing(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype(str).str.strip().eq("")


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def reverse_km_median_followup(times: Iterable[float], events: Iterable[int]):
    """Return the reverse-KM median, treating DFS censoring as the event."""
    table = pd.DataFrame({"time": list(times), "event": list(events)})
    table = table.replace([float("inf"), float("-inf")], pd.NA).dropna()
    if table.empty:
        return None
    table = table.sort_values("time", kind="mergesort")
    at_risk = float(len(table))
    survival = 1.0
    for time, group in table.groupby("time", sort=True):
        censor_events = int((group["event"] == 0).sum())
        if censor_events:
            survival *= 1.0 - (float(censor_events) / at_risk)
        if survival <= 0.5:
            return float(time)
        at_risk -= float(len(group))
    return None


def _event_time_masks(frame: pd.DataFrame):
    raw_time_missing = _raw_missing(frame[TIME_COLUMN])
    raw_event_missing = _raw_missing(frame[EVENT_COLUMN])
    time = _numeric(frame[TIME_COLUMN])
    event = _numeric(frame[EVENT_COLUMN])
    nonnumeric_time = (~raw_time_missing) & time.isna()
    nonnumeric_event = (~raw_event_missing) & event.isna()
    nonbinary_event = event.notna() & ~event.isin([0, 1])
    missing = raw_time_missing | raw_event_missing
    time_le_zero = time.notna() & time.le(0)
    conflict = ((~missing) & (nonnumeric_time | nonnumeric_event | nonbinary_event))
    valid = (~missing & ~conflict & time.notna() & event.isin([0, 1]) &
             time.gt(0))
    return time, event, missing, time_le_zero, conflict, valid


def _reverse_km_summary(times: pd.Series, events: pd.Series) -> Dict[str, object]:
    median = reverse_km_median_followup(times.tolist(), events.tolist())
    return {
        "method": "reverse_KM; DFS_event=0 treated as censoring event",
        "time_unit": "months",
        "median_months": median,
    }


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                                     suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _atomic_csv(path: str, frame: pd.DataFrame) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + os.path.basename(path) + ".",
                                     suffix=".tmp", dir=os.path.dirname(path))
    os.close(fd)
    try:
        frame.to_csv(temporary, index=False, encoding="utf-8-sig")
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _summary_rows(summary: dict):
    rows = []
    counts = summary["counts"]
    for key, value in counts.items():
        rows.append({"section": "counts", "metric": key, "value": value})
    for key, value in summary["follow_up_months"].items():
        rows.append({"section": "follow_up_months", "metric": key, "value": value})
    rows.append({"section": "reverse_KM", "metric": "median_months",
                 "value": summary["reverse_KM"]["median_months"]})
    for key, value in summary["horizon_evaluable"].items():
        rows.append({"section": "horizon_evaluable", "metric": key, "value": value})
    return pd.DataFrame(rows, columns=["section", "metric", "value"])


def _write_audit(summary: dict, outcome_rows: int, outcome_columns: list,
                 freeze_payload: dict, model_lock_exists: bool,
                 qc_root: str) -> None:
    audit = {
        "audit_name": "W06_outcome_read_audit",
        "workflow_stage": "W06",
        "first_a_dfs_read": True,
        "authorized_data_scope": "A DFS endpoint only",
        "technical_id_read_order": ["A393", "A137"],
        "technical_reader_api": "read_technical_A",
        "outcome_reader_api": "read_A_outcomes",
        "outcome_columns_requested": OUTCOME_COLUMNS,
        "outcome_rows_returned": outcome_rows,
        "outcome_columns_returned": outcome_columns,
        "freeze_lock_validation": {
            "performed_before_source_read": True,
            "valid": True,
            "A_outcome_unlock": bool(freeze_payload["A_outcome_unlock"]),
            "B_unlock": bool(freeze_payload["B_unlock"]),
        },
        "B_access_boundary": {
            "model_freeze_lock_exists": bool(model_lock_exists),
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_data_read": False,
            "B_statistics_generated": False,
        },
        "aggregate_qc": {
            "A393_total": summary["counts"]["A393_total"],
            "DFS_event_count": summary["counts"]["DFS_event_count"],
            "censor_count": summary["counts"]["censor_count"],
            "missing_outcome": summary["counts"]["missing_outcome"],
            "DFS_time_le_zero": summary["counts"]["DFS_time_le_zero"],
            "duplicated_ID": summary["counts"]["duplicated_ID"],
            "event_time_conflict": summary["counts"]["event_time_conflict"],
        },
        "patient_identifiers_in_audit": False,
        "original_paths_in_audit": False,
    }
    _atomic_json(os.path.join(qc_root, "outcome_read_audit.json"), audit)
    lines = [
        "# W06 outcome read audit",
        "",
        "- Stage: W06",
        "- Scope: A DFS endpoint only",
        "- First-stage freeze lock: valid before source read",
        "- A outcome reader: `read_A_outcomes`",
        "- Requested columns: `影像号`, `DFS_time`, `DFS_event`",
        "- A rows returned: %d" % outcome_rows,
        "- B source opened: no",
        "- B data/statistics read or generated: no",
        "- Patient identifiers in this audit: no",
        "",
        "All reported values are aggregate counts or summaries; the local "
        "patient-level modeling population is stored separately.",
    ]
    with open(os.path.join(qc_root, "outcome_read_audit.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def run_w06(data_path: str = DATA_XLSX, output_root: str = OUTPUT_ROOT) -> dict:
    """Run W06 and return the aggregate endpoint summary."""
    qc_root = os.path.join(output_root, "A_endpoint_qc")
    model_root = os.path.join(output_root, "A_modeling")
    model_population = os.path.join(model_root, "A_modeling_population.csv")

    # This is deliberately the first operation touching any source artifact.
    freeze_payload = validate_freeze_lock(FREEZE_LOCK)
    if not freeze_payload.get("A_outcome_unlock") or freeze_payload.get("B_unlock"):
        raise RuntimeError("technical freeze lock does not authorize A-only outcome read")
    if os.path.exists(MODEL_FREEZE_LOCK):
        raise RuntimeError("model_freeze_lock.json must not exist during W06")

    technical_ids = load_frozen_a_ids()
    allowed_ids = technical_ids["A393"]
    outcomes = read_A_outcomes(
        data_path,
        allowed_ids=allowed_ids,
        dtype={ID_COLUMN: str},
        usecols=OUTCOME_COLUMNS,
    )
    if set(outcomes.columns) != set(OUTCOME_COLUMNS):
        raise AssertionError("A DFS reader returned unexpected columns")
    outcomes[ID_COLUMN] = outcomes[ID_COLUMN].astype(str).str.strip()

    duplicate_rows = outcomes[ID_COLUMN].duplicated(keep=False)
    duplicate_ids = int(outcomes.loc[duplicate_rows, ID_COLUMN].nunique())
    duplicate_row_count = int(duplicate_rows.sum())
    time, event, missing, time_le_zero, conflict, valid = _event_time_masks(outcomes)
    returned_ids = set(outcomes[ID_COLUMN])
    unavailable_ids = allowed_ids - returned_ids
    missing_outcome = int(missing.sum()) + len(unavailable_ids)
    eligible = valid & ~duplicate_rows

    event_count = int((event.eq(1) & eligible).sum())
    censor_count = int((event.eq(0) & eligible).sum())
    valid_times = time[eligible]
    valid_events = event[eligible].astype(int)
    if len(valid_times) == 0:
        raise RuntimeError("no valid A DFS records remain after endpoint QC")

    followup = {
        "unit": "months",
        "n": int(len(valid_times)),
        "min": float(valid_times.min()),
        "q1": float(valid_times.quantile(0.25)),
        "median": float(valid_times.quantile(0.50)),
        "q3": float(valid_times.quantile(0.75)),
        "max": float(valid_times.max()),
        "mean": float(valid_times.mean()),
        "sd": float(valid_times.std(ddof=1)) if len(valid_times) > 1 else 0.0,
    }
    summary = {
        "workflow_stage": "W06",
        "endpoint": {
            "name": "DFS",
            "time_column": TIME_COLUMN,
            "event_column": EVENT_COLUMN,
            "time_unit": "months",
            "horizon_months": HORIZONS_MONTHS,
        },
        "counts": {
            "A393_total": len(allowed_ids),
            "A393_technical_unique": len(allowed_ids),
            "A393_outcome_rows_returned": int(len(outcomes)),
            "A393_outcome_unique_ids": int(outcomes[ID_COLUMN].nunique()),
            "DFS_event_count": event_count,
            "censor_count": censor_count,
            "missing_outcome": missing_outcome,
            "outcome_unavailable_source_ids": int(len(unavailable_ids)),
            "DFS_time_le_zero": int(time_le_zero.sum()),
            "duplicated_ID": duplicate_ids,
            "duplicated_ID_rows": duplicate_row_count,
            "event_time_conflict": int(conflict.sum()),
            "frozen_technical_exclusion": 0,
            "A_modeling_population": int(eligible.sum()),
        },
        "follow_up_months": followup,
        "reverse_KM": _reverse_km_summary(valid_times, valid_events),
        "horizon_evaluable": {
            "3_year": int(valid_times.ge(HORIZONS_MONTHS["3_year"]).sum()),
            "5_year": int(valid_times.ge(HORIZONS_MONTHS["5_year"]).sum()),
        },
        "quality_rules": {
            "missing_outcome": "raw blank/missing DFS_time or DFS_event; source IDs absent from the authorized read are also unavailable",
            "DFS_time_le_zero": "numeric DFS_time <= 0; reported separately from conflict",
            "event_time_conflict": "nonempty DFS_time/DFS_event with nonnumeric time or nonnumeric/nonbinary event",
            "horizon_evaluable": "valid DFS_time >= 36 or 60 months, respectively",
        },
        "eligibility_rule": {
            "include": "A393 technical ID with exactly one row, available numeric DFS_time>0, and DFS_event in {0,1}",
            "exclude_only": ["frozen technical exclusion", "outcome unavailable", "duplicated ID", "DFS_time<=0", "event/time conflict", "explicit unrepairable source-data error"],
            "performance_based_exclusion": False,
        },
        "data_integrity": {
            "A137_technical_unique": len(technical_ids["A137"]),
            "A137_subset_A393": True,
            "raw_source_correction": False,
            "DFS_definition_changed": False,
            "censor_rule_changed": False,
            "follow_up_cutoff_changed": False,
            "eligibility_changed": False,
            "technical_cohort_changed": False,
        },
    }
    if event_count + censor_count != int(eligible.sum()):
        raise AssertionError("valid A DFS records are not binary event/censor partition")

    population = outcomes.loc[eligible, OUTCOME_COLUMNS].copy()
    population["technical_cohort"] = "A393"
    population["modeling_eligible"] = 1
    population = population[[ID_COLUMN, "technical_cohort", TIME_COLUMN,
                              EVENT_COLUMN, "modeling_eligible"]]
    _atomic_csv(model_population, population)
    summary["A_modeling_population_sha256"] = _sha256(model_population)
    _atomic_json(os.path.join(qc_root, "endpoint_qc_summary.json"), summary)
    _atomic_csv(os.path.join(qc_root, "endpoint_qc_summary.csv"),
                _summary_rows(summary))
    _atomic_json(os.path.join(model_root, "A_modeling_population_schema.json"), {
        "file": "A_modeling_population.csv",
        "columns": list(population.columns),
        "n_rows": int(len(population)),
        "patient_level_local_sensitive": True,
        "eligibility_source": "W06 endpoint QC only",
    })
    _write_audit(summary, len(outcomes), list(outcomes.columns), freeze_payload,
                 os.path.exists(MODEL_FREEZE_LOCK), qc_root)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="W06 A-only DFS endpoint QC")
    parser.add_argument("--split", choices=["A", "B", "all"], default="A")
    parser.add_argument("--data", default=DATA_XLSX)
    parser.add_argument("--out-root", default=OUTPUT_ROOT)
    args = parser.parse_args()
    if args.split != "A":
        raise RuntimeError("W06 is A-only; B/all are disabled until model_freeze_lock.json")
    summary = run_w06(args.data, args.out_root)
    print("W06 complete: A393=%d, DFS events=%d, censors=%d, modeling=%d" % (
        summary["counts"]["A393_total"],
        summary["counts"]["DFS_event_count"],
        summary["counts"]["censor_count"],
        summary["counts"]["A_modeling_population"]))


if __name__ == "__main__":
    main()
