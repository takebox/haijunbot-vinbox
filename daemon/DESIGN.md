# HaijunBot Local Daemon (haijunbot-daemon) Design Proposal

> Status: Design finalized, pending implementation
> Scope: This round only wires up the chain "authenticate → connect to gateway → stay online → receive commands and return placeholder results"

## 1. Background and Goals

Write a local daemon in **Go**, running on the user's machine, **completely independent** of the browser extension (does not depend on the extension or the browser).

There is only one goal this round: **wire up the chain and communication**.

Specifically:

1. The web page (logged in) pushes login information (JWT + gateway address) to the local daemon;
2. The daemon uses a **dedicated endpoint** `/api/daemon/ws` (subprotocol `haijunbot-daemon`) to connect to the gateway, with handshake/heartbeat shape consistent with the browser extension;
3. Stay online: `hello` / `hello_ack` / heartbeat / reconnect on disconnect;
4. Can receive commands from the gateway and return a **placeholder result** (`not_implemented`).

Explicitly **out of scope this round**:

- Concrete business features (actual execution of commands);
- Daemon self-update;
- Browser extension update;
- Server-side update.

## 2. Overall Architecture

```text
┌──────────────┐  ①POST /api/auth {gateway,token}  ┌────────────────────┐
│ Web App.vue   │ ─────────────────────────────────▶│  Local daemon      │
│ (hjb-ai.cn)   │ ◀────────── /api/status ──────────│  127.0.0.1:17800   │
└──────────────┘                                    │  (Go, resident)    │
                                                    └─────────┬──────────┘
                                                              │ ②WS subprotocol
                                                              │ ["haijunbot-daemon",
                                                              │  "haijunbot-token.<jwt>"]
                                                              ▼
                                                    ┌────────────────────┐
                                                    │ Gateway /api/daemon/ws │
                                                    │  hello/hello_ack    │
                                                    │  ping/pong          │
                                                    │  capability.list    │
                                                    │  capability.call    │
                                                    └────────────────────┘
```

**Key design**: The daemon uses a handshake/heartbeat shape consistent with the browser extension, but goes through a **dedicated endpoint**,
the gateway side manages sessions via a separate `daemon_capability_manager`, independent of extension sessions.

Therefore:

- **Gateway side**: add the endpoint `/api/daemon/ws` (`app.py`) and session management `daemon_capability_manager.handle_daemon_websocket`, and provide three HTTP APIs `/api/daemon/sessions`, `/api/daemon/capability/list`, `/api/daemon/capability/call` for the Agent tool layer to call;
- **Web side minimal change**: only add one "Authenticate local process" entry point + one `fetch`, without touching existing logic.

## 3. Authentication Chain

### 3.1 Web page → daemon

The web page adds an entry (e.g., an "Authenticate local process" button in the settings panel); clicking it triggers:

```http
POST http://127.0.0.1:17800/api/auth
Content-Type: application/json

{
  "gateway": "https://hjb-ai.cn",
  "token": "<JWT>"
}
```

- `gateway`: taken on the web side from `window.__haijunbotAuthBridge.getGateway()` (near `App.vue:16661`), same logic as the extension;
- `token`: taken on the web side from `auth.value.token`, same source as the extension's `getToken()`.

After validating the input parameters, the daemon returns:

```json
{ "success": true, "status": "connecting", "daemon_version": "0.1.0" }
```

### 3.2 Daemon → gateway

The daemon uses the same handshake/heartbeat shape as the browser extension (see `browser_extension/background/ws_client.js:65-69`), but goes through a dedicated endpoint:

| Item       | Value                                                                                                                                             |
| -------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| URL      | `{ws_gateway}/api/daemon/ws`                                                                                                                      |
| Subprotocol   | `["haijunbot-daemon", "haijunbot-token." + urlencode(token)]`                                                                                           |
| First frame     | `{"type":"hello","client_id":...,"extension_version":...,"browser_info":...,"tabs":[]}`                                                           |
| Response     | `{"type":"hello_ack","session_id":...,"heartbeat_interval":...}`                                                                                  |
| Heartbeat     | Send `{"type":"ping"}` per `heartbeat_interval` (default 20s), receive `pong`                                                                     |
| Capabilities     | Receive `{"type":"capability.list"}` → reply `capability.list.result`; receive `{"type":"capability.call","id","name","params"}` → reply `capability.call.result` |
| Auth failure | Close code `4401` / `4403` → mark Token as invalid, **do not reconnect**, wait for the web page to push again                                       |
| Other disconnects | Exponential backoff reconnect: 1s → 30s                                                                                                           |

Field conventions for daemon sessions:

- `client_id`: `daemon-<hostname>-<uuid>`
- `extension_version`: the daemon's own version
- `browser_info`: identifies it as the daemon (e.g., `{"name":"haijunbot-daemon","os":...}`)
- `tabs`: empty array
- `user_id`: **not reported by the daemon**; instead the gateway parses it from `haijunbot-token.<token>` in the WS subprotocol and binds it to the session, used for multi-user isolation (see 8.7)

### 3.3 Status query

```http
GET http://127.0.0.1:17800/api/status
```

```json
{
  "connected": true,
  "session_id": "...",
  "gateway": "https://hjb-ai.cn",
  "token_valid": true,
  "daemon_version": "0.1.0"
}
```

The web page can poll this endpoint to display "Connected / Not connected / Token invalid".

## 4. Local API

| Method | Path          | Description                                        |
| ---- | ------------- | ------------------------------------------- |
| POST | `/api/auth`   | Receives `{gateway, token}`, stores in memory and triggers connection |
| GET  | `/api/status` | Returns connection status, `session_id`, Token validity    |
| POST | `/api/logout` | Clears the Token in memory, disconnects the WebSocket          |

### Security design

- **Bind only to `127.0.0.1`**, never listen on `0.0.0.0`;
- **No additional authentication** (confirmed): because it is only open to the local loopback, external access is impossible;
- Token is **memory-only**, not persisted to disk, and becomes invalid when the process exits.

## 5. Directory Structure

```text
daemon/                          # Same level as browser_extension/
├── DESIGN.md                    # This document
├── go.mod                       # module haijunbot-daemon
├── cmd/
│   └── haijunbot-daemon/
│       └── main.go              # Entry: load config, start local API, start WS client
└── internal/
    ├── config/
    │   └── config.go            # Port, gateway defaults, config file reading
    ├── localapi/
    │   └── server.go            # /api/auth /api/status /api/logout
    ├── auth/
    │   └── store.go             # In-memory token / gateway storage
    ├── wsclient/
    │   ├── client.go            # WS subprotocol + hello + heartbeat + reconnect + capability message handling
    │   └── client_capability_test.go # WS unit tests for capability list / capability call
    ├── capability/
    │   ├── capability.go        # Platform / Capability / Result / Registry
    │   ├── platform.go          # Current / Matches (platform determination)
    │   ├── registry_linux.go    # //go:build linux: Linux capability assembly (empty this round)
    │   ├── registry_windows.go  # //go:build windows: Windows capability assembly (empty this round)
    │   ├── registry_other.go    # //go:build !linux && !windows: fallback (empty this round)
    │   └── capability_test.go   # Registration / query / platform filter / execution unit tests
    └── handler/
        └── dispatch.go          # command dispatch (action is the capability name; returns not_implemented as placeholder when registry not wired up)
```

## 6. Configuration

Default config file: `~/.haijunbot/daemon/config.yaml`

```yaml
listen: "127.0.0.1:17800" # Local API listen address
gateway: "" # Default gateway (can be overridden by /api/auth)
heartbeat_interval: 20 # seconds, can be overridden by hello_ack
reconnect_min: 1 # seconds
reconnect_max: 30 # seconds
```

Command-line arguments can override the config file (e.g., `--listen`, `--gateway`).

## 7. Service Installation and Management

The daemon supports registration as a system service, enabling autostart on boot and unified lifecycle management. The reference implementation is `src/haijunbot/haijunbot_service/eli.py` (`SystemdBackend` / `WindowsTaskBackend`).

### 7.1 Subcommands

```text
haijunbot-daemon [run] [options]     Run the daemon in the foreground (default behavior, backward compatible)
haijunbot-daemon install [options]   Install as a system service and set to autostart on boot (does not start)
haijunbot-daemon uninstall        Stop and uninstall the system service
haijunbot-daemon start            Start the service
haijunbot-daemon stop             Stop the service
haijunbot-daemon restart          Restart the service
haijunbot-daemon status           View service status
```

`install` and `run` share the `-listen` / `-gateway` / `-config` options; `install` will bake these values into the service definition.

### 7.2 Platform implementation

| Item       | Linux                                                  | Windows                                       |
| -------- | ------------------------------------------------------ | --------------------------------------------- |
| Service definition | `~/.config/systemd/user/haijunbot-daemon.service`         | Scheduled task `HaijunBot-Daemon`                      |
| Install     | Write unit + `systemctl --user daemon-reload` + `enable`  | `schtasks /Create /SC ONLOGON /RL HIGHEST /F` |
| Start     | `systemctl --user start`                               | Detached process start + PID file                       |
| Stop     | `systemctl --user stop`                                | `taskkill /PID <pid> /F`                      |
| Autostart     | `systemctl --user enable`                              | The scheduled task itself (triggered at logon)                    |
| Status     | `is-active` / `is-enabled` / `show --property=MainPID` | PID alive (`tasklist`) + `schtasks /Query`     |

Key contents of the Linux unit:

```ini
[Unit]
Description=HaijunBot Daemon
After=network.target

[Service]
Type=simple
Environment=PATH=<executable directory>:<current PATH>
Environment=<passthrough proxy environment variables, written only if present>
ExecStart=<absolute path to executable> run --listen 127.0.0.1:17800
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
```

The Windows PID file is located at `~/.haijunbot/pids/haijunbot-daemon.pid`.

### 7.3 Code structure

```text
internal/service/
├── service.go            # Service interface, Options, Status, New, ResolveExecPath, BuildRunArgs
├── systemd_linux.go      # //go:build linux: BuildUnit + systemd user service implementation
├── task_windows.go       # //go:build windows: scheduled task implementation
├── new_linux.go          # //go:build linux: platform dispatch
├── new_windows.go        # //go:build windows: platform dispatch
├── new_other.go          # //go:build !linux && !windows: fallback
├── procattr_windows.go   # //go:build windows: detached process start attributes
├── procattr_other.go     # //go:build !windows: empty implementation
└── service_test.go       # Pure function and platform dispatch unit tests
```

Platform dispatch is provided by each platform file via `newPlatformService()`; `New()` falls back to `unsupportedService` when it returns nil (avoiding references to platform-specific types in files without build tags).

## 8. Capability Registry

### 8.1 Design goals and reference

The daemon needs a unified way to describe "what this machine can do", letting the gateway (and thus the model) **query capabilities first, then call by name**, without hardcoding platform differences on the gateway side.

The reference is the `Tool` / `ToolRegistry` model in the Python side `src/haijunbot/haijunbot_tools/registry.py`: each tool consists of the four elements `name` / `description` / `parameters` / `func`, and the registry handles registration, lookup, listing, and execution. The Go side does an equivalent mapping but uses Go idioms: `Handler` returns `(any, error)`, and results are expressed with `Result{Success, Data, Error}`.

### 8.2 Capability structure

| Field          | Type                                       | Description                                              |
| ------------- | ------------------------------------------ | ------------------------------------------------- |
| `name`        | `string`                                   | Unique capability name, recommended "domain.action" form (e.g., `fs.read`) |
| `description` | `string`                                   | Capability description, for the model to understand its purpose                          |
| `parameters`  | `map[string]any`                           | Parameter JSON schema description, may be empty                     |
| `platform`    | `Platform`                                 | Applicable platform; treated as `any` when empty                        |
| `handler`     | `func(params map[string]any) (any, error)` | Capability implementation; not included in JSON serialization (`json:"-"`)        |

`Result` is the result of one call: `success` (bool), `data` (any), `error` (string).

### 8.3 Registry interface

| Method                             | Description                                                                                                                                                   |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `NewRegistry()`                  | Create the registry and call `registerPlatformCapabilities` to assemble the current platform's capabilities                                                                                     |
| `Register(cap Capability) error` | Register a capability; empty name or duplicate registration returns an error (no silent overwrite)                                                                                                   |
| `Get(name string)`               | Look up by name, returns `(*Capability, bool)`                                                                                                                   |
| `List()`                         | Returns copies of all capabilities, sorted by name ascending                                                                                                                           |
| `ListForPlatform(p Platform)`    | Returns capabilities applicable to the specified platform (including `any`), sorted by name ascending                                                                                                       |
| `Execute(name, params) Result`   | Execute by name; unregistered returns `unknown capability: <name>`; nil `handler` returns `capability not implemented: <name>`; a `handler` panic is recovered and turned into an error |

The registry is concurrency-safe (`sync.RWMutex`) and **contains no global state**—`NewRegistry()` returns an independent instance each time, so multiple daemons connecting to the same gateway do not interfere with each other.

### 8.4 Platform division and dispatch

Platform values: `windows` / `linux` / `darwin` / `any`, where `any` denotes a cross-platform general capability (`Matches` returns true for any platform).

Platform-specific capabilities are assembled via **build tags**:

```text
internal/capability/
├── capability.go          # No tag: types and registry
├── platform.go            # No tag: Current / Matches
├── registry_linux.go      # //go:build linux
├── registry_windows.go    # //go:build windows
└── registry_other.go      # //go:build !linux && !windows
```

Each platform file provides `registerPlatformCapabilities(reg *Registry)`, called by `NewRegistry()`. The reason for not writing a `runtime.GOOS` `switch` in an untagged file is that it would reference platform-specific types, and during cross-compilation (e.g., `GOOS=windows go build`) the corresponding types would be excluded, causing an outright build failure. This approach is consistent with `newPlatformService()` in `internal/service`.

### 8.5 WS protocol extension

Add two types of messages on the existing WS connection (gateway → daemon):

#### Query capability list

```json
{ "type": "capability.list" }
```

```json
{
  "type": "capability.list.result",
  "capabilities": [
    {
      "name": "fs.read",
      "description": "Read file contents",
      "parameters": {
        "type": "object",
        "properties": { "path": { "type": "string" } }
      },
      "platform": "any"
    }
  ]
}
```

#### Invoke capability

```json
{
  "type": "capability.call",
  "id": "call-1",
  "name": "fs.read",
  "params": { "path": "/tmp/a.txt" }
}
```

```json
{
  "type": "capability.call.result",
  "id": "call-1",
  "success": true,
  "data": { "content": "..." },
  "error": ""
}
```

On failure, `success` is `false` and `error` gives the reason (e.g., `unknown capability: fs.read`, `capability registry is nil`, `capability name is empty`).

### 8.6 Relationship with the extension command/result envelope

The command envelope structure remains unchanged (`{id, type:"command", action, params, timeout_ms}` → `{id, type:"result", success, data, error}`), except that **`action` is now the capability name**: after wiring up the registry it is executed by `handler.DispatchWith(reg, cmd)`; when not wired up (`Registry` is nil) it falls back to the old placeholder implementation (returns `not_implemented`), ensuring backward compatibility.

### 8.7 Scope this round

This round implements the framework **and registers Linux platform capabilities**:

- The Linux platform has registered 21 capabilities (`registerPlatformCapabilities` assembled in `registry_linux.go` under `//go:build linux`), see the table below; Windows platform capabilities were subsequently completed (`registry_windows.go` assembled under `//go:build windows`, covering system / process / application / GUI / input / clipboard / script / filesystem / cross-machine direct transfer / service / system configuration (theme / power plan / proxy / screen timeout / remote desktop / startup) / UI automation (control tree / menu) / browser extension / OCR, etc.), Darwin is not yet registered (falls back to `registry_other.go`);
- Gateway side (Python) implemented: added the dedicated endpoint `/api/daemon/ws` and session management `daemon_capability_manager`, and provided three HTTP APIs `/api/daemon/sessions`, `/api/daemon/capability/list`, `/api/daemon/capability/call`; cross-node calls are forwarded by `NodeConnectionManager` via the `daemon_capability_*` messages of `node_protocol`;
- When multiple daemons connect to the same gateway, the gateway distinguishes sessions by the `client_id` in `hello` (`session_id` is assigned by the gateway), and capability call results are routed back to the corresponding session by `id`.

#### Registered Linux capabilities

| Capability name                  | Description                                           | Implementation                                       |
| ----------------------- | ---------------------------------------------- | ---------------------------------------------- |
| `linux.script.exec`     | Execute shell script                                | `sh -c` (with timeout)                              |
| `linux.process.list`    | List processes                                       | Read `/proc` directly (does not depend on `ps`)                  |
| `linux.process.kill`    | Kill process                                       | Send signal                                       |
| `linux.system.info`     | System info (distro/kernel/CPU/memory, etc.)             | Read `/proc`, `/etc/os-release`                  |
| `linux.fs.read`         | Read file (supports offset/limit, binary auto base64) | Standard library                                         |
| `linux.fs.write`        | Write file                                         | Standard library                                         |
| `linux.fs.list`         | List directory                                         | Standard library                                         |
| `linux.service.list`    | List user-level systemd services                        | `systemctl --user`                             |
| `linux.service.status`  | Query service status                                   | `systemctl --user`                             |
| `linux.service.start`   | Start service                                       | `systemctl --user`                             |
| `linux.service.stop`    | Stop service                                       | `systemctl --user`                             |
| `linux.service.restart` | Restart service                                       | `systemctl --user`                             |
| `linux.window.list`     | List windows                                       | `wmctrl -lp`, fallback `xdotool search`            |
| `linux.window.focus`    | Focus window                                       | `wmctrl -i -a` / `xdotool windowactivate`      |
| `linux.window.close`    | Close window                                       | `wmctrl -i -c` / `xdotool windowclose`         |
| `linux.input.click`     | Move mouse and click                                 | `xdotool mousemove` + `click`                  |
| `linux.input.type`      | Type text                                       | `xdotool type --delay -- <text>`               |
| `linux.input.keys`      | Send keys/key combinations                                | `xdotool key -- <keys>`                        |
| `linux.clipboard.get`   | Read clipboard                                       | `xclip -selection clipboard -o` / `xsel -b -o` |
| `linux.clipboard.set`   | Write clipboard                                       | `xclip` stdin / `xsel -b -i`                   |
| `linux.screenshot`      | Screenshot                                           | `import` > `scrot` > `grim`                    |

Design constraints and known limitations:

- **GUI capabilities do not link X11 directly**: an early attempt to call X11 with pure Go `dlopen` (`cgo_import_dynamic` + `linkname`) failed (ABI0/ABIInternal mismatch), and the cgo approach required `X11/extensions/XTest.h` and broke `CGO_ENABLED=0` cross-compilation, so it was finally changed to **invoking external commands** (`xdotool`/`wmctrl`/`xclip`/`xsel`/`import`/`scrot`/`grim`). When a tool is missing, it returns a clear error with an installation hint.
- Before executing a GUI capability, it checks `DISPLAY` / `WAYLAND_DISPLAY`; when empty it returns "no graphical environment detected"; under Wayland `xdotool`/`wmctrl` are usually unavailable (only `grim` screenshots work).
- `linux.service.*` only supports `--user`-level services; unit names undergo whitelist validation and are **rejected if they start with `-`**, preventing things like `--now` from being treated by `systemctl` as command-line options (argument injection).
- `linux.fs.*` does no path whitelisting/sandboxing and can read/write any path the daemon has permission for; binary detection is "contains NUL or invalid UTF-8", so pure-ASCII binary formats may be missed.
- The success path of GUI capabilities is **not end-to-end verified on this machine** (this machine has no `DISPLAY` and all GUI tools are missing); only the error path and parsing logic were verified.

#### Multi-user isolation

Daemon capabilities can perform arbitrary operations on the user's machine, so the gateway side must enforce user-level isolation, preventing any valid Token from invoking another user's machine across users:

- **Session bound to `user_id`**: after successful authentication at the `/api/daemon/ws` endpoint, `user_id` is taken from `auth_payload["user_info"]` and passed to `DaemonCapabilityManager.handle_daemon_websocket`, written into the session; the browser extension endpoint (`/api/browser-ext/ws`) is handled the same way.
- **Remove the "allow even without Token" fallback**: the WS endpoints of daemon and browser-ext previously allowed connections without a token on the grounds that "the gateway has some logged-in session"; this has now been changed to an outright authentication failure (4401).
- **HTTP API ownership check**: `/api/daemon/capability/list`, `/api/daemon/capability/call`, `/api/browser-ext/command` use `check_session_access(session_id, user_id, is_admin)` before the call to verify session ownership; `/api/daemon/sessions`, `/api/browser-ext/sessions` filter by `user_id` (when `user_id` is `system` or `is_admin`, all are visible).
- **Cross-node forwarding carries `user_id`**: when the master forwards `daemon_capability_list_request` / `daemon_capability_call_request` to a child, the payload carries `user_id` and `is_admin`, and the child side re-verifies ownership to prevent bypass.
- **Rejection semantics**: a nonexistent session returns `daemon session not found: <id>`; a cross-user one returns `forbidden: daemon session belongs to another user`.

## 9. Web-side changes

Only one place: add an "Authenticate local process" button; clicking it:

```js
await fetch("http://127.0.0.1:17800/api/auth", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    gateway: window.__haijunbotAuthBridge.getGateway(),
    token: window.__haijunbotAuthBridge.getToken(),
  }),
});
```

Does not change any existing logic.

## 10. Verification method

1. `go build ./...` passes;
2. Start the daemon, `curl -X POST http://127.0.0.1:17800/api/auth -d '{"gateway":"...","token":"<real JWT>"}'`;
3. `GET /api/status` returns `connected: true` with a `session_id`;
4. On the gateway side, `GET /api/daemon/sessions` shows the session;
5. On the gateway side, `POST /api/daemon/capability/list` (with `session_id`) → returns the capability list (21 `linux.*` capabilities on Linux);
6. On the gateway side, `POST /api/daemon/capability/call` (with `session_id`/`name`/`params`) → executes the corresponding capability; when the capability name does not exist, returns `unknown capability: <name>`;
7. Reconnect with backoff after a disconnect; do not spin-reconnect when the Token is invalid (4401);
8. Multi-user isolation: using user A's Token with user B's `session_id` to call `capability/list` or `capability/call` → returns `forbidden: daemon session belongs to another user`; `GET /api/daemon/sessions` returns only A's own sessions; connecting to `/api/daemon/ws` without a Token → close code 4401.

## 11. Follow-up (not this round)

- Actual execution of commands (business features);
- Daemon self-update;
- Browser extension update (download zip → overwrite extension directory → notify `chrome.runtime.reload()`);
- Server-side update.

## 12. Confirmed decisions

| Item             | Decision                                                                                   |
| -------------- | -------------------------------------------------------------------------------------- |
| Local port authentication   | No authentication (bind 127.0.0.1 only)                                                             |
| Port / config    | Default `127.0.0.1:17800`, config via `~/.haijunbot/daemon/config.yaml`                          |
| Code location       | `daemon/`, same directory as the browser extension                                                          |
| Scope this round       | Only wire up the chain and communication                                                                       |
| Extension directory path   | To be determined later (extension update not involved this round)                                                         |
| Capability naming       | "domain.action" form (e.g., `fs.read`), `action` is the capability name                                     |
| Capability platform dispatch   | Use build tags (`registry_*.go`), do not write a platform switch in untagged files                           |
| Capability registry scope | Framework + 21 Linux platform capabilities implemented; Windows platform capabilities completed; Darwin not registered; gateway side implemented |
