# Pipeline DAG Visualization + Runtime Progress Marking -- Design Proposal

> Status: proposal pending administrator confirmation before implementation
> Date: 2026-10-08
> Rollback point: `513f7167115c6bdb85137fb7c42a15f0d0a15899`
> Related: `docs/design/ai-dark-factory-orchestration-engine.md` (DAG orchestration engine), `src/haijunbot/haijunbot_tools/pipeline_runner.py`

## 0. Administrator Decisions (inputs to this proposal)

| ID | Decision      | Meaning |
| --- | ------------- | ------- |
| D1 | **Plan B**    | frontend draws its own SVG (not mermaid/d3-graphviz); highest controllability / aesthetics |
| D2 | **make it flashy** | visuals must be dazzling: glowing nodes, flowing edges, gradients, animations |
| D3 | **full-chain real time** | backend execution state is pushed to the frontend in real time, not a one-shot snapshot |
| Extra | distinguish multiple flows | the frontend may orchestrate several flows at once; it must be able to distinguish them |
| Extra | activity bar entry | add an "Orchestration View" entry in the left activity bar |

---

## 1. Current State Survey (verified facts)

### 1.1 Backend: pipeline_runner execution state

`src/haijunbot/haijunbot_tools/pipeline_runner.py` (1147 lines):

- `execute()` (:101): parse orchestration YAML -> `_build_dag` -> `_create_stage_agents` (serial creation of hjb resident Agents on the main thread, :424) -> `_schedule` (parallel scheduling via thread pool, :659).
- `_schedule` (:659) holds the single **authoritative state machine** `state: Dict[stage, "pending"|"running"|"completed"|"failed"|"skipped"]`, plus `results`, `gate_blocked_stage`, `gate_approval_path`.
- State transition points:
  - After `_create_stage_agents` succeeds, `agent_map[stage] = agent_id` (:452) -- **the stage <-> agent_id mapping is produced here**.
  - In `_schedule`, `state[stage] = "running"` (:757, before dispatch).
  - `_handle_stage_result` (:845): `completed` / `failed` / `pending` (retry rollback).
  - `skipped`: dependency failed (:695) or `when` not satisfied (:734).
  - Gate block (:795).
- Current progress is **only output to `stdout_lines`** (text); no structured events, no external push.

### 1.2 Backend: real-time WebSocket push channel (exists; reusable)

- `SessionOutputRouter` (`src/haijunbot/haijunbot_gateway/output_bridge.py:38`): `publish(message, session_id=None)`; `session_id=None` means **broadcast to all active connections** (:114). Thread-safe (`RLock`).
- Global router singleton: `haijunbot_web_gateway/app.py:297 _router`, assigned at :2158.
- **Existing precedent of the same kind**: `_on_agent_status_change` (app.py:518) directly calls `_router.publish({"type": "status_update", ...}, session_id=None)` to broadcast Agent status; `WebGateway.publish_editor_command` (:849) likewise broadcasts `editor_*` messages.
- Frontend `handleMessage` (`App.vue:15043`) dispatches by `message.type`; branches already exist for `status_update` (:15463), `editor_open_file` (:15525), `eval_js_request` (:15528), etc. -- **adding one more type is enough; no protocol-framework change needed**.
- Frontend main connection: `connect()` (App.vue:11092) establishes the main WebSocket; `handleMessage(message)` (:11187) handles all broadcast messages.

### 1.3 Frontend: activity bar and sidebar

- Activity bar: `WorkspacePanel.vue:21` (`.workspace-activity-bar`); each entry is a `.workspace-activity-button`, clicking emits `setSidebarView` view (e.g. :27).
- Sidebar content: starting at `App.vue:76`, rendered by branching on `workspaceSidebarView` (agents/files/search/manage/timers/plugins/...).
- Sidebar title: mapped by a ternary expression at `App.vue:79`.
- **Existing "overlay big map" precedent**: `TopologyOverlay.vue` (1027 lines, self-drawn SVG network topology) + `topology.js` (pure JS data model + layout, 335 lines, with `topology.test.mjs`). **This is the best reference template for D2 "self-drawn SVG"** (glow filters, gradients, edge animations, responsive scaling, Esc to close, hover tooltips).
- Frontend stack: Vue 3 + Vite; testing with vitest + `node --test` (`topology.test.mjs`).

### 1.4 Frontend: Agent status source

- `agentList` (App.vue:9280) + `agentStatuses` (Map: agent_id -> {execution_status}).
- `getStatusClass(agent)` (:11936): `agent.status==='stopped'` -> stopped; otherwise take the execution_status from `agentStatuses`; default running.
- `status_update` messages (:15463) update `agentStatuses` in real time.

**Conclusion**: D3 "full-chain real time" needs no new channel -- reuse `SessionOutputRouter.publish` (backend) + a new `handleMessage` branch (frontend).

---

## 2. Overall Design (Plan B)

```text
pipeline_runner (executing)               web_gateway                    frontend
  │ state machine state/results/gate       │                          │
  │--emit_pipeline_event()--> global event bus │                      │
  │        (thread-safe, pure data)        │                          │
  │                          <-- drain --- │ (background polling thread) │
  │                                       │--_router.publish(broadcast)--> │
  │                                       │   type=pipeline_event     │
  │                                       │                          │ handleMessage
  │                                       │                          │  new branch
  │                                       │                          ▼
  │                                       │                  pipelineStore (multi-flow Map)
  │                                       │                          │
  │                                       │                  OrchestrationView.vue
  │                                       │                  (activity bar entry + self-drawn SVG DAG)
```

**Three-layer decoupling**:

1. **Production layer** (pipeline_runner): at state-machine transition points, call `emit_pipeline_event(...)` to write structured events into the **global event bus**. pipeline_runner is unaware of WebSocket / the frontend.
2. **Bridge layer** (web_gateway): a background thread `drain()`s events from the event bus and broadcasts them via `_router.publish(..., session_id=None)`. With no frontend connection, events only linger in memory briefly (with an upper bound), never blocking execution.
3. **Consumption layer** (frontend): `handleMessage` gains a `pipeline_event` branch, writing into `pipelineStore` (grouped by `pipeline_id`, supporting multiple flows); `OrchestrationView.vue` renders it.

---

## 3. Backend Design

### 3.1 Added: pipeline event bus (`src/haijunbot/haijunbot_tools/pipeline_events.py`)

A small standalone module, avoiding mutual imports between pipeline_runner and web_gateway:

```python
# Thread-safe event queue (bounded, prevents memory growth when there is no consumer)
class PipelineEventBus:
    def emit(self, event: dict) -> None      # producer: called by pipeline_runner
    def drain(self) -> list[dict]            # consumer: called by the web_gateway background thread
    def has_events(self) -> bool

def get_event_bus() -> PipelineEventBus      # global singleton
```

- Uses `collections.deque(maxlen=N)` + `threading.Lock`; overflow at `maxlen` drops the oldest events (progress events can tolerate dropped frames; the final state is authoritative via `pipeline_done`).
- Pure in-memory, no IO, no external dependencies.

### 3.2 Changed: pipeline_runner emits events at state transition points

Add a private method `_emit(...)` (internally calls `get_event_bus().emit`) and instrument the following spots:

| Event             | Trigger point                                             | Key fields |
| ----------------- | --------------------------------------------------------- | ---------- |
| `pipeline_start`  | `execute()` after `_build_dag` succeeds (around :165)     | `pipeline_id`, `orchestration_file`, `working_dir`, `nodes` (stage/agent/depends_on/output/gate/when), `max_workers`, `approve` |
| `pipeline_agents` | after `_create_stage_agents` completes (around :185)      | `pipeline_id`, `agent_map` (stage -> agent_id) |
| `stage_update`    | at every `state[stage]` transition in `_schedule`         | `pipeline_id`, `stage`, `status`, `agent_id`, `output`, `error?`, `retry?`, `detail?` |
| `pipeline_done`   | before `_schedule` returns (various exits starting at :810) | `pipeline_id`, `success`, `final_status` (completed/failed/gate_blocked), `gate_stage?`, `approval_path?` |

**`pipeline_id` generation**: `f"{stem of orchestration_file}-{timestamp}-{short random}"`, unique and stable within a single `execute()`. Multi-flow distinction relies on it.

**Instrumentation principle**: only **append one emit line** at existing state-transition points; do not change the control flow, return values, or stdout text. `state`/`results` semantics unchanged -> the existing 48 unit tests are unaffected (emit is a pure side effect; tests do not consume the bus).

### 3.3 Changed: web_gateway bridge thread

`src/haijunbot/haijunbot_web_gateway/app.py`:

- Add `_pipeline_event_pump()`: `while True: drain -> for e in events: _router.publish({"type":"pipeline_event","payload":e}, session_id=None); sleep(0.2)`.
- Start it in the `create_app` startup lifespan via `asyncio.to_thread` (or `threading.Thread(daemon=True)`), and set a stop flag on shutdown.
- Reuse the global `_router` (:2158). **With no frontend connection, `publish` returns directly** (`output_bridge.py:105`), and the events are dropped -- consistent with the "real-time" semantics (no history replay).
- If concerned about backlog when there is no connection: clear the queue after drain regardless of whether subscribers exist (current implementation already does this).

**Why polling rather than a direct callback**: pipeline_runner runs in a **separate thread/subprocess** (inside the Agent triggered by send_to_agent), which is not in the same context as the gateway's asyncio event loop; polling the bus is the simplest, decoupled cross-thread bridge. A 0.2s delay satisfies the "real-time" feel.

### 3.4 Correct handling of concurrent multi-flow

- Each `pipeline_runner.execute()` generates an independent `pipeline_id`; events carry that id.
- The frontend `pipelineStore` maintains state per `pipeline_id` key, never overwriting each other.
- Running the same `orchestration_file` twice concurrently -> two `pipeline_id`s; the frontend shows two independent flows (a "same orchestration file" group label can be added).

---

## 4. Frontend Design

### 4.1 Data layer: `src/stores/pipelineStore.js` (new)

Pure JS (easy to unit test with `node --test`; follow the `topology.js` style):

```js
// Internally: Map<pipeline_id, PipelineState>
// PipelineState = {
//   id, orchestrationFile, specFile, workingDir, startedAt, finishedAt,
//   maxWorkers, approve, status,               // running|completed|failed|gate_blocked
//   nodes: [{ stage, agent, dependsOn[], output, gate, when, agentId, status, error }],
//   gateStage, approvalPath, lastSeq
// }

export function createPipelineStore()
  - applyEvent(store, event)      // merge by type; auto-create for unknown pipeline_id
  - listPipelines(store)          // return as array (descending by startedAt)
  - getPipeline(store, id)
  - pruneFinished(store, max=20)  // keep the most recent N finished flows; prevent memory growth
```

- Event merge rules:
  - `pipeline_start` -> create the entry + initialize nodes (status=pending).
  - `pipeline_agents` -> backfill each node's `agentId`.
  - `stage_update` -> update the corresponding node's status/error/retry.
  - `pipeline_done` -> set the entry's final state.
- **Idempotent**: duplicate events overwrite by `stage`; no duplicate nodes appended.

### 4.2 View: `src/components/OrchestrationView.vue` (new, the "flashy" self-drawn SVG view)

Follow the SVG techniques of `TopologyOverlay.vue` (`<defs>` glow filters / gradients, `viewBox` self-adaptation, hover highlight, Esc to close).

**Layout algorithm**: DAG layering (topological level = longest-path depth).

- Extract a pure function `layoutDag(nodes) -> {width, height, positions: {stage: {x,y}}, edges: [{from,to}]}` into `src/components/dagLayout.js`, with `dagLayout.test.mjs` (testable via `node --test`).
- Layering: `level(node) = 0 if no dependencies else 1 + max(level(deps))`; within the same level, arrange vertically in declaration order; spread horizontally between levels.
- Edges: Bezier curves (`<path d="M... C...">`).

**Node visuals (D2 flashy)**:

- Rounded-rectangle cards containing stage name + agent name + status badge.
- Status color scheme (reuse the TopologyOverlay palette style):
  - `pending` gray (`#8a9bb0`)
  - `running` cyan-blue + **breathing glow** (`<animate>` or CSS `@keyframes`; `feGaussianBlur` filter pulsing)
  - `completed` green (`#34d99b`) + a checkmark
  - `failed` red (`#ff5d6c`) + an X
  - `skipped` semi-transparent gray + dashed border
  - `gate` gate node: gold border (`#f0b429`) + shield icon; blinks while blocked
- Edge visuals:
  - Completed edges: solid green + **flowing light dots** (`stroke-dasharray` + `animate` offset).
  - In-progress edges: cyan flowing.
  - Not started: static gray.
- Top stats cards (reuse the `.topo-stats` style of TopologyOverlay): per-status node counts, elapsed time, parallelism.
- Multi-flow: a top tab bar (orchestration file name + short id); click to switch. **The default tab shows the most recent flow.** (Admin confirmed: Tab switching)
- Top stats cards (reuse the `.topo-stats` style of TopologyOverlay): per-status node counts, elapsed time, parallelism.

**Interaction**:

- Hover a node -> tooltip (agent_id, output path, error).
- Click a node -> **jump to that Agent's chat panel** (admin confirmed: jump). Reuse the existing `onWorkspaceSidebarAgentClick`-style logic; if there is no agent_id (not created / skipped), show details only.
- Finished flows can be collapsed/closed (`pruneFinished`).

### 4.3 Entry: add "Orchestration View" to the activity bar (both forms)

Admin confirmed: **sidebar-embedded + overlay big map** -- both are needed, sharing the same render component.

- **Shared component**: `OrchestrationView.vue` only renders "the DAG + tabs + stats for a given pipelineStore"; it receives `pipelines`/`activeId` via props and reports interaction events (switch tab, click node) via emit. Both containers reuse the same component.
- **Form A: sidebar-embedded** (activity bar entry)
  - `WorkspacePanel.vue`: add a `.workspace-activity-button` to the activity bar (icon: a flow/DAG graphic, self-drawn SVG), `@click="$emit('setSidebarView', 'orchestration')"`, title "Orchestration View".
  - `App.vue`: sidebar title mapping (:79) adds `orchestration` -> "Orchestration View"; the sidebar content branch (starting at :76) adds `v-else-if="workspaceSidebarView === 'orchestration'"`, rendering `OrchestrationView` (compact mode).
- **Form B: overlay big map**
  - New `OrchestrationOverlay.vue` (follow TopologyOverlay.vue's overlay structure: mask + panel + Esc to close + `visible` prop / `update:visible` / `close` emit); internally reuses `OrchestrationView` (big map mode).
  - Entry: add a "⤢ big map" button at the top of the sidebar-embedded view (`$emit` to `App.vue` to open the overlay); the overlay can conversely "open in sidebar".
  - `App.vue` adds a `showOrchestrationOverlay` ref + `openOrchestrationOverlay()` / `closeOrchestrationOverlay()` (following `showTopologyOverlay`, :11030/:9604).
- `App.vue` common changes:
  - `handleMessage` (:15043) adds an `else if (type === 'pipeline_event')` branch -> `pipelineStore.applyEvent`.
  - Import `pipelineStore`, `OrchestrationView`, `OrchestrationOverlay`.

### 4.4 Aesthetics and responsiveness

- SVG `viewBox` + `preserveAspectRatio`, adapting to the sidebar width.
- Glow effects look best under the dark theme (consistent with the existing TopologyOverlay).
- Animations use CSS `@keyframes` (breathing/flowing) to avoid JS timer overhead.

---

## 5. Change List (estimate)

| File | Type | Description |
| --- | --- | --- |
| `src/haijunbot/haijunbot_tools/pipeline_events.py` | new | event bus (~60 lines) |
| `src/haijunbot/haijunbot_tools/pipeline_runner.py` | modified | add `_emit` + 5 types of instrumentation (~40 lines, pure additions) |
| `src/haijunbot/haijunbot_web_gateway/app.py` | modified | bridge thread + lifespan start/stop (~40 lines) |
| `src/haijunbot/haijunbot_service/frontend/src/stores/pipelineStore.js` | new | multi-flow state merge (~120 lines) |
| `src/haijunbot/haijunbot_service/frontend/src/components/dagLayout.js` | new | DAG layered-layout pure function (~100 lines) |
| `src/haijunbot/haijunbot_service/frontend/src/components/OrchestrationView.vue` | new | self-drawn SVG view (~400 lines; shared by sidebar/overlay) |
| `src/haijunbot/haijunbot_service/frontend/src/components/OrchestrationOverlay.vue` | new | overlay big-map container (~120 lines; modeled on TopologyOverlay) |
| `src/haijunbot/haijunbot_service/frontend/src/components/WorkspacePanel.vue` | modified | activity bar entry button (~12 lines) |
| `src/haijunbot/haijunbot_service/frontend/src/App.vue` | modified | title mapping + sidebar branch + overlay mount + `handleMessage` branch + imports (~50 lines) |
| tests | new | `test_pipeline_events.py`, `test_pipeline_runner.py` instrumentation assertions, `pipelineStore.test.mjs`, `dagLayout.test.mjs` |

---

## 6. Compatibility and Constraints

- **Backward compatibility**: pipeline_runner's return value, stdout, and state-machine semantics are unchanged; emit is a pure side effect. The existing 48 pipeline_runner unit tests + 77 related tests are unaffected.
- **No frontend connection**: events are dropped; no backlog, no execution blocking.
- **Multi-flow**: isolated via `pipeline_id`.
- **Minimal changes**: the WebSocket protocol framework is unchanged (only one message type added); the Agent state machine is unchanged; the flow YAML format is unchanged.
- **No eval introduced**: the frontend never evals backend data; events are pure JSON data.
- **Security**: events contain only stage/agent_id/path/status, no secrets; broadcasting goes over the existing authenticated connection.

---

## 7. Verification Plan

1. **Backend unit tests**:
   - `test_pipeline_events.py`: emit/drain/overflow-drop/thread safety.
   - `test_pipeline_runner.py`: mock the bus; assert the start/agents/stage_update/done event sequence is consistent with stage statuses.
2. **Frontend unit tests** (`node --test`):
   - `pipelineStore.test.mjs`: multi-flow isolation, event-merge idempotency, final states, prune.
   - `dagLayout.test.mjs`: correct layering, single node without dependencies, multiple dependencies, cycles (defensive).
3. **Build**: `npm run build` passes; `ruff check` / `ty check` pass.
4. **End-to-end (optional; the admin has indicated real-environment verification can be skipped)**: `pipeline_runner dry_run` produces no events; during a real run the frontend shows nodes transitioning in real time from pending -> running -> completed.

---

## 8. Decisions Confirmed by the Administrator (2026-10-08)

1. **Entry form**: sidebar-embedded + overlay big map **both are required** (sharing `OrchestrationView`).
2. **Multi-flow display**: top **Tab switching**.
3. **Node click behavior**: **jump** to the corresponding Agent chat panel (show details only when there is no agent_id).
4. **Event retention**: the frontend keeps the most recent **20** finished flows.

> The proposal is finalized and can move to implementation.