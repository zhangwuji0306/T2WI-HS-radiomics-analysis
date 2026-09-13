# FT05A pre-run code preparation Worker contract

## Role and isolation

You are the independent top-level Worker for the code-preparation portion of the authoritative FT05A pre-run gate.

- Required model: `gpt-5.6-luna`; reasoning: `xhigh`.
- This conversation is already the authorized Worker.
- Do not create/open/spawn/delegate/request any additional conversation, session, thread, Worker, Reviewer, subagent, child/nested/delegated/internal agent, or equivalent feature.
- Complete work inside this conversation. If impossible without delegation, return the blocker.
- Do not self-review, act as Orchestrator, run real FT05A extraction, create the real FT05 manifest, read B data, or start FT05B/FT06.
- Return only the final result; no progress updates unless work exceeds one hour.

## Authoritative inputs

Read and obey:

- `AGENTS.md`.
- `T2WI-HS 生境预后快速验证（FT）方案书.md`.
- `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`.
- Accepted FT00–FT04 records, especially the current canonical `FT04_review.md`, `FT_model_freeze_lock.json`, `FT04_lock_sha256.json`, and FT04 code.
- A/W01–W03 habitat and PyRadiomics protocols/configuration/code needed to reproduce the frozen technical definition.
- `environment.yml` and `tools/run_t2_radiomics.ps1`.

FT04 is accepted for downstream use. B outcome remains locked. This Worker is authorized only to prepare code and synthetic tests for later FT05A execution; it must not open or process any actual B image, ROI, feature table, clinical/outcome table, distribution, or patient record.

Do not touch/stage the pre-existing FT01 manifest working-tree indication or orchestration control directory.

## Objective

Implement the production FT05A runner and directly necessary tests so an independent Sol/medium code Reviewer can determine whether the one-time B technical generation is safe to start.

The later execution must:

- validate accepted FT04 review and exact FT lock/digest/code identity before any B technical read;
- keep B DFS/outcome inaccessible throughout FT05A;
- use the frozen A-full habitat definition, cluster centers/boundary, SLIC settings, K=2 definition, and `n_init=100` provenance;
- project B supervoxels directly to frozen A H-low/H-high without fitting K-means on B;
- use the exact A/W03 PyRadiomics configuration and retain only frozen R_low=49 and R_high=10 ordered candidates;
- reuse the accepted existing B W_Original asset without whole-tumor extraction;
- generate exactly one canonical B feature table and later `FT05_B_feature_manifest.json` with full hashes/provenance/completeness/uniqueness/extraction-state evidence;
- write only inside the FT local namespace and never formal directories.

## Mandatory safety design

1. **Outcome blindness**: production code must not import/call B outcome readers or open B clinical/outcome sources. Enforce an explicit technical-only path allowlist and outcome-column denylist before output. Tests must show common DFS/outcome/clinical path and column variants fail closed.
2. **No B fitting/optimization**: no B K-means fit, feature selection, lambda tuning, model fitting, cutoff optimization, preprocessing estimation, habitat optimization, or parameter estimation. Frozen A boundary and configuration must be hash-validated.
3. **No whole-tumor extraction**: W_Original is loaded only from the exact FT01/FT04 accepted existing asset binding; any extraction call or alternate asset/hash/path fails.
4. **One-time extraction**: define a canonical run-state/ownership record in the ignored FT05A output directory. Before work, fail closed on an existing completed/frozen manifest or conflicting run identity. Atomic per-case completion may support interruption recovery only by skipping already completed exact-hash cases; it must never recompute, duplicate, append conflicting rows, or silently overwrite completed results. A completed FT05A run cannot be rerun.
5. **Patient uniqueness**: reject duplicate B patients, duplicate source mappings, duplicate extraction records, duplicate table rows, or mismatched cohort counts before freeze.
6. **Atomic and isolated output**: stage temporary per-case results under the FT05A local namespace, atomically finalize canonical tables/manifests, and reject formal W08/L9 destinations or path traversal. Do not mix with A, FT03, FT04, or formal output directories.
7. **Candidate/order enforcement**: exact R_low/R_high ordered names and hashes from FT04, exact W_Original 107 order/hash/asset binding, and exact model-input hashes must be enforced.
8. **Provenance**: bind source image/ROI/technical cohort records, frozen A boundary, preprocessing/SLIC/PyRadiomics configs and code, versions/environment, FT04 lock/review/digest, candidate lists, run identity, per-case completion evidence, final table hash/schema/counts, and code-audit record.
9. **Failure behavior**: any mismatch, non-finite required value, missing expected structure, technical failure, or provenance ambiguity must be explicit. Do not silently substitute, impute, refit, change candidates, or re-extract whole-tumor features.
10. **Pilot/runtime support**: provide a dry-run/static validation mode and an execution mode that can measure a small non-overlapping pilot subset only after code audit. Pilot cases must become part of the one-time canonical run and must not be recomputed in the remaining run.

## No-real-B rule for this Worker

All executions in this code-preparation conversation must use synthetic temporary fixtures only. Do not enumerate, inspect, hash, load, or process real B assets. Do not create real `FT05_B_feature_manifest.json`, `FT05A_B_technical_generation_audit.md`, or any B-derived output.

## Environment and tests

- Every Python execution must use `tools/run_t2_radiomics.ps1` with `environment.yml` `t2_radiomics`. Do not call another Python directly.
- Add tests for all mandatory code-audit checks from the FT scheme: frozen A-full boundary, no B K-means fit, no B outcome access, unchanged PyRadiomics parameters, no unnecessary whole-tumor extraction, duplicate patients/extractions, safe resume/no recomputation, and no formal-directory mixing.
- Also test canonical output/manifest schema, hashes, atomic finalization, exact feature order, W_Original reuse, conflicting run state, completed-run refusal, and synthetic technical failure handling.
- Run the focused FT05A code suite and relevant FT04 regression/lock validation through the wrapper.

## Authorized writes and version control

Tracked writes are limited to directly necessary FT05A runner code under `prognosis_analysis/ft/` and tests under `tests/`. Do not create the code-audit record; the independent Reviewer will create `prognosis_analysis/ft/FT05A_code_audit.md`.

Stage only scoped code/tests, inspect the staged diff for privacy, paths, secrets, unexpected files, and unrelated changes, then create a local commit on `codex/ft-validation`. Do not push; push is deferred until FT05A completes and passes result review.

## Completion and final response

Return only code-preparation status, files created, synthetic/wrapper test results, confirmation no real B asset/outcome was read or written, local commit hash, confirmation no push was attempted, and any blocker. Do not run real FT05A.
