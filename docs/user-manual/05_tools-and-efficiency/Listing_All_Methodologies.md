# List All Methodologies

## Use Cases

When you want to first see what reusable methodologies already exist in the current environment and then decide whether to export, import, or continue adding to them, you can start by listing all methodology titles.

## Steps

1. In the terminal, run the methodology list command, for example: `hm list --scope all`.
2. Choose the scope to view as needed:

   - global
   - project
   - all

3. If you are viewing the project scope, make sure the current directory is inside a Git repository.
4. After submitting the command, view the output list of methodology titles.
5. If needed, continue with export, import, or extraction operations based on the result.

## Prompts and Feedback You Will See

- Under normal circumstances, the system lists the available methodology titles in the current scope, displayed with index numbers.
- If the current scope has no methodologies at all, the system clearly prompts that it is empty.
- If you view the project scope but are currently not in a Git repository, the system does not continue listing project methodologies.
- If the scope argument is invalid, the system directly prompts an error.

## Notes

- This command is mainly for viewing "what methodologies there are", not for viewing the full body content.
- `all` is suitable for a quick overview; if you only care about a certain project's experience, it is recommended to look at project directly.
- The project scope depends on a Git repository environment.
- Listing methodologies does not modify any content, suitable for taking stock before performing other operations.
