# 📋 HAIJUNBOT Rules System Best Practices

This guide explains how to create, use, and manage the HAIJUNBOT rule system, helping developers write high-quality, maintainable rule documents.

## ✨ What Is the Rule System

The HAIJUNBOT rule system is a Markdown-based collection of standardized instructions used to guide Agents in following unified standards and best practices during tasks such as code generation, code review, and refactoring.

### The Value of the Rule System

- **Unified standards**: ensures consistent output style across different Agents
- **Quality assurance**: built-in checklists reduce code defects
- **Knowledge transfer**: documents best practices for easy team sharing
- **Flexible extension**: rules can be customized according to project needs
- **Dynamic rendering**: supports Jinja2 template syntax to make rule content dynamic

---

## 📚 Overview of Existing Rules

HAIJUNBOT includes the following built-in rules, located in the `builtin/rules/` and `builtin/rules/testing/` directories:

### Architecture Design

| rule file               | Purpose       | Use cases      |
| ----------------------- | ------------- | -------------- |
| `solid.md`              | SOLID design principles | Object-oriented design |
| `clean_architecture.md` | Clean architecture | Architecture design |
| `clean_code.md`         | Clean code standards | Code generation, refactoring |

### Development Workflow

| rule file        | Purpose      | Use cases    |
| ---------------- | ------------ | ------------ |
| `sdd.md`         | Spec-driven development | Design document writing |
| `tdd.md`         | Test-driven development | Test code generation |
| `refactoring.md` | Refactoring guide | Code refactoring tasks |

### Code Quality

| rule file          | Purpose      | Use cases    |
| ------------------ | ------------ | ------------ |
| `code_review.md`   | Code review standards | Code review tasks |
| `documentation.md` | Documentation writing standards | Documentation generation |

### Security Standards

| rule file     | Purpose      | Use cases    |
| ------------- | ------------ | ------------ |
| `security.md` | Secure coding standards | Security-related code |

### Performance Optimization Guide

| rule file             | Purpose      | Use cases    |
| --------------------- | ------------ | ------------ |
| `performance.md`      | Performance optimization guide | Performance-sensitive code |
| `rust_performance.md` | Rust performance optimization | Rust code optimization |

### UI Design

| rule file            | Purpose         | Use cases    |
| -------------------- | --------------- | ------------ |
| `ios-dark-theme.md`  | Zen-iOS dark theme | Front-end UI development |
| `ios-light-theme.md` | Zen-iOS light theme | Front-end UI development |

### Tool Configuration

| rule file              | Purpose      | Use cases    |
| ---------------------- | ------------ | ------------ |
| `ignore_all_alerts.md` | Ignore all alerts | Special-case usage |

### Testing Standards

| rule file            | Purpose                       | Use cases      |
| -------------------- | ----------------------------- | -------------- |
| `cpp_test.md`        | C/C++ testing guide           | C/C++ code testing |
| `go_test.md`         | Go testing guide              | Go code testing |
| `javascript_test.md` | JavaScript/TypeScript testing guide | JS/TS code testing |
| `java_test.md`       | Java testing guide            | Java code testing |
| `php_test.md`        | PHP testing guide             | PHP code testing |
| `python_test.md`     | Python testing guide          | Python code testing |
| `ruby_test.md`       | Ruby testing guide            | Ruby code testing |
| `rust_test.md`       | Rust testing guide            | Rust code testing |

---

## 🚀 How to Use Rules

### Where Rules Are Stored

HAIJUNBOT supports loading rules from multiple locations, in priority order from high to low:

1. **Central rule repository** (highest priority)
   - Location: specified via the `central_rules_repo` configuration
   - Supports a local directory or a Git repository URL
   - If a rule with the same name exists, the central repository takes precedence

2. **Project rule directory**
   - Location: `<project root directory>/.haijunbot/rules/`
   - Stores project-specific rule files (`.md` format)

3. **Configured rule directory**
   - Location: specified via the `rules_load_dirs` configuration item
   - Supports multiple directories, loaded in configuration order

4. **Global rule directory**
   - Location: `~/.haijunbot/rules/`
   - Stores globally shared rule files

5. **Built-in rule directory**
   - Location: `builtin/rules/` and `builtin/rules/testing/`
   - The rule set bundled with HAIJUNBOT

6. **Rules in the rules.yaml file**
   - You can define naming rules in `rules.yaml`
   - YAML format, where the key is the rule name and the value is the rule content

### How Rules Are Loaded

#### Method 1: Specify via the `--rule-names` argument

```bash
# Use a single rule
haijunbot code --rule-names clean_code

# Use multiple rules (comma-separated)
haijunbot code --rule-names clean_code,security,performance

# Combine project rules and built-in rules
haijunbot code --rule-names my_project_rule,clean_code
```

#### Method 2: Via the project rule file

Create a `.haijunbot/rules/rule.md` file and its content is loaded automatically:

```markdown
# .haijunbot/rules/rule.md

# This is a global rule that applies to all tasks

You must follow the following principles:

- Code must comply with the PEP 8 standard
- All public functions must have type annotations
- Unit tests must be written
```

#### Method 3: Via the global rule file

Create a `~/.haijunbot/rules/rule.md` file to apply it to all projects:

```markdown
# ~/.haijunbot/rules/rule.md

# Global default rule

When writing Python code:

- You must use `f-strings` for string formatting
- The `print()` statement is forbidden (use the logging module)
```

#### Method 4: Define naming rules via rules.yaml

Create a `rules.yaml` file to define rules that can be referenced by name:

```yaml
# .haijunbot/rules.yaml or ~/.haijunbot/rules.yaml
python_best_practices: |
  # Python best practices rules

  **Naming conventions:**
  - Variable names use snake_case
  - Class names use PascalCase
  - Constants use UPPER_CASE

cpp_memory_safety: |
  # C++ memory safety rules

  **Must:**
  - Use smart pointers to manage memory
  - Raw pointers are forbidden
  - The RAII pattern must be used
```

Reference by name when using:

```bash
haijunbot code --rule-names python_best_practices
```

#### Method 5: Interactively add rules with @

Entering the `@` symbol in interactive input triggers the rule completion feature, allowing you to quickly select and insert the desired rules.

**Usage steps:**

1. **Trigger completion**: type the `@` symbol during interactive input
2. **Browse rules**: the system automatically displays a list of all available rules, including:
   - Built-in rules (`builtin/rules/`)
   - Project rules (`.haijunbot/rules/`)
   - YAML-defined rules (`rules.yaml`)
   - Global rules (`~/.haijunbot/rules/`)
3. **Select a rule**: use the up/down keys or the mouse to select the desired rule
4. **Automatic injection**: after confirming the selection, the rule content is automatically inserted into the input

**Completion priority:**

Rules are displayed and searched in the following order:

1. Central rule repository (highest priority)
2. Project rule directory (`.haijunbot/rules/`)
3. Project `rules.yaml` file
4. Configured rule directory
5. Global rule directory (`~/.haijunbot/rules/`)
6. Built-in rule directory (`builtin/rules/`)

**Supported operations:**

- **Real-time search**: type part of a rule name to quickly filter the rule list
- **Multi-select insertion**: you can select multiple rules and insert them one by one
- **Content preview**: some systems support previewing rule content before insertion
- **Shortcuts**: supports using `Tab` or `Enter` to quickly confirm the selection

**Use cases:**

- ✅ When you need to quickly switch between different rule sets
- ✅ When you don't remember the exact name of a rule
- ✅ When you want to combine multiple rule usages
- ✅ When you temporarily need to add extra rules
- ✅ During interactive development and debugging

**Method comparison:**

| Method              | Pros         | Cons       | Use cases    |
| ------------------- | ------------ | ---------- | ------------ |
| `--rule-names` argument | Explicit specification | Must remember names | Scripts and CI/CD |
| Project rule file   | Automatically loaded | Single file only | Project-fixed rules |
| Global rule file    | Applies to all projects | May not be suitable | Personal general standards |
| rules.yaml          | Centralized management and reuse | Must be predefined | Commonly used rule sets |
| @ interactive       | Quick and flexible search | Interactive scenarios only | Temporary needs |

**Notes:**

- The `@` completion feature is only available in interactive mode
- The completion list automatically merges all available rule sources
- When rules have the same name, the higher-priority rule overrides the lower-priority rule
- If there are many rule files, it is recommended to use the search feature to locate them quickly

### Detailed Explanation of Rule Loading Priority

When multiple rule sources are specified, the system merges rules in the following order:

1. **Global rule file** (`~/.haijunbot/rules/rule.md`)
2. **Project rule file** (`.haijunbot/rules/rule.md`)
3. **Rules specified via `--rule-names`**

When looking up a specified rule, the search order is:

1. Central rule repository
2. Project rule directory (`.haijunbot/rules/`)
3. Project `rules.yaml` file
4. Configured rule directory
5. Global `rules.yaml` file
6. Built-in rules (lowest priority)

### Usage Examples

#### Example 1: Using specific rules during code review

```bash
# Use only code review rules
haijunbot review --rule-names code_review,security
```

#### Example 2: Using multiple rules during refactoring

```bash
# Combine refactoring rules and clean code rules
haijunbot refactor --rule-names refactoring,clean_code
```

#### Example 3: Configure dedicated rules for a specific project

Create `.haijunbot/rules/my_project_rule.md` in the project root directory:

```markdown
# My project rules

**Project-specific requirements:**

- All API functions must return a unified format: `{"code": 0, "data": {...}, "msg": ""}`
- Database operations must be executed within a transaction
- All external calls must have a timeout setting (default 30 seconds)
```

When using:

```bash
cd /path/to/my/project
haijunbot code --rule-names my_project_rule,clean_code
```

---

## 🔧 Using Rule Placeholders

The HAIJUNBOT rule system supports using **Jinja2 template syntax**, allowing placeholders to be used in rule files to make rule content dynamic.

### Available Placeholder Variables

| Variable name           | Description              | Example value          |
| ----------------------- | ------------------------ | ---------------------- |
| `{{ current_dir }}`     | Current working directory (absolute path) | `/home/user/myproject` |
| `{{ script_dir }}`      | Directory where the script is located | `/path/to/haijunbot/...`  |
| `{{ haijunbot_data_dir }}` | haijunbot data directory    | `~/.haijunbot`            |
| `{{ haijunbot_src_dir }}`  | haijunbot source directory  | `/path/to/haijunbot`      |
| `{{ git_root_dir }}`    | Git repository root directory | `/home/user/myproject` |
| `{{ rule_file_dir }}`   | Directory where the rule file is located | `/home/user/...`       |

### Jinja2 Basic Syntax

#### Variable Output

```jinja2
{{ variable_name }}
```

Example:

```markdown
# Project root directory is: {{ git_root_dir }}

**Requirements:**

- Configuration files must be placed in the `{{ git_root_dir }}/config/` directory
- Test files must be placed in the `{{ git_root_dir }}/tests/` directory
```

After rendering:

```markdown
# Project root directory is: /home/user/myproject

**Requirements:**

- Configuration files must be placed in the `/home/user/myproject/config/` directory
- Test files must be placed in the `/home/user/myproject/tests/` directory
```

#### Conditionals

```markdown
{% if condition %}
Content
{% endif %}
```

Example:

```markdown
{% if git_root_dir != current_dir %}
**Note:** you are not currently in the project root directory; please switch to {{ git_root_dir }} before performing the operation
{% endif %}
```

#### Loops

```markdown
{% for item in list %}

- {{ item }}
  {% endfor %}
```

#### Comments

```markdown
{# This is a comment #}
```

### Practical Application Examples

#### Example 1: Referencing project-specific paths

```markdown
# Project file organization standards

**Directory structure that must be followed:**

Configuration files: `{{ git_root_dir }}/config/`
Source code: `{{ git_root_dir }}/src/`
Test code: `{{ git_root_dir }}/tests/`
Documentation: `{{ git_root_dir }}/docs/`

**Requirements:**

- All source code files must be placed in the `{{ git_root_dir }}/src/` directory
- Test files must be placed in the `{{ git_root_dir }}/tests/` directory
- Configuration files must be placed in the `{{ git_root_dir }}/config/` directory
```

#### Example 2: Dynamically generate rules based on the environment

```markdown
# Environment-specific configuration requirements

**Configuration file locations:**

Main configuration: `{{ haijunbot_data_dir }}/config/main.yaml`

{% if rule_file_dir == git_root_dir + "/.haijunbot/rules" %}
**Project-specific configuration:**

- Project configuration file: `{{ git_root_dir }}/.haijunbot/config.yaml`
- Use the project configuration to override the global configuration
  {% endif %}
```

#### Example 3: Standardizing paths

```markdown
# Use git_root_dir to ensure path consistency

**Log file location:**

Logs must be written to: `{{ git_root_dir }}/logs/app.log`

**Temporary file location:**

Temporary files must be placed in: `{{ git_root_dir }}/tmp/`

**Prohibited items:**

- Storing temporary files in the `{{ git_root_dir }}/src/` directory is forbidden
- Using hard-coded paths (such as `/tmp/` or `/var/log/`) is forbidden
```

### Best Practices for Using Placeholders

1. **Prefer using `git_root_dir`**: ensure paths are always relative to the project root directory
2. **Avoid hard-coded paths**: use placeholders instead of absolute paths
3. **Use conditionals reasonably**: generate different rules for different environments
4. **Add comments**: add comments explaining complex Jinja2 syntax
5. **Test the rendering result**: after creating a rule, test whether placeholders render correctly

### Frequently Asked Questions

**Q: What happens if placeholder rendering fails?**

A: If Jinja2 rendering fails (e.g. a syntax error), the system returns the original content and rule loading is not affected.

**Q: Can I define my own variables in a rule file?**

A: Not directly, but you can define temporary variables within the template using Jinja2's `set` statement.

**Q: Are placeholders rendered recursively?**

A: No, each rule file is rendered only once.

---

## 📝 Rule File Format Standards

### Basic Structure

Rule files use Markdown format, and the following structure is recommended:

````markdown
# Rule title

## Introduction/Background

Briefly describe the purpose and use cases of the rule.

## Core Principles

### Principle Name

**Execution requirements:**

- **Must**: mandatory requirement
- **Must not**: prohibited behavior

## Detailed Standards

### Subsection

**Check items:**

- [ ] Checkpoint 1
- [ ] Checkpoint 2

## Code Examples

### ❌ Bad practice

```python
# Incorrect example code
```
````

### ✅ Good practice

```python
# Correct example code
```

## Checklist

Before completing the task, you must confirm:

- [ ] Check item 1

- [ ] Check item 2

### Format Requirements

1. **Heading levels**: use `##` for top-level sections and `###` for subsections
2. **Emphasis markers**:
   - **Must**: mandatory requirement, use bold
   - **Must not**: prohibited behavior, use bold
   - Recommendation: recommended practice, use bold
3. **Checklist**: use the `- [ ]` format so the Agent can confirm items one by one
4. **Code examples**: use explicit headings to distinguish good/bad practices, such as `❌ Bad practice` and `✅ Good practice`

---

## 🎯 Best Practices for Writing Rules

### 1. Clarity Principle

**Requirements:**

- Use clear, unambiguous language
- Avoid using vague words (such as "as much as possible" or "appropriately")
- Clearly distinguish mandatory requirements from recommendations

**Example:**

❌ **Bad wording:**

```markdown
Functions should be as short as possible
```

✅ **Good wording:**

```markdown
**Must**: functions must not exceed 20 lines
```

### 2. Actionability Principle

**Requirements:**

- Each rule should be verifiable
- Provide specific criteria for judgment
- Include illustrative code examples

**Example:**

```markdown
**Naming requirements:**

- Variable names must clearly express their purpose
- Function names must clearly express their function
- Meaningless variable names (such as `a`, `b`, `x`, `temp`) are forbidden
```

### 3. Structure Principle

**Requirements:**

- Organize content in logical layers
- Keep related content together
- Use clear section headings to delineate content

**Recommended structure:**

1. Core Principles (highest priority)
2. Specific standards
3. Code examples
4. Checklist

### 4. Example-driven

**Requirements:**

- Each key standard should be accompanied by examples
- Use comparisons between "good practice" and "bad practice"
- Example code should be concise and easy to understand

---

## 📂 Rule Classification and Organization

### Naming Conventions

Rule file naming should follow the following principles:

- **Lowercase letters**: use lowercase letters and underscores
- **Descriptive**: the file name should clearly describe the rule content
- **Consistency**: similar rule usages share the same prefix

**Example:**

```text
clean_code.md        # Clean code standards
code_review.md       # Code review standards
rust_performance.md  # Rust performance optimization
```

### Classification Principles

Classify by the nature of the rules:

1. **General standards**: applicable to all languages and scenarios (e.g. `clean_code.md`)
2. **Language-specific**: standards for a specific language (e.g. `rust_performance.md`)
3. **Task-specific**: standards for a specific task (e.g. `code_review.md`)
4. **Domain-specific**: standards for a specific domain (e.g. `security.md`)

---

## 🚀 Complete Example of Creating a New Rule

### Scenario: Create a Python exception handling rule

#### Step 1: Determine the rule goal

Goal: guide the Agent to correctly handle Python exceptions

#### Step 2: Create the rule file

File path: `builtin/rules/python_exception_handling.md`

#### Step 3: Write the rule content

````markdown
# Python exception handling standards

## Core Principles You Must Follow

### 1. Catch exceptions explicitly (mandatory)

**Execution requirements:**

- **Must**: catch specific exception types and avoid using bare `except:`
- **Must**: only catch exceptions you are able to handle
- **Must not**: use `except:` to catch all exceptions
- **Must not**: catch and then do nothing (pass)

**Example:**

❌ **Bad practice:**

```python
try:
    data = load_config()
except:
    pass
```
````

✅ **Good practice:**

```python
try:
    data = load_config()
except FileNotFoundError:
    logger.error(f"Config file not found: {config_path}")
    raise
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON format: {e}")
    raise
```

### 2. Use finally to clean up resources

**Execution requirements:**

- **Must**: release resources in the `finally` block
- **Must**: use context managers to manage resources
- **Must not**: omit resource release in the `except` block

**Example:**

```python
# Use a context manager
with open('file.txt', 'r') as f:
    data = f.read()
    # The file is closed automatically
```

### 3. Provide meaningful error messages

**Execution requirements:**

- **Must**: record context information when catching exceptions
- **Must**: use structured logging to record exception details
- **Must not**: throw meaningless exceptions

## Exception Handling Checklist

Before submitting code, you must confirm:

- [ ] All exception catches are of specific types
- [ ] No bare `except:` is used
- [ ] Caught exceptions are handled or re-thrown
- [ ] Resources are released correctly (using `with` or `finally`)

- [ ] Exception messages contain sufficient context

### Step 4: Test the rule

Verify the effectiveness of the rule by having the Agent generate code with reference to it.

---

## ❓ Frequently Asked Questions and Notes

### Q1: How detailed should a rule be?

**A:** A rule should be detailed enough, but not excessive.

- ✅ A good rule: defines clear boundaries and expectations
- ❌ An excessive rule: lists all possible cases, making the document hard to read

### Q2: How should rule priority be handled?

**A:** Within a rule file, use the "Core Principles" section to mark the highest-priority content. If rules conflict with one another, resolve it through version numbers or an override mechanism.

### Q3: Do rules support inheritance or composition?

**A:** Rule files are independent, but a rule can reference other rules. For example, `rust_performance.md` can reference the basic principles in `clean_code.md`.

### Q4: How should existing rules be updated?

**A:** When updating a rule, you should:

1. Maintain backward compatibility, or clearly mark breaking changes
2. Update the version number (if any)
3. Notify team members that the rule has been updated
4. Provide a migration guide (if there are major changes)

### Q5: Can a rule file contain content in other languages?

**A:** Rule files are mainly written in Markdown, but can contain code examples in any language for illustration.

### Q6: How do I debug rule loading problems?

**A:** You can debug in the following ways:

1. Check whether the rule file path is correct
2. Confirm whether the rule file name (without the `.md` suffix) matches the `--rule-names` argument
3. Check whether there are Jinja2 syntax errors
4. Check whether the rule file encoding is UTF-8

### Q7: What should I do if multiple rules conflict?

**A:** When multiple rules conflict:

1. A rule loaded later overrides the same content in a rule loaded earlier
2. In `--rule-names`, a rule specified later has higher priority
3. It is recommended to explicitly mark priority in rules or use conditionals to avoid conflicts

---

## 📌 Notes

1. **Keep it concise**: rule files should be concise and clear, avoiding verbosity
2. **Regular review**: rules should be updated as technology evolves
3. **Team consensus**: the creation of rules should be based on team consensus
4. **Practical testing**: new rules should have their effectiveness verified in practice
5. **Documentation synchronization**: rule changes should be synchronized to the relevant documentation in a timely manner
6. **Encoding standards**: rule files must use UTF-8 encoding

---

## 🔗 Related Resources

- [builtin/rules/](https://github.com/takebox/HaijunBot/tree/main/builtin/rules) - built-in rule directory
- [builtin/rules/testing/](https://github.com/takebox/HaijunBot/tree/main/builtin/rules/testing) - built-in testing rule directory
- [docs/haijunbot_config.md](../haijunbot_config.md) - configuration system documentation
- [builtin_rules.py](https://github.com/takebox/HaijunBot/blob/main/src/haijunbot/haijunbot_code_agent/builtin_rules.py) - loading
- code_agent_rules.py - management

---

## 🤝 Contributing

Contributions of new rules or improvements to existing rules are welcome! Before submitting, please make sure that:

- You follow this best practices guide
- Rules are clear and unambiguous
- Sufficient examples are included
- Verified through practical testing
- UTF-8 encoding is used
- Jinja2 placeholders are used correctly (if needed)

---

## 📄 License

MIT License
