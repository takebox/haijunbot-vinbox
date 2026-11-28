# Python Orchestration DSL (Layer 1: Structure Generation) Design Document

> Status: **implemented** (Layer 1: structure generation). Implementation lives in `src/haijunbot/haijunbot_tools/orchestration_dsl.py` and `src/haijunbot/haijunbot_tools/orchestration_loader.py`.
> Prior discussion: three proposals in `docs/research/` + the loop-orchestration discussion.
> Target readers: later implementers, reviewers.
>
> **Important terminology (explicitly confirmed with the user during implementation)**: the DSL script suffix is **`.flow`** (not `.py`). The two orchestration file semantics:
>
> - **`.yaml` / `.yml`** = **organization orchestration**: batch-create Agents, does not generate a `flow` (does not go through the pipeline).
> - **`.flow`** = **process orchestration**: executes the DSL script to generate a DAG, which goes through pipeline scheduling.
>
> Both count as "orchestration files"; the backend `load_orchestration` and `parse-orchestration` handle both generically, and the frontend gates interaction by suffix.
> Any `.py` mentioned in the history sections below refers to what is currently implemented as the `.flow` suffix (the original text is kept to record the design evolution).

---

## 1. Background and Goals

### 1.1 Current state (verified facts)

The orchestration file is currently **YAML** (`agents` definitions + optional `flow`), parsed by the `pipeline_runner` engine into a **DAG (directed acyclic graph)** and scheduled for execution.

- Engine: `src/haijunbot/haijunbot_tools/pipeline_runner.py`
  - `execute()` (:102) reads the file -> `yaml.safe_load` (:131) -> `_build_dag` (:354) -> `_schedule` (:857).
  - Supports: `depends_on` / `input` / `output` / `when` (restricted expressions, :1244) / `on_error` / `retry` / `gate` / `max_workers`.
  - Cycle detection: `_topo_sort` (:457); a cycle raises an error directly (:450).
- There are **3** parse entry points (duplicated implementations):
  1. `app.py:10444` `_handle_parse_orchestration_request` (master; frontend preview/form).
  2. `node_manager.py:1432` `_handle_parse_orchestration_request` (child; cross-node).
  3. `pipeline_runner.py:131` (at real execution time).
- 2 run entry points (only pass a file path): `app.py:10590` and `node_manager.py:1610`.
- Frontend: `App.vue` orchestration modal (`parseOrchestrationFile` :13221, `runOrchestration` :13366, `previewOrchestration` :13405); file filter allows only `.yaml/.yml` (`ORCHESTRATE_FILE_EXTENSIONS` :13066); `dagLayout.js` lays out by `dependsOn`.
- Artifacts: `.haijunbot/artifacts/<pipeline_id>/`, passing data across stages via `input`/`output` paths.

### 1.2 Pain points

YAML expression power has hit its ceiling. Restricted expressions like `when` (a whitelist; no eval) are the ceiling; they cannot express:

- **Dynamically generating** a set of stages from external data (e.g. fan-out per function in a C file).
- Reuse/composition (defining a group of stages as a reusable unit).
- Any structure that requires computation (generating N stages in a loop, choosing different sub-graphs by condition).

### 1.3 This proposal's goal (Layer 1: structure generation)

**Let users write orchestration in Python, but Python only "generates the DAG structure"; it does not participate in runtime scheduling.**

- After executing a Python orchestration file, the output is **a DAG data structure isomorphic to the current `_build_dag` output**.
- The execution engine, scheduling, events, frontend visualization, and cross-node distribution **all stay unchanged** (they still consume DAG data).
- Loops are **expanded at compile time** (the number of rounds/stages is decided at generation time), not runtime loops.
  - Runtime dynamic loops (e.g. C2Rust "compile failed, go back for another pass") are **out of scope for this proposal** and belong to Layer 2 (adding a `loop` primitive to the engine), tracked separately.

### 1.4 Non-goals (explicitly excluded)

- ❌ Runtime dynamic control flow (loop/while primitives, branching on runtime results).
- ❌ Side effects directly in the orchestration script such as `send_to_agent` (the script only declares structure; it does not execute).
- ❌ Breaking existing YAML orchestration: YAML must remain usable (coexists; is not replaced).

---

## 2. Core Design

### 2.1 Two-phase model: load (execute script) -> schedule (consume data)

```text
Orchestration file (.flow)  --execute-->  DAG data (pure structure)  -->  _schedule consumes (unchanged)
     │                        ▲
     └── import haijunbot.haijunbot_tools.orchestration_dsl (trusted library; constructors only, no side effects)
```

- **Load phase**: execute the `.flow` script; the script declares stages using the DSL constructors; when the script finishes, the `Pipeline` object holds the DAG data.
- **Schedule phase**: hand the DAG data to the existing `_schedule`; identical to the YAML path.

**Key invariant**: the DAG data structure produced by the DSL = the `nodes` structure of the existing `_build_dag` (fields: `stage/agent/depends_on/input/output/gate/when/retry/on_error`). This is the premise of "zero changes to the engine".

### 2.2 Trusted environment assumption

Explicitly confirmed by the user: **the runtime environment is a trusted environment**. Therefore:

- The orchestration `.flow` has the same trust level as HaijunBot's own code; **no sandbox is needed**.
- But one boundary remains: **the script only declares structure; it does not perform side effects** (no task dispatch, no artifact writes). This is for **previewability, cross-node support, and visualization**, not for security.

### 2.3 Preview semantics

Preview = **execute the DSL script to obtain the DAG structure, but do not create Agents or dispatch tasks**. This is exactly the semantics of the existing `dry_run` (`pipeline_runner.py:175`):

- YAML: `parse-orchestration` statically parses out `nodes` (`app.py:10547`).
- Python: execute the script -> take `Pipeline.nodes` -> the same `nodes` structure.
- The frontend behavior after receiving `nodes` is unchanged (`previewOrchestration` already consumes `nodes`).

### 2.4 Cross-node distribution

Recommended: **distribute the "executed DAG data", not the script itself**.

- Rationale: child nodes do not need to install the DSL library, execute the script, or share the script file; they just consume data.
- But the **run entry still passes a file path** (as it does today, `app.py:10590`). So there are two landing approaches:
  - **Approach 1 (recommended, minimal changes)**: child nodes also execute the script (requires the child node to have `haijunbot.haijunbot_tools.orchestration_dsl`; since HaijunBot code is distributed uniformly, this is naturally satisfied). The script path is reachable via a shared file system / same machine.
  - **Approach 2 (more thorough)**: after the master executes the script and obtains the DAG data, pass the **data** to the child nodes along with the `run-orchestration` request. This requires extending the request protocol (adding a `dag` field); child nodes skip parsing and use it directly.
- This proposal **defaults to Approach 1** (consistent with today, minimal changes); Approach 2 is an optional enhancement, decided based on the cross-node deployment shape.

---

## 3. DSL Design

### 3.1 Module location

Add `src/haijunbot/haijunbot_tools/orchestration_dsl.py` (same directory as `orchestration_loader.py`, so the unified loader can import it easily).

**Pure library, no side effects, no engine dependency**: it only provides constructors that accumulate declarations into DAG data.

### 3.2 Minimal API (implemented)

```python
from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage

p = Pipeline()                       # top-level container

# Declare stages (each corresponds to one flow item)
p.add(stage("planner", agent="demo_planner", output=".df/plan.md"))
p.add(stage("worker_a", agent="demo_worker_a",
            depends_on=["planner"], input=".df/plan.md", output=".df/a.md"))
p.add(stage("worker_b", agent="demo_worker_b",
            depends_on=["planner"], input=".df/plan.md", output=".df/b.md"))
p.add(stage("aggregator", agent="demo_aggregator",
            depends_on=["worker_a", "worker_b"],
            input=[".df/a.md", ".df/b.md"], output=".df/final.md"))

# agents definitions
p.agent("demo_planner", working_dir=".", task="You are a planner...")
# ...remaining agents

# Top-level optional
p.spec("Pipeline background...")
p.default_on_error("abort")

# After the script finishes, p.nodes / p.agents are the DAG data (consumed by the engine)
```

### 3.3 Expressing "arbitrary structure" with Python (the value of Layer 1)

```python
# Example: fan-out per function list (not possible in YAML)
funcs = [f.name for f in parse_c_functions("input.c")]   # arbitrary Python logic
for fn in funcs:
    p.add(stage(f"translate_{fn}", agent="translator", output=f"out/{fn}.rs"))
    p.add(stage(f"compile_{fn}", agent="builder",
                depends_on=[f"translate_{fn}"], input=f"out/{fn}.rs",
                output=f"build/{fn}.log"))

# Example: "loop" expanded at compile time (fixed number of rounds)
for i in range(3):
    p.add(stage(f"pass_{i}", agent="optimizer",
                depends_on=[f"pass_{i-1}"] if i else []))
```

### 3.4 Field mapping to YAML

DSL constructor arguments = the keys of the YAML `flow` items, one-to-one:

| DSL                                    | YAML flow key   | Description                                        |
| -------------------------------------- | --------------- | -------------------------------------------------- |
| `stage(name, agent=...)`               | `stage` / `agent` | required                                        |
| `depends_on=[...]`                     | `depends_on`    | default = previous stage (linear)                  |
| `input=...`                            | `input`         | string or list                                     |
| `output=...`                           | `output`        | globally unique                                    |
| `gate=True`                            | `gate`          | gate                                               |
| `when="a.b > 0"`                       | `when`          | restricted expression, semantics unchanged         |
| `retry=3`                              | `retry`         | per-stage retry                                    |
| `on_error="abort"`                     | `on_error`      | failure policy                                     |

The DSL is only **syntactic sugar** and introduces no new semantics -- guaranteeing zero changes to the engine/frontend.

---

## 4. Change Point List (implemented)

### 4.1 Added

| File | Content |
|---|---|
| `src/haijunbot/haijunbot_tools/orchestration_dsl.py` | DSL library: `Pipeline` / `stage` / `agent` and other constructors, producing DAG data |
| `src/haijunbot/haijunbot_tools/orchestration_loader.py` | **Unified loader** `load_orchestration(path) -> {agents, flow, spec, default_on_error}`: dispatches by suffix (`.yaml/.yml` -> `yaml.safe_load`; `.flow` -> execute the script and extract the structure). **Eliminates the 3 duplicated parse implementations** |
| `tests/haijunbot_tools/test_orchestration_dsl.py` | DSL unit tests: construction -> produced structure isomorphic to `_build_dag`; field mapping; error handling |

### 4.2 Modified

| File:line | Change |
|---|---|
| `pipeline_runner.py` | remove `import yaml`; change `yaml.safe_load` to call `load_orchestration(path)`; downstream logic unchanged |
| `app.py` `_handle_parse_orchestration_request` | change `yaml.safe_load` to `load_orchestration(path)` (import inside the try block), exceptions converted to `ORCHESTRATION_PARSE_ERROR`; `has_flow`/`nodes` logic unchanged |
| `node_manager.py` `_handle_parse_orchestration_request` | same as above (child side) |
| `App.vue` `ORCHESTRATE_FILE_EXTENSIONS` | add `.flow` (previously `.yaml/.yml`) |
| `App.vue` input placeholder | prompt "(.yaml/.yml=organization orchestration, .flow=process orchestration)" |
| `App.vue` `accept` | `accept=".yaml,.yml,.flow"` |
| `App.vue` `parseOrchestrationFile` | gate the `has_flow` determination by the `.flow` suffix |
| `pipeline_runner.py` tool `description` / parameter description | orchestration files support YAML / `.flow` DSL |

> Note: `import yaml` in `app.py` / `node_manager.py` still has other uses; it is retained.

### 4.3 Unchanged (important)

- `_build_dag` / `_topo_sort` / `_schedule` / `_run_stage` / `_eval_when`: **completely untouched** (they consume DAG data, regardless of origin).
- `pipeline_events.py`, the event protocol, `pipelineStore.js`, `OrchestrationView.vue`, `dagLayout.js`: **completely untouched**.
- Artifact directory, `pipeline_id` generation (`_make_pipeline_id` uses the file name stem; `.flow` applies the same way): untouched.

---

## 5. Loader Design (key)

```python
def load_orchestration(path: str) -> dict:
    """Load an orchestration file by suffix and return the unified structure {agents, flow, spec, default_on_error}.

    - .yaml/.yml: yaml.safe_load (current behavior)
    - .flow: execute the script; the script must define the top-level variable `pipeline` (a Pipeline instance),
             and return the structure it exports.
    """
    suffix = Path(path).suffix.lower()
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if suffix == ".flow":
        return _load_flow(path)
    raise ValueError(f"Unsupported orchestration file type: {suffix} (only .yaml/.yml/.flow are supported)")
```

The `_load_flow` contract (**the agreement**):

- After the script executes, the top-level variable `pipeline` (a `Pipeline` instance) must exist.
- Prefer calling `pipeline.to_dict()`; fall back to reading the attributes `agents`/`flow`/`spec_text`/`default_on_error`.
- The script **must not have side effects** (no task dispatch, no artifact writes); enforced by convention + documentation (trusted environment; no forcing, no sandbox).
- Execution method: `exec` the script in an **isolated namespace**, catch exceptions, and return a clear error.

**Error handling**: script syntax error / runtime error / missing `pipeline` variable -> raise `ValueError` (with clear messages); callers (`app.py` / `node_manager.py`) catch it and convert to `ORCHESTRATION_PARSE_ERROR`, isomorphic to the existing YAML parse failure, so the frontend prompt is consistent.

---

## 6. C2Rust Example (the part Layer 1 can express)

Layer 1 can express structures that are **"known at compile time"**, for example:

```python
# c2rust_pipeline.flow
from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage
from pathlib import Path

p = Pipeline()
p.spec("Translate C code into Rust: translate function by function, compiling and verifying each.")

# Arbitrary Python: scan the functions to translate
funcs = scan_functions("input.c")          # returns the list of function names

p.agent("translator", working_dir=".", task="Translate the given C functions into Rust...")
p.agent("builder",    working_dir=".", task="Compile the Rust code and output the compile log...")

for fn in funcs:
    p.add(stage(f"translate_{fn}", agent="translator", output=f"out/{fn}.rs"))
    p.add(stage(f"compile_{fn}", agent="builder",
                depends_on=[f"translate_{fn}"],
                input=f"out/{fn}.rs", output=f"build/{fn}.log"))

# Fixed-round retry at compile time (not a runtime loop)
for i in range(2):
    p.add(stage(f"retry_round_{i}", agent="builder",
                depends_on=[f"compile_{f}" for f in funcs] if i == 0
                           else [f"retry_round_{i-1}"]))
```

**What Layer 1 cannot express**: going back to `translate_{fn}` to retranslate **carrying the compile error** after `compile_{fn}` fails, with the **number of rounds depending on the compile result** -- this is a runtime loop and belongs to Layer 2.

> Note: Layer 1 already covers structures like "**translate each function independently + compile, at most a fixed number of rounds**", far stronger than YAML; only scenarios where "the number of rounds is only known at runtime" need Layer 2.

---

## 7. Confirmed Decisions (former open items)

1. **Module path**: use `haijunbot_tools/orchestration_dsl.py` (same directory as `orchestration_loader.py`, so the unified loader can import it easily).
2. **Script entry convention**: top-level variable name `pipeline` (a `Pipeline` instance).
3. **Unified loader**: **done** in this iteration; the 3 duplicated parse implementations converge into `load_orchestration`.
4. **Cross-node distribution**: use Approach 1 (child nodes execute the script); since HaijunBot code is distributed uniformly, this is naturally satisfied.
5. **Frontend template/generator**: **not done** in this iteration; only hand-written `.flow` is supported.
6. **Suffix**: `.flow` (not `.py`); `.yaml/.yml` keeps the organization-orchestration semantics.

---

## 8. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Script side effects (trusted but still possible to misuse) | accidentally executing tasks during preview | documentation strongly enforces "only declare, do not execute"; the DSL library exposes no side-effect APIs |
| Script execution failures hard to locate | poor UX | the loader catches exceptions and returns a traceback summary; the frontend prompts |
| 3 parse implementations drifting | inconsistent behavior | converge into the unified `load_orchestration` |
| Cross-node without shared storage | child nodes cannot access the script | reserve Approach 2 (pass DAG data), enable when needed |
| Users mistakenly think runtime loops are supported | unmet expectations | documentation clearly states the Layer 1 boundary; Layer 2 is tracked separately |

---

## 9. Verification Plan (after implementation)

1. **DSL unit tests**: `Pipeline` construction -> the produced structure matches the equivalent YAML's `_build_dag` result **field by field**. ✅ Implemented (`tests/haijunbot_tools/test_orchestration_dsl.py`, 18 cases all passing).
2. **Loader unit tests**: `.yaml` / `.flow` sources return isomorphic structures; error paths (syntax error / missing `pipeline` / unsupported suffix). ✅ Implemented.
3. **End-to-end**: rewrite `simple_demo.yaml` as an equivalent `.flow`; run dry-run and a real execution; results match. (pending)
4. **Frontend**: `.flow` files can be selected/parsed/previewed (`has_flow`/`nodes` work). ✅ Implemented (`vite build` passes).
5. **Regression**: all existing YAML orchestration cases unchanged; `pipeline_runner` existing unit tests all pass. ✅ Regressed (`ruff` + related `pytest` cases all pass).

---

## 10. Relationship to Layer 2

- Layer 1 is the **foundation** for Layer 2: the DSL library, the unified loader, and frontend `.flow` support are all reusable.
- Layer 2 (adding a `loop` primitive to the engine) is **tracked as a separate project** because it breaks the DAG acyclicity assumption and touches `_build_dag` / `_schedule` / the event protocol / `dagLayout.js`.
- After Layer 1 ships, if the "runtime loop" need is validated, Layer 2 can be started.

---

## 11. Layer 2: Runtime Loop Primitive (`loop`) -- implemented

> Status: **implemented**. Implementation lives in `src/haijunbot/haijunbot_tools/orchestration_dsl.py` (the `loop()` constructor),
> `src/haijunbot/haijunbot_tools/pipeline_runner.py` (`_fold_loops_into_dag` / `_run_loop` / `_eval_until`),
> and the frontend `pipelineStore.js` / `OrchestrationView.vue`.

### 11.1 Semantics

The DSL adds `loop(name, body, until, max_iterations=5, on_error=None)`:

- `name`: the loop node name (shares the namespace with stage names; must not conflict).
- `body`: the sub-graph formed by **already declared stage names** (string or list, non-empty).
- `until`: the loop termination condition expression (non-empty), **evaluated after all stages in the body finish for each round**.
- `max_iterations`: positive integer upper bound (default 5); if `until` is still not satisfied when the bound is reached, the loop is treated as
  `completed` (`until_satisfied=false`) rather than looping forever.
- `on_error`: behavior when a stage inside the body fails (default `abort`).

Key point: **body means "the whole segment re-runs"** (not per-stage retry). Each round executes the stages inside the body once in internal dependency order,
and each round uses an isolated status file (`{stage}.iter{N}.status`) to avoid interference from the previous round.

### 11.2 The `until` expression: reads artifact files

`until` reuses the existing `when` evaluation framework (`_substitute_refs` / `_eval_boolean` / `_eval_comparison`),
with two new **whitelisted functions** (no arbitrary code eval):

- `file(path)`: reads the body of an artifact file under `work_dir`.
  - **Out-of-bounds protection**: after `resolve`, the path must still be within `work_dir`, otherwise an error is raised.
  - **Size cap**: only reads the first 1MB (`open(...,'rb').read(max_bytes)`) to avoid exhausting memory.
  - Returns an empty string if the file does not exist.
- `contains(text, substr)`: substring matching; returns a boolean.

Example:

```python
loop(
    "fix_until_ok",
    body=["compile", "fix"],
    until='contains(file("build.log"), "BUILD SUCCESS")',
    max_iterations=5,
)
```

**Performance note**: `file()` is **lazy-evaluated** -- the file content is never concatenated into the expression string. This is required
because `_split_top_level` / `_find_top_level_op` are character-by-character Python loops; concatenating 1MB of text into the
expression would hang (it once made pytest hang for 90s+). Also `_substitute_refs` was changed to **skip content inside quotes**
to avoid incorrectly replacing the path in `file("report.md")`.

### 11.3 DAG folding and scheduling

- `_build_dag` first expands the loop items (validating unique names, non-empty body, non-empty until, `max_iterations >= 1`),
  then calls `_fold_loops_into_dag` to fold the body stages into a loop composite node:
  - `kind="loop"`, `body_stages`, `until`, `max_iterations`;
  - the loop node's `depends_on` = the union of the body's external dependencies;
  - top-level nodes that depend on body stages are rewritten to depend on the loop node;
  - inter-dependencies between body stages are allowed; stages depending on **other loops** raise an error.
- `_iter_agent_nodes`: expands into the nodes that need Agents (normal stages + loop body_stages),
  used by `_create_stage_agents`.
- `_schedule`: loop nodes go through `_run_loop`, normal nodes go through `_run_stage`; `agent_id` is taken via
  `agent_map.get(...)`.

### 11.4 Event protocol (backward compatible)

- New `loop_iteration` event: `{stage, iteration, max_iterations}`, broadcast at the start of each round.
- `stage_update` gains optional fields `loop` (the owning loop name) and `iteration` for body stages.
- `pipeline_start`'s `nodes` carry extra fields `kind` / `until` / `max_iterations` /
  `body_stages` on loop nodes (built by `_node_event_payload`); normal stage fields remain **unchanged**.

### 11.5 Frontend

- `pipelineStore.js`: `emptyStage` adds `kind/until/maxIterations/iteration/bodyStages`;
  handles the `loop_iteration` event to update the current round; when `stage_update` carries `loop`, updates the corresponding loop node.
- `OrchestrationView.vue`: loop nodes get an `is-loop` class (dashed border + purple accent),
  show 🔁 in the top-right corner, and display `iteration/maxIterations` on the right.

### 11.6 Boundaries and invariants

- **Existing orchestration without loops behaves completely unchanged** (for both YAML and `.flow`): `_build_dag`'s output fields for normal stages
  are unchanged; the scheduling path is unchanged; event fields are unchanged; frontend rendering is unchanged.
- `until` must remain **whitelisted**, no eval of arbitrary code; `file()` is forbidden from reading arbitrary files outside `work_dir`.
- A stage failing inside the body -> loop `failed` (handled per the loop's `on_error`).

### 11.7 Verification

- `pytest tests/haijunbot_tools/test_pipeline_runner.py tests/haijunbot_tools/test_orchestration_dsl.py tests/haijunbot_plugins/test_ai_dark_factory.py tests/haijunbot_web_gateway/test_pipeline_events_ingest.py` -> 161 passed.
- `ruff check` on the two files -> All checks passed.
- Frontend `node --test src/stores/pipelineStore.test.mjs` -> 18 passed; `vite build` succeeds; `eslint` on the changed files -> 0 errors.

---

## Appendix: Change Impact Quick Reference

```text
Added (Layer 1):
  orchestration_dsl.py        (DSL library)
  orchestration_loader.py     (unified loader)
  test_orchestration_dsl.py   (unit tests, 18 cases)

Modified (Layer 1):
  pipeline_runner.py          (switch to load_orchestration; tool description/parameter description)
  app.py                      (_handle_parse_orchestration_request switches to load_orchestration)
  node_manager.py             (same, child side)
  App.vue                     (support .flow suffix, placeholder, accept, has_flow gating)

Added/Modified (Layer 2 loop):
  orchestration_dsl.py        (loop() constructor + Pipeline.add support)
  pipeline_runner.py          (_fold_loops_into_dag / _iter_agent_nodes / _run_loop /
                               _eval_until / _eval_contains / _read_artifact_text /
                               _node_event_payload; _run_stage supports _status_suffix)
  pipelineStore.js            (loop fields + loop_iteration event)
  OrchestrationView.vue       (loop node rendering)
  test_orchestration_dsl.py   (TestLoop 10 cases)
  test_pipeline_runner.py     (TestBuildDagLoop 11 + TestLoop 6 + TestEvalUntil 7 cases)

Unchanged (Layer 2):
  _topo_sort's external behavior / existing YAML orchestration semantics / existing event fields
```