# R6-6/G3R technical preflight independent review

## Disposition

`accepted for downstream use`

项目原生含义：`G3R ACCEPTED FOR FORMAL W08` 的 technical gate 已接受。该接受不等于 formal W08 已执行或 formal W08 已产生模型结果。接受后的唯一下一执行阶段为强制 sentinel `R6-6.5`；在其完成并通过前，不得启动 formal W08、真实 A-side outer-final Cox、risk score、prediction、performance evaluation、model comparison、calibration、model freeze 或任何 B validation。

## Repository and accepted bindings

- 当前 HEAD、执行代码提交和 evidence certificate 均为 `15fc59e36cc9b9337d32f77148ba6c0d3463fd00`；`origin/main` 与当前 HEAD 一致。
- 已接受的 R6-4A、R6-5R 和 R6-5 证据链与当前 technical preflight 绑定一致。R6-5 锁定为 `max_iter=3000`、`tolerance=1e-7`，objective、gradient、zero-start、penalty semantics、candidate pools/order、alpha/lambda 规则及 W07/W07A/P3B 规则均未改变。
- 当前 technical preflight code/config 的实际 SHA-256 与 certificate 一致；protected code/config tree SHA-256 为 `3b73d1f32b81363bf31e91224b12f0791a80122a87c3086c68e896a76b471fc3`。
- W07 outer split SHA-256 为 `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`；R_low/R_high candidate hashes 分别为 `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` 和 `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`。
- freeze lock、W04、W07/W07A、P4R、R6-4A、R6-5R、R6-5、current technical preflight code/config 及 aggregate artifact 的声明哈希均与实际文件一致。

## Completeness and feasibility

- Frozen design: `10 repeats × 5 outer folds = 50/50` fold units。
- Fixed technical definitions: `17/17`；每个定义均为 `50` 条记录。
- Aggregate records: `850/850`；缺失记录 `0`，重复 fold-definition records `0`。
- All required runs are estimable；all paired populations are valid；所有 `850` 条记录的 inner 5-fold technical feasibility 均有效。
- 聚合 event/censor feasibility 的最小计数为：training events `62`、training censors `210`、validation events `13`、validation censors `49`。这些值仅作为 technical aggregate feasibility gate，未用于训练、调参或生成性能。

## Technical correctness

- 使用 frozen W07 split/hash；habitat fitting 为 outer-training-only、patient-balanced `K=2`；boundary、mask 和 provider transform 均为 fold-specific，outer validation 未参与中心或 boundary fitting。
- P3B 八字段状态保持不变：`structural_absence=0`、`technical_small_roi=1–9`、`extractable>=10`，`minimumROISize=10`；eligibility 在 provider transform 之后、任何 preprocessing 之前执行。
- main、W-available、R_low、R_high 和 dual-radiomics model-specific populations 与 frozen 规则一致；paired comparator 使用同一 outer repeat/fold、同一训练派生 boundary、同一 eligible set 和同一 train/validation role assignment。

## Regression, environment and boundary

- Locked environment `t2_radiomics` probe：exit code `0`，Python `3.7.12`、NumPy `1.21.6`、pandas `1.3.5`、SciPy `1.7.3`、scikit-learn `1.0.2`、PyRadiomics `3.0.1`、SimpleITK `2.2.1`，全部匹配锁定规格。
- Technical regression suite：`51` tests，exit code `0`，failures `0`，errors `0`，skips `0`，unexpected skips `0`。
- `B_data_read`、`B_reader_invoked`、`B_source_opened`、`B_statistics_generated` 均为 `false`。
- `Cox_fit_called`、risk score、prediction、performance、model comparison、calibration、formal W08、R6-6.5 和 model freeze 均为 `false` 或 absent；`model_freeze_lock.json` 不存在。

## Aggregate output and privacy

- `P5_technical_preflight_summary.json`、`P5_fold_feasibility.csv`、`P5_release_gate.json` 和 `P5_sha256_manifest.json` 为唯一 aggregate output 成员；manifest 中三项数据文件的实际 SHA-256 全部匹配。
- 聚合 CSV 不含患者标识列、影像号、原始路径或患者级技术字段；未发现 patient-level output、formal model output 或性能字段进入 Git tracked files。
- 审查对象 SHA-256：evidence JSON `0f82258a61ce9ba8084da9a7b06355fd81d2275ec127102ccc416e7655c30278`；Worker audit `bc20aa96d995cc617b41f6216d1f0a2d40bfaaf20de135a89d81a26a38d302f7`；aggregate manifest `0cd8a09bc395f6c22c1c07f6bc6344ebe9a97b84e1a8da34130a2062655d76e6`。
