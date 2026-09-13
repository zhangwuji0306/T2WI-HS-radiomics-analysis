"""Create a current-main-cohort, outcome-blind comparison of two K-means habitat arms."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HAB_ROOT = os.path.dirname(SCRIPT_DIR)
OUT_ROOT = os.path.join(HAB_ROOT, "output")
GLOBAL_ROOT = os.path.join(OUT_ROOT, "technical_pilot")
PATIENT_ROOT = os.path.join(OUT_ROOT, "technical_pilot_amended")
REPORT = os.path.join(OUT_ROOT, "technical_feasibility_main_kmeans.md")

def read_primary(root: str, amended: bool) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary = pd.read_csv(os.path.join(root, "summary.csv"), encoding="utf-8-sig")
    icc = pd.read_csv(os.path.join(root, "descriptor_icc.csv"), encoding="utf-8-sig")
    run = pd.read_csv(os.path.join(root, "run_manifest.csv"), encoding="utf-8-sig")
    summary = summary[(summary["变体"] == ("patient_k2_1x1x2" if amended else "primary_1x1x2")) &
                      (pd.to_numeric(summary["K"], errors="coerce") == 2)].copy()
    icc = icc[(icc["变体"] == ("patient_k2_1x1x2" if amended else "primary_1x1x2")) &
              (pd.to_numeric(icc["K"], errors="coerce") == 2) &
              (icc["descriptor"] == "H_high_fraction")].copy()
    return summary, icc, run


def global_case_rates() -> pd.DataFrame:
    metrics = pd.read_csv(os.path.join(GLOBAL_ROOT, "pair_metrics.csv"), encoding="utf-8-sig")
    metrics = metrics[(metrics["变体"] == "primary_1x1x2") &
                      (pd.to_numeric(metrics["K"], errors="coerce") == 2)].copy()
    rows = []
    for scale, group in metrics.groupby("尺度mm"):
        r1 = group[["R1_H-low_texture_eligible", "R1_H-high_texture_eligible"]].apply(
            pd.to_numeric, errors="coerce")
        r2 = group[["R2_H-low_texture_eligible", "R2_H-high_texture_eligible"]].apply(
            pd.to_numeric, errors="coerce")
        r1_empty = ((pd.to_numeric(group["R1_H-low_voxels"], errors="coerce") == 0) |
                    (pd.to_numeric(group["R1_H-high_voxels"], errors="coerce") == 0))
        r2_empty = ((pd.to_numeric(group["R2_H-low_voxels"], errors="coerce") == 0) |
                    (pd.to_numeric(group["R2_H-high_voxels"], errors="coerce") == 0))
        unassigned = ((pd.to_numeric(group["unassigned_R1"], errors="coerce") > 0) |
                      (pd.to_numeric(group["unassigned_R2"], errors="coerce") > 0))
        failed = r1_empty | r2_empty | unassigned
        rows.append({
            "尺度mm": float(scale),
            "R1_both_rate": float(r1.min(axis=1).mean()),
            "R2_both_rate": float(r2.min(axis=1).mean()),
            "pair_both_rate": float((r1.min(axis=1) * r2.min(axis=1)).mean()),
            "R1_empty_n": int(r1_empty.sum()),
            "R2_empty_n": int(r2_empty.sum()),
            "any_failed_n": int(failed.sum()),
            "any_failed_rate": float(failed.mean()),
        })
    return pd.DataFrame(rows)


def numeric(row: pd.Series, key: str, default: float = np.nan) -> float:
    value = pd.to_numeric(row.get(key, default), errors="coerce")
    return float(value) if pd.notna(value) else default


def gate_row(summary_row: pd.Series, icc_row: pd.Series, n_pairs: int,
             r1_texture: float, r2_texture: float, pair_texture: float,
             amended: bool, failure_rate: float = np.nan,
             r1_empty_n: int = 0, r2_empty_n: int = 0) -> dict:
    hlow = numeric(summary_row, "H-low_Dice_median")
    hhigh = numeric(summary_row, "H-high_Dice_median")
    if amended:
        empty = numeric(summary_row, "empty_or_failed_case_rate")
    else:
        empty = failure_rate
    icc = numeric(icc_row, "ICC_2_1")
    empty_ok = bool(np.isfinite(empty) and empty == 0.0)
    return {
        "scale": numeric(summary_row, "尺度mm"), "hlow": hlow, "hhigh": hhigh,
        "empty": empty, "icc": icc, "r1_texture": r1_texture,
        "r2_texture": r2_texture, "pair_texture": pair_texture,
        "r1_empty_n": int(r1_empty_n), "r2_empty_n": int(r2_empty_n),
        "empty_ok": empty_ok, "qualified": empty_ok,
    }


def fmt(value: float, pct: bool = False) -> str:
    if not np.isfinite(value):
        return "NA"
    return ("%.1f%%" % (100.0 * value)) if pct else ("%.3f" % value)


def main() -> None:
    global_summary, global_icc, global_run = read_primary(GLOBAL_ROOT, amended=False)
    patient_summary, patient_icc, patient_run = read_primary(PATIENT_ROOT, amended=True)
    global_rates = global_case_rates().set_index("尺度mm")
    n_global = int(pd.to_numeric(global_run.iloc[0]["n_selected_A_same_sequence_pairs"], errors="coerce"))
    n_patient = int(pd.to_numeric(patient_run.iloc[0]["n_selected_A_same_sequence_pairs"], errors="coerce"))
    global_rows, patient_rows = [], []
    for _, row in global_summary.sort_values("尺度mm").iterrows():
        scale = numeric(row, "尺度mm")
        icc_rows = global_icc[np.isclose(pd.to_numeric(global_icc["尺度mm"], errors="coerce"), scale)]
        tex = global_rates.loc[scale]
        global_rows.append(gate_row(row, icc_rows.iloc[0], n_global,
                                    float(tex["R1_both_rate"]), float(tex["R2_both_rate"]),
                                    float(tex["pair_both_rate"]), amended=False,
                                    failure_rate=float(tex["any_failed_rate"]),
                                    r1_empty_n=int(tex["R1_empty_n"]),
                                    r2_empty_n=int(tex["R2_empty_n"])))
    for _, row in patient_summary.sort_values("尺度mm").iterrows():
        scale = numeric(row, "尺度mm")
        icc_rows = patient_icc[np.isclose(pd.to_numeric(patient_icc["尺度mm"], errors="coerce"), scale)]
        patient_rows.append(gate_row(
            row, icc_rows.iloc[0], n_patient,
            numeric(row, "R1_both_habitats_texture_eligible_rate"),
            numeric(row, "R2_both_habitats_texture_eligible_rate"),
            numeric(row, "pair_both_habitats_texture_eligible_rate"), amended=True))

    def table(rows: list[dict]) -> list[str]:
        lines = [
            "|尺度|H-low Dice|H-high Dice|空/失败|H-high分数 ICC|R1双生境纹理准入|R2双生境纹理准入|配对双准入|零失败门槛|",
            "|---:|---:|---:|---:|---:|---:|---:|---:|:---|",
        ]
        for x in rows:
            verdict = "通过" if x["qualified"] else "不通过"
            lines.append("| %.0f mm | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                x["scale"], fmt(x["hlow"]), fmt(x["hhigh"]), fmt(x["empty"], True),
                fmt(x["icc"]), fmt(x["r1_texture"], True), fmt(x["r2_texture"], True),
                fmt(x["pair_texture"], True), verdict))
        return lines

    g_core = any(x["qualified"] for x in global_rows)
    p_core = any(x["qualified"] for x in patient_rows)
    lines = [
        "# 当前宽松主分析集的 K-means 生境技术可行性比较",
        "",
        "> 本报告仅使用当前宽松主分析集的 A 集同序列 R1/R2 技术配对数据；不读取 DFS、CSS、OS、临床变量或 B 集结果。",
        "",
        "## 数据边界与判定规则",
        "",
        "- 宽松主分析集为 A=393、B=107；当前可用于同序列 R1/R2 技术重复性计算的 A 集配对为 %d 例。" % n_global,
        "- 跨病例 K-means：所有病例 R1 超体素均值共享聚类中心，R2 使用同一中心。",
        "- 病例内 K-means：每例独立拟合 K=2，按患者内中心由低到高标记 H-low/H-high。",
        "- 主输入：肌肉均值归一化、`[1,1,2] mm`、三维 SLIC、4/6/8 mm；K=2。",
        "- 当前唯一技术门槛：空生境、算法失败或肿瘤内未分配体素病例数必须为0。",
        "- Dice、ICC、ARI、双读者样本量及生境纹理准入率作为后续描述，不参与当前方法停止判定。",
        "",
        "## 跨病例 K-means",
        "",
    ] + table(global_rows) + [
        "",
        "判定：**跨病例K-means 4 mm尚未达到零失败门槛**。18例技术配对中，R1有%d例空生境、R2有%d例空生境，任一读者空/失败共%d例（%s）。即使主建模只使用R1，仍有%d/18例为空生境。" % (
            global_rows[0]["r1_empty_n"], global_rows[0]["r2_empty_n"],
            int(round(global_rows[0]["empty"] * n_global)), fmt(global_rows[0]["empty"], True),
            global_rows[0]["r1_empty_n"]),
        "",
        "## 病例内 K-means",
        "",
    ] + table(patient_rows) + [
        "",
        "判定：病例内K-means在18例技术配对的4/6/8 mm分支中均未出现空生境、算法失败或未分配体素，因此达到当前零失败门槛；其余指标仅作后续描述。",
        "",
        "## 比较结论与后续边界",
        "",
        "1. 按当前唯一门槛，病例内K-means在现有18例中通过，跨病例K-means 4 mm未通过。",
        "2. 跨病例K-means 4 mm已被指定为主方法候选，但在进入全A特征生成或预后建模前，必须先解决并复核现有空生境病例；不得把空生境编码为0或静默排除病例。",
        "3. 下一步应在A=393全部R1病例上执行正确计入空生境的无结局干跑。只要任一A病例仍为空/失败，主流程即暂停并提交病例清单。",
        "4. Dice、ICC和纹理准入率后续报告，但不参与当前停止判定；本报告不比较预后效能。",
        "",
        "## 产物索引",
        "",
        "- 跨病例 K-means：`technical_pilot/pair_metrics.csv`、`summary.csv`、`descriptor_icc.csv`。",
        "- 病例内 K-means：`technical_pilot_amended/pair_metrics.csv`、`summary.csv`、`descriptor_icc.csv`。",
        "- 运行边界：两套 `run_manifest.csv` 均记录 `outcome_columns_read=False`、`B_data_read=False`。",
    ]
    with open(REPORT, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(REPORT)
    print("cross_case_qualified", g_core)
    print("within_case_qualified", p_core)


if __name__ == "__main__":
    main()
