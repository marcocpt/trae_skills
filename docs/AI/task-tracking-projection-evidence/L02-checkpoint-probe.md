# L-02 真实 GitHub 探针取证：checkpoint 评论选取规则

> 归属：Task Tracking 投影改造设计 §8 待取证项 L-02（`docs/AI/2026-10-02-task-tracking-projection-design.md`）
> 取证日期：2026-10-02 ｜ 执行环境：gh CLI（marcocpt），真实 GitHub REST API v3
> 探针仓库：`marcocpt/dd-checkpoint-probe-20261002`（私有一次性 scratch repo，issue #1，取证后可整体删除；删除属 owner 动作）
> 结果：**PASS——冻结规则已写入 `dd-workflow-runtime/references/task-tracking.md` §6.1**
>
> 产物三件套（可复现闭环）：
> 1. 本文档（结论 + 设计 + 更正记录）；
> 2. `L02-checkpoint-probe.sh` —— **完整探针脚本**（含修复后的选取 jq，无旗标）；
> 3. `L02-checkpoint-probe-raw-output.md` —— **原始输出**（初稿 `parsed=0` 假象与去旗标后的更正同文件留存）。

## 1. 探针设计（对应 L-02 四类风险）

| 探针评论 | 内容 | 验证点 |
|---|---|---|
| c1 | 合法 checkpoint（probe-wf，cp-…-a1b2） | 基线；随后 PATCH 编辑验证编辑语义 |
| c2 | 合法 checkpoint（**other-wf-999**） | 同 Issue 其他 workflow 过滤 |
| c3 | 仅 marker、无必填字段 | 伪造 marker 识别 |
| c4 | 与 c1 **同 checkpoint_id** | 重复 checkpoint 折叠 |
| c5 | 合法 checkpoint（probe-wf，cp-…-c5d5，最晚投递） | 端到端"最新"选取目标 |

另做 API 机制取证：默认序、id 单调性、`sort=created&direction=desc`、`since`、`per_page` 分页与上限、编辑后 `created_at` 稳定性。

## 2. 实测结果（原始数据见 `L02-checkpoint-probe-raw-output.md`）

### 2.1 API 机制

| 探针项 | 实测 | 结论 |
|---|---|---|
| 默认排序 | oldest→newest（created 升序），`first=03:53:28Z last=03:53:36Z` | 与 GitHub REST 合同一致（单 Issue 评论按 id 升序返回） |
| id 单调性 | `[5945301012,…,5945302701] monotonic_ascending=true`（5/5） | comment id 与创建序一致且全局唯一（**排序键依据以 GitHub 合同为主、样本为辅**） |
| `sort=created&direction=desc` | 仍返回最旧在前 | **该端点无 sort/direction 参数**（GitHub REST 合同 + 实测一致）：选取必须客户端排序 |
| `since` | 取 c2 创建时刻，仍返回 5 条（含编辑过的 c1） | **按 `updated_at` 过滤**：不能用作 created 时间游标 |
| `per_page=2` 分页 | `Link: …page=2; rel="next", …page=3; rel="last"` | 全量翻页以 Link 驱动 |
| `per_page=101` | 无报错（返回全部 5 条） | 服务端钳制、不报错；实现按 ≤100 分页 |
| 编辑语义 | c1 PATCH 后 `created_at` 不变、id 不变、`updated_at` 03:53:28→03:53:42 | `ASSERT created_at-stable: PASS`——排序键对编辑稳定（**资格**对编辑不稳定，见 §4） |

### 2.2 端到端选取（v2：脚本端到端段直接实现 §6.1 七步冻结规则 → PASS）

选取实现（完整脚本见 `L02-checkpoint-probe.sh`，与合同 §6.1 一一对应）：

1. `--paginate` 全量翻页（`per_page=100`，跟随 `Link: rel="next"`）；
2. marker 前缀过滤（`startswith("<!-- dd-checkpoint:v1 -->")`）；
3. **八字段完整校验（结构化区限定）**：同行字段（workflow_id/workflow_type/checkpoint_id/host/state_status/remote）只认**头部区**（首个 section 头之前）的行首 `key: ` 且值 trim 非空；section 字段（Branch/SHA）必须是精确 `key:` section 头且 body 有非空行——正文（Current:/Next: 自由文本）中无论行中还是独立行的 `SHA: fake` 都不构成结构化字段（§3 事故 2 负样本已内嵌为脚本自检门）；缺任一字段 = malformed 丢弃；
4. `workflow_id == 当前工作流` 过滤；
5. `group_by(cp) | map(sort_by(.id)[0])`——同 checkpoint_id 保留**最小 comment id**（首投）；
6. `sort_by(.id)[-1]`——comment id 最大者为最新（`id`/`created_at` 从原始评论对象保留，不经字段投影丢失）；
7. 输出五计数：`fetched_total / marker_candidates / malformed / after_workflow_filter / duplicates`。

v2 运行结果（完整输出见 `L02-checkpoint-probe-raw-output.md` v2 节）：

```text
fetched_total=5 marker_candidates=5 malformed=1 after_workflow_filter=3 duplicates=1
selected checkpoint_id=cp-20261002T100500Z-c5d5 comment_id=5945302701 created_at=2026-10-02T03:53:36Z
negative_sample_1_sha_empty_then_blocker_valid=false
negative_sample_2_sha_whitespace_next_line_valid=false
negative_sample_3_sha_only_in_prose_midline_valid=false
negative_sample_4_sha_prose_standalone_line_valid=false
negative_sample_5_sha_in_current_body_canonical_order_violation_valid=false
```

计数核对：`malformed=1`（c3 伪造）→ `after_workflow_filter=3`（c2 排除）→ `duplicates=1`（c4 折叠首投）→ 选中 c5 ✓；五个负样本自检全部 false ✓。

## 3. 取证过程更正（诚实记录，两次）

1. **jq `"n"` 旗标事故**：初稿端到端 jq 误写 `capture(re; "n")`：Oniguruma 旗标 `"n"`（ignore empty matches）吞掉全部匹配，且被 `try … // empty` 静默归零，呈现 `parsed=0` 假象。教训：**正则旗标不得凭直觉携带；静默丢弃路径必须配对计数输出**——已固化为合同 §6.1 第 7 条（五个计数）。
2. **八字段校验的换行值与跨行误吞**：§6 模板中 `SHA:` / `Branch:` 的值在冒号**下一行**，初版逐字段正则 `": [^\n]+"` 把全部合法评论误判 malformed（`malformed=5`；该次失败运行的完整输出未单独保存，事故事实与修正以本节、脚本 git 历史及 raw-output v2 节为准）。第一版修正 `":\\s*\\S"` 又引入反向漏洞：`\s*` 跨行会把 `SHA:` 空值后紧跟的 `Blocker: none` 误判为有效值（外审 B-R-01 指出）。第二版 `"\\s*\\S"` 仍无法拒绝「Current: 正文独立一行 `SHA: fake` 顶替缺失字段」（外审 B-R-01 二轮）。最终版改为**结构化区限定**的 jq 行级解析：同行字段只认头部区（首个 section 头之前）、`Branch`/`SHA` 必须是精确 `key:` section 头且 body 有非空行；五个负样本（跨行误吞 / 纯空白下一行 / 仅正文行中提及 / 正文独立行 `SHA: fake` / Current body 内独立 `SHA:` 行破坏 canonical 顺序）内嵌为**脚本自检门**（bash grep 强制，任一非 false 取证失败退出）。

## 4. 探针覆盖边界与复审整改（2026-10-02 外审 FINDINGS 收口）

- **B-M-01（校验过弱）**：初版冻结规则只要求 marker + workflow_id + checkpoint_id，最小伪造即可通过。整改：合同 §6.1 第 2 条升级为**完整必填字段校验**（恢复实际消费的 `workflow_id / workflow_type / checkpoint_id / host / state_status / remote / Branch / SHA`，缺任一 = malformed 丢弃）。探针 c3 只覆盖"无字段"这一档；"字段不全"档由合同规则覆盖，未单独投递样本。
- **B-M-02（编辑结论过度）**：初版写"编辑不影响选取结果"，实际只证明了**普通正文编辑**不改 id/created_at。整改：§6.1 第 6 条改为"排序键稳定 ≠ 资格稳定"——编辑可改变评论资格（改掉 marker/必填字段 → malformed；改 checkpoint_id → 视为新 checkpoint），约定 **append-only** 且恢复方每次抓取重新评估资格。raw-output v1 节已将该旧结论标注为"历史初稿结论，已被推翻"。探针未覆盖"编辑关键字段"样本，该档由本条规则约束。
- **B-M-03（证据可复现性）→ B-R-01 收口**：证据三件套入仓（本文档 / `L02-checkpoint-probe.sh` / `L02-checkpoint-probe-raw-output.md`）。复审指出初版入仓脚本仍是三字段旧逻辑且 `sort_by(.id)` 引用经投影丢失的 `.id`——脚本端到端段已重写为 §6.1 七步规则的直接实现（八字段校验、保留原始评论对象、五计数），并真实重跑（v2，2026-10-02T05:47:20Z，PASS，计数齐全）。复审二轮指出 `:\\s*\\S` 会跨行误吞（`SHA:` 空值后紧跟 `Blocker: none` 误判有效）——已改为 jq 组合逻辑（同行值 OR 下一行值且下一行非字段行；gh 内嵌 jq 为 RE2 不支持前瞻），并把五个负样本（跨行误吞 / 纯空白下一行 / 仅正文行中提及 / 正文独立行 `SHA: fake` / Current body 内独立 `SHA:` 行破坏 canonical 顺序）内嵌为**脚本自检门**（bash grep 强制，任一非 false 取证失败退出）。**合同测试同步加固**：`TestSection61Selection` 现断言脚本含八字段、五计数、`sort_by(.id)[-1]`、`issechdr` 结构化守卫、五个负样本自检门与"无 n 旗标"，语义漂移会被测试捕获。
- **B-R-02 收口**：raw-output v1 节的"编辑稳定"旧结论已标注为历史初稿结论、被 B-M-02 推翻；本文档不再把三字段 jq 称为"生产语义"（§2.2 已替换为八字段规则实现）。
- **B-H-01 收口**：全部改动落位于 `docs/task-tracking-projection` worktree（分支 `docs/task-tracking-projection`），`develop` 工作树保持干净。
- **补强（计数）**：§6.1 第 7 条要求输出 `fetched_total / marker_candidates / malformed / after_workflow_filter / duplicates` 五计数（探针脚本初稿只有 parsed / filtered 两档，不足以判断静默丢失）。
- **补强（合同测试）**：`dd-workflow-runtime/tests/test_task_tracking.py` 新增 §6.1 section-scoped 断言与变异测试（`TestSection61Selection` + `TestMutations` 三条 §6.1 变异），把翻页/禁 sort+since/完整字段校验/workflow 过滤/去重/最新选取/append-only/计数/证据脚本语义固定进测试。
- **样本量边界**：5 条 / 单 issue；>100 条真实多页场景未触发（Link 语义已用 per_page=2 验证），实现侧在超长 issue 上重验。

## 5. 复核与清理

- scratch repo `marcocpt/dd-checkpoint-probe-20261002` 保留供复核（5 条评论 id：5945301012 / 5945301327 / 5945301627 / 5945301947 / 5945302701），owner 可随时删除。
- 外审（ChatGPT 会话 `6abf1aa1-63e8-83ea-b1d9-778db3f08447`）已独立核对该 issue 的评论 ID 与本文摘要一致。
