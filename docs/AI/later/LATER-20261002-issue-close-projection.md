---
id: LATER-20261002-issue-close-projection
title: task-tracking 合同缺 Issue close 时机规则——外部关 Issue 造成投影漂移
status: closed
closed: 2026-10-02（合同修订随本分支交付：§6.2 增第 6 时机、新增 §6.5、§10 澄清、§13 两条红线、TestCloseRule + mutation 测试）
created: 2026-10-02
source: Macim #111 实测（用户在其他会话直接关闭已绑定 Issue，看板未同步；工作流实为 in-progress）
tags: [task-tracking, projection, macim]
related: [dd-workflow-runtime/references/task-tracking.md]
target_phase: task-tracking 分支（docs/task-tracking-projection）合入 develop 后的第一次合同修订
trigger: 用户批准对该分支的合同修订，或再次出现外部关闭 Issue 导致投影漂移时
---

# task-tracking 合同缺 Issue close 时机规则——外部关 Issue 造成投影漂移

## 现状（2026-10-02 Macim 实测）

- Macim #112（canvas-visual-encoding）：工作流真完成（status=completed），其他会话关闭了 Issue 但没同步看板 → 卡片滞留「待验证」。
- Macim #111（visual-region-split）：工作流**未完成**（in-progress），其他会话按用户要求直接关闭 Issue → 若把卡片标成「完成」即伪造投影；实测中按合同保持了「开发中」并在 checkpoint 澄清。
- 根因：`task-tracking.md` §6.2 的五个写回时机与 §10 的看板映射**都没有定义 Issue close 的时机与语义**——任何会话都可以绕过工作流直接 `gh issue close`，投影随之漂移，且合同对此无规则可依。

## 待做（合同修订，属主 task-tracking.md）

1. **§6.2 增补第 6 个写回时机（close 规则）**：Issue 关闭只能发生在工作流 Closure（`status=completed`，顺序：写最终 checkpoint → 同步看板「完成」→ close）或 `abandoned`（close 前写 abandoned checkpoint）；**禁止在工作流 active/paused/handoff-ready 期间关闭 Issue**——需要放弃任务时先走 abandoned 处置。
2. **§10 增补一句**：看板与 checkpoint 跟随 runtime state，**不跟随 Issue 的 open/closed 状态**；外部直接关闭已绑定 Issue 视为投影脱节，恢复方以最新 checkpoint 为准（已有 §1.1 原则的延伸，写明即可）。
3. **§13 红线增补**：把外部关闭 Issue 当作工作流完成；在 active/paused/handoff-ready 期间关闭已绑定 Issue 而不写 abandoned/completed checkpoint。
4. **可选机械化兜底**：目标项目 GitHub Actions 监听 `issues.closed`，若 Issue 正文/评论含 `dd-checkpoint:v1` 且最后一条 checkpoint 的 `state_status` 不是 completed/abandoned，则自动评论提醒并 reopen——作为投影漂移的机械防线。
5. **合同测试**：§6.1/§6.2 section-scoped 断言 + mutation 用例（把 close 规则行删除/篡改必须转红）。

## 延后理由

- 合同刚落地（2026-10-02 合入 develop@8486c19），本轮先以如实 checkpoint 澄清应急，避免在既有外审闭环之外夹带未审查的合同修订；
- 修订应走既有的测试先行 + 送审闭环，与本分支（docs/task-tracking-projection）待推送的 a1027a5 合并后一并处理成本最低。

## 复核方式

- 修订后跑 `dd-workflow-runtime/tests/test_task_tracking.py` 全量；
- 以 Macim 两个真实 Issue（#111 未完成、#112 已完成）作为语义复核样本。
