# W03 habitat radiomics reproducibility and candidate freeze

## Scope

W03 is completed before any A endpoint access. The input graph is restricted to the A technical cohort manifest, reader-specific upstream muscle-normalized images and tumor masks, the fixed SLIC configuration, and the frozen technical phenotype centers.

Each available reader follows the same ordered procedure:

```text
reader-specific image/ROI
→ fixed upstream preprocessing
→ 3D SLIC at 4 mm with [4,4,2] voxel supergrid
→ frozen technical boundary
→ H-low/H-high assignment
→ Original radiomics
```

The two habitat blocks use the same PyRadiomics settings: `binWidth=0.248808`, no internal normalization, no internal resampling, and first-order, shape, GLCM, GLRLM, GLSZM, GLDM and NGTDM classes.

## Reproducibility and availability rules

For every feature in `R_low` and `R_high`, calculate two-reader ICC(2,1) using paired cases in which both readers have the corresponding habitat and finite feature values. The technical reproducibility gate is strictly `ICC > 0.75` with `n_valid_pairs >= 10`; features below the pair minimum are labelled `insufficient reproducibility sample`.

Finite feature rate is calculated separately for each reader among cases in which the corresponding habitat is present. Both reader-specific rates must be at least 0.95 for formal prediction candidacy.

Candidate levels are fixed as follows:

| Level | Feature classes | Formal prediction pool |
|---|---|---:|
| Main | GLCM, GLRLM, GLSZM, GLDM, NGTDM | Yes |
| Secondary | First-order | Yes |
| Exploratory/QC | Shape | No |

No endpoint, clinical, validation, association, ranking or model input is read by W03. ICC thresholds and exclusion rules are fixed before the candidate hashes are generated. Structural absence remains distinct from technical failure, and the low/high processing and gates are symmetric.

## Local outputs

The patient-level feature tables, reader availability records, technical failure records and feature-level QC are written only to `prognosis_analysis/output/w03_habitat_radiomics_A/`. The candidate freeze record contains `R_low_candidate_hash` and `R_high_candidate_hash`, candidate counts, threshold definitions, symmetry checks and file hashes. No patient-level payload is part of the repository.
