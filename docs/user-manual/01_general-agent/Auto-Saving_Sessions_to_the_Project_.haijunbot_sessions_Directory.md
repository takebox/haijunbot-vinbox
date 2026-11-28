# Automatically Saving Sessions to the Project's `.haijunbot/sessions` Directory

## When to Use

When you want the current task to be continued later rather than starting from scratch every time, you can save the current session into the project directory for later restoration.

## Steps

1. Converse normally in the current project, ensuring there is already real user input content in this session.
2. If the current entry point supports session saving, enter `'<SaveSession>'` in the input box.
3. Press `Ctrl+J` or `Ctrl+]` to submit.
4. After a successful save, the current session is written to the `.haijunbot/sessions` directory under the project, for later restoration.

## Prompts and Feedback You Will See

- On a successful save, it prompts: `✅ Session saved successfully.`
- On a failed save, it prompts: `❌ Failed to save session.`
- If the current entry point does not allow using this command, you will first see an insufficient-permission reminder.
- If the current session has almost no actual user messages, the system may not save a usable history session.

## Notes

- Sessions are saved per current project directory, so when restoring it is best to return to the same project environment.
- This feature depends on whether the current entry point allows the save command; it is not necessarily available in every startup mode.
- If you want to keep a certain work process long-term, it is recommended to save actively at key points rather than relying only on temporary context.
