# Automatically Triggering Task Analysis After Task Completion

## When to Use

When you want the system to automatically enter a wrap-up analysis stage after the task is done, helping to organize results and review the process, rather than just giving a one-line "done", you can turn on automatic task analysis.

## Steps

1. First enter a session or startup mode where the task analysis capability is already enabled.
2. Submit and complete the task normally.
3. After the task ends, the system shows a confirmation prompt: `Task completed. Perform task analysis (save memory, generate methodology, etc.)?`
4. If you confirm to continue, the system enters the task analysis flow; if you skip, this round of analysis ends directly.

## Prompts and Feedback You Will See

- After the task completes, the system does not just stop at a closing remark; instead, it first shows: `Task completed. Perform task analysis (save memory, generate methodology, etc.)?`
- If you continue, you may later also see: `Task completed. Are you satisfied?`
- If task summary is also enabled, you will usually also see task summary content output.
- Automatic analysis is suitable after a task ends to help you further distill results, experience, and follow-up actions.

## Notes

- Whether automatic task analysis runs depends on whether the task analysis feature is enabled.
- The currently confirmed user-visible entry point is the confirmation prompt after task completion, not a standalone command in the ordinary input box.
- If you just want to finish quickly without entering extra analysis, you should check whether the current config has this capability enabled.
