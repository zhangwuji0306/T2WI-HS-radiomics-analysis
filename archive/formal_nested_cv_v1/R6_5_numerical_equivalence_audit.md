# R6-5 numerical equivalence and implementation regression audit

## Disposition

`PASS` for the authorized R6-5 scope. Canonical coordinate/provenance binding, direct old/new solver equivalence, and old/new pure selection-reducer equivalence on the complete 100-point grid passed within the registered tolerances. The W08 gate remains `HOLD`; this evidence does not authorize R6-6/G3R, formal W08, outer-final Cox fitting, prediction, performance evaluation, model freezing, or B access.

Machine-readable evidence: `prognosis_analysis/R6_5_numerical_equivalence.json`.

## Coordinate and provenance binding

The superseding R6-5R disposition is applied. The canonical coordinate is `repeat=1`, `outer_fold=1`, `population=R_high`:

| Binding | Training | Validation |
|---|---:|---:|
| Full outer side | 314 | 79 |
| Extractable / eligible | 282 | 67 |
| Structural absence | 21 | 7 |
| Technical small ROI | 11 | 5 |

The canonical eligible ID hashes are the registered R6-5R values:

- training: `90b08549c4bd7204a8437ce5fb984af608ba019a0cc10e6d1124b9fbddaf41b1`
- validation: `148ac9faad72ba250b558246967b26adfe3c52f9ff09e07377e6c3bef374dd06`

The full outer train/validation ID hashes independently match the R6-5R registration. The frozen W07 split file and canonical split hash both equal `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.

The P3B contract remains sourced from P3B with `minimumROISize=10`, eligibility applied after provider transform and before preprocessing, and state definitions `0`, `1–9`, and `>=10` voxels. Registered P3B train, validation, and combined state hashes are respectively `4981f5b2785b8f223d42a69a41567b4175d819f47b9566f92def1ac0f22f4c05`, `84af0be99d65e12e5aedca20b688c9c00ca06ac4de6fa13bd1f7cb44447cc8b7`, and `3073fab85237e3a637bbfdc34244e91014d761f1ba57f947f0060d005ce66d99`.

Provider binding passed: `AOnlyFoldFeatureProvider`, full-outer-training-only fit, validation IDs excluded from fitting, fold-specific habitat enabled, and the registered training-derived boundary representation preserved. W04, W07A, technical-freeze, W07/W08 configuration, candidate-pool, R6-4A, and R6-5R evidence hashes are recorded in the JSON companion.

The historical R6-2 diagnostic runner remains `historical_diagnostic_runner_not_exactly_recoverable`; no exact historical replay is claimed. The old solver source itself is recoverable from commit `899cf71e1895985f1f2eb5daf482d1c595dad154`.

## Solver lock

- Elastic-Net `max_iter=3000`; tolerance `1e-7`.
- Alpha grid `[0.1, 0.5, 0.9, 1.0]` unchanged.
- Lambda grid remains 100 log-spaced values per alpha from training-only `lambda_max` to `lambda_max*1e-4`; selection remains inner-CV-only with the registered tie-break.
- Objective, gradient, convergence criteria, zero-start behavior, penalty semantics, candidate order/pool, W07 split, population rules, and `minimumROISize=10` are unchanged.

## Synthetic direct-fit numerical equivalence

The old solver from the R6-0 baseline commit and the current solver with the R6-4A budget were compared on deterministic, outcome-free synthetic fixtures.

| Check | Old | New | Result |
|---|---:|---:|---|
| Direct-fit budget | 250 | 3000 | pass |
| Direct-fit iterations | 6 | 6 | pass |
| Objective | 2.6673510312306403 | 2.6673510312306403 | pass |
| Maximum coefficient delta | — | 0.0 | pass |
| Maximum synthetic risk-score delta | — | 0.0 | pass |

Coefficient and synthetic risk-score vectors have identical SHA-256 digests between old and new implementations. Synthetic risk scores were used only for implementation comparison and are not formal predictions or performance results.

## 100-point selection equivalence

Selection equivalence was tested without calling `tune_elastic_net`, fitting candidate models, generating risk values, or executing any scoring function. A deterministic in-memory fixture contained 400 candidate records: four frozen alpha values and 100 log-spaced lambda ratios for every alpha. Each record carried a preassigned `selection_score` utility; no outcome, risk, or performance quantity was used to create it.

The old and current `_select_candidate` source bodies were loaded separately and executed in memory after replacing the historical score-field token with `selection_score`. The fixture explicitly verified 100 values per alpha, ratios from `1.0` to `1e-4`, logarithmic spacing, complete indices `0..99`, and the index-to-ratio mapping. The tied utility records at lambda indices 37 and 42 exercised the registered tie-break: larger lambda ratio first, then smaller alpha index.

| Selection output | Old solver | R6-4A solver | Result |
|---|---:|---:|---|
| Selected alpha | 0.1 | 0.1 | pass |
| Selected alpha index | 0 | 0 | pass |
| Selected lambda index | 37 | 37 | pass |
| Selected lambda ratio | `0.031992671377973826` | `0.031992671377973826` | pass |

This is evidence for the selection reducer, grid semantics, and tie-break only; it does not claim 100 solver fits or cross-validation score generation.

## Preserved R6-4A stress evidence

The accepted R6-4A stress evidence is preserved without rewriting: 16/16 stress fits converged, 0 failed, and the maximum observed iteration count was 1814 under the uniform 3000-iteration budget. No fold/model-specific budget, candidate deletion, candidate skipping, warm start, or scientific-parameter change was introduced.

## Regression

| Suite | Tests | Failures | Errors | Skips | Exit |
|---|---:|---:|---:|---:|---:|
| Compileall | — | 0 | 0 | 0 | 0 |
| R6-4A/W08 targeted plus R6-5 | 81 | 0 | 0 | 0 | 0 |
| W07, B-blinding, A-access binding/negative tests | 37 | 0 | 0 | 0 | 0 |

The existing provenance reconciliation suite was also run and remains non-clean for pre-existing reasons: 32 tests, 1 existing failure, 7 existing errors, 0 skips. All errors report the existing `manifest.successor_revision_history.pre_w08_sop[1]` snapshot mismatch; the failure is the existing `execution_status` wording assertion. The combined W07/modeling/B/access run similarly had 44 tests with 1 error at the same existing snapshot mismatch. No R6-5 evidence or scientific, technical, statistical, or modeling binding file was changed to bypass these findings.

Environment: Python 3.7.12, NumPy 1.21.6, pandas 1.3.5, SciPy 1.7.3, scikit-learn 1.0.2, PyRadiomics v3.0.1, SimpleITK 2.2.1.

## Stage boundary

`B_data_read=false`, `B_reader_invoked=false`, `B_source_opened=false`, and `B_statistics_generated=false`. No real A-side outer-final Cox fit, formal W08 rerun, formal prediction/risk score, performance metric, model comparison, model-freeze lock, R6-6, or R6-6.5 was started. Temporary probe files were removed. The only new worktree files are this audit, its JSON companion, and `tests/test_r6_5_validation.py`; no commit or push was performed.
