# -*- coding: utf-8 -*-
"""Optimizer utility functions."""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeOptions
from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeStats


def run_cmd(
    cmd: List[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
) -> Tuple[int, str, str]:
    """Execute a command and return the result."""
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=dict(os.environ, **(env or {})),
    )
    try:
        out, err = p.communicate(timeout=timeout if timeout and timeout > 0 else None)
        return p.returncode, out, err
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        err_msg = f"Command '{' '.join(cmd)}' timed out after {timeout} seconds."
        if err:
            err_msg += f"\n{err}"
        return -1, out, err_msg


def cargo_check(
    crate_dir: Path,
    stats: OptimizeStats,
    max_checks: int,
    timeout: Optional[int] = None,
) -> Tuple[bool, str]:
    """Run cargo test and return a summary of the result."""
    # Uniformly use cargo test as the verification method
    if max_checks and stats.cargo_checks >= max_checks:
        return False, "cargo test budget exhausted"
    code, out, err = run_cmd(["cargo", "test", "-q"], crate_dir, timeout=timeout)
    stats.cargo_checks += 1
    ok = code == 0
    diag = err.strip() or out.strip()
    # Take the first line as the summary
    first_line = next((ln for ln in diag.splitlines() if ln.strip()), "")
    return ok, first_line


def run_cargo_fmt(crate_dir: Path) -> None:
    """Run cargo fmt to format the code. A fmt failure does not affect the main flow; only a warning is logged."""
    try:
        res = subprocess.run(
            ["cargo", "fmt"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(crate_dir),
        )
        if res.returncode == 0:
            PrettyOutput.auto_print("✅ [c2rust-optimizer][fmt] Code formatting completed")
        else:
            # A fmt failure does not affect the main flow; only log a warning
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-optimizer][fmt] Code formatting failed (non-fatal): {res.stderr or res.stdout}"
            )
    except Exception as e:
        # A fmt failure does not affect the main flow; only log a warning
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-optimizer][fmt] Code formatting exception (non-fatal): {e}"
        )


def check_clippy_warnings(crate_dir: Path) -> Tuple[bool, str]:
    """
    Check whether there are clippy warnings.
    Uses JSON format output for precise parsing and pinpointing warnings.
    Returns (has_warnings, json_output); has_warnings being True means there are warnings, and json_output is the JSON-format output.
    """
    try:
        res = subprocess.run(
            ["cargo", "clippy", "--message-format=json", "--", "-W", "clippy::all"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(crate_dir),
        )
        # clippy's JSON output is usually on stdout
        stdout_output = (res.stdout or "").strip()
        stderr_output = (res.stderr or "").strip()

        # Parse the JSON output and extract warning information
        warnings = []
        if stdout_output:
            for line in stdout_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    # Only handle messages of type warning
                    if (
                        msg.get("reason") == "compiler-message"
                        and msg.get("message", {}).get("level") == "warning"
                    ):
                        warnings.append(msg)
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Ignore lines that cannot be parsed (possibly other output)
                    continue

        has_warnings = len(warnings) > 0

        # Debug output
        if has_warnings:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-optimizer][clippy-check] Detected {len(warnings)} Clippy warnings"
            )
        elif res.returncode != 0:
            # If the return code is non-zero but there are no warnings, it may be a compile error
            PrettyOutput.auto_print(
                f"📊 [c2rust-optimizer][clippy-check] Clippy returned a non-zero exit code ({res.returncode}) but no warnings were detected; it may be a compile error"
            )
            if stderr_output:
                PrettyOutput.auto_print(
                    f"📊 [c2rust-optimizer][clippy-check] Error output preview (first 200 characters): {stderr_output[:200]}"
                )

        # Return the JSON-format output (for later parsing)
        return has_warnings, stdout_output
    except Exception as e:
        # Assume no warnings when the check fails, to avoid blocking the flow
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-optimizer][clippy-check] Exception while checking Clippy warnings (non-fatal): {e}"
        )
        return False, ""


def check_missing_safety_doc_warnings(crate_dir: Path) -> Tuple[bool, str]:
    """
    Check whether there are missing_safety_doc warnings.
    Uses JSON format output for precise parsing and pinpointing warnings.
    Returns (has_warnings, json_output); has_warnings being True means there are warnings, and json_output is the JSON-format output.
    """
    try:
        res = subprocess.run(
            [
                "cargo",
                "clippy",
                "--message-format=json",
                "--",
                "-W",
                "clippy::missing_safety_doc",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(crate_dir),
        )
        # clippy's JSON output is usually on stdout
        stdout_output = (res.stdout or "").strip()
        stderr_output = (res.stderr or "").strip()

        # Parse the JSON output and extract warning information
        warnings = []
        if stdout_output:
            for line in stdout_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    # Only handle messages of type warning that are missing_safety_doc
                    if msg.get("reason") == "compiler-message":
                        message = msg.get("message", {})
                        if message.get("level") == "warning":
                            code = message.get("code", {})
                            code_str = code.get("code", "") if code else ""
                            if "missing_safety_doc" in code_str:
                                warnings.append(msg)
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Ignore lines that cannot be parsed (possibly other output)
                    continue

        has_warnings = len(warnings) > 0

        # Debug output
        if has_warnings:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-optimizer][missing-safety-doc-check] Detected {len(warnings)} missing_safety_doc warnings"
            )
        elif res.returncode != 0:
            # If the return code is non-zero but there are no warnings, it may be a compile error
            PrettyOutput.auto_print(
                f"📊 [c2rust-optimizer][missing-safety-doc-check] Clippy returned a non-zero exit code ({res.returncode}) but no warnings were detected; it may be a compile error"
            )
            if stderr_output:
                PrettyOutput.auto_print(
                    f"📊 [c2rust-optimizer][missing-safety-doc-check] Error output preview (first 200 characters): {stderr_output[:200]}"
                )

        # Return the JSON-format output (for later parsing)
        return has_warnings, stdout_output
    except Exception as e:
        # Assume no warnings when the check fails, to avoid blocking the flow
        PrettyOutput.auto_print(
            f"⚠️ [c2rust-optimizer][missing-safety-doc-check] Exception while checking missing_safety_doc warnings (non-fatal): {e}"
        )
        return False, ""


def cargo_check_full(
    crate_dir: Path,
    stats: OptimizeStats,
    max_checks: int,
    timeout: Optional[int] = None,
) -> Tuple[bool, str]:
    """
    Run cargo test; returns whether it succeeded and the full output (stdout+stderr).
    Counts toward stats.cargo_checks and is limited by the max_checks budget.
    """
    if max_checks and stats.cargo_checks >= max_checks:
        return False, "cargo test budget exhausted"
    try:
        res = subprocess.run(
            ["cargo", "test", "-q"],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(crate_dir),
            timeout=timeout if timeout and timeout > 0 else None,
        )
        stats.cargo_checks += 1
        ok = res.returncode == 0
        out = res.stdout or ""
        err = res.stderr or ""
        msg = (out + ("\n" + err if err else "")).strip()
        return ok, msg
    except subprocess.TimeoutExpired as e:
        stats.cargo_checks += 1
        out_s = e.stdout.decode("utf-8", errors="ignore") if e.stdout else ""
        err_s = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        msg = f"cargo test timed out after {timeout} seconds"
        full_output = (out_s + ("\n" + err_s if err_s else "")).strip()
        if full_output:
            msg += f"\nOutput:\n{full_output}"
        return False, msg
    except Exception as e:
        stats.cargo_checks += 1
        return False, f"cargo test exception: {e}"


def git_toplevel(start: Path) -> Optional[Path]:
    """Return the Git repository root directory that contains start (--show-toplevel). Returns None if not in a repository."""
    try:
        code, out, err = run_cmd(["git", "rev-parse", "--show-toplevel"], start)
        if code == 0:
            p = (out or "").strip()
            if p:
                return Path(p)
        return None
    except Exception:
        return None


def git_head_commit(root: Path) -> Optional[str]:
    """Get the Git HEAD commit hash."""
    try:
        code, out, err = run_cmd(["git", "rev-parse", "--verify", "HEAD"], root)
        if code == 0:
            return out.strip()
        return None
    except Exception:
        return None


def git_reset_hard(root: Path, commit: str) -> bool:
    """Run git reset --hard to the specified commit."""
    try:
        code, _, _ = run_cmd(["git", "reset", "--hard", commit], root)
        if code != 0:
            return False
        return True
    except Exception:
        return False


def iter_rust_files(crate_dir: Path) -> Iterable[Path]:
    """Iterate over all Rust files in the crate directory."""
    src = crate_dir / "src"
    if not src.exists():
        # Still try to traverse the entire crate directory, but prioritize src
        yield from crate_dir.rglob("*.rs")
        return
    # Traverse src first
    yield from src.rglob("*.rs")


def read_file(path: Path) -> str:
    """Read the file content."""
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str) -> None:
    """Write the file content."""
    path.write_text(content, encoding="utf-8")


def backup_file(path: Path) -> Path:
    """Back up the file."""
    bak = path.with_suffix(path.suffix + ".bak_opt")
    shutil.copy2(path, bak)
    return bak


def restore_file_from_backup(path: Path, backup: Path) -> None:
    """Restore the file from the backup."""
    shutil.move(str(backup), str(path))


def remove_backup(backup: Path) -> None:
    """Delete the backup file."""
    if backup.exists():
        backup.unlink(missing_ok=True)


def ensure_report_dir(crate_dir: Path) -> Path:
    """Ensure the report directory exists."""
    report_dir = crate_dir / ".haijunbot" / "c2rust"
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir


def find_project_root() -> Optional[Path]:
    """
    Find the project root directory (the directory containing .haijunbot/c2rust).
    Searches upward from the current directory, up to 5 levels.
    """
    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME

    cwd = Path(".").resolve()
    current = cwd
    for _ in range(5):
        if current and current.exists():
            haijunbot_dir = current / C2RUST_DIRNAME
            if haijunbot_dir.exists() and haijunbot_dir.is_dir():
                return current
            parent = current.parent
            if parent == current:  # Reached the root directory
                break
            current = parent
    return None


def parse_patterns(s: Optional[str]) -> List[str]:
    """Parse a comma-separated pattern string."""
    if not s or not isinstance(s, str):
        return []
    parts = [x.strip() for x in s.replace("\n", ",").split(",")]
    return [x for x in parts if x]


def match_any_pattern(rel: str, patterns: List[str]) -> bool:
    """Check whether the relative path matches any pattern."""
    if not patterns:
        return False
    import fnmatch

    return any(fnmatch.fnmatch(rel, pat) for pat in patterns)


def compute_target_files(
    crate_dir: Path,
    options: OptimizeOptions,
    processed: Set[str],
) -> List[Path]:
    """
    Compute the list of target files (filtered by include/exclude/resume/max_files).

    Args:
        crate_dir: crate root directory
        options: optimization options
        processed: set of already processed files

    Returns:
        list of target files
    """
    include = parse_patterns(options.include_patterns)
    exclude = parse_patterns(options.exclude_patterns)
    maxn = int(options.max_files or 0)
    take: List[Path] = []
    for p in sorted(iter_rust_files(crate_dir), key=lambda x: x.as_posix()):
        try:
            rel = p.resolve().relative_to(crate_dir.resolve()).as_posix()
        except Exception:
            rel = p.as_posix()
        # include filter (if provided, one of them must match)
        if include and not match_any_pattern(rel, include):
            continue
        # exclude filter
        if exclude and match_any_pattern(rel, exclude):
            continue
        # resume: skip already processed files
        if options.resume and rel in processed:
            continue
        take.append(p)
        if maxn > 0 and len(take) >= maxn:
            break
    return take


def detect_crate_dir(preferred: Optional[Path]) -> Path:
    """
    Select the crate directory strategy:
    - If preferred is provided and contains Cargo.toml, use it
    - Otherwise: try to infer from the project root (find the directory containing .haijunbot/c2rust)
    - Otherwise: prefer <cwd>/<cwd.name>_rs; use it if Cargo.toml exists
    - Otherwise: recursively find the first directory containing Cargo.toml under the current directory
    - On failure: if the current directory has Cargo.toml, return the current directory; otherwise raise an error
    """
    if preferred:
        preferred = preferred.resolve()
        if (preferred / "Cargo.toml").exists():
            return preferred

    # Try to infer the crate directory from the project root
    project_root = find_project_root()
    if project_root:
        # Strategy 1: <project_root.name>_rs under the parent of project_root
        candidate1 = project_root.parent / f"{project_root.name}_rs"
        if (candidate1 / "Cargo.toml").exists():
            return candidate1
        # Strategy 2: project_root itself (if it contains Cargo.toml)
        if (project_root / "Cargo.toml").exists():
            return project_root
        # Strategy 3: subdirectories under project_root that contain Cargo.toml
        for d in project_root.iterdir():
            if d.is_dir() and (d / "Cargo.toml").exists():
                return d

    cwd = Path(".").resolve()
    candidate = cwd / f"{cwd.name}_rs"
    if (candidate / "Cargo.toml").exists():
        return candidate

    # Search for the first directory containing Cargo.toml (limit depth to 2 to avoid being too slow)
    for p in [cwd] + [d for d in cwd.iterdir() if d.is_dir()]:
        if (p / "Cargo.toml").exists():
            return p

    if (cwd / "Cargo.toml").exists():
        return cwd
    raise FileNotFoundError("Cargo.toml not found; the corresponding crate directory cannot be determined.")
