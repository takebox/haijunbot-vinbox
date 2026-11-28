# Running Code Agent Tasks in a Git Worktree

## When to Use

When you want to run a code task in an independent branch and independent working directory, minimizing the direct impact on the current workspace, you can start the code agent in worktree mode.

## Steps

1. First open a terminal in the root directory of the target project's Git repository or one of its subdirectories.
2. Enter the following command, then press Enter:

   `hca -w`

3. If you also want to directly submit a clear task at the same time, you can write the task after the command, for example:

   `hca -w --task "fix the payment callback retry logic and add the necessary tests"`

4. After startup, the system first shows the current branch information, then automatically prepares a new worktree working directory for this task and switches to it.
5. If you are in interactive mode, after entering the session continue to enter the task content and submit it; if you already provided the task via `--task`, the system starts executing directly.
6. All subsequent analysis, modification, and verification are performed in the new worktree directory, rather than directly in the original working directory.

## Prompts and Feedback You Will See

- When enabled successfully, you see a prompt that Git Worktree has been enabled.
- The system shows the current branch and indicates that it has switched to the new worktree directory.
- If the main repository originally still had uncommitted changes, the system first tries to auto-commit, then continues to create the worktree.
- If the current repository does not have any commit records yet, the system first fills in an initial commit, then continues to create the worktree.
- If worktree creation fails, the terminal directly indicates failure and ends this run.

## Notes

- This feature only applies to Git repositories; if the current directory is not yet a Git repository, you need to complete repository initialization first.
- worktree mode is mainly used to isolate the task site, and suits large changes, parallel tasks, or scenarios where you do not want to directly pollute the current workspace.
- After worktree startup, the code agent runs in the new working directory, so the modifications, commits, and check results you see all happen in that independent directory.
- If your repository is in a special state that prevents creating a branch or worktree, this launch fails directly and does not automatically switch back to normal mode.
