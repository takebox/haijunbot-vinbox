# Auto-Detecting Risky Large Deletions and Reverting Changes if Needed

## When to Use

When a single change involves a large-scale deletion of code, the system automatically appends a risk judgment, avoiding keeping dangerous changes directly because key logic was mistakenly deleted.

## Steps

1. Start the code agent normally and submit your code task.
2. If a large number of code deletions appear after this round of changes, the system automatically enters an extra risk judgment flow.
3. This step does not require you to manually enter a command; the system automatically judges whether these deletions are reasonable based on the current patch preview.
4. If the judgment result considers the risk too high, the system automatically reverts this round of changes; if the judgment result considers it reasonable, it continues the subsequent flow.

## Prompts and Feedback You Will See

- When a large number of deletions is detected, the system clearly indicates that it is judging whether these deletions are reasonable.
- If the system judges the deletions to be reasonable, it gives a confirmation prompt, then continues the subsequent commit flow.
- If the system judges the deletions to be unreasonable, the terminal indicates that this change has been reverted, along with a per-file patch preview to help you understand what was just reverted.
- If the judgment process itself fails, the system handles it in a more conservative way, prioritizing avoiding keeping high-risk deletions directly.

## Notes

- This is an automatic protection mechanism, not a command you can manually call at any time during the normal input stage.
- A reverted situation usually means the system considers the current deletion scale too large or untrustworthy; you should re-describe the task scope to avoid having the system mistakenly delete a large amount of code.
- If your task is itself large-scale simplification, deleting old modules, or removing deprecated logic, please state the purpose of the deletion clearly in the task description, which makes it easier for subsequent judgments to align with the real goal.
