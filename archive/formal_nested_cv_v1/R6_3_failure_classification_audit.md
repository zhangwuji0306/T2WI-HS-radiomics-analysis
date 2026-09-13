# R6-3 failure classification audit

## Disposition

**唯一推荐类别：Class A — iteration budget insufficient / `iteration_budget_exhausted`.**

Machine-readable classification validation: `PASS`.

Authorized next remediation path: `R6-4A`.

Disposition is ready for protocol-owner review. The W08 gate remains `HOLD`. No
formal W08 rerun, performance output, W09 output, model freeze, or B access is
authorized by this audit.

## First-failure coordinate

| Field | Recorded aggregate value |
|---|---|
| Repeat / outer fold | `1 / 1` |
| Run / model | `M3H / M3H` |
| Population | `R_high` |
| Failure stage | `outer_final_refit` |
| Outer training / validation | `n=282 / n=67`; events `66 / 15` |
| Post-preprocessing feature count | `p=25`; `C=13`, `G=6`, `R_high=6` |
| Selected solver coordinates | `alpha=0.5`; lambda ratio index `50` of the frozen 100-point grid |
| Solver result | `non_converged`; `iteration_budget_exhausted`; `iterations=250` |
| Stability observations | `backtrack_objective`; 81 backtracks; 0 clipping events |
| Downstream output | No coefficient, risk score, held-out prediction, or performance result |

The coordinate is determined by the frozen execution order, not by a post hoc
search. `repeat=1 / outer_fold=1` is the first W07 outer split. The replay
completed the eight preceding fixed runs in that fold (`M0`, `M1`, `M2`,
`M0_W_available`, `M5`, `M2_R_low`, `M3L`, and `M2_R_high`) and stopped at the
next fixed run, `M3H`, on the `R_high` population. Inner CV had completed and
selected alpha/lambda before the complete outer-training refit failed. The
recorded inner seed is `13346`, consistent with the frozen seed rule for this
repeat/fold.

## Class determination

| Class | Determination | Exclusion or support basis |
|---|---|---|
| A — iteration budget insufficient | **TRUE; unique recommendation** | The frozen Elastic-Net path reached `max_iter=250`, remained `non_converged`, and raised `iteration_budget_exhausted` during `outer_final_refit`. Clipping count was `0`, and the failure occurred after population construction and inner-CV selection. |
| B — preprocessing/habitat/technical extractability mismatch | **FALSE** | R6-2 reached `M3H` with `R_high` features present after fold-specific preprocessing (`p=25`, including six `R_high` features). The preceding `M2_R_high` run completed in the same fold, and the technical preflight/replay evidence did not identify a habitat, mask, extractability, or preprocessing mismatch at the failure coordinate. |
| C — linear-predictor clipping participates in failure | **FALSE** | The recorded clipping count at the first failure was `0`; the diagnostic evidence does not show clipping participating in the failed iterations. |
| D — environment/reproducibility mismatch | **FALSE** | The locked `t2_radiomics` environment passed the recorded probe, and the first-failure replay reproduced the same coordinate and failure mode. The locked targeted suite was recorded as `70/70` on two runs. No version or environment mismatch was recorded. |
| E — implementation/protocol violation or untracked behavior change | **FALSE** | R6-1 observability was recorded as instrumentation-only; the current solver hash matches the R6-2 binding, the frozen W04/W07/W07A inputs and candidate hashes are unchanged, and the baseline-equivalence test covers Cox PH and Elastic-Net outputs. No untracked parameter, split, population, or B-boundary change was found. |

## Frozen bindings and invariants

| Binding | Value |
|---|---|
| W04 modeling protocol | `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe` |
| W07 outer split artifact | `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` |
| W07A protocol amendment | `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70` |
| W08 nested-CV configuration | `f432b9741071a37be37fb63361e2007978ee6f47d4ce269b36a8692aa4fcbe7a` |
| R6-1 solver source | `8f97fcc01cd7c821dd88468bd090d0ae6735018cdda775be491ae7d5b03026fb` |
| R_low candidate pool | 49 candidates; `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` |
| R_high candidate pool | 10 candidates; `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` |
| Solver bindings | `max_iter=250`; `tolerance=1e-7`; alpha grid `[0.1, 0.5, 0.9, 1.0]`; 100 lambda values per alpha; minimum ratio `1e-4` |
| Population and split invariants | A modeling population `393`; W07 outer CV `10 repeats × 5 folds`; W07A fold-specific eligibility and `minimumROISize=10` |

The R6-2 aggregate records agree with the current file hashes and with
`HEAD=origin/main=42e14caeab56907ebc913cbe607876cb7c4563ba`. No frozen binding
was changed for this classification.

The freeze is independently supported at each relevant layer: `250` and
`1e-7` are the solver budget and convergence threshold recorded by the W08
configuration and solver source; the alpha grid and 100-point lambda path are
validated by the implementation and appear unchanged in the replay binding;
the R_low/R_high candidate counts and hashes are the W03 frozen pools; the
W07 split hash identifies the exact repeat/fold sequence; and the A population
and W07A fold-specific eligibility rules are carried forward without dynamic
replacement. The observed failure is therefore a failure while applying these
bindings, not evidence that any binding was changed.

## Relationship to protocol-prescribed handling

The observed result is a fail-closed numerical failure under the frozen
protocol. The prescribed handling is to preserve the failure context, stop the
formal run at the first hard failure, and return to protocol review. It does
not permit deleting the failed candidate, skipping the fold or run, changing
the outer split, changing the alpha/lambda grid, changing the convergence
budget or tolerance, or substituting a new population. The current state is
therefore:

- `B_data_read=false`, `B_reader_invoked=false`, `B_source_opened=false`,
  `B_statistics_generated=false`;
- W08 `HOLD`;
- `model_freeze_lock.json` absent;
- formal predictions, performance metrics, and W09 artifacts absent.

## R6-4A remediation boundary

The authorized next path is R6-4A, which preserves the statistical model and
allows only a uniform, pre-specified convergence-efficiency remediation. A
fixed iteration-budget study or increase may use one common `max_iter` for
every Elastic-Net candidate; `tolerance=1e-7`, objective, convergence
criteria, alpha/lambda grids, candidate pools, W07 splits, W04/W07A
populations, and `minimumROISize=10` remain unchanged. A fixed-order
same-alpha lambda-path warm start may also be evaluated only if the candidate
grid and final optimization objective remain unchanged and zero-start and
warm-start solutions are numerically equivalent after sufficient convergence.

R6-4A does not authorize changing solver mathematics, deleting candidates,
skipping failed folds, changing eligibility, changing the endpoint, formal
W08 rerun, performance analysis, W09, or B access. R6-4A must be followed by
R6-5 numerical equivalence and regression, then R6-6 final-code technical
preflight/G3R, before any R6-7 formal W08 rerun.

## Evidence basis

- `prognosis_analysis/R6_0_baseline_audit.md`
- `prognosis_analysis/R6_1_observability_audit.md`
- `prognosis_analysis/R6_2_diagnostic_replay_audit.md`
- `prognosis_analysis/output/r6_2_diagnostic_replay/r6_2_diagnostic_replay.json`
- `prognosis_analysis/W07_outer_splits_protocol.md`
- `prognosis_analysis/W07A_pre_W08_protocol_amendment.md`
- `prognosis_analysis/W08_nested_cv_protocol.md`
- `prognosis_analysis/W08_implementation_audit.md`
- `prognosis_analysis/configs/w08_nested_cv.json`
- `prognosis_analysis/modeling_protocol.json`
- `prognosis_analysis/execution_status.json`

This audit contains aggregate, de-identified evidence only; no patient-level
content is copied into the repository.
