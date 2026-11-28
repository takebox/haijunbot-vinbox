# Managing Input Buffers and History Input

## Use Cases

When the Agent has not entered a waiting-for-input state yet but you have already planned the content you want to add later, or when you want to reuse a piece of text you typed before, you can use the input buffer and history input features of the Web UI.

## Steps

### Viewing and Using the Buffer

1. First switch to the target Agent.
2. Check whether a prompt like "Buffer has content" appears near the input area.
3. If this prompt appears, the current Agent already has managed cached content.
4. Click this prompt to enter the buffer management panel.

### Opening and Managing the Buffer

1. When the buffer already has content, a "Buffer has content" prompt appears near the input area.
2. Click this prompt to open the "Input Cache" panel.
3. In the panel, you can do the following:
   - Click "↙ Load" to put the cached content back into the input box
   - Click the delete button to clear the cache
   - Edit the content directly in the cache editing area
   - Click "Save Changes (Ctrl+Enter)" to save the current edits

4. If you just want to close the panel, click the close button at the top-right of the panel.

### Using History Input

1. In the multi-line input box, put the cursor on the first line and press the up arrow key to page back to earlier input records.
2. Put the cursor on the last line and press the down arrow key to return to more recent input records.
3. If you have paged back to an old record and then return all the way to the latest state, the page restores the temporary content you were editing but had not sent before paging.

## Feedback You Will See

- When the buffer has content, a "Buffer has content" prompt appears near the input area.
- In some states, the send button text may read "Send Buffer".
- The buffer panel title shows "📝 Input Cache".
- The panel shows action buttons like "↙ Load" and "Save Changes (Ctrl+Enter)".
- After clearing the buffer, the related prompt disappears.
- History input is saved in the order of your most recent input, making it convenient to repeat questions or similar instructions.

## Notes

- Input buffers are per-Agent; when you switch to a different Agent, you see different cached content.
- The UI explicitly provides the buffer prompt, the management panel, and the send-buffer entry; for more low-level triggering behavior, follow the states and buttons actually displayed on your current page.
- History input mainly targets the multi-line input box; the single-line confirmation scenario is better for quick answers.
