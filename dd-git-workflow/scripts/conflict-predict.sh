#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-git-workflow/scripts 配套脚本
# 用法: ./conflict-predict.sh [base-branch]
# 输出 ConflictPredictionReport JSON 到 stdout
# 依赖: git 2.55+（支持 merge-tree --write-tree --name-only）, jq

BASE="${1:-origin/develop}"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

git fetch origin develop:refs/remotes/origin/develop 2>/dev/null || true

# 使用 git merge-tree --write-tree --name-only 检测冲突（git 2.55+）
set +e
TREE_OUTPUT=$(git merge-tree --write-tree --name-only "$BASE" HEAD 2>&1)
EXIT_CODE=$?
set -e

if [ "$EXIT_CODE" -eq 0 ]; then
  printf '{"ConflictPredictionReport":{"branch":"%s","base":"%s","has_conflict":false,"conflict_files":[],"conflict_count":0,"severity":"none"}}\n' \
    "$CURRENT_BRANCH" "$BASE"
  exit 0
fi

# --name-only 模式：冲突文件直接以文件名列表输出（每行一个）
# 输出格式：<OID>\n<conflicted filenames>\n<messages>
# 提取 OID 行之后的文件名部分
TREE_OID=$(echo "$TREE_OUTPUT" | head -1)
CONFLICT_FILES=$(echo "$TREE_OUTPUT" | tail -n +2 | sed '/^$/q' | head -n -1 | grep -v '^$' || true)

if [ -z "$CONFLICT_FILES" ]; then
  # 兼容：回退到旧版 grep 解析
  CONFLICT_FILES=$(echo "$TREE_OUTPUT" | grep -oE 'Merge conflict in [^ ]+' | sed 's/Merge conflict in //' || true)
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
