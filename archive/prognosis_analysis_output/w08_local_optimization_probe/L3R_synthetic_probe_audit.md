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
| `a_input_load` | 3 / 3 | 0 | 0.011264 | [0.005780, 0.019177] |
| `slic_cache_prepare_validate` | 3 / 3 | 0 | 0.035702 | [0.023566, 0.059111] |
| `single_fold_kmeans_n_init_100` | 3 / 3 | 0 | 0.160115 | [0.105904, 0.176329] |
| `habitat_mask_g_features` | 3 / 3 | 0 | 0.019353 | [0.010073, 0.020307] |
| `r_low_pyradiomics` | 3 / 3 | 0 | 0.106853 | [0.054169, 0.109579] |
| `r_high_pyradiomics` | 3 / 3 | 0 | 0.096481 | [0.048465, 0.112530] |
| `model_preprocessor` | 3 / 3 | 0 | 0.212185 | [0.130487, 0.220164] |
| `elastic_net_single_candidate` | 3 / 3 | 0 | 0.015999 | [0.011697, 0.018765] |
| `elastic_net_100_lambda_alpha_path` | 3 / 3 | 0 | 5.461936 | [5.393203, 8.051113] |
| `uno_weights_and_bottom_call` | 3 / 3 | 0 | 0.008154 | [0.006039, 0.016137] |

## Aggregate resource summary

Resource values use the same aggregate-only rule: median and inclusive range across the three repeats.

| Stage | CPU utilization % | Peak RSS bytes | Disk read bytes | Disk write bytes |
|---|---:|---:|---:|---:|
| `a_input_load` | 0.000 [0.000, 162.956] | 147582976 [141877248, 147738624] | 3836 [3836, 13133] | 3836 [3836, 3836] |
| `slic_cache_prepare_validate` | 79.300 [66.302, 87.529] | 147689472 [143507456, 147849216] | 1969 [1969, 9779] | 1004 [1004, 1004] |
| `single_fold_kmeans_n_init_100` | 103.277 [97.586, 106.335] | 147689472 [143831040, 147849216] | 2894 [2894, 2894] | 0 [0, 0] |
| `habitat_mask_g_features` | 153.886 [80.735, 155.113] | 147689472 [144494592, 147849216] | 52063 [52063, 52063] | 0 [0, 0] |
| `r_low_pyradiomics` | 131.606 [115.380, 142.591] | 147693568 [146796544, 147857408] | 0 [0, 0] | 0 [0, 0] |
| `r_high_pyradiomics` | 161.949 [83.311, 193.437] | 147697664 [146997248, 147857408] | 0 [0, 0] | 0 [0, 0] |
| `model_preprocessor` | 99.358 [95.730, 107.769] | 147697664 [147226624, 147857408] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_single_candidate` | 97.662 [83.267, 133.577] | 147697664 [147288064, 147857408] | 0 [0, 0] | 0 [0, 0] |
| `elastic_net_100_lambda_alpha_path` | 99.553 [98.783, 100.242] | 147697664 [147304448, 147857408] | 0 [0, 0] | 0 [0, 0] |
| `uno_weights_and_bottom_call` | 96.830 [0.000, 191.633] | 147697664 [147312640, 147857408] | 0 [0, 0] | 0 [0, 0] |

The JSON artifact is the machine-readable source for the same aggregate values.

## Relative hotspot reading

The stage medians distinguish PyRadiomics (R-low/R-high), synthetic Elastic-Net fitting (single candidate and 100-lambda alpha path), and A technical/synthetic input and cache I/O. These are software timing observations only and are not model performance measurements.

## Runtime estimate

- Basis: one complete A-technical plus synthetic repeat immediately before the measured repeats, with a 15% guard.
- Estimated total: 138.000 seconds.
- Above 40 minutes: false.

## Access and output boundary

`outcome_columns_read=false`; `formal_writer_invoked=false`; `B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`; `B_statistics_generated=false`.
