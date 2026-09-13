# R6-5R superseding protocol-owner disposition review

## Disposition

`accepted for downstream use` — `R6-5R coordinate reconciliation accepted under superseding disposition`. The project state may be reduced to `HOLD — AUTHORIZED FOR R6-5 ONLY`. This acceptance does not establish R6-5 numerical or implementation equivalence and does not authorize R6-6/G3R, formal W08, R6-6.5, outer-final Cox fitting, prediction, performance evaluation, model freezing, or B access.

## Review basis and supersession

The protocol-owner disposition supplied for this review explicitly supersedes the earlier R6-5R I/II/III branch premise that required current canonical `288/68`. It defines the canonical production-equivalent population for `repeat=1`, `outer_fold=1`, `population=R_high` as `282/67`, while preserving all historical evidence and retaining the exact-runner recovery axis as `historical_diagnostic_runner_not_exactly_recoverable`. This is a governance correction to the branch premise, not a change to eligibility, cases, ROI threshold, provider semantics, scientific parameters, or modeling rules.

The first-round review remains preserved as the correct disposition under its then-authorized `288/68` premise. It is not treated as Reviewer error and was not overwritten.

## Independent findings

- The canonical production reconstruction starts from the frozen W07 outer train/validation sides `314/79`, fits `AOnlyFoldFeatureProvider` on the full outer training side only, transforms both sides, validates the P3B eight-field contract, and applies the existing `derive_fold_populations(..., R_high, require_p3b=True)` rule.
- R_high train states reconcile as `282 extractable + 21 structural absence + 11 technical-small-ROI = 314`; validation states reconcile as `67 + 7 + 5 = 79`. The canonical eligible population is therefore `282/67`.
- The evidence records both canonical eligible ID hashes: train `90b08549c4bd7204a8437ce5fb984af608ba019a0cc10e6d1124b9fbddaf41b1` and validation `148ac9faad72ba250b558246967b26adfe3c52f9ff09e07377e6c3bef374dd06`.
- The recorded P3B hashes are train `4981f5b2785b8f223d42a69a41567b4175d819f47b9566f92def1ac0f22f4c05`, validation `84af0be99d65e12e5aedca20b688c9c00ca06ac4de6fa13bd1f7cb44447cc8b7`, and combined `3073fab85237e3a637bbfdc34244e91014d761f1ba57f947f0060d005ce66d99`. The P3B state boundary remains `voxel_count == 0`, `1 <= voxel_count < 10`, and `voxel_count >= 10`; `minimumROISize=10` is unchanged.
- The frozen W07 split hash remains `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`. W07A, modeling protocol, candidate-pool, technical-freeze, provider, boundary, and eligibility bindings recorded by the evidence match the reviewed files.
- R6-2 remains an unchanged historical diagnostic record at `M3H/R_high`, `repeat=1`, `outer_fold=1`, with nominal `282/67`. Its audit and aggregate evidence hashes remain `6ac0226a6efa1fa374260658e4dc8bf30a602a50ebcb9054d5eb7ab739dd7796` and `3bea77bcfa4f55b3f27c0497fdfbb9a5f2742971de9f62afd07f1fbd02149f09`. No new ID hashes were written into R6-2, and neither exact nor byte-exact historical runner recovery is claimed.
- The prior local `288/68` observation is not used as canonical population truth, an R6-5 acceptance criterion, or a basis to modify W07, W07A, P3B, `minimumROISize=10`, R6-2, or eligibility. No canonical eligibility drift evidence was identified, so eligibility remediation is not indicated.
- The registered convergence-only change remains uniform Elastic-Net `max_iter=3000` with `tolerance=1e-7`. The objective, convergence criterion, zero-start behavior, candidate pools, alpha grid, lambda grid and selection, W07 split, provider semantics, boundary, P3B contract, and model-specific population rules remain bound and unchanged.
- Git review started from a clean worktree at commit `64fbf45f1605b67363815361564ee598349aeeb2`, synchronized with the reviewed `main` remote reference. The reviewed commit contains the R6-5R evidence, audit, preserved first-round review, and status bookkeeping; no uncommitted scientific, technical, statistical, or modeling change was present.

## Stage and safety boundary

- `B_data_read=false`, `B_reader_invoked=false`, `B_source_opened=false`, and `B_statistics_generated=false`.
- Formal W08 remains on `HOLD`; no R6-5R Cox fit, risk score, prediction, performance metric, or model-freeze lock was generated. The model-freeze lock remains absent.
- R6-5 is limited to numerical regression, implementation equivalence, and canonical coordinate/provenance validation using permitted deterministic fixtures, targeted regression, compilation checks, and A-only adapter smoke checks. It must not perform a real A-side M3H outer-final Cox fit.
- Completion of R6-5 requires a new independent review before R6-6/G3R. R6-6.5 remains prohibited until after an accepted G3R.
- The reviewed evidence and this report contain only aggregate, de-identified, and provenance information; no patient-level identifiers, original image identifiers, B data, or absolute local data paths are included.

## Authorized consequence

R6-5R is accepted under the superseding protocol-owner disposition. The only authorized next execution stage is R6-5 under the canonical `282/67` eligible-ID hashes and unchanged W07/W07A, provider, boundary, P3B, candidate-pool, alpha/lambda, objective, convergence, `tolerance=1e-7`, `max_iter=3000`, and B-lock bindings.
