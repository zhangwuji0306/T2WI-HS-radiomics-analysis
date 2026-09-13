# W08 implementation audit

## Scope

This audit covers the code and protocol contract for W08 A-only repeated
nested cross-validation. It does not represent a formal patient-level W08
analysis and contains no patient-level results.

## Source and method locks

- W04 protocol SHA-256: `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`.
- W07 outer split SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.
- W06 A population and its schema/audit are inherited through the code-level
  binding in `w07_outer_splits.py`; runtime JSON cannot redirect them.
- R_low and R_high candidate hashes are recorded from the frozen W03 pools.

## Code-level controls

1. `run_w08` accepts only the project-locked W08 config, reads only the
   code-bound W06 A population and W07 `outer_splits_A.csv`, verifies both
   provenance contracts, and passes the feature table through an in-memory
   A-only boundary.
2. Non-A rows, non-A393 cohorts, ID mismatches, invalid DFS values, and
   non-explicit radiomics availability are hard failures.
3. The fixed run registry includes the W04 model set plus the W07-paired M0/M2
   comparator populations; no comparison is reconstructed from an outer-fold
   result after fitting.
4. A `FoldFeatureProvider` is mandatory and must expose fold-specific habitat
   fitting. Provider fitting receives only outer-training IDs; validation is
   transformed with the returned state and cannot enter representation fitting.
5. Inner CV is stratified five-fold and is constructed only from the current
   outer-training frame. Candidate records retain inner train/validation ID
   hashes and count every alpha/lambda attempt.
6. Clinical imputation/scaling, radiomics imputation, variance filtering,
   correlation reduction, scaling, alpha, lambda and coefficient selection are
   fitted inside the relevant training scope.
7. Stable risk-set sums, bounded exponentiation and deterministic backtracking
   provide the minimum recorded numerical-stability path for low penalties;
   candidates are not deleted and folds are not skipped.
8. Results are returned in memory. No W08 patient-level artifact, model freeze
   lock, or B validation artifact is created.

## Synthetic verification contract

The test suite exercises all seven W04 model definitions on synthetic A-like
frames, provider training/validation isolation, inner-only selection, fixed
split hash propagation, explicit availability handling, B-row/path rejection,
and low-penalty candidate accounting. The formal 50-fold run is not invoked.

## Access status

`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
`B_statistics_generated=false`.
