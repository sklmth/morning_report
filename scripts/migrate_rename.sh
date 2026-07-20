#!/usr/bin/env bash
# ── 一次性迁移脚本：命名规范化重构后，更新服务器 systemd 服务路径 ──
#
# 背景：本次重构改了入口脚本路径
#   src/web_server.py → daily_report/web_server.py   （日报服务 8990）
#   run_analytics.py  → analytics/main.py            （经营分析 8992）
# 已安装的 systemd 服务 ExecStart 仍指向旧路径，需就地更新一次。
#
# 用法（服务器上，git pull 之后执行一次）：
#   sudo bash scripts/migrate_rename.sh
#
# 幂等：可重复执行；已是新路径则跳过。
set -Eeuo pipefail

SVC_MAIN="${SVC_MAIN:-morning-report.service}"
SVC_ANALYTICS="${SVC_ANALYTICS:-morning-report-analytics.service}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

log(){ printf '[migrate] %s\n' "$*"; }

if [[ "$(id -u)" != "0" ]]; then
  echo "需要 root 权限操作 systemd，请用 sudo 运行。" >&2
  exit 1
fi

changed_any=0

fix_execstart(){
  local svc="$1" old="$2" new="$3"
  local f="$SYSTEMD_DIR/$svc"
  if [[ ! -f "$f" ]]; then
    log "未找到 $f，跳过（该服务可能未安装）。"
    return 0
  fi
  if grep -qF "$new" "$f"; then
    log "$svc 已是新路径，无需修改。"
    return 0
  fi
  if grep -qF "$old" "$f"; then
    cp -a "$f" "$f.bak.$(date +%Y%m%d%H%M%S)"      # 备份
    sed -i "s#$old#$new#g" "$f"
    log "$svc ExecStart 已更新：$old → $new（原文件已备份 .bak）"
    changed_any=1
  else
    log "$svc 未匹配到旧路径 '$old'，请手动检查 ExecStart。"
  fi
}

# 日报服务：src/web_server.py → daily_report/web_server.py
fix_execstart "$SVC_MAIN" "src/web_server.py" "daily_report/web_server.py"

# 经营分析：run_analytics.py → analytics/main.py
fix_execstart "$SVC_ANALYTICS" "run_analytics.py" "analytics/main.py"

if [[ "$changed_any" == "1" ]]; then
  log "systemctl daemon-reload…"
  systemctl daemon-reload
  for svc in "$SVC_MAIN" "$SVC_ANALYTICS"; do
    if systemctl list-unit-files | grep -q "^$svc"; then
      log "重启 $svc…"
      systemctl restart "$svc"; sleep 2
      systemctl is-active --quiet "$svc" \
        && log "  ✓ $svc active" \
        || { log "  ✗ $svc 启动失败，日志："; journalctl -u "$svc" -n 20 --no-pager; }
    fi
  done
else
  log "无改动，无需重启。"
fi

log "迁移完成。之后日常更新用：bash scripts/deploy.sh"
