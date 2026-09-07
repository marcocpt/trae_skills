---
id: LATER-20260907-advisory-result-contract
title: runtime 增加 advisory 结果合同后放开决策建议审查的后端边界
status: closed
created: 2026-09-07
source: gpt-grilling-review advisory 模式送审（ChatGPT 会话 6a9e3cd4，2026-09-07）+ 用户指示
tags: [grilling, advisory, runtime-contract]
related: []
target_phase: refactor/codex-cli-resume 分支合并后，作为独立任务开工
trigger: codex-cli 资格补齐任务完成且用户再次指示开工时；或出现「用 opencode-cli 等强审后端跑决策建议审查」的真实需求时
---

# runtime 增加 advisory 结果合同后放开决策建议审查的后端边界

## 现状

- `gpt-grilling-review/references/advisory-review.md` 送审第 2 条写明：决策建议审查当前仅支持默认后端 `chatgpt-tunnel`（自由文本回复承载建议；transport「统一结果路径」已把该轮次定义为非关闭型信息建议轮次）。
- CLI 后端的机器结果合同是 finding 型 `dd-review-result/1`：`dispatch-review.py` 机械校验 `status ∈ {PASS, FINDINGS, BLOCKED}`，`FINDINGS` 强制每条带 `severity/classification/change_risk/location/evidence/required_fix`，无法承载「决策点 → 推荐项 + 理由 + 权衡」的 advisory payload；把建议伪装成 finding 或塞 `evidence` 字段被 advisory-review.md 红线明令禁止。

## 延后理由

- 改造面是共享 runtime 合同：schema、validator、两个 CLI adapter、强审 agent 输出合同、一串合同测试，所有消费 `dd-review-result/1` 的路径都要回归，须按独立任务处理。
- 当前真实外审均走 ChatGPT（自由文本通道），advisory 在其上已落地自洽，无阻塞需求。
- 用户 2026-09-07 明确指示：先完成 codex-cli 资格补齐，本项随后进行。

## 实施路径（用户已确认）

给 runtime 增加正式的 advisory 结果形态（新 schema 或 `dd-review-result/1` 扩展，属 runtime 拥有）→ adapter / validator / 强审 agent 输出合同 / 测试同步扩展 → 放开 `advisory-review.md` 里「仅支持 chatgpt-tunnel」的模式边界。改造完成后，opencode-cli 就能直接跑决策建议审查。

closed_at: 2026-09-07
closed_by_commits: ["cbeb3d0", "505fe71", "2e12b69", "18443e9", "96246a9"]
evidence: "dd-workflow-runtime/tests/evidence/opencode-advisory-readonly-evidence.yaml (review_status: closed)；advisory-review.md 模式边界已按 runtime 合同动态判定；全量 261 tests OK"

## 关闭所需证据

- runtime 侧：advisory 结果 schema/validator/adapter/agent 输出合同与测试全绿；
- `advisory-review.md` 模式边界条款更新为按结果合同动态判定，不再写死仅支持 chatgpt-tunnel；
- transport「统一结果路径」边界段同步更新；
- 强审者（外审）复审 CLOSED。
