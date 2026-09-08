# W08 L6 本地计算优化与集成审计

## 结论

L6 技术探针完成。当前集成在不改变科学参数的前提下保留表示缓存与 2-worker 并行，数值线程固定为 1；三重复测的总技术探针中位时间由 90.9752223 s 降至 31.6911194 s，下降 65.1651%，满足至少 20% 的保留条件。代表性阶段本身增加 13.6891%，但单折模型阶段下降 84.3636%，总时间仍显著下降。

本次没有启动正式 W08，也没有生成 B、风险、预测、性能或模型冻结结果。A 侧只读取 outcome-blind technical 输入；求解器、选择器和编排检查使用合成夹具。

## 环境与冻结绑定

- Conda 环境：`t2_radiomics`；实际解释器为该环境内的 `python.exe`。
- 版本：Python 3.7.12、NumPy 1.21.6、pandas 1.3.5、openpyxl 3.0.10、SciPy 1.7.3、scikit-learn 1.0.2、matplotlib 3.5.3、PyYAML 6.0、PyRadiomics 3.0.1、SimpleITK 2.2.1、PyWavelets 1.3.0。
- 所有 Python、测试和探针均通过 `tools/run_t2_radiomics.ps1 -PythonArguments` 调用。
- OMP、MKL、OpenBLAS、NumExpr 均固定为 1 线程。
- K-means 保持 K=2、k-means++、n_init=100、max_iter=300、tol=1e-4；外层 50 折、内层 5 折；alpha 4 个、每个 alpha 100 个 lambda；Elastic-Net max_iter=3000、tol=1e-7；minimumROISize=10。

## 正确性矩阵

| 检查项 | 结果 |
|---|---:|
| 50 个外层折的 K-means 中心/边界重复一致性 | 50/50，通过 |
| 代表性 low/high mask | 精确一致，通过 |
| G 特征 | 6 列，有限且重复稳定，通过 |
| R-low / R-high | 49 / 10 项；相对全量提取器最大绝对差异均为 0，通过 |
| P3B 三态边界 | 0、1–9、≥10 体素状态均通过 |
| fold-specific population 与 paired comparator | 5 条 population 规则、5 个固定 comparator，通过 |
| ModelPreprocessor | 合成 32×68，有限且重复精确一致，通过 |
| lambda 顺序 | 100 点，1.0 到 1e-4，严格递减，通过 |
| alpha/lambda 选择与确定性 tie-break | 通过 |
| 系数、收敛和失败审计 | 收敛系数有限；失败时系数清空，通过 |
| serial/parallel ordering | 2-fold 合成复核，通过 |
| checkpoint/resume | 往返、篡改拒绝、仅恢复有效完成折，通过 |

## 三重复测与调用计数

| 指标（baseline → integrated） | 结果 |
|---|---:|
| representation 中位时间 | 17.6685554 → 20.0872198 s |
| single-fold model 中位时间 | 74.2108837 → 11.6038996 s |
| total technical probe 中位时间 | 90.9752223 → 31.6911194 s |
| PyRadiomics 调用总数 | 6 → 6 |
| Cox core 调用总数 | 112254 → 39399 |
| mask signature cache 命中率 | 0% → 83.3333% |
| 峰值 RSS 中位数 | 357568512 → 356614144 bytes |

A technical 输入每次 393 行，三次合计 1179 行，失败数为 0。缓存验证包含失配发现与重算；原始缓存未被写入。

CPU 中位利用率（baseline → integrated）：输入加载 96.627% → 95.468%，SLIC 缓存准备/验证 95.725% → 97.439%，100-point alpha/lambda 路径 97.270% → 96.351%。对应磁盘读写中位数分别为：输入加载读取 25111241 → 25111241 bytes、写入均为 0；SLIC 缓存阶段读取 2433185 → 4424651 bytes、写入 28762 → 46689 bytes；数值路径读写均为 0。

## Worker 决策

保留 `representation_workers=2`、`outer_fold_workers=2`，每个 worker 的数值线程为 1。4-worker 未获准使用：本次已证明 2-worker 的正确性和总时间收益，但没有同等强度的 4-worker 内存、交换和磁盘稳定性证据。

## 回归与安全边界

定向回归共 141 项，137 项通过、0 errors、4 项失败。失败项为：

- L5 与 R6-5/R6-5R 的 W08 config hash binding；
- R6-5 canonical coordinate 与 registered binding；
- R6-5R audit path hash 的 one-to-one binding；
- technical preflight A 的 P4R current approved binding。

4 项均为当前 HEAD 已存在的 R6-5/R6-5R/P4R provenance binding 漂移，不由本次 L6 文件变更引起；因此不能将整组回归称为全绿。`compileall` 和 `git diff --check` 通过。

B 侧读取、reader/source 打开、统计生成、formal writer 调用均为 false；未启动实际正式运行，未写入个体级派生结果。临时脚本、探针输出和中间产物已清理。
