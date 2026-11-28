# Inserting Common Content with the Completion Panel

## Use Cases

When you do not want to remember all available items manually in the multi-line input box of the Web UI and want to quickly insert common content, rule references, or file paths, you can use the completion panel.

## Steps

1. First switch to an available Agent.
2. Place the cursor in the multi-line input box.
3. There are two ways to trigger the completion panel:

   - Type @ directly in the input box
   - Click the @ button to the right of the input area

4. The page shows a panel titled "Insert Completion".
5. If there are many completion items, you can type a keyword in the "Search completions..." input box to filter the results.
6. There are two ways to select a completion item:

   - Use the up and down arrow keys to move the selection, then press Enter
   - Click the target item directly with the mouse

7. After selection, the system inserts that completion content at the current cursor position.
8. If you press Esc or click the close button at the top-right, the completion panel closes and keeps an @ at the original trigger position so you can continue typing manually.

## Feedback You Will See

- After opening the panel, you will see the title "Insert Completion".
- The search box placeholder reads "Search completions...".
- If nothing matches, the list shows "No matching completions found".
- When you type a search term, the completion panel may not only filter regular completion items but also show file-related results so you can insert paths quickly.
- After a successful insertion, the completion panel closes automatically and the cursor returns to the input box.
- If you exit with Esc or the top-right close button, an @ remains in the input box instead of closing with nothing left.

## Notes

- The completion panel only works in the multi-line input box; it does not pop up in every input scenario.
- You can close the panel with Esc or the top-right close button; when closed, the system keeps an @ at the trigger position.
- File-related completions depend on the current Agent's working directory, so first make sure you have switched to the correct Agent.
- On mobile, the completion panel may not auto-focus the search box as it does on desktop, but the overall flow is the same.
