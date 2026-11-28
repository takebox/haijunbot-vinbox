#!/usr/bin/env python3
"""Scan Git staging area to intercept commits with suspected real credentials.

Design principles:
- Only check "added lines" from this staging (diff + lines), not the entire repo history, ensuring speed.
- Exit code 1 on hitting real credential patterns, aborting the commit, and printing file/line number/redacted snippet.
- Detection rules share the same module as pre-share scanning (haijunbot_agent.share_secret_scanner),
  avoiding rule drift between the two; allowlist filters test samples/placeholders to reduce false positives.
- Never print full credentials: always redact (keeping a few characters at start and end).

Usage: Called by .githooks/pre-commit, no manual execution needed.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Reuse shared detection rule module.
# This script is called directly by pre-commit as `python3 .githooks/scan_staged_secrets.py`,
# so sys.path may not include src/ at runtime. Locate repo root by __file__ and inject src here.
# On import failure, exit with error message (never silently pass).
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

try:
    from haijunbot.haijunbot_agent.share_secret_scanner import (
        SECRET_PATTERNS,
        SKIP_SUFFIXES,
        is_whitelisted,
        mask,
    )
except Exception as _import_err:  # pragma: no cover - environment error fallback
    print(
        f"[scan-secrets] Cannot load shared scan rule module: {_import_err}",
        file=sys.stderr,
    )
    print(
        "[scan-secrets] Please verify the repo src/ directory is complete, or check the Python environment.",
        file=sys.stderr,
    )
    sys.exit(1)


def _staged_diff() -> str:
    """Get diff of staged area relative to HEAD (including added lines)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--no-color", "--no-ext-diff"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        print(f"[scan-secrets] git diff failed: {result.stderr}", file=sys.stderr)
        return ""
    return result.stdout


def scan() -> int:
    diff = _staged_diff()
    if not diff:
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
            # Parse hunk header @@ -a,b +c,d @@, get starting line number of added side
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
                snippet = m.group(0)
                findings.append(
                    f"  {current_file}:{line_no}  [{name}]  {mask(snippet)}"
                )

    if not findings:
        return 0

    print("", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    print("❌ Commit intercepted: suspected real credentials found in staged area", file=sys.stderr)
    print("=" * 72, file=sys.stderr)
    for f in findings:
        print(f, file=sys.stderr)
    print("", file=sys.stderr)
    print("How to resolve:", file=sys.stderr)
    print(
        "  1. If real credentials → Remove from code, use environment variables/config files (do not commit)",
        file=sys.stderr,
    )
    print(
        "  2. If test samples/placeholders → Add to share_secret_scanner.py allowlist",
        file=sys.stderr,
    )
    print(
        "  3. If commit is truly needed (e.g., security test data) → HAIJUNBOT_ALLOW_SECRETS=1 git commit ...",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(scan())
