# Comparison Analysis: HaijunBot CodeAgent vs Haijun Code Code Agent Capabilities

## 1. Research Scope and Information Sources

This document conducts a Comparison Analysis based on the following actual code and documents, focusing on "code Agent / task execution agent" capabilities, and does not discuss peripheral business unrelated to code agents.

### 1.1 HaijunBot Code Sources

- `src/haijunbot/haijunbot_code_agent/code_agent.py` - HaijunBot CodeAgent main implementation, tool assembly, context manager initialization, and runtime Flow
- `src/haijunbot/haijunbot_code_agent/code_agent_prompts.py` - Scenario-based system prompts and Requirement classification
- `src/haijunbot/haijunbot_tools/task_list_manager.py` - task list, Validation Agent, and task execution Constraints
- `src/haijunbot/haijunbot_agent/__init__.py` - generic Agent base, ARCHER workflow, and memory/rule/event Mechanisms
- `src/haijunbot/haijunbot_agent/sub_agent.py` - generic sub-Agent implementation
- `src/haijunbot/haijunbot_code_agent/sub_code_agent.py` - CodeAgent sub-agent implementation
- `src/haijunbot/haijunbot_code_agent/code_analyzer/__init__.py` - main entry for code analysis capabilities
- `src/haijunbot/haijunbot_code_agent/code_analyzer/llm_context_recommender.py` - LLM-driven context recommendation and symbol scanning

### 1.2 Haijun Code Code Sources

- `../haijun-code/README.md` - project Architecture overview, capability catalog, and Key design Description
- `../haijun-code/src/context.ts` - system/user context collection and caching
- `../haijun-code/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts` - explicit plan mode implementation
- `../haijun-code/src/tools/FileEditTool/FileEditTool.ts` - file editing Security checks, permission checks, and file state Validation
- `../haijun-code/src/tools/TaskListTool/TaskListTool.ts` - task list reading
- `../haijun-code/src/tools/TaskCreateTool/TaskCreateTool.ts` - task creation
- `../haijun-code/src/tools/TaskUpdateTool/TaskUpdateTool.ts` - task update, completion hooks, and Validation prompts
- `../haijun-code/src/tools/AgentTool/AgentTool.tsx` - sub-agent/teammate agent spawning
- `../haijun-code/src/tools/AgentTool/agentToolUtils.ts` - sub-agent finalization, Security handoff, and background lifecycle
- `../haijun-code/src/tools/AgentTool/runAgent.ts` - sub-agent execution and tool parsing

### 1.3 Analysis Boundaries

- Key Comparison areas: execution workflow, task planning, context management, tool system, sub-agents, multi-task collaboration, Security/permissions, editing Reliability, memory and state management, and observability
- Not explored in depth: UI skins, account systems, commercial closed-source capabilities, and peripheral integrations weakly related to code agents
- Conclusions are based only on the current repository snapshot, without assuming hidden implementations in unread code

---

## 2. Overall Assessment

**Conclusion first:**

HaijunBot already has a fairly complete "project-level code Agent" foundational framework, and its Advantages are:

- A clear ARCHER workflow Constraints
- A rule system, Methodology system, and memory system
- Project-level code analysis, context recommendation, impact analysis, build Validation, lint, and post-process
- task_list_manager for complex task decomposition and Validation
- Generic Agent and CodeAgent layering, with strong extensibility

But compared with Haijun Code, HaijunBot still has several obvious weaknesses:

1. **The plan mode is not yet "productized" and "stateful"**: HaijunBot has HYPOTHESIZE / EXECUTE semantics, but lacks an explicit, switchable, constrainable, auditable `plan mode` state machine like Haijun Code's.
2. **The permission and editing Security Model is not granular enough**: HaijunBot Mainly relies on prompt Constraints and manual confirmation, while Haijun Code puts permission checks, path rules, and file-state consistency validation into the tool implementation layer.
3. **Multi-agent collaboration is still more "subtask invocation" than a "collaboration system"**: HaijunBot has `sub_agent` / `sub_code_agent`, but Haijun Code has already formed a complete system of agent types, teams, mailboxes, background execution, recovery, and handoff classification.
4. **The context injection Mechanism is not yet lightweight, cached, or visualized**: HaijunBot leans more toward "runtime search + LLM recommendation", while Haijun Code emphasizes "layered system/user context caching + automatic memory injection + context visualization".
5. **The editing tool layer still has room to improve robustness**: Haijun Code's FileEditTool is more systematic in permissions, path normalization, file size, file existence, and concurrent modification detection; HaijunBot currently emphasizes search/replace accuracy, but has relatively fewer tool-level protections.
6. **Observability and runtime state feedback are insufficient**: Haijun Code has stronger UI and state feedback for plan/task/agent/progress/context, while HaijunBot relies more on text-based Flow Constraints.

In other words, **HaijunBot is stronger in "Methodology" and "engineering analysis capabilities", while Haijun Code is more mature in "execution productization" and "state-machine-based tool governance".**

---

## 3. Code Agent Architecture Comparison of the Two Projects

### 3.1 HaijunBot's Architecture Characteristics

As can be seen from `CodeAgent(Agent)`, HaijunBot uses a **generic Agent base + code-specific enhancement layer** pattern:

- Generic capabilities are managed uniformly in `haijunbot_agent`: event bus, PromptManager, MemoryManager, RulesManager, TaskAnalyzer, TaskListManager, SessionManager, ToolExecutor, etc.
- Code capabilities are enhanced in `haijunbot_code_agent`:
  - `ContextManager`
  - `ContextRecommender`
  - `GitManager`
  - `DiffManager`
  - `ImpactManager`
  - `BuildValidationManager`
  - `LintManager`
  - `PostProcessManager`

In `code_agent.py` the following can be seen directly:

- `CodeAgent` inherits from `Agent`
- During initialization it separates "base attributes / context managers / code managers / tool lists / post-parent-init setup"
- Uses `ContextManager(self.root_dir)` for project context management
- Uses `ContextRecommender` for LLM-driven semantic context recommendation
- Subscribes to `AFTER_TOOL_CALL` on the event bus, which Describes deep coupling between post-execution processing and diff/commit

This Describes HaijunBot's design focus: **treating code tasks as a specialized form on top of the Agent base**.

### 3.2 Haijun Code's Architecture Characteristics

From its README and directory structure, Haijun Code uses a more pronounced **tool platform + stateful CLI + multi-agent orchestration** pattern:

- `QueryEngine.ts` is responsible for the LLM query/tool-call loop
- `Tool.ts` is responsible for unified definitions of all tools
- Each tool under `tools/` is independently modularized, containing:
  - schema
  - permission model
  - execution logic
  - UI rendering
- `context.ts` handles centralized collection and caching of system/user context
- Tools such as `AgentTool`, `Task*Tool`, and `EnterPlanModeTool` turn the "agent system" itself into tools
- `coordinator/`, `tasks/`, `memdir/`, `services/extractMemories/`, and `teamMemorySync/` reflect a stronger runtime system design

Haijun Code's focus is not on "one big Agent class", but rather:

> Make the Agent an execution unit jointly constrained and driven by the state machine, permission system, task system, context system, and UI system.

### 3.3 Architecture Differences Summary

| Dimension       | HaijunBot                                 | Haijun Code                      |
| ------------ | -------------------------------------- | -------------------------------- |
| Core organization | Generic Agent base + CodeAgent extension | Tool platform + state machine + multi-agent orchestration |
| Focus        | Rules/Methodology/code analysis depth  | Permissions/state/interaction/multi-agent collaboration |
| Scalability direction | Better for quickly integrating new rules, tools, and analyzers | Better for large-scale interactive use and complex collaboration |
| Current maturity | Strong engineering capability          | Stronger productization and collaboration |

---

## 4. Workflow Design Comparison

### 4.1 HaijunBot: Obvious ARCHER Workflow Advantages

HaijunBot enforces ARCHER in its system prompts:

- ANALYZE
- RULE
- COLLECT
- HYPOTHESIZE
- EXECUTE
- REVIEW

Its Strengths:

1. **Complete Flow**: analysis, rule loading, information collection, solution design, execution, and review are all defined.
2. **Suitable for research/complex engineering tasks**: especially code tasks that require extensive information collection and multi-round analysis.
3. **Emphasizes evidence and traceability**: forbids speculation and prioritizes tools.
4. **Carries a REVIEW closed loop**: more reliable than many agents that only "write code".

`code_agent_prompts.py` also supports dynamically selecting system prompts by Scenario, which shows that HaijunBot has begun moving from a "unified Agent" toward a "Scenario-based Agent".

### 4.2 Haijun Code: Plan Mode Is More Explicit and More Executable

Haijun Code's `EnterPlanModeTool` is worth attention:

- It is not a pure prompt convention, but an **explicit tool**
- After entering, it modifies `toolPermissionContext.mode`
- It clearly stipulates: **do not edit files in plan mode**
- It requires first exploring and comparing options, asking the user questions when necessary, and then exiting plan mode to await approval
- It is also a read-only, concurrency-safe tool

This means Haijun Code's "planning" is not a soft Constraint, but a **hard Constraint with system state switching**.

### 4.3 HaijunBot's Current Gaps

Although HaijunBot semantically has HYPOTHESIZE, it lacks the following capabilities:

- No real "planning state / execution state" system state switch
- No tool-level read-only restrictions to ensure no write operations occur during the planning Phase
- In non-interactive mode it often proceeds directly to execution, and the planning-execution boundary is less clear than in Haijun Code
- Lacks an explicit state record point for "exiting plan state after approval"

### 4.4 Improvement Recommendations

**Recommendation 1: Introduce an explicit Plan Mode to HaijunBot.**

Recommended implementation:

- `enter_plan_mode` / `exit_plan_mode` tools
- Record the current mode in Agent state: `analyze` / `plan` / `execute` / `review`
- In plan mode, the tool layer directly forbids `edit_file`, write-type `execute_script`, and dangerous shells
- Allow `read_code`, `execute_script` (read-only commands), `search_web`, and `load_rule`
- When exiting plan mode, require generating a structured plan Abstract and writing it to short-term memory

**Benefits:**

- Reduce the Risks of accidentally modifying code
- Let "analyze first, modify later" truly land in system state
- Better suited for future UI, approval flows, and remote collaboration

---

## 5. Context Management Comparison

### 5.1 HaijunBot: Semantic Recommendation + Project Scanning

HaijunBot's `ContextRecommender` takes a heavier but smarter approach:

- Scans the project build symbol table when necessary
- Extracts Key terms based on the LLM
- Fuzzy-searches candidate symbols in the symbol table
- Then uses the LLM for a second-stage filter of candidate symbols
- Returns recommended symbols as context

The Strengths of this design:

- Stronger "semantic understanding" for large engineering tasks
- Not just grep, but combines project symbols with intent understanding
- Naturally compatible with the `ImpactAnalyzer` and `DependencyAnalyzer` system

But it also has obvious costs:

- High cost of the first scan
- Sensitive to project scale
- More like "on-demand code understanding" than a "session-level context system"

### 5.2 Haijun Code: Layered System/User Context Caching

`context.ts` shows that Haijun Code has made context collection an independent Module:

- `getSystemContext()`: collects git status, branch, recent commits, debug injection, etc.
- `getUserContext()`: collects `HAIJUN.md`, memory files, dates, etc.
- Both implement memoized caching
- It also considers skipping git status in certain Scenarios to reduce overhead
- Has explicit "bare mode / disable injection" handling for user context

This is a **lighter, more stable, more infrastructure-like** design.

### 5.3 Where HaijunBot Can Improve

HaijunBot can add the following capabilities:

1. **Layered context caching**:
   - System context: git status, branch, recent commits, tool Availability, working directory
   - User context: rules, project memory, short-term plans, README Abstract
   - Engineering context: recently edited files, recommended symbols, task list

2. **Incremental context refresh**:
   - Do not redo heavy analysis every round
   - Invalidate on file changes, branch changes, and task changes

3. **Context visualization**:
   - Haijun Code has `/context`
   - HaijunBot currently lacks an intuitive display of "what exactly is being fed to the Model now"

4. **Automatic injection of project convention documents**:
   - Similar to Haijun Code's `HAIJUN.md`
   - HaijunBot can use `.haijunbot/rules/project_info/README.md`, project rules, and Key Methodology Abstracts as a stable context layer

### 5.4 Recommendation Priorities

- **High priority**: session-level system context caching with incremental refresh
- **Medium priority**: context visualization command/tool
- **Medium priority**: automatic injection of project design documents and convention Abstracts

---

## 6. Tool System and Editing Reliability Comparison

### 6.1 Characteristics of HaijunBot's Tool System

HaijunBot mounts by default in `CodeAgent._build_code_agent_tool_list()`:

- `execute_script`
- `read_code`
- `edit_file`
- `load_rule`
- `virtual_tty`
- `search_web`
- `read_webpage`
- `memory`
- `methodology`
- `task_list_manager` (optional)

Strengths:

- Wide tool coverage
- Leans toward a unified "research + coding + knowledge accumulation" platform
- Has memory/methodology capabilities that Haijun Code does not fully replicate

### 6.2 Haijun Code FileEditTool's Strengths

`FileEditTool.ts` exposes a very mature tool governance design:

- Strict schema validation
- Path normalization to prevent relative paths/`~` from bypassing rules
- Permission checks executed at the tool layer
- Refuses to edit directories restricted by deny rules
- Prevents UNC path credential leakage (a Windows Security detail)
- Limits the maximum editable file size to prevent OOM
- Suggests similar paths when a file does not exist
- Handles edge cases such as empty files, file creation, and existing files
- Reads the current file state before editing, providing a basis for preventing accidental overwrites
- Integrates with git diff, file history, LSP, and VSCode notifications

This Describes Haijun Code's editing tool as not a "text replacement function", but an **infrastructure tool with Security, state, feedback, and diagnostic awareness**.

### 6.3 HaijunBot's Current Shortcomings

HaijunBot's `edit_file` search/replace is well suited to precise patches, but at the system level it currently lacks some capabilities:

- Lacks an explicit path-level permission Model
- Lacks large-file editing protection
- Lacks concurrent-write protection for "file already changed externally"
- Lacks unified editing history and IDE integration
- Lacks rule-based deny/allow path governance

### 6.4 Improvement Recommendations

**Recommendation 2: Strengthen the Security governance layer of HaijunBot's edit_file/execute_script.**

Recommended additions:

- Path allowlist/blocklist policies
- File size limits
- mtime/hash checks before editing
- Protected paths (e.g., `.git/`, `node_modules/`, `dist/`, binary directories) denied by default
- Add "read-only command / write command / dangerous command" classification to `execute_script`
- Apply extra interception policies to high-Risk commands in non-interactive mode

**Recommendation 3: Introduce a unified patch session and editing history.**

At minimum, it should record:

- Files modified in this round
- An Abstract of each edit, before and after
- Whether it passed subsequent Validation
- Whether a rollback was triggered

---

## 7. Task System and Validation Mechanism Comparison

### 7.1 HaijunBot: task_list_manager Is Already Strong

HaijunBot's `task_list_manager` is actually a strong asset of this project:

- Supports `add_tasks` / `execute_task` / `update_task`
- Requires task descriptions to include Constraints, required items, forbidden items, and Validation criteria
- Supports both `main` and `sub` task agent types
- Supports dependency management
- Supports the Validation Agent
- Supports recording verification_method
- Can also count Model call rounds

This is no longer a simple todo list, but an **execution planning system with Validation semantics**.

### 7.2 Haijun Code: A Lighter Task System, But More Closely Integrated with Multi-Agent/State Systems

Haijun Code's task tools:

- `TaskCreateTool`
- `TaskListTool`
- `TaskUpdateTool`

Their characteristics:

- Very clear schemas
- The UI automatically expands the task panel
- Has task created / completed hooks
- Can automatically associate an owner in agent swarm mode
- `TaskUpdateTool` is linked with the Validation agent type (`VERIFICATION_AGENT_TYPE`)
- Can collaborate through the teammate mailbox

Haijun Code does not rely on "very strict task descriptions" for quality, but on:

- Tool schemas
- System state
- Hooks
- UI visibility
- Multi-agent collaboration Mechanisms

### 7.3 The Complementary Relationship Between HaijunBot and Haijun Code

- HaijunBot is strong at **task content standardization**
- Haijun Code is strong at **task runtime integration**

### 7.4 HaijunBot Improvement Recommendations

**Recommendation 4: Upgrade task_list_manager from "strong prompt Constraints" to a "strong state system".**

It can add:

1. Task owner / worker agent concepts
2. Visible state during task execution
3. Task completion hooks
4. Task Validation hooks
5. Automatic association of tasks with the current diff/file changes
6. Support for "task recovery / suspension / background continuation"

**Recommendation 5: Productize the Validation Agent.**

HaijunBot already has a Validation Agent prototype; it is Recommended to complete:

- `verification` as an explicit agent type
- Automatically trigger the Validation agent after task completion
- Automatically write back task state on failed Validation
- Display Validation results structurally as a checklist

---

## 8. Multi-Agent Collaboration Capability Comparison

### 8.1 HaijunBot's Current State

HaijunBot has:

- `sub_agent`
- `sub_code_agent`
- Main/subtask agent dispatch in `task_list_manager`

Advantages:

- Already has a foundation for multi-agent execution
- Generic tasks and code tasks can be routed separately
- Can inherit some rules/tools through the parent agent

But the limitations are also obvious:

- Sub-agents are mostly "one-shot calls"
- Lacks long-lived agent identity
- Lacks message channels between agents
- Lacks team/role/queue/background lifecycles
- Lacks clear agent handoff Security checks

### 8.2 Haijun Code's Leading Position

As seen in the `AgentTool` directory, Haijun Code has formed a complete multi-agent system:

- Built-in agent types: `exploreAgent`, `planAgent`, `verificationAgent`, `generalPurposeAgent`
- `runAgent.ts` handles sub-agent execution
- `resumeAgent.ts` handles recovery
- `forkSubagent.ts` handles async/background sub-agents
- `agentMemory.ts` / `agentMemorySnapshot.ts` handle agent memory
- `SendMessageTool` supports sending messages to agents
- `TeamCreateTool` / `TeamDeleteTool` support team agent management
- `spawnTeammate()` indicates support for team/teammate mode
- Has concepts such as mailbox, owner, team_name, and agent_id
- Has a handoff classifier that performs Security classification on sub-agent output

This is an evolution from "subtask execution" to an "agent collaboration system".

### 8.3 HaijunBot Improvement Recommendations

**Recommendation 6: Upgrade HaijunBot's sub-agent system to "role-based collaborating agents".**

The first Phase can start with:

- Built-in agent types: `explore`, `plan`, `implement`, `verify`
- Each agent type has an independent system prompt and default tool set
- Unified sub-agent output structure
- Support explicitly returning sub-agent results to the main agent

The second Phase can do:

- agent_id / mailbox / send_message
- Background agents and recovery Mechanism
- team coordinator
- Agent worktree isolation

### 8.4 Points Particularly Worth Borrowing

Haijun Code's `AgentTool` explicitly restricts:

- Teammates cannot spawn more teammates, keeping the team roster flat
- In-process teammates cannot spawn background agents
- Performs Security handoff classification on sub-agent output

Such Constraints are very Key, because once multi-agent systems lack rules, complexity can quickly spiral out of control.

---

## 9. Permission and Security Model Comparison

### 9.1 HaijunBot's Current State

HaijunBot's Security relies more on:

- System prompt Constraints
- User confirmation
- The review/revert workflow
- Git diff and rollback capabilities
- Build Validation / lint / impact analysis

This already helps with engineering tasks, but it is more **post-execution governance** and **Flow Constraints**.

### 9.2 Haijun Code's Current State

Haijun Code clearly leans more toward **pre-execution governance**:

- Every tool has a permission model
- `EnterPlanModeTool` modifies the permission mode
- `FileEditTool` performs permission checks at the tool layer
- Has modes such as `default/plan/acceptEdits/dontAsk/auto`
- Spawning sub-agents also requires permission
- Supports organization policy limits (the README mentions `policyLimits/`)

### 9.3 HaijunBot Improvement Recommendations

**Recommendation 7: Add a unified PermissionContext to HaijunBot.**

It is Recommended to support at least:

- Modes: `default` / `plan` / `execute` / `dangerous`
- Path permissions: read/write/deny
- Tool permissions: allow / require confirmation / forbid
- Risk grading for shell commands
- Automatic permission decision rules for non-interactive mode

This will elevate HaijunBot from "relying on prompt self-discipline" to "system-level Constraint enforcement".

---

## 10. Memory System Comparison

### 10.1 HaijunBot's Advantages

HaijunBot's memory system is clearly more systematic than the capabilities exposed by Haijun Code's current code snapshot:

- The `memory` tool uniformly supports save/retrieve/clear
- Memory layering: short-term / project long-term / global long-term
- Combined with methodology and rules, it can form long-term knowledge accumulation
- Memory counts are displayed directly in Agent startup statistics
- `sub_agent` / `sub_code_agent` also merge memory tags back into the parent agent

This is HaijunBot's strength, and it is Recommended to keep and strengthen it.

### 10.2 Haijun Code's Highlights

Haijun Code also has things worth borrowing:

- `context.ts` reads memory files / HAIJUN.md
- The README mentions `extractMemories/` and `teamMemorySync/`
- `agentMemory.ts` and `agentMemorySnapshot.ts` show its memory is more deeply bound to the sub-agent lifecycle

### 10.3 Directions Where HaijunBot Can Strengthen

**Recommendation 8: Upgrade the memory system from a "storage capability" to an "automatic injection and automatic distillation capability".**

Recommendations:

- Automatically extract candidate memories at the end of each round
- Distinguish facts, preferences, project conventions, and temporary execution plans
- Automatically summarize sub-agent results into structured short-term memory
- Automatically form "experience memory" candidates after task completion
- Automatically include project design documents in the searchable context layer

---

## 11. Observability and User Experience Comparison

### 11.1 Haijun Code's Obvious Advantages

As seen from its directories and tool implementations, Haijun Code is clearly more mature in these aspects:

- `renderToolUseMessage` / `renderToolResultMessage` / `renderToolUseRejectedMessage`
- Automatic task list expansion
- Grouped sub-agent progress UI display
- Context visualization
- Plan mode, task, and agent are all stateful objects
- Rich progress events

### 11.2 HaijunBot's Current State

HaijunBot's current Advantages lie in information and Methodology, but its runtime experience leans more toward "terminal log streams":

- State exists in prompts and text output
- Tool execution results rarely form a unified visual state
- Subtasks/Validation/review lack a unified panel-style representation

### 11.3 HaijunBot Improvement Recommendations

**Recommendation 9: Add execution-state visualization objects to HaijunBot.**

For example:

- Current mode
- Abstract of the current task list
- Currently collected context files
- Current set of changed files
- Current Validation state
- Current Risks level

Even a pure terminal text panel would significantly improve Availability.

---

## 12. Designs HaijunBot Has Not Yet Implemented, but Worth Borrowing from Haijun Code

Below are the designs currently most worth borrowing that HaijunBot has not yet fully implemented.

### 12.1 Explicit Plan Mode State Machine

**Haijun Code Current State:** `EnterPlanModeTool` explicitly switches state and restricts behavior.

**HaijunBot current state:** Only Flow conventions, no real state machine.

**Recommendation: introduce at high priority.**

---

### 12.2 Tool-Level Permission System

**Haijun Code Current State:** tools carry their own permission checks, adjudicated by mode and path rules.

**HaijunBot current state:** Mainly relies on prompts, confirmation, and Flow control.

**Recommendation: introduce at high priority.**

---

### 12.3 Role-Based Sub-Agent System

**Haijun Code Current State:** explore / plan / verification / teammate / team.

**HaijunBot current state:** sub_agent / sub_code_agent are fairly generic.

**Recommendation: introduce phased at high priority.**

---

### 12.4 Sub-Agent Security Handoff Classifier

**Haijun Code Current State:** run a classifier check on sub-agent handoffs and generate warnings.

**HaijunBot current state:** sub-agent result returns lack dedicated Security classification.

**Recommendation: medium-high priority.**

---

### 12.5 Background Agents and Recovery Mechanism

**Haijun Code Current State:** async/background agents, resume, mailbox.

**HaijunBot current state:** sub-agents are mostly synchronous one-shot executions.

**Recommendation: medium priority.**

---

### 12.6 Layered Context Caching

**Haijun Code Current State:** system/user context is layered and cached.

**HaijunBot current state:** relies more on on-demand analysis and recommendation.

**Recommendation: high priority.**

---

### 12.7 File Editing Robustness Protection

**Haijun Code Current State:** path normalization, deny rules, large-file protection, and concurrent-change protection.

**HaijunBot current state:** search/replace is precise, but system protections are sparse.

**Recommendation: high priority.**

---

### 12.8 Task Hooks and UI State Integration

**Haijun Code Current State:** task creation/completion hooks, task panel expansion, and automatic owner assignment.

**HaijunBot current state:** strong task specifications, but weak runtime integration.

**Recommendation: medium priority.**

---

## 13. HaijunBot's Existing Advantages Should Not Blindly Copy Haijun Code

It should also be noted that Haijun Code is not superior to HaijunBot in every aspect. HaijunBot has several capabilities that should continue to be upheld, or even strengthened as Differentiating directions.

### 13.1 Rule System and Methodology System

HaijunBot's `load_rule`, `methodology`, project-level rules, and codifiable Flow knowledge are not reflected with equal strength in Haijun Code's code snapshot.

### 13.2 Research Workflow Capability

ARCHER is very well suited for:

- Code research
- Solution Comparison
- Project reverse engineering
- Technology selection
- Open-source project investigation

Haijun Code is more like a productized executor, while HaijunBot is more like an engineering research assistant. This positioning is worth keeping.

### 13.3 Code Analysis Depth

HaijunBot's `ContextManager`, `ImpactAnalyzer`, `DependencyAnalyzer`, `BuildValidationManager`, and `LintManager` form a clearer engineering Validation chain.

### 13.4 Layered Memory Design

HaijunBot's three-tier short-term/project/global memory is well suited to long-term use, and automatic distillation and automatic injection should be further strengthened rather than weakened.

---

## 14. Recommended Improvement Roadmap

### P0: Should be advanced as soon as possible

1. **Explicit Plan Mode**
   - Add `enter_plan_mode` / `exit_plan_mode`
   - Add an Agent mode state field
   - Forbid write operations in plan mode

2. **Tool-level permission context**
   - Add unified permission checks for `edit_file`, `execute_script`, and `virtual_tty`
   - Support path rules, command Risks levels, and non-interactive automatic decisions

3. **Layered context caching**
   - Layer by system context / user context / project context
   - Incremental invalidation
   - Reduce repeated analysis overhead

4. **Editing robustness enhancement**
   - File size limits
   - hash/mtime checks
   - Protected paths denied by default
   - Editing history records

### P1: Recommended for the medium term

5. **Role-based sub-agents**
   - Four built-in agent types: explore / plan / implement / verify
   - Different default tool sets and system prompts

6. **Productize the Validation agent**
   - Automatic Validation after task completion
   - Automatic task-state writeback on Validation failure

7. **Task hooks and task state panel**
   - create/update/complete hooks
   - Integrate with diff, file changes, and Validation state

8. **Context visualization**
   - Add a current-context Abstract command
   - Display system context, project context, injected memory, and recommended code files

### P2: Long-Term Evolution Directions

9. **Background agents and recovery Mechanism**
10. **agent mailbox / send_message**
11. **team/coordinator Model**
12. **Sub-agent output Security classifier**
13. **Runtime visualization on the IDE / Web UI side**

---

## 15. An Executable Landing Example

If only a "small-version iteration" is allowed first, it is Recommended to prioritize the following combination:

### 15.1 Goals

Upgrade HaijunBot from "prompt-driven Flow Constraints" to a "state-driven Secure execution framework".

### 15.2 Specific Scope

- Add the Agent `mode` state
- Implement plan mode tools
- Add PermissionContext for `edit_file` / `execute_script`
- Record task state and the current mode in `task_list_manager`
- Output a current execution-state panel

### 15.3 Expected Benefits

- More stable complex tasks
- More Secure non-interactive mode
- Easier future integration with Web/IDE
- Fully compatible with the current ARCHER design

---

## 16. Final Conclusion

### 16.1 One-Sentence Assessment

- **HaijunBot**: more like an "engineering-research, rule-driven, code-analysis" code Agent platform.
- **Haijun Code**: more like a "state-driven, built-in-permission, collaboration-productized" code Agent system.

### 16.2 The Most Valuable Directions for HaijunBot to Borrow

The most valuable thing to learn is not Haijun Code's UI, but the three things behind it:

1. **State-machine-based plan/execute permission switching**
2. **Built-in tool-layer permissions and editing Security governance**
3. **Role-based multi-agent collaboration system**

### 16.3 The Most Important Directions for HaijunBot to Keep

HaijunBot should not give up the parts where it has already formed Advantages:

- The ARCHER research workflow
- The rule system and Methodology system
- Layered memory
- Deep code analysis and the Validation chain

A more reasonable path is not to "turn HaijunBot into a replica of Haijun Code", but:

> Keep HaijunBot's Advantages in rules, research, analysis, and Validation, while adopting Haijun Code's mature designs in state management, permission governance, and collaboration systems.

This will give HaijunBot a better chance to become a project-level code Agent platform suited to both deep engineering research and stable code execution.

---

## 17. Improvement Item Checklist Overview

| Priority | Improvement item        | Current HaijunBot state | Haijun Code reference point       |
| ------ | ------------------ | ---------------- | -------------------------------- |
| P0     | Explicit Plan Mode | Prompt Constraints only      | `EnterPlanModeTool`              |
| P0     | Tool-level permission context | Weak             | tool permission system           |
| P0     | Editing robustness | Partially available | `FileEditTool`                   |
| P0     | Layered context caching | Weak             | `context.ts`                     |
| P1     | Role-based sub-agents | Generic sub-agents | `AgentTool` built-in agents      |
| P1     | Productized Validation agent | Prototype exists | verification agent + task update |
| P1     | Task hooks / panel | Has a task system | `TaskCreate/Update/ListTool`     |
| P1     | Context visualization | Basic missing | `/context` direction             |
| P2     | Background agent recovery | Basic missing | `resumeAgent` / background agent |
| P2     | agent mailbox | Basic missing | `SendMessageTool` / mailbox      |
| P2     | Sub-agent handoff Security classification | Basic missing | `classifyHandoffIfNeeded`        |

---

## 18. Reference Code Location Index

### HaijunBot

- CodeAgent main class: `src/haijunbot/haijunbot_code_agent/code_agent.py:72-338`
- CodeAgent tool list: `src/haijunbot/haijunbot_code_agent/code_agent.py:189-228`
- Requirement classification and Scenario prompts: `src/haijunbot/haijunbot_code_agent/code_agent_prompts.py:22-250`
- Generic Agent system prompt and resource management: `src/haijunbot/haijunbot_agent/__init__.py:217-260`
- Generic sub-agent: `src/haijunbot/haijunbot_agent/sub_agent.py:22-209`
- Code sub-agent: `src/haijunbot/haijunbot_code_agent/sub_code_agent.py:18-208`
- Task list tool: `src/haijunbot/haijunbot_tools/task_list_manager.py:91-320`
- Code analysis capability exports: `src/haijunbot/haijunbot_code_agent/code_analyzer/__init__.py:1-69`
- LLM context recommender: `src/haijunbot/haijunbot_code_agent/code_analyzer/llm_context_recommender.py:27-260`

### Haijun Code

- Project overview: `../haijun-code/README.md:41-271`
- system/user context: `../haijun-code/src/context.ts:36-189`
- plan mode: `../haijun-code/src/tools/EnterPlanModeTool/EnterPlanModeTool.ts:36-126`
- File editing tool: `../haijun-code/src/tools/FileEditTool/FileEditTool.ts:86-260`
- Task list: `../haijun-code/src/tools/TaskListTool/TaskListTool.ts:33-116`
- Task creation: `../haijun-code/src/tools/TaskCreateTool/TaskCreateTool.ts:48-138`
- Task update: `../haijun-code/src/tools/TaskUpdateTool/TaskUpdateTool.ts:88-260`
- Agent tool: `../haijun-code/src/tools/AgentTool/AgentTool.tsx`
- Agent tool utilities: `../haijun-code/src/tools/AgentTool/agentToolUtils.ts`
- Agent execution: `../haijun-code/src/tools/AgentTool/runAgent.ts`
