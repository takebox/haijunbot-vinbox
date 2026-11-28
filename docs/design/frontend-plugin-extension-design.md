# Frontend Plugin Extension Design Plan (Plan 1 + Plan 2)

> Status: The administrator has confirmed the direction (manage by node + self-designed extension points aiming to cover everything + security not considered for now)
> Date: 2026-10-07
> Rollback point: `7a7506376e7d464cf62ea9e7230947783fdedf59`

## Background

The administrator approved "both Plan 1 and Plan 2 are to be done", and clarified:

1. **Plugin management is node-based** (each node has its own plugin set; management must be done per node)
2. **Extension points are designed by me, aiming to cover everything and be as complete as possible, with security not considered for now**

Prerequisite completed: plugin reversible effects (PluginRegistry, revokes tools/rules on uninstall).

## Current State Survey (verified facts)

**Backend plugin management functions** (`src/haijunbot/haijunbot_agent/utils.py`):

- `install_plugin(source_path, force, source_url, _installing_deps)` (:556)
- `list_plugins()` (:868, only prints to console, does not return structured data)
- `uninstall_plugin(plugin_name)` (:923, calls PluginRegistry.revoke_plugin before uninstall)
- `upgrade_plugin(plugin_name)` (:979)
- Plugin directory: `<data_dir>/plugins/<name>/` (each node has its own data_dir)

**Backend web_gateway (app.py)**:

- No plugin-related HTTP API
- Management endpoint pattern: `verify_token` + `_check_permission` + `{"success": True/False, "data": ...}`
- **Node proxy**: `node_http_proxy` (:4554) handles `/api/node/{node_id}/{path}`, currently supporting the `agent/` and `http_proxy/` prefixes
- **Node execution**: `node_exec` (:4398) executes commands on a specified node (directly if local / via `send_request_to_node` if remote)
- **Node protocol**: `node_protocol.py` defines message types; `node_manager.py` (:194-318) dispatches and handles them, with child nodes handling each request locally

**Frontend (src/haijunbot/haijunbot_service/frontend/)**:

- Single-page application, no vue-router, static output from vite build, served with `npm run preview`
- `AdminPanel.vue` (4 tabs: users/groups/system/config, `activeTab` + `switchTab`, :399)
- Sidebar views: agents/files/search/manage/timers/git/directory tree (`workspaceSidebarView` ref)
- `buildNodeHttpUrl` (App.vue:2428) generates `/api/node/{node_id}/{path}` to access any node
- `fetchWithAuth` (App.vue:2327) calls the backend with a Bearer token
- Testing: vitest + node test; build: vite build
- The frontend does not expose a global Vue; node_modules has `vue.global.js`

**Key mechanism**: `PrettyOutput` has a **Sink mechanism** (`add_sink`/`remove_sink`, output.py:873/879, `emit_output` broadcasts to all sinks). The API layer can register a custom sink to capture the output of functions such as install_plugin, without modifying those functions.

## Plan 1: Plugin Management UI (by node)

### Backend: New plugin management messages in the node protocol

**node_protocol.py** adds:

```python
PLUGIN_MANAGE_REQUEST = "plugin_manage_request"
PLUGIN_MANAGE_RESPONSE = "plugin_manage_response"
```

**node_manager.py** adds a branch to the dispatch logic, with child nodes handling plugin management operations locally:

- `_handle_plugin_manage_request(message)`: based on `action` (list/install/uninstall/upgrade), calls the corresponding function in `haijunbot_agent/utils.py` and returns structured JSON
- list → `list_plugins_info()` (new, returns structured data)
- install → `install_plugin(source, force)`, capturing output with a Sink
- uninstall → `uninstall_plugin(name)`
- upgrade → `upgrade_plugin(name)`

### Backend: master plugin management API (app.py)

**`node_http_proxy` extends the `plugins/` prefix**: forwards `/api/node/{node_id}/plugins/...` to the target node for execution.

**master local plugin management API** (`/api/plugins/...`, `verify_token` + `admin:plugins` permission):
| Method | Path | Function |
|------|------|------|
| GET | `/api/plugins?node_id=xxx` | List plugins on the specified node |
| POST | `/api/plugins/install?node_id=xxx` | Install `{source, force}` on the specified node |
| POST | `/api/plugins/{name}/uninstall?node_id=xxx` | Uninstall a plugin on the specified node |
| POST | `/api/plugins/{name}/upgrade?node_id=xxx` | Upgrade a plugin on the specified node |

`node_id` defaults to `master`. Locally, master calls the function directly; remotely, it forwards via `send_request_to_node(node_id, PLUGIN_MANAGE_REQUEST, ...)`.

**`haijunbot_agent/utils.py` adds `list_plugins_info() -> list[dict]`**: returns structured plugin info (name/description/version/dependencies/frontend), leaving the original `list_plugins()` unchanged.

### Frontend: AdminPanel adds a "Plugin Management" tab + node selector

- Adds a 5th tab "Plugin Management" (`activeTab === 'plugins'`)
- **Node selector**: lists all online nodes (including master); after selection, manage that node's plugins
- Functions: list/install (source + force)/uninstall (confirm + trigger revocation)/upgrade
- Uses `buildNodeHttpUrl` + `fetchWithAuth` to call the backend (with node_id)

## Plan 2: Plugin Extension Frontend (covering all extension points)

### Core Idea

The frontend is a static artifact built by vite, and plugins cannot participate in the build. Plugin frontend extensions use **runtime dynamic loading**:

- The plugin config.yaml declares `frontend` extension points
- The backend serves plugin frontend resources per node
- At startup, the frontend fetches the extension manifest, dynamically `import()`s the plugin JS, and renders it with Vue dynamic components

### Extension Point Types (aiming to cover everything)

The `frontend` field of a plugin's config.yaml declares a list of extension points, each with a `type`:

```yaml
name: my-plugin
version: 0.1.0
frontend:
  # 1. Add a new tab to the admin panel (AdminPanel)
  admin_tabs:
    - id: my-panel
      title: My Panel
      entry: frontend/my-panel.js
  # 2. Add a new view to the workspace sidebar
  sidebar_views:
    - id: my-view
      title: My View
      entry: frontend/my-view.js
  # 3. Tool panel extension
  tool_panels:
    - id: my-tool
      title: My Tool
      entry: frontend/my-tool.js
```

### Plugin Frontend JS Format

A pure browser ES module that **uses Vue through the global `window.Vue`** (does not import 'vue', avoiding npm module resolution), exporting a Vue component definition (using a render function, compatible with the runtime build):

```js
// frontend/my-panel.js
export default {
  name: "MyPanel",
  render(h) {
    return h("div", { class: "my-panel" }, "Plugin panel content");
  },
};
```

### Backend Changes

1. **`GET /api/plugins`** returns each plugin's `frontend` extension declaration (including node_id)
2. **`GET /api/plugins/{node_id}/{name}/frontend/{path}`**: serves plugin frontend resources (ES module JS) from the specified node, setting Content-Type `application/javascript`; for remote nodes, the file content is returned via `action=serve_frontend` of `PLUGIN_MANAGE_REQUEST` or via the node HTTP proxy

### Frontend Changes

1. **main.js exposes a global Vue**: `import * as Vue from 'vue'; window.Vue = Vue`
2. **Add an extension loader** (`pluginExtensions.js`):
   - At startup, call `GET /api/plugins` to fetch the extension manifest
   - For each extension, use `import(url)` to dynamically load the plugin JS (the url points to the backend serve endpoint)
   - Cache the loaded components
3. **AdminPanel renders dynamic tabs**: builds dynamic tabs from the extension manifest and renders them with `<component :is>`
4. **Sidebar dynamic views**: builds sidebar view entries from the extension manifest and renders plugin components

### Implemented (Issue #97, 2026-10)

Building on Plan 2, the host capabilities available to the plugin side are filled in:

1. **Unified `window.__haijunbot*` interface family** (App.vue, wrapped in try/catch, silently degrading on exceptions):
   - Info queries: `__haijunbotGetActiveAgentInfo` / `__haijunbotGetUserInfo` / `__haijunbotGetNodes` / `__haijunbotGetGatewayInfo`
   - UI control: `__haijunbotShowToast` / `__haijunbotSwitchSidebarView` / `__haijunbotOpenPanel`
   - Existing compatibility: `__haijunbotFetch` / `__haijunbotSendToActiveAgent` / `__haijunbotCreateAgentForTask` / `__haijunbotPickDirectory`
2. **Unified props injection**: when rendering, `sidebar_views` (App.vue:550) and `admin_tabs` (AdminPanel.vue:283) automatically inject `workingDir`/`agentInfo`/`userInfo`/`nodes`/`gatewayUrl`/`fetchWithAuth`/`getHttpProtocol`/`showToast` (admin_tabs does not include workingDir/agentInfo).
3. **tool_panels frontend rendering**: rendered as a workspace sidebar view (`plugin-tool:<id>`), with a new entry in the WorkspacePanel activity bar, independent of `sidebar_views` (`plugin:<id>`), using the `plugin-tool:` prefix for the component cache key to avoid conflicts.
4. **Event subscription mechanism**: `window.__haijunbotOn(event, handler)` (returns an unsubscribe function) / `window.__haijunbotOff(event, handler)`. The host emits at state changes: `agent_changed` / `token_changed` / `user_changed` / `nodes_changed`.

## File List Involved

**Backend**:

- `src/haijunbot/haijunbot_web_gateway/node_protocol.py`: adds 2 message types
- `src/haijunbot/haijunbot_web_gateway/node_manager.py`: adds `_handle_plugin_manage_request`
- `src/haijunbot/haijunbot_web_gateway/app.py`: adds plugin management API + node_http_proxy extends the plugins/ prefix
- `src/haijunbot/haijunbot_agent/utils.py`: adds `list_plugins_info()`

**Frontend**:

- `src/haijunbot/haijunbot_service/frontend/src/main.js`: exposes window.Vue
- `src/haijunbot/haijunbot_service/frontend/src/components/AdminPanel.vue`: adds the plugin management tab + dynamic plugin tabs
- `src/haijunbot/haijunbot_service/frontend/src/App.vue`: sidebar dynamic views
- Adds `src/haijunbot/haijunbot_service/frontend/src/pluginExtensions.js` (extension loader)

**Testing**:

- Backend: pytest covers the plugin management API + list_plugins_info + node protocol
- Frontend: vitest covers the extension loader + AdminPanel plugin tab + sidebar dynamic view

## Verification and Rollback

- Frontend: `npm run test:vitest` + `npm run test:node` + `vite build` all green
- Backend: `ruff check` + `ty` + relevant pytest
- Real install/uninstall isolated with `HAIJUNBOT_DATA_DIR`
- Rollback point: `7a7506376e7d464cf62ea9e7230947783fdedf59`
