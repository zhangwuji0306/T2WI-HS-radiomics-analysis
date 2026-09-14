# Post-V2 693例 DFS 敏感性分析结果

本目录保存全队列无准入门槛敏感性分析的脱敏、非患者级结果：阶段摘要、模型效能、覆盖度、模型比较和冻结模型元数据。

结果范围为 A=530、B=163，共693例。A侧使用扩展队列验证并完成全A冻结；B侧仅使用A侧冻结模型进行预测后评价，未在B侧调参、重拟合或筛选特征。

本目录不包含病例清单、患者级特征、个体预测值、影像或ROI、可关联个体的哈希、本机绝对路径及临床原始表。

## 文件说明

- `T1_summary.json`、`T2_summary.json`、`T3_summary.json`、`T4_summary.json`：各阶段完成状态与队列级核验摘要。
- `T3_A_validation_metrics.csv`、`T3_B_validation_metrics.csv`：A、B两侧14个模型的聚合效能指标。
- `T3_A_paired_comparisons.csv`：配对比较的共同样本数及折叠一致性，不含个体标识哈希。
- `T3_model_freeze.json`：全A冻结模型的非患者级元数据。
- `T4_coverage.csv`：模型覆盖度和事件覆盖度。
- `T4_primary_vs_sensitivity_comparison.csv`：Primary v2与693例敏感性分析的模型效能比较。
- `T4_common_population_comparisons.csv`、`T4_common_population_eligibility.csv`：按任务书第十、十一节完成的12组共同可分析人群模型比较及其覆盖度。
- `T4_model_comparison_summary.md`：12组模型比较的A/B侧效能差异摘要。
- `T4_summary.md`、`sensitivity_693_workflow_summary.json`：结果解读和完整工作流摘要。
