# Project status

## Goal

完成直肠癌治疗前 T2WI 生境分析，形成可追溯、可复现且符合数据隔离要求的影像组学分析流程，并评估其与预后终点的关系。

## Current state

- 项目代码分为 `feature_extract`、`habitat_analysis` 和 `prognosis_analysis` 三个工作区。
- 影像预处理、设备映射、高信号筛选审计及整块肿瘤候选特征 QC 已形成现有上游资产。
- 预处理已采用显式 normalization 状态、完整有效配置 SHA-256 印章及输入/版本 provenance；R1/R2 的肌肉标签规则已分离。
- Original 与 Wavelet/LoG 特征提取已采用原子最终写入；过滤特征通过 `completion_manifest.csv` 判断是否完成。
- 已加入冻结前代码回归测试，覆盖标签解析、归一化隔离、强制覆盖、断点续跑、流水线印章、倾斜 FOV、SLIC物理尺度换算、A/B隔离、患者等权bootstrap、冻结锁和技术队列审计。
- 当前主方法为三维 SLIC 4 mm 加全部有效超体素、每例总权重固定为1的跨病例 K-means K=2；4 mm在`[1,1,2] mm`图像上使用`[4,4,2]`体素超网格。
- A 集和 B 集的队列定义、数据隔离规则及主参数已记录在项目方法文档中。
- 已完成修正后18例M1/M2比较、A=393校正M1、结构状态、技术因素效应量及严格A=137核验；校正后A=393硬技术失败0例，结构性单生境25例。bootstrap按`smoke=20`、`preflight=200`、`formal=1000`分目录和模式管理；preflight 200次已完成并判定为`CLEAR PASS`，formal患者层面bootstrap已完成1000/1000、成功1000/1000并通过全部稳定性门禁，正式判定为`FORMAL PASS`、`formal_eligible=1`。A393身份审计对称差为0，A137仍为A393真子集；结局盲态保持。
- 已完成结局盲态0.1%高信号阈值技术合理性审计及补充技术混杂分解：A筛选母队列530例，重算A393与现有清单对称差为0，A137仍为A393真子集；预设阈值扫描保持单调嵌套，A393 preflight已按区间完整连接。近0.10–<0.25%区间的post-SLIC高信号保留召回率中位数为0；补充模型显示加入原始序列名没有稳定的交叉验证增益，但肿瘤体积依赖仍存在，综合判断为`NEUTRAL_WITH_TECHNICAL_CAUTION`。主阈值仍保持0.1%，未读取结局或B集，未执行阈值优化。
- W02 H-low/H-high Original radiomics 工作流已在 outcome-blind 条件下完成 A393 全量建立：固定使用 W01 肌肉归一化、`[1,1,2] mm`、无 N4 图像、肿瘤 ROI 与冻结 SLIC labels；PyRadiomics 固定 `Original`、`binWidth=0.248808`、不内部归一化/重采样，完整覆盖 first-order、shape、GLCM、GLRLM、GLSZM、GLDM 和 NGTDM。A393 中 dual-habitat 368例、single-H-low 24例、single-H-high 1例；R_low 可提取391例、R_high可提取356例，结构性未定义分别为1例和24例，技术失败分别为1例和13例。未读取临床、病理、预后或B集数据，未执行ICC、候选筛选或建模。
- W03 habitat-specific radiomics 结局盲态技术 QC 与候选池已冻结：A393 中 R1 技术覆盖393例，A内R2覆盖17例；R_low 有效 pair 为17，R_high 有效 pair 为15，107个特征在两读者对应存在病例中的 finite-rate 均达到`>=95%`。严格按 `ICC(2,1)>0.75` 且 `n_valid_pairs>=10`，R_low 正式 prediction candidate 49个，R_high 10个；候选哈希分别为`a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`和`a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`。全流程 outcome-blind，未读取临床、病理、结局或B集数据。
- W04 建模协议已在首次读取 DFS 前冻结：固定 M0–M5 及比较层级、DFS 3年/5年主时间点、A-only 人群资格、结构性缺失与可用性规则、5折×10重复嵌套交叉验证、事件分层、training-only 预处理、Elastic-Net Cox alpha 网格与内层 CV lambda 规则；`prognosis_analysis/modeling_protocol.json` 的 SHA-256 为`32d34b4b24af76b59b62f2df2cd4f04a4b7681e41da2eaee4e655d17dd9a04ce`。冻结时未读取 DFS/OS/CSS 或任何 B 数据，`B_unlock=false`，`model_freeze_lock.json` 尚未生成。
- W05 A-only 数据访问边界已完成：正式入口为 `prognosis_analysis/scripts/build_model_dataset_a.py --split A`；technical A、A clinical/outcomes、B validation 分别使用显式 reader，A outcome 受第一把锁保护，B 仅接受 `model_freeze_lock.json` 授权。A 模式先读取 A393/A137 technical IDs，再按 ID 白名单读取临床/结局和原始 feature，并只生成 A 产物；legacy builder 已 fail closed。W05 合成数据与回归门禁通过，尚未生成 `model_freeze_lock.json`，未读取真实 DFS 或 B 数据。
- GitHub/Codex 仓库采用代码和文档边界；原始影像、临床数据、患者级结果和原始影像号均保留在本地。

## In progress

- 当前执行协议为《T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md》及《三十二、具体执行工作流：从formal PASS至A-only model freeze.md》。
- 旧冻结前修复任务书和方法学修订报告已转入`archive/protocol_history/`，仅作为决策历史保存。
- 方法学证据存放于`manuscript/methodology_defense/`；W02/W03 患者级特征、诊断、可用性与候选QC输出保存在本地 `prognosis_analysis/output/` 对应目录，仓库仅保留可复用脚本、固定配置、测试及协议文档。

## Next task

当前已完成 W05 A-only 数据访问边界及相关回归门禁。下一阶段执行 W06 A 集 endpoint QC 与 A-only 建模；完成 A-only nested validation、全 A 最终拟合并生成第二阶段 `model_freeze_lock.json` 后，才允许首次读取 B 集进行一次性外部验证。

## Important decisions

- GitHub/Codex 仓库不保存原始影像、ROI、Slicer 工程、临床/病理/预后表及患者级派生结果。
- 任何进入仓库的影像相关资料必须使用匿名影像号；原始影像号—匿名号映射仅保存在本地 `local_private/image_id_mapping.csv`。
- 技术干跑不得读取结局或临床变量。
- 硬技术失败不填补；结构性单生境保留，主低维描述符按结构零规则生成，表型内纹理在相应表型不存在时保持未定义；不切换主方法，也不根据结局决定排除。
- 第一阶段技术锁只允许A outcome读取，不允许B访问；B必须保持不可见直至第二阶段最终模型锁生成，之后仅用于一次验证。
- W05 访问入口固定为 `read_technical_A`、`read_A_outcomes`、`read_B_validation`；A/B 队列归属统一由 `resolve_cohort_membership()` 判定，legacy `b_validation_unlock.json` 不具有独立授权能力。
- 技术队列清单只由影像清单、设备映射和高信号筛选审计生成；不得从预后或临床表生成A集技术候选。
- bootstrap模式固定为`smoke=20`、`preflight=200`、`formal=1000`，分别写入`habitat_analysis/output/bootstrap_stability_A_post_slic_fix/{smoke,preflight,formal}/`；只有完整formal=1000可进入冻结门禁。
- B集相关特征、QC和模型步骤必须同时通过第一阶段`freeze_lock.json`和第二阶段`model_freeze_lock.json`校验。
- 预计超过 40 分钟的任务必须先进行小样本估时，并遵守 `AGENTS.md` 中的单次检查和结果核验规则。

## Verification

### Local environment

```powershell
conda run -n t2_radiomics --no-capture-output python --version
conda run -n t2_radiomics --no-capture-output python tools/build_image_id_mapping.py
```

### Codex cloud environment

在 Codex 环境设置中固定 Python 3.7，并将 setup script 设置为：

```bash
bash setup.sh
```

云端验证仅覆盖依赖安装、脚本帮助信息和不含患者级数据的静态检查，不执行真实影像或临床数据分析。

### Code regression checks

```powershell
conda run -n t2_radiomics --no-capture-output python -m compileall -q feature_extract/scripts tests
conda run -n t2_radiomics --no-capture-output python -m unittest discover -s tests -p "test_*.py"
```
