---
name: plantuml_fix
description: Triggered when there is a need to fix or validate a PlantUML code block. Triggered whenever the user mentions "PlantUML", "UML diagram", "diagram fix", or "syntax error". Not triggered: only generating PlantUML without fixing; non-PlantUML diagrams; Mermaid diagrams.
license: MIT
---

# PlantUML Fix Rule

## Rule Overview

This rule is used to fix PlantUML code blocks in Markdown files. PlantUML is a commonly used UML diagram drawing tool; however, syntax errors or formatting problems may occur when it is embedded in Markdown files.

**Workflow:**

1. **Extract**: use a script to extract the PlantUML code blocks from the Markdown file into separate `.puml` files
2. **Validate**: use a script to call the PlantUML program to validate the syntax of the `.puml` files and report errors
3. **Fix**: the AI fixes the content of the `.puml` files based on the error messages
4. **Write back**: use a script to write the fixed `.puml` file content back into the Markdown file

**Important notes:**

- The script is only responsible for extraction, validation reporting, and writing back
- The fixing work is done by the AI; the AI needs to manually fix the `.puml` files based on the validation error messages

## The Principles You Must Follow

### 1. The Safety Principle

**Requirements:**

- **Must**: back up the original file before modifying
- **Must**: verify the availability of the PlantUML program before performing the fix
- **Forbidden**: directly overwriting the original file without keeping a backup

### 2. The Accuracy Principle

**Requirements:**

- **Must**: accurately extract the PlantUML code blocks (including the start and end markers)
- **Must**: use the official PlantUML program for syntax validation
- **Must**: preserve the indentation and formatting of the original code
- **Forbidden**: modifying the content of non-PlantUML code blocks

## The Operations You Must Execute

### Operation 1: Check the environment dependencies

**Execution steps:**

1. Check whether the Python environment is available
2. Check whether the PlantUML program is installed (the `plantuml` command or a Java jar file)
3. Verify the script file exists: `{{ rule_file_dir }}/plantuml_fix.py`

### Operation 2: Extract the PlantUML code blocks

**Execution steps:**

```bash
python3 {{ rule_file_dir }}/plantuml_fix.py extract <markdown_file>
```

The script will:

- Extract all PlantUML code blocks from the Markdown file
- Create a separate `.puml` file for each code block
- Automatically add the `@startuml` and `@enduml` markers (if missing)
- Output by default to the system temporary directory (e.g. `/tmp/plantuml_<filename>/`), avoiding git management
- Use the `-o` parameter to specify an output directory

### Operation 3: Validate the PlantUML syntax

**Execution steps:**

```bash
python3 {{ rule_file_dir }}/plantuml_fix.py validate <filename>_plantuml/
```

Or use the plantuml command directly:

```bash
plantuml -checkonly <filename>_plantuml/*.puml
```

### Operation 4: The AI fixes the .puml files

**Execution steps:**

1. Based on the validation error messages, use the `edit_file` (find and replace) or `write_file` (rewrite the whole file) tool to fix the `.puml` files
2. Common fixes include:
   - Fixing arrow syntax (`-->`, `->`, etc.)
   - Adding missing semicolons
   - Fixing comment formatting
   - Adding missing `@startuml`/`@enduml` markers

### Operation 5: Write the fixed content back to the Markdown

**Execution steps:**

```bash
python3 {{ rule_file_dir }}/plantuml_fix.py writeback <markdown_file> <puml_dir>
```

The script will:

- Automatically back up the original Markdown file (with a `.bak` suffix)
- Replace the content back into the corresponding PlantUML code blocks
- Keep the rest of the Markdown file unchanged

## Checklist

After completing the task, be sure to confirm:

- [ ] The script file has been created at `{{ rule_file_dir }}/plantuml_fix.py`
- [ ] The rule file has been created at `{{ rule_file_dir }}/plantuml_fix.md`
- [ ] The script has executable permissions
- [ ] The PlantUML program is correctly installed
- [ ] The PlantUML code blocks in the test file can be correctly extracted
- [ ] The fixed code can pass the PlantUML syntax validation
- [ ] The fixed content has been correctly written back to the Markdown file

## Common Error Types and Fix Methods

### 1. Version compatibility issues

**Problem:** directives such as `!theme plain` are not supported in old versions (e.g. 1.2020.02)

**Fix method:**

- Remove the unsupported `!theme` directive
- Check the PlantUML version: `plantuml -version`
- Use `-checkonly` to verify syntax compatibility

### 2. Activity Diagram syntax problems

**Problem:** a standalone code line is not valid syntax

```plantuml
# incorrect example
::call function;
enqueueCommandInLane();  # a standalone code line is invalid
```

**Fix method:** merge the code into a description line

```plantuml
# correct example
::call function enqueueCommandInLane();
```

### 3. Variable assignment syntax problems

**Problem:** a standalone variable assignment line is invalid

```plantuml
# incorrect example
::initialize;
count = 1;  # a standalone assignment line is invalid
```

**Fix method:** merge the assignment into a description line

```plantuml
# correct example
::initialize count = 1;
```

### 4. Conditional statement syntax problems

**Problem:** `if`/`elseif` is missing the `then` keyword

```plantuml
# incorrect example
if (condition?) (yes)
  :operation;
else (no)
  :other operation;
endif
```

**Fix method:** add the `then` keyword

```plantuml
# correct example
if (condition?) then (yes)
  :operation;
else (no)
  :other operation;
endif
```

### 5. Multi-line object literal problems

**Problem:** an object literal spanning multiple lines or causing parsing errors

```plantuml
# incorrect example
::call function func({
  key1: value1,
  key2: value2
});
```

**Fix method:** merge into a single line or use a variable

```plantuml
# correct example
::call function func({ key1: value1, key2: value2 });
```

### 6. Arrow syntax problems

**Problem:** the arrow syntax is incorrect

```plantuml
# incorrect example
A -> B: message
A --> B: message
```

**Fix method:** use the correct arrow according to the diagram type

- Class diagram: use `-->` or `--*`, etc.
- Sequence diagram: use `->` or `-->`
- Activity diagram: use `->` to connect activities

## Fix Strategy Summary

### The Minimal Modification Principle

1. Only fix syntax errors; do not change the semantics
2. Keep the indentation and formatting of the original code
3. Prefer merging code lines over deleting them

### Fix Order

1. First fix version compatibility problems (such as removing`!theme`)
2. Then fix syntax structure problems (such as `if`/`then`)
3. Finally fix code line merging problems

### Validation Method

```bash
# validate each file one by one
for f in *.puml; do
  echo "checking $f"
  plantuml -checkonly "$f"
done

# or validate in batch
plantuml -checkonly *.puml
```

## Related Resources

- PlantUML official documentation: <https://plantuml.com/>
- PlantUML syntax reference: <https://plantuml.com/zh/>
- Activity Diagram syntax: <https://plantuml.com/activity-diagram-beta>
- PlantUML version history: <https://plantuml.com/changes>
