# Quick Start: From Zero Installation to First Run

## When to Use

You are new to HaijunBot and want to install it on a clean machine and successfully run your first conversation. This article is an **end-to-end tutorial**: from installation, configuration, and verification to completing your first task with the General Agent, giving you commands you can copy and run throughout.

If you only want a quick reference for installation commands, see [Quick Start](../../haijunbot_book/2.Quick_Start.md) first; this article builds on it by filling in the "how to confirm it really works after installing" part.

## Prerequisites

- **Operating System**: Linux (primary support), Windows 10/11 (WSL or native).
- **Python**: 3.12 (the one-click script automatically installs `uv` and sets up Python).
- **Network**: Ability to access GitHub (or the Gitee mirror) and the API of the chosen model platform.
- **Model Credentials**: An API Base URL and API Key for an OpenAI-compatible or Haijun platform.

## Steps

### Step 1: Install

#### Option A: One-click install script (recommended)

```bash
# GitHub (recommended)
bash -c "$(curl -fsSL https://raw.githubusercontent.com/takebox/HaijunBot/main/scripts/quick-install.sh)"

# Or use the Gitee mirror (faster access domestically)
bash -c "$(curl -fsSL https://gitee.com/takebox/HaijunBot/raw/main/scripts/quick-install.sh)"
```

The script automatically: fetches the latest tag source code (shallow clone), installs `uv`, installs HaijunBot with `uv tool install -e . --python 3.12`, and optionally installs enhancement tools such as `rg`, `fd`, `fzf`, `tmux`, and `tree`.

#### Option B: Manual installation from source

```bash
# 1. Clone the source of the latest release version (replace <latest-tag> with the target tag)
git clone --depth 1 --branch <latest-tag> https://github.com/takebox/HaijunBot.git
cd HaijunBot
# 2. Add the repository's built-in dependency directory to PATH (the current repo has x86_64_linux built in)
export PATH="$(pwd)/src/haijunbot/haijunbot_data/deps/x86_64_linux:$PATH"
# 3. Use uv to install the project and additional tools
uv tool install -e . --python 3.12
uv tool install playwright
uv tool install ddgr
```

#### Option C: Docker (no local environment needed)

```bash
# Pull the latest image (public, no login required)
docker pull ghcr.io/takebox/haijunbot:latest

# Run as the current user (recommended, avoids file permission issues)
docker run -it --rm \
  --user "$(id -u):$(id -g)" \
  -v $(pwd):/workspace \
  -v $HOME/.haijunbot:/home/haijunbot/.haijunbot \
  -v $HOME/.gitconfig:/home/haijunbot/.gitconfig:ro \
  -w /workspace \
  ghcr.io/takebox/haijunbot:latest
```

### Step 2: Verify the installation

```bash
# View the version and available commands
hjb --help

# View platform and model info (the first run creates the default config)
hpm info
```

If the command outputs version/help info normally, the installation succeeded.

### Step 3: Configure the model

#### Recommended: Interactive configuration wizard

```bash
hqc
```

The wizard guides you step by step: choose the AI platform (OpenAI / Haijun) → enter the API Base URL and API Key → automatically fetch available models and select one → configure model groups (Normal / Smart / Cheap) → test the connection → save to `~/.haijunbot/config.yaml`.

#### Optional: Manual configuration

When running any `haijunbot` command for the first time (such as `hjb`), if `~/.haijunbot/config.yaml` does not exist, the system attempts to start the interactive wizard. After you press `Ctrl+C` to exit the wizard, a default config file is generated, and you then fill in the credentials manually.

In CI / test environments you can skip the wizard:

```bash
export HAIJUNBOT_SKIP_INTERACTIVE_CONFIG=1
```

### Step 4: First conversation

```bash
# Interactive General Agent
hjb
```

After entering, type the task directly, for example:

```text
Introduce yourself in one sentence, and list the first 5 tools you can call.
```

Press Enter to send, and observe the Agent's thinking and tool-calling process. For multiline input, use `Ctrl + J` to submit (Enter inserts a newline).

### Step 5: Let CodeAgent modify code once

```bash
# Enter one of your Git repositories
cd /path/to/your/repo

# Interactive code Agent
hca
```

Enter a clear, small task, for example:

```text
Add a one-sentence introduction after the project name at the top of README.md.
```

CodeAgent will locate the file, modify it, show a diff preview, perform static checks / build verification according to configuration, and finally generate a commit.

## Prompts and Feedback You Will See

- When `hjb` / `hca` start, they print resource statistics such as the currently loaded model groups, tools, and rule counts.
- If confirmation is enabled, before tool execution a "summary of tools and arguments to be executed" pops up waiting for your confirmation.
- After CodeAgent modifies code, it shows an enhanced diff preview and a per-file patch summary.
- In multiline input mode, a `Ctrl + J` submit hint appears above the input box.

## Notes

- The one-click script prefers the latest GitHub tag and falls back to Gitee or the default branch on failure.
- After installing with `uv tool install -e .`, modifications to the source take effect immediately, which is suitable for developers.
- On first use, keep `~/.haijunbot/config.yaml` safe; it contains the API Key, so do not commit it to a version control repository.
- If the command reports that a tool or rule cannot be found, see Q5 and Q6 in [FAQ](../../haijunbot_book/8.FAQ.md).

## Next Steps

- To systematically learn how to use a single Agent: see [Single Agent in Practice: General Agent and CodeAgent](Hands-on_with_single_Agent_General_Agent_and_CodeAgent.md).
- To drive multiple Agents at once: see [Multi-Agent Orchestration: Driving Pipelines with pipeline_runner](Multi-Agent_Orchestration_Driving_Pipelines_with_pipeline_runner.md).
- To use it through a browser: see [Starting the Web Gateway Service](../04_web-ui-and-gateway/Starting_the_Web_Gateway_Service.md).
