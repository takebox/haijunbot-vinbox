# AI Dark Factory Plugin Optimization Plan: Align with the Latest Orchestration Engine + Complete the Development Pipeline

> Status: **Reviewed, in implementation**
> Goal: make the dark factory plugin (`builtin/plugins/ai-dark-factory/`) fully leverage the latest `pipeline_runner` orchestration engine capabilities and fill in the weak links of the development pipeline.
> Basis: a cross-analysis of the plugin's current state (rules/tools/orchestration template/config) and the latest `pipeline_runner` capabilities.
> Related: `docs/design/ai-dark-factory-orchestration-engine.md` (orchestration engine design), `docs/design/orchestration-python-dsl.md` (.flow DSL).

---

## 0. Background

The dark factory plugin has been wired into the `pipeline_runner` orchestration engine, and the four-layer pipeline (planner → generator → validator → orchestrator gate) is headed in the right direction. However, since the plugin was designed, the orchestration engine has gained several new capabilities (the loop runtime iteration primitive, DAG parallelism, when conditional branching, retry/on_error, spec top-level field injection, and enhanced gate approval), while the plugin's **orchestration template** and **rules documentation** still stay at the engine's most basic linear capabilities.

At the same time, examining the whole development pipeline reveals several **completeness gaps**: no holdout scenario generation step, weak isolation mechanisms, the validator's multiple sampling not using engine primitives, and no place to persist gate history metrics.

This plan has two parts:

- **A. Capability alignment**: make the orchestration template and rules documentation demonstrate and use the latest engine capabilities.
- **B. Pipeline completion**: fill in the weak links of the development pipeline.

---

## 1. Current State Review

### 1.1 Plugin Composition

| Category       | File                                 | Purpose                                                                                                |
|---|---|---|
| Config         | `config.yaml`                        | Plugin metadata, rule/tool load directories, orchestration entry, three replace_map entry points (run/issue/pr) |
| Rule           | `rules/spec_writing.md`              | NLSpec four-element writing specification                                                              |
| Rule           | `rules/tdd_iron_rule.md`             | TDD iron rule (do not write code without a failing test)                                                  |
| Rule           | `rules/holdout_discipline.md`        | Acceptance scenario isolation discipline                                                                |
| Rule           | `rules/orchestration.md`             | Orchestration discipline (sw-controller, four-layer architecture, human approval gateway)               |
| Tool           | `tools/spec_validator.py`            | Validate whether an NLSpec contains the four elements                                                   |
| Tool           | `tools/holdout_generator.py`         | Generate holdout scenarios (invisible to the coding side)                                              |
| Tool           | `tools/gate_calculator.py`           | Compute gate metrics (pass rate / false positive rate / human override rate)                            |
| Orchestration  | `orchestration/dark_factory_pipeline.yaml` | Four-layer pipeline reference template (agents + flow)                                                  |

### 1.2 Development Pipeline (current state)

```text
Requirement input (Issue/PR/run)
  → ① NLSpec writing (spec_writing rule + spec_validator tool)
  → ② Dynamic generation of the orchestration file (agents + flow, user confirms)
  → ③ pipeline_runner drives the four-layer pipeline
        planner → generator(TDD) → validator → orchestrator(gate)
  → ④ Gate calculation (gate_calculator) → human approval
  → ⑤ Delivery/merge
```

### 1.3 Latest Orchestration Engine Capabilities (`pipeline_runner`)

| Capability                             | Description                                                                                                                             |
|---|---|
| **loop runtime iteration primitive**   | `loop(name, body, until, max_iterations)`: body is a subgraph of already-declared stages; the whole segment reruns until `until` is satisfied or the cap is reached; `until` supports the whitelisted functions `file(path)` (reads the artifact text in work_dir) and `contains(text, substr)` |
| **DAG parallelism**                    | `depends_on` explicitly declares dependencies; `input` supports multiple-input lists; `max_workers` defaults to 4-way parallel |
| **when conditional branching**         | `stage.field` references upstream status_file/artifact JSON fields, supporting `== != >= <= > < && \|\| !` |
| **retry / on_error**                   | `retry` failed retry count; `on_error: abort/continue/skip_dependents` failure strategies; top-level `default_on_error` |
| **spec top-level field injection**     | The top-level `spec` field of the orchestration file is injected as background into each stage (optional) |
| **Enhanced gate approval**             | `gate: true` stops the pipeline; the frontend approval overlay does approve/reject/retry; the backend `record_approval` audits |
| **Preview**                            | The frontend "Preview" button does not execute, it only draws a static DAG |

---

## 2. Pipeline Completeness Gaps (review conclusions)

| ID  | Gap                                    | Current State                                                                                                                               | Impact                                                                                                     |
|---|---|---|---|
| **G1** | Missing holdout generation step       | In the orchestration template, the validator claims to "hold holdout scenarios", but **no step in the pipeline calls `holdout_generator` to generate scenarios**, and no holdout artifact path is defined | The "hidden scenarios" for isolated evaluation actually have no reliable source, and the validator has no scenarios to test |
| **G2** | Weak holdout isolation mechanism      | The generator and validator share the `.df/` artifact directory, with no mechanism ensuring the holdout files are not seen by the generator | Violates holdout_discipline's rule that "the coding agent never sees the acceptance scenarios"            |
| **G3** | Validator's multiple sampling does not use engine primitives | holdout_discipline requires "run each scenario 3 times, passing 2-of-3", but it relies on the validator agent implementing it on its own | Unreliable and unobservable; the engine already has a loop primitive to express it                        |
| **G4** | No persistence for gate history metrics | `gate_calculator` needs `false_positives`/`human_overrides`/`total_human_reviews` (accumulated across tasks), and there is no place in the pipeline to persist this history data | The false positive rate / human override rate metrics cannot be truly computed, so the gate decision basis is incomplete |
| **G5** | No regression verification step       | holdout_generator has a "compatibility with existing modules" template, but the pipeline has no explicit stage that runs the existing test suite to prevent regressions | Changes may introduce regressions with no check                                                            |
| **G6** | No spec→holdout consistency check     | holdout should stem from the spec, but no step ensures they are consistent                                                                | The holdout may diverge from the spec, distorting the evaluation                                           |
| **G7** | The orchestration template does not demonstrate the latest engine capabilities | The template only uses a linear flow, not demonstrating loop/DAG/when/retry                                                               | The agent that dynamically generates orchestration files does not know the engine's capability boundaries and cannot produce better orchestration |

---

## 3. Plan

### 3.1 Part A: Capability alignment (G7)

#### A1. Add capability examples and descriptions to the orchestration template

In `orchestration/dark_factory_pipeline.yaml`:

- Keep the four-layer linear pipeline as the **default reference** (backward compatible, still directly runnable).
- In the comment area, add descriptions of loop/DAG/when/retry capabilities with **copyable examples** (such as expressing the validator's 3 sampling runs with loop).
- Explicitly mark that "orchestration files are generated dynamically; the template only demonstrates the format and capabilities".

#### A2. Add engine capability descriptions to the orchestration.md rule

In `rules/orchestration.md`, add a new section "Orchestration Engine Capability List" listing the semantics and use cases of loop/DAG parallelism/when/retry/on_error, so the agent that dynamically generates orchestration files knows the available primitives.

### 3.2 Part B: Pipeline completion (G1–G6)

#### B1. Complete the holdout generation step (G1 + G2 + G6)

In the template's flow, insert a **`holdout` stage** after planner and before generator:

- This stage is executed by an **independent agent** (`df_holdout`), whose responsibility: read the NLSpec, use the `holdout_generator` tool to generate hidden acceptance scenarios, and write them to `.df/holdout.json`.
- **Isolation**: `.df/holdout.json` is only an input for validator and **is not injected into generator**; generator's input is only `.df/plan.md`.
- **Consistency**: the task description of the holdout stage requires that "scenarios must stem from the spec's Goal/Interfaces, corresponding one by one", and this agent guarantees consistency.

> Note: `holdout_generator` is currently a templated generator (cycling through 8 fixed templates), producing **scenario skeletons**. The holdout agent must refine them against the spec on this basis to produce acceptance scenarios truly targeted at the feature. This plan does not change the tool itself (keeping changes minimal); instead it guarantees quality through agent responsibilities and rule constraints.

#### B2. Express the validator's multiple sampling with the loop primitive (G3)

In the orchestration template, express the validator with loop:

```yaml
flow:
  - stage: "holdout"
    agent: "df_holdout"
    input: ".df/plan.md"
    output: ".df/holdout.json"     # invisible to the coding side, passed only to validator
  - stage: "validator"
    agent: "df_validator"
    input: ".df/holdout.json"      # consumes only holdout, not plan (isolation)
    output: ".df/report.json"
    retry: 2                        # retry on failure, working with the 2-of-3 semantics
```

> Note: the loop primitive suits "rerun the whole segment until until is satisfied", while "run each scenario 3 times, taking 2-of-3" is **within-scenario** multiple sampling, which semantically is better executed inside the validator agent per holdout_discipline + backed up by `retry`. This plan uses `retry` to express retries and clarifies in the rules that 2-of-3 is implemented inside the validator. **The loop is not force-fitted** (to avoid a semantic mismatch).

#### B3. Persist gate history metrics (G4)

In the pipeline, designate a **cross-task metrics ledger** file (such as `.df/gate_metrics.json`):

- The orchestrator stage reads the history ledger and passes the accumulated `false_positives`/`human_overrides`/`total_human_reviews` to `gate_calculator`.
- After human approval, append this round's results back to the ledger.
- In the orchestration.md rule, document the ledger's location and fields.

> Note: this item is a **pipeline convention** (executed by the agent per the rules); the engine and tool code are not changed, keeping changes minimal.

#### B4. Complete the regression verification step (G5)

In the template's flow, insert a **`regression` stage** after validator and before orchestrator:

- Responsibility: run the existing test suite (such as `pytest`/the project test command) to confirm no regressions.
- Artifact: `.df/regression.json` (pass/fail).
- When this stage fails, `on_error: abort` (regression failure immediately aborts and hands off to a human).

#### B5. Update the rules documentation

- `orchestration.md`: add descriptions of the holdout generation step, isolation conventions, gate ledger, and regression step.
- `holdout_discipline.md`: add the concrete implementation method of "generated by an independent holdout agent, written to `.df/holdout.json`, passed only to validator".

### 3.3 Clean up leftovers

The `builtin/plugins-ext/ai-dark-factory/` directory **contains only a `__pycache__` leftover, with no actual files**, and nothing in the repository references it (plugins are only loaded from `builtin/plugins/` and `data_dir/plugins/`). **Delete the leftover directory**.

---

## 4. Implementation Steps

1. **Clean up leftovers**: delete `builtin/plugins-ext/ai-dark-factory/`.
2. **Orchestration template**: update `orchestration/dark_factory_pipeline.yaml`, adding the holdout/regression stages and completing the capability-description comments.
3. **Rules documentation**: update `orchestration.md` and `holdout_discipline.md`.
4. **Verification**: run `tests/haijunbot_plugins/test_ai_dark_factory.py`; use `pipeline_runner`'s dry-run to validate the new orchestration template parses (no cycles, valid agent references, unique artifacts).

---

## 5. Risks and Trade-offs

| Risk                                                                   | Mitigation                                                                                    |
|---|---|
| Changing the orchestration template breaks existing usability          | Keep the original four-layer pipeline as the core; new stages are optional references; dry-run validation |
| holdout_generator is a templated generator with limited quality        | Refine through the holdout agent's responsibilities + rule constraints; do not change the tool (minimal changes) |
| The new stages increase pipeline runtime                              | The holdout/regression stages are lightweight; they can be skipped with a `when` condition    |
| The gate ledger is a pipeline convention, agents may not follow it     | Clearly required in the rules documentation; tool support may be considered later (not this round) |

---

## 6. What Is Not Done (explicit boundary)

- **Do not change the `pipeline_runner` engine code**: the engine's capabilities are sufficient; this plan only aligns on the plugin side.
- **Do not change the code of the three tools (spec_validator/holdout_generator/gate_calculator)**: keep changes minimal, implementing through rules and pipeline conventions.
- **Do not introduce an external orchestration framework**: consistent with the conclusion of `docs/research/agent-tech-report-2026q3.md`, the self-developed engine direction is correct.

---

## 7. Verification Criteria

1. `builtin/plugins-ext/ai-dark-factory/` is deleted.
2. `dark_factory_pipeline.yaml` contains the holdout/regression stages, and `pipeline_runner` dry-run parsing passes (no cycles, valid agent references, unique artifacts).
3. `orchestration.md`/`holdout_discipline.md` have added the new step descriptions.
4. `tests/haijunbot_plugins/test_ai_dark_factory.py` all pass.