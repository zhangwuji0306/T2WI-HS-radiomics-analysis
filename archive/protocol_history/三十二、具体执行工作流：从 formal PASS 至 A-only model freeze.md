# 三十二、具体执行工作流：从 formal PASS 至 A-only model freeze

本文件规定从 formal bootstrap 已通过后，到 A 集模型开发完成并生成第二阶段模型冻结锁为止的**唯一正式执行顺序**。

本文件优先级高于旧版阶段说明、旧版脚本注释及历史 protocol。若现有代码与本工作流冲突：

> **以本工作流为准，先修改代码，再执行分析。**

不得因为旧代码仍可运行而绕过本工作流。

---

# 一、总原则

整个流程分为四个阶段：

```text
阶段 0：冻结前代码与数据访问整改
    ↓
阶段 I：technical freeze + pre-outcome method freeze
    ↓
阶段 II：A-only outcome analysis + nested internal validation
    ↓
阶段 III：A-only final refit + model freeze
```

在：

```text
prognosis_analysis/model_freeze_lock.json
```

正式生成并通过完整校验之前：

> **B 集任何临床、结局、radiomics、habitat feature、QC、缺失率、模型性能及患者级数据均不得读取。**

“不得读取”不是指：

> 可以先载入内存但不输出。

而是：

> **在文件读取或数据库读取入口之前就必须通过权限门禁。**

---

# 二、当前已完成技术状态

formal patient-level bootstrap 已完成：

- requested = 1000；
- completed = 1000；
- success = 1000；
- nondegenerate rate = 1.000；
- reference H-low center = 2.101717；
- reference H-high center = 3.519630；
- reference boundary = 2.810674；
- bootstrap boundary median = 2.811491；
- boundary 95% interval = [2.708194, 2.924580]；
- width / center distance = 0.152609；
- assignment stability median = 0.986711；
- assignment stability P5 = 0.960980；
- structural-state stability median = 1.000；
- structural-state stability P5 = 0.997；
- formal_eligible = 1。

最终技术稳定性判定：

> **FORMAL PASS**

因此从本文件开始：

- 不再修改 0.1% high-signal eligibility；
- 不再修改 4 mm SLIC；
- 不再修改 K；
- 不再修改 patient-balanced weighting；
- 不再修改 muscle normalization；
- 不再通过增加 bootstrap 次数进行方法选择；
- 不再重新比较 M1/M2/M3；
- 不得因后续 DFS 结果重新定义技术主方法。

---

# 三、Workflow 总览

正式顺序改为：

```text
W00  formal结果归档与仓库状态同步
 ↓
W00A 冻结前阻断性代码修复
 ↓
W00B freeze/data-access集成测试
 ↓
W01  technical freeze / freeze_lock.json
 ↓
W02  H-low/H-high Original radiomics结局盲态提取框架
 ↓
W03  habitat radiomics ICC与技术候选池冻结
 ↓
W04  modeling protocol冻结
 ↓
W05  真正A-only数据访问改造与验证
 ↓
W06  首次读取A结局 + endpoint QC
 ↓
W07  冻结A modeling population与CV splits
 ↓
W08  repeated nested CV
      fold-specific habitat
      → fold-specific G
      → fold-specific R_low/R_high
      → models
 ↓
W09  A集模型比较与稳定性评价
 ↓
W10  A137、tumor-volume及dual-habitat敏感性分析
 ↓
W11  依据预设层级确定final A model architecture
 ↓
W12  full-A final refit
 ↓
W13  A-only model freeze / model_freeze_lock.json
```

只有 W13 完成后：

> 才允许进入 B 集一次性外部验证。

---

# W00 — formal 结果归档与状态同步

## W00.1 目标

正式关闭 technical bootstrap 阶段。

---

## W00.2 必须确认

- formal 1000/1000 完成；
- `formal_eligible=1`；
- bootstrap summary 完整；
- A393 technical cohort identity 未变化；
- A137 仍为 A393 真子集；
- preprocessing config 未改变；
- SLIC config 未改变；
- high-signal threshold audit 未改变。

---

## W00.3 更新项目状态

更新：

```text
PROJECT_STATUS.md
habitat_analysis/analysis_freeze.md
```

明确记录：

> formal=1000 complete / FORMAL PASS，当前进入冻结前代码整改与 technical freeze。

---

## W00.4 禁止

不得：

- 再增加 bootstrap 寻找更漂亮结果；
- 修改 high-signal threshold；
- 修改 SLIC 尺度；
- 修改 K；
- 修改 normalization；
- 重新比较 M1/M2/M3。

---

# W00A — 冻结前阻断性代码修复

本阶段是新的**硬前置门禁**。

在完成本阶段之前：

> **不得执行正式 `stage7_freeze`，更不得读取 A outcome。**

---

## W00A.1 修复 stage7 freeze 的确定性运行错误

当前 `revised_workflow_technical.py` 中：

```text
stage7_freeze()
```

会调用：

```python
validate_freeze_lock(...)
```

因此必须保证该函数被显式导入。

正式执行前必须完成：

```python
from freeze_lock import (
    ...
    validate_formal_bootstrap,
    validate_freeze_lock,
)
```

并加入针对该执行路径的回归测试。

仅通过：

```text
compileall
```

不足以证明该问题已解决。

---

## W00A.2 强化 freeze lock schema

第一阶段锁不能再仅由少量 bootstrap 字段构成。

必须定义：

```text
freeze_schema_version
```

并至少强制以下字段存在且值正确：

```text
habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false

bootstrap_mode = formal
bootstrap_requested = 1000
bootstrap_completed = 1000
bootstrap_completion_status = complete
bootstrap_operational_pass = 1
formal_eligible = 1

outcome_columns_read = false
B_data_read = false

eligibility_threshold_fraction = 0.001
eligibility_threshold_role = minimum_imaging_presence
threshold_selection_performed = false
threshold_audit_conclusion = NEUTRAL_WITH_TECHNICAL_CAUTION
```

缺任何必要字段：

> lock invalid。

---

## W00A.3 freeze lock 必须绑定正式冻结资产

不得只绑定 config 和 patient ID。

至少加入以下 SHA-256：

```text
A393_id_hash
A137_id_hash

manifest_hash
scanner_map_hash
preprocessing_config_hash
slic_config_hash
high_signal_screen_hash

formal_bootstrap_summary_hash

global_descriptors_hash
feature_qc_hash
feature_dictionary_hash

threshold_audit_hash
threshold_confounding_audit_hash

habitat_map_manifest_hash
```

---

## W00A.4 habitat maps 使用 manifest 锁定

不要求把 393 个 NRRD hash 全部直接写入 `freeze_lock.json`。

建议生成：

```text
habitat_analysis/output/habitat_maps_A_manifest.csv
```

至少：

```text
patient_id
relative_path
sha256
```

然后：

```text
freeze_lock.json
```

绑定：

```text
habitat_map_manifest_hash
```

---

## W00A.5 audit 不得仅检查“文件存在”

以下文件：

```text
threshold audit
threshold confounding audit
formal bootstrap summary
feature QC
feature dictionary
```

必须：

> 计算内容 hash 并进入 freeze lock。

不能仅使用：

```python
os.path.exists(...)
```

作为最终冻结证明。

---

## W00A.6 冻结提交点

当前 staging → 多次 `os.replace()` 的方案可以防普通 Python exception，但不能保证系统断电情况下完全原子。

正式推荐：

```text
freeze_bundles/
    freeze_<bundle_hash>/
        maps/
        features/
        feature_dictionary.md
        artifact_manifest.json
        freeze_lock.json
```

全部验证完成后，仅原子更新：

```text
CURRENT_FREEZE.json
```

如果本轮不重构为 bundle：

> 至少必须保留 staging + rollback，并明确当前机制属于 exception-safe，而非严格 crash-atomic。

这不阻止 W01，但必须记录为工程限制。

---

# W00B — freeze 与数据隔离集成测试

在正式 technical freeze 前必须通过以下测试。

---

## W00B.1 stage7 synthetic integration test

必须覆盖：

```text
synthetic inputs
↓
freeze preflight
↓
staging features/maps
↓
staging lock
↓
validate_freeze_lock
↓
promotion
```

至少确保不会再次出现：

> 单元测试通过，但真正执行 stage7 时 NameError。

---

## W00B.2 lock tampering test

生成合法 freeze lock 后：

分别修改：

```text
global_descriptors
feature_qc
feature_dictionary
habitat map manifest
threshold audit
```

验证：

> `validate_freeze_lock()` 必须 hard fail。

---

## W00B.3 B read-before-unlock test

在：

```text
model_freeze_lock.json
```

不存在时：

任何：

```text
B clinical
B outcome
B whole-tumor radiomics
B habitat
B feature QC
```

读取入口都必须在真正读取文件之前 hard fail。

---

## W00B.4 A outcome-before-first-lock test

在：

```text
freeze_lock.json
```

不存在或无效时：

任何 A outcome/clinical reader 必须 hard fail。

但：

```text
technical A imaging
technical A manifest
technical A preprocessing
```

仍允许读取。

---

# W01 — 正式 technical freeze

只有 W00A 与 W00B 全部通过后执行。

---

## W01.1 输入

必须核验：

- A393 technical cohort；
- A137 strict cohort；
- manifest；
- scanner map；
- preprocessing config；
- SLIC config；
- formal bootstrap summary；
- baseline integrity；
- center reproducibility；
- technical robustness；
- threshold audit；
- threshold confounding audit。

---

## W01.2 运行

执行：

```text
stage7_freeze
```

正式生成：

- habitat maps；
- global descriptors；
- feature QC；
- feature dictionary；
- artifact manifest；
- freeze lock。

---

## W01.3 主低维 global habitat block G

固定为：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

---

## W01.4 A393 硬门禁

必须：

```text
n = 393
unique ID = 393
hard technical failures = 0
six G features all finite
H-low + H-high voxel conservation = pass
```

---

## W01.5 A137 硬门禁

必须：

```text
n = 137
unique ID = 137
A137 ⊂ A393
```

---

## W01.6 第一阶段 freeze lock

生成：

```text
habitat_analysis/freeze_lock.json
```

必须通过严格 schema validation。

该 lock 的唯一权限意义为：

```text
A_outcome_unlock = true
B_unlock = false
```

因此：

> 第一把锁只允许读取 A 临床与结局，不允许读取 B。

---

# W02 — 建立 H-low/H-high Original radiomics 工作流

该阶段仍然：

> **outcome blind**

目的：

> 在首次读取 DFS 前冻结 habitat-specific radiomics 定义。

---

## W02.1 输入

使用：

- muscle-normalized T2WI；
- `[1,1,2] mm`；
- 无 N4；
- tumor ROI；
- SLIC labels；
- frozen technical center/boundary 仅用于 full-A 技术描述和 ICC 技术框架。

不重新：

- normalize；
- resample；
- 计算新 binWidth。

---

## W02.2 PyRadiomics 参数

固定：

```text
imageType = Original
binWidth = 0.248808
normalize = false
resample = false
```

H-low 与 H-high：

> 使用同一灰度离散化标尺。

---

## W02.3 特征类别

完整提取：

- firstorder；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

---

## W02.4 正式预测候选层级

### Main

Original texture：

- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

### Secondary

first-order。

### Exploratory

shape。

---

## W02.5 对称性

必须建立：

```text
R_low
R_high
```

采用完全对称：

- extraction；
- QC；
- ICC；
- candidate filtering；
- nested CV；
- model family。

不得预设：

> H-low 或 H-high 更重要。

---

## W02.6 structural absence

single-H-low：

```text
R_high = structurally undefined
```

single-H-high：

```text
R_low = structurally undefined
```

不得填 0。

---

## W02.7 availability 状态

每例至少记录：

```text
H_low_present
H_high_present

R_low_extractable
R_high_extractable

R_low_failure_reason
R_high_failure_reason
```

必须区分：

```text
structural absence
technical failure
```

---

# W03 — habitat-specific radiomics 结局盲态 QC

必须在读取 DFS 前完成。

---

## W03.1 R1/R2 流程

每个 reader 均独立经过：

```text
reader-specific image/ROI
↓
fixed preprocessing
↓
SLIC
↓
frozen technical phenotype framework
↓
H-low/H-high
↓
Original radiomics
```

---

## W03.2 ICC

分别：

```text
R_low ICC(2,1)
R_high ICC(2,1)
```

技术候选门槛：

```text
ICC > 0.75
```

并预设：

```text
n_valid_pairs >= 10
```

否则：

```text
insufficient reproducibility sample
```

---

## W03.3 availability 门槛

在 habitat 存在病例中：

```text
finite feature rate >= 95%
```

否则不进入正式 prediction candidate pool。

---

## W03.4 禁止

不得：

- univariate Cox；
- DFS association；
- outcome correlation；
- LASSO；
- outcome-based feature ranking；
- 根据结局修改 ICC threshold。

---

## W03.5 candidate hashes

最终生成：

```text
R_low_candidate_hash
R_high_candidate_hash
```

并冻结。

---

# W04 — Modeling protocol freeze

首次读取 DFS 前必须生成：

```text
prognosis_analysis/modeling_protocol.json
prognosis_analysis/modeling_protocol.md
```

---

## W04.1 正式模型

```text
M0 = C
M1 = C + H_high_fraction
M2 = C + G
M3L = C + G + R_low
M3H = C + G + R_high
M4 = C + G + R_low + R_high
M5 = C + W
```

---

## W04.2 模型层级比较

固定：

```text
M0 → M1
M1 → M2
M2 → M3L
M2 → M3H
M3L vs M3H
M2 → M4
M0 → M5
```

不得在看到 DFS 后随意增加组合。

---

## W04.3 主终点

```text
DFS
```

主要时间点：

```text
3 years
5 years
```

---

## W04.4 nested CV

固定：

```text
Outer CV:
5-fold × 10 repeats

Inner CV:
5-fold
```

共：

```text
50 outer validation folds
```

---

## W04.5 stratification

按：

```text
DFS event status
```

分层。

训练与验证 fold 均必须至少存在 event。

---

## W04.6 radiomics modeling

采用：

> Elastic Net Cox 为优先高维模型。

预设 alpha：

```text
0.1
0.5
0.9
1.0
```

lambda：

> inner CV 决定。

不得用 outer validation performance 调参。

---

# W05 — 真正 A-only 数据访问改造

这是首次读取 A outcome 前的最后一道代码安全门禁。

---

## W05.1 禁止继续直接使用当前 legacy builder

在完成本阶段前：

```text
prognosis_analysis/scripts/build_model_dataset.py
```

不得用于首次结局读取。

必要时应临时设置为：

> fail closed。

---

## W05.2 访问模型必须分为三类

建议统一数据读取 API：

```text
read_technical_A(...)
read_A_outcomes(...)
read_B_validation(...)
```

权限分别为：

### technical A

不需要第一把锁。

### A clinical/outcomes

必须：

```text
validate_freeze_lock()
```

### B anything

必须：

```text
validate_model_freeze_lock()
```

---

## W05.3 A 模式

正式 builder 必须支持：

```text
--split A
```

在第二把锁生成前：

```text
--split B
--split all
```

必须 hard fail。

---

## W05.4 ID restriction 必须先于临床信息使用

A mode 中必须先读取：

```text
A393 / A137 technical IDs
```

然后：

> 用 ID 白名单限制 clinical/outcome rows。

不得先构建包含 A+B 的完整 modeling dataframe 后再切 A。

---

## W05.5 不得读取 B feature table

不能：

```text
读取全部R1 radiomics
→ 再筛A
```

如果原始文件同时包含 A/B：

> reader 必须在数据读取函数中实施授权过滤，且不得产生 B 派生统计。

长期更优方案：

> 分离 A/B 受控数据文件或受控 reader。

---

## W05.6 A mode 禁止产生

```text
dataset_*_B.csv
```

也禁止：

- B count；
- B missingness；
- B complete-case count；
- B outcome；
- B habitat distribution；
- B radiomics distribution；
- B QC summary。

---

## W05.7 唯一 split 实现

A/B 判定逻辑必须统一调用：

```text
resolve_cohort_membership()
```

或现有集中实现。

不得在不同脚本重复手写：

```text
vendor
model
field strength
```

判定规则。

---

## W05.8 第二阶段锁统一

从本阶段开始规定：

> B 解锁只认 `prognosis_analysis/model_freeze_lock.json`。

旧：

```text
b_validation_unlock.json
```

不得再作为正式权限来源。

应废弃或仅保留兼容迁移，不得独立解锁 B。

---

## W05.9 W05 回归测试

必须测试：

```text
freeze_lock missing
→ A outcome hard fail

freeze_lock valid
→ A outcome allowed

model_freeze_lock missing
→ any B read hard fail

model_freeze_lock valid
→ B validation allowed
```

还必须证明：

> hard fail 发生在真正读取 B 文件之前。

---

# W06 — 首次读取 A DFS

只有以下全部完成后：

- W01 technical freeze；
- W03 R_low/R_high candidate freeze；
- W04 modeling protocol freeze；
- W05 A-only access isolation；
- 所有相关回归测试通过；

才允许第一次读取 A outcome。

---

## W06.1 endpoint QC

报告：

- A393 总人数；
- DFS event count；
- censor count；
- follow-up；
- reverse-KM median follow-up；
- 3-year evaluable；
- 5-year evaluable；
- DFS_time ≤ 0；
- duplicated ID；
- event/time conflict；
- missing outcome。

---

## W06.2 可修改范围

仅允许修正：

> 可追溯的原始数据错误。

不得根据影像或模型结果改变：

- DFS definition；
- censor rule；
- follow-up cutoff；
- eligibility；
- technical cohort。

---

## W06.3 A modeling population

生成：

```text
A_modeling_population.csv
```

排除只能来自：

- frozen technical exclusion；
- outcome unavailable；
- 明确且不可修复的数据错误。

不得因模型表现排除病例。

---

# W07 — 冻结 CV split plan

正式 nested modeling 前生成：

```text
outer_splits_A.csv
```

至少：

```text
patient_id
repeat
fold
role
seed
```

并计算：

```text
outer_split_hash
```

---

## W07.1 Main population

用于：

```text
M0
M1
M2
M5
```

---

## W07.2 R_low population

同一 splits 比较：

```text
M2 vs M3L
```

---

## W07.3 R_high population

同一 splits 比较：

```text
M2 vs M3H
```

---

## W07.4 dual-radiomics population

同一 splits 比较：

```text
M2
M3L
M3H
M4
```

用于真正 paired：

```text
M3L vs M3H
```

---

# W08 — repeated nested CV

这是 A-only 分析核心。

每个：

```text
repeat × outer fold
```

完整执行以下步骤。

---

## W08.1 outer split

得到：

```text
Train_outer
Validation_outer
```

Validation_outer 从此：

> 不参与任何参数估计。

---

## W08.2 fold-specific global K-means

仅使用：

```text
Train_outer
```

预缓存的：

- SLIC labels；
- supervoxel means。

病例等权：

```text
sum(supervoxel weights per patient) = 1
```

重新拟合：

```text
C_low_train
C_high_train
b_train
```

---

## W08.3 apply training boundary

对：

```text
Train_outer
Validation_outer
```

均使用：

```text
b_train
```

生成 habitat。

Validation 不参与 boundary fitting。

---

## W08.4 fold-specific G

重新生成六个 G。

因此：

> nested CV 不能直接使用 full-A frozen G。

---

## W08.5 fold-specific R_low/R_high

对 training 与 validation 分别从 fold-specific mask 提取。

仅允许使用 W03 冻结候选池。

---

## W08.6 provenance

每个 fold 至少记录：

```text
training_id_hash
validation_id_hash

centers
boundary

R_low_candidate_hash
R_high_candidate_hash

preprocessing/code version
random seed
```

---

## W08.7 clinical preprocessing

所有：

- imputation；
- scaling；

只在 Train_outer 拟合。

---

## W08.8 radiomics preprocessing

以下均仅 Train_outer：

- near-zero variance；
- correlation reduction；
- scaling；
- alpha/lambda tuning；
- Elastic Net feature selection。

---

## W08.9 outer prediction

Inner CV 完成后：

```text
refit complete Train_outer
→ Validation_outer transform
→ prediction
```

Validation 端不得：

- refit boundary；
- refit scaler；
- feature selection；
- lambda tuning；
- imputation fitting。

---

# W09 — A 内部验证结果汇总

所有性能必须来自：

> held-out outer validation predictions。

---

## W09.1 discrimination

报告：

- Harrell C-index；
- Uno C-index；
- 3-year AUC；
- 5-year AUC。

---

## W09.2 calibration

报告：

- 3-year calibration；
- 5-year calibration；
- calibration slope；
- calibration-in-the-large。

---

## W09.3 prediction error

报告：

- 3-year Brier；
- 5-year Brier；
- integrated Brier score，如实现稳定。

---

## W09.4 paired comparison

所有增量比较必须使用：

> same patients + same outer splits。

---

## W09.5 radiomics stability

报告每个 feature：

```text
selection frequency
```

重点看：

- effect size；
- prediction improvement；
- consistency；
- calibration；
- repeat/fold stability。

不得单凭 P 值决定模型有效性。

---

# W10 — 预设敏感性分析

---

## W10.1 A137

A137 不重新开发技术方法。

优先在 A393 outer CV 体系中：

> 提取 strict phenotype validation cases 的 held-out prediction。

---

## W10.2 tumor volume

预设：

```text
log(tumor_volume)
```

加入：

```text
M2-V
M3L-V
M3H-V
```

用于判断 habitat 是否主要代理 tumor burden。

---

## W10.3 dual-habitat-only

在 dual-radiomics eligible population 中比较：

```text
M2
M3L
M3H
M4
```

---

# W11 — A-only final model architecture

B 仍不可见。

允许最终模型为：

```text
M0
M1
M2
M3L
M3H
M4
```

M5 主要作为 whole-tumor comparator。

---

## W11.1 决策原则

使用：

```text
hierarchy
+ incremental evidence
+ parsimony
+ stability
```

不得：

> 直接选择最高一次 C-index。

---

## W11.2 如果所有 habitat 模型均无增量

允许：

```text
M0 Clinical
```

成为 final model。

不得因此：

- 改 0.1%；
- 改 SLIC；
- 改 K；
- 增加 Wavelet/LoG 寻找阳性结果。

---

# W12 — full-A final refit

使用全部 A modeling population。

---

## W12.1 deployment habitat

使用正式 frozen technical centers：

```text
H-low = 2.101717
H-high = 3.519630
boundary = 2.810674
```

---

## W12.2 Final G

使用已锁定 full-A G 或重新生成后验证 hash 一致。

---

## W12.3 Final R_low/R_high

如果 final model 使用 habitat radiomics：

使用：

- full-A frozen habitat；
- fixed Original parameters；
- frozen candidate pools。

---

## W12.4 full-A preprocessing

使用 full A 确定：

- imputation；
- scaling；
- correlation reduction；
- Elastic Net alpha；
- lambda；
- final selected features。

这些形成 deployment parameters。

---

## W12.5 performance reporting

不得把 full-A training performance 当作内部验证性能。

论文 A 内部性能必须来自：

> W08/W09 outer held-out predictions。

---

# W13 — A-only model freeze

完成全部 A-only 分析后生成唯一正式第二阶段锁：

```text
prognosis_analysis/model_freeze_lock.json
```

---

## W13.1 严格 schema

必须定义：

```text
model_freeze_schema_version
```

并进行严格验证。

---

## W13.2 cohort

记录：

```text
A_modeling_population_hash
A393_id_hash
A137_id_hash
```

---

## W13.3 technical dependency

记录：

```text
freeze_lock_hash
preprocessing_config_hash
slic_config_hash
global_center_low
global_center_high
global_boundary
```

---

## W13.4 modeling protocol

记录：

```text
modeling_protocol_hash
outer_split_hash
outcome_definition_hash
candidate_pool_hashes
```

---

## W13.5 final model artifacts

必须绑定：

```text
final_model_id
final_model_family
final_model_feature_list_hash
final_model_coefficients_hash
preprocessing_parameter_hash
baseline_survival_hash
final_model_artifact_hash
```

---

## W13.6 必须声明

```text
A_model_development_complete = true
A_model_frozen = true

B_data_read = false
B_validation_unlocked = true
```

生成 lock 时：

> `B_data_read` 必须仍为 false。

---

## W13.7 B access

B reader 只能调用：

```text
validate_model_freeze_lock()
```

不得再依赖独立：

```text
b_validation_unlock.json
```

作为正式权限来源。

---

## W13.8 freeze 后禁止

一旦 `model_freeze_lock.json` 生成：

不得根据 B：

- 改 final model；
- 改 H-low/H-high 选择；
- 改 radiomics features；
- 改 lambda；
- 改 clinical variables；
- 改 habitat；
- 改 threshold；
- 改 preprocessing；
- 重新校准 primary model 后再重新报告原验证。

B 只能：

> 一次性外部验证已冻结模型。

---

# 三十三、阶段硬门禁

## Gate 0 — code readiness

必须：

- stage7 import bug 修复；
- strict freeze schema 完成；
- artifact hashes 完成；
- synthetic freeze integration test 通过；
- A/B read guard integration test 通过。

---

## Gate A — technical freeze

必须：

- formal PASS；
- A393 exact；
- A137 exact；
- feature QC pass；
- artifact manifest 完整；
- `freeze_lock.json` 有效。

---

## Gate B — outcome unlock

必须：

- W02 方法冻结；
- W03 candidate pools 冻结；
- W04 modeling protocol 冻结；
- W05 A-only read isolation 完成；
- B reader fail-closed 测试通过。

否则：

> 不读取 DFS。

---

## Gate C — nested validation

必须：

- A outcome QC 完成；
- A modeling population 冻结；
- CV splits 冻结。

---

## Gate D — final architecture

必须完成：

- M0–M5 预设分析；
- paired comparisons；
- A137 sensitivity；
- tumor-volume sensitivity；
- dual-habitat sensitivity。

---

## Gate E — model freeze

必须：

- final architecture 确定；
- full-A refit 完成；
- final artifacts 完整；
- hashes 一致；
- B 从未读取；
- `model_freeze_lock.json` 验证通过。

---

# 三十四、关键回归测试清单

必须保留以下测试：

1. stage7 end-to-end synthetic freeze；
2. freeze artifact tampering detection；
3. A outcome requires first lock；
4. B read requires second lock；
5. B failure occurs before physical file read；
6. validation patient excluded from K-means fitting；
7. fold-specific habitat；
8. H-low/R-low 与 H-high/R-high 对称；
9. structural absence ≠ 0；
10. training-only imputation；
11. training-only scaler；
12. training-only correlation filter；
13. training-only Elastic Net tuning；
14. single centralized A/B split resolver；
15. final model lock artifact validation。

---

# 三十五、A-only 阶段完成标志

进入 B 验证前必须同时存在且通过校验：

```text
habitat_analysis/freeze_lock.json

prognosis_analysis/modeling_protocol.json

prognosis_analysis/output/A_endpoint_qc/

prognosis_analysis/output/A_modeling/

prognosis_analysis/output/nested_cv/

prognosis_analysis/output/A_model_comparison/

prognosis_analysis/output/final_model_A/

prognosis_analysis/model_freeze_lock.json
```

同时必须能够证明：

- H-high burden 是否提供增量信息；
- macro-habitat 是否提供增量信息；
- H-low texture 是否提供增量信息；
- H-high texture 是否提供增量信息；
- H-low 与 H-high 哪个更稳定；
- dual-habitat 是否进一步改善；
- whole-tumor radiomics 是否提供增量价值；
- 结果对 A137 是否稳健；
- 是否主要受 tumor volume 解释；
- final model 结构及参数为何；
- 所有 final deployment artifacts 是否被冻结；
- B 是否从未参与任何上述决定。

全部满足后：

> **A-only model development complete。**

此时：

```text
B_validation_unlocked = true
```

才具有正式意义。