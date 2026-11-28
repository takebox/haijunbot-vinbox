#!/usr/bin/env bash
# Install the Gitleaks credential scanner (user-level, no sudo required).
#
# Gitleaks is the preferred scanner for the pre-commit hook .githooks/pre-commit; when not installed,
# the hook automatically falls back to the built-in lightweight scanner (fewer rules). This script installs Gitleaks.
#
# Usage:
#   bash scripts/install-gitleaks.sh          # install the latest version
#   GITLEAKS_VERSION=8.30.1 bash scripts/install-gitleaks.sh   # specify a version
#
# Install location: $HOME/.local/bin/gitleaks (usable immediately after install if that directory is in PATH)
set -euo pipefail

VERSION="${GITLEAKS_VERSION:-8.30.1}"
INSTALL_DIR="${GITLEAKS_INSTALL_DIR:-$HOME/.local/bin}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Detect operating system and architecture
case "$(uname -s)" in
    Linux)  OS="linux" ;;
    Darwin) OS="darwin" ;;
    *) echo "Error: unsupported operating system $(uname -s)" >&2; exit 1 ;;
esac
case "$(uname -m)" in
    x86_64|amd64)  ARCH="x64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    armv7l)        ARCH="armv7" ;;
    armv6l)        ARCH="armv6" ;;
    *) echo "Error: unsupported architecture $(uname -m)" >&2; exit 1 ;;
esac

URL="https://github.com/gitleaks/gitleaks/releases/download/v${VERSION}/gitleaks_${VERSION}_${OS}_${ARCH}.tar.gz"
echo "Downloading Gitleaks v${VERSION} (${OS}/${ARCH}) ..."
echo "  $URL"

curl -fSL --retry 3 -o "$TMP_DIR/gitleaks.tar.gz" "$URL"
tar -xzf "$TMP_DIR/gitleaks.tar.gz" -C "$TMP_DIR"

mkdir -p "$INSTALL_DIR"
install -m 0755 "$TMP_DIR/gitleaks" "$INSTALL_DIR/gitleaks"

"$INSTALL_DIR/gitleaks" version

echo ""
echo "✅ Installed to $INSTALL_DIR/gitleaks"
if ! echo ":$PATH:" | grep -q ":$INSTALL_DIR:"; then
    echo "⚠️  Note: $INSTALL_DIR is not in PATH."
    echo "   Add the following line to ~/.bashrc (or ~/.zshrc) and log in again:"
    echo "   export PATH=\"$INSTALL_DIR:\$PATH\""
    echo "   Or run: bash scripts/install-git-hooks.sh and then specify the gitleaks path manually."
fi
echo "   The pre-commit hook will automatically detect and use gitleaks."
