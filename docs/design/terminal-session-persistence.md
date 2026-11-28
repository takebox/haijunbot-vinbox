# HaijunBot Integrated Terminal Session Persistence Plan (Plan A)

## 1. Overview

### 1.1 Background and Goals

The Administrator raised a requirement: **the integrated terminal loses its session after the frontend page disconnects; the session should be preserved so that the same account can continue on the next login**, and it is also required to **support the same user logging in from multiple devices**.

Goals:

- After the frontend page disconnects (refresh / network loss / closing the tab), the terminal process is not killed and the session is preserved.
- After the same account logs in again (including switching devices), the previous terminal session can be restored and interaction continued.
- When multiple devices of the same user are online at the same time, they can all see the same terminal in real time without interfering with each other.

### 1.2 Design Principles

- **Minimal changes**: only change code relevant to the goal, do not refactor unrelated parts.
- **Decouple process from connection**: the terminal process lifecycle is decoupled from the frontend WebSocket connection — disconnecting does not kill the process.
- **Isolate by account**: session ownership is determined by the user (`session_id`), and it can only be restored by the same account.
- **Multi-device broadcast**: when multiple devices of the same account coexist, output is broadcast to all online devices; a reconnecting device only replays the buffer, without duplication.
- **Backward compatibility**: the existing terminal create / close / input / resize logic remains unchanged.

---

## 2. Current State Analysis

### 2.1 Core Files

- Backend: `src/haijunbot/haijunbot_web_gateway/terminal_session_manager.py` (601 lines)
- Backend: `src/haijunbot/haijunbot_web_gateway/app.py` (terminal-related: WS message handling, HTTP endpoints)
- Backend: `src/haijunbot/haijunbot_gateway/output_bridge.py` (`SessionOutputRouter` publish/subscribe)
- Frontend: `src/haijunbot/haijunbot_service/frontend/src/App.vue`, `components/TerminalPanel.vue`

### 2.2 Key Facts

1. **Sessions are memory-only**: `TerminalSessionManager._sessions` is an in-memory dictionary with no persistence. `cleanup()` is called when the app shuts down (lifespan shutdown), killing all sessions.

2. **Frontend disconnect does not kill the process**: the `finally` block of `WebSocketConnectionManager.handle` only does `router.unregister`, `input_registry.unregister_provider`, and chat client cleanup, and **does not close the terminal session**. The terminal process continues running after the WS disconnects.

3. **Output is dropped during disconnection**: terminal output is published via `router.publish(message, session_id=...)`. After the WS disconnects, that session has no subscribers, and `publish` in `output_bridge.py` drops the output directly due to `if not callbacks: return`.

4. **Sessions are already bound to users**: `session_id = f"session_{user_id}"` (app.py:967), passed in when creating a terminal (app.py:1389), stored in `TerminalSession.session_id`.

5. **Multiple coexisting devices are naturally supported**: `router._subscribers[session_id]` is a `{connection_id: sender}` dictionary that can hold multiple connections; `publish(session_id=...)` broadcasts to all connections under that session; a WS disconnect only removes that `connection_id` and does not affect other devices.

6. **Frontend sessions are pure memory**: `terminalSessions` (App.vue:7731) is cleared on refresh and does not rediscover sessions still alive on the backend.

### 2.3 Root Cause of the Problem

It is not "disconnect kills the process" (the process is still alive), but three gaps:

- **No output buffering**: output is dropped during disconnection and cannot be replayed after reconnecting.
- **No attach/reconnect mechanism**: the frontend cannot re-associate an existing session with a new connection.
- **Opaque session ownership**: `list_terminals()` returns all sessions and does not include `session_id`, so they cannot be filtered/isolated by account.

---

## 3. Plan A Design

### 3.1 Backend Changes

#### 3.1.1 Output Ring Buffer (`terminal_session_manager.py`)

- Add an output ring buffer to `TerminalSession` (`collections.deque(maxlen=N)`), retaining about 1MB of output by default (configurable).
- When `_publish_output` runs, it both publishes via `stream_publisher` and writes to the buffer.
- Provide a `get_output_buffer()` method that returns the buffer content (for replay on attach).

#### 3.1.2 Attach Capability (`terminal_session_manager.py`)

- Add `list_sessions_for_user(session_id)`: returns the metadata of live sessions belonging to the specified user (`session_id` match) (including `terminal_id`, `interpreter`, `working_dir`, `node_id`, `created_at`, `is_closed`).
- Add `attach_session(terminal_id, session_id)`: after validating session ownership, returns the session's buffer content for the frontend to replay. **Replay is per-connection**: each new connection gets the buffer when it attaches, and devices already online are not replayed again (controlled per connection by the frontend; the backend is only responsible for providing the buffer snapshot).

#### 3.1.3 Ownership Filtering and Field Exposure (`app.py`)

- `list_terminals` (HTTP GET `/api/terminals`) is changed to filter by the current user's `session_id`, returning only that user's own sessions and exposing the `session_id`, `node_id`, and `created_at` fields.
- Add an attach endpoint (HTTP or WS message): called by the frontend after login/reconnect to obtain the list of live sessions + buffer content.
- The attach endpoint reuses the `terminal:create` permission check and also validates session ownership (you can only attach your own sessions).

### 3.2 Frontend Changes (`App.vue`)

- After the WS reconnects successfully, call `list_terminals` (or the attach endpoint) to pull back the current user's live sessions.
- Add each live session to `terminalSessions`, call `initIndependentTerminal` to initialize xterm, and replay the buffer content.
- Multiple devices each replay independently, without duplication.
- Show a "restorable sessions" tab in the terminal panel, where the user can click to attach or close.

### 3.3 Multi-Device Semantics

| Scenario                   | Behavior                                              |
| -------------------------- | ----------------------------------------------------- |
| Devices A and B both online | Both receive terminal output in real time (existing capability, retained) |
| Device A disconnects       | Only A's subscription is removed, B keeps receiving   |
| Device A reconnects        | Only A is replayed the buffer, B is not duplicated    |
| Any device closes terminal | Broadcast `terminal_closed`, all devices remove the tab |

---

## 4. Limitations and Future Enhancements

### 4.1 Limitations (Plan A)

- The terminal process still runs inside the gateway process (PTY), so **sessions are still lost after a gateway restart / upgrade** (`cleanup()` kills all sessions on lifespan shutdown).
- The buffer has a limit; early output beyond the limit cannot be replayed.

### 4.2 Future Enhancements (Plan B)

- **Process decoupling (tmux/screen or a standalone daemon)**: decouple the terminal process from the gateway process so the gateway only acts as a proxy. Terminals survive a gateway restart and can be re-attached. This is a large change, introduces external dependencies, and makes multi-node / Windows support complex, with high risk; to be evaluated separately.

---

## 5. Verification Method

1. Backend syntax / import checks pass.
2. Run the terminal-related tests under `tests/haijunbot_web_gateway/` to confirm no regressions.
3. End-to-end verification:
   - Create a terminal → frontend disconnects → the backend process is still alive (visible via `list_terminals`).
   - Log in again → the session is automatically restored → output from the disconnection period is replayed → input can continue.
   - Two devices of the same account online at the same time → both receive output in real time; one disconnects and reconnects → the buffer is only replayed to that device, without duplication.
4. Permission checks: users without the `terminal:create` permission cannot create/attach; you can only attach your own sessions.

---

## 6. Change Log

- 2026-10-06: Plan A finalized and implementation started. Initial safe rollback commit: `98ff93532d6c2901dddfb862d9e39c71e97fc863`.
