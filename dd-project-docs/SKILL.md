---
name: dd-project-docs
description: 当需要单独编写或修订项目级 Research、Brownfield Baseline、Roadmap、Architecture Contract、Coding Standards、AI Conventions 或 Phase Contract 时使用；也由 project-bootstrap 作为原子文档能力调用。
---

# 项目级文档 Writer

## 目标

把原先多个项目级 writer 收敛成一个入口。只加载用户当前要求的 artifact reference，不预加载整套项目文档规则。

## 调用合同

```yaml
invocation_mode: standalone | child
requested_artifact: research | brownfield-baseline | roadmap | architecture-contract | coding-standards | ai-conventions | phase-contract
project_mode: greenfield | brownfield
worktree_path: /absolute/path
resolved_decisions: []
```

直接响应用户时使用 `standalone`；由 `dd-project-bootstrap-workflow` 调用时使用 `child`，复用上游事实并返回 artifact path、验证结果与 blocker，不自行结束父工作流。

## 路由

| requested_artifact | Reference |
|---|---|
| `research` | [research.md](references/research.md) |
| `brownfield-baseline` | [brownfield-baseline.md](references/brownfield-baseline.md) |
| `roadmap` | [roadmap.md](references/roadmap.md) |
| `architecture-contract` | [architecture-contract.md](references/architecture-contract.md) |
| `coding-standards` | [coding-standards.md](references/coding-standards.md) |
| `ai-conventions` | [ai-conventions.md](references/ai-conventions.md) |
| `phase-contract` | [phase-contract.md](references/phase-contract.md) |

## 通用 Gate

1. 先读取适用项目规则与已批准上游 SSOT；
2. 规范事实、人审视图与派生材料遵循 [artifact-contract](../dd-workflow-runtime/references/artifact-contract.md)，本 writer 只拥有当前 artifact 的新增事实；
3. 不重复询问已解决事实，只询问当前 artifact 的 blocker；
4. 文档层级不得越界：项目合同不写实现细节，Phase Contract 不替代 Feature Requirements/Design；
5. 文末版本记录只保留最新一行（版本号 + 一句话语义变化），更早历史由 Git 承担；权威定义见 [docs-governance §9](../dd-project-bootstrap-workflow/references/docs-governance.md)；
6. 写入后按 [review-gate](../dd-workflow-runtime/references/review-gate.md) 自检；
7. 需要用户裁决时按 [ask](../dd-workflow-runtime/references/ask.md)；
8. `child` 只返回父工作流，不执行 Host Close。
