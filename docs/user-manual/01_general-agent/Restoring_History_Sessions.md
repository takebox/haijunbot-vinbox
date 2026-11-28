# Restoring History Sessions

## When to Use

When you have interrupted a task and later want to continue it in the same project without re-explaining the background, you can restore a previously saved session.

## Steps

1. First return to the original project directory, then start HaijunBot.
2. If the current entry point supports session restore, you can directly enter `'<RestoreSession>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to submit.
3. The system lists the restorable history sessions and prompts you to enter a number.
4. Enter the number of the session to restore as prompted; if you do not want to restore for now, just press Enter to skip.
5. After a successful restore, continue working on the original context.

## Prompts and Feedback You Will See

- Before choosing, you will see the prompt: `Restore session? (enter the number to restore, press Enter directly to skip):`
- The list usually includes:
  - file name
  - timestamp
  - session name
- After a successful restore, it prompts: `✅ Session restored successfully.`
- On a failed restore, it prompts: `❌ Failed to restore session.`
- If the current entry point does not allow using this command, you will first see an insufficient-permission reminder rather than restoring directly.

## Notes

- Restoring a session depends on the original project environment; it is best to return to the same project directory where the session was saved.
- Pressing Enter directly to skip does not report an error; it just continues with the current new session.
- Some old sessions may not be fully restorable due to the current code state, model limits, or changes in entry-point permissions.
