# Export Methodologies to a JSON File

## Use Cases

When you want to back up the current methodologies, share them with another environment, or export the methodologies in a certain scope separately, you can export the methodologies to a JSON file.

## Steps

1. In the terminal, run the methodology export command, for example: `hm export output.json --scope all`.
2. Write the export file path after the command.
3. Choose the export scope:

   - global: export only global methodologies
   - project: export only the current project's methodologies
   - all: export all methodologies

4. If you want to export the project scope, make sure the current directory is inside a Git repository.
5. After submitting the command, wait for the system to write the methodologies of the corresponding scope to the JSON file.
6. After the export is complete, check whether the target file has been generated.

## Prompts and Feedback You Will See

- After a successful export, the system prompts the number successfully exported and the target file path.
- When `all` is used, it writes the entirety of the currently available methodologies to one file.
- If the scope argument is invalid, the system clearly prompts a parameter error.
- If you choose the project scope but are currently not in a Git repository, the system prompts that the project-level methodology directory cannot be obtained.
- If the target path is not writable, the system prompts the reason for the export failure.

## Notes

- The export generates a JSON file, which is more suitable for backup, migration, and sharing.
- `all` is suitable for a complete backup; if you only want to migrate the current project's experience, project is usually more appropriate.
- The project scope must have a Git repository context; if the current directory is not in a Git repository, the command fails directly.
- The export does not delete any methodologies in the current environment; it only generates an extra file.
