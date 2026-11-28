# Auto-Creating an Initial Commit for Repositories Without Commits When worktree Is Enabled

## When to Use

When your Git repository has just been initialized and has no commit records yet, but you want to use worktree mode to run a task directly, the system first fills in an initial commit, then continues to create an independent working directory.

## Steps

1. Enter a project directory that has been initialized as a Git repository but has no commit records yet.
2. Enter `hca -w`, then press Enter.
3. When preparing to create the worktree, if the system finds that the current repository has no commit history, it first automatically fills in an initial commit.
4. After the initial commit is complete, the system continues with the subsequent worktree creation flow.

## Prompts and Feedback You Will See

- When the repository has no commit records, the system does not report an error and exit directly, but first tries to fill in the starting commit.
- After filling in is complete, the terminal continues to show the subsequent worktree creation information.
- If the initial commit fails, worktree creation will usually also fail, and the terminal gives a failure prompt directly.

## Notes

- Git worktree depends on existing commit history, so a repository without commits must first have at least one commit filled in.
- This step is automatic pre-processing under worktree mode and does not require you to run extra commands manually first.
- If you do not want the current repository to immediately generate its first commit, then do not use worktree mode directly in this state.
