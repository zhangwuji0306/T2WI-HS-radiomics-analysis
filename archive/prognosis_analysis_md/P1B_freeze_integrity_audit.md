# P1B 第一把锁完整性审计

## 审计范围、时间和起始 commit

- 审计时间：2026-09-02T14:50:08+08:00。
- 起始 commit：`bbae7841884a299a59661d8171e1bea7502ce466`。
- 上游基线：P0 `c7158a656b82f956f9b559a2e7bb1f5d5735f8c6`；P1A 审计提交为起始 commit。
- 范围：原始 `habitat_analysis/freeze_lock.json` 的 schema、路径绑定、SHA-256、地图 manifest 及其 393 个地图文件；W04/W03/W07 的相关绑定；三个未被原锁绑定的 supporting audit 文件。
- 边界：未运行模型、性能评估、预测、W08 formal、50-fold preflight；未读取 B source、B validation 数据或患者级内容本身。A-side 仅执行锁算法所需的 ID hash、文件 hash、存在性和 manifest 完整性核验。

## Core frozen scientific artifacts 与 supporting audit artifacts

### Core frozen scientific artifacts

原锁的核心科学冻结集合包括：

- A393/A137 技术队列 ID hash；
- manifest、scanner map、preprocessing config、SLIC config；
- high-signal screening 文件；
- formal bootstrap summary；
- global descriptors、feature QC、feature dictionary；
- habitat map manifest 及其 393 个地图文件。

核验结果：12 个核心锁字段全部 `MATCH`；high-signal screening 的 2 个文件均存在且复合 hash `MATCH`；地图 manifest 为 393 个唯一条目，393/393 个地图文件存在、逐项 hash 匹配，未发现重复、缺失或额外文件。

### Supporting audit artifacts

- 锁绑定的 supporting audit：`threshold_audit` 与 `threshold_confounding_audit`，2/2 个锁字段 `MATCH`。
- 未被原锁绑定的 supporting audit：
  - `habitat_analysis/output/habitat_features_A/freeze_qc.csv`：存在；SHA-256 `6887ad00ec8bed586f407df9b2d1c38085b474c60e8ba6f63508458c71c45444`；未绑定。
  - `habitat_analysis/output/freeze_preflight_A_post_slic_fix/freeze_preflight.csv`：存在；SHA-256 `f0e9a2e339c8b34a3c5ea486ba3ba0da8a2bc443a13eeb5bca8519b1eb3131d8`；未绑定。
  - `habitat_analysis/output/freeze_preflight_A_post_slic_fix/freeze_preflight.md`：存在；SHA-256 `3cf68ba988e0f521ee37a927b3ff00aee2032084b022b2203903524072867ee7`；未绑定。

三个 supporting 文件均不在原锁的 `artifact_paths`，也没有对应的顶层 hash 字段；它们不参与当前 `validate_freeze_lock` 结果。

## 原锁逐项 hash 核验结论

- 原锁 schema/version：`freeze_schema_version=1.0`；`validate_freeze_lock`：`PASS`。
- 14/14 个原锁绑定 hash 字段重新计算后与 lock 记录一致；当前文件缺失：0；hash mismatch：0。
- 原始 lock 文件 SHA-256：`0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262`。
- 原锁状态字段保持：`A_outcome_unlock=true`、`B_unlock=false`、`outcome_columns_read=false`、`B_data_read=false`、formal bootstrap `1000/1000` 且 `formal_eligible=1`。

## 原 lock、W04、W03/W07 绑定关系

- W04：`prognosis_analysis/modeling_protocol.json` 当前 SHA-256 为 `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`。W04 的 `technical_freeze` 引用与原锁文件 hash、schema `1.0` 一致；W01 feature dictionary 和 W01 method config 的绑定一致；19/19 个 W04 `source_revisions` 文件级 hash 均 `PRESENT_MATCH`。W04 绑定原锁，但原锁不反向绑定 W04。
- W03：`prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json` 当前文件 hash 为 `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2`。按 W03 candidate hash 算法重算，R_low 为 49 个、R_high 为 10 个，两个 candidate hash 均与 W03 metadata 及 W04 记录一致。W03 candidate pool 由 W04 绑定，未纳入原锁的 14 个 hash 字段。
- W07：`prognosis_analysis/configs/w07_outer_splits.json` 当前文件 hash 为 `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217`，状态为 frozen；其 source、schema、source audit 的三个文件级绑定均 `PRESENT_MATCH`。`prognosis_analysis/output/outer_splits_A.csv` 文件级 hash 为 `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`，与 W07 protocol 记录一致。W07 split 由 W07 自身配置/协议绑定，未纳入原锁。
- 原锁对 W04/W03/W07 的关系是上游技术锁被后续协议引用，而不是将后续建模协议、candidate pool 或 outer split 反写进原锁；未发现相关 mismatch 或缺失。

## 原始锁 immutable 与历史行为核验

- `git diff --exit-code -- habitat_analysis/freeze_lock.json`：无 unstaged diff。
- `git diff --cached --exit-code -- habitat_analysis/freeze_lock.json`：无 staged diff。
- 当前原锁与 P0 基线 `c7158a656b82f956f9b559a2e7bb1f5d5735f8c6`：无 diff。
- `git log --follow -- habitat_analysis/freeze_lock.json` 显示原锁仅在 `3c3f16e838ff985551bf173ea1618477b1940d5e` 添加，至起始 commit 未发生后续修改；本审计未执行重新冻结或任何会写回原锁的脚本。

基于当前工作树、提交历史及 W04 绑定，未发现通过重新读取 DFS 前重新冻结而改变历史锁的证据。Git 历史不能证明仓库外每一次本地进程行为；该限制不改变当前文件完整性结论。

## freeze_integrity_addendum.json 最小 schema 建议

建议由后续 P3E 另行创建，且不改写原锁：

```json
{
  "schema_version": "1.0",
  "original_freeze_lock_sha256": "<64-lowercase-hex>",
  "freeze_qc_sha256": "<64-lowercase-hex>",
  "freeze_preflight_csv_sha256": "<64-lowercase-hex>",
  "freeze_preflight_md_sha256": "<64-lowercase-hex>",
  "verification_timestamp": "<RFC3339>",
  "verification_commit": "<40-hex-git-commit>",
  "core_scientific_artifacts_match_original_lock": true,
  "scientific_parameters_changed": false,
  "technical_freeze_regenerated": false,
  "outcome_used_to_modify_technical_method": false,
  "B_data_read": false
}
```

## W01 rerun decision

- core frozen scientific artifacts altered? **NO**。
- original freeze lock still validates? **YES**。
- historical W01 needs scientific rerun? **NO**。

理由：14/14 个原锁绑定 hash 字段、393/393 个地图文件及 manifest 均通过；原锁与 P0 基线无 diff；W04/W03/W07 的后续引用关系无 mismatch。三个未绑定 supporting audit 文件只构成待补充的完整性证据，不改变任何冻结参数、队列绑定、特征定义或地图内容，因此不触发 W01 scientific rerun。

## Evidence files/commands 与 B_data_read 状态

证据文件（均为仓库相对路径）：

- `AGENTS.md`
- `项目说明.md`
- `PROJECT_STATUS.md`
- `habitat_analysis/freeze_lock.json`
- `habitat_analysis/analysis_freeze.md`
- `habitat_analysis/scripts/freeze_lock.py`
- `prognosis_analysis/modeling_protocol.json`
- `prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json`
- `prognosis_analysis/configs/w07_outer_splits.json`
- `prognosis_analysis/W07_outer_splits_protocol.md`
- `T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md`

核验命令：

- `python -c "... freeze_lock.compute_artifact_hashes(...) ..."`：逐项重算原锁 14 个 hash 字段。
- `python -c "... freeze_lock.validate_freeze_lock(...) ..."`：原锁 schema、状态和 artifact hash 验证通过。
- `python -c "... freeze_lock.validate_habitat_map_manifest(...) ..."`：393/393 地图 manifest 覆盖通过。
- `Get-FileHash -Algorithm SHA256`：三个 supporting audit 文件及 W04/W03/W07 相关文件的文件级 hash。
- `git diff --exit-code -- habitat_analysis/freeze_lock.json` 与 `git diff --cached --exit-code -- habitat_analysis/freeze_lock.json`：原锁无工作树 diff。
- `git diff --check`：通过。

状态：W08 formal **HOLD**；`B_unlock=false`；`B_data_read=false`；`prognosis_analysis/model_freeze_lock.json` **ABSENT**。本审计未创建、修改或提交任何患者级 artifact；本报告不包含患者 ID、患者级清单、本机绝对路径、邮箱、凭据或秘密。
