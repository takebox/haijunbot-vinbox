# -*- coding: utf-8 -*-
"""hotpatch tool unit tests

Covers two usage modes + multiple modules + automatic switching of existing class instances.
"""

import importlib
import importlib.util
import sys
import types

import pytest

from haijunbot.haijunbot_tools.hotpatch import HotpatchTool


@pytest.fixture
def tool():
    """Create HotpatchTool instance (avoid full initialization)."""
    return object.__new__(HotpatchTool)


def _load_module(name: str, path) -> types.ModuleType:
    """Add module directory to sys.path and load module from file.

    After adding directory to sys.path, reload can find the module through the import system
    (consistent with the real haijunbot module being on sys.path).
    """
    importlib.util.spec_from_file_location  # Ensure importlib.util is imported
    sys.path.insert(0, str(path.parent))
    module = importlib.import_module(name)
    return module


# ------------------------------------------------------------------
# Mode 1: Hot update existing module (reload)
# ------------------------------------------------------------------
def test_reload_module_effective(tool, tmp_path):
    """After modifying module file, reload, new code takes effect immediately."""
    mod_file = tmp_path / "demo_mod.py"
    mod_file.write_text("VALUE = 1\n", encoding="utf-8")

    # Dynamically load module
    module = _load_module("demo_mod", mod_file)
    assert module.VALUE == 1

    # Modify disk file
    mod_file.write_text("VALUE = 42\n", encoding="utf-8")

    # reload takes effect
    result = tool._apply_patch("demo_mod", clear_cache=False, rebind_instances=True)
    assert result["success"] is True
    assert "demo_mod" in result["reloaded"]
    assert sys.modules["demo_mod"].VALUE == 42

    sys.modules.pop("demo_mod", None)


def test_reload_batch_multiple_modules(tool, tmp_path):
    """Batch multi-module reload, single failure does not affect others."""
    mod_a = tmp_path / "batch_a.py"
    mod_b = tmp_path / "batch_b.py"
    mod_a.write_text("A = 1\n", encoding="utf-8")
    mod_b.write_text("B = 1\n", encoding="utf-8")

    for name, path in (("batch_a", mod_a), ("batch_b", mod_b)):
        _load_module(name, path)

    mod_a.write_text("A = 100\n", encoding="utf-8")
    mod_b.write_text("B = 200\n", encoding="utf-8")

    result = tool._apply_patch(
        "batch_a,batch_b", clear_cache=False, rebind_instances=True
    )
    assert result["success"] is True
    assert set(result["reloaded"]) == {"batch_a", "batch_b"}
    assert sys.modules["batch_a"].A == 100
    assert sys.modules["batch_b"].B == 200

    sys.modules.pop("batch_a", None)
    sys.modules.pop("batch_b", None)


def test_reload_rebind_existing_instance(tool, tmp_path):
    """Existing class instances automatically switch to new methods (core capability)."""
    mod_file = tmp_path / "demo_cls.py"
    mod_file.write_text(
        "class Greeter:\n    def greet(self):\n        return 'old'\n",
        encoding="utf-8",
    )

    module = _load_module("demo_cls", mod_file)

    inst = module.Greeter()
    assert inst.greet() == "old"

    # Modify class method
    mod_file.write_text(
        "class Greeter:\n    def greet(self):\n        return 'new'\n",
        encoding="utf-8",
    )

    result = tool._apply_patch("demo_cls", clear_cache=False, rebind_instances=True)
    assert result["success"] is True
    assert result["rebound"] >= 1
    # Old instance automatically switches to new method
    assert inst.greet() == "new"

    sys.modules.pop("demo_cls", None)


def test_reload_rebind_disabled(tool, tmp_path):
    """rebind_instances=False does not rebind instances."""
    mod_file = tmp_path / "demo_norebind.py"
    mod_file.write_text(
        "class G:\n    def v(self):\n        return 'old'\n",
        encoding="utf-8",
    )
    module = _load_module("demo_norebind", mod_file)
    inst = module.G()

    mod_file.write_text(
        "class G:\n    def v(self):\n        return 'new'\n",
        encoding="utf-8",
    )
    result = tool._apply_patch(
        "demo_norebind", clear_cache=False, rebind_instances=False
    )
    assert result["success"] is True
    assert result["rebound"] == 0
    # Not rebound, still uses old class
    assert inst.v() == "old"

    sys.modules.pop("demo_norebind", None)


# ------------------------------------------------------------------
# Mode 2: Inject entirely new module
# ------------------------------------------------------------------
def test_inject_new_module(tool):
    """Injecting an entirely new module can be imported immediately."""
    result = tool._inject_new_module("my_probe", "def f():\n    return 'probe'\n")
    assert result["success"] is True
    assert "my_probe" in sys.modules
    my_probe = sys.modules["my_probe"]

    assert my_probe.f() == "probe"
    sys.modules.pop("my_probe", None)


# ------------------------------------------------------------------
# Mode 2: Execute arbitrary statements/code blocks
# ------------------------------------------------------------------
def test_execute_statement_access_agent(tool):
    """Execute arbitrary statements and access agent context."""

    class FakeAgent:
        data = {"key": "value"}

    agent = FakeAgent()
    result = tool._execute_statement(
        "print(agent.data['key'])",
        {"agent": agent},
    )
    assert result["success"] is True


def test_execute_statement_access_external_object(tool):
    """Access/modify objects outside agent (sys.modules global state)."""
    # Create an external module
    ext = types.ModuleType("ext_target")
    setattr(ext, "STATE", 0)
    sys.modules["ext_target"] = ext

    result = tool._execute_statement(
        "sys.modules['ext_target'].STATE = 99",
        {"agent": None},
    )
    assert result["success"] is True
    assert sys.modules["ext_target"].STATE == 99
    sys.modules.pop("ext_target", None)


def test_execute_statement_define_function(tool):
    """Execute code block defining function and inject into hotpatch module namespace."""
    result = tool._execute_statement(
        "def debug_hook():\n    return 123\n", {"agent": None}
    )
    assert result["success"] is True
    assert "debug_hook" in result["defined"]
    hp_module = sys.modules["haijunbot.haijunbot_tools.hotpatch"]
    assert hp_module.debug_hook() == 123
    # Clean up injected function to avoid pollution
    del hp_module.debug_hook


# ------------------------------------------------------------------
# Exceptions and parameter validation
# ------------------------------------------------------------------
def test_invalid_args_no_throw(tool):
    """Invalid parameters return error, no exception thrown."""
    result = tool.execute({})
    assert result["success"] is False
    assert "stderr" in result


def test_inject_new_module_requires_code(tool):
    """new_module_name without code returns error."""
    result = tool.execute({"new_module_name": "x"})
    assert result["success"] is False


def test_statement_exception_captured(tool):
    """Statement execution exception is caught, no exception thrown."""
    result = tool._execute_statement("raise ValueError('boom')", {"agent": None})
    assert result["success"] is False
    assert "boom" in result["error"]


def test_reload_does_not_affect_other_modules(tool, tmp_path):
    """reload does not affect other modules."""
    mod_a = tmp_path / "iso_a.py"
    mod_b = tmp_path / "iso_b.py"
    mod_a.write_text("A = 1\n", encoding="utf-8")
    mod_b.write_text("B = 1\n", encoding="utf-8")
    for name, path in (("iso_a", mod_a), ("iso_b", mod_b)):
        _load_module(name, path)
    # iso_b is not affected
    assert sys.modules["iso_b"].B == 1

    sys.modules.pop("iso_a", None)
    sys.modules.pop("iso_b", None)
