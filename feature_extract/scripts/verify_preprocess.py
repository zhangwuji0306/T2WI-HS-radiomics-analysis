"""显式验证预处理输出是否符合指定的 normalization pipeline。"""
from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import SimpleITK as sitk

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = [1.0, 1.0, 2.0]
EPS = 1e-6
METRICS = os.path.join(ROOT, "output", "qc", "logs", "preprocess_metrics.csv")


def geom(img: sitk.Image) -> dict:
    return {"size": list(img.GetSize()), "spacing": list(img.GetSpacing()),
            "origin": list(img.GetOrigin()), "direction": list(img.GetDirection())}


def geometry_matches(left: sitk.Image, right: sitk.Image, tol: float = EPS) -> bool:
    a, b = geom(left), geom(right)
    if a["size"] != b["size"]:
        return False
    values_a = a["spacing"] + a["origin"] + a["direction"]
    values_b = b["spacing"] + b["origin"] + b["direction"]
    return all(abs(x - y) <= tol for x, y in zip(values_a, values_b))


def _metric_value(metric: Optional[pd.Series], key: str) -> str:
    if metric is None or key not in metric.index or pd.isna(metric[key]):
        return ""
    return str(metric[key]).strip()


def _finite_float(metric: Optional[pd.Series], key: str) -> bool:
    value = _metric_value(metric, key)
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def latest_metric(metrics: pd.DataFrame, pid: str, reader: str,
                  expected: str) -> Optional[pd.Series]:
    required = {"影像号", "读者", "normalization_requested"}
    if metrics.empty or not required.issubset(metrics.columns):
        return None
    rows = metrics.loc[
        (metrics["影像号"].astype(str) == str(pid))
        & (metrics["读者"].astype(str) == reader)
        & (metrics["normalization_requested"].astype(str) == expected)]
    return rows.iloc[-1] if len(rows) else None


def validate_metric(metric: Optional[pd.Series], expected: str) -> List[str]:
    if metric is None:
        return ["normalization metrics 缺失"]
    failures = []
    if _metric_value(metric, "normalization_applied") != expected:
        failures.append("normalization_applied 不匹配")
    if _metric_value(metric, "normalization_status") != "success":
        failures.append("normalization_status 不是 success")
    if expected == "muscle":
        if _metric_value(metric, "reference_label") != "3":
            failures.append("muscle reference_label 不是 3")
        if not _finite_float(metric, "reference_mean"):
            failures.append("reference_mean 非有限数")
        else:
            if float(_metric_value(metric, "reference_mean")) <= 0:
                failures.append("reference_mean 不大于 0")
        if "fallback" in metric.index and _metric_value(metric, "fallback").lower() in {
                "true", "1", "yes"}:
            failures.append("存在 fallback 标记")
    else:
        if _metric_value(metric, "reference_label") != "1":
            failures.append("z-score reference_label 不是 1")
        if not _finite_float(metric, "reference_mean"):
            failures.append("z-score reference_mean 非有限数")
        if not _finite_float(metric, "reference_sd"):
            failures.append("z-score reference_sd 非有限数")
        elif float(_metric_value(metric, "reference_sd")) <= 1e-12:
            failures.append("z-score reference_sd 无效")
    return failures


def validate_case(prep: str, pid: str, reader: str, expected: str,
                  metrics: pd.DataFrame) -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    notes: List[str] = []
    directory = os.path.join(prep, pid)
    image_path = os.path.join(directory, reader + "_image.nrrd")
    mask_path = os.path.join(directory, reader + "_mask.nrrd")
    if not os.path.exists(image_path) or not os.path.exists(mask_path):
        return ["图像或掩膜文件缺失"], notes
    try:
        image = sitk.ReadImage(image_path)
        mask = sitk.ReadImage(mask_path)
    except Exception as exc:
        return ["读取失败: {0}: {1}".format(type(exc).__name__, exc)], notes
    if not all(abs(a - b) <= EPS for a, b in zip(image.GetSpacing(), TARGET)):
        failures.append("spacing 不符合目标间距")
    if not geometry_matches(image, mask):
        failures.append("图像与掩膜几何不一致")
    if image.GetPixelID() != sitk.sitkFloat32:
        failures.append("图像不是 float32")
    mask_array = sitk.GetArrayFromImage(mask)
    tumor = mask_array == 1
    n_tumor = int(tumor.sum())
    if n_tumor == 0:
        failures.append("肿瘤 ROI 为空")
    metric = latest_metric(metrics, pid, reader, expected)
    failures.extend(validate_metric(metric, expected))
    image_array = sitk.GetArrayFromImage(image).astype(np.float64)
    if n_tumor and expected == "zscore":
        mean, sd = float(image_array[tumor].mean()), float(image_array[tumor].std())
        if abs(mean) >= 1e-3 or abs(sd - 1.0) >= 1e-2:
            failures.append("z-score 肿瘤 ROI 均值/标准差不符合要求")
        notes.append("肿瘤 ROI 均值={0:.4f} 标准差={1:.4f}".format(mean, sd))
    elif n_tumor:
        mean, sd = float(image_array[tumor].mean()), float(image_array[tumor].std())
        notes.append("muscle 模式肿瘤 ROI 均值={0:.4f} 标准差={1:.4f}".format(mean, sd))
    return failures, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="显式验证预处理输出")
    parser.add_argument("--ids", required=True, help="逗号分隔的影像号")
    parser.add_argument("--expected-normalization", required=True,
                        choices=["muscle", "zscore"],
                        help="本次输出必须符合的 normalization")
    parser.add_argument("--prep-dir", default=None,
                        help="预处理目录；缺省按 normalization 选择")
    parser.add_argument("--metrics-csv", default=METRICS,
                        help="preprocess_metrics.csv 路径")
    args = parser.parse_args()
    ids = [value.strip() for value in args.ids.split(",") if value.strip()]
    default_prep = ("output/preprocessed_zscore"
                    if args.expected_normalization == "zscore"
                    else "output/preprocessed")
    prep = args.prep_dir or default_prep
    if not os.path.isabs(prep):
        prep = os.path.join(ROOT, prep)
    metrics_path = args.metrics_csv
    if not os.path.isabs(metrics_path):
        metrics_path = os.path.join(ROOT, metrics_path)
    try:
        metrics = pd.read_csv(metrics_path, dtype=str)
    except (OSError, pd.errors.EmptyDataError, FileNotFoundError):
        metrics = pd.DataFrame()

    failures: List[str] = []
    for pid in ids:
        lines = ["== {0} ==".format(pid)]
        r1_fail, r1_notes = validate_case(
            prep, pid, "R1", args.expected_normalization, metrics)
        lines.append("R1: " + ("通过" if not r1_fail else "失败: " + "; ".join(r1_fail)))
        lines.extend("    " + note for note in r1_notes)
        if r1_fail:
            failures.append(pid + " R1")

        r2_image = os.path.join(prep, pid, "R2_image.nrrd")
        r2_mask = os.path.join(prep, pid, "R2_mask.nrrd")
        if os.path.exists(r2_image) or os.path.exists(r2_mask):
            r2_fail, r2_notes = validate_case(
                prep, pid, "R2", args.expected_normalization, metrics)
            lines.append("R2: " + ("通过" if not r2_fail else "失败: " + "; ".join(r2_fail)))
            lines.extend("    " + note for note in r2_notes)
            if r2_fail:
                failures.append(pid + " R2")
        else:
            lines.append("R2: 未生成（可能因 R2 QC 失败而跳过）")
        print("\n".join(lines))
    print("\n" + ("全部通过" if not failures else "失败项: " + ", ".join(failures)))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
