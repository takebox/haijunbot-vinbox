#!/bin/bash

set -e

# ===== Offline install package creation script =====
# Purpose: package HaijunBot and all its dependencies into an offline install package
# Usage: ./scripts/create_offline_package.sh [output-dir]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$(dirname "$SCRIPT_DIR")" && pwd)"
OUTPUT_DIR="${1:-$PROJECT_ROOT/offline_package}"
PACKAGE_NAME="haijunbot-offline-$(date +%Y%m%d-%H%M%S).tar.gz"

# ===== Color output =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
	echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
	echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
	echo -e "${RED}[ERROR]${NC} $1"
}

# ===== Detect system architecture =====
ARCH=$(uname -m)
case "$ARCH" in
x86_64)
	ARCH_NAME="x86_64"
	;;
aarch64 | arm64)
	ARCH_NAME="aarch64"
	;;
*)
	log_error "Unsupported system architecture: $ARCH"
	exit 1
	;;
esac

log_info "Detected system architecture: $ARCH_NAME"

# ===== Create temporary packaging directory =====
# Use a disk directory instead of /tmp (tmpfs has limited capacity)
TEMP_BASE="$HOME/.cache/haijunbot-offline-tmp"
mkdir -p "$TEMP_BASE"
TEMP_DIR=$(mktemp -d -p "$TEMP_BASE")
PACKAGE_DIR="$TEMP_DIR/haijunbot-offline"
mkdir -p "$PACKAGE_DIR"

log_info "Creating temporary packaging directory: $PACKAGE_DIR"

# ===== 1. Package project source =====
log_info "Step 1: package project source..."

# Exclude unnecessary files
EXCLUDE_PATTERNS="
--exclude=.git
--exclude=.venv
--exclude=node_modules
--exclude=__pycache__
--exclude=*.pyc
--exclude=*.pyo
--exclude=.pytest_cache
--exclude=.mypy_cache
--exclude=.ruff_cache
--exclude=offline_package
--exclude=*.tar.gz
--exclude=*.zip
"

rsync -a $EXCLUDE_PATTERNS "$PROJECT_ROOT/" "$PACKAGE_DIR/source/"

log_info "Source packaging complete"

# ===== 2. Create and package a clean virtual environment =====
log_info "Step 2: create a clean virtual environment..."

# Create temporary virtual environment directory
BUILD_VENV="$TEMP_DIR/build_venv"

# Use uv to create a new virtual environment (faster and cleaner)
if command -v uv &>/dev/null; then
	UV_BIN="uv"
else
	UV_BIN="$PROJECT_ROOT/src/haijunbot/haijunbot_data/deps/${ARCH_NAME}_linux/bin/uv"
	if [ ! -f "$UV_BIN" ]; then
		log_error "uv tool not found"
		exit 1
	fi
fi

log_info "Creating virtual environment with uv: $UV_BIN"
$UV_BIN venv "$BUILD_VENV" --python 3.12

# Activate the virtual environment and install dependencies
source "$BUILD_VENV/bin/activate"

# Install project dependencies (only required dependencies, no dev dependencies)
log_info "Installing project dependencies..."
cd "$PROJECT_ROOT"
$UV_BIN pip install -e . --no-cache-dir

# Clean up cache and compiled files
find "$BUILD_VENV" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_VENV" -type f -name '*.pyc' -delete 2>/dev/null || true
find "$BUILD_VENV" -type f -name '*.pyo' -delete 2>/dev/null || true
find "$BUILD_VENV" -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_VENV" -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

# Copy the virtual environment to the packaging directory
rsync -a --exclude=__pycache__ --exclude='*.pyc' --exclude='*.pyo' --exclude=.pytest_cache --exclude='*.egg-info' "$BUILD_VENV/" "$PACKAGE_DIR/venv/"

# Record the virtual environment path (used to fix path references during install)
echo "$BUILD_VENV" >"$PACKAGE_DIR/venv_origin_path.txt"

log_info "Virtual environment packaging complete ($(du -sh "$PACKAGE_DIR/venv" | cut -f1))"

# Exit the virtual environment
deactivate
cd "$SCRIPT_DIR"

# ===== 3. Package the standalone Python environment =====
log_info "Step 3: package the standalone Python environment..."

# Use uv to download the standalone Python 3.12 environment
if command -v uv &>/dev/null; then
	UV_BIN="uv"
else
	# Use the bundled uv
	UV_BIN="$PROJECT_ROOT/src/haijunbot/haijunbot_data/deps/${ARCH_NAME}_linux/bin/uv"
	if [ ! -f "$UV_BIN" ]; then
		log_error "uv tool not found"
		exit 1
	fi
fi

log_info "Using uv: $UV_BIN"

# Download the standalone Python 3.12 environment
PYTHON_DIR="$PACKAGE_DIR/python"
mkdir -p "$PYTHON_DIR"

$UV_BIN python install 3.12 --install-dir "$PYTHON_DIR" --no-cache

if [ -d "$PYTHON_DIR" ]; then
	log_info "Python environment packaging complete ($(du -sh "$PYTHON_DIR" | cut -f1))"
else
	log_warn "Python environment download failed; it will be downloaded from a mirror during install"
fi

# ===== 4. Package bundled dependencies =====
log_info "Step 4: package bundled dependencies..."

DEPS_SRC="$PROJECT_ROOT/src/haijunbot/haijunbot_data/deps"
if [ -d "$DEPS_SRC" ]; then
	# Only copy the dependency directory for the current architecture to reduce the offline package size
	mkdir -p "$PACKAGE_DIR/deps"
	if [ -d "$DEPS_SRC/${ARCH_NAME}_linux" ]; then
		rsync -a "$DEPS_SRC/${ARCH_NAME}_linux/" "$PACKAGE_DIR/deps/${ARCH_NAME}_linux/"
		log_info "Bundled dependencies packaging complete ($(du -sh "$PACKAGE_DIR/deps" | cut -f1))"
	else
		log_warn "Bundled dependency directory for the current architecture not found: ${ARCH_NAME}_linux"
	fi
else
	log_warn "Bundled dependency directory not found"
fi

# ===== 5. Package frontend build artifacts =====
log_info "Step 5: package frontend build artifacts..."

FRONTEND_DIST="$PROJECT_ROOT/src/haijunbot/haijunbot_service/frontend/dist"
if [ -d "$FRONTEND_DIST" ]; then
	mkdir -p "$PACKAGE_DIR/frontend"
	rsync -a "$FRONTEND_DIST/" "$PACKAGE_DIR/frontend/dist/"
	log_info "Frontend build artifacts packaging complete ($(du -sh "$PACKAGE_DIR/frontend/dist" | cut -f1))"
else
	log_warn "Frontend build artifacts not found, skipping packaging"
fi

# ===== 6. Create install script =====
log_info "Step 6: create install script..."

INSTALL_SCRIPT="$PACKAGE_DIR/install.sh"
cat >"$INSTALL_SCRIPT" <<'INSTALL_EOF'
#!/bin/bash

set -e

# ===== Offline install script =====
# Purpose: install HaijunBot from the offline package
# Usage: ./install.sh [install-dir]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${1:-$HOME/HaijunBot}"

# ===== Color output =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== Detect system architecture =====
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) ARCH_NAME="x86_64"; ;;
    aarch64|arm64) ARCH_NAME="aarch64"; ;;
    *) log_error "Unsupported architecture: $ARCH"; exit 1; ;;
esac

log_info "Detected system architecture: $ARCH_NAME"

# ===== 1. Extract source =====
log_info "Step 1: install source to $INSTALL_DIR..."

if [ -d "$INSTALL_DIR" ]; then
    log_warn "Target directory already exists; the old directory will be backed up"
    mv "$INSTALL_DIR" "$INSTALL_DIR.backup.$(date +%Y%m%d%H%M%S)"
fi

mkdir -p "$INSTALL_DIR"
rsync -a "$SCRIPT_DIR/source/" "$INSTALL_DIR/"

log_info "Source installation complete"

# ===== 2. Install virtual environment =====
log_info "Step 2: install virtual environment..."

if [ -d "$SCRIPT_DIR/venv" ]; then
    mkdir -p "$INSTALL_DIR/.venv"
    rsync -a "$SCRIPT_DIR/venv/" "$INSTALL_DIR/.venv/"

    # Fix the virtual environment path
    cd "$INSTALL_DIR"

    # Read the original virtual environment path
    ORIGIN_VENV_PATH=""
    if [ -f "$SCRIPT_DIR/venv_origin_path.txt" ]; then
        ORIGIN_VENV_PATH=$(cat "$SCRIPT_DIR/venv_origin_path.txt")
    fi

    # If there is an original path, replace it with the install path; otherwise replace the extraction path
    if [ -n "$ORIGIN_VENV_PATH" ]; then
        SEARCH_PATH="$ORIGIN_VENV_PATH"
    else
        SEARCH_PATH="$SCRIPT_DIR/.venv"
    fi

    # Update the shebang paths of scripts in the bin directory
    for script in .venv/bin/*; do
        if [ -f "$script" ]; then
            sed -i "s|$SEARCH_PATH|$INSTALL_DIR/.venv|g" "$script" 2>/dev/null || true
        fi
    done

    # Update the VIRTUAL_ENV variable in the activate script
    if [ -f ".venv/bin/activate" ]; then
        sed -i "s|VIRTUAL_ENV=.*|VIRTUAL_ENV=\"$INSTALL_DIR/.venv\"|g" ".venv/bin/activate"
    fi

    # Update pyvenv.cfg
    if [ -f ".venv/pyvenv.cfg" ]; then
        sed -i "s|home = .*|home = $INSTALL_DIR/.venv/bin|g" ".venv/pyvenv.cfg"
    fi

    log_info "Virtual environment installation complete"
else
    log_error "The offline package does not include a virtual environment; offline installation requires one"
    exit 1
fi

# ===== 3. Install Python environment =====
log_info "Step 3: configure Python environment..."

if [ -d "$SCRIPT_DIR/python" ]; then
    # The directory structure created by uv python install --install-dir is cpython-3.12.x-linux-x86_64-gnu/bin/python3.12
    # The bin/ and lib/ contents inside the cpython subdirectory must be promoted/copied into the corresponding .venv/ locations
    log_info "Copying standalone Python environment..."
    
    # Find the cpython subdirectory (wildcard match)
    CPYTHON_DIR=$(find "$SCRIPT_DIR/python" -maxdepth 1 -type d -name "cpython-*" | head -n 1)
    
    if [ -n "$CPYTHON_DIR" ] && [ -d "$CPYTHON_DIR" ]; then
        # Copy the contents of the bin directory to .venv/bin/
        if [ -d "$CPYTHON_DIR/bin" ]; then
            mkdir -p "$INSTALL_DIR/.venv/bin"
            rsync -a "$CPYTHON_DIR/bin/" "$INSTALL_DIR/.venv/bin/" --exclude='*.pyc' --exclude='__pycache__'
        fi
        
        # Copy the contents of the lib directory to .venv/lib/
        if [ -d "$CPYTHON_DIR/lib" ]; then
            mkdir -p "$INSTALL_DIR/.venv/lib"
            rsync -a "$CPYTHON_DIR/lib/" "$INSTALL_DIR/.venv/lib/" --exclude='*.pyc' --exclude='__pycache__'
        fi
        
        log_info "Python environment configuration complete"
    else
        log_warn "cpython subdirectory not found, skipping Python environment copy"
    fi
fi

# ===== 4. Install bundled dependencies =====
log_info "Step 4: install bundled dependencies..."

if [ -d "$SCRIPT_DIR/deps" ]; then
    DEPS_DEST="$INSTALL_DIR/src/haijunbot/haijunbot_data/deps"
    mkdir -p "$DEPS_DEST"
    rsync -a "$SCRIPT_DIR/deps/" "$DEPS_DEST/"
    
    # Add bundled tools to PATH
    export PATH="$DEPS_DEST/${ARCH_NAME}_linux/bin:$PATH"
    log_info "Bundled dependencies installation complete"
fi

# ===== 5. Install frontend build artifacts =====
log_info "Step 5: install frontend build artifacts..."

if [ -d "$SCRIPT_DIR/frontend/dist" ]; then
    FRONTEND_DEST="$INSTALL_DIR/src/haijunbot/haijunbot_service/frontend"
    mkdir -p "$FRONTEND_DEST"
    rsync -a "$SCRIPT_DIR/frontend/dist/" "$FRONTEND_DEST/dist/"
    log_info "Frontend build artifacts installation complete"
fi

# ===== 6. Install HaijunBot =====
log_info "Step 6: install HaijunBot to the system..."

cd "$INSTALL_DIR"

# Activate the virtual environment
source .venv/bin/activate

# Install HaijunBot (using the existing virtual environment; no need to download dependencies)
# Offline install: use only the existing virtual environment dependencies, do not attempt online installation
pip install -e . --no-deps || {
    log_error "Offline installation failed; make sure the virtual environment includes all required dependencies"
    exit 1
}

log_info "HaijunBot installation complete"

# ===== 7. Configure shell environment =====
log_info "Step 7: configure shell environment..."

# Detect the current shell
SHELL_NAME=$(basename "$SHELL")
SHELL_CONFIG=""

case "$SHELL_NAME" in
    bash) SHELL_CONFIG="$HOME/.bashrc"; ;;
    zsh) SHELL_CONFIG="$HOME/.zshrc"; ;;
    fish) SHELL_CONFIG="$HOME/.config/fish/config.fish"; ;;
    *) log_warn "Unknown shell type; please configure manually"; ;;
esac

# Add PATH configuration
if [ -n "$SHELL_CONFIG" ]; then
    PATH_LINE="export PATH=\"$INSTALL_DIR/.venv/bin:\$PATH\""
    if ! grep -q "$PATH_LINE" "$SHELL_CONFIG" 2>/dev/null; then
        echo "" >> "$SHELL_CONFIG"
        echo "# HaijunBot offline installation" >> "$SHELL_CONFIG"
        echo "$PATH_LINE" >> "$SHELL_CONFIG"
        log_info "Updated $SHELL_CONFIG"
    fi
fi

# ===== 8. Verify installation =====
log_info "Step 8: verify installation..."

export PATH="$INSTALL_DIR/.venv/bin:$PATH"

if command -v haijunbot &> /dev/null; then
    HAIJUNBOT_VERSION=$(haijunbot --version 2>&1 || echo "unknown version")
    log_info "✓ HaijunBot installed: $HAIJUNBOT_VERSION"
else
    log_warn "haijunbot command not found; please manually source the config file"
fi

# ===== Installation complete =====
log_info "========================================"
log_info "✓ HaijunBot offline installation complete!"
log_info "========================================"
log_info "Install location: $INSTALL_DIR"
log_info "Virtual environment: $INSTALL_DIR/.venv"
log_info ""
log_info "Quick start:"
log_info "  1. Run the following command to activate the environment:"
log_info "     source $SHELL_CONFIG"
log_info "     or"
log_info "     source $INSTALL_DIR/.venv/bin/activate"
log_info ""
log_info "  2. Start HaijunBot:"
log_info "     haijunbot"
log_info ""
log_info "========================================"
INSTALL_EOF

chmod +x "$INSTALL_SCRIPT"

log_info "Install script creation complete"

# ===== 7. Create README =====
log_info "Step 7: create README document..."

README_FILE="$PACKAGE_DIR/README.md"
cat >"$README_FILE" <<'README_EOF'
# HaijunBot Offline Install Package

## Contents

- **source**: HaijunBot source code
- **venv**: Python virtual environment (includes all dependencies)
- **python**: standalone Python 3.12 environment
- **deps**: bundled tools (uv, rg, fd, tmux, etc.)
- **frontend**: frontend build artifacts
- **install.sh**: install script

## Installation

1. Extract the offline package:
   ```bash
   tar -xzf haijunbot-offline-*.tar.gz
   cd haijunbot-offline
   ```

2. Run the install script:
   ```bash
   ./install.sh [install-dir]
   ```
   Installs to \`$HOME/HaijunBot\` by default

3. Activate the environment:
   ```bash
   source ~/.bashrc  # or source ~/.zshrc
   ```

4. Start HaijunBot:
   ```bash
   haijunbot
   ```

## System requirements

- Linux system (x86_64 or aarch64 architecture)
- At least 2GB of available disk space
- Git (optional, for version management)

## Notes

- This offline package is built for a specific architecture; make sure the architecture matches
- The first launch after installation may require configuring an API key
- If you encounter problems, check the installation log

README_EOF

log_info "README document creation complete"

# ===== 8. Package and compress =====
log_info "Step 8: package and compress..."

mkdir -p "$OUTPUT_DIR"
PACKAGE_FILE="$OUTPUT_DIR/$PACKAGE_NAME"

cd "$TEMP_DIR"
tar -czf "$PACKAGE_FILE" haijunbot-offline

PACKAGE_SIZE=$(du -sh "$PACKAGE_FILE" | cut -f1)

log_info "Offline package creation complete: $PACKAGE_FILE"
log_info "Offline package size: $PACKAGE_SIZE"

# ===== 9. Clean up temporary files =====
log_info "Step 9: clean up temporary files..."

rm -rf "$TEMP_DIR"

log_info "Temporary files cleanup complete"

# ===== Complete =====
log_info "========================================"
log_info "✓ Offline install package created successfully!"
log_info "========================================"
log_info "Output file: $PACKAGE_FILE"
log_info "Package size: $PACKAGE_SIZE"
log_info "Architecture: $ARCH_NAME"
log_info ""
log_info "Usage:"
log_info "  1. Transfer the offline package to the target machine"
log_info "  2. Extract: tar -xzf $PACKAGE_NAME"
log_info "  3. Install: ./install.sh"
log_info ""
log_info "========================================"
