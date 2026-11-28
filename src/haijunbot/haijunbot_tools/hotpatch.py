# -*- coding: utf-8 -*-
"""hotpatch tool module

Provides arbitrary code hot-patching capability: hot-update/inject the code of any
Python module/function within a running HaijunBot process, taking effect immediately without restarting the process.

Supports two modes of use:
1. Apply modified code (reload): after code has been written to disk via edit/write, hot-update
   the specified module (supports batch multi-module); after reload, automatically rebind existing class instances to the new class,
   so new methods take effect immediately.
2. Temporarily inject code (debugging itself): inject arbitrary statements/code blocks/functions/brand-new modules from memory,
   without writing to disk or persisting, valid only for this run. The namespace injects agent / sys / globals,
   allowing access to/modification of any in-process object inside or outside the agent.

Implementation principles:
- importlib.reload re-executes existing module code;
- types.ModuleType + exec dynamically creates a module from in-memory code and registers it in sys.modules;
- gc.get_objects() traverses the heap and rebinds old class instances' __class__ to the new class (automatically switching to new methods);
- sys.modules cleanup + importlib.invalidate_caches handles dependencies and newly added files;
- All exceptions are caught and returned as error information; never throws exceptions to the Agent main flow.
"""

import gc
import importlib
import os
import shutil
import sys
import types
from typing import Any, Dict, List

from haijunbot.haijunbot_utils.output import PrettyOutput


class HotpatchTool:
    """Runtime hot-patch tool: hot-updates/injects arbitrary Python code and takes effect immediately"""

    name = "hotpatch"
    description = (
        "Arbitrary code hot-patch: hot-update/inject arbitrary Python code within a running HaijunBot process, taking effect immediately, "
        "without restarting the process. Two modes: 1) module_name hot-updates an existing module (supports comma-separated batch multi-module; "
        "after reload, existing class instances are automatically rebound to the new class); 2) code temporarily injects arbitrary statements/code blocks/functions/brand-new modules "
        "(without writing to disk or persisting; the namespace injects agent/sys/globals, allowing access to any object inside or outside the agent). "
        "Suited to adjusting its own behavior at runtime in self-evolution scenarios."
    )
    parameters = {
        "type": "object",
        "properties": {
            "module_name": {
                "type": "string",
                "description": "Mode 1: name of the existing module to hot-update (e.g., haijunbot.haijunbot_tools.load_rule); "
                "supports comma-separated batch multi-module, e.g., 'a,b,c'. Choose one of this and new_module_name",
            },
            "file_path": {
                "type": "string",
                "description": "Mode 1: module file path, from which the module name is derived (choose one of this and module_name)",
            },
            "new_module_name": {
                "type": "string",
                "description": "Mode 2: name of the brand-new module to inject (e.g., my_plugin); together with code, creates from memory "
                "a new module that can be imported immediately after being registered in sys.modules",
            },
            "code": {
                "type": "string",
                "description": "Mode 2: the code to inject. Can be any statement/code block (e.g., print(agent.data)), "
                "a function definition (def f(): ...), or, together with new_module_name, the source of a new module. The namespace injects "
                "agent/sys/globals, allowing access to runtime objects",
            },
            "clear_cache": {
                "type": "boolean",
                "description": "Mode 1: whether to clear the module cache from sys.modules and re-import; "
                "defaults to false (uses importlib.reload). Set to true when the module has dependents that need to be forcibly refreshed",
            },
            "rebind_instances": {
                "type": "boolean",
                "description": "Mode 1: whether to automatically rebind existing class instances' __class__ to the new class, "
                "so new methods take effect immediately. Defaults to true",
            },
        },
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the hot patch

        Parameters:
            args (Dict): a dict containing module_name / file_path / new_module_name / code /
                         clear_cache / rebind_instances

        Returns:
            Dict[str, Any]: a dict containing the success status, patch result, or error information
        """
        try:
            module_name = (args.get("module_name") or "").strip()
            new_module_name = (args.get("new_module_name") or "").strip()
            file_path = (args.get("file_path") or "").strip()
            code = args.get("code")
            clear_cache = bool(args.get("clear_cache", False))
            rebind_instances = bool(args.get("rebind_instances", True))

            # Mode 2: inject a brand-new module (new_module_name + code)
            if new_module_name:
                if not code:
                    return self._err("code must be provided when injecting a brand-new module")
                return self._inject_new_module(new_module_name, code)

            # Mode 2: execute arbitrary statements/code block (code only, no module_name/new_module_name)
            if code is not None and not module_name and not file_path:
                return self._execute_statement(code, args)

            # Mode 1: hot-update an existing module (batch supported)
            if not module_name and file_path:
                module_name = self._derive_module_name(file_path)
            if not module_name:
                return self._err("One of module_name, new_module_name, or code must be provided")

            return self._apply_patch(module_name, clear_cache, rebind_instances)
        except Exception as e:
            return self._err(f"Hot patch failed: {str(e)}")

    # ------------------------------------------------------------------
    # Mode 2: inject a brand-new module
    # ------------------------------------------------------------------
    def _inject_new_module(self, module_name: str, code: str) -> Dict[str, Any]:
        """Inject a brand-new module from in-memory code; it can be imported immediately after being registered in sys.modules."""
        try:
            module = types.ModuleType(module_name)
            exec(compile(code, f"<hotpatch:{module_name}>", "exec"), module.__dict__)
            sys.modules[module_name] = module
            PrettyOutput.auto_print(f"🧩 Injected brand-new module: {module_name}")
            return {
                "success": True,
                "module": module_name,
                "mode": "new_module",
                "error": "",
            }
        except Exception as e:
            return {
                "success": False,
                "module": module_name,
                "mode": "new_module",
                "error": f"Failed to inject brand-new module {module_name}: {str(e)}",
            }

    # ------------------------------------------------------------------
    # Mode 2: execute arbitrary statements/code block (with agent context)
    # ------------------------------------------------------------------
    def _execute_statement(self, code: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute arbitrary statements/code block, with the namespace injecting agent/sys/globals.

        Supports arbitrary multi-line statements/code blocks (e.g., print(agent.data)), not limited to function/module definitions.
        """
        try:
            agent = args.get("agent")
            namespace: Dict[str, Any] = {
                "agent": agent,
                "sys": sys,
                "globals": globals,
                "__builtins__": __builtins__,
            }
            exec(compile(code, "<hotpatch:statement>", "exec"), namespace)

            # If the code defines callable objects, inject them into this module's namespace for later reference
            func_names = [
                k
                for k, v in namespace.items()
                if callable(v) and not k.startswith("__")
            ]
            if func_names:
                for fn in func_names:
                    globals()[fn] = namespace[fn]
            PrettyOutput.auto_print("⚡ Executed injected code block")
            return {
                "success": True,
                "mode": "statement",
                "defined": func_names,
                "error": "",
            }
        except Exception as e:
            return {
                "success": False,
                "mode": "statement",
                "defined": [],
                "error": f"Failed to execute injected code: {str(e)}",
            }

    # ------------------------------------------------------------------
    # Mode 1: hot-update an existing module (batch + instance rebinding)
    # ------------------------------------------------------------------
    def _apply_patch(
        self, module_name: str, clear_cache: bool, rebind_instances: bool
    ) -> Dict[str, Any]:
        """Hot-update the specified module(s); supports comma-separated batch multi-module.

        Returns a dict: {"success": bool, "module": str, "mode": "reload",
                    "reloaded": [...], "rebound": int, "error": str}
        """
        names = [n.strip() for n in module_name.split(",") if n.strip()]
        if not names:
            return self._err("module_name is empty")
        reloaded: List[str] = []
        rebound_total = 0
        errors: List[str] = []
        for name in names:
            try:
                rebound = self._reload_one(name, clear_cache, rebind_instances)
                reloaded.append(name)
                rebound_total += rebound
            except Exception as e:
                errors.append(f"{name}: {str(e)}")
        success = not errors
        result: Dict[str, Any] = {
            "success": success,
            "module": module_name,
            "mode": "reload",
            "reloaded": reloaded,
            "rebound": rebound_total,
            "error": "; ".join(errors),
        }
        if success:
            PrettyOutput.auto_print(
                f"🔧 Hot patch successful: {module_name} (reloaded {len(reloaded)}, rebound instances {rebound_total})"
            )
        return result

    def _reload_one(
        self, module_name: str, clear_cache: bool, rebind_instances: bool
    ) -> int:
        """Reload a single module and return the number of rebound instances."""
        importlib.invalidate_caches()
        old_classes: Dict[str, type] = {}
        if rebind_instances and module_name in sys.modules:
            old_classes = self._collect_classes(sys.modules[module_name], module_name)

        if clear_cache:
            sys.modules.pop(module_name, None)
            module = importlib.import_module(module_name)
        else:
            if module_name in sys.modules:
                # Clear the pyc cache to avoid reload reusing stale bytecode (source changed but pyc not invalidated)
                self._clear_pycache(module_name)
                module = importlib.reload(sys.modules[module_name])
            else:
                module = importlib.import_module(module_name)

        if rebind_instances and old_classes:
            return self._rebind_instances(module, module_name, old_classes)
        return 0

    @staticmethod
    def _clear_pycache(module_name: str) -> None:
        """Delete the __pycache__ under the directory corresponding to the module's __file__, forcing reload to recompile the source."""
        module = sys.modules.get(module_name)
        if module is None:
            return
        file_path = getattr(module, "__file__", None)
        if not file_path:
            return
        pycache = os.path.join(os.path.dirname(file_path), "__pycache__")
        if os.path.isdir(pycache):
            try:
                shutil.rmtree(pycache)
            except OSError:
                pass

    @staticmethod
    def _collect_classes(module: types.ModuleType, module_name: str) -> Dict[str, type]:
        """Collect classes defined within the module (name -> class object)."""
        return {
            name: cls
            for name, cls in module.__dict__.items()
            if isinstance(cls, type) and getattr(cls, "__module__", None) == module_name
        }

    def _rebind_instances(
        self,
        module: types.ModuleType,
        module_name: str,
        old_classes: Dict[str, type],
    ) -> int:
        """Rebind old class instances' __class__ to the new class, so new methods take effect immediately."""
        new_classes = self._collect_classes(module, module_name)
        if not new_classes:
            return 0
        rebound = 0
        for obj in gc.get_objects():
            cls = type(obj)
            if cls.__module__ != module_name:
                continue
            for name, new_cls in new_classes.items():
                old_cls = old_classes.get(name)
                # Exactly match the old class (excluding subclasses), and ensure old and new are indeed different objects
                if old_cls is not None and cls is old_cls and cls is not new_cls:
                    try:
                        obj.__class__ = new_cls
                        rebound += 1
                    except TypeError:
                        pass  # __slots__ / C types cannot be rebound; skip
                    break
        return rebound

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------
    def _derive_module_name(self, file_path: str) -> str:
        """Derive the module name from a file path.

        Prefer deriving it from the path within the haijunbot package (e.g., src/haijunbot/haijunbot_tools/x.py →
        haijunbot.haijunbot_tools.x); otherwise use the file stem as the module name.
        """
        try:
            p = os.path.abspath(os.path.expanduser(file_path))
            parts = p.replace(os.sep, "/").split("/")
            for i in range(len(parts) - 1, -1, -1):
                if parts[i] == "haijunbot" and i + 1 < len(parts):
                    sub = parts[i + 1 :]
                    if sub[-1].endswith(".py"):
                        sub[-1] = sub[-1][:-3]
                    return ".".join(sub)
            return os.path.splitext(os.path.basename(p))[0]
        except Exception:
            return os.path.splitext(os.path.basename(file_path))[0]

    @staticmethod
    def _err(msg: str) -> Dict[str, Any]:
        return {"success": False, "stdout": "", "stderr": msg}
