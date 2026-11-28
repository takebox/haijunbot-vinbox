# Introduction to HaijunBot Rule System (Rules)

## 1. Overview

### 1.1 What is the Rule System

The HaijunBot rule system is a Markdown-based collection of standardized instructions used to guide Agents in following unified standards and best practices during tasks such as code generation, code review, and refactoring. The rule system is the core mechanism by which HaijunBot achieves "behavioral standardization" and "knowledge reuse".

### 1.2 Value of the Rule System

- **Unified standards**: ensures consistent output style across different Agents
- **Quality assurance**: built-in checklists reduce code defects
- **Knowledge transfer**: documents best practices for easy team sharing
- **Flexible extension**: rules can be customized according to project needs
- **Dynamic rendering**: supports Jinja2 template syntax to make rule content dynamic
- **Extremely high extensibility**: the rule system is an extremely extensible system; track support, rules support, spec, and more can all be extended through this system

### 1.3 How the Rule System Works

The rule system works through the following mechanisms:

1. **Rule loading**: loads rule files from multiple sources (project rules, global rules, built-in rules, etc.)
2. **Rule merging**: merges rule content in priority order
3. **Rule injection**: injects rule content into the Agent's system prompt
4. **Dynamic injection**: supports dynamically referencing specific rules in user input

### 1.4 Extensibility of the Rule System

The rule system is an extremely extensible system. It is not only used for code standards; various features can also be extended through rules:

- **Track support**: various tracks can be defined and integrated through the rule system to extend the Agent's capabilities
- **Rules support**: the rule system itself supports defining new rules through rules, enabling recursive extension of rules
- **Spec support**: project specifications (specs) can be defined and generated through the rule system to guide project development
- **HaijunBot configuration**: HaijunBot's own configuration can also be handled through the rule system, enabling intelligent and automated configuration management
- **Rule expansion**: the expansion and enhancement of rules can also be done through the rule system, enabling self-improvement and iteration of rules
- **Other extensions**: any scenario that needs to guide Agent behavior can be implemented through the rule system

This design gives the HaijunBot system extremely high scalability; users can flexibly extend functionality according to their needs, and can even extend the rule system itself through the rule system.

---

## 2. Rule Types and Sources

### 2.1 Rule Tree Structure

The rule system is organized in a tree structure, with 3 root nodes serving as indexes:

1. **Built-in rules index** (`builtin_rules.md`): the index file for HaijunBot built-in rules, listing the categories and paths of all built-in rules
2. **Project rules directory** (`.haijunbot/rules/`): the directory for project-specific rule files
3. **Global rules directory** (`~/.haijunbot/rules/`): the directory for globally shared rule files

**Flexible referencing**: users can import rules from any node, using the following methods:

- **Reference by index**: use the rule name and the system looks it up in the index file (e.g. `clean_code`). Without a prefix, built-in rules are searched first, so the `builtin:` prefix is not needed
- **Reference by prefix**: use a prefix to explicitly specify the source, supporting relative paths (e.g. `project:architecture_design/solid`, `global:python_style`)

### 2.2 Rule Sharing

Rules support a sharing mechanism, allowing rules to be shared to the central rules repository for use by multiple projects.

#### Central Rules Repository

Specify the central rules repository via the `central_rules_repo` configuration, supporting:

- **Git repository URL**: the system automatically clones it to `~/.haijunbot/central_rules_repo`
- **Local directory path**: use a local directory directly

The central rules repository has the highest priority; if a rule with the same name exists, the central repository takes precedence. The system automatically performs a daily update check.

#### Rule Sharing Process

Local rules can be shared to the central rules repository via a command-line tool:

1. **Usage**: run `hca --share-rule` to start the rule sharing process

2. **Source**: you can select rules to share from the following locations
   - Project rules directory (`.haijunbot/rules/`)
   - Built-in rules directory (`builtin/rules/`)
   - Configured rule loading directories (`rules_load_dirs`)

3. **Share**: the selected rules are copied to the central rules repository, preserving the original directory structure

4. **Index update**: shared rules do not automatically update the index. If you need to update the index file for global rules (`~/.haijunbot/rules/rule.md`), you can request HaijunBot to scan the rules directories and update the index file in an interactive session

#### Rule Loading Directory Priority

The rule system searches for rules in the following priority order:

1. **Central rules repository** (`central_rules_repo`): highest priority
2. **Project rules directory** (`.haijunbot/rules/`)
3. **Configured rules directories** (`rules_load_dirs`): specified via configuration items, supporting multiple directories
4. **Global rules directory** (`~/.haijunbot/rules/`)
5. **Built-in rules** (`builtin/rules/`): lowest priority

### 2.3 Rule Types

The HaijunBot rule system supports the following types of rules:

#### Global Rules

- **Location**: `~/.haijunbot/rules/rule.md`
- **Scope**: all projects
- **Purpose**: personal general coding standards, global best practices

#### Project Rules

- **Location**: `<project root directory>/.haijunbot/rules/rule.md`
- **Scope**: current project
- **Purpose**: project-specific coding standards and business logic constraints

#### Naming Rules

Naming rules can be loaded from multiple sources, in priority order from high to low:

1. **Central rules repository** (highest priority)
   - Location: specified via the `central_rules_repo` configuration
   - Supports a local directory or a Git repository URL
   - Supports automatic cloning and daily updates

2. **Project `rules/` directory**
   - Location: `<project root directory>/.haijunbot/rules/`
   - Stores project-specific rule files (`.md` format)

3. **Configured rules directories**
   - Location: specified via the `rules_load_dirs` configuration item
   - Supports multiple directories, loaded in configuration order

4. **Global rules directory**
   - Location: `~/.haijunbot/rules/`
   - The directory for globally shared rule files

5. **Built-in rules** (lowest priority)
   - Location: `builtin/rules/` and `builtin/rules/testing/`
   - The rule set bundled with HaijunBot

### 2.4 Rule Reference Methods

The rule system supports multiple referencing methods; rules can be imported from any node of the tree structure:

#### Reference by Index (Recommended)

Use the rule name and the system automatically looks it up in the index file:

```bash
hca --rule-names clean_code,security
```

The system searches in priority order: central rules repository → project rules directory → configured rules directories → global rules directory → built-in rules index.

#### Explicitly Specify the Source by Prefix

Use a prefix to explicitly specify the rule source and avoid ambiguity. Rule names do not need to include the `.md` suffix; the system adds it automatically. Prefix references support relative paths:

- **`project:`**: project rules directory (e.g. `project:api_standard` or `project:architecture_design/solid`)
- **`global:`**: global rules directory (e.g. `global:python_style`)
- **`central:`**: central rules repository (e.g. `central:team_rule`)
- **`config1:`, `config2:`**: configured rules directories (numbered in configuration order)

**Notes**:

- Without a prefix the system searches built-in rules first, so the `builtin:` prefix is not needed
- Without a prefix, relative path references are not supported; relative paths are only supported with a prefix

**Examples**:

```bash
# Reference from project rules (root node rule)
hca --rule-names project:api_standard

# Reference from project rules (child node rule, using a relative path)
hca --rule-names project:architecture_design/solid

# Reference from global rules
hca --rule-names global:python_style

# Reference from the central rules repository
hca --rule-names central:team_rule

# Combined usage (built-in rules require no prefix)
hca --rule-names clean_code,project:api_standard
```

### 2.5 Rule Loading Priority

When multiple rule sources are specified, the system merges rules in the following order:

1. **Global rule file** (`~/.haijunbot/rules/rule.md`)
2. **Project rule file** (`.haijunbot/rules/rule.md`)
3. **Rules specified via `--rule-names`**

When looking up a specified rule (without a prefix), the search order is:

1. Central rules repository
2. Project rules directory (`.haijunbot/rules/`)
3. Configured rules directories
4. Global rules directory (`~/.haijunbot/rules/`)
5. Built-in rules index (`builtin_rules.md`)
6. Built-in rules directory (lowest priority)

**Note**: when referencing with a prefix, the specified source is searched directly and the priority order above is not followed.

---

## 3. Built-in Rules Overview

HaijunBot includes a rich set of built-in rules covering architecture design, development workflow, code quality, security standards, performance optimization, and more.

### 3.1 Architecture Design Rules

| Rule file                            | Purpose          | Use cases      |
| ------------------------------------ | ---------------- | -------------- |
| `solid.md`                           | SOLID design principles | Object-oriented design |
| `clean_architecture.md`              | Clean architecture | Architecture design |
| `clean_code.md`                      | Clean code standards | Code generation, refactoring |
| `code-reverse-design.md`             | Code reverse design rules | Code refactoring |
| `architecture-diagram-generation.md` | Architecture diagram generation rules | Architecture document generation |

### 3.2 Development Workflow Rules

| Rule file               | Purpose       | Use cases      |
| ----------------------- | ------------- | -------------- |
| `sdd.md`                | Spec-driven development | Design document writing |
| `tdd.md`                | Test-driven development | Test code generation |
| `refactoring.md`        | Refactoring guide | Code refactoring tasks |
| `c2rust_transpiler.md`  | C2Rust translation | Translating C code to Rust |
| `go2rust_transpiler.md` | Go2Rust translation | Translating Go code to Rust |

### 3.3 Code Quality Rules

| Rule file             | Purpose      | Use cases    |
| --------------------- | ------------ | ------------ |
| `code_review.md`      | Code review standards | Code review tasks |
| `documentation.md`    | Documentation writing standards | Documentation generation |
| `refactor-checker.md` | Refactoring inspector | Refactoring quality checks |

### 3.4 Security Standard Rules

| Rule file                   | Purpose          | Use cases    |
| --------------------------- | ---------------- | ------------ |
| `security.md`               | Secure coding standards | Security-related code |
| `vulnerability-analysis.md` | Security vulnerability analysis rules | Security auditing |

### 3.5 Performance Optimization Rules

| Rule file             | Purpose       | Use cases     |
| --------------------- | ------------- | ------------- |
| `performance.md`      | Performance optimization guide | Performance-sensitive code |
| `rust_performance.md` | Rust performance optimization | Rust code optimization |

### 3.6 UI Design Rules

| Rule file               | Purpose            | Use cases    |
| ----------------------- | ------------------ | ------------ |
| `dark-theme-design.md`  | Dark theme design rules | Front-end UI development |
| `light-theme-design.md` | Light theme design rules | Front-end UI development |
| `macos-web-design.md`   | macOS Web design standards | Web UI development |

### 3.7 Development Tool Rules

| Rule file              | Purpose      | Use cases    |
| ---------------------- | ------------ | ------------ |
| `script-generation.md` | Script generation rules | Script code generation |
| `track-development.md` | Track development rules | Track development |
| `mcp-integration.md`   | MCP integration rules | MCP tool integration |

### 3.8 Testing Standard Rules

| Rule file            | Purpose                        | Use cases       |
| -------------------- | ------------------------------ | --------------- |
| `cpp_test.md`        | C/C++ testing guide            | C/C++ code testing |
| `go_test.md`         | Go testing guide               | Go code testing |
| `javascript_test.md` | JavaScript/TypeScript testing guide | JS/TS code testing |
| `java_test.md`       | Java testing guide             | Java code testing |
| `php_test.md`        | PHP testing guide              | PHP code testing |
| `python_test.md`     | Python testing guide           | Python code testing |
| `ruby_test.md`       | Ruby testing guide             | Ruby code testing |
| `rust_test.md`       | Rust testing guide             | Rust code testing |

### 3.9 Tool Configuration Rules

| Rule file             | Purpose          | Use cases    |
| --------------------- | ---------------- | ------------ |
| `add_rule.md`         | New rule specification | When creating new rules |
| `alert-management.md` | Alert management rules | Alert handling |
| `self_config.md`      | Self-service configuration rules | Configuration file modification |
| `add_builtin_rule.md` | New built-in rule specification | Adding built-in rules |

### 3.10 Deployment Standard Rules

| Rule file                  | Purpose      | Use cases    |
| -------------------------- | ------------ | ------------ |
| `opensource-deployment.md` | Open-source deployment rules | Open-source project deployment |

---

## 4. Ways to Use Rules

### 4.1 Specify via Command-Line Arguments

Use the `--rule-names` argument to specify the rules to use:

```bash
# Use a single rule
hca --rule-names clean_code "Create a user module"

# Use multiple rules (comma-separated)
hca --rule-names clean_code,security,performance "Create an API"

# Combine project rules and built-in rules
hca --rule-names my_project_rule,clean_code "Create a feature"
```

### 4.2 Via the Project Rule File

Create a `.haijunbot/rules/rule.md` file and its content is loaded automatically:

```markdown
# .haijunbot/rules/rule.md

# This is a global rule that applies to all tasks

You must follow the following principles:

- Code must comply with the PEP 8 standard
- All public functions must have type annotations
- Unit tests must be written
```

### 4.3 Via the Global Rule File

Create a `~/.haijunbot/rules/rule.md` file to apply it to all projects:

```markdown
# ~/.haijunbot/rules/rule.md

# Global default rule

When writing Python code:

- You must use `f-strings` for string formatting
- The `print()` statement is forbidden (use the logging module)
```

### 4.4 Interactively Add Rules with @

Entering the `@` symbol in interactive input triggers the rule completion feature, allowing you to quickly select and insert the desired rules.

**Steps**:

1. **Trigger completion**: type the `@` symbol during interactive input
2. **Browse rules**: the system automatically displays a list of all available rules
3. **Select a rule**: use the up/down keys or the mouse to select the desired rule
4. **Automatic injection**: after confirming the selection, the rule content is automatically inserted into the input

**Completion priority**:

Rules are displayed and searched in the following order:

1. Central rules repository (highest priority)
2. Project rules directory (`.haijunbot/rules/`)
3. Configured rules directories
4. Global rules directory (`~/.haijunbot/rules/`)
5. Built-in rules directory (`builtin/rules/`)

**Use cases**:

- ✅ When you need to quickly switch between different rule sets
- ✅ When you don't remember the exact name of a rule
- ✅ When you want to combine multiple rules
- ✅ When you temporarily need to add extra rules
- ✅ During interactive development and debugging

---

## 5. Rule Injection Mechanism

### 5.1 System Prompt Injection

Rules (including global, project, and rules specified by `--rule-names`) are merged into a single string, wrapped in `<rules>...</rules>` tags, and injected into the Agent's system prompt.

**Important feature**: rules are preserved during context compaction. Because rules are part of the system prompt, and the system prompt is always retained during context compaction (it does not participate in compaction), rule content remains effective throughout the entire conversation and is not lost due to context compaction. This ensures that the Agent always follows rule constraints throughout task execution.

### 5.2 Dynamic Injection into User Input

Users can use the `'<rule:rule_name>'` marker in their input to dynamically inject a specific rule. The system intercepts this marker, looks up the corresponding rule content, and replaces it with content wrapped in `<rule>...</rule>` tags, inserting it directly into the user input.

**Example**:

```
> Create a user module '<rule:clean_code>'
```

is converted to:

```
> Create a user module <rule>
# Clean code standards
...
</rule>
```

---

## 6. Rule File Format

### 6.1 Basic Structure

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

````

### 6.2 Format Requirements

1. **Heading levels**: use `##` for top-level sections and `###` for subsections
2. **Emphasis markers**:
   - **Must**: mandatory requirement, in bold
   - **Must not**: prohibited behavior, in bold
   - Recommendation: recommended practice, in bold
3. **Checklist**: use the `- [ ]` format so the Agent can confirm items one by one
4. **Code examples**: use explicit headings to distinguish good/bad practices, such as `❌ Bad practice` and `✅ Good practice`

---

## 7. Rule Placeholders (Jinja2 Templates)

### 7.1 Available Placeholder Variables

| Variable name | Description | Example value |
|--------|------|--------|
| `{{ current_dir }}` | Current working directory (absolute path) | `/home/user/myproject` |
| `{{ script_dir }}` | Directory where the script is located | `/path/to/haijunbot/...` |
| `{{ haijunbot_data_dir }}` | haijunbot data directory | `~/.haijunbot` |
| `{{ haijunbot_src_dir }}` | haijunbot source directory | `/path/to/haijunbot` |
| `{{ git_root_dir }}` | Git repository root directory | `/home/user/myproject` |
| `{{ rule_file_dir }}` | Directory where the rule file is located | `/home/user/...` |

### 7.2 Usage Example

```markdown
# Project file organization standards

**Directory structure that must be followed:**

Configuration files: `{{ git_root_dir }}/config/`
Source code: `{{ git_root_dir }}/src/`
Test code: `{{ git_root_dir }}/tests/`

**Requirements:**

- All source code files must be placed in the `{{ git_root_dir }}/src/` directory
- Test files must be placed in the `{{ git_root_dir }}/tests/` directory
````

---

## 8. Best Practices for the Rule System

### 8.1 Principles for Writing Rules

1. **Clarity**: use clear, unambiguous language
2. **Actionability**: each rule should be verifiable
3. **Structure**: organize content in logical layers
4. **Example-driven**: each key standard should be accompanied by examples

### 8.2 Recommendations for Using Rules

1. **Project rules**: create a dedicated rule file for the project to ensure consistent code style
2. **Rule combinations**: combine multiple rules according to the task type
3. **Rule priority**: understand the rule loading priority to avoid conflicts
4. **Rule updates**: regularly review and update rules to keep best practices current
