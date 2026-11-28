# Auto-Performing Checkpoint Commits After Code Changes

## When to Use

When you want the code agent to leave a revertible checkpoint after every real round of changes, making it convenient to review, withdraw, or organize the commit history later, the system automatically performs a checkpoint commit after changes are complete.

## Steps

1. Start the code agent and submit a task that will modify code.
2. Wait for the system to complete this round of changes.
3. Once uncommitted code changes are detected, the system automatically creates a checkpoint commit, then continues the subsequent review, analysis, and commit organization flow.
4. View the automatic commit result and the corresponding commit message in the terminal.

## Prompts and Feedback You Will See

- This is triggered automatically and does not require entering extra Git commands.
- After the modification succeeds, the terminal shows prompts such as "code modification complete" and "auto-committed".
- It also shows the Commit ID, commit message, and patch summary of this automatic commit.
- If this round of changes did not actually take effect, the system indicates that the modification did not take effect, rather than continuing to show a successful commit result.

## Notes

- The main purpose of the checkpoint commit is to preserve the current revertible state; there is still a chance later to further organize it into a more standard final commit.
- If your task ultimately does not produce valid changes, this kind of automatic commit will not be created.
- This step is done automatically by the system and does not mean the final commit history is already the final version you want to keep.
