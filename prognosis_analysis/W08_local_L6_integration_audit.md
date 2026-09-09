# W08 L6 本地集成等价性与执行参数审计

## 结论

当前代码的 L6 技术探针已完成。正确性矩阵由当前代码 synthetic probe 与锁定 unittest 证据组成；真实 A 探针仅覆盖 outcome-blind provider、K-means boundary 和代表性 mask，不是模型性能或正式 W08。

bounded synthetic technical probe 的三次同机重复中，集成总 probe 中位耗时相对 baseline 下降 1.07%；由于该 workload 不是 formal 100-point/3000-iteration 证据，本审计不将复杂缓存/并行层标为正式性能批准。正式本地参数保持 `representation_workers=2`、`outer_fold_workers=2`、每 worker 数值线程为 1。

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
- 结果：50/50 fold 完成；provider fit calls=50；这是 current-code provider/mask representation evidence，不是 formal W08 model/performance evidence。
- 每个 fold 记录 seed、centers/boundary、代表性 low/high mask voxel counts、training population count/hash；不记录患者级明细。

## 性能比较（bounded synthetic）

该比较在同一机器、同一 `t2_radiomics`、同一 synthetic 输入和同一线程上分别重复 3 次。它使用 8 个 synthetic case、2 个 representation folds、5 个 candidate penalties、`max_iter=60`；不能写成正式 100-point/3000-iteration 性能证据。

| 指标 | baseline 中位数 | integrated 中位数 |
|---|---:|---:|
| representation seconds | 0.889933 | 0.874223 |
| single-fold model seconds | 0.293558 | 0.285022 |
| total technical probe seconds | 1.172572 | 1.160000 |
| PyRadiomics calls | 32 | 4 |
| Cox core calls | 10 | 10 |
| mask signature reuse rate | 0.8750 | 0.8750 |

CPU、RSS、磁盘 read/write 的每次原始记录与 median/range 均保存在 JSON；性能数字仅表示 bounded technical software probe。

## 回归与安全边界

- 定向回归：43/43 通过、0 failed、0 errors；完整回归：305 tests，304 通过、1 failed、0 errors。唯一失败为既有 `execution_status` wording assertion，未由本次 L6 文件变更引起。两次回归、compileall 和 `git diff --check` 均通过 wrapper/检查命令执行。
- 不启动 formal W08，不生成 risk、prediction、performance 或 model-freeze lock；不读 B，不写患者级输出。
- `formal_100_point_3000_iteration_performance_completed=false`；真实 A 50-fold provider probe 与 synthetic bounded performance probe 不替代彼此。

机器可读完整证据见同目录 `W08_local_L6_integration.json`。
