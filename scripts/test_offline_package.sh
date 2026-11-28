#!/bin/bash

# ===== Offline package test script =====
# Purpose: test the basic functionality of the offline package
# Usage: ./scripts/test_offline_package.sh [offline-package-path]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_DIR")" && pwd)"

# ===== Color output =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== Argument check =====
if [ $# -lt 1 ]; then
    log_error "Usage: $0 <offline-package-path>"
    log_info "Example: $0 offline_package/haijunbot-offline-*.tar.gz"
    exit 1
fi

PACKAGE_FILE="$1"

if [ ! -f "$PACKAGE_FILE" ]; then
    log_error "Offline package file does not exist: $PACKAGE_FILE"
    exit 1
fi

log_info "Testing offline package: $PACKAGE_FILE"

# ===== Create test environment =====
TEST_DIR=$(mktemp -d)
log_info "Creating test environment: $TEST_DIR"

# ===== 1. Extraction test =====
log_info "Step 1: test extraction..."

cd "$TEST_DIR"
tar -xzf "$PACKAGE_FILE"

if [ ! -d "haijunbot-offline" ]; then
    log_error "Extraction failed: haijunbot-offline directory not found"
    exit 1
fi

log_info "✓ Extraction succeeded"

# ===== 2. File structure check =====
log_info "Step 2: check file structure..."

cd haijunbot-offline

# Check required files
REQUIRED_FILES="source install.sh README.md"
MISSING_FILES=""

for file in $REQUIRED_FILES; do
    if [ ! -e "$file" ]; then
        MISSING_FILES="$MISSING_FILES $file"
    fi
done

if [ -n "$MISSING_FILES" ]; then
    log_error "Missing required files: $MISSING_FILES"
    exit 1
fi

log_info "✓ File structure check passed"

# ===== 3. Install script check =====
log_info "Step 3: check install script..."

if [ ! -x "install.sh" ]; then
    log_error "install.sh is not executable"
    exit 1
fi

# Check install script syntax
if ! bash -n install.sh; then
    log_error "install.sh syntax error"
    exit 1
fi

log_info "✓ Install script check passed"

# ===== 4. Source check =====
log_info "Step 4: check source..."

if [ ! -f "source/pyproject.toml" ]; then
    log_error "Missing pyproject.toml"
    exit 1
fi

if [ ! -d "source/src" ]; then
    log_error "Missing src directory"
    exit 1
fi

log_info "✓ Source check passed"

# ===== 5. Virtual environment check =====
log_info "Step 5: check virtual environment..."

if [ -d "venv" ]; then
    VENV_SIZE=$(du -sh venv | cut -f1)
    log_info "Virtual environment size: $VENV_SIZE"
    
    # Check key files
    if [ ! -f "venv/bin/python" ]; then
        log_warn "Missing python executable in the virtual environment"
    fi
    
    log_info "✓ Virtual environment check passed"
else
    log_warn "The offline package does not include a virtual environment"
fi

# ===== 6. Bundled dependencies check =====
log_info "Step 6: check bundled dependencies..."

if [ -d "deps" ]; then
    DEPS_SIZE=$(du -sh deps | cut -f1)
    log_info "Bundled dependencies size: $DEPS_SIZE"
    
    # Check architecture directory
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64) ARCH_DIR="x86_64_linux"; ;;
        aarch64|arm64) ARCH_DIR="aarch64_linux"; ;;
        *) log_warn "Unknown architecture: $ARCH"; ;;
    esac
    
    if [ -n "$ARCH_DIR" ] && [ -d "deps/$ARCH_DIR" ]; then
        # Check key tools
        if [ -f "deps/$ARCH_DIR/bin/uv" ]; then
            log_info "✓ Found uv tool"
        else
            log_warn "Missing uv tool"
        fi
    fi
    
    log_info "✓ Bundled dependencies check passed"
else
    log_warn "The offline package does not include bundled dependencies"
fi

# ===== 7. Package size statistics =====
log_info "Step 7: measure package size..."

TOTAL_SIZE=$(du -sh . | cut -f1)
log_info "Total offline package size: $TOTAL_SIZE"

# Size of each part
echo ""
echo "Size statistics by part:"
echo "----------------"
du -sh source venv python deps frontend 2>/dev/null | while read size path; do
    echo "  $path: $size"
done

# ===== 8. Clean up test environment =====
log_info "Step 8: clean up test environment..."

cd "$PROJECT_ROOT"
rm -rf "$TEST_DIR"

log_info "✓ Test environment cleanup complete"

# ===== Test complete =====
log_info "========================================"
log_info "✓ Offline package test passed!"
log_info "========================================"
log_info "Offline package file: $PACKAGE_FILE"
log_info "Total size: $TOTAL_SIZE"
log_info ""
log_info "You can install using the following commands:"
log_info "  tar -xzf $PACKAGE_FILE"
log_info "  cd haijunbot-offline"
log_info "  ./install.sh"
log_info ""
log_info "========================================"
