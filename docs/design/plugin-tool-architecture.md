# Plugin System Tool Architecture Plan

## Background and Problem

In the HaijunBot plugin system, the responsibility of a plugin's "tools" is unclear, and there is a problem where two kinds of tools are conflated:

- **Used by the plugin itself**: the code a plugin needs to implement its functionality (such as the gh plugin's GitHub API wrapper and token management).
- **Used by the Agent**: tools exposed to the Agent (`class XxxTool`, with `name`/`description`/`parameters`/`execute`), letting the AI assistant act on the user's behalf.

Previously, when the gateway frontend proxied plugin functionality, it treated plugin functionality as "Agent tools" — loading ToolRegistry / PluginToolManager to execute `class XxxTool`, which caused **coupling between a plugin's internal functionality and Agent tools**, and could even expose the plugin's internal functionality to the Agent.

## Core Principle: Tools Are Split into Two Categories, Truly Isolated

A plugin's tools must be divided into two categories, and **physically isolated**:

### 1. Plugin Private Functionality (used by the plugin itself)

- The code a plugin needs to implement its functionality, placed in a **plugin private directory** (such as `plugin/`, `api/`, `internal/`).
- **Not declared in `tool_load_dirs`**, so it is not loaded by ToolRegistry, and **the Agent cannot see or call it**.
- The gateway frontend proxy calls these private functions through the plugin function channel.

### 2. Agent Tools (used by the Agent)

- Tools exposed to the Agent (`class XxxTool`), placed in the `tools/` directory and declared via `tool_load_dirs`.
- The tool class is a **thin wrapper** around the plugin's private functionality: it only parses arguments, calls the private function, and formats the return.

## Runtime Environment Separation (gateway / agent)

The two categories of tools **run in different process environments**, further strengthening isolation:

| Category                              | Runtime Environment          | Loading Mechanism                                        | Caller                                                  |
| ------------------------------------- | ---------------------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| Plugin private functionality (`plugin/`) | **gateway** (master process) | Dynamically loaded by gateway via importlib on demand  | Frontend proxy (`POST /api/plugins/{node_id}/function-call`) |
| Agent tools (`tools/`)                | **agent process**            | Loaded by ToolRegistry (`register_tool_by_file`)         | Agent (AI assistant)                                    |

- Plugin private functionality runs in the **gateway**, is invoked by the frontend proxy, and **is not exposed to the Agent**.
- Agent tools run in the **agent process**, are invoked by the Agent, and are thin wrappers around the private functionality.
- Therefore, the frontend proxy's calls to plugin functionality **do not go through the ToolRegistry / Agent tool mechanism**, and are completely isolated from the Agent side.

## Isolation Mechanism

- **The private functionality directory does not enter `tool_load_dirs`** → it is not loaded by ToolRegistry → it is invisible to the Agent.
- The **gateway frontend proxy**, through the plugin function endpoint, dynamically loads plugin private functionality and invokes it, **without going through the ToolRegistry / Agent tool mechanism**.
- Private functionality and Agent tools **do not share the same implementation**: the tool class only thinly wraps the private functionality, and the private functionality itself is not exposed to the Agent.

## gh Plugin Example

The gh plugin's functional logic (list PRs, list Issues, view, merge, comment, close) is carried by **two layers**:

- **Private functionality layer** (`plugin/`): pure function implementations, running in the gateway, invoked by the frontend sidebar proxy (not exposed to the Agent).
- **Agent side**: no longer provides `tools/` tool classes. Because code_agent's tool whitelist already includes `execute_script`, it can directly call the official GitHub `gh` CLI to perform all GitHub operations, with no extra tools needed.

```text
builtin/plugins/gh/
├── config.yaml          # declares rules_load_dirs + frontend (no tool_load_dirs)
├── plugin/              # plugin private functionality (not exposed to Agent, invoked by gateway frontend proxy)
│   ├── api.py           # pure functions: list_issues / list_prs / get_issue / get_pr
│   │                    #                merge_pr / comment / close_issue / resolve_repo
│   └── gh_common.py     # low-level GitHub API wrapper, token management
├── rules/               # usage rules (guide the Agent to use the gh CLI to complete operations)
└── frontend/            # frontend components (call plugin/api.py via gateway)
```

- `plugin/api.py` provides pure functions, **not exposed via `tool_load_dirs`**, invisible to the Agent.
- The gateway frontend proxy calls the pure functions in `plugin/api.py`, without going through ToolRegistry.
- When the Agent handles GitHub tasks, it directly executes `gh` CLI commands via `execute_script` (reusing the gh CLI login state).

## Implementation Points

1. Create a new plugin private functionality directory (such as `plugin/`) to carry the plugin's functionality implementation.
2. If Agent tools are needed, change the `tools/` tool classes into thin wrappers that call the private functionality; if the Agent can complete the work directly with the CLI, no `tools/` is needed.
3. The gateway provides a plugin function proxy endpoint that dynamically loads and invokes plugin private functionality.
4. Update the plugin development rules documentation to clarify the isolation specification for the two categories of tools.

## Related Code Locations

- Plugin private functionality: `builtin/plugins/<name>/plugin/` (new convention)
- Agent tools: `builtin/plugins/<name>/tools/`
- Tool loading: `src/haijunbot/haijunbot_tools/registry.py` (`register_tool_by_file`)
- Plugin registration tracking: `src/haijunbot/haijunbot_tools/plugin_registry.py` (PluginRegistry)
- gateway plugin function proxy: `src/haijunbot/haijunbot_web_gateway/app.py`
