# 三十二、具体执行工作流：从 formal PASS 至 A-only model freeze

本文件是从 formal technical stability PASS 到 A-only final model freeze 的唯一正式执行顺序。

本版根据 2026-08-31 代码审阅结果修订，新增 **W00R 冻结前代码安全整改**，并强化 W01、W05、W13 的 fail-closed 规则。

整个流程分为三阶段：

```text
阶段 I：技术冻结前代码安全整改 + technical freeze + outcome-blind方法冻结
    ↓
阶段 II：A-only outcome analysis + repeated nested internal validation
    ↓
阶段 III：A-only final refit + model freeze
```

在第三阶段完成并生成 `prognosis_analysis/model_freeze_lock.json` 之前：

> **B 集临床、结局、habitat、radiomics、missingness 和模型性能始终不可读取。**

这里的“不可读取”不是“读取后不使用”，而是正式分析代码不得打开/载入含 B 数据的源资产。

---

# Workflow 总览

```text
W00   formal结果归档与仓库状态同步
 ↓
W00R  冻结前代码安全整改与回归门禁
 ↓
W01   technical freeze / strict freeze_lock.json
 ↓
W02   H-low/H-high Original radiomics结局盲态提取框架
 ↓
W03   habitat radiomics ICC与技术候选池冻结
 ↓
W04   modeling_protocol冻结
 ↓
W05   真正A-only数据访问 + B源级隔离
 ↓
W06   首次读取A结局 + endpoint QC
 ↓
W07   冻结A modeling population与CV splits
 ↓
W08   repeated nested CV：
       fold-specific habitat → G → R_low/R_high → models
 ↓
W09   A集模型比较与稳定性评价
 ↓
W10   A137、tumor-volume、dual-habitat等预设敏感性
 ↓
W11   按预设层级确定final A model architecture
 ↓
W12   full-A refit / deployment artifacts
 ↓
W13   A-only model freeze / model_freeze_lock.json
 ↓
后续  B一次性外部验证
```

任何前序硬门禁未通过：

> 后序任务不得运行。

---

# W00 — formal 结果归档与状态同步

## 目标

正式关闭 technical bootstrap 阶段。

## 已确认 formal 结果

- requested=1000；
- completed=1000；
- success=1000；
- nondegenerate rate=1.000；
- reference H-low center=2.101717；
- reference H-high center=3.519630；
- reference boundary=2.810674；
- bootstrap boundary median=2.811491；
- boundary 95% interval=[2.708194, 2.924580]；
- width/center distance=0.152609；
- assignment stability median=0.986711；
- assignment stability P5=0.960980；
- structural-state stability median=1.000；
- structural-state stability P5=0.997；
- formal_eligible=1。

最终判定：

> **FORMAL PASS**

## 必须保持

- 不追加 bootstrap 寻找更漂亮结果；
- 不调整 0.1%；
- 不调整 SLIC；
- 不调整 K；
- 不调整 normalization；
- 不重新比较 M1/M2/M3。

---

# W00R — 冻结前代码安全整改与回归门禁

该阶段是本版新增的**强制前置门禁**。

在 W00R 全部通过前：

> **不得执行正式 W01 `stage7_freeze`，不得生成第一把正式 freeze lock。**

## W00R.1 修复 stage7 的确定性运行错误

当前 `habitat_analysis/scripts/revised_workflow_technical.py` 必须确认显式导入：

```python
validate_freeze_lock
```

因为 `stage7_freeze()` 在 staging lock 写入后会调用该函数。

修复后必须通过：

```text
import module
→ construct staging lock
→ validate staging lock
```

的真实执行路径。

## W00R.2 增加 stage7 synthetic integration test

必须新增不含真实患者数据的测试，覆盖：

```text
mock/synthetic staged habitat assets
↓
freeze preflight pass
↓
staging feature/QC/dictionary/map manifest
↓
staging freeze lock
↓
validate_freeze_lock
↓
formal promotion commit point
```

测试至少验证：

- 缺少 `validate_freeze_lock` 或 lock 字段时 hard fail；
- 某个正式 artifact hash 改变时 lock validation fail；
- promotion 未完成时不能产生“合法冻结”状态。

`compileall` 不能替代该集成测试。

## W00R.3 升级第一阶段 lock schema

`freeze_lock.py` 必须定义并严格验证版本化 schema。

最少要求：

```text
freeze_schema_version = 1
habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false
outcome_columns_read = false
B_data_read = false
bootstrap_mode = formal
bootstrap_requested = 1000
bootstrap_completed = 1000
bootstrap_completion_status = complete
bootstrap_operational_pass = 1
formal_eligible = 1
eligibility_threshold_fraction = 0.001
eligibility_threshold_role = minimum_imaging_presence
threshold_selection_performed = false
threshold_audit_conclusion = NEUTRAL_WITH_TECHNICAL_CAUTION
```

缺字段、类型错误、未知 schema version、关键值错误均必须 fail closed。

## W00R.4 lock 必须绑定正式冻结输出

正式 `freeze_lock.json` 至少绑定：

- A393 ID hash；
- A137 ID hash；
- manifest hash；
- scanner map hash；
- preprocessing config hash；
- SLIC config hash；
- formal bootstrap summary hash；
- threshold audit hash；
- threshold confounding audit hash；
- `global_descriptors_full_A.csv` hash；
- `feature_qc.csv` hash；
- `feature_dictionary.md` hash；
- habitat maps manifest hash；
- global centers；
- boundary；
- source git commit。

必须生成：

```text
habitat_analysis/output/habitat_maps_A/habitat_maps_manifest.csv
```

或等效 manifest，逐例记录匿名 ID、正式 map 文件名与 SHA-256。

禁止只检查审计文件“存在”而不绑定其内容 hash。

## W00R.5 冻结 promotion 改为单一可恢复 commit point

推荐结构：

```text
freeze_bundles/
  freeze_<bundle_hash>/
      maps/
      features/
      feature_dictionary.md
      habitat_maps_manifest.csv
      freeze_lock.json

CURRENT_FREEZE.json
```

全部 staging 与 QC 验证完后，只原子切换：

```text
CURRENT_FREEZE.json
```

如果暂不采用 bundle，必须实现等价的 crash-recoverable transaction/commit marker，并有恢复测试。

仅在 Python exception 时做 rollback 不足以覆盖进程 kill/断电。

## W00R.6 legacy outcome builder 临时 fail closed

在 W05 真正改造成 A-only 之前，当前旧版：

```text
prognosis_analysis/scripts/build_model_dataset.py
```

如果仍会读取全量临床/预后表、B rows 或生成 B dataset，则必须：

- 暂时显式拒绝正式运行；或
- 从正式工作流入口移除。

不得依赖操作者“记住不要运行”。

## W00R.7 统一 split resolver

正式 A/B 定义只允许有一个实现，例如：

```text
resolve_cohort_membership()
```

A 定义固定为：

```text
GE MEDICAL SYSTEMS
+ DISCOVERY MR750
+ 3.0 T
```

以下脚本不得各自重写该规则：

- whole-tumor QC；
- habitat technical cohort；
- outcome builder；
- B validator；
- 后续 validation scripts。

## W00R.8 回归检查

至少运行：

```text
compileall
unit tests
stage7 integration test
freeze artifact tamper test
```

W00R 通过后，在项目状态中记录：

> `PRE_FREEZE_CODE_GATE = PASS`

然后才进入 W01。

---

# W01 — 正式 technical freeze

## W01.1 输入门禁

核验：

- W00R PASS；
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

## W01.2 运行

执行正式 `stage7_freeze` 或重构后的等效 freeze command。

生成：

- habitat maps；
- global descriptors；
- feature QC；
- feature dictionary；
- habitat maps manifest；
- strict `freeze_lock.json`；
- freeze bundle/commit marker。

## W01.3 主低维 G

固定：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

## W01.4 technical freeze QC

A393：

- exact n=393；
- unique ID=393；
- hard technical failures=0；
- 六个 G 全部 finite；
- H-low + H-high voxel conservation 成立。

A137：

- exact n=137；
- strict ⊂ lenient。

正式 maps：

- map manifest exact n=393；
- map files all present；
- map hashes complete；
- manifest hash 与 lock 一致。

## W01.5 第一把锁的含义

第一把锁生成后：

```text
habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false
```

但这里的 `A_outcome_unlock=true` 仅表示：

> technical prerequisite 已满足。

仍必须完成 W02、W03、W04、W05 后，Gate B 全部通过，W06 才能真正首次打开 A outcome 数据。

## W01.6 W01 后冻结资产不可变

任何以下文件改变：

-正式 habitat map；
- global descriptors；
- feature QC；
- feature dictionary；
- audit；
- technical cohort；
- config；

都会使原 lock 失效。

不得修改后继续沿用旧 lock。

---

# W02 — H-low/H-high Original radiomics 结局盲态提取框架

该步骤仍然：

> **outcome blind。**

## W02.1 输入

使用与主 habitat 相同的：

- muscle-normalized T2WI；
- `[1,1,2] mm`；
- 无 N4；
- tumor ROI；
- SLIC supervoxel labels；
- frozen technical method。

不重新 normalize/resample，不重新计算 binWidth。

## W02.2 参数

固定：

```text
imageType = Original
binWidth = 0.248808 approximately
PyRadiomics normalize = false
PyRadiomics resample = false
```

H-low/H-high 使用同一灰度标尺。

## W02.3 完整提取类别

每种 habitat 提取：

- firstorder；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

## W02.4 正式候选层级

Main：

> Original texture（GLCM/GLRLM/GLSZM/GLDM/NGTDM）。

Secondary：

> first-order。

Exploratory：

> shape。

## W02.5 对称特征块

```text
R_low  = H-low Original texture
R_high = H-high Original texture
```

两者方法地位完全相同。

## W02.6 结构性不存在

single-H-low：

> `R_high = structurally undefined`

single-H-high：

> `R_low = structurally undefined`

禁止填 0。

## W02.7 availability 状态

每例至少保存：

```text
H_low_present
H_high_present
R_low_extractable
R_high_extractable
R_low_failure_reason
R_high_failure_reason
```

必须区分 structural absence 与 technical failure。

---

# W03 — habitat-specific radiomics outcome-blind QC 与候选池冻结

W03 必须在首次读取 DFS 前完成。

## W03.1 R1/R2 重复性

每一读者独立经过同一固定技术流程，然后生成 H-low/H-high 并提取 Original radiomics。

## W03.2 ICC

分别计算：

```text
R_low ICC(2,1)
R_high ICC(2,1)
```

候选要求：

```text
ICC > 0.75
n_valid_pairs >= 预设最低值（建议10）
```

## W03.3 availability

在 A/R1 中，对相应 habitat 存在病例计算 finite feature rate。

建议候选要求：

```text
finite rate >= 95%
```

## W03.4 禁止 outcome-driven filtering

不得进行：

- univariate Cox；
- DFS association；
- outcome correlation；
- LASSO；
- prediction feature importance；
- 根据结果修改 ICC 阈值。

## W03.5 输出与候选池 hash

保存：

```text
H_low_original_icc.csv
H_high_original_icc.csv
H_low_candidate_features.csv
H_high_candidate_features.csv
availability_summary.csv
extraction_failures.csv
provenance.json
```

冻结：

```text
R_low_candidate_hash
R_high_candidate_hash
```

---

# W04 — modeling protocol 冻结

首次读取 A DFS 前生成：

```text
prognosis_analysis/modeling_protocol.json
prognosis_analysis/modeling_protocol.md
```

至少固定：

- 科学问题；
- endpoint；
- C/G/R_low/R_high/W 定义；
- M0–M5；
- eligible population 规则；
- structural absence 处理；
- nested CV；
- split seed policy；
- inner tuning；
- paired comparison；
- primary/secondary performance metrics；
- final architecture 决策层级。

## W04.1 模型

```text
M0  C
M1  C + H_high_fraction
M2  C + G
M3L C + G + R_low
M3H C + G + R_high
M4  C + G + R_low + R_high
M5  C + W
```

M4 仅在 dual-radiomics eligible cohort。

## W04.2 比较层级

```text
M0 → M1
M1 → M2
M2 → M3L
M2 → M3H
M3L vs M3H
M2 → M4
M0 → M5
```

## W04.3 CV

正式固定：

```text
Outer CV = 5-fold × 10 repeats
Inner CV = 5-fold
```

outer repeat seed：

```text
12345 + repeat_index
```

按 DFS event 分层；每个 training/validation fold 必须有 event。

## W04.4 penalized Cox

Radiomics：Elastic Net Cox 优先。

预设 alpha：

```text
0.1, 0.5, 0.9, 1.0
```

lambda 由 training-only inner CV 决定。

outer validation 不得参与调参。

---

# W05 — 真正 A-only 数据访问 + B 源级隔离

这是首次读取 A DFS 前最后一个硬门禁。

## W05.1 不允许“先读全表再筛 A”

正式 outcome 分析不得：

```python
clinical = read_excel(full_A_B_table)
clinical = clinical[clinical.split == "A"]
```

因为此时 B outcome 已经被正式分析进程读取。

同样禁止：

- 先载入全量 whole-tumor feature table 后再筛 A；
- 先载入 B habitat 后不用；
- 生成 `dataset_*_B.csv`；
- 统计 B 样本数、missingness 或 feature availability。

## W05.2 建立 A-only 源资产

在本地受控环境中，由数据隔离步骤生成只包含 A ID 的：

```text
prognosis_analysis/data/A_clinical_outcomes.*
```

或等效路径。

该资产必须：

- 只含 A technical cohort 合法 ID；
- 不含任意 B row；
- ID hash 与第一把锁/technical cohort 对齐；
- 生成过程不进入模型选择逻辑；
- B 原始临床/预后资产继续保持不可由正式分析路径访问。

建议 B 数据位于未挂载、独立权限或独立目录，并在 W13 前不暴露给正式脚本。

## W05.3 A-only builder

正式 builder 使用：

```text
--split A
```

或更严格地完全不提供 B/all 模式。

它只允许读取：

- A393/A modeling population；
- A137 membership；
- A clinical variables；
- A outcomes；
- A whole-tumor candidates；
- A technical/frozen assets。

## W05.4 A raw dataset

生成：

```text
dataset_primary_raw_A.csv
```

可包含：

- patient ID；
- DFS；
- C；
- full-A descriptive G；
- W candidate fields；
- descriptive variables。

注意：

> full-A G 只用于描述/final refit；nested CV 性能必须重新计算 fold-specific G。

## W05.5 habitat radiomics 不进入静态 full-A wide table用于内部CV

R_low/R_high 依赖 fold-specific boundary。

nested modeling 通过 fold-specific asset/cache 读取，不能直接使用 full-A frozen mask 提取的 R_low/R_high 来估计内部验证性能。

## W05.6 建立 outcome access guard

建议提供三个不同权限入口：

```text
read_technical_A()      # 不需要outcome lock
read_A_outcomes()       # 需要第一把lock + Gate B
read_B_validation()     # 需要第二把model lock
```

不得把安全责任留给每个脚本自行记得调用 `select_split()`。

## W05.7 单一 cohort resolver

A/B membership 必须复用 W00R 冻结的 resolver；builder 不得自行重新实现厂商/机型/场强判定。

## W05.8 Gate B

只有以下全部成立才可进入 W06：

- W01 strict freeze lock 有效；
- W03 candidate pools 已冻结；
- W04 modeling protocol 已冻结；
- A-only source asset 已建立并 hash 核验；
- legacy full A/B builder 已不能绕过；
- B source 对正式分析代码不可达；
- B builder 在 model lock 不存在时 hard fail。

否则：

> **不读取 DFS。**

---

# W06 — 正式首次读取 A DFS

W06 是整个项目第一次允许 outcome-aware 分析。

## W06.1 endpoint QC

报告：

- A 总人数；
- DFS event count；
- censor count；
- follow-up；
- median follow-up；
- reverse-KM follow-up；
- 3-year evaluable；
- 5-year evaluable；
- DFS_time≤0；
- duplicated ID；
- event/time conflict；
- missing outcome。

## W06.2 允许修改的内容

仅允许修正：

> 可追溯的原始数据错误。

不得根据影像/模型结果改变：

- DFS definition；
- censor date；
- follow-up cutoff；
- eligibility；
- A393/A137 technical definition。

## W06.3 冻结 A modeling population

生成：

```text
A_modeling_population.csv
```

排除原因只允许：

- 已冻结 technical exclusion；
- outcome 不可用；
- 明确数据错误且无法修复。

生成 ID hash 并纳入后续 model lock。

---

# W07 — 冻结 CV split plan

正式建模前生成固定 split files。

最少字段：

```text
影像号
repeat
fold
role
seed
```

## W07.1 Main split plan

用于 M0/M1/M2/M5。

## W07.2 R_low plan

在 R_low-eligible population 的相同 splits 中 paired 比较 M2 vs M3L。

## W07.3 R_high plan

在 R_high-eligible population 的相同 splits 中 paired 比较 M2 vs M3H。

## W07.4 dual plan

在 dual-radiomics eligible population 中用相同 splits 比较：

```text
M2, M3L, M3H, M4
```

split files 全部生成 hash，后续不得重新抽 splits 寻找更好结果。

---

# W08 — repeated nested CV

每个 `repeat × outer fold` 完整执行以下流程。

## W08.1 Outer split

取得：

```text
Train_outer
Validation_outer
```

Validation_outer 不参与任何参数估计。

## W08.2 Training-only global habitat centers

读取预缓存 SLIC labels 与 supervoxel means。

只用 Train_outer，患者等权：

```text
sum(supervoxel weights per patient) = 1
```

拟合 K=2 得到：

```text
C_low_train
C_high_train
b_train
```

## W08.3 应用 training boundary

Train_outer 和 Validation_outer 均使用同一个 `b_train` 生成 fold-specific habitat masks。

Validation_outer 不参与 boundary fitting。

## W08.4 fold-specific G

根据 fold-specific masks 重新计算六个 G。

禁止直接拿 full-A G 作为 outer validation feature。

## W08.5 fold-specific R_low/R_high

从 training/validation 各自 fold-specific habitat masks 提取 Original radiomics，只保留 W03 冻结的 candidate pools。

## W08.6 fold asset provenance

每 fold 至少保存：

```text
centers.json
train_global_habitat.csv
validation_global_habitat.csv
train_R_low.csv
validation_R_low.csv
train_R_high.csv
validation_R_high.csv
provenance.json
```

并记录：

- train ID hash；
- validation ID hash；
- centers/boundary；
- candidate hashes；
- code/config hashes。

## W08.7 Clinical preprocessing

imputation 参数只在 Train_outer 拟合，再应用 Validation_outer。

## W08.8 G preprocessing

G 应完整 finite；标准化只用 Train_outer。

## W08.9 W preprocessing

Train_outer 内：

1. near-zero variance；
2. correlation reduction（预设 `|rho| > 0.90`）；
3. standardization；
4. Elastic Net tuning/selection。

## W08.10 R_low/R_high preprocessing

采用与 W 相同的 training-only 规则。

结构性 absence 的处理必须遵循 W04 预先冻结策略。

## W08.11–W08.17 模型

```text
M0  C
M1  C + H_high_fraction
M2  C + G
M3L C + G + penalized R_low
M3H C + G + penalized R_high
M4  C + G + penalized (R_low + R_high)
M5  C + penalized W
```

C/G 不做 outcome-based univariate screening。

## W08.18 Outer prediction

inner CV 完成后用最佳训练参数 refit 完整 Train_outer，然后 Validation_outer 只做 transform/prediction。

不得在 Validation_outer 上重新：

- scaling；
- correlation filtering；
- feature selection；
- alpha/lambda tuning；
- boundary fitting；
- imputation fitting。

---

# W09 — A 内部验证结果汇总

所有性能必须来自 held-out outer validation predictions。

## W09.1 discrimination

报告：

- Harrell C-index；
- Uno C-index。

建议 Harrell 作为主 discrimination，Uno 为 censoring-robust 补充。

## W09.2 time-dependent metrics

- 3-year AUC；
- 5-year AUC。

## W09.3 calibration

- 3-year/5-year calibration；
- slope；
- calibration-in-the-large。

## W09.4 prediction error

- 3-year/5-year Brier；
- integrated Brier score（实现稳定时）。

## W09.5 paired comparison

M2 vs M3L、M2 vs M3H、M3L vs M3H 必须在相同 eligible patients + 相同 outer splits 中 paired evaluation。

## W09.6 selection stability

对每个 R_low/R_high/W feature 报告 selection frequency。

不能以单个 P 值决定“有效/无效”；重点看 effect size、incremental prediction、calibration、repeat/fold stability。

---

# W10 — 预设敏感性分析

## W10.1 A137 strict

A137 不是新的方法开发集。

优先在原 A outer split 框架下评价 strict subset held-out predictions。

重点 M0/M1/M2/M3L/M3H，M4 为补充。

## W10.2 Tumor-volume sensitivity

在相同 outer splits 中加入：

```text
log(tumor_volume)
```

形成：

```text
M2-V
M3L-V
M3H-V
```

## W10.3 dual-habitat-only

在 dual-radiomics eligible cohort 比较 M2/M3L/M3H/M4。

## W10.4 Whole-tumor comparator

M5 优于或不优于 M0 都接受，不因结果与既往不同修改当前技术 pipeline。

---

# W11 — A-only final model architecture

B 仍完全不可见。

final model 可以是：

- M0；
- M1；
- M2；
- M3L；
- M3H；
- M4。

M5 为 comparator，除非出现明确、稳定、可重复优势，否则不因高维特征更多优先选择。

## 决策原则

```text
hierarchy
+ incremental evidence
+ parsimony
+ stability
```

而不是最高一次 C-index。

顺序：

1. M0 → M1 → M2；
2. 若 M2 有合理基础，再评价 M3L/M3H；
3. 若一个 habitat 稳定增量，优先单 habitat；
4. 两个均有稳定信号时再评价 M4；
5. 若 habitat 模型均不改善 clinical，允许 M0 成为 final model。

不得因阴性结果回头改 0.1%、SLIC、K 或增加 Wavelet/LoG 寻找阳性。

---

# W12 — Full-A final refit

使用全部 A modeling patients。

## W12.1 deployment habitat

使用 full-A frozen technical centers：

```text
H-low = 2.101717
H-high = 3.519630
boundary = 2.810674
```

## W12.2 Final G

使用 W01 锁定的正式 full-A global descriptors，或重新计算后要求 bitwise/数值规则一致并通过 hash/QA。

## W12.3 Final R_low/R_high

若 final model 使用 habitat radiomics：

- full-A frozen masks；
- fixed Original parameters；
- fixed candidate pools。

## W12.4 Final W

若 final model 使用 W，采用既有冻结的 main `muscle_f0.25` candidate pool。

## W12.5 Final preprocessing/tuning

imputation、scaling、correlation reduction、alpha、lambda 仅使用 full A，并采用与 nested CV 一致的 tuning rule。

## W12.6 保存 deployment artifacts

至少：

```text
final_selected_features.csv
preprocessing.json
model_parameters.json
baseline_survival.csv
final_model_report.md
```

记录：

- final feature list；
- coefficients；
- imputation/scaling；
- correlation policy；
- alpha/lambda；
- baseline cumulative hazard/survival；
- 3-year/5-year prediction mapping。

## W12.7 A performance 引用

论文中的 A internal performance 必须来自 W08/W09 held-out predictions。

full-A refit training performance 不能作为内部验证性能。

---

# W13 — A-only model freeze

生成唯一正式第二把锁：

```text
prognosis_analysis/model_freeze_lock.json
```

## W13.1 严格 schema

建议：

```text
model_freeze_schema_version = 1
A_model_development_complete = true
A_model_frozen = true
B_data_read = false
B_validation_unlocked = true
```

缺任一必需字段或 artifact hash 不匹配时 B 仍锁定。

## W13.2 cohort dependency

记录：

- A modeling population hash；
- A393 hash；
- A137 hash；
- eligible population definitions。

## W13.3 technical dependency

记录：

- `freeze_lock.json` hash；
- freeze bundle/manifest hash；
- full-A centers/boundary；
- SLIC config hash；
- preprocessing config hash。

## W13.4 modeling protocol

记录：

- modeling protocol hash；
- outer splits hash；
- inner CV policy；
- outcome definition；
- endpoint horizons；
- model hierarchy；
- final architecture decision record。

## W13.5 feature definitions

记录：

```text
Clinical variables
G feature list
R_low candidate hash
R_high candidate hash
W candidate hash
```

## W13.6 final model artifacts

记录：

```text
final_model_id
final_model_family
final_model_feature_list/hash
final_model_coefficients_hash
preprocessing_parameter_hash
baseline_survival_hash
final_selected_features_hash
source_git_commit
```

## W13.7 第二把锁是唯一 B unlock

正式代码中必须移除/禁用任何平行 unlock：

```text
b_validation_unlock.json
```

不得存在：

```text
if old_unlock_exists: allow_B
```

所有 B 入口统一：

```text
validate_model_freeze_lock()
```

只有严格验证通过才允许打开 B 数据源。

## W13.8 B source mount/permission 切换

第二把锁成功生成并验证后，才允许将 B 临床/结局/feature 数据源挂载或开放给验证脚本。

在 mount/unlock 之前再次记录：

```text
B_data_read = false
```

## W13.9 Freeze 后禁止修改

不得根据 B：

- 改 final model；
- 改 H-low/H-high 选择；
- 改 radiomics features；
- 改 alpha/lambda；
- 改 clinical variables；
- 改 habitat；
- 改 0.1%；
- 改 missingness strategy；
- 重校 primary model。

B 只执行一次预先定义的外部验证。

---

# 三十三、每阶段硬门禁

## Gate 0 — pre-freeze code safety

必须：

- stage7 import bug 修复；
- stage7 integration test PASS；
- strict freeze schema PASS；
- artifact tamper test PASS；
- crash-safe/transactional promotion 方案完成；
- legacy outcome builder fail closed；
- split resolver 单一化。

## Gate A — technical freeze

必须：

- formal PASS；
- A393 exact；
- A137 exact；
- feature QC PASS；
- map manifest 完整；
- strict `freeze_lock.json` 有效且绑定所有正式资产。

## Gate B — outcome unlock

必须：

- habitat radiomics方法冻结；
- R_low/R_high候选池冻结；
- modeling protocol冻结；
- A-only source asset 已物理隔离；
- legacy full A/B 读取路径不可绕过；
- B source 对正式分析不可达。

否则不读取 DFS。

## Gate C — nested validation

必须：

- A endpoint QC 完成；
- A modeling population 冻结；
- split files 冻结并 hash。

## Gate D — final model selection

必须：

- 预设 M0–M5 分析完成；
- 主要 paired comparisons 完成；
- strict sensitivity 完成；
- volume sensitivity 完成；
- dual-habitat sensitivity 按计划完成。

## Gate E — A-only model freeze

必须：

- final architecture 确定；
- full-A refit 完成；
- final artifacts 完整；
- `model_freeze_lock.json` 严格验证通过；
- 旧 B unlock 路径禁用；
- B 仍未读取。

---

# 三十四、建议输出目录

```text
habitat_analysis/
├── freeze_bundles/                 # 若采用bundle方案
├── CURRENT_FREEZE.json             # 单一commit point
├── freeze_lock.json
└── output/
    ├── habitat_maps_A/
    │   └── habitat_maps_manifest.csv
    └── habitat_features_A/
        ├── global_descriptors_full_A.csv
        └── feature_qc.csv

prognosis_analysis/
├── modeling_protocol.json
├── modeling_protocol.md
├── model_freeze_lock.json
└── output/
    ├── pre_outcome/
    │   ├── habitat_radiomics_qc/
    │   └── access_guard/
    ├── A_endpoint_qc/
    ├── A_modeling/
    │   ├── population/
    │   └── splits/
    ├── nested_cv/
    │   ├── fold_assets/
    │   ├── M0_clinical/
    │   ├── M1_burden/
    │   ├── M2_global_habitat/
    │   ├── M3L_Hlow/
    │   ├── M3H_Hhigh/
    │   ├── M4_dual_habitat/
    │   └── M5_whole_tumor/
    ├── sensitivity/
    │   ├── strict_A137/
    │   ├── tumor_volume/
    │   └── dual_habitat_only/
    ├── A_model_comparison/
    └── final_model_A/
        ├── final_selected_features.csv
        ├── preprocessing.json
        ├── model_parameters.json
        ├── baseline_survival.csv
        └── final_model_report.md
```

患者级输出仍只保存在本地受控环境，不提交 GitHub。

---

# 三十五、关键回归测试

在正式 A modeling 前至少具备以下测试。

## 1. Stage7 runtime/integration

真实覆盖 staging lock validation 与 promotion；防止只通过 compileall。

## 2. Freeze artifact tamper

修改 global descriptors、map manifest、audit 或 dictionary 任一内容后：

> 原 freeze lock 必须失效。

## 3. Validation-patient exclusion

outer validation ID 绝不进入 K-means center fitting。

## 4. Fold-specific habitat

验证不同 outer fold 中同一患者允许因 training boundary 不同产生不同 habitat assignment，证明未误用 full-A boundary。

## 5. R_low/R_high symmetry

extraction、ICC、preprocessing、model selection 规则对称。

## 6. Structural absence

single-H-low → R_high undefined；single-H-high → R_low undefined；禁止自动填 0。

## 7. Training-only scaler/imputer

Validation 只能使用 training 参数。

## 8. Training-only correlation filter

Validation 不参与相关矩阵。

## 9. Training-only Elastic Net tuning

Outer validation 不参与 alpha/lambda 选择。

## 10. A outcome lock

第一把 lock 不存在或 Gate B 不通过时：

> `read_A_outcomes()` hard fail。

## 11. B source read guard

第二把 lock 不存在时：

- B builder hard fail；
- B file open/read function 不应被调用；
- 不能通过 `all` 模式绕过。

## 12. Single B unlock mechanism

即使伪造/遗留 `b_validation_unlock.json`，只要 `model_freeze_lock.json` 不存在或无效：

> B 仍 hard fail。

## 13. Cohort resolver consistency

所有正式脚本对同一 synthetic scanner table 得到完全相同 A/B membership。

---

# 三十六、A-only 阶段完成标志

进入 B 验证前必须同时存在并验证：

```text
PRE_FREEZE_CODE_GATE = PASS
habitat_analysis/freeze_lock.json
habitat map manifest / freeze bundle integrity PASS
prognosis_analysis/modeling_protocol.json
A-only source access guard PASS
prognosis_analysis/output/A_endpoint_qc/
prognosis_analysis/output/A_modeling/splits/
prognosis_analysis/output/nested_cv/
prognosis_analysis/output/A_model_comparison/
prognosis_analysis/output/final_model_A/
prognosis_analysis/model_freeze_lock.json
```

必须能够回答：

- H-high burden 是否增加 clinical 模型信息？
- macro-habitat 是否增加信息？
- H-low texture 是否增加信息？
- H-high texture 是否增加信息？
- H-low 与 H-high 哪个更稳定？
- 双 habitat 联合是否进一步改善？
- whole-tumor radiomics 在当前 A393 的增量价值如何？
- 发现是否对 A137 稳健？
- 是否主要由 tumor volume 解释？
- final A model 由哪些变量组成？
- final deployment 参数是否全部冻结并 hash？
- B 是否从未参与任何技术、特征、模型或缺失处理决定？
- 第二把锁之前是否不存在任何 B 数据源读取？

全部满足后：

> **A-only model development complete。**

此时由 `model_freeze_lock.json` 唯一声明：

```text
B_validation_unlocked = true
```

然后才进入 B 一次性外部验证。
