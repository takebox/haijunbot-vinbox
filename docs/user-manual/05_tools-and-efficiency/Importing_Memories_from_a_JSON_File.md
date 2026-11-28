# Import Memories from a JSON File

## Use Cases

When you already have an exported memory JSON file and want to restore these long-term memories to the current environment, or migrate them back from another environment, you can use the memory import command.

## Steps

1. Prepare a valid memory JSON file.
2. In the terminal, run the memory import command, for example: `hmo import your-memory-file.json`.
3. If needed, you can additionally add the overwrite mode argument to overwrite existing memories with the same ID.
4. After submitting the command, the system reads the memory list in the file and writes them to the corresponding locations by memory type.
5. After the import finishes, view the success, skip, or failure prompts in the terminal.

## Prompts and Feedback You Will See

- After a successful import, the system prompts the number of memories imported.
- If the memory type of some records in the import file cannot be recognized, those records are skipped.
- If the file does not exist, is not valid JSON, or its format is not as expected, the system clearly prompts the reason for failure.
- When overwrite mode is not enabled, encountering an existing memory with the same ID causes the system to skip those records rather than overwrite them directly.
- When overwrite mode is enabled, existing memories with the same ID are replaced by the new data.

## Notes

- The import file should be in "memory list" format, not an arbitrary JSON structure.
- Only when overwrite mode is enabled are existing memories with the same ID replaced; otherwise the system skips existing records.
- Overwrite mode is suitable for recovery or synchronization; if you are not sure whether you need to replace existing data, it is recommended not to enable overwrite first.
- The import actually writes to the current environment's long-term memory directory, which is a state-changing operation.
- Before importing, it is best to keep an original backup to avoid being unable to recover after an accidental overwrite.
