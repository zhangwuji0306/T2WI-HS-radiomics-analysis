"""构建 v2 原始建模数据集，不在全 A 上标准化或做相关筛选。

候选组学特征来自 stage6_v2 的 ICC 固定预筛选。所有预测数据驱动操作（插补、近零方差、
跨特征族相关去重和标准化）必须在后续嵌套 CV 的外层训练折内完成。

默认同时生成宽松高信号主分析集和严格敏感性集；不带 ``_strict`` 后缀的文件（以及显式的
``*_lenient`` 副本）供主分析使用。

预设治疗前临床影像学变量共 9 个：年龄、CEA_log、mrT_4级、mrN_3级、MRF、mrEMVI、
thickness、EID、活检病理非腺癌。性别、length、distance 不进入任何主模型。
"""
from __future__ import annotations

import os
import sys

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
HABITAT_ROOT = os.path.join(PROJECT_ROOT, "habitat_analysis")
HABITAT_SCRIPTS = os.path.join(HABITAT_ROOT, "scripts")
FEATURE_SCRIPTS = os.path.join(EX_ROOT, "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import require_b_unlock, resolve_cohort_membership  # noqa: E402

TECHNICAL_COHORT = os.path.join(HABITAT_ROOT, "output", "technical_cohort_manifest")
TECHNICAL_A393 = os.path.join(TECHNICAL_COHORT, "cohort_A_lenient.csv")
TECHNICAL_A137 = os.path.join(TECHNICAL_COHORT, "cohort_A_strict.csv")
FREEZE_LOCK = os.path.join(HABITAT_ROOT, "freeze_lock.json")
HABITAT_CONFIG = os.path.join(HABITAT_ROOT, "configs", "main_cross_case_kmeans_k2_4mm.json")
PREPROCESSING_CONFIG = os.path.join(EX_ROOT, "configs", "radiomics_params.yaml")
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
    cohort = resolve_cohort_membership(man, sc)
    cohort = cohort.loc[cohort["排除"].fillna("0").ne("1")]
    cohort = cohort[["影像号", "split"]]
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


def validate_outcome_unlock() -> dict:
    raise RuntimeError("legacy builder is disabled; no outcome source may be opened")


def load_features(*args, **kwargs):
    raise RuntimeError("legacy builder is disabled; use build_model_dataset_a.py")


def build_screened_dataset(*args, **kwargs):
    raise RuntimeError("legacy builder is disabled; use build_model_dataset_a.py")


def main() -> None:
    raise RuntimeError(
        "legacy build_model_dataset.py is disabled; use "
        "build_model_dataset_a.py --split A"
    )


if __name__ == "__main__":
    main()
