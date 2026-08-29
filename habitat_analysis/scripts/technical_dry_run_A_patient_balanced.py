"""Outcome-blind A=393 validation for the selected patient-balanced M1."""
from __future__ import annotations

import json
import os
import time
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

import technical_dry_run_A as base


OUT = os.path.join(base.HAB, "output", "feasibility_A_patient_balanced")


def fit_patient_balanced(chunks, cfg):
    chunks = [np.asarray(x, dtype=float) for x in chunks if len(x)]
    x = np.concatenate(chunks)
    weights = np.concatenate([np.full(len(z), 1.0 / len(z)) for z in chunks])
    c = cfg["clustering"]
    model = KMeans(n_clusters=int(c["k"]), init=c["initialization"],
                   n_init=int(c["n_init"]), max_iter=int(c["max_iter"]),
                   tol=float(c["tol"]), random_state=int(cfg["random_seed"]))
    model.fit(x.reshape(-1, 1), sample_weight=weights)
    return np.sort(model.cluster_centers_.ravel()), int(len(chunks)), int(len(x))


def main():
    start = time.time()
    os.makedirs(OUT, exist_ok=True)
    with open(base.CONFIG, encoding="utf-8") as handle:
        cfg = json.load(handle)
    cases = base.load_cases()
    if len(cases) != 393:
        raise RuntimeError("expected 393 A cases, got %d" % len(cases))
    input_paths = [
        (base.A_TABLE, "A_identifier_list_only"),
        (base.MANIFEST, "technical_manifest"),
        (base.SCANNER, "technical_scanner_map"),
        (base.AUDIT, "technical_high_signal_features_R1"),
        (base.PREP_METRICS, "preprocess_metrics_R1"),
        (base.CONFIG, "locked_config"),
    ]
    inrows = [base.file_record(path, role) for path, role in input_paths]
    bases, caches, fit = [], {}, []
    for _, case in cases.iterrows():
        row, cache = base.first_pass(case, cfg)
        bases.append(row)
        if cache is not None:
            fit.append(cache["values"])
            caches[str(row["影像号"])] = cache
        pid = str(case["影像号"])
        inrows += [base.file_record(os.path.join(base.PREP, pid, "R1_image.nrrd"), "R1_preprocessed_image"),
                   base.file_record(os.path.join(base.PREP, pid, "R1_mask.nrrd"), "R1_preprocessed_mask")]
    pd.DataFrame(inrows).to_csv(os.path.join(OUT, "input_manifest.csv"), index=False, encoding="utf-8-sig")
    centers, fit_cases, fit_supervoxels = fit_patient_balanced(fit, cfg)
    lookup = {str(x["影像号"]): x for _, x in cases.iterrows()}
    empty_equal = np.full(2, np.nan)
    df = pd.DataFrame([
        base.assign(lookup[str(r["影像号"])], r, caches.get(str(r["影像号"])),
                    centers, empty_equal, cfg)
        for r in bases
    ])
    merge_cols = ["肿瘤体积mm3", "R1场强", "R1厂商", "R1机型", "R1系列",
                  "R1面内间距", "R1层厚", "R1层数", "序列名", "尺寸",
                  "high_fraction", "high_lcc_voxels", "high_lcc_volume_mm3",
                  "high_lcc_fraction", "muscle_mean", "muscle_label"]
    for col in merge_cols:
        if col in cases.columns:
            df = df.merge(cases[["影像号", col]], on="影像号", how="left")
    df["tumor_volume_mm3_for_strata"] = pd.to_numeric(df["肿瘤体积mm3"], errors="coerce")
    volume = df["tumor_volume_mm3_for_strata"].dropna()
    if len(volume) >= 4:
        bins = np.unique(np.quantile(volume, [0, .25, .5, .75, 1]))
        if len(bins) >= 2:
            df["tumor_volume_quartile"] = pd.cut(
                df["tumor_volume_mm3_for_strata"], bins=bins, labels=False,
                include_lowest=True, duplicates="drop") + 1
    df.sort_values("影像号").to_csv(os.path.join(OUT, "case_diagnostics.csv"), index=False, encoding="utf-8-sig")
    df["technical_failure"] = pd.to_numeric(df["technical_failure"], errors="coerce").fillna(1).astype(int)
    n, failures = len(df), int(df["technical_failure"].sum())
    rate = float(failures / n) if n else np.nan
    decision = "PASS_LT_5_PERCENT" if n and rate < .05 else "STOP_GE_5_PERCENT"
    counts = Counter(t for value in df["failure_types"].fillna("")
                     for t in str(value).split(";") if t)
    pd.DataFrame([
        ["target_cases", n], ["valid_first_pass_cases", len(fit)],
        ["technical_failure_cases", failures], ["technical_failure_rate", rate],
        ["failure_threshold_exclusive", .05],
        ["maximum_failures_at_strict_threshold", int(np.floor(.05 * n - 1e-12))],
        ["empty_habitat_cases", counts["empty_habitat"]],
        ["algorithm_failure_cases", counts["algorithm_failure"]],
        ["unassigned_tumor_voxel_cases", counts["unassigned_tumor_voxels"]],
        ["geometry_or_label_error_cases", counts["geometry_or_label_error"]],
        ["automatic_gate_decision", decision],
    ], columns=["metric", "value"]).to_csv(
        os.path.join(OUT, "failure_summary.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{
        "center_type": "M1_patient_balanced_all_supervoxels",
        "H_low": centers[0], "H_high": centers[1],
        "boundary_b": float(np.mean(centers)), "fit_cases": fit_cases,
        "fit_supervoxels": fit_supervoxels, "fit_case_weighting": "each_case_total_weight_1",
    }]).to_csv(os.path.join(OUT, "global_centers.csv"), index=False, encoding="utf-8-sig")
    base.group_failure(df, ["R1厂商", "R1机型", "R1场强", "R1系列"]).to_csv(
        os.path.join(OUT, "failure_by_scanner.csv"), index=False, encoding="utf-8-sig")
    base.group_failure(df, ["tumor_volume_quartile"]).to_csv(
        os.path.join(OUT, "failure_by_tumor_volume.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame([{
        "analysis_id": "A_full_M1_patient_balanced_technical_validation",
        "n_cases": n, "reader": "R1", "scale_mm": cfg["slic"]["target_scale_mm"],
        "spacing_mm": ";".join(map(str, cfg["preprocessing"]["target_spacing_mm"])),
        "normalization": cfg["preprocessing"]["normalization"],
        "n4_enabled": cfg["preprocessing"]["n4_enabled"], "k": cfg["clustering"]["k"],
        "random_seed": cfg["random_seed"], "outcome_columns_read": False,
        "B_data_read": False, "fit_cases": fit_cases,
        "fit_supervoxels": fit_supervoxels, "technical_failure_cases": failures,
        "technical_failure_rate": rate, "automatic_gate_decision": decision,
        "elapsed_seconds": round(time.time() - start, 3), "smoke": False,
    }]).to_csv(os.path.join(OUT, "run_manifest.csv"), index=False, encoding="utf-8-sig")
    print("A cases:", n, "valid first pass cases:", len(fit),
          "technical failures:", failures, "failure rate:", "%.6f" % rate,
          "gate:", decision, "elapsed seconds:", round(time.time() - start, 1),
          "outputs:", OUT)


if __name__ == "__main__":
    main()
