"""FT04 full-A refit, model-state serialization, and frozen prediction boundary.

The FT04 production path reads the accepted A-only feature assets, selects the
penalty for each penalized model by the accepted ordinary training-only
five-fold rule on that model's complete eligible A population, and then fits
one final model on that population.  Patient-level fitted state is written
only below the ignored FT04 output directory.  The tracked lock contains
relative paths, hashes, and aggregate metadata only.
"""
from __future__ import absolute_import

import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_SCRIPTS_ROOT = os.path.join(_PROJECT_ROOT, "prognosis_analysis", "scripts")
for _path in (_HERE, _SCRIPTS_ROOT):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import ft02_runner as ft02  # noqa: E402
import ft03_runner as ft03  # noqa: E402


FT04_STAGE = "FT04"
FT_LABEL = "exploratory_fullA_habitat_non_nested_validation"
MODEL_IDS = tuple(ft02.FT_MODEL_SPECS.keys())
REPEAT = 1
SEED = 12345
INNER_FOLDS = 5
LAMBDA_COUNT = 20
MAX_ITER = 3000
TOLERANCE = 1e-7
HORIZONS = OrderedDict((("3_year", 36.0), ("5_year", 60.0)))
PRE_RUN_ESTIMATE_MINUTES = 180

DEFAULT_OUTPUT_ROOT = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "output", "ft_20260910_01a08bf3", "FT04")
DEFAULT_STATE_ROOT = os.path.join(DEFAULT_OUTPUT_ROOT, "model_states")
DEFAULT_LOCK = os.path.join(_HERE, "FT_model_freeze_lock.json")
DEFAULT_AUDIT = os.path.join(_HERE, "FT04_refit_and_freeze_audit.md")
FT05_MANIFEST = os.path.join(_HERE, "FT05_B_feature_manifest.json")
FT05B_UNLOCK = os.path.join(_HERE, "FT05B_outcome_unlock.json")
FORMAL_MODEL_LOCK = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "model_freeze_lock.json")


class FT04ValidationError(ValueError):
    """Raised when an FT04 artifact or prediction contract is invalid."""


def _sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value):
    return _sha256_bytes(value.encode("utf-8"))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path):
    return os.path.relpath(os.path.abspath(path), _PROJECT_ROOT).replace("\\", "/")


def _absolute(relative):
    if os.path.isabs(relative):
        raise FT04ValidationError("absolute path is not permitted in FT04 artifacts")
    path = os.path.abspath(os.path.join(_PROJECT_ROOT, str(relative)))
    root = os.path.abspath(_PROJECT_ROOT)
    if os.path.commonpath([root, path]) != root:
        raise FT04ValidationError("artifact path escapes the project root")
    return path


def _canonical_json(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
        return None if not np.isfinite(value) else value
    if isinstance(value, float):
        return None if not np.isfinite(value) else value
    return value


def _write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(_json_safe(payload), handle, ensure_ascii=False, indent=2,
                  sort_keys=True, allow_nan=False)
        handle.write("\n")


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except (IOError, OSError, ValueError) as exc:
        raise FT04ValidationError("cannot read JSON artifact %s: %s" %
                                  (_relative(path), exc))


def _git_head():
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_PROJECT_ROOT,
            stderr=subprocess.STDOUT).decode("ascii").strip()
        return value if len(value) == 40 else None
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return None


def _file_record(path, required=True):
    if not os.path.isfile(path):
        if required:
            raise FT04ValidationError("required artifact is missing: %s" %
                                      _relative(path))
        return {"path": _relative(path), "exists": False, "sha256": None}
    return {"path": _relative(path), "exists": True, "sha256": _sha256_file(path)}


def _source_records(frame_paths=None):
    paths = OrderedDict((
        ("ft00_protocol", os.path.join(_HERE, "FT00_protocol.json")),
        ("ft00_isolation_audit", os.path.join(_HERE, "FT00_isolation_audit.md")),
        ("protocol_amendment", os.path.join(_HERE, "FT_protocol_amendment_20260911.json")),
        ("ft01_asset_manifest", os.path.join(_HERE, "FT01_asset_manifest.json")),
        ("ft01_asset_audit", os.path.join(_HERE, "FT01_asset_audit.md")),
        ("ft02_runner", os.path.join(_HERE, "ft02_runner.py")),
        ("ft02_technical_audit", os.path.join(_HERE, "FT02_technical_audit.md")),
        ("ft03_runner", os.path.join(_HERE, "ft03_runner.py")),
        ("ft03_validation", os.path.join(_HERE, "FT03_A_validation.json")),
        ("ft03_validation_report", os.path.join(_HERE, "FT03_A_validation_report.md")),
        ("ft03_review", os.path.join(_HERE, "FT03_review.md")),
        ("ft04_runner", os.path.join(_HERE, "ft04_runner.py")),
        ("ft_scheme", os.path.join(_PROJECT_ROOT, "T2WI-HS 生境预后快速验证（FT）方案书.md")),
        ("environment", os.path.join(_PROJECT_ROOT, "environment.yml")),
        ("w07_split", os.path.join(_PROJECT_ROOT, "prognosis_analysis", "output", "outer_splits_A.csv")),
        ("habitat_freeze_lock", os.path.join(_PROJECT_ROOT, "habitat_analysis", "freeze_lock.json")),
        ("w03_candidate_freeze", os.path.join(
            _PROJECT_ROOT, "prognosis_analysis", "output", "w03_habitat_radiomics_A",
            "candidate_freeze.json")),
    ))
    if frame_paths:
        paths.update(frame_paths)
    return OrderedDict((key, _file_record(path)) for key, path in paths.items())


def _environment_fingerprint():
    import matplotlib
    import openpyxl
    import pywt
    import scipy
    import sklearn
    import yaml
    import radiomics
    import SimpleITK

    return OrderedDict((
        ("environment_name", "t2_radiomics"),
        ("environment_file", "environment.yml"),
        ("python", platform.python_version()),
        ("numpy", np.__version__),
        ("pandas", pd.__version__),
        ("scipy", scipy.__version__),
        ("scikit_learn", sklearn.__version__),
        ("matplotlib", matplotlib.__version__),
        ("openpyxl", openpyxl.__version__),
        ("pyyaml", yaml.__version__),
        ("pyradiomics", getattr(radiomics, "__version__", "unknown")),
        ("simpleitk", SimpleITK.Version_VersionString()),
        ("pywavelets", pywt.__version__),
        ("wrapper", "tools/run_t2_radiomics.ps1"),
    ))


def _preprocessor_state(preprocessor):
    clinical = preprocessor.clinical
    global_block = preprocessor.global_block
    radiomics = preprocessor.radiomics
    return OrderedDict((
        ("model_id", preprocessor.model_id),
        ("feature_names", list(preprocessor.feature_names)),
        ("radiomics_blocks", list(preprocessor.radiomics_blocks)),
        ("clinical", OrderedDict((
            ("feature_names", list(clinical.feature_names)),
            ("imputations", dict(clinical.imputations)),
            ("means", dict(clinical.means)),
            ("scales", dict(clinical.scales)),
            ("constant_continuous", list(clinical.constant_continuous)),
        ))),
        ("global_block", None if global_block is None else OrderedDict((
            ("columns", list(global_block.columns)),
            ("medians", dict(global_block.medians)),
            ("means", dict(global_block.means)),
            ("scales", dict(global_block.scales)),
        ))),
        ("radiomics", None if radiomics is None else OrderedDict((
            ("input_columns", list(radiomics.input_columns)),
            ("imputation_medians", dict(radiomics.imputation_medians)),
            ("kept_after_missing", list(radiomics.kept_after_missing)),
            ("kept_after_variance", list(radiomics.kept_after_variance)),
            ("kept_columns", list(radiomics.kept_columns)),
            ("means", dict(radiomics.means)),
            ("scales", dict(radiomics.scales)),
            ("dropped_all_nonfinite", list(radiomics.dropped_all_nonfinite)),
            ("dropped_near_zero_variance", list(radiomics.dropped_near_zero_variance)),
            ("dropped_correlation", list(radiomics.dropped_correlation)),
        ))),
    ))


def _restore_preprocessor(state):
    model_id = state.get("model_id")
    if model_id not in ft02.FT_MODEL_SPECS:
        raise FT04ValidationError("model-state preprocessor has an unknown model")
    prep = ft02.FTPreprocessor(model_id)
    clinical_state = state.get("clinical") or {}
    prep.clinical.feature_names = list(clinical_state.get("feature_names", []))
    prep.clinical.imputations = dict(clinical_state.get("imputations", {}))
    prep.clinical.means = dict(clinical_state.get("means", {}))
    prep.clinical.scales = dict(clinical_state.get("scales", {}))
    prep.clinical.constant_continuous = list(
        clinical_state.get("constant_continuous", []))
    global_state = state.get("global_block")
    if global_state is not None:
        block = ft02._w08.NumericPreprocessor(global_state["columns"])
        block.medians = dict(global_state.get("medians", {}))
        block.means = dict(global_state.get("means", {}))
        block.scales = dict(global_state.get("scales", {}))
        prep.global_block = block
    radiomics_state = state.get("radiomics")
    if radiomics_state is not None:
        block = ft02._w08.RadiomicsPreprocessor(
            radiomics_state["input_columns"])
        block.imputation_medians = dict(radiomics_state.get("imputation_medians", {}))
        block.kept_after_missing = list(radiomics_state.get("kept_after_missing", []))
        block.kept_after_variance = list(radiomics_state.get("kept_after_variance", []))
        block.kept_columns = list(radiomics_state.get("kept_columns", []))
        block.means = dict(radiomics_state.get("means", {}))
        block.scales = dict(radiomics_state.get("scales", {}))
        block.dropped_all_nonfinite = list(
            radiomics_state.get("dropped_all_nonfinite", []))
        block.dropped_near_zero_variance = list(
            radiomics_state.get("dropped_near_zero_variance", []))
        block.dropped_correlation = list(
            radiomics_state.get("dropped_correlation", []))
        prep.radiomics = block
    prep.radiomics_blocks = list(state.get("radiomics_blocks", []))
    prep.feature_names = list(state.get("feature_names", []))
    if not prep.feature_names:
        raise FT04ValidationError("model-state preprocessor is empty")
    return prep


def _model_class(model):
    if isinstance(model, ft02._w08.CoxElasticNetModel):
        return "CoxElasticNetModel"
    if isinstance(model, ft02._w08.CoxPHModel):
        return "CoxPHModel"
    raise FT04ValidationError("unsupported fitted FT model class")


def _restore_model(state):
    model_state = state.get("model") or {}
    class_name = model_state.get("class")
    if class_name == "CoxElasticNetModel":
        model = ft02._w08.CoxElasticNetModel(
            model_state["alpha"], model_state["penalty"],
            max_iter=model_state["max_iter"],
            tolerance=model_state["tolerance"])
    elif class_name == "CoxPHModel":
        model = ft02._w08.CoxPHModel(
            max_iter=model_state["max_iter"],
            tolerance=model_state["tolerance"])
    else:
        raise FT04ValidationError("unknown serialized Cox model class")
    model.coef_ = np.asarray(model_state.get("coef", []), dtype=float)
    model.baseline_times_ = np.asarray(
        model_state.get("baseline_times", []), dtype=float)
    model.baseline_survival_ = np.asarray(
        model_state.get("baseline_survival", []), dtype=float)
    model.fit_audit = model_state.get("fit_audit") or {}
    if model.coef_.ndim != 1 or not model.coef_.size or \
            not np.isfinite(model.coef_).all():
        raise FT04ValidationError("serialized Cox coefficients are invalid")
    if model.baseline_times_.ndim != 1 or model.baseline_survival_.ndim != 1 or \
            len(model.baseline_times_) != len(model.baseline_survival_) or \
            len(model.baseline_times_) == 0:
        raise FT04ValidationError("serialized baseline survival is invalid")
    if not np.isfinite(model.baseline_times_).all() or \
            not np.isfinite(model.baseline_survival_).all():
        raise FT04ValidationError("serialized baseline survival is nonfinite")
    if not model.fit_audit.get("converged") or \
            model.fit_audit.get("fit_status") != "converged":
        raise FT04ValidationError("serialized Cox model is not converged")
    return model


def _raw_predictor_columns(model_id):
    blocks = ft02.FT_MODEL_SPECS[model_id]["blocks"]
    columns = []
    columns.extend(ft02.CLINICAL_COLUMNS)
    if "H_high_fraction" in blocks:
        columns.append("H_high_fraction")
    if "G" in blocks:
        columns.extend(ft02.GLOBAL_COLUMNS)
    for block in ("R_low", "R_high", "W_Original"):
        if block not in blocks:
            continue
        if block == "W_Original":
            columns.append("W_Original_available")
        else:
            columns.extend([block + "_structurally_defined",
                            block + "_technically_available"])
        columns.extend(ft02.BLOCK_PREFIXES[block] + name
                       for name in ft02.BLOCK_FEATURE_NAMES[block])
    return columns


def _model_input_hash(model_id, raw_columns, transformed_columns):
    payload = OrderedDict((
        ("model_id", model_id),
        ("raw_predictor_columns", list(raw_columns)),
        ("transformed_feature_names", list(transformed_columns)),
    ))
    return _sha256_text(_canonical_json(payload))


def _fit_full_model(frame, model_id):
    population = ft02._model_population(model_id)
    mask = ft02.population_mask(frame, population)
    fit_frame = frame.loc[mask].copy().reset_index(drop=True)
    if fit_frame.empty:
        raise FT04ValidationError("empty eligible full-A fitting population: %s" % model_id)
    prep = ft02.FTPreprocessor(model_id).fit(fit_frame)
    X = prep.transform(fit_frame)
    time = fit_frame["DFS_time"].to_numpy(dtype=float)
    event = fit_frame["DFS_event"].to_numpy(dtype=int)
    spec = ft02.FT_MODEL_SPECS[model_id]
    selection = OrderedDict((
        ("alpha", None),
        ("lambda_selection_scope", "not_applicable_unpenalized"),
        ("outer_validation_used_for_lambda", False),
        ("outer_validation_used_for_selection", False),
    ))
    if spec["penalized"]:
        selection = ft02._inner_lambda_selection(
            fit_frame, model_id, SEED, lambda_count=LAMBDA_COUNT,
            max_iter=MAX_ITER, tolerance=TOLERANCE)
        outer_lambda_reference = float(
            ft02._w08._lambda_max(X, time, event, 1.0))
        final_lambda = float(outer_lambda_reference * selection["lambda_ratio"])
        if not np.isfinite(final_lambda) or final_lambda <= 0:
            raise FT04ValidationError("selected full-A lambda is invalid: %s" % model_id)
        model = ft02._w08.CoxElasticNetModel(
            1.0, final_lambda, max_iter=MAX_ITER,
            tolerance=TOLERANCE).fit(X, time, event)
        selection["alpha"] = 1.0
        selection["outer_lambda_reference"] = outer_lambda_reference
        selection["outer_lambda"] = final_lambda
        selection["lambda_reference_scope"] = "full_A_eligible_population"
    else:
        model = ft02._w08.CoxPHModel(
            max_iter=MAX_ITER, tolerance=TOLERANCE).fit(X, time, event)
    ft02._w08._require_converged_model(model, "FT04 full-A %s Cox" % model_id)
    risk = np.asarray(model.predict_risk(X), dtype=float)
    if not np.isfinite(risk).all():
        raise FT04ValidationError("full-A risk is nonfinite: %s" % model_id)
    survival = model.predict_survival(X, HORIZONS)
    if any(not np.isfinite(np.asarray(values, dtype=float)).all()
           for values in survival.values()):
        raise FT04ValidationError("full-A survival is nonfinite: %s" % model_id)
    cutoff = float(np.median(risk))
    if not np.isfinite(cutoff):
        raise FT04ValidationError("full-A cutoff is nonfinite: %s" % model_id)
    raw_columns = _raw_predictor_columns(model_id)
    transformed_columns = list(prep.feature_names)
    model_state = OrderedDict((
        ("schema_version", "1.0"),
        ("artifact_id", "FT04_model_state_%s" % model_id),
        ("stage", FT04_STAGE),
        ("model_id", model_id),
        ("predictor_blocks", list(spec["blocks"])),
        ("population", population),
        ("eligible_n", int(len(fit_frame))),
        ("event_count", int(event.sum())),
        ("raw_predictor_columns", raw_columns),
        ("transformed_feature_names", transformed_columns),
        ("model_input_hash", _model_input_hash(
            model_id, raw_columns, transformed_columns)),
        ("preprocessor", _preprocessor_state(prep)),
        ("model", OrderedDict((
            ("class", _model_class(model)),
            ("family", "Cox"),
            ("alpha", 1.0 if spec["penalized"] else None),
            ("penalty", float(getattr(model, "penalty", 0.0))),
            ("max_iter", int(model.max_iter)),
            ("tolerance", float(model.tolerance)),
            ("coef", model.coef_.tolist()),
            ("baseline_times", model.baseline_times_.tolist()),
            ("baseline_survival", model.baseline_survival_.tolist()),
            ("fit_audit", model.fit_audit),
        ))),
        ("selection", selection),
        ("cutoff", OrderedDict((
            ("rule", "median_full_A_fitted_linear_predictor"),
            ("optimized", False),
            ("value", cutoff),
        ))),
        ("prediction_formula", OrderedDict((
            ("risk", "dot(transformed_features, coef)"),
            ("survival", "S0(horizon) ** exp(clip(risk, -50, 50))"),
            ("horizons_months", dict(HORIZONS)),
        ))),
    ))
    return model_state, model, prep, fit_frame, risk


def _state_summary(state, state_path, state_hash):
    return OrderedDict((
        ("path", _relative(state_path)),
        ("sha256", state_hash),
        ("model_id", state["model_id"]),
        ("population", state["population"]),
        ("eligible_n", state["eligible_n"]),
        ("event_count", state["event_count"]),
        ("predictor_blocks", state["predictor_blocks"]),
        ("raw_predictor_columns", state["raw_predictor_columns"]),
        ("transformed_feature_count", len(state["transformed_feature_names"])),
        ("transformed_feature_order_sha256", _sha256_text(
            _canonical_json(state["transformed_feature_names"]))),
        ("model_input_hash", state["model_input_hash"]),
        ("selection", OrderedDict((
            ("alpha", state["selection"].get("alpha")),
            ("lambda_selection_scope", state["selection"].get(
                "lambda_selection_scope")),
            ("lambda_ratio", state["selection"].get("lambda_ratio")),
            ("outer_lambda", state["selection"].get("outer_lambda")),
            ("inner_folds", state["selection"].get("inner_folds", 0)),
            ("lambda_count", state["selection"].get("lambda_count", 0)),
            ("candidate_attempts", state["selection"].get("candidate_attempts", 0)),
            ("candidate_failures", state["selection"].get("candidate_failures", 0)),
            ("outer_validation_used_for_lambda", state["selection"].get(
                "outer_validation_used_for_lambda", False)),
            ("outer_validation_used_for_selection", state["selection"].get(
                "outer_validation_used_for_selection", False)),
        ))),
        ("cutoff", state["cutoff"]),
        ("fit_converged", bool(state["model"]["fit_audit"].get("converged"))),
    ))


def _lock_identity_payload(lock):
    payload = json.loads(json.dumps(lock))
    payload.pop("lock_identity_sha256", None)
    return payload


def _lock_identity(lock):
    return _sha256_text(_canonical_json(_lock_identity_payload(lock)))


def _formal_lock_state():
    return _file_record(FORMAL_MODEL_LOCK, required=False)


def _build_lock(frame, source_records, state_summaries, started_seconds,
                formal_state, input_sources):
    split, population = ft02.load_frozen_w07_repeat1()
    split = split.copy()
    split["patient_id"] = split["patient_id"].astype(str)
    population = population.copy()
    population["patient_id"] = population["patient_id"].astype(str)
    lock = OrderedDict((
        ("schema_version", "1.0"),
        ("artifact_id", "FT_model_freeze_lock"),
        ("stage", FT04_STAGE),
        ("status", "FROZEN"),
        ("label", FT_LABEL),
        ("analysis_scope", "A-only full_A habitat final refit and deterministic B prediction freeze"),
        ("not_formal_model_freeze_lock", True),
        ("formal_lock_path", "prognosis_analysis/model_freeze_lock.json"),
        ("formal_lock_at_freeze", formal_state),
        ("cohort", OrderedDict((
            ("source", "frozen W07 A393 modeling population"),
            ("split", "A"),
            ("eligible_definition", "complete accepted A393 population, then frozen model-specific technical availability"),
            ("full_A_habitat", True),
            ("row_count", int(len(frame))),
            ("id_hash", ft02._id_hash(frame["patient_id"])),
            ("endpoint", "DFS"),
            ("time_column", "DFS_time"),
            ("event_column", "DFS_event"),
        ))),
        ("habitat_definition", OrderedDict((
            ("definition", "accepted frozen full_A habitat"),
            ("K", 2),
            ("n_init", 100),
            ("R_low", 49),
            ("R_high", 10),
            ("W_Original", 107),
            ("W_Original_order_sha256", ft02.W_ORIGINAL_ORDER_SHA256),
            ("no_refit", True),
        ))),
        ("split", OrderedDict((
            ("repeat", REPEAT),
            ("folds", [1, 2, 3, 4, 5]),
            ("seed", SEED),
            ("regenerated", False),
            ("artifact", "prognosis_analysis/output/outer_splits_A.csv"),
            ("artifact_sha256", ft02.W07_SPLIT_ARTIFACT_SHA256),
            ("repeat1_canonical_sha256", ft02.W07_REPEAT1_CANONICAL_SHA256),
            ("row_count", int(len(split))),
        ))),
        ("model_order", list(MODEL_IDS)),
        ("models", OrderedDict((summary["model_id"], summary)
                                for summary in state_summaries)),
        ("prediction_contract", OrderedDict((
            ("mode", "frozen_state_prediction_only"),
            ("forbidden_on_B", [
                "fit", "lambda_tuning", "feature_selection", "cutoff_optimization",
                "K_means_fit", "habitat_optimization", "preprocessing_estimation",
                "radiomics_reextraction", "model_selection",
            ]),
            ("horizons_months", dict(HORIZONS)),
            ("risk_formula", "dot(frozen_preprocessed_features, frozen_coef)"),
            ("survival_formula", "S0(horizon) ** exp(clip(risk, -50, 50))"),
            ("expected_model_input_hashes", OrderedDict(
                (summary["model_id"], summary["model_input_hash"])
                for summary in state_summaries)),
        ))),
        ("b_access", OrderedDict((
            ("state", "locked"),
            ("b_data_read", False),
            ("b_feature_manifest", "prognosis_analysis/ft/FT05_B_feature_manifest.json"),
            ("b_feature_manifest_required_status", "frozen"),
            ("b_outcome_unlock", "prognosis_analysis/ft/FT05B_outcome_unlock.json"),
            ("b_outcome_read", False),
            ("ft05a_authorized_only_after_independent_ft04_acceptance", True),
            ("ft05a_executed", False),
            ("ft06_executed", False),
        ))),
        ("provenance", OrderedDict((
            ("code_commit", _git_head()),
            ("wrapper", "tools/run_t2_radiomics.ps1"),
            ("environment", _environment_fingerprint()),
            ("environment_file_sha256", source_records["environment"]["sha256"]),
            ("sources", source_records),
            ("input_sources", input_sources),
            ("ft04_runtime_seconds", round(float(started_seconds), 3)),
            ("pre_run_estimate_minutes", PRE_RUN_ESTIMATE_MINUTES),
            ("estimate_basis", {
                "accepted_ft03_runtime_seconds": 9871.243,
                "accepted_ft03_unique_production_fit_groups": 13,
                "estimate_method": "historical FT03 locked-environment runtime; full-A FT04 refit remains a long task",
            }),
            ("long_task_rule", "pre-estimate recorded; no periodic worker polling"),
        ))),
        ("validation", OrderedDict((
            ("all_models_complete", True),
            ("all_model_states_distinct", len(set(
                summary["sha256"] for summary in state_summaries)) == len(state_summaries)),
            ("all_fits_converged", all(summary["fit_converged"]
                                        for summary in state_summaries)),
            ("preprocessing_frozen", True),
            ("cutoffs_non_optimized", True),
            ("b_data_read", False),
            ("formal_outputs_written", False),
            ("formal_lock_unchanged", True),
        ))),
    ))
    lock["lock_identity_sha256"] = _lock_identity(lock)
    return lock


def _write_audit(lock, path):
    lines = [
        "# FT04 Refit and Freeze Audit",
        "",
        "## Status",
        "",
        "`COMPLETE`",
        "",
        "Stage: `FT04` — Full_A Final Refit & Freeze.",
        "Analysis label: `exploratory_fullA_habitat_non_nested_validation`.",
        "The run is A-only and leaves B technical assets, B outcomes, and formal W08/L9 locks unchanged.",
        "",
        "## Frozen models",
        "",
        "| Model | Population | Eligible n | Events | State SHA-256 | Cutoff rule |",
        "|---|---|---:|---:|---|---|",
    ]
    for model_id in MODEL_IDS:
        item = lock["models"][model_id]
        lines.append("| %s | %s | %d | %d | `%s` | `%s` |" % (
            model_id, item["population"], item["eligible_n"], item["event_count"],
            item["sha256"], item["cutoff"]["rule"]))
    lines.extend([
        "",
        "Penalized models use `alpha=1`, 20 candidates, and ordinary training-only inner five-fold selection on the complete eligible full-A fitting population. Unpenalized models retain the accepted Cox specification.",
        "All final states include ordered raw predictors, transformed feature names, preprocessing parameters, coefficients, baseline survival, exact prediction formulas, and deterministic non-optimized cutoffs.",
        "",
        "## Provenance and boundaries",
        "",
        "- Frozen habitat: `K=2`, `n_init=100`, `R_low=49`, `R_high=10`, `W_Original=107`.",
        "- Frozen split binding: W07 repeat 1, five folds, seed `12345`; split regeneration is `false`.",
        "- Endpoint: DFS; prediction horizons: 36 and 60 months.",
        "- B state: locked; FT05A, FT05B, and FT06: not executed.",
        "- Formal lock: `prognosis_analysis/model_freeze_lock.json` unchanged.",
        "- Runtime wrapper: `tools/run_t2_radiomics.ps1`; pre-run long-task estimate: `%d` minutes based on accepted FT03 runtime evidence; no periodic worker polling." % PRE_RUN_ESTIMATE_MINUTES,
        "",
        "## Deliverables",
        "",
        "- `prognosis_analysis/ft/FT_model_freeze_lock.json`",
        "- ignored local FT04 model states under `prognosis_analysis/output/ft_20260910_01a08bf3/FT04/model_states/`",
        "- `prognosis_analysis/ft/ft04_runner.py`",
    ])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def run_ft04(output_root=DEFAULT_OUTPUT_ROOT, lock_path=DEFAULT_LOCK,
             audit_path=DEFAULT_AUDIT):
    """Build the seven final full-A model states and the tracked FT lock."""
    if os.path.exists(FORMAL_MODEL_LOCK):
        formal_state_before = _formal_lock_state()
    else:
        formal_state_before = _formal_lock_state()
    frame = ft03.build_authoritative_a_frame()
    split, population = ft02.load_frozen_w07_repeat1()
    frame = ft02.validate_proven_a_frame(
        frame, population, models=list(MODEL_IDS)).reset_index(drop=True)
    state_root = os.path.join(output_root, "model_states")
    os.makedirs(state_root, exist_ok=True)
    summaries = []
    input_sources = OrderedDict((
        ("a_raw", _file_record(ft03.DEFAULT_RAW_A)),
        ("a_global", _file_record(ft03.DEFAULT_GLOBAL)),
        ("a_r_low", _file_record(ft03.DEFAULT_R_LOW)),
        ("a_r_high", _file_record(ft03.DEFAULT_R_HIGH)),
        ("a_w_original", _file_record(ft03.DEFAULT_W)),
    ))
    source_records = _source_records()
    for model_id in MODEL_IDS:
        state, unused_model, unused_prep, unused_frame, unused_risk = \
            _fit_full_model(frame, model_id)
        state_path = os.path.join(state_root, model_id + ".json")
        _write_json(state_path, state)
        state_hash = _sha256_file(state_path)
        summaries.append(_state_summary(state, state_path, state_hash))
    if len({summary["sha256"] for summary in summaries}) != len(summaries):
        raise FT04ValidationError("final model-state hashes are not distinct")
    formal_state_after = _formal_lock_state()
    if formal_state_before != formal_state_after:
        raise FT04ValidationError("formal model-freeze lock changed during FT04")
    lock = _build_lock(
        frame, source_records, summaries, 0.0,
        formal_state_after, input_sources)
    lock["provenance"]["ft04_runtime_seconds"] = None
    lock["lock_identity_sha256"] = _lock_identity(lock)
    _write_json(lock_path, lock)
    validate_ft_model_freeze_lock(lock_path)
    _write_audit(lock, audit_path)
    return lock


def finalize_ft04_from_existing_states(output_root=DEFAULT_OUTPUT_ROOT,
                                       lock_path=DEFAULT_LOCK,
                                       audit_path=DEFAULT_AUDIT):
    """Finalize an already completed local refit without refitting models."""
    formal_state_before = _formal_lock_state()
    frame = ft03.build_authoritative_a_frame()
    split, population = ft02.load_frozen_w07_repeat1()
    frame = ft02.validate_proven_a_frame(
        frame, population, models=list(MODEL_IDS)).reset_index(drop=True)
    state_root = os.path.join(output_root, "model_states")
    summaries = []
    for model_id in MODEL_IDS:
        state_path = os.path.join(state_root, model_id + ".json")
        state = _read_json(state_path)
        if state.get("stage") != FT04_STAGE or state.get("model_id") != model_id:
            raise FT04ValidationError("existing FT04 state is incomplete: %s" % model_id)
        summaries.append(_state_summary(
            state, state_path, _sha256_file(state_path)))
    if len({summary["sha256"] for summary in summaries}) != len(summaries):
        raise FT04ValidationError("final model-state hashes are not distinct")
    formal_state_after = _formal_lock_state()
    if formal_state_before != formal_state_after:
        raise FT04ValidationError("formal model-freeze lock changed during FT04")
    input_sources = OrderedDict((
        ("a_raw", _file_record(ft03.DEFAULT_RAW_A)),
        ("a_global", _file_record(ft03.DEFAULT_GLOBAL)),
        ("a_r_low", _file_record(ft03.DEFAULT_R_LOW)),
        ("a_r_high", _file_record(ft03.DEFAULT_R_HIGH)),
        ("a_w_original", _file_record(ft03.DEFAULT_W)),
    ))
    lock = _build_lock(
        frame, _source_records(), summaries, 0.0,
        formal_state_after, input_sources)
    lock["provenance"]["ft04_runtime_seconds"] = None
    lock["provenance"]["finalization_mode"] = "existing_completed_local_states"
    lock["lock_identity_sha256"] = _lock_identity(lock)
    _write_json(lock_path, lock)
    validate_ft_model_freeze_lock(lock_path)
    _write_audit(lock, audit_path)
    return lock


def _validate_source_records(records):
    for label, record in records.items():
        if not record.get("exists"):
            raise FT04ValidationError("bound source is missing: %s" % label)
        path = _absolute(record["path"])
        if _sha256_file(path) != record.get("sha256"):
            raise FT04ValidationError("bound source hash mismatch: %s" % label)


def validate_ft_model_freeze_lock(lock_path=DEFAULT_LOCK):
    """Validate lock identity, sources, and every ignored model state."""
    lock = _read_json(lock_path)
    if lock.get("artifact_id") != "FT_model_freeze_lock" or \
            lock.get("stage") != FT04_STAGE or lock.get("status") != "FROZEN":
        raise FT04ValidationError("invalid FT04 lock identity")
    if lock.get("not_formal_model_freeze_lock") is not True or \
            lock.get("formal_lock_path") == lock.get("artifact_id"):
        raise FT04ValidationError("FT04 lock is not separate from the formal lock")
    if lock.get("b_access", {}).get("state") != "locked" or \
            lock.get("b_access", {}).get("b_data_read") is not False:
        raise FT04ValidationError("FT04 lock does not keep B locked")
    identity = lock.get("lock_identity_sha256")
    if identity != _lock_identity(lock):
        raise FT04ValidationError("FT04 lock identity hash mismatch")
    _validate_source_records(lock.get("provenance", {}).get("sources", {}))
    _validate_source_records(lock.get("provenance", {}).get("input_sources", {}))
    models = lock.get("models", {})
    if lock.get("model_order") != list(MODEL_IDS) or \
            set(models) != set(MODEL_IDS):
        raise FT04ValidationError("FT04 lock model set/order mismatch")
    hashes = []
    for model_id in MODEL_IDS:
        summary = models[model_id]
        state_path = _absolute(summary["path"])
        if _sha256_file(state_path) != summary.get("sha256"):
            raise FT04ValidationError("model-state hash mismatch: %s" % model_id)
        state = _read_json(state_path)
        if state.get("model_id") != model_id or \
                state.get("model_input_hash") != summary.get("model_input_hash"):
            raise FT04ValidationError("model-state identity mismatch: %s" % model_id)
        if state.get("cutoff", {}).get("optimized") is not False:
            raise FT04ValidationError("model cutoff is not marked non-optimized: %s" % model_id)
        if not state.get("model", {}).get("fit_audit", {}).get("converged"):
            raise FT04ValidationError("model state is not converged: %s" % model_id)
        hashes.append(summary["sha256"])
    if len(set(hashes)) != len(hashes):
        raise FT04ValidationError("model-state hashes are not distinct")
    expected_hashes = lock.get("prediction_contract", {}).get(
        "expected_model_input_hashes", {})
    if expected_hashes != dict((model_id, models[model_id]["model_input_hash"])
                               for model_id in MODEL_IDS):
        raise FT04ValidationError("prediction input hash binding is inconsistent")
    return lock


def _validate_b_feature_manifest(lock, manifest_path):
    if not os.path.isfile(manifest_path):
        raise FT04ValidationError("FT05_B_feature_manifest.json is required before B prediction")
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_id") != "FT05_B_feature_manifest" or \
            manifest.get("status") != "frozen":
        raise FT04ValidationError("FT05 B feature manifest is not accepted and frozen")
    if manifest.get("ft04_lock_identity_sha256") != lock.get("lock_identity_sha256"):
        raise FT04ValidationError("FT05 B manifest is not bound to this FT04 lock")
    expected = lock["prediction_contract"]["expected_model_input_hashes"]
    if manifest.get("model_input_hashes") != expected:
        raise FT04ValidationError("FT05 B manifest model-input hashes do not match FT04")
    return manifest


def _validate_outcome_unlock(lock, manifest_path, unlock_path):
    if not os.path.isfile(unlock_path):
        raise FT04ValidationError("FT05B outcome-unlock authorization is required")
    unlock = _read_json(unlock_path)
    if unlock.get("artifact_id") != "FT05B_outcome_unlock" or \
            unlock.get("status") != "authorized":
        raise FT04ValidationError("FT05B outcome-unlock authorization is invalid")
    if unlock.get("ft04_lock_identity_sha256") != lock.get("lock_identity_sha256"):
        raise FT04ValidationError("FT05B authorization is not bound to FT04")
    if unlock.get("ft05_manifest_sha256") != _sha256_file(manifest_path):
        raise FT04ValidationError("FT05B authorization is not bound to FT05 manifest")
    return unlock


def _validate_b_predictor_frame(frame, state):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise FT04ValidationError("B predictor frame must be non-empty")
    if "patient_id" not in frame.columns:
        raise FT04ValidationError("B predictor frame lacks patient_id")
    if any(column in frame.columns for column in ("DFS_time", "DFS_event")):
        raise FT04ValidationError("B outcome columns are not accepted in predictor input")
    ids = frame["patient_id"].astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise FT04ValidationError("B predictor IDs must be unique and nonblank")
    if "split" in frame.columns and not frame["split"].astype(str).str.upper().eq("B").all():
        raise FT04ValidationError("B predictor frame has a non-B split")
    for column in frame.columns:
        if str(column).lower().endswith("path") or str(column).lower() in (
                "path", "source_path", "image_path", "roi_path", "input_path", "file_path"):
            raise FT04ValidationError("path columns are not accepted in B predictor input")
    missing = sorted(set(state["raw_predictor_columns"]) - set(frame.columns))
    if missing:
        raise FT04ValidationError("B predictor frame is missing frozen columns")
    model_id = state["model_id"]
    for block in ("R_low", "R_high", "W_Original"):
        if block not in state["predictor_blocks"]:
            continue
        availability = ("W_Original_available" if block == "W_Original" else
                        block + "_technically_available")
        structural = None if block == "W_Original" else block + "_structurally_defined"
        values = pd.to_numeric(frame[availability], errors="coerce")
        if values.isna().any() or not values.isin([1]).all():
            raise FT04ValidationError("B predictor block is not fully available: %s" % block)
        if structural is not None:
            structural_values = pd.to_numeric(frame[structural], errors="coerce")
            if structural_values.isna().any() or not structural_values.isin([1]).all():
                raise FT04ValidationError("B predictor block is not structurally defined: %s" % block)
    return frame.copy()


def load_frozen_prediction_state(lock_path, model_id):
    lock = validate_ft_model_freeze_lock(lock_path)
    if model_id not in MODEL_IDS:
        raise FT04ValidationError("unknown frozen FT model")
    state_path = _absolute(lock["models"][model_id]["path"])
    state = _read_json(state_path)
    model = _restore_model(state)
    preprocessor = _restore_preprocessor(state["preprocessor"])
    if len(model.coef_) != len(preprocessor.feature_names):
        raise FT04ValidationError("frozen coefficient/feature count mismatch")
    return lock, state, model, preprocessor


def predict_b_from_frozen(feature_frame, model_id, lock_path=DEFAULT_LOCK,
                          manifest_path=FT05_MANIFEST, outcomes_requested=False):
    """Predict B risk/survival only after the later FT05 locks validate."""
    lock, state, model, preprocessor = load_frozen_prediction_state(
        lock_path, model_id)
    _validate_b_feature_manifest(lock, manifest_path)
    if outcomes_requested:
        _validate_outcome_unlock(lock, manifest_path, FT05B_UNLOCK)
    checked = _validate_b_predictor_frame(feature_frame, state)
    X = preprocessor.transform(checked)
    risk = np.asarray(model.predict_risk(X), dtype=float)
    survival = model.predict_survival(X, HORIZONS)
    if not np.isfinite(risk).all():
        raise FT04ValidationError("frozen B risk is nonfinite")
    output = OrderedDict((
        ("patient_id", checked["patient_id"].astype(str).tolist()),
        ("risk", risk),
        ("survival_probability_36", np.asarray(survival["3_year"], dtype=float)),
        ("survival_probability_60", np.asarray(survival["5_year"], dtype=float)),
    ))
    return pd.DataFrame(output)


def evaluate_b_from_frozen(feature_frame, outcome_frame, model_id,
                           lock_path=DEFAULT_LOCK, manifest_path=FT05_MANIFEST):
    """Evaluate frozen predictions only when FT05B explicitly unlocks outcomes."""
    prediction = predict_b_from_frozen(
        feature_frame, model_id, lock_path=lock_path,
        manifest_path=manifest_path, outcomes_requested=True)
    if not isinstance(outcome_frame, pd.DataFrame):
        raise FT04ValidationError("B outcome frame must be a DataFrame")
    required = {"patient_id", "DFS_time", "DFS_event"}
    if not required.issubset(outcome_frame.columns):
        raise FT04ValidationError("B outcome frame lacks the frozen DFS endpoint")
    outcome = outcome_frame[list(required)].copy()
    outcome["patient_id"] = outcome["patient_id"].astype(str).str.strip()
    if outcome["patient_id"].eq("").any() or outcome["patient_id"].duplicated().any():
        raise FT04ValidationError("B outcome IDs must be unique and nonblank")
    if set(outcome["patient_id"]) != set(prediction["patient_id"]):
        raise FT04ValidationError("B outcomes do not exactly cover predictions")
    outcome = outcome.set_index("patient_id").loc[prediction["patient_id"]].reset_index()
    time = pd.to_numeric(outcome["DFS_time"], errors="coerce").to_numpy(dtype=float)
    event = pd.to_numeric(outcome["DFS_event"], errors="coerce").to_numpy(dtype=int)
    if not np.isfinite(time).all() or (time <= 0).any() or not np.isin(event, [0, 1]).all():
        raise FT04ValidationError("B DFS outcome values are invalid")
    risk = prediction["risk"].to_numpy(dtype=float)
    return OrderedDict((
        ("model_id", model_id),
        ("n", int(len(outcome))),
        ("event_count", int(event.sum())),
        ("harrell_c_index", ft02.harrell_c_index_hook(time, event, risk)),
        ("prediction", prediction),
    ))


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("run", "validate"))
    parser.add_argument("--lock", default=DEFAULT_LOCK)
    parser.add_argument("--audit", default=DEFAULT_AUDIT)
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT)
    args = parser.parse_args()
    if args.command == "run":
        lock = run_ft04(args.output_root, args.lock, args.audit)
        print(json.dumps({
            "status": lock["status"],
            "artifact_id": lock["artifact_id"],
            "models": list(lock["models"]),
            "state_hashes": dict((key, value["sha256"])
                                  for key, value in lock["models"].items()),
            "lock_identity_sha256": lock["lock_identity_sha256"],
        }, sort_keys=True))
    else:
        lock = validate_ft_model_freeze_lock(args.lock)
        print(json.dumps({
            "status": "VALID",
            "artifact_id": lock["artifact_id"],
            "lock_identity_sha256": lock["lock_identity_sha256"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
