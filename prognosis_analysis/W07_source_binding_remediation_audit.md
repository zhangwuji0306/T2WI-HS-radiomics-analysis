# W07 Source Binding Remediation Audit

## Scope

W07 consumes only the audited W06 A modeling-population artifact. Its A-only
source authorization is fixed in `prognosis_analysis/scripts/w07_outer_splits.py`
and cannot be redefined by a runtime configuration file.

## Frozen W06 provenance

The code-level project lock fixes these artifacts and SHA-256 values:

- Source: `prognosis_analysis/output/A_modeling/A_modeling_population.csv`
- Schema: `prognosis_analysis/output/A_modeling/A_modeling_population_schema.json`
- W06 audit: `prognosis_analysis/output/A_endpoint_qc/endpoint_qc_summary.json`
- Source SHA-256: `5c93441f535ba86d965c3da14b4b33fe52f73d4337cd15a670b3ca2b8a2c23e4`
- Schema SHA-256: `41f6a6ac69bc0727755817d1e3e6902e24c612c00d6c88f52c4c2f42904039c6`
- W06 audit SHA-256: `0814082014600935922d3b082b678217b81aef710b3efe62a2103a67a85ae319`

The checked-in JSON retains the same values for audit readability. W07 accepts
only the project-locked configuration path, validates its provenance fields
against the code-level lock, and performs all artifact path, resolved-target,
hash, schema, and W06 audit checks against that lock. The source CSV is opened
only after these checks pass.

## Rejection coverage

The regression suite rejects:

- a self-consistent custom configuration with a fabricated W06 source,
  schema, audit, and matching hashes;
- an A-modeling file with an untrusted same-name path;
- source, schema, or W06 audit content whose hash differs from the lock; and
- a B-named input.

Each rejection occurs before `pandas.read_csv` is called.

## Compatibility and access boundary

The frozen contract remains 393 cases, 89 DFS events, 304 censored cases,
5-fold × 10-repeat stratified outer CV, 50 validation folds, and 19,650 split
rows. The existing local split artifact remains
`24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.

The existing split artifact was validated read-only against the code-locked
W06 population; it was not regenerated. `B_data_read=false`.

## Verification

- `python -m unittest tests.test_w07_outer_splits -v`: 12 tests passed.
- A-only/W06 and B-isolation regressions: 39 tests passed.
- Read-only W07 artifact validation: 393/89/304, 19,650 rows, 50 folds, and
  the split hash above passed.
- `python -m py_compile prognosis_analysis/scripts/w07_outer_splits.py tests/test_w07_outer_splits.py`: passed.
- `python -m json.tool prognosis_analysis/configs/w07_outer_splits.json`: passed.
- Static forbidden-reader scan for W07: passed.

The current system Python reports `ModuleNotFoundError: No module named
'SimpleITK'`; this unrelated environment limitation does not affect W07,
which does not import or use SimpleITK.
