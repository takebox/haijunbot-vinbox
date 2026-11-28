# Setting the Maximum Review Iterations for the Code Agent

## When to Use

When you want automatic code review not to extend indefinitely, or you want to explicitly limit "how many more rounds can be fixed after the review finds problems", you can set the maximum review iterations when starting the code agent.

## Steps

1. Open a terminal in the project directory.
2. Enter a command like: `hca --review-max-iterations 3 --task "your task"`
3. After pressing Enter, the system first executes the normal code task.
4. If the task produces code modification, when it later enters the review stage, the system controls the number of loop rounds according to the upper limit you set.
5. Before each round begins, the system first asks whether you want to continue the current round of code review.

## Prompts and Feedback You Will See

- Before each review round begins, you see a confirmation prompt like "Perform code review round 1?".
- While the review is in progress, the system shows the current round, for example "Code review loop - round 1/3".
- If a certain round has already passed, the system indicates that the current round review passed and ends the subsequent loop.
- If there are still problems after reaching the maximum number you set, the system stops continuing the review and no longer infinitely appends the next round.
- When you set the maximum number to `0`, it means no upper limit, and the system handles it in infinite mode, but before each round begins it still first asks whether you want to continue.

## Notes

- This parameter is only meaningful when automatic code review is enabled; if you have also disabled automatic review, this upper limit setting will not take effect.
- The maximum iterations control the upper limit of the "review and fix loop", not the total number of rounds of the whole task.
- If you want to reduce time consumption, you can set a smaller upper limit; if you value repeatedly polishing the result more, you can raise the upper limit, or use `0` to enter infinite mode.
