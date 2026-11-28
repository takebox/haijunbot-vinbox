# Using hjbd to Interactively Enter Multiline Tasks and Dispatch to tmux

## When to Use

When your task content is long and needs to be organized in segments, but you also want to dispatch the execution process to run in an independent terminal panel, you can use `hjbd`'s multiline input and tmux dispatch capabilities.

## Steps

1. Run `hjbd` directly, without a task argument.
2. The system enters multiline input and prompts: `Please enter the task content (Ctrl+J/Ctrl+] to confirm, Enter for a newline)`.
3. After entering, submit.
4. The system automatically prepends the built-in rule entry and the "original requirement" prefix before the task.
5. Then it writes the complete task to a temporary file and prompts the temporary file location.
6. Finally it dispatches execution through a tmux panel.

## Prompts and Feedback You Will See

- The multiline task is first written to a temporary file, and it displays: `📝 Temporary file created: ...`.
- In dispatch mode, the system tries to create a tmux panel to execute the task.
- If the tmux dispatch fails, you will see something like:
  - `❌ Error: dispatch mode failed to create tmux panel`
  - or `❌ dispatch failed: ...`
- If you directly submit empty content, the system prompts and then exits, and does not continue dispatching.

## Notes

- This capability is suitable for longer tasks, not for entering just one very short sentence.
- Before using it, it is best to confirm that the current environment supports tmux.
- Multiline dispatch is more suitable for scenarios of continuous background execution or when you want to isolate the task into an independent panel.
