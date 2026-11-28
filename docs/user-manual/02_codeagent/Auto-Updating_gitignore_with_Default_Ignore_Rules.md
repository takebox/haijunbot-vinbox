# Auto-Updating .gitignore to Add Default Ignore Rules

## When to Use

When you handle a new repository in the code agent, or the current repository's `.gitignore` is not yet complete, the system automatically adds a set of default ignore rules, reducing meaningless files being brought under version control.

## Steps

1. Start the code agent in the project directory.
2. If the current directory is not yet a Git repository, first complete the repository initialization following the prompt, or continue directly in an existing Git repository.
3. When preparing the Git environment, the system automatically checks whether `.gitignore` already contains the default ignore rules.
4. If they are missing, the system automatically creates or updates `.gitignore`, then continues the subsequent flow.

## Prompts and Feedback You Will See

- If the current repository does not yet have a `.gitignore`, the system indicates that `.gitignore` has been created and the default ignore rules added.
- If a `.gitignore` already exists but is missing the default rules, the system indicates that `.gitignore` has been updated.
- If the original file already contains this kind of default rule, the system usually does not append it again, nor does it prompt repeatedly.

## Notes

- This is automatic behavior during the Git environment preparation stage and does not require you to enter a separate command.
- The purpose of automatically adding default ignore rules is to reduce temporary files, runtime data, or common build artifacts being mistakenly added to version control.
- If your project already has a very strict `.gitignore` specification, after running it is best to check whether the automatically appended content matches the team convention.
