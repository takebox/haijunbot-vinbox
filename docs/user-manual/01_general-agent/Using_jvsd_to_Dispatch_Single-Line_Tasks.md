# Using hjbd to Dispatch Single-Line Tasks Directly

## When to Use

When you just want to quickly throw a short task at the system without first entering the full interactive flow, you can use `hjbd` to dispatch a single-line task directly.

## Steps

1. Enter on the command line: `hjbd "your task"`.
2. If this is not an existing file path, the system automatically prepends the built-in rule entry and the "original requirement" prefix before the task.
3. For a single-line task, the system hands the content directly to `hjb -n --task` for processing.
4. After submitting, wait for the execution result.

## Prompts and Feedback You Will See

- `hjbd` is a convenience wrapper around `hjb`, suitable for quick dispatch.
- If the content passed in is empty, the system directly reports an error and exits.
- If the `hjb` command cannot be found on this machine, the system prompts: `❌ Error: 'hjb' command not found, please make sure haijunbot is installed correctly`.

## Notes

- Single-line mode is suitable for short tasks, not for complex long descriptions.
- If your content is itself an existing file path, the system treats it as a task file rather than ordinary text.
- When you want to enter multiple paragraphs of description, it is recommended to switch to the multiline approach.
