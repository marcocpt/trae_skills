#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./branch-health.sh [base-branch]
# 输出 BranchHealthReport JSON 到 stdout
# 依赖: git 2.38+, macOS date（BSD）

BASE="${1:-origin/develop}"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git fetch origin develop:refs/remotes/origin/develop 2>/dev/null || true

# 1. 陈旧度：自最近一次同步 merge 后的天数
LAST_SYNC_DATE=$(git log -1 --format=%ci "${BASE}..HEAD" --merges --grep="sync develop" 2>/dev/null | cut -d' ' -f1 || echo "")
if [ -z "$LAST_SYNC_DATE" ]; then
  # 没有同步 merge commit，用分支与 base 的分叉点时间
  MERGE_BASE=$(git merge-base "$BASE" HEAD 2>/dev/null || echo "")
  if [ -n "$MERGE_BASE" ]; then
    LAST_SYNC_DATE=$(git log -1 --format=%ci "$MERGE_BASE" | cut -d' ' -f1)
  else
    LAST_SYNC_DATE=$(date +%Y-%m-%d)
  fi
fi

TODAY_TS=$(date +%s)
# macOS BSD date 解析 YYYY-MM-DD
LAST_TS=$(date -j -f "%Y-%m-%d" "$LAST_SYNC_DATE" +%s 2>/dev/null || echo "$TODAY_TS")
STALE_DAYS=$(( (TODAY_TS - LAST_TS) / 86400 ))
[ $STALE_DAYS -lt 0 ] && STALE_DAYS=0

# 2. 冲突难度：merge-tree 检测冲突文件数
CONFLICT_COUNT=0
if ! git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then
  CONFLICT_OUTPUT=$(git merge-tree --write-tree "$BASE" HEAD 2>&1 || true)
  CONFLICT_COUNT=$(echo "$CONFLICT_OUTPUT" | grep -cE 'Merge conflict in' || true)
fi

# 3. 变更规模：分支相对 base 的变更文件数
CHANGED_FILES=$(git diff --name-only "$BASE...HEAD" 2>/dev/null | wc -l | tr -d ' ')

# 4. 可合并性
if git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then
  MERGEABLE=true
  MERGEABLE_SCORE=100
else
  MERGEABLE=false
  MERGEABLE_SCORE=0
fi

# 评分计算
STALE_SCORE=$(( 100 - STALE_DAYS * 20 ))
[ $STALE_SCORE -lt 0 ] && STALE_SCORE=0
CONFLICT_SCORE=$(( 100 - CONFLICT_COUNT * 15 ))
[ $CONFLICT_SCORE -lt 0 ] && CONFLICT_SCORE=0
SCALE_SCORE=$(( 100 - (CHANGED_FILES - 5) * 3 ))
[ $SCALE_SCORE -lt 0 ] && SCALE_SCORE=0
[ $SCALE_SCORE -gt 100 ] && SCALE_SCORE=100

TOTAL=$(( (STALE_SCORE * 30 + CONFLICT_SCORE * 30 + SCALE_SCORE * 20 + MERGEABLE_SCORE * 20) / 100 ))

# 等级
if [ $TOTAL -ge 80 ]; then GRADE="healthy"
elif [ $TOTAL -ge 60 ]; then GRADE="watch"
elif [ $TOTAL -ge 40 ]; then GRADE="warning"
else GRADE="dangerous"
fi

# 告警
WARNINGS=""
[ $STALE_DAYS -gt 1 ] && WARNINGS="${WARNINGS}stale>${STALE_DAYS}d; "
[ "$CONFLICT_COUNT" -gt 5 ] && WARNINGS="${WARNINGS}conflict>${CONFLICT_COUNT}files; "
[ "$CHANGED_FILES" -gt 20 ] && WARNINGS="${WARNINGS}scale>${CHANGED_FILES}files; "
$MERGEABLE || WARNINGS="${WARNINGS}not-mergeable; "
[ -z "$WARNINGS" ] && WARNINGS="none"

printf '{"BranchHealthReport":{"branch":"%s","base":"%s","stale_days":%d,"conflict_files":%d,"changed_files":%d,"mergeable":%s,"scores":{"stale":%d,"conflict":%d,"scale":%d,"mergeable":%d,"total":%d},"grade":"%s","warnings":"%s"}}\n' \
  "$CURRENT_BRANCH" "$BASE" "$STALE_DAYS" "$CONFLICT_COUNT" "$CHANGED_FILES" "$MERGEABLE" \
  "$STALE_SCORE" "$CONFLICT_SCORE" "$SCALE_SCORE" "$MERGEABLE_SCORE" "$TOTAL" "$GRADE" "$WARNINGS"
