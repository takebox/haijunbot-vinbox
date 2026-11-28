# Daemon System Info Reporting: Chain and Troubleshooting Guide

This document describes each link in the chain of **haijunbot-daemon reporting system information on registration**, and the method for locating problems
when end-to-end verification fails.

## 1. Chain Overview

```text
[daemon] capability.CollectSystemInfo()
   │  daemon/internal/capability/{linux_system_linux,system_windows,system_darwin}.go
   ▼
[daemon] hello frame {"type":"hello", ..., "system_info": {...}}
   │  daemon/internal/wsclient/client.go  connectAndServe()
   ▼  WS /api/daemon/ws (subprotocol haijunbot-daemon + haijunbot-token.<token>)
[gateway] handle_daemon_websocket() parses hello
   │  src/haijunbot/haijunbot_web_gateway/daemon_capability_manager.py
   ▼
[gateway] session persisted self._sessions[session_id]["system_info"]
   │
   ▼
[gateway] GET /api/daemon/sessions → {"success":true,"sessions":[{...,"system_info":{...}}]}
   │  src/haijunbot/haijunbot_web_gateway/app.py
   ▼
[Agent] daemon.list_sessions → JSON in stdout contains system_info
       src/haijunbot/haijunbot_tools/daemon.py
```

## 2. Checkpoints for Each Link

### Link A: daemon collects system info

- Code: `capability.CollectSystemInfo()`
- Platform implementation files:
  - Linux: `daemon/internal/capability/linux_system_linux.go` (12 fields)
  - Windows: `daemon/internal/capability/system_windows.go` (6 fields)
  - macOS: `daemon/internal/capability/system_darwin.go` (6 fields)
- **Verification method**: the daemon startup log should show

  ```text
  [wsclient] hello will report system_info: hostname=xxx fields=N
  ```

- **Failure symptoms**:
  - This line missing → the collection function returned an error; the log will contain
    `[wsclient] failed to collect system info; hello will not contain system_info: ...`
  - `fields=0` → the platform implementation returned an empty map (check whether the build tag matches the current GOOS)

### Link B: hello frame sending

- Code: `connectAndServe()` in `daemon/internal/wsclient/client.go`
- hello frame fields: `type` / `client_id` / `extension_version` / `tabs` / `system_info`
- **Note**: the daemon's hello **does not contain** `browser_info` (browser info is reported by the extension itself).
- **Verification method**: daemon log

  ```text
  [wsclient] connected http://.../api/daemon/ws (subprotocol [haijunbot-daemon haijunbot-token.xxx])
  ```

### Link C: gateway receives and persists

- Code: `handle_daemon_websocket()` in `daemon_capability_manager.py`
- **Verification method**: the gateway log should show

  ```text
  [DAEMON] session connected: session_id=... client_id=... node_id=... user_id=...
  [DAEMON] hello system_info: received=True hostname='xxx' platform='yyy' fields=N
  ```

- **Failure symptoms and meanings**:

  | Symptom                      | Meaning                                                                                  |
  | ------------------------- | ------------------------------------------------------------------------------------- |
  | No `session connected` line | WS not connected: invalid token, subprotocol mismatch, wrong endpoint                                         |
  | `received=False fields=0` | The gateway received hello but it has no `system_info` → the problem is in Link A/B (old daemon version or collection failure) |
  | `hostname=''`             | There is no `hostname` key in `system_info` → check the field names in the platform implementation                             |
  | `platform=''`             | `system_info` has neither `os_name` nor `platform`, and the old `browser_info` does not have them either          |

### Link D: HTTP API response

- Code: `/api/daemon/sessions` in `app.py`
- **Verification method**:

  ```bash
  curl -s http://127.0.0.1:<gateway port>/api/daemon/sessions \
    -H "Authorization: Bearer <token>" | python -m json.tool
  ```

- **Failure symptom**: the `session connected` log is present, but here `system_info` is `{}`
  → the problem is in the response layer (`list_sessions()` does not carry the field, or the session has been cleaned up by heartbeat timeout)

### Link E: Agent tool pass-through

- Code: the `list_sessions` branch in `src/haijunbot/haijunbot_tools/daemon.py`
- This branch passes the `sessions` list returned by the gateway to `_format_result()`,
  which uses `json.dumps` to **serialize as-is, without trimming fields**.
- **Failure symptom**: the curl in Link D can see `system_info`, but the Agent side cannot
  → check whether an old `daemon.py` is used (the old version has no such description but the logic already passes through),
  or the Agent is connected to another gateway (`master_url` mismatch).

## 3. Quick Troubleshooting Mnemonic

Look at three log/output points in order to pinpoint the problem to a specific link:

1. Does the **daemon log** have `hello will report system_info: ... fields=N`?
   - If not → the problem is in Link A/B (daemon side).
2. Does the **gateway log** have `hello system_info: received=True ... fields=N`?
   - If not → the problem is in the transmission/parsing of Link C (token, subprotocol, field names).
3. Does **curl `/api/daemon/sessions`** have `system_info`?
   - If not → the problem is in Link D (response layer).
   - If present but the Agent cannot see it → the problem is in Link E (wrong gateway or old code).

## 4. Known Limitations

- `client_id` contains the PID (`daemon-<hostname>-<pid>`), which changes on every daemon restart,
  so `node_id` (defaulting to `client_id`) is unstable. If a stable node identity is needed,
  refer to the extension's `getClientId()` approach to persist client_id (not done this round).
- The system info fields on Windows / macOS are fewer than on Linux (only hostname/os_name/arch/
  cpu_count/user/home), because no platform-specific libraries were introduced.
- No real end-to-end integration was done this round (the user explicitly requested to skip it); only unit tests cover
  the four segments: gateway parsing, persistence, response, and Agent pass-through.
