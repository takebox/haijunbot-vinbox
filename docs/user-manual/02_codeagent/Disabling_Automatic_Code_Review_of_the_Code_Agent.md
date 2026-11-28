# Disabling Automatic Code Review of the Code Agent

## When to Use

When you only want the code agent to complete the code analysis, modification, and basic wrap-up flow, and do not want it to continue into the automatic code review and fix loop after modification, you can disable automatic code review at startup.

## Steps

1. Open a terminal in the project directory.
2. Enter a command like: `hca --disable-review --task "your task"`
3. After pressing Enter, the system executes this code task in the normal way.
4. After the code modification is complete, the system skips the automatic code review flow and directly enters the subsequent result organization and ending stage.

## Prompts and Feedback You Will See

- After disabling, the system no longer enters the "which round of code review" confirmation and loop prompts.
- The task still continues to perform code modification, commit result organization, and other subsequent flows; it does not completely stop task execution.
- If the current task actually does not produce code changes, it would not enter the review stage anyway.

## Notes

- This parameter only affects the "automatic review flow after code modification is complete" and does not affect you normally initiating a code task.
- If what you are currently handling is a high-risk change, disabling automatic review reduces the system's secondary check step; it is recommended to use it only when you clearly know why you want to disable it.
- This is a launch parameter and is suitable for taking effect temporarily for this task; the next time you do not pass it, it still returns to the default behavior.
