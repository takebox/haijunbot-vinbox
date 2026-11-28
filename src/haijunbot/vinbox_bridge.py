# -*- coding: utf-8 -*-
"""Direct in-code entry point for Haijun AI inside Vinbox.

Haijun AI does not open a HaijunBot chat tab. It imports this module and calls
``ask()``; the call runs in the same Python process, on the same Vinbox model
lane, with no API key and no second provider.

Example (inside any Vinbox Python process)::

    from haijunbot.vinbox_bridge import ask
    result = ask("Baca app/program-file/README.md lalu ringkas isinya.")
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Optional

from haijunbot.haijunbot_utils import vinbox_runtime


def platform_ready() -> bool:
    """True when the Vinbox platform can be loaded (the registry is readable)."""
    try:
        from haijunbot.haijunbot_platform.vinbox import load_model_registry

        load_model_registry()
        return True
    except Exception:
        return False


def _make_agent(
    *,
    name: str = "HaijunBot",
    system_prompt: Optional[str] = None,
    non_interactive: bool = True,
    **kwargs: Any,
) -> Any:
    from haijunbot.haijunbot_agent import Agent

    return Agent(
        name=name,
        system_prompt=system_prompt,
        non_interactive=non_interactive,
        allow_savesession=False,
        use_tools=kwargs.pop("use_tools", None),
        **kwargs,
    )


def ask(
    instruction: str,
    *,
    name: str = "HaijunBot",
    system_prompt: Optional[str] = None,
    non_interactive: bool = True,
    **kwargs: Any,
) -> Any:
    """Run one HaijunBot task in-process and return its result.

    ``instruction`` is the task text. Extra keyword arguments are passed to the
    ``Agent`` constructor (for example ``use_tools`` or ``rule_names``).
    """
    if not instruction or not instruction.strip():
        raise ValueError("instruksi kosong")

    # Inside Vinbox this pins the model lane, the data directory and the
    # terminal environment before the agent builds anything.
    vinbox_runtime.apply_process_defaults()

    # Make sure the platform exists before the Agent tries to build a model.
    if not platform_ready():
        raise RuntimeError(
            "Vinbox model registry tidak bisa dibaca. Jalankan di dalam Vinbox "
            "(VINBOX_HOME=/app/vinbox) atau set VINBOX_HOME."
        )

    agent = _make_agent(
        name=name,
        system_prompt=system_prompt,
        non_interactive=non_interactive,
        **kwargs,
    )
    return agent.run(instruction.strip())


def agent(
    *,
    name: str = "HaijunBot",
    system_prompt: Optional[str] = None,
    non_interactive: bool = True,
    **kwargs: Any,
) -> Any:
    """Create a reusable Agent bound to the Vinbox platform."""
    vinbox_runtime.apply_process_defaults()
    if not platform_ready():
        raise RuntimeError(
            "Vinbox model registry tidak bisa dibaca. Jalankan di dalam Vinbox "
            "(VINBOX_HOME=/app/vinbox) atau set VINBOX_HOME."
        )
    return _make_agent(
        name=name,
        system_prompt=system_prompt,
        non_interactive=non_interactive,
        **kwargs,
    )


def status() -> Dict[str, Any]:
    """Honest readiness information for Haijun's own health checks."""
    result: Dict[str, Any] = {
        "ready": False,
        "platform": "vinbox",
        "error": None,
        "runtime": vinbox_runtime.status(),
    }
    try:
        from haijunbot.haijunbot_platform.vinbox import load_model_registry

        registry = load_model_registry()
        result["ready"] = True
        result["registry"] = getattr(registry, "__file__", "")
        try:
            result["current"] = registry.current_selection()
        except Exception as exc:
            result["error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - status reports the real cause
        result["error"] = str(exc)
    return result
