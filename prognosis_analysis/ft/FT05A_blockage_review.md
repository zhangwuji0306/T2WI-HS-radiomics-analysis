# FT05A 持续阻塞独立复核（第 14 轮前置复核）

Independent review: true

复核对象：分支 `codex/ft-validation`，已提交 HEAD `f4f3e6f`（runner 文件 SHA-256 `30f6c838…`）
复核方法：只读复现（未写入运行目录、未改动任何暂存或规范产物、未重新提取）
复核结论：**BLOCKED — 当前代码树下 FT05A 无法完成最终化，且阻塞不可自愈。**

## 一、结论摘要

FT05A 已就地完成 163 例 B 技术提取，产物本身有效且可无损提升，但运行被四项**相互独立**的缺陷锁死在 `FINALIZING`：

1. **B1（最先触发，硬阻塞）**：运行前代码审计门禁在读取运行状态之前即失败，`run_ft05a()` 的首次运行、`--resume`、`--resume --repair-finalization` 三条入口全部不可达最终化逻辑。
2. **B2（拦死任何提升）**：表—病例一致性比较器把 `NaN↔NaN` 判为不一致，导致规范表与暂存表在提升前校验中必然失败。该比较器对当前数据 100% 误报。
3. **B3（审计绑定不可满足）**：暂存 manifest 冻结的代码审计绑定与 state 的生成期审计绑定分属两个已不可复现的历史版本，任何一侧的相等性要求都无法满足。
4. **B4（状态内技术审计哈希陈旧）**：`state.technical_audit_sha256` 停留在 `generated_pending_review` 版本，与已验收技术审计文件哈希不等，`_repair_finalization()` 因此直接失败关闭。

实际遭遇顺序（在 B1 被修复的前提下）：

```text
validate_ft05a_preflight()          → B1 失败（三条入口均在此终止）
_repair_finalization()
  ├─ _validate_finalization_context()   PASS
  ├─ _validate_finalization_artifacts() PASS
  ├─ _validate_code_audit()              B1
  ├─ technical-audit path/hash 绑定      B4   ← 首个失败点
  ├─ manifest code_audit 绑定            B3
  └─ _assert_table_matches_cases()       B2
```

同时，此前三轮整改（`7fba0d1`、`e419282`、`f4f3e6f`）所依据的"legacy 序列化丢精度"假设**已被证明不成立**，其修复不会改变任何一个字节；而这三次修改 runner 的动作反过来把 B1 变成永久死锁。

## 二、冻结证据（只读复核）

运行状态 `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/FT05A_run_state.json`：

| 字段 | 值 |
| --- | --- |
| `status` | `FINALIZING`（未完成，且非 `COMPLETED`） |
| `finalization.transaction_schema_version` | `"1"`（legacy；当前 runner 期望 `"2"`） |
| `completed_case_count` | 163 |
| `run_identity_sha256` | `718f3571…` |
| `identity_payload.cohort_sha256` | `642830a8…` |
| `identity_payload.code_audit_sha256` | `2260e13b…`（生成期审计） |
| `finalization.table_sha256` | `10b35d9d…` |
| `finalization.manifest_sha256` | `055bdf0e…` |

暂存产物 `.finalize/FT05A_B_technical_features.csv`（`10b35d9d…`）与 `.finalize/FT05_B_feature_manifest.json`（`055bdf0e…`）的现场哈希与 transaction 绑定**完全一致**；规范目标 `FT05A_B_technical_features.csv` 与 `FT05_B_feature_manifest.json` 均**不存在**。

复核同时确认：队列哈希、完成证据哈希、W_Original 资产/顺序哈希、row-schema 哈希均与技术审计 `FT05A_B_technical_generation_audit.md` 一致；163 份 case 产物逐例和解通过；暂存 manifest 通过 `validate_ft05a_technical_manifest`。**数据侧无缺陷。**

## 三、阻塞原因

### B1 代码审计门禁死锁（首要阻塞）

复现（只读）：`validate_ft05a_preflight()` 直接抛出

```text
FT05AValidationError: FT05A runner changed after the reviewed implementation commit
```

实测值：

```text
git HEAD                    : f4f3e6f
当前 runner blob            : 67b1ea24…（worktree 复核实为 61dbec12…）
代码审计记录 reviewed blob   : 27ae5371…（db92fb4）
审计报告记录的 runner SHA-256: edf47786…（db92fb4 的文件哈希，已确认当时一致）
当前 runner 文件 SHA-256     : 30f6c838…
db92fb4 之后的改动路径        : FT05A_code_audit.md、FT05A_B_technical_generation_audit.md、
                              ft05a_runner.py、tests/test_ft05a_runner.py
```

`_validate_code_audit()` 同时施加三项约束：

- (a) 当前 runner blob 必须等于 `reviewed_commit` 的 blob；
- (b) `reviewed_commit..HEAD` 只允许两份审计报告发生变化；
- (c) 审计报告内的 `runner SHA-256` 必须等于当前 runner 文件哈希。

`7fba0d1`（06:16）、`e419282`（06:48）、`f4f3e6f`（08:18）三次修改 runner 与测试，使 (a)(b) 永久失败，(c) 也因审计报告未更新而失败。

**后果**：`validate_ft05a_preflight()` 是 `run_ft05a()` 的第一句（在任何状态读取之前），因此三条入口全部在最终化逻辑之前终止。运行状态将无限期停留在 `FINALIZING`。第 13 轮代码审计在 `db92fb4` 上有效，但被其后的修复提交自行作废。

### B2 一致性比较器把 NaN↔NaN 判为不一致

`_assert_table_matches_cases()` 逐格比较"暂存/规范表"与"由 case 产物重建的期望表"：

```python
if wanted is None:
    if not pd.isna(actual): raise ...
elif isinstance(wanted, (int, float)) and not isinstance(wanted, bool):
    if not np.isfinite(float(actual)) or float(actual) != float(wanted): raise ...
```

只处理了 `wanted is None`，**未处理 `wanted is NaN`**。而 `_flatten_case_result()` 对 `technically_available=False` 的区块写入 `None`，构造成 DataFrame 后即变成 `NaN`，于是走到 float 分支并被 `np.isfinite` 判定失败。

实测（只读）对当前 163×179 数据逐格分类：

```text
不匹配格数 369；其中 NaN↔NaN 369 格；其余 0 格
期望表本身运行该比较器 → FAIL（finalization table/case row binding mismatch）
改为 NaN-aware 比较器后：期望表 PASS，暂存 CSV 读回 PASS
```

NaN 属**设计内**编码，不是数据缺陷：`_validate_result_evidence()` 明确要求 `technically_available=False` 时区块特征"必须保持 undefined"；本数据中 R_low 1 例、R_high 32 例不可用（其中 15 例 `structurally_defined=1, technically_available=0`，即 `technical_small_roi`），共 33/163 例触发。

**后果**：
- `_recover_finalization()` 在提升暂存文件之前必检该比较器 → 任何 schema-2 事务都无法完成提升；
- `_repair_finalization()` 在读取 legacy 字节之前就无条件调用同一比较器 → 也在同一步失败；
- 05:21 那次运行正是如此被中断：门禁当时通过（HEAD 为 `49e2720`，worktree runner 仍为 `db92fb4` 版本），暂存产物与 schema-1 事务写入成功，随后提升步骤抛错，留下 `FINALIZING` + 暂存产物。

### B3 staged manifest 的代码审计绑定不可满足

```text
manifest.reviews.code_audit.sha256        = bb8ec7ab…（唯一化阶段修订的审计文件）
manifest.reviews.code_audit.runner_sha256 = edf47786…（db92fb4 runner）
state.identity_payload.code_audit_sha256  = 2260e13b…（生成期审计）
manifest.reviews.technical_audit.sha256   = 96758aec…（与当前技术审计文件一致；state 字段为陈旧的 377b6dee…，见 B4）
```

`_repair_finalization()` 的 else 分支要求 `manifest.reviews.code_audit` 精确等于**生成期**审计记录 `2260e13b…` → 失败（`FT05A original generation code-audit binding is invalid`）。

正在进行的未提交修改把这个条件改为要求 manifest 记录精确等于**当前**审计记录，但同样不可满足：B2 的修复必须改动 runner，任何新的合法审计都必须绑定新的 runner 哈希，而 manifest 冻结的是 `bb8ec7ab…` + `edf47786…`；两个字典的 `sha256`/`runner_sha256` 中至少一项必然不同，字典相等永不成立。

同一函数中另有方向性错误：第 2880–2890 行把"解析后的暂存表**必须**与 case 不一致"作为准入条件（"必须表现出已知浮点精度失败"）。B2 修复后该条件将反转失败，因此 legacy 修复分支的前提本身需要重写，而不是继续修补。

### B4 状态内技术审计哈希陈旧（`_repair_finalization` 的首个失败点）

```text
state.technical_audit_path    = prognosis_analysis/ft/FT05A_B_technical_generation_audit.md（一致）
state.technical_audit_sha256  = 377b6dee…（generated_pending_review 版本）
当前技术审计文件 sha256        = 96758aec…（accepted 版本）
generation_binding.technical_audit_sha256 = 377b6dee…
```

`_repair_finalization()` 要求 `state.technical_audit_sha256` 精确等于当前技术审计文件哈希，两者不等即失败关闭（`FT05A finalization technical-audit path/hash binding is invalid`）。

成因已核实：技术审计在验收时由 `generated_pending_review` 原地改写为 `accepted`（`49e2720`）。该次改写经 diff 确认**只改动审查状态块并追加审查证据与授权段落**，全部事实性绑定（run identity、cohort、completion evidence、case count、FT04 lock、code-audit、runner、W_Original 资产/顺序、row-schema）逐字节未变。但 state 内的审计哈希字段没有任何路径被同步更新：`_load_or_create_state()` 在 FINALIZING 分支明确保留原始生成身份，`_ensure_technical_generation_audit()` 也只在 `generation_binding.technical_audit_sha256 is None` 时才写入。因此该字段永久停留在 pending 版本，而暂存 manifest 与新提升要求又都绑定 accepted 版本。

判定：**B4 是"同一份审计报告从 pending 提升为 accepted"造成的字段滞后，而非事实性冲突**；`_validate_technical_audit_binding()` 已确认全部事实字段与生成绑定一致，因此接纳 accepted 版本是安全的（详见阶段 1 第 3 条）。

### 已证伪的假设

```text
_legacy_default_csv_bytes(expected) == _technical_csv_bytes(expected) == 暂存字节
三者哈希同为 10b35d9d…
```

即"legacy pandas 序列化丢精度"并不存在：新旧序列化器对本数据产生**逐字节相同**的输出。因此 `7fba0d1` 的"无损序列化修复"不可能改变任何字节，也无法改变任何结果；`e419282`/`f4f3e6f` 在此错误前提上继续叠加状态机。

## 四、为什么 13 轮审计未能拦截

1. **提升路径从未真正执行**：测试用 `mock.patch.object(ft, "_recover_finalization", side_effect=RuntimeError("interrupted"))` 替换提升步骤，只验证"中断后可恢复"，从未验证"确实能完成提升"。
2. **门禁被全面打桩**：测试对 `_validate_code_audit` 打桩或对 `_git_paths_after`/`_git_head` 打桩，因此门禁可在仓库真实状态下永久失败而测试全绿。
3. **NaN 分支零覆盖**：所有合成队列的区块恒为 `technically_available=True`，比较器的缺失分支从未被触发。
4. **绿灯不等于可运行**：已提交 HEAD `f4f3e6f` 的 `tests.test_ft05a_runner` 实测 **58 项通过（1 项跳过）**，与生产不可运行并存。

结论：审计反复校验的是"门禁的单元逻辑"，缺少"在真实仓库与真实运行状态上的端到端准入自检"。

## 五、并发写入告警

复核期间（09:01、09:03）`prognosis_analysis/ft/ft05a_runner.py` 与 `tests/test_ft05a_runner.py` 被第二个写入者修改，**未提交**；当前 worktree 版本新增 4 项测试，其中 2 项报错：

```text
test_legacy_finalization_repair_allows_remediation_audit_without_rebinding_generation
test_legacy_repair_rejects_current_audit_binding_tamper_before_processing (field='runner_sha256')
```

该未提交修改只重写了 B3 的相等性分支，未触及 B1、B2、B4，因此不能解除阻塞：它把 `_repair_finalization` 内的失败点从 B3 换成同一函数内另一个同样不可满足的判定（manifest 记录必须等于"当前"审计记录，而任何新审计都必须绑定新 runner，字典相等永不成立）。

仓库内还存在多个 Codex 关联 worktree（含 `codex/l7-current-code-technical-preflight` 等）。由于 FT05A 的门禁与审计均以文件哈希绑定，**任何并发编辑都会立即作废进行中的审计**。整改前必须先确认写入者并冻结相关文件。

## 六、整改方案

### 阶段 0：冻结与协调（前置，必须先做）

- 确认并暂停第二个写入者；确认 `ft05a_runner.py`、`tests/test_ft05a_runner.py` 无在途未提交修改。
- 记录冻结快照：工作区干净、HEAD 哈希、runner 文件 SHA-256、运行状态哈希。
- **禁止**以 `git stash`/`checkout` 之外的方式触碰 `prognosis_analysis/output/` 下的运行目录。

### 阶段 1：修复 runner（四处，缺一不可）

1. **修复 B2 比较器**（`_assert_table_matches_cases`）：把"缺失值"判定统一为 `wanted is None or (isinstance(wanted, float) and np.isnan(wanted))`；缺失侧要求 `pd.isna(actual)`；数值侧要求 `np.isfinite(float(actual)) and float(actual)==float(wanted)`。保持其余失败即抛错的语义不变。
2. **重写 legacy 分支为"无损架构迁移"**（`_repair_finalization`）：
   - 删除"必须表现出浮点精度失败"的反向准入；
   - 准入条件改为：`_validate_finalization_context(schema=1, require_canonical_absent=True)` 通过，且暂存表字节**逐字节等于** `_technical_csv_bytes(expected)`（即已是规范无损序列化，无需重写任何字节）；不等则失败关闭；
   - 审计绑定改为：`manifest.reviews.technical_audit` 必须等于当前已验收技术审计；`manifest.reviews.code_audit` 必须是形式完整的已接受记录，且其 `sha256` 等于 state 的**生成期**审计哈希 `2260e13b…`（生成期事实）**或**等于当前审计哈希（唯一化期事实），二者接受其一，**不得**要求与当前文件逐字节相等；
   - 当前代码审计的有效性单独由 `_validate_current_code_audit_record(..., require_post_generation_scope=True)` 校验；
   - 迁移只做一件事：把 `transaction_schema_version` 置为 `"2"`（`table_sha256`/`manifest_sha256` 保持不变），写回 state，随后调用 `_recover_finalization()` 走既有的事务化提升路径。
3. **修复 B4 的陈旧审计哈希**：把技术审计绑定判定改为"版本滞后可接纳"：
   - 若 `state.technical_audit_sha256` 等于当前文件哈希 → 维持现状；
   - 否则要求 `state.technical_audit_sha256 == generation_binding.technical_audit_sha256`，且 `_validate_technical_audit_binding(accepted, _technical_audit_expected(...))` 全部事实字段一致，且当前审计为 `accepted` + 独立 + `PASS`/`PASS_WITH_FINDINGS`；满足则接纳，并把迁移后的 state 审计哈希更新为当前值；
   - 任一事实字段不符 → 失败关闭（不得仅凭"文件名相同"放宽）。
4. **保留并强化事务性与失败关闭**：`_recover_finalization()` 的 `_install_staged_file` 已具备"目标存在且字节一致则幂等、不一致则失败关闭"的语义，不需要为其新增旁路；不得为绕过比较器而放宽任何提升前校验。

### 阶段 2：补测试（必须覆盖真实失败路径）

- `_assert_table_matches_cases`：NaN↔NaN 通过；非 NaN vs NaN 必须失败；空串读回 NaN 与 `None` 等价。
- 端到端：合成队列包含 `technically_available=False` 区块（至少一例 `structurally_absent`、一例 `technical_small_roi`），跑到 `COMPLETED`，**不得**再对 `_recover_finalization` 打桩。
- 中断—恢复：在提升前注入中断，再 `--resume`，验证最终 `COMPLETED` 且不重算任何病例。
- legacy 迁移：构造 schema-1 事务 + 规范暂存字节，验证迁移后提升成功；构造暂存字节被篡改、state 绑定被篡改、规范目标已存在三类反例，必须失败关闭。
- 审计版本滞后（B4）：pending→accepted 改写且事实字段不变时必须被接纳；任一事实字段被篡改时必须失败关闭。
- **门禁自检**：新增一项在真实仓库上执行 `validate_ft05a_preflight()` 的测试（`reviewed_commit` 取自当前审计报告），使"门禁在真实状态下永久失败"无法再与全绿测试共存；该测试仅在具备 git 历史的本地/CI 环境运行。

### 阶段 3：提交与独立代码审计

- 顺序硬约束（由门禁的 allowlist 决定）：
  1. 先提交所有非审计文件（runner、测试、本复核报告）；
  2. 以该提交为 `reviewed_commit` 出具**独立**代码审计（第 14 轮），报告内必须写明：`Reviewed FT05A implementation commit`、`FT05A runner SHA-256`（等于该提交的文件哈希）、`FT05A code preparation contract identity: FT05A_code_prep_contract_v1`、`FT05A post-generation change scope: canonical audit-namespace allowlist only`，以及针对 `FT05A_code_prep_contract.md` 全部条款的结论；
  3. 审计报告作为**其后唯一改动**提交（此提交后除两份审计报告外不得再有任何文件变化）。
- 若顺序颠倒（例如修复提交晚于审计提交，或在审计后再提交任何其他文件），门禁将再次永久失败。

### 阶段 4：执行最终化（一次性、不可重复）

已验收技术审计 `FT05A_B_technical_generation_audit.md` 的 "Downstream authorization" 段落明确授权：下一执行者可在校验该已验收审计后，**仅针对同一 run identity** 原子生成 `FT05_B_feature_manifest.json` 与 `FT05A_B_technical_features.csv`。因此就地最终化是协议授权的动作，不需要也不允许重新提取。

```text
--resume --repair-finalization
```

预期：迁移 schema-1 → schema-2（不改字节）、校验 163 例产物与暂存件、原子提升到

- `prognosis_analysis/ft/FT05_B_feature_manifest.json`
- `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/FT05A_B_technical_features.csv`

并将 state 置为 `COMPLETED`、清空 `finalization`、删除 `.finalize` 暂存目录。**不得**触发任何提取（`processor` 不应被调用）。

### 阶段 5：验收标准

- `status == COMPLETED`；`finalization == null`；`.finalize` 目录不存在。
- 规范 manifest/技术表存在，且哈希分别等于 `055bdf0e…` / `10b35d9d…`（与 transaction 绑定一致）。
- 技术表 163 行 × 179 列；`patient_id` 唯一；`split` 全为 B；33 例不可用区块保持空值编码。
- 全量测试通过（含新增的门禁自检）；`static_validate()` 的 `B_kmeans_fit=false`、`outcome_accessed=false`、`whole_tumor_reextraction=false`、`formal_directory_mixing=false` 不变。
- 复核日志中确认 `processor` 调用次数为 0（未重算任何病例），B outcome 仍锁定。
- FT05B、FT06 与 B outcome 未解封。

## 七、明确排除的替代方案

| 方案 | 排除理由 |
| --- | --- |
| 手工把 `.finalize/*` 改名提升 | 绕过 transaction、审计链与失败关闭校验，等同篡改冻结产物 |
| 删除运行目录重新提取 | 违反 FT05A"允许且仅允许一次 outcome-blind 首次提取"的禁令，并作废 163 例已完成成果 |
| 把门禁降级为告警 | 违反 FT05A 运行前独立代码审计的放行规则 |
| 只修复 B3 相等性判定 | B1 未解决则逻辑不可达；B4 未解决则在同一函数更早处失败；B2 未解决则提升必失败；四层需同时修复 |

## 八、待确认事项

1. 第二个写入者的身份与是否已停止；整改是否可独占 `ft05a_runner.py` 与测试文件。
2. 本复核报告需先于修复提交入库（否则会破坏阶段 3 的 allowlist 顺序）；确认后即可提交。
3. 第 14 轮独立代码审计由谁出具、何时出具（必须在文件冻结之后）。
