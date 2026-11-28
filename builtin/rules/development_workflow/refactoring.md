---
name: refactoring
description: Triggered when the code structure needs to be improved without changing functionality. Triggered whenever the user mentions "refactoring", "code optimization", "technical debt", "improve code", "clean up code", "optimize structure". Not triggered: only fixing bugs without structural improvement; only adding new features; performance optimization without code structure changes.
---

# Refactoring Rules

## Refactoring Principles That Must Be Followed

### 1. Small Steps, Fast Iteration Principle (Must Follow)

**Execution Requirements:**

- **Must**: Each refactoring makes only small changes
- **Must**: Run tests immediately after each change
- **Must**: Confirm tests pass before proceeding to the next refactoring step
- **Must**: Use version control, committing each small change for easy rollback

**Forbidden:**

- **Forbidden**: Large-scale refactoring all at once
- **Forbidden**: Continuing refactoring when tests fail

### 2. Preserve Functionality Principle (Must Follow)

**Execution Requirements:**

- **Must**: Refactoring should not change the code's external behavior
- **Must**: Before and after refactoring, all tests must pass
- **Must**: If there is a functionality change request, it must be committed separately; do not mix it with refactoring

**Verification Method:**

- Run all tests before refactoring and record the test results
- Run all tests after refactoring to ensure consistent results
- If tests fail, roll back or fix immediately

### 3. Identify Code Smells (Must Identify and Handle)

**Code smells that must be identified and handled:**

- [ ] Duplicate code (violates the DRY principle)
- [ ] Overly long methods or classes (exceeding a reasonable length)
- [ ] Excessively deep nesting (exceeding 3-4 levels)
- [ ] Magic numbers and strings (unnamed constants)
- [ ] Excessive parameter lists (exceeding 3-4 parameters)
- [ ] Overly long method chains
- [ ] Oversized classes (too many responsibilities)

## Refactoring Techniques You Must Master

### 1. Extract Method

**When to use:** The method is too long or contains duplicate logic
**Operation Steps:**

1. Identify a method block that can stand alone
2. Create a new method and move the code
3. Replace the original code with a method call
4. Run tests to confirm

### 2. Extract Variable

**When to use:** Complex expressions are hard to understand
**Operation Steps:**

1. Identify complex expressions
2. Create a meaningful variable name
3. Replace the expression with the variable
4. Run tests to confirm

### 3. Rename

**When to use:** The name is unclear or misleading
**Operation Steps:**

1. Determine a clearer name
2. Use the IDE's refactoring tools to rename
3. Run tests to confirm

### 4. Remove Duplication

**When to use:** Duplicate code is found
**Operation Steps:**

1. Identify duplicate patterns
2. Extract common logic into a function or class
3. Replace all duplicate code
4. Run tests to confirm

### 5. Simplify Conditional

**When to use:** Conditional expressions are complex and hard to understand
**Operation Steps:**

1. Extract conditions into meaningful variables
2. Use early returns to reduce nesting
3. Use clearer conditional expressions
4. Run tests to confirm

### 6. Move Code

**When to use:** The code is in an inappropriate location
**Operation Steps:**

1. Determine where the code should live
2. Move the code to the appropriate location
3. Update references
4. Run tests to confirm

## Refactoring Timing Judgment

### Situations Requiring Refactoring

1. **Before adding new features**:
   - If the existing code structure is hard to extend
   - **Must**: First refactor the existing code to make it easier to extend
   - **Then**: Add the new features

2. **When fixing bugs**:
   - If you find that code structure problems cause the bug
   - **Must**: First refactor the code structure
   - **Then**: Fix the bug

3. **During code review**:
   - If you find areas for improvement
   - **Must**: Recommend refactoring
   - **Must**: Provide specific refactoring suggestions

4. **Regular cleanup**:
   - **Must**: Regularly clean up technical debt
   - **Must**: Identify and refactor code smells

## Refactoring Execution Checklist

After completing refactoring, please make sure to confirm:

- [ ] All tests pass (test results are consistent before and after refactoring)
- [ ] The code is clearer and more readable
- [ ] No new bugs have been introduced
- [ ] Performance has not significantly degraded (if it has, the reason must be explained)
- [ ] The code is easier to extend and maintain
- [ ] Code smells have been eliminated or reduced
- [ ] The refactoring has been committed to version control
