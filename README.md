# T2WI-HS-radiomics-analysis

直肠癌治疗前 T2WI 生境分析项目，包含影像预处理、影像组学、固定 full-A habitat、预后建模及方法文档。

## 当前主线

```text
MRI/radiomics freeze
→ full-A habitat freeze
→ candidate freeze
→ Primary v2 fixed 5-fold A validation
→ full-A model freeze
→ frozen B external validation
→ final interpretation
```

当前方法为 **Primary Prognostic Analysis v2**。Formal W08 v1 已归档并标记为 `archived / superseded`，旧 W08/G3/R5/R6 记录不再是 active next step。FT validation v1 已归档，是 Primary v2 的历史开发来源，不是当前活动分析树。

## Primary v2 固定合同

- 固定 full-A 3D SLIC、cross-case K-means `K=2`，不在 CV fold 或 B 中重拟合 habitat centers、boundary 或 habitat radiomics。
- `R_low=49`、`R_high=10`、`W_Original=107`；保留全部 `M0–M5`。
- LASSO-Cox `alpha=1`；A 内部验证为固定 `repeat-1`、single 5-fold outer validation。
- 临床/影像预处理、特征选择和 lambda 选择均遵守 training-only 规则；B 只执行 frozen prediction。
- Primary v2 是 post-FT protocol transition：FT03 A 与 FT06 B 结果在方法提升/登记决定时已可见，不能追溯表述为 B 结果前的预先指定；B prediction 在 B evaluation 前已冻结。

## 数据边界

GitHub/Codex 仓库只保存代码、配置、方法文档和不含原始影像号的项目状态信息。以下材料保留在本地受控环境，不进入仓库：

- 原始影像、ROI 和 Slicer 工程；
- 临床、病理和预后原始表；
- 患者级特征、预测、模型状态和分析输出；
- 含原始影像号的清单、日志、报告或历史结果。

原始影像号—匿名号映射表仅保存在本地 `local_private/image_id_mapping.csv`。归档目录中的报告和 JSON 仅限安全的协议、审查及聚合证据。

## 目录

- `feature_extract/scripts/`：清单、预处理、归一化、QC 和特征提取脚本。
- `feature_extract/configs/`：PyRadiomics 及技术敏感性参数。
- `habitat_analysis/`：固定 habitat 方法、配置、队列定义和冻结规则。
- `prognosis_analysis/primary/`：Primary v2 当前协议、验证、冻结和外部验证代码。
- `manuscript/methodology_defense/`：方法学证据归档。
- `archive/formal_nested_cv_v1/`：Formal W08 v1 历史协议与审查归档。
- `archive/ft_validation_v1/`：FT validation v1 安全聚合证据归档。
- `archive/protocol_history/`：更早的协议历史。

当前科学主协议为根目录的《T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md》；当前 Primary v2 合同见《T2WI-HS-radiomics-analysis Primary v2 正式分析方案书与串行执行工作流.md》及 `prognosis_analysis/primary/protocol.json`。归档内容不作为当前分析输入。

## 环境与检查

本地影像组学环境为 conda `t2_radiomics`，固定版本见 `environment.yml`。若 PowerShell 无法直接识别 `conda`，使用 `tools/run_t2_radiomics.ps1`。

```powershell
.\tools\run_t2_radiomics.ps1 -PythonArguments @('-m','compileall','-q','feature_extract/scripts','prognosis_analysis/primary')
.\tools\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','discover','-s','tests','-p','test_*.py')
```

真实影像分析及患者级结果只在本地受控环境执行；提交前检查待提交文件，确认不含患者隐私、绝对路径、凭据或大文件。
