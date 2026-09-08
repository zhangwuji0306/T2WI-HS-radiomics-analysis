"""Shared, fail-closed K-means parameters for the W08 production entries."""
from __future__ import absolute_import

import json
import math
import os
from collections import namedtuple


_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_HABITAT_CONFIG = os.path.join(
    _PROJECT_ROOT, "habitat_analysis", "configs",
    "main_cross_case_kmeans_k2_4mm.json")

_FROZEN_VALUES = {
    "algorithm": "kmeans",
    "k": 2,
    "initialization": "k-means++",
    "n_init": 100,
    "max_iter": 300,
    "tol": 1e-4,
}


class FrozenKMeansParameters(namedtuple(
        "FrozenKMeansParameters",
        ("algorithm", "k", "initialization", "n_init", "max_iter", "tol"))):
    """Immutable validated parameters shared by every W08 K-means entry."""

    __slots__ = ()

    def as_dict(self):
        return {name: getattr(self, name) for name in _FROZEN_VALUES}

    def sklearn_kwargs(self):
        """Return only parameters consumed by sklearn.cluster.KMeans."""
        return {
            "n_clusters": self.k,
            "init": self.initialization,
            "n_init": self.n_init,
            "max_iter": self.max_iter,
            "tol": self.tol,
        }


def _is_exact_int(value):
    return type(value) is int


def _is_finite_number(value):
    return type(value) in (int, float) and math.isfinite(float(value))


def _validate_clustering_section(config):
    if not isinstance(config, dict):
        raise RuntimeError("frozen habitat configuration must be a JSON object")
    clustering = config.get("clustering")
    if not isinstance(clustering, dict):
        raise RuntimeError("frozen habitat configuration lacks clustering object")

    missing = sorted(set(_FROZEN_VALUES) - set(clustering))
    if missing:
        raise RuntimeError(
            "frozen habitat configuration lacks clustering keys: %s" % missing)

    if clustering.get("algorithm") != _FROZEN_VALUES["algorithm"]:
        raise RuntimeError("frozen K-means algorithm must be kmeans")
    if not _is_exact_int(clustering.get("k")) or \
            clustering.get("k") != _FROZEN_VALUES["k"]:
        raise RuntimeError("frozen K-means k must be the locked value 2")
    if clustering.get("initialization") != _FROZEN_VALUES["initialization"]:
        raise RuntimeError("frozen K-means initialization must be k-means++")
    if not _is_exact_int(clustering.get("n_init")) or \
            clustering.get("n_init") != _FROZEN_VALUES["n_init"]:
        raise RuntimeError("frozen K-means n_init must be the locked value 100")
    if not _is_exact_int(clustering.get("max_iter")) or \
            clustering.get("max_iter") != _FROZEN_VALUES["max_iter"]:
        raise RuntimeError("frozen K-means max_iter must be the locked value 300")
    if not _is_finite_number(clustering.get("tol")) or \
            float(clustering.get("tol")) != _FROZEN_VALUES["tol"]:
        raise RuntimeError("frozen K-means tol must be the locked value 1e-4")

    return FrozenKMeansParameters(
        _FROZEN_VALUES["algorithm"],
        _FROZEN_VALUES["k"],
        _FROZEN_VALUES["initialization"],
        _FROZEN_VALUES["n_init"],
        _FROZEN_VALUES["max_iter"],
        _FROZEN_VALUES["tol"],
    )


def load_frozen_kmeans_parameters(config_path=DEFAULT_HABITAT_CONFIG):
    """Load and validate the repository's complete frozen K-means contract."""
    if not isinstance(config_path, str) or not config_path.strip():
        raise RuntimeError("frozen habitat configuration path is invalid")
    try:
        with open(config_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        raise RuntimeError("cannot load frozen habitat configuration: %s" % exc)
    return _validate_clustering_section(payload)


KMEANS_PARAMETERS = load_frozen_kmeans_parameters()


def validate_frozen_kmeans_parameters(config_path=DEFAULT_HABITAT_CONFIG):
    """Revalidate the source and return the module's shared frozen object."""
    current = load_frozen_kmeans_parameters(config_path)
    if current != KMEANS_PARAMETERS:
        raise RuntimeError("frozen K-means parameters changed after module load")
    return KMEANS_PARAMETERS
