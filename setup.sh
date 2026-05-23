#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
MODELS_DIR="$ROOT_DIR/models"
FOUNDRY_DIR="$ROOT_DIR/foundry"
TOOLS_DIR="$ROOT_DIR/.tools"
UV_BIN="${UV_BIN:-}"

command -v npm >/dev/null || {
  echo "npm is required." >&2
  exit 1
}

command -v git >/dev/null || {
  echo "git is required." >&2
  exit 1
}

if [[ -z "$UV_BIN" ]]; then
  UV_BIN="$(command -v uv || true)"
fi

if [[ -z "$UV_BIN" ]]; then
  command -v curl >/dev/null || {
    echo "curl is required to bootstrap uv." >&2
    exit 1
  }

  mkdir -p "$TOOLS_DIR"
  curl -LsSf https://astral.sh/uv/install.sh | env \
    UV_UNMANAGED_INSTALL="$TOOLS_DIR" \
    sh
  UV_BIN="$TOOLS_DIR/uv"
fi

export UV_CACHE_DIR="$ROOT_DIR/.uv-cache"
export UV_PYTHON_INSTALL_DIR="$ROOT_DIR/.python"
export FOUNDRY_CHECKPOINT_DIRS="$MODELS_DIR"

"$UV_BIN" python install 3.12
"$UV_BIN" venv --clear --seed --python 3.12 "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/backend/requirements-dev.txt"
"$VENV_DIR/bin/python" -m pip install "rc-foundry[all]"

if [[ ! -d "$FOUNDRY_DIR/.git" ]]; then
  git clone https://github.com/RosettaCommons/foundry.git "$FOUNDRY_DIR"
fi

"$VENV_DIR/bin/foundry" install base-models --checkpoint-dir "$MODELS_DIR"

cd "$ROOT_DIR/frontend"
npm install

echo "Environment ready."
echo "Activate Python with: source .venv/bin/activate"
echo "Expose Foundry checkpoints with: export FOUNDRY_CHECKPOINT_DIRS=\"$MODELS_DIR\""
