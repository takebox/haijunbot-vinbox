# Verify Refactoring Logical Consistency

## Use Cases

When you complete a round of refactoring and want to confirm whether the new code still preserves the original logic, rather than only looking at code style, file structure, or naming changes, you can use the built-in refactoring check expert to perform a logical consistency check.

## Steps

1. In the task, clearly tell the system: use the refactoring check expert.
2. Provide a commit number that can be used for comparison and the refactoring scope you want to check.
3. If needed, then state the functional paths or risk points you particularly focus on.
4. If you want to directly start the task, you can use a description like: `Please use the refactoring check expert to compare the differences between the current implementation and commit abc123, focusing on whether the user login, permission judgment, and exception return logic remain consistent.`
5. After submitting the task, wait for the system to read the content of the corresponding version and perform a comparative analysis of the current logic.
6. View the final conclusion to confirm whether it is "logic consistent" or "inconsistency exists".

## Prompts and Feedback You Will See

- The system reads the accessible historical version content based on the commit number you provide.
- When needed, it also reads the code context to assist the judgment.
- Finally it gives a logical consistency conclusion with the basis for the analysis.
- If the commit number cannot be accessed or the context is insufficient, the system usually first prompts the precondition problem rather than directly giving an arbitrary conclusion.

## Notes

- This is an expert-type task entry point, not a fixed CLI command.
- The core goal is to verify "whether the logic is consistent", not to compare whether the text differences are the same.
- The input premise is that the repository history is accessible and the commit number you provide is valid.
- If the refactoring scope is large, it is recommended to check by module to avoid an overly general conclusion at once.
- It is best to specify the three pieces of information "baseline version + current scope + key functional paths"; otherwise the analysis result tends to remain at a generalized conclusion.
