# HaijunBot CodeAgent Feature Supplement Plan and Implementation Roadmap

## 1. Document Goals

Based on the Comparison Analysis conclusions in the `docs/compare/haijunbot_vs_haijun_code_agent.md` document, this document provides the supplemental feature plan and implementation roadmap for the next Phase of HaijunBot CodeAgent.

This plan adheres to the following overall principles:

> **Keep HaijunBot's Advantages in rules, research, analysis, and Validation, while adopting Haijun Code's mature designs for state management, permission governance, and collaboration systems.**

This document is not a code implementation document, but a unified planning document for subsequent Architecture evolution and iterative development, used to guide the phased Implementation that follows.

---

## 2. Evolution Goals

HaijunBot already has strong project-level code analysis and task execution capabilities, especially with obvious Advantages in the following areas:

- **Strong rule system**: supports `load_rule`, enabling the codification of best practices, Architecture principles, and task Constraints
- **Strong research workflow**: the ARCHER Flow suits complex code research, project reverse engineering, technology investigation, and solution Comparison
- **Strong code analysis**: provides context recommendation, dependency analysis, impact analysis, build Validation, lint, and post-process
- **Relatively complete Validation chain**: provides infrastructure such as review, task_list_manager, and verification agent
- **Mature memory system**: provides three-tier memory: short-term, project long-term, and global long-term

However, from the perspectives of productized execution, Security governance, and multi-agent collaboration, the following shortcomings remain:

- The system state boundary between the planning Phase and the execution Phase is not clear enough
- Tool permission control Mainly relies on prompts and manual confirmation, lacking a unified permission context
- Sub-agents exist, but they are not yet a complete collaboration system
- Context management leans toward "real-time analysis" and lacks stable layered caching and visualization
- Editing tools still have room to improve in path governance, concurrent write protection, and file state validation

Therefore, the Goal of this round of feature supplementation is not to rewrite HaijunBot, but to let HaijunBot complete an upgrade **from "strong engineering capability" to "strong engineering capability + strong state governance + strong collaboration capability"**.

---

## 3. Overall Design Principles

### 3.1 Principles for What to Keep

The following capabilities are HaijunBot's core Advantages and must be preserved and further strengthened in subsequent evolution:

1. **Rules first**
   - Keep preserving the priority of `load_rule`, project rules, organization rules, and special-topic rules
   - New capabilities must not grow independently and bypass the rule system

2. **Research workflow first**
   - ARCHER remains the main Flow for complex technical tasks
   - New state machines should not weaken the in-depth requirements of ANALYZE / COLLECT / REVIEW

3. **Analysis and Validation first**
   - New capabilities must serve more Secure, more verifiable code changes
   - The impact analysis, build Validation, static checking, and Validation agent Mechanisms must be preserved

4. **Memory and Methodology first**
   - The memory system and the Methodology system are HaijunBot's Differentiating capabilities and should not be weakened
   - They should be embedded more deeply into the execution Flow in the future, rather than being marginalized

### 3.2 Principles for What to Adopt

The following mature designs from Haijun Code are worth adopting, but should be localized around the HaijunBot Architecture:

1. **State management**: introduce explicit execution state instead of relying only on prompt conventions
2. **Permission governance**: push permission decisions down into the tool layer instead of relying only on Model self-discipline
3. **Collaboration system**: upgrade sub-agents from "one-shot subtask execution" to "role-based collaboration units"
4. **Context as infrastructure**: evolve from real-time search enhancement to "layered caching + automatic injection + visualization"
5. **Runtime observability**: task, agent, mode, and Validation states must be displayable and traceable

### 3.3 Principles for the Evolution Approach

- No one-shot big refactoring
- Prioritize **incremental evolution**
- Each Phase must deliver a minimal closed loop that can be landed
- Each Phase must be verifiable, reversible, and further extensible

---

## 4. Goal Capability Blueprint

This feature supplementation plan Recommends unfolding around the following five main threads:

### 4.1 Main Thread A: State Management Upgrade

Goal: upgrade HaijunBot from "Flow prompt-driven" to "state-driven execution".

Key capabilities:

- Introduce an Agent execution state Model
- Introduce explicit Plan Mode / Execute Mode / Review Mode
- Make the planning Phase truly read-only, allowing modifications only in the execution Phase
- State changes can be recorded, displayed, and validated

### 4.2 Main Thread B: Permission Governance Upgrade

Goal: give HaijunBot's tool system a unified permission context to reduce the Risks of misoperation and unauthorized write operations.

Key capabilities:

- Perform permission checks before tool calls
- Path-level read/write control
- Risk grading for shell commands
- Automatic decision policy for non-interactive mode

### 4.3 Main Thread C: Collaboration System Upgrade

Goal: upgrade the existing `sub_agent` / `sub_code_agent` into a role-based, traceable, verifiable collaboration system.

Key capabilities:

- Role-based sub-agent types
- Unified sub-agent output structure
- Mechanisms for returning, validating, and aggregating sub-agent results
- Future support for mailbox / background / coordinator

### 4.4 Main Thread D: Context System Upgrade

Goal: while keeping HaijunBot's deep analysis capabilities, complete a lightweight, cached, stably injected context infrastructure.

Key capabilities:

- Layering of system context / project context / task context
- Context caching with incremental refresh
- Automatic injection of project design documents and rules
- Context visualization

### 4.5 Main Thread E: Observability and Validation Upgrade

Goal: make task execution state, sub-agent state, permission state, context state, and Validation state all visualizable and traceable.

Key capabilities:

- Display of the current mode
- Abstract of the current task list
- Display of current context sources
- Display of current diff / Risks / Validation results
- Linking of task hooks and Validation hooks

---

## 5. Recommended Incremental Architecture Design

### 5.1 New Unified Runtime Object: ExecutionContext

It is Recommended to add a unified runtime context object, for example:

- `mode`: the current execution mode (analyze / plan / execute / review)
- `permission_context`: the current permission context
- `task_context`: the current task, dependencies, and Phase state
- `context_layers`: the current system context, project context, and task context
- `verification_state`: the current Validation state
- `risk_level`: the current Risks level

Purpose:

- Let Agent, CodeAgent, tools, and task_list_manager share the same runtime state
- Provide a unified basis for "mode switching / permission checks / output display"

### 5.2 New Unified Permission Object: PermissionContext

It is Recommended to add a unified permission object for pre-execution decisions at the tool layer:

- `mode`: default / plan / execute / dangerous
- `file_read_rules`
- `file_write_rules`
- `shell_rules`
- `network_rules`
- `interactive_policy`
- `non_interactive_policy`

Its core responsibilities:

- Make unified decisions before tool calls
- Provide consistent Constraints for `edit_file`, `execute_script`, `virtual_tty`, and future write-type tools

### 5.3 Unified Sub-Agent Abstraction: AgentRole / AgentTask

It is Recommended to elevate sub-agents from "tool-call Parameters" to a unified abstraction:

- `agent_role`: explore / plan / implement / verify
- `task_goal`
- `task_scope`
- `allowed_tools`
- `required_output_schema`
- `handoff_policy`

In this way, whether it is a synchronous sub-agent, a background sub-agent, or a team agent, the same abstraction can be reused later.

### 5.4 Unified Context-Layer Abstraction: ContextLayers

It is Recommended to divide the context into:

1. **System Context**
   - Current directory
   - git status Abstract
   - Current branch
   - Recent commits
   - Current tool Availability

2. **Project Context**
   - Project overview
   - Rules Abstract
   - `project_info` document Abstract
   - Project long-term memory

3. **Task Context**
   - Current task plan
   - Current task list Abstract
   - Current recommended files and symbols
   - Recently edited files
   - Current diff Abstract

This can balance:

- HaijunBot's existing deep analysis capabilities
- Haijun Code-style stable injection and caching

---

## 6. Phased Implementation Plan

The following uses a **Phase 1 / Phase 2 / Phase 3** approach.

---

## 7. Phase 1: State Governance and Security Infrastructure

### 7.1 Goals

Establish a minimal usable foundation for state management and permission governance, letting HaijunBot evolve from "Constraints via prompts" to "system state Constraints + tool permission adjudication".

### 7.2 Core Deliverables

1. **Introduce the Agent Mode state Model**
   - Add a mode field
   - Initial support: `analyze` / `plan` / `execute` / `review`

2. **Add explicit Plan Mode tools**
   - `enter_plan_mode`
   - `exit_plan_mode`

3. **Add PermissionContext**
   - Allow read-only tool calls in plan mode
   - Forbid write tools and dangerous scripts

4. **Strengthen edit_file / execute_script tool protection**
   - Path rules
   - File size limits
   - File state validation (mtime/hash)
   - High-Risk command detection

5. **Initial execution-state panel**
   - Display mode, current task, permission state, and context-source Abstract

### 7.3 Affected Modules

- `src/haijunbot/haijunbot_agent/`
- `src/haijunbot/haijunbot_code_agent/`
- `src/haijunbot/haijunbot_tools/`
- `src/haijunbot/haijunbot_utils/`

### 7.4 Recommended Breakdown

#### Sub-Module 1: Mode State Management

Recommended location:

- The `haijunbot_agent` base layer

Recommended content:

- Define the mode enum
- Provide a mode switching API
- Integrate with the system prompt / run loop

#### Sub-Module 2: PermissionContext

Recommended location:

- The `haijunbot_tools` or `haijunbot_agent` shared layer

Recommended content:

- A unified tool permission check Interface
- Provide mode-based decision logic
- Provide automatic policies for non-interactive mode

#### Sub-Module 3: Tool Security Enhancement

Recommended location:

- `edit_file`
- `execute_script`
- `virtual_tty`

Recommended content:

- Pre-edit validation
- Path normalization
- High-Risk command interception
- Concurrent file-modification detection

### 7.5 Risks

- Modifying the Agent base may affect existing behavior
- Tightening tool permissions may expose implicit dependencies on dangerous behavior in old Flows
- If the non-interactive policy is too strict, the automation completion rate may drop

### 7.6 Mitigation Measures

- Ship in compatible mode by default
- First record permission decisions, then gradually enable strict interception
- Provide clear log output for plan mode and execute mode

### 7.7 Acceptance Criteria

- The Agent can clearly report the current mode
- Files cannot be edited directly in plan mode
- `edit_file` and `execute_script` can perform permission checks
- High-Risk paths and commands can be rejected or require confirmation
- The execution-state panel can display the current mode and permission state

---

## 8. Phase 2: Collaboration System and Validation System Upgrade

### 8.1 Goals

Building on Phase 1, integrate sub-agents, the task system, and Validation Mechanisms into a role-based collaboration system.

### 8.2 Core Deliverables

1. **Role-based sub-agents**
   - explore agent
   - plan agent
   - implement agent
   - verify agent

2. **Unified sub-agent output protocol**
   - Structured results
   - Key findings
   - Risks Description
   - Verifiable artifact locations

3. **Productize the Validation agent**
   - Automatically trigger the verify agent after a task completes
   - Write back task state on Validation failure

4. **Initial task hooks**
   - on_task_created
   - on_task_started
   - on_task_completed
   - on_task_verified

5. **Link tasks with diff/file sets**
   - Tasks automatically record related files
   - Output a change Abstract when a task ends

### 8.3 Affected Modules

- `src/haijunbot/haijunbot_agent/sub_agent.py`
- `src/haijunbot/haijunbot_code_agent/sub_code_agent.py`
- `src/haijunbot/haijunbot_tools/task_list_manager.py`
- `src/haijunbot/haijunbot_agent/`
- `src/haijunbot/haijunbot_code_agent/`

### 8.4 Recommended Breakdown

#### Sub-Module 1: AgentRole Definitions

- Define roles
- Configure default tool sets
- Configure default system prompts

#### Sub-Module 2: Unified handoff output format

Recommended structure:

- `summary`
- `findings`
- `modified_files`
- `risks`
- `verification_suggestions`

#### Sub-Module 3: Validation Automation

- Automatically enter the verify Phase after a subtask completes
- Write Validation results back to task_list_manager

### 8.5 Risks

- Sub-agent behavior Differences increase debugging complexity
- If the dual task/agent system is not well designed, responsibilities can easily overlap
- Automatic Validation may increase token and execution costs

### 8.6 Mitigation Measures

- First implement a few built-in roles, without rolling out team collaboration from the start
- Unify the output protocol to reduce complexity caused by agent Differences
- Enable the Validation agent by default only for complex tasks or explicitly marked tasks

### 8.7 Acceptance Criteria

- Sub-agents with different roles can be created explicitly
- Sub-agent output structure is unified
- Automatic Validation is supported after task completion
- Validation results can be written back to the task state
- Tasks can display related files and change Abstracts

---

## 9. Phase 3: Context System and Runtime Observability Upgrade

### 9.1 Goals

Continue upgrading HaijunBot's context capability from "strong analysis" to "strong analysis + strong context infrastructure + strong visualization".

### 9.2 Core Deliverables

1. **Layered ContextLayers implementation**
   - system context
   - project context
   - task context

2. **Context caching with incremental refresh**
   - Refresh triggered by git status changes
   - Refresh of task context triggered by file changes
   - Refresh of project context triggered by rule changes

3. **Context visualization tools**
   - View the currently injected context
   - View current task context sources
   - View current recommended files/symbols

4. **Automatic project-document injection**
   - `.haijunbot/rules/project_info/README.md`
   - Key Module design documents
   - Task-related rules Abstract

5. **Enhanced runtime panel**
   - Current mode
   - Current task
   - Current context layers
   - Current diff state
   - Current verification state
   - Current Risks level

### 9.3 Affected Modules

- `src/haijunbot/haijunbot_code_agent/code_analyzer/`
- `src/haijunbot/haijunbot_agent/`
- `src/haijunbot/haijunbot_utils/`
- `docs/`

### 9.4 Risks

- Too many context layers may cause injection bloat
- Poor cache invalidation handling may lead to misuse of stale information
- Overly heavy visualization may harm CLI simplicity

### 9.5 Mitigation Measures

- Start with Abstract-level injection instead of injecting whole documents
- Add versions and expiration times to cached objects
- Start with a lightweight text panel in the CLI, avoiding premature complex UI

### 9.6 Acceptance Criteria

- Context is managed in layers
- Frequently used context can be cached and refreshed
- Current context sources and Abstracts can be viewed
- Project design documents can be automatically used as context sources
- The runtime panel can display context and Validation information

---

## 10. Long-Term Direction (Phase 4+)

After the first three Phases stabilize, consider the following long-term capabilities:

1. **Background agent and recovery Mechanism**
2. **agent mailbox / send_message**
3. **team / coordinator collaboration Model**
4. **worktree isolation execution**
5. **Sub-agent output Security classifier**
6. **Unified runtime display for IDE / Web**
7. **Automatic memory distillation and automatic task archival**

These directions are not Recommended to be pursued prematurely; otherwise, they will increase system complexity and dilute the current main Goals.

---

## 11. Prioritization Recommendations

### P0 (Do first)

- Explicit Plan Mode
- Agent state Model
- PermissionContext
- `edit_file` / `execute_script` Security enhancements
- Initial execution-state panel

### P1 (Second batch)

- Role-based sub-agents
- Productized Validation agent
- task hooks
- Task-to-diff/file association

### P2 (Third batch)

- ContextLayers
- Context caching
- Context visualization
- Automatic project-document injection

### P3 (Long-term)

- Background agents
- Collaboration mailbox
- coordinator Model
- worktree isolation
- Stronger UI/IDE integration

---

## 12. Implementation Order Recommendations

It is Recommended to proceed in the following order rather than making large parallel Module changes:

1. **Do state management first, then permission governance**
   - Without state, there is no basis for permission modes

2. **Do permission governance first, then the collaboration system**
   - Without permission Constraints, multi-agent collaboration Risks are amplified

3. **Do the collaboration system first, then enhance the context system**
   - Multi-agent requirements on context abstraction are more explicit; doing collaboration first makes the context converge more easily

4. **Observability runs through the entire process**
   - Each Phase should at least add basic state display to prevent the system from becoming undebuggable after evolution

---

## 13. Module Impact Map

| Module                              | Impact direction | Main responsibilities                              |
| --------------------------------- | -------- | -------------------------------------------------- |
| `haijunbot_agent`                    | High     | mode, runtime state, state display, base extensibility |
| `haijunbot_code_agent`               | High     | code task Flow, context integration, plan/execute/review binding |
| `haijunbot_tools`                    | High     | permission checks, task hooks, tool-level Security governance |
| `haijunbot_code_agent/code_analyzer` | Medium   | context layering, caching, document injection       |
| `haijunbot_utils`                    | Medium   | Configuration, caching, Risks classification, global shared utilities |
| `docs`                            | Medium   | project design documents and Implementation roadmap maintenance |

---

## 14. Risks Overview

### 14.1 Main Risks

1. **Evolution scope too broad, causing Phases to lose focus**
2. **State machine inconsistent with the existing prompt Flow**
3. **Overly strict permission system reducing automation efficiency**
4. **Collaboration system complexity rising too quickly**
5. **Token costs rising after the context system is added**

### 14.2 Mitigation Strategy

1. Stick to phased delivery
2. Be compatible first, tighten later
3. First limit read-only/high-Risk capabilities, without blocking everything at once
4. Do role-based sub-agents first, without immediately building team/coordinator
5. Always start context with Abstracts before deep automatic injection

---

## 15. Per-Phase Acceptance Approach

### Phase 1 Acceptance

- Read Key code locations and confirm mode and permission context have been introduced
- Verify that write operations cannot be performed in plan mode
- Verify that `edit_file` / `execute_script` can output clear permission decisions
- Verify that the execution-state panel can reflect the current mode and permission state

### Phase 2 Acceptance

- Verify that sub-agents with different roles can be created
- Verify that the sub-agent output structure is unified
- Verify that a task can automatically enter the Validation Flow after completion
- Verify that Validation results can feed back into the task state

### Phase 3 Acceptance

- Verify that context is layered by system/project/task
- Verify that the context cache exists and can be invalidated
- Verify that current context-source Abstracts can be viewed
- Verify that project design documents can be automatically used as context sources

---

## 16. Recommended First-Round Landed Slice

If only one round of short-cycle feature supplementation is launched, it is Recommended to limit the scope to the following:

### 16.1 Must do

- Add the mode state Model
- Add `enter_plan_mode` / `exit_plan_mode`
- Add basic path protection and file state validation to `edit_file`
- Add read-only/high-Risk classification to `execute_script`
- Add a lightweight execution-state panel

### 16.2 Defer

- mailbox
- background agent
- team/coordinator
- worktree isolation
- complex UI

### 16.3 Reasons

This set of changes best demonstrates:

- Preserving HaijunBot's original research and analysis Advantages
- Adopting Haijun Code's state management and permission governance capabilities
- Controllable Risks
- Ease of forming a minimal closed loop

---

## 17. Final Conclusion

The most correct direction for HaijunBot's next Phase is not to copy Haijun Code, but to perform a **Differentiating enhancement**:

- **Hold on to HaijunBot's rules, research, analysis, and Validation Advantages**
- **Adopt Haijun Code's experience in state management, permission governance, and collaboration systems**
- **Through phased evolution, upgrade HaijunBot from a "code Agent with strong analysis" to a "project-level code Agent platform with strong analysis + strong governance + strong collaboration"**

This plan Recommends completing Phase 1 first, then deciding whether to advance the deeper capabilities of Phase 2 and Phase 3 based on Implementation results.

---

## 18. Recommendations for Follow-Up Companion Documents

It is Recommended to continue adding the following documents later:

1. `haijunbot_code_agent_state_model_design.md`
   - Dedicated to Describing the mode state machine design

2. `haijunbot_permission_context_design.md`
   - Dedicated to Describing the permission decision Model and tool integration specification

3. `haijunbot_agent_role_collaboration_design.md`
   - Dedicated to Describing the role-based sub-agent design

4. `haijunbot_context_layers_design.md`
   - Dedicated to Describing context layering and caching strategies

5. `haijunbot_execution_observability_design.md`
   - Dedicated to Describing the runtime visualization and state display design
