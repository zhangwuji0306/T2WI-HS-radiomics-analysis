"""Local W08 A-only execution adapter.

This module is the controlled local bridge between the frozen W08 library and
the already-authorized A technical artifacts.  It never calls a B reader and
does not create the second-stage model-freeze lock.

The provider keeps the W08 library's fold boundary immutable.  SLIC labels are
computed once per A case from the frozen preprocessing configuration and are
cached locally; each outer-training fold fits its own patient-balanced K=2
centres, then reassigns those labels and extracts fold-specific global and
habitat radiomics features for both the training and held-out patients.
"""
from __future__ import absolute_import

import argparse
import hashlib
import json
import operator
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy import ndimage
from sklearn.cluster import KMeans

SCRIPT_ROOT = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_ROOT not in sys.path:
    sys.path.insert(0, SCRIPT_ROOT)
FEATURE_SCRIPT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_ROOT)), "feature_extract", "scripts")
HABITAT_SCRIPT_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(SCRIPT_ROOT)), "habitat_analysis", "scripts")
for _script_root in (FEATURE_SCRIPT_ROOT, HABITAT_SCRIPT_ROOT):
    if _script_root not in sys.path:
        sys.path.insert(0, _script_root)

import w02_habitat_radiomics as w02  # noqa: E402
import w07_outer_splits as w07  # noqa: E402
import w08_nested_cv as w08  # noqa: E402
from data_split_guard import read_technical_A  # noqa: E402
import technical_dry_run_A as technical  # noqa: E402


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = os.path.dirname(ROOT)
OUTPUT_ROOT = os.path.join(ROOT, "output", "w08_formal_A")
WORK_ROOT = os.path.join(OUTPUT_ROOT, "work")
SLIC_CACHE_ROOT = os.path.join(WORK_ROOT, "slic_cache")

MINIMUM_ROI_SIZE = 10
# PyRadiomics 3.0.1 treats its minimumROISize as a strict lower bound
# (``roiSize <= minimumROISize``).  W08 keeps the public P3B threshold at 10;
# this backend-only value disables the duplicated, off-by-one check after the
# provider has already classified the mask using the frozen contract.
_PYRADIOMICS_COMPATIBILITY_MINIMUM_ROI_SIZE = None
RADIOMICS_STATE_STRUCTURALLY_ABSENT = "structurally_absent"
RADIOMICS_STATE_TECHNICALLY_UNEXTRACTABLE_SMALL_ROI = \
    "technically_unextractable_small_ROI"
RADIOMICS_STATE_EXTRACTABLE = "radiomics_extractable"
RADIOMICS_SUPPORT_COLUMNS = (
    "R_low_voxel_count", "R_high_voxel_count", "R_low_state", "R_high_state",
    "R_low_structurally_defined", "R_high_structurally_defined",
    "R_low_technically_extractable", "R_high_technically_extractable",
)

W06_POPULATION = os.path.join(
    ROOT, "output", "A_modeling", "A_modeling_population.csv")
W03_LOW = os.path.join(
    ROOT, "output", "w03_habitat_radiomics_A", "R1_R_low_features.csv")
W03_HIGH = os.path.join(
    ROOT, "output", "w03_habitat_radiomics_A", "R1_R_high_features.csv")
SV_TABLE = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "output",
    "local_global_diagnostic_A_post_slic_fix", "supervoxel_mean_A.csv")
HABITAT_CONFIG = os.path.join(
    PROJECT_ROOT, "habitat_analysis", "configs",
    "main_cross_case_kmeans_k2_4mm.json")
CLINICAL_A = os.path.join(
    ROOT, "output", "modeling_v2", "dataset_primary_raw_A.csv")
FEATURE_ROOT = os.path.join(
    PROJECT_ROOT, "feature_extract", "output", "features_v2", "muscle_f0.25")
W_BATCHES = (
    ("original", "features_original.csv",
     ("影像号", "读者", "split", "normalization", "f", "binWidth")),
    ("wavelet", "features_wavelet.csv",
     ("影像号", "读者", "split", "normalization", "f")),
    ("log", "features_log.csv",
     ("影像号", "读者", "split", "normalization", "f")),
)


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_json(path, payload):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, path)


def _atomic_csv(frame, path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    temporary = path + ".tmp"
    frame.to_csv(temporary, index=False, encoding="utf-8-sig")
    os.replace(temporary, path)


def _normalise_ids(values):
    output = {str(value).strip() for value in values}
    if "" in output:
        raise RuntimeError("A-only allow-list contains a blank identifier")
    return output


def _six_neighbor_interface(habitat, roi, spacing_xyz):
    """Return 3-D six-neighbour habitat interface area in mm2."""
    areas = [spacing_xyz[0] * spacing_xyz[1],
             spacing_xyz[0] * spacing_xyz[2],
             spacing_xyz[1] * spacing_xyz[2]]
    total = 0.0
    for axis, area in enumerate(areas):
        left = np.take(habitat, indices=range(habitat.shape[axis] - 1), axis=axis)
        right = np.take(habitat, indices=range(1, habitat.shape[axis]), axis=axis)
        left_roi = np.take(roi, indices=range(roi.shape[axis] - 1), axis=axis)
        right_roi = np.take(roi, indices=range(1, roi.shape[axis]), axis=axis)
        total += float(((left >= 0) & (right >= 0) & left_roi & right_roi &
                        (left != right)).sum()) * area
    return total


def _radiomics_support_state(voxel_count):
    """Classify one fold-specific habitat mask by its voxel support."""
    if isinstance(voxel_count, bool):
        raise RuntimeError("radiomics mask voxel count must be an integer")
    try:
        voxel_count = operator.index(voxel_count)
    except TypeError:
        raise RuntimeError("radiomics mask voxel count must be an integer")
    if voxel_count < 0:
        raise RuntimeError("radiomics mask voxel count cannot be negative")
    if voxel_count == 0:
        return RADIOMICS_STATE_STRUCTURALLY_ABSENT
    if voxel_count < MINIMUM_ROI_SIZE:
        return RADIOMICS_STATE_TECHNICALLY_UNEXTRACTABLE_SMALL_ROI
    return RADIOMICS_STATE_EXTRACTABLE


def _backend_compatibility_settings(config):
    """Build backend settings without changing the frozen public threshold."""
    settings = w02.extractor_settings(config)
    if type(MINIMUM_ROI_SIZE) is not int or MINIMUM_ROI_SIZE != 10:
        raise w08.W08ValidationError(
            "W08 public minimumROISize is not the frozen value 10")
    setting = settings.get("setting")
    if not isinstance(setting, dict) or \
            setting.get("minimumROISize") != MINIMUM_ROI_SIZE:
        raise w08.W08ValidationError(
            "W08 public/config minimumROISize is inconsistent")
    backend = dict(settings)
    backend["setting"] = dict(setting)
    backend["setting"]["minimumROISize"] = \
        _PYRADIOMICS_COMPATIBILITY_MINIMUM_ROI_SIZE
    return backend


def _build_backend_compatible_extractor(config=None):
    """Create the locked PyRadiomics extractor with the boundary shim only."""
    if config is None:
        config = w02.load_config()
    settings = _backend_compatibility_settings(config)
    return w02.featureextractor.RadiomicsFeatureExtractor(settings)


def _mask_label_voxel_count(mask):
    """Count label-1 voxels without changing the SimpleITK mask."""
    mask_array = w02.sitk.GetArrayFromImage(mask)
    labels = np.unique(mask_array)
    if not np.isin(labels, [0, 1]).all():
        raise w08.W08ValidationError(
            "radiomics compatibility mask must be binary with label 1")
    return int(np.count_nonzero(mask_array == 1))


def _read_header(path):
    return list(pd.read_csv(path, encoding="utf-8-sig", nrows=0).columns)


def _read_a_csv(path, allowed_ids, usecols=None):
    """Read an A-allowed technical CSV before any pandas frame is assembled."""
    frame = read_technical_A(
        path, allowed_ids=allowed_ids, dtype={"影像号": str}, usecols=usecols)
    if "影像号" not in frame.columns:
        raise RuntimeError("A technical source lacks 影像号: %s" % os.path.basename(path))
    frame["影像号"] = frame["影像号"].astype(str).str.strip()
    if "split" in frame.columns:
        split = frame["split"].astype(str).str.strip()
        if not split.eq("A").all():
            raise RuntimeError("non-A row admitted from %s" % os.path.basename(path))
    return frame


def _read_a_w_batch(batch_name, filename, metadata_columns, allowed_ids):
    path = os.path.join(FEATURE_ROOT, filename)
    header = _read_header(path)
    feature_columns = [column for column in header
                       if column not in set(metadata_columns)]
    if not feature_columns:
        raise RuntimeError("W batch has no feature columns: %s" % batch_name)
    usecols = list(metadata_columns) + feature_columns
    table = _read_a_csv(path, allowed_ids, usecols=usecols)
    table = table[table["读者"].astype(str).str.strip().eq("R1")].copy()
    if set(table["影像号"]) != set(allowed_ids):
        raise RuntimeError("W batch does not cover the W06 A population: %s" %
                           batch_name)
    if table["影像号"].duplicated().any():
        raise RuntimeError("W batch has duplicated A R1 IDs: %s" % batch_name)
    table = table[["影像号"] + feature_columns].set_index("影像号")
    table.columns = ["W__" + str(column) for column in table.columns]
    for column in table.columns:
        table[column] = pd.to_numeric(table[column], errors="coerce")
    return table


def load_a_feature_frame(population):
    """Assemble a W08 frame from A-only reads and explicit availability flags."""
    allowed_ids = _normalise_ids(population["patient_id"])
    clinical_usecols = ["影像号", "split"] + list(w08.CLINICAL_COLUMNS)
    clinical = _read_a_csv(CLINICAL_A, allowed_ids, usecols=clinical_usecols)
    clinical = clinical[clinical["影像号"].isin(allowed_ids)].copy()
    clinical = clinical.set_index("影像号")
    if set(clinical.index) != allowed_ids:
        raise RuntimeError("A clinical feature frame does not cover W06 A")

    w_tables = [_read_a_w_batch(name, filename, metadata, allowed_ids)
                for name, filename, metadata in W_BATCHES]
    whole_tumour = pd.concat(w_tables, axis=1, join="inner")
    if len(whole_tumour.columns) != 1130:
        raise RuntimeError("W block must contain 1130 frozen features, got %d" %
                           len(whole_tumour.columns))
    if set(whole_tumour.index) != allowed_ids:
        raise RuntimeError("W block does not cover W06 A")

    low = _read_a_csv(
        W03_LOW, allowed_ids, usecols=["影像号", "habitat_present", "status"])
    high = _read_a_csv(
        W03_HIGH, allowed_ids, usecols=["影像号", "habitat_present", "status"])
    low = low.set_index("影像号")
    high = high.set_index("影像号")
    if set(low.index) != allowed_ids or set(high.index) != allowed_ids:
        raise RuntimeError("W03 A availability does not cover W06 A")

    data = population.copy()
    data["patient_id"] = data["patient_id"].astype(str).str.strip()
    data = data.set_index("patient_id")
    for column in w08.CLINICAL_COLUMNS:
        data[column] = clinical[column]
    data = data.join(whole_tumour, how="left")
    data["split"] = "A"
    data["technical_cohort"] = "A393"

    availability = {}
    for block, table in (("R_low", low), ("R_high", high)):
        present = pd.to_numeric(table["habitat_present"], errors="coerce")
        status = table["status"].astype(str).str.strip()
        if present.isna().any() or not present.isin([0, 1]).all():
            raise RuntimeError("invalid W03 %s structural availability" % block)
        availability[block + "_structurally_defined"] = present.astype(int)
        availability[block + "_technically_available"] = status.eq("extractable").astype(int)

    finite_w = np.isfinite(data[whole_tumour.columns].to_numpy(dtype=float)).all(axis=1)
    availability["W_structurally_defined"] = 1
    availability["W_technically_available"] = finite_w.astype(int)
    availability["W_available"] = finite_w.astype(int)

    # These columns are intentionally placeholders in the initial frame.
    # The formal provider replaces them from fold-specific masks before any
    # preprocessing or model fitting occurs.
    placeholders = {column: np.nan for column in w08.GLOBAL_COLUMNS}
    for block in ("R_low", "R_high"):
        for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
            placeholders[w08.RADIOMICS_PREFIXES[block] + feature] = np.nan
    data["split"] = "A"
    data["technical_cohort"] = "A393"
    extra = pd.concat([pd.DataFrame(availability, index=data.index),
                       pd.DataFrame(placeholders, index=data.index)], axis=1)
    data = pd.concat([data, extra], axis=1)
    return data.reset_index()


class AOnlyFoldFeatureProvider(w08.FoldFeatureProvider):
    """Fold-specific habitat/G/R provider backed only by the A technical data."""

    formal_capable = True
    fold_specific_habitat = True

    def __init__(self, frame, supervoxel_table, habitat_config=HABITAT_CONFIG,
                 cache_root=SLIC_CACHE_ROOT):
        self.frame = w08._normalise_frame(frame)
        self._by_id = self.frame.set_index("patient_id", drop=False)
        self._allowed_ids = set(self._by_id.index)
        self._sv = self._normalise_supervoxel_table(supervoxel_table)
        self._habitat_config = w07._read_json(habitat_config)
        self._cache_root = cache_root
        os.makedirs(self._cache_root, exist_ok=True)
        self._case_cache = {}
        self._state_cache = {}
        self.fit_calls = []
        self.transform_calls = []
        self._extractor = _build_backend_compatible_extractor()

    @staticmethod
    def _normalise_supervoxel_table(table):
        required = {"影像号", "reader", "sv_label", "n_tumor_voxels", "Mean"}
        if not required.issubset(table.columns):
            raise RuntimeError("A supervoxel table lacks required columns")
        table = table.copy()
        table["影像号"] = table["影像号"].astype(str).str.strip()
        if not table["reader"].astype(str).str.strip().eq("R1").all():
            raise RuntimeError("A supervoxel table contains a non-R1 reader")
        table["sv_label"] = pd.to_numeric(table["sv_label"], errors="coerce")
        table["n_tumor_voxels"] = pd.to_numeric(
            table["n_tumor_voxels"], errors="coerce")
        table["Mean"] = pd.to_numeric(table["Mean"], errors="coerce")
        if table[["sv_label", "n_tumor_voxels", "Mean"]].isna().any().any():
            raise RuntimeError("A supervoxel table contains invalid values")
        if table["sv_label"].duplicated().any():
            # Duplicates are allowed across cases but not within one case.
            duplicate = table.duplicated(["影像号", "sv_label"]).any()
            if duplicate:
                raise RuntimeError("A supervoxel table has duplicate case labels")
        return table

    def _sv_for_id(self, identifier):
        group = self._sv[self._sv["影像号"].eq(str(identifier))]
        if group.empty:
            raise RuntimeError("missing A supervoxel representation for %s" % identifier)
        return group.sort_values("sv_label").reset_index(drop=True)

    def _cache_path(self, identifier):
        return os.path.join(self._cache_root, str(identifier) + ".npz")

    def _prepare_case(self, identifier):
        identifier = str(identifier).strip()
        if identifier in self._case_cache:
            return self._case_cache[identifier]
        cache_path = self._cache_path(identifier)
        image_path = os.path.join(technical.PREP, identifier, "R1_image.nrrd")
        mask_path = os.path.join(technical.PREP, identifier, "R1_mask.nrrd")
        if not (os.path.isfile(image_path) and os.path.isfile(mask_path)):
            raise RuntimeError("A preprocessed image/ROI is missing for %s" % identifier)

        image = w02.sitk.ReadImage(w02.apath(image_path))
        roi_image = w02.sitk.ReadImage(w02.apath(mask_path))
        errors, arr, roi = technical.geom(image, roi_image)
        if errors:
            raise RuntimeError("A case %s failed geometry validation: %s" %
                               (identifier, ";".join(errors)))
        if os.path.isfile(cache_path):
            with np.load(cache_path) as cached:
                labels = cached["labels"].astype(np.int32, copy=False)
                cached_roi = cached["roi"].astype(bool, copy=False)
            if labels.shape != roi.shape or not np.array_equal(cached_roi, roi):
                raise RuntimeError("SLIC cache mismatch for A case %s" % identifier)
        else:
            labels = technical.slic_labels(image, self._habitat_config, True)
            if labels.shape != roi.shape:
                raise RuntimeError("SLIC label shape mismatch for A case %s" % identifier)
            temporary = cache_path + ".tmp"
            with open(temporary, "wb") as handle:
                np.savez_compressed(handle, labels=labels,
                                    roi=roi.astype(np.uint8))
            os.replace(temporary, cache_path)

        sv = self._sv_for_id(identifier)
        observed_values, observed_counts, observed_by_label = technical.sv_stats(
            arr, labels, roi)
        expected_by_label = dict(zip(
            sv["sv_label"].astype(int), sv["Mean"].to_numpy(dtype=float)))
        expected_counts_by_label = dict(zip(
            sv["sv_label"].astype(int),
            sv["n_tumor_voxels"].to_numpy(dtype=int)))
        if set(observed_by_label) != set(expected_by_label):
            raise RuntimeError("SLIC/supervoxel mean mismatch for A case %s" % identifier)
        if (not all(abs(float(observed_by_label[label]) -
                        float(expected_by_label[label])) <= 5e-6
                    for label in expected_by_label) or
                any(int(observed_counts[index]) != int(expected_counts_by_label[label])
                    for index, label in enumerate(sorted(observed_by_label)))):
            raise RuntimeError("SLIC/supervoxel support mismatch for A case %s" % identifier)
        self._case_cache[identifier] = {
            "image_path": image_path,
            "mask_path": mask_path,
            "labels": labels,
            "roi": roi,
            "spacing_xyz": tuple(float(x) for x in image.GetSpacing()),
            "sv": sv,
        }
        return self._case_cache[identifier]

    def prepare_all_cases(self):
        for identifier in sorted(self._allowed_ids):
            self._prepare_case(identifier)

    def _feature_sources(self, training_hash):
        required = w08._required_fold_specific_columns(list(w08.MODEL_SPECS))
        return {
            column: {
                "source": "fold_fit_regenerated",
                "fit_training_id_hash": training_hash,
                "validation_ids_used_for_fit": False,
            }
            for column in required
        }

    def fit(self, training_ids, seed):
        ids = sorted(str(value).strip() for value in training_ids)
        if not ids or not set(ids).issubset(self._allowed_ids):
            raise w08.W08ValidationError("provider training IDs are not in the A frame")
        self.fit_calls.append(tuple(ids))
        flattened = []
        weights = []
        for identifier in ids:
            self._prepare_case(identifier)
            group = self._sv_for_id(identifier)
            values = group["Mean"].to_numpy(dtype=float)
            if values.size == 0 or not np.isfinite(values).all():
                raise w08.W08ValidationError(
                    "missing/nonfinite A supervoxel input for %s" % identifier)
            flattened.append(values)
            weights.append(np.full(values.size, 1.0 / float(values.size)))
        values = np.concatenate(flattened)
        sample_weights = np.concatenate(weights)
        if np.unique(values).size < 2:
            raise w08.W08ValidationError("fold-specific K=2 habitat fit needs two distinct values")
        estimator = KMeans(n_clusters=2, random_state=int(seed), n_init=10)
        estimator.fit(values.reshape(-1, 1), sample_weight=sample_weights)
        centres = tuple(sorted(float(value)
                               for value in estimator.cluster_centers_.reshape(-1)))
        boundary = (centres[0] + centres[1]) / 2.0
        training_hash = w08.canonical_id_hash(ids)
        state = w08.FoldState(
            training_hash, int(seed), centres, boundary,
            metadata={
                "fold_specific_habitat": True,
                "patient_weighting": "each patient total supervoxel weight=1",
                "supervoxel_count": int(values.size),
                "representation_source": "A_preprocessed_R1_SLIC_supervoxel_mean",
                "feature_generation": "fold-specific habitat masks; G and R regenerated",
                "feature_sources": self._feature_sources(training_hash),
                "validation_ids_used_for_fit": False,
            })
        return state

    @staticmethod
    def _habitat_from_boundary(case, boundary):
        labels = case["labels"]
        roi = case["roi"]
        sv = case["sv"]
        habitat = np.full(labels.shape, -1, dtype=np.int8)
        for label, mean in zip(sv["sv_label"].astype(int), sv["Mean"]):
            habitat[labels == int(label)] = int(float(mean) >= float(boundary))
        habitat[~roi] = -1
        return habitat

    def _radiomics_for_mask(self, image, mask, block, expected_voxel_count):
        actual_voxel_count = _mask_label_voxel_count(mask)
        if type(expected_voxel_count) is not int or \
                actual_voxel_count != expected_voxel_count:
            raise w08.W08ValidationError(
                "radiomics compatibility mask voxel count is inconsistent")
        if _radiomics_support_state(actual_voxel_count) != \
                RADIOMICS_STATE_EXTRACTABLE:
            raise w08.W08ValidationError(
                "radiomics compatibility backend received an ineligible mask")
        result = self._extractor.execute(image, mask)
        output = {}
        for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
            value = result.get(feature, np.nan)
            try:
                output[w08.RADIOMICS_PREFIXES[block] + feature] = float(value)
            except (TypeError, ValueError):
                output[w08.RADIOMICS_PREFIXES[block] + feature] = np.nan
        return output

    def _transform_one(self, identifier, state):
        case = self._prepare_case(identifier)
        image = w02.sitk.ReadImage(w02.apath(case["image_path"]))
        roi = case["roi"]
        habitat = self._habitat_from_boundary(case, state.boundary)
        low_mask = roi & (habitat == 0)
        high_mask = roi & (habitat == 1)
        low_voxel_count = int(low_mask.sum())
        high_voxel_count = int(high_mask.sum())
        low_state = _radiomics_support_state(low_voxel_count)
        high_state = _radiomics_support_state(high_voxel_count)
        tumour_n = int(roi.sum())
        spacing_xyz = case["spacing_xyz"]
        voxel_volume = float(np.prod(spacing_xyz))
        tumour_volume = float(tumour_n * voxel_volume)
        values = case["sv"]["Mean"].to_numpy(dtype=float)
        high_fraction = float(high_mask.sum() / float(tumour_n))
        interface = _six_neighbor_interface(habitat, roi, spacing_xyz)
        connected, n_connected = ndimage.label(
            high_mask, ndimage.generate_binary_structure(3, 1))
        sizes = np.bincount(connected.ravel())[1:] if n_connected else np.array([])
        largest = int(sizes.max()) if len(sizes) else 0
        depth = ndimage.distance_transform_edt(roi, sampling=spacing_xyz[::-1])
        max_depth = float(depth[roi].max()) if roi.any() else 0.0
        radial = (float(depth[high_mask].sum() / (max_depth * tumour_n))
                  if high_mask.any() and max_depth > 0 else 0.0)
        row = {
            "patient_id": identifier,
            "R_low_voxel_count": low_voxel_count,
            "R_high_voxel_count": high_voxel_count,
            "R_low_state": low_state,
            "R_high_state": high_state,
            "R_low_structurally_defined": int(low_voxel_count > 0),
            "R_high_structurally_defined": int(high_voxel_count > 0),
            "R_low_technically_extractable": int(
                low_state == RADIOMICS_STATE_EXTRACTABLE),
            "R_high_technically_extractable": int(
                high_state == RADIOMICS_STATE_EXTRACTABLE),
            "H_high_fraction": high_fraction,
            "sv_median_minus_boundary": float(np.median(values) - state.boundary),
            "sv_IQR": float(np.percentile(values, 75) - np.percentile(values, 25)),
            "interface_density": float(interface / tumour_volume),
            "H_high_largest_component_tumor_fraction": float(largest / float(tumour_n)),
            "H_high_radial_burden": radial,
        }
        if low_state == RADIOMICS_STATE_EXTRACTABLE:
            low_image_mask = w02.make_habitat_mask(
                image, low_mask.astype(np.uint8), 1)
            row.update(self._radiomics_for_mask(
                image, low_image_mask, "R_low", low_voxel_count))
        else:
            row.update({w08.RADIOMICS_PREFIXES["R_low"] + feature: np.nan
                        for feature in w08.FROZEN_CANDIDATE_FEATURES["R_low"]})
        if high_state == RADIOMICS_STATE_EXTRACTABLE:
            high_image_mask = w02.make_habitat_mask(
                image, high_mask.astype(np.uint8), 1)
            row.update(self._radiomics_for_mask(
                image, high_image_mask, "R_high", high_voxel_count))
        else:
            row.update({w08.RADIOMICS_PREFIXES["R_high"] + feature: np.nan
                        for feature in w08.FROZEN_CANDIDATE_FEATURES["R_high"]})
        return row

    def transform(self, ids, state):
        identifiers = [str(value).strip() for value in ids]
        if not set(identifiers).issubset(self._allowed_ids):
            raise w08.W08ValidationError("provider transform IDs are not in the A frame")
        self.transform_calls.append((tuple(identifiers), state.training_id_hash))
        cache = self._state_cache.setdefault(state.training_id_hash, {})
        new_rows = []
        for identifier in identifiers:
            if identifier not in cache:
                cache[identifier] = self._transform_one(identifier, state)
            new_rows.append(cache[identifier])
        generated = pd.DataFrame(new_rows).set_index("patient_id")
        base = self._by_id.loc[identifiers].copy()
        for column in RADIOMICS_SUPPORT_COLUMNS:
            base[column] = generated.loc[identifiers, column].to_numpy()
        for column in w08.GLOBAL_COLUMNS:
            base[column] = generated.loc[identifiers, column].to_numpy()
        for block in ("R_low", "R_high"):
            for feature in w08.FROZEN_CANDIDATE_FEATURES[block]:
                column = w08.RADIOMICS_PREFIXES[block] + feature
                base[column] = generated.loc[identifiers, column].to_numpy()
        return base.reset_index(drop=True)


def _serialise_complex(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def write_results(result, config, population, started_epoch, output_root):
    os.makedirs(output_root, exist_ok=True)
    predictions = result["predictions"].copy()
    fold_results = result["fold_results"].copy()
    selections = result["selection_results"].copy()

    prediction_columns = [
        "run_id", "model_id", "population", "repeat", "fold", "patient_id",
        "DFS_time", "DFS_event", "risk_score", "training_id_hash",
        "validation_id_hash", "outer_split_hash",
        "outer_validation_used_for_selection",
    ]
    _atomic_csv(predictions[prediction_columns],
                os.path.join(output_root, "predictions.csv"))

    complex_fold = ["centers", "representation_metadata", "preprocessing_audit",
                    "selected_features", "stability_actions",
                    "linear_predictor_clipping"]
    for column in complex_fold:
        if column in fold_results.columns:
            fold_results[column] = fold_results[column].map(_serialise_complex)
    _atomic_csv(fold_results, os.path.join(output_root, "fold_results.csv"))

    if "inner_records" in selections.columns:
        selections["inner_records"] = selections["inner_records"].map(
            _serialise_complex)
    if "linear_predictor_clipping" in selections.columns:
        selections["linear_predictor_clipping"] = selections[
            "linear_predictor_clipping"].map(_serialise_complex)
    _atomic_csv(selections, os.path.join(output_root, "selection_results.csv"))

    outer_summary = result["audit"]["outer_split_validation"]
    audit = dict(result["audit"])
    audit.update({
        "status": "formal_complete",
        "formal_run": True,
        "patient_level_outputs_written": True,
        "output_scope": "local_sensitive_prognosis_analysis_output_only",
        "W06_population_sha256": _sha256(W06_POPULATION),
        "W07_outer_split_sha256": w08.W07_OUTER_SPLIT_SHA256,
        "W04_protocol_sha256": w08.W04_PROTOCOL_SHA256,
        "n_population": int(len(population)),
        "prediction_rows_written": int(len(predictions)),
        "folds_expected": 50,
        "fold_results_expected": 650,
        "runs_expected": 13,
        "metrics_ready_schema": "prognosis_analysis/configs/w08_results_schema.json",
        "audit_schema": "prognosis_analysis/configs/w08_audit_schema.json",
        "created_at_epoch": time.time(),
        "started_at_epoch": started_epoch,
        "completed_at_epoch": time.time(),
        "outer_split_summary_copy": outer_summary,
        "model_freeze_lock_created": False,
    })
    _atomic_json(os.path.join(output_root, "audit.json"), audit)

    metadata = {
        "stage": "W08",
        "status": "formal_complete",
        "formal_run": True,
        "runs": list(w08.FIXED_RUN_IDS),
        "models": list(w08.MODEL_SPECS),
        "outer_split_hash": w08.W07_OUTER_SPLIT_SHA256,
        "W04_protocol_sha256": w08.W04_PROTOCOL_SHA256,
        "B_data_read": False,
        "B_reader_invoked": False,
        "B_source_opened": False,
        "B_statistics_generated": False,
        "outer_validation_used_for_selection": False,
        "patient_level_outputs_written": True,
        "outputs": {
            "predictions": "predictions.csv",
            "fold_results": "fold_results.csv",
            "selection_results": "selection_results.csv",
            "audit": "audit.json",
        },
    }
    _atomic_json(os.path.join(output_root, "run_metadata.json"), metadata)


def _load_population_and_provider(output_root=OUTPUT_ROOT):
    population = w08.load_frozen_a_population()
    frame = load_a_feature_frame(population)
    sv = pd.read_csv(SV_TABLE, encoding="utf-8-sig", dtype={"影像号": str})
    provider = AOnlyFoldFeatureProvider(
        frame, sv, cache_root=os.path.join(output_root, "work", "slic_cache"))
    return population, frame, provider


def smoke(output_root=OUTPUT_ROOT):
    """Validate one real A outer fold/provider transformation without fitting W08."""
    population, frame, provider = _load_population_and_provider(output_root)
    splits = w08.load_frozen_outer_splits(population)
    first = splits[(splits["repeat"] == 1) & (splits["fold"] == 1)]
    train_ids = sorted(first.loc[first["role"] == "train", "patient_id"].tolist())
    validation_ids = sorted(first.loc[first["role"] == "validation", "patient_id"].tolist())
    state = provider.fit(train_ids, 14346)
    train = provider.transform(train_ids[:2], state)
    validation = provider.transform(validation_ids[:2], state)
    required = w08._required_fold_specific_columns(list(w08.MODEL_SPECS))
    w08._validate_fold_provider_state(provider, state, train_ids, required)
    w08._validate_fold_provider_output(train, train_ids[:2], required, True)
    w08._validate_fold_provider_output(validation, validation_ids[:2], required, True)
    if not np.isfinite(train[list(w08.GLOBAL_COLUMNS)].to_numpy(dtype=float)).all():
        raise RuntimeError("smoke provider generated nonfinite global features")
    print(json.dumps({
        "stage": "W08",
        "status": "adapter_smoke_pass",
        "A_population": int(len(population)),
        "train_cases_checked": 2,
        "validation_cases_checked": 2,
        "B_data_read": False,
        "provider_formal_capable": bool(provider.formal_capable),
    }, ensure_ascii=False, sort_keys=True))


def preflight_fold(output_root=OUTPUT_ROOT):
    """Audit first-fold fold-specific mask sizes without radiomics/model fitting."""
    population, frame, provider = _load_population_and_provider(output_root)
    splits = w08.load_frozen_outer_splits(population)
    eligible = w08.eligible_ids(frame, "dual_radiomics")
    first = splits[(splits["repeat"] == 1) & (splits["fold"] == 1)]
    train_ids = sorted(set(first.loc[first["role"] == "train", "patient_id"]) & eligible)
    fold_ids = sorted(set(first["patient_id"]) & eligible)
    state = provider.fit(train_ids, 14346)
    sizes = []
    for identifier in fold_ids:
        case = provider._prepare_case(identifier)
        habitat = provider._habitat_from_boundary(case, state.boundary)
        sizes.append((identifier,
                      int((case["roi"] & (habitat == 0)).sum()),
                      int((case["roi"] & (habitat == 1)).sum())))
    subminimum = [row for row in sizes if row[1] < 10 or row[2] < 10]
    print(json.dumps({
        "stage": "W08",
        "status": "fold_mask_size_preflight_blocked",
        "population": "dual_radiomics",
        "eligible_cases": int(len(eligible)),
        "fold_cases": int(len(fold_ids)),
        "repeat": 1,
        "fold": 1,
        "boundary": float(state.boundary),
        "subminimum_cases": int(len(subminimum)),
        "min_low_mask_voxels": int(min(row[1] for row in sizes)),
        "min_high_mask_voxels": int(min(row[2] for row in sizes)),
        "locked_minimum_roi_size": 10,
        "B_data_read": False,
        "formal_run_started": False,
    }, ensure_ascii=False, sort_keys=True))


def formal(output_root=OUTPUT_ROOT):
    if os.path.exists(os.path.join(ROOT, "model_freeze_lock.json")):
        raise RuntimeError("W08 must not create or consume model_freeze_lock.json")
    final_names = ("predictions.csv", "fold_results.csv", "selection_results.csv",
                   "audit.json", "run_metadata.json")
    existing = [name for name in final_names
                if os.path.exists(os.path.join(output_root, name))]
    if existing:
        raise RuntimeError("formal W08 output already exists; inspect before rerun: %s" %
                           ",".join(existing))
    started = time.time()
    os.makedirs(output_root, exist_ok=True)
    _atomic_json(os.path.join(output_root, "run_state.json"), {
        "stage": "W08", "status": "running", "formal_run": True,
        "B_data_read": False, "started_at_epoch": started,
    })
    population, frame, provider = _load_population_and_provider(output_root)
    _atomic_json(os.path.join(output_root, "run_state.json"), {
        "stage": "W08", "status": "modeling", "formal_run": True,
        "B_data_read": False, "started_at_epoch": started,
        "A_population": int(len(population)), "W_columns": 1130,
        "slic_cache_cases": int(len(provider._case_cache)),
    })
    result = w08.run_w08(frame, provider)
    write_results(result, w08.load_config(), population, started, output_root)
    _atomic_json(os.path.join(output_root, "run_state.json"), {
        "stage": "W08", "status": "complete", "formal_run": True,
        "B_data_read": False, "started_at_epoch": started,
        "completed_at_epoch": time.time(),
        "n_fold_results": int(len(result["fold_results"])),
        "n_predictions": int(len(result["predictions"])),
    })
    print(json.dumps({
        "stage": "W08", "status": "formal_complete",
        "n_fold_results": int(len(result["fold_results"])),
        "n_predictions": int(len(result["predictions"])),
        "B_data_read": False,
        "output_root": "prognosis_analysis/output/w08_formal_A",
        "elapsed_seconds": round(time.time() - started, 3),
    }, ensure_ascii=False, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description="Local W08 A-only formal execution")
    parser.add_argument("--smoke", action="store_true",
                        help="validate one real A fold/provider transformation")
    parser.add_argument("--preflight-fold", action="store_true",
                        help="audit first-fold fold-specific mask sizes only")
    parser.add_argument("--output-root", default=OUTPUT_ROOT,
                        help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.smoke:
        smoke(args.output_root)
    elif args.preflight_fold:
        preflight_fold(args.output_root)
    else:
        formal(args.output_root)


if __name__ == "__main__":
    main()
