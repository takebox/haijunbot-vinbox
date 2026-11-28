# -*- coding: utf-8 -*-
"""
HaijunBot Security Analysis Suite - Rust Heuristic Security Checker

Purpose and Scope:
- Focus on basic security issues such as unsafe usage, raw pointers, error handling, concurrency, and FFI.
- Provides explainable heuristic detection and confidence assessment for .rs source files.

Output Conventions:
- Returns a list of haijunbot.haijunbot_sec.workflow.Issue (structured format for aggregation scoring and report generation).
- Confidence range [0,1]; severity is high/medium/low.

Usage:
- from haijunbot.haijunbot_sec.checkers.rust_checker import analyze_rust_files
- issues = analyze_rust_files("./repo", ["src/lib.rs", "src/foo.rs"])
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
from pathlib import Path
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple
from typing import TYPE_CHECKING

from haijunbot.haijunbot_sec.types import Issue

if TYPE_CHECKING:
    from haijunbot.haijunbot_sec.project_database import ProjectDatabase

# Taint analysis framework (core dependency)
import haijunbot.haijunbot_sec.taint_analyzer as taint_analyzer

# Data flow analyzer (for false positive filtering)
from haijunbot.haijunbot_sec.data_flow_analyzer import (
    DataFlowAnalyzer,
    DataFlowResult,
)

# ---------------------------
# Rule Library (Regular Expressions)
# ---------------------------

RE_UNSAFE = re.compile(r"\bunsafe\b")
RE_RAW_PTR = re.compile(r"\*(?:mut|const)\s+[A-Za-z_]\w*")  # raw pointer at type position
RE_FORGET = re.compile(r"\bmem::forget\b")
RE_TRANSMUTE = re.compile(r"\bmem::transmute\b")
RE_MAYBE_UNINIT = re.compile(r"\bMaybeUninit\b")
RE_ASSUME_INIT = re.compile(r"\bassume_init\s*\(")

RE_UNWRAP = re.compile(r"\bunwrap\s*\(", re.IGNORECASE)
RE_EXPECT = re.compile(r"\bexpect\s*\(", re.IGNORECASE)
RE_EXTERN_C = re.compile(r'extern\s+"C"')
RE_UNSAFE_IMPL = re.compile(
    r"\bunsafe\s+impl\s+(?:Send|Sync)\b|\bimpl\s+unsafe\s+(?:Send|Sync)\b",
    re.IGNORECASE,
)

# result ignore/underscore binding (may ignore errors)
RE_LET_UNDERSCORE = re.compile(r"\blet\s+_+\s*=\s*.+;")
RE_MATCH_IGNORE_ERR = re.compile(
    r"\.ok\s*\(\s*\)|\.ok\?\s*;|\._?\s*=\s*.+\.err\(\s*\)", re.IGNORECASE
)  # rough

# type conversion related
RE_AS_CAST = re.compile(r"\b\w+\s+as\s+[A-Za-z_]\w*", re.IGNORECASE)
RE_FROM_RAW_PARTS = re.compile(r"\bfrom_raw_parts\s*\(")
RE_FROM_RAW = re.compile(r"\bfrom_raw\s*\(")
RE_INTO_RAW = re.compile(r"\binto_raw\s*\(")

# memory operations related
RE_GET_UNCHECKED = re.compile(r"\.get_unchecked\s*\(")
RE_GET_UNCHECKED_MUT = re.compile(r"\.get_unchecked_mut\s*\(")
RE_OFFSET = re.compile(r"\.offset\s*\(")
RE_ADD = re.compile(r"\.add\s*\(")
RE_COPY_NONOVERLAPPING = re.compile(r"\bcopy_nonoverlapping\s*\(")
RE_COPY = re.compile(r"\bcopy\s*\(")
RE_WRITE = re.compile(r"\bwrite\s*\(")
RE_READ = re.compile(r"\bread\s*\(")
RE_MANUALLY_DROP = re.compile(r"\bManuallyDrop\b")

# concurrency related
RE_ARC = re.compile(r"\bArc\s*<", re.IGNORECASE)
RE_MUTEX = re.compile(r"\bMutex\s*<", re.IGNORECASE)
RE_RWLOCK = re.compile(r"\bRwLock\s*<", re.IGNORECASE)
RE_REFCELL = re.compile(r"\bRefCell\s*<", re.IGNORECASE)
RE_CELL = re.compile(r"\bCell\s*<", re.IGNORECASE)

# error handling related
RE_PANIC = re.compile(r"\bpanic!\s*\(")
RE_UNREACHABLE = re.compile(r"\bunreachable!\s*\(")

# FFI related
RE_CSTRING = re.compile(r"\bCString\b")
RE_CSTR = re.compile(r"\bCStr\b")
RE_FFI_PTR_DEREF = re.compile(r"\*[A-Za-z_]\w*\s*[\[\.]")  # raw pointer dereference

# lifetime related
RE_LIFETIME_PARAM = re.compile(r"<['][a-z]\w*>")  # lifetime parameter
RE_STATIC_LIFETIME = re.compile(r"&'static\s+")

# other unsafe patterns
RE_UNINIT = re.compile(r"\buninit\s*\(")
RE_ZEROED = re.compile(r"\bzeroed\s*\(")


# ---------------------------
# Common Utilities
# ---------------------------


def _safe_line(lines: Sequence[str], idx: int) -> str:
    if 1 <= idx <= len(lines):
        return lines[idx - 1]
    return ""


def _strip_line(s: str, max_len: int = 200) -> str:
    s = s.strip().replace("\t", " ")
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _window(
    lines: Sequence[str], center: int, before: int = 3, after: int = 3
) -> List[Tuple[int, str]]:
    start = max(1, center - before)
    end = min(len(lines), center + after)
    return [(i, _safe_line(lines, i)) for i in range(start, end + 1)]


def _remove_comments_preserve_strings(text: str) -> str:
    """
    Remove comments from Rust source code (//, ///, //!, /* */, /** */, /*! */), preserving string and character literal content;
    To maintain stable line numbers and window positioning, comment content is replaced with spaces and newlines preserved.
    Note: This is a heuristic implementation to reduce false positives from API matches in comments.
    """
    res: list[str] = []
    i = 0
    n = len(text)
    in_sl_comment = False  # //
    in_bl_comment = False  # /* */
    in_string = False  # "
    in_char = False  # '
    in_raw_string = False  # r"..." or r#"..."#
    raw_string_hash_count = 0  # number of # in raw string
    escape = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        nxt2 = text[i + 2] if i + 2 < n else ""

        if in_sl_comment:
            # single-line comment ends at newline
            if ch == "\n":
                in_sl_comment = False
                res.append(ch)
            else:
                # use spaces as placeholder to preserve column count
                res.append(" ")
            i += 1
            continue

        if in_bl_comment:
            # multi-line comment until */
            if ch == "*" and nxt == "/":
                in_bl_comment = False
                res.append(" ")
                res.append(" ")
                i += 2
            else:
                # keep newlines in comment body, replace the rest with spaces
                res.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        # handle raw strings (r"..." or r#"..."#)
        if in_raw_string:
            if ch == '"':
                # check whether there are enough # to end the raw string
                hash_count = 0
                j = i - 1
                while j >= 0 and text[j] == "#":
                    hash_count += 1
                    j -= 1
                if hash_count == raw_string_hash_count:
                    in_raw_string = False
                    raw_string_hash_count = 0
                    res.append(ch)
                    i += 1
                else:
                    res.append(ch)
                    i += 1
            else:
                res.append(ch)
                i += 1
            continue

        # in non-comment state, handle strings and char literals
        if in_string:
            res.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            res.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        # enter comment detection (must not be inside a string/char literal)
        # single-line comment: //, ///, //!
        if ch == "/" and nxt == "/":
            in_sl_comment = True
            res.append(" ")
            res.append(" ")
            i += 2
            continue
        # multi-line comment: /*, /**, /*!
        if ch == "/" and nxt == "*":
            in_bl_comment = True
            res.append(" ")
            res.append(" ")
            i += 2
            continue

        # enter raw string: r"..." or r#"..."# or br"..." or b"..." (byte string)
        # check whether it is r" or br"
        if ch == "r" and nxt == '"':
            # simple raw string: r"
            in_raw_string = True
            raw_string_hash_count = 0
            res.append(ch)
            res.append(nxt)
            i += 2
            continue
        if ch == "b" and nxt == "r" and nxt2 == '"':
            # byte raw string: br"
            in_raw_string = True
            raw_string_hash_count = 0
            res.append(ch)
            res.append(nxt)
            res.append(nxt2)
            i += 3
            continue
        if ch == "r" and nxt == "#":
            # raw string with #: r#"
            # count the number of #
            raw_string_hash_count = 1
            j = i + 1
            while j < n and text[j] == "#":
                raw_string_hash_count += 1
                j += 1
            if j < n and text[j] == '"':
                in_raw_string = True
                # output r and all # and "
                for k in range(i, j + 1):
                    res.append(text[k])
                i = j + 1
                continue
        if ch == "b" and nxt == "r" and nxt2 == "#":
            # byte raw string: br#"
            raw_string_hash_count = 1
            j = i + 2
            while j < n and text[j] == "#":
                raw_string_hash_count += 1
                j += 1
            if j < n and text[j] == '"':
                in_raw_string = True
                # output br and all # and "
                res.append(ch)
                res.append(nxt)
                for k in range(i + 2, j + 1):
                    res.append(text[k])
                i = j + 1
                continue

        # enter string/char literal
        # handle b"..." (byte string, not a raw string; must come after raw string detection)
        if ch == "b" and nxt == '"' and nxt2 != "r":
            in_string = True
            res.append(ch)
            res.append(nxt)
            i += 2
            continue
        if ch == '"':
            in_string = True
            res.append(ch)
            i += 1
            continue
        if ch == "'":
            in_char = True
            res.append(ch)
            i += 1
            continue

        # normal characters
        res.append(ch)
        i += 1

    return "".join(res)


def _mask_strings_preserve_len(text: str) -> str:
    """
    Replace the contents inside string and char literals with spaces, keeping quotes and newlines, and preserving length and line numbers.
    Used to avoid mistaking fragments inside strings (such as "unsafe(") as code when scanning generic API patterns.
    Note: this function does not remove comments; call it on text with comments already removed.
    """
    res: list[str] = []
    in_string = False
    in_char = False
    in_raw_string = False
    raw_string_hash_count = 0
    escape = False

    i = 0
    n = len(text)

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        nxt2 = text[i + 2] if i + 2 < n else ""

        if in_raw_string:
            if ch == '"':
                # check whether there are enough # to end the raw string
                hash_count = 0
                j = i - 1
                while j >= 0 and text[j] == "#":
                    hash_count += 1
                    j -= 1
                if hash_count == raw_string_hash_count:
                    in_raw_string = False
                    raw_string_hash_count = 0
                    res.append('"')
                    i += 1
                elif ch == "\n":
                    res.append("\n")
                    i += 1
                else:
                    res.append(" ")
                    i += 1
            else:
                if ch == "\n":
                    res.append("\n")
                else:
                    res.append(" ")
                i += 1
            continue

        if in_string:
            if escape:
                # keep an escaped backslash as two characters (backslash + space) so as not to break column alignment too much
                res.append(" ")
                escape = False
            elif ch == "\\":
                res.append("\\")
                escape = True
            elif ch == '"':
                res.append('"')
                in_string = False
            elif ch == "\n":
                res.append("\n")
            else:
                res.append(" ")
            i += 1
            continue

        if in_char:
            if escape:
                res.append(" ")
                escape = False
            elif ch == "\\":
                res.append("\\")
                escape = True
            elif ch == "'":
                res.append("'")
                in_char = False
            elif ch == "\n":
                res.append("\n")
            else:
                res.append(" ")
            i += 1
            continue

        # detect the start of a raw string: r"..." or r#"..."# or br"..." or b"..." (byte string)
        if ch == "r" and nxt == '"':
            # simple raw string: r"
            in_raw_string = True
            raw_string_hash_count = 0
            res.append(ch)
            res.append(nxt)
            i += 2
            continue
        if ch == "b" and nxt == "r" and nxt2 == '"':
            # byte raw string: br"
            in_raw_string = True
            raw_string_hash_count = 0
            res.append(ch)
            res.append(nxt)
            res.append(nxt2)
            i += 3
            continue
        if ch == "r" and nxt == "#":
            # raw string with #: r#"
            raw_string_hash_count = 1
            j = i + 1
            while j < n and text[j] == "#":
                raw_string_hash_count += 1
                j += 1
            if j < n and text[j] == '"':
                in_raw_string = True
                # output r and all # and "
                for k in range(i, j + 1):
                    res.append(text[k])
                i = j + 1
                continue
        if ch == "b" and nxt == "r" and nxt2 == "#":
            # byte raw string: br#"
            raw_string_hash_count = 1
            j = i + 2
            while j < n and text[j] == "#":
                raw_string_hash_count += 1
                j += 1
            if j < n and text[j] == '"':
                in_raw_string = True
                # output br and all # and "
                res.append(ch)
                res.append(nxt)
                for k in range(i + 2, j + 1):
                    res.append(text[k])
                i = j + 1
                continue

        # handle b"..." (byte string, not a raw string; must come after raw string detection)
        if ch == "b" and nxt == '"' and nxt2 != "r":
            in_string = True
            res.append(ch)
            res.append(nxt)
            i += 2
            continue
        if ch == '"':
            in_string = True
            res.append('"')
            i += 1
            continue
        if ch == "'":
            in_char = True
            res.append("'")
            i += 1
            continue

        res.append(ch)
        i += 1

    return "".join(res)


def _has_safety_comment_around(
    lines: Sequence[str], line_no: int, radius: int = 5
) -> bool:
    """
    Rust convention: write SAFETY: comment near unsafe to explain preconditions.
    If present, reduce confidence appropriately.
    """
    for _, s in _window(lines, line_no, before=radius, after=radius):
        # support English and Chinese "SAFETY/safety" annotations, compatible with full-width colon
        if (
            "SAFETY:" in s
            or "Safety:" in s
            or "safety:" in s
            or "SAFETY：" in s  # full-width colon
            or "safety" in s
            or "safety:" in s
            or "safety：" in s
        ):
            return True
    return False


def _in_test_context(lines: Sequence[str], line_no: int, radius: int = 20) -> bool:
    """
    If #[test] or mod tests etc. appears nearby, likely test context; reduce severity moderately.
    """
    for _, s in _window(lines, line_no, before=radius, after=radius):
        if "#[test]" in s or "cfg(test)" in s or re.search(r"\bmod\s+tests\b", s):
            return True
    return False


def _severity_from_confidence(conf: float) -> str:
    if conf >= 0.8:
        return "high"
    if conf >= 0.6:
        return "medium"
    return "low"


# ---------------------------
# rule implementations
# ---------------------------


def _rule_unsafe(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe block usage.
    - Prefer database query for symbols table to get unsafe_block symbols
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        symbols = database.get_symbols_by_file(relpath)
        for symbol in symbols:
            if symbol.get("kind") != "unsafe_block":
                continue
            # unsafe impl Send/Sync is handled specifically by _rule_unsafe_impl, skipped here
            if "__unsafe_impl__" in symbol.get("name", ""):
                continue

            line_start = symbol.get("line_start", 0)
            if line_start <= 0 or line_start > len(lines):
                continue

            s = lines[line_start - 1]
            # SAFETY comment: filter directly, do not report
            if _has_safety_comment_around(lines, line_start, radius=5):
                continue
            conf = 0.8
            if _in_test_context(lines, line_start):
                conf -= 0.05
            conf = max(0.5, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="unsafe",
                    file=relpath,
                    line=line_start,
                    evidence=_strip_line(s),
                    description="Unsafe code block/identifier present; memory/aliasing/lifetime safety must be proven.",
                    suggestion="Wrap unsafe operations in the smallest possible scope, and provide a SAFETY comment describing preconditions and invariants.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_unsafe"
        )
        pass

    return issues


def _rule_raw_pointer(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect raw pointer (*mut/*const) usage.
    - Prefer database query for pointer_states to get RAW_POINTER state pointers
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        pointer_states = database.get_pointer_states_by_file(relpath)
        for state in pointer_states:
            if state.get("state") != "RAW_POINTER":
                continue

            line = state.get("line", 0)
            if line <= 0 or line > len(lines):
                continue

            var_name = state.get("var_name", "")
            s = lines[line - 1]
            # SAFETY comment: filter directly, do not report
            if _has_safety_comment_around(lines, line, radius=5):
                continue
            conf = 0.75
            if _in_test_context(lines, line):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="raw_pointer",
                    file=relpath,
                    line=line,
                    evidence=_strip_line(s),
                    description=f"Raw pointer {var_name} (*mut/*const) appears; it may bypass borrow/lifetime checks and risks undefined behavior.",
                    suggestion="Prefer references/smart pointers; when raw pointers must be used, rigorously prove no aliasing, alignment, and lifetime safety.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_raw_pointer"
        )
        pass

    return issues


def _rule_transmute(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect mem::transmute calls.
    - Prefer database query for call_graph to get transmute calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name not in [
                "transmute",
                "mem::transmute",
                "std::mem::transmute",
            ]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.85
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="mem::transmute",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using mem::transmute for type conversion; if layout/alignment/lifetime is not strictly guaranteed, it will cause undefined behavior.",
                    suggestion="Avoid transmute; prefer safe conversions or audited abstractions such as bytemuck; if it must be used, rigorously document invariants.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_transmute"
        )
        pass

    return issues


def _rule_maybe_uninit(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect MaybeUninit/assume_init usage.
    - Prefer using database to query the call_graph table to obtain related calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        maybe_uninit_calls = []
        assume_init_calls = []

        for call in call_graph:
            callee_name = call.get("callee_name", "")
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            if callee_name in ["MaybeUninit", "maybe_uninit", "std::mem::MaybeUninit"]:
                maybe_uninit_calls.append(call)
            elif callee_name in ["assume_init", "maybe_uninit_assume_init"]:
                assume_init_calls.append(call)

        # Handle MaybeUninit calls
        for call in maybe_uninit_calls:
            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.7
            # Check if assume_init is nearby
            for assume_call in assume_init_calls:
                assume_line = assume_call.get("caller_line", 0)
                if abs(assume_line - idx) <= 3:
                    conf += 0.1
                    break
            if _has_safety_comment_around(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="MaybeUninit/assume_init",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using MaybeUninit/assume_init requires ensuring correct initialization and read order, otherwise it may cause undefined behavior.",
                    suggestion="Ensure no reads before initialization; use safer constructors; describe preconditions in a SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )

        # Handle assume_init calls
        for call in assume_init_calls:
            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            # Avoid duplicate reports (if already reported near MaybeUninit)
            already_reported = False
            for issue in issues:
                if abs(issue.line - idx) <= 3:
                    already_reported = True
                    break
            if already_reported:
                continue

            s = lines[idx - 1]
            conf = 0.7
            if _has_safety_comment_around(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="MaybeUninit/assume_init",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using assume_init requires ensuring correct initialization, otherwise it may cause undefined behavior.",
                    suggestion="Ensure no reads before initialization; use safer constructors; describe preconditions in a SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_maybe_uninit"
        )
        pass

    return issues


def _rule_unwrap_expect(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unwrap/expect calls.
    - Prefer using database to query the call_graph table to obtain unwrap/expect calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # Match unwrap and expect method calls
            if callee_name not in ["unwrap", "expect"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.65
            if _in_test_context(lines, idx):
                conf -= 0.1
            conf = max(0.45, min(0.8, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="error_handling",
                    pattern="unwrap/expect",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Direct unwrap/expect may panic on error; missing robust error handling path.",
                    suggestion="Use ? to propagate errors or match to handle explicitly; provide error context and recovery strategy for critical paths.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_unwrap_expect"
        )
        pass

    return issues


def _rule_extern_c(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect extern "C" declarations.
    - Prefer using database to query the symbols table to obtain extern blocks
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        symbols = database.get_symbols_by_file(relpath)
        for symbol in symbols:
            # detect extern blocks (kind='extern_block' or name contains 'extern')
            kind = symbol.get("kind", "")
            name = symbol.get("name", "")
            if kind != "extern_block" and "extern" not in name.lower():
                continue

            line_start = symbol.get("line_start", 0)
            if line_start <= 0 or line_start > len(lines):
                continue

            s = lines[line_start - 1]
            conf = 0.7
            if _has_safety_comment_around(lines, line_start):
                conf -= 0.05
            conf = max(0.5, min(0.85, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="ffi",
                    pattern='extern "C"',
                    file=relpath,
                    line=line_start,
                    evidence=_strip_line(s),
                    description="FFI boundary must ensure pointer validity, length/alignment, lifetime, thread safety constraints; otherwise may cause undefined behavior.",
                    suggestion="Perform strict parameter validation and safe encapsulation at FFI boundary; record invariants and constraints in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_extern_c"
        )
        pass

    return issues


def _rule_unsafe_impl(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe impl Send/Sync.
    - Prefer database query for symbols to get unsafe impl definitions
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        symbols = database.get_symbols_by_file(relpath)
        for symbol in symbols:
            # detect unsafe impl Send/Sync
            kind = symbol.get("kind", "")
            name = symbol.get("name", "")
            # DataCollector may store as kind='impl' or kind='unsafe_block' (name contains __unsafe_impl__)
            if kind == "impl":
                # check whether it is an impl of Send or Sync
                if "Send" not in name and "Sync" not in name:
                    continue
                # check whether it is an unsafe impl
                is_unsafe = symbol.get("is_unsafe", False) or "unsafe" in name.lower()
                if not is_unsafe:
                    continue
            elif kind == "unsafe_block" and "__unsafe_impl__" in name:
                # DataCollector stores unsafe impl as unsafe_block with name format __unsafe_impl__TypeName
                # Need to check if it is Send/Sync from source line
                line_start = symbol.get("line_start", 0)
                if line_start <= 0 or line_start > len(lines):
                    continue
                s = lines[line_start - 1]
                if "Send" not in s and "Sync" not in s:
                    continue
            else:
                continue

            line_start = symbol.get("line_start", 0)
            if line_start <= 0 or line_start > len(lines):
                continue

            s = lines[line_start - 1]
            conf = 0.8
            if _has_safety_comment_around(lines, line_start):
                conf -= 0.1
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="concurrency",
                    pattern="unsafe_impl_Send_or_Sync",
                    file=relpath,
                    line=line_start,
                    evidence=_strip_line(s),
                    description="Manually written unsafe impl Send/Sync may violate concurrency memory model guarantees and risk data races.",
                    suggestion="Avoid manual unsafe impl; if necessary, strictly prove thread safety preconditions and minimize unsafe regions.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_unsafe_impl"
        )
        pass

    return issues


def _rule_ignore_result(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect let _ = xxx ignoring results.
    - Prefer database query for data_flow to get let _ binding info
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        # query the data_flow table to obtain let _ bindings
        data_flows = database.get_data_flow_by_file(relpath)
        for flow in data_flows:
            # detect let _ binding pattern (ignored result)
            var_name = flow.get("var_name", "")
            if var_name != "_":
                continue

            line = flow.get("line", 0)
            if line <= 0 or line > len(lines):
                continue

            s = lines[line - 1]
            conf = 0.55
            if _in_test_context(lines, line):
                conf -= 0.1
            conf = max(0.4, min(0.7, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="error_handling",
                    pattern="ignored_result",
                    file=relpath,
                    line=line,
                    evidence=_strip_line(s),
                    description="May ignore returned error result causing unhandled failures.",
                    suggestion="Explicitly handle Result (? propagation or match) ensuring error paths cover resource cleanup and logging.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_ignore_result"
        )
        pass

    return issues


def _rule_forget(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect mem::forget usage; skips Drop causing resource leaks.
    - Prefer database query for call_graph to get mem::forget calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match mem::forget calls
            if callee_name not in ["mem::forget", "forget"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.75
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="resource_management",
                    pattern="mem::forget",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="mem::forget skips Drop causing leaks; misuse may break invariants or cause leaks.",
                    suggestion="Avoid unnecessary mem::forget; if suppressing Drop, prefer ManuallyDrop or design safer ownership transfer.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_forget"
        )
        pass

    return issues


def _rule_get_unchecked(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect get_unchecked/get_unchecked_mut usage (bypasses bounds checks).
    - Prefer using database to query the call_graph table to obtain get_unchecked/get_unchecked_mut calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match get_unchecked/get_unchecked_mut calls
            if callee_name not in ["get_unchecked", "get_unchecked_mut"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.8
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="get_unchecked",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="get_unchecked/get_unchecked_mut bypass bounds checks; invalid index causes undefined behavior.",
                    suggestion="Prefer safe indexing ([] or get); if must use get_unchecked, prove index validity in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_get_unchecked"
        )
        pass

    return issues


def _rule_pointer_arithmetic(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect pointer arithmetic (offset/add) which may produce invalid pointers.
    - Prefer using database to query the call_graph table to obtain offset/add calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match offset/add calls (pointer arithmetic)
            if callee_name not in [
                "offset",
                "add",
                "sub",
                "wrapping_offset",
                "wrapping_add",
                "wrapping_sub",
            ]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.75
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="pointer_arithmetic",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Pointer arithmetic with offset/add; if result exceeds valid range, causes undefined behavior.",
                    suggestion="Ensure pointer arithmetic result is within valid object bounds; prefer safe abstractions like slice over raw pointer arithmetic.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_pointer_arithmetic",
        )
        pass

    return issues


def _rule_unsafe_mem_ops(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe memory operations (copy_nonoverlapping/copy/write/read).
    - Prefer using database to query the call_graph table to obtain unsafe memory operation calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match unsafe memory operations
            unsafe_mem_ops = [
                "copy_nonoverlapping",
                "copy",
                "write",
                "read",
                "write_bytes",
                "read_volatile",
                "write_volatile",
                "read_unaligned",
                "write_unaligned",
            ]
            if callee_name not in unsafe_mem_ops:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.8
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="unsafe_mem_ops",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Unsafe memory ops (copy/copy_nonoverlapping/write/read) require ensuring pointer validity, alignment, overlap checks.",
                    suggestion="Prefer safe copy methods; if must use, prove pointer validity/alignment/bounds in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_unsafe_mem_ops",
        )
        pass

    return issues


def _rule_from_raw_parts(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe constructors like from_raw_parts/from_raw.
    - Prefer using database to query the call_graph table to obtain from_raw_parts/from_raw calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match from_raw_parts/from_raw calls
            if callee_name not in ["from_raw_parts", "from_raw_parts_mut", "from_raw"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.85
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="from_raw_parts/from_raw",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="from_raw_parts/from_raw constructing from raw pointer requires pointer validity, alignment, lifetime safety.",
                    suggestion="Prefer safe constructors; if must use, prove all preconditions (validity/alignment/lifetime) in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_from_raw_parts",
        )
        pass

    return issues


def _rule_manually_drop(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect ManuallyDrop usage requiring manual Drop management.
    - Prefer using database to query the symbols table to obtain ManuallyDrop type usages
    - Prefer using database to query the call_graph table to obtain ManuallyDrop::new/drop calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        # First query call_graph to detect if ManuallyDrop::drop is called (proper cleanup)
        call_graph = database.get_call_graph()
        has_manually_drop_cleanup = False
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name == "ManuallyDrop::drop":
                caller_file = call.get("caller_file", "")
                if os.path.basename(caller_file) == os.path.basename(relpath):
                    has_manually_drop_cleanup = True
                    break

        # query the symbols table to obtain ManuallyDrop type usages
        symbols = database.get_symbols_by_file(relpath)
        for sym in symbols:
            type_name = sym.get("type", "")
            if "ManuallyDrop" not in type_name:
                continue

            idx = sym.get("line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            # If ManuallyDrop::drop called, proper cleanup - skip
            if has_manually_drop_cleanup:
                continue

            s = lines[idx - 1]
            conf = 0.7
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.85, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="resource_management",
                    pattern="ManuallyDrop",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="ManuallyDrop requires manual Drop management; misuse may cause leaks or double frees.",
                    suggestion="Ensure ManuallyDrop-wrapped object is dropped manually at appropriate time; explain lifetime management in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )

        # query the call_graph table to obtain ManuallyDrop::new calls (report only new, not drop)
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # Only match ManuallyDrop::new, not ManuallyDrop::drop
            if callee_name != "ManuallyDrop::new":
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            # If ManuallyDrop::drop called, proper cleanup - skip
            if has_manually_drop_cleanup:
                continue

            # Avoid duplicate reports
            if any(i.line == idx for i in issues):
                continue

            s = lines[idx - 1]
            conf = 0.7
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.85, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="resource_management",
                    pattern="ManuallyDrop",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="ManuallyDrop requires manual Drop management; misuse may cause leaks or double frees.",
                    suggestion="Ensure ManuallyDrop-wrapped object is dropped manually at appropriate time; explain lifetime management in SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_manually_drop"
        )
        pass

    return issues


def _rule_panic_unreachable(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect panic!/unreachable! macro calls.
    - Prefer using database to query the call_graph table to obtain panic!/unreachable! calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # Match panic! and unreachable! macro calls
            if callee_name not in ["panic!", "unreachable!"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.6
            if _in_test_context(lines, idx):
                conf -= 0.15  # panic is more common in tests
            if "assert" in s.lower():
                conf -= 0.1  # panic in assert! macros is usually acceptable
            conf = max(0.4, min(0.75, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="error_handling",
                    pattern="panic/unreachable",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="panic!/unreachable! may crash program; lacks graceful error handling.",
                    suggestion="Prefer Result for error handling; only use panic when truly unrecoverable.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_panic_unreachable",
        )
        pass

    return issues


def _rule_refcell_borrow(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect RefCell borrow/borrow_mut usage.
    - Prefer using database to query the symbols table to obtain RefCell variable definitions
    - Prefer using database to query the call_graph table to obtain borrow/borrow_mut calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        # query the symbols table to obtain RefCell variables
        symbols = database.get_symbols_by_file(relpath)
        refcell_vars: set[str] = set()
        for symbol in symbols:
            # detect RefCell type variables
            type_info = symbol.get("type", "")
            if "RefCell" in type_info:
                var_name = symbol.get("name", "")
                if var_name:
                    refcell_vars.add(var_name)

        # query the call_graph table to obtain borrow/borrow_mut calls
        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match borrow and borrow_mut method calls
            if callee_name not in ["borrow", "borrow_mut"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            # check via the caller_name field whether it is a borrow of a RefCell variable
            # caller_name format may be "var.borrow" or "borrow"
            caller_name = call.get("caller_name", "")
            is_refcell_borrow = False
            for var in refcell_vars:
                # use string matching instead of regular expressions
                if (
                    caller_name == var
                    or f"{var}.borrow" in caller_name
                    or f"{var}.borrow_mut" in caller_name
                ):
                    is_refcell_borrow = True
                    break

            if not is_refcell_borrow:
                continue

            # check whether try_borrow is used (safer)
            if "try_borrow" in s.lower():
                continue

            conf = 0.55
            if _in_test_context(lines, idx):
                conf -= 0.1
            conf = max(0.4, min(0.7, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="error_handling",
                    pattern="RefCell_borrow",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="RefCell using borrow/borrow_mut may panic at runtime (borrow conflict).",
                    suggestion="Consider using try_borrow/try_borrow_mut which return Result, or use Mutex/RwLock for compile-time checking.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_refcell_borrow",
        )
        pass

    return issues


def _rule_ffi_cstring(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect CString/CStr usage in FFI.
    - Prefer using database to query the call_graph table to obtain CString/CStr calls
    - Check via the symbols table whether it is in an FFI context
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        # query the call_graph table to obtain CString/CStr calls
        call_graph = database.get_call_graph()
        # query the symbols table to check the FFI context
        symbols = database.get_symbols_by_file(relpath)
        has_ffi_context = False
        for symbol in symbols:
            kind = symbol.get("kind", "")
            name = symbol.get("name", "")
            if (
                kind == "extern_block"
                or "extern" in name.lower()
                or "ffi" in name.lower()
            ):
                has_ffi_context = True
                break

        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # match CString and CStr calls
            if callee_name not in ["CString", "CStr", "CString::new", "CStr::from_ptr"]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            # check whether it is in an FFI context (via caller_name or nearby symbols)
            caller_name = call.get("caller_name", "")
            in_ffi = (
                has_ffi_context
                or "ffi" in caller_name.lower()
                or "extern" in caller_name.lower()
            )

            if not in_ffi:
                continue

            s = lines[idx - 1]
            conf = 0.65
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            conf = max(0.5, min(0.8, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="ffi",
                    pattern="CString/CStr",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using CString/CStr in FFI requires ensuring correct lifetime management and null byte handling.",
                    suggestion="Ensure the CString lifetime covers the FFI call period; note that CStr must not contain interior null bytes.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_ffi_cstring"
        )
        pass

    return issues


def _rule_integer_overflow(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect integer overflow risk.
    - Detect arithmetic operations directly from source (+ , -, *)
    - Exclude cases where checked_/saturating_ is already used
    - Exclude constant computations (such as 1 + 2)
    """
    issues: List[Issue] = []
    import re

    # match arithmetic operations: variable + variable, variable * variable, variable - variable
    # exclude constant computations (pure numbers) and checked_/saturating_ method calls
    arithmetic_pattern = re.compile(r"\b(\w+)\s*([+\-*])\s*(\w+)\b")

    # exclusion patterns: constant computations, method calls
    constant_pattern = re.compile(r"^\d+$")
    safe_method_pattern = re.compile(
        r"\b(checked_|saturating_|wrapping_|overflowing_)(add|sub|mul)"
    )

    for idx, line in enumerate(lines, 1):
        # skip comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # check whether there is a safe method call
        if safe_method_pattern.search(line):
            continue

        # find arithmetic operations
        for match in arithmetic_pattern.finditer(line):
            left, op, right = match.groups()

            # exclude constant computations
            if constant_pattern.match(left) and constant_pattern.match(right):
                continue

            # exclude pointer arithmetic (a dedicated rule already exists)
            # only exclude pointer arithmetic in method-call form (such as .offset(n), .add(n))
            if ".offset" in line or ".add" in line:
                continue

            conf = 0.6
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.1
            conf = max(0.4, min(0.8, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="integer_overflow",
                    pattern="integer_overflow",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description=f"Integer overflow risk: '{left} {op} {right}' may overflow/wrap in release mode.",
                    suggestion="Use safe methods such as checked_add/saturating_add, or prove in a SAFETY comment that overflow cannot occur.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
            break  # report only once per line

    return issues


def _rule_unsafe_fn(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe fn declarations.
    - Detect unsafe fn declaration patterns directly from source
    - Does not depend on database (DataCollector does not extract the is_unsafe attribute)
    """
    issues: List[Issue] = []
    import re

    # match unsafe fn declarations
    unsafe_fn_pattern = re.compile(r"\bunsafe\s+fn\s+(\w+)")

    for idx, line in enumerate(lines, 1):
        # skip comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        match = unsafe_fn_pattern.search(line)
        if match:
            # skip when a SAFETY comment is present; do not report
            if _has_safety_comment_around(lines, idx):
                continue

            fn_name = match.group(1)
            conf = 0.75
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="unsafe_fn",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description=f"unsafe fn '{fn_name}' declaration requires the caller to guarantee safety; preconditions should be described in a SAFETY comment.",
                    suggestion="Clearly state in a SAFETY comment the safety conditions the caller must satisfy; consider using a safe API instead.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )

    return issues


def _rule_as_cast(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect data truncation that may be caused by as type conversions.
    - Detect as type conversions directly from source
    - Infer variable types from function signatures and let declarations
    - Distinguish widening conversions (safe) from truncating conversions (dangerous)
    - Report only dangerous type conversions
    """
    issues: List[Issue] = []
    import re

    # type size mapping (bit width)
    type_sizes = {
        "u8": 8,
        "i8": 8,
        "u16": 16,
        "i16": 16,
        "u32": 32,
        "i32": 32,
        "u64": 64,
        "i64": 64,
        "u128": 128,
        "i128": 128,
        "usize": 64,
        "isize": 64,  # assume 64-bit system
    }

    # ---- Step 1: build variable type mapping ----
    var_types: dict = {}

    # extract parameter types from function signatures: fn foo(x: u64, y: i32)
    fn_param_pattern = re.compile(r"fn\s+\w+[^)]*\(([^)]*)\)")
    param_type_pattern = re.compile(r"(\w+)\s*:\s*(u\d+|i\d+|usize|isize)")
    for line in lines:
        for fn_match in fn_param_pattern.finditer(line):
            params_str = fn_match.group(1)
            for pm in param_type_pattern.finditer(params_str):
                var_types[pm.group(1)] = pm.group(2)

    # extract variable types from let declarations: let x: u64 = ...
    let_type_pattern = re.compile(r"let\s+(mut\s+)?(\w+)\s*:\s*(u\d+|i\d+|usize|isize)")
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        m = let_type_pattern.search(line)
        if m:
            var_types[m.group(2)] = m.group(3)

    # ---- Step 2: detect as type conversions ----
    cast_pattern = re.compile(r"(\w+)\s+as\s+(u\d+|i\d+|usize|isize)")

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        for match in cast_pattern.finditer(line):
            var_name = match.group(1)
            target_type = match.group(2)

            source_type = var_types.get(var_name, None)
            src_size = type_sizes.get(source_type, 0) if source_type else 0
            tgt_size = type_sizes.get(target_type, 0)

            is_dangerous = False
            desc = ""

            if src_size > 0 and tgt_size > 0 and source_type:
                if src_size > tgt_size:
                    is_dangerous = True
                    desc = f"truncation from {source_type}({src_size}bit) to {target_type}({tgt_size}bit)"
                elif (
                    src_size == tgt_size
                    and source_type.startswith("i")
                    and target_type.startswith("u")
                ):
                    is_dangerous = True
                    desc = f"sign change from {source_type} to {target_type}"
            else:
                # Unknown source type: only report for very small targets
                if target_type in ["u8", "i8"]:
                    is_dangerous = True
                    desc = (
                        f"potential truncation to {target_type} (unknown source type)"
                    )

            if is_dangerous:
                conf = 0.65
                if _has_safety_comment_around(lines, idx):
                    conf -= 0.1
                conf = max(0.45, min(0.85, conf))

                issues.append(
                    Issue(
                        language="rust",
                        category="type_safety",
                        pattern="as_cast_truncation",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(line),
                        description=f"as type conversion may cause data truncation or sign issues ({desc}).",
                        suggestion="Use TryFrom/TryInto for safe conversions; if as must be used, prove in a SAFETY comment that the value range is safe.",
                        confidence=conf,
                        severity=_severity_from_confidence(conf),
                    )
                )
                break

    return issues


def _rule_into_raw(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect whether into_raw calls have a paired from_raw.
    - Prefer using database to query the call_graph table
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()

        # collect all into_raw and from_raw calls
        into_raw_calls = []
        has_from_raw = False

        for call in call_graph:
            callee_name = call.get("callee_name", "")
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            if "into_raw" in callee_name:
                into_raw_calls.append(call)
            elif "from_raw" in callee_name:
                has_from_raw = True

        # if there is no paired from_raw, report all into_raw calls
        if not has_from_raw:
            for call in into_raw_calls:
                idx = call.get("caller_line", 0)
                if idx <= 0 or idx > len(lines):
                    continue

                s = lines[idx - 1]
                conf = 0.7
                if _has_safety_comment_around(lines, idx):
                    conf -= 0.1
                conf = max(0.5, min(0.85, conf))

                issues.append(
                    Issue(
                        language="rust",
                        category="resource_management",
                        pattern="into_raw_leak",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="No paired from_raw after an into_raw call may cause a memory leak.",
                        suggestion="Ensure from_raw is called at the appropriate time to reclaim memory; or use ManuallyDrop to explicitly indicate intentional leakage.",
                        confidence=conf,
                        severity=_severity_from_confidence(conf),
                    )
                )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_into_raw"
        )
        pass

    return issues


def _rule_static_mut(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect static mut global mutable state.
    - Directly detect static mut declaration patterns from source code
    - Does not rely on database (DataCollector does not extract the mut attribute of static)
    """
    issues: List[Issue] = []
    import re

    # Match static mut declarations
    static_mut_pattern = re.compile(r"\bstatic\s+mut\s+(\w+)")

    for idx, line in enumerate(lines, 1):
        # Skip comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        match = static_mut_pattern.search(line)
        if match:
            var_name = match.group(1)
            conf = 0.75
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            conf = max(0.55, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="concurrency",
                    pattern="static_mut",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description=f"static mut '{var_name}' global mutable state may cause data races in a multithreaded environment.",
                    suggestion="Use Mutex/RwLock/Atomic types instead of static mut; or use thread_local.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )

    return issues


def _rule_unchecked_math(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe math operations such as unchecked_add/sub/mul.
    - Prefer using the database to query the call_graph table
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # Match unchecked math operations
            unchecked_ops = [
                "unchecked_add",
                "unchecked_sub",
                "unchecked_mul",
                "unchecked_shl",
                "unchecked_shr",
                "unchecked_div",
                "unchecked_rem",
                "unchecked_neg",
            ]
            if callee_name not in unchecked_ops:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.8
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.6, min(0.95, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="unchecked_math",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Unchecked math operations cause undefined behavior on overflow.",
                    suggestion="Ensure operands do not overflow; prove the value range is safe in a SAFETY comment.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.rust_checker",
            function="_rule_unchecked_math",
        )
        pass

    return issues


def _rule_rc_cycle(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect Rc reference cycle risks.
    - Directly detect Rc<RefCell<...>> types from source code
    - Detect structures that may form reference cycles
    """
    issues: List[Issue] = []

    import re

    # Detect Rc<RefCell<...>> types
    rc_refcell_pattern = re.compile(r"Rc<RefCell<")

    for idx, line in enumerate(lines, 1):
        # Skip comment lines
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect Rc<RefCell<...>> types
        if rc_refcell_pattern.search(line):
            conf = 0.55
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            conf = max(0.4, min(0.75, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="memory_leak",
                    pattern="rc_cycle",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description="Rc<RefCell<...>> may form reference cycles causing memory leaks.",
                    suggestion="Consider using Weak to break the cycle; or use Arc<Mutex> with manual lifetime management.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )

    return issues


def _rule_command_injection(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect command injection risks (simplified taint analysis).
    - Detect user input (stdin, args, env) flowing to Command::new/.arg()
    - Support cross-function taint propagation
    - Simplified implementation based on regex matching, does not rely on database
    """
    issues: List[Issue] = []
    import re

    # Taint source patterns: stdin, args, env
    source_patterns = [
        re.compile(r"io::stdin\(\)|stdin\(\)"),
        re.compile(r"\.lines\(\)"),
        re.compile(r"env::args\(\)|std::env::args"),
        re.compile(r"env::var\(|std::env::var"),
    ]

    # Taint sink patterns: Command::new, .arg()
    sink_pattern = re.compile(r"Command::new|\.arg\(")

    # ---- Step 1: Identify functions that return tainted values ----
    tainted_functions = set()
    fn_pattern = re.compile(r"fn\s+(\w+)\s*[<(]")
    fn_start = -1
    fn_name = None
    fn_body_lines = []

    for idx, line in enumerate(lines, 1):
        # Detect function start
        fn_match = fn_pattern.search(line)
        if fn_match:
            # Save the previous function
            if fn_name and fn_body_lines:
                # Check whether the function body contains a taint source
                fn_body = "\n".join(fn_body_lines)
                for pattern in source_patterns:
                    if pattern.search(fn_body):
                        # Check whether there is a return value (simple heuristic: the function signature has -> or the body has an implicit return)
                        if "->" in lines[fn_start - 1] or any(
                            ln.strip() and not ln.strip().startswith("//")
                            for ln in fn_body_lines[-3:]
                        ):
                            tainted_functions.add(fn_name)
                            break
            # Start a new function
            fn_name = fn_match.group(1)
            fn_start = idx
            fn_body_lines = []
        elif fn_start > 0:
            # Collect the function body (stop when the next fn is encountered)
            if not fn_pattern.search(line):
                fn_body_lines.append(line)
            else:
                # New function starts, process the previous function
                if fn_name and fn_body_lines:
                    fn_body = "\n".join(fn_body_lines)
                    for pattern in source_patterns:
                        if pattern.search(fn_body):
                            if "->" in lines[fn_start - 1] or any(
                                ln.strip() and not ln.strip().startswith("//")
                                for ln in fn_body_lines[-3:]
                            ):
                                tainted_functions.add(fn_name)
                                break
                new_match = fn_pattern.search(line)
                fn_name = new_match.group(1) if new_match else None
                fn_start = idx
                fn_body_lines = []

    # Process the last function
    if fn_name and fn_body_lines:
        fn_body = "\n".join(fn_body_lines)
        for pattern in source_patterns:
            if pattern.search(fn_body):
                if "->" in lines[fn_start - 1] or any(
                    ln.strip() and not ln.strip().startswith("//")
                    for ln in fn_body_lines[-3:]
                ):
                    tainted_functions.add(fn_name)
                    break

    # ---- Step 2: Find taint source variables ----
    tainted_vars = set()
    for idx, line in enumerate(lines, 1):
        # Detect taint source assignments: let user_input = stdin...
        if "let " in line:
            # Direct taint source
            for pattern in source_patterns:
                if pattern.search(line):
                    match = re.search(r"let\s+(mut\s+)?(\w+)", line)
                    if match:
                        tainted_vars.add(match.group(2))

            # Tainted function call: let input = get_user_input()
            for func_name in tainted_functions:
                if func_name + "(" in line or func_name + "::" in line:
                    match = re.search(r"let\s+(mut\s+)?(\w+)", line)
                    if match:
                        tainted_vars.add(match.group(2))

    # ---- Step 3: Track variable assignment propagation ----
    # Multiple rounds of propagation until convergence
    for _ in range(3):  # At most 3 rounds
        new_vars = set()
        for idx, line in enumerate(lines, 1):
            if "let " in line:
                # Check whether a tainted variable was assigned: let other = tainted.clone()
                for var in tainted_vars:
                    if var in line:
                        match = re.search(r"let\s+(mut\s+)?(\w+)", line)
                        if match and match.group(2) != var:
                            new_vars.add(match.group(2))
        if new_vars <= tainted_vars:
            break
        tainted_vars.update(new_vars)

    # If no taint source is found, return directly
    if not tainted_vars:
        return issues

    # ---- Step 4: Find taint sink usages ----
    for idx, line in enumerate(lines, 1):
        if sink_pattern.search(line):
            # Check whether a tainted variable is used
            for var in tainted_vars:
                if f"&{var}" in line or f"{var}" in line:
                    conf = 0.75
                    if _has_safety_comment_around(lines, idx):
                        conf -= 0.1
                    if _in_test_context(lines, idx):
                        conf -= 0.1
                    conf = max(0.5, min(0.9, conf))

                    issues.append(
                        Issue(
                            language="rust",
                            category="taint-analysis",
                            pattern="taint-flow",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description=f"Command injection risk: user input '{var}' is used directly for command execution",
                            suggestion="Sanitize user input with shlex::split or shell_words::split, or use parameterized command execution",
                            confidence=conf,
                            severity="critical",
                        )
                    )
                    break  # Avoid duplicate reports

    return issues


def _rule_toctou_race(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect TOCTOU (Time-of-Check to Time-of-Use) race condition vulnerabilities.
    - Detect the race window between check and use in filesystem operations
    - Typical patterns: exists() followed by read(), is_dir() followed by create(), etc.
    - CWE-362: Race Condition
    """
    issues: List[Issue] = []
    import re

    # TOCTOU check patterns: a check operation followed by a use operation
    # Pattern 1: path.exists() followed by fs::read/write/open
    # Pattern 2: path.is_dir()/is_file() followed by file operations
    # Pattern 3: fs::metadata() followed by file operations

    check_patterns = [
        (re.compile(r"\.exists\(\)"), "exists check"),
        (re.compile(r"\.is_dir\(\)"), "is_dir check"),
        (re.compile(r"\.is_file\(\)"), "is_file check"),
        (re.compile(r"\.metadata\(\)"), "metadata check"),
        (re.compile(r"fs::metadata|path\.metadata"), "metadata check"),
    ]

    use_patterns = [
        re.compile(r"fs::read|fs::write|fs::File::open|fs::File::create"),
        re.compile(r"\.read_to_string|\.read_to_end"),
        re.compile(r"OpenOptions::new"),
    ]

    # Analyze per function, detect the case where the check and use are in the same function but not in the same statement
    fn_pattern = re.compile(r"fn\s+(\w+)\s*[<(]")
    fn_start = -1
    fn_name = None
    fn_body_lines = []
    fn_body_start = 0

    for idx, line in enumerate(lines, 1):
        fn_match = fn_pattern.search(line)
        if fn_match:
            # Analyze the previous function
            if fn_name and len(fn_body_lines) > 0:
                _analyze_toctou_in_function(
                    lines,
                    fn_body_start,
                    fn_body_lines,
                    check_patterns,
                    use_patterns,
                    relpath,
                    issues,
                )
            # Start a new function
            fn_name = fn_match.group(1)
            fn_start = idx
            fn_body_lines = []
            fn_body_start = idx
        elif fn_start > 0:
            if not fn_pattern.search(line):
                fn_body_lines.append((idx, line))
            else:
                # New function starts
                if fn_name and len(fn_body_lines) > 0:
                    _analyze_toctou_in_function(
                        lines,
                        fn_body_start,
                        fn_body_lines,
                        check_patterns,
                        use_patterns,
                        relpath,
                        issues,
                    )
                new_match = fn_pattern.search(line)
                fn_name = new_match.group(1) if new_match else None
                fn_start = idx
                fn_body_lines = []
                fn_body_start = idx

    # Process the last function
    if fn_name and len(fn_body_lines) > 0:
        _analyze_toctou_in_function(
            lines,
            fn_body_start,
            fn_body_lines,
            check_patterns,
            use_patterns,
            relpath,
            issues,
        )

    return issues


def _analyze_toctou_in_function(
    lines: Sequence[str],
    fn_start: int,
    fn_body_lines: List[Tuple[int, str]],
    check_patterns: List,
    use_patterns: List,
    relpath: str,
    issues: List[Issue],
) -> None:
    """Analyze TOCTOU patterns in the function body"""

    # Find the positions of check operations
    check_positions = []
    for line_no, line in fn_body_lines:
        for pattern, check_name in check_patterns:
            if pattern.search(line):
                # Check whether it is in an if condition
                if "if " in line or "if(" in line:
                    check_positions.append((line_no, check_name, line))
                    break

    # If there is no check operation, return directly
    if not check_positions:
        return

    # Find the positions of use operations
    use_positions = []
    for line_no, line in fn_body_lines:
        for pattern in use_patterns:
            if pattern.search(line):
                use_positions.append((line_no, line))
                break

    # Check whether a TOCTOU pattern exists: a check operation followed by a use operation
    for check_line, check_name, check_content in check_positions:
        for use_line, use_content in use_positions:
            # The use operation comes after the check operation (not on the same line)
            if use_line > check_line:
                # Check whether there are safety measures (such as the create_new atomic operation)
                if "create_new" in use_content or "O_EXCL" in use_content:
                    continue

                # Check whether there is a SAFETY comment
                conf = 0.7
                if _has_safety_comment_around(lines, use_line):
                    conf -= 0.15
                if _in_test_context(lines, use_line):
                    conf -= 0.1
                conf = max(0.5, min(0.85, conf))

                issues.append(
                    Issue(
                        language="rust",
                        category="concurrency",
                        pattern="toctou_race",
                        file=relpath,
                        line=use_line,
                        evidence=_strip_line(use_content),
                        description=f"TOCTOU race condition: file operation after {check_name}, a race window exists",
                        suggestion="Use atomic operations (such as create_new) or file descriptors to avoid race conditions",
                        confidence=conf,
                        severity="medium",
                    )
                )
                break  # Report each check operation only once


def _rule_uninit_zeroed(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect the use of uninit/zeroed, the risk of uninitialized memory access.
    - Prefer using the database to query the call_graph table to obtain uninit/zeroed calls
    - Return empty list if no database
    """
    issues: List[Issue] = []

    if database is None:
        return issues

    try:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            # Match uninit/zeroed calls
            if callee_name not in [
                "uninit",
                "zeroed",
                "mem::uninitialized",
                "MaybeUninit::uninit",
                "MaybeUninit::zeroed",
            ]:
                continue

            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue

            idx = call.get("caller_line", 0)
            if idx <= 0 or idx > len(lines):
                continue

            s = lines[idx - 1]
            conf = 0.75
            if _has_safety_comment_around(lines, idx):
                conf -= 0.1
            if _in_test_context(lines, idx):
                conf -= 0.05
            conf = max(0.5, min(0.9, conf))

            issues.append(
                Issue(
                    language="rust",
                    category="unsafe_usage",
                    pattern="uninit/zeroed",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using uninit/zeroed creates uninitialized memory; reading it before initialization causes undefined behavior.",
                    suggestion="Ensure initialization is completed before use; prefer MaybeUninit for safer uninitialized memory management.",
                    confidence=conf,
                    severity=_severity_from_confidence(conf),
                )
            )
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.rust_checker", function="_rule_uninit_zeroed"
        )
        pass

    return issues


# ---------------------------
# Public main entry point
# ---------------------------


def analyze_rust_text(
    relpath: str,
    text: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    Perform Rust heuristic analysis based on the provided text.
    - Accuracy optimization: remove comments before heuristic matching (preserving string/char literals),
      to avoid false positives caused by API hits in comments.
    - Accuracy optimization 2: for generic API scanning, use a copy with "string content masked" to avoid treating fragments inside strings as code.
    - Accuracy optimization 3: use dataflow analysis to filter false positives.
    - Database-driven: prefer database queries, create a temporary database when there is no database.

    Args:
        relpath: relative file path
        text: source code text
        database: project database instance (optional)
    """
    clean_text = _remove_comments_preserve_strings(text)
    masked_text = _mask_strings_preserve_len(clean_text)
    # Raw lines: preserve comments and string content, used for SAFETY comment checks, etc.
    lines = text.splitlines()
    # Masked lines: string content has been replaced with spaces, suitable for generic API/keyword matching, reducing false positives
    mlines = masked_text.splitlines()

    # Dataflow analysis (used for false positive filtering)
    # If there is no database, create a temporary in-memory database and collect data with DataCollector
    _temp_database = None
    _db_file_path = relpath  # File path used for querying the database
    if database is None:
        try:
            from haijunbot.haijunbot_sec.project_database import ProjectDatabase
            from haijunbot.haijunbot_sec.data_collector import DataCollector

            _temp_database = ProjectDatabase(".", in_memory=True)
            collector = DataCollector(_temp_database)
            # Write to a temporary file for DataCollector analysis
            import tempfile
            import os

            _tmp_dir = tempfile.mkdtemp(prefix="hsec_rust_")
            _tmp_file = os.path.join(_tmp_dir, os.path.basename(relpath))
            with open(_tmp_file, "w", encoding="utf-8") as f:
                f.write(text)
            collector.analyze_file(_tmp_file, "rust")
            # Use the full path of the temporary file to query the database
            _db_file_path = _tmp_file
            database = _temp_database
        except Exception:
            pass  # On creation failure, continue using an empty database
    else:
        # When there is an external database, ensure the correct file path is used
        import os

        if os.path.isabs(relpath):
            _db_file_path = relpath

    data_flow_analyzer = DataFlowAnalyzer()
    data_flow_result = data_flow_analyzer.analyze_code(
        text, is_cpp=False, database=database, file_path=_db_file_path
    )

    # Clean up temporary files and directories (after all rule checks are complete)
    def _cleanup_temp_files():
        if _temp_database is not None:
            try:
                import os

                os.unlink(_tmp_file)
                os.rmdir(_tmp_dir)
            except (OSError, NameError):
                pass

    issues: List[Issue] = []
    # Generic API/keyword matching (using masked lines)
    issues.extend(_rule_unsafe(lines, _db_file_path, database=database))
    issues.extend(_rule_raw_pointer(lines, _db_file_path, database=database))
    issues.extend(_rule_transmute(mlines, _db_file_path, database=database))
    issues.extend(_rule_forget(mlines, _db_file_path, database=database))
    issues.extend(_rule_maybe_uninit(mlines, _db_file_path, database=database))
    # Error handling
    issues.extend(_rule_unwrap_expect(mlines, _db_file_path, database=database))
    issues.extend(_rule_ignore_result(mlines, _db_file_path, database=database))
    issues.extend(_rule_panic_unreachable(mlines, _db_file_path, database=database))
    # FFI related
    issues.extend(_rule_extern_c(mlines, _db_file_path, database=database))
    issues.extend(_rule_ffi_cstring(mlines, _db_file_path, database=database))
    # Concurrency related
    issues.extend(_rule_unsafe_impl(mlines, _db_file_path, database=database))
    issues.extend(_rule_refcell_borrow(mlines, _db_file_path, database=database))
    # Memory operation related
    issues.extend(_rule_get_unchecked(mlines, _db_file_path, database=database))
    issues.extend(_rule_pointer_arithmetic(mlines, _db_file_path, database=database))
    issues.extend(_rule_unsafe_mem_ops(mlines, _db_file_path, database=database))
    issues.extend(_rule_from_raw_parts(mlines, _db_file_path, database=database))
    issues.extend(_rule_manually_drop(mlines, _db_file_path, database=database))
    issues.extend(_rule_uninit_zeroed(mlines, _db_file_path, database=database))
    # New rules
    issues.extend(_rule_integer_overflow(mlines, _db_file_path, database=database))
    issues.extend(_rule_unsafe_fn(mlines, _db_file_path, database=database))
    issues.extend(_rule_as_cast(mlines, _db_file_path, database=database))
    issues.extend(_rule_into_raw(mlines, _db_file_path, database=database))
    issues.extend(_rule_static_mut(mlines, _db_file_path, database=database))
    issues.extend(_rule_unchecked_math(mlines, _db_file_path, database=database))
    issues.extend(_rule_rc_cycle(mlines, _db_file_path, database=database))
    # Taint analysis rules
    issues.extend(_rule_command_injection(mlines, _db_file_path, database=database))
    # TOCTOU race condition
    issues.extend(_rule_toctou_race(lines, _db_file_path, database=database))
    # SQL injection
    issues.extend(_rule_sql_injection(lines, _db_file_path, database=database))
    # Path traversal
    issues.extend(_rule_path_traversal(lines, _db_file_path, database=database))
    # Hardcoded credentials
    issues.extend(_rule_hardcoded_credentials(lines, _db_file_path, database=database))
    # Insecure random numbers
    issues.extend(_rule_insecure_random(lines, _db_file_path, database=database))
    # Secret not zeroized
    issues.extend(_rule_secret_no_zeroize(lines, _db_file_path, database=database))
    # Debug leaks secret
    issues.extend(_rule_debug_leak_secret(lines, _db_file_path, database=database))
    # Async safety issues
    issues.extend(_rule_async_safety(lines, _db_file_path, database=database))

    # Taint analysis (core functionality)
    try:
        taint_paths = taint_analyzer.analyze_with_best_analyzer(
            text, rules=None, file_path=str(_db_file_path), database=database
        )
        # Convert taint analysis results into Issue objects
        for taint_path in taint_paths:
            issue = Issue(
                language="rust",
                category="taint-analysis",
                pattern="taint-flow",
                file=str(_db_file_path),
                line=taint_path.line_number,
                evidence=f"{taint_path.source} -> {taint_path.sink}",
                description=f"Taint flow from {taint_path.source} to {taint_path.sink}",
                suggestion="Sanitize input data before use",
                confidence=taint_path.confidence,
                severity="high" if taint_path.confidence > 0.7 else "medium",
            )
            issues.append(issue)
    except Exception:
        # On taint analysis failure, silently ignore it without affecting heuristic scanning
        pass

    # Use dataflow analysis to filter false positives
    filtered_issues = _filter_issues_with_data_flow(
        issues, data_flow_analyzer, data_flow_result, lines
    )

    # Clean up temporary files and directories
    _cleanup_temp_files()

    return filtered_issues


def _filter_issues_with_data_flow(
    issues: List[Issue],
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> List[Issue]:
    """
    Use dataflow analysis to filter false positives

    Args:
        issues: list of issues found by heuristic scanning
        analyzer: dataflow analyzer
        dataflow_result: dataflow analysis result
        lines: list of source code lines

    Returns:
        List[Issue]: filtered list of issues
    """
    filtered_issues = []

    for issue in issues:
        # Check whether it is a false positive
        if _is_false_positive(issue, analyzer, dataflow_result, lines):
            continue
        filtered_issues.append(issue)

    return filtered_issues


def _is_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether an issue is a false positive

    Args:
        issue: issue object
        analyzer: dataflow analyzer
        dataflow_result: dataflow analysis result
        lines: list of source code lines

    Returns:
        bool: whether it is a false positive
    """
    issue_type = issue.pattern

    # unsafe false positive filtering: check whether there is a SAFETY comment
    if issue_type == "unsafe":
        return _is_unsafe_false_positive(issue, analyzer, dataflow_result, lines)

    # unwrap/expect false positive filtering: check whether there is an error handling context
    if issue_type in ["unwrap/expect", "unwrap", "expect"]:
        return _is_unwrap_false_positive(issue, analyzer, dataflow_result, lines)

    # panic false positive filtering: check whether it is in a test context or in an assert
    if issue_type in ["panic/unreachable", "panic!", "unreachable!"]:
        return _is_panic_false_positive(issue, analyzer, dataflow_result, lines)

    # raw pointer false positive filtering: check whether there is a SAFETY comment proving safety
    if issue_type == "raw_pointer":
        return _is_raw_pointer_false_positive(issue, analyzer, dataflow_result, lines)

    # transmute false positive filtering: check whether there is a SAFETY comment
    if issue_type == "mem::transmute":
        return _is_transmute_false_positive(issue, analyzer, dataflow_result, lines)

    # get_unchecked false positive filtering: check whether there is a bounds check or SAFETY comment
    if issue_type == "get_unchecked":
        return _is_get_unchecked_false_positive(issue, analyzer, dataflow_result, lines)

    # pointer arithmetic false positive filtering: check whether there is a SAFETY comment
    if issue_type == "pointer_arithmetic":
        return _is_pointer_arithmetic_false_positive(
            issue, analyzer, dataflow_result, lines
        )

    # memory operation false positive filtering: check whether there is a SAFETY comment
    if issue_type == "unsafe_mem_ops":
        return _is_unsafe_mem_ops_false_positive(
            issue, analyzer, dataflow_result, lines
        )

    # from_raw_parts false positive filtering: check whether there is a SAFETY comment
    if issue_type == "from_raw_parts/from_raw":
        return _is_from_raw_parts_false_positive(
            issue, analyzer, dataflow_result, lines
        )

    # Default is not to filter
    return False


def _is_unsafe_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether an unsafe block is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    2. Whether it is in a test context
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # SAFETY comments are already handled in the rule functions; here we check the dataflow analysis result
    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    return False


def _is_unwrap_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether unwrap/expect is a false positive

    Check logic:
    1. Whether it is in a test context
    2. Whether it is inside an if let Some/Ok branch (the unwrapped variable is the same variable matched by the if let)
    3. Whether it is inside a match Some/Ok branch (the unwrapped variable is the same variable matched by the match)
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    # Get the variable name of the unwrap call
    import re

    unwrap_line = lines[line_num - 1]
    # Extract the variable name: xxx.unwrap() or xxx.expect()
    var_match = re.search(r"(\w+)\.unwrap\(\)", unwrap_line)
    if not var_match:
        var_match = re.search(r"(\w+)\.expect\(\)", unwrap_line)
    unwrap_var = var_match.group(1) if var_match else None

    # Check whether it is inside an if let Some/Ok branch
    # Search upward for an if let Some(var) or if let Ok(var) construct
    for i in range(max(0, line_num - 15), line_num):
        if i >= len(lines):
            continue
        line = lines[i]
        # Check if let Some(var) = unwrap_var or if let Ok(var) = unwrap_var
        if "if let" in line:
            # Extract the variable name in the if let
            let_match = re.search(r"if let Some\((\w+)\)\s*=\s*(\w+)", line)
            if let_match:
                bound_var = let_match.group(1)  # variable in Some
                source_var = let_match.group(2)  # source variable
                # Check whether the unwrap uses the source variable or the bound variable
                if unwrap_var == source_var or unwrap_var == bound_var:
                    # Check whether unwrap is inside an if let block (determined by indentation)
                    if_indent = len(line) - len(line.lstrip())
                    unwrap_indent = len(unwrap_line) - len(unwrap_line.lstrip())
                    if unwrap_indent > if_indent:
                        return True
            else:
                let_match = re.search(r"if let Ok\((\w+)\)\s*=\s*(\w+)", line)
                if let_match:
                    bound_var = let_match.group(1)
                    source_var = let_match.group(2)
                    if unwrap_var == source_var or unwrap_var == bound_var:
                        if_indent = len(line) - len(line.lstrip())
                        unwrap_indent = len(unwrap_line) - len(unwrap_line.lstrip())
                        if unwrap_indent > if_indent:
                            return True

    # Check whether it is inside a match Some/Ok branch
    # Search upward for the match structure
    for i in range(max(0, line_num - 20), line_num):
        if i >= len(lines):
            continue
        line = lines[i]
        if "match" in line and unwrap_var and unwrap_var in line:
            # Find the structure that matches unwrap_var
            # Check whether unwrap is inside a Some/Ok branch
            for j in range(i + 1, line_num):
                check_line = lines[j]
                # Check the Some branch
                if re.search(r"Some\((\w+)\)\s*=>", check_line):
                    # unwrap is inside the Some branch
                    return True
                # Check the Ok branch
                if re.search(r"Ok\((\w+)\)\s*=>", check_line):
                    return True

    return False


def _is_panic_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether panic!/unreachable! is a false positive

    Check logic:
    1. Whether it is in a test context
    2. Whether it is in an assert macro
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    line = lines[line_num - 1]

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    # Check whether it is in an assert macro (assert!, assert_eq!, assert_ne!, etc.)
    if "assert" in line.lower():
        return True

    # Check whether it is in a test function (by checking the function definition context)
    for i in range(max(0, line_num - 20), line_num):
        if i < len(lines):
            line = lines[i]
            if "#[test]" in line or "#[cfg(test)]" in line:
                return True

    return False


def _is_raw_pointer_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether raw pointer usage is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    2. Whether it is at an FFI boundary (in an extern block)
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    # SAFETY comments are already handled in the rule function
    return False


def _is_transmute_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether transmute is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    return False


def _is_get_unchecked_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether get_unchecked is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving index validity
    2. Whether there is a preceding bounds check
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    # Check whether the previous 5 lines have a bounds check
    for i in range(max(0, line_num - 5), line_num):
        if i < len(lines):
            line = lines[i]
            if "<" in line or ">" in line or "<=" in line or ">=" in line:
                if "len" in line or "size" in line or "length" in line:
                    return True

    return False


def _is_pointer_arithmetic_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether pointer arithmetic is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    return False


def _is_unsafe_mem_ops_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether an unsafe memory operation is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    return False


def _is_from_raw_parts_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
    Determine whether from_raw_parts is a false positive

    Check logic:
    1. Whether there is a SAFETY comment proving safety
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    # Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    return False


def _rule_sql_injection(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-89: SQL injection detection
    Detection points:
    - format! constructs an SQL query
    - String concatenation constructs SQL
    - Dynamic ORDER BY/IN clause
    """
    issues: List[Issue] = []

    # SQL keyword patterns
    sql_keywords = [
        "SELECT",
        "INSERT",
        "UPDATE",
        "DELETE",
        "FROM",
        "WHERE",
        "ORDER BY",
        "GROUP BY",
        "HAVING",
        "LIMIT",
        "OFFSET",
        "IN",
    ]

    for idx, line in enumerate(lines, start=1):
        # Detect format! constructing SQL
        if "format!(" in line:
            # Check whether it contains SQL keywords
            line_upper = line.upper()
            for keyword in sql_keywords:
                if keyword in line_upper:
                    # Check whether there are safeguards for parameterized queries
                    has_safe_pattern = False
                    # Check whether parameterized placeholders such as $1, $2 are used
                    if re.search(r"\$\d+", line):
                        has_safe_pattern = True
                    # Check whether it is inside a safe macro such as sqlx::query_as!
                    if "sqlx::query_as!" in line or "sqlx::query!" in line:
                        has_safe_pattern = True

                    if not has_safe_pattern:
                        issues.append(
                            Issue(
                                language="rust",
                                category="sql_injection",
                                pattern="format_sql_injection",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(line),
                                description="Using format! to construct an SQL query may lead to SQL injection attacks",
                                suggestion="Use parameterized queries (sqlx::query_as! or .bind()) instead of string concatenation",
                                confidence=0.7,
                                severity="high",
                            )
                        )
                    break

        # Detect string concatenation constructing SQL
        if ".to_string()" in line or "+ " in line:
            line_upper = line.upper()
            for keyword in sql_keywords:
                if keyword in line_upper:
                    # Check whether it is a safe parameterized query
                    has_safe_pattern = False
                    if ".bind(" in line or "sqlx::query_as!" in line:
                        has_safe_pattern = True

                    if not has_safe_pattern:
                        issues.append(
                            Issue(
                                language="rust",
                                category="sql_injection",
                                pattern="concat_sql_injection",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(line),
                                description="String concatenation constructing an SQL query may lead to SQL injection attacks",
                                suggestion="Use parameterized queries (.bind()) instead of string concatenation",
                                confidence=0.6,
                                severity="high",
                            )
                        )
                    break

    return issues


def _rule_path_traversal(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-22: Path traversal detection
    Detection points:
    - PathBuf::from(user_input)
    - path.push(user_input)
    - format! constructs a file path
    - String concatenation constructs a file path
    """
    issues: List[Issue] = []

    for idx, line in enumerate(lines, start=1):
        # Detect PathBuf::from(user_input)
        if "PathBuf::from(" in line:
            # Check whether there is a canonicalize validation
            has_canonicalize = False
            # Look ahead 5 lines
            for i in range(idx, min(len(lines) + 1, idx + 5)):
                if "canonicalize" in lines[i - 1]:
                    has_canonicalize = True
                    break

            if not has_canonicalize:
                issues.append(
                    Issue(
                        language="rust",
                        category="path_traversal",
                        pattern="pathbuf_from_user_input",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(line),
                        description="PathBuf::from directly uses user input, which may lead to path traversal attacks",
                        suggestion="Use canonicalize() to normalize the path and verify that the path is within the expected directory",
                        confidence=0.6,
                        severity="high",
                    )
                )

        # Detect path.push(user_input)
        if ".push(" in line and "PathBuf" in line:
            # Check whether there is a canonicalize validation
            has_canonicalize = False
            for i in range(max(0, idx - 5), min(len(lines), idx + 5)):
                if "canonicalize" in lines[i]:
                    has_canonicalize = True
                    break

            if not has_canonicalize:
                issues.append(
                    Issue(
                        language="rust",
                        category="path_traversal",
                        pattern="path_push_user_input",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(line),
                        description="path.push() adds user input to the path, which may lead to path traversal attacks",
                        suggestion="Verify that the input does not contain .. or use canonicalize() to normalize the path",
                        confidence=0.6,
                        severity="high",
                    )
                )

        # Detect format! constructing a file path
        if "format!(" in line:
            # Check whether it contains file path keywords
            path_indicators = [
                "/",
                "path",
                "file",
                "dir",
                "config",
                "data",
                "tmp",
                "var",
                "etc",
            ]
            has_path_indicator = any(
                indicator in line.lower() for indicator in path_indicators
            )

            if has_path_indicator:
                # Check whether there is a canonicalize or starts_with validation
                has_validation = False
                for i in range(max(0, idx - 5), min(len(lines), idx + 5)):
                    if "canonicalize" in lines[i] or "starts_with" in lines[i]:
                        has_validation = True
                        break

                if not has_validation:
                    issues.append(
                        Issue(
                            language="rust",
                            category="path_traversal",
                            pattern="format_path_injection",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description="format! constructs a file path, which may lead to path traversal attacks",
                            suggestion="Use canonicalize() to normalize the path and verify that the path is within the expected directory",
                            confidence=0.5,
                            severity="medium",
                        )
                    )

    return issues


def _rule_hardcoded_credentials(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-798: Hardcoded credential detection
    Detection points:
    - const/static variable assigned a sensitive string
    - Variable name contains keywords such as key/password/secret/token
    - String::from() assigned a sensitive string
    """
    issues: List[Issue] = []

    # Sensitive variable name keywords
    sensitive_keywords = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "api_secret",
        "token",
        "access_key",
        "secret_key",
        "private_key",
        "privatekey",
        "priv_key",
        "auth",
        "credential",
        "jwt",
        "encryption_key",
    ]

    # Exclusion patterns (environment variable names, config names, etc.)
    exclude_patterns = [
        "env",
        "config",
        "name",
        "path",
        "url",
        "length",
        "type",
        "file",
    ]

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Skip comments
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue

        # Detect const/static variable assignments
        if (
            stripped.startswith("const ") or stripped.startswith("static ")
        ) and "= " in stripped:
            # Extract the variable name
            match = re.search(r"(?:const|static)\s+(\w+)", stripped)
            if match:
                var_name = match.group(1).lower()

                # Check whether it is a sensitive variable name
                is_sensitive = any(kw in var_name for kw in sensitive_keywords)
                is_excluded = any(ex in var_name for ex in exclude_patterns)

                if is_sensitive and not is_excluded:
                    # Check whether it is assigned a string literal
                    if '"' in stripped and len(stripped) > 30:
                        issues.append(
                            Issue(
                                language="rust",
                                category="hardcoded_credentials",
                                pattern="const_sensitive_value",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(line),
                                description="const/static variable contains a hardcoded credential",
                                suggestion="Use environment variables or a config file to store sensitive information",
                                confidence=0.8,
                                severity="critical",
                            )
                        )

        # Detect let variable assigned a sensitive string
        if "let " in stripped and "= " in stripped:
            # Extract the variable name
            match = re.search(r"let\s+(?:mut\s+)?(\w+)", stripped)
            if match:
                var_name = match.group(1).lower()

                is_sensitive = any(kw in var_name for kw in sensitive_keywords)
                is_excluded = any(ex in var_name for ex in exclude_patterns)

                if is_sensitive and not is_excluded:
                    # Check whether it is assigned a string literal
                    if '"' in stripped:
                        issues.append(
                            Issue(
                                language="rust",
                                category="hardcoded_credentials",
                                pattern="let_sensitive_value",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(line),
                                description="let variable contains a hardcoded credential",
                                suggestion="Use environment variables or a config file to store sensitive information",
                                confidence=0.7,
                                severity="high",
                            )
                        )

        # Detect String::from() assigned a sensitive string
        if "String::from(" in stripped:
            # Search backward for the variable name
            for i in range(max(0, idx - 3), idx):
                prev_line = lines[i - 1].strip()
                if "let " in prev_line or ": " in prev_line:
                    match = re.search(r"(?:let\s+(?:mut\s+)?|(\w+)\s*:)", prev_line)
                    if match:
                        var_name = match.group(1).lower() if match.group(1) else ""
                        if var_name and any(
                            kw in var_name for kw in sensitive_keywords
                        ):
                            issues.append(
                                Issue(
                                    language="rust",
                                    category="hardcoded_credentials",
                                    pattern="string_from_sensitive",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(line),
                                    description="String::from() contains a hardcoded credential",
                                    suggestion="Use environment variables or a config file to store sensitive information",
                                    confidence=0.7,
                                    severity="high",
                                )
                            )
                            break

    return issues


def _rule_insecure_random(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-338: Insecure random number detection
    Detection points:
    - StdRng::seed_from_u64() fixed seed
    - SmallRng is not cryptographically secure
    - thread_rng() used for security purposes
    """
    issues: List[Issue] = []

    # Security-sensitive function name keywords
    security_keywords = [
        "key",
        "token",
        "secret",
        "password",
        "nonce",
        "session",
        "auth",
        "crypt",
        "encrypt",
        "salt",
    ]

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect fixed seed
        if "seed_from_u64" in stripped:
            issues.append(
                Issue(
                    language="rust",
                    category="insecure_random",
                    pattern="fixed_seed",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description="Initializing the random number generator with a fixed seed produces predictable random numbers",
                    suggestion="Use OsRng to obtain true random numbers from the operating system",
                    confidence=0.9,
                    severity="high",
                )
            )

        # Detect SmallRng
        if "SmallRng" in stripped:
            issues.append(
                Issue(
                    language="rust",
                    category="insecure_random",
                    pattern="small_rng",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(line),
                    description="SmallRng is not a cryptographically secure random number generator",
                    suggestion="Use OsRng or rand::rngs::ThreadRng instead",
                    confidence=0.8,
                    severity="medium",
                )
            )

        # Detect thread_rng used for security purposes
        if "thread_rng" in stripped:
            # Check whether the function name contains security keywords
            for i in range(max(0, idx - 10), idx):
                prev_line = lines[i].strip()
                if "fn " in prev_line:
                    # Extract the function name
                    match = re.search(r"fn\s+(\w+)", prev_line)
                    if match:
                        func_name = match.group(1).lower()
                        if any(kw in func_name for kw in security_keywords):
                            issues.append(
                                Issue(
                                    language="rust",
                                    category="insecure_random",
                                    pattern="thread_rng_security",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(line),
                                    description="thread_rng used for security-sensitive operations may not be secure enough",
                                    suggestion="Use OsRng for cryptographically secure random number generation",
                                    confidence=0.6,
                                    severity="medium",
                                )
                            )
                            break

    return issues


def _rule_secret_no_zeroize(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-226: Secret not zeroized detection
    Detection points:
    - Sensitive variables stored in String/Vec without using zeroize
    - No call to the .zeroize() method
    - No use of the Zeroizing wrapper
    """
    issues: List[Issue] = []

    # Sensitive variable name keywords
    sensitive_keywords = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "key",
        "token",
        "private",
        "credential",
        "session",
    ]

    # Check whether the zeroize library is used (to lower confidence)
    # has_zeroize_import = False
    # for line in lines:
    #     if "use zeroize" in line or "zeroize::" in line:
    #         has_zeroize_import = True
    #         break

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect sensitive variable assignments
        if "let " in stripped and "= " in stripped:
            # Extract the variable name
            match = re.search(r"let\s+(?:mut\s+)?(\w+)", stripped)
            if match:
                var_name = match.group(1).lower()

                # Check whether it is a sensitive variable name
                is_sensitive = any(kw in var_name for kw in sensitive_keywords)

                if is_sensitive:
                    # Check whether the Zeroizing wrapper is used
                    has_zeroizing = "Zeroizing" in stripped

                    if not has_zeroizing:
                        # Check whether there is a .zeroize() call within the function
                        has_zeroize_call = False
                        # Find the function end position
                        func_end = idx + 20  # Look ahead 20 lines by default
                        for i in range(idx, min(len(lines) + 1, func_end)):
                            check_line = lines[i - 1].strip()
                            if var_name in check_line and ".zeroize()" in check_line:
                                has_zeroize_call = True
                                break
                            # Encountered the function end marker
                            if check_line.startswith("fn ") or check_line == "}":
                                break

                        if not has_zeroize_call:
                            issues.append(
                                Issue(
                                    language="rust",
                                    category="secret_no_zeroize",
                                    pattern="sensitive_no_zeroize",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(line),
                                    description="Sensitive data stored in memory is not cleared, which may lead to memory leakage",
                                    suggestion="Use the zeroize library to clear sensitive data, or use the Zeroizing wrapper",
                                    confidence=0.6,
                                    severity="medium",
                                )
                            )

    return issues


def _rule_debug_leak_secret(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-532: Debug secret leakage detection
    Detection points:
    - #[derive(Debug)] on a struct containing sensitive fields
    - Sensitive field names contain keywords such as key/password/secret/token
    """
    issues: List[Issue] = []

    # Sensitive field name keywords
    sensitive_keywords = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "api_key",
        "apikey",
        "secret_key",
        "token",
        "private_key",
        "credential",
    ]

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect #[derive(Debug)]
        if (
            stripped == "#[derive(Debug)]"
            or "#[derive(Debug," in stripped
            or "derive(Debug)" in stripped
        ):
            # Check whether the next line is a struct definition
            if idx < len(lines):
                next_line = lines[idx].strip()
                if next_line.startswith("struct ") or next_line.startswith(
                    "pub struct "
                ):
                    # Extract the struct name
                    struct_match = re.search(r"struct\s+(\w+)", next_line)
                    if struct_match:
                        struct_name = struct_match.group(1)

                        # Check whether the struct contains sensitive fields
                        has_sensitive_field = False
                        sensitive_fields = []

                        # Find the range of the struct body
                        for i in range(idx + 1, min(len(lines), idx + 20)):
                            field_line = lines[i].strip()

                            # struct end
                            if field_line == "}":
                                break

                            # Extract the field name
                            field_match = re.search(r"(?:pub\s+)?(\w+)\s*:", field_line)
                            if field_match:
                                field_name = field_match.group(1).lower()
                                if any(kw in field_name for kw in sensitive_keywords):
                                    has_sensitive_field = True
                                    sensitive_fields.append(field_match.group(1))

                        if has_sensitive_field:
                            issues.append(
                                Issue(
                                    language="rust",
                                    category="debug_leak_secret",
                                    pattern="derive_debug_sensitive",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(line),
                                    description=f"struct {struct_name} contains sensitive fields {sensitive_fields}, the Debug trait may leak sensitive information",
                                    suggestion="Implement a custom Debug trait to mask sensitive fields",
                                    confidence=0.7,
                                    severity="medium",
                                )
                            )

    return issues


def _rule_async_safety(
    lines: List[str],
    relpath: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    CWE-1031: Async safety issue detection
    Detection points:
    - std::fs in an async function
    - std::thread::sleep in an async function
    - std::net::TcpStream::connect in an async function
    - CPU-intensive loop in an async function
    """
    issues: List[Issue] = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Detect async functions
        if "async fn " in stripped:
            # Extract the function name
            match = re.search(r"async\s+fn\s+(\w+)", stripped)
            if match:
                func_start = idx

                # Find the function body range (simple method: find the next async fn or end of file)
                func_end = len(lines)
                for i in range(idx, len(lines)):
                    if lines[i].strip().startswith("async fn ") and i > idx - 1:
                        func_end = i
                        break

                # Check for blocking operations within the function body
                for i in range(func_start, min(func_end + 1, len(lines) + 1)):
                    check_line = lines[i - 1].strip()

                    # Detect std::fs operations
                    if "std::fs::" in check_line and "tokio::fs" not in check_line:
                        issues.append(
                            Issue(
                                language="rust",
                                category="async_safety",
                                pattern="blocking_io",
                                file=relpath,
                                line=i,
                                evidence=_strip_line(lines[i - 1]),
                                description="using blocking std::fs I/O in an async function blocks the entire runtime",
                                suggestion="use tokio::fs for asynchronous file operations",
                                confidence=0.8,
                                severity="high",
                            )
                        )

                    # Detect std::thread::sleep
                    if "std::thread::sleep" in check_line:
                        issues.append(
                            Issue(
                                language="rust",
                                category="async_safety",
                                pattern="blocking_sleep",
                                file=relpath,
                                line=i,
                                evidence=_strip_line(lines[i - 1]),
                                description="using std::thread::sleep in an async function blocks the entire runtime",
                                suggestion="use tokio::time::sleep for asynchronous sleep",
                                confidence=0.9,
                                severity="high",
                            )
                        )

                    # Detect std::net::TcpStream::connect
                    if "std::net::TcpStream::connect" in check_line:
                        issues.append(
                            Issue(
                                language="rust",
                                category="async_safety",
                                pattern="blocking_net",
                                file=relpath,
                                line=i,
                                evidence=_strip_line(lines[i - 1]),
                                description="using blocking std::net network operations in an async function",
                                suggestion="use tokio::net for asynchronous network operations",
                                confidence=0.8,
                                severity="high",
                            )
                        )

                    # Detect CPU-intensive loops
                    if "for _ in 0.." in check_line or "for _ in 0.." in check_line:
                        # Check whether the loop count is very large
                        loop_match = re.search(r"0\.\.([0-9]+)", check_line)
                        if loop_match:
                            loop_count = int(loop_match.group(1))
                            if loop_count > 10000:
                                issues.append(
                                    Issue(
                                        language="rust",
                                        category="async_safety",
                                        pattern="cpu_intensive_loop",
                                        file=relpath,
                                        line=i,
                                        evidence=_strip_line(lines[i - 1]),
                                        description="CPU-intensive loop in an async function blocks the runtime",
                                        suggestion="use spawn_blocking to move CPU-intensive tasks to a separate thread",
                                        confidence=0.6,
                                        severity="medium",
                                    )
                                )

    return issues


def analyze_rust_file(
    base: Path, relpath: Path, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Read files from disk for analysis.
    """
    try:
        text = (base / relpath).read_text(errors="ignore")
    except Exception:
        return []
    return analyze_rust_text(str(relpath), text, database=database)


def analyze_rust_files(
    base_path: str,
    relative_paths: List[str],
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    Batch analyze files; relative paths are relative to base_path.
    """
    base = Path(base_path).resolve()
    out: List[Issue] = []
    for f in relative_paths:
        p = Path(f)
        if p.suffix.lower() == ".rs":
            out.extend(analyze_rust_file(base, p, database=database))
    return out
