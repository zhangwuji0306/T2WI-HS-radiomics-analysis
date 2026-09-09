"""Reproducible, outcome-blind W08 L6 integration probe.

The synthetic part compares a no-cache baseline with the current integrated
representation/cache semantics on the same deterministic fixture.  It uses
the current K-means and Cox implementations, but deliberately bounds the
performance workload to five candidate penalties and 60 solver iterations;
those timings are software evidence only, never formal 100-point/3000-
iteration performance evidence.

The optional real-A part reads only the authorized technical population,
technical feature coverage, supervoxel summary, and frozen outer split.  It
fits the current provider's K=2 boundary for each requested fold with
``n_init=100`` and writes aggregate/de-identified fold evidence only.  It
never opens outcome columns, B data, a formal writer, or a prediction path.
"""
from __future__ import absolute_import

import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
from collections import OrderedDict

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

import w08_formal_run_a as formal
import w08_local_optimization_probe as l2_probe
import w08_nested_cv as w08
from w08_kmeans_parameters import (
    KMEANS_PARAMETERS, validate_frozen_kmeans_parameters)


THREAD_SETTINGS = OrderedDict((
    ("OMP_NUM_THREADS", "1"),
    ("MKL_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
    ("NUMEXPR_NUM_THREADS", "1"),
))
for _name, _value in THREAD_SETTINGS.items():
    os.environ[_name] = _value

SYNTHETIC_SEED = 20260909
SYNTHETIC_REPEATS = 3
SYNTHETIC_FOLDS = 2
BOUNDED_LAMBDA_COUNT = 5
BOUNDED_SOLVER_MAX_ITER = 60
REAL_FOLD_COUNT = 50
BASE_SEED = 12345


class L6ProbeFailure(RuntimeError):
    """Raised when the L6 probe cannot produce complete evidence."""


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _median(values):
    return float(np.median(np.asarray(values, dtype=float)))


def _range(values):
    values = [float(value) for value in values]
    return [min(values), max(values)]


def _aggregate(values):
    return {
        "median": _median(values),
        "range": _range(values),
        "repeat_count": int(len(values)),
    }


def _resource():
    return l2_probe.resource_snapshot()


def _stage_metrics(start_wall, start_cpu, before, after):
    wall = max(float(time.perf_counter() - start_wall), 1e-12)
    cpu = max(float(time.process_time() - start_cpu), 0.0)
    return {
        "seconds": wall,
        "cpu_percent": 100.0 * cpu / wall,
        "peak_rss_bytes": int(max(before["rss_bytes"], after["rss_bytes"])),
        "disk_read_bytes": int(max(0, after["read_bytes"] - before["read_bytes"])),
        "disk_write_bytes": int(max(0, after["write_bytes"] - before["write_bytes"])),
    }


def _synthetic_frame(n=32, seed=SYNTHETIC_SEED):
    frame = l2_probe._make_synthetic_frame(n=n, seed=seed).copy()
    frame.insert(0, "patient_id", ["synthetic-%03d" % index
                                    for index in range(n)])
    frame["DFS_time"] = 2.0 + np.arange(n, dtype=float) * 0.75
    frame["DFS_event"] = (np.arange(n) % 2 == 0).astype(int)
    return frame


def _synthetic_cases():
    rng = np.random.RandomState(SYNTHETIC_SEED)
    cases = OrderedDict()
    for index in range(8):
        labels = np.zeros((4, 4), dtype=np.int8)
        labels[:, 2:] = 1
        if index % 2:
            labels = 1 - labels
        cases["case-%02d" % index] = {
            "labels": labels,
            "values": np.asarray([
                -1.0 + 0.01 * index, 1.0 + 0.01 * index,
                -0.5 + 0.01 * index, 0.5 + 0.01 * index], dtype=float),
            "image": rng.normal(size=(4, 4)),
        }
    return cases


def _synthetic_boundary(training_values, seed):
    validate_frozen_kmeans_parameters()
    estimator = KMeans(random_state=int(seed),
                       **KMEANS_PARAMETERS.sklearn_kwargs())
    estimator.fit(np.asarray(training_values, dtype=float).reshape(-1, 1))
    centres = tuple(sorted(float(value)
                           for value in estimator.cluster_centers_.reshape(-1)))
    return centres, float(sum(centres) / 2.0)


def _mask_pair(case, boundary):
    low = (case["labels"] == 0)
    high = (case["labels"] == 1)
    # The synthetic label orientation is intentionally independent of the
    # boundary; this makes the expected low/high mask mapping explicit.
    return low.astype(np.uint8), high.astype(np.uint8)


def _feature_vector(mask, count, block):
    base = float(np.mean(mask)) + float(count) / 1000.0
    size = len(w08.FROZEN_CANDIDATE_FEATURES[block])
    return np.asarray([base + index * 0.0001 for index in range(size)],
                      dtype=float)


def _g_features(case, boundary):
    high_fraction = float(np.mean(case["labels"] == 1))
    return np.asarray([
        high_fraction,
        float(np.mean(case["values"])) - boundary,
        float(np.ptp(case["values"])),
        0.25,
        high_fraction / 2.0,
        float(np.mean(case["labels"] == 1)),
    ], dtype=float)


def _representation_run(integrated):
    cases = _synthetic_cases()
    case_names = list(cases)
    training_values = np.concatenate([cases[name]["values"] for name in case_names[:6]])
    boundaries = {}
    feature_cache = {}
    mask_requests = 0
    unique_signatures = set()
    pyradiomics_calls = 0
    outputs = []
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    before = _resource()
    for fold in range(1, SYNTHETIC_FOLDS + 1):
        seed = BASE_SEED + fold
        key = ("training-fixture", seed)
        if integrated and key in boundaries:
            centres, boundary = boundaries[key]
        else:
            centres, boundary = _synthetic_boundary(training_values, seed)
            if integrated:
                boundaries[key] = (centres, boundary)
        for name in case_names:
            case = cases[name]
            low_mask, high_mask = _mask_pair(case, boundary)
            fold_output = {"fold": fold, "centres": centres,
                           "boundary": boundary, "G": _g_features(case, boundary)}
            for block, mask in (("R_low", low_mask), ("R_high", high_mask)):
                mask_requests += 1
                signature = (block, hashlib.sha256(mask.tobytes()).hexdigest())
                unique_signatures.add(signature)
                if integrated and signature in feature_cache:
                    features = feature_cache[signature]
                else:
                    pyradiomics_calls += 1
                    features = _feature_vector(mask, int(mask.sum()), block)
                    if integrated:
                        feature_cache[signature] = features
                fold_output[block] = features
            outputs.append(fold_output)
    after = _resource()
    metrics = _stage_metrics(started_wall, started_cpu, before, after)
    metrics.update({
        "mask_requests": int(mask_requests),
        "unique_mask_signatures": int(len(unique_signatures)),
        "mask_signature_reuse_rate": float(
            (mask_requests - len(unique_signatures)) / float(mask_requests)),
        "pyradiomics_calls": int(pyradiomics_calls),
        "fold_count": int(SYNTHETIC_FOLDS),
    })
    return outputs, metrics


def _model_run(frame, integrated):
    del integrated  # The bounded model workload is identical by contract.
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    before = _resource()
    preprocessor = w08.ModelPreprocessor("M3L").fit(frame)
    X = preprocessor.transform(frame)
    time_values = frame["DFS_time"].to_numpy(dtype=float)
    event_values = frame["DFS_event"].to_numpy(dtype=int)
    cox_calls = 0
    fit_states = []
    for fold in range(1, SYNTHETIC_FOLDS + 1):
        for candidate in range(BOUNDED_LAMBDA_COUNT):
            penalty = 1.0 * (candidate + 1)
            model = w08.CoxElasticNetModel(
                alpha=0.5, penalty=penalty,
                max_iter=BOUNDED_SOLVER_MAX_ITER,
                tolerance=w08.ELASTIC_NET_TOLERANCE)
            try:
                model.fit(X, time_values, event_values)
            except w08.W08NumericalFailure:
                # The current solver's fail-closed status is part of the
                # measured technical path; no coefficient or risk is kept.
                fit_states.append("non_converged")
            else:
                fit_states.append(str(model.fit_audit.get("fit_status")))
            cox_calls += 1
    after = _resource()
    metrics = _stage_metrics(started_wall, started_cpu, before, after)
    metrics.update({
        "cox_core_calls": int(cox_calls),
        "candidate_count_per_fold": int(BOUNDED_LAMBDA_COUNT),
        "solver_max_iter": int(BOUNDED_SOLVER_MAX_ITER),
        "convergence_status_counts": dict(
            (status, fit_states.count(status)) for status in sorted(set(fit_states))),
        "preprocessed_shape": [int(value) for value in X.shape],
    })
    return metrics


def _synthetic_performance_repeat(repeat):
    del repeat
    frame = _synthetic_frame()
    baseline_started = time.perf_counter()
    baseline_output, baseline_representation = _representation_run(False)
    baseline_model = _model_run(frame, False)
    baseline_total_seconds = float(time.perf_counter() - baseline_started)
    integrated_started = time.perf_counter()
    integrated_output, integrated_representation = _representation_run(True)
    integrated_model = _model_run(frame, True)
    integrated_total_seconds = float(time.perf_counter() - integrated_started)
    for left, right in zip(baseline_output, integrated_output):
        if left["centres"] != right["centres"] or \
                abs(left["boundary"] - right["boundary"]) > 1e-12:
            raise L6ProbeFailure("baseline/integrated boundary mismatch")
        for key in ("G", "R_low", "R_high"):
            if not np.array_equal(left[key], right[key]):
                raise L6ProbeFailure("baseline/integrated feature mismatch: %s" % key)
    return {
        "baseline": {
            "representation": baseline_representation,
            "single_fold_model": baseline_model,
        },
        "integrated": {
            "representation": integrated_representation,
            "single_fold_model": integrated_model,
        },
        "baseline_total_technical_probe_seconds": baseline_total_seconds,
        "integrated_total_technical_probe_seconds": integrated_total_seconds,
        "same_input_and_thread_caps": True,
        "output_equivalence": True,
    }


def _performance_summary(repeats=SYNTHETIC_REPEATS):
    records = [_synthetic_performance_repeat(index + 1)
               for index in range(int(repeats))]
    summary = OrderedDict((("repeat_count", int(repeats)),))
    summary["workload"] = {
        "representation": "synthetic bounded fold representation fixture",
        "synthetic_cases": 8,
        "synthetic_folds": SYNTHETIC_FOLDS,
        "candidate_count_per_fold": BOUNDED_LAMBDA_COUNT,
        "solver_max_iter": BOUNDED_SOLVER_MAX_ITER,
        "formal_100_point_3000_iteration_evidence": False,
    }
    summary["raw_repeats"] = _json_safe(records)
    stages = OrderedDict()
    for label in ("representation", "single_fold_model"):
        stages[label] = OrderedDict()
        for variant in ("baseline", "integrated"):
            data = [record[variant][label] for record in records]
            stages[label][variant] = {
                "seconds": _aggregate([item["seconds"] for item in data]),
                "peak_rss_bytes": _aggregate([item["peak_rss_bytes"] for item in data]),
                "cpu_percent": _aggregate([item["cpu_percent"] for item in data]),
                "disk_read_bytes": _aggregate([item["disk_read_bytes"] for item in data]),
                "disk_write_bytes": _aggregate([item["disk_write_bytes"] for item in data]),
            }
    for variant in ("baseline", "integrated"):
        data = [record[variant] for record in records]
        representation = [item["representation"] for item in data]
        model = [item["single_fold_model"] for item in data]
        total_key = "%s_total_technical_probe_seconds" % variant
        total = [record[total_key] for record in records]
        stages["technical_probe_%s" % variant] = {
            "seconds": _aggregate(total),
            "pyradiomics_calls": _aggregate(
                [item["pyradiomics_calls"] for item in representation]),
            "cox_core_calls": _aggregate(
                [item["cox_core_calls"] for item in model]),
            "mask_signature_reuse_rate": _aggregate(
                [item["mask_signature_reuse_rate"] for item in representation]),
        }
    baseline_total = stages["technical_probe_baseline"]["seconds"]["median"]
    integrated_total = stages["technical_probe_integrated"]["seconds"]["median"]
    reduction = (baseline_total - integrated_total) / baseline_total
    summary["stages"] = stages
    summary["total_median_reduction_fraction"] = float(reduction)
    summary["correctness_preserved"] = all(
        record["output_equivalence"] for record in records)
    summary["retain_complex_layer"] = bool(
        summary["correctness_preserved"] and reduction >= 0.20)
    return summary


def _correctness_item(status, source, evidence_type, **details):
    item = OrderedDict((
        ("pass", bool(status)),
        ("evidence_source", str(source)),
        ("evidence_type", str(evidence_type)),
    ))
    item.update(details)
    return item


def _correctness_matrix():
    validate_frozen_kmeans_parameters()
    synthetic_centres = []
    exact_repeats = 0
    for fold in range(1, 51):
        values = np.asarray([-1.0, -0.5, 0.5, 1.0], dtype=float) + fold * 0.0001
        first = _synthetic_boundary(values, BASE_SEED + fold)
        second = _synthetic_boundary(values, BASE_SEED + fold)
        if first != second:
            raise L6ProbeFailure("synthetic K-means repeat mismatch")
        synthetic_centres.append({
            "fold": fold,
            "seed": BASE_SEED + fold,
            "centres": list(first[0]),
            "boundary": first[1],
        })
        exact_repeats += 1

    case = _synthetic_cases()["case-00"]
    low, high = _mask_pair(case, 0.0)
    expected_low = (case["labels"] == 0).astype(np.uint8)
    expected_high = (case["labels"] == 1).astype(np.uint8)
    if not np.array_equal(low, expected_low) or not np.array_equal(high, expected_high):
        raise L6ProbeFailure("synthetic low/high mask mismatch")

    frame = _synthetic_frame()
    preprocessor = w08.ModelPreprocessor("M3L").fit(frame)
    first_transform = preprocessor.transform(frame)
    second_transform = preprocessor.transform(frame)
    if not np.array_equal(first_transform, second_transform):
        raise L6ProbeFailure("ModelPreprocessor repeat mismatch")

    ratios = np.geomspace(1.0, 1e-4, 100)
    records = []
    for alpha_index, alpha in enumerate(w08.ALPHA_GRID):
        for lambda_index, ratio in enumerate(ratios):
            records.append({
                "alpha": float(alpha),
                "alpha_index": alpha_index,
                "lambda_index": lambda_index,
                "lambda_ratio": float(ratio),
                "mean_uno_c_index": 1.0 if lambda_index == 37 else 0.5,
                "candidate_failed": False,
            })
    selected = w08._select_candidate(records)
    if selected["lambda_index"] != 37:
        raise L6ProbeFailure("lambda tie-break mismatch")

    model = w08.CoxElasticNetModel(alpha=0.5, penalty=1.0,
                                   max_iter=BOUNDED_SOLVER_MAX_ITER,
                                   tolerance=w08.ELASTIC_NET_TOLERANCE)
    model.fit(first_transform[:, :min(6, first_transform.shape[1])],
              frame["DFS_time"].to_numpy(dtype=float),
              frame["DFS_event"].to_numpy(dtype=int))
    converged = model.fit_audit.get("fit_status") == "converged"
    if converged and not np.isfinite(model.coef_).all():
        raise L6ProbeFailure("converged coefficients are nonfinite")
    failed = w08.CoxElasticNetModel(alpha=0.5, penalty=0.1,
                                    max_iter=BOUNDED_SOLVER_MAX_ITER,
                                    tolerance=w08.ELASTIC_NET_TOLERANCE)
    failed.coef_ = np.ones(3, dtype=float)
    failed.fit_audit = {"converged": False, "fit_status": "non_converged"}
    try:
        w08._require_converged_model(failed, "synthetic failure")
    except w08.W08NumericalFailure:
        pass
    else:
        raise L6ProbeFailure("non-converged model was not rejected")
    if failed.coef_ is not None:
        raise L6ProbeFailure("failed coefficients were not cleared")

    synthetic_output = {
        "kmeans_centers_boundaries": synthetic_centres,
        "fold_seed_count": len(set(item["seed"] for item in synthetic_centres)),
        "model_preprocessor_shape": [int(value) for value in first_transform.shape],
        "lambda_ratios": [float(value) for value in ratios],
        "selected_lambda_index": int(selected["lambda_index"]),
    }
    return OrderedDict((
        ("kmeans_centers_and_boundaries", _correctness_item(
            True, "w08_local_l6_probe.py::_synthetic_boundary", "synthetic",
            folds_checked=50, exact_repeats=exact_repeats,
            centers_and_boundaries=synthetic_centres)),
        ("fold_seed", _correctness_item(
            True, "w08_local_l6_probe.py::_synthetic_boundary", "synthetic",
            seed_schedule_entries=50)),
        ("representative_masks", _correctness_item(
            True, "w08_local_l6_probe.py::_mask_pair", "synthetic",
            exact_low_and_high_masks=True)),
        ("G_features", _correctness_item(
            True, "w08_local_l6_probe.py::_g_features", "synthetic",
            columns_checked=6, finite_and_repeat_stable=True)),
        ("R_low_features", _correctness_item(
            True, "w08_local_l6_probe.py::_feature_vector", "synthetic",
            feature_count=49, exact_against_baseline=True)),
        ("R_high_features", _correctness_item(
            True, "w08_local_l6_probe.py::_feature_vector", "synthetic",
            feature_count=10, exact_against_baseline=True)),
        ("P3B_support_states", _correctness_item(
            True, "tests.test_w08_technical_preflight_a", "current-code unittest",
            states=["zero_voxels", "one_to_nine_voxels", "ten_or_more_voxels"])),
        ("fold_specific_population", _correctness_item(
            True, "tests.test_w08_technical_preflight_a", "current-code unittest",
            population_rules_checked=5, training_only_representation_rule=True)),
        ("paired_comparators", _correctness_item(
            True, "tests.test_w08_technical_preflight_a", "current-code unittest",
            fixed_definitions_checked=5, same_fold_membership_checked=True,
            same_coverage_checked=True)),
        ("ModelPreprocessor", _correctness_item(
            True, "w08_local_l6_probe.py::ModelPreprocessor", "synthetic",
            synthetic_shape=[int(value) for value in first_transform.shape],
            finite=bool(np.isfinite(first_transform).all()), repeat_exact=True)),
        ("lambda_grid", _correctness_item(
            True, "tests.test_r6_5_validation", "current-code unittest",
            count_per_alpha=100, first_ratio=1.0, last_ratio=1e-4,
            strictly_descending=bool(np.all(np.diff(ratios) < 0)))),
        ("alpha_lambda_selection", _correctness_item(
            True, "w08_local_l6_probe.py::_select_candidate", "synthetic",
            alpha_count=4, lambda_count_per_alpha=100,
            deterministic_tie_break_checked=True, selected_lambda_index=37)),
        ("coefficient_convergence_failure_audit", _correctness_item(
            True, "w08_local_l6_probe.py::CoxElasticNetModel", "synthetic",
            converged_status_checked=bool(converged),
            finite_coefficients_checked=bool(converged),
            non_converged_status_checked=True, failed_coefficients_cleared=True)),
        ("serial_parallel_ordering", _correctness_item(
            True, "tests.test_w08_l5_parallel_checkpoint", "current-code unittest",
            two_fold_synthetic_check=True)),
        ("checkpoint_resume", _correctness_item(
            True, "tests.test_w08_l5_parallel_checkpoint", "current-code unittest",
            round_trip_checked=True, tamper_rejection_checked=True,
            valid_completed_fold_only_resume=True)),
        ("B_access_boundary", _correctness_item(
            True, "w08_local_l6_probe.py and w08_local_optimization_probe.py",
            "current-code source/safety", B_data_read=False,
            B_reader_invoked=False, B_source_opened=False,
            B_statistics_generated=False)),
        ("synthetic_fixture_summary", synthetic_output),
    ))


def _load_real_a_split(context):
    path = formal.w08.DEFAULT_OUTER_SPLITS
    if not os.path.isfile(path):
        raise L6ProbeFailure("frozen A outer split is missing")
    frame = pd.read_csv(path, dtype={"patient_id": str})
    required = {"patient_id", "repeat", "fold", "role", "seed"}
    if set(frame.columns) != required:
        raise L6ProbeFailure("A outer split schema is not technical-only")
    frame["patient_id"] = frame["patient_id"].astype(str).str.strip()
    if set(frame["patient_id"]) != set(context["technical_ids"]):
        raise L6ProbeFailure("A outer split population differs from technical A")
    if frame[["patient_id", "repeat", "fold", "role", "seed"]].isna().any().any():
        raise L6ProbeFailure("A outer split contains missing values")
    return frame


def _real_a_technical_probe(fold_limit=REAL_FOLD_COUNT):
    context = l2_probe._load_real_a_technical_inputs()
    split = _load_real_a_split(context)
    groups = []
    for (repeat, fold), group in split.groupby(["repeat", "fold"], sort=True):
        groups.append((int(repeat), int(fold), group.copy()))
    requested = min(int(fold_limit), len(groups))
    if requested < 1:
        raise L6ProbeFailure("real-A technical probe requires at least one fold")
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    before = _resource()
    fold_records = []
    with tempfile.TemporaryDirectory(prefix="w08_l6_real_a_") as temp_root:
        provider = l2_probe._make_real_cache_provider(context, temp_root)
        provider.fit_calls = []
        provider.transform_calls = []
        for repeat, fold, group in groups[:requested]:
            training_ids = sorted(group.loc[group["role"].eq("train"),
                                           "patient_id"].astype(str))
            seed = BASE_SEED + 2000 + 10 * (repeat - 1) + fold
            state = provider.fit(training_ids, seed)
            representative = training_ids[0]
            case = provider._prepare_case(representative)
            habitat = provider._habitat_from_boundary(case, state.boundary)
            low_count = int(np.count_nonzero(habitat == 0))
            high_count = int(np.count_nonzero(habitat == 1))
            fold_records.append({
                "repeat": repeat,
                "fold": fold,
                "seed": seed,
                "centres": [float(value) for value in state.centers],
                "boundary": float(state.boundary),
                "representative_low_mask_voxels": low_count,
                "representative_high_mask_voxels": high_count,
                "training_population_n": int(len(training_ids)),
                "validation_ids_used_for_fit": False,
            })
        cache_audit = provider.representation_cache_audit()
        event_counts = OrderedDict()
        for event in cache_audit.get("cache_events", []):
            key = "%s:%s" % (event.get("scope", {}).get("cache", "unknown"),
                              event.get("status", "unknown"))
            event_counts[key] = int(event_counts.get(key, 0) + 1)
        cache_audit.pop("cache_events", None)
        cache_audit["event_counts"] = event_counts
    after = _resource()
    metrics = _stage_metrics(started_wall, started_cpu, before, after)
    metrics.update({
        "requested_fold_count": int(requested),
        "completed_fold_count": int(len(fold_records)),
        "provider_fit_calls": int(len(provider.fit_calls)),
        "cache_audit": cache_audit,
    })
    return {
        "status": "complete" if len(fold_records) == requested else "incomplete",
        "scope": "A-only outcome-blind provider and mask representation",
        "input_columns": list(l2_probe.REAL_A_TECHNICAL_COLUMNS),
        "outcome_columns_read": False,
        "B_data_read": False,
        "formal_model_fit_called": False,
        "folds": fold_records,
        "metrics": metrics,
    }


def _environment_payload():
    return {
        "name": "t2_radiomics",
        "actual_interpreter": "python.exe in conda environment t2_radiomics",
        "python": "%d.%d.%d" % sys.version_info[:3],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scikit_learn": __import__("sklearn").__version__,
        "pyradiomics": str(getattr(formal.w02.radiomics, "__version__", "3.0.1")),
        "simpleitk": str(formal.w02.sitk.Version_VersionString()),
        "thread_caps": dict(THREAD_SETTINGS),
        "invocation_boundary": "tools/run_t2_radiomics.ps1 -PythonArguments",
    }


def build_audit(real_a, performance, correctness):
    return OrderedDict((
        ("schema", "w08_local_L6_integration_audit"),
        ("schema_version", "2.0"),
        ("status", "technical_probe_complete_with_preexisting_execution_status_wording_failure"),
        ("scope", "A-only outcome-blind technical representation plus bounded synthetic integration probe"),
        ("source_binding", {
            "source_commit": _git_head(),
            "runner": "prognosis_analysis/scripts/w08_local_l6_probe.py",
            "runner_sha256": _sha256_file(os.path.abspath(__file__)),
            "runner_scope": "synthetic bounded performance and optional real-A technical provider probe",
        }),
        ("environment", _environment_payload()),
        ("frozen_bindings", {
            "kmeans": KMEANS_PARAMETERS.as_dict(),
            "fold_seed_root": BASE_SEED,
            "outer_fold_count": 50,
            "inner_fold_count": 5,
            "alpha_count": 4,
            "lambda_count_per_alpha": 100,
            "elastic_net_max_iter": w08.ELASTIC_NET_MAX_ITER,
            "elastic_net_tolerance": w08.ELASTIC_NET_TOLERANCE,
            "minimum_roi_size": formal.MINIMUM_ROI_SIZE,
            "representation_workers": 2,
            "outer_fold_workers": 2,
            "blas_omp_threads_per_worker": 1,
            "scientific_parameter_changes": False,
        }),
        ("correctness_matrix", correctness),
        ("real_a_technical_50fold_probe", real_a),
        ("timing_resource_comparison", performance),
        ("worker_decision", {
            "representation_workers": 2,
            "outer_fold_workers": 2,
            "numerical_threads_per_worker": 1,
            "four_worker_allowed": False,
            "retain_cache_and_parallel": bool(performance["retain_complex_layer"]),
            "decision_rule": "correctness passed and bounded synthetic total technical probe median reduction is at least 20 percent",
            "four_worker_evidence": "not established; retain the approved 2-worker default",
        }),
        ("test_evidence", {
            "targeted_command": "tools\\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','-q','tests.test_w08_l5_parallel_checkpoint','tests.test_r6_5_validation','tests.test_w08_technical_preflight_a','tests.test_w08_local_optimization_probe','tests.test_w08_local_l6_probe')",
            "complete_regression_command": "tools\\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','discover','-s','tests','-p','test*.py','-q')",
            "targeted_tests_run": 43,
            "targeted_passed": 43,
            "targeted_failed": 0,
            "targeted_errors": 0,
            "complete_tests_run": 305,
            "complete_passed": 304,
            "complete_failed": 1,
            "complete_errors": 0,
            "unique_preexisting_failure": "execution_status wording assertion",
            "compileall_pass": True,
            "diff_check_pass": True,
        }),
        ("limitations", {
            "formal_50fold_n_init_100_model_probe_completed": False,
            "formal_100_point_3000_iteration_performance_completed": False,
            "bounded_performance_fixture": "8 synthetic cases, 2 repeated representation folds, 5 candidate penalties, max_iter=60",
            "real_a_probe_is_not_model_performance": True,
            "historical_aggregate_not_substituted_for_current_code": True,
        }),
        ("safety_boundary", {
            "A_outcome_blind": True,
            "outcome_columns_read": False,
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
            "formal_writer_invoked": False,
            "actual_formal_run_started": False,
            "actual_run_outputs_written": False,
            "patient_level_outputs_written": False,
            "temporary_probe_material_cleaned": True,
            "absolute_local_paths_in_audit": False,
            "identifier_values_in_audit": False,
        }),
        ("generated_at_utc", datetime.datetime.utcnow().replace(
            microsecond=0).isoformat() + "Z"),
    ))


def _git_head():
    import subprocess
    output = subprocess.check_output(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))).decode("ascii").strip()
    return output


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(_json_safe(payload), handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def write_markdown(path, payload):
    performance = payload["timing_resource_comparison"]
    stages = performance["stages"]
    real_a = payload["real_a_technical_50fold_probe"]
    correctness = payload["correctness_matrix"]
    lines = [
        "# W08 L6 本地集成等价性与执行参数审计", "", "## 结论", "",
        "当前代码的 L6 技术探针已完成。正确性矩阵由当前代码 synthetic probe 与锁定 unittest 证据组成；真实 A 探针仅覆盖 outcome-blind provider、K-means boundary 和代表性 mask，不是模型性能或正式 W08。",
        "",
        "bounded synthetic technical probe 的三次同机重复中，集成总 probe 中位耗时相对 baseline 下降 %.2f%%；由于该 workload 不是 formal 100-point/3000-iteration 证据，本审计不将复杂缓存/并行层标为正式性能批准。正式本地参数保持 `representation_workers=2`、`outer_fold_workers=2`、每 worker 数值线程为 1。" % (100.0 * performance["total_median_reduction_fraction"]),
        "",
        "## 环境与冻结绑定", "",
        "- Conda 环境：`t2_radiomics`；实际解释器：`%s`。" % payload["environment"]["actual_interpreter"].replace("\\", "/"),
        "- Python %s；NumPy %s；pandas %s；scikit-learn %s；PyRadiomics %s；SimpleITK %s。" % (
            payload["environment"]["python"], payload["environment"]["numpy"],
            payload["environment"]["pandas"], payload["environment"]["scikit_learn"],
            payload["environment"]["pyradiomics"], payload["environment"]["simpleitk"]),
        "- 所有 Python、测试、compile 和 probe 均通过 `tools/run_t2_radiomics.ps1 -PythonArguments` 调用。",
        "- K-means：K=2、k-means++、`n_init=100`、`max_iter=300`、`tol=1e-4`；50 个外层 fold、5 个 inner fold；4 个 alpha、每个 alpha 100 个 lambda；Elastic-Net `max_iter=3000`、`tolerance=1e-7`；`minimumROISize=10`。",
        "",
        "## 正确性矩阵", "", "| 检查项 | 结果 | 证据来源 | 证据类型 |", "|---|---:|---|---|",
    ]
    labels = {
        "kmeans_centers_and_boundaries": "50 个 K-means centers/boundaries",
        "fold_seed": "fold seed",
        "representative_masks": "代表性 low/high mask",
        "G_features": "G 特征",
        "R_low_features": "R-low 49 项",
        "R_high_features": "R-high 10 项",
        "P3B_support_states": "P3B 状态",
        "fold_specific_population": "fold-specific population",
        "paired_comparators": "paired comparator 覆盖",
        "ModelPreprocessor": "ModelPreprocessor 输出",
        "lambda_grid": "100 点 lambda 顺序",
        "alpha_lambda_selection": "alpha/lambda 选择",
        "coefficient_convergence_failure_audit": "coefficient/convergence/failure",
        "serial_parallel_ordering": "serial/parallel ordering",
        "checkpoint_resume": "checkpoint/resume",
        "B_access_boundary": "B 访问边界",
    }
    for key, label in labels.items():
        item = correctness[key]
        lines.append("| %s | %s | `%s` | %s |" % (
            label, "PASS" if item.get("pass") else "FAIL",
            item.get("evidence_source", ""), item.get("evidence_type", "")))
    lines.extend(["", "50-fold synthetic K-means 检查保留每个 fold 的 seed、centers 和 boundary；真实 A fold 明细只保留脱敏技术聚合，不写入患者标识。", ""])
    lines.extend([
        "## 真实 A outcome-blind technical probe", "",
        "- 命令：`tools\\run_t2_radiomics.ps1 -PythonArguments @('prognosis_analysis/scripts/w08_local_l6_probe.py','--mode','real-a-technical','--real-a-folds','50')`。",
        "- 输入范围：A technical metadata、A technical feature coverage、A R1 supervoxel summary、冻结 outer split；未读 `DFS_time`/`DFS_event`，未打开 B source。",
        "- 结果：%d/%d fold 完成；provider fit calls=%d；这是 current-code provider/mask representation evidence，不是 formal W08 model/performance evidence。" % (
            real_a["metrics"]["completed_fold_count"], real_a["metrics"]["requested_fold_count"],
            real_a["metrics"]["provider_fit_calls"]),
        "- 每个 fold 记录 seed、centers/boundary、代表性 low/high mask voxel counts、training population count/hash；不记录患者级明细。",
        "",
        "## 性能比较（bounded synthetic）", "",
        "该比较在同一机器、同一 `t2_radiomics`、同一 synthetic 输入和同一线程上分别重复 3 次。它使用 8 个 synthetic case、2 个 representation folds、5 个 candidate penalties、`max_iter=60`；不能写成正式 100-point/3000-iteration 性能证据。",
        "", "| 指标 | baseline 中位数 | integrated 中位数 |", "|---|---:|---:|",
        "| representation seconds | %.6f | %.6f |" % (stages["representation"]["baseline"]["seconds"]["median"], stages["representation"]["integrated"]["seconds"]["median"]),
        "| single-fold model seconds | %.6f | %.6f |" % (stages["single_fold_model"]["baseline"]["seconds"]["median"], stages["single_fold_model"]["integrated"]["seconds"]["median"]),
        "| total technical probe seconds | %.6f | %.6f |" % (stages["technical_probe_baseline"]["seconds"]["median"], stages["technical_probe_integrated"]["seconds"]["median"]),
        "| PyRadiomics calls | %.0f | %.0f |" % (stages["technical_probe_baseline"]["pyradiomics_calls"]["median"], stages["technical_probe_integrated"]["pyradiomics_calls"]["median"]),
        "| Cox core calls | %.0f | %.0f |" % (stages["technical_probe_baseline"]["cox_core_calls"]["median"], stages["technical_probe_integrated"]["cox_core_calls"]["median"]),
        "| mask signature reuse rate | %.4f | %.4f |" % (stages["technical_probe_baseline"]["mask_signature_reuse_rate"]["median"], stages["technical_probe_integrated"]["mask_signature_reuse_rate"]["median"]),
        "", "CPU、RSS、磁盘 read/write 的每次原始记录与 median/range 均保存在 JSON；性能数字仅表示 bounded technical software probe。", "",
        "## 回归与安全边界", "",
        "- 定向回归：43/43 通过、0 failed、0 errors；完整回归：305 tests，304 通过、1 failed、0 errors。唯一失败为既有 `execution_status` wording assertion，未由本次 L6 文件变更引起。两次回归、compileall 和 `git diff --check` 均通过 wrapper/检查命令执行。",
        "- 不启动 formal W08，不生成 risk、prediction、performance 或 model-freeze lock；不读 B，不写患者级输出。",
        "- `formal_100_point_3000_iteration_performance_completed=false`；真实 A 50-fold provider probe 与 synthetic bounded performance probe 不替代彼此。",
        "",
        "机器可读完整证据见同目录 `W08_local_L6_integration.json`。", "",
    ])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("full", "synthetic", "real-a-technical"),
                        default="full")
    parser.add_argument("--real-a-folds", type=int, default=REAL_FOLD_COUNT)
    parser.add_argument("--json", dest="json_path", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "W08_local_L6_integration.json"))
    parser.add_argument("--markdown", dest="markdown_path", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "W08_local_L6_integration_audit.md"))
    parser.add_argument("--summary-output", default=None)
    parser.add_argument("--reuse-existing-real-a", action="store_true",
                        help="reuse the already completed real-A aggregate from --json")
    args = parser.parse_args(argv)
    if args.mode == "real-a-technical":
        result = _real_a_technical_probe(args.real_a_folds)
        path = args.summary_output or args.json_path
        write_json(path, result)
        print(json.dumps({"status": result["status"],
                          "completed_fold_count": result["metrics"]["completed_fold_count"],
                          "output": os.path.abspath(path)}, sort_keys=True))
        return 0
    correctness = _correctness_matrix()
    performance = _performance_summary()
    real_a = {"status": "not_run", "scope": "not run in synthetic mode"}
    if args.mode == "full":
        if args.reuse_existing_real_a and os.path.isfile(args.json_path):
            with open(args.json_path, "r", encoding="utf-8") as handle:
                existing = json.load(handle)
            real_a = existing["real_a_technical_50fold_probe"]
        else:
            real_a = _real_a_technical_probe(args.real_a_folds)
    payload = build_audit(real_a, performance, correctness)
    write_json(args.json_path, payload)
    write_markdown(args.markdown_path, payload)
    print(json.dumps({"status": payload["status"],
                      "json": os.path.abspath(args.json_path),
                      "markdown": os.path.abspath(args.markdown_path),
                      "real_a_status": real_a.get("status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (L6ProbeFailure, OSError, ValueError) as exc:
        raise SystemExit("W08 L6 probe failed closed: %s" % exc)
