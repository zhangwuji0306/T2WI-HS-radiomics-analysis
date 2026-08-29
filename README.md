# T2WI-HS-radiomics-analysis

直肠癌治疗前 T2WI 生境分析项目。项目包含影像预处理、影像组学特征提取、生境分析和预后分析的代码、参数及方法文档。

## 数据边界

GitHub/Codex 仓库只保存代码、配置、方法文档和不含原始影像号的项目状态信息。

以下内容保留在本地受控环境，不进入仓库：

- 原始影像、ROI 和 Slicer 工程文件；
- 临床、病理和预后原始表；
- 患者级特征、模型数据集和分析输出；
- 含原始影像号的清单、日志、报告或历史结果。

需要共享的清单或结果必须先将影像号替换为匿名号。原始影像号—匿名号映射表保存在本地 `local_private/image_id_mapping.csv`，不进入 GitHub。

## 目录

- `feature_extract/scripts/`：影像清单、预处理、归一化、QC 和特征提取脚本。
- `feature_extract/configs/`：PyRadiomics 及技术敏感性参数。
- `habitat_analysis/scripts/`：当前生境分析脚本。
- `habitat_analysis/configs/`：主方法参数和终点定义。
- `habitat_analysis/` 下的 Markdown 文件：队列定义、分析冻结和执行边界。
- `prognosis_analysis/scripts/`：队列建模表和候选特征 QC 脚本。
- `archive/`：历史探索材料，仅保存在本地。

## 当前主线

主方法候选为三维 SLIC 4 mm 加跨病例 K-means，聚类数为 K=2。

分析顺序为：

```text
feasibility_A
→ habitat_maps_A
→ habitat_features_A
→ modeling
→ quick_check
→ nested_cv
→ final_model
→ validation_B
```

A 集为技术干跑和模型开发队列，B 集在 A 集参数、特征和模型冻结前保持不可见。技术干跑不得读取结局或临床变量；失败病例按预先冻结的规则处理。

## 环境

本地分析环境为 conda 环境 `t2_radiomics`：

- Python 3.7.12
- NumPy 1.21.6
- pandas 1.3.5
- SciPy 1.7.3
- scikit-learn 1.0.2
- PyRadiomics 3.0.1
- SimpleITK 2.2.1

完整依赖见 `environment.yml`。Codex 云端环境使用 Python 3.7，并通过 `setup.sh` 安装 `requirements-cloud.txt`。云端任务只针对代码、配置和不含患者级数据的文档；真实影像分析在本地受控环境执行。

## 本地使用

```powershell
conda env update -n t2_radiomics -f environment.yml
conda run -n t2_radiomics --no-capture-output python <script>
```

涉及 SimpleITK 的本地脚本需要使用本机配置的 ASCII junction。不要将本地绝对路径写入清单、报告或仓库文档。

## 影像号匿名化

本地生成或更新映射表：

```powershell
python tools/build_image_id_mapping.py
```

该命令只更新本地 `local_private/image_id_mapping.csv`，不修改原始影像或原始数据。提交前应检查所有待提交文件，确认不含原始影像号、患者级数据、绝对路径和敏感信息。

## 文档入口

- [项目说明](项目说明.md)
- [组学分析方案](组学分析方案.md)
- [生境分析方案与工作流](生境分析方案与工作流.md)
- [分析冻结状态](habitat_analysis/analysis_freeze.md)
- [项目状态](PROJECT_STATUS.md)
