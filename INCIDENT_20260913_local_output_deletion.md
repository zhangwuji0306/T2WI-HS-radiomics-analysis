# 本地非受控输出删除事故与恢复报告（2026-09-13）

Status: 已恢复并完成完整性核验

影响对象：本地`feature_extract/`与`habitat_analysis/`目录树。患者级输出仍只保存在本地受控环境，不进入版本库。

## 一、事故机制

隔离验证曾把真实`feature_extract/`和`habitat_analysis/`目录以Windows目录联接挂入临时沙箱。Python 3.7的`shutil.rmtree`在清理沙箱时递归进入联接目标，导致真实目录内容被删除。

受版本控制的代码、配置和文档可由Git恢复；被`.gitignore`排除的影像预处理、生境图、患者级特征及QC输出只能由本地备份恢复。

## 二、恢复来源与范围

1. Git受控文件已依据当前分支和远程引用核对；不存在缺失文件，Git对象库完整。
2. `feature_extract/output/`已从外部备份恢复：当前目录与备份均为2,907个文件，逐路径的文件大小和修改时间完全一致。
3. `habitat_analysis/output/`已从外部备份恢复：保留20个幸存文件，补回523个缺失文件，共40,527,017字节；恢复后两端均为543个文件。
4. 生境输出完成逐文件SHA-256比较：缺失0、额外0、大小或哈希不一致0。
5. `prognosis_analysis/output/ft_20260910_01a08bf3/FT05A/`及`local_private/`未被覆盖或改写。

## 三、冻结资产核验

| 资产 | SHA-256 | 状态 |
| --- | --- | --- |
| `feature_extract/output/features_v2/muscle_f0.25/features_original.csv` | `462201e66d8e8989063f02f1d7f63865a23335883c582707dc7713f40d3e9649` | MATCH |
| `feature_extract/output/manifest.csv` | `bb13c69fa903744b7ef08887eb982518b98511310050edce1061f236279b5120` | MATCH |
| `habitat_analysis/output/habitat_features_A/global_descriptors_full_A.csv` | `5bcbd9a79764518b1f66142f72dbde386096a1f223d163ed744bf5b658c36011` | MATCH |
| `habitat_analysis/output/habitat_maps_A_manifest.csv` | `8c0fd7ed6ee3cfcb68cc4602e16be03b726e26c3d683a5274ea8f629d856ea3a` | MATCH |
| `habitat_analysis/output/feasibility_A_patient_balanced_post_slic_fix/global_centers.csv` | `cdef0a8e9dd9ba47f24997a1d0b8749dc378077565b9b27f099d294096c0b600` | MATCH |

FT01 asset manifest声明的13项来源全部存在且文件大小、SHA-256均匹配。FT04冻结锁的20项provenance来源全部通过`validate_ft_model_freeze_lock()`校验。

两个受行尾转换影响的配置保持锁定的LF字节：

- `feature_extract/configs/radiomics_params.yaml`：`5cad11c0c3671148e1d16a23b77263fbbcc7470c2e42bd28a8077bab60e058e9`；
- `habitat_analysis/configs/main_cross_case_kmeans_k2_4mm.json`：`fc2f856b3bc3fcd3d358f4476fd87a8117568712b3fc382c5e24e315e976bb3f`。

## 四、恢复后流程状态

锁定环境`t2_radiomics`版本核验通过。FT05A只读preflight已不再因W_Original或其他源资产缺失而停止；当前停止点为既有代码审计绑定：

```text
FT05A runner changed after the reviewed implementation commit
```

FT05A的B1–B5审计结论不因本次数据恢复改变。数据删除事故造成的恢复前置条件已经解除，不需要重新提取；后续仍须按既有整改与审计流程处理，且不得在门禁通过前执行最终化或读取B结局。

## 五、后续本地操作边界

- 临时验证必须使用真实复制，不使用目录联接或符号链接承载可能被递归清理的目录。
- 任何删除操作前必须解析并核对最终绝对目标，且不得指向项目真实数据树。
- Git checkout、分支切换或行尾处理后，先复核冻结配置的原始SHA-256，再执行FT05A preflight。
- 患者级恢复产物继续由`.gitignore`隔离，不得暂存或上传。
