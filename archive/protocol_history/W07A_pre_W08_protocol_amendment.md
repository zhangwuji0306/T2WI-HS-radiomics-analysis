# W07A Pre-W08 Protocol Amendment

## Amendment status

- Amendment ID: `W07A_pre_W08_protocol_amendment`
- Status: `frozen`
- Effective timing: after W06/W07 and P1A–P1D audits; before any formal W08 prediction or performance calculation.
- Trigger: technical preflight only.
- Outcome-performance-informed: `false`.
- `B_data_read`: `false`.

This amendment fixes the W07A decisions required before the technical-only
preflight and any formal W08 run. It does not authorize formal prediction,
performance evaluation, Cox fitting, model selection, or access to B data.

## 1. Reader and data-access policy

Production A ingestion must use an explicitly authorized A-only reader/API.
Arbitrary custom readers are prohibited in production. A custom callable is
not an authorized reader; it must be rejected before it is executed. Any
authorized adapter must enforce the A allowlist and selected-column contract
at source-read time and return only authorized A rows. B data must not be
opened, materialized, or enter application memory.

The existing lock order remains mandatory: access and provenance locks are
validated before source opening or row materialization. A returned frame must
also pass identifier presence, uniqueness, and allowlist-subset checks before
downstream use.

## 2. Small-ROI state rule

For each fold-specific habitat mask, classify support by mask voxel count:

| State | Rule | Modeling meaning |
|---|---|---|
| `structural_absence` | count = 0 | The required habitat is absent; no radiomics value exists. |
| `technical_small_roi` | 1 ≤ count < 10 | The habitat is present but technically unavailable for extraction. |
| `extractable` | count ≥ 10 | The habitat satisfies the radiomics support rule. |

`structural_absence` and `technical_small_roi` are distinct states; 0 does
not equal 1–9. `minimumROISize` remains fixed at `10`. No unsupported block
may be converted to zero, ordinary missingness, or an imputed radiomics
value.

For a model requiring more than one radiomics block, retain each block state
separately. For a mutually exclusive model-level coverage classification,
assign `structural_absence` if any required block has count 0; otherwise assign
`technical_small_roi` if any required block has count 1–9; otherwise assign
`extractable` only when every required block has count ≥10.

## 3. Model-specific populations

The main population is the W06 A modeling population. Eligibility is assessed
within each outer repeat/fold after the fold-specific training-derived habitat
boundary is applied. Technical eligibility is not a performance-based
exclusion.

| Model/run | Population | Required radiomics support |
|---|---|---|
| M0 | `main` | None |
| M1 | `main` | None |
| M2 | `main` | None |
| M3L | current-fold `R_low` extractable | `R_low` count ≥10 |
| M3H | current-fold `R_high` extractable | `R_high` count ≥10 |
| M4 | current-fold dual extractable | `R_low` count ≥10 and `R_high` count ≥10 |

M0/M1/M2 retain the W04 primary architecture. Global-habitat structural
values defined by W04 remain valid values in the main population.

## 4. Paired comparator rule

Every radiomics comparator is paired within the same outer repeat/fold and
uses the identical eligible patient set, the identical train/validation role
assignment, and the identical training-derived habitat boundary:

- M3L is compared with M2 refit on the same current-fold `R_low`-eligible set.
- M3H is compared with M2 refit on the same current-fold `R_high`-eligible set.
- M4 is compared with M2 refit on the same current-fold dual-eligible set.
- M3L versus M3H uses the same current-fold dual-eligible set.

The boundary is fitted from outer-training patients only using the frozen
patient-balanced K=2 procedure, then applied unchanged to outer training and
outer validation. Outer-validation patients never contribute to center or
boundary fitting. No comparator may be reconstructed from a different
population, split, or boundary.

## 5. Clinical and penalty policy

### Primary low-dimensional models

M0, M1, and M2 keep the W04 primary architecture and use the unpenalized
Breslow Cox PH specification:

- M0: `C`;
- M1: `C + H_high_fraction`;
- M2: `C + G`.

All predeclared clinical predictors remain in `C`. No clinical predictor may
be removed by univariate outcome screening, P value, hazard ratio, coefficient
threshold, or complete-case selection. Clinical preprocessing remains
training-only.

### Prespecified ridge stability sensitivities

Before formal W08 performance is observed, run the prespecified sensitivity
models M0-R, M1-R, and M2-R with the same A-side population, W07 outer splits,
training-only preprocessing, and paired estimand as their corresponding
primary models. Their predictor blocks are respectively `C`, `C +
H_high_fraction`, and `C + G`; the complete clinical block is retained.

Each sensitivity uses pure ridge Cox (L2; `alpha=0`) without coefficient-zero
feature selection. In each outer fold, lambda selection uses only an
event-stratified inner 5-fold CV within outer training:

1. At β=0 in the relevant inner-training set, calculate the
   event-normalized observed-information scale `I0` and set
   `lambda_ref = trace(I0) / p`.
2. If `lambda_ref` is not positive, hard-fail the run; do not derive a scale
   from validation or from the full dataset.
3. Search 100 log-spaced values of `lambda / lambda_ref` from `10^4` through
   `10^-4`, using mean inner-validation Uno C-index for selection.
4. Within `1e-12`, select the larger lambda. After selection, recompute
   `lambda_ref` on the complete outer-training set and refit with the selected
   relative position.

Outer validation contributes only held-out prediction and evaluation after
the outer-training refit. It does not contribute to preprocessing, lambda
scale, lambda selection, or clinical membership.

### M3L/M3H/M4 penalty semantics

M3L, M3H, and M4 retain the current implementation semantics. The complete
preprocessed coefficient vector receives the same Elastic Net objective and
proximal penalty:

- M3L: the complete `C + G + R_low` vector is penalized;
- M3H: the complete `C + G + R_high` vector is penalized;
- M4: the complete `C + G + R_low + R_high` vector is penalized.

There is no exemption for `C` or `G`, no block-level penalty mask, and no
post hoc change to R-only penalty semantics. Shared alpha/lambda tuning remains
training-only inner-CV under the frozen W04/W08 selection rules. This decision
is fixed before any formal performance and may not be changed in response to
formal results.

## 6. Coverage estimand and W09 reporting contract

Coverage is reported by model/run and outer repeat/fold. The denominator
`validation_opportunities` is the relevant outer-validation A population
before the required fold-specific radiomics eligibility classification. For
M0/M1/M2, radiomics-state fields are `not_applicable`; their opportunities are
the main-population validation cases.

For each radiomics run, W09 must report:

- `validation_opportunities`: all relevant outer-validation opportunities;
- `valid_predictions`: held-out predictions produced from the final
  outer-training fit for patients satisfying the model-specific population;
- `structural_absence`: counts, with per-block counts retained and the
  model-level mutually exclusive count defined above;
- `technical_small_roi_unavailable`: counts, with per-block counts retained
  and the model-level mutually exclusive count defined above;
- `per_patient_held_out_prediction_count`: the number of valid held-out
  predictions contributed by each patient across the 10 repeats, including
  zero when no valid prediction exists for that run;
- `per-fold effective n`: the number of valid held-out predictions used for
  each fold-level metric, retained separately for every repeat/fold and
  model/run.

The model-level coverage categories must reconcile to the opportunities
unless a separate prespecified hard-failure reason is recorded. Structural
absence must not be pooled with technical small-ROI unavailability. Paired
comparators must report the same opportunity set, valid-prediction set, and
effective `n` within each paired fold. A metric that cannot be estimated is
recorded as not estimable with its prespecified reason; no alternate metric,
population, or endpoint is substituted.

## 7. Non-estimability and hard-fail rule

For every required model-specific population and every outer fold, the
training and validation event gates must be satisfied. Every inner 5-fold
training and validation partition used for tuning must also satisfy the event
gate. If technical eligibility causes any required training/validation event
gate or inner 5-fold gate to fail:

- do not change W07 outer splits;
- do not dynamically reduce the number of folds or repeats;
- do not lower `minimumROISize=10`;
- do not add or replace cases;
- do not change the boundary, candidate pools, endpoint, alpha grid, or
  lambda rule.

The formal run hard-fails and returns to protocol review. This amendment
defines no fallback; therefore no fallback is available for an event-gate or
inner-CV failure. The failure must be recorded with the affected model/run,
repeat/fold, population state, and gate type without exposing patient-level
identifiers.

## 8. Protocol lock and provenance

The companion JSON file records `W07A_protocol_sha256`, the SHA-256 of the
exact UTF-8 bytes of this Markdown amendment. W08 code/configuration must
hard-bind that recorded hash before any formal W08 prediction or performance
run. The hash is a protocol identity check and does not authorize a formal
run or change any existing scientific freeze.

The non-identifying audit basis and source provenance are recorded in the
companion JSON. Existing W04, W03, W06, W07, technical freeze, candidate-pool,
and outer-split artifacts remain unchanged.
