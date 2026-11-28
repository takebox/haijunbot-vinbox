# Terminal-Bench 2.0 Evaluation Environment Setup

> This document explains how to set up the Terminal-Bench 2.0 evaluation environment locally, run evaluations using HaijunBot's Harbor adapter (`src/haijunbot/haijunbot_eval/harbor_agent.py`), and produce `reward.txt` with values 0/1 as a quantitative metric for self-evolution.

## Background

HaijunBot is encapsulated as Harbor's `BaseInstalledAgent` (`HaijunBotInstalledAgent`) via the `haijunbot_eval` package, enabling HaijunBot to solve real terminal tasks in Terminal-Bench 2.0's isolated Docker task environments.

Evaluation process:

1. Harbor installs `haijunbot-ai-assistant` in the task container to provide the `hca` CLI (prioritizing a pre-built offline wheelhouse from the local machine with `--no-index --find-links` for fully offline installation; falls back to online multi-mirror installation if no wheelhouse is provided)
2. `run()` writes the task instruction to a container file and calls `hca -n --task-file <path>` for execution
3. LLM API keys are passed through from Harbor to the `hca` process inside the container via `--ae`
4. Each task produces `reward.txt` with value 0/1, allowing comparison of pass rates before and after evolution

## Environment Requirements

| Dependency | Version Requirement | Description                                        |
| ---------- | ------------------- | -------------------------------------------------- |
| Docker     | Any modern version  | Terminal-Bench isolated environment, Docker daemon must be running |
| uv         | 0.12+               | Creates isolated evaluation virtual environment     |
| Python     | 3.12+               | Harbor requires `>=3.12` (local machine uses 3.14) |
| Disk       | ≥10GB               | Evaluation container images + dataset cache       |
| LLM API key | Any                 | OpenAI/Juglow/DeepSeek etc., used by `hca` inside container |

> **Note**: If the local machine has proxy environment variables (`http_proxy`/`https_proxy`) configured, Harbor installation requires a direct connection (using `env -u http_proxy -u https_proxy ...`), otherwise installation will fail. The evaluation run script already handles this.

## Quick Start

It is recommended to use the project's built-in script `scripts/run_eval.sh`, which completes environment setup with a single command:

```bash
# 1. Set up environment (create venv + install harbor + download dataset)
./scripts/run_eval.sh setup

# 2. Run evaluation (set LLM API key first)
export OPENAI_API_KEY=sk-xxx
./scripts/run_eval.sh run --n-concurrent 4 --n-tasks 10
```

The script will:

- Use `uv` to create an isolated virtual environment at `~/.haijunbot-eval-venv` (does not pollute system Python)
- Install `harbor` and download `terminal-bench@2.0` dataset to `~/.cache/harbor/tasks`
- Build an offline wheelhouse with Python 3.12 at `~/.cache/harbor/wheelhouse` (pre-downloads `haijunbot-ai-assistant` and all dependencies from local machine for offline installation in containers)
- Run `harbor run` and automatically pass through configured API key environment variables

## Manual Setup (Equivalent to Script Steps)

```bash
# 1. Create isolated virtual environment and install harbor
uv venv ~/.haijunbot-eval-venv --python 3.14
env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
    uv pip install --python ~/.haijunbot-eval-venv/bin/python harbor

# 2. Download terminal-bench@2.0 dataset (89 tasks)
~/.haijunbot-eval-venv/bin/harbor download "terminal-bench@2.0" --cache

# 3. Run evaluation
export OPENAI_API_KEY=sk-xxx
PYTHONPATH=src ~/.haijunbot-eval-venv/bin/harbor run \
    --dataset terminal-bench@2.0 \
    -a haijunbot.haijunbot_eval.harbor_agent:HaijunBotInstalledAgent \
    --ae OPENAI_API_KEY=$OPENAI_API_KEY \
    --n-concurrent 4
```

## Key Parameters

| Parameter                                                | Description                                  |
| -------------------------------------------------------- | -------------------------------------------- |
| `-a haijunbot.haijunbot_eval.harbor_agent:HaijunBotInstalledAgent` | Specifies HaijunBot adapter class (custom import path) |
| `--ae KEY=VALUE`                                         | Passes environment variables to `hca` inside container (API keys etc.) |
| `--dataset terminal-bench@2.0`                           | Evaluation dataset                          |
| `-n/--n-concurrent`                                      | Number of concurrent evaluations (default 4) |
| `--n-tasks`                                              | Maximum number of tasks to run (for small-scale validation) |
| `--print-config`                                         | Only print parsed config without running (for self-check) |

## Verifying Environment Availability

### 1. Verify adapter can be loaded by Harbor

```bash
cd /path/to/HaijunBot
PYTHONPATH=src ~/.haijunbot-eval-venv/bin/python -c "
from harbor.utils.import_path import import_class
from harbor.agents.installed.base import BaseInstalledAgent
cls = import_class('haijunbot.haijunbot_eval.harbor_agent:HaijunBotInstalledAgent')
assert cls.name() == 'haijunbot'
assert issubclass(cls, BaseInstalledAgent)
print('Adapter loading OK')
"
```

### 2. Verify config parsing is correct (no actual run)

```bash
PYTHONPATH=src ~/.haijunbot-eval-venv/bin/harbor run \
    --dataset terminal-bench@2.0 \
    -a haijunbot.haijunbot_eval.harbor_agent:HaijunBotInstalledAgent \
    --ae OPENAI_API_KEY=test --print-config
```

Should output JSON containing `"name": "terminal-bench", "version": "2.0"` and agent path.

### 3. Verify dataset can be downloaded

```bash
~/.haijunbot-eval-venv/bin/harbor download "terminal-bench@2.0" --cache
# Output: "Successfully downloaded 89 task(s)"
```

## Outputs and Results

- Evaluation results are written to `jobs/` directory by default (can be changed via `--jobs-dir` parameter of `harbor run`)
- Each task produces `reward.txt` with value 0/1
- Pass rates of the same batch of tasks before and after evolution can be compared as quantitative metric for self-evolution

## Important Notes

1. **Installation source**: Adapter `install()` installs `haijunbot-ai-assistant` inside the container. By default it prioritizes **locally pre-built offline wheelhouse** (`HAIJUNBOT_WHEELHOUSE_DIR` specified, defaults to `~/.cache/harbor/wheelhouse`) for fully offline installation, avoiding network instability issues when container directly downloads large packages (like playwright) from PyPI. If no wheelhouse is provided, it falls back to online multi-mirror installation (Tsinghua → Alibaba Cloud → direct PyPI). The wheelhouse is automatically built by `run_eval.sh setup` using Python 3.12 (matching Python version in Ubuntu 24.04 container to ensure wheel platform/ABI compatibility), containing `haijunbot-ai-assistant` and all its dependencies. Defaults to **latest PyPI version** (`JCA_VERSION=latest`); can specify specific version with `JCA_VERSION=<version>`. If wheelhouse already built, it skips by default (marker records actual version); after releasing new version, need `JCA_FORCE_REBUILD=1` to force rebuild to use new version. To test with latest local source code, need to publish to PyPI first, or modify `harbor_agent.py`'s `install()` to install from local wheel/git.

2. **API key required**: `hca` inside container requires a real LLM API key to solve tasks, passed via `--ae`. Evaluation cannot proceed without key.

3. **Network**: When using offline wheelhouse, container does **not** need access to PyPI to install `haijunbot-ai-assistant`. However, `hca` still needs to access model APIs (via `OPENAI_API_BASE` etc. passed through `--ae`). If container cannot directly connect to model APIs, need to pass proxy variables (`HTTP_PROXY`/`HTTPS_PROXY`) via `--ae`.

4. **Lazy dependencies**: The `haijunbot_eval` package itself does not import harbor; HaijunBot main project can safely import it. Only the `harbor_agent` module requires harbor environment.

## Related Files

- `src/haijunbot/haijunbot_eval/harbor_agent.py` — HaijunBot Harbor adapter
- `src/haijunbot/haijunbot_eval/__init__.py` — Lightweight package entry (no harbor dependency)
- `tests/haijunbot_eval/test_harbor_agent.py` — Adapter unit tests
- `scripts/run_eval.sh` — Evaluation environment setup and run script