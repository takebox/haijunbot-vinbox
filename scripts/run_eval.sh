#!/bin/bash
# shellcheck disable=SC2218  # false positive: helper functions (check_prereq/echo_*) are all defined before setup/run_eval
# =============================================================================
# HaijunBot Terminal-Bench 2.0 evaluation environment setup and run script
#
# Features:
#   1. Use uv to create an isolated Harbor evaluation virtual environment (avoid polluting the system Python)
#   2. Install harbor (the Terminal-Bench 2.0 evaluation framework)
#   3. Download the terminal-bench@2.0 dataset to the local cache
#   4. Run harbor run, evaluating HaijunBot with the haijunbot_eval adapter layer
#
# Usage:
#   # Set up the environment only (create venv + install harbor + download dataset)
#   ./scripts/run_eval.sh setup
#
#   # Run the evaluation. API key source (choose one):
#   #   - Prefer reading from the model group in ~/.haijunbot/config.yaml (default ds, can specify with -g <group-name>)
#   #   - Or export OPENAI_API_KEY (together with HAIJUNBOT_MODEL/HAIJUNBOT_PLATFORM/OPENAI_API_BASE)
#   OPENAI_API_KEY=sk-xxx ./scripts/run_eval.sh run [--n-concurrent N] [--n-tasks N]
#   ./scripts/run_eval.sh run -g linuxdo --n-concurrent 2
#
#   # View harbor run help
#   ./scripts/run_eval.sh help
#
# Notes:
#   - A full evaluation requires a real LLM API key (passed through --ae to the hca process inside the container)
#   - Inside the evaluation container, pip install haijunbot-ai-assistant (PyPI release) is run,
#     if you need to evaluate the latest local source, publish to PyPI first or adjust the adapter layer's install()
# =============================================================================
set -euo pipefail

# ===== Configuration =====
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${EVAL_VENV_DIR:-$HOME/.haijunbot-eval-venv}"
HARBOR_VERSION="${HARBOR_VERSION:-harbor}"
# Version of haijunbot-ai-assistant installed in the evaluation container; latest=latest PyPI version, can specify e.g. 6.0.10
JCA_VERSION="${JCA_VERSION:-latest}"
# When set to 1, force rebuild the offline wheelhouse (otherwise a cache hit skips it; after a new release set to 1 to update)
JCA_FORCE_REBUILD="${JCA_FORCE_REBUILD:-0}"

# Local proxy environment variables can make pip/uv install fail; install with a direct connection
PROXY_UNSET="env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY"

# ===== Color output =====
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
echo_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
echo_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
echo_err() { echo -e "${RED}[ERROR]${NC} $1"; }

# ===== Prerequisite check =====
check_prereq() {
	if ! command -v uv >/dev/null 2>&1; then
		echo_err "uv not found; please install first: curl -LsSf https://astral.sh/uv/install.sh | sh"
		exit 1
	fi
	if ! command -v docker >/dev/null 2>&1; then
		echo_err "docker not found; Terminal-Bench 2.0 evaluation requires a Docker isolated environment"
		exit 1
	fi
	if ! docker info >/dev/null 2>&1; then
		echo_err "Docker daemon is not running; please start docker first"
		exit 1
	fi
}

# ===== Build offline wheelhouse (predownload dependencies locally for offline install in the container) =====
# Downloading large packages (playwright 38MB etc.) directly from PyPI inside the container is unstable and prone to mid-download timeouts/corruption.
# On the local machine, predownload all dependencies to the wheelhouse using the same Python 3.12 as the container; during evaluation
# upload to the container and install fully offline with --no-index --find-links, completely bypassing the problem.
build_wheelhouse() {
	local wh_dir="${HAIJUNBOT_WHEELHOUSE_DIR:-$HOME/.cache/harbor/wheelhouse}"
	# The marker records the actual built version (does not rely on the versioned filename, so a new release is still judged correctly)
	local wh_marker="$wh_dir/.built"
	if [ -f "$wh_marker" ] && [ "$JCA_FORCE_REBUILD" != "1" ]; then
		echo_info "wheelhouse already exists, skipping build: $wh_dir ($(cat "$wh_marker"))"
		return 0
	fi
	echo_info "Building offline wheelhouse: $wh_dir (JCA_VERSION=$JCA_VERSION)"
	local wh_venv="$HOME/.cache/harbor/wh-venv"
	if [ ! -x "$wh_venv/bin/python" ]; then
		uv venv "$wh_venv" --python 3.12
		$PROXY_UNSET uv pip install --python "$wh_venv/bin/python" pip
	fi
	mkdir -p "$wh_dir"
	# Download dependencies with Python 3.12 to ensure wheel platform/ABI compatibility with the container (Ubuntu 24.04 + 3.12)
	# Defaults to the latest PyPI version (JCA_VERSION=latest); a specific version can also be specified
	local jca_spec="haijunbot-ai-assistant"
	[ "$JCA_VERSION" != "latest" ] && jca_spec="haijunbot-ai-assistant==$JCA_VERSION"
	$PROXY_UNSET "$wh_venv/bin/python" -m pip download \
		--no-cache-dir --dest "$wh_dir" "$jca_spec"
	# jieba only provides an sdist; offline build requires setuptools/wheel
	$PROXY_UNSET "$wh_venv/bin/python" -m pip download \
		--no-cache-dir --dest "$wh_dir" setuptools wheel
	# Parse the actual version from the downloaded wheel filename and write it to the marker
	local built_ver wheel_files=("$wh_dir"/haijunbot_ai_assistant-*.whl)
	if [ -e "${wheel_files[0]}" ]; then
		built_ver="$(basename "${wheel_files[0]}" .whl | sed -E 's/haijunbot_ai_assistant-([0-9][^-]*).*/\1/')"
	else
		built_ver="$JCA_VERSION"
	fi
	echo "$built_ver" >"$wh_marker"
	echo_info "wheelhouse build complete: $wh_dir (haijunbot-ai-assistant $built_ver)"
}

# ===== 1. Create venv and install harbor =====
setup() {
	check_prereq
	if [ ! -x "$VENV_DIR/bin/harbor" ]; then
		echo_info "Creating evaluation virtual environment: $VENV_DIR"
		uv venv "$VENV_DIR" --python 3.14
		echo_info "Installing harbor ($HARBOR_VERSION)..."
		$PROXY_UNSET uv pip install --python "$VENV_DIR/bin/python" "$HARBOR_VERSION"
	else
		echo_info "Evaluation virtual environment already exists, skipping creation: $VENV_DIR"
	fi
	echo_info "harbor version: $("$VENV_DIR/bin/harbor" --version)"

	echo_info "Downloading the terminal-bench@2.0 dataset to the local cache..."
	"$VENV_DIR/bin/harbor" download "terminal-bench@2.0" --cache
	echo_info "Dataset download complete (cached at ~/.cache/harbor/tasks)"

	# Build offline wheelhouse (predownload dependencies locally for offline install in the container)
	build_wheelhouse
}

# ===== Read the specified model group info from ~/.haijunbot/config.yaml =====
# Output format: platform|model|api_base|api_key
read_model_group() {
	local group="$1"
	local cfg="$HOME/.haijunbot/config.yaml"
	if [ ! -f "$cfg" ]; then
		echo_err "Config file not found: $cfg"
		return 1
	fi
	# Use the harbor-venv python to parse YAML (system python3 may lack pyyaml)
	if [ ! -x "$VENV_DIR/bin/python" ]; then
		echo_err "Evaluation virtual environment not ready; please run setup first"
		return 1
	fi
	"$VENV_DIR/bin/python" -c "
import sys, yaml
group = '$group'
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
groups = cfg.get('llm_groups', {})
if group not in groups:
    sys.exit(2)
g = groups[group]
llm_name = g.get('normal_llm') or g.get('cheap_llm') or g.get('smart_llm')
llms = cfg.get('llms', {})
m = llms.get(llm_name, {})
lc = m.get('llm_config', {}) or {}
platform = m.get('platform', '')
model = m.get('model', '')
api_base = lc.get('openai_api_base', '') or lc.get('OPENAI_API_BASE', '')
api_key = lc.get('openai_api_key', '') or lc.get('OPENAI_API_KEY', '')
print(f'{platform}|{model}|{api_base}|{api_key}')
" 2>/dev/null
}

# ===== 2. Run evaluation =====
run_eval() {
	setup
	# Prefer reading model info from the ds model group in ~/.haijunbot/config.yaml
	MODEL_GROUP="${EVAL_MODEL_GROUP:-ds}"
	INFO="$(read_model_group "$MODEL_GROUP")" || {
		rc=$?
		if [ "$rc" -eq 2 ]; then
			echo_err "Model group does not exist in config.yaml: $MODEL_GROUP"
		else
			echo_err "Failed to read model group $MODEL_GROUP from config.yaml"
		fi
		exit 1
	}
	IFS='|' read -r PLATFORM MODEL API_BASE API_KEY <<<"$INFO"
	# If the config.yaml model group does not provide an API key, fall back to the OPENAI_API_KEY environment variable
	# (model name/platform/base fall back accordingly to HAIJUNBOT_MODEL / HAIJUNBOT_PLATFORM / OPENAI_API_BASE)
	if [ -z "$API_KEY" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
		API_KEY="$OPENAI_API_KEY"
		[ -z "$PLATFORM" ] && PLATFORM="${HAIJUNBOT_PLATFORM:-openai}"
		[ -z "$MODEL" ] && MODEL="${HAIJUNBOT_MODEL:-}"
		[ -z "$API_BASE" ] && API_BASE="${OPENAI_API_BASE:-}"
	fi
	if [ -z "$API_KEY" ]; then
		echo_err "API key not configured: configure the $MODEL_GROUP model group in ~/.haijunbot/config.yaml, or export OPENAI_API_KEY"
		exit 1
	fi
	echo_info "Using model group $MODEL_GROUP: platform=$PLATFORM model=$MODEL base=$API_BASE"

	# Environment variables passed through to hca inside the container
	AE_ARGS=(--ae "OPENAI_API_KEY=$API_KEY")
	[ -n "$API_BASE" ] && AE_ARGS+=(--ae "OPENAI_API_BASE=$API_BASE")
	[ -n "$MODEL" ] && AE_ARGS+=(--ae "HAIJUNBOT_MODEL=$MODEL")
	[ -n "$PLATFORM" ] && AE_ARGS+=(--ae "HAIJUNBOT_PLATFORM=$PLATFORM")
	# Reasoning models such as deepseek-flash enter long thinking reasoning by default, causing request timeouts and
	# empty content. The local config.yaml is configured with thinking disabled, but hca inside the container
	# does not automatically include it when building the model config from environment variables; OPENAI_EXTRA_BODY must be explicitly passed through to disable it.
	if [ -z "${OPENAI_EXTRA_BODY:-}" ]; then
		AE_ARGS+=(--ae 'OPENAI_EXTRA_BODY={"thinking":{"type":"disabled"}}')
	fi
	# Additionally pass through other API key / proxy variables the user has set
	for var in OPENAI_API_BASE OPENAI_BASE_URL \
		JUGLOW_API_KEY JUGLOW_BASE_URL \
		API_BASE_URL HTTP_PROXY HTTPS_PROXY NO_PROXY; do
		if [ -n "${!var:-}" ]; then
			AE_ARGS+=(--ae "$var=${!var}")
		fi
	done
	echo_info "Starting Terminal-Bench 2.0 evaluation (haijunbot adapter layer)..."
	# shellcheck disable=SC2068
	# HAIJUNBOT_WHEELHOUSE_DIR lets install() read the local offline wheelhouse (Harbor main process environment)
	HAIJUNBOT_WHEELHOUSE_DIR="${HAIJUNBOT_WHEELHOUSE_DIR:-$HOME/.cache/harbor/wheelhouse}" \
		PYTHONPATH="$PROJECT_DIR/src" "$VENV_DIR/bin/harbor" run \
		--dataset terminal-bench@2.0 \
		-a haijunbot.haijunbot_eval.harbor_agent:HaijunBotInstalledAgent \
		"${AE_ARGS[@]}" \
		"$@"
}

# ===== 3. Help =====
show_help() {
	"$VENV_DIR/bin/harbor" run --help 2>/dev/null || true
}

# ===== Entry point =====
case "${1:-}" in
setup) setup ;;
run)
	shift
	# Parse -g/--group to specify the model group (priority: -g argument > EVAL_MODEL_GROUP environment variable > default ds)
	# Remaining arguments are passed to harbor run as-is
	local_model_group=""
	remaining=()
	while [ $# -gt 0 ]; do
		case "$1" in
		-g | --group)
			local_model_group="$2"
			shift 2
			;;
		-g=* | --group=*)
			local_model_group="${1#*=}"
			shift
			;;
		*)
			remaining+=("$1")
			shift
			;;
		esac
	done
	if [ -n "$local_model_group" ]; then
		export EVAL_MODEL_GROUP="$local_model_group"
	fi
	run_eval "${remaining[@]}"
	;;
help)
	check_prereq
	show_help
	;;
*)
	echo "Usage: $0 {setup|run|help}"
	echo "  setup   Set up the evaluation environment (create venv + install harbor + download dataset)"
	echo "  run     Run the evaluation (-g <model-group> specifies the model group, default ds; API key read from config.yaml or export OPENAI_API_KEY)"
	echo "  help    View harbor run arguments"
	exit 1
	;;
esac
