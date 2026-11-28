#!/usr/bin/env bash
# Install HaijunBot Git hooks (enables pre-commit credential scanning protection).
#
# Usage:
#   bash scripts/install-git-hooks.sh
#
# Run once after each clone of the repository (core.hooksPath is local config, not distributed with the repo).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d .githooks ]; then
    echo "Error: .githooks directory not found; make sure you run this from the repository root." >&2
    exit 1
fi

# Ensure hook script is executable
chmod +x .githooks/pre-commit

git config core.hooksPath .githooks

echo "✅ Git hooks enabled (core.hooksPath = .githooks)"
echo "   Suspected credentials in the staging area will be scanned automatically before commit."
echo "   Emergency bypass: HAIJUNBOT_ALLOW_SECRETS=1 git commit ..."
if ! command -v gitleaks >/dev/null 2>&1; then
    echo ""
    echo "ℹ️  Gitleaks not detected; the built-in lightweight scanner (fewer rules) will be used before commit."
    echo "   Recommended to install Gitleaks for more comprehensive detection: bash scripts/install-gitleaks.sh"
fi
