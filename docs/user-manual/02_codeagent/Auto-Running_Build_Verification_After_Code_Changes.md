# Auto-Running Build Verification After Code Changes

## When to Use

When you want the system to immediately try to build or compile after code changes are complete, so as to discover obvious compilation errors, build failures, or environment mismatch problems as early as possible, the code agent automatically runs build verification under suitable conditions.

## Steps

1. Start the code agent in the project directory and submit a task that will modify code.
2. Wait for the system to complete this round of changes and the automatic commit.
3. If the current session allows build verification, the system automatically starts this step, and you do not need to manually enter a compile command.
4. View the build verification result in the terminal, then decide whether to continue fixing or end this round of the task.

## Prompts and Feedback You Will See

- When build verification starts, the terminal indicates that a compilation check is in progress, with a summary of the files involved in this round.
- If verification passes, the final result shows that build verification passed and marks the time taken; sometimes it also shows the detected build system type.
- If build verification is turned off, or the current project has already remembered to "only do basic static checks", the system will not continue with full build verification, but takes the subsequent alternative flow.
- If the build verification process itself errors out, the main flow will not be interrupted directly because of it.

## Notes

- This is an automatic verification step after code changes, not a command manually called at any time during the input stage.
- Whether build verification is executed also depends on the current environment, configuration, and project state; not all repositories will necessarily perform this step fully.
- Passing build verification does not mean all functions are fine; it is mainly used to discover compilation or build-level errors as early as possible.
