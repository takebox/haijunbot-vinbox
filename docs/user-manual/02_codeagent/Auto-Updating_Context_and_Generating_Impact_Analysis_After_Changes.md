# Auto-Updating Code Context and Generating an Impact Analysis Report After Code Changes

## When to Use

When what you modify is an interface, a public function, cross-module logic, or other content that easily affects multiple files, the system automatically updates the code context after the change and generates an impact analysis, helping you judge where further checking may be needed.

## Steps

1. Start the code agent in the project directory and submit a task that will modify code.
2. Wait for the system to complete this round of changes.
3. Once a file is detected to have been modified, the system first automatically updates the current code context, then continues to analyze which files, symbols, or tests these changes may affect.
4. View the impact analysis result in the terminal, and continue to judge whether supplementary modification or additional verification is needed.

## Prompts and Feedback You Will See

- This is triggered automatically after code modification and does not require entering a separate command.
- The terminal first indicates that it is updating the code context, then indicates that a change impact analysis is in progress.
- The analysis result is summarized into the final output, usually indicating the files, interfaces, or test scope that may be affected.
- If the current modification is too small to extract valid changes, or the analysis fails, the system may not output a complete report, but the main flow still continues.

## Notes

- The impact analysis helps you narrow the review scope; it does not mean all verification has already been completed automatically.
- If you see additional affected files or tests mentioned in the report, it is best to check these positions manually as well.
- This feature is only meaningful when code changes actually occur; pure explanatory tasks will not produce this kind of analysis result.
