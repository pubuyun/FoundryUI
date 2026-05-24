#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/pubuyun/FoundryUI.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/FoundryUI}"
SERVICE_NAME="${SERVICE_NAME:-foundryui}"
SERVICE_USER="${SERVICE_USER:-${SUDO_USER:-${USER:-root}}}"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_HOST="${FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

as_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    "$@"
  elif command -v sudo >/dev/null 2>&1; then
    sudo "$@"
  else
    fail "This step needs root privileges and sudo is not installed: $*"
  fi
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "Required command not found: $1"
}

install_basic_packages_if_possible() {
  local missing=()
  for cmd in git curl npm node systemctl; do
    command -v "$cmd" >/dev/null 2>&1 || missing+=("$cmd")
  done

  if [[ "${#missing[@]}" -eq 0 ]]; then
    return
  fi

  if command -v apt-get >/dev/null 2>&1; then
    log "Installing missing OS packages for: ${missing[*]}"
    as_root apt-get update
    curl -fsSL https://deb.nodesource.com/setup_lts.x | bash -
    as_root apt-get install -y nodejs
    as_root apt-get install -y git curl systemd
  else
    fail "Missing commands: ${missing[*]}. Install them first, then rerun this script."
  fi
}

check_node_version() {
  local major
  major="$(node -p 'Number(process.versions.node.split(".")[0])')"
  if (( major < 20 )); then
    fail "Node.js 20 or newer is required. Found: $(node --version)"
  fi
}

clone_or_update_repo() {
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    log "Updating existing checkout at $INSTALL_DIR"
    git -C "$INSTALL_DIR" fetch --all --prune
    git -C "$INSTALL_DIR" pull --ff-only
    return
  fi

  if [[ -e "$INSTALL_DIR" && -n "$(find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]]; then
    fail "$INSTALL_DIR exists and is not a git checkout. Move it aside or set INSTALL_DIR to another path."
  fi

  log "Cloning FoundryUI from $REPO_URL into $INSTALL_DIR"
  as_root mkdir -p "$(dirname "$INSTALL_DIR")"
  if [[ -w "$(dirname "$INSTALL_DIR")" ]]; then
    git clone "$REPO_URL" "$INSTALL_DIR"
  else
    as_root git clone "$REPO_URL" "$INSTALL_DIR"
    as_root chown -R "$SERVICE_USER:" "$INSTALL_DIR"
  fi
}

run_project_setup() {
  log "Running setup.sh. This installs Python dependencies, Foundry, frontend packages, and model checkpoints."
  chmod +x "$INSTALL_DIR/setup.sh"
  (cd "$INSTALL_DIR" && ./setup.sh)
}

build_frontend() {
  log "Building frontend production bundle."
  (cd "$INSTALL_DIR/frontend" && npm run build)
}

ensure_service_user_can_write() {
  if [[ "$SERVICE_USER" != "root" ]]; then
    log "Ensuring $SERVICE_USER owns $INSTALL_DIR for runtime artifacts."
    as_root chown -R "$SERVICE_USER:" "$INSTALL_DIR"
  fi
}

write_runtime_script() {
  local runtime_script="$INSTALL_DIR/run-foundryui-service.sh"
  log "Writing service runtime script to $runtime_script"
  cat >"$runtime_script" <<EOF
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$INSTALL_DIR"
BACKEND_HOST="$BACKEND_HOST"
BACKEND_PORT="$BACKEND_PORT"
FRONTEND_HOST="$FRONTEND_HOST"
FRONTEND_PORT="$FRONTEND_PORT"

export FOUNDRY_CHECKPOINT_DIRS="\$ROOT_DIR/models"
export FOUNDRYUI_RFD3_CKPT="\${FOUNDRYUI_RFD3_CKPT:-\$ROOT_DIR/models/rfd3_latest.ckpt}"
export FOUNDRYUI_RF3_CKPT="\${FOUNDRYUI_RF3_CKPT:-\$ROOT_DIR/models/rf3_foundry_2025_12_01_remapped.ckpt}"
export HOST="\$FRONTEND_HOST"
export PORT="\$FRONTEND_PORT"
export NITRO_HOST="\$FRONTEND_HOST"
export NITRO_PORT="\$FRONTEND_PORT"

cd "\$ROOT_DIR"

"\$ROOT_DIR/.venv/bin/uvicorn" backend.main:app --host "\$BACKEND_HOST" --port "\$BACKEND_PORT" &
backend_pid="\$!"

node "\$ROOT_DIR/frontend/.output/server/index.mjs" &
frontend_pid="\$!"

shutdown() {
  kill "\$backend_pid" "\$frontend_pid" 2>/dev/null || true
  wait "\$backend_pid" "\$frontend_pid" 2>/dev/null || true
}
trap shutdown INT TERM

wait -n "\$backend_pid" "\$frontend_pid"
status="\$?"
shutdown
exit "\$status"
EOF
  chmod +x "$runtime_script"
}

write_systemd_service() {
  local unit_path="/etc/systemd/system/${SERVICE_NAME}.service"
  log "Writing systemd unit to $unit_path"
  as_root tee "$unit_path" >/dev/null <<EOF
[Unit]
Description=FoundryUI backend and frontend
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/run-foundryui-service.sh
Restart=on-failure
RestartSec=5
KillMode=control-group
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

  as_root systemctl daemon-reload
  as_root systemctl enable "$SERVICE_NAME"
  as_root systemctl restart "$SERVICE_NAME"
}

print_summary() {
  cat <<EOF

FoundryUI deployment is complete.

Service:
  systemctl status $SERVICE_NAME
  journalctl -u $SERVICE_NAME -f
  systemctl restart $SERVICE_NAME

URLs:
  Frontend: http://$FRONTEND_HOST:$FRONTEND_PORT
  Backend:  http://$BACKEND_HOST:$BACKEND_PORT/health

Install directory:
  $INSTALL_DIR

To customize a future install, set environment variables before running:
  REPO_URL, INSTALL_DIR, SERVICE_NAME, SERVICE_USER, BACKEND_HOST, BACKEND_PORT, FRONTEND_HOST, FRONTEND_PORT

EOF
}

main() {
  log "Starting FoundryUI deployment."
  install_basic_packages_if_possible
  require_command git
  require_command curl
  require_command npm
  require_command node
  require_command systemctl
  check_node_version
  clone_or_update_repo
  run_project_setup
  build_frontend
  ensure_service_user_can_write
  write_runtime_script
  write_systemd_service
  print_summary
}

main "$@"
