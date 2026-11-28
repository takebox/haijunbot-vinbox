# Interactive Code Development with hca

## Overview

`hca` (HaijunBot Code Agent) is the code agent tool of the HaijunBot system, specifically designed for code modification, refactoring, and development tasks. Interactive mode allows you to have multi-turn conversations with the Agent and progressively refine the code implementation.

## Usage

Run the `hca` command directly (without arguments) to enter an interactive session. In an interactive session:

- You can continuously input multiple tasks, and the Agent will execute them in sequence
- Enter a blank line to exit the session

## Multi-line Input

In an interactive session, multi-line input is supported:

- **New line**: Press `Enter` to start a new line
- **Submit**: Press `Ctrl+J` or `Ctrl+]` to confirm submission
- **View history**: Press `Ctrl+O` to view and copy the conversation history
- **Exit program**: Press `Ctrl+X` to exit the program

## Referencing File Context

Using the `@` or `#` symbols in the input allows you to reference files:

- **`@`**: Reference files in the Git repository (obtained via `git ls-files`)
- **`#`**: Reference all files (excluding the `.git` directory)

After entering `@` or `#`, file completion is automatically triggered, and selecting a file automatically inserts its file path. The Agent will automatically read the content of these files as context.

## Built-in @ Commands

Using the `'<command name>'` format in the input allows you to invoke built-in commands:

### Session Management Commands

- **`'<Summary>'`**: Summarize current conversation history and clean up to start a new session
- **`'<Clear>'`**: Clear current conversation history
- **`'<Pin>'`**: Pin content - fix marked content to the top of session

  ```
  > '<Pin>' This is important information that needs to be pinned
  ```

- **`'<SaveSession>'`**: Save the current session to `.haijunbot/saved_session.json`
- **`'<RestoreSession>'`**: Restore the session from `.haijunbot/saved_session.json`
- **`'<ListSessions>'`**: List all saved session files

### Tools and Features Commands

- **`'<ToolUsage>'`**: Display tool usage instructions
- **`'<FixToolCall>'`**: Fix the last tool call error
- **`'<ReloadConfig>'`**: Reload configuration file

### Mode Switching Commands

- **`'<Quiet>'`**: Switch to unattended mode (non-interactive mode)

### Rule Reference Commands

- **`'<rule:rule name>'`**: Dynamically reference rules

### Quick Template Commands

These commands will be replaced by corresponding prompt templates:

- **`'<Web>'`**: Web search template
- **`'<Dev>'`**: Development requirement template
- **`'<Fix>'`**: Fix issue template
- **`'<Check>'`**: Static code check template
- **`'<FindRelatedFiles>'`**: Find related files template

## Interrupting LLM Output

When the Agent is generating a response, you can press `Ctrl+C` to interrupt the output. After interruption:

1. Agent stops current response generation
2. If currently in unattended mode, automatically exits unattended mode and switches to interactive mode
3. Prompts for user intervention information
4. Can input new instructions or additional information
5. If tool calls are detected, asks whether to continue processing tool calls

**Usage scenarios**:

- Agent output does not meet expectations, need to stop immediately
- Need to supplement important information
- Need to change task direction

## Unattended Mode

In an interactive session, you can use the `'<Quiet>'` command to switch to unattended mode:

```
> '<Quiet>' Execute this task without asking me any questions
```

Characteristics of unattended mode:

- Agent will not ask for user confirmation
- Automatically decides all choices
- Suitable for automated task execution
- **Automatically performs code review (review)**, unless disabled with the `--disable-review` parameter

**Notes**:

- When started with the `-n` or `--non-interactive` parameter, it defaults to unattended mode
- Using `'<Quiet>'` in an interactive session can temporarily switch to unattended mode
- In unattended mode, Agent will automatically complete all operations as much as possible
- **Code review is skipped in interactive mode**; it only runs automatically in unattended mode

## Notes

- When using the `-n` or `--non-interactive` parameter, it automatically exits after completing one task
- When specifying a task with the `--task` or `--task-file` parameter, it executes that task directly
- Agent remembers conversation history in current session and can reference previous context in subsequent tasks

---

**Document version**: v1.0  
**Last Updated**: 2025-01-12  
**Maintainer**: HaijunBot Team
