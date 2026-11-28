---
name: tdd
description: Triggered when a TDD development process where tests are written before feature implementation is needed. Triggered whenever the user mentions "test-driven", "TDD", "red-green-refactor", "write tests first", "tests first". Not triggered: writing tests only without a TDD process; only running existing tests; debugging test failures without using a TDD approach.
---

# Test-Driven Development (TDD) Rules

## Mandatory Workflow

### Red-Green-Refactor Cycle (Strictly Enforced)

1. **🔴 Red Phase (Write a failing test)**:
   - Write the test case before implementing any feature code
   - The test must describe the expected behavior, not the implementation details
   - Run the test and confirm it fails (red)

2. **🟢 Green Phase (Make the test pass)**:
   - Write the simplest code that makes the test pass
   - Do not over-engineer; implement only the minimal code that makes the test pass
   - Run the test and confirm it passes (green)

3. **🔵 Refactor Phase (Optimize the code)**:
   - Optimize the code structure on the basis of passing tests
   - After refactoring, you must run the tests again to ensure all tests still pass
   - If refactoring causes tests to fail, roll back or fix immediately

## Principles You Must Follow

### Test-First Principle

- **Forbidden**: Implementing feature code before writing the test
- **Mandatory**: Write test cases for every new feature
- **Mandatory**: Tests should be clear, readable, and maintainable
- **Mandatory**: Use descriptive test names that clearly express the test intent

### Test Coverage Requirements

- **Mandatory**: Write corresponding tests for brand-new features
- **Mandatory**: Tests must cover the following three scenarios:
  - Normal scenario (happy path)
  - Boundary scenario (edge cases)
  - Exception scenario (error cases)
- **Mandatory**: Ensure tests run independently and do not depend on other tests
- **Mandatory**: Ensure tests are repeatable with consistent results

## Practical Guidance

### How to Think When Writing Tests

- Ask yourself: "What should this feature do?" rather than "How is this feature implemented?"
- Tests should verify behavior, not implementation details
- One test should verify only one behavior or scenario

### Handling Process When a Bug Is Found

1. First write a test case that reproduces the bug
2. Run the test and confirm it fails (reproducing the issue)
3. Fix the code
4. Run the test and confirm it passes (issue resolved)

## Code Example

```python
# ✅ Correct approach: write the test first
def test_calculate_total():
    assert calculate_total([1, 2, 3]) == 6
    assert calculate_total([]) == 0
    assert calculate_total([-1, 1]) == 0

# Then implement the feature
def calculate_total(numbers):
    return sum(numbers)
```

## Execution Checklist

Before submitting code, please make sure to confirm:

- [ ] All new features have corresponding test cases
- [ ] Tests cover normal, boundary, and exception scenarios
- [ ] All tests can run independently
- [ ] All tests pass
- [ ] Test names clearly describe the test intent
