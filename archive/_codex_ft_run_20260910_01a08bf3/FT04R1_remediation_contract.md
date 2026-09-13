# FT04 first-review remediation Worker contract

## Role and isolation

You are a new independent top-level Worker for FT04 remediation only.

- Required model: `gpt-5.6-luna`.
- Required reasoning: `xhigh`.
- This current conversation is already the authorized Worker. Do not create/open/spawn/delegate/request any additional conversation, session, thread, Worker, Reviewer, subagent, child/nested/delegated/internal agent, or equivalent agent feature.
- Complete the remediation inside this conversation. If impossible without delegation, stop and return the blocker.
- Do not act as Reviewer or Orchestrator. Do not start FT05A or any later module.
- Do not provide progress updates; return only the final result. If work exceeds one hour, one hourly status is permitted.

## Authoritative inputs

Read and obey:

- `AGENTS.md`.
- `T2WI-HS 生境预后快速验证（FT）方案书.md`.
- `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`.
- Accepted FT00–FT03 records.
- Original FT04 contract: `_codex_ft_run_20260910_01a08bf3/FT04_contract.md`.
- FT04 implementation commit `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`.
- First review record `prognosis_analysis/ft/FT04_review.md` and commit `971ea04f00f9f76d45cb609211fc3fe8a3c42dab`.
- Current FT04 runner, lock, audit, tests, and local model-state artifacts.
- `environment.yml` and `tools/run_t2_radiomics.ps1`.

The first review disposition is `not accepted for downstream use`. Implement only its four blocking remediations and necessary tests/audit updates. Preserve all accepted model fits and local model-state artifacts unless a demonstrated correctness issue requires regeneration. Do not alter scientific model definitions, populations, lambda results, coefficients, preprocessing, risk formulas, cutoffs, or baseline-survival state merely to remediate contract/provenance validation.

The pre-existing FT01 manifest working-tree indication and orchestration control directory are outside scope. Do not stage, normalize, revert, or commit them.

## Required remediation

1. **Canonical FT05B unlock artifact**
   - Change the frozen production contract to require exactly `prognosis_analysis/ft/FT_B_unlock.json`, matching the authoritative FT scheme.
   - Reject alternate filenames/paths, including the prior `FT05B_outcome_unlock.json` name.
   - Add positive and negative regression coverage for the exact canonical path.

2. **Git binding that is technically valid and verifiable**
   - Replace the incorrect FT03 `provenance.code_commit` binding.
   - The final FT04 provenance design must bind the reviewed FT04 runner/code and lock to observable Git history without asserting an impossible self-referential commit hash.
   - Use an explicit non-circular representation: distinguish the immutable implementation/source commit from the commit that records the final lock/review attestation. Validate referenced commits with Git and validate the exact current runner/lock content by file/blob SHA-256. The audit must state precisely which commit contains which version and must not claim that a commit contains itself.
   - At minimum, every referenced commit must resolve, be an ancestor of the current branch, and contain the named FT04 files expected by its declared role; current file hashes must match the lock/audit bindings.

3. **Fail-closed downstream prerequisite validation**
   - Production B prediction must require an accepted independent FT04 review record at its canonical path and validate its accepted disposition plus binding to the current FT04 lock/code identity.
   - It must use the canonical `FT05_B_feature_manifest.json` path rather than any caller-selected path.
   - Validate the complete FT05A freeze contract needed before B prediction: feature-table completeness and hash, patient uniqueness, no duplicate extraction, exact R_low/R_high names/order/count/candidate hashes, W_Original reuse/order/hash, frozen A-full boundary identity, identical A/W03 PyRadiomics configuration/provenance, no B K-means fit, outcome-blind generation, one-time first extraction, no formal-directory mixing, and accepted FT05A technical/code review status where prescribed.
   - Require the canonical FT05B unlock artifact only when outcome access/evaluation is requested; prediction-only feature loading must still require the accepted FT04 and complete canonical FT05A feature freeze.
   - Reject missing, forged, incomplete, alternate-path, non-accepted, hash-mismatched, duplicate, or provenance-inconsistent prerequisites.
   - Do not create real FT05A/FT05B artifacts in this remediation. Tests must use synthetic temporary fixtures only.

4. **Candidate-list hashes**
   - Add the canonical R_low and R_high candidate-list hashes to `FT_model_freeze_lock.json` using the accepted upstream values:
     - R_low: `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`.
     - R_high: `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`.
   - Validate these hashes when validating the FT04 lock and future FT05A manifest.

5. **Regeneration and tests**
   - Regenerate only the FT04 lock/audit and directly affected FT04 code/tests.
   - Preserve B locked, the formal model lock absent, and FT05A/later modules unexecuted.
   - Run the FT04 plus FT03/FT02/W07 suites through the wrapper. Add focused negative tests covering all four remediation areas.

## Environment and data boundary

- Every Python execution must use `tools/run_t2_radiomics.ps1` with the repository `environment.yml` environment `t2_radiomics`. Do not call another Python directly.
- Do not read any B source, feature, clinical, outcome, image, ROI, distribution, or performance data.
- Do not expose patient identifiers, patient-level values, private absolute paths, or sensitive outputs in tracked artifacts or responses.
- If any operation is expected to exceed 40 minutes, estimate it first and obey the project monitoring rule.

## Authorized writes and version control

Modify only directly necessary FT04 runner/predictor code, `FT_model_freeze_lock.json`, `FT04_refit_and_freeze_audit.md`, and FT04 tests. Local model-state files may be read/validated but should not be regenerated unless required by a demonstrated inconsistency.

Stage only FT04 remediation files, inspect the staged diff for scope/privacy/paths/large files, and create a local commit on `codex/ft-validation`. Do not push. The Orchestrator will attempt accumulated push only after FT04 is independently accepted.

## Completion criteria and final response

Return only whether all four blocking findings are remediated, exact wrapper test results, lock/code/audit validation status, preservation of model-state hashes and B/formal locks, local commit hash, confirmation that no push was attempted, and any blocker. Do not begin FT05A.
