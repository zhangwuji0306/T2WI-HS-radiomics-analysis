# FT05A Code Remediation Worker — Round 5

## Role and isolation

- You are the fresh, independent top-level Worker for the existing FT05A pre-run code-gate remediation unit, using `gpt-5.6-luna` with xhigh reasoning.
- You are already the Worker for this unit. You MUST NOT create, open, fork, spawn, delegate to, request, or invoke any additional conversation, session, thread, subagent, child agent, nested agent, delegated agent, internal agent, Worker, Reviewer, or equivalent descendant.
- Do not further decompose or delegate this unit. Complete all work inside this conversation; if impossible without delegation, stop and return the blocker.
- Do not act as Reviewer or Orchestrator.
- Do not report progress. Return only after implementation, verification, and local commit are complete, unless runtime exceeds one hour.

## Current authoritative state

- The pasted external opinion was based on obsolete HEAD `6d30aeccdd2c606098a0e3a7abe9effbd670d285` and MUST NOT be used to redo FT03 or FT04.
- Current accepted facts are authoritative: `prognosis_analysis/ft/FT03_review.md` accepts FT03; `prognosis_analysis/ft/FT04_review.md` accepts FT04; `FT_model_freeze_lock.json` is frozen and validates; current branch includes the FT05A runner and its canonical fifth-round audit.
- Read repository `AGENTS.md`, the FT scheme/amendments, accepted FT03/FT04 artifacts, all relevant FT05A contracts/audits, current code/tests, and `prognosis_analysis/ft/FT05A_code_audit.md` at commit `49e840f325bf241dce40003fde96a80dbbe8fc12`.

## Environment and privacy boundary

- Every Python invocation MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`; never invoke Python directly.
- Use static inspection and synthetic fixtures only.
- Do NOT enumerate, locate, read, hash, copy, or write real B images, ROIs, W_Original rows, technical features, identifiers, clinical data, outcomes, or real FT05 manifests.
- Do not execute real FT05A or any FT05B/FT06 work.

## Authorized remediation only

Close the single confirmed fifth-round blocking finding:

- The FT05A production interface must accept only the one literal, absolute, canonical output-root spelling defined by the project.
- Reject before ownership creation, state creation, source loading, hashing, or extraction every relative path, `.` segment, `..`-normalized spelling, trailing-dot/space variant where applicable, slash-form variant if noncanonical, case variant, descendant, parent, symlink/junction/reparse alias, and any other caller spelling that is not exactly the canonical root.
- Retain resolved-path/reparse checks so lexical exactness does not weaken junction/symlink escape protection.
- Ensure all accepted calls derive owner/state/artifact/staging/table/manifest paths from the internal canonical constant, never from caller-controlled path text.
- Add adversarial synthetic tests proving each available alias class fails before any processor, W_Original loader, cohort/source reader, owner/state writer, or output creation is invoked.
- Update any prior test that intentionally accepted lexical aliases so it now enforces rejection.
- Preserve all previously accepted FT05A controls and technical-only semantics. Do not broaden scope or change scientific definitions.

## Verification and Git

- Run focused FT05A tests, relevant FT04+FT05A tests, accepted-state regression, FT05A static validation, and FT04 lock validation through the wrapper.
- A Windows symlink test may be skipped only for an actual privilege limitation; retain non-privileged junction/reparse and lexical adversarial evidence.
- Modify only the FT05A implementation/tests necessary for this blocker. Do not edit the canonical Reviewer report.
- Commit scoped project-safe code/tests locally. Do not push; the Orchestrator controls integration and push timing.
- Do not stage or alter unrelated files, local output, the ephemeral control store, or the pre-existing `prognosis_analysis/ft/FT01_asset_manifest.json` worktree entry.

## Completion criteria

Complete only when every available non-exact spelling fails closed before any B-technical side effect, all relevant wrapper regressions pass, FT04 remains `VALID`, no real B asset was touched, and a scoped local commit exists.
