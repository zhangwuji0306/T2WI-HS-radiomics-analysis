# W04 Modeling protocol freeze

**Protocol ID:** `W04_modeling_protocol_freeze`
**Protocol version:** `1.0`
**Status:** frozen before first A DFS read
**Scope:** A-only prognostic model development; B remains locked.

This document and the paired JSON are the sole W04 modeling specification. The
protocol is outcome-blind at freeze. No DFS, OS, CSS, clinical, pathology or B
data are read in W04.

## Frozen source revisions

| Source | Path | SHA-256 |
|---|---|---|
| Taskbook | `T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md` | `0ba96334e37b5729356b947ffa41bd2d52649cc84f8d760ba4bbc51a129ffc3c` |
| Formal workflow | `三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md` | `26be0bae34faf6dc0b22c7bb3f3e041988ed87cb85b5de1c72cfe8969bd1fd6d` |
| W01 technical freeze | `habitat_analysis/freeze_lock.json` | `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262` |
| W01 feature dictionary | `habitat_analysis/feature_dictionary.md` | `e8b5b181cd977a548c6fcff5fcbbc534be2f830b347fae589fcb38ebaf0429db` |
| W01 method config | `habitat_analysis/configs/main_cross_case_kmeans_k2_4mm.json` | `fc2f856b3bc3fcd3d358f4476fd87a8117568712b3fc382c5e24e315e976bb3f` |
| W02 protocol | `prognosis_analysis/W02_habitat_radiomics_protocol.md` | `110fffe7bb2276d27276a338ff8cda829f7b22ffb522f539cad054c0c5bd4672` |
| W02 config | `prognosis_analysis/configs/w02_habitat_radiomics.json` | `4b74b8cabd90a8e7ae1d269abc13fd8f423e1b192f3fbb2effafab1c9cb5342f` |
| W02 schema | `prognosis_analysis/output/w02_habitat_radiomics_A/feature_schema.json` | `dab26184bd8ed09d1bf74aac91ff4f7e2729d23260744a2c640cc09cfcad1100` |
| W03 protocol | `prognosis_analysis/W03_habitat_radiomics_protocol.md` | `1a572d42e405cf9b4bcc71576927ca498b373ffb43cbbacc5f75c3bc5c0b73c6` |
| W03 config | `prognosis_analysis/configs/w03_habitat_radiomics.json` | `cfd98e5aa68f5cfcbe070287c702bd9582112c7e27f6ff4641748a78abd34307` |
| W03 candidate freeze | `prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json` | `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2` |
| W03 schema | `prognosis_analysis/output/w03_habitat_radiomics_A/feature_schema.json` | `17d96e2ec8567b8f39cc7ff9cb72f792bdecc31d2d275ff8345cf9b6035a1d04` |
| W03 output manifest | `prognosis_analysis/output/w03_habitat_radiomics_A/output_manifest.json` | `85756d47dafa858c9ac554d85313327ba5b7dbf7e72073ef43fa42460e01b444` |
| Whole-tumor technical QC | `prognosis_analysis/scripts/stage6_qc.py` | `458955763d6862e0669f745accf8f31e590c6449b7bb51bd717edbb4388d8ca8` |

The technical environment is Python `3.7.12`, PyRadiomics `3.0.1` and
SimpleITK `2.2.1`. The W04 freeze commit is
`c47e322ca2e2d85546ac36ef32f86ff6461f821c`. The technical seed root is the
predeclared `random_seed=12345` in `feature_extract/configs/radiomics_params.yaml`.

## Access gates

At W04 freeze:

```text
A_outcome_read_allowed = false
B_unlock = false
prognosis_analysis/model_freeze_lock.json = not generated
```

The first A DFS read is allowed only after all of the following are complete:

1. `habitat_analysis/freeze_lock.json` validates with
   `A_outcome_unlock=true` and `B_unlock=false`.
2. W02 H-low/H-high Original radiomics schema and availability rules are
   frozen.
3. W03 `R_low` and `R_high` candidate pools are frozen.
4. This protocol is frozen and its hash is recorded.
5. W05 A-only reading and the centralized cohort split resolver pass.
6. The B reader hard-fails before any physical B file read.

Any missing prerequisite is a hard failure and must not trigger a DFS read.
B access recognizes only a valid `prognosis_analysis/model_freeze_lock.json`
generated after W13 strict validation. W04 does not create that file.

## Endpoint

The primary endpoint is DFS, using the locked `DFS_time` and `DFS_event`
columns after W06 endpoint QC. The prespecified horizons are 3 years and 5
years. OS and CSS are secondary endpoints only after the primary DFS protocol
and A-only model development are fixed; they are not part of W04 model
selection.

## Predictor blocks

### Clinical block C

The fixed treatment-time clinical block contains exactly:

```text
年龄, CEA_log, mrT_4级, mrN_3级, MRF, mrEMVI, thickness, EID, 活检病理非腺癌
```

Age, `CEA_log`, `thickness` and `EID` are continuous. `mrT_4级` and `mrN_3级`
are one-hot encoded categorical variables. MRF, mrEMVI and biopsy pathology
non-adenocarcinoma are binary. Categorical reference levels are the lowest
predeclared levels and cannot be selected from outcome data.

Sex, `length`, `distance` and all postoperative variables are excluded from
the primary treatment-time model.

### Global habitat block G

G contains exactly the six W01-frozen global descriptors:

```text
H_high_fraction
sv_median_minus_boundary
sv_IQR
interface_density
H_high_largest_component_tumor_fraction
H_high_radial_burden
```

`habitat_entropy` and `H_high_component_density` remain descriptive and are not
primary predictors. The W01 technical center values are used for full-A
technical representation and final refit only; each nested outer training
fold refits its own centers and boundary.

### Habitat-specific radiomics

The W03 candidate pools are fixed before outcome access:

| Block | Count | Candidate hash | Technical gate |
|---|---:|---|---|
| `R_low` | 49 | `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` | ICC(2,1) > 0.75, at least 10 valid pairs, finite rate ≥ 0.95 in each reader among habitat-present cases |
| `R_high` | 10 | `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` | same prespecified gate |

Both blocks use the W02/W03 Original-only schema and the same technical rules.
The primary model reader is R1; R2 is used only for W03 reproducibility and is
never pooled into primary predictors.

### Whole-tumor reference block W

W is the fixed whole-tumor `muscle_f0.25` technical schema in
`feature_extract/output/features_v2/`, with no outcome-based prefiltering:

| Batch | Fixed feature count |
|---|---:|
| Original | 107, including Shape |
| Wavelet | 8 × 93 = 744, without Shape |
| LoG | 3 × 93 = 279, without Shape |
| Total | 1,130 |

Original, Wavelet and LoG schema and implementation are bound to the frozen
technical configuration and scripts listed in the JSON source revisions. W is
only a reference comparator; its high-dimensional preprocessing and selection
are training-only.

## Formal model set

| Model | Predictors | Family | Role / population |
|---|---|---|---|
| M0 | C | unpenalized Cox PH | clinical baseline |
| M1 | C + `H_high_fraction` | unpenalized Cox PH | high-signal burden |
| M2 | C + G | unpenalized Cox PH | macro-habitat organization |
| M3L | C + G + R_low | Elastic-Net Cox | H-low internal texture; R_low-eligible population |
| M3H | C + G + R_high | Elastic-Net Cox | H-high internal texture; R_high-eligible population |
| M4 | C + G + R_low + R_high | Elastic-Net Cox | dual-habitat texture complementarity; dual-radiomics eligible population only |
| M5 | C + W | Elastic-Net Cox | whole-tumor reference comparator |

For high-dimensional models, Elastic-Net Cox is the priority and fixed model
family. The low-dimensional C/G models use unpenalized Cox PH with Breslow
treatment of ties.

## Fixed comparisons

Only the following comparisons are primary and in this order:

```text
M0 → M1
M1 → M2
M2 → M3L
M2 → M3H
M3L vs M3H
M2 → M4
M0 → M5
```

`M2` is refit on the identical eligible patients and outer splits when it is a
comparator for M3L, M3H or M4. Likewise, M0 is refit on the W-available
patients for M0→M5. Every paired comparison uses the same patients and same
outer splits.

The following combinations are not primary models and cannot be added after
DFS access:

```text
C + W + R_low
C + W + R_high
C + W + G + R_low
C + W + G + R_high
C + W + G + R_low + R_high
```

## Eligibility and fixed missingness rules

The main technical population is exact A393 membership from the first-stage
technical freeze. A137 is an exact strict sensitivity subset evaluated within
the A393 outer-validation framework; it does not define a second development
method.

The A modeling population is A393 intersected with valid A DFS records after
W06 QC. The only allowed exclusions are frozen technical exclusions, outcome
unavailability, duplicated IDs, `DFS_time<=0`, `DFS_event` outside `{0,1}`,
event/time conflicts and explicit unrepairable source-data errors. Cases cannot
be excluded because of model performance, feature association or fold-level
results.

Model-specific populations are fixed as follows:

- M0/M1/M2 use the main A modeling population; C and G structural values are
  retained.
- M5 uses the W-available main population; M0 is refit on that same population.
- M3L uses the R_low-eligible population; M2 is refit on those same patients.
- M3H uses the R_high-eligible population; M2 is refit on those same patients.
- M4 and the M3L-versus-M3H comparison use the dual-radiomics eligible
  population where both radiomics blocks are structurally and technically
  available.

For G, a missing H-high phenotype has structural zero values for
`H_high_fraction`, `interface_density`,
`H_high_largest_component_tumor_fraction` and `H_high_radial_burden`.
`sv_median_minus_boundary` and `sv_IQR` remain defined. Structural zeros are
valid values and are not imputed.

For R_low/R_high, structural absence remains `null`/structurally undefined and
technical failure remains `null`/technical failure. Neither is converted to
zero or ordinary missingness. A case is in a radiomics model population only
when the required block is structurally and technically available. Within an
eligible block, nonfinite feature values are median-imputed inside the current
training fit only; if a feature has no finite value in that training fit, it is
dropped in that fit. No outcome-based availability filter is permitted.

Clinical continuous variables use the training-fold median for imputation;
categorical variables use the training-fold mode, with ties resolved by the
lowest predeclared level. Invalid levels hard-fail. Predictor missingness does
not trigger a complete-case exclusion.

## Repeated nested validation

The outer design is stratified by `DFS_event`, 5 folds × 10 repeats, yielding
50 outer validation folds. The inner design is stratified 5-fold CV within each
outer training set. Both outer and inner training and validation folds must
contain at least one event; otherwise the run hard-fails without reducing the
number of folds or changing the endpoint.

The deterministic seed root is 12345. With repeat indexed 1–10 and outer fold
indexed 1–5:

```text
outer_split_seed = 12345 + (repeat - 1)
inner_split_seed = 12345 + 1000 + 10*(repeat - 1) + outer_fold
fold_kmeans_seed = 12345 + 2000 + 10*(repeat - 1) + outer_fold
model_solver_seed = 12345 + 3000 + 10*(repeat - 1) + outer_fold
```

All seed values are recorded per fold. No unseeded random operation is allowed.

For every outer fold, only outer-training patients are used to refit the
patient-balanced K=2 centers. Each patient contributes total supervoxel weight
1 (`1/n_i` per effective supervoxel). The lower and higher centers are H-low
and H-high, and their midpoint is the fold boundary. That boundary is applied
to both outer training and outer validation patients. Fold-specific G and
fold-specific R_low/R_high are regenerated from those masks; full-A frozen G
is not used as an outer-validation representation.

## Training-only preprocessing and tuning

Outer validation never fits or tunes centers, boundary, habitat masks, G,
radiomics, imputation, variance filters, correlation filters, scaling,
feature selection, alpha or lambda.

For high-dimensional blocks the fixed order is:

```text
training-only imputation
→ training-only near-zero variance filter
→ training-only correlation reduction
→ training-only scaling
→ inner-CV alpha/lambda tuning
→ outer-training refit and Elastic-Net feature selection
```

Near-zero variance is removed when `n_unique<=1`, or when both
`n_unique/n_training<0.01` and the most-common/second-most-common frequency
ratio is greater than 100. A zero second frequency gives an infinite ratio.
Correlation reduction uses absolute Pearson correlation `>0.90` on the
training data and retains the lexicographically first feature in the frozen
feature order. Numeric predictors are z-scored with the training mean and
training population standard deviation; validation data are transformed only
with those parameters.

The Elastic-Net alpha grid is exactly:

```text
[0.1, 0.5, 0.9, 1.0]
```

For each alpha, 100 log-spaced lambda values run from the training-only
`lambda_max` to `lambda_max × 1e-4`. Lambda and alpha are selected only by
inner-CV mean Uno C-index. A tie within `1e-12` selects the larger lambda, then
the smaller alpha in the frozen grid order. No univariate outcome ranking is
used. Selected radiomics features are those with non-zero coefficients in the
tuned training-only fit.

## Evaluation metrics

All performance measures are calculated from held-out outer-validation
predictions. The fixed discrimination metrics are Harrell C-index, Uno
C-index, time-dependent AUC at 3 years and time-dependent AUC at 5 years.

The fixed calibration metrics are 3-year and 5-year calibration, calibration
slope at each horizon, and calibration-in-the-large at each horizon. The fixed
prediction-error metrics are IPCW Brier score at 3 years, IPCW Brier score at 5
years, and integrated Brier score through 5 years. Censoring weights for
outer-validation evaluation are estimated from the corresponding training
data only.

Feature stability is reported as selection frequency across the 50 outer folds,
with repeat/fold consistency. Every fixed comparison reports paired metric
differences on identical patients and splits. Fold-level and repeat-level
results are retained and summarized across all 50 outer folds. A single maximum
fold or repeat value cannot select the final architecture. A metric that is not
estimable is recorded with its prespecified reason; it is not replaced by a
different metric or endpoint.

Final architecture selection is deferred to W11 and is limited to M0–M4. It
uses the frozen hierarchy, incremental evidence, parsimony and stability. M5
remains the whole-tumor reference comparator. W04 does not select a final
architecture.
