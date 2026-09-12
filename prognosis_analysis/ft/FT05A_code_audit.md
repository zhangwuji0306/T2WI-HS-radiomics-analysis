# FT05A Independent Pre-run Code Audit — Round 7

Independent review: true

Reviewed FT05A implementation commit: `fa725c88ac2e6b82726902fac48cd6bb5369b39c`

FT05A runner SHA-256: `475b3f86bd2ccd9966f1fee6fb2d4a73f7bc4f9d93a690418a5857ea4913310e`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: PASS

## Scope and evidence

- Reviewed the repository instructions, FT scheme and approved amendment, accepted FT00–FT04 artifacts, prior FT05A contracts and audits, the round-6 remediation, current `prognosis_analysis/ft/ft05a_runner.py`, current `tests/test_ft05a_runner.py`, and implementation commit `fa725c8`.
- The production defaults for `FT05_B_feature_manifest.json`, `FT05A_code_audit.md`, and `FT05A_B_technical_generation_audit.md` each pass `_validate_namespace_path` on Windows and resolve to their canonical tracked locations.
- The namespace validator uses `normcase(realpath(...))` for both the candidate and trusted canonical-artifact sets. Exact tracked-path admission additionally requires the caller's literal spelling to equal the canonical constant; the output root requires the single literal absolute canonical spelling.
- An independent round-7 synthetic probe accepted the three exact tracked paths and rejected relative, dot-segment, parent-normalized, descendant, case, slash, trailing-dot, trailing-space, and extended-path aliases before preflight, ownership, W_Original loading, cohort loading, state/output writers, or hashing. Existing junction/reparse coverage rejected an output-root alias before processing.
- FT05A wrapper regression: 33 tests passed, with one Windows symbolic-link privilege skip and no failures.
- FT04, FT03, FT02, and W07 wrapper regression: 65 tests passed with no failures.
- FT05A static validation returned no B clustering fit, outcome reader, whole-tumour re-extraction, formal-directory mixing, or other static finding.
- FT04 lock validation returned `VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- No production FT05A manifest, technical feature table, run state, or FT05B unlock was accessed or created. No B image/ROI, B outcome or clinical table, patient-level output, or real FT05A technical artifact was read or written during this review.

## Mandatory control assessment

| Control | Assessment |
|---|---|
| Production canonical tracked paths | Exact manifest, code-audit, and technical-audit defaults pass the Windows namespace gate. |
| Normalized representation | Candidate and trusted artifact membership use the same `normcase(realpath(...))` representation; raw literal comparison is retained only for exact tracked-path admission. |
| Exact-path and pre-side-effect rejection | Relative, dot, parent, descendant, case, slash, trailing-dot/space, extended, alternate, and reparse aliases fail closed before preflight and technical side effects. |
| FT04 prerequisite and binding | Frozen FT04 lock, serialized-lock digest, accepted FT04 review, current FT05A code binding, and preparation-contract identity remain enforced. |
| Outcome blindness and no B fitting | Technical input/result deny-lists, static checks, and the default processor prevent outcome access, B clustering fitting, and feedback from B results. |
| Frozen A boundary and PyRadiomics | Preflight binds the accepted full-A habitat/SLIC definition, candidate hashes, unchanged A/W03 PyRadiomics configuration, and minimum-ROI rule; processing projects B cases onto that boundary. |
| W_Original trust and source uniqueness | W_Original path/hash/order/reuse binding is derived from FT04/FT01 trust records; source paths, hashes, keys, case identities, patients, and persisted rows are one-to-one validated. |
| One-time ownership, pilot, and resume | The canonical owner/state namespace, immutable case artifacts, pilot selection, resume identity, and completed-run refusal prevent duplicate extraction or recomputation. |
| Finalization and provenance | Interrupted finalization recovery revalidates transaction paths, hashes, case evidence, W_Original bindings, table/manifest equality, and completion state before installation. |
| Structural/technical states | Structural absence, small-ROI technical unavailability, and available blocks are explicit and consistently serialized; undefined features cannot be treated as available. |
| Formal-directory isolation | Technical source and output allowlists reject formal/A/FT03/FT04/W08/L9 namespaces and path traversal. |
| Accepted-state regression | The focused and upstream synthetic suites pass; no regression was detected in the previously accepted FT05A controls. |

## Nonblocking platform finding

The synthetic directory-symlink test was skipped because the Windows account lacks symbolic-link privilege. This is nonblocking: the equivalent Windows junction/reparse path test passed, and the production validator retains both exact lexical admission and resolved-path containment checks.

## Downstream authorization

FT05A is authorized for the next contract-defined real-B technical-generation step only. The authorization is limited to one outcome-blind first extraction after FT04 freeze, with the existing W_Original asset reused, no B outcome access, no B fitting or optimization, and no FT05B/FT06 execution in this audit.
