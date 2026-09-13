# `n_init`快速一致性校验归档

本目录保存已停止的`n_init=10`与`n_init=100`快速一致性校验材料，仅用于方法和代码追溯。

归档内容：

- `T2WI-HS-radiomics-analysis n_init快速等价性验证工作流.md`：原验证工作流；
- `validate_kmeans_n_init_equivalence.py`：原独立验证脚本；
- `test_kmeans_n_init_equivalence.py`：原回归测试。

该校验由人工停止，未形成可用于正式判断的结论，也未保留结论性输出。当前本地W08整改直接以冻结技术方案的`n_init=100`为目标，执行入口为项目根目录的《T2WI-HS-radiomics-analysis W08本地计算优化整改与分包执行工作流.md》。本目录文件不得被当前测试发现、生产脚本导入或作为正式分析输入。
