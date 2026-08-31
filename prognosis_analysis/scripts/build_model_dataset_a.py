"""Build the formal A-only raw modeling datasets for W05.

The builder reads technical A identifiers first, uses those identifiers as the
allow-list for every clinical/outcome and raw feature read, and emits only A
artifacts.  B/all modes are deliberately disabled until the second-stage model
freeze exists.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict, Iterable, Set

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
SCREEN_ROOT = os.path.join(PROJECT_ROOT, "habitat_analysis", "output",
                           "high_signal_eligibility_audit")
TECHNICAL_COHORT = os.path.join(PROJECT_ROOT, "habitat_analysis", "output",
                                "technical_cohort_manifest")
TECHNICAL_A393 = os.path.join(TECHNICAL_COHORT, "cohort_A_lenient.csv")
TECHNICAL_A137 = os.path.join(TECHNICAL_COHORT, "cohort_A_strict.csv")

FEATURE_SCRIPTS = os.path.join(EX_ROOT, "scripts")
if FEATURE_SCRIPTS not in sys.path:
    sys.path.insert(0, FEATURE_SCRIPTS)
from data_split_guard import (  # noqa: E402
    read_A_outcomes,
    read_technical_A,
    require_b_unlock,
    resolve_cohort_membership,
)

BATCH_FILES = {"original": "features_original.csv",
               "wavelet": "features_wavelet.csv",
               "log": "features_log.csv"}
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
PRIMARY_CLINICAL = ["年龄", "CEA_log", "mrT_4级", "mrN_3级", "MRF", "mrEMVI",
                    "thickness", "EID", "活检病理非腺癌"]
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


def _ids(frame: pd.DataFrame, label: str) -> Set[str]:
    if "影像号" not in frame.columns:
        raise AssertionError("%s lacks 影像号" % label)
    values = frame["影像号"].astype(str).str.strip()
    if values.eq("").any() or values.duplicated().any():
        raise AssertionError("%s identifiers must be nonempty and unique" % label)
    return set(values)


def load_a_technical_ids() -> Dict[str, Set[str]]:
    """Read both frozen technical A ID lists before any outcome read."""
    a393 = read_technical_A(TECHNICAL_A393, allow_full=True,
                            dtype={"影像号": str})
    a137 = read_technical_A(TECHNICAL_A137, allow_full=True,
                            dtype={"影像号": str})
    ids = {"lenient": _ids(a393, "A393 technical cohort"),
           "strict": _ids(a137, "A137 technical cohort")}
    if not ids["strict"].issubset(ids["lenient"]):
        raise AssertionError("A137 technical cohort is not a subset of A393")
    return ids


def cohort_table(screen: str, allowed_ids: Iterable[str]) -> pd.DataFrame:
    if screen not in SCREEN_FILES:
        raise ValueError("screen must be lenient or strict")
    allowed = set(str(value).strip() for value in allowed_ids)
    manifest = pd.read_csv(MANIFEST, encoding="utf-8-sig", dtype=str)
    scanner = pd.read_csv(SCANNER, encoding="utf-8-sig", dtype=str)
    cohort = resolve_cohort_membership(manifest, scanner)
    if "排除" in cohort.columns:
        cohort = cohort[cohort["排除"].fillna("0").astype(str).ne("1")]
    cohort = cohort[(cohort["split"] == "A") & cohort["影像号"].isin(allowed)][
        ["影像号", "split"]]
    screen_file, pass_column = SCREEN_FILES[screen]
    screening = pd.read_csv(os.path.join(SCREEN_ROOT, screen_file),
                            encoding="utf-8-sig", dtype={"patient_id": str})
    if pass_column not in screening.columns:
        raise AssertionError("screening file missing %s" % pass_column)
    screening["patient_id"] = screening["patient_id"].astype(str).str.strip()
    eligible = screening.loc[
        pd.to_numeric(screening[pass_column], errors="coerce").eq(1),
        ["patient_id"]].rename(columns={"patient_id": "影像号"})
    cohort = cohort.merge(eligible.assign(_eligible=1), on="影像号", how="inner")
    return cohort.drop(columns=["_eligible"])


def load_features(combo: str, allowed_ids: Iterable[str]):
    candidate_path = os.path.join(STAGE6, combo, "candidate_features.csv")
    if not os.path.exists(candidate_path):
        raise FileNotFoundError("missing candidate feature pool: %s" % candidate_path)
    candidates = pd.read_csv(candidate_path, encoding="utf-8-sig")
    tables = []
    for batch, filename in BATCH_FILES.items():
        wanted = candidates.loc[candidates["batch"] == batch, "feature"].tolist()
        path = os.path.join(FEATURES, combo, filename)
        # The reader filters the mixed raw source before a pandas frame is
        # assembled.  Only the already-authorized A IDs are admitted.
        table = read_technical_A(path, allowed_ids=allowed_ids,
                                 dtype={"影像号": str})
        if "split" in table.columns and table["split"].astype(str).ne("A").any():
            raise AssertionError("technical feature table contains non-A rows after filtering")
        table = table[table["读者"] == "R1"].copy()
        table["影像号"] = table["影像号"].astype(str).str.strip()
        if table["影像号"].duplicated().any():
            raise AssertionError("R1 feature identifiers are duplicated: %s" % batch)
        absent = sorted(set(wanted) - set(table.columns))
        if absent:
            raise AssertionError("%s missing candidate features: %s" % (batch, absent[:5]))
        tables.append(table[["影像号"] + wanted].set_index("影像号"))
    features = pd.concat(tables, axis=1)
    if features.columns.duplicated().any():
        raise AssertionError("duplicate feature names across batches")
    return features.reset_index(), candidates


def _normalize_clinical(clinical: pd.DataFrame) -> pd.DataFrame:
    if "影像号" not in clinical.columns:
        raise AssertionError("A clinical/outcome table lacks 影像号")
    clinical = clinical.copy()
    clinical["影像号"] = clinical["影像号"].astype(str).str.strip()
    if clinical["影像号"].duplicated().any():
        raise AssertionError("A clinical/outcome identifiers are duplicated")
    if "性别" in clinical.columns:
        clinical["性别"] = clinical["性别"].map({"男": 1, "女": 0})
    return clinical


def _write_dataset(screen: str, combo: str, features: pd.DataFrame,
                   candidates: pd.DataFrame, clinical: pd.DataFrame,
                   cohort: pd.DataFrame, output_root: str) -> None:
    if set(cohort["split"].astype(str)) != {"A"}:
        raise AssertionError("A builder received a non-A cohort")
    clinical = _normalize_clinical(clinical)
    required = ["影像号"] + OUTCOMES + PRIMARY_CLINICAL + DESCRIPTIVE + POSTOP
    missing = sorted(set(required) - set(clinical.columns))
    if missing:
        raise AssertionError("A clinical/outcome table missing columns: %s" % missing[:5])
    feature_cols = candidates["feature"].tolist()
    dataset = cohort.merge(features, on="影像号", how="left").merge(
        clinical[required], on="影像号", how="left", validate="one_to_one")
    if dataset[feature_cols].isna().sum().sum() != 0:
        raise AssertionError("A candidate radiomics features contain missing values")
    dataset["cc"] = (dataset["CEA_log"].notna() &
                      dataset["活检病理非腺癌"].notna()).astype(int)
    ordered = (["影像号", "split", "cc"] + OUTCOMES + PRIMARY_CLINICAL + feature_cols +
               DESCRIPTIVE + POSTOP)
    dataset = dataset[ordered]
    suffix = "" if screen == "lenient" else "_strict"
    os.makedirs(output_root, exist_ok=True)
    raw_name = "dataset_primary_raw_A%s.csv" % suffix
    r_name = "dataset_primary_raw_A%s_r.csv" % suffix
    dataset.to_csv(os.path.join(output_root, raw_name), index=False, encoding="utf-8-sig")
    dataset.rename(columns=R_ALIASES).to_csv(
        os.path.join(output_root, r_name), index=False, encoding="utf-8")
    schema = {
        "analysis_version": "v2_continuous_nested",
        "split": "A",
        "combo": combo,
        "screening_rule": screen,
        "screening_source": SCREEN_FILES[screen][0],
        "screening_pass_column": SCREEN_FILES[screen][1],
        "screening_definition": SCREEN_DEFINITIONS[screen],
        "primary_clinical_variables": PRIMARY_CLINICAL,
        "primary_clinical_variables_r": [R_ALIASES[x] for x in PRIMARY_CLINICAL],
        "r_column_aliases": R_ALIASES,
        "radiomics_candidates": feature_cols,
        "data_processing": "raw; fit imputation/filtering/scaling inside outer training folds",
        "complete_case_definition": "CEA_log and 活检病理非腺癌 both observed",
        "n_A": len(dataset),
        "n_A_complete_case": int(dataset["cc"].sum()),
    }
    with open(os.path.join(output_root, "analysis_schema_A%s.json" % suffix),
              "w", encoding="utf-8") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    lines = ["# A 建模数据集检查", "", "- 情景：%s" % combo,
             "- 高信号筛选：%s" % screen,
             "- A 样本量：%d" % len(dataset),
             "- ICC 固定候选特征：%d" % len(feature_cols),
             "- 预设临床影像学变量：%d" % len(PRIMARY_CLINICAL),
             "- 完整病例：A %d" % int(dataset["cc"].sum()),
             "- 数据保持原始尺度；不得直接用全 A 预标准化。"]
    with open(os.path.join(output_root, "report_A%s.md" % suffix),
              "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_a_datasets(combo: str, screens, output_root: str = MODELING) -> None:
    technical_ids = load_a_technical_ids()
    all_a_ids = technical_ids["lenient"]
    # This is the only clinical/outcome entry point.  It receives the A393
    # allow-list after both technical ID files have been read.
    clinical = read_A_outcomes(DATA_XLSX, allowed_ids=all_a_ids,
                               dtype={"影像号": str})
    features, candidates = load_features(combo, all_a_ids)
    for screen in screens:
        cohort = cohort_table(screen, technical_ids[screen])
        screen_ids = set(cohort["影像号"])
        screen_features = features[features["影像号"].isin(screen_ids)].copy()
        screen_clinical = clinical[clinical["影像号"].astype(str).str.strip().isin(screen_ids)].copy()
        _write_dataset(screen, combo, screen_features, candidates, screen_clinical,
                       cohort, output_root)


def main() -> None:
    parser = argparse.ArgumentParser(description="构建正式 A-only v2 原始建模数据集")
    parser.add_argument("--combo", default="muscle_f0.25")
    parser.add_argument("--screen", choices=["both", "lenient", "strict"], default="both")
    parser.add_argument("--split", choices=["A", "B", "all"], default="A")
    parser.add_argument("--out-root", default=MODELING)
    args = parser.parse_args()
    if args.split != "A":
        # Keep this check first: no manifest, feature, clinical, or outcome
        # source may be opened while the second lock is absent.
        require_b_unlock()
        raise RuntimeError("W05 formal builder is A-only; B/all are disabled until model freeze")
    screens = (["lenient", "strict"] if args.screen == "both" else [args.screen])
    build_a_datasets(args.combo, screens, args.out_root)


if __name__ == "__main__":
    main()
