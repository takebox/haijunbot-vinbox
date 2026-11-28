---
name: karpathy_coding_guidelines
description: Triggered when code needs to be written, modified, or reviewed. Triggered whenever the user mentions "coding guidelines", "Karpathy", "coding best practices", "high-quality code". Not triggered: pure documentation writing; non-coding tasks; deployment and operations.
---

# Karpathy Coding Behavior Guidelines

**Core Principle:** These guidelines lean toward caution rather than speed. For simple tasks, use your own judgment — no need to follow them to the letter.

## 1. Think Clearly Before Coding

**Do not make assumptions, do not hide confusion, and be explicit about trade-offs.**

Before starting implementation:

- Clearly state your assumptions. If unsure, ask.
- If there are multiple viable approaches, list them all — do not silently pick one.
- If there is a simpler way, say so directly. Question existing approaches when necessary.
- If something is unclear, stop, point out the confusion, and confirm with the user.

## 2. Keep It Simple

**Solve the problem with the least amount of code, and do not make unfounded guesses.**

- Do not build extra features beyond the requirements.
- Do not introduce abstractions for one-off code.
- Do not add unrequested "flexibility" or "configurability" on your own.
- Do not pile on error handling for scenarios that cannot occur.
- If you wrote 200 lines when 50 would do, rewrite it.

Ask yourself: "Would a senior engineer think this is overcomplicated?" If so, simplify.

- **No file should exceed 1000 lines.** Files over 1000 lines prevent the model from reading the complete context in one pass, affecting code understanding and modification quality. Oversized files should be split into multiple modules or sub-files.

## 3. Make Precise Modifications

**Only change what needs to be changed, and only clean up problems you yourself introduced.**

When editing existing code:

- Do not casually "improve" adjacent code, comments, or formatting.
- Do not refactor parts that were never broken.
- Match the existing code style, even if you would write it differently yourself.
- If you spot unrelated dead code, mention it, but do not delete it on your own.

When your changes produce orphaned code:

- Delete imports, variables, or functions that became unused because of your modifications.
- Unless asked, do not delete dead code that existed before your changes.

Testing standard: every line of your changes should be directly traceable to the user's request.

## 4. Goal-Driven Execution

**First define verifiable success criteria, then iterate in a loop until verification passes.**

Turn vague tasks into verifiable goals:

- "Add validation" → "Write tests for invalid input, then make the tests pass"
- "Fix a bug" → "Write a test that reproduces the issue, then make it pass"
- "Refactor X" → "Ensure the relevant tests pass both before and after refactoring"

For multi-step tasks, first give a brief plan:

```text
1. [Step] → Verification method: [How to check]
2. [Step] → Verification method: [How to check]
3. [Step] → Verification method: [How to check]
```

Clear success criteria let you iterate independently. Vague criteria (like "make it work") will only send you back for repeated clarification.

---

**When these guidelines pay off:** fewer unnecessary changes in diffs, less rework caused by over-engineering, and clarifications happening before implementation rather than after mistakes.
