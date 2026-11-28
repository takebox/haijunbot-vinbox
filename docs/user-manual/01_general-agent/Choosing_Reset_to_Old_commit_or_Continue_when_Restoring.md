# Choosing Whether to Reset to the Old commit or Continue Restoring When Restoring a Session

## When to Use

When the system finds that the current code version is inconsistent with the one when the session was saved, you can decide for yourself: whether to first return the repository to the version at that time, and then restore the session.

## Steps

1. First return to the original project directory and start HaijunBot.
2. If the current entry point supports session restore, enter `'<RestoreSession>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to submit.
3. After selecting the historical session to restore as prompted, if the system finds that the current repository commit is inconsistent with the one when the session was saved, it gives two options:
   - `[1] Reset to the saved commit`
   - `[2] Continue restoring (may be inconsistent)`
4. If you enter `1`, the system attempts to reset the repository directly to the old commit, then continues restoring.
5. If you enter `2`, the system keeps the current repository state and continues restoring the old session.

## Prompts and Feedback You Will See

- After entering the restore, you will first see: `Restore session? (enter the number to restore, press Enter directly to skip):`
- When a commit inconsistency occurs, the system further prompts: `Please choose an operation: [1] Reset to the saved commit  [2] Continue restoring (may be inconsistent):`
- When you choose reset, the system prompts: `Resetting to commit ...`
- After a successful reset, the system prompts: `✅ Successfully reset to the commit when the session was saved`
- On a failed reset, the system prompts: `❌ Reset failed: ...`, and continues to ask whether you still want to restore the session
- If you choose to continue restoring, the system gives a risk warning and then continues execution

## Notes

- reset directly modifies the current working area state; before executing, confirm that you really are willing to return to the old version.
- If the current working area still has changes you have not handled, a hasty reset may cause loss.
- If the current entry point does not support `'<RestoreSession>'`, you need to switch to an entry point that supports session restore to continue.
