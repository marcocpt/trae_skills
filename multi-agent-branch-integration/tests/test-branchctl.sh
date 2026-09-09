#!/usr/bin/env bash
#
# test-branchctl.sh — multi-agent-branch-integration 合同测试。
#
# 所有破坏性 Git 操作（rebase / merge / integrate / worktree）只在
# mktemp 创建的临时仓库中执行，绝不触碰真实仓库。
#
# 用法： bash tests/test-branchctl.sh
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BRANCHCTL="$SKILL_DIR/runtime/branchctl"
INSTALLER="$SKILL_DIR/install.sh"
UPDATER="$SKILL_DIR/update.sh"

PASS=0
FAIL=0
FAILED_CASES=""

TROOT=""
cleanup() {
  if [ -n "$TROOT" ] && [ -d "$TROOT" ]; then
    rm -rf "$TROOT"
  fi
}
trap cleanup EXIT

report() {
  local id="$1" result="$2" msg="${3:-}"
  if [ "$result" = "PASS" ]; then
    PASS=$((PASS + 1))
    printf 'PASS %s %s\n' "$id" "$msg"
  else
    FAIL=$((FAIL + 1))
    FAILED_CASES="$FAILED_CASES $id"
    printf 'FAIL %s %s\n' "$id" "$msg"
  fi
}

run_tool() {
  # run_tool <目录> <命令...>：执行安装后的 branchctl，输出捕获到 stdout。
  local dir="$1"
  shift
  (cd "$dir" && bash "$BRANCHCTL" "$@")
}

git_init_branch() {
  # git_init_branch <目录> <分支>：可移植地初始化指定默认分支的仓库。
  local dir="$1" branch="$2"
  if git init -q -b "$branch" "$dir" 2>/dev/null; then
    return 0
  fi
  git init -q "$dir"
  git -C "$dir" symbolic-ref HEAD "refs/heads/$branch" >/dev/null
}

git_cfg() {
  git -C "$1" config user.email "branchctl-test@example.com"
  git -C "$1" config user.name "branchctl-test"
  git -C "$1" config commit.gpgsign false
}

# fixture_repo <用例名>：建 bare origin + work 克隆（含 develop 初始提交 + 已安装 Skill）。
# 设置全局变量 FIX_ORIGIN / FIX_WORK。
fixture_repo() {
  local name="$1"
  local base="$TROOT/$name"
  FIX_ORIGIN="$base-origin.git"
  FIX_WORK="$base-work"
  git init -q --bare "$FIX_ORIGIN"
  git_init_branch "$base-seed" "develop"
  git_cfg "$base-seed"
  (cd "$base-seed" && git commit -q --allow-empty -m init)
  (cd "$base-seed" && git remote add origin "$FIX_ORIGIN")
  (cd "$base-seed" && git push -q origin develop)
  git clone -q -b develop "$FIX_ORIGIN" "$FIX_WORK" 2>/dev/null
  git_cfg "$FIX_WORK"
  bash "$INSTALLER" "$FIX_WORK" >/dev/null 2>&1
  # 真实项目会提交安装产物；提交后工作树干净，符合各命令的干净假设。
  (cd "$FIX_WORK" && git add -A && git commit -q -m "chore: install branchctl")
  # 安装提交同样推送到 origin，避免本地 develop 与远端人为分叉。
  (cd "$FIX_WORK" && git push -q origin develop)
}

# advance_develop <work克隆> <文件名> <内容>：用第二个克隆推进远端 develop。
advance_develop() {
  local work="$1" file="$2" content="$3"
  local adv="$work-adv"
  rm -rf "$adv"
  git clone -q -b develop "$FIX_ORIGIN" "$adv" 2>/dev/null
  git_cfg "$adv"
  printf '%s\n' "$content" >"$adv/$file"
  (cd "$adv" && git add "$file" && git commit -q -m "develop: update $file" && git push -q origin develop)
}

new_feature() {
  # new_feature <work克隆> <分支名>：切出 feature 分支并做一次提交。
  local work="$1" branch="$2"
  (cd "$work" && git checkout -q -b "$branch")
  printf 'feature work\n' >"$work/work.txt"
  (cd "$work" && git add work.txt && git commit -q -m "feature: work")
}

assert_rc_zero() {
  local id="$1" rc="$2" where="$3"
  if [ "$rc" -eq 0 ]; then
    return 0
  fi
  report "$id" "FAIL" "$where: 期望退出码 0，实际 $rc"
  return 1
}

assert_rc_nonzero() {
  local id="$1" rc="$2" where="$3"
  if [ "$rc" -ne 0 ]; then
    return 0
  fi
  report "$id" "FAIL" "$where: 期望非 0 退出码，实际为 0"
  return 1
}

assert_contains() {
  local id="$1" text="$2" needle="$3" where="$4"
  case "$text" in
    *"$needle"*)
      return 0
      ;;
    *)
      report "$id" "FAIL" "$where: 输出缺少期望 [$needle]"
      return 1
      ;;
  esac
}

# ---------------------------------------------------------------- T01 安装
t01() {
  local id="T01" d="$TROOT/t01" out rc
  git_init_branch "$d" "develop"
  git_cfg "$d"
  (cd "$d" && git commit -q --allow-empty -m init)
  out="$(bash "$INSTALLER" "$d" 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "install" || return 0
  [ -x "$d/scripts/branchctl" ] || { report "$id" "FAIL" "缺少 scripts/branchctl"; return 0; }
  [ -f "$d/.agent/branch-policy.yaml" ] || { report "$id" "FAIL" "缺少策略文件"; return 0; }
  [ -x "$d/.githooks/pre-push" ] || { report "$id" "FAIL" "缺少 pre-push hook"; return 0; }
  grep -qF "multi-agent-branch-integration:start" "$d/AGENTS.md" || { report "$id" "FAIL" "AGENTS.md 缺少 marker"; return 0; }
  [ "$(git -C "$d" config core.hooksPath)" = ".githooks" ] || { report "$id" "FAIL" "core.hooksPath 未设置"; return 0; }
  [ -f "$d/.github/workflows/branch-policy-check.yml" ] || { report "$id" "FAIL" "缺少 workflow"; return 0; }
  report "$id" "PASS" "安装产物齐全"
}

# ---------------------------------------------------------------- T02 install 幂等
t02() {
  local id="T02" d="$TROOT/t02" n
  git_init_branch "$d" "develop"
  git_cfg "$d"
  (cd "$d" && git commit -q --allow-empty -m init)
  bash "$INSTALLER" "$d" >/dev/null 2>&1
  printf '\n# sentinel: keep-me\n' >>"$d/.agent/branch-policy.yaml"
  bash "$INSTALLER" "$d" >/dev/null 2>&1
  n="$(grep -cF "multi-agent-branch-integration:start" "$d/AGENTS.md")"
  if [ "$n" != "1" ]; then
    report "$id" "FAIL" "marker 出现 $n 次（期望 1）"
    return 0
  fi
  grep -qF "sentinel: keep-me" "$d/.agent/branch-policy.yaml" || {
    report "$id" "FAIL" "二次安装覆盖了项目策略"
    return 0
  }
  report "$id" "PASS" "幂等成立"
}

# ---------------------------------------------------------------- T03 private init
t03() {
  local id="T03" out rc
  fixture_repo "t03"
  (cd "$FIX_WORK" && git checkout -q -b feature/t03)
  out="$(run_tool "$FIX_WORK" init --private 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "init --private" || return 0
  [ "$(git -C "$FIX_WORK" config branch.feature/t03.agentShared)" = "false" ] || {
    report "$id" "FAIL" "agentShared 未落盘为 false"
    return 0
  }
  assert_contains "$id" "$out" "VISIBILITY=private" "init 输出" || return 0
  # 无参数 init 走策略默认值（模板为 private）。
  (cd "$FIX_WORK" && git checkout -q -b feature/t03b)
  out="$(run_tool "$FIX_WORK" init 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "init（默认）" || return 0
  assert_contains "$id" "$out" "VISIBILITY=private" "默认 init 输出" || return 0
  report "$id" "PASS" "private 初始化正确"
}

# ---------------------------------------------------------------- T04 shared init
t04() {
  local id="T04" out rc
  fixture_repo "t04"
  (cd "$FIX_WORK" && git checkout -q -b feature/t04)
  out="$(run_tool "$FIX_WORK" init --shared 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "init --shared" || return 0
  [ "$(git -C "$FIX_WORK" config branch.feature/t04.agentShared)" = "true" ] || {
    report "$id" "FAIL" "agentShared 未落盘为 true"
    return 0
  }
  assert_contains "$id" "$out" "VISIBILITY=shared" "init 输出" || return 0
  report "$id" "PASS" "shared 初始化正确"
}

# ---------------------------------------------------------------- T05 private sync 走 rebase
t05() {
  local id="T05" out rc before after parent origin_dev parents
  fixture_repo "t05"
  (cd "$FIX_WORK" && git checkout -q -b feature/priv)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'priv work\n' >"$FIX_WORK/priv.txt"
  (cd "$FIX_WORK" && git add priv.txt && git commit -q -m "feature: priv work")
  before="$(git -C "$FIX_WORK" rev-parse HEAD)"
  (cd "$FIX_WORK" && git push -q -u origin feature/priv)
  advance_develop "$FIX_WORK" "dev.txt" "develop work"
  out="$(run_tool "$FIX_WORK" sync 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "sync" || return 0
  assert_contains "$id" "$out" "SYNC_METHOD=rebase" "同步方法" || return 0
  after="$(git -C "$FIX_WORK" rev-parse HEAD)"
  origin_dev="$(git -C "$FIX_WORK" rev-parse refs/remotes/origin/develop)"
  parent="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print $2}')"
  parents="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print NF}')"
  if [ "$parents" != "2" ]; then
    report "$id" "FAIL" "rebase 后应为线性单父提交"
    return 0
  fi
  if [ "$parent" != "$origin_dev" ]; then
    report "$id" "FAIL" "rebase 未落到 origin/develop 之上"
    return 0
  fi
  if [ "$before" = "$after" ]; then
    report "$id" "FAIL" "提交未被重写（不像 rebase）"
    return 0
  fi
  report "$id" "PASS" "private 同步发生 rebase"
}

# ---------------------------------------------------------------- T06 shared sync 走 merge
t06() {
  local id="T06" out rc f1 parents
  fixture_repo "t06"
  (cd "$FIX_WORK" && git checkout -q -b feature/shr)
  run_tool "$FIX_WORK" init --shared >/dev/null 2>&1
  printf 'shr work\n' >"$FIX_WORK/shr.txt"
  (cd "$FIX_WORK" && git add shr.txt && git commit -q -m "feature: shr work")
  f1="$(git -C "$FIX_WORK" rev-parse HEAD)"
  advance_develop "$FIX_WORK" "dev.txt" "develop work"
  out="$(run_tool "$FIX_WORK" sync 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "sync" || return 0
  assert_contains "$id" "$out" "SYNC_METHOD=merge" "同步方法" || return 0
  parents="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print NF}')"
  if [ "$parents" != "3" ]; then
    report "$id" "FAIL" "shared 同步应产生 merge 提交（期望双父）"
    return 0
  fi
  (cd "$FIX_WORK" && git merge-base --is-ancestor "$f1" HEAD) || {
    report "$id" "FAIL" "原提交被重写（shared 禁止 rebase）"
    return 0
  }
  report "$id" "PASS" "shared 同步为 merge 且保留原提交"
}

# ---------------------------------------------------------------- T07 unknown 拒绝同步
t07() {
  local id="T07" out rc before after
  fixture_repo "t07"
  (cd "$FIX_WORK" && git checkout -q -b feature/unk)
  printf 'x\n' >"$FIX_WORK/x.txt"
  (cd "$FIX_WORK" && git add x.txt && git commit -q -m "feature: x")
  before="$(git -C "$FIX_WORK" rev-parse HEAD)"
  out="$(run_tool "$FIX_WORK" sync 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "sync（unknown）" || return 0
  assert_contains "$id" "$out" "UNKNOWN_VISIBILITY" "拒绝原因" || return 0
  after="$(git -C "$FIX_WORK" rev-parse HEAD)"
  if [ "$before" != "$after" ]; then
    report "$id" "FAIL" "拒绝后历史被改动"
    return 0
  fi
  report "$id" "PASS" "unknown 可见性拒绝同步且历史不动"
}

# ---------------------------------------------------------------- T08 share 单向转换
t08() {
  local id="T08" out rc
  fixture_repo "t08"
  (cd "$FIX_WORK" && git checkout -q -b feature/sh)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  out="$(run_tool "$FIX_WORK" share 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "share" || return 0
  [ "$(git -C "$FIX_WORK" config branch.feature/sh.agentShared)" = "true" ] || {
    report "$id" "FAIL" "share 未落盘为 true"
    return 0
  }
  assert_contains "$id" "$out" "VISIBILITY=shared" "share 输出" || return 0
  assert_contains "$id" "$out" "REBASE_ALLOWED=false" "share 输出" || return 0
  assert_contains "$id" "$out" "FORCE_PUSH_ALLOWED=false" "share 输出" || return 0
  assert_contains "$id" "$out" "SYNC_METHOD=merge" "share 输出" || return 0
  report "$id" "PASS" "share 单向转换正确"
}

# ---------------------------------------------------------------- T09 集成分支拒绝 preflight
t09() {
  local id="T09" out rc
  fixture_repo "t09"
  out="$(run_tool "$FIX_WORK" preflight 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "preflight（develop）" || return 0
  report "$id" "PASS" "集成分支直接开发被拒绝"
}

# ---------------------------------------------------------------- T10 review-ready SHA
t10() {
  local id="T10" out rc base head dev
  fixture_repo "t10"
  (cd "$FIX_WORK" && git checkout -q -b feature/rev)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'r\n' >"$FIX_WORK/r.txt"
  (cd "$FIX_WORK" && git add r.txt && git commit -q -m "feature: r")
  out="$(run_tool "$FIX_WORK" review-ready 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "review-ready" || return 0
  assert_contains "$id" "$out" "REVIEW_READY=true" "就绪标志" || return 0
  base="$(printf '%s' "$out" | grep '^BASE_SHA=' | cut -d= -f2)"
  head="$(printf '%s' "$out" | grep '^HEAD_SHA=' | cut -d= -f2)"
  dev="$(printf '%s' "$out" | grep '^DEVELOP_SHA=' | cut -d= -f2)"
  for sha in "$base" "$head" "$dev"; do
    case "$sha" in
      ''|*[!0-9a-f]*)
        report "$id" "FAIL" "SHA 非法（非十六进制）：$sha"
        return 0
        ;;
    esac
    if [ "${#sha}" -ne 40 ]; then
      report "$id" "FAIL" "SHA 长度非法：$sha"
      return 0
    fi
  done
  report "$id" "PASS" "SHA 输出齐全有效"
}

# ---------------------------------------------------------------- T11 脏工作树 gate 失败
t11() {
  local id="T11" out rc
  fixture_repo "t11"
  (cd "$FIX_WORK" && git checkout -q -b feature/gate)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'dirty\n' >"$FIX_WORK/dirty.txt"
  out="$(run_tool "$FIX_WORK" gate-ready 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "gate-ready（dirty）" || return 0
  assert_contains "$id" "$out" "DIRTY_WORKTREE" "失败原因" || return 0
  report "$id" "PASS" "脏工作树门禁失败"
}

# ---------------------------------------------------------------- T12 过期 merge-ready 失败
t12() {
  local id="T12" out rc
  fixture_repo "t12"
  (cd "$FIX_WORK" && git checkout -q -b feature/old)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'feature side\n' >"$FIX_WORK/shared.txt"
  (cd "$FIX_WORK" && git add shared.txt && git commit -q -m "feature: touch shared")
  advance_develop "$FIX_WORK" "shared.txt" "develop side"
  out="$(run_tool "$FIX_WORK" merge-ready 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "merge-ready（过期）" || return 0
  assert_contains "$id" "$out" "INTEGRATION_SYNC_REQUIRED" "失败原因" || return 0
  assert_contains "$id" "$out" "ACTION=./scripts/branchctl sync" "修复动作" || return 0
  report "$id" "PASS" "过期分支集成前被阻断"
}

# ---------------------------------------------------------------- T13 integrate 固定 --no-ff
t13() {
  local id="T13" out rc parents
  fixture_repo "t13"
  (cd "$FIX_WORK" && git checkout -q -b feature/F99-demo)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'i\n' >"$FIX_WORK/i.txt"
  (cd "$FIX_WORK" && git add i.txt && git commit -q -m "feature: i")
  out="$(run_tool "$FIX_WORK" integrate 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "integrate" || return 0
  parents="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print NF}')"
  if [ "$parents" != "3" ]; then
    report "$id" "FAIL" "可 fast-forward 时未保留 merge commit"
    return 0
  fi
  report "$id" "PASS" "集成保留 merge commit"
}

# ---------------------------------------------------------------- T14 hook 阻断（push-check）
t14() {
  local id="T14" out rc
  fixture_repo "t14"
  (cd "$FIX_WORK" && git checkout -q -b feature/blk)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'feature side\n' >"$FIX_WORK/shared.txt"
  (cd "$FIX_WORK" && git add shared.txt && git commit -q -m "feature: touch shared")
  advance_develop "$FIX_WORK" "shared.txt" "develop side"
  out="$(run_tool "$FIX_WORK" push-check </dev/null 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "push-check（需同步）" || return 0
  assert_contains "$id" "$out" "PUSH_ALLOWED=false" "阻断标志" || return 0
  # 端到端：真实 git push 同样被 pre-push hook 拦下。
  if (cd "$FIX_WORK" && git push -q origin feature/blk >/dev/null 2>&1); then
    report "$id" "FAIL" "pre-push hook 未阻断真实推送"
    return 0
  fi
  report "$id" "PASS" "需同步时推送被阻断（含真实 hook）"
}

# ---------------------------------------------------------------- T15 真实 worktree
t15() {
  local id="T15" out rc wt
  fixture_repo "t15"
  wt="$TROOT/t15-wt"
  (cd "$FIX_WORK" && git worktree add -q "$wt" -b feature/wt 2>/dev/null) || {
    report "$id" "FAIL" "创建 worktree 失败"
    return 0
  }
  out="$(run_tool "$wt" status 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "worktree status" || return 0
  assert_contains "$id" "$out" "WORKTREE=linked" "worktree 识别" || return 0
  run_tool "$wt" init --private >/dev/null 2>&1
  out="$(run_tool "$wt" preflight 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "worktree preflight" || return 0
  report "$id" "PASS" "链接 worktree 工作正常"
}

# ---------------------------------------------------------------- T16 detached HEAD / CI
t16() {
  local id="T16" out rc
  fixture_repo "t16"
  (cd "$FIX_WORK" && git checkout -q -b feature/ci)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'c\n' >"$FIX_WORK/c.txt"
  (cd "$FIX_WORK" && git add c.txt && git commit -q -m "feature: c")
  (cd "$FIX_WORK" && git checkout -q --detach HEAD)
  out="$(GITHUB_HEAD_REF="feature/ci" GITHUB_BASE_REF="develop" run_tool "$FIX_WORK" ci-check 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "ci-check（env）" || return 0
  assert_contains "$id" "$out" "CI_READY=true" "CI 就绪" || return 0
  out="$(run_tool "$FIX_WORK" ci-check --head-ref feature/ci --base-ref develop 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "ci-check（flags）" || return 0
  assert_contains "$id" "$out" "CI_READY=true" "CI 就绪" || return 0
  report "$id" "PASS" "detached HEAD 下 CI 检查正常"
}

# ---------------------------------------------------------------- T17 update 保留配置
t17() {
  local id="T17"
  fixture_repo "t17"
  printf '\n# local tweak\nsync:\n  warning_behind_commits: 99\n' >>"$FIX_WORK/.agent/branch-policy.yaml"
  bash "$UPDATER" "$FIX_WORK" >/dev/null 2>&1
  grep -q "warning_behind_commits: 99" "$FIX_WORK/.agent/branch-policy.yaml" || {
    report "$id" "FAIL" "update 覆盖了项目策略"
    return 0
  }
  if ! cmp -s "$SKILL_DIR/runtime/branchctl" "$FIX_WORK/scripts/branchctl"; then
    report "$id" "FAIL" "受管 runtime 未更新"
    return 0
  fi
  report "$id" "PASS" "策略保留且 runtime 更新"
}

# ---------------------------------------------------------------- T18 install 不覆盖未知 branchctl
t18() {
  local id="T18" d="$TROOT/t18" out rc
  git_init_branch "$d" "develop"
  git_cfg "$d"
  (cd "$d" && git commit -q --allow-empty -m init)
  mkdir -p "$d/scripts"
  printf '# local tool - do not touch\n' >"$d/scripts/branchctl"
  chmod +x "$d/scripts/branchctl"
  out="$(bash "$INSTALLER" "$d" 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "install（未知 branchctl）" || return 0
  grep -qF "local tool - do not touch" "$d/scripts/branchctl" || {
    report "$id" "FAIL" "项目自有 branchctl 被覆盖"
    return 0
  }
  report "$id" "PASS" "未知已有文件被保护"
}

# ---------------------------------------------------------------- T19 install 不覆盖未知 pre-push
t19() {
  local id="T19" d="$TROOT/t19" out rc
  git_init_branch "$d" "develop"
  git_cfg "$d"
  (cd "$d" && git commit -q --allow-empty -m init)
  mkdir -p "$d/.githooks"
  printf '# local hook - do not touch\n' >"$d/.githooks/pre-push"
  chmod +x "$d/.githooks/pre-push"
  out="$(bash "$INSTALLER" "$d" 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "install（未知 hook）" || return 0
  grep -qF "local hook - do not touch" "$d/.githooks/pre-push" || {
    report "$id" "FAIL" "项目自有 hook 被覆盖"
    return 0
  }
  report "$id" "PASS" "未知已有 hook 被保护"
}

# ---------------------------------------------------------------- T20 update 残缺 marker 碰都不碰
t20() {
  local id="T20" before after out rc
  fixture_repo "t20"
  # 删掉 end marker 并在其后放哨兵，模拟手工编辑残缺。
  grep -vF "multi-agent-branch-integration:end" "$FIX_WORK/AGENTS.md" >"$FIX_WORK/AGENTS.md.tmp"
  mv "$FIX_WORK/AGENTS.md.tmp" "$FIX_WORK/AGENTS.md"
  printf 'USER-SENTINEL-AFTER-UNMATCHED-START\n' >>"$FIX_WORK/AGENTS.md"
  before="$(sha_file_print "$FIX_WORK/AGENTS.md")"
  out="$(bash "$UPDATER" "$FIX_WORK" 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "update（残缺 marker）" || return 0
  after="$(sha_file_print "$FIX_WORK/AGENTS.md")"
  if [ "$before" != "$after" ]; then
    report "$id" "FAIL" "残缺 marker 下文件被改动"
    return 0
  fi
  grep -qF "USER-SENTINEL-AFTER-UNMATCHED-START" "$FIX_WORK/AGENTS.md" || {
    report "$id" "FAIL" "用户内容丢失"
    return 0
  }
  # 反向残缺：只有孤儿 end marker，同样必须 fail-closed 且不追加。
  printf 'user content\n<!-- multi-agent-branch-integration:end -->\nmore user content\n' >"$FIX_WORK/AGENTS.md"
  before="$(sha_file_print "$FIX_WORK/AGENTS.md")"
  out="$(bash "$UPDATER" "$FIX_WORK" 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "update（孤儿 end）" || return 0
  after="$(sha_file_print "$FIX_WORK/AGENTS.md")"
  if [ "$before" != "$after" ]; then
    report "$id" "FAIL" "孤儿 end 下文件被改动"
    return 0
  fi
  if grep -qF "multi-agent-branch-integration:start" "$FIX_WORK/AGENTS.md"; then
    report "$id" "FAIL" "孤儿 end 下被追加了 start"
    return 0
  fi
  report "$id" "PASS" "残缺 marker 下文件原样保留"
}

sha_file_print() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

# ---------------------------------------------------------------- T21 CI 合成 merge commit 不得假 PASS
t21() {
  local id="T21" out rc f1 m
  fixture_repo "t21"
  (cd "$FIX_WORK" && git checkout -q -b feature/syn)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'feature side\n' >"$FIX_WORK/feat.txt"
  (cd "$FIX_WORK" && git add feat.txt && git commit -q -m "feature: feat")
  f1="$(git -C "$FIX_WORK" rev-parse HEAD)"
  advance_develop "$FIX_WORK" "package.json" '{"name":"x"}'
  (cd "$FIX_WORK" && git fetch -q origin)
  # 模拟 PR 合成 merge commit 并进入 detached，同时删掉 head 引用。
  (cd "$FIX_WORK" && git checkout -q --detach refs/remotes/origin/develop)
  (cd "$FIX_WORK" && git merge -q --no-ff "$f1" -m "synthetic pr merge")
  m="$(git -C "$FIX_WORK" rev-parse HEAD)"
  (cd "$FIX_WORK" && git push -q origin :feature/syn 2>/dev/null || true)
  (cd "$FIX_WORK" && git branch -qD feature/syn 2>/dev/null || true)
  (cd "$FIX_WORK" && git fetch -q origin --prune)
  # 无明确 SHA：必须 fail-closed，不得拿合成提交冒充。
  out="$(run_tool "$FIX_WORK" ci-check --head-ref feature/syn --base-ref develop 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "ci-check（引用缺失）" || return 0
  assert_contains "$id" "$out" "UNRESOLVED_HEAD" "失败原因" || return 0
  case "$out" in
    *"CI_READY=true"*)
      report "$id" "FAIL" "出现假 PASS"
      return 0
      ;;
  esac
  # 给明确 SHA：必须真实判定（落后+关键路径 → 阻断）。
  out="$(run_tool "$FIX_WORK" ci-check --head-ref feature/syn --base-ref develop --head-sha "$f1" 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "ci-check（明确 SHA 仍落后）" || return 0
  assert_contains "$id" "$out" "INTEGRATION_SYNC_REQUIRED" "失败原因" || return 0
  report "$id" "PASS" "合成提交无假 PASS，明确 SHA 真实判定"
}

# ---------------------------------------------------------------- T22 跨 worktree integrate 明确拒绝
t22() {
  local id="T22" out rc wt
  fixture_repo "t22"
  wt="$TROOT/t22-wt"
  (cd "$FIX_WORK" && git worktree add -q "$wt" -b feature/wtint 2>/dev/null) || {
    report "$id" "FAIL" "创建 worktree 失败"
    return 0
  }
  run_tool "$wt" init --private >/dev/null 2>&1
  printf 'w\n' >"$wt/w.txt"
  (cd "$wt" && git add w.txt && git commit -q -m "feature: w")
  out="$(run_tool "$wt" integrate 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "integrate（develop 被主 worktree 占用）" || return 0
  assert_contains "$id" "$out" "INTEGRATION_BRANCH_CHECKED_OUT_ELSEWHERE" "失败原因" || return 0
  # ACTION 必须是可执行的：不得指示到 holder 里再调 integrate（死路）。
  assert_contains "$id" "$out" "PR" "修复动作" || return 0
  case "$out" in
    *"中执行 integrate"*)
      report "$id" "FAIL" "ACTION 仍指示死路"
      return 0
      ;;
  esac
  report "$id" "PASS" "跨 worktree 集成被明确拒绝"
}

# ---------------------------------------------------------------- T23 workflow 按策略分支生成
t23() {
  local id="T23" d="$TROOT/t23"
  git_init_branch "$d" "develop"
  git_cfg "$d"
  (cd "$d" && git commit -q --allow-empty -m init)
  bash "$INSTALLER" "$d" >/dev/null 2>&1
  sed 's/^integration_branch:.*/integration_branch: trunk/' "$d/.agent/branch-policy.yaml" >"$d/.agent/branch-policy.yaml.tmp"
  mv "$d/.agent/branch-policy.yaml.tmp" "$d/.agent/branch-policy.yaml"
  bash "$INSTALLER" "$d" >/dev/null 2>&1
  grep -q "trunk" "$d/.github/workflows/branch-policy-check.yml" || {
    report "$id" "FAIL" "workflow 未跟随策略分支"
    return 0
  }
  if grep -q "__INTEGRATION_BRANCH__" "$d/.github/workflows/branch-policy-check.yml"; then
    report "$id" "FAIL" "workflow 残留未替换占位符"
    return 0
  fi
  report "$id" "PASS" "workflow 分支跟随策略"
}

# ---------------------------------------------------------------- T24 share 拒绝 unknown 直通
t24() {
  local id="T24" out rc
  fixture_repo "t24"
  (cd "$FIX_WORK" && git checkout -q -b feature/unkshare)
  printf 'x\n' >"$FIX_WORK/x.txt"
  (cd "$FIX_WORK" && git add x.txt && git commit -q -m "feature: x")
  out="$(run_tool "$FIX_WORK" share 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "share（unknown）" || return 0
  assert_contains "$id" "$out" "UNKNOWN_VISIBILITY" "拒绝原因" || return 0
  if [ -n "$(git -C "$FIX_WORK" config --get branch.feature/unkshare.agentShared || true)" ]; then
    report "$id" "FAIL" "拒绝后仍落盘了配置"
    return 0
  fi
  report "$id" "PASS" "unknown 不得直通 shared"
}

# ---------------------------------------------------------------- T25 preflight 暴露必须同步
t25() {
  local id="T25" out rc
  fixture_repo "t25"
  (cd "$FIX_WORK" && git checkout -q -b feature/pre)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'feature side\n' >"$FIX_WORK/shared.txt"
  (cd "$FIX_WORK" && git add shared.txt && git commit -q -m "feature: touch shared")
  advance_develop "$FIX_WORK" "shared.txt" "develop side"
  out="$(run_tool "$FIX_WORK" preflight 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "preflight（需同步）" || return 0
  assert_contains "$id" "$out" "INTEGRATION_SYNC_REQUIRED" "失败原因" || return 0
  # 关闭 before_work 后回到只做准入。
  sed 's/before_work: true/before_work: false/' "$FIX_WORK/.agent/branch-policy.yaml" >"$FIX_WORK/.agent/branch-policy.yaml.tmp"
  mv "$FIX_WORK/.agent/branch-policy.yaml.tmp" "$FIX_WORK/.agent/branch-policy.yaml"
  out="$(run_tool "$FIX_WORK" preflight 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "preflight（before_work 关闭）" || return 0
  report "$id" "PASS" "preflight 同步暴露受开关控制"
}

# ---------------------------------------------------------------- T26 update 补装不造成误报
t26() {
  local id="T26" out rc sk
  fixture_repo "t26"
  # 删掉 workflow 后 update 应补装成功，且把渲染指纹记入 manifest。
  rm -f "$FIX_WORK/.github/workflows/branch-policy-check.yml"
  out="$(bash "$UPDATER" "$FIX_WORK" 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "update（补装）" || return 0
  [ -f "$FIX_WORK/.github/workflows/branch-policy-check.yml" ] || {
    report "$id" "FAIL" "workflow 未被补装"
    return 0
  }
  grep -q "branch-policy-check.yml" "$FIX_WORK/.agent/.branchctl-managed" || {
    report "$id" "FAIL" "补装后未记入指纹"
    return 0
  }
  # 模拟下一版 Skill 模板升级：复制 Skill 并改模板，再 update 不得误报本地修改。
  sk="$TROOT/t26-skill"
  cp -r "$SKILL_DIR" "$sk"
  printf '# template v2\n' >>"$sk/templates/github/branch-policy-check.yml"
  out="$(bash "$sk/update.sh" "$FIX_WORK" 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "update（模板升级）" || return 0
  grep -qF "template v2" "$FIX_WORK/.github/workflows/branch-policy-check.yml" || {
    report "$id" "FAIL" "模板升级未生效"
    return 0
  }
  report "$id" "PASS" "补装与模板升级无误报"
}

# fixture_overlap <用例名> <分支名>：构造可自动合并的路径重叠
#（feature 改首行，develop 改末行），供自动同步测试使用。
# 设置 FIX_ORIGIN / FIX_WORK。
fixture_overlap() {
  local name="$1"
  local branch="$2"
  local base="$TROOT/$name"
  FIX_ORIGIN="$base-origin.git"
  FIX_WORK="$base-work"
  git init -q --bare "$FIX_ORIGIN"
  git_init_branch "$base-seed" "develop"
  git_cfg "$base-seed"
  printf 'l1\nl2\nl3\n' >"$base-seed/shared.txt"
  (cd "$base-seed" && git add shared.txt && git commit -q -m init)
  (cd "$base-seed" && git remote add origin "$FIX_ORIGIN")
  (cd "$base-seed" && git push -q origin develop)
  git clone -q -b develop "$FIX_ORIGIN" "$FIX_WORK" 2>/dev/null
  git_cfg "$FIX_WORK"
  bash "$INSTALLER" "$FIX_WORK" >/dev/null 2>&1
  (cd "$FIX_WORK" && git add -A && git commit -q -m "chore: install branchctl")
  (cd "$FIX_WORK" && git push -q origin develop)
  (cd "$FIX_WORK" && git checkout -q -b "$branch")
  sed 's/^l1$/l1-feat/' "$FIX_WORK/shared.txt" >"$FIX_WORK/shared.txt.tmp"
  mv "$FIX_WORK/shared.txt.tmp" "$FIX_WORK/shared.txt"
  (cd "$FIX_WORK" && git commit -qam "feature: touch shared")
  advance_develop_l3 "$FIX_WORK"
}

advance_develop_l3() {
  local work="$1"
  local adv="$work-adv"
  rm -rf "$adv"
  git clone -q -b develop "$FIX_ORIGIN" "$adv" 2>/dev/null
  git_cfg "$adv"
  sed 's/^l3$/l3-dev/' "$adv/shared.txt" >"$adv/shared.txt.tmp"
  mv "$adv/shared.txt.tmp" "$adv/shared.txt"
  (cd "$adv" && git commit -qam "develop: touch shared" && git push -q origin develop)
}

# ---------------------------------------------------------------- T27 agent-start 自动初始化并同步
t27() {
  local id="T27" out rc parent origin_dev
  fixture_overlap "t27" "feature/auto"
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "agent-start" || return 0
  assert_contains "$id" "$out" "AGENT_START=true" "启动标志" || return 0
  assert_contains "$id" "$out" "AUTO_INIT=true" "自动初始化标记" || return 0
  assert_contains "$id" "$out" "SOURCE=policy" "策略来源" || return 0
  assert_contains "$id" "$out" "PRIOR_EVIDENCE=STALE" "证据作废声明" || return 0
  [ "$(git -C "$FIX_WORK" config branch.feature/auto.agentShared)" = "false" ] || {
    report "$id" "FAIL" "未按策略落盘为 private"
    return 0
  }
  origin_dev="$(git -C "$FIX_WORK" rev-parse refs/remotes/origin/develop)"
  parent="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print $2}')"
  if [ "$parent" != "$origin_dev" ]; then
    report "$id" "FAIL" "自动同步未发生 rebase"
    return 0
  fi
  report "$id" "PASS" "自动初始化并 rebase"
}

# ---------------------------------------------------------------- T28 agent-start 尊重显式 shared
t28() {
  local id="T28" out rc parents
  fixture_overlap "t28" "feature/autoshr"
  run_tool "$FIX_WORK" init --shared >/dev/null 2>&1
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "agent-start（shared）" || return 0
  assert_contains "$id" "$out" "AUTO_INIT=false" "不重复初始化" || return 0
  assert_contains "$id" "$out" "PRIOR_EVIDENCE=PRESERVED" "证据保留声明" || return 0
  parents="$(git -C "$FIX_WORK" rev-list --parents -n 1 HEAD | awk '{print NF}')"
  if [ "$parents" != "3" ]; then
    report "$id" "FAIL" "shared 未走 merge"
    return 0
  fi
  report "$id" "PASS" "显式 shared 走 merge 且不重写"
}

# ---------------------------------------------------------------- T29 无默认值时 agent-start 照样阻断
t29() {
  local id="T29" out rc
  fixture_overlap "t29" "feature/nodefault"
  sed 's/^  default_visibility:.*/  default_visibility:/' "$FIX_WORK/.agent/branch-policy.yaml" >"$FIX_WORK/.agent/branch-policy.yaml.tmp"
  mv "$FIX_WORK/.agent/branch-policy.yaml.tmp" "$FIX_WORK/.agent/branch-policy.yaml"
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-start（无默认值）" || return 0
  assert_contains "$id" "$out" "UNKNOWN_VISIBILITY" "拒绝原因" || return 0
  if [ -n "$(git -C "$FIX_WORK" config --get branch.feature/nodefault.agentShared || true)" ]; then
    report "$id" "FAIL" "拒绝后仍写入了配置"
    return 0
  fi
  report "$id" "PASS" "无默认值时不猜测"
}

# ---------------------------------------------------------------- T30 agent-finish 无测试命令
t30() {
  local id="T30" out rc
  fixture_repo "t30"
  (cd "$FIX_WORK" && git checkout -q -b feature/fin)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'f\n' >"$FIX_WORK/f.txt"
  (cd "$FIX_WORK" && git add f.txt && git commit -q -m "feature: f")
  out="$(run_tool "$FIX_WORK" agent-finish 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "agent-finish" || return 0
  assert_contains "$id" "$out" "AGENT_FINISH=true" "收尾标志" || return 0
  assert_contains "$id" "$out" "LOCAL_TESTS=skipped" "测试跳过声明" || return 0
  assert_contains "$id" "$out" "REVIEW_READY=true" "就绪标志" || return 0
  for sha in $(printf '%s' "$out" | grep -E '^(BASE_SHA|HEAD_SHA|DEVELOP_SHA)=' | cut -d= -f2); do
    case "$sha" in
      ''|*[!0-9a-f]*)
        report "$id" "FAIL" "SHA 非法（非十六进制）：$sha"
        return 0
        ;;
    esac
    if [ "${#sha}" -ne 40 ]; then
      report "$id" "FAIL" "SHA 长度非法：$sha"
      return 0
    fi
  done
  if [ "$(printf '%s' "$out" | grep -cE '^(BASE_SHA|HEAD_SHA|DEVELOP_SHA)=')" != "3" ]; then
    report "$id" "FAIL" "三组 SHA 缺失"
    return 0
  fi
  case "$out" in
    *"LOCAL_TESTS=passed"*)
      report "$id" "FAIL" "伪造了测试通过"
      return 0
      ;;
  esac
  report "$id" "PASS" "无命令时如实跳过不断言通过"
}

# ---------------------------------------------------------------- T31 agent-finish 执行配置测试
t31() {
  local id="T31" out rc pol
  fixture_repo "t31"
  (cd "$FIX_WORK" && git checkout -q -b feature/fint)
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  printf 'f\n' >"$FIX_WORK/f.txt"
  (cd "$FIX_WORK" && git add f.txt && git commit -q -m "feature: f")
  pol="$FIX_WORK/.agent/branch-policy.yaml"
  awk '/before_merge: true/{print; print "  test_command: \"true\""; next}1' "$pol" >"$pol.tmp"
  mv "$pol.tmp" "$pol"
  out="$(run_tool "$FIX_WORK" agent-finish 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "agent-finish（测试通过）" || return 0
  assert_contains "$id" "$out" "LOCAL_TESTS=passed" "测试通过" || return 0
  sed 's/test_command: "true"/test_command: "false"/' "$pol" >"$pol.tmp"
  mv "$pol.tmp" "$pol"
  out="$(run_tool "$FIX_WORK" agent-finish 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-finish（测试失败）" || return 0
  assert_contains "$id" "$out" "LOCAL_TESTS_FAILED" "失败原因" || return 0
  report "$id" "PASS" "配置测试如实执行并阻断"
}

# ---------------------------------------------------------------- T32 agent-finish 未知可见性拒绝
t32() {
  local id="T32" out rc
  fixture_repo "t32"
  (cd "$FIX_WORK" && git checkout -q -b feature/unkfin)
  printf 'x\n' >"$FIX_WORK/x.txt"
  (cd "$FIX_WORK" && git add x.txt && git commit -q -m "feature: x")
  out="$(run_tool "$FIX_WORK" agent-finish 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-finish（unknown）" || return 0
  assert_contains "$id" "$out" "UNKNOWN_VISIBILITY" "拒绝原因" || return 0
  (cd "$FIX_WORK" && git checkout -q develop)
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-start（develop）" || return 0
  report "$id" "PASS" "收尾不自动初始化"
}

# ---------------------------------------------------------------- T33 冻结分支拒绝自动同步
t33() {
  local id="T33" out rc before after
  fixture_overlap "t33" "feature/frz"
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  out="$(run_tool "$FIX_WORK" freeze 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "freeze" || return 0
  assert_contains "$id" "$out" "SYNC_FROZEN=true" "冻结标志" || return 0
  before="$(git -C "$FIX_WORK" rev-parse HEAD)"
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-start（已冻结）" || return 0
  assert_contains "$id" "$out" "SYNC_FROZEN" "拒绝原因" || return 0
  after="$(git -C "$FIX_WORK" rev-parse HEAD)"
  if [ "$before" != "$after" ]; then
    report "$id" "FAIL" "冻结后历史仍被改写"
    return 0
  fi
  out="$(run_tool "$FIX_WORK" unfreeze 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "unfreeze" || return 0
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_zero "$id" "$rc" "agent-start（解冻后）" || return 0
  assert_contains "$id" "$out" "AGENT_START=true" "启动标志" || return 0
  report "$id" "PASS" "冻结阻断、解冻恢复"
}

# ---------------------------------------------------------------- T34 自动入口不继承 develop 例外
t34() {
  local id="T34" out rc pol
  fixture_repo "t34"
  pol="$FIX_WORK/.agent/branch-policy.yaml"
  awk '/allow_direct_on_integration/{sub(/false/, "true")}1' "$pol" >"$pol.tmp"
  mv "$pol.tmp" "$pol"
  out="$(run_tool "$FIX_WORK" agent-start 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-start（develop）" || return 0
  if [ -n "$(git -C "$FIX_WORK" config --get branch.develop.agentShared || true)" ]; then
    report "$id" "FAIL" "develop 被写入了可见性"
    return 0
  fi
  # preflight 的例外本身不受影响：分支门禁照样放行（走到可见性检查才停，
  # 而不是倒在 INTEGRATION_BRANCH），且全程不写配置。
  out="$(run_tool "$FIX_WORK" preflight 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "preflight（develop 无可见性）" || return 0
  assert_contains "$id" "$out" "UNKNOWN_VISIBILITY" "停在可见性而非分支门禁" || return 0
  case "$out" in
    *"INTEGRATION_BRANCH"*)
      report "$id" "FAIL" "例外未生效"
      return 0
      ;;
  esac
  report "$id" "PASS" "自动入口只认 feature"
}

# ---------------------------------------------------------------- T35 失败路径不吞证据声明
t35() {
  local id="T35" out rc pol
  fixture_overlap "t35" "feature/failafter"
  run_tool "$FIX_WORK" init --private >/dev/null 2>&1
  pol="$FIX_WORK/.agent/branch-policy.yaml"
  awk '/before_merge: true/{print; print "  test_command: \"false\""; next}1' "$pol" >"$pol.tmp"
  mv "$pol.tmp" "$pol"
  (cd "$FIX_WORK" && git add .agent/branch-policy.yaml && git commit -qm "test: failing test command")
  out="$(run_tool "$FIX_WORK" agent-finish 2>&1)"
  rc=$?
  assert_rc_nonzero "$id" "$rc" "agent-finish（测试失败）" || return 0
  assert_contains "$id" "$out" "LOCAL_TESTS_FAILED" "失败原因" || return 0
  assert_contains "$id" "$out" "PRIOR_EVIDENCE=STALE" "证据声明仍在" || return 0
  assert_contains "$id" "$out" "HEAD_BEFORE=" "旧 HEAD 仍在" || return 0
  assert_contains "$id" "$out" "HEAD_AFTER=" "新 HEAD 仍在" || return 0
  report "$id" "PASS" "失败路径证据不丢"
}

main() {
  TROOT="$(mktemp -d 2>/dev/null || mktemp -d -t branchctl-test)"
  command -v git >/dev/null 2>&1 || {
    printf 'FAIL: 找不到 git\n'
    exit 1
  }
  t01
  t02
  t03
  t04
  t05
  t06
  t07
  t08
  t09
  t10
  t11
  t12
  t13
  t14
  t15
  t16
  t17
  t18
  t19
  t20
  t21
  t22
  t23
  t24
  t25
  t26
  t27
  t28
  t29
  t30
  t31
  t32
  t33
  t34
  t35
  printf -- '----------------------------------------\n'
  printf 'TOTAL: %s passed, %s failed\n' "$PASS" "$FAIL"
  if [ -n "$FAILED_CASES" ]; then
    printf 'FAILED:%s\n' "$FAILED_CASES"
  fi
  [ "$FAIL" -eq 0 ]
}

main "$@"
