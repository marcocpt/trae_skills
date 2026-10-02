#!/usr/bin/env bash
# L-02 最小真实 GitHub 探针：checkpoint 评论选取规则取证
# （属主：skills 仓库 Task Tracking 投影设计 §8 待取证项 L-02；
#   本脚本为「可复现证据」，端到端选取段直接实现合同 task-tracking.md §6.1 的七步冻结规则）
#
# 前置：gh 已登录 marcocpt；scratch repo 不存在或可复用。
# 产出：/tmp/dd-checkpoint-probe-result.md（机器可核证据：原始输出 + 断言结果）
#
# 探针范围（对应 L-02 四类风险）：
#   1. 过滤其他 workflow   → c2（other-wf）
#   2. 伪造 marker         → c3（有 marker、无必填字段）
#   3. 重复 checkpoint     → c4（与 c1 同 checkpoint_id）
#   4. 分页与排序          → 默认序 / Link header / sort=created-desc / since / per_page 上限 / id 单调
#   5. 编辑语义            → 追加式 PATCH c1 后 created_at/id 不变（updated_at 变化；幂等可重跑）
#   6. 端到端选取          → §6.1 冻结规则（八字段校验 + workflow 过滤 + 去重 + id 最大 + 五计数）应选中 c5
set -euo pipefail

REPO="marcocpt/dd-checkpoint-probe-20261002"
ISSUE_TITLE="L-02 checkpoint probe (dd-checkpoint selection rule evidence)"
OUT="/tmp/dd-checkpoint-probe-result.md"
WF="probe-wf-20261002T000000Z"
CP_A="cp-20261002T100000Z-a1b2"
CP_B="cp-20261002T100500Z-c5d5"
MARKER='<!-- dd-checkpoint:v1 -->'

# §6 模板正文（占位：$1 workflow_id  $2 checkpoint_id  $3 stage）
checkpoint_body() {
  printf '%s\n\nworkflow_id: %s\nworkflow_type: feature-development\ncheckpoint_id: %s\nhost: codex\nstage: %s\nstate_status: active\nremote: local-only\n\nCurrent:\nprobe comment.\n\nNext:\nn/a.\n\nBranch:\ndocs/task-tracking-projection\n\nSHA:\n0000000000000000000000000000000000000000\n\nBlocker:\nnone\n\nTaken over from:\nnone\n' \
    "$MARKER" "$1" "$2" "$3"
}

echo "==> 1. 确保 scratch repo 与 issue 存在"
gh repo view "$REPO" >/dev/null 2>&1 || gh repo create "$REPO" --private --description "L-02 checkpoint probe (disposable)" >/dev/null
ISSUE_NUMBER=$(gh issue list -R "$REPO" --state open --json number,title --jq ".[] | select(.title==\"$ISSUE_TITLE\") | .number" | head -1)
if [ -z "${ISSUE_NUMBER:-}" ]; then
  ISSUE_NUMBER=$(gh issue create -R "$REPO" --title "$ISSUE_TITLE" --body "自动探针：验证 dd-checkpoint 评论选取规则（L-02）。可整体删除。" | grep -o '[0-9]*$')
fi
echo "issue=$ISSUE_NUMBER"

echo "==> 2. 投递探针评论（幂等：仅在 issue 无评论时投递）"
EXISTING=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq 'length')
if [ "$EXISTING" -eq 0 ]; then
  gh issue comment "$ISSUE_NUMBER" -R "$REPO" --body "$(checkpoint_body "$WF" "$CP_A" implementation)"   # c1
  gh issue comment "$ISSUE_NUMBER" -R "$REPO" --body "$(checkpoint_body "other-wf-999" "cp-other-0001" implementation)"  # c2 其他 workflow
  gh issue comment "$ISSUE_NUMBER" -R "$REPO" --body "$MARKER

伪造成评论：无任何必填字段。"   # c3 伪造（有 marker、零字段）
  gh issue comment "$ISSUE_NUMBER" -R "$REPO" --body "$(checkpoint_body "$WF" "$CP_A" implementation)"   # c4 重复 checkpoint_id
  gh issue comment "$ISSUE_NUMBER" -R "$REPO" --body "$(checkpoint_body "$WF" "$CP_B" documentation)"   # c5 最新
else
  echo "issue 已有 $EXISTING 条评论，跳过投递（幂等重跑）"
fi

echo "==> 3. 追加式编辑 c1（模拟上游更正；append-only，幂等）"
C1_ID=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '.[0].id')
C1_CREATED_BEFORE=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '.[0].created_at')
C1_BODY=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '.[0].body')
case "$C1_BODY" in
  *"探针追加式编辑痕迹"*) echo "c1 已含追加痕迹，跳过（幂等）" ;;
  *)
    gh api -X PATCH "repos/$REPO/issues/comments/$C1_ID" \
      -f body="$C1_BODY

探针追加式编辑痕迹：本行由探针 PATCH 追加（append-only）。" >/dev/null
    ;;
esac
C1_CREATED_AFTER=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '.[0].created_at')

echo "==> 4. API 机制取证"
{
  echo "# L-02 真实 GitHub 探针取证（$(date -u +%FT%TZ)）"
  echo "repo=$REPO issue=$ISSUE_NUMBER"
  echo
  echo "## 评论清单（默认序，前 100 条）"
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" \
    --jq '.[] | "\(.id) \(.created_at) \(.updated_at) \(.body | split("\n")[0])"'
  echo
  echo "## c1 追加式编辑前后 created_at"
  echo "before=$C1_CREATED_BEFORE after=$C1_CREATED_AFTER"
  [ "$C1_CREATED_BEFORE" = "$C1_CREATED_AFTER" ] && echo "ASSERT created_at-stable: PASS" || echo "ASSERT created_at-stable: FAIL"
  echo
  echo "## id 单调性"
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '[.[].id] as $ids |
    (reduce range(1; $ids|length) as $i (true; . and ($ids[$i] > $ids[$i-1]))) as $mono |
    "ids=\($ids) monotonic_ascending=\($mono)"'
  echo
  echo "## 默认排序 = created 升序"
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '"first=" + .[0].created_at + " last=" + (.[-1].created_at)'
  echo
  echo "## sort=created direction=desc（预期：被端点忽略，仍最旧在前 → 选取必须客户端排序）"
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100&sort=created&direction=desc" --jq '"first=" + .[0].created_at'
  echo
  echo "## per_page=2 分页 Link header"
  gh api -i "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=2" 2>/dev/null | grep -i '^link:' || echo "(单页无 Link)"
  echo
  echo "## per_page=101 上限"
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=101" --jq 'length'
  echo
  echo "## since 参数（取 c2 created 时刻；预期按 updated_at 过滤，编辑过的 c1 仍被纳入 → 不可作 created 游标）"
  SINCE=$(gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '.[1].created_at')
  gh api "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100&since=$SINCE" --jq 'length'
  echo
  echo "## 端到端选取（实现合同 §6.1 七步冻结规则：全量 Link 翻页 → marker 前缀 → 八字段完整校验 →"
  echo "   workflow_id 过滤 → 同 checkpoint_id 取最小 comment id → comment id 最大为最新 → 输出五计数）"
  gh api --paginate "repos/$REPO/issues/$ISSUE_NUMBER/comments?per_page=100" --jq '
    def reqs: ["workflow_id","workflow_type","checkpoint_id","host","state_status","remote","Branch","SHA"];
    # 字段解析（结构化区限定；gh 内嵌 jq 为 RE2 无前瞻 → 行级状态机）：
    # ① 同行字段（workflow_id/workflow_type/checkpoint_id/host/state_status/remote）：
    #    必须位于**首个 section 头（Current:/Next:/…）之前**的头部区，行首 "key: " 且值非空；
    # ② section 字段（Branch/SHA）：必须存在 trim 后恰为 "key:" 的 section 头行，
    #    且其 body（到下一 section 头前）有非空行；
    # ③ 正文（Current:/Next: 自由文本）中出现的 "SHA: fake"——无论行中还是独立行——
    #    都不构成结构化字段（外审 B-R-01 负样本 4）。
    def sectionkeys: ["Current","Next","Branch","SHA","Blocker","Taken over from"];
    def trim: gsub("^\\s+|\\s+$";"");
    def issechdr($ln): ($ln | trim) as $t | ($t | endswith(":")) and ((sectionkeys | index($t[:-1])) != null);
    def seckey($ln): ($ln | trim | sub(":$";""));
    def hasfield($b; $f):
      ($b | split("\n")) as $L
      | ($L | length) as $n
      | ([range(0; $n) | select(issechdr($L[.]))]) as $hidx
      # canonical 顺序约束（外审 B-R-01 终轮）：section 头的 canonical 序号必须严格递增
      # （Current→Next→Branch→SHA→Blocker→Taken over from）；正文行即便形如 "SHA:"，
      # 只要破坏顺序（如出现在 Current body 内）即整条 malformed——防正文伪造 section 顶替。
      | ([$hidx[] | . as $i | (sectionkeys | index(seckey($L[$i])))]) as $seq
      | if $seq != ($seq | unique) then false
        elif (["Branch","SHA"] | index($f)) != null then
          any(range(0; $n);
            (($L[.] | trim) == ($f + ":"))
            and (. as $i
                 | (($hidx | map(select(. > $i)) | if length > 0 then .[0] else $n end) - 1) as $stop
                 | any(range($i + 1; $stop + 1); ($L[.] | trim | length) > 0)))
        else
          ([$hidx[]] | if length > 0 then .[0] else $n end) as $h0
          | any(range(0; $h0);
              ($L[.] | startswith($f + ": "))
              and (($L[.] as $ln | $ln[($f | length) + 2:]) | test("\\S")))
        end;
    . as $comments
    | ($comments | length) as $fetched_total
    | [$comments[] | select((.body // "") | startswith("<!-- dd-checkpoint:v1 -->"))] as $markers
    | ($markers | length) as $marker_candidates
    | [$markers[]
        | select(. as $c | (reqs | all(. as $f | hasfield($c.body; $f))))] as $valids
    | (($markers | length) - ($valids | length)) as $malformed
    | [$valids[]
        | { id: .id, created_at: .created_at, updated_at: .updated_at,
            wf: (.body | capture("workflow_id: (?<v>[^\n]+)")).v,
            cp: (.body | capture("checkpoint_id: (?<v>[^\n]+)")).v }] as $parsed
    | [$parsed[] | select(.wf == "'"$WF"'")] as $mine
    | ($mine | length) as $after_workflow_filter
    | ($mine | group_by(.cp) | map(sort_by(.id)[0])) as $firsts
    | (($mine | length) - ($firsts | length)) as $duplicates
    | ($firsts | sort_by(.id)[-1]) as $sel
    | "fetched_total=\($fetched_total) marker_candidates=\($marker_candidates) malformed=\($malformed) after_workflow_filter=\($after_workflow_filter) duplicates=\($duplicates)",
      "selected checkpoint_id=\($sel.cp) comment_id=\($sel.id) created_at=\($sel.created_at)",
      # 负样本自检（§3 事故 2 及外审 B-R-01 的回归门），全部必须为 false：
      # ① SHA: 空值后紧跟 "Blocker: none"——不得跨行误吞；
      # ② SHA: 下一行只有空格——纯空白不算值；
      # ③ 结构化区缺 SHA，仅正文 Current: 行中间出现 "SHA: fake"——非行首字段不得顶替。
      (("-- dd-checkpoint 样本 --\n\nworkflow_id: probe-wf-20261002T000000Z\nworkflow_type: feature-development\ncheckpoint_id: cp-fake-0001\nhost: codex\nstate_status: active\nremote: local-only\n\nBranch:\ndocs/task-tracking-projection\n\nSHA:\n\nBlocker:\nnone\n") | hasfield(.; "SHA")) as $n1
      | (("-- dd-checkpoint 样本 --\n\nworkflow_id: probe-wf-20261002T000000Z\nworkflow_type: feature-development\ncheckpoint_id: cp-fake-0002\nhost: codex\nstate_status: active\nremote: local-only\n\nBranch:\ndocs/task-tracking-projection\n\nSHA:\n   \nBlocker:\nnone\n") | hasfield(.; "SHA")) as $n2
      | (("-- dd-checkpoint 样本 --\n\nworkflow_id: probe-wf-20261002T000000Z\nworkflow_type: feature-development\ncheckpoint_id: cp-fake-0003\nhost: codex\nstate_status: active\nremote: local-only\n\nCurrent:\n例行核对（SHA: fake 仅为正文提及，非字段）\n\nNext:\nn/a.\n\nBranch:\ndocs/task-tracking-projection\n\nBlocker:\nnone\n\nTaken over from:\nnone\n") | hasfield(.; "SHA")) as $n3
      | "negative_sample_1_sha_empty_then_blocker_valid=\($n1) (expect false)",
        "negative_sample_2_sha_whitespace_next_line_valid=\($n2) (expect false)",
        "negative_sample_3_sha_only_in_prose_midline_valid=\($n3) (expect false)",
      # ⑤ Current body 内独立 "SHA:" 行（后跟 fake），正式 SHA section 缺失——
      #    破坏 canonical 顺序（Current→SHA→Next 违反 Current→Next→…），整条 malformed，必须 false。
      (("-- dd-checkpoint 样本 --\n\nworkflow_id: probe-wf-20261002T000000Z\nworkflow_type: feature-development\ncheckpoint_id: cp-fake-0005\nhost: codex\nstate_status: active\nremote: local-only\n\nCurrent:\n排查记录如下：\nSHA:\nfake\nNext:\nn/a.\n\nBranch:\ndocs/task-tracking-projection\n\nBlocker:\nnone\n") | hasfield(.; "SHA")) as $n5
        | "negative_sample_5_sha_in_current_body_canonical_order_violation_valid=\($n5) (expect false)",
      # ④ 结构化区缺 SHA，Current 正文独立一行 "SHA: fake"——非 section 头不得顶替（B-R-01 负样本）。
      (("-- dd-checkpoint 样本 --\n\nworkflow_id: probe-wf-20261002T000000Z\nworkflow_type: feature-development\ncheckpoint_id: cp-fake-0004\nhost: codex\nstate_status: active\nremote: local-only\n\nCurrent:\n排查记录如下：\nSHA: fake\nBranch: fake-ref\n\nNext:\nn/a.\n\nBlocker:\nnone\n") | hasfield(.; "SHA")) as $n4
        | "negative_sample_4_sha_prose_standalone_line_valid=\($n4) (expect false)"
'
} | tee "$OUT"

# 负样本自检门：三个负样本全部必须为 false；任一为 true 说明校验误吞/误放，取证失败。
for gate in \
  "negative_sample_1_sha_empty_then_blocker_valid=false (expect false)" \
  "negative_sample_2_sha_whitespace_next_line_valid=false (expect false)" \
  "negative_sample_3_sha_only_in_prose_midline_valid=false (expect false)" \
  "negative_sample_4_sha_prose_standalone_line_valid=false (expect false)" \
  "negative_sample_5_sha_in_current_body_canonical_order_violation_valid=false (expect false)"
do
  grep -q "$gate" "$OUT" || { echo "✋ 负样本自检失败：$gate" >&2; exit 1; }
done
echo "证据文件：$OUT"
