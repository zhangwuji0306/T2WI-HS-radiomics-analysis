"""构建 v2 原始建模数据集，不在全 A 上标准化或做相关筛选。

候选组学特征来自 stage6_v2 的 ICC 固定预筛选。所有预测数据驱动操作（插补、近零方差、
跨特征族相关去重和标准化）必须在后续嵌套 CV 的外层训练折内完成。

默认同时生成宽松高信号主分析集和严格敏感性集；不带 ``_strict`` 后缀的文件（以及显式的
``*_lenient`` 副本）供主分析使用。

预设治疗前临床影像学变量共 9 个：年龄、CEA_log、mrT_4级、mrN_3级、MRF、mrEMVI、
thickness、EID、活检病理非腺癌。性别、length、distance 不进入任何主模型。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
EX_ROOT = os.path.join(PROJECT_ROOT, "feature_extract")
MODELING = os.path.join(ROOT, "output", "modeling_v2")
DATA_XLSX = os.path.join(ROOT, "data", "radiology_clinic_pathology_prognosis_data.xlsx")
MANIFEST = os.path.join(EX_ROOT, "output", "manifest.csv")
SCANNER = os.path.join(EX_ROOT, "output", "scanner_map.csv")
STAGE6 = os.path.join(ROOT, "output", "qc", "stage6_v2")
FEATURES = os.path.join(EX_ROOT, "output", "features_v2")
SCREEN_ROOT = os.path.join(ROOT, "..", "habitat_analysis", "output", "high_signal_eligibility_audit")
SCREEN_FILES = {
    "lenient": ("lenient_screening_decisions.csv", "lenient_pass"),
    "strict": ("recommended_screening_decisions.csv", "recommended_pass"),
}
SCREEN_DEFINITIONS = {
    "lenient": {
        "high_signal": "tumor voxel intensity >= per-case fat ROI mean",
        "minimum_high_voxels": 1,
        "minimum_high_fraction": 0.001,
    },
    "strict": {
        "high_signal": "tumor voxel intensity >= per-case fat ROI mean",
        "minimum_high_fraction": 0.01,
        "minimum_high_lcc_volume_mm3": 128.0,
        "minimum_high_core2_volume_mm3": 32.0,
    },
}

BATCH_FILES = {"original": "features_original.csv", "wavelet": "features_wavelet.csv",
               "log": "features_log.csv"}
PRIMARY_CLINICAL = ["年龄", "CEA_log", "mrT_4级", "mrN_3级", "MRF", "mrEMVI",
                    "thickness", "EID", "活检病理非腺癌"]
EXCLUDED_PRIMARY = ["性别", "length", "distance"]
DESCRIPTIVE = ["性别", "distance", "length", "是否新辅助", "手术术式", "术式非LAR"]
POSTOP = ["(y)pT_4级", "(y)pN_3级", "PNI", "LVI", "组织学粘液成分有无",
          "pTRG_应答", "mucin_original_missing"]
OUTCOMES = ["OS", "OS_Status", "CSS", "CSS_Status", "DFS_time", "DFS_event"]
R_ALIASES = {"影像号": "patient_id", "年龄": "age", "CEA_log": "cea_log",
             "mrT_4级": "mrt_ord", "mrN_3级": "mrn_ord", "MRF": "mrf",
             "mrEMVI": "mremvi", "thickness": "thickness_mm", "EID": "eid_mm",
             "活检病理非腺癌": "biopsy_non_adenocarcinoma", "性别": "sex",
             "distance": "distance_mm", "length": "length_mm", "是否新辅助": "neoadjuvant",
             "手术术式": "surgery_type", "术式非LAR": "non_lar",
             "(y)pT_4级": "ypt_ord", "(y)pN_3级": "ypn_ord",
             "组织学粘液成分有无": "mucin", "pTRG_应答": "ptrg_response",
             "mucin_original_missing": "mucin_original_missing"}


def cohort_table(screen: str) -> pd.DataFrame:
    man = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    sc = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    sc["_field"] = pd.to_numeric(sc["R1场强"], errors="coerce")
    is_a = ((sc["R1厂商"] == "GE MEDICAL SYSTEMS") &
            (sc["R1机型"] == "DISCOVERY MR750") & (sc["_field"].round(1) == 3.0))
    cohort = pd.DataFrame({"影像号": man["影像号"].astype(str).str.strip(),
                           "split": np.where(is_a, "A", "B")})
    if screen not in SCREEN_FILES:
        raise ValueError("screen must be lenient or strict")
    screen_file, pass_col = SCREEN_FILES[screen]
    screen_path = os.path.join(SCREEN_ROOT, screen_file)
    if not os.path.exists(screen_path):
        raise FileNotFoundError(f"缺少高信号筛选结果：{screen_path}")
    decisions = pd.read_csv(screen_path, encoding="utf-8-sig", dtype={"patient_id": str})
    decisions["patient_id"] = decisions["patient_id"].astype(str).str.strip()
    if pass_col not in decisions.columns:
        raise AssertionError(f"筛选结果缺少 {pass_col}")
    eligible = decisions.loc[pd.to_numeric(decisions[pass_col], errors="coerce") == 1,
                             ["patient_id"]].rename(columns={"patient_id": "影像号"})
    cohort = cohort.merge(eligible.assign(_eligible=1), on="影像号", how="inner")
    return cohort.drop(columns=["_eligible"])


def load_features(combo: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    cand_path = os.path.join(STAGE6, combo, "candidate_features.csv")
    if not os.path.exists(cand_path):
        raise FileNotFoundError(f"缺少 {cand_path}；请先运行 stage6_qc.py")
    candidates = pd.read_csv(cand_path, encoding="utf-8-sig")
    tables = []
    for batch, fname in BATCH_FILES.items():
        wanted = candidates.loc[candidates["batch"] == batch, "feature"].tolist()
        path = os.path.join(FEATURES, combo, fname)
        table = pd.read_csv(path, encoding="utf-8-sig", dtype={"影像号": str})
        table = table[table["读者"] == "R1"].copy()
        table["影像号"] = table["影像号"].astype(str).str.strip()
        absent = sorted(set(wanted) - set(table.columns))
        if absent:
            raise AssertionError(f"{batch} 缺少候选特征：{absent[:5]}")
        tables.append(table[["影像号"] + wanted].set_index("影像号"))
    features = pd.concat(tables, axis=1)
    if features.columns.duplicated().any():
        raise AssertionError("合并后三批次存在重复特征名")
    return features.reset_index(), candidates


def build_screened_dataset(screen: str, combo: str, features: pd.DataFrame,
                           candidates: pd.DataFrame, clinical: pd.DataFrame,
                           main_alias: bool) -> None:
    cohort = cohort_table(screen)
    cols = ["影像号"] + OUTCOMES + PRIMARY_CLINICAL + DESCRIPTIVE + POSTOP
    dataset = cohort.merge(features, on="影像号", how="left").merge(
        clinical[cols], on="影像号", how="left")
    feature_cols = candidates["feature"].tolist()
    if dataset[feature_cols].isna().sum().sum() != 0:
        raise AssertionError("候选组学特征存在缺失")
    dataset["cc"] = (dataset["CEA_log"].notna() &
                     dataset["活检病理非腺癌"].notna()).astype(int)
    order = (["影像号", "split", "cc"] + OUTCOMES + PRIMARY_CLINICAL + feature_cols +
             DESCRIPTIVE + POSTOP)
    dataset = dataset[order]
    suffix = "" if main_alias else "_" + screen
    dataset.to_csv(os.path.join(MODELING, "dataset_primary_raw%s.csv" % suffix),
                   index=False, encoding="utf-8-sig")
    dataset[dataset["split"] == "A"].to_csv(
        os.path.join(MODELING, "dataset_primary_raw_A%s.csv" % suffix),
        index=False, encoding="utf-8-sig")
    dataset[dataset["split"] == "B"].to_csv(
        os.path.join(MODELING, "dataset_primary_raw_B%s.csv" % suffix),
        index=False, encoding="utf-8-sig")
    r_dataset = dataset.rename(columns=R_ALIASES)
    r_dataset.to_csv(os.path.join(MODELING, "dataset_primary_raw%s_r.csv" % suffix),
                     index=False, encoding="utf-8")
    r_dataset[r_dataset["split"] == "A"].to_csv(
        os.path.join(MODELING, "dataset_primary_raw_A%s_r.csv" % suffix),
        index=False, encoding="utf-8")
    r_dataset[r_dataset["split"] == "B"].to_csv(
        os.path.join(MODELING, "dataset_primary_raw_B%s_r.csv" % suffix),
        index=False, encoding="utf-8")

    schema = {"analysis_version": "v2_continuous_nested",
              "combo": combo, "screening_rule": screen,
              "screening_source": SCREEN_FILES[screen][0],
              "screening_pass_column": SCREEN_FILES[screen][1],
              "screening_definition": SCREEN_DEFINITIONS[screen],
              "primary_clinical_variables": PRIMARY_CLINICAL,
              "primary_clinical_variables_r": [R_ALIASES[x] for x in PRIMARY_CLINICAL],
              "r_column_aliases": R_ALIASES,
              "excluded_from_primary": EXCLUDED_PRIMARY,
              "radiomics_candidates": feature_cols,
              "data_processing": "raw; fit imputation/filtering/scaling inside outer training folds",
              "complete_case_definition": "CEA_log and 活检病理非腺癌 both observed"}
    schema_name = "analysis_schema.json" if main_alias else "analysis_schema_%s.json" % screen
    with open(os.path.join(MODELING, schema_name), "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    a = dataset[dataset["split"] == "A"]
    b = dataset[dataset["split"] == "B"]
    lines = ["# v2 建模数据集检查", "",
             "- 情景：%s" % combo, "- 高信号筛选：%s" % screen,
             "- 队列：A %d / B %d" % (len(a), len(b)),
             "- ICC 固定候选特征：%d" % len(feature_cols),
             "- 预设临床影像学变量：%d（已删除性别、length、distance）" % len(PRIMARY_CLINICAL),
             "- 完整病例：A %d / B %d" % (int(a["cc"].sum()), int(b["cc"].sum())),
             "- 数据保持原始尺度；不得直接用全 A 预标准化。"]
    report_name = "report.md" if main_alias else "report_%s.md" % screen
    with open(os.path.join(MODELING, report_name), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if main_alias:
        # Keep an explicit lenient-named copy in addition to the legacy main aliases
        # consumed by the downstream R scripts.
        for name in [
            "dataset_primary_raw.csv", "dataset_primary_raw_A.csv", "dataset_primary_raw_B.csv",
            "dataset_primary_raw_r.csv", "dataset_primary_raw_A_r.csv", "dataset_primary_raw_B_r.csv",
            "analysis_schema.json", "report.md",
        ]:
            stem, ext = os.path.splitext(name)
            shutil.copyfile(os.path.join(MODELING, name),
                            os.path.join(MODELING, stem + "_lenient" + ext))
    print("；".join(lines[2:]))


def main() -> None:
    ap = argparse.ArgumentParser(description="构建筛选后的 v2 原始建模数据集")
    ap.add_argument("--combo", default="muscle_f0.25")
    ap.add_argument("--screen", choices=["both", "lenient", "strict"], default="both",
                    help="生成宽松主分析集、严格保留集，或单独生成一种")
    args = ap.parse_args()
    os.makedirs(MODELING, exist_ok=True)
    features, candidates = load_features(args.combo)
    clinical = pd.read_excel(DATA_XLSX)
    clinical["影像号"] = clinical["影像号"].astype(str).str.strip()
    clinical["性别"] = clinical["性别"].map({"男": 1, "女": 0}).astype(int)
    screens = ["lenient", "strict"] if args.screen == "both" else [args.screen]
    for screen in screens:
        build_screened_dataset(screen, args.combo, features, candidates, clinical,
                                main_alias=(screen == "lenient"))


if __name__ == "__main__":
    main()
