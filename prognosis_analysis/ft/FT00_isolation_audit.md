# FT00 Isolation Audit

## Status

`PASS`

FT00 is frozen as an independent exploratory branch. Only FT00 protocol and
isolation records are established here; FT01–FT07 are not executed.

## Baseline

- Pre-FT baseline commit: `88ffcda16b8ba16324f6824637490d5bc1652ef8`
- Baseline branch: `main`
- Dedicated FT branch: `codex/ft-validation`
- Formal W08 state: `HOLD`; the recorded last attempt is failed and produced no
  final outputs.
- FT local output namespace: `prognosis_analysis/output/ft_20260910_01a08bf3/`
- Tracked FT00 records: `prognosis_analysis/ft/FT00_protocol.json` and this file.

The pre-existing untracked FT scheme and worker contract were read as inputs and
were not modified. No formal project status file was changed.

## Frozen FT contract

The FT branch is bound to the full_A habitat and the existing A/B feature assets.
The frozen radiomics candidate pools are R_low=49 and R_high=10 with the W03
candidate hashes recorded in `FT00_protocol.json`. The seven prespecified models
are M0, M1, M2, M3L, M3H, M4 and M5. All models use Cox; high-dimensional models
use alpha=1. The A analysis uses ordinary single-layer 5-fold CV and reuses one
pre-frozen W07 split set, with repeat 1 preferred. The exploratory performance
label is:

`exploratory_fullA_habitat_non_nested_validation`

DFS is the primary endpoint with 3-year and 5-year evaluation horizons. The
prespecified A outputs and fixed model comparisons are listed below and in the
protocol JSON. Each comparison uses one common eligible population for both
models.

| Comparison | Common eligible population |
|---|---|
| M0 vs M1 | Main A modeling population |
| M0 vs M2 | Main A modeling population |
| M2 vs M3L | R_low eligible population |
| M2 vs M3H | R_high eligible population |
| M2 vs M4 | Dual-radiomics eligible population |
| M3L vs M3H | Dual-radiomics eligible population |
| M4 vs M5 | Intersection of dual-radiomics and W-available populations |

For M4 vs M5, the common population requires both R_low and R_high
availability and W availability. No full-A DFS-based univariate feature screening, habitat re-optimization,
candidate-pool change, split regeneration, or performance-informed parameter
change is allowed.

## State and lock checks

| Check | Result |
|---|---|
| `habitat_analysis/freeze_lock.json` exists and is valid JSON | PASS |
| Technical habitat freeze is true | PASS |
| Technical freeze `A_outcome_unlock=true` | PASS |
| Technical freeze `B_unlock=false` | PASS |
| Technical freeze `B_data_read=false` | PASS |
| Technical freeze `outcome_columns_read=false` | PASS |
| Technical freeze formal bootstrap is complete and eligible | PASS |
| W04 modeling protocol exists and is frozen | PASS |
| W07 split config is frozen with 50 validation folds and repeat 1 is the preferred frozen split reference | PASS |
| W07 split artifact hash matches the frozen record | PASS |
| W03 candidate counts and hashes match the frozen record | PASS |
| `prognosis_analysis/model_freeze_lock.json` is absent | PASS |
| `prognosis_analysis/execution_status.json` records all B access flags false | PASS |
| FT namespace is distinct from formal output namespaces | PASS |

The existing formal W08 `HOLD` state does not authorize FT to alter formal
outputs. FT00 writes only to its FT-scoped records and reserves the separate
local output namespace above for later FT stages.

## Isolation boundary

FT00 may read protocol, lock, status, configuration, candidate-freeze metadata,
W07 split metadata/hash, and the locked environment probe. FT00 does not read A
outcome data or any B source, feature, QC, clinical, outcome, missingness,
distribution, or performance data. No B reader is invoked and no B source is
opened.

The following remain outside the FT00 write boundary:

- `habitat_analysis/freeze_lock.json`
- `prognosis_analysis/modeling_protocol.json`
- `prognosis_analysis/execution_status.json`
- `prognosis_analysis/configs/w07_outer_splits.json`
- `prognosis_analysis/output/outer_splits_A.csv`
- `prognosis_analysis/model_freeze_lock.json`
- formal W08/L9 output namespaces
- all B assets

The FT model freeze lock is not created at FT00 and cannot authorize B access.
B access requires the later FT-specific amendment after FT04 review. No FT00
operation can unlock B.

## Validation evidence

The locked environment probe completed through the project wrapper:

```text
tools/run_t2_radiomics.ps1
```

The probe reported Python 3.7.12, PyRadiomics 3.0.1 and SimpleITK 2.2.1, with
`matches_locked_spec=true`. No Python analysis, model fitting, prediction,
performance calculation, feature extraction, or patient-level output was
performed for FT00.

The FT00 protocol records the SHA-256 references for the worker contract, FT
scheme, project state, project entry documents, current SOP, master protocol,
technical freeze and habitat/radiomics configurations, W02/W03 protocols and
assets, W04 protocol, execution status, W07 split configuration and artifact,
and W07A amendment. All 23 recorded source-reference hashes matched the local
files at FT00 validation.

## Git isolation evidence

- `codex/ft-validation` is based directly on the pre-FT baseline commit above
  and contains the two FT00 deliverables.
- `main` retains its published history; FT00 artifacts are removed there by
  normal, recoverable cleanup commit `b09306182e072d0d913d8820d849b4da54d7f1ba`.
- The dedicated branch is the only downstream handoff branch for later FT
  units.

## Conclusion

FT00 isolation and protocol freeze are complete. Formal W08/L9 semantics and
locks are unchanged, the formal model freeze lock remains absent, and B remains
locked.
