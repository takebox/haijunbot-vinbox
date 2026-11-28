# AI Dark Factory: Built-in Orchestration Execution Engine (Plan B) Design

> Status: **pending review (design before implementation)**
> Goal: let the dark factory's 4 agents (planner -> generator -> validator -> orchestrator) **collaborate automatically and in order**, while keeping the gate as a manual approval checkpoint (not fully unattended).
> Basis: a complete investigation of HaijunBot's multi-Agent orchestration mechanism (see "Investigation Facts" at the end).
>
> **Related**: orchestration files now support `.flow` (Python DSL, compile-time DAG generation); the dark factory can be one of its users. See `docs/design/orchestration-python-dsl.md`.

---

## 0. Background and Problem

The current dark factory uses `@OrganizeAgents` to load `dark_factory_pipeline.yaml`, which only **batch-creates 4 agents with a `task` (role description)**. The investigation confirms (see the end for details):

- `@OrganizeAgents` (`builtin_input_handler.py:546-757`) **returns directly after creating the agents, with no automatic execution**.
- An agent with `--task` (regardless of `no_interaction_mode`) **executes the task once and then exits** after starting (hjb `haijunbot.py:1647-1653,1713`; hca `code_agent.py:1726-1760`); web_gateway is closed in its finally block.
- The orchestration file **only supports single-agent creation fields; no dependency/order/artifact-passing fields** (`builtin_input_handler.py:711-729`).
- The system has **no ready-made "wait/join multi-agent sequential execution" mechanism** (`dispatch` is parallel tmux dispatch, `tmux_wrapper.py:72`).

**Conclusion**: the dark factory currently has "pipeline roles created, but no pipeline scheduling engine". Making the 4 agents collaborate automatically requires a **built-in orchestration execution engine** (Plan B).

**Design orientation**: the orchestration execution engine (`pipeline_runner`) is **generic infrastructure**, unrelated to the dark factory's specific business (NLSpec/four-layer architecture/holdout/gate). It lives in the core tools directory; any plugin/user can use it to define their own multi-Agent pipelines; the dark factory is just one of its users (declaring its own stages and artifact contract through the `flow` field of the orchestration file).

**Dynamic orchestration file generation**: the orchestration file (containing `agents` and `flow`) is a **structured plan dynamically generated for each task**; the orchestration agent produces it jointly from the spec, the current state of the codebase, and user discussion; it is executed after the user confirms. The plugin's bundled `dark_factory_pipeline.yaml` is only a reference template, not directly used for every task. The dark factory works in an **existing codebase** -- the generator stage directly modifies the current code, not producing into a separate directory.

---

## 1. Design Goals and Principles

### 1.1 Goals

1. One trigger; automatically run the full `plan -> generate -> validate -> gate` four-layer pipeline.
2. **Auto-pass intermediate artifacts** between layers (implementation plan -> codebase changes -> pass/fail report).
3. Each layer **automatically waits for completion** before triggering the next.
4. **Stop and wait for manual approval at the gate**; no auto-merge (not fully unattended).

### 1.2 Principles

- **Coordinate only, do not execute** (sw-controller mode): the scheduler does not write code or run tests; it only schedules in order and passes artifacts.
- **Reuse existing mechanisms**: prioritize reusing `hca -n --task-file` + `status_file` (the ready-made non-interactive execution + status callback); do not reinvent the wheel.
- **Minimal invasiveness**: do not change the core agent startup logic; provide the new capability as a **core generic tool**.
- **Keep the manual approval checkpoint**: stop at the gate, consistent with the admin's "not fully unattended" decision.

---

## 2. Overall Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Trigger entries (three kinds)                              │
│  ① user enters <dark-factory/issue> / <dark-factory/pr>      │
│  ② user enters <dark-factory/run> (new; runs the pipeline directly) │
│  ③ main agent calls the pipeline_runner tool                 │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Orchestration execution engine pipeline_runner (core generic tool, auto-registered) │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Read the orchestration definition (flow order)         │ │
│  │ For each stage:                                        │ │
│  │   1. assemble the task-file (this stage's task + upstream artifact paths) │ │
│  │   2. launch the stage agent with hca -n --task-file (synchronous) │ │
│  │   3. poll status_file waiting for completed/failed      │ │
│  │   4. verify the artifact was written; write it into the next stage's task-file │ │
│  │ Gate stage: output the approval report, then stop and wait for manual approval │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
    planner --plan--> generator --code--> validator --report--> orchestrator --approval report--> manual approval
```

---

## 3. Orchestration Definition Format Extension (orchestration file gains `flow`)

On top of the `agents` in `dark_factory_pipeline.yaml`, add a top-level `flow` field describing **stage order and artifact contract**:

```yaml
agents:
  - name: "df_planner"
    type: "agent"
    working_dir: "."
    task: "..."   # role description (unchanged)
  # ... df_generator / df_validator / df_orchestrator

flow:
  - stage: "planner"
    agent: "df_planner"
    output: ".df/plan.md"          # this stage's artifact (implementation plan)
  - stage: "generator"
    agent: "df_generator"
    input: ".df/plan.md"           # depends on the previous stage's artifact
    # no separate output: the generator directly modifies code in working_dir (existing codebase)
  - stage: "validator"
    agent: "df_validator"
    input: ".df/plan.md"           # depends on the planning artifact; the validation target is the modified working directory
    output: ".df/report.json"      # pass/fail report
  - stage: "orchestrator"
    agent: "df_orchestrator"
    input: ".df/report.json"
    output: ".df/approval.md"      # approval report (handed to a human)
    gate: true                     # gate: stop and wait for manual approval
```

**Compatibility**: `flow` is an **optional** field. Without `flow`, `@OrganizeAgents` behaves unchanged (only creates agents). With `flow`, the orchestration engine drives execution per the flow.

---

## 4. Core Component: the pipeline_runner Tool

### 4.1 Location and form

- **File**: `src/haijunbot/haijunbot_tools/pipeline_runner.py` (**core generic tool**, not plugin-specific)
- **Class**: `PipelineRunnerTool` (`name = "pipeline_runner"`, equal to the file name stem)
- **Registration**: the core tools directory is auto-scanned and registered by `ToolRegistry._load_builtin_tools` (`registry.py:600-620`); no configuration needed.
- **Genericity**: does not depend on any plugin business. It only does "read the orchestration file flow -> drive agents in order -> pass artifacts -> wait for completion"; the specific stages/artifacts/gates are declared by the **using party's orchestration file**.
- **Responsibility**: read the orchestration file + drive each stage's agent with `hca -n --task-file` per flow order, poll status_file to wait, pass artifacts, stop at the gate.

### 4.2 Parameters

```json
{
  "type": "object",
  "properties": {
    "orchestration_file": {"type": "string", "description": "orchestration YAML path"},
    "working_dir": {"type": "string", "description": "working directory (default: current directory)"},
    "approve": {"type": "boolean", "description": "whether the gate stage has received manual approval (default false; requires human confirmation)"}
  },
  "required": ["orchestration_file"]
}
```

### 4.3 Execution flow

```text
execute(args):
  1. Validate parameters: orchestration_file exists; the file parses and contains agents + flow.
  2. Initialize the working directory: create the .df/ directory.
  3. Iterate over each stage in the flow:
     a. Assemble the task-file JSON:
        {
          "task_desc": <agent.task role description> + "\n\nInput artifact for this stage:\n" + <summary of the input path content>,
          "background": "Dark factory pipeline, stage=<stage>, input=<input>, output=<output>",
          "additional_info": "Write this stage's artifact to <output>, then exit.",
          "status_file": "<working_dir>/.df/<stage>.status"
        }
     b. Run via subprocess: hca -n --task-file <taskfile> (cwd=working_dir).
     c. Poll <stage>.status until "completed"/"failed" appears (timeout raises an error).
     d. Verify the <output> artifact was written; on failure, abort the pipeline and report.
  4. Gate stage (gate: true):
     a. Output the approval report path .df/approval.md.
     b. If approve=false: stop; return "approval report generated; after manual approval, re-run the gate confirmation with approve=true".
     c. If approve=true: mark the pipeline complete; return the summary.
  5. Return {"success", "stdout", "stderr"}; stdout contains each stage's status and artifact paths.
```

### 4.4 Key implementation points

- **Synchronous waiting**: poll status_file (2s interval; default timeout 30min, configurable). Reuse the `status_file` mechanism (`haijunbot.py:1758-1801`).
- **Artifact passing**: the upstream stage's `<output>` path is written into the next stage's task-file `input`; the agent reads it via `additional_info`.
- **Failure handling**: abort on any stage failing; keep already-written artifacts for troubleshooting.
- **Gate stop**: after the orchestrator stage completes, the engine does not continue; it waits for manual approval (the `approve` parameter).
- **hca availability**: validate `shutil.which("hca")` before calling; raise an error if unavailable.

---

## 5. Trigger Entries (three kinds)

### 5.1 New replace_map instruction `<dark-factory/run>`

Add to the `replace_map` in `config.yaml`:

```yaml
dark-factory/run:
  append: false
  template: |
    Run the dark factory pipeline with the built-in orchestration engine pipeline_runner.
    - First confirm the NLSpec is ready; otherwise complete it with spec_validator.
    - Discuss with the user and dynamically generate the orchestration file (agents + flow, referring to
      the orchestration/dark_factory_pipeline.yaml template); write the NLSpec content into
      the top-level spec field of the orchestration file (the engine injects it into each stage Agent's background
      from there); save it to .df/pipeline.yaml after the user confirms it is correct.
    - Call pipeline_runner to execute (approve=false; stop at the gate).
    - After the run, hand the approval report to a human for approval.
```

When the user enters `<dark-factory/run>`, the main agent is triggered: discuss with the user to generate the orchestration file -> user confirms -> call pipeline_runner.

### 5.2 Keep `<dark-factory/issue>` / `<dark-factory/pr>`

These two entries target GitHub Issue/PR-driven flows; their templates likewise change to "dynamically generate the orchestration file + user confirmation + run the pipeline with pipeline_runner"; everything else remains unchanged.

### 5.3 Manual invocation

The main agent or the orchestrator agent can directly call the `pipeline_runner` tool.

---

## 6. Relationship to Existing Mechanisms

| Existing mechanism      | Usage under Plan B                                             |
| ----------------------- | -------------------------------------------------------------- |
| `@OrganizeAgents`       | **Kept**: without `flow`, still only creates agents; with `flow`, it is recommended to use pipeline_runner to drive execution |
| `hca -n --task-file`    | **Reused**: as the stage agent's execution entry (`haijunbot.py:1095-1119`) |
| `status_file`           | **Reused**: as the stage completion status callback (`haijunbot.py:1758-1801`) |
| `send_to_agent`         | **Not used** (async; cannot synchronously wait; and task-carrying agents have already exited) |
| `no_interaction_mode`   | **Not used** (stage agents are driven by hca -n, naturally non-interactive) |
| the 3 tools (spec_validator/holdout_generator/gate_calculator) | **Kept**: still callable inside each stage agent |

---

## 7. Landing the "Not Fully Unattended" Requirement

- **Fully automatic segment**: planner -> generator -> validator are driven automatically by the engine; can run unattended.
- **Manual approval checkpoint**: after the orchestrator produces the approval report, the engine **stops**, returns the approval report path, and waits for a human `approve=true` confirmation before marking completion.
- **No automatic merge**: the engine does not do git merge / PR merge; delivery/merge is triggered by a human after approval.

---

## 8. Implementation Steps

1. **Extend the orchestration file**: add the `flow` field to `dark_factory_pipeline.yaml` (stage order + artifact contract).
2. **Add the core generic tool** `src/haijunbot/haijunbot_tools/pipeline_runner.py`: implement `PipelineRunnerTool` (validate / assemble task-file / launch hca / poll status / artifact check / gate stop). Placed in the core directory and auto-registered by `ToolRegistry._load_builtin_tools` (`registry.py:600-620`); no configuration needed.
3. **Update config.yaml**: add `dark-factory/run` to `replace_map` (template: discuss with the user to dynamically generate the orchestration file -> user confirms -> call pipeline_runner).
4. **Update the rules**: add a "drive the pipeline with pipeline_runner" note to `orchestration.md`.
5. **Update the design doc**: record the Plan B orchestration engine design.
6. **Add tests**: add pipeline_runner unit tests to `tests/haijunbot_tools/test_pipeline_runner.py` (mock hca subprocess + status_file).

---

## 9. Verification

- **Unit tests**: pipeline_runner calls hca in flow order in a mocked scenario, polls status, passes artifacts, and stops at the gate.
- **Orchestration file**: yamllint passes; the `flow` field parses.
- **End-to-end (optional; requires a real environment)**: after `<dark-factory/run>` is triggered, observe the 4 stages executing in order, artifacts landing on disk, and the gate stopping.

---

## 10. Risks and Countermeasures

| Risk                                | Countermeasure                                                    |
| ----------------------------------- | ---------------------------------------------------------------- |
| a stage agent never finishes        | poll timeout (default 30min, configurable); on timeout, error out and keep artifacts |
| artifact contract mismatch (a stage did not write its output) | validate the output is on disk after each stage; abort if missing |
| hca unavailable / not logged in     | validate `shutil.which("hca")` before launch; error with a prompt |
| gate accidentally auto-passes       | default `approve=false`; manual confirmation is mandatory        |
| conflict with `@OrganizeAgents` behavior | `flow` is optional; without flow, the original behavior is kept; backward compatible |

---

## 11. Investigation Facts (basis for the proposal)

1. **@OrganizeAgents**: `builtin_input_handler.py:546-757`; returns directly after creating agents; no automatic execution.
2. **Agent startup**: `agent_manager.py:251` Popen; `AGENT_ENTRY_POINTS={agent:hjb, code_agent:hca}` (115-118); with `--task`, it executes once then exits (hjb `haijunbot.py:1647-1653,1713`; hca `code_agent.py:1726-1760`).
3. **Message passing**: `send_to_agent` (`gateway_manager.py:617`) goes through `/api/agent/{id}/message`; the `/message` endpoint `haijunbot.py:1527-1558` injects into the input stream and works only for standby agents without a task.
4. **task-file/status_file**: `haijunbot.py:1095-1119` parses the task-file (task_desc/background/additional_info/status_file); `haijunbot.py:1758-1801` writes back status/.output/.error files after execution.
5. **Orchestration file fields**: `builtin_input_handler.py:711-729`; no dependency/order/artifact fields.
6. **Sequential execution mechanism**: no ready-made wait/join; `dispatch` is parallel tmux dispatch (`tmux_wrapper.py:72`).
7. **Agent execution entries**: CLI task (hjb:1647/hca:1726), `/message` (haijunbot.py:1527), interactive loop (hjb:1689-1711); the main loop is `agent.run` (`haijunbot_agent/__init__.py:1958`).

---

## Appendix A: pipeline_runner Supporting DAG Orchestration (design)

> Status: **implemented (2026-10-08)**. Core implementation is in `src/haijunbot/haijunbot_tools/pipeline_runner.py`; tests are in `tests/haijunbot_tools/test_pipeline_runner.py` (43 cases). Unit tests and mocked end-to-end verification pass; **real-environment end-to-end verification is deferred per the administrator's request**.
> Goal: upgrade `pipeline_runner`'s `flow` from a **linear list** to a **DAG (directed acyclic graph)**, supporting parallelism, multi-input fan-in, conditional branching, failure policies, and retries.
> Scope confirmation (administrator 2026-10-08): **do all of it** (parallel / multi-input / conditional / failure policies / retry), default parallelism 4.

## A.1 Background and Problem

The current `pipeline_runner.py` (`src/haijunbot/haijunbot_tools/pipeline_runner.py`) `flow` is a **linear array**; `execute()` iterates sequentially with `for idx, stage in enumerate(flow)`:

- Each stage **can only specify one agent** (`agent_name` is a single string; lines 154-157 validate that it is within `agents_by_name`).
- Input **can only be the previous stage's output** (`stage_input = input_ref or previous_output`, line 163) -- no multi-input, no branching, no parallelism, no loops.
- A stage failure **aborts the whole run** (lines 201-207); no retry, no fault-tolerant branching.

**Conclusion**: flow currently only supports **linear order**. To support "more complex orchestration flows" (dark factory multi-validator parallelism, branching on results, multi-report fan-in, etc.), flow needs to be upgraded to a DAG.

## A.2 Design Goals and Principles

1. **DAG scheduling**: support parallelism, multi-input fan-in, conditional branching, failure policies, and retries.
2. **Coordinate only, do not execute** (unchanged): the scheduler does not write code or test; it only schedules and passes artifacts.
3. **Stage agent = resident Agent entity, uniformly using `hjb`**: each flow stage corresponds to a **resident Agent entity** (created via `_create_agent`, `type: agent` -> `hjb --web-gateway` standby), whose task is sent via `send_to_agent` with **synchronous waiting** for completion. **Uniformly use `hjb`** -- `hjb` (`haijunbot_agent/haijunbot.py`) has **no repository file lock** (the lock only exists in `hca`'s `code_agent.py:1688-1696`); multiple resident hjb Agents can run in parallel safely. Do not use the one-shot `hca -n --task-file` subprocess as the parallel carrier (constrained by the repository file lock; see A.5.1).
4. **Unified hjb entry**: stage Agents are always `type: agent` -> `hjb` (`agent_manager.py:115-118`), avoiding hca's repository lock.
5. **Backward compatible**: old orchestration files (linear flow) need zero changes; `flow` remains optional; without flow, `@OrganizeAgents` behaves unchanged.
6. **Security**: `when` conditions use a restricted expression parser; never `eval` arbitrary code.

## A.3 Core Concept: from "list" to "graph"

**Current state**: `flow` is an array of `[{stage, agent, input, output, gate}]`; the implicit order = the array index.

**After upgrade**: `flow` remains an array (keeping it human-readable and backward compatible), but each stage explicitly declares `depends_on` (the list of upstream stages it depends on); the engine builds the DAG from it and does **topological sort + parallel scheduling**.

```yaml
flow:
  - stage: "plan"
    agent: "df_planner"
    output: ".df/plan.md"

  # two validators in parallel, both depend on plan
  - stage: "verify_unit"
    agent: "df_validator_unit"
    input: ".df/plan.md"
    output: ".df/report_unit.json"
    depends_on: ["plan"]

  - stage: "verify_e2e"
    agent: "df_validator_e2e"
    input: ".df/plan.md"
    output: ".df/report_e2e.json"
    depends_on: ["plan"]

  # fan-in: the orchestrator consumes both validation reports
  - stage: "orchestrate"
    agent: "df_orchestrator"
    input: [".df/report_unit.json", ".df/report_e2e.json"]
    output: ".df/approval.md"
    depends_on: ["verify_unit", "verify_e2e"]
    gate: true
```

**Key points**:

- `depends_on` defaults to the previous stage (**keeping the linear style fully compatible; old orchestration files need no changes**).
- `input` is upgraded to **accept a list** (multi-input fan-in).
- Stages without dependencies automatically enter parallel scheduling.

## A.4 Field Extensions

| Field             | Current state | DAG version       | Description                                      |
| ----------------- | ------------- | ------------------ | ------------------------------------------------ |
| `stage`           | string        | string             | stage unique name (graph node ID)               |
| `agent`           | single string | single string      | still a single agent per stage (keeping the "coordinate only" semantic) |
| `depends_on`      | ❌ none       | `[stage names]` optional | explicit dependencies; default = previous     |
| `input`           | single string | **string or list** | multi-input fan-in                              |
| `output`          | single string | single string      | artifact path                                   |
| `gate`            | bool          | bool               | gate                                            |
| `when`            | ❌ none       | conditional expression (optional) | conditional branching               |
| `retry`           | ❌ none       | int (optional)     | failure retry count                             |
| `on_error`        | ❌ none       | `abort`/`continue`/`skip_dependents` | failure policy                      |
| `default_on_error`| ❌ none       | top-level optional, same three values | the global default when a stage does not declare `on_error` (invalid value falls back to `abort`) |

## A.5 Scheduling Engine (core change)

`execute()` changes from a `for` linear loop to a **DAG scheduling loop**:

```text
execute(args):
  1. Validate parameters (same as today)
  2. Parse the flow and build the graph:
     - node = stage; edge = depends_on relationship
     - validate: unique stage names, agent exists, referenced stages in depends_on exist
     - topological sort; detect cycles (error out and do not execute if cyclic)
  3. Initialize the artifact directory .df/, spec summary (same as today)
  4. Create the resident Agent entities needed by this pipeline (via _create_agent; type determines hjb/hca)
  5. Scheduling loop (key addition):
     while there are unfinished nodes:
       - ready = nodes whose dependencies have all completed successfully
       - send tasks in parallel to the resident Agents for the ready nodes (concurrency cap max_workers, default 4)
       - each node = one independent Agent (send_to_agent sends -> synchronous wait for completion -> verify artifact)
       - collect each node's result; update the completed set
  6. Gate: after any gate node completes, stop if approve=false (same as today)
  7. Failure policy: handle per on_error
  8. Return the summary (stdout contains each stage's status/artifact/duration)
```

### A.5.1 Key constraint: the hca repository file lock (why uniformly use hjb)

**Code facts** (`code_agent.py:1688-1696`, `utils.py:421-470`, `haijunbot_agent/haijunbot.py`):

- **hca** (`code_agent.py`) takes an exclusive lock on startup keyed by the **repository root**: `code_agent_{md5(repo_root)}.lock` (`code_agent.py:1692`). The lock is **non-blocking exclusive**: when an existing live instance holds the lock, a new process **directly `sys.exit(0)`** (`utils.py:432-436`). **The `--web-gateway` resident mode also reaches this lock** (`code_agent.py:1591-1603`, then continues to 1690).
- **hjb** (`haijunbot_agent/haijunbot.py`) has **no file-lock logic at all** (grep finds no `_acquire_single_instance_lock`), and supports both `--web-gateway` resident mode (`haijunbot.py:950-957,1262`) and `--task-file` (`haijunbot.py:819-820`).

**Conclusion (administrator decision 2026-10-08)**: **parallel orchestration uniformly uses `hjb` resident Agents**, fundamentally avoiding hca's repository file lock -- multiple resident hjb Agents can run in parallel safely under the same repository, **with no worktree isolation needed** (the worktree option is not accepted).

### A.5.2 Parallelism implementation (resident hjb Agent + synchronous send_to_agent wait)

Each flow stage is a **resident `hjb` Agent entity**. Parallelism = sending tasks to multiple mutually-independent resident Agents at the same time and waiting for each to complete, **not a thread-pool schedule, nor one-shot hca subprocesses**.

- **Creation**: create resident Agents via `_create_agent`, **uniformly `type: agent` -> `hjb --web-gateway`** on standby (`agent_manager.py:115-118`); no repository lock; can run in parallel.
- **Sending**: `send_to_agent` sends each Agent its stage task.
- **Synchronous waiting**: **add a `wait` parameter to `send_to_agent`** -- it is currently async fire-and-forget (`gateway_manager.py:617` only sends a message and returns immediately; the `/message` endpoint `haijunbot.py:1527` only injects into the input stream). With `wait=true`, wait for the Agent to finish processing and return the result (see A.5.3).
- **Concurrency cap**: `max_workers` defaults to 4, limiting the number of simultaneously-executing resident Agents to avoid exhausting resources.
- **Artifact isolation**: `status_file` distinguishes by the `stage` name; the artifact directory `.df/` has independent files per stage; hjb has no repository lock, so parallel execution under the same repository needs no worktree.

### A.5.3 New capability: the `wait` parameter of send_to_agent

The current `send_to_agent` only delivers a message and does not wait for the result. To support "synchronously wait for a stage Agent to complete", **add a `wait` parameter to `send_to_agent` (administrator decision 2026-10-08)**:

- **`wait=false` (default, backward compatible)**: behavior unchanged; async fire-and-forget.
- **`wait=true`**: after sending, **poll the Agent's `/status`** (`code_agent.py:1349` / the `execution_status` interface already in `haijunbot.py`) until `execution_status` returns to an idle/completed state, then return the result.
- **Result callback**: after the Agent completes its stage task, it returns the artifact path / structured result via `/message` or a dedicated callback interface; the orchestration engine validates the artifact from this and proceeds to the next batch.
- **Timeout**: the polling has a timeout (configurable by default); on timeout, error out and keep the scene intact.

> Note: `/message` currently only works for **standby agents without a task** (`haijunbot.py:1527-1558` injects into the input stream); resident hjb Agents are exactly this kind of standby agent, so the `wait` mechanism aligns naturally with the resident Agent plan.

## A.6 Conditional Branching (`when`)

`when` references upstream stage results with **simple expressions**; the node executes only if satisfied, otherwise it is skipped (marked skipped; its downstream is treated as "dependencies satisfied").

```yaml
- stage: "verify_e2e"
  agent: "df_validator_e2e"
  depends_on: ["verify_unit"]
  when: "verify_unit.status == 'completed' && verify_unit.pass_rate >= 0.9"
```

**Expression scope (conservative)**: only supports reading the upstream stage's **structured results** (read from status_file or artifact JSON), such as `status`, `pass_rate`, `exit_code`. **No arbitrary code evaluation** (security consideration; avoids injection). Use a restricted expression parser (e.g. `asteval` or a hand-written whitelist parser), not `eval()`.

## A.7 Failure Policy (`on_error`)

Each stage can declare its behavior on failure:

| Value             | Behavior                                                        |
| ----------------- | --------------------------------------------------------------- |
| `abort` (default) | abort the whole pipeline (same as today)                        |
| `continue`        | mark as failed, but continue executing nodes that do not depend on it |
| `skip_dependents` | mark as failed, and skip all downstream nodes that depend on it |

A global default `default_on_error` can be set; stage-level can override.

## A.8 Retry (`retry`)

Each stage can declare `retry: N`; on failure, automatically re-run the stage up to N times; if retries are exhausted and it still fails, handle per `on_error`. Each retry re-assembles the task-file and clears the old status_file.

## A.9 Compatibility (key constraints)

- **`flow` remains optional**: without flow, `@OrganizeAgents` behaves unchanged.
- **Old orchestration files need zero changes**: `depends_on` defaults to the previous stage; single-string `input` is also accepted (auto-converted to a single-element list). The existing linear flow of `dark_factory_pipeline.yaml` needs no changes.
- **All new fields are optional**: `when`/`retry`/`on_error`/`worktree` default to current behavior when absent.
- **`send_to_agent` backward compatible**: the new synchronous wait is an **optional parameter / new operation**; existing async calls are unaffected.
- **Linear orchestration still works**: without a parallelism need, `depends_on` defaults to the previous stage, equivalent to today's linear flow.

## A.10 Scope of Changes

| File                                                                   | Changes                                                                                   |
| ---------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `src/haijunbot/haijunbot_tools/pipeline_runner.py`                           | core: graph building / topological sort / resident Agent creation and scheduling / conditions / failure policies / retry. About +250~350 lines |
| `src/haijunbot/haijunbot_tools/gateway_manager.py`                           | add synchronous wait capability to `send_to_agent` (`wait` parameter, or a new `send_to_agent_sync` operation) |
| `src/haijunbot/haijunbot_agent/haijunbot.py` / `code_agent.py`                  | if needed: supplement `/message` or `/status` with "task complete + result callback" semantics |
| `builtin/plugins/ai-dark-factory/orchestration/dark_factory_pipeline.yaml` | add DAG usage notes to comments (optional; add a parallel example to the template) |
| `docs/design/ai-dark-factory-orchestration-engine.md`                  | this document (this appendix)                                                             |
| `tests/haijunbot_tools/test_pipeline_runner.py`                           | add DAG tests: topological sort, parallelism, multi-input, conditions, failure policies, cycle detection, lock handling |

**Unchanged**: `@OrganizeAgents`, `status_file`, config.yaml (no new entries needed).

## A.11 Risks and Countermeasures

| Risk                                        | Countermeasure                                                       |
| ------------------------------------------- | -------------------------------------------------------------------- |
| a cycle causing an infinite loop            | detect during topological sort up front; error out without executing if cyclic |
| **parallel execution under the same repo blocked by the file lock** | **uniformly use hjb to avoid it** (hjb has no repository lock; `haijunbot.py` has no `_acquire_single_instance_lock`); no worktree needed |
| **synchronous wait timeout / hang**         | `wait=true` polls `/status` with a timeout (configurable by default); on timeout, error out and keep the scene intact |
| parallel stage resource contention (multiple Agents running at once) | configurable `max_workers` (default 4), avoiding overwhelming the machine |
| parallel stages writing the same artifact path | convention: each stage has an independent output file; the engine validates output uniqueness |
| `when` expression injection                  | restricted expression parser; whitelist; no eval of arbitrary code   |
| gate semantics ambiguous under parallelism  | gate nodes remain single nodes; they execute only after all their dependencies complete, then stop and wait for approval |
| resident Agent creation failure / unavailable | validate before launch and retry creation; on failure, handle per `on_error` |
| increased complexity                        | keep the "single agent per stage" constraint; a DAG only solves scheduling; it does not introduce multi-agent single stages |

## A.12 Implementation Steps (after review passes)

1. ✅ **Add a `wait` parameter to `send_to_agent`** (`gateway_manager.py`): with `wait=true`, wait for completion and return the result. The actual implementation uses **`status_file` as the completion signal** (poll the local status file: completed -> success, failed -> failure, timeout 1800s), and keeps `/status` polling as the fallback. `wait` defaults to `false`, backward compatible.
2. ✅ Refactor `execute()`: split out `_build_dag()` (parse + validate + topological sort), `_create_stage_agents()` (create resident hjb Agents), `_run_stage()` (send_to_agent send + wait synchronous wait + artifact check), and `_schedule()` (parallel scheduling loop).
3. ✅ Implement the `when` restricted-expression parsing, `on_error` failure policies, and `retry`; additionally add top-level `default_on_error` and `output` global-uniqueness validation.
4. ✅ **The orchestration system ignores the `type` field of flow stages** (administrator decision 2026-10-08): stage Agents are always created as `type: agent` -> `hjb`; the `type` in the orchestration file is not read or depended on.
5. ✅ Update the template YAML comments + the design doc (this appendix).
6. ✅ Add unit tests (mock `send_to_agent` + `status_file`, covering parallel / fan-in / conditions / failures / cycles / retry / gate / artifact JSON references / creation retry). All 43 cases pass in practice.
7. ⏳ Verification: unchanged behavior of old orchestration files is covered by unit tests; **real-environment end-to-end verification of the new DAG orchestration is deferred per the administrator's request**.

### A.12.1 Supplementary implementation notes (differences from the initial design)

- **`status_file` as the completion signal**: the resident hjb Agent writes back `status_file` after executing its stage task; the engine polls this file to determine completion, which is more direct and reliable than polling `/status` (`/status` is only a fallback).
- **`when` can reference artifact JSON**: in `_run_stage`, after the artifact lands, if `output` is a `.json` whose top level is a dict, read its fields and merge them into that stage's `result` (status_file fields take precedence), so downstream `when` can reference artifact content via `stage.field` (e.g. `report.pass_rate`).
- **Resident Agent creation failure retry**: `_create_agent_with_retry` retries up to 3 times with increasing intervals; a success without an `agent_id` is also treated as a failure to retry; when exhausted, return failure with the last error. Creation happens serially on the main thread; **it is not created inside the scheduling thread**.
- **Parallelism implementation**: `_schedule` uses `ThreadPoolExecutor(max_workers=4)` to concurrently run the `_run_stage` of the same ready batch; the thread only does "dispatch + wait" (I/O blocking), creating no Agents and doing no CPU computation.
- **dry-run preview (new `dry_run` parameter)**: since the orchestration file is dynamically generated per task, with `dry_run=true` only parse + validate + topological sort are performed, outputting the DAG that would be executed (stages/dependencies/parallel batches/artifacts/gate/when/retry/on_error); **no Agents are created and no tasks are dispatched**; used to validate the dynamically generated orchestration file before execution. Default `false`, backward compatible.