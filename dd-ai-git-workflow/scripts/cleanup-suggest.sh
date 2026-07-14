#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./cleanup-suggest.sh [stale-days]
# 输出 CleanupSuggestion JSON 到 stdout
# 依赖: git 2.38+, jq, macOS date（BSD）

STALE_DAYS="${1:-7}"
BASE="origin/develop"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git fetch origin develop:refs/remotes/origin/develop 2>/dev/null || true
git fetch --prune origin 2>/dev/null || true

# 1. 已合并到 develop 的本地分支（排除当前分支、develop、main）
MERGED_BRANCHES=$(git branch --merged "$BASE" 2>/dev/null | grep -vE '^\*|develop$|main$|'"$CURRENT_BRANCH"'$' | sed 's/^ *//' | grep -v '^$' || true)
MERGED_JSON=$(echo "$MERGED_BRANCHES" | jq -R -s -c 'split("\n") | map(select(length > 0))')

# 2. 陈旧 worktree（超过 N 天无活动）
STALE_WORKTREES_JSON="[]"
TODAY_TS=$(date +%s)
WORKTREE_PATHS=$(git worktree list --porcelain | grep '^worktree ' | sed 's/^worktree //')

while IFS= read -r wt_path; do
  [ -z "$wt_path" ] && continue
  [ "$wt_path" = "$(git rev-parse --show-toplevel)" ] && continue  # 跳过主 worktree

  LAST_COMMIT_DATE=$(git -C "$wt_path" log -1 --format=%ci 2>/dev/null | cut -d' ' -f1 || echo "")
  [ -z "$LAST_COMMIT_DATE" ] && continue

  LAST_TS=$(date -j -f "%Y-%m-%d" "$LAST_COMMIT_DATE" +%s 2>/dev/null || echo "$TODAY_TS")
  AGE_DAYS=$(( (TODAY_TS - LAST_TS) / 86400 ))

  if [ $AGE_DAYS -ge $STALE_DAYS ]; then
    WT_BRANCH=$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "detached")
    IS_MERGED=false
    if [ "$WT_BRANCH" != "detached" ] && git branch --merged "$BASE" 2>/dev/null | grep -q "$WT_BRANCH"; then
      IS_MERGED=true
    fi
    STALE_WORKTREES_JSON=$(echo "$STALE_WORKTREES_JSON" | jq -c \
      '. += [{"path":"'"$wt_path"'","branch":"'"$WT_BRANCH"'","age_days":'"$AGE_DAYS"',"merged":'"$IS_MERGED"'}]')
  fi
done <<< "$WORKTREE_PATHS"

# 3. 孤儿 worktree（元数据残留）
ORPHAN_COUNT=$(git worktree list --porcelain | grep '^worktree ' | while IFS= read -r line; do
  wt_path=$(echo "$line" | sed 's/^worktree //')
  [ -d "$wt_path" ] || echo "orphan"
done | wc -l | tr -d ' ')

printf '{"CleanupSuggestion":{"merged_branches":%s,"stale_worktrees":%s,"orphan_worktrees":%d,"stale_threshold_days":%d,"current_branch":"%s"}}\n' \
  "$MERGED_JSON" "$STALE_WORKTREES_JSON" "$ORPHAN_COUNT" "$STALE_DAYS" "$CURRENT_BRANCH"
