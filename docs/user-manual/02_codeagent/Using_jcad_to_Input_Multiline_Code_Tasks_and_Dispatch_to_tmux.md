# Using hcad to Interactively Input Multiline Code Tasks and Dispatch to tmux

## When to Use

When your task description is very long, containing multiple paragraphs of background, constraints, and goals, and you want to dispatch the task to tmux to execute directly after you finish inputting, you can start `hcad`'s interactive input mode directly.

## Steps

1. First enter the project directory, and make sure the terminal environment you are currently using can dispatch tmux tasks normally.
2. Enter `hcad`, then press Enter.
3. The terminal shows a multiline input prompt; enter the complete task content directly following the prompt.
4. During input, a normal Enter is used for a newline; after the input is complete, press the confirm shortcut in the prompt to submit the whole block of content.
5. After submission, the system first writes this multiline task into a temporary file, then automatically dispatches it to the code agent to execute.
6. After dispatching is complete, go to the corresponding tmux window or pane to view the subsequent running process.

## Prompts and Feedback You Will See

- After entering interactive input, the terminal clearly prompts: `Please enter the task content (Ctrl+J/Ctrl+] to confirm, Enter for newline)`.
- After submission, the terminal shows a prompt that the temporary file has been created, indicating that the multiline task has been saved and is ready to be dispatched.
- If you end directly without entering anything, the system indicates that this input is empty and exits directly, and does not continue to dispatch the task.
- If dispatching fails, the terminal directly shows the error information.

## Notes

- This method suits long task descriptions; if you are only dispatching a one-sentence short task, writing `hcad "your task"` directly is more convenient.
- When submitting multiline input, you do not end with a normal Enter, but with the confirm shortcut in the prompt; a normal Enter only continues the newline.
- The system temporarily saves your task content before dispatching, so you will see a temporary file creation prompt; this is normal.
- If the current environment cannot dispatch tmux tasks normally, this method will also fail; in that case, first confirm that the tmux environment is available.
