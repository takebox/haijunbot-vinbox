# Multi-Agent Orchestration: Driving Pipelines with pipeline_runner

## When to Use

When a task can be split into a multi-stage flow like "planning → execution → verification → aggregation" and the stages have dependencies, doing it serially with a single Agent is slow and messy. HaijunBot has a built-in **`pipeline_runner`** orchestration engine: you declare an orchestration file (containing `agents` definitions and an optional `flow` order), it builds a DAG according to `flow`, uses resident `hjb` Agents to schedule stages in parallel, waits synchronously for completion, validates artifacts, and passes the previous stage's artifacts to the next stage.

It follows the **sw-controller pattern**: it only coordinates and does not execute — the engine itself does not write code or test; what each stage does is declared by the `task` in the orchestration file.

## Prerequisites

- HaijunBot is installed and `hjb` can run (orchestration creates resident `hjb` Agents).
- You have a working directory (artifacts are written under its `.haijunbot/artifacts/`).
- An orchestration file (`.yaml` / `.yml` / `.flow`).

## Steps

### 1. Look at a minimal example

The repository ships `builtin/agent_orchestration/simple_demo.yaml`, demonstrating "fan-out → parallel → converge":

```text
           ┌─> worker_a ─┐
planner ───┤             ├─> aggregator
           └─> worker_b ─┘
```

Its `flow` section:

```yaml
flow:
  - stage: "planner"
    agent: "demo_planner"
    output: ".df/demo_plan.md"
  - stage: "worker_a"
    agent: "demo_worker_a"
    depends_on: ["planner"]
    input: ".df/demo_plan.md"
    output: ".df/demo_a.md"
  - stage: "worker_b"
    agent: "demo_worker_b"
    depends_on: ["planner"]
    input: ".df/demo_plan.md"
    output: ".df/demo_b.md"
  - stage: "aggregator"
    agent: "demo_aggregator"
    depends_on: ["worker_a", "worker_b"]
    input:
      - ".df/demo_a.md"
      - ".df/demo_b.md"
    output: ".df/demo_final.md"
```

Key point: `worker_a` and `worker_b` both depend only on `planner`, so they run **in parallel**; `aggregator` runs after both have completed.

### 2. Preview the plan first (without executing)

Before actually running, use `dry_run` to validate the orchestration file and see the DAG that will be executed (stages / dependencies / parallel batches / artifacts / gates / conditions / retries / failure policy), **without creating Agents or dispatching tasks**:

```text
pipeline_runner(
  orchestration_file="builtin/agent_orchestration/simple_demo.yaml",
  working_dir="/path/to/workdir",
  dry_run=true
)
```

In the Web interface, select a file in the orchestration dialog and click "Preview" to see the static DAG diagram.

### 3. Run the pipeline

```text
pipeline_runner(
  orchestration_file="builtin/agent_orchestration/simple_demo.yaml",
  working_dir="/path/to/workdir",
  max_workers=4
)
```

`max_workers` is the upper limit of parallelism (default 4), limiting the number of stage Agents executing at the same time.

In the Web interface, select an orchestration file and click "Run Pipeline" to see each stage's status and the DAG in real time in "Orchestration View".

### 4. Capability list of the orchestration file

Each item in `flow` is a stage and supports the following fields:

| Field | Description |
| --- | --- |
| `stage` | Stage name (unique; referenced by `depends_on` / `when`) |
| `agent` | References the `name` in `agents` |
| `input` | Upstream artifact path; a single string is automatically converted to a single-element list, and multiple inputs are written as a list |
| `output` | This stage's artifact path; non-empty and globally unique (duplicates cause an error) |
| `depends_on` | List of dependent stages; default = the previous stage (linear) |
| `when` | Restricted expression; the stage is skipped if it is not satisfied |
| `retry` | Number of retries on failure (integer, default 0) |
| `on_error` | Failure policy: `abort` (default) / `continue` / `skip_dependents` |
| `gate` | Gate: when `true`, `approve=false` will pause and wait for manual approval |

Optional top-level fields:

- `spec`: Injected as background for each stage (optional).
- `default_on_error`: Global default when a stage does not declare `on_error` (an invalid value falls back to `abort`).

#### `when` restricted expression

`when` uses **whitelist evaluation** (it does not eval arbitrary code) and supports:

- Referencing fields of an upstream stage: `stage.field` (taken from the upstream `status_file` and the artifact JSON content).
- Comparison: `==` `!=` `>=` `<=` `>` `<`.
- Logic: `&&` `||` `!`.
- Literals: number / string / boolean.

Example:

```yaml
- stage: "notify"
  agent: "notifier"
  depends_on: ["validator"]
  when: "validator.pass_rate >= 0.9"
```

#### `loop` runtime loop primitive

When you need to "rerun until it meets the bar" (such as a fix → re-verify loop), use `loop`:

```yaml
flow:
  - stage: "fix"
    agent: "fixer"
    output: ".df/report.json"
  - loop: "retry_until_pass"
    body: ["fix"]
    until: "contains(file(\".df/report.json\"), \"\\\"pass_rate\\\": 1.0\")"
    max_iterations: 3
```

- `body`: A subgraph composed of already-declared stages; the whole block is rerun.
- `until` whitelist functions: `file("relative artifact path")` (reads the artifact body within work_dir), `contains(text, substr)`.
- `max_iterations`: Upper limit; it stops when reached.

### 5. `gate` gate and manual approval

A stage with `gate: true` will **pause** after completing; by default `approve=false`, and it is released only after manual confirmation. This achieves "not fully unattended": fully automatic segments can be unattended, while key checkpoints retain manual approval.

In the Web interface's "Orchestration View", when a gate pauses, an approval overlay pops up offering three operations — **approve / reject / retry** — and you can fill in a note; the approval record is written to the log.

### 6. Two suffixes for orchestration files

| Suffix | Semantics |
| --- | --- |
| `.yaml` / `.yml` | **Organizational orchestration**: declares a group of Agents, used for batch creation; may include `flow` to run a pipeline |
| `.flow` | **Process orchestration**: declares the DAG structure with a Python DSL (the script only declares structure and produces no side effects), suitable for scenarios YAML cannot express, such as "dynamically generating stages from data" |

A `.flow` script is declared with DSL constructors; after execution it produces DAG data isomorphic to YAML, and the engine behaves exactly the same. Example:

```python
from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage

p = Pipeline()
p.add(stage("planner", agent="demo_planner", output=".df/plan.md"))
p.add(stage("worker_a", agent="demo_worker_a",
            depends_on=["planner"], input=".df/plan.md", output=".df/a.md"))
p.agent("demo_planner", working_dir=".", task="You are the planner...")
```

> For the detailed design, see `docs/design/orchestration-python-dsl.md`.

## Prompts and Feedback You Will See

- **Preview**: Static DAG diagram (each stage and its dependencies), no Agents created.
- **While running**: Each stage's status updates in real time (pending / running / done / failed / skipped), and you can see the parallel batches.
- **Gate paused**: An approval overlay appears; you need to choose approve / reject / retry.
- **Artifacts**: Each stage's artifacts are written to `.haijunbot/artifacts/<pipeline_id>/` under `working_dir` (in the example, `.df/` is just an example path).

## Notes

- The engine **only coordinates and does not execute**: what each stage does is determined by that stage Agent's `task`; the engine does not write code.
- The `output` path must be globally unique; duplicates cause an error.
- If `depends_on` is omitted it means "the previous stage" (linear); to parallelize you must explicitly declare dependencies.
- A `flow` with cycles is directly rejected by topological sorting and causes an error.
- Stage Agents are resident `hjb` Agents; after creation the engine waits for their gateway to be ready before dispatching tasks; a readiness timeout (about 60 seconds) causes an error.
- All example orchestration files can be run; paths are subject to the actual files in the repository (`builtin/agent_orchestration/`, `builtin/plugins/ai-dark-factory/orchestration/`).

## Next Steps

- Want to see a real multi-stage pipeline (with gates)? See `builtin/plugins/ai-dark-factory/orchestration/dark_factory_pipeline.yaml`.
- Want multiple Agents to message each other and collaborate (rather than orchestrating by DAG)? See [Best Practices for Collaboration Modes](Best_Practices_for_Collaboration_Modes.md).
