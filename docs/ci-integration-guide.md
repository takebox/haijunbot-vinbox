# HaijunBot CI Integration Guide

This document introduces how to integrate HaijunBot into CI/CD (GitHub Actions / GitLab CI) to achieve **automatic PR code review, automatic issue triage, and automatic CI test reporting**.

HaijunBot reuses **headless non-interactive mode** (`hjb -n`) + the **`--task-file` state-file mechanism** to accomplish CI integration, with no additional services required.

---

## 1. Principles

The HaijunBot CodeAgent CLI (`hjb`) supports two CI-friendly usages:

### 1.1 Pass the task directly (simple scenarios)

```bash
hjb -n --task "perform a code review on the src/ directory"
```

- `-n` / `--non-interactive`: non-interactive mode; exits automatically after the task completes
- Output is written to stdout

### 1.2 Pass JSON via `--task-file` (recommended, supports a status file)

```bash
cat > task.json <<'EOF'
{
  "task_desc": "Please review the code changes in this commit",
  "background": "This is an automatic CI review",
  "status_file": "/tmp/status.json"
}
EOF

hjb -n --task-file task.json
```

After the task completes, the following are generated:

| File                                             | Content                                              |
| ------------------------------------------------ | ---------------------------------------------------- |
| `status_file` (e.g. `/tmp/status.json`)          | `{"status": "completed"/"failed", "exit_code": 0/1}` |
| `status_file.output` (e.g. `/tmp/status.output`) | The Agent's structured output                        |
| `status_file.error` (e.g. `/tmp/status.error`)   | Error information on failure                         |

CI only needs to parse these three files to obtain the structured result, with **no need to add an `--output-format json` parameter**.

---

## 2. GitHub Actions Templates

The repository provides 3 out-of-the-box templates under `scripts/ci/`:

| Template                  | Trigger   | Purpose                                                       |
| ------------------------- | --------- | ------------------------------------------------------------- |
| `haijunbot-pr-review.yml`    | PR        | Performs code review on the `git diff` and comments on the PR |
| `haijunbot-issue-triage.yml` | issue     | Automatically triages the issue and comments                  |
| `haijunbot-ci-test.yml`      | push / PR | Runs tests and reports the results                            |

### 2.1 Usage Steps

1. Copy the corresponding template into your repository's `.github/workflows/` (e.g. `haijunbot-pr-review.yml`).
2. Configure in the repository's **Settings → Secrets and variables → Actions** (HaijunBot reads the API Key from the standard LLM environment variables):
   - `OPENAI_API_KEY` (OpenAI platform): the API Key for calling the LLM
   - `JUGLOW_API_KEY` (Juglow platform): the API Key for calling the LLM
   - `OPENAI_API_BASE` (optional): custom OpenAI-compatible endpoint
   - `HAIJUNBOT_MODEL` (optional): specify the model, default `gpt-5`
   - `HAIJUNBOT_PLATFORM` (optional): specify the platform, default `openai`
3. Adjust `TEST_COMMAND` (in `haijunbot-ci-test.yml`, default `pytest -v`) or `HAIJUNBOT_REVIEW_RULES` (in `haijunbot-pr-review.yml`, additional review rules) in the template as needed.

> **Installation and Configuration Notes**: The template uses `pip install haijunbot-ai-assistant` to install HaijunBot from PyPI (suitable for any user repository). The first run of `hjb` automatically generates the default `~/.haijunbot/config.yaml` (non-interactive), and the API Key is injected via the standard environment variables mentioned above, **with no need to pre-provision config.yaml**.

### 2.1.1 Non-interactive Quick Configuration (CI-friendly)

HaijunBot provides two non-interactive configuration methods; either one is sufficient:

#### Method A: Environment variables (runtime override, most lightweight)

```bash
export OPENAI_API_KEY=sk-xxx        # API Key
export HAIJUNBOT_MODEL=gpt-4o          # Override the default model gpt-5
export HAIJUNBOT_PLATFORM=openai       # Override the default platform openai
export HAIJUNBOT_SKIP_INTERACTIVE_CONFIG=1  # Skip the first-time interactive configuration wizard
hjb -n --task-file task.json
```

Environment variables have the highest priority (> config.yaml > default values) and are suitable for temporarily specifying a model/platform without writing a file.

#### Method B: `hqc` non-interactive mode (persists to config.yaml)

```bash
hqc --platform openai --base-url https://api.openai.com/v1 \
    --api-key sk-xxx --model gpt-4o --group default --skip-test
```

Writes the model into `~/.haijunbot/config.yaml` under `llms` + `llm_groups` in one go and sets it as the default group, so subsequent `hjb` runs work directly. Suitable for configuring first and then running in CI, or persisting locally. `--skip-test` skips the connectivity test (to avoid CI network dependencies).

> Interactive mode: run `hqc` directly (without arguments) and enter inputs as prompted; the logic remains unchanged.

### 2.2 Automatic PR Review (haijunbot-pr-review.yml)

- Trigger: `pull_request` (opened / synchronize / reopened), skips draft PRs
- Flow: checkout (`fetch-depth: 0` to fetch the full history) → install HaijunBot → compute the PR diff → build the task-file → `hjb -n --task-file` review → parse `.output` → comment on the PR using `github-script`
- Permissions: requires `pull-requests: write`

### 2.3 Automatic Issue Triage (haijunbot-issue-triage.yml)

- Trigger: `issues` (opened)
- Flow: write the issue body to a temporary file → build the task-file → `hjb -n` triage → comment the triage conclusion
- Permissions: requires `issues: write`

### 2.4 CI Test Reporting (haijunbot-ci-test.yml)

- Trigger: push (main) / PR
- Flow: install dependencies → build the task-file → `hjb -n` runs tests and analyzes the root cause of failures → comment the test report on the PR
- Compared with plain pytest: HaijunBot can **automatically analyze failed cases, locate the root cause, and provide fix suggestions**

---

## 3. GitLab CI Example

GitLab CI can likewise use `hjb -n --task-file`; an example `.gitlab-ci.yml`:

```yaml
haijunbot-review:
  stage: test
  image: python:3.12
  variables:
    OPENAI_API_KEY: $OPENAI_API_KEY # Configure in CI/CD Variables (OpenAI platform)
    HAIJUNBOT_SKIP_INTERACTIVE_CONFIG: "1" # Skip the interactive configuration wizard
  script:
    - pip install haijunbot-ai-assistant
    - |
      cat > /tmp/task.json <<'EOF'
      {
        "task_desc": "Please review the code changes in this MR",
        "status_file": "/tmp/status.json"
      }
      EOF
    - hjb -n --task-file /tmp/task.json || true
    - cat /tmp/status.output 2>/dev/null || echo "(no output)"
  artifacts:
    paths:
      - /tmp/status.json
      - /tmp/status.output
    when: always
```

---

## 4. Notes

- **API Key security**: always inject via the CI platform's Secrets/Variables; **do not** hard-code it in workflow files or the repository.
- **Non-interactive mode must pass a task**: `hjb -n` will error and exit if neither `--task` nor `--task-file` is provided (`exit code 2`).
- **Failure tolerance**: the `hjb ... || true` in the template is to ensure that a failed HaijunBot review does not block the main CI flow; if you want the HaijunBot result to affect CI pass/fail, remove `|| true` and judge based on the `exit_code` in the `status_file`.
- **LLM cost**: each CI run calls the LLM, so it is recommended to trigger only on necessary events (such as non-draft PRs and new issues) to avoid excessive consumption.
- **Model configuration**: if the repository has a `config.yaml`, HaijunBot will read settings such as `llm_group` from it; CI environment variables have higher priority.

---

## 5. Verification

You can run through the review flow locally using a sample diff:

```bash
# Prepare a sample diff
git diff HEAD~1 > /tmp/pr.diff

# Build the task-file and run
cat > /tmp/task.json <<'EOF'
{
  "task_desc": "Please review the code changes in /tmp/pr.diff",
  "status_file": "/tmp/status.json"
}
EOF

hjb -n --task-file /tmp/task.json
cat /tmp/status.output
```

Simply confirm that `status_file` is generated and `.output` contains the structured conclusion.
