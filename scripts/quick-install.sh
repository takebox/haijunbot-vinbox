#!/bin/bash

# HaijunBot minimal install script
# Supports automatic installation of dependency tools and automatic upgrade
#
# For users in China to fetch the script (GitHub raw may time out):
#   bash -c "$(curl -fsSL https://gitee.com/takebox/HaijunBot/raw/main/scripts/quick-install.sh)"

set -e

# ===== Configuration =====
GITHUB_URL="https://github.com/takebox/HaijunBot.git"
GITEE_URL="https://gitee.com/takebox/HaijunBot.git"
DEST_DIR="$HOME/HaijunBot"
DEFAULT_BRANCH="main"

# Mirror configuration (acceleration for users in China)
export UV_PYTHON_INSTALL_MIRROR="https://python-standalone.org/mirror/astral-sh/python-build-standalone/"
export UV_DEFAULT_INDEX="https://mirrors.aliyun.com/pypi/simple/"
export UV_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"
# Limit the number of parallel downloads to avoid triggering remote source rate limiting (403)
export UV_CONCURRENT_DOWNLOADS=4

# ===== Color output =====
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== Resumable install state marker =====
STATE_FILE="$HOME/.haijunbot/.install_state"

set_state() {
	mkdir -p "$(dirname "$STATE_FILE")"
	echo "$1" >>"$STATE_FILE"
}

check_state() {
	[ -f "$STATE_FILE" ] && grep -q "^$1$" "$STATE_FILE"
}

clear_state() {
	rm -f "$STATE_FILE"
}

# ===== Detect system =====
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
Linux) PLATFORM="unknown-linux-gnu" ;;
Darwin) PLATFORM="apple-darwin" ;;
*)
	echo_error "Unsupported operating system: $OS"
	exit 1
	;;
esac

case "$ARCH" in
x86_64) ARCH_TYPE="x86_64" ;;
aarch64 | arm64) ARCH_TYPE="aarch64" ;;
*)
	echo_error "Unsupported architecture: $ARCH"
	exit 1
	;;
esac

echo_info "Detected system: $OS $ARCH"

# ===== Install uv (required) =====
install_uv() {
	if check_state "uv"; then
		echo_info "uv already installed, skipping"
		return 0
	fi

	if command -v uv &>/dev/null; then
		echo_info "uv already installed: $(uv --version)"
		return 0
	fi

	echo_info "Installing uv..."

	# Try multiple install sources: Chinese public mirror -> official
	local UV_INSTALL_URLS=(
		"https://uv.agentsmirror.com/install-cn.sh"
		"https://astral.sh/uv/install.sh"
	)

	for url in "${UV_INSTALL_URLS[@]}"; do
		echo_info "Trying install source: $url"
		if curl -LsSf "$url" -o /tmp/uv-install.sh 2>/dev/null && sh /tmp/uv-install.sh 2>/dev/null; then
			export PATH="$HOME/.local/bin:$PATH"
			echo_info "uv installed successfully"
			rm -f /tmp/uv-install.sh
			return 0
		fi
		rm -f /tmp/uv-install.sh
		echo_warn "Install source failed, trying the next one..."
	done

	# Fallback: manually download the binary (multi-source retry)
	echo_warn "Install-script method failed, trying manual download..."
	local TEMP_DIR=$(mktemp -d)
	local UV_DOWNLOAD_URLS=(
		"https://uv.agentsmirror.com/github/astral-sh/uv/releases/download/latest/uv-${ARCH_TYPE}-${PLATFORM}.tar.gz"
		"https://github.com/astral-sh/uv/releases/latest/download/uv-${ARCH_TYPE}-${PLATFORM}.tar.gz"
	)

	for url in "${UV_DOWNLOAD_URLS[@]}"; do
		echo_info "Trying download: $url"
		if curl -L "$url" | tar -xzf - -C "$TEMP_DIR" 2>/dev/null; then
			mkdir -p "$HOME/.local/bin"
			mv "$TEMP_DIR"/uv-* "$HOME/.local/bin/uv" 2>/dev/null || true
			chmod +x "$HOME/.local/bin/uv"
			export PATH="$HOME/.local/bin:$PATH"
			echo_info "uv installed successfully (manual download method)"
			rm -rf "$TEMP_DIR"
			return 0
		fi
		echo_warn "Download source failed, trying the next one..."
	done

	rm -rf "$TEMP_DIR"
	echo_error "uv installation failed; please install manually: https://docs.astral.sh/uv/"
	return 1
}

# ===== Install optional tools =====
install_optional_tools() {
	if check_state "optional_tools"; then
		echo_info "Optional tools already installed, skipping"
		return 0
	fi

	local tools=("rg:ripgrep" "fd:fd-find" "fzf:fzf" "tmux:tmux" "tree:tree")

	echo ""
	echo_info "Optional tools installation (improves the experience)"
	echo "The following tools improve the HaijunBot experience; install them?"
	echo "  - rg (ripgrep): fast search tool"
	echo "  - fd: fast file finder"
	echo "  - fzf: fuzzy search tool"
	echo "  - tmux: terminal multiplexer"
	echo "  - tree: directory tree viewer"
	echo ""
	read -p "Install optional tools? [Y/n]: " install_choice

	if [[ ! "$install_choice" =~ ^[Nn]$ ]]; then
		echo_info "Installing optional tools..."

		if command -v apt-get &>/dev/null; then
			sudo apt-get update -qq && sudo apt-get install -y -qq ripgrep fd-find fzf tmux tree 2>/dev/null || true
		elif command -v pacman &>/dev/null; then
			sudo pacman -Sy --noconfirm 2>/dev/null || true
			sudo pacman -S --noconfirm --needed ripgrep fd fzf tmux tree 2>/dev/null || true
		elif command -v brew &>/dev/null; then
			brew install ripgrep fd fzf tmux tree 2>/dev/null || true
		elif command -v yum &>/dev/null; then
			sudo yum install -y -q ripgrep fd-find fzf tmux tree 2>/dev/null || true
		else
			echo_warn "No package manager detected, skipping optional tool installation"
		fi

		set_state "optional_tools"
		echo_info "Optional tools installation complete"
	fi
}

# ===== Get latest version =====
get_latest_tag() {
	git ls-remote --refs --sort='-version:refname' --tags "$GITHUB_URL" 2>/dev/null | head -n 1 | awk -F/ '{print $NF}'
}

# ===== Clone or update source =====
prepare_source() {
	if check_state "source"; then
		echo_info "Source already ready, skipping"
		return 0
	fi

	local tag=$(get_latest_tag)
	local source_url="$GITHUB_URL"
	local ref="${tag:-$DEFAULT_BRANCH}"

	echo_info "Target version: $ref"

	if [ -d "$DEST_DIR/.git" ]; then
		echo_info "Existing repository detected, updating..."
		cd "$DEST_DIR"
		git fetch --depth 1 origin "$ref" 2>/dev/null || git fetch origin 2>/dev/null
		git checkout -f "$ref" 2>/dev/null || git checkout -f "origin/$ref" 2>/dev/null
		# Switch back to the main branch to avoid detached HEAD affecting auto-upgrade
		git checkout -f "$DEFAULT_BRANCH" 2>/dev/null || true
		echo_info "Source update complete"
		# HaijunBot must be reinstalled after updating the source
		if check_state "haijunbot"; then
			echo_warn "Source updated; HaijunBot will be reinstalled"
			sed -i '/^haijunbot$/d' "$STATE_FILE"
		fi
	else
		echo_info "Cloning source to $DEST_DIR..."
		rm -rf "$DEST_DIR"

		if git clone --depth 1 --branch "$ref" "$source_url" "$DEST_DIR" 2>/dev/null; then
			echo_info "Source clone succeeded"
		else
			echo_warn "GitHub clone failed, trying Gitee..."
			rm -rf "$DEST_DIR"
			git clone --depth 1 --branch "$ref" "$GITEE_URL" "$DEST_DIR" 2>/dev/null || {
				echo_error "Source clone failed; please check the network connection"
				exit 1
			}
		fi
		# Switch back to the main branch to avoid detached HEAD affecting auto-upgrade
		cd "$DEST_DIR" && git checkout -f "$DEFAULT_BRANCH" 2>/dev/null || true
	fi
}

# ===== Install HaijunBot =====
install_haijunbot() {
	if check_state "haijunbot"; then
		echo_info "HaijunBot already installed, skipping"
		return 0
	fi

	# Multi-source retry: Aliyun -> Tsinghua -> official
	local PYPI_INDEXES=(
		"https://mirrors.aliyun.com/pypi/simple/"
		"https://pypi.tuna.tsinghua.edu.cn/simple"
		"https://pypi.org/simple/"
	)

	local INSTALL_OK=0

	# Source install mode
	cd "$DEST_DIR"
	echo_info "Installing HaijunBot from source (Python 3.12)..."

	for index in "${PYPI_INDEXES[@]}"; do
		echo_info "Trying PyPI source: $index"
		if uv tool install -e . --python 3.12 --default-index "$index"; then
			INSTALL_OK=1
			break
		fi
		echo_warn "PyPI source failed, trying the next one..."
	done

	if [ "$INSTALL_OK" -ne 1 ]; then
		echo_error "HaijunBot installation failed"
		exit 1
	fi

	# Update shell environment
	uv tool update-shell 2>/dev/null || true

	set_state "haijunbot"
	echo_info "HaijunBot installation complete"
}
# ===== Verify installation =====
verify_installation() {
	export PATH="$HOME/.local/bin:$PATH"

	if command -v haijunbot &>/dev/null; then
		echo_info "✓ HaijunBot installed: $(haijunbot --version 2>&1 || echo 'unknown version')"
	else
		echo_warn "haijunbot command not found; please run: source ~/.bashrc or reopen the terminal"
	fi
}

# ===== Main flow =====
main() {
	echo ""
	echo "========================================"
	echo "  HaijunBot AI Assistant - Minimal Install"
	echo "========================================"
	echo ""

	# Check prerequisites
	command -v git &>/dev/null || {
		echo_error "git is required; please install it first"
		exit 1
	}
	command -v curl &>/dev/null || {
		echo_error "curl is required; please install it first"
		exit 1
	}

	# Run installation
	install_uv || exit 1
	set_state "uv"

	prepare_source
	set_state "source"

	install_haijunbot
	install_optional_tools
	verify_installation

	echo ""
	echo "========================================"
	echo "✓ Installation complete!"
	echo "========================================"

	echo "Install location: $DEST_DIR"

	echo ""
	echo "Quick start:"
	echo "  1. If the haijunbot command is unavailable, run: source ~/.bashrc"
	echo "  2. Start HaijunBot: haijunbot"

	echo "  3. Upgrade HaijunBot: cd $DEST_DIR && git fetch --depth 1 && git reset --hard origin/main && uv tool install -e . --python 3.12"

	echo ""
	echo "========================================"
}

main
