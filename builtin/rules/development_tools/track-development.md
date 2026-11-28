---
name: track-development
description: Triggered when there is a need to develop or install a HaijunBot Track feature. Triggered whenever the user mentions "install track", "install a track", "Track development", "feature extension", "plugin development", or "add a track". Not triggered: only using an existing Track without developing; only configuring Track parameters; Agent development that does not involve a Track.
---

# Track Development Rule

## Rule Introduction

This rule defines the standardized process and requirements for track development, ensuring the standardization of track addition and the accuracy of feature analysis.

This rule applies to the following scenarios:

- **Git repository track addition**: clone a track from a remote Git repository
- **Local path track addition**: validate a local track path

A track can be a local path or a Git repository. A Git repository track is cloned directly into the `{{ haijunbot_data_dir }}/rules/` directory.

## Jinja2 Variable Usage Guide

### Available Built-in Variables

The following Jinja2 template variables are available in track documentation files:

| Variable name                                       | Description                 | Example value                   |
| -------------------------------------------- | -------------------- | ------------------------ |
| `{% raw %}{{ rule_file_dir }}{% endraw %}`   | The directory containing the current rule file | `/path/to/builtin/rules` |
| `{% raw %}{{ git_root_dir }}{% endraw %}`    | Git repository root directory       | `/home/user/project`     |
| `{% raw %}{{ current_dir }}{% endraw %}`     | Current working directory         | `/home/user/project/src` |
| `{% raw %}{{ haijunbot_src_dir }}{% endraw %}`  | HaijunBot source code directory      | `/home/user/haijunbot`      |
| `{% raw %}{{ haijunbot_data_dir }}{% endraw %}` | HaijunBot data directory      | `/home/user/.haijunbot`     |

**⚠️ Important note:**

`{% raw %}{{ rule_file_dir }}{% endraw %}` represents the absolute path of **the directory containing the current rule file**. When referencing a file in the same directory, directly use `{% raw %}{{ rule_file_dir }}{% endraw %}/file name.md`; do **not** add the directory level again.

**Example**: if the rule file is in the `builtin/rules/tool_config/` directory and you are referencing `add_rule.md` in the same directory, you should write `{% raw %}{{ rule_file_dir }}{% endraw %}/add_rule.md`; the **wrong** way is `{{ rule_file_dir }}/tool_config/add_rule.md`.

### Variable Usage Examples

#### Example 1: Referencing a path in track documentation

```markdown
### Track file location

The track file is located at: `{% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/my_track/`
```

#### Example 2: Dynamically generating a path

```markdown
### Document path

- Track directory: `{% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/[track_name]/`
- Track rule file: `{% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/[track_name]/TRACK.md`
```

#### Example 3: Using variables in a code example

```markdown
### Install command

`` `bash
cd {% raw %}{{ haijunbot_data_dir }}{% endraw %}/rules/my_track/
pip install -r requirements.txt
`` `
```

### 1. Path Validation Principle

- **Must**: before processing any input, first validate its validity
- **Must**: for a Git URL, confirm the format is correct
- **Must**: for a local path, confirm the path exists and is accessible
- **Forbidden**: directly using an unvalidated path or URL

### 2. Track Analysis Principle

- **Must**: analyze the core functionality and characteristics of the track
- **Must**: prioritize reading documentation files such as README, package.json, and setup.py
- **Must**: choose an appropriate analysis method according to the track's complexity
- **Forbidden**: inferring functionality only from the file name or directory name

**Analysis strategy:**

- **Simple track** (number of files < 50, clear documentation): directly read key files and summarize the functionality
- **Complex track** (number of files ≥ 50, complex or missing documentation): use `task_list_manager` to create a task list for in-depth analysis

## Workflow You Must Follow

### Stage 1: Input Processing and Validation

1. **Receive user input** (local path or Git URL)
2. **Determine the input type**:
   - If it is a Git URL (starting with `http://`, `https://`, `git@`) → go to Stage 2
   - If it is a local path → go to Stage 3

### Stage 2: Git Repository Processing

1. **Check the rules directory**: verify whether the `{{ haijunbot_data_dir }}/rules` directory exists, and create it if it does not
2. **Extract the repository name**: extract the repository name from the Git URL (for example: `https://github.com/user/repo.git` → `repo`)
3. **Execute the clone operation**:

   ```bash
   git clone <url> {{ haijunbot_data_dir }}/rules/<repo_name>
   ```

4. **Handle clone failure**: ask the user how to handle it (retry, change the URL, or give up)
5. **Verify the clone result**: confirm that the cloned directory is valid

**Optimization strategy:**

- For large repositories use a shallow clone: `git clone --depth 1 <url>`
- Ask the user whether to overwrite when the target directory exists

### Stage 3: Local Path Validation

1. **Path existence check**: confirm the path exists
2. **Path readability verification**: verify that the path has read permission
3. **Error handling**: when the path is invalid, ask the user to confirm the correct path

### Stage 4: Track Function Analysis

1. **Read key documentation** (by priority):
   - `README.md`, `README.rst`, `README.txt`
   - `package.json` (Node.js project)
   - `setup.py`, `pyproject.toml` (Python project)
   - `Cargo.toml` (Rust project)
   - `pom.xml` (Java project)

2. **Information extraction and analysis**:
   - Track name recognition
   - Core function description
   - Main characteristics summary
   - Applicable scenario analysis

3. **Complexity assessment**:
   - Count the number of files in the track directory
   - Judge documentation completeness
   - For complex tracks, use `task_list_manager` to create in-depth analysis tasks

**Handling missing information:**

- When documentation is missing, infer from the directory structure
- When inference is difficult, use a basic description: `[track name] - functionality to be improved`

## Specific Requirements and Conventions

### 1. Input Validation Convention

- **Git URL format**: must support standard formats such as `http://`, `https://`, and `git@`
- **Local path format**: must support both absolute and relative path resolution
- **Path validity**: must verify path existence and access permission
- **Input type determination**: must accurately distinguish a Git URL from a local path

### 2. Git Operation Convention

- **Clone directory structure**: `{{ haijunbot_data_dir }}/rules/<repo_name>`
- **Clone failure handling**: must provide options such as retry, change URL, and give up
- **Repository name extraction**: must correctly parse the repository name from the URL
- **Shallow clone optimization**: large repositories must use the `--depth 1` parameter

### 3. Track Analysis Convention

- **Documentation reading priority**: README → package.json → setup.py → Cargo.toml → pom.xml
- **Information extraction completeness**: should include track name, function description, main characteristics, and applicable scenarios
- **Complexity assessment standard**: number of files < 50 is a simple track, ≥ 50 is a complex track
- **Analysis method selection**: simple tracks are read directly, complex tracks use `task_list_manager`

### 4. Rule File Format Convention

- **Track rule file**: the rule file (such as TRACK.md) under the `{{ haijunbot_data_dir }}/rules/[track_name]/` directory
- **Top-level rule required**: the rule file serving as the Track's main entry should contain a YAML front matter header
- **Sub-rules optional**: detailed sub-rule files referenced by the main rule may omit the header
- **Trigger condition description**: should clearly explain the trigger conditions in the `description` field of the track rule file's YAML front matter, including trigger keywords, user intent, or applicable scenarios

**Trigger condition description requirements:**

- **Must**: use clear expressions such as "triggered when..." or "triggered whenever the user mentions..."
- **Must**: clearly list the trigger keywords or phrases
- **Must**: explain the applicable business scenario or user intent
- **Forbidden**: using vague or ambiguous trigger condition descriptions

**Trigger condition description example:**

```yaml
---
name: code_review
description: Use this rule when the user needs to perform a code review. Triggered whenever the user mentions code review, reviewing code, checking code quality, or needs to perform a code review or quality check.
license: MIT
---
```

Wrong example:

```yaml
---
description: Code review rule
---
```

**Header field descriptions:**

- **name** (required): the unique identifier name of the track
  - **Must** use the file name (without the .md suffix)
  - **Must** use English or pinyin; Chinese is not recommended
  - Example: `code_review`, `pptx_generator`

- **description** (required): a detailed description of the track's trigger scenarios
  - **Must** use a clear expression to explain the trigger conditions
  - **Must** list the trigger keywords
  - Example see above

- **license** (optional): open source license identifier
  - Common licenses: `MIT`, `Apache-2.0`, `GPL-3.0`
  - If no special authorization is needed, it may be omitted

### 5. Error Handling Convention

- **Git clone failure**: network check, URL validation, user interaction handling
- **Path validation failure**: user confirmation, spell check, re-input
- **Track analysis failure**: basic description, user manual input, feature-to-be-improved marker

## Practical Guidance

### Best Practice Recommendations

1. **Preprocessing validation**: before performing any operation, first conduct a comprehensive input validity check
2. **Progressive analysis**: start from simple documentation and gradually go deeper into complex analysis
3. **User interaction optimization**: provide clear choices and prompts at key decision points
4. **Error recovery mechanism**: consider failure situations and recovery strategies at each stage

### Performance Optimization Recommendations

1. **Use shallow clone**: prefer a shallow clone for large repositories
2. **Documentation caching**: analyzed track information may be cached to avoid repeated analysis
3. **Parallel processing**: batch processing optimization may be considered when adding multiple tracks

### Quality Control Recommendations

1. **Multi-source verification**: combine multiple documentation sources for cross-verification
2. **Feature completeness check**: ensure the extracted function description is accurate and comprehensive
3. **Format consistency verification**: the rule file format must conform to the specification

## Execution Checklist

After completing the task, be sure to confirm all of the following items are completed:

### Input Validation Check

- [ ] The input type is accurately determined (Git URL or local path)
- [ ] The Git URL format validation passed
- [ ] The local path existence and readability validation passed

### Git Operation Check

- [ ] The rules directory structure check is correct (`{{ haijunbot_data_dir }}/rules/`)
- [ ] The repository name is extracted accurately
- [ ] The Git clone operation executed successfully
- [ ] The clone failure handling mechanism took effect

### Track Analysis Check

- [ ] Key documentation files have been read
- [ ] The track function description is generated accurately
- [ ] The complexity assessment standard is applied correctly
- [ ] The analysis method is chosen appropriately

### Quality Control Check

- [ ] The Markdown syntax is correct with no errors
- [ ] The rule file format conforms to the specification
- [ ] The error handling mechanism is complete
- [ ] The user interaction flow is clear

## Error Handling Convention

### Git Clone Failure Handling

**Should execute:**

1. **Network connection check**: verify network connectivity
2. **URL format validation**: confirm the correctness of the Git URL format
3. **User interaction handling**: provide options such as retry, change URL, and give up

**Handling flow:**

- **Retry mechanism**: allow the user to re-execute the clone operation
- **URL change**: support the user entering a new Git URL
- **Give-up handling**: provide a complete exit mechanism

### Path Validation Failure Handling

**Should execute:**

1. **User confirmation mechanism**: ask and confirm the correct path
2. **Spell check prompt**: provide path spell check suggestions
3. **Re-input opportunity**: allow the user to re-enter the path

### Track Analysis Failure Handling

**Should execute:**

1. **Basic description provided**: use the directory name as the track name
2. **User manual input option**: allow the user to manually provide a function description
3. **Feature-to-be-improved marker**: use the standard format "[track name] - functionality to be improved"

**Degradation handling:**

- **Documentation missing response**: infer functionality based on the directory structure
- **Analysis difficulty handling**: use a standardized to-be-improved description
- **User participation mechanism**: provide a manual input and confirmation flow

## Related Resources

- **Reference rule**: `{{ rule_file_dir }}/../tool_config/add_rule.md`
- **Track directory**: `{{ haijunbot_data_dir }}/rules/` (the unified storage location for Git repository tracks and local tracks)
