# FT03 Worker contract

## Role and isolation

You are the independent top-level Worker for exactly one formal workflow unit: FT03.

- Required model: `gpt-5.6-luna`.
- Required reasoning: `xhigh`.
- You are already the independent Worker for this assigned unit.
- Do not create, open, spawn, delegate to, or request any additional conversation, session, or thread.
- Do not invoke any subagent, child agent, nested agent, delegated agent, internal agent, or equivalent agent-creation feature.
- Do not further decompose or delegate this unit. Complete all work inside this conversation. If that is impossible, stop and return the blocker to the Orchestrator.
- Do not act as Orchestrator or Reviewer. Do not review your own work and do not start FT04 or any later module.
- Do not provide progress updates. Return only a concise final result after the unit finishes. If execution exceeds one hour, an hourly status may be emitted, but do not otherwise narrate progress.

## Authoritative inputs

Read and obey:

- `AGENTS.md`.
- `T2WI-HS 生境预后快速验证（FT）方案书.md`.
- `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`.
- `prognosis_analysis/ft/FT00_protocol.json` and `FT00_isolation_audit.md`.
- `prognosis_analysis/ft/FT01_asset_manifest.json` and `FT01_asset_audit.md`.
- `prognosis_analysis/ft/ft02_runner.py` and `FT02_technical_audit.md`.
- `PROJECT_STATUS.md` and `项目说明.md` only as project-state/context records.
- The repository `environment.yml` and `tools/run_t2_radiomics.ps1`.

FT00, FT01, and FT02 are accepted upstream prerequisites. Preserve their scientific and technical contracts. The current working branch is `codex/ft-validation`. A pre-existing stat-only/line-ending working-tree indication for `prognosis_analysis/ft/FT01_asset_manifest.json` is outside FT03 scope: do not modify, stage, normalize, revert, or include it in any commit.

## Objective

Execute FT03 — A Modeling & Internal Validation — exactly as defined by the FT scheme, using the accepted FT02 production runner and the frozen W07 repeat-1 ordinary 5-fold split.

Run all seven prespecified models: `M0`, `M1`, `M2`, `M3L`, `M3H`, `M4`, and `M5`. Produce cross-validated A-only predictions and all required aggregate validation results:

- Uno C-index and Harrell C-index;
- 3-year and 5-year AUC;
- 3-year and 5-year Brier score;
- calibration;
- KM;
- DCA;
- bootstrap 95% confidence intervals;
- the seven prespecified paired comparisons on their frozen common eligible populations.

The analysis label must be `exploratory_fullA_habitat_non_nested_validation`, and performance must be labeled `non_nested_exploratory_estimate`.

## Frozen constraints

- A-only. Do not read, open, derive, or use any B source, feature, clinical, outcome, missingness, distribution, image, ROI, or performance data.
- Do not create or modify any B-access record or model-freeze lock.
- Do not alter or regenerate the frozen W07 repeat-1 split.
- Do not perform post-hoc feature changes, full-A DFS-based univariate screening, lambda changes, model changes, habitat changes, or performance-informed reruns.
- High-dimensional models use Cox with `alpha=1`; lambda selection is training-only ordinary inner 5-fold CV as implemented in accepted FT02.
- `M5 = C + W_Original`, with exactly the frozen ordered 107 Original whole-tumor features and no Wavelet, LoG, or other filtered features.
- Preserve the frozen `R_low=49` and `R_high=10` candidates and hashes.
- Every paired comparison must use the common eligible population frozen in FT00/FT02.
- Do not alter formal W08/L9 artifacts, formal locks, formal outputs, or unrelated project resources.

## Environment and runtime rules

- Every Python execution, including probes, tests, dry runs, and the real FT03 run, must use `tools/run_t2_radiomics.ps1`, which resolves the repository `environment.yml` environment `t2_radiomics` (Python 3.7.12 and locked dependencies). Do not call another Python environment directly.
- Before starting any script expected to exceed 40 minutes, first estimate runtime from a small-sample measurement or relevant historical timing and record the estimate in the final aggregate report/audit without exposing patient identifiers.
- After launch, obey the project long-task monitoring rule. Do not poll output or report progress. Only the Orchestrator may check at the allowed schedule; the Worker should run to completion unless a genuine blocker occurs.
- Do not expose original imaging IDs, patient identifiers, source rows, clinical dates, patient-level features, patient-level predictions, or local private paths in tracked artifacts, command output, commits, or the final response.

## Authorized writes and destinations

The project-native output namespace is `prognosis_analysis/output/ft_20260910_01a08bf3/`. Store all patient-level predictions, fold-level records, bootstrap replicates, and other sensitive/local analysis output only under an FT03-specific subdirectory there. These files are local and must not be staged or committed.

Tracked deliverables may be created only when aggregate and de-identified:

- `prognosis_analysis/ft/FT03_A_validation.json`;
- `prognosis_analysis/ft/FT03_A_validation_report.md`;
- directly necessary FT03 runner code under `prognosis_analysis/ft/`;
- directly necessary FT03 tests under `tests/`.

Do not add orchestration contracts or the `_codex_ft_run_20260910_01a08bf3/` control store to Git.

## Required evidence and acceptance criteria

1. All seven models complete on the authoritative A-only inputs and frozen repeat-1 split.
2. Each patient receives only held-out-fold cross-validated prediction(s) for its eligible model/population; there is no training-fold leakage.
3. Metrics, calibration, KM, DCA, bootstrap 95% CIs, and paired comparisons follow the accepted FT02 hook semantics and the scheme horizons.
4. The report makes the eligible denominator/population explicit for each model and comparison using aggregate counts only.
5. Output provenance binds the FT00 protocol/amendment, FT01 asset manifest, FT02 runner, frozen W07 split, environment, code commit, seeds, model definitions, candidate/order hashes, and local output hashes as appropriate.
6. Tests cover the FT03 aggregation/output interfaces, paired-population enforcement, label/horizon semantics, duplicate/missing held-out prediction rejection, and B-path/column rejection. Run the directly relevant tests plus FT02/W07 regression suites through the wrapper.
7. Tracked JSON/Markdown contain no patient identifiers, patient-level values, B data, private source paths, or formal W08/L9 output.
8. The formal `prognosis_analysis/model_freeze_lock.json` and all B access flags remain unchanged/locked. FT04 is not executed.

## Version control

After successful validation, stage only FT03-scoped tracked files. Inspect the staged diff for identifiers, secrets, local absolute paths, unexpected large files, and unrelated changes. Commit on `codex/ft-validation` and push that branch. Do not include the pre-existing FT01 manifest working-tree indication or the control store. If push fails, retain the local commit and report the exact failure without claiming synchronization.

## Final response

Return only:

- whether FT03 completed;
- aggregate deliverables created;
- the essential aggregate result status and validation/test evidence;
- runtime and long-task-rule compliance;
- commit hash and push status;
- any blocker.

Do not start FT04 and do not include patient-level values or identifiers.
