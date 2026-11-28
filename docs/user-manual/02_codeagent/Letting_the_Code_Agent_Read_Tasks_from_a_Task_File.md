# Letting the Code Agent Read Tasks from a Task File

## When to Use

When your code task is very long, or you want to hand the same task description to the code agent repeatedly, you can write the task into a file, then let the code agent read it directly from the file.

## Steps

1. First prepare a text file in the project directory and write the task description into it.
2. In the terminal, enter: `hca --task-file your-task-file-path`
3. After pressing Enter, the system reads the file content and uses the content in the file as this task description.
4. If you also want to run in non-interactive mode at the same time, you can add `-n` to the command.
5. Wait for the task to finish executing, and view the result in the terminal.

## Prompts and Feedback You Will See

- If the file can be read normally, the system starts executing directly, and you do not need to manually paste the same task content again.
- If the file cannot be read, the system reports an error and gives a prompt like: `❌ Error: cannot read task description from file: ...`
- If you pass both `--task` and `--task-file`, the system directly refuses to execute and prompts: `❌ Error: cannot use --task and --task-file parameters at the same time`
- If the task file stores structured task content, the system automatically organizes the task description, background information, and additional information within it before executing.

## Notes

- `--task-file` suits long tasks, templated tasks, and batch processing scenarios.
- Do not use `--task` and `--task-file` at the same time; these two input methods are mutually exclusive.
- If the file contains background and supplementary explanations besides the main task, the system brings them into the current task as well; therefore when writing the file it is best to organize this content clearly.
