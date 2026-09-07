> 决策建议审查（advisory review）的执行规则。路由入口与适用判断见 [SKILL.md](../SKILL.md)；后端选择、会话续接与传输规则一律按 [transport.md](transport.md) 对应分节执行，本文件不复制。

# 决策建议审查（开放决策点求建议）

## 适用与不适用

适用：

- 用户已有一组**开放决策点**（规格没有答案、需要人选的设计/参数/策略问题），要求外部强审者给意见与建议后由用户裁决；
- 用户要求"先把所有问题列出来、给出建议、我再定"。

不适用：

- 审核代码/文档找缺陷、按意见修复闭环 → 走 [SKILL.md](../SKILL.md) 的问题闭环审查主流程；
- 强审者复核修复结果 → 走 [SKILL.md](../SKILL.md)「修复后复查」。

## 决策点模型

每个决策点（DP）记录：

- **id**：稳定编号（DP-1、DP-2…）；
- **问题**：要选什么（一句话）；
- **背景与约束**：相关规格、代码位置、已定约束；
- **选项**：A/B（必要时 C），每项一句影响说明；
- **强审者建议**：推荐项 + 理由 + 主要反对意见/风险；信息不足时明确说缺什么材料；
- **用户裁决**：采纳的方案 / 不采纳（记理由）/ 延后。

DP 内部 status 取值：`OPEN`（待送审或待建议）→ `ADVISED`（已拿到建议待裁决）→ `DECIDED` / `DEFERRED`。本模式不使用 finding 生命周期与 CLOSED 判据。

## 送审

1. 后端解析与校验按 [SKILL.md](../SKILL.md)「输入」与传输合同「后端选择」执行；后端自身不具资格 → 按 [SKILL.md](../SKILL.md)「BLOCKED 恢复动作」处理；
2. **模式边界（按 runtime 合同动态判定，LATER-20260907 起放开）**：后端支持本模式的机械条件是——registry 声明 `advisory` capability 与 `advisory_result_schema: dd-advisory-result/1`，且该调用形态有 backend-bound 只读/结果格式证据（FR-MB-012），经 dispatch 的 advisory 路径（`request.mode: "advisory"`，候选来自 `stateful_roles`）产出 `dd-advisory-result/1`。当前满足条件者：`opencode-cli`（证据 `opencode-advisory-readonly-evidence.yaml`）与 `codex-cli`（专用 advisory profile 注入 prompt，证据 `codex-advisory-readonly-evidence.yaml`）；**不得**谎报为资格失败，**不得**把决策点建议伪装成 finding 或塞进 evidence 字段；
3. 受审范围与请求按所选通道构造：CLI 后端经 `dispatch-review.py` 发 `mode: "advisory"` 请求（`decision_points` 必填，含每点的 id/问题/背景约束/已知选项；`verification` 仅是补充上下文，**不是** admission gate）；`chatgpt-tunnel` 的 content 按 transport「决策建议审」模板构造，覆盖：全部决策点、每点的背景/约束/已知选项、可选权威依据、冻结 baseline；
4. 明确要求强审者对**每个**决策点输出：推荐项、理由、反对意见/风险、信息是否充足；并声明覆盖情况（`reviewed` / `unreadable`），未完整读取即不得宣称审核完成；`status: ADVISORY` 的结果必须完整覆盖 scope 与全部请求的 DP，reviewer 新提的开放问题出现在 `suggested_decision_points`（无正式 id，由本层登记后分配）；
5. 强审者提出新的开放问题（用户没列到的）→ 从 `suggested_decision_points` 或自由文本中登记为新 DP 并标注来源。

## 结果处理与展示

1. 本地核对强审者引用的文件、行号、规格（标准同 [SKILL.md](../SKILL.md) 循环状态机第 4 步）；发现强审者引用或建议依据有误 → 该 DP 视为未获有效建议、保持 `OPEN`，附本地反证、复用同一会话请求重新评估，取得修正后的有效建议后才置 `ADVISED`；不得静默丢弃，也不得套用 finding 的 DISPUTED 状态；
2. 汇总为**决策清单**，一次向用户展示全部 DP 的：问题、选项、强审者建议、一句理由。决策清单是只读展示，不是裁决请求；
3. **裁决一次一个**：展示决策清单后，从第一个 `ADVISED` 的 DP 开始逐个请求裁决，每次只含一个 DP（标推荐项与影响说明）；用户未回答不得跳到下一个；用户可只裁决其中一部分，其余保持 `ADVISED` 或按用户指示 `DEFERRED`；
4. 信息不足、未获得建议的 DP 保持 `OPEN`，不得据以请求裁决；补齐材料后重新送审该 DP；
5. 用户回答含糊 → 就该 DP 重新提问，不得猜测裁决。

## 裁决后

- 采纳 → 记录所选方案与理由；需要实施时按用户指示转问题闭环审查或单独任务，本模式不自动修改文件；
- 不采纳 → 记录不采纳理由；
- 延后 → `DEFERRED`，不得继续当阻塞项。

## 夹带缺陷

决策建议审查中强审者顺带发现疑似代码/文档缺陷时：登记为**待核查问题候选**（标注来自 advisory 轮次），不得直接作为 canonical finding 进入主流程。须经问题闭环审查的权威审查轮次重新送审该问题，正式返回 `FINDINGS` 后，才按 [SKILL.md](../SKILL.md) 主流程建立 finding 并分流处置；不得混入决策点模型。

## 红线

- 不得把"求建议"跑成问题闭环审查，强行套 SEVERITY / CLASSIFICATION / CHANGE_RISK；
- 不得把决策清单展示当成批量裁决请求，也不得借清单名义一次要求用户拍板多个独立 DP；
- 不得把决策点建议伪装成 finding 或塞进 evidence 字段来绕过后端结果合同；
- 不得在用户未裁决时替用户选方案并直接实施；
- 后端资格、会话续接、只读取证规则与问题闭环审查同源同责，违反即按传输合同对应红线处理。
