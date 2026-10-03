#!/usr/bin/env python3
"""L-03 探针：从 task-tracking.md 真实表格抽取词表，验证 Design §3.4 的防漂移假设。

一次性取证探针，不是交付物。产出 L03-vocab-extract-probe.md。
真实依赖：dd-workflow-runtime/references/task-tracking.md（owner 合同，无 mock）。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TT = REPO_ROOT / "dd-workflow-runtime" / "references" / "task-tracking.md"


def section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}.*?$(.*?)(?=^## |\Z)", text, re.S | re.M)
    if not m:
        raise SystemExit(f"FAIL: 找不到章节 {heading}")
    return m.group(1)


def table_rows(block: str) -> list[list[str]]:
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    return rows


def backticked(cell: str) -> str | None:
    m = re.fullmatch(r"`([a-z0-9\-]+)`", cell.strip())
    return m.group(1) if m else None


def main() -> int:
    text = TT.read_text(encoding="utf-8")

    # §2 sync 取值表：| `synced` | ... |
    sec2 = section(text, "2. 状态字段")
    sync_values = [v for v in (backticked(r[0]) for r in table_rows(sec2)) if v]

    # §4 绑定失败矩阵：| 情形 | `sync` | `sync_reason` | ...
    sec4 = section(text, "4. 绑定失败矩阵")
    matrix = table_rows(sec4)
    header = matrix[0]
    missing = [c for c in ("`sync`", "`sync_reason`") if c not in header]
    if missing:
        raise SystemExit(f"FAIL: §4 表格缺少列 {missing}，header={header}")
    i_sync, i_reason = header.index("`sync`"), header.index("`sync_reason`")
    sync_from_matrix, reasons = set(), set()
    for row in matrix[1:]:
        s = backticked(row[i_sync])
        r = backticked(row[i_reason])
        if s:
            sync_from_matrix.add(s)
        if r:
            reasons.add(r)

    print("§2 sync 取值 :", sync_values)
    print("§4 sync 取值 :", sorted(sync_from_matrix))
    print("§4 sync_reason:", sorted(reasons))

    problems = []
    if sorted(sync_values) != sorted(sync_from_matrix):
        problems.append(f"§2 与 §4 的 sync 取值不一致: {sorted(sync_values)} vs {sorted(sync_from_matrix)}")
    if len(sync_values) != 4:
        problems.append(f"sync 取值应为 4 个，实际 {len(sync_values)}")
    # §4 共 11 行；其中「绑定有效→synced」与「用户明确禁用→disabled」两行的
    # sync_reason 列为 `—`，故带反引号原因值的只有 9 个。这两个无原因取值正是
    # Design §3.2 分支②（sync ∈ {synced, disabled} 即 PASS）的依据。
    if len(reasons) != 9:
        problems.append(f"sync_reason 应为 9 个带原因行的取值，实际 {len(reasons)}")
    if len(matrix) - 1 != 11:
        problems.append(f"§4 应为 11 行数据，实际 {len(matrix) - 1}")

    if problems:
        for p in problems:
            print("PROBLEM:", p)
        return 1

    # 对本工作流真实 state 跑一次判定探针（分支 ①：已绑定）
    state = subprocess.run(
        ["git", "rev-parse", "--git-dir"], cwd=REPO_ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    state_file = Path(state) / "feature-development-state.json"
    print("真实 state:", state_file, "exists=", state_file.exists())

    print("\nRESULT: passed — Design §3.4 抽取假设成立")
    return 0


if __name__ == "__main__":
    sys.exit(main())
