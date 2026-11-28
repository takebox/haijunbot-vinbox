---
name: orchestration
description: The orchestration discipline for the AI Agent dark factory. Triggered when a multi-Agent pipeline (planner/generator/validator/orchestrator) needs to be orchestrated. Requires that sw-controller only coordinates and does not execute, that the four-layer architecture is clear, and that a human approval checkpoint is retained at the gate.
---

# Orchestration Discipline

## Core Principles

Dark factory orchestration follows the **sw-controller pattern**: the master control agent **only coordinates, it does not execute**. The orchestrator is the nervous system of the pipeline, responsible for dispatching generators, dispatching validators, and executing gates, rather than writing code or testing itself.

Key insight: **design the orchestration logic first, then focus on the individual agents**. A strong generator agent paired with a weak orchestrator will perform poorly; a simple generator agent paired with a well-designed orchestrator will instead win out.

## Four-Layer Architecture

```text
┌─────────────────────────────────────────────────┐
│  Orchestrator — the nervous system of the pipeline │
│  Read spec → dispatch generator → dispatch validator → gate │
├─────────────────────────────────────────────────┤
│  Planner — decompose tasks, generate a plan        │
├─────────────────────────────────────────────────┤
│  Holdout (scenario generator) — generate hidden acceptance scenarios │
├─────────────────────────────────────────────────┤
│  Generators — write code from the spec             │
├─────────────────────────────────────────────────┤
│  Validators — run holdout, evaluate the output     │
├─────────────────────────────────────────────────┤
│  Regression — run existing tests to prevent regressions │
└─────────────────────────────────────────────────┘
```

## Orchestration Discipline

1. **Coordinate, don't execute**: the master control agent does not write code or test personally; it is only responsible for scheduling and gating.
2. **Single responsibility**: the planner only plans, holdout only generates scenarios, the generator only generates, the validator only evaluates, and regression only runs regressions; they do not cross boundaries.
3. **Stage progression**: advance strictly in the order planning → scenario generation → generation → validation → regression → gate; do not skip stages.
4. **Context injection**: each agent has its responsibility description injected via the `task` field, and its methodology injected via the rules system.

## Human Approval Checkpoint (Not Fully Unattended)

This plugin adopts a "not fully unattended" design; the key differences from a pure dark factory (fully automatic auto-merge):

1. **Fully automatic segment**: from the spec to the generator writing code and the validator running holdout scenarios, the whole process is AI-autonomous and can run unattended.
2. **Human approval checkpoint**: after the validator produces the pass/fail report, the **orchestrator does not merge automatically**; instead it outputs a structured approval report (per-scenario pass rates, failed scenario details, change diff summary) for human approval.
3. **After approval passes**: once the human confirms, it proceeds to the delivery/merge stage.
4. **Gate criteria**: only recommend passing when the scenario pass rate is ≥90%; only consider relaxing to automatic when the false positive rate is <5% and the human override rate is <10%.

This preserves the dark factory's efficiency of "humans only review the pass/fail report, not line-by-line code" while controlling the trust boundary through the human approval checkpoint, avoiding the risk of losing control with pure unattended operation.

## Orchestration File: A Dynamically Generated Structured Plan

The orchestration file (containing `agents` and `flow`) is a **structured plan dynamically generated for each task**, jointly produced by the orchestration agent based on the spec, the current state of the codebase, and discussions with the user, and executed only after the user confirms. The plugin's bundled `orchestration/dark_factory_pipeline.yaml` serves only as a **reference template** (demonstrating the four-layer architecture and flow format) and is not used directly for each task.

Key points for generating the orchestration file:

1. **agents**: define the role descriptions (`task`) for planner / holdout / generator / validator / regression / orchestrator according to the architecture.
2. **flow**: declare the stage order and artifact contracts (`stage`/`agent`/`input`/`output`/`gate`).
3. **Adapt to the existing codebase**: the generator stage has **no separate code directory artifact**—it directly modifies the existing code in `working_dir` (the existing codebase); the validator validates the modified working directory.
4. **Gate**: set `gate: true` in the orchestrator stage to pause and wait for human approval.
5. After generation, write it to `.df/pipeline.yaml`, and **execute only after the user confirms it is correct**.

### Holdout Scenario Generation and Isolation

- **Generation stage**: in the flow, set a **`holdout` stage** after the planner and before the generator, where an independent agent (`df_holdout`) reads the NLSpec, uses the `holdout_generator` tool to generate scenario skeletons, refines them into acceptance scenarios based on the spec's Goal/Interfaces, and writes `.df/holdout.json` to disk (marked `hidden=true`).
- **Isolation**: `.df/holdout.json` is **only used as the validator's `input` and is never injected into the generator** (the generator's `input` is only `.df/plan.md`). This is a hard requirement of holdout_discipline.
- **Consistency**: scenarios must originate from the spec—each scenario corresponds to a Goal or Interface contract in the spec.

### Regression Validation Stage

- In the flow, set a **`regression` stage** after the validator and before the orchestrator, where an independent agent (`df_regression`) runs the project's existing test suite, producing `.df/regression.json`.
- This stage uses `on_error: abort`: if regression fails, abort and hand it to a human.

### Gate Historical Metrics Ledger

- The `gate_calculator`'s false positive rate/human override rate need to be **accumulated across tasks**. The agreed ledger file is `.df/gate_metrics.json`:
  - The orchestrator stage reads the ledger and passes the accumulated `false_positives`/`human_overrides`/`total_human_reviews` together with the current results to `gate_calculator`.
  - After human approval, append the current results back to the ledger.
- When the ledger does not exist, treat it as the first task (all values are 0).

## Orchestration Engine Capability List (pipeline_runner)

When dynamically generating an orchestration file, the following engine capabilities may be used (all fields are optional; defaults produce linear behavior):

| Capability | Field/Syntax | Use Case |
|---|---|---|
| Linear/DAG | `depends_on` (default = previous stage); `input` supports a multi-input list | Stage dependencies, parallel branches |
| Parallel | Top-level `max_workers` (default 4) | Running multiple independent stages (e.g. multiple generators) in parallel |
| Conditional branching | `when` (`stage.field` comparison/logic, `== != >= <= > < && \|\| !`) | Skip/execute a stage based on upstream results |
| Retry on failure | `retry` (integer) | Fallback for jittery stages |
| Failure strategy | `on_error: abort/continue/skip_dependents`; top-level `default_on_error` | Control failure propagation |
| Gate | `gate: true` | Human approval checkpoint |
| Background injection | Top-level `spec` field | Inject spec background into all stages |
| Runtime loop | `loop(name, body, until, max_iterations)`: body is a subgraph composed of declared stages; the whole segment reruns until `until` is satisfied or the limit is reached; `until` supports `file("relative path")`, `contains(text, substr)` | "Rerun until it meets the standard" (e.g. a fix → re-verify loop) |

> Note: `loop` is suitable for "rerun the whole segment until it meets the standard", whereas holdout's "run each scenario 3 times and take 2-of-3" is **within-scenario** multiple sampling, performed internally by the validator agent according to holdout_discipline, with `retry` as a fallback; **do not force it into a loop**.

## Executing with the Built-in Orchestration Engine (pipeline_runner)

After the orchestration file is confirmed, use the built-in orchestration engine `pipeline_runner` tool to **automatically drive the four-layer pipeline in sequence**:

1. **Trigger**: the user enters `<dark-factory/run>`, or the main agent directly calls the `pipeline_runner` tool.
2. **Driving method**: `pipeline_runner` follows the `flow` order, launches the stage agents one by one with `hca -n --task-file`, polls `status_file` and synchronously waits for completion, and passes the artifacts to the next stage after verifying they are written to disk.
3. **Artifact contracts**: planner → `.df/plan.md` (implementation plan); holdout → `.df/holdout.json` (hidden acceptance scenarios, passed only to the validator); generator → **no separate code directory**, directly modifies the existing codebase (the artifact is the codebase changes, viewable via git diff); validator → `.df/report.json` (pass/fail report); regression → `.df/regression.json` (regression results); orchestrator → `.df/approval.md` (approval report).
4. **Gate pause**: after the orchestrator stage (`gate: true`) produces the approval report, the engine **pauses**, defaulting to `approve=false`, and only proceeds after human approval passes and the gate is rerun with `approve=true` for confirmation.

- The orchestration engine **coordinates but does not execute**: it does not write code or test, and is only responsible for sequential scheduling and artifact passing.
- `flow` is an optional field: when there is no `flow`, `@OrganizeAgents` still only creates agents (backward compatible).

## Common Pitfalls

- **Orchestrator overstepping into execution**: the master control writes code itself, losing dispatch discipline.
- **Confused responsibilities**: the generator also does validation, and evaluation loses its independence.
- **Skipping the gate**: delivering directly without evaluation, losing control of the trust boundary.
- **Premature full automation**: enabling automatic merging before accumulating enough evidence that the evaluator agrees with human judgment.
