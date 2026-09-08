"""Independent A-only validation of the two frozen K-means initialisation counts.

This module deliberately consumes only the A technical supervoxel summary and
the frozen outer split table.  It does not import the formal modelling code or
any image/feature extraction implementation.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

# Set these before importing numerical libraries.  They also apply to spawned
# workers, and threadpool_limits below provides a second local guard.
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
              "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "1"

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

try:
    from threadpoolctl import threadpool_limits
except ImportError:  # pragma: no cover - the locked environment includes it
    @contextmanager
    def threadpool_limits(limits=1):
        yield


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUPERVOXEL_PATH = ROOT / "habitat_analysis" / "output" / \
    "local_global_diagnostic_A_post_slic_fix" / "supervoxel_mean_A.csv"
DEFAULT_SPLIT_PATH = ROOT / "prognosis_analysis" / "output" / \
    "outer_splits_A.csv"
DEFAULT_OUTPUT_DIR = ROOT / "prognosis_analysis" / "output" / \
    "n_init_equivalence_A"

REPEATS = tuple(range(1, 11))
FOLDS = tuple(range(1, 6))
EXPECTED_FOLD_COUNT = len(REPEATS) * len(FOLDS)
LOW = "R_low"
HIGH = "R_high"
DUAL = "dual"

FOLD_COLUMNS = [
    "repeat", "outer_fold", "seed", "training_patient_count",
    "training_supervoxel_count", "center_low_10", "center_high_10",
    "boundary_10", "inertia_10", "n_iter_10", "center_low_100",
    "center_high_100", "boundary_100", "inertia_100", "n_iter_100",
    "centers_exact_equal", "boundary_exact_equal", "inertia_exact_equal",
    "material_difference", "affected_supervoxels", "affected_cases",
    "support_state_changes", "eligibility_changes",
    "paired_population_changes", "G_value_changes",
]

ERROR_MESSAGE = "input validation failed"


class ValidationError(ValueError):
    """A safe, patient-identifier-free validation or execution error."""


class OutputConflictError(RuntimeError):
    """Raised when a prior result would otherwise be overwritten."""


def _as_identifier(series: pd.Series, label: str) -> pd.Series:
    if series.isna().any():
        raise ValidationError("%s contains missing identifiers" % label)
    values = series.astype(str).str.strip()
    if values.eq("").any():
        raise ValidationError("%s contains blank identifiers" % label)
    return values


def _integer_series(series: pd.Series, label: str) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise ValidationError("%s contains non-numeric values" % label)
    array = values.to_numpy(dtype=float)
    if not np.isfinite(array).all() or not np.equal(array, np.floor(array)).all():
        raise ValidationError("%s contains invalid integer values" % label)
    return values.astype(np.int64)


def _normalise_supervoxels(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"影像号", "reader", "sv_label", "Mean", "n_tumor_voxels"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValidationError("supervoxel table is missing required columns")
    data = frame.copy()
    data["_patient_id"] = _as_identifier(data["影像号"], "supervoxel table")
    readers = data["reader"].astype(str).str.strip()
    if not readers.eq("R1").all():
        raise ValidationError("supervoxel table contains non-R1 rows")
    labels = data["sv_label"]
    if labels.isna().any():
        raise ValidationError("supervoxel table contains missing supervoxel labels")
    data["_sv_label"] = labels.astype(str).str.strip()
    if data["_sv_label"].eq("").any():
        raise ValidationError("supervoxel table contains blank supervoxel labels")
    if data.duplicated(["_patient_id", "_sv_label"]).any():
        raise ValidationError("supervoxel labels are not unique within cases")

    means = pd.to_numeric(data["Mean"], errors="coerce")
    if means.isna().any() or not np.isfinite(means.to_numpy(dtype=float)).all():
        raise ValidationError("Mean contains non-finite values")
    data["_mean"] = means.astype(float)

    voxels = pd.to_numeric(data["n_tumor_voxels"], errors="coerce")
    if voxels.isna().any():
        raise ValidationError("n_tumor_voxels contains non-numeric values")
    voxel_array = voxels.to_numpy(dtype=float)
    if (not np.isfinite(voxel_array).all() or
            not np.equal(voxel_array, np.floor(voxel_array)).all() or
            not np.greater(voxel_array, 0).all()):
        raise ValidationError("n_tumor_voxels must be positive integers")
    data["_voxels"] = voxels.astype(np.int64)
    if data.empty:
        raise ValidationError("supervoxel table is empty")
    return data


def _normalise_splits(frame: pd.DataFrame) -> pd.DataFrame:
    required = {"patient_id", "repeat", "fold", "role"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValidationError("outer split table is missing required columns")
    data = frame.copy()
    data["_patient_id"] = _as_identifier(data["patient_id"], "outer split table")
    data["_repeat"] = _integer_series(data["repeat"], "repeat")
    data["_fold"] = _integer_series(data["fold"], "fold")
    data["_role"] = data["role"].astype(str).str.strip()
    if not data["_role"].isin(["train", "validation"]).all():
        raise ValidationError("outer split table contains an invalid role")
    if data.duplicated(["_patient_id", "_repeat", "_fold"]).any():
        raise ValidationError("outer split table contains duplicate fold membership")
    return data


def validate_inputs(supervoxels: pd.DataFrame,
                    splits: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame,
                                                   Set[str]]:
    """Validate all inputs before any K-means estimator is constructed."""
    sv = _normalise_supervoxels(supervoxels)
    split = _normalise_splits(splits)
    cohort = set(sv["_patient_id"])
    split_cohort = set(split["_patient_id"])
    if cohort != split_cohort:
        raise ValidationError("supervoxel table does not cover the split cohort")
    if len(cohort) == 0:
        raise ValidationError("A technical cohort is empty")
    if set(split["_repeat"]) != set(REPEATS):
        raise ValidationError("outer split table must contain ten repeats")
    if set(split["_fold"]) != set(FOLDS):
        raise ValidationError("outer split table must contain five folds")
    if set(zip(split["_repeat"], split["_fold"])) != {
            (repeat, fold) for repeat in REPEATS for fold in FOLDS}:
        raise ValidationError("outer split table does not contain 50 fold groups")

    for repeat in REPEATS:
        repeat_rows = split[split["_repeat"] == repeat]
        validation_counts = repeat_rows.loc[
            repeat_rows["_role"] == "validation", "_patient_id"].value_counts()
        training_counts = repeat_rows.loc[
            repeat_rows["_role"] == "train", "_patient_id"].value_counts()
        if (set(validation_counts.index) != cohort or
                not validation_counts.eq(1).all() or
                set(training_counts.index) != cohort or
                not training_counts.eq(len(FOLDS) - 1).all()):
            raise ValidationError("outer split validation coverage is incomplete")
        for fold in FOLDS:
            current = repeat_rows[repeat_rows["_fold"] == fold]
            train_ids = set(current.loc[current["_role"] == "train",
                                        "_patient_id"])
            validation_ids = set(current.loc[
                current["_role"] == "validation", "_patient_id"])
            if not train_ids or not validation_ids:
                raise ValidationError("outer split contains an empty fold role")
            if train_ids.intersection(validation_ids):
                raise ValidationError("training and validation IDs overlap")
            if train_ids.union(validation_ids) != cohort:
                raise ValidationError("fold roles do not cover the A cohort")
    return sv, split, cohort


def _fold_seed(repeat: int, fold: int) -> int:
    return 12345 + 2000 + 10 * (int(repeat) - 1) + int(fold)


def _fit_arm(values: np.ndarray, weights: np.ndarray, seed: int,
             n_init: int) -> Dict[str, object]:
    values = np.asarray(values, dtype=float).reshape(-1)
    weights = np.asarray(weights, dtype=float).reshape(-1)
    if values.size == 0 or values.size != weights.size:
        raise ValidationError("training supervoxel values and weights are invalid")
    if (not np.isfinite(weights).all() or not np.greater(weights, 0).all()):
        raise ValidationError("training sample weights are invalid")
    if np.unique(values).size < 2:
        raise ValidationError("training values do not support K=2")
    with threadpool_limits(limits=1):
        estimator = KMeans(
            n_clusters=2,
            init="k-means++",
            random_state=int(seed),
            n_init=int(n_init),
            max_iter=300,
            tol=1e-4,
        )
        estimator.fit(values.reshape(-1, 1), sample_weight=weights)
    centers = np.sort(estimator.cluster_centers_.reshape(-1).astype(float))
    return {
        "center_low": float(centers[0]),
        "center_high": float(centers[1]),
        "boundary": float((centers[0] + centers[1]) / 2.0),
        "inertia": float(estimator.inertia_),
        "n_iter": int(estimator.n_iter_),
    }


def _training_values_and_weights(training: pd.DataFrame) -> Tuple[np.ndarray,
                                                                  np.ndarray]:
    """Return values with exactly one unit of weight per training case."""
    ordered = training.sort_values(["_patient_id", "_sv_label"],
                                   kind="mergesort")
    counts = ordered.groupby("_patient_id", sort=False)["_sv_label"].transform(
        "size").to_numpy(dtype=float)
    weights = 1.0 / counts
    if not np.isfinite(weights).all():
        raise ValidationError("patient-balanced weights are invalid")
    by_case = pd.Series(weights, index=ordered["_patient_id"].to_numpy())
    totals = by_case.groupby(level=0, sort=False).sum().to_numpy(dtype=float)
    if not np.allclose(totals, 1.0, rtol=0.0, atol=1e-12):
        raise ValidationError("patient-balanced weights do not sum to one")
    return ordered["_mean"].to_numpy(dtype=float), weights


def _support_state(voxel_count: int) -> str:
    if int(voxel_count) == 0:
        return "structural_absence"
    if int(voxel_count) < 10:
        return "technical_small_roi"
    return "extractable"


def _propagate(frame: pd.DataFrame, boundary: float) -> Tuple[pd.DataFrame,
                                                               np.ndarray]:
    ordered = frame.sort_values(["_patient_id", "_sv_label"],
                                kind="mergesort").reset_index(drop=True)
    labels = (ordered["_mean"].to_numpy(dtype=float) >= float(boundary))
    rows = []
    for identifier, group in ordered.groupby("_patient_id", sort=True):
        means = group["_mean"].to_numpy(dtype=float)
        voxels = group["_voxels"].to_numpy(dtype=np.int64)
        high = means >= float(boundary)
        low_count = int(voxels[~high].sum())
        high_count = int(voxels[high].sum())
        rows.append({
            "_patient_id": identifier,
            "R_low_voxel_count": low_count,
            "R_high_voxel_count": high_count,
            "R_low_state": _support_state(low_count),
            "R_high_state": _support_state(high_count),
            "sv_median_minus_boundary": float(np.median(means) - boundary),
        })
    return pd.DataFrame(rows).set_index("_patient_id"), labels


def _population_sets(case_frame: pd.DataFrame) -> Dict[str, Set[str]]:
    low = set(case_frame.index[
        case_frame["R_low_state"].eq("extractable")])
    high = set(case_frame.index[
        case_frame["R_high_state"].eq("extractable")])
    return {LOW: low, HIGH: high, DUAL: low.intersection(high)}


def compare_fold(supervoxels: pd.DataFrame, splits: pd.DataFrame,
                  repeat: int, fold: int) -> Tuple[Dict[str, object],
                                                  pd.DataFrame]:
    """Fit both arms for one fold and compare the propagated model inputs."""
    repeat = int(repeat)
    fold = int(fold)
    current = splits[(splits["_repeat"] == repeat) &
                     (splits["_fold"] == fold)]
    train_ids = sorted(set(current.loc[current["_role"] == "train",
                                      "_patient_id"]))
    fold_ids = sorted(set(current["_patient_id"]))
    training = supervoxels[supervoxels["_patient_id"].isin(train_ids)]
    values, weights = _training_values_and_weights(training)
    seed = _fold_seed(repeat, fold)
    arm10 = _fit_arm(values, weights, seed, 10)
    arm100 = _fit_arm(values, weights, seed, 100)

    centers_equal = bool(np.array_equal(
        np.asarray([arm10["center_low"], arm10["center_high"]]),
        np.asarray([arm100["center_low"], arm100["center_high"]])))
    boundary_equal = bool(arm10["boundary"] == arm100["boundary"])
    inertia_equal = bool(arm10["inertia"] == arm100["inertia"])
    arm10_case = None
    arm100_case = None
    labels_changed = np.array([], dtype=bool)
    affected_cases: Set[str] = set()
    support_state_changes = 0
    eligibility_changes = 0
    paired_population_changes = 0
    g_changes = 0
    affected_case_rows = []

    fold_frame = supervoxels[supervoxels["_patient_id"].isin(fold_ids)]
    if not centers_equal or not boundary_equal:
        arm10_case, labels10 = _propagate(fold_frame, arm10["boundary"])
        arm100_case, labels100 = _propagate(fold_frame, arm100["boundary"])
        labels_changed = labels10 != labels100
        affected_supervoxels = int(labels_changed.sum())
        populations10 = _population_sets(arm10_case)
        populations100 = _population_sets(arm100_case)
        changed_population_names = [
            name for name in (LOW, HIGH, DUAL)
            if populations10[name] != populations100[name]
        ]
        paired_population_changes = len(changed_population_names)
        eligibility_changes = len(set().union(*[
            populations10[name].symmetric_difference(populations100[name])
            for name in (LOW, HIGH, DUAL)]))
        state_columns = ["R_low_state", "R_high_state"]
        support_state_changes = int(sum(
            (arm10_case[column] != arm100_case[column]).sum()
            for column in state_columns))
        g_delta = arm10_case["sv_median_minus_boundary"] != \
            arm100_case["sv_median_minus_boundary"]
        g_changes = int(g_delta.sum())
        count_delta = (
            (arm10_case["R_low_voxel_count"] !=
             arm100_case["R_low_voxel_count"]) |
            (arm10_case["R_high_voxel_count"] !=
             arm100_case["R_high_voxel_count"]))
        state_delta = pd.Series(False, index=arm10_case.index)
        for column in state_columns:
            state_delta |= arm10_case[column] != arm100_case[column]
        eligibility_delta = pd.Series(False, index=arm10_case.index)
        for name in (LOW, HIGH, DUAL):
            eligibility_delta |= pd.Series(
                arm10_case.index.isin(populations10[name]) !=
                arm10_case.index.isin(populations100[name]),
                index=arm10_case.index)
        affected_mask = (
            pd.Series(labels_changed, index=fold_frame.sort_values(
                ["_patient_id", "_sv_label"], kind="mergesort").index)
            .groupby(fold_frame.sort_values(
                ["_patient_id", "_sv_label"], kind="mergesort")["_patient_id"])
            .any())
        affected_mask = affected_mask.reindex(arm10_case.index, fill_value=False)
        affected_mask |= count_delta | state_delta | eligibility_delta | g_delta
        affected_cases = set(arm10_case.index[affected_mask])
        for identifier in sorted(affected_cases):
            affected_case_rows.append({
                "repeat": repeat,
                "outer_fold": fold,
                "patient_id": identifier,
                "R_low_voxel_count_10": int(
                    arm10_case.loc[identifier, "R_low_voxel_count"]),
                "R_low_voxel_count_100": int(
                    arm100_case.loc[identifier, "R_low_voxel_count"]),
                "R_high_voxel_count_10": int(
                    arm10_case.loc[identifier, "R_high_voxel_count"]),
                "R_high_voxel_count_100": int(
                    arm100_case.loc[identifier, "R_high_voxel_count"]),
                "R_low_state_10": arm10_case.loc[identifier, "R_low_state"],
                "R_low_state_100": arm100_case.loc[identifier, "R_low_state"],
                "R_high_state_10": arm10_case.loc[identifier, "R_high_state"],
                "R_high_state_100": arm100_case.loc[identifier, "R_high_state"],
                "sv_median_minus_boundary_10": float(
                    arm10_case.loc[identifier, "sv_median_minus_boundary"]),
                "sv_median_minus_boundary_100": float(
                    arm100_case.loc[identifier, "sv_median_minus_boundary"]),
            })
    else:
        affected_supervoxels = 0

    material = bool(
        affected_supervoxels or support_state_changes or
        eligibility_changes or paired_population_changes or g_changes)
    row = {
        "repeat": repeat,
        "outer_fold": fold,
        "seed": seed,
        "training_patient_count": len(train_ids),
        "training_supervoxel_count": int(len(training)),
        "center_low_10": arm10["center_low"],
        "center_high_10": arm10["center_high"],
        "boundary_10": arm10["boundary"],
        "inertia_10": arm10["inertia"],
        "n_iter_10": arm10["n_iter"],
        "center_low_100": arm100["center_low"],
        "center_high_100": arm100["center_high"],
        "boundary_100": arm100["boundary"],
        "inertia_100": arm100["inertia"],
        "n_iter_100": arm100["n_iter"],
        "centers_exact_equal": centers_equal,
        "boundary_exact_equal": boundary_equal,
        "inertia_exact_equal": inertia_equal,
        "material_difference": material,
        "affected_supervoxels": affected_supervoxels,
        "affected_cases": len(affected_cases),
        "support_state_changes": support_state_changes,
        "eligibility_changes": eligibility_changes,
        "paired_population_changes": paired_population_changes,
        "G_value_changes": g_changes,
    }
    return row, pd.DataFrame(affected_case_rows)


_WORKER_SUPERVOXELS = None
_WORKER_SPLITS = None


def _init_worker(supervoxels: pd.DataFrame, splits: pd.DataFrame) -> None:
    global _WORKER_SUPERVOXELS, _WORKER_SPLITS
    _WORKER_SUPERVOXELS = supervoxels
    _WORKER_SPLITS = splits
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"


def _worker_fold(spec: Tuple[int, int]):
    repeat, fold = spec
    try:
        row, affected = compare_fold(_WORKER_SUPERVOXELS, _WORKER_SPLITS,
                                     repeat, fold)
        return {"row": row, "affected": affected, "error": None}
    except Exception as exc:  # return safe text through the parent process
        return {"row": None, "affected": pd.DataFrame(),
                "error": "%s: %s" % (type(exc).__name__, str(exc))}


def _empty_summary(status: str = "INCOMPLETE") -> Dict[str, object]:
    return {
        "status": status,
        "folds_completed": 0,
        "folds_exact_equal": 0,
        "folds_with_center_difference": 0,
        "folds_with_boundary_difference": 0,
        "affected_supervoxels": 0,
        "affected_cases": 0,
        "support_state_changes": 0,
        "eligibility_changes": 0,
        "paired_population_changes": 0,
        "G_value_changes": 0,
        "stopped_early": False,
        "outcome_data_read": False,
        "clinical_data_read": False,
        "B_data_read": False,
        "cox_fit_generated": False,
        "prediction_generated": False,
        "performance_generated": False,
    }


def _write_outputs(output_dir: Path, fold_rows: Sequence[Mapping[str, object]],
                   affected: pd.DataFrame, summary: Mapping[str, object],
                   error: Optional[str] = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    fold_frame = pd.DataFrame(list(fold_rows), columns=FOLD_COLUMNS)
    if not fold_frame.empty:
        fold_frame = fold_frame.sort_values(["repeat", "outer_fold"],
                                            kind="mergesort")
    fold_frame.to_csv(output_dir / "n_init_fold_comparison.csv",
                      index=False, encoding="utf-8-sig")
    if not affected.empty:
        affected.sort_values(["repeat", "outer_fold", "patient_id"],
                             kind="mergesort").to_csv(
                                 output_dir / "n_init_affected_cases.csv",
                                 index=False, encoding="utf-8-sig")
    with (output_dir / "n_init_equivalence_summary.json").open(
            "w", encoding="utf-8") as handle:
        json.dump(dict(summary), handle, ensure_ascii=False, indent=2,
                  sort_keys=True)
    lines = [
        "# n_init equivalence verification",
        "",
        "- status: `%s`" % summary["status"],
        "- folds completed: %d/%d" % (
            summary["folds_completed"], EXPECTED_FOLD_COUNT),
        "- folds exactly equal: %d" % summary["folds_exact_equal"],
        "- folds with center difference: %d" %
        summary["folds_with_center_difference"],
        "- folds with boundary difference: %d" %
        summary["folds_with_boundary_difference"],
        "- affected supervoxels: %d" % summary["affected_supervoxels"],
        "- affected cases: %d" % summary["affected_cases"],
        "- support-state changes: %d" % summary["support_state_changes"],
        "- eligibility changes: %d" % summary["eligibility_changes"],
        "- paired-population changes: %d" %
        summary["paired_population_changes"],
        "- `sv_median_minus_boundary` changes: %d" %
        summary["G_value_changes"],
        "- stopped early: `%s`" % summary["stopped_early"],
        "",
        "Inputs were limited to the A technical supervoxel summary and the "
        "frozen outer split roles. No outcome, clinical, B-set, prediction, "
        "or performance data were read or generated.",
    ]
    if error:
        lines.extend(["", "Execution note: %s" % error])
    (output_dir / "n_init_equivalence_report.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")


def _assert_output_is_new(output_dir: Path) -> None:
    targets = [
        "n_init_fold_comparison.csv",
        "n_init_affected_cases.csv",
        "n_init_equivalence_summary.json",
        "n_init_equivalence_report.md",
    ]
    existing = [name for name in targets if (output_dir / name).exists()]
    if existing:
        raise OutputConflictError(
            "output directory contains existing result files: %s" %
            ", ".join(existing))


def run_validation(supervoxels: pd.DataFrame, splits: pd.DataFrame,
                   output_dir: Path,
                   workers: int = 2,
                   stop_on_first_material_difference: bool = True) -> Dict[str,
                                                                           object]:
    """Run the independent comparison and write only the four N1 artifacts."""
    if int(workers) not in (1, 2):
        raise ValueError("workers must be 1 or 2")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _assert_output_is_new(output_dir)
    fold_rows = []
    affected_frames = []
    summary = _empty_summary()
    execution_error = None
    try:
        sv, split, _ = validate_inputs(supervoxels, splits)
    except Exception as exc:
        execution_error = "%s: %s" % (type(exc).__name__, str(exc))
        summary["error_summary"] = ERROR_MESSAGE
        _write_outputs(output_dir, fold_rows, pd.DataFrame(), summary,
                       execution_error)
        return summary

    specs = [(repeat, fold) for repeat in REPEATS for fold in FOLDS]
    results = []
    if int(workers) == 1:
        _init_worker(sv, split)
        for spec in specs:
            result = _worker_fold(spec)
            results.append(result)
            if result["error"] or (stop_on_first_material_difference and
                                    result["row"] and
                                    result["row"]["material_difference"]):
                break
    else:
        context = mp.get_context("spawn")
        pool = context.Pool(processes=int(workers), initializer=_init_worker,
                            initargs=(sv, split))
        try:
            for result in pool.imap_unordered(_worker_fold, specs):
                results.append(result)
                if result["error"] or (stop_on_first_material_difference and
                                        result["row"] and
                                        result["row"]["material_difference"]):
                    pool.terminate()
                    break
            else:
                pool.close()
        finally:
            pool.join()

    stopped_early = False
    error_messages = []
    for result in results:
        if result["error"]:
            error_messages.append(result["error"])
            continue
        row = result["row"]
        fold_rows.append(row)
        affected = result["affected"]
        if not affected.empty:
            affected_frames.append(affected)
        if stop_on_first_material_difference and row["material_difference"]:
            stopped_early = True
    if error_messages:
        execution_error = "fold execution failed: %s" % error_messages[0]
    summary["folds_completed"] = len(fold_rows)
    summary["folds_exact_equal"] = sum(
        bool(row["centers_exact_equal"] and row["boundary_exact_equal"] and
             row["inertia_exact_equal"]) for row in fold_rows)
    summary["folds_with_center_difference"] = sum(
        not bool(row["centers_exact_equal"]) for row in fold_rows)
    summary["folds_with_boundary_difference"] = sum(
        not bool(row["boundary_exact_equal"]) for row in fold_rows)
    for field in ("affected_supervoxels", "support_state_changes",
                  "eligibility_changes", "paired_population_changes",
                  "G_value_changes"):
        summary[field] = int(sum(int(row[field]) for row in fold_rows))
    affected = (pd.concat(affected_frames, ignore_index=True)
                if affected_frames else pd.DataFrame())
    summary["affected_cases"] = (int(affected["patient_id"].nunique())
                                  if not affected.empty else 0)
    summary["stopped_early"] = bool(stopped_early)
    material_found = any(bool(row["material_difference"]) for row in fold_rows)
    if material_found:
        summary["status"] = "NOT_EQUIVALENT"
    elif execution_error or len(fold_rows) != EXPECTED_FOLD_COUNT:
        summary["status"] = "INCOMPLETE"
    elif summary["folds_with_center_difference"] or any(
            not bool(row["inertia_exact_equal"]) for row in fold_rows):
        summary["status"] = "INPUT_EQUIVALENT_WITH_NUMERICAL_DIFFERENCE"
    else:
        summary["status"] = "EXACT_EQUIVALENCE"
    if execution_error:
        summary["error_summary"] = ERROR_MESSAGE
    _write_outputs(output_dir, fold_rows, affected, summary, execution_error)
    return summary


def _load_inputs(supervoxel_path: Path, split_path: Path) -> Tuple[pd.DataFrame,
                                                                    pd.DataFrame]:
    if not supervoxel_path.is_file() or not split_path.is_file():
        raise ValidationError("required A technical input file is missing")
    return (
        pd.read_csv(supervoxel_path, dtype={"影像号": str}),
        pd.read_csv(split_path, dtype={"patient_id": str}),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate A-only K-means n_init equivalence.")
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    stop = parser.add_mutually_exclusive_group()
    stop.add_argument("--stop-on-first-material-difference",
                      dest="stop_on_first_material_difference",
                      action="store_true")
    stop.add_argument("--no-stop-on-first-material-difference",
                      dest="stop_on_first_material_difference",
                      action="store_false")
    parser.set_defaults(stop_on_first_material_difference=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        supervoxels, splits = _load_inputs(DEFAULT_SUPERVOXEL_PATH,
                                           DEFAULT_SPLIT_PATH)
        summary = run_validation(
            supervoxels, splits, args.output_dir, workers=args.workers,
            stop_on_first_material_difference=
            args.stop_on_first_material_difference)
    except OutputConflictError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print("%s: %s" % (type(exc).__name__, str(exc)), file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
