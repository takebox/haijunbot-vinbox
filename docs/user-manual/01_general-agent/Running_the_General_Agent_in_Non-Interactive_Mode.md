# Running the General Agent in Non-Interactive Mode

## When to Use

Suitable for scripted execution, unattended processing, or scenarios where you explicitly do not want to manually enter content during the run.

## Steps

1. Add `-n` or `--non-interactive` at startup.
2. At the same time you must use `-T` or `--task` to provide the task content directly.
3. After submitting the command, the system enters execution directly and no longer waits for you to continue entering input in the terminal.

## Prompts and Feedback You Will See

- If you only enable non-interactive mode but do not provide a task, the system directly reports an error: non-interactive mode must be used with `--task`, and then exits.
- If the arguments are complete, the system continues to start and immediately executes the task you passed in.
- In this mode, the interactive multiline input prompt does not appear.

## Notes

- The most important precondition of non-interactive mode is that the task must be written completely at startup.
- This method is not suitable for tasks that need to be continuously supplemented with notes midway.
- If you only want to reduce interaction but may still modify requirements temporarily, it is recommended to keep using the interactive approach.
