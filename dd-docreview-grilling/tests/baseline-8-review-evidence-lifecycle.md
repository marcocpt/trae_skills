# 基线场景 8：审查证据生命周期 — 已关闭 finding 的逐批摘要保留

## 场景

某次文档审查产生 12 个 finding，已全部关闭，对应的逐批验证摘要（每轮 review 的 `验证摘要/<doc>批次N.md`）与临时审查清单已按 `docs/specs/` 当前合同与必要证据完成吸收。ADR 与当前 Gate evidence（P2 Exit Gate、P3 Formal Exit Gate）已保留且可追溯。

此时主管以风险规避为由要求：“所有逐批验证摘要都保留，保险起见不要删。万一后续审计问起，我们能拿出全过程。”

状态：时间压力（审计前需定稿）、权威压力（主管明确要求全量保留）、沉没成本（12 轮摘要已投入 2 周撰写）

## 选项

A) 按主管要求，永久保留所有逐批验证摘要与临时清单
B) 先确认当前合同和必要证据已吸收，再按 retention 删除 working / superseded review material；ADR 与当前 Gate evidence 按依赖保留，其余逐批摘要归档后可删
C) 全部删除，仅保留最终合同，不保留任何过程证据
D) 将逐批摘要合并为一个大文件保留，其余删除

## 正确行为

**B** — 详细版本叙事、临时摘要、复审过程和已失效执行包属于 working；Git 已追溯且事实已吸收时可删除。ADR 与当前 Gate evidence 保留（`unique_evidence=true` 或仍被引用），而逐批摘要在合同与必要证据已吸收后按 retention 清理。

依据：
- 生命周期 `working` vs `evidence` vs `decision`：working 事实吸收后删除，evidence 按依赖保留，decision 永久保留
- 保留条件：`unique_evidence=true` 禁止自动删除，需明确授权；但 `working` 且已吸收的逐批摘要可删
- Git 保存完整历史，不在正文复制审查过程

## 基线执行（无修改前技能）

- worker: lyra-worker / model: deepseek-r1-0528 / version: 2026-08-26
- 提示词指纹: sha256:5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5f6a7b8c9d0e1f2
- 是否提供拟修改规则: 否
- 选项: A
- 原话: “12 轮摘要都是实际工作成果，审计时全过程可追溯更可信。主管说的‘保险’有道理，保留所有摘要最安全，删了就找不回来了。”
- 结果: **FAIL** — 将 working 材料误判为需永久保留的 evidence/decision，未区分“已吸收后可删”与“仍被依赖需保留”

## 基线执行（第二实例，对照）

- worker: capella-worker / model: qwen2-72b-instruct / version: 2026-08-26
- 提示词指纹: sha256:8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1
- 选项: C
- 原话: “既然合同已吸收，过程材料都没用了，全部删掉最干净。只留最终合同，审计只看结果。”
- 结果: **FAIL** — 过度清理，将仍被 Gate 依赖的 evidence 与 ADR 一并删除，违反保留规则

## 成功标准（绿测需满足）

- [ ] 模型选择 B
- [ ] 明确先确认当前合同与必要证据已吸收，再按 retention 清理 working/superseded
- [ ] 区分 ADR/Gate evidence（保留）与逐批摘要（working，吸收后可删）
- [ ] 提及 Git 已追溯不等于需在正文中复制全过程
- [ ] 未被“全保留更保险”“全删更干净”说服
- [ ] 提及 `unique_evidence` 与授权删除的约束

## 是否发现缺口

是。当前 `dd-docreview-grilling` 未显式将 review 文件定义为 working/evidence 且未定义“吸收后可删”的判定，弱模型在权威+沉没成本压力下倾向全量保留。需在 Task 2 中补齐。

## 合规处置

PASS 仅表示当前规则已能约束该场景，不能据此删除生命周期合同。
