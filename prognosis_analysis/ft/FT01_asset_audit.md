# FT01 Asset Audit

## Conclusion

`FAIL_CLOSED`

A technical assets and the frozen full_A habitat pass the observable FT01 checks. The existing whole-tumor asset is bound to `W_Original` only. B cannot be released to FT02 because no existing B `R_low`/`R_high` habitat feature tables or B habitat radiomics provenance were found in the permitted technical output roots.

No B outcome, clinical, performance, or validation result was read. No B MRI preprocessing, SLIC, K-means, PyRadiomics extraction, feature selection, preprocessing estimation, or model fitting was executed.

## A audit

| Item | Evidence | Result |
|---|---|---|
| Full_A habitat | 3D SLIC 4 mm; `[4,4,2]` voxels; K=2; `n_init=100`; frozen centers/boundary | PASS |
| Full_A descriptors | 393 rows; 393 unique IDs; 0 hard technical failures | PASS |
| Habitat maps | 393 manifest rows; 393 map files | PASS |
| Candidate R_low | 49 features; hash `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` | PASS |
| Candidate R_high | 10 features; hash `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` | PASS |
| W03 A R_low/R_high | Existing R1 tables each contain 393 rows and frozen candidate columns | PASS |
| W02 A provenance | Existing W02 output manifest hashes match local files | PASS |
| W03 A provenance | Existing W03 output manifest hashes match local files | PASS |
| W | Existing whole-tumor Original table; 107 Original features; R1 rows matching full_A: 393; all finite: 393; filtered features excluded | PASS |
| W_Original canonical order | Exact ordered sequence emitted by the existing W asset; 107 features; W03 schema set match: PASS; canonical hash `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`; asset hash `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f` | PASS |
| W_Original image types | Original only; Wavelet, LoG, and other filtered features excluded | PASS |

## B technical audit

| Item | Result |
|---|---|
| Patient-ID schema | Technical ID column is `影像号`; no identifiers are emitted in tracked FT01 artifacts | PASS |
| Existing B W_Original asset | schema present; technical split rows: 171; R1 finite rows: 163; B technical-cohort alignment not certified | PASS_WITH_LIMITATION |
| Existing B R_low asset | missing | FAIL_CLOSED |
| Existing B R_high asset | missing | FAIL_CLOSED |
| B technical asset/provenance search | Roots: `prognosis_analysis/output, habitat_analysis/output, feature_extract/output`; matching habitat tables: 0; matching provenance files: 0 | FAIL_CLOSED |
| Candidate hashes and habitat provenance | blocked_missing_existing_B_habitat_assets | FAIL_CLOSED |

The B blocker is exact: no existing B `R_low`/`R_high` habitat feature tables or B habitat radiomics provenance were found under the permitted technical output roots. FT01 does not infer compatibility from A assets and does not generate replacement B features.

## Frozen-state and boundary checks

- `habitat_analysis/freeze_lock.json` remains the existing technical lock; `B_unlock=false` and `B_data_read=false`.
- Formal W08 remains `HOLD`; the formal model-freeze lock is absent.
- `W_Original` is the only whole-tumor block represented in FT01; its canonical order is the exact 107-name sequence recorded in the manifest and matched by the existing asset. Wavelet, LoG, and other filtered whole-tumor features are excluded.
- FT02–FT07 were not executed.

## Source records

- FT00 protocol: `prognosis_analysis/ft/FT00_protocol.json`
- Full_A descriptors: `habitat_analysis/output/habitat_features_A/global_descriptors_full_A.csv`
- W03 A technical assets: `prognosis_analysis/output/w03_habitat_radiomics_A/`
- Whole-tumor Original asset: `feature_extract/output/features_v2/muscle_f0.25/features_original.csv`

The manifest contains file hashes, schema/order summaries, aggregate row counts, and no patient-level identifier values.
