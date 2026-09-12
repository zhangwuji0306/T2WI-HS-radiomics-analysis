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
import re
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
FT04_REVIEW = os.path.join(_HERE, "FT04_review.md")
FT05_MANIFEST = os.path.join(_HERE, "FT05_B_feature_manifest.json")
FT_B_UNLOCK = os.path.join(_HERE, "FT_B_unlock.json")
FT04_LOCK_DIGEST = os.path.join(_HERE, "FT04_lock_sha256.json")
FT05A_TECHNICAL_AUDIT = os.path.join(
    _HERE, "FT05A_B_technical_generation_audit.md")
FT05A_CODE_AUDIT = os.path.join(_HERE, "FT05A_code_audit.md")
FORMAL_MODEL_LOCK = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "model_freeze_lock.json")

# This is the immutable first-round FT04 implementation commit.  The final
# remediation commit is intentionally not embedded in the lock: doing so
# would make the lock assert a hash for the commit that contains the lock.
FT04_IMPLEMENTATION_SOURCE_COMMIT = (
    "8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d")
R_LOW_CANDIDATE_HASH = (
    "a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0")
R_HIGH_CANDIDATE_HASH = (
    "a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce")


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


def _accepted_w_original_binding():
    """Return the accepted FT01 W_Original binding without reading the asset."""
    manifest_path = os.path.join(_HERE, "FT01_asset_manifest.json")
    manifest = _read_json(manifest_path)
    asset = manifest.get("W_Original_asset") or {}
    canonical = manifest.get("W_Original_canonical_order") or {}
    b_asset = (manifest.get("b_technical_audit") or {}).get("W_Original") or {}
    asset_path = asset.get("path")
    if asset_path != canonical.get("source_asset_path") or \
            asset.get("exists") is not True or \
            b_asset.get("existing_asset") is not True or \
            asset.get("non_original_feature_column_count") != 0:
        raise FT04ValidationError("accepted FT01 W_Original metadata is invalid")
    feature_count = asset.get("original_feature_count")
    order_sha256 = asset.get("original_feature_order_sha256")
    if feature_count != 107 or order_sha256 != ft02.W_ORIGINAL_ORDER_SHA256:
        raise FT04ValidationError("accepted FT01 W_Original schema is invalid")
    source_records = manifest.get("source_files") or []
    matches = [record for record in source_records
               if record.get("path") == asset_path]
    if len(matches) != 1 or matches[0].get("exists") is not True:
        raise FT04ValidationError("accepted FT01 W_Original asset record is missing")
    asset_sha256 = matches[0].get("sha256")
    if not re.match(r"^[0-9a-f]{64}$", str(asset_sha256)):
        raise FT04ValidationError("accepted FT01 W_Original asset hash is invalid")
    return OrderedDict((
        ("path", asset_path),
        ("asset_sha256", asset_sha256),
        ("feature_count", 107),
        ("order_sha256", order_sha256),
        ("reused_existing_asset", True),
        ("reextracted", False),
    ))


def _git_head():
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=_PROJECT_ROOT,
            stderr=subprocess.STDOUT).decode("ascii").strip()
        return value if len(value) == 40 else None
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return None


def _git_text(arguments):
    try:
        return subprocess.check_output(
            ["git"] + list(arguments), cwd=_PROJECT_ROOT,
            stderr=subprocess.STDOUT).decode("ascii").strip()
    except (OSError, subprocess.CalledProcessError, UnicodeError):
        return None


def _git_commit_resolves(commit):
    if not isinstance(commit, str) or not re.match(r"^[0-9a-f]{40}$", commit):
        return False
    resolved = _git_text(["rev-parse", "%s^{commit}" % commit])
    return resolved == commit


def _git_commit_is_ancestor(commit):
    head = _git_head()
    if not head or not _git_commit_resolves(commit):
        return False
    try:
        subprocess.check_call(
            ["git", "merge-base", "--is-ancestor", commit, head],
            cwd=_PROJECT_ROOT, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _git_commit_has_path(commit, relative_path):
    if not _git_commit_resolves(commit):
        return False
    if not isinstance(relative_path, str) or os.path.isabs(relative_path):
        return False
    value = _git_text(["cat-file", "-e", "%s:%s" %
                       (commit, relative_path)])
    return value == ""


def _validate_git_commit_binding(commit, role, paths):
    if not _git_commit_resolves(commit):
        raise FT04ValidationError("%s does not resolve to a Git commit" % role)
    if not _git_commit_is_ancestor(commit):
        raise FT04ValidationError("%s is not an ancestor of the current branch" % role)
    if not paths or any(not _git_commit_has_path(commit, path) for path in paths):
        raise FT04ValidationError("%s does not contain its declared FT04 files" % role)


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
        ("w03_radiomics_protocol", os.path.join(
            _PROJECT_ROOT, "prognosis_analysis", "W03_habitat_radiomics_protocol.md")),
        ("w03_radiomics_config", os.path.join(
            _PROJECT_ROOT, "prognosis_analysis", "configs", "w03_habitat_radiomics.json")),
        ("radiomics_parameter_file", os.path.join(
            _PROJECT_ROOT, "feature_extract", "configs", "radiomics_params.yaml")),
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


def _write_lock_digest(lock_path=DEFAULT_LOCK, digest_path=FT04_LOCK_DIGEST):
    payload = OrderedDict((
        ("schema_version", "1.0"),
        ("artifact_id", "FT04_lock_sha256_attestation"),
        ("status", "canonical"),
        ("hash_algorithm", "SHA-256"),
        ("lock_path", _relative(lock_path)),
        ("lock_sha256", _sha256_file(lock_path)),
        ("self_referential", False),
    ))
    _write_json(digest_path, payload)
    return payload


def _validate_lock_digest(lock_path):
    if not os.path.isfile(FT04_LOCK_DIGEST):
        raise FT04ValidationError("canonical FT04 lock digest attestation is required")
    digest = _read_json(FT04_LOCK_DIGEST)
    if digest.get("schema_version") != "1.0" or \
            digest.get("artifact_id") != "FT04_lock_sha256_attestation" or \
            digest.get("status") != "canonical" or \
            digest.get("hash_algorithm") != "SHA-256" or \
            digest.get("self_referential") is not False:
        raise FT04ValidationError("FT04 lock digest attestation is invalid")
    if digest.get("lock_path") != _relative(lock_path):
        raise FT04ValidationError("FT04 lock digest attestation path mismatch")
    lock_sha256 = digest.get("lock_sha256")
    if not re.match(r"^[0-9a-f]{64}$", str(lock_sha256)):
        raise FT04ValidationError("FT04 lock digest attestation hash is invalid")
    if _sha256_file(lock_path) != lock_sha256:
        raise FT04ValidationError("FT04 lock serialized bytes do not match canonical digest")
    return digest


def _formal_lock_state():
    return _file_record(FORMAL_MODEL_LOCK, required=False)


def _frozen_a_boundary_identity(lock):
    payload = OrderedDict((
        ("definition", lock.get("habitat_definition")),
        ("full_A_habitat", lock.get("cohort", {}).get("full_A_habitat")),
        ("source_hashes", OrderedDict((
            (key, lock.get("provenance", {}).get("sources", {}).get(
                key, {}).get("sha256"))
            for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                        "w03_candidate_freeze")
        ))),
    ))
    return _sha256_text(_canonical_json(payload))


def _pyradiomics_provenance(source_records):
    return OrderedDict((
        ("scope", "identical_A_and_W03_configuration_and_provenance"),
        ("configuration_path", source_records["w03_radiomics_config"]["path"]),
        ("configuration_sha256", source_records["w03_radiomics_config"]["sha256"]),
        ("protocol_path", source_records["w03_radiomics_protocol"]["path"]),
        ("protocol_sha256", source_records["w03_radiomics_protocol"]["sha256"]),
        ("parameter_file_path", source_records["radiomics_parameter_file"]["path"]),
        ("parameter_file_sha256", source_records["radiomics_parameter_file"]["sha256"]),
    ))


def _git_binding(source_records, attestation_parent):
    runner_path = source_records["ft04_runner"]["path"]
    lock_path = _relative(DEFAULT_LOCK)
    return OrderedDict((
        ("implementation_source_commit", FT04_IMPLEMENTATION_SOURCE_COMMIT),
        ("implementation_source_role",
         "immutable first-round FT04 implementation/source commit; it contains the reviewed FT04 runner and lock version"),
        ("implementation_source_paths", [
            "prognosis_analysis/ft/ft04_runner.py",
            "prognosis_analysis/ft/FT_model_freeze_lock.json",
        ]),
        ("attestation_parent_commit", attestation_parent),
        ("attestation_parent_role",
         "preceding local FT04 remediation commit; it is not claimed to contain the final attestation"),
        ("attestation_parent_paths", [
            "prognosis_analysis/ft/ft04_runner.py",
            "prognosis_analysis/ft/FT_model_freeze_lock.json",
        ]),
        ("final_attestation_commit", OrderedDict((
            ("hash_embedded", False),
            ("role", "local child commit recording the final FT04 lock and audit"),
            ("reason_not_embedded", "embedding it would make the lock self-referential"),
            ("parent_commit", attestation_parent),
        ))),
        ("current_file_bindings", OrderedDict((
            ("ft04_runner", OrderedDict((
                ("path", runner_path),
                ("sha256", source_records["ft04_runner"]["sha256"]),
            ))),
            ("ft04_lock", OrderedDict((
                ("path", lock_path),
                ("hash_type", "exact_serialized_file_sha256"),
                ("sha256_embedded", False),
                ("digest_attestation_path", _relative(FT04_LOCK_DIGEST)),
            ))),
        ))),
    ))


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
            ("R_low_candidate_hash", R_LOW_CANDIDATE_HASH),
            ("R_high", 10),
            ("R_high_candidate_hash", R_HIGH_CANDIDATE_HASH),
            ("W_Original", 107),
            ("W_Original_order_sha256", ft02.W_ORIGINAL_ORDER_SHA256),
            ("W_Original_asset", _accepted_w_original_binding()),
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
            ("b_outcome_unlock", "prognosis_analysis/ft/FT_B_unlock.json"),
            ("b_outcome_read", False),
            ("ft05a_authorized_only_after_independent_ft04_acceptance", True),
            ("ft05a_executed", False),
            ("ft06_executed", False),
        ))),
        ("provenance", OrderedDict((
            ("git_binding", _git_binding(source_records, _git_head())),
            ("wrapper", "tools/run_t2_radiomics.ps1"),
            ("environment", _environment_fingerprint()),
            ("environment_file_sha256", source_records["environment"]["sha256"]),
            ("pyradiomics", _pyradiomics_provenance(source_records)),
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


def _write_audit(lock, path, lock_path=DEFAULT_LOCK):
    git_binding = lock["provenance"]["git_binding"]
    runner_binding = git_binding["current_file_bindings"]["ft04_runner"]
    lock_file_sha256 = _sha256_file(lock_path)
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
        "- Frozen habitat: `K=2`, `n_init=100`, `R_low=49` (candidate hash `%s`), `R_high=10` (candidate hash `%s`), `W_Original=107` (order hash `%s`)." % (
            R_LOW_CANDIDATE_HASH, R_HIGH_CANDIDATE_HASH,
            ft02.W_ORIGINAL_ORDER_SHA256),
        "- W_Original binding: reuse-only accepted existing asset `%s` with asset SHA-256 `%s`; feature count `107`, order SHA-256 `%s`, and re-extraction `false`." % (
            lock["habitat_definition"]["W_Original_asset"]["path"],
            lock["habitat_definition"]["W_Original_asset"]["asset_sha256"],
            lock["habitat_definition"]["W_Original_asset"]["order_sha256"]),
        "- Frozen split binding: W07 repeat 1, five folds, seed `12345`; split regeneration is `false`.",
        "- Endpoint: DFS; prediction horizons: 36 and 60 months.",
        "- B state: locked; FT05A, FT05B, and FT06: not executed.",
        "- Formal lock: `prognosis_analysis/model_freeze_lock.json` unchanged.",
        "- Immutable implementation/source commit: `%s`; it contains the first-round reviewed FT04 runner and lock version. It is distinct from the remediation attestation." % git_binding["implementation_source_commit"],
        "- Attestation parent commit: `%s`; it contains the preceding FT04 remediation state and is not claimed to contain the final attestation." % git_binding["attestation_parent_commit"],
        "- The final local attestation commit is the child that records the remediation lock and this audit. Its hash is intentionally not embedded in the lock, avoiding a self-referential commit claim." ,
        "- Current FT04 runner SHA-256: `%s`; serialized FT04 lock file SHA-256: `%s` (canonical attestation: `prognosis_analysis/ft/FT04_lock_sha256.json`); lock payload identity SHA-256: `%s`." % (
            runner_binding["sha256"], lock_file_sha256,
            lock["lock_identity_sha256"]),
        "- PyRadiomics configuration/provenance is bound to the accepted A/W03 files by SHA-256 in `provenance.pyradiomics`.",
        "- B prediction is fail-closed on the canonical `FT05_B_feature_manifest.json`, an accepted independent FT04 review bound to the current lock/code, and the complete FT05A table/block/provenance/review contract.",
        "- B outcome evaluation additionally requires the canonical `FT_B_unlock.json`; prediction-only loading does not read or require B outcomes.",
        "- Runtime wrapper: `tools/run_t2_radiomics.ps1`; pre-run long-task estimate: `%d` minutes based on accepted FT03 runtime evidence; no periodic worker polling." % PRE_RUN_ESTIMATE_MINUTES,
        "",
        "## Validation",
        "",
        "- The seven existing FT04 model states reload in `t2_radiomics` and reproduce their frozen risk/survival outputs; their hashes are preserved.",
        "- `tests/test_ft04_runner.py`: 23 synthetic/contract tests passed, including canonical-path, Git-binding, review-gate, complete-manifest, hash/provenance, W_Original binding, outcome-unlock, tamper, and formal-lock negative coverage.",
        "- FT04 plus accepted FT03/FT02/W07 wrapper regression suite: 64 tests passed.",
        "",
        "## Deliverables",
        "",
        "- `prognosis_analysis/ft/FT_model_freeze_lock.json`",
        "- `prognosis_analysis/ft/FT04_lock_sha256.json`",
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
    _write_lock_digest(lock_path)
    validate_ft_model_freeze_lock(lock_path)
    _write_audit(lock, audit_path, lock_path)
    return lock


def _remediation_input_sources(previous_lock):
    """Reuse accepted source metadata without opening the W_Original asset."""
    previous = previous_lock.get("provenance", {}).get("input_sources") or {}
    if not previous:
        raise FT04ValidationError("existing FT04 input-source metadata is missing")
    sources = OrderedDict((key, value) for key, value in previous.items())
    accepted_w = _accepted_w_original_binding()
    current_w = sources.get("a_w_original") or {}
    if current_w.get("path") != accepted_w["path"] or \
            current_w.get("sha256") != accepted_w["asset_sha256"] or \
            current_w.get("exists") is not True:
        raise FT04ValidationError("existing FT04 W_Original source metadata is inconsistent")
    sources["a_w_original"] = OrderedDict((
        ("exists", True),
        ("path", accepted_w["path"]),
        ("sha256", accepted_w["asset_sha256"]),
    ))
    return sources


def finalize_ft04_from_existing_states(output_root=DEFAULT_OUTPUT_ROOT,
                                       lock_path=DEFAULT_LOCK,
                                       audit_path=DEFAULT_AUDIT):
    """Reissue FT04 provenance from completed states without reading B data."""
    previous_lock = _read_json(lock_path)
    formal_state_before = _formal_lock_state()
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
    lock = OrderedDict((key, value) for key, value in previous_lock.items())
    lock["habitat_definition"] = OrderedDict(
        (key, value) for key, value in lock["habitat_definition"].items())
    lock["habitat_definition"]["W_Original_asset"] = \
        _accepted_w_original_binding()
    lock["models"] = OrderedDict(
        (summary["model_id"], summary) for summary in summaries)
    lock["provenance"] = OrderedDict(
        (key, value) for key, value in lock["provenance"].items())
    lock["provenance"]["git_binding"] = _git_binding(
        _source_records(), _git_head())
    lock["provenance"]["sources"] = _source_records()
    lock["provenance"]["input_sources"] = _remediation_input_sources(previous_lock)
    lock["provenance"]["finalization_mode"] = "existing_completed_local_states"
    lock["formal_lock_at_freeze"] = formal_state_after
    lock["validation"] = OrderedDict(
        (key, value) for key, value in lock.get("validation", {}).items())
    lock["validation"]["formal_lock_unchanged"] = True
    lock["lock_identity_sha256"] = _lock_identity(lock)
    _write_json(lock_path, lock)
    _write_lock_digest(lock_path)
    validate_ft_model_freeze_lock(lock_path)
    _write_audit(lock, audit_path, lock_path)
    return lock


def _validate_source_records(records):
    if not isinstance(records, dict) or not records:
        raise FT04ValidationError("FT04 provenance source records are missing")
    for label, record in records.items():
        if not record.get("exists"):
            raise FT04ValidationError("bound source is missing: %s" % label)
        path = _absolute(record["path"])
        if _sha256_file(path) != record.get("sha256"):
            raise FT04ValidationError("bound source hash mismatch: %s" % label)


def _validate_input_source_records(records):
    if not isinstance(records, dict) or not records:
        raise FT04ValidationError("FT04 input-source records are missing")
    accepted_w = _accepted_w_original_binding()
    for label, record in records.items():
        if label == "a_w_original":
            if record.get("exists") is not True or \
                    record.get("path") != accepted_w["path"] or \
                    record.get("sha256") != accepted_w["asset_sha256"]:
                raise FT04ValidationError("accepted W_Original source binding mismatch")
            continue
        if not record.get("exists"):
            raise FT04ValidationError("bound input source is missing: %s" % label)
        path = _absolute(record["path"])
        if _sha256_file(path) != record.get("sha256"):
            raise FT04ValidationError("bound input source hash mismatch: %s" % label)


def _validate_candidate_contract(lock):
    habitat = lock.get("habitat_definition") or {}
    expected = {
        "K": 2,
        "n_init": 100,
        "R_low": 49,
        "R_low_candidate_hash": R_LOW_CANDIDATE_HASH,
        "R_high": 10,
        "R_high_candidate_hash": R_HIGH_CANDIDATE_HASH,
        "W_Original": 107,
        "W_Original_order_sha256": ft02.W_ORIGINAL_ORDER_SHA256,
        "no_refit": True,
    }
    for key, value in expected.items():
        if habitat.get(key) != value:
            raise FT04ValidationError("FT04 frozen habitat contract mismatch: %s" % key)
    if habitat.get("W_Original_asset") != _accepted_w_original_binding():
        raise FT04ValidationError("FT04 W_Original asset binding mismatch")


def _validate_git_binding(lock):
    provenance = lock.get("provenance") or {}
    if "code_commit" in provenance:
        raise FT04ValidationError("legacy non-specific code_commit binding is forbidden")
    binding = provenance.get("git_binding") or {}
    implementation = binding.get("implementation_source_commit")
    attestation_parent = binding.get("attestation_parent_commit")
    _validate_git_commit_binding(
        implementation, "implementation source commit",
        binding.get("implementation_source_paths"))
    _validate_git_commit_binding(
        attestation_parent, "attestation parent commit",
        binding.get("attestation_parent_paths"))
    if implementation == attestation_parent:
        raise FT04ValidationError("implementation and attestation commits are not distinct")
    source_paths = binding.get("implementation_source_paths")
    parent_paths = binding.get("attestation_parent_paths")
    expected_paths = [
        "prognosis_analysis/ft/ft04_runner.py",
        "prognosis_analysis/ft/FT_model_freeze_lock.json",
    ]
    if source_paths != expected_paths or parent_paths != expected_paths:
        raise FT04ValidationError("FT04 Git role paths are incomplete")
    final_attestation = binding.get("final_attestation_commit") or {}
    if final_attestation.get("hash_embedded") is not False or \
            final_attestation.get("parent_commit") != attestation_parent:
        raise FT04ValidationError("FT04 attestation binding is circular or incomplete")
    current_files = binding.get("current_file_bindings") or {}
    runner = current_files.get("ft04_runner") or {}
    lock_file = current_files.get("ft04_lock") or {}
    if runner.get("path") != "prognosis_analysis/ft/ft04_runner.py" or \
            not re.match(r"^[0-9a-f]{64}$", str(runner.get("sha256", ""))):
        raise FT04ValidationError("current FT04 runner file binding is invalid")
    current_runner = _absolute(runner["path"])
    if _sha256_file(current_runner) != runner["sha256"]:
        raise FT04ValidationError("current FT04 runner file SHA-256 mismatch")
    source_runner = provenance.get("sources", {}).get("ft04_runner", {})
    if source_runner.get("sha256") != runner.get("sha256"):
        raise FT04ValidationError("FT04 runner source and Git bindings disagree")
    if set(lock_file) != {"path", "hash_type", "sha256_embedded",
                          "digest_attestation_path"} or \
            lock_file.get("path") != _relative(DEFAULT_LOCK) or \
            lock_file.get("hash_type") != "exact_serialized_file_sha256" or \
            lock_file.get("sha256_embedded") is not False or \
            lock_file.get("digest_attestation_path") != _relative(FT04_LOCK_DIGEST):
        raise FT04ValidationError("current FT04 lock binding is invalid")


def _validate_pyradiomics_binding(lock):
    provenance = lock.get("provenance") or {}
    sources = provenance.get("sources") or {}
    expected = {
        "configuration_path": "w03_radiomics_config",
        "configuration_sha256": "w03_radiomics_config",
        "protocol_path": "w03_radiomics_protocol",
        "protocol_sha256": "w03_radiomics_protocol",
        "parameter_file_path": "radiomics_parameter_file",
        "parameter_file_sha256": "radiomics_parameter_file",
    }
    record = provenance.get("pyradiomics") or {}
    if record.get("scope") != "identical_A_and_W03_configuration_and_provenance":
        raise FT04ValidationError("A/W03 PyRadiomics provenance scope is invalid")
    for record_key, source_key in expected.items():
        source = sources.get(source_key) or {}
        expected_value = source.get("path") if record_key.endswith("_path") else source.get("sha256")
        if record.get(record_key) != expected_value:
            raise FT04ValidationError("A/W03 PyRadiomics binding mismatch: %s" % record_key)


def _canonical_artifact_path(requested, canonical, label):
    if requested is None:
        return canonical
    if os.path.normcase(os.path.abspath(requested)) != \
            os.path.normcase(os.path.abspath(canonical)):
        raise FT04ValidationError("%s must use its canonical path" % label)
    return canonical


def _read_text(path, label):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (IOError, OSError, UnicodeError) as exc:
        raise FT04ValidationError("cannot read %s: %s" % (label, exc))


def _marker_digest(text, label):
    pattern = r"(?im)^\s*(?:[-*]\s*)?`?%s`?\s*(?:SHA-256)?\s*[:=]\s*`?([0-9a-f]{64})`?\s*$" % re.escape(label)
    match = re.search(pattern, text)
    if not match:
        raise FT04ValidationError("review is not bound to %s" % label)
    return match.group(1).lower()


def _marker_commit(text, label):
    pattern = r"(?im)^\s*(?:[-*]\s*)?`?%s`?\s*[:=]\s*`?([0-9a-f]{40})`?\s*$" % re.escape(label)
    match = re.search(pattern, text)
    if not match:
        raise FT04ValidationError("review is not bound to %s" % label)
    return match.group(1).lower()


def _validate_ft04_review(lock, lock_path=DEFAULT_LOCK):
    path = _canonical_artifact_path(None, FT04_REVIEW, "FT04 review")
    if not os.path.isfile(path):
        raise FT04ValidationError("accepted independent FT04 review is required")
    text = _read_text(path, "FT04 review")
    lowered = text.lower()
    if re.search(r"not\s+accepted\s+for\s+downstream\s+use", lowered):
        raise FT04ValidationError("FT04 review disposition is not accepted")
    accepted = re.search(
        r"(?im)^\s*(?:(?:disposition|status)\s*[:：]\s*)?`?accepted\s+for\s+downstream\s+use`?\s*$",
        text)
    if not accepted:
        raise FT04ValidationError("FT04 review disposition is not accepted")
    if not re.search(r"(?i)independent\s+(?:review|reviewer)|independent\s*[:：=]\s*true", text):
        raise FT04ValidationError("FT04 review is not marked independent")
    lock_identity = _marker_digest(text, "FT04 lock identity")
    lock_sha256 = _marker_digest(text, "FT04 lock file")
    runner_sha = _marker_digest(text, "FT04 runner")
    if lock_identity != lock.get("lock_identity_sha256"):
        raise FT04ValidationError("FT04 review is bound to a different lock")
    if lock_sha256 != _sha256_file(lock_path):
        raise FT04ValidationError("FT04 review is bound to different serialized lock bytes")
    digest = _validate_lock_digest(lock_path)
    if lock_sha256 != digest.get("lock_sha256"):
        raise FT04ValidationError("FT04 review does not attest the canonical lock digest")
    expected_runner = lock["provenance"]["git_binding"]["current_file_bindings"][
        "ft04_runner"]["sha256"]
    if runner_sha != expected_runner:
        raise FT04ValidationError("FT04 review is bound to different FT04 code")
    reviewed_commit = _marker_commit(text, "FT04 reviewed remediation commit")
    _validate_git_commit_binding(
        reviewed_commit, "reviewed FT04 remediation commit",
        ["prognosis_analysis/ft/ft04_runner.py",
         "prognosis_analysis/ft/FT_model_freeze_lock.json"])
    return text


def _validate_ft_output_path(relative_path, label):
    if not isinstance(relative_path, str) or os.path.isabs(relative_path):
        raise FT04ValidationError("%s must be a relative FT output path" % label)
    normalized = relative_path.replace("\\", "/")
    prefix = "prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/"
    if not normalized.startswith(prefix):
        raise FT04ValidationError("%s is outside the FT05A output namespace" % label)
    lowered = normalized.lower()
    if any(token in lowered for token in ("formal", "/w08/", "/l9/")):
        raise FT04ValidationError("%s mixes with a formal output namespace" % label)
    return _absolute(normalized)


def _validate_nonformal_relative_path(relative_path, label):
    if not isinstance(relative_path, str) or os.path.isabs(relative_path):
        raise FT04ValidationError("%s must be a relative project path" % label)
    normalized = relative_path.replace("\\", "/")
    lowered = normalized.lower()
    if any(token in lowered for token in ("formal", "/w08/", "/l9/")):
        raise FT04ValidationError("%s mixes with a formal output namespace" % label)
    return _absolute(normalized)


def _technical_feature_columns():
    columns = ["patient_id"]
    for block in ("R_low", "R_high"):
        columns.extend([block + "_structurally_defined",
                        block + "_technically_available"])
        columns.extend(ft02.BLOCK_PREFIXES[block] + name
                       for name in ft02.BLOCK_FEATURE_NAMES[block])
    columns.append("W_Original_available")
    columns.extend(ft02.BLOCK_PREFIXES["W_Original"] + name
                   for name in ft02.BLOCK_FEATURE_NAMES["W_Original"])
    return columns


def _canonical_b_feature_columns():
    columns = ["patient_id"]
    columns.extend(ft02.CLINICAL_COLUMNS)
    for column in ("H_high_fraction",) + tuple(ft02.GLOBAL_COLUMNS):
        if column not in columns:
            columns.append(column)
    columns.extend(column for column in _technical_feature_columns()
                   if column != "patient_id")
    return columns


def _validate_ft05a_review_artifact(record, canonical_path, label):
    if not isinstance(record, dict) or record.get("path") != _relative(canonical_path):
        raise FT04ValidationError("%s path is not canonical" % label)
    if record.get("status") != "accepted" or record.get("independent") is not True or \
            record.get("verdict") not in ("PASS", "PASS_WITH_FINDINGS"):
        raise FT04ValidationError("%s is not accepted" % label)
    if not re.match(r"^[0-9a-f]{64}$", str(record.get("sha256", ""))):
        raise FT04ValidationError("%s hash is invalid" % label)
    path = _absolute(record["path"])
    if _sha256_file(path) != record["sha256"]:
        raise FT04ValidationError("%s hash mismatch" % label)
    text = _read_text(path, label)
    if not re.search(r"(?i)independent", text) or \
            not re.search(r"(?im)^\s*(?:verdict|status)\s*[:：]\s*(?:PASS|PASS_WITH_FINDINGS|accepted)\s*$", text):
        raise FT04ValidationError("%s content is incomplete" % label)


def _validate_ft05a_feature_table(manifest):
    table_record = manifest.get("feature_table") or {}
    required_keys = (
        "path", "sha256", "format", "complete", "columns", "row_count",
        "patient_id_column", "patient_count", "patient_ids_unique",
        "duplicate_patient_count", "duplicate_extraction_count",
        "extraction_count")
    if any(key not in table_record for key in required_keys):
        raise FT04ValidationError("FT05A feature-table completeness record is incomplete")
    table_path = _validate_ft_output_path(table_record["path"], "FT05A feature table")
    if table_record.get("format") != "csv" or table_record.get("complete") is not True:
        raise FT04ValidationError("FT05A feature table is not complete CSV")
    if not re.match(r"^[0-9a-f]{64}$", str(table_record.get("sha256", ""))):
        raise FT04ValidationError("FT05A feature-table hash is invalid")
    if _sha256_file(table_path) != table_record["sha256"]:
        raise FT04ValidationError("FT05A feature-table hash mismatch")
    try:
        table = pd.read_csv(table_path)
    except (IOError, OSError, ValueError) as exc:
        raise FT04ValidationError("cannot read FT05A feature table: %s" % exc)
    if list(table.columns) != table_record["columns"]:
        raise FT04ValidationError("FT05A feature-table column order mismatch")
    if table_record.get("patient_id_column") != "patient_id" or \
            "patient_id" not in table.columns:
        raise FT04ValidationError("FT05A feature-table patient ID schema is invalid")
    ids = table["patient_id"].astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise FT04ValidationError("FT05A feature-table patients are not unique")
    if int(table_record["row_count"]) != len(table) or \
            int(table_record["patient_count"]) != len(table) or \
            table_record.get("patient_ids_unique") is not True or \
            int(table_record["duplicate_patient_count"]) != 0:
        raise FT04ValidationError("FT05A feature-table row/uniqueness evidence is invalid")
    if int(table_record["duplicate_extraction_count"]) != 0 or \
            int(table_record["extraction_count"]) != len(table):
        raise FT04ValidationError("FT05A duplicate-extraction evidence is invalid")
    for column in table.columns:
        lowered = str(column).lower()
        if lowered in ("dfs_time", "dfs_event", "outcome", "event", "survival_time") or \
                lowered.endswith("path") or lowered in ("path", "source_path", "image_path", "roi_path"):
            raise FT04ValidationError("FT05A feature table contains outcome or path data")
    if "split" in table.columns and not table["split"].astype(str).str.upper().eq("B").all():
        raise FT04ValidationError("FT05A feature table contains a non-B row")
    required_columns = set(_canonical_b_feature_columns())
    missing = sorted(required_columns - set(table.columns))
    if missing:
        raise FT04ValidationError("FT05A feature table is missing frozen model-input columns")
    allowed_columns = required_columns | {"split"}
    extra = sorted(set(table.columns) - allowed_columns)
    if extra:
        raise FT04ValidationError("FT05A feature table has unexpected columns")
    for column in required_columns - {"patient_id"}:
        values = pd.to_numeric(table[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise FT04ValidationError("FT05A feature table contains nonfinite required values")
    return table, table_path


def _validate_b_feature_manifest(lock, manifest_path=None, state=None):
    manifest_path = _canonical_artifact_path(
        manifest_path, FT05_MANIFEST, "FT05_B_feature_manifest")
    if not os.path.isfile(manifest_path):
        raise FT04ValidationError("canonical FT05_B_feature_manifest.json is required before B prediction")
    manifest = _read_json(manifest_path)
    if manifest.get("artifact_id") != "FT05_B_feature_manifest" or \
            manifest.get("schema_version") != "1.0" or \
            manifest.get("status") != "frozen":
        raise FT04ValidationError("FT05 B feature manifest is not complete and frozen")
    if manifest.get("ft04_lock_identity_sha256") != lock.get("lock_identity_sha256"):
        raise FT04ValidationError("FT05 B manifest is not bound to this FT04 lock")
    expected = lock["prediction_contract"]["expected_model_input_hashes"]
    if manifest.get("model_input_hashes") != expected:
        raise FT04ValidationError("FT05 B manifest model-input hashes do not match FT04")
    table, table_path = _validate_ft05a_feature_table(manifest)
    if state is not None:
        _validate_b_predictor_frame(table, state)
    blocks = manifest.get("feature_blocks") or {}
    if set(blocks) != {"R_low", "R_high", "W_Original"}:
        raise FT04ValidationError("FT05 B feature blocks are incomplete")
    for block, names, count, digest in (
            ("R_low", ft02.R_LOW_FEATURE_NAMES, 49, R_LOW_CANDIDATE_HASH),
            ("R_high", ft02.R_HIGH_FEATURE_NAMES, 10, R_HIGH_CANDIDATE_HASH)):
        record = blocks.get(block) or {}
        if record.get("feature_names") != list(names) or \
                record.get("count") != count or \
                record.get("candidate_hash") != digest:
            raise FT04ValidationError("FT05 B %s candidate/order contract mismatch" % block)
    w_record = blocks.get("W_Original") or {}
    if w_record.get("feature_names") != list(ft02.W_ORIGINAL_FEATURE_NAMES) or \
            w_record.get("count") != 107 or \
            w_record.get("order_sha256") != ft02.W_ORIGINAL_ORDER_SHA256 or \
            w_record.get("reused_existing_asset") is not True or \
            w_record.get("reextracted") is not False:
        raise FT04ValidationError("FT05 B W_Original reuse/order contract mismatch")
    frozen_w = lock["habitat_definition"].get("W_Original_asset") or {}
    if w_record.get("asset_path") != frozen_w.get("path") or \
            w_record.get("asset_sha256") != frozen_w.get("asset_sha256"):
        raise FT04ValidationError("FT05 B W_Original asset is not the accepted existing asset")
    asset_path = _validate_nonformal_relative_path(
        w_record.get("asset_path"), "FT05 B W_Original asset")
    if not os.path.isfile(asset_path) or \
            _sha256_file(asset_path) != frozen_w.get("asset_sha256"):
        raise FT04ValidationError("FT05 B W_Original asset hash mismatch")
    boundary = manifest.get("frozen_a_full_boundary") or {}
    if boundary.get("definition") != "accepted frozen full_A habitat" or \
            boundary.get("lock_identity_sha256") != lock.get("lock_identity_sha256") or \
            boundary.get("identity_sha256") != _frozen_a_boundary_identity(lock) or \
            boundary.get("K") != 2 or boundary.get("n_init") != 100 or \
            boundary.get("no_refit") is not True or \
            boundary.get("source_hashes") != OrderedDict((
                (key, lock["provenance"]["sources"][key]["sha256"])
                for key in ("ft01_asset_manifest", "habitat_freeze_lock",
                            "w03_candidate_freeze"))):
        raise FT04ValidationError("FT05 B frozen A-full boundary binding is invalid")
    pyradiomics = manifest.get("pyradiomics_provenance")
    if pyradiomics != lock["provenance"]["pyradiomics"] or \
            manifest.get("pyradiomics_matches_A_W03") is not True:
        raise FT04ValidationError("FT05 B PyRadiomics provenance is not identical to A/W03")
    generation = manifest.get("generation") or {}
    required_false = ("outcome_accessed", "b_kmeans_fit", "repeat_extraction",
                      "duplicate_extraction", "checkpoint_resume_repeated_extraction",
                      "whole_tumor_reextraction", "formal_directory_mixing")
    if generation.get("outcome_blind") is not True or \
            generation.get("one_time_first_extraction") is not True or \
            generation.get("w_original_reused") is not True or \
            any(generation.get(key) is not False for key in required_false):
        raise FT04ValidationError("FT05 B generation is not outcome-blind and one-time")
    reviews = manifest.get("reviews") or {}
    _validate_ft05a_review_artifact(
        reviews.get("technical_audit"), FT05A_TECHNICAL_AUDIT,
        "FT05A technical audit")
    _validate_ft05a_review_artifact(
        reviews.get("code_audit"), FT05A_CODE_AUDIT,
        "FT05A code audit")
    return manifest, table, table_path


def _validate_outcome_unlock(lock, manifest_path=None, unlock_path=None):
    manifest_path = _canonical_artifact_path(
        manifest_path, FT05_MANIFEST, "FT05_B_feature_manifest")
    unlock_path = _canonical_artifact_path(
        unlock_path, FT_B_UNLOCK, "FT_B_unlock")
    if not os.path.isfile(unlock_path):
        raise FT04ValidationError("canonical FT_B_unlock.json is required for outcome access")
    unlock = _read_json(unlock_path)
    if unlock.get("artifact_id") != "FT_B_unlock" or \
            unlock.get("status") != "authorized" or \
            unlock.get("outcome_access") is not True:
        raise FT04ValidationError("FT_B_unlock authorization is invalid")
    if unlock.get("ft04_lock_identity_sha256") != lock.get("lock_identity_sha256"):
        raise FT04ValidationError("FT_B_unlock is not bound to FT04")
    if unlock.get("ft05_manifest_sha256") != _sha256_file(manifest_path):
        raise FT04ValidationError("FT_B_unlock is not bound to the canonical FT05 manifest")
    return unlock


def validate_ft_model_freeze_lock(lock_path=DEFAULT_LOCK):
    """Validate the FT04 lock, Git bindings, sources, and model states."""
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
    b_access = lock.get("b_access") or {}
    if b_access.get("b_feature_manifest") != \
            "prognosis_analysis/ft/FT05_B_feature_manifest.json" or \
            b_access.get("b_outcome_unlock") != \
            "prognosis_analysis/ft/FT_B_unlock.json":
        raise FT04ValidationError("FT04 lock does not use canonical B artifact paths")
    identity = lock.get("lock_identity_sha256")
    if identity != _lock_identity(lock):
        raise FT04ValidationError("FT04 lock identity hash mismatch")
    _validate_lock_digest(lock_path)
    _validate_source_records(lock.get("provenance", {}).get("sources", {}))
    _validate_input_source_records(
        lock.get("provenance", {}).get("input_sources", {}))
    _validate_candidate_contract(lock)
    _validate_git_binding(lock)
    _validate_pyradiomics_binding(lock)
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


def _validate_b_predictor_frame(frame, state):
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise FT04ValidationError("B predictor frame must be non-empty")
    if "patient_id" not in frame.columns:
        raise FT04ValidationError("B predictor frame lacks patient_id")
    if any(str(column).lower() in (
            "dfs_time", "dfs_event", "outcome", "event", "survival_time")
            for column in frame.columns):
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
    for column in state["raw_predictor_columns"]:
        values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise FT04ValidationError("B predictor frame contains nonfinite frozen values")
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


def _validate_caller_frame_identity(frame, canonical_frame, canonical_table_path,
                                    state):
    if frame is None:
        return canonical_frame.copy()
    checked = _validate_b_predictor_frame(frame, state)
    if list(checked.columns) != list(canonical_frame.columns):
        raise FT04ValidationError(
            "caller predictor columns do not exactly match the canonical feature table")
    try:
        with open(canonical_table_path, "rb") as handle:
            canonical_bytes = handle.read()
        caller_bytes = checked.to_csv(index=False).encode("utf-8")
    except (IOError, OSError, UnicodeError, TypeError, ValueError):
        raise FT04ValidationError(
            "caller predictor frame cannot be serialized for identity verification")
    if caller_bytes != canonical_bytes:
        raise FT04ValidationError(
            "caller predictor frame does not exactly match the canonical feature table")
    return checked


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


def predict_b_from_frozen(feature_frame=None, model_id=None, lock_path=DEFAULT_LOCK,
                          manifest_path=None, outcomes_requested=False,
                          unlock_path=None):
    """Predict B risk/survival only after the later FT05 locks validate."""
    lock, state, model, preprocessor = load_frozen_prediction_state(
        lock_path, model_id)
    _validate_ft04_review(lock, lock_path)
    unused_manifest, canonical_frame, canonical_table_path = _validate_b_feature_manifest(
        lock, manifest_path, state)
    _canonical_artifact_path(unlock_path, FT_B_UNLOCK, "FT_B_unlock")
    if outcomes_requested:
        _validate_outcome_unlock(lock, manifest_path, unlock_path)
    checked = _validate_caller_frame_identity(
        feature_frame, canonical_frame, canonical_table_path, state)
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
                           lock_path=DEFAULT_LOCK, manifest_path=None,
                           unlock_path=None):
    """Evaluate frozen predictions only when FT05B explicitly unlocks outcomes."""
    prediction = predict_b_from_frozen(
        feature_frame, model_id, lock_path=lock_path,
        manifest_path=manifest_path, outcomes_requested=True,
        unlock_path=unlock_path)
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
    parser.add_argument("command", choices=("run", "remediate", "validate"))
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
    elif args.command == "remediate":
        lock = finalize_ft04_from_existing_states(
            args.output_root, args.lock, args.audit)
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
