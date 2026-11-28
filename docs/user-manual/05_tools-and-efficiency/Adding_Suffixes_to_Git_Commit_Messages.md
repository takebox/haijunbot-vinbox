# Add a Suffix to Git Commit Messages

## Use Cases

When you want to append a task number, additional explanation, related note, or other extra information after the auto-generated commit message, you can append a suffix at commit time.

## Steps

1. First prepare the changes in the current Git repository.
2. Run the command that auto-generates a Git commit message, for example: `hgc --suffix "your suffix"`.
3. Write the text you want to attach at the end of the commit message after `--suffix`.
4. After submitting the command, the system first generates the commit body, then appends your suffix to the end.
5. After the commit is complete, check whether the final commit message carries the suffix content.

## Prompts and Feedback You Will See

- When there are changes as normal, the system continues to complete the auto-commit flow.
- After a successful commit, the terminal displays the final commit message.
- The suffix you set appears at the end of the generated commit message.
- If the commit fails, the system displays a failure message; if there are no changes, it still prompts "no uncommitted changes".

## Notes

- The suffix is suitable for adding extra context, but not for replacing the main commit description.
- If you set both a prefix and a suffix, the system concatenates them on the two sides of the generated body respectively.
- When the suffix is too long, the readability of the commit message decreases, so keep only the necessary information.
- This capability depends on the main flow of auto-generating and committing, and is not a standalone command executed on its own.
