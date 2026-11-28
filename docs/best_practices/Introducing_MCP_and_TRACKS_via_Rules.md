# Quickly Introducing MCP and TRACKS via Rules

## 1. Overview

### 1.1 What are MCP and TRACKS

- **MCP (Model Context Protocol)**: Model Context Protocol, which allows HaijunBot to communicate with external independent processes through a standard protocol and access the tools and resources provided by that process.
- **TRACKS**: HaijunBot's track system, which allows adding reusable track modules via a Git repository or local path.

### 1.2 Why Use Rules for Introduction

HaijunBot provides dedicated rules to guide the integration of MCP and TRACKS:

- **`mcp-integration.md`**: MCP integration rule, guiding how to configure and integrate MCP tools
- **`track-development.md`**: Track development rule, guiding how to add and manage tracks

Using these rules allows the Agent to automatically complete the integration work, reducing manual configuration errors and improving efficiency.

---

## 2. Quickly Introducing MCP

### 2.1 Introducing MCP Using Rules

The simplest way is to use the rules directly and let the Agent help you complete the MCP integration:

```bash
# Approach 1: Use the rule on the command line
hca --rule-names mcp-integration "Integrate the filesystem MCP server with path /home/user/documents"

# Approach 2: Use the rule in an interactive session
hca
> '<rule:mcp-integration>' Integrate the filesystem MCP server with path /home/user/documents
```

### 2.2 MCP Integration Process

The Agent will automatically perform the following steps according to the rule:

1. **Configuration preparation phase**
   - Determine the MCP server type and communication method
   - Prepare the MCP server runtime environment and dependencies
   - Plan the client naming and configuration structure

2. **Configuration writing phase**
   - Add the MCP configuration to the `~/.haijunbot/config.yaml` file
   - Choose the correct client configuration format according to the server type
   - Verify the YAML syntax and configuration completeness

3. **Verification and testing phase**
   - Restart HaijunBot to load the new configuration
   - Check the startup logs to confirm the configuration loaded successfully
   - Verify that the MCP tools are correctly registered and available

### 2.3 MCP Integration Examples

#### Example 1: Integrating a stdio-type MCP server

```bash
hca --rule-names mcp-integration "
Integrate the filesystem MCP server:
- Type: stdio
- Command: npx -y @modelcontextprotocol/server-filesystem
- Args: /home/user/documents
- Name: filesystem
"
```

The Agent will automatically generate the configuration:

```yaml
# ~/.haijunbot/config.yaml
mcp:
  - type: "stdio"
    name: "filesystem"
    command: "npx"
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/home/user/documents"
```

#### Example 2: Integrating an SSE-type MCP server

```bash
hca --rule-names mcp-integration "
Integrate a remote MCP server:
- Type: sse
- URL: https://api.example.com/mcp
- Name: remote-tools
"
```

The Agent will automatically generate the configuration:

```yaml
# ~/.haijunbot/config.yaml
mcp:
  - type: "sse"
    name: "remote-tools"
    base_url: "https://api.example.com/mcp"
```

#### Example 3: Integrating multiple MCP clients

```bash
hca --rule-names mcp-integration "
Integrate multiple MCP servers:
1. filesystem: stdio type, path /home/user/documents
2. database: stdio type, command python -m mcp_database_server
3. remote-api: sse type, URL https://api.example.com/mcp
"
```

### 2.4 Verifying MCP Integration

After the integration is complete, the Agent will automatically verify:

```bash
# The Agent will automatically perform the verification steps
1. Check the configuration file format
2. Verify the accessibility of the MCP server
3. Test the tool registration status
4. Provide a verification report
```

If verification fails, the Agent will provide detailed error information and repair suggestions.

---

## 3. Quickly Introducing TRACKS

### 3.1 Introducing TRACKS Using Rules

Use the track development rule to let the Agent help you add tracks:

```bash
# Approach 1: Add a track from a Git repository
hca --rule-names track-development "Add track: https://github.com/user/track-repo.git"

# Approach 2: Add a track from a local path
hca --rule-names track-development "Add track: /path/to/local/track"

# Approach 3: Use the rule in an interactive session
hca
> '<rule:track-development>' Add track: https://github.com/user/track-repo.git
```

### 3.2 TRACKS Addition Process

The Agent will automatically perform the following steps according to the rule:

1. **Input processing and validation**
   - Receive user input (local path or Git URL)
   - Determine the input type (Git URL or local path)
   - Validate the validity of the path or URL

2. **Git repository processing** (if it is a Git URL)
   - Check whether the track directory exists
   - Extract the repository name
   - Perform the clone operation
   - Handle clone failures

3. **Local path validation** (if it is a local path)
   - Path existence check
   - Path readability verification
   - Error handling

4. **Track functionality analysis**
   - Read key documents (README, package.json, setup.py, etc.)
   - Extract the track name, functionality description, and main features
   - Assess complexity (simple tracks are read directly; complex tracks use task_list_manager)

5. **Track information registration**
   - Register the track information in `~/.haijunbot/rules/rule.md`
   - Record the track name, functionality description, location, and addition time in a unified format

### 3.3 TRACKS Addition Examples

#### Example 1: Adding a track from a Git repository

```bash
hca --rule-names track-development "
Add track:
- Git URL: https://github.com/user/my-track.git
- Function: This is a track module for processing data
"
```

The Agent will automatically perform:

```bash
1. Clone the repository to ~/.haijunbot/tracks/my-track
2. Analyze the track functionality (read README.md)
3. Register the track information in ~/.haijunbot/rules/rule.md
```

#### Example 2: Adding a track from a local path

```bash
hca --rule-names track-development "
Add track:
- Local path: /home/user/my-local-track
- Function: A locally developed track module
"
```

The Agent will automatically perform:

```bash
1. Verify the path existence and readability
2. Analyze the track functionality
3. Register the track information in ~/.haijunbot/rules/rule.md
```

#### Example 3: Adding tracks in batch

```bash
hca --rule-names track-development "
Add tracks in batch:
1. https://github.com/user/track1.git
2. https://github.com/user/track2.git
3. /path/to/local/track3
"
```

### 3.4 Track Information Registration Format

The Agent will automatically register the track information in `~/.haijunbot/rules/rule.md`:

```markdown
## [Track name]

- **Function description**: [The core functionality description of the track]
- **Location**: [The full path of the track]
- **Addition time**: [YYYY-MM-DD HH:MM:SS]
```

---

## 4. Advanced Usage

### 4.1 Combining Rules

You can use multiple rules at the same time to complete complex integration tasks:

```bash
hca --rule-names mcp-integration,track-development "
Task: Fully integrate the development environment

1. Integrate MCP:
   - filesystem MCP: path /home/user/projects
   - database MCP: command python -m mcp_database_server

2. Add tracks:
   - https://github.com/user/code-analysis-track.git
   - https://github.com/user/test-generation-track.git
"
```

### 4.2 Custom Configuration

If you need a custom configuration, you can describe it in detail in the task description:

```bash
hca --rule-names mcp-integration "
Integrate a custom MCP server:
- Type: stdio
- Command: /usr/local/bin/my-mcp-server
- Args: --config /path/to/config.json
- Environment variables:
  - API_KEY: your-api-key
  - DEBUG: true
- Name: my-custom-mcp
"
```

### 4.3 Error Handling and Retry

If an error occurs during the integration process, the Agent will:

1. **Provide detailed error information**
2. **Give repair suggestions**
3. **Support a retry mechanism**

For example:

```bash
# If the Git clone fails
Agent: ⚠️ Git clone failed, possible causes:
1. Network connection problem
2. Incorrect URL format
3. The repository does not exist or access is not authorized

Please choose:
1. Retry
2. Change the URL
3. Abandon
```

---

## 5. Best Practices

### 5.1 MCP Integration Best Practices

1. **Explicitly specify the type**: Explicitly specify the MCP server type (stdio, sse, streamable) in the task description
2. **Use meaningful names**: Use meaningful names for MCP clients to facilitate identification
3. **Verify the configuration**: Verify that the configuration is correct after the integration is complete
4. **Document it**: Record the purpose and configuration of each MCP

### 5.2 TRACKS Addition Best Practices

1. **Use version control**: Prefer Git repositories over local paths
2. **Clear functionality description**: Provide a clear functionality description in the task description
3. **Update in a timely manner**: Update tracks to the latest version regularly
4. **Documentation maintenance**: Keep the track documentation up to date

### 5.3 Rule Usage Best Practices

1. **Clear task description**: Provide a clear, detailed task description
2. **Use rule names**: Use the correct rule names (`mcp-integration`, `track-development`)
3. **Verify the results**: Verify that the functionality works correctly after the integration is complete
4. **Error handling**: When encountering an error, check the detailed error information provided by the Agent

---

## 6. Real-World Application Scenarios

### Scenario 1: Quickly Integrating a Development Toolchain

```bash
hca --rule-names mcp-integration,track-development "
Integrate a complete development toolchain:

MCP integration:
1. filesystem: access project files
2. git: Git operation tool
3. database: database operation tool

Track addition:
1. code-analysis: code analysis track
2. test-generation: test generation track
3. documentation: documentation generation track
"
```

### Scenario 2: Setting Up a Team Collaboration Environment

```bash
hca --rule-names mcp-integration "
Configure a unified MCP environment for the team:
- Shared filesystem MCP: path /shared/projects
- Team database MCP: connect to the team database
- Code review MCP: integrate code review tools
"
```

### Scenario 3: Project-Specific Track Integration

```bash
hca --rule-names track-development "
Add dedicated tracks for the current project:
- Project track repository: https://github.com/company/project-tracks.git
- Locally developed tracks: ./local-tracks
"
```
