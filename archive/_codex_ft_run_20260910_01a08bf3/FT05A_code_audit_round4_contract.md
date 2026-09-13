# FT05A Pre-run Code Reviewer Contract — Round 4

## Role and isolation

- Act as the independent fourth-round FT05A pre-run code Reviewer using `gpt-5.6-sol` with medium reasoning.
- This is a fresh top-level leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Review only; do not repair, access real B, run FT05A, or perform later modules.
- Do not report progress. Return only after review and local report-only commit, unless runtime exceeds one hour.

## Sources, environment, and privacy

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all FT05A contracts/audits, current code/tests, and remediation commit `c8682c4`.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static inspection and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Review scope

Independently reassess the complete FT05A pre-run gate. In particular, reproduce/adversarially assess:

- independent binding of `W_Original` to accepted FT01/FT04 path, SHA-256, order, schema, and row provenance, with no manifest self-authorization;
- one-to-one persisted mappings for image path, ROI path, source keys/hashes, case identity and patient identity;
- fail-closed audit binding, preflight-before-B-read, exact roots, finalization recovery, artifact/table/manifest binding, pilot selected-source reads and resume, structural absence/small ROI, duplicate/concurrency prevention, technical-only schema, outcome isolation, frozen A boundary, no B fit, unchanged PyRadiomics, and accepted-state regression.

## Verdict and deliverable

- Use exactly `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`; only the first two authorize the real-B execution Worker.
- If not `PASS`, record concrete findings; do not repair.
- Replace/update `prognosis_analysis/ft/FT05A_code_audit.md` with round-4 evidence and verdict. It must remain deidentified and contain no local absolute paths or patient-level data.
- Commit only the canonical report locally. Do not push or stage unrelated files, local outputs, control-store files, or `prognosis_analysis/ft/FT01_asset_manifest.json`.

## Completion criteria

Complete only when independent wrapper-based review is complete, privacy boundaries are preserved, the verdict is explicit, and the report-only local commit exists.
