# Auto-Running Static Checks and Showing Auto-Fix Suggestions After Code Changes

## When to Use

When you want to check format, syntax, style, or static problems immediately after code changes are done, and to get directly executable auto-fix suggestions as a priority, the code agent automatically runs static checks under suitable conditions.

## Steps

1. Start the code agent and submit a task that will modify code.
2. Wait for the system to complete this round of changes and the related verification.
3. If the current file type supports static check tools, the system automatically runs these checks, and you do not need to execute them one by one manually.
4. View the static check results in the terminal; if the system gives auto-fix suggestions, handle them according to the suggestions first.

## Prompts and Feedback You Will See

- This is triggered automatically after modification and does not require entering extra commands.
- If the static checks pass, the result shows that the static scan passed.
- If problems are found, the system organizes them into subsequent fix prompts, and gives auto-fix command suggestions as a priority when available.
- If the corresponding tool is missing from the current environment, you may see a result saying the related tool cannot run; this will not necessarily interrupt the main flow.
- If the earlier full build verification has already failed and you have not yet switched to the basic static check route, the system may skip this step to avoid stacking errors repeatedly.

## Notes

- Auto-fix suggestions are usually the preferred way to handle things, but that does not mean all problems can definitely be fixed in one go.
- Different languages and file types match different static check tools, and not all files will get the same kind of check.
- If your environment does not have the corresponding tool installed, you may see situations like "tool not installed" or the command being unavailable in the terminal; this is an environment problem, not necessarily a code problem.
