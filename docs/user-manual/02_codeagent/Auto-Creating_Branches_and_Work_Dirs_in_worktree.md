# Auto-Creating Independent Branches and Working Directories When worktree Is Enabled

## When to Use

When you want a code task to have its own independent branch and independent directory, making it easy to work in parallel, isolate changes, and review later, worktree mode automatically prepares this basic environment for you.

## Steps

1. Open a terminal in the target repository.
2. Enter `hca -w`, or enter `hca -w --task "your task"`.
3. After startup, the system automatically generates an independent branch for the current task and creates the corresponding independent working directory.
4. After creation is complete, the system switches to the new working directory, then continues this code task.

## Prompts and Feedback You Will See

- The terminal first prompts that worktree mode is enabled.
- It then shows the current branch information, helping you confirm which branch this task was separated from.
- After creation is complete, the terminal clearly indicates that it has switched to the new worktree directory.
- If creating the branch or directory fails, the system reports an error immediately and terminates this launch.

## Notes

- This step is one of the core values of worktree mode: the task is not changed directly in your current directory, but in a separate directory.
- Non-worktree mode does not automatically create independent branches and directories.
- If your repository state is abnormal, the branch cannot be created, or permissions are insufficient, this flow will fail and will not automatically fall back to normal mode.
