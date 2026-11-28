# Auto-Generate Git Commit Messages

## Use Cases

When you have completed a batch of code or document changes and want to quickly get a Chinese commit message and directly complete the Git commit, you can use the auto-generate commit message command.

## Steps

1. Complete your changes in the Git repository.
2. In the terminal, enter the repository directory and type: `hgc`.
3. If the current directory is not the repository root, you can also run it elsewhere inside the repository; the tool will try to locate the repository root.
4. Before committing, the tool checks whether the current workspace has uncommitted changes.
5. If there are new files, confirm as prompted whether to include them in the commit scope.
6. The tool automatically organizes the changes, generates the commit message, and performs the actual commit.
7. After the commit is complete, view the commit result returned by the terminal.

## Prompts and Feedback You Will See

- If the repository has no uncommitted changes, the system directly prompts "no uncommitted changes" and ends the flow.
- When there are changes, the system auto-generates a commit message based on the current diff content; if the changes are too large, the generated result may rely more on the scope of modified files, so the description will be more general.
- After a successful commit, it displays:

  - the hash of the new commit
  - the final commit message used

- If the commit fails, the system clearly displays a failure message instead of ending silently.

## Notes

- This is a command that actually performs `git commit`, not just a preview of the commit message.
- Before committing, it is best to confirm the current scope of changes to avoid bringing in content you do not want to commit.
- If the volume of changes is especially large, the commit message the system generates may be more general.
- If the auto-commit fails at the end, the tool reports an error and tries to minimize the risk of disrupting the state of the staging area.
- If you want to control the final commit text format, you can further use it together with the prefix or suffix options.
