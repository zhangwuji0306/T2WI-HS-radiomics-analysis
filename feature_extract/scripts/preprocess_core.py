"""Strict preprocessing implementation with explicit, auditable normalization."""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import tempfile
import time
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import SimpleITK as sitk

from workflow_utils import (
    atomic_write_csv, atomic_write_json, atomic_write_text, git_commit,
    merge_rows, physical_points_inside_image, read_csv_or_empty,
    stable_json_sha256, utc_now,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
ASCII_PROJECT_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), "radiomics26")
OUT = os.path.join(ROOT, "output")
PREP_DIR = os.path.join(OUT, "preprocessed")
QC_DIR = os.path.join(OUT, "qc")
QC_LOG = os.path.join(QC_DIR, "logs")
QC_REPORT = os.path.join(QC_DIR, "qc_report.csv")
TIMING_CSV = os.path.join(QC_LOG, "preprocess_timing.csv")
METRICS_CSV = os.path.join(QC_LOG, "preprocess_metrics.csv")
CONFIG = os.path.join(ROOT, "configs", "radiomics_params.yaml")

DEFAULTS = {
    "target_spacing": [1.0, 1.0, 2.0],
    "resample_interpolator": "sitkBSpline",
    "mask_interpolator": "sitkNearestNeighbor",
    "n4_enabled": False,
    "n4_mask": "foreground",
    "n4_downsample_factor": 2.0,
    "normalization": "muscle",
    "erode_radius_R1": [1, 1, 0],
    "erode_radius_R2": [2, 2, 0],
    "crop_padding": 5,
    "geometry_tolerance": 1e-3,
    "min_tumor_voxels": 10,
}
INTERP = {"sitkBSpline": sitk.sitkBSpline,
          "sitkNearestNeighbor": sitk.sitkNearestNeighbor}
TIMING_COLS = [
    "影像号", "读者", "normalization_requested", "n4_enabled",
    "read", "n4", "resample", "align", "crop", "normalize", "save", "total",
]
METRICS_COLS = [
    "影像号", "读者", "normalization_requested", "normalization_applied",
    "normalization_status", "reference_label", "reference_mean", "reference_sd",
    "failure_code", "reference_voxels", "eroded_voxels", "erode_radius",
    "reference_cv", "reference_p10", "reference_p50", "reference_p90",
    "reference_grad",
]
PIPELINE_VERSION = "v5-strict-normalization"


def ascii_path(path: str) -> str:
    """Route local Windows SimpleITK I/O through the ASCII junction."""
    absolute = os.path.abspath(str(path))
    project_root = os.path.abspath(PROJECT_ROOT)
    if absolute.lower().startswith((project_root + os.sep).lower()):
        return os.path.join(
            ASCII_PROJECT_ROOT, absolute[len(project_root) + 1:])
    return absolute


def preprocessing_config_sha256(cfg: Dict) -> str:
    return stable_json_sha256(cfg)


def pipeline_stamp(cfg: Dict) -> str:
    return stable_json_sha256(
        {"pipeline_version": PIPELINE_VERSION, "preprocessing": cfg})


def load_config() -> Dict:
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        import yaml
        with open(CONFIG, encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        cfg.update(payload.get("preprocessing") or {})
    return cfg


def mask_image(mask_arr: np.ndarray, ref: sitk.Image, label: int) -> sitk.Image:
    image = sitk.GetImageFromArray((mask_arr == label).astype(np.uint8))
    image.CopyInformation(ref)
    return image


def foreground_mask(image: sitk.Image) -> sitk.Image:
    threshold = sitk.OtsuThresholdImageFilter()
    threshold.SetOutsideValue(0)
    threshold.SetInsideValue(1)
    mask = threshold.Execute(sitk.Cast(image, sitk.sitkFloat32))
    labelled = sitk.RelabelComponent(sitk.ConnectedComponent(mask > 0))
    result = labelled == 1
    result.CopyInformation(image)
    return result


def muscle_stats(image: sitk.Image, mask_arr: np.ndarray, label: int,
                 erode_radius: List[int]) -> Dict:
    binary = (mask_arr == label).astype(np.uint8)
    total = int(binary.sum())
    radius = [int(value) for value in erode_radius]
    stats = {"total": total, "eroded": 0, "erode_radius": radius}
    if total == 0:
        return stats
    mask = sitk.GetImageFromArray(binary)
    mask.CopyInformation(image)
    eroded = sitk.GetArrayFromImage(
        sitk.BinaryErode(mask, kernelRadius=radius, kernelType=sitk.sitkBox))
    stats["eroded"] = int(eroded.sum())
    if stats["eroded"] == 0:
        return stats
    array = sitk.GetArrayFromImage(image).astype(np.float64)
    values = array[eroded == 1]
    mean, sd = float(values.mean()), float(values.std())
    p10, p50, p90 = (float(np.percentile(values, q)) for q in (10, 50, 90))
    _, ys, xs = np.where(eroded == 1)
    if values.size > 20000:
        step = int(np.ceil(values.size / 20000.0))
        selected = np.arange(0, values.size, step)
        xs, ys, values = xs[selected], ys[selected], values[selected]
    matrix = np.column_stack([xs, ys, np.ones_like(xs)])
    try:
        coefficient, _, _, _ = np.linalg.lstsq(matrix, values, rcond=None)
        grad = float(np.hypot(coefficient[0], coefficient[1]) / mean * 100.0)
        grad /= min(image.GetSpacing()[0], image.GetSpacing()[1])
    except Exception:
        grad = float("nan")
    stats.update({
        "mean": mean, "sd": sd,
        "cv": float(sd / mean) if mean > 0 else float("nan"),
        "p10": p10, "p50": p50, "p90": p90, "grad": grad,
    })
    return stats


def muscle_failure(stats: Dict, reader: str) -> str:
    if int(stats.get("total", 0)) == 0:
        return reader + "_MUSCLE_LABEL_MISSING"
    if int(stats.get("eroded", 0)) == 0:
        return reader + "_MUSCLE_EROSION_EMPTY"
    mean = stats.get("mean")
    if mean is None or not np.isfinite(float(mean)) or float(mean) <= 0:
        return reader + "_MUSCLE_MEAN_INVALID"
    return ""


def metric_row(requested: str, status: str, applied: str = "",
               label: str = "", stats: Optional[Dict] = None,
               failure_code: str = "", reference_mean: Optional[float] = None,
               reference_sd: Optional[float] = None) -> Dict:
    stats = stats or {}
    mean = stats.get("mean") if reference_mean is None else reference_mean
    sd = stats.get("sd") if reference_sd is None else reference_sd
    return {
        "normalization_requested": requested,
        "normalization_applied": applied,
        "normalization_status": status,
        "reference_label": label,
        "reference_mean": mean,
        "reference_sd": sd,
        "failure_code": failure_code,
        "reference_voxels": stats.get("total"),
        "eroded_voxels": stats.get("eroded"),
        "erode_radius": ",".join(map(str, stats.get("erode_radius", []))),
        "reference_cv": stats.get("cv"),
        "reference_p10": stats.get("p10"),
        "reference_p50": stats.get("p50"),
        "reference_p90": stats.get("p90"),
        "reference_grad": stats.get("grad"),
    }


def n4_correct(image: sitk.Image, mask: Optional[sitk.Image],
               factor: float = 1.0) -> sitk.Image:
    filt = sitk.N4BiasFieldCorrectionImageFilter()
    float_image = sitk.Cast(image, sitk.sitkFloat32)
    if mask is None or factor <= 1.0:
        return filt.Execute(float_image, mask) if mask is not None else filt.Execute(float_image)
    spacing = [value * factor for value in float_image.GetSpacing()]
    coarse_image = resample_to(float_image, spacing=spacing, interp=sitk.sitkBSpline)
    coarse_mask = resample_to(
        mask, spacing=spacing, interp=sitk.sitkNearestNeighbor,
        pixel=sitk.sitkUInt8)
    filt.Execute(coarse_image, coarse_mask)
    bias = filt.GetLogBiasFieldAsImage(float_image)
    result = float_image / sitk.Exp(bias)
    result.CopyInformation(float_image)
    return result


def resample_to(image: sitk.Image, spacing=None, grid=None,
                interp=sitk.sitkBSpline, pixel=None,
                default: float = 0.0) -> sitk.Image:
    if grid is not None:
        size, origin, target_spacing, direction = grid
    else:
        size = [
            int(math.ceil(image.GetSize()[i] * image.GetSpacing()[i] / spacing[i]))
            for i in range(3)
        ]
        origin, target_spacing = image.GetOrigin(), list(spacing)
        direction = image.GetDirection()
    return sitk.Resample(
        image, size, sitk.Transform(), interp, origin, target_spacing,
        direction, default,
        pixel if pixel is not None else image.GetPixelIDValue())


def crop_bbox(image: sitk.Image, mask_arr: np.ndarray, pad: int) -> sitk.Image:
    zs, ys, xs = np.where(mask_arr)
    z0 = max(int(zs.min()) - pad, 0)
    z1 = min(int(zs.max()) + pad + 1, mask_arr.shape[0])
    y0 = max(int(ys.min()) - pad, 0)
    y1 = min(int(ys.max()) + pad + 1, mask_arr.shape[1])
    x0 = max(int(xs.min()) - pad, 0)
    x1 = min(int(xs.max()) + pad + 1, mask_arr.shape[2])
    array = sitk.GetArrayFromImage(image)[z0:z1, y0:y1, x0:x1]
    result = sitk.GetImageFromArray(array)
    result.SetSpacing(image.GetSpacing())
    result.SetOrigin(image.TransformIndexToPhysicalPoint((x0, y0, z0)))
    result.SetDirection(image.GetDirection())
    return result


def zscore_roi(image: sitk.Image,
               mask_arr: np.ndarray) -> Tuple[sitk.Image, float, float]:
    array = sitk.GetArrayFromImage(image).astype(np.float32)
    values = array[mask_arr == 1]
    mean, sd = float(values.mean()), float(values.std())
    if not np.isfinite(mean) or not np.isfinite(sd) or sd <= 1e-12:
        return sitk.Cast(image, sitk.sitkFloat32), mean, sd
    result = sitk.GetImageFromArray((array - mean) / sd)
    result.CopyInformation(image)
    return result, mean, sd


def geom_consistent(left: sitk.Image, right: sitk.Image, tol: float) -> bool:
    if list(left.GetSize()) != list(right.GetSize()):
        return False
    lv = list(left.GetSpacing()) + list(left.GetOrigin()) + list(left.GetDirection())
    rv = list(right.GetSpacing()) + list(right.GetOrigin()) + list(right.GetDirection())
    return all(abs(a - b) <= tol for a, b in zip(lv, rv))


def tumor_bbox_points(mask_arr: np.ndarray,
                      image: sitk.Image) -> List[Tuple[float, ...]]:
    zs, ys, xs = np.where(mask_arr == 1)
    if len(zs) == 0:
        return []
    return [
        image.TransformIndexToPhysicalPoint((int(x), int(y), int(z)))
        for z in (zs.min(), zs.max())
        for y in (ys.min(), ys.max())
        for x in (xs.min(), xs.max())
    ]


def image_metadata(path: str, image: sitk.Image) -> Dict:
    stat = os.stat(path)
    try:
        stored_path = os.path.relpath(path, ROOT)
    except ValueError:
        # Windows cannot make a relative path across different drive letters.
        # This occurs for isolated test/temp locations; production inputs stay
        # below ROOT and therefore remain repository-relative in metadata.
        stored_path = os.path.abspath(path)
    return {
        "path": stored_path,
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
        "image_size": list(image.GetSize()),
        "spacing": list(image.GetSpacing()),
        "origin": list(image.GetOrigin()),
        "direction": list(image.GetDirection()),
        "pixel_type": image.GetPixelIDTypeAsString(),
    }


def atomic_write_image(image: sitk.Image, path: str) -> None:
    io_path = ascii_path(path)
    os.makedirs(os.path.dirname(io_path), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(
        prefix="." + os.path.basename(io_path) + ".", suffix=".nrrd",
        dir=os.path.dirname(io_path))
    os.close(fd)
    try:
        sitk.WriteImage(image, temp_path)
        os.replace(temp_path, io_path)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def remove_outputs(paths: List[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


def is_present(value) -> bool:
    return value is not None and not pd.isna(value) and str(value).strip() != ""


def build_metadata(cfg: Dict, normalization: str, inputs: Dict,
                   readers: Dict) -> Dict:
    return {
        "pipeline_version": PIPELINE_VERSION,
        "pipeline_stamp": pipeline_stamp(cfg),
        "git_commit": git_commit(ROOT),
        "config_sha256": preprocessing_config_sha256(cfg),
        "normalization": normalization,
        "created_at": utc_now(),
        "simpleitk_version": sitk.Version_VersionString(),
        "numpy_version": np.__version__,
        "inputs": inputs,
        "readers": readers,
    }


def case_is_current(outdir: str, cfg: Dict, has_r2: bool) -> bool:
    stamp_path = os.path.join(outdir, ".pipeline_stamp")
    metadata_path = os.path.join(outdir, "pipeline_metadata.json")
    r1 = [os.path.join(outdir, name)
          for name in ("R1_image.nrrd", "R1_mask.nrrd")]
    if not all(os.path.exists(path) for path in r1):
        return False
    try:
        with open(stamp_path, encoding="ascii") as handle:
            if handle.read().strip() != pipeline_stamp(cfg):
                return False
        with open(metadata_path, encoding="utf-8") as handle:
            metadata = json.load(handle)
    except (OSError, ValueError):
        return False
    if metadata.get("pipeline_stamp") != pipeline_stamp(cfg):
        return False
    if has_r2:
        r2 = [os.path.join(outdir, name)
              for name in ("R2_image.nrrd", "R2_mask.nrrd")]
        r2_status = (metadata.get("readers") or {}).get("R2", {}).get("status")
        if r2_status != "success" or not all(os.path.exists(path) for path in r2):
            return False
    return True


def save_qc(qc: Dict, processed_ids: List[str]) -> None:
    old = read_csv_or_empty(QC_REPORT)
    if not old.empty and {"影像号", "阶段"}.issubset(old.columns):
        old = old.loc[
            ~((old["阶段"] == "preprocess") & old["影像号"].isin(processed_ids))]
    rows = []
    for pid in qc:
        rows.extend(qc[pid])
    combined = pd.concat([old, pd.DataFrame(rows)], ignore_index=True, sort=False)
    if not combined.empty:
        combined = combined.drop_duplicates(
            subset=["影像号", "阶段", "代码", "说明"], keep="last")
    atomic_write_csv(combined, QC_REPORT)


def process(pid: str, row: pd.Series, cfg: Dict, qc: Dict,
            force: bool) -> Tuple[str, Dict, Optional[Dict], Dict]:
    relative = lambda path: ascii_path(os.path.join(ROOT, path))
    outdir = os.path.join(PREP_DIR, pid)
    os.makedirs(outdir, exist_ok=True)
    r1_files = [os.path.join(outdir, name)
                for name in ("R1_image.nrrd", "R1_mask.nrrd")]
    r2_files = [os.path.join(outdir, name)
                for name in ("R2_image.nrrd", "R2_mask.nrrd")]
    has_r2 = (
        str(row.get("是否双读者", "")) == "1"
        and is_present(row.get("R2图像文件"))
        and is_present(row.get("R2掩膜文件"))
    )
    stamp_path = os.path.join(outdir, ".pipeline_stamp")
    metadata_path = os.path.join(outdir, "pipeline_metadata.json")
    if not force and case_is_current(outdir, cfg, has_r2):
        return "skipped", {}, None, {}
    # A stale pair must never remain usable if this case is reprocessed and fails.
    # The derived outputs are disposable; remove only this case's known files.
    remove_outputs(r1_files + r2_files + [stamp_path, metadata_path])

    requested = str(cfg["normalization"])
    qc[pid] = []
    metrics = {}
    base_timing = {
        "read": 0.0, "n4": 0.0, "resample": 0.0, "align": 0.0,
        "crop": 0.0, "normalize": 0.0, "save": 0.0, "total": 0.0,
    }
    timing_r1 = dict(base_timing)
    timing_r2 = dict(base_timing) if has_r2 else None
    reader_meta = {"R1": {"status": "pending"}}
    if has_r2:
        reader_meta["R2"] = {"status": "pending"}
    input_meta = {}

    def warn(code: str, message: str, level: str = "WARN") -> None:
        qc[pid].append({
            "影像号": pid, "阶段": "preprocess", "级别": level,
            "代码": code, "说明": requested + ": " + message,
        })

    def fail_r1(code: str, message: str,
                stats: Optional[Dict] = None):
        warn(code, message, "ERROR")
        label = "3" if requested == "muscle" else "1"
        metrics["R1"] = metric_row(
            requested, "failed", label=label, stats=stats,
            failure_code=code)
        reader_meta["R1"] = {"status": "failed", "failure_code": code}
        if has_r2:
            reader_meta["R2"] = {
                "status": "not_run", "failure_code": "R1_FAILED"}
        remove_outputs(r1_files + r2_files)
        atomic_write_json(
            metadata_path,
            build_metadata(cfg, requested, input_meta, reader_meta))
        return "failed", timing_r1, timing_r2, metrics

    t0 = time.perf_counter()
    image1_path = relative(row["图像文件"])
    mask1_path = relative(row["掩膜文件"])
    image1 = sitk.ReadImage(image1_path)
    mask1 = sitk.ReadImage(mask1_path)
    timing_r1["read"] = time.perf_counter() - t0
    input_meta["R1_image"] = image_metadata(image1_path, image1)
    input_meta["R1_mask"] = image_metadata(mask1_path, mask1)
    if not geom_consistent(
            image1, mask1, float(cfg["geometry_tolerance"])):
        return fail_r1(
            "R1_GEOM_MISMATCH", "R1图像与掩膜几何不一致")
    mask1_array = sitk.GetArrayFromImage(mask1)
    tumor1 = int((mask1_array == 1).sum())
    if tumor1 == 0:
        return fail_r1("R1_NO_TUMOR", "R1无肿瘤勾画")
    if tumor1 < int(cfg["min_tumor_voxels"]):
        warn("R1_SMALL_TUMOR", "R1肿瘤体素数低于最小记录阈值")

    n4_on = bool(cfg.get("n4_enabled"))
    n4_factor = float(cfg.get("n4_downsample_factor", 1.0))
    t0 = time.perf_counter()
    n4_mask1 = (
        foreground_mask(image1)
        if n4_on and cfg["n4_mask"] == "foreground" else None)
    corrected1 = (
        n4_correct(image1, n4_mask1, n4_factor)
        if n4_on else sitk.Cast(image1, sitk.sitkFloat32))
    timing_r1["n4"] = time.perf_counter() - t0

    muscle1 = None
    if requested == "muscle":
        muscle1 = muscle_stats(
            corrected1, mask1_array, 3, list(cfg["erode_radius_R1"]))
        code = muscle_failure(muscle1, "R1")
        if code:
            return fail_r1(
                code, "R1肌肉参照不满足归一化要求", muscle1)

    t0 = time.perf_counter()
    spacing = list(cfg["target_spacing"])
    resampled1 = resample_to(
        corrected1, spacing=spacing,
        interp=INTERP[cfg["resample_interpolator"]])
    resampled_mask1 = resample_to(
        mask_image(mask1_array, image1, 1), spacing=spacing,
        interp=INTERP[cfg["mask_interpolator"]],
        pixel=sitk.sitkUInt8)
    timing_r1["resample"] = time.perf_counter() - t0
    if not geom_consistent(
            resampled1, resampled_mask1,
            float(cfg["geometry_tolerance"])):
        return fail_r1(
            "R1_RESAMPLED_GEOM_MISMATCH",
            "重采样后R1图像与掩膜几何不一致")
    tumor_mask1 = sitk.GetArrayFromImage(resampled_mask1) == 1
    if int(tumor_mask1.sum()) == 0:
        return fail_r1(
            "R1_TUMOR_LOST_AFTER_RESAMPLE", "重采样后R1肿瘤为空")

    r2_valid = False
    r2_failure = ""
    muscle2 = None
    muscle_label = ""
    if has_r2 and timing_r2 is not None:
        try:
            t0 = time.perf_counter()
            image2_path = relative(row["R2图像文件"])
            mask2_path = relative(row["R2掩膜文件"])
            image2 = sitk.ReadImage(image2_path)
            mask2 = sitk.ReadImage(mask2_path)
            timing_r2["read"] = time.perf_counter() - t0
            input_meta["R2_image"] = image_metadata(image2_path, image2)
            input_meta["R2_mask"] = image_metadata(mask2_path, mask2)
            if not geom_consistent(
                    image2, mask2, float(cfg["geometry_tolerance"])):
                r2_failure = "R2_GEOM_MISMATCH"
            mask2_array = sitk.GetArrayFromImage(mask2)
            if not r2_failure and int((mask2_array == 1).sum()) == 0:
                r2_failure = "R2_NO_TUMOR"
            points = tumor_bbox_points(mask1_array, image1)
            if (not r2_failure
                    and not physical_points_inside_image(image2, points)):
                r2_failure = "R2_FOV_NOT_COVERED"
            if not r2_failure and requested == "muscle":
                label_status = str(
                    row.get("R2肌肉标签状态", "")).strip().lower()
                muscle_label = str(row.get("R2肌肉标签", "")).strip()
                if label_status == "missing":
                    r2_failure = "R2_MUSCLE_LABEL_MISSING"
                elif (label_status != "resolved"
                      or muscle_label not in ("2", "3")):
                    r2_failure = "R2_MUSCLE_LABEL_UNRESOLVED"
            if not r2_failure:
                t0 = time.perf_counter()
                n4_mask2 = (
                    foreground_mask(image2)
                    if n4_on and cfg["n4_mask"] == "foreground" else None)
                corrected2 = (
                    n4_correct(image2, n4_mask2, n4_factor)
                    if n4_on else sitk.Cast(image2, sitk.sitkFloat32))
                timing_r2["n4"] = time.perf_counter() - t0
                if requested == "muscle":
                    muscle2 = muscle_stats(
                        corrected2, mask2_array, int(muscle_label),
                        list(cfg["erode_radius_R2"]))
                    r2_failure = muscle_failure(muscle2, "R2")
            if not r2_failure:
                t0 = time.perf_counter()
                grid = (
                    list(resampled1.GetSize()), resampled1.GetOrigin(),
                    list(resampled1.GetSpacing()), resampled1.GetDirection(),
                )
                resampled2 = resample_to(
                    corrected2, grid=grid,
                    interp=INTERP[cfg["resample_interpolator"]])
                resampled_mask2 = resample_to(
                    mask_image(mask2_array, image2, 1), grid=grid,
                    interp=INTERP[cfg["mask_interpolator"]],
                    pixel=sitk.sitkUInt8)
                timing_r2["align"] = time.perf_counter() - t0
                tumor_mask2 = sitk.GetArrayFromImage(resampled_mask2) == 1
                if int(tumor_mask2.sum()) == 0:
                    r2_failure = "R2_TUMOR_LOST_AFTER_RESAMPLE"
                else:
                    r2_valid = True
        except Exception as exc:
            r2_failure = "R2_EXCEPTION"
            warn(
                r2_failure,
                "R2处理异常: {0}: {1}".format(type(exc).__name__, exc),
                "ERROR")

    if has_r2 and r2_failure:
        warn(r2_failure, "R2处理失败并从本次输出中跳过", "ERROR")
        remove_outputs(r2_files)
        metrics["R2"] = metric_row(
            requested, "failed",
            label=muscle_label if requested == "muscle" else "1",
            stats=muscle2, failure_code=r2_failure)
        reader_meta["R2"] = {
            "status": "failed", "failure_code": r2_failure}

    box = tumor_mask1 | tumor_mask2 if r2_valid else tumor_mask1
    t0 = time.perf_counter()
    cropped1 = crop_bbox(resampled1, box, int(cfg["crop_padding"]))
    cropped_mask1 = crop_bbox(
        resampled_mask1, box, int(cfg["crop_padding"]))
    timing_r1["crop"] = time.perf_counter() - t0
    t0 = time.perf_counter()
    if requested == "muscle":
        normalized1 = sitk.Cast(
            cropped1 / float(muscle1["mean"]), sitk.sitkFloat32)
        metrics["R1"] = metric_row(
            "muscle", "success", "muscle", "3", muscle1)
    else:
        normalized1, mean1, sd1 = zscore_roi(
            cropped1, sitk.GetArrayFromImage(cropped_mask1) == 1)
        if not np.isfinite(sd1) or sd1 <= 1e-12:
            return fail_r1(
                "R1_ZSCORE_SD_INVALID", "R1肿瘤ROI标准差无效")
        metrics["R1"] = metric_row(
            "zscore", "success", "zscore", "1",
            reference_mean=mean1, reference_sd=sd1)
    timing_r1["normalize"] = time.perf_counter() - t0
    cropped_mask1.CopyInformation(normalized1)
    t0 = time.perf_counter()
    atomic_write_image(normalized1, r1_files[0])
    atomic_write_image(cropped_mask1, r1_files[1])
    timing_r1["save"] = time.perf_counter() - t0
    timing_r1["total"] = sum(
        value for key, value in timing_r1.items() if key != "total")
    reader_meta["R1"] = {"status": "success"}

    if r2_valid and timing_r2 is not None:
        t0 = time.perf_counter()
        cropped2 = crop_bbox(resampled2, box, int(cfg["crop_padding"]))
        cropped_mask2 = crop_bbox(
            resampled_mask2, box, int(cfg["crop_padding"]))
        timing_r2["crop"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        if requested == "muscle":
            normalized2 = sitk.Cast(
                cropped2 / float(muscle2["mean"]), sitk.sitkFloat32)
            metrics["R2"] = metric_row(
                "muscle", "success", "muscle", muscle_label, muscle2)
        else:
            normalized2, mean2, sd2 = zscore_roi(
                cropped2, sitk.GetArrayFromImage(cropped_mask2) == 1)
            if not np.isfinite(sd2) or sd2 <= 1e-12:
                r2_valid = False
                r2_failure = "R2_ZSCORE_SD_INVALID"
                warn(r2_failure, "R2肿瘤ROI标准差无效，跳过R2", "ERROR")
                remove_outputs(r2_files)
                metrics["R2"] = metric_row(
                    "zscore", "failed", label="1",
                    failure_code=r2_failure,
                    reference_mean=mean2, reference_sd=sd2)
                reader_meta["R2"] = {
                    "status": "failed", "failure_code": r2_failure}
            else:
                metrics["R2"] = metric_row(
                    "zscore", "success", "zscore", "1",
                    reference_mean=mean2, reference_sd=sd2)
        timing_r2["normalize"] = time.perf_counter() - t0
        if r2_valid:
            cropped_mask2.CopyInformation(normalized2)
            t0 = time.perf_counter()
            atomic_write_image(normalized2, r2_files[0])
            atomic_write_image(cropped_mask2, r2_files[1])
            timing_r2["save"] = time.perf_counter() - t0
            timing_r2["total"] = sum(
                value for key, value in timing_r2.items()
                if key != "total")
            reader_meta["R2"] = {"status": "success"}

    metadata = build_metadata(
        cfg, requested, input_meta, reader_meta)
    atomic_write_json(metadata_path, metadata)
    atomic_write_text(
        stamp_path, pipeline_stamp(cfg), encoding="ascii")
    status = "done" if not r2_failure else "done_r2_failed"
    return status, timing_r1, timing_r2, metrics


def resolve_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return path
    return path if os.path.isabs(path) else os.path.join(ROOT, path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="严格预处理流水线")
    parser.add_argument(
        "--manifest", default=os.path.join(OUT, "manifest.csv"))
    parser.add_argument("--ids", help="逗号分隔的影像号")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--normalize", choices=["muscle", "zscore"])
    parser.add_argument(
        "--prep-dir", default=None,
        help="预处理输出目录；缺省按 normalization 选择 output/preprocessed 或 output/preprocessed_zscore")
    parser.add_argument("--n4", action="store_true")
    parser.add_argument("--n4-factor", type=float)
    parser.add_argument("--metrics-csv")
    parser.add_argument("--timing-csv")
    parser.add_argument("--qc-report")
    args = parser.parse_args()

    cfg = load_config()
    if args.normalize:
        cfg["normalization"] = args.normalize
    if args.n4:
        cfg["n4_enabled"] = True
    if args.n4_factor is not None:
        cfg["n4_downsample_factor"] = args.n4_factor

    global PREP_DIR, METRICS_CSV, TIMING_CSV, QC_REPORT
    default_prep_dir = (
        "output/preprocessed_zscore"
        if cfg["normalization"] == "zscore" else "output/preprocessed")
    PREP_DIR = resolve_path(args.prep_dir or default_prep_dir)
    if args.metrics_csv:
        METRICS_CSV = resolve_path(args.metrics_csv)
    if args.timing_csv:
        TIMING_CSV = resolve_path(args.timing_csv)
    if args.qc_report:
        QC_REPORT = resolve_path(args.qc_report)
    os.makedirs(PREP_DIR, exist_ok=True)
    os.makedirs(QC_LOG, exist_ok=True)
    if os.path.exists(CONFIG):
        os.makedirs(os.path.join(OUT, "configs"), exist_ok=True)
        shutil.copy2(
            CONFIG, os.path.join(
                OUT, "configs", "radiomics_params.yaml"))

    frame = pd.read_csv(
        args.manifest, encoding="utf-8-sig", dtype=str)
    if args.ids:
        selected = [
            value.strip() for value in args.ids.split(",")
            if value.strip()]
        frame = frame[frame["影像号"].isin(selected)]
    frame = frame[frame["排除"] != "1"]
    processed_ids = list(frame["影像号"])
    timing_rows, metric_rows, qc, statuses = [], [], {}, {}
    updated_ids = []

    for _, row in frame.iterrows():
        pid = row["影像号"]
        try:
            status, timing1, timing2, metrics = process(
                pid, row, cfg, qc, args.force)
        except Exception as exc:
            status = "error"
            timing1, timing2 = {}, None
            metrics = {
                "R1": metric_row(
                    str(cfg["normalization"]), "failed",
                    failure_code="EXCEPTION")}
            qc[pid] = [{
                "影像号": pid, "阶段": "preprocess",
                "级别": "ERROR", "代码": "EXCEPTION",
                "说明": "{0}: {1}".format(
                    type(exc).__name__, exc),
            }]
            outdir = os.path.join(PREP_DIR, pid)
            remove_outputs([
                os.path.join(outdir, name)
                for name in (
                    "R1_image.nrrd", "R1_mask.nrrd", "R2_image.nrrd",
                    "R2_mask.nrrd", ".pipeline_stamp", "pipeline_metadata.json")
            ])
        statuses[status] = statuses.get(status, 0) + 1
        if status != "skipped":
            updated_ids.append(pid)
        for reader, timing in (("R1", timing1), ("R2", timing2)):
            if timing and timing.get("total"):
                timing_rows.append({
                    "影像号": pid,
                    "读者": reader,
                    "normalization_requested": cfg["normalization"],
                    "n4_enabled": str(bool(cfg["n4_enabled"])),
                    **{key: round(value, 3)
                       for key, value in timing.items()},
                })
        for reader, values in metrics.items():
            metric_rows.append({
                "影像号": pid, "读者": reader, **values})

    save_qc(qc, updated_ids)
    if metric_rows:
        merged_metrics = merge_rows(
            read_csv_or_empty(METRICS_CSV),
            pd.DataFrame(metric_rows),
            ["影像号", "读者", "normalization_requested"])
        atomic_write_csv(
            merged_metrics, METRICS_CSV, METRICS_COLS)
    if timing_rows:
        current = pd.DataFrame(timing_rows)
        merged_timing = merge_rows(
            read_csv_or_empty(TIMING_CSV), current,
            ["影像号", "读者", "normalization_requested",
             "n4_enabled"])
        atomic_write_csv(
            merged_timing, TIMING_CSV, TIMING_COLS)
        for reader in ("R1", "R2"):
            subset = current[current["读者"] == reader]
            if len(subset):
                print(
                    "[{0}] n={1} mean={2:.1f}s "
                    "median={3:.1f}s max={4:.1f}s".format(
                        reader, len(subset),
                        subset["total"].mean(),
                        subset["total"].median(),
                        subset["total"].max()))
        r1 = current[current["读者"] == "R1"]
        r2 = current[current["读者"] == "R2"]
        if len(r1):
            n_r2 = int((frame["是否双读者"] == "1").sum())
            estimate = r1["total"].mean() * len(frame)
            if len(r2):
                estimate += r2["total"].mean() * n_r2
            print(
                "当前队列预估约 {0:.1f} 分钟（{1:.2f} 小时）".format(
                    estimate / 60.0, estimate / 3600.0))
    print("状态统计:", statuses)


if __name__ == "__main__":
    main()
