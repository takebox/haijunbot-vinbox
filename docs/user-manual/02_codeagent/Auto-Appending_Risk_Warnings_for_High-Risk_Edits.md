# Auto-Appending Risk Warnings for High-Risk Edits

## When to Use

When this round of changes has a large impact scope, many interface changes, and widely affected tests, the system automatically marks this edit as high-risk and reminds you to review it carefully.

## Steps

1. Run the code agent in the project directory and submit a code modification task.
2. If this round of changes is judged to be a high-risk edit, the system automatically appends reminder information in the subsequent results.
3. Based on these reminders, check the named affected files, interface changes, and related tests first.

## Prompts and Feedback You Will See

- This happens automatically and does not require entering extra commands.
- For high risk, the system adds an obvious risk warning in the subsequent results, reminding you that this edit has a large impact scope.
- The prompt content usually tells you the number of affected files, the number of interface changes, and the number of related tests, helping you judge which parts to review carefully.

## Notes

- The point of this kind of prompt is not to stop you from continuing, but to remind you not to look only at the immediate changes and to check the surrounding impact as well.
- If you are already doing cross-module refactoring, large-scale interface adjustments, or replacement of shared capabilities, seeing a high-risk prompt is normal.
- After the risk warning appears, it is best not to rely only on "the code can run"; it is best to also do targeted regression checks.
