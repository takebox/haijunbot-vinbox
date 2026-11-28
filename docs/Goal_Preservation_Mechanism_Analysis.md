# Analysis of the Goal-Preservation Mechanism in the HaijunBot System

## Overview

This document analyzes how the Code Agent and Agent implementations in the HaijunBot system ensure, through various mechanisms, that the initial goal does not drift during execution. It focuses on key features such as the prompt mechanisms in summarization behavior, memory management, and code review.

## Core Mechanisms

### 1. Summary Mechanism

#### 1.1 Summary Trigger Timing

The HaijunBot system triggers summary generation in the following two situations:

- **Token-limit trigger**: when the conversation history reaches the token limit, a summary is automatically generated for context compression
- **Task-completion trigger**: a complete summary report is generated after task execution completes

#### 1.2 Summary Prompt Design

The system uses two different summary prompts:

**DEFAULT_SUMMARY_PROMPT** (default summary prompt):

- Used for the summary when a task completes
- Provides a complete structured report format
- Includes goal hierarchies, task status matrices, key information navigation, etc.

**SUMMARY_REQUEST_PROMPT** (token-limit trigger prompt):

- Specifically used for context compression scenarios
- Emphasizes the principle of "no loss of key information"
- Especially for code development tasks, requires fully preserving the context of code changes

#### 1.3 Summary Verification Mechanism

During the code review stage, the system specifically verifies the accuracy of the summary content:

```python
# Review requirements (from the _build_review_prompts method)
"""
- **Fully verify the key information in the code-generation summary**: do not blindly trust the summary; you must cross-check it item by item against the git diff and the actual code
- If you need more context, you must use the read_code tool to read the relevant files to verify whether the behavior/location/file mentioned in the summary actually exists and matches the description
- If the code-generation summary is inconsistent with the actual code, the actual code shall prevail, and the inconsistency should be recorded as a problem
"""
```

### 2. Memory Management System

#### 2.1 Memory Types

The system supports three types of memory:

- **Short-term memory (short_term)**: temporary data, debugging information, and intermediate results for the current task
- **Project long-term memory (project_long_term)**: key architecture decisions, configuration schemes, business rules
- **Global long-term memory (global_long_term)**: general solutions, best practices, technical standards

#### 2.2 Memory Prompt Mechanism

At the start of a task, the system automatically prompts the available memory tags:

```python
def prepare_memory_tags_prompt(self) -> str:
    """Prepare the memory tag prompt"""
    # Check whether there is a memory tool
    if self._has_memory_tool():
        memory_tags_prompt = "\n\n💡 Tip: before analyzing the task, it is recommended to use the memory tool (action=save) to record key information for later retrieval and reuse."
```

#### 2.3 Automatic Memory Saving

The system automatically prompts to save memorable information when a task completes:

```python
def prompt_memory_save(self) -> None:
    """Let the LLM automatically decide and save memorable information"""
    prompt = """Review this task and determine whether there is memorable information. Use the memory tool (action=save) to save it:
- global_long_term: new methods/techniques, user preferences, technical knowledge
- project_long_term: project findings/configurations, implementation details/conventions
If there is no memorable information, just say so."""
```

### 3. Code Review and Fix Loop

#### 3.1 Review Flow

CodeAgent implements a multi-round code review mechanism:

1. **Obtain code changes**: obtain all modifications from the start of the task to the present via git diff
2. **Build the review prompt**: build the review prompt by combining the user's requirements, the modification history, and the code changes
3. **Independent review Agent**: create a dedicated CodeReview-Agent for independent review
4. **Problem parsing**: parse the review results and identify issues that need fixing
5. **Fix execution**: perform fixes based on the review results
6. **Fix summary**: generate a fix summary and append it to the modification history

#### 3.2 Modification History Tracking

The system maintains a complete modification history record:

```python
# Save the initial summary as the first part of the modification history
modification_history = code_generation_summary or ""

# Append the fix summary after each round of fixes
fix_summary = self._generate_fix_summary()
if fix_summary:
    modification_history += f"\n\n[Fix Summary - Round {iteration}]\n{fix_summary}"
```

#### 3.3 Review Verification Requirements

The review stage places special emphasis on verifying the summary content:

- **Do not blindly trust the summary**: treat the summary as a "statement to be verified"
- **Cross-check item by item**: for each key modification point mentioned in the summary, there must be corresponding evidence in the git diff or the actual code
- **Handling inconsistencies**: when the summary is found to be inconsistent with the actual code, it must be pointed out in the review results

### 4. Initial Goal Anchoring Mechanism

#### 4.1 Git Commit Anchor

The system records the initial Git Commit at the start of a task as a safe fallback point:

````python
# Add the initial commit information to addon_prompt (safe fallback point)
initial_commit_prompt = f"""
**🔖 Initial Git Commit (safe fallback point)**:
The initial commit at the start of this task is: `{start_commit}`

**⚠️ Safe fallback command**:
```bash
git reset --hard {start_commit}
````

This will discard all uncommitted changes and restore the working tree to the state at the start of the task.
"""

````

#### 4.2 Preserving User Requirements

The review prompt explicitly requires respecting the user's original requirements:

```python
"""**Respect the user's original requirements**: if the user explicitly supports a certain approach or implementation in the requirements, it should not be judged as a risk or problem, unless the approach has an obvious error or violates security principles"""
````

#### 4.3 Non-interactive Mode Constraints

In non-interactive mode, the system automatically executes the plan, avoiding drifting from the goal by waiting for user confirmation:

```python
non_interactive_note = """
[System Note]
This session is in **non-interactive mode**:
- In PLAN mode, after giving a clear, executable, detailed plan, you should **automatically enter EXECUTE mode to execute the plan** rather than waiting for additional user confirmation;
- In EXECUTE mode, keep a step-by-step, small-commit, rollback-capable strategy, but there is no need to repeatedly ask the user "should I continue";
- If the information is severely insufficient, you may supplement the necessary analysis yourself in RESEARCH mode, rather than getting stuck waiting for user input.
"""
```

### 5. Code Change Context Management

#### 5.1 Context Manager

CodeAgent uses ContextManager to manage the code analysis context:

```python
self.context_manager = ContextManager(self.root_dir)
```

#### 5.2 Impact Scope Analysis

Uses ImpactManager to analyze the impact scope of code modifications:

```python
self.impact_manager = ImpactManager(self.root_dir, self.context_manager)
```

#### 5.3 Build Validation

Uses BuildValidationManager to validate the build state after code modifications:

```python
self.build_validation_manager = BuildValidationManager(self.root_dir)
```

## Key Design Principles

### 1. Verification-First Principle

- All summary content must undergo actual verification
- The mere existence of code does not mean the task is complete
- Concrete verification evidence must be provided (compilation results, test results, run logs, etc.)

### 2. Context Integrity Principle

- The summary must provide context support with "no loss of key information"
- Especially for code development tasks, it requires fully preserving the context of code changes
- Ensures subsequent conversations can proceed smoothly without tracing back to the original history

### 3. Actual-Code-Takes-Precedence Principle

- The review stage must take the actual code as the standard and must not blindly trust the summary
- When the summary is found inconsistent with the actual code, it must be pointed out and corrected
- All judgments must be based on actual verification, not unfounded assumptions

### 4. Progressive Fixing Principle

- Supports multiple rounds of review and fix loops
- Generates a fix summary after each round of fixes and updates the modification history
- Gradually approaches the target implementation through iteration

## Implementation File Locations

### Core Implementation Files

1. **CodeAgent main class**: `src/haijunbot/haijunbot_code_agent/code_agent.py`
   - `_review_and_fix()`: review-fix loop
   - `_build_review_prompts()`: build review prompts
   - `generate_summary()`: summary generation

2. **Agent base class**: `src/haijunbot/haijunbot_agent/__init__.py`
   - `generate_summary()`: base implementation of summary generation

3. **Prompt definitions**: `src/haijunbot/haijunbot_agent/prompts.py`
   - `DEFAULT_SUMMARY_PROMPT`: default summary prompt
   - `SUMMARY_REQUEST_PROMPT`: token-limit trigger prompt

4. **Memory management**: `src/haijunbot/haijunbot_agent/memory_manager.py`
   - `prepare_memory_tags_prompt()`: memory tag prompt
   - `prompt_memory_save()`: automatic memory saving

### Related Managers

- **Git manager**: `src/haijunbot/haijunbot_code_agent/code_agent_git.py`
- **Diff manager**: `src/haijunbot/haijunbot_code_agent/code_agent_diff.py`
- **Impact analysis manager**: `src/haijunbot/haijunbot_code_agent/code_agent_impact.py`
- **Build validation manager**: `src/haijunbot/haijunbot_code_agent/code_agent_build.py`

## Summary

The HaijunBot system ensures, through a multi-layered goal-preservation mechanism, that the initial goal does not drift during execution:

1. **Structured summary mechanism**: ensures key information is not lost through carefully designed summary prompts
2. **Memory management system**: preserves important context through memory tags and automatic saving mechanisms
3. **Code review loop**: ensures code modifications meet the original requirements through multiple rounds of independent review
4. **Verification-first principle**: all conclusions must be based on actual verification, avoiding subjective assumptions
5. **Progressive fixing**: gradually approaches the target implementation through iteration

Together these mechanisms form a complete closed-loop system that can effectively maintain goal consistency in complex code development tasks and avoid drifting from the original requirements during execution.
