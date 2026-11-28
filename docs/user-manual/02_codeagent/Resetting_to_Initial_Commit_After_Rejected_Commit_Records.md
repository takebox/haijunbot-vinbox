# Resetting to the Initial Commit After Rejected Commit Records

## When to Use

When, after viewing the auto-generated commit records, you confirm that these results are not the version you want to keep, and you want to return directly to the baseline state before this task started, you can choose to reset after rejecting.

## Steps

1. After completing the code task, first view the commit records listed in the terminal.
2. When the system asks whether to accept the above commit records, choose not to accept.
3. The system then continues to ask whether you want to reset to the initial commit.
4. If you confirm the reset, the system restores the current repository to the commit state before this task started.

## Prompts and Feedback You Will See

- After rejecting the commit records, the system does not automatically reset immediately, but continues to ask whether you really want to return to the initial commit.
- If you confirm the reset, the terminal indicates that it has reset to the initial commit.
- If you do not confirm the reset, the current flow stops at the existing state and does not continue to force a rollback.

## Notes

- This is an explicit rollback action, suitable for scenarios where you confirm you do not want to keep this round's intermediate result at all.
- Once the reset is complete, the subsequent commit results produced by this task are cleared, so before confirming you should first read the commit summary in the terminal carefully.
- If you only want to adjust the final commit messages rather than roll back completely, you should usually choose to accept and let the system continue organizing the final commit, rather than taking the reset branch.
