# Using the General Agent to Execute Tasks Interactively

## When to Use

Suitable for tasks where you still need to add requirements while executing, such as debugging problems, clarifying requirements step by step, and correcting direction while watching results.

## Steps

1. Start the general agent directly in the terminal, without a one-shot task argument, and without enabling non-interactive mode.
2. After startup it enters the multiline input interface, with the prompt: `Please enter your task (Ctrl+C to exit)`
3. Write your task content in the input area.
4. After entering, press the submit shortcut shown in the bottom toolbar hint. The default text is configured as submit keys such as `Ctrl+J`, `Ctrl+]`.
5. After submitting, the agent immediately begins processing your task.

## Prompts and Feedback You Will See

- The left side of the input box shows `👤 >`
- The bottom toolbar shows shortcut hints, including:
  - `@` file completion
  - the submit shortcut (such as `Ctrl+J/Ctrl+]`)
  - `Ctrl+O` copy history information
  - `Alt+T` enter the terminal
  - `Ctrl+X` exit the program
  - `Ctrl+C/D` cancel
- The first time you use multiline input, the system also displays an extra explanation of the submission method.

## Notes

- If you press `Ctrl+C` to cancel the current input, this task is not submitted.
- If you have already written the task very completely, executing it directly as a one-shot task is usually faster.
- Interactive mode is more suitable for scenarios that need multiple rounds of supplementary notes.
