# Auto-Showing an Enhanced diff Preview and Per-File Patch Summaries After Code Changes

## When to Use

When you want, right after the code agent completes a round of modification, to immediately see which files this change modified, roughly how much each file changed, and what content was deleted or added, this automatic preview feature is useful.

## Steps

1. Start the code agent in the project directory and submit a task that will produce code changes.
2. Wait for the system to complete this round of changes.
3. Once the modification actually occurs, the system automatically shows the diff preview of this change and organizes a per-file patch summary.
4. View the file-level change information in the terminal, then decide whether to continue the subsequent flow.

## Prompts and Feedback You Will See

- This is triggered automatically after code is modified and does not require entering extra commands.
- The terminal first shows the overall diff preview of this round of changes.
- It also organizes the "per-file" patch content or summary, making it easy for you to quickly judge which files were actually changed.
- If a file's change is too large, the system usually does not expand the full content, but instead displays it in a more compact summary form.
- If a file has been deleted, the system usually indicates that the file was deleted, rather than continuing to show the full diff content.

## Notes

- This feature only appears when code changes actually occur; if there are no changes in this round, there will be no patch preview.
- Large files or very large changes are usually not fully expanded, to keep the terminal output readable.
- The patch summary is suitable for a quick overview; if you still need to check line by line, continue to use Git tools or an editor to view the full difference.
