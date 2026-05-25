#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCS_DIR="$ROOT/docs"
BRANCH="${GITHUB_PAGES_BRANCH:-gh-pages}"

if [ ! -f "$DOCS_DIR/index.html" ]; then
  echo "docs/index.html was not found."
  exit 1
fi

if ! git -C "$ROOT" diff --quiet || ! git -C "$ROOT" diff --cached --quiet; then
  echo "Working tree has uncommitted changes. Commit or stash before publishing docs."
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

git -C "$ROOT" worktree add "$TMP" "$BRANCH" 2>/dev/null || git -C "$ROOT" worktree add --orphan "$TMP" "$BRANCH"
find "$TMP" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
cp -R "$DOCS_DIR"/. "$TMP"/
touch "$TMP/.nojekyll"
git -C "$TMP" add .
git -C "$TMP" commit -m "Publish docs" || echo "No documentation changes to publish."
git -C "$TMP" push origin "$BRANCH"

echo "Published docs/ to GitHub Pages branch '$BRANCH'."
