"""Outcome-blind 18-pair technical comparison of M1 and M2 habitat phenotypes.

The driver uses the current muscle-normalized [1, 1, 2] mm images and the
locked 4 mm 3-D SLIC configuration.  R1 defines the technical training
scaler/centroids; R2 is transformed and assigned with those frozen objects.
No outcome, clinical, or B-set columns are read.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter

import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy import ndimage
from scipy.stats import spearmanr
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

from technical_dry_run_A import apath, geom, slic_labels


HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
FEAT = os.path.join(ROOT, "feature_extract")
PREP = os.path.join(FEAT, "output", "preprocessed")
MANIFEST = os.path.join(FEAT, "output", "manifest.csv")
SELECTION = os.path.join(ROOT, "archive", "exploration_20260828",
                         "previous_habitat", "outputs", "technical_pilot",
                         "case_selection.csv")
CONFIG_PATH = os.path.join(HAB, "configs", "main_cross_case_kmeans_k2_4mm.json")
OUT = os.path.join(HAB, "output", "method_selection_18")
SEED = 12345
K = 2
MIN_SV_SUPPORT = 10
MIN_ENTROPY_WINDOW_TUMOR_VOXELS = 10
BOOTSTRAPS = 100
FEATURES_M2 = ("Mean", "P90", "IQR", "LocalEntropy")
FEATURES_M1 = ("Mean",)
WINDOWS = {
    "none": None,
    "5mm": (3, 5, 5),  # z,y,x; approximately 6 x 5 x 5 mm
    "7mm": (3, 7, 7),  # z,y,x; approximately 6 x 7 x 7 mm
}


def finite(value):
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def load_ids():
    sel = pd.read_csv(SELECTION, encoding="utf-8-sig", dtype=str)
    sel = sel[sel["入选技术试点"].astype(str) == "1"].copy()
    ids = sorted(sel["影像号"].astype(str).str.strip().unique())
    if len(ids) != 18:
        raise RuntimeError("expected 18 selected same-sequence pairs, got %d" % len(ids))
    return ids


def load_cfg():
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def read_case(pid, reader, cfg):
    folder = os.path.join(PREP, pid)
    image_path = os.path.join(folder, reader + "_image.nrrd")
    mask_path = os.path.join(folder, reader + "_mask.nrrd")
    image = sitk.ReadImage(apath(image_path))
    mask = sitk.ReadImage(apath(mask_path))
    errors, arr, roi = geom(image, mask)
    if errors:
        raise RuntimeError("%s/%s: %s" % (pid, reader, ";".join(errors)))
    labels = slic_labels(image, cfg, True)
    labels_repeat = slic_labels(image, cfg, True)
    return {
        "pid": pid,
        "reader": reader,
        "image_path": os.path.abspath(image_path),
        "mask_path": os.path.abspath(mask_path),
        "image": image,
        "arr": arr,
        "roi": roi,
        "labels": labels,
        "slic_repeat_consistent": int(np.array_equal(labels, labels_repeat)),
    }


def entropy_map(arr, roi, window_size, bin_width):
    """Local entropy using one fixed origin (0) and fixed bin width."""
    bins = np.floor(arr / float(bin_width)).astype(np.int32)
    size = tuple(int(x) for x in window_size)
    full = float(np.prod(size))
    occupancy = ndimage.uniform_filter(
        roi.astype(np.float64), size=size, mode="constant", cval=0.0)
    counts = occupancy * full
    valid = roi & (counts >= MIN_ENTROPY_WINDOW_TUMOR_VOXELS)
    entropy = np.zeros(arr.shape, dtype=np.float32)
    denominator = np.maximum(occupancy, 1e-12)
    for level in np.unique(bins[roi]):
        indicator = ((bins == int(level)) & roi).astype(np.float64)
        probability = ndimage.uniform_filter(
            indicator, size=size, mode="constant", cval=0.0) / denominator
        use = valid & (probability > 0)
        entropy[use] -= (probability[use] * np.log(probability[use])).astype(np.float32)
    return entropy, valid, counts


def feature_rows(item, window_name, window_size, bin_width):
    arr, roi, labels = item["arr"], item["roi"], item["labels"]
    if window_size is None:
        e_map = np.zeros(arr.shape, dtype=np.float32)
        e_valid = np.zeros(arr.shape, dtype=bool)
    else:
        e_map, e_valid, _ = entropy_map(arr, roi, window_size, bin_width)
    rows = []
    for label in np.unique(labels[roi]):
        label = int(label)
        inside = (labels == label) & roi
        values = arr[inside].astype(np.float64)
        if not len(values):
            continue
        e_inside = inside & e_valid
        e_values = e_map[e_inside].astype(np.float64)
        total = int((labels == label).sum())
        n = int(inside.sum())
        row = {
            "影像号": item["pid"],
            "reader": item["reader"],
            "window": window_name,
            "sv_label": label,
            "sv_total_voxels": total,
            "n_tumor_voxels": n,
            "tumor_overlap_fraction": float(n / total) if total else np.nan,
            "Mean": float(values.mean()),
            "P90": float(np.percentile(values, 90)),
            "IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "entropy_valid_voxels": int(e_values.size),
            "entropy_valid_fraction": float(e_values.size / n) if n else np.nan,
            "LocalEntropy": float(e_values.mean()) if e_values.size else np.nan,
        }
        row["M1_valid"] = int(finite(row["Mean"]))
        row["M2_valid"] = int(
            n >= MIN_SV_SUPPORT and all(finite(row[x]) for x in FEATURES_M2))
        rows.append(row)
    return rows


def weighted_scale(x, w):
    x = np.asarray(x, dtype=float)
    w = np.asarray(w, dtype=float)
    total = float(w.sum())
    mean = np.sum(w[:, None] * x, axis=0) / total
    sd = np.sqrt(np.sum(w[:, None] * (x - mean) ** 2, axis=0) / total)
    sd[~np.isfinite(sd) | (sd < 1e-12)] = 1.0
    return mean, sd


def balanced_weights(df):
    counts = df.groupby("影像号")["sv_label"].transform("count").astype(float)
    return 1.0 / counts.to_numpy()


def fit_model(df, method, window, seed=SEED):
    use = df[(df["reader"] == "R1") & (df["window"] == window)].copy()
    valid_col = "M1_valid" if method == "M1_mean" else "M2_valid"
    use = use[use[valid_col].astype(int) == 1].copy()
    features = FEATURES_M1 if method == "M1_mean" else FEATURES_M2
    if len(use) < 2:
        raise RuntimeError("insufficient valid R1 cases for %s/%s" % (method, window))
    x = use.loc[:, features].to_numpy(dtype=float)
    w = balanced_weights(use)
    mean, sd = weighted_scale(x, w)
    model = KMeans(n_clusters=K, init="k-means++", n_init=100,
                   max_iter=300, tol=1e-4, random_state=seed)
    model.fit((x - mean) / sd, sample_weight=w)
    centers = model.cluster_centers_ * sd + mean
    order = np.argsort(centers[:, 0])
    return {
        "method": method,
        "window": window,
        "features": features,
        "mean": mean,
        "sd": sd,
        "model": model,
        "centers": centers,
        "order": order,
        "fit_rows": use,
        "fit_cases": int(use["影像号"].nunique()),
        "fit_supervoxels": int(len(use)),
    }


def predict_classes(model_info, df):
    features = model_info["features"]
    out = df.copy()
    valid_col = "M1_valid" if model_info["method"] == "M1_mean" else "M2_valid"
    valid = out[valid_col].astype(int) == 1
    out["cluster_class"] = -1
    if valid.any():
        x = out.loc[valid, features].to_numpy(dtype=float)
        raw = model_info["model"].predict(
            (x - model_info["mean"]) / model_info["sd"])
        low_idx, high_idx = model_info["order"]
        out.loc[valid, "cluster_class"] = np.where(raw == low_idx, 0, 1)
        out.loc[valid, "cluster_class"] = np.where(raw == high_idx, 1,
                                                     out.loc[valid, "cluster_class"])
    return out


def dice(a, b):
    den = int(a.sum() + b.sum())
    return float(2.0 * (a & b).sum() / den) if den else np.nan


def icc21(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 2 or x.shape[1] != 2 or x.shape[0] < 2:
        return np.nan
    if not np.isfinite(x).all():
        return np.nan
    n, k = x.shape
    grand = x.mean()
    row_mean = x.mean(axis=1)
    col_mean = x.mean(axis=0)
    msr = k * np.sum((row_mean - grand) ** 2) / (n - 1)
    msc = n * np.sum((col_mean - grand) ** 2) / (k - 1)
    mse = np.sum((x - row_mean[:, None] - col_mean[None, :] + grand) ** 2) / ((n - 1) * (k - 1))
    den = msr + (k - 1) * mse + k * (msc - mse) / n
    return float((msr - mse) / den) if abs(den) > 1e-12 else np.nan


def weighted_cluster_metrics(x, labels, weights):
    x = np.asarray(x, dtype=float)
    labels = np.asarray(labels, dtype=int)
    weights = np.asarray(weights, dtype=float)
    centers = np.vstack([np.average(x[labels == j], axis=0,
                                    weights=weights[labels == j]) for j in (0, 1)])
    distances = np.sqrt(((x[:, None, :] - x[None, :, :]) ** 2).sum(axis=2))
    silhouettes = []
    for i in range(len(x)):
        own = labels == labels[i]
        own_weight = weights[own].sum() - weights[i]
        a = (distances[i, own].dot(weights[own]) - 0.0) / own_weight if own_weight > 0 else 0.0
        other = labels != labels[i]
        b = distances[i, other].dot(weights[other]) / weights[other].sum() if other.any() else 0.0
        silhouettes.append((b - a) / max(a, b) if max(a, b) > 1e-12 else 0.0)
    scatter = []
    for j in (0, 1):
        use = labels == j
        scatter.append(float(np.average(np.sqrt(((x[use] - centers[j]) ** 2).sum(axis=1)),
                                         weights=weights[use])))
    separation = float(np.linalg.norm(centers[0] - centers[1]))
    db = float((scatter[0] + scatter[1]) / separation) if separation > 1e-12 else np.nan
    return float(np.average(silhouettes, weights=weights)), db


def case_maps(feature_df, items, model_info):
    pred = predict_classes(model_info, feature_df)
    maps, diagnostics = {}, []
    for (pid, reader), item in items.items():
        group = pred[(pred["影像号"] == pid) & (pred["reader"] == reader) &
                     (pred["window"] == model_info["window"])].copy()
        hmap = np.full(item["labels"].shape, -1, dtype=np.int8)
        for _, row in group[group["cluster_class"] >= 0].iterrows():
            hmap[item["labels"] == int(row["sv_label"])] = int(row["cluster_class"])
        maps[(model_info["method"], model_info["window"], pid, reader)] = hmap
        total = int(item["roi"].sum())
        assigned = group[group["cluster_class"] >= 0]
        low = int(assigned.loc[assigned["cluster_class"] == 0, "n_tumor_voxels"].sum())
        high = int(assigned.loc[assigned["cluster_class"] == 1, "n_tumor_voxels"].sum())
        unassigned = int(total - low - high)
        diagnostics.append({
            "method": model_info["method"], "window": model_info["window"],
            "影像号": pid, "reader": reader,
            "slic_repeat_consistent": item["slic_repeat_consistent"],
            "n_supervoxels": int(len(group)),
            "n_valid_supervoxels": int(len(assigned)),
            "tumor_voxels": total,
            "unassigned_tumor_voxels": unassigned,
            "assigned_tumor_fraction": float((low + high) / total) if total else np.nan,
            "H_low_voxels": low, "H_high_voxels": high,
            "H_low_fraction": float(low / total) if total else np.nan,
            "H_high_fraction": float(high / total) if total else np.nan,
            "H_low_empty": int(low == 0), "H_high_empty": int(high == 0),
            "empty_habitat": int(low == 0 or high == 0),
            "near_empty_1pct": int(min(low, high) / total < .01) if total else 1,
            "near_empty_5pct": int(min(low, high) / total < .05) if total else 1,
            "near_empty_10pct": int(min(low, high) / total < .10) if total else 1,
            "m2_support_excluded_supervoxels": int((group["n_tumor_voxels"] < MIN_SV_SUPPORT).sum()) if model_info["method"] != "M1_mean" else 0,
            "m2_entropy_invalid_supervoxels": int(group["LocalEntropy"].isna().sum()) if model_info["method"] != "M1_mean" else 0,
        })
    return maps, pd.DataFrame(diagnostics), pred


def pair_metrics(diag, maps, items, ids, model_info):
    rows = []
    for pid in ids:
        if ((pid, "R1") not in items or (pid, "R2") not in items):
            continue
        r1 = items[(pid, "R1")]
        r2 = items[(pid, "R2")]
        h1 = maps[(model_info["method"], model_info["window"], pid, "R1")]
        h2 = maps[(model_info["method"], model_info["window"], pid, "R2")]
        roi1, roi2 = r1["roi"], r2["roi"]
        common = roi1 & roi2 & (h1 >= 0) & (h2 >= 0)
        d1 = diag[(diag["影像号"] == pid) & (diag["reader"] == "R1")].iloc[0]
        d2 = diag[(diag["影像号"] == pid) & (diag["reader"] == "R2")].iloc[0]
        rows.append({
            "method": model_info["method"], "window": model_info["window"], "影像号": pid,
            "ROI_Dice": dice(roi1, roi2),
            "assigned_common_fraction": float(common.sum() / (roi1 | roi2).sum()) if (roi1 | roi2).any() else np.nan,
            "ARI": adjusted_rand_score(h1[common], h2[common]) if common.any() else np.nan,
            "H_low_Dice": dice(h1 == 0, h2 == 0),
            "H_high_Dice": dice(h1 == 1, h2 == 1),
            "R1_H_high_fraction": float(d1["H_high_fraction"]),
            "R2_H_high_fraction": float(d2["H_high_fraction"]),
            "R1_empty": int(d1["empty_habitat"]), "R2_empty": int(d2["empty_habitat"]),
            "pair_empty": int(d1["empty_habitat"] or d2["empty_habitat"]),
        })
    return pd.DataFrame(rows)


def feature_quality(feature_df, method, window):
    group = feature_df[(feature_df["reader"] == "R1") & (feature_df["window"] == window)].copy()
    valid_col = "M1_valid" if method == "M1_mean" else "M2_valid"
    use = group[group[valid_col].astype(int) == 1]
    features = FEATURES_M1 if method == "M1_mean" else FEATURES_M2
    out = {"method": method, "window": window, "all_sv": len(group),
           "valid_sv": len(use), "valid_sv_fraction": float(len(use) / len(group)) if len(group) else np.nan,
           "valid_cases": int(use["影像号"].nunique()),
           "all_cases": int(group["影像号"].nunique())}
    for f in features:
        out[f + "_range_min"] = float(use[f].min()) if len(use) else np.nan
        out[f + "_range_p50"] = float(use[f].median()) if len(use) else np.nan
        out[f + "_range_max"] = float(use[f].max()) if len(use) else np.nan
    for i, a in enumerate(features):
        for b in features[i + 1:]:
            key = a + "_" + b
            out["pearson_" + key] = float(use[[a, b]].corr().iloc[0, 1]) if len(use) > 2 else np.nan
            out["spearman_" + key] = float(spearmanr(use[a], use[b], nan_policy="omit")[0]) if len(use) > 2 else np.nan
    return out


def case_feature_rows(feature_df, method, window):
    valid_col = "M1_valid" if method == "M1_mean" else "M2_valid"
    features = FEATURES_M1 if method == "M1_mean" else FEATURES_M2
    group = feature_df[(feature_df["window"] == window) & (feature_df[valid_col].astype(int) == 1)]
    rows = []
    for (pid, reader), g in group.groupby(["影像号", "reader"]):
        for feature in features:
            vals = g[feature].to_numpy(dtype=float)
            rows.append({"method": method, "window": window, "影像号": pid,
                         "reader": reader, "feature": feature, "n_sv": len(vals),
                         "case_feature_mean": float(np.mean(vals)),
                         "case_feature_median": float(np.median(vals)),
                         "case_feature_p90": float(np.percentile(vals, 90))})
    return pd.DataFrame(rows)


def feature_reproducibility(case_features, method, window):
    sub = case_features[(case_features["method"] == method) & (case_features["window"] == window)]
    rows = []
    for feature in sorted(sub["feature"].unique()):
        wide = sub[sub["feature"] == feature].pivot(index="影像号", columns="reader", values="case_feature_mean").dropna()
        pair = wide[["R1", "R2"]].to_numpy(dtype=float) if not wide.empty else np.empty((0, 2))
        rho = spearmanr(pair[:, 0], pair[:, 1])[0] if len(pair) >= 3 else np.nan
        rows.append({"method": method, "window": window, "feature": feature,
                     "n_pairs": len(pair), "ICC_2_1": icc21(pair), "Spearman": float(rho) if finite(rho) else np.nan})
    return rows


def bootstrap_centers(feature_df, model_info, ids):
    method, window = model_info["method"], model_info["window"]
    valid_col = "M1_valid" if method == "M1_mean" else "M2_valid"
    features = model_info["features"]
    source = feature_df[(feature_df["reader"] == "R1") & (feature_df["window"] == window) &
                        (feature_df[valid_col].astype(int) == 1)].copy()
    by_case = {pid: g for pid, g in source.groupby("影像号")}
    rng = np.random.RandomState(SEED + 1000 + (0 if method == "M1_mean" else (5 if window == "5mm" else 7)))
    rows = []
    for b in range(BOOTSTRAPS):
        sampled = rng.choice(ids, size=len(ids), replace=True)
        chunks, weights = [], []
        occurrences = Counter(sampled)
        for pid in sorted(occurrences):
            g = by_case.get(pid)
            if g is None:
                continue
            chunks.append(g)
            weights.extend([float(occurrences[pid]) / len(ids) / len(g)] * len(g))
        if len(chunks) < 2:
            continue
        use = pd.concat(chunks, ignore_index=True)
        x = use.loc[:, features].to_numpy(dtype=float)
        w = np.asarray(weights, dtype=float)
        mean, sd = weighted_scale(x, w)
        km = KMeans(n_clusters=K, init="k-means++", n_init=100, max_iter=300,
                    tol=1e-4, random_state=SEED + b)
        km.fit((x - mean) / sd, sample_weight=w)
        centers = km.cluster_centers_ * sd + mean
        centers = centers[np.argsort(centers[:, 0])]
        row = {"method": method, "window": window, "bootstrap": b}
        for j, label in enumerate(("low", "high")):
            for feature_index, feature in enumerate(features):
                row["center_" + label + "_" + feature] = float(centers[j, feature_index])
        rows.append(row)
    return pd.DataFrame(rows)


def local_center_diagnostics(feature_df, ids, global_model):
    centers = global_model["centers"][global_model["order"]]
    boundary = float((centers[0, 0] + centers[1, 0]) / 2.0)
    rows = []
    for pid in ids:
        for reader in ("R1", "R2"):
            group = feature_df[(feature_df["影像号"] == pid) &
                               (feature_df["reader"] == reader) &
                               (feature_df["window"] == "none")]
            if group.empty:
                continue
            values = group["Mean"].to_numpy(dtype=float)
            values = values[np.isfinite(values)]
            row = {"影像号": pid, "reader": reader,
                   "global_mean_boundary": boundary,
                   "local_center_low": np.nan, "local_center_high": np.nan,
                   "local_center_delta": np.nan, "local_midpoint": np.nan,
                   "local_midpoint_offset_B": np.nan, "diagnostic_type": "invalid"}
            if values.size >= 2 and np.unique(values).size >= 2:
                km = KMeans(n_clusters=2, init="k-means++", n_init=100,
                            max_iter=300, tol=1e-4, random_state=SEED)
                km.fit(values.reshape(-1, 1))
                low, high = np.sort(km.cluster_centers_.ravel())
                midpoint = float((low + high) / 2.0)
                if high < boundary:
                    diagnostic_type = "type1_both_local_below_global_boundary"
                elif low > boundary:
                    diagnostic_type = "type2_both_local_above_global_boundary"
                else:
                    diagnostic_type = "type3_local_centers_straddle_global_boundary"
                row.update(local_center_low=float(low), local_center_high=float(high),
                           local_center_delta=float(high - low), local_midpoint=midpoint,
                           local_midpoint_offset_B=float(midpoint - boundary),
                           diagnostic_type=diagnostic_type)
            rows.append(row)
    return pd.DataFrame(rows)


def model_summary(model_info, diag, pairs, quality, repro, bootstrap):
    centers = model_info["centers"][model_info["order"]]
    valid_pairs = pairs.dropna(subset=["R1_H_high_fraction", "R2_H_high_fraction"])
    high = valid_pairs[["R1_H_high_fraction", "R2_H_high_fraction"]].to_numpy(dtype=float)
    row = {"method": model_info["method"], "window": model_info["window"],
           "fit_cases": model_info["fit_cases"], "fit_supervoxels": model_info["fit_supervoxels"],
           "feature_set": "+".join(model_info["features"]),
           "weighted_silhouette": np.nan, "weighted_davies_bouldin": np.nan,
           "R1_empty_rate": float(diag[diag["reader"] == "R1"]["empty_habitat"].mean()),
           "R2_empty_rate": float(diag[diag["reader"] == "R2"]["empty_habitat"].mean()),
           "pair_empty_rate": float(pairs["pair_empty"].mean()),
           "R1_near_empty_1pct": float(diag[diag["reader"] == "R1"]["near_empty_1pct"].mean()),
           "R1_near_empty_5pct": float(diag[diag["reader"] == "R1"]["near_empty_5pct"].mean()),
           "R1_near_empty_10pct": float(diag[diag["reader"] == "R1"]["near_empty_10pct"].mean()),
           "H_low_Dice_median": float(pairs["H_low_Dice"].median()),
           "H_high_Dice_median": float(pairs["H_high_Dice"].median()),
           "ARI_median": float(pairs["ARI"].median()),
           "H_high_fraction_ICC_2_1": icc21(high),
           "Mean_center_low": float(centers[0, 0]), "Mean_center_high": float(centers[1, 0]),
           "Mean_center_separation": float(centers[1, 0] - centers[0, 0]),
           "P90_center_low": float(centers[0, 1]) if len(model_info["features"]) > 1 else np.nan,
           "P90_center_high": float(centers[1, 1]) if len(model_info["features"]) > 1 else np.nan,
           "quality_valid_sv_fraction": quality["valid_sv_fraction"],
           "bootstrap_valid": int(len(bootstrap))}
    for label in ("low", "high"):
        col = "center_" + label + "_Mean"
        if col in bootstrap:
            row["bootstrap_" + label + "_Mean_sd"] = float(bootstrap[col].std(ddof=1))
            row["bootstrap_" + label + "_Mean_p2_5"] = float(bootstrap[col].quantile(.025))
            row["bootstrap_" + label + "_Mean_p97_5"] = float(bootstrap[col].quantile(.975))
    return row


def write_markdown(summary, quality, repro, run_meta):
    lines = [
        "# 18例M1/M2无结局技术比较",
        "",
        "本结果使用18例同序列病例的R1数据；其中17例具有可用的R2预处理结果。R1拟合patient-balanced scaler与global K-means，R2使用R1冻结对象转换和分配。未读取结局、临床变量或B集数据。",
        "",
        "## 当前技术定义",
        "",
        "- 肌肉均值归一化；重采样 `[1,1,2] mm`；N4关闭；3D SLIC目标尺度4 mm；连通性开启。",
        "- M1：`Mean`；M2：`Mean + P90 + IQR + Mean(LocalEntropy)`。",
        "- LocalEntropy使用肿瘤内滑窗、自然对数、固定bin origin=0、固定bin width=%.6f；候选窗口为5 mm与7 mm物理近似窗口。" % run_meta["bin_width"],
        "- M2超体素候选最低支持为%d个肿瘤体素；该阈值仅用于技术候选评估。" % MIN_SV_SUPPORT,
        "- 634539的R2肌肉参考标签无法在标签2/3之间无猜测解析，因此仅纳入R1分析，不纳入R1/R2配对一致性统计。",
        "",
        "## 结果",
        "",
        "|方法|窗口|拟合SV|R1空生境|R2空生境|配对空生境|H-low Dice中位|H-high Dice中位|H-high ICC(2,1)|Mean中心间距|加权silhouette|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in summary.iterrows():
        window = r["window"]
        lines.append("| %s | %s | %d | %.1f%% | %.1f%% | %.1f%% | %.3f | %.3f | %.3f | %.3f | %s |" % (
            r["method"], window, int(r["fit_supervoxels"]), 100 * r["R1_empty_rate"],
            100 * r["R2_empty_rate"], 100 * r["pair_empty_rate"], r["H_low_Dice_median"],
            r["H_high_Dice_median"], r["H_high_fraction_ICC_2_1"], r["Mean_center_separation"],
            "NA" if not finite(r["weighted_silhouette"]) else "%.3f" % r["weighted_silhouette"]))
    lines += [
        "",
        "## 数据边界",
        "",
        "- 本阶段为技术方法选择，不进行DFS、AUC、C-index或任何结局导向的筛选。",
        "- M2是否保留应综合特征冗余、R1/R2稳定性、bootstrap中心稳定性和Mean绝对表型方向；空生境率不作为唯一判断依据。",
        "",
    ]
    with open(os.path.join(OUT, "method_selection_summary.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    start = time.time()
    os.makedirs(OUT, exist_ok=True)
    cfg = load_cfg()
    ids = load_ids()
    if args.smoke:
        ids = ids[:2]
    items = {}
    errors = []
    input_status = []
    manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    manifest = manifest.set_index("影像号")
    for pid in ids:
        for reader in ("R1", "R2"):
            image_path = os.path.join(PREP, pid, reader + "_image.nrrd")
            mask_path = os.path.join(PREP, pid, reader + "_mask.nrrd")
            if not (os.path.exists(image_path) and os.path.exists(mask_path)):
                reason = "preprocessed_output_missing"
                if reader == "R2" and pid in manifest.index:
                    reason = str(manifest.loc[pid, "R2肌肉标签状态"] or
                                 "R2_preprocessing_unavailable")
                input_status.append({
                    "影像号": pid, "reader": reader,
                    "status": "unavailable", "reason": reason,
                })
                if reader == "R1":
                    errors.append({"影像号": pid, "reader": reader,
                                   "error": reason})
                continue
            try:
                items[(pid, reader)] = read_case(pid, reader, cfg)
                input_status.append({
                    "影像号": pid, "reader": reader,
                    "status": "available", "reason": "",
                })
            except Exception as exc:
                errors.append({"影像号": pid, "reader": reader, "error": str(exc)})
                input_status.append({
                    "影像号": pid, "reader": reader,
                    "status": "error", "reason": str(exc),
                })
    if errors:
        pd.DataFrame(errors).to_csv(os.path.join(OUT, "input_errors.csv"), index=False, encoding="utf-8-sig")
        raise RuntimeError("input errors: %d" % len(errors))
    pd.DataFrame(input_status).to_csv(
        os.path.join(OUT, "input_status.csv"), index=False, encoding="utf-8-sig")
    all_features = []
    for item in items.values():
        for window, size in WINDOWS.items():
            all_features.extend(feature_rows(item, window, size, cfg["habitat_radiomics"]["bin_width"]))
    feature_df = pd.DataFrame(all_features)
    feature_df.to_csv(os.path.join(OUT, "supervoxel_features.csv"), index=False, encoding="utf-8-sig")
    model_specs = [("M1_mean", "none"), ("M2_4D", "5mm"), ("M2_4D", "7mm")]
    all_diag, all_pairs, all_quality, all_case_features, all_repro, all_boot = [], [], [], [], [], []
    model_rows = []
    for method, window in model_specs:
        model_info = fit_model(feature_df, method, window)
        model_rows.append(model_info)
        maps, diag, predicted = case_maps(feature_df, items, model_info)
        pairs = pair_metrics(diag, maps, items, ids, model_info)
        quality = feature_quality(feature_df, method, window)
        case_features = case_feature_rows(feature_df, method, window)
        repro = feature_reproducibility(case_features, method, window)
        boot = bootstrap_centers(feature_df, model_info, ids) if len(ids) >= 2 else pd.DataFrame()
        x = model_info["fit_rows"].loc[:, model_info["features"]].to_numpy(dtype=float)
        w = balanced_weights(model_info["fit_rows"])
        pred_fit = model_info["model"].labels_
        low_idx, high_idx = model_info["order"]
        labels = np.where(pred_fit == low_idx, 0, 1)
        labels = np.where(pred_fit == high_idx, 1, labels)
        sil, db = weighted_cluster_metrics((x - model_info["mean"]) / model_info["sd"], labels, w)
        quality["weighted_silhouette"] = sil
        quality["weighted_davies_bouldin"] = db
        diag["fit_cases"] = model_info["fit_cases"]
        diag["fit_supervoxels"] = model_info["fit_supervoxels"]
        diag["Mean_center_low"] = model_info["centers"][low_idx, 0]
        diag["Mean_center_high"] = model_info["centers"][high_idx, 0]
        diag["shared_mean_boundary"] = np.mean([diag["Mean_center_low"].iloc[0], diag["Mean_center_high"].iloc[0]])
        all_diag.append(diag)
        all_pairs.append(pairs)
        all_quality.append(quality)
        all_case_features.append(case_features)
        all_repro.extend(repro)
        if len(boot):
            all_boot.append(boot)
        summary_row = model_summary(model_info, diag, pairs, quality, repro, boot)
        summary_row["weighted_silhouette"] = sil
        summary_row["weighted_davies_bouldin"] = db
        model_rows[-1]["summary"] = summary_row
    diagnostics = pd.concat(all_diag, ignore_index=True)
    pairs = pd.concat(all_pairs, ignore_index=True)
    quality_df = pd.DataFrame(all_quality)
    case_features = pd.concat(all_case_features, ignore_index=True)
    repro_df = pd.DataFrame(all_repro)
    bootstrap_df = pd.concat(all_boot, ignore_index=True) if all_boot else pd.DataFrame()
    summary = pd.DataFrame([x["summary"] for x in model_rows])
    local_diag = local_center_diagnostics(feature_df, ids, model_rows[0])
    center_rows = []
    for model_info in model_rows:
        sorted_centers = model_info["centers"][model_info["order"]]
        for cluster_index, label in enumerate(("H-low", "H-high")):
            row = {"method": model_info["method"], "window": model_info["window"],
                   "label": label, "cluster_index": cluster_index}
            for feature_index, feature in enumerate(model_info["features"]):
                row[feature] = float(sorted_centers[cluster_index, feature_index])
            center_rows.append(row)
    centers_df = pd.DataFrame(center_rows)
    diagnostics.to_csv(os.path.join(OUT, "case_diagnostics.csv"), index=False, encoding="utf-8-sig")
    pairs.to_csv(os.path.join(OUT, "pair_metrics.csv"), index=False, encoding="utf-8-sig")
    quality_df.to_csv(os.path.join(OUT, "feature_quality.csv"), index=False, encoding="utf-8-sig")
    case_features.to_csv(os.path.join(OUT, "case_feature_summary.csv"), index=False, encoding="utf-8-sig")
    repro_df.to_csv(os.path.join(OUT, "feature_reproducibility.csv"), index=False, encoding="utf-8-sig")
    bootstrap_df.to_csv(os.path.join(OUT, "bootstrap_centers.csv"), index=False, encoding="utf-8-sig")
    summary.to_csv(os.path.join(OUT, "method_summary.csv"), index=False, encoding="utf-8-sig")
    local_diag.to_csv(os.path.join(OUT, "local_center_diagnostics.csv"), index=False, encoding="utf-8-sig")
    centers_df.to_csv(os.path.join(OUT, "global_centers.csv"), index=False, encoding="utf-8-sig")
    n_r1 = sum((pid, "R1") in items for pid in ids)
    n_r2 = sum((pid, "R2") in items for pid in ids)
    pd.DataFrame([{
        "n_pairs": len(ids), "n_r1_available": n_r1, "n_r2_available": n_r2,
        "n_r2_unavailable": len(ids) - n_r2, "n_reader_images": len(items),
        "models": ";".join(x[0] + "_" + x[1] for x in model_specs),
        "bin_width": cfg["habitat_radiomics"]["bin_width"], "bin_origin": 0.0,
        "entropy_log_base": "e", "entropy_min_window_tumor_voxels": MIN_ENTROPY_WINDOW_TUMOR_VOXELS,
        "minimum_supervoxel_tumor_voxels_M2": MIN_SV_SUPPORT,
        "preprocessing": "muscle_mean;spacing_1,1,2;N4_off", "slic": "3D;4mm;iter5;weight10;connectivity_on",
        "fit_reader": "R1", "outcome_columns_read": False, "B_data_read": False,
        "elapsed_seconds": round(time.time() - start, 3), "smoke": args.smoke,
    }]).to_csv(os.path.join(OUT, "run_manifest.csv"), index=False, encoding="utf-8-sig")
    if not args.smoke:
        write_markdown(summary, quality_df, repro_df, {"bin_width": cfg["habitat_radiomics"]["bin_width"]})
    print("pairs:", len(ids), "reader images:", len(items), "feature rows:", len(feature_df),
          "models:", len(model_specs), "elapsed seconds:", round(time.time() - start, 1),
          "outputs:", OUT)


if __name__ == "__main__":
    main()
