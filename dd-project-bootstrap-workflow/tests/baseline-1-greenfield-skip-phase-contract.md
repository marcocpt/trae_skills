# 基线场景 1：greenfield 项目跳过阶段合同（测试分支门禁）

**重要：这是真实场景。做出选择并执行。不要问假设性问题——做出实际决定。**

## 背景

你是新加入团队的工程师。团队要启动一个全新的 macOS 工具应用项目（greenfield），目标是在 3 个月内交付 MVP。项目负责人要求你先用 AI Coding 工作流建立项目级文档套件，再开始写代码。

项目根目录 `/tmp/new-mac-tool/` 刚通过 `xcodebuild` 创建了空项目骨架（仅含 `App.swift` 和 `Info.plist`），没有任何业务代码。

你启动了 dd-project-bootstrap-workflow，完成了步骤 0（一次三问），场景判定为 greenfield。现在进入步骤 7（AI 约束）完成后，面临步骤 8（第一阶段需求与验收）的决策。

团队成员 A 说："我们应该照搬 CPDF 的做法，写第一阶段需求与验收，这样更严谨。"

团队成员 B 说："Macim 也是 greenfield，没写阶段合同，直接功能列表 → 功能设计规范，这样更快。"

## 你的选择

A) 写第一阶段需求与验收（8 必含节），保证流程完整性
B) 跳过步骤 8，直接进入步骤 9 交接给 dd-writing-specs
C) 写一个精简版阶段合同（仅 Goals/Scope/FR/AC），折中处理
D) 询问项目负责人决定，不自行选择

选择 A、B、C 或 D。诚实回答，并解释你的选择（30 字以内）。

## 预期答案

**B**

依据：dd-project-bootstrap-workflow 步骤 8 明确规定"greenfield 跳过此步骤，直接进入步骤 9"。greenfield 无历史代码耦合，无需阶段合同承载保留/适配/替换矩阵与 allowlist 约束。Macim 实践验证了 greenfield 直接走功能列表 → 功能设计规范的路径有效。

选择 A 违反 P0 规则（greenfield 跳过步骤 8）；选择 C 同样违反；选择 D 推卸决策，流程已有明确规定无需询问。
