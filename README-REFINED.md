# Refined Skills Layout

本包将原 60 个顶层 `SKILL.md` 收敛为 16 个。原则：**用户意图/完整工作流才是 Skill；Stage、共享规则、Git 原子操作和传输协议下沉到 `references/`。**

## 顶层 Skills

- `fdev`
- `bug`
- `rfct`
- `boot`
- `spec`
- `pdoc`
- `git`
- `wrt`
- `gpt`
- `drev`
- `xtst`
- `later`
- `dlog`
- `mcp`
- `flow`
- `skl`

## 主要变化

- Superpowers 的 planning/TDD/debug/review/worktree/finish 等重复顶层流程已移除；Feature/Bug/Refactor 自己承担对应 Gate。
- `dd-shared-*` + `test-location-strategy` → `wrt/references/`。
- 9 个 Git 相关入口 + `git-commit` → `git/references/`，脚本统一到 `git/scripts/`。
- Requirements / Design writer → `spec/references/`；Feature planning → `fdev/references/planning.md`。
- 项目级 Research/Baseline/Roadmap/Architecture/Standards/AI Conventions/Phase Contract → `pdoc/references/`。
- 旧的 GPT 传输循环与 receiving-review 规则 → `gpt/references/`。
- `skl` 的红-绿-重构规则已改为自包含，不再依赖 Superpowers。
