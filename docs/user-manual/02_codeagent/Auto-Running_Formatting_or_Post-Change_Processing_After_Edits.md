# Auto-Running Formatting or Post-Change Processing After Code Changes

## When to Use

When you want the code agent to conveniently complete formatting, automatic fixes, or other post-change processing steps after modifying files, reducing the number of times you manually re-run tools, this automatic processing capability is very helpful.

## Steps

1. Start the code agent and submit a task that will modify code.
2. If the subsequent flow enters the final commit organization stage, the system automatically checks whether the files changed in this round match available post-processing commands.
3. For matched files, the system automatically executes formatting or other post-processing actions.
4. After processing is complete, the system continues to organize the final commit result.

## Prompts and Feedback You Will See

- This happens automatically; you do not need to write "please format it again" separately in the task.
- When a file is processed successfully, the terminal indicates that the file has been processed, with the name of the tool used.
- If multiple files are processed in this round, it will also indicate at the end how many files were processed in total.
- If a processing command fails, times out, or the tool does not exist, the system gives a warning, but usually will not directly interrupt the whole main flow because of it.

## Notes

- This step usually happens in the final commit organization flow, and is not executed immediately every time a small change is generated.
- Whether automatic post-processing runs depends on whether the current file type matches an existing rule, and whether the current environment has the corresponding tool.
- If your project has special requirements for formatting or automatic fixes, you can continue to extend the behavior of this step with custom configuration.
