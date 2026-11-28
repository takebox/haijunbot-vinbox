# Auto-Fixing Malformed JSON When Code Review Results Are Malformed

## When to Use

When the code review stage has already started but the review result output format does not meet the system requirements, the system automatically tries to fix the result format, avoiding directly interrupting the whole review loop because of a format problem.

## Steps

1. Start the code agent and let the task enter the code review flow.
2. If the result format of a certain review round is incorrect, the system automatically enters the format repair step.
3. This step does not require you to manually retry, nor do you need to organize the JSON yourself.
4. If the repair succeeds, the system continues to use the repaired result to judge whether this round passes; if several consecutive repair attempts all fail, the system restarts this review round.

## Prompts and Feedback You Will See

- When there is a format problem, the terminal indicates that it is trying to repair the JSON format, and shows which repair attempt this is.
- If the repair succeeds, the terminal indicates that the JSON format was repaired successfully, and the current round continues.
- If the repair still fails after multiple attempts, the terminal indicates that the JSON format repair failed, and re-runs the current round of code review.
- This kind of problem usually does not terminate the whole task directly, but instead tries self-recovery first.

## Notes

- This is an automatic recovery mechanism inside the review flow, not a command for users to manually call during the normal input stage.
- If you see this kind of prompt, it means the current problem is mainly an abnormal review result format, and does not necessarily mean the code itself has a more serious problem.
- If this situation occurs frequently in the same task, it usually means the review content of this round is too complex, and you can consider splitting the task smaller later.
