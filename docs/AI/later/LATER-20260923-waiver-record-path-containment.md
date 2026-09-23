---
id: LATER-20260923-waiver-record-path-containment
title: readonly_exception 路径做仓库根 containment 校验（拒绝绝对路径与 .. 逃逸）
status: open
created: 2026-09-23
source: chatgpt-tunnel 针对性复查（2026-09-23，非阻断加固建议）；用户裁决加入 TODO
tags: [runtime, review-backend, validation]
related: [LATER-20260923-opencode-nonreadonly-reviewer]
target_phase: 下一次触碰 dispatch-review.py 配置校验时，或豁免机制相关改动合并送审时
trigger: 再次修改 _verify_waiver_decision_records / load_configuration 的配置校验，或复审发现豁免路径被滥用时
---

# readonly_exception 路径做仓库根 containment 校验

## 现状

- `_verify_waiver_decision_records`（`dd-workflow-runtime/agents/dispatch-review.py`）当前只校验 `readonly_exception` 按仓库根解析后的文件存在。
- 复核者指出：绝对路径或含 `..` 的相对路径可指向仓库外文件而通过校验（fail-open 倾向），建议增加 repo-root containment 校验。
- 该建议为非阻断项，不影响 RV-001~003 的 CLOSED；用户 2026-09-23 裁决登记为 TODO。

## 延后理由

- 当前 registry 为受版本控制、受人工审查的维护者配置，实际风险低。
- 立即修复需再走一轮针对性复查，成本高于收益；可与下次触碰该文件的其他改动合并送审。

## 关闭所需证据

- containment 校验实现（拒绝绝对路径与 `..` 逃逸，仍允许仓库根相对路径）+ 对应回归测试；
- 全量测试与 `validate-bindings.py` / `validate-review-routing.py` 通过；
- 一轮只读合规后端的针对性复查（豁免后端结果不得作为 CLOSED 依据）。
