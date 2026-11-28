# -*- coding: utf-8 -*-
"""
Compilation command handling module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

from haijunbot.haijunbot_utils.output import PrettyOutput


class CompileCommandsManager:
    """Compilation command manager"""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._compile_commands_cache: Optional[List[Dict[str, Any]]] = None
        self._compile_commands_path: Optional[Path] = None

    def _find_compile_commands(self) -> Optional[Path]:
        """
        Locate the compile_commands.json file.
        Search order:
        1. project_root / compile_commands.json
        2. project_root / build / compile_commands.json
        3. The parent directory of project_root and upward (up to 3 levels)
        """
        # First search under project_root
        candidates = [
            self.project_root / "compile_commands.json",
            self.project_root / "build" / "compile_commands.json",
        ]
        # Search upward (up to 3 levels)
        current = self.project_root.parent
        for _ in range(3):
            if current and current.exists():
                candidates.append(current / "compile_commands.json")
                current = current.parent
            else:
                break

        for path in candidates:
            if path.exists() and path.is_file():
                return path.resolve()
        return None

    def load_compile_commands(self) -> Optional[List[Dict[str, Any]]]:
        """
        Load the compile_commands.json file.
        If already cached, return the cached result directly.
        """
        if self._compile_commands_cache is not None:
            return self._compile_commands_cache

        compile_commands_path = self._find_compile_commands()
        if compile_commands_path is None:
            self._compile_commands_cache = []
            self._compile_commands_path = None
            return None

        try:
            with compile_commands_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self._compile_commands_cache = data
                    self._compile_commands_path = compile_commands_path
                    PrettyOutput.auto_print(
                        f"📋 [c2rust-transpiler][compile_commands] Loaded: {compile_commands_path} ({len(data)} records)"
                    )
                    return data
        except Exception as e:
            PrettyOutput.auto_print(
                f"❌ [c2rust-transpiler][compile_commands] Load failed: {compile_commands_path}: {e}"
            )
            self._compile_commands_cache = []
            self._compile_commands_path = None
            return None

        self._compile_commands_cache = []
        self._compile_commands_path = None
        return None

    def extract_compile_flags(self, c_file_path: Union[str, Path]) -> Optional[str]:
        """
        Extract the compile flags for the specified C file from compile_commands.json.

        If the compile_commands.json contains an arguments field, join that array with spaces and return it.
        If only a command field is present, return the command string directly.

        Return format:
        - If arguments exists: a space-joined argument string, e.g. "-I/usr/include -DDEBUG"
        - If only command: the full compile command string, e.g. "gcc -I/usr/include -DDEBUG file.c"

        If not found or parsing fails, return None.
        """
        compile_commands = self.load_compile_commands()
        if not compile_commands:
            return None

        # Normalize the target file path
        try:
            target_path = Path(c_file_path)
            if not target_path.is_absolute():
                target_path = (self.project_root / target_path).resolve()
            target_path = target_path.resolve()
        except Exception:
            return None

        # Find the matching compile command
        for entry in compile_commands:
            if not isinstance(entry, dict):
                continue

            entry_file = entry.get("file")
            if not entry_file:
                continue

            try:
                entry_path = Path(entry_file)
                if not entry_path.is_absolute() and entry.get("directory"):
                    directory = entry.get("directory")
                    if directory is not None:
                        entry_path = (Path(directory) / entry_path).resolve()
                entry_path = entry_path.resolve()

                # Path matching (supports relative and absolute paths)
                if entry_path == target_path:
                    # If arguments exists, join with spaces and return
                    arguments = entry.get("arguments")
                    if isinstance(arguments, list):
                        # Filter out empty strings, then join with spaces
                        args = [str(arg) for arg in arguments if arg]
                        return " ".join(args) if args else None
                    # If only command is present, return the command string directly
                    elif entry.get("command"):
                        command = entry.get("command", "")
                        return command if command else None
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.transpiler_compile",
                    function="extract_compile_flags",
                )
                continue

        return None
