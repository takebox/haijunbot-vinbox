---
name: add_rule
description: Triggered when a new rule needs to be added, existing rules need to be managed, or a rule system needs to be configured. Triggered whenever the user mentions "adding a rule", "creating a rule", "writing a rule", "defining a rule", "rule management", or "rule configuration". Not triggered: only using load_rule to load an existing rule; only querying the rule list; only reading the content of a rule without modifying it; discussing rule concepts without involving creating/managing operations.
---

# Adding and Managing Rules Specification

When the user requests creating a new rule, modifying the rule system, or standardizing existing rules, follow this specification: determine the applicable scope, choose the proper storage location, and write the rule file with a unified structure.

## 1. First Determine the Applicable Scope: Global Rules vs Project Rules

- **Global rules**: applicable to all projects (general coding conventions, security baselines, performance strategies, etc.).
  - Storage location: under `{% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/`, either directly in the root directory or in category subdirectories.
- **Project rules**: applicable only to the current project (project-specific architecture conventions, development workflows, tool settings, etc.).
  - Storage location: `{% raw %}{{ git_root_dir }}{% endraw %}/.haijunbot/rules/<category>/<rule_name>.md`.

**Selection principles:**

1. Common to multiple projects → create it as a global rule;
2. Only for the current project → create it as a project rule;
3. Maintenance cost: changes to a global rule affect all projects, so proceed with caution;
4. Permissions: global rules usually require higher permissions (the data directory belongs to the user's private space; project rules travel with the repository).

**Workflow**: determine the type → place it in the corresponding path → create the rule file. Once created, the file is automatically scanned into the index; no manual registration is required.

## 2. Rule File Structure

```markdown
# rule title

## Rule Overview

(optional) one sentence describing what this rule does, when to use it, and the expected effect.

## Principles You Must Follow

(required) the core principles required by this rule. Describe each one in a paragraph:

- **Must**: specific requirements to follow
- **Forbidden**: explicitly forbidden items
   Multiple principles can be given in several subsections.

## Operations You Must Execute

(required) the specific operation steps or workflow required by this rule. Divide into sections by stage/step; the steps must be executable and verifiable.

## Practical Guidance

(optional) best practices, common mistakes, and notes.

## Self-Check Checklist

(optional) a checklist used to verify items one by one after completion:

- [ ] check item 1
- [ ] check item 2
```

> The above section names (Rule Overview / Principles You Must Follow / Operations You Must Execute) are the unified convention between rules and the methodology; be sure to write them accordingly to avoid a mismatched structure.

## 3. YAML Header (required for entry rules)

Place it at the top of the file:

```yaml
---
name: code_review # required: the rule name, must equal the file name (without .md), in lowercase English or pinyin
description: trigger description # required: used for indexing and automatic matching
license: MIT # optional: open source license identifier
---
```

- **name**: in lowercase English/pinyin, must match the file name (e.g. the name of `security.md` is `security`).
- **description**: the "trigger condition" written for the rule matcher, not a functional introduction. **It must be written in the "trigger/non-trigger" form**:
  ```text
  Triggered when [a clear scenario] is needed. Triggered whenever the user mentions "[keyword 1]", "[keyword 2]", or [a scenario]. Not triggered: [irrelevant condition 1]; [irrelevant condition 2]; [irrelevant condition 3].
  ```
  Writing tips:
  - It must include a trigger scenario, 2 to 5 quoted keywords, and 2 to 3 non-trigger conditions;
  - Only describe "when it should be used"; do not write a functional introduction, track description, or rule body;
  - Avoid being too short or vague; a total length of 80 to 200 characters is recommended.
- **license** (optional): `MIT` / `Apache-2.0` / `GPL-3.0` / `BSD-3-Clause`, etc.; it may be left empty if licensing is not involved.

Sub-rules (reference files cited by top-level rules) may omit the YAML header; when the header is missing, the index uses the file name in place of the description.

## 4. File Name Conventions

- Lowercase letters, underscore separation, ending in `.md`;
- No spaces, hyphens, or uppercase letters.
- Examples: ✅ `code_review.md`, `tdd.md`; ❌ `CodeReview.md`, `code-review.md`.
- The name should be short and indicate its purpose, avoiding names that are too generic (such as `rule.md`).

## 5. Archive by Category

Rules are placed in subdirectories named by topic. Common categories (not mandatory; new ones may be created as needed):

| Category directory        | Covered content                                |
| ------------------------- | ---------------------------------------------- |
| `architecture_design`     | Architecture/design patterns/code organization |
| `code_quality`            | Code conventions/review/documentation/build validation |
| `deployment`              | Deployment/release/environment/CI-CD           |
| `development_tools`       | Tool usage/script generation/tool configuration |
| `development_workflow`    | Methodology/development workflow/collaboration (such as TDD, SDD, refactoring) |
| `performance`             | Performance analysis/optimization/resource management |
| `security`                | Secure coding/vulnerability analysis/security testing |
| `tool_config`             | Tool and rule system configuration (such as this file) |
| `ui_design`               | Interface conventions/theme design             |

Choosing a category: each rule belongs to only one category, filed under its most core topic; if unsure, refer to the directory where similar built-in rules are located.

## 6. Jinja2 Template Variables

Rule files support Jinja2. The following variables can be used to write relative paths; **do not hardcode absolute paths**:

| Variable                                     | Meaning                                   |
| -------------------------------------------- | ----------------------------------------- |
| `{% raw %}{{ rule_file_dir }}{% endraw %}`   | The directory of this rule file (absolute path) |
| `{% raw %}{{ git_root_dir }}{% endraw %}`    | The Git repository root directory         |
| `{% raw %}{{ current_dir }}{% endraw %}`     | The current working directory             |
| `{% raw %}{{ haijunbot_src_dir }}{% endraw %}`  | The HaijunBot source directory               |
| `{% raw %}{{ haijunbot_data_dir }}{% endraw %}` | The HaijunBot data directory (usually `~/.haijunbot`) |

Usage tips:

- To reference a sub-rule in the same directory: directly write `{% raw %}{{ rule_file_dir }}{% endraw %}/sub_rule.md`; **do not** add a redundant category prefix in front;
- Use `{% raw %}{{ git_root_dir }}{% endraw %}` for locations inside the project, and `{% raw %}{{ haijunbot_data_dir }}{% endraw %}` for data locations;
- Reference these variables in the rule body as needed; when you need to display the literal "{{ ... }}", wrap it with `{% raw %}...{% endraw %}` to avoid being parsed as a template.

**⚠️ Key point: do not mix up `git_root_dir` and `haijunbot_src_dir`**

- `{% raw %}{{ git_root_dir }}{% endraw %}` is resolved by `git rev-parse`, and **points to the root of the repository where the current working directory is located**; when run outside a repository, it falls back to the current working directory and the path becomes invalid. It is only suitable for referring to locations inside **the user's own project** (such as `{% raw %}{{ git_root_dir }}{% endraw %}/.haijunbot/rules/...`, `{% raw %}{{ git_root_dir }}{% endraw %}/project_info/...`).
- `{% raw %}{{ haijunbot_src_dir }}{% endraw %}` is resolved by tracing up from the source location, **is independent of the running directory**, and is the only stable locator variable for HaijunBot's own resources.
- **Forbidden**: using `{% raw %}{{ git_root_dir }}{% endraw %}` to point to HaijunBot's own resources (`browser_extension/`, `docs/`, `builtin/rules/`, `CHANGELOG.md`, `.haijunbot/`, etc.). Users often run outside the repository; at that time `git_root_dir` degrades to the current directory and all such paths become invalid.
- Correct usage: to point to HaijunBot's own resources, always use `{% raw %}{{ haijunbot_src_dir }}{% endraw %}`, and note the difference between resources at the repository root (concat directly, e.g. `{% raw %}{{ haijunbot_src_dir }}{% endraw %}/browser_extension/...`) and source code inside the Python package (which must include `src/haijunbot`, e.g. `{% raw %}{{ haijunbot_src_dir }}{% endraw %}/src/haijunbot/haijunbot_tools/...`).

## 7. Companion Scripts (as needed)

If a rule needs automated auxiliary operations, companion scripts may be placed alongside it, named the same as the rule with the language distinguished by the file extension (e.g. `code_review.md` ↔ `scripts/code_review.py`).

- Location: project `{% raw %}{{ git_root_dir }}{% endraw %}/.haijunbot/rules/<category>/scripts/`, global `{% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/<category>/scripts/`.
- When referencing them in rules, use variable paths, e.g.: `{% raw %}{{ rule_file_dir }}{% endraw %}/scripts/code_review.sh`.
- Scripts should be executable, as independent as possible, and include error handling; external dependencies can be documented with a `requirements.txt` / `package.json` / `DEPENDENCIES.md` file in the same directory.

## 8. Best Practices and Maintenance

**When designing a rule**

- Single responsibility: one rule focuses on only one topic;
- Actionable: write it so specific that it can be executed, avoiding empty talk (compare: ❌"the code should be written well" vs ✅"the function body should not exceed 50 lines");
- Verifiable: provide explicit acceptance/check items;
- Consistent with each other: adjacent rules should not conflict with one another.

**Common mistakes**

- Rules are too abstract and have no examples;
- The YAML header is missing, or the description is not written in the trigger/non-trigger form;
- Conflicts between rules;
- Hardcoded absolute paths.

**Maintenance**

- Periodically review whether the rules are still applicable, and update them as the project evolves;
- Delete rules that are outdated or no longer used;
- Record rule changes when necessary.
