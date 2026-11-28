# -*- coding: utf-8 -*-
"""Global isolation for haijunbot_web_gateway tests.

Why isolation is necessary (important):
1. ``create_app()`` reads ``get_data_dir()`` (default ``~/.haijunbot``) and constructs
   ``UserManager`` / ``PermissionManager`` / ``TimerManager`` / ``ChatManager``.
   These objects **write** to ``<data_dir>/auth/*.json`` and ``<data_dir>/gateway/.haijunbot_timers.json``.
   The production gateway process uses the same real data directory, so running tests directly
   would modify production user/permission/timer data.
2. ``AgentManager.PERSISTENCE_FILE`` is a **module-level constant** (set at import time by ``get_data_dir()``),
   pointing to ``<data_dir>/gateway/.haijunbot_agents.json``. ``_load_agents()`` reads it,
   and if a recorded pid happens to be alive, ``delete_agent()`` will ``os.kill`` the real process.
   Therefore, in addition to environment variables, this constant must also be redirected to a temp directory.
3. ``create_app()`` overwrites ``os.environ["HAIJUNBOT_AUTH_TOKEN"]``; monkeypatch ensures restoration after tests.

Isolation approach: point ``HAIJUNBOT_DATA_DIR`` to a per-test ``tmp_path``,
and redirect module-level path constants in already-imported modules.
Tests use ``TestClient`` (ASGI in-memory transport) throughout,
so no ports are listened on and there is no conflict with deployed services.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

# Must be set before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect the entire HaijunBot data directory to a temp directory to avoid touching the real ~/.haijunbot."""
    data_dir = tmp_path / "haijunbot_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(data_dir))

    # Module-level constants are fixed at import time; explicit redirection required (only works for already-imported modules)
    from haijunbot.haijunbot_web_gateway import agent_manager, timer_manager

    monkeypatch.setattr(
        agent_manager.AgentManager,
        "PERSISTENCE_FILE",
        data_dir / "gateway" / ".haijunbot_agents.json",
    )
    monkeypatch.setattr(
        timer_manager.TimerManager,
        "PERSISTENCE_FILE",
        data_dir / "gateway" / ".haijunbot_timers.json",
    )

    yield data_dir


@pytest.fixture
def auth_token(monkeypatch):
    """Set an independent gateway Token for the current test and return it."""
    token = "test-token-isolated"
    monkeypatch.setenv("HAIJUNBOT_AUTH_TOKEN", token)
    return token
