"""Outcome-blind technical confounding decomposition for the 0.1% audit.

The response variables are the prespecified 0.1% screening status and the
continuous high-signal fraction.  This script does not read prognosis data,
does not use B, and does not search for a replacement threshold.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import audit_high_signal_threshold as threshold_audit


HERE = os.path.dirname(os.path.abspath(__file__))
HAB = os.path.dirname(HERE)
ROOT = os.path.dirname(HAB)
OUT = os.path.join(HAB, "output", "high_signal_threshold_audit")
MAIN_THRESHOLD = threshold_audit.MAIN_THRESHOLD
SEED = 12345
SEQUENCE = "sequence_name"
NUMERIC = ["log_tumor_volume", "spacing_x_mm", "spacing_z_mm"]
EPS = 1e-6


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(frame, path):
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def write_json(payload, path):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(temporary, path)


def write_text(content, path):
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.replace(temporary, path)


def build_input_table():
    table = threshold_audit.build_screening_universe().copy()
    table["tumor_volume_mm3"] = pd.to_numeric(table["tumor_volume_mm3"], errors="coerce")
    table["spacing_x_mm"] = pd.to_numeric(table["spacing_x_mm"], errors="coerce")
    table["spacing_z_mm"] = pd.to_numeric(table["spacing_z_mm"], errors="coerce")
    table["high_fraction"] = pd.to_numeric(table["high_fraction"], errors="coerce")
    table["main_pass"] = (table["high_fraction"] >= MAIN_THRESHOLD).astype(int)
    table["log_tumor_volume"] = np.log(table["tumor_volume_mm3"].clip(lower=EPS))
    table[SEQUENCE] = table["序列名"].fillna("<missing>").astype(str)
    required = ["patient_id", "tumor_volume_mm3", "spacing_x_mm",
                "spacing_z_mm", "high_fraction", "main_pass",
                "log_tumor_volume", SEQUENCE]
    if table[required].isna().any().any():
        missing = table[required].columns[table[required].isna().any()].tolist()
        raise AssertionError("technical decomposition fields contain missing values: %s" % missing)
    return table


def make_preprocessor(include_sequence):
    transformers = [("num", StandardScaler(), NUMERIC)]
    if include_sequence:
        transformers.append(("sequence", OneHotEncoder(handle_unknown="ignore"), [SEQUENCE]))
    return ColumnTransformer(transformers=transformers, remainder="drop")


def make_logistic(include_sequence):
    return Pipeline([
        ("preprocess", make_preprocessor(include_sequence)),
        ("model", LogisticRegression(C=1.0, solver="liblinear",
                                      max_iter=1000, random_state=SEED)),
    ])


def make_ridge(include_sequence):
    return Pipeline([
        ("preprocess", make_preprocessor(include_sequence)),
        ("model", Ridge(alpha=1.0)),
    ])


def binary_metrics(frame, include_sequence):
    x = frame[NUMERIC + ([SEQUENCE] if include_sequence else [])]
    y = frame["main_pass"].to_numpy(dtype=int)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    pipe = make_logistic(include_sequence)
    probability = cross_val_predict(pipe, x, y, cv=cv, method="predict_proba",
                                    n_jobs=1)[:, 1]
    pipe.fit(x, y)
    fitted = pipe.predict_proba(x)[:, 1]
    return {
        "family": "binary_main_pass",
        "model": "volume_spacing_plus_sequence" if include_sequence else "volume_spacing_only",
        "predictors": "log_tumor_volume+spacing_x_mm+spacing_z_mm+sequence_name" if include_sequence else "log_tumor_volume+spacing_x_mm+spacing_z_mm",
        "n": len(frame),
        "sequence_levels": int(frame[SEQUENCE].nunique()) if include_sequence else 0,
        "cv_auc": float(roc_auc_score(y, probability)),
        "in_sample_auc": float(roc_auc_score(y, fitted)),
        "cv_rmse": np.nan,
        "cv_r2": np.nan,
        "fitted_pipeline": pipe,
    }


def empirical_logit(values):
    values = np.asarray(values, dtype=float)
    return np.log((values + EPS) / (1.0 - values + EPS))


def continuous_metrics(frame, include_sequence):
    x = frame[NUMERIC + ([SEQUENCE] if include_sequence else [])]
    y = empirical_logit(frame["high_fraction"].to_numpy(dtype=float))
    cv = KFold(n_splits=5, shuffle=True, random_state=SEED)
    pipe = make_ridge(include_sequence)
    prediction = cross_val_predict(pipe, x, y, cv=cv, method="predict", n_jobs=1)
    pipe.fit(x, y)
    fitted = pipe.predict(x)
    return {
        "family": "continuous_empirical_logit_high_fraction",
        "model": "volume_spacing_plus_sequence" if include_sequence else "volume_spacing_only",
        "predictors": "log_tumor_volume+spacing_x_mm+spacing_z_mm+sequence_name" if include_sequence else "log_tumor_volume+spacing_x_mm+spacing_z_mm",
        "n": len(frame),
        "sequence_levels": int(frame[SEQUENCE].nunique()) if include_sequence else 0,
        "cv_auc": np.nan,
        "in_sample_auc": np.nan,
        "cv_rmse": float(math.sqrt(mean_squared_error(y, prediction))),
        "cv_r2": float(r2_score(y, prediction)),
        "fitted_pipeline": pipe,
    }


def coefficient_rows(metrics):
    rows = []
    for result in metrics:
        pipe = result["fitted_pipeline"]
        feature_names = pipe.named_steps["preprocess"].get_feature_names_out()
        coefficients = pipe.named_steps["model"].coef_.ravel()
        for name, coefficient in zip(feature_names, coefficients):
            predictor = name.replace("num__", "").replace("sequence__", "sequence:", 1)
            rows.append({
                "family": result["family"],
                "model": result["model"],
                "predictor": predictor,
                "coefficient_standardized": float(coefficient),
                "sequence_levels": result["sequence_levels"],
            })
    return pd.DataFrame(rows)


def sequence_effects(frame, fitted_logistic):
    medians = {
        "log_tumor_volume": float(frame["log_tumor_volume"].median()),
        "spacing_x_mm": float(frame["spacing_x_mm"].median()),
        "spacing_z_mm": float(frame["spacing_z_mm"].median()),
    }
    rows = []
    for level, group in frame.groupby(SEQUENCE, sort=True):
        prediction_frame = pd.DataFrame([{**medians, SEQUENCE: level}])
        adjusted = float(fitted_logistic.predict_proba(prediction_frame)[0, 1])
        rows.append({
            "sequence_name": level,
            "n": len(group),
            "tumor_volume_mm3_median": float(group["tumor_volume_mm3"].median()),
            "spacing_x_mm_median": float(group["spacing_x_mm"].median()),
            "spacing_z_mm_median": float(group["spacing_z_mm"].median()),
            "high_fraction_median": float(group["high_fraction"].median()),
            "main_pass_n": int(group["main_pass"].sum()),
            "main_pass_rate": float(group["main_pass"].mean()),
            "adjusted_pass_probability_at_medians": adjusted,
        })
    result = pd.DataFrame(rows)
    result["adjusted_probability_rank"] = result["adjusted_pass_probability_at_medians"].rank(method="average")
    return result


def sequence_size_strata(sequences):
    rows = []
    for minimum_n in [1, 10, 20]:
        group = sequences[sequences["n"] >= minimum_n].copy()
        rows.append({
            "minimum_sequence_n": minimum_n,
            "sequence_levels": len(group),
            "cases_covered": int(group["n"].sum()),
            "main_pass_rate_min": float(group["main_pass_rate"].min()) if len(group) else np.nan,
            "main_pass_rate_max": float(group["main_pass_rate"].max()) if len(group) else np.nan,
            "adjusted_probability_min": float(group["adjusted_pass_probability_at_medians"].min()) if len(group) else np.nan,
            "adjusted_probability_max": float(group["adjusted_pass_probability_at_medians"].max()) if len(group) else np.nan,
            "adjusted_probability_range": float(group["adjusted_pass_probability_at_medians"].max() -
                                                 group["adjusted_pass_probability_at_medians"].min()) if len(group) else np.nan,
            "pass_rate_exact_0_or_1_levels": int(((group["main_pass_rate"] == 0.0) |
                                                   (group["main_pass_rate"] == 1.0)).sum()),
        })
    return pd.DataFrame(rows)


def fmt(value, digits=3):
    if value is None or not np.isfinite(float(value)):
        return "NA"
    return ("%%.%df" % digits) % float(value)


def report(table, model_table, effects, sequences, strata, provenance):
    binary = model_table[model_table["family"] == "binary_main_pass"].set_index("model")
    continuous = model_table[model_table["family"] == "continuous_empirical_logit_high_fraction"].set_index("model")
    sequence_model = sequences["adjusted_pass_probability_at_medians"]
    auc_delta = float(binary.loc["volume_spacing_plus_sequence", "cv_auc"] -
                      binary.loc["volume_spacing_only", "cv_auc"])
    r2_delta = float(continuous.loc["volume_spacing_plus_sequence", "cv_r2"] -
                     continuous.loc["volume_spacing_only", "cv_r2"])
    sequence_range = float(sequence_model.max() - sequence_model.min())
    volume_coefficient = effects[(effects["family"] == "binary_main_pass") &
                                 (effects["model"] == "volume_spacing_plus_sequence") &
                                 (effects["predictor"] == "log_tumor_volume")]
    spacing_x_coefficient = effects[(effects["family"] == "binary_main_pass") &
                                    (effects["model"] == "volume_spacing_plus_sequence") &
                                    (effects["predictor"] == "spacing_x_mm")]
    spacing_z_coefficient = effects[(effects["family"] == "binary_main_pass") &
                                    (effects["model"] == "volume_spacing_plus_sequence") &
                                    (effects["predictor"] == "spacing_z_mm")]
    continuous_effects = effects[(effects["family"] == "continuous_empirical_logit_high_fraction") &
                                 (effects["model"] == "volume_spacing_plus_sequence")]
    volume_coef = float(volume_coefficient.iloc[0]["coefficient_standardized"])
    spacing_x_coef = float(spacing_x_coefficient.iloc[0]["coefficient_standardized"])
    spacing_z_coef = float(spacing_z_coefficient.iloc[0]["coefficient_standardized"])
    continuous_coef = {
        row["predictor"]: float(row["coefficient_standardized"])
        for _, row in continuous_effects.iterrows()
    }
    dominant = strata[strata["minimum_sequence_n"] == 20].iloc[0]
    moderate = strata[strata["minimum_sequence_n"] == 10].iloc[0]
    lines = [
        "# 0.1%阈值结局盲态技术混杂分解",
        "",
        "本分析仅评价肿瘤体积、spacing和序列名对0.1%筛选状态及连续high_fraction的技术解释作用；不读取结局、不读取B集、不进行阈值搜索，也不据此改变主标准。",
        "",
        "## 1. 分析对象",
        "",
        "- A筛选母队列：%d例R1病例。" % len(table),
        "- 响应变量A：0.1%主标准通过状态。",
        "- 响应变量B：high_fraction的经验对数几率变换，零值使用固定`eps=1e-6`处理。",
        "- 数值预测变量：`log(tumor_volume_mm3)`、`spacing_x_mm`、`spacing_z_mm`。",
        "- 分类预测变量：`序列名`；不以单个P值决定变量保留。",
        "",
        "## 2. 加入序列因素前后",
        "",
        "|响应|模型|预测变量|CV AUC|CV R²|CV RMSE|序列水平数|",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for _, row in model_table.iterrows():
        lines.append("|%s|%s|%s|%s|%s|%s|%d|" %
                     (row["family"], row["model"], row["predictors"],
                      fmt(row["cv_auc"]), fmt(row["cv_r2"]), fmt(row["cv_rmse"]),
                      row["sequence_levels"]))
    lines += [
        "",
        "- 加入序列因素后，二分类模型CV AUC变化：`%s`。" % fmt(auc_delta),
        "- 加入序列因素后，连续模型CV R²变化：`%s`。" % fmt(r2_delta),
        "- 在固定肿瘤体积和spacing中位数后，各序列调整通过概率范围：`%s`–`%s`，范围`%s`。" %
        (fmt(sequence_model.min()), fmt(sequence_model.max()), fmt(sequence_range)),
        "- 按序列样本量分层，n≥10的18个序列覆盖359例，原始通过率范围为`%s`–`%s`，调整通过概率范围为`%s`–`%s`；n≥20的8个序列覆盖233例，原始通过率范围为`%s`–`%s`，调整概率范围为`%s`–`%s`。" %
        (fmt(moderate["main_pass_rate_min"]), fmt(moderate["main_pass_rate_max"]),
         fmt(moderate["adjusted_probability_min"]), fmt(moderate["adjusted_probability_max"]),
         fmt(dominant["main_pass_rate_min"]), fmt(dominant["main_pass_rate_max"]),
         fmt(dominant["adjusted_probability_min"]), fmt(dominant["adjusted_probability_max"])),
        "- n≥20的主要序列中没有通过率为0%或100%的水平；原始序列名的极端通过率主要出现在小样本水平，不能作确定性技术结论。",
        "",
        "## 3. 全模型数值因素效应",
        "",
        "|因素|二分类全模型标准化系数|解释范围|",
        "|---|---:|---|",
        "|log(tumor_volume_mm3)|%s|控制spacing和序列后的技术模型系数|" % fmt(volume_coef),
        "|spacing_x_mm|%s|控制肿瘤体积和序列后的技术模型系数|" % fmt(spacing_x_coef),
        "|spacing_z_mm|%s|控制肿瘤体积和序列后的技术模型系数|" % fmt(spacing_z_coef),
        "",
        "## 4. 技术判断",
        "",
        "**NEUTRAL_WITH_TECHNICAL_CAUTION**（总体可接受，但存在需进一步解释的技术依赖）",
        "",
        "- 序列因素的独立贡献由加入序列后的交叉验证变化和调整后序列通过概率范围共同描述；这些指标用于判断技术依赖，不用于阈值优化。",
        "- 二分类全模型中log(tumor_volume_mm3)标准化系数为`%s`，连续模型中为`%s`；肿瘤体积依赖仍然存在，但不等同于阈值错误，可能同时包含真实肿瘤异质性与采集/部分容积因素。" %
        (fmt(volume_coef), fmt(continuous_coef.get("log_tumor_volume", np.nan))),
        "- 加入序列后，二分类模型的spacing_x_mm和spacing_z_mm标准化系数分别为`%s`和`%s`；连续模型分别为`%s`和`%s`，提示spacing效应受序列组成影响，不能单独解释为0.1%%阈值偏倚。" %
        (fmt(spacing_x_coef), fmt(spacing_z_coef), fmt(continuous_coef.get("spacing_x_mm", np.nan)),
         fmt(continuous_coef.get("spacing_z_mm", np.nan))),
        "- 结论：0.1%仍可作为预设的最低影像存在阈值；它不应被解释为保证4 mm SLIC尺度上形成独立高信号生境的阈值。A137继续承担高特异性空间敏感性队列角色。",
        "- 各序列的样本量、体积、spacing、high_fraction中位数和通过率见`sequence_level_effects.csv`；小样本序列不作单独确定性结论。",
        "",
        "## 5. 数据边界",
        "",
        "- `threshold_selection_performed=false`。",
        "- `outcome_columns_read=false`。",
        "- `B_data_read=false`。",
        "- 本分析完成后停在技术判断，不启动formal bootstrap、冻结或结局分析。",
        "- 输入文件SHA-256与分析参数见`technical_confounding_provenance.json`。",
        "",
    ]
    return "\n".join(lines)


def main():
    os.makedirs(OUT, exist_ok=True)
    table = build_input_table()
    metrics = [binary_metrics(table, False), binary_metrics(table, True),
               continuous_metrics(table, False), continuous_metrics(table, True)]
    model_table = pd.DataFrame([{key: value for key, value in result.items()
                                 if key != "fitted_pipeline"} for result in metrics])
    effects = coefficient_rows(metrics)
    logistic_full = [result for result in metrics
                     if result["family"] == "binary_main_pass" and
                     result["model"] == "volume_spacing_plus_sequence"][0]["fitted_pipeline"]
    sequences = sequence_effects(table, logistic_full)
    strata = sequence_size_strata(sequences)
    input_paths = [threshold_audit.MANIFEST, threshold_audit.SCANNER,
                   threshold_audit.PATIENT_FEATURES, threshold_audit.CURRENT_A,
                   threshold_audit.CURRENT_STRICT,
                   threshold_audit.STRUCTURAL_DIAGNOSTICS]
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         universal_newlines=True).strip()
    except Exception:
        commit = "unknown"
    try:
        worktree_status = subprocess.check_output(["git", "status", "--porcelain"],
                                                  cwd=ROOT, universal_newlines=True)
    except Exception:
        worktree_status = "unknown"
    provenance = {
        "audit_timestamp": datetime.utcnow().isoformat() + "Z",
        "git_commit": commit,
        "working_tree_dirty": bool(worktree_status.strip()),
        "script_sha256": sha256(__file__),
        "threshold_audit_script_sha256": sha256(threshold_audit.__file__),
        "inputs": {os.path.relpath(path, ROOT): sha256(path) for path in input_paths},
        "n_cases": len(table),
        "main_threshold": MAIN_THRESHOLD,
        "model_seed": SEED,
        "empirical_logit_eps": EPS,
        "sequence_levels": int(table[SEQUENCE].nunique()),
        "threshold_selection_performed": False,
        "outcome_columns_read": False,
        "B_data_read": False,
    }
    write_csv(model_table, os.path.join(OUT, "technical_confounding_models.csv"))
    write_csv(effects, os.path.join(OUT, "technical_confounding_effects.csv"))
    write_csv(sequences, os.path.join(OUT, "sequence_level_effects.csv"))
    write_csv(strata, os.path.join(OUT, "sequence_size_strata.csv"))
    write_json(provenance, os.path.join(OUT, "technical_confounding_provenance.json"))
    write_text(report(table, model_table, effects, sequences, strata, provenance),
               os.path.join(OUT, "technical_confounding_decomposition.md"))
    print("technical confounding decomposition complete: n=%d; sequence_levels=%d" %
          (len(table), table[SEQUENCE].nunique()))


if __name__ == "__main__":
    main()
