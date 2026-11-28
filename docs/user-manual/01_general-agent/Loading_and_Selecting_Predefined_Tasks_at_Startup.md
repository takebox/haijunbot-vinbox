# Loading and Selecting Predefined Tasks at Startup

## When to Use

If you frequently perform repetitive work, such as fixed inspection flows, common analysis tasks, or standardized operations, you can select from the predefined task list at startup rather than rewriting the full task each time.

## Steps

1. First prepare the predefined task list, then start the general agent.
2. After startup, the system first lists the number and name of the selectable tasks.
3. If you enter the filter-style selection interface, you will see the prompt: `Select a task number (ESC to skip) >`
4. At this point you can directly select a number; if you press `ESC`, you skip the predefined task selection.
5. If the current environment does not enter the filter interface, the system instead uses ordinary input and prompts: `Please select a task number (0 or press Enter directly to skip predefined tasks):`
6. After selecting, the system takes the corresponding task content as the starting point of this execution and continues the subsequent flow.

## Prompts and Feedback You Will See

- The system first prints the predefined task list and displays the numbers.
- You may see one of two selection methods:
  - `Select a task number (ESC to skip) >`
  - `Please select a task number (0 or press Enter directly to skip predefined tasks):`
- If you choose to skip, it does not report an error; instead, it continues into ordinary task input or the subsequent flow.
- If you select a task, the system continues by asking whether you want to add extra notes.

## Notes

- Only predefined tasks that have already been prepared will appear in the list.
- If there is no suitable task in the list, just skip; you do not have to force a selection.
- The task name is only the entry point; the actual execution content still depends on the specific task you select and the subsequent supplementary notes.
