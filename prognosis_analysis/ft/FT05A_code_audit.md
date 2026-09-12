# FT05A Independent Pre-run Code Audit — Round 4

Independent review: true

Reviewed FT05A implementation commit: `c8682c4d6f321ff17a1f02cab3fe555805eb4f92`

FT05A runner SHA-256: `3d0f1c4df25c8998294fc87d3743e267786ce36427bf1ffd36561667aee75bcf`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

FT05A remains unauthorized to access real B technical assets. The round-3 remediation closes the two previously reported manifest-boundary defects, but the production runner still permits multiple independent run namespaces beneath the nominal FT05A output root. This defeats global one-time ownership and permits the same case to be extracted more than once.

## Evidence

- Reviewed the repository instructions, FT scheme and amendment, accepted FT00–FT04 records, all FT05A contracts and prior audits, remediation commit `c8682c4d6f321ff17a1f02cab3fe555805eb4f92`, and the current FT05A/FT04 implementation and tests.
- Wrapper static validation passed with no clustering fit, outcome reader, whole-tumour re-extraction, or formal-directory mixing finding.
- The combined FT05A, FT04, FT03, FT02, and W07 wrapper regression passed: 91 tests, 91 passed.
- The canonical FT04 lock validated as `VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- The canonical manifest validator rejected alternate W_Original provenance and duplicate persisted image/ROI paths, source keys, source hashes, case identities, and patient identities in the synthetic regression suite. It independently derives the accepted W_Original path, asset hash, 107-feature schema/order, and row values from the FT01/FT04 binding.
- Synthetic regressions passed for audit binding, preflight-before-file-read, exact technical source roots, finalization recovery and tamper rejection, case-artifact/table/manifest binding, selected-source pilot reads and resume, structural absence, PyRadiomics minimum-ROI handling, outcome isolation, frozen A boundary, no B fit, unchanged A/W03 PyRadiomics settings, and technical-only output schema.
- An independent synthetic adversarial probe supplied two distinct descendant output roots under the canonical FT05A directory and the same run identity/cohort. Both invocations completed a pilot for the same selected case, and the processor was called twice. No real B source or manifest was accessed.
- No real B image, ROI, W_Original row, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Independent W_Original binding | PASS | The validator derives the binding from the canonical FT04 lock, cross-checks FT01, enforces exact path/hash/schema/order, and verifies every persisted W_Original row against the accepted asset. |
| One-to-one persisted source mappings | PASS | Canonical validation rejects repeated or aliased image/ROI paths, source keys, source hashes, case identities, and patient identities and binds rows to source records in order. |
| Fail-closed code-audit binding | PASS | The audit record is bound to the exact reviewed implementation commit, current runner bytes, independent-review marker, accepted verdict, and preparation-contract identity; intervening committed code paths and stale runner hashes are rejected. |
| Preflight before B technical reads | PASS | Lock/review/code/config/static checks precede technical cohort loading and source hashing. |
| Exact source and output roots | FAIL | Technical source reads are fixed to the canonical source root, but the output-root validator accepts arbitrary descendants of the canonical FT05A root instead of the single canonical run root. |
| Finalization and artifact binding | PASS | Recovery constrains transaction paths and revalidates state, case artifacts, source records, table bytes, manifest bytes, W_Original, and completion evidence before installation or completion. |
| Pilot selected-source reads and resume | PASS_WITH_FINDINGS | Within one state namespace, selected sources are read once and completed pilot cases are not recomputed; separate accepted descendant namespaces bypass that guarantee. |
| Structural absence and technical-small-ROI states | PASS | The production processor records explicit unavailable states without imputation and applies the frozen 10-voxel PyRadiomics boundary. |
| Duplicate and concurrent extraction prevention | FAIL | Ownership is scoped to the caller-selected output root. Two accepted descendant roots create separate owner/state/case namespaces and can process the same case twice. |
| Technical-only schema and outcome isolation | PASS | Input/result/table schemas deny clinical/outcome fields, and the nine clinical predictors remain deferred to the authorized later join. |
| Frozen A boundary, no B fit, unchanged PyRadiomics | PASS | The runner projects to the accepted A-full boundary, contains no clustering fit, and constructs the A/W03 PyRadiomics 3.0.1 settings without re-estimation. |
| Accepted-state regression | PASS | The combined 91-test wrapper regression and FT04 production validation passed. |

## Blocking finding

`_validate_namespace_path` accepts any output root contained beneath `DEFAULT_OUTPUT_ROOT`. Run ownership, run state, case artifacts, staging, and the technical feature table are then derived from that caller-selected descendant. Consequently, the ownership file is not global to the canonical FT05A run. A synthetic probe used two descendant roots with the same run identity and technical cohort; both runs returned `PILOT_COMPLETE` and processed the same selected case independently. The same defect permits parallel full runs to perform duplicate extraction before competing for a manifest.

This violates the fixed-root, one-time generation, pilot continuity, and duplicate/concurrency requirements. The production interface must enforce one exact canonical output root, or otherwise place ownership and run identity in one immutable global namespace that cannot vary with caller input, before real-B technical execution can be authorized.

## Disposition

The prior W_Original self-authorization and persisted source-aliasing findings are closed, and the remaining reviewed controls are intact. The output-root ownership bypass is blocking. Verdict `FAIL`; no real B technical execution is authorized.
