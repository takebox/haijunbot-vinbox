---
name: clean_code
description: Triggered when clean code needs to be written or reviewed. Triggered whenever the user mentions "clean code", "coding standards", "best practices", "code review", "readability", "naming conventions", "code quality". Not triggered: architecture design (use the clean_architecture rules); performance optimization; secure coding (use the security rules).
---

# Clean Code Rules

## Core Principles That Must Be Followed

### 1. Readability First (Essential)

**Guidelines:**

- **Must**: Code is written for humans; machines merely execute it
- **Must**: Use meaningful variable and function names
- **Must**: Code should be self-explanatory, reducing unnecessary comments
- **Forbidden**: Use meaningless variable names (such as `a`, `b`, `x`, `temp`)

**Naming Requirements:**

- Variable names must clearly indicate their use
- Function names must clearly indicate their function
- Class names must clearly indicate their responsibility

### 2. Single Responsibility (Must Follow)

**Function Requirements:**

- **Must**: Each function does only one thing
- **Must**: The function name should accurately describe its function
- **Forbidden**: One function performing multiple unrelated tasks

**Class Requirements:**

- **Must**: Each class has only one reason to change
- **Must**: The class's responsibility should be clear and explicit
- **Forbidden**: Creating "god classes" with muddled responsibilities

**Code Requirements:**

- **Must**: Keep functions and classes concise
- **Must**: If a function or class grows complex, it must be split

### 3. DRY Principle (No Repetition)

**Guidelines:**

- **Forbidden**: Write duplicate code
- **Must**: Extract common logic into functions or classes
- **Must**: Use configuration rather than hardcoding
- **Must**: Identify and eliminate duplicate patterns

## Naming Conventions (Must Follow)

### Variable and Function Naming

- **Must**: Use descriptive names, avoid abbreviations
- **Must**: Function names should be verbs or verb phrases (such as `calculateTotal`, `getUserById`)
- **Must**: Class names should be nouns or noun phrases (such as `UserService`, `OrderProcessor`)
- **Must**: Boolean variables should use prefixes like is/has/can (such as `isValid`, `hasPermission`, `canEdit`)
- **Forbidden**: Use single-letter variable names (except loop counters)
- **Forbidden**: Use misleading names

### Constant Naming

- **Must**: Constants should be in ALL_CAPS with words separated by underscores (such as `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`)
- **Must**: Magic numbers and strings must be defined as constants

## Function Design Standards (Must Follow)

### Function Length

- **Must**: Functions should be short, ideally no more than twenty lines
- **Must**: If a function exceeds twenty lines, consider splitting it
- **Must**: A function should do one thing, and do it well

### Function Parameters

- **Must**: Function parameters should be as few as possible, ideally no more than three
- **Must**: If parameters exceed three, consider using an object or configuration class
- **Forbidden**: Use boolean parameters to control function behavior (use the strategy pattern or function overloading instead)

### Function Behavior

- **Must**: Avoid side effects; functions should be predictable
- **Must**: Functions should return a consistent result type
- **Forbidden**: A function both modifies state and returns a value (unless explicitly required)

## Code Organization Standards (Must Follow)

### Code Layout

- **Must**: Related code should be placed together
- **Must**: Use blank lines to separate logical blocks
- **Must**: Maintain a consistent code style
- **Must**: Follow the project's code formatting standards

### Code Cleanup

- **Must**: Delete unused code
- **Must**: Delete outdated comments
- **Must**: Delete debug code (such as `console.log`, `print` statements)
- **Forbidden**: Commit code containing debug code

## Code Examples

### ❌ Bad Practices

```python
def calc(x, y, z):
    return x * y + z * 2

def process(data):
    # Process the data
    result = []
    for i in data:
        if i > 0:
            result.append(i * 2)
    return result
```

### ✅ Good Practices

```python
TAX_MULTIPLIER = 2.0

def calculate_total_price(quantity: int, unit_price: float, tax_rate: float) -> float:
    subtotal = quantity * unit_price
    tax = subtotal * tax_rate
    return subtotal + tax

def filter_and_double_positive_numbers(numbers: list[int]) -> list[int]:
    """Filter positive numbers and double them"""
    return [number * 2 for number in numbers if number > 0]
```

## Code Quality Checklist

Before committing code, please make sure to confirm:

- [ ] All variables and functions have meaningful names
- [ ] Function length does not exceed twenty lines (or a reasonable limit)
- [ ] Function parameters do not exceed three
- [ ] No duplicate code
- [ ] No unused code or comments
- [ ] Code formatting complies with project standards
- [ ] Code is self-explanatory and does not need excessive comments
- [ ] Each function does only one thing
- [ ] Each class has a single responsibility
