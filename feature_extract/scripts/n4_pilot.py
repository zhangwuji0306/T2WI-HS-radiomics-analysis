"""N4 重启决策试点（仅前景掩膜全图校正）。

步骤（--stage all 顺序执行，可分段续跑）：
  equiv   全分辨率 vs 降采样 N4 等效性对照（5 例，原始分辨率、前景掩膜，记录耗时与校正一致性）
  prep    分层抽样（种子 12345）→ 试点 N4 预处理（肌肉 + Z-score 双臂，独立目录与指标表，
          不污染正式产物）
  features 22 对 A 内双读者 Original 特征提取（基线特征取自正式产物；N4 特征取自试点目录）
  report  配对指标（肌肉 CV/梯度/μ）、去标记率、组中位、设备间 p50 距离、22 对 ICC 对比、
          计时外推 → 决策规则判定 → output/qc/n4_decision/（sample.csv、equiv.csv、report.md、
          decision.json）

用法:
  python scripts/n4_pilot.py [--stage all|equiv|prep|features|report] [--seed 12345] [--factor 2.0]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import SimpleITK as sitk
from scipy.stats import wilcoxon

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MANIFEST = os.path.join(OUT, "manifest.csv")
SCANNER = os.path.join(OUT, "scanner_map.csv")
OUTLIERS = os.path.join(OUT, "qc", "normalization_qc", "outliers.csv")
METRICS_CANON = os.path.join(OUT, "qc", "logs", "preprocess_metrics.csv")
TIMING_ORIG = os.path.join(OUT, "qc", "logs", "features_timing.csv")
TIMING_FILT = os.path.join(OUT, "qc", "logs", "features_filtered_timing.csv")
PILOT = os.path.join(OUT, "n4pilot")
DEC = os.path.join(OUT, "qc", "n4_decision")
PREP_SCRIPT = os.path.join(ROOT, "scripts", "preprocess.py")
EXT_SCRIPT = os.path.join(ROOT, "scripts", "extract_features.py")
CV_HARD, GRAD_HARD = 0.40, 1.0
CV_MED, GRAD_MED = 0.15, 1.0
QUOTAS = [("GE MEDICAL SYSTEMS|DISCOVERY MR750|3.0", 25),
          ("GE MEDICAL SYSTEMS|OPTIMA MR360|1.5", 2),
          ("Philips Medical Systems|Multiva|1.5", 2)]
CONTROL_QUOTAS = [("GE MEDICAL SYSTEMS|DISCOVERY MR750|3.0", 6),
                  ("GE MEDICAL SYSTEMS|OPTIMA MR360|1.5", 2),
                  ("Philips Medical Systems|Multiva|1.5", 2)]


def load_frame() -> tuple[pd.DataFrame, set]:
    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    df = man.merge(sc[["影像号", "R1厂商", "R1机型", "R1场强"]], on="影像号", how="left")
    df["_f"] = pd.to_numeric(df["R1场强"], errors="coerce")
    df["device"] = (df["R1厂商"].fillna("") + "|" + df["R1机型"].fillna("") + "|" +
                    df["_f"].round(1).astype(str))
    is_a = (df["R1厂商"] == "GE MEDICAL SYSTEMS") & (df["R1机型"] == "DISCOVERY MR750") & \
           (df["_f"].round(1) == 3.0)
    df["is_a"] = is_a
    flagged = set()
    if os.path.exists(OUTLIERS):
        ol = pd.read_csv(OUTLIERS, encoding="utf-8-sig", dtype=str)
        flagged = set(ol.loc[ol["类别"] == "不均匀性较大", "影像号"])
    return df, flagged


def sample_pilot(df: pd.DataFrame, flagged: set, seed: int) -> tuple[list, list, list, list]:
    rng = random.Random(seed)
    big = {"GE MEDICAL SYSTEMS|DISCOVERY MR750|3.0",
           "GE MEDICAL SYSTEMS|OPTIMA MR360|1.5",
           "Philips Medical Systems|Multiva|1.5"}
    flagged30: list = []
    used: set = set()
    for dev, quota in QUOTAS:
        ids = sorted(x for x in flagged
                     if df.loc[df["影像号"] == x, "device"].iloc[0] == dev)
        pick = rng.sample(ids, min(quota, len(ids)))
        flagged30 += pick
        used.update(pick)
    other = sorted(x for x in flagged
                   if df.loc[df["影像号"] == x, "device"].iloc[0] not in big)
    if other:
        flagged30.append(other[0])
        used.add(other[0])
    pairs = sorted(df.loc[(df["is_a"]) & (df["是否双读者"] == "1"), "影像号"])
    used.update(pairs)
    controls: list = []
    for dev, quota in CONTROL_QUOTAS:
        pool = sorted(x for x in df["影像号"]
                      if x not in used and x not in flagged and
                      df.loc[df["影像号"] == x, "device"].iloc[0] == dev)
        controls += rng.sample(pool, min(quota, len(pool)))
        used.update(controls)
    return flagged30, pairs, controls, sorted(used)


def run_prep(ids: list, norm: str) -> None:
    cmd = [sys.executable, PREP_SCRIPT, "--n4", "--ids", ",".join(ids),
           "--normalize", norm,
           "--prep-dir", os.path.join(PILOT, "preprocessed" if norm == "muscle"
                                      else "preprocessed_zscore"),
           "--metrics-csv", os.path.join(PILOT, f"metrics_{norm}.csv"),
           "--timing-csv", os.path.join(PILOT, f"timing_{norm}.csv")]
    print(f"[prep] N4 预处理（{norm}，{len(ids)} 例）...")
    subprocess.run(cmd, check=True)


def run_features(ids: list, norm: str) -> None:
    cmd = [sys.executable, EXT_SCRIPT, "--norm", norm, "--f", "0.25",
           "--ids", ",".join(ids), "--workers", "2",
           "--prep-dir", os.path.join(PILOT, "preprocessed" if norm == "muscle"
                                      else "preprocessed_zscore"),
           "--out-root", os.path.join(PILOT, "features")]
    print(f"[features] 试点特征提取（{norm} f=0.25，{len(ids)} 例）...")
    subprocess.run(cmd, check=True)


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def icc21(pivot: pd.DataFrame) -> float:
    """ICC(2,1)：two-way random, absolute agreement, single measures（Shrout-Fleiss）。"""
    pivot = pivot.dropna()
    n, k = pivot.shape
    if n < 3 or k < 2:
        return float("nan")
    grand = float(pivot.values.mean())
    ss_subj = k * float(((pivot.mean(axis=1) - grand) ** 2).sum())
    ss_rater = n * float(((pivot.mean(axis=0) - grand) ** 2).sum())
    ss_total = float(((pivot - grand) ** 2).values.sum())
    ss_err = max(ss_total - ss_subj - ss_rater, 0.0)
    ms_subj = ss_subj / (n - 1)
    ms_rater = ss_rater / (k - 1)
    ms_err = max(ss_err / ((n - 1) * (k - 1)), 1e-12)
    return (ms_subj - ms_err) / (ms_subj + (k - 1) * ms_err + k * (ms_rater - ms_err) / n)


def feature_icc(feat_csv: str, pairs: list, meta_cols: list) -> pd.DataFrame:
    feats = pd.read_csv(feat_csv, dtype={"影像号": str})
    feats = feats[feats["影像号"].isin(pairs) & feats["读者"].isin(["R1", "R2"])]
    rows = []
    for col in feats.columns:
        if col in meta_cols:
            continue
        piv = feats.pivot(index="影像号", columns="读者", values=col)
        rows.append({"feature": col, "icc": icc21(piv), "n_pairs": int(piv.dropna().shape[0])})
    return pd.DataFrame(rows)


def stage_equiv(df: pd.DataFrame, pilot_ids: list, factor: float) -> pd.DataFrame:
    import preprocess
    ids = sorted(pilot_ids)[:5]
    rows = []
    for pid in ids:
        row = df.loc[df["影像号"] == pid].iloc[0]
        img = sitk.ReadImage(os.path.join(ROOT, row["图像文件"]))
        m_img = sitk.ReadImage(os.path.join(ROOT, row["掩膜文件"]))
        m_arr = sitk.GetArrayFromImage(m_img)
        fm = preprocess.foreground_mask(img)
        t0 = time.perf_counter()
        cf = preprocess.n4_correct(img, fm, factor=1.0)
        tf = time.perf_counter() - t0
        t0 = time.perf_counter()
        cd = preprocess.n4_correct(img, fm, factor=factor)
        td = time.perf_counter() - t0
        mf = preprocess.muscle_stats(cf, m_arr, 3, [1, 1, 0])
        md = preprocess.muscle_stats(cd, m_arr, 3, [1, 1, 0])
        af = sitk.GetArrayFromImage(cf).astype(np.float64)
        ad = sitk.GetArrayFromImage(cd).astype(np.float64)
        fm_a = sitk.GetArrayFromImage(fm) == 1
        r = float(np.corrcoef(af[fm_a], ad[fm_a])[0, 1]) if fm_a.sum() > 10 else float("nan")
        rows.append({"影像号": pid,
                     "corr_foreground": round(r, 6),
                     "cv_full": mf.get("cv"), "cv_down": md.get("cv"),
                     "grad_full": mf.get("grad"), "grad_down": md.get("grad"),
                     "n4_sec_full": round(tf, 2), "n4_sec_down": round(td, 2),
                     "speedup": round(tf / td, 1) if td > 0 else float("nan")})
        print(f"[equiv] {pid}: corr={r:.4f}  CV {mf.get('cv')}→{md.get('cv')}  "
              f"N4 {tf:.1f}s→{td:.1f}s（×{tf / td:.1f}）")
    eq = pd.DataFrame(rows)
    eq.to_csv(os.path.join(DEC, "equiv.csv"), index=False, encoding="utf-8-sig")
    return eq


def stage_report(df: pd.DataFrame, pilot_ids: list, flagged30: list, pairs: list,
                 controls: list, factor: float) -> None:
    os.makedirs(DEC, exist_ok=True)
    lines: list[str] = []
    def L(s: str = "") -> None:
        lines.append(s)
        print(s)

    # ---- 配对指标（R1, muscle）----
    canon = pd.read_csv(METRICS_CANON, dtype=str)
    canon = canon[(canon["读者"] == "R1") & (canon["normalization"] == "muscle")]
    canon = canon[canon["影像号"].isin(pilot_ids)].set_index("影像号")
    pil = pd.read_csv(os.path.join(PILOT, "metrics_muscle.csv"), dtype=str)
    pil = pil[(pil["读者"] == "R1") & (pil["normalization"] == "muscle")]
    pil = pil[pil["影像号"].isin(pilot_ids)].set_index("影像号")
    common = sorted(set(canon.index) & set(pil.index))
    cv_b = pd.to_numeric(canon.loc[common, "muscle_cv"], errors="coerce")
    cv_a = pd.to_numeric(pil.loc[common, "muscle_cv"], errors="coerce")
    gr_b = pd.to_numeric(canon.loc[common, "grad"], errors="coerce")
    gr_a = pd.to_numeric(pil.loc[common, "grad"], errors="coerce")
    mu_b = pd.to_numeric(canon.loc[common, "muscle_mean"], errors="coerce")
    mu_a = pd.to_numeric(pil.loc[common, "muscle_mean"], errors="coerce")
    pair = pd.DataFrame({"影像号": common, "cv_before": cv_b.values, "cv_after": cv_a.values,
                         "grad_before": gr_b.values, "grad_after": gr_a.values,
                         "mu_before": mu_b.values, "mu_after": mu_a.values}).set_index("影像号")
    pair.to_csv(os.path.join(DEC, "paired_metrics.csv"), index=False, encoding="utf-8-sig")
    d = pair.dropna(subset=["cv_before", "cv_after"])
    med_cv_b, med_cv_a = float(d["cv_before"].median()), float(d["cv_after"].median())
    med_gr_b, med_gr_a = float(d["grad_before"].median()), float(d["grad_after"].median())
    cv_delta = (pd.to_numeric(d["cv_after"], errors="coerce") -
                pd.to_numeric(d["cv_before"], errors="coerce"))
    gr_delta = (pd.to_numeric(d["grad_after"], errors="coerce") -
                pd.to_numeric(d["grad_before"], errors="coerce"))
    dg = pair.dropna(subset=["grad_before", "grad_after"])
    p_cv = wilcoxon(d["cv_before"], d["cv_after"]).pvalue if len(d) >= 6 else float("nan")
    p_gr = wilcoxon(dg["grad_before"], dg["grad_after"]).pvalue if len(dg) >= 6 else float("nan")
    mu_ratio = pd.to_numeric(pair["mu_after"], errors="coerce") / \
        pd.to_numeric(pair["mu_before"], errors="coerce")

    # ---- 去标记率（30 例分层样本）----
    fl = pair.index.intersection(flagged30)
    fl_df = pair.loc[fl].dropna(subset=["cv_after", "grad_after"])
    n_fixed = int(((fl_df["cv_after"] <= CV_HARD) & (fl_df["grad_after"] <= GRAD_HARD)).sum())
    rate = n_fixed / len(fl_df) if len(fl_df) else float("nan")
    lo, hi = wilson_ci(n_fixed, len(fl_df))

    # ---- 组中位（MR750 为主）----
    mr750 = [x for x in common if df.loc[df["影像号"] == x, "device"].iloc[0]
             == "GE MEDICAL SYSTEMS|DISCOVERY MR750|3.0"]
    mcv_b = float(d.loc[d.index.intersection(mr750), "cv_before"].median())
    mcv_a = float(d.loc[d.index.intersection(mr750), "cv_after"].median())

    # ---- 设备间 p50 距离（MR750 vs 其余）----
    def p50dist(metrics: pd.DataFrame, ids: list) -> float:
        m = metrics[metrics.index.isin(ids)]
        a = pd.to_numeric(m.loc[m.index.isin(mr750), "muscle_p50"], errors="coerce")
        b = pd.to_numeric(m.loc[~m.index.isin(mr750), "muscle_p50"], errors="coerce")
        return float(abs(a.mean() - b.mean())) if len(a) and len(b) else float("nan")
    d50_b = p50dist(canon, common)
    d50_a = p50dist(pil, common)

    # ---- 22 对 ICC（Original 特征，f=0.25）----
    meta = ["影像号", "读者", "split", "normalization", "f", "binWidth"]
    icc_rows = []
    for norm, sub in (("muscle", ""), ("zscore", "")):
        base_csv = os.path.join(OUT, "features", f"{norm}_f0.25", "features_original.csv")
        pil_csv = os.path.join(PILOT, "features", f"{norm}_f0.25", "features_original.csv")
        b = feature_icc(base_csv, pairs, meta).rename(columns={"icc": "icc_before"})
        a = feature_icc(pil_csv, pairs, meta).rename(columns={"icc": "icc_after"})
        m = b.merge(a, on="feature")
        m["norm"] = norm
        icc_rows.append(m)
    icc = pd.concat(icc_rows, ignore_index=True)
    icc.to_csv(os.path.join(DEC, "icc_before_after.csv"), index=False, encoding="utf-8-sig")
    icc_ok = icc.dropna(subset=["icc_before", "icc_after"])
    icc_sum = icc_ok.groupby("norm").agg(
        n=("feature", "count"),
        pass_before=("icc_before", lambda s: int((s > 0.75).sum())),
        pass_after=("icc_after", lambda s: int((s > 0.75).sum())),
        mean_before=("icc_before", "mean"), mean_after=("icc_after", "mean"),
        median_before=("icc_before", "median"), median_after=("icc_after", "median")).reset_index()

    # ---- 计时外推 ----
    tim = pd.read_csv(os.path.join(PILOT, "timing_muscle.csv"), dtype=str)
    tim["total"] = pd.to_numeric(tim["total"], errors="coerce")
    tim["n4"] = pd.to_numeric(tim["n4"], errors="coerce")
    t_r1 = tim.loc[tim["读者"] == "R1", "total"].dropna()
    t_r2 = tim.loc[tim["读者"] == "R2", "total"].dropna()
    n4_r1 = tim.loc[tim["读者"] == "R1", "n4"].dropna()
    n4_s = f"{n4_r1.mean():.1f}（中位 {n4_r1.median():.1f}，最大 {n4_r1.max():.1f}）"
    # 全量重跑外推：R1 693 例 + R2 30 例（双臂）
    prep_h = (693 * t_r1.mean() + 30 * t_r2.mean()) / 3600
    prep_h *= 2  # 双臂（muscle + zscore）
    def wall(f_csv: str, combos: int) -> float:
        t = pd.read_csv(f_csv, dtype=str)
        s = pd.to_numeric(t["seconds"], errors="coerce").mean()
        return s * 723 * combos / 2 / 3600 if s == s else float("nan")
    orig_h = wall(TIMING_ORIG, 4)
    filt_h = wall(TIMING_FILT, 4)
    total_h = prep_h + 3 / 60 + orig_h + filt_h + 5 / 60

    # ---- 决策规则（全部满足才重启）----
    c1 = bool((rate >= 0.70) or (mcv_a < CV_MED))
    c2 = bool((0.95 <= float(mu_ratio.median()) <= 1.05) and (d50_a <= d50_b + 1e-9))
    c3 = bool((icc_sum["pass_after"] >= icc_sum["pass_before"]).all()) if len(icc_sum) else False
    c4 = bool(total_h <= 10)
    decision = "重启" if (c1 and c2 and c3 and c4) else "不重启（证据不足或存在退化风险）"

    L("# N4 重启决策试点报告")
    L()
    L(f"- 试点规模：不均匀性较大 30 例（设备分层，种子 12345）＋ A 内双读者 {len(pairs)} 对 ＋ "
      f"未标记对照 {len(controls)} 例，去重后 {len(pilot_ids)} 例")
    L(f"- N4 方案：仅前景掩膜全图校正，降采样因子 {factor:g}（等效性见下）")
    L()
    L("## 1. 全分辨率 vs 降采样等效性（5 例）")
    L()
    L("| 影像号 | 前景内相关性 | CV 全→降 | 梯度 全→降 | 耗时 全→降 (s) | 加速比 |")
    L("|---|---|---|---|---|---|")
    eq = pd.read_csv(os.path.join(DEC, "equiv.csv"), dtype={"影像号": str})
    for _, r in eq.iterrows():
        L(f"| {r['影像号']} | {float(r['corr_foreground']):.4f} | "
          f"{float(r['cv_full']):.4f}→{float(r['cv_down']):.4f} | "
          f"{float(r['grad_full']):.3f}→{float(r['grad_down']):.3f} | "
          f"{float(r['n4_sec_full']):.1f}→{float(r['n4_sec_down']):.1f} | ×{float(r['speedup']):.1f} |")
    L()
    L("## 2. 配对指标（N4 前后，同例）")
    L()
    L(f"- 肌肉 CV：中位 {med_cv_b:.3f} → {med_cv_a:.3f}，差值中位 {cv_delta.median():+.4f}"
      f"（配对 Wilcoxon p={p_cv:.4g}）")
    L(f"- 面内梯度：中位 {med_gr_b:.3f} → {med_gr_a:.3f} %/mm，差值中位 {gr_delta.median():+.4f}"
      f"（p={p_gr:.4g}）")
    L(f"- μ_muscle 比值（后/前）：中位 {mu_ratio.median():.4f}（0.95–1.05 判定阈值）")
    L(f"- 设备间 p50 距离（MR750 vs 其余）：{d50_b:.4f} → {d50_a:.4f}")
    L(f"- 去标记率（30 例，CV≤{CV_HARD} 且梯度≤{GRAD_HARD}）：{n_fixed}/{len(fl_df)} = "
      f"{rate * 100:.1f}%（95%CI {lo * 100:.1f}–{hi * 100:.1f}%）")
    L(f"- MR750 组中位 CV：{mcv_b:.3f} → {mcv_a:.3f}（< {CV_MED} 判定阈值）")
    L()
    L("## 3. 22 对双读者 ICC（Original 107 特征，f=0.25）")
    L()
    L("| 通路 | 特征数 | ICC>0.75 通过 前→后 | 平均 ICC 前→后 | 中位 ICC 前→后 |")
    L("|---|---|---|---|---|")
    for _, r in icc_sum.iterrows():
        L(f"| {r['norm']} | {r['n']} | {r['pass_before']}→{r['pass_after']} | "
          f"{r['mean_before']:.3f}→{r['mean_after']:.3f} | {r['median_before']:.3f}→{r['median_after']:.3f} |")
    L()
    L("## 4. 计时与全量重跑成本")
    L()
    L(f"- 试点 N4 单例耗时：{n4_s} s（前景掩膜全图校正，降采样 ×{factor:g}）")
    L("- 全量重跑预估：预处理双臂 {:.1f} h ＋ σ_A 重算 0.1 h ＋ Original 特征 {:.1f} h ＋ "
      "Wavelet/LoG 特征 {:.1f} h ＋ 质控 0.1 h ≈ **{:.1f} h**".format(prep_h, orig_h, filt_h, total_h))
    L()
    L("## 5. 决策规则判定（全部满足才重启）")
    L()
    L(f"- 规则1（去标记率≥70% 或 MR750 组中位 CV<{CV_MED}）：{'满足' if c1 else '不满足'}")
    L(f"- 规则2（μ 比值 0.95–1.05 且设备间 p50 距离不增大）：{'满足' if c2 else '不满足'}")
    L(f"- 规则3（ICC>0.75 通过数不下降）：{'满足' if c3 else '不满足'}")
    L(f"- 规则4（重跑 ≤ 10 h）：{'满足' if c4 else '不满足'}")
    L()
    L(f"**决策：{decision}**")
    L()
    L("## 6. 备注")
    L()
    L("- 试点产物与正式产物完全隔离（output/n4pilot/）；本记录为正式方案偏离/重启的依据。")
    L("- 若重启：全量 `--n4 --force` 重跑预处理（PIPELINE_VERSION 升 v5）、重算 σ_A 与 σ_A(filt)、"
      "重提取全部 4 组合 × 3 批次特征并重做阶段六；若否决：本报告作为方案偏离的正式记录，"
      "最终报告中讨论残余偏置场对纹理特征的潜在影响。")
    with open(os.path.join(DEC, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    json.dump({"decision": decision, "deflag_rate": None if rate != rate else rate,
               "deflag_ci": [None if lo != lo else lo, None if hi != hi else hi],
               "med_cv_before": med_cv_b, "med_cv_after": med_cv_a,
               "cv_delta_median": float(cv_delta.median()),
               "med_grad_before": med_gr_b, "med_grad_after": med_gr_a,
               "grad_delta_median": float(gr_delta.median()),
               "mu_ratio_median": float(mu_ratio.median()),
               "p50_dist_before": d50_b, "p50_dist_after": d50_a,
               "mr750_med_cv_after": mcv_a,
               "icc": icc_sum.to_dict("records"),
               "rerun_hours": total_h, "n4_sec": n4_s,
               "criteria": {"c1": c1, "c2": c2, "c3": c3, "c4": c4}},
              open(os.path.join(DEC, "decision.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2, allow_nan=True)
    L(f"\n已写入 {DEC}")


def main() -> None:
    ap = argparse.ArgumentParser(description="N4 重启决策试点")
    ap.add_argument("--stage", default="all", choices=["all", "equiv", "prep", "features", "report"])
    ap.add_argument("--seed", type=int, default=12345)
    ap.add_argument("--factor", type=float, default=2.0)
    args = ap.parse_args()

    os.makedirs(PILOT, exist_ok=True)
    os.makedirs(DEC, exist_ok=True)
    df, flagged = load_frame()
    flagged30, pairs, controls, pilot_ids = sample_pilot(df, flagged, args.seed)
    if not os.path.exists(os.path.join(DEC, "sample.csv")):
        pd.DataFrame([{"影像号": x,
                       "类别": ("flagged30" if x in flagged30 else
                                "pair" if x in pairs else "control"),
                       "设备组": df.loc[df["影像号"] == x, "device"].iloc[0]}
                      for x in pilot_ids]).to_csv(
            os.path.join(DEC, "sample.csv"), index=False, encoding="utf-8-sig")
    print(f"试点集 {len(pilot_ids)} 例（flagged30={len(flagged30)}，pairs={len(pairs)}，"
          f"controls={len(controls)}）")

    if args.stage in ("all", "equiv"):
        stage_equiv(df, pilot_ids, args.factor)
    if args.stage in ("all", "prep"):
        run_prep(pilot_ids, "muscle")
        run_prep(pilot_ids, "zscore")
    if args.stage in ("all", "features"):
        run_features(pairs, "muscle")
        run_features(pairs, "zscore")
    if args.stage in ("all", "report"):
        stage_report(df, pilot_ids, flagged30, pairs, controls, args.factor)


if __name__ == "__main__":
    main()
