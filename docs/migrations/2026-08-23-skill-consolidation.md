# 2026-08-23 Skill 目录收敛迁移映射

来源 commit：`8bdfd99`（refactor: streamline）。原则：**用户意图/完整工作流才是 Skill；Stage、共享规则、Git 原子操作和传输协议下沉到 `references/`**。顶层 `SKILL.md` 从 60 个收敛为 16 个（清单见 [README-REFINED.md](../../README-REFINED.md)）。

## Skill 正文映射（旧路径 → 新路径）

### → dd-git-workflow

| 旧路径 | 新路径 |
|---|---|
| `dd-git-branch/SKILL.md` | `references/branch.md` |
| `dd-git-ci/SKILL.md` | `references/ci.md` |
| `dd-git-cleanup/SKILL.md` | `references/cleanup.md` |
| `git-commit/SKILL.md` | `references/commit.md` |
| `dd-git-conflict/SKILL.md` | `references/conflict.md` |
| `dd-git-health/SKILL.md` | `references/health.md` |
| `dd-git-merge/SKILL.md` | `references/merge.md` |
| `dd-ai-git-workflow/SKILL.md` | `references/scripts.md` |
| `dd-git-worktree/SKILL.md` | `references/worktree.md` |
| `dd-ai-git-workflow/scripts/*.sh`（6 个） | `scripts/`（原名保留） |

### → dd-project-docs

| 旧路径 | 新路径 |
|---|---|
| `dd-write-ai-conventions/SKILL.md` | `references/ai-conventions.md` |
| `dd-write-architecture-contract/SKILL.md` | `references/architecture-contract.md` |
| `dd-brownfield-baseline/SKILL.md` | `references/brownfield-baseline.md` |
| `dd-write-coding-standards/SKILL.md` | `references/coding-standards.md` |
| `dd-write-phase-contract/SKILL.md` | `references/phase-contract.md` |
| `dd-project-research/SKILL.md` | `references/research.md` |
| `dd-write-roadmap/SKILL.md` | `references/roadmap.md` |
| `dd-write-phase-contract/tests/*` | `tests/dd-write-phase-contract/` |

### → dd-workflow-runtime（由 `dd-shared-workflow-runtime` 更名）

| 旧路径 | 新路径 |
|---|---|
| `dd-shared-ask/SKILL.md` | `references/ask.md` |
| `dd-shared-ci/SKILL.md` | `references/ci.md` |
| `dd-shared-subagent/SKILL.md` | `references/review-gate.md` |
| `dd-shared-state/SKILL.md` | `references/state.md` |
| `dd-shared-ui/SKILL.md` | `references/ui-evidence.md` |
| `test-location-strategy/SKILL.md` | `references/test-location.md` |
| `dd-shared-workflow-runtime/references/runtime-contract.md` | `references/runtime-contract.md`（同结构迁移） |
| `dd-shared-workflow-runtime/tests/*`、`dd-shared-ci/tests/*` | `tests/`（后者在 `tests/dd-shared-ci/`） |

### → dd-writing-specs

| 旧路径 | 新路径 |
|---|---|
| `dd-write-requirements/SKILL.md` | `references/requirements-writer.md` |
| `dd-write-design/SKILL.md` | `references/design-writer.md` |
| 两者的 `tests/*` | `tests/dd-write-requirements/`、`tests/dd-write-design/` |

### → dd-feature-development-workflow

| 旧路径 | 新路径 |
|---|---|
| `writing-plans/SKILL.md` | `references/planning.md` |
| `writing-plans/plan-document-reviewer-prompt.md` | `references/planning-reviewer-prompt.md` |

### → gpt-grilling-review

| 旧路径 | 新路径 |
|---|---|
| `gpt-code-review.md`（原顶层文件） | `references/classification-policy.md` |
| `receiving-code-review/SKILL.md` | `references/receiving-feedback.md` |
| `gpt-review-loop/SKILL.md` | `references/transport.md` |

## 整目录删除（无继任者）

Superpowers 系重复流程与工具 skill：`brainstorming`、`dispatching-parallel-agents`、`executing-plans`、`finishing-a-development-branch`、`gh-cli`、`github-issue-create`、`github-issues-do`、`github-mr`、`github-pull`、`grilling`、`my-test-driven-debug`、`requesting-code-review`、`subagent-driven-development`、`systematic-debugging`、`test-driven-development`、`using-git-worktrees`、`using-superpowers`、`verification-before-completion`、`find-skills`（符号链接）、`shared/scripts/sync-ai-test-worktree.sh`。

例外：`brainstorming` 的 HTML server 脚本（start/stop-server.sh + server.cjs + helper.js + frame-template.html，字节不变）迁移到 `dd-docreview-grilling/scripts/`，供文档审核可视化使用。

## 历史文档原则

`docs/superpowers/plans/`、`docs/superpowers/specs/` 是实施记录，保持迁移前原文，不追改路径；需要新旧对照时查本文件。同日修复：`writing-design-specs_审查结果.md` 曾被误存为 `#U5ba1#U67e5#U7ed3#U679c.md` 乱码名，已恢复原名（内容未变）。

## 项目级不变量（本次收敛不改变）

上游拥有事实，下游引用事实；下游只拥有新增信息。弱模型需要完全展开的执行材料时，生成 derived artifact（实现计划/执行版，强模型展开或脚本生成 + SHA 校验），不复制进 canonical SSOT。
