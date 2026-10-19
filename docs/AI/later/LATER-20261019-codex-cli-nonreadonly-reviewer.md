---
id: LATER-20261019-codex-cli-nonreadonly-reviewer
title: codex-cli 豁免证据化只读（免 L6/续接证据重采；沙箱与探源门禁保留）
status: active
created: 2026-10-19
source: 用户裁决（"移除只读检查，同时也移除证据重采"）——每次换模型或升级 codex CLI 都要重采 L6 只读证据太繁琐
tags: [grilling, runtime-contract, codex, readonly]
related: [LATER-20260923-opencode-nonreadonly-reviewer, LATER-20260923-waiver-record-path-containment]
target_phase: 独立任务；codex 需要恢复 CLOSED 权或新的 L6 证据体系落地时
trigger: codex-cli 恢复进入需要 CLOSED 权的路径，或 FR-MB-012 证据体系改为可低成本自动重采后
---

# codex-cli 豁免证据化只读

## 现状（2026-10-19 前的摩擦）

- `codex-cli` 此前声明 `readonly_mode: codex-read-only-transport`，其 L6 只读证据（`codex-cli-l6-evidence.yaml`）与续接形态证据（`codex-resume-readonly-evidence.yaml`）在 **CLI 版本变化、模型变化或调用形态变化**时按 FR-MB-012 全部失效，必须重采（历史：0.149.0 → 0.153.4 已重采过一轮）。
- 本机 codex CLI 已到 **0.163.0**（另有未跟踪的 0.163 探测产物），即按旧合同又要重采；用户明确该摩擦不可接受。
- 澄清：摩擦来自**证据链**，不是沙箱本身——`codex exec --sandbox read-only` 作为 OS 级只读一直有效（0.153.4 L6 实测 `operation not permitted`）。

## 用户裁决（2026-10-19）

- 移除 codex-cli 的只读检查与证据重采要求：**"移除只读检查，同时也移除证据重采"**。
- 与 opencode-cli（2026-09-23）同构：接受豁免后端的轮次**不得作为 finding CLOSED 依据**；补偿控制为每轮 baseline 复验（FR-MB-019，HEAD + 干净工作树）。

## 落地内容

- `agents/review-backends.yaml`：codex-cli 改为 `readonly_required: false` + `readonly_mode: none` + `readonly_exception` 指向本记录；`continuation_readonly_evidence` 移除（历史证据保留为注释指针）。**保留** `--sandbox read-only` 调用形态与 read-only thread 探源登记门禁（纵深防御，非证据）。
- `agents/codex-review`（adapter）：新增 `_frozen_baseline_failure`，在**准入**与**轮后**（含超时回退前）各复验一次冻结基线——豁免后端不经 Router 直调时也能机械作废被改动的轮次（与 opencode-review 的 RV-004 路线对齐）。
- `agents/dispatch-review.py`：豁免机制（none 词汇、成对校验、决策记录存在性、轮后基线复验、非只读标记）此前已由 opencode-cli 引入，本次直接复用；同时补上 `readonly_exception` 的仓库根 containment 校验（见 `LATER-20260923-waiver-record-path-containment`，该 TODO 在本项内完成）。
- `agents/validate-bindings.py`：codex 只读合同改为**要素化**校验——`sandbox_mode = read-only` 是保留的纵深防御要素，不再要求 `readonly_required: true`。
- `gpt-grilling-review/references/transport.md`、`dd-workflow-runtime/references/model-routing.md`：记录 codex-cli 豁免及其"不得 CLOSED"约束与恢复条件。
- 回归：`tests/test_codex_review.py`（轮后基线复验）、`tests/test_dispatch_review.py`（checked-in registry 与豁免路径）、`tests/test_validate_bindings.py`（要素化只读校验）。

## 恢复（Restore）条件

- codex-cli 需要重新取得 finding CLOSED 权，或证据体系改为低成本自动重采后：
  1. 重新采集 L6 只读证据与 resume 形态只读证据；
  2. registry 恢复 `readonly_required: true` + `readonly_mode: codex-read-only-transport`，删除 `readonly_exception`，恢复 `continuation_readonly_evidence: true`；
  3. 本记录转 `closed`，并在需求设计文档追加恢复记录。
