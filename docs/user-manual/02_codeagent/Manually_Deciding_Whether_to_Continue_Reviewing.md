# Manually Deciding Whether to Continue Reviewing Before Each Code Review Round

## When to Use

When you do not want the system to run through the whole review loop in one go, but want to decide for yourself before each round begins whether to continue, you can make the choice directly in the round confirmation prompt.

## Steps

1. Start the code agent and submit a task that will modify code.
2. After entering the code review flow, pay attention to the confirmation prompt before each round begins.
3. When the terminal asks whether to perform the next code review round, choose to continue or stop according to your needs.
4. If you choose to continue, the system starts that round of review; if you choose not to continue, the current review loop ends immediately.

## Prompts and Feedback You Will See

- Before each review round begins, the system shows a confirmation prompt like "Perform code review round N?".
- If you confirm continuing, the system immediately shows the information that this round of code review has started.
- If you refuse to continue, the terminal indicates that you have stopped continuing code review at the current round, and this round's flow ends immediately.
- In non-interactive mode, the default choice of this confirmation is usually different from interactive mode, so it is easier to continue executing during automated runs.

## Notes

- What is decided here is "whether to continue to the next review round", not "whether to accept the final code result".
- If you have already seen the previous round's result and confirmed there is no need to continue, you can stop directly to avoid running extra invalid rounds.
- In interactive mode, the system usually does not continue on your behalf by default, so pay attention to the confirmation prompt in the terminal.
