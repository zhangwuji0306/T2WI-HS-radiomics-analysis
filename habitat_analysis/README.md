# 生境分析工作区

本目录承载当前直肠癌 T2WI 生境分析。正式方法、停止规则和统计路径以项目根目录的《生境分析方案与工作流.md》为准；队列规则见`cohort_definition.md`，机器可读主参数见`configs/main_cross_case_kmeans_k2_4mm.json`。

## 当前输入

- 图像清单与设备信息：`../feature_extract/output/manifest.csv`、`../feature_extract/output/scanner_map.csv`
- 肌肉归一化主预处理图像：`../feature_extract/output/preprocessed/`
- 高信号筛选审计：`output/high_signal_eligibility_audit/`
- 0.1%阈值技术合理性审计：`output/high_signal_threshold_audit/`
- 技术宽松主分析集与严格敏感性集：`output/technical_cohort_manifest/`
- 临床、影像、病理及预后原始表：`../prognosis_analysis/data/`
- H5 整块肿瘤候选：`../feature_extract/output/features_v2/`及`../prognosis_analysis/output/qc/stage6_v2/`

## 执行边界

当前主方法为三维 SLIC 4 mm 加全部有效超体素、每例总权重固定为1的跨病例 K-means K=2；在`[1,1,2] mm`图像上使用`[4,4,2]`体素超网格。空生境记录为`single-H-low`、`single-H-high`或`dual-habitat`结构状态，不计入硬技术失败；硬技术失败率＜5%时记录并剔除，达到或超过5%时停止。技术队列由影像清单、设备映射和高信号筛选审计独立生成。bootstrap固定为`smoke=20`、`preflight=200`、`formal=1000`并分目录保存；A集preflight 200次已判定为`CLEAR PASS`，但smoke/preflight不能解锁冻结，只有完整formal=1000及全部门禁通过后才能生成第一阶段`freeze_lock.json`。该锁只允许A集结局分析；B=107必须继续保持不可见，直至`prognosis_analysis/model_freeze_lock.json`生成后才允许一次性验证。

`scripts/`仅存放当前技术冻结脚本；`output/bootstrap_stability_A_post_slic_fix/formal/`为下一项正式分析目录；正式maps/features通过staging验证后原子晋升。参数冻结及执行状态见`analysis_freeze.md`，完整后续顺序见根目录当前执行任务书。
