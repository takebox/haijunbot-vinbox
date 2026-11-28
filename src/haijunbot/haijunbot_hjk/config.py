# -*- coding: utf-8 -*-
"""Tool configuration definitions

Defines the list of tools to check and their related information.
"""

from typing import Dict, List

# Tool configuration list
TOOLS_CONFIG: List[Dict[str, str]] = [
    {
        "name": "git",
        "command": "git",
        "description": "Distributed version control system",
        "install_hint": "Visit https://git-scm.com/downloads to download and install, or install via a package manager:"
        "\n  Ubuntu/Debian: sudo apt install git"
        "\n  macOS: brew install git",
    },
    {
        "name": "ripgrep",
        "command": "rg",
        "description": "Extremely fast text search tool",
        "install_hint": "Visit https://github.com/BurntSushi/ripgrep#installation to install, or use a package manager:"
        "\n  Ubuntu/Debian: sudo apt install ripgrep"
        "\n  macOS: brew install ripgrep",
    },
    {
        "name": "fd-find",
        "command": "fd",
        "description": "Fast and user-friendly file-finding tool",
        "install_hint": "Visit https://github.com/sharkdp/fd#installation to install, or use a package manager:"
        "\n  Ubuntu/Debian: sudo apt install fd-find"
        "\n  macOS: brew install fd",
    },
    {
        "name": "fzf",
        "command": "fzf",
        "description": "Command-line fuzzy finder",
        "install_hint": "Visit https://github.com/junegunn/fzf#installation to install, or use a package manager:"
        "\n  Ubuntu/Debian: sudo apt install fzf"
        "\n  macOS: brew install fzf",
    },
    {
        "name": "rustup",
        "command": "rustup",
        "description": "Rust toolchain installer",
        "install_hint": "Visit https://rustup.rs/ to install, or run:"
        "\n  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
    },
    {
        "name": "cargo",
        "command": "cargo",
        "description": "Rust package manager",
        "install_hint": "cargo is usually installed together with rustup; if not installed, install rustup first:"
        "\n  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh",
    },
    {
        "name": "loc",
        "command": "loc",
        "description": "Code line count statistics tool",
        "install_hint": "Visit https://github.com/cgag/loc to install, or use a package manager:"
        "\n  Ubuntu/Debian: sudo apt install loc"
        "\n  macOS: brew install loc"
        "\n  Cargo: cargo install loc"
        "\n  pip: pip install loc",
    },
    {
        "name": "tmux",
        "command": "tmux",
        "description": "Terminal multiplexer",
        "install_hint": "Ubuntu/Debian: sudo apt install tmux"
        "\n  macOS: brew install tmux"
        "\n  or visit https://github.com/tmux/tmux to view the documentation",
    },
]

# Lint tool configuration list
LINT_TOOLS_CONFIG: List[Dict[str, str]] = [
    {
        "name": "ruff",
        "command": "ruff",
        "description": "Python code linter and formatter",
        "install_hint": "Install: pip install ruff"
        "\n  or visit https://docs.astral.sh/ruff/ to view the documentation",
    },
    {
        "name": "ty",
        "command": "ty check",
        "description": "Python static type checker (extremely fast)",
        "install_hint": "Install: pip install ty"
        "\n  or visit https://docs.astral.sh/ty/ to view the documentation",
    },
    {
        "name": "shellcheck",
        "command": "shellcheck",
        "description": "Shell script static analysis tool",
        "install_hint": "Ubuntu/Debian: sudo apt install shellcheck"
        "\n  macOS: brew install shellcheck"
        "\n  or visit https://www.shellcheck.net/ to view the documentation",
    },
    {
        "name": "clang-tidy",
        "command": "clang-tidy",
        "description": "C/C++ linter and static analysis tool",
        "install_hint": "Ubuntu/Debian: sudo apt install clang-tidy"
        "\n  macOS: brew install llvm"
        "\n  or visit https://clang.llvm.org/extra/clang-tidy/ to view the documentation",
    },
    {
        "name": "eslint",
        "command": "eslint",
        "description": "JavaScript/TypeScript linter",
        "install_hint": "Install: npm install -g eslint"
        "\n  or visit https://eslint.org/ to view the documentation",
    },
    {
        "name": "rubocop",
        "command": "rubocop",
        "description": "Ruby static code analysis tool",
        "install_hint": "Install: gem install rubocop"
        "\n  or visit https://docs.rubocop.org/ to view the documentation",
    },
    {
        "name": "pylint",
        "command": "pylint",
        "description": "Python code checking tool",
        "install_hint": "Install: pip install pylint"
        "\n  or visit https://pylint.org/ to view the documentation",
    },
    {
        "name": "flake8",
        "command": "flake8",
        "description": "Python code style checking tool",
        "install_hint": "Install: pip install flake8"
        "\n  or visit https://flake8.pycqa.org/ to view the documentation",
    },
    {
        "name": "prettier",
        "command": "prettier",
        "description": "General-purpose code formatter (JS/TS/CSS/HTML/JSON/Markdown, etc.)",
        "install_hint": "Install: npm install -g prettier"
        "\n  or visit https://prettier.io/ to view the documentation",
    },
    {
        "name": "markdownlint",
        "command": "markdownlint",
        "description": "Markdown file checking and formatting tool",
        "install_hint": "Install: npm install -g markdownlint-cli"
        "\n  or visit https://github.com/igorshubovych/markdownlint-cli to view the documentation",
    },
    {
        "name": "stylelint",
        "command": "stylelint",
        "description": "CSS/SCSS/SASS/LESS style checking tool",
        "install_hint": "Install: npm install -g stylelint"
        "\n  or visit https://stylelint.io/ to view the documentation",
    },
    {
        "name": "swiftlint",
        "command": "swiftlint",
        "description": "Swift code checking and formatting tool",
        "install_hint": "Install: brew install swiftlint (macOS)"
        "\n  or visit https://github.com/realm/SwiftLint to view the documentation",
    },
    {
        "name": "ktlint",
        "command": "ktlint",
        "description": "Kotlin code formatting tool",
        "install_hint": "Install: brew install ktlint (macOS)"
        "\n  or visit https://github.com/pinterest/ktlint to view the documentation",
    },
    {
        "name": "sqlfluff",
        "command": "sqlfluff",
        "description": "SQL code formatting and checking tool",
        "install_hint": "Install: pip install sqlfluff"
        "\n  or visit https://docs.sqlfluff.com/ to view the documentation",
    },
    {
        "name": "phpstan",
        "command": "phpstan",
        "description": "PHP static analysis tool",
        "install_hint": "Install: composer global require phpstan/phpstan"
        "\n  or visit https://phpstan.org/ to view the documentation",
    },
]

# Build tool configuration list
BUILD_TOOLS_CONFIG: List[Dict[str, str]] = [
    {
        "name": "pytest",
        "command": "pytest",
        "description": "Python testing framework",
        "install_hint": "Install: pip install pytest"
        "\n  or visit https://docs.pytest.org/ to view the documentation",
    },
    {
        "name": "build",
        "command": "python -m build",
        "description": "Python package build tool",
        "install_hint": "Install: pip install build"
        "\n  or visit https://pypa-build.readthedocs.io/ to view the documentation",
    },
    {
        "name": "twine",
        "command": "twine",
        "description": "PyPI package publishing tool",
        "install_hint": "Install: pip install twine"
        "\n  or visit https://twine.readthedocs.io/ to view the documentation",
    },
    {
        "name": "cmake",
        "command": "cmake",
        "description": "Cross-platform build system generator",
        "install_hint": "Ubuntu/Debian: sudo apt install cmake"
        "\n  macOS: brew install cmake"
        "\n  or visit https://cmake.org/ to view the documentation",
    },
    {
        "name": "go",
        "command": "go",
        "description": "Go language toolchain",
        "install_hint": "Visit https://go.dev/dl/ to download and install, or use a package manager:"
        "\n  Ubuntu/Debian: sudo apt install golang-go"
        "\n  macOS: brew install go",
    },
    {
        "name": "gradle",
        "command": "gradle",
        "description": "Java automated build tool",
        "install_hint": "Ubuntu/Debian: sudo apt install gradle"
        "\n  macOS: brew install gradle"
        "\n  or visit https://gradle.org/ to view the documentation",
    },
    {
        "name": "maven",
        "command": "mvn",
        "description": "Java project management tool",
        "install_hint": "Ubuntu/Debian: sudo apt install maven"
        "\n  macOS: brew install maven"
        "\n  or visit https://maven.apache.org/ to view the documentation",
    },
    {
        "name": "npm",
        "command": "npm",
        "description": "Node.js package manager",
        "install_hint": "npm is included automatically when installing Node.js"
        "\n  Visit https://nodejs.org/ to download and install"
        "\n  or visit https://docs.npmjs.com/ to view the documentation",
    },
]

# Get tool configuration


def get_tools_config() -> List[Dict[str, str]]:
    """Get the tool configuration list"""
    return TOOLS_CONFIG


def get_tool_config(tool_name: str) -> Dict[str, str] | None:
    """Get the configuration of the specified tool

    Args:
        tool_name: Tool name

    Returns:
        Tool configuration dictionary, or None if not found
    """
    # Search for the tool in all configuration lists
    for config_list in [TOOLS_CONFIG, LINT_TOOLS_CONFIG, BUILD_TOOLS_CONFIG]:
        for tool in config_list:
            if tool["name"] == tool_name:
                return tool
    return None


def get_lint_tools_config() -> List[Dict[str, str]]:
    """Get the lint tool configuration list"""
    return LINT_TOOLS_CONFIG


def get_build_tools_config() -> List[Dict[str, str]]:
    """Get the build tool configuration list"""
    return BUILD_TOOLS_CONFIG
