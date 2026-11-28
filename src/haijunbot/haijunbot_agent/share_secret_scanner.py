# -*- coding: utf-8 -*-
"""Sensitive credential scanner (shared module).

This module is the single source of truth for "credential detection rules", reused by the following two places to avoid rule drift:
- Git pre-commit hook: .githooks/scan_staged_secrets.py (scans newly added lines in the staging area)
- Pre-share gate: commit_and_push in haijunbot_agent/share_manager.py (scans files to be shared)

Design principles:
- Keep only "high-confidence, low-false-positive" real credential forms.
- Known test samples/placeholders go through a whitelist to avoid false positives.
- Never output complete credentials: always mask them (keep a few leading and trailing characters).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Iterable
from typing import List
from typing import Tuple

# ---------------------------------------------------------------------------
# Detection rules: (name, regex)
# Keep only "high-confidence, low-false-positive" real credential forms.
# ---------------------------------------------------------------------------
SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    # OpenAI / OpenAI-like sk- keys (real lengths are far longer than examples)
    ("OpenAI/generic sk- key", re.compile(r"\bsk-[A-Za-z0-9_-]{32,}\b")),
    # GitHub token
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    # AWS Access Key (a real AKIA is followed by 16 uppercase alphanumerics; official examples excluded)
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    # Slack token
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    # Google API key
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    # Private key block
    (
        "Private key file content",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
    ),
    # Generic "assignment-type" secret: key/secret/token/password = a long random string
    # Note: the prefix boundary uses (?<![A-Za-z0-9]) rather than \b—the underscore belongs to \w, so if \b is used,
    # common names like db_password / DB_PASSWORD / my_api_key would be missed because there is "no word boundary between _ and p".
    (
        "Suspected hardcoded key/password",
        re.compile(
            r"""(?ix)
            (?<![A-Za-z0-9])
            (?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|
               private[_-]?key|client[_-]?secret|passwd|password)
            \b
            \s*[:=]\s*
            ["']([A-Za-z0-9_\-/+=]{20,})["']
            """
        ),
    ),
]

# ---------------------------------------------------------------------------
# Whitelist: fragments that are clearly test samples/placeholders; if matched, the line is ignored.
# Each entry is a regex; a match is considered safe.
# ---------------------------------------------------------------------------
WHITELIST_PATTERNS: List[re.Pattern] = [
    re.compile(r"AKIAIOSFODNN7EXAMPLE"),  # AWS official documentation example
    re.compile(r"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"),  # AWS example secret
    re.compile(r"sk-1234567890abcdef"),  # Obviously fake value
    re.compile(r"sk-xxx+", re.IGNORECASE),
    re.compile(r"your[-_]?(?:secret|api|token|key)", re.IGNORECASE),
    re.compile(r"placeholder", re.IGNORECASE),
    re.compile(r"example[-_]?(?:key|token|secret)", re.IGNORECASE),
    re.compile(r"<[^>]*(?:key|token|secret|password)[^>]*>", re.IGNORECASE),
    re.compile(r"\$\{[^}]*(?:KEY|TOKEN|SECRET|PASSWORD)[^}]*\}"),  # ${ENV_VAR}
    re.compile(r"os\.environ|getenv|process\.env|System\.getenv"),  # Read from environment variables
    re.compile(
        r"-for-unit-tests"
    ),  # Unit test placeholder token (such as test-token-for-unit-tests)
]

# Binary/resource file suffixes are skipped directly, to avoid false positives and wasted performance
SKIP_SUFFIXES = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".jar",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp4",
    ".mp3",
    ".wasm",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".db",
)


@dataclass
class Finding:
    """A single match record (whose snippet has been masked)."""

    file: str
    line_no: int
    rule_name: str
    masked_snippet: str


def mask(value: str) -> str:
    """Mask: keep only a few leading and trailing characters; never output the complete credential."""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}(len={len(value)})"


def is_whitelisted(line: str) -> bool:
    """Determine whether the entire line matches the whitelist (test samples/placeholders)."""
    return any(p.search(line) for p in WHITELIST_PATTERNS)


def scan_text(text: str, file_label: str) -> List[Finding]:
    """Scan text line by line and return all match records.

    Args:
        text: The text content to be scanned.
        file_label: The file identifier shown in the report (a path or placeholder name).
    """
    findings: List[Finding] = []
    for idx, line in enumerate(text.splitlines(), 1):
        if is_whitelisted(line):
            continue
        for name, pattern in SECRET_PATTERNS:
            m = pattern.search(line)
            if m:
                findings.append(
                    Finding(
                        file=file_label,
                        line_no=idx,
                        rule_name=name,
                        masked_snippet=mask(m.group(0)),
                    )
                )
    return findings


def _should_skip(path: str) -> bool:
    """Determine by suffix whether to skip (binary/resource files)."""
    return path.lower().endswith(SKIP_SUFFIXES)


def scan_files(paths: Iterable[str]) -> List[Finding]:
    """Scan the given list of files and return all match records.

    Files that do not exist, are unreadable, fail to read, or have a binary suffix are silently skipped; never raise.
    """
    findings: List[Finding] = []
    for path in paths:
        if _should_skip(path):
            continue
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        findings.extend(scan_text(text, path))
    return findings


def format_findings(findings: List[Finding]) -> str:
    """Format the match records into masked report text (one per line)."""
    return "\n".join(
        f"  {f.file}:{f.line_no}  [{f.rule_name}]  {f.masked_snippet}" for f in findings
    )
