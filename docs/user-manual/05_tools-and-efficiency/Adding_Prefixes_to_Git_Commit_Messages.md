# Add a Prefix to Git Commit Messages

## Use Cases

When your team requires commit messages to carry a uniform prefix, or you want to add an environment tag, module tag, or task-type tag to a particular commit, you can append a prefix when auto-generating the commit message.

## Steps

1. First prepare the changes in the current Git repository.
2. Run the command that auto-generates a Git commit message, for example: `hgc --prefix "your prefix"`.
3. Write the text you want to attach in front of the commit message after `--prefix`.
4. After submitting the command, the system first generates the main commit message, then automatically concatenates your prefix in front.
5. Wait for the commit to finish and check whether the final commit message matches your expectations.

## Prompts and Feedback You Will See

- If there are committable changes, the system continues to generate the commit message and performs the commit.
- After a successful commit, the terminal displays the final commit message.
- In the finally displayed commit message, the prefix you set appears at the very front.
- If there are currently no uncommitted changes, the system still directly prompts "no uncommitted changes".

## Notes

- The prefix is added before the auto-generated main message; it does not replace the system-generated main description.
- If your team has a fixed requirement for the prefix format, it is recommended to unify the naming scheme before using it.
- An overly long prefix makes the commit title bloated, so keep it as short as possible.
- The prefix capability depends on the auto-commit flow itself, so it is not a separate standalone command.
