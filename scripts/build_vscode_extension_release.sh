#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIR="$ROOT_DIR/src/haijunbot/haijunbot_vscode_extension"

if [[ ! -d "$EXT_DIR" ]]; then
  echo "[ERROR] VS Code extension directory does not exist: $EXT_DIR" >&2
  exit 1
fi

cd "$EXT_DIR"

echo "[INFO] Working directory: $EXT_DIR"

if [[ ! -f package.json ]]; then
  echo "[ERROR] package.json not found" >&2
  exit 1
fi

if [[ ! -d node_modules ]]; then
  echo "[INFO] Installing dependencies..."
  npm install
else
  echo "[INFO] Using existing node_modules"
fi

echo "[INFO] Compiling TypeScript..."
npm run build

if [[ ! -f dist/extension.js ]]; then
  echo "[ERROR] Build artifact dist/extension.js not found after compilation" >&2
  exit 1
fi

echo "[INFO] Packaging VSIX..."
rm -f ./*.vsix
npm run package

VSIX_PATH="$(find . -maxdepth 1 -type f -name '*.vsix' | head -n 1)"
if [[ -z "$VSIX_PATH" ]]; then
  echo "[ERROR] .vsix artifact not found after packaging" >&2
  exit 1
fi

echo "[SUCCESS] TypeScript artifact: $EXT_DIR/dist/extension.js"
echo "[SUCCESS] VSIX artifact: $EXT_DIR/${VSIX_PATH#./}"
