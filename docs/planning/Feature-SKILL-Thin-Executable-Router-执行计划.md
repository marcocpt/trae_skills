# 执行计划：dd-feature-development-workflow 主 SKILL.md 重构为 Thin Executable Router

> **执行前提**：本计划已由强模型于 2026-08-29 完成仓库事实核查（主 SKILL.md、9 个 feature reference、runtime 合同、24+164 项合同测试均基线全绿）。执行时**不需要重新调查仓库**，直接按本计划修改、跑测试、看差异。若执行中发现与本计划描述不符的仓库事实，停止并报告，不要自行改设计。

---

## 0. 范围

- 本任务**只修改** `dd-feature-development-workflow/SKILL.md`。
- 只有当防重复检查（第十一节）或验证（第十二节）发现确属本任务的问题时，才允许触碰对应 reference，且必须在最终报告中单独说明原因。
- 禁止重新设计工作流；禁止顺手做与本任务无关的重构。
- 运行时 YAML 调用块（`workflow_type`、`required_exit_stages`、`delivery_policy` 等字段）**原位保留，不改内容**；Gate/Stage 图的 Stage 顺序与"五个对外 Gate 聚合十个 Stage"的语义不得改动（措辞可微调）。
- **同步改写现有 `## 目标` 中"主文件只做路由"的旧表述**：修改后主文件的自我定位是——主文件拥有整体执行叙事（目标、工作流概览、Stage 路由）与跨 Stage 红线，reference 拥有各 Stage 详细规则。不得让"只做路由"的旧句与新结构并存。

## 一、目标

当前 `dd-feature-development-workflow/SKILL.md` 为了节省 token 和渐进式加载，已经被压缩成偏"路由器"的形式，但抽象程度过高：第一次阅读时能看到很多 Stage、Gate、状态和术语，却不能快速理解"这个工作流实际要做什么"。

本次重构目标是：

> 将当前的"Thin Router"调整为"Thin Executable Router"：
> 主 `SKILL.md` 负责清楚说明"做什么、按什么顺序、每一步得到什么"；reference 继续负责"具体怎么做"。

必须在**保持现有质量门禁和单一事实源的前提下**提高可读性，不能把已下沉的详细规则重新复制回主文件。

## 二、必须保持不变的架构

以下现有能力不得删除、降级或改语义：

1. durable state / 状态恢复；
2. Bootstrap Handoff 已解决事实继承；
3. approved specification → planning → TDD；
4. AC → Task → Test/Evidence 追溯；
5. 每个 Phase 的 Local Gate；
6. 基于风险的强模型审查；
7. Documentation 在最终候选冻结之前完成；
8. frozen candidate SHA；
9. 独立 Reviewer；
10. Final Candidate 的完整规格缺口检查；
11. exact-SHA Full CI；
12. Candidate Gate 不推进目标分支；
13. Delivery 只能推进同一个 `candidate_sha`；
14. Workflow Gate 与 Git/外部动作授权分离；
15. 用户可见行为必须有用户可见证据；
16. progressive disclosure：Stage 详细规则按需读取 reference；
17. Trae / Codex 的 Host Close 语义保持不变；
18. 不新增第二套状态系统、ledger、Phase 0~6 或其他平行工作流。

不要为了"更容易读"把 reference 的 schema、模板、异常分支、恢复细节、CI 命令等重新复制到主 `SKILL.md`。

## 三、主文件要解决的可读性问题（可读性标准）

不以固定行数作为成功标准。改为两级可读性标准：

1. Agent 读完"目标 + 工作流概览"后，应能回答：
   - 这个 Skill 最终完成什么；
   - Feature 从需求到交付的大致顺序；
   - 哪些步骤负责规格、计划、实现、验证和交付。
2. Agent 读完 Stage 路由表后，应能回答：
   - 当前 Stage 实际要做什么；
   - 该 Stage 的完成标志是什么；
   - 需要打开哪个 reference 获取详细规则。

不得为了把内容压进某个固定行数而：压缩必要语义；调整内容顺序迎合数字；把 reference 详细规则复制回主文件。

当前文件的主要问题不是长度，而是缺少"执行叙事"：12 条不变量多为抽象英文短语，Stage 表只有"读取 | Gate 概要"，第一次阅读无法回答上述问题。

## 四、新增"工作流怎么运行"章节

在"目标/不适用"之后、"运行时"之前，增加一个非常简洁的 Happy Path / 工作流概览。语义如下：

1. 收集并确认 Feature 需求，复用已有 Handoff 和已解决事实；
2. 固定工作环境并确认基线；
3. 调用 `dd-writing-specs` 生成并批准 Requirements、Design、Test Matrix，UI 功能按需包含 Visual；
4. 从已批准规格拆出 Phase 和可执行 Task；
5. 按 Phase → Task → TDD 实现，每个 Phase 必须通过 Local Gate；
6. 根据真实实现同步受影响文档；
7. 冻结最终候选 SHA；
8. 对同一个 SHA 做确定性验证、独立审查、完整规格缺口检查和完整 CI；
9. 确认阶段决定继续交付还是回退；继续交付时仅按既有动作级授权推进同一个已验证候选 SHA，缺少所需授权时停在对应动作边界并保留证据。授权检查发生在每个 Git／远端动作边界（包括冻结候选阶段的分支 push），不是只在最后一步；
10. 完成交付、清理、状态收尾和 Host Close。

要求：

- 只写 8~12 行；
- 不加入 schema；
- 不重复 reference 中的详细规则；
- 中文表达优先，只有实际代码字段名、Skill 名、文件名等保留英文；
- **不要在此提前使用英文 Stage 名 token**（原因见第十二节测试注意事项）；
- **授权措辞遵守 `artifact-source-and-packet.md` 合同**：`delivery_authorization.status` 只取 `authorized | not-required | not-authorized | pending`，只有 `authorized` 明确列出的动作可执行，`pending`／缺字段在动作边界 `BLOCKED`；概览里不枚举这套状态机（详细语义在合同），也不要把"尚未决定"（`pending`）写成"明确禁止"（`not-authorized`）。

## 五、重写 Stage 路由表，使其描述"实际动作"

表头从 `Stage | 读取 | Gate 概要` 改为：

`Stage | 实际要做什么 | 完成标志 | 详细规则`

各 Stage 语义如下（表格内容保持紧凑，每个 Stage 最多 1~2 句）：

### Intake
- 做什么：确认 Feature 的目标、范围、成功标准、失败路径、兼容性及可验证 AC，只补尚未解决的 blocker。
- 完成：需求事实已确认并持久化。

### Environment
- 做什么：固定唯一 worktree，验证基线和并发状态。
- 完成：工作环境与状态一致，可安全进入规格阶段。

### Specification
- 做什么：调用 `dd-writing-specs`，生成并批准 Requirements、Design、Test Matrix；UI 功能按需生成 Visual。
- 完成：canonical spec 已批准，并有当前内容指纹和批准依据。

### Planning
- 做什么：从已批准规格生成 Phase 和可执行 Task 包，建立 AC → Task → Test/Evidence 映射。
- 完成：所有 Phase/Task 输入输出、写入范围、验证方式和停止条件都明确。

### Implementation
- 做什么：按当前 Task 的 `anchors`、全局约束、Out of Scope、失败路径及必要集成输入**选择性读取**规格（不完整重读）；按 Phase 执行 Task 并采用 TDD；每个 Phase 通过 Local Gate 并完成按风险路由的紧凑 Phase 复核（命中风险触发器时升级独立强审）；高风险 UI 按风险触发远程 Smoke CI；Local Gate 未通过不得进入下一 Phase。
- 完成：全部 Phase 已验证，无未解释的当前 Phase 缺口。
- 注意：这一行同时承载三项下沉语义（`anchors` 选择性读取、按风险触发 Smoke CI、风险路由 Phase 复核），不得复制 `implementation.md` 的触发器列表、A/B/C 定义和读取规则。

### Documentation
- 做什么：根据最终已验证行为判断哪些长期文档需要更新、无需更新或已过期。
- 完成：文档与即将冻结的实现一致。

### Final Candidate
- 做什么：冻结候选 SHA；对同一个 SHA 做确定性验证、独立审查、完整规格缺口检查和 Full CI。候选 Gate **只产出并验证可交付候选，不推进目标分支**。
- 完成：review / gap / CI 均绑定同一 `candidate_sha` 并通过。

### Confirmation
- 做什么：确认继续交付还是回退，不修改候选内容。
- 完成：继续或回退的决策已记录并持久化；仅当决定继续时才进入 Delivery。

### Delivery
- 做什么：仅在已有 action-specific authorization 的范围内推进同一个 `candidate_sha`。
- 完成：要求且获授权的交付动作都有证据。

### Closure
- 做什么：验证最终状态、写 Completion Receipt、按规则清理并完成 Host Close。
- 完成：成功路径的状态或 Completion Receipt 为 `completed`，所需清理已验证并按宿主合同收尾；`paused` 不是完成（不写 completed Receipt、不触发最终 Host Close）。

### Stage → reference 映射（冻结，表格"详细规则"列一律按此填写）

- Intake / Environment → `intake-and-environment.md`
- Specification → `specification.md`
- Planning → `planning-stage.md`
- Implementation → `implementation.md`
- Documentation → `documentation.md`
- Final Candidate / Confirmation → `candidate.md`
- Delivery / Closure → `delivery-and-closure.md`

现有合同测试只检查 reference 文件名是否出现在主文件，**不检查 Stage 与 reference 的配对是否正确**；因此配对以本清单为准，弱模型不得自行决定或改动配对。

## 六、核心不变量压缩：12 条 → 7 条

### 新的核心不变量（约 7 条，中文优先）

1. 没有已批准规格，不修改生产代码；
2. 已解决事实继承，状态和仓库证据支持恢复，不重复询问；
3. 每个 AC 必须能追到 Task 和 Test/Evidence；
4. 每个 Phase 必须通过 Local Gate 才能继续；
5. 用户可见行为必须有用户可见证据；
6. 最终候选必须冻结，审查 / 完整规格缺口检查 / 完整 CI 绑定同一个 SHA；
7. 内容批准、测试 PASS、审查者 PASS 只证明 Workflow Gate，不自动产生 Git 或外部动作授权。

### 旧 12 条不变量的完整去向映射（不得静默丢任何语义）

| 旧不变量 | 去向 |
|---|---|
| 1. No approved specification, no production code | 保留 → 新 #1 |
| 2. Resolved Bootstrap facts are inherited | 保留 → 新 #2 |
| 3. Every Phase ends with a local quality Gate | 保留 → 新 #4 |
| 4. High-risk UI changes get remote Smoke CI | **下沉**：`references/implementation.md` 的 Risk-based UI Smoke 章节是唯一属主；主文件只在 Implementation 路由行体现"高风险 UI 按风险触发 Smoke CI"，不复制触发器列表 |
| 5. The exact frozen candidate entering develop gets full CI | 保留 → 新 #6 |
| 6. User-visible behavior requires user-visible evidence | 保留 → 新 #5 |
| 7. Persist before every Stage transition | 不变量区移除；红线"状态未持久化就跨 Stage"保留；详细语义属主为 runtime |
| 8. Trae completion requires a final ASK | 不变量区移除；红线"Trae 完成后直接结束会话"保留；详细语义属主为 runtime Host Close 合同 |
| 9. Re-read approved originals; summaries only locate sources | **下沉（双层）**：共享原则"批准原文是事实来源，摘要只定位"由 `artifact-source-and-packet.md` 维护；Feature Planning 的"一次完整读取 + canonical inventory + 定向回读"执行策略由 `references/planning-stage.md` 维护；红线"用摘要替代批准原文，或在来源指纹／批准依据失效后继续执行旧包"保留 |
| 10. Phase 只读 anchors/global constraints | **下沉**：`references/implementation.md` 是读取规则唯一属主；主文件 Implementation 路由行保留一句真实语义（含 `anchors` 字样，见第五节），满足 AC-05 合同 |
| 11. Candidate Gate 不推进目标分支；Delivery 只推进同一 `candidate_sha` | 拆分：SHA 绑定保留 → 新 #6；"Candidate Gate 不更新 develop/main"的精确语义由 `references/candidate.md` 详细拥有，并在主文件 Stage/Gate 图（promote 只出现在 Delivery Gate）与 Final Candidate 路由行保持边界可见；红线"完整 CI 没有验证最终候选 SHA 就推进 develop"只覆盖"CI 未验证不得推进"场景，不作为该语义的归口 |
| 12. 内容批准 / 测试 PASS / Reviewer PASS 均不授权 Git 或外部动作 | 保留 → 新 #7 |

### 同文件防重复提醒

新 #3 来自现"通用质量 Gate"章节的"每个 AC 映射到计划、测试或明确证据"。升格为不变量后，"通用质量 Gate"章节不得再保留同一句的重复表述，该章节其余条目（项目规则、UI 证据、手动步骤、Git 卫生）保持不变。

### anchors 语义要求（AC-05 合同）

- 不得仅为了通过测试放一个无语义的 `anchors` 字符串；
- 不得恢复为"每个 Phase 完整读取全部规格"；
- `references/implementation.md` 仍是详细读取规则的唯一属主；
- 预期**不需要修改任何测试**；只有真实合同发生变化时才允许修改测试。

## 七、红线区

现有红线 14 条全部保留，不新增、不删减语义，并按主题分组以便扫读（建议分组：规格来源、授权边界、状态持久化、阶段纪律、UI 证据——具体命名执行者定，只归类、不改写语义）。本任务中迁出不变量的规则中，persist、Trae ASK、Documentation 先于冻结在现有红线中已有对应条目，不要产生同义重复；"Candidate Gate 不推进目标分支"不由现有红线归口（现有红线只覆盖"CI 未验证不得推进"场景），其边界按第六节 #11 的去向保留在 Stage/Gate 图、Final Candidate 路由行及 `references/candidate.md`；若措辞需要微调以避免重复，保持语义不变。

## 八、降低英文术语密度

正文优先使用中文。例如优先写：

- 验证证据，而不是 evidence；
- 完整规格缺口检查，而不是 full-spec gap；
- 冻结候选版本/冻结候选 SHA，而不是 frozen candidate；
- 交付授权，而不是 delivery authorization；
- 审查者，而不是 Reviewer，但代码字段 `candidate_review` 保持原样；
- 运行时，而不是 runtime，但 Skill 名 `dd-workflow-runtime` 保持原样。

以下内容必须保持原始标识，不翻译：文件名；Skill 名；字段名；枚举值；CLI 命令；YAML/JSON schema 字段；`candidate_sha`、`full_ci_run`、`delivery_authorization` 等现有合同标识。

**不要为了中文化修改程序或合同字段名。**

## 九、首次出现的少数抽象术语给一句话解释

只对第一次阅读确实难懂、而且主文件必须出现的术语增加极短解释，不建立术语表。例如：

- 冻结候选 SHA：实现和文档完成后锁定、等待最终验证和交付的唯一版本；
- 完整规格缺口检查：最后从整套已批准规格反查是否存在遗漏、越界或未验证项；
- compact verification：**不给自定义释义**，改写为中文"验证证据包"并一句路由到 `artifact-verification.md`（该文件是 plan+result 与 coverage/runs/bindings/validity 四不变量的唯一属主；主文件任何简化定义都会形成第二套定义）。

如果术语可以直接改成普通中文，则优先改写，不增加解释。

## 十、禁止事项

1. 把主 `SKILL.md` 恢复成过去的大而全版本；
2. 为了可读性复制共享 artifact 合同三个分文件（`artifact-source-and-packet.md` / `artifact-verification.md` / `artifact-lifecycle.md`）、`review-gate.md`、`ci.md` 的完整规则；
3. 增加新的顶层 Skill；
4. 引入 `implement-spec` 的 Phase 0~6；
5. 引入第二套 ledger/state；
6. 删除 exact-SHA、独立审查、完整规格缺口检查、Full CI；
7. 降低任何 Gate；
8. 把 Git/外部动作授权与 Workflow PASS 合并；
9. 修改现有字段/schema，仅为了文案美观；
10. 修改与本任务无关的 Skill；
11. 把"文件更短"本身当成成功标准；
12. 宣称 token 一定下降，除非有实际测量证据。

## 十一、完成后防重复检查

逐项检查：

1. 主 `SKILL.md` 是否只讲"整体怎么走"和"每 Stage 做什么"；
2. Stage 的详细规则是否仍只有对应 reference 一个属主；
3. A/B/C 语义是否仍只取 `dd-workflow-runtime/references/review-gate.md`；
4. `artifact-contract.md` 是否仍只作为共享合同路由器；来源／执行包／授权是否只取 `artifact-source-and-packet.md`，验证证据是否只取 `artifact-verification.md`，生命周期／同步是否只取 `artifact-lifecycle.md`，主文件不得复制这些详细合同；
5. CI 细节是否仍只由 runtime CI reference 负责；
6. 状态恢复通用语义是否仍由 runtime 负责；
7. `dd-writing-specs` 已拥有的规格语义检查是否没有在 Feature 主 Skill 中重新完整复制。

如果发现主文件与 reference 同时定义同一规则，优先保留 reference 作为唯一详细属主，主文件改为一句话概述并链接。

## 十二、验证

### 命令

```bash
python3 -m unittest discover -s dd-feature-development-workflow/tests -p 'test_*.py'
python3 -m unittest discover -s dd-workflow-runtime/tests -p 'test_*.py'
git diff --check
```

**优先在不修改任何测试代码的情况下让全部测试通过。** 只有真实合同发生变化时才允许修改测试，且：不得删除核心合同断言；不得把严格断言改成无意义的字符串存在检查；必须说明为什么测试需要调整。

### Stage 顺序合同测试注意事项

现有测试通过英文 token 的**首次出现位置**验证 `implementation < documentation < final-candidate`。因此修改主 `SKILL.md` 时：

- 工作流概览优先使用中文描述（这天然规避该风险）；
- 若英文 Stage 名提前出现，必须保持真实 Stage 顺序；
- 不得因为示例、说明或 YAML 中的乱序首次出现破坏该测试；
- 不得为了测试而改变真实 Stage 顺序。

### 语义检查清单

- 所有 active reference 链接仍有效；
- 没有新增重复规则；
- Stage 顺序不变（intake → environment → specification → planning → implementation → documentation → final-candidate → confirmation → delivery → closure）；
- Documentation 仍早于 Final Candidate；
- Candidate Gate 仍不更新 develop/main；
- Delivery 仍只推进同一个 `candidate_sha`；
- Git/外部动作仍要求独立授权；
- 12 条旧不变量的每一条都能在第六节去向映射中找到归宿。

## 十三、最终输出

完成后只报告：

1. 修改了哪些文件；
2. 主 `SKILL.md` 的结构发生了什么变化；
3. 删除/下沉了哪些重复或过度抽象内容；
4. 哪些核心治理能力明确保持不变；
5. 测试结果；
6. 如发现现有合同本身存在矛盾，单独列为 finding，不要擅自改变语义。

## 十四、本次范围外的后续建议（执行者只在报告中转述，不实施）

本次重构落地后，建议另起一个小任务为主文件新增内容补测试保护：现有合同测试没有断言"工作流概览章节存在"或"十个 Stage 的完整顺序"（顺序断言只覆盖 `implementation < documentation < final-candidate` 三个 token），下一轮重构可能在测试全绿的情况下无声删掉概览或 Stage 表。该建议不属于本次执行范围；不要为了加断言而修改本次交付。

---

本任务的成功标准不是"把文档写得更多"，而是：

> Agent 第一次只读 `SKILL.md` 就能理解整个 Feature 从需求到交付到底怎么走；只有进入具体 Stage 时，才需要打开对应 reference。
