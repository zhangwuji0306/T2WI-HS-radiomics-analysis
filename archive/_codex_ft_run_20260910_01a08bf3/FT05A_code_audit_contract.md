# FT05A Pre-run Code Reviewer Contract

## Role and isolation

- Act as the independent, top-level FT05A pre-run code Reviewer using `gpt-5.6-sol` with medium reasoning.
- This is a leaf task. You MUST NOT create, fork, delegate to, or otherwise start any session, thread, subagent, descendant, Worker, or Reviewer.
- Review only. Do not repair code, alter implementation, run real-B processing, or perform FT05B work.
- Do not report progress. Return only after the review and commit are complete, unless runtime exceeds one hour.

## Required sources

Read and follow:

- repository `AGENTS.md` and all applicable project instructions;
- `T2WI-HS 生境预后快速验证（FT）方案书.md` and its applicable amendment(s);
- accepted FT00–FT04 records, especially the canonical FT04 review, lock, digests, and code;
- `_codex_ft_run_20260910_01a08bf3/FT05A_code_prep_contract.md`;
- commit `7ddc4458f11fd631173e3778bd2a1ac518f74143`;
- `prognosis_analysis/ft/ft05a_runner.py` and `tests/test_ft05a_runner.py`.

## Environment and privacy boundary

- Any Python invocation MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`; do not invoke Python directly.
- Perform static inspection and synthetic tests only.
- Do NOT enumerate, locate, read, hash, copy, or write real B images, ROIs, features, clinical data, outcomes, identifiers, or manifests derived from real B assets.
- Do not open any B outcome source under any name. Do not generate the real FT05 feature manifest.

## Mandatory audit checks

Determine whether the implementation guarantees all of the following before any real-B access:

1. The frozen A-full habitat boundary is used exactly.
2. No K-means or other habitat-boundary fitting occurs on B.
3. No B outcome is read or made available to the runner.
4. The frozen PyRadiomics configuration is unchanged.
5. Unnecessary whole-tumour extraction is prohibited and `W_Original` reuse is exact.
6. Duplicate patients and duplicate extractions are rejected.
7. Checkpoint/resume never recomputes completed cases, including pilot cases.
8. Formal-analysis directories cannot be read from or mixed into the FT run.

Also verify:

- accepted FT04 review and lock validity are hard prerequisites to B access;
- one-time run-state semantics, atomic finalization, and explicit failure behaviour;
- canonical output and manifest schemas;
- candidate/order hashes and whole-tumour binding;
- outcome denylist and path allowlist enforcement;
- pilot cases become part of the canonical run and cannot be recomputed;
- the existing FT04 test-state mismatch reported by the Worker, and whether it materially blocks FT05A.

## Verdict and remediation

- Use exactly one verdict: `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`.
- Only `PASS` or `PASS_WITH_FINDINGS` authorizes the later execution Worker to access real B technical assets.
- Because this is the first Reviewer for this streaming module, if the verdict is anything other than `PASS`, provide a concrete remediation plan strictly limited to the FT05A code-preparation/pre-run gate. Do not implement it.

## Deliverable and Git scope

- Write the canonical tracked report `prognosis_analysis/ft/FT05A_code_audit.md`.
- The report must be deidentified, must contain no patient-level rows or local absolute paths, and must state the evidence, findings, verdict, and (when required) limited remediation plan.
- Commit only `prognosis_analysis/ft/FT05A_code_audit.md` locally. Do not push.
- Do not modify or stage unrelated files, the ephemeral control store, local output, or the pre-existing stat-only `prognosis_analysis/ft/FT01_asset_manifest.json` worktree entry.

## Completion criteria

Complete only when the canonical report exists, the verdict is explicit, relevant synthetic/static checks have been performed through the required wrapper, privacy boundaries were preserved, and the report-only local commit has been created.
