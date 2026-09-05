# T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流

CURRENT EXECUTION STATUS
========================

Authoritative operational workflow: YES

Completed:
P0 / P1 / G1 / P2 / P3 / G2R / P4 provenance remediation + independent review

Current gate:
P4 PASS_WITH_FINDINGS (P4 PASS; no blocking findings)

Next:
P5 implementation: NOT STARTED / NOT AUTHORIZED

P5 authorization:
NO

B_data_read:
false

formal_W08_started:
false

model_freeze_lock:
NOT GENERATED

Formal W08:
HOLD

B:
LOCKED


## 0. 工作流定位

当前项目不得再按照：

```text
W00R FAIL
→ 回退 W01
→ 重做 W01–W07
```

执行。

新的正式状态定义为：

```text
W01–W07：历史阶段保留，不重跑
W08 implementation：已完成
W08 formal：HOLD

当前进入：
Post-freeze remediation
+
W07A Pre-W08 protocol amendment
+
50-fold technical preflight
```

只有新的 Pre-W08 Gate 全部通过后，才允许正式 W08。

---

# 一、总控智能体必须冻结的六条原则

## 原则 1：不回滚已经完成的 W01–W07

不得重新：

- 选择 high-signal threshold；
- 修改 4 mm SLIC；
- 修改 K=2；
- 修改 patient-balanced K-means；
- 修改 muscle normalization；
- 重跑 W03 ICC 以寻找不同 candidate pool；
- 重建 W07 split 以适应新问题。

原有：

```text
R_low candidates = 49
R_high candidates = 10
W03 candidate hashes
W07 outer split hash
```

继续保持。

---

## 原则 2：原始第一把锁保持 bitwise immutable

不得直接修改：

```text
habitat_analysis/freeze_lock.json
```

原因：

```text
W04 modeling_protocol
        ↓
已绑定原 freeze_lock SHA-256
```

任何新的完整性证据必须通过：

```text
freeze_integrity_addendum.json
```

或等价的补充文件实现。

不能伪装成：

> “在读取 DFS 前重新冻结”。

---

## 原则 3：原 W04 不覆盖、不重写

原：

```text
prognosis_analysis/modeling_protocol.json
```

继续作为历史主协议。

新技术规则通过：

```text
W07A_pre_W08_protocol_amendment.md
W07A_pre_W08_protocol_amendment.json
```

补充。

W08 formal 必须同时验证：

```text
W04 hash
+
W07 split hash
+
W07A amendment hash
```

---

## 原则 4：正式 W08 前不得产生模型性能

整改期间禁止产生或查看：

```text
C-index
Uno C-index
AUC
Brier
calibration
ΔC-index
feature selection frequency
final coefficients
```

允许读取 A outcome 的唯一用途限于：

- 已冻结 W07 split 的校验；
- 技术可估计性所需 event/censor count；
- 不涉及性能的模型可执行性检查。

技术规则必须先冻结，再检查其 event feasibility。

---

## 原则 5：B 继续绝对锁定

整个整改阶段：

```text
model_freeze_lock.json = absent
B_data_read = false
B_reader_invoked = false
B_source_opened = false
B_statistics_generated = false
```

任何 B access test 必须使用 synthetic 文件。

---

## 原则 6：不允许多个子智能体同时修改同一核心文件

总控智能体必须实行：

```text
单文件单阶段唯一 owner
```

特别是：

```text
data_split_guard.py
w08_nested_cv.py
w08_formal_run_a.py
w08_nested_cv.json
PROJECT_STATUS.md
```

不得由多个子智能体并发写入。

---

# 二、总工作流

```text
P0  仓库快照 + W08 HOLD
 ↓
P1  并行审计
 ├─ P1A A-only reader 安全审计
 ├─ P1B technical-freeze 完整性审计
 ├─ P1C 50-fold small-ROI 纯技术扫描
 └─ P1D clinical / penalty methodology 审计
 ↓
G1  整改设计门禁
 ↓
P2  冻结 W07A protocol amendment
 ↓
P3  分模块代码整改
 ├─ P3A reader authorization 修复
 ├─ P3B fold-specific extractability 实现
 ├─ P3C paired population / coverage 实现
 ├─ P3D clinical stability / penalty 实现
 └─ P3E integrity addendum + regression hardening
 ↓
G2  synthetic + regression gate
 ↓
P4  post-freeze integrity verification
 ↓
P5  全 50-fold TECHNICAL-ONLY preflight
 ↓
G3  FORMAL W08 RELEASE GATE
 ↓
P6  W08 formal repeated nested CV
 ↓
P7  W09 A-only model comparison
 ↓
P8  W10 prespecified sensitivities
 ↓
P9  W11 final architecture
 ↓
P10 W12 full-A refit
 ↓
P11 W13 model_freeze_lock
 ↓
首次允许 B validation
```

---

# 三、P0 — 仓库快照与正式 W08 HOLD

## 分包：子智能体 S0

### 目标

建立整改起点，不修改科学代码。

### 输入

```text
main HEAD
PROJECT_STATUS.md
W04 protocol
W07 split config/artifact
W08 protocol/config
W08 preflight audit
freeze_lock.json
```

### 必须确认

```text
formal W08 = not started
held-out predictions = none
W08 performance metrics = none
model_freeze_lock.json = absent
B_data_read = false
```

### 输出

建议新建：

```text
prognosis_analysis/W07A_pre_W08_remediation_baseline.md
```

记录：

- remediation 起始 commit；
- 原 W04 hash；
- 原 freeze_lock hash；
- W03 candidate hashes；
- W07 split hash；
- W08 当前 blocked 原因；
- B access 状态。

### 禁止

不得：

- 修改 freeze_lock；
- 修改 W04；
- 修改 W07 split；
- 执行任何正式模型。

### Gate P0

只有 baseline 完整记录后允许进入 P1。

---

# 四、P1 — 四路并行审计

这一阶段可以并行。

每个子智能体只提交：

```text
审计报告
+
建议 patch
```

原则上暂不直接修改共享核心代码。

---

# P1A — A-only reader 安全审计

## 分包：子智能体 S1A

### 重点文件

```text
feature_extract/scripts/data_split_guard.py
prognosis_analysis/scripts/build_model_dataset_a.py
prognosis_analysis/scripts/w06_endpoint_qc.py
prognosis_analysis/scripts/w08_formal_run_a.py
tests/test_w05_access.py
```

### 必须验证

重点攻击路径：

```python
read_A_outcomes(
    mixed_A_B_source,
    reader=malicious_reader,
    allowed_ids={"A1"}
)
```

恶意 reader 返回：

```text
A1
B1
```

确认当前代码是否允许 B1 进入 application dataframe。

同样测试：

```text
read_technical_A()
read_B_validation()
compatibility aliases
```

### 推荐整改目标

正式 production reader 必须满足：

```text
authorization before patient-row materialization
```

优先方案：

```text
移除生产路径任意 reader= callable
```

若 connector adapter 必须存在，则定义受控接口：

```text
authorized adapter
必须接收：
allowed_ids
id_column
usecols
```

且由 adapter 在真实数据源读取层执行过滤。

### 禁止方案

不能仅：

```text
reader()
→ 得到 A+B DataFrame
→ 检查 ID
→ 删除 B
```

因为 B 已进入应用内存。

### 输出

```text
P1A_reader_security_audit.md
```

包含：

- bypass reproduction；
- 正式 W05/W06 是否实际使用该 bypass；
- 建议 API；
- 需要新增的 regression tests。

---

# P1B — 第一把锁完整性审计

## 分包：子智能体 S1B

### 目标

区分：

```text
scientific frozen artifact
vs
supporting audit artifact
```

### 核验现有 hash

逐一重新计算：

```text
A393
A137
manifest
scanner map
preprocessing config
SLIC config
high-signal screens
formal bootstrap summary
global descriptors
feature QC
feature dictionary
threshold audit
confounding audit
habitat map manifest
393 habitat maps
```

与现有 freeze_lock 比较。

### 额外核验

未被原 lock 绑定的：

```text
freeze_qc.csv
freeze_preflight.csv
freeze_preflight.md
```

仅计算 hash，不修改原 lock。

### 输出

```text
P1B_freeze_integrity_audit.md
```

并提出：

```text
freeze_integrity_addendum.json
```

schema。

### 关键结论格式

必须明确回答：

```text
core frozen scientific artifacts altered?
YES / NO

original freeze lock still validates?
YES / NO

historical W01 needs scientific rerun?
YES / NO
```

---

# P1C — 全 50-fold small-ROI 技术扫描

## 分包：子智能体 S1C

这是整个整改中最重要的技术诊断之一。

### 目的

仅回答：

> fold-specific boundary 变化后，R_low / R_high 的 mask 支持大小如何变化？

不得运行 Cox。

不得生成任何模型性能。

### 使用固定资产

```text
W06 A modeling population
W07 frozen outer splits
frozen SLIC labels
frozen supervoxel means
training-only patient-balanced K=2
```

### 对全部

```text
10 repeats × 5 folds
```

重新得到 training-derived boundary。

随后对所有 train/validation 病例统计：

```text
R_low voxel count
R_high voxel count
```

分为：

```text
state 0:
0 voxel

state 1:
1–9 voxels

state 2:
>=10 voxels
```

### 输出只允许聚合统计

可以输出：

```text
每 fold：
n_low_zero
n_low_1_9
n_low_ge10

n_high_zero
n_high_1_9
n_high_ge10

n_dual_ge10
```

患者 ID 只保留本地敏感输出，不进入仓库。

### 不允许

不得：

- 降低 minimumROISize；
- 动态排除 fold；
- 修改 threshold；
- 修改 boundary；
- 修改 W07 splits。

### 输出

```text
P1C_fold_specific_extractability_audit.md
```

---

# P1D — Clinical model 与 penalty methodology 审计

## 分包：子智能体 S1D

### 目标

不运行正式模型性能，只审查模型定义是否方法学一致。

---

## 问题 A：9 个 clinical predictors

保持变量 membership：

```text
年龄
CEA_log
mrT
mrN
MRF
mrEMVI
thickness
EID
活检病理非腺癌
```

不得利用 A outcome：

- 做 univariate screening；
- 按 P 值删变量；
- 按 HR 删变量。

但需要报告实际 design-matrix df。

---

## 问题 B：M0/M1/M2 未惩罚 Cox 稳定性

评估：

```text
effective df
事件数
outer-training 事件规模
```

提出预先冻结的 stability sensitivity：

```text
M0-R
M1-R
M2-R
```

推荐：

```text
ridge Cox
所有原 clinical predictors 保留
lambda training-only / inner-CV
```

不得用于改变 primary architecture，只用于验证 primary conclusion 稳定性。

---

## 问题 C：M3L/M3H/M4 penalty semantics

必须明确当前模型到底是：

```text
C + G + R
全部共同接受 Elastic Net penalty
```

还是：

```text
C + G 固定
仅 R 接受 penalty
```

当前正式 W08 前必须写清。

总控推荐默认：

```text
不得在看到正式性能后再决定。
```

如果改变 penalty semantics：

> 必须在 W07A amendment 中显式记录，并通过 synthetic test 后才能正式 W08。

### 输出

```text
P1D_modeling_methodology_audit.md
```

---

# 五、G1 — 整改设计门禁

## 总控智能体执行

汇总：

```text
P1A
P1B
P1C
P1D
```

### 必须在此阶段做出正式决定

不得留到 W08 运行时临时判断。

至少冻结以下五项：

### Decision 1 — reader policy

例如：

```text
arbitrary custom reader = prohibited in production
```

---

### Decision 2 — small-ROI 状态定义

推荐冻结：

```text
0 voxels
→ structurally absent

1–9 voxels
→ technically unextractable_small_ROI

>=10 voxels
→ radiomics extractable
```

必须强调：

```text
0 ≠ 1–9
```

---

### Decision 3 — radiomics population

推荐：

```text
R_low model:
当前fold R_low >=10

R_high model:
当前fold R_high >=10

dual:
当前fold R_low >=10 AND R_high >=10
```

---

### Decision 4 — paired comparator

例如：

```text
M3H
vs
M2_R_high
```

必须使用：

```text
同一 fold
同一 training patient set
同一 validation patient set
```

M3L、M4 同理。

---

### Decision 5 — clinical / penalty policy

必须明确：

```text
Primary M0/M1/M2 是否保持 W04 规格
ridge sensitivity 是否预设
M3/M4 中 C/G 是否接受 penalty
```

不得在正式性能出现后再决定。

---

# 六、P2 — 冻结 W07A Pre-W08 amendment

## 分包：子智能体 S2

这个阶段必须由**单一子智能体**完成。

禁止多人并发修改 protocol。

### 新增

```text
prognosis_analysis/W07A_pre_W08_protocol_amendment.md
prognosis_analysis/W07A_pre_W08_protocol_amendment.json
```

### amendment 必须声明

```text
amendment timing:
after W06/W07
before any formal W08 prediction/performance

trigger:
technical preflight only

outcome-performance-informed:
false

B_data_read:
false
```

---

## 必须写入 small-ROI rule

```text
structural_absence:
mask voxel count = 0

technical_small_roi:
1 <= voxel count < 10

extractable:
voxel count >= 10
```

不得改变：

```text
minimumROISize = 10
```

---

## 必须写入 population rule

逐 model 固定：

```text
M0/M1/M2:
main

M3L:
fold-specific R_low extractable

M3H:
fold-specific R_high extractable

M4:
fold-specific dual extractable
```

---

## 必须写入 paired rule

每个 radiomics comparator：

```text
same patients
same outer split
same training-derived habitat boundary
```

---

## 必须写入 coverage estimand

W09 后续必须报告：

```text
validation opportunities
valid predictions
structural absence
technical small-ROI unavailable
per-patient held-out prediction count
per-fold effective n
```

---

## 必须写入不可估计规则

如果技术 eligibility 导致某 fold：

```text
training/validation event gate
或
inner 5-fold gate
```

无法满足：

不得：

- 改 W07 split；
- 动态减少 fold；
- 降低 10 voxel；
- 增补病例。

必须：

```text
formal run hard fail
→ return to protocol review
```

除非 amendment 本身预先规定了统一 fallback。

---

## Amendment lock

计算：

```text
W07A_protocol_sha256
```

之后 W08 code/config 必须硬绑定该 hash。

---

# 七、P3 — 代码整改

此阶段允许并行，但必须按文件划分 ownership。

---

# P3A — Reader authorization

## 子智能体 S3A

### 独占文件

```text
feature_extract/scripts/data_split_guard.py
tests/test_w05_access.py
```

### 必须加入测试

#### Test 1

malicious reader 返回 A+B：

```text
allowed_ids = A only
```

必须在 B row materialization 前 hard fail。

#### Test 2

A outcome missing first lock：

```text
hard fail before source open
```

#### Test 3

B missing model lock：

```text
hard fail before source open
```

#### Test 4

正常 streaming CSV/XLSX：

```text
仍只返回 allowlisted rows
```

---

# P3B — Fold-specific extractability

## 子智能体 S3B

### 独占文件

```text
prognosis_analysis/scripts/w08_formal_run_a.py
```

### 实现

provider 输出必须增加状态：

```text
R_low_voxel_count
R_high_voxel_count

R_low_state
R_high_state

R_low_structurally_defined
R_high_structurally_defined

R_low_technically_extractable
R_high_technically_extractable
```

不得：

```text
1–9 voxel → ordinary NaN → median imputation
```

---

# P3C — Fold-specific population + paired comparison

## 子智能体 S3C

### 独占文件

```text
prognosis_analysis/scripts/w08_nested_cv.py
prognosis_analysis/configs/w08_nested_cv.json
```

但必须在 S3B API 固定以后再开始。

### 实现

每 fold：

```text
provider transform
↓
extractability state
↓
derive fold-specific eligible IDs
↓
derive comparator IDs
↓
fit paired models
```

确保：

```text
M2_R_low vs M3L
M2_R_high vs M3H
M2_dual vs M3L/M3H/M4
```

严格 paired。

---

# P3D — Clinical stability / penalty implementation

## 子智能体 S3D

与 S3C 不能同时编辑 `w08_nested_cv.py`。

因此执行顺序：

```text
S3C 完成
↓
merge
↓
S3D 开始
```

### 如果 G1 决定加入 ridge sensitivity

新增预设：

```text
M0-R
M1-R
M2-R
```

要求：

```text
same W07 splits
same patients
training-only tuning
不得用于 primary architecture search
```

### penalty semantics

必须写入代码 audit：

```text
which coefficient blocks are penalized
```

不能仅靠注释推断。

---

# P3E — Integrity addendum 与测试增强

## 子智能体 S3E

不得修改原：

```text
freeze_lock.json
```

### 新增建议

```text
habitat_analysis/freeze_integrity_addendum.json
```

至少记录：

```text
original_freeze_lock_sha256

freeze_qc_sha256
freeze_preflight_csv_sha256
freeze_preflight_md_sha256

verification_timestamp
verification_commit

core_scientific_artifacts_match_original_lock = true

scientific_parameters_changed = false
technical_freeze_regenerated = false
outcome_used_to_modify_technical_method = false
B_data_read = false
```

### 扩增 tamper regression

至少再覆盖：

```text
A393
A137
manifest
scanner_map
preprocessing config
SLIC config
screen files
bootstrap summary
threshold confounding audit
```

### closed-schema

可设计：

```text
schema v2
```

但不要用它覆盖历史 v1 lock。

---

# 八、G2/G2R — Synthetic + Regression Gate

总控智能体统一运行。

必须覆盖至少以下测试组：

```text
A. full test suite

B. malicious custom reader
C. B access-before-lock
D. A outcome-before-lock

E. 0 voxel structural absence
F. 1–9 voxel technical unavailable
G. >=10 extractable

H. R_low paired population
I. R_high paired population
J. dual paired population

K. validation ID never enters boundary fit
L. validation never enters imputation/scaling
M. validation never enters correlation filtering
N. validation never enters alpha/lambda selection

O. W03 candidate hashes unchanged
P. W07 split hash unchanged
Q. W04 hash unchanged

R. Cox non-convergence fail closed
S. no stale coefficients after failed fit

T. integrity addendum does not alter original freeze_lock
```

### Gate G2 PASS 条件

```text
all required tests pass
+
no patient-level artifact committed
+
no B access
```

否则不得进入 P4。

当前状态：G2R PASS。若 P5 implementation 阶段新增或修改正式执行代码，不得沿用本次 G2R 结果授权新代码；必须在 P5 technical-only preflight 前完成 G2R2。

---

# 九、P4 — Post-freeze integrity verification

## 子智能体 S4

重新验证：

```text
original freeze_lock
W04
W03 candidate hashes
W06 population
W07 split
W07A amendment
```

必须证明：

```text
original freeze_lock unchanged

W04 original SHA relationship unchanged

technical parameters unchanged

W07 split unchanged

W03 candidates unchanged
```

### 输出

```text
prognosis_analysis/W07A_pre_W08_integrity_audit.md
```

---

# 十、P5 implementation — 技术预检入口补齐与 G2R2

P5 technical-only preflight 必须使用与 formal W08 分离的、fail-closed 执行入口。当前 `w08_formal_run_a.py --preflight-fold` 的单 fold 预检不等价于本阶段，也不能单独授权 50-fold P5。

## 必须具备的执行边界

建议新增独立入口：

```text
prognosis_analysis/scripts/w08_technical_preflight_a.py
```

或为现有 runner 增加等价的独立 `--technical-preflight-all` 模式。该入口只允许完成：

```text
training-only habitat centre fitting
boundary assignment
mask generation
extractability classification
model-specific eligible population construction
event/censor feasibility
inner-5-fold feasibility
W03/W04/W07/W07A hash verification
```

该入口不得调用或产生：

```text
final Cox fitting
risk score
held-out prediction
C-index / AUC / Brier / calibration
model comparison
B data access
```

预检结果只写入本地敏感输出目录；仓库如需提交证据，仅保留不含患者标识的聚合结果：

```text
P5_technical_preflight_summary.json
P5_fold_feasibility.csv
P5_release_gate.json
```

## G2R2

P5 执行入口完成任何新增或修改后，必须重新通过回归门禁，不能引用旧 G2R 结果。G2R2 至少覆盖完整测试发现集、W05 access tests、W08 tests 和新增 P5 technical-only tests，并证明：

```text
P5 cannot call final Cox fitting
P5 cannot generate prediction or performance
P5 cannot open B
P5 cannot modify W07 split or minimumROISize
P5 verifies W04/W07/W07A hashes
```

G2R2 未通过前不得执行真实患者级 P5。

---

# 十一、P5 — 全 50-fold TECHNICAL-ONLY preflight

这是正式 W08 前最后一道硬门禁。

## 分包：子智能体 S5

### 允许执行

```text
10 repeats × 5 folds

training-only habitat center fitting
boundary assignment
mask generation
extractability classification
eligible population construction
event/censor feasibility
inner-CV feasibility
```

### 禁止执行

不得：

```text
fit final Cox models
compute risk scores
compute held-out predictions
compute C-index
compute AUC
compute Brier
compute calibration
compare models
```

### 每个 fold 必须记录

```text
run_id
repeat
fold

training_id_hash
validation_id_hash

centers
boundary

n_train_before_eligibility
n_validation_before_eligibility

n_structural_absence
n_small_roi_1_9
n_extractable

n_train_after_eligibility
n_validation_after_eligibility

train_events
train_censors
validation_events
validation_censors

inner_5fold_feasible

R_low_candidate_hash
R_high_candidate_hash

B_data_read=false
performance_generated=false
```

### Gate G3

只有：

```text
50/50 folds technical preflight complete
all required formal runs estimable
all paired populations valid
all hashes unchanged
no performance generated
```

才允许：

```text
FORMAL_W08_RELEASE = PASS
```

否则：

```text
FORMAL_W08_RELEASE = FAIL
```

并停止。

不得自动修改协议。

---

# 十二、P6 — W08 Formal

## 子智能体 S6

只有 G3 PASS 后执行。

正式运行：

```text
5 folds × 10 repeats
```

遵守：

```text
training-only habitat
training-only G/R generation
training-only preprocessing
training-only inner tuning
held-out validation prediction
```

### 输出仅存本地敏感目录

```text
predictions
fold_results
selection_results
audit
```

仓库只提交：

```text
aggregate audit
schema
non-patient-level summary
```

### 正式完成条件

所有预设 run 完成。

不得：

```text
skip difficult fold
delete failed candidate
change alpha grid
change lambda range
change small-ROI rule
```

---

# 十三、P7 — W09 A-only 模型评价

## 子智能体 S7

仅消费 frozen W08 held-out predictions。

### 分析

```text
Harrell C
Uno C
3y/5y AUC
3y/5y Brier
calibration
IBS if estimable
```

### paired comparisons

仅允许预设：

```text
M0 → M1
M1 → M2
M2 → M3L
M2 → M3H
M3L vs M3H
M2 → M4
M0 → M5
```

### 新增必须报告

radiomics coverage：

```text
effective validation coverage
structural absence frequency
small-ROI technical unavailable frequency
per-patient held-out prediction frequency
```

不得只报告“可计算病例中的最好 C-index”。

---

# 十四、P8 — W10 Prespecified Sensitivity

## 子智能体 S8

仅运行事先冻结的：

### A137

```text
strict phenotype sensitivity
```

### Tumor volume

```text
M2-V
M3L-V
M3H-V
```

### Dual habitat

```text
M2
M3L
M3H
M4
```

### Clinical ridge stability

如 W07A 已冻结：

```text
M0-R
M1-R
M2-R
```

### 可选 penalty sensitivity

只有 W07A 已预设才可运行。

---

# 十五、P9 — W11 Final Architecture Decision

## 子智能体 S9

不得选择：

> 单个最高 C-index。

按照冻结层级：

```text
incremental evidence
+
paired consistency
+
stability
+
coverage
+
parsimony
+
calibration
```

选择：

```text
M0 / M1 / M2 / M3L / M3H / M4
```

M5：

```text
reference comparator
```

不是因为 feature 更多就优先。

### 输出

```text
final_architecture_decision.md
```

必须写明：

```text
selection criteria
all alternatives
why rejected
no B information used
```

---

# 十六、P10 — W12 Full-A Final Refit

## 子智能体 S10

使用全部 A modeling population。

Deployment habitat 使用既有全 A technical centers：

```text
H-low = 2.101717
H-high = 3.519630
boundary = 2.810674
```

生成：

```text
imputation
scaling
correlation filter
selected features
penalty parameters
coefficients
baseline survival
deployment preprocessing
```

所有 artifact 计算 SHA-256。

---

# 十七、P11 — W13 Model Freeze

## 子智能体 S11

生成：

```text
prognosis_analysis/model_freeze_lock.json
```

必须绑定：

```text
original technical freeze hash
freeze integrity addendum hash
W04 hash
W07 split hash
W07A amendment hash
W03 candidate hashes
W08 formal audit hash
W09 result-summary hash
W10 sensitivity audit hash
final architecture hash
deployment model artifact hashes
A population hash
source commit
```

状态必须：

```text
A_model_development_complete = true
A_model_frozen = true

B_data_read = false
B_validation_unlocked = true
```

只有严格验证成功后：

> 才允许第一次打开 B source。

---

# 十八、子智能体统一任务包模板

总控智能体每次分包必须使用以下格式。

```text
[TASK ID]

Stage:
例如 P3B

Goal:
一句话说明任务目标。

Starting commit:
固定 SHA。

Read-only inputs:
允许读取的文件。

Owned files:
本子智能体唯一允许修改的文件。

Forbidden files:
不得修改的冻结资产。

Data boundary:
A technical / A outcome / B access 权限。

Scientific invariants:
threshold / SLIC / K / candidates / split 等不得变化项。

Required implementation:
需要完成的具体代码或文档。

Required tests:
必须运行的测试。

Expected outputs:
文件路径和报告。

Hard-fail conditions:
出现哪些情况立即终止。

No-go actions:
禁止事项。

Handoff summary:
1. changed files
2. commit SHA
3. tests run
4. test result
5. remaining risks
6. B_data_read status
7. patient-level artifact status
```

---

# 十九、总控智能体合并规则

## 可以并行

```text
P1A
P1B
P1C
P1D
```

因为主要输出审计报告。

以及：

```text
P3A
P3B
P3E
```

前提是文件 ownership 不重叠。

---

## 必须串行

```text
P1
→ G1
→ P2
```

因为 amendment 必须基于全部审计。

```text
P3B
→ P3C
```

因为 eligibility API 必须先稳定。

```text
P3C
→ P3D
```

避免同时修改 `w08_nested_cv.py`。

```text
P3
→ G2R
→ P4
→ P5 implementation
→ G2R2
→ P5 technical-only
→ G3
→ P6
```

不得跳阶段。

```text
P6
→ P7
→ P8
→ P9
→ P10
→ P11
```

严格串联。

---

# 二十、禁止总控智能体做的事情

不得因为子智能体报告“模型跑不动”而自动：

```text
降低 minimumROISize
修改 W07 split
降低 inner fold 数
修改 alpha
修改 lambda range
删除困难病例
修改 candidate pool
增加新模型
修改 high-signal threshold
修改 SLIC
修改 K
```

必须返回上一级 protocol gate。

---

# 二十一、最终门禁矩阵

| Gate | 必须通过的内容 | 失败后 |
|---|---|---|
| P0 | baseline snapshot | 不开始整改 |
| G1 | reader + integrity + ROI + modeling 决策 | 不写 amendment |
| G2/G2R | synthetic/regression 全通过 | 不执行真实 preflight |
| P4 | post-remediation integrity audit PASS | 不开始 P5 implementation |
| P5 implementation | fail-closed technical-only 入口就绪 | 不执行真实 P5 |
| G2R2 | 新 P5 入口回归通过 | 不执行真实 P5 |
| P5 | 50-fold technical preflight PASS | 不执行正式 W08 |
| G3 | 50-fold technical preflight、可估计性和完整性均通过 | 不执行正式 W08 |
| W08 Gate | formal 50 folds 完整 | 不进入 W09 |
| W09/W10 Gate | A-only结果完整 | 不选 final architecture |
| W11 Gate | final architecture 可审计 | 不 full-A refit |
| W12 Gate | deployment artifacts 完整 | 不生成 model lock |
| W13 Gate | strict model lock valid | B 继续锁定 |

---

# 二十二、当前整改优先级

## P0 — 当前必须完成

```text
1. P4 post-freeze integrity audit
2. P5 technical-only entry implementation
3. G2R2 regression gate
4. 50-fold technical-only preflight
5. G3 release gate
```

---

## P1 — 建议同轮完成

```text
6. freeze integrity addendum
7. PROJECT_STATUS and document-entry synchronization
8. clinical ridge stability prespecification
9. explicit high-dimensional penalty semantics
```

---

## P2 — 工程增强

```text
10. full tamper-test matrix
11. future closed schema v2
12. immutable freeze bundle / crash-atomic pointer
```

P2 不作为当前 W08 release blocker，除非在实施过程中发现真实 artifact mismatch。

---

# 二十三、当前总控应向所有子智能体广播的统一状态

```text
REMEDIATION_BASELINE_COMMIT = 78b0e8f48becd64413859027e8809e155ecded5e

W01-W07 = historical completed; do not rerun

W08_FORMAL = HOLD

W08_predictions_generated = false
W08_metrics_generated = false

model_freeze_lock = absent

B_data_read = false

technical method remains frozen:
threshold = unchanged
SLIC = unchanged
K = 2
minimumROISize = 10
W03 candidates = unchanged
W07 splits = unchanged

Current allowed work:
post-freeze integrity remediation
P5 technical-only entry implementation
G2R2 regression gate
technical-only 50-fold preflight

Formal model evaluation is prohibited
until FORMAL_W08_RELEASE = PASS.
```
