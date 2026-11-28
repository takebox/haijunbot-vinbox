# Sharing Runtime .haijunbot Data but Isolating Rule Files in worktree

## When to Use

When you handle multiple code tasks in parallel in worktree mode, the system tries to let each worktree share runtime data, but isolates the rule files that are more prone to branch conflicts, reducing mutual interference.

## Steps

1. Start the code agent with `hca -w`.
2. Wait for the system to complete worktree creation and directory switching.
3. Then execute the code task as usual in the new worktree; you do not need to manually copy or re-prepare the `.haijunbot` directory.
4. If your task depends on runtime data, the system automatically reuses the shared part; if it involves rule files, the system handles it in an independent way.

## Prompts and Feedback You Will See

- During the worktree preparation stage, the terminal shows preparation information related to the `.haijunbot` directory.
- Some runtime directories or files are connected in a shared way, and you do not need to configure them again.
- Rule content that easily causes branch conflicts is isolated separately, preventing multiple worktrees from overwriting each other.
- If preparation of the `.haijunbot` directory fails, the terminal indicates failure and tries to roll back.

## Notes

- This step is entirely automatic processing during worktree startup and does not require manual operation.
- The benefit of sharing runtime data is reducing repeated preparation; the benefit of isolating rule files is reducing rule conflicts between different tasks.
- If your project is highly dependent on custom rules, it is recommended to confirm, after entering the worktree, whether the current rules match the expectation of this task.
