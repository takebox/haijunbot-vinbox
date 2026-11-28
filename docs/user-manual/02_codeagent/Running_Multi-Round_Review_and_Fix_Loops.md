# Running Multi-Round Code Review and Fix Loops

## When to Use

When you want the code agent, after completing the first round of modification, not to stop immediately, but to continue checking whether this change truly satisfies the requirement and whether there are still obvious problems, you can use the default code review and fix loop.

## Steps

1. Start the code agent in the project directory and submit a task that will produce code changes.
2. Wait for the system to complete the first round of code modification.
3. If automatic code review is not currently disabled, the system enters the code review flow after modification.
4. When the review finds problems, the system lists the problems and continues into the fix stage.
5. After the fix is complete, if review is still allowed to continue, the system enters the next review round again, until it passes, reaches the upper limit, or you actively stop it.

## Prompts and Feedback You Will See

- Code review is entered automatically after modification is complete, and you do not need to enter a separate "start review" command.
- At the start of each round, the terminal shows which round of code review is current.
- If the review passes, the terminal indicates that this round of code review passed and gives a brief summary.
- If the review does not pass, the system lists the problems found one by one, including the problem type, location, and fix suggestion, then continues the subsequent fix flow.

## Notes

- This capability happens by default after code changes; if you do not want to use it, you can disable automatic code review at startup.
- Its goal is to continuously approach "the requirement is complete and the changes are reasonable", so it suits code tasks that need quality control.
- If this round actually does not produce code changes, the review loop usually does not continue.
