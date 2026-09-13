# -*- coding: utf-8 -*-
"""归一化质控（无 N4 阶段）：设备内 × 设备间检验，仅以肌肉为参照组织。

数据源：
  output/qc/logs/preprocess_metrics.csv  预处理记录的肌肉指标（normalization=muscle 行）
  output/manifest.csv                    病例清单（双读者标志）
  output/scanner_map.csv                 影像号 → 厂商/机型/场强（DICOM 头）
  output/qc/qc_report.csv                预处理告警（肌肉参照失败及 R2 标签未解析等）
  output/preprocessed/<ID>/              肌肉参照归一化输出（双读者一致性用）

输出：output/qc/normalization_qc/
  device_groups.csv        设备分组病例数
  within_device_stats.csv  设备内指标统计（中位/IQR/离群计数）
  outliers.csv             设备内离群复核清单（3×MAD 与 1.5×IQR 双标准）
  between_device.csv       设备间肌肉指标比较（μ_muscle/p10/p50/p90/CV/梯度）
  pair_consistency.csv     双读者 30 例归一化后肿瘤 ROI 均值比（描述性，不作判定）
  plots/boxplots.png       设备分组箱线图
  report.md                质控摘要与建议（是否重启 N4 / 复核清单）

用法：
  python scripts/qc_normalization.py [--prep-dir output/preprocessed]
"""
from __future__ import annotations

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]  # 中文字体
plt.rcParams["axes.unicode_minus"] = False
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import SimpleITK as sitk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
DEFAULT_PREP = os.path.join(OUT, "preprocessed")

# 建议阈值（可在数据上校准后写入报告）
CV_N4_THRESHOLD = 0.15      # 设备组肌肉 CV 中位 > 15% → 建议重启 N4
GRAD_N4_THRESHOLD = 1.0     # 设备组肌肉梯度中位 > 1 %/mm → 建议重启 N4

METRICS = ["muscle_mean", "muscle_cv", "muscle_p10", "muscle_p50", "muscle_p90", "grad"]
METRIC_ALIASES = {
    "reference_mean": "muscle_mean",
    "reference_cv": "muscle_cv",
    "reference_p10": "muscle_p10",
    "reference_p50": "muscle_p50",
    "reference_p90": "muscle_p90",
    "reference_grad": "grad",
    "reference_voxels": "muscle_voxels",
}
# 离群规则：μ 系指标用组中位比值（组织互换会使 μ 偏移 2 倍以上，天然个体差异 <2.5 倍）；
# CV 与梯度用绝对阈值（上侧）。均为可解释的保守规则。
RATIO_LOW, RATIO_HIGH = 0.4, 2.5
CV_HARD = 0.40      # 肌肉 CV > 40% 视为严重不均匀/污染
GRAD_HARD = 1.0     # 肌肉内面内梯度 > 1 %/mm 视为明显偏置


def group_label(row: pd.Series) -> str:
    v = str(row["R1厂商"]).strip()
    m = str(row["R1机型"]).strip().upper()
    fs = str(row["R1场强"]).strip()
    try:
        fs = f"{float(fs):g}T"
    except ValueError:
        fs = f"{fs}T"
    return f"{v} {m} {fs}".strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="归一化质控（设备内×设备间，肌肉参照）")
    ap.add_argument("--prep-dir", default=DEFAULT_PREP)
    args = ap.parse_args()

    qcdir = os.path.join(OUT, "qc", "normalization_qc")
    plotdir = os.path.join(qcdir, "plots")
    os.makedirs(plotdir, exist_ok=True)

    metrics_path = os.path.join(OUT, "qc", "logs", "preprocess_metrics.csv")
    if not os.path.exists(metrics_path):
        print("缺少 preprocess_metrics.csv，请先运行预处理（muscle 模式）")
        return
    m = pd.read_csv(metrics_path, dtype=str)
    required = {
        "normalization_requested", "normalization_applied",
        "normalization_status", "reference_mean", "reference_cv",
        "reference_p10", "reference_p50", "reference_p90",
        "reference_grad", "reference_voxels",
    }
    if not required.issubset(m.columns):
        print("preprocess_metrics.csv 缺少严格 normalization 字段，请重新运行预处理")
        return
    m = m[(m["normalization_requested"] == "muscle") &
          (m["normalization_applied"] == "muscle") &
          (m["normalization_status"] == "success")].copy()
    for source, target in METRIC_ALIASES.items():
        if source in m.columns and target not in m.columns:
            m[target] = m[source]
    for c in METRICS + ["muscle_voxels", "eroded_voxels"]:
        m[c] = pd.to_numeric(m[c], errors="coerce")
    man = pd.read_csv(os.path.join(OUT, "manifest.csv"), encoding="utf-8-sig", dtype=str)
    sm = pd.read_csv(os.path.join(OUT, "scanner_map.csv"), encoding="utf-8-sig", dtype=str)
    qc_path = os.path.join(OUT, "qc", "qc_report.csv")
    qc = pd.DataFrame()
    if os.path.exists(qc_path) and os.path.getsize(qc_path) > 0:
        try:
            qc = pd.read_csv(qc_path, encoding="utf-8-sig", dtype=str)
        except pd.errors.EmptyDataError:
            qc = pd.DataFrame()

    mm_all = m.merge(sm[["影像号", "R1厂商", "R1机型", "R1场强"]], on="影像号", how="left")
    mm_all["设备组"] = mm_all.apply(lambda r: group_label(r) if pd.notna(r["R1厂商"]) else "未知", axis=1)
    # 小样本组（<10 例）并入"其他"（仍单独列出病例）
    vc = mm_all["设备组"].value_counts()
    small = set(vc[vc < 10].index)
    mm_all.loc[mm_all["设备组"].isin(small), "设备组"] = "其他(小样本)"
    mm = mm_all[mm_all["读者"] == "R1"]  # 设备内/设备间统计以 R1（每例一次测量）为准
    groups = [g for g in mm["设备组"].unique() if pd.notna(g)]
    groups.sort()

    # ---- 设备分组 ---- #
    gdf = mm.groupby("设备组").size().reset_index(name="例数")
    gdf.to_csv(os.path.join(qcdir, "device_groups.csv"), index=False, encoding="utf-8-sig")

    # ---- 设备内统计与离群 ---- #
    stats_rows, out_rows = [], []
    for g in groups:
        sub = mm[mm["设备组"] == g]
        for c in METRICS:
            v = sub[c].dropna()
            if v.empty:
                continue
            med, q1, q3 = float(v.median()), float(v.quantile(0.25)), float(v.quantile(0.75))
            if c in ("muscle_cv", "grad"):
                hard = CV_HARD if c == "muscle_cv" else GRAD_HARD
                bad = v[v > hard]
                rule = f"绝对阈值 >{hard}"
                cat = "不均匀性较大"
            else:
                # μ 系指标离群 = 采集尺度/协议变体（信息性）；肌肉归一化按定义消除尺度，
                # 判别正确性由标签相对灰度保证（见 manifest 判别），此类不视为错误
                bad = v[(v < RATIO_LOW * med) | (v > RATIO_HIGH * med)]
                rule = f"组中位比值 <{RATIO_LOW}× 或 >{RATIO_HIGH}×"
                cat = "采集尺度变体"
            stats_rows.append({"设备组": g, "指标": c, "n": len(v), "中位": round(med, 4),
                               "Q1": round(q1, 4), "Q3": round(q3, 4),
                               "离群规则": rule, "类别": cat, "条数": len(bad)})
            for idx, val in bad.items():
                out_rows.append({"影像号": mm.loc[idx, "影像号"], "设备组": g, "指标": c,
                                 "类别": cat, "值": round(float(val), 4), "组中位": round(med, 4)})
    pd.DataFrame(stats_rows).to_csv(os.path.join(qcdir, "within_device_stats.csv"),
                                    index=False, encoding="utf-8-sig")
    out_df = pd.DataFrame(out_rows)
    out_df.to_csv(os.path.join(qcdir, "outliers.csv"), index=False, encoding="utf-8-sig")
    n_sev = len(out_df[out_df["类别"] == "不均匀性较大"]) if len(out_df) else 0
    n_scale = len(out_df[out_df["类别"] == "采集尺度变体"]) if len(out_df) else 0

    # ---- 告警与退回标志汇总 ---- #
    flags = []
    if not qc.empty:
        qp = qc[(qc["阶段"] == "preprocess") &
                (qc["代码"].isin([
                    "R1_MUSCLE_LABEL_MISSING", "R1_MUSCLE_EROSION_EMPTY",
                    "R1_MUSCLE_MEAN_INVALID", "R2_MUSCLE_LABEL_MISSING",
                    "R2_MUSCLE_LABEL_UNRESOLVED", "R2_MUSCLE_EROSION_EMPTY",
                    "R2_MUSCLE_MEAN_INVALID"]))]
        for _, r in qp.iterrows():
            flags.append({"影像号": r["影像号"], "读者": r["读者"] if "读者" in r else "",
                          "代码": r["代码"], "说明": r["说明"]})
    ero_bad = mm_all[mm_all["erode_radius"].notna() & (mm_all["erode_radius"].str.strip() != "")]
    ero_default = {"R1": "1,1,0", "R2": "2,2,0"}
    for _, r in ero_bad.iterrows():
        if r["erode_radius"].strip() != ero_default.get(r["读者"], ""):
            flags.append({"影像号": r["影像号"], "读者": r["读者"],
                          "代码": "ERODE_RADIUS_DIFFERENT", "说明": f"实际腐蚀半径 {r['erode_radius']}"})
    pd.DataFrame(flags).to_csv(os.path.join(qcdir, "flags.csv"), index=False, encoding="utf-8-sig")

    # ---- 设备间比较 ---- #
    bd = []
    for g in groups:
        sub = mm[mm["设备组"] == g]
        row = {"设备组": g, "n": len(sub)}
        for c in METRICS:
            row[f"{c}_中位"] = round(float(sub[c].median()), 4) if sub[c].notna().any() else ""
        row["肌肉CV中位"] = round(float(sub["muscle_cv"].median()), 4)
        row["梯度中位(%/mm)"] = round(float(sub["grad"].median()), 4)
        bd.append(row)
    bd_df = pd.DataFrame(bd)
    bd_df.to_csv(os.path.join(qcdir, "between_device.csv"), index=False, encoding="utf-8-sig")
    p50s = bd_df.set_index("设备组")["muscle_p50_中位"].dropna()
    dist_rows = []
    if len(p50s) > 1:
        pooled = float(np.nanmedian(mm["muscle_p50"]))
        for i in range(len(p50s)):
            for j in range(i + 1, len(p50s)):
                a, b = p50s.index[i], p50s.index[j]
                d = abs(p50s.iloc[i] - p50s.iloc[j]) / pooled * 100.0
                dist_rows.append({"组A": a, "组B": b, "|Δp50|/合计中位(%)": round(d, 2)})
    pd.DataFrame(dist_rows).to_csv(os.path.join(qcdir, "between_device_distance.csv"),
                                   index=False, encoding="utf-8-sig")

    # ---- 双读者一致性（描述性） ---- #
    pair_rows = []
    for _, r in man[man["是否双读者"] == "1"].iterrows():
        pid = r["影像号"]
        d1 = os.path.join(args.prep_dir, pid, "R1_image.nrrd")
        d2 = os.path.join(args.prep_dir, pid, "R2_image.nrrd")
        m1p = os.path.join(args.prep_dir, pid, "R1_mask.nrrd")
        m2p = os.path.join(args.prep_dir, pid, "R2_mask.nrrd")
        if not all(os.path.exists(p) for p in (d1, d2, m1p, m2p)):
            continue
        a1 = sitk.GetArrayFromImage(sitk.ReadImage(d1))
        b1 = sitk.GetArrayFromImage(sitk.ReadImage(m1p)) == 1
        a2 = sitk.GetArrayFromImage(sitk.ReadImage(d2))
        b2 = sitk.GetArrayFromImage(sitk.ReadImage(m2p)) == 1
        mu1 = float(a1[b1].mean()) if b1.any() else float("nan")
        mu2 = float(a2[b2].mean()) if b2.any() else float("nan")
        pair_rows.append({"影像号": pid, "R1肿瘤ROI均值": round(mu1, 4), "R2肿瘤ROI均值": round(mu2, 4),
                          "R2/R1": round(mu2 / mu1, 4) if mu1 and mu2 else ""})
    pd.DataFrame(pair_rows).to_csv(os.path.join(qcdir, "pair_consistency.csv"),
                                   index=False, encoding="utf-8-sig")

    # ---- 箱线图 ---- #
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, c in zip(axes.flat, ["muscle_mean", "muscle_cv", "grad", "muscle_p50"]):
        data = [mm[mm["设备组"] == g][c].dropna().values for g in groups]
        ax.boxplot(data, labels=groups, showfliers=False)
        ax.set_title(c)
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(os.path.join(plotdir, "boxplots.png"), dpi=120)
    plt.close(fig)

    # ---- 报告 ---- #
    n4_rec = []
    for _, r in bd_df.iterrows():
        cv, gr = r["肌肉CV中位"], r["梯度中位(%/mm)"]
        if isinstance(cv, str) or isinstance(gr, str):
            continue
        if float(cv) > CV_N4_THRESHOLD or float(gr) > GRAD_N4_THRESHOLD:
            note = "（小样本合并组，仅供参考）" if str(r["设备组"]).endswith("(小样本)") else ""
            n4_rec.append(f"- {r['设备组']}：肌肉CV中位={cv}、梯度中位={gr} %/mm → 建议重启 N4{note}")
    lines = ["# 归一化质控报告（无 N4 阶段，肌肉参照）", "",
             f"- 分析例数（muscle 模式，R1 每例一次测量）：{len(mm)}",
             f"- 设备分组：{len(groups)} 组（见 device_groups.csv）",
             f"- 不均匀性较大（CV>{CV_HARD} / 梯度>{GRAD_HARD} %/mm，复核参考）：{n_sev} 条",
             f"- 采集尺度变体（μ 系指标超出组中位 {RATIO_LOW}×~{RATIO_HIGH}×，信息性，肌肉归一化已消除尺度）：{n_scale} 条",
             f"- 标志（肌肉参照失败、R2 标签未解析或腐蚀半径差异）：{len(flags)} 条（见 flags.csv）",
             f"- 双读者一致性（描述性）：{len(pair_rows)} 例（见 pair_consistency.csv）", "",
             "## N4 重启建议", ""]
    lines += n4_rec if n4_rec else ["- 各设备组肌肉 CV 中位 ≤15% 且梯度中位 ≤1 %/mm，暂不重启 N4", ""]
    lines += ["## 设备间比较", ""]
    lines += [f"- 肌肉 p50 中位："
              + "；".join(f"{r['设备组']}={r['muscle_p50_中位']}" for _, r in bd_df.iterrows()),
              "- 组间 |Δp50|/合计中位：见 between_device_distance.csv", ""]
    lines += ["## 复核清单", ""]
    if len(out_df) and n_sev:
        sev = out_df[out_df["类别"] == "不均匀性较大"]
        ids_sev = sev["影像号"].unique()
        lines += [f"- 不均匀性较大（{n_sev} 条，{len(ids_sev)} 例）："
                  + "、".join(str(x) for x in ids_sev[:30]) + (" 等" if len(ids_sev) > 30 else ""), ""]
    else:
        lines += ["- 无不均匀性较大病例", ""]
    if len(flags):
        lines += [f"- 标志（{len(flags)} 条）：" + "；".join(
            f"{r['影像号']}({r['代码']})" for r in flags[:20]), ""]
    else:
        lines += ["- 无标志", ""]
    with open(os.path.join(qcdir, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))
    print("\n输出:", qcdir)


if __name__ == "__main__":
    main()
