# Post-V2 693例无准入门槛 DFS 敏感性分析

`sensitivity_693.py` 按任务书串行执行 T1→T2→T3→T4：

- T1：保留 Primary v2 A393 与 FT05A B163 冻结资产，仅为 A 扩展的 137 例生成固定中心/边界下的 R1 生境图与生境特征缓存。
- T2：构建 A530 建模特征、保留 A393 的既有 repeat-1 折叠，并以 `seed=12345`、`DFS_event` 分层为新增病例确定性补充分折。
- T3：使用 Primary v2 相同的 M0–M5、训练集内预处理、内层五折 lambda 选择和 `alpha=1`；A 全部验证完成后冻结 full-A 模型，再对 B163 做 frozen prediction-only 评价。
- T4：报告 Primary v2 与 693 例敏感性结果的方向、幅度、覆盖度和 B 外部稳健性；按任务书第十、十一节在共同可分析人群中完成12组模型比较，并为逐指标差异报告患者级配对 bootstrap percentile 95% CI。

在项目根目录、`t2_radiomics` 环境中运行：

```powershell
& .\tools\run_t2_radiomics.ps1 -PythonArguments @(
  'prognosis_analysis/post_v2/sensitivity_693.py', '--all')
```

若 T1–T3 已完成，仅补跑完整模型比较：

```powershell
& .\tools\run_t2_radiomics.ps1 -PythonArguments @(
  'prognosis_analysis/post_v2/sensitivity_693.py', '--compare')
```

患者级输入、缓存、特征、预测和分析输出均写入本地忽略目录：
`habitat_analysis/output/sensitivity_693_cache/` 与
`prognosis_analysis/output/sensitivity_693/`。Primary v2 目录不作为输出目标。
