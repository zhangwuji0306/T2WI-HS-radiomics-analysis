"""FT02 A-only modeling and technical interfaces.

This module is intentionally in-memory.  It consumes an already authorized A
feature frame and the pre-frozen W07 repeat-1 split frame; it never opens a
patient-data source and never writes a formal or FT result file.  FT03 can use
the returned fold predictions and the metric/data hooks without changing the
frozen W08/L9 implementation.
"""
from __future__ import absolute_import

import hashlib
import json
import math
import os
import re
import sys
from collections import OrderedDict

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_SCRIPT_ROOT = os.path.join(_PROJECT_ROOT, "prognosis_analysis", "scripts")
if _SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, _SCRIPT_ROOT)
import w08_nested_cv as _w08  # noqa: E402


class FTValidationError(ValueError):
    """Raised when an FT input or technical contract is not valid."""


FT_STAGE = "FT02"
FT_LABEL = "exploratory_fullA_habitat_non_nested_validation"
W_ORIGINAL_FEATURE_COUNT = 107
W_ORIGINAL_ORDER_SHA256 = (
    "1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f")
W_ORIGINAL_MANIFEST = os.path.join(_HERE, "FT01_asset_manifest.json")
W07_SPLIT_ARTIFACT = os.path.join(
    _PROJECT_ROOT, "prognosis_analysis", "output", "outer_splits_A.csv")
W07_SPLIT_ARTIFACT_SHA256 = (
    "24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502")
W07_REPEAT1_CANONICAL_SHA256 = (
    "774436340ce68cd70a2c6acd17acbb7fa484fd7f29989f12670dde519c9f376d")
W07_REPEAT1_SEED = 12345
W07_REPEAT1 = 1
W07_A393_SIZE = 393
W07_SPLIT_COLUMNS = ("patient_id", "repeat", "fold", "role", "seed")
W07_ROLES = ("train", "validation")

FT_MODEL_SPECS = OrderedDict((
    ("M0", {"blocks": ("C",), "family": "Cox", "penalized": False}),
    ("M1", {"blocks": ("C", "H_high_fraction"), "family": "Cox",
             "penalized": False}),
    ("M2", {"blocks": ("C", "G"), "family": "Cox", "penalized": False}),
    ("M3L", {"blocks": ("C", "G", "R_low"), "family": "Cox",
              "penalized": True, "alpha": 1.0}),
    ("M3H", {"blocks": ("C", "G", "R_high"), "family": "Cox",
              "penalized": True, "alpha": 1.0}),
    ("M4", {"blocks": ("C", "G", "R_low", "R_high"), "family": "Cox",
             "penalized": True, "alpha": 1.0}),
    ("M5", {"blocks": ("C", "W_Original"), "family": "Cox",
             "penalized": True, "alpha": 1.0}),
))

FT_COMPARISONS = (
    ("M0_vs_M1", "M0", "M1", "main"),
    ("M0_vs_M2", "M0", "M2", "main"),
    ("M2_vs_M3L", "M2", "M3L", "R_low"),
    ("M2_vs_M3H", "M2", "M3H", "R_high"),
    ("M2_vs_M4", "M2", "M4", "dual_radiomics"),
    ("M3L_vs_M3H", "M3L", "M3H", "dual_radiomics"),
    ("M4_vs_M5", "M4", "M5", "dual_radiomics_and_W_Original"),
)

_BASE_COLUMNS = ("patient_id", "DFS_time", "DFS_event")
_PATH_COLUMNS = frozenset(("path", "source_path", "image_path", "roi_path",
                           "input_path", "file_path"))


def load_w_original_names(manifest_path=W_ORIGINAL_MANIFEST):
    """Load and validate the accepted FT01 canonical W_Original order."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        names = tuple(payload["W_Original_canonical_order"]["feature_names"])
    except (IOError, OSError, ValueError, KeyError, TypeError) as exc:
        raise FTValidationError("W_Original canonical order is unavailable: %s" % exc)
    digest = hashlib.sha256(json.dumps(list(names), ensure_ascii=False,
                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    if len(names) != W_ORIGINAL_FEATURE_COUNT or digest != W_ORIGINAL_ORDER_SHA256:
        raise FTValidationError("W_Original canonical order failed the frozen hash")
    if any(str(name).startswith(("wavelet", "log")) for name in names):
        raise FTValidationError("filtered whole-tumor features entered W_Original")
    return names


W_ORIGINAL_FEATURE_NAMES = load_w_original_names()
R_LOW_FEATURE_NAMES = tuple(_w08.FROZEN_CANDIDATE_FEATURES["R_low"])
R_HIGH_FEATURE_NAMES = tuple(_w08.FROZEN_CANDIDATE_FEATURES["R_high"])
BLOCK_PREFIXES = {"R_low": "R_low__", "R_high": "R_high__",
                  "W_Original": "W__"}
BLOCK_FEATURE_NAMES = {
    "R_low": R_LOW_FEATURE_NAMES,
    "R_high": R_HIGH_FEATURE_NAMES,
    "W_Original": W_ORIGINAL_FEATURE_NAMES,
}
CLINICAL_COLUMNS = tuple(_w08.CLINICAL_COLUMNS)
GLOBAL_COLUMNS = tuple(_w08.GLOBAL_COLUMNS)


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_frame_hash(frame, columns=None):
    columns = list(columns or frame.columns)
    ordered = frame.loc[:, columns].copy()
    return _sha256_text(ordered.to_csv(index=False, line_terminator="\n"))


def _id_hash(ids):
    values = sorted(str(value).strip() for value in ids)
    if any(not value for value in values):
        raise FTValidationError("blank identifier cannot be hashed")
    return _sha256_text("\n".join(values) + "\n")


def schema_hash(frame):
    """Return a de-identified hash of column names and dtypes."""
    payload = [(str(column), str(frame[column].dtype)) for column in frame.columns]
    return _sha256_text(json.dumps(payload, ensure_ascii=False,
                                   separators=(",", ":")))


def _numeric_flag(frame, column):
    if column not in frame.columns:
        raise FTValidationError("missing explicit availability flag: %s" % column)
    values = pd.to_numeric(frame[column], errors="coerce")
    if values.isna().any() or not values.isin([0, 1]).all():
        raise FTValidationError("availability flag must be binary: %s" % column)
    return values.astype(int).eq(1)


def availability_mask(frame, block):
    """Resolve explicit availability without turning structural absence into NA."""
    if block in ("R_low", "R_high"):
        p3b_fields = {
            "%s_voxel_count" % block,
            "%s_state" % block,
            "%s_structurally_defined" % block,
            "%s_technically_extractable" % block,
        }
        present = p3b_fields & set(frame.columns)
        p3b_specific = p3b_fields - {
            "%s_structurally_defined" % block,
        }
        if present & p3b_specific:
            if present != p3b_fields:
                raise FTValidationError(
                    "%s P3B structural-state fields are incomplete" % block)
            categories = _w08._p3b_extractability_categories(
                frame, required=True)
            return categories[block].eq("extractable")
        structural = _numeric_flag(frame, block + "_structurally_defined")
        technical = _numeric_flag(frame, block + "_technically_available")
        if (technical & ~structural).any():
            raise FTValidationError(
                "%s technical availability exceeds structural definition" % block)
        return structural & technical
    if block == "W_Original":
        if "W_Original_available" in frame.columns:
            return _numeric_flag(frame, "W_Original_available")
        return _numeric_flag(frame, "W_available")
    raise FTValidationError("unknown availability block: %s" % block)


def _reject_b_rows_or_paths(frame):
    if "split" in frame.columns:
        split = frame["split"].astype(str).str.strip().str.upper()
        if split.ne("A").any():
            raise FTValidationError("FT02 accepts A rows only")
    forbidden_prefixes = ("b__", "b_", "b-")
    for column in frame.columns:
        name = str(column).lower()
        if name.startswith(forbidden_prefixes):
            raise FTValidationError("B-prefixed input column is not allowed")
    for column in frame.columns:
        if str(column).lower() not in _PATH_COLUMNS:
            continue
        values = frame[column].dropna().astype(str)
        for value in values:
            parts = [item for item in re.split(r"[\\/]", value.lower()) if item]
            if "b" in parts or any(item.startswith("b_") or item.startswith("b-")
                                    for item in parts):
                raise FTValidationError("B path is not allowed in FT02 input")


def _block_columns(frame, block):
    if block == "C":
        return list(CLINICAL_COLUMNS)
    if block == "G":
        return list(GLOBAL_COLUMNS)
    if block == "H_high_fraction":
        return ["H_high_fraction"]
    if block not in BLOCK_PREFIXES:
        raise FTValidationError("unknown predictor block: %s" % block)
    prefix = BLOCK_PREFIXES[block]
    expected = [prefix + name for name in BLOCK_FEATURE_NAMES[block]]
    actual = [str(column) for column in frame.columns if str(column).startswith(prefix)]
    if actual != expected:
        # Ordering is part of W_Original and candidate provenance.  For R
        # blocks accept a different frame column order only after checking the
        # exact identity; preprocessing reorders to the frozen order below.
        if block == "W_Original" or set(actual) != set(expected):
            raise FTValidationError("%s feature identity/order is not frozen" % block)
    return expected


def validate_ft_frame(frame, models=None):
    """Fail-closed validation for an A-only FT modeling frame."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise FTValidationError("FT frame must be a non-empty pandas DataFrame")
    frame = frame.copy()
    _reject_b_rows_or_paths(frame)
    missing = sorted((set(_BASE_COLUMNS) | set(CLINICAL_COLUMNS)) - set(frame.columns))
    if missing:
        raise FTValidationError("missing required FT columns: %s" % missing)
    ids = frame["patient_id"].astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise FTValidationError("patient_id must be nonempty and unique")
    time = pd.to_numeric(frame["DFS_time"], errors="coerce")
    event = pd.to_numeric(frame["DFS_event"], errors="coerce")
    if time.isna().any() or not np.isfinite(time.to_numpy(dtype=float)).all() or (time <= 0).any():
        raise FTValidationError("DFS_time must be finite and positive")
    if event.isna().any() or not event.isin([0, 1]).all():
        raise FTValidationError("DFS_event must be binary")
    models = list(FT_MODEL_SPECS if models is None else models)
    for model_id in models:
        if model_id not in FT_MODEL_SPECS:
            raise FTValidationError("unknown FT model: %s" % model_id)
        for block in FT_MODEL_SPECS[model_id]["blocks"]:
            for column in _block_columns(frame, block):
                if column not in frame.columns:
                    raise FTValidationError("missing %s feature: %s" % (block, column))
        for block in FT_MODEL_SPECS[model_id]["blocks"]:
            if block in ("R_low", "R_high", "W_Original"):
                availability_mask(frame, block)
    # Availability state is a structural invariant of the input frame, not a
    # performance-dependent option.  Validate any supplied R-block state even
    # when a caller requests a lower-dimensional model subset.
    for block in ("R_low", "R_high"):
        if any(str(column).startswith(block + "_") for column in frame.columns):
            availability_mask(frame, block)
    # If W_Original is requested, any other W-prefixed feature is a schema
    # violation; this is the hard boundary excluding Wavelet/LoG inputs.
    if "M5" in models:
        allowed = set("W__" + name for name in W_ORIGINAL_FEATURE_NAMES)
        extras = sorted(set(column for column in frame.columns
                            if str(column).startswith("W__")) - allowed)
        if extras:
            raise FTValidationError("filtered whole-tumor features are excluded")
    return frame


def validate_frozen_split(split_frame, frame=None, repeat=1):
    """Validate, but never regenerate, one frozen five-fold split set."""
    required = set(W07_SPLIT_COLUMNS)
    if not isinstance(split_frame, pd.DataFrame) or not required.issubset(split_frame.columns):
        raise FTValidationError("split frame lacks frozen W07 columns")
    split = split_frame.copy()
    split["patient_id"] = split["patient_id"].astype(str).str.strip()
    split["repeat"] = pd.to_numeric(split["repeat"], errors="coerce")
    split["fold"] = pd.to_numeric(split["fold"], errors="coerce")
    if split[["repeat", "fold"]].isna().any().any():
        raise FTValidationError("W07 split repeat/fold is nonnumeric")
    split = split[split["repeat"].astype(int).eq(int(repeat))].copy()
    if split.empty or sorted(split["fold"].astype(int).unique().tolist()) != [1, 2, 3, 4, 5]:
        raise FTValidationError("FT02 requires the pre-frozen W07 repeat-1 five-fold set")
    split["fold"] = split["fold"].astype(int)
    split["role"] = split["role"].astype(str).str.lower()
    if not set(split["role"]).issubset({"train", "validation"}):
        raise FTValidationError("W07 split has an unknown role")
    split["seed"] = pd.to_numeric(split["seed"], errors="coerce")
    if split["seed"].isna().any() or not np.isfinite(
            split["seed"].to_numpy(dtype=float)).all():
        raise FTValidationError("W07 split seed is invalid")
    split["seed"] = split["seed"].astype(int)
    seed_values = split.groupby("fold")["seed"].unique()
    if any(len(values) != 1 for values in seed_values):
        raise FTValidationError("W07 fold seed is not unique")
    validation_ids = []
    for fold in range(1, 6):
        current = split[split["fold"].eq(fold)]
        train_ids = current.loc[current["role"].eq("train"), "patient_id"]
        valid_ids = current.loc[current["role"].eq("validation"), "patient_id"]
        if train_ids.empty or valid_ids.empty:
            raise FTValidationError("W07 fold %d is empty" % fold)
        if train_ids.duplicated().any() or valid_ids.duplicated().any():
            raise FTValidationError("W07 fold %d contains duplicate IDs" % fold)
        if set(train_ids) & set(valid_ids):
            raise FTValidationError("W07 fold %d train/validation overlap" % fold)
        validation_ids.extend(valid_ids.tolist())
    if len(validation_ids) != len(set(validation_ids)):
        raise FTValidationError("W07 validation IDs repeat within repeat 1")
    if frame is not None:
        frame_ids = set(frame["patient_id"].astype(str))
        if not frame_ids.issubset(set(split["patient_id"])):
            raise FTValidationError("A frame contains IDs absent from the frozen W07 split")
    return split.reset_index(drop=True)


def _canonical_split_hash(split):
    return _canonical_frame_hash(split, list(W07_SPLIT_COLUMNS))


def _validate_w07_repeat1(split, expected_ids=None):
    """Validate the exact frozen W07 repeat-1 slice and its provenance locks."""
    if list(split.columns) != list(W07_SPLIT_COLUMNS):
        raise FTValidationError("frozen W07 split schema mismatch")
    split = split.copy()
    split["patient_id"] = split["patient_id"].astype(str).str.strip()
    split["repeat"] = pd.to_numeric(split["repeat"], errors="coerce")
    split["fold"] = pd.to_numeric(split["fold"], errors="coerce")
    split["seed"] = pd.to_numeric(split["seed"], errors="coerce")
    if split[["repeat", "fold", "seed"]].isna().any().any():
        raise FTValidationError("frozen W07 repeat-1 contains invalid numeric fields")
    split["repeat"] = split["repeat"].astype(int)
    split["fold"] = split["fold"].astype(int)
    split["seed"] = split["seed"].astype(int)
    split["role"] = split["role"].astype(str).str.strip().str.lower()
    if set(split["repeat"]) != {W07_REPEAT1}:
        raise FTValidationError("frozen W07 artifact is not repeat 1")
    if len(split) != W07_A393_SIZE * 5:
        raise FTValidationError("frozen W07 repeat-1 row count is not A393 x 5")
    if sorted(split["fold"].unique().tolist()) != [1, 2, 3, 4, 5]:
        raise FTValidationError("frozen W07 repeat-1 folds are incomplete")
    if set(split["role"]) != set(W07_ROLES):
        raise FTValidationError("frozen W07 repeat-1 roles are incomplete")
    if set(split["seed"]) != {W07_REPEAT1_SEED}:
        raise FTValidationError("frozen W07 repeat-1 seed is not frozen")
    for fold in range(1, 6):
        current = split[split["fold"].eq(fold)]
        if set(current["role"]) != set(W07_ROLES):
            raise FTValidationError("frozen W07 fold %d roles are incomplete" % fold)
        train_ids = current.loc[current["role"].eq("train"), "patient_id"]
        valid_ids = current.loc[current["role"].eq("validation"), "patient_id"]
        if train_ids.duplicated().any() or valid_ids.duplicated().any() or \
                set(train_ids) & set(valid_ids):
            raise FTValidationError("frozen W07 fold %d ID roles are invalid" % fold)
    ids = set(split["patient_id"])
    if len(ids) != W07_A393_SIZE:
        raise FTValidationError("frozen W07 repeat-1 membership is not complete A393")
    if expected_ids is not None and ids != set(str(value) for value in expected_ids):
        raise FTValidationError("frozen W07 repeat-1 membership differs from A393")
    if _canonical_split_hash(split) != W07_REPEAT1_CANONICAL_SHA256:
        raise FTValidationError("frozen W07 repeat-1 canonical hash mismatch")
    return split.reset_index(drop=True)


def load_frozen_w07_repeat1():
    """Load the project-bound W07 artifact and return its repeat-1 slice."""
    if not os.path.isfile(W07_SPLIT_ARTIFACT):
        raise FTValidationError("frozen W07 split artifact is missing")
    if _sha256_file(W07_SPLIT_ARTIFACT).lower() != \
            W07_SPLIT_ARTIFACT_SHA256:
        raise FTValidationError("frozen W07 split artifact hash mismatch")
    try:
        population = _w08.load_frozen_a_population()
        all_split = _w08.load_frozen_outer_splits(population)
    except Exception as exc:
        raise FTValidationError("frozen W07 binding failed: %s" % exc)
    if list(all_split.columns) != list(W07_SPLIT_COLUMNS):
        raise FTValidationError("frozen W07 split schema mismatch")
    repeat1 = all_split[all_split["repeat"].eq(W07_REPEAT1)].copy()
    repeat1 = _validate_w07_repeat1(
        repeat1, expected_ids=population["patient_id"].astype(str))
    return repeat1, population.copy()


def validate_proven_a_frame(frame, frozen_population, models=None):
    """Require explicit A provenance and complete frozen A393 membership."""
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        raise FTValidationError("A feature frame must be a non-empty pandas DataFrame")
    if "patient_id" not in frame.columns:
        raise FTValidationError("A feature frame lacks patient_id")
    required_provenance = {"split", "technical_cohort", "modeling_eligible"}
    missing = sorted(required_provenance - set(frame.columns))
    if missing:
        raise FTValidationError(
            "A cohort identity is unproven; missing provenance columns: %s" % missing)
    split = frame["split"].astype(str).str.strip().str.upper()
    cohort = frame["technical_cohort"].astype(str).str.strip()
    eligible = pd.to_numeric(frame["modeling_eligible"], errors="coerce")
    if not split.eq("A").all():
        raise FTValidationError("A-only FT02 input contains non-A or ambiguous split")
    if not cohort.eq("A393").all():
        raise FTValidationError("A-only FT02 input is not technical cohort A393")
    if eligible.isna().any() or not eligible.isin([0, 1]).all() or \
            not eligible.eq(1).all():
        raise FTValidationError("A-only FT02 input has unproven modeling eligibility")
    population = frozen_population.copy()
    population["patient_id"] = population["patient_id"].astype(str).str.strip()
    ids = frame["patient_id"].astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise FTValidationError("A feature frame IDs must be unique and nonblank")
    frozen_ids = set(population["patient_id"])
    if len(frozen_ids) != W07_A393_SIZE or set(ids) != frozen_ids:
        raise FTValidationError("A-only FT02 input is not complete frozen A393 membership")
    if len(frame) != W07_A393_SIZE:
        raise FTValidationError("A-only FT02 input must contain all 393 A cases")
    if not set({"patient_id", "DFS_time", "DFS_event"}).issubset(population.columns):
        raise FTValidationError("frozen A393 endpoint provenance is incomplete")
    population = population.set_index("patient_id")
    observed = frame.set_index(ids)
    expected_time = pd.to_numeric(population.loc[ids, "DFS_time"], errors="coerce")
    expected_event = pd.to_numeric(population.loc[ids, "DFS_event"], errors="coerce")
    observed_time = pd.to_numeric(observed["DFS_time"], errors="coerce")
    observed_event = pd.to_numeric(observed["DFS_event"], errors="coerce")
    if not np.array_equal(observed_time.to_numpy(dtype=float),
                          expected_time.to_numpy(dtype=float)) or \
            not np.array_equal(observed_event.to_numpy(dtype=int),
                               expected_event.to_numpy(dtype=int)):
        raise FTValidationError("A feature-frame endpoint differs from frozen A393")
    return validate_ft_frame(frame, models=models)


def population_mask(frame, population):
    if population == "main":
        return pd.Series(True, index=frame.index)
    if population == "R_low":
        return availability_mask(frame, "R_low")
    if population == "R_high":
        return availability_mask(frame, "R_high")
    if population == "dual_radiomics":
        return availability_mask(frame, "R_low") & availability_mask(frame, "R_high")
    if population == "dual_radiomics_and_W_Original":
        return (availability_mask(frame, "R_low") & availability_mask(frame, "R_high") &
                availability_mask(frame, "W_Original"))
    if population == "W_Original":
        return availability_mask(frame, "W_Original")
    raise FTValidationError("unknown FT population: %s" % population)


class FTPreprocessor(object):
    """Training-only FT preprocessing with frozen block identity."""

    def __init__(self, model_id):
        if model_id not in FT_MODEL_SPECS:
            raise FTValidationError("unknown FT model: %s" % model_id)
        self.model_id = model_id
        self.spec = FT_MODEL_SPECS[model_id]
        self.clinical = _w08.ClinicalPreprocessor()
        self.global_block = None
        self.radiomics = None
        self.radiomics_blocks = []
        self.feature_names = []

    def fit(self, frame):
        self.clinical.fit(frame)
        names = list(self.clinical.feature_names)
        blocks = self.spec["blocks"]
        extra = []
        if "H_high_fraction" in blocks:
            extra.append("H_high_fraction")
        if "G" in blocks:
            extra.extend(GLOBAL_COLUMNS)
        if extra:
            self.global_block = _w08.NumericPreprocessor(extra).fit(frame)
            names.extend(extra)
        columns = []
        for block in ("R_low", "R_high", "W_Original"):
            if block in blocks:
                current = _block_columns(frame, block)
                columns.extend(current)
                self.radiomics_blocks.append(block)
        if columns:
            self.radiomics = _w08.RadiomicsPreprocessor(columns).fit(frame)
            names.extend(self.radiomics.kept_columns)
        self.feature_names = names
        if not self.feature_names:
            raise FTValidationError("preprocessing retained no feature")
        return self

    def transform(self, frame):
        if not self.feature_names:
            raise FTValidationError("preprocessor is not fitted")
        pieces = [self.clinical.transform(frame).to_numpy(dtype=float)]
        if self.global_block is not None:
            pieces.append(self.global_block.transform(frame))
        if self.radiomics is not None:
            pieces.append(self.radiomics.transform(frame))
        output = np.column_stack(pieces)
        if not np.isfinite(output).all():
            raise FTValidationError("preprocessed matrix contains nonfinite values")
        return output

    def audit(self):
        return {
            "model_id": self.model_id,
            "feature_names": list(self.feature_names),
            "clinical_imputations": dict(self.clinical.imputations),
            "clinical_means": dict(self.clinical.means),
            "clinical_scales": dict(self.clinical.scales),
            "radiomics_input_count": 0 if self.radiomics is None else len(self.radiomics.input_columns),
            "radiomics_kept_columns": [] if self.radiomics is None else list(self.radiomics.kept_columns),
            "radiomics_dropped_all_nonfinite": [] if self.radiomics is None else list(self.radiomics.dropped_all_nonfinite),
            "radiomics_dropped_near_zero_variance": [] if self.radiomics is None else list(self.radiomics.dropped_near_zero_variance),
            "radiomics_dropped_correlation": [] if self.radiomics is None else list(self.radiomics.dropped_correlation),
        }


def _inner_lambda_selection(frame, model_id, seed, lambda_count=20,
                             max_iter=1000, tolerance=1e-7):
    if not FT_MODEL_SPECS[model_id]["penalized"]:
        raise FTValidationError("lambda selection requested for unpenalized model")
    if int(lambda_count) < 2:
        raise FTValidationError("lambda_count must be at least two")
    inner_splits = _w08.make_inner_splits(frame, int(seed), folds=5)
    ratios = np.geomspace(1.0, _w08.LAMBDA_MIN_RATIO, int(lambda_count))
    scores = [[] for _ in ratios]
    attempts = failures = 0
    for train_idx, validation_idx in inner_splits:
        train = frame.iloc[train_idx].reset_index(drop=True)
        valid = frame.iloc[validation_idx].reset_index(drop=True)
        prep = FTPreprocessor(model_id).fit(train)
        X_train = prep.transform(train)
        X_valid = prep.transform(valid)
        time_train = train["DFS_time"].to_numpy(dtype=float)
        event_train = train["DFS_event"].to_numpy(dtype=int)
        layout = _w08._prepare_uno_c_index_layout(
            time_train, event_train,
            valid["DFS_time"].to_numpy(dtype=float),
            valid["DFS_event"].to_numpy(dtype=int))
        maximum = _w08._lambda_max(X_train, time_train, event_train, 1.0)
        for index, ratio in enumerate(ratios):
            attempts += 1
            try:
                model = _w08.CoxElasticNetModel(
                    1.0, float(maximum * ratio), max_iter=max_iter,
                    tolerance=tolerance).fit(X_train, time_train, event_train)
                _w08._require_converged_model(model, "FT inner alpha=1 Cox")
                risk = model.predict_risk(X_valid)
                score = _w08._uno_c_index_from_layout(layout, risk)
                if np.isfinite(score):
                    scores[index].append(float(score))
                else:
                    failures += 1
            except (_w08.W08ValidationError, _w08.W08NumericalFailure):
                failures += 1
    summary = []
    for index, ratio in enumerate(ratios):
        finite = scores[index]
        summary.append({
            "lambda_index": int(index),
            "lambda_ratio": float(ratio),
            "mean_uno_c_index": float(np.mean(finite)) if finite else float("nan"),
            "n_estimable_inner_scores": int(len(finite)),
            "n_inner_scores": int(len(inner_splits)),
        })
    valid = [row for row in summary if np.isfinite(row["mean_uno_c_index"])]
    if not valid:
        raise FTValidationError("no estimable training-only lambda candidate")
    best = max(row["mean_uno_c_index"] for row in valid)
    tied = [row for row in valid if best - row["mean_uno_c_index"] <= 1e-12]
    selected = sorted(tied, key=lambda row: -row["lambda_ratio"])[0]
    return {
        "alpha": 1.0,
        "lambda_ratio": selected["lambda_ratio"],
        "lambda_index": selected["lambda_index"],
        "mean_uno_c_index": selected["mean_uno_c_index"],
        "inner_folds": 5,
        "lambda_count": int(lambda_count),
        "candidate_attempts": int(attempts),
        "candidate_failures": int(failures),
        "lambda_selection_scope": "outer_training_inner_5fold_only",
        "outer_validation_used_for_lambda": False,
        "outer_validation_used_for_selection": False,
        "all_inner_records": summary,
    }


def fit_fold_a(train_frame, validation_frame, model_id, seed=12345,
               lambda_count=20, max_iter=1000, tolerance=1e-7):
    """Fit one A fold and return the model, preprocessor, risk and audit."""
    if model_id not in FT_MODEL_SPECS:
        raise FTValidationError("unknown FT model: %s" % model_id)
    train = validate_ft_frame(train_frame, models=[model_id]).reset_index(drop=True)
    valid = validate_ft_frame(validation_frame, models=[model_id]).reset_index(drop=True)
    prep = FTPreprocessor(model_id).fit(train)
    X_train = prep.transform(train)
    X_valid = prep.transform(valid)
    time_train = train["DFS_time"].to_numpy(dtype=float)
    event_train = train["DFS_event"].to_numpy(dtype=int)
    spec = FT_MODEL_SPECS[model_id]
    selection = {
        "alpha": None,
        "lambda_selection_scope": "not_applicable_unpenalized",
        "outer_validation_used_for_lambda": False,
        "outer_validation_used_for_selection": False,
    }
    if spec["penalized"]:
        selection = _inner_lambda_selection(
            train, model_id, seed, lambda_count=lambda_count,
            max_iter=max_iter, tolerance=tolerance)
        outer_max = _w08._lambda_max(X_train, time_train, event_train, 1.0)
        final_lambda = float(outer_max * selection["lambda_ratio"])
        if not np.isfinite(final_lambda) or final_lambda <= 0:
            raise FTValidationError("training-only lambda is nonpositive")
        model = _w08.CoxElasticNetModel(
            1.0, final_lambda, max_iter=max_iter, tolerance=tolerance).fit(
                X_train, time_train, event_train)
        selection["outer_lambda_reference"] = float(outer_max)
        selection["outer_lambda"] = final_lambda
        selection["alpha"] = 1.0
    else:
        model = _w08.CoxPHModel(max_iter=max_iter, tolerance=tolerance).fit(
            X_train, time_train, event_train)
    _w08._require_converged_model(model, "FT %s Cox" % model_id)
    risk = model.predict_risk(X_valid)
    if not np.isfinite(risk).all():
        raise FTValidationError("FT risk prediction is nonfinite")
    survival = model.predict_survival(
        X_valid, OrderedDict((("3_year", 36.0), ("5_year", 60.0))))
    for horizon_name in ("3_year", "5_year"):
        values = np.asarray(survival[horizon_name], dtype=float)
        if len(values) != len(risk) or not np.isfinite(values).all() or \
                np.any(values < 0.0) or np.any(values > 1.0):
            raise FTValidationError(
                "FT %s survival prediction is not a probability" % horizon_name)
    return {
        "model": model,
        "preprocessor": prep,
        "risk": risk,
        "survival": survival,
        "selection": selection,
        "preprocessing": prep.audit(),
        "fit_audit": dict(model.fit_audit),
        "alpha": 1.0 if spec["penalized"] else None,
        "family": "Cox",
    }


def _rows_for_fold(split, frame, fold, eligible_ids):
    current = split[split["fold"].eq(int(fold))]
    eligible = set(str(value) for value in eligible_ids)
    train_ids = set(current.loc[current["role"].eq("train"), "patient_id"]) & eligible
    valid_ids = set(current.loc[current["role"].eq("validation"), "patient_id"]) & eligible
    train = frame[frame["patient_id"].astype(str).isin(train_ids)].copy()
    valid = frame[frame["patient_id"].astype(str).isin(valid_ids)].copy()
    if train.empty or valid.empty:
        raise FTValidationError("fold %d has an empty eligible side" % fold)
    return train, valid


def _prediction_frame(ids, risks, folds, survival_36=None, survival_60=None):
    output = {
        "patient_id": [str(value) for value in ids],
        "risk": np.asarray(risks, dtype=float),
        "fold": np.asarray(folds, dtype=int),
    }
    if survival_36 is not None and survival_60 is not None:
        output["survival_probability_36"] = np.asarray(survival_36, dtype=float)
        output["survival_probability_60"] = np.asarray(survival_60, dtype=float)
    return pd.DataFrame(output)


def _model_population(model_id):
    blocks = FT_MODEL_SPECS[model_id]["blocks"]
    if "R_low" in blocks and "R_high" in blocks:
        return "dual_radiomics"
    if "R_low" in blocks:
        return "R_low"
    if "R_high" in blocks:
        return "R_high"
    if "W_Original" in blocks:
        return "W_Original"
    return "main"


def _fit_model_cv(frame, split, model_id, population, lambda_count=20,
                  max_iter=1000, tolerance=1e-7):
    """Fit one model on one explicit eligible population and frozen folds."""
    eligible = frame.loc[population_mask(frame, population), "patient_id"].astype(str)
    if eligible.empty:
        raise FTValidationError("empty eligible population for %s" % model_id)
    risk_by_id = {}
    survival36_by_id = {}
    survival60_by_id = {}
    fold_by_id = {}
    folds = []
    states = []
    for fold in range(1, 6):
        train, valid = _rows_for_fold(split, frame, fold, eligible)
        if int(train["DFS_event"].sum()) < 1 or int(valid["DFS_event"].sum()) < 1:
            raise FTValidationError("fold %d lacks an event for %s" % (fold, model_id))
        seed_values = split.loc[split["fold"].eq(fold), "seed"]
        unique_seeds = pd.to_numeric(seed_values, errors="coerce").dropna().unique()
        if len(unique_seeds) != 1:
            raise FTValidationError("fold %d seed is ambiguous" % fold)
        fitted = fit_fold_a(
            train, valid, model_id, seed=int(unique_seeds[0]),
            lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance)
        valid_ids = valid["patient_id"].astype(str).tolist()
        for index, identifier in enumerate(valid_ids):
            if identifier in risk_by_id:
                raise FTValidationError("duplicate cross-validated prediction")
            risk_by_id[identifier] = float(fitted["risk"][index])
            survival36_by_id[identifier] = float(fitted["survival"]["3_year"][index])
            survival60_by_id[identifier] = float(fitted["survival"]["5_year"][index])
            fold_by_id[identifier] = int(fold)
        train_ids = train["patient_id"].astype(str).tolist()
        folds.append({
            "fold": int(fold),
            "n_train": int(len(train)),
            "n_validation": int(len(valid)),
            "train_event_count": int(train["DFS_event"].sum()),
            "validation_event_count": int(valid["DFS_event"].sum()),
            "training_id_hash": _id_hash(train_ids),
            "validation_id_hash": _id_hash(valid_ids),
            "selection": fitted["selection"],
            "preprocessing": fitted["preprocessing"],
            "fit_audit": fitted["fit_audit"],
        })
        states.append({
            "fold": int(fold),
            "model": fitted["model"],
            "preprocessor": fitted["preprocessor"],
            "selection": fitted["selection"],
        })
    expected_ids = set(str(value) for value in eligible)
    if set(risk_by_id) != expected_ids:
        raise FTValidationError("cross-validation did not cover the eligible population")
    ordered_ids = sorted(risk_by_id)
    prediction = _prediction_frame(
        ordered_ids, [risk_by_id[item] for item in ordered_ids],
        [fold_by_id[item] for item in ordered_ids],
        [survival36_by_id[item] for item in ordered_ids],
        [survival60_by_id[item] for item in ordered_ids])
    spec = FT_MODEL_SPECS[model_id]
    return {
        "record": {
            "model_id": model_id,
            "predictor_blocks": list(spec["blocks"]),
            "population": population,
            "eligible_n": int(len(eligible)),
            "alpha": 1.0 if spec["penalized"] else None,
            "family": "Cox",
            "ordinary_single_layer_5fold": True,
            "folds": folds,
            "prediction_coverage": int(len(prediction)),
        },
        "prediction": prediction,
        "states": states,
        "eligible_ids": tuple(sorted(expected_ids)),
    }


def _paired_result(frame, left_fit, right_fit, comparison_id,
                   left_model, right_model, population, split):
    """Compare two models fit on exactly one common population and folds."""
    left = left_fit["prediction"].set_index("patient_id")
    right = right_fit["prediction"].set_index("patient_id")
    ids = sorted(set(left.index))
    if not ids or set(ids) != set(right.index):
        raise FTValidationError(
            "paired comparison models do not share one common eligible population")
    if not left.loc[ids, "fold"].equals(right.loc[ids, "fold"]):
        raise FTValidationError("paired comparison fold assignments differ")
    common_ids = set(ids)
    fold_records = []
    for fold in range(1, 6):
        current = split[split["fold"].eq(fold)]
        train_ids = sorted(set(current.loc[current["role"].eq("train"), "patient_id"]) & common_ids)
        valid_ids = sorted(set(current.loc[current["role"].eq("validation"), "patient_id"]) & common_ids)
        if not train_ids or not valid_ids:
            raise FTValidationError("paired comparison fold %d is empty" % fold)
        assignment = pd.DataFrame({
            "patient_id": train_ids + valid_ids,
            "role": (["train"] * len(train_ids)) +
                    (["validation"] * len(valid_ids)),
        }).sort_values(["role", "patient_id"], kind="mergesort").reset_index(drop=True)
        fold_records.append({
            "fold": int(fold),
            "n_train": int(len(train_ids)),
            "n_validation": int(len(valid_ids)),
            "training_id_hash": _id_hash(train_ids),
            "validation_id_hash": _id_hash(valid_ids),
            "fold_assignment_hash": _canonical_frame_hash(
                assignment, ["patient_id", "role"]),
        })
    source = frame.set_index(frame["patient_id"].astype(str)).loc[ids]
    left_risk = left.loc[ids, "risk"].to_numpy(dtype=float)
    right_risk = right.loc[ids, "risk"].to_numpy(dtype=float)
    time = source["DFS_time"].to_numpy(dtype=float)
    event = source["DFS_event"].to_numpy(dtype=int)
    left_c = harrell_c_index_hook(time, event, left_risk)
    right_c = harrell_c_index_hook(time, event, right_risk)
    return {
        "comparison_id": comparison_id,
        "left_model": left_model,
        "right_model": right_model,
        "population": population,
        "common_n": int(len(ids)),
        "common_id_hash": _id_hash(ids),
        "common_training_validation_are_identical": True,
        "folds": fold_records,
        "harrell_c_left": _json_number(left_c),
        "harrell_c_right": _json_number(right_c),
        "harrell_c_delta_right_minus_left": _json_number(right_c - left_c)
        if np.isfinite(left_c) and np.isfinite(right_c) else None,
        "eligibility_is_paired": True,
    }


def _json_number(value):
    return None if value is None or not np.isfinite(value) else float(value)


def _run_ft02_a_core(frame, split, model_ids, repeat=1, lambda_count=20,
                     max_iter=1000, tolerance=1e-7, split_source=None):
    """Run the in-memory core after the boundary and split have been proven."""
    split = validate_frozen_split(split, frame=frame, repeat=repeat)
    split_hash = _canonical_split_hash(split)
    split_seeds = sorted(set(split["seed"].astype(int).tolist()))
    if len(split_seeds) != 1:
        raise FTValidationError("frozen split has ambiguous repeat seed")
    if (split_source and split_source.get("canonical_sha256") and
            split_source["canonical_sha256"] != split_hash):
        raise FTValidationError("frozen split canonical hash mismatch")
    predictions = OrderedDict()
    model_results = OrderedDict()
    fitted_states = OrderedDict()
    population_counts = {}
    fit_cache = {}
    for model_id in model_ids:
        population = _model_population(model_id)
        key = (model_id, population, _id_hash(
            frame.loc[population_mask(frame, population), "patient_id"]))
        if key not in fit_cache:
            fit_cache[key] = _fit_model_cv(
                frame, split, model_id, population, lambda_count=lambda_count,
                max_iter=max_iter, tolerance=tolerance)
        fitted = fit_cache[key]
        population_counts[population] = int(len(fitted["eligible_ids"]))
        predictions[model_id] = fitted["prediction"]
        model_results[model_id] = fitted["record"]
        fitted_states[model_id] = fitted["states"]

    paired = []
    paired_states = OrderedDict()
    for comparison_id, left, right, population in FT_COMPARISONS:
        if left not in model_ids or right not in model_ids:
            continue
        left_population = population_mask(frame, _model_population(left))
        right_population = population_mask(frame, _model_population(right))
        common_mask = left_population & right_population
        common_ids = frame.loc[common_mask, "patient_id"].astype(str)
        if common_ids.empty:
            raise FTValidationError("paired comparison has no common eligible IDs")
        common_key = _id_hash(common_ids)
        left_key = (left, population, common_key)
        right_key = (right, population, common_key)
        if left_key not in fit_cache:
            common_frame = frame[frame["patient_id"].astype(str).isin(set(common_ids))]
            fit_cache[left_key] = _fit_model_cv(
                common_frame, split, left, population,
                lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance)
        if right_key not in fit_cache:
            common_frame = frame[frame["patient_id"].astype(str).isin(set(common_ids))]
            fit_cache[right_key] = _fit_model_cv(
                common_frame, split, right, population,
                lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance)
        left_fit = fit_cache[left_key]
        right_fit = fit_cache[right_key]
        paired.append(_paired_result(
            frame, left_fit, right_fit, comparison_id, left, right,
            population, split))
        paired_states[comparison_id] = {
            "population": population,
            "left": left_fit["states"],
            "right": right_fit["states"],
        }

    provenance = {
        "stage": FT_STAGE,
        "label": FT_LABEL,
        "a_only": True,
        "b_data_read": False,
        "split_repeat": int(repeat),
        "split_fold_count": 5,
        "split_hash": split_hash,
        "split_source": dict(split_source or {"kind": "validated_test_split"}),
        "input_schema_hash": schema_hash(frame),
        "input_id_hash": _id_hash(frame["patient_id"]),
        "w_original_feature_count": W_ORIGINAL_FEATURE_COUNT,
        "w_original_order_sha256": W_ORIGINAL_ORDER_SHA256,
        "runner_source": "prognosis_analysis/ft/ft02_runner.py",
        "runner_source_sha256": _sha256_file(__file__),
        "preprocessing_scope": "training_only",
        "lambda_scope": "outer_training_inner_5fold_only",
        "lambda_outer_validation_used": False,
    }
    return {
        "stage": FT_STAGE,
        "label": FT_LABEL,
        "model_definitions": json.loads(json.dumps(FT_MODEL_SPECS)),
        "split_provenance": {
            "repeat": int(repeat),
            "folds": [1, 2, 3, 4, 5],
            "seed": int(split_seeds[0]),
            "hash": split_hash,
            "regenerated": False,
        },
        "population_counts": population_counts,
        "models": model_results,
        "predictions": predictions,
        "paired_model_comparisons": paired,
        "fitted_state": {
            "native": fitted_states,
            "paired_comparisons": paired_states,
            "survival_horizons_months": {"3_year": 36.0, "5_year": 60.0},
        },
        "provenance": provenance,
        "validation": {
            "fail_closed": True,
            "a_cohort_proven": True,
            "b_data_read": False,
            "formal_outputs_written": False,
            "formal_lock_written": False,
        },
    }


def run_ft02_a(feature_frame, split_frame=None, models=None, lambda_count=20,
               max_iter=1000, tolerance=1e-7):
    """Production FT02 entry point bound to the frozen W07 repeat-1 artifact."""
    if split_frame is not None:
        raise FTValidationError(
            "production FT02 does not accept caller-supplied split tables")
    model_ids = list(FT_MODEL_SPECS if models is None else models)
    frozen_split, frozen_population = load_frozen_w07_repeat1()
    frame = validate_proven_a_frame(
        feature_frame, frozen_population, models=model_ids).reset_index(drop=True)
    split_source = {
        "kind": "project_locked_W07_repeat1",
        "artifact": "prognosis_analysis/output/outer_splits_A.csv",
        "artifact_sha256": W07_SPLIT_ARTIFACT_SHA256,
        "canonical_sha256": W07_REPEAT1_CANONICAL_SHA256,
        "repeat": W07_REPEAT1,
        "seed": W07_REPEAT1_SEED,
        "roles": list(W07_ROLES),
        "membership": "A393",
    }
    return _run_ft02_a_core(
        frame, frozen_split, model_ids, repeat=W07_REPEAT1,
        lambda_count=lambda_count, max_iter=max_iter, tolerance=tolerance,
        split_source=split_source)


def run_ft02_a_for_testing(feature_frame, split_frame, models=None, repeat=1,
                            lambda_count=20, max_iter=1000, tolerance=1e-7,
                            split_source=None):
    """Test-only synthetic runner; it is not a production A entry point."""
    model_ids = list(FT_MODEL_SPECS if models is None else models)
    frame = validate_ft_frame(feature_frame, models=model_ids).reset_index(drop=True)
    return _run_ft02_a_core(
        frame, split_frame, model_ids, repeat=repeat, lambda_count=lambda_count,
        max_iter=max_iter, tolerance=tolerance, split_source=split_source)


def harrell_c_index_hook(time, event, risk):
    return float(_w08.harrell_c_index(time, event, risk))


def uno_c_index_hook(training_time, training_event, evaluation_time,
                     evaluation_event, risk):
    return float(_w08.uno_c_index(
        training_time, training_event, evaluation_time, evaluation_event, risk))


def predict_risk_hook(model, preprocessor, frame):
    """Apply an already fitted fold model without fitting or tuning."""
    if not isinstance(preprocessor, FTPreprocessor):
        raise FTValidationError("risk prediction requires an FT preprocessor")
    checked = validate_ft_frame(frame, models=[preprocessor.model_id])
    risk = model.predict_risk(preprocessor.transform(checked))
    if not np.isfinite(risk).all():
        raise FTValidationError("risk prediction is nonfinite")
    return np.asarray(risk, dtype=float)


def predict_risk_survival_hook(model, preprocessor, frame,
                               horizons=(36.0, 60.0)):
    """Return risk and Cox survival probabilities for explicit horizons."""
    if not isinstance(preprocessor, FTPreprocessor):
        raise FTValidationError("survival prediction requires an FT preprocessor")
    checked = validate_ft_frame(frame, models=[preprocessor.model_id])
    X = preprocessor.transform(checked)
    risk = np.asarray(model.predict_risk(X), dtype=float)
    if not np.isfinite(risk).all():
        raise FTValidationError("risk prediction is nonfinite")
    horizon_map = OrderedDict()
    for horizon in horizons:
        horizon = float(horizon)
        if not np.isfinite(horizon) or horizon <= 0:
            raise FTValidationError("survival horizon must be finite and positive")
        horizon_map["%g_months" % horizon] = horizon
    survival = model.predict_survival(X, horizon_map)
    output = {"risk": risk}
    for name, values in survival.items():
        values = np.asarray(values, dtype=float)
        if len(values) != len(risk) or not np.isfinite(values).all() or \
                np.any(values < 0.0) or np.any(values > 1.0):
            raise FTValidationError("survival prediction is not a probability")
        output["survival_probability_%s" % name] = values
    return output


def predict_survival_hook(model, preprocessor, frame, horizons=(36.0, 60.0)):
    """Return only horizon-keyed survival probabilities for FT03 metrics."""
    result = predict_risk_survival_hook(
        model, preprocessor, frame, horizons=horizons)
    return {key: value for key, value in result.items()
            if key.startswith("survival_probability_")}


def _censoring_survival(training_time, training_event, query):
    return _w08._km_censoring_survival(training_time, training_event, query, left=True)


def time_dependent_auc_hook(training_frame, evaluation_frame, risk, horizon):
    """Case/control cumulative AUC with training-only censoring weights."""
    train_time = training_frame["DFS_time"].to_numpy(dtype=float)
    train_event = training_frame["DFS_event"].to_numpy(dtype=int)
    time = evaluation_frame["DFS_time"].to_numpy(dtype=float)
    event = evaluation_frame["DFS_event"].to_numpy(dtype=int)
    risk = np.asarray(risk, dtype=float)
    cases = np.where((event == 1) & (time <= float(horizon)))[0]
    controls = np.where(time > float(horizon))[0]
    concordant = tied = total = 0.0
    for i in cases:
        g_case = _censoring_survival(train_time, train_event, time[i])
        if g_case <= 1e-12:
            continue
        for j in controls:
            g_control = _censoring_survival(train_time, train_event, float(horizon))
            if g_control <= 1e-12:
                continue
            weight = 1.0 / (g_case * g_control)
            total += weight
            if risk[i] > risk[j]:
                concordant += weight
            elif risk[i] == risk[j]:
                tied += weight
    return float("nan") if total == 0 else float((concordant + 0.5 * tied) / total)


def auc_3_year_hook(training_frame, evaluation_frame, risk):
    return time_dependent_auc_hook(training_frame, evaluation_frame, risk, 36.0)


def auc_5_year_hook(training_frame, evaluation_frame, risk):
    return time_dependent_auc_hook(training_frame, evaluation_frame, risk, 60.0)


def brier_score_hook(training_frame, evaluation_frame, survival_probability, horizon):
    """IPCW Brier hook; censoring weights are estimated from training only."""
    train_time = training_frame["DFS_time"].to_numpy(dtype=float)
    train_event = training_frame["DFS_event"].to_numpy(dtype=int)
    time = evaluation_frame["DFS_time"].to_numpy(dtype=float)
    event = evaluation_frame["DFS_event"].to_numpy(dtype=int)
    prediction = np.asarray(survival_probability, dtype=float)
    if len(prediction) != len(time):
        raise FTValidationError("survival prediction length mismatch")
    contributions = []
    for current_time, current_event, estimate in zip(time, event, prediction):
        if current_event == 1 and current_time <= float(horizon):
            observed = 0.0
            g = _censoring_survival(train_time, train_event, current_time)
        elif current_time > float(horizon):
            observed = 1.0
            g = _censoring_survival(train_time, train_event, float(horizon))
        else:
            continue
        if g > 1e-12:
            contributions.append(((observed - float(estimate)) ** 2) / g)
    return float("nan") if not contributions else float(np.mean(contributions))


def brier_3_year_hook(training_frame, evaluation_frame, survival_probability):
    return brier_score_hook(training_frame, evaluation_frame, survival_probability, 36.0)


def brier_5_year_hook(training_frame, evaluation_frame, survival_probability):
    return brier_score_hook(training_frame, evaluation_frame, survival_probability, 60.0)


def calibration_data_hook(training_frame, evaluation_frame, survival_probability,
                          horizon, bins=5):
    time = evaluation_frame["DFS_time"].to_numpy(dtype=float)
    event = evaluation_frame["DFS_event"].to_numpy(dtype=int)
    prediction = np.asarray(survival_probability, dtype=float)
    usable = ((event == 1) & (time <= float(horizon))) | (time > float(horizon))
    if not np.any(usable):
        return {"horizon": float(horizon), "bins": [], "estimable_n": 0}
    values = prediction[usable]
    outcome = (((event[usable] == 1) & (time[usable] <= float(horizon)))).astype(float)
    edges = np.unique(np.quantile(values, np.linspace(0, 1, int(bins) + 1)))
    records = []
    for index in range(max(1, len(edges) - 1)):
        if len(edges) == 1:
            mask = np.ones(len(values), dtype=bool)
        elif index == len(edges) - 2:
            mask = (values >= edges[index]) & (values <= edges[index + 1])
        else:
            mask = (values >= edges[index]) & (values < edges[index + 1])
        if np.any(mask):
            records.append({"bin": int(index + 1), "n": int(mask.sum()),
                            "mean_predicted_survival": float(np.mean(values[mask])),
                            "observed_event_fraction": float(np.mean(outcome[mask]))})
    return {"horizon": float(horizon), "bins": records,
            "estimable_n": int(len(values)), "method": "uncensored_or_event_by_horizon"}


def km_data_hook(evaluation_frame, risk, groups=2):
    """Return Kaplan-Meier curve data split by a fixed risk rank."""
    time = evaluation_frame["DFS_time"].to_numpy(dtype=float)
    event = evaluation_frame["DFS_event"].to_numpy(dtype=int)
    risk = np.asarray(risk, dtype=float)
    if len(risk) != len(time):
        raise FTValidationError("KM risk length mismatch")
    labels = np.where(risk >= np.nanmedian(risk), "high", "low") if int(groups) == 2 else None
    if labels is None:
        raise FTValidationError("KM hook currently supports two groups")
    output = {}
    for label in ("low", "high"):
        mask = labels == label
        current_time = time[mask]
        current_event = event[mask]
        survival = 1.0
        curve = [{"time": 0.0, "survival": 1.0}]
        for point in sorted(np.unique(current_time[current_event == 1])):
            at_risk = int(np.sum(current_time >= point))
            deaths = int(np.sum((current_time == point) & (current_event == 1)))
            if at_risk:
                survival *= 1.0 - float(deaths) / float(at_risk)
                curve.append({"time": float(point), "survival": float(survival)})
        output[label] = {"n": int(mask.sum()), "curve": curve}
    return {"groups": output, "group_rule": "risk_median"}


def dca_data_hook(evaluation_frame, event_probability, horizon,
                  thresholds=None):
    """Return decision-curve net benefit points for a supplied horizon risk."""
    if thresholds is None:
        thresholds = np.linspace(0.05, 0.95, 19)
    time = evaluation_frame["DFS_time"].to_numpy(dtype=float)
    event = evaluation_frame["DFS_event"].to_numpy(dtype=int)
    prediction = np.asarray(event_probability, dtype=float)
    usable = ((event == 1) & (time <= float(horizon))) | (time > float(horizon))
    outcome = ((event[usable] == 1) & (time[usable] <= float(horizon))).astype(int)
    pred = prediction[usable]
    n = len(outcome)
    points = []
    for threshold in thresholds:
        threshold = float(threshold)
        positive = pred >= threshold
        tp = float(np.sum(positive & (outcome == 1)))
        fp = float(np.sum(positive & (outcome == 0)))
        points.append({"threshold": threshold,
                       "net_benefit": (tp / n - fp / n * threshold / (1 - threshold))
                       if n else float("nan"), "n": int(n)})
    return {"horizon": float(horizon), "points": points,
            "method": "uncensored_or_event_by_horizon"}


def bootstrap_ci_hook(metric_fn, n, n_bootstrap=200, seed=20260911,
                      mode="case_resample"):
    """Deterministic bootstrap hook with an explicit resampling mode."""
    if mode not in ("case_resample", "paired_case_resample"):
        raise FTValidationError("unsupported bootstrap mode: %s" % mode)
    if int(n) <= 1 or int(n_bootstrap) <= 0:
        raise FTValidationError("bootstrap requires positive sample and replicate counts")
    rng = np.random.RandomState(int(seed))
    estimate = metric_fn(np.arange(int(n), dtype=int))
    values = []
    for _ in range(int(n_bootstrap)):
        indices = rng.randint(0, int(n), size=int(n))
        value = metric_fn(indices)
        if value is not None and np.isfinite(value):
            values.append(float(value))
    if not values:
        return {"estimate": _json_number(estimate), "lower": None, "upper": None,
                "n_bootstrap": int(n_bootstrap), "n_estimable": 0,
                "seed": int(seed), "mode": mode}
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {"estimate": _json_number(estimate), "lower": float(lower),
            "upper": float(upper), "n_bootstrap": int(n_bootstrap),
            "n_estimable": int(len(values)), "seed": int(seed), "mode": mode}


def paired_comparison_hook(time, event, left_risk, right_risk,
                           metric=harrell_c_index_hook, n_bootstrap=0,
                           seed=20260911, mode="paired_case_resample"):
    """Compare two risk vectors on one already-aligned common population."""
    time = np.asarray(time, dtype=float)
    event = np.asarray(event, dtype=int)
    left = np.asarray(left_risk, dtype=float)
    right = np.asarray(right_risk, dtype=float)
    if not (len(time) == len(event) == len(left) == len(right)):
        raise FTValidationError("paired comparison vectors are not aligned")
    left_value = float(metric(time, event, left))
    right_value = float(metric(time, event, right))
    output = {"left": _json_number(left_value), "right": _json_number(right_value),
              "delta_right_minus_left": _json_number(right_value - left_value),
              "common_n": int(len(time)), "paired": True}
    if int(n_bootstrap) > 0:
        def delta(indices):
            return float(metric(time[indices], event[indices], right[indices]) -
                         metric(time[indices], event[indices], left[indices]))
        output["delta_bootstrap"] = bootstrap_ci_hook(
            delta, len(time), n_bootstrap=n_bootstrap, seed=seed, mode=mode)
    else:
        output["delta_bootstrap"] = {"n_bootstrap": 0, "seed": int(seed), "mode": mode}
    return output


def build_provenance_record(frame, split, split_source=None):
    """Build a shareable provenance record without patient-level values."""
    return {
        "stage": FT_STAGE,
        "label": FT_LABEL,
        "a_only": True,
        "b_data_read": False,
        "input_schema_hash": schema_hash(frame),
        "input_row_count": int(len(frame)),
        "input_id_hash": _id_hash(frame["patient_id"]),
        "split_hash": _canonical_frame_hash(split, split.columns),
        "split_source": dict(split_source or {"kind": "caller_supplied_frozen_split"}),
        "w_original": {"count": W_ORIGINAL_FEATURE_COUNT,
                       "order_sha256": W_ORIGINAL_ORDER_SHA256,
                       "image_type": "Original",
                       "filtered_features_excluded": True},
        "runner": "prognosis_analysis/ft/ft02_runner.py",
        "runner_sha256": _sha256_file(__file__),
    }
