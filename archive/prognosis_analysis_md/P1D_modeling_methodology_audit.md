# P1D Clinical model 与 penalty methodology audit

## 审计结论

**P1D：条件通过，正式 W08 前保持 HOLD。**

- Clinical block 的 membership 与 W04 一致：固定 9 个临床 predictor；未发现当前代码、配置或冻结文档存在基于 A outcome 的 univariate screening、P 值删变量或 HR 删变量路径。
- M0/M1/M2 的 primary architecture 可以保持不变，但 M2 的事件数/设计列比最低，存在估计不稳定和收敛风险。建议预先冻结 M0-R、M1-R、M2-R 作为 stability sensitivity；敏感性模型不得改写 primary architecture。
- 现行实现对 M3L/M3H/M4 的全部 C+G+R 系数共同施加 Elastic Net penalty；配置和方法文档只写了 `Elastic-Net Cox`，没有显式写出 block-level penalty mask。因此，操作语义明确，但正式协议语义尚不完整，必须在正式 W08 前冻结并记录。
- 本审计未运行正式 W08、Cox 性能、预测、模型选择或任何 B reader；未修改代码、正式协议或 P2 文件。

## 数据边界与审计对象

本审计仅核对以下非识别性材料：W04 modeling protocol、W08 配置与实现、W08 synthetic-test 结构、W07 外层分层汇总、W06 A-side endpoint 汇总及既有审计报告。报告只保留聚合计数、设计列数和方法学结论，不包含患者 ID、真实影像号、临床原始值、患者级表或可逆标识。

W08 当前状态为 `implementation_ready_not_run`；既有 W08 preflight 未产生预测、指标或正式模型结果。

## 1. Clinical predictors 与 design-matrix df

### 1.1 Membership

固定 clinical block `C` 包含且仅包含：

| Clinical predictor | 处理方式 | 系数列贡献 |
| --- | --- | ---: |
| 年龄 | 连续变量，training-only median imputation 与 scaling | 1 |
| CEA_log | 连续变量，training-only median imputation 与 scaling | 1 |
| mrT | 预声明 4 个水平，最低水平为 reference；one-hot | 3 |
| mrN | 预声明 4 个水平，最低水平为 reference；one-hot | 3 |
| MRF | 二元变量 | 1 |
| mrEMVI | 二元变量 | 1 |
| thickness | 连续变量，training-only median imputation 与 scaling | 1 |
| EID | 连续变量，training-only median imputation 与 scaling | 1 |
| 活检病理非腺癌 | 二元变量 | 1 |
| **合计** | **9 个 clinical predictors** | **13** |

代码中的实际系数列为：4 个连续列、`mrT_4级=2/3/4` 三列、`mrN_3级=1/2/3` 三列，以及 3 个二元列。没有截距项。最低预声明水平作为 reference，不由 outcome 决定。

### 1.2 各模型设计列数

下表中的 M0/M1/M2 为实际且固定的低维 design-matrix df；高维模型列数为 radiomics training-only 过滤前的名义列数，正式外层运行后可能因非有限值、近零方差和相关性规则而减少。

| Model | Block membership | 设计列数 |
| --- | --- | ---: |
| M0 | C | **13** |
| M1 | C + `H_high_fraction` | **14** |
| M2 | C + G（6 个 global descriptors） | **19** |
| M3L | C + G + R_low（49 个冻结候选） | 68（过滤前） |
| M3H | C + G + R_high（10 个冻结候选） | 29（过滤前） |
| M4 | C + G + R_low + R_high | 78（过滤前） |

M0/M1/M2 不执行 radiomics 过滤，故其 13/14/19 为实际设计列数。W08 formal 尚未运行，不能将高维模型的过滤后每折列数或 selected-feature df 报告为已观测结果。

### 1.3 Outcome-based screening 核对

核对结果为 **PASS**：

- W04 将 C block 固定为上述 9 个变量，并把分类 reference level 预先声明为最低水平。
- W04/W08 配置显式记录 `univariate_outcome_feature_ranking=false`。
- W08 clinical preprocessor 只读取固定的 `CLINICAL_COLUMNS`，没有按单变量 Cox 结果、P 值或 HR 结果重建列集合。
- 高维候选的 alpha/lambda 只在当前 outer-training 内进行 inner-CV 选择；radiomics 的非零系数选择也发生在 training-only tuned fit 内，不是 outcome-based univariate ranking。
- W08 记录 `outer_validation_used_for_selection=false`，且外层验证不参与 preprocessing、feature selection、alpha 或 lambda。

该结论是对当前冻结协议、实现和测试结构的静态方法学审计；由于正式 W08 尚未运行，不包含任何正式性能结果的反向核验。

## 2. M0/M1/M2 未惩罚 Cox 稳定性

### 2.1 事件规模与 df

W06/W07 的 A-side 聚合汇总为 393 例、89 个 DFS events、304 个 censored observations。固定 5-fold × 10-repeat 外层分层方案中，每个训练折包含 314 或 315 例、71–72 个 events；每个验证折包含 78 或 79 例、17–18 个 events；50 个外层折均通过至少 1 个 event 的门禁。

| Model | 设计 df | 全部 89 events / df | 外层训练 events / df（范围） |
| --- | ---: | ---: | ---: |
| M0 | 13 | 6.85 | 5.46–5.54 |
| M1 | 14 | 6.36 | 5.07–5.14 |
| M2 | 19 | 4.68 | 3.74–3.79 |

这些比值是稳定性描述，不是单独的通过阈值。M2 的 19 个设计列对应较低的事件/df，且分类列之间的相关性、稀疏水平或近分离都可能进一步放大系数不确定性。当前范围没有读取临床原始值，因此不对具体水平稀疏性作病例级判断。

### 2.2 实现层面的风险判定

当前 `CoxPHModel` 的统计目标仍是未惩罚 Breslow partial likelihood。拟合时加入的极小 ridge 仅用于 Newton 信息矩阵求解的数值稳定化，未加入 Cox objective，因此不等同于统计意义上的 ridge regularization，也不能消除 M0/M1/M2 的估计不稳定风险。

结论：primary M0/M1/M2 规格可继续保持 W04 定义，但在正式 W08 前应冻结并执行独立的 ridge stability sensitivity。敏感性模型只用于判断 primary 结论的稳健性，不用于重新选择模型架构、删除 clinical predictor 或改变比较层级。

### 2.3 预先冻结的 M0-R/M1-R/M2-R 方案

建议在正式性能出现前按以下规则冻结：

1. `M0-R = C`、`M1-R = C + H_high_fraction`、`M2-R = C + G`；分别使用与 M0/M1/M2 相同的 A-side population、W07 外层 split、训练-only preprocessing 和 paired estimand。
2. Clinical membership、分类 reference、imputation 与 scaling 完全不变；9 个原 clinical predictors 全部保留，不执行 univariate screening、P 值删变量、HR 删变量或系数阈值删变量。
3. 使用纯 ridge Cox（L2，`alpha=0`），不做系数置零式 feature selection。建议统一采用当前 per-event negative partial log-likelihood 标度，并预先定义 training-only ridge scale：在每个 inner-training set 的 `beta=0` 处计算 event-normalized observed information `I0`，令 `lambda_ref = trace(I0) / p`；若 `lambda_ref` 非正则 hard fail，不改用验证集或全体数据兜底。
4. 在每个 outer fold 内，仅使用 outer-training 数据建立 inner 5-fold、event-stratified CV。对 `lambda / lambda_ref` 使用预先固定的 log-spaced 网格 `10^4` 至 `10^-4`（100 个候选）；以 mean inner-validation Uno C-index 选择，平局时选择较大 lambda。完成选择后，使用 outer-training 重新计算 `lambda_ref`，按选定的相对位置获得 outer-training refit lambda。
5. Outer validation 只接受最终 outer-training refit 的预测，不参与 lambda scale、lambda selection、预处理或任何变量保留决策。报告时与对应 primary M0/M1/M2 并列为 stability sensitivity，不改变 W11 的 primary architecture rule。

该方案需要在 P2/W07A amendment 中以冻结文本记录后，才可由后续实现分包编码；本 P1D 不修改 P2 文件。

## 3. M3L/M3H/M4 penalty semantics

### 3.1 当前实现、配置和文档的口径

| 层级 | 当前证据 | 审计结论 |
| --- | --- | --- |
| 实现 | `ModelPreprocessor` 先拼接 C、G、R；`_fit_outer_model` 将完整 `X_train` 传给 `CoxElasticNetModel`；`_objective` 对完整 `beta` 计算 L1 与 L2，proximal step 也对完整向量施加阈值；没有 penalty mask 或 exempt-block 参数 | **C、G、R 全部共同接受 Elastic Net penalty** |
| 配置 | M3L/M3H/M4 只声明 `family: Elastic_Net_Cox`、alpha/lambda 网格和 training-only 选择；没有 `penalty_mask`、`unpenalized_blocks` 或 C/G exemption 字段 | 未显式定义 block-level 语义 |
| 文档 | W04/W08 写明 `Elastic-Net Cox`、penalized Cox partial likelihood 和非零系数选择，但没有说明 C/G 是否免罚 | 正式协议文字不完整 |

因此，当前**实际运行语义**是：

```text
M3L: C + G + R_low 全部接受 Elastic Net penalty
M3H: C + G + R_high 全部接受 Elastic Net penalty
M4:  C + G + R_low + R_high 全部接受 Elastic Net penalty
```

这不是“C+G 固定、仅 R 接受 penalty”的实现。需要注意，当前实现中的 C/G/R 特征经过不同的预处理；“共同接受 penalty”指其进入同一个完整 coefficient vector 并使用同一 alpha/lambda 目标，不表示原始量纲相同。

### 3.2 正式 W08 前必须冻结的决定

P2/W07A amendment 至少应明确写出：

- 选择保留当前实现的全向量 penalty，还是改为 C/G unpenalized、仅 R penalized；
- penalty 的对象是原始 predictor block 还是 preprocessing 后的 coefficient columns；
- alpha/lambda 是否对所有受罚列共享，以及 C/G 若免罚时是否仍保留在同一 Cox objective；
- 该决定的生效时间为 W06/W07 之后、任何正式 W08 prediction/performance 之前，且不得由正式性能反推。

若保留当前实现，最小修订是把“C+G+R 全部共同接受 Elastic Net penalty”写入 amendment/config audit，并保持 primary architecture 不变。若改为只惩罚 R，则属于 semantics change：必须先更新 amendment 和实现，再通过 synthetic test，之后才可正式 W08；本审计不实施该改变。

### 3.3 Synthetic-test 要求

在后续实现分包中应增加不含真实数据的语义测试：

1. 构造带有显式 C、G、R 标签的确定性设计矩阵，验证当前全向量实现的 objective penalty 等于对完整 coefficient vector 计算的 `L1 + L2` 项；并验证 proximal threshold 覆盖 C、G、R 三个 block。
2. 若 amendment 选择 R-only penalty，使用同一 synthetic matrix 验证 C/G 系数改变不会增加 penalty，而 R 系数改变会增加 penalty；同时验证 C/G 仍进入 Cox partial likelihood。
3. 用相同 outer-training、不同 outer-validation synthetic outcome/预测输入验证 alpha/lambda 选择只依赖 inner-training/inner-validation，不依赖 outer validation。
4. 验证 M0-R/M1-R/M2-R 的 clinical column 名称与 primary 完全相同，且任何 ridge lambda 选择都不会删除原 clinical predictors。

## 4. 访问与产物状态

| Control | 状态 |
| --- | --- |
| `B_data_read` | `false` |
| `B_reader_invoked` | `false` |
| `B_source_opened` | `false` |
| `B_statistics_generated` | `false` |
| 正式 W08 prediction/performance | 未运行 |
| `model_freeze_lock.json` | 未生成 |

## 证据登记

- `prognosis_analysis/modeling_protocol.json`
- `prognosis_analysis/modeling_protocol.md`
- `prognosis_analysis/configs/w08_nested_cv.json`
- `prognosis_analysis/scripts/w08_nested_cv.py`
- `prognosis_analysis/scripts/w08_formal_run_a.py`
- `prognosis_analysis/W07_outer_splits_protocol.md`
- `prognosis_analysis/W08_nested_cv_protocol.md`
- `prognosis_analysis/W08_implementation_audit.md`
- `prognosis_analysis/W08_preflight_execution_audit.md`
- `prognosis_analysis/P1C_fold_specific_extractability_audit.md`
- `prognosis_analysis/output/A_endpoint_qc/endpoint_qc_summary.json`
- `prognosis_analysis/output/A_endpoint_qc/outcome_read_audit.json`
