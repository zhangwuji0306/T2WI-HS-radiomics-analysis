# W08 local L3R exact feature reduction audit

## Scope

This audit covers the outcome-blind PyRadiomics implementation change for
the frozen W08 habitat candidates. It contains no patient identifier,
patient-level feature value, clinical outcome, prediction, performance
result, or local machine path.

## Frozen feature contract

- `R_low`: 49 frozen candidates.
- `R_high`: 10 frozen candidates.
- Total frozen radiomics candidates: 59.
- Candidate identities and order remain sourced from
  `w08_nested_cv.FROZEN_CANDIDATE_FEATURES`; candidate hashes are unchanged.
- Each block has its own extractor. Only `Original` is enabled, and only the
  candidate names belonging to that block are enabled within their feature
  classes.
- `shape` and every unused feature class are disabled. The enabled classes are
  the classes represented by the frozen candidates: `firstorder`, `glcm`,
  `gldm`, `glrlm`, `glszm`, and `ngtdm`.

The following settings remain unchanged:

```text
binWidth=0.248808
normalize=false
resampledPixelSpacing=null
minimumROIDimensions=2
public minimumROISize=10
label=1
PyRadiomics backend minimumROISize=null (compatibility shim only)
```

The public P3B support classification is unchanged: zero voxels are
`structurally_absent`, one to nine voxels are
`technically_unextractable_small_ROI`, and ten or more voxels are
`radiomics_extractable`. Ineligible masks are rejected before PyRadiomics is
called. If an exact extractor omits a frozen feature or returns a non-numeric
value, the provider fails closed.

## Equivalence verification

The exact block extractors were compared with the retained full-category
extractor on deterministic synthetic image/mask fixtures covering:

- exactly 10 voxels;
- an 11-voxel irregular ROI near the threshold;
- a large ROI;
- both `R_low` and `R_high` blocks;
- multiple gray levels and 3-D texture directions.

All 59 requested feature values were present in both results and matched with
zero absolute and relative tolerance, treating paired `NaN` values as equal.
The exact result contained no `original_` feature outside the block's frozen
candidate list.

## Aggregate benchmark

The fixed synthetic L2 image fixture was executed five times per extractor in
the locked `t2_radiomics` environment. The table reports medians of direct
PyRadiomics execution; values are software timing observations, not model
performance.

| Block | Full-category median (s) | Exact-candidate median (s) | Reduction |
|---|---:|---:|---:|
| `R_low` | 0.066094 | 0.053196 | 19.5% |
| `R_high` | 0.069953 | 0.056445 | 19.3% |

The exact medians are below the corresponding L2 reference medians
(`R_low=0.069941 s`, `R_high=0.070348 s`). The three-repeat synthetic-only
technical probe completed successfully with all safety flags false.

## Verification record

- L3R exact-feature tests: 4/4 passed.
- Existing W08 radiomics boundary tests: 5/5 passed.
- Synthetic-only technical probe: 3/3 repeats complete; no failure stage.
- Environment source: root `environment.yml`, environment name `t2_radiomics`,
  Python `3.7.12`, NumPy `1.21.6`, pandas `1.3.5`, SciPy `1.7.3`,
  scikit-learn `1.0.2`, PyRadiomics `3.0.1`, and SimpleITK `2.2.1`.
- Actual invocation for every test, probe, and version check:
  `tools/run_t2_radiomics.ps1 -PythonArguments ...`.
- PyRadiomics: 3.0.1.
- SimpleITK: 2.2.1.
- Thread settings: OMP/MKL/OPENBLAS/NUMEXPR = 1.
- No formal writer was invoked.

## Access boundary

`outcome_columns_read=false`; `formal_writer_invoked=false`;
`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
`B_statistics_generated=false`.

This L3R change does not start formal W08, W09, model freeze, or B
validation.
