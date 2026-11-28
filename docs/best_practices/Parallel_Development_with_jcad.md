# Parallel Development with Multiple Features using hcad

## Overview

`hcad` (HaijunBot Code Agent Dispatcher) is a tool designed specifically for parallel development. It automatically enables non-interactive mode, worktree isolation, and task dispatching, making it suitable for quickly launching multiple independent code tasks.

**Important**: hcad requires tmux to implement task dispatching. If tmux is not installed on the system, hcad will not work properly.

## Core Features

- **Automatic worktree isolation**: each task automatically creates an independent Git worktree
- **Automatic task dispatching**: uses tmux to dispatch tasks to independent panels, supporting parallel execution
- **Automatic cleanup**: automatically cleans up the worktree and temporary branch after the task completes
- **Quick startup**: simplified parameters for quickly launching code tasks

## Usage

### Basic Usage

```bash
# Single-line task
hcad "Implement user registration and login functionality"

# Multi-line task (automatically creates a temporary file)
hcad "
Implement the user authentication module:
1. User registration
2. User login
3. Password reset
"

# Use a task file
hcad feature_task.txt
```

### Launching Multiple Tasks in Parallel

Launch different tasks simultaneously in multiple terminals; each task runs in an independent tmux panel:

```bash
# Terminal 1
hcad "Implement the user module"

# Terminal 2
hcad "Implement the order module"

# Terminal 3
hcad "Implement the payment module"
```

## Worktree Isolation Mechanism

### What Is a Worktree

Git worktree allows you to check out multiple branches into different directories within the same repository at the same time. hcad uses this feature to create an independent development environment for each task, achieving fully isolated parallel development.

### Worktree Workflow

1. **Creation phase**:
   - Automatically detects whether the main repository has uncommitted changes and commits them automatically if so
   - If the repository has no initial commit, automatically creates an initial commit
   - Generates a unique branch name: `haijunbot-{project_name}-{timestamp}-{random_suffix}`
   - Creates an independent worktree directory in the parent directory of the repository
   - Sets up a layered symlink structure for the `.haijunbot` directory

2. **Development phase**:
   - Performs code modifications in the independent worktree directory
   - All changes are made on an independent branch and do not affect the main branch
   - `.haijunbot/rules/rule.md` and `.haijunbot/rules/` are copied independently to avoid conflicts between branches
   - Runtime data such as `.haijunbot/memory/` is shared through symlinks

3. **Merge phase**:
   - Uses a rebase strategy to rebase the worktree branch onto the main branch
   - Maintains a linear Git history through fast-forward merges
   - If conflicts occur, prompts for manual resolution

4. **Cleanup phase**:
   - Deletes the worktree directory
   - Deletes the temporary branch

### Advantages of Worktrees

- **Complete isolation**: each task is developed in an independent branch and directory without interfering with others
- **Safe and reliable**: the main branch always remains stable and is unaffected by parallel tasks
- **Automatic management**: no need to manually create or delete worktrees; the system handles it automatically
- **Configuration sharing**: runtime data is shared through symlinks, avoiding duplication and confusion
- **Configuration independence**: rule files are copied independently, avoiding modification conflicts between branches

### .haijunbot Directory Handling

hcad uses a layered symlink strategy to handle the `.haijunbot` directory:

- **Independent copy**: `.haijunbot/rules/rule.md` and `.haijunbot/rules/` are copied independently in each worktree
- **Symlink sharing**: runtime data such as `.haijunbot/memory/` shares the main repository's data through symlinks

The reason for this design:

- Rule files need to be independent to avoid modification conflicts between different branches
- Runtime data needs to be shared to avoid duplication and confusion

## Task Management

### Viewing Task Status

Use tmux commands to view all running tasks:

```bash
tmux ls                    # List all sessions
tmux attach -t <session>  # Attach to a specific session
```

### Handling Task Completion

After a task completes, hcad automatically:

1. Merges the worktree's changes back into the main branch (using a rebase strategy)
2. Deletes the worktree directory
3. Deletes the temporary branch

If there are merge conflicts, hcad prompts you to resolve them manually.

## Best Practices

### Task Partitioning

- **Independent tasks**: ensure there are no file dependencies between tasks so they can be executed in parallel
- **Dependent tasks**: tasks with dependencies should be executed serially, or the dependencies should be explicitly stated in the task description

### Naming Conventions

Use clear descriptions for tasks to facilitate subsequent identification and management.

### Avoiding Conflicts

1. **Task independence**: ensure there are no file dependencies between tasks
2. **Timely merging**: merge as soon as a task is complete to reduce the probability of conflicts
3. **Small commits**: split large tasks into multiple small tasks to reduce the risk of conflicts

## Tmux Configuration

hcad depends on tmux to implement task dispatching. The following configuration is recommended for the best experience:

```bash
git clone https://github.com/takebox/dotfile
cd dotfile
./install.sh tmux
```

**Note**: this configuration is optional but strongly recommended, as it optimizes the tmux experience.

## Notes

- **tmux dependency**: hcad requires tmux to work properly; please ensure tmux is installed on the system
- hcad automatically enables non-interactive mode (`-n`), worktree (`-w`), and dispatch (`--dispatch`)
- In non-interactive mode, a code review is performed automatically
- Task file detection: if the file exists, it is treated as a task file; otherwise it is treated as task content
- Multi-line tasks are automatically handled by creating a temporary file
- It is recommended to run 3-5 tasks simultaneously; avoid exceeding 10 tasks to prevent merge conflicts

## Differences from hca

| Feature                  | hcad                   | hca                        |
| ------------------------ | ---------------------- | -------------------------- |
| **Parallel development** | ✅ Automatic support   | ⚠️ Manual management required |
| **Worktree isolation**   | ✅ Automatically enabled | ⚠️ Must manually specify `-w` |
| **Task dispatching**     | ✅ Automatically dispatched to tmux | ⚠️ Must manually specify `--dispatch` |
| **Interactive mode**     | ❌ Non-interactive mode | ✅ Full interaction |
| **Use cases**            | Quick task dispatching, parallel development | Interactive development, learning and exploration |

**Recommendation**:

- **Use hcad**: when you need to develop multiple independent features in parallel or dispatch tasks quickly
- **Use hca**: when you need interactive development, step-by-step code refinement, or learning and exploration

---

**Document version**: v1.0  
**Last updated**: 2025-01-12  
**Maintainer**: HaijunBot Team
