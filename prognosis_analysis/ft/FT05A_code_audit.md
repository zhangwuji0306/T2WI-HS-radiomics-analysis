# FT05A Independent Pre-run Code Audit — Round 5

Independent review: true

Reviewed FT05A implementation commit: `a5351b7dfcd2721aed0fdca3b4430aa10788a736`

FT05A runner SHA-256: `7719ef56afae8e043c954076a1bce26371c17f8c25e7487f40d165e6fe0cd9a4`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

FT05A remains unauthorized to access real B technical assets. The round-4 duplicate-namespace defect is closed for descendant roots and resolved filesystem aliases, but the production validator accepts relative, dot-segment, parent-normalized, and case-variant spellings of the canonical output root. This conflicts with the round-5 requirement that every non-exact output-root spelling fail before ownership creation or extraction.

## Evidence

- Reviewed the repository instructions, FT scheme and amendment, accepted FT00–FT04 records, all FT05A contracts and prior audits, remediation commit `a5351b7dfcd2721aed0fdca3b4430aa10788a736`, and the current FT05A/FT04 implementation and tests.
- The locked wrapper environment matched the required Python 3.7.12, PyRadiomics 3.0.1, and SimpleITK 2.2.1 specification.
- Wrapper static validation passed with no B clustering fit, outcome reader, whole-tumour re-extraction, or formal-directory mixing finding.
- The combined FT05A, FT04, FT03, FT02, and W07 wrapper regression passed: 94 tests, 94 passed, with one platform-permission skip.
- The canonical FT04 lock validated as `VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- The round-4 descendant-root attack now fails before processing: a second descendant invocation does not call the processor, does not load W_Original, and does not create the descendant namespace.
- An independent synthetic path probe confirmed that a descendant root, a Windows junction alias to the canonical root, and a junction escape are rejected. The same probe confirmed that relative, `.`-segment, `..`-normalized, and case-variant spellings are accepted and returned as the canonical path.
- No real B image, ROI, W_Original row, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Independent W_Original trust binding | PASS | The canonical validator derives the accepted path, SHA-256, 107-feature schema/order, and row values from the FT01/FT04 trust chain rather than from manifest assertions. |
| One-to-one source and patient mappings | PASS | Cohort and manifest validation reject repeated patient identities, case identities, image/ROI paths, source keys, and source hashes. |
| Fail-closed audit binding | PASS | The audit is bound to an explicit independent-review marker, accepted verdict, exact implementation ancestor, current runner bytes, and preparation-contract identity; intervening committed code changes are rejected. |
| Preflight before technical reads | PASS | FT04 lock/review, code-audit, configuration, frozen-boundary, and static checks precede cohort loading and source hashing. |
| Exact canonical output root | FAIL | `_validate_namespace_path` resolves and case-normalizes the caller input before comparison. Consequently, several non-exact spellings are accepted rather than rejected as required by the round-5 contract. |
| One global owner/state/artifact/staging/table namespace | PASS | Descendant and resolved reparse aliases cannot create independent namespaces; accepted lexical aliases collapse to the same canonical namespace. Owner, state, cases, staging, table, and manifest are derived from that canonical path. |
| Finalization and manifest/table provenance | PASS | Recovery constrains canonical transaction paths and revalidates state identity, case artifacts, source records, W_Original, table bytes, manifest bytes, and completion evidence before installation. |
| Pilot/resume and duplicate extraction prevention | PASS | Within the single resolved namespace, selected pilot sources are read once, completed exact-hash cases are skipped, concurrent ownership is rejected, and completed runs cannot be rerun. |
| Structural states and PyRadiomics minimum ROI | PASS | Structural absence and technical-small-ROI states are explicit, non-imputed, and preserve the frozen 10-voxel extraction boundary. |
| Technical-only schema and outcome isolation | PASS | Input, result, and table boundaries reject clinical/outcome fields and paths; clinical predictors remain deferred to the later authorized join. |
| Frozen A boundary, no B fit, unchanged PyRadiomics | PASS | Projection uses the accepted A-full boundary without B fitting and binds the unchanged A/W03 PyRadiomics configuration. |
| Accepted-state regression | PASS | All 94 executed wrapper tests passed, and FT04 production validation remained valid. |

## Blocking finding

The output-root gate does not enforce the exact caller spelling. It first resolves relative and dot-segment paths and then compares with `normcase(realpath(...))`. On Windows, this admits a relative project path, a trailing `.` path, a `nested/..` path, and an uppercase case variant of the canonical root. The focused regression explicitly expects these aliases to be accepted and collapsed.

Although these admitted aliases currently converge on one physical owner/state/artifact namespace and therefore do not reproduce the round-4 duplicate extraction, the round-5 contract expressly requires every relative or case-normalized alias to fail before ownership creation or extraction. The gate must require the literal absolute canonical root spelling before resolution, while retaining resolved-path checks for symlink/junction escapes.

## Platform-permission judgment

The directory-symlink regression was skipped because the current Windows account lacks symbolic-link privilege. This skip is not independently blocking: a non-privileged Windows junction was available and rejected, junction escape was rejected, descendant-root coverage passed, and the same resolved-path comparison fail-closes filesystem aliases that resolve away from the canonical root. The separate lexical-alias acceptance remains a confirmed blocking failure regardless of the symlink skip.

## Disposition

The round-4 independent-namespace bypass is closed, and all previously accepted technical, provenance, recovery, and isolation controls remain intact. Exact output-root admission is not compliant with the round-5 gate. Verdict `FAIL`; no real B technical execution is authorized.
