---
name: haijunbot_agent_cli_invocation
description: Use this rule when you need to invoke the HaijunBot general agent or code agent via the command line — the HaijunBot Agent CLI invocation specification. It includes: determining whether a task is a general requirement or a code development requirement; checking before launch whether the hjb or hca command is correctly installed; entering the target working directory before launching the command; always using non-interactive mode for unattended invocation; passing a clear and complete requirement description directly on the command line; specifying the background, goals, constraints, deliverables, and acceptance criteria in the requirement; choosing hjb for general tasks and hca for code development tasks; and performing the necessary result checks and failure handling before and after execution. Trigger this whenever the user mentions "invoke hjb", "invoke hca", "unattended HaijunBot execution", "launch agent from the command line", "have the agent execute a task", or when another agent needs to correctly invoke the HaijunBot agent via the CLI.
---

# HaijunBot Agent CLI Invocation Specification

## Rule Introduction

This rule is used to guide other agents to correctly invoke the HaijunBot general agent (`hjb`) and code agent (`hca`) via the command line. The goal is to ensure that the invocation process is automatable, reproducible, and auditable, and to avoid execution failures caused by a missing command, an incorrect directory, interactive blocking, or an incomplete requirement description.

## Principles You Must Follow

### 1. Choose the Correct Agent Type

**Requirement description:**

- **Must**: Use `hjb` for general requirements, information organization, research and analysis, document writing, and process-oriented tasks
- **Must**: Use `hca` for code-related tasks such as code development, code modification, refactoring, test supplementation, and build fixes
- **Forbidden**: Assigning an explicitly code-development task to `hjb`
- **Forbidden**: Assigning a purely general task to `hca` by default

### 2. Check Whether the Command Is Available Before Launch

**Requirement description:**

- **Must**: Check whether the command is already installed before invoking `hjb` or `hca`
- **Must**: If the command does not exist, report an error immediately and give a clear prompt
- **Forbidden**: Invoking directly without confirming that the command exists

**Example:**

```bash
command -v hjb >/dev/null 2>&1 || {
  echo "ERROR: hjb is not installed or not in PATH" >&2
  exit 1
}

command -v hca >/dev/null 2>&1 || {
  echo "ERROR: hca is not installed or not in PATH" >&2
  exit 1
}
```

### 3. Enter the Working Directory Before Launch

**Requirement description:**

- **Must**: Switch to the target working directory first, then execute the agent command
- **Must**: The working directory should be consistent with the task context, for example the root directory of the target repository or a specified subdirectory
- **Forbidden**: Launching the agent directly in an unknown directory, a temporary directory, or the wrong directory

**Example:**

```bash
cd /path/to/project || {
  echo "ERROR: cannot enter working directory /path/to/project" >&2
  exit 1
}
```

### 4. Must Use Non-interactive Mode

**Requirement description:**

- **Must**: Use non-interactive mode to avoid waiting for manual input
- **Must**: Ensure the invocation method is suitable for unattended execution
- **Forbidden**: Using an invocation method that requires manual confirmation, manual supplementary input, or entering an interactive session

**Example:**

```bash
hjb -n --task "..."
hca -n --task "..."
```

### 5. The Requirement Must Be Passed Directly on the Command Line and Be Described Completely

**Requirement description:**

- **Must**: Pass the requirement directly through command-line arguments, without relying on subsequent interactive supplementation
- **Must**: The requirement description must be clear, complete, and executable
- **Must**: At minimum include the following information:
  - **Background**: The current task background, context, and business purpose
  - **Goal**: What you want to accomplish
  - **Scope/Constraints**: Modifiable scope, forbidden modification scope, technical limitations, and style requirements
  - **Deliverables**: What result you want output
  - **Acceptance criteria**: How to judge that the task is complete
- **Forbidden**: Passing only a vague short sentence, such as "fix it", "take a look at this issue", or "handle it for me"
- **Forbidden**: Omitting acceptance criteria or key context

**Good requirement example:**

```text
Background: The current project is a Python CLI tool, and a new built-in rule needs to be added so that other agents can correctly invoke hjb and hca.
Goal: Add a rule file and ensure the content covers command installation detection, working directory switching, non-interactive invocation, and task description standards.
Scope and constraints: Only the rule files under the builtin/rules directory may be modified; follow the existing built-in rule format; do not modify the Python runtime code.
Deliverables: Add 1 rule file; supplement the rule index or registration information if necessary.
Acceptance criteria: The rule file naming is compliant, the YAML header is complete, load_rule can load it normally, and the rule body clearly explains the correct way to invoke hjb/hca.
```

**Bad requirement example:**

```text
Help me sort out the agent invocation.
```

### 6. The Command Should Have Clear Failure Handling

**Requirement description:**

- **Must**: Handle directory switching failures, missing commands, and execution failures in the command execution chain
- **Must**: Output error information that can locate the problem
- **Forbidden**: Swallowing errors or failing silently

## Actions You Must Perform

### Action 1: Identify the Task Type and Choose the Command

**Execution steps:**

1. Determine whether the task is a general requirement
2. Determine whether the task is a code development requirement
3. Choose `hjb` for general requirements
4. Choose `hca` for code development requirements

**Decision rules:**

- Typical scenarios for using `hjb`: investigation, summarization, documentation, planning, knowledge organization, general automation processes
- Typical scenarios for using `hca`: modifying source code, adding tests, fixing builds, refactoring, implementing features, troubleshooting code defects

### Action 2: Detect the Command and Prepare the Execution Command

**Execution steps:**

1. Use `command -v` to check whether the target command exists
2. Merge the working directory switch and the agent command into the same shell command for execution
3. If any step fails, exit immediately

**Notes:**

Because commands are usually executed one by one independently, executing a single `cd` alone will not automatically affect the next new command. Therefore, switching the working directory must be placed in the same command as the `hjb`/`hca` invocation.

**General template:**

```bash
command -v <agent_cmd> >/dev/null 2>&1 || {
  echo "ERROR: <agent_cmd> is not installed or not in PATH" >&2
  exit 1
}

cd <work_dir> && <agent_cmd> -n --task "<complete task description>" || {
  echo "ERROR: cannot enter working directory <work_dir> or <agent_cmd> execution failed" >&2
  exit 1
}
```

### Action 3: Pass the Complete Requirement Directly in Non-interactive Mode

**Execution steps:**

1. Organize the requirement into a complete piece of text
2. Clearly state the background, goals, constraints, deliverables, and acceptance criteria in the text
3. Use `--task` to pass the requirement and execute it directly in the same command
4. Stay in unattended mode

**hjb invocation template:**

```bash
command -v hjb >/dev/null 2>&1 || {
  echo "ERROR: hjb is not installed or not in PATH" >&2
  exit 1
}
cd /path/to/workdir && hjb -n --task "Background: <background description>. Goal: <goal description>. Scope and constraints: <constraint description>. Deliverables: <deliverable description>. Acceptance criteria: <acceptance criteria description>." || {
  echo "ERROR: cannot enter working directory or hjb execution failed" >&2
  exit 1
}
```

**hca invocation template:**

```bash
command -v hca >/dev/null 2>&1 || {
  echo "ERROR: hca is not installed or not in PATH" >&2
  exit 1
}
cd /path/to/workdir && hca -n --task "Background: <project background>. Goal: <code development goal>. Scope and constraints: <modifiable files, technical constraints, forbidden items>. Deliverables: <code/test/documentation requirements>. Acceptance criteria: <build, test, and behavior verification requirements>." || {
  echo "ERROR: cannot enter working directory or hca execution failed" >&2
  exit 1
}
```

### Action 4: Check the Returned Result After Execution

**Execution steps:**

1. Check the command exit code
2. Check whether there is obvious error information in the output
3. If necessary, continue with builds, tests, or result verification according to the acceptance criteria
4. If it fails, retain a clear error context for subsequent handling

## Practical Guidance

### Recommended Practices

- **Must**: Prefer single-line, copyable, auditable commands
- **Must**: Write the acceptance criteria in the task text, rather than only writing the implementation actions
- **Must**: Keep the working directory consistent with the target repository
- **Recommended**: Write out the file scope, tech stack, and forbidden items clearly in complex tasks

### Forbidden Practices

- **Forbidden**: Directly executing `hjb` or `hca` without `cd`-ing into the project directory
- **Forbidden**: Omitting the `-n` non-interactive parameter
- **Forbidden**: Splitting the requirement into a two-phase mode of "launch first, then input interactively"
- **Forbidden**: Giving only a vague one-line command without providing background and acceptance criteria

## Checklist

Before completing the invocation design or orchestration, you must confirm:

- [ ] `hjb` or `hca` has been correctly chosen according to the task type
- [ ] The target command has been checked for installation before invocation
- [ ] The correct working directory has been entered before launch
- [ ] Non-interactive mode has been used
- [ ] The complete requirement has been passed directly on the command line
- [ ] The requirement includes the background, goals, scope/constraints, deliverables, and acceptance criteria
- [ ] The command has clear failure handling logic
