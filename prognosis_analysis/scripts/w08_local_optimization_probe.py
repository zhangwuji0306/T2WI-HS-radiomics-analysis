"""Synthetic, outcome-blind W08 local timing and resource probe.

The probe exercises the frozen W08 implementation on deterministic synthetic
inputs only.  It deliberately does not call the formal writer, open A/B
clinical outcome readers, or write patient-level, prediction, or performance
artifacts.  Only aggregate medians, ranges, and counts are retained.
"""
from __future__ import absolute_import

import ctypes
import datetime
import json
import math
import os
import platform
import sys
import tempfile
import time
from collections import OrderedDict

# The local W08 contract uses one worker for the SLIC stage.  Keep numerical
# library threads at one as an execution parameter, without changing science
# parameters or the frozen K-means contract.
THREAD_SETTINGS = OrderedDict((
    ("OMP_NUM_THREADS", "1"),
    ("MKL_NUM_THREADS", "1"),
    ("OPENBLAS_NUM_THREADS", "1"),
    ("NUMEXPR_NUM_THREADS", "1"),
))
for _name, _value in THREAD_SETTINGS.items():
    os.environ[_name] = _value

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import w08_formal_run_a as formal  # noqa: E402
import w08_nested_cv as w08  # noqa: E402
from w08_kmeans_parameters import (  # noqa: E402
    KMEANS_PARAMETERS, validate_frozen_kmeans_parameters)


OUTPUT_NAME = "w08_local_optimization_probe_summary.json"
AUDIT_NAME = "W08_local_L2_baseline_profile_audit.md"
REPEAT_COUNT = 3
SYNTHETIC_SEED = 20260908
STAGE_NAMES = (
    "a_input_load",
    "slic_cache_prepare_validate",
    "single_fold_kmeans_n_init_100",
    "habitat_mask_g_features",
    "r_low_pyradiomics",
    "r_high_pyradiomics",
    "model_preprocessor",
    "elastic_net_single_candidate",
    "elastic_net_100_lambda_alpha_path",
    "uno_weights_and_bottom_call",
)
FORBIDDEN_OUTPUT_NAMES = frozenset((
    "predictions.csv", "fold_results.csv", "selection_results.csv",
    "formal_output_manifest.json", "model_freeze_lock.json", "release_gate.json",
))
FORBIDDEN_KEYS = frozenset((
    "patient_id", "影像号", "病历号", "姓名", "DFS_time", "DFS_event",
    "risk_score", "prediction", "predictions", "c_index", "auc", "brier",
    "calibration", "performance", "model_comparison",
))
B_ACCESS_FLAGS = (
    "B_data_read", "B_reader_invoked", "B_source_opened",
    "B_statistics_generated",
)


class ProbeFailure(RuntimeError):
    """Raised when an aggregate probe cannot be considered complete."""


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _windows_resource_snapshot():
    """Read process RSS and I/O counters without adding a dependency."""
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
    handle = kernel32.GetCurrentProcess()

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    class IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    memory = ProcessMemoryCounters()
    memory.cb = ctypes.sizeof(memory)
    if not psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(memory), ctypes.sizeof(memory)):
        raise OSError("GetProcessMemoryInfo failed")
    io = IoCounters()
    if not kernel32.GetProcessIoCounters(handle, ctypes.byref(io)):
        raise OSError("GetProcessIoCounters failed")
    return {
        "rss_bytes": int(memory.PeakWorkingSetSize),
        "read_bytes": int(io.ReadTransferCount),
        "write_bytes": int(io.WriteTransferCount),
    }


def _proc_resource_snapshot():
    """Read Linux process counters for portable test execution."""
    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF)
    rss = int(usage.ru_maxrss)
    if sys.platform != "darwin":
        rss *= 1024
    read_bytes = write_bytes = 0
    io_path = "/proc/self/io"
    if os.path.isfile(io_path):
        with open(io_path, "r", encoding="utf-8") as handle:
            values = {}
            for line in handle:
                key, value = line.split(":", 1)
                values[key.strip()] = int(value.strip())
        read_bytes = int(values.get("read_bytes", 0))
        write_bytes = int(values.get("write_bytes", 0))
    else:
        raise OSError("process disk I/O counters are unavailable")
    return {
        "rss_bytes": rss,
        "read_bytes": read_bytes,
        "write_bytes": write_bytes,
    }


def resource_snapshot():
    if os.name == "nt":
        return _windows_resource_snapshot()
    return _proc_resource_snapshot()


def _make_survival_arrays(n=32):
    """Create deterministic software-regression arrays, never real outcomes."""
    indices = np.arange(n, dtype=float)
    time_values = 2.0 + indices * 0.75
    event_values = (np.arange(n) % 2 == 0).astype(int)
    risk_values = np.sin(indices / 4.0) + indices / float(n)
    return time_values, event_values, risk_values


def _make_synthetic_frame(n=32, seed=SYNTHETIC_SEED):
    rng = np.random.RandomState(seed)
    frame = pd.DataFrame({
        "年龄": np.linspace(40.0, 75.0, n),
        "CEA_log": np.log1p(np.linspace(1.0, 20.0, n)),
        "thickness": np.linspace(3.0, 12.0, n),
        "EID": np.linspace(0.5, 5.0, n),
        "mrT_4级": 1 + np.arange(n) % 4,
        "mrN_3级": np.arange(n) % 4,
        "MRF": np.arange(n) % 2,
        "mrEMVI": (np.arange(n) + 1) % 2,
        "活检病理非腺癌": (np.arange(n) // 2) % 2,
    })
    for column in w08.GLOBAL_COLUMNS:
        frame[column] = rng.normal(size=n)
    for block in ("R_low", "R_high"):
        for index, feature in enumerate(w08.FROZEN_CANDIDATE_FEATURES[block]):
            # Independent deterministic waves keep the preprocessing path
            # non-degenerate without embedding a patient or endpoint field.
            x = np.arange(n, dtype=float) + 1.0
            frame[w08.RADIOMICS_PREFIXES[block] + feature] = (
                np.sin(x * (index + 1) * 0.13) +
                np.cos(x * (index + 2) * 0.07) +
                0.01 * rng.normal(size=n))
    return frame


def _make_synthetic_image(temp_root):
    image_array = np.zeros((8, 24, 24), dtype=np.float32)
    z, y, x = np.indices(image_array.shape)
    image_array[:] = (0.2 * z + 0.03 * y + 0.11 * x +
                      0.5 * np.sin(x / 2.0) + 0.25 * np.cos(y / 3.0))
    image = formal.w02.sitk.GetImageFromArray(image_array)
    image.SetSpacing((1.0, 1.0, 2.0))
    roi = np.ones(image_array.shape, dtype=np.uint8)
    mask = formal.w02.sitk.GetImageFromArray(roi)
    mask.CopyInformation(image)
    image_path = os.path.join(temp_root, "synthetic_image.nrrd")
    mask_path = os.path.join(temp_root, "synthetic_mask.nrrd")
    formal.w02.sitk.WriteImage(image, image_path)
    formal.w02.sitk.WriteImage(mask, mask_path)
    labels = np.zeros(image_array.shape, dtype=np.int32)
    labels[:, :, 12:] = 1
    case = {
        "image_path": image_path,
        "mask_path": mask_path,
        "labels": labels,
        "roi": roi.astype(bool),
        "spacing_xyz": (1.0, 1.0, 2.0),
        "sv": pd.DataFrame({
            "sv_label": [0, 1],
            "n_tumor_voxels": [int((labels == 0).sum()), int((labels == 1).sum())],
            "Mean": [-0.5, 0.5],
        }),
    }
    return image, mask, case


def _make_provider(case, extractor, stub_radiomics=False):
    """Use the production provider methods against a synthetic case."""
    provider = formal.AOnlyFoldFeatureProvider.__new__(
        formal.AOnlyFoldFeatureProvider)
    provider._extractor = extractor
    provider._case_cache = {}
    provider._state_cache = {}
    provider._prepare_case = lambda _identifier: case
    if stub_radiomics:
        def synthetic_radiomics(_image, _mask, block, expected_voxel_count):
            if expected_voxel_count < formal.MINIMUM_ROI_SIZE:
                raise w08.W08ValidationError("synthetic mask below frozen threshold")
            return {
                w08.RADIOMICS_PREFIXES[block] + feature: 0.0
                for feature in w08.FROZEN_CANDIDATE_FEATURES[block]
            }
        provider._radiomics_for_mask = synthetic_radiomics
    return provider


def _run_stage(name, function):
    before = resource_snapshot()
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        function()
    except BaseException as exc:  # record aggregate failure and fail closed
        return {"ok": False, "stage": name,
                "error_class": exc.__class__.__name__}
    elapsed = time.perf_counter() - started_wall
    cpu_elapsed = time.process_time() - started_cpu
    after = resource_snapshot()
    if not math.isfinite(elapsed) or elapsed <= 0.0:
        return {"ok": False, "stage": name, "error_class": "InvalidTiming"}
    return {
        "ok": True,
        "stage": name,
        "seconds": float(elapsed),
        "cpu_percent": float(100.0 * cpu_elapsed / elapsed),
        "rss_bytes": int(after["rss_bytes"]),
        "read_bytes": max(0, int(after["read_bytes"] - before["read_bytes"])),
        "write_bytes": max(0, int(after["write_bytes"] - before["write_bytes"])),
    }


def _single_iteration(temp_root):
    rng = np.random.RandomState(SYNTHETIC_SEED)
    image, _mask, case = _make_synthetic_image(temp_root)
    cfg = formal.w07._read_json(formal.HABITAT_CONFIG)
    fixture_matrix = rng.normal(size=(32, 6))
    fixture_values = np.linspace(-1.0, 1.0, 48).reshape(8, 6)
    times, events, risk = _make_survival_arrays()
    frame = _make_synthetic_frame()
    extractor = formal._build_backend_compatible_extractor()
    state = w08.FoldState("synthetic-training", 2026,
                          (-0.5, 0.5), 0.0, {})
    provider_for_g = _make_provider(case, extractor, stub_radiomics=True)
    provider_for_r = _make_provider(case, extractor, stub_radiomics=False)

    def input_load():
        source = os.path.join(temp_root, "synthetic_input.csv")
        pd.DataFrame(fixture_matrix).to_csv(source, index=False)
        loaded = pd.read_csv(source)
        if loaded.shape != fixture_matrix.shape:
            raise ProbeFailure("synthetic input shape changed")

    def slic_cache():
        labels = formal.technical.slic_labels(
            image, cfg, connected=True)
        cache_path = os.path.join(temp_root, "slic_cache.npz")
        np.savez_compressed(cache_path, labels=labels,
                            roi=case["roi"].astype(np.uint8))
        with np.load(cache_path) as cached:
            cached_labels = cached["labels"].astype(np.int32, copy=False)
            cached_roi = cached["roi"].astype(bool, copy=False)
        if not np.array_equal(labels, cached_labels) or \
                not np.array_equal(case["roi"], cached_roi):
            raise ProbeFailure("synthetic SLIC cache validation failed")

    def kmeans():
        validate_frozen_kmeans_parameters()
        values = np.concatenate([
            fixture_values[index] + index * 0.01
            for index in range(fixture_values.shape[0])])
        weights = np.concatenate([
            np.full(fixture_values.shape[1], 1.0 / fixture_values.shape[1])
            for _index in range(fixture_values.shape[0])])
        estimator = formal.KMeans(
            random_state=12345, **KMEANS_PARAMETERS.sklearn_kwargs())
        estimator.fit(values.reshape(-1, 1), sample_weight=weights)
        if estimator.n_init != 100:
            raise ProbeFailure("K-means n_init binding changed")

    def habitat_and_g():
        row = provider_for_g._transform_one("synthetic", state)
        required = set(formal.w08.GLOBAL_COLUMNS)
        if not required.issubset(row) or not all(
                np.isfinite(float(row[column])) for column in required):
            raise ProbeFailure("synthetic habitat/G output is incomplete")

    def r_low():
        low = case["roi"] & (case["labels"] == 0)
        mask = formal.w02.make_habitat_mask(image, low.astype(np.uint8), 1)
        provider_for_r._radiomics_for_mask(
            image, mask, "R_low", int(low.sum()))

    def r_high():
        high = case["roi"] & (case["labels"] == 1)
        mask = formal.w02.make_habitat_mask(image, high.astype(np.uint8), 1)
        provider_for_r._radiomics_for_mask(
            image, mask, "R_high", int(high.sum()))

    def preprocess():
        preprocessor = w08.ModelPreprocessor("M3L").fit(frame)
        transformed = preprocessor.transform(frame)
        if transformed.shape[0] != len(frame) or not np.isfinite(transformed).all():
            raise ProbeFailure("synthetic ModelPreprocessor output is invalid")

    def single_elastic_net():
        model = w08.CoxElasticNetModel(
            alpha=0.5, penalty=0.05,
            max_iter=w08.ELASTIC_NET_MAX_ITER,
            tolerance=w08.ELASTIC_NET_TOLERANCE)
        model.fit(fixture_matrix, times, events)
        if not model.fit_audit.get("converged", False):
            raise ProbeFailure("synthetic Elastic-Net candidate did not converge")

    def lambda_path():
        for alpha in w08.ALPHA_GRID:
            maximum = w08._lambda_max(fixture_matrix, times, events, alpha)
            ratios = np.geomspace(1.0, w08.LAMBDA_MIN_RATIO, w08.LAMBDA_COUNT)
            for ratio in ratios:
                model = w08.CoxElasticNetModel(
                    alpha=alpha, penalty=float(maximum * ratio),
                    max_iter=w08.ELASTIC_NET_MAX_ITER,
                    tolerance=w08.ELASTIC_NET_TOLERANCE)
                model.fit(fixture_matrix, times, events)
                if not model.fit_audit.get("converged", False):
                    raise ProbeFailure("synthetic lambda path fit did not converge")

    def uno_bottom_call():
        train_time, train_event, _ = _make_survival_arrays(32)
        validation_time = train_time[::2]
        validation_event = train_event[::2]
        validation_risk = risk[::2]
        weights = []
        for query in validation_time:
            survival = w08._km_censoring_survival(
                train_time, train_event, query, left=True)
            weights.append(0.0 if survival <= 1e-12 else 1.0 / (survival * survival))
        if not weights or not np.isfinite(weights).all():
            raise ProbeFailure("synthetic Uno weight preparation failed")
        score = w08.uno_c_index(
            train_time, train_event, validation_time, validation_event,
            validation_risk)
        if not np.isfinite(score):
            raise ProbeFailure("synthetic Uno bottom call was not estimable")

    functions = (
        input_load, slic_cache, kmeans, habitat_and_g, r_low, r_high,
        preprocess, single_elastic_net, lambda_path, uno_bottom_call,
    )
    return [_run_stage(name, function)
            for name, function in zip(STAGE_NAMES, functions)]


def _aggregate(values, digits=6):
    if not values:
        return None
    return {
        "median": round(float(np.median(values)), digits),
        "range": [round(float(np.min(values)), digits),
                  round(float(np.max(values)), digits)],
    }


def _aggregate_stage(records):
    successful = [record for record in records if record.get("ok")]
    result = {
        "repeat_count": int(len(records)),
        "success_count": int(len(successful)),
        "failure_count": int(len(records) - len(successful)),
        "duration_seconds": _aggregate(
            [record["seconds"] for record in successful]),
        "cpu_utilization_percent": _aggregate(
            [record["cpu_percent"] for record in successful], digits=3),
        "peak_rss_bytes": _aggregate(
            [record["rss_bytes"] for record in successful], digits=0),
        "disk_read_bytes": _aggregate(
            [record["read_bytes"] for record in successful], digits=0),
        "disk_write_bytes": _aggregate(
            [record["write_bytes"] for record in successful], digits=0),
    }
    return result


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            for nested in _walk_keys(child):
                yield nested
    elif isinstance(value, (list, tuple)):
        for child in value:
            for nested in _walk_keys(child):
                yield nested


def _validate_aggregate_safety(payload):
    keys = set(_walk_keys(payload))
    unsafe = sorted(keys & FORBIDDEN_KEYS)
    if unsafe:
        raise ProbeFailure("aggregate output contains forbidden fields: %s" % unsafe)
    for key in B_ACCESS_FLAGS:
        if payload.get("safety", {}).get(key) is not False:
            raise ProbeFailure("probe safety flag %s is not false" % key)
    if payload.get("safety", {}).get("formal_writer_invoked") is not False:
        raise ProbeFailure("formal writer safety flag is not false")
    text = json.dumps(payload, ensure_ascii=False)
    if "predictions.csv" in text or "model_freeze_lock.json" in text:
        raise ProbeFailure("aggregate output names a forbidden formal artifact")


def _write_json_atomic(path, payload):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(_json_safe(payload), handle, ensure_ascii=False,
                  indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def run_probe(output_dir, repeats=REPEAT_COUNT, estimate_seconds=None):
    """Run the three-repeat synthetic probe and write only aggregate output."""
    if type(repeats) is not int or repeats < 3:
        raise ValueError("L2 requires at least three repeats")
    output_dir = os.path.abspath(os.fspath(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    existing = [name for name in os.listdir(output_dir)
                if name not in (OUTPUT_NAME,)]
    forbidden = sorted(set(existing) & FORBIDDEN_OUTPUT_NAMES)
    if forbidden:
        raise ProbeFailure("probe output directory contains formal artifacts: %s" %
                           forbidden)

    records_by_stage = OrderedDict((name, []) for name in STAGE_NAMES)
    for _repeat in range(repeats):
        with tempfile.TemporaryDirectory(prefix="w08_l2_probe_") as temp_root:
            records = _single_iteration(temp_root)
        for record in records:
            records_by_stage[record["stage"]].append(record)

    stages = OrderedDict((name, _aggregate_stage(records))
                         for name, records in records_by_stage.items())
    failure_stage_counts = OrderedDict()
    for records in records_by_stage.values():
        for record in records:
            if not record.get("ok"):
                failure_stage_counts[record["stage"]] = \
                    int(failure_stage_counts.get(record["stage"], 0) + 1)
    completed = not failure_stage_counts and all(
        stage["success_count"] == repeats for stage in stages.values())
    estimate = None
    if estimate_seconds is not None:
        estimate_seconds = float(estimate_seconds)
        if not math.isfinite(estimate_seconds) or estimate_seconds <= 0:
            raise ValueError("estimate_seconds must be a positive finite number")
        estimate = {
            "pilot_repeat_count": 1,
            "estimated_total_seconds": round(
                estimate_seconds * float(repeats) * 1.15, 3),
            "over_40_minutes": bool(estimate_seconds * repeats * 1.15 > 2400.0),
            "basis": "one complete synthetic repeat immediately before the measured repeats; 15 percent guard",
        }
    else:
        estimate = {
            "pilot_repeat_count": 0,
            "estimated_total_seconds": None,
            "over_40_minutes": None,
            "basis": "pilot estimate not supplied by the caller",
        }

    payload = {
        "schema": "w08_local_optimization_probe",
        "schema_version": "1.0",
        "status": "complete" if completed else "failed",
        "scope": "synthetic technical timing only",
        "repeat_count": int(repeats),
        "stages": stages,
        "failure_stage_counts": failure_stage_counts,
        "estimation": estimate,
        "runtime": {
            "python": "%d.%d.%d" % sys.version_info[:3],
            "platform": "%s-%s" % (platform.system(), platform.release()),
            "threads": dict(THREAD_SETTINGS),
            "pyradiomics": str(getattr(formal.w02.radiomics, "__version__", "3.0.1")),
            "simpleitk": str(formal.w02.sitk.Version_VersionString()),
        },
        "bindings": {
            "kmeans": KMEANS_PARAMETERS.as_dict(),
            "alpha_grid_count": int(len(w08.ALPHA_GRID)),
            "lambda_count_per_alpha": int(w08.LAMBDA_COUNT),
            "elastic_net_max_iter": int(w08.ELASTIC_NET_MAX_ITER),
            "elastic_net_tolerance": float(w08.ELASTIC_NET_TOLERANCE),
            "minimum_roi_size": int(formal.MINIMUM_ROI_SIZE),
        },
        "safety": {
            "outcome_columns_read": False,
            "formal_writer_invoked": False,
            "B_data_read": False,
            "B_reader_invoked": False,
            "B_source_opened": False,
            "B_statistics_generated": False,
        },
        "generated_at_utc": datetime.datetime.utcnow().replace(
            microsecond=0).isoformat() + "Z",
    }
    _validate_aggregate_safety(payload)
    _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), payload)
    if not completed:
        raise ProbeFailure("synthetic W08 L2 probe failed at aggregate stages")
    return payload


def write_audit_report(summary, path, estimate_seconds=None):
    """Write a concise, de-identified Markdown audit from aggregate JSON."""
    if summary.get("status") != "complete":
        raise ProbeFailure("cannot write a successful L2 audit from failed probe")
    lines = [
        "# W08 local L2 baseline profile audit",
        "",
        "## Scope",
        "",
        "This audit contains synthetic, outcome-blind technical timing only. "
        "It contains no patient identifier, absolute path, clinical outcome, "
        "outer-validation prediction, or model performance result.",
        "",
        "## Execution contract",
        "",
        "- Repeats: %d; thread settings: OMP/MKL/OPENBLAS/NUMEXPR = 1."
        % summary["repeat_count"],
        "- K-means binding: algorithm=kmeans, k=2, initialization=k-means++, "
        "n_init=100, max_iter=300, tol=1e-4.",
        "- Elastic-Net binding: alpha grid size %d, 100 lambdas per alpha, "
        "max_iter=%d, tolerance=%g."
        % (summary["bindings"]["alpha_grid_count"],
           summary["bindings"]["elastic_net_max_iter"],
           summary["bindings"]["elastic_net_tolerance"]),
        "- Synthetic technical fixture only; B access flags are all false.",
        "",
        "## Aggregate timing and resource profile",
        "",
        "All values below retain only the median, inclusive range, and counts "
        "across the three repeats.",
        "",
        "| Stage | Success / repeats | Failures | Median seconds | Range seconds |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in STAGE_NAMES:
        stage = summary["stages"][name]
        timing = stage["duration_seconds"]
        if timing is None:
            median = "n/a"
            range_text = "n/a"
        else:
            median = "%.6f" % timing["median"]
            range_text = "[%.6f, %.6f]" % tuple(timing["range"])
        lines.append("| `%s` | %d / %d | %d | %s | %s |" % (
            name, stage["success_count"], stage["repeat_count"],
            stage["failure_count"], median, range_text))
    lines.extend([
        "",
        "## Aggregate resource summary",
        "",
        "Resource values use the same aggregate-only rule: median and inclusive "
        "range across the three repeats.",
        "",
        "| Stage | CPU utilization % | Peak RSS bytes | Disk read bytes | Disk write bytes |",
        "|---|---:|---:|---:|---:|",
    ])
    for name in STAGE_NAMES:
        stage = summary["stages"][name]
        def resource_text(key, digits=3):
            metric = stage[key]
            if metric is None:
                return "n/a"
            if digits == 0:
                return "[%d, %d]" % tuple(metric["range"])
            return "[%.{0}f, %.{0}f]".format(digits) % tuple(metric["range"])
        cpu = stage["cpu_utilization_percent"]
        cpu_text = "n/a" if cpu is None else "%.3f [%.3f, %.3f]" % (
            cpu["median"], cpu["range"][0], cpu["range"][1])
        rss = stage["peak_rss_bytes"]
        rss_text = "n/a" if rss is None else "%d %s" % (
            rss["median"], resource_text("peak_rss_bytes", digits=0))
        read = stage["disk_read_bytes"]
        read_text = "n/a" if read is None else "%d %s" % (
            read["median"], resource_text("disk_read_bytes", digits=0))
        write = stage["disk_write_bytes"]
        write_text = "n/a" if write is None else "%d %s" % (
            write["median"], resource_text("disk_write_bytes", digits=0))
        lines.append("| `%s` | %s | %s | %s | %s |" % (
            name, cpu_text, rss_text, read_text, write_text))
    lines.extend([
        "",
        "The JSON artifact is the machine-readable source for the same "
        "aggregate values.",
        "",
        "## Relative hotspot reading",
        "",
        "The stage medians distinguish PyRadiomics (R-low/R-high), synthetic "
        "Elastic-Net fitting (single candidate and 100-lambda alpha path), "
        "and synthetic input/cache I/O. These are software timing observations "
        "only and are not model performance measurements.",
        "",
        "## Runtime estimate",
        "",
        "- Basis: one complete synthetic repeat immediately before the measured "
        "repeats, with a 15% guard.",
        "- Estimated total: %s seconds."
        % ("not supplied" if estimate_seconds is None else
           "%.3f" % summary["estimation"]["estimated_total_seconds"]),
        "- Above 40 minutes: %s."
        % str(summary["estimation"]["over_40_minutes"]).lower(),
        "",
        "## Access and output boundary",
        "",
        "`outcome_columns_read=false`; `formal_writer_invoked=false`; "
        "`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`; "
        "`B_statistics_generated=false`.",
        "",
    ])
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "output", "w08_local_optimization_probe"))
    parser.add_argument("--audit", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        AUDIT_NAME))
    parser.add_argument("--repeats", type=int, default=REPEAT_COUNT)
    parser.add_argument("--estimate-seconds", type=float, default=None)
    args = parser.parse_args(argv)
    summary = run_probe(args.output, repeats=args.repeats,
                        estimate_seconds=args.estimate_seconds)
    write_audit_report(summary, args.audit,
                       estimate_seconds=args.estimate_seconds)
    print(json.dumps({
        "status": summary["status"],
        "repeat_count": summary["repeat_count"],
        "output": os.path.relpath(
            os.path.join(os.path.abspath(args.output), OUTPUT_NAME),
            os.getcwd()),
        "audit": os.path.relpath(os.path.abspath(args.audit), os.getcwd()),
    }, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeFailure as exc:
        raise SystemExit("W08 L2 probe failed closed: %s" % exc)
