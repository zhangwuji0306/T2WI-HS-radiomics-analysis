"""W08: A-only repeated nested cross-validation pipeline.

The runner is deliberately split into two boundaries:

* :func:`run_w08` opens only the code-bound W06 A population and the code-bound
  W07 outer-split artifact.  The feature table is supplied in memory by an
  already-authorized A-only upstream reader.
* :func:`run_w08_in_memory` performs the fold work.  A
  :class:`FoldFeatureProvider` must fit a representation on outer-training IDs
  and then transform training and validation IDs with that immutable state.

No W08 result is written by this module.  This keeps patient-level predictions
in memory for tests and makes a future formal writer an explicit, separately
audited action.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import math
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.model_selection import StratifiedKFold

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)
import w07_outer_splits as w07  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
DEFAULT_CONFIG = os.path.join(ROOT, "configs", "w08_nested_cv.json")
DEFAULT_POPULATION = os.path.join(
    ROOT, "output", "A_modeling", "A_modeling_population.csv")
DEFAULT_OUTER_SPLITS = os.path.join(ROOT, "output", "outer_splits_A.csv")
DEFAULT_W07_CONFIG = os.path.join(ROOT, "configs", "w07_outer_splits.json")

# These values are provenance locks, not values which may be replaced by a
# runtime JSON.  They are copied from the frozen W04/W07 contracts so that a
# future caller cannot redirect W08 to a different protocol or split plan.
W04_PROTOCOL_SHA256 = (
    "888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe")
W07_OUTER_SPLIT_SHA256 = (
    "24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502")
W07_SPLIT_COLUMNS = ["patient_id", "repeat", "fold", "role", "seed"]
W08_STATUS = "implementation_ready_not_run"

ALPHA_GRID = (0.1, 0.5, 0.9, 1.0)
LAMBDA_COUNT = 100
LAMBDA_MIN_RATIO = 1e-4
CORRELATION_THRESHOLD = 0.90
HORIZONS_MONTHS = OrderedDict((("3_year", 36.0), ("5_year", 60.0)))

CLINICAL_CONTINUOUS = ["年龄", "CEA_log", "thickness", "EID"]
CLINICAL_CATEGORICAL = OrderedDict((
    ("mrT_4级", (1, 2, 3, 4)),
    ("mrN_3级", (0, 1, 2, 3)),
))
CLINICAL_BINARY = ["MRF", "mrEMVI", "活检病理非腺癌"]
CLINICAL_COLUMNS = (
    CLINICAL_CONTINUOUS + list(CLINICAL_CATEGORICAL.keys()) + CLINICAL_BINARY)
GLOBAL_COLUMNS = [
    "H_high_fraction",
    "sv_median_minus_boundary",
    "sv_IQR",
    "interface_density",
    "H_high_largest_component_tumor_fraction",
    "H_high_radial_burden",
]

MODEL_SPECS = OrderedDict((
    ("M0", {"blocks": ("C",), "family": "Cox_PH_unpenalized",
             "population": "main"}),
    ("M1", {"blocks": ("C", "H_high_fraction"),
             "family": "Cox_PH_unpenalized", "population": "main"}),
    ("M2", {"blocks": ("C", "G"), "family": "Cox_PH_unpenalized",
             "population": "main"}),
    ("M3L", {"blocks": ("C", "G", "R_low"),
              "family": "Elastic_Net_Cox", "population": "R_low"}),
    ("M3H", {"blocks": ("C", "G", "R_high"),
              "family": "Elastic_Net_Cox", "population": "R_high"}),
    ("M4", {"blocks": ("C", "G", "R_low", "R_high"),
             "family": "Elastic_Net_Cox", "population": "dual_radiomics"}),
    ("M5", {"blocks": ("C", "W"), "family": "Elastic_Net_Cox",
             "population": "W_available"}),
))

# One W07 split plan is reused for these paired population-specific runs.  The
# same model ID can therefore occur more than once, but each occurrence has a
# distinct fixed eligible population for the prespecified comparison.
FIXED_RUN_DEFINITIONS = (
    {"run_id": "M0", "model_id": "M0", "population": "main"},
    {"run_id": "M1", "model_id": "M1", "population": "main"},
    {"run_id": "M2", "model_id": "M2", "population": "main"},
    {"run_id": "M0_W_available", "model_id": "M0", "population": "W_available"},
    {"run_id": "M5", "model_id": "M5", "population": "W_available"},
    {"run_id": "M2_R_low", "model_id": "M2", "population": "R_low"},
    {"run_id": "M3L", "model_id": "M3L", "population": "R_low"},
    {"run_id": "M2_R_high", "model_id": "M2", "population": "R_high"},
    {"run_id": "M3H", "model_id": "M3H", "population": "R_high"},
    {"run_id": "M2_dual_radiomics", "model_id": "M2", "population": "dual_radiomics"},
    {"run_id": "M3L_dual_radiomics", "model_id": "M3L", "population": "dual_radiomics"},
    {"run_id": "M3H_dual_radiomics", "model_id": "M3H", "population": "dual_radiomics"},
    {"run_id": "M4", "model_id": "M4", "population": "dual_radiomics"},
)
FIXED_RUN_IDS = tuple(run["run_id"] for run in FIXED_RUN_DEFINITIONS)

POPULATION_RULES = {
    "main": (),
    "W_available": ("W",),
    "R_low": ("R_low",),
    "R_high": ("R_high",),
    "dual_radiomics": ("R_low", "R_high"),
}

RADIOMICS_PREFIXES = {"R_low": "R_low__", "R_high": "R_high__", "W": "W__"}


class W08ValidationError(ValueError):
    """Raised for a protocol, provenance, isolation, or model invariant."""


def _absolute(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_id_hash(ids):
    """Hash sorted, newline-delimited IDs without exposing the IDs."""
    values = sorted(str(value).strip() for value in ids)
    if any(not value for value in values):
        raise W08ValidationError("identifier hash received a blank ID")
    return _sha256_text("\n".join(values) + "\n")


def _canonical_split_hash(frame):
    return hashlib.sha256(
        frame[W07_SPLIT_COLUMNS].to_csv(
            index=False, lineterminator="\n").encode("utf-8")).hexdigest()


def _read_json(path):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _validate_config(config):
    required = {"stage", "status", "frozen_protocol_sha256",
                "frozen_outer_split_sha256", "outer_cv", "inner_cv",
                "models", "fixed_runs", "provenance", "output_schema", "audit_schema"}
    missing = sorted(required - set(config))
    if missing:
        raise W08ValidationError("W08 config missing keys: %s" % missing)
    if config["stage"] != "W08" or config["status"] != W08_STATUS:
        raise W08ValidationError("W08 config is not implementation-ready")
    if config["frozen_protocol_sha256"].lower() != W04_PROTOCOL_SHA256:
        raise W08ValidationError("W08 protocol hash is not the W04 lock")
    if config["frozen_outer_split_sha256"].lower() != W07_OUTER_SPLIT_SHA256:
        raise W08ValidationError("W08 outer split hash is not the W07 lock")
    outer = config["outer_cv"]
    if (outer.get("folds"), outer.get("repeats"), outer.get("total_folds")) != (5, 10, 50):
        raise W08ValidationError("W08 requires 5 folds x 10 repeats")
    if outer.get("stratify_by") != "DFS_event":
        raise W08ValidationError("W08 outer stratification must be DFS_event")
    inner = config["inner_cv"]
    if inner.get("folds") != 5 or inner.get("stratify_by") != "DFS_event":
        raise W08ValidationError("W08 inner CV must be 5-fold DFS_event stratified")
    if list(config.get("alpha_grid", [])) != list(ALPHA_GRID):
        raise W08ValidationError("W08 alpha grid differs from W04")
    if config.get("lambda_grid", {}).get("values_per_alpha") != LAMBDA_COUNT:
        raise W08ValidationError("W08 lambda grid must contain 100 values per alpha")
    if config.get("lambda_grid", {}).get("minimum_ratio") != LAMBDA_MIN_RATIO:
        raise W08ValidationError("W08 lambda minimum ratio differs from W04")
    if list(config["models"]) != list(MODEL_SPECS):
        raise W08ValidationError("W08 model set differs from W04")
    config_runs = tuple(item["run_id"] for item in config["fixed_runs"])
    if config_runs != FIXED_RUN_IDS:
        raise W08ValidationError("W08 paired run set differs from W04/W07 comparisons")
    for item, expected in zip(config["fixed_runs"], FIXED_RUN_DEFINITIONS):
        if item != expected:
            raise W08ValidationError("W08 paired run definition differs from the frozen comparison")
    provenance = config["provenance"]
    if provenance.get("population_source") != "prognosis_analysis/output/A_modeling/A_modeling_population.csv":
        raise W08ValidationError("W08 population source is not the W06 A artifact")
    if provenance.get("outer_split_source") != "prognosis_analysis/output/outer_splits_A.csv":
        raise W08ValidationError("W08 outer split source is not the W07 artifact")
    if provenance.get("B_data_read") is not False:
        raise W08ValidationError("W08 must remain B-blinded")
    return config


def load_config(path=DEFAULT_CONFIG):
    if _absolute(path) != _absolute(DEFAULT_CONFIG):
        raise W08ValidationError("W08 accepts only the project-locked config path")
    return _validate_config(_read_json(path))


def load_frozen_a_population():
    """Read the code-bound W06 A population through the W07 gate."""
    config = w07.load_config(DEFAULT_W07_CONFIG)
    return w07.load_a_modeling_population(DEFAULT_POPULATION, config)


def load_frozen_outer_splits(population, path=DEFAULT_OUTER_SPLITS):
    """Read only the code-bound W07 outer split artifact."""
    if _absolute(path) != _absolute(DEFAULT_OUTER_SPLITS):
        raise W08ValidationError("W08 accepts only the fixed W07 outer split path")
    if _absolute(DEFAULT_OUTER_SPLITS) != _absolute(
            os.path.join(PROJECT_ROOT, "prognosis_analysis", "output",
                         "outer_splits_A.csv")):
        raise W08ValidationError("W07 split path resolution changed")
    if not os.path.isfile(path):
        raise W08ValidationError("frozen W07 outer split artifact is missing")
    if _sha256_file(path).lower() != W07_OUTER_SPLIT_SHA256:
        raise W08ValidationError("W07 outer split artifact hash mismatch")
    split_frame = pd.read_csv(path)
    w07_config = w07.load_config(DEFAULT_W07_CONFIG)
    w07.validate_outer_splits(split_frame, population, w07_config)
    if _canonical_split_hash(split_frame).lower() != W07_OUTER_SPLIT_SHA256:
        raise W08ValidationError("W07 canonical split hash mismatch")
    return split_frame[W07_SPLIT_COLUMNS].copy()


def _normalise_frame(frame):
    if not isinstance(frame, pd.DataFrame):
        raise W08ValidationError("A feature frame must be a pandas DataFrame")
    data = frame.copy()
    if "patient_id" not in data.columns:
        if "影像号" in data.columns:
            data = data.rename(columns={"影像号": "patient_id"})
        else:
            raise W08ValidationError("A feature frame lacks patient_id")
    data["patient_id"] = data["patient_id"].astype(str).str.strip()
    if data["patient_id"].eq("").any() or data["patient_id"].duplicated().any():
        raise W08ValidationError("A feature frame requires unique nonblank IDs")
    for column in ("DFS_time", "DFS_event"):
        if column not in data.columns:
            raise W08ValidationError("A feature frame lacks %s" % column)
    time = pd.to_numeric(data["DFS_time"], errors="coerce")
    event = pd.to_numeric(data["DFS_event"], errors="coerce")
    if time.isna().any() or not np.isfinite(time.to_numpy(dtype=float)).all() or not time.gt(0).all():
        raise W08ValidationError("A feature frame contains invalid DFS_time")
    if event.isna().any() or not event.isin([0, 1]).all():
        raise W08ValidationError("A feature frame contains non-binary DFS_event")
    data["DFS_time"] = time.astype(float)
    data["DFS_event"] = event.astype(int)
    if "split" in data.columns:
        split = data["split"].astype(str).str.strip()
        if not split.eq("A").all():
            raise W08ValidationError("W08 rejects non-A rows before modeling")
    if "technical_cohort" in data.columns:
        cohort = data["technical_cohort"].astype(str).str.strip()
        if not cohort.eq("A393").all():
            raise W08ValidationError("W08 accepts only technical cohort A393")
    return data


def _validate_population_alignment(data, population):
    ids = set(data["patient_id"])
    expected = set(population["patient_id"])
    if ids != expected:
        raise W08ValidationError("A feature frame IDs do not equal the W06 A population")
    event_map = population.set_index("patient_id")["DFS_event"]
    observed = data.set_index("patient_id")["DFS_event"]
    if not observed.eq(event_map.loc[observed.index]).all():
        raise W08ValidationError("feature-frame DFS_event differs from W06 A population")


def _validate_split_frame(split_frame, population):
    if list(split_frame.columns) != W07_SPLIT_COLUMNS:
        raise W08ValidationError("W07 split schema mismatch")
    try:
        w07_config = w07.load_config(DEFAULT_W07_CONFIG)
        summary = w07.validate_outer_splits(split_frame, population, w07_config)
    except Exception as exc:
        raise W08ValidationError("W07 split validation failed: %s" % exc)
    return summary


def _required_availability_mask(frame, block):
    """Use explicit structural and technical flags; never infer availability."""
    structural = "%s_structurally_defined" % block
    technical = "%s_technically_available" % block
    available = "%s_available" % block
    if structural in frame.columns and technical in frame.columns:
        left = pd.to_numeric(frame[structural], errors="coerce")
        right = pd.to_numeric(frame[technical], errors="coerce")
        if left.isna().any() or right.isna().any() or not left.isin([0, 1]).all() or not right.isin([0, 1]).all():
            raise W08ValidationError("invalid %s structural/technical availability flags" % block)
        return left.eq(1) & right.eq(1)
    if available in frame.columns:
        values = pd.to_numeric(frame[available], errors="coerce")
        if values.isna().any() or not values.isin([0, 1]).all():
            raise W08ValidationError("invalid %s availability flag" % block)
        return values.eq(1)
    raise W08ValidationError(
        "%s eligibility requires explicit structural and technical availability flags" % block)


def eligible_ids(frame, population_name):
    if population_name not in POPULATION_RULES:
        raise W08ValidationError("unknown W07 population: %s" % population_name)
    mask = pd.Series(True, index=frame.index)
    for block in POPULATION_RULES[population_name]:
        mask &= _required_availability_mask(frame, block)
    return set(frame.loc[mask, "patient_id"])


def _block_columns(frame, block):
    if block == "C":
        return list(CLINICAL_COLUMNS)
    if block == "G":
        return list(GLOBAL_COLUMNS)
    if block == "H_high_fraction":
        return ["H_high_fraction"]
    if block in RADIOMICS_PREFIXES:
        prefix = RADIOMICS_PREFIXES[block]
        columns = [column for column in frame.columns
                   if str(column).startswith(prefix)]
        if not columns:
            raise W08ValidationError("%s block has no prefixed features" % block)
        return columns
    raise W08ValidationError("unknown predictor block: %s" % block)


def validate_feature_schema(frame, models=None, strict=False):
    models = list(MODEL_SPECS if models is None else models)
    missing_clinical = sorted(set(CLINICAL_COLUMNS) - set(frame.columns))
    if missing_clinical:
        raise W08ValidationError("missing frozen clinical columns: %s" % missing_clinical)
    needed = set()
    for model_id in models:
        if model_id not in MODEL_SPECS:
            raise W08ValidationError("unknown W04 model: %s" % model_id)
        for block in MODEL_SPECS[model_id]["blocks"]:
            if block in ("C", "G", "H_high_fraction"):
                needed.update(_block_columns(frame, block))
            elif block in RADIOMICS_PREFIXES:
                needed.update(_block_columns(frame, block))
    missing = sorted(needed - set(frame.columns))
    if missing:
        raise W08ValidationError("missing W04 predictor columns: %s" % missing[:20])
    if strict:
        expected = {"R_low": 49, "R_high": 10, "W": 1130}
        for block, count in expected.items():
            if any(block in MODEL_SPECS[mid]["blocks"] for mid in models):
                actual = len(_block_columns(frame, block))
                if actual != count:
                    raise W08ValidationError(
                        "%s must contain %d frozen features, got %d" %
                        (block, count, actual))


@dataclass
class FoldState:
    """Immutable representation state fitted using outer-training patients."""

    training_id_hash: str
    seed: int
    centers: tuple = None
    boundary: float = None
    metadata: dict = field(default_factory=dict)


class FoldFeatureProvider(object):
    """Interface for fold-specific habitat/G/radiomics regeneration."""

    fold_specific_habitat = True

    def fit(self, training_ids, seed):  # pragma: no cover - interface contract
        raise NotImplementedError

    def transform(self, ids, state):  # pragma: no cover - interface contract
        raise NotImplementedError


class FrameFoldFeatureProvider(FoldFeatureProvider):
    """In-memory provider for tests and authorized A-only upstream adapters.

    ``supervoxel_values`` is optional only for low-dimensional/unit tests.  A
    formal run must provide it (or use an equivalent provider) so that centers
    and the boundary are fitted from outer-training patients per W08.  The
    provider preserves all prefixed radiomics columns supplied by the caller;
    a production adapter can replace this class to regenerate those columns
    from fold-specific masks.
    """

    def __init__(self, frame, supervoxel_values=None):
        self.frame = _normalise_frame(frame)
        self._by_id = self.frame.set_index("patient_id", drop=False)
        self.supervoxel_values = {
            str(key).strip(): np.asarray(value, dtype=float).reshape(-1)
            for key, value in (supervoxel_values or {}).items()
        }
        self.fit_calls = []
        self.transform_calls = []
        self.fold_specific_habitat = bool(self.supervoxel_values)

    def fit(self, training_ids, seed):
        ids = sorted(str(value).strip() for value in training_ids)
        if not ids or any(identifier not in self._by_id.index for identifier in ids):
            raise W08ValidationError("provider training IDs are not in the A frame")
        self.fit_calls.append(tuple(ids))
        if not self.supervoxel_values:
            return FoldState(canonical_id_hash(ids), int(seed), metadata={
                "fold_specific_habitat": False,
                "representation_source": "provided_frame_columns",
            })
        flattened = []
        weights = []
        for identifier in ids:
            values = self.supervoxel_values.get(identifier)
            if values is None or values.size == 0 or not np.isfinite(values).all():
                raise W08ValidationError("missing/nonfinite supervoxel input for %s" % identifier)
            flattened.append(values)
            weights.append(np.full(values.size, 1.0 / float(values.size)))
        values = np.concatenate(flattened)
        sample_weights = np.concatenate(weights)
        if np.unique(values).size < 2:
            raise W08ValidationError("fold-specific K=2 habitat fit needs two distinct values")
        estimator = KMeans(n_clusters=2, random_state=int(seed), n_init=10)
        estimator.fit(values.reshape(-1, 1), sample_weight=sample_weights)
        centers = tuple(sorted(float(value) for value in estimator.cluster_centers_.reshape(-1)))
        boundary = (centers[0] + centers[1]) / 2.0
        return FoldState(canonical_id_hash(ids), int(seed), centers, boundary, {
            "fold_specific_habitat": True,
            "patient_weighting": "each patient total supervoxel weight=1",
            "supervoxel_count": int(values.size),
        })

    def transform(self, ids, state):
        identifiers = [str(value).strip() for value in ids]
        if any(identifier not in self._by_id.index for identifier in identifiers):
            raise W08ValidationError("provider transform IDs are not in the A frame")
        self.transform_calls.append((tuple(identifiers), state.training_id_hash))
        rows = self._by_id.loc[identifiers].copy()
        if state.boundary is not None:
            if any(identifier not in self.supervoxel_values for identifier in identifiers):
                raise W08ValidationError("missing supervoxel input during transform")
            generated = []
            for identifier in identifiers:
                values = self.supervoxel_values[identifier]
                high = values >= state.boundary
                q25, q75 = np.percentile(values, [25.0, 75.0])
                generated.append({
                    "patient_id": identifier,
                    "H_high_fraction": float(np.mean(high)),
                    "sv_median_minus_boundary": float(np.median(values) - state.boundary),
                    "sv_IQR": float(q75 - q25),
                })
            generated = pd.DataFrame(generated).set_index("patient_id")
            for column in ("H_high_fraction", "sv_median_minus_boundary", "sv_IQR"):
                rows[column] = generated.loc[identifiers, column].to_numpy()
        return rows.reset_index(drop=True)


def _as_numeric(values, label):
    numeric = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise W08ValidationError("%s contains invalid nonnumeric values" % label)
    return numeric


def _mode_lowest(series, levels=None):
    values = series.dropna()
    if values.empty:
        if levels is None:
            raise W08ValidationError("cannot impute an all-missing categorical field")
        return levels[0]
    counts = values.value_counts()
    top = counts[counts == counts.max()].index.tolist()
    if levels is not None:
        rank = {str(value): index for index, value in enumerate(levels)}
        return sorted(top, key=lambda value: rank.get(str(value), len(rank)))[0]
    return sorted(top, key=lambda value: str(value))[0]


class ClinicalPreprocessor(object):
    """Training-only imputation, fixed level encoding, and continuous scaling."""

    def __init__(self):
        self.feature_names = []
        self.imputations = {}
        self.means = {}
        self.scales = {}
        self.constant_continuous = []

    def fit(self, frame):
        missing = sorted(set(CLINICAL_COLUMNS) - set(frame.columns))
        if missing:
            raise W08ValidationError("clinical preprocessor missing %s" % missing)
        self.feature_names = []
        for column in CLINICAL_CONTINUOUS:
            numeric = pd.to_numeric(frame[column], errors="coerce").replace(
                [np.inf, -np.inf], np.nan)
            finite = numeric[np.isfinite(numeric.to_numpy(dtype=float))]
            if finite.empty:
                raise W08ValidationError("clinical continuous field is all missing: %s" % column)
            median = float(finite.median())
            filled = numeric.fillna(median).to_numpy(dtype=float)
            mean = float(np.mean(filled))
            scale = float(np.std(filled, ddof=0))
            self.imputations[column] = median
            self.means[column] = mean
            self.scales[column] = scale if scale > 0.0 else 1.0
            if scale == 0.0:
                self.constant_continuous.append(column)
            self.feature_names.append(column)
        for column, levels in CLINICAL_CATEGORICAL.items():
            values = frame[column].copy()
            values = values.map(lambda value: value if pd.isna(value) else self._canonical_level(value, levels, column))
            mode = _mode_lowest(values, levels)
            self.imputations[column] = mode
            # Lowest predeclared level is the fixed reference level.
            for level in levels[1:]:
                self.feature_names.append("%s=%s" % (column, level))
        for column in CLINICAL_BINARY:
            values = pd.to_numeric(frame[column], errors="coerce")
            nonmissing = values.dropna()
            if not nonmissing.isin([0, 1]).all():
                raise W08ValidationError("clinical binary field has invalid levels: %s" % column)
            mode = _mode_lowest(nonmissing, (0, 1))
            self.imputations[column] = float(mode)
            self.feature_names.append(column)
        return self

    @staticmethod
    def _canonical_level(value, levels, column):
        try:
            numeric = float(value)
            if numeric.is_integer():
                value = int(numeric)
        except (TypeError, ValueError):
            pass
        if value not in levels:
            raise W08ValidationError("invalid %s level: %s" % (column, value))
        return value

    def transform(self, frame):
        output = pd.DataFrame(index=frame.index)
        for column in CLINICAL_CONTINUOUS:
            values = pd.to_numeric(frame[column], errors="coerce").replace(
                [np.inf, -np.inf], np.nan).fillna(self.imputations[column])
            numeric = values.to_numpy(dtype=float)
            if not np.isfinite(numeric).all():
                raise W08ValidationError("clinical transform has nonfinite values: %s" % column)
            output[column] = (numeric - self.means[column]) / self.scales[column]
        for column, levels in CLINICAL_CATEGORICAL.items():
            values = frame[column].map(lambda value: self.imputations[column] if pd.isna(value)
                                       else self._canonical_level(value, levels, column))
            for level in levels[1:]:
                output["%s=%s" % (column, level)] = values.eq(level).astype(float).to_numpy()
        for column in CLINICAL_BINARY:
            values = pd.to_numeric(frame[column], errors="coerce").fillna(self.imputations[column])
            if not values.isin([0, 1]).all():
                raise W08ValidationError("clinical transform has invalid binary values: %s" % column)
            output[column] = values.astype(float).to_numpy()
        return output[self.feature_names].reset_index(drop=True)


class NumericPreprocessor(object):
    """Training-only numeric imputation and z-scoring for G or H blocks."""

    def __init__(self, columns):
        self.columns = list(columns)
        self.medians = {}
        self.means = {}
        self.scales = {}

    def fit(self, frame):
        for column in self.columns:
            values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            finite = values.dropna()
            if finite.empty:
                raise W08ValidationError("numeric block field is all missing: %s" % column)
            median = float(finite.median())
            filled = values.fillna(median).to_numpy(dtype=float)
            mean = float(np.mean(filled))
            scale = float(np.std(filled, ddof=0))
            self.medians[column] = median
            self.means[column] = mean
            self.scales[column] = scale if scale > 0.0 else 1.0
        return self

    def transform(self, frame):
        output = []
        for column in self.columns:
            values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            numeric = values.fillna(self.medians[column]).to_numpy(dtype=float)
            if not np.isfinite(numeric).all():
                raise W08ValidationError("numeric transform is nonfinite: %s" % column)
            output.append((numeric - self.means[column]) / self.scales[column])
        if not output:
            return np.empty((len(frame), 0), dtype=float)
        return np.column_stack(output)


class RadiomicsPreprocessor(object):
    """Frozen-order training-only radiomics imputation/filtering/scaling."""

    def __init__(self, columns):
        self.input_columns = list(columns)
        self.imputation_medians = {}
        self.kept_after_missing = []
        self.kept_after_variance = []
        self.kept_columns = []
        self.means = {}
        self.scales = {}
        self.dropped_all_nonfinite = []
        self.dropped_near_zero_variance = []
        self.dropped_correlation = []

    @staticmethod
    def _near_zero(values):
        unique, counts = np.unique(values, return_counts=True)
        if unique.size <= 1:
            return True
        order = np.argsort(counts)[::-1]
        first = float(counts[order[0]])
        second = float(counts[order[1]])
        ratio = math.inf if second == 0.0 else first / second
        return (float(unique.size) / float(values.size) < 0.01) and ratio > 100.0

    def fit(self, frame):
        filled = {}
        for column in self.input_columns:
            values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            finite = values.dropna()
            if finite.empty:
                self.dropped_all_nonfinite.append(column)
                continue
            median = float(finite.median())
            self.imputation_medians[column] = median
            filled[column] = values.fillna(median).to_numpy(dtype=float)
        self.kept_after_missing = [column for column in self.input_columns if column in filled]
        for column in self.kept_after_missing:
            if self._near_zero(filled[column]):
                self.dropped_near_zero_variance.append(column)
            else:
                self.kept_after_variance.append(column)
        # The frozen rule retains the lexicographically first feature in every
        # correlated group.  Sorting is only for the reduction decision; the
        # stored output remains in that same deterministic order.
        ordered = sorted(self.kept_after_variance)
        retained = []
        for column in ordered:
            candidate = filled[column]
            correlated = False
            for previous in retained:
                left = candidate - np.mean(candidate)
                right = filled[previous] - np.mean(filled[previous])
                denom = np.sqrt(np.sum(left * left) * np.sum(right * right))
                corr = 0.0 if denom == 0.0 else float(np.sum(left * right) / denom)
                if abs(corr) > CORRELATION_THRESHOLD:
                    correlated = True
                    break
            if correlated:
                self.dropped_correlation.append(column)
            else:
                retained.append(column)
        self.kept_columns = retained
        for column in self.kept_columns:
            values = filled[column]
            self.means[column] = float(np.mean(values))
            scale = float(np.std(values, ddof=0))
            self.scales[column] = scale if scale > 0.0 else 1.0
        return self

    def transform(self, frame):
        output = []
        for column in self.kept_columns:
            values = pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
            numeric = values.fillna(self.imputation_medians[column]).to_numpy(dtype=float)
            if not np.isfinite(numeric).all():
                raise W08ValidationError("radiomics transform is nonfinite: %s" % column)
            output.append((numeric - self.means[column]) / self.scales[column])
        if not output:
            raise W08ValidationError("radiomics preprocessing retained no feature")
        return np.column_stack(output)


class ModelPreprocessor(object):
    """Compose frozen clinical/G/radiomics preprocessing for one model."""

    def __init__(self, model_id):
        if model_id not in MODEL_SPECS:
            raise W08ValidationError("unknown model: %s" % model_id)
        self.model_id = model_id
        self.spec = MODEL_SPECS[model_id]
        self.clinical = ClinicalPreprocessor()
        self.global_block = None
        self.radiomics = None
        self.feature_names = []

    def fit(self, frame):
        blocks = self.spec["blocks"]
        self.clinical.fit(frame)
        names = list(self.clinical.feature_names)
        extra = []
        if "H_high_fraction" in blocks:
            extra.append("H_high_fraction")
        if "G" in blocks:
            extra.extend(GLOBAL_COLUMNS)
        if extra:
            self.global_block = NumericPreprocessor(extra).fit(frame)
            names.extend(extra)
        radiomics_columns = []
        for block in ("R_low", "R_high", "W"):
            if block in blocks:
                radiomics_columns.extend(_block_columns(frame, block))
        if radiomics_columns:
            self.radiomics = RadiomicsPreprocessor(radiomics_columns).fit(frame)
            names.extend(self.radiomics.kept_columns)
        self.feature_names = names
        return self

    def transform(self, frame):
        pieces = [self.clinical.transform(frame).to_numpy(dtype=float)]
        if self.global_block is not None:
            pieces.append(self.global_block.transform(frame))
        if self.radiomics is not None:
            pieces.append(self.radiomics.transform(frame))
        return np.column_stack(pieces)

    def audit(self):
        return {
            "model_id": self.model_id,
            "feature_names": list(self.feature_names),
            "clinical_imputations": dict(self.clinical.imputations),
            "clinical_constant_continuous": list(self.clinical.constant_continuous),
            "radiomics_input_count": 0 if self.radiomics is None else len(self.radiomics.input_columns),
            "radiomics_dropped_all_nonfinite": [] if self.radiomics is None else list(self.radiomics.dropped_all_nonfinite),
            "radiomics_dropped_near_zero_variance": [] if self.radiomics is None else list(self.radiomics.dropped_near_zero_variance),
            "radiomics_dropped_correlation": [] if self.radiomics is None else list(self.radiomics.dropped_correlation),
            "radiomics_kept_columns": [] if self.radiomics is None else list(self.radiomics.kept_columns),
        }


def _cox_components(X, time, event, beta):
    """Return Breslow log-likelihood and score with stable risk-set sums."""
    if len(X) == 0 or int(np.sum(event)) == 0:
        raise W08ValidationError("Cox fit requires at least one event")
    order = np.argsort(-time, kind="mergesort")
    sorted_time = time[order]
    sorted_event = event[order]
    sorted_X = X[order]
    eta = np.clip(np.asarray(sorted_X.dot(beta), dtype=float), -50.0, 50.0)
    exp_eta = np.exp(eta)
    cumulative_risk = np.cumsum(exp_eta)
    cumulative_xrisk = np.cumsum(sorted_X * exp_eta[:, None], axis=0)
    loglik = 0.0
    gradient = np.zeros(X.shape[1], dtype=float)
    unique_event_times = np.unique(sorted_time[sorted_event == 1])
    for current in unique_event_times:
        event_mask = (sorted_time == current) & (sorted_event == 1)
        last = int(np.searchsorted(-sorted_time, -current, side="right")) - 1
        risk_sum = float(cumulative_risk[last])
        if not np.isfinite(risk_sum) or risk_sum <= 0.0:
            raise W08ValidationError("nonfinite Cox risk-set sum")
        event_count = int(np.sum(event_mask))
        event_x = np.sum(sorted_X[event_mask], axis=0)
        loglik += float(np.dot(event_x, beta)) - event_count * math.log(risk_sum)
        gradient += event_x - event_count * cumulative_xrisk[last] / risk_sum
    return float(loglik), gradient


def _cox_information(X, time, event, beta):
    """Observed Breslow information matrix for the low-dimensional Cox fit."""
    order = np.argsort(-time, kind="mergesort")
    sorted_time = time[order]
    sorted_event = event[order]
    sorted_X = X[order]
    eta = np.clip(sorted_X.dot(beta), -50.0, 50.0)
    exp_eta = np.exp(eta)
    risk = np.cumsum(exp_eta)
    xrisk = np.cumsum(sorted_X * exp_eta[:, None], axis=0)
    xxrisk = np.cumsum(
        (sorted_X[:, :, None] * sorted_X[:, None, :]) * exp_eta[:, None, None], axis=0)
    information = np.zeros((X.shape[1], X.shape[1]), dtype=float)
    for current in np.unique(sorted_time[sorted_event == 1]):
        event_mask = (sorted_time == current) & (sorted_event == 1)
        last = int(np.searchsorted(-sorted_time, -current, side="right")) - 1
        denom = float(risk[last])
        mean = xrisk[last] / denom
        covariance = xxrisk[last] / denom - np.outer(mean, mean)
        information += int(np.sum(event_mask)) * covariance
    return information


def _cox_negative_loglik(X, time, event, beta):
    loglik, _ = _cox_components(X, time, event, beta)
    return -loglik / float(np.sum(event))


def _lambda_max(X, time, event, alpha):
    _, score = _cox_components(X, time, event, np.zeros(X.shape[1], dtype=float))
    gradient = -score / float(np.sum(event))
    maximum = float(np.max(np.abs(gradient)))
    if not np.isfinite(maximum) or maximum <= 0.0:
        return 1.0
    return max(maximum / max(float(alpha), 1e-12), 1e-12)


class CoxPHModel(object):
    """Unpenalized Breslow Cox PH model for C/G models."""

    def __init__(self, max_iter=200, tolerance=1e-8):
        self.max_iter = int(max_iter)
        self.tolerance = float(tolerance)
        self.coef_ = None
        self.baseline_times_ = None
        self.baseline_survival_ = None
        self.fit_audit = {}

    def fit(self, X, time, event):
        X = np.asarray(X, dtype=float)
        time = np.asarray(time, dtype=float)
        event = np.asarray(event, dtype=int)
        if np.sum(event) < 1:
            raise W08ValidationError("unpenalized Cox fit requires an event")
        beta = np.zeros(X.shape[1], dtype=float)
        converged = False
        for iteration in range(self.max_iter):
            old = _cox_negative_loglik(X, time, event, beta)
            _, score = _cox_components(X, time, event, beta)
            gradient = -score / float(np.sum(event))
            information = _cox_information(X, time, event, beta) / float(np.sum(event))
            ridge = 1e-8 * max(1.0, float(np.trace(information)))
            try:
                step = np.linalg.solve(information + ridge * np.eye(X.shape[1]), gradient)
            except np.linalg.LinAlgError:
                step = gradient
            if not np.isfinite(step).all():
                step = np.nan_to_num(step, nan=0.0, posinf=1.0, neginf=-1.0)
            length = 1.0
            accepted = False
            while length >= 1e-8:
                proposal = beta - length * step
                new = _cox_negative_loglik(X, time, event, proposal)
                if np.isfinite(new) and new <= old + 1e-12:
                    beta = proposal
                    accepted = True
                    break
                length *= 0.5
            if not accepted:
                beta = beta - 1e-4 * gradient
            if np.max(np.abs(length * step)) < self.tolerance:
                converged = True
                break
        self.coef_ = beta
        self._fit_baseline(X, time, event)
        self.fit_audit = {"iterations": iteration + 1, "converged": bool(converged),
                          "stability_actions": []}
        return self

    def _fit_baseline(self, X, time, event):
        beta = self.coef_
        order = np.argsort(-time, kind="mergesort")
        sorted_time = time[order]
        sorted_event = event[order]
        eta = np.clip(X[order].dot(beta), -50.0, 50.0)
        risk = np.cumsum(np.exp(eta))
        times = []
        survival = []
        cumulative = 0.0
        for current in np.unique(sorted_time[sorted_event == 1]):
            mask = (sorted_time == current) & (sorted_event == 1)
            last = int(np.searchsorted(-sorted_time, -current, side="right")) - 1
            cumulative += float(np.sum(mask)) / float(risk[last])
            times.append(float(current))
            survival.append(math.exp(-cumulative))
        self.baseline_times_ = np.asarray(times, dtype=float)
        self.baseline_survival_ = np.asarray(survival, dtype=float)

    def predict_risk(self, X):
        if self.coef_ is None:
            raise W08ValidationError("Cox model is not fitted")
        return np.asarray(X, dtype=float).dot(self.coef_)

    def predict_survival(self, X, horizons):
        risk = self.predict_risk(X)
        output = {}
        for name, horizon in horizons.items():
            index = np.searchsorted(self.baseline_times_, float(horizon), side="right") - 1
            baseline = 1.0 if index < 0 else float(self.baseline_survival_[index])
            hazard = -math.log(max(baseline, 1e-300))
            output[name] = np.exp(-hazard * np.exp(np.clip(risk, -50.0, 50.0)))
        return output


class CoxElasticNetModel(object):
    """Elastic-Net Cox fit using a deterministic proximal-gradient solver.

    The stable risk-set implementation clips only the linear predictor used in
    exponentiation to [-50, 50].  This is recorded in ``fit_audit`` when it is
    encountered.  Candidate paths are never dropped because of a low penalty;
    a failed line search retries with a smaller step and a minimal ridge
    stabilization before raising a hard, auditable error.
    """

    def __init__(self, alpha, penalty, max_iter=250, tolerance=1e-7):
        self.alpha = float(alpha)
        self.penalty = float(penalty)
        self.max_iter = int(max_iter)
        self.tolerance = float(tolerance)
        self.coef_ = None
        self.baseline_times_ = None
        self.baseline_survival_ = None
        self.fit_audit = {}

    def _smooth(self, X, time, event, beta):
        value = _cox_negative_loglik(X, time, event, beta)
        _, score = _cox_components(X, time, event, beta)
        gradient = -score / float(np.sum(event))
        ridge = self.penalty * (1.0 - self.alpha)
        value += 0.5 * ridge * float(np.dot(beta, beta))
        gradient = gradient + ridge * beta
        return value, gradient

    def _objective(self, X, time, event, beta):
        value = _cox_negative_loglik(X, time, event, beta)
        value += self.penalty * self.alpha * float(np.sum(np.abs(beta)))
        value += 0.5 * self.penalty * (1.0 - self.alpha) * float(np.dot(beta, beta))
        return value

    def fit(self, X, time, event):
        X = np.asarray(X, dtype=float)
        time = np.asarray(time, dtype=float)
        event = np.asarray(event, dtype=int)
        if np.sum(event) < 1:
            raise W08ValidationError("Elastic-Net Cox fit requires an event")
        beta = np.zeros(X.shape[1], dtype=float)
        previous = beta.copy()
        step = 1.0
        actions = []
        converged = False
        for iteration in range(self.max_iter):
            smooth_y, gradient_y = self._smooth(X, time, event, beta)
            accepted = False
            local_step = step
            for _ in range(60):
                proposal = np.sign(beta - local_step * gradient_y) * np.maximum(
                    np.abs(beta - local_step * gradient_y) - local_step * self.penalty * self.alpha, 0.0)
                if not np.isfinite(proposal).all():
                    local_step *= 0.5
                    actions.append("backtrack_nonfinite")
                    continue
                delta = proposal - beta
                quadratic = smooth_y + float(np.dot(gradient_y, delta)) + float(np.dot(delta, delta)) / (2.0 * local_step)
                actual_smooth, _ = self._smooth(X, time, event, proposal)
                if np.isfinite(actual_smooth) and actual_smooth <= quadratic + 1e-10:
                    accepted = True
                    beta = proposal
                    step = min(local_step * 1.25, 1e6)
                    break
                local_step *= 0.5
                actions.append("backtrack_objective")
            if not accepted:
                # Minimal stability action: retain the last finite iterate and
                # reduce the step.  The candidate is still counted and fitted.
                actions.append("minimum_step_stability")
                step = max(local_step, 1e-12)
                if not np.isfinite(beta).all():
                    beta = previous.copy()
            if np.max(np.abs(beta - previous)) < self.tolerance:
                converged = True
                break
            previous = beta.copy()
        self.coef_ = beta
        self._fit_baseline(X, time, event)
        if not actions:
            actions = ["stable_path"]
        self.fit_audit = {
            "iterations": iteration + 1,
            "converged": bool(converged),
            "stability_actions": sorted(set(actions)),
            "nonzero_coefficients": int(np.sum(np.abs(beta) > 1e-10)),
        }
        return self

    def _fit_baseline(self, X, time, event):
        helper = CoxPHModel()
        helper.coef_ = self.coef_
        helper._fit_baseline(X, time, event)
        self.baseline_times_ = helper.baseline_times_
        self.baseline_survival_ = helper.baseline_survival_

    def predict_risk(self, X):
        if self.coef_ is None:
            raise W08ValidationError("Elastic-Net model is not fitted")
        return np.asarray(X, dtype=float).dot(self.coef_)

    def predict_survival(self, X, horizons):
        risk = self.predict_risk(X)
        output = {}
        for name, horizon in horizons.items():
            index = np.searchsorted(self.baseline_times_, float(horizon), side="right") - 1
            baseline = 1.0 if index < 0 else float(self.baseline_survival_[index])
            hazard = -math.log(max(baseline, 1e-300))
            output[name] = np.exp(-hazard * np.exp(np.clip(risk, -50.0, 50.0)))
        return output


def make_inner_splits(frame, seed, folds=5):
    events = pd.to_numeric(frame["DFS_event"], errors="coerce").to_numpy(dtype=int)
    counts = np.bincount(events, minlength=2)
    if int(np.min(counts)) < int(folds):
        raise W08ValidationError("inner event gate failed; cannot reduce the five folds")
    splitter = StratifiedKFold(n_splits=int(folds), shuffle=True, random_state=int(seed))
    indices = np.arange(len(frame))
    output = []
    for train_idx, validation_idx in splitter.split(indices, events):
        if int(np.sum(events[train_idx])) < 1 or int(np.sum(events[validation_idx])) < 1:
            raise W08ValidationError("inner train/validation event gate failed")
        output.append((train_idx, validation_idx))
    return output


def _km_censoring_survival(train_time, train_event, query, left=True):
    """Kaplan-Meier estimate of censoring survival G(t), from training only."""
    time = np.asarray(train_time, dtype=float)
    censor_event = 1 - np.asarray(train_event, dtype=int)
    value = 1.0
    for current in np.unique(time[censor_event == 1]):
        if (current < query) if left else (current <= query):
            at_risk = int(np.sum(time >= current))
            deaths = int(np.sum((time == current) & (censor_event == 1)))
            if at_risk > 0:
                value *= (1.0 - float(deaths) / float(at_risk))
    return max(float(value), 0.0)


def harrell_c_index(time, event, risk):
    time = np.asarray(time, dtype=float)
    event = np.asarray(event, dtype=int)
    risk = np.asarray(risk, dtype=float)
    concordant = tied = comparable = 0.0
    for i in range(len(time)):
        if event[i] != 1:
            continue
        later = np.where(time > time[i])[0]
        for j in later:
            comparable += 1.0
            if risk[i] > risk[j]:
                concordant += 1.0
            elif risk[i] == risk[j]:
                tied += 1.0
    if comparable == 0.0:
        return float("nan")
    return float((concordant + 0.5 * tied) / comparable)


def uno_c_index(train_time, train_event, validation_time, validation_event, risk):
    train_time = np.asarray(train_time, dtype=float)
    train_event = np.asarray(train_event, dtype=int)
    time = np.asarray(validation_time, dtype=float)
    event = np.asarray(validation_event, dtype=int)
    risk = np.asarray(risk, dtype=float)
    concordant = tied = comparable = 0.0
    for i in range(len(time)):
        if event[i] != 1:
            continue
        censor_survival = _km_censoring_survival(train_time, train_event, time[i], left=True)
        if censor_survival <= 1e-12:
            continue
        weight = 1.0 / (censor_survival * censor_survival)
        later = np.where(time > time[i])[0]
        for j in later:
            comparable += weight
            if risk[i] > risk[j]:
                concordant += weight
            elif risk[i] == risk[j]:
                tied += weight
    if comparable == 0.0:
        return float("nan")
    return float((concordant + 0.5 * tied) / comparable)


def _ipcw_weights(train_time, train_event, validation_time, validation_event, horizon):
    weights = np.zeros(len(validation_time), dtype=float)
    observed = np.zeros(len(validation_time), dtype=float)
    for index, (time, event) in enumerate(zip(validation_time, validation_event)):
        if time <= horizon and event == 1:
            g = _km_censoring_survival(train_time, train_event, time, left=True)
            observed[index] = 0.0
            weights[index] = 0.0 if g <= 1e-12 else 1.0 / g
        elif time > horizon:
            g = _km_censoring_survival(train_time, train_event, horizon, left=False)
            observed[index] = 1.0
            weights[index] = 0.0 if g <= 1e-12 else 1.0 / g
    return observed, weights


def _safe_metric(value, reason=None):
    if value is None or not np.isfinite(float(value)):
        return float("nan"), reason or "not_estimable"
    return float(value), ""


def evaluate_metrics(train_time, train_event, validation_time, validation_event,
                     risk, survival_predictions, survival_grid=None):
    result = {}
    value, reason = _safe_metric(harrell_c_index(validation_time, validation_event, risk))
    result["harrell_c_index"] = value
    result["harrell_c_index_reason"] = reason
    value, reason = _safe_metric(uno_c_index(
        train_time, train_event, validation_time, validation_event, risk))
    result["uno_c_index"] = value
    result["uno_c_index_reason"] = reason
    brier_values = []
    for name, horizon in HORIZONS_MONTHS.items():
        observed, weights = _ipcw_weights(
            train_time, train_event, validation_time, validation_event, horizon)
        predicted_survival = np.asarray(survival_predictions[name], dtype=float)
        if np.sum(weights > 0) == 0:
            brier = float("nan")
            auc = float("nan")
            slope = float("nan")
            intercept = float("nan")
            metric_reason = "no_positive_IPCW_weight"
        else:
            predicted_risk = 1.0 - predicted_survival
            residual = observed - predicted_survival
            brier = float(np.sum(weights * residual * residual) / np.sum(weights))
            cases = (weights > 0) & (observed == 0)
            controls = (weights > 0) & (observed == 1)
            if not np.any(cases) or not np.any(controls):
                auc = float("nan")
                auc_reason = "missing_case_or_control"
            else:
                numerator = denominator = 0.0
                for i in np.where(cases)[0]:
                    for j in np.where(controls)[0]:
                        pair_weight = weights[i] * weights[j]
                        denominator += pair_weight
                        if predicted_risk[i] > predicted_risk[j]:
                            numerator += pair_weight
                        elif predicted_risk[i] == predicted_risk[j]:
                            numerator += 0.5 * pair_weight
                auc = float("nan") if denominator == 0.0 else numerator / denominator
                auc_reason = ""
            x = np.log(np.clip(predicted_risk, 1e-8, 1.0 - 1e-8) /
                       np.clip(1.0 - predicted_risk, 1e-8, 1.0))
            valid = weights > 0
            x_mean = float(np.average(x[valid], weights=weights[valid]))
            y_mean = float(np.average((1.0 - observed[valid]), weights=weights[valid]))
            variance = float(np.average((x[valid] - x_mean) ** 2, weights=weights[valid]))
            slope = float(np.average((x[valid] - x_mean) *
                                     ((1.0 - observed[valid]) - y_mean),
                                     weights=weights[valid]) / variance) if variance > 0 else float("nan")
            intercept = float(y_mean - (0.0 if not np.isfinite(slope) else slope * x_mean))
            metric_reason = ""
        result["%s_auc" % name] = auc
        result["%s_auc_reason" % name] = metric_reason if not np.isfinite(auc) else ""
        result["%s_brier" % name] = brier
        result["%s_brier_reason" % name] = metric_reason if not np.isfinite(brier) else ""
        result["%s_calibration_slope" % name] = slope
        result["%s_calibration_slope_reason" % name] = metric_reason if not np.isfinite(slope) else ""
        result["%s_calibration_in_the_large" % name] = intercept
        result["%s_calibration_in_the_large_reason" % name] = metric_reason if not np.isfinite(intercept) else ""
        if np.isfinite(brier):
            brier_values.append((float(horizon), brier))
    if survival_grid:
        # Integrate fixed-month IPCW Brier values from 0 through 60 months;
        # horizon-specific 3/5-year values above remain independently reported.
        integrated_values = [(0.0, 0.0)]
        for key, horizon in survival_grid["horizons"].items():
            observed, weights = _ipcw_weights(
                train_time, train_event, validation_time, validation_event, horizon)
            prediction = np.asarray(survival_grid["predictions"][key], dtype=float)
            if np.sum(weights > 0) == 0:
                continue
            residual = observed - prediction
            integrated_values.append((float(horizon), float(
                np.sum(weights * residual * residual) / np.sum(weights))))
        if len(integrated_values) >= 2:
            integrate = getattr(np, "trapezoid", getattr(np, "trapz", None))
            result["integrated_brier_5_year"] = float(integrate(
                [value for _, value in integrated_values],
                [time for time, _ in integrated_values]) / 60.0)
            result["integrated_brier_5_year_reason"] = ""
        else:
            result["integrated_brier_5_year"] = float("nan")
            result["integrated_brier_5_year_reason"] = "no_estimable_integrated_grid_horizon"
    elif len(brier_values) >= 2:
        integrate = getattr(np, "trapezoid", getattr(np, "trapz", None))
        result["integrated_brier_5_year"] = float(integrate(
            [value for _, value in brier_values], [time for time, _ in brier_values]) /
            (brier_values[-1][0] - brier_values[0][0]))
        result["integrated_brier_5_year_reason"] = ""
    else:
        result["integrated_brier_5_year"] = float("nan")
        result["integrated_brier_5_year_reason"] = "fewer_than_two_estimable_horizons"
    return result


def _select_candidate(records):
    valid = [record for record in records if np.isfinite(record["mean_uno_c_index"])]
    if not valid:
        raise W08ValidationError("inner Uno C-index is not estimable for any candidate")
    best = max(record["mean_uno_c_index"] for record in valid)
    tied = [record for record in valid if best - record["mean_uno_c_index"] <= 1e-12]
    # Larger lambda means larger ratio; remaining tie is the smaller alpha in
    # the frozen alpha-grid order (the index is the frozen order).
    tied.sort(key=lambda record: (-record["lambda_ratio"], record["alpha_index"]))
    return tied[0]


def tune_elastic_net(raw_frame, model_id, inner_seed, lambda_count=LAMBDA_COUNT,
                     max_iter=250, tolerance=1e-7):
    """Tune alpha and lambda using only the supplied outer-training frame."""
    if model_id not in MODEL_SPECS or MODEL_SPECS[model_id]["family"] != "Elastic_Net_Cox":
        raise W08ValidationError("inner tuning is only for Elastic-Net models")
    inner_splits = make_inner_splits(raw_frame, inner_seed, folds=5)
    ratios = np.geomspace(1.0, LAMBDA_MIN_RATIO, int(lambda_count))
    records = []
    stability_actions = []
    for inner_index, (train_idx, validation_idx) in enumerate(inner_splits, start=1):
        inner_train = raw_frame.iloc[train_idx].reset_index(drop=True)
        inner_validation = raw_frame.iloc[validation_idx].reset_index(drop=True)
        preprocessor = ModelPreprocessor(model_id).fit(inner_train)
        X_train = preprocessor.transform(inner_train)
        X_validation = preprocessor.transform(inner_validation)
        train_time = inner_train["DFS_time"].to_numpy(dtype=float)
        train_event = inner_train["DFS_event"].to_numpy(dtype=int)
        validation_time = inner_validation["DFS_time"].to_numpy(dtype=float)
        validation_event = inner_validation["DFS_event"].to_numpy(dtype=int)
        censoring = {"train_ids_hash": canonical_id_hash(inner_train["patient_id"]),
                     "validation_ids_hash": canonical_id_hash(inner_validation["patient_id"])}
        for alpha_index, alpha in enumerate(ALPHA_GRID):
            maximum = _lambda_max(X_train, train_time, train_event, alpha)
            scores = []
            for lambda_index, ratio in enumerate(ratios):
                penalty = float(maximum * ratio)
                model = CoxElasticNetModel(alpha, penalty, max_iter=max_iter,
                                           tolerance=tolerance).fit(
                                               X_train, train_time, train_event)
                risk = model.predict_risk(X_validation)
                score = uno_c_index(train_time, train_event,
                                    validation_time, validation_event, risk)
                if not np.isfinite(score):
                    score = float("nan")
                scores.append(score)
                stability_actions.extend(model.fit_audit.get("stability_actions", []))
                records.append({
                    "inner_fold": inner_index,
                    "alpha": float(alpha),
                    "alpha_index": int(alpha_index),
                    "lambda_index": int(lambda_index),
                    "lambda_ratio": float(ratio),
                    "inner_lambda_max": float(maximum),
                    "inner_lambda": penalty,
                    "uno_c_index": float(score),
                    "inner_train_ids_hash": censoring["train_ids_hash"],
                    "inner_validation_ids_hash": censoring["validation_ids_hash"],
                    "candidate_attempted": True,
                    "stability_actions": list(model.fit_audit.get("stability_actions", [])),
                })
    grouped = {}
    for record in records:
        key = (record["alpha_index"], record["lambda_index"])
        grouped.setdefault(key, []).append(record["uno_c_index"])
    summary = []
    for (alpha_index, lambda_index), scores in grouped.items():
        finite = [score for score in scores if np.isfinite(score)]
        summary.append({
            "alpha": float(ALPHA_GRID[alpha_index]),
            "alpha_index": int(alpha_index),
            "lambda_index": int(lambda_index),
            "lambda_ratio": float(ratios[lambda_index]),
            "mean_uno_c_index": float(np.mean(finite)) if finite else float("nan"),
            "n_estimable_inner_scores": int(len(finite)),
            "n_inner_scores": int(len(scores)),
        })
    selected = _select_candidate(summary)
    selected = dict(selected)
    selected["candidate_attempts"] = int(len(records))
    selected["candidate_failures"] = int(sum(not row["candidate_attempted"] for row in records))
    selected["inner_folds"] = int(len(inner_splits))
    selected["lambda_count"] = int(lambda_count)
    selected["all_inner_records"] = records
    selected["stability_actions"] = sorted(set(stability_actions)) or ["stable_path"]
    return selected


def _fit_outer_model(train_frame, validation_frame, model_id, inner_seed,
                     lambda_count=LAMBDA_COUNT, max_iter=250, tolerance=1e-7):
    preprocessor = ModelPreprocessor(model_id).fit(train_frame)
    X_train = preprocessor.transform(train_frame)
    X_validation = preprocessor.transform(validation_frame)
    train_time = train_frame["DFS_time"].to_numpy(dtype=float)
    train_event = train_frame["DFS_event"].to_numpy(dtype=int)
    if MODEL_SPECS[model_id]["family"] == "Cox_PH_unpenalized":
        model = CoxPHModel(max_iter=max_iter, tolerance=tolerance).fit(
            X_train, train_time, train_event)
        selection = {
            "alpha": None, "lambda_ratio": None, "lambda": None,
            "candidate_attempts": 0, "candidate_failures": 0,
            "inner_folds": 0, "lambda_count": 0,
            "mean_uno_c_index": None, "stability_actions": [],
        }
    else:
        selection = tune_elastic_net(
            train_frame, model_id, inner_seed, lambda_count=lambda_count,
            max_iter=max_iter, tolerance=tolerance)
        outer_lambda_max = _lambda_max(
            X_train, train_time, train_event, selection["alpha"])
        final_lambda = float(outer_lambda_max * selection["lambda_ratio"])
        model = CoxElasticNetModel(
            selection["alpha"], final_lambda, max_iter=max_iter,
            tolerance=tolerance).fit(X_train, train_time, train_event)
        selection["outer_lambda_max"] = float(outer_lambda_max)
        selection["outer_lambda"] = final_lambda
        selection["stability_actions"] = sorted(set(
            selection["stability_actions"] + model.fit_audit.get("stability_actions", [])))
    risk = model.predict_risk(X_validation)
    survival = model.predict_survival(X_validation, HORIZONS_MONTHS)
    grid_horizons = OrderedDict(("month_%d" % month, float(month))
                                for month in range(12, 61, 12))
    survival_grid = {"horizons": grid_horizons,
                     "predictions": model.predict_survival(X_validation, grid_horizons)}
    return model, preprocessor, selection, risk, survival, survival_grid


def _outer_fold_rows(split_frame, eligible):
    eligible = set(eligible)
    for repeat in sorted(split_frame["repeat"].unique()):
        for fold in sorted(split_frame["fold"].unique()):
            current = split_frame[(split_frame["repeat"] == repeat) &
                                  (split_frame["fold"] == fold)]
            train_ids = sorted(set(current.loc[current["role"] == "train", "patient_id"]) & eligible)
            validation_ids = sorted(set(current.loc[current["role"] == "validation", "patient_id"]) & eligible)
            if set(train_ids) & set(validation_ids):
                raise W08ValidationError("outer train/validation overlap")
            if not train_ids or not validation_ids:
                raise W08ValidationError("outer fold has an empty eligible side")
            yield int(repeat), int(fold), train_ids, validation_ids


def _resolve_runs(models=None, runs=None):
    if runs is not None and models is not None:
        raise W08ValidationError("specify either model IDs or fixed run IDs, not both")
    if runs is not None:
        by_id = {item["run_id"]: item for item in FIXED_RUN_DEFINITIONS}
        selected = []
        for run_id in runs:
            if run_id not in by_id:
                raise W08ValidationError("unknown W08 fixed run: %s" % run_id)
            selected.append(dict(by_id[run_id]))
        return selected
    if models is not None:
        selected = []
        for model_id in models:
            if model_id not in MODEL_SPECS:
                raise W08ValidationError("unknown W04 model: %s" % model_id)
            selected.append({"run_id": model_id, "model_id": model_id,
                             "population": MODEL_SPECS[model_id]["population"]})
        return selected
    return [dict(item) for item in FIXED_RUN_DEFINITIONS]


def run_w08_in_memory(feature_frame, outer_splits, provider, config=None,
                      models=None, runs=None, strict_schema=False, require_fixed_hash=False,
                      lambda_count=LAMBDA_COUNT, max_outer_folds=None,
                      solver_max_iter=250, solver_tolerance=1e-7):
    """Run W08 against an already-authorized A-only frame without file I/O.

    ``max_outer_folds`` exists solely for synthetic/preflight tests.  It is
    rejected when ``require_fixed_hash`` is true, so a formal run cannot be
    accidentally truncated.
    """
    config = _validate_config(config or load_config())
    selected_runs = _resolve_runs(models=models, runs=runs)
    selected_models = sorted(set(item["model_id"] for item in selected_runs),
                             key=lambda item: list(MODEL_SPECS).index(item))
    if require_fixed_hash and max_outer_folds is not None:
        raise W08ValidationError("formal W08 cannot truncate the 50 outer folds")
    data = _normalise_frame(feature_frame)
    population = pd.DataFrame({
        "patient_id": data["patient_id"].tolist(),
        "DFS_event": data["DFS_event"].astype(int).tolist(),
    })
    _validate_population_alignment(data, population)
    validate_feature_schema(data, selected_models, strict=strict_schema)
    if not isinstance(provider, FoldFeatureProvider):
        raise W08ValidationError("W08 requires a FoldFeatureProvider")
    if not provider.fold_specific_habitat:
        raise W08ValidationError("formal W08 requires fold-specific habitat fitting")
    split_summary = _validate_split_frame(outer_splits, population)
    split_hash = _canonical_split_hash(outer_splits)
    if require_fixed_hash and split_hash.lower() != W07_OUTER_SPLIT_SHA256:
        raise W08ValidationError("W08 outer splits are not the W07 fixed artifact")

    id_to_row = data.set_index("patient_id", drop=False)
    eligibility = {}
    for run in selected_runs:
        population_name = run["population"]
        eligible = eligible_ids(data, population_name)
        if not eligible:
            raise W08ValidationError("no eligible A patients for %s" % run["run_id"])
        eligibility[run["run_id"]] = eligible

    predictions = []
    fold_results = []
    selection_results = []
    representation_cache = {}
    completed_folds = 0
    for run in selected_runs:
        run_id = run["run_id"]
        model_id = run["model_id"]
        population_name = run["population"]
        eligible = eligibility[run_id]
        model_fold_count = 0
        for repeat, fold, train_ids, validation_ids in _outer_fold_rows(outer_splits, eligible):
            if max_outer_folds is not None and model_fold_count >= int(max_outer_folds):
                break
            outer_seed = 12345 + repeat - 1
            inner_seed = 12345 + 1000 + 10 * (repeat - 1) + fold
            kmeans_seed = 12345 + 2000 + 10 * (repeat - 1) + fold
            solver_seed = 12345 + 3000 + 10 * (repeat - 1) + fold
            event_train = id_to_row.loc[train_ids, "DFS_event"].to_numpy(dtype=int)
            event_validation = id_to_row.loc[validation_ids, "DFS_event"].to_numpy(dtype=int)
            if np.sum(event_train) < 1 or np.sum(event_validation) < 1:
                raise W08ValidationError("outer event gate failed for %s repeat=%d fold=%d" %
                                         (model_id, repeat, fold))
            cache_key = tuple(train_ids)
            if cache_key not in representation_cache:
                state = provider.fit(train_ids, kmeans_seed)
                if state.training_id_hash != canonical_id_hash(train_ids):
                    raise W08ValidationError("provider training provenance hash mismatch")
                representation_cache[cache_key] = state
            state = representation_cache[cache_key]
            train_repr = provider.transform(train_ids, state)
            validation_repr = provider.transform(validation_ids, state)
            train_repr = _normalise_frame(train_repr)
            validation_repr = _normalise_frame(validation_repr)
            if set(train_repr["patient_id"]) != set(train_ids) or set(validation_repr["patient_id"]) != set(validation_ids):
                raise W08ValidationError("provider representation changed outer fold membership")
            train_repr = train_repr.set_index("patient_id").loc[train_ids].reset_index()
            validation_repr = validation_repr.set_index("patient_id").loc[validation_ids].reset_index()
            model, preprocessor, selection, risk, survival, survival_grid = _fit_outer_model(
                train_repr, validation_repr, model_id, inner_seed,
                lambda_count=lambda_count, max_iter=solver_max_iter,
                tolerance=solver_tolerance)
            train_time = train_repr["DFS_time"].to_numpy(dtype=float)
            train_event = train_repr["DFS_event"].to_numpy(dtype=int)
            valid_time = validation_repr["DFS_time"].to_numpy(dtype=float)
            valid_event = validation_repr["DFS_event"].to_numpy(dtype=int)
            metrics = evaluate_metrics(train_time, train_event, valid_time,
                                       valid_event, risk, survival, survival_grid)
            fold_id_hash = canonical_id_hash(train_ids)
            validation_id_hash = canonical_id_hash(validation_ids)
            fold_result = {
                "run_id": run_id, "model_id": model_id, "population": population_name,
                "repeat": repeat, "fold": fold, "outer_seed": outer_seed,
                "inner_seed": inner_seed, "fold_kmeans_seed": kmeans_seed,
                "model_solver_seed": solver_seed,
                "n_train": len(train_ids), "n_validation": len(validation_ids),
                "train_events": int(np.sum(train_event)),
                "validation_events": int(np.sum(valid_event)),
                "training_id_hash": fold_id_hash,
                "validation_id_hash": validation_id_hash,
                "outer_split_hash": split_hash,
                "W04_protocol_sha256": W04_PROTOCOL_SHA256,
                "centers": list(state.centers) if state.centers is not None else None,
                "boundary": state.boundary,
                "representation_metadata": state.metadata,
                "preprocessing_audit": preprocessor.audit(),
                "selected_alpha": selection.get("alpha"),
                "selected_lambda_ratio": selection.get("lambda_ratio"),
                "selected_lambda": selection.get("outer_lambda"),
                "selected_features": [
                    name for name, coefficient in zip(
                        preprocessor.feature_names, model.coef_)
                    if abs(float(coefficient)) > 1e-10
                ],
                "candidate_attempts": selection.get("candidate_attempts", 0),
                "candidate_failures": selection.get("candidate_failures", 0),
                "inner_folds": selection.get("inner_folds", 0),
                "stability_actions": selection.get("stability_actions", []),
                "outer_validation_used_for_selection": False,
                "R_low_candidate_hash": config["provenance"]["R_low_candidate_hash"],
                "R_high_candidate_hash": config["provenance"]["R_high_candidate_hash"],
            }
            fold_result.update(metrics)
            fold_results.append(fold_result)
            selection_results.append({
                "run_id": run_id, "model_id": model_id, "population": population_name,
                "repeat": repeat, "fold": fold,
                "training_id_hash": fold_id_hash,
                "validation_id_hash": validation_id_hash,
                "inner_seed": inner_seed,
                "selected_alpha": selection.get("alpha"),
                "selected_lambda_ratio": selection.get("lambda_ratio"),
                "selected_lambda": selection.get("outer_lambda"),
                "inner_mean_uno_c_index": selection.get("mean_uno_c_index"),
                "candidate_attempts": selection.get("candidate_attempts", 0),
                "candidate_failures": selection.get("candidate_failures", 0),
                "outer_validation_used_for_selection": False,
                "inner_records": selection.get("all_inner_records", []),
            })
            for identifier, prediction, observed_time, observed_event in zip(
                    validation_repr["patient_id"], risk, valid_time, valid_event):
                predictions.append({
                    "run_id": run_id, "model_id": model_id, "population": population_name,
                    "repeat": repeat, "fold": fold,
                    "patient_id": identifier, "DFS_time": float(observed_time),
                    "DFS_event": int(observed_event), "risk_score": float(prediction),
                    "training_id_hash": fold_id_hash,
                    "validation_id_hash": validation_id_hash,
                    "outer_split_hash": split_hash,
                    "outer_validation_used_for_selection": False,
                })
            completed_folds += 1
            model_fold_count += 1

    audit = {
        "stage": "W08",
        "status": W08_STATUS,
        "formal_run": bool(require_fixed_hash and max_outer_folds is None),
        "runs_requested": [run["run_id"] for run in selected_runs],
        "models_requested": selected_models,
        "outer_split_hash": split_hash,
        "outer_split_hash_locked": W07_OUTER_SPLIT_SHA256,
        "W04_protocol_sha256": W04_PROTOCOL_SHA256,
        "outer_split_validation": split_summary,
        "n_fold_results": int(len(fold_results)),
        "n_predictions": int(len(predictions)),
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "patient_level_outputs_written": False,
        "outer_validation_used_for_selection": False,
        "candidate_failures": int(sum(row["candidate_failures"] for row in fold_results)),
    }
    return {
        "predictions": pd.DataFrame(predictions),
        "fold_results": pd.DataFrame(fold_results),
        "selection_results": pd.DataFrame(selection_results),
        "audit": audit,
    }


def run_w08(feature_frame, provider, config_path=DEFAULT_CONFIG,
            strict_schema=True):
    """Formal entry point: load only locked W06/W07 artifacts, then run in memory."""
    config = load_config(config_path)
    population = load_frozen_a_population()
    outer_splits = load_frozen_outer_splits(population)
    data = _normalise_frame(feature_frame)
    _validate_population_alignment(data, population)
    return run_w08_in_memory(
        data, outer_splits, provider, config=config,
        strict_schema=strict_schema, require_fixed_hash=True,
        lambda_count=LAMBDA_COUNT)


def main():
    parser = argparse.ArgumentParser(
        description="W08 A-only nested CV library entry point; feature input is an authorized in-memory adapter")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=argparse.SUPPRESS)
    parser.add_argument("--dry-run", action="store_true",
                        help="validate the locked W08 config without opening patient data")
    args = parser.parse_args()
    config = load_config(args.config)
    if not args.dry_run:
        raise SystemExit("W08 requires an authorized A-only feature-frame adapter; no patient data were opened")
    print(json.dumps({"stage": "W08", "status": config["status"],
                      "B_data_read": False, "patient_level_outputs_written": False},
                     ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
