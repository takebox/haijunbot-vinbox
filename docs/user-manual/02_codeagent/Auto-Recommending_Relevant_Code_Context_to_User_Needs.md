# Auto-Recommending Relevant Code Context Based on User Needs

## When to Use

When your task involves multiple files or multiple modules, or the requirement you give is relatively long, the system tries to automatically supplement more relevant code context before formal processing, helping subsequent analysis and modification focus on the key positions faster.

## Steps

1. Open a terminal in the project directory.
2. Start the code agent in interactive or non-interactive mode, for example enter `hca`, or enter `hca -n --task "fix order timeout cancellation logic"`.
3. Submit your task content normally; you do not need to enter an extra command like "recommend context".
4. After receiving the task, the system automatically tries to recommend more relevant code context based on your current needs, then continues the subsequent analysis and modification flow.

## Prompts and Feedback You Will See

- This happens automatically and does not require entering extra commands.
- In the task description area you see, context information supplemented by the system may be included, used to help subsequent processing focus more accurately on related files and modules.
- If the current task is very simple, or the system does not find particularly valuable supplementary context, the subsequent flow also continues as usual and will not be interrupted because there is no recommendation result.

## Notes

- The role of this capability is to help the system find related code faster; it is not the same as filling in the business goal for you; your task description should still be written as clearly as possible.
- It is an automatic auxiliary behavior before execution, not a command you trigger separately at any time during the run.
- If you have already clearly given very specific files, modules, or goals, the context recommended by the system usually only plays a supplementary role.
