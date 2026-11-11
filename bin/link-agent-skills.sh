#!/usr/bin/env bash
#
# link-agent-skills.sh — 把本仓库的 skill 软链安装到本机各 Agent 的用户级 skills 目录
#
# 幂等：可重复执行。只增不删，同名真实目录先备份再替换，非本仓库的自有 skill 一律不动。
#
# 用法：
#   ./bin/link-agent-skills.sh            # 执行同步，输出摘要
#   ./bin/link-agent-skills.sh --quiet    # 仅在发生变更时输出（给 git hook / launchd 用）
#   ./bin/link-agent-skills.sh --check    # 只检查不同步，全部就位返回 0，否则返回 1
#   ./bin/link-agent-skills.sh --dry-run  # 只报告将要做什么
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && /bin/pwd -P)"
SRC="$(cd "$SCRIPT_DIR/.." && /bin/pwd -P)"   # 仓库根；/bin/pwd -P 才会规范化大小写
BACKUP_ROOT="$HOME/.skill-link-backups"

QUIET=0; CHECK=0; DRY=0; NORM=0
for a in "$@"; do
  case "$a" in
    --quiet|-q) QUIET=1 ;;
    --check|-c) CHECK=1; DRY=1 ;;   # --check 必须严格只读
    --dry-run|-n) DRY=1 ;;
    --normalize) NORM=1 ;;          # 把写法/大小写不一致的链接统一成规范路径
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

# 判断两个路径是否指向同一个目录（bash 内建 -ef 按 dev+inode 比较，跟随软链；
# 规避大小写/写法差异导致的伪变更，且无子进程开销）
same_dir() {
  [ "$1" -ef "$2" ]
}

# 判断链接是否归本技能库所有：规范化目标路径，并校验其 git common dir
# 与本仓库一致（覆盖主仓库与任意 worktree，同时拒绝 /tmp/AGENT/skills 这类伪路径）
is_owned_link() {
  local link="$1" raw target d root common src_common
  raw="$(readlink "$link")" || return 1
  case "$raw" in
    /*) target="$raw" ;;
    *) target="$(dirname "$link")/$raw" ;;
  esac
  case "$target" in *"/../"*|*/..) return 1 ;; esac
  d="$(dirname "$target")"
  [ -d "$d" ] || return 1
  target="$(cd "$d" && pwd -P)/$(basename "$target")"
  d="$target"
  [ -d "$d" ] || d="$(dirname "$d")"
  root="$(git -C "$d" rev-parse --show-toplevel 2>/dev/null)" || return 1
  common="$(git -C "$d" rev-parse --git-common-dir 2>/dev/null)" || return 1
  common="$(cd "$d" && cd "$common" 2>/dev/null && pwd -P)" || return 1
  src_common="$(cd "$SRC" && git rev-parse --git-common-dir 2>/dev/null)" || return 1
  src_common="$(cd "$SRC" && cd "$src_common" 2>/dev/null && pwd -P)" || return 1
  [ "$common" = "$src_common" ] || return 1
  case "$target" in "$root"|"$root"/*) return 0 ;; esac
  return 1
}

run() {
  "$@" || { echo "错误：命令失败：$*" >&2; exit 1; }
}

# 旧名 -> 新名；用于清理仍指向其他存活 worktree 的旧名链接
LEGACY_MAP=(
  "abu-hotline:abu"
  "dd-ai-refactor-workflow:rfct"
  "dd-blackbox-device-testing:bbdt"
  "dd-bug-fast-track:bfix"
  "dd-bug-fix-workflow:bug"
  "dd-docreview-grilling:drev"
  "dd-feature-development-workflow:fdev"
  "dd-feature-fast-track:fft"
  "dd-file-task-queue:task"
  "dd-git-workflow:git"
  "dd-later-tracking:later"
  "dd-project-bootstrap-workflow:boot"
  "dd-project-docs:pdoc"
  "dd-workflow-runtime:wrt"
  "dd-writing-specs:spec"
  "dd-xctest-newbie-grilling-review:xtst"
  "detailed-log:dlog"
  "devboard-onboarding:dvb"
  "gpt-grilling-review:gpt"
  "macim-c-pilot-reannotation:macim"
  "macos-gui-probe-evidence:probe"
  "mcp-builder:mcp"
  "multi-agent-branch-integration:brch"
  "workflow-runner:flow"
  "writing-skills:skl"
)

# 目标：本机各 Agent app / CLI 的用户级 skills 目录
TARGETS=(
  "$HOME/.workbuddy-ai/skills"       # WorkBuddy AI
  "$HOME/.workbuddy/skills"          # WorkBuddy (legacy)
  "$HOME/.codex/skills"              # Codex CLI
  "$HOME/.config/opencode/skills"    # OpenCode
  "$HOME/.agents/skills"             # 通用 agents 目录
  "$HOME/.claude/skills"             # Claude Code
  "$HOME/.cursor/skills"             # Cursor
  "$HOME/.trae/skills"               # Trae CLI
  "$HOME/.trae-cn/skills"            # Trae CN
  "$HOME/.grok/skills"               # Grok CLI
  "$HOME/.openclaw-autoclaw/skills"  # AutoClaw / OpenClaw
  "$HOME/.codebuddy/skills"          # CodeBuddy
  "$HOME/.codebuddy1/skills"         # CodeBuddy (legacy profile)
)

# 收集源 skill：含 SKILL.md 的目录（docs/ 之类无 SKILL.md 的自动排除）
SKILLS=()
for d in "$SRC"/*/; do
  [ -f "${d}SKILL.md" ] && SKILLS+=("$(basename "$d")")
done
if [ ${#SKILLS[@]} -eq 0 ]; then
  echo "错误：$SRC 下没有找到任何含 SKILL.md 的 skill" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_ROOT/$STAMP"
BACKED_UP=0
CREATED=0; REPOINTED=0; REPLACED=0; PRUNED=0; ALREADY=0; CHANGED_DIRS=0
MIGRATED=0; CONFLICTS=0

log() { [ "$QUIET" -eq 1 ] || echo "$@"; }

for T in "${TARGETS[@]}"; do
  [ "$DRY" -eq 1 ] || run mkdir -p "$T"
  c_new=0; c_fix=0; c_rep=0; c_prune=0

  for s in "${SKILLS[@]}"; do
    src="$SRC/$s"; dst="$T/$s"
    if [ -L "$dst" ]; then
      cur="$(readlink "$dst")"
      if same_dir "$dst" "$src" && { [ "$NORM" -eq 0 ] || [ "$cur" = "$src" ]; }; then
        ALREADY=$((ALREADY+1)); continue
      fi
      if ! is_owned_link "$dst"; then
        CONFLICTS=$((CONFLICTS+1))
        log "  [冲突跳过] ${dst/#$HOME/~}  已存在非本库链接 -> $cur"
        continue
      fi
      [ "$DRY" -eq 1 ] || run ln -sfn "$src" "$dst"
      REPOINTED=$((REPOINTED+1)); c_fix=$((c_fix+1))
      log "  [重指] ${dst/#$HOME/~}  ($cur -> $src)"
    elif [ -e "$dst" ]; then
      if [ "$DRY" -eq 1 ]; then
        log "  [将备份替换] ${dst/#$HOME/~}"
      else
        run mkdir -p "$BACKUP/$T"; run mv "$dst" "$BACKUP/$T/$s"; run ln -sfn "$src" "$dst"
        BACKED_UP=1
        log "  [备份替换] ${dst/#$HOME/~} -> ${BACKUP/#$HOME/~}/$T/$s"
      fi
      REPLACED=$((REPLACED+1)); c_rep=$((c_rep+1))
    else
      [ "$DRY" -eq 1 ] || run ln -sfn "$src" "$dst"
      CREATED=$((CREATED+1)); c_new=$((c_new+1))
    fi
  done

  # 备份子目录按目标 app 区分，避免不同目标同名文件互相覆盖
  tsub="${T/#$HOME\//}"; tsub="${tsub//\//_}"

  # 清理：指向本仓库但目标已不存在的断链（源 skill 被删/改名）
  for e in "$T"/*; do
    [ -L "$e" ] || continue
    [ -e "$e" ] && continue                       # 有效链接，跳过
    tgt="$(readlink "$e")"
    is_owned_link "$e" || continue
    if [ "$DRY" -eq 1 ]; then
      log "  [将清理断链] ${e/#$HOME/~} -> $tgt"
    else
      run mkdir -p "$BACKUP/dangling/$tsub"; run mv "$e" "$BACKUP/dangling/$tsub/"
      BACKED_UP=1
      log "  [清理断链] ${e/#$HOME/~} (源已删除: $tgt)"
    fi
    PRUNED=$((PRUNED+1)); c_prune=$((c_prune+1))
  done

  # 迁移：旧名链接若仍指向其他存活 worktree，不会被断链清理捕获
  for pair in "${LEGACY_MAP[@]}"; do
    old="${pair%%:*}"; new="${pair#*:}"
    legacy="$T/$old"
    [ -L "$legacy" ] || continue
    is_owned_link "$legacy" || continue
    if [ -L "$T/$new" ]; then
      is_owned_link "$T/$new" || continue
    fi
    [ "$DRY" -eq 1 ] || same_dir "$T/$new" "$SRC/$new" || continue
    if [ "$DRY" -eq 1 ]; then
      log "  [将迁移旧名链接] ${legacy/#$HOME/~} -> $new"
    else
      run mkdir -p "$BACKUP/legacy/$tsub"
      run mv "$legacy" "$BACKUP/legacy/$tsub/$old"
      BACKED_UP=1
      log "  [迁移旧名链接] ${legacy/#$HOME/~} -> $new"
    fi
    MIGRATED=$((MIGRATED+1)); c_prune=$((c_prune+1))
  done

  if [ $((c_new+c_fix+c_rep+c_prune)) -gt 0 ]; then
    CHANGED_DIRS=$((CHANGED_DIRS+1))
    log "$(printf '%-42s 新增 %2d | 重指 %2d | 替换 %2d | 清理 %2d' "${T/#$HOME/~}" "$c_new" "$c_fix" "$c_rep" "$c_prune")"
  else
    log "$(printf '%-42s 已就位 (%d)' "${T/#$HOME/~}" "${#SKILLS[@]}")"
  fi
done

TOTAL=$((CREATED+REPOINTED+REPLACED+PRUNED+MIGRATED+CONFLICTS))
EXPECT=$(( ${#SKILLS[@]} * ${#TARGETS[@]} ))

if [ "$CHECK" -eq 1 ]; then
  if [ "$TOTAL" -gt 0 ] || [ "$CONFLICTS" -gt 0 ]; then
    echo "不同步：$TOTAL 处需要处理（源 ${#SKILLS[@]} 个 skill × ${#TARGETS[@]} 个目标 = 期望 $EXPECT 条；冲突 $CONFLICTS）" >&2
    exit 1
  fi
  echo "已同步：$EXPECT/$EXPECT 条链接全部就位"
  exit 0
fi

if [ "$TOTAL" -gt 0 ]; then
  echo "同步完成：新增 $CREATED | 重指 $REPOINTED | 替换 $REPLACED | 清理 $PRUNED | 迁移旧名 $MIGRATED | 冲突跳过 $CONFLICTS | 涉及 $CHANGED_DIRS 个目录（源 ${#SKILLS[@]} 个 skill）"
  [ "$BACKED_UP" -eq 1 ] && echo "备份：${BACKUP/#$HOME/~}"
else
  [ "$QUIET" -eq 1 ] || echo "无需变更：$EXPECT/$EXPECT 条链接全部就位"
fi
if [ "$CONFLICTS" -gt 0 ]; then
  echo "存在 $CONFLICTS 个非本库同名链接，已跳过未覆盖。" >&2
  exit 1
fi
exit 0
