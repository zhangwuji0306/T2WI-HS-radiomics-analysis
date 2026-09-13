# R6-5R W08 source binding refresh audit

## Disposition

`PASS` — the R6-5R coordinate provenance register matches the current W08
configuration and source files after the L5 execution-layer remediation. The
refresh is limited to SHA-256 source/configuration registrations; no
scientific parameter, population, solver, outcome, B-side, formal-output,
model-freeze, or W09 binding was changed.

## Current source/configuration bindings

| Path | SHA-256 |
|---|---|
| `prognosis_analysis/configs/w08_nested_cv.json` | `3e218f98b1397ef0e2615ca0556e605f91c730b5a7a30e263ada31bf34c89ef4` |
| `prognosis_analysis/scripts/w08_formal_run_a.py` | `44d6f4ec4b8253a6d86860c3678e43a5e10931413c50b0a8b05ebf795a333074` |
| `prognosis_analysis/scripts/w08_nested_cv.py` | `85644f4ec772ae22bccade96a3f0b5041fe021a72cefb04210bd725c7245329d` |

The registered values were recomputed from the current files. The W08 config
now explicitly binds the coordinator policy that each successfully validated
fold is atomically checkpointed before progress is emitted.

## L5 remediation evidence

- Thread caps are configured before importing NumPy, scikit-learn, or the
  downstream scientific stack. The locked environment reports one thread for
  each loaded BLAS/OpenMP pool after importing `w08_nested_cv`.
- The coordinator validates and atomically writes each independent fold
  checkpoint as soon as that fold succeeds. A later worker failure preserves
  already written valid checkpoints for same-attempt recovery.
- Checkpoint resume remains fail-closed for attempt, code, split, protocol,
  environment, result digest, row coverage, and result-count mismatches.
- Progress is emitted only after the corresponding new checkpoint has been
  atomically replaced, while resumed progress reflects already validated
  checkpoints.

## Environment

All Python checks use `tools\\run_t2_radiomics.ps1` and the project-root
`environment.yml` `t2_radiomics` environment: Python 3.7.12, NumPy 1.21.6,
pandas 1.3.5, SciPy 1.7.3, scikit-learn 1.0.2, PyRadiomics 3.0.1,
SimpleITK 2.2.1, and PyWavelets 1.3.0.

## Verification

- Required locked regression group (L5 checkpoint/thread, W08 nested-CV,
  transactional outputs, formal release gate, technical preflight, L4, L3C,
  and R6-5): 121/121 passed.
- Full test discovery: 300 passed and one pre-existing failure in
  `test_provenance_reconciliation.ProvenanceReconciliationTests.test_execution_status_is_the_failed_w08_hold_state`,
  where the historical assertion still expects `minimum ROI` instead of the
  recorded external-interruption summary.
- Locked-environment `compileall` and `git diff --check`: passed.
- No patient-level artifact, absolute local path, credential, or patient
  identifier is present in the refreshed record.

The R6-5R stage remains B-blinded and the formal W08 gate remains `HOLD`.
