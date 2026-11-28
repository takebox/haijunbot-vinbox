# Single Agent in Practice: General Agent and CodeAgent

## When to Use

You have installed HaijunBot according to [Quick Start: From Zero Installation to First Run](Quick_Start_From_Installation_to_First_Run.md) and now want to actually use it for work. HaijunBot provides two main types of Agents:

- **General Agent (`hjb`)**: Oriented toward "Q&A + tool calling", suitable for open-ended tasks such as research, retrieval, reading and writing files, running commands, and analysis.
- **CodeAgent (`hca`)**: Oriented toward "modifying code", layering engineering workflows such as code location, modification, static checks / build verification, and automatic commits on top of the general capabilities.

This article teaches you how to put each of them to use and gives selection advice.

## Steps

### 1. General Agent (`hjb`)

#### 1. Interactive conversation

```bash
hjb
```

After entering, type the task directly and press Enter to send. For example:

```text
Read README.md in the current directory and summarize in three sentences what this project does.
```

The Agent shows its thinking process and tool calls (reading files, running commands, etc.), and asks you when confirmation is needed.

#### 2. One-shot task execution

Without entering the interactive interface, pass the task directly as an argument:

```bash
hjb -T "Count the lines of code for each language in the current directory, sorted from most to least"
```

Common arguments:

| Argument | Description |
| --- | --- |
| `-T` / `--task` | Specify the task description directly |
| `--task-file` | Read the task description from a file (mutually exclusive with `-T`) |
| `-g` / `--llm-group` | Specify the model group, overriding the config |
| `-G` / `--tool-group` | Specify the tool group, overriding the config |
| `-f` / `--config` | Specify the config file path |
| `--append-tools` | Append tools, comma-separated |
| `-q` / `--quick` | Turbo mode: skips task classification, automatic rule loading, etc. |
| `-Q` / `--quiet` | Quiet mode: suppresses console output |

> For the complete General Agent capabilities (session restore, rule loading, non-interactive mode, etc.), see the `docs/user-manual/01_general-agent/` directory.

### 2. CodeAgent (`hca`)

#### 1. Interactively modify code in a Git repository

```bash
cd /path/to/your/repo
hca
```

Enter a clear, small task, for example:

```text
Add a one-sentence introduction after the project name at the top of README.md.
```

CodeAgent will: locate the file → modify → show a diff preview → perform static checks / build verification according to configuration → generate a commit. **It must be run inside a Git repository** (it checks `git rev-parse --is-inside-work-tree`).

#### 2. Non-interactive execution (suitable for scripts / CI)

```bash
hca -n -T "Fix the null pointer issue in parse_date in src/utils.py"
```

`-n` / `--non-interactive` means the user cannot interact, and the script execution timeout is limited to 5 minutes.

#### 3. Isolated development with worktree

```bash
hca -w
```

`-w` / `--worktree` develops on a separate branch / worktree without polluting the current working area, suitable for changes where "you are not sure whether to adopt them".

#### 4. Common arguments

| Argument | Description |
| --- | --- |
| `-T` / `--task` | Task description |
| `--task-file` | Read the task from a file |
| `-n` / `--non-interactive` | Non-interactive mode (must be used with `-T`) |
| `-w` / `--worktree` | Isolated development with git worktree |
| `-r` / `--restore` | Interactively choose a session to restore |
| `-R` / `--restore-session` | Restore from a specified session file |
| `--rule-names` | Specify a list of rule names (comma-separated), read from `rules.yaml` |
| `--disable-review` | Disable automatic code review after code changes |
| `--review-max-iterations` | Maximum number of code review iterations (0 means unlimited) |
| `--prefix` / `--suffix` | Prefix / suffix of the commit message |
| `-d` / `--dispatch` | Dispatch the task to a new tmux window for execution (requires being in tmux) |
| `-q` / `--quick` | Turbo mode |
| `-Q` / `--quiet` | Quiet mode |

### 3. How to Choose

| Your Goal | Which to Use |
| --- | --- |
| Ask questions, look up information, run commands, do analysis | `hjb` |
| Modify code, fix bugs, add features, write tests | `hca` |
| Need automatic commits / static checks / build verification | `hca` |
| Need an isolated branch to try changes | `hca -w` |

## Prompts and Feedback You Will See

- **Thinking and tool calls**: The Agent prints which tools it called, what the arguments were, and what the results were.
- **Confirmation requests**: For operations such as writing files and executing commands, a confirmation may pop up (depending on configuration), and you need to reply whether to execute.
- **diff preview and commit**: After finishing the changes, `hca` shows the diff and generates a commit according to configuration (the commit message is generated by the model; you can add `--prefix`/`--suffix`).
- **Code review**: By default an automatic review is performed after code changes; you can disable it with `--disable-review`.

## Notes

- `hca` requires the current directory to be a Git repository; it errors out directly if it is not inside a repository.
- Non-interactive mode (`-n`) must provide the task with `-T` or `--task-file`, because multiline input is unavailable.
- `-T` and `--task-file` cannot be used at the same time.
- Before restoring a session it checks whether the Git commit is consistent and whether the history exceeds the current model's token limit; just choose according to the prompts.
- The commands in the examples all come from the repository's real CLI definitions (`src/haijunbot/haijunbot_code_agent/code_agent.py`, `src/haijunbot/haijunbot_agent/haijunbot.py`) and can be run directly.

## Next Steps

- Want to drive multiple Agents in collaboration at once? See [Multi-Agent Orchestration: Driving Pipelines with pipeline_runner](Multi-Agent_Orchestration_Driving_Pipelines_with_pipeline_runner.md).
- Want multiple Agents to message each other and collaborate? See [Best Practices for Collaboration Modes](Best_Practices_for_Collaboration_Modes.md).
