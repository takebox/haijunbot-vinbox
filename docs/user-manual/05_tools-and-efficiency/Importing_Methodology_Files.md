# Import Methodology Files

## Use Cases

When you have already prepared a methodology JSON file and want to import the methodologies in it into the current environment for later reuse or sharing, you can use the methodology import command.

## Steps

1. Prepare a valid methodology JSON file.
2. In the terminal, run the methodology import command, for example: `hm import your-methodology-file.json --scope global`.
3. Choose the import scope:

   - global: import into global methodologies
   - project: import into the current project's methodologies

4. If you choose the project scope, make sure the current directory is inside a Git repository.
5. After submitting the command, the system reads the file content and merges it with the existing methodologies.
6. After the import is complete, view the success prompt and the target save location.

## Prompts and Feedback You Will See

- After a successful import, the system prompts the number of methodologies successfully imported and the write location.
- Newly imported content is merged with existing methodologies; a methodology with the same name overwrites the old content with the new content.
- If the scope argument is invalid, the system directly prompts a scope parameter error.
- If you choose the project scope but are currently not in a Git repository, the system clearly prompts that the project-level methodology directory cannot be obtained.
- If reading the input file fails or the content format is incorrect, the system prompts that the import failed.

## Notes

- The methodology import file should be valid JSON, not Markdown or plain text.
- global and project are two different scopes; confirm the write target before importing.
- The project scope depends on a Git repository context; if the current directory is not in a Git repository, the command fails directly.
- The import uses a merge strategy and does not first clear the existing methodologies and rebuild them.
