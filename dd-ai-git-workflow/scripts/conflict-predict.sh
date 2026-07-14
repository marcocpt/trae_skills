#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./conflict-predict.sh [base-branch]
# 输出 ConflictPredictionReport JSON 到 stdout
# 依赖: git 2.38+（支持 merge-tree --write-tree）, jq

BASE="${1:-origin/develop}"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git fetch origin develop:refs/remotes/origin/develop 2>/dev/null || true

# 使用 git merge-tree --write-tree 检测冲突（git 2.38+）
# 注意：不能用 `... || true` 后接 `$?`，否则退出码恒为 0
set +e
TREE_OUTPUT=$(git merge-tree --write-tree "$BASE" HEAD 2>&1)
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  printf '{"ConflictPredictionReport":{"branch":"%s","base":"%s","has_conflict":false,"conflict_files":[],"conflict_count":0,"severity":"none"}}\n' \
    "$CURRENT_BRANCH" "$BASE"
  exit 0
fi

# 解析冲突文件：git merge-tree --write-tree 在冲突时输出 "CONFLICT (content): Merge conflict in <file>"
CONFLICT_FILES=$(echo "$TREE_OUTPUT" | grep -oE 'Merge conflict in [^ ]+' | sed 's/Merge conflict in //' || true)

if [ -z "$CONFLICT_FILES" ]; then
  # 兼容旧版 git：回退到试合并检测
  # 用 trap 保护，避免脚本中途退出时卡在 merge 状态污染工作区
  trap 'git merge --abort 2>/dev/null || true' EXIT INT TERM
  CONFLICT_FILES=$(git merge --no-commit --no-ff "$BASE" 2>&1 | grep -oE 'CONFLICT .* in [^ ]+' | sed -E 's/.* in //' || true)
  git merge --abort 2>/dev/null || true
  trap - EXIT INT TERM
fi

CONFLICT_FILE_JSON=$(echo "$CONFLICT_FILES" | jq -R -s -c 'split("\n") | map(select(length > 0))')

CONFLICT_COUNT=$(echo "$CONFLICT_FILES" | grep -c . || true)
if [ "$CONFLICT_COUNT" -le 2 ]; then
  SEVERITY="low"
elif [ "$CONFLICT_COUNT" -le 5 ]; then
  SEVERITY="medium"
else
  SEVERITY="high"
fi

printf '{"ConflictPredictionReport":{"branch":"%s","base":"%s","has_conflict":true,"conflict_files":%s,"conflict_count":%d,"severity":"%s"}}\n' \
  "$CURRENT_BRANCH" "$BASE" "$CONFLICT_FILE_JSON" "$CONFLICT_COUNT" "$SEVERITY"
