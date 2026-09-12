# FT05A Independent Pre-run Code Audit — Round 6

Independent review: true

Reviewed FT05A implementation commit: `e7a231c2f4eed0f57abb11613d98dd0f2b068291`

FT05A runner SHA-256: `ce29143a4bf35bebc0577f083c6ca06aa453c4a34c14f622cc1148d8b87b5020`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

The exact-output-root remediation correctly rejects every tested non-exact root spelling before technical side effects and retains reparse-resolution protection. The current production namespace validator nevertheless rejects its own canonical tracked manifest, code-audit, and technical-audit paths on Windows. The default production invocation therefore cannot pass the initial namespace gate, and FT05A remains unauthorized to access real B technical assets.

## Evidence

- Reviewed the repository instructions, FT scheme and amendment, accepted FT03/FT04 records, prior FT05A canonical audits and relevant contracts, remediation commit `e7a231c2f4eed0f57abb11613d98dd0f2b068291`, and the current FT05A/FT04 implementation and tests.
- The required wrapper environment reported Python 3.7.12, PyRadiomics 3.0.1, and SimpleITK 2.2.1.
- An independent lexical probe rejected all 12 tested non-exact forms: relative, dot-segment, parent-normalized, trailing separator, case variant, slash variant, trailing dot, trailing space, parent, descendant, extended-path spelling, and non-string input. The exact literal `CANONICAL_OUTPUT_ROOT` was accepted.
- Focused wrapper path coverage passed the lexical, exact-root, descendant-root, noncanonical-root, and Windows junction checks. The directory-symlink check was skipped only because symbolic-link privilege was unavailable.
- The combined FT05A, FT04, FT03, FT02, and W07 wrapper regression passed: 96 tests, 96 passed, with one platform-permission skip.
- FT05A static validation passed with no B clustering fit, outcome reader, whole-tumour re-extraction, or formal-directory mixing finding.
- The canonical FT04 lock validated as `VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- A production-default namespace probe rejected all three canonical tracked paths: `FT05_B_feature_manifest.json`, `FT05A_code_audit.md`, and `FT05A_B_technical_generation_audit.md`. This occurs before cohort/source/W_Original/owner/state/output activity.
- No real B image, ROI, W_Original row, technical feature, identifier, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Exact literal output-root admission | PASS | `_canonical_output_root` compares caller text to the single absolute `CANONICAL_OUTPUT_ROOT` before resolution, then confirms the resolved location. All tested lexical aliases, parents, descendants, and reparse spellings fail closed. |
| Pre-side-effect rejection | PASS | Adversarial tests instrument owner acquisition, W_Original loading, cohort loading, hashing, processor calls, and state/output writers; non-exact roots reach none of them. |
| Internal canonical run namespace | PASS_WITH_FINDINGS | Owner, state, case artifacts, staging, and the feature table are derived from `CANONICAL_OUTPUT_ROOT`. The separately validated canonical tracked manifest/audit paths are unusable because of the blocking comparison defect below. |
| Reparse-resolution protection | PASS | The exact lexical check is followed by `realpath` comparison. A non-privileged Windows junction alias was rejected; junction/descendant coverage exercises the same resolved-path protection used for directory symlinks. |
| Frozen FT04 prerequisite and audit binding | PASS | The canonical FT04 lock remains valid, and code-audit validation binds independence, accepted verdict, reviewed implementation ancestry, exact runner bytes, preparation-contract identity, and report-only post-review history. |
| Technical-only and outcome isolation | PASS | Input, result, table, and path boundaries reject clinical/outcome fields; FT05A exposes no outcome reader and defers clinical predictors to the authorized later join. |
| No B fit; frozen A boundary and PyRadiomics | PASS | Production projection uses the accepted A-full boundary with no B clustering fit and binds the unchanged A/W03 PyRadiomics configuration and 10-voxel minimum ROI boundary. |
| W_Original provenance and one-to-one sources | PASS | The validator derives W_Original path/hash/order/rows from the accepted FT01/FT04 trust chain and rejects duplicate or aliased patient, image, ROI, source-key, source-hash, and case mappings. |
| Pilot/resume and global ownership | PASS | One canonical owner/state namespace, exact case-artifact hashes, selected-source pilot handling, and completed-run refusal prevent repeated accepted work in the synthetic suite. |
| Finalization, manifest/table provenance, and structural states | PASS | Recovery revalidates canonical transaction paths, table/manifest bytes and binding, completion evidence, W_Original, source records, case artifacts, and explicit structural/technical availability states. |
| Accepted-state regression | PASS_WITH_FINDINGS | All 96 combined wrapper tests passed and FT04 remained valid, but the suite does not exercise the production-default canonical tracked artifact paths and therefore did not detect the blocking namespace defect. |

## Blocking finding

`_validate_namespace_path` builds `canonical_artifacts` from `normcase(realpath(...))`, but its FT-namespace admission branch tests the un-normalized `absolute` path for membership in that normalized set. On Windows, the exact canonical tracked paths retain their original case in `absolute` and do not equal the lower-cased set members. Consequently, the production defaults for the manifest, code audit, and technical audit are all rejected as outside the FT local namespace.

This is fail-closed with respect to B access, but it prevents the only intended production invocation from reaching preflight or execution. It also means the round-6 requirement that the accepted call use canonical downstream artifact paths is not satisfied. The existing synthetic tests relocate these constants into the temporary output root, so they bypass the failing tracked-artifact branch.

## Platform-permission judgment

The one directory-symlink test skip is non-blocking. The skip reflects the current Windows account's missing symbolic-link privilege, while the production gate retains the post-lexical `realpath` check and the available non-privileged junction test passed. Parent, descendant, extended-path, and lexical alias probes also fail before side effects. This judgment does not mitigate the independent canonical-artifact-path blocker.

## Disposition

The exact output-root spelling defect is closed, reparse protection remains intact, and the previously accepted technical, provenance, recovery, ownership, structural-state, and isolation controls show no regression. The production-default canonical artifact paths fail their own namespace gate. Verdict `FAIL`; no real B technical execution is authorized.
