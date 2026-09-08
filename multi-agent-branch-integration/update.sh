#!/usr/bin/env bash
#
# update.sh — 更新 Skill 管理的 runtime，保留项目本地策略。
#
# 用法：
#     /path/to/multi-agent-branch-integration/update.sh [目标目录] [--force-managed-files]
#
# 允许更新：
#   - scripts/branchctl
#   - .githooks/pre-push
#   - 受 Skill marker 管理的 .github/workflows/branch-policy-check.yml
#   - AGENTS.md 中 marker 之间的 Skill 片段
#
# 绝不覆盖：
#   - .agent/branch-policy.yaml（项目本地策略）
#   - AGENTS.md 中 marker 之外的任何内容
#
# 本地修改过受管文件时默认报冲突并退出非 0，
# 只有显式给出 --force-managed-files 才强制覆盖。
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER_START="<!-- multi-agent-branch-integration:start -->"
MARKER_END="<!-- multi-agent-branch-integration:end -->"
WORKFLOW_MARKER="managed by multi-agent-branch-integration"
MANIFEST=".agent/.branchctl-managed"

log() { printf 'update: %s\n' "$*"; }
fail() {
  printf 'update: ERROR: %s\n' "$*" >&2
  exit 1
}

sha_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    fail "找不到 sha256sum / shasum，无法校验受管文件。"
  fi
}

FORCE="false"
TARGET="."
for arg in "$@"; do
  case "$arg" in
    --force-managed-files) FORCE="true" ;;
    -h|--help)
      printf '用法： update.sh [目标目录] [--force-managed-files]\n'
      exit 0
      ;;
    *)
      if [ "$TARGET" = "." ]; then
        TARGET="$arg"
      else
        fail "未知参数：${arg}。"
      fi
      ;;
  esac
done
TARGET="$(cd "$TARGET" 2>/dev/null && pwd || fail "目标目录不存在：$TARGET")"
MARKER_ERROR=""

git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1 \
  || fail "目标不是 Git 仓库：${TARGET}。"

SRC_BRANCHCTL="$SKILL_DIR/runtime/branchctl"
SRC_PREPUSH="$SKILL_DIR/runtime/pre-push"
SRC_WORKFLOW="$SKILL_DIR/templates/github/branch-policy-check.yml"
SRC_FRAGMENT="$SKILL_DIR/templates/AGENTS.fragment.md"
[ -f "$SRC_BRANCHCTL" ] || fail "Skill 目录不完整：缺少 runtime/branchctl。"

policy_integration_branch() {
  local v=""
  v="$(sed -n 's/^integration_branch:[[:space:]]*//p' "$1" 2>/dev/null | head -n 1 || true)"
  v="$(printf '%s' "$v" | tr -d '[:space:]' | tr -d "\"'")"
  case "$v" in
    ''|*[[:space:]]*) printf 'develop' ;;
    *) printf '%s' "$v" ;;
  esac
}

recorded_sha() {
  # recorded_sha <相对路径>：从指纹清单取期望值，无清单返回空。
  local rel="$1" line
  [ -f "$TARGET/$MANIFEST" ] || return 0
  line="$(grep -F "  $rel" "$TARGET/$MANIFEST" | head -n 1 || true)"
  [ -n "$line" ] || return 0
  printf '%s' "${line%% *}"
}

check_managed() {
  # check_managed <相对路径> <新文件>：返回 0 可更新 / 1 冲突。
  local rel="$1" src="$2"
  local dst="$TARGET/$rel"
  local want cur fresh
  want="$(recorded_sha "$rel")"
  if [ ! -f "$dst" ]; then
    return 0
  fi
  cur="$(sha_file "$dst")"
  fresh="$(sha_file "$src")"
  if [ "$cur" = "$fresh" ]; then
    return 0
  fi
  if [ -n "$want" ] && [ "$cur" = "$want" ]; then
    # 与上次安装一致、无本地修改，可安全更新。
    return 0
  fi
  if [ -z "$want" ]; then
    # 无指纹基线且内容与新版不同：无法区分本地修改，保守视为冲突。
    return 1
  fi
  return 1
}

CONFLICTS=""

maybe_update() {
  local rel="$1" src="$2" mode="$3"
  local dst="$TARGET/$rel"
  if [ "$FORCE" = "true" ]; then
    install -m "$mode" "$src" "$dst"
    log "已强制更新 ${rel}（--force-managed-files）。"
    return 0
  fi
  if check_managed "$rel" "$src"; then
    install -m "$mode" "$src" "$dst"
    log "已更新 ${rel}。"
  else
    CONFLICTS="$CONFLICTS $rel"
    printf 'update: CONFLICT: %s 有本地修改，拒绝静默覆盖（加 --force-managed-files 可强制）。\n' "$rel" >&2
  fi
}

mkdir -p "$TARGET/scripts" "$TARGET/.githooks"

maybe_update "scripts/branchctl" "$SRC_BRANCHCTL" "0755"
maybe_update ".githooks/pre-push" "$SRC_PREPUSH" "0755"

# workflow：只动 marker 管理的文件，且按项目策略重新渲染分支名。
WORKFLOW="$TARGET/.github/workflows/branch-policy-check.yml"
RENDERED_WF=""
if [ -f "$WORKFLOW" ]; then
  if grep -qF "$WORKFLOW_MARKER" "$WORKFLOW"; then
    RENDERED_WF="$(mktemp 2>/dev/null || printf '')"
    [ -n "$RENDERED_WF" ] || fail "无法创建临时文件。"
    WF_IB="$(policy_integration_branch "$TARGET/.agent/branch-policy.yaml")"
    WF_IB_ESC="$(printf '%s' "$WF_IB" | sed 's/[&|\\]/\\&/g')"
    sed "s|__INTEGRATION_BRANCH__|$WF_IB_ESC|g" "$SRC_WORKFLOW" >"$RENDERED_WF"
    maybe_update ".github/workflows/branch-policy-check.yml" "$RENDERED_WF" "0644"
  else
    log "branch-policy-check.yml 非 marker 管理，跳过。"
  fi
else
  mkdir -p "$TARGET/.github/workflows"
  RENDERED_WF="$(mktemp 2>/dev/null || printf '')"
  [ -n "$RENDERED_WF" ] || fail "无法创建临时文件。"
  WF_IB2="$(policy_integration_branch "$TARGET/.agent/branch-policy.yaml")"
  WF_IB2_ESC="$(printf '%s' "$WF_IB2" | sed 's/[&|\\]/\\&/g')"
  sed "s|__INTEGRATION_BRANCH__|$WF_IB2_ESC|g" "$SRC_WORKFLOW" >"$RENDERED_WF"
  install -m 0644 "$RENDERED_WF" "$WORKFLOW"
  log "已补装 .github/workflows/branch-policy-check.yml（已记入受管指纹）。"
fi

# AGENTS.md marker 片段刷新（marker 外内容原样保留）。
# 完整矩阵（F-MABI-003）：不存在→创建；0/0→追加；1/1 且有序→刷新；
# 其余一切组合（缺 end、孤儿 end、重复、错序）一律 fail-closed，碰都不碰。
if [ ! -f "$TARGET/AGENTS.md" ]; then
  {
    printf '# AGENTS.md\n\n'
    printf '%s\n' "$MARKER_START"
    cat "$SRC_FRAGMENT"
    printf '%s\n' "$MARKER_END"
  } >"$TARGET/AGENTS.md"
  log "AGENTS.md 不存在，已创建（含接入片段）。"
else
  starts="$(grep -cF "$MARKER_START" "$TARGET/AGENTS.md" || true)"
  ends="$(grep -cF "$MARKER_END" "$TARGET/AGENTS.md" || true)"
  start_line="$(grep -nF "$MARKER_START" "$TARGET/AGENTS.md" | head -n 1 | cut -d: -f1 || true)"
  end_line="$(grep -nF "$MARKER_END" "$TARGET/AGENTS.md" | head -n 1 | cut -d: -f1 || true)"
  if [ -z "$end_line" ]; then end_line="0"; fi
  if [ -z "$start_line" ]; then start_line="0"; fi
  if [ "$starts" = "0" ] && [ "$ends" = "0" ]; then
    {
      cat "$TARGET/AGENTS.md"
      printf '\n%s\n' "$MARKER_START"
      cat "$SRC_FRAGMENT"
      printf '%s\n' "$MARKER_END"
    } >"$TARGET/AGENTS.md.tmp"
    mv "$TARGET/AGENTS.md.tmp" "$TARGET/AGENTS.md"
    log "AGENTS.md 缺少 marker，已追加片段（原有内容未动）。"
  elif [ "$starts" = "1" ] && [ "$ends" = "1" ] && [ "$start_line" -lt "$end_line" ]; then
    awk -v start="$MARKER_START" -v end="$MARKER_END" -v frag="$SRC_FRAGMENT" '
      $0 == start { print; while ((getline line < frag) > 0) print line; close(frag); skip = 1; next }
      $0 == end { skip = 0; print; next }
      !skip { print }
    ' "$TARGET/AGENTS.md" >"$TARGET/AGENTS.md.tmp"
    mv "$TARGET/AGENTS.md.tmp" "$TARGET/AGENTS.md"
    log "已刷新 AGENTS.md 内 marker 片段（外部内容未动）。"
  else
    printf 'update: ERROR: AGENTS.md 的 Skill marker 残缺或错乱（start=%s end=%s），拒绝修改该文件，其它更新继续。\n' "$starts" "$ends" >&2
    MARKER_ERROR="AGENTS.md"
  fi
fi

# 项目策略：只读确认，永远不碰。
if [ -f "$TARGET/.agent/branch-policy.yaml" ]; then
  log "项目策略 .agent/branch-policy.yaml 未动（属项目所有）。"
else
  log "提示：项目缺少 .agent/branch-policy.yaml，可用 install.sh 补建（update.sh 不创建策略文件）。"
fi

# hook 路径：缺失则补设，已有其它值则告警不覆盖。
existing_hooks="$(git -C "$TARGET" config --get core.hooksPath || true)"
if [ -z "$existing_hooks" ]; then
  git -C "$TARGET" config core.hooksPath .githooks
  log "已补设 core.hooksPath=.githooks。"
elif [ "$existing_hooks" != ".githooks" ]; then
  printf 'update: WARN: core.hooksPath 已有自定义值（%s），不覆盖。\n' "$existing_hooks" >&2
fi

# 刷新指纹清单：只有内容已与新版一致的文件才记录新指纹；
# 存在冲突的文件保留旧基线，下次仍会报冲突（不把本地修改洗白）。
refresh_entry() {
  local rel="$1" src="$2"
  local dst="$TARGET/$rel"
  local cur fresh want
  [ -f "$dst" ] || return 0
  cur="$(sha_file "$dst")"
  fresh="$(sha_file "$src")"
  if [ "$cur" = "$fresh" ]; then
    printf '%s  %s\n' "$fresh" "$rel"
    return 0
  fi
  want="$(recorded_sha "$rel")"
  if [ -n "$want" ]; then
    printf '%s  %s\n' "$want" "$rel"
  fi
  return 0
}

{
  refresh_entry "scripts/branchctl" "$SRC_BRANCHCTL"
  refresh_entry ".githooks/pre-push" "$SRC_PREPUSH"
  if [ -n "$RENDERED_WF" ] && [ -f "$WORKFLOW" ] && grep -qF "$WORKFLOW_MARKER" "$WORKFLOW"; then
    refresh_entry ".github/workflows/branch-policy-check.yml" "$RENDERED_WF"
    rm -f "$RENDERED_WF"
  fi
} >"$TARGET/$MANIFEST"

if [ -n "$CONFLICTS" ]; then
  printf 'update: ERROR: 以下受管文件存在本地修改未更新：%s\n' "$CONFLICTS" >&2
  exit 1
fi

if [ -n "$MARKER_ERROR" ]; then
  printf 'update: ERROR: %s 的 marker 异常未处理，整体以失败退出（其它文件已正常更新）。\n' "$MARKER_ERROR" >&2
  exit 1
fi

log "更新完成。"
