# FT04 First-Round Review

## Disposition

`not accepted for downstream use`

## Evidence

- Commit under review: `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`; its scoped diff contains only the FT04 audit, FT-specific lock, runner, and tests. The accepted FT03 review commit `d7f9e1e65f7e594999f3b5e0071455fe7563b2ad` remains an ancestor.
- Seven ignored local model states exist and match the hashes in `FT_model_freeze_lock.json`. All source and input-source hashes validate. Reload checks in `t2_radiomics` reproduced each model's linear predictor exactly, reproduced each frozen median cutoff exactly, and produced finite 36/60-month survival probabilities in `[0,1]` with coefficient/feature counts and raw predictor order matching.
- Model populations and event totals match the accepted FT03 populations. M0, M1, and M2 are untuned Cox models; M3L, M3H, M4, and M5 use Cox with `alpha=1`, 20 lambda candidates, complete eligible-A inner five-fold selection, zero recorded candidate failures, and converged final fits.
- The lock records A-only scope, DFS, 36/60-month horizons, W07 repeat 1, `K=2`, `n_init=100`, `R_low=49`, `R_high=10`, `W_Original=107`, deterministic non-optimized median cutoffs, and B locked. No FT05-or-later artifact exists, the formal model lock remains absent, and no formal output differs from the pre-FT baseline.
- The FT04 commit contains no patient-level values, private absolute paths, credentials, B data, or unexpected large files. Local model states are ignored and uncommitted.

## Wrapper tests

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
47 tests run; 47 passed; 0 failed; exit code 0; 140.347 s

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; exit code 0
```

## Findings and downstream decision

Blocking findings:

1. The frozen B outcome-unlock contract names `prognosis_analysis/ft/FT05B_outcome_unlock.json`, while the authoritative FT scheme requires `prognosis_analysis/ft/FT_B_unlock.json`. The prediction code therefore cannot consume the prescribed FT05B deliverable without changing already-frozen code.
2. The lock records `provenance.code_commit` as the FT03 review commit `d7f9e1e65f7e594999f3b5e0071455fe7563b2ad`. That commit contains neither the FT04 runner nor the FT04 lock; the actual FT04 commit is `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`. The required code/lock commit binding is therefore incorrect.
3. The production B prediction boundary does not verify that FT04 has an accepted independent review. It also accepts a caller-selected manifest path and a minimal manifest containing only an artifact label, status, lock identity, and model-input hashes. This does not fail closed on the contract-required accepted FT04 gate and complete FT05A feature-freeze/provenance prerequisites.
4. `FT_model_freeze_lock.json` records the R-block counts but omits the frozen R_low and R_high candidate-list hashes required for later B feature compatibility checks. The hashes are present upstream but are not frozen or validated as part of the model lock.

Nonblocking findings: none.

FT04 is not accepted for downstream use. No later FT module is authorized.

## FT04-only remediation plan

1. Align the frozen outcome-unlock filename and artifact validation with the authoritative `FT_B_unlock.json` contract, then add a regression test using that exact prescribed artifact.
2. Reissue the FT04 lock so its commit binding resolves to a commit that actually contains the reviewed FT04 runner and lock; validate that binding against Git rather than only recording the current pre-commit HEAD.
3. Make the prediction boundary require the accepted FT04 review and the canonical FT05A manifest path, and validate the complete frozen-manifest contract needed for B prediction, including feature completeness/order, candidate hashes, radiomics provenance, and uniqueness/extraction-state evidence. Add negative tests for missing, forged, incomplete, alternate-path, and non-accepted prerequisites.
4. Add the canonical R_low and R_high candidate-list hashes to the FT04 lock and enforce them in lock and B-manifest validation.
5. Regenerate only the FT04 lock/audit and directly affected FT04 code/tests, rerun the FT04 plus FT03/FT02/W07 wrapper suites, and obtain a new independent FT04 review before downstream use.
