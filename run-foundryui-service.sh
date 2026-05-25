#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/opt/FoundryUI"
BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_HOST="127.0.0.1"
FRONTEND_PORT="3000"
FRONTEND_INTERNAL_HOST="127.0.0.1"
FRONTEND_INTERNAL_PORT="3001"
NGINX_PREFIX="$ROOT_DIR/runtime/nginx"
NGINX_CONFIG="$ROOT_DIR/nginx-foundryui.conf"

export FOUNDRY_CHECKPOINT_DIRS="$ROOT_DIR/models"
export FOUNDRYUI_RFD3_CKPT="${FOUNDRYUI_RFD3_CKPT:-$ROOT_DIR/models/rfd3_latest.ckpt}"
export FOUNDRYUI_RF3_CKPT="${FOUNDRYUI_RF3_CKPT:-$ROOT_DIR/models/rf3_foundry_01_24_latest_remapped.ckpt}"
export HOST="$FRONTEND_INTERNAL_HOST"
export PORT="$FRONTEND_INTERNAL_PORT"
export NITRO_HOST="$FRONTEND_INTERNAL_HOST"
export NITRO_PORT="$FRONTEND_INTERNAL_PORT"

cd "$ROOT_DIR"
mkdir -p "$NGINX_PREFIX/logs" "$NGINX_PREFIX/tmp/client_body" "$NGINX_PREFIX/tmp/proxy" "$NGINX_PREFIX/tmp/fastcgi" "$NGINX_PREFIX/tmp/uwsgi" "$NGINX_PREFIX/tmp/scgi"

"$ROOT_DIR/.venv/bin/uvicorn" backend.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" &
backend_pid="$!"

node "$ROOT_DIR/frontend/.output/server/index.mjs" &
frontend_pid="$!"

nginx -p "$NGINX_PREFIX/" -c "$NGINX_CONFIG" -g "daemon off;" &
nginx_pid="$!"

shutdown() {
  kill "$backend_pid" "$frontend_pid" "$nginx_pid" 2>/dev/null || true
  wait "$backend_pid" "$frontend_pid" "$nginx_pid" 2>/dev/null || true
}
trap shutdown INT TERM

wait -n "$backend_pid" "$frontend_pid" "$nginx_pid"
status="$?"
shutdown
exit "$status"
