#!/usr/bin/env bash
#
# haijunbot-daemon cross-platform build script.
#
# By default it produces Linux and Windows service binaries (amd64 / arm64 each, plus arm32 for Linux),
# all statically linked with CGO_ENABLED=0, ready to deploy directly to target machines.
#
# Usage:
#   ./scripts/build.sh                          # build all default targets
#   ./scripts/build.sh --version 5.0.5          # specify version
#   ./scripts/build.sh --targets linux/amd64    # build only specified targets
#   ./scripts/build.sh --output /tmp/out        # custom output directory
#   ./scripts/build.sh --clean                  # clean output directory before build
#
# Artifacts are placed in dist/, named haijunbot-daemon_<goos>_<goarch>[.exe],
# and dist/SHA256SUMS is generated for verification.
#
# Note: the daemon includes install / uninstall / start / stop / restart / status
# subcommands; this build script only produces the binaries. Service registration
# is handled by the binaries themselves.

set -euo pipefail

# Script directory and daemon module root (script is at <daemon>/scripts/).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${MODULE_DIR}/.." && pwd)"

# Default build matrix: Linux and Windows, two architectures each.
DEFAULT_TARGETS=(
  "linux/amd64"
  "linux/arm64"
  "linux/arm"
  "windows/amd64"
  "windows/arm64"
)

OUTPUT_DIR="${MODULE_DIR}/dist"
VERSION=""
TARGETS=()
CLEAN=0

# Print usage.
usage() {
  cat <<'EOF'
Usage: build.sh [options]

Options:
  --version <version>   version to inject (auto-detected by default)
  --targets <list>      comma-separated targets, e.g. linux/amd64,windows/amd64
                       default: linux/amd64,linux/arm64,linux/arm,windows/amd64,windows/arm64
  --output <dir>        artifact output directory (default <daemon>/dist)
  --clean               clean output directory before build
  -h, --help            show this help

Version detection order:
  --version argument > VERSION environment variable > repo-root pyproject.toml > git describe --tags
EOF
}

# Parse command-line arguments.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      [[ -n "${VERSION}" ]] || { echo "error: --version requires a value" >&2; exit 2; }
      shift 2
      ;;
    --targets)
      [[ -n "${2:-}" ]] || { echo "error: --targets requires a value" >&2; exit 2; }
      IFS=',' read -r -a TARGETS <<< "$2"
      shift 2
      ;;
    --output)
      [[ -n "${2:-}" ]] || { echo "error: --output requires a value" >&2; exit 2; }
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --clean)
      CLEAN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

# Check the Go toolchain.
if ! command -v go >/dev/null 2>&1; then
  echo "error: go command not found." >&2
  echo "If Go is already installed, run: export PATH=\$PATH:/usr/local/go/bin" >&2
  exit 1
fi

# Detect version: argument > environment variable > pyproject.toml > git tag.
detect_version() {
  # The --version argument is already in VERSION; the VERSION env var is the next priority.
  if [[ -n "${VERSION}" ]]; then
    echo "${VERSION}"
    return
  fi
  local pyproject="${REPO_ROOT}/pyproject.toml"
  if [[ -f "${pyproject}" ]]; then
    local v
    v="$(grep -m1 -E '^version[[:space:]]*=' "${pyproject}" \
      | sed -E 's/^version[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/')"
    if [[ -n "${v}" ]]; then
      echo "${v}"
      return
    fi
  fi
  if command -v git >/dev/null 2>&1; then
    local tag
    tag="$(git -C "${REPO_ROOT}" describe --tags --always 2>/dev/null || true)"
    if [[ -n "${tag}" ]]; then
      echo "${tag}"
      return
    fi
  fi
  echo "0.0.0-dev"
}

VERSION="$(detect_version)"

# Use the default matrix when no targets are specified explicitly.
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  TARGETS=("${DEFAULT_TARGETS[@]}")
fi

if [[ "${CLEAN}" -eq 1 ]]; then
  rm -rf "${OUTPUT_DIR}"
fi
mkdir -p "${OUTPUT_DIR}"

echo "==> haijunbot-daemon build"
echo "    module dir: ${MODULE_DIR}"
echo "    output dir: ${OUTPUT_DIR}"
echo "    version:    ${VERSION}"
echo "    targets:    ${TARGETS[*]}"
echo

# Build each target.
built=()
for target in "${TARGETS[@]}"; do
  goos="${target%%/*}"
  goarch="${target##*/}"
  if [[ -z "${goos}" || -z "${goarch}" || "${goos}" == "${goarch}" ]]; then
    echo "error: invalid target '${target}', expected <goos>/<goarch>" >&2
    exit 2
  fi

  ext=""
  if [[ "${goos}" == "windows" ]]; then
    ext=".exe"
  fi
  out="${OUTPUT_DIR}/haijunbot-daemon_${goos}_${goarch}${ext}"

  echo "--> building ${goos}/${goarch}"
  # CGO_ENABLED=0 ensures static linking without depending on target glibc version;
  # -trimpath strips local paths; -s -w strips the symbol table and debug info.
  # Must cd to the module root, otherwise ./cmd/haijunbot-daemon resolves relative to the caller's cwd.
  (
    cd "${MODULE_DIR}"
    CGO_ENABLED=0 GOOS="${goos}" GOARCH="${goarch}" \
      go build -trimpath \
        -ldflags "-s -w -X main.version=${VERSION}" \
        -o "${out}" ./cmd/haijunbot-daemon
  )

  built+=("${out}")
done

# Generate checksum file.
echo
echo "==> generating checksums"
(
  cd "${OUTPUT_DIR}"
  # Compute only for artifacts built this time, to avoid mixing in stale files.
  for f in "${built[@]}"; do
    basename "${f}"
  done | xargs sha256sum > SHA256SUMS
)
echo "    ${OUTPUT_DIR}/SHA256SUMS"

# Summarize artifacts.
echo
echo "==> build complete, artifacts:"
for f in "${built[@]}"; do
  size="$(du -h "${f}" | cut -f1)"
  printf '    %-48s %s\n' "$(basename "${f}")" "${size}"
done

echo
echo "hint: after deploying to the target machine, use '<binary> install' to register as a system service,"
echo "      Linux uses a systemd user service; Windows uses a logon scheduled task."
