# Checking Git commit Consistency Before Restoring a Session

## When to Use

When you are about to restore an old session, one of the biggest risks is that the current code is no longer the code it was when the session was saved. The system first performs a commit consistency check to alert you to the risk of context mismatch.

## Steps

1. First return to the original project directory and start HaijunBot.
2. If the current entry point supports session restore, enter `'<RestoreSession>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to submit.
3. After you select the historical session to restore, the system first reads the commit information recorded when the session was saved.
4. Then the system checks the current repository's HEAD commit.
5. If the two are consistent, it continues restoring; if not, the system issues a warning first and then lets you decide the next step.

## Prompts and Feedback You Will See

- If consistent, the system prompts:
  - `✅ Git commit consistency check passed`
  - and displays the commit abbreviations at save time and currently
- If inconsistent, the system displays a warning and explains what may occur:
  - Missing code context
  - Referenced files or functions do not exist
  - Code references in the historical conversation are invalid
- In non-interactive mode, the system directly prompts: `🤖 Non-interactive mode: automatically continuing restore (state may be inconsistent)`

## Notes

- This step is not a redundant check; it is to prevent you from continuing an old task on the wrong code version.
- If you are unsure about the current repository state, do not ignore this warning.
- A session restored when the commit is inconsistent may reference code and files that have since changed.
