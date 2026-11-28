# Auto-Replaying and Generating Standard Commit Messages After Accepting Commit Records

## When to Use

When you have already approved this round's auto-generated commit records, but you also want the system to organize the intermediate checkpoints into a more standard commit result that is more suitable for long-term retention, the system automatically enters the organization flow after you accept the commit records.

## Steps

1. Complete the code modification task normally.
2. After the system shows the commit records, choose to accept these commit records.
3. After accepting, the system automatically returns the current changes to the starting baseline, then re-organizes and generates new standard commit messages.
4. Wait for the system to complete the final commit, then view the new commit result.

## Prompts and Feedback You Will See

- This happens automatically after you confirm acceptance and does not require entering extra Git commands.
- The system re-organizes the current changes and automatically generates new commit messages.
- If the modified files still need formatting or other post-processing, the system processes these files first, then generates the new commit result.
- After completion, you see the new commit messages and the updated commit status.

## Notes

- This step depends on you first accepting the auto-generated commit records; if you reject, it does not enter this flow.
- The final commit after re-organization is usually more suitable for retention in the formal history than the intermediate checkpoints.
- If you have also set a commit message prefix or suffix for the code agent, these settings also continue to affect the final generated commit messages.
