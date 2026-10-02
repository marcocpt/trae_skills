# L-02 探针原始输出

本文件保存两次运行的**完整原始输出**（脚本见同目录 `L02-checkpoint-probe.sh`）：

- **v1 初稿**（2026-10-02T03:53:43Z）：端到端 jq 误用 Oniguruma `"n"` 旗标，出现 `parsed=0` 假象；其"选取结果对编辑稳定"是**历史初稿结论，已被复审 B-M-02 推翻**——当前规则为"排序键稳定 ≠ 资格稳定 + append-only + 每次抓取重新评估资格"（合同 §6.1 第 6 条）。原样保留仅作事故与更正记录。
- **v2 最终版**（2026-10-02T05:47:20Z）：脚本端到端段**直接实现合同 §6.1 七步冻结规则**（marker 前缀 → 八字段完整校验（含负样本自检门）→ workflow 过滤 → 同 checkpoint_id 取最小 comment id → comment id 最大 → 五计数），执行结果 PASS。

---

# 【v2 最终版】L-02 真实 GitHub 探针取证（2026-10-02T05:47:20Z）

repo=marcocpt/dd-checkpoint-probe-20261002 issue=1

## 评论清单（默认序，前 100 条）

    5945301012 2026-10-02T03:53:28Z 2026-10-02T05:09:47Z <!-- dd-checkpoint:v1 -->
    5945301327 2026-10-02T03:53:29Z 2026-10-02T03:53:29Z <!-- dd-checkpoint:v1 -->
    5945301627 2026-10-02T03:53:31Z 2026-10-02T03:53:31Z <!-- dd-checkpoint:v1 -->
    5945301947 2026-10-02T03:53:33Z 2026-10-02T03:53:33Z <!-- dd-checkpoint:v1 -->
    5945302701 2026-10-02T03:53:36Z 2026-10-02T03:53:36Z <!-- dd-checkpoint:v1 -->

（c1 的 updated_at=05:09:47 为第二次运行中追加式编辑所致，符合 append-only 预期。）

## c1 追加式编辑前后 created_at

    before=2026-10-02T03:53:28Z after=2026-10-02T03:53:28Z
    ASSERT created_at-stable: PASS

## id 单调性

    ids=[5945301012,5945301327,5945301627,5945301947,5945302701] monotonic_ascending=true

## 默认排序 = created 升序

    first=2026-10-02T03:53:28Z last=2026-10-02T03:53:36Z

## sort=created direction=desc（预期：被端点忽略，仍最旧在前 → 选取必须客户端排序）

    first=2026-10-02T03:53:28Z

## per_page=2 分页 Link header

    Link: <https://api.github.com/repositories/1401026703/issues/1/comments?per_page=2&page=2>; rel="next", <https://api.github.com/repositories/1401026703/issues/1/comments?per_page=2&page=3>; rel="last"

## per_page=101 上限

    5

## since 参数（取 c2 created 时刻；预期按 updated_at 过滤，编辑过的 c1 仍被纳入 → 不可作 created 游标）

    5

## 端到端选取（实现合同 §6.1 七步冻结规则：全量 Link 翻页 → marker 前缀 → 八字段完整校验 →
   workflow_id 过滤 → 同 checkpoint_id 取最小 comment id → comment id 最大为最新 → 输出五计数）

    fetched_total=5 marker_candidates=5 malformed=1 after_workflow_filter=3 duplicates=1
    selected checkpoint_id=cp-20261002T100500Z-c5d5 comment_id=5945302701 created_at=2026-10-02T03:53:36Z
    negative_sample_1_sha_empty_then_blocker_valid=false (expect false)
    negative_sample_2_sha_whitespace_next_line_valid=false (expect false)
    negative_sample_3_sha_only_in_prose_midline_valid=false (expect false)
    negative_sample_4_sha_prose_standalone_line_valid=false (expect false)
    negative_sample_5_sha_in_current_body_canonical_order_violation_valid=false (expect false)

计数核对：`malformed=1`（c3 伪造：有 marker、零必填字段）→ `after_workflow_filter=3`（c2 其他 workflow 被排除）→ `duplicates=1`（c4 与 c1 同 checkpoint_id，折叠为首投）→ 选中 c5（cp-…-c5d5，comment id 最大）✓

负样本自检（§3 事故 2 与外审 B-R-01 回归门）：脚本内用 jq 构造五个伪造 body——①`SHA:` 空值后紧跟 `Blocker: none`（跨行误吞）；②`SHA:` 下一行仅空格（纯空白不算值）；③结构化区缺 `SHA`、仅 Current: 正文行中提及 `SHA: fake`（非行首字段不得顶替）；④结构化区缺 `SHA`、Current: 正文**独立一行** `SHA: fake`（非 section 头不得顶替，外审 B-R-01 负样本）——五者 `hasfield("SHA")` 必须均为 false（第 5 项：Current body 内独立 `SHA:` 行破坏 canonical 顺序 Current→SHA→Next，整条 malformed）；脚本以 bash grep 门强制，任一非 false 取证失败退出。

---

# 【v1 初稿·历史记录】L-02 真实 GitHub 探针取证（2026-10-02T03:53:43Z）

> ⚠️ 本节为**历史初稿**：端到端 jq 带有 Oniguruma `"n"` 旗标事故（见下）；其"选取结果对编辑稳定"
> 结论已被复审 B-M-02 推翻（编辑可改变评论资格），当前规则以合同 §6.1 第 6 条为准。

repo=marcocpt/dd-checkpoint-probe-20261002 issue=1

## 评论清单（默认序，前 100 条）

    5945301012 2026-10-02T03:53:28Z 2026-10-02T03:53:42Z <!-- dd-checkpoint:v1 -->
    5945301327 2026-10-02T03:53:29Z 2026-10-02T03:53:29Z <!-- dd-checkpoint:v1 -->
    5945301627 2026-10-02T03:53:31Z 2026-10-02T03:53:31Z <!-- dd-checkpoint:v1 -->
    5945301947 2026-10-02T03:53:33Z 2026-10-02T03:53:33Z <!-- dd-checkpoint:v1 -->
    5945302701 2026-10-02T03:53:36Z 2026-10-02T03:53:36Z <!-- dd-checkpoint:v1 -->

## c1 编辑前后 created_at

    before=2026-10-02T03:53:28Z after=2026-10-02T03:53:28Z
    ASSERT created_at-stable: PASS

## id 单调性

    ids=[5945301012,5945301327,5945301627,5945301947,5945302701] monotonic_ascending=true

## 默认排序 = created 升序

    first=2026-10-02T03:53:28Z last=2026-10-02T03:53:36Z

## sort=created direction=desc

    first=2026-10-02T03:53:28Z

## per_page=2 分页 Link header

    Link: <https://api.github.com/repositories/1401026703/issues/1/comments?per_page=2&page=2>; rel="next", <https://api.github.com/repositories/1401026703/issues/1/comments?per_page=2&page=3>; rel="last"

## per_page=101 上限

    5

## since 参数（取 c2 之后时刻）

    5

## 端到端选取（初稿，三字段 jq + "n" 旗标事故）

    parsed_with_required_fields=0 after_workflow_filter=0
    selected checkpoint_id=

## 更正与补充（同日 2026-10-02）

- 初稿「端到端选取」jq 误用 `capture(re; "n")` 旗标（Oniguruma 旗标 "n" 吞掉全部匹配，被 try 静默丢弃）；
  去旗标后重跑：`parsed_with_required_fields=4 after_workflow_filter=3 selected checkpoint_id=cp-20261002T100500Z-c5d5` —— PASS。
- **关键事实 1：comments 端点忽略 `sort=created&direction=desc`**（实测仍返回最旧在前）→ 选取必须客户端排序。
- **关键事实 2：`since` 按 `updated_at` 过滤**（c1 编辑后重新进入 since 之后结果集）→ 不能用于 created 时间游标。
- id 单调性：5/5 严格递增；comment id 唯一 → 以 id 为排序键（等价 created 序且避免秒级并列）。
- 编辑语义：PATCH 后 created_at/id 不变、updated_at 变化 → 排序键对编辑稳定（**资格稳定性结论已被推翻**，见文件头部说明）。
- 伪造（c3：有 marker 无必填字段）被字段校验丢弃；其他 workflow（c2）被 workflow_id 过滤排除；重复 checkpoint_id（c4）折叠为最小 comment id（首次投递）。
