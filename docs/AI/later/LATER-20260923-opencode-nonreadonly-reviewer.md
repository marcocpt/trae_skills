---
id: LATER-20260923-opencode-nonreadonly-reviewer
title: opencode-cli 因免费档 403 降级为非只读强审后端（恢复条件与后续动作）
status: active
created: 2026-09-23
source: 用户实测要求（"测试下外生 opencode 是否可以工作"）+ 用户裁决（"确认取消只读限制"）
tags: [grilling, runtime-contract, opencode, readonly]
related: [gd-2026-09-02-multi-backend-grilling, LATER-20260923-waiver-record-path-containment]
target_phase: OpenCode Zen 套餐/Provider 策略变化后，作为独立任务恢复只读合同
trigger: OpenCode 免费档（或改用付费档/其他非 Zen Provider 后）重新接受带能力限制的 agent；或 opencode-cli 恢复进入需要 CLOSED 权的路径
---

# opencode-cli 因免费档 403 降级为非只读强审后端

## 现状（2026-09-23 实测）

- `opencode 1.18.32`（已是最新版）+ `muse-spark-1.3-contributor-free`（OpenCode Zen 免费档）下，**任何带能力限制的 agent 都被 provider 拒绝**：
  - 只读 `permission` 块（默认拒绝 + 只读工具白名单）→ `403 FreeTierError: OpenCode's free tier can only be used from within OpenCode`；
  - 换用 `tools: {write/edit/bash: false}` 或项目 config 层 `permission` → 同样 403（门槛识别的是"能力受限"本身，与限制语法/来源无关）；
  - 无限制 agent（默认 build、显式 allow-all）→ 正常；
  - 付费档模型 `opencode/muse-spark-1.3` → `402 Insufficient account funds`（账户无余额）。
- 该限制出现在 2026-09-08（当时 L6 取证仍可用受限 agent）与 2026-09-19（首次 403）之间，属 provider 侧策略变化，本地不可解。
- 完整实测矩阵见 `dd-workflow-runtime/tests/evidence/opencode-nonreadonly-decision-20260923.yaml`。

## 用户裁决（2026-09-23）

- 不改用 DeepSeek 等替代 Provider、不给 Zen 充值，选择**取消 opencode-cli 的机械只读限制**，让 opencode 强审可用。
- 同时接受约束：opencode-cli 的轮次**不得作为 finding CLOSED 依据**（CLOSED 仍须由只读合规后端落地）；补偿控制为每轮 baseline 复验（FR-MB-019，HEAD + 干净工作树）。

## 落地内容

- `agents/review-backends.yaml`：opencode-cli 声明 `readonly_required: false` + `readonly_mode: none` + `readonly_exception` 指向本记录；`continuation_readonly_evidence` 移除（历史证据保留为注释指针）。
- `agents/dispatch-review.py`：新增 `none` 词汇与"成对校验 + 决策记录"规则；豁免后端免 L6 证据，但其结果携带显式非只读标记 `readonly_confirmation = {confirmed: false, evidence: "not-required:<backend>:readonly-waived-by-decision"}`；stateful 候选序对豁免后端不要求续接只读取证。
- `agents/validate-bindings.py`：profile 权限块与 registry `readonly_required` 声明做跨产物一致性校验（豁免形态下 profile 不得再含权限限制块）。
- `agents/opencode-review`（adapter）：新增 `_frozen_baseline_failure`，在**准入**与**轮后**（含超时回退前）各复验一次冻结基线——豁免后端不经 Router 直调时也能机械作废被改动的轮次（RV-004 路线裁决，见下）。
- `gpt-grilling-review/references/transport.md`：opencode-cli 分节与 FR-MB-004 通用条款记录例外与"不得 CLOSED"约束；并新增「直调 adapter」合规边界（准入 + 轮后双重复验、请求字段约束）。

## 未恢复的路径（也在本项范围内）

- 原生 `opencode-native` / `strong-reviewer` subagent 路径**保持只读合同不变**，因此在免费档下仍会 403、不可实际使用；未做豁免。

## 相关裁决：豁免后端 finding 轮的路线（RV-004，2026-09-23）

- 现状：Router 的 finding 链不含 `opencode-cli`（它只出现在 advisory 的 stateful 候选序列），因此"用 opencode 做 finding/复审"没有规范化路径，实际走的是直接调 adapter。
- 用户裁决（2026-09-23）：采用**规范化 adapter 直调**——不改 Router finding 链（避免 Gate/CLOSED 语义风险），改为把直调约束写进 `transport.md`，并把轮后基线复验补进 adapter 使其机械化。
- 直调结果仍是豁免结果，**不得作为 finding CLOSED 依据**；漂移即 `baseline_mismatch` BLOCKED 且不 fallback。

## 恢复（Restore）条件

- OpenCode 免费档或付费档重新接受带能力限制的 agent（或改用其他可用 Provider 且完成 FR-MB-012 取证）后：
  1. 重新采集 L6 只读证据与 resume 形态只读证据；
  2. registry 恢复 `readonly_required: true` + `readonly_mode: agent-read-only-contract`，删除 `readonly_exception`；
  3. profile 恢复机械只读块（validate-bindings.py 会机械校验一致性）；
  4. 本记录转 `closed`，并在需求设计文档追加恢复记录。
