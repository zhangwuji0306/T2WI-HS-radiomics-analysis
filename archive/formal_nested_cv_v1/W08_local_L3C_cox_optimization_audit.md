# W08 local L3C Cox optimization audit

## Scope

This audit covers exact, outcome-blind Cox-core and inner-fold Uno-layout
reuse for the W08 local optimization stage. It does not authorize or execute
formal W08, outer-final Cox fitting, prediction, performance evaluation, model
freezing, W09, or B access.

## Implementation binding

- The existing Breslow objective, gradient, penalty, line search, convergence
  criteria, zero-start, alpha order, lambda order, and candidate order remain
  unchanged.
- Each Cox fit prepares stable descending-time order, sorted design data,
  unique event-time boundaries, risk-set endpoints, event counts, and event-X
  summaries once. The prepared core returns log-likelihood and gradient from
  the same risk-set pass.
- Elastic-Net iterations reuse the current-beta smooth/objective calculation
  and the accepted proposal calculation within the same iteration. No warm
  start, active-set rule, strong rule, candidate deletion, or external Cox
  solver was introduced.
- Each inner fold prepares censoring KM weights and comparable validation pairs
  once; Elastic-Net and prescribed ridge sensitivity tuning reuse that layout
  for every candidate in the fold.

## Numerical verification

The L3C synthetic regression suite passed for both tied and untied survival
times, including prepared risk geometry, coefficient/objective/gradient
calculation, convergence and fail-closed failure state, and reuse of inner
Uno weights and comparable pairs. Existing R6-4A solver regression and the
R6-5 numerical-equivalence tests also passed.

The deterministic synthetic fixtures exercised low-dimensional and
multi-feature Cox designs, alpha values in the frozen grid, ordinary
convergence, line-search behavior, and explicit iteration-budget failure.
No real A outcome column was opened and no formal risk or performance
artifact was generated.

## Execution environment

The project-root `environment.yml` was treated as the sole environment
contract. The verified invocation used `tools/run_t2_radiomics.ps1` and
environment `t2_radiomics`, reporting Python 3.7.12, NumPy 1.21.6, pandas
1.3.5, SciPy 1.7.3, scikit-learn 1.0.2, PyRadiomics 3.0.1, SimpleITK 2.2.1,
and PyWavelets 1.3.0.

## Synthetic timing

Three repeats were run in the locked `t2_radiomics` environment with
OMP/MKL/OPENBLAS/NUMEXPR set to one thread. The synthetic 4-alpha × 100-lambda
Elastic-Net path had a median duration of **6.297300 seconds** (range
5.331141–8.253964 seconds). The L2 baseline for the same probe stage was
30.732965 seconds (range 29.825117–31.198794 seconds). These are software
timings only, not model-performance results.

## Boundary

`outcome_columns_read=false`; `formal_writer_invoked=false`;
`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
`B_statistics_generated=false`.

The L3C implementation is ready for independent review and later L4
integration. This Worker stops at L3C.
