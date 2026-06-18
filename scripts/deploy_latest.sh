#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/root/.openclaw/workspace/morning_report}"
SERVICE_NAME="${SERVICE_NAME:-morning-report.service}"
BRANCH="${BRANCH:-master}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_DIR/.venv/bin/python}"
PIP_BIN="${PIP_BIN:-$REPO_DIR/.venv/bin/pip}"
INSTALL_DEPS="${INSTALL_DEPS:-auto}"
LOG_LINES="${LOG_LINES:-80}"

log() {
  printf '[%(%F %T)T] %s\n' -1 "$*"
}

run() {
  log "+ $*"
  "$@"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing command: $1" >&2
    exit 1
  fi
}

require_cmd git
require_cmd systemctl
require_cmd journalctl

if [[ ! -d "$REPO_DIR/.git" ]]; then
  echo "ERROR: not a git repository: $REPO_DIR" >&2
  exit 1
fi

cd "$REPO_DIR"

log "Repository: $REPO_DIR"
log "Service: $SERVICE_NAME"
log "Branch: $BRANCH"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: local working tree has uncommitted changes. Refusing to deploy." >&2
  git status --short >&2
  exit 1
fi

BEFORE_REV="$(git rev-parse --short HEAD)"
run git fetch origin "$BRANCH"

REMOTE_REV="$(git rev-parse --short "origin/$BRANCH")"
if [[ "$BEFORE_REV" == "$REMOTE_REV" ]]; then
  log "Already up to date at $BEFORE_REV. Restarting service anyway to ensure active code matches disk."
else
  log "Updating $BEFORE_REV -> $REMOTE_REV"
  run git pull --ff-only origin "$BRANCH"
fi

AFTER_REV="$(git rev-parse --short HEAD)"
log "Current commit: $(git log -1 --format='%h %s')"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python not found or not executable: $PYTHON_BIN" >&2
  exit 1
fi

if [[ "$INSTALL_DEPS" == "1" || "$INSTALL_DEPS" == "true" || "$INSTALL_DEPS" == "yes" ]]; then
  if [[ ! -x "$PIP_BIN" ]]; then
    echo "ERROR: pip not found or not executable: $PIP_BIN" >&2
    exit 1
  fi
  run "$PIP_BIN" install -r requirements.txt
elif [[ "$INSTALL_DEPS" == "auto" && -x "$PIP_BIN" ]]; then
  if ! git diff --quiet "$BEFORE_REV" "$AFTER_REV" -- requirements.txt 2>/dev/null; then
    run "$PIP_BIN" install -r requirements.txt
  else
    log "requirements.txt unchanged; skipping dependency install."
  fi
else
  log "Skipping dependency install."
fi

run "$PYTHON_BIN" -m py_compile src/*.py
run systemctl restart "$SERVICE_NAME"
sleep 2
run systemctl is-active --quiet "$SERVICE_NAME"

log "Service status: $(systemctl is-active "$SERVICE_NAME")"
log "Recent logs:"
journalctl -u "$SERVICE_NAME" --since '3 minutes ago' --no-pager -n "$LOG_LINES"

log "Deploy complete."
