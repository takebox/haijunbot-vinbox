# Control everything, schedule everything — Complete Implementation Plan

> Status: Plan finalized, awaiting milestone-based execution
> Goal: advance HaijunBot from "can control the local system + basic scheduling" to the complete form of "control everything, schedule everything"
> Principle: evolve incrementally on the existing three-layer architecture (frontend control layer / gateway orchestration layer / local daemon layer), without rebuilding from scratch

---

## 1. Goal Definition

**Control everything**: let the system perform operations on anything on the user's machine — system, processes, apps, windows, input, files, services, browser, network, peripherals, power — and be able to **orchestrate multi-step operation sequences** (RPA-style automation).

**Schedule everything**: let any of the above operations be automatically triggered **by time, by event, or by condition** — supporting cron expressions, one-shot/recurring, dependency-triggered, failure retries, and result feedback.

In one sentence: **any capability can be orchestrated; any orchestration can be scheduled.**

---

## 2. Architecture Overview (current state)

```text
┌─────────────────────────────────────────────────────────────┐
│  Frontend control layer (frontend/ Vue)                     │
│  - Space-sequence shortcuts + Ctrl dual track · command palette · modal focus management │
└───────────────────────────┬─────────────────────────────────┘
                            │ HTTPS (hjb-ai.cn)
┌───────────────────────────▼─────────────────────────────────┐
│  Gateway orchestration layer (haijunbot_web_gateway/ Python)    │
│  - Agent lifecycle · node management · groups/chat · scheduled tasks (TimerManager) │
│  - daemon session management (capability.list / capability.call)          │
└───────────────────────────┬─────────────────────────────────┘
                            │ WS (haijunbot-daemon subprotocol)
┌───────────────────────────▼─────────────────────────────────┐
│  Local daemon layer (daemon/ Go, user machine)               │
│  - 35-capability registry · DispatchWith(action,params) dispatch          │
│  - Windows/Linux platform capabilities · zero third-party dependencies  │
└─────────────────────────────────────────────────────────────┘
```

**Key chains** (already working and verified):

- Frontend → gateway → daemon: the instruction `{action, params}` is executed via `DispatchWith` by the capability registry (`daemon/internal/handler/dispatch.go`)
- Gateway → daemon: the two HTTP APIs `capability.list` / `capability.call`
- Gateway → scheduling: `TimerManager` (`timer_manager.py`) + `/api/timers`, supporting `run_at` / `delay_seconds` / `interval_seconds`, with action types `create_agent` / `run_shell_command`

---

## 3. Current State Inventory (based on code facts)

### 3.1 Local daemon layer capabilities (daemon, 35)

| Domain      | Capability                                          | Win | Lin |
| ----------- | --------------------------------------------------- | :-: | :-: |
| system      | `system.info`                                       | ✅  | ✅  |
| process     | `process.list` / `process.kill`                     | ✅  | ✅  |
| app         | `app.list` (installed apps)                         | ✅  | ❌  |
| gui         | `window.list` / `window.focus` / `window.close`     | ✅  | ❌  |
| input       | `input.click` / `input.type` / `input.keys`         | ✅  | ❌  |
| clipboard   | `clipboard.get` / `clipboard.set` / `screenshot`    | ✅  | ❌  |
| script      | `script.exec`                                       | ✅  | ✅  |
| fs          | `fs.read` / `fs.write`                              | ✅  | ✅  |
| service     | `service.list`                                      | ✅  | ❌  |
| transfer    | `fs.transfer.push` / `fs.transfer.pull`             | ✅  | ✅  |
| browser_ext | `browser.ext.status` / `browser.ext.sync`           | ✅  | ✅  |
| ocr         | `ocr.recognize`                                     | ✅  | ✅  |

### 3.2 Gateway orchestration layer

- Agent: create / send / list / delete / regenerate
- Nodes: list / restart / update code
- Groups/chat: create_group / send_group_message / direct messages
- Scheduling: `create_timer` / `list_timers` / `get_timer` / `delete_timer` (only 2 action types)

### 3.3 Frontend control layer

- Space-sequence shortcuts (Space p/a/v/n/m) + Ctrl dual track, command palette with 30 actions
- Modal focus management, keyboard-only operation
- **No scheduled-task management UI**

---

## 4. Gap Analysis

| Dimension                            | Current State              | Target           | Completion |
| ------------------------------------ | -------------------------- | ---------------- | :--------: |
| Control - local system               | 35 capabilities (Win 20 / Lin 4) | Whole system |    ~40%    |
| Control - browser/web page           | Extension + eval_js        | Whole web page   |    ~60%    |
| Control - multi-step automation      | No RPA/recording/macros    | Operation sequences |   ~10%  |
| Scheduling - timer engine            | run_at/delay/interval      | Full cron        |    ~50%    |
| Scheduling - action types            | 2 (agent/command)          | Any capability   |    ~30%    |
| Scheduling - event-driven            | None                       | File/system events |   ~5%    |
| Scheduling - intelligent loop        | None                       | Feedback/retry/alerts |   ~20% |
| Orchestration - visualization        | No scheduling UI           | Visual panel     |    ~10%    |

**Overall completion: about 40%.**

---

## 5. Phased Implementation Roadmap

Ordered by "return on investment" and "dependency relationships", divided into 6 milestones (M1–M6). Each phase is independently verifiable and reversible.

---

### M1: Scheduled tasks → any daemon capability (opening the lifeline of "schedule everything")

**Goal**: expand the action types of scheduled tasks from 2 to calling any daemon capability.
**Benefit**: immediately gain real capabilities such as "open a certain window at 9 AM every day / scheduled screenshots / scheduled process cleanup / scheduled file sync".

**Change points**:

1. `src/haijunbot/haijunbot_web_gateway/app.py`
   - Add a branch for `action.type == "capability_call"` in `_build_timer_action`
   - Add `_build_capability_call_callback(action_params)`: inputs `node_id` / `capability` / `params`; the callback dispatches the instruction through the existing daemon `capability.call` HTTP API
2. `src/haijunbot/haijunbot_tools/gateway_manager.py`
   - Add `capability_call` to the `timer_action_type` enum in `_create_timer`
   - Supplement the `timer_action_params` description in the tool schema with the `capability` / `params` fields
3. `daemon/` needs no change (`DispatchWith` can already execute any registered capability)

**Verification criteria**:

- Add a `capability_call` scheduled task, set `run_at` 5 seconds later, targeting `windows.screenshot`; when it fires, the daemon returns the screenshot result
- The full chain of `list_timers` / `get_timer` / `delete_timer` works normally
- node tests + vitest + build all green

---

### M2: cron expression support (real scheduling needs)

**Goal**: support cron semantics such as "every Monday at 9:00" and "every day at 18:30", replacing hand-calculated `run_at`/`interval`.

**Change points**:

1. `src/haijunbot/haijunbot_web_gateway/timer_manager.py`
   - Add `cron_expr: Optional[str]` to `TimerTask`
   - Add `schedule_cron(cron_expr, ...)`; use a lightweight cron parser (`croniter` or a self-implemented 5-field parser, preferring self-implementation to avoid new dependencies)
   - In `_wait_for_next_task` / `_execute_task`, handle the next-trigger-time calculation for cron tasks
2. Add a `cron` branch to `_parse_timer_schedule` in `app.py`
3. Add `schedule.cron` to the `gateway_manager.py` schema

**Verification criteria**:

- Create a `cron: "0 9 * * 1"` task and assert `run_at` is calculated as the next Monday at 9:00
- Recurring cron tasks correctly advance to the next trigger point after firing
- The cron semantics are unchanged after persistence/restart recovery

---

### M3: Frontend visual scheduling panel (making scheduling "visible and manageable")

**Goal**: create/view/start-stop/delete scheduled tasks in the UI, rather than only by command.

**Change points**:

1. Add the component `src/haijunbot/haijunbot_service/frontend/src/components/TimerPanel.vue`
   - List: task ID / action type / schedule / next trigger time / latest result / start-stop
   - Create: choose the action type (create_agent / run_shell_command / capability_call) + fill in parameters + choose the schedule (cron / run_at / interval)
   - Operations: start-stop / delete / run once immediately
2. `App.vue`: add an entry (can be attached to the Manage domain `Space m t`); the modal is integrated into the focus-trap/restore system
3. Reuse the gateway `/api/timers` + `/api/timers/{id}` endpoints; if the "run immediately/start-stop" endpoints are missing, add them

**Verification criteria**:

- The panel can list, create, and delete scheduled tasks
- Modal auto-focus + Tab trap + focus restoration work normally
- A newly created `capability_call` task is visible and operable on the panel
- node + vitest + build all green

---

### M4: RPA operation sequences (the true form of Control everything)

**Goal**: record/orchestrate multi-step GUI operation sequences and replay them (click here → type → click there → screenshot verification).

**Change points**:

1. Add `windows_automation_windows.go` under `daemon/internal/capability/`
   - `automation.record`: listen for mouse/keyboard events and generate a step sequence (based on `SetWindowsHookEx`)
   - `automation.replay`: execute the sequence step by step (reusing the existing `input.click` / `input.type` / `input.keys` primitives)
   - `automation.sequence`: directly accept and execute a JSON step array (no recording needed; can be generated by an Agent)
   - Step types: click / type / keys / wait / screenshot / focus / run_script
2. Register the above capabilities in `registry_windows.go`
3. Optional on the gateway side: `capability_call` scheduled tasks can directly schedule `automation.sequence`

**Verification criteria**:

- Record a sequence that opens Notepad and types text; after replaying, the window content is correct
- `automation.sequence` accepts JSON steps and executes them one by one, with a failing middle step locatable
- Scheduled tasks can schedule `automation.sequence`

---

### M5: Event-driven scheduling (file/system event triggers)

**Goal**: support event triggers such as "when a file changes" and "when a process starts", rather than only time triggers.

**Change points**:

1. Add `windows_events_windows.go` under `daemon/internal/capability/` (or a cross-platform `fs_watch`)
   - `fs.watch`: listen for directory changes based on `ReadDirectoryChangesW` (Win) / inotify (Linux), reporting back to the gateway via callback
   - Event types: file created/modified/deleted/renamed, process started/exited (optional)
2. Gateway `TimerManager` or a new `EventManager`: receive daemon event reports → match registered "event → action" rules → trigger the action (reusing M1's capability_call chain)
3. Add `create_event_rule` / `list_event_rules` / `delete_event_rule` to `gateway_manager.py`

**Verification criteria**:

- Watch a directory; after a file is created, a `capability_call` is triggered automatically (such as a screenshot)
- Event rules can be listed/deleted and recover after a restart

---

### M6: Intelligent closed loop (plan-execute-feedback-retry-alert)

**Goal**: give scheduled tasks result validation, failure retry, and success/failure alerts, forming an automated closed loop.

**Change points**:

1. In `timer_manager.py` / the timer callback, add:
   - `retry` configuration (retry count, interval, exponential backoff)
   - `on_success` / `on_failure` hooks (can point to a notification Agent / group message / another task)
   - Result persistence (success/failure/duration/output summary)
2. The frontend `TimerPanel` shows the execution history and next-retry information
3. Optional: natural language scheduling ("remind me every morning" → parsed into cron + a notification action)

**Verification criteria**:

- A task configured with retry retries with backoff after failure and stops on success
- After failure, an alert is sent to the group per `on_failure`
- The execution history is visible on the panel

---

## 6. Dependencies and Order

```text
M1 (schedule → capability)   ← the foundation of all scheduling, do it first
M2 (cron)                    ← depends on M1's action framework
M3 (visual panel)            ← depends on M1/M2 interfaces
M4 (RPA sequences)           ← independent, can run in parallel with M2/M3
M5 (event-driven)            ← depends on M1's action chain + daemon event reporting
M6 (intelligent closed loop) ← depends on M1/M3
```

**Suggested execution order**: M1 → M2 → M3 → M4 → M5 → M6 (M4 can progress in parallel with M2/M3).

---

## 7. Risks and Cautions

1. **Minimal changes**: each phase is committed and verified independently, keeping it reversible at any time (current safe rollback point `7c043685efd88da3c4f80bad1935ff18fa8b01b8`).
2. **Zero third-party dependencies**: on the daemon side, stick to pure syscall + PowerShell without introducing cgo/external tools; prefer self-implementing cron parsing.
3. **Security**: `capability_call` scheduled tasks involve executing operations on the user's machine, so parameters must be validated to avoid privilege escalation; pay attention to privacy boundaries for event listening.
4. **Do not break the existing shortcut/focus system**: the modal added in M3 must be integrated into the focus trap/restore and must not introduce new key combinations.
5. **Testing discipline**: each phase has clear verification criteria (node + vitest + build all green); never use `npx jest`.

---

## 8. Completion Tracking

| Milestone                    | Status | Verification          |
| ---------------------------- | :----: | --------------------- |
| M1 schedule → capability     |   ⬜   | node + vitest + build |
| M2 cron support              |   ⬜   | node + vitest + build |
| M3 visual panel              |   ⬜   | node + vitest + build |
| M4 RPA sequences             |   ⬜   | node + vitest + build |
| M5 event-driven              |   ⬜   | node + vitest + build |
| M6 intelligent closed loop   |   ⬜   | node + vitest + build |

After completing M1–M6, the overall completion of "Control everything, schedule everything" is expected to go from **40% → 85%+**.