
"""Outcome-blind A=393 technical dry run for shared-centre habitat diagnosis."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import time
from collections import Counter
import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy import ndimage
from sklearn.cluster import KMeans

HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
FEAT = os.path.join(ROOT, "feature_extract")
PREP = os.path.join(FEAT, "output", "preprocessed")
MANIFEST = os.path.join(FEAT, "output", "manifest.csv")
SCANNER = os.path.join(FEAT, "output", "scanner_map.csv")
TECHNICAL_A = os.path.join(HAB, "output", "technical_cohort_manifest",
                           "cohort_A_lenient.csv")
AUDIT = os.path.join(HAB, "output", "high_signal_eligibility_audit",
                     "patient_features.csv")
PREP_METRICS = os.path.join(FEAT, "output", "qc", "logs", "preprocess_metrics.csv")
CONFIG = os.path.join(HAB, "configs", "main_cross_case_kmeans_k2_4mm.json")
OUT = os.path.join(HAB, "output", "feasibility_A")
ASCII_ROOT = os.path.join(os.path.dirname(ROOT), "radiomics26")


def apath(path):
    path = os.path.abspath(path)
    root = os.path.abspath(ROOT)
    return os.path.join(ASCII_ROOT, path[len(root) + 1:]) if path.lower().startswith((root + os.sep).lower()) else path


def number(value):
    try:
        x = float(value)
        return x if np.isfinite(x) else np.nan
    except (TypeError, ValueError):
        return np.nan


def load_cases():
    a = pd.read_csv(TECHNICAL_A, encoding="utf-8-sig", dtype=str,
                    usecols=["影像号"])
    ids = sorted(set(a["影像号"].astype(str).str.strip()))
    if len(ids) != 393:
        raise RuntimeError("A identifier count is %d, expected 393" % len(ids))
    mcols = ["影像号", "序列名", "尺寸", "层厚mm", "面内间距mm", "肿瘤体素",
             "肿瘤体积mm3", "几何一致", "R1标签2均灰度", "R1标签3均灰度"]
    m = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str, usecols=mcols)
    m["影像号"] = m["影像号"].astype(str).str.strip()
    fcols = ["patient_id", "reader", "high_fraction", "high_lcc_voxels",
             "high_lcc_volume_mm3", "high_lcc_fraction"]
    f = pd.read_csv(AUDIT, encoding="utf-8-sig", dtype=str, usecols=fcols)
    f = f[(f["reader"] == "R1") & f["patient_id"].isin(ids)].copy()
    f = f.rename(columns={"patient_id": "影像号"})
    pm = pd.read_csv(PREP_METRICS, encoding="utf-8-sig", dtype=str)
    strict_cols = {
        "影像号", "读者", "normalization_requested",
        "normalization_applied", "normalization_status",
        "reference_label", "reference_mean",
    }
    if not strict_cols.issubset(pm.columns):
        raise RuntimeError(
            "preprocess_metrics.csv lacks the strict normalization schema; "
            "regenerate preprocessing outputs before the technical dry run")
    pm = pm[(pm["读者"] == "R1")
            & (pm["normalization_requested"] == "muscle")
            & (pm["normalization_applied"] == "muscle")
            & (pm["normalization_status"] == "success")
            & (pm["reference_label"] == "3")
            & pm["影像号"].isin(ids)].copy()
    pm = pm.rename(columns={"reference_label": "muscle_label",
                           "reference_mean": "muscle_mean"})
    scols = ["影像号", "R1厂商", "R1机型", "R1场强", "R1系列", "R1行", "R1列",
             "R1面内间距", "R1层厚", "R1层数"]
    s = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str, usecols=scols)
    s["影像号"] = s["影像号"].astype(str).str.strip()
    table = pd.DataFrame({"影像号": ids})
    for part in (m, f, s, pm):
        table = table.merge(part[part["影像号"].isin(ids)], on="影像号",
                            how="left", validate="one_to_one")
    return table.sort_values("影像号").reset_index(drop=True)


def geom(image, mask):
    errors = []
    if image.GetSize() != mask.GetSize(): errors.append("image_mask_size_mismatch")
    if not np.allclose(image.GetSpacing(), mask.GetSpacing(), atol=1e-5, rtol=0): errors.append("image_mask_spacing_mismatch")
    if not np.allclose(image.GetOrigin(), mask.GetOrigin(), atol=1e-4, rtol=0): errors.append("image_mask_origin_mismatch")
    if not np.allclose(image.GetDirection(), mask.GetDirection(), atol=1e-5, rtol=0): errors.append("image_mask_direction_mismatch")
    arr = sitk.GetArrayFromImage(image).astype(np.float32, copy=False)
    marr = sitk.GetArrayFromImage(mask)
    if arr.shape != marr.shape: errors.append("image_mask_array_shape_mismatch")
    if not np.isin(np.unique(marr), [0, 1]).all(): errors.append("nonbinary_preprocessed_mask")
    roi = marr == 1
    if not roi.any(): errors.append("empty_tumor_mask")
    if roi.any() and not np.isfinite(arr[roi]).all(): errors.append("nonfinite_image_inside_tumor")
    return errors, arr, roi


def slic_grid_metadata(image, cfg):
    """Return the voxel super-grid implied by a requested physical scale.

    SimpleITK's SLIC filter expects the super-grid in voxel units.  The
    conversion is therefore target physical scale divided by voxel spacing,
    independent of the image field of view.
    """
    target = float(cfg["slic"]["target_scale_mm"])
    spacing = tuple(float(value) for value in image.GetSpacing())
    grid = [max(1, int(round(target / spacing[i]))) for i in range(3)]
    actual = [grid[i] * spacing[i] for i in range(3)]
    return {
        "requested_scale_mm": target,
        "spacing_mm_xyz": spacing,
        "supergrid_voxels_xyz": tuple(grid),
        "actual_supergrid_mm_xyz": tuple(actual),
    }


def slic_labels(image, cfg, connected):
    meta = slic_grid_metadata(image, cfg)
    grid = list(meta["supergrid_voxels_xyz"])
    f = sitk.SLICImageFilter()
    f.SetSuperGridSize(grid)
    f.SetMaximumNumberOfIterations(int(cfg["slic"]["maximum_iterations"]))
    f.SetSpatialProximityWeight(float(cfg["slic"]["spatial_proximity_weight"]))
    f.SetInitializationPerturbation(bool(cfg["slic"]["initialization_perturbation"]))
    f.SetEnforceConnectivity(bool(connected))
    f.SetNumberOfWorkUnits(int(cfg["slic"]["work_units"]))
    return sitk.GetArrayFromImage(f.Execute(sitk.Cast(image, sitk.sitkFloat32))).astype(np.int32, copy=False)


def sv_stats(arr, labels, roi):
    means, counts = {}, {}
    for label in np.unique(labels[roi]):
        inside = (labels == label) & roi
        n = int(inside.sum())
        if n:
            means[int(label)] = float(arr[inside].mean())
            counts[int(label)] = n
    return np.asarray(list(means.values()), float), np.asarray(list(counts.values()), float), means


def qstats(x, name):
    names = ("_min", "_p5", "_median", "_p95", "_max")
    x = np.asarray(x, float)
    return {name + z: np.nan for z in names} if not len(x) else dict(zip([name + z for z in names], np.percentile(x, [0, 5, 50, 95, 100])))


def residual_stats(arr, labels, roi, means):
    r = [arr[(labels == label) & roi] - mean for label, mean in means.items()]
    r = np.concatenate(r) if r else np.array([], float)
    if not len(r):
        return dict(slic_residual_rmse=np.nan, slic_residual_mae=np.nan, slic_residual_sd=np.nan, slic_residual_abs_p95=np.nan)
    return dict(slic_residual_rmse=float(np.sqrt(np.mean(r * r))), slic_residual_mae=float(np.mean(np.abs(r))),
                slic_residual_sd=float(np.std(r)), slic_residual_abs_p95=float(np.percentile(np.abs(r), 95)))


def lcc(mask, spacing):
    if not mask.any(): return 0, 0.0, 0.0
    cc, _ = ndimage.label(mask, ndimage.generate_binary_structure(3, 1))
    sizes = np.bincount(cc.ravel())[1:]
    n = int(sizes.max())
    return n, n * float(np.prod(spacing)), float(n / int(mask.sum()))


def fit_primary(chunks, cfg):
    x = np.concatenate([z for z in chunks if len(z)])
    k = int(cfg["clustering"]["k"])
    if not len(x) or np.unique(x).size < k: return np.full(k, np.nan)
    c = cfg["clustering"]
    model = KMeans(n_clusters=k, init=c["initialization"], n_init=int(c["n_init"]),
                   max_iter=int(c["max_iter"]), tol=float(c["tol"]),
                   random_state=int(cfg["random_seed"]))
    model.fit(x.reshape(-1, 1))
    return np.sort(model.cluster_centers_.ravel())


def fit_equal_case(chunks, cfg):
    chunks = [np.asarray(x, float) for x in chunks if len(x)]
    if not chunks: return np.full(2, np.nan)
    x = np.concatenate(chunks)
    weights = np.concatenate([np.full(len(z), 1.0 / len(z)) for z in chunks])
    centers = np.array([x.min(), x.max()], float)
    for _ in range(int(cfg["clustering"]["max_iter"])):
        labels = np.argmin(np.abs(x[:, None] - centers[None, :]), axis=1)
        updated = centers.copy()
        for i in (0, 1):
            if np.any(labels == i): updated[i] = np.sum(weights[labels == i] * x[labels == i]) / np.sum(weights[labels == i])
        updated.sort()
        if np.max(np.abs(updated - centers)) <= float(cfg["clustering"]["tol"]): return updated
        centers = updated
    return centers


def first_pass(case, cfg):
    pid = str(case["影像号"])
    ip, mp = os.path.join(PREP, pid, "R1_image.nrrd"), os.path.join(PREP, pid, "R1_mask.nrrd")
    row = {"影像号": pid, "reader": "R1", "pass1_status": "failed",
           "image_path": os.path.abspath(ip), "mask_path": os.path.abspath(mp),
           "empty_habitat": 0, "algorithm_failure": 0,
           "unassigned_tumor_voxels": 0, "geometry_or_label_error": 0}
    try:
        image, mask = sitk.ReadImage(apath(ip)), sitk.ReadImage(apath(mp))
        errors, arr, roi = geom(image, mask)
        row["geometry_error_details"] = ";".join(errors)
        if errors:
            row["geometry_or_label_error"], row["failure_reason"] = 1, ";".join(errors)
            return row, None
        before, after = slic_labels(image, cfg, False), slic_labels(image, cfg, True)
        slic_meta = slic_grid_metadata(image, cfg)
        row.update(slic_image_unassigned_before=int((before < 0).sum()),
                   slic_image_unassigned_after=int((after < 0).sum()),
                   slic_supervoxels_before_connectivity=int(np.unique(before[roi]).size),
                   slic_supervoxels_after_connectivity=int(np.unique(after[roi]).size),
                   slic_requested_scale_mm=slic_meta["requested_scale_mm"],
                   slic_spacing_mm_xyz=";".join(map(str, slic_meta["spacing_mm_xyz"])),
                   slic_supergrid_voxels_xyz=";".join(map(str, slic_meta["supergrid_voxels_xyz"])),
                   slic_actual_supergrid_mm_xyz=";".join(map(str, slic_meta["actual_supergrid_mm_xyz"])))
        row["slic_supervoxel_count_change"] = row["slic_supervoxels_after_connectivity"] - row["slic_supervoxels_before_connectivity"]
        vals, sizes, means = sv_stats(arr, after, roi)
        row.update(effective_supervoxels=len(vals), **qstats(vals, "supervoxel_mean"),
                   **qstats(sizes, "supervoxel_tumor_voxels"), **residual_stats(arr, after, roi, means))
        spacing = tuple(float(x) for x in image.GetSpacing()[::-1])
        row.update(tumor_voxels_current_grid=int(roi.sum()),
                   tumor_volume_mm3_current_grid=float(roi.sum() * np.prod(spacing)),
                   pass1_status="ok")
        return row, {"values": vals, "image_path": ip, "mask_path": mp}
    except Exception as exc:
        row["algorithm_failure"], row["failure_reason"] = 1, "%s: %s" % (type(exc).__name__, exc)
        return row, None


def assign(case, row, cache, centers, equal, cfg):
    out = dict(row)
    if cache is None:
        out["technical_failure"] = 1
        out["failure_types"] = "algorithm_failure" if row.get("algorithm_failure") else "geometry_or_label_error"
        return out
    try:
        image, mask = sitk.ReadImage(apath(cache["image_path"])), sitk.ReadImage(apath(cache["mask_path"]))
        errors, arr, roi = geom(image, mask)
        labels = slic_labels(image, cfg, True)
        vals, sizes, means = sv_stats(arr, labels, roi)
        out.update(slic_repeat_supervoxels=len(vals),
                   slic_repeat_consistent=int(len(vals) == int(row["effective_supervoxels"]) and np.allclose(np.sort(vals), np.sort(cache["values"]), atol=1e-6, rtol=0)),
                   geometry_error_details_second_pass=";".join(errors),
                   geometry_or_label_error=int(bool(errors)),
                   **qstats(vals, "supervoxel_mean"), **qstats(sizes, "supervoxel_tumor_voxels"),
                   **residual_stats(arr, labels, roi, means))
        if len(centers) != 2 or not np.isfinite(centers).all() or centers[1] <= centers[0]:
            raise RuntimeError("invalid_global_kmeans_centers")
        b = float(np.mean(centers))
        out.update(H_low_center=float(centers[0]), H_high_center=float(centers[1]),
                   shared_boundary_b=b, shared_center_distance=float(centers[1] - centers[0]),
                   supervoxels_below_b=int(np.sum(vals < b)), supervoxels_at_or_above_b=int(np.sum(vals >= b)))
        out["H_low_empty"], out["H_high_empty"] = int(out["supervoxels_below_b"] == 0), int(out["supervoxels_at_or_above_b"] == 0)
        hab = np.full(labels.shape, -1, np.int8)
        for lab, mean in means.items(): hab[labels == lab] = int(mean >= b)
        hab[~roi] = -1
        unassigned, low, high = int((roi & ((labels < 0) | (hab < 0))).sum()), int((hab == 0).sum()), int((hab == 1).sum())
        out.update(H_low_voxels=low, H_high_voxels=high, unassigned_tumor_voxels=unassigned,
                   unassigned_tumor_fraction=float(unassigned / roi.sum()), empty_habitat=int(low == 0 or high == 0))
        out["structural_state"] = ("single-H-low" if high == 0 else
                                    "single-H-high" if low == 0 else
                                    "dual-habitat")
        spacing = tuple(float(x) for x in image.GetSpacing()[::-1])
        fat = number(case.get("R1标签2均灰度"))
        manifest_muscle = number(case.get("R1标签3均灰度"))
        muscle = number(case.get("muscle_mean"))
        muscle_source = "preprocess_metrics"
        threshold = fat / muscle if np.isfinite(fat) and np.isfinite(muscle) and muscle > 0 else np.nan
        out.update(fat_mean_raw=fat, muscle_mean_raw=muscle,
                   muscle_mean_preprocess=muscle, muscle_mean_manifest_raw=manifest_muscle,
                   muscle_reference_source=muscle_source, fat_muscle_ratio=threshold)
        if np.isfinite(threshold):
            pre = roi & (arr >= threshold)
            post = np.zeros_like(roi, bool)
            for lab, mean in means.items():
                if mean >= threshold: post |= (labels == lab) & roi
            pn, qn, overlap = int(pre.sum()), int(post.sum()), int((pre & post).sum())
            largest, volume, fraction = lcc(pre, spacing)
            out.update(preprocessed_high_voxels=pn, preprocessed_high_fraction=float(pn / roi.sum()),
                       preprocessed_high_lcc_voxels=largest, preprocessed_high_lcc_volume_mm3=volume,
                       preprocessed_high_lcc_fraction=fraction, supervoxel_high_post_voxels=qn,
                       supervoxel_high_post_fraction=float(qn / roi.sum()), supervoxel_high_overlap_voxels=overlap,
                       supervoxel_high_retention_recall=float(overlap / pn) if pn else np.nan,
                       supervoxel_high_precision=float(overlap / qn) if qn else np.nan,
                       supervoxel_high_post_to_pre_ratio=float(qn / pn) if pn else np.nan)
        if np.isfinite(equal).all() and equal[1] > equal[0]:
            eb = float(np.mean(equal))
            out.update(equal_case_weight_H_low_center=float(equal[0]), equal_case_weight_H_high_center=float(equal[1]),
                       equal_case_weight_boundary_b=eb, equal_case_weight_H_low_count=int(np.sum(vals < eb)),
                       equal_case_weight_H_high_count=int(np.sum(vals >= eb)),
                       equal_case_weight_empty=int(np.sum(vals < eb) == 0 or np.sum(vals >= eb) == 0))
        types = []
        if out["algorithm_failure"]: types.append("algorithm_failure")
        if out["unassigned_tumor_voxels"] > 0: types.append("unassigned_tumor_voxels")
        if out["geometry_or_label_error"]: types.append("geometry_or_label_error")
        out["technical_failure"], out["failure_types"], out["failure_reason"] = int(bool(types)), ";".join(types), ";".join(types)
        out["pass2_status"] = "ok"
    except Exception as exc:
        out.update(algorithm_failure=1, technical_failure=1, failure_types="algorithm_failure",
                   failure_reason="%s: %s" % (type(exc).__name__, exc), pass2_status="failed")
    return out


def file_record(path, role):
    d = {"role": role, "path": os.path.abspath(path)}
    try:
        st, h = os.stat(path), hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
        d.update(exists=1, bytes=st.st_size, modified_time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)), sha256=h.hexdigest())
    except OSError as exc:
        d.update(exists=0, bytes=np.nan, modified_time="", sha256="", error=str(exc))
    return d


def group_failure(df, cols):
    cols = [c for c in cols if c in df.columns]
    if not cols: return pd.DataFrame()
    rows = []
    for key, g in df.groupby(cols, dropna=False):
        if not isinstance(key, tuple): key = (key,)
        rows.append(dict(zip(cols, key), n_cases=len(g), n_failures=int(g.technical_failure.sum()), failure_rate=float(g.technical_failure.mean())))
    return pd.DataFrame(rows).sort_values(cols)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    start = time.time()
    os.makedirs(OUT, exist_ok=True)
    cfg = json.load(open(CONFIG, encoding="utf-8"))
    cases = load_cases()
    if args.smoke: cases = cases.head(1).copy()
    inrows = [file_record(p, r) for p, r in
              [(TECHNICAL_A, "outcome_blind_A_identifier_list"), (MANIFEST, "technical_manifest"),
               (SCANNER, "technical_scanner_map"), (AUDIT, "technical_high_signal_features_R1"),
               (PREP_METRICS, "preprocess_metrics_R1"), (CONFIG, "locked_config")]]
    for pid in cases["影像号"].astype(str):
        inrows += [file_record(os.path.join(PREP, pid, "R1_image.nrrd"), "R1_preprocessed_image"),
                   file_record(os.path.join(PREP, pid, "R1_mask.nrrd"), "R1_preprocessed_mask")]
    pd.DataFrame(inrows).to_csv(os.path.join(OUT, "input_manifest.csv"), index=False, encoding="utf-8-sig")
    bases, caches, fit, allvals = [], {}, [], []
    for _, case in cases.iterrows():
        row, cache = first_pass(case, cfg)
        bases.append(row)
        if cache is not None:
            vals = cache["values"]
            fit.append(vals); allvals.append(vals); caches[str(row["影像号"])] = cache
    centers, equal = fit_primary(fit, cfg), fit_equal_case(allvals, cfg)
    lookup = {str(x["影像号"]): x for _, x in cases.iterrows()}
    df = pd.DataFrame([assign(lookup[str(r["影像号"])], r, caches.get(str(r["影像号"])), centers, equal, cfg) for r in bases])
    for c in ["肿瘤体积mm3", "R1场强", "R1厂商", "R1机型", "R1系列", "R1面内间距", "R1层厚", "R1层数", "序列名", "尺寸",
              "high_fraction", "high_lcc_voxels", "high_lcc_volume_mm3", "high_lcc_fraction",
              "muscle_mean", "muscle_label"]:
        if c in cases.columns: df = df.merge(cases[["影像号", c]], on="影像号", how="left")
    df["tumor_volume_mm3_for_strata"] = pd.to_numeric(df["肿瘤体积mm3"], errors="coerce")
    v = df["tumor_volume_mm3_for_strata"].dropna()
    if len(v) >= 4:
        bins = np.unique(np.quantile(v, [0, .25, .5, .75, 1]))
        if len(bins) >= 2:
            df["tumor_volume_quartile"] = pd.cut(df["tumor_volume_mm3_for_strata"], bins=bins, labels=False, include_lowest=True, duplicates="drop") + 1
    df.sort_values("影像号").to_csv(os.path.join(OUT, "case_diagnostics.csv"), index=False, encoding="utf-8-sig")
    df["technical_failure"] = pd.to_numeric(df["technical_failure"], errors="coerce").fillna(1).astype(int)
    n, fail = len(df), int(df["technical_failure"].sum())
    rate = float(fail / n) if n else np.nan
    decision = "PASS_LT_5_PERCENT" if n and rate < .05 else "STOP_GE_5_PERCENT"
    cnt = Counter(t for s in df["failure_types"].fillna("") for t in str(s).split(";") if t)
    pd.DataFrame([["target_cases", n], ["valid_first_pass_cases", len(fit)], ["technical_failure_cases", fail],
                  ["technical_failure_rate", rate], ["failure_threshold_exclusive", .05],
                  ["maximum_failures_at_strict_threshold", int(np.floor(.05 * n - 1e-12))],
                  ["empty_habitat_cases", cnt["empty_habitat"]], ["algorithm_failure_cases", cnt["algorithm_failure"]],
                  ["unassigned_tumor_voxel_cases", cnt["unassigned_tumor_voxels"]],
                  ["geometry_or_label_error_cases", cnt["geometry_or_label_error"]],
                  ["automatic_gate_decision", decision]], columns=["metric", "value"]).to_csv(
                      os.path.join(OUT, "failure_summary.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([["primary_unweighted_supervoxel", centers[0], centers[1], np.mean(centers) if np.isfinite(centers).all() else np.nan, len(fit), sum(len(x) for x in fit), "up_to_2000_supervoxels_per_case"],
                  ["diagnostic_equal_case_weight", equal[0], equal[1], np.mean(equal) if np.isfinite(equal).all() else np.nan, len(allvals), sum(len(x) for x in allvals), "each_case_total_weight_1"]],
                 columns=["center_type", "H_low", "H_high", "boundary_b", "fit_cases", "fit_supervoxels", "fit_case_weighting"]).to_csv(
                     os.path.join(OUT, "global_centers.csv"), index=False, encoding="utf-8-sig")
    group_failure(df, ["R1厂商", "R1机型", "R1场强", "R1系列"]).to_csv(os.path.join(OUT, "failure_by_scanner.csv"), index=False, encoding="utf-8-sig")
    group_failure(df, ["tumor_volume_quartile"]).to_csv(os.path.join(OUT, "failure_by_tumor_volume.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{"analysis_id": "A_full_technical_dry_run_shared_center_diagnostic", "n_cases": n, "reader": "R1",
                   "scale_mm": cfg["slic"]["target_scale_mm"], "spacing_mm": ";".join(map(str, cfg["preprocessing"]["target_spacing_mm"])),
                   "normalization": cfg["preprocessing"]["normalization"], "n4_enabled": cfg["preprocessing"]["n4_enabled"],
                   "k": cfg["clustering"]["k"], "random_seed": cfg["random_seed"], "outcome_columns_read": False,
                   "B_data_read": False, "fit_cases": len(fit), "fit_supervoxels": sum(len(x) for x in fit),
                   "technical_failure_cases": fail, "technical_failure_rate": rate, "automatic_gate_decision": decision,
                   "elapsed_seconds": round(time.time() - start, 3), "smoke": args.smoke}]).to_csv(
                       os.path.join(OUT, "run_manifest.csv"), index=False, encoding="utf-8-sig")
    print("A cases:", n, "valid first pass cases:", len(fit), "technical failures:", fail,
          "failure rate:", "%.6f" % rate if np.isfinite(rate) else "nan", "gate:", decision,
          "elapsed seconds:", round(time.time() - start, 1), "outputs:", OUT)


if __name__ == "__main__":
    main()
