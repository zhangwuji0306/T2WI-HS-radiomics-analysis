# W08 local L2 baseline profile audit

## Scope

This audit contains synthetic, outcome-blind technical timing only. It contains no patient identifier, absolute path, clinical outcome, outer-validation prediction, or model performance result.

## Execution contract

- Repeats: 3; thread settings: OMP/MKL/OPENBLAS/NUMEXPR = 1.
- K-means binding: algorithm=kmeans, k=2, initialization=k-means++, n_init=100, max_iter=300, tol=1e-4.
- Elastic-Net binding: alpha grid size 4, 100 lambdas per alpha, max_iter=3000, tolerance=1e-07.
- Synthetic technical fixture only; B access flags are all false.

## Aggregate timing and resource profile

All values below retain only the median, inclusive range, and counts across the three repeats.

| Stage | Success / repeats | Failures | Median seconds | Range seconds |
|---|---:|---:|---:|---:|
| `a_input_load` | 3 / 3 | 0 | 0.006788 | [0.006252, 0.010843] |
| `slic_cache_prepare_validate` | 3 / 3 | 0 | 0.029500 | [0.026574, 0.042241] |
| `single_fold_kmeans_n_init_100` | 3 / 3 | 0 | 0.124605 | [0.107818, 0.146784] |
| `habitat_mask_g_features` | 3 / 3 | 0 | 0.011399 | [0.010133, 0.014366] |
| `r_low_pyradiomics` | 3 / 3 | 0 | 0.073637 | [0.067870, 0.109747] |
| `r_high_pyradiomics` | 3 / 3 | 0 | 0.075484 | [0.068812, 0.102606] |
| `model_preprocessor` | 3 / 3 | 0 | 0.152735 | [0.141948, 0.187448] |
| `elastic_net_single_candidate` | 3 / 3 | 0 | 0.081551 | [0.072138, 0.082320] |
| `elastic_net_100_lambda_alpha_path` | 3 / 3 | 0 | 31.368313 | [30.115491, 31.858156] |
| `uno_weights_and_bottom_call` | 3 / 3 | 0 | 0.006687 | [0.005962, 0.006733] |

## Aggregate resource summary

Resource values use the same aggregate-only rule: median and inclusive range across the three repeats.

| Stage | CPU utilization % | Peak RSS bytes | Disk read bytes | Disk write bytes |
|---|---:|---:|---:|---:|
| `a_input_load` | 0.000 [0.000, 144.098] | 147709952 [141819904, 147828736] | 3836 [3836, 13133] | 3836 [3836, 3836] |
| `slic_cache_prepare_validate` | 105.931 [73.980, 117.595] | 147808256 [143257600, 147894272] | 1969 [1969, 9779] | 1004 [1004, 1004] |
| `single_fold_kmeans_n_init_100` | 100.317 [95.804, 101.444] | 147808256 [143564800, 147894272] | 2894 [2894, 2894] | 0 [0, 0] |
| `habitat_mask_g_features` | 137.075 [108.764, 154.196] | 147808256 [144220160, 147894272] | 52063 [52063, 52063] | 0 [0, 0] |
| `r_low_pyradiomics` | 127.314 [99.661, 230.218] | 147828736 [146833408, 147902464] | 0 [0, 0] | 0 [0, 0] |
| `r_high_pyradiomics` | 121.826 [90.828, 124.198] | 147828736 [147099648, 147902464] | 0 [0, 0] | 0 [0, 0] |
| `model_preprocessor` | 100.028 [99.068, 102.301] | 147828736 [147415040, 147902464] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_single_candidate` | 108.300 [95.799, 113.885] | 147828736 [147476480, 147902464] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_100_lambda_alpha_path` | 99.253 [98.925, 99.324] | 147828736 [147521536, 147902464] | 0 [0, 0] | 0 [0, 0] |
| `uno_weights_and_bottom_call` | 233.652 [232.069, 262.081] | 147828736 [147521536, 147902464] | 0 [0, 0] | 0 [0, 0] |

The JSON artifact is the machine-readable source for the same aggregate values.

## Relative hotspot reading

The stage medians distinguish PyRadiomics (R-low/R-high), synthetic Elastic-Net fitting (single candidate and 100-lambda alpha path), and synthetic input/cache I/O. These are software timing observations only and are not model performance measurements.

## Runtime estimate

- Basis: one complete synthetic repeat immediately before the measured repeats, with a 15% guard.
- Estimated total: 111.131 seconds.
- Above 40 minutes: false.

## Access and output boundary

`outcome_columns_read=false`; `formal_writer_invoked=false`; `B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`; `B_statistics_generated=false`.
