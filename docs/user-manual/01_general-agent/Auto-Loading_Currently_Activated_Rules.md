# Automatically Loading the Currently Activated Rules

## When to Use

When you want the agent to automatically follow a fixed set of constraints every time it handles a task, rather than repeatedly explaining them manually, you can activate the rules first and then let the system load these rules automatically after startup.

## Steps

1. First confirm that the rules you need are already in the activated state.
2. If you are unsure of the current status, first enter `'<ListRule>'` in the conversation input box, then press `Ctrl+J` or `Ctrl+]` to see which rules are shown as `✅ Activated`.
3. Start the general agent or continue the current session.
4. Enter and submit the task normally; the system automatically brings the currently activated rules into this round of processing.

## Prompts and Feedback You Will See

- After startup it will not ask you to paste the rule content manually again.
- If you subsequently view the rule status, the system displays the rule name, content preview, file path, and whether it is activated.
- Activated rules take effect as the default constraints of the current session.

## Notes

- Only rules that have already been activated are automatically brought into the current task environment.
- If you suspect the result does not meet expectations, first check whether you have activated a rule that does not fit the current task.
- It is recommended to check the rule status once before formally executing a complex task, to avoid starting work with the wrong rules.
