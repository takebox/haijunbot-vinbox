"""LSP language server configuration reader module (single source of configuration).

Configuration comes uniformly from the ``lsp.languages`` section of ``~/.haijunbot/config.yaml``; haijunbot-lsp
(CLI / daemon) and the web gateway (Monaco editor) share this module to avoid config drift between the two.

Configuration structure::

    lsp:
      languages:
        python:
          command: pylsp
          args: []
          file_extensions: [".py", ".pyi"]
          monaco_language: python
          root_markers: ["pyproject.toml", ".git"]
          initialization_options: {}
          install_hint: "pip install python-lsp-server"

Field descriptions:

    command                 str        Startup command (required; a string, not a list,
                                       to avoid shell parsing; put arguments in args)
    args                    list[str]  Startup arguments (optional, default [])
    file_extensions         list[str]  File extensions (optional, default []),
                                       used to match languages by extension
    monaco_language         str        Corresponding Monaco language id (optional, defaults to the language name)
    root_markers            list[str]  Workspace root marker files (optional, default [])
    initialization_options  dict       Options passed to the LSP initialize call (optional, default {})
    install_hint            str        Hint text shown when the server is not installed (optional, default "")

User configuration overrides the built-in default configuration (``DEFAULT_LANGUAGES``); language names are case-insensitive.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from haijunbot.haijunbot_utils.config import get_global_config_data


@dataclass
class LanguageConfig:
    """LSP server configuration for a single language.

    Attributes:
        command: The LSP server executable command.
        args: The list of startup arguments.
        file_extensions: The list of supported file extensions.
        monaco_language: The corresponding Monaco language id, defaults to the language name.
        root_markers: Marker files used to determine the workspace root.
        initialization_options: Options passed to the LSP ``initialize`` call.
        install_hint: Hint text shown when the server is not installed.
    """

    command: str
    args: List[str] = field(default_factory=list)
    file_extensions: List[str] = field(default_factory=list)
    monaco_language: str = ""
    root_markers: List[str] = field(default_factory=list)
    initialization_options: Dict[str, Any] = field(default_factory=dict)
    install_hint: str = ""


@dataclass
class LSPConfig:
    """LSP configuration data class.

    Attributes:
        languages: Dictionary of language configurations, keyed by language name with LanguageConfig values.
    """

    languages: Dict[str, LanguageConfig]


# Built-in default language configurations, used when not configured in config.yaml.
# A user configuration with the same name fully overrides the corresponding default entry.
DEFAULT_LANGUAGES: Dict[str, LanguageConfig] = {
    "python": LanguageConfig(
        command="pylsp",
        args=[],
        file_extensions=[".py", ".pyi"],
        monaco_language="python",
        root_markers=["pyproject.toml", "setup.py", "setup.cfg", ".git"],
        install_hint="pip install python-lsp-server",
    ),
    "go": LanguageConfig(
        command="gopls",
        args=[],
        file_extensions=[".go"],
        monaco_language="go",
        root_markers=["go.mod", "go.sum", ".git"],
        install_hint="go install golang.org/x/tools/gopls@latest",
    ),
    "typescript": LanguageConfig(
        command="typescript-language-server",
        args=["--stdio"],
        file_extensions=[".ts", ".tsx"],
        monaco_language="typescript",
        root_markers=["package.json", "tsconfig.json", ".git"],
        install_hint="npm install -g typescript-language-server typescript",
    ),
    "javascript": LanguageConfig(
        command="typescript-language-server",
        args=["--stdio"],
        file_extensions=[".js", ".jsx", ".mjs", ".cjs"],
        monaco_language="javascript",
        root_markers=["package.json", "jsconfig.json", ".git"],
        install_hint="npm install -g typescript-language-server typescript",
    ),
    "rust": LanguageConfig(
        command="rust-analyzer",
        args=[],
        file_extensions=[".rs"],
        monaco_language="rust",
        root_markers=["Cargo.toml", "Cargo.lock", ".git"],
        install_hint="rustup component add rust-analyzer",
    ),
    "c": LanguageConfig(
        command="clangd",
        args=[],
        file_extensions=[".c", ".h"],
        monaco_language="c",
        root_markers=["compile_commands.json", "CMakeLists.txt", ".git"],
        install_hint="Install clangd (e.g. apt install clangd)",
    ),
    "cpp": LanguageConfig(
        command="clangd",
        args=[],
        file_extensions=[".cpp", ".hpp", ".cc", ".cxx", ".hh"],
        monaco_language="cpp",
        root_markers=["compile_commands.json", "CMakeLists.txt", ".git"],
        install_hint="Install clangd (e.g. apt install clangd)",
    ),
    "lua": LanguageConfig(
        command="lua-language-server",
        args=[],
        file_extensions=[".lua"],
        monaco_language="lua",
        root_markers=[".luarc.json", ".git"],
        install_hint="Install lua-language-server",
    ),
    "bash": LanguageConfig(
        command="bash-language-server",
        args=["start"],
        file_extensions=[".sh", ".bash", ".zsh"],
        monaco_language="shell",
        root_markers=[".git"],
        install_hint="npm install -g bash-language-server",
    ),
    "ruby": LanguageConfig(
        command="solargraph",
        args=["stdio"],
        file_extensions=[".rb"],
        monaco_language="ruby",
        root_markers=["Gemfile", ".git"],
        install_hint="gem install solargraph",
    ),
    "php": LanguageConfig(
        command="intelephense",
        args=["--stdio"],
        file_extensions=[".php"],
        monaco_language="php",
        root_markers=["composer.json", ".git"],
        install_hint="npm install -g intelephense",
    ),
    "html": LanguageConfig(
        command="vscode-html-language-server",
        args=["--stdio"],
        file_extensions=[".html", ".htm"],
        monaco_language="html",
        root_markers=[".git"],
        install_hint="npm install -g vscode-langservers-extracted",
    ),
    "css": LanguageConfig(
        command="vscode-css-language-server",
        args=["--stdio"],
        file_extensions=[".css", ".scss", ".less"],
        monaco_language="css",
        root_markers=[".git"],
        install_hint="npm install -g vscode-langservers-extracted",
    ),
}


def _as_str_list(value: Any) -> List[str]:
    """Normalize a config value into a list of strings; return an empty list when the type does not match."""
    if isinstance(value, list) and all(isinstance(i, str) for i in value):
        return [i for i in value if isinstance(i, str)]
    return []


def _parse_language(name: str, raw: Any) -> Optional[LanguageConfig]:
    """Parse a single language configuration.

    Args:
        name: The language name (key in config.yaml).
        raw: The raw configuration object.

    Returns:
        A LanguageConfig; returns None when the format is invalid (the caller logs a warning and skips it).
    """
    if not isinstance(raw, dict):
        return None

    command = raw.get("command")
    if not isinstance(command, str) or not command.strip():
        return None

    monaco_language = raw.get("monaco_language")
    if not isinstance(monaco_language, str) or not monaco_language.strip():
        monaco_language = name

    initialization_options = raw.get("initialization_options")
    if not isinstance(initialization_options, dict):
        initialization_options = {}

    install_hint = raw.get("install_hint")
    if not isinstance(install_hint, str):
        install_hint = ""

    return LanguageConfig(
        command=command.strip(),
        args=_as_str_list(raw.get("args")),
        file_extensions=_as_str_list(raw.get("file_extensions")),
        monaco_language=monaco_language.strip(),
        root_markers=_as_str_list(raw.get("root_markers")),
        initialization_options=initialization_options,
        install_hint=install_hint,
    )


class LSPConfigReader:
    """LSP configuration reader.

    Reads ``lsp.languages`` from the global configuration data (``~/.haijunbot/config.yaml``),
    merges it with the built-in default configuration, giving user configuration priority. Provides language detection and configuration lookup.
    """

    def load_config(self) -> LSPConfig:
        """Load the LSP configuration: built-in defaults + user configuration (user takes priority).

        Returns:
            An LSPConfig object. Language entries with invalid formats are skipped without affecting other languages.
        """
        languages: Dict[str, LanguageConfig] = {
            name: cfg for name, cfg in DEFAULT_LANGUAGES.items()
        }

        config_data = get_global_config_data()
        lsp_data = config_data.get("lsp") or {}
        if not isinstance(lsp_data, dict):
            return LSPConfig(languages=languages)

        languages_data = lsp_data.get("languages") or {}
        if not isinstance(languages_data, dict):
            return LSPConfig(languages=languages)

        for lang_name, lang_data in languages_data.items():
            if not isinstance(lang_name, str) or not lang_name.strip():
                continue
            parsed = _parse_language(lang_name.strip(), lang_data)
            if parsed is None:
                continue
            # A user configuration fully overrides the default entry of the same name
            languages[lang_name.strip()] = parsed

        return LSPConfig(languages=languages)

    def get_language_config(self, language: str) -> Optional[LanguageConfig]:
        """Get the configuration for the specified language.

        Args:
            language: The language name (case-insensitive).

        Returns:
            A LanguageConfig object, or None if it does not exist.
        """
        if not isinstance(language, str) or not language.strip():
            return None
        config = self.load_config()
        target = language.strip()
        if target in config.languages:
            return config.languages[target]
        # Case-insensitive fallback
        lowered = target.lower()
        for name, cfg in config.languages.items():
            if name.lower() == lowered:
                return cfg
        return None

    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect the language from the file extension.

        Args:
            file_path: The file path.

        Returns:
            The language name, or None if it cannot be detected.
        """
        try:
            config = self.load_config()
        except Exception:
            return None
        ext = Path(file_path).suffix
        if not ext:
            return None
        for lang_name, lang_config in config.languages.items():
            if ext in lang_config.file_extensions:
                return lang_name
        return None
