# Manually Triggering Task Analysis Directly

## When to Use

When a task has already been done and you want the system to immediately summarize this work, save memory, or distill experience, you can confirm the execution of task analysis as prompted after the task ends.

## Steps

1. First bring the current task to a clear ending point, letting the system finish this round of response.
2. After the task ends, watch whether the system pops up a confirmation prompt: `Task completed. Perform task analysis (save memory, generate methodology, etc.)?`
3. If you want to start the analysis right away, confirm to continue; if you do not want to do analysis now, choose to skip.
4. If you continue, the system then asks: `Task completed. Are you satisfied?`
5. If you choose dissatisfied, the system further prompts: `Please provide improvement feedback (press Enter directly to skip)`, and you can enter supplementary opinions and submit.

## Prompts and Feedback You Will See

- Task analysis is not triggered immediately by entering a sentence in the ordinary conversation at any time; instead, a confirmation prompt appears after the task completes.
- You will first see: `Task completed. Perform task analysis (save memory, generate methodology, etc.)?`
- Then you may see:
  - `Task completed. Are you satisfied?`
  - `Please provide improvement feedback (press Enter directly to skip)`
- If you confirm execution, the system continues the subsequent analysis, memory saving, or experience distillation flow.

## Notes

- This capability is more suitable when the task has already come to a pause, not for triggering frequently midway.
- The currently confirmed user-visible entry point is the "confirmation prompt after task completion", not a standalone built-in command in the ordinary input box.
- If you skip this step, this round of the task still ends; it just does not continue with the subsequent analysis.
