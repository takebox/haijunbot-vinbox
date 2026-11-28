# Extending LSP Language Support for the Editor

This document explains how to add LSP (Language Server Protocol) support for a language to HaijunBot's editor through configuration.

**Core mechanism: changing configuration is extending.** To add a language, just add an entry in the `lsp.languages` section of `~/.haijunbot/config.yaml`,
**with no need to modify any code**.

## Overall Architecture

HaijunBot uses LSP in two places, and they **share the same configuration**:

```text
~/.haijunbot/config.yaml  →  lsp.languages  ← single source of configuration
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
  haijunbot-lsp (CLI / daemon)      Web gateway (Monaco editor)
  hover / definition / references / diagnostics         hover / completion / diagnostics
              │                             │
              │                    WS /api/lsp/{language}?root=<workspace>
              │                             │ (gateway bridging, language-agnostic, pure forwarding)
              │                             ▼
              └────────────► language server subprocess (stdio)
```

- **Configuration reading layer**: `LSPConfigReader` in `src/haijunbot/haijunbot_lsp/config.py`,
  shared by both places to avoid configuration drift.
- **Web gateway conversion**: `src/haijunbot/haijunbot_web_gateway/lsp_registry.py` converts the configuration into the
  gateway's internal spec structure.
- **WS bridging**: `src/haijunbot/haijunbot_web_gateway/lsp_bridge.py` and `app.py`'s
  `GET /api/lsp/servers` and `WS /api/lsp/{language}`; it is completely language-agnostic, only doing
  JSON-RPC forwarding between WebSocket ↔ subprocess stdio.
- **Frontend client**: `src/haijunbot/haijunbot_service/frontend/src/lsp/registry.js` (fetches the manifest, builds the index)
  and `manager.js` (connection, document synchronization, registering hover/completion providers, diagnostics).

## Configuration Location

The configuration is located in the `lsp.languages` section of `~/.haijunbot/config.yaml`:

```yaml
lsp:
  languages:
    python:
      command: pylsp
      args: []
      file_extensions: [".py", ".pyi"]
      monaco_language: python
      root_markers: ["pyproject.toml", "setup.py", ".git"]
      install_hint: "pip install python-lsp-server"
```

**Built-in defaults**: the code contains built-in default configurations for 13 languages (python / go / typescript /
javascript / rust / c / cpp / lua / bash / ruby / php / html / css),
ready to use out of the box. A user configuration **fully overrides** the default entry for a language with the same name, and languages not configured use the default.

## Field Description

| Field                    | Type         | Required | Default                | Description                                                                                                   |
| ------------------------ | ------------ | -------- | ---------------------- | ------------------------------------------------------------------------------------------------------------- |
| `command`                | string       | ✅       | —                      | Startup command (executable file name or absolute path). Put parameters in `args`, do not write them together |
| `args`                   | list[string] |          | `[]`                   | Startup arguments, e.g. `["--stdio"]`                                                                         |
| `file_extensions`        | list[string] |          | `[]`                   | File extensions, e.g. `[".py", ".pyi"]`, used to match the language by extension                              |
| `monaco_language`        | string       |          | Uses the language name | The corresponding Monaco language id, e.g. `python`, `typescript`                                             |
| `root_markers`           | list[string] |          | `[]`                   | Marker files used to determine the workspace root, e.g. `["Cargo.toml", ".git"]`                              |
| `initialization_options` | object       |          | `{}`                   | Initialization options passed to the LSP `initialize`                                                         |
| `install_hint`           | string       |          | `""`                   | The hint text shown to the user when the server is not installed                                              |

The language name (the key under `languages`) is the server id, and is also the value in the WS path `/api/lsp/{language}`,
and is **case-insensitive**.

**Fault tolerance**: language entries with a missing `command` or wrong field types are skipped and a `logging.warning` is recorded,
**without affecting other languages**.

## Complete Example: Adding Rust Support (rust-analyzer)

### Step 1: Install the Language Server

```bash
rustup component add rust-analyzer
rust-analyzer --version    # confirm it is executable
```

### Step 2: Modify the Configuration

Edit `~/.haijunbot/config.yaml` and add under `lsp.languages`:

```yaml
lsp:
  languages:
    rust:
      command: rust-analyzer
      args: []
      file_extensions: [".rs"]
      monaco_language: rust
      root_markers: ["Cargo.toml", "Cargo.lock", ".git"]
      install_hint: "rustup component add rust-analyzer"
```

### Step 3: Confirm It Is Recognized

```bash
cd /home/skyfire/code/HaijunBot
.venv/bin/python -c "
from haijunbot.haijunbot_web_gateway.lsp_registry import load_lsp_server_specs
for sid, s in sorted(load_lsp_server_specs().items()):
    print(f'{sid:12} monaco={s[\"monacoLanguage\"]:12} command={s[\"command\"]}')
"
```

You should see a `rust` line. If not, check the YAML indentation and whether `command` is a string.

### Step 4: Take Effect

- **haijunbot-lsp**: takes effect on the next call (the configuration is read every time).
- **Web editor**: restart the gateway (the configuration is loaded at startup) and refresh the browser page.

Then open a `.rs` file in the Web UI; hovering over a symbol should show type/documentation hints, and completion suggestions should appear while typing.

## Degradation Behavior

Design principle: **LSP is an enhancement, not a dependency**. The failure of any part will not affect the editor's basic functionality
(open, edit, save, multi-tab, syntax highlighting).

| Scenario                                               | Behavior                                                                                                                                          |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language server not installed / command does not exist | Backend returns `SERVER_START_FAILED` (including `install_hint`); frontend logs one degradation warning via `console.warn`, editor works normally |
| WS connection failure / timeout                        | Frontend `console.warn`, silently degrades to syntax highlighting only                                                                            |
| Config entry missing `command` / type error            | Backend skips that entry and records a warning; other languages are unaffected                                                                    |
| Manifest fetch failure                                 | Frontend degrades to an empty map; all languages degrade to syntax highlighting only                                                              |
| Files on non-master nodes                              | Currently only master-local LSP is supported; non-master files are skipped (known limitation)                                                     |

## Debugging Methods

### 1. Confirm Whether the Configuration Is Recognized

```bash
cd /home/skyfire/code/HaijunBot
.venv/bin/python -c "
from haijunbot.haijunbot_lsp.config import LSPConfigReader
r = LSPConfigReader()
for name, cfg in sorted(r.load_config().languages.items()):
    print(f'{name:12} command={cfg.command:30} args={cfg.args} ext={cfg.file_extensions}')
"
```

### 2. Check the Bridge Logs

The language server process's startup, stderr, and exit are all written to the gateway log with the keyword prefix `[lsp_bridge]`:

```bash
grep "\[lsp_bridge\]" <gateway log file>
```

Common logs:

- Process startup / reuse: `logger.info` (containing `server_id`, `workspace_root`, pid)
- Subprocess stderr output: forwarded as-is (the language server's own errors appear here)
- Idle reclamation / exit: `logger.info`

### 3. Check the Frontend Logs

In the browser developer tools Console, LSP-related logs start with `[lsp]`:

- `[lsp] Failed to fetch the language server manifest: HTTP 401` — token problem
- `[lsp] Language server "xxx" is unavailable; degraded to syntax highlighting only. Install hint: ...` — server not installed
- `[lsp] Exception fetching the language server manifest; degraded to no LSP` — network/gateway problem

### 4. Manually Verify the WS Bridge

```bash
# requires websocat or a similar tool; the token goes in the subprotocol
websocat -H="Sec-WebSocket-Protocol: haijunbot-ws,haijunbot-token.<urlencoded-token>" \
  "ws://127.0.0.1:8000/api/lsp/rust?root=/abs/path/to/project"
# then manually type one line of JSON-RPC:
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"processId":null,"rootUri":null,"capabilities":{}}}
```

Receiving `result.capabilities` means both the bridge and the language server are working normally.

## Known Limitations

1. **Master-local only**: file read/write goes through `/api/node/{nodeId}/...`, but the LSP bridge is registered locally on the master.
   Files on non-master nodes skip LSP (cross-node WS forwarding is a separate transport-layer problem).
2. **The workspace root uses the file's containing directory**: it does not search upward for `root_markers`, so opening files in different subdirectories of the same project
   may start a separate language server process each.
3. **`didSave` is not implemented**: currently didOpen / didChange / didClose are synchronized, but didSave is not sent.

## CodeAgent Integration

Besides the editor (Monaco), LSP capabilities are also exposed to CodeAgent in the form of a native tool.

### Tool Form

The tool name is `lsp` (`src/haijunbot/haijunbot_tools/lsp.py`), adopting a **single-tool + action enum** design
to avoid polluting the tool list by registering one tool per LSP method. It is registered in CodeAgent's
`base_tools` (the `_build_code_agent_tool_list` of `code_agent.py`).

```json
{
  "name": "lsp",
  "arguments": {
    "action": "find_definition",
    "file_path": "src/main.py",
    "symbol_name": "MyClass"
  }
}
```

### action List

| action               | Required parameters    | Corresponding LSPDaemonClient method |
| -------------------- | ---------------------- | ------------------------------------ |
| document_symbols     | file_path              | `document_symbol`                    |
| find_definition      | file_path, symbol_name | `definition_by_name`                 |
| find_references      | file_path, symbol_name | `references_by_name`                 |
| find_implementation  | file_path, symbol_name | `implementation_by_name`             |
| find_type_definition | file_path, symbol_name | `type_definition_by_name`            |
| find_callers         | file_path, symbol_name | `incoming_calls_by_name`             |
| find_callees         | file_path, symbol_name | `outgoing_calls_by_name`             |
| hover                | file_path, line        | `hover`                              |
| diagnostic           | file_path              | `diagnostic`                         |
| code_action          | file_path, symbol_name | `code_action_by_name`                |
| workspace_symbols    | query                  | `workspace_symbol`                   |

### Parameters and Inference

- When `language` is omitted, it is inferred by extension via `LSPConfigReader.detect_language()`;
- When `project_path` is omitted, the directory containing `file_path` is used;
- `file_path` supports relative paths (relative to the current working directory) and absolute paths, normalized internally with `os.path.abspath`;
- The parameter design is oriented toward LLMs: it prioritizes `symbol_name` and avoids exact line/column numbers (only `hover` needs `line`).

### Return Format

Unified as `{"success": bool, "stdout": str, "stderr": str}`, where `stdout` is JSON text:

```json
{
  "action": "find_definition",
  "language": "python",
  "project_path": "/path/to/project",
  "file_path": "/path/to/project/src/main.py",
  "result": {
    "file_path": "...",
    "line": 43,
    "column": 5,
    "symbol_name": "..."
  }
}
```

### Asynchronous Bridging

`LSPDaemonClient` is a fully asynchronous interface, while the tool's `execute` is a synchronous method. In the implementation:

- If the current thread has no running event loop → call `asyncio.run()` directly;
- If the current thread already has a running event loop (such as inside the Web gateway) → start another thread to run `asyncio.run()`,
  avoiding `RuntimeError: This event loop is already running`.

### Degradation Behavior

The following situations all return `success=false` without throwing an exception or interrupting the Agent:

| Situation                                                                                                    | `stderr` content                                                                          |
| ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------- |
| Language cannot be recognized                                                                                | Prompts to explicitly specify with `language` and lists the currently supported languages |
| Language server not installed / daemon startup failure                                                       | The reason + the `install_hint` of the corresponding language                             |
| The language server does not support that LSP method (e.g. pylsp does not support `textDocument/diagnostic`) | The reason + `install_hint`                                                               |

### Boundaries with Other Tools

- Semantic queries (definition/references/implementation/diagnostics/fixes) → `lsp`;
- Plain-text search → `execute_script` + rg (LSP is not suitable for text matching);
- Call-chain/dependency-graph analysis → `symbol_dependency` (static parsing, no language server needed);
- Reading file contents → `read_code`.

## Related Source Code

| File                                                     | Responsibility                                                                                                    |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `src/haijunbot/haijunbot_lsp/config.py`                        | **Configuration reading layer (single source)**, built-in default languages, shared by haijunbot-lsp and the gateway |
| `src/haijunbot/haijunbot_tools/lsp.py`                         | **CodeAgent's LSP tool**, action dispatch, language inference, asynchronous bridging                              |
| `src/haijunbot/haijunbot_lsp/daemon_client.py`                 | LSP daemon client (fully asynchronous), reused by the tool layer                                                  |
| `src/haijunbot/haijunbot_web_gateway/lsp_registry.py`          | Converts the configuration into the gateway spec structure                                                        |
| `src/haijunbot/haijunbot_web_gateway/lsp_bridge.py`            | LSP framing codec, process pool, workspace root resolution                                                        |
| `src/haijunbot/haijunbot_web_gateway/app.py`                   | `GET /api/lsp/servers`, `WS /api/lsp/{server_id}`                                                                 |
| `src/haijunbot/haijunbot_service/frontend/src/lsp/registry.js` | Frontend fetches the manifest and builds the language/extension index                                             |
| `src/haijunbot/haijunbot_service/frontend/src/lsp/manager.js`  | Self-built lightweight LSP client, document synchronization, language feature provider                            |
