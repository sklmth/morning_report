#!/usr/bin/env bash
# 企业知识库 —— 增量部署 / 更新脚本
# 只对本次真正变动的部分执行操作，尽量快。
#
# 用法：
#   bash deploy.sh              # 增量：按 git 变动决定装依赖/重启/什么都不做
#   FULL=1   bash deploy.sh     # 全量：无条件装依赖 + 重启（忽略 git 变动）
#   REBUILD=1 bash deploy.sh    # 文档(documents/)有增删时，额外重建向量库
#   FORCE=1  bash deploy.sh     # 强制重启后端（不管有无变动）
set -Eeuo pipefail

# ── 可覆盖变量 ───────────────────────────────────
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
KB_DIR="$REPO_DIR/company_kb"
SERVICE="${SERVICE:-company-kb.service}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
PIP_BIN="${PIP_BIN:-$REPO_DIR/.venv/bin/pip}"
BRANCH="${BRANCH:-master}"
REBUILD="${REBUILD:-0}"
FORCE="${FORCE:-0}"
FULL="${FULL:-0}"         # 1 = 全量：无条件装依赖 + 重启
# 供上层统一脚本调用：SKIP_PULL=1 时不拉代码，用 DIFF_BASE 作为对比起点
SKIP_PULL="${SKIP_PULL:-0}"
DIFF_BASE="${DIFF_BASE:-}"

log(){ printf '[%(%F %T)T] [kb] %s\n' -1 "$*"; }
py(){ [[ -x "$PYTHON_BIN" ]] && echo "$PYTHON_BIN" || echo python3; }
pip_bin(){ [[ -x "$PIP_BIN" ]] && echo "$PIP_BIN" || echo pip3; }

cd "$REPO_DIR"

# 1. 首次部署：准备 .env 和 logs
[[ -f "$KB_DIR/.env" ]] || { cp "$KB_DIR/.env.example" "$KB_DIR/.env"; log "已生成 .env"; }
mkdir -p "$KB_DIR/logs"

# 2. 拉代码，记录前后 commit（被统一脚本调用时跳过，复用其已拉取的结果）
if [[ "$SKIP_PULL" == "1" ]]; then
  BEFORE="${DIFF_BASE:-$(git rev-parse HEAD)}"
  AFTER="$(git rev-parse HEAD)"
else
  BEFORE="$(git rev-parse HEAD)"
  git fetch -q origin "$BRANCH"
  git pull -q --ff-only origin "$BRANCH" || true
  AFTER="$(git rev-parse HEAD)"
  log "提交: $(git log -1 --format='%h %s')"
fi

# 3. 算出本次 company_kb 下变动的文件
if [[ "$BEFORE" == "$AFTER" ]]; then
  CHANGED=""
  log "代码无更新。"
else
  CHANGED="$(git diff --name-only "$BEFORE" "$AFTER" -- company_kb/ || true)"
  log "本次变动文件:"; echo "$CHANGED" | sed 's/^/    /'
fi

# 4. 判断需要哪些动作
need_deps=0; need_restart=0; need_build=0
if [[ "$FULL" == "1" ]]; then
  # 全量：无条件装依赖 + 重启（建库仍看 REBUILD/向量库是否存在，避免误清已有库）
  need_deps=1; need_restart=1; log "全量部署 → 装依赖 + 重启。"
else
  echo "$CHANGED" | grep -q 'company_kb/requirements.txt' && { need_deps=1; need_restart=1; }
  echo "$CHANGED" | grep -qE 'company_kb/(api|query|config|ingest)\.py' && need_restart=1
fi
[[ "$REBUILD" == "1" ]] && { need_build=1; need_restart=1; }
[[ "$FORCE"   == "1" ]] && need_restart=1
# 向量库不存在时，强制建一次
[[ ! -d "$KB_DIR/chroma_db" ]] && { need_build=1; need_restart=1; log "未发现向量库，将建库。"; }

# 5. 按需执行
if [[ "$need_deps" == "1" ]]; then
  log "requirements 变动 → 安装依赖…"
  "$(pip_bin)" install -q -r "$KB_DIR/requirements.txt"
else
  log "依赖无变动 → 跳过安装。"
fi

if [[ "$need_build" == "1" ]]; then
  log "重建向量库（documents/）…"
  (cd "$KB_DIR" && "$(py)" ingest.py)
fi

if [[ "$need_restart" == "1" ]]; then
  "$(py)" -m py_compile "$KB_DIR"/{config,ingest,query,api}.py
  if systemctl list-unit-files | grep -q "^$SERVICE"; then
    systemctl restart "$SERVICE"; sleep 3
    systemctl is-active --quiet "$SERVICE" \
      && log "后端已重启 ($SERVICE active)" \
      || { log "启动失败，日志:"; journalctl -u "$SERVICE" -n 30 --no-pager; exit 1; }
  else
    log "未配置 $SERVICE，请先按 company-kb.service.example 设置。"
  fi
else
  # 只有前端或无变动：无需重启，Nginx 已托管最新静态文件
  log "无需重启后端（仅前端更新或无变动，Nginx 直接生效）。"
fi

log "部署完成。"
[[ "$need_restart" == "1" ]] && { curl -s http://127.0.0.1:8994/api/health || true; echo; }
