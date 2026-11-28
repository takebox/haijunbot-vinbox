# Turning Build Failure Errors into Subsequent Fix Hints

## When to Use

When the code has been modified successfully but build verification did not pass, the system does not simply print an error and finish, but organizes the build failure information into subsequent fix hints, pushing the next round of modification to converge in the right direction.

## Steps

1. Start the code agent and submit a code task.
2. If build verification after this round of modification fails, first view the failure summary shown in the terminal.
3. If you did not choose to disable build verification, the system automatically converts this error information into a reference for the next fix step.
4. Continue to let the system execute the subsequent fix, or manually adjust your task description based on this error information.

## Prompts and Feedback You Will See

- After the build fails, the terminal shows a failure prompt and error summary.
- If you did not switch to "only do basic static checks", the system continues to use these errors as an important reference for the subsequent fix.
- The effect of doing this is: the next round of fix no longer just continues blindly, but prioritizes converging on the problems exposed by this build failure.

## Notes

- This step automatically connects to the subsequent fix flow; you do not need to additionally copy and paste the error log to the system.
- If the error information is especially long, the terminal usually only shows a summary, rather than fully expanding it without limit.
- The quality of this kind of fix hint depends on whether the current build error is clear; if the error itself comes from a missing external environment, you may still need to supplement the environment condition description later.
