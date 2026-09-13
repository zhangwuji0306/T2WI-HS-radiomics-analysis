# FT B Outcome Access Amendment

Status: `AUTHORIZED`

The FT04 frozen model lock is valid and remains B-locked until this FT05B
authorization. FT05A is scientifically frozen under
`FT05A_scientific_freeze_amendment.md`; its accepted technical audit is
`accepted / PASS`.

The frozen outcome-blind technical assets are retained only in the ignored
local FT05A output namespace:

- Feature table: `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/FT05A_B_technical_features.csv`
  - SHA-256: `10b35d9d661da665bfe98e95dbefa34a6b0e9c0d911bae37a34f3d635ab5d804`
- Feature manifest: `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/.finalize/FT05_B_feature_manifest.json`
  - SHA-256: `055bdf0e98d05ed4c4e0b8ae2c175d5e82d66ba484ebec30b4b8c04c9e0eb251`

The table and manifest are complete for 163 unique B technical cases. The
completion evidence SHA-256 is
`1f70e474ef2dcf42c875630a309fd9f27d88bb9342d5ea60a44d7e1b85ecd585`, the
row-schema SHA-256 is
`3aa6dbec948a52da64aaab74367ab797e340ee0348e10acdf433b79595ba9e19`, and
the FT04 lock identity SHA-256 is
`10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.

The only FT05B authorization entry is
`prognosis_analysis/ft/ft05b_runner.py::validate_ft05b_gate`. It validates the
FROZEN/VALID FT04 lock, absence of the formal model lock, the accepted FT05A
technical audit and scientific amendment, the exact ignored `.finalize`
manifest/table bytes, 163 unique ordered B technical rows, the candidate and
W_Original contracts, and the FT_B_unlock hash/scope bindings. It fails closed
on the former canonical manifest path, any hash/schema/order/uniqueness
mismatch, and any disabled or out-of-scope unlock.

After the gate passes, `ft05b_runner.py::read_b_dfs` uses the existing
allow-list/streaming primitive and requests only `影像号`, `DFS_time`, and
`DFS_event`. It does not call the formal `read_B_validation` reader or
`require_b_unlock`; the in-memory source frame is reduced to aggregate counts
and is not persisted. Access is authorized only for FT06 frozen-model
prediction/evaluation. B fitting, tuning, feature selection, K-means fit,
cutoff change, preprocessing estimation, and radiomics re-extraction remain
prohibited.
