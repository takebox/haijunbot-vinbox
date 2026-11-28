# Dispatching Code Agent Tasks to a tmux Window

## When to Use

When your code task takes a long time to execute, or you want to throw the current task into a new tmux window to run asynchronously and then return to the current window to continue other work, you can use dispatch mode.

## Steps

1. First enter a terminal window that is already running in a tmux session.
2. In the current project directory, enter a command like the following, then press Enter:

   `hca --dispatch --task "refactor the cache cleanup logic and check related tests"`

3. The system immediately tries to dispatch this task to run in a new tmux window.
4. After the current command is successfully dispatched, it exits directly and does not stay in the original window to continue the task.
5. You can switch to the newly created tmux window to view the subsequent running process.

## Prompts and Feedback You Will See

- When dispatch starts, the terminal indicates that it is dispatching the task to a new tmux window.
- If dispatch succeeds, you see a prompt that the task has been successfully dispatched to a new tmux window, and then the current process ends.
- If you only write `--dispatch` without providing `--task` at the same time, the system reports an error directly and indicates that this parameter must be used together with `--task`.
- If the current environment cannot create a tmux window or pane, the system indicates that dispatch failed and asks you to check the tmux configuration.

## Notes

- This feature is only meaningful in a tmux environment; if you did not start it inside a tmux session, it is usually not suitable to use this way.
- `--dispatch` needs to be used together with `--task`; you cannot start it first and then add the task later.
- After a successful dispatch, the current window does not continue to show the task execution process; you need to switch to the target tmux window to view the running status.
- If the task content is very long and not suitable to write directly on the command line, you can use a task file instead, or use `hcad` directly.
