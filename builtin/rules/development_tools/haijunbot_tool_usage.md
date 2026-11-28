---
name: haijunbot_tool_usage
description: Triggered when the HaijunBot tool system needs to be used or learned. Triggered whenever the user mentions "tool usage", "tool configuration", "tool learning", "haijunbot-tool". Not triggered: only calling tools without learning/configuration; Agent-related operations; rule-related operations.
---

# HaijunBot Tool CLI Usage Rules

## Rule Introduction

This rule explains how to use the `haijunbot-tool` command-line tool to manage and view tool information in the HaijunBot tool system.

## Available Commands

### 1. The list command

**Function:** List all available tools

**Syntax:**

```bash
haijunbot-tool list [OPTIONS]
```

**Options:**

- `--json`: output in JSON format
- `--detailed`: show detailed information (including parameter definitions)

**Examples:**

```bash
# simple list
haijunbot-tool list

# detailed information
haijunbot-tool list --detailed

# JSON format
haijunbot-tool list --json

# detailed JSON format
haijunbot-tool list --detailed --json
```

### 2. The show command

**Function:** Show detailed information for the specified tool

**Syntax:**

```bash
haijunbot-tool show TOOL_NAME [OPTIONS]
```

**Arguments:**

- `TOOL_NAME`: the name of the tool to view (required)

**Options:**

- `--json`: output in JSON format

**Examples:**

```bash
# view tool details
haijunbot-tool show execute_script

# JSON format
haijunbot-tool show execute_script --json
```

## Common Use Cases

### Scenario 1: View all available tools

```bash
haijunbot-tool list
```

### Scenario 2: View the detailed parameters of a tool

```bash
haijunbot-tool show read_code
```

### Scenario 3: Get tool information in JSON format (for script processing)

```bash
haijunbot-tool show edit_tool --json
```

### Scenario 4: View the tool list with parameter definitions

```bash
haijunbot-tool list --detailed
```

## Related Resources

- CLI implementation location: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_tools/eli/main.py`
- Tool registry: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_tools/registry.py`
