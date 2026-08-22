# Refined Skills Layout

本包将原 60 个顶层 `SKILL.md` 收敛为 16 个。原则：**用户意图/完整工作流才是 Skill；Stage、共享规则、Git 原子操作和传输协议下沉到 `references/`。**

## 顶层 Skills

- `dd-feature-development-workflow`
- `dd-bug-fix-workflow`
- `dd-ai-refactor-workflow`
- `dd-project-bootstrap-workflow`
- `dd-writing-specs`
- `dd-project-docs`
- `dd-git-workflow`
- `dd-workflow-runtime`
- `gpt-grilling-review`
- `dd-docreview-grilling`
- `dd-xctest-newbie-grilling-review`
- `dd-later-tracking`
- `detailed-log`
- `mcp-builder`
- `workflow-runner`
- `writing-skills`

## 主要变化

- Superpowers 的 planning/TDD/debug/review/worktree/finish 等重复顶层流程已移除；Feature/Bug/Refactor 自己承担对应 Gate。
- `dd-shared-*` + `test-location-strategy` → `dd-workflow-runtime/references/`。
- 9 个 Git 相关入口 + `git-commit` → `dd-git-workflow/references/`，脚本统一到 `dd-git-workflow/scripts/`。
- Requirements / Design writer → `dd-writing-specs/references/`；Feature planning → `dd-feature-development-workflow/references/planning.md`。
- 项目级 Research/Baseline/Roadmap/Architecture/Standards/AI Conventions/Phase Contract → `dd-project-docs/references/`。
- 旧的 GPT 传输循环与 receiving-review 规则 → `gpt-grilling-review/references/`。
- `writing-skills` 的红-绿-重构规则已改为自包含，不再依赖 Superpowers。
