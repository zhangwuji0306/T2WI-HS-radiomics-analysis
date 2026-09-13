# 生境分析工作区

本目录承载当前直肠癌 T2WI 生境分析。固定方法和队列定义以本目录的 `configs/`、`cohort_definition.md`、`freeze_lock.json`、`freeze_integrity_addendum.json` 和 `feature_dictionary.md` 为准；Primary v2 预后合同见 `../prognosis_analysis/primary/README.md` 和 `../prognosis_analysis/primary/protocol.json`。

## 当前输入

- 图像清单与设备信息：`../feature_extract/output/manifest.csv`、`../feature_extract/output/scanner_map.csv`
- 肌肉归一化主预处理图像：`../feature_extract/output/preprocessed/`
- 高信号筛选审计：`output/high_signal_eligibility_audit/`
- 0.1%阈值技术合理性审计：`output/high_signal_threshold_audit/`
- 技术宽松主分析集与严格敏感性集：`output/technical_cohort_manifest/`
- 临床、影像、病理及预后原始表：`../prognosis_analysis/data/`
- H5 整块肿瘤候选：`../feature_extract/output/features_v2/`及`../prognosis_analysis/output/qc/stage6_v2/`

## 执行边界

当前主方法为三维 SLIC 4 mm 加全部有效超体素、每例总权重固定为1的跨病例 K-means K=2；在`[1,1,2] mm`图像上使用`[4,4,2]`体素超网格。空生境记录为`single-H-low`、`single-H-high`或`dual-habitat`结构状态，不计入硬技术失败；硬技术失败率＜5%时记录并剔除，达到或超过5%时停止。技术队列由影像清单、设备映射和高信号筛选审计独立生成。bootstrap固定为`smoke=20`、`preflight=200`、`formal=1000`并分目录保存；正式 `freeze_lock.json`、fixed full-A habitat maps、manifest 和派生缓存均属于当前 active 分析资产。

`scripts/`仅存放当前技术冻结脚本；`output/bootstrap_stability_A_post_slic_fix/formal/`保存正式 bootstrap 证据。正式 maps/features 通过 staging 验证后原子晋升。下一阶段顺序为示例分析、次要结局分析和敏感性分析；当前 active 缓存不得移动到 `archive/`。
