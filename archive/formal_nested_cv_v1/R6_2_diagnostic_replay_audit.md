# R6-2 first-failure diagnostic replay audit

## Disposition

`REPRODUCED_FIRST_FAILURE`。本次诊断在冻结 W07 外层序列的首次 Elastic-Net Cox 失败处停止，未执行正式 W08 重跑、性能评估、W09 或模型冻结。

R6-3 建议分类：**Class C — 冻结 Elastic-Net solver 的收敛/迭代预算失败**。

证据为：冻结内层 CV 已完成并给出候选；失败发生在 `outer_final_refit`，迭代达到冻结的 `max_iter=250`，状态为 `non_converged`，失败原因为 `iteration_budget_exhausted`。未发现 B 访问、队列漂移、W07 split 变化、参数修改或环境版本不匹配证据。该分类仅供 R6-3 protocol-owner disposition，不构成 solver remediation 或正式重跑授权。

## First failure context

| Field | Value |
|---|---|
| Replay status | `reproduced_first_failure` |
| Repeat / outer fold | `1 / 1` |
| Run / model | `M3H / M3H` |
| Population | `R_high` |
| Inner seed | `13346` |
| Outer training | `n=282`, events=`66` |
| Outer validation | `n=67`, events=`15` |
| Post-preprocessing features | `p=25`; `C=13`, `G=6`, `R_high=6` |
| Selected alpha | `0.5` (`alpha_index=1`) |
| Selected lambda ratio | `0.009545484566618337` (`lambda_index=50`, frozen 100-point geometric grid) |
| Outer lambda max / final lambda | `1.0523593768634127 / 0.010045280190385798` |
| Selected inner score | `0.6985414043308824` |
| Failure stage | `outer_final_refit` |
| Iterations | `250` |
| Convergence status / reason | `non_converged` / `null` |
| Failure reason | `iteration_budget_exhausted` |
| Stability actions | `backtrack_objective`, `iteration_budget_exhausted` |
| Backtracking / clipping | `81 / 0` |
| Last objective | `5.020749966374221` |
| Objective improvement / coefficient delta | `2.817007144439998e-05 / 0.002386203181961477` |
| Non-zero coefficient count | `null` |

The replay completed the eight preceding fixed runs in the same first outer fold (`M0`, `M1`, `M2`, `M0_W_available`, `M5`, `M2_R_low`, `M3L`, `M2_R_high`) and stopped before the next run. No outer risk score, held-out prediction, C-index, AUC, Brier, calibration, or performance comparison was generated.

## Frozen bindings

| Binding | SHA-256 / value |
|---|---|
| W04 modeling protocol | `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe` |
| W07 outer split artifact | `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` |
| W07A protocol amendment | `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70` |
| W08 nested-CV config | `f432b9741071a37be37fb63361e2007978ee6f47d4ce269b36a8692aa4fcbe7a` |
| R6-1 solver source SHA-256 | `8f97fcc01cd7c821dd88468bd090d0ae6735018cdda775be491ae7d5b03026fb` |
| Code commit | `ae92f7cbbaf2ab5bfb608ab029ab0566d7203c55` |
| R_low candidate hash | `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` |
| R_high candidate hash | `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` |
| Solver bindings | `max_iter=250`, `tolerance=1e-7`, alpha grid `[0.1, 0.5, 0.9, 1.0]`, 100 lambda values/alpha, minimum ratio `1e-4` |

The locked `t2_radiomics` environment passed the project probe: Python `3.7.12`, NumPy `1.21.6`, pandas `1.3.5`, SciPy `1.7.3`, scikit-learn `1.0.2`, PyRadiomics `3.0.1`, SimpleITK `2.2.1`, and all other locked versions matched.

## Access and output state

| State | Result |
|---|---|
| `B_data_read` | `false` |
| `B_reader_invoked` | `false` |
| `B_source_opened` | `false` |
| `B_statistics_generated` | `false` |
| Formal W08 | failed; gate remains `HOLD` |
| Formal final outputs | absent |
| Performance outputs | not generated |
| W09 | not executed; no artifacts |
| `model_freeze_lock.json` | absent |
| Historical failed archive | preserved; not rewritten |

## Command and outputs

Command:

```text
tools\run_t2_radiomics.ps1 -PythonArguments @('prognosis_analysis/scripts/_r6_2_diagnostic_replay.py')
```

Elapsed time: `19814.325 s` (approximately 5 h 30 min 14 s).

De-identified aggregate diagnostic output:

`prognosis_analysis/output/r6_2_diagnostic_replay/r6_2_diagnostic_replay.json`

The replay reused the preserved local SLIC cache for 393 A cases and wrote no patient-level diagnostic table or repository-visible patient data.

## Locked-environment targeted-test evidence

The following command was executed twice through the repository environment wrapper:

```text
& .\tools\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_w08_nested_cv','tests.test_w08_transactional_outputs','tests.test_w08_formal_release_gate','tests.test_w08_technical_preflight_a')
```

Run 1 stdout and exit status:

```text
......................................................................
----------------------------------------------------------------------
Ran 70 tests in 152.251s

OK
{"B_data_read": false, "attempt_id": "attempt_1788696136913808_c1f7ea7f549a", "elapsed_seconds": 0.083, "n_fold_results": 1, "n_predictions": 1, "output_root": "prognosis_analysis/output/w08_formal_A", "stage": "W08", "status": "formal_complete"}
exit_code=0
```

Run 2 stdout and exit status:

```text
......................................................................
----------------------------------------------------------------------
Ran 70 tests in 158.501s

OK
{"B_data_read": false, "attempt_id": "attempt_1788696227455762_55bb7dd42d0c", "elapsed_seconds": 0.054, "n_fold_results": 1, "n_predictions": 1, "output_root": "prognosis_analysis/output/w08_formal_A", "stage": "W08", "status": "formal_complete"}
exit_code=0
```

The runner-status lines above are emitted by synthetic transactional test fixtures; they are not a formal patient-level W08 run, do not authorize W08 release, and do not represent formal predictions or performance outputs.

## Baseline observations retained

The previously recorded full-test observations remain baseline findings: the Pre-W08 SOP snapshot mismatch and tests that still expect the historical minimum-ROI summary. They are not reclassified as an environment failure and were not “fixed” by changing historical provenance, `execution_status`, the SOP snapshot, or scientific parameters.
