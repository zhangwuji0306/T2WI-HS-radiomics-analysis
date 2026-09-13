"""Outcome-blind W08 local timing and resource probe.

The measured probe uses the existing A-only technical reader and a small,
aggregate-only sample of the existing SLIC cache.  The remaining numerical
stages use deterministic synthetic inputs.  It never calls the formal writer,
opens an outcome reader, or writes patient-level, prediction, or performance
artifacts.  Only aggregate medians, ranges, and counters are retained.
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
REAL_CACHE_SAMPLE_SIZE = 3
REAL_A_TECHNICAL_COLUMNS = (
    "影像号", "technical_cohort", "modeling_eligible")
REAL_A_FEATURE_COLUMNS = ("影像号", "读者", "split")
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


def _failure_record(stage, exception):
    """Return failure evidence without copying a path or row identifier."""
    return {
        "ok": False,
        "stage": str(stage),
        "error_type": exception.__class__.__name__,
    }


def _normalise_failure_stage(stage):
    stage = str(stage)
    if stage in STAGE_NAMES or stage in ("initialization", "iteration"):
        return stage
    return "unknown"


def _normalise_error_type(error_type):
    error_type = str(error_type)
    if (error_type and len(error_type) <= 80 and
            error_type.replace("_", "").isalnum()):
        return error_type
    return "StageFailure"


def _load_real_a_technical_inputs():
    """Read only the locked A technical boundary and aggregate its coverage."""
    # The population source also contains non-technical columns.  The
    # explicit usecols contract prevents those columns from being materialised
    # by the technical reader.
    metadata = formal.read_technical_A(
        formal.W06_POPULATION,
        allow_full=True,
        usecols=list(REAL_A_TECHNICAL_COLUMNS),
        dtype={"影像号": str})
    required = set(REAL_A_TECHNICAL_COLUMNS)
    if not required.issubset(metadata.columns):
        raise ProbeFailure("A technical metadata columns are incomplete")
    metadata = metadata[list(REAL_A_TECHNICAL_COLUMNS)].copy()
    metadata["影像号"] = metadata["影像号"].astype(str).str.strip()
    if metadata["影像号"].eq("").any() or \
            metadata["影像号"].duplicated().any():
        raise ProbeFailure("A technical metadata identifiers are invalid")
    if not metadata["technical_cohort"].astype(str).str.strip().eq("A393").all():
        raise ProbeFailure("A technical metadata cohort is not A-only")
    eligible = pd.to_numeric(metadata["modeling_eligible"], errors="coerce")
    if eligible.isna().any() or not eligible.eq(1).all():
        raise ProbeFailure("A technical metadata contains ineligible rows")
    identifiers = set(metadata["影像号"])

    feature_source = os.path.join(formal.FEATURE_ROOT, "features_original.csv")
    feature_rows = formal.read_technical_A(
        feature_source,
        allowed_ids=identifiers,
        usecols=list(REAL_A_FEATURE_COLUMNS),
        dtype={"影像号": str})
    feature_rows["影像号"] = feature_rows["影像号"].astype(str).str.strip()
    feature_rows = feature_rows[
        feature_rows["读者"].astype(str).str.strip().eq("R1")].copy()
    if not feature_rows["split"].astype(str).str.strip().eq("A").all():
        raise ProbeFailure("A technical feature source contains a non-A row")
    if feature_rows["影像号"].duplicated().any() or \
            set(feature_rows["影像号"]) != identifiers:
        raise ProbeFailure("A technical feature source does not cover A")

    supervoxels = formal.technical_preflight._read_authorized_a_supervoxels(
        formal.SV_TABLE, identifiers, project_root=formal.PROJECT_ROOT)
    if set(supervoxels["影像号"].astype(str).str.strip()) != identifiers:
        raise ProbeFailure("A technical supervoxel source does not cover A")
    return {
        "technical_ids": identifiers,
        "supervoxels": supervoxels,
        "input_metrics": {
            "sample_count": int(len(metadata)),
            "successful_count": int(len(metadata)),
            "failure_count": 0,
        },
    }


def _existing_slic_cache_root():
    """Find a non-empty permitted SLIC cache without inventing a new source."""
    candidates = [formal.SLIC_CACHE_ROOT]
    attempts_root = os.path.join(formal.OUTPUT_ROOT, "attempts")
    if os.path.isdir(attempts_root):
        for name in sorted(os.listdir(attempts_root)):
            candidates.append(os.path.join(attempts_root, name, "work",
                                           "slic_cache"))
    for candidate in candidates:
        if not os.path.isdir(candidate):
            continue
        if any(name.endswith(".npz") and
               os.path.isfile(os.path.join(candidate, name))
               for name in os.listdir(candidate)):
            return candidate
    raise ProbeFailure("no existing SLIC cache is available for L2")


def _make_real_cache_provider(context, cache_root, read_only=False):
    """Reuse the production provider's case preparation/cache validation."""
    provider = formal.AOnlyFoldFeatureProvider.__new__(
        formal.AOnlyFoldFeatureProvider)
    provider._allowed_ids = set(context["technical_ids"])
    provider._sv = formal.AOnlyFoldFeatureProvider._normalise_supervoxel_table(
        context["supervoxels"])
    provider._habitat_config = formal.w07._read_json(formal.HABITAT_CONFIG)
    provider._habitat_config_path = os.path.abspath(formal.HABITAT_CONFIG)
    provider._cache_root = cache_root
    os.makedirs(cache_root, exist_ok=True)
    provider._cache_read_only = bool(read_only)
    provider._by_id = pd.DataFrame({
        "patient_id": sorted(context["technical_ids"]),
    }).set_index("patient_id", drop=False)
    provider._case_cache = {}
    provider._fit_cache = {}
    provider._state_cache = {}
    provider._feature_cache = {}
    provider._mask_signatures = {}
    provider._cache_events = []
    provider._cache_counts = {
        "slic_hits": 0, "slic_misses": 0, "slic_invalidations": 0,
        "representation_hits": 0, "representation_misses": 0,
        "representation_invalidations": 0,
        "feature_hits": 0, "feature_misses": 0,
        "feature_invalidations": 0,
    }
    provider._extractors = formal._build_exact_feature_extractors()
    provider._cache_contract = provider._build_cache_contract()
    return provider


def _real_slic_cache_probe(context, temp_root):
    """Measure existing hits and safe temporary miss/validation fixtures."""
    existing_root = _existing_slic_cache_root()
    cache_files = [name for name in os.listdir(existing_root)
                   if name.endswith(".npz") and
                   os.path.isfile(os.path.join(existing_root, name))]
    cache_identifiers = {
        os.path.splitext(name)[0] for name in cache_files}
    sample = sorted(set(context["technical_ids"]) & cache_identifiers)
    sample = sample[:REAL_CACHE_SAMPLE_SIZE]
    if not sample:
        raise ProbeFailure("existing SLIC cache has no authorized A sample")

    counters = {
        "existing_cache_file_count": int(len(cache_files)),
        "existing_cache_sample_count": int(len(sample)),
        "hit_count": 0,
        "miss_count": 0,
        "validation_failure_count": 0,
        "recomputed_count": 0,
    }

    def account_slic(provider, fallback_status):
        before = len(getattr(provider, "_cache_events", []))
        provider._prepare_case(sample[0])
        events = getattr(provider, "_cache_events", [])[before:]
        event = events[-1] if events else {"status": fallback_status}
        status = event.get("status")
        if status == "hit":
            counters["hit_count"] += 1
        elif status in ("miss", "mismatch"):
            counters["miss_count"] += 1
            if status == "mismatch":
                counters["validation_failure_count"] += 1
            counters["recomputed_count"] += 1
        else:
            raise ProbeFailure("unexpected SLIC cache status")

    hit_provider = _make_real_cache_provider(context, existing_root)
    for identifier in sample:
        cache_path = hit_provider._cache_path(identifier)
        if not os.path.isfile(cache_path):
            counters["miss_count"] += 1
            continue
        before = len(getattr(hit_provider, "_cache_events", []))
        hit_provider._prepare_case(identifier)
        events = getattr(hit_provider, "_cache_events", [])[before:]
        event = events[-1] if events else {"status": "hit"}
        if event.get("status") == "hit":
            counters["hit_count"] += 1
        elif event.get("status") in ("miss", "mismatch"):
            counters["miss_count"] += 1
            if event.get("status") == "mismatch":
                counters["validation_failure_count"] += 1
            counters["recomputed_count"] += 1
        else:
            raise ProbeFailure("unexpected existing SLIC cache status")

    # Exercise the actual cold-miss branch on a real A image/ROI, but keep the
    # generated cache in the iteration's temporary directory.
    cold_root = os.path.join(temp_root, "slic_cache_cold")
    cold_provider = _make_real_cache_provider(context, cold_root)
    account_slic(cold_provider, "miss")

    # Corrupt only a temporary copy of a real cache entry and verify that the
    # production provider records the mismatch and recomputes that case.
    corrupt_root = os.path.join(temp_root, "slic_cache_corrupt")
    os.makedirs(corrupt_root, exist_ok=True)
    source_path = os.path.join(existing_root, sample[0] + ".npz")
    corrupt_path = os.path.join(corrupt_root, sample[0] + ".npz")
    with np.load(source_path) as cached:
        labels = cached["labels"].astype(np.int32, copy=False)
        roi = cached["roi"].astype(bool, copy=False)
    corrupt_roi = roi.copy()
    corrupt_roi.flat[0] = not bool(corrupt_roi.flat[0])
    with open(corrupt_path, "wb") as handle:
        np.savez_compressed(handle, labels=labels, roi=corrupt_roi)
    corrupt_provider = _make_real_cache_provider(context, corrupt_root)
    before = len(getattr(corrupt_provider, "_cache_events", []))
    try:
        corrupt_provider._prepare_case(sample[0])
    except BaseException:
        counters["validation_failure_count"] += 1
        raise
    else:
        events = getattr(corrupt_provider, "_cache_events", [])[before:]
        if events and events[-1].get("status") != "mismatch":
            raise ProbeFailure("corrupt SLIC cache mismatch was not recorded")
        counters["validation_failure_count"] += 1
        counters["recomputed_count"] += 1
    return counters


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


def _make_provider(case, extractors, stub_radiomics=False):
    """Use the production provider methods against a synthetic case."""
    provider = formal.AOnlyFoldFeatureProvider.__new__(
        formal.AOnlyFoldFeatureProvider)
    provider._extractors = extractors
    provider._case_cache = {}
    provider._fit_cache = {}
    provider._state_cache = {}
    provider._feature_cache = {}
    provider._mask_signatures = {}
    provider._cache_events = []
    provider._cache_counts = {
        "slic_hits": 0, "slic_misses": 0, "slic_invalidations": 0,
        "representation_hits": 0, "representation_misses": 0,
        "representation_invalidations": 0,
        "feature_hits": 0, "feature_misses": 0,
        "feature_invalidations": 0,
    }
    provider._cache_contract = {"schema": "synthetic-l4-probe"}
    provider_case = dict(case)
    provider_case.update({
        "geometry_hash": "synthetic-geometry",
        "image_file_sha256": "synthetic-image",
        "roi_file_sha256": "synthetic-roi",
    })
    provider._prepare_case = lambda _identifier: provider_case
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
    started_wall = time.perf_counter()
    started_cpu = time.process_time()
    try:
        before = resource_snapshot()
    except BaseException as exc:  # record aggregate failure and fail closed
        return _failure_record(name, exc)
    try:
        details = function()
    except BaseException as exc:  # record aggregate failure and fail closed
        return _failure_record(name, exc)
    elapsed = time.perf_counter() - started_wall
    cpu_elapsed = time.process_time() - started_cpu
    try:
        after = resource_snapshot()
    except BaseException as exc:  # sampling failures are observable failures
        return _failure_record(name, exc)
    if not math.isfinite(elapsed) or elapsed <= 0.0:
        return {"ok": False, "stage": name, "error_type": "InvalidTiming"}
    result = {
        "ok": True,
        "stage": name,
        "seconds": float(elapsed),
        "cpu_percent": float(100.0 * cpu_elapsed / elapsed),
        "rss_bytes": int(after["rss_bytes"]),
        "read_bytes": max(0, int(after["read_bytes"] - before["read_bytes"])),
        "write_bytes": max(0, int(after["write_bytes"] - before["write_bytes"])),
    }
    if details is not None:
        result["metrics"] = details
    return result


def _single_iteration(temp_root, real_technical=False):
    technical_context = None
    try:
        rng = np.random.RandomState(SYNTHETIC_SEED)
        image, _mask, case = _make_synthetic_image(temp_root)
        cfg = formal.w07._read_json(formal.HABITAT_CONFIG)
        fixture_matrix = rng.normal(size=(32, 6))
        fixture_values = np.linspace(-1.0, 1.0, 48).reshape(8, 6)
        times, events, risk = _make_survival_arrays()
        frame = _make_synthetic_frame()
        extractors = formal._build_exact_feature_extractors()
        state = w08.FoldState("synthetic-training", 2026,
                              (-0.5, 0.5), 0.0, {})
        provider_for_g = _make_provider(case, extractors, stub_radiomics=True)
        provider_for_r = _make_provider(case, extractors, stub_radiomics=False)
    except BaseException as exc:
        return [_failure_record("initialization", exc)]

    def input_load():
        nonlocal technical_context
        if real_technical:
            technical_context = _load_real_a_technical_inputs()
            return {"technical_input": technical_context["input_metrics"]}
        source = os.path.join(temp_root, "synthetic_input.csv")
        pd.DataFrame(fixture_matrix).to_csv(source, index=False)
        loaded = pd.read_csv(source)
        if loaded.shape != fixture_matrix.shape:
            raise ProbeFailure("synthetic input shape changed")
        return {"technical_input": {
            "sample_count": int(loaded.shape[0]),
            "successful_count": int(loaded.shape[0]),
            "failure_count": 0,
        }}

    def slic_cache():
        if real_technical:
            if technical_context is None:
                raise ProbeFailure("A technical input stage did not complete")
            return {"slic_cache": _real_slic_cache_probe(
                technical_context, temp_root)}
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
        return {"slic_cache": {
            "existing_cache_file_count": 0,
            "existing_cache_sample_count": 0,
            "hit_count": 0,
            "miss_count": 1,
            "validation_failure_count": 0,
            "recomputed_count": 1,
        }}

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
    metric_names = sorted({
        str(metric_name)
        for record in successful
        for metrics in (record.get("metrics", {}),)
        if isinstance(metrics, dict)
        for metric_name in metrics
    })
    for namespace in metric_names:
        values_by_key = OrderedDict()
        for record in successful:
            metrics = record.get("metrics", {})
            values = metrics.get(namespace, {})
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    values_by_key.setdefault(str(key), []).append(float(value))
        if values_by_key:
            result[namespace] = OrderedDict(
                (key, dict(_aggregate(values, digits=0),
                           total=int(sum(values))))
                for key, values in values_by_key.items())
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


def _estimation_payload(repeats, estimate_seconds):
    if estimate_seconds is None:
        return {
            "pilot_repeat_count": 0,
            "estimated_total_seconds": None,
            "over_40_minutes": None,
            "basis": "pilot estimate not supplied by the caller",
        }
    estimate_seconds = float(estimate_seconds)
    if not math.isfinite(estimate_seconds) or estimate_seconds <= 0:
        raise ValueError("estimate_seconds must be a positive finite number")
    estimated_total = estimate_seconds * float(repeats) * 1.15
    return {
        "pilot_repeat_count": 1,
        "estimated_total_seconds": round(estimated_total, 3),
        "over_40_minutes": bool(estimated_total > 2400.0),
        "basis": "one complete A-technical plus synthetic repeat immediately before the measured repeats; 15 percent guard",
    }


def _safe_estimate_seconds(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _safety_payload():
    return {
        "outcome_columns_read": False,
        "formal_writer_invoked": False,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
    }


def _build_payload(status, repeats, stages, failure_stage_counts,
                   estimate_seconds=None, failed_stage=None,
                   error_type=None, aggregate_message=None,
                   technical_inputs=True):
    payload = {
        "schema": "w08_local_optimization_probe",
        "schema_version": "1.1",
        "status": str(status),
        "scope": ("A-only technical and synthetic technical timing"
                   if technical_inputs else "synthetic technical timing only"),
        "repeat_count": int(repeats),
        "stages": stages,
        "failure_stage_counts": OrderedDict(failure_stage_counts),
        "estimation": _estimation_payload(repeats, estimate_seconds),
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
        "safety": _safety_payload(),
        "generated_at_utc": datetime.datetime.utcnow().replace(
            microsecond=0).isoformat() + "Z",
    }
    if technical_inputs:
        payload["real_a_technical_input"] = stages.get(
            "a_input_load", {}).get("technical_input", {})
        payload["slic_cache_evidence"] = stages.get(
            "slic_cache_prepare_validate", {}).get("slic_cache", {})
    if failed_stage is not None:
        payload["failed_stage"] = str(failed_stage)
    if error_type is not None:
        payload["error_type"] = str(error_type)
    if aggregate_message is not None:
        payload["aggregate_error_message"] = str(aggregate_message)
    return payload


def _empty_stages():
    return OrderedDict((name, _aggregate_stage([])) for name in STAGE_NAMES)


def _failure_summary(stages, failure_stage_counts, repeats,
                     estimate_seconds, technical_inputs, failed_stage,
                     error_type, message):
    payload = _build_payload(
        "failed", repeats, stages, failure_stage_counts,
        estimate_seconds=estimate_seconds, failed_stage=failed_stage,
        error_type=error_type, aggregate_message=message,
        technical_inputs=technical_inputs)
    _validate_aggregate_safety(payload)
    return payload


def _invoke_single_iteration(temp_root, technical_inputs):
    if technical_inputs:
        return _single_iteration(temp_root, real_technical=True)
    return _single_iteration(temp_root)


def run_probe(output_dir, repeats=REPEAT_COUNT, estimate_seconds=None,
              technical_inputs=True):
    """Run the three-repeat probe with fail-closed aggregate state handling."""
    output_dir = os.path.abspath(os.fspath(output_dir))
    os.makedirs(output_dir, exist_ok=True)
    state_estimate_seconds = _safe_estimate_seconds(estimate_seconds)
    baseline_stages = _empty_stages()
    baseline = _build_payload(
        "initializing", repeats if type(repeats) is int else 0,
        baseline_stages, OrderedDict(),
        estimate_seconds=state_estimate_seconds,
        technical_inputs=bool(technical_inputs))
    _validate_aggregate_safety(baseline)
    _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), baseline)

    try:
        if type(repeats) is not int or repeats < 3:
            raise ValueError("L2 requires at least three repeats")
        # Validate the caller's estimate after the non-complete baseline is
        # durable, so invalid input cannot leave a stale successful summary.
        _estimation_payload(repeats, estimate_seconds)
        # The baseline above replaces any prior complete result before any
        # source, cache, stage, or sampling work begins.
        running = _build_payload(
            "running", repeats, baseline_stages, OrderedDict(),
            estimate_seconds=state_estimate_seconds,
            technical_inputs=bool(technical_inputs))
        _validate_aggregate_safety(running)
        _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), running)

        existing = [name for name in os.listdir(output_dir)
                    if name not in (OUTPUT_NAME,)]
        forbidden = sorted(set(existing) & FORBIDDEN_OUTPUT_NAMES)
        if forbidden:
            raise ProbeFailure("probe output directory contains formal artifacts")

        records_by_stage = OrderedDict((name, []) for name in STAGE_NAMES)
        unknown_failures = []
        for _repeat in range(repeats):
            try:
                with tempfile.TemporaryDirectory(prefix="w08_l2_probe_") as temp_root:
                    records = _invoke_single_iteration(temp_root,
                                                       bool(technical_inputs))
                if not isinstance(records, (list, tuple)):
                    raise ProbeFailure("iteration did not return stage records")
                for record in records:
                    if not isinstance(record, dict) or \
                            record.get("stage") not in records_by_stage:
                        unknown_failures.append(record)
                        continue
                    records_by_stage[record["stage"]].append(record)
            except BaseException as exc:
                unknown_failures.append(_failure_record("iteration", exc))

        stages = OrderedDict((name, _aggregate_stage(records))
                             for name, records in records_by_stage.items())
        failure_stage_counts = OrderedDict()
        failure_details = []
        for records in records_by_stage.values():
            for record in records:
                if not record.get("ok"):
                    stage = _normalise_failure_stage(
                        record.get("stage", "unknown"))
                    failure_stage_counts[stage] = \
                        int(failure_stage_counts.get(stage, 0) + 1)
                    failure_details.append(record)
        for record in unknown_failures:
            stage = _normalise_failure_stage(record.get("stage", "iteration")) \
                if isinstance(record, dict) else "iteration"
            failure_stage_counts[stage] = \
                int(failure_stage_counts.get(stage, 0) + 1)
            if isinstance(record, dict):
                failure_details.append(record)
        completed = not failure_stage_counts and all(
            stage["success_count"] == repeats for stage in stages.values())
        if not completed:
            first_failure = failure_details[0] if failure_details else {}
            failed_stage = _normalise_failure_stage(
                first_failure.get("stage", "iteration"))
            error_type = _normalise_error_type(
                first_failure.get("error_type", "StageFailure"))
            payload = _failure_summary(
                stages, failure_stage_counts, repeats, state_estimate_seconds,
                bool(technical_inputs), failed_stage, error_type,
                "L2 probe failed closed during %s." % failed_stage)
            _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), payload)
            raise ProbeFailure("L2 probe failed closed at %s" % failed_stage)

        payload = _build_payload(
            "complete", repeats, stages, failure_stage_counts,
            estimate_seconds=state_estimate_seconds,
            technical_inputs=bool(technical_inputs))
        _validate_aggregate_safety(payload)
        _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), payload)
        return payload
    except BaseException as exc:
        # This catches initialization, iteration, aggregation, and validation
        # exceptions that occur before the normal failed payload is emitted.
        try:
            with open(os.path.join(output_dir, OUTPUT_NAME),
                      "r", encoding="utf-8") as handle:
                current = json.load(handle)
        except BaseException:
            current = {}
        if current.get("status") == "failed":
            raise
        stage = _normalise_failure_stage(
            current.get("failed_stage", "iteration"))
        error_type = _normalise_error_type(exc.__class__.__name__)
        failed_counts = OrderedDict(current.get("failure_stage_counts", {}))
        failed_counts[stage] = int(failed_counts.get(stage, 0) + 1)
        stages = current.get("stages", _empty_stages())
        payload = _failure_summary(
            stages, failed_counts,
            repeats if type(repeats) is int else 0,
            state_estimate_seconds, bool(technical_inputs), stage, error_type,
            "L2 probe failed closed during %s." % stage)
        _write_json_atomic(os.path.join(output_dir, OUTPUT_NAME), payload)
        if isinstance(exc, ProbeFailure):
            raise
        raise ProbeFailure("L2 probe failed closed during %s" % stage)


def write_audit_report(summary, path, estimate_seconds=None):
    """Write a concise, de-identified Markdown audit from aggregate JSON."""
    if summary.get("status") != "complete":
        raise ProbeFailure("cannot write a successful L2 audit from failed probe")
    technical_scope = summary.get("scope") == \
        "A-only technical and synthetic technical timing"
    lines = [
        "# W08 local L2 baseline profile audit",
        "",
        "## Scope",
        "",
        ("This audit contains outcome-blind A-only technical input/cache timing "
         "and deterministic synthetic numerical timing. "
         if technical_scope else
         "This audit contains synthetic, outcome-blind technical timing only. ")
        + "It contains no patient identifier, absolute path, clinical outcome, "
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
        ("- The A input stage calls the existing `read_technical_A` boundary "
         "with technical columns only; B access flags are all false."
         if technical_scope else
         "- Synthetic technical fixture only; B access flags are all false."),
        "",
    ]
    if technical_scope:
        input_metrics = summary.get("real_a_technical_input", {})
        cache_metrics = summary.get("slic_cache_evidence", {})

        def count_text(metrics, key):
            value = metrics.get(key)
            if not isinstance(value, dict):
                return "n/a"
            return "%d [%.0f, %.0f]" % (
                int(value.get("total", 0)), value.get("range", [0, 0])[0],
                value.get("range", [0, 0])[1])

        lines.extend([
            "## A-only technical input evidence",
            "",
            "The measured input stage used the existing outcome-blind A-only "
            "technical reader for frozen A metadata, a frozen A technical "
            "feature source, and the frozen A supervoxel summary. No outcome "
            "reader was invoked.",
            "",
            "| Counter | Total across repeats | Median [range] per repeat |",
            "|---|---:|---:|",
            "| Technical rows sampled | %s | %s |" % (
                count_text(input_metrics, "sample_count"),
                "n/a" if "sample_count" not in input_metrics else
                "%.0f [%.0f, %.0f]" % (
                    input_metrics["sample_count"]["median"],
                    input_metrics["sample_count"]["range"][0],
                    input_metrics["sample_count"]["range"][1])),
            "| Successful technical rows | %s | %s |" % (
                count_text(input_metrics, "successful_count"),
                "n/a" if "successful_count" not in input_metrics else
                "%.0f [%.0f, %.0f]" % (
                    input_metrics["successful_count"]["median"],
                    input_metrics["successful_count"]["range"][0],
                    input_metrics["successful_count"]["range"][1])),
            "| Failed technical rows | %s | %s |" % (
                count_text(input_metrics, "failure_count"),
                "n/a" if "failure_count" not in input_metrics else
                "%.0f [%.0f, %.0f]" % (
                    input_metrics["failure_count"]["median"],
                    input_metrics["failure_count"]["range"][0],
                    input_metrics["failure_count"]["range"][1])),
            "",
            "## Existing SLIC cache evidence",
            "",
            "The SLIC stage exercised the production A-only case preparation "
            "and cache validation logic. Existing cache entries were checked "
            "read-only; cold-miss and invalid-cache checks used temporary "
            "copies that were removed after each repeat.",
            "",
            "| Counter | Total across repeats | Median [range] per repeat |",
            "|---|---:|---:|",
        ])
        for key, label in (
                ("existing_cache_file_count", "Existing cache files"),
                ("existing_cache_sample_count", "Existing cache sample"),
                ("hit_count", "Cache hits"),
                ("miss_count", "Cache misses"),
                ("validation_failure_count", "Validation failures"),
                ("recomputed_count", "Recomputed entries")):
            value = cache_metrics.get(key)
            per_repeat = "n/a" if not isinstance(value, dict) else \
                "%.0f [%.0f, %.0f]" % (
                    value["median"], value["range"][0], value["range"][1])
            lines.append("| %s | %s | %s |" % (
                label, count_text(cache_metrics, key), per_repeat))
    lines.extend([
        "## Aggregate timing and resource profile",
        "",
        "All values below retain only the median, inclusive range, and counts "
        "across the three repeats.",
        "",
        "| Stage | Success / repeats | Failures | Median seconds | Range seconds |",
        "|---|---:|---:|---:|---:|",
    ])
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
        "and A technical/synthetic input and cache I/O. These are software "
        "timing observations only and are not model performance measurements.",
        "",
        "## Runtime estimate",
        "",
        "- Basis: one complete A-technical plus synthetic repeat immediately "
        "before the measured repeats, with a 15% guard.",
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
    parser.add_argument("--synthetic-only", action="store_true",
                        help="run the legacy synthetic-only probe")
    args = parser.parse_args(argv)
    summary = run_probe(args.output, repeats=args.repeats,
                        estimate_seconds=args.estimate_seconds,
                        technical_inputs=not args.synthetic_only)
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
