---
name: plugin-development
description: Triggered when there is a need to develop, write, or maintain a HaijunBot plugin. Triggered whenever the user mentions "plugin development", "writing a plugin", "developing a plugin", "built-in plugin", "new plugin", "haijunbot plugin", or "gh plugin". Not triggered: only installing/uninstalling an existing plugin (use the CLI command); developing a Track (use the track-development rule); developing an Agent (does not involve a plugin).
---

# HaijunBot Plugin Development Rule

This rule defines the standardized development process and conventions for HaijunBot plugins, ensuring that plugins conform to loading conventions, can be correctly registered and uninstalled, and are maintainable.

## Plugin System Overview

A HaijunBot plugin is a **directory-organized extensible unit**. Extension points (tools/rules/Agents/orchestration/frontend) are declared through `config.yaml`, and at runtime HaijunBot automatically loads and registers them. Plugin resources follow the **reversible effect** (Cordis philosophy): on load, they are explicitly registered in `PluginRegistry`; on unload, they are precisely revoked according to that registration, making register/unregister fully symmetric.

**Two kinds of plugins:**

- **Built-in plugins**: located in the source `builtin/plugins/<name>/`; `config.yaml` declares `builtin: true`; not copied, and cannot be uninstalled/upgraded.
- **External plugins**: located in `<data_dir>/plugins/<name>/` (default `~/.haijunbot/plugins/`); can be installed/upgraded/uninstalled.

## Plugin Directory Structure

```text
<plugin_name>/
├── config.yaml          # required: plugin configuration (name/version + extension point declarations)
├── README.md            # recommended: developer documentation
├── plugin/              # optional: plugin-private functionality (runs on the gateway, not exposed to the Agent)
├── rules/               # optional: rules (Markdown, with YAML front matter)
├── tools/               # optional: Agent tools (Python modules, class XxxTool)
├── agents/              # optional: Agent definitions (YAML)
├── orchestration/       # optional: orchestration pipelines (YAML)
└── frontend/            # optional: frontend extensions (pure browser ES modules, using window.Vue)
```

> **Tools come in two kinds, physically isolated**: `plugin/` is plugin-private functionality (runs on the gateway, invoked through the frontend proxy, **not exposed to the Agent**); `tools/` holds Agent tools (run in the agent process, invoked by the Agent). See "Tools (tools/)" and "Plugin-private functionality (plugin/)" below.

## config.yaml Field Specification

```yaml
---
name: my-plugin # required: the plugin's unique identifier (the directory name and the basis for tool/rule naming)
description: Plugin description. # required: functional description
version: 0.1.0 # version number (compared at install time)
license: MIT # open source license
builtin: true # built-in plugin marker (not written for external plugins)
# --- Extension points (paths use the {% raw %}{{plugin_dir}}{% endraw %} placeholder, automatically rendered by jinja2 at runtime into absolute plugin paths) ---
rules_load_dirs:
  - "{% raw %}{{plugin_dir}}{% endraw %}/rules"
tool_load_dirs:
  - "{% raw %}{{plugin_dir}}{% endraw %}/tools"
# agent_definition_dirs:
#   - "{% raw %}{{plugin_dir}}{% endraw %}/agents"
# --- Orchestration pipeline declarations (consumed with OrganizeAgents + --task-file) ---
orchestration:
  - name: "my-pipeline"
    description: "pipeline description"
    file: "{% raw %}{{plugin_dir}}{% endraw %}/orchestration/my_pipeline.yaml"
# --- Frontend extension declarations (optional) ---
# frontend:
#   admin_tabs:
#     - id: my-admin
#       title: "My admin"
#       entry: admin_tab.js
#   sidebar_views:
#     - id: my-view
#       title: "My view"
#       entry: sidebar_view.js
#   tool_panels:
#     - id: my-tool
#       title: "My tool"
#       entry: tool.js
# --- Dependency declarations (optional; three kinds: plugins/python/commands) ---
# dependencies:
#   plugins:
#     - name: other-plugin
#       version: ">=1.0.0"
#   python:
#     requests: ">=2.0"
#   commands:
#     - git
# --- Custom capability list (optional, for frontend display) ---
# capabilities:
#   - name: "event hook xxx"
#     description: "describes this capability"
---
```

**Field key points:**

- `{% raw %}{{plugin_dir}}{% endraw %}` is a jinja2 template variable, rendered at runtime into the plugin directory's absolute path (see `render_plugin_config_template`); **do not** hardcode absolute paths.
- Each `orchestration` item contains `name`/`description`/`file`; when the file path contains `plugins/<name>/`, the source plugin name is automatically inferred.
- The top-level `capabilities` field is used to declare custom capabilities such as event hooks and @built-in commands, merged for display with the automatically inferred capabilities (rules/tools/agents/orchestration/frontend).
- The plugin config is read and rendered by `_load_plugin_configs` and `_deep_merge`-merged into the global configuration, so fields such as `rules_load_dirs`/`tool_load_dirs`/`replace_map` are consumed by `get_rules_load_dirs()`/`get_tool_load_dirs()`/`get_replace_map()`.
- **Private configuration isolation**: in the plugin config.yaml, **except for the extension point fields** (`tool_load_dirs`/`rules_load_dirs`/`agent_definition_dirs`/`orchestration`/`roles_dirs`/`before_tool_call_cb_dirs`/`after_tool_call_cb_dirs`/`before_model_call_cb_dirs`/`summary_cb_dirs`/`builtin_input_handler_dirs`/`replace_map`), the remaining fields (`name`/`description`/`version`/`builtin`/`license`/`dependencies`/`capabilities`/`frontend`/custom business fields) are isolated into the `plugin_configs.<plugin_name>` dedicated configuration item in the global configuration, **without polluting the global configuration's top level, and same-named private fields across multiple plugins do not overwrite each other**. Plugins can read their own private configuration via `get_plugin_config(plugin_name)` / `get_all_plugin_configs()` (`haijunbot.haijunbot_utils.config`).

## Extension Point Development Conventions

### 1. Tools (tools/)

Tool files are Python modules. **The class `name` must equal the file name stem** (otherwise the registry does not load it).

```python
class MyPluginTool:
    name = "my_plugin_tool"          # must equal the file name stem
    description = "tool description"
    parameters = {
        "type": "object",
        "properties": {"input": {"type": "string", "description": "input"}},
        "required": ["input"],
    }

    @staticmethod
    def check() -> bool:
        """Whether the tool is usable (always returns True when there are no external dependencies)."""
        return True

    def execute(self, args: dict) -> dict:
        """Returns {"success": bool, "stdout": str, "stderr": str}."""
        try:
            # implementation logic
            return {"success": True, "stdout": "...", "stderr": ""}
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": f"execution error: {e}"}
```

**Key points:**

- The class must have the `name`/`description`/`parameters`/`execute` attributes, and only when `item.name == file name stem` is it loaded by `register_tool_by_file`.
- Optional `protocol_version` (default "1.0") and `interactive` (serial execution required when True).
- When the tool path contains `plugins/<name>/`, `_infer_source_plugin` automatically infers the source plugin name and registers it in `PluginRegistry`, revoking it precisely on uninstall.
- **Runtime environment**: Agent tools run in the **agent process**, loaded by ToolRegistry, invoked by the Agent. Tool classes should preferably be thin wrappers around private functionality (see the next section).

### 2. Plugin-private functionality (plugin/, optional)

Functionality the plugin uses for itself (such as API wrappers, token management, pure business functions) goes in the `plugin/` directory (e.g., `plugin/api.py`).

**Key constraints:**

- `plugin/` is **not declared in `tool_load_dirs`**, so it is not loaded by ToolRegistry; **the Agent cannot see or call it**.
- **Runtime environment**: plugin-private functionality runs on the **gateway** (the master process), invoked through the frontend proxy.
- The gateway frontend proxy calls private functionality via `POST /api/plugins/{node_id}/function-call` (request body `{plugin, function, arguments}`), and **only allows** invoking functions in the module's `PUBLIC_FUNCTIONS` whitelist.
- Agent tools (tools/) are **thin wrappers** around the private functionality: they only parse parameters, invoke the private functionality, and format the return as `{"success","stdout","stderr"}`.

**api.py conventions:**

- Each function is a pure function returning a dict: `{"success": bool, "data": ... / "message": ... / "error": ...}`.
- At the end of the module, define the `PUBLIC_FUNCTIONS: list[str]` whitelist; the gateway only allows invoking whitelisted functions (to prevent arbitrary functions from being called).
- Tool classes load `plugin/api.py` by file path via importlib (because `plugin/` is not in sys.path), using `importlib.util.spec_from_file_location` to load and cache it, for the thin-wrapper tool classes to call.

### 3. Rules (rules/)

Markdown files, beginning with YAML front matter:

```yaml
---
name: my_plugin_rule
description: When this rule is triggered (clearly list the trigger keywords/scenarios).
---
```

Rules are automatically discovered and loaded by the Agent to constrain behavior in the relevant scenarios.

### 4. Agent definitions (agents/, optional)

YAML format; the `agent_definition_dirs` must be enabled in config.yaml:

```yaml
name: my_agent
description: Agent role description.
system_prompt: |
  You are the dedicated Agent of the my-plugin plugin.
```

### 5. Orchestration (orchestration/, optional)

YAML orchestration pipelines, consumed by `OrganizeAgents` with `hca -n --task-file`. Reference the example formats under `builtin/agent_orchestration/`.

### 6. Frontend extensions (frontend/, optional)

Frontend JS is a **pure browser ES module**: render with `window.Vue`, export a default component, and **do not `import 'vue'`**. Declare `admin_tabs`/`sidebar_views`/`tool_panels` in the `frontend` field of config.yaml; each item contains `id`/`title`/`entry` (entry is a JS file name, relative to the plugin's frontend directory).

The frontend dynamically loads plugin JS via `GET /api/plugins/{node_id}/{name}/frontend/{path}` (the backend returns content wrapped in JSON), loading it as a Vue component via a Blob URL `import()`. The plugin JS should be **self-contained in a single file** (not referencing relative-path resources), otherwise the Blob module cannot be resolved.

## Development Process

1. **Generate the scaffold**: `haijunbot --new-plugin <name>` (optionally add `--plugin-output-dir <dir>`), generating a complete skeleton that conforms to the loading conventions (config.yaml/README/rules/tools/agents/orchestration/frontend).
2. **Implement extension points as needed**: edit config.yaml to declare extension points, and implement tools/rules/Agents/orchestration/frontend in the corresponding directories.
3. **Local verification**:
   - The tool class name matches the file name stem; `execute` returns `{"success","stdout","stderr"}`.
   - Rules have YAML front matter (name/description).
   - config.yaml can be parsed by yaml, and the `{% raw %}{{plugin_dir}}{% endraw %}` placeholder is correct.
   - Use `py_compile` or an actual import to verify the tool module syntax is correct.
4. **Install**: `haijunbot --install-plugin <path>` (path can be a directory, tar/tar.gz/tgz/zip, or an http(s) URL). Installing with a URL records the source for `--upgrade-plugin` upgrades.
5. **View**: `haijunbot --list-plugins` lists installed plugins.
6. **Uninstall**: `haijunbot --uninstall-plugin <name>` (built-in plugins cannot be uninstalled; it will be rejected).

## Dependency Conventions

The `dependencies` field in config.yaml supports three kinds (see `_check_dependencies`):

- **plugins**: other HaijunBot plugins, containing `name`/`version`, optional `url`/`tag`/`branch`. Plugin dependencies with a url are automatically downloaded and installed when not present.
- **python**: Python packages, as a dict `{package name: version constraint}` or a list `[{"name":..., "version":...}]`.
- **commands**: system commands, as a list `["git", "jq"]` or a dict.

When dependencies are unsatisfied, installation is rejected; plugin dependencies with a url are attempted to be installed automatically.

## Built-in Plugin Conventions

- Located in `builtin/plugins/<name>/`; `config.yaml` declares `builtin: true`.
- Built-in plugins **cannot be uninstalled or upgraded** (`uninstall_plugin` defensively rejects it).
- If a plugin name exists in both the built-in directory and the data directory, the built-in one takes precedence (the data directory copy is skipped).

## Verification Checklist

- [ ] config.yaml exists and contains `name`/`description`/`version`
- [ ] Extension point paths use the `{% raw %}{{plugin_dir}}{% endraw %}` placeholder, without hardcoded absolute paths
- [ ] The tool class `name` equals the file name stem, implementing `check()` and `execute()`
- [ ] Rule files have YAML front matter (name/description)
- [ ] Frontend JS uses `window.Vue`, does not `import 'vue'`, is self-contained in a single file
- [ ] Dependency declarations are in the correct format (plugins/python/commands)
- [ ] `py_compile` passes and config.yaml is parseable
- [ ] Installation succeeded: `haijunbot --install-plugin <path>`
- [ ] Uninstall is reversible: `haijunbot --uninstall-plugin <name>` can revoke the registered resources

## Related Code Locations

- Plugin registration tracking: `src/haijunbot/haijunbot_tools/plugin_registry.py` (PluginRegistry, the source of truth for the reversible effect)
- Tool loading: `src/haijunbot/haijunbot_tools/registry.py` (`register_tool_by_file`/`_infer_source_plugin`)
- Plugin scaffold/install/uninstall/list: `src/haijunbot/haijunbot_agent/utils.py` (`scaffold_plugin`/`install_plugin`/`uninstall_plugin`/`list_plugins`/`list_plugins_info`)
- Plugin config merging: `src/haijunbot/haijunbot_utils/utils.py` (`_load_plugin_configs`)
- Template rendering: `src/haijunbot/haijunbot_utils/template_utils.py` (`render_plugin_config_template`)
- Extension point directory reading: `src/haijunbot/haijunbot_utils/config.py` (`get_tool_load_dirs`/`get_rules_load_dirs`/`get_agent_definition_dirs`/`get_plugin_orchestrations`)
- Frontend extension loading: `src/haijunbot/haijunbot_service/frontend/src/pluginExtensions.js`
- CLI commands: `src/haijunbot/haijunbot_agent/haijunbot.py`
