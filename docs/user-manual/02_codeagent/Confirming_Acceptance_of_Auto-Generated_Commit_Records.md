# Confirming Whether to Accept the Auto-Generated Commit Records Before Committing

## When to Use

When the system has already automatically generated a set of commit records based on this task, but you still want to take a look before finalizing and decide whether to accept them, you can make the choice directly at the commit confirmation stage.

## Steps

1. Start the code agent and complete a task that will modify code.
2. After the system automatically organizes this round's commit records, view the commit history summary listed in the terminal.
3. When the terminal asks whether you accept the above commit records, enter a confirmation or rejection as needed.
4. If you accept, the system continues to organize the final commit; if you reject, the system enters the subsequent rejection branch.

## Prompts and Feedback You Will See

- The system first lists the detected commit records, letting you see brief information for each commit.
- It then shows a confirmation prompt asking whether to accept the above commit records.
- If you accept, the system continues the later final organization and re-commit flow.
- If you do not accept, the system does not force the use of these commit records directly, but switches to the subsequent reset branch.

## Notes

- What is confirmed here is "whether to accept the commit records organized automatically this time", not simply confirming whether the task is done.
- If you are not satisfied with the commit granularity, commit message, or intermediate result, you can reject at this step.
- Before rejecting, it is recommended to carefully read the commit summary listed in the terminal to avoid mistakenly passing it.
