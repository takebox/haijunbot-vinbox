---
name: mcp-integration
description: Triggered when there is a need to integrate an MCP service or extend tool functionality. Triggered whenever the user mentions "MCP integration", "MCP service", "tool extension", or "protocol development". Not triggered: only using existing tools without involving MCP; only configuring the Agent without involving MCP; ordinary tool invocation.
---

# MCP Integration Rule

## Rule Introduction

This rule guides how to integrate MCP (Model Context Protocol) tools into HaijunBot through a configuration file.

## Workflow You Must Follow

### MCP Integration Flow (strictly follow)

1. **🔧 Configuration preparation stage**:
   - Determine the MCP server type and communication method
   - Prepare the MCP server runtime environment and dependencies
   - Plan the client naming and configuration structure

2. **⚙️ Configuration implementation stage**:
   - Add the MCP configuration in the `~/.haijunbot/config.yaml` file
   - Choose the correct client configuration format according to the server type
   - Validate the YAML syntax and configuration completeness

3. **🧪 Verification and testing stage**:
   - Restart HaijunBot to load the new configuration
   - Check the startup logs to confirm the configuration loaded successfully
   - Verify that the MCP tools are correctly registered and usable

4. **🔍 Troubleshooting stage**:
   - Analyze configuration errors and runtime issues
   - Perform targeted fixes according to the error messages
   - Verify feature completeness after the fix

## Principles You Must Follow

### Configuration Management Principle

- **Must**: MCP tool configuration should be placed in the `mcp` list in the `~/.haijunbot/config.yaml` file
- **Must**: each MCP client configuration is an independent list item
- **Forbidden**: directly modifying YAML files under the `~/.haijunbot/mcp/` directory (this method is deprecated)
- **Must**: the configuration file must specify the MCP client type
- **Must**: provide the required configuration parameters according to the client type

### Type Safety Principle

- **Must**: the stdio type should include a `command` field
- **Must**: the sse and streamable types should include a `base_url` field
- **Must**: use correct YAML syntax and format
- **Forbidden**: using undefined fields in the configuration

### Verification and Confirmation Principle

- **Must**: after configuration is complete, restart HaijunBot for verification
- **Must**: check the startup logs to confirm there are no configuration errors
- **Must**: verify that the MCP tools are correctly registered
- **Forbidden**: directly using MCP tools without verification

## Specific Requirements and Conventions

### 1. Configuration File Location Requirement (must follow)

**Location specification:**

- **Must**: MCP tool configuration should be placed in the `mcp` list in the `~/.haijunbot/config.yaml` file
- **Must**: each MCP client configuration is an independent list item
- **Forbidden**: directly modifying YAML files under the `~/.haijunbot/mcp/` directory (this method is deprecated)

### 2. Configuration Structure Requirement (must follow)

**Basic configuration format:**

Each MCP configuration item should contain the following fields:

```yaml
mcp:
  - type: "stdio" | "sse" | "streamable"  # type must be specified
    name: "custom name"                      # optional, defaults to "mcp"
    enable: true                             # optional, defaults to true
    # other type-specific parameters...
```

### 3. MCP Client Type Selection Requirement

Choose the appropriate client type according to how your MCP server is implemented:

#### 1. stdio type (standard input/output)

**Applicable scenarios:** command-line programs running locally that communicate via stdin/stdout

**Required parameters:**

- `type`: must be `"stdio"`
- `command`: the full command to start the MCP server

**Optional parameters:**

- `name`: MCP client name (used for the tool naming prefix)
- `args`: command argument list (array format)
- `env`: environment variables (object format)
- `enable`: whether to enable (default true)

**Configuration example:**

```yaml
mcp:
  - type: "stdio"
    name: "filesystem"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/path/to/allowed/directory"
    env:
      NODE_ENV: "production"
```

#### 2. sse type (Server-Sent Events)

**Applicable scenarios:** MCP servers communicating over the HTTP SSE protocol

**Required parameters:**

- `type`: must be `"sse"`
- `base_url`: the HTTP base URL of the MCP server

**Optional parameters:**

- `name`: MCP client name
- `enable`: whether to enable (default true)

**Configuration example:**

```yaml
mcp:
  - type: "sse"
    name: "remote-mcp"
    base_url: "https://example.com/mcp/sse"
```

#### 3. streamable type

**Applicable scenarios:** MCP servers that support streaming communication

**Required parameters:**

- `type`: must be `"streamable"`
- `base_url`: the HTTP base URL of the MCP server

**Optional parameters:**

- `name`: MCP client name
- `enable`: whether to enable (default true)

**Configuration example:**

```yaml
mcp:
  - type: "streamable"
    name: "streaming-server"
    base_url: "https://example.com/mcp/stream"
```

### Operation 2: Configuring multiple MCP clients

Multiple MCP clients can be configured in the `mcp` list:

```yaml
mcp:
  - type: "stdio"
    name: "filesystem"
    command: "npx"
    args:
      - "@modelcontextprotocol/server-filesystem"
      - "/home/user/documents"

  - type: "sse"
    name: "remote-tools"
    base_url: "https://api.example.com/mcp"

  - type: "stdio"
    name: "database"
    command: "python"
    args:
      - "-m"
      - "mcp_database_server"
    enable: false # temporarily disabled
```

### 4. Configuration Verification Requirement (must follow)

**Verification steps:**

1. **Must**: save the `~/.haijunbot/config.yaml` file
2. **Must**: restart HaijunBot to load the new configuration
3. **Must**: observe the startup logs to confirm the MCP tool loading status

**Success indicators:**

- **Must**: no `⚠️` configuration error warnings
- **Must**: no `⚠️` MCP tool loading failure warnings
- **Must**: no `⚠️` MCP tool registration failure warnings

**Tool naming rule:**

- **Must**: MCP tools are registered in the form `{name}.tool_call.{tool_name}`
- **Must**: resource-related tools are registered in the forms `{name}.resource.get_resource_list` and `{name}.resource.get_resource`

For example, configuring `name: "filesystem"` with the server providing the tool `read_file` results in the registered tool name `filesystem.tool_call.read_file`

## Practical Guidance

### Preparation before configuration

- **Must**: confirm the MCP server is correctly installed and usable
- **Must**: understand the MCP server's communication method (stdio, sse, streamable)
- **Must**: plan a reasonable client naming scheme to avoid conflicts with existing tools
- **Must**: prepare the dependencies and environment required for the MCP server to run

### Best practices during configuration

- **Recommended**: use meaningful client names for easy identification and management
- **Recommended**: add an `enable` field for each MCP client for easy temporary disabling
- **Recommended**: use absolute paths or confirm the command is in PATH to avoid path issues
- **Recommended**: configure a single MCP client first, verify success, then add more
- **Recommended**: keep a backup of the configuration file for rollback and recovery

### Multiple client configuration management

- **Must**: ensure each client configuration is an independent list item
- **Must**: identify each client with a unique name
- **Recommended**: group and name clients by function or purpose
- **Recommended**: use comments to explain each client's purpose and configuration

### Troubleshooting approach

1. **Configuration loading issue**: check the YAML syntax, field completeness, and type correctness
2. **Server startup issue**: verify command availability, permissions, and dependency completeness
3. **Network connection issue**: check URL accessibility, network connectivity, and firewall settings
4. **Tool registration issue**: confirm the naming convention, tool usability, and parameter correctness

## Common Issue Troubleshooting

### Issue 1: Configuration loading failed

**Symptom:** `⚠️` configuration error warning

**Possible causes:**

- The MCP server is not installed or is not in PATH
- The command path is wrong
- Insufficient permissions

**Solutions:**

- Confirm the MCP server is correctly installed
- Use an absolute path or confirm the command is in PATH
- Check whether the command can be executed manually in the terminal

### Issue 2: Failed to get the tool list

**Symptom:** `⚠️` MCP tool loading failure warning

**Possible causes:**

- The MCP server did not start normally
- The base_url configuration is wrong (sse/streamable)
- Network connection issue

**Solutions:**

- Check the MCP server logs
- Verify the base_url accessibility
- Test the network connection

### Issue 3: Tool execution is unresponsive

**Symptom:** the tool registers successfully but is unresponsive or times out during execution

**Possible causes:**

- The MCP server takes too long to process requests
- Incorrect parameter passing
- Server-side exception

**Solutions:**

- Check the MCP server logs
- Verify the tool parameter format
- Increase the server timeout configuration (if supported)

### Issue 4: Deprecated file method warning

**Symptom:** `⚠️` deprecated file method warning

**Solutions:**

- Migrate the YAML configurations under the `~/.haijunbot/mcp/` directory to the `mcp` list in `~/.haijunbot/config.yaml`
- Delete or rename the configuration files in the `~/.haijunbot/mcp/` directory

## Execution Checklist

### Must confirm before configuration is complete

- [ ] The MCP server type and communication method have been confirmed
- [ ] The MCP server runtime environment and dependencies have been prepared
- [ ] A reasonable client naming scheme has been planned

### Must confirm during configuration

- [ ] The configuration has been added to the `mcp` list in `~/.haijunbot/config.yaml`
- [ ] Every MCP configuration contains a `type` field
- [ ] The stdio type contains a `command` field
- [ ] The sse/streamable type contains a `base_url` field
- [ ] The YAML format is correct (indentation, quotes, etc.)
- [ ] The old configuration files in the `~/.haijunbot/mcp/` directory have been deleted or disabled

### Must confirm after configuration is complete

- [ ] HaijunBot has been restarted and the startup logs checked
- [ ] No configuration error warnings appeared
- [ ] The MCP tools are successfully registered (verifiable via the tool list)
- [ ] The MCP tools have been verified to work normally

## Related Resources

- Configuration management: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_utils/config.py`
- MCP registration implementation: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_tools/registry.py` (the register_mcp_tool_by_config method)
- MCP client implementation: `{{ haijunbot_src_dir }}/src/haijunbot/haijunbot_mcp/`
