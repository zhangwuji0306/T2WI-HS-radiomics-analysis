# T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书

**当前分析性质：**

> 探索性影像生境预后研究。

当前尚未确定 H-low 或 H-high 哪一类生境携带主要预后信息，因此不得预设“H-low 一定更重要”或“H-high 一定更重要”。

本阶段核心科学假说为：

> **在具有可识别瘤内 T2 高信号成分的直肠癌中，将整个肿瘤视为单一 ROI 可能混合具有不同信号表型和生物学属性的组织区域，从而稀释影像组学中的预后信息。基于冻结的 H-low/H-high 生境分割后，预后信息可能存在于 H-low、H-high、两者的空间组织方式，或其组合之中。**

---

# 本版修订说明

2026-08-31 对当前 `main` 分支进行代码与协议一致性审阅后，本任务书增加以下硬性约束：

1. 当前 `revised_workflow_technical.py` 的 `stage7_freeze()` 在调用 `validate_freeze_lock()` 前必须完成显式导入修复，并增加能够真实走到 lock validation/promotion 分支的无患者数据集成测试；仅 `compileall` 和孤立的 lock 单元测试不足以作为 W01 放行依据。
2. 第一阶段 `freeze_lock.json` 必须升级为**严格版本化冻结清单**，不仅绑定输入与参数，也必须绑定正式冻结输出；禁止“lock 有效但正式 habitat feature/map 已被替换”的状态。
3. 在首次读取 A 结局之前，必须完成真正的 **A-only 数据访问改造**。禁止先读取含 B 的整张临床/预后表或全量 B 特征后再筛选 A；A outcome 分析应只接触预先物理隔离的 A-only 数据源。
4. 第二阶段 B 解锁只能由 `prognosis_analysis/model_freeze_lock.json` 完成。旧的 `b_validation_unlock.json` 或任何平行 B 解锁机制不得作为正式分析入口。
5. 所有正式 A/B cohort 判定必须复用单一 split resolver；不得在多个脚本中分别重写厂商、机型和场强规则。

上述修订属于**防止代码绕过研究设计的工程性硬门禁**，不改变已经冻结的科学问题、0.1% eligibility、4 mm SLIC、K=2、patient-balanced clustering、A393/A137、临床变量块、主要终点或模型层级。

---

# 一、既往证据及其在本研究中的定位

## 1.1 既往整瘤 radiomics 结果

此前已经完成过整瘤 T2WI radiomics 分析，结果提示整瘤 radiomics 模型的预测性能低于临床模型。这一结果是提出 habitat 分析的重要背景证据。

但此前分析使用的是未按照当前“存在 T2 高信号成分”标准筛选的更宽泛患者队列，与当前 A393 主队列并不完全相同。因此不能写成：

> “整瘤 radiomics 已被证明在 A393 中无预测价值。”

更准确的定位是：

> **既往不同但相关队列中的结果降低了整瘤 radiomics 具有较强增量预测价值的先验可能性，并为进一步研究肿瘤内部生境分解提供了方法学动机。**

---

# 二、当前核心研究问题

本阶段不以“寻找性能最高的任意 radiomics 模型”为目标，而围绕以下递进问题展开：

## Q1

在当前 A393 中，冻结的低维 habitat descriptors 是否在临床模型基础上提供增量预测信息？

## Q2

如果存在增量信息，它主要来自：

- 高信号负荷本身；
- H-low/H-high 空间组织；
- H-low 内部纹理；
- H-high 内部纹理；
- H-low 与 H-high 的组合？

## Q3

传统 whole-tumor radiomics 在当前 A393 中是否再次表现出有限的增量价值？

## Q4

habitat-specific radiomics 是否能够提取出整瘤 radiomics 中因不同组织成分混合而被稀释的信息？

---

# 三、不设置 H-low 与 H-high 的方向性先验

虽然此前经验提出过“H-low 可能才是主要预后区域”，但目前证据不足以将其作为正式方向性假设。

因此冻结前必须规定：

> **H-low 和 H-high 具有对称的分析地位。**

不得先只分析 H-low、看到结果后才决定是否分析 H-high，或反之。

两种 habitat-specific radiomics 必须采用：

- 相同预处理；
- 相同 Original 特征定义；
- 相同 ICC 规则；
- 相同 nested CV；
- 相同模型家族；
- 相同评价指标。

H-low 和 H-high 谁更具有预测信息，由 A 集探索性分析结果回答，不能在结果出来前预设。

---

# 四、第一阶段：代码安全门禁与 technical freeze

## 4.1 已完成 formal 技术稳定性

formal patient-level bootstrap 已完成：

- 1000/1000；
- nondegenerate rate=1.000；
- reference boundary=2.810674；
- bootstrap boundary median=2.811491；
- 95% CI=[2.708194, 2.924580]；
- CI width / center distance=0.152609；
- assignment stability median=0.986711；
- assignment stability P5=0.960980；
- structural-state stability median=1.000；
- structural-state P5=0.997；
- `formal_eligible=1`。

结论：

> **FORMAL PASS。**

因此不再修改：

- 0.1%；
- 4 mm SLIC；
- K；
- 患者等权策略；
- normalization；
- bootstrap 次数用于方法选择。

## 4.2 Gate 0：freeze 前代码安全修复

**在正式运行 W01 technical freeze 之前，必须先完成并验证以下项目。**

### A. 修复 stage7 运行阻断

`revised_workflow_technical.py` 必须显式导入并可调用：

```text
validate_freeze_lock
```

必须增加 synthetic/integration test，使测试真实覆盖：

```text
staging assets
→ staging lock
→ validate_freeze_lock
→ promotion/commit point
```

不得仅以 `compileall` 通过作为 stage7 可运行证据。

### B. 第一把锁采用严格 schema

`freeze_lock.json` 必须至少含：

```text
freeze_schema_version = 1
habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false
outcome_columns_read = false
B_data_read = false
eligibility_threshold_fraction = 0.001
eligibility_threshold_role = minimum_imaging_presence
threshold_selection_performed = false
threshold_audit_conclusion = NEUTRAL_WITH_TECHNICAL_CAUTION
```

缺少任一必需字段、字段类型不符或值不符时必须 fail closed。

### C. 锁必须绑定正式冻结资产

除既有 patient/config/bootstrap hashes 外，至少绑定：

- `global_descriptors_full_A.csv` hash；
- `feature_qc.csv` hash；
- `feature_dictionary.md` hash；
- habitat maps manifest hash；
- formal bootstrap summary hash；
- threshold audit hash；
- threshold confounding audit hash；
- A393/A137 ID hashes；
- preprocessing/SLIC config hashes；
- centers 与 boundary。

393 个 habitat map 可先生成：

```text
habitat_maps_manifest.csv
```

逐文件记录匿名 ID 与 SHA-256，再由 `freeze_lock.json` 绑定该 manifest 的 hash。

### D. promotion 必须有单一可恢复 commit point

正式冻结不得依赖“连续若干 `os.replace()` 全部恰好完成”来定义成功。应采用以下之一：

1. 不可变 freeze bundle + 单一 `CURRENT_FREEZE` 指针原子切换；或
2. 等效的 crash-recoverable transaction/commit marker。

Python 异常 rollback 可以保留，但不能作为唯一的崩溃一致性保证。

### E. 旧 outcome builder 在 W05 完成前必须 fail closed

当前 legacy `build_model_dataset.py` 在 A-only 改造完成前不得成为可运行的正式 outcome 入口。若其仍会加载全量 A/B 临床、结局或 feature，则必须显式拒绝运行或移出正式执行入口。

Gate 0 未通过：

> **不得运行正式 W01，不得生成第一把正式 freeze lock，更不得读取 A outcome。**

## 4.3 第一阶段正式 technical freeze

Gate 0 通过后执行 technical freeze，生成：

- 正式 habitat maps；
- global descriptors；
- feature QC；
- feature dictionary；
- habitat map manifest；
- 严格 `freeze_lock.json`。

第一把锁只允许：

> **后续在 W02–W05 完成后读取 A outcome。**

第一把锁本身**不允许读取 B**，也不代表可以立即跳过 W02–W05 读取 DFS。

---

# 五、A 集正式建模队列

## 5.1 主队列

A393。

## 5.2 严格敏感性队列

A137。

A137 不得重新：

- 选阈值；
- 重新定义技术方法；
- 重新定义 habitat。

内部 CV 中仍按 outer training fold 拟合 fold-specific centers/boundary；这属于预先规定的验证程序，不是重新选择技术方法。

---

# 六、主终点

主终点：

> DFS。

主要时间点：

- 3 年；
- 5 年。

OS/CSS 为次要结局，在主 DFS 分析方案冻结后再分析。

---

# 七、固定临床基线变量块 C

Clinical block 固定为 9 项：

1. 年龄；
2. `CEA_log`；
3. `mrT_4级`；
4. `mrN_3级`；
5. MRF；
6. mrEMVI；
7. thickness；
8. EID；
9. 活检病理非腺癌。

以下变量不进入主预测模型：

- 性别；
- length；
- distance。

术后病理变量不进入治疗前 prediction model。

---

# 八、低维全局 habitat 特征块 G

固定 6 项：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

分别描述 H-high burden、全局信号位置、supervoxel 级异质性、habitat interface、H-high connectivity 和 radial localization。

`habitat_entropy` 与 `H_high_component_density` 继续作为描述性/次要变量。

---

# 九、新增 habitat-specific Original radiomics

本阶段正式增加两个对称特征块：

## R_low

> H-low ROI 内提取的 Original PyRadiomics 特征。

## R_high

> H-high ROI 内提取的 Original PyRadiomics 特征。

---

# 十、为什么当前只提 Original

本阶段不扩展 Wavelet、LoG。理由：

1. habitat ROI 比 whole-tumor ROI 更小；
2. 高阶滤波显著增加维度；
3. 小 H-high 区域可能产生较高纹理不稳定性；
4. 当前科学问题首先是验证“分区本身是否恢复预后信息”，而不是最大化特征空间。

以后开展 Wavelet/LoG habitat radiomics 时必须明确标记为：

> post-hoc exploratory analysis。

---

# 十一、habitat Original 特征类别

完整提取：

- first-order；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

## 11.1 主要 habitat-radiomics 候选

优先：

> texture features。

H-low/H-high 本身由 signal-based clustering 定义，first-order Mean、Median、Percentiles 等与 habitat 定义存在部分数学耦合；texture 更直接回答“已定义 habitat 内部的空间灰度组织是否仍携带信息”。

## 11.2 First-order

提取、QC 并保留，作为 secondary habitat-radiomics candidate。

## 11.3 Shape

完整提取用于 QC 和探索，但不作为主要 habitat-radiomics signature 的优先候选，因为其与 H-high fraction、largest component、interface、radial burden 存在明显概念重叠。

---

# 十二、灰度离散化

habitat Original 使用已冻结主影像参数：

- muscle normalization；
- `[1,1,2] mm`；
- fixed binWidth 约 `0.248808`；
- PyRadiomics 内部不重新 normalize；
- 不重新 resample。

不得根据 H-low/H-high 自身强度分布重新计算 binWidth。

---

# 十三、habitat-specific radiomics 的 ICC

必须使用 A 集双读者数据。

每一读者均根据自身 ROI/影像经过相同完整流程：

```text
reader-specific image/ROI
→ fixed technical pipeline
→ habitat assignment
→ habitat-specific radiomics
```

分别计算：

- R_low ICC(2,1)；
- R_high ICC(2,1)。

预筛选标准：

> ICC > 0.75。

有效成对病例数必须达到建模协议预设的最低要求；建议 `n_valid_pairs >= 10`。不得使用 B ICC 筛选。

---

# 十四、结构性单 habitat 病例

当前 A393：

- dual-habitat：368；
- single-H-low：24；
- single-H-high：1。

因此 24 例不存在 H-high，1 例不存在 H-low。对应 habitat 内部 radiomics 属于：

> structurally undefined。

不能填 0。

---

# 十五、habitat-specific radiomics 的结构性缺失处理

原始数据层：

```text
H_high_feature = NA
```

表示 H-high 不存在，而不是 H-high 纹理等于 0。

正式建模协议必须预先区分：

- structural absence；
- technical extraction failure；
- ordinary missingness。

结构性缺失不得与随机 missing 混为一类。主模型中的具体处理规则必须在首次读取 DFS 前写入 `modeling_protocol.json`，并在 training fold 内执行。

---

# 十六、dual-habitat sensitivity analysis

针对 dual-radiomics eligible 病例额外进行 R_low/R_high 均完整存在的敏感性分析，用于检验结构性缺失处理是否影响主要结论。

该分析只作为 sensitivity，不替代 A393 主分析。

---

# 十七、whole-tumor radiomics W 的重新定位

现有整瘤 radiomics 包含 Original、Wavelet、LoG。既往相关队列中观察到 radiomics model < clinical model，因此本研究不把 W 作为主要方法开发方向。

但由于当前 A393 与既往队列不同，W 仍需作为 reference comparator 重新评价，用于回答：

> habitat decomposition 是否提供了传统 whole-tumor radiomics 未捕获的信息。

---

# 十八、Whole-tumor radiomics 的处理原则

继续使用已有 outcome-blind ICC 候选池。

在 nested CV training fold 内部进行：

- near-zero variance filtering；
- correlation reduction；
- scaling；
- LASSO/Elastic Net Cox；
- hyperparameter tuning。

不得重新大规模探索预处理方案。

所有 A/B split 判定必须调用统一的 cohort/split resolver，不允许 `stage6_qc.py`、`build_model_dataset.py` 或后续脚本各自维护不同版本的 A 定义。

---

# 十九、正式模型层级

## M0 — Clinical baseline

> C

回答标准治疗前临床/MRI预测能力。

## M1 — Clinical + high-signal burden

> C + `H_high_fraction`

回答单纯知道高信号“多少”是否增加信息。

## M2 — Clinical + global habitat

> C + G

回答 habitat 空间组织是否超出单纯 high-signal burden。

## M3L — Clinical + global habitat + H-low radiomics

> C + G + R_low

回答 H-low 内部纹理是否在 macro-habitat 结构之外提供信息。

## M3H — Clinical + global habitat + H-high radiomics

> C + G + R_high

回答 H-high 内部纹理是否在 macro-habitat 结构之外提供信息。

## M4 — Clinical + global habitat + dual-habitat radiomics

> C + G + R_low + R_high

只在 dual-radiomics eligible cohort 中评价。

## M5 — Clinical + whole-tumor radiomics

> C + W

定位为 conventional whole-tumor radiomics comparator，不是本研究重点开发模型。

---

# 二十、最重要的模型比较

本研究不强调“哪个模型 AUC 最高”，而强调问题导向比较：

- `M0 → M1`：high-signal burden 本身有没有信息？
- `M1 → M2`：空间组织信息是否超出单纯 burden？
- `M2 → M3L`：H-low 内部纹理是否增加信息？
- `M2 → M3H`：H-high 内部纹理是否增加信息？
- `M3L vs M3H`：哪一种 habitat 具有更稳定的增量价值？该比较明确标记为 exploratory comparative analysis。
- `M2 → M4`：同时加入两种 habitat 纹理是否进一步改善？
- `M0 → M5`：whole-tumor radiomics 在当前 A393 中的增量价值如何？

不能因为 H-low/H-high 其中一个胜出就把另一个称为“无生物学意义”。

---

# 二十一、不进行无限模型排列组合

不预设增加：

- C+W+R_low；
- C+W+R_high；
- C+W+G+R_low；
- C+W+G+R_high；
- C+W+G+R_low+R_high。

若以后运行，必须明确标记为 post-hoc exploratory analysis，不能用于正式 final model 选择。

---

# 二十二、H-low vs H-high 比较方式

不能仅比较两个模型表面 C-index 谁大。必须在相同 eligible population 与相同 outer CV splits 中 paired evaluation。

主要比较：

- ΔHarrell C-index；
- ΔUno C-index；
- Δ3-year AUC；
- Δ5-year AUC；
- Brier；
- calibration；
- feature-selection stability。

重点关注 H-low/H-high 信号是否在不同 repeat/fold 中持续出现，而不是一次性某折表现最好。

---

# 二十三、高维模型使用 penalized Cox

R_low、R_high、W 使用 Elastic Net Cox/LASSO Cox。

所有数据驱动步骤必须进入 inner CV：

- imputation；
- scaling；
- variance filtering；
- correlation filtering；
- penalty selection；
- feature selection。

Clinical 和固定低维 G 原则上强制保留或使用较低/零 penalty；radiomics 接受 penalty。

---

# 二十四、fold-specific habitat 是硬门禁

A 集 cross-validation 中不能使用 full-A global centers 生成全部患者 habitat 后直接做 CV。

每个 outer fold 必须执行：

```text
outer training
↓
仅 training patients 拟合 K=2 centers/boundary
↓
training/validation 均使用 training boundary 生成 habitat mask
↓
重新计算 fold-specific G
↓
提取 fold-specific R_low/R_high
↓
training fold 内 radiomics preprocessing/selection
↓
模型拟合
↓
validation prediction
```

因此 H-low/H-high radiomics 也必须是 fold-specific。

---

# 二十五、允许预缓存的 patient-internal operation

可提前缓存：

- muscle-normalized image；
- tumor ROI；
- SLIC labels；
- 每个 supervoxel mean。

不需要每个 outer fold 重新运行 SLIC。

每 fold 重新执行：

> boundary assignment → H-low/H-high masks → G → habitat radiomics。

---

# 二十六、tumor volume sensitivity

outcome-blind 分析已经发现 high_fraction 与 tumor volume 相关，因此预设：

- M2 + log(tumor_volume)；
- M3L + log(tumor_volume)；
- M3H + log(tumor_volume)。

目的为判断 habitat/habitat-specific radiomics 是否主要代理 tumor burden。不得根据该结果修改 habitat 定义。

---

# 二十七、A137 严格敏感性分析

A137 沿用主分析方法，不作为新的方法开发集。

重点重复 M0、M1、M2、M3L、M3H。M4 因样本量更小可作为补充。

优先在 A393 预先冻结的 outer split 体系下评价 strict phenotype，而不是在 A137 内重新开发聚类和模型。

---

# 二十八、whole-tumor radiomics 既往结果的论文表述

不得写：

> “Whole-tumor radiomics had no prognostic value.”

建议写：

> Previous analyses in a broader rectal-cancer cohort suggested limited incremental predictive value of whole-tumor T2WI radiomics relative to clinical variables. Because that cohort was not restricted using the current high-signal eligibility definition, whole-tumor radiomics was retained as a reference comparator rather than treated as a definitive negative control.

---

# 二十九、核心生物学假说的最终表述

建议冻结为：

> **We hypothesized that whole-tumor radiomic averaging may obscure prognostically relevant heterogeneity by mixing spatially distinct T2 signal phenotypes. Accordingly, we evaluated whether prognostic information was preferentially carried by the H-low habitat, the H-high habitat, their macroscopic spatial organization, or combinations thereof, without prespecifying which habitat would be prognostically dominant.**

---

# 三十、数据隔离、第一把锁与第二把锁

## 30.1 第一把锁：`habitat_analysis/freeze_lock.json`

第一把锁是 technical artifact lock，不是普通“运行完成标记”。

它必须：

- 使用严格版本化 schema；
- 绑定正式 habitat maps/features/QC/dictionary 与关键审计资产；
- 绑定 A393/A137、config、bootstrap 与 boundary；
- 声明 `A_outcome_unlock=true`；
- 声明 `B_unlock=false`；
- 在生成时保持 `outcome_columns_read=false`、`B_data_read=false`。

第一把锁生成后仍必须完成 W02–W05，Gate B 通过后才允许首次读取 A DFS。

## 30.2 A outcome 必须来自物理 A-only 数据源

W05 后正式 A outcome 入口不得读取一个同时含 A 和 B 的 Excel/CSV 后再用 `split == A` 过滤。

正式分析应使用：

```text
A_clinical_outcomes.*
```

或等效的、在本地受控环境中预先生成且只含 A ID 的数据资产。

B 临床/结局源文件在第二把锁前应保持：

- 不挂载；或
- 不可由正式分析路径访问；或
- 由独立受控目录/权限隔离。

A-only 文件的 ID 集必须与第一把锁中的 A cohort hash 对齐。任何额外 ID、缺失 ID 或重复 ID 均 fail closed。

## 30.3 第二把锁：`prognosis_analysis/model_freeze_lock.json`

第二把锁只能在以下全部完成后生成：

- A outcome QC；
- nested A validation；
- H-low/H-high paired comparison；
- strict sensitivity；
- volume sensitivity；
- final architecture；
- full-A refit；
- deployment parameters/artifacts hash 完整。

第二把锁是**唯一正式 B 解锁凭据**。

不得再使用或创建能独立放行 B 的：

```text
b_validation_unlock.json
```

或其他平行 unlock 文件。

所有 B reader/builder 必须统一调用：

> `validate_model_freeze_lock()` 或等效的单一严格验证入口。

第二把锁必须在 B 尚未读取时声明：

```text
A_model_development_complete = true
A_model_frozen = true
B_data_read = false
B_validation_unlocked = true
```

并绑定最终模型、预处理参数、candidate pools、A modeling population、CV plan、technical freeze 与 source commit。

## 30.4 B 不得用于决定

B 不得用于：

- H-low 还是 H-high 更重要；
- threshold；
- model family；
- clinical variables；
- feature pool；
- penalty；
- lambda；
- calibration strategy；
- habitat definition；
- missingness strategy。

B 只用于 model freeze 后的一次性外部验证。

---

# 三十一、A 阶段结束后的决策原则

### 情形 A：R_low 稳定增量、R_high 无明显增量

结论可表述 H-low 可能是主要预后信息载体，但必须注明 exploratory finding requiring external validation。

### 情形 B：R_high 更强

同样接受，不回头修改假说。

### 情形 C：二者均有信息

讨论不同 habitat 可能代表不同风险维度。

### 情形 D：单独均有限，但 R_low+R_high 组合有效

提示 prognostic information may reside in inter-habitat complementarity。

### 情形 E：habitat radiomics 无增量，但 G 有效

说明宏观空间结构可能比复杂纹理更稳健。

### 情形 F：G、R_low、R_high 均无增量

同样属于有效研究结果：技术稳定性不自动意味着预后预测价值。不得因此重新调 SLIC/K/0.1%。

---

# 三十二、具体工作流

正式执行以仓库根目录：

> `三十二、具体执行工作流：从formal PASS至A-only model freeze.md`

为准。

该工作流必须包含：

```text
W00 formal归档
→ W00R 冻结前代码安全整改
→ W01 technical freeze
→ W02–W05 outcome-blind方法与A-only访问冻结
→ W06 首次读取A DFS
→ W07–W12 A-only modeling/refit
→ W13 model_freeze_lock
→ 后续B一次性验证
```

---

# 三十三、最终原则

本阶段不是寻找哪个影像模型 AUC 最高，而是回答：

> **在具有高 T2 信号成分的直肠癌中，将肿瘤分解为 H-low 和 H-high 之后，是否能够发现整瘤分析所掩盖的预后信息，以及这种信息主要位于何种生境层级。**

因此：

- Whole-tumor radiomics = reference comparator；
- Global habitat descriptors = macro-habitat representation；
- H-low radiomics = candidate intra-habitat representation；
- H-high radiomics = equally ranked candidate intra-habitat representation；
- H-low vs H-high = exploratory biological comparison；
- Clinical model = prediction baseline；
- First freeze = technical artifact integrity + A outcome permission only；
- Second freeze = final model integrity + the only B unlock；
- A/B isolation = code-enforced and source-level, not merely a statement in documentation。
