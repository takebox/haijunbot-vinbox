# HaijunBot-Vinbox

**HaijunBot runs EXCLUSIVELY inside the Vinbox machine.**

No external API keys, no standalone operation, no cloud backends. HaijunBot leverages Vinbox's model registry (OpenCode free models, local .gguf files, subscription providers enabled by user), CDP 9222 browser terminal, and pwsh terminal with working dir `app/program-file`.

## ⚠️ VINBOX-ONLY SCOPE

This repository is a vinbox-integrated version of HaijunBot. It does NOT operate standalone and does NOT support:

- Running outside of a Vinbox container
- External model providers (OpenAI, Anthropic, etc.) - all model access goes through Vinbox's bridge (port 4097)
- Independent browser/terminal instances - uses Vinbox's CDP 9222 and pwsh
- Hardcoded LLM configuration - all models/resolve from Vinbox's MODELS tab

## 🏓 How HaijunBot Works Inside VinBox

- **Model Lane**: Uses Vinbox's OpenAI-compatible bridge at `http://127.0.0.1:4097/v1`, which always answers with the model selected in the Vinbox MODELS tab (free OpenCode models, local .gguf files, or subscription providers the user enabled)
- **Browser**: Attaches to Vinbox's single Chromium on CDP 9222
- **Terminal**: Uses Vinbox's pwsh shell, working directory `app/program-file`
- **State**: Persisted in `vinbox/data/` (bind-mounted, survives a rebuild)

## 📁 Key Files Updated for VinBox Integration

| File | Purpose |
|------|---------|
| `src/haijunbot/haijunbot_smart_shell/main.py` | Executes commands via `vinbox_runtime` (pwsh, Vinbox working dir, process_env) |
| `src/haijunbot/haijunbot_utils/vinbox_runtime.py` | Runtime utilities for Vinbox integration |
| `app/llm/openai_bridge.py` | OpenAI-compatible bridge that uses `model_registry.current_selection()` - never chooses a model itself |
| `docker-compose.yml` | HaijunBot service running inside Vinbox container with proper env vars |
| `entrypoint.sh` | Starts HaijunBot service inside Vinbox on port 8000 with proper env vars |

## 🐳 Docker Integration

The HaijunBot service is added to the master `docker-compose.yml` and `entrypoint.sh` as a service running INSIDE the Vinbox container:

```yaml
haijunbot:
  build:
    context: ./haijunbot
    dockerfile: HaijunBot/Dockerfile
  image: vinbox-vinbox:latest-haijunbot
  container_name: haijunbot-core
  restart: unless-stopped
  environment:
    VINBOX_HOME: /app/vinbox
    VINBOX_LLM_BASE_URL: http://127.0.0.1:4097/v1
    VINBOX_CDP_URL: http://127.0.0.1:9222
    VINBOX_PROGRAM_FILE: /app/vinbox/app/program-file
    VINBOX_SHELL: pwsh
  ports:
    - "8000:8000"  # HaijunBot gateway
    - "5173:5173"   # HaijunBot frontend
    - "7340:7340"   # HaijunBot panel
```

## 🔒 Security

- No API keys or tokens are hardcoded in the code
- All model access goes through Vinbox's model registry
- No upstream agent code is used - this is a standalone HaijunBot deployment
- VINBOX ID and tokens are environment-configured, not embedded in code

## 📦 Repo Information

- **Original repo**: GitHub was `takebox/HaijunBot`
- **New vinbox-specific repo**: `github.com/takebox/haijunbot-vinbox`
- **Purpose**: HaijunBot service that runs exclusively within Vinbox environment
- **Model LLM**: Handled through Vinbox's model registry (OpenCode free models, local .gguf, subscription providers enabled by user)
- **No external provider stacks**

## 🚀 Quick Start (Inside VinBox)

HaijunBot is already included when you run `docker compose up -d --build` in the Vinbox directory. The HaijunBot service will start on port 8000 inside the Vinbox container, using:

- Model lane: `http://127.0.0.1:4097/v1`
- CDP terminal: `http://127.0.0.1:9222`
- pwsh shell: working dir `app/program-file`

No additional setup required - HaijunBot leverages all of Vinbox's existing infrastructure.