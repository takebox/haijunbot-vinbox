---
name: code_review
description: Triggered when code review or PR review is needed. Triggered whenever the user mentions "code review", "CR", "code review", "Pull Request", "PR review", "quality gatekeeping". Not triggered: writing new code (use the karpathy rules); refactoring checks (use the refactor-checker rules); documentation writing.
---

# Code Review Rules

## Aspects That Must Be Reviewed

### 1. Functional Correctness (Must Verify)

**Checklist:**

- [ ] Does the code implement the intended functionality?
- [ ] Are all boundary cases handled?
- [ ] Are all exception cases handled?
- [ ] Are there potential security vulnerabilities?
- [ ] Are there obvious logic errors?

**Action Requirements:**

- If functionality is not implemented or is implemented incorrectly, point it out and request a fix
- If boundary or exception handling is missing, request that it be added
- If security vulnerabilities are found, mark them as blocking issues

### 2. Code Quality (Must Evaluate)

**Checklist:**

- [ ] Is the code clear and readable?
- [ ] Are variable and function names accurate and meaningful?
- [ ] Is there duplicate code that needs refactoring?
- [ ] Is the code structure reasonable?

**Action Requirements:**

- If naming is unclear, suggest a clearer name
- If duplicate code is found, suggest extracting common logic
- If the code structure is messy, suggest refactoring

### 3. Performance Considerations (Must Evaluate)

**Checklist:**

- [ ] Are there obvious performance bottlenecks?
- [ ] Are the algorithm and data structure choices reasonable?
- [ ] Is there unnecessary computation or resource consumption?
- [ ] Is there a risk of memory leaks?

**Action Requirements:**

- If performance issues are found, point them out and provide optimization suggestions
- If the algorithm choice is inappropriate, suggest a more suitable approach

### 4. Maintainability (Must Evaluate)

**Checklist:**

- [ ] Is the code structure reasonable?
- [ ] Does it follow the project's coding standards?
- [ ] Are there appropriate comments and documentation?
- [ ] Is the code easy to understand and modify?

**Action Requirements:**

- If coding standards are violated, request correction
- If necessary comments are missing, request that they be added
- If the code is difficult to understand, request refactoring

## Review Conduct Standards

### Principles You Must Follow

- **Must**: Maintain constructive feedback, focusing on the code rather than the person
- **Must**: Provide specific, actionable suggestions
- **Must**: Acknowledge good practices and design
- **Must**: Respond to review requests promptly
- **Forbidden**: Use aggressive or derogatory language

### Format of Review Comments

- Clearly indicate where the problem is (file, line number, code snippet)
- Explain the impact of the problem (why this is a problem)
- Provide specific fix recommendations (how to fix it)
- If it is a blocking issue, mark it clearly

### Handling Complex Changes

- For large or complex changes, phased reviews may be requested
- Suggest splitting complex features into multiple small, reviewable commits

## Review Checklist

When completing a code review, please make sure to confirm:

**Functional Level:**

- [ ] The code implements the intended functionality
- [ ] Boundary and exception cases are handled
- [ ] No obvious bugs or logic errors

**Quality Level:**

- [ ] The code follows the project's coding standards
- [ ] Naming is clear and meaningful
- [ ] No duplicate code
- [ ] The code structure is reasonable

**Security and Performance:**

- [ ] No security vulnerabilities
- [ ] Performance is acceptable
- [ ] Resource usage is reasonable

**Maintainability:**

- [ ] Appropriate error handling is in place
- [ ] Necessary test coverage exists
- [ ] Code comments are clear and accurate
- [ ] The code is easy to understand and maintain
