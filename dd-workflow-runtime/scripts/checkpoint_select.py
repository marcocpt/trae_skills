#!/usr/bin/env python3
"""§6.1 checkpoint 选取的 canonical 机械实现。

语义属主：dd-workflow-runtime/references/task-tracking.md §6.1（本文件是其
机械实现；L02-checkpoint-probe.sh 为取证证据，不作为运行时实现）。

输入（stdin）：评论 JSON——兼容三种形态：
  1. 单页数组（[comment, ...]）；
  2. gh api --paginate 的多页拼接文档（[...][...]）；
  3. gh api --paginate --slurp 的页数组（[[...], [...]]）。

输出（stdout）：KEY=VALUE 行，供 shell grep 消费：
  selected_id=<comment id 或空>
  selected_state=<state_status 或空>
  selected_checkpoint_id=<checkpoint_id 或空>
  fetched_total=N marker_candidates=N malformed=N after_workflow_filter=N duplicates=N

选项：--workflow-id <id> 按 §6.1 第 3 条过滤；缺省不过滤（如 guard 场景：
一张 Issue 只绑定一个 workflow，见 task-tracking.md §3）。
"""

from __future__ import annotations

import argparse
import json
import sys

MARKER = "<!-- dd-checkpoint:v1 -->"
SAME_LINE_FIELDS = ("workflow_id", "workflow_type", "checkpoint_id", "host", "state_status", "remote")
SECTION_FIELDS = ("Branch", "SHA")
SECTION_ORDER = ("Current", "Next", "Branch", "SHA", "Blocker", "Taken over from")
REQUIRED_FIELDS = SAME_LINE_FIELDS + SECTION_FIELDS


def load_documents(text: str) -> list:
    """解析单个或拼接的 JSON 文档（gh --paginate 的多页输出）。"""
    decoder = json.JSONDecoder()
    docs: list = []
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx] in " \t\r\n":
            idx += 1
        if idx >= n:
            break
        obj, end = decoder.raw_decode(text, idx)
        docs.append(obj)
        idx = end
    return docs


def flatten(docs: list) -> list:
    """把页数组/单页数组统一展开成评论 dict 列表。"""
    out: list = []

    def walk(obj) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            out.append(obj)

    for doc in docs:
        walk(doc)
    return out


def has_field(body: str, field: str) -> bool:
    """§6.1 第 2 条：字段资格判定（结构化区限定，正文提及不算）。"""
    lines = body.split("\n")
    n = len(lines)
    hdr_idx = [
        i
        for i in range(n)
        if lines[i].strip().endswith(":") and lines[i].strip()[:-1] in SECTION_ORDER
    ]
    seq = [SECTION_ORDER.index(lines[i].strip()[:-1]) for i in hdr_idx]
    if seq != sorted(set(seq)):
        return False  # section 头顺序破坏 canonical 序（如 Current 正文内伪造 SHA: 行）
    if field in SECTION_FIELDS:
        for i in hdr_idx:
            if lines[i].strip() == field + ":":
                stop = next((h for h in hdr_idx if h > i), n) - 1
                if any(lines[j].strip() for j in range(i + 1, stop + 1)):
                    return True
        return False
    prefix = field + ": "
    h0 = hdr_idx[0] if hdr_idx else n
    return any(
        lines[i].startswith(prefix) and lines[i][len(prefix):].strip() for i in range(h0)
    )


def header_value(body: str, field: str) -> str:
    prefix = field + ": "
    for line in body.split("\n"):
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return ""


def select(comments: list, workflow_id: str | None, trusted_associations: tuple = ()) -> dict:
    counts = {
        "fetched_total": len(comments),
        "marker_candidates": 0,
        "malformed": 0,
        "untrusted": 0,
        "after_workflow_filter": 0,
        "duplicates": 0,
    }
    markers = [
        c
        for c in comments
        if isinstance(c, dict) and isinstance(c.get("body"), str) and c["body"].startswith(MARKER)
    ]
    counts["marker_candidates"] = len(markers)
    valids = [c for c in markers if all(has_field(c["body"], f) for f in REQUIRED_FIELDS)]
    counts["malformed"] = counts["marker_candidates"] - len(valids)
    if trusted_associations:
        # 来源真实性门：checkpoint 须来自有仓库写权限的作者（伪造 terminal 不新增特权）；
        # 不可信来源（如 NONE/CONTRIBUTOR）整条丢弃，防绕过防线
        trusted = [
            c
            for c in valids
            if c.get("author_association") in trusted_associations
        ]
        counts["untrusted"] = len(valids) - len(trusted)
        valids = trusted
    parsed = [
        {
            "id": c["id"],
            "state": header_value(c["body"], "state_status"),
            "cp": header_value(c["body"], "checkpoint_id"),
            "wf": header_value(c["body"], "workflow_id"),
        }
        for c in valids
    ]
    mine = [p for p in parsed if workflow_id is None or p["wf"] == workflow_id]
    counts["after_workflow_filter"] = len(mine)
    firsts: dict = {}
    for p in sorted(mine, key=lambda x: x["id"]):
        firsts.setdefault(p["cp"], p)  # 同 checkpoint_id 取首投（最小 comment id）
    counts["duplicates"] = len(mine) - len(firsts)
    selected = max(firsts.values(), key=lambda x: x["id"]) if firsts else None
    return {"selected": selected, "counts": counts}


def main() -> int:
    parser = argparse.ArgumentParser(description="task-tracking §6.1 checkpoint 选取")
    parser.add_argument("--workflow-id", default=None)
    parser.add_argument(
        "--author-associations",
        default="",
        help="逗号分隔的可信 author_association 集合（如 OWNER,COLLABORATOR,MEMBER）；"
        "非空时丢弃不可信来源的 checkpoint（来源真实性门）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON（测试用）")
    args = parser.parse_args()
    trusted = tuple(a.strip() for a in args.author_associations.split(",") if a.strip())

    comments = flatten(load_documents(sys.stdin.read()))
    result = select(comments, args.workflow_id, trusted)
    selected, counts = result["selected"], result["counts"]

    if args.json:
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(f"selected_id={selected['id'] if selected else ''}")
    print(f"selected_state={selected['state'] if selected else ''}")
    print(f"selected_checkpoint_id={selected['cp'] if selected else ''}")
    print(
        "fetched_total={fetched_total} marker_candidates={marker_candidates} "
        "malformed={malformed} untrusted={untrusted} "
        "after_workflow_filter={after_workflow_filter} "
        "duplicates={duplicates}".format(**counts)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
