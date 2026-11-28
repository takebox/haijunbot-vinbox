import atexit
import errno

# -*- coding: utf-8 -*-
import hashlib
import json
import os
import platform
import signal
import subprocess
import sys
import threading
import time
from datetime import date, datetime
from pathlib import Path
from pathlib import PurePath
from pathlib import PureWindowsPath
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

import yaml  # type: ignore[import-untyped]

from haijunbot import __version__
from haijunbot.haijunbot_utils.config import (
    detect_file_encoding,
    get_data_dir,
    get_default_encoding,
    get_max_input_token_count,
    read_text_file,
    set_global_config_data,
    set_llm_group,
    save_exception,
)
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.globals import get_in_chat, get_interrupt, set_interrupt
from haijunbot.haijunbot_utils.output import PrettyOutput


# Global flag to prevent duplicate calls to init_env
_init_env_called = False


def _get_bundled_deps_platform_key() -> Optional[str]:
    """Return the bundled deps directory name for the current platform.

    Args:
        None

    Returns:
        The current platform directory name, e.g. `x86_64_linux`; returns None if the current platform or architecture cannot be identified

    Example:
        >>> key = _get_bundled_deps_platform_key()
        >>> key in {None, "x86_64_linux", "x86_64_windows", "aarch64_macos"}
        True
    """
    system_name = platform.system().lower()
    machine = platform.machine().lower()

    arch_aliases = {
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }
    system_aliases = {
        "linux": "linux",
        "windows": "windows",
        "darwin": "macos",
    }

    normalized_arch = arch_aliases.get(machine)
    normalized_system = system_aliases.get(system_name)
    if not normalized_arch or not normalized_system:
        return None
    return f"{normalized_arch}_{normalized_system}"


def _get_editable_project_root() -> Optional[Path]:
    """Infer the project root directory in an editable-install scenario."""
    current_file = Path(__file__).resolve()
    for candidate in current_file.parents:
        if (candidate / "pyproject.toml").exists() and (
            candidate / "src" / "haijunbot"
        ).exists():
            return candidate
    return None


def ensure_bundled_deps_in_path() -> Optional[Path]:
    """Add the repository's bundled deps directory for the current platform to PATH.

    Why: HaijunBot has bundled some runtime tools into the source repository.
    In editable-install or source-run scenarios, adding this directory to PATH early avoids users
    having to install `uv`, `rg`, `fd`, `tmux` etc. separately, and lets CLI subprocesses inherit the same environment.

    Args:
        None

    Returns:
        The directory successfully added to PATH; returns None if the current context is not a recognizable/usable source scenario

    Example:
        >>> result = ensure_bundled_deps_in_path()
        >>> result is None or isinstance(result, Path)
        True
    """
    platform_key = _get_bundled_deps_platform_key()
    if not platform_key:
        return None

    project_root = _get_editable_project_root()
    if not project_root:
        return None

    deps_dir = project_root / "src" / "haijunbot" / "haijunbot_data" / "deps" / platform_key
    if not deps_dir.is_dir():
        return None

    deps_dir_str = str(deps_dir)
    current_path = os.environ.get("PATH", "")
    path_entries: List[str]
    if current_path:
        path_entries = current_path.split(os.pathsep)
    else:
        path_entries = []

    if os.name == "nt":
        normalized_target = str(PureWindowsPath(deps_dir_str)).lower()
        normalized_entries = {
            str(PureWindowsPath(entry)).lower() for entry in path_entries if entry
        }
    else:
        normalized_target = str(PurePath(deps_dir_str))
        normalized_entries = {str(PurePath(entry)) for entry in path_entries if entry}

    if normalized_target in normalized_entries:
        return deps_dir

    os.environ["PATH"] = (
        deps_dir_str if not current_path else current_path + os.pathsep + deps_dir_str
    )
    return deps_dir


def decode_output(data: bytes) -> str:
    """Decode command output, automatically trying UTF-8 and GBK encodings

    Args:
        data: output data of bytes type

    Returns:
        The decoded string
    """
    from haijunbot.haijunbot_utils.config import get_default_encoding

    # Prefer the system default encoding (Windows: gbk, others: utf-8)
    for enc in (get_default_encoding(), "utf-8", "gbk"):
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, AttributeError):
            pass

    # Finally try latin-1 (never fails, but may produce garbled characters)
    try:
        return data.decode("latin-1")
    except AttributeError:
        # If not bytes type, convert to string
        return str(data)


g_config_file: Optional[str] = None

COMMAND_MAPPING = {
    # haijunbot main command
    "hjb": "haijunbot",
    # code agent
    "hca": "haijunbot-code-agent",
    # smart shell
    "hss": "haijunbot-smart-shell",
    # platform management
    "hpm": "haijunbot-platform-manager",
    # Git commit
    "hgc": "haijunbot-git-commit",
    # Git compress
    "hgs": "haijunbot-git-squash",
    # agent
    "ha": "haijunbot-agent",
    # tools
    "ht": "haijunbot-tool",
    # memory organization
    "hmo": "haijunbot-memory-organizer",
    # security analysis
    "hsec": "haijunbot-sec",
    # C2Rust migration
    "hc2r": "haijunbot-c2rust",
}


def is_editable_install() -> bool:
    """
    Detect whether the current HaijunBot is installed in editable mode (pip/uv install -e .).

    Order of checks (multiple strategies in parallel, any hit is considered an editable install):
    1. Read PEP 610's direct_url.json (dir_info.editable)
    2. Support legacy .egg-link / .pth editable installs
    3. Heuristic fallback: a .git exists upstream of the source path and it is not in site-packages/dist-packages
    """
    # Prefer importlib.metadata to read the distribution's direct_url.json
    try:
        import importlib.metadata as metadata  # Python 3.8+
    except Exception:
        # If importlib.metadata is unavailable, return None directly, meaning it cannot be checked
        return False

    def _check_direct_url() -> Optional[bool]:
        candidates = ["haijunbot-ai-assistant", "haijunbot_ai_assistant"]
        for name in candidates:
            try:
                dist = metadata.distribution(name)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.utils", function="_check_direct_url"
                )
                continue
            try:
                files = dist.files or []
                for f in files:
                    try:
                        if f.name == "direct_url.json":
                            p = Path(str(dist.locate_file(f)))
                            if p.exists():
                                with open(
                                    p, "r", encoding="utf-8", errors="ignore"
                                ) as fp:
                                    info = json.load(fp)
                                dir_info = info.get("dir_info") or {}
                                if isinstance(dir_info, dict) and bool(
                                    dir_info.get("editable")
                                ):
                                    return True
                                # Support some tools possibly writing a top-level editable field
                                if bool(info.get("editable")):
                                    return True
                                return False  # Found direct_url.json but it is not marked editable
                    except Exception as e:
                        save_exception(
                            e, module="haijunbot_utils.utils", function="_check_direct_url"
                        )
                        continue
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.utils", function="_check_direct_url"
                )
                continue
        return None

    res = _check_direct_url()
    if res is True:
        # Explicitly marked editable, return True directly
        return True
    # For cases where res is False/None, do not conclude immediately; continue with the subsequent compatibility strategies

    # Support legacy .egg-link / .pth editable installs
    try:
        module_path = Path(__file__).resolve()
        pkg_root = module_path.parent.parent  # haijunbot package root directory

        # 1) sys.path-based .egg-link / .pth detection (closer to test scenarios, relies on os.path.exists)
        import os as _os

        for entry in sys.path:
            try:
                egg_link = Path(entry) / f"{pkg_root.name}.egg-link"
                pth_file = Path(entry) / f"{pkg_root.name}.pth"
                if _os.path.exists(str(egg_link)) or _os.path.exists(str(pth_file)):
                    return True
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.utils", function="_check_direct_url"
                )
                continue

        # 2) Support the more general .egg-link form (reads the pointed-to source path)
        for entry in sys.path:
            try:
                p = Path(entry)
                if not p.exists() or not p.is_dir():
                    continue
                for egg in p.glob("*.egg-link"):
                    try:
                        text = egg.read_text(encoding="utf-8", errors="ignore")
                        first_line = (text.strip().splitlines() or [""])[0]
                        if not first_line:
                            continue
                        src_path = Path(first_line).resolve()
                        # The current package root is under the source path pointed to by egg-link, treat as editable install
                        if str(pkg_root).startswith(str(src_path)):
                            return True
                    except Exception as e:
                        save_exception(
                            e, module="haijunbot_utils.utils", function="_check_direct_url"
                        )
                        continue
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.utils", function="_check_direct_url"
                )
                continue
    except Exception as e:
        save_exception(e, module="haijunbot_utils.utils", function="_check_direct_url")
        pass

    # Heuristic fallback: source repository path
    try:
        parents = list(Path(__file__).resolve().parents)
        has_git = any((d / ".git").exists() for d in parents)
        in_site = any(
            ("site-packages" in str(d)) or ("dist-packages" in str(d)) for d in parents
        )
        if has_git and not in_site:
            return True
    except Exception as e:
        save_exception(e, module="haijunbot_utils.utils", function="_check_direct_url")
        pass

    return False


def _setup_signal_handler() -> None:
    """Set the SIGINT signal handler"""
    original_sigint = signal.getsignal(signal.SIGINT)

    def sigint_handler(signum: int, frame: Any) -> None:
        if get_in_chat():
            set_interrupt(True)
            if get_interrupt() > 5 and original_sigint and callable(original_sigint):
                cast(Callable[[int, Any], Any], original_sigint)(signum, frame)
        else:
            if original_sigint and callable(original_sigint):
                cast(Callable[[int, Any], Any], original_sigint)(signum, frame)

    signal.signal(signal.SIGINT, sigint_handler)


# ----------------------------
# Single-instance file lock (placed for use early in initialization)
# ----------------------------
_INSTANCE_LOCK_PATH: Optional[Path] = None


def _get_instance_lock_path(lock_name: str = "instance.lock") -> Path:
    try:
        data_dir = Path(str(get_data_dir()))
    except Exception:
        data_dir = Path(os.path.expanduser("~/.haijunbot"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / lock_name


def _read_lock_owner_pid(lock_path: Path) -> Optional[int]:
    try:
        txt = lock_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not txt:
            return None
        try:
            info = json.loads(txt)
            pid = info.get("pid")
            return int(pid) if pid is not None else None
        except Exception:
            # Support pure numeric PID
            return int(txt)
    except Exception:
        return None


def _is_process_alive(pid: int) -> bool:
    if pid is None or pid <= 0:
        return False
    if sys.platform == "win32":
        # Windows: os.kill(pid, 0) is unavailable; use ctypes to call OpenProcess
        import ctypes

        try:
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(  # type: ignore[attr-defined]
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)  # type: ignore[attr-defined]
                return True
            return False
        except OSError:
            return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # No permission but the process exists
        return True
    except OSError as e:
        # On some platforms, EPERM means the process exists but there is no permission
        if getattr(e, "errno", None) == errno.EPERM:
            return True
        return False
    else:
        return True


def _release_instance_lock() -> None:
    global _INSTANCE_LOCK_PATH
    try:
        if _INSTANCE_LOCK_PATH and _INSTANCE_LOCK_PATH.exists():
            _INSTANCE_LOCK_PATH.unlink()
    except Exception:
        # Cleanup failure does not affect exit
        pass
    _INSTANCE_LOCK_PATH = None


def _acquire_single_instance_lock(lock_name: str = "instance.lock") -> None:
    """
    Create an instance lock in the data directory (~/.haijunbot or the configured data directory) to prevent duplicate startup.
    If a live instance is detected, print a message and exit.
    """
    global _INSTANCE_LOCK_PATH
    lock_path = _get_instance_lock_path(lock_name)

    # Lock already exists: check whether it is a valid live instance
    if lock_path.exists():
        pid = _read_lock_owner_pid(lock_path)
        if pid and _is_process_alive(pid):
            PrettyOutput.auto_print(
                f"⚠️ Detected an existing running HaijunBot instance (PID: {pid}).\nIf you are sure no instance is running, delete the lock file and retry: {lock_path}"
            )
            sys.exit(0)
        # Try to remove the stale lock
        try:
            lock_path.unlink()
        except Exception:
            PrettyOutput.auto_print(
                f"❌ Failed to delete the old lock file: {lock_path}, please clean it up manually and retry."
            )
            sys.exit(1)

    # Atomically create the lock file to avoid concurrent races
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    try:
        fd = os.open(str(lock_path), flags)
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            payload = {
                "pid": os.getpid(),
                "time": int(time.time()),
                "argv": sys.argv[:10],
            }
            try:
                fp.write(json.dumps(payload, ensure_ascii=False))
            except Exception:
                fp.write(str(os.getpid()))
        _INSTANCE_LOCK_PATH = lock_path
        atexit.register(_release_instance_lock)
    except FileExistsError:
        # Re-verify under extreme concurrency
        pid = _read_lock_owner_pid(lock_path)
        if pid and _is_process_alive(pid):
            PrettyOutput.auto_print(
                f"⚠️ Detected an existing running HaijunBot instance (PID: {pid})."
            )
            sys.exit(0)
        PrettyOutput.auto_print(
            f"❌ The lock file already exists but may be stale: {lock_path}, please delete it manually and retry."
        )
        sys.exit(1)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to create instance lock: {e}")
        sys.exit(1)


def _is_installed_via_uv_tool() -> bool:
    """Detect whether the current haijunbot is installed via uv tool

    Returns:
        bool: True if installed via uv tool
    """
    try:
        # Check whether sys.argv[0] is in a typical uv tool install directory
        argv0_path = Path(sys.argv[0]).resolve()

        # Typical paths for uv tool installs
        if sys.platform == "win32":
            uv_tool_dirs = [
                Path(os.environ.get("LOCALAPPDATA", "")) / "uv" / "bin",
                Path(os.environ.get("APPDATA", "")) / "uv" / "bin",
            ]
        else:
            uv_tool_dirs = [
                Path.home() / ".local" / "bin",
                Path.home() / ".local" / "share" / "uv" / "bin",
            ]

        # Check whether it is in the uv tool directory
        for uv_dir in uv_tool_dirs:
            try:
                if uv_dir.exists() and argv0_path.is_relative_to(uv_dir):
                    # Further verify whether it is really installed via uv tool
                    from shutil import which as _which

                    uv_exe = _which("uv")
                    if uv_exe:
                        try:
                            # Run uv tool list to verify
                            result = subprocess.run(
                                [uv_exe, "tool", "list"],
                                capture_output=True,
                                timeout=10,
                                text=True,
                            )
                            if result.returncode == 0:
                                if "haijunbot-ai-assistant" in result.stdout.lower():
                                    return True
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_utils.utils",
                                function="_is_installed_via_uv_tool",
                            )
                            pass
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.utils", function="_is_installed_via_uv_tool"
                )
                pass
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.utils", function="_is_installed_via_uv_tool"
        )
        pass
    return False


def _check_pip_updates() -> bool:
    """Check whether the pip-installed HaijunBot has an update

    Returns:
        bool: whether an update was performed (returns True on successful update to trigger a restart)
    """
    import urllib.error
    import urllib.request

    from packaging import version

    # Check the last check date
    last_check_file = Path(str(get_data_dir())) / "last_pip_check"
    today_str = date.today().strftime("%Y-%m-%d")

    if last_check_file.exists():
        try:
            last_check_date = last_check_file.read_text().strip()
            if last_check_date == today_str:
                return False
        except Exception as e:
            save_exception(
                e, module="haijunbot_utils.utils", function="_check_pip_updates"
            )
            pass

    try:
        # Get the latest version on PyPI
        url = "https://pypi.org/pypi/haijunbot-ai-assistant/json"
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                latest_version = data["info"]["version"]
        except (urllib.error.URLError, KeyError, ValueError):
            return False

        # Compare versions
        current_ver = version.parse(__version__)
        latest_ver = version.parse(latest_version)

        if latest_ver > current_ver:
            PrettyOutput.auto_print(
                f"ℹ️ Detected new version v{latest_version} (current version: v{__version__})"
            )

            # Check whether it is a major version upgrade (different major version number)
            is_major_upgrade = latest_ver.major != current_ver.major
            if is_major_upgrade:
                # A major version upgrade may contain incompatible changes; ask the user for confirmation
                from haijunbot.haijunbot_utils.input import user_confirm

                PrettyOutput.auto_print(
                    f"⚠️ Major version upgrade warning: v{current_ver} -> v{latest_ver}"
                )
                PrettyOutput.auto_print(
                    "A major version upgrade may contain incompatible API changes; please review the release notes."
                )
                if not user_confirm("Continue upgrading? (default is to upgrade)", default=True):
                    PrettyOutput.auto_print("ℹ️ Upgrade cancelled; updates will be checked again on next startup.")
                    # Update the check date to avoid repeated prompts
                    last_check_file.write_text(today_str)
                    return False

            # Pre-initialize to ensure it is accessible outside the subsequent branches (ty cross-branch inference limitation)
            cmd_list: List[str] = []
            update_cmd = ""

            # Detect whether it is installed via uv tool
            is_uv_tool_install = _is_installed_via_uv_tool()

            if is_uv_tool_install:
                # Update using uv tool upgrade
                from shutil import which as _which

                uv_exe = _which("uv")
                if uv_exe:
                    # Note: uv tool upgrade does not support extra arguments; it only upgrades the base package
                    cmd_list = [uv_exe, "tool", "upgrade", "haijunbot-ai-assistant"]
                    update_cmd = "uv tool upgrade haijunbot-ai-assistant"
                else:
                    # If uv cannot be found, fall back to pip
                    is_uv_tool_install = False

            if not is_uv_tool_install:
                # Detect whether it is in a virtual environment
                hasattr(sys, "real_prefix") or (
                    hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
                )

                # Detect whether uv is available (prefer uv inside the virtual environment, then uv in PATH)
                from shutil import which as _which

                uv_executable: Optional[str] = None
                if sys.platform == "win32":
                    venv_uv = Path(sys.prefix) / "Scripts" / "uv.exe"
                else:
                    venv_uv = Path(sys.prefix) / "bin" / "uv"
                if venv_uv.exists():
                    uv_executable = str(venv_uv)
                else:
                    path_uv = _which("uv")
                    if path_uv:
                        uv_executable = path_uv

                # Update command
                package_spec = "haijunbot-ai-assistant"
                if uv_executable:
                    cmd_list = [
                        uv_executable,
                        "pip",
                        "install",
                        "--upgrade",
                        package_spec,
                    ]
                    update_cmd = f"uv pip install --upgrade {package_spec}"
                else:
                    cmd_list = [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--upgrade",
                        package_spec,
                    ]
                    update_cmd = (
                        f"{sys.executable} -m pip install --upgrade {package_spec}"
                    )

            # Automatically attempt the upgrade (provide a manual command on failure)
            try:
                PrettyOutput.auto_print("ℹ️ Auto-updating HaijunBot, please wait...")
                result = subprocess.run(
                    cmd_list,
                    capture_output=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    # Update the check date to avoid repeated triggers
                    last_check_file.write_text(today_str)
                    return True
                else:
                    err = (
                        decode_output(result.stderr)
                        or decode_output(result.stdout)
                        or ""
                    ).strip()
                    if err:
                        PrettyOutput.auto_print(
                            f"⚠️ Auto-update failed, error message (truncated): {err[:500]}"
                        )
                    PrettyOutput.auto_print(f"ℹ️ Please run the following command manually to update: {update_cmd}")
            except Exception:
                PrettyOutput.auto_print("⚠️ Exception during auto-update; switched to manual update mode.")
                PrettyOutput.auto_print(f"ℹ️ Please run the following command manually to update: {update_cmd}")

        # Update the check date
        last_check_file.write_text(today_str)

    except Exception:
        # Silently handle errors without affecting normal use
        pass

    return False


# Major version update flag file management
_major_update_lock = threading.Lock()
_update_reboot_flag_path = None  # Lazy initialization


def _get_update_reboot_flag_path() -> Path:
    """Get the update-reboot flag file path

    Returns:
        Path: the flag file path
    """
    global _update_reboot_flag_path
    if _update_reboot_flag_path is None:
        data_dir = Path(str(get_data_dir()))
        _update_reboot_flag_path = data_dir / "update_reboot_flag.txt"
    return _update_reboot_flag_path


def _has_update_reboot_flag() -> bool:
    """Check whether there is an update flag waiting for a reboot

    Returns:
        bool: True if there is an update flag awaiting reboot, otherwise False
    """
    flag_path = _get_update_reboot_flag_path()
    return flag_path.exists()


def _set_update_reboot_flag() -> None:
    """Set the update-reboot flag"""
    flag_path = _get_update_reboot_flag_path()
    try:
        flag_path.write_text("1")
    except IOError as e:
        PrettyOutput.auto_print(f"⚠️ Unable to write the update-reboot flag: {e}")


def _clear_update_reboot_flag() -> None:
    """Clear the update-reboot flag"""
    flag_path = _get_update_reboot_flag_path()
    try:
        if flag_path.exists():
            flag_path.unlink()
    except (IOError, OSError) as e:
        PrettyOutput.auto_print(f"⚠️ Unable to clear the update-reboot flag: {e}")


def _get_major_update_flag_path() -> Path:
    """Get the major version update flag file path

    Returns:
        Path: the flag file path
    """
    data_dir = Path(str(get_data_dir()))
    return data_dir / "major_update_pending.json"


def _has_major_update_pending() -> Optional[str]:
    """Check whether there is a pending major version update

    Returns:
        Optional[str]: if there is a pending update, return the remote version number, otherwise return None
    """
    flag_path = _get_major_update_flag_path()
    if not flag_path.exists():
        return None

    try:
        with _major_update_lock:
            with open(flag_path, "r") as f:
                data: Dict[str, Any] = json.load(f)
            remote_version = data.get("remote_version")
            if isinstance(remote_version, str):
                return remote_version
            return None
    except (json.JSONDecodeError, IOError, KeyError):
        # The flag file is corrupted; delete it
        try:
            with _major_update_lock:
                flag_path.unlink()
        except (IOError, OSError):
            pass
        return None


def _set_major_update_pending(remote_version: str) -> None:
    """Set the major version update flag

    Args:
        remote_version: the detected new version number (e.g. v2.1.0)
    """
    flag_path = _get_major_update_flag_path()
    data = {
        "remote_version": remote_version,
        "detected_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    try:
        with _major_update_lock:
            with open(flag_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        PrettyOutput.auto_print(f"⚠️ Unable to write the major version update flag: {e}")


def _clear_major_update_flag() -> None:
    """Clear the major version update flag"""
    flag_path = _get_major_update_flag_path()
    try:
        with _major_update_lock:
            if flag_path.exists():
                flag_path.unlink()
    except (IOError, OSError) as e:
        PrettyOutput.auto_print(f"⚠️ Unable to clear the major version update flag: {e}")


def _check_haijunbot_updates() -> bool:
    """Check and update HaijunBot itself (git repository or pip package)

    Returns:
        bool: whether the process needs to restart
    """
    # Skip the auto-update check in non-interactive mode
    from haijunbot.haijunbot_utils.input import _is_non_interactive_for_current_agent

    if _is_non_interactive_for_current_agent():
        return False

    # Check whether there is an update flag awaiting reboot (minor version update completed)
    if _has_update_reboot_flag():
        # Automatically restart to apply the update
        _clear_update_reboot_flag()
        return True

    # Search upward from the current file directory for the repository root containing .git, fixing the previous issue of only checking src/haijunbot
    try:
        script_path = Path(__file__).resolve()
        repo_root: Optional[Path] = None
        for d in [script_path.parent] + list(script_path.parents):
            if (d / ".git").exists():
                repo_root = d
                break
    except Exception:
        repo_root = None

    # First check whether it is a git source install (finding the repository root is treated as a source install)
    if repo_root and (repo_root / ".git").exists():
        from haijunbot.haijunbot_utils.git_utils import check_and_update_git_repo

        # Run the background update check (minor versions auto-update; major versions only write a flag)
        updated = check_and_update_git_repo(str(repo_root))

        # Check whether there is a pending major version update
        pending_version = _has_major_update_pending()
        if pending_version:
            PrettyOutput.auto_print(f"🎉 Detected a pending major version upgrade: {pending_version}")

            PrettyOutput.auto_print("ℹ️ Performing major version upgrade...")
            # Clear the flag and perform the actual update
            _clear_major_update_flag()
            updated = check_and_update_git_repo(str(repo_root))

        return updated

    # Check whether it is a pip/uv pip installed version
    return _check_pip_updates()


def _show_usage_stats(welcome_str: str) -> None:
    """Display the HaijunBot welcome message

    Args:
        welcome_str: the welcome message string
    """
    try:
        from rich.align import Align
        from rich.console import Group
        from rich.text import Text

        import os

        from haijunbot.haijunbot_utils.config import (
            get_cheap_model_name,
            get_cheap_platform_name,
            get_eval_model_name,
            get_eval_platform_name,
            get_haijunbot_gitee_url,
            get_haijunbot_github_url,
            get_normal_model_name,
            get_normal_platform_name,
            get_smart_model_name,
            get_smart_platform_name,
            is_eval_model_configured,
        )

        # Welcome message Panel
        if welcome_str:
            haijunbot_ascii_art_str = """
   ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
   ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
   ██║███████║██████╔╝██║   ██║██║███████╗
██╗██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚████║██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝"""

            # Get model info and working directory
            try:
                cheap_model = get_cheap_model_name()
                cheap_platform = get_cheap_platform_name()
                normal_model = get_normal_model_name()
                normal_platform = get_normal_platform_name()
                smart_model = get_smart_model_name()
                smart_platform = get_smart_platform_name()
                # Display vertically line by line to avoid incomplete display when concatenated horizontally in narrow terminals
                model_lines = [
                    f"💰 Cheap: {cheap_model}({cheap_platform})",
                    f"⭐ Normal: {normal_model}({normal_platform})",
                    f"🧠 Smart: {smart_model}({smart_platform})",
                ]
                # Eval is optional; mark it clearly when not configured
                if is_eval_model_configured():
                    model_lines.append(
                        f"🧪 Eval: {get_eval_model_name()}({get_eval_platform_name()})"
                    )
                else:
                    model_lines.append("🧪 Eval: not configured")
            except Exception:
                model_lines = [
                    "💰 Cheap: unknown",
                    "⭐ Normal: unknown",
                    "🧠 Smart: unknown",
                    "🧪 Eval: not configured",
                ]

            work_dir = os.getcwd()
            work_dir_info = f"📁 Working directory: {work_dir}"

            # Get the repository link
            github_url = get_haijunbot_github_url()
            gitee_url = get_haijunbot_gitee_url()

            welcome_panel_content = Group(
                Align.center(Text(haijunbot_ascii_art_str, style="bold blue")),
                Align.center(Text(welcome_str, style="bold")),
                "",  # for a blank line
                *[Align.center(Text(line, style="cyan")) for line in model_lines],
                Align.center(Text(work_dir_info, style="dim")),
                "",  # for a blank line
                Align.center(Text(f"🎯 v{__version__}", style="bold green")),
                "",  # for a blank line
                Align.center(
                    Text("🐙 GitHub: ", style="bold cyan")
                    + Text.from_markup(
                        f"[link={github_url}]{github_url}[/link]", style="cyan"
                    )
                ),
                Align.center(
                    Text("🎋 Gitee: ", style="bold cyan")
                    + Text.from_markup(
                        f"[link={gitee_url}]{gitee_url}[/link]", style="cyan"
                    )
                ),
            )

            PrettyOutput.print_welcome_panel(welcome_panel_content)
    except Exception:
        # Fail silently without affecting normal use
        pass


def init_env(
    welcome_str: str = "",
    config_file: Optional[str] = None,
    llm_group: Optional[str] = None,
    auto_upgrade: bool = True,
) -> None:
    """Initialize the HaijunBot environment

    Args:
        welcome_str: the welcome message string
        config_file: config file path, defaults to None (uses ~/.haijunbot/config.yaml)
        llm_group: model group override parameter, used to display the user-specified model group
        auto_upgrade: whether to automatically check and upgrade HaijunBot, defaults to True
    """
    global _init_env_called

    # Prevent duplicate calls
    if _init_env_called:
        return

    try:
        _init_env_called = True
    except Exception:
        # If setup fails (theoretically impossible), continue execution
        pass

    # 0.1 Fix proxy environment variables: strip the socks:// prefix
    # Some applications do not support the socks:// protocol prefix; it needs to be removed
    try:
        proxy_vars = [
            "http_proxy",
            "https_proxy",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "all_proxy",
        ]
        for var in proxy_vars:
            value = os.environ.get(var)
            if value and value.startswith("socks://"):
                # Strip the socks:// prefix, keeping the address part
                os.environ[var] = value[8:]
    except Exception:
        # Fail silently without affecting normal use
        pass

    # 0. Check whether we are in a terminal environment opened by HaijunBot, to avoid nesting
    try:
        if os.environ.get("terminal") == "1":
            PrettyOutput.auto_print(
                "⚠️ Detected that the current terminal was opened by HaijunBot. Starting again may cause nesting."
            )
            from haijunbot.haijunbot_utils.input import user_confirm

            if not user_confirm("Continue starting HaijunBot anyway?", default=False):
                PrettyOutput.auto_print("ℹ️ Startup cancelled to avoid terminal nesting.")
                sys.exit(0)
    except Exception as e:
        save_exception(e, module="haijunbot_utils.utils", function="init_env")
        pass

    # 1. Set up signal handling
    try:
        _setup_signal_handler()
    except Exception as e:
        save_exception(e, module="haijunbot_utils.utils", function="init_env")
        pass

    # 2. Inject the repository's bundled deps directory to ensure subsequent commands and subprocesses can directly find bundled tools
    try:
        ensure_bundled_deps_in_path()
    except Exception as e:
        save_exception(e, module="haijunbot_utils.utils", function="init_env")
        pass

    # 3. Set up the config file
    global g_config_file
    g_config_file = config_file
    try:
        load_config()
        # Set default GitHub and Gitee link configuration so all tools can access them
        from haijunbot.haijunbot_utils.config import (
            GLOBAL_CONFIG_DATA,
            set_config,
        )

        if not GLOBAL_CONFIG_DATA.get("haijunbot_github_url"):
            set_config(
                "haijunbot_github_url", "https://github.com/takebox/HaijunBot.git"
            )
        if not GLOBAL_CONFIG_DATA.get("haijunbot_gitee_url"):
            set_config("haijunbot_gitee_url", "https://gitee.com/takebox/HaijunBot.git")
    except Exception:
        # Fail silently without affecting normal use
        pass

    set_llm_group(llm_group)

    # 4. Display historical statistics (only shown when the welcome message is displayed)
    # Use lazy loading to avoid blocking initialization
    if welcome_str:
        try:
            # Display statistics in a background thread to avoid blocking the main flow
            def show_stats_async() -> None:
                try:
                    _show_usage_stats(welcome_str)
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_utils.utils", function="show_stats_async"
                    )
                    pass

            stats_thread = threading.Thread(target=show_stats_async, daemon=True)
            stats_thread.start()
        except Exception:
            # Fail silently without affecting normal use
            pass

    # 5. Check for HaijunBot updates (perform the check in a background thread)
    if auto_upgrade:
        try:

            def check_updates_background() -> None:
                """Check for updates in a background thread; only marks, does not involve user interaction"""
                try:
                    # Walk up from the current file's directory to find the repo root containing .git
                    script_path = Path(__file__).resolve()
                    repo_root: Optional[Path] = None
                    for d in [script_path.parent] + list(script_path.parents):
                        if (d / ".git").exists():
                            repo_root = d
                            break

                    # First check whether this is a git source installation
                    if repo_root and (repo_root / ".git").exists():
                        from haijunbot.haijunbot_utils.git_utils import (
                            check_and_update_git_repo_background,
                        )

                        check_and_update_git_repo_background(str(repo_root))
                except Exception:
                    # Fail silently without affecting normal use
                    pass

            update_thread = threading.Thread(
                target=check_updates_background, daemon=True
            )
            update_thread.start()
        except Exception:
            # Fail silently without affecting normal use
            pass

    # 5.1 Check update markers (performed in the main thread, involves user interaction)
    if auto_upgrade:
        try:
            should_restart = False

            # Check whether there is an update marker waiting for a restart (minor version update completed)
            if _has_update_reboot_flag():
                PrettyOutput.auto_print(
                    "✅ Detected that HaijunBot has finished updating, restarting to apply the new version..."
                )
                _clear_update_reboot_flag()
                should_restart = True
            # Check whether there is a pending major version update
            pending_version = _has_major_update_pending()
            if pending_version:
                PrettyOutput.auto_print(f"🎉 Detected a pending major version upgrade: {pending_version}")
                from haijunbot.haijunbot_utils.input import user_confirm

                PrettyOutput.auto_print("ℹ️ Performing major version upgrade...")
                # Clear the marker and perform the actual update
                _clear_major_update_flag()
                should_restart = _check_haijunbot_updates()

            if should_restart:
                os.execv(sys.executable, [sys.executable] + sys.argv)
                sys.exit(0)
        except Exception:
            # Fail silently without affecting normal use
            pass

    # 5.1 Check update markers (performed in the main thread, involves user interaction)
    if auto_upgrade:
        try:
            should_restart = False

            # Check whether there is an update marker waiting for a restart (minor version update completed)
            if _has_update_reboot_flag():
                PrettyOutput.auto_print(
                    "✅ Detected that HaijunBot has finished updating, restarting to apply the new version..."
                )
                _clear_update_reboot_flag()
                should_restart = True
            # Check whether there is a pending major version update
            pending_version = _has_major_update_pending()
            if pending_version:
                PrettyOutput.auto_print(f"🎉 Detected a pending major version upgrade: {pending_version}")
                PrettyOutput.auto_print("ℹ️ Performing major version upgrade...")
                # Clear the marker and perform the actual update
                _clear_major_update_flag()
                should_restart = _check_haijunbot_updates()

            if should_restart:
                os.execv(sys.executable, [sys.executable] + sys.argv)
                sys.exit(0)
        except Exception:
            # Fail silently without affecting normal use
            pass


def _interactive_config_setup(config_file_path: Path) -> None:
    """Interactive configuration guide

    Directly call the quick_config module to perform quick configuration.
    If the HAIJUNBOT_SKIP_INTERACTIVE_CONFIG environment variable is set, skip interactive configuration.
    """
    import os

    # Check whether to skip interactive configuration (for CI/test environments)
    if os.environ.get("HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"):
        PrettyOutput.auto_print(
            "ℹ️ Skipped interactive configuration (HAIJUNBOT_SKIP_INTERACTIVE_CONFIG is set)"
        )
        return

    PrettyOutput.auto_print("ℹ️ Welcome to HaijunBot! Starting the quick configuration program...")

    try:
        # Import the quick_config module
        # Since hqc (quick_config) now takes no arguments, call quick_config.app() directly
        from haijunbot.haijunbot_utils import quick_config

        original_argv = sys.argv
        try:
            # Since the quick_config function takes no arguments, the --output argument is no longer passed
            sys.argv = ["quick-config"]
            quick_config.app()
        finally:
            sys.argv = original_argv

        sys.exit(0)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Failed to start the configuration program: {e}")
        sys.exit(1)


def load_config() -> None:
    config_file = g_config_file

    # If the user explicitly specifies a config file, still load only that file (backward compatibility)
    if config_file is not None:
        config_file_path = Path(config_file)
        if not config_file_path.exists():
            old_config_file = config_file_path.parent / "env"
            if old_config_file.exists():  # The old config file exists
                _read_old_config_file(old_config_file)
            else:
                _interactive_config_setup(config_file_path)
        else:
            _load_and_process_config(
                str(config_file_path.parent), str(config_file_path)
            )
    else:
        # Always load ~/.haijunbot/config.yaml as the base configuration
        user_config_path = Path(os.path.expanduser("~/.haijunbot/config.yaml"))
        config_files = []

        # First add the user's global config file (if it exists)
        if user_config_path.exists():
            config_files.append(str(user_config_path))
        elif (user_config_path.parent / "env").exists():
            # The old config file exists
            _read_old_config_file(user_config_path.parent / "env")
            return
        else:
            # The user config file does not exist; automatically create a default config file
            PrettyOutput.auto_print("ℹ️  The config file does not exist; creating default configuration...")
            try:
                schema_path = str(
                    Path(__file__).parent.parent / "haijunbot_data" / "config_schema.json"
                )
                user_config_path.parent.mkdir(parents=True, exist_ok=True)
                generate_default_config(schema_path, str(user_config_path))
                PrettyOutput.auto_print(f"✅ Created default config file: {user_config_path}")
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Failed to create default config file: {e}")
                # Create a minimal usable empty configuration
                try:
                    user_config_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(user_config_path, "w", encoding="utf-8") as f:
                        f.write("# HaijunBot config file\n")
                    PrettyOutput.auto_print(f"✅ Created empty config file: {user_config_path}")
                except Exception:
                    PrettyOutput.auto_print("❌ Unable to create config file")
                    return
            # Continue loading the config file
            config_files.append(str(user_config_path))

        # Then look for project config files in the current directory and its parent directories
        project_config_files = _find_all_config_files(os.getcwd())

        # Add project config files to the list (project config overrides user config)
        config_files.extend(project_config_files)

        # Merge all config files (later ones override earlier ones)
        if len(config_files) == 1:
            # Only the user config file; load it directly
            _load_and_process_config(
                str(user_config_path.parent), str(user_config_path)
            )
        else:
            # Multiple config files; merge them (project config overrides user config)
            content, merged_config = _merge_configs(config_files)
            # Use the last config file as the primary config file
            main_config_file = config_files[-1]
            main_config_dir = str(Path(main_config_file).parent)

            try:
                _ensure_schema_declaration(
                    main_config_dir, main_config_file, content, merged_config
                )
                # Load and merge plugin config, passing the config file's directory for resolving relative paths
                merged_config = _load_plugin_configs(merged_config, main_config_dir)
                set_global_config_data(merged_config)
                _process_env_variables(merged_config)
            except Exception:
                from haijunbot.haijunbot_utils.input import user_confirm

                PrettyOutput.auto_print("❌ Failed to load config file")
                if user_confirm("The config file format is invalid. Delete and reconfigure?"):
                    try:
                        os.remove(main_config_file)
                        PrettyOutput.auto_print(
                            "✅ Deleted the corrupted config file. Please restart HaijunBot to reconfigure."
                        )
                    except Exception:
                        PrettyOutput.auto_print("❌ Failed to delete config file")
                sys.exit(1)


def _find_all_config_files(start_dir: str) -> List[str]:
    """Walking up level by level from the given directory, find all .haijunbot/config.yaml files

    Args:
        start_dir: Starting directory path

    Returns:
        List[str]: List of config file paths ordered from upper level to lower level
    """
    config_files = []
    current_dir = Path(start_dir).resolve()
    root_dir = Path("/").resolve()
    max_levels = 20  # Search up at most 20 levels to prevent infinite loops
    level = 0

    while current_dir != root_dir and level < max_levels:
        config_path = current_dir / ".haijunbot" / "config.yaml"
        if config_path.exists():
            config_files.append(str(config_path))
        current_dir = current_dir.parent
        level += 1

    # Check the root directory
    config_path = root_dir / ".haijunbot" / "config.yaml"
    if config_path.exists():
        config_files.append(str(config_path))

    # Reverse the list so upper-level configs come first and lower-level configs come after
    config_files.reverse()
    return config_files


def _merge_configs(config_files: List[str]) -> Tuple[str, Dict[str, Any]]:
    """Load multiple config files in order and merge them (lower level overrides upper level)

    Args:
        config_files: List of config file paths (from upper level to lower level)

    Returns:
        Tuple[str, dict]: (raw content of the last config file, merged config dict)
    """
    merged_config = {}
    last_content = ""

    for config_file in config_files:
        content, config_data = _load_config_file(config_file)
        if isinstance(config_data, dict):
            merged_config.update(config_data)
        last_content = content  # Save the content of the last config file

    return last_content, merged_config


def _load_config_file(config_file: str) -> Tuple[str, Dict[str, Any]]:
    """Read and parse a YAML-format config file

    Args:
        config_file: Config file path

    Returns:
        Tuple[str, dict]: (raw file content, parsed config dict)
    """
    content = read_text_file(config_file)
    # Render jinja2 template variables (such as {{current_dir}}, {{config_file_dir}}, etc.)
    from haijunbot.haijunbot_utils.template_utils import render_main_config_template

    config_file_dir = str(Path(config_file).parent)
    rendered_content = render_main_config_template(content, config_file_dir)
    config_data = yaml.safe_load(rendered_content) or {}
    return content, config_data


def _ensure_schema_declaration(
    haijunbot_dir: str, config_file: str, content: str, config_data: Dict[str, Any]
) -> None:
    """Ensure the config file contains a schema declaration

    Args:
        haijunbot_dir: HaijunBot data directory path
        config_file: Config file path
        content: Raw content of the config file
        config_data: Parsed config dict
    """
    if (
        isinstance(config_data, dict)
        and "# yaml-language-server: $schema=" not in content
    ):
        schema_path = Path(
            os.path.relpath(
                Path(__file__).parent.parent / "haijunbot_data" / "config_schema.json",
                start=haijunbot_dir,
            )
        )
        with open(config_file, "w", encoding=get_default_encoding()) as f:
            f.write(f"# yaml-language-server: $schema={schema_path}\n")
            f.write(content)


def _process_env_variables(config_data: Dict[str, Any]) -> None:
    """Process environment variables in the configuration

    Args:
        config_data: Parsed config dict
    """
    if "ENV" in config_data and isinstance(config_data["ENV"], dict):
        os.environ.update(
            {str(k): str(v) for k, v in config_data["ENV"].items() if v is not None}
        )


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries

    Args:
        base: Base dictionary (low priority)
        override: Override dictionary (high priority)

    Returns:
        Dict[str, Any]: Merged dictionary

    Features:
        - For nested dicts, perform a recursive merge
        - For lists, append (extend)
        - For other types, override overrides base
        - Does not modify the original dict; returns a new dict (using deepcopy)
    """
    import copy

    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                # Both are dicts; merge recursively
                result[key] = _deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Append merge: override list first, base list after
                # In the final merge the project list comes first and the plugin list after; when merging between plugins, the later-loaded plugin list comes first
                result[key] = copy.deepcopy(value) + result[key]
            else:
                # Other types; override directly
                result[key] = (
                    copy.deepcopy(value) if isinstance(value, (dict, list)) else value
                )
        else:
            # New key; add directly
            result[key] = (
                copy.deepcopy(value) if isinstance(value, (dict, list)) else value
            )
    return result


# Plugin extension-point field whitelist: these fields are merged into the global config for getters to consume
# (get_tool_load_dirs/get_rules_load_dirs/get_agent_definition_dirs/
#  get_plugin_orchestrations/get_roles_dirs/get_builtin_input_handler_dirs/
#  get_replace_map, etc.).
# The remaining fields are treated as plugin-private config, isolated into a separate plugin_configs entry to avoid polluting the global config,
# and to avoid multiple plugins' same-named private fields overriding each other.
_PLUGIN_EXTENSION_FIELDS = frozenset(
    {
        "tool_load_dirs",
        "rules_load_dirs",
        "agent_definition_dirs",
        "orchestration",
        "roles_dirs",
        "after_tool_call_cb_dirs",
        "builtin_input_handler_dirs",
        "before_tool_call_cb_dirs",
        "before_model_call_cb_dirs",
        "summary_cb_dirs",
        "replace_map",
    }
)

# Key name of the separate config entry in the global config where plugin-private config is stored
PLUGIN_CONFIGS_KEY = "plugin_configs"


def _load_plugin_configs(
    merged_config: Dict[str, Any], config_file_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Load and merge plugin configuration

    Args:
        merged_config: Already-merged main config dict (project config)
        config_file_dir: Directory containing the config file, used to resolve relative paths. Defaults to the current working directory.

    Returns:
        Dict[str, Any]: Config dict after merging plugin configuration

    Priority:
        Project config > plugin config > user global config
        That is, merged_config (project config) overrides plugin_config (plugin config)
    """
    from haijunbot.haijunbot_utils.output import PrettyOutput
    from haijunbot.haijunbot_utils.config import get_data_dir

    # Automatically discover subdirectories under the plugins directory (can be disabled via the HAIJUNBOT_DISABLE_AUTO_DISCOVER environment variable)
    auto_discovered_dirs = []
    if not os.environ.get("HAIJUNBOT_DISABLE_AUTO_DISCOVER"):
        # Built-in plugins: load directly from the source built-in directory builtin/plugins/ (without copying)
        try:
            from haijunbot.haijunbot_utils.template_utils import _get_builtin_dir

            builtin_dir = _get_builtin_dir()
            if builtin_dir is not None:
                builtin_plugins_dir = builtin_dir / "plugins"
                if builtin_plugins_dir.exists() and builtin_plugins_dir.is_dir():
                    for item in sorted(builtin_plugins_dir.iterdir()):
                        if item.is_dir() and (item / "config.yaml").exists():
                            auto_discovered_dirs.append(str(item))
        except Exception:
            pass

        # External plugins: load from the data directory plugins/
        data_dir = Path(get_data_dir())
        plugins_dir = data_dir / "plugins"
        if plugins_dir.exists() and plugins_dir.is_dir():
            for item in sorted(plugins_dir.iterdir()):  # Use lexicographic order to ensure consistent ordering
                if item.is_dir() and (item / "config.yaml").exists():
                    auto_discovered_dirs.append(str(item))

    # Read the plugin directory list from the configuration
    plugin_dirs = merged_config.get("plugin_dirs", [])

    # Merge automatically discovered and config-specified plugin directories (config-specified first)
    if isinstance(plugin_dirs, list):
        all_plugin_dirs = plugin_dirs + auto_discovered_dirs
    else:
        all_plugin_dirs = auto_discovered_dirs

    if not all_plugin_dirs:
        return merged_config

    # Determine the base directory for relative paths
    base_dir = Path(config_file_dir) if config_file_dir else Path(os.getcwd())

    # First collect all plugin configs and merge them in order (later-loaded ones override earlier ones)
    combined_plugin_config: Dict[str, Any] = {}
    # Collect each plugin's private config (non-extension-point fields), isolated by plugin name to avoid overriding each other
    plugin_configs: Dict[str, Any] = {}

    # Iterate over each plugin directory and load its configuration
    for plugin_dir in all_plugin_dirs:
        if not isinstance(plugin_dir, str):
            PrettyOutput.auto_print(
                f"⚠️  An element in plugin_dirs is not a string type: {plugin_dir}"
            )
            continue

        # Support relative and absolute paths
        plugin_path = Path(plugin_dir)
        if not plugin_path.is_absolute():
            # Relative path, relative to the directory containing the config file
            plugin_path = base_dir / plugin_path

        # Check whether the plugin directory exists
        if not plugin_path.exists():
            PrettyOutput.auto_print(f"⚠️  Plugin directory does not exist: {plugin_path}")
            continue

        # Check whether the config.yaml file exists
        plugin_config_file = plugin_path / "config.yaml"
        if not plugin_config_file.exists():
            PrettyOutput.auto_print(f"⚠️  Missing config.yaml in plugin directory: {plugin_path}")
            continue

        try:
            # Read the raw content of the plugin config file
            with open(plugin_config_file, "r", encoding="utf-8") as f:
                config_content = f.read()

            # Render template variables (such as {{plugin_dir}})
            from haijunbot.haijunbot_utils.template_utils import render_plugin_config_template

            rendered_content = render_plugin_config_template(
                config_content, str(plugin_path)
            )

            # Parse YAML
            import yaml

            plugin_config = yaml.safe_load(rendered_content)

            if isinstance(plugin_config, dict):
                # If the plugin declares it applies to code_agent, register it in PluginRegistry (for code_agent to build its tool list)
                if plugin_config.get("code_agent_tools"):
                    from haijunbot.haijunbot_tools.plugin_registry import PluginRegistry

                    PluginRegistry.instance().set_plugin_code_agent_tools(
                        plugin_path.name, True
                    )
                # Split extension-point fields from private fields:
                # - Extension-point fields (whitelist) are merged into the global config for getters to consume
                # - The remaining fields are treated as plugin-private config, isolated by plugin name into plugin_configs,
                #   to avoid polluting the top level of the global config and to avoid multiple plugins' same-named private fields overriding each other
                extension_config: Dict[str, Any] = {}
                private_config: Dict[str, Any] = {}
                for key, value in plugin_config.items():
                    if key in _PLUGIN_EXTENSION_FIELDS:
                        extension_config[key] = value
                    else:
                        private_config[key] = value
                # Merge extension-point config: later-loaded plugins override earlier ones
                if extension_config:
                    combined_plugin_config = _deep_merge(
                        combined_plugin_config, extension_config
                    )
                # Collect plugin-private config (isolated by plugin name)
                if private_config:
                    plugin_configs[plugin_path.name] = private_config
                PrettyOutput.auto_print(f"✅ Loaded plugin config: {plugin_path}")
            else:
                PrettyOutput.auto_print(
                    f"⚠️  Invalid plugin config file format: {plugin_config_file}"
                )
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Failed to load plugin config {plugin_path}: {e}")

    # Aggregate each plugin's private config into a separate config entry, then merge into the global config
    if plugin_configs:
        combined_plugin_config[PLUGIN_CONFIGS_KEY] = plugin_configs

    # Finally merge the project config with the merged plugin config (project config takes priority)
    if combined_plugin_config:
        merged_config = _deep_merge(combined_plugin_config, merged_config)

    return merged_config


def _load_and_process_config(haijunbot_dir: str, config_file: str) -> None:
    """Load and process the config file
    Features:
    1. Read the config file
    2. Ensure the schema declaration exists
    3. Save the config to a global variable
    4. Process environment variables

    Args:
        haijunbot_dir: HaijunBot data directory path
        config_file: Config file path
    """
    from haijunbot.haijunbot_utils.input import user_confirm

    try:
        content, config_data = _load_config_file(config_file)
        _ensure_schema_declaration(haijunbot_dir, config_file, content, config_data)
        # Load and merge plugin config, passing the config file's directory for resolving relative paths
        config_file_dir = str(Path(config_file).parent)
        config_data = _load_plugin_configs(config_data, config_file_dir)
        set_global_config_data(config_data)
        _process_env_variables(config_data)
    except Exception:
        PrettyOutput.auto_print("❌ Failed to load config file")
        if user_confirm("The config file format is invalid. Delete and reconfigure?"):
            try:
                os.remove(config_file)
                PrettyOutput.auto_print(
                    "✅ Deleted the corrupted config file. Please restart HaijunBot to reconfigure."
                )
            except Exception:
                PrettyOutput.auto_print("❌ Failed to delete config file")
        sys.exit(1)


def generate_default_config(schema_path: str, output_path: str) -> None:
    """Generate a default YAML-format config file from the schema file

    Features:
    1. Read the config structure from the schema file
    2. Generate the default config based on the default values in the schema
    3. Automatically add the schema declaration
    4. Handle nested schema structures
    5. Preserve comments and formatting

    Args:
        schema_path: schema file path
        output_path: Path of the generated config file
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    def _generate_from_schema(schema_dict: Dict[str, Any]) -> Dict[str, Any]:
        config = {}
        if "properties" in schema_dict:
            for key, value in schema_dict["properties"].items():
                if "default" in value:
                    config[key] = value["default"]
                elif "properties" in value:  # Handle nested objects
                    config[key] = _generate_from_schema(value)
                elif value.get("type") == "array":  # handle list type
                    config[key] = []
        return config

    default_config = _generate_from_schema(schema)

    content = f"# yaml-language-server: $schema={schema_path}\n"
    content += yaml.dump(default_config, allow_unicode=True, sort_keys=False)

    with open(output_path, "w", encoding=get_default_encoding()) as f:
        f.write(content)


def _load_default_config_from_schema() -> Dict[str, Any]:
    """Generate a default config dict from schema, used to compare and remove keys equal to default values"""
    try:
        schema_path = (
            Path(__file__).parent.parent / "haijunbot_data" / "config_schema.json"
        )
        if not schema_path.exists():
            return {}
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        def _generate_from_schema(schema_dict: Dict[str, Any]) -> Dict[str, Any]:
            cfg: Dict[str, Any] = {}
            if isinstance(schema_dict, dict) and "properties" in schema_dict:
                for key, value in schema_dict["properties"].items():
                    if "default" in value:
                        cfg[key] = value["default"]
                    elif value.get("type") == "array":
                        cfg[key] = []
                    elif "properties" in value:
                        cfg[key] = _generate_from_schema(value)
            return cfg

        return _generate_from_schema(schema)
    except Exception:
        return {}


def _prune_defaults_with_schema(config_data: Dict[str, Any]) -> bool:
    """
    Delete config items consistent with schema default values, return whether changes occurred
    Only process keys defined in schema; keys not in schema will not be modified
    """
    defaults = _load_default_config_from_schema()
    if not defaults or not isinstance(config_data, dict):
        return False

    changed = False

    def _prune_node(node: Dict[str, Any], default_node: Dict[str, Any]) -> None:
        nonlocal changed
        for key in list(node.keys()):
            if key in default_node:
                dv = default_node[key]
                v = node[key]
                if isinstance(dv, dict) and isinstance(v, dict):
                    _prune_node(v, dv)
                    if not v:
                        del node[key]
                        changed = True
                elif isinstance(dv, list) and isinstance(v, list):
                    if v == dv:
                        del node[key]
                        changed = True
                else:
                    if v == dv:
                        del node[key]
                        changed = True

    _prune_node(config_data, defaults)
    return changed


def _read_old_config_file(config_file: Union[str, Path]) -> None:
    """Read and parse legacy-format env config file

    Features:
    1. Parse legacy config file in key-value pair format
    2. Support handling multi-line values
    3. Automatically strip quotes and spaces from values
    4. Save config data to global variables
    5. Set environment variables and display migration warning

    Args:
        config_file: path to legacy-format config file
    """
    config_data = {}
    current_key = None
    current_value = []
    content = read_text_file(str(config_file), errors="ignore")
    for line in content.splitlines():
        line = line.rstrip()
        if not line or line.startswith(("#", ";")):
            continue
        if "=" in line and not line.startswith((" ", "\t")):
            # handle the previously collected multi-line value
            if current_key is not None:
                processed_value = "\n".join(current_value).strip().strip("'").strip('"')
                # convert strings "true"/"false" to bool type
                if processed_value.lower() == "true":
                    final_value = True
                elif processed_value.lower() == "false":
                    final_value = False
                else:
                    final_value = processed_value  # type: ignore[assignment]
                config_data[current_key] = final_value
                current_value = []
                # parse the new key-value pair
            key_part, value_part = line.split("=", 1)
            current_key = key_part.strip()
            current_value.append(value_part.strip())
        elif current_key is not None:
            # subsequent lines of a multi-line value
            current_value.append(line.strip())
    # handle the last key-value pair
    if current_key is not None:
        processed_value = "\n".join(current_value).strip().strip("'").strip('"')
        # convert strings "true"/"false" to bool type
        if processed_value.lower() == "true":
            final_value = True
        elif processed_value.lower() == "false":
            final_value = False
        else:
            final_value = processed_value  # type: ignore[assignment]
        config_data[current_key] = final_value
    os.environ.update({str(k): str(v) for k, v in config_data.items() if v is not None})
    set_global_config_data(config_data)
    PrettyOutput.auto_print(
        "⚠️ Legacy-format config file detected. Legacy format will no longer be supported in the future; please migrate to the new format as soon as possible"
    )


# thread-local storage, used for sharing retry counters
_retry_context = threading.local()

# separate thread-local storage, for the while_success retry counter
_retry_context_success = threading.local()

# separate thread-local storage, for the while_true retry counter
_retry_context_true = threading.local()


def _get_retry_count() -> int:
    """Get the current thread's retry count (deprecated, kept for backward compatibility)"""
    if not hasattr(_retry_context, "count"):
        _retry_context.count = 0
    return int(_retry_context.count)


def _increment_retry_count() -> int:
    """Increment retry count and return the new count value (deprecated, kept for backward compatibility)"""
    if not hasattr(_retry_context, "count"):
        _retry_context.count = 0
    _retry_context.count += 1
    return int(_retry_context.count)


def _reset_retry_count() -> None:
    """Reset retry count (deprecated, kept for backward compatibility)"""
    _retry_context.count = 0


# counter functions dedicated to while_success
def _get_retry_count_success() -> int:
    """Get the current thread's while_success retry count"""
    if not hasattr(_retry_context_success, "count"):
        _retry_context_success.count = 0
    return int(_retry_context_success.count)


def _increment_retry_count_success() -> int:
    """Increment while_success retry count and return the new count value"""
    if not hasattr(_retry_context_success, "count"):
        _retry_context_success.count = 0
    _retry_context_success.count += 1
    return int(_retry_context_success.count)


def _reset_retry_count_success() -> None:
    """Reset while_success retry count"""
    _retry_context_success.count = 0


# counter functions dedicated to while_true
def _get_retry_count_true() -> int:
    """Get the current thread's while_true retry count"""
    if not hasattr(_retry_context_true, "count"):
        _retry_context_true.count = 0
    return int(_retry_context_true.count)


def _increment_retry_count_true() -> int:
    """Increment while_true retry count and return the new count value"""
    if not hasattr(_retry_context_true, "count"):
        _retry_context_true.count = 0
    _retry_context_true.count += 1
    return int(_retry_context_true.count)


def _reset_retry_count_true() -> None:
    """Reset while_true retry count"""
    _retry_context_true.count = 0


def while_success(func: Callable[[], Any]) -> Any:
    """Repeatedly execute the function until success (log accumulation then unified print, avoid boxing each time)

    Args:
    func -- the function to execute

    Returns:
    function execution result

    Note:
    Uses a dedicated retry counter, retries up to 6 times, using exponential backoff (first wait 1s)
    """
    MAX_RETRIES = 6
    result: Any = None

    while True:
        # check interrupt signal; if interrupted, return directly (without clearing the interrupt flag)
        if get_interrupt() > 0:
            return None
        try:
            result = func()
            _reset_retry_count_success()  # reset counter after success
            break
        except Exception as e:
            retry_count = _increment_retry_count_success()
            if retry_count <= MAX_RETRIES:
                # exponential backoff: 1st wait 1s (2^0), 2nd wait 2s (2^1), 3rd wait 4s (2^2), 4th wait 8s (2^3), 6th wait 32s (2^5)
                sleep_time = 2 ** (retry_count - 1)
                if retry_count < MAX_RETRIES:
                    PrettyOutput.auto_print(
                        f"⚠️ Exception occurred:\n{e}\nRetrying ({retry_count}/{MAX_RETRIES}), waiting {sleep_time}s..."
                    )
                    time.sleep(sleep_time)
                else:
                    PrettyOutput.auto_print(
                        f"⚠️ Exception occurred:\n{e}\nMaximum retry count reached ({retry_count}/{MAX_RETRIES})"
                    )
                    _reset_retry_count_success()
                    raise
            else:
                _reset_retry_count_success()
                raise
    return result


def while_true(func: Callable[[], bool]) -> Any:
    """Repeatedly execute the function until it returns True (log accumulation then unified print, avoid boxing each time)

    Args:
        func: the function to execute, must return a boolean value

    Returns:
        the True value finally returned by the function

    Note:
        Unlike while_success, this function only checks whether the return is True,
        does not catch exceptions; exceptions are thrown directly.
        Uses a dedicated retry counter, retries up to 6 times, using exponential backoff (first wait 1s)
    """
    MAX_RETRIES = 6
    ret: bool = False

    while True:
        # check interrupt signal; if interrupted, return directly (without clearing the interrupt flag)
        if get_interrupt() > 0:
            return False
        try:
            ret = func()
            if ret:
                _reset_retry_count_true()  # reset counter after success
                break
        except Exception:
            # exception is thrown directly, not caught
            _reset_retry_count_true()
            raise

        retry_count = _increment_retry_count_true()
        if retry_count <= MAX_RETRIES:
            # exponential backoff: 1st wait 1s (2^0), 2nd wait 2s (2^1), 3rd wait 4s (2^2), 4th wait 8s (2^3), 6th wait 32s (2^5)
            sleep_time = 2 ** (retry_count - 1)
            if retry_count < MAX_RETRIES:
                PrettyOutput.auto_print(
                    f"⚠️ Empty value returned, retrying ({retry_count}/{MAX_RETRIES}), waiting {sleep_time}s..."
                )
                time.sleep(sleep_time)
            else:
                PrettyOutput.auto_print(
                    f"⚠️ Empty value returned, maximum retry count reached ({retry_count}/{MAX_RETRIES})"
                )
                _reset_retry_count_true()
                break
        else:
            _reset_retry_count_true()
            break
    return ret


def get_file_md5(filepath: str) -> str:
    """Calculate the MD5 hash of the file content

    Args:
        filepath: path of the file to compute the hash for

    Returns:
        str: MD5 hash of the file content (to reduce memory usage, only the first 100MB is read for computation)
    """
    # streaming read to avoid loading 100MB into memory at once (MD5 is used for file verification, not security purposes)
    h = hashlib.md5(usedforsecurity=False)
    max_bytes = 100 * 1024 * 1024  # consistent with the original implementation: only read the first 100MB
    buf_size = 8 * 1024 * 1024  # 8MB buffer
    read_bytes = 0
    with open(filepath, "rb") as f:
        while read_bytes < max_bytes:
            to_read = min(buf_size, max_bytes - read_bytes)
            chunk = f.read(to_read)
            if not chunk:
                break
            h.update(chunk)
            read_bytes += len(chunk)
    return h.hexdigest()


def get_file_line_count(filename: str) -> int:
    """Count the number of lines in the file

    Args:
        filename: path of the file to count lines for

    Returns:
        int: number of lines in the file, returns 0 if the file cannot be read
    """
    try:
        # use streaming line-by-line counting to avoid reading the entire file into memory
        enc = detect_file_encoding(filename) or get_default_encoding()
        with open(filename, "r", encoding=enc, errors="ignore") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def is_context_overflow(
    content: str,
    platform: Optional[Any] = None,
) -> bool:
    """Determine whether the file content exceeds the context limit

    Args:
        content: the content to check
        platform: platform instance (optional); if provided, uses the remaining token count for the judgment

    Returns:
        bool: returns True if the content exceeds the context limit
    """
    # fast length estimation: if the content length clearly exceeds the limit, return True directly without precise token calculation
    if content:
        # rough estimation: assume each token averages about 4 characters; conservative estimate uses 3.5 characters/token
        estimated_tokens = len(content) // 3.5

        # get the maximum token limit
        max_tokens = get_max_input_token_count()

        # if the estimated token count exceeds 150% of the limit, consider it exceeded (avoid precise calculation)
        if estimated_tokens > max_tokens * 1.5:
            return True

        # if the estimated token count is less than 50% of the limit, consider it safe
        if estimated_tokens < max_tokens * 0.5:
            return False

    # only perform precise token calculation when the estimated result is ambiguous
    content_tokens = get_context_token_count(content)

    # prefer using the remaining token count
    if platform is not None:
        try:
            remaining_tokens = platform.get_remaining_token_count()
            # if the content token count exceeds 80% of the remaining tokens, consider it exceeding the limit
            threshold = int(remaining_tokens * 0.8)
            if threshold > 0:
                return content_tokens > threshold
        except Exception as e:
            save_exception(
                e, module="haijunbot_utils.utils", function="is_context_overflow"
            )
            pass

    # fallback: use the input window limit
    return content_tokens > get_max_input_token_count()


def get_loc_stats() -> str:
    """Use the loc command to get code statistics for the current directory

    Returns:
        str: raw string output by the loc command, returns an empty string on failure
    """
    try:
        result = subprocess.run(["loc"], capture_output=True)
        return decode_output(result.stdout) if result.returncode == 0 else ""
    except FileNotFoundError:
        return ""


def is_uv_tool_installed_haijunbot() -> bool:
    """Detect whether the current HaijunBot is installed via uv (uv tool install or uv pip install).

    Returns:
        bool: returns True if installed via uv, otherwise False
    """
    # check the current Python interpreter path
    # path characteristics of uv tool installation:
    # - Linux/macOS: ~/.local/share/uv/tools/
    # - Windows: %LOCALAPPDATA%\uv\uv\tools\
    exec_path = Path(sys.executable).resolve()
    exec_path_str = str(exec_path).lower()

    # check whether the path contains uv/tools/ (uv tool install)
    if "uv/tools" in exec_path_str:
        return True

    # check whether it is uv pip install
    # method: try running uv pip show haijunbot-ai-assistant
    try:
        result = subprocess.run(
            ["uv", "pip", "show", "haijunbot-ai-assistant"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # if the command succeeds and the output contains the package name, it was installed via uv pip
        if result.returncode == 0 and "haijunbot-ai-assistant" in result.stdout:
            return True
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ):
        # uv command unavailable or execution failed
        pass

    return False


def _pull_git_repo(repo_path: Path, repo_type: str) -> None:
    """Perform a git pull on the specified git repository and determine whether there is an update based on the commit hash."""
    git_dir = repo_path / ".git"
    if not git_dir.is_dir():
        return

    # auto-upgrade only for users who installed via uv (uv tool install or uv pip install)
    if not is_uv_tool_installed_haijunbot():
        PrettyOutput.auto_print(
            f"ℹ️ Detected that your HaijunBot was not installed via uv, skipping auto-update for '{repo_path.name}'."
        )
        PrettyOutput.auto_print("   To use the auto-update feature, please reinstall using any of the following commands:")
        PrettyOutput.auto_print(
            "   uv tool install git+https://github.com/takebox/HaijunBot.git"
        )
        PrettyOutput.auto_print("   or")
        PrettyOutput.auto_print(
            "   uv pip install git+https://github.com/takebox/HaijunBot.git"
        )
        return

    try:
        # check whether there is a remote repository
        remote_result = subprocess.run(
            ["git", "remote"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=10,
        )
        if not decode_output(remote_result.stdout).strip():
            return

        # check git repository status
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=10,
        )
        has_local_changes = bool(decode_output(status_result.stdout))
        if has_local_changes:
            # when there are uncommitted changes, stash to save first, then stash pop to restore after pull
            try:
                subprocess.run(
                    ["git", "stash"],
                    cwd=repo_path,
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as e:
                error_message = decode_output(e.stderr).strip() if e.stderr else str(e)
                PrettyOutput.auto_print(
                    f"⚠️ stash '{repo_path.name}' failed, skipping update: {error_message}"
                )
                return

        # check whether it is an empty repository
        ls_remote_result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=10,
        )

        if not decode_output(ls_remote_result.stdout).strip():
            return

        # execute git pull
        subprocess.run(
            ["git", "pull"],
            cwd=repo_path,
            capture_output=True,
            check=True,
            timeout=60,
        )

        # if local changes were stashed earlier, restore after pull
        if has_local_changes:
            try:
                subprocess.run(
                    ["git", "stash", "pop"],
                    cwd=repo_path,
                    capture_output=True,
                    check=True,
                    timeout=30,
                )
            except subprocess.CalledProcessError as e:
                error_message = decode_output(e.stderr).strip() if e.stderr else str(e)
                PrettyOutput.auto_print(
                    f"⚠️ stash pop '{repo_path.name}' failed (there may be conflicts), please resolve manually: {error_message}"
                )

    except FileNotFoundError:
        PrettyOutput.auto_print(f"⚠️ git command not found, skipping update for '{repo_path.name}'.")
    except subprocess.TimeoutExpired:
        PrettyOutput.auto_print(f"❌ Update of '{repo_path.name}' timed out.")
    except subprocess.CalledProcessError as e:
        error_message = decode_output(e.stderr).strip() if e.stderr else str(e)
        PrettyOutput.auto_print(f"❌ Update of '{repo_path.name}' failed: {error_message}")
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Unknown error occurred while updating '{repo_path.name}': {str(e)}")


def daily_check_git_updates(repo_dirs: List[str], repo_type: str) -> None:
    """
    Perform a once-daily git update check for the specified directory list.

    Args:
        repo_dirs (List[str]): list of git repository directories to check.
        repo_type (str): the repository type name, e.g. "tool" or "methodology", used for log output.
    """
    # auto-upgrade only for users who installed via uv tool
    if not is_uv_tool_installed_haijunbot():
        return

    data_dir = Path(str(get_data_dir()))
    last_check_file = data_dir / f"{repo_type}_updates_last_check.txt"
    should_check_for_updates = True

    if last_check_file.exists():
        try:
            last_check_timestamp = float(last_check_file.read_text())
            last_check_date = datetime.fromtimestamp(last_check_timestamp).date()
            if last_check_date == datetime.now().date():
                should_check_for_updates = False
        except (ValueError, IOError):
            pass

    if should_check_for_updates:
        for repo_dir in repo_dirs:
            p_repo_dir = Path(repo_dir)
            if p_repo_dir.exists() and p_repo_dir.is_dir():
                _pull_git_repo(p_repo_dir, repo_type)
        try:
            last_check_file.write_text(str(time.time()))
        except IOError as e:
            PrettyOutput.auto_print(f"⚠️ Unable to write git update check timestamp: {e}")


def atomic_write_json(
    file_path: Union[str, Path],
    data: Any,
    *,
    indent: Optional[int] = None,
    ensure_ascii: bool = False,
    default: Optional[Callable[[Any], Any]] = None,
) -> None:
    """Atomically write a JSON file to avoid leaving truncated invalid JSON when the process is interrupted.

    Using ``open(path, "w") + json.dump`` directly is a streaming write: if the process is
    interrupted (Ctrl+C, killed, crash) during the write, the target file will remain in a "half-written" state,
    and the next read will raise ``JSONDecodeError: Expecting value``, making the session unrecoverable.

    This function first writes to a temporary file in the same directory, then after flush + fsync uses ``os.replace``
    to atomically replace the target file. This way, at any moment the target file is either the old complete content or the new
    complete content, never truncated.

    Args:
        file_path: target file path
        data: the object to serialize
        indent: indentation (None means compact output)
        ensure_ascii: whether to escape non-ASCII characters
        default: conversion function for non-serializable objects
    """
    import tempfile

    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # the temporary file must be in the same directory as the target file, otherwise os.replace may fail across devices
    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(
                data,
                f,
                ensure_ascii=ensure_ascii,
                indent=indent,
                default=default,
            )
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        # any exception (including KeyboardInterrupt) must clean up the temporary file to avoid leftovers
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def cleanup_stale_tmp_files(
    directory: Union[str, Path], max_age_seconds: float = 3600
) -> int:
    """Clean up temporary files left by :func:`atomic_write_json` in the directory.

    Normally the temporary file is deleted or renamed; but when the process is SIGKILLed, cleanup cannot be performed,
    leaving ``.<name>.<random>.tmp``. These leftover files do not affect data correctness (the target file
    is always complete), but they pollute the directory, so this function is provided for cleanup at startup.

    Args:
        directory: the directory to clean up
        max_age_seconds: only clean up files whose modification time is earlier than this many seconds, to avoid accidentally deleting temporary files being written

    Returns:
        int: the actual number of files deleted
    """
    import time

    removed = 0
    try:
        entries = os.listdir(directory)
    except OSError:
        return 0

    now = time.time()
    for name in entries:
        if not (name.startswith(".") and name.endswith(".tmp")):
            continue
        full = os.path.join(str(directory), name)
        try:
            if now - os.path.getmtime(full) < max_age_seconds:
                continue
            os.unlink(full)
            removed += 1
        except OSError:
            continue
    return removed


def find_repeated_pattern(
    text: str, min_pattern_len: int = 10, min_repeat_count: int = 2
) -> Tuple[str, int, float]:
    """Find a consecutively repeating pattern at the end of a string.

    Leveraging the premise that the repeating pattern appears at the end, build the KMP failure function in reverse from the end,
    detecting the minimal period and repeat count in O(n) time.

    Args:
        text: the string to analyze
        min_pattern_len: minimum pattern length (default 10)
        min_repeat_count: minimum repeat count (default 2)

    Returns:
        Tuple[str, int, float]:
            - the repeated string content (returns an empty string if not found)
            - the repeat count (returns 0 if not found)
            - the ratio of repeated content to total content, 0.0~1.0 (returns 0.0 if not found)
    """
    if not text or len(text) < min_pattern_len * min_repeat_count:
        return "", 0, 0.0

    total_len = len(text)

    # build the KMP failure function for the reversed text, O(n)
    # after reversal, the original "end repetition" becomes "beginning repetition", which KMP can detect directly
    rev = text[::-1]
    fail = [0] * total_len
    j = 0
    for i in range(1, total_len):
        while j > 0 and rev[i] != rev[j]:
            j = fail[j - 1]
        if rev[i] == rev[j]:
            j += 1
        fail[i] = j

    # for each prefix of the reversed text (i.e. each suffix of the original text), find the minimal period
    # the prefix rev[0:i+1] of rev corresponds to the suffix text[total_len-1-i:] of the original text
    # prefix length L = i + 1, period = L - fail[i] (when L % period == 0)
    best_pattern = ""
    best_count = 0
    best_ratio = 0.0
    checked_periods = set()

    for i in range(min_pattern_len - 1, total_len):
        L = i + 1  # prefix length (i.e. suffix length)
        period = L - fail[i]
        if L % period != 0:
            continue
        if period in checked_periods:
            continue
        checked_periods.add(period)

        # in the original text, the last L characters consist of (L/period) patterns with period 'period'
        # but we need to verify the consecutive repeat count from the end backward (may exceed L/period)
        # because the repetition may extend into the prefix part
        pattern = text[total_len - period :]  # the last 'period' characters of the original text
        count = 0
        pos = total_len
        while pos >= period and text[pos - period : pos] == pattern:
            count += 1
            pos -= period

        if count >= min_repeat_count:
            ratio = (count * period) / total_len
            if ratio > best_ratio:
                best_pattern = pattern
                best_count = count
                best_ratio = ratio
            if best_ratio > 0.9:
                break

    return best_pattern, best_count, best_ratio


def is_repeating_text(
    text: str,
    min_text_len: int = 1000,
    min_total_repeat_len: int = 500,
    min_repeat_count: int = 5,
    min_ratio: float = 0.3,
) -> Tuple[bool, str, int, float]:
    """Determine whether a string has begun abnormally repeating.

    Criteria:
        - total string length > min_text_len (default 1000)
        - total length of repeated content (pattern length × count) > min_total_repeat_len (default 500)
        - repeat count > min_repeat_count (default 5)
        - repetition ratio > min_ratio (default 30%)

    Args:
        text: the string to detect
        min_text_len: minimum total string length
        min_total_repeat_len: minimum total length of repeated content (pattern length × count)
        min_repeat_count: minimum repeat count
        min_ratio: Minimum repetition ratio

    Returns:
        Tuple[bool, str, int, float]:
            - Whether it is determined to be a repetition
            - The repeated string content
            - The repetition count
            - The repetition ratio
    """
    if len(text) <= min_text_len:
        return False, "", 0, 0.0

    pattern, count, ratio = find_repeated_pattern(
        text, min_pattern_len=10, min_repeat_count=min_repeat_count
    )

    total_repeat_len = len(pattern) * count
    if (
        total_repeat_len > min_total_repeat_len
        and count > min_repeat_count
        and ratio > min_ratio
    ):
        return True, pattern, count, ratio

    return False, pattern, count, ratio


def extract_json_from_text(text: str, start_pos: int = 0) -> Tuple[Optional[str], int]:
    """Extract a complete JSON object from the text (via bracket matching)

    Args:
        text: The text to extract from
        start_pos: The position to start searching from

    Returns:
        Tuple[Optional[str], int]:
            - The first element is the extracted JSON string (if found), otherwise None
            - The second element is the position after the JSON ends
    """
    # Skip whitespace characters
    pos = start_pos
    while pos < len(text) and text[pos] in (" ", "\t", "\n", "\r"):
        pos += 1

    if pos >= len(text):
        return None, pos

    # Check whether it starts with { or [
    if text[pos] not in ("{", "["):
        return None, pos

    open_char = text[pos]
    close_char = "}" if open_char == "{" else "]"

    # Use bracket matching to find the complete JSON object/array
    brace_count = 0
    in_string = False
    escape_next = False
    string_char = None

    json_start = pos
    for i in range(pos, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if not in_string:
            if char in ('"', "'"):
                in_string = True
                string_char = char
            elif char == open_char:
                brace_count += 1
            elif char == close_char:
                brace_count -= 1
                if brace_count == 0:
                    # Found the complete JSON object/array
                    return text[json_start : i + 1], i + 1
        else:
            if char == string_char:
                in_string = False
                string_char = None

    return None, len(text)
