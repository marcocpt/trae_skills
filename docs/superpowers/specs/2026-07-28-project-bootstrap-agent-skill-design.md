# 项目 Bootstrap Agent Skill 生态重构设计

> 最后更新：2026-07-28  
> 文档状态：已批准方案，待书面审查

## 1. 目标

把 `dd-project-bootstrap-workflow` 及其直接依赖重构为 Trae/Codex 可以跨会话稳定执行的项目 Bootstrap Agent Skill 生态。在不降低产物质量和 Gate 强度的前提下，通过渐进式加载、状态恢复、上游事实复用和按风险审查减少重复上下文与 Token 消耗。

## 2. 成功标准

1. `dd-project-bootstrap-workflow/SKILL.md` 只保留触发边界、路由算法、依赖图、节点 Gate、状态恢复和 Handoff，不再内嵌完整 docs 治理规范。
2. 用户可指定任意入口；Agent 必须先执行 Preflight Gap Scan，补齐阻塞依赖后再进入请求节点。
3. Greenfield/Brownfield 按历史兼容义务判定，代码数量只作为辅助信号。
4. Bootstrap 可在新会话读取持久化状态、验证产物后继续，不重复询问已确认事实。
5. 父 skill 已确认的事实必须传给子 skill；子 skill 只询问缺失的阻塞输入或自身新增决策。
6. Workflow Gate 与 Git Delivery Gate 分离；未提交不再自动等价于节点未完成。
7. 审查始终覆盖范围、正确性、可验证性三个语义视角，但只有高风险节点默认使用三个并行审查 Agent。
8. Brownfield Characterization Test 只有经过处置分类后才能进入目标 AC。
9. Legacy Compatibility Surface 与 Target Public Surface 分开管理。
10. Bootstrap 对 Greenfield/Brownfield 统一交接给 `dd-feature-development-workflow`，通过结构化 Handoff 表达模式差异。
11. Trae 完成 Bootstrap 后禁止直接结束会话；必须 ASK 用户“结束本次任务”或“还有其他任务”。

## 3. 非目标

- 不重写 bug-fix、refactor、Git、CI 或 UI 验证工作流。
- 不改变现有项目文档的业务内容。
- 不把 docs governance 拆成可独立触发的 skill。
- 不要求所有既有 skill 在本轮统一使用同一种文档命名。
- 不用一次 Bootstrap 偿还 Brownfield 的全部历史 lint、测试或架构债务。

## 4. 总体架构

```text
User request
    ↓
dd-project-bootstrap-workflow/SKILL.md
    ├─ Preflight / Gap Scan / State Restore
    ├─ Dependency Graph / Node Gate
    ├─ Child Invocation Contract
    └─ Handoff / Host Close Contract
         │
         ├─ references/docs-governance.md
         ├─ references/execution-contract.md
         └─ references/brownfield-policy.md
              │
              ├─ dd-project-docs/brownfield-baseline
              ├─ dd-project-docs/research
              ├─ dd-project-docs/roadmap
              ├─ dd-project-docs/architecture-contract
              ├─ dd-project-docs/coding-standards
              ├─ dd-project-docs/ai-conventions
              └─ dd-project-docs/phase-contract
                       ↓
              structured handoff
                       ↓
            dd-feature-development-workflow
                       ↓
                 dd-writing-specs
```

核心原则是“workflow 负责编排，writer 负责产物，reference 负责详细政策，state 负责跨会话连续性”。

## 5. 文件结构与职责

### 5.1 Bootstrap 核心

| 文件 | 职责 |
|---|---|
| `dd-project-bootstrap-workflow/SKILL.md` | 短入口、Preflight、依赖图、节点调度、Gate、Handoff、Trae 收尾约束 |
| `dd-project-bootstrap-workflow/references/docs-governance.md` | 当前内嵌 docs 治理规范、目录、SSOT、同步、History/ADR、阅读策略 |
| `dd-project-bootstrap-workflow/references/execution-contract.md` | 状态模型、Gap Scan、节点契约、审查预算、Workflow/Delivery Gate、子 skill 调用协议、Handoff |
| `dd-project-bootstrap-workflow/references/brownfield-policy.md` | 模式判定、Characterization 分类、兼容面拆分、lint ratchet、技术探针和架构冻结规则 |
| `dd-project-bootstrap-workflow/tests/baseline-1-greenfield-skip-phase-contract.md` | 验证空脚手架仍是 Greenfield，默认跳过 Phase Contract |
| `dd-project-bootstrap-workflow/tests/baseline-2-brownfield-baseline-first.md` | 验证请求从 Roadmap 开始时仍补齐 Brownfield Baseline |
| `dd-project-bootstrap-workflow/tests/baseline-3-resume-without-reasking.md` | 验证跨会话恢复和已确认事实复用 |
| `dd-project-bootstrap-workflow/tests/baseline-4-trae-final-ask.md` | 验证 Trae 完成后必须 ASK，不能直接结束 |

### 5.2 新增 Phase Contract writer

| 文件 | 职责 |
|---|---|
| `dd-project-docs/phase-contract/SKILL.md` | 独立编写准备阶段或迁移阶段的 `{X}_01_阶段需求与验收.md` |
| `dd-project-docs/phase-contract/tests/baseline-1-brownfield-classification.md` | 验证 Characterization 分类到 AC 的映射 |
| `dd-project-docs/phase-contract/tests/baseline-2-known-defect-not-ac.md` | 验证 KNOWN_DEFECT 不升级为目标契约 |
| `dd-project-docs/phase-contract/tests/baseline-3-upstream-context.md` | 验证复用 Bootstrap 上游事实且不重复 grill |

`dd-project-docs/phase-contract` 与 `dd-writing-specs/requirements-writer` 的边界：

- `dd-writing-specs/requirements-writer` 面向功能或产品需求合同；
- `dd-project-docs/phase-contract` 面向项目准备、迁移、兼容基线和阶段 Exit Gate；
- 两者共享 Requirements 层原则，但触发条件、上游输入和验收映射不同。

### 5.3 共享协议

| 文件 | 修改职责 |
|---|---|
| `dd-shared-state/SKILL.md` | 增加 `project-bootstrap` 类型、通用状态字段、完成态不阻塞并发、恢复后产物验证 |
| `dd-shared-ask/SKILL.md` | 抽象宿主结构化询问；增加 Trae 会话结束 ASK 合同；保持 Codex 无工具时简短文本回退 |
| `dd-shared-subagent/SKILL.md` | 从“所有检查固定三 Agent”改为质量标准不变、执行强度按风险选择 |

### 5.4 直接子 skill

| 文件 | 修改职责 |
|---|---|
| `dd-project-docs/brownfield-baseline/SKILL.md` | 使用历史义务定义；输出完整处置分类；区分旧兼容面与目标公开面 |
| `dd-project-docs/research/SKILL.md` | 接收上游上下文；只为未验证高风险假设触发技术探针 |
| `dd-project-docs/roadmap/SKILL.md` | 消费 Gap Scan、研究和基线事实，不重复询问；明确路线级 Gate |
| `dd-project-docs/architecture-contract/SKILL.md` | 区分 provisional/approved/frozen；拆分 Legacy/Target Public Surface |
| `dd-project-docs/coding-standards/SKILL.md` | Greenfield 零新增违规；Brownfield baseline + changed-code ratchet |
| `dd-project-docs/ai-conventions/SKILL.md` | 生成短 `AGENTS.md`、按需 nested `AGENTS.md`、薄 Trae adapter，并固化 Trae 最终 ASK |
| `dd-feature-development-workflow/SKILL.md` | 接收 Bootstrap Handoff，复用工作环境、目标、范围、阶段合同和已确认决策 |

## 6. Preflight 与模式判定

Preflight 是任何入口的共同前置步骤，只读取完成判定所需的最少上下文：

1. 读取当前 Git/worktree 状态及适用的 `AGENTS.md`/项目规则；
2. 检测宿主能力：Trae/Codex、结构化询问、子 Agent、Git 权限；
3. 恢复 `project-bootstrap-state.json`；存在时验证记录的产物仍存在且未明显失效；
4. 确认 `requested_entry`，但不把它当成无条件跳过前置依赖的 `start_step`；
5. 识别已有治理产物为 `missing`、`partial`、`valid`、`stale` 或 `conflicting`；
6. 生成 `blocking_gaps` 与 `deferred_gaps`；
7. 仅对无法从仓库或状态推断的阻塞决策询问用户。

模式定义：

- Greenfield：不存在需要理解、保留、适配、替换或明确废弃的既有产品行为与兼容承诺。
- Brownfield：存在至少一项上述历史义务。

发布版本、真实用户、Public API、持久化数据、外部调用方、生产行为、协议、兼容性测试和迁移承诺是主要信号。源文件数量只用于发现候选证据，不能单独决定模式。

## 7. 状态模型

状态文件位于 worktree 私有 Git 目录：

```text
$(git rev-parse --git-dir)/project-bootstrap-state.json
```

必含信息：

```yaml
schema_version: 1
workflow_type: project-bootstrap
status: active | handoff-ready | completed | paused
project_mode: greenfield | brownfield
host: trae | codex | other
requested_entry: <节点名>
current_node: <节点名>
completed_nodes: []
artifacts: {}
decisions: []
blocking_gaps: []
deferred_gaps: []
handoff: {}
```

规则：

- 每个节点 Gate 通过后立即更新状态；
- 恢复时先验证状态与文件，不能盲信 JSON；
- 已确认事实保存在 `decisions`，子 skill 禁止重复询问；
- `completed` 状态不阻塞新的工作流；
- Handoff 被下游确认接收前保留状态；
- 无状态文件时从仓库事实重建，不默认从头 grill。

## 8. 依赖图与节点 Gate

```text
Preflight
   ↓
Docs Governance
   ├─ Brownfield Baseline（Brownfield 必需）
   └─ Research / Technical Spike（风险触发）
            ↓
          Roadmap
            ↓
 Architecture Contract (provisional/approved baseline)
            ↓
   Coding Standards
            ↓
      AI Conventions
            ↓
 Phase Contract（Brownfield 必需；Greenfield 默认跳过）
            ↓
          Handoff
```

每个节点用同一契约描述：

- `requires`：必须有效的上游事实或产物；
- `produces`：该节点唯一负责的产物；
- `gate`：可验证的完成条件；
- `next`：依赖已满足的候选后继节点。

通用 Workflow Gate：

1. 产物存在；
2. 产物通过该节点的语义验证；
3. 阻塞决策已解决；
4. 状态已持久化；
5. blocking issue 为零。

Git commit、push、PR 和远程 CI 属于 Delivery Gate，由用户、项目规则与 `dd-git-workflow` 决定。Delivery 失败必须如实记录，但不反向伪造节点产物未完成。

## 9. 上游上下文与子 skill 协议

父 skill 调用子 skill 时传递：

- 项目模式、宿主与工作环境；
- 已确认目标、平台、技术栈、范围和兼容义务；
- 当前有效产物路径与状态；
- 未解决的、仅属于该子 skill 的问题；
- 当前 review level 与 Git delivery policy。

子 skill：

- 必须消费上游事实；
- 不得重新询问已解决事实；
- 可询问缺失的阻塞输入；
- 可询问其产物特有的新决策；
- 发现上游冲突时返回 blocker，不在下游另写一套规则。

## 10. 审查与 Token 预算

三个语义视角始终保留：

1. 覆盖与范围；
2. 一致与正确；
3. 可验证与可观测。

执行强度：

| Review level | 默认执行方式 | 适用情况 |
|---|---|---|
| `low` | 主 Agent 一次完成三视角自检 | 机械迁移、链接修复、低风险格式变更 |
| `standard` | 一个独立 reviewer 覆盖三视角 | 普通文档产物和常规节点 |
| `high` | 三个方向 reviewer 并行，主 Agent 汇总 | Brownfield 基线、架构边界、兼容分类、高风险 UI/数据迁移 |

无子 Agent 能力时，用同一 Agent 的独立三轮检查替代，不降低检查项。任何级别发现 blocker 都必须修复并复验。禁止为了省 Token 跳过 lint、解析、链接、测试映射或状态一致性等确定性检查。

## 11. Brownfield 合同

Characterization Test 处置：

```text
PRESERVE                  → 可映射为保持现状的 AC
ADAPT                     → AC 写目标语义，不复制旧接口
REPLACE                   → 旧行为不进入目标 AC
KNOWN_DEFECT              → 禁止成为目标 AC
TOLERATED_COMPATIBILITY   → 明确兼容范围后才可进入 AC
REVIEW                    → 阻塞 Phase Contract
```

公开面拆分：

- Legacy Compatibility Surface：已有兼容承诺，只能通过明确决策缩减；
- Target Public Surface：新架构允许暴露的接口，可通过 Requirements + Architecture Review/ADR 新增。

质量策略：

- 已有违规建立可审计 baseline；
- 修改代码不得增加违规；
- 新代码遵守完整规范；
- CI 使用 ratchet，不要求 Bootstrap 当天清零全部历史债务。

## 12. 架构和技术验证状态

技术探针按风险触发：

- 存在会影响 Roadmap 或架构的未验证高风险假设时必需；
- 技术栈成熟且已有可靠证据时可跳过。

架构契约状态：

```text
Architecture Hypothesis
    → Technical Validation
    → provisional
    → Bootstrap approved baseline
    → First implementation evidence
    → frozen
```

Bootstrap 出口要求“足以约束首个 Feature 的 approved baseline”，不假装尚未经过实现验证的架构已经永久冻结。

## 13. Handoff

Greenfield 与 Brownfield 统一交给 `dd-feature-development-workflow`。Handoff 包含：

```text
Goal
Scope
Project Mode
Selected Feature/Phase
Required Reading
Relevant Files
Constraints
Acceptance Criteria or Requirements Seed
Verification
Out of Scope
Resolved Decisions
Open Non-blocking Items
```

Greenfield 默认没有 Phase Contract，由 Feature workflow 使用 Requirements Seed 进入 `dd-writing-specs`。Brownfield 必须携带 Baseline 与已批准 Phase Contract；Feature workflow 直接复用，不重新 grill 已确认内容。

## 14. Trae/Codex 宿主合同

通用决策：

- 优先使用宿主结构化询问；
- 没有结构化工具时使用含 2–4 个互斥选项的简短文本；
- 一次只问一个阻塞决策；
- happy path 不重复确认。

Trae 完成约束：

1. Exit Gate 与 Handoff 均完成后，禁止直接结束会话；
2. 必须使用 Trae 的结构化 ASK：
   - `结束本次任务`
   - `还有其他任务`
3. 选择“还有其他任务”时接收新任务并继续；
4. 选择“结束本次任务”后把状态更新为 `completed`，再输出最终摘要；
5. `dd-project-docs/ai-conventions` 必须把该规则写入项目 AI 入口与 Trae 薄适配器。

Codex 不强制无意义的结束确认；按当前任务完成后正常交付，除非项目规则另有要求。

## 15. 验证策略

实施后执行：

1. 对所有新增/修改 skill 运行 `quick_validate.py`；
2. 检查 YAML frontmatter、skill 名称、相对链接与引用文件存在性；
3. 检查 Markdown fence 平衡和 UTF-8；
4. 扫描并消除旧矛盾：
   - `>=1 个源文件即 brownfield`
   - 无条件严格 `0→1→...→9`
   - 节点完成必须依赖 `git log -1`
   - 所有检查无条件三子 Agent
   - Bootstrap 完成后 Trae 直接结束
5. 逐个核对 7 个 Bootstrap/Phase Contract baseline 场景；
6. 比较修改前后 `SKILL.md` 行数，确认核心入口显著瘦身；
7. 用 `git diff --check` 检查补丁卫生；
8. 检查 Git 暂存范围，避免混入无关文件。

## 16. 迁移与兼容

- 以当前工作区版本为源，不回退已存在的修改；
- 保留现有 skill 名称，避免破坏显式调用；
- 旧步骤编号只在迁移说明或测试背景中保留，不继续作为运行时状态主键；
- 子 skill 在无 Bootstrap 上游上下文时仍可独立触发，并执行自己的最小 Preflight；
- 新协议先由 Bootstrap 调用链采用，不强迫 bug-fix/refactor 工作流同步迁移；
- Trae 源 skill 完成验证后，再按现有迁移约定同步 Codex personal skill；本轮不自动覆盖 Codex 副本。

## 17. 已决策事项

1. 采用完整生态方案 3。
2. 新建 `dd-project-docs/phase-contract`。
3. Bootstrap 与 Feature workflow 使用统一 Handoff。
4. `SKILL.md` 采用 progressive disclosure，详细政策进入三份 reference。
5. 审查质量标准固定，执行强度按风险调整。
6. Trae 最终必须 ASK；Codex 不强制结束确认。
7. Brownfield 使用兼容义务判定和 lint ratchet。
8. Workflow Gate 与 Delivery Gate 分离。

