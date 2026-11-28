# Automatically Appending Past Experience to the Current Task Context When Methodology Is Enabled

## When to Use

When the system has found experience from similar past issues and you want this experience to directly participate in the reasoning of the current task, rather than being placed only in external notes, you can let the methodology be automatically appended to the current context.

## Steps

1. First enter a startup mode or session where methodology is already enabled.
2. Enter the current task normally and submit it in the usual way.
3. The system first processes your current input, then automatically retrieves the corresponding historical experience.
4. After finding suitable experience, the system directly appends this content to the current task context as a reference for subsequent execution.

## Prompts and Feedback You Will See

- The appended experience enters the current context in a form like "The following is execution experience for similar past issues, for reference:".
- In subsequent responses and execution, the agent naturally refers to this experience.
- You do not need to manually copy and paste past practices.

## Notes

- This capability depends on methodology already being enabled at the current entry point; if it is not enabled, historical experience will not be appended automatically.
- What is appended automatically is "reference experience", not a mandatory rule.
- If you find that the historical experience does not fit the current problem, you should clearly correct the direction in the current task in time.
