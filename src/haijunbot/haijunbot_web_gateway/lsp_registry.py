"""LSP language server registry (read from global configuration).

This module converts the ``lsp.languages`` configuration in ``~/.haijunbot/config.yaml``
into the spec structure required by the Web gateway, for use by ``app.py``
(``GET /api/lsp/servers``, ``WS /api/lsp/{id}``) and ``lsp_bridge.py`` (process pool).

The configuration source is unique: ``haijunbot.haijunbot_lsp.config.LSPConfigReader``
(shared with haijunbot-lsp). Adding a new language only requires adding an entry under
``lsp.languages`` in ``~/.haijunbot/config.yaml`` without modifying any code.

spec fields (converted from LanguageConfig):

    id                      str        Language name, e.g. "python" (i.e. the config key)
    monacoLanguage          str        Corresponding Monaco language id
    command                 list[str]  ``[command] + args``, for create_subprocess_exec
    extensions              list[str]  File extensions
    args                    list[str]  Startup arguments
    rootMarkers             list[str]  workspace root marker files
    initializationOptions   dict       Options passed to initialize
    installHint             str        Hint text shown when not installed
    _source                 str        Fixed to "config", marks the source
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _to_spec(language: str, cfg: Any) -> Dict[str, Any]:
    """Convert a LanguageConfig into the spec dict used by the Web gateway."""
    args = list(cfg.args or [])
    command = [cfg.command] + args
    return {
        "id": language,
        "monacoLanguage": cfg.monaco_language or language,
        "command": command,
        "args": args,
        "extensions": list(cfg.file_extensions or []),
        "rootMarkers": list(cfg.root_markers or []),
        "initializationOptions": dict(cfg.initialization_options or {}),
        "installHint": cfg.install_hint or "",
        "_source": "config",
    }


def load_lsp_server_specs() -> Dict[str, Dict[str, Any]]:
    """Load all LSP language server configurations.

    Returns:
        ``{server_id: spec}``; returns an empty dict if configuration reading fails (no exception raised).
    """
    try:
        from haijunbot.haijunbot_lsp.config import LSPConfigReader

        config = LSPConfigReader().load_config()
    except Exception as e:  # pragma: no cover - environment failure fallback
        logger.warning("[lsp_registry] Failed to read LSP configuration, returning empty config: %s", e)
        return {}

    specs: Dict[str, Dict[str, Any]] = {}
    for language, cfg in config.languages.items():
        if not cfg.command:
            logger.warning("[lsp_registry] Language %s is missing a command, skipped", language)
            continue
        specs[language] = _to_spec(language, cfg)
    return specs


def get_lsp_server_spec(server_id: str) -> Optional[Dict[str, Any]]:
    """Get a single language server configuration by id.

    Args:
        server_id: Language name, e.g. "python".

    Returns:
        The spec dict; returns None if it does not exist.
    """
    if not isinstance(server_id, str) or not server_id.strip():
        return None
    return load_lsp_server_specs().get(server_id.strip())


def list_lsp_server_ids() -> List[str]:
    """Return all registered server ids (sorted)."""
    return sorted(load_lsp_server_specs().keys())
