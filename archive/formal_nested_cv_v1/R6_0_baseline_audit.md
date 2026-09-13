# R6-0 baseline audit

## Baseline status

R6-0 baseline established at remediation-start commit `21492ef4b8aaf488355c648d953c02070b9acd45` on `main`. At baseline creation, `HEAD` and `origin/main` were identical and the working tree was clean.

The failed formal W08 code commit is `fdd0ce0f779fb10555465a4d040f6e390969f541`. The formal run failed closed in `nested_cv_modeling` with `W08NumericalFailure: Elastic-Net Cox fit did not converge`. The required 50/50 outer-validation completion was not achieved.

The original failed-run identifier is `attempt_1788647247630504_d8ea5057fc8b`; its failed archive identifier is `attempt_1788647247630504_d8ea5057fc8b_failed`, at `prognosis_analysis/output/w08_formal_A/attempts/attempt_1788647247630504_d8ea5057fc8b_failed`. The archive-internal metadata retains the original identifier.

## Git and frozen provenance

| Binding | Path | SHA-256 | Git blob | Blob at failed commit |
|---|---|---|---|---|
| W04 modeling protocol | `prognosis_analysis/modeling_protocol.json` | `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe` | `5c0219564415d6033672b27e1e61b0a537e5c6fa` | same |
| W07 outer-split config | `prognosis_analysis/configs/w07_outer_splits.json` | `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217` | `8497f8a6724ebe69dd8d8cdc293caf1ab730ff23` | same |
| W07 outer-split artifact | `prognosis_analysis/output/outer_splits_A.csv` | `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` | `3abc0b1deaa04bbce19c959ce4d7259420725599` | recorded artifact |
| W07A amendment JSON | `prognosis_analysis/W07A_pre_W08_protocol_amendment.json` | `0ca857a7b22c5b948c675f9970cc07b5a908c3f486be3f5656c86e20b5479f14` | `25d4b0a326ebfe61f9974e4c29c71a031e9a6f99` | same |
| W07A locked protocol | `prognosis_analysis/W07A_pre_W08_protocol_amendment.md` | `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70` | `d5dedd9530126fcfab327efed1278811c5fabea7` | same |
| W08 nested-CV config | `prognosis_analysis/configs/w08_nested_cv.json` | `f432b9741071a37be37fb63361e2007978ee6f47d4ce269b36a8692aa4fcbe7a` | `4da0a6acc1047f7e7767b27d706ab8a0ff476085` | same |
| Current solver code | `prognosis_analysis/scripts/w08_nested_cv.py` | `7bee63c3bd81df96b240dd24ef4af07228c6a6d8031174efa288974df2436259` | `075fe9624d8b8130f31016cd488d926feff3486c` | same |

The W08 configuration embeds the recorded W04, W07 artifact, and W07A locked-protocol hashes. No W03/W04/W07/W07A scientific input, W08 configuration, or solver-code change exists between the failed commit and the remediation-start commit; the intervening changes are limited to project/status and failure-audit records.

## Failure archive integrity

Both failed attempts are present under `prognosis_analysis/output/w08_formal_A/attempts/`.

| Archive | State | Inventory | Metadata evidence |
|---|---|---:|---|
| `attempt_001_failed` | preserved historical failed attempt; failure stage `nested_cv_modeling_radiomics_extraction` | 398 files, 5,820,718 bytes, 393 `.npz` cache files | `failure_audit_invalid_original.json`, `failure_audit.json`, `formal_stderr.log`, `formal_stdout.log`, and `run_state.json` are present and hashed in `R6_remediation_baseline.json`; the empty `formal_stdout.log` has SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `attempt_1788647247630504_d8ea5057fc8b_failed` | current formal W08 failed attempt; failure stage `nested_cv_modeling` | 396 files, 5,818,107 bytes, 393 `.npz` cache files | `attempt_state.json`, `failure_audit.json`, and `run_state.json` are present and hashed in `R6_remediation_baseline.json`; metadata matches the execution-status failure commit, type, stage, and B flags |

`attempt_001_failed` was neither renamed nor deleted. No final W08 output, held-out prediction, or model-freeze artifact is treated as available.

## Access and stage boundary

| Item | Baseline state |
|---|---|
| `B_data_read` | `false` |
| `B_reader_invoked` | `false` |
| `B_source_opened` | `false` |
| `B_statistics_generated` | `false` |
| `prognosis_analysis/model_freeze_lock.json` | absent |
| Formal W08 final outputs | absent |
| Held-out predictions | absent |
| W09 execution/metrics/performance | not executed |

No B file, B patient row/outcome/radiomics/distribution, performance calculation, solver patch, diagnostic replay, or formal W08 rerun was performed for this baseline.

## Verification commands

The baseline was verified with the following read-only checks:

```text
git status --short --branch
git rev-parse HEAD
git rev-parse origin/main
git show -s --format='%H%n%P%n%s' fdd0ce0f779fb10555465a4d040f6e390969f541
git diff --name-status fdd0ce0f779fb10555465a4d040f6e390969f541..HEAD
git rev-parse <commit>:<path> for locked inputs and solver
Get-FileHash -Algorithm SHA256 for locked inputs, solver, and archive metadata
Get-ChildItem -Recurse for failure-archive inventory
Test-Path for model_freeze_lock.json and named W08/W09 final artifacts
```

The machine-readable record is `prognosis_analysis/R6_remediation_baseline.json`.
