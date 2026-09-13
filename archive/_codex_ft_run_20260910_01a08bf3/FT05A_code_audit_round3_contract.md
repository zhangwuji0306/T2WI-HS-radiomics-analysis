# FT05A Pre-run Code Reviewer Contract — Round 3

## Role and isolation

- Act as the independent third-round FT05A pre-run code Reviewer using `gpt-5.6-luna` with xhigh reasoning.
- This is a fresh top-level leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Review only; do not repair, access real B, run FT05A, or perform later modules.
- Do not report progress. Return only after review and local report-only commit, unless runtime exceeds one hour.

## Sources, environment, and privacy

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all prior FT05A contracts and canonical audits, commits `35f873ac8333f4f8c0e8e770b87a79e36635d4da` and `d0c59b0`, and current FT05A/FT04 code/tests.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Use static inspection and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Review scope

Reassess the full FT05A pre-run gate, with adversarial focus on the four round-2 blockers:

1. `FINALIZING` recovery is constrained to canonical namespaces and revalidates table, manifest, bindings, completion evidence, W_Original, and transaction contents before completion.
2. The technical-manifest validator cryptographically and semantically validates exact roots, file/source hashes, case identity, ordering, table correspondence, and W_Original bindings, rejecting formal/disallowed provenance.
3. The canonical report-only audit commit remains valid while the audit is explicitly independent and bound to exact reviewed implementation commit, runner SHA-256, and contract; intervening code changes or forged/stale audits fail closed.
4. Pilot reads/hashes only selected technical sources including selected W_Original rows, yet later resume/finalization establishes exact whole-asset and row binding without recomputing pilot extraction.

Also revalidate the original mandatory eight checks, technical-only schema/downstream contract, one-time ownership/resume, structural absence/small-ROI behavior, outcome isolation, frozen A boundary, no B fitting, frozen PyRadiomics, and accepted-state regression.

## Verdict and deliverable

- Use exactly `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`; only the first two authorize real-B technical execution.
- If not `PASS`, record concrete findings but do not repair.
- Replace/update `prognosis_analysis/ft/FT05A_code_audit.md` with the round-3 evidence and verdict, deidentified and without local absolute paths or patient-level data.
- Commit only that canonical report locally; do not push or stage unrelated/local/control-store/FT01-manifest changes.

## Completion criteria

Complete only when independent wrapper-based static/synthetic review is complete, privacy boundaries are preserved, the verdict is explicit, and the report-only local commit exists.
