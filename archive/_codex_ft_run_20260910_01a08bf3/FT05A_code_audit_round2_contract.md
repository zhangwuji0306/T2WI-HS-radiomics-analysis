# FT05A Pre-run Code Reviewer Contract — Round 2

## Role and isolation

- Act as the independent second-round FT05A pre-run code Reviewer using `gpt-5.6-luna` with xhigh reasoning.
- This is a fresh top-level leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Review only. Do not repair code, run real-B processing, or perform FT05B/later work.
- Do not report progress. Return only after review and local commit are complete, unless runtime exceeds one hour.

## Sources and environment

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, both prior FT05A contracts, `prognosis_analysis/ft/FT05A_code_audit.md`, remediation commit `35f873a`, and current FT05A/FT04 code and tests.
- Any Python invocation MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static inspection and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write any real B asset, identifier, clinical data, outcome, or real FT05 manifest.

## Review scope

Independently verify that all first-round blockers are closed and that the implementation fail-closes before any B technical read:

1. Exact frozen A-full boundary; no B fitting; no B outcome access.
2. Code-audit binding to exact runner SHA-256, reviewed commit, and contract identity.
3. Fixed canonical FT05A roots and exact source-root contracts; rejection of formal/A/FT03/FT04/W08/L9 mixing.
4. Technical-only FT05A schema and a correct canonical downstream technical validator, with the clinical/outcome join deferred to its authorized stage.
5. Exclusive run ownership, atomic creation, duplicate prevention, artifact/input/W_Original/result/row/schema binding, tamper rejection, completed-run refusal, and safe interruption recovery.
6. Pilot reads/hashes only selected sources, remains in the one canonical run, and is never recomputed.
7. Frozen structural-absence and technical-small-ROI states, including PyRadiomics 3.0.1 minimum-size behavior, without imputation/substitution.
8. Recoverable atomic finalization and audit-before-final-output ordering.
9. Accepted-state combined regression, including the corrected FT04 stale test.

Also validate the original mandatory eight checks and ensure the FT04 lock/review/digest is a hard prerequisite.

## Verdict and deliverable

- Use exactly one verdict: `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`. Only the first two authorize a later execution Worker.
- If not `PASS`, state concrete findings; do not repair.
- Replace/update the canonical tracked report `prognosis_analysis/ft/FT05A_code_audit.md` with round-2 evidence and verdict. Keep it deidentified and free of local absolute paths or patient-level data.
- Commit only the canonical report locally. Do not push. Do not stage unrelated files, local output, control-store files, or `prognosis_analysis/ft/FT01_asset_manifest.json`.

## Completion criteria

Complete only when independent static/synthetic review is finished through the required wrapper, privacy boundaries are preserved, the explicit verdict is recorded, and the report-only local commit exists.
