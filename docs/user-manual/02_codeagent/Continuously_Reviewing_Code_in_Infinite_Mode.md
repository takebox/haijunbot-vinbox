# Continuously Reviewing Code in Infinite Mode

## When to Use

When you want the system not to limit the number of review rounds in advance, but to continuously run the "review -> fix -> re-review" loop until the review passes or you actively stop it, you can use infinite mode.

## Steps

1. When starting the code agent, set the maximum number of code review iterations to `0`.
2. Normally submit a task that will modify code.
3. After the modification is complete, the system enters the code review loop and continues running in infinite mode.
4. Before each round begins, you can still decide whether to continue to the next review round according to the prompt.
5. Only when the review passes, or you actively refuse to continue, does infinite mode end.

## Prompts and Feedback You Will See

- After entering this mode, the terminal clearly shows that the current round is in infinite mode.
- At the start of each round, you see a round prompt with an "infinite mode" note.
- After the review passes, the system indicates passing and ends, just like normal mode.
- If you choose to stop continuing midway, the system immediately stops subsequent rounds.

## Notes

- Infinite mode is not "running forever unattended", because before each round begins there is usually still a confirmation asking whether to continue.
- It suits complex refactorings, problems with high quality requirements, and problems that need multiple rounds to converge gradually.
- If you are only handling very small changes, you generally do not need to specifically use infinite mode.
