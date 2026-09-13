"""A-only, outcome-blind habitat technical pilot.

The default entry point reproduces the prespecified global-centre pilot.  The
``--amended`` entry point evaluates the patient-relative K=2 strategy and its
technical sensitivity arms.  Neither entry point reads outcome columns or
creates B-set predictions; the amended report records the quantitative gate
result after all technical metrics are written.  Both modes use the existing
muscle-normalized [1,1,2] mm images for the main arm and reconstruct the
[2,2,2] mm and N4 arms from raw image/label files when needed.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from typing import Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import SimpleITK as sitk
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import ndimage
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAB_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = os.path.dirname(HAB_ROOT)
FEATURE_ROOT = os.path.join(PROJECT_ROOT, "feature_extract")
PREP_ROOT = os.path.join(FEATURE_ROOT, "output", "preprocessed")
MANIFEST = os.path.join(FEATURE_ROOT, "output", "manifest.csv")
SCANNER_MAP = os.path.join(FEATURE_ROOT, "output", "scanner_map.csv")
MODEL_A = os.path.join(PROJECT_ROOT, "prognosis_analysis", "output", "modeling_v2", "dataset_primary_raw_A.csv")
CONFIG = os.path.join(HAB_ROOT, "configs", "technical_pilot.json")
AMENDED_CONFIG = os.path.join(HAB_ROOT, "configs", "technical_pilot_amended.json")
OUT_ROOT = os.path.join(HAB_ROOT, "output")
PILOT_ROOT = os.path.join(OUT_ROOT, "technical_pilot")
MAP_ROOT = os.path.join(OUT_ROOT, "habitat_maps")
QC_ROOT = os.path.join(OUT_ROOT, "qc")
LOG_ROOT = os.path.join(OUT_ROOT, "logs")

# The amended, patient-relative technical gate is written to a separate
# output namespace so that the prespecified global-centre pilot remains an
# auditable baseline.  The ``--amended`` entry point switches these globals
# before any output is created.
AMENDED_PILOT_ROOT = os.path.join(OUT_ROOT, "technical_pilot_amended")
AMENDED_MAP_ROOT = os.path.join(OUT_ROOT, "habitat_maps_amended")
AMENDED_QC_ROOT = os.path.join(OUT_ROOT, "qc_amended")
AMENDED_LOG_ROOT = os.path.join(OUT_ROOT, "logs_amended")
ASCII_PROJECT_ROOT = os.path.join(os.path.dirname(PROJECT_ROOT), "radiomics26")


def ascii_path(path: str) -> str:
    """Route SimpleITK file I/O through the ASCII junction on Windows."""
    absolute = os.path.abspath(str(path))
    root = os.path.abspath(PROJECT_ROOT)
    if absolute.lower().startswith((root + os.sep).lower()):
        return os.path.join(ASCII_PROJECT_ROOT, absolute[len(root) + 1:])
    return absolute

sys.path.insert(0, os.path.join(FEATURE_ROOT, "scripts"))
import preprocess as prep  # noqa: E402


def ensure_dirs() -> None:
    for path in (PILOT_ROOT, MAP_ROOT, QC_ROOT, LOG_ROOT):
        os.makedirs(path, exist_ok=True)


def read_json(path: str) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def normalize_seq(value: str) -> str:
    value = str(value or "").strip().lower()
    value = re.sub(r"[_\-\s]+", "", value)
    return value


def raw_nrrd_pair(folder: str) -> Tuple[str, str]:
    files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".nrrd"))
    labels = [f for f in files if "label" in f.lower()]
    images = [f for f in files if "label" not in f.lower()]
    if len(images) != 1 or len(labels) != 1:
        raise RuntimeError("expected one image and one label in %s" % folder)
    return os.path.join(folder, images[0]), os.path.join(folder, labels[0])


def load_pairs() -> pd.DataFrame:
    manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    scanner = pd.read_csv(SCANNER_MAP, encoding="utf-8-sig", dtype=str)
    # Only the cohort identifier is read from the modeling table.  Survival
    # endpoints and all other clinical columns are deliberately excluded from
    # the technical pilot input.
    a = pd.read_csv(MODEL_A, encoding="utf-8-sig", dtype=str,
                    usecols=["影像号"])
    aids = set(a["影像号"].astype(str).str.strip())
    scanner = scanner.set_index(scanner["影像号"].astype(str).str.strip())
    rows = []
    for _, row in manifest.iterrows():
        pid = str(row["影像号"]).strip()
        if pid not in aids or str(row.get("排除", "0")) == "1":
            continue
        if str(row.get("是否双读者", "0")) != "1":
            continue
        if not str(row.get("R2图像文件", "")).strip():
            continue
        srow = scanner.loc[pid] if pid in scanner.index else None
        seq1 = str(srow.get("R1系列", "")) if srow is not None else ""
        seq2 = str(srow.get("R2系列", "")) if srow is not None else ""
        same = bool(seq1 and seq2 and normalize_seq(seq1) == normalize_seq(seq2))
        # Re-check that the current R1/R2 folders each contain one image and
        # one label.  This catches stale records after a corrected sequence.
        try:
            r1_img, r1_lbl = raw_nrrd_pair(os.path.join(FEATURE_ROOT, "result", pid))
            r2_img, r2_lbl = raw_nrrd_pair(os.path.join(FEATURE_ROOT, "reader_2_result", pid))
        except Exception as exc:
            rows.append({"影像号": pid, "入选技术试点": 0, "序列一致": int(same),
                         "排除原因": "当前原始文件解析失败: %s" % exc})
            continue
        rows.append({"影像号": pid, "入选技术试点": int(same), "序列一致": int(same),
                     "R1序列": seq1, "R2序列": seq2,
                     "R1原始图像": r1_img, "R1原始掩膜": r1_lbl,
                     "R2原始图像": r2_img, "R2原始掩膜": r2_lbl,
                     "预处理目录": os.path.join(PREP_ROOT, pid),
                     "排除原因": "" if same else "R1/R2序列不一致"})
    selection = pd.DataFrame(rows).sort_values("影像号")
    selection.to_csv(os.path.join(PILOT_ROOT, "case_selection_all_A.csv"), index=False, encoding="utf-8-sig")
    selected = selection[selection["入选技术试点"] == 1].copy()
    selected.to_csv(os.path.join(PILOT_ROOT, "case_selection.csv"), index=False, encoding="utf-8-sig")
    return selected


def image_array(image: sitk.Image) -> np.ndarray:
    return sitk.GetArrayFromImage(image).astype(np.float32, copy=False)


def muscle_or_zscore(image: sitk.Image, labels: np.ndarray, label: int,
                     erosion: List[int]) -> sitk.Image:
    stats = prep.muscle_stats(image, labels, label, erosion)
    if stats:
        return sitk.Cast(image / float(stats["mean"]), sitk.sitkFloat32)
    arr = image_array(image)
    roi = arr[labels == 1]
    mu = float(roi.mean()) if roi.size else 0.0
    sd = float(roi.std()) if roi.size else 0.0
    if sd > 1e-12:
        arr = (arr - mu) / sd
    out = sitk.GetImageFromArray(arr)
    out.CopyInformation(image)
    return out


def raw_prepare_pair(row: pd.Series, spacing: List[float], n4: bool,
                     n4_factor: float) -> Dict[str, Tuple[sitk.Image, sitk.Image]]:
    i1 = sitk.ReadImage(ascii_path(str(row["R1原始图像"])))
    m1 = sitk.ReadImage(ascii_path(str(row["R1原始掩膜"])))
    a1 = sitk.GetArrayFromImage(m1)
    i2 = sitk.ReadImage(ascii_path(str(row["R2原始图像"])))
    m2 = sitk.ReadImage(ascii_path(str(row["R2原始掩膜"])))
    a2 = sitk.GetArrayFromImage(m2)
    corr1 = prep.n4_correct(i1, prep.foreground_mask(i1), factor=n4_factor) if n4 else sitk.Cast(i1, sitk.sitkFloat32)
    corr2 = prep.n4_correct(i2, prep.foreground_mask(i2), factor=n4_factor) if n4 else sitk.Cast(i2, sitk.sitkFloat32)
    # Compute the muscle reference on the corrected raw image, before any
    # resampling or cropping, matching the locked primary preprocessing order.
    ref1 = prep.muscle_stats(corr1, a1, 3, [1, 1, 0])
    r2_label_text = str(row.get("R2肌肉标签", "3"))
    r2_label = int(r2_label_text) if r2_label_text in ("2", "3") else 3
    ref2 = prep.muscle_stats(corr2, a2, r2_label, [2, 2, 0])
    n1 = prep.resample_to(corr1, spacing=spacing, interp=sitk.sitkBSpline)
    nm1 = prep.resample_to(prep.mask_image(a1, i1, 1), spacing=spacing,
                           interp=sitk.sitkNearestNeighbor, pixel=sitk.sitkUInt8)
    grid = (list(n1.GetSize()), n1.GetOrigin(), list(n1.GetSpacing()), n1.GetDirection())
    n2 = prep.resample_to(corr2, grid=grid, interp=sitk.sitkBSpline)
    nm2 = prep.resample_to(prep.mask_image(a2, i2, 1), grid=grid,
                           interp=sitk.sitkNearestNeighbor, pixel=sitk.sitkUInt8)
    am1 = sitk.GetArrayFromImage(nm1) == 1
    am2 = sitk.GetArrayFromImage(nm2) == 1
    box = am1 | am2
    c1 = prep.crop_bbox(n1, box, 5)
    cm1 = prep.crop_bbox(nm1, box, 5)
    c2 = prep.crop_bbox(n2, box, 5)
    cm2 = prep.crop_bbox(nm2, box, 5)
    if ref1:
        z1 = sitk.Cast(c1 / float(ref1["mean"]), sitk.sitkFloat32)
    else:
        z1 = muscle_or_zscore(c1, sitk.GetArrayFromImage(cm1), 1, [0, 0, 0])
    if ref2:
        z2 = sitk.Cast(c2 / float(ref2["mean"]), sitk.sitkFloat32)
    else:
        z2 = muscle_or_zscore(c2, sitk.GetArrayFromImage(cm2), 1, [0, 0, 0])
    cm1.CopyInformation(z1)
    cm2.CopyInformation(z2)
    return {"R1": (z1, cm1), "R2": (z2, cm2)}


def load_main_pair(row: pd.Series) -> Dict[str, Tuple[sitk.Image, sitk.Image]]:
    out = {}
    for reader in ("R1", "R2"):
        image = sitk.ReadImage(ascii_path(os.path.join(str(row["预处理目录"]), reader + "_image.nrrd")))
        mask = sitk.ReadImage(ascii_path(os.path.join(str(row["预处理目录"]), reader + "_mask.nrrd")))
        out[reader] = (image, mask)
    return out


def perturb_mask(mask: sitk.Image, sign: int, radius: int, axes: List[int]) -> sitk.Image:
    arr = sitk.GetArrayFromImage(mask) == 1
    structure = np.zeros((3, 3, 3), dtype=bool)
    zrad, yrad, xrad = [int(radius * x) for x in axes]
    structure[1 - zrad:2 + zrad, 1 - yrad:2 + yrad, 1 - xrad:2 + xrad] = True
    if sign < 0:
        arr = ndimage.binary_erosion(arr, structure=structure, iterations=1, border_value=0)
    elif sign > 0:
        arr = ndimage.binary_dilation(arr, structure=structure, iterations=1)
    out = sitk.GetImageFromArray(arr.astype(np.uint8))
    out.CopyInformation(mask)
    return out


def supergrid_size(image: sitk.Image, scale_mm: float) -> List[int]:
    size = list(image.GetSize())
    spacing = list(image.GetSpacing())
    return [max(1, int(round(size[i] * spacing[i] / float(scale_mm)))) for i in range(3)]


def slic_labels(image: sitk.Image, mask: sitk.Image, scale_mm: float, cfg: dict) -> Tuple[np.ndarray, np.ndarray]:
    filt = sitk.SLICImageFilter()
    filt.SetSuperGridSize(supergrid_size(image, scale_mm))
    filt.SetMaximumNumberOfIterations(int(cfg["slic_iterations"]))
    filt.SetSpatialProximityWeight(float(cfg["slic_spatial_weight"]))
    filt.SetInitializationPerturbation(False)
    filt.SetEnforceConnectivity(True)
    filt.SetNumberOfWorkUnits(int(cfg["slic_work_units"]))
    labels = sitk.GetArrayFromImage(filt.Execute(sitk.Cast(image, sitk.sitkFloat32)))
    roi = sitk.GetArrayFromImage(mask) == 1
    return labels.astype(np.int32), roi


def supervoxel_values(image: sitk.Image, labels: np.ndarray, roi: np.ndarray,
                      max_count: int, seed: int) -> Tuple[np.ndarray, dict]:
    arr = image_array(image)
    ids = np.unique(labels[roi])
    values = []
    means = {}
    for label_id in ids:
        vals = arr[(labels == label_id) & roi]
        if vals.size == 0:
            continue
        means[int(label_id)] = float(vals.mean())
        values.append(float(vals.mean()))
    values = np.asarray(values, dtype=np.float64)
    if values.size > max_count:
        rng = np.random.RandomState(seed)
        values = rng.choice(values, size=max_count, replace=False)
    return values, means


def cluster_centers(values: Iterable[np.ndarray], k: int, seed: int) -> np.ndarray:
    all_values = np.concatenate([x for x in values if len(x)], axis=0).reshape(-1, 1)
    if all_values.size == 0 or np.unique(all_values).size < k:
        return np.full(k, np.nan, dtype=float)
    model = KMeans(n_clusters=k, init="k-means++", n_init=100,
                   random_state=seed, max_iter=300, tol=1e-4)
    model.fit(all_values)
    return np.sort(model.cluster_centers_.ravel())


def patient_cluster_centers(values: np.ndarray, seed: int) -> Tuple[np.ndarray, bool]:
    """Fit the amended patient-relative K=2 rule on one reader's case."""
    values = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    if values.size < 2 or np.unique(values).size < 2:
        return np.full(2, np.nan, dtype=float), False
    model = KMeans(n_clusters=2, init="k-means++", n_init=100,
                   random_state=seed, max_iter=300, tol=1e-4)
    model.fit(values)
    centers = np.sort(model.cluster_centers_.ravel())
    return centers, bool(np.isfinite(centers).all() and centers[1] > centers[0])


def patient_otsu_threshold(values: np.ndarray) -> Tuple[float, bool]:
    """Return an Otsu threshold for one reader/case's supervoxel means.

    The implementation operates on the exact sorted supervoxel means rather
    than an arbitrary histogram binning, which makes the sensitivity branch
    deterministic in the Python 3.7 environment.
    """
    values = np.asarray(values, dtype=np.float64).ravel()
    values = values[np.isfinite(values)]
    unique = np.unique(values)
    if unique.size < 2:
        return np.nan, False
    counts = np.asarray([(values == v).sum() for v in unique], dtype=np.float64)
    cumulative = np.cumsum(counts)
    weighted = np.cumsum(counts * unique)
    total = float(cumulative[-1])
    total_weighted = float(weighted[-1])
    denom = cumulative * (total - cumulative)
    between = np.full(unique.shape, -np.inf, dtype=np.float64)
    valid = denom > 0
    between[valid] = ((total * weighted[valid] - cumulative[valid] * total_weighted) ** 2) / denom[valid]
    cut = int(np.argmax(between))
    if not np.isfinite(between[cut]) or cut >= unique.size - 1:
        return np.nan, False
    threshold = float((unique[cut] + unique[cut + 1]) / 2.0)
    return threshold, bool(np.isfinite(threshold))


def assign_habitat(labels: np.ndarray, roi: np.ndarray, means: dict,
                   centers: np.ndarray) -> np.ndarray:
    out = np.full(labels.shape, -1, dtype=np.int8)
    for label_id, mean in means.items():
        if np.isfinite(centers).all():
            out[labels == int(label_id)] = int(np.argmin(np.abs(centers - mean)))
    out[~roi] = -1
    return out


def assign_patient_habitat(labels: np.ndarray, roi: np.ndarray, means: dict,
                           method: str, seed: int) -> Tuple[np.ndarray, np.ndarray, bool]:
    """Assign low/high labels independently within one patient and reader."""
    values = np.asarray(list(means.values()), dtype=np.float64)
    centers = np.full(2, np.nan, dtype=float)
    ok = False
    threshold = np.nan
    if method == "patient_k2":
        centers, ok = patient_cluster_centers(values, seed)
    elif method == "patient_otsu":
        threshold, ok = patient_otsu_threshold(values)
        if ok:
            finite = values[np.isfinite(values)]
            centers = np.asarray([float(finite[finite <= threshold].mean()),
                                  float(finite[finite > threshold].mean())], dtype=float)
            ok = bool(np.isfinite(centers).all() and centers[1] > centers[0])
    if not ok:
        return np.full(labels.shape, -1, dtype=np.int8), centers, False
    out = np.full(labels.shape, -1, dtype=np.int8)
    for label_id, mean in means.items():
        if method == "patient_otsu":
            idx = 0 if mean <= threshold else 1
        else:
            idx = int(np.argmin(np.abs(centers - mean)))
        out[labels == int(label_id)] = idx
    out[~roi] = -1
    # A valid method must populate both habitats inside the reader's ROI.
    populated = [int(((out == idx) & roi).sum()) for idx in (0, 1)]
    return out, centers, bool(all(x > 0 for x in populated))


def dice(a: np.ndarray, b: np.ndarray) -> float:
    den = int(a.sum() + b.sum())
    return float(2.0 * (a & b).sum() / den) if den else float("nan")


def connected_stats(habitat: np.ndarray, idx: int, spacing: Tuple[float, float, float]) -> Tuple[int, float, float]:
    binary = habitat == idx
    if not binary.any():
        return 0, 0.0, 0.0
    structure = ndimage.generate_binary_structure(3, 1)
    cc, n = ndimage.label(binary, structure=structure)
    sizes = np.bincount(cc.ravel())[1:]
    vol = float(np.prod(spacing))
    return int(n), float(sizes.max() * vol), float(sizes.max() / sizes.sum())


def habitat_descriptors(image: sitk.Image, habitat: np.ndarray,
                        roi: np.ndarray, idx: int) -> Dict[str, float]:
    """Low-dimensional habitat descriptors used for the ICC gate."""
    arr = image_array(image)
    spacing_zyx = tuple(float(x) for x in image.GetSpacing()[::-1])
    voxel_mm3 = float(np.prod(spacing_zyx))
    tumor_voxels = int(roi.sum())
    tumor_mm3 = tumor_voxels * voxel_mm3
    high = (habitat == idx) & roi
    low = (habitat == 0) & roi if idx != 0 else (habitat == 1) & roi
    ncomp, _, largest_frac = connected_stats(habitat, idx, spacing_zyx)
    # Interface area is counted once per positive x/y/z neighbor pair.
    interface_mm2 = 0.0
    for axis, face_area in ((0, spacing_zyx[1] * spacing_zyx[2]),
                            (1, spacing_zyx[0] * spacing_zyx[2]),
                            (2, spacing_zyx[0] * spacing_zyx[1])):
        a = np.take(habitat, indices=range(habitat.shape[axis] - 1), axis=axis)
        b = np.take(habitat, indices=range(1, habitat.shape[axis]), axis=axis)
        ra = np.take(roi, indices=range(roi.shape[axis] - 1), axis=axis)
        rb = np.take(roi, indices=range(1, roi.shape[axis]), axis=axis)
        interface_mm2 += float(((a != b) & ra & rb).sum()) * face_area
    distance = ndimage.distance_transform_edt(roi, sampling=spacing_zyx)
    max_distance = float(distance[roi].max()) if tumor_voxels else 0.0
    radial = float(distance[high].mean() / max_distance) if high.any() and max_distance > 0 else np.nan
    high_med = float(np.median(arr[high])) if high.any() else np.nan
    low_med = float(np.median(arr[low])) if low.any() else np.nan
    return {
        "H_high_fraction": float(high.sum() / tumor_voxels) if tumor_voxels else np.nan,
        "H_high_largest_component_fraction": largest_frac,
        "H_high_component_density": float(ncomp / (tumor_mm3 / 1000.0)) if tumor_mm3 > 0 else np.nan,
        "habitat_interface_density": float(interface_mm2 / tumor_mm3) if tumor_mm3 > 0 else np.nan,
        "H_high_radial_index": radial,
        "signal_contrast": high_med - low_med if np.isfinite(high_med) and np.isfinite(low_med) else np.nan,
    }


def effective_bins(image: sitk.Image, habitat: np.ndarray, idx: int, bin_width: float) -> int:
    vals = image_array(image)[habitat == idx]
    if vals.size == 0:
        return 0
    return int(np.unique(np.floor(vals / float(bin_width))).size)


def save_map(habitat: np.ndarray, reference: sitk.Image, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out = sitk.GetImageFromArray((habitat + 1).astype(np.int8))
    out.CopyInformation(reference)
    sitk.WriteImage(out, ascii_path(path), useCompression=True)


def save_overlay(habitat: np.ndarray, image: sitk.Image, roi: np.ndarray,
                 path: str) -> None:
    """Save one central/max-area slice as a compact visual QC overlay."""
    areas = roi.reshape(roi.shape[0], -1).sum(axis=1)
    z = int(np.argmax(areas)) if areas.size else int(roi.shape[0] // 2)
    bg = image_array(image)[z]
    sl_roi = roi[z]
    sl_h = habitat[z]
    finite = bg[np.isfinite(bg)]
    lo, hi = np.percentile(finite, [1, 99]) if finite.size else (0.0, 1.0)
    if hi <= lo:
        hi = lo + 1.0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig, ax = plt.subplots(figsize=(4.5, 4.5), dpi=160)
    ax.imshow(bg, cmap="gray", vmin=lo, vmax=hi)
    overlay = np.ma.masked_where(sl_h < 0, sl_h)
    ax.imshow(overlay, cmap="coolwarm", alpha=0.42, vmin=0, vmax=1)
    ax.contour(sl_roi.astype(float), levels=[0.5], colors="lime", linewidths=0.7)
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    fig.savefig(path, bbox_inches="tight", pad_inches=0)
    plt.close(fig)


def metrics_for_pair(pid: str, variant: str, scale: float, k: int,
                     data: Dict[str, Dict[str, object]], centers: np.ndarray,
                     cfg: dict, map_dir: str) -> dict:
    r1 = data["R1"]
    r2 = data["R2"]
    h1 = assign_habitat(r1["labels"], r1["roi"], r1["means"], centers)
    h2 = assign_habitat(r2["labels"], r2["roi"], r2["means"], centers)
    common = r1["roi"] & r2["roi"]
    row = {"影像号": pid, "变体": variant, "尺度mm": scale, "K": k,
           "聚类中心": ";".join("%.8g" % x for x in centers),
           "聚类中心间距": float(np.min(np.diff(centers))) if len(centers) > 1 and np.isfinite(centers).all() else np.nan,
           "ROI_Dice": dice(r1["roi"], r2["roi"]),
           "common_voxels": int(common.sum()),
           "adjusted_rand_index": adjusted_rand_score(h1[common], h2[common]) if common.any() and np.all(h1[common] >= 0) and np.all(h2[common] >= 0) else np.nan,
           "unassigned_R1": int((r1["roi"] & (h1 < 0)).sum()),
           "unassigned_R2": int((r2["roi"] & (h2 < 0)).sum())}
    spacing = tuple(float(x) for x in r1["image"].GetSpacing()[::-1])
    for idx in range(k):
        key = "H-low" if idx == 0 else ("H-high" if idx == k - 1 else "H-mid")
        a = (h1 == idx) & common
        b = (h2 == idx) & common
        row[key + "_Dice"] = dice(a, b)
        row[key + "_fraction_R1"] = float((h1 == idx).sum() / r1["roi"].sum()) if r1["roi"].sum() else np.nan
        row[key + "_fraction_R2"] = float((h2 == idx).sum() / r2["roi"].sum()) if r2["roi"].sum() else np.nan
        for reader, item, hab in (("R1", r1, h1), ("R2", r2, h2)):
            ncomp, largest, largest_frac = connected_stats(hab, idx, spacing)
            prefix = "%s_%s_" % (reader, key)
            row[prefix + "components"] = ncomp
            row[prefix + "largest_component_ml"] = largest / 1000.0
            row[prefix + "largest_component_fraction"] = largest_frac
            row[prefix + "voxels"] = int((hab == idx).sum())
            row[prefix + "volume_ml"] = float((hab == idx).sum() * np.prod(spacing) / 1000.0)
            row[prefix + "effective_bins"] = effective_bins(item["image"], hab, idx, cfg["bin_width"])
            row[prefix + "texture_eligible"] = int(row[prefix + "voxels"] >= 64 and row[prefix + "volume_ml"] >= 0.5 and row[prefix + "effective_bins"] >= 4)
    row["empty_habitat_R1"] = int(any(row["R1_%s_voxels" % key] == 0 for key in
                                          (["H-low", "H-high"] if k == 2 else
                                           ["H-low", "H-mid", "H-high"])))
    row["empty_habitat_R2"] = int(any(row["R2_%s_voxels" % key] == 0 for key in
                                          (["H-low", "H-high"] if k == 2 else
                                           ["H-low", "H-mid", "H-high"])))
    row["empty_or_failed_case"] = int(
        row["empty_habitat_R1"] or row["empty_habitat_R2"] or
        row["unassigned_R1"] > 0 or row["unassigned_R2"] > 0 or
        not np.isfinite(centers).all())
    for reader, item, hab in (("R1", r1, h1), ("R2", r2, h2)):
        desc = habitat_descriptors(item["image"], hab, item["roi"], k - 1)
        for name, value in desc.items():
            row["%s_%s" % (reader, name)] = value
    save_map(h1, r1["image"], os.path.join(map_dir, "%s_%s_%gmm_K%d_R1.nrrd" % (pid, variant, scale, k)))
    save_map(h2, r2["image"], os.path.join(map_dir, "%s_%s_%gmm_K%d_R2.nrrd" % (pid, variant, scale, k)))
    if abs(float(scale) - 6.0) < 1e-6 and int(k) == 2:
        qc_dir = os.path.join(QC_ROOT, "overlays", variant)
        save_overlay(h1, r1["image"], r1["roi"], os.path.join(qc_dir, "%s_R1.png" % pid))
        save_overlay(h2, r2["image"], r2["roi"], os.path.join(qc_dir, "%s_R2.png" % pid))
    return row


def gate_dice(a: np.ndarray, b: np.ndarray) -> float:
    """Dice used by the amended gate; empty/failed habitat is a failure."""
    den = int(a.sum() + b.sum())
    return float(2.0 * (a & b).sum() / den) if den else 0.0


def metrics_for_pair_patient(pid: str, variant: str, scale: float,
                             method: str, data: Dict[str, Dict[str, object]],
                             cfg: dict, map_dir: str, seed: int) -> dict:
    """Metrics for the amended patient-relative K=2/Otsu arms."""
    assigned = {}
    for reader in ("R1", "R2"):
        item = data[reader]
        hab, centers, ok = assign_patient_habitat(
            item["labels"], item["roi"], item["means"], method, seed)
        counts = [int(((hab == idx) & item["roi"]).sum()) for idx in (0, 1)]
        assigned[reader] = {"habitat": hab, "centers": centers,
                            "ok": bool(ok), "counts": counts}
    r1, r2 = data["R1"], data["R2"]
    h1, h2 = assigned["R1"]["habitat"], assigned["R2"]["habitat"]
    common = r1["roi"] & r2["roi"]
    row = {
        "影像号": pid, "变体": variant, "尺度mm": scale,
        "方法": method, "K": 2,
        "R1_聚类中心": ";".join("%.8g" % x for x in assigned["R1"]["centers"]),
        "R2_聚类中心": ";".join("%.8g" % x for x in assigned["R2"]["centers"]),
        "R1_聚类中心间距": float(np.diff(assigned["R1"]["centers"])[0]) if np.isfinite(assigned["R1"]["centers"]).all() else np.nan,
        "R2_聚类中心间距": float(np.diff(assigned["R2"]["centers"])[0]) if np.isfinite(assigned["R2"]["centers"]).all() else np.nan,
        "R1_method_ok": int(assigned["R1"]["ok"]),
        "R2_method_ok": int(assigned["R2"]["ok"]),
        "ROI_Dice": dice(r1["roi"], r2["roi"]),
        "common_voxels": int(common.sum()),
        "adjusted_rand_index": adjusted_rand_score(h1[common], h2[common]) if common.any() and np.all(h1[common] >= 0) and np.all(h2[common] >= 0) else np.nan,
        "unassigned_R1": int((r1["roi"] & (h1 < 0)).sum()),
        "unassigned_R2": int((r2["roi"] & (h2 < 0)).sum()),
        "empty_habitat_R1": int(min(assigned["R1"]["counts"]) == 0),
        "empty_habitat_R2": int(min(assigned["R2"]["counts"]) == 0),
    }
    row["empty_or_failed_case"] = int(
        (not assigned["R1"]["ok"]) or (not assigned["R2"]["ok"]) or
        row["empty_habitat_R1"] or row["empty_habitat_R2"])
    spacing = tuple(float(x) for x in r1["image"].GetSpacing()[::-1])
    for idx, key in ((0, "H-low"), (1, "H-high")):
        a = (h1 == idx) & common
        b = (h2 == idx) & common
        row[key + "_Dice"] = gate_dice(a, b)
        row[key + "_fraction_R1"] = float((h1 == idx).sum() / r1["roi"].sum()) if r1["roi"].sum() else np.nan
        row[key + "_fraction_R2"] = float((h2 == idx).sum() / r2["roi"].sum()) if r2["roi"].sum() else np.nan
        for reader, item, hab in (("R1", r1, h1), ("R2", r2, h2)):
            ncomp, largest, largest_frac = connected_stats(hab, idx, spacing)
            prefix = "%s_%s_" % (reader, key)
            row[prefix + "components"] = ncomp
            row[prefix + "largest_component_ml"] = largest / 1000.0
            row[prefix + "largest_component_fraction"] = largest_frac
            row[prefix + "voxels"] = int((hab == idx).sum())
            row[prefix + "volume_ml"] = float((hab == idx).sum() * np.prod(spacing) / 1000.0)
            row[prefix + "effective_bins"] = effective_bins(item["image"], hab, idx, cfg["bin_width"])
            row[prefix + "texture_eligible"] = int(
                row[prefix + "voxels"] >= 64 and row[prefix + "volume_ml"] >= 0.5 and
                row[prefix + "effective_bins"] >= 4)
    for reader, item, hab in (("R1", r1, h1), ("R2", r2, h2)):
        desc = habitat_descriptors(item["image"], hab, item["roi"], 1)
        for name, value in desc.items():
            row["%s_%s" % (reader, name)] = value
    save_map(h1, r1["image"], os.path.join(map_dir, "%s_%s_%gmm_R1.nrrd" % (pid, variant, scale)))
    save_map(h2, r2["image"], os.path.join(map_dir, "%s_%s_%gmm_R2.nrrd" % (pid, variant, scale)))
    if abs(float(scale) - 6.0) < 1e-6:
        qc_dir = os.path.join(QC_ROOT, "overlays", variant)
        save_overlay(h1, r1["image"], r1["roi"], os.path.join(qc_dir, "%s_R1.png" % pid))
        save_overlay(h2, r2["image"], r2["roi"], os.path.join(qc_dir, "%s_R2.png" % pid))
    return row


def process_variant(selected: pd.DataFrame, variant: str, cfg: dict,
                    scales: List[float], ks: List[int], spacing: List[float],
                    n4: bool) -> List[dict]:
    prepared = {}
    for _, row in selected.iterrows():
        pid = str(row["影像号"])
        if variant == "primary_1x1x2":
            pair = load_main_pair(row)
        else:
            pair = raw_prepare_pair(row, spacing, n4, float(cfg["n4_downsample_factor"]))
        prepared[pid] = pair
    records = []
    for scale in scales:
        per_case = {}
        fit_values = []
        for j, (pid, pair) in enumerate(prepared.items()):
            per_case[pid] = {}
            for reader in ("R1", "R2"):
                image, mask = pair[reader]
                labels, roi = slic_labels(image, mask, scale, cfg)
                vals, means = supervoxel_values(image, labels, roi,
                                                 int(cfg["max_supervoxels_per_case_for_fit"]),
                                                 int(cfg["random_seed"]) + j)
                per_case[pid][reader] = {"image": image, "mask": mask,
                                         "labels": labels, "roi": roi,
                                         "means": means, "fit_values": vals}
                if reader == "R1":
                    fit_values.append(vals)
        for k in ks:
            centers = cluster_centers(fit_values, k, int(cfg["random_seed"]))
            for pid, pair in per_case.items():
                records.append(metrics_for_pair(pid, variant, scale, k, pair,
                                                centers, cfg, os.path.join(MAP_ROOT, variant)))
    return records


def process_patient_variant(selected: pd.DataFrame, variant: str, method: str,
                            cfg: dict, scales: List[float], spacing: List[float],
                            n4: bool) -> List[dict]:
    """Run one patient-relative method for all cases and candidate scales."""
    prepared = {}
    for _, row in selected.iterrows():
        pid = str(row["影像号"])
        pair = load_main_pair(row) if not n4 and spacing == list(cfg["main_spacing_mm"]) else raw_prepare_pair(
            row, spacing, n4, float(cfg["n4_downsample_factor"]))
        prepared[pid] = pair
    records = []
    seed0 = int(cfg["random_seed"])
    for scale in scales:
        per_case = {}
        for j, (pid, pair) in enumerate(prepared.items()):
            per_case[pid] = {}
            for reader in ("R1", "R2"):
                image, mask = pair[reader]
                labels, roi = slic_labels(image, mask, scale, cfg)
                vals, means = supervoxel_values(
                    image, labels, roi,
                    int(cfg["max_supervoxels_per_case_for_fit"]), seed0 + j)
                per_case[pid][reader] = {"image": image, "mask": mask,
                                         "labels": labels, "roi": roi,
                                         "means": means, "fit_values": vals}
        for j, (pid, pair) in enumerate(per_case.items()):
            records.append(metrics_for_pair_patient(
                pid, variant, scale, method, pair, cfg,
                os.path.join(MAP_ROOT, variant), seed0 + j))
    return records


def add_patient_roi_perturbation_variants(selected: pd.DataFrame, cfg: dict,
                                          scales: List[float]) -> List[dict]:
    """Patient-relative K=2 ROI erosion/dilation sensitivity arms."""
    records = []
    seed0 = int(cfg["random_seed"])
    for scale in scales:
        prepared = {}
        for j, (_, row) in enumerate(selected.iterrows()):
            pid = str(row["影像号"])
            pair = load_main_pair(row)
            prepared[pid] = {}
            for reader in ("R1", "R2"):
                image, mask = pair[reader]
                labels, roi = slic_labels(image, mask, scale, cfg)
                prepared[pid][reader] = {"image": image, "mask": mask,
                                         "labels": labels, "roi": roi,
                                         "seed": seed0 + j}
        for sign, name in ((-1, "patient_k2_roi_erode1"),
                           (1, "patient_k2_roi_dilate1")):
            for pid, pair in prepared.items():
                altered = {}
                for reader in ("R1", "R2"):
                    item = pair[reader]
                    mask = perturb_mask(item["mask"], sign,
                                        int(cfg["roi_perturbation_voxels"]),
                                        list(cfg["roi_perturbation_axes"]))
                    roi = sitk.GetArrayFromImage(mask) == 1
                    vals, means = supervoxel_values(
                        item["image"], item["labels"], roi,
                        int(cfg["max_supervoxels_per_case_for_fit"]),
                        int(item["seed"]))
                    altered[reader] = {"image": item["image"], "mask": mask,
                                       "labels": item["labels"], "roi": roi,
                                       "means": means, "fit_values": vals}
                records.append(metrics_for_pair_patient(
                    pid, name, scale, "patient_k2", altered, cfg,
                    os.path.join(MAP_ROOT, name), int(pair["R1"]["seed"])))
    return records


def add_roi_perturbation_variants(selected: pd.DataFrame, cfg: dict,
                                  scales: List[float], ks: List[int]) -> List[dict]:
    records = []
    # Fit centers on the baseline primary arm separately at each SLIC scale.
    # Perturbed masks alter support but never alter intensity calibration or
    # clustering centers.
    for scale in scales:
        prepared = {}
        fit_values = []
        for j, (_, row) in enumerate(selected.iterrows()):
            pid = str(row["影像号"])
            pair = load_main_pair(row)
            prepared[pid] = {}
            for reader in ("R1", "R2"):
                image, mask = pair[reader]
                labels, roi = slic_labels(image, mask, scale, cfg)
                vals, means = supervoxel_values(image, labels, roi,
                                                 int(cfg["max_supervoxels_per_case_for_fit"]),
                                                 int(cfg["random_seed"]) + j)
                prepared[pid][reader] = {"image": image, "mask": mask,
                                         "labels": labels, "means": means,
                                         "fit_values": vals}
                if reader == "R1":
                    fit_values.append(vals)
        baseline_centers = {k: cluster_centers(fit_values, k, int(cfg["random_seed"])) for k in ks}
        for sign, name in ((-1, "roi_erode1"), (1, "roi_dilate1")):
            for k in ks:
                centers = baseline_centers[k]
                for pid, pair in prepared.items():
                    altered = {}
                    for reader in ("R1", "R2"):
                        item = pair[reader]
                        mask = perturb_mask(item["mask"], sign,
                                            int(cfg["roi_perturbation_voxels"]),
                                            list(cfg["roi_perturbation_axes"]))
                        labels = item["labels"]
                        roi = sitk.GetArrayFromImage(mask) == 1
                        vals, means = supervoxel_values(item["image"], labels, roi,
                                                         int(cfg["max_supervoxels_per_case_for_fit"]),
                                                         int(cfg["random_seed"]))
                        altered[reader] = {"image": item["image"], "mask": mask,
                                           "labels": labels, "roi": roi,
                                           "means": means, "fit_values": vals}
                    records.append(metrics_for_pair(pid, name, scale, k, altered,
                                                    centers, cfg, os.path.join(MAP_ROOT, name)))
    return records


def summarize(records: pd.DataFrame) -> pd.DataFrame:
    value_cols = [c for c in records.columns if c.endswith("_Dice") or c in ("ROI_Dice", "adjusted_rand_index")]
    rows = []
    for keys, group in records.groupby(["变体", "尺度mm", "K"], dropna=False):
        row = {"变体": keys[0], "尺度mm": keys[1], "K": keys[2], "n": len(group)}
        for col in value_cols:
            x = pd.to_numeric(group[col], errors="coerce").dropna()
            row[col + "_median"] = float(x.median()) if len(x) else np.nan
            row[col + "_q1"] = float(x.quantile(0.25)) if len(x) else np.nan
            row[col + "_q3"] = float(x.quantile(0.75)) if len(x) else np.nan
            row[col + "_n"] = int(len(x))
        fail_cols = [c for c in group.columns if c.endswith("_texture_eligible")]
        eligible = group[fail_cols].apply(pd.to_numeric, errors="coerce") if fail_cols else pd.DataFrame()
        row["texture_ineligible_case_rate"] = float((eligible.min(axis=1) < 1).mean()) if not eligible.empty else np.nan
        if "empty_or_failed_case" in group.columns:
            failure = pd.to_numeric(group["empty_or_failed_case"], errors="coerce").fillna(1) > 0
        else:
            habitat_voxel_cols = [c for c in group.columns
                                  if c.startswith(("R1_H-", "R2_H-")) and c.endswith("_voxels")]
            empty = (group[habitat_voxel_cols].apply(pd.to_numeric, errors="coerce") == 0).any(axis=1)
            failure = (empty |
                       (pd.to_numeric(group["unassigned_R1"], errors="coerce") > 0) |
                       (pd.to_numeric(group["unassigned_R2"], errors="coerce") > 0))
        row["empty_or_failed_case_rate"] = float(failure.mean())
        row["empty_or_unassigned_rate"] = row["empty_or_failed_case_rate"]
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["变体", "尺度mm", "K"])


def summarize_patient(records: pd.DataFrame) -> pd.DataFrame:
    """Summary with the amended gate's all-case failure accounting."""
    value_cols = [c for c in records.columns
                  if c.endswith("_Dice") or c in ("ROI_Dice", "adjusted_rand_index")]
    rows = []
    for keys, group in records.groupby(["变体", "尺度mm", "方法"], dropna=False):
        row = {"变体": keys[0], "尺度mm": keys[1], "方法": keys[2],
               "K": 2, "n": len(group)}
        for col in value_cols:
            x = pd.to_numeric(group[col], errors="coerce").dropna()
            row[col + "_median"] = float(x.median()) if len(x) else np.nan
            row[col + "_q1"] = float(x.quantile(0.25)) if len(x) else np.nan
            row[col + "_q3"] = float(x.quantile(0.75)) if len(x) else np.nan
            row[col + "_n"] = int(len(x))
        eligible_cols = [c for c in group.columns if c.endswith("_texture_eligible")]
        eligible = group[eligible_cols].apply(pd.to_numeric, errors="coerce") if eligible_cols else pd.DataFrame()
        r1_eligible = group[["R1_H-low_texture_eligible", "R1_H-high_texture_eligible"]].apply(pd.to_numeric, errors="coerce")
        r2_eligible = group[["R2_H-low_texture_eligible", "R2_H-high_texture_eligible"]].apply(pd.to_numeric, errors="coerce")
        row["R1_both_habitats_texture_eligible_rate"] = float(r1_eligible.min(axis=1).mean())
        row["R2_both_habitats_texture_eligible_rate"] = float(r2_eligible.min(axis=1).mean())
        row["pair_both_habitats_texture_eligible_rate"] = float(
            (r1_eligible.min(axis=1) * r2_eligible.min(axis=1)).mean())
        row["texture_ineligible_case_rate"] = float((eligible.min(axis=1) < 1).mean()) if not eligible.empty else np.nan
        row["empty_or_failed_case_rate"] = float(pd.to_numeric(group["empty_or_failed_case"], errors="coerce").mean())
        row["unassigned_case_rate"] = float(((pd.to_numeric(group["unassigned_R1"], errors="coerce") > 0) |
                                               (pd.to_numeric(group["unassigned_R2"], errors="coerce") > 0)).mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["变体", "尺度mm", "方法"])


def icc_2_1(x: np.ndarray, y: np.ndarray) -> float:
    """Two-way random, single-measure ICC(2,1) for two readers."""
    data = np.column_stack([x, y]).astype(float)
    data = data[np.isfinite(data).all(axis=1)]
    n, k = data.shape if data.ndim == 2 else (0, 0)
    if n < 2 or k != 2:
        return np.nan
    grand = data.mean()
    row_means = data.mean(axis=1)
    col_means = data.mean(axis=0)
    ms_subject = k * np.sum((row_means - grand) ** 2) / (n - 1)
    ms_rater = n * np.sum((col_means - grand) ** 2) / (k - 1)
    residual = data - row_means[:, None] - col_means[None, :] + grand
    ms_error = np.sum(residual ** 2) / ((n - 1) * (k - 1))
    denom = ms_subject + (k - 1) * ms_error + k * (ms_rater - ms_error) / n
    return float((ms_subject - ms_error) / denom) if abs(denom) > 1e-12 else np.nan


def write_descriptor_icc(records: pd.DataFrame) -> None:
    descriptors = ["H_high_fraction", "H_high_largest_component_fraction",
                   "H_high_component_density", "habitat_interface_density",
                   "H_high_radial_index", "signal_contrast"]
    rows = []
    group_cols = ["变体", "尺度mm", "K"]
    if "方法" in records.columns:
        group_cols.insert(2, "方法")
    for keys, group in records.groupby(group_cols, dropna=False):
        for desc in descriptors:
            c1, c2 = "R1_" + desc, "R2_" + desc
            if c1 not in group.columns or c2 not in group.columns:
                continue
            x = pd.to_numeric(group[c1], errors="coerce").to_numpy()
            y = pd.to_numeric(group[c2], errors="coerce").to_numpy()
            valid = np.isfinite(x) & np.isfinite(y)
            row = {"变体": keys[0], "尺度mm": keys[1], "K": keys[-1],
                   "descriptor": desc, "n": int(valid.sum()),
                   "ICC_2_1": icc_2_1(x, y)}
            if "方法" in records.columns:
                row["方法"] = keys[2]
            rows.append(row)
    pd.DataFrame(rows).to_csv(os.path.join(PILOT_ROOT, "descriptor_icc.csv"),
                              index=False, encoding="utf-8-sig")


def write_device_composition(selected: pd.DataFrame) -> None:
    scanner = pd.read_csv(SCANNER_MAP, encoding="utf-8-sig", dtype=str)
    ids = set(selected["影像号"].astype(str))
    cols = ["影像号", "R1厂商", "R1机型", "R1场强", "R1系列", "R2系列"]
    out = scanner[scanner["影像号"].astype(str).isin(ids)][cols].copy()
    out.to_csv(os.path.join(PILOT_ROOT, "device_composition.csv"), index=False,
               encoding="utf-8-sig")


def write_amended_report(selected: pd.DataFrame, records: pd.DataFrame,
                         summary: pd.DataFrame, elapsed: float,
                         manual_qc_status: str = "not_evaluated") -> None:
    """Write a self-contained outcome-blind amended-pilot report."""
    primary = summary[summary["变体"] == "patient_k2_1x1x2"].copy()
    icc = pd.read_csv(os.path.join(PILOT_ROOT, "descriptor_icc.csv"),
                      encoding="utf-8-sig")
    lines = [
        "# 患者内相对生境技术试点报告",
        "",
        "> 本报告仅使用A集同序列R1/R2的技术重复性数据，不读取生存结局，不生成B集结果。",
        "",
        "## 执行摘要",
        "",
        "- A集同序列双读者病例：%d例；指标行：%d；运行时间：%.1f秒。" % (len(selected), len(records), elapsed),
        "- 主方法：肌肉均值归一化、[1,1,2] mm、三维SLIC、患者内K=2；按患者内聚类中心低/高标记H-low/H-high。",
        "- 敏感性：患者内Otsu、[2,2,2] mm、N4、ROI侵蚀/膨胀。",
        "- 空生境、方法失败和无法分配均按技术失败计入，不从Dice中删除。",
        "",
        "## 主方法门槛指标",
        "",
        "|尺度|H-low Dice中位数|H-high Dice中位数|空/失败比例|H-high分数ICC(2,1)|自动核心判定|",
        "|---:|---:|---:|---:|---:|:---|",
    ]
    for _, row in primary.sort_values("尺度mm").iterrows():
        s = float(row["尺度mm"])
        icc_row = icc[(icc["变体"] == "patient_k2_1x1x2") &
                      (icc["尺度mm"] == s) & (icc["方法"] == "patient_k2") &
                      (icc["descriptor"] == "H_high_fraction")]
        hficc = float(icc_row["ICC_2_1"].iloc[0]) if not icc_row.empty else np.nan
        ok = (float(row["H-low_Dice_median"]) >= 0.70 and
              float(row["H-high_Dice_median"]) >= 0.70 and
              float(row["empty_or_failed_case_rate"]) < 0.10 and
              np.isfinite(hficc) and hficc >= 0.75)
        lines.append("| %.0f mm | %.3f | %.3f | %.1f%% | %.3f | %s |" % (
            s, float(row["H-low_Dice_median"]), float(row["H-high_Dice_median"]),
            100.0 * float(row["empty_or_failed_case_rate"]), hficc,
            "通过" if ok else "不通过"))
    lines += [
        "",
        "## 描述符与纹理可计算性",
        "",
        "- 描述符准入规则：ICC(2,1)≥0.75且有效配对≥20/22；具体结果见 `descriptor_icc.csv`。",
        "- 低维描述符和生境内纹理可计算比例见 `summary.csv`；高维分支只有在A集R1两类生境均满足纹理要求的比例≥90%时才可进入后续模型。",
        "",
        "## 敏感性分支",
        "",
        "|变体|尺度|H-low Dice中位数|H-high Dice中位数|空/失败比例|",
        "|:---|---:|---:|---:|---:|",
    ]
    sens = summary[summary["变体"] != "patient_k2_1x1x2"]
    for _, row in sens.sort_values(["变体", "尺度mm"]).iterrows():
        lines.append("| %s | %.0f mm | %.3f | %.3f | %.1f%% |" % (
            row["变体"], float(row["尺度mm"]), float(row["H-low_Dice_median"]),
            float(row["H-high_Dice_median"]), 100.0 * float(row["empty_or_failed_case_rate"])))
    lines += [
        "",
        "## QC与门槛状态",
        "",
        "- 6 mm主方法叠加图输出于 `../qc_amended/overlays/patient_k2_1x1x2/`；每例包含R1和R2，供逐例核对ROI边界、层面方向和标签方向。",
        "- 当前人工叠加图复核状态：%s。" % manual_qc_status,
        "- 自动指标仅代表算法和数据一致性检查；最终技术门槛判定需同时考虑人工QC。",
        "",
        "## 文件索引",
        "",
        "- `case_selection.csv`：入选病例及原始文件；",
        "- `pair_metrics.csv`：逐病例、逐尺度技术指标；",
        "- `summary.csv`：分支汇总；",
        "- `descriptor_icc.csv`：低维描述符ICC；",
        "- `run_manifest.csv`：运行边界与结局/B集隔离声明。",
        "",
    ]
    with open(os.path.join(PILOT_ROOT, "technical_pilot_amended_report.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main() -> None:
    global PILOT_ROOT, MAP_ROOT, QC_ROOT, LOG_ROOT
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="仅运行首个配对病例，用于耗时测定")
    parser.add_argument("--amended", action="store_true",
                        help="运行患者内K=2/Otsu修订技术门槛试点")
    args = parser.parse_args()
    start = time.time()
    if args.amended:
        PILOT_ROOT, MAP_ROOT, QC_ROOT, LOG_ROOT = (AMENDED_PILOT_ROOT,
                                                   AMENDED_MAP_ROOT,
                                                   AMENDED_QC_ROOT,
                                                   AMENDED_LOG_ROOT)
    ensure_dirs()
    cfg = read_json(AMENDED_CONFIG if args.amended else CONFIG)
    selected = load_pairs()
    if args.smoke:
        selected = selected.head(1).copy()
    if selected.empty:
        raise RuntimeError("没有可用于 A 集同序列 R1/R2 技术试点的病例")
    write_device_composition(selected)
    with open(os.path.join(LOG_ROOT, "technical_pilot_run.log"), "w", encoding="utf-8") as log:
        log.write("start=%s n_cases=%d smoke=%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), len(selected), args.smoke))
    scales = [float(x) for x in cfg["scales_mm"]]

    if args.amended:
        all_records = []
        all_records.extend(process_patient_variant(
            selected, "patient_k2_1x1x2", "patient_k2", cfg, scales,
            list(cfg["main_spacing_mm"]), False))
        all_records.extend(process_patient_variant(
            selected, "patient_otsu_1x1x2", "patient_otsu", cfg, scales,
            list(cfg["main_spacing_mm"]), False))
        all_records.extend(process_patient_variant(
            selected, "patient_k2_isotropic_2x2x2", "patient_k2", cfg, scales,
            list(cfg["isotropic_spacing_mm"]), False))
        all_records.extend(process_patient_variant(
            selected, "patient_k2_n4_1x1x2", "patient_k2", cfg, scales,
            list(cfg["main_spacing_mm"]), True))
        all_records.extend(add_patient_roi_perturbation_variants(selected, cfg, scales))
        records = pd.DataFrame(all_records)
        records.to_csv(os.path.join(PILOT_ROOT, "pair_metrics.csv"), index=False,
                       encoding="utf-8-sig")
        summary = summarize_patient(records)
        summary.to_csv(os.path.join(PILOT_ROOT, "summary.csv"), index=False,
                       encoding="utf-8-sig")
        write_descriptor_icc(records)
        elapsed = time.time() - start
        pd.DataFrame([{
            "strategy": "amended_patient_relative",
            "n_selected_A_same_sequence_pairs": len(selected),
            "n_metric_rows": len(records),
            "variants": ";".join(sorted(records["变体"].unique())),
            "scales_mm": ";".join(str(x) for x in scales),
            "K_values": "2",
            "elapsed_seconds": round(elapsed, 3),
            "outcome_columns_read": False,
            "B_data_read": False,
            "technical_gate_decision": "pending_manual_qc",
        }]).to_csv(os.path.join(PILOT_ROOT, "run_manifest.csv"), index=False,
                   encoding="utf-8-sig")
        write_amended_report(selected, records, summary, elapsed,
                             manual_qc_status="not_evaluated")
        with open(os.path.join(LOG_ROOT, "technical_pilot_run.log"), "a", encoding="utf-8") as log:
            log.write("end=%s elapsed_seconds=%.3f rows=%d strategy=amended_patient_relative\n" %
                      (time.strftime("%Y-%m-%d %H:%M:%S"), elapsed, len(records)))
        print("selected pairs:", len(selected))
        print("metric rows:", len(records))
        print("elapsed seconds:", round(elapsed, 1))
        print("outputs:", PILOT_ROOT)
        return

    ks = [int(x) for x in cfg["cluster_k"]]
    all_records = []
    all_records.extend(process_variant(selected, "primary_1x1x2", cfg, scales, ks,
                                        list(cfg["main_spacing_mm"]), False))
    all_records.extend(process_variant(selected, "isotropic_2x2x2", cfg, scales, ks,
                                        list(cfg["isotropic_spacing_mm"]), False))
    all_records.extend(process_variant(selected, "n4_1x1x2", cfg, scales, ks,
                                        list(cfg["main_spacing_mm"]), True))
    all_records.extend(add_roi_perturbation_variants(selected, cfg, scales, ks))
    records = pd.DataFrame(all_records)
    records.to_csv(os.path.join(PILOT_ROOT, "pair_metrics.csv"), index=False, encoding="utf-8-sig")
    summary = summarize(records)
    summary.to_csv(os.path.join(PILOT_ROOT, "summary.csv"), index=False, encoding="utf-8-sig")
    write_descriptor_icc(records)
    pd.DataFrame([{"n_selected_A_same_sequence_pairs": len(selected),
                   "n_metric_rows": len(records),
                   "variants": ";".join(sorted(records["变体"].unique())),
                   "scales_mm": ";".join(str(x) for x in scales),
                   "K_values": ";".join(str(x) for x in ks),
                   "elapsed_seconds": round(time.time() - start, 3),
                   "outcome_columns_read": False,
                   "B_data_read": False,
                   "technical_gate_decision": "not_performed"}]).to_csv(
                       os.path.join(PILOT_ROOT, "run_manifest.csv"), index=False, encoding="utf-8-sig")
    with open(os.path.join(LOG_ROOT, "technical_pilot_run.log"), "a", encoding="utf-8") as log:
        log.write("end=%s elapsed_seconds=%.3f rows=%d\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), time.time() - start, len(records)))
    print("selected pairs:", len(selected))
    print("metric rows:", len(records))
    print("elapsed seconds:", round(time.time() - start, 1))
    print("outputs:", PILOT_ROOT)


if __name__ == "__main__":
    main()
