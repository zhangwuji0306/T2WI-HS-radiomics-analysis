# FT05A Independent Pre-run Code Audit — Round 3

Independent review: true

Reviewed FT05A implementation commit: `d0c59b07b8347dedc7fd04a7e2d08dd4f98a9616`

FT05A runner SHA-256: `73169e36c4d1c28d2418abecd1606cdb88b4cd7cc08e5a38d697cc9fa3404535`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

FT05A remains unauthorized to access real B technical assets. The round-2 remediation closes the normal finalization-recovery, source-file, case-identity, table-order, audit-commit, and pilot-row paths, but the canonical technical-manifest validator still accepts self-authorized W_Original provenance and duplicate source mappings.

## Evidence

- Reviewed the repository instructions, FT scheme and amendments, accepted FT00–FT04 records, all prior FT05A contracts and audits, commits `35f873ac8333f4f8c0e8e770b87a79e36635d4da` and `d0c59b07b8347dedc7fd04a7e2d08dd4f98a9616`, and the current FT05A/FT04 implementation and tests.
- The wrapper static validation passed with no B clustering fit, outcome reader, whole-tumour re-extraction, or formal-directory mixing finding.
- The focused FT05A synthetic suite passed: 24 tests, 24 passed.
- The FT04 plus FT05A wrapper regression passed: 48 tests, 48 passed.
- The accepted-state combined wrapper regression passed: 89 tests, 89 passed.
- Synthetic finalization-recovery checks rejected altered transaction paths and recovered an interrupted transition only after revalidating the canonical table, manifest, completed-case evidence, W_Original binding, and case artifacts.
- Synthetic source tamper, selected-row pilot instrumentation, duplicate-prevention, structural-state, outcome-isolation, audit-binding, and one-time resume checks passed.
- No real B image, ROI, W_Original asset, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Exact frozen A-full boundary | PASS | Preflight and case evidence bind the frozen boundary identity, K=2, n_init=100, SLIC settings, and source hashes before technical processing. |
| No habitat fitting on B | PASS | Wrapper static validation found no clustering import, K-means symbol, or fitting call; production projection uses the frozen boundary directly. |
| No B outcome or clinical access | PASS | Technical input and result schemas denylist outcome/clinical fields and paths; static and synthetic negative checks pass. |
| Frozen PyRadiomics configuration | PASS | Preflight binds the accepted A/W03 configuration and exact settings before case processing. |
| No whole-tumour extraction; exact W_Original reuse | PASS_WITH_FINDINGS | Normal generation and finalization bind the accepted W_Original rows; standalone manifest validation can accept a manifest-supplied disallowed W_Original path and hash. |
| Duplicate patients and extractions rejected | FAIL | Normal cohort loading rejects duplicate mappings, but standalone manifest validation accepts distinct patient rows with identical image/ROI/source mappings after self-consistent hash and identity updates. |
| Resume never recomputes completed or pilot cases | PASS | Ownership, artifact hashes, case identity, row/schema hashes, and interrupted-finalization recovery are checked before reuse. |
| No formal-directory read or mixing | PASS_WITH_FINDINGS | Canonical transaction and ordinary source roots are constrained; the manifest validator's exact-path exception bypasses the disallowed non-formal `feature_extract/output` root for W_Original. |

## Residual blocking findings

1. **W_Original provenance is self-authorized by the manifest.** `validate_ft05a_technical_manifest` validates `feature_blocks.W_Original.asset_path` with `exact_paths=(w_record["asset_path"],)`. When no internal expected asset is supplied, it then constructs the W_Original binding from that same manifest path and hash before loading it. A synthetic frozen manifest was changed to use `feature_extract/output/_ft05a_round3_synthetic_w.csv`, with the corresponding self-reported asset hash and source-record bindings; the validator returned success. The validator therefore does not independently bind W_Original to the accepted FT01/FT04 path and hash or reject every disallowed provenance root.

2. **Persisted source mappings are not required to be one-to-one.** The manifest validator checks duplicate case identities and patient IDs, but does not reject repeated `image_path`, `roi_path`, `source_image_key`, or `source_roi_key` values. A synthetic manifest with two patient rows mapped to the same image/ROI and source keys, with recomputed case identities and cohort hashes, was accepted. This leaves duplicate extraction and incorrect patient-to-source provenance fail-open at the canonical manifest boundary.

Both findings are blocking because the later technical manifest is the provenance boundary for the one-time, technical-only B generation. Real B technical execution must not start until the validator independently binds W_Original to the accepted asset and rejects repeated source mappings.

## Disposition

FT04 remains an accepted prerequisite and the accepted-state regression is intact. The normal FT05A execution paths are substantially fail-closed, but the canonical manifest boundary is not. Verdict `FAIL`; no real B technical execution is authorized.
