# W07A Pre-W08 Integrity Audit

## P4 decision

- Audit stage: `P4 — Post-freeze integrity verification`.
- Audit time: `2026-09-05T13:06:20+08:00`.
- Starting commit: `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`.
- Current commit: `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`.
- `origin/main` at verification: `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`.
- Overall P4 result: **FAIL / HOLD**.
- P5 implementation, G2R2, 50-fold P5, G3, and formal W08 remain unauthorized.

The core technical artifacts and their recorded hashes remain intact. P4 does
not pass because two frozen documentation provenance bindings no longer match
the current files: the W04 taskbook source revision and the W07A workflow
source provenance. No frozen asset was repaired or regenerated.

## Scope and access boundary

This audit used only outcome-blind technical metadata, JSON/Markdown protocol
content, file bytes, SHA-256 values, lock validation, and output-directory
metadata. The W06 population CSV and W06 source-audit artifact were hashed but
not parsed. No A clinical/outcome values, B source, B validation data, model
fit, prediction, performance metric, or patient-level result was read or
generated.

The pre-existing user-confirmed deletion of `组学分析方案.md` was preserved
and is outside this audit. The listed immutable artifacts had no working-tree
diff.

## Verification results

| Verification item | Result | Evidence |
|---|---|---|
| Original technical `freeze_lock.json` byte identity | **PASS** | Current SHA-256 `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262`, matching the recorded original hash; `validate_freeze_lock` passed all 14 required artifact-hash fields. |
| Original lock working-tree integrity | **PASS** | `git diff --quiet HEAD --` check over the immutable freeze, W04, W03, W07, W07A, and G2R artifacts returned no diff. |
| Technical freeze state | **PASS** | `A_outcome_unlock=true`, `B_unlock=false`, `outcome_columns_read=false`, `B_data_read=false`; addendum records `core_scientific_artifacts_match_original_lock=true`, `scientific_parameters_changed=false`, `technical_freeze_regenerated=false`, and `outcome_used_to_modify_technical_method=false`. |
| W04 protocol file and original-freeze relationship | **PASS** | `prognosis_analysis/modeling_protocol.json` SHA-256 `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`; its `technical_freeze` binding matches the current original lock SHA and schema `1.0`. |
| W04 source-revision closure | **FAIL / HOLD** | 19 source revisions were checked. 17 current-path entries match; the archived workflow content matches after resolving its documented archive location; the `taskbook` entry does not match. W04 records `0ba96334e37b5729356b947ffa41bd2d52649cc84f8d760ba4bbc51a129ffc3c`, while the current taskbook is `cc881c008629a1acc0a2b4e6570b4ef277faa27ed5c9f12f908ee947b42381dd`. |
| W03 candidate pools | **PASS** | Candidate-freeze file SHA-256 `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2`. Recomputed canonical candidate hashes: `R_low` count 49, `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`; `R_high` count 10, `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`. Both match W03 metadata, W04, W07A, and W08 bindings. |
| W06 population binding | **PASS** | W07 config and code-level lock agree with the current byte hashes of the W06 source, schema, and source-audit artifacts: `5c93441f535ba86d965c3da14b4b33fe52f73d4337cd15a670b3ca2b8a2c23e4`, `41f6a6ac69bc0727755817d1e3e6902e24c612c00d6c88f52c4c2f42904039c6`, and `0814082014600935922d3b082b678217b81aef710b3efe62a2103a67a85ae319`. |
| W07 split and design | **PASS** | W07 config SHA-256 `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217`; split artifact SHA-256 `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`. The 5-fold × 10-repeat, 50-fold design, seed root, roles, and W06 code-locked binding agree with the frozen records. |
| W07A amendment lock | **PASS** | Exact UTF-8 SHA-256 of `W07A_pre_W08_protocol_amendment.md` is `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70`, matching the companion JSON. W04, original freeze, W07 config, W07 split, and both W03 candidate hashes also match. P1A–P1D audit-basis hashes are 4/4 matches. |
| W07A workflow provenance | **FAIL / HOLD** | W07A records workflow SHA-256 `ef3db6abb0c51765d0d34f15ede9a19931f7301633fac2da01934e8017c21fd3`; the current workflow file is `0e9e48d8b02a101dad306cc76945249f051eb547f2319bd052fc75c3d49cd5ad`. |
| G2R evidence traceability | **PASS (evidence retained)** | `G2_environment_fingerprint.json` current SHA-256 `a6151d7a135ea19a3f529199996c4063f2fd7b3da4484aa920a73599939ab74b`. Its base commit `72d518cb57525b085b1458eaa19dcecc8e48349e` is an ancestor of the current commit; referenced environment source hashes match. The recorded complete discovery is PASS, 132 ran with 0 failures, 0 errors, 0 skipped; targeted W00B/W05/W08 records are PASS. G2R2 was not run in P4. |

## Technical-parameter comparison

The following frozen technical values and relationships were rechecked without
reading clinical/outcome content:

- The original lock remains byte-identical by SHA-256 and passes the existing
  lock validator. Its frozen threshold fraction is `0.001`; the SLIC supergrid
  is `4.0 × 4.0 × 4.0 mm` with voxel grid `[4, 4, 2]`; the cross-case method
  remains `K=2`; and the frozen centers/boundary are unchanged by the lock
  identity check.
- W07A and W08 agree on `minimumROISize=10` and the three distinct support
  states: zero, 1–9, and at least 10 voxels.
- W04 and W08 agree on the alpha grid `[0.1, 0.5, 0.9, 1.0]`, 100 logarithmic
  lambda values, training-only tuning, inner 5-fold selection, outer 5-fold ×
  10-repeat structure, and 50 total outer validation folds.
- W07A/W08 preserve the paired-population, same-split, same-training-boundary
  contract and the joint penalty semantics for the high-dimensional runs.

These field-level checks are **PASS**, but they do not override the W04 and
W07A provenance failures above; the overall P4 gate remains **FAIL / HOLD**.

## W08, model-lock, and artifact state

- Formal W08: `HOLD`; no formal W08 start is recorded.
- W08 configuration status: `implementation_ready_not_run`.
- `prognosis_analysis/model_freeze_lock.json`: **ABSENT**.
- Current `prognosis_analysis/output/w08_formal_A` metadata contains 393 files,
  all `.npz` files under `work`; no prediction, performance, fold-result, or
  selection-result filenames were present.
- This P4 audit created only this non-patient-level audit report. No new
  patient-level artifact was created.
- `B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
  `B_statistics_generated=false`.

## Read-only commands and results

| Command/check | Result |
|---|---|
| `git rev-parse HEAD`; `git rev-parse origin/main` | Both returned `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`. |
| `git status --short` | Only the pre-existing user-confirmed deletion was present. |
| `python -c "import sys; sys.path.insert(0, 'habitat_analysis/scripts'); import freeze_lock; freeze_lock.validate_freeze_lock('habitat_analysis/freeze_lock.json', artifact_root='habitat_analysis')"` | PASS; 14/14 required artifact-hash fields matched. |
| `Get-FileHash -Algorithm SHA256 -LiteralPath` on the freeze, W04, W03, W07, W07A, G2R, and provenance files | Values recorded above; required artifact hashes matched except the two explicitly reported provenance mismatches. |
| Read-only Python hash verifier for W03 canonical candidate arrays, W04/W07/W07A/W08 bindings, W06 byte hashes, and G2 ancestry | W03 2/2 candidate hashes PASS; W06 3/3 hashes PASS; W07A audit basis 4/4 PASS; W04 source revisions 18 content matches and 1 mismatch; W07A workflow provenance FAIL. |
| `git diff --quiet HEAD --` over immutable freeze/W04/W03/W07/W07A/G2R artifacts | PASS; no immutable artifact diff. |
| `Test-Path prognosis_analysis/model_freeze_lock.json`; W08 output metadata scan | Model lock absent; 393 technical `.npz` cache files only; no formal-result filename hits. |

## Handoff

- Changed file: `prognosis_analysis/W07A_pre_W08_integrity_audit.md` only.
- Tests/checks run: existing `freeze_lock.validate_freeze_lock`; SHA-256
  recomputation for freeze/W04/W03/W06/W07/W07A/G2R artifacts; W03 canonical
  candidate-hash recomputation; W04/W07/W07A/W08 binding comparison; G2 base
  ancestry check; immutable-artifact Git diff check; formal-output metadata
  scan.
- Result: **P4 FAIL / HOLD** due to the W04 taskbook SHA mismatch and W07A
  workflow provenance SHA mismatch. Frozen technical values and artifact
  hashes otherwise remain consistent.
- Remaining risk: the two documentation provenance bindings must be resolved
  by protocol owner review before any P5 implementation or later gate; no
  automatic repair was attempted.
- `B_data_read`: `false`.
- Patient-level artifact status: none created by this audit; only the
  non-patient-level audit report was written.
