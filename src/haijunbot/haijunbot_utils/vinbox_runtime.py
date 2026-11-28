# -*- coding: utf-8 -*-
"""Runtime adapter so HaijunBot can live inside the Vinbox machine.

Vinbox owns the LLM lane, the real Chromium (CDP 9222), the pwsh terminal and
the File Manager. Nothing here modifies Vinbox: this module only *reads* its
state and mirrors the environment ``app/terminal_pwsh.py`` gives the terminal,
so every HaijunBot subprocess behaves like a command typed in Vinbox.

Detection order: ``VINBOX_HOME`` (the operator's explicit signal), then
``/app/vinbox`` (the container path), then a *structural* check: the package is
physically inside a tree that carries Vinbox's own markers (``HAIJUN.md`` and
``app/llm/model_registry.py``). A checkout that merely sits next to a Vinbox
tree has neither marker and stays standalone.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

DEFAULT_VINBOX_HOME = Path("/app/vinbox")
DATA_SUBDIR = Path("data") / "haijunbot"
DEFAULT_DISPLAY = ":99"
DEFAULT_CDP_URL = "http://127.0.0.1:9222"


def _looks_like_vinbox(path: Path) -> bool:
    """True only when *path* carries Vinbox's own markers."""
    try:
        return (path / "HAIJUN.md").is_file() and (
            path / "app" / "llm" / "model_registry.py"
        ).is_file()
    except OSError:
        return False


def _structural_home() -> Optional[Path]:
    """The Vinbox tree this package lives in, if any."""
    try:
        here = Path(__file__).resolve()
    except OSError:
        return None
    for parent in here.parents:
        if _looks_like_vinbox(parent):
            return parent
    return None


def vinbox_home() -> Optional[Path]:
    """The Vinbox root, or ``None`` when HaijunBot runs standalone."""
    # Explicit first, then the container path, then the structural marker
    # check. A checkout that merely sits next to a Vinbox tree stays standalone.
    candidates = []
    env_home = os.environ.get("VINBOX_HOME", "").strip()
    if env_home:
        candidates.append(Path(env_home))
    candidates.append(DEFAULT_VINBOX_HOME)
    structural = _structural_home()
    if structural is not None:
        candidates.append(structural)

    for candidate in candidates:
        try:
            if candidate.is_dir() and (
                candidate != structural or _looks_like_vinbox(candidate)
            ):
                return candidate
        except OSError:
            continue
    return None


def is_vinbox() -> bool:
    return vinbox_home() is not None


def program_file_dir() -> Path:
    """Vinbox's File Manager root: where installs and agent output belong."""
    home = vinbox_home()
    if home is None:
        return Path.cwd()
    return home / "app" / "program-file"


def data_dir() -> Path:
    """Persistent HaijunBot state inside Vinbox (``./data`` is bind-mounted)."""
    home = vinbox_home()
    if home is None:
        return Path.cwd() / DATA_SUBDIR
    return home / DATA_SUBDIR


def models_settings_path() -> Optional[Path]:
    home = vinbox_home()
    if home is None:
        return None
    return home / "data" / "models.json"


def current_model_id() -> Optional[str]:
    """The model id selected in Vinbox Settings (MODELS tab), if readable."""
    path = models_settings_path()
    if path is None or not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    current = payload.get("current")
    if isinstance(current, str) and current.strip():
        return current.strip()
    if isinstance(current, dict):
        model_id = current.get("id")
        if isinstance(model_id, str) and model_id.strip():
            return model_id.strip()
    return None


class PwshNotFound(RuntimeError):
    """PowerShell Core (pwsh) is required and was not found on this machine."""


# Tempat pemasangan yang lazim, dipakai kalau PATH tidak memuat pwsh.
# Windows: MSI/winget, Linux: paket/tarball, macOS: brew cask.
_PWSH_CANDIDATES = {
    "nt": (
        r"%ProgramFiles%\PowerShell\7\pwsh.exe",
        r"%ProgramFiles%\PowerShell\7-preview\pwsh.exe",
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe",
    ),
    "posix": (
        "/usr/bin/pwsh",
        "/usr/local/bin/pwsh",
        "/opt/microsoft/powershell/7/pwsh",
        "/snap/bin/pwsh",
        "/opt/homebrew/bin/pwsh",
    ),
}

_PWSH_INSTALL_HINT = {
    "nt": "winget install --id Microsoft.PowerShell --source winget",
    "posix": (
        "Linux: apt-get install -y powershell (atau tarball powershell-7-linux-x64) "
        "/ macOS: brew install --cask powershell"
    ),
}


def find_pwsh() -> Optional[str]:
    """Path pwsh kalau ada, ``None`` kalau tidak — tanpa melempar.

    Dipakai laporan status (``status()``, panel, bridge): laporan harus tetap
    bisa dibaca di mesin yang belum punya pwsh, sementara eksekusi perintah
    memakai :func:`pwsh_path` yang melempar :class:`PwshNotFound`.
    """
    override = os.environ.get("HAIJUNBOT_SHELL", "").strip()
    if override:
        return override

    found = shutil.which("pwsh")
    if found:
        return found

    platform_key = "nt" if os.name == "nt" else "posix"
    for raw in _PWSH_CANDIDATES[platform_key]:
        candidate = Path(os.path.expandvars(raw))
        if candidate.is_file():
            return str(candidate)
    return None


def pwsh_path() -> str:
    """Path absolut PowerShell Core untuk platform ini.

    Vinbox menjalankan setiap perintah lewat ``pwsh`` di Windows, Linux dan
    macOS. ``cmd.exe``, ``powershell.exe`` dan ``bash`` tidak dipakai, jadi pwsh
    yang tidak ada adalah ERROR dengan perintah pemasangan yang jelas — bukan
    alasan untuk diam-diam memakai shell lain.

    ``HAIJUNBOT_SHELL`` menimpa hasil pencarian (mis. pwsh portabel).
    """
    found = find_pwsh()
    if found:
        return found

    platform_key = "nt" if os.name == "nt" else "posix"
    raise PwshNotFound(
        "pwsh (PowerShell Core) tidak ditemukan. Vinbox hanya memakai pwsh, "
        "bukan cmd.exe/powershell.exe/bash.\n"
        f"Pasang dulu: {_PWSH_INSTALL_HINT[platform_key]}\n"
        "Atau set HAIJUNBOT_SHELL ke path pwsh yang sudah ada."
    )


def shell_path() -> str:
    """Nama lama untuk :func:`pwsh_path`; tetap dipakai modul lain."""
    return pwsh_path()


def pwsh_argv(command: str, *, non_interactive: bool = True) -> list[str]:
    """Argv untuk menjalankan *command* di pwsh, bukan di cmd.exe.

    Selalu dipakai dengan ``shell=False``: perintah jadi satu argumen
    ``-Command``, sehingga tidak ada cmd.exe/bash yang ikut menafsirkan teks.
    """
    argv = [pwsh_path(), "-NoLogo"]
    if non_interactive:
        argv.append("-NoProfile")
    argv += ["-Command", command]
    return argv


def command_argv(interpreter: Optional[str], command: str) -> list[str]:
    """Argv untuk satu perintah teks, memakai *interpreter* kalau masuk akal.

    ``pwsh`` mendapat ``-NoLogo -NoProfile -Command``; python mendapat ``-c``.
    Shell lain (cmd.exe, bash, sh, zsh) tidak dipakai Vinbox, jadi perintah tetap
    dijalankan lewat pwsh.
    """
    exe = (interpreter or "").strip() or pwsh_path()
    name = os.path.basename(exe).lower()
    if name.startswith("pwsh"):
        return [exe, "-NoLogo", "-NoProfile", "-Command", command]
    if name.startswith("python"):
        return [exe, "-c", command]
    return pwsh_argv(command)



def working_dir() -> str:
    """Commands run in the File Manager, never in Vinbox's own source tree."""
    if not is_vinbox():
        return os.getcwd()
    return str(program_file_dir())


def cdp_url() -> str:
    return (
        os.environ.get("BROWSER_CDP_URL", "").strip()
        or os.environ.get("VINBOX_CDP_URL", "").strip()
        or DEFAULT_CDP_URL
    )


def new_cdp_page(playwright: Any) -> Any:
    """Attach to Vinbox's single Chromium and return ``(browser, page)``.

    Vinbox forbids a second Chromium: the browser belongs to the center panel
    and must stay open. Callers close only the page they opened.
    """
    browser = playwright.chromium.connect_over_cdp(cdp_url())
    contexts = list(getattr(browser, "contexts", []) or [])
    context = contexts[0] if contexts else browser.new_context()
    return browser, context.new_page()


def _log_execution(execution_id: str, script_content: str, result: Dict[str, Any]) -> None:
    """Append an execution record to the data directory."""
    try:
        d = data_dir()
        d.mkdir(parents=True, exist_ok=True)
        log_file = d / "executions.jsonl"
        record = {
            "id": execution_id,
            "timestamp": datetime.now().isoformat(),
            "script_content": script_content[:500] if script_content else "",
            "success": result.get("success", False),
            "stdout": (result.get("stdout") or "")[:200],
            "stderr": (result.get("stderr") or "")[:200],
        }
        # Keep only last 50 entries to avoid unbounded growth
        entries: List[Dict[str, Any]] = []
        if log_file.is_file():
            try:
                existing = json.loads(log_file.read_text(encoding="utf-8"))
                if isinstance(existing, list):
                    entries = existing
            except (OSError, ValueError):
                pass
        entries.append(record)
        entries = entries[-50:]
        log_file.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001 - logging must not raise
        pass


def process_env(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Environment for HaijunBot subprocesses living inside Vinbox.

    Mirrors ``app/terminal_pwsh.py:shell_env``: File Manager bin/packages first
    on PATH and PYTHONPATH, ``PIP_TARGET`` into the File Manager, DISPLAY on the
    Vinbox Xvfb screen, and the persistent HaijunBot data directory.
    """
    env = dict(base if base is not None else os.environ)
    home = vinbox_home()
    if home is None:
        return env

    install_root = program_file_dir()
    install_bin = install_root / "bin"
    install_packages = install_root / "packages"
    install_lib = install_root / "lib"
    env["VINBOX_HOME"] = str(home)
    env["TERM"] = env.get("TERM") or "xterm-256color"
    env.setdefault("DISPLAY", DEFAULT_DISPLAY)
    env.setdefault("BROWSER_CDP_URL", cdp_url())
    env.setdefault("HAIJUNBOT_DATA_DIR", str(data_dir()))
    env["SHELL"] = env.get("HAIJUNBOT_SHELL") or shell_path()

    path_parts = [str(install_bin), str(install_packages / "bin")]
    path_parts += [part for part in (env.get("PATH") or "").split(os.pathsep) if part]
    env["PATH"] = os.pathsep.join(dict.fromkeys(path_parts))

    python_parts = [str(install_packages), str(install_lib)]
    python_parts += [
        part for part in (env.get("PYTHONPATH") or "").split(os.pathsep) if part
    ]
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(python_parts))

    env["PIP_TARGET"] = str(install_packages)
    return env


def apply_process_defaults() -> bool:
    """Make the current process behave like Vinbox. Returns True when inside.

    Only defaults are set: an operator can still override every value.
    """
    if not is_vinbox():
        return False
    for key, value in process_env(os.environ).items():
        os.environ.setdefault(key, value)
    try:
        data_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return True


def status() -> Dict[str, Any]:
    """Honest readiness report for the panel and health checks.

    Laporan tidak boleh gagal hanya karena pwsh belum dipasang: shell yang tidak
    ada dilaporkan sebagai ``None`` + ``pwsh_present: False``. Eksekusi perintah
    tetap memakai :func:`pwsh_path` yang melempar :class:`PwshNotFound`.
    """
    home = vinbox_home()
    shell = find_pwsh()
    result: Dict[str, Any] = {
        "inside_vinbox": home is not None,
        "vinbox_home": str(home) if home else None,
        "data_dir": str(data_dir()) if home else None,
        "program_file": str(program_file_dir()) if home else None,
        "shell": shell,
        "working_dir": working_dir(),
        "cdp_url": cdp_url(),
        "model": current_model_id(),
    }
    if home is not None:
        result["pwsh_present"] = shell is not None
        result["models_settings"] = str(models_settings_path() or "")
    return result