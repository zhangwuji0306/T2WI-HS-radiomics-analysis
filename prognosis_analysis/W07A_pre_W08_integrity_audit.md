# W07A Pre-W08 Integrity Audit

## P4 result

- Audit stage: `P4 — Post-freeze integrity verification`.
- Verification source commit: `b35605c931b7a00bd1ef503120a5a26057be9a8e`.
- Overall P4 result: **PASS**, with the explicit W07A historical-source exception recorded below.
- P5 implementation, G2R2, 50-fold P5, G3, and formal W08 remain unauthorized.

The independent machine-readable reconciliation is
`prognosis_analysis/W07A_pre_W08_provenance_reconciliation.json`; its
fail-closed validator is
`prognosis_analysis/scripts/provenance_reconciliation.py`.

## Scope and access boundary

This audit used protocol documents, JSON/configuration metadata, Git objects,
file bytes and SHA-256 values. The W07 outer-split CSV was checked only as a
recorded path/SHA metadata binding and was not opened. No A clinical/outcome
value, B source, B validation data, model fit, prediction, performance metric,
or patient-level result was read or generated.

The user-confirmed deletion of `组学分析方案.md` remains untouched and is
outside this remediation. No frozen scientific or modeling asset was modified.

## Provenance reconciliation

| Binding | Reconciled evidence | Semantic disposition |
|---|---|---|
| W04 taskbook | Frozen W04 source revision remains path `T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md`, SHA-256 `0ba96334e37b5729356b947ffa41bd2d52649cc84f8d760ba4bbc51a129ffc3c`. Exact historical bytes are recoverable from Git commit `78b0e8f48becd64413859027e8809e155ecded5e`, the same Git path, blob `8a89c12b621b2560202902df3477aaa11acd0a5c`, and recomputed SHA-256 `0ba96334e37b5729356b947ffa41bd2d52649cc84f8d760ba4bbc51a129ffc3c`. | The current Scientific Master Protocol successor is the approved same-path revision at commit `b35605c931b7a00bd1ef503120a5a26057be9a8e`, current SHA-256 `cc881c008629a1acc0a2b4e6570b4ef277faa27ed5c9f12f908ee947b42381dd`. W04 scientific and modeling freeze authority remains `prognosis_analysis/modeling_protocol.json`; no frozen parameter or scientific meaning changed. |
| W04 workflow path migration | Frozen W04 source revision remains the historical root path `三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md`, SHA-256 `26be0bae34faf6dc0b22c7bb3f3e041988ed87cb85b5de1c72cfe8969bd1fd6d`. The exact 100% archive rename is verified at commit `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`, archive path `archive/protocol_history/三十二、具体执行工作流：从 formal PASS 至 A-only model freeze.md`, blob `ceb7146ec51e73da03bb1a8f04d6cac9026c66b4`, and recomputed SHA-256 `26be0bae34faf6dc0b22c7bb3f3e041988ed87cb85b5de1c72cfe8969bd1fd6d`. | The archive is historical only and is not treated as the current execution input. The approved current successor is the Pre-W08 SOP at commit `21f2bf7f0bb3cbbad2f8e4d1a305f748d60f60d2`; its current worktree SHA-256 is `0e9e48d8b02a101dad306cc76945249f051eb547f2319bd052fc75c3d49cd5ad` and its Git snapshot SHA-256 is `e5549211211fda3bfe1dfc8f6ba826b6be5f7e7943fb6d96ed4444899857603a`. |
| W07A workflow | Recorded W07A source provenance remains path `T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md`, SHA-256 `ef3db6abb0c51765d0d34f15ede9a19931f7301633fac2da01934e8017c21fd3`. The exact pre-amendment byte snapshot is not recoverable: Git commit, path and blob are explicitly `null`, and exact verification is `false`. | Reconciliation is **PASS with explicit `historical_source_snapshot_unrecoverable` exception**. The current approved successor is the Pre-W08 SOP identified above. This is not and must not be reported as W07A byte-exact PASS. The semantic review concludes that later operational additions and restructuring do not alter the frozen W07A scientific decisions, technical parameters, or A/B boundary; later P5/G2R2 governance text is not retroactively treated as W07A freeze content. |

## Approval and invariants

Protocol-owner approval covers only P4 document-provenance reconciliation:
preserving the W04 historical revision, registering the W04 archive migration,
registering the W07A unrecoverable-source exception, adding this independent
manifest/validator, and recording the audit evidence. It does not authorize
changes to `freeze_lock`, `modeling_protocol`, W03/W07/W07A frozen assets or
parameters; B access; formal W08; P5 implementation; G2R2; 50-fold P5; or G3.

The manifest and validator require these invariants:

- `outcome_performance_informed=false`
- `scientific_parameters_changed=false`
- `B_data_read=false`
- `formal_W08_started=false`

The reconciliation is governance metadata only. It does not modify a
scientific protocol, re-freeze W04 or W07A, change any parameter, or authorize
the next execution stage.

## Validation evidence

- Manifest CLI: `python prognosis_analysis/scripts/provenance_reconciliation.py --root .` — **PASS**.
- Provenance tests: `python -m unittest discover -s tests -p "test_provenance_reconciliation.py"` — **10 tests, 0 failures**.
- Modeling protocol tests: `python -m unittest discover -s tests -p "test_modeling_protocol.py"` — **7 tests, 0 failures**.
- The modeling protocol source-revision test now delegates to the version-aware validator; it does not reduce validation to file existence.
- Fail-closed regression coverage includes missing/forged W07A exception, W04 Git-object mismatch, modified successor SHA, unapproved successor, and unregistered successor revision.
- The validator requires Git, verifies recoverable historical bytes, verifies the approved successor's current and Git-snapshot SHA-256 values, rejects unregistered schema/version changes, and preserves `W07A exact_verification=false`.

## Preserved state

- `habitat_analysis/freeze_lock.json`: unchanged and still valid.
- `prognosis_analysis/modeling_protocol.json`: unchanged; recorded W04 source revisions remain unchanged.
- W03 candidate freeze, W07 split/configuration, W07A amendment and its lock: unchanged.
- `prognosis_analysis/model_freeze_lock.json`: absent.
- Formal W08: not started; status remains `HOLD`.
- Patient-level artifacts: none created by this remediation.
- `B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`; `B_statistics_generated=false`.
- P5 authorization: **no**.
