#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./pre-merge-check.sh
# 输出 PreMergeChecklist JSON 到 stdout
# 依赖: git 2.38+, swiftlint（可选）

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
BASE="origin/develop"
CHECKS_OK=true
RESULTS=()

git fetch origin develop:refs/remotes/origin/develop 2>/dev/null || true

# 1. 未提交文件检查
UNSTAGED=$(git status --porcelain | wc -l | tr -d ' ')
if [ "$UNSTAGED" -gt 0 ]; then
  RESULTS+=('"uncommitted_files":{"status":"fail","count":'"$UNSTAGED"'}')
  CHECKS_OK=false
else
  RESULTS+=('"uncommitted_files":{"status":"pass","count":0}')
fi

# 2. SwiftLint strict（仅在存在 .swift 文件变更时检查）
SWIFT_CHANGED=$(git diff --name-only "$BASE...HEAD" | grep -c '\.swift$' || true)
if [ "$SWIFT_CHANGED" -gt 0 ]; then
  if command -v swiftlint >/dev/null 2>&1; then
    if swiftlint lint --strict >/dev/null 2>&1; then
      RESULTS+=('"swiftlint":{"status":"pass","files_checked":'"$SWIFT_CHANGED"'}')
    else
      RESULTS+=('"swiftlint":{"status":"fail","files_checked":'"$SWIFT_CHANGED"'}')
      CHECKS_OK=false
    fi
  else
    RESULTS+=('"swiftlint":{"status":"skip","reason":"swiftlint not installed"}')
  fi
else
  RESULTS+=('"swiftlint":{"status":"skip","reason":"no swift changes"}')
fi

# 3. 文档同步检查（swift 变更但无 docs 变更时告警）
DOCS_CHANGED=$(git diff --name-only "$BASE...HEAD" | grep -c '^docs/' || true)
SRC_CHANGED=$(git diff --name-only "$BASE...HEAD" | grep -c '\.swift$' || true)
if [ "$SRC_CHANGED" -gt 0 ] && [ "$DOCS_CHANGED" -eq 0 ]; then
  RESULTS+=('"doc_sync":{"status":"warn","reason":"swift changes without docs update","swift_files":'"$SRC_CHANGED"',"docs_files":0}')
else
  RESULTS+=('"doc_sync":{"status":"pass","swift_files":'"$SRC_CHANGED"',"docs_files":'"$DOCS_CHANGED"'}')
fi

# 4. 冲突预检
CONFLICT_COUNT=0
if git merge-tree --write-tree "$BASE" HEAD >/dev/null 2>&1; then
  RESULTS+=('"conflict_predict":{"status":"pass","conflict_files":0}')
else
  CONFLICT_COUNT=$(git merge-tree --write-tree "$BASE" HEAD 2>&1 | grep -cE 'Merge conflict in' || true)
  RESULTS+=('"conflict_predict":{"status":"fail","conflict_files":'"$CONFLICT_COUNT"'}')
  CHECKS_OK=false
fi

# 5. 与 develop 同步检查
AHEAD=$(git rev-list --count "$BASE..HEAD" 2>/dev/null || echo 0)
BEHIND=$(git rev-list --count "HEAD..$BASE" 2>/dev/null || echo 0)
if [ "$BEHIND" -gt 0 ]; then
  RESULTS+=('"sync":{"status":"warn","ahead":'"$AHEAD"',"behind":'"$BEHIND"',"reason":"branch behind develop, run daily-sync"}')
else
  RESULTS+=('"sync":{"status":"pass","ahead":'"$AHEAD"',"behind":0}')
fi

# 6. Build 检查（提示手动执行）
# 注意：用 compgen -G 而非 ls，避免 pipefail 下无匹配时整条管道失败
HAS_XCODE_PROJ=false
if compgen -G "*.xcodeproj" > /dev/null || compgen -G "*.xcworkspace" > /dev/null; then
  HAS_XCODE_PROJ=true
fi
if [ "$HAS_XCODE_PROJ" = "true" ]; then
  RESULTS+=('"build":{"status":"manual","reason":"run xcodebuild or project test script"}')
else
  RESULTS+=('"build":{"status":"skip","reason":"no xcode project detected"}')
fi

# 7. 测试检查（提示手动执行）
RESULTS+=('"tests":{"status":"manual","reason":"run project test script (e.g. scripts/ci/test-macos.sh)"}')

# 8. 公共文件检查（commit 是否含 PublicFile tag）
PUBLIC_FILE_COMMITS=$(git log "$BASE..HEAD" --grep="PublicFile:" --oneline | wc -l | tr -d ' ')
if [ "$PUBLIC_FILE_COMMITS" -gt 0 ]; then
  RESULTS+=('"public_file":{"status":"warn","commits":'"$PUBLIC_FILE_COMMITS"',"reason":"public file modified, ensure isolated branch"}')
else
  RESULTS+=('"public_file":{"status":"pass","commits":0}')
fi

# 9. 公共文件分支年龄检测（含 PublicFile: tag 的 commit 必须 <1 天合并）
# 取 merge-base 后最早 commit 日期与今天对比
PUBLIC_FILE_AGE_OK=true
PUBLIC_FILE_AGE_DAYS=0
if [ "$PUBLIC_FILE_COMMITS" -gt 0 ]; then
  MERGE_BASE=$(git merge-base "$BASE" HEAD 2>/dev/null || echo "")
  if [ -n "$MERGE_BASE" ]; then
    EARLIEST_DATE=$(git log --format=%cd --date=short "${MERGE_BASE}..HEAD" 2>/dev/null | sort | head -1 || echo "")
    if [ -n "$EARLIEST_DATE" ]; then
      TODAY_TS=$(date +%s)
      EARLY_TS=$(date -j -f "%Y-%m-%d" "$EARLIEST_DATE" +%s 2>/dev/null || echo "$TODAY_TS")
      PUBLIC_FILE_AGE_DAYS=$(( (TODAY_TS - EARLY_TS) / 86400 ))
      [ "$PUBLIC_FILE_AGE_DAYS" -lt 0 ] && PUBLIC_FILE_AGE_DAYS=0
      if [ "$PUBLIC_FILE_AGE_DAYS" -gt 1 ]; then
        PUBLIC_FILE_AGE_OK=false
      fi
    fi
  fi
  if [ "$PUBLIC_FILE_AGE_OK" = "true" ]; then
    RESULTS+=('"public_file_age":{"status":"pass","age_days":'"$PUBLIC_FILE_AGE_DAYS"',"reason":"public file branch within 1 day"}')
  else
    RESULTS+=('"public_file_age":{"status":"fail","age_days":'"$PUBLIC_FILE_AGE_DAYS"',"reason":"public file branch exceeds 1 day, merge immediately"}')
    CHECKS_OK=false
  fi
else
  RESULTS+=('"public_file_age":{"status":"skip","reason":"no public file commits"}')
fi

# 10. 跨模块修改检查（无 CrossModule: tag 时告警）
# 检测修改文件是否跨多个顶层模块目录（带 / 的路径），无 CrossModule: tag 则 warn
CHANGED_FILES_LIST=$(git diff --name-only "$BASE...HEAD" 2>/dev/null || true)
MODULE_DIRS=$(echo "$CHANGED_FILES_LIST" | grep '/' | sed -E 's|^([^/]+)/.*|\1|' | sort -u | grep -v '^$' || true)
MODULE_COUNT=$(echo "$MODULE_DIRS" | grep -c . || true)
CROSSMODULE_COMMITS=$(git log "$BASE..HEAD" --grep="CrossModule:" --oneline | wc -l | tr -d ' ')
if [ "$MODULE_COUNT" -gt 1 ]; then
  if [ "$CROSSMODULE_COMMITS" -gt 0 ]; then
    RESULTS+=('"cross_module":{"status":"pass","modules":'"$MODULE_COUNT"',"declared_commits":'"$CROSSMODULE_COMMITS"'}')
  else
    RESULTS+=('"cross_module":{"status":"warn","modules":'"$MODULE_COUNT"',"declared_commits":0,"reason":"cross-module changes without CrossModule: tag"}')
  fi
else
  RESULTS+=('"cross_module":{"status":"pass","modules":'"$MODULE_COUNT"',"declared_commits":0}')
fi

# 拼接 JSON
JOIN_RESULTS=$(printf '%s,' "${RESULTS[@]}" | sed 's/,$//')
printf '{"PreMergeChecklist":{"branch":"%s","base":"%s","all_pass":%s,"checks":{%s}}}\n' \
  "$CURRENT_BRANCH" "$BASE" "$CHECKS_OK" "$JOIN_RESULTS"
