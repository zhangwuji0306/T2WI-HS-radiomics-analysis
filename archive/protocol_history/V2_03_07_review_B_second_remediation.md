# V2-03～V2-07 Reviewer B 第二次补救复审记录

## 审查范围

本复审仅覆盖 Primary v2 的 V2-03～V2-07 第二次补救结果：提交 `a19a734`、当前 `prognosis_analysis/primary/` 实际代码与 JSON、既有 Reviewer B 记录，以及已接受的 V2-00～V2-02 合同。未修改被审查代码、JSON、测试或历史 Reviewer 记录；未执行 V2-08 及以后；未将输出目录、原始影像、临床/病理/预后表或患者级数据作为审查输入。

## 已确认通过项

- `a19a734` 仅修改 `prognosis_analysis/primary/validate_external.py` 和 `prognosis_analysis/primary/test_equivalence.py`；未见本提交把输出目录或患者级材料纳入版本范围。
- 当前 manifest、canonical lock、external registration 的直接验证通过；`final_report.build_final_report` 对三者执行完整 provenance 校验并通过。FT03/FT04/FT06 source ref、commit、path、hash 未变；B=107 与 FT06 B=163 仍明确区分。
- AST/JSON 解析、`compileall` 和 `git diff --check` 通过。
- 第二次补救新增的合成边界测试分别通过：B completeness、registration builder self-validation、promotion metadata negative test、runtime model identity negative test、cohort identity negative test。B completeness 测试确认正确 FT06 token/hash 下 163 行可通过，1、162、164 行、重复 ID、错误 frame attrs、跨 cohort 字段和 B107 身份均被拒绝；163 行内的 model-specific eligible 子集仍可计算。
- `validate_frozen_b_predictors` 当前顺序为完整 registration/manifest、B token/hash、B=163 行数及 attrs 检查，再执行 predictor schema 和 eligibility；`predict_frozen` 委托该入口。builder 直接写入 `patient_level_predictions_copied=false` 与 `patient_level_metrics_copied=false`，其生成对象可通过 `validate_external_registration`，篡改这两个字段会被拒绝。
- 当前 active Primary v2 合同仍为 single repeat-1 five-fold、training-only preprocessing/lambda、`alpha=1`、fixed full-A habitat、B frozen prediction only；M5 population 为 `W_Original_available`。canonical lock/runtime gate 登记并校验 `model_id`、`population`、`model_input_hash`、transformed feature order hash 和 `state_sha256`。受保护 FT04 coefficients、risk predictions、metrics 跨记录数值等价性仍透明保持 `NOT EVALUATED`，本复审未将其单独作为阻断项。

## 阻断发现

### 1. 锁定分析环境中的合成等价性和 canonical runner 不可运行

在项目规定的 `t2_radiomics` 环境（Python 3.7.12、pandas 1.3.5）中直接运行：

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-B','prognosis_analysis/primary/test_equivalence.py')
```

在 `prognosis_analysis/primary/validate_assets.py:299-305` 的 `canonical_frame_hash` 处抛出：

```text
TypeError: to_csv() got an unexpected keyword argument 'lineterminator'
```

`prognosis_analysis/primary/run_cv.py:474` 的 canonical A runner 每次运行都会调用该函数，因此 `run_equivalence_checks` 在模型/折叠等价性检查前即失败。该代码由此前提交引入而非 `a19a734` 新增，但当前第二次补救结果在锁定环境中仍未满足强制的“合成等价性通过”条件，也不能作为 V2-08 的可靠运行入口。

全仓库锁定环境回归测试结果为 316 tests、2 failures、8 errors；其中多项历史 provenance/R6 测试另有既有工作区绑定不一致。本条阻断判断以 Primary v2 合成等价性和 canonical runner 的直接失败为依据，不把那些无关历史测试单独升级为本复审阻断项。

### 2. `evaluate_frozen_predictions` 构成未经过同一 completeness gate 的 B 入口

`prognosis_analysis/primary/validate_external.py:271-308` 的公开函数 `evaluate_frozen_predictions` 未调用 `validate_frozen_b_predictors` 或 `_validate_b_frame_completeness`，也未校验 registration、manifest、B token/hash、B=163 基础 frame 完整性或 gate 中的 `B_base_frame_n`。它仅检查 `predictions.attrs["frozen_prediction_only"]`、模型 ID，以及传入 outcome frame 的 eligible ID 集合。

使用一行脱敏合成 B outcome frame 和手工设置的 `frozen_prediction_only=True`、`model_id="M0"` 的一行 prediction，实际函数返回：

```text
eligible_n=1, DFS_events=1
```

因此公开 B 评价入口仍可在不完整 frame、无 FT06 B=163 绑定且仅凭可伪造属性的情况下生成评价结果。该行为违反“所有 B 入口必须经过同一完整性 gate”的要求，存在下游分母污染和伪造 frozen-prediction provenance 的风险。`predict_frozen` 本身已通过完整 gate，不足以消除该独立公开入口的旁路。

## 下游交接结论

B=163 predictor completeness 修复、builder 自洽性、final-report provenance、A393 exact identity、runtime identity、M5 token、FT evidence promotion 和隐私范围在本次检查中均保持正确；但锁定环境的 canonical runner 失败，以及 B evaluation 入口绕过统一 completeness gate，仍是实质性缺口。

## 语义 disposition

**not accepted for downstream use**

## 进入 V2-08～V2-12 的条件

1. 使 Primary v2 canonical runner 在项目锁定的 `t2_radiomics` 环境中可运行，并重新通过合成等价性、B completeness、builder self-validation、metadata/runtime negative tests、AST/JSON/compile 与 `git diff --check`。
2. 使 `evaluate_frozen_predictions` 复用同一完整 B gate，或只接受由该 gate 产生且不可伪造/可验证绑定的 gate 状态；不允许仅依赖 `frozen_prediction_only` 属性或 eligible ID 集合。
3. 继续透明保留受保护 FT04 coefficients、risk predictions、metrics 跨记录数值等价性的 `NOT EVALUATED` 状态，不得据此伪称已完成。
