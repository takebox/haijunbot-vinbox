# Directly Executing Tasks Passed from the Command Line

## When to Use

Suitable for batch processing, script invocation, or when you have already written the task completely and do not want to enter the interactive input interface again.

## Steps

1. When starting the general agent, pass the task content directly via `--task`.
2. After submitting the command, the system will not ask you to enter a task again.
3. The startup stage first outputs a prompt explaining that it is currently executing the task passed from the command line.
4. After that the agent immediately begins processing.

## Prompts and Feedback You Will See

- The system prints a message indicating it is executing the task you passed from the command line.
- The multiline input prompt `Please enter your task (Ctrl+C to exit)` does not appear.
- If the task starts normally, it means the command-line task has been received successfully.

## Notes

- This method is suitable for a one-off, clearly defined task, not for scenarios where requirements need to be added while it runs.
- If the task content is very long and complex, it is recommended to check whether the command is correct first before executing.
- If you still need to adjust the task frequently afterwards, it is recommended to switch to interactive input.
