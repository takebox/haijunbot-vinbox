# HaijunBot Plugin Development Guide

> This document is aimed at **plugin authors and open-source contributors**, introducing how to develop, package, publish, and distribute HaijunBot plugin packages.
> If you just want to install/use an existing plugin, see the plugin chapter of the [Usage Guide](haijunbot_book/4.Usage_Guide.md).
>
> Related design documents: [Plugin System Tool Architecture](design/plugin-tool-architecture.md), [Frontend Plugin Extension Design](design/frontend-plugin-extension-design.md).

## 1. What Is a Plugin

HaijunBot adopts a **kernel + plugin package** architecture: any configuration supported by `config.yaml` (tools / rules / Agent definitions / orchestration / frontend extensions / callbacks) can be packaged as a plugin, which is automatically discovered and injected after installation, **with no need to modify the kernel or redeploy**.

A plugin is an **extensible unit organized by directory**, automatically loaded and registered by HaijunBot at runtime. Plugin resources follow a **reversible effect**: they are explicitly registered into the `PluginRegistry` when loaded, and precisely rolled back according to the registration when unloaded; register / unregister are fully symmetric.

**Two types of plugins:**

| Type | Location | Characteristics |
| --- | --- | --- |
| Built-in plugin | Source `builtin/plugins/<name>/` | `config.yaml` declares `builtin: true`; not copied, cannot be uninstalled/upgraded |
| External plugin | `<data_dir>/plugins/<name>/` (default `~/.haijunbot/plugins/`) | Can be installed / upgraded / uninstalled |

## 2. Quick Start

### 1. Generate the Scaffold

```bash
haijunbot --new-plugin my-plugin --plugin-output-dir .
```

Generates a complete skeleton conforming to the loading conventions:

```text
my-plugin/
├── config.yaml          # Required: plugin configuration (name/version + extension point declarations)
├── README.md            # Recommended: developer documentation
├── plugin/              # Optional: plugin-private functionality (runs on the gateway, not exposed to the Agent)
├── rules/               # Optional: rules (Markdown, with YAML front matter)
├── tools/               # Optional: Agent tools (Python modules, class XxxTool)
├── agents/              # Optional: Agent definitions (YAML)
├── orchestration/       # Optional: orchestration pipelines (YAML)
└── frontend/            # Optional: frontend extensions (pure-browser ES modules, using window.Vue)
```

### 2. Implement Extension Points as Needed

Edit `config.yaml` to declare extension points, and implement rules / tools / Agents / orchestration / frontend in the corresponding directories.

### 3. Local Verification

```bash
# Tool module syntax check
python -m py_compile my-plugin/tools/my_plugin_tool.py

# Install locally for verification (directory install)
haijunbot --install-plugin ./my-plugin

# View installed plugins
haijunbot --list-plugins
```

## 3. config.yaml Field Specification

```yaml
---
name: my-plugin            # Required: unique plugin identifier (basis for the directory name and tool/rule naming)
description: Plugin description.     # Required: feature description
version: 0.1.0             # Version number (used for version comparison during installation)
license: MIT               # Open-source license
builtin: true              # Built-in plugin flag (not written for external plugins)
# --- Extension points (paths use the {{plugin_dir}} placeholder, automatically rendered by jinja2 at runtime to the plugin's absolute path) ---
rules_load_dirs:
  - "{{plugin_dir}}/rules"
tool_load_dirs:
  - "{{plugin_dir}}/tools"
# agent_definition_dirs:
#   - "{{plugin_dir}}/agents"
# --- Orchestration pipeline declarations ---
orchestration:
  - name: "my-pipeline"
    description: "Pipeline description"
    file: "{{plugin_dir}}/orchestration/my_pipeline.yaml"
# --- Frontend extension declarations (optional) ---
# frontend:
#   admin_tabs:
#     - id: my-admin
#       title: "My Admin"
#       entry: admin_tab.js
#   sidebar_views:
#     - id: my-view
#       title: "My View"
#       entry: sidebar_view.js
#   tool_panels:
#     - id: my-tool
#       title: "My Tool"
#       entry: tool.js
# --- Dependency declarations (optional; three types: plugins/python/commands) ---
# dependencies:
#   plugins:
#     - name: other-plugin
#       version: ">=1.0.0"
#   python:
#     requests: ">=2.0"
#   commands:
#     - git
---
```

**Key points:**

- `{{plugin_dir}}` is a jinja2 template variable, rendered at runtime to the plugin directory's absolute path (see `render_plugin_config_template`); **do not** hard-code absolute paths.
- The remaining fields other than the extension-point fields (`name`/`description`/`version`/`builtin`/`license`/`dependencies`/`capabilities`/`frontend`/custom business fields) are isolated into `plugin_configs.<plugin_name>` in the global configuration, **without polluting the top level of the global configuration, and private fields with the same name across multiple plugins do not overwrite one another**. A plugin can read its own private configuration via `get_plugin_config(plugin_name)`.

## 4. Extension Point Development Specification

### 1. Tools (tools/)

Tool files are Python modules. **The class's `name` must equal the file name stem** (otherwise the registry will not load it).

```python
class MyPluginTool:
    name = "my_plugin_tool"          # Must equal the file name stem
    description = "Tool description"
    parameters = {
        "type": "object",
        "properties": {"input": {"type": "string", "description": "Input"}},
        "required": ["input"],
    }

    @staticmethod
    def check() -> bool:
        """Whether the tool is available (always returns True when there are no external dependencies)."""
        return True

    def execute(self, args: dict) -> dict:
        """Returns {"success": bool, "stdout": str, "stderr": str}."""
        try:
            return {"success": True, "stdout": "...", "stderr": ""}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": f"Execution exception: {e}"}
```

- Tools run in the **agent process**, are loaded by the ToolRegistry, and are called by the Agent.
- Optional `protocol_version` (default `"1.0"`), `interactive` (when True, requires serial execution).

### 2. Plugin-Private Functionality (plugin/, optional)

Implementations of functionality used by the plugin itself (API wrappers, token management, pure business functions) go in the `plugin/` directory.

- `plugin/` is **not declared in `tool_load_dirs`**, so it is not loaded by the ToolRegistry, and **the Agent cannot see or call it**.
- It runs on the **gateway** (master process) and is called by the frontend proxy via `POST /api/plugins/{node_id}/function-call`.
- Each function in `api.py` is a pure function that returns `{"success": bool, "data"/"message"/"error": ...}`; at the end of the module, a `PUBLIC_FUNCTIONS: list[str]` whitelist is defined, and the gateway **only allows** calling functions on the whitelist.
- Agent tools (`tools/`) should be **thin wrappers** around private functionality: only parsing arguments, calling the private functionality, and formatting the return value.

### 3. Rules (rules/)

Markdown files with YAML front matter at the beginning:

```yaml
---
name: my_plugin_rule
description: When to trigger this rule (clearly list the trigger keywords/scenarios).
---
```

Rules are automatically discovered and loaded by the Agent and are used to constrain behavior in relevant scenarios.

### 4. Agent Definitions (agents/, optional)

YAML format; you need to enable `agent_definition_dirs` in `config.yaml`:

```yaml
name: my_agent
description: Agent role description.
system_prompt: |
  You are the dedicated Agent of the my-plugin plugin.
```

### 5. Orchestration (orchestration/, optional)

YAML orchestration pipelines, consumed together with `OrganizeAgents` and `hca -n --task-file`. Refer to the example format under `builtin/agent_orchestration/`.

### 6. Frontend Extensions (frontend/, optional)

Frontend JS is a **pure-browser ES module**: it renders with `window.Vue` and exports a default component; **do not `import 'vue'`**. Declare `admin_tabs`/`sidebar_views`/`tool_panels` in the `frontend` field of `config.yaml`, each item containing `id`/`title`/`entry` (entry is the JS file name, relative to the plugin's frontend directory).

The frontend dynamically loads the plugin JS via `GET /api/plugins/{node_id}/{name}/frontend/{path}`, loading it as a Vue component via Blob URL `import()`. Plugin JS should be **single-file and self-contained** (not referencing relative-path resources), otherwise the Blob module cannot be resolved.

#### 6.1 The Three Extension Points

| Extension Point | Render Location | Description |
|--------|----------|------|
| `admin_tabs` | Admin panel tab | Adds a tab in the admin panel (AdminPanel) |
| `sidebar_views` | Workspace sidebar | Adds an entry in the activity bar; the view name is `plugin:<id>` |
| `tool_panels` | Workspace sidebar | Adds an entry in the activity bar; the view name is `plugin-tool:<id>`, independent of `sidebar_views` |

#### 6.2 Unified props (automatically injected by the host)

When rendering a plugin component, the host automatically injects the following props (the plugin component receives them by declaring them in `props`; undeclared ones are ignored):

```js
export default {
  name: 'MyView',
  props: {
    workingDir: String,   // Current working directory
    agentInfo: Object,    // Info about the current active Agent { agentId, agentName, workingDir }, or null
    userInfo: Object,     // Info about the current logged-in user { user_id, username, display_name, is_admin }, or null
    nodes: Array,         // Node list [{ node_id, status, ... }]
    gatewayUrl: String,   // Gateway address
    fetchWithAuth: Function, // Authenticated fetch(url, options)
    getHttpProtocol: Function, // () => 'http' | 'https'
    showToast: Function,  // (message, type) show a toast
  },
  render(h) {
    return h('div', {}, 'Plugin content');
  },
};
```

#### 6.3 The window.__haijunbot* API Family

Plugin components can also access host capabilities through the global `window.__haijunbot*` APIs (without declaring props):

| API | Signature | Description |
|------|------|------|
| `__haijunbotFetch` | `(url, options) => Promise<Response>` | Authenticated fetch that automatically carries the token |
| `__haijunbotSendToActiveAgent` | `(text, options) => {success, agentId}` | Sends a prompt to the current active Agent |
| `__haijunbotGetActiveAgentInfo` | `() => {agentId, agentName, workingDir} \| null` | Gets info about the current active Agent |
| `__haijunbotCreateAgentForTask` | `(options) => Promise<{success, agentId}>` | Creates a new Agent to handle a task |
| `__haijunbotPickDirectory` | `() => Promise<string \| null>` | Opens the directory picker dialog |
| `__haijunbotGetUserInfo` | `() => userInfo \| null` | Gets info about the current logged-in user |
| `__haijunbotGetNodes` | `() => Array` | Gets the node list (a copy of the array) |
| `__haijunbotShowToast` | `(message, type='success')` | Shows a toast notification |
| `__haijunbotSwitchSidebarView` | `(view) => {success}` | Switches the workspace sidebar view (built-in or `plugin:<id>`/`plugin-tool:<id>`) |
| `__haijunbotOpenPanel` | `(kind) => {success}` | Opens a panel/navigation (admin/settings/workspace/git/plugins/topology/docs) |
| `__haijunbotGetGatewayInfo` | `() => {host, port, protocol}` | Gets info about the current gateway |

#### 6.4 Event Subscription

Plugins can subscribe to host events via `window.__haijunbotOn(event, handler)`, which returns an unsubscribe function; `window.__haijunbotOff(event, handler)` unsubscribes (if handler is omitted, all subscriptions for that event are cleared).

```js
const off = window.__haijunbotOn('agent_changed', (payload) => {
  // payload: { agentId, agentName, workingDir }, or null
  console.log('Current Agent changed', payload);
});
// Clean up when the component is unmounted
// off();
```

| Event | payload | Trigger Timing |
|------|---------|----------|
| `agent_changed` | `{agentId, agentName, workingDir} \| null` | The current active Agent changes |
| `token_changed` | `{token}` | The token changes (null on logout) |
| `user_changed` | `{userInfo} \| null` | The current user info changes |
| `nodes_changed` | `{nodes}` | The node list changes |

## 5. Version Management

### Semantic Versioning

The `version` field of `config.yaml` uses [semantic versioning](https://semver.org/lang/zh-CN/) (e.g. `1.2.3`); version comparison is performed by `packaging.version.Version` (see `_compare_versions`).

### Override Rules

When installing to an existing plugin directory, whether to override is decided by version comparison:

| Scenario | Behavior |
| --- | --- |
| New version > installed version | Overrides installation |
| New version == installed version | Overrides installation |
| New version < installed version | **Refuses installation** |
| Either side has no version number | Allows override (compatible with older-format plugins) |
| `--install-plugin-force` | Ignores version comparison and forcibly overrides |

### Dependency Version Constraints

Version constraints can be declared in `dependencies` (see `_check_version_constraint`):

```text
"1.2.0"            Exact version
">=1.2.0"          Greater than or equal to
">1.2.0"           Greater than
"<=1.2.0"          Less than or equal to
"<1.2.0"           Less than
"==1.2.0"          Exactly equal to
"*"                Any version
">=1.0.0,<2.0.0"   Range (comma-separated; all must be satisfied)
```

## 6. Dependency Declarations

The `dependencies` field of `config.yaml` supports three types (see `_check_dependencies`):

- **plugins**: other HaijunBot plugins, containing `name`/`version`/optional `url`/`tag`/`branch`. Plugin dependencies with a `url` are **automatically downloaded and installed** when not installed.
- **python**: Python packages, as a dict `{package name: version constraint}` or a list `[{"name":..., "version":...}]`.
- **commands**: system commands, as a list `["git", "jq"]` or a dict.

Installation is refused when dependencies are not satisfied; plugin dependencies with a `url` will attempt automatic installation (including circular dependency detection).

## 7. Publishing Process

### 1. Packaging

Package the plugin directory as an archive (supporting `.tar` / `.tar.gz` / `.tgz` / `.zip`). **The archive can directly be the plugin directory, or contain a single plugin directory** (installation automatically identifies the directory containing `config.yaml`):

```bash
# Recommended: package the plugin directory itself; after extraction it is my-plugin/
tar -czf my-plugin-0.1.0.tar.gz -C . my-plugin
```

> Before packaging, make sure the directory does not contain irrelevant files such as `__pycache__` and `.git`.

### 2. Hosting and Distribution

Host the archive at a publicly accessible URL; common methods:

- **GitHub Release asset**: `https://github.com/<owner>/<repo>/releases/download/<tag>/my-plugin-0.1.0.tar.gz`
- **GitHub repository archive**: `https://github.com/<owner>/<repo>/archive/refs/tags/<tag>.tar.gz` (triggered by tag)
- Any downloadable http(s) direct link

### 3. Distribution Mechanism (records the source on installation)

When a user installs via a URL, HaijunBot writes the source URL into the `.source` file in the plugin directory for later upgrades (see `install_plugin` / `upgrade_plugin`):

```bash
haijunbot --install-plugin https://github.com/<owner>/<repo>/releases/download/v0.1.0/my-plugin-0.1.0.tar.gz
```

Afterward, the user can upgrade to the latest version from that source with one command:

```bash
haijunbot --upgrade-plugin my-plugin
```

> **Tip**: if you want the upgrade to take effect, when releasing a new version you should update the content pointed to by the same source URL (or keep the URL always pointing to latest).

## 8. Installation and Uninstallation (User Perspective)

| Command | Description |
| --- | --- |
| `haijunbot --install-plugin <path or URL>` | Installs a plugin: directory, `.tar`/`.tar.gz`/`.tgz`/`.zip`, or http(s) URL |
| `haijunbot --install-plugin-force <path or URL>` | Forcibly overrides an installed plugin (ignores version comparison) |
| `haijunbot --upgrade-plugin <name>` | Upgrade: re-download the latest version from the recorded source URL of the plugin (only for plugins installed via URL) |
| `haijunbot --uninstall-plugin <name>` | Uninstalls a plugin (built-in plugins cannot be uninstalled; it will refuse) |
| `haijunbot --list-plugins` | Lists all installed plugins |

- The plugin name is taken from the `name` field in `config.yaml`; if absent, the directory name/file name is used.
- Uninstallation follows the reversible effect: it revokes the resources such as tools/rules registered by the plugin.

## 9. Contribution Process (Open-source Collaboration)

You are welcome to contribute your plugin to the community. Follow the standard Fork & Pull Request workflow (see [Contributing](haijunbot_book/7.Contributing.md) and the repository root `CONTRIBUTING.md` for details):

1. **Fork** this repository and create a feature branch (e.g. `feat/plugin-<name>`); **do not commit directly to `main`**:

   ```bash
   gh repo fork takebox/HaijunBot --clone   # fork and clone; the fork becomes origin and the original repository becomes upstream
   cd HaijunBot
   git checkout -b feat/plugin-<name>
   ```

2. Add/modify the plugin on the branch (recommended to place it in `builtin/plugins/<name>/` or a separate plugin repository).
3. After local verification passes, commit; the commit message follows the convention (`feat:` / `fix:` / `docs:` etc.).
4. Push the branch and create a Pull Request; the description must include: background, change list, and verification method:

   ```bash
   git push -u origin feat/plugin-<name>
   gh pr create --repo takebox/HaijunBot --base main \
     --head <your-username>:feat/plugin-<name> \
     --title "feat(plugin): add <name> plugin" --body-file <description file>
   ```

5. If it resolves an Issue, link it in the PR description with `Closes #<number>`.
6. Wait for the maintainer to review and merge.

> **Keep your fork in sync**: when upstream has new commits, you can sync your fork with upstream using `gh repo sync <your-username>/HaijunBot`.

## 10. Verification Checklist

- [ ] `config.yaml` exists and contains `name`/`description`/`version`
- [ ] Extension-point paths use the `{{plugin_dir}}` placeholder and do not hard-code absolute paths
- [ ] The tool class `name` equals the file name stem and implements `check()` and `execute()`
- [ ] Rule files have YAML front matter (`name`/`description`)
- [ ] Frontend JS uses `window.Vue`, does not `import 'vue'`, and is single-file and self-contained
- [ ] `plugin/api.py` defines the `PUBLIC_FUNCTIONS` whitelist (if using private functionality)
- [ ] The dependency declaration format is correct (plugins/python/commands)
- [ ] `py_compile` passes and `config.yaml` can be parsed by yaml
- [ ] Installation succeeds: `haijunbot --install-plugin <path>`
- [ ] Uninstallation is reversible: `haijunbot --uninstall-plugin <name>` can revoke the registered resources

## Related Code Locations

- Plugin registration tracking: `src/haijunbot/haijunbot_tools/plugin_registry.py` (PluginRegistry, the source of truth for the reversible effect)
- Tool loading: `src/haijunbot/haijunbot_tools/registry.py` (`register_tool_by_file` / `_infer_source_plugin`)
- Plugin scaffolding/installation/uninstallation/listing/upgrading: `src/haijunbot/haijunbot_agent/utils.py` (`scaffold_plugin` / `install_plugin` / `uninstall_plugin` / `list_plugins` / `upgrade_plugin`)
- Plugin config merging: `src/haijunbot/haijunbot_utils/utils.py` (`_load_plugin_configs`)
- Template rendering: `src/haijunbot/haijunbot_utils/template_utils.py` (`render_plugin_config_template`)
- Extension-point directory reading: `src/haijunbot/haijunbot_utils/config.py`
- Frontend extension loading: `src/haijunbot/haijunbot_service/frontend/src/pluginExtensions.js`
- CLI commands: `src/haijunbot/haijunbot_agent/haijunbot.py`
