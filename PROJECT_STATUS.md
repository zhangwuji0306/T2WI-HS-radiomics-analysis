# Project status

## Goal

完成直肠癌治疗前 T2WI 生境分析，形成可追溯、可复现且符合数据隔离要求的影像组学分析流程，并评估其与预后终点的关系。

## Current state

- 项目代码分为 `feature_extract`、`habitat_analysis` 和 `prognosis_analysis` 三个工作区。
- 影像预处理、设备映射、高信号筛选审计及整块肿瘤候选特征 QC 已形成现有上游资产。
- 预处理已采用显式 normalization 状态、完整有效配置 SHA-256 印章及输入/版本 provenance；R1/R2 的肌肉标签规则已分离。
- Original 与 Wavelet/LoG 特征提取已采用原子最终写入；过滤特征通过 `completion_manifest.csv` 判断是否完成。
- 已加入 11 个合成数据回归测试，覆盖标签解析、归一化隔离、强制覆盖、断点续跑、流水线印章和倾斜 FOV。
- 当前主方法候选为三维 SLIC 4 mm 加跨病例 K-means K=2。
- A 集和 B 集的队列定义、数据隔离规则及主参数已记录在项目方法文档中。
- 当前已完成A集无结局M1技术运行；结构性单生境不计入硬技术失败。尚未解除结局盲态，仍需完成结构诊断、local-global诊断、bootstrap、技术因素核验、A=137敏感性及主特征冻结。
- GitHub/Codex 仓库采用代码和文档边界；原始影像、临床数据、患者级结果和原始影像号均保留在本地。

## In progress

- 维护代码、配置和方法文档的 GitHub 版本。
- 使用本地匿名化映射表管理影像号与匿名号之间的对应关系。
- 在本地完成代码检查后重新生成上游清单、muscle 预处理、z-score 敏感性预处理及对应 QC；真实患者数据分析仍在本地受控环境执行。

## Next task

在结局盲态下完成结构状态、local-global机制、患者层面bootstrap、技术因素和严格A=137敏感性核验；满足冻结条件后再纳入A集预设临床变量与DFS。B集在全A参数、特征和模型冻结前保持不可见。

## Important decisions

- GitHub/Codex 仓库不保存原始影像、ROI、Slicer 工程、临床/病理/预后表及患者级派生结果。
- 任何进入仓库的影像相关资料必须使用匿名影像号；原始影像号—匿名号映射仅保存在本地 `local_private/image_id_mapping.csv`。
- 技术干跑不得读取结局或临床变量。
- 硬技术失败不填补；结构性单生境保留，主低维描述符按结构零规则生成，表型内纹理在相应表型不存在时保持未定义；不切换主方法，也不根据结局决定排除。
- B 集在全 A 集参数、特征和模型冻结前保持不可见，冻结后仅用于一次验证。
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
