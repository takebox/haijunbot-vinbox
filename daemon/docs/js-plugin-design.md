# haijunbot-daemon JS Plugin System Design Document

> Status: Design draft (pending review)
> Author: HaijunBot
> Date: 2026-10-02

## 1. Background and Goals

haijunbot-daemon (a GO background service) currently exposes system capabilities externally through the **capability registry** (`internal/capability`),
with the gateway dispatching commands to execute them over the WS protocol. The capability list covers filesystem (fs.read/write/list), process, clipboard, input,
window, service, system info, screenshot, OCR, browser extension, etc.

**Goal**: implement a **JS runtime plugin system** inside haijunbot-daemon, exposing the built-in GO capabilities as JS objects,
so users can write JS scripts for automation (similar to shell scripts, but with richer capabilities and friendlier semantics).

**Script management**: following the management model of the browser extension (browser.ext), provide management capabilities for scripts such as install, update, list, query, delete, and run,
making scripts first-class citizens manageable by the daemon (see §6).

**Non-goals**:

- Does not change the existing capability registration logic or the WS gateway call chain.
- Does no browser-side sandboxing/multi-tenant isolation (scripts run with daemon permissions, equivalent to shell permissions; see §8 security model).

## 2. Technology Choice: goja

The Go standard library does not provide a JS interpreter, so a third-party JS engine must be introduced. Candidate comparison:

| Engine                    | Language     | cgo    | License | Description                                                 |
| ----------------------- | -------- | ------ | ---- | ---------------------------------------------------- |
| **goja** (dop251/goja) | Pure Go    | None     | MIT  | The most active pure Go ES5.1+ engine, supports async/await, Promise |
| otto                    | Pure Go    | None     | MIT  | Older, maintenance inactive, average performance                           |
| v8go                    | C++ binding | **Yes** | BSD  | Depends on V8, good performance but introduces cgo and a huge binary               |

**Choice conclusion: goja**.

- Pure Go implementation, **zero cgo**, consistent with the daemon's existing "pure syscall + zero cgo" design philosophy, cross-compilation friendly.
- MIT license, all dependencies are pure Go libraries (regexp2, sourcemap, x/text, etc.).
- Supports ES5.1 and part of ES6+ (async/await, Promise, arrow functions), sufficient to support automation scripts.

**Dependency impact**: go.mod gains `github.com/dop251/goja` and its pure Go transitive dependencies, no cgo, no binary size explosion.

## 3. Overall Architecture

```text
┌────────────────────────────────────────────────────────────┐
│                     cmd/haijunbot-daemon/main.go                │
│    run-script / script <list|status|install|remove|run>      │
│                        │                                     │
│                        ▼                                     │
│   ┌──────────────────────────────────────────────────────┐  │
│   │          internal/jsruntime  (new package)            │  │
│   │                                                       │  │
│   │  ┌─────────────────┐   ┌──────────────────────────┐  │  │
│   │  │  Runtime         │   │  CapabilityBridge        │  │  │
│   │  │  (goja wrapper)  │   │  (capability → JS object)│  │  │
│   │  │  - RunScript()   │   │  - haijunbot.cap()          │  │  │
│   │  │  - error handling│   │  - haijunbot.caps.<nested>  │  │  │
│   │  └─────────────────┘   │  - haijunbot.listCaps()      │  │  │
│   │                        └──────────────────────────┘  │  │
│   └──────────────────────────────┬───────────────────────┘  │
│                                  │ call                     │
│   ┌──────────────────────────────▼───────────────────────┐  │
│   │      internal/capability.Registry (existing, unchanged)│  │
│   │      Execute(name, params) → Result{Success,Data,Err}│  │
│   └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

- **`internal/jsruntime`** (new package): wraps the goja runtime, providing script execution and capability bridging.
- **`internal/capability`** (existing package, **unchanged**): the capability registry, acting as the backend executor for JS capabilities.
- **`cmd/haijunbot-daemon/main.go`**: adds the `run-script` and `script` subcommands, assembling the Registry → injecting the JS runtime → executing/managing scripts.

## 4. Capability Exposure API Design

Within scripts, capabilities are accessed through the global `haijunbot` object. Three access forms are provided to suit different scenarios.

### 4.1 `haijunbot.cap(name, params)` —— General call

Calls directly by capability name, returning the capability `Result` (`{success, data, error}`).

```js
const res = haijunbot.cap("linux.system.info");
if (res.success) {
  print("hostname:", res.data.hostname);
} else {
  print("failed:", res.error);
}
```

### 4.2 `haijunbot.caps.<domain>.<action>(params)` —— Nested namespace

Iterates over all capabilities in the Registry, splitting capability names by `.` into nested objects, with leaf nodes as callable functions.
Capability name `linux.fs.read` → `haijunbot.caps.linux.fs.read({path})`.

```js
const files = haijunbot.caps.linux.fs.list({ path: "/home" });
print(JSON.stringify(files.data, null, 2));
```

**Implementation highlights**:

- When calling, if `Result.Success === false`, **throw a JS exception** (`throw new Error(res.error)`), letting scripts handle failures with try/catch; meanwhile `haijunbot.cap` provides an object-returning form for scenarios needing explicit success/failure checks.
- Parameters: JS objects are automatically converted to `map[string]any` (goja natively supports object ↔ Go map conversion).
- Unregistered capability: `haijunbot.cap` returns `{success:false, error:"unknown capability: ..."}`; nested access to a nonexistent domain/action returns `undefined`, and calling it raises a TypeError.

### 4.3 `haijunbot.listCaps()` —— Capability list

Returns the list of capabilities available on the current platform (name + description + parameter schema), making it easy for script authors to discover capabilities.

```js
haijunbot.listCaps().forEach((c) => print(c.name, "-", c.description));
```

### 4.4 Automatic capability exposure mechanism

**All capabilities registered in the Registry are automatically exposed to JS**, with no need to hand-write bindings for each capability:

- The `haijunbot.caps` nested object is automatically built by iterating `Registry.ListForPlatform(capability.Current())`, split by capability name `.` to generate the nested structure. **Add a capability and it is automatically usable in JS**.
- Automatic platform filtering: only exposes capabilities applicable to the current platform (including `PlatformAny`); on Linux only `linux.*` + `any.*` are visible.
- `haijunbot.cap(name, params)` is the general entry, looking up the Registry directly by name and calling Execute.

## 5. Script Execution (run-script)

### 5.1 CLI subcommand `run-script`

```text
haijunbot-daemon run-script <file.js> [--arg key=value ...]
```

- `<file.js>`: script file path (required), can be a `.js` file at any path.
- `--arg key=value`: optional, injects key-value pairs into the script's global object `haijunbot.args` (e.g., `haijunbot.args.path`), for script parameterization.

**Execution flow**:

1. Create `capability.NewRegistry()` and assemble the current platform's capabilities (reusing the registration logic of the existing `run` flow, see §7 reuse points).
2. Read the script file contents.
3. Create `jsruntime.Runtime`, inject the `haijunbot` capability object.
4. Execute the script; output the result or error.
5. Exit code: 0 on success; non-zero on script syntax error / runtime error / capability call failure.

### 5.2 Output conventions

- Within scripts, `print(...)` / `console.log(...)` output to stdout.
- A Promise returned at the top level of the script is awaited (supports async scripts).
- Errors are output to stderr, with goja stack information (file/line number) attached to aid location.

## 6. Script Management (script.\* capabilities + CLI)

Following the management model of the browser extension (browser.ext), treat scripts as objects manageable by the daemon.

### 6.1 Storage layout

```text
~/.haijunbot/scripts/
├── <name>.js              # The script itself (single file)
└── <name>.json            # Optional metadata (manifest: name/version/description/enabled)
```

- Fixed directory `~/.haijunbot/scripts/`, at the same level as `~/.haijunbot/browser_extension`, following the existing `~/.haijunbot` convention.
- One `<name>.js` file per script; an optional same-named `<name>.json` stores metadata (version, description, enabled state).
- The script name is the file name (without extension), serving as the unique identifier of the script.

### 6.2 Management capabilities (exposed as capability)

Script management itself is exposed as a capability (cross-platform, `PlatformAny`), available both for the gateway to dispatch commands to manage scripts
and for invoking within scripts via `haijunbot.cap("script.list")` (inter-script collaboration).

| Capability name           | Purpose                                      | Key parameters                                                         |
| ---------------- | ----------------------------------------- | ---------------------------------------------------------------- |
| `script.list`    | List installed scripts (name/version/description/enabled state) | —                                                                |
| `script.status`  | Query the status of a single script                          | `name`                                                           |
| `script.install` | Install/update script (from a local file path or content)     | `name`, `source` (file path or script content), `description`, `enabled` |
| `script.remove`  | Delete script                                  | `name`                                                           |
| `script.run`     | Run an installed script (by name)                  | `name`, `args` (passed to `haijunbot.args`)                             |

**install sources**:

- When `source` is a local file path, read the file contents to install;
- When `source` is a script content string, write it directly;
- When updating, overwrite the same-named script, preserving metadata or updating per parameters.

**Security validation** (following browser.ext's extraction security policy):

- Script names allow only `[A-Za-z0-9_-]`, rejecting path traversal (`../`, absolute paths) to prevent writing outside `~/.haijunbot/scripts/`.
- A size limit is set for script files (e.g., 1 MiB) to prevent abnormal content from bloating.

### 6.3 CLI subcommand `script`

```text
haijunbot-daemon script list
haijunbot-daemon script status <name>
haijunbot-daemon script install <name> <source.js> [--desc ...] [--disable]
haijunbot-daemon script remove <name>
haijunbot-daemon script run <name> [--arg key=value ...]
```

- `script list`: list installed scripts.
- `script install <name> <source.js>`: install/update a script from a local `.js` file.
- `script run <name>`: run an installed script (equivalent to `run-script ~/.haijunbot/scripts/<name>.js`, but resolved by name).

### 6.4 Correspondence with the browser extension

| Browser extension (browser.ext)              | JS script (script.\*)                |
| -------------------------------------- | ----------------------------------- |
| `~/.haijunbot/browser_extension` fixed directory | `~/.haijunbot/scripts/` fixed directory       |
| `browser.ext.status`                   | `script.status` / `script.list`     |
| `browser.ext.sync` (download from gateway)       | `script.install` (from local path/content) |
| manifest.json version                     | `<name>.json` metadata version            |
| Takes effect on manual browser refresh                     | Scripts run on demand, no hot-reload concept          |

## 7. Code Reuse Points

The `run` flow in `main.go` (around line 544) already contains the capability assembly logic:

```go
registry := capability.NewRegistry()
capability.SetBrowserExtCredentialProvider(...) // Inject gateway Token
capability.SetOcrGatewayLister(...)             // Inject the list of authenticated gateways
```

`run-script` and `script run` need to reuse this assembly logic (especially injecting the provider, so browser.ext / ocr capabilities are available).
**Approach**: extract a `newRuntimeRegistry()` helper function (or reuse the existing assembly function), shared by `run`, `run-script`, `script run`,
to avoid reinventing the wheel. The specific extraction method will be determined during implementation per the principle of minimal change.

## 8. Security Model

- **Permission boundary**: JS scripts run with daemon permissions and can invoke all registered capabilities (equivalent to shell script permissions).
  This is the intended design—the plugin system is positioned as a "local automation tool" and does no sandbox isolation.
- **Capability whitelist (optional enhancement)**: later, `--allow` / `--deny` arguments or a config file can be added to restrict the subset of capabilities a script can call,
  reducing the risk of mistakes. Not implemented in the first version; described in the docs.
- **Script name validation**: only `[A-Za-z0-9_-]` is allowed, rejecting path traversal and preventing out-of-bounds script writes.
- **Injection surface**: `haijunbot.args` comes only from CLI `--arg` or `script.run`'s `args`; capability parameters come from the script itself; there is no network input and no XSS surface.
- **Documentation hint**: clearly inform users that script permissions are equivalent to the daemon's, and not to run scripts of unknown origin.

## 9. Directory Structure (new parts)

```text
daemon/
├── cmd/haijunbot-daemon/
│   └── main.go                  # Add run-script and script subcommands
├── internal/
│   └── jsruntime/               # New package
│       ├── runtime.go           # goja wrapper: create runtime, RunScript, error handling
│       ├── bridge.go            # Capability bridge: haijunbot.cap / haijunbot.caps / haijunbot.listCaps
│       ├── runtime_test.go      # Unit tests
│       └── bridge_test.go       # Capability bridge unit tests (fake capabilities)
├── internal/
│   └── scriptmgr/               # New package: script storage and management (list/status/install/remove)
│       ├── manager.go           # Script directory resolution, CRUD, security validation
│       ├── manager_test.go      # Unit tests
├── examples/
│   ├── system-info.js           # Example: read system info
│   └── list-dir.js              # Example: list directory
└── docs/
    └── js-plugin-design.md      # This document
```

## 10. Implementation Plan

| Step | Content                                                          | Verification                            |
| ---- | ------------------------------------------------------------- | ------------------------------- |
| 1    | Introduce the goja dependency, implement the `internal/jsruntime` runtime wrapper          | Unit tests execute JS expressions/functions/Promise |
| 2    | Implement the capability bridge (haijunbot.cap / haijunbot.caps / haijunbot.listCaps)    | Unit tests verify calls and errors with fake capabilities  |
| 3    | Implement `scriptmgr` script storage and management (list/status/install/remove) | Unit tests cover CRUD and security validation        |
| 4    | Implement the `run-script` and `script` subcommands + assembly reuse               | Actually execute example scripts, manage scripts      |
| 5    | Write example scripts and usage docs                                        | Example scripts run end-to-end              |
| 6    | Overall verification (build + test + examples)                               | All green, no regressions                    |

## 11. Verification Plan

- **Unit tests**:
  - `internal/jsruntime`: basic JS execution, async/await, capability call success/failure, unregistered capability, parameter passing (string/number/bool/nested object).
  - `internal/scriptmgr`: script CRUD, script name validation (path traversal rejection), size limit, metadata read/write.
- **End-to-end**: `go run ./cmd/haijunbot-daemon script install demo examples/system-info.js` → `script list` → `script run demo` actually invokes capabilities and outputs results.
- **Regression**: `go build ./...` + `go test ./...` all green, existing subcommands such as `run`/`status` unaffected.
- **Dependency check**: after `go mod tidy`, go.mod only gains goja and its pure Go transitive dependencies, no cgo.
