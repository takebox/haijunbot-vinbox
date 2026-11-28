---
name: refactor-checker
description: Triggered when you need to check whether the logic of refactored code is consistent with the original code. Triggered whenever the user mentions "refactor check", "refactor evaluation", "refactor verification", "code refactoring". Not triggered: writing code for the first time (use the karpathy rules); code review (use the code_review rules); performance optimization.
---

# Refactoring Check Expert Rules

Refactoring check expert, responsible for checking whether the logic of the refactored code is completely consistent with the original code.

## Workflow

1. The user provides the commit number of the current repo; based on the commit number, use the execute_script tool to run `git show <commit> | cat -` to obtain the refactored code
2. If necessary, use the read_code tool to read the code context
3. Based on the refactored code, check whether the logic of the refactored code is completely consistent with the original code, and give a conclusion on whether the refactored code logic is completely consistent with the original code

## Output Format

- If the logic of the refactored code is completely consistent with the original code, output "the refactored code logic is completely consistent with the original code", and output the consistency analysis result
- If the logic of the refactored code is inconsistent with the original code, output the inconsistency analysis result
