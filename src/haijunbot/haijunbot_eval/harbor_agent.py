# -*- coding: utf-8 -*-
"""HaijunBot's Harbor (Terminal-Bench 2.0) adapter layer.

Wraps HaijunBot as Harbor's ``BaseInstalledAgent`` so it can run as a
Terminal-Bench 2.0 evaluation agent. Core idea:

1. ``install()``: install the hca CLI in the evaluation container via ``pip install haijunbot-ai-assistant``.
2. ``run()``: write the task instruction to a file in the container, then invoke
   ``hca -n --task-file <path>`` to run the task inside the container (hca's execute_script
   naturally runs in the container environment, so no command redirection is needed).
3. API key / base URL are passed in through Harbor's ``--ae`` (extra env); this adapter layer
   reads them in ``run()`` and passes them through to the hca process.

Harbor is a lazy dependency: this module is only loaded in the Harbor environment (Harbor
locates the class via ``harbor run -a haijunbot_eval.harbor_agent:HaijunBotInstalledAgent``),
so importing the ``haijunbot_eval`` package from the HaijunBot main project does not trigger the harbor dependency.
"""

from __future__ import annotations

import base64
import shlex
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, ClassVar, override

# harbor is a lazy dependency: this module is only loaded in the Harbor environment (Harbor
# locates the class via ``harbor run -a haijunbot_eval.harbor_agent:HaijunBotInstalledAgent``),
# so importing the ``haijunbot_eval`` package from the HaijunBot main project does not trigger the harbor dependency.
# The type-ignore comments at the end of the import lines below suppress false unresolved-import reports from static checkers.
from harbor.agents.capabilities import AgentCapabilities  # type: ignore
from harbor.agents.installed.base import (  # type: ignore
    BaseInstalledAgent,
    with_prompt_template,
)

# harbor moved ``ModelConnectionSpec`` between releases. Until 0.24 it lived in
# ``harbor.agents.model_connection`` and exposed ``api_key_envs``/``passthrough``;
# stable 0.25+ exposes it in ``harbor.agents.agent_auth_resolution`` and models the
# same agent-specific credentials through ``ProviderAccess``.
try:  # harbor < 0.25
    from harbor.agents.model_connection import ModelConnectionSpec  # type: ignore

    _MODEL_CONNECTION_LEGACY = True
except ImportError:  # harbor >= 0.25
    from harbor.agents.agent_auth_resolution import (  # type: ignore
        ModelConnectionSpec,
        ProviderAccess,
    )

    _MODEL_CONNECTION_LEGACY = False

# Common LLM API key / base URL environment variables, passed through to the hca process inside the container.
# hca's platform implementations (openai/haijun/deepseek, etc.) read credentials from these standard variable names.
_PASSTHROUGH_ENV_VARS: tuple[str, ...] = (
    # OpenAI / compatible platforms
    "OPENAI_API_KEY",
    "OPENAI_API_BASE",
    "OPENAI_BASE_URL",
    # Juglow
    "JUGLOW_API_KEY",
    "JUGLOW_BASE_URL",
    # Generic proxy
    "API_BASE_URL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
)

# The proxy variables passed through into the container point to the host at 127.0.0.1:7890, and there is no corresponding proxy service inside the container,
# so passing them through to hca causes Connection errors when it calls the LLM API; hence they are excluded from passthrough.
_PROXY_ENV_VARS: frozenset[str] = frozenset(
    {"HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"}
)

# Path where the task instruction is written inside the container
_INSTRUCTION_PATH = PurePosixPath("/tmp/haijunbot-instruction.txt")

# Path where the offline wheelhouse is placed inside the container
_WHEELHOUSE_REMOTE_DIR = PurePosixPath("/tmp/haijunbot-wheelhouse")


class HaijunBotInstalledAgent(BaseInstalledAgent):
    """HaijunBot's Harbor adapter agent."""

    # Evaluation images usually do not include Python/git, so install() needs apt to add them and pip to install packages,
    # and the first install takes a long time, so the setup timeout is relaxed (the default 360s is not enough).
    DEFAULT_SETUP_TIMEOUT_SEC: ClassVar[float] = 1800.0

    capabilities = AgentCapabilities()
    if _MODEL_CONNECTION_LEGACY:
        MODEL_CONNECTION = ModelConnectionSpec(
            default_provider=None,
            api_key_envs=_PASSTHROUGH_ENV_VARS,
            passthrough=True,
        )
    else:
        MODEL_CONNECTION = ModelConnectionSpec(
            default_provider=None,
            agent_provider_access=ProviderAccess(
                api_key_candidate_names=list(_PASSTHROUGH_ENV_VARS),
            ),
        )

    @staticmethod
    @override
    def name() -> str:
        return "haijunbot"

    @override
    def get_version_command(self) -> str | None:
        return "hca --version 2>/dev/null || true"

    @override
    def parse_version(self, stdout: str) -> str:
        return (stdout or "").strip() or "unknown"

    @override
    async def install(self, environment: Any) -> None:
        """Install the hca CLI (haijunbot-ai-assistant package) in the evaluation container.

        Evaluation images (e.g. gpt2-codegolf) usually do not include Python/git, and the PyPI release of
        haijunbot-ai-assistant does not bundle the builtin prompt resources. Therefore, in order:
        1. Use apt to add python3/pip/git;
        2. Configure git user.name/email (required by hca at startup);
        3. pip-install haijunbot-ai-assistant (PEP 668 requires --break-system-packages);
        4. Upload builtin/prompts from the local source tree to the container data directory to fill in the missing resources.
        """
        check = await environment.exec(
            command="command -v hca >/dev/null 2>&1",
            user="root",
        )
        if check.return_code == 0:
            self.logger.debug("hca already installed, skipping installation")
            return

        # The HTTP_PROXY=127.0.0.1 passed through into the container points at the container itself; bypass it with a direct connection.
        no_proxy = "env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy"

        # 1. Fill in system dependencies: python3/pip/git
        sys_check = await environment.exec(
            command=(
                "command -v python3 >/dev/null 2>&1 && "
                "python3 -m pip --version >/dev/null 2>&1 && "
                "command -v git >/dev/null 2>&1"
            ),
            user="root",
        )
        if sys_check.return_code != 0:
            # The container's default apt source is the official Ubuntu source (archive.ubuntu.com), and
            # connecting directly to foreign sources from inside the container is very slow, so replace it with a domestic mirror (Aliyun) first.
            apt_mirror_cmd = (
                "set -euo pipefail; "
                "if command -v sed >/dev/null 2>&1; then "
                "sed -i "
                "'s|http://archive.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g; "
                "s|http://security.ubuntu.com/ubuntu/|http://mirrors.aliyun.com/ubuntu/|g' "
                "/etc/apt/sources.list.d/ubuntu.sources /etc/apt/sources.list "
                "2>/dev/null || true; "
                "fi"
            )
            await self.exec_as_root(environment, command=apt_mirror_cmd)
            # Direct connections to external sources from inside the container occasionally time out, so retry apt overall several times (break on success).
            apt_cmd = (
                "set -euo pipefail; "
                "done_apt=0; "
                "for i in 1 2 3; do "
                f"if {no_proxy} apt-get update -qq && "
                f"{no_proxy} DEBIAN_FRONTEND=noninteractive "
                "apt-get install -y -qq python3 python3-pip git; "
                "then done_apt=1; break; fi; "
                'echo "[install] apt round $i failed, retrying in 5s..."; sleep 5; '
                "done; "
                'if [ "$done_apt" -ne 1 ]; then '
                'echo "[install] apt install still failed after multiple retries" >&2; exit 1; fi'
            )
            await self.exec_as_root(
                environment,
                command=apt_cmd,
                timeout_sec=900,
            )

        # 2. Configure the git identity (required by hca at startup)
        await self.exec_as_root(
            environment,
            command=(
                "git config --global user.name 'HaijunBot' && "
                "git config --global user.email 'haijunbot@local'"
            ),
        )

        # 3. Install haijunbot-ai-assistant (Ubuntu 24.04's pip is restricted by PEP 668)
        # Prefer using the local prebuilt offline wheelhouse (completely avoids unstable large-package downloads inside the container);
        # fall back to online multi-mirror installation when no wheelhouse is provided.
        wheelhouse_dir = self._wheelhouse_dir()
        if wheelhouse_dir is not None:
            await self._install_from_wheelhouse(
                environment, wheelhouse_dir, no_proxy
            )
        else:
            await self._install_online(environment, no_proxy)

        # 4. Fill in the builtin prompt resources missing from the PyPI package (uploaded from the local source tree)
        prompts_dir = self._local_prompts_dir()
        if prompts_dir is not None:
            await self.exec_as_root(
                environment,
                command="mkdir -p /root/.haijunbot/prompts",
            )
            await environment.upload_dir(prompts_dir, "/root/.haijunbot/prompts")
            self.logger.debug("uploaded builtin/prompts to the container data directory")

    @override
    @with_prompt_template
    async def run(self, instruction: str, environment: Any, context: Any) -> None:
        """Run HaijunBot inside the evaluation container to solve the task.

        The instruction is passed in after being rendered by Harbor's ``@with_prompt_template``.
        Write the instruction to a file in the container, then invoke ``hca -n --task-file <path>``.
        """
        # Write the instruction using base64 to avoid shell escaping issues
        encoded = base64.b64encode(instruction.encode("utf-8")).decode("ascii")
        await self.exec_as_agent(
            environment,
            command=(
                f"printf '%s' {shlex.quote(encoded)} | base64 -d > "
                f"{_INSTRUCTION_PATH.as_posix()}"
            ),
        )

        env = self._build_passthrough_env()
        run_id = uuid.uuid4().hex
        log_path = (self.environment_logs_dir / f"hca-{run_id}.log").as_posix()

        # Harbor may inject proxy variables pointing to the container's own loopback
        # (HTTP_PROXY=127.0.0.1:7890), and there is no corresponding proxy service inside the container,
        # which causes Connection errors when hca calls the LLM API. Explicitly clear the proxies before starting hca to force direct connections.
        command = (
            "env -u HTTP_PROXY -u HTTPS_PROXY -u http_proxy -u https_proxy "
            f"hca -n --task-file {shlex.quote(_INSTRUCTION_PATH.as_posix())} "
            f"2>&1 | tee {shlex.quote(log_path)}"
        )
        await self.exec_as_agent(environment, command=command, env=env)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _wheelhouse_dir(self) -> Path | None:
        """Locate the local prebuilt offline wheelhouse directory (for offline installation into the container).

        The local wheelhouse path is specified via the ``HAIJUNBOT_WHEELHOUSE_DIR`` environment variable;
        returns None when unset or when the directory does not exist, and install() falls back to online installation.
        """
        raw = self._get_env("HAIJUNBOT_WHEELHOUSE_DIR")
        if not raw:
            return None
        wheelhouse = Path(raw).expanduser()
        return wheelhouse if wheelhouse.is_dir() else None

    async def _install_from_wheelhouse(
        self,
        environment: Any,
        wheelhouse_dir: Path,
        no_proxy: str,
    ) -> None:
        """Install haijunbot-ai-assistant in the container using the local prebuilt offline wheelhouse.

        After uploading the wheelhouse to the container, install fully offline with
        ``--no-index --find-links``, completely avoiding the unstable direct download
        of large packages (playwright, etc.) from PyPI inside the container. The wheelhouse must be
        prebuilt with the same Python version as the container for ABI compatibility.
        """
        remote_dir = _WHEELHOUSE_REMOTE_DIR.as_posix()
        self.logger.info("installing with the offline wheelhouse: %s", wheelhouse_dir)
        await self.exec_as_root(
            environment,
            command=f"mkdir -p {remote_dir}",
        )
        await environment.upload_dir(wheelhouse_dir, remote_dir)
        install_cmd = (
            "set -euo pipefail; "
            "installed=0; "
            "for i in 1 2 3; do "
            f"if {no_proxy} python3 -m pip install --break-system-packages "
            "--no-cache-dir --upgrade "
            f"--no-index --find-links={remote_dir} haijunbot-ai-assistant; "
            "then installed=1; break; fi; "
            'echo "[install] offline round $i failed, retrying in 5s..."; sleep 5; '
            "done; "
            'if [ "$installed" -ne 1 ]; then '
            'echo "[install] offline wheelhouse install still failed after multiple retries" >&2; '
            "exit 1; fi"
        )
        await self.exec_as_agent(
            environment,
            command=install_cmd,
            timeout_sec=900,
        )

    async def _install_online(self, environment: Any, no_proxy: str) -> None:
        """Install haijunbot-ai-assistant online from multiple mirrors (fallback when the offline wheelhouse is unavailable).

        Direct connections to PyPI from inside the container are unstable; large-package downloads may hit ReadTimeout midway or become corrupted
        (empty wheel files, hash mismatch). Domestic mirrors (Tsinghua tuna) are fast but occasionally return
        403/rate-limit. Therefore a multi-mirror fallback is used (Tsinghua → Aliyun → direct PyPI),
        retrying the whole thing for several rounds, and --no-cache-dir avoids failed retries due to corrupted cached files.
        """
        pip_indexes = (
            "https://pypi.tuna.tsinghua.edu.cn/simple",
            "https://mirrors.aliyun.com/pypi/simple/",
            "https://pypi.org/simple",
        )
        pip_install_cmd = (
            "set -euo pipefail; "
            "installed=0; "
            "for i in 1 2 3; do "
            'for idx in "{0}" "{1}" "{2}"; do '
            f"if {no_proxy} python3 -m pip install --break-system-packages "
            "--no-cache-dir --upgrade --timeout 120 --retries 10 "
            '-i "$idx" haijunbot-ai-assistant; then installed=1; break 2; fi; '
            'echo "[install] source $idx failed, switching to the next source"; '
            "done; "
            'echo "[install] round $i: all sources failed, retrying in 5s..."; sleep 5; '
            "done; "
            'if [ "$installed" -ne 1 ]; then '
            'echo "[install] pip install still failed after multiple retries" >&2; exit 1; fi'
        ).format(*pip_indexes)
        await self.exec_as_agent(
            environment,
            command=pip_install_cmd,
            timeout_sec=1500,
        )

    def _local_prompts_dir(self) -> Path | None:
        """Locate the builtin/prompts directory in the local source tree.

        The PyPI release of haijunbot-ai-assistant does not bundle the builtin prompt resources, so they must be
        uploaded from the local source tree. The local code runs from source (``src/haijunbot/haijunbot_eval/``),
        so the project root is derived by walking upward from there; returns None if not found (e.g. when installed as a package).
        """
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        prompts_dir = project_root / "builtin" / "prompts"
        return prompts_dir if prompts_dir.is_dir() else None

    def _build_passthrough_env(self) -> dict[str, str]:
        """Collect the API credential environment variables to pass through to the hca process.

        Proxy variables (HTTP_PROXY/HTTPS_PROXY, etc.) point to the host at 127.0.0.1:7890,
        and there is no corresponding proxy service inside the container; passing them through causes Connection
        errors when hca calls the LLM API, so they are excluded.
        """
        env: dict[str, str] = {}
        for name in _PASSTHROUGH_ENV_VARS:
            if name in _PROXY_ENV_VARS:
                continue
            value = self._get_env(name)
            if value:
                env[name] = value
        return env
