# -*- coding: utf-8 -*-
"""LSP semantic query tool.

Purpose:
- Provide CodeAgent with language-server-based semantic capabilities (definition/references/implementation/diagnostics/fix suggestions);
- Reuse the existing daemon client in haijunbot_lsp instead of reimplementing the LSP protocol.

Design points:
- A single tool with action enum dispatch, to avoid registering one tool per LSP method and polluting the tool list;
- LLM-friendly parameters: prefer symbol names (symbol_name) over exact line/column numbers;
- Language and project root are inferred automatically; when omitted, derive them from the file extension and containing directory;
- Uniformly returns {"success": bool, "stdout": str, "stderr": str};
- Any exception degrades to success=False and does not interrupt the Agent.

Parameters:
- action (str): query type, see the enum in parameters
- file_path (str): target file path (relative or absolute)
- symbol_name (str): symbol name (used by find_*/code_action)
- query (str): search term for workspace_symbols
- line / column (int): only needed by hover (1-based, column defaults to 0)
- language (str): language name; when omitted, inferred from the extension
- project_path (str): project root directory; when omitted, uses the directory containing the file

Returns:
- success (bool)
- stdout (str): JSON text
- stderr (str)
"""

import asyncio
import dataclasses
import json
import os
import threading
from typing import Any, Dict, List, Optional

from haijunbot.haijunbot_lsp.config import LSPConfigReader
from haijunbot.haijunbot_lsp.daemon_client import LSPDaemonClient
from haijunbot.haijunbot_utils.config import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput


def _run_async(coro: Any) -> Any:
    """Run a coroutine in a synchronous context, supporting the case where the current thread already has an event loop.

    - If the current thread has no running event loop: use asyncio.run directly;
    - If the current thread already has a running event loop (such as inside a web gateway): run it in a separate thread
      to avoid "RuntimeError: This event loop is already running".
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}

    def _worker() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as e:  # noqa: BLE001 - need to pass the exception back as-is
            result["error"] = e

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join()

    if "error" in result:
        raise result["error"]
    return result.get("value")


def _to_jsonable(obj: Any) -> Any:
    """Convert dataclass / list / tuple and similar into a JSON-serializable structure."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return _to_jsonable(dataclasses.asdict(obj))
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


class lsp:
    """LSP semantic query tool (definition/references/implementation/diagnostics/fix suggestions)."""

    name = "lsp"
    description = (
        "Perform code semantic queries through a language server (LSP), which is more accurate than text search. "
        "action possible values: document_symbols (list file symbols), "
        "find_definition (look up a definition by symbol name), find_references (look up references by symbol name), "
        "find_implementation (look up the implementation by symbol name), find_type_definition (look up the type definition by symbol name), "
        "find_callers (who calls this symbol), find_callees (what this symbol calls), "
        "hover (type/documentation info, requires line), diagnostic (errors and warnings), "
        "code_action (get fix suggestions by symbol name), workspace_symbols (search symbols across the whole workspace, requires query). "
        "Prefer symbol names (symbol_name) over line/column numbers; for plain text search use rg/grep instead."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "document_symbols",
                    "find_definition",
                    "find_references",
                    "find_implementation",
                    "find_type_definition",
                    "find_callers",
                    "find_callees",
                    "hover",
                    "diagnostic",
                    "code_action",
                    "workspace_symbols",
                ],
                "description": "The type of LSP query to execute",
            },
            "file_path": {
                "type": "string",
                "description": "Target file path (relative or absolute); required for all actions except workspace_symbols",
            },
            "symbol_name": {
                "type": "string",
                "description": "Symbol name (used by find_*/code_action; preferred over line/column numbers)",
            },
            "query": {
                "type": "string",
                "description": "Symbol search term for workspace_symbols",
            },
            "line": {
                "type": "number",
                "description": "Line number (1-based; only needed by hover)",
            },
            "column": {
                "type": "number",
                "description": "Column number (1-based; only needed by hover, defaults to 1)",
            },
            "language": {
                "type": "string",
                "description": "Language name (such as python/go/rust); when omitted, inferred automatically from the file extension",
            },
            "project_path": {
                "type": "string",
                "description": "Project root directory; when omitted, uses the directory containing file_path",
            },
        },
        "required": ["action"],
    }

    @staticmethod
    def check() -> bool:
        """Tool availability check: launches the daemon on demand and is always available."""
        return True

    def _fail(self, message: str) -> Dict[str, Any]:
        return {"success": False, "stdout": "", "stderr": message}

    @staticmethod
    def _resolve_path(path: str) -> str:
        return os.path.abspath(os.path.expanduser(path))

    def _resolve_language(
        self, reader: LSPConfigReader, language: Optional[str], file_path: Optional[str]
    ) -> Optional[str]:
        """Determine the language: an explicit value takes priority, otherwise infer from the file extension."""
        if language and str(language).strip():
            return str(language).strip()
        if file_path:
            return reader.detect_language(file_path)
        return None

    def _supported_languages(self, reader: LSPConfigReader) -> List[str]:
        try:
            config = reader.load_config()
            return sorted(config.languages.keys())
        except Exception as e:  # noqa: BLE001
            save_exception(
                e, module="haijunbot_tools.lsp", function="_supported_languages"
            )
            return []

    def _install_hint(self, reader: LSPConfigReader, language: str) -> str:
        try:
            lang_config = reader.get_language_config(language)
            if lang_config and lang_config.install_hint:
                return f" Install hint: {lang_config.install_hint}"
        except Exception as e:  # noqa: BLE001
            save_exception(e, module="haijunbot_tools.lsp", function="_install_hint")
        return ""

    def _dispatch(
        self,
        client: LSPDaemonClient,
        action: str,
        language: str,
        project_path: str,
        file_path: Optional[str],
        symbol_name: Optional[str],
        query: Optional[str],
        line: Optional[int],
        column: Optional[int],
    ) -> Any:
        """Dispatch to the corresponding LSPDaemonClient method based on the action (returns a coroutine)."""
        if action == "document_symbols":
            return client.document_symbol(language, project_path, file_path or "")
        if action == "find_definition":
            return client.definition_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "find_references":
            return client.references_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "find_implementation":
            return client.implementation_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "find_type_definition":
            return client.type_definition_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "find_callers":
            return client.incoming_calls_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "find_callees":
            return client.outgoing_calls_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "hover":
            # The LSP protocol and client use 0-based line/column; the tool exposes 1-based line numbers, so convert here
            # (consistent with the hover command in eli.py)
            line_1based = int(line) if line is not None else 1
            column_1based = int(column) if column is not None else 1
            return client.hover(
                language,
                project_path,
                file_path or "",
                max(line_1based - 1, 0),
                max(column_1based - 1, 0),
            )
        if action == "diagnostic":
            return client.diagnostic(language, project_path, file_path or "")
        if action == "code_action":
            return client.code_action_by_name(
                language, project_path, file_path or "", symbol_name or ""
            )
        if action == "workspace_symbols":
            return client.workspace_symbol(language, project_path, query or "")
        raise ValueError(f"Unsupported action: {action}")

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Under the v1.0 protocol the agent is injected into args; ignore it
        if isinstance(args, dict):
            args = {k: v for k, v in args.items() if k != "agent"}

        try:
            action = args.get("action")
            if not isinstance(action, str) or not action.strip():
                return self._fail("Missing or invalid action argument")
            action = action.strip()

            file_path_arg = args.get("file_path")
            symbol_name = args.get("symbol_name")
            query = args.get("query")
            language_arg = args.get("language")
            project_path_arg = args.get("project_path")
            line = args.get("line")
            column = args.get("column")

            reader = LSPConfigReader()

            # workspace_symbols does not require file_path
            file_path: Optional[str] = None
            if isinstance(file_path_arg, str) and file_path_arg.strip():
                file_path = self._resolve_path(file_path_arg)

            if action != "workspace_symbols" and not file_path:
                return self._fail("Missing file_path argument")

            language = self._resolve_language(reader, language_arg, file_path)
            if not language:
                supported = self._supported_languages(reader)
                return self._fail(
                    "Unable to detect the language; please specify it explicitly with the language argument. "
                    f"Currently supported languages: {', '.join(supported) if supported else '(none)'}"
                )

            # project_path: an explicit value takes priority, otherwise use the directory containing the file (workspace_symbols requires it explicitly)
            if isinstance(project_path_arg, str) and project_path_arg.strip():
                project_path = self._resolve_path(project_path_arg)
            elif file_path:
                project_path = os.path.dirname(file_path)
            else:
                project_path = os.getcwd()

            # Pre-validate actions that require a symbol name
            if action in (
                "find_definition",
                "find_references",
                "find_implementation",
                "find_type_definition",
                "find_callers",
                "find_callees",
                "code_action",
            ) and (not isinstance(symbol_name, str) or not symbol_name.strip()):
                return self._fail(f"action={action} requires the symbol_name argument")

            if action == "workspace_symbols" and (
                not isinstance(query, str) or not query.strip()
            ):
                return self._fail("action=workspace_symbols requires the query argument")

            client = LSPDaemonClient()
            coro = self._dispatch(
                client,
                action,
                language,
                project_path,
                file_path,
                symbol_name,
                query,
                line,
                column,
            )
            result = _run_async(coro)

            out_obj: Dict[str, Any] = {
                "action": action,
                "language": language,
                "project_path": project_path,
                "file_path": file_path,
                "result": _to_jsonable(result),
            }
            stdout = json.dumps(out_obj, ensure_ascii=False, indent=2)
            return {"success": True, "stdout": stdout, "stderr": ""}

        except Exception as e:  # noqa: BLE001 - any exception degrades
            save_exception(e, module="haijunbot_tools.lsp", function="execute")
            message = str(e)
            hint = ""
            try:
                lang = locals().get("language")
                if lang:
                    hint = self._install_hint(LSPConfigReader(), lang)
            except Exception as inner:  # noqa: BLE001
                save_exception(inner, module="haijunbot_tools.lsp", function="execute")
            PrettyOutput.auto_print(f"❌ LSP query failed: {message}")
            return self._fail(f"LSP query failed: {message}{hint}")
