# HaijunBot LSP Client Tools

`haijunbot_lsp` is a command-line LSP (Language Server Protocol) client tool that supports communication with LSP servers for various languages and provides features such as code symbol queries.

## Features

- Supports LSP servers for multiple programming languages
- Automatically detects the language of a file
- Symbol queries (lists functions, classes, variables, etc.)
- Supports both human-readable and JSON output formats
- Reuses the `~/.haijunbot/config.yaml` configuration

## Installation

`haijunbot_lsp` is integrated into the HaijunBot project, so no additional installation is required.

### Installing LSP Servers

`haijunbot_lsp` requires the appropriate LSP server to be installed to work. Below are the installation methods for LSP servers of common languages:

#### Python

```bash
pip install python-lsp-server
```

#### Go

```bash
go install golang.org/x/tools/gopls@latest
```

#### Rust

```bash
rustup component add rust-analyzer
```

#### C/C++

```bash
# Ubuntu/Debian
sudo apt-get install clangd

# macOS
brew install llvm

# Or build from source: https://clangd.llvm.org/installation/
```

#### JavaScript/TypeScript

```bash
npm install -g javascript-typescript-stdio typescript-language-server
```

#### Other Languages

See the [LSP server implementation list](https://microsoft.github.io/language-server-protocol/implementors/tools/) for LSP server installation methods for more languages.

## Usage

### Commands

Two command names are supported:

- `haijunbot-lsp`
- `hlsp`

### Querying File Symbols

````bash
# Query the symbols of a file (human-readable format)
hlsp symbols /path/to/file.py

# Query the symbols of a file (JSON format)
hlsp symbols /path/to/file.py --json

# Specify the LSP server command
hlsp symbols /path/to/file.py --server-command "python -m pylsp"
``

### Viewing the Version

```bash
hlsp version
````

## Configuration

### Built-in Default Configuration

`haijunbot_lsp` ships with LSP server configurations for the following common languages, ready to use out of the box:

| Language   | LSP server                           |
| ---------- | ------------------------------------- |
| Python     | `python -m pylsp`                     |
| Go         | `gopls`                               |
| Rust       | `rust-analyzer`                       |
| C/C++      | `clangd`                              |
| JavaScript | `javascript-typescript-stdio`         |
| TypeScript | `typescript-language-server --stdio`  |
| Lua        | `lua-language-server`                 |
| Bash       | `bash-language-server start`          |
| Ruby       | `solargraph stdio`                    |
| PHP        | `intelephense --stdio`                |
| HTML       | `vscode-html-language-server --stdio` |
| CSS        | `vscode-css-language-server --stdio`  |

### Configuration File Location

`~/.haijunbot/config.yaml`

### Configuration Format

```yaml
lsp:
  # Language configuration (overrides the built-in default configuration)
  languages:
    python:
      command: python
      args: ["-m", "pylsp"]
      file_extensions: [".py", ".pyi"]

    rust:
      command: rust-analyzer
      args: []
      file_extensions: [".rs"]

    go:
      command: gopls
      args: []
      file_extensions: [".go"]
```

### Configuration Notes

- User configuration overrides the built-in default configuration
- `lsp.languages`: defines the mapping from languages to LSP server startup commands
  - `command`: The LSP server executable command
  - `args`: The list of startup arguments
  - `file_extensions`: The list of supported file extensions
- The server command should support stdin/stdout communication (stdio)

## Examples

### Python File Symbol Query

```bash
# The Python LSP server configuration is built in, ready to use out of the box
# Query symbols
hlsp symbols myapp.py
```

### Rust File Symbol Query

```bash
# The Rust LSP server configuration is built in, ready to use out of the box
# Query symbols
hlsp symbols main.rs --json
```

### Using a Custom Server Command

```bash
# Temporarily use a different server command
hlsp symbols test.py --server-command "custom-lsp-server --stdio"
```

## Technical Architecture

```text
ELI Layer (eli.py)
  ↓
Configuration Layer (config.py)
  ↓
LSP Client Layer (client.py)
  ↓
Protocol Layer (protocol.py)
```

## Development Notes

- Uses `typer` as the CLI framework
- Uses `asyncio` for asynchronous LSP communication
- Uses `print` for output
- Follows the project code conventions (mypy, ruff, bandit checks)

## Dependencies

- Python 3.8+
- typer
- pydantic
- haijunbot_utils
