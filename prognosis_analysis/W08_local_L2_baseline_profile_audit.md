# W08 local L2 baseline profile audit

## Scope

This audit contains outcome-blind A-only technical input/cache timing and deterministic synthetic numerical timing. It contains no patient identifier, absolute path, clinical outcome, outer-validation prediction, or model performance result.

## Execution contract

- Repeats: 3; thread settings: OMP/MKL/OPENBLAS/NUMEXPR = 1.
- K-means binding: algorithm=kmeans, k=2, initialization=k-means++, n_init=100, max_iter=300, tol=1e-4.
- Elastic-Net binding: alpha grid size 4, 100 lambdas per alpha, max_iter=3000, tolerance=1e-07.
- The A input stage calls the existing `read_technical_A` boundary with technical columns only; B access flags are all false.

## A-only technical input evidence

The measured input stage used the existing outcome-blind A-only technical reader for frozen A metadata, a frozen A technical feature source, and the frozen A supervoxel summary. No outcome reader was invoked.

| Counter | Total across repeats | Median [range] per repeat |
|---|---:|---:|
| Technical rows sampled | 1179 [393, 393] | 393 [393, 393] |
| Successful technical rows | 1179 [393, 393] | 393 [393, 393] |
| Failed technical rows | 0 [0, 0] | 0 [0, 0] |

## Existing SLIC cache evidence

The SLIC stage exercised the production A-only case preparation and cache validation logic. Existing cache entries were checked read-only; cold-miss and invalid-cache checks used temporary copies that were removed after each repeat.

| Counter | Total across repeats | Median [range] per repeat |
|---|---:|---:|
| Existing cache files | 1179 [393, 393] | 393 [393, 393] |
| Existing cache sample | 9 [3, 3] | 3 [3, 3] |
| Cache hits | 9 [3, 3] | 3 [3, 3] |
| Cache misses | 3 [1, 1] | 1 [1, 1] |
| Validation failures | 3 [1, 1] | 1 [1, 1] |
| Recomputed entries | 3 [1, 1] | 1 [1, 1] |
## Aggregate timing and resource profile

All values below retain only the median, inclusive range, and counts across the three repeats.

| Stage | Success / repeats | Failures | Median seconds | Range seconds |
|---|---:|---:|---:|---:|
| `a_input_load` | 3 / 3 | 0 | 5.570830 | [5.388980, 5.804907] |
| `slic_cache_prepare_validate` | 3 / 3 | 0 | 2.291583 | [2.230011, 2.559033] |
| `single_fold_kmeans_n_init_100` | 3 / 3 | 0 | 0.113153 | [0.108757, 0.115491] |
| `habitat_mask_g_features` | 3 / 3 | 0 | 0.011237 | [0.009708, 0.012846] |
| `r_low_pyradiomics` | 3 / 3 | 0 | 0.069941 | [0.068922, 0.071469] |
| `r_high_pyradiomics` | 3 / 3 | 0 | 0.070348 | [0.069711, 0.072549] |
| `model_preprocessor` | 3 / 3 | 0 | 0.142709 | [0.141329, 0.152388] |
| `elastic_net_single_candidate` | 3 / 3 | 0 | 0.070557 | [0.069959, 0.072486] |
| `elastic_net_100_lambda_alpha_path` | 3 / 3 | 0 | 30.732965 | [29.825117, 31.198794] |
| `uno_weights_and_bottom_call` | 3 / 3 | 0 | 0.006308 | [0.005997, 0.008470] |

## Aggregate resource summary

Resource values use the same aggregate-only rule: median and inclusive range across the three repeats.

| Stage | CPU utilization % | Peak RSS bytes | Disk read bytes | Disk write bytes |
|---|---:|---:|---:|---:|
| `a_input_load` | 99.451 [99.290, 99.592] | 329981952 [298065920, 329981952] | 25111241 [25111241, 25115724] | 0 [0, 0] |
| `slic_cache_prepare_validate` | 98.867 [95.251, 99.495] | 329981952 [329981952, 330137600] | 2433185 [2433185, 2440995] | 28762 [28762, 28762] |
| `single_fold_kmeans_n_init_100` | 100.568 [94.704, 110.470] | 329981952 [329981952, 330137600] | 2894 [2894, 2894] | 0 [0, 0] |
| `habitat_mask_g_features` | 121.630 [0.000, 160.946] | 329981952 [329981952, 330137600] | 52063 [52063, 52063] | 0 [0, 0] |
| `r_low_pyradiomics` | 109.313 [90.682, 111.702] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |
| `r_high_pyradiomics` | 155.476 [107.686, 179.312] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |
| `model_preprocessor` | 98.539 [92.281, 99.502] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_single_candidate` | 110.725 [107.780, 111.673] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_100_lambda_alpha_path` | 99.591 [99.413, 99.649] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |
| `uno_weights_and_bottom_call` | 184.486 [0.000, 247.721] | 329981952 [329981952, 330137600] | 0 [0, 0] | 0 [0, 0] |

The JSON artifact is the machine-readable source for the same aggregate values.

## Relative hotspot reading

The stage medians distinguish PyRadiomics (R-low/R-high), synthetic Elastic-Net fitting (single candidate and 100-lambda alpha path), and A technical/synthetic input and cache I/O. These are software timing observations only and are not model performance measurements.

## Runtime estimate

- Basis: one complete A-technical plus synthetic repeat immediately before the measured repeats, with a 15% guard.
- Estimated total: 135.085 seconds.
- Above 40 minutes: false.

## Access and output boundary

`outcome_columns_read=false`; `formal_writer_invoked=false`; `B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`; `B_statistics_generated=false`.
