# FT05A Independent Pre-run Code Audit — Round 9

Independent review: true

Reviewed FT05A implementation commit: `030a2db2f5610da0f1dba9bd7ab4d42344979904`

FT05A runner SHA-256: `a7dd51838510d3989ac973a1007808ee1e751414b1490fae68f80c4d7efb60ef`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

## Scope and evidence

- Reviewed the repository instructions, FT scheme and approved amendment, accepted FT00–FT04 records and lock, all FT05A contracts and prior audits, the current FT05A runner and tests, and implementation commit `030a2db`.
- FT05A wrapper regression passed: 40 synthetic tests, 1 Windows symbolic-link privilege skip, 0 failures.
- FT04/FT03/FT02/W07 wrapper regression passed: 65 tests, 0 failures.
- FT04 freeze-lock synthetic regression passed: 6 tests, 0 failures.
- FT05A static validation returned `pass: true` with no findings for B clustering fit, outcome access, whole-tumour re-extraction, or formal-directory mixing.
- FT04 lock validation returned `VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- The migration implementation restricts identity differences to `code_audit_sha256`, validates the expected current audit record fields, rejects completed/frozen/non-resume states, uses an atomic state writer, and revalidates completed case artifacts, source records, processor results, flattened rows, schema, row hashes, and pilot keys before migration.
- Existing regressions continue to support the frozen FT04 prerequisite, exact canonical namespace, technical-source allowlist, outcome blindness, no B fitting, frozen A boundary, unchanged PyRadiomics configuration, W_Original order/candidate binding, source uniqueness, one-time ownership, finalization recovery, technical-only schema, and structural/small-ROI states.
- No real B image, ROI, W_Original value, technical feature, outcome, clinical/prognostic source, patient-level output, or real FT05A run artifact was read, hashed, changed, or generated during this review.

## Blocking findings

### 1. W_Original migration does not require whole-asset hash validation before state identity change

The migration callback validates completed cases by calling `_load_w_original_asset` with only the completed patient IDs. The selected-row loader intentionally does not hash the complete W_Original file. Consequently, a changed unselected W_Original row can leave the accepted asset hash in the run identity unchanged while the migration writes the new code-audit identity. An independent synthetic probe changed only an unselected row in a synthetic W_Original asset; the migration wrote `identity_migration` and returned a pilot-complete state even though the physical asset no longer matched the accepted hash. A later full resume may reject the asset, but the migration has already changed persistent run identity and can therefore not be treated as an all-or-nothing accepted continuation.

### 2. Status-specific pilot completion invariants are not enforced before migration

`_validate_run_state_structure` accepts a `PILOT_COMPLETE` state whose `pilot_case_keys` contains a valid cohort case while `completed_case_keys` and completed artifact hashes are empty. With no case files, the migration callback accepts and rewrites this state. An independent synthetic probe reproduced this migration of a structurally incomplete pilot state. A subsequent full continuation can process a case that the state claims was already part of a completed pilot, weakening the one-time completion and pilot ownership contract.

## Nonblocking platform finding

The synthetic directory-symlink test was skipped because the Windows account lacks symbolic-link privilege. This remains nonblocking: the available junction/reparse test and the lexical/resolved-path checks cover the same production namespace gate, and all other required synthetic regressions passed.

## FT05A-only remediation plan

1. Before writing a migrated state, validate the complete accepted W_Original asset bytes against the FT04-bound path and SHA-256, while retaining selected-row validation for each completed pilot artifact. No migration state write may occur if the whole asset, path, order, or row binding is inconsistent.
2. Add status-specific run-state invariants before migration. In particular, require `PILOT_COMPLETE` to have a valid completion timestamp, a nonempty pilot set, and exact equality between pilot keys and completed case keys/artifact hashes; reject any incomplete or semantically inconsistent resumable state without changing its bytes.
3. Add synthetic regressions for unselected W_Original tampering, rejected migration-state immutability, malformed pilot completion, and a valid full resume that verifies the new parser against pilot artifacts without recomputation or overwrite.

No FT05A execution or later FT module is authorized until this FT05A-only remediation is independently reviewed.

## Downstream authorization

No downstream authorization. The same-run FT05A resume is not authorized, and this audit does not authorize FT05B or FT06.
