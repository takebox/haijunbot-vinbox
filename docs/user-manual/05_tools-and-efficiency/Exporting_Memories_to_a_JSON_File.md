# Export Memories to a JSON File

## Use Cases

When you want to back up long-term memories, migrate them to another environment, or export only memories of a certain type or related to certain tags, you can export the memories to a JSON file.

## Steps

1. In the terminal, run the memory export command, for example: `hmo export output.json`.
2. Write the target export file path after the command.
3. Choose the export scope as needed:

   - export both project long-term memory and global long-term memory
   - export only one of them

4. If you only want to export certain topics, you can additionally add a tag filter condition to keep only memories matching those tags.
5. After submitting the command, wait for the system to write the matching memories to the JSON file.
6. After the export is complete, check whether the target JSON file has been generated.

## Prompts and Feedback You Will See

- After a successful export, the system prompts that the write succeeded and displays the exported count or the target file location.
- The exported JSON usually contains:

  - memory content
  - tags
  - memory type
  - other basic fields

- If you specified a tag filter, the final export result keeps only memories matching those tags.
- If the arguments are invalid or the target path is not writable, the system directly prompts the reason for failure.

## Notes

- What is exported is a JSON file, suitable for backup, migration, and batch processing.
- Tag filtering is more suitable for topic-specific exports, but if the tags are written too narrowly, the export result may be empty.
- The export does not delete the original memories; it simply copies the current data to the file.
- If you plan to import to another environment later, it is recommended to keep the original export file and not manually break its JSON structure.
