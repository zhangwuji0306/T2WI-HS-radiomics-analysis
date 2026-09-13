import json
import os
import sys
import unittest

import numpy as np
import SimpleITK as sitk


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..",
                                       "prognosis_analysis", "scripts"))
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import w08_formal_run_a as formal  # noqa: E402
import w08_nested_cv as w08  # noqa: E402


class MutableIdentityProvider(w08.FoldFeatureProvider):
    def __init__(self):
        self.version = "one"
        self.fit_count = 0
        self.formal_capable = False

    def representation_cache_identity(self):
        return {
            "provider_class": self.__class__.__name__,
            "contract_version": self.version,
        }

    def fit(self, training_ids, seed):
        self.fit_count += 1
        ids = sorted(str(value) for value in training_ids)
        return w08.FoldState(
            w08.canonical_id_hash(ids), int(seed), metadata={})

    def transform(self, ids, state):
        raise NotImplementedError


class W08L4RepresentationCacheTests(unittest.TestCase):
    def test_exact_scope_reuses_state_and_normalised_membership(self):
        provider = MutableIdentityProvider()
        cache = w08.FoldRepresentationCache(provider, ["R_low__f0"])

        first = cache.get_or_fit(["S002", "S001"], 123)
        second = cache.get_or_fit(["S001", "S002"], 123)

        self.assertIs(first, second)
        self.assertEqual(provider.fit_count, 1)
        self.assertEqual(cache.audit()["misses"], 1)
        self.assertEqual(cache.audit()["hits"], 1)
        self.assertEqual(
            first.metadata["representation_cache_key"]["training_id_hash"],
            w08.canonical_id_hash(["S001", "S002"]))

    def test_provider_identity_change_invalidates_same_fold_scope(self):
        provider = MutableIdentityProvider()
        cache = w08.FoldRepresentationCache(provider, [])
        cache.get_or_fit(["S001", "S002"], 123)
        provider.version = "two"
        cache.get_or_fit(["S001", "S002"], 123)

        audit = cache.audit()
        self.assertEqual(provider.fit_count, 2)
        self.assertEqual(len(audit["invalidations"]), 1)
        self.assertEqual(
            audit["invalidations"][0]["reason"],
            "provider_or_feature_schema_changed")
        self.assertNotIn("S001", json.dumps(audit, sort_keys=True))

    def test_mask_signature_requires_exact_voxel_mask(self):
        provider = formal.AOnlyFoldFeatureProvider.__new__(
            formal.AOnlyFoldFeatureProvider)
        provider._cache_contract = {"contract": "synthetic"}
        case = {
            "geometry_hash": "geometry",
            "image_file_sha256": "image",
            "roi_file_sha256": "roi",
        }
        first = np.zeros((2, 3, 4), dtype=np.uint8)
        first.flat[:10] = 1
        second = np.zeros_like(first)
        second.flat[1:11] = 1

        first_signature, _ = provider._mask_signature(case, "R_low", first)
        same_signature, _ = provider._mask_signature(case, "R_low", first.copy())
        changed_signature, _ = provider._mask_signature(case, "R_low", second)

        self.assertEqual(first_signature, same_signature)
        self.assertNotEqual(first_signature, changed_signature)

    def test_feature_cache_mismatch_recomputes_only_the_entry(self):
        provider = formal.AOnlyFoldFeatureProvider.__new__(
            formal.AOnlyFoldFeatureProvider)
        provider._cache_contract = {"contract": "synthetic"}
        provider._feature_cache = {}
        provider._mask_signatures = {}
        provider._cache_events = []
        provider._cache_counts = {
            "slic_hits": 0, "slic_misses": 0, "slic_invalidations": 0,
            "representation_hits": 0, "representation_misses": 0,
            "representation_invalidations": 0,
            "feature_hits": 0, "feature_misses": 0,
            "feature_invalidations": 0,
        }
        calls = []
        values = {
            formal.w08.RADIOMICS_PREFIXES["R_low"] + feature: float(index)
            for index, feature in enumerate(
                formal.w08.FROZEN_CANDIDATE_FEATURES["R_low"])
        }
        provider._radiomics_for_mask = lambda *_args: calls.append(1) or dict(values)
        image = sitk.GetImageFromArray(np.arange(24, dtype=np.float32).reshape(2, 3, 4))
        mask_array = np.zeros((2, 3, 4), dtype=np.uint8)
        mask_array.flat[:10] = 1
        mask = sitk.GetImageFromArray(mask_array)
        case = {
            "geometry_hash": "geometry",
            "image_file_sha256": "image",
            "roi_file_sha256": "roi",
        }

        provider._cached_radiomics_for_mask(
            "SYNTHETIC-001", case, image, mask, "R_low", 10)
        provider._cached_radiomics_for_mask(
            "SYNTHETIC-001", case, image, mask, "R_low", 10)
        self.assertEqual(len(calls), 1)

        cache_entry = next(iter(provider._feature_cache.values()))
        cache_entry["values"].pop(next(iter(cache_entry["values"])))
        provider._cached_radiomics_for_mask(
            "SYNTHETIC-001", case, image, mask, "R_low", 10)

        self.assertEqual(len(calls), 2)
        self.assertEqual(provider._cache_counts["feature_hits"], 1)
        self.assertEqual(provider._cache_counts["feature_invalidations"], 1)
        self.assertNotIn("SYNTHETIC-001", json.dumps(
            provider.representation_cache_audit(), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
