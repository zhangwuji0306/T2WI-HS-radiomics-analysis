# W07 Source Binding Remediation Audit

## Scope

W07 accepts only the W06 A modeling-population artifact. This remediation
closes the source-path validation gap without changing the split design or
reading any B data.

## Frozen W06 binding

The W07 configuration binds the input to these W06 artifacts:

- Source: `prognosis_analysis/output/A_modeling/A_modeling_population.csv`
- Schema: `prognosis_analysis/output/A_modeling/A_modeling_population_schema.json`
- W06 audit: `prognosis_analysis/output/A_endpoint_qc/endpoint_qc_summary.json`
- Source SHA-256: `5c93441f535ba86d965c3da14b4b33fe52f73d4337cd15a670b3ca2b8a2c23e4`
- Schema SHA-256: `41f6a6ac69bc0727755817d1e3e6902e24c612c00d6c88f52c4c2f42904039c6`
- W06 audit SHA-256: `0814082014600935922d3b082b678217b81aef710b3efe62a2103a67a85ae319`

Before `read_csv` is called, W07 verifies:

1. The supplied path is the configured A source path, including its resolved
   filesystem target.
2. The source, schema, and W06 audit hashes match the frozen configuration.
3. The W06 schema has the expected file name, columns, row count, and
   eligibility source.
4. The W06 audit is a W06 endpoint-QC summary whose source hash and aggregate
   counts match the frozen A393 contract.

## Rejection coverage

The regression suite rejects a valid-looking
`untrusted_source/A_modeling_population.csv`, rejects a modified file at the
authorized source name, rejects a modified W06 schema, and retains the
pre-existing B-named input rejection. All four cases fail before the source
CSV is loaded by pandas.

## Compatibility and access boundary

The frozen contract remains 393 cases, 89 DFS events, 304 censored cases,
5-fold × 10-repeat stratified outer CV, 50 validation folds, and 19,650 split
rows. The existing outer split hash remains
`24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.

W07 reads only the bound W06 A artifacts. No B source, B clinical data, B
radiomics data, B QC data, or B-derived statistics were read.

## Verification

- `python -m unittest tests.test_w07_outer_splits -v`: 10 tests passed.
- `python prognosis_analysis/scripts/w07_outer_splits.py`: completed with the
  frozen counts and split hash above; all B access flags were `false`.
- `python -m py_compile prognosis_analysis/scripts/w07_outer_splits.py tests/test_w07_outer_splits.py`: passed.
- `python -m json.tool prognosis_analysis/configs/w07_outer_splits.json`: passed.
