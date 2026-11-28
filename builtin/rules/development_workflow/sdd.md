---
name: sdd
description: Triggered when an SDD development workflow that writes a spec before implementing the code is needed. Triggered whenever the user mentions "spec-driven", "spec first", "requirement analysis", "spec writing", or "SDD". Not triggered: writing code only without involving spec-first; only reading existing specs; the TDD workflow.
---

# Spec-Driven Development (SDD) Rule

## The Workflow You Must Follow

### The Spec-Implement-Verify Loop (strictly enforced)

1. **📝 Spec Phase (writing the functional spec)**:
   - Before writing any code, a detailed functional specification (Spec) should first be written
   - The Spec must clearly describe the functional goals, inputs and outputs, boundary conditions, and exception handling
   - The Spec should include clear acceptance criteria
   - The Spec must be reviewed and confirmed before entering the implementation phase

2. **⚡ Implementation Phase (coding based on the spec)**:
   - Implement the code strictly according to the description in the Spec
   - Do not deviate from the functional boundaries and interface design defined in the Spec
   - If areas of the Spec are unclear during implementation, update the Spec first before continuing
   - While writing code, also think about how to verify the Spec's acceptance criteria

3. **✅ Verification Phase (verifying compliance with the spec)**:
   - Verify the correctness of the implementation against the Spec
   - Ensure all acceptance criteria are satisfied
   - Run tests, code reviews, documentation checks, and other verification activities
   - If verification fails, return to the implementation or Spec phase to fix it

## The Principles You Must Comply With

### The Spec-First Principle

- **Forbidden**: starting to implement a feature without a Spec
- **Must**: every new feature has a corresponding specification document
- **Must**: the Spec should be clear, specific, and verifiable
- **Must**: the Spec should contain complete acceptance criteria

### The Spec Completeness Principle

- **Must**: the Spec should include a functional description (what it does)
- **Must**: the Spec should include the interface definition (inputs and outputs)
- **Must**: the Spec should include boundary conditions (edge cases)
- **Must**: the Spec should include exception handling (error cases)
- **Must**: the Spec should include acceptance criteria (how to verify completion)

### The Spec Consistency Principle

- **Must**: the code implementation must remain consistent with the Spec
- **Forbidden**: implementing functionality beyond the scope of the Spec (unless the Spec is updated)
- **Must**: updating the Spec in sync when the code changes
- **Forbidden**: the Spec and the code being inconsistent

## Spec Writing Requirements

### 1. File Location Requirements (must be followed)

**Location specification:**

- **Must**: Spec files should be placed in the project's `.haijunbot/rules/spec/` directory

**File path:**

```text
{{ git_root_dir }}/.haijunbot/rules/spec/<spec_name>.md
```

**Variable description:**

- `{{ git_root_dir }}`: the root directory of the current git repository

**Naming conventions:**

- **Must**: use lowercase letters
- **Must**: separate words with underscores `_`
- **Must**: use the `.md` suffix
- **Forbidden**: using spaces, hyphens `-`, or uppercase letters

**Naming examples:**

- ✅ Correct: `user_auth_spec.md`, `data_processing_spec.md`
- ❌ Incorrect: `UserAuthSpec.md`, `user-auth-spec.md`

### 2. Content a Spec Should Include

0. **YAML header (required)**
   - **Must**: the Spec file has a YAML front matter header at the top
   - Format as follows:

   ```yaml
   ---
   name: spec_name # required, the brief identifier of the spec
   description: spec function description # required, the detailed description of the spec
   ---
   ```

   - `name`: the name identifier of the spec, using lowercase letters and underscores
   - `description`: the functional description of the spec, clearly stating the design goals

1. **Functional overview**
   - Briefly state the goals and value of the functionality
   - Clearly state the usage scenarios of the functionality

2. **Interface definition**
   - The signature of functions/methods (parameter types, return value types)
   - The definition of API endpoints (paths, methods, request/response formats)
   - The public interface of classes (properties and methods)

3. **Input/output description**
   - A detailed description of all parameters (types, ranges, constraints)
   - A detailed description of the return value (type, meaning)
   - Possible exceptions or error codes raised

4. **Functional behavior**
   - The processing logic for normal cases
   - The handling approach for boundary conditions
   - The strategy for handling exceptional cases
   - Performance requirements (if applicable)

5. **Acceptance criteria**
   - Clear pass conditions
   - Verifiable test scenarios
   - Specific verification methods

### 3. Spec Writing Conventions

- **Must**: use clear, concise language
- **Must**: avoid vague expressions (such as "as fast as possible", "reasonable")
- **Must**: use specific values and ranges
- **Must**: provide concrete examples
- **Must**: use a structured format (such as lists, tables)

## Practical Guidance

### The way of thinking when writing a Spec

- Ask yourself: "What problem is this feature supposed to solve?" rather than "How is this feature implemented?"
- Think about functional requirements from the user's perspective, not the technical perspective
- Clearly define the boundaries of the functionality: what is in scope, what is out of scope
- Consider all possible input scenarios (normal, boundary, exceptional)

### Best practices for writing a Spec

- Use the user-story format ("As a... I need... so that...")
- Number each acceptance criterion for traceability
- Use examples to illustrate complex requirements
- Distinguish "required" and "optional" requirements
- Consider backward compatibility and extensibility

### The handling workflow when a Spec problem is found

1. Stop the implementation immediately
2. Update the Spec document, clarifying or supplementing the missing information
3. Re-review the updated Spec
4. Continue the implementation after confirming the Spec is complete

## Code Examples

### ❌ Bad practice (no Spec)

```python
# start writing code directly, with no specification document
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
```

### ✅ Good practice (write a Spec first)

**Spec document:**

````markdown
# Data Processing Functional Specification

## Functional Overview

Filters and transforms the input numeric list, returning twice the value of the positive numbers.

## Interface Definition

### Function Signature

```python
def filter_and_double_positive_numbers(numbers: list[int]) -> list[int]
```
````

### Parameter description

- `numbers`: the input numeric list, which may be empty

### Return value description

- Returns the list of doubled positive numbers after filtering
- If there are no positive numbers, returns an empty list

### Exception description

- If the input is not a list, raises TypeError
- If the list contains non-numeric elements, raises ValueError

## Functional Behavior

### Normal cases

- Input [1, 2, 3], returns [2, 4, 6]
- Input [-1, 0, 1], returns [2]

### Boundary cases

- Input an empty list [], returns []
- Input contains 0; 0 is not considered a positive number and is not processed

### Exceptional cases

- Input of a non-list type raises TypeError
- A list containing non-numeric elements such as strings raises ValueError

## Acceptance Criteria

1. Can correctly filter positive numbers and double them
2. Can correctly handle an empty list
3. Can correctly handle a list containing 0
4. Can correctly raise a type error
5. Can correctly raise a value error

````markdown
**Code implementation:**

```python
# implemented based on the Spec
def filter_and_double_positive_numbers(numbers: list[int]) -> list[int]:
    """Filter positive numbers and double them

    Args:
        numbers: the input numeric list

    Returns:
        the list of doubled positive numbers after filtering

    Raises:
        TypeError: if the input is not a list
        ValueError: if the list contains non-numeric elements
    """
    if not isinstance(numbers, list):
        raise TypeError("Input must be a list")

    result = []
    for number in numbers:
        if not isinstance(number, (int, float)):
            raise ValueError("List must contain only numbers")
        if number > 0:
            result.append(number * 2)

    return result
```
````

## Execution Checklist

Before starting to implement a feature, be sure to confirm:

- [ ] A complete functional specification document has been written
- [ ] The Spec file has been placed in the `{{ git_root_dir }}/.haijunbot/rules/spec/` directory
- [ ] The Spec file naming conforms to the conventions (lowercase letters, underscore separation, .md suffix)
- [ ] The Spec file includes a YAML header (the name and description fields)
- [ ] The Spec includes the functional overview and goals
- [ ] The Spec includes a clear interface definition
- [ ] The Spec includes a complete input/output description
- [ ] The Spec includes boundary conditions and exception handling
- [ ] The Spec includes explicit acceptance criteria
- [ ] The Spec has been reviewed and confirmed

When implementing the feature, be sure to confirm:

- [ ] The implementation follows the Spec strictly
- [ ] There is no implementation beyond the scope of the Spec
- [ ] Update the Spec first when the Spec is unclear

After completing the implementation, be sure to confirm:

- [ ] All acceptance criteria have been satisfied
- [ ] The code implementation is consistent with the Spec
- [ ] Tests have been written to verify all acceptance criteria
- [ ] The documentation stays in sync with the implementation
- [ ] The code has passed review

**Signs of successful SDD:**

- Implementation = Spec (no deviation)
- Acceptance = criteria (all pass)
- Documentation = reality (reflects the current state)
