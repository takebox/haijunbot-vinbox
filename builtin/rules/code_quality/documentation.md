---
name: documentation
description: Triggered when technical documentation or API documentation needs to be written. Triggered whenever the user mentions "write documentation", "technical documentation", "API documentation", "project documentation", "documentation generation", "README". Not triggered: code review; refactoring checks; performance optimization.
---

# Documentation Writing Rules

## Documentation Principles That Must Be Followed

### 1. Clarity Principle (Must Follow)

**Documentation Requirements:**

- **Must**: Documentation should be clear and accurate
- **Must**: Use simple language
- **Must**: Avoid unnecessary technical jargon
- **Must**: Provide explanations of terminology when necessary

**Writing Requirements:**

- Use short sentences, avoid long sentences
- Use the active voice
- Use concrete examples
- Avoid vague expressions

### 2. Completeness Principle (Must Follow)

**Documentation Requirements:**

- **Must**: Documentation should cover all important features
- **Must**: Include usage examples
- **Must**: Describe limitations and caveats
- **Must**: Describe prerequisites and dependencies

**Content Requirements:**

- Feature description: explain what the feature does
- Usage instructions: explain how to use it
- Parameter descriptions: describe all parameters
- Return value descriptions: describe return values
- Exception descriptions: describe possible exceptions
- Example code: provide runnable examples

### 3. Timeliness Principle (Must Follow)

**Maintenance Requirements:**

- **Must**: Update documentation synchronously when code changes
- **Must**: Documentation should reflect the current implementation
- **Must**: Delete outdated documentation
- **Forbidden**: Documentation inconsistent with code

**Update Timing:**

- Update documentation immediately when adding new features
- Update documentation synchronously when modifying features
- Delete related documentation when removing features
- Regularly check consistency between documentation and code

## Types of Documentation That Must Be Written

### 1. Code Comments (Must Write)

**Comment Requirements:**

- **Must**: Explain "why", not "what"
- **Must**: Complex logic must have comments
- **Must**: Public APIs must have docstrings
- **Forbidden**: Comments that merely repeat what the code says

**Comment Content:**

- Business logic explanations
- Reasons for algorithm choices
- Reasons for special handling
- Known issues and limitations

**Docstring Format:**

```python
def calculate_total(items: list[Item], discount: float = 0.0) -> float:
    """Calculate the total price of items

    Args:
        items: List of items, must not be empty
        discount: Discount rate, range 0.0-1.0, default 0.0

    Returns:
        The calculated total price with the discount applied

    Raises:
        ValueError: Raised when items is empty or discount is out of the valid range

    Example:
        >>> items = [Item(price=10.0), Item(price=20.0)]
        >>> calculate_total(items, discount=0.1)
        27.0
    """
    pass
```

### 2. README Documentation (Must Write)

**README Requirements:**

- **Must**: Project overview and quick start
- **Must**: Installation and configuration instructions
- **Must**: Usage examples
- **Must**: FAQ (if applicable)

**README Structure:**

- Project introduction
- Feature highlights
- Installation steps
- Configuration instructions
- Quick start
- Usage examples
- API documentation link
- Contribution guidelines
- License information

### 3. API Documentation (Must Write)

**API Documentation Requirements:**

- **Must**: Function signatures and parameter descriptions
- **Must**: Return value descriptions
- **Must**: Usage examples
- **Must**: Exception descriptions

**Documentation Content:**

- Function/method signatures
- Parameter types and descriptions
- Return value types and descriptions
- Possible exceptions
- Usage examples
- Related API links

## Documentation Writing Checklist

After completing the code, please make sure to confirm:

**Code Comments:**

- [ ] All public APIs have docstrings
- [ ] Complex logic has explanatory comments
- [ ] Comments explain "why" rather than "what"
- [ ] No outdated comments

**README:**

- [ ] README includes a quick start guide
- [ ] Installation and configuration instructions are present
- [ ] Usage examples are present
- [ ] Documentation is clear and readable

**API Documentation:**

- [ ] All public APIs are documented
- [ ] Parameters and return values are described
- [ ] Usage examples are present
- [ ] Possible exceptions are described

**Documentation Maintenance:**

- [ ] Documentation is kept in sync with the code
- [ ] Outdated documentation is deleted
- [ ] Documentation reflects the current implementation
