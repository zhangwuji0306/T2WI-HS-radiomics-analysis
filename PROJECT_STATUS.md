# Project status

## Goal

完成直肠癌治疗前 T2WI 生境分析，形成可追溯、可复现且符合数据隔离要求的影像组学分析流程，并评估其与预后终点的关系。

## Current state

- 项目代码分为 `feature_extract`、`habitat_analysis` 和 `prognosis_analysis` 三个工作区。
- 影像预处理、设备映射、高信号筛选审计及整块肿瘤候选特征 QC 已形成现有上游资产。
- 当前主方法候选为三维 SLIC 4 mm 加跨病例 K-means K=2。
- A 集和 B 集的队列定义、数据隔离规则及主参数已记录在项目方法文档中。
- 当前阶段尚未进入 `habitat_maps_A` 及其下游生境结果阶段。
- GitHub/Codex 仓库采用代码和文档边界；原始影像、临床数据、患者级结果和原始影像号均保留在本地。

## In progress

- 维护代码、配置和方法文档的 GitHub 版本。
- 使用本地匿名化映射表管理影像号与匿名号之间的对应关系。
- 准备可在 Codex 云端复现依赖安装和代码检查的环境；真实患者数据分析仍在本地受控环境执行。

## Next task

在本地受控环境中，对 A 集全部 393 例执行无结局技术干跑：

1. 按冻结参数生成候选生境结果；
2. 记录空生境、算法失败、未分配肿瘤体素及几何/标签错误；
3. 按病例合并技术失败并计算联合失败率；
4. 失败率低于 5% 时冻结成功/排除病例清单，达到或超过 5% 时停止并提交失败清单；
5. 在 A 集参数、特征和模型全部冻结前，不读取或使用 B 集 107 例。

## Important decisions

- GitHub/Codex 仓库不保存原始影像、ROI、Slicer 工程、临床/病理/预后表及患者级派生结果。
- 任何进入仓库的影像相关资料必须使用匿名影像号；原始影像号—匿名号映射仅保存在本地 `local_private/image_id_mapping.csv`。
- 技术干跑不得读取结局或临床变量。
- 生境失败不填 0、不作普通缺失插补、不切换为病例内 K-means，也不根据结局决定排除。
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
