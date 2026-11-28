# Auto-Truncating Overly Large diffs During Code Review to Fit the Context Window

## When to Use

When a single change involves too many files or the diff content is too large and is no longer suitable to be fully inserted into a single code review, the system automatically truncates and compresses the diff display, avoiding the review stage failing because the content is too long.

## Steps

1. Run the code agent normally and submit a task that will produce relatively large changes.
2. When the system enters the code review stage, if this round's diff is too large, the system automatically switches to the truncated diff to continue the review.
3. You do not need to manually trim the patch, nor do you need to re-enter commands.
4. View the truncation prompt in the terminal, then use the file list to continue judging this round's review result.

## Prompts and Feedback You Will See

- This happens automatically during the code review stage and does not require entering extra commands.
- If the diff is truncated, the terminal clearly indicates that the current review uses a trimmed diff.
- The prompt usually explains the size of the original diff, how much content is currently shown, and which files the full modification involves.
- Even if the diff is not fully expanded, the system still continues this round of review, rather than giving up directly because the content is too large.

## Notes

- The purpose of truncation is to let the system continue the review even when the context window is limited; it does not mean the unshown parts are completely unimportant.
- If your change is especially large, after seeing the truncation prompt, it is best to also view the full patch yourself with Git tools.
- This kind of situation is common in large refactorings, large batches of file adjustments, or tasks that modify many files at once.
