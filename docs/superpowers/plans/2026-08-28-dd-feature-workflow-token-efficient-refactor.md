# DD Feature 工作流低 Token 重构实现计划

> **面向 AI 代理的工作者：** 由主 Agent 按任务顺序调度 `luna-worker` 执行；Luna 只修改当前任务的 Write scope，不得自宣 Gate PASS。主 Agent 在每个任务后核对 diff、命令输出和停止条件。不要并行执行共享文件任务。

**目标：** 在不降低来源可信度、验证有效性、独立审查、UI 证据、exact-SHA CI 和 Delivery 授权边界的前提下，减少 `dd-feature-development-workflow` 的重复读取、重复字段和重复审查，并修复当前 Candidate/Documentation/Delivery 与共享 CI 的合同冲突。

**架构：** 保留十个可恢复 Stage 作为内部状态机，把对外质量语义收敛为五个 Gate；主 `SKILL.md` 只做路由，Stage 细节按需读取。Phase 只消费当前 requirement anchors 和全局约束，Final Candidate 在冻结基线上执行一次独立 A/B/C 审查并产出完整 spec gap。共享 Artifact Contract 采用“一份 source manifest + Task 引用”和“两块 verification + 四个不变量”。

**技术栈：** Markdown Skill 合同、Python 3 标准库 `unittest`、`rg`、`shasum`、Git 只读检查。

**计划状态：** `draft`

**执行授权：** `pending-user-approval`。本轮只批准写计划；不得据此修改 Skill、删除文件、commit、push、开 PR、merge 或调用外部审查。

---

## 1. 冻结决策

以下决策是本计划的实现边界；执行者不得自行换方案。

1. `state` 与 repository evidence 分开保留：state 只保存进度和引用，evidence 保存事实证明。
2. 保留 Stage Graph 用于恢复；五个 Gate 只做聚合命名，不替换 Stage。
3. Planning 完整读取 canonical spec；Phase 只读取当前 anchors、全局约束和真实 integration anchors；Final Candidate 再完整读取一次 canonical spec。
4. Final Candidate 的一次独立 `standard` A/B/C 审查同时交付代码/设计 findings 与 full-spec gap table；不再额外做第二次完整模型扫描。
5. 普通 Phase 执行确定性检查和紧凑 A/B/C 结果；命中共享风险触发器时才升级独立审查。
6. Documentation 在候选冻结前完成。Candidate Gate 只产生可交付候选，不推进目标分支；Delivery Gate 在确认和授权后推进同一 SHA。
7. source 的 Gate 身份为 `stable_id + path + digest + approval`；`version_label` 只作可选人类标签，不复制到每个 Task。
8. verification 可以存成 `plan + result` 两块，但 `coverage`、`run`、`bindings` 和 `validity` 四个语义必须存在；`validity` 每次都验证，不能只在异常时记录。
9. `delivery_authorization` 独立保留。内容批准、测试 PASS、Reviewer PASS 均不授权 Git 或外部动作。
10. exact candidate SHA、Full CI 与 same-SHA promote 是一个不可拆分不变量；任何候选后内容变化都会使旧审查和 CI 失效。
11. 不引入第二套 workflow state、run ledger、顶层 Skill 或自由关闭 tests/gap/review 的开关。
12. Token 降幅保持 `NOT_PROVEN`，直到固定模型、请求、允许文件、质量标准和重复次数后实测。

## 2. 五个 Gate 与 Stage 映射

```text
Source Gate
  Intake → Environment → Specification

Plan Gate
  Planning

Phase Gate
  Implementation × N

Candidate Gate
  Documentation → freeze candidate SHA
  → deterministic verification
  → one independent A/B/C review + full-spec gap
  → Full CI on exact SHA

Delivery Gate
  Confirmation → authorized same-SHA promote
  → Delivery → Closure
```

Gate 结果与 Delivery 状态分开持久化：Candidate 可以 `PASS`，而 Delivery 同时为 `not-required`、`not-authorized`、`pending` 或 `completed`。

## 3. Acceptance Criteria

| ID | 验收条件 |
|---|---|
| AC-01 | 主 `SKILL.md` 只包含触发/运行时调用、核心不变量、Stage/Gate 路由和红线；Bootstrap、state schema、legacy mapping 全部下沉。 |
| AC-02 | 每个 Stage reference 从主 `SKILL.md` 一层可达；进入一个 Stage 不要求读取不相关 Stage 的正文。 |
| AC-03 | Source manifest 只定义一次完整 source metadata；每个 Task 只写 `ref + anchors`，同时仍可机械检测 stale 和批准绑定。 |
| AC-04 | verification 只有 `plan` 与 `result` 两块，但 Gate 仍必须证明 coverage 完整、必需 runs PASS、bindings 匹配、validity=`valid`。 |
| AC-05 | Phase 不完整重读全部 spec；它验证 manifest digest，读取当前 anchors、全局约束和 `consumes`/integration anchors，并在合同漂移时回 Planning。 |
| AC-06 | 普通 Phase 无独立强审消耗；风险 Phase 按 `review-gate` 升级；每个 Phase 仍有确定性验证和 A/B/C 结论。 |
| AC-07 | Documentation 在候选冻结前完成；候选变化使 review/gap/CI 全部 stale。 |
| AC-08 | Candidate Gate 在同一冻结 SHA 上完成一次独立 `standard` A/B/C review、full-spec gap 和 Full CI，不更新目标分支。 |
| AC-09 | Delivery 只有在用户/项目策略明确授权后才推进 `candidate_sha`；推进 SHA 必须等于 review SHA 和 CI SHA。 |
| AC-10 | 共享 CI/Test Location 文档不含旧步骤号、Macim 名称、固定 workflow/scheme 或未授权强制 push；项目规则和项目脚本拥有项目特定命令。 |
| AC-11 | Bug/Refactor/Feature 调用者继续获得 exact-SHA CI、失败不伪装 PASS 和本地诊断不替代远程 Gate 的语义。 |
| AC-12 | 所有现行 baseline 使用 Stage 术语；新红/绿场景证明候选顺序、anchor 读取、compact verification 和 frozen review。 |
| AC-13 | 删除旧 reference 前，活跃路径引用扫描为零且用户明确批准精确删除清单；历史迁移文档不追改。 |
| AC-14 | 最终记录文件字节和实际加载集合的前后差异，但不得据此宣称固定 token 百分比。 |

## 4. Source Manifest

执行开始时必须重算下列 SHA-256；任一不匹配即 `BLOCKED_SOURCE_STALE`，先由主 Agent 重读差异并修订计划。

| Ref | 路径 | SHA-256 | 用途 |
|---|---|---|---|
| S01 | `dd-feature-development-workflow/SKILL.md` | `1aec4eb68e3aa1511339404a1ce49e8ef5298a6a0ed3c0ee3b67574338b0cc02` | 当前 Router、Stage Graph、state/handoff、Gate |
| S02 | `dd-feature-development-workflow/references/specification-and-planning.md` | `f66cbd601a38c2db35b3a9c07de4798dffab620151d0a9a733073549e53e8d5d` | Intake/Environment/Specification/Planning 原始正文 |
| S03 | `dd-feature-development-workflow/references/planning.md` | `6ab79f87c4045308ec63be36efc054620b3c42ae9c95e5ada6dc1eb4b09c0b50` | 弱模型计划包模板和粒度规则 |
| S04 | `dd-feature-development-workflow/references/implementation-and-verification.md` | `f35c601b9febe6f78ebf7203ce6aa82d601058f447b045db57959006a9b51fbc` | Phase、Local Gate、Candidate 原始正文 |
| S05 | `dd-feature-development-workflow/references/delivery-and-closure.md` | `8e6ea5b46f109be267db7ef189626bab7c302f89c4d5fa97e8390833e22667ea` | Documentation/Delivery/Closure 原始正文 |
| S06 | `dd-feature-development-workflow/references/planning-reviewer-prompt.md` | `e48509e5bfc1dc62eee080721263ee20cdfca563320f352d6fb26a904fec1d11` | 待退休的孤儿模板 |
| S07 | `dd-workflow-runtime/SKILL.md` | `baa42470305d0a72959806b186129e530a08291e0883d55e97e9c5fe76fd0052` | 共享 runtime 和 Delivery 授权优先级 |
| S08 | `dd-workflow-runtime/references/artifact-contract.md` | `b22d7c472af3a3ef00eec68e65860e0d9115c5eceb38789ffde3e51474f63cd7` | Source、执行包、verification 唯一属主 |
| S09 | `dd-workflow-runtime/references/review-gate.md` | `76f7e07970d250c7f9ed16ce9e0b6f403d8afa74d2baf7c7ec827c994ddc8665` | A/B/C、风险升级和冻结基线 |
| S10 | `dd-workflow-runtime/references/model-routing.md` | `d14e8b23b06d22dea5c45132ed2baab250d740e3250e50eb47ae7b576bf205ad` | 独立审查执行与 fail-closed 路由 |
| S11 | `dd-workflow-runtime/references/ci.md` | `10e3b18672398e09df6eda93eede8b9658664b897f79cc42222a2a3977a76bb2` | 当前共享 CI 合同 |
| S12 | `dd-workflow-runtime/references/test-location.md` | `cf65ef0c3b00362e6b466c5072534df73ac8799fdf33aa28479670d4af634413` | 当前测试位置合同 |
| S13 | `docs/migrations/2026-08-23-skill-consolidation.md` | `3b91e2784c9ae415f871f9fe8c9685a3088d5cf49e343490ad139bf3102822db` | 历史迁移边界；只读，不追改 |

## 5. 文件职责与精确范围

### 创建

- `dd-feature-development-workflow/references/state-and-handoff.md` — Bootstrap Handoff、Feature state、legacy mapping、恢复补充。
- `dd-feature-development-workflow/references/intake-and-environment.md` — Intake 与 Environment。
- `dd-feature-development-workflow/references/specification.md` — Specification 调用合同与 Gate。
- `dd-feature-development-workflow/references/planning-stage.md` — Planning Stage、Phase 拆分和 `planning.md` 调用合同。
- `dd-feature-development-workflow/references/implementation.md` — Phase Loop、TDD、Local Gate、风险 Smoke/Review。
- `dd-feature-development-workflow/references/documentation.md` — 候选冻结前的 impact-based 文档同步。
- `dd-feature-development-workflow/references/candidate.md` — frozen candidate、独立 review/full gap、Full CI。
- `dd-workflow-runtime/references/ci-xcode.md` — 仅在 Xcode 项目需要本地诊断时读取的通用 adapter；不含项目名或固定 scheme。
- `dd-feature-development-workflow/tests/test_feature_workflow_contracts.py` — Feature 文档结构与合同断言。
- `dd-workflow-runtime/tests/test_ci_contracts.py` — CI/Test Location 通用性和授权断言。
- `dd-feature-development-workflow/tests/baseline-7-candidate-before-delivery.md` — 候选顺序压力场景。
- `dd-feature-development-workflow/tests/baseline-8-phase-anchor-loading.md` — Phase 选择性读取与 drift 场景。
- `dd-feature-development-workflow/tests/baseline-9-compact-verification.md` — compact schema 下 stale evidence 场景。
- `dd-feature-development-workflow/tests/baseline-10-frozen-candidate-review.md` — 独立审查冻结基线场景。
- `dd-feature-development-workflow/tests/evidence/2026-08-28-token-efficient-refactor-red.md` — 实际红测输出；禁止预填或伪造。
- `dd-feature-development-workflow/tests/evidence/2026-08-28-token-efficient-refactor-green.md` — 实际绿测输出；禁止预填或伪造。

### 修改

- `dd-feature-development-workflow/SKILL.md`
- `dd-feature-development-workflow/references/planning.md`
- `dd-feature-development-workflow/references/delivery-and-closure.md`
- `dd-feature-development-workflow/tests/baseline-1-state-not-updated.md`
- `dd-feature-development-workflow/tests/baseline-2-state-deleted-before-merge.md`
- `dd-feature-development-workflow/tests/baseline-3-trae-completion.md`
- `dd-feature-development-workflow/tests/baseline-4-planning-phase-split.md`
- `dd-feature-development-workflow/tests/baseline-5-original-source-and-evidence.md`
- `dd-feature-development-workflow/tests/verify-scenario-feature-dev.md`
- `dd-workflow-runtime/references/artifact-contract.md`
- `dd-workflow-runtime/references/ci.md`
- `dd-workflow-runtime/references/test-location.md`
- `dd-workflow-runtime/tests/dd-shared-ci/baseline-1-xcode-signing.md`
- `dd-ai-refactor-workflow/SKILL.md`
- `dd-ai-refactor-workflow/references/verification-and-delivery.md`

### 精确删除清单：另需用户授权

- `dd-feature-development-workflow/references/specification-and-planning.md`
- `dd-feature-development-workflow/references/implementation-and-verification.md`
- `dd-feature-development-workflow/references/planning-reviewer-prompt.md`

如果删除未获授权，执行者必须保留这三份文件、在文件首行标记 `retired-reference: not-routed`，并报告未完成的清理；不得扩大删除范围。

### 明确不修改

- `docs/superpowers/plans/2026-08-28-dd-feature-workflow-token-efficient-refactor.md` — 本计划是执行输入；执行阶段只读并保留。
- `docs/migrations/2026-08-23-skill-consolidation.md` 及其他历史 plan/spec。
- `dd-workflow-runtime/references/model-routing.md` 和 review adapter/路由脚本。
- 任何项目仓库的 CI workflow、scheme、证书、runner 或真实数据。
- Git 历史、远端分支、PR 和 worktree。

## 6. 执行协议

1. 主 Agent 一次只派发一个任务给 `luna-worker`，明确本任务文件所有权。
2. Luna 必须知道自己不是仓库中唯一执行者；不得回退或覆盖任务范围外的用户改动。
3. 每个任务返回：修改文件、关键 diff、实际命令、退出码、未验证项和 blocker。
4. 主 Agent 以冻结 diff 验收；不接受“已完成”“看起来正确”代替命令证据。
5. 任一来源 hash 变化、出现范围外 active consumer、需修改产品语义、缺删除/Git/外部授权时立即停止。
6. 本计划不授权 commit。计划中的每个 Task 的 Delivery authorization 均为 `not-authorized`。

### 弱模型 Context Loading Contract

主 Agent 派发时只发送：§1 中与当前任务有关的冻结决策、当前任务引用的 AC、对应 Source Manifest 行、当前 Task 正文、允许读取/写入的精确文件。不得让 Luna 预加载整份计划、其他 Task、历史 migration 或未引用的 Stage reference。跨 Task 事实由主 Agent 通过已验收产物和 digest 传递，不靠 Luna 的会话记忆。

---

### 任务 0：Preflight、来源新鲜度与基线清单

**Source refs：** S01–S13

**Consumes：** 当前 `develop` worktree、Source Manifest、用户批准后的计划。

**Produces：** 可复验的 branch/HEAD/status、source hashes、现有文件字节、active-reference inventory；不修改文件。

**Write scope：** 无。

- [ ] **步骤 1：验证仓库与工作区**

```bash
test "$(git branch --show-current)" = "develop"
test "$(git rev-parse HEAD)" = "93d9a272659f264ec9d7c3404e5437d6b2ac7b7e"
git status --short
test -z "$(git status --porcelain | grep -v '^?? docs/superpowers/plans/2026-08-28-dd-feature-workflow-token-efficient-refactor.md$')"
```

预期：除本计划文件外无工作区变化，全部断言退出码 0。HEAD 或其他状态变化时不得机械继续。

- [ ] **步骤 2：重算 Source Manifest**

```bash
shasum -a 256 \
  dd-feature-development-workflow/SKILL.md \
  dd-feature-development-workflow/references/specification-and-planning.md \
  dd-feature-development-workflow/references/planning.md \
  dd-feature-development-workflow/references/implementation-and-verification.md \
  dd-feature-development-workflow/references/delivery-and-closure.md \
  dd-feature-development-workflow/references/planning-reviewer-prompt.md \
  dd-workflow-runtime/SKILL.md \
  dd-workflow-runtime/references/artifact-contract.md \
  dd-workflow-runtime/references/review-gate.md \
  dd-workflow-runtime/references/model-routing.md \
  dd-workflow-runtime/references/ci.md \
  dd-workflow-runtime/references/test-location.md \
  docs/migrations/2026-08-23-skill-consolidation.md
```

预期：逐项等于 §4；不等则 `BLOCKED_SOURCE_STALE`。

- [ ] **步骤 3：记录实际规模和引用者**

```bash
wc -c dd-feature-development-workflow/SKILL.md \
  dd-feature-development-workflow/references/*.md \
  dd-workflow-runtime/references/ci.md \
  dd-workflow-runtime/references/test-location.md
rg -n "specification-and-planning|implementation-and-verification|planning-reviewer-prompt|dd-workflow-runtime/(ci|test-location)|references/(ci|test-location)\.md" \
  dd-* docs --glob '*.md'
```

预期：保存原始输出供任务 7 对比；不得把字节变化换算成已证明的 token 降幅。

**Verification：** 上述三组命令均实际运行且输出归档到主 Agent 任务记录。

**Stop conditions：** 非预期 branch/HEAD、overlap dirty files、任一 hash 变化或发现本计划未列出的 active consumer。

**Delivery authorization：** `not-authorized`；禁止任何写入和 Git 外部动作。

---

### 任务 1：建立失败测试与弱模型红测证据

**Source refs：** S01–S12

**Consumes：** 当前 Stage/Gate、artifact、review 和 CI 合同。

**Produces：** 四个压力场景、两个 Python 合同测试、真实红测证据。

**Write scope：** 仅创建 §5 中两个 `test_*.py`、四个 `baseline-*.md` 和红测 evidence 文件。

- [ ] **步骤 1：创建 Feature 合同测试**

使用 Python `unittest` 和 `pathlib`，测试方法固定为：

```text
test_stage_order_documentation_before_candidate
test_candidate_does_not_promote_target
test_delivery_promotes_exact_candidate_sha
test_phase_reads_anchors_not_full_specs
test_candidate_requires_frozen_standard_review_and_full_gap
test_compact_verification_keeps_coverage_run_bindings_validity
test_main_skill_routes_every_reference_directly
test_retired_references_have_no_active_links
```

每个失败信息必须指出文件、缺失/禁用的合同和 AC ID；不得只返回布尔值。

- [ ] **步骤 2：创建 CI 合同测试**

固定断言：

```text
ci.md 和 test-location.md 不出现 feature-dev/bug-fix 旧步骤号
ci.md 和 test-location.md 不出现 Macim、MacimApp、macos-ci.yml、macos-xcuitest.yml
ci.md 明确 external Git action requires delivery_authorization
ci.md 明确 CI evidence binds exact SHA
ci.md 明确 local diagnosis cannot close required remote CI Gate
ci-xcode.md 存在且优先项目文档/项目脚本，不固定 workspace/project/scheme
dd-ai-refactor-workflow 不再无条件要求每个 Commit push
```

- [ ] **步骤 3：创建四个压力场景**

每个场景包含时间、权威或沉没成本压力，并冻结以下正确行为：

1. `baseline-7`：候选 CI 已绿，但 Documentation 后产生新 commit；必须使候选 stale，而不是直接交付。
2. `baseline-8`：Phase package digest 有效，但前一 Phase 改动了 `consumes` anchor；必须打开真实 anchor，合同失效则回 Planning。
3. `baseline-9`：run 为 PASS，但 candidate SHA 与 evidence binding 不同；即使没有 exception 也必须判 `stale`。
4. `baseline-10`：强审 PASS 后 diff 改变；旧审查和 full gap 必须失效并重新冻结。

- [ ] **步骤 4：运行确定性红测**

```bash
python3 -m unittest \
  dd-feature-development-workflow/tests/test_feature_workflow_contracts.py \
  dd-workflow-runtime/tests/test_ci_contracts.py -v
```

预期：非零退出，失败至少覆盖 AC-03、AC-04、AC-05、AC-07、AC-08、AC-09、AC-10。

- [ ] **步骤 5：运行真实弱模型红测**

主 Agent 向全新 `luna-worker` 分别提供四个 scenario，但不提供拟修改规则；逐字记录模型选择、理由、模型/日期和结果到红测 evidence。若无法取得全新弱模型实例，标记 `BLOCKED_EVAL_UNAVAILABLE`，不得编造输出或先改 Skill。

**Verification：** Python tests 按预期失败；四个实际模型输出均有证据，或任务明确 BLOCKED。

**Stop conditions：** 测试意外全绿、断言依赖计划中的未来文本而非行为合同、红测输出非真实运行。

**Delivery authorization：** `not-authorized`。

---

### 任务 2：压缩 Artifact Contract，保留四个验证不变量

**Source refs：** S03、S08

**Consumes：** AC-03、AC-04，任务 1 红测。

**Produces：** 共享 source manifest/task refs 合同和 compact verification schema；Planning 模板同步。

**Write scope：**

- 修改 `dd-workflow-runtime/references/artifact-contract.md`
- 修改 `dd-feature-development-workflow/references/planning.md`
- 修改 `dd-feature-development-workflow/tests/baseline-5-original-source-and-evidence.md`
- 修改任务 1 创建的 Feature contract test

- [ ] **步骤 1：定义唯一 source manifest**

合同必须使用以下等价结构；字段名不得另造同义词：

```yaml
source_manifest:
  SPEC-REQ:
    stable_id: SPEC-REQ
    path: docs/specs/feature/requirements.md
    digest: sha256:current-content
    approval:
      status: approved
      authority: user-or-project-role
      decided_at: 2026-08-28
      evidence_ref: repository-or-thread-reference
    version_label: v1.0  # optional, not a stale Gate input

task:
  sources:
    - ref: SPEC-REQ
      anchors: [FR-001, AC-001]
```

规则：完整 metadata 在一个 Phase plan 中只出现一次；Task 不复制 path/version/digest/approval。执行前同时验证 manifest digest、source digest 和 approval→digest 绑定。

- [ ] **步骤 2：定义两块 verification schema**

```yaml
verification:
  plan:
    requirement_refs: [AC-001]
    checks:
      - id: CHECK-001
        command: exact-command-or-manual-step
        oracle: exact-pass-condition
  result:
    coverage:
      AC-001: covered
    runs:
      - check_id: CHECK-001
        outcome: PASS
        evidence_ref: repository-relative-evidence
    bindings:
      source_manifest_digest: sha256:current-manifest
      implementation_digest: git-or-file-digest
      environment: recorded-environment-id
    validity: valid
```

Gate 规则：必需 coverage 无 `partial|missing|unverified`；必需 run 全部 PASS；bindings 与当前输入一致；validity 必须为 `valid`。非 `valid` 时才追加 `validity_exception`，但 exception 不能替代 validity 检查。

- [ ] **步骤 3：同步 Planning 模板**

删除 Task 级重复 `路径、ID、版本、内容指纹、approval`，在每个 Phase plan 头部增加一次 `source_manifest`，Task 使用 `sources: [{ref, anchors}]`。保留 `consumes`、`produces`、write scope、steps、verification、stop conditions 和 delivery authorization。

- [ ] **步骤 4：运行定向测试和消费者扫描**

```bash
python3 -m unittest dd-feature-development-workflow/tests/test_feature_workflow_contracts.py -v
rg -n "verification_plan|existing_coverage|run_result|evidence_validity|逐项路径、稳定 ID、版本" \
  dd-* docs --glob '*.md'
```

预期：compact-schema 相关测试通过；扫描只允许历史文档或尚待任务 4 迁移的当前 Feature reference。发现其他 active consumer 即停止扩 scope。

**Verification：** AC-03/AC-04 通过；旧四层字段不再作为四份并列 artifact 的现行合同。

**Stop conditions：** 需要修改未列入 Write scope 的 active workflow、approval 不再绑定 digest、normal path 不检查 validity。

**Delivery authorization：** `not-authorized`。

---

### 任务 3：按 Stage 拆 reference，暂不删除旧文件

**Source refs：** S01–S06、S13

**Consumes：** 当前四份 Feature references、历史迁移边界。

**Produces：** 七份单一职责 Stage reference；旧文件暂时保留作为对照。

**Write scope：** 仅创建 §5 中七份 Feature reference；不得修改或删除旧 reference。

- [ ] **步骤 1：迁移 state/handoff**

把 Bootstrap Handoff、Feature state、legacy `current_step` mapping 和 evidence-first recovery 移入 `state-and-handoff.md`。文件不得复制 runtime 通用 state 字段，只保留 Feature 增量。

- [ ] **步骤 2：迁移前四个 Stage**

`intake-and-environment.md` 只拥有 Intake/Environment；`specification.md` 只拥有 Specification；`planning-stage.md` 只拥有 Phase 档位、`phase_list` 和对 `planning.md` 的调用合同。

- [ ] **步骤 3：迁移实现与候选前文档**

`implementation.md` 只拥有 Phase/TDD/Local Gate/UI Smoke/Phase risk review；`documentation.md` 只拥有 impact-based 文档同步；`candidate.md` 只拥有候选冻结、独立 review/full gap、Full CI 和 invalidation。

- [ ] **步骤 4：验证无语义丢失**

```bash
for file in \
  state-and-handoff.md intake-and-environment.md specification.md planning-stage.md \
  implementation.md documentation.md candidate.md; do
  test -s "dd-feature-development-workflow/references/$file" || exit 1
done
rg -n "Bootstrap Handoff|Feature State|Intake|Environment|Specification|Planning|Phase Loop|TDD|Local Gate|Documentation|Final Candidate" \
  dd-feature-development-workflow/references
```

预期：每个主题在新文件中有且只有一个属主；旧文件仅作为待退休对照造成的重复必须列明，不能被误判为新结构重复。

**Verification：** 新文件完整、职责不重叠、历史迁移文档未改。

**Stop conditions：** 迁移时需要改变产品/授权语义，或发现正文唯一事实无法判断属主。

**Delivery authorization：** `not-authorized`；旧文件删除未获授权。

---

### 任务 4：重写 Router 与 Feature Gate 语义

**Source refs：** S01、S07–S10

**Consumes：** 任务 2 schema 和任务 3 references。

**Produces：** 新 Stage order、五 Gate 聚合、Phase anchor/drift 检查、Candidate-ready 与 same-SHA Delivery。

**Write scope：**

- 修改 `dd-feature-development-workflow/SKILL.md`
- 修改任务 3 创建的七份 reference
- 修改 `dd-feature-development-workflow/references/delivery-and-closure.md`
- 修改 `dd-feature-development-workflow/references/planning.md`

- [ ] **步骤 1：把主 Skill 缩为 Router**

主文件保留：目标/不适用、runtime 调用、十二条以内核心不变量、Stage/Gate 图、每 Stage 一行路由、通用红线。删除内联 Handoff、state YAML、legacy mapping 和重复 Stage 说明，并从主文件直接链接全部现行 reference。

- [ ] **步骤 2：修正 Stage 顺序和 Gate 输出**

固定顺序：

```text
intake → environment → specification → planning → implementation
→ documentation → final-candidate → confirmation → delivery → closure
```

Candidate 输出 `candidate_sha`、`candidate_review`、`full_spec_gap`、`full_ci_run`、`candidate_ready=true`；不得在 Candidate 更新 develop/main。Confirmation 只决定交付或回退。Delivery 只能推进同一 `candidate_sha`。

- [ ] **步骤 3：实现 Phase 选择性读取与 anchor drift**

每个 Phase：验证 package/manifest/source digests；读取 Task anchors、所有声明为 global 的约束、Out of Scope、失败路径；打开 `consumes` 和 integration anchors。实现细节漂移且合同仍成立可在当前 scope 适配；接口/架构/规格假设失效则 package stale，回 Planning。删除每 Phase 完整重读全部原始规格的要求。

- [ ] **步骤 4：接入紧凑 Phase review**

Local Gate 先执行 lint/build/typecheck/定向测试/映射检查，再保存 A/B/C 三个结果引用，不写第二篇长 self-review。命中 `review-gate` 触发器时按现有 level/routing 升级；普通 Phase 独立强审调用次数为零。

- [ ] **步骤 5：定义 Candidate Assurance**

候选必须包含已同步 Documentation。冻结后先确定性验证，再用 `review_level=standard`、`review_execution=auto` 审查同一 SHA；Reviewer 输入为 canonical spec、frozen diff、Phase verification refs，输出 A/B/C findings 和逐 requirement/AC 的 full gap table。无安全独立路线且未获外部授权时 `BLOCKED`，不得 inline 降级为独立 PASS。任何修复重新冻结并重做 review/gap/CI。

- [ ] **步骤 6：定义 Delivery exact-SHA invariant**

Delivery 检查 confirmation、action-specific authorization 和 `review_sha == gap_sha == ci_sha == candidate_sha`，然后才允许 promote/push/merge。候选后任何内容变化返回 Documentation/Final Candidate。

- [ ] **步骤 7：运行 Feature tests**

```bash
python3 -m unittest dd-feature-development-workflow/tests/test_feature_workflow_contracts.py -v
git diff --check
```

预期：除 retired-link 和尚待任务 5 CI 的断言外，其余 Feature tests PASS。

**Verification：** AC-01、AC-02、AC-05–AC-09 通过；主 Skill 与 reference 没有重复定义同一合同。

**Stop conditions：** Reviewer 被允许静默 inline 降级；Candidate 仍先 promote；Documentation 后仍可沿用旧 candidate；Delivery 授权被并入质量 PASS。

**Delivery authorization：** `not-authorized`。

---

### 任务 5：清理共享 CI/Test Location 合同

**Source refs：** S07、S11、S12

**Consumes：** AC-10/AC-11、任务 1 CI red tests。

**Produces：** 通用 CI hub、通用 Test Location 决策、按需 Xcode adapter、Refactor 调用者授权修正。

**Write scope：**

- 修改 `dd-workflow-runtime/references/ci.md`
- 修改 `dd-workflow-runtime/references/test-location.md`
- 创建 `dd-workflow-runtime/references/ci-xcode.md`
- 修改 `dd-workflow-runtime/tests/dd-shared-ci/baseline-1-xcode-signing.md`
- 修改任务 1 创建的 `dd-workflow-runtime/tests/test_ci_contracts.py`
- 修改 `dd-ai-refactor-workflow/SKILL.md`
- 修改 `dd-ai-refactor-workflow/references/verification-and-delivery.md`

- [ ] **步骤 1：明确唯一职责**

`test-location.md` 只决定本地/远端/不可执行和授权 blocker；`ci.md` 只拥有 exact-SHA run discovery/trigger/wait/result 语义；`ci-xcode.md` 只拥有 Xcode 本地诊断 adapter。不得在三处重复项目命令。

- [ ] **步骤 2：重写通用 CI invariants**

保留：精确 SHA、运行中不重复触发、失败不伪装 PASS、本地复现只诊断、基础设施 blocker 有证据。删除：旧 Feature/Bug 步骤号、Macim 名称、固定 workflow、无授权强制 push、固定 sleep 查 run。需要 push 才能触发 CI 时，先检查 action-specific `delivery_authorization`；未授权即返回 blocker。

- [ ] **步骤 3：建立通用 Xcode adapter**

优先使用项目 `AGENTS.md`/项目脚本；缺少项目命令时使用 `xcodebuild -list` 和 `-showBuildSettings` 发现 workspace/project、scheme 与签名设置。禁止 `head -1` 猜多 target 配置，禁止固定 app/scheme/workflow 名。无法唯一解析时 ASK/BLOCKED，不自行选择。

- [ ] **步骤 4：修正 Refactor 调用者**

把“每个 Commit 后 push”改为“每个逻辑批次完成确定性验证；只有 delivery authorization 允许时 push 并取得同 SHA CI。必需远端 CI 未授权时停在 Delivery 边界”。保留 Characterization Test 覆盖和远端 CI 质量要求。

- [ ] **步骤 5：运行共享测试和消费者扫描**

```bash
python3 -m unittest dd-workflow-runtime/tests/test_ci_contracts.py -v
python3 -m unittest discover -s dd-workflow-runtime/tests -p 'test_*.py' -v
rg -n "1\.2\.5|4\.5b|5\.5|8\.2\.1|Macim|MacimApp|macos-ci\.yml|macos-xcuitest\.yml|每个 Commit 后.*push" \
  dd-workflow-runtime dd-ai-refactor-workflow --glob '*.md'
```

预期：tests PASS；扫描只允许 baseline 的“旧行为”引用，现行 contract 为零。

**Verification：** AC-10/AC-11 通过；Bug/Feature/Refactor 的引用仍可解析。

**Stop conditions：** 需要修改真实项目 CI；本地验证被允许替代必需远程 Gate；无授权 push 仍存在；多 target Xcode 被猜测。

**Delivery authorization：** `not-authorized`。

---

### 任务 6：迁移旧测试、切断旧路由并执行精确清理 Gate

**Source refs：** S01–S06、S13

**Consumes：** 任务 3–5 的 green contracts。

**Produces：** 现行 Stage 测试、零 active legacy links、经授权时删除三份旧 reference。

**Write scope：** §5“修改”中的 Feature baseline/verify 文件；`dd-feature-development-workflow/SKILL.md`；精确删除清单仅在本任务取得授权后可写。

- [ ] **步骤 1：更新旧 baseline 术语**

把步骤 0–9、`9.1-merging` 等旧模型替换为 `current_stage`、`current_phase`、`*_in_progress` 和 evidence-first recovery。保留 baseline 的原始失败事实，不改写成从未发生过。

- [ ] **步骤 2：切断 active legacy links**

```bash
rg -n "specification-and-planning|implementation-and-verification|planning-reviewer-prompt" \
  dd-feature-development-workflow --glob '*.md'
```

预期：除旧文件自身、测试中明确标注的历史字符串外，active Router/reference 为零。

- [ ] **步骤 3：请求精确删除授权**

向用户列出 §5 的三条路径和步骤 2 的零引用证据。只有用户明确同意这三条路径后才使用 `apply_patch` 删除；不得扩大为目录清理。

- [ ] **步骤 4：未授权路径**

若用户未授权，保留文件并在首行加 `retired-reference: not-routed`；状态记 `cleanup_pending_authorization`。这不影响新 Router Gate，但 Closure 不得声称清理完成。

- [ ] **步骤 5：运行所有 Feature tests**

```bash
python3 -m unittest dd-feature-development-workflow/tests/test_feature_workflow_contracts.py -v
rg -n "步骤 (0|1|2|3|4|5|6|7|8|9)(\.|：| )|9\.1-merging" \
  dd-feature-development-workflow/tests --glob '*.md'
git diff --check
```

预期：合同测试 PASS；现行预期不再依赖旧步骤号，历史失败引用须有明确 `historical` 标签。

**Verification：** AC-12/AC-13 通过或清理明确 `pending_authorization`。

**Stop conditions：** active link 非零、用户只给模糊“清理一下”、历史 baseline 被删除或伪造。

**Delivery authorization：** 文档修改 `not-authorized-for-git`；三文件删除 `pending-exact-approval`。

---

### 任务 7：完整验证、实际绿测与 Plan Completion Receipt

**Source refs：** 全部

**Consumes：** 所有实现任务结果。

**Produces：** 冻结 diff、确定性验证、真实弱模型绿测、byte/loading 对比、未证明项和 Completion Receipt。

**Write scope：** 只允许补写绿测 evidence；发现实现缺陷时返回对应任务，不在本任务临时扩 scope。

- [ ] **步骤 1：冻结允许文件集合**

```bash
git diff --name-only | sort
git status --short
```

预期：仅出现 §5 的创建/修改文件、本计划文件，以及经批准删除的精确三文件。其他路径即 `BLOCKED_SCOPE_DRIFT`。

- [ ] **步骤 2：运行确定性全套验证**

```bash
python3 -m unittest dd-feature-development-workflow/tests/test_feature_workflow_contracts.py -v
python3 -m unittest dd-workflow-runtime/tests/test_ci_contracts.py -v
python3 -m unittest discover -s dd-workflow-runtime/tests -p 'test_*.py' -v
python3 dd-workflow-runtime/agents/validate-bindings.py
python3 dd-workflow-runtime/agents/validate-review-routing.py
git diff --check
```

预期：全部退出码 0。未实际运行的检查不得标 PASS。

- [ ] **步骤 3：运行链接、重复和红线扫描**

```bash
rg -n "2–5 分钟|四层验证证据|完整读取该包引用的批准原始规格|每个 Commit 后.*push|Macim|MacimApp" \
  dd-feature-development-workflow dd-workflow-runtime dd-ai-refactor-workflow --glob '*.md'
rg -n "specification-and-planning|implementation-and-verification|planning-reviewer-prompt" \
  dd-feature-development-workflow --glob '*.md'
```

预期：现行合同命中为零；baseline 中的历史引用必须明确标为 historical。

- [ ] **步骤 4：运行真实弱模型绿测**

用与任务 1 相同的四个 scenario、全新 `luna-worker` 和相同输入范围，只增加新 Skill/reference。逐字记录输出、模型/日期、读取文件和 PASS/FAIL 到 green evidence。四场景必须全部满足各自成功标准；失败则返回拥有该合同的任务修复并重跑，不得只改 evidence。

- [ ] **步骤 5：记录规模与实际加载集合**

重复任务 0 的 `wc -c`；分别记录 Planning、普通 Phase、Candidate、Xcode CI 场景需要读取的文件集合和总字节。输出只写观察值：

```text
main_skill_bytes_before / after
planning_loaded_bytes_before / after
phase_loaded_bytes_before / after
candidate_loaded_bytes_before / after
xcode_ci_loaded_bytes_before / after
token_saving_claim: NOT_PROVEN
```

- [ ] **步骤 6：主 Agent 做最终 A/B/C 验收**

A：AC-01–AC-14、IN/OUT 和未授权项是否完整；B：Stage/Gate/schema/CI 合同是否一致；C：所有 PASS 是否有命令或真实模型 evidence。若拟发往外部 ChatGPT，先展示精确 outbound context 并取得授权；未执行则记录 `EXTERNAL_REVIEW_NOT_EXECUTED`，不得称已外审。

- [ ] **步骤 7：写 Completion Receipt 并停止**

Receipt 包含 source HEAD、diff 文件清单、测试命令/退出码、绿测 evidence、删除授权状态、Git Delivery 状态和下一安全动作。不得 commit、push、PR 或 merge。

**Verification：** AC-01–AC-14 全部有 evidence；所有未执行项明确列出。

**Stop conditions：** 任一测试失败、绿测非全 PASS、diff 越界、source 变化、独立审查被误报、删除/Git 未授权。

**Delivery authorization：** `not-authorized`；完成后停在用户确认 Gate。

## 7. 执行顺序与依赖

```text
Task 0 Preflight
  ↓
Task 1 Red tests
  ↓
Task 2 Artifact schema
  ↓
Task 3 Reference split
  ↓
Task 4 Feature semantics
  ↓
Task 5 CI/Test Location
  ↓
Task 6 Legacy migration / authorized cleanup
  ↓
Task 7 Full validation and green evidence
```

任何 Task BLOCKED 时停止；不得跳到后续任务用下游修改掩盖上游合同缺失。

## 8. Plan Gate

计划获用户确认前：

- `package_review=draft`
- `execution_authorization=pending-user-approval`
- `deletion_authorization=pending-exact-approval`
- `git_delivery=not-authorized`
- `external_review=not-authorized`

用户确认本计划后，主 Agent 才能从 Task 0 开始并调度弱模型；确认计划不自动授权三文件删除或任何 Git/外部动作。
