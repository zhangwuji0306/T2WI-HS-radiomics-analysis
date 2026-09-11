# FT01 Asset Audit

## Conclusion

`PARTIAL_PASS`

`FT01_A = PASS`

`FT01_B_habitat_assets = NOT_YET_GENERATED`

A technical assets and the frozen full_A habitat pass the FT01 checks. The existing whole-tumor asset is bound to the approved 107-feature `W_Original` definition. B `R_low`/`R_high` have never been generated; their absence is the expected pre-FT05A state and does not block A-only FT02-FT04.

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
| Existing B R_low asset | NOT_YET_GENERATED | NOT_YET_GENERATED |
| Existing B R_high asset | NOT_YET_GENERATED | NOT_YET_GENERATED |
| B technical asset/provenance search | Roots: `prognosis_analysis/output, habitat_analysis/output, feature_extract/output`; matching habitat tables: 0; matching provenance files: 0 | NOT_YET_GENERATED |
| Candidate hashes and habitat provenance | Frozen target hashes recorded; B evidence will be generated and audited in FT05A | NOT_YET_GENERATED |

B habitat radiomics are deferred until FT04 freezes `FT_model_freeze_lock.json`. FT05A then permits one outcome-blind first extraction using the frozen A-full boundary, no B K-means fit, and the unchanged A/W03 PyRadiomics configuration. B outcome remains locked until the feature table, hash, and provenance audit pass.

## Frozen-state and boundary checks

- `habitat_analysis/freeze_lock.json` remains the existing technical lock; `B_unlock=false` and `B_data_read=false`.
- Formal W08 remains `HOLD`; the formal model-freeze lock is absent.
- `W_Original` is the only whole-tumor block represented in FT01; its canonical order is the exact 107-name sequence recorded in the manifest and matched by the existing asset. Wavelet, LoG, and other filtered whole-tumor features are excluded.
- FT02–FT07 were not executed by this audit; `FT02_ready=true` authorizes only A-only FT02-FT04.

## Source records

- FT00 protocol: `prognosis_analysis/ft/FT00_protocol.json`
- FT protocol amendment: `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`
- Full_A descriptors: `habitat_analysis/output/habitat_features_A/global_descriptors_full_A.csv`
- W03 A technical assets: `prognosis_analysis/output/w03_habitat_radiomics_A/`
- Whole-tumor Original asset: `feature_extract/output/features_v2/muscle_f0.25/features_original.csv`

The manifest contains file hashes, schema/order summaries, aggregate row counts, and no patient-level identifier values.
