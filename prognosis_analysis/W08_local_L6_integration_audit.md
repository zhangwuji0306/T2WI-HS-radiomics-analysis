# W08 L6 本地集成等价性与执行参数审计

## 结论

当前代码的 L6 技术探针已完成。正确性矩阵由当前代码 synthetic probe 与锁定 unittest 证据组成；真实 A 探针覆盖 outcome-blind provider、K-means boundary、代表性 mask，以及由 `provider.transform` 生成的 G/R-low/R-high 表示，不是模型性能或正式 W08。

bounded synthetic technical probe 的三次同机重复中，集成总 probe 中位耗时相对 baseline 下降 5.65%；该结果低于 20% 阈值，因此复杂缓存/并行层不启用于正式执行。历史请求参数为 `representation_workers=2`、`outer_fold_workers=2`；当前 formal effective 设置唯一为 `representation_workers=1`、`outer_fold_workers=1`、每 worker 数值线程为 1，且不初始化复杂缓存或进程池。

## 环境与冻结绑定

- Conda 环境：`t2_radiomics`；实际解释器：`python.exe in conda environment t2_radiomics`。
- Python 3.7.12；NumPy 1.21.6；pandas 1.3.5；scikit-learn 1.0.2；PyRadiomics v3.0.1；SimpleITK 2.2.1。
- 所有 Python、测试、compile 和 probe 均通过 `tools/run_t2_radiomics.ps1 -PythonArguments` 调用。
- K-means：K=2、k-means++、`n_init=100`、`max_iter=300`、`tol=1e-4`；50 个外层 fold、5 个 inner fold；4 个 alpha、每个 alpha 100 个 lambda；Elastic-Net `max_iter=3000`、`tolerance=1e-7`；`minimumROISize=10`。

## 正确性矩阵

| 检查项 | 结果 | 证据来源 | 证据类型 |
|---|---:|---|---|
| 50 个 K-means centers/boundaries | PASS | `w08_local_l6_probe.py::_synthetic_boundary` | synthetic |
| fold seed | PASS | `w08_local_l6_probe.py::_synthetic_boundary` | synthetic |
| 代表性 low/high mask | PASS | `w08_local_l6_probe.py::_mask_pair` | synthetic |
| G 特征 | PASS | `w08_local_l6_probe.py::_g_features` | synthetic |
| R-low 49 项 | PASS | `w08_local_l6_probe.py::_feature_vector` | synthetic |
| R-high 10 项 | PASS | `w08_local_l6_probe.py::_feature_vector` | synthetic |
| P3B 状态 | PASS | `tests.test_w08_technical_preflight_a` | current-code unittest |
| fold-specific population | PASS | `tests.test_w08_technical_preflight_a` | current-code unittest |
| paired comparator 覆盖 | PASS | `tests.test_w08_technical_preflight_a` | current-code unittest |
| ModelPreprocessor 输出 | PASS | `w08_local_l6_probe.py::ModelPreprocessor` | synthetic |
| 100 点 lambda 顺序 | PASS | `tests.test_r6_5_validation` | current-code unittest |
| alpha/lambda 选择 | PASS | `w08_local_l6_probe.py::_select_candidate` | synthetic |
| coefficient/convergence/failure | PASS | `w08_local_l6_probe.py::CoxElasticNetModel` | synthetic |
| serial/parallel ordering | PASS | `tests.test_w08_l5_parallel_checkpoint` | current-code unittest |
| checkpoint/resume | PASS | `tests.test_w08_l5_parallel_checkpoint` | current-code unittest |
| B 访问边界 | PASS | `w08_local_l6_probe.py and w08_local_optimization_probe.py` | current-code source/safety |

50-fold synthetic K-means 检查保留每个 fold 的 seed、centers 和 boundary；真实 A fold 明细只保留脱敏技术聚合，不写入患者标识。

## 真实 A outcome-blind technical probe

- 命令：`tools\run_t2_radiomics.ps1 -PythonArguments @('prognosis_analysis/scripts/w08_local_l6_probe.py','--mode','real-a-technical','--real-a-folds','50')`。
- 输入范围：A technical metadata、A technical feature coverage、A R1 supervoxel summary、冻结 outer split；未读 `DFS_time`/`DFS_event`，未打开 B source。
- 结果：50/50 fold 完成；provider fit calls=50；provider transform calls=100（training/validation 各 1 次每 fold）；G=6、R-low=49、R-high=10 列的代表性表示均完成。这是 current-code provider/mask/representation evidence，不是 formal W08 model/performance evidence。
- 每个 fold 记录 seed、centers/boundary、代表性 low/high mask voxel counts、training population count 和代表性 transform 完成摘要；不记录患者级明细或 per-fold hash。formal training population 仅保留聚合 count。
- 旧 R6-6.5/G3R 记录中的 stale code/coordinate hash 保留为历史证据且不作为本次 L6 current-code 依据；本审计以 JSON `provenance_disposition.current_code_evidence_source` 为准。

## 性能比较（bounded synthetic）

该比较在同一机器、同一 `t2_radiomics`、同一 synthetic 输入和同一线程上分别重复 3 次。它使用 8 个 synthetic case、2 个 representation folds、5 个 candidate penalties、`max_iter=60`；不能写成正式 100-point/3000-iteration 性能证据。

| 指标 | baseline 中位数 | integrated 中位数 |
|---|---:|---:|
| representation seconds | 0.184861 | 0.175960 |
| single-fold model seconds | 0.204166 | 0.191047 |
| total technical probe seconds | 0.389702 | 0.367683 |
| PyRadiomics calls | 32 | 4 |
| Cox core calls | 10 | 10 |
| mask signature reuse rate | 0.8750 | 0.8750 |

CPU、RSS、磁盘 read/write 的每次原始记录与 median/range 均保存在 JSON；性能数字仅表示 bounded technical software probe。

## 回归与安全边界

- 定向与完整回归、compileall 和 `git diff --check` 的最终计数见 JSON `test_evidence`；完整回归若保留既有 `execution_status` wording assertion，则仅该已知失败可接受。所有 Python 检查均通过 wrapper 执行。
- 不启动 formal W08，不生成 risk、prediction、performance 或 model-freeze lock；不读 B，不写患者级输出。
- `formal_100_point_3000_iteration_performance_completed=false`；真实 A 50-fold provider probe 与 synthetic bounded performance probe 不替代彼此。

机器可读完整证据见同目录 `W08_local_L6_integration.json`。
