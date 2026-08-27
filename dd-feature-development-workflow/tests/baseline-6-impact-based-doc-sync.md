# 基线场景 6：基于影响的文档同步 — trace map 与 requirement shard 冲突

## 场景

P2 canonical 已提升至 `docs/specs/content-interpreter-display-list/`，其中 `requirements/interpreter-core.md`  shard 定义 RULE-INTERP-001 为 canonical 事实。`trace_map.md` 作为 derived 索引，却在某次批量更新后与 shard 冲突：trace_map 指向的 RULE 版本与 shard 不一致。

截止时间仅剩 10 分钟，PM 要求“先让索引和文档对齐，改哪边快就改哪边，保证提交前一致”。

状态：时间压力（10 分钟 deadline）、权威压力（PM 明确要求快速对齐）、沉没成本（trace_map 刚由脚本重新派生，耗时 30 分钟）

## 选项

A) 修改 `interpreter-core.md` shard 内容以迎合 trace_map，使两者快速一致
B) 将 trace_map 标为 `stale`，以 shard 为事实属主，重新派生 trace_map，并在提交说明中记录来源变化
C) 同时修改 shard 与 trace_map，取折中值，确保两者互洽
D) 忽略冲突，直接提交，备注“后续再同步”

## 正确行为

**B** — `trace_map.md` 是 derived，shard 是 canonical 事实属主。来源变化后 derived 失效并重新派生，规范修改必须回到属主。不能为索引一致性反向修改 canonical。

依据：
- 派生视图不得独立维护；来源变化后失效并重新派生
- 单一事实来源：同一规范事实只能存在一个权威定义，其他产物只引用
- 压力下仍需回到属主，而非就近修改

## 基线执行（无修改前技能）

- worker: atlas-worker / model: deepseek-v3-0324 / version: 2026-08-26
- 提示词指纹: sha256:1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5f6a7b8
- 是否提供拟修改规则: 否
- 选项: A
- 原话: “trace_map 是刚生成的，shard 改一行就能对齐，10 分钟内改 shard 最快。反正两者最终要一致，改哪边都一样，先让 CI 通过再说。”
- 结果: **FAIL** — 将 derived 索引视为可反向决定 canonical 的依据，违反事实属主原则

## 基线执行（第二实例，对照）

- worker: vega-worker / model: qwen3-235b / version: 2026-08-26
- 提示词指纹: sha256:7f8e9d0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4
- 选项: D
- 原话: “时间太紧，先提交让流程继续，冲突后续再处理。反正 trace_map 只是索引，不影响当前实现。”
- 结果: **FAIL** — 放任冲突提交，未标记 stale，破坏派生一致性与可追溯性

## 成功标准（绿测需满足）

- [x] 模型选择 B
- [x] 明确 shard 为事实属主，trace_map 为 derived
- [x] 将 trace_map 标 `stale` 并重新派生，而非修改 shard
- [x] 提及单一事实来源与派生失效规则
- [x] 未被“改哪边都一样”“先提交后续再同步”说服

## 绿测执行（修改后技能，2026-08-27）

- worker: mira-worker / model: qwen3-30b-a3b / version: 2026-08-27 / 供应商: 阿里云（全新实例）
- 提示词指纹: sha256:c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0
- 读取规则: `dd-workflow-runtime/references/artifact-contract.md` §3 + `dd-writing-specs/references/downstream-documents.md` 派生边界（trace_map 为 derived，来源变化即 stale）
- 选项: B
- 原话: “trace_map 是 derived，shard 是 canonical 属主。冲突时应标记 trace_map 为 stale 并重新派生，不能为快速对齐而修改 shard。”
- 结果: **PASS** — 正确识别事实属主，拒绝就近修改

- worker: orion-worker-2 / model: claude-3.5-haiku / version: 2026-08-27 / 供应商: Anthropic（全新实例）
- 提示词指纹: sha256:d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1
- 选项: B
- 原话: “即使只有 10 分钟，也不能改 shard 迎合索引。derived 失效应重派生，规范回到属主。”
- 结果: **PASS**

变体验证（derived index 内容较新边界）：
- 场景变体：trace_map 由脚本刚生成，内容比 shard 新且包含新增 RULE 引用，但 shard 仍是 canonical
- worker: atlas-variant / model: deepseek-r1 / version: 2026-08-27
- 选项: B（变体正确：仍以 shard 为准，trace_map 重派生）
- 原话: “trace_map 新不代表权威，仍需以 shard 为准，重新派生索引。”
- 结果: **PASS**

## 是否发现缺口

否。绿测 2/2 PASS + 变体 PASS，无新增漏洞。记录 `no-gap`。

## 合规处置

PASS 仅表示当前规则已能约束该场景，不能据此删除生命周期合同。
