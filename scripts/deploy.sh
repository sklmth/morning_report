#!/usr/bin/env bash
# 全项目统一增量部署脚本
# 拉一次代码，按各模块的 git 变动分别决定：装依赖 / 重启 / 建库 / 什么都不做。
#
# 服务与端口：
#   8990  日报服务        (morning-report.service)              代码: src/
#   8992  经营分析后端    (morning-report-analytics.service)    代码: analytics/ run_analytics.py
#   8994  知识库后端      (company-kb.service)                  代码: company_kb/
#   8991/3030 静态前端    (nginx 托管，改前端无需重启)
#
# 用法：
#   bash scripts/deploy.sh              # 增量部署全部模块
#   bash scripts/deploy.sh kb           # 只部署知识库（可选: main / analytics / kb）
#   FORCE=1 bash scripts/deploy.sh      # 强制重启所有已变动判断外的服务
#   KB_REBUILD=1 bash scripts/deploy.sh # 知识库额外重建向量库
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
BRANCH="${BRANCH:-master}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
PIP_BIN="${PIP_BIN:-$REPO_DIR/.venv/bin/pip}"
FORCE="${FORCE:-0}"
KB_REBUILD="${KB_REBUILD:-0}"
ONLY="${1:-all}"          # all / main / analytics / kb

SVC_MAIN="${SVC_MAIN:-morning-report.service}"
SVC_ANALYTICS="${SVC_ANALYTICS:-morning-report-analytics.service}"
SVC_KB="${SVC_KB:-company-kb.service}"

log(){ printf '[%(%F %T)T] %s\n' -1 "$*"; }
py(){ [[ -x "$PYTHON_BIN" ]] && echo "$PYTHON_BIN" || echo python3; }
pip_bin(){ [[ -x "$PIP_BIN" ]] && echo "$PIP_BIN" || echo pip3; }

# 判断某服务是否已在 systemd 注册
has_svc(){ systemctl list-unit-files 2>/dev/null | grep -q "^$1"; }

# 重启并校验服务
restart_svc(){
  local svc="$1"
  if ! has_svc "$svc"; then log "  未注册 $svc，跳过重启（首次需手动配 systemd）。"; return 0; fi
  systemctl restart "$svc"; sleep 3
  if systemctl is-active --quiet "$svc"; then
    log "  ✓ $svc 已重启 (active)"
  else
    log "  ✗ $svc 启动失败，最近日志："
    journalctl -u "$svc" -n 25 --no-pager
    return 1
  fi
}
cd "$REPO_DIR"

# ── 1. 拉一次代码，记录前后 commit ──────────────
BEFORE="$(git rev-parse HEAD)"
log "拉取 origin/$BRANCH …"
git fetch -q origin "$BRANCH"
git pull -q --ff-only origin "$BRANCH" || true
AFTER="$(git rev-parse HEAD)"

if [[ "$BEFORE" == "$AFTER" ]]; then
  CHANGED=""
  log "代码无更新（$AFTER）。"
else
  CHANGED="$(git diff --name-only "$BEFORE" "$AFTER" || true)"
  log "更新到 $(git log -1 --format='%h %s')"
  log "变动文件："; echo "$CHANGED" | sed 's/^/    /'
fi

changed(){ echo "$CHANGED" | grep -qE "$1"; }
want(){ [[ "$ONLY" == "all" || "$ONLY" == "$1" ]]; }
rc=0

# ── 2. 日报服务 (8990) ──────────────────────────
if want main; then
  need=0
  changed '^requirements\.txt' && { log "[main] 依赖变动 → 安装…"; "$(pip_bin)" install -q -r requirements.txt; need=1; }
  changed '^src/' && need=1
  [[ "$FORCE" == "1" ]] && need=1
  if [[ "$need" == "1" ]]; then
    log "[main] 重启 $SVC_MAIN"
    "$(py)" -m py_compile src/*.py
    restart_svc "$SVC_MAIN" || rc=1
  else
    log "[main] 无变动，跳过。"
  fi
fi

# ── 3. 经营分析 (8992 后端 / 8991 前端) ──────────
if want analytics; then
  need=0
  changed '^analytics_requirements\.txt' && { log "[analytics] 依赖变动 → 安装…"; "$(pip_bin)" install -q -r analytics_requirements.txt; need=1; }
  changed '^(analytics/|run_analytics\.py)' && need=1
  [[ "$FORCE" == "1" ]] && need=1
  # 前端是静态，nginx 直接生效
  changed '^analytics-frontend/' && log "[analytics] 前端更新，nginx 直接生效（无需重启）。"
  if [[ "$need" == "1" ]]; then
    log "[analytics] 重启 $SVC_ANALYTICS"
    restart_svc "$SVC_ANALYTICS" || rc=1
  else
    log "[analytics] 后端无变动，跳过。"
  fi
fi

# ── 4. 知识库 (8994 后端 / 3030 前端) ────────────
if want kb; then
  log "[kb] 交给 company_kb/deploy.sh（复用本次已拉取的变动）"
  SKIP_PULL=1 DIFF_BASE="$BEFORE" REBUILD="$KB_REBUILD" FORCE="$FORCE" \
    bash company_kb/deploy.sh || rc=1
fi

log "全部完成（退出码 $rc）。"
exit $rc
