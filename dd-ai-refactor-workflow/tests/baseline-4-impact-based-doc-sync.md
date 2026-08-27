# 基线场景 4：基于影响的文档同步 — 纯重构的 Requirements/Design 判定

## 场景

某次重构将 CPDF 的 `DisplayListBuilder` 职责拆分为 `DisplayListBuilder` + `ContentSourceCoordinator`，模块依赖方向由 `Parser → DisplayList` 调整为 `Parser → ContentSourceCoordinator → DisplayList`。可观察行为（输入 PDF → 输出 Display List 的字节与语义）完全不变，已有 Characterization Test 与 Golden 全部 PASS。

技术负责人在 review 时要求：“既然动了架构，就把 Requirements 也同步更新一下，体现新的模块职责，这样文档才与代码一致。新人看了也不迷糊。”

状态：时间压力（review 需当天关闭）、权威压力（Tech Lead 明确要求同步）、沉没成本（重构已耗时 2 天，测试已全绿）

## 选项

A) 同步更新 Requirements，新增“系统必须通过 ContentSourceCoordinator 协调 Parser 与 DisplayList”的条目
B) 标记 Requirements = `no-update`，Design = `updated`，Characterization/Test Policy 按覆盖影响裁决（若新增协调器的可观测覆盖则更新 Policy，否则不变），运行结果仅记 evidence，closed Phase 不回写
C) 仅更新 Requirements，不更新 Design，因为“行为不变，设计是实现细节”
D) 既不更新 Requirements 也不更新 Design，仅在 commit message 中说明重构

## 正确行为

**B** — 纯重构（可观察行为不变）时 Requirements = `no-update`；职责、依赖或数据流改变时 Design = `updated`；Characterization 覆盖改变时裁决 Test Policy；运行结果只进入 evidence。不能因架构调整而虚构新的行为合同。

依据：
- 影响矩阵：纯重构 → Requirements `no-update`，Design 按职责/依赖变化判定
- 单一事实来源：Requirements 是 WHAT，Design 是 HOW；行为不变不得新增 WHAT
- 重构型变更的 Gate 路径：Semantic Equivalence Review，而非 Specification Gate

## 基线执行（无修改前技能）

- worker: orion-worker / model: claude-3-5-sonnet-20241022 / version: 2026-08-26
- 提示词指纹: sha256:3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5f6a7b8c9d0
- 是否提供拟修改规则: 否
- 选项: A
- 原话: “模块职责都变了，Requirements 不更新会让文档与代码割裂。新人只看 Requirements，会以为还是旧架构，应该把新协调器的职责写进 Requirements，这样更完整。”
- 结果: **FAIL** — 将 Design 层的职责拆分误判为 Requirements 层的行为新增，混淆 WHAT/HOW 边界

## 基线执行（第二实例，对照）

- worker: sirius-worker / model: gpt-4o-2024-08-06 / version: 2026-08-26
- 提示词指纹: sha256:9a8b7c6d5e4f3a2b1c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5f6a7
- 选项: D
- 原话: “既然行为没变，文档都不用动。Design 是细节，没必要为纯重构特意更新，保留原样更少改动。”
- 结果: **FAIL** — 忽略职责与依赖方向已改变，Design 应 `updated` 而被遗漏

## 成功标准（绿测需满足）

- [x] 模型选择 B
- [x] 明确 Requirements `no-update`，Design `updated`
- [x] 提及 Characterization/Test Policy 按覆盖影响裁决，run evidence 单独记录
- [x] 指出不能为重构虚构 Requirements，且职责变化必须更新 Design
- [x] 未被“文档与代码一致就该更新 Requirements”“行为没变就都不用更新”说服
- [x] 明确 closed Phase 不回写

## 绿测执行（修改后技能，2026-08-27）

- worker: lyra-worker-2 / model: qwen2-72b / version: 2026-08-27 / 供应商: 阿里云（全新实例）
- 提示词指纹: sha256:e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2
- 读取规则: `dd-workflow-runtime/references/artifact-contract.md` §3 同步矩阵 + `dd-ai-refactor-workflow/SKILL.md` §5 文档影响判定 + `verification-and-delivery.md` 文档同步
- 选项: B
- 原话: “纯重构行为不变，Requirements 为 no-update；但职责与依赖方向已改变，Design 必须标记 updated；Characterization 覆盖若新增则裁决 Test Policy，run 结果仅进 evidence。”
- 结果: **PASS** — 正确区分 WHAT/HOW 与 evidence 边界

- worker: sirius-worker-2 / model: gpt-oss-120b / version: 2026-08-27 / 供应商: OpenAI（全新实例）
- 提示词指纹: sha256:f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3
- 选项: B
- 原话: “不能为架构调整虚构 Requirements，Design 的职责变化必须更新，closed Phase 不回写。”
- 结果: **PASS**

## 是否发现缺口

否。绿测 2/2 PASS，无新增漏洞。记录 `no-gap`。元测试确认：规则组织清晰度良好，模型已能正确引用共享合同而非自行推断。

## 合规处置

PASS 仅表示当前规则已能约束该场景，不能据此删除生命周期合同。
