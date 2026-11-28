# Functional Comparison Document: HaijunBot CLI vs OpenAI Codex CLI

## 📋 Overview

This document Compares the features, design philosophy, and applicable Scenarios of two AI-assisted development command-line tools, **HaijunBot CLI** and **OpenAI Codex CLI**, to help developers choose the tool that best fits their Requirements.

### Basic Information

| Feature | HaijunBot CLI                 | OpenAI Codex CLI           |
| -------- | -------------------------- | -------------------------- |
| Developer | Open-source community (takebox) | OpenAI                     |
| Open-source status | ✅ Fully open source      | ❌ Closed source           |
| Main positioning | AI application development SDK + personal assistant | AI code generation assistant |
| Programming language | Python | Rust                       |
| Platform support | Linux/macOS/WSL | macOS/Linux/Windows + WSL2 |
| Installation method | pip/uv/Docker/source | Official installer/Docker |
| Configuration format | YAML | TOML                       |
| SDK support | ✅ Python SDK | ❌ No SDK                   |
| First release | 2025 | 2025                      |

---

## 🔍 Core Feature Comparison

### 1. Architecture Design and Positioning

| Dimension | HaijunBot CLI                                    | Codex CLI                                 |
| ------------ | --------------------------------------------- | ----------------------------------------- |
| **Core positioning** | An AI application development SDK providing basic Components for building professional AI applications | An AI code generation assistant, a code editing tool integrated into the terminal |
| **Usage mode** | SDK programming + command-line interaction | Terminal interactive + non-interactive     |
| **Scalability** | ⭐⭐⭐⭐⭐ Highly programmable, freely customizable | ⭐⭐⭐ Supports MCP protocol extensions     |
| **Applicable Scenarios** | Building AI applications, automating tasks, multi-agent collaboration | Code generation, real-time editing, rapid development |

**HaijunBot Advantages:**

- Provided as a Python SDK, letting developers freely combine various capabilities
- Built-in `Agent` and `CodeAgent` basic Components for quickly building professional AI applications
- Emphasizes programmability and Scalability

**Codex Advantages:**

- Optimized for terminal experience, seamlessly integrated into development workflows
- Rust implementation, excellent Performance, fast startup
- Focused on code generation and editing Scenarios

### 2. Command System

#### HaijunBot CLI Command List (19 core commands)

| Command | Shortcut | Description |
| ------------------------------ | -------- | -------------------------- |
| `haijunbot` | `hjb` | Generic AI agent supporting multiple tasks |
| `haijunbot-agent-dispatcher` | `hjbd` | Task dispatch and interaction mode |
| `haijunbot-agent` | `ha` | Basic AI agent functionality |
| `haijunbot-code-agent` | `hca` | Code analysis, modification, and generation |
| `haijunbot-code-agent-dispatcher` | `hcad` | Code task dispatch |
| `haijunbot-git-commit` | `hgc` | Generate Git commit messages |
| `haijunbot-git-squash` | `hgs` | Tidy up Git commit history |
| `haijunbot-platform-manager` | `hpm` | Manage LLM platforms |
| `haijunbot-tool` | `ht` | Tool management and invocation |
| `haijunbot-methodology` | `hm` | Methodology knowledge base management |
| `haijunbot-smart-shell` | `hss` | Smart Shell functionality |
| `haijunbot-memory-organizer` | `hmo` | Memory management with import/export support |
| `haijunbot-sec` | `hsec` | Security analysis suite (C/C++/Rust) |
| `haijunbot-c2rust` | `hc2r` | C→Rust migration suite |
| `haijunbot-config` | `hcfg` | Configuration management tool |

#### Codex CLI Command List

| Command/Slash command | Description |
| -------------------------------- | ------------------------------------------ |
| `codex` | Start an interactive session |
| `codex "prompt"` | One-shot prompt execution |
| `codex exec "task"` | Non-interactive automated execution |
| `codex resume` | Session resume (interactive selection) |
| `codex resume --last` | Jump to the most recent session |
| `/review` | Code review (branch/commit/change) |
| `/model` | Switch Model at runtime |
| `/approvals` | Set approval mode (Auto/Read-only/Full Access) |
| `/plan` | Planning feature |
| `/status` | View status |
| `/exit` | Exit the session |
| `codex cloud` | Cloud task manager |
| `codex mcp` | MCP server management |
| `codex completion bash/zsh/fish` | Shell completion installation |

**Comparison Analysis:**

- **Number of commands**: HaijunBot provides more dedicated commands (20+), while Codex uses the slash-command pattern
- **Feature coverage**: HaijunBot covers more ground (Security analysis, code migration, etc.); Codex focuses on code-related features
- **Command design**: HaijunBot uses standalone commands + shortcuts; Codex uses a main command + subcommands/slash commands
- **Specialization**: HaijunBot has dedicated Security analysis and code migration suites; Codex has cloud service integration

### 3. Tool Ecosystem

| Dimension | HaijunBot CLI                                         | Codex CLI                                  |
| ---------------- | -------------------------------------------------- | ------------------------------------------ |
| **Number of built-in tools** | 30+ tools | About 10-15 tools |
| **Tool types** | File operations, code analysis, command execution, web search, Git operations, etc. | File read/write, code editing, Shell commands, web search, etc. |
| **Extension method** | Custom Python tool registration | MCP (Model Context Protocol) |
| **Code analysis depth** | Deep (symbol lookup, precise editing, build Validation) | Moderate (smart editing, diff preview) |
| **Special tools** | Methodology system, memory system, Security scanning, code migration | Image input, Web search, cloud services |

#### HaijunBot Built-In Core Tools (partial)

- `read_code` - reads source code files
- `edit_file` - precise text editing (search/replace)
- `execute_script` - executes script commands
- `search_web` - web search
- `read_webpage` - reads webpage content
- `save_memory` - saves memory
- `retrieve_memory` - retrieves memory
- `virtual_tty` - virtual terminal

#### Codex Built-In Core Tools (partial)

- File read/write operations
- Code editing and diff
- Shell command execution (`!command`)
- Web search tool (requires enabling)
- Image input support (PNG, JPEG)

**Comparison Analysis:**

- **Tool richness**: HaijunBot's tool ecosystem is richer, especially advanced features like memory and
  Methodology
- **Extension Mechanism**: HaijunBot uses custom Python tools,
  while Codex uses the MCP standard protocol
- **Specialized tools**: HaijunBot has dedicated Security analysis and code migration tools; Codex has image input and cloud services

### 4. Configuration and Management

| Dimension | HaijunBot CLI                         | Codex CLI                     |
| -------------- | ---------------------------------- | ----------------------------- |
| **Configuration file** | `~/.haijunbot/config.yaml` | `~/.codex/config.toml` |
| **Configuration format** | YAML | TOML |
| **Interactive Configuration** | ✅ Automatic first-run guide | ❌ Requires manual editing |
| **Configuration hot reload** | ✅ Supported (the `'<ReloadConfig>'` directive) | ❌ Not supported |
| **Model group management** | ✅ Supports switching between multiple Model groups | ⚠️ Supports Model switching, no Model-group concept |
| **Visual Configuration** | ✅ Generates a Web UI based on JSON Schema | ❌ None |

#### HaijunBot Configuration Example

```yaml
llm_group: default

llm_groups:
  default:
    normal_llm: gpt-5
    cheap_llm: gpt-3.5-turbo

llms:
  gpt-5:
    platform: openai
    model: gpt-5
    max_input_token_count: 128000
    llm_config:
      openai_api_key: "your-api-key"
      openai_api_base: "https://api.openai.com/v1"
```

#### Codex Configuration Example

```toml
[features]
web_search_request = true

[sandbox_workspace_write]
network_access = true

[models]
default = "gpt-5-codex"
```

**Comparison Analysis:**

- **Configuration complexity**: HaijunBot Configuration is more complex but more powerful (Model groups, multiple platforms); Codex Configuration is simple
- **Configuration experience**: HaijunBot has an interactive guide and a visual interface,
  while Codex requires manual editing
- **Flexibility**: HaijunBot supports multiple Model groups and dynamic switching; Codex supports runtime Model switching

### 5. Model Support

| Dimension | HaijunBot CLI                            | Codex CLI                 |
| -------------- | ------------------------------------- | ------------------------- |
| **Supported platforms** | Multiple platforms (OpenAI, Haijun, domestic Models, etc.) | OpenAI ecosystem |
| **Custom platforms** | ✅ Supports integrating new platforms through a unified Interface | ❌ Only OpenAI Models |
| **Model groups** | ✅ Supports multiple Model groups (normal/cheap/smart) | ⚠️ Default Model, switchable at runtime |
| **Model switching** | ✅ Configuration file + command-line Parameters (`-g`) | ✅ `/model` slash command |

**Comparison Analysis:**

- **Platform diversity**: HaijunBot supports multiple LLM platforms; Codex supports only the OpenAI ecosystem
- **Customization**: HaijunBot can integrate new LLM providers; Codex is limited to OpenAI
- **Model management**: HaijunBot's Model-group system is more powerful (normal/cheap/smart); Codex is simple and direct

### 6. Security and Permission Control

| Dimension | HaijunBot CLI                  | Codex CLI                            |
| ------------ | --------------------------- | ------------------------------------ |
| **Manual intervention** | ✅ Multi-level intervention Mechanism | ✅ Approval mode |
| **Sandbox Mechanism** | ⚠️ Depends on Docker (optional) | ✅ Default sandbox (Apple Seatbelt/Docker) |
| **Network isolation** | ⚠️ Depends on Docker | ✅ Configurable network access |
| **Execution confirmation** | ✅ `[Y/n]` confirmation by default | ✅ Based on approval mode |
| **Force exit** | ✅ Force exit after 5 Ctrl+C presses | ✅ Ctrl+C exit |
| **File permissions** | Docker mode supports non-root users | Filesystem isolation inside the sandbox |

**Comparison Analysis:**

- **Default Security**: Codex's default sandbox environment is more Secure; HaijunBot needs Docker for a sandbox
- **Manual control**: HaijunBot's manual intervention Mechanism is more fine-grained (intervention after thinking); Codex's approval mode is more intuitive
- **Network control**: Codex's network access control is finer-grained; HaijunBot depends on Docker

### 7. Session and Memory Management

| Dimension | HaijunBot CLI                                 | Codex CLI                       |
| -------------- | ------------------------------------------ | ------------------------------- |
| **Short-term memory** | ✅ Three-tier Architecture (short-term/project long-term/global long-term) | ⚠️ Session context (up to 10 messages) |
| **Memory persistence** | ✅ Complete memory system | ✅ Local session storage |
| **Session recovery** | ✅ `'<SaveSession>'` + `--restore-session` | ✅ `codex resume` (more powerful) |
| **Memory retrieval** | ✅ Smart retrieval (by type and tag) | ⚠️ Recovery by session ID |
| **Memory export** | ✅ Import/export supported | ❌ None |
| **Session length** | ✅ Unlimited | ✅ Long sessions supported (7 hours) |

**Comparison Analysis:**

- **Memory system**: HaijunBot's three-tier memory system is more powerful (short-term/project long-term/
  global long-term), while Codex has only session memory
- **Session recovery**: Codex's session recovery is more complete
  (`--all`, `--last`, SESSION_ID)
- **Session length**: Codex supports long sessions (7 hours); HaijunBot is unlimited but depends on the Model context

### 8. Interaction Modes

| Dimension | HaijunBot CLI                      | Codex CLI                       |
| -------------- | ------------------------------- | ------------------------------- |
| **Interactive mode** | ✅ Full interactive mode | ✅ Full-screen terminal UI |
| **Non-interactive mode** | ✅ `-n/--non-interactive` | ✅ One-shot prompt + exec command |
| **Multi-line input** | ✅ Dedicated multi-line input mode | ⚠️ Supported in interactive mode |
| **Shortcuts** | `@`/`#` file completion, `Ctrl+J` to submit | `Ctrl+G` editor, double-click `Esc` to edit |
| **File selection** | ✅ Git-file mode + full-file mode | ✅ `@` symbol triggers fuzzy search |
| **Special directives** | ✅ Built-in special directives | ✅ Slash commands |
| **Shell completion** | ⚠️ Basic built-in completion | ✅ Full bash/zsh/fish completion |

**Comparison Analysis:**

- **Interaction experience**: Codex's full-screen terminal UI is more modern; HaijunBot's interaction is more traditional but practical
- **File completion**: HaijunBot's Git-file mode and full-file mode are more fine-grained,
  while Codex's fuzzy search is simpler
- **Shell completion**: Codex provides complete Shell completion scripts; HaijunBot's completion is weaker
- **Special directives**: both have powerful directive systems, but with different design philosophies

### 9. Integration and Automation

| Dimension | HaijunBot CLI                  | Codex CLI                 |
| -------------- | --------------------------- | ------------------------- |
| **CI/CD support** | ✅ Non-interactive mode, script timeout control | ✅ Non-interactive execution, cloud service integration |
| **Script timeout** | ✅ 5 minutes by default in non-interactive mode | ⚠️ Not explicitly Described |
| **Git integration** | ✅ Dedicated Git tools | ✅ Integrated into code review |
| **Multi-solution generation** | ❌ Not supported | ✅ `--attempts` Parameters |
| **API Interface** | ✅ Python SDK | ❌ No SDK, CLI only |
| **Configuration hot reload** | ✅ Reloads Configuration at runtime | ❌ Requires restart |

**Comparison Analysis:**

- **Git integration**: HaijunBot has dedicated Git tools; Codex integrates it into code review
- **Multi-solution generation**: Codex supports generating multiple solutions (`--attempts`); HaijunBot does not
- **Programming Interface**: HaijunBot provides a complete Python SDK; Codex is CLI only

---

## 🌟 Distinctive Features

### HaijunBot Distinctive Features

1. **Methodology system** (`haijunbot-methodology`)
   - Codify successful experiences into reusable Methodology
   - Supports local and centralized sharing

2. **Memory system** (`haijunbot-memory-organizer`)
   - Three-tier memory Architecture
   - Memory organization, merging, and import/export

3. **Python SDK**
   - Complete Python API
   - Programmatically build AI applications

### Codex Distinctive Features

1. **Image input support**
   - Formats such as PNG and JPEG
   - Use screenshots and design specs as prompts

2. **Cloud service integration**
   - `codex cloud` cloud task manager
   - Supports remote execution and management

3. **Custom slash commands**
   - Create team-specific workflows
   - Reusable command templates

4. **High-Performance Rust**
   - Fast startup and response
   - Memory-Safe

---

## 🎯 Applicable Scenario Comparison

### Scenarios Where HaijunBot CLI Fits Better

✅ **Building AI applications**

- Need to build customized AI applications using the SDK
- Need deep programmability and extensibility

✅ **Multi-Model platform support**

- Need to use non-OpenAI Models (Haijun, domestic Models, etc.)
- Need to switch between different LLM providers

✅ **Complex task automation**

- Need Methodology codification and reuse
- Need multi-agent collaboration

✅ **Specialized code tasks**

- Security analysis (C/C++/Rust)
- C→Rust code migration
- Deep code analysis and refactoring

✅ **Memory management Requirements**

- Need long-term memory and knowledge accumulation
- Need memory retrieval and export

✅ **Open source and customization**

- Need to view and modify source code
- Need to add custom features

### Scenarios Where Codex CLI Fits Better

✅ **Rapid code generation and editing**

- Quickly generate code snippets in the terminal
- Real-time code editing and modification

✅ **Modern terminal experience**

- Need a full-screen terminal UI
- Need a smooth interactive experience

✅ **Image input Requirements**

- Need to use screenshots or design images as prompts
- Need to handle image-related tasks

✅ **Long-running complex tasks**

- Need continuous context beyond 7 hours
- Need uninterrupted complex task execution

✅ **Cloud service integration**

- Need to execute and manage tasks remotely
- Need cloud service integration

✅ **Performance-sensitive Scenarios**

- Need fast startup and response
- Rust's high-Performance Advantages are obvious

✅ **Deep OpenAI ecosystem integration**

- Focus on using OpenAI Models
- Need the latest OpenAI features

---

## 📊 Overall Ratings

| Evaluation dimension | HaijunBot CLI | Codex CLI  |
| ------------------------- | ---------- | ---------- |
| **Scalability** (customization) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐     |
| **Feature richness** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐   |
| **Ease of use** (learning curve) | ⭐⭐⭐     | ⭐⭐⭐⭐⭐ |
| **Performance** (startup/response) | ⭐⭐⭐     | ⭐⭐⭐⭐⭐ |
| **Documentation and community** | ⭐⭐⭐⭐   | ⭐⭐⭐     |
| **Open-sourceness** | ⭐⭐⭐⭐⭐ | ⭐         |
| **Model diversity** | ⭐⭐⭐⭐⭐ | ⭐⭐       |
| **Interaction experience** | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ |
| **Security** (sandbox/permissions) | ⭐⭐⭐⭐   | ⭐⭐⭐⭐⭐ |
| **Specialized features** (Security/migration) | ⭐⭐⭐⭐⭐ | ⭐⭐       |
| **SDK support** | ⭐⭐⭐⭐⭐ | ⭐         |
| **Cloud service integration** | ⭐⭐       | ⭐⭐⭐⭐⭐ |

---

## 💡 Selection Recommendations

### Choose HaijunBot CLI if

- You need to build programmable AI applications
- You need to use multiple LLM platforms (not just OpenAI)
- You need specialized features such as Security analysis and code migration
- You need a complete memory system
- You need multi-agent collaboration
- You need open source and full control

### Choose Codex CLI if

- You focus on code generation and editing Scenarios
- You need a modern terminal interaction experience
- You need image input functionality
- You need long-session support (7 hours)
- You need cloud service integration
- You need Rust's high Performance
- You work entirely within the OpenAI ecosystem

### Use Both

The two tools are not mutually exclusive and can be used in different Scenarios:

- Use **Codex CLI** for daily code writing and quick editing
- Use **HaijunBot CLI** to build automation scripts, perform Security analysis,
  and handle complex tasks such as code migration
- Use the **HaijunBot SDK** to build customized AI applications

---

## 📝 Summary

**HaijunBot CLI** is a powerful, highly Scalable AI application development platform,
providing a complete Python SDK, a rich tool ecosystem, multi-Model support, and specialized
feature suites. It suits developers who need deep customization, building AI applications, and handling complex
tasks.

**Codex CLI** is a modern CLI tool designed for code generation and editing,
offering a smooth terminal experience, a high-Performance Rust implementation, image input support, and cloud
service integration. It suits developers focused on the OpenAI ecosystem who need fast coding.

Both tools have their advantages; which one you choose depends on your specific Requirements:

- **Programmability and extensibility** → HaijunBot CLI
- **Terminal experience and code generation** → Codex CLI
- **Multi-Model support** → HaijunBot CLI
- **Deep OpenAI integration** → Codex CLI
- **Specialized features (Security/migration)** → HaijunBot CLI
- **Modern interaction and Performance** → Codex CLI

The best way is to choose the right tool based on the actual Scenario, or even use
both in the same project to leverage each tool's Advantages.

---

## 🔗 Related Resources

### HaijunBot CLI

- GitHub: <https://github.com/takebox/HaijunBot>
- Docs: `/docs/haijunbot_book/`
- Configuration: `~/.haijunbot/config.yaml`

### Codex CLI

- Official docs: <https://developers.openai.com/codex/cli/features>
- Configuration: `~/.codex/config.toml`

---

Last updated: 2025-01-12
