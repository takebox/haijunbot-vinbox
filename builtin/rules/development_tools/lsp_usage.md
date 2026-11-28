---
name: lsp_usage
description: Triggered when there is a need to use LSP tools for code analysis or development environment configuration. Triggered whenever the user mentions "LSP", "Language Server", "code navigation", "symbol lookup", "code diagnostics", "type inference", or "code completion". Not triggered: only using grep to search code; only running code without analysis; simple file operations that do not involve LSP.
---

# LSP Tool Usage Rule

## Rule Introduction

This rule guides how HaijunBot uses the haijunbot_lsp (hlsp) tool to enhance the ability to understand and modify code. The hlsp tool communicates with a language server (Language Server Protocol, LSP) to provide functions such as code navigation, symbol lookup, diagnostic information, and code actions.

**Core value**:

- Provide accurate code semantic information for LLM Agents
- Support code navigation and symbol location
- Provide code diagnostics and fix suggestions
- Simplified parameter design suited to LLMs

## Principles You Must Follow

### 1. Tool Selection Principle (must follow)

**Applicable scenarios**:

- **Must**: when you need to understand the code structure, find symbol definitions, or view symbol references, prioritize the hlsp tool
- **Must**: when you need to obtain code diagnostic information (syntax errors, lint warnings), use hlsp diagnostic
- **Must**: when you need to obtain code fix suggestions (refactoring, optimization), use the hlsp codeAction-related commands
- **Recommended**: when you need to understand the semantic information of a function or class, use hlsp hover
- **Forbidden**: do not use the hlsp tool for simple text search (use rg or grep)

**Tool advantages**:

- Accuracy: based on the LSP server's semantic analysis, not simple text matching
- Completeness: includes type information, docstrings, call relationships, etc.
- Consistency: a unified interface that supports multiple programming languages

### 1.1 Using the `lsp` Tool Within CodeAgent (must follow)

Within CodeAgent, the LSP capability is already wrapped as a native tool `lsp`; you **must prioritize the `lsp` tool over calling the `hlsp` CLI via `execute_script`**:

- **Must**: all LSP semantic queries within CodeAgent are completed through the `lsp` tool
- **Forbidden**: using `execute_script` to assemble shell commands that call `hlsp` (prone to path escaping issues and provides no structured return)
- **Forbidden**: using the `lsp` tool for pure text search (use `execute_script` + rg)

**Invocation format**:

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

**action and parameter reference**:

| action               | Required parameters    | Description                     |
| -------------------- | ---------------------- | ------------------------------- |
| document_symbols     | file_path              | List all symbols in a file      |
| find_definition      | file_path, symbol_name | Find a definition by symbol name |
| find_references      | file_path, symbol_name | Find references by symbol name  |
| find_implementation  | file_path, symbol_name | Find implementations by symbol name |
| find_type_definition | file_path, symbol_name | Find the type definition by symbol name |
| find_callers         | file_path, symbol_name | Who calls this symbol           |
| find_callees         | file_path, symbol_name | What this symbol calls          |
| hover                | file_path, line        | Type/documentation info (line starts at 1) |
| diagnostic           | file_path              | Errors and warnings             |
| code_action          | file_path, symbol_name | Get fix suggestions by symbol name |
| workspace_symbols    | query                  | Search symbols across the workspace |

**Automatic inference**:

- When `language` is omitted, it is inferred from the file extension (e.g., `.py` → python)
- When `project_path` is omitted, the directory containing `file_path` is used
- `file_path` supports both relative paths (relative to the current working directory) and absolute paths

**Return format**: `{"success": bool, "stdout": <JSON>, "stderr": <error>}`, where the `result` field in `stdout` is the query result.

**Degradation behavior**: when the language cannot be recognized, the language server is not installed, or the daemon fails to start, it returns `success=false`, and `stderr` contains the reason and installation hints, without interrupting the task.

### 1.2 Tool Selection Boundaries (must follow)

| Scenario                 | Should use            | Reason                   |
| ------------------------ | --------------------- | ------------------------ |
| Find symbol definition/reference/implementation | `lsp`                 | Semantically accurate, supports cross-file |
| Find type/docstring      | `lsp` hover           | Unique to LSP            |
| Find syntax errors/lint warnings | `lsp` diagnostic      | Unique to LSP            |
| Find refactoring/fix suggestions | `lsp` code_action     | Unique to LSP            |
| Pure text search         | `execute_script` + rg | LSP is not suitable for text matching |
| Call chain/dependency graph analysis | `symbol_dependency`   | Static parsing, no language server needed |
| Read file content        | `read_code`           | —                        |

### 2. Command Usage Principle (must follow)

**Symbol query commands** (preferred):

1. **document_symbols** - list all symbols in a file

   ```bash
   hlsp document_symbols <file_path>
   ```

   - **Must**: when analyzing a new file, first use this command to understand the file structure
   - **Must**: before looking up a symbol, confirm the symbol name and location
   - **Output**: a list of all classes, functions, and variables and their locations

2. **def-name** - find a definition by symbol name (best suited to LLMs)

   ```bash
   hlsp def-name <file_path> <symbol_name>
   ```

   - **Must**: LLMs should prioritize this command, which only requires knowing the symbol name
   - **Forbidden**: do not use commands that require exact column numbers
   - **Applicable**: looking up the definitions of functions, classes, variables, etc.

3. **hover** - get hover information for a symbol

   ```bash
   hlsp hover <file_path> <line> <column> --language <lang>
   ```

   - **Must**: the `--language` parameter is required; you must specify the programming language

   - **Must**: used when you need to understand the semantics, type, or docstring of a symbol
   - **Output**: includes type information, parameter descriptions, docstrings, etc.

**Diagnostics and fix commands**:

1. **diagnostic** - get code diagnostic information

   ```bash
   hlsp diagnostic <file_path> --language <lang>
   ```

   - **Must**: the `--language` parameter is required; you must specify the programming language

   - **Must**: used when checking code quality or finding errors
   - **Output**: includes all diagnostic information (ERROR/WARNING/INFO/HINT)
   - **Note**: pylsp may not support this method and will show a friendly error

2. **codeAction-by-name** - get fix suggestions by symbol name (best suited to LLMs)

   ```bash
   hlsp codeAction-by-name <file_path> <symbol_name> --language <lang>
   ```

   - **Must**: the `--language` parameter is required; you must specify the programming language

   - **Must**: LLMs should prioritize this command to obtain fix suggestions
   - **Applicable**: obtaining fix, refactoring, and optimization suggestions for a specific symbol

3. **codeAction** - get fix suggestions by line number

   ```bash
   hlsp codeAction <file_path> <line>
   ```

   - **Recommended**: use this command when only a line number is available
   - **Feature**: the column number defaults to 0, suitable for quick queries

### 3. LLM-Friendly Usage Principle (must follow)

**Parameter simplification**:

- **Must**: prioritize commands based on symbol names (such as `def-name`, `codeAction-by-name`)
- **Must**: avoid commands that require exact column numbers (LLMs are not good at handling exact column numbers)
- **Must**: use the `--language` parameter to specify the programming language (required, no default value)

**Usage flow**:

1. First use `document_symbols` to understand the file structure
2. After obtaining the symbol list, query by symbol name
3. Use `hover` to get detailed semantic information
4. Use `diagnostic` to check code problems
5. Use `codeAction-by-name` to get fix suggestions

**JSON output**:

- **Recommended**: use the `--json` parameter when the result needs to be processed programmatically
- **Output**: a structured JSON format, convenient for parsing and processing

### 4. Daemon Management Principle (must follow)

**Automatic startup**:

- **Must**: the daemon is automatically started the first time any hlsp command is used
- **Forbidden**: do not start the daemon manually (`hlsp daemon start` is deprecated)

**Status check**:

- **Recommended**: use `hlsp daemon status` to view the daemon status
- **Recommended**: use `hlsp daemon stop` to stop the daemon (only for debugging)

## Complete Command List

### Symbol Query Commands

| Command          | Parameters              | Description          | LLM suitability |
| ---------------- | ----------------------- | -------------------- | ---------- |
| document_symbols | file_path               | List all symbols in a file   | ⭐⭐⭐⭐⭐ |
| def-name         | file_path, symbol_name  | Find a definition by symbol name   | ⭐⭐⭐⭐⭐ |
| ref-name         | file_path, symbol_name  | Find references by symbol name   | ⭐⭐⭐⭐⭐ |
| impl-name        | file_path, symbol_name  | Find implementations by symbol name   | ⭐⭐⭐⭐⭐ |
| callers-name     | file_path, symbol_name  | Find symbols called within the function | ⭐⭐⭐⭐⭐ |
| hover            | file_path, line, column | Get symbol hover information     | ⭐⭐⭐⭐   |

### Diagnostics and Fix Commands

| Command            | Parameters             | Description              | LLM suitability |
| ------------------ | ---------------------- | ---------------------- | ---------- |
| diagnostic         | file_path              | Get code diagnostic information       | ⭐⭐⭐⭐⭐ |
| codeAction-by-name | file_path, symbol_name | Get fix suggestions by symbol name | ⭐⭐⭐⭐⭐ |
| codeAction         | file_path, line        | Get fix suggestions by line number   | ⭐⭐⭐⭐   |

### Daemon Management Commands

| Command       | Parameters | Description         |
| ------------- | ---- | ---------------- |
| daemon status | -    | View the daemon status |
| daemon stop   | -    | Stop the daemon     |

## Usage Examples

### Example 1: Analyzing a Python file

```bash
# 1. First understand the file structure
hlsp document_symbols src/main.py --language python

# 2. Find the definition of a function
hlsp def-name src/main.py MyClass --language python

# 3. Get detailed information about the function
hlsp hover src/main.py 10 5 --language python

# 4. Check for code problems
hlsp diagnostic src/main.py --language python

# 5. Get fix suggestions
hlsp codeAction-by-name src/main.py MyClass --language python
```

### Example 2: Finding all references

```bash
# 1. First get the symbol list
hlsp document_symbols src/main.py --language python

# 2. Find all references of the symbol
hlsp ref-name src/main.py MyClass --language python
```

### Example 3: Finding the symbols called by a function (the callees)

```bash
# 1. First get the symbol list
hlsp document_symbols src/main.py --language python

# 2. Find all symbols called within the function
hlsp callers-name src/main.py my_function --language python

# 3. Output in JSON format (default)
hlsp callers-name src/main.py my_function --language python
```

**Note**: the `callers-name` command is used to analyze which other symbols are called within a specified function, returning the definition locations of those called symbols. This is very useful for understanding function dependency relationships.

### Example 4: JSON output format

```bash
# Get the structured JSON output (default)
hlsp document_symbols src/main.py --language python
hlsp diagnostic src/main.py --language python
hlsp codeAction-by-name src/main.py MyClass --language python
```

## FAQ and Notes

### 1. pylsp limitations

**Unsupported features**:

- `textDocument/diagnostic` - pylsp does not support this method
- `textDocument/implementation` - pylsp does not support this method
- `textDocument/typeDefinition` - pylsp does not support this method

**Workarounds**:

- The tool returns a friendly error message
- You can try another LSP server (such as rust-analyzer, gopls, etc.)

### 2. Performance optimization

**Daemon reuse**:

- The daemon runs for a long time, avoiding repeated startup
- The LSP server instance is reused
- Subsequent query performance is significantly improved

**Timeout settings**:

- LSP server initialization timeout: 30 seconds
- Request timeout: 30 seconds
- If it times out, check the LSP server configuration

### 3. Error handling

**Common errors**:

- `LSP server not initialized` - the daemon is not started
- `Method Not Found` - the LSP server does not support the method
- `Timeout` - the LSP server response timed out

**Handling methods**:

- Check the daemon status: `hlsp daemon status`
- Try restarting the daemon: `hlsp daemon stop` and then re-run the command
- Check the LSP server configuration

## Best Practices

### 1. Code understanding flow

```bash
# Step 1: understand the file structure
document_symbols → get the symbol list

# Step 2: find the symbol definition
def-name → locate the symbol position

# Step 3: get symbol information
hover → understand the symbol semantics

# Step 4: view symbol references
ref-name → understand usage

# Step 5: check for code problems
diagnostic → discover potential problems

# Step 6: get fix suggestions
codeAction-by-name → apply the fix
```

### 2. LLM usage suggestions

**Prefer**:

- Commands based on symbol names (`def-name`, `ref-name`, `codeAction-by-name`)
- Commands that only need a line number (`codeAction`)

**Avoid**:

- Commands that require exact column numbers
- Commands that require manually managing the daemon

### 3. Multi-language support

**Supported programming languages**:

- Python (pylsp) - supported by default
- Rust (rust-analyzer) - requires configuration
- JavaScript/TypeScript (typescript-language-server) - requires configuration
- Go (gopls) - requires configuration
- Any other language server that implements the LSP protocol

**Must-follow principles**:

- **Must**: if the LSP server does not exist, you should first install the corresponding LSP server
- **Must**: after installing the LSP server, ensure it is accessible in the system PATH

**General LSP Server installation process**:

1. **Find the LSP server for the target language**
   - Visit <https://langserver.org/> to view the list of known LSP servers
   - Search GitHub or a search engine for `"<language> language server"`
   - Check the official documentation of the target language or community recommendations

2. **Install the LSP server**
   - **Install via a package manager** (recommended)

     ```bash
     # Python
     pip install python-lsp-server

     # Node.js
     npm install -g <language-server-name>

     # Go
     go install <package-path>

     # Rust
     cargo install <crate-name>

     # System package manager
     apt install <language-server>   # Debian/Ubuntu
     brew install <language-server>  # macOS
     pacman -S <language-server>     # Arch Linux
     ```

   - **Download a precompiled binary**
     - Visit the LSP server's GitHub Releases page
     - Download the binary for the corresponding platform
     - Extract it and move it to a directory in PATH (such as `/usr/local/bin` or `~/.local/bin`)

   - **Compile from source code**

     ```bash
     git clone <repository-url>
     cd <repository>
     cargo build --release  # or make, npm run build, etc.
     cp target/release/<binary> /usr/local/bin/
     ```

3. **Verify the installation**

   ```bash
   # Method 1: check whether the command is executable
   <lsp-server-command> --version
   <lsp-server-command> --help

   # Method 2: check whether the command is in PATH
   which <lsp-server-command>
   where <lsp-server-command>  # Windows

   # Method 3: test with hlsp
   hlsp document_symbols test.<ext> --language <lang>
   ```

4. **Configure hlsp to use the new LSP server**
   - **Must**: use the `--language` parameter to specify the programming language (required)
   - Ensure the correct languageId is used
   - Common languageIds: `python`, `rust`, `javascript`, `typescript`, `go`, `cpp`, `java`, etc.
   - If the LSP server is not in PATH, set an absolute path or add it to PATH

**Common language LSP Server examples**:

| Language              | LSP Server                 | Install command                                        | LanguageId                 |
| --------------------- | -------------------------- | ------------------------------------------------------ | -------------------------- |
| Python                | python-lsp-server          | `pip install "python-lsp-server[all]"`                 | `python`                   |
| Rust                  | rust-analyzer              | `rustup component add rust-analyzer`                   | `rust`                     |
| JavaScript/TypeScript | typescript-language-server | `npm install -g typescript typescript-language-server` | `javascript`, `typescript` |
| Go                    | gopls                      | `go install golang.org/x/tools/gopls@latest`           | `go`                       |
| C/C++                 | clangd                     | `apt install clangd` or `brew install clangd`          | `c`, `cpp`                 |
| Java                  | jdt.ls                     | Download the Eclipse plugin or use the VSCode extension | `java`                     |
| PHP                   | intelephense               | `npm install -g intelephense`                          | `php`                      |
| Lua                   | lua-language-server        | Download the binary or compile from source             | `lua`                      |

**Troubleshooting installation failures**:

1. **Check the system environment**

   ```bash
   # Check PATH
   echo $PATH

   # Check the package manager
   pip --version
   npm --version
   go version
   rustc --version
   ```

2. **Check permissions**
   - If sudo is needed, use `sudo pip install` or `sudo npm install -g`
   - Or install to the user directory: `pip install --user`, `npm config set prefix ~/.local`

3. **View the error log**
   - Most LSP servers output detailed logs on startup
   - You can run `<lsp-server-command>` directly in the terminal to view errors

4. **Find alternatives**
   - If one LSP server does not work, you can try another implementation
   - For example, Python has multiple choices such as pyls, pylsp, and pyright

**Usage method**:

```bash
hlsp document_symbols src/main.rs --language rust
hlsp def-name src/main.rs MyStruct --language rust
```

**Note**: the `--language` parameter is required and must be specified for all commands.

## Summary

**Core principles**:

1. Prioritize commands based on symbol names and avoid exact column numbers
2. First understand the file structure, then perform symbol queries
3. Combine diagnostics and fix suggestions to improve code quality
4. Leverage daemon reuse to optimize performance

**Applicable scenarios**:

- Code understanding and analysis
- Symbol navigation and location
- Code quality checking
- Code fixing and refactoring

**Inapplicable scenarios**:

- Simple text search (use rg, grep)
- Queries of non-code files
- Programming languages that do not support LSP
