#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$ROOT/docs"
PUBLIC_DIR="$ROOT/public"

if [ ! -f "$DOCS_DIR/index.html" ]; then
  echo "docs/index.html was not found."
  exit 1
fi

rm -rf "$PUBLIC_DIR"
mkdir -p "$PUBLIC_DIR"
cp -R "$DOCS_DIR"/. "$PUBLIC_DIR"/

cat > "$ROOT/.gitlab-pages-docs.yml" <<'YAML'
pages:
  stage: deploy
  script:
    - echo "Publishing FoundryUI docs"
  artifacts:
    paths:
      - public
  only:
    - main
YAML

echo "Prepared GitLab Pages content in ./public."
echo "Use .gitlab-pages-docs.yml as the GitLab CI config for docs-only Pages publishing."
