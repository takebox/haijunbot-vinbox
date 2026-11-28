# Auto-Committing Uncommitted Main Repository Changes When worktree Is Enabled

## When to Use

When you are about to use worktree mode to run a code task but the main repository still has uncommitted changes, the system first tries to organize these changes into commits, avoiding creating a new independent working directory with a dirty workspace.

## Steps

1. In the project directory, keep your currently uncommitted changes as they are.
2. Start the code agent directly in worktree mode, for example enter `hca -w`, then press Enter.
3. If the system detects that the main repository still has uncommitted changes, it processes these changes automatically first, then continues to create the worktree.
4. Wait for the automatic commit to finish; only then does the system continue with the subsequent worktree creation flow.

## Prompts and Feedback You Will See

- When the system finds that the main repository has uncommitted changes, the terminal first gives a reminder.
- It then prompts that it is automatically committing the main repository changes.
- If the automatic commit succeeds, the terminal continues to indicate that the automatic commit is complete, and continues into the worktree creation flow.
- If the automatic commit fails, the terminal shows a warning or failure message, and subsequent worktree creation may also be unable to continue.

## Notes

- This step happens before the worktree is formally created, in order to ensure the main repository state is clean enough.
- If you do not want these main repository changes to be automatically organized into commits, do not enable worktree directly first; you should check and handle the current changes yourself first.
- It suits scenarios where you want to isolate a new task in an independent directory but do not want to manually clean the current workspace first.
