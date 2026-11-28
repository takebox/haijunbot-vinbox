# -*- coding: utf-8 -*-
"""Session real-time save daemon (SessionDaemon) unit tests.

Coverage:
- Normal exit: daemon cleans up memory after receiving quit, no disk write
- Unexpected exit: writes to disk by snapshot when pipe EOF occurs (simulating process being killed), and recoverable
- build_snapshot_files indentation/encoder mapping
"""

import json
import os
import subprocess
import sys
import time

import pytest

from haijunbot.haijunbot_agent.session_daemon import SessionDaemon
from haijunbot.haijunbot_agent.session_daemon import build_snapshot_files

pytestmark = pytest.mark.skipif(
    not hasattr(os, "fork"), reason="Requires os.fork (POSIX platform)"
)


def _wait_for(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Poll until condition is met."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class TestBuildSnapshotFiles:
    """build_snapshot_files mapping logic."""

    def test_indent_and_encoder_mapping(self):
        files = [
            ("/tmp/a_saved_session_x_20260101_000000.json", {"messages": []}, None),
            ("/tmp/a_saved_session_x_20260101_000000_commit.json", {"c": 1}, None),
            ("/tmp/a_saved_session_x_20260101_000000_state.json", {"s": 1}, object()),
            ("/tmp/a_saved_session_x_tasklist.json", {"t": 1}, None),
        ]
        plan = build_snapshot_files("ignored", files)
        assert len(plan) == 4
        by_name = {os.path.basename(p["path"]): p for p in plan}
        # Main session / commit uses indent=4
        assert by_name["a_saved_session_x_20260101_000000.json"]["indent"] == 4
        assert by_name["a_saved_session_x_20260101_000000_commit.json"]["indent"] == 4
        # state / tasklist uses indent=2
        assert by_name["a_saved_session_x_20260101_000000_state.json"]["indent"] == 2
        assert by_name["a_saved_session_x_tasklist.json"]["indent"] == 2
        # Only state uses SafeEncoder
        assert by_name["a_saved_session_x_20260101_000000_state.json"][
            "use_safe_encoder"
        ]
        assert not by_name["a_saved_session_x_20260101_000000.json"][
            "use_safe_encoder"
        ]


class TestSessionDaemonNormalExit:
    """Normal exit: no disk write."""

    def test_normal_exit_does_not_write(self, tmp_path):
        daemon = SessionDaemon()
        assert daemon.start()
        try:
            session_file = str(tmp_path / "sess_saved_session_agent_20260101_000000.json")
            files = [
                {"path": session_file, "data": {"messages": [{"role": "user"}]},
                  "indent": 4, "use_safe_encoder": False},
            ]
            assert daemon.send_snapshot(files)
            # Normal exit notification
            daemon.send_quit()
            # Give daemon some time; even if writing to disk, only these files would be written
            time.sleep(0.3)
            assert not os.path.exists(session_file)
        finally:
            daemon.send_quit()


class TestSessionDaemonCrash:
    """Unexpected exit: disk write on EOF."""

    def test_crash_writes_files(self, tmp_path):
        """Run daemon in separate child process, parent sends snapshot then directly _exit to simulate being killed."""
        session_file = str(tmp_path / "sess_saved_session_agent_20260101_000000.json")
        commit_file = session_file[:-5] + "_commit.json"
        state_file = str(tmp_path / "sess_saved_session_agent_20260101_000000_state.json")
        tasklist_file = str(tmp_path / "sess_saved_session_agent_tasklist.json")

        script = f"""
import os, time
from haijunbot.haijunbot_agent.session_daemon import SessionDaemon
d = SessionDaemon()
assert d.start()
files = [
    {{"path": {session_file!r}, "data": {{"messages": [{{"role": "user", "content": "hi"}}]}},
      "indent": 4, "use_safe_encoder": False}},
    {{"path": {commit_file!r}, "data": {{"current_commit": "abc", "agent_name": "agent"}},
      "indent": 4, "use_safe_encoder": False}},
    {{"path": {state_file!r}, "data": {{"metadata": {{"agent_name": "agent"}}}},
      "indent": 2, "use_safe_encoder": True}},
    {{"path": {tasklist_file!r}, "data": {{"task_lists": {{}}}},
      "indent": 2, "use_safe_encoder": False}},
]
assert d.send_snapshot(files)
time.sleep(0.3)
# Simulate being killed: directly _exit, no quit sent, pipe write end closes triggering daemon EOF
os._exit(0)
"""
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd(),
        )
        assert proc.returncode == 0, proc.stderr

        # Daemon should write 4 files to disk after EOF
        assert _wait_for(lambda: os.path.exists(session_file)), "Main session file not written"
        assert _wait_for(lambda: os.path.exists(commit_file)), "Commit file not written"
        assert _wait_for(lambda: os.path.exists(state_file)), "State file not written"
        assert _wait_for(lambda: os.path.exists(tasklist_file)), "Tasklist file not written"

        # Content should be parseable normally (format consistent with save_session)
        with open(session_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["messages"][0]["content"] == "hi"
        with open(commit_file, "r", encoding="utf-8") as f:
            assert json.load(f)["current_commit"] == "abc"


class TestSessionDaemonDisabled:
    """All operations should be safe no-ops when not started."""

    def test_operations_noop_when_not_started(self):
        daemon = SessionDaemon()
        assert not daemon.enabled
        assert not daemon.send_snapshot([])
        # Should not raise
        daemon.send_quit()
