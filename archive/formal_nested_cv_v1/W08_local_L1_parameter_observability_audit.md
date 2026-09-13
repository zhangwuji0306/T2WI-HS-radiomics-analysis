# W08 local L1 parameter and observability audit

## Scope

This audit covers the shared frozen K-means contract, the aggregate-only W08
progress schema, and the formal result transaction sequence. It contains no
patient-level material, prediction values, performance results, or local
machine paths.

## Frozen parameter contract

The W08 formal provider, nested-CV frame provider, and technical preflight
continue to use the same immutable `KMEANS_PARAMETERS` object from
`prognosis_analysis/scripts/w08_kmeans_parameters.py`:

```text
algorithm=kmeans
k=2
initialization=k-means++
n_init=100
max_iter=300
tol=1e-4
```

The three production entry points still fail closed on missing, mistyped, or
changed frozen values. No scientific parameter, candidate pool, cohort, split,
solver, or B-access boundary is changed by this L1 remediation.

## Remediation A: terminal progress sequencing

The formal path now reaches `progress.status=complete` only after all of the
following have succeeded:

1. Result files are written to staging, validated, and promoted with the
   formal manifest as commit marker.
2. A terminal `attempt_state.json` records `status=complete` and
   `final_outputs_generated=true`.
3. The terminal `run_state.json` records the same completion semantics.
4. The terminal progress write records `status=complete`.

Any terminal write failure or external interruption closes the relevant attempt
and the root run/progress records with `status=failed`. If outputs had already
been promoted, they are moved into the failed-attempt archive before the
failure states are exposed; the root formal manifest and predictions are not
left as a success marker. The normal progress callback remains observational
only for the in-memory model result.

## Remediation B: closed progress schema

Progress validation now requires the exact allowed key set and closed values:

- `current_run` is restricted to the frozen W08 run registry;
- `status` and `stage` use fixed enumerations;
- repeat, fold, outer-fold, and per-fold run counts use bounded integer
  ranges and frozen totals;
- completion and initialization states use fixed field shapes;
- timestamps are finite and ordered, and elapsed time is non-negative;
- unknown keys, missing keys, patient identifiers, risk scores, metrics,
  performance text, and arbitrary run labels are rejected;
- all four B-access flags are always boolean `false`.

## Remediation C: fail-closed promotion windows

The formal promotion path marks the attempt as `promoting` before moving any
formal output. Any `BaseException`, including `KeyboardInterrupt`, during
promotion or post-promotion manifest validation leaves the exception visible
to the caller and routes the attempt through the failed-attempt closeout.
Already promoted root files are moved into the failed-attempt archive, and any
remaining staging tree is moved below that archive as intermediate evidence.
The root formal output names, complete manifest, and `.staging` directory are
therefore absent before the failed `attempt_state.json`, `run_state.json`, and
progress are published. A new attempt can be created after this closeout.

## Verification

- L1 progress/schema and callback regression: 7/7 passed.
- Transaction sequencing and terminal-state fault-injection regression: 15/15
  passed, covering attempt-state, run-state, final-progress, manifest-write,
  intermediate-promotion, manifest-promotion, and external-interruption
  failures.
- Direct W08 nested-CV, technical-preflight, and release-gate tests: 81/81
  passed.
- Combined L1 and direct W08 targeted regression: 103/103 passed.
- `compileall` passed for the three W08 production modules and two direct L1
  test modules.
- `git diff --check` passed.
- The changed path set is limited to the formal W08 adapter, direct L1/schema
  and transaction tests, and this audit.
- No formal W08 run, real outcome read, B read, formal prediction, or formal
  performance output was generated.

## Access status

`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
`B_statistics_generated=false`.
