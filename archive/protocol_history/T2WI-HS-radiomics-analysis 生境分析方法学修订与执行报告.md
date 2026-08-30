# T2WI-HS-radiomics-analysis 生境分析方法学修订与执行报告

## 一、研究目标与当前方法

本项目拟在治疗前 T2WI 上建立跨患者统一的绝对信号表型，并评价不同肿瘤对这些表型的表达负荷和空间组织与无病生存期（DFS）的关系。主方法的科学估计对象是肌肉归一化后的群体水平 T2 表型，而不是每个患者内部相对最亮或最暗的区域。

图像强度定义为：

\[
I' = I / \mu_{\mathrm{muscle}}
\]

当前保留的方法为 M1：

```text
肌肉均值归一化
→ [1,1,2] mm 重采样
→ 4 mm 三维 SLIC
→ 保留与肿瘤 ROI 相交的全部有效超体素
→ 计算每个超体素内肿瘤体素的平均归一化 T2 信号
→ 每例总权重固定为1
→ patient-balanced global K-means，K=2
→ 按中心从低到高固定为 H-low 和 H-high
```

病例 \(i\) 有 \(n_i\) 个有效超体素时，每个超体素的拟合权重为：

\[
w_{ij}=1/n_i,\qquad \sum_j w_{ij}=1
\]

病例内 K-means 仅用于解释患者内部相对异质性，不生成主生境图、不进入预后模型，也不用于 B 集重新聚类。病例内 Z-score 会移除患者间绝对信号差异，不作为主方法。

## 二、已完成并可直接沿用的技术结论

### 2.1 上游预处理与标签规则

- R1 共693例均已完成严格预处理；主分析仅允许肌肉均值归一化，不允许 Z-score 回退进入全局聚类。
- R1 标签固定为肿瘤1、脂肪2、肌肉3。
- R2 的肌肉标签按逐病例规则解析；无法无猜测确定肌肉标签的R2不进入配对重复性评价，R1仍可用于主分析。
- R2仅用于后续重复性描述，不是主方法冻结或A集结局纳入的前置门槛。

### 2.2 方法选择

18例无结局技术比较已经完成。M2在 Mean 基础上加入 P90、IQR 和局部熵，并比较5 mm与7 mm局部窗口，但未改善共同表型共存情况，复杂度和解释负担反而增加。因此：

- M1保留为主方法；
- M2作为已完成的技术敏感性分析，不再进入候选竞争；
- M3纹理扩展不继续执行；
- 不再通过改变K值、缩小SLIC尺度、病例内强制分群或增加聚类特征来追求较低的空生境率。

### 2.3 A集无结局技术运行

A集393例已在不读取结局、临床变量和B集数据的条件下完成patient-balanced M1运行。全部病例均完成图像读取、几何核查、归一化、SLIC、聚类和肿瘤体素分配；算法失败、几何或标签错误及未分配肿瘤体素均为0。

全A描述性聚类结果为：

\[
C_{\mathrm{low}}=2.0955,\quad C_{\mathrm{high}}=3.3411,\quad b=2.7183
\]

其中 \(b=(C_{\mathrm{low}}+C_{\mathrm{high}})/2\) 为最近中心分配边界。上述数值仅用于全A技术描述；正式内部验证时必须在每个外层训练折重新拟合中心，不能将全A中心用于外层验证折。

## 三、单生境的正式解释

A集有156/393例（39.69%）仅表达一个全局表型。该现象应定义为结构性全局表型缺失，而不是技术失败：某例全部有效超体素位于统一群体边界的同一侧，因此均被分配到H-low或H-high。

后续必须区分三类状态：

1. **硬技术失败**：图像读取、几何、归一化、SLIC、非有限值、聚类数值或体素分配错误；
2. **结构性表型状态**：`single-H-low`、`single-H-high`或`dual-habitat`；
3. **条件性生境影像组学可用性**：某一表型不存在或体积过小，导致该表型内的纹理特征无法稳定定义。

单生境病例保留在主分析队列。下列量在单生境病例中具有合法的结构零：

- 缺失表型的存在指示为0；
- 缺失表型的体积分数为0；
- 生境熵为0，其中约定 \(0\log 0=0\)；
- H-low/H-high界面密度为0。

表型内纹理特征在相应表型不存在时属于结构性未定义，不能填0，也不应作为全队列主模型的必需输入。

## 四、主分析与次要分析的特征架构

### 4.1 全队列主要特征

主分析仅使用所有硬技术成功病例均可定义的低维全局表型特征。建议冻结以下候选：

|变量|定义|单生境处理|
|---|---|---|
|`H_high_fraction`|H-high体素数/肿瘤总体素数|可取0或1|
|`habitat_entropy`|\(-\sum_k p_k\log p_k\)|取0|
|`interface_density`|H-low/H-high三维邻接界面面积/肿瘤体积|取0|
|`H_high_largest_component_tumor_fraction`|最大H-high连通成分体积/肿瘤体积|H-high缺失时取0|
|`H_high_component_density`|H-high连通成分数/肿瘤体积（cm³）|H-high缺失时取0|
|`H_high_radial_burden`|H-high体素归一化径向深度之和/肿瘤总体素数|H-high缺失时取0|
|`sv_median_minus_boundary`|病例超体素Mean中位数减去训练边界|始终可定义|
|`sv_IQR`|病例超体素Mean的P75−P25|始终可定义|

`H_low_fraction=1-H_high_fraction`，不与`H_high_fraction`同时作为模型输入。`single-H-low`、`single-H-high`、`dual-habitat`、H-low/H-high体素数、P05/P95及中心距离作为描述和质控字段，不与其确定性派生变量重复进入模型。

### 4.2 条件性次要分析

`signal_contrast`及H-low/H-high内的一阶或纹理影像组学仅能在两个表型均达到技术要求时定义。该部分作为条件性次要分析，不影响全队列主分析，也不作为本轮解除结局盲态的前置门槛。最低体积或体素数必须在不读取结局的条件下依据提取成功率和特征有限性另行冻结；结构性未定义值不得插补为0。

## 五、方法冻结前尚需完成的工作

当前仍需完成以下事项：

1. 统一正式方案、冻结文件和机器可读配置：全部有效超体素、病例等权M1、结构性表型状态不计入硬技术失败；
2. 利用现有全A逐例诊断表补齐单生境方向、近空生境及相对边界位置的统计；
3. 在全A完成病例内K=2的local-global机制诊断；
4. 在患者层面bootstrap评估全局中心、边界和分配稳定性；
5. 排查结构状态是否主要由归一化质量、采集序列或肿瘤大小驱动；
6. 在严格高信号A=137子集中完成预设敏感性描述；
7. 冻结全病例可定义的主特征字典和生成规则；
8. 在上述无结局工作通过后，仅纳入A集DFS和预设临床变量，并在建模开始前停止。

A集按设计来源于同一设备平台，因此“扫描仪稳健性”不能作为A内冻结门槛。A内仅评价序列和采集参数、肌肉归一化质量及肿瘤体积等技术因素；跨设备迁移性留待全A模型冻结后在B集一次性评价。双读者分析继续作为后续重复性描述，不作为本阶段停止门槛。

## 六、可执行的下一步工作流

### 阶段0：建立只读基线并统一协议

**输入**

- `habitat_analysis/output/feasibility_A_patient_balanced/`
- `habitat_analysis/output/method_selection_18/`
- `生境分析方案与工作流.md`
- `habitat_analysis/analysis_freeze.md`
- `habitat_analysis/configs/main_cross_case_kmeans_k2_4mm.json`
- `habitat_analysis/README.md`
- `PROJECT_STATUS.md`

**操作**

1. 保存现有M1运行清单、输入清单、全局中心和逐例诊断表的SHA-256；原结果设为只读，不覆盖。
2. 将正式聚类配置统一为“全部有效超体素＋每例总权重1”，取消每例2000个超体素上限。
3. 将硬技术失败限定为读取、几何、归一化、SLIC、非有限特征、聚类数值和未分配体素错误。
4. 将`empty_habitat`移入`structural_state`，不再计入技术失败率或病例排除条件。
5. 保留硬技术失败率规则：修复后失败病例比例<5%时可记录并剔除后继续，≥5%时停止；当前全A硬技术失败率为0%。
6. 在协议修订记录中注明本次修订在DFS、临床变量及B集不可见条件下完成。

**输出**

- 更新后的正式方案、冻结文件和JSON配置；
- `habitat_analysis/protocol_amendment_structural_state.md`；
- `habitat_analysis/output/technical_baseline_checksums.csv`。

**通过条件**

- 文档与配置对M1、失败类型和结构状态的定义完全一致；
- 配置中不存在`max_supervoxels_per_case_for_fit=2000`或将空生境计入失败的规则；
- 所有修订文件不含结局结果和原始影像号。

### 阶段1：核验全A M1基线

**操作**

1. 核对输入清单恰有393个唯一A-R1病例，且运行清单中`outcome_columns_read=False`、`B_data_read=False`。
2. 核对两中心和边界均为有限值、中心不重合、H-high中心高于H-low中心。
3. 核对逐例诊断表恰有393行且病例唯一；每例肿瘤体素均被分配，H-low与H-high体素数之和等于肿瘤总体素数。
4. 核对算法、几何/标签和未分配体素错误均为0。
5. 若仅缺少派生统计，直接使用现有逐例诊断表，不重跑图像、SLIC或聚类。
6. 若发现原始图像、ROI、预处理或超体素Mean发生实质更正，仅重跑受影响病例的上游预处理/SLIC；由于全局中心依赖全部病例，随后必须对全A重新拟合M1中心并重新分配全部393例。

**输出**

- `habitat_analysis/output/structural_diagnostics_A/baseline_integrity.csv`
- `habitat_analysis/output/structural_diagnostics_A/baseline_integrity.md`

**停止条件**

- 行数、病例唯一性、体素守恒或数据隔离任一不满足；
- 硬技术失败率≥5%。

### 阶段2：结构性表型诊断

本阶段直接从现有`case_diagnostics.csv`派生，不重复运行SLIC。

**逐例计算**

```text
fraction_H_low
fraction_H_high
minority_fraction = min(fraction_H_low, fraction_H_high)
state = single-H-low / single-H-high / dual-habitat
minority_eq_0
minority_lt_0_01
minority_lt_0_05
minority_lt_0_10
sv_min, sv_P05, sv_median, sv_P95, sv_max
P05_minus_b
P95_minus_b
```

按稳健分位数定义病例相对全局边界的位置：

- `global-low predominant`：\(P95<b\)；
- `boundary-crossing`：\(P05\le b\le P95\)；
- `global-high predominant`：\(P05>b\)。

**汇总**

1. 分别报告`single-H-low`、`single-H-high`和`dual-habitat`例数及比例；
2. 报告`minority_fraction=0`、`<1%`、`<5%`和`<10%`；
3. 报告三类边界位置状态及其P05/P95分布；
4. 检查结构状态、边界状态和体素计数之间的逻辑一致性。

**输出**

- `habitat_analysis/output/structural_diagnostics_A/habitat_case_distribution.csv`
- `habitat_analysis/output/structural_diagnostics_A/structural_state_summary.csv`
- `habitat_analysis/output/structural_diagnostics_A/structural_state_report.md`

**通过条件**

- 393例全部获得唯一结构状态；
- 所有体积分数位于[0,1]且两类之和在数值容差内等于1；
- 单生境计数与既有156例一致。若不一致，先追溯定义或输入版本，不继续后续阶段。

### 阶段3：全A local-global机制诊断

**操作**

1. 生成全A超体素级中间表，字段至少包括匿名病例号、超体素标签、肿瘤体素数、物理体积和Mean归一化T2。若现有运行未保存完整超体素级值，则按冻结参数重新执行无结局SLIC与Mean汇总；该操作不读取结局或B集。
2. 以重新生成的超体素表复算全Apatient-balanced M1。有效超体素数和逐例体素数必须与阶段1一致，中心及边界与基线的绝对差应≤`1e-6`；否则停止并追溯实现或输入版本。
3. 从完整超体素表补充每例P25、P75和`sv_IQR=P75-P25`。
4. 对每例的全部有效超体素Mean单独拟合K=2；固定k-means++、`n_init=100`、`max_iter=300`、`tol=1e-4`和随机种子12345。
5. 仅保存排序后的`local_center_low`、`local_center_high`和`local_center_distance`，不生成正式生境图。
6. 计算：

\[
B_i=(L_{i,\mathrm{low}}+L_{i,\mathrm{high}})/2-b
\]

以及两个局部中心相对 \(b\) 的偏移。
7. 将病例分为“两个局部中心均低于边界”“跨越边界”“两个局部中心均高于边界”。
8. 有效超体素少于2个或Mean只有一个不同取值时，将local K=2记为诊断不可用，但不将病例从主分析队列剔除。

**输出**

- `habitat_analysis/output/local_global_diagnostic_A/supervoxel_mean_A.csv`
- `habitat_analysis/output/local_global_diagnostic_A/local_global_diagnostic.csv`
- `habitat_analysis/output/local_global_diagnostic_A/local_global_summary.md`

**解释规则**

若多数单生境病例的两个局部中心均位于全局边界同一侧，则说明患者内相对异质性存在，但不构成两个跨患者共同绝对表型；这不触发方法替换。

### 阶段4：患者层面bootstrap稳定性

**输入**

每例全部有效超体素Mean及病例索引。该表不得含DFS、临床变量或B集病例。

**操作**

1. 固定随机种子12345，执行1000次患者层面有放回抽样；每次抽取393个患者实例。
2. 某患者被抽中多次时按抽样实例重复贡献；每个实例内部超体素权重和为1。
3. 每次重新拟合patient-balanced K=2，排序中心并记录 \(C_{low}\)、\(C_{high}\)、\(b\) 和中心距离。
4. 使用每次bootstrap边界重新分配原全A超体素，计算每例H-high体积分数及相对于全A参考分配的体素加权一致率。
5. 报告中心、边界、中心距离的中位数、标准差、2.5%和97.5%分位数。

**推荐的操作性通过标准**

- 非退化拟合成功率≥99%；
- 全A边界位于bootstrap 95%区间内；
- 边界95%区间宽度不超过全A中心间距的25%；
- 病例级分配一致率中位数≥0.95，且第5百分位数≥0.80。

**输出**

- `habitat_analysis/output/bootstrap_stability_A/bootstrap_global_centers.csv`
- `habitat_analysis/output/bootstrap_stability_A/case_assignment_stability.csv`
- `habitat_analysis/output/bootstrap_stability_A/bootstrap_stability_report.md`

**分支**

- 全部通过：进入阶段5；
- 仅病例级一致率不通过：定位靠近边界的病例，报告连续margin特征并进入技术复核，不修改K、SLIC尺度或聚类特征；
- 中心/边界稳定性不通过或退化拟合≥1%：暂停结局纳入，检查异常病例影响、归一化和采集因素；不自动启用M2/M3或病例内K-means。

### 阶段5：归一化与采集因素诊断

A集由同一设备平台构成，本阶段比较的技术因素包括：

```text
muscle_mean_raw
muscle_mean_preprocess
muscle CV
muscle gradient（如已有）
fat/muscle ratio
序列标识及可用采集参数
tumor volume
n_supervoxels
```

**操作**

1. 按`single-H-low`、`single-H-high`和`dual-habitat`分组报告中位数、四分位数及标准化差异；分类变量报告各层级状态比例。
2. 绘制边界位置、肌肉归一化指标、肿瘤体积和超体素数之间的无结局诊断图。
3. 不以单个P值决定保留或排除；重点识别是否存在某一序列、异常归一化区间或极端肿瘤大小几乎决定结构状态的情况。
4. 若发现可修复的上游错误，只重做受影响病例的预处理/SLIC；其后按阶段1规则对全A重新拟合中心并重新执行阶段2至5。

**输出**

- `habitat_analysis/output/technical_robustness_A/structural_state_by_qc.csv`
- `habitat_analysis/output/technical_robustness_A/technical_robustness_report.md`

**通过条件**

- 无证据表明结构状态由明确的归一化错误或单一异常采集层级近乎完全决定；
- 所有发现的可修复上游错误均已处理并完成全A连锁更新。

### 阶段6：严格高信号子集敏感性

**操作**

1. 使用既有严格高信号A=137名单筛选阶段2结果；保持全A M1中心和标签不变，不在该子集重新聚类。
2. 报告三类结构状态、exact-empty及minority `<1%`、`<5%`、`<10%`比例。
3. 与A=393比较时仅作无结局机制描述，重点判断宽松体素级入组标准与4 mm超体素级表型之间是否存在尺度差异。
4. A=137继续作为预设敏感性集，不因单生境率变化替代宽松主分析集。

**输出**

- `habitat_analysis/output/sensitivity/strict_A137_structural_state.csv`
- `habitat_analysis/output/sensitivity/strict_A137_structural_state.md`

### 阶段7：冻结M1与主特征字典

**冻结条件**

1. 全A硬技术失败率<5%；
2. 结构状态统计完整且通过体素守恒检查；
3. bootstrap达到阶段4的操作性标准；
4. 结构状态未被确认由可修复的归一化或采集错误主导；
5. 主特征均能在全部硬技术成功病例中得到有限值。

**操作**

1. 冻结M1参数、标签方向、结构状态定义及主特征公式。
2. 为每个主特征记录名称、单位、公式、输入、允许范围、结构零规则和QC条件。
3. 用全A中心生成仅供技术描述和最终全A拟合准备使用的生境图及特征表。
4. 明确标记：全A中心生成的特征不能直接用于嵌套交叉验证的外层验证折；建模阶段必须按外层训练折重新拟合中心并重新生成训练/验证特征。
5. 条件性生境影像组学保持次要分析状态，不影响主特征冻结。

**输出**

- `habitat_analysis/feature_dictionary.md`
- `habitat_analysis/output/habitat_maps_A/`
- `habitat_analysis/output/habitat_features_A/global_descriptors_full_A.csv`
- `habitat_analysis/output/habitat_features_A/feature_qc.csv`
- `habitat_analysis/analysis_freeze.md`的最终技术冻结版本。

**不通过分支**

任一冻结条件不满足时暂停，不读取结局；提交对应的稳定性或技术复核报告。不得根据预后结果反向调整M1。

### 阶段8：A集临床与结局变量纳入

本阶段是本工作流的终点。只有阶段7完成后才可解除A集结局盲态；B集图像、临床和结局继续保持不可见。

**8.1 锁定病例索引**

1. 以A集技术成功病例清单为唯一主索引；当前若硬技术失败仍为0，则应为393例。
2. 使用本地影像号—匿名号映射生成分析匿名号；原始影像号不得写入仓库或可提交结果。
3. 记录宽松主分析集、严格敏感性集、结构状态及技术排除状态，但结构状态不作为排除条件。

**8.2 纳入预设临床变量**

主建模临床变量固定为：

```text
年龄
CEA_log
mrT_4级
mrN_3级
MRF
mrEMVI
thickness
EID
活检病理非腺癌
```

性别、length和distance仅可保留在队列描述表，不进入临床、生境或联合模型的建模字段。此时只完成字段合并和缺失性审计，不进行插补、标准化或变量筛选。

**8.3 纳入结局**

1. 主终点字段固定为`DFS_time`和`DFS_event`，统一时间单位为月。
2. 核对`DFS_event`仅为0/1，`DFS_time>0`，事件病例有有效时间，重复病例为0。
3. 统计总DFS事件数，以及36个月和60个月内发生的DFS事件数；时间依赖AUC所需的删失处理留到建模阶段。
4. CSS和OS仅作为预设探索性终点登记，不参与本轮方法判断。
5. 不读取或合并B集结局。

**8.4 合并与审计**

1. 对技术索引、临床表和DFS表执行一对一连接；输出未匹配、重复和关键字段缺失清单。
2. 核对合并前后病例数、技术状态、结构状态和严格子集标记不变。
3. 生成变量角色字典，明确`id`、`technical_qc`、`descriptive_only`、`clinical_predictor`、`endpoint`和`future_foldwise_feature`。
4. 保存输入文件哈希、脚本版本、运行时间和病例流转计数。

**输出**

- `habitat_analysis/output/modeling/analysis_index_A_locked.csv`
- `habitat_analysis/output/modeling/cohort_descriptive_A.csv`
- `habitat_analysis/output/modeling/variable_roles_A.csv`
- `habitat_analysis/output/modeling/outcome_integration_qc.csv`
- `habitat_analysis/output/modeling/outcome_integration_manifest.json`

`analysis_index_A_locked.csv`只包含匿名号、纳入/技术状态、9个预设临床变量、DFS字段及建模阶段所需的上游索引；不把用全A中心生成的描述性生境特征当作可直接用于内部验证的固定模型特征。

**最终通过条件**

- 一对一连接成立，无未解释的病例丢失或重复；
- 终点取值、时间单位和事件计数通过核验；
- 9个临床变量与描述专用变量的角色清楚；
- 结局纳入未改变任何图像、生境、特征定义或病例排除规则；
- B集仍未读取；
- 输出及清单的SHA-256已保存。

完成上述核验后立即停止。不得在本阶段拟合Cox模型、计算AUC/C-index、执行插补或标准化、进行特征选择、确定lambda或查看任何模型性能。

## 七、建模前的完成判定

只有以下条件全部满足，项目才可进入下一阶段建模：

```text
协议与配置已统一
AND 全A硬技术完整性通过
AND 结构状态已完整量化
AND local-global机制诊断完成
AND bootstrap稳定性通过
AND 归一化/采集技术复核通过
AND 严格A=137敏感性完成
AND 主特征字典与生成规则已冻结
AND A集临床与DFS一对一合并并通过QC
AND B集仍不可见
```

达到该状态时，后续建模应从预先冻结的外层训练折内聚类、特征生成和数据处理开始；本报告不启动或评价任何预后模型。
