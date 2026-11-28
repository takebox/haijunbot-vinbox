# Check Refactoring Consistency via Commit

## Use Cases

When you already know the commit to compare against and want to check explicitly, based on that historical version, whether the refactored code still preserves the original logic, you can use the commit as the primary input to start a refactoring consistency check task.

## Steps

1. Prepare an accessible commit identifier.
2. In the task, clearly state: please compare the current refactored implementation based on this commit.
3. Specify the module, file, or feature scope you want to check.
4. If you want to give a clear task directly, you can use a description like: `Please compare the current refactoring result of the src/payment module based on commit abc123, focusing on whether the order creation, payment callback, and exception handling logic remain consistent.`
5. After submitting the task, wait for the system to read the code content of the target commit and perform a logical comparison with the current implementation.
6. Based on the output result, judge whether this refactoring preserved the original functional logic.

## Prompts and Feedback You Will See

- The system first reads the code content corresponding to the specified commit.
- After the comparison is complete, it outputs a conclusion about whether the logic is consistent.
- The result usually emphasizes functional consistency and behavioral consistency rather than formatting or style differences.
- If the commit is inaccessible or the repository history is incomplete, the system prompts that the preconditions are insufficient.

## Notes

- This kind of check depends on the repository history being accessible, so the commit must be valid.
- If your goal is only a general refactoring review, you can also directly use the "verify refactoring logical consistency" approach without focusing on a particular commit.
- The focus of the check is functional logic, not whether the code looks the same.
- The clearer the specified scope, the more credible the analysis conclusion usually is.
- It is best to provide both the commit and the current check scope; if you only give the commit without saying which module to focus on, the output tends to be too broad.
