# FT04 Worker contract

## Role and isolation

You are the independent top-level Worker for exactly one formal workflow unit: FT04.

- Required model: `gpt-5.6-luna`.
- Required reasoning: `xhigh`.
- You are already the independent Worker for this assigned unit.
- Do not create, open, spawn, delegate to, or request any additional conversation, session, or thread.
- Do not invoke any subagent, child agent, nested agent, delegated agent, internal agent, or equivalent agent-creation feature.
- Do not further decompose or delegate this unit. Complete it inside this conversation; if that is impossible, stop and return the blocker to the Orchestrator.
- Do not act as Orchestrator or Reviewer. Do not review your own work and do not start FT05A, FT05B, FT06, FT07, or any formal W08/L9 work.
- Do not provide progress updates. Return only a concise final result after the unit finishes. If execution exceeds one hour, an hourly status may be emitted, but do not otherwise narrate progress.

## Authoritative inputs and accepted prerequisites

Read and obey:

- `AGENTS.md`.
- `T2WI-HS 生境预后快速验证（FT）方案书.md`.
- `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`.
- `prognosis_analysis/ft/FT00_protocol.json` and `FT00_isolation_audit.md`.
- `prognosis_analysis/ft/FT01_asset_manifest.json` and `FT01_asset_audit.md`.
- `prognosis_analysis/ft/ft02_runner.py` and `FT02_technical_audit.md`.
- `prognosis_analysis/ft/ft03_runner.py`, `FT03_A_validation.json`, `FT03_A_validation_report.md`, and `FT03_review.md`.
- The repository `environment.yml` and `tools/run_t2_radiomics.ps1`.

FT00–FT03 are accepted upstream prerequisites. FT03 first-round disposition is `accepted for downstream use` in commit `d7f9e1e65f7e594999f3b5e0071455fe7563b2ad`, which is local but not yet on the remote because GitHub was unreachable. Preserve that commit and all accepted contracts.

A pre-existing stat-only/line-ending working-tree indication for `prognosis_analysis/ft/FT01_asset_manifest.json` and the orchestration control directory are outside FT04 scope. Do not modify, stage, normalize, revert, or commit them.

## Objective

Execute FT04 — Full_A Final Refit & Freeze — exactly as defined by the FT scheme.

Using the full authoritative A population applicable to each frozen model, refit all seven models (`M0`, `M1`, `M2`, `M3L`, `M3H`, `M4`, `M5`) and freeze everything needed for deterministic later B prediction and evaluation:

- cohort and eligibility definition;
- full_A habitat definition;
- predictor blocks and ordered feature names;
- preprocessing state and parameters;
- selected lambda for penalized models;
- coefficients and intercept/baseline-survival state required for risk and survival prediction;
- exact risk formula and feature transformations;
- a non-performance-optimized A-derived cutoff for later B KM grouping;
- endpoint and 36/60-month horizons;
- B prediction/evaluation code and its hash;
- code commit, environment fingerprint, source/artifact hashes, seeds, and model-state hashes.

Create and freeze the core artifact `prognosis_analysis/ft/FT_model_freeze_lock.json`. The FT lock must be unmistakably separate from and must never masquerade as the formal `prognosis_analysis/model_freeze_lock.json`.

## Frozen modeling rules

- A-only. Do not read, open, derive, inspect, or use any B source, feature, clinical, outcome, missingness, distribution, image, ROI, or performance data.
- Do not create a B feature manifest or unlock B access. FT05A may begin only after FT04 is independently accepted.
- Preserve the frozen W07 repeat-1 split, model set, predictor definitions, `alpha=1`, `R_low=49`, `R_high=10`, `W_Original=107`, candidate/order hashes, endpoint, horizons, and eligibility rules.
- Do not perform full-A DFS-based univariate screening, post-hoc feature changes, habitat changes, split regeneration, performance-based lambda/cutoff/model optimization, or removal of weak models.
- For each penalized model, select lambda using the already accepted ordinary training-only 5-fold rule on the model's complete eligible A fitting population. Do not use FT03 validation performance or any B information to choose lambda.
- For unpenalized models, retain the accepted Cox specification without tuning.
- If no more specific frozen cutoff rule is present in the authoritative FT records, use the median of that final model's full-A fitted linear predictor as the deterministic non-optimized cutoff. Record this operational rule before inspecting any B data; do not optimize it against survival separation or metrics.
- Freeze the baseline survival needed for 36- and 60-month survival predictions consistently with accepted FT02/FT03 semantics.

## B evaluation-code boundary

Implement or freeze only the code necessary to consume the FT04 model artifacts later. During FT04 it must be exercised only with synthetic/non-B fixtures.

The production B prediction path must fail closed unless the later FT-specific prerequisites exist and validate, including:

- accepted FT04 lock identity;
- frozen `FT05_B_feature_manifest.json` and its expected model-input hashes;
- FT05B outcome-unlock authorization for FT06 when outcomes are requested.

Prediction code must not fit a model, tune lambda, fit K-means, select features, optimize cutoff, estimate preprocessing on B, or re-extract radiomics. Do not create the future FT05/FT06 authorization artifacts during FT04.

## Environment and runtime rules

- Every Python execution—including probes, tests, timing runs, final refits, serialization, and synthetic B-predictor checks—must use `tools/run_t2_radiomics.ps1`, which resolves the repository `environment.yml` environment `t2_radiomics`. Do not call another Python environment directly.
- Before starting any script expected to exceed 40 minutes, estimate runtime from a small-sample measurement or relevant historical timing. Record the estimate in the aggregate FT04 audit without exposing patient identifiers.
- Obey `AGENTS.md` long-task monitoring rules. Do not poll or narrate progress. Only the Orchestrator may inspect at the allowed hourly schedule.
- Do not expose original imaging IDs, patient identifiers, source rows, dates, patient-level features/predictions, or private absolute paths in tracked artifacts, commands, commits, or final response.

## Authorized writes and destinations

Patient-derived fitted model objects, detailed preprocessing states, coefficient tables when treated as analysis outputs, and any per-patient or sensitive intermediate data must remain under an FT04-specific directory inside:

`prognosis_analysis/output/ft_20260910_01a08bf3/`

These local outputs must remain ignored and uncommitted. The tracked FT lock may bind them by repository-relative logical names and cryptographic hashes, while including only the minimum de-identified model metadata required by the project's established FT convention. Do not place local absolute paths in tracked files.

Tracked FT04 files may include only:

- `prognosis_analysis/ft/FT_model_freeze_lock.json`;
- `prognosis_analysis/ft/FT04_refit_and_freeze_audit.md`;
- directly necessary FT04/frozen-B-prediction code under `prognosis_analysis/ft/`;
- directly necessary FT04 tests under `tests/`.

Do not modify project status files, formal W08/L9 locks/outputs, earlier FT artifacts, or unrelated files.

## Required validation and completion evidence

1. Seven final A model states exist, are readable in `t2_radiomics`, have distinct stable hashes, and match the frozen model/population/feature contracts.
2. Penalized-model lambda selection uses only the full eligible A fitting population with the accepted inner five-fold rule and `alpha=1`; all fits converge under the accepted numerical budget without scientific-rule changes.
3. Preprocessing parameters are frozen and later prediction applies them without refitting.
4. Risk and 36/60-month survival predictions can be reproduced from the frozen state on synthetic or held-in consistency fixtures; the later B code is prediction-only and fail-closed before FT05A/FT05B prerequisites.
5. The cutoff rule is deterministic, A-only, non-optimized, and frozen separately for each model when model risk scales differ.
6. `FT_model_freeze_lock.json` is internally self-consistent, binds all required upstream files/code/environment/model artifacts, records B as locked, and cannot be confused with the formal lock.
7. Tests cover model serialization/reload, exact feature order, preprocessing replay, risk/survival equivalence, model-state hash tampering, FT-lock validation, missing/forged FT05 prerequisites, forbidden fit/tuning/extraction paths, B column/path rejection during FT04, and preservation of formal locks.
8. Run the directly relevant FT04 suite plus FT03/FT02/W07 regression suites through the wrapper. Keep runtime proportional, but do not omit tests needed to support the lock.
9. Tracked files contain no patient identifiers, patient-level values, sensitive paths, secrets, B data, or formal output contamination.
10. FT05A and all later modules remain unexecuted.

## Version control and deferred push policy

After successful validation, stage only FT04-scoped tracked files. Inspect the staged diff for identifiers, secrets, absolute paths, unexpected large files, and unrelated changes. Commit on `codex/ft-validation`.

Do not attempt to push from this Worker. The Orchestrator will perform one combined push attempt only after the FT04 Reviewer completes, covering the previously unpushed FT03 review commit and FT04 commits. A push failure is non-blocking for module execution under the user's explicit deferred-retry policy.

## Final response

Return only:

- whether FT04 completed;
- aggregate deliverables and local model-state count/hashes status;
- essential validation/test evidence and runtime-rule compliance;
- local commit hash;
- confirmation that no push was attempted;
- confirmation that B/formal locks stayed unchanged;
- any blocker.

Do not start FT05A.
