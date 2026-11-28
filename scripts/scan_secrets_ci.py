#!/usr/bin/env python3
"""CI credential scanner: scans the added lines of changed files within a given git range.

Shares the same rule set as the local pre-commit hook .githooks/scan_staged_secrets.py
(haijunbot_agent.share_secret_scanner) to avoid rule drift:
- The local hook scans the "staging area";
- This script scans "any git range" (PR / push / full history), invoked by GitHub Actions.

Usage:
    python3 scripts/scan_secrets_ci.py <git-range>

    <git-range> is like "origin/main..HEAD", "<sha1>..<sha2>", or "HEAD" (single commit).
    When no range is given, HEAD's single commit is scanned by default.

Exit codes: 0=not found; 1=suspected credentials found (CI fails accordingly).
Never print full credentials: always masked.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys

# Reuse the shared rule module (same source as the local hook).
#
# Note: load directly by "file path" here, rather than `import haijunbot.haijunbot_agent...`.
# Reason: share_secret_scanner.py itself only uses the standard library, but once package import is used, Python first
# executes the parent package haijunbot/haijunbot_agent/__init__.py, which transitively imports many modules (including yaml
# and other third-party dependencies). In CI only this scan script needs to run, without installing the whole project's
# dependencies, so we bypass package initialization and load this single file directly, keeping "zero third-party dependencies".
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCANNER_PATH = os.path.join(
    _REPO_ROOT, "src", "haijunbot", "haijunbot_agent", "share_secret_scanner.py"
)

try:
    _spec = importlib.util.spec_from_file_location(
        "share_secret_scanner_standalone", _SCANNER_PATH
    )
    if _spec is None or _spec.loader is None:
        raise ImportError(f"Failed to load from path: {_SCANNER_PATH}")
    _scanner = importlib.util.module_from_spec(_spec)
    # Must register in sys.modules first: the in-module @dataclass relies on cls.__module__ being resolvable.
    sys.modules[_spec.name] = _scanner
    _spec.loader.exec_module(_scanner)

    SECRET_PATTERNS = _scanner.SECRET_PATTERNS
    SKIP_SUFFIXES = _scanner.SKIP_SUFFIXES
    is_whitelisted = _scanner.is_whitelisted
    mask = _scanner.mask
except Exception as _import_err:  # pragma: no cover - fallback for environment anomalies
    print(f"[scan-secrets-ci] Failed to load shared scan rule module: {_import_err}", file=sys.stderr)
    sys.exit(2)


def _diff(git_range: str) -> str:
    """Get the added-lines diff for the given range."""
    cmd = [
        "git",
        "diff",
        "--unified=0",
        "--no-color",
        "--no-ext-diff",
        git_range,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if result.returncode != 0:
        print(
            f"[scan-secrets-ci] git diff failed (range={git_range}): {result.stderr}",
            file=sys.stderr,
        )
        return ""
    return result.stdout


def scan(git_range: str) -> int:
    diff = _diff(git_range)
    if not diff:
        print(f"[scan-secrets-ci] Range {git_range} has no changes, skipping.")
        return 0

    findings: list[str] = []
    current_file = ""
    current_line_no = 0

    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[len("+++ b/") :]
            continue
        if raw.startswith("+++ "):
            current_file = raw[6:]
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            current_line_no = int(m.group(1)) if m else 0
            continue
        if not raw.startswith("+"):
            continue
        if current_file.lower().endswith(SKIP_SUFFIXES):
            continue

        line = raw[1:]
        line_no = current_line_no
        current_line_no += 1

        if is_whitelisted(line):
            continue

        for name, pattern in SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                findings.append(
                    f"  {current_file}:{line_no}  [{name}]  {mask(m.group(0))}"
                )

    if not findings:
        print(f"[scan-secrets-ci] No suspected credentials found in range {git_range}.")
        return 0

    print("", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print("❌ Credential scan failed: suspected real credentials found in changes", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    for f in findings:
        print(f, file=sys.stderr)
    print("", file=sys.stderr)
    print("How to handle:", file=sys.stderr)
    print(
        "  1. If confirmed a real credential → remove from the code and use environment variables/config files (do not commit)",
        file=sys.stderr,
    )
    print(
        "  2. If confirmed a test sample/placeholder → add to the share_secret_scanner.py whitelist",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    rng = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    sys.exit(scan(rng))
