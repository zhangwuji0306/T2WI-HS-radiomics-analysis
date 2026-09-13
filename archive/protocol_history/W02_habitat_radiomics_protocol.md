# W02 H-low/H-high Original radiomics

W02 is an outcome-blind technical stage. It uses the W01 frozen R1
muscle-normalized T2WI, tumor ROI and frozen SLIC habitat labels from the A393
technical cohort. It does not read clinical, pathology, DFS/OS/CSS, or B-cohort
data, and it does not perform ICC calculation, candidate filtering, modeling,
or outcome-driven technical selection.

Both blocks are extracted by the same PyRadiomics 3.0.1 parameter set:

- image type: `Original` only;
- `binWidth=0.248808`;
- `normalize=false`;
- internal resampling disabled (`resampledPixelSpacing=null`);
- `firstorder`, `shape`, `glcm`, `glrlm`, `glszm`, `gldm`, and `ngtdm`.

The frozen habitat map is used directly as the mask source; W02 does not
re-normalize, resample, rerun SLIC, or estimate a new bin width. `R_low` and
`R_high` are processed symmetrically in every case. If a habitat is absent,
its block is recorded as `structurally_undefined` with `failure_class` set to
`structural_absence`; all its feature values remain undefined. A PyRadiomics
or input error is recorded separately as `technical_failure` and is never
converted to zero.

The local outputs are written to
`prognosis_analysis/output/w02_habitat_radiomics_A/` and include paired feature
tables, paired diagnostics, per-case availability, technical failure records,
an aggregate summary, and parameter/provenance JSON. These patient-level
outputs are local and gitignored. W03 owns outcome-blind reproducibility QC and
candidate-pool filtering.

Run locally with:

```powershell
conda run -n t2_radiomics --no-capture-output python prognosis_analysis/scripts/w02_habitat_radiomics.py
```
