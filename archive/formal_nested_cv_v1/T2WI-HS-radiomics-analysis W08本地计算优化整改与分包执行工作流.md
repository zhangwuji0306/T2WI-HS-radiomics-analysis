# T2WI-HS-radiomics-analysis W08本地计算优化整改与分包执行工作流

## 0. 工作流定位

本工作流是《T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md》中P6/R6-7正式W08执行前的本地技术整改补充。它不替代科学主协议，不重新定义W01–W07，也不授权W09、模型冻结或B集验证。

本轮目标是：在严格执行冻结K-means `n_init=100`的前提下，减少fold-specific影像组学与nested-CV的重复计算，使formal W08能够在本地锁定环境中稳定、可观察、可恢复地完成。

本工作流执行到formal W08技术完整性复核结束即停止。不得解释模型性能，不得进入W09。

## 1. 当前执行起点

当前项目状态按以下事实处理：

- 最近一次formal W08因外部运行会话中断而停止；
- 该attempt仍可能保留`.staging`目录和SLIC缓存，但没有完整正式输出；
- `predictions.csv`、正式性能结果和`model_freeze_lock.json`均不得视为已经生成；
- `10 vs 100`一致性校验被人工停止，未形成可接受结论；
- 冻结主配置规定跨病例K-means使用`n_init=100`；
- 工作区可能存在尚未提交的`n_init`共享参数和进度记录草稿，执行时必须先核对归属和完整性，不得直接覆盖或默认接受；
- B访问四项必须继续为`false`。

## 2. 不可改变的分析边界

### 2.1 科学参数

下列内容保持冻结：

- A主分析集及其既有身份绑定；
- W07固定outer split；
- 10 repeats × 5 outer folds；
- 5-fold inner CV；
- K-means K=2、k-means++、患者平衡权重、固定fold seed；
- K-means `n_init=100`、`max_iter=300`、`tol=1e-4`；
- SLIC 3D、目标尺度4 mm及既有预处理；
- R-low 49项和R-high 10项冻结候选；
- 临床、G、R-low、R-high和W特征块定义；
- alpha网格`[0.1, 0.5, 0.9, 1.0]`；
- 每个alpha 100个lambda；
- Elastic-Net `max_iter=3000`、`tolerance=1e-7`；
- zero-start；
- Cox目标函数、gradient、proximal update、line search和收敛条件；
- 13个formal run及其模型人群；
- `minimumROISize=10`及P3B结构/技术状态规则；
- outer validation不得参与边界、预处理、特征选择或lambda选择。

### 2.2 本轮明确不实施

本轮不得：

- 减少outer repeats、outer folds或inner folds；
- 缩减alpha/lambda网格；
- 按中途性能删除候选或模型；
- 引入early stopping改变候选池；
- 更换Cox solver、PyRadiomics或SimpleITK版本；
- 引入warm start；
- 引入GPU实现；
- 读取、复制或统计B集；
- 将患者级输入、缓存、特征、预测或结果提交Git；
- 将中断attempt改写为成功；
- 在正式输出不完整时进入W09。

### 2.3 允许改变的工程参数

以下仅属于本地执行参数，可在验证后记录于运行审计：

- `representation_workers`；
- `outer_fold_workers`；
- BLAS/OMP线程数；
- staging内缓存位置；
- 进度记录频率；
- 同一attempt内的checkpoint和恢复方式。

这些参数不得改变任何fold的输入、模型选择、数值结果或正式输出结构。

## 3. 目标计算结构

```text
冻结A人群与W07 split
        ↓
50个training-only K-means边界（n_init=100）
        ↓
病例×fold生境分配和掩膜签名
        ↓
同病例完全相同掩膜去重
        ↓
仅提取冻结候选的fold-specific G/R特征
        ↓
50份fold-specific表示进入staging
        ↓
outer-fold多进程nested-CV
        ↓
逐fold原子checkpoint与确定性归并
        ↓
50 folds / 13 runs完整性核验
        ↓
一次性提升正式W08输出
```

影像组学表示生成和模型拟合必须分为两个非嵌套并行阶段。不得同时开启representation进程池、outer-fold进程池和数值库多线程。

## 4. 项目原生记录与输出位置

### 4.1 正式代码和测试

正式代码位于：

```text
prognosis_analysis/scripts/
tests/
```

### 4.2 本地敏感运行产物

所有病例级、fold级和预测级产物只允许写入：

```text
prognosis_analysis/output/w08_formal_A/
prognosis_analysis/output/w08_local_optimization_probe/
```

上述目录受`.gitignore`排除，不得提交。

### 4.3 可提交证据

仅允许提交不含患者标识、原始路径、病例级值和性能结果的：

- 方法与执行工作流；
- 代码和配置；
- synthetic/aggregate测试结果；
- 聚合耗时和资源摘要；
- 脱敏技术审计；
- 独立Reviewer结论；
- 项目状态摘要。

### 4.4 分包执行规则

正式分包按`isolated-batch-orchestrator`执行。每个编号工作单元对应一个独立Worker及其独立Reviewer，不得在未获批准时拆分、合并、跳过或重排。Worker和Reviewer均为独立顶层会话，不得继续委派。Reviewer只复核，不修复；不通过时由新的整改Worker处理。

项目文件、Git提交、测试结果和本地输出是跨单元交接依据；聊天记忆不得作为唯一证据。临时调度信息不写入永久项目结构。

## 5. 总依赖图

```text
L0  中断现场封口与代码归属核对
 ↓
L1  n_init=100单一来源与进度可观察性
 ↓
L2  无性能本地基准与热点确认
 ↓
 ├───────────────┐
 ↓               ↓
L3R             L3C
影像组学精确化   Cox核心等价优化
 └───────┬───────┘
         ↓
L4  fold-specific表示、掩膜复用与缓存
 ↓
L5  outer-fold并行、checkpoint与恢复
 ↓
L6  集成等价性和本地执行参数确定
 ↓
L7  最终代码P5/G3R技术预检
 ↓
L8  current-code binding与formal release gate
 ↓
L9  本地formal W08
 ↓
L10 正式输出技术完整性复核并停止
```

只有L3R和L3C允许并行；二者必须使用隔离工作区，并在各自通过独立复核后由L4统一集成。其余单元按图串行。

# 一、L0——中断现场封口与代码归属核对

## L0目标

将中断的formal attempt和人工终止的一致性校验转化为明确、可审计、不会阻塞新release gate的状态，并形成干净的代码整改起点。

## L0输入

- `git status`与当前HEAD；
- `prognosis_analysis/execution_status.json`；
- `prognosis_analysis/output/w08_formal_A/run_state.json`；
- `prognosis_analysis/output/w08_formal_A/attempts/`；
- 当前未提交和未跟踪文件；
- 现有失败attempt审计模式；
- `archive/protocol_history/n_init_equivalence_cancelled/`中的已停止一致性校验材料。

## L0执行动作

1. 核对本机不存在残留W08或一致性校验进程。
2. 核对中断attempt没有完整manifest、正式predictions或已提升结果。
3. 使用现有failed-attempt结构将`.staging`关闭为显式失败归档：
   - `status=failed`；
   - `failure_stage=external_execution_interruption`；
   - `final_outputs_generated=false`；
   - 记录原attempt ID和code commit；
   - B访问四项为`false`。
4. 更新根`run_state.json`和`execution_status.json`，不得继续显示正在运行。
5. 保留失败现场，不覆盖既有失败attempt。
6. 核对`archive/protocol_history/n_init_equivalence_cancelled/`中的一致性校验归档未被当作当前执行入口，且没有结论性输出被用于正式判断。
7. 对当前未提交代码逐文件判断归属：
   - 与L1目标一致的草稿保留给L1；
   - 与当前流程无关但属于用户的改动保持原状；
   - 不得擅自删除或纳入提交。
8. 输出仅含聚合状态的脱敏现场审计。

## L0输出

```text
prognosis_analysis/W08_local_L0_reconciliation_audit.md
prognosis_analysis/W08_local_L0_reconciliation.json
```

本地失败attempt继续位于被忽略的output目录。

## L0验收条件

- 无活动W08/一致性校验进程；
- 不存在未登记的`.staging` attempt；
- 中断attempt明确为失败，不是成功或可直接续跑；
- 正式输出仍不存在；
- 一致性校验明确为未完成、无结论；
- B访问四项为`false`；
- 当前代码草稿归属清楚；
- Reviewer接受其作为L1输入。

## L0禁止

- 删除失败attempt以绕过release gate；
- 复用任何未完成模型结果；
- 启动新的formal W08；
- 生成或解释性能；
- 读取B。

# 二、L1——`n_init=100`单一来源与进度可观察性

## L1目标

使所有W08生产和技术预检入口从同一冻结来源读取`n_init=100`，并提供不含患者信息和性能信息的运行进度。

## L1输入

- L0接受的干净起点；
- `habitat_analysis/configs/main_cross_case_kmeans_k2_4mm.json`；
- `prognosis_analysis/scripts/w08_formal_run_a.py`；
- `prognosis_analysis/scripts/w08_nested_cv.py`；
- `prognosis_analysis/scripts/w08_technical_preflight_a.py`；
- 当前工作区已有的`w08_kmeans_parameters.py`及progress草稿，仅作为候选实现。

## L1实现要求

1. 建立唯一共享参数入口，验证冻结配置中的：
   - `algorithm=kmeans`；
   - `k=2`；
   - `initialization=k-means++`；
   - `n_init=100`；
   - `max_iter=300`；
   - `tol=1e-4`。
2. formal provider、frame provider和technical preflight均消费同一参数入口。
3. formal CLI不得允许覆盖`n_init`。
4. 删除生产路径中的`n_init=10`硬编码。
5. progress只允许记录：
   - 阶段；
   - 当前repeat/fold/run名称；
   - 已完成fold/run数；
   - 总fold/run数；
   - 开始、更新时间和耗时；
   - B访问四项。
6. progress不得记录患者标识、模型系数、预测、指标或病例级失败信息。
7. progress写入必须原子化；progress写入失败不得改变模型计算，但须在最终审计中可见。
8. `run_state.json`、progress和attempt state的成功/失败语义必须一致。

## L1测试

- 配置为100时三个入口得到100；
- 配置缺失、类型错误或不等于100时fail closed；
- production source不再出现活动的`n_init=10`；
- progress schema不允许患者字段和性能字段；
- callback缺失时库函数仍按原逻辑运行；
- callback异常不会污染模型结果；
- B访问四项不能被callback覆盖为true；
-现有W08 targeted tests全部通过。

## L1输出

- 共享K-means参数模块；
- W08三个入口的参数绑定；
- progress实现与回归测试；
- `prognosis_analysis/W08_local_L1_parameter_observability_audit.md`。

## L1验收条件

- `n_init=100`在所有生产入口一致；
- 其他K-means参数未改变；
- progress不含敏感信息和性能；
- 所有相关测试通过；
- 工作树只含L1授权改动；
- Reviewer接受后方可执行L2。

# 三、L2——无性能本地基准与热点确认

## L2目标

在不产生outer-validation预测或性能指标的情况下，量化本地运行中各阶段的耗时、缓存命中和资源占用，为后续优化提供同机基准。

## L2允许的数据范围

允许使用：

- synthetic确定性矩阵；
- 不含结局的A-only技术影像、ROI和supervoxel摘要；
- frozen split中的角色信息，但不得连接`DFS_time`或`DFS_event`；
- synthetic time/event/risk数组，仅用于底层函数耗时和回归测试。

不得使用真实A结局进行solver或指标测量，不得生成或保留真实outer-validation risk、C-index、AUC、Brier、calibration或模型比较。Synthetic函数返回值仅作为软件回归对象，不得表述为模型性能。

## L2测量阶段

至少分别记录：

1. A输入加载；
2. SLIC cache准备与校验；
3. 单fold K-means 100次初始化；
4. 生境掩膜和6项G特征；
5. R-low PyRadiomics；
6. R-high PyRadiomics；
7. ModelPreprocessor；
8. synthetic单个Elastic-Net候选拟合；
9. synthetic完整100-lambda alpha路径；
10. synthetic Uno C-index权重准备和底层函数调用；
11. 峰值RSS、CPU利用率和磁盘读写摘要。

## L2执行约束

- 在同一本机、同一conda环境、同一线程设置下重复至少3次；
- 报告中仅保留中位数、范围和聚合计数；
- 病例标识和绝对路径不得进入可提交报告；
- probe不得调用formal writer；
- probe输出写入`prognosis_analysis/output/w08_local_optimization_probe/`；
- 不以旧`n_init=10`作为科学对照，只允许作为纯耗时参考。

## L2输出

```text
prognosis_analysis/scripts/w08_local_optimization_probe.py
tests/test_w08_local_optimization_probe.py
prognosis_analysis/W08_local_L2_baseline_profile_audit.md
```

## L2验收条件

- 各阶段耗时可区分；
- 能判断PyRadiomics、Cox候选拟合和I/O的相对占比；
- 未产生性能或患者级可提交输出；
- B访问四项为`false`；
- Reviewer确认L3R/L3C可据此独立执行。

# 四、L3R——PyRadiomics冻结特征精确化

## L3R目标

只计算正式模型实际使用的R-low 49项和R-high 10项特征，同时保持这些特征与当前完整类别提取器的数值完全一致。

## L3R实现要求

1. 根据`FROZEN_CANDIDATE_FEATURES`按feature class拆分特征名。
2. 分别构建R-low和R-high extractor。
3. 仅启用`Original`图像类型。
4. R-low只启用49项候选；R-high只启用10项候选。
5. 禁用未使用的shape和其他特征。
6. 保持：
   - `binWidth=0.248808`；
   - `normalize=false`；
   - `resampledPixelSpacing=null`；
   - `minimumROIDimensions=2`；
   - P3B `minimumROISize=10`及兼容shim；
   - label=1。
7. extractor初始化一次后在所属进程中复用，不跨进程共享。
8. 未返回任一冻结特征时fail closed，不得填充静默默认值后继续。

## L3R等价性样本

确定性测试至少覆盖：

- 恰好10个体素的可提取ROI；
- 接近最小尺寸的非规则ROI；
- 大ROI；
- R-low和R-high；
- 各冻结feature class；
- structural absence；
- technical small ROI；
- 具有多个灰度级和纹理方向的synthetic mask。

## L3R验收条件

- 59项冻结特征名称、数量和顺序一致；
- 对同一image/mask，旧提取器与新提取器的59项值完全一致；
- 状态分类和失败语义一致；
- 未使用特征不再计算；
- 固定基准中位耗时不高于L2；
- Reviewer接受后提交独立commit供L4集成。

## L3R禁止

- 修改候选池；
- 修改bin width或离散化；
- 修改mask；
- 为提速跳过可提取ROI；
- 改变PyRadiomics版本。

# 五、L3C——Cox核心等价优化

## L3C目标

减少Elastic-Net候选拟合中重复的排序、风险集、似然、梯度和删失权重计算，不改变solver路径和选择结果。

## L3C允许优化

1. 对每次fit预先建立：
   - 稳定降序time order；
   - sorted time/event/X；
   - unique event-time边界；
   - risk-set endpoint；
   - event count和event-X汇总。
2. 一次Cox核心调用同时返回log-likelihood和gradient。
3. `_smooth()`不得为了value和gradient重复执行同一风险集计算。
4. 当前beta的smooth objective、完整objective和accepted proposal可在同一迭代内复用。
5. inner fold的删失KM量、Uno权重和可比较病例对预先生成，并供该fold全部候选复用。
6. 保持candidate顺序、alpha顺序、lambda顺序和zero-start。

## L3C明确禁止

- warm start；
- active-set或strong-rule筛选；
- 候选并行导致候选顺序改变；
- 修改objective、gradient、penalty或line search；
- 修改`max_iter`或`tolerance`；
- 用外部Cox库替换当前solver；
- 使用实际outer-validation性能作为等价性证据。

## L3C测试矩阵

至少覆盖：

- 无ties和含ties的生存时间；
- 低维和高维设计矩阵；
- alpha 0.1、0.5、0.9、1.0；
- 大lambda、中lambda和小lambda；
- 正常收敛、backtracking和明确失败；
- coefficient、objective、gradient、risk-set和audit字段；
- 100点候选选择reducer。

## L3C数值验收

- 离散状态、candidate顺序、选择的alpha/lambda和失败集合必须完全一致；
- objective、gradient、coefficient及synthetic risk使用既有R6-5 `1e-10`比较阈值；
- convergence status和failure semantics一致；
- 不生成正式risk或性能；
- 固定基准中位耗时不高于L2；
- Reviewer接受后提交独立commit供L4集成。

# 六、L4——fold-specific表示、掩膜复用与缓存

## L4目标

集成L3R和L3C，并将每fold重复的病例影像处理改为一次边界计算、掩膜签名去重和可验证的fold-specific表示生成。

## L4集成前提

- L3R和L3C均已获独立Reviewer接受；
- 两个commit在目标工作区可见；
- 不存在未接受分支改动；
- 合并后完整测试可运行。

## L4掩膜签名规则

每个病例、每个fold按其training-only boundary生成R-low/R-high supervoxel标签分配。缓存复用的必要条件为：

- 同一病例；
- 同一block；
- 完全相同的体素级二值mask；
- 同一图像和ROI几何；
- 同一冻结extractor配置；
- 同一PyRadiomics/SimpleITK环境。

不得根据boundary接近、体素数相同或摘要统计相同推定mask相同。

## L4两阶段表示生成

1. 顺序读取50个固定outer-training集合。
2. 使用`n_init=100`计算50个边界。
3. 为每个病例生成50个分配签名。
4. 统计每例唯一签名数及理论复用率。
5. 对唯一mask提取G/R特征。
6. 将结果映射回50个fold。
7. 每fold生成一份完整表示，必须覆盖该fold全部A病例。
8. 每份表示携带：
   - repeat/fold；
   - training ID hash；
   - boundary和centers；
   - feature schema；
   - P3B状态计数；
   - validation未参与拟合的标志。
9. 病例级表示只写入`.staging/work/representations/`。

## L4缓存策略

- SLIC label/ROI cache继续逐例验证；
- 当前attempt内的feature cache允许复用；
- 跨attempt复用必须通过现有输入、配置和环境绑定；
- 任一cache mismatch只重算对应病例/签名；
- mismatch必须记录，不能静默接受；
- cache不进入Git。

## L4验收条件

- 50个fold均有唯一training-derived boundary；
- 每fold表示覆盖完整A人群；
- 缓存命中与直接重算的mask、状态和59项特征一致；
- paired populations、eligible counts及P3B状态与直接provider一致；
- 外层验证ID未用于boundary或eligibility阈值学习；
- 不生成模型拟合、预测或性能；
- Reviewer接受后方可执行L5。

# 七、L5——outer-fold并行、checkpoint与恢复

## L5目标

在同一本地工作站上并行执行独立outer folds，并使外部会话中断后能够安全恢复同一代码和输入下已完成的fold。

## L5并行实现

1. 新增受控执行参数：

```text
outer_fold_workers = 1 | 2 | 4
```

2. 默认本地值为2。
3. 每个进程一次只处理一个完整outer fold及其13个run。
4. 每个worker独立持有provider、预处理器和solver对象。
5. worker不写正式根输出，只返回或写入所属fold checkpoint。
6. coordinator按`repeat → fold → FIXED_RUN_IDS`排序归并。
7. 禁止线程共享PyRadiomics extractor。
8. 禁止nested multiprocessing。
9. 启动前固定：

```text
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
OPENBLAS_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1
```

## L5 checkpoint结构

每个完成fold写入：

```text
.staging/work/checkpoints/repeat_<r>_fold_<f>/
```

checkpoint至少包含：

- fold状态；
- fold结果；
- selection records；
- held-out prediction内部结果；
- repeat/fold/run完整性；
- 当前code commit；
- W06/W07/W07A绑定；
- K-means参数；
-环境指纹；
- 完成时间。

checkpoint属于本地敏感中间产物，不得提交，也不得在全部fold完成前解释。

## L5恢复规则

只有以下全部一致时允许恢复：

- attempt ID；
- code commit；
- W06人群；
- W07 split；
- W07A协议；
- K-means参数；
-候选特征身份；
- solver参数；
- Python、NumPy、scikit-learn、PyRadiomics、SimpleITK版本。

恢复时逐fold验证checkpoint schema和run数量。不完整或不一致的fold单独废弃并重算；不得跨不同代码提交拼接。

## L5失败语义

- 任一worker异常立即停止分派新fold；
- 已完成checkpoint保留在当前staging；
- attempt保持未完成，不提升正式输出；
- 可恢复故障由显式resume入口继续；
- 不满足恢复绑定时，将attempt关闭为failed并新建attempt；
- 不允许人工复制CSV拼接正式结果。

## L5测试

- 1 worker与2 workers处理相同fold结果一致；
- worker完成顺序变化不改变最终排序；
- 一个worker失败时无正式输出；
- 模拟中断后恢复与连续运行结果一致；
- checkpoint被截断、篡改或跨commit时fail closed；
- B访问四项始终为`false`；
- progress正确反映已完成fold，而非仅反映任务已分派。

## L5验收条件

- 串行和并行的离散结果完全一致；
- 浮点结果满足L3C/R6-5等价标准；
- 失败和恢复测试通过；
- transaction输出边界未弱化；
- Reviewer接受后方可进入L6。

# 八、L6——集成等价性和本地执行参数确定

## L6目标

对L1–L5的最终集成代码进行完整正确性与性能核验，并确定formal W08唯一允许的本地worker设置。

## L6正确性矩阵

至少核对：

- 50个K-means centers/boundaries；
- fold seed；
- 代表性病例的low/high mask；
- G特征；
- R-low 49项；
- R-high 10项；
- P3B状态；
- fold-specific population；
- paired comparator覆盖；
- ModelPreprocessor输出；
- 100点lambda候选顺序；
- alpha/lambda选择；
- coefficient、convergence及failure audit；
- serial/parallel输出排序；
- checkpoint/resume一致性；
- B访问边界。

其中真实A数据只用于不含结局的provider、mask和特征表示核验；solver、coefficient、risk及选择reducer等比较只使用既有确定性synthetic fixture，不得打开真实A结局列或生成真实性能。

## L6性能比较

在同一机器、同一环境、同一输入和线程设置下，对基准与集成版本分别重复至少3次，报告中位数：

- representation阶段耗时；
- 单fold模型阶段耗时；
- 总技术probe耗时；
- PyRadiomics调用次数；
- Cox核心调用次数；
- mask signature复用率；
- 峰值RSS；
- CPU和磁盘摘要。

复杂缓存和并行机制只有在正确性通过且固定probe总耗时中位数至少下降20%时保留。若未达到：

- 保留`n_init=100`和progress；
- 保留已证明简单、正确且无性能倒退的单项优化；
- 移除收益不足的复杂缓存/并行层；
- 重新执行L6，不得以放宽数值阈值换取通过。

## L6 worker数决策

L5 的历史请求默认仍登记为：

```text
representation_workers=2
outer_fold_workers=2
BLAS/OMP threads per worker=1
```

本次 L6 bounded synthetic total technical probe 中位耗时下降低于20%，因此按上一节规则移除收益不足的复杂缓存/并行层。当前 formal 的有效设置唯一为：

```text
representation_workers=1
outer_fold_workers=1
BLAS/OMP threads per worker=1
complex_cache_and_parallel_enabled=false
```

配置中的 `historical_requested_outer_fold_workers=2` 仅保留请求历史；formal 只能使用上述 effective serial setting。L4 `FoldRepresentationCache`、L5 `ProcessPoolExecutor` 及 provider 的多层 SLIC/representation/feature cache 保留用于历史测试或非formal探针，formal current-code path 不初始化、不调用。

只有同时满足以下条件才允许提高到4：

- 4-worker结果与1-worker等价；
- 峰值内存不超过可用物理内存的70%；
- 无持续交换/分页；
- 磁盘未成为主要瓶颈；
- 4-worker相对2-worker有明确稳定收益。

L6输出必须把最终worker设置写入脱敏审计，formal不得临时更改。

## L6输出

```text
prognosis_analysis/W08_local_L6_integration_audit.md
prognosis_analysis/W08_local_L6_integration.json
```

## L6验收条件

- 完整回归测试通过；
- 数值等价性通过；
- 本地执行参数唯一确定；
- 无B访问、正式预测或性能；
- Reviewer接受集成代码供P5/G3R使用。

# 九、L7——最终代码P5/G3R技术预检

## L7目标

使用L6接受的最终代码和本地执行参数，重新建立current-code 50-fold technical-only证据。

## L7执行要求

1. 在锁定`t2_radiomics`环境运行版本核验。
2. 运行完整测试发现集及W05/W08/R6相关targeted tests。
3. 运行compile检查。
4. 使用最终`n_init=100`执行50-fold technical-only preflight。
5. 必须保持：
   - 50/50 folds；
   - 17个固定技术run定义；
   - 850/850聚合技术记录；
   - required runs全部estimable；
   - paired populations一致；
   - inner 5-fold feasibility PASS；
   - `minimumROISize=10`；
   - B访问四项为`false`。
6. 不得调用Cox正式拟合，不得生成risk、prediction或performance。

## L7长任务规则

启动前依据L2/L6实测估算运行时间。启动后仅在预计时间十分之一节点检查一次；预计时间内不再轮询。超出预计时间超过`min(预计时间/10, 10分钟)`后再检查一次。完成后按产物核验，不以控制台缓冲为依据。

## L7输出

沿用项目现有P5/G3R aggregate evidence、audit和review机制，不新建竞争性的状态体系。病例级技术记录仍只留在本地output目录，可提交证据只包含聚合结果。

## L7验收条件

- 环境、测试和50-fold技术预检全部通过；
- current-code证据绑定的是最终优化实现；
- 没有正式W08输出；
- Reviewer给出可供L8使用的接受结论。

# 十、L8——current-code binding与formal release gate

## L8目标

按现有append-only证据机制完成最终代码绑定，并在干净工作树上重新执行formal W08 release gate。

## L8动作

1. 核对L7证据对应当前代码commit。
2. 按现有successor/finalization模式完成G3R evidence binding。
3. 确认历史失败记录未被改写。
4. 确认中断attempt已显式协调。
5. 确认不存在未跟踪脚本、测试或临时文件。
6. 确认正式输出与`model_freeze_lock.json`不存在。
7. 确认B访问四项为`false`。
8. 执行formal release gate。

## L8 PASS条件

- `clean_worktree=PASS`；
- current code commit匹配；
- current G3R certificate匹配；
- W05访问边界PASS；
- W08配置PASS；
- prior attempts reconciled；
- model freeze absent；
- B访问四项PASS；
- `formal_authorized=true`。

任一项失败均不得启动L9。

# 十一、L9——本地formal W08

## L9目标

在L8接受的同一commit、同一环境和同一worker设置下完成新的A-only formal W08。

## L9启动前核验

- HEAD与L8绑定commit一致；
- 工作树干净；
- `t2_radiomics`版本核验通过；
- 本地磁盘空间充分；
- 当前无其他W08进程；
- 无未协调staging attempt；
- worker和BLAS线程设置等于L6；
- B数据未挂载到执行入口；
- 输出根目录不存在正式结果冲突。

## L9运行方式

- 通过`tools/run_t2_radiomics.ps1`调用锁定环境；
- 由Windows计划任务或独立后台进程运行；
- 启动窗口使用隐藏模式；
- stdout和stderr写入本地attempt日志；
- 进程不得依附Codex、RDP或其他临时交互会话；
- 使用本地ASCII兼容路径访问SimpleITK文件；
- 只启动一个formal attempt。

## L9运行监测

启动前依据L6基准给出预计时间。监测严格遵守项目`AGENTS.md`：

1. 在预计时间十分之一节点检查一次：
   - 主进程和worker存活；
   - progress更新时间合理；
   - completed fold开始增加；
   - checkpoint原子落盘；
   - stdout/stderr无异常；
   - B访问四项为`false`。
2. 预计时间内不再监测。
3. 超出预计时间超过规定阈值后再检查一次并更新估计。
4. 完成后以正式产物核验。

## L9中断处理

- 外部会话断开但后台进程存活：不干预；
- 进程停止且checkpoint绑定全部一致：使用显式resume入口继续同一attempt；
- checkpoint绑定不一致或状态损坏：关闭为failed，新建attempt；
- 不得复制旧attempt中的模型结果进入新attempt；
- 不得为了恢复减少剩余fold或模型。

## L9完成条件

- 50/50 outer folds完成；
- 13个formal runs每fold完整；
- 650条fold结果；
- 全部所需held-out predictions存在；
- selection records完整；
- formal output manifest验证通过；
- attempt从staging一次性提升；
- `final_outputs_generated=true`；
- B访问四项为`false`；
- 未生成`model_freeze_lock.json`。

L9 Worker完成后停止，不解释AUC、C-index或模型优劣。

# 十二、L10——正式输出技术完整性复核并停止

## L10目标

独立核验formal W08是否完整、可追溯且未越过分析边界。本单元只审查技术完整性，不评价性能。

## L10复核项目

1. attempt ID、code commit、环境指纹和release gate一致。
2. 50个outer folds全部出现且无重复。
3. 13个run在每fold均完整，共650条fold结果。
4. prediction覆盖、training/validation hash和outer split一致。
5. 每fold centers、boundary、seed和`n_init=100`记录完整。
6. paired comparator具有相同人群和boundary。
7. selected alpha/lambda均来自冻结网格。
8. convergence/failure audit字段完整。
9. checkpoint归并顺序确定，正式manifest覆盖全部最终文件。
10. 不存在残留成功staging或未登记attempt。
11. B访问四项为`false`。
12. `model_freeze_lock.json`不存在。
13. Git中不含患者级输出、绝对路径或隐私信息。

## L10输出

```text
prognosis_analysis/W08_local_L10_formal_integrity_review.md
```

报告只包含聚合计数、绑定和技术结论，不包含患者标识、预测值或性能指标。

## L10结论分支

### accepted for downstream use

记录formal W08技术完整性已接受，下一理论阶段为W09，但本工作流在此停止，等待用户授权。

### accepted with non-blocking findings

记录不影响正式输出正确性、可复现性和下游使用的发现；本工作流仍停止，由用户决定是否进入W09。

### not accepted for downstream use

不得进入W09。根据缺陷类型返回相应单元，由新的整改Worker执行：

- 参数或绑定错误：返回L1或L8；
- 特征不一致：返回L3R/L4；
- solver不一致：返回L3C；
- 并行、checkpoint或归并错误：返回L5；
- formal执行不完整：关闭失败attempt后返回L9。

# 十三、统一分包任务合同

每个L0–L10 Worker任务包必须包含：

```text
工作单元ID：
唯一目标：
允许读取的输入：
已接受的上游commit/证据：
允许修改的文件：
允许写入的本地output目录：
必须生成的交付物：
必须运行的测试：
明确验收条件：
禁止操作：
失败时保留的最小证据：
停止位置：
```

统一约束：

- Worker只执行一个工作单元；
- 不执行后续单元；
- 不自审；
- 不再创建任何agent或会话；
- 不修改未授权文件；
- 不读取B；
- 不提交患者级数据；
- 长任务遵守单次监测规则；
- 完成后提供可观察文件、diff、测试和commit证据。

每个Reviewer任务包必须包含：

```text
被审工作单元ID：
工作单元合同：
待审commit或工作区：
实际交付物位置：
上游接受证据：
验收条件：
需要复跑的只读检查：
下游污染风险：
允许的三种结论：
```

Reviewer不得编辑代码、修复结果或执行下一单元。

# 十四、提交与合并规则

1. 每个Worker只提交本单元授权文件。
2. L3R和L3C使用隔离分支或worktree；不得同时修改同一共享文件。
3. 独立Reviewer未接受的commit不得合并到主执行分支。
4. remediation使用新的Worker和新的commit。
5. 合并后由下一单元重新运行与改动规模相称的测试。
6. 所有可提交报告先脱敏。
7. `prognosis_analysis/output/`、`habitat_analysis/output/`及患者级缓存不得暂存。
8. 推送前核对staged diff、敏感路径、大文件和远程状态。
9. 用户工作区中与本工作流无关的修改不得夹带。

# 十五、最终验收矩阵

| 单元 | 必须结果 | 未通过时停止点 |
|---|---|---|
| L0 | 中断attempt显式失败、现场可审计 | 不进入L1 |
| L1 | 全入口`n_init=100`、progress安全 | 不进入L2 |
| L2 | 无性能热点基准完整 | 不进入L3R/L3C |
| L3R | 59项PyRadiomics完全一致 | 不进入L4 |
| L3C | Cox核心和选择结果等价 | 不进入L4 |
| L4 | 50-fold表示与直接provider一致 | 不进入L5 |
| L5 | 串行/并行/恢复一致 | 不进入L6 |
| L6 | 集成等价且本地参数确定 | 不进入L7 |
| L7 | current-code 50-fold P5/G3R通过 | 不进入L8 |
| L8 | binding及release gate PASS | 不进入L9 |
| L9 | formal W08完整提升 | 不进入L10之外阶段 |
| L10 | 独立技术完整性接受 | 停止，等待W09授权 |

# 十六、工作流完成定义

只有同时满足以下条件，本地整改与formal W08执行才算完成：

- formal生产入口统一使用冻结`n_init=100`；
- 优化没有改变科学参数、候选池、模型选择或数值语义；
- 本地并行和恢复机制通过等价性测试；
- final-code P5/G3R和release gate重新通过；
- 50-fold formal W08产生完整、事务性提升的正式输出；
- 独立Reviewer接受技术完整性；
- B访问四项保持`false`；
- `model_freeze_lock.json`仍不存在；
- Git中不存在患者级或可识别数据；
- 工作流在W09之前停止。
