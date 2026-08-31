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
- 已完成修正后18例M1/M2比较、A=393校正M1、结构状态、技术因素效应量及严格A=137核验；校正后A=393硬技术失败0例，结构性单生境25例。bootstrap按`smoke=20`、`preflight=200`、`formal=1000`分目录和模式管理；preflight 200次已完成并判定为`CLEAR PASS`，formal 1000次已完成并通过T02稳定性门禁（`FORMAL PASS`、`formal_eligible=1`），结局盲态保持。
- 已完成结局盲态0.1%高信号阈值技术合理性审计及补充技术混杂分解：A筛选母队列530例，重算A393与现有清单对称差为0，A137仍为A393真子集；预设阈值扫描保持单调嵌套，A393 preflight已按区间完整连接。近0.10–<0.25%区间的post-SLIC高信号保留召回率中位数为0；补充模型显示加入原始序列名没有稳定的交叉验证增益，但肿瘤体积依赖仍存在，综合判断为`NEUTRAL_WITH_TECHNICAL_CAUTION`。主阈值仍保持0.1%，未读取结局或B集，未执行阈值优化。
- GitHub/Codex 仓库采用代码和文档边界；原始影像、临床数据、患者级结果和原始影像号均保留在本地。

## In progress

- 当前执行协议为《T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md》及《三十二、具体执行工作流：从formal PASS至A-only model freeze.md》。
- 旧冻结前修复任务书和方法学修订报告已转入`archive/protocol_history/`，仅作为决策历史保存。
- 方法学证据存放于`manuscript/methodology_defense/`；患者级技术输出仍仅保留在本地。

## Next task

当前进入W01 technical freeze：完成第一阶段`freeze_lock.json`后，按W02–W05冻结生境特异性组学、建模协议及A-only访问边界，再首次读取A集DFS。第一把锁只解锁A集预设临床变量与DFS；完成A-only nested validation、全A最终拟合并生成第二阶段`model_freeze_lock.json`后，才允许首次读取B集进行一次性外部验证。

## Important decisions

- GitHub/Codex 仓库不保存原始影像、ROI、Slicer 工程、临床/病理/预后表及患者级派生结果。
- 任何进入仓库的影像相关资料必须使用匿名影像号；原始影像号—匿名号映射仅保存在本地 `local_private/image_id_mapping.csv`。
- 技术干跑不得读取结局或临床变量。
- 硬技术失败不填补；结构性单生境保留，主低维描述符按结构零规则生成，表型内纹理在相应表型不存在时保持未定义；不切换主方法，也不根据结局决定排除。
- 第一阶段技术锁只允许A outcome读取，不允许B访问；B必须保持不可见直至第二阶段最终模型锁生成，之后仅用于一次验证。
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
