# T2WI-HS-radiomics-analysis
# Primary Prognostic Analysis v2 正式分析方案书与串行执行工作流

## 版本定位

方案名称：

**Primary Prognostic Analysis v2 — Frozen Full-A Habitat Validation**

简称：

**Primary v2**

本方案自批准后替代既往以 repeated nested CV、fold-specific habitat reconstruction 为核心的 Formal W08 v1，成为项目唯一正式预后分析主线。

旧 Formal W08 v1 不删除，仅作为：

`superseded formal methodology`

归档保存。

原 FT 分析不再作为独立“快速验证”继续发展，其科学框架经本方案重新定义后成为 Primary v2 的方法学来源；FT 的开发、审计和事故恢复历史仍作为历史证据归档。

---

# 第一部分：方法学转换背景

## 1. 原 Formal W08 v1 的状态

截至本次换轨决策，原正式分析仍处于：

`W08 / HOLD`

最后一次 formal W08 未产生最终正式结果，正式 model freeze 尚不存在。

因此，本次调整发生在旧正式主分析尚未成功完成之前，不属于对已经发表或已经正式冻结主结果的事后替换。

---

## 2. 原 W08 v1 的主要问题

原 W08 采用高度严格的 repeated nested validation：

- 5-fold × 10 repeats，共 50 个 outer folds；
- 每个 outer-training fold 独立重新拟合 K=2 habitat centers；
- 每个 fold 重新计算 boundary；
- 根据 fold-specific boundary 重建 H-low/H-high；
- 重新生成 G；
- 重新生成 R_low/R_high；
- 高维模型再进行 inner CV；
- Elastic-Net 搜索 4 个 alpha × 100 个 lambda。

这一设计具有很强的统计隔离能力，但存在三个实际问题：

### 2.1 计算负担过大

habitat reconstruction、radiomics generation 和高维调参均嵌入 50 个 outer folds，运行成本和工程复杂度显著超过本研究实际需要。

### 2.2 临床解释不直观

同一患者的 H-high/H-low 定义会随训练 fold 改变。

换言之：

> H-high 不再是固定影像表型，而是训练子样本的函数。

这不利于最终形成可以被临床理解和复现的固定 MRI habitat phenotype。

### 2.3 方法复杂度超过核心科学问题需要

本研究真正的问题并不是：

> 不同随机训练子集中重新定义 habitat 后，模型平均性能如何？

而是：

> 一个固定、可解释、技术上冻结的 MRI habitat phenotype 是否携带可重复的预后信息？

因此 Primary v2 改用固定 full-A habitat。

---

# 第二部分：Primary v2 核心科学问题

本研究的正式科学问题定义为：

> 在治疗前 T2WI MRI 中，通过预先固定的 3D SLIC + cross-case K-means 方法得到的 H-low/H-high habitat，以及相应 habitat-specific radiomics，是否能够在临床变量基础上提供具有外部可重复性的 DFS 预后信息？

Primary endpoint：

**Disease-Free Survival, DFS**

固定评价时间：

- 3 years
- 5 years

OS/CSS 如后续分析，仅作为 secondary/exploratory endpoint，不参与 Primary v2 模型设计。

---

# 第三部分：固定影像表型

## 3.1 Habitat 方法

固定使用：

```text
3D SLIC
→ target supervoxel scale = 4 mm
→ cross-case K-means
→ K = 2
→ n_init = 100
```

采用 full-A technical population 建立一次固定 habitat definition。

技术中心和 boundary 冻结后：

```text
lower cluster → H-low
higher cluster → H-high
```

之后：

**不在 CV fold 内重新拟合 centers。**

**不在 B 中重新拟合 centers。**

**不根据 DFS 调整 boundary。**

FT 已经冻结该 full-A 技术定义，并明确禁止修改 SLIC、K、n_init、H-low/H-high 定义及候选特征集合。

---

## 3.2 Habitat global descriptors

G 保留既往冻结定义。

核心 global habitat descriptors 保持固定，不根据 Primary v2 结果重新筛选。

H_high_fraction 仍作为最直观的单一 burden descriptor，独立构成 M1。

完整 G 构成 M2。

---

## 3.3 Habitat-specific radiomics

继续使用既有冻结候选集合：

```text
R_low  = 49 features
R_high = 10 features
```

候选特征集合已经在 outcome-independent 技术阶段定义。

Primary v2 禁止：

- 根据 FT03 结果删减 candidate pool；
- 根据 FT06 结果只保留 R_high；
- 根据 B performance 更改候选特征；
- 新做 DFS-based univariate screening。

---

## 3.4 Whole-tumour radiomics

主比较仅使用：

**W_Original = 107**

不再使用：

- Wavelet
- LoG
- filtered radiomics

原因不是这些特征“无效”，而是 Primary v2 的目标是构建计算成本合理且临床解释清楚的主分析。

W_Original 仅作为 whole-tumour radiomics reference comparator。

---

# 第四部分：临床变量

Clinical block C 沿用既往冻结定义，不因 FT 结果重新选择。

即保持治疗前可获得的临床/MRI变量。

原则：

```text
clinical predictors fixed before Primary v2 canonicalization
```

不得：

- 根据 B 结果重新删除临床变量；
- 根据 p 值 stepwise；
- 使用 postoperative variables；
- 根据影像组学模型表现调整 C。

---

# 第五部分：正式模型集合

Primary v2 保留 FT 原始预设的全部 7 个模型。

这是非常重要的科学约束。

| Model | Predictors | Purpose |
|---|---|---|
| M0 | C | clinical baseline |
| M1 | C + H_high_fraction | simple habitat burden |
| M2 | C + G | global habitat organization |
| M3L | C + G + R_low | H-low radiomics |
| M3H | C + G + R_high | H-high radiomics |
| M4 | C + G + R_low + R_high | dual-habitat radiomics |
| M5 | C + W_Original | whole-tumour radiomics comparator |

不得因为 FT06 中 M3H 表现较好而把：

`M3H`

事后升级为唯一 primary model。

Primary v2 的核心比较仍是模型层级比较，而不是事后冠军模型选择。

---

# 第六部分：模型类型

## 6.1 低维模型

M0、M1、M2：

**Cox proportional hazards model**

不做 stepwise selection。

---

## 6.2 高维模型

M3L、M3H、M4、M5：

**LASSO-Cox**

固定：

```text
alpha = 1
```

取消原 Formal W08：

```text
alpha ∈ [0.1, 0.5, 0.9, 1.0]
```

的额外搜索。

这样减少一个调参维度，同时提高结果解释的一致性。

---

# 第七部分：A 队列内部验证

## 7.1 验证结构

正式 Primary v2 使用：

**固定 single-repeat 5-fold outer validation**

使用已经冻结的 W07 repeat-1 split。

FT03 已按这一固定 5-fold 结构完成 A-only 验证，且当时没有读取 B。

---

## 7.2 高维模型调参

虽然取消 repeated nested CV，但仍必须保持训练/验证隔离。

每个 outer fold：

```text
outer training
    ↓
training-only preprocessing
    ↓
training-only lambda CV
    ↓
fit final fold model
    ↓
outer validation prediction
```

outer-validation 数据：

不得参与：

- imputation 参数估计；
- scaling；
- variance filtering；
- correlation filtering；
- lambda selection；
- feature selection。

因此论文中不应简单描述为：

`non-nested CV`

更准确描述为：

> **single-repeat 5-fold outer validation with training-only cross-validation for LASSO penalty selection**

---

# 第八部分：最终模型冻结

完成 A 5-fold validation 后：

使用 full A modeling population 重新拟合所有 M0–M5。

高维模型仍只通过 A 内部选择 lambda。

随后冻结：

- predictor order；
- preprocessing；
- selected features；
- coefficients；
- lambda；
- baseline hazard / survival representation；
- risk score definition；
- cutoff，如需要；
- model-specific eligibility；
- source asset hashes。

冻结完成后：

**模型禁止再因 B 表现变化。**

---

# 第九部分：B 外部验证

## 9.1 原则

B 只允许：

```text
load frozen model
→ load frozen-compatible B predictors
→ predict
→ evaluate
```

禁止：

- B feature selection；
- B lambda tuning；
- B coefficient refit；
- B cutoff optimization；
- B habitat refit；
- B radiomics candidate re-selection；
- B→A feedback。

FT06 已经按照 frozen prediction only 原则完成 163 例、42 events 的 B validation，没有在 B 上拟合、调参、筛特征或重做 habitat。

---

# 第十部分：已有 FT 结果的正式处理

## 10.1 原则

采用：

**Promotion without recomputation**

不重新执行患者级 FT03/FT04/FT06。

原因：

如果 Primary v2 的科学合同与既有 FT 完全一致，那么重新计算：

- 不产生新的独立证据；
- 不能恢复“结果未知”的状态；
- 反而增加工程风险。

---

## 10.2 可直接提升的证据

### A validation

FT03：

- A = 393
- events = 89
- fixed repeat-1 5-fold
- M0–M5 均完成。

### Full-A refit/model freeze

使用 FT04 已冻结模型作为 Primary v2 candidate canonical state。

### B external validation

FT06：

- B = 163
- DFS events = 42
- frozen prediction only。

---

# 第十一部分：必须公开记录的方法学时间顺序

这是 Primary v2 能否保持科学可信度的关键。

既有 FT 最终结论为：

`FT-INCONCLUSIVE`

而 FT 原方案当时明确规定其不改变 formal L9。

因此，本次把 FT 框架提升为正式主线属于：

**post-FT protocol transition**

必须明确记录：

> 在决定把 streamlined FT framework 提升为正式主分析方法时，FT03 A 结果和 FT06 B 外部验证结果已经可见。

不得写成：

> Primary v2 was prespecified before B validation.

正确表述是：

> The modeling pipeline itself was frozen before external validation. The subsequent decision to adopt this streamlined pipeline as the principal analytic framework was made for computational feasibility, fixed-phenotype interpretability and methodological simplicity.

因此：

**模型对 B 的验证仍是 frozen external validation；**

但：

**把该框架提升为论文正式主分析，是在 B 结果已经可见之后作出的项目方法学决策。**

两者必须区分。

---

# 第十二部分：结果解释原则

由于本次 protocol transition 发生在 FT06 后：

Primary v2 结果可用于：

- 主要模型描述；
- discrimination；
- calibration；
- prediction error；
- model comparisons；
- habitat-specific signal interpretation；
- hypothesis generation。

但结论必须避免：

> 某个模型已经被完全独立地“事前指定并外部证实”。

特别是 M3H。

即使已有结果显示 R_high 有较积极信号，也只能表述为：

> R_high-specific radiomics showed the most consistent signal under the frozen validation framework.

不能因为该观察结果改变模型设计。

---

# 第十三部分：正式评价指标

所有 M0–M5 固定报告：

## Discrimination

- Harrell C-index
- Uno C-index
- time-dependent AUC at 3 years
- time-dependent AUC at 5 years

## Prediction error

- Brier score at 3 years
- Brier score at 5 years

如已有稳定实现，可保留：

- integrated Brier score

## Calibration

- 3-year calibration
- 5-year calibration

## Clinical stratification

- Kaplan-Meier by frozen risk definition

## Clinical utility

- DCA at 3 and 5 years

## Uncertainty

- patient-level bootstrap 95% CI

FT03/FT06 已经生成这些主要结果类型。

---

# 第十四部分：正式模型比较

保持原预设比较，不因观察结果调整：

```text
M0 vs M1
M0 vs M2
M2 vs M3L
M2 vs M3H
M2 vs M4
M3L vs M3H
M4 vs M5
```

所有 paired comparisons：

必须在共同 eligible population 上计算。

不得直接比较两个使用不同患者集合得到的 C-index，并把差异解释为模型增益。

---

# 第十五部分：Primary v2 不再执行的内容

以下正式退出 active analysis：

```text
10 repeated outer CV runs
50 outer folds
fold-specific K-means refitting
fold-specific habitat boundary reconstruction
fold-specific habitat radiomics regeneration
Elastic-Net alpha grid search
Wavelet/LoG main comparator
Formal W08 R5/R6 remediation chain
L0–L7 W08 performance optimization chain
```

这些内容全部定义为：

**Superseded Formal Method v1**

---

# 第十六部分：仍然保留的旧 main 优点

统计框架采用 FT，但工程治理继续继承 main 的优点。

必须保留：

## A/B isolation

在模型冻结前禁止使用 B 进行模型开发。

## Provenance binding

所有关键输入均保留：

- path
- schema
- SHA-256
- model identity

## Fail-closed validation

关键 freeze 或 schema 不一致时禁止静默继续。

## Transactional output

避免 partial output 被误认为正式结果。

## Patient-level privacy boundary

患者级文件、特征和原始 ID 不进入 GitHub。

因此最终框架是：

> **FT 的科学统计方法 + main 的数据治理标准**

而不是简单复制 FT 的全部工程实现。

---

# 第十七部分：Git 与仓库整改目标

## 新的活动主线

最终只保留：

```text
main
```

作为长期主分支。

整改过程临时使用：

```text
codex/primary-v2-transition
```

整改完成后合并并删除。

---

## 旧 Formal v1

当前 main 在换轨前建立归档锚点：

```text
archive/formal-nested-cv-v1-20260913
```

之后旧 W08/R5/R6/L* 进入：

```text
archive/formal_nested_cv_v1/
```

---

## FT

当前 FT 最终提交建立：

```text
archive/ft-validation-v1-20260913
```

FT 分支在 Primary v2 整改完成前保留。

整改完成、证据提升验证完成后：

删除：

```text
codex/ft-validation
```

但 tag 永久保留。

---

# 第十八部分：新的正式目录结构

最终建议：

```text
prognosis_analysis/
│
├── primary/
│   ├── README.md
│   ├── protocol.json
│   ├── validate_assets.py
│   ├── run_cv.py
│   ├── refit_freeze.py
│   ├── validate_external.py
│   └── final_report.py
│
├── configs/
│
├── modeling_protocol.md
├── modeling_protocol.json
├── execution_status.json
│
└── archive_reference.md
```

历史：

```text
archive/
├── formal_nested_cv_v1/
├── ft_validation_v1/
├── protocol_history/
├── project_status_history/
└── incidents/
```

---

# 第十九部分：Primary v2 串行执行工作流

以下工作必须严格串行。

任何阶段 FAIL：

**停止，不进入下一阶段。**

---

## V2-00 — Freeze current history

### 目标

确保换轨前历史不可丢失。

### 操作

建立两个 immutable references：

```text
archive/formal-nested-cv-v1-20260913
archive/ft-validation-v1-20260913
```

记录：

- current main HEAD
- current FT HEAD
- old formal status
- FT final state

### Gate

必须可以通过 tag 恢复完整旧 main 和完整 FT。

---

## V2-01 — Protocol Transition Amendment

### 输出

创建：

```text
PRIMARY_ANALYSIS_V2_TRANSITION_20260913.md
```

必须明确：

1. Formal W08 v1 未成功完成；
2. Formal v1 被 superseded；
3. 转换理由：
   - computational feasibility
   - fixed phenotype interpretability
   - methodological simplicity
4. FT03/FT06 已经可见；
5. 不因观察结果重新选模型；
6. M0–M5 全部保留；
7. B 不再用于新的 tuning。

### Gate

文档必须明确包含：

```text
post-FT protocol transition
```

并禁止任何“pretend-prespecified”描述。

---

## V2-02 — Primary Scientific Contract

### 输出

创建：

```text
prognosis_analysis/primary/protocol.json
prognosis_analysis/primary/README.md
```

固定：

- cohort definitions
- DFS
- 3/5-year horizons
- 3D SLIC 4 mm
- K=2
- fixed full-A habitat
- R_low=49
- R_high=10
- W_Original=107
- C/G
- M0–M5
- alpha=1
- W07 repeat-1 5-fold
- training-only lambda selection
- B frozen prediction only

### Gate

Primary v2 scientific contract 与 accepted FT scientific contract 必须一致。

任何因 FT06 performance 导致的新增/删减：

FAIL。

---

## V2-03 — Canonical Code Extraction

### 目标

从 FT 代码中抽出正式主分析最小实现。

### 新代码

```text
primary/validate_assets.py
primary/run_cv.py
primary/refit_freeze.py
primary/validate_external.py
primary/final_report.py
```

### 迁移原则

保留：

```text
scientific computation
A/B isolation
hash/provenance
schema validation
fail-closed checks
```

移除：

```text
FT-specific branch guards
historic remediation compatibility
incident recovery logic
temporary audit rounds
legacy finalization machinery
```

### Gate

活动代码中不得再依赖：

```text
FT00
FT01
FT02
...
```

作为正式运行状态机。

---

## V2-04 — Equivalence Validation

### 目标

证明 Primary v2 代码只是 FT scientific computation 的 canonicalization，不是新分析。

### 测试内容

对 synthetic fixtures 和允许的冻结 metadata：

验证：

```text
feature order identical
eligibility identical
imputation identical
scaling identical
lambda-selection behavior identical
coefficients identical
risk predictions identical
metrics identical
```

### 特别要求

这一步：

**不得为了验证代码重新读取 B outcome。**

### Gate

所有允许比较的 numerical outputs：

完全一致或达到预先定义的机器精度 tolerance。

---

## V2-05 — Evidence Promotion

### 目标

将已有 FT 科学结果注册为 Primary v2 evidence。

不重新分析患者数据。

建立：

```text
PRIMARY_V2_EVIDENCE_MANIFEST.json
```

至少绑定：

### A

FT03 aggregate/report SHA-256

### Model freeze

FT04 lock SHA-256

### B

FT06 aggregate/report SHA-256

### Technical assets

- habitat lock
- R_low hash
- R_high hash
- W_Original hash/order
- clinical schema
- cohort identities

### Gate

若 Primary v2 与 FT 在任何科学计算规则上不等价：

不得 promotion；

必须重新定义该部分为新的 exploratory analysis。

---

## V2-06 — Canonical Model Freeze

### 目标

生成新的正式 Primary v2 model identity。

注意：

不是重新 fit。

而是将 accepted FT04 frozen states：

登记为：

```text
Primary v2 canonical frozen models
```

新的 lock 记录：

```text
source = promoted_from_FT04
original_FT04_hash
Primary_v2_protocol_hash
promotion_date
no_refit = true
no_B_tuning = true
```

### Gate

模型 coefficients、features、lambda 与原 FT04 必须完全一致。

---

## V2-07 — Canonical External Validation Registration

### 目标

把 FT06 注册为 Primary v2 的外部验证证据。

新的正式 summary 必须明确：

```text
B prediction was frozen before B evaluation
Primary-v2 promotion decision occurred after FT B results were available
```

不能混淆。

### Gate

FT06 原始：

- patient eligibility
- model identity
- predictions
- metrics

全部不可修改。

---

## V2-08 — Archive Formal v1

将旧 Formal W08 相关非活动资产归档：

```text
W08 repeated nested-CV protocols
R5*
R6*
L0-L7 optimization records
old formal execution SOP
formal remediation reports
```

进入：

```text
archive/formal_nested_cv_v1/
```

### 保留在 active tree

仍被 Primary v2 使用的：

- feature extraction
- habitat configs
- freeze lock
- W02/W03 frozen candidate definitions
- clinical schema
- B access controls
- generic provenance utilities

不得归档。

### Gate

active main 不再把 Formal W08 v1 列为下一步任务。

---

## V2-09 — Archive FT Development History

FT 不再作为 active analysis tree。

归档保留：

```text
FT protocol
FT03 report
FT04 lock/audit
FT06 report
FT final audit
key scientific-freeze records
```

事故/工程材料进入：

```text
archive/incidents/
```

其余大量 FT remediation/audit rounds 可保存在 archive tag 中，不必全部复制进 main。

### Gate

未来读者可以找到：

```text
方法来源
A结果
冻结模型
B结果
最终审计
```

但不会把 FT 当成另一条活动分析路线。

---

## V2-10 — Rewrite README

README 的“当前主线”替换成：

```text
MRI/radiomics freeze
→ full-A habitat freeze
→ candidate freeze
→ Primary v2 fixed 5-fold A validation
→ full-A model freeze
→ frozen B external validation
→ final interpretation
```

Formal v1：

```text
archived / superseded
```

FT：

```text
historical development source of Primary v2
```

---

## V2-11 — Rewrite PROJECT_STATUS

新的 `PROJECT_STATUS.md` 只保留：

```text
Current method:
Primary Prognostic Analysis v2

Habitat:
frozen full-A K=2

A validation:
completed / promoted from FT03

Model freeze:
completed / promoted from FT04

B external validation:
completed / promoted from FT06

Formal v1:
superseded

FT:
archived

Current next stage:
scientific interpretation / manuscript-ready analysis
```

旧长状态文件进入：

```text
archive/project_status_history/
```

---

## V2-12 — Branch Cleanup

确认所有 evidence/tag 可恢复后：

删除历史 codex 分支。

包括：

```text
codex/ft-validation
codex/w08-nested-cv
codex/w08-preflight-blocked
codex/w08-coxph-remediation
codex/p0-pre-w08-baseline
codex/l7-current-code-technical-preflight
codex/r2-...
codex/g2r-...
及其它已失去活动价值的旧 worker branches
```

最终长期分支：

```text
main
```

---

## V2-13 — Final Scientific Audit

最终独立检查以下问题。

### Scientific identity

是否只有一个 Primary protocol？

### No performance-driven redesign

是否保留原 M0–M5？

### B integrity

是否不存在 B-guided refitting/tuning？

### Fixed phenotype

是否所有患者使用同一冻结 habitat definition？

### A validation isolation

lambda 是否仅在 outer training 中选择？

### External validation

B 是否 frozen prediction only？

### Transparency

是否明确披露 Primary v2 promotion 发生在 FT06 结果可见后？

### Archive clarity

旧 Formal v1 和 FT 是否均不再作为 active protocol？

全部 PASS 后：

Primary v2 成为项目唯一正式分析基线。

---

# 第二十部分：最终项目状态定义

整改完成后的科学状态应为：

```text
Image preprocessing
        ↓
Radiomics technical freeze
        ↓
Full-A 3D SLIC / K=2 habitat freeze
        ↓
G / R_low / R_high candidate freeze
        ↓
Primary v2 fixed 5-fold A validation
        ↓
Full-A refit/model freeze
        ↓
Frozen B external validation
        ↓
Scientific interpretation
```

而以下内容全部退出 active pipeline：

```text
Repeated 10×5 nested CV
Fold-specific habitat reconstruction
Fold-specific radiomics regeneration
Formal W08 R6 remediation
FT engineering recovery chain
```

---

# 第二十一部分：Primary v2 完成定义

只有同时满足以下条件才算整改完成：

### 方法

只有一个正式 protocol：

`Primary Prognostic Analysis v2`

### 影像表型

H-low/H-high 使用固定 full-A definition。

### 模型

M0–M5 保持原 FT 预设。

### 内部验证

固定 repeat-1 5-fold。

### 调参

LASSO alpha=1；

lambda training-only CV。

### 冻结

最终模型在 B 评价前已经冻结。

### 外部验证

B frozen prediction only。

### 时间顺序

明确记录 Primary v2 promotion decision 是 post-FT。

### 结果使用

不得根据 FT06 结果删除模型、重新选变量或改变 candidate pool。

### Git

Formal v1 和 FT 均归档；

只有 main 为长期主分支。

### 项目状态

README 和 PROJECT_STATUS 只描述 Primary v2。

达到以上标准后，项目即可正式结束“方法开发/整改期”，进入：

**结果解释、图表整理、敏感性分析和论文撰写阶段。**
