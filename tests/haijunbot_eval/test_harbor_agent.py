# -*- coding: utf-8 -*-
"""HaijunBot Harbor adapter layer unit tests (no Docker dependency).

Harbor is an optional dependency: when ``harbor`` is not installed locally, this
test module is skipped entirely (``pytest.importorskip``). Tests use a mock
environment to capture command invocations and verify install / run command
construction and API key passthrough logic.
"""

import base64
import asyncio
from pathlib import Path

import pytest

harbor = pytest.importorskip("harbor", reason="harbor package required (optional dependency)")

from harbor.agents.installed.base import BaseInstalledAgent  # noqa: E402  # type: ignore

from haijunbot.haijunbot_eval.harbor_agent import (  # noqa: E402
    HaijunBotInstalledAgent,
    _INSTRUCTION_PATH,
    _PASSTHROUGH_ENV_VARS,
)


class _FakeResult:
    def __init__(self, code=0, out="", err=""):
        self.return_code = code
        self.stdout = out
        self.stderr = err


class _FakeEnvironment:
    """Mock environment that captures exec calls."""

    def __init__(self, jca_installed=False, sys_missing=False):
        self.commands = []
        self.uploads = []
        self.jca_installed = jca_installed
        self.sys_missing = sys_missing

    async def exec(self, command, cwd=None, env=None, timeout_sec=None, user=None):
        self.commands.append({"cmd": command, "env": env, "user": user})
        if "command -v hca" in command:
            return _FakeResult(0 if self.jca_installed else 1)
        if self.sys_missing and "command -v python3" in command:
            return _FakeResult(1)
        return _FakeResult(0, "ok")

    async def upload_dir(self, source_dir, target_dir):
        self.uploads.append((str(source_dir), target_dir))


def _make_agent(**kwargs):
    extra_env = dict(kwargs.pop("extra_env", None) or {})
    extra_env.setdefault("OPENAI_API_KEY", "sk-test-123")
    return HaijunBotInstalledAgent(
        logs_dir=Path("/tmp/harbor-test-logs"),
        model_name="gpt-4o",
        extra_env=extra_env,
        **kwargs,
    )


def _run(coro):
    return asyncio.run(coro)


# ----------------------------------------------------------------------
# Class loading and basic attributes
# ----------------------------------------------------------------------
def test_agent_subclasses_base_installed_agent():
    assert issubclass(HaijunBotInstalledAgent, BaseInstalledAgent)


def test_agent_name():
    assert HaijunBotInstalledAgent.name() == "haijunbot"


def test_agent_can_instantiate():
    agent = _make_agent()
    assert agent.version() is None
    assert agent.get_version_command() == "hca --version 2>/dev/null || true"


def test_passthrough_env_collects_api_keys():
    agent = _make_agent()
    env = agent._build_passthrough_env()
    assert env["OPENAI_API_KEY"] == "sk-test-123"
    # Unconfigured variables should not appear
    assert "JUGLOW_API_KEY" not in env


def test_passthrough_env_skips_empty():
    agent = HaijunBotInstalledAgent(
        logs_dir=Path("/tmp/harbor-test-logs"),
        model_name="gpt-4o",
        extra_env={"OPENAI_API_KEY": ""},
    )
    env = agent._build_passthrough_env()
    assert "OPENAI_API_KEY" not in env


def test_passthrough_env_vars_declared():
    # Key credential variables must be in the passthrough list
    assert "OPENAI_API_KEY" in _PASSTHROUGH_ENV_VARS
    assert "JUGLOW_API_KEY" in _PASSTHROUGH_ENV_VARS


def test_passthrough_env_skips_proxy_vars():
    # Proxy variables point to host machine 127.0.0.1:7890, which has no corresponding
    # proxy service inside the container. Passthrough would cause Connection error
    # when hca calls the LLM API, so they must be excluded.
    agent = _make_agent(
        extra_env={
            "HTTP_PROXY": "http://127.0.0.1:7890",
            "HTTPS_PROXY": "http://127.0.0.1:7890",
            "http_proxy": "http://127.0.0.1:7890",
            "https_proxy": "http://127.0.0.1:7890",
        }
    )
    env = agent._build_passthrough_env()
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        assert name not in env
    # Credentials should still be passed through
    assert env["OPENAI_API_KEY"] == "sk-test-123"


# ----------------------------------------------------------------------
# install
# ----------------------------------------------------------------------
def test_install_skips_when_jca_present():
    agent = _make_agent()
    env = _FakeEnvironment(jca_installed=True)
    _run(agent.install(env))
    # Should only have one hca check, no pip install
    assert len(env.commands) == 1
    assert "command -v hca" in env.commands[0]["cmd"]
    assert "pip install" not in env.commands[0]["cmd"]


def test_install_runs_pip_when_missing():
    agent = _make_agent()
    env = _FakeEnvironment(jca_installed=False)
    _run(agent.install(env))
    # Command sequence: hca check, system dependency check, git config, pip install, mkdir
    pip_cmds = [c for c in env.commands if "pip install" in c["cmd"]]
    assert len(pip_cmds) == 1
    pip_cmd = pip_cmds[0]["cmd"]
    assert "haijunbot-ai-assistant" in pip_cmd
    # Bypass invalid proxy inside container + handle PEP 668
    assert "env -u HTTP_PROXY" in pip_cmd
    assert "--break-system-packages" in pip_cmd
    # Use domestic mirror to speed up downloads (direct PyPI access unreliable in container)
    assert "pypi.tuna.tsinghua.edu.cn" in pip_cmd
    assert "--quiet" not in pip_cmd
    # Upload builtin/prompts from local source to fill resources
    assert len(env.uploads) == 1
    assert env.uploads[0][1] == "/root/.haijunbot/prompts"


def test_install_skips_system_deps_when_present():
    # When python3/pip/git already exist, apt installation should not be triggered
    agent = _make_agent()
    env = _FakeEnvironment(jca_installed=False)
    _run(agent.install(env))
    apt_cmds = [c for c in env.commands if "apt-get" in c["cmd"]]
    assert apt_cmds == []


def test_install_apt_uses_mirror_and_retry_when_sys_missing():
    # When python3/pip/git are missing, apt should switch to a domestic mirror and retry multiple rounds
    agent = _make_agent()
    env = _FakeEnvironment(jca_installed=False, sys_missing=True)
    _run(agent.install(env))
    # Mirror replacement command (sed replaces official source with Aliyun)
    mirror_cmds = [c for c in env.commands if "mirrors.aliyun.com/ubuntu" in c["cmd"]]
    assert len(mirror_cmds) == 1
    assert "archive.ubuntu.com" in mirror_cmds[0]["cmd"]
    # apt install command: bypass proxy + overall retry loop
    apt_cmds = [c for c in env.commands if "apt-get" in c["cmd"]]
    assert len(apt_cmds) == 1
    apt_cmd = apt_cmds[0]["cmd"]
    assert "env -u HTTP_PROXY" in apt_cmd
    assert "for i in 1 2 3" in apt_cmd
    assert "done_apt=1; break" in apt_cmd


def test_install_uses_offline_wheelhouse_when_configured(tmp_path):
    # When HAIJUNBOT_WHEELHOUSE_DIR is set, use offline wheelhouse installation:
    # upload wheelhouse to container + --no-index --find-links fully offline install
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    (wheelhouse / "haijunbot_ai_assistant-6.0.10-py3-none-any.whl").write_text("x")
    agent = _make_agent(extra_env={"HAIJUNBOT_WHEELHOUSE_DIR": str(wheelhouse)})
    env = _FakeEnvironment(jca_installed=False)
    _run(agent.install(env))

    # Should upload wheelhouse to container /tmp/haijunbot-wheelhouse
    wh_uploads = [u for u in env.uploads if "wheelhouse" in u[1]]
    assert len(wh_uploads) == 1
    assert wh_uploads[0][1] == "/tmp/haijunbot-wheelhouse"

    # pip command should be offline install: --no-index --find-links
    pip_cmds = [c for c in env.commands if "pip install" in c["cmd"]]
    assert len(pip_cmds) == 1
    pip_cmd = pip_cmds[0]["cmd"]
    assert "--no-index" in pip_cmd
    assert "--find-links=/tmp/haijunbot-wheelhouse" in pip_cmd
    assert "haijunbot-ai-assistant" in pip_cmd
    # Offline install should not contain any online mirror sources
    assert "pypi.tuna.tsinghua.edu.cn" not in pip_cmd
    assert "pypi.org" not in pip_cmd


def test_wheelhouse_dir_none_when_unset():
    # When HAIJUNBOT_WHEELHOUSE_DIR is not set, returns None (fall back to online install)
    agent = _make_agent()
    assert agent._wheelhouse_dir() is None


def test_wheelhouse_dir_none_when_missing_dir(tmp_path):
    # When set but directory does not exist, returns None
    agent = _make_agent(
        extra_env={"HAIJUNBOT_WHEELHOUSE_DIR": str(tmp_path / "nope")}
    )
    assert agent._wheelhouse_dir() is None


# ----------------------------------------------------------------------
# run
# ----------------------------------------------------------------------
def test_run_writes_instruction_and_invokes_jca():
    agent = _make_agent()
    env = _FakeEnvironment()
    instruction = "Please solve the task: calculate 1+1 and write the result to /tmp/answer.txt."
    _run(agent.run(instruction, env, None))

    assert len(env.commands) == 2

    # First command: base64 write instruction
    write_cmd = env.commands[0]["cmd"]
    assert "base64 -d" in write_cmd
    assert _INSTRUCTION_PATH.as_posix() in write_cmd
    # Verify the written content can be decoded back to the original text
    encoded = write_cmd.split("printf '%s' ")[1].split(" |")[0].strip("'")
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert decoded == instruction

    # Second command: hca invocation
    run_cmd = env.commands[1]["cmd"]
    assert "hca -n" in run_cmd
    assert "--task-file" in run_cmd
    assert _INSTRUCTION_PATH.as_posix() in run_cmd
    # Must clear proxy variables pointing to container's own loopback before starting hca (force direct connection)
    assert "env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy" in run_cmd
    # API key passthrough
    assert env.commands[1]["env"]["OPENAI_API_KEY"] == "sk-test-123"


def test_run_invokes_as_agent_user():
    agent = _make_agent()
    env = _FakeEnvironment()
    _run(agent.run("do the thing", env, None))
    # exec_as_agent's user is None (default agent user)
    for cmd in env.commands:
        assert cmd["user"] is None


def test_base64_roundtrip():
    instruction = "Chinese task: write hello world to a file."
    encoded = base64.b64encode(instruction.encode("utf-8")).decode("ascii")
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert decoded == instruction
