# Best Practices for Using Rules

## 1. Overview

This document summarizes the best practices for using the HaijunBot rule system, helping developers use the rule system efficiently and correctly to improve code quality and development efficiency.

---

## 2. Rule Selection Strategies

### 2.1 Selecting Rules Based on Task Type

Different task types should use different rule combinations:

| Task Type     | Recommended Rules                                    | Description                   |
| ------------ | ------------------------------------------- | ---------------------- |
| **Code Generation** | `clean_code`, `security`                    | Ensure code quality and security   |
| **Code Refactoring** | `refactoring`, `clean_code`                 | Follow refactoring principles and code standards |
| **API Development** | `clean_code`, `security`, `documentation`   | APIs need documentation and security considerations |
| **Performance Optimization** | `performance`, `rust_performance` (if applicable) | Focus on performance optimization         |
| **Test Writing** | `tdd`, `python_test` (or the corresponding language)          | Test-driven development and testing standards |
| **Architecture Design** | `clean_architecture`, `solid`               | Architecture design principles           |
| **Security Audit** | `security`, `vulnerability-analysis`        | Security-related tasks           |

### 2.2 Principles of Rule Combination

1. **Core rules first**: Select core rules (such as `clean_code`) first, then add specific rules
2. **Avoid conflicts**: Pay attention to conflicts between rules; rules loaded later override rules loaded earlier
3. **Use in moderation**: Do not load too many rules at once; 3-5 rules are usually enough
4. **Project rules first**: Project-specific rules should take precedence over general rules

### 2.3 Understanding Rule Priority

Understand rule loading priority and organize rules reasonably:

```
Priority from high to low:
1. Central rule repository
2. Project rule directory (.haijunbot/rules/)
3. Configured rule directory
4. Global rule directory (~/.haijunbot/rules/)
5. Built-in rules (builtin/rules/)
```

---

## 3. Ways to Use Rules

### 3.1 Command-line Argument Approach

**Applicable scenarios**: Scripts, CI/CD, one-off tasks

```bash
# Single rule
hca --rule-names clean_code "Create user module"

# Multiple rules
hca --rule-names clean_code,security,performance "Create API"

# Project rules + built-in rules
hca --rule-names my_project_rule,clean_code "Create feature"
```

**Advantages**:

- Explicitly specify rules
- Suitable for automation scenarios
- Repeatable execution

**Disadvantages**:

- Need to remember rule names
- The command line can be very long

### 3.2 Project Rule File Approach

**Applicable scenarios**: Fixed coding standards for a project

**Recommended approach**: Use the `add_rule` rule to create automatically, rather than writing by hand.

**Manual creation** (not recommended):
Create a `.haijunbot/rules/rule.md` file:

```markdown
# Project rules

You must follow the following principles:

- Code must comply with the PEP 8 standard
- All public functions must have type annotations
- Unit tests must be written
```

**Advantages**:

- Automatically loaded, no need to specify each time
- Shared by the team, unified standards
- Version controlled, changes can be tracked

**Disadvantages**:

- Only applies to the current project
- May affect all tasks

### 3.3 Global Rule File Approach

**Applicable scenarios**: Personal general coding standards

**Recommended approach**: Use the `add_rule` rule to create automatically, rather than writing by hand.

**Manual creation** (not recommended):
Create a `~/.haijunbot/rules/rule.md` file:

```markdown
# Global rules

When writing code in Python:

- Must use f-strings for string formatting
- Forbidden to use the print() statement (use the logging module)
```

**Advantages**:

- Takes effect in all projects
- Unified personal preferences

**Disadvantages**:

- May not be suitable for all projects
- Needs to be used with caution

### 3.4 @ Interactive Approach

**Applicable scenarios**: Interactive development, temporary requirements

Enter `@` in an interactive session to trigger rule completion:

```
> @clean_code @security Create user authentication module
```

**Advantages**:

- Quick selection
- Supports search
- Flexible combination

**Disadvantages**:

- Only available in interactive mode
- Requires manual input

---

## 4. Best Practices for Organizing Rules

### 4.1 Project Rule Organization

**Recommended structure**:

```
Project root directory/
├── .haijunbot/
│   ├── rule                    # Project rule file (auto-loaded)
│   └── rules/                  # Project rule directory
│       ├── api/
│       │   └── rest_api_standard.md
│       ├── database/
│       │   └── db_migration_guide.md
│       └── testing/
│           └── test_standards.md
```

**Organization principles**:

1. Classify by functional module
2. Use descriptive directory names
3. Keep the structure clear
4. Update documentation in a timely manner

### 4.2 Global Rule Organization

**Recommended structure**:

```
~/.haijunbot/
├── rule                        # Global rule file (auto-loaded)
└── rules/                      # Global rule directory
    ├── python/
    │   └── python_style_guide.md
    ├── javascript/
    │   └── js_best_practices.md
    └── general/
        └── code_review_checklist.md
```

### 4.3 Rule Naming Conventions

**File naming**:

- ✅ Use lowercase letters: `python_api_standard.md`
- ✅ Use underscores as separators: `rest_api_guide.md`
- ❌ Avoid spaces: `python api standard.md`
- ❌ Avoid hyphens: `python-api-standard.md`
- ❌ Avoid uppercase: `PythonApiStandard.md`

**Rule name** (used for `--rule-names`):

- Remove the `.md` suffix from the file name
- For example: `python_api_standard.md` → `python_api_standard`

---

## 5. Best Practices for Writing Rules

**Recommended approach**: Use the `add_rule` rule to automatically generate or introduce rules, rather than writing by hand. `add_rule` is itself a rule; it guides the Agent to create rule files according to best practices, ensuring the rule format is correct and the structure is clear.

**How to use**:

```bash
# Use the add_rule rule to create a new rule
hca --rule-names add_rule "Create a Python API development standards rule"

# Or use it in an interactive session
hca
> '<rule:add_rule>' Create a Python API development standards rule
```

### 5.1 The Principle of Clarity

**Requirement**: Use clear, unambiguous language

**❌ Bad writing**:

```markdown
Functions should be a bit shorter where possible
```

**✅ Good writing**:

```markdown
**Required**: Function length must not exceed 20 lines
```

### 5.2 The Principle of Actionability

**Requirement**: Every rule should be verifiable

**❌ Bad writing**:

```markdown
The code should be efficient
```

**✅ Good writing**:

```markdown
**Performance requirements:**

- Database queries must use indexes
- Avoid N+1 query problems
- Batch operations must use the batch API
```

### 5.3 The Principle of Structure

**Requirement**: Organize content according to logical levels

**Recommended structure**:

1. Introduction/background
2. Core principles (highest priority)
3. Specific specifications
4. Code examples
5. Checklist

### 5.4 Example-Driven

**Requirement**: Every key specification should be accompanied by an example

````markdown
## Code examples

### ❌ Bad practice

```python
def process_data(data):
    result = []
    for item in data:
        result.append(item * 2)
    return result
```
````

### ✅ Good practice

```python
def process_data(data: List[int]) -> List[int]:
    """Process data, multiplying each element by 2"""
    return [item * 2 for item in data]
```

````

---

## 6. Examples of Rule Usage Scenarios

### Scenario 1: New Project Initialization

**Goal**: Establish coding standards for a new project

**Recommended approach**: Use the `add_rule` rule to automatically create project rules. `add_rule` is itself a rule, used via `hca --rule-names add_rule`.

**Steps**:

1. Use `add_rule` to create the project rule file
2. Create a rule directory and add more rule files as needed
3. Commit to version control

**Example**:

```bash
# Use add_rule to create the project rule file
hca --rule-names add_rule "Create project coding standards, including:
- Code must comply with the PEP 8 standard
- All public functions must have type annotations
- Unit tests must be written
- APIs must return a unified format"

# Use add_rule to create rule files in the rule directory
hca --rule-names add_rule "Create a REST API standards rule in the .haijunbot/rules/api/ directory"
hca --rule-names add_rule "Create a database migration guide rule in the .haijunbot/rules/database/ directory"

# Commit to version control
git add .haijunbot/
git commit -m "Add project coding standards"
````

**Manual creation approach** (not recommended):

```bash
# Manually create project rules (not recommended)
cat > .haijunbot/rules/rule.md << 'EOF'
# Project coding standards

- Code must comply with the PEP 8 standard
- All public functions must have type annotations
- Unit tests must be written
- APIs must return a unified format
EOF

# Create the rule directory
mkdir -p .haijunbot/rules/{api,database,testing}

# Commit to version control
git add .haijunbot/
git commit -m "Add project coding standards"
```

### Scenario 2: Code Review

**Goal**: Use rules to guide code review

**Steps**:

1. Use the code review rule
2. Combine with project-specific rules
3. Generate a review report

**Example**:

```bash
hca --rule-names code_review,my_project_rule "
Review the following code files:
- src/api/users.py
- src/models/user.py
- src/services/user_service.py

Focus on:
1. Code style consistency
2. Security vulnerabilities
3. Performance issues
4. Test coverage
"
```

### Scenario 3: Refactoring Task

**Goal**: Use rules to guide refactoring

**Steps**:

1. Use the refactoring rule
2. Combine with code quality rules
3. Refactor step by step

**Example**:

```bash
hca --rule-names refactoring,clean_code "
Refactor the user authentication module:
1. Extract the authentication logic into a separate service class
2. Implement dependency injection
3. Add unit tests
4. Update documentation
"
```

### Scenario 4: Performance Optimization

**Goal**: Use rules to guide performance optimization

**Steps**:

1. Use performance optimization rules
2. Analyze performance bottlenecks
3. Apply optimization strategies

**Example**:

```bash
hca --rule-names performance,rust_performance "
Optimize order query performance:
1. Analyze current query performance
2. Add necessary database indexes
3. Optimize the query logic
4. Add performance tests
"
```

---

## 7. Best Practices for Maintaining Rules

### 7.1 Regular Review

**Recommendation**: Review the rules once a quarter

**Review content**:

1. Whether the rules are still applicable
2. Whether there are new best practices to add
3. Whether there are outdated rules to delete
4. Whether there are conflicts between rules

### 7.2 Version Control

**Recommendation**: Include rule files in version control

**Project rules**:

```bash
# Commit project rules
git add .haijunbot/rules/
git commit -m "Update project rules: add API standards"
```

**Global rules**:

```bash
# Global rules can be managed separately
cd ~/.haijunbot
git init
git add rules/
git commit -m "Update global rules"
```

### 7.3 Team Collaboration

**Recommendation**: Establish a rule management process

1. **Rule proposal**: Team members can propose new rules
2. **Rule review**: The team reviews rule proposals
3. **Rule release**: Release rules after review passes
4. **Rule update**: Update rules regularly

### 7.4 Documentation Synchronization

**Recommendation**: Keep rule documentation in sync

1. Update documentation when rules change
2. Provide rule usage examples
3. Record rule change history

---

## 8. Performance Optimization Recommendations

### 8.1 Rule File Size

**Recommendations**:

- A single rule file should not exceed 10KB
- Avoid including large numbers of code examples in rules
- Use links to reference external resources

### 8.2 Rule Loading Optimization

**Recommendations**:

1. Only load the necessary rules
2. Avoid loading too many rules (3-5 recommended)
3. Use project rule files rather than specifying each time

### 8.3 Rule Caching

**Description**: HaijunBot automatically caches rule content, but HaijunBot needs to be restarted after rule files change.

---

## 9. Summary

### 9.1 Core Principles

1. **Clarify goals**: Choose appropriate rules according to the task type
2. **Use in moderation**: Do not load too many rules at once
3. **Organize clearly**: Organize rule files by functional module
4. **Maintain regularly**: Review and update rules regularly
5. **Team sharing**: Include rules in version control and share them across the team

### 9.2 Recommended Practices

1. **Project rules**: Create dedicated rule files for the project
2. **Rule combination**: Combine and use multiple rules according to the task type
3. **Rule priority**: Understand rule loading priority and avoid conflicts
4. **Rule maintenance**: Review and update rules regularly to maintain best practices
