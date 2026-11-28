# Terminal-Bench 2.0 Evaluation Run Guide

> This document explains **how to manually run** Terminal-Bench 2.0 evaluations (HaijunBot adapter). For environment setup details, see [eval_environment_setup.md](./eval_environment_setup.md). This document focuses on running itself and includes an enhanced image solution for verifier network issues.

## 1. Prerequisites

- Environment has been set up according to `eval_environment_setup.md` (harbor venv + dataset + wheelhouse).
- Local Docker daemon is running normally.
- LLM API key is configured (in `~/.haijunbot/config.yaml` under `ds` model group, or via environment variable `OPENAI_API_KEY`).
- Local proxy environment variables `http_proxy/https_proxy=127.0.0.1:7890` will cause pip/uv installation to fail; installation commands must be prefixed with `env -u http_proxy -u https_proxy` for direct connection (script already handles this).

## 2. Quick Run (One-Click)

```bash
cd /home/skyfire/HaijunBot

# Specify harbor venv (actual path on local machine), run evaluation
EVAL_VENV_DIR=/home/skyfire/harbor-venv \
  bash scripts/run_eval.sh run \
  --n-tasks 1 --n-concurrent 1 \
  --include-task-name crack-7z-hash
```

- `run_eval.sh run` automatically:
  1. Reads platform/model/api_base/api_key from model group in `~/.haijunbot/config.yaml` (default `ds`, can specify with `-g <group>`, e.g. `-g linuxdo`);
  2. Passes through `OPENAI_API_KEY`, `OPENAI_API_BASE`, `HAIJUNBOT_MODEL`, `HAIJUNBOT_PLATFORM`;
  3. Passes through `OPENAI_EXTRA_BODY={"thinking":{"type":"disabled"}}` (disables deepseek reasoning, critical fix);
  4. Points `HAIJUNBOT_WHEELHOUSE_DIR` to offline wheelhouse for container `install()` to install hca offline.
- Other common parameters:
  - `-g <model group>` / `--group=<model group>`: Specifies model group in config.yaml (default `ds`).
  - `--n-tasks N`: Run N tasks; `--n-concurrent N`: Concurrency.
  - `--include-task-name <name>`: Run only specified task (e.g. `crack-7z-hash`).
  - `--agent-timeout-multiplier 2`: Multiply agent timeout by 2 (default 900s, may be insufficient for complex tasks).
- API key sources (choose one): Prioritizes reading from config.yaml model group; falls back to environment variable `OPENAI_API_KEY` if not configured (paired with `HAIJUNBOT_MODEL`/`HAIJUNBOT_PLATFORM`/`OPENAI_API_BASE`).

> If using fish terminal, explicitly call `bash scripts/run_eval.sh ...`.

### View All Task Names

The terminal-bench@2.0 dataset has **89 tasks total**; task names are the task names in `~/.cache/harbor/tasks/<hash>/<task_name>/task.toml`. To view:

```bash
find ~/.cache/harbor/tasks/ -name task.toml 2>/dev/null | awk -F/ '{print $(NF-1)}' | sort
```

Example tasks: `crack-7z-hash`, `gpt2-codegolf`, `password-recovery`, `path-tracing`, `qemu-alpine-ssh`, `sqlite-db-truncate`, etc.

> Use `--include-task-name <name>` to run only specified task; task name must match exactly.

### Run in Background (Optional)

```bash
cd /home/skyfire/HaijunBot
setsid env EVAL_VENV_DIR=/home/skyfire/harbor-venv \
  bash scripts/run_eval.sh run \
  --n-tasks 1 --n-concurrent 1 \
  --include-task-name crack-7z-hash \
  > /tmp/eval-run.log 2>&1 < /dev/null &
tail -f /tmp/eval-run.log
```

## 3. View Results

Harbor evaluation results are written to the trial directory for each task; the core file is `result.json`:

```bash
# Find most recently generated result.json
find ~/.cache/harbor -name result.json -newermt '-1 hour' 2>/dev/null | tail -5
```

Key fields in `result.json`:

```json
{
  "reward": 1, // 0 or 1
  "verifier": {
    "stdout": "...", // verifier output (pytest results)
    "reward": 1
  }
}
```

- `reward: 1`: Task passed.
- `reward: 0`: Task failed. Check `verifier.stdout` to determine if agent didn't complete or verifier itself failed.

## 4. Verifier Network Issues and Enhanced Image Solution (Important)

### Background

Terminal-Bench 2.0 verifier's default `test.sh` runs **inside the evaluation container**:

```bash
curl -LsSf https://astral.sh/uv/0.9.5/install.sh | sh   # download uv
uvx -p 3.13 -w pytest==8.4.1 pytest --ctrf ...           # run pytest with uvx
```

However, container access to `astral.sh` (Cloudflare) has **intermittent timeouts**, and `curl` has no retry; this causes uv/uvx to be unavailable and pytest cannot run—**even if agent completed the task, reward becomes 0**.

### Solution: Pre-build Enhanced Image + Modify test.sh

Make verifier run **completely offline**, not depending on downloading anything inside container:

1. Build enhanced image `crack-7z-hash-enh` (pre-installed python3.12 + pytest + hca).
2. Change cached task's `test.sh` to use `python3 -m pytest` (replacing curl+uvx).
3. Change `task.toml`'s `docker_image` to point to enhanced image.

> When Harbor task cache hits, it **will not overwrite** existing task directories (`tasks/client.py` has `target_dir.exists() and not overwrite` returns cached directly), so modifying `~/.cache/harbor/tasks/.../crack-7z-hash/tests/test.sh` and `task.toml` is safe.

### Enhanced Image Dockerfile

```dockerfile
# scripts/docker/crack-7z-hash-enh.Dockerfile
FROM alexgshaw/crack-7z-hash:20251031

# Pre-install system python3.12 + pip + git (reliable network during build)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

# Pre-install pytest==8.4.1 + pytest-json-ctrf==0.3.5 (pure Python packages)
COPY pytest-site/ /tmp/pytest-site/
RUN cp -r /tmp/pytest-site/* /usr/lib/python3/dist-packages/ \
    && rm -rf /tmp/pytest-site

# Pre-install hca (haijunbot-ai-assistant) + dependencies: install completely offline using offline cp312 wheelhouse
COPY wheelhouse/ /tmp/wheelhouse/
RUN python3 -m pip install --break-system-packages --no-index \
        --find-links=/tmp/wheelhouse haijunbot-ai-assistant \
    && rm -rf /tmp/wheelhouse

# PyPI release doesn't package builtin prompt resources; supplement from local source
COPY prompts/ /root/.haijunbot/prompts/

RUN python3 --version && python3 -m pytest --version && command -v hca
```

Build command:

```bash
mkdir -p /tmp/enhimg
cp -r ~/.cache/harbor/wheelhouse /tmp/enhimg/wheelhouse
cp -r /tmp/pytest-site /tmp/enhimg/pytest-site       # pytest 8.4.1 + ctrf (see below)
cp -r /home/skyfire/HaijunBot/builtin/prompts /tmp/enhimg/prompts
cp scripts/docker/crack-7z-hash-enh.Dockerfile /tmp/enhimg/Dockerfile
cd /tmp/enhimg && docker build -t crack-7z-hash-enh:latest .
```

> `pytest-site` is a pre-installed directory of pytest 8.4.1 + pytest-json-ctrf 0.3.5 (pure Python packages).
>
> Generation (on host, Python 3.12):
>
> ```bash
> uv pip install --python <py312> --target /tmp/pytest-site pytest==8.4.1 pytest-json-ctrf==0.3.5
> ```

### Modify test.sh and task.toml

Modify cached task directory (hash in path varies by actual):

```bash
TASKDIR=~/.cache/harbor/tasks/MAyhSNHCZegJvZuPyTitjJ/crack-7z-hash

# 1. Modify test.sh: use python3 -m pytest instead of curl+uvx
cat > "$TASKDIR/tests/test.sh" <<'EOF'
#!/bin/bash
# Offline verifier: use python3 + pytest pre-installed in enhanced image
if [ "$PWD" = "/" ]; then
    echo "Error: No working directory set."
    exit 1
fi
python3 -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ $? -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
EOF

# 2. Modify task.toml: docker_image points to enhanced image
sed -i 's|docker_image = "alexgshaw/crack-7z-hash:20251031"|docker_image = "crack-7z-hash-enh:latest"|' "$TASKDIR/task.toml"
```

### Verify (Offline)

```bash
docker run --rm --network=none \
  -v "$TASKDIR/tests/test_outputs.py:/tests/test_outputs.py:ro" \
  -v "$TASKDIR/tests/test.sh:/tests/test.sh:ro" \
  crack-7z-hash-enh:latest bash -c '
mkdir -p /app && echo "honeybear" > /app/solution.txt
mkdir -p /logs/verifier && cd /app
bash /tests/test.sh
echo "reward: $(cat /logs/verifier/reward.txt)"   # expect 1
'
```

## 5. Common Issues

### 1. reward=0 but agent clearly completed task

Most likely verifier network issue (see section 4). Check `result.json`'s `verifier.stdout`:

- If see `curl: (28) SSL connection timeout` / `uvx: command not found` → use enhanced image solution.
- If agent didn't complete due to timeout (`AgentTimeoutError`) → add `--agent-timeout-multiplier 2`.

### 2. Unstable network when pip installs dependencies in container

`install()` already uses offline wheelhouse (`--no-index --find-links`) for completely offline installation with overall retry loop. If still fails, confirm `HAIJUNBOT_WHEELHOUSE_DIR` points to correct wheelhouse.

### 3. deepseek response timeout / 0 tokens

Confirm `OPENAI_EXTRA_BODY={"thinking":{"type":"disabled"}}` is passed through (`run_eval.sh` adds by default). This is critical fix to disable deepseek reasoning mode.

### 4. Need enhanced images for other tasks too?

Each task has different base images (`python:3.13-slim`, `alexgshaw/gpt2-codegolf`, etc.). Need to build corresponding enhanced image per task and modify its cached `test.sh` and `task.toml`. The crack-7z-hash enhanced image solution can be reused as template.

## Related Files

- `scripts/run_eval.sh`: Setup + run script (`setup` / `run` / `help`).
- `src/haijunbot/haijunbot_eval/harbor_agent.py`: HaijunBot Harbor adapter.
- `docs/technical/eval_environment_setup.md`: Environment setup document.