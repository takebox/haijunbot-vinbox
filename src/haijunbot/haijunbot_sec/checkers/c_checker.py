# -*- coding: utf-8 -*-
"""
HaijunBot Security Analysis Suite - C/C++ Heuristic Security Checker

Purpose and Scope:
- Focus on three fundamental security issues: memory management, buffer operations, and error handling; provides explainable heuristic detection and confidence assessment.
- Targets C/C++ and header files (.c/.cpp/.h/.hpp).

Output Conventions:
- Returns a list of haijunbot.haijunbot_sec.workflow.Issue (structured format for aggregation scoring and report generation).
- Confidence range [0,1], weighted based on matched rules and contextual clues; severity is high/medium/low.

Usage (example):
- from haijunbot.haijunbot_sec.checkers.c_checker import analyze_files
- issues = analyze_files("./repo", ["src/a.c", "include/a.h"])
"""

from __future__ import annotations


from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
from pathlib import Path
from typing import Any
from typing import Dict
from typing import TYPE_CHECKING
from typing import Iterable
from typing import List
from typing import Optional
from typing import Sequence
from typing import Tuple

from haijunbot.haijunbot_sec.types import Issue

if TYPE_CHECKING:
    from haijunbot.haijunbot_sec.project_database import ProjectDatabase

# Taint analysis framework (core dependency)
import haijunbot.haijunbot_sec.taint_analyzer as taint_analyzer

# Data flow analyzer (for false positive filtering)
from haijunbot.haijunbot_sec.data_flow_analyzer import (
    DataFlowAnalyzer,
    DataFlowResult,
    PointerState,
)

# ---------------------------
# Helper functions
# ---------------------------


def _is_cpp_file(file_path: str) -> bool:
    """Check if file is a C++ file"""
    return file_path.lower().endswith((".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"))


# ---------------------------
# Rule Library (Regular Expressions)
# ---------------------------

RE_UNSAFE_API = re.compile(
    r"\b(strcpy|strcat|gets|sprintf|vsprintf)\s*\(",
    re.IGNORECASE,
)
RE_BOUNDARY_FUNCS = re.compile(
    r"\b(memcpy|memmove|strncpy|strncat)\s*\(",
    re.IGNORECASE,
)
RE_MEM_MGMT = re.compile(
    r"\b(malloc|calloc|realloc|free|new\s+|delete\b)",
    re.IGNORECASE,
)
RE_IO_API = re.compile(
    r"\b(fopen|fread|fwrite|read|write|open|close)\s*\(",
    re.IGNORECASE,
)
# fclose usually doesn't need its return value checked (checking after close is of little value)
RE_IO_API_NO_CHECK = re.compile(
    r"\b(fclose)\s*\(",
    re.IGNORECASE,
)
# Permission operation functions (return value checking is crucial)
RE_PRIV_API = re.compile(
    r"\b(setuid|setgid|seteuid|setegid|setreuid|setregid|setresuid|setresgid|"
    r"chown|lchown|fchown|chmod|fchmod|fchmodat)\s*\(",
    re.IGNORECASE,
)
# Deserialization related functions (CWE-502)
RE_DESERIALIZE_API = re.compile(
    r"\b(json_loads|json_load|yaml_load|pickle_loads|pickle_load|"
    r"protobuf_decode|msgpack_unpack|cbor_decode|xml_parse|"
    r"unserialize|deserialize|decode)\s*\(",
    re.IGNORECASE,
)

# SSRF related functions (CWE-918)
RE_SSRF_API = re.compile(
    r"\b(curl_easy_setopt|curl_easy_init|wget|system|popen)\b",
    re.IGNORECASE,
)

# SSRF URL parameters
RE_SSRF_URL_PARAM = re.compile(r"CURLOPT_URL")

# SSRF validation functions
RE_SSRF_VALIDATE = re.compile(
    r"\b(is_url_allowed|is_domain_allowed|validate_url|check_url|"
    r"url_whitelist|is_safe_url|verify_url|sanitize_url|is_valid_url)\b",
    re.IGNORECASE,
)

# Resource consumption related functions (CWE-400)
RE_RESOURCE_API = re.compile(
    r"\b(malloc|calloc|realloc|alloca|new)\s*\(",
    re.IGNORECASE,
)

# Resource limit constants
RE_RESOURCE_LIMIT = re.compile(
    r"\b(MAX_|max_|LIMIT_|limit_|BOUND_|bound_)\w*\b",
    re.IGNORECASE,
)

# Recursive function detection
RE_RECURSIVE_CALL = re.compile(
    r"\b(fibonacci|traverse|recurse|recursive)\b",
    re.IGNORECASE,
)

# Network IO functions (return value checking is crucial)
RE_NET_API = re.compile(
    r"\b(recv|send|recvfrom|sendto|recvmsg|sendmsg|"
    r"connect|accept|accept4|listen|bind|socket)\s*\(",
    re.IGNORECASE,
)

# Added: format string / dangerous temporary file / command execution and other risky API patterns
RE_PRINTF_LIKE = re.compile(
    r"\b(printf|sprintf|snprintf|vsprintf|vsnprintf|syslog|vsyslog|err|errx|warn|warnx)\s*\(",
    re.IGNORECASE,
)
RE_FPRINTF = re.compile(r"\bfprintf\s*\(", re.IGNORECASE)
RE_INSECURE_TMP = re.compile(r"\b(tmpnam|tempnam|mktemp)\s*\(", re.IGNORECASE)
RE_SYSTEM_LIKE = re.compile(r"\b(system|popen)\s*\(", re.IGNORECASE)
RE_EXEC_LIKE = re.compile(
    r"\b(execvp|execlp|execvpe|execl|execve|execv)\s*\(", re.IGNORECASE
)
# Windows ShellExecute API (false negative fix)
RE_SHELLEXECUTE = re.compile(
    r"\b(ShellExecute|ShellExecuteA|ShellExecuteW|ShellExecuteEx|ShellExecuteExA|ShellExecuteExW)\s*\(",
    re.IGNORECASE,
)
RE_SCANF_CALL = re.compile(r'\b(?:[fs]?scanf)\s*\(\s*"([^"]*)"', re.IGNORECASE)
# sscanf/fscanf format string is in the 2nd parameter (the 1st parameter is the input source/FILE*)
RE_SCANF_CALL_ARG2 = re.compile(
    r'\b(?:sscanf|fscanf)\s*\([^,]+,\s*"([^"]*)"', re.IGNORECASE
)
# Threads/locks related
RE_PTHREAD_LOCK = re.compile(
    r"\bpthread_mutex_lock\s*\(\s*&?\s*([A-Za-z_]\w*)\s*\)\s*;?", re.IGNORECASE
)
RE_PTHREAD_UNLOCK = re.compile(
    r"\bpthread_mutex_unlock\s*\(\s*&?\s*([A-Za-z_]\w*)\s*\)\s*;?", re.IGNORECASE
)
# Other dangerous usages
RE_ATOI_FAMILY = re.compile(r"\b(atoi|atol|atoll|atof)\s*\(", re.IGNORECASE)
RE_RAND = re.compile(r"\b(rand|srand)\s*\(", re.IGNORECASE)
RE_STRTOK = re.compile(r"\bstrtok\s*\(", re.IGNORECASE)
RE_OPEN_PERMISSIVE = re.compile(
    r"\bopen\s*\(\s*[^,]+,\s*[^,]*O_CREAT[^,]*,\s*(0[0-7]{3,4})\s*\)", re.IGNORECASE
)
RE_FOPEN_MODE = re.compile(r'\bfopen\s*\(\s*[^,]+,\s*"([^"]+)"\s*\)', re.IGNORECASE)
RE_GENERIC_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*")
RE_FREE_CALL_ANY = re.compile(r"\bfree\s*\(\s*([^)]+?)\s*\)", re.IGNORECASE)
# Extension: more dangerous usage related
RE_ALLOCA = re.compile(r"\balloca\s*\(\s*([^)]+)\s*\)", re.IGNORECASE)
RE_VLA_DECL = re.compile(
    r"\b(?:const\s+|volatile\s+|static\s+|register\s+|unsigned\s+|signed\s+)?[A-Za-z_]\w*(?:\s+\*|\s+)+[A-Za-z_]\w*\s*\[\s*([^\]]+)\s*\]\s*;",
    re.IGNORECASE,
)
RE_PTHREAD_RET = re.compile(
    r"\b(pthread_(?:mutex_(?:lock|trylock|timedlock)|create|cond_(?:wait|timedwait)|join|detach))\s*\(",
    re.IGNORECASE,
)
RE_PTHREAD_COND_WAIT = re.compile(r"\bpthread_cond_(?:timed)?wait\s*\(", re.IGNORECASE)
RE_PTHREAD_CREATE = re.compile(
    r"\bpthread_create\s*\(\s*&\s*([A-Za-z_]\w*)\s*,", re.IGNORECASE
)
RE_PTHREAD_JOIN = re.compile(r"\bpthread_join\s*\(\s*([A-Za-z_]\w*)\s*,", re.IGNORECASE)
RE_PTHREAD_DETACH = re.compile(
    r"\bpthread_detach\s*\(\s*([A-Za-z_]\w*)\s*\)", re.IGNORECASE
)
# C++ standard library locks
RE_STD_MUTEX = re.compile(r"\b(?:std::)?mutex\s+([A-Za-z_]\w*)", re.IGNORECASE)
RE_MUTEX_LOCK = re.compile(r"\b([A-Za-z_]\w*)\s*\.lock\s*\(", re.IGNORECASE)
RE_MUTEX_UNLOCK = re.compile(r"\b([A-Za-z_]\w*)\s*\.unlock\s*\(", re.IGNORECASE)
RE_MUTEX_TRY_LOCK = re.compile(r"\b([A-Za-z_]\w*)\s*\.try_lock\s*\(", re.IGNORECASE)
RE_LOCK_GUARD = re.compile(
    r"\b(?:std::)?lock_guard\s*<[^>]+>\s*([A-Za-z_]\w*)", re.IGNORECASE
)
RE_UNIQUE_LOCK = re.compile(
    r"\b(?:std::)?unique_lock\s*<[^>]+>\s*([A-Za-z_]\w*)", re.IGNORECASE
)
RE_SHARED_LOCK = re.compile(
    r"\b(?:std::)?shared_lock\s*<[^>]+>\s*([A-Za-z_]\w*)", re.IGNORECASE
)
RE_STD_LOCK = re.compile(r"\bstd::lock\s*\(", re.IGNORECASE)
RE_SCOPED_LOCK = re.compile(r"\b(?:std::)?scoped_lock\s*<", re.IGNORECASE)
# Data race detection
RE_STATIC_VAR = re.compile(
    r"\bstatic\s+(?:const\s+|volatile\s+)?[A-Za-z_]\w*(?:\s+\*|\s+)+([A-Za-z_]\w*)",
    re.IGNORECASE,
)
RE_EXTERN_VAR = re.compile(
    r"\bextern\s+[A-Za-z_]\w*(?:\s+\*|\s+)+([A-Za-z_]\w*)", re.IGNORECASE
)
RE_STD_THREAD = re.compile(r"\b(?:std::)?thread\s+([A-Za-z_]\w*)", re.IGNORECASE)
RE_ATOMIC = re.compile(r"\b(?:std::)?atomic\s*<[^>]+>\s*([A-Za-z_]\w*)", re.IGNORECASE)
RE_VOLATILE = re.compile(
    r"\bvolatile\s+[A-Za-z_]\w*(?:\s+\*|\s+)+([A-Za-z_]\w*)", re.IGNORECASE
)
RE_VAR_ACCESS = re.compile(r"\b([A-Za-z_]\w*)\s*(?:=|\[|->|\.)", re.IGNORECASE)
RE_VAR_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*=", re.IGNORECASE)
RE_INET_LEGACY = re.compile(r"\b(inet_addr|inet_aton)\s*\(", re.IGNORECASE)
RE_TIME_UNSAFE = re.compile(r"\b(asctime|ctime|localtime|gmtime)\s*\(", re.IGNORECASE)
RE_GETENV = re.compile(r'\bgetenv\s*\(\s*"[^"]*"\s*\)', re.IGNORECASE)

# Helper regex patterns
RE_REALLOC_ASSIGN_BACK = re.compile(
    r"\b([A-Za-z_]\w*)\s*=\s*realloc\s*\(\s*\1\s*,", re.IGNORECASE
)
RE_MALLOC_ASSIGN = re.compile(
    r"\b([A-Za-z_]\w*)\s*=\s*(?:\([^)]*\))?\s*malloc\s*\(", re.IGNORECASE
)
RE_CALLOC_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*calloc\s*\(", re.IGNORECASE)
RE_NEW_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*new\b", re.IGNORECASE)
RE_DEREF = re.compile(r"(\*|->)\s*[A-Za-z_]\w*|\b[A-Za-z_]\w*\s*\[", re.IGNORECASE)
RE_NULL_CHECK = re.compile(
    r"\bif\s*\(\s*(!\s*)?[A-Za-z_]\w*\s*(==|!=)\s*NULL\s*\)|\bif\s*\(\s*[A-Za-z_]\w*\s*\)",
    re.IGNORECASE,
)
RE_FREE_VAR = re.compile(r"free\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;", re.IGNORECASE)
RE_USE_VAR = re.compile(r"\b([A-Za-z_]\w*)\b")
RE_STRLEN_IN_SIZE = re.compile(r"\bstrlen\s*\(", re.IGNORECASE)
RE_SIZEOF_PTR = re.compile(r"\bsizeof\s*\(\s*\*\s*[A-Za-z_]\w*\s*\)", re.IGNORECASE)
RE_STRNCPY = re.compile(r"\bstrncpy\s*\(", re.IGNORECASE)
RE_STRNCAT = re.compile(r"\bstrncat\s*\(", re.IGNORECASE)
# CWE-327: weak encryption algorithm API patterns
RE_WEAK_CRYPTO = re.compile(
    r"\b(DES_set_key|DES_set_key_unchecked|DES_ecb_encrypt|DES_cbc_encrypt|DES_ncbc_encrypt|"
    r"DES_ede3_cbc_encrypt|DES_ede2_cbc_encrypt|"
    r"RC4_set_key|RC4|"
    r"MD5_Init|MD5_Update|MD5_Final|MD5_Transform|"
    r"SHA1_Init|SHA1_Update|SHA1_Final|SHA1_Transform|"
    r"BF_set_key|BF_ecb_encrypt|BF_cbc_encrypt|BF_encrypt|BF_decrypt)\s*\(",
    re.IGNORECASE,
)

# C++ specific patterns
RE_SHARED_PTR = re.compile(r"\b(?:std::)?shared_ptr\s*<", re.IGNORECASE)
RE_UNIQUE_PTR = re.compile(r"\b(?:std::)?unique_ptr\s*<", re.IGNORECASE)
RE_WEAK_PTR = re.compile(r"\b(?:std::)?weak_ptr\s*<", re.IGNORECASE)
RE_SMART_PTR_ASSIGN = re.compile(
    r"\b([A-Za-z_]\w*)\s*=\s*(?:std::)?(?:shared_ptr|unique_ptr|weak_ptr)\s*<",
    re.IGNORECASE,
)
RE_NEW_ARRAY = re.compile(r"\bnew\s+[A-Za-z_]\w*\s*\[", re.IGNORECASE)
RE_DELETE_ARRAY = re.compile(r"\bdelete\s*\[\s*\]", re.IGNORECASE)
RE_DELETE = re.compile(r"\bdelete\s+(?!\[)", re.IGNORECASE)
RE_STATIC_CAST = re.compile(r"\bstatic_cast\s*<", re.IGNORECASE)
RE_DYNAMIC_CAST = re.compile(r"\bdynamic_cast\s*<", re.IGNORECASE)
RE_REINTERPRET_CAST = re.compile(r"\breinterpret_cast\s*<", re.IGNORECASE)
RE_CONST_CAST = re.compile(r"\bconst_cast\s*<", re.IGNORECASE)
RE_VECTOR_ACCESS = re.compile(
    r"\b(?:std::)?vector\s*<[^>]+>\s*[A-Za-z_]\w*\s*\[", re.IGNORECASE
)
RE_STRING_ACCESS = re.compile(
    r"\b(?:std::)?(?:string|wstring)\s*[A-Za-z_]\w*\s*\[", re.IGNORECASE
)
RE_VECTOR_VAR = re.compile(
    r"\b(?:std::)?vector\s*<[^>]+>\s*([A-Za-z_]\w*)", re.IGNORECASE
)
RE_STRING_VAR = re.compile(
    r"\b(?:std::)?(?:string|wstring)\s+([A-Za-z_]\w*)", re.IGNORECASE
)
RE_AT_METHOD = re.compile(r"\.at\s*\(", re.IGNORECASE)
RE_VIRTUAL_DTOR = re.compile(r"\bvirtual\s+~[A-Za-z_]\w*\s*\(", re.IGNORECASE)
RE_CLASS_DECL = re.compile(r"\bclass\s+([A-Za-z_]\w*)", re.IGNORECASE)
RE_DTOR_DECL = re.compile(r"~\s*([A-Za-z_]\w*)\s*\(", re.IGNORECASE)
RE_MOVE = re.compile(r"\bstd::move\s*\(", re.IGNORECASE)
RE_MOVE_ASSIGN = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*std::move\s*\(", re.IGNORECASE)
RE_THROW = re.compile(r"\bthrow\s+", re.IGNORECASE)
RE_TRY = re.compile(r"\btry\s*\{", re.IGNORECASE)
RE_CATCH = re.compile(r"\bcatch\s*\(", re.IGNORECASE)
RE_NOEXCEPT = re.compile(r"\bnoexcept\s*(?:\([^)]*\))?", re.IGNORECASE)


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
    Remove comments from C/C++ source code (// and /* */), preserving string and character literal content;
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
    escape = False

    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if in_sl_comment:
            # Single-line comment ends at newline
            if ch == "\n":
                in_sl_comment = False
                res.append(ch)
            else:
                # Use spaces as placeholders to preserve column count
                res.append(" ")
            i += 1
            continue

        if in_bl_comment:
            # Multi-line comment until */
            if ch == "*" and nxt == "/":
                in_bl_comment = False
                res.append(" ")
                res.append(" ")
                i += 2
            else:
                # Keep newlines inside the comment body, replace the rest with spaces
                res.append("\n" if ch == "\n" else " ")
                i += 1
            continue

        # In non-comment state, handle strings and character literals
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

        # Enter comment determination (must not be inside a string/char literal)
        if ch == "/" and nxt == "/":
            in_sl_comment = True
            # Keep two placeholders to avoid concatenation
            res.append(" ")
            res.append(" ")
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_bl_comment = True
            res.append(" ")
            res.append(" ")
            i += 2
            continue

        # Enter string/char literal
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

        # Ordinary character
        res.append(ch)
        i += 1

    return "".join(res)


def _mask_strings_preserve_len(text: str) -> str:
    """
    Replace the inner content of strings and char literals with spaces, keeping quotes and newlines, preserving length and line numbers.
    Used to avoid mistakenly treating fragments inside strings (such as "system(") as code when scanning general API patterns.
    Note: this function does not remove comments; call it on text from which comments have already been removed.
    """
    res: list[str] = []
    in_string = False
    in_char = False
    escape = False
    for ch in text:
        if in_string:
            if escape:
                # Keep an escaped backslash as two characters (backslash + space) so as not to break column alignment too much
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
            continue
        if ch == '"':
            in_string = True
            res.append('"')
            continue
        if ch == "'":
            in_char = True
            res.append("'")
            continue
        res.append(ch)
    return "".join(res)


def _strip_if0_blocks(text: str) -> str:
    """
    Preprocess the common #if 0 ... #else ... #endif structure:
    - Skip the body of #if 0; if #else exists, keep the #else branch
    - Preserve line count and newlines to keep line numbers stable
    Limitation: only recognizes the constant-0 condition, does not evaluate complex expressions; #elif is not handled
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    stack: list[
        dict[str, Any]
    ] = []  # Each frame: {"kind": "if0"|"if", "skipping": bool, "in_else": bool}

    def any_skipping() -> bool:
        return any(frame.get("skipping", False) for frame in stack)

    for line in lines:
        if re.match(r"^\s*#\s*if\s+0\b", line):
            # Enter #if 0: skip the body
            stack.append({"kind": "if0", "skipping": True, "in_else": False})
            out.append("\n" if line.endswith("\n") else "")
            continue
        if re.match(r"^\s*#\s*if\b", line):
            # Other #if: do not evaluate, only record, inherit the outer skipping
            stack.append({"kind": "if", "skipping": any_skipping(), "in_else": False})
            out.append(
                line if not any_skipping() else ("\n" if line.endswith("\n") else "")
            )
            continue
        if re.match(r"^\s*#\s*else\b", line):
            if stack:
                top = stack[-1]
                if top["kind"] == "if0":
                    # The else of #if 0: flip skipping to make the else branch active
                    top["skipping"] = not top["skipping"]
                    top["in_else"] = True
            out.append(
                line if not any_skipping() else ("\n" if line.endswith("\n") else "")
            )
            continue
        if re.match(r"^\s*#\s*endif\b", line):
            if stack:
                stack.pop()
            out.append(
                line if not any_skipping() else ("\n" if line.endswith("\n") else "")
            )
            continue
        # Normal code
        if any_skipping():
            out.append("\n" if line.endswith("\n") else "")
        else:
            out.append(line)
    return "".join(out)


def _has_null_check_around(
    var: str, lines: Sequence[str], line_no: int, radius: int = 5
) -> bool:
    """
    Extend null pointer check detection to reduce false positives:
    - if (ptr) / if (!ptr)
    - if (ptr == NULL/0) / if (NULL/0 == ptr)
    - Assertion/check macros: assert(ptr), assert(ptr != NULL), BUG_ON(!ptr), WARN_ON(!ptr), CHECK/ENSURE, etc.
    - Early return: if (!ptr) return ... / if (ptr == NULL) return ...
    - Error handling jump: if (!ptr) goto error; / if (ptr == NULL) goto fail;
    - Loop conditions: while (ptr && ...) / for (...; ptr && ...; ...)
    """
    for i, s in _window(lines, line_no, before=radius, after=radius):
        # Direct true/false check
        if re.search(rf"\bif\s*\(\s*{re.escape(var)}\b", s):
            return True
        if re.search(rf"\bif\s*\(\s*!\s*{re.escape(var)}\b", s):
            return True
        # Explicit comparison with NULL/0 (any order)
        if re.search(rf"\bif\s*\(\s*{re.escape(var)}\s*(==|!=)\s*(NULL|0)\b", s):
            return True
        if re.search(rf"\bif\s*\(\s*(NULL|0)\s*(==|!=)\s*{re.escape(var)}\b", s):
            return True
        # Assertion/check macros (common): assert/BUG_ON/WARN_ON/CHECK/ENSURE
        if re.search(
            rf"\b(assert|BUG_ON|WARN_ON|CHECK|ENSURE)\s*\(\s*(!\s*)?{re.escape(var)}(\s*(==|!=)\s*(NULL|0))?\s*\)",
            s,
        ):
            return True
        # Early return defense: if (!ptr) return ... / if (ptr == NULL) return ...
        if re.search(rf"\bif\s*\([^)]*{re.escape(var)}[^)]*\)\s*\breturn\b", s):
            return True
        # Error handling jump: if (!ptr) goto error; / if (ptr == NULL) goto fail;
        if re.search(rf"\bif\s*\([^)]*{re.escape(var)}[^)]*\)\s*\bgoto\b", s):
            return True
        # Loop condition check: while (ptr && ...) / for (...; ptr && ...; ...)
        if re.search(rf"\bwhile\s*\([^)]*{re.escape(var)}[^)]*\)", s):
            return True
        if re.search(rf"\bfor\s*\([^)]*{re.escape(var)}[^)]*\)", s):
            return True
    return False


def _has_len_bound_around(lines: Sequence[str], line_no: int, radius: int = 3) -> bool:
    for _, s in _window(lines, line_no, before=radius, after=radius):
        # Detect presence of length bound/check (very rough)
        if any(
            k in s
            for k in [
                "sizeof(",
                "BUFFER_SIZE",
                "MAX_",
                "min(",
                "clamp(",
                "snprintf",
                "strlcpy",
                "strlcat",
            ]
        ):
            return True
    return False


def _severity_from_confidence(conf: float, base: str) -> str:
    # Adjust default severity based on base category
    if conf >= 0.8:
        return "high"
    if conf >= 0.6:
        return "medium"
    return "low"


# ---------------------------
# Specific validation rules
# ---------------------------


def _rule_unsafe_api(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unsafe API calls (strcpy/strcat/gets/sprintf/vsprintf).
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    """
    issues: List[Issue] = []
    UNSAFE_APIS = {"strcpy", "strcat", "gets", "sprintf", "vsprintf"}
    is_header = str(relpath).lower().endswith((".h", ".hpp"))
    re_type_kw = re.compile(
        r"\b(static|inline|const|volatile|unsigned|signed|long|short|int|char|void|size_t|ssize_t)\b"
    )

    # Prefer using database queries
    if database:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name.lower() not in UNSAFE_APIS:
                continue
            # Safe wrapper detection: skip if caller_name contains security keywords
            caller_name = call.get("caller_name", "")
            if re.search(
                r"(safe|secure|wrapper|bounded|checked|limited|copy)",
                caller_name,
                re.IGNORECASE,
            ):
                continue
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            if 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                continue

            # Skip preprocessor lines and declaration lines
            t = s.lstrip()
            if t.startswith("#") or re.search(r"\b(typedef|extern)\b", s):
                continue

            # Skip function prototypes in header files
            if is_header:
                m = re.search(rf"\b{callee_name}\s*\(", s, re.IGNORECASE)
                if m:
                    before = s[: m.start()]
                    if re_type_kw.search(before) and s.strip().endswith(");"):
                        continue

            api = callee_name
            # Filter: skip if call is in condition_protected line
            _ua_is_protected = False
            if database:
                try:
                    _ua_df_nodes = database.get_data_flow_by_file(relpath)
                    for n in _ua_df_nodes:
                        if (
                            n.get("use_type") == "condition_protected"
                            and n["line"] == idx
                        ):
                            _ua_is_protected = True
                            break
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.checkers.c_checker",
                        function="_rule_unsafe_api",
                    )
                    pass
            if _ua_is_protected:
                continue
            conf = 0.85
            if not _has_len_bound_around(lines, idx, radius=2):
                conf += 0.05
            severity = _severity_from_confidence(conf, "unsafe_api")
            issues.append(
                Issue(
                    language="c/cpp",
                    category="unsafe_api",
                    pattern=api,
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Use of unsafe/high-risk string API may cause buffer overflow or formatting risk.",
                    suggestion="Replace with a bounds-aware safe API (such as snprintf/strlcpy, etc.) or add explicit length checks.",
                    confidence=min(conf, 0.95),
                    severity=severity,
                )
            )
        # AST supplementary detection: unsafe API calls after macro expansion (call_graph only records macro names, not the expanded function names)
        ast_issues = _ast_unsafe_api_check(lines, relpath, issues)
        if ast_issues:
            issues.extend(ast_issues)
        return issues

    # Skip regex fallback when there is no database (to avoid false positives), but still do AST-assisted detection
    ast_issues = _ast_unsafe_api_check(lines, relpath, issues)
    if ast_issues:
        issues.extend(ast_issues)
    return issues


def _ast_unsafe_api_check(
    lines: Sequence[str],
    relpath: str,
    existing_issues: List[Issue],
) -> Optional[List[Issue]]:
    """
    Use tree-sitter AST to supplement detection of unsafe API calls after macro expansion.
    call_graph can only see the macro name (such as SAFE_COPY), not the expanded strcpy.
    This function parses the source AST directly to capture all unsafe function calls.
    """
    try:
        import tree_sitter_c as tsc
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    code = "\n".join(lines)
    if not code.endswith("\n"):
        code += "\n"
    code_bytes = code.encode("utf-8")

    is_cpp = _is_cpp_file(relpath)
    try:
        if is_cpp:
            lang = Language(tscpp.language())
        else:
            lang = Language(tsc.language())
        parser = Parser(lang)
    except Exception:
        return None

    tree = parser.parse(code_bytes)
    root = tree.root_node

    UNSAFE_APIS = {"strcpy", "strcat", "gets", "sprintf", "vsprintf"}
    # Parse #define macros and build a mapping from macro names to unsafe APIs
    macro_to_unsafe: dict[str, str] = {}
    for raw_line in lines:
        m = re.match(r"^\s*#define\s+(\w+)\s*\([^)]*\)\s*(\w+)\s*\(", raw_line)
        if m:
            macro_name = m.group(1)
            real_api = m.group(2).lower()
            if real_api in UNSAFE_APIS:
                macro_to_unsafe[macro_name] = real_api
    # Collect the line numbers of existing issues to avoid duplicate reports
    existing_lines = {issue.line for issue in existing_issues}
    issues: List[Issue] = []

    def _find_unsafe_calls(node):
        if node.type == "call_expression":
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                func_name = code_bytes[
                    func_node.start_byte : func_node.end_byte
                ].decode("utf-8", errors="replace")
                real_api = macro_to_unsafe.get(func_name, func_name)
                if real_api.lower() in UNSAFE_APIS:
                    line_num = node.start_point[0] + 1
                    if line_num not in existing_lines:
                        existing_lines.add(line_num)
                        evidence = code_bytes[node.start_byte : node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        # Only take the first line as evidence
                        evidence_line = evidence.split("\n")[0].strip()
                        conf = 0.75  # AST detection confidence is slightly lower
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="unsafe_api",
                                pattern=real_api,
                                file=relpath,
                                line=line_num,
                                evidence=evidence_line,
                                description="Use of unsafe/high-risk string API may cause buffer overflow or formatting risk.",
                                suggestion="Replace with a bounds-aware safe API (such as snprintf/strlcpy, etc.) or add explicit length checks.",
                                confidence=min(conf, 0.95),
                                severity=_severity_from_confidence(conf, "unsafe_api"),
                            )
                        )
        for child in node.children:
            _find_unsafe_calls(child)

    _find_unsafe_calls(root)
    return issues if issues else None


def _rule_boundary_funcs(
    lines: Sequence[str],
    relpath: str,
    original_lines: Optional[Sequence[str]] = None,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    Detect potentially risky calls to boundary functions (memcpy/memmove/strncpy/strncat).
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    """
    issues: List[Issue] = []
    BOUNDARY_FUNCS = {"memcpy", "memmove", "strncpy", "strncat"}

    # Prefer using database queries
    if database:
        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name.lower() not in BOUNDARY_FUNCS:
                continue
            # Check file path match (match using basename, because the database may store temporary file paths)
            caller_file = call.get("caller_file", "")
            import os

            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            api = callee_name
            # Get the code content from the original line
            if original_lines and 0 < idx <= len(original_lines):
                s = original_lines[idx - 1]
            elif 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                s = ""
            # Build the argument string (for safe-pattern detection)
            args = _extract_call_args(s, api)
            conf = 0.65

            # Safe-pattern detection (sizeof usage)
            safe_sizeof = False
            if api.lower() in ("memcpy", "memmove") and args:
                if (
                    "sizeof" in args
                    and not RE_SIZEOF_PTR.search(args)
                    and not RE_STRLEN_IN_SIZE.search(args)
                ):
                    safe_sizeof = True
            if safe_sizeof:
                continue

            # strncpy/strncat safe-pattern detection
            if api.lower() in ("strncpy", "strncat") and args:
                safe_sizeof_pattern = re.search(
                    r"sizeof\s*\(\s*\w+\s*\)\s*-\s*1",
                    args,
                )
                has_null_term = False
                if safe_sizeof_pattern:
                    check_lines = (
                        original_lines if original_lines is not None else lines
                    )
                    for check_idx in range(idx, min(idx + 3, len(check_lines) + 1)):
                        check_line = check_lines[check_idx - 1]
                        if re.search(
                            r"\w+\s*\[\s*sizeof\s*\(\s*\w+\s*\)\s*-\s*1\s*\]\s*=\s*'\\0'",
                            check_line,
                        ):
                            has_null_term = True
                            break
                if safe_sizeof_pattern and has_null_term:
                    continue

            # Risk escalation
            if args and (RE_STRLEN_IN_SIZE.search(args) or RE_SIZEOF_PTR.search(args)):
                conf += 0.15
            if not _has_len_bound_around(lines, idx, radius=2):
                conf += 0.1

            issues.append(
                Issue(
                    language="c/cpp",
                    category="buffer_overflow",
                    pattern=api,
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="The buffer operation involves length/bounds; confirm whether the length source is reliable to avoid out-of-bounds.",
                    suggestion="Verify the destination buffer size against the copy length; validate external input; prefer safe wrappers.",
                    confidence=min(conf, 0.95),
                    severity=_severity_from_confidence(conf, "buffer_overflow"),
                )
            )
        return issues

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _extract_call_args(line: str, func_name: str) -> str:
    """Extract function call arguments from a code line"""
    try:
        pattern = re.compile(rf"\b{func_name}\s*\(", re.IGNORECASE)
        m = pattern.search(line)
        if not m:
            return ""
        start = line.index("(", m.start())
        end = line.rfind(")")
        if end != -1 and end > start:
            return line[start + 1 : end]
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.c_checker", function="_extract_call_args"
        )
        pass
    return ""


def _ast_realloc_assign_back_check(
    lines: Sequence[str], relpath: str
) -> Optional[List[Issue]]:
    """tree-sitter AST-based detection of realloc return value usage, replacing regex scanning."""
    try:
        import tree_sitter_c as tsc
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    code = "".join(lines)
    if not code.endswith("\n"):
        code += "\n"
    code_bytes = code.encode("utf-8")

    is_cpp = _is_cpp_file(relpath)
    try:
        if is_cpp:
            lang = Language(tscpp.language())
        else:
            lang = Language(tsc.language())
        parser = Parser(lang)
    except Exception:
        return None

    tree = parser.parse(code_bytes)
    root = tree.root_node

    issues: List[Issue] = []

    def _find_realloc_calls(node):
        """Recursively find all realloc call nodes."""
        results = []
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            if (
                func
                and code_bytes[func.start_byte : func.end_byte].decode(
                    "utf-8", errors="replace"
                )
                == "realloc"
            ):
                results.append(node)
        for child in node.children:
            results.extend(_find_realloc_calls(child))
        return results

    realloc_calls = _find_realloc_calls(root)

    for call_node in realloc_calls:
        line_num = call_node.start_point[0] + 1
        evidence = _strip_line(lines[line_num - 1])

        # Extract the first argument of realloc (the original pointer variable name)
        args = call_node.child_by_field_name("arguments")
        first_arg_name = None
        if args:
            for child in args.children:
                if child.type == "identifier":
                    first_arg_name = code_bytes[
                        child.start_byte : child.end_byte
                    ].decode("utf-8", errors="replace")
                    break
                elif child.type in (
                    "pointer_expression",
                    "parenthesized_expression",
                    "cast_expression",
                ):
                    # Recursively find the leftmost identifier
                    inner = child
                    while inner and inner.type != "identifier":
                        ids = [c for c in inner.children if c.type == "identifier"]
                        if ids:
                            inner = ids[0]
                            break
                        inner = inner.children[0] if inner.children else None
                    if inner and inner.type == "identifier":
                        first_arg_name = code_bytes[
                            inner.start_byte : inner.end_byte
                        ].decode("utf-8", errors="replace")
                    break

        # Check whether the realloc call is in the right-hand side of an assignment expression
        parent = call_node.parent
        lhs_var = None
        is_assigned = False

        # cast_expression: (int *)realloc(...) → parent is cast
        if parent and parent.type == "cast_expression":
            parent = parent.parent

        # parenthesized_expression: (realloc(...)) → not common but handled
        while parent and parent.type == "parenthesized_expression":
            parent = parent.parent

        if parent and parent.type == "assignment_expression":
            is_assigned = True
            # Extract the lvalue variable name
            lhs_node = parent.child_by_field_name("left")
            if lhs_node:
                lhs_var = (
                    code_bytes[lhs_node.start_byte : lhs_node.end_byte]
                    .decode("utf-8", errors="replace")
                    .strip()
                )

        # Also check initialization declarations: type *p = realloc(...)
        if parent and parent.type == "init_declarator":
            is_assigned = True
            decl_node = parent.child_by_field_name("declarator")
            if decl_node:
                # Handle nesting such as pointer_declarator
                inner = decl_node
                while inner and inner.type != "identifier":
                    ids = [c for c in inner.children if c.type == "identifier"]
                    if ids:
                        inner = ids[0]
                        break
                    inner = inner.children[0] if inner.children else None
                if inner and inner.type == "identifier":
                    lhs_var = code_bytes[inner.start_byte : inner.end_byte].decode(
                        "utf-8", errors="replace"
                    )

        if not is_assigned:
            # realloc call without assignment, memory leak risk
            var_desc = f"pointer {first_arg_name}" if first_arg_name else "pointer"
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="realloc_assign_back",
                    file=relpath,
                    line=line_num,
                    evidence=evidence,
                    description=f"realloc called but the result is not assigned back to {var_desc}, which may cause a memory leak or use of freed memory.",
                    suggestion="Use a temporary pointer to receive the realloc return value, then assign it back to the original pointer after confirming it is non-null.",
                    confidence=0.75,
                    severity="high",
                )
            )
        elif lhs_var and first_arg_name and lhs_var == first_arg_name:
            # p = realloc(p, ...) directly overwrites the original pointer; if realloc fails, the original memory leaks
            conf = 0.8
            if not _has_null_check_around(lhs_var, lines, line_num, radius=3):
                conf += 0.1
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="realloc_assign_back",
                    file=relpath,
                    line=line_num,
                    evidence=evidence,
                    description=f"realloc directly overwrites the original pointer {lhs_var}; if it fails, the original memory leaks.",
                    suggestion="Use a temporary pointer to receive the realloc return value, then assign it back to the original pointer after confirming it is non-null.",
                    confidence=min(conf, 0.95),
                    severity=_severity_from_confidence(conf, "memory_mgmt"),
                )
            )
        # else: tmp = realloc(p, ...) receives with a temporary variable; this is the safe pattern and is not reported

    return issues


def _rule_realloc_assign_back(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where the realloc return value is not used (taint analysis + heuristic fallback).
    - Prefer taint analysis to detect whether the realloc return value is used
    - If taint analysis is unavailable, fall back to heuristic detection
    """
    issues: List[Issue] = []

    # Try using taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["realloc_assign_back"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to an Issue
    if taint_paths:
        for path in taint_paths:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="realloc_assign_back_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or "realloc return value not used",
                    description=path.description
                    or "the realloc return value is not assigned back to the original pointer, which may cause a memory leak or use of freed memory",
                    suggestion="Use a temporary pointer to receive the realloc return value, then assign it back to the original pointer after confirming it is non-null",
                    confidence=path.confidence,
                    severity="high",
                )
            )
        return issues

    # Taint analysis has no results; use tree-sitter AST detection
    ast_issues = _ast_realloc_assign_back_check(lines, relpath)
    if ast_issues is not None:
        issues.extend(ast_issues)
        return issues

    # Final fallback when tree-sitter is unavailable: regex heuristics
    realloc_call_pattern = re.compile(
        r"realloc\s*\(\s*([A-Za-z_]\w*)\s*,", re.IGNORECASE
    )
    for idx, s in enumerate(lines, start=1):
        m = realloc_call_pattern.search(s)
        if m:
            var = m.group(1)
            has_assign = False
            if "=" in s:
                assign_match = re.search(
                    rf"\b{re.escape(var)}\s*=\s*realloc", s, re.IGNORECASE
                )
                if assign_match:
                    has_assign = True
                else:
                    tmp_assign_match = re.search(
                        r"\b([A-Za-z_]\w*)\s*=\s*realloc", s, re.IGNORECASE
                    )
                    if tmp_assign_match:
                        has_assign = True

            if not has_assign:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="realloc_assign_back",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"realloc called but the result is not assigned back to pointer {var}, which may cause a memory leak or use of freed memory.",
                        suggestion="Use a temporary pointer to receive the realloc return value, then assign it back to the original pointer after confirming it is non-null.",
                        confidence=0.75,
                        severity="high",
                    )
                )

        m2 = RE_REALLOC_ASSIGN_BACK.search(s)
        if m2:
            var = m2.group(1)
            conf = 0.8
            if not _has_null_check_around(var, lines, idx, radius=3):
                conf += 0.1
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="realloc_assign_back",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"realloc directly overwrites the original pointer {var}; if it fails, the original memory leaks.",
                    suggestion="Use a temporary pointer to receive the realloc return value, then assign it back to the original pointer after confirming it is non-null.",
                    confidence=min(conf, 0.95),
                    severity=_severity_from_confidence(conf, "memory_mgmt"),
                )
            )
    return issues


def _rule_malloc_no_null_check(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where NULL is not checked after memory allocation.
    Note: prefer querying the database for null_checks; fall back to the heuristic implementation on failure.
    """
    issues: List[Issue] = []

    # Skip very short functions (usually sample code)
    # If a function has fewer than 10 lines, it may be test or sample code
    if len(lines) < 10:
        return issues

    # Prefer trying database-driven detection
    if database:
        try:
            from haijunbot.haijunbot_sec.data_flow_analyzer import DataFlowAnalyzer

            analyzer = DataFlowAnalyzer(database)
            code = "\n".join(lines)
            result = analyzer.analyze_code(
                code, is_cpp=False, database=database, file_path=relpath
            )

            if result and result.null_checks is not None:
                # Get the allocation point from pointer_states
                if result.pointer_states:
                    for var_name, state in result.pointer_states.items():
                        if state.state == "ALLOCATED" and state.line:
                            # Check whether there is a null_check
                            has_check = var_name in result.null_checks
                            if not has_check:
                                issues.append(
                                    Issue(
                                        language="c/cpp",
                                        category="memory_mgmt",
                                        pattern="alloc_no_null_check",
                                        file=relpath,
                                        line=state.line,
                                        evidence=_strip_line(lines[state.line - 1])
                                        if state.line <= len(lines)
                                        else "",
                                        description=f"After memory is allocated to {var_name}, success is not checked (missing NULL check).",
                                        suggestion="Check whether the allocation result is NULL before use, and release already-acquired resources on the error path.",
                                        confidence=0.85,
                                        severity="high",
                                    )
                                )
                if issues:
                    return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_malloc_no_null_check",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_function_return_ptr_no_check(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where a function-returned pointer is used directly without a NULL check.
    Note: prefer querying the database for null_checks; fall back to the heuristic implementation on failure.
    """
    issues: List[Issue] = []

    # Prefer trying database-driven detection
    if database:
        try:
            from haijunbot.haijunbot_sec.data_flow_analyzer import DataFlowAnalyzer

            analyzer = DataFlowAnalyzer(database)
            code = "\n".join(lines)
            result = analyzer.analyze_code(
                code, is_cpp=False, database=database, file_path=relpath
            )

            if result and result.null_checks is not None:
                # Get the assignment point of the function-returned pointer from pointer_states
                if result.pointer_states:
                    for var_name, state in result.pointer_states.items():
                        # Check whether it comes from a function return (not ALLOCATED but has a value)
                        if state.line and state.state == "UNKNOWN":
                            # Skip functions that cannot return NULL
                            line_text = (
                                lines[state.line - 1]
                                if state.line <= len(lines)
                                else ""
                            )
                            # Smart pointers (cannot return NULL)
                            if re.search(
                                r"\b(make_unique|make_shared|make_unique_for_overwrite)\s*<",
                                line_text,
                            ):
                                continue
                            # Non-pointer-returning functions (open returns int, time returns time_t, etc.)
                            if re.search(
                                r"\b(open|close|read|write|time|clock|strlen|strcmp|strncmp|strtok_r?)\s*\(",
                                line_text,
                            ):
                                continue
                            # Return value assigned to a non-pointer type (int fd = open(...))
                            if re.search(
                                r"\b(int|long|short|unsigned|size_t|ssize_t|time_t|clock_t|BOOL|bool)\s+"
                                + re.escape(var_name)
                                + r"\s*=",
                                line_text,
                            ):
                                continue
                            # Check whether there is a null_check
                            has_check = var_name in result.null_checks
                            # Check whether it is within a condition_protected line
                            if not has_check and database:
                                try:
                                    df_nodes = database.get_data_flow_by_file(relpath)
                                    for n in df_nodes:
                                        if (
                                            n.get("use_type") == "condition_protected"
                                            and n["line"] == state.line
                                        ):
                                            has_check = True
                                            break
                                except Exception as e:
                                    save_exception(
                                        e,
                                        module="haijunbot_sec.checkers.c_checker",
                                        function="_rule_function_return_ptr_no_check",
                                    )
                                    pass
                            if not has_check:
                                # Second confirmation: use regex to check whether a NULL check is nearby
                                if _has_null_check_around(
                                    var_name, lines, state.line, radius=5
                                ):
                                    has_check = True
                            if not has_check:
                                issues.append(
                                    Issue(
                                        language="c/cpp",
                                        category="memory_mgmt",
                                        pattern="function_return_ptr_no_check",
                                        file=relpath,
                                        line=state.line,
                                        evidence=_strip_line(lines[state.line - 1])
                                        if state.line <= len(lines)
                                        else "",
                                        description=f"The pointer returned by the function is assigned to {var_name} without checking whether it is NULL.",
                                        suggestion="Check whether the function-returned pointer is NULL before use; ensure all possible return paths are validated.",
                                        confidence=0.75,
                                        severity="medium",
                                    )
                                )
                if issues:
                    return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_function_return_ptr_no_check",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


# Global deduplication set for cross-file UAF detection (to avoid duplicate reports during multi-file analysis)
_cross_file_uaf_seen: set[Tuple[str, int]] = set()

# Global deduplication set for cross-file Double Free detection
_cross_file_double_free_seen: set[Tuple[str, int]] = set()


def _detect_cross_file_double_free(
    database: "ProjectDatabase", relpath: str, lines: Sequence[str]
) -> List[Issue]:
    """
    Cross-file Double Free detection: based on call order

    Core principle:
    From the caller's perspective, calling free_wrapper1 first and then free_wrapper2 = Double Free.
    Does not rely on variable name matching, only on the call order in call_graph.

    Detection logic:
    1. Query all pointers in FREED state in pointer_states to get the free function name (scope)
    2. In call_graph, find who called the free function (caller)
    3. Within the same caller, find other free calls after the line number of the free call
    4. Deduplicate and generate an Issue

    Args:
        database: project database instance
        relpath: relative path of the current file
        lines: list of source code lines

    Returns:
        List of detected cross-file Double Free issues
    """
    global _cross_file_double_free_seen
    issues: List[Issue] = []

    try:
        import sqlite3

        conn = sqlite3.connect(database.db_path)
        cursor = conn.cursor()

        # Step 1: Query all pointers in FREED state to get the free function name (scope)
        cursor.execute("""
            SELECT var_name, file_path, line, scope, deallocator
            FROM pointer_states
            WHERE state = 'FREED'
        """)
        freed_pointers = cursor.fetchall()

        # Step 2: Collect all free function names
        free_scopes = set()
        for (
            freed_var,
            freed_file,
            freed_line,
            freed_scope,
            deallocator,
        ) in freed_pointers:
            if freed_scope != "global":
                free_scopes.add(freed_scope)

        # Step 3: For each free function, find callers, then find consecutive free function calls in the callers
        for free_scope in free_scopes:
            # Find who called this free function
            cursor.execute(
                """
                SELECT caller_name, caller_file, caller_line
                FROM call_graph
                WHERE callee_name = ? AND caller_name != 'unknown'
            """,
                (free_scope,),
            )
            callers = cursor.fetchall()

            # Step 4: In each caller, check whether there are multiple free function calls
            for caller_name, caller_file, caller_line in callers:
                # Find all calls in the caller
                cursor.execute(
                    """
                    SELECT callee_name, caller_line
                    FROM call_graph
                    WHERE caller_name = ? AND caller_file = ?
                    ORDER BY caller_line
                """,
                    (caller_name, caller_file),
                )
                all_calls = cursor.fetchall()

                # Find all free function calls
                free_calls_in_caller = [
                    (callee, line)
                    for callee, line in all_calls
                    if callee in free_scopes
                ]

                # If there are multiple free function calls, report Double Free
                if len(free_calls_in_caller) >= 2:
                    for i in range(len(free_calls_in_caller) - 1):
                        first_free, first_line = free_calls_in_caller[i]
                        second_free, second_line = free_calls_in_caller[i + 1]

                        # Deduplication check
                        dedup_key = (caller_file, second_line)
                        if dedup_key in _cross_file_double_free_seen:
                            continue
                        _cross_file_double_free_seen.add(dedup_key)

                        # Generate Issue
                        try:
                            from pathlib import PurePath

                            caller_file_rel = str(
                                PurePath(caller_file).relative_to(
                                    PurePath(str(database.project_path))
                                )
                            )
                        except ValueError:
                            caller_file_rel = caller_file.split("/")[-1]

                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="memory_mgmt",
                                pattern="double_free",
                                file=caller_file_rel,
                                line=second_line,
                                evidence=f"Cross-file Double Free: in {caller_file}, consecutively calling free functions {first_free} (line {first_line}) and {second_free} (line {second_line})",
                                description=f"Double free risk detected: {caller_name} first calls {first_free}, then calls {second_free}, which may cause Double Free.",
                                suggestion="Set the pointer to NULL after free; ensure each block of memory is freed only once; clarify ownership and free paths.",
                                confidence=0.85,
                                severity="high",
                            )
                        )

        conn.close()
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.c_checker",
            function="_detect_cross_file_double_free",
        )
        pass

    return issues


def _detect_cross_file_uaf(
    database: "ProjectDatabase", relpath: str, lines: Sequence[str]
) -> List[Issue]:
    """
    Cross-file UAF detection: based on call order rather than variable name matching

    Core principle:
    From the caller's perspective, calling free_wrapper first and then use_wrapper = UAF.
    Does not depend on variable name matching, only on the call order in call_graph.

    Detection logic:
    1. Query all pointers with FREED state in pointer_states to get the free function name (scope)
    2. Find who called the free function (caller) in call_graph
    3. In the same caller, find all calls after the free call line number
    4. Deduplicate and generate Issue

    Args:
        database: project database instance
        relpath: relative path of the current file
        lines: list of source code lines

    Returns:
        List of detected cross-file UAF issues
    """
    global _cross_file_uaf_seen
    issues: List[Issue] = []

    try:
        import sqlite3

        conn = sqlite3.connect(database.db_path)
        cursor = conn.cursor()

        # Step 1: Query all pointers with FREED state to get the free function name (scope)
        cursor.execute("""
            SELECT var_name, file_path, line, scope, deallocator
            FROM pointer_states
            WHERE state = 'FREED'
        """)
        freed_pointers = cursor.fetchall()

        # Step 2: For each freed pointer, trace the call chain
        for (
            freed_var,
            freed_file,
            freed_line,
            freed_scope,
            deallocator,
        ) in freed_pointers:
            # Skip global scope (not a free inside a function)
            if freed_scope == "global":
                continue

            # Step 3: Find who called the free function in call_graph
            cursor.execute(
                """
                SELECT caller_name, caller_file, caller_line
                FROM call_graph
                WHERE callee_name = ? AND caller_name != 'unknown'
            """,
                (freed_scope,),
            )
            callers = cursor.fetchall()

            # Step 4: In each caller, find calls after the free call
            for caller_name, caller_file, caller_line in callers:
                cursor.execute(
                    """
                    SELECT callee_name, caller_line
                    FROM call_graph
                    WHERE caller_name = ? AND caller_file = ? AND caller_line > ?
                """,
                    (caller_name, caller_file, caller_line),
                )
                post_free_calls = cursor.fetchall()

                # Step 5: Calls after free are UAF risks (based on call order, not dependent on variable names)
                for callee_name, call_line in post_free_calls:
                    # Deduplication check (using a global set)
                    dedup_key = (caller_file, call_line)
                    if dedup_key in _cross_file_uaf_seen:
                        continue
                    _cross_file_uaf_seen.add(dedup_key)

                    # Generate Issue (using relative path)
                    try:
                        from pathlib import PurePath

                        caller_file_rel = str(
                            PurePath(caller_file).relative_to(
                                PurePath(str(database.project_path))
                            )
                        )
                    except ValueError:
                        caller_file_rel = caller_file.split("/")[-1]

                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="use_after_free_suspect",
                            file=caller_file_rel,
                            line=call_line,
                            evidence=f"Cross-file UAF: in {caller_file}:{caller_line}, after calling free function {freed_scope}, called {callee_name} at line {call_line}",
                            description=f"Use-after-free risk detected: {caller_name} first calls {freed_scope} to free memory, then calls {callee_name}, which may use already-freed memory.",
                            suggestion="After free, the pointer should be set to NULL, and any dereference before reassignment should be avoided; it is recommended to introduce lifecycle management and dynamic/static detection.",
                            confidence=0.8,
                            severity="high",
                        )
                    )

                # Step 6: Detect variable use after the free call in the same caller (query by scope, not by variable name)
                # Find all use nodes after the free call line number in the caller
                cursor.execute(
                    """
                    SELECT var_name, file_path, line
                    FROM data_flow
                    WHERE scope = ? AND node_type = 'use' AND line > ?
                """,
                    (caller_name, caller_line),
                )
                post_free_uses = cursor.fetchall()

                for use_var, use_file, use_line in post_free_uses:
                    # Deduplication check
                    dedup_key = (use_file, use_line)
                    if dedup_key in _cross_file_uaf_seen:
                        continue
                    _cross_file_uaf_seen.add(dedup_key)

                    # Generate Issue
                    try:
                        from pathlib import PurePath

                        use_file_rel = str(
                            PurePath(use_file).relative_to(
                                PurePath(str(database.project_path))
                            )
                        )
                    except ValueError:
                        use_file_rel = use_file.split("/")[-1]

                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="use_after_free_suspect",
                            file=use_file_rel,
                            line=use_line,
                            evidence=f"Cross-function UAF: in {caller_file}:{caller_line}, after calling free function {freed_scope}, variable {use_var} is used at line {use_line}",
                            description=f"Use-after-free risk detected: after {caller_name} calls {freed_scope} to free memory, variable {use_var} is still used.",
                            suggestion="After free, the pointer should be set to NULL, and any dereference before reassignment should be avoided; it is recommended to introduce lifecycle management and dynamic/static detection.",
                            confidence=0.75,
                            severity="high",
                        )
                    )

        conn.close()
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.c_checker", function="_detect_cross_file_uaf"
        )
        pass

    return issues


def _rule_uaf_suspect(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    UAF (use-after-free) detection (taint analysis + heuristic fallback + cross-file analysis):
    - Prefer taint analysis to detect the taint propagation path of free -> dereference
    - If taint analysis is unavailable, fall back to heuristic detection
    - Heuristic: only warn when an obvious "dereference use" (v->, *v, v[...]) is detected within the window after free(var) and no reassignment/null-setting is seen before that
    - Ignore the case where the pointer is immediately set to NULL/0 after free
    - Cross-file analysis: use the database to trace pointer states and detect cross-file UAF risks
    """
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code,
        rules=["use_after_free", "double_free"],
        file_path=relpath,
        database=database,
    )

    # If taint analysis has results, convert them to Issues
    if taint_paths:
        for path in taint_paths:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="use_after_free_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or f"{path.source} -> {path.sink}",
                    description=path.description
                    or f"Taint analysis detected UAF risk: {path.source} -> {path.sink}",
                    suggestion="After free, the pointer should be set to NULL, and any dereference before reassignment should be avoided; it is recommended to introduce lifecycle management and dynamic/static detection.",
                    confidence=path.confidence,
                    severity="critical"
                    if path.severity.value == "critical"
                    else "high",
                )
            )
        return issues

    # Taint analysis has no results, fall back to heuristic detection
    # Collect all free(var) locations
    free_calls: List[Tuple[str, int]] = []
    for idx, s in enumerate(lines, start=1):
        for m in re.finditer(r"free\s*\(\s*([A-Za-z_]\w*)\s*\)\s*;", s):
            free_calls.append((m.group(1), idx))

    # For each free(var), look for "dangerous use" in the subsequent window
    for var, free_ln in free_calls:
        # 50-line window after free
        start = free_ln + 1
        end = min(len(lines), free_ln + 50)

        # Note: no longer skip the case of setting NULL after free
        # Because even if set to NULL, subsequent code may still use it through an alias or without checking NULL
        # For example: free(ptr); ptr = NULL; char *p = ptr; if (p) strcpy(p, "test");
        # In this case, ptr has been set to NULL, but the alias p may still be misused

        reassigned = False
        uaf_evidence_line: Optional[int] = None

        deref_arrow = re.compile(rf"\b{re.escape(var)}\s*->")
        deref_star = re.compile(rf"(?<!\w)\*\s*{re.escape(var)}\b")
        deref_index = re.compile(rf"\b{re.escape(var)}\s*\[")
        # Detect passing as a function argument (may cause UAF)
        func_param = re.compile(
            rf"\b(printf|fprintf|sprintf|snprintf|strcpy|strcat|memcpy|memmove|strlen|strcmp|strchr|strstr|gets|fgets|fputs|puts|scanf|fscanf|sscanf)\s*\([^)]*\b{re.escape(var)}\b"
        )
        assign_pat = re.compile(rf"\b{re.escape(var)}\s*=")

        for j in range(start, end + 1):
            sj = _safe_line(lines, j)
            # First detect reassignment (including setting NULL or re-pointing); if present, treat it as a "lifecycle reset" and do not report this item
            if assign_pat.search(sj):
                reassigned = True
                break
            # Detect obvious dereference use
            if (
                deref_arrow.search(sj)
                or deref_star.search(sj)
                or deref_index.search(sj)
                or func_param.search(sj)  # Detect passing as a function argument
            ):
                uaf_evidence_line = j
                break

        if uaf_evidence_line and not reassigned:
            # Use the free line as the evidence point (to stay consistent with existing output)
            evidence = _strip_line(_safe_line(lines, free_ln))
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="use_after_free_suspect",
                    file=relpath,
                    line=free_ln,
                    evidence=evidence,
                    description=f"Variable {var} has a dereference use in the nearby window after free (UAF clue), and no reassignment/null-setting was detected.",
                    suggestion="After free, the pointer should be set to NULL, and any dereference before reassignment should be avoided; it is recommended to introduce lifecycle management and dynamic/static detection.",
                    confidence=0.65,
                )
            )

    # Cross-file UAF detection: use the database to trace pointer states
    if database is not None:
        cross_file_issues = _detect_cross_file_uaf(database, relpath, lines)
        issues.extend(cross_file_issues)

    return issues


def _rule_unchecked_io(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect unchecked IO return values (taint analysis + heuristic fallback).
    - Prefer taint analysis to detect whether the IO return value is checked
    - If taint analysis is unavailable, fall back to heuristic detection
    """
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["unchecked_io"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to Issues (but first filter out calls within condition protection)
    if taint_paths:
        # Query the condition_protected line number set from the database, used to filter false positives
        protected_lines: set[int] = set()
        if database:
            try:
                df_nodes = database.get_data_flow_by_file(relpath)
                for n in df_nodes:
                    if n.get("use_type") == "condition_protected":
                        protected_lines.add(n["line"])
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.checkers.c_checker",
                    function="_rule_unchecked_io",
                )
                pass

        # Query the value_check variable set from the database, used to filter IO calls protected by value checks
        value_checked_vars: set[str] = set()
        df_nodes = []
        if database:
            try:
                df_nodes = database.get_data_flow_by_file(relpath)
                for n in df_nodes:
                    if n.get("use_type") == "value_check":
                        value_checked_vars.add(n["var_name"])
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.checkers.c_checker",
                    function="_rule_unchecked_io",
                )
                pass

        for path in taint_paths:
            # Filter: if the IO call is within a condition_protected line, skip
            if path.line_number in protected_lines:
                continue
            # Filter: if the variable used by the IO call has a value_check, skip
            # (e.g. fd in read(fd,...) has value_check(fd >= 0))
            if value_checked_vars and path.code_snippet:
                for var in value_checked_vars:
                    if re.search(rf"\b{re.escape(var)}\b", path.code_snippet):
                        # Also need to confirm the value_check is before the IO call
                        try:
                            vc_nodes = [
                                n
                                for n in df_nodes
                                if n.get("use_type") == "value_check"
                                and n["var_name"] == var
                            ]
                            for vc in vc_nodes:
                                if vc["line"] < path.line_number:
                                    protected_lines.add(path.line_number)
                                    break
                        except Exception as e:
                            save_exception(
                                e,
                                module="haijunbot_sec.checkers.c_checker",
                                function="_rule_unchecked_io",
                            )
                            pass
            if path.line_number in protected_lines:
                continue

            issues.append(
                Issue(
                    language="c/cpp",
                    category="error_handling",
                    pattern="unchecked_io_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or "IO return value unchecked",
                    description=path.description
                    or "IO function return value unchecked, may lead to missing error handling",
                    suggestion="Check the return value/errno; release resources on the error path",
                    confidence=path.confidence,
                    severity="medium",
                )
            )
        if issues:
            return issues

    # Taint analysis has no results, fall back to heuristic detection
    # Pre-collect the condition_protected line number set, used to filter false positives
    _protected_lines_regex: set[int] = set()
    if database:
        try:
            _df_nodes_regex = database.get_data_flow_by_file(relpath)
            for n in _df_nodes_regex:
                if n.get("use_type") == "condition_protected":
                    _protected_lines_regex.add(n["line"])
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.checkers.c_checker", function="_rule_unchecked_io"
            )
            pass
    for idx, s in enumerate(lines, start=1):
        # Exclude preprocessing and declarations
        t = s.lstrip()
        if t.startswith("#") or re.search(r"\b(typedef|extern)\b", s):
            continue

        # Detect IO/permission/network function calls
        m = RE_IO_API.search(s)
        api_type = "io"
        if not m:
            m = RE_PRIV_API.search(s)
            api_type = "privilege"
        if not m:
            m = RE_NET_API.search(s)
            api_type = "network"
        if not m:
            continue

        # Filter: if the IO call is within a condition_protected line, skip
        if idx in _protected_lines_regex:
            continue

        # Exclude IO calls wrapped by error-handling macros/functions (e.g. RETRY_IF_EINTR(write(...)))
        # Pattern: MACRO_NAME(io_func(...)), the macro already handles the return value
        if re.search(
            r"\b[A-Z][A-Z0-9_]*\s*\(\s*"
            + re.escape(m.group(0).split("(")[0])
            + r"\s*\(",
            s,
        ):
            continue

        # If a condition judgment appears on this line or the following 2 lines, consider it checked (skip directly)
        nearby = " ".join(
            _safe_line(lines, i) for i in range(idx, min(idx + 2, len(lines)) + 1)
        )
        if re.search(r"\b(if|while|for)\s*\(", nearby) or re.search(
            r"(>=|<=|==|!=|<|>)", nearby
        ):
            continue

        # If assigned to a variable, look for a check of that variable in the subsequent window
        assigned_var: Optional[str] = None
        try:
            # Only take the left side before the call to match the nearest "var ="
            left = s[: m.start()]
            assigns = list(RE_GENERIC_ASSIGN.finditer(left))
            if assigns:
                assigned_var = assigns[-1].group(1)
        except Exception:
            assigned_var = None

        checked_via_var = False
        if assigned_var:
            end = min(len(lines), idx + 5)
            var_pat_cond = re.compile(
                rf"\b(if|while|for)\s*\([^)]*\b{re.escape(assigned_var)}\b[^)]*\)"
            )
            var_pat_cmp = re.compile(
                rf"\b{re.escape(assigned_var)}\b\s*(>=|<=|==|!=|<|>)"
            )
            for j in range(idx + 1, end + 1):
                sj = _safe_line(lines, j)
                if var_pat_cond.search(sj) or var_pat_cmp.search(sj):
                    checked_via_var = True
                    break
        if checked_via_var:
            continue

        # No check seen so far, consider it may be unchecked for errors
        conf = 0.65  # Slightly raised the base confidence compared to before, since more exclusions have been done

        # Set different descriptions and suggestions based on the API type
        if api_type == "privilege":
            description = (
                "Permission operation functions may not check the return value, which may cause permission setting failure while the program continues to run."
            )
            suggestion = "Check whether the return value is 0 (success); on failure, terminate the program or take recovery measures."
            pattern = "unchecked_privilege_op"
            conf = 0.80  # Permission operations are more important, raise the confidence
        elif api_type == "network":
            description = "Network IO functions may not check the return value, which may cause connection failure or data loss."
            suggestion = (
                "Check the return value (recv/send returns the number of bytes or -1); handle partial sends and connection errors."
            )
            pattern = "unchecked_network_io"
            conf = 0.75
        else:
            description = "I/O/system calls may not check the return value, and there is a risk of missing error handling."
            suggestion = "Check the return value/errno; release resources (handles/memory/locks) on the error path."
            pattern = "io_call"

        issues.append(
            Issue(
                language="c/cpp",
                category="error_handling",
                pattern=pattern,
                file=relpath,
                line=idx,
                evidence=_strip_line(s),
                description=description,
                suggestion=suggestion,
                confidence=min(conf, 0.85),
                severity=_severity_from_confidence(conf, "error_handling"),
            )
        )
    return issues


def _rule_strncpy_no_nullterm(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect the common pitfall of not ensuring the destination buffer is NUL-terminated after strncpy/strncat.
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    """
    issues: List[Issue] = []
    STRNCPY_FUNCS = {"strncpy", "strncat"}

    # Prefer to use the database query
    if database:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name.lower() not in STRNCPY_FUNCS:
                continue
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            if 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                continue

            # Check whether it is within a condition_protected line (a call under if-condition protection does not count as a problem)
            is_condition_protected = False
            if database:
                try:
                    df_nodes = database.get_data_flow_by_file(relpath)
                    for n in df_nodes:
                        if (
                            n.get("use_type") == "condition_protected"
                            and n["line"] == idx
                        ):
                            is_condition_protected = True
                            break
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_sec.checkers.c_checker",
                        function="_rule_strncpy_no_nullterm",
                    )
                    pass
            if is_condition_protected:
                continue
            # Check whether it is a safe strncpy usage
            safe_sizeof_pattern = re.search(r"sizeof\s*\(\s*\w+\s*\)\s*-\s*1", s)
            window_text = " ".join(t for _, t in _window(lines, idx, before=1, after=3))
            # CWE-170 false positive filter: check whether subsequent lines have an explicit NULL termination
            has_null_term = re.search(
                r"\w+\s*\[\s*(?:sizeof\s*\(\s*\w+\s*\)\s*-\s*1|\w+\s*-\s*1)\s*\]\s*=\s*'\\0'",
                window_text,
            ) or re.search(
                r"\w+\s*\[\s*\w+\s*-\s*1\s*\]\s*=\s*0",
                window_text,
            )
            if safe_sizeof_pattern and has_null_term:
                continue
            # Even if there is no sizeof-1 pattern, skip as long as there is an explicit NULL termination
            if has_null_term:
                continue

            conf = 0.55
            if not re.search(
                r"\\0|'\\0'|\"\\0\"|len\s*-\s*1|sizeof\s*\(\s*\w+\s*\)\s*-\s*1",
                window_text,
            ):
                conf += 0.15
            issues.append(
                Issue(
                    language="c/cpp",
                    category="buffer_overflow",
                    pattern="strncpy/strncat",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using strncpy/strncat may not automatically add NUL termination, leading to a potential unterminated string risk.",
                    suggestion="Ensure the destination buffer is terminated with '\0' (e.g. manual termination or use of a safer API).",
                    confidence=min(conf, 0.75),
                    severity=_severity_from_confidence(conf, "buffer_overflow"),
                )
            )
        return issues

    # Skip the regex fallback when there is no database (to avoid false positives)
    return issues


# ---------------------------
# External main entry point
# ---------------------------

# ---------------------------
# Additional rules (newly added)
# ---------------------------


def _rule_format_string(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect format string vulnerabilities: the format argument of printf/sprintf/snprintf/vsprintf/vsnprintf is not a literal;
    the second argument of fprintf is not a literal.
    Accuracy optimization:
    - Allow common localization/wrapper macros that wrap literals as the format argument (e.g. _("..."), gettext("..."), tr("..."), QT_TR_NOOP("..."))
    - If the argument is a variable name, look back several lines; if the variable is assigned a literal string, consider it a safer usage (skip)
    - For different functions, accurately locate the argument position of the "format string":
      printf: 1st arg; sprintf/vsprintf: 2nd arg; snprintf/vsnprintf: 3rd arg; fprintf: 2nd arg
    """
    SAFE_WRAPPERS = (
        "_",
        "gettext",
        "dgettext",
        "ngettext",
        "tr",
        "QT_TR_NOOP",
        "QT_TRANSLATE_NOOP",
    )
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["format_string"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to Issues
    if taint_paths:
        for path in taint_paths:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="unsafe_usage",
                    pattern="format_string_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or f"{path.source} -> {path.sink}",
                    description=path.description
                    or f"Taint analysis detected format string risk: {path.source} -> {path.sink}",
                    suggestion="Use a constant format string and parameterize external input; avoid using unvalidated input as a format string.",
                    confidence=path.confidence,
                    severity="high",
                )
            )
        return issues

    # Taint analysis has no results, fall back to heuristic detection

    def _arg_is_literal(s: str, j: int) -> bool:
        while j < len(s) and s[j].isspace():
            j += 1
        return j < len(s) and s[j] == '"'

    def _arg_is_wrapper_literal(s: str, j: int) -> bool:
        k = j
        while k < len(s) and (s[k].isalnum() or s[k] == "_"):
            k += 1
        name = s[j:k]
        p = k
        while p < len(s) and s[p].isspace():
            p += 1
        if name in SAFE_WRAPPERS and p < len(s) and s[p] == "(":
            q = p + 1
            while q < len(s) and s[q].isspace():
                q += 1
            return q < len(s) and s[q] == '"'
        return False

    def _leading_ident(s: str, j: int) -> Optional[str]:
        k = j
        if k < len(s) and (s[k].isalpha() or s[k] == "_"):
            while k < len(s) and (s[k].isalnum() or s[k] == "_"):
                k += 1
            return s[j:k]
        return None

    def _var_assigned_literal(
        var: str, lines: Sequence[str], upto_idx: int, lookback: int = 5
    ) -> bool:
        start = max(1, upto_idx - lookback)
        pat_assign = re.compile(rf"\b{re.escape(var)}\s*=\s*")
        literal_line = None
        for j in range(start, upto_idx):
            sj = _safe_line(lines, j)
            m = pat_assign.search(sj)
            if not m:
                continue
            k = m.end()
            while k < len(sj) and sj[k].isspace():
                k += 1
            if k < len(sj) and sj[k] == '"':
                literal_line = j
                break
        if literal_line is None:
            return False
        # Check whether there is another assignment that overwrites the same variable after the literal assignment
        for j in range(literal_line + 1, upto_idx):
            sj = _safe_line(lines, j)
            if pat_assign.search(sj):
                return False  # There is an overwriting assignment, not safe
        return True

    def _nth_arg_start(s: str, open_paren_idx: int, n: int) -> Optional[int]:
        """
        Return the starting index of the n-th argument (the first non-whitespace character), or None on failure.
        Only perform bracket matching and comma counting within a single line (heuristic).
        """
        depth = 0
        # Start after '('
        i = open_paren_idx + 1
        # Skip to the first argument
        # If the 1st argument is needed, locate its start first
        # Unified logic: iterate, recording the start position of each argument
        starts: List[int] = []
        start_pos = None
        while i < len(s):
            ch = s[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                if depth == 0:
                    # End
                    if start_pos is not None:
                        starts.append(start_pos)
                        start_pos = None
                    break
                depth -= 1
            elif ch == "," and depth == 0:
                # Argument separator
                if start_pos is None:
                    # Empty argument, record the current position (possibly a macro expansion), try to return for subsequent judgment
                    starts.append(i + 1)
                else:
                    starts.append(start_pos)
                    start_pos = None
                # Next argument
            else:
                if not start_pos and not ch.isspace():
                    start_pos = i
            i += 1
        # Append the start of the last argument
        if start_pos is not None:
            starts.append(start_pos)
        # Remove the leading whitespace of the argument start
        cleaned: List[int] = []
        for pos in starts:
            j = pos
            while j < len(s) and s[j].isspace():
                j += 1
            cleaned.append(j)
        if 1 <= n <= len(cleaned):
            return cleaned[n - 1]
        return None

    for idx, s in enumerate(lines, start=1):
        flagged = False
        # Handle printf/sprintf/snprintf/vsprintf/vsnprintf (format string argument positions differ)
        m1 = RE_PRINTF_LIKE.search(s)
        if m1:
            try:
                name = m1.group(1).lower()
                open_idx = s.index("(", m1.start())
                # Argument index mapping
                fmt_arg_map = {
                    "printf": 1,
                    "sprintf": 2,
                    "vsprintf": 2,
                    "snprintf": 3,
                    "vsnprintf": 3,
                    "syslog": 2,  # False negative fix: syslog format string is the 2nd argument
                    "vsyslog": 2,  # False negative fix: vsyslog format string is the 2nd argument
                    "err": 2,  # False negative fix: err format string is the 2nd argument
                    "errx": 2,  # False negative fix: errx format string is the 2nd argument
                    "warn": 2,  # False negative fix: warn format string is the 2nd argument
                    "warnx": 2,  # False negative fix: warnx format string is the 2nd argument
                }
                fmt_idx = fmt_arg_map.get(name, 1)
                j = _nth_arg_start(s, open_idx, fmt_idx)
                if j is not None:
                    # Variables assigned literals/wrapped literals/lookback literals
                    if not _arg_is_literal(s, j):
                        if s[j].isalpha() or s[j] == "_":
                            if _arg_is_wrapper_literal(s, j):
                                flagged = False
                            else:
                                ident = _leading_ident(s, j)
                                if ident and _var_assigned_literal(
                                    ident, lines, idx, lookback=5
                                ):
                                    flagged = False
                                else:
                                    flagged = True
                        else:
                            flagged = True
                else:
                    # Cannot resolve argument position, conservatively warn
                    flagged = True
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.checkers.c_checker", function="_nth_arg_start"
                )
                pass

        # fprintf: the second argument is the format string
        m2 = RE_FPRINTF.search(s)
        if not flagged and m2:
            try:
                open_idx = s.index("(", m2.start())
                j = _nth_arg_start(s, open_idx, 2)
                if j is not None:
                    if not _arg_is_literal(s, j):
                        if s[j].isalpha() or s[j] == "_":
                            if _arg_is_wrapper_literal(s, j):
                                flagged = False
                            else:
                                ident = _leading_ident(s, j)
                                if ident and _var_assigned_literal(
                                    ident, lines, idx, lookback=5
                                ):
                                    flagged = False
                                else:
                                    flagged = True
                        else:
                            flagged = True
                else:
                    flagged = True
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.checkers.c_checker", function="_nth_arg_start"
                )
                pass

        if flagged:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="unsafe_usage",
                    pattern="format_string",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="The format string argument is not a literal, which may lead to a format string vulnerability.",
                    suggestion="Use a constant format string and parameterize external input; avoid using unvalidated input as a format string.",
                    confidence=0.8,
                    severity="high",
                )
            )
    return issues


def _rule_insecure_tmpfile(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect insecure temporary file APIs: tmpnam/tempnam/mktemp
    Note: Prefer database query for call_graph table, fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    insecure_apis = ["tmpnam", "tempnam", "mktemp"]

    # Prefer database-driven detection
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in insecure_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="unsafe_usage",
                            pattern="insecure_tmpfile",
                            file=relpath,
                            line=call.get("caller_line", 0),
                            evidence=f"{callee}() call",
                            description=f"Using insecure temporary file API ({callee}) may lead to race conditions and hijacking risks.",
                            suggestion="Use mkstemp/mkdtemp or a secure wrapper, and set appropriate permissions.",
                            confidence=0.9,
                            severity="high",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_insecure_tmpfile",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_command_execution(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Command execution vulnerability detection (taint analysis + heuristic fallback):
    - Prefer taint analysis to detect taint propagation paths from user input -> command execution functions
    - If taint analysis is unavailable, fall back to heuristic detection
    - Heuristic: detect system/popen and exec* family where arguments are not literals (may introduce command injection risk)
    Accuracy optimizations:
    - For the exec* family, warn only when the first argument is not a literal path
    - If the first argument is a variable name, look back several lines; if that variable is found to be assigned a literal string, treat it as a safer usage (skip)
    """
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["command_injection"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to Issues
    # Sanitization check for taint paths: if the sink variable was processed by a sanitize/validate function call within the last few lines, skip
    _taint_sanitize_pat = re.compile(
        r"\b(sanitize|validate|check|clean|escape|filter|purify|verify|is_safe|is_valid)\w*\s*\("
    )
    if taint_paths:
        for path in taint_paths:
            # Extract the first argument variable name in the sink line and check whether it has been sanitized
            sink_line_idx = path.line_number - 1  # Convert to 0-based (only for length validation)
            if 0 <= sink_line_idx < len(lines):
                sink_line = _safe_line(lines, path.line_number)
                # Extract the first argument identifier from the sink call
                paren_pos = sink_line.index("(")
                j = paren_pos + 1
                while j < len(sink_line) and sink_line[j].isspace():
                    j += 1
                if j < len(sink_line) and (
                    sink_line[j].isalpha() or sink_line[j] == "_"
                ):
                    k = j
                    while k < len(sink_line) and (
                        sink_line[k].isalnum() or sink_line[k] == "_"
                    ):
                        k += 1
                    sink_var = sink_line[j:k]
                    # Check whether the sink variable was sanitized by a function call in previous lines
                    start = max(1, path.line_number - 10)
                    for row in range(start, path.line_number):
                        sr = _safe_line(lines, row)
                        if _taint_sanitize_pat.search(sr) and re.search(
                            rf"\b{re.escape(sink_var)}\b", sr
                        ):
                            break
                    else:
                        sink_var = None  # No sanitization call found
                    if sink_var is not None:
                        continue  # Already sanitized, skip this path
            issues.append(
                Issue(
                    language="c/cpp",
                    category="unsafe_usage",
                    pattern="command_exec_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or f"{path.source} -> {path.sink}",
                    description=path.description
                    or f"Taint analysis detected command injection risk: {path.source} -> {path.sink}",
                    suggestion="Avoid concatenating commands; use parameterized interfaces or a controlled whitelist; strictly validate/escape external input.",
                    confidence=path.confidence,
                    severity="critical"
                    if path.severity.value == "critical"
                    else "high",
                )
            )
        return issues

    # Taint analysis returned no results, fall back to heuristic detection

    def _arg_is_literal_or_wrapper(s: str, start_idx: int) -> bool:
        # Skip whitespace and determine whether it is directly a literal
        j = start_idx + 1
        while j < len(s) and s[j].isspace():
            j += 1
        return j < len(s) and s[j] == '"'

    def _first_arg_identifier(s: str, start_idx: int) -> Optional[str]:
        j = start_idx + 1
        while j < len(s) and s[j].isspace():
            j += 1
        if j < len(s) and (s[j].isalpha() or s[j] == "_"):
            k = j
            while k < len(s) and (s[k].isalnum() or s[k] == "_"):
                k += 1
            return s[j:k]
        return None

    def _var_assigned_literal(
        var: str, lines: Sequence[str], upto_idx: int, lookback: int = 5
    ) -> bool:
        # Search for var = "..." within the preceding lookback lines
        start = max(1, upto_idx - lookback)
        pat_assign = re.compile(rf"\b{re.escape(var)}\s*=\s*")
        literal_line = None
        for j in range(start, upto_idx):
            sj = _safe_line(lines, j)
            m = pat_assign.search(sj)
            if not m:
                continue
            # Check whether the right side of the assignment is a literal (quotes are preserved in the masked text)
            k = m.end()
            while k < len(sj) and sj[k].isspace():
                k += 1
            if k < len(sj) and sj[k] == '"':
                literal_line = j
                break
        if literal_line is None:
            return False
        # Check whether any later assignment overwrites the same variable after the literal assignment
        for j in range(literal_line + 1, upto_idx):
            sj = _safe_line(lines, j)
            if pat_assign.search(sj):
                return False  # There is an overwriting assignment, not safe
        return True

    # sanitize/validate function name patterns (the variable is considered sanitized after the call)
    _sanitize_pattern = re.compile(
        r"\b(sanitize|validate|check|clean|escape|filter|purify|verify|is_safe|is_valid)\w*\s*\("
    )

    def _var_sanitized(
        var: str, lines: Sequence[str], upto_idx: int, lookback: int = 10
    ) -> bool:
        # Search for sanitize/validate function calls within the preceding lookback lines
        start = max(1, upto_idx - lookback)
        for j in range(start, upto_idx):
            sj = _safe_line(lines, j)
            # Pattern 1: sanitize_xxx(var) or validate_xxx(var)
            if _sanitize_pattern.search(sj) and re.search(rf"\b{re.escape(var)}\b", sj):
                return True
            # Pattern 2: if (is_safe_xxx(var)) or if (is_valid_xxx(var))
            if (
                re.search(r"\bif\s*\(", sj)
                and re.search(
                    r"\b(is_safe|is_valid|is_allowed|is_authorized)\w*\s*\(", sj
                )
                and re.search(rf"\b{re.escape(var)}\b", sj)
            ):
                return True
        return False

    # Build a set of wrapper functions: use call_graph to find wrapper functions that call system/popen/exec*
    _wrapper_funcs: set[str] = set()
    if database:
        try:
            _dangerous_callees = {
                "system",
                "popen",
                "execvp",
                "execlp",
                "execvpe",
                "execl",
                "execve",
                "execv",
            }
            _cg = database.get_call_graph()
            for _call in _cg:
                _cn = _call.get("callee_name", "").lower()
                if _cn in _dangerous_callees:
                    _wrapper = _call.get("caller_name", "")
                    if _wrapper and _wrapper not in ("unknown", "main"):
                        _wrapper_funcs.add(_wrapper)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_command_execution",
            )
            pass

    for idx, s in enumerate(lines, start=1):
        flagged = False
        m_sys = RE_SYSTEM_LIKE.search(s)
        # Detect wrapper function calls (traced to system/popen/exec* via call_graph)
        if not m_sys and _wrapper_funcs:
            for _wf in _wrapper_funcs:
                _m_wf = re.search(rf"\b{re.escape(_wf)}\s*\(", s, re.IGNORECASE)
                if _m_wf:
                    m_sys = _m_wf
                    break
        if m_sys:
            try:
                start = s.index("(", m_sys.start())
                if not _arg_is_literal_or_wrapper(s, start):
                    # If the first argument is a variable and was previously assigned a literal, skip
                    ident = _first_arg_identifier(s, start)
                    if ident and _var_assigned_literal(ident, lines, idx, lookback=5):
                        flagged = False
                    elif ident and _var_sanitized(ident, lines, idx, lookback=10):
                        flagged = False
                    else:
                        flagged = True
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.checkers.c_checker", function="_var_sanitized"
                )
                pass
        if not flagged:
            m_exec = RE_EXEC_LIKE.search(s)
            if m_exec:
                try:
                    start = s.index("(", m_exec.start())
                    if not _arg_is_literal_or_wrapper(s, start):
                        ident = _first_arg_identifier(s, start)
                        if ident and _var_assigned_literal(
                            ident, lines, idx, lookback=5
                        ):
                            flagged = False
                        elif ident and _var_sanitized(ident, lines, idx, lookback=10):
                            flagged = False
                        else:
                            flagged = True
                except Exception:
                    flagged = True
        if flagged:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="unsafe_usage",
                    pattern="command_exec",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="External command execution may use a non-literal argument, posing a command injection risk.",
                    suggestion="Avoid concatenating commands; use parameterized interfaces or a controlled whitelist; strictly validate/escape external input.",
                    confidence=0.7,
                    severity="high",
                )
            )

    # Detect the Windows ShellExecute API (false negative fix)
    for idx, s in enumerate(lines, start=1):
        m_shell = RE_SHELLEXECUTE.search(s)
        if m_shell:
            try:
                start = s.index("(", m_shell.start())
                # The 3rd argument of ShellExecute is the file/program name, and the 4th argument is the parameters
                # Check whether the 3rd or 4th argument is a non-literal
                # Simplified detection: for any ShellExecute call, check whether there is a variable argument
                if not _arg_is_literal_or_wrapper(s, start):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="unsafe_usage",
                            pattern="command_exec",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="ShellExecute call detected; a command execution risk may exist.",
                            suggestion="Avoid using ShellExecute to execute user input; use a whitelist to restrict executable programs.",
                            confidence=0.65,
                            severity="high",
                        )
                    )
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.checkers.c_checker", function="_var_sanitized"
                )
                pass

    # Detect the second argument of the exec* family being user input (false negative fix)
    # Functions such as execl/execlp: the first argument is the path, the second is argv[0], the third is argv[1]...
    # If the second or subsequent arguments are non-literals, command injection may exist
    for idx, s in enumerate(lines, start=1):
        m_exec = RE_EXEC_LIKE.search(s)
        if not m_exec:
            continue
        try:
            func_name = m_exec.group(1).lower()
            # execl/execlp/execlpe family: check the 2nd and subsequent arguments
            if func_name in ["execl", "execlp", "execlpe"]:
                start = s.index("(", m_exec.start())
                # Check whether there are multiple arguments and the second argument is not a literal
                # Simplified detection: check whether any comma-separated argument is a non-literal
                args_part = s[start + 1 :]
                # Check whether there is a second argument (comma-separated)
                if "," in args_part:
                    # Check whether the second argument is a non-literal
                    # Simplified detection: if the second argument is not a string literal (does not start with a quote)
                    second_arg_start = args_part.index(",") + 1
                    second_arg = args_part[second_arg_start:].strip()
                    if second_arg and not second_arg.startswith('"'):
                        # The second argument may be a variable
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="unsafe_usage",
                                pattern="command_exec",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description="exec* family function call detected; the second argument may be user input.",
                                suggestion="Avoid using user input as an argument to exec* functions; use a whitelist to restrict executable programs.",
                                confidence=0.6,
                                severity="high",
                            )
                        )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.checkers.c_checker", function="_var_sanitized"
            )
            pass

    return issues


def _rule_sql_injection(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    SQL injection detection (taint analysis + heuristic fallback):
    - Prefer taint analysis to detect taint propagation paths from user input -> SQL concatenation functions
    - If taint analysis is unavailable, fall back to heuristic detection
    - Heuristic: detect patterns where sprintf/snprintf concatenates SQL statements (format string contains SQL keywords and arguments contain user input)
    """
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["sql_injection"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to Issues
    if taint_paths:
        for path in taint_paths:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="injection",
                    pattern="sql_injection_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or f"{path.source} -> {path.sink}",
                    description=path.description
                    or f"Taint analysis detected SQL injection risk: {path.source} -> {path.sink}",
                    suggestion="Use parameterized queries or prepared statements; avoid concatenating user input into SQL statements.",
                    confidence=path.confidence,
                    severity="critical",
                )
            )
        return issues

    # Taint analysis returned no results, fall back to heuristic detection
    # SQL keyword pattern (case-insensitive)
    sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "EXEC", "EXECUTE"]
    # SQL execution functions
    sql_exec_funcs = [
        "mysql_query",
        "sqlite3_exec",
        "sqlite3_prepare",
        "pg_exec",
        "SQLExecDirect",
    ]

    # Detect sprintf/snprintf concatenating SQL statements
    for idx, s in enumerate(lines, start=1):
        # Detect sprintf/snprintf calls
        m = re.search(r"\b(sprintf|snprintf)\s*\(", s)
        if not m:
            continue
        try:
            # Extract the format string argument (sprintf's 2nd argument, snprintf's 3rd argument)
            # Simplified handling: check whether the string contains SQL keywords
            for kw in sql_keywords:
                if re.search(rf"\b{kw}\b", s, re.IGNORECASE):
                    # Check whether there are arguments (%s, %d, etc.)
                    if re.search(r"%[sdu]", s):
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="injection",
                                pattern="sql_injection",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description="SQL statement concatenation detected; an SQL injection risk may exist.",
                                suggestion="Use parameterized queries or prepared statements; avoid concatenating user input into SQL statements.",
                                confidence=0.7,
                                severity="high",
                            )
                        )
                        break
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_sql_injection",
            )
            pass

    # Detect strcpy+strcat concatenating SQL statements (false negative fix)
    # Pattern: strcat concatenates user input and is preceded by strcpy initializing an SQL statement
    for idx, s in enumerate(lines, start=1):
        if not re.search(r"\bstrcat\s*\(", s):
            continue
        # Check whether strcat concatenates a non-literal argument (possibly user input)
        # Simplified detection: the second argument of strcat is not a string literal
        m = re.search(r"\bstrcat\s*\([^,]+,\s*(\w+)", s)
        if not m:
            continue
        # Look back to see whether there is a strcpy initializing an SQL statement
        start = max(1, idx - 5)
        has_sql_init = False
        for j in range(start, idx):
            prev_line = _safe_line(lines, j)
            if re.search(r"\bstrcpy\s*\(", prev_line):
                # Check whether strcpy initializes an SQL statement (contains SQL keywords)
                for kw in sql_keywords:
                    if re.search(rf"\b{kw}\b", prev_line, re.IGNORECASE):
                        has_sql_init = True
                        break
            if has_sql_init:
                break
        if has_sql_init:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="injection",
                    pattern="sql_injection",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Detected strcpy+strcat concatenating SQL statements; an SQL injection risk may exist.",
                    suggestion="Use parameterized queries or prepared statements; avoid concatenating user input into SQL statements.",
                    confidence=0.65,
                    severity="high",
                )
            )

    # Detect SQL execution functions directly using concatenated variables (false negative fix)
    for idx, s in enumerate(lines, start=1):
        for func in sql_exec_funcs:
            if not re.search(rf"\b{func}\s*\(", s):
                continue
            # First detect dereferenced arguments (e.g. *query) and report directly
            deref_m = re.search(rf"\b{func}\s*\([^,]+,\s*\*(\w+)", s)
            if deref_m:
                deref_var = deref_m.group(1)
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="injection",
                        pattern="sql_injection",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Detected {func} directly using dereferenced variable pointer {deref_var}; an SQL injection risk may exist.",
                        suggestion="Use parameterized queries or prepared statements; avoid concatenating user input into SQL statements.",
                        confidence=0.75,
                        severity="high",
                    )
                )
                continue
            # Check whether a variable argument is used (non-literal)
            m = re.search(rf"\b{func}\s*\([^,]+,\s*(\w+)", s)
            if m:
                var_name = m.group(1)
                # Check whether the variable was assigned by sprintf/snprintf earlier
                start = max(1, idx - 10)
                for j in range(start, idx):
                    prev_line = _safe_line(lines, j)
                    if re.search(
                        rf"\b(sprintf|snprintf)\s*\(\s*{re.escape(var_name)}", prev_line
                    ):
                        # Check whether there are SQL keywords
                        for kw in sql_keywords:
                            if re.search(rf"\b{kw}\b", prev_line, re.IGNORECASE):
                                issues.append(
                                    Issue(
                                        language="c/cpp",
                                        category="injection",
                                        pattern="sql_injection",
                                        file=relpath,
                                        line=idx,
                                        evidence=_strip_line(s),
                                        description=f"Detected {func} using a concatenated SQL variable; an SQL injection risk may exist.",
                                        suggestion="Use parameterized queries or prepared statements; avoid concatenating user input into SQL statements.",
                                        confidence=0.7,
                                        severity="high",
                                    )
                                )
                                break
                    break

    return issues


def _rule_memory_leak(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Memory leak detection (based on the database's pointer_states):
    - Detect pointers with an ALLOCATED state but no corresponding FREED state
    - Use the database's pointer_states table for precise analysis
    """
    issues: List[Issue] = []

    # Skip very short functions (usually sample code)
    # If a function has fewer than 10 lines, it may be test or sample code
    if len(lines) < 10:
        return issues

    if database is None:
        # Skip regex fallback when there is no database (to avoid false positives)
        return issues

    # Get the current file's pointer_states from the database
    try:
        states = database.get_pointer_states_by_file(relpath)
    except Exception:
        return issues

    if not states:
        return issues

    # Group by variable name and check for ALLOCATED but not FREED cases
    var_states: Dict[str, List[Dict[str, Any]]] = {}
    for state in states:
        var_name = state.get("var_name", "")
        if var_name:
            if var_name not in var_states:
                var_states[var_name] = []
            var_states[var_name].append(state)

    # Get the function parameter list (used to skip memory leak checks for parameters)
    func_params = set()
    try:
        symbols = database.get_symbols_by_file(relpath)
        for sym in symbols:
            if sym.get("kind") == "parameter":
                func_params.add(sym.get("name", ""))
    except Exception as e:
        save_exception(
            e, module="haijunbot_sec.checkers.c_checker", function="_rule_memory_leak"
        )
        pass

    # Check the state of each variable
    for var_name, state_list in var_states.items():
        has_allocated = any(s.get("state") == "ALLOCATED" for s in state_list)
        has_freed = any(s.get("state") == "FREED" for s in state_list)

        if has_allocated and not has_freed:
            # Skip function parameters (the caller is responsible for parameter memory management)
            if var_name in func_params:
                continue
            # Skip variables that have a null check (indicating the caller cares about the return value)
            try:
                from haijunbot.haijunbot_sec.data_flow_analyzer import DataFlowAnalyzer

                analyzer = DataFlowAnalyzer(database)
                code = "\n".join(lines)
                result = analyzer.analyze_code(
                    code, is_cpp=False, database=database, file_path=relpath
                )
                if result and result.null_checks and var_name in result.null_checks:
                    continue
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.checkers.c_checker",
                    function="_rule_memory_leak",
                )
                pass
            # Find the position of the first ALLOCATED state
            for state in state_list:
                if state.get("state") == "ALLOCATED":
                    line = state.get("line", 0)
                    allocator = state.get("allocator", "malloc")
                    scope = state.get("scope", "")

                    # Get the evidence line
                    evidence = ""
                    if 0 < line <= len(lines):
                        evidence = _strip_line(lines[line - 1])

                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory",
                            pattern="memory_leak",
                            file=relpath,
                            line=line,
                            evidence=evidence,
                            description=f"Pointer '{var_name}' in function '{scope}' is allocated via {allocator} but not freed; a memory leak may exist.",
                            suggestion="Ensure that allocated memory is freed on all code paths, or use the RAII pattern.",
                            confidence=0.8,
                            severity="medium",
                            var_name=var_name,
                        )
                    )
                    break  # Report each variable only once

    return issues


def _rule_path_traversal(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Path traversal detection (taint analysis + heuristic fallback):
    - Prefer taint analysis to detect taint propagation paths from user input -> path concatenation functions
    - If taint analysis is unavailable, fall back to heuristic detection
    - Heuristic: detect patterns where strcat/strncat concatenates paths
    """
    issues: List[Issue] = []

    # Try to use taint analysis
    code = "\n".join(lines)
    taint_paths = taint_analyzer.analyze_with_best_analyzer(
        code, rules=["path_traversal"], file_path=relpath, database=database
    )

    # If taint analysis has results, convert them to Issues
    if taint_paths:
        for path in taint_paths:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="injection",
                    pattern="path_traversal_taint",
                    file=relpath,
                    line=path.line_number,
                    evidence=path.code_snippet or f"{path.source} -> {path.sink}",
                    description=path.description
                    or f"Taint analysis detected path traversal risk: {path.source} -> {path.sink}",
                    suggestion="Validate user input, filter path traversal characters such as ../, and use a whitelist to restrict accessible paths.",
                    confidence=path.confidence,
                    severity="high",
                )
            )
        return issues

    # Taint analysis returned no results, fall back to heuristic detection
    # Path concatenation function patterns
    path_concat_pattern = re.compile(r"\b(strcat|strncat)\s*\(")
    # snprintf/sprintf path concatenation pattern (false negative fix)
    snprintf_pattern = re.compile(r"\b(snprintf|sprintf)\s*\(")
    # File operation function patterns
    file_op_pattern = re.compile(r"\b(fopen|open|openat)\s*\(")
    # Path-related keywords
    path_keywords = [
        "path",
        "file",
        "dir",
        "folder",
        "config",
        "data",
        "log",
        "tmp",
        "temp",
    ]

    # sanitize/validate function name patterns
    _path_sanitize_pattern = re.compile(
        r"\b(sanitize|validate|check|clean|filter|verify|is_safe|is_valid|is_allowed)\w*\s*\("
    )

    def _has_path_sanitized(
        lines: Sequence[str], upto_idx: int, lookback: int = 10
    ) -> bool:
        start = max(1, upto_idx - lookback)
        for j in range(start, upto_idx):
            sj = _safe_line(lines, j)
            if _path_sanitize_pattern.search(sj):
                return True
            # if (is_safe_filename(var)) pattern
            if re.search(r"\bif\s*\(", sj) and re.search(
                r"\b(is_safe|is_valid|is_allowed)\w*\s*\(", sj
            ):
                return True
        return False

    # Detect path concatenation subsequently used for file operations
    for idx, s in enumerate(lines, start=1):
        if path_concat_pattern.search(s):
            # Skip already sanitized/validated paths
            if _has_path_sanitized(lines, idx, lookback=10):
                continue
            # Check whether the following few lines contain file operations (expand window to 10 lines)
            for j in range(idx, min(idx + 10, len(lines) + 1)):
                if file_op_pattern.search(lines[j - 1]):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="injection",
                            pattern="path_traversal",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Path concatenation detected followed by file operations, possible path traversal risk.",
                            suggestion="Validate user input, filter path traversal characters such as ../, and use a whitelist to restrict access paths.",
                            confidence=0.6,
                            severity="medium",
                        )
                    )
                    break

    # Detect snprintf/sprintf concatenated paths used for file operations (false negative fix)
    for idx, s in enumerate(lines, start=1):
        if not snprintf_pattern.search(s):
            continue
        # Check whether it contains path-related keywords or a format string
        has_path_context = False
        for kw in path_keywords:
            if re.search(rf"\b{kw}\b", s, re.IGNORECASE):
                has_path_context = True
                break
        if not has_path_context and not re.search(r"%s", s):
            continue
        # Check whether the following 10 lines contain file operations
        for j in range(idx, min(idx + 10, len(lines) + 1)):
            if file_op_pattern.search(lines[j - 1]):
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="injection",
                        pattern="path_traversal",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="snprintf/sprintf concatenated path detected followed by file operations, possible path traversal risk.",
                        suggestion="Validate user input, filter path traversal characters such as ../, and use a whitelist to restrict access paths.",
                        confidence=0.65,
                        severity="medium",
                    )
                )
                break

    return issues


def _rule_integer_overflow_from_calls(
    lines: Sequence[str], relpath: str, alloc_calls: List[Dict[str, Any]]
) -> List[Issue]:
    """
    Integer overflow detection helper functions based on call_graph data.
    Analyze multiplication/addition expressions in malloc/calloc/realloc call arguments.
    """
    issues: List[Issue] = []

    # Detect multiplication or addition expressions (excluding pointer declarations)
    mul_pattern = re.compile(r"(?<![(*])\b([A-Za-z_]\w*)\s\*\s([A-Za-z_]\w*)(?!\s\))")
    add_pattern = re.compile(r"\b([A-Za-z_]\w*)\s\+\s([A-Za-z_]\w*|\d+)")

    # Overflow check patterns (safe patterns) - generalized version
    # Pattern 1: var <= MAX / other_var (direct check)
    # Pattern 2: var > MAX / other_var (return/error if greater)
    # Pattern 3: var <= MAX - other_var (addition check)
    # Support multiple MAX constants: INT_MAX, UINT_MAX, SIZE_MAX, SSIZE_MAX, LONG_MAX, etc.
    # Use non-capturing groups (?:...) to avoid group index confusion
    MAX_CONSTANTS = r"(?:UINT_MAX|INT_MAX|SIZE_MAX|SSIZE_MAX|LONG_MAX|ULONG_MAX|LLONG_MAX|ULLONG_MAX|INT8_MAX|INT16_MAX|INT32_MAX|INT64_MAX|UINT8_MAX|UINT16_MAX|UINT32_MAX|UINT64_MAX|\d+)"

    mul_overflow_check = re.compile(
        rf"\b([A-Za-z_]\w*)\s(<=|<|>|>=)\s{MAX_CONSTANTS}\s/\s([A-Za-z_]\w*)"
    )
    add_overflow_check = re.compile(
        rf"\b([A-Za-z_]\w*)\s(<|<=|>|>=)\s{MAX_CONSTANTS}\s-\s([A-Za-z_]\w*|\d+)"
    )

    # Added: overflow checks in conditional statements (if/while statements)
    # Pattern: if (count > 0 && elem_size > 0 && count <= SIZE_MAX / elem_size)
    conditional_overflow_check = re.compile(
        rf"\b(if|while)\s*\([^)]*([A-Za-z_]\w*)\s(<=|<)\s{MAX_CONSTANTS}\s/\s([A-Za-z_]\w*)[^)]*\)"
    )

    # Added: variable comparison check (more general pattern)
    # Pattern: count <= SIZE_MAX / elem_size or base_size <= SIZE_MAX - extra
    generic_div_check = re.compile(
        rf"([A-Za-z_]\w*)\s(<=|<|>|>=)\s{MAX_CONSTANTS}\s/\s([A-Za-z_]\w*)"
    )
    generic_sub_check = re.compile(
        rf"([A-Za-z_]\w*)\s(<=|<|>|>=)\s{MAX_CONSTANTS}\s-\s([A-Za-z_]\w*|\d+)"
    )

    def _has_overflow_check(
        var1: str, var2: str, lines: Sequence[str], upto_idx: int, lookback: int = 10
    ) -> bool:
        """Check whether within the preceding lookback lines there is an overflow check for var1*var2 or var1+var2

        Generalized version: supports multiple MAX constants and check patterns
        """
        start = max(1, upto_idx - lookback)
        for j in range(start, upto_idx):
            sj = _safe_line(lines, j)

            # Check multiplication overflow check patterns
            m = mul_overflow_check.search(sj)
            if m:
                checked_var = m.group(1)
                divisor_var = m.group(3)
                # Check whether var1 or var2 is involved
                if checked_var == var1 or checked_var == var2:
                    return True
                if divisor_var == var1 or divisor_var == var2:
                    return True

            # Check addition overflow check patterns
            m = add_overflow_check.search(sj)
            if m:
                checked_var = m.group(1)
                if checked_var == var1 or checked_var == var2:
                    return True

            # Check overflow checks in conditional statements
            m = conditional_overflow_check.search(sj)
            if m:
                checked_var = m.group(2)
                divisor_var = m.group(4)
                if checked_var == var1 or checked_var == var2:
                    return True
                if divisor_var == var1 or divisor_var == var2:
                    return True

            # Check general division check patterns
            m = generic_div_check.search(sj)
            if m:
                checked_var = m.group(1)
                divisor_var = m.group(3)
                if checked_var == var1 or checked_var == var2:
                    return True
                if divisor_var == var1 or divisor_var == var2:
                    return True

            # Check general subtraction check patterns
            m = generic_sub_check.search(sj)
            if m:
                checked_var = m.group(1)
                sub_var = m.group(3)
                if checked_var == var1 or checked_var == var2:
                    return True
                if sub_var == var1 or sub_var == var2:
                    return True

        return False

    reported = set()  # Deduplication: (line, pattern) reported only once

    for call in alloc_calls:
        idx = call.get("caller_line", 0)
        callee_name = call.get("callee_name", "malloc")
        if 0 < idx <= len(lines):
            s = lines[idx - 1]
        else:
            continue

        # Extract the malloc/calloc/realloc argument part
        # False negative fix: start searching for the parenthesis from the function name position to avoid interference from type casts
        try:
            func_pos = s.find(callee_name)
            if func_pos < 0:
                continue
            paren_start = s.find("(", func_pos)
            if paren_start < 0:
                continue
            alloc_start = paren_start + 1
            alloc_end = s.find(")", alloc_start)
            if alloc_end < 0:
                continue
            alloc_arg = s[alloc_start:alloc_end].strip()
        except (ValueError, IndexError):
            continue

        # Skip the same line and same pattern already reported (deduplication)
        if (idx, "integer_overflow") in reported:
            continue

        # Detect multiplication overflow
        mul_match = mul_pattern.search(alloc_arg)
        if mul_match:
            var1, var2 = mul_match.group(1), mul_match.group(2)
            # Exclude the sizeof safe pattern: var * sizeof(...) is a standard safe idiom
            if re.search(r"\bsizeof\s*\(", alloc_arg):
                mul_match = None
            elif not _has_overflow_check(var1, var2, lines, idx, lookback=10):
                reported.add((idx, "integer_overflow"))
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="arithmetic",
                        pattern="integer_overflow",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Multiplication expression '{mul_match.group(0)}' detected as a {callee_name} argument, possible integer overflow risk.",
                        suggestion="Use safe integer arithmetic functions or add overflow checks to ensure the allocation size is correct.",
                        confidence=0.7,
                        severity="high",
                    )
                )

        # Detect addition overflow
        add_match = add_pattern.search(alloc_arg)
        if add_match and (idx, "integer_overflow") not in reported:
            var1, var2 = add_match.group(1), add_match.group(2)
            # Exclude addition of a small constant: var + small number cannot overflow
            if var2.isdigit() and int(var2) <= 100:
                add_match = None
            elif not _has_overflow_check(var1, var2, lines, idx, lookback=10):
                reported.add((idx, "integer_overflow"))
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="arithmetic",
                        pattern="integer_overflow",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Addition expression '{add_match.group(0)}' detected as a {callee_name} argument, possible integer overflow risk.",
                        suggestion="Use safe integer arithmetic functions or add overflow checks to ensure the allocation size is correct.",
                        confidence=0.7,
                        severity="high",
                    )
                )

        # False negative fix: detect indirect multiplication overflow
        # Pattern: a variable is used as a malloc argument and was assigned by a multiplication in the preceding few lines
        if not mul_match and not add_match:
            # Check whether alloc_arg is a variable name
            var_in_alloc = re.match(r"^([A-Za-z_]\w*)$", alloc_arg)
            if var_in_alloc:
                target_var = var_in_alloc.group(1)
                # Search backward for a multiplication assignment to that variable
                for lookback_line in range(max(0, idx - 10), idx):
                    prev_line = lines[lookback_line]
                    # Detect multiplication assignment pattern: var = expr1 * expr2
                    assign_mul = re.search(
                        rf"\b{re.escape(target_var)}\s*=\s*([^;]+)\s*\*\s*([^;]+)",
                        prev_line,
                    )
                    if assign_mul:
                        expr1, expr2 = (
                            assign_mul.group(1).strip(),
                            assign_mul.group(2).strip(),
                        )
                        # Check whether there is an overflow check (increase the lookback range to cover if conditions)
                        # Key optimization: an overflow check in an if condition is valid inside the if block
                        if not _has_overflow_check(
                            expr1, expr2, lines, idx, lookback=15
                        ):
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="arithmetic",
                                    pattern="integer_overflow",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(s),
                                    description=f"Variable '{target_var}' is assigned by multiplication and then used in {callee_name}, possible integer overflow risk.",
                                    suggestion="Use safe integer arithmetic functions or add overflow checks to ensure the allocation size is correct.",
                                    confidence=0.6,
                                    severity="medium",
                                )
                            )
                        break

    return issues


def _rule_integer_overflow(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Integer overflow detection:
    - Detect multiplication/addition expressions used as malloc/calloc/realloc arguments
    - Detect integer overflow risks that may cause insufficient buffer allocation
    - Optimization: recognize preceding overflow checks to avoid false positives
    - Prefer database query for call_graph table, fall back to regex detection when there is no data
    """
    issues: List[Issue] = []
    import os

    # Set of memory allocation functions
    ALLOC_FUNCS = {"malloc", "calloc", "realloc"}

    # Prefer database query
    if database:
        try:
            call_graph = database.get_call_graph()
            alloc_calls = []
            for call in call_graph:
                callee_name = call.get("callee_name", "")
                if callee_name in ALLOC_FUNCS:
                    caller_file = call.get("caller_file", "")
                    if os.path.basename(caller_file) == os.path.basename(relpath):
                        alloc_calls.append(call)

            # If there is data in the database, use the database result
            if alloc_calls:
                return _rule_integer_overflow_from_calls(lines, relpath, alloc_calls)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_integer_overflow",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_hardcoded_credentials(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Hardcoded credential detection:
    - Prefer database query on the data_flow table to detect sensitive variable assignments
    - If database unavailable, fall back to regex matching
    - Detect sensitive variable names (password, key, secret, token, etc.)
    - Detect hardcoded sensitive strings
    """
    issues: List[Issue] = []

    # List of sensitive variable names
    SENSITIVE_VARS = {
        "password",
        "passwd",
        "pwd",
        "secret",
        "key",
        "token",
        "api_key",
        "apikey",
        "auth",
        "credential",
        "private_key",
        "access_key",
    }

    # Prefer database query
    if database:
        try:
            data_flow = database.get_data_flow_by_file(relpath)
            for node in data_flow:
                var_name = node.get("var_name", "")
                if var_name.lower() not in SENSITIVE_VARS:
                    continue
                # Check whether it is an assignment operation whose value is a string literal
                node_type = node.get("node_type", "")
                if node_type == "assign":
                    line_num = node.get("line_number", 0)
                    if 0 < line_num <= len(lines):
                        s = lines[line_num - 1]
                        # Check whether it is assigned a string literal
                        str_match = re.search(r'"([^"]{4,})"', s)
                        if str_match:
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="crypto",
                                    pattern="hardcoded_credentials",
                                    file=relpath,
                                    line=line_num,
                                    evidence=_strip_line(s),
                                    description="Hardcoded credential detected: the variable name contains a sensitive keyword and is assigned a hardcoded string.",
                                    suggestion="Use environment variables, configuration files, or a key management system to store sensitive information and avoid hardcoding.",
                                    confidence=0.75,
                                    severity="high",
                                )
                            )
            # If the database has results, return
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_hardcoded_credentials",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_toctou_race_from_calls(
    lines: Sequence[str], relpath: str, file_calls: List[Dict[str, Any]]
) -> List[Issue]:
    """
    TOCTOU race condition detection helper functions based on call_graph data.
    Detect the pattern where an access/stat check is immediately followed by a fopen/open use.
    """
    issues: List[Issue] = []

    # Set of check functions
    CHECK_FUNCS = {"access", "lstat", "stat", "fstat"}
    # Set of use functions (including C++ ifstream/ofstream/fstream constructors)
    USE_FUNCS = {"fopen", "open", "openat", "ifstream", "ofstream", "fstream"}

    # Sort calls by line number
    file_calls.sort(key=lambda c: c.get("caller_line", 0))

    # Detect pattern: after a check function call, a use function call appears within a few lines
    for i, call in enumerate(file_calls):
        callee_name = call.get("callee_name", "")
        if callee_name not in CHECK_FUNCS:
            continue

        check_line = call.get("caller_line", 0)
        if 0 < check_line <= len(lines):
            check_evidence = _strip_line(lines[check_line - 1])
        else:
            continue

        # Detect use functions within the following 15 lines (false negative fix: expand window from 5 lines to 15 lines)
        for j in range(i + 1, len(file_calls)):
            next_call = file_calls[j]
            next_line = next_call.get("caller_line", 0)
            next_callee = next_call.get("callee_name", "")

            # Check whether it is within the 15-line window
            if next_line - check_line > 15:
                break

            if next_callee in USE_FUNCS:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="concurrency",
                        pattern="toctou_race",
                        file=relpath,
                        line=check_line,
                        evidence=check_evidence,
                        description=f"TOCTOU race condition detected: {callee_name} check followed by use of {next_callee}, there is a race window.",
                        suggestion="Use the O_NOFOLLOW flag, fstat to check the already opened file descriptor, or use atomic operations to avoid the race.",
                        confidence=0.65,
                        severity="high",
                    )
                )
                break

    return issues


def _rule_toctou_race(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    TOCTOU race condition detection:
    - Detect access+fopen pattern
    - Detect lstat+fopen pattern
    - Detect stat+fopen pattern
    - Prefer database query for call_graph table, fall back to regex detection when there is no data
    """
    issues: List[Issue] = []
    import os

    # Set of check functions
    CHECK_FUNCS = {"access", "lstat", "stat", "fstat"}
    # Set of use functions (including C++ ifstream/ofstream/fstream constructors)
    USE_FUNCS = {"fopen", "open", "openat", "ifstream", "ofstream", "fstream"}

    # Prefer database query
    if database:
        try:
            call_graph = database.get_call_graph()
            file_calls = []
            for call in call_graph:
                callee_name = call.get("callee_name", "")
                if callee_name in CHECK_FUNCS or callee_name in USE_FUNCS:
                    caller_file = call.get("caller_file", "")
                    if os.path.basename(caller_file) == os.path.basename(relpath):
                        file_calls.append(call)

            # If there is data in the database, use the database result
            if file_calls:
                return _rule_toctou_race_from_calls(lines, relpath, file_calls)
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.checkers.c_checker", function="_rule_toctou_race"
            )
            pass

    # Skip detection when there is no database (to avoid false positives)
    return issues


def _rule_scanf_no_width(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect scanf/sscanf/fscanf using %s without specifying a maximum width, which poses a buffer overflow risk.
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    Accuracy optimizations:
    - Ignore the GNU extension %ms (automatic memory allocation) and the %m[...] pattern (automatic allocation)
    - Ignore %*s which discards input (does not write to the target buffer)
    """
    issues: List[Issue] = []
    SCANF_FUNCS = {"scanf", "sscanf", "fscanf"}

    # Prefer database query
    if database:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name.lower() not in SCANF_FUNCS:
                continue
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            if 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                continue

            # Extract the format string from the code line
            # The scanf format string is the 1st argument, and the sscanf/fscanf format string is the 2nd argument
            m = RE_SCANF_CALL.search(s)
            if not m:
                m = RE_SCANF_CALL_ARG2.search(s)
            if not m:
                continue
            fmt = m.group(1)

            unsafe = False
            if "%s" in fmt and not re.search(r"%\d+s", fmt):
                unsafe = True
            if unsafe and re.search(r"%\*s", fmt):
                unsafe = False
            if unsafe and re.search(r"%m[a-z\[]", fmt, re.IGNORECASE):
                unsafe = False

            if unsafe:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="buffer_overflow",
                        pattern="scanf_%s_no_width",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="scanf/sscanf/fscanf uses %s without limiting the maximum width, posing a buffer overflow risk.",
                        suggestion='Specify a maximum width for %s (e.g. "%255s"), or use a safer reading method.',
                        confidence=0.75,
                        severity="high",
                    )
                )
        return issues

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


# List of async-signal-safe functions (POSIX standard)
ASYNC_SIGNAL_SAFE_FUNCS = {
    # IO
    "write",
    "read",
    "close",
    "pipe",
    "_exit",
    "_Exit",
    # Signals
    "signal",
    "sigprocmask",
    "sigaction",
    "sigpending",
    "sigsuspend",
    "kill",
    # Process
    "fork",
    "execve",
    "execv",
    "execvp",
    "execvpe",
    # Memory
    "mmap",
    "munmap",
    "mprotect",
    # Others
    "getpid",
    "getppid",
    "getuid",
    "geteuid",
    "getgid",
    "getegid",
    "setuid",
    "setgid",
    "seteuid",
    "setegid",
    "chdir",
    "chroot",
    "sync",
    "fsync",
    "dup",
    "dup2",
    "fcntl",
    "flock",
    "waitpid",
    "wait",
    "waitid",
    "alarm",
    "pause",
    "sleep",
    "clock_gettime",
    "gettimeofday",
    # Error handling
    "errno",
    "strerror",  # strerror may be unsafe in some implementations, but POSIX marks it as safe
}

# Common functions that are unsafe in a signal handler
ASYNC_SIGNAL_UNSAFE_FUNCS = {
    # IO functions (not async-signal-safe)
    "printf",
    "fprintf",
    "sprintf",
    "snprintf",
    "vprintf",
    "vfprintf",
    "vsprintf",
    "vsnprintf",
    "scanf",
    "fscanf",
    "sscanf",
    "fopen",
    "fclose",
    "fread",
    "fwrite",
    "perror",
    "puts",
    "fputs",
    "putchar",
    "fputc",
    "fgets",
    "gets",
    # Memory allocation
    "malloc",
    "calloc",
    "realloc",
    "free",
    "memalign",
    "valloc",
    # Process control
    "exit",
    "system",
    "popen",
    "pclose",
    # String operations
    "strdup",
    "strndup",
    "strerror_r",
    # Time functions
    "localtime",
    "gmtime",
    "asctime",
    "ctime",
    "strftime",
    # Others
    "syslog",
    "abort",
    "raise",
}


def _rule_signal_handler_unsafe(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect calls to non-async-signal-safe functions within a signal handler.

    The POSIX standard specifies that only async-signal-safe functions may be called within a signal handler.
    Unsafe functions include: printf, fprintf, malloc, free, exit, etc.

    Detection logic:
    1. Find the signal(sig, handler) call and extract the handler function name
    2. Find the definition body of the handler function
    3. Check whether the handler function body calls any non-async-signal-safe functions
    """
    issues: List[Issue] = []

    # Regex-match signal(sig, handler) calls
    SIGNAL_PATTERN = re.compile(
        r"\bsignal\s*\(\s*[^,]+,\s*([A-Za-z_]\w*)\s*\)", re.IGNORECASE
    )

    # Find all signal handler registrations
    handler_names = set()
    for line in lines:
        m = SIGNAL_PATTERN.search(line)
        if m:
            handler_names.add(m.group(1))

    if not handler_names:
        return issues

    # Build the complete code text
    code = "\n".join(lines)

    for handler_name in handler_names:
        # Find the position of the handler function definition
        func_pattern = re.compile(
            rf"^(?:static\s+)?(?:void|int)\s+{re.escape(handler_name)}\s*\([^)]*\)\s*\{{",
            re.MULTILINE,
        )

        for func_match in func_pattern.finditer(code):
            start_pos = func_match.end() - 1  # Points to the '{'

            # Find the end position of the function body (matching braces)
            brace_count = 1
            end_pos = start_pos + 1
            while end_pos < len(code) and brace_count > 0:
                if code[end_pos] == "{":
                    brace_count += 1
                elif code[end_pos] == "}":
                    brace_count -= 1
                end_pos += 1

            # Extract the function body
            func_body = code[start_pos:end_pos]
            func_body_lines = func_body.splitlines()

            # Compute the starting line number of the function
            func_start_line = code[: func_match.start()].count("\n") + 1

            # Check for unsafe function calls within the function body
            for line_offset, line in enumerate(func_body_lines):
                line_num = func_start_line + line_offset

                for unsafe_func in ASYNC_SIGNAL_UNSAFE_FUNCS:
                    # Match function call patterns
                    if re.search(rf"\b{re.escape(unsafe_func)}\s*\(", line):
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="signal_safety",
                                pattern="signal_handler_unsafe_func",
                                file=relpath,
                                line=line_num,
                                evidence=_strip_line(line),
                                description=f"Signal handler '{handler_name}' calls non-async-signal-safe function '{unsafe_func}'. "
                                f"POSIX requires signal handlers to only call async-signal-safe functions.",
                                suggestion=f"Replace '{unsafe_func}' with an async-signal-safe alternative "
                                f"(e.g., use write() instead of printf(), _exit() instead of exit()).",
                                confidence=0.85,
                                severity="medium",
                            )
                        )

    return issues


def _rule_weak_crypto(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect the use of weak cryptographic algorithms (CWE-327): DES/RC4/MD5/SHA1/Blowfish, etc.
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    """
    issues: List[Issue] = []
    WEAK_CRYPTO_APIS = {
        "DES_set_key",
        "DES_set_key_unchecked",
        "DES_ecb_encrypt",
        "DES_cbc_encrypt",
        "DES_ncbc_encrypt",
        "DES_ede3_cbc_encrypt",
        "DES_ede2_cbc_encrypt",
        "RC4_set_key",
        "RC4",
        "MD5_Init",
        "MD5_Update",
        "MD5_Final",
        "MD5_Transform",
        "SHA1_Init",
        "SHA1_Update",
        "SHA1_Final",
        "SHA1_Transform",
        "BF_set_key",
        "BF_ecb_encrypt",
        "BF_cbc_encrypt",
        "BF_encrypt",
        "BF_decrypt",
    }

    # Prefer database query
    if database:
        import os

        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name not in WEAK_CRYPTO_APIS:
                continue
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            if 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                continue

            issues.append(
                Issue(
                    language="c/cpp",
                    category="crypto",
                    pattern="weak_crypto",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"Use of weak cryptographic algorithm {callee_name}, which risks being broken.",
                    suggestion="Use stronger cryptographic algorithms (e.g. AES-256 instead of DES, SHA-256 instead of MD5/SHA1).",
                    confidence=0.85,
                    severity="high",
                )
            )
        return issues
    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_uninitialized_var(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect use of uninitialized variables (CWE-457): used after declaration without being assigned.
    Detection pattern: after "type var;" it is used directly without assignment within the window (return var, var+1, func(var), etc.).
    Exclude: initialization at declaration (int var = 0;), pointer types (covered by _rule_uninitialized_ptr_use).
    """
    issues: List[Issue] = []

    # Skip regex detection when there's no database (avoid false positives)
    if database is None:
        return issues

    # Type keywords
    type_kw = re.compile(
        r"\b(int|long|short|char|float|double|unsigned|signed|size_t|ssize_t|"
        r"uint\d*_t|int\d*_t|BOOL|bool)\b"
    )
    # Declaration pattern: type var; (excluding = and *)
    decl_pattern = re.compile(r"\b([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;")

    # Collect line number ranges within class/struct (used to exclude member variables)
    class_member_lines = set()
    brace_depth = 0
    in_class_body = False
    for idx, s in enumerate(lines, start=1):
        if re.search(r"\b(class|struct)\s+\w+", s):
            in_class_body = True
            brace_depth = s.count("{") - s.count("}")
            if brace_depth > 0:
                class_member_lines.add(idx)
            continue
        if in_class_body:
            brace_depth += s.count("{") - s.count("}")
            class_member_lines.add(idx)
            if brace_depth <= 0:
                in_class_body = False

    candidates = []  # (var, decl_line)
    for idx, s in enumerate(lines, start=1):
        # Skip preprocessor lines
        t = s.lstrip()
        if t.startswith("#"):
            continue
        # Skip typedef (type alias, not a variable declaration)
        if re.search(r"\btypedef\b", s):
            continue
        # Skip class/struct member variables (covered by the uninitialized_member rule)
        if idx in class_member_lines:
            continue
        # Must have a type keyword
        if not type_kw.search(s):
            continue
        # Exclude pointer declarations (covered by _rule_uninitialized_ptr_use)
        if "*" in s:
            continue
        # Exclude declarations with initialization
        if "=" in s:
            continue
        # Exclude function declarations (containing parentheses)
        if "(" in s:
            continue
        m = decl_pattern.search(s)
        if m:
            var = m.group(2)
            # Exclude common non-variable names
            if var in (
                "main",
                "if",
                "while",
                "for",
                "return",
                "struct",
                "enum",
                "union",
            ):
                continue
            candidates.append((var, idx))

    # Check whether candidate variables may be used before being initialized
    for var, decl_line in candidates:
        end = min(len(lines), decl_line + 30)
        # Collect assignment lines and usage lines
        assign_lines = []
        use_line = None
        for j in range(decl_line + 1, end + 1):
            sj = _safe_line(lines, j)
            # Assignment: var = ...
            if re.search(rf"\b{re.escape(var)}\s*=", sj):
                assign_lines.append(j)
            # Usage: return var, var + ..., func(var), printf(...var...)
            elif re.search(rf"\b{re.escape(var)}\b", sj):
                # Exclude declaration lines (re-declaration of the same variable name)
                if type_kw.search(sj) and re.search(rf"\b{re.escape(var)}\s*;", sj):
                    continue
                use_line = j
                break

        if not use_line:
            continue

        # If there is no assignment, report directly
        if not assign_lines:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="uninitialized",
                    pattern="uninitialized_var",
                    file=relpath,
                    line=decl_line,
                    evidence=_strip_line(_safe_line(lines, decl_line)),
                    description=f"Variable {var} is used without initialization after declaration; it may read an undefined value.",
                    suggestion="Initialize the variable at declaration, or ensure all paths assign it before use.",
                    confidence=0.7,
                    severity="medium",
                )
            )
            continue

        # Check whether the assignment is inside an if block but the usage is outside it (possible uninitialized path)
        # Simplified detection: assignment line is more indented than usage line -> assignment is inside a conditional block
        for assign_line in assign_lines:
            assign_indent = len(_safe_line(lines, assign_line)) - len(
                _safe_line(lines, assign_line).lstrip()
            )
            use_indent = len(_safe_line(lines, use_line)) - len(
                _safe_line(lines, use_line).lstrip()
            )
            if assign_indent > use_indent:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="uninitialized",
                        pattern="uninitialized_var",
                        file=relpath,
                        line=decl_line,
                        evidence=_strip_line(_safe_line(lines, decl_line)),
                        description=f"Variable {var} is assigned only inside a conditional branch; other paths may use an uninitialized value.",
                        suggestion="Initialize the variable at declaration, or ensure all paths assign it before use.",
                        confidence=0.65,
                        severity="medium",
                    )
                )
                break

        # If the assignment and usage are at the same indentation level, treat it as safe (initialized)
        continue

    # === Second pass: detect uninitialized C++ class members ===
    # Detection pattern: member variable declared inside class as type var; but not initialized by the constructor
    # Collect class member variables
    class_members: Dict[str, List[Tuple[str, int]]] = {}  # class_name -> [(var, line)]
    current_class: Optional[str] = None
    class_brace_depth = 0
    in_class = False

    for idx, s in enumerate(lines, start=1):
        t = s.lstrip()
        if t.startswith("#"):
            continue
        # Detect class definitions
        class_match = re.search(r"\bclass\s+(\w+)", s)
        if class_match:
            current_class = class_match.group(1)
            class_brace_depth = s.count("{") - s.count("}")
            in_class = "{" in s
            if current_class not in class_members:
                class_members[current_class] = []
            continue

        if in_class and current_class:
            class_brace_depth += s.count("{") - s.count("}")
            if class_brace_depth <= 0:
                in_class = False
                current_class = None
                continue

            # Detect member variable declarations (non-function, non-pointer, no initialization)
            if type_kw.search(s) and "(" not in s and "*" not in s and "=" not in s:
                m = decl_pattern.search(s)
                if m:
                    var = m.group(2)
                    if var not in (
                        "main",
                        "if",
                        "while",
                        "for",
                        "return",
                        "struct",
                        "enum",
                        "union",
                    ):
                        class_members.setdefault(current_class, []).append((var, idx))

    # Check whether the constructor initializes these members
    for cls_name, members in class_members.items():
        if not members:
            continue
        # Find the initializer list in the constructor
        ctor_init_vars = set()
        in_ctor = False
        ctor_brace_depth = 0
        for idx, s in enumerate(lines, start=1):
            # Detect constructor definitions
            if re.search(rf"\b{re.escape(cls_name)}\s*\([^)]*\)\s*(?::|\{{)", s):
                in_ctor = True
                ctor_brace_depth = s.count("{") - s.count("}")
                # Check the initializer list: : member(value)
                init_list_match = re.search(r":\s*(.+)", s)
                if init_list_match:
                    init_text = init_list_match.group(1)
                    for var, _ in members:
                        if re.search(rf"\b{re.escape(var)}\s*\(", init_text):
                            ctor_init_vars.add(var)
                continue

            if in_ctor:
                ctor_brace_depth += s.count("{") - s.count("}")
                if ctor_brace_depth <= 0:
                    in_ctor = False
                    continue
                # Check the continuation lines of the initializer list
                for var, _ in members:
                    if var not in ctor_init_vars and re.search(
                        rf"\b{re.escape(var)}\s*\(", s
                    ):
                        ctor_init_vars.add(var)
                # Check assignments inside the constructor body
                for var, _ in members:
                    if var not in ctor_init_vars and re.search(
                        rf"\b{re.escape(var)}\s*=", s
                    ):
                        ctor_init_vars.add(var)

        # Check whether class methods have this->var assignments (to exclude false positives)
        method_assigned_vars = set()
        for idx, s in enumerate(lines, start=1):
            for var, _ in members:
                if var not in ctor_init_vars and re.search(
                    rf"\bthis\s*->\s*{re.escape(var)}\s*=", s
                ):
                    method_assigned_vars.add(var)

        # Report uninitialized members
        for var, line_no in members:
            if var not in ctor_init_vars and var not in method_assigned_vars:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="uninitialized",
                        pattern="uninitialized_member",
                        file=relpath,
                        line=line_no,
                        evidence=_strip_line(_safe_line(lines, line_no)),
                        description=f"Member variable {var} of class {cls_name} is not initialized in the constructor.",
                        suggestion="Initialize all member variables in the constructor initializer list, or use in-class initializers.",
                        confidence=0.7,
                        severity="medium",
                    )
                )

    return issues


def _rule_signed_to_unsigned(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect signed-to-unsigned conversion errors (CWE-195): (size_t)int_var or (unsigned)int_var.
    Exclude: a negative-value check before the conversion (if (len < 0) return;).
    """
    issues: List[Issue] = []
    # Explicit cast patterns: (size_t)var or (unsigned)var or (uint32_t)var
    cast_pattern = re.compile(
        r"\(\s*(size_t|unsigned|uint\d*_t|ULONG|DWORD)\s*\)\s*\(?\s*([A-Za-z_]\w*)\s*\)?"
    )

    for idx, s in enumerate(lines, start=1):
        t = s.lstrip()
        if t.startswith("#"):
            continue
        for m in cast_pattern.finditer(s):
            var = m.group(2)
            # Check the previous 5 lines for a negative-value check
            has_neg_check = False
            start = max(1, idx - 5)
            for j in range(start, idx):
                sj = _safe_line(lines, j)
                if re.search(rf"\bif\s*\([^)]*{re.escape(var)}\s*(<|<=)\s*0", sj):
                    has_neg_check = True
                    break
                if re.search(rf"\b{re.escape(var)}\s*(<|<=)\s*0", sj):
                    has_neg_check = True
                    break
            if has_neg_check:
                continue

            issues.append(
                Issue(
                    language="c/cpp",
                    category="type_confusion",
                    pattern="signed_unsigned_conversion",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"Signed variable {var} is cast to unsigned type {m.group(1)}; negative values will become huge positive numbers.",
                    suggestion="Check whether the value is negative before the conversion, or declare it as size_t/unsigned from the start.",
                    confidence=0.75,
                    severity="high",
                )
            )
    return issues


def _ast_divide_by_zero_check(
    lines: Sequence[str], relpath: str
) -> Optional[List[Issue]]:
    """Divide-by-zero detection based on the tree-sitter AST, replacing regex scanning.
    Advantage: it can recognize #define macro constants used as divisors, avoiding false positives.
    """
    try:
        import tree_sitter_c as tsc
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    # Ensure each line ends with \n for correct AST line numbers
    normalized = [(line if line.endswith("\n") else line + "\n") for line in lines]
    code = "".join(normalized)
    if not code.endswith("\n"):
        code += "\n"
    code_bytes = code.encode("utf-8")

    is_cpp = _is_cpp_file(relpath)
    try:
        if is_cpp:
            lang = Language(tscpp.language())
        else:
            lang = Language(tsc.language())
        parser = Parser(lang)
    except Exception:
        return None

    tree = parser.parse(code_bytes)
    root = tree.root_node

    # 1. Collect constant macros defined by #define (with non-zero constant values)
    const_macros: set = set()

    def _collect_const_macros(node):
        if node.type == "preproc_def":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if name_node and value_node:
                name = code_bytes[name_node.start_byte : name_node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                val = (
                    code_bytes[value_node.start_byte : value_node.end_byte]
                    .decode("utf-8", errors="replace")
                    .strip()
                )
                # The value is a non-zero numeric constant
                if val.isdigit() and val != "0":
                    const_macros.add(name)
        for child in node.children:
            _collect_const_macros(child)

    _collect_const_macros(root)

    # 2. Find all division/modulo expressions
    issues: List[Issue] = []

    def _extract_identifier(node):
        """Extract identifier names from nodes, handling nested cases."""
        if node.type == "identifier":
            return code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
        if node.type == "parenthesized_expression" and node.children:
            inner = node.children[1] if len(node.children) > 1 else node.children[0]
            return _extract_identifier(inner)
        return None

    def _find_div_mod(node):
        if node.type == "binary_expression":
            for child in node.children:
                if child.type in ("/", "%"):
                    right = node.child_by_field_name("right")
                    if right:
                        _check_divisor(right, node)
                    break
        for child in node.children:
            _find_div_mod(child)

    def _check_divisor(divisor_node, expr_node):
        line_num = expr_node.start_point[0] + 1
        divisor_name = _extract_identifier(divisor_node)

        # Numeric literals
        if divisor_node.type == "number_literal":
            val = code_bytes[divisor_node.start_byte : divisor_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            digits = "".join(c for c in val if c.isdigit())
            if digits and digits != "0":
                return  # Non-zero constant, safe

        # Macro constants
        if divisor_name and divisor_name in const_macros:
            return  # Macro is defined as a non-zero constant, safe

        # sizeof expressions
        if divisor_node.type == "sizeof_expression" or (
            divisor_name and divisor_name == "sizeof"
        ):
            return

        # Division within overflow checks: e.g. INT_MAX / obj_size, SIZE_MAX / count
        # Check whether the division expression's parent node is part of a comparison expression
        parent = expr_node.parent
        if parent and parent.type == "binary_expression":
            parent_op = parent.child_by_field_name("operator")
            if parent_op:
                op_text = code_bytes[parent_op.start_byte : parent_op.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if op_text in (">", ">=", "<", "<=", "==", "!="):
                    # Check whether the other side of the comparison contains INT_MAX/UINT_MAX/SIZE_MAX
                    left_of_cmp = parent.child_by_field_name("left")
                    right_of_cmp = parent.child_by_field_name("right")
                    for cmp_side in (left_of_cmp, right_of_cmp):
                        if cmp_side:
                            side_text = code_bytes[
                                cmp_side.start_byte : cmp_side.end_byte
                            ].decode("utf-8", errors="replace")
                            if re.search(
                                r"\b(INT_MAX|UINT_MAX|SIZE_MAX|LONG_MAX|ULONG_MAX)\b",
                                side_text,
                            ):
                                return  # Division within an overflow check, safe

        # Determine the divisor description
        divisor_desc = divisor_name or code_bytes[
            divisor_node.start_byte : divisor_node.end_byte
        ].decode("utf-8", errors="replace")

        # Check for nearby zero checks
        if divisor_name:
            has_zero_check = False
            start = max(1, line_num - 5)
            for j in range(start, line_num + 1):
                sj = _safe_line(lines, j)
                if re.search(
                    rf"\bif\s*\([^)]*{re.escape(divisor_name)}\s*(==|!=)\s*0", sj
                ):
                    has_zero_check = True
                    break
                if re.search(rf"\bif\s*\(\s*!?\s*{re.escape(divisor_name)}\s*\)", sj):
                    has_zero_check = True
                    break
                if re.search(rf"\b{re.escape(divisor_name)}\s*(==|!=)\s*0", sj):
                    has_zero_check = True
                    break
            if has_zero_check:
                return

        issues.append(
            Issue(
                language="c/cpp",
                category="arithmetic",
                pattern="divide_by_zero",
                file=relpath,
                line=line_num,
                evidence=_strip_line(lines[line_num - 1])
                if line_num <= len(lines)
                else "",
                description=f"Divisor {divisor_desc} may be zero; there is a divide-by-zero risk.",
                suggestion="Check whether the divisor is zero before division/modulo.",
                confidence=0.7,
                severity="high",
            )
        )

    _find_div_mod(root)
    return issues


def _rule_divide_by_zero(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect divide-by-zero errors (CWE-369): b is a variable in a/b or a%b and there is no nearby zero check.
    Exclude: divisor is a non-zero constant, a non-zero macro constant, or there is a nearby zero check (if (b == 0) / if (b) / if (!b)).
    Prefer tree-sitter AST detection, falling back to regex when unavailable.
    """
    # Prefer AST detection
    ast_issues = _ast_divide_by_zero_check(lines, relpath)
    if ast_issues is not None:
        return ast_issues

    # Fallback: regex detection
    issues: List[Issue] = []
    # Division/modulo patterns: var / var or var % var
    div_pattern = re.compile(r"\b([A-Za-z_]\w*)\s*/\s*([A-Za-z_]\w*)")
    mod_pattern = re.compile(r"\b([A-Za-z_]\w*)\s*%\s*([A-Za-z_]\w*)")

    for idx, s in enumerate(lines, start=1):
        t = s.lstrip()
        if t.startswith("#"):
            continue
        # Skip division inside string literals (e.g. char path[] = "/home/...")
        # Simple heuristic: the line contains quotes and the division is between quotes
        for pattern in (div_pattern, mod_pattern):
            for m in pattern.finditer(s):
                # Check whether the match is inside a string literal
                before = s[: m.start()]
                if before.count('"') % 2 == 1 or before.count("'") % 2 == 1:
                    continue
                divisor = m.group(2)
                # Exclude constant non-zero divisors
                if divisor.isdigit() and divisor != "0":
                    continue
                # Exclude sizeof(...)
                if "sizeof" in s[m.start() : m.end()]:
                    continue
                # Exclude division within overflow checks (e.g. INT_MAX / obj_size)
                if re.search(r"(INT_MAX|UINT_MAX|SIZE_MAX)\s*/\s", s):
                    continue
                # Check the previous 5 lines and the current line for a zero check
                has_zero_check = False
                start = max(1, idx - 5)
                for j in range(start, idx + 1):
                    sj = _safe_line(lines, j)
                    if re.search(
                        rf"\bif\s*\([^)]*{re.escape(divisor)}\s*(==|!=)\s*0", sj
                    ):
                        has_zero_check = True
                        break
                    if re.search(rf"\bif\s*\(\s*!?\s*{re.escape(divisor)}\s*\)", sj):
                        has_zero_check = True
                        break
                    if re.search(rf"\b{re.escape(divisor)}\s*(==|!=)\s*0", sj):
                        has_zero_check = True
                        break
                if has_zero_check:
                    continue

                issues.append(
                    Issue(
                        language="c/cpp",
                        category="arithmetic",
                        pattern="divide_by_zero",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Divisor {divisor} may be zero; there is a divide-by-zero risk.",
                        suggestion="Check whether the divisor is zero before division/modulo.",
                        confidence=0.7,
                        severity="high",
                    )
                )
    return issues


def _rule_compiler_security_check(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where compiler optimization may remove safety checks (CWE-733):
    A pointer variable has a NULL check but is not declared volatile, so the compiler may optimize away the check.
    Exclude: variables declared volatile.
    """
    issues: List[Issue] = []
    # Collect volatile variables
    volatile_vars = set()
    for s in lines:
        m = re.search(r"\bvolatile\s+.*?\b([A-Za-z_]\w*)\b", s)
        if m:
            volatile_vars.add(m.group(1))
        m = re.search(r"\bvolatile\s+char\s*\*\s*([A-Za-z_]\w*)", s)
        if m:
            volatile_vars.add(m.group(1))

    # Detect NULL check patterns: if (ptr == NULL) / if (!ptr) / if (ptr)
    null_check_pattern = re.compile(
        r"\bif\s*\(\s*(!\s*)?([A-Za-z_]\w*)\s*(==|!=)?\s*(NULL|0)?\s*\)"
    )

    for idx, s in enumerate(lines, start=1):
        t = s.lstrip()
        if t.startswith("#"):
            continue
        for m in null_check_pattern.finditer(s):
            var = m.group(2)
            if var in ("if", "while", "for", "return", "NULL", "0"):
                continue
            # Skip volatile variables
            if var in volatile_vars:
                continue
            # Check whether it is a pointer type (a *var or type *var declaration appears in the preceding lines)
            is_pointer = False
            start = max(1, idx - 10)
            for j in range(start, idx + 1):
                sj = _safe_line(lines, j)
                if re.search(rf"\b[A-Za-z_]\w*\s*\*\s*{re.escape(var)}\b", sj):
                    is_pointer = True
                    break
                if re.search(rf"\b{re.escape(var)}\s*\*\b", sj):
                    is_pointer = True
                    break
                # Pointers in function parameters
                if re.search(rf"\*\s*{re.escape(var)}\b", sj):
                    is_pointer = True
                    break
            if not is_pointer:
                continue

            issues.append(
                Issue(
                    language="c/cpp",
                    category="optimization",
                    pattern="compiler_security_check",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"The NULL check for pointer {var} may be removed by compiler optimization (not declared volatile).",
                    suggestion="Declare the pointer as volatile to prevent the compiler from optimizing away the safety check, or use a compiler barrier.",
                    confidence=0.6,
                    severity="medium",
                )
            )
    return issues


def _rule_alloc_size_overflow(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect simple cases where the allocation size may overflow: a malloc/calloc/realloc argument contains a multiplication expression and sizeof is not explicitly used.
    - Prefer database query for call_graph table
    - If database unavailable, fall back to regex matching
    """
    issues: List[Issue] = []
    ALLOC_FUNCS = {"malloc", "calloc", "realloc"}

    # Prefer database queries
    if database:
        import os

        reported = set()  # Deduplication: (line, pattern) is reported only once
        call_graph = database.get_call_graph()
        for call in call_graph:
            callee_name = call.get("callee_name", "")
            if callee_name.lower() not in ALLOC_FUNCS:
                continue
            caller_file = call.get("caller_file", "")
            if os.path.basename(caller_file) != os.path.basename(relpath):
                continue
            idx = call.get("caller_line", 0)
            if (idx, "alloc_size_overflow") in reported:
                continue
            if 0 < idx <= len(lines):
                s = lines[idx - 1]
            else:
                continue

            # Extract arguments
            try:
                m = re.search(rf"\b{callee_name}\s*\(", s, re.IGNORECASE)
                if not m:
                    continue
                start = s.index("(", m.start())
                end = s.find(")", start + 1)
                if end != -1:
                    args = s[start + 1 : end]
                    if "*" in args and not re.search(r"\bsizeof\s*\(", args):
                        # CWE-190 false-positive filtering: check the previous 5 lines for an overflow check
                        has_overflow_check = False
                        for j in range(max(1, idx - 5), idx):
                            sj = _safe_line(lines, j)
                            if (
                                re.search(
                                    r"\b(INT_MAX|UINT_MAX|SIZE_MAX|INT_MAX)\s*/",
                                    sj,
                                )
                                or re.search(
                                    r"\b\w+\s*<=\s*(INT_MAX|UINT_MAX|SIZE_MAX)\s*/",
                                    sj,
                                )
                                or re.search(
                                    r"\b\w+\s*<\s*(INT_MAX|UINT_MAX|SIZE_MAX)\s*/",
                                    sj,
                                )
                            ):
                                has_overflow_check = True
                                break
                        if has_overflow_check:
                            continue
                        reported.add((idx, "alloc_size_overflow"))
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="memory_mgmt",
                                pattern="alloc_size_overflow",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description="The malloc/calloc/realloc size calculation contains multiplication and does not explicitly use sizeof; there is an integer overflow risk.",
                                suggestion="Use sizeof to compute the element size and check whether the multiplication may overflow.",
                                confidence=0.6,
                                severity="medium",
                            )
                        )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_sec.checkers.c_checker",
                    function="_rule_alloc_size_overflow",
                )
                pass
        return issues

    # Skip the regex fallback when there is no database (avoid false positives)
    return issues


# ---------------------------
# Newly added rules such as null pointer / wild pointer / deadlock
# ---------------------------


# CWE-468: pointer arithmetic error regex
RE_PTRDIFF_SIZEOF = re.compile(
    r"\(s*\w+\s*-\s*\w+\s*\)\s*/\s*sizeof\s*\(", re.IGNORECASE
)


def _rule_pointer_arithmetic_error(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-468: Detect the error of dividing the result of pointer subtraction by sizeof(type) again.
    Pointer subtraction already divides by sizeof(type) automatically; dividing again is an error.
    Pattern: (ptr1 - ptr2) / sizeof(type)
    """
    issues: List[Issue] = []

    for idx, s in enumerate(lines, start=1):
        if RE_PTRDIFF_SIZEOF.search(s):
            issues.append(
                Issue(
                    language="c/cpp",
                    category="arithmetic",
                    pattern="pointer_arithmetic_error",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Dividing the result of pointer subtraction by sizeof again; pointer subtraction already divides by the element size automatically, so dividing again is an error.",
                    suggestion="Use (end - begin) directly as the element count; there is no need to divide by sizeof again.",
                    confidence=0.85,
                    severity="high",
                )
            )

    return issues


# CWE-667: deadlock risk - acquiring mutexes in different orders
RE_MUTEX_LOCK = re.compile(r"\b(\w+)\s*\.\s*lock\s*\(")


def _rule_deadlock_risk(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-667: Detect multiple functions in the same file acquiring mutexes in different orders, which may cause deadlock.
    Heuristic: collect the call order of mutex.lock() within each function, and detect order differences between functions.
    """
    issues: List[Issue] = []

    # Collect mutex acquisition order by function
    func_mutex_order: Dict[
        str, List[Tuple[str, int]]
    ] = {}  # func_name -> [(mutex_name, line)]
    current_func: Optional[str] = None
    brace_depth = 0

    for idx, s in enumerate(lines, start=1):
        # Detect function definitions
        func_match = re.search(
            r"\b(?:void|int|char|long|unsigned|bool|auto|static)\s+(\w+)\s*\(", s
        )
        if func_match:
            current_func = func_match.group(1)
            brace_depth = s.count("{") - s.count("}")
            if current_func not in func_mutex_order:
                func_mutex_order[current_func] = []
            continue

        if current_func:
            brace_depth += s.count("{") - s.count("}")
            if brace_depth <= 0:
                current_func = None
                continue

            # Detect mutex.lock() calls
            m = RE_MUTEX_LOCK.search(s)
            if m:
                mutex_name = m.group(1)
                func_mutex_order[current_func].append((mutex_name, idx))

    # Detect mutex acquisition order differences between functions
    func_names = [f for f in func_mutex_order if len(func_mutex_order[f]) >= 2]
    for i, f1 in enumerate(func_names):
        order1 = [m for m, _ in func_mutex_order[f1]]
        for f2 in func_names[i + 1 :]:
            order2 = [m for m, _ in func_mutex_order[f2]]
            # Check whether there is a common mutex but with a different order
            common = set(order1) & set(order2)
            if len(common) >= 2:
                # Get the order of the common mutex in the two functions
                idx1 = [order1.index(m) for m in common if m in order1]
                idx2 = [order2.index(m) for m in common if m in order2]
                # If the orders differ, report a deadlock risk
                if idx1 != idx2:
                    # Report the mutex acquisition in the first function
                    for mutex_name, line_no in func_mutex_order[f1]:
                        if mutex_name in common:
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="concurrency",
                                    pattern="deadlock_risk",
                                    file=relpath,
                                    line=line_no,
                                    evidence=_strip_line(lines[line_no - 1]),
                                    description=f"Functions {f1} and {f2} acquire mutex {mutex_name} in different orders, which may cause deadlock.",
                                    suggestion="Ensure all functions acquire mutexes in the same order, or use std::lock to acquire multiple mutexes at once.",
                                    confidence=0.75,
                                    severity="high",
                                )
                            )
                            break  # Report only once per function pair
                    break  # Report only once per function pair

    return issues


# CWE-783: assignment in conditions
RE_ASSIGN_IN_COND = re.compile(
    r"\b(?:if|while|for\s*\([^;]*;)\s*\([^)]*\b(\w+)\s*=\s*(\d+)\s*\)"
)


def _rule_assignment_in_condition(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-783: Detect assignments using = instead of == in if/while conditions.
    Exclude legitimate usages: patterns with a comparison operator such as if ((result = func()) != 0).
    """
    issues: List[Issue] = []

    for idx, s in enumerate(lines, start=1):
        # Detect assignments in if/while conditions
        # Pattern 1: if (x = 0) - assigning a constant, always false/true
        m = re.search(r"\b(?:if|while)\s*\(\s*\b(\w+)\s*=\s*(\d+)\s*\)", s)
        if m:
            var = m.group(1)
            val = m.group(2)
            # Exclude legitimate usages: if ((result = func()) != 0)
            # Check whether the assignment is within extra parentheses and has a comparison operator
            if re.search(r"\(\s*\(" + re.escape(var) + r"\s*=", s) and re.search(
                r"!=|==|<=|>=|<|>", s[s.index(var) :]
            ):
                continue
            issues.append(
                Issue(
                    language="c/cpp",
                    category="logic_error",
                    pattern="assignment_in_condition",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"Assignment '{var} = {val}' is used instead of comparison '{var} == {val}' in a conditional expression, which may cause a logic error.",
                    suggestion="If the intent is comparison, use the '==' operator; if the intent is to assign and then test, it is recommended to use extra parentheses to make the intent clear.",
                    confidence=0.8,
                    severity="high",
                )
            )

    return issues


def _ast_null_deref_check(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> Optional[List[Issue]]:
    """Null pointer dereference detection based on the tree-sitter AST, replacing regex scanning."""
    try:
        import tree_sitter_c as tsc
        import tree_sitter_cpp as tscpp
        from tree_sitter import Language, Parser
    except ImportError:
        return None

    # Ensure each line ends with \n for correct AST line numbers
    # (callers may pass splitlines() which strips \n)
    normalized = [(line if line.endswith("\n") else line + "\n") for line in lines]
    code = "".join(normalized)
    if not code.endswith("\n"):
        code += "\n"
    code_bytes = code.encode("utf-8")

    is_cpp = _is_cpp_file(relpath)
    try:
        if is_cpp:
            lang = Language(tscpp.language())
        else:
            lang = Language(tsc.language())
        parser = Parser(lang)
    except Exception:
        return None

    tree = parser.parse(code_bytes)
    root = tree.root_node
    # Note: has_error only means partial parse errors (e.g. macros),
    # the AST is still usable for analysis. Don't return None.

    stack_arrays: set[str] = set()
    stack_structs: set[str] = set()  # Non-pointer local variables; accessing with . is safe
    func_params: set[str] = set()  # Function parameters; the caller guarantees non-NULL
    global_vars: set[str] = set()  # Global variables

    def _extract_declarator_name(decl_node):
        """Extract variable names from declarator nodes, handling pointer_declarator/array_declarator nesting."""
        name = None
        is_pointer = False
        is_array = False
        node = decl_node
        while node:
            if node.type == "identifier":
                name = code_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="replace"
                )
                break
            elif node.type == "pointer_declarator":
                is_pointer = True
                for child in node.children:
                    if child.type in (
                        "identifier",
                        "array_declarator",
                        "pointer_declarator",
                    ):
                        node = child
                        break
                else:
                    break
            elif node.type == "array_declarator":
                is_array = True
                for child in node.children:
                    if child.type in (
                        "identifier",
                        "pointer_declarator",
                        "array_declarator",
                    ):
                        node = child
                        break
                else:
                    break
            else:
                break
        return name, is_pointer, is_array

    def _collect_declarations(node, is_global=False):
        """Collect declaration information: stack arrays, stack structs, function parameters, global variables."""
        if node.type == "parameter_declaration":
            decl_node = None
            for child in node.children:
                if child.type in (
                    "pointer_declarator",
                    "identifier",
                    "array_declarator",
                ):
                    decl_node = child
                    break
            if decl_node:
                name, is_pointer, is_array = _extract_declarator_name(decl_node)
                if name:
                    func_params.add(name)
                    if is_array:
                        stack_arrays.add(name)
        elif node.type == "declaration":
            parent = node.parent
            is_local = parent is not None and parent.type == "compound_statement"
            decl_nodes = []
            for child in node.children:
                if child.type in (
                    "identifier",
                    "pointer_declarator",
                    "array_declarator",
                    "init_declarator",
                ):
                    decl_nodes.append(child)
            for dn in decl_nodes:
                if dn.type == "init_declarator":
                    for ic in dn.children:
                        if ic.type in (
                            "pointer_declarator",
                            "identifier",
                            "array_declarator",
                        ):
                            name, is_pointer, is_array = _extract_declarator_name(ic)
                            if name:
                                if is_array:
                                    stack_arrays.add(name)
                                elif not is_pointer and is_local:
                                    stack_structs.add(name)
                                if not is_local:
                                    global_vars.add(name)
                            break
                else:
                    name, is_pointer, is_array = _extract_declarator_name(dn)
                    if name:
                        if is_array:
                            stack_arrays.add(name)
                        elif not is_pointer and is_local:
                            stack_structs.add(name)
                        if not is_local:
                            global_vars.add(name)
        for child in node.children:
            _collect_declarations(
                child, is_global=(is_global or node.type == "translation_unit")
            )

    _collect_declarations(root)

    # Collect NULL assignments to global variables within this function
    null_assigned_global_vars: set[str] = set()

    def _collect_null_assigned_global_vars(node):
        """Collect patterns that assign NULL to global variables: global_var = NULL"""
        if node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and left.type == "identifier":
                lhs_name = code_bytes[left.start_byte : left.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if lhs_name in global_vars and right:
                    rhs_text = (
                        code_bytes[right.start_byte : right.end_byte]
                        .decode("utf-8", errors="replace")
                        .strip()
                    )
                    if rhs_text in ("NULL", "0", "nullptr"):
                        null_assigned_global_vars.add(lhs_name)
        for child in node.children:
            _collect_null_assigned_global_vars(child)

    _collect_null_assigned_global_vars(root)

    # Track local pointer variables assigned from safe sources
    safe_assigned_vars: set[str] = set()

    def _is_safe_rhs(node):
        """Check if RHS of assignment is a safe (non-NULL) source."""
        if node.type == "pointer_expression":
            op = node.child_by_field_name("operator")
            if op and code_bytes[op.start_byte : op.end_byte].decode() == "&":
                return True  # address-of can never be NULL
        elif node.type == "cast_expression":
            for cc in node.children:
                if cc.type not in ("(", ")", "type_descriptor"):
                    inner_text = (
                        code_bytes[cc.start_byte : cc.end_byte]
                        .decode("utf-8", errors="replace")
                        .strip()
                    )
                    if inner_text in global_vars or inner_text in stack_arrays:
                        return True
                    if cc.type == "pointer_expression":
                        op2 = cc.child_by_field_name("operator")
                        if (
                            op2
                            and code_bytes[op2.start_byte : op2.end_byte].decode()
                            == "&"
                        ):
                            return True
                    if cc.type == "call_expression":
                        func2 = cc.child_by_field_name("function")
                        if func2:
                            fn = code_bytes[func2.start_byte : func2.end_byte].decode(
                                "utf-8", errors="replace"
                            )
                            if fn in ("alloca", "__builtin_alloca"):
                                return True
        elif node.type == "identifier":
            rhs_text = code_bytes[node.start_byte : node.end_byte].decode(
                "utf-8", errors="replace"
            )
            if rhs_text in global_vars or rhs_text in stack_arrays:
                return True
        elif node.type == "call_expression":
            # alloca() returns stack memory, can never be NULL
            func = node.child_by_field_name("function")
            if func:
                func_name = code_bytes[func.start_byte : func.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if func_name in ("alloca", "__builtin_alloca"):
                    return True
        return False

    def _collect_safe_assignments(node):
        """Track local pointer variables assigned from safe sources."""
        if node.type == "init_declarator":
            lhs_name = None
            rhs_is_safe = False
            for child in node.children:
                if child.type in ("pointer_declarator", "identifier"):
                    name_info = _extract_declarator_name(child)
                    if name_info and name_info[0]:
                        lhs_name = name_info[0]
                elif child.type not in ("pointer_declarator", "identifier", "="):
                    rhs_is_safe = _is_safe_rhs(child)
            if lhs_name and rhs_is_safe:
                safe_assigned_vars.add(lhs_name)
        elif node.type == "assignment_expression":
            left = node.child_by_field_name("left")
            right = node.child_by_field_name("right")
            if left and right and left.type == "identifier":
                lhs_name = code_bytes[left.start_byte : left.end_byte].decode(
                    "utf-8", errors="replace"
                )
                if _is_safe_rhs(right):
                    safe_assigned_vars.add(lhs_name)
        for child in node.children:
            _collect_safe_assignments(child)

    _collect_safe_assignments(root)

    protected_ranges: Dict[str, List[Tuple[int, int]]] = {}
    early_exit_vars: Dict[
        str, List[int]
    ] = {}  # var_name -> list of if_statement line numbers

    def _has_early_exit(block_node):
        text = code_bytes[block_node.start_byte : block_node.end_byte].decode(
            "utf-8", errors="replace"
        )
        return bool(re.search(r"\b(return|goto|exit|abort|throw)\b", text))

    def _extract_null_checked_vars(condition_node):
        checked = []

        def _find_null_checks(n, result_list=None):
            out = result_list if result_list is not None else checked
            if n.type == "binary_expression":
                left = n.child_by_field_name("left")
                right = n.child_by_field_name("right")
                op_node = n.child_by_field_name("operator")
                if left and right and op_node:
                    op = code_bytes[op_node.start_byte : op_node.end_byte].decode()
                    if op in ("==", "!="):
                        l_text = (
                            code_bytes[left.start_byte : left.end_byte]
                            .decode("utf-8", errors="replace")
                            .strip()
                        )
                        r_text = (
                            code_bytes[right.start_byte : right.end_byte]
                            .decode("utf-8", errors="replace")
                            .strip()
                        )
                        var_name = None

                        # Helper: extract var name from identifier or (var = expr) pattern
                        def _extract_var_from_cond(side_node):
                            if side_node.type == "identifier":
                                return code_bytes[
                                    side_node.start_byte : side_node.end_byte
                                ].decode("utf-8", errors="replace")
                            elif side_node.type == "parenthesized_expression":
                                # Handle (var = expr) pattern like while ((next = readdir()) != NULL)
                                for sc in side_node.children:
                                    if sc.type == "assignment_expression":
                                        lhs = sc.child_by_field_name("left")
                                        if lhs and lhs.type == "identifier":
                                            return code_bytes[
                                                lhs.start_byte : lhs.end_byte
                                            ].decode("utf-8", errors="replace")
                            return None

                        if r_text in ("NULL", "0", "nullptr"):
                            var_name = _extract_var_from_cond(left)
                        elif l_text in ("NULL", "0", "nullptr"):
                            var_name = _extract_var_from_cond(right)
                        if var_name:
                            if op == "!=":
                                out.append((var_name, "consequence"))
                            else:
                                out.append((var_name, "alternative"))
                    elif op == "&&":
                        # Short-circuit: if left is true, right is evaluated
                        # Left vars checked as "consequence" protect right-side derefs
                        left_checks = []
                        _find_null_checks(left, left_checks)
                        for vname, branch in left_checks:
                            if branch == "consequence":
                                # var != NULL on left: var is safe on right
                                out.append((vname, "consequence"))
                        # Also: bare identifier on left means truthy check (var != NULL)
                        if left.type == "identifier":
                            vname = code_bytes[left.start_byte : left.end_byte].decode(
                                "utf-8", errors="replace"
                            )
                            out.append((vname, "consequence"))
                        # Recurse into right for additional checks
                        _find_null_checks(right, out)
                        return  # Already recursed; skip default child traversal
                    elif op == "||":
                        # Short-circuit: if left is true, right is NOT evaluated
                        # Left vars checked as "alternative" (!var / var == NULL) protect right-side derefs
                        left_checks = []
                        _find_null_checks(left, left_checks)
                        for vname, branch in left_checks:
                            if branch == "alternative":
                                # !var on left: var is NULL -> right only runs if var is NOT NULL
                                out.append((vname, "consequence"))
                        # Recurse into right for additional checks
                        _find_null_checks(right, out)
                        return  # Already recursed; skip default child traversal
            elif n.type == "unary_expression":
                op_node = n.child_by_field_name("operator")
                # tree-sitter-c: unary_expression may not have "operand" field
                # (same issue as pointer_expression); find identifier among named children
                operand = n.child_by_field_name("operand")
                if operand is None:
                    for child in n.children:
                        if child.is_named and child.type == "identifier":
                            operand = child
                            break
                if op_node and operand:
                    op = code_bytes[op_node.start_byte : op_node.end_byte].decode()
                    if op == "!" and operand.type == "identifier":
                        var_name = code_bytes[
                            operand.start_byte : operand.end_byte
                        ].decode("utf-8", errors="replace")
                        out.append((var_name, "alternative"))
            elif n.type == "identifier":
                parent = n.parent
                # C: bare identifier in parenthesized_expression of if/while
                # C++: bare identifier in condition_clause of if/while
                if parent and parent.type in (
                    "parenthesized_expression",
                    "condition_clause",
                ):
                    gp = parent.parent
                    if gp and gp.type in ("if_statement", "while_statement"):
                        if parent.child_count <= 3:
                            var_name = code_bytes[n.start_byte : n.end_byte].decode(
                                "utf-8", errors="replace"
                            )
                            out.append((var_name, "consequence"))
                # bare identifier in assert() argument: assert(ptr) means ptr is non-NULL
                elif parent and parent.type == "argument_list":
                    gp = parent.parent
                    if gp and gp.type == "call_expression":
                        func_node = gp.child_by_field_name("function")
                        if func_node and func_node.type == "identifier":
                            func_name = code_bytes[
                                func_node.start_byte : func_node.end_byte
                            ].decode("utf-8", errors="replace")
                            if func_name == "assert":
                                var_name = code_bytes[n.start_byte : n.end_byte].decode(
                                    "utf-8", errors="replace"
                                )
                                out.append((var_name, "consequence"))
            for child in n.children:
                _find_null_checks(child, out)

        _find_null_checks(condition_node)
        return checked

    def _collect_null_protections(node):
        # Handle assert() calls: assert(p != NULL) means p is safe after this line
        # assert is equivalent to if (!(condition)) abort();
        if node.type == "expression_statement":
            for child in node.children:
                if child.type == "call_expression":
                    func_name_node = child.child_by_field_name("function")
                    if func_name_node and func_name_node.type == "identifier":
                        func_name = code_bytes[
                            func_name_node.start_byte : func_name_node.end_byte
                        ].decode("utf-8", errors="replace")
                        if func_name == "assert":
                            args = child.child_by_field_name("arguments")
                            if args:
                                # Extract the first argument as the condition
                                for arg in args.children:
                                    if arg.is_named and arg.type != ",":
                                        checked_vars = _extract_null_checked_vars(arg)
                                        for var_name, safe_branch in checked_vars:
                                            # assert(p != NULL): p is safe after assert (consequence)
                                            # assert(p): p is truthy (non-NULL) after assert (consequence)
                                            if safe_branch == "consequence":
                                                # assert acts as early exit for the negation,
                                                # so var is safe from assert line onwards
                                                early_exit_vars.setdefault(
                                                    var_name, []
                                                ).append(node.start_point[0] + 1)
                                        break  # Only process first argument
        if node.type in ("if_statement", "while_statement"):
            condition = None
            for child in node.children:
                # C uses parenthesized_expression; C++ may use condition_clause
                if child.type in ("parenthesized_expression", "condition_clause"):
                    condition = child
                    break
            if condition:
                # Recognize bounds check: if (idx >= 0 && idx < 10) etc.
                # Add bounds-checked variables to protected_ranges for subscript_expression protection
                cond_text = code_bytes[
                    condition.start_byte : condition.end_byte
                ].decode("utf-8", errors="replace")
                bounds_check_match = re.finditer(
                    r"\b(\w+)\s*>=\s*\d+\s*&&\s*\1\s*<\s*\d+",
                    cond_text,
                )
                bounds_check_match2 = re.finditer(
                    r"\b(\w+)\s*>=\s*\d+\s*&&\s*\1\s*<=\s*\d+",
                    cond_text,
                )
                consequence = None
                for child in node.children:
                    if child.type == "compound_statement":
                        consequence = child
                        break
                if consequence:
                    cstart = consequence.start_point[0] + 1
                    cend = consequence.end_point[0] + 1
                    for m in list(bounds_check_match) + list(bounds_check_match2):
                        bvar = m.group(1)
                        if bvar not in protected_ranges:
                            protected_ranges[bvar] = []
                        protected_ranges[bvar].append((cstart, cend))

                checked_vars = _extract_null_checked_vars(condition)
                for var_name, safe_branch in checked_vars:
                    if safe_branch == "consequence":
                        consequence = None
                        for child in node.children:
                            if child.type == "compound_statement":
                                consequence = child
                                break
                        if consequence:
                            start = consequence.start_point[0] + 1
                            end = consequence.end_point[0] + 1
                            if var_name not in protected_ranges:
                                protected_ranges[var_name] = []
                            protected_ranges[var_name].append((start, end))
                            # If consequence has early exit, var is also safe after the if block
                            # e.g. if ((NULL == p) || ...) { return; } -> p safe after if
                            if _has_early_exit(consequence):
                                early_exit_vars.setdefault(var_name, []).append(
                                    node.start_point[0] + 1
                                )
                        else:
                            # No compound_statement: e.g. if (p) return;
                            if _has_early_exit(node):
                                early_exit_vars.setdefault(var_name, []).append(
                                    node.start_point[0] + 1
                                )
                    elif safe_branch == "alternative":
                        # var == NULL / !var: if consequence has early exit,
                        # var is safe after the if block
                        consequence = None
                        for child in node.children:
                            if child.type == "compound_statement":
                                consequence = child
                                break
                        if consequence:
                            if _has_early_exit(consequence):
                                early_exit_vars.setdefault(var_name, []).append(
                                    node.start_point[0] + 1
                                )
                        else:
                            # No compound_statement: check if_statement's direct
                            # children for early exit (e.g. if (!p) return;)
                            if _has_early_exit(node):
                                early_exit_vars.setdefault(var_name, []).append(
                                    node.start_point[0] + 1
                                )
        for child in node.children:
            _collect_null_protections(child)

    _collect_null_protections(root)

    deref_points: List[Tuple[str, int, str]] = []

    def _is_short_circuit_protected(deref_node, var_name):
        """Check if a deref of var_name inside a condition is protected by &&/|| short-circuit."""
        n = deref_node.parent
        while n:
            if n.type == "binary_expression":
                op_node = n.child_by_field_name("operator")
                if op_node:
                    op = code_bytes[op_node.start_byte : op_node.end_byte].decode()
                    if op in ("&&", "||"):
                        left = n.child_by_field_name("left")
                        right = n.child_by_field_name("right")
                        if left and right:
                            # Is deref_node on the right side of this &&/||?
                            if (
                                deref_node.start_byte >= right.start_byte
                                and deref_node.end_byte <= right.end_byte
                            ):
                                # Check if left side protects var_name
                                # Simplified inline check (no dependency on _find_null_checks closure)
                                left_text = (
                                    code_bytes[left.start_byte : left.end_byte]
                                    .decode("utf-8", errors="replace")
                                    .strip()
                                )
                                if op == "&&":
                                    # bare identifier on left means truthy (var != NULL)
                                    if (
                                        left.type == "identifier"
                                        and left_text == var_name
                                    ):
                                        return True
                                    # var != NULL on left
                                    if left.type == "binary_expression":
                                        lop = left.child_by_field_name("operator")
                                        if lop:
                                            lop_text = code_bytes[
                                                lop.start_byte : lop.end_byte
                                            ].decode()
                                            if lop_text == "!=":
                                                ll = left.child_by_field_name("left")
                                                lr = left.child_by_field_name("right")
                                                if ll and lr:
                                                    ll_text = (
                                                        code_bytes[
                                                            ll.start_byte : ll.end_byte
                                                        ]
                                                        .decode(
                                                            "utf-8", errors="replace"
                                                        )
                                                        .strip()
                                                    )
                                                    lr_text = (
                                                        code_bytes[
                                                            lr.start_byte : lr.end_byte
                                                        ]
                                                        .decode(
                                                            "utf-8", errors="replace"
                                                        )
                                                        .strip()
                                                    )
                                                    if (
                                                        lr_text
                                                        in ("NULL", "0", "nullptr")
                                                        and ll_text == var_name
                                                    ):
                                                        return True
                                                    if (
                                                        ll_text
                                                        in ("NULL", "0", "nullptr")
                                                        and lr_text == var_name
                                                    ):
                                                        return True
                                elif op == "||":
                                    # !var on left means var == NULL -> right only runs if var non-NULL
                                    if left.type == "unary_expression":
                                        lop = left.child_by_field_name("operator")
                                        if (
                                            lop
                                            and code_bytes[
                                                lop.start_byte : lop.end_byte
                                            ].decode()
                                            == "!"
                                        ):
                                            # Find operand (may not have field name)
                                            loperand = left.child_by_field_name(
                                                "operand"
                                            )
                                            if loperand is None:
                                                for ch in left.children:
                                                    if (
                                                        ch.is_named
                                                        and ch.type == "identifier"
                                                    ):
                                                        loperand = ch
                                                        break
                                            if (
                                                loperand
                                                and loperand.type == "identifier"
                                            ):
                                                lo_text = code_bytes[
                                                    loperand.start_byte : loperand.end_byte
                                                ].decode("utf-8", errors="replace")
                                                if lo_text == var_name:
                                                    return True
                                    # var == NULL on left
                                    if left.type == "binary_expression":
                                        lop = left.child_by_field_name("operator")
                                        if lop:
                                            lop_text = code_bytes[
                                                lop.start_byte : lop.end_byte
                                            ].decode()
                                            if lop_text == "==":
                                                ll = left.child_by_field_name("left")
                                                lr = left.child_by_field_name("right")
                                                if ll and lr:
                                                    ll_text = (
                                                        code_bytes[
                                                            ll.start_byte : ll.end_byte
                                                        ]
                                                        .decode(
                                                            "utf-8", errors="replace"
                                                        )
                                                        .strip()
                                                    )
                                                    lr_text = (
                                                        code_bytes[
                                                            lr.start_byte : lr.end_byte
                                                        ]
                                                        .decode(
                                                            "utf-8", errors="replace"
                                                        )
                                                        .strip()
                                                    )
                                                    if (
                                                        lr_text
                                                        in ("NULL", "0", "nullptr")
                                                        and ll_text == var_name
                                                    ):
                                                        return True
                                                    if (
                                                        ll_text
                                                        in ("NULL", "0", "nullptr")
                                                        and lr_text == var_name
                                                    ):
                                                        return True
            # Stop at condition boundary
            if n.type in ("if_statement", "while_statement"):
                break
            n = n.parent
        return False

    def _is_inside_sizeof(node):
        """Check if node is inside a sizeof expression (sizeof does not dereference)."""
        n = node.parent
        while n:
            if n.type == "sizeof_expression":
                return True
            # Stop at statement boundaries to avoid excessive traversal
            if n.type in (
                "expression_statement",
                "if_statement",
                "while_statement",
                "for_statement",
                "return_statement",
            ):
                break
            n = n.parent
        return False

    def _collect_implicit_deref_arg(arg_node, call_node):
        """Extract pointer variable names from the argument nodes of call_expression, marking them as implicit dereferences."""
        if arg_node.type == "identifier":
            var_name = code_bytes[arg_node.start_byte : arg_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            # Stack arrays cannot be NULL, skip
            if var_name in stack_arrays:
                return
            # If the same call expression contains sizeof(var), then var is an array, not a pointer
            call_text = code_bytes[call_node.start_byte : call_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            if re.search(rf"\bsizeof\s*\(\s*{re.escape(var_name)}\s*\)", call_text):
                return
            if _is_short_circuit_protected(arg_node, var_name):
                return
            line = call_node.start_point[0] + 1
            evidence = code_bytes[call_node.start_byte : call_node.end_byte].decode(
                "utf-8", errors="replace"
            )
            deref_points.append((var_name, line, evidence))
        elif arg_node.type == "field_expression":
            # p->member passed as argument: extract base pointer
            op_node = arg_node.child_by_field_name("operator")
            if (
                op_node
                and code_bytes[op_node.start_byte : op_node.end_byte].decode() == "->"
            ):
                base_arg = arg_node.child_by_field_name("argument")
                if base_arg and base_arg.type == "identifier":
                    var_name = code_bytes[
                        base_arg.start_byte : base_arg.end_byte
                    ].decode("utf-8", errors="replace")
                    if not _is_short_circuit_protected(arg_node, var_name):
                        line = call_node.start_point[0] + 1
                        evidence = code_bytes[
                            call_node.start_byte : call_node.end_byte
                        ].decode("utf-8", errors="replace")
                        deref_points.append((var_name, line, evidence))
        elif arg_node.type == "pointer_expression":
            # *p passed as argument: extract operand
            op_node = arg_node.child_by_field_name("operator")
            if (
                op_node
                and code_bytes[op_node.start_byte : op_node.end_byte].decode() == "*"
            ):
                for child in arg_node.children:
                    if child.is_named and child.type == "identifier":
                        var_name = code_bytes[child.start_byte : child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        if not _is_short_circuit_protected(arg_node, var_name):
                            line = call_node.start_point[0] + 1
                            evidence = code_bytes[
                                call_node.start_byte : call_node.end_byte
                            ].decode("utf-8", errors="replace")
                            deref_points.append((var_name, line, evidence))
                        break

    def _collect_derefs(node):
        if node.type == "pointer_expression":
            # tree-sitter-c: both * (deref) and & (address-of) are pointer_expression
            # Only collect * (dereference), skip & (address-of which is safe)
            op_node = node.child_by_field_name("operator")
            is_deref = True
            if op_node:
                op_text = code_bytes[op_node.start_byte : op_node.end_byte].decode()
                if op_text == "&":
                    is_deref = False  # address-of, not dereference
            if not is_deref:
                pass  # &var is not a dereference
            else:
                # tree-sitter-c: pointer_expression children are [* identifier],
                # no "operand" field; find identifier among named children
                var_name = None
                for child in node.children:
                    if child.is_named and child.type == "identifier":
                        var_name = code_bytes[child.start_byte : child.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        break
                if var_name:
                    if _is_short_circuit_protected(node, var_name):
                        pass  # protected by &&/|| short-circuit in condition
                    else:
                        line = node.start_point[0] + 1
                        # *p write also counts as dereference (*p = value crashes too if p is NULL)
                        evidence = code_bytes[node.start_byte : node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        deref_points.append((var_name, line, evidence))
        elif node.type == "field_expression":
            # Distinguish `.` (stack struct access, cannot be NULL) vs `->` (pointer dereference)
            operator_node = node.child_by_field_name("operator")
            is_arrow = False
            if operator_node:
                op_text = code_bytes[
                    operator_node.start_byte : operator_node.end_byte
                ].decode()
                is_arrow = op_text == "->"
            if is_arrow:
                # `->` is a pointer dereference, extract the variable name on the argument side
                arg_node = node.child_by_field_name("argument")
                if arg_node and arg_node.type == "identifier":
                    var_name = code_bytes[
                        arg_node.start_byte : arg_node.end_byte
                    ].decode("utf-8", errors="replace")
                    if _is_short_circuit_protected(node, var_name):
                        pass
                    else:
                        line = node.start_point[0] + 1
                        evidence = code_bytes[node.start_byte : node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        deref_points.append((var_name, line, evidence))
            # `.` accesses a stack struct, cannot be NULL, do not collect
        elif node.type == "subscript_expression":
            # sizeof(arr[i]) does not actually dereference, sizeof only computes the type size
            if _is_inside_sizeof(node):
                for child in node.children:
                    _collect_derefs(child)
                return
            # arr[i] or next->d_name[0]
            base = node.child_by_field_name("argument")
            if base:
                if base.type == "identifier":
                    var_name = code_bytes[base.start_byte : base.end_byte].decode(
                        "utf-8", errors="replace"
                    )
                    if _is_short_circuit_protected(node, var_name):
                        pass
                    elif var_name in func_params:
                        # Function parameter array: if the index is within bounds check protection range, skip null deref detection
                        # e.g. void safe(int* arr, int idx) { if (idx >= 0 && idx < 10) { arr[idx] = 42; } }
                        index_node = node.child_by_field_name("index")
                        has_bounds_protection = False
                        if index_node and index_node.type == "identifier":
                            idx_name = code_bytes[
                                index_node.start_byte : index_node.end_byte
                            ].decode("utf-8", errors="replace")
                            line = node.start_point[0] + 1
                            if any(
                                start <= line <= end
                                for start, end in protected_ranges.get(idx_name, [])
                            ):
                                has_bounds_protection = True
                        if has_bounds_protection:
                            pass  # Index is protected by bounds check, null check for array parameter should be at the caller
                        else:
                            line = node.start_point[0] + 1
                            evidence = code_bytes[
                                node.start_byte : node.end_byte
                            ].decode("utf-8", errors="replace")
                            deref_points.append((var_name, line, evidence))
                    else:
                        line = node.start_point[0] + 1
                        evidence = code_bytes[node.start_byte : node.end_byte].decode(
                            "utf-8", errors="replace"
                        )
                        deref_points.append((var_name, line, evidence))
                elif base.type == "field_expression":
                    # next->d_name[0]: extract the base pointer of field_expression
                    base_arg = base.child_by_field_name("argument")
                    if base_arg and base_arg.type == "identifier":
                        var_name = code_bytes[
                            base_arg.start_byte : base_arg.end_byte
                        ].decode("utf-8", errors="replace")
                        if _is_short_circuit_protected(node, var_name):
                            pass
                        else:
                            line = node.start_point[0] + 1
                            evidence = code_bytes[
                                node.start_byte : node.end_byte
                            ].decode("utf-8", errors="replace")
                            deref_points.append((var_name, line, evidence))
        elif node.type == "call_expression":
            # Implicit dereference: pointer arguments of whitelisted functions are dereferenced inside the function
            # e.g. strcpy(p, "hello") will dereference p
            func_node = node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                func_name = code_bytes[
                    func_node.start_byte : func_node.end_byte
                ].decode("utf-8", errors="replace")
                # Determine which parameter positions need to be checked
                # key=function name, value=list of parameter indices to check (0-based)
                # -1 means "all arguments after the format string" (printf family)
                _deref_arg_indices = {
                    # String operations: the 1st argument (destination buffer) is dereferenced
                    "strcpy": [0],
                    "strncpy": [0],
                    "strcat": [0],
                    "strncat": [0],
                    # Memory operations: the 1st argument is dereferenced
                    "memcpy": [0],
                    "memmove": [0],
                    "memset": [0],
                    # String queries: the 1st argument (source string) is dereferenced
                    "strlen": [0],
                    "strcmp": [0, 1],
                    "strncmp": [0, 1],
                    "strchr": [0],
                    "strrchr": [0],
                    "strstr": [0],
                    "strtok": [0],
                    # I/O: relevant arguments are dereferenced
                    "puts": [0],
                    "fputs": [0],
                    "gets": [0],
                    "fgets": [0],
                    # free: free(NULL) is safe, does not dereference the pointer, do not mark as implicit dereference
                    # printf family: -1 means all arguments after the format string
                    "printf": [-1],
                    "fprintf": [-1],
                    "sprintf": [-1],
                    "snprintf": [-1],
                    "syslog": [-1],
                }
                arg_indices = _deref_arg_indices.get(func_name)
                if arg_indices is not None:
                    # Collect arguments in argument_list
                    arg_list = None
                    for child in node.children:
                        if child.type == "argument_list":
                            arg_list = child
                            break
                    if arg_list:
                        args = [c for c in arg_list.children if c.is_named]
                        for idx in arg_indices:
                            if idx == -1:
                                # printf family: skip the format string (0th argument), check all arguments after it
                                for ai in range(1, len(args)):
                                    _collect_implicit_deref_arg(args[ai], node)
                            elif idx < len(args):
                                _collect_implicit_deref_arg(args[idx], node)
        for child in node.children:
            _collect_derefs(child)

    _collect_derefs(root)

    issues: List[Issue] = []
    reported_vars: set[str] = set()

    for var_name, line, evidence in deref_points:
        if var_name == "this":
            continue
        if var_name in stack_arrays:
            continue
        if var_name in stack_structs:
            continue
        # Do not skip func_params: function parameters are exactly the most likely to be NULL, need detection
        # But for array parameters in subscript_expression, if the index is within bounds check protection range, skip (see _collect_derefs)
        if var_name in global_vars:
            # Global variables are only reported when explicitly assigned to NULL within this function
            if var_name not in null_assigned_global_vars:
                continue
        if var_name in safe_assigned_vars:
            continue
        if var_name in early_exit_vars and any(
            line > check_line for check_line in early_exit_vars[var_name]
        ):
            continue
        in_protected = any(
            start <= line <= end for start, end in protected_ranges.get(var_name, [])
        )
        if in_protected:
            continue
        if var_name in reported_vars:
            continue
        reported_vars.add(var_name)
        issues.append(
            Issue(
                language="c/cpp",
                category="memory_mgmt",
                pattern="possible_null_deref",
                file=relpath,
                line=line,
                evidence=_strip_line(evidence),
                description=f"Pointer {var_name} may have been dereferenced without NULL check protection, posing a null pointer dereference risk.",
                suggestion="Perform a NULL check before using the pointer; ensure all return/assignment paths have performed validity checks.",
                confidence=0.7,
                severity="high",
                var_name=var_name,
            )
        )

    return issues


def _rule_possible_null_deref(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect null pointer dereference:
    - Occurrence of p->... or *p access, with no obvious NULL check nearby.
    - Occurrence of arr[...] array access, with no obvious NULL check nearby.
    Note: Prefer taint analysis, fall back to heuristic implementation on failure.
    Accuracy optimizations:
    - For *p detection, introduce context determination to exclude false positives from multiplication expressions a * p as much as possible
     (only when * appears in a typical dereference context, such as line start/after parenthesis/after comma/after assignment operator/after semicolon/after colon/after bracket/logical not/address-of/after another dereference)
    """
    issues: List[Issue] = []

    # Prefer AST detection
    ast_issues = _ast_null_deref_check(lines, relpath, database)
    if ast_issues is not None:
        return ast_issues

    # Get null_checks information from database (used for false positive filtering)
    db_null_checks: Dict[str, List[int]] = {}
    # Collect function parameters (NULL checks for parameters should be at the caller)
    func_params: set[str] = set()
    # Array variable names queried from database (pending merge into stack_arrays)
    db_array_vars: set[str] = set()
    if database is not None:
        try:
            # Query null_checks directly from database
            flow_nodes = database.get_data_flow_by_file(relpath)
            for node in flow_nodes:
                if node.get("use_type") == "null_check":
                    var_name = node.get("var_name", "")
                    line = node.get("line", 0)
                    if var_name and line > 0:
                        if var_name not in db_null_checks:
                            db_null_checks[var_name] = []
                        db_null_checks[var_name].append(line)
                # Collect function parameters
                if (
                    node.get("node_type") == "param_in"
                    or node.get("value_source") == "parameter"
                ):
                    var_name = node.get("var_name", "")
                    if var_name:
                        func_params.add(var_name)
            # Query array variables of the current file from symbols table (type_name ends with [])
            try:
                file_symbols = database.get_symbols_by_file(relpath)
                # Path mismatch fallback: database may store absolute paths, while relpath is relative
                if not file_symbols:
                    import os

                    abs_path = os.path.abspath(relpath)
                    file_symbols = database.get_symbols_by_file(abs_path)
                if not file_symbols:
                    # Finally try LIKE suffix matching
                    with database._get_connection() as _conn:
                        _cur = _conn.cursor()
                        _cur.execute(
                            "SELECT * FROM symbols WHERE file_path LIKE ? ORDER BY line_start",
                            ("%" + relpath,),
                        )
                        file_symbols = [dict(row) for row in _cur.fetchall()]
                for sym in file_symbols:
                    if sym.get("kind") == "variable" and (
                        sym.get("type_name", "").endswith("[]")
                    ):
                        sym_name = sym.get("name", "")
                        if sym_name:
                            db_array_vars.add(sym_name)
            except Exception:
                pass
        except Exception:
            pass
    # Prefer taint analysis first
    try:
        import haijunbot.haijunbot_sec.taint_analyzer as taint_analyzer

        analyzer = taint_analyzer.TaintAnalyzerFactory.create("joern")
        if analyzer and analyzer.is_available():
            code = "\n".join(lines)
            rule = taint_analyzer.get_rule("null_deref")
            if rule:
                taint_paths = rule.check(analyzer, code, relpath)
                for path in taint_paths:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="possible_null_deref",
                            file=relpath,
                            line=path.line_number,
                            evidence=path.code_snippet,
                            description=path.description,
                            suggestion="Check whether it is NULL before using the pointer to avoid null pointer dereference.",
                            confidence=0.85,
                            severity="high",
                        )
                    )
            # Taint analysis succeeded, return result
            if issues:
                return issues
        # Taint analysis unavailable, fall back to heuristic detection
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.c_checker",
            function="_rule_possible_null_deref",
        )
        pass
    # Heuristic detection (fallback)
    re_arrow = re.compile(r"\b([A-Za-z_]\w*)\s*->")
    re_star = re.compile(r"(?<!\w)\*\s*([A-Za-z_]\w*)\b")
    # Added: detect array access arr[...], exclude array declarations in type declarations
    re_array_access = re.compile(r"\b([A-Za-z_]\w*)\s*\[")
    type_kw = re.compile(
        r"\b(typedef|struct|union|enum|class|char|int|long|short|void|size_t|ssize_t|FILE)\b"
    )

    def _is_deref_context(line: str, star_pos: int) -> bool:
        k = star_pos - 1
        while k >= 0 and line[k].isspace():
            k -= 1
        if k < 0:
            return True
        # Typical set of leading characters that can be regarded as dereference
        return line[k] in "(*,=:{;[!&"

    def _is_array_declaration(line: str, var_pos: int) -> bool:
        """Determine whether it is an array declaration rather than an array access"""
        # Check whether there is a type keyword before the variable and a semicolon on the same line (possibly a declaration)
        before = line[:var_pos]
        after = line[var_pos:]
        # If there is a type keyword before and a semicolon after, it may be a declaration
        if type_kw.search(before) and ";" in after:
            # Further check: if followed by ] then ; or =, more likely a declaration
            if re.search(r"\]\s*[;=]", after):
                return True
        return False

    # Precompiled regular expressions for safe context detection
    re_malloc_like = re.compile(
        r"\b(malloc|calloc|realloc|new|kmalloc|vmalloc|kzalloc)\b"
    )
    re_static_global = re.compile(r"^\s*(static|extern)\s+.*\b([A-Za-z_]\w*)\b")
    re_const_str = re.compile(r"\bconst\s+char\s*\*\s*([A-Za-z_]\w*)\b")
    # Smart pointer types (cannot be NULL)
    re_smart_ptr = re.compile(
        r"\b(auto|std::unique_ptr|std::shared_ptr|std::weak_ptr)\b"
    )
    # delete/delete[] statements (not dereferences)
    re_delete_stmt = re.compile(r"^\s*delete\s*\[?\s*\]?\s*([A-Za-z_]\w*)")

    # Collect static/global variables and constant string pointers (usually already ensured non-null)
    safe_vars: set[str] = set()
    # Collect stack array variables (stack arrays cannot be NULL)
    stack_arrays: set[str] = set()
    # Merge array variables queried from database
    stack_arrays.update(db_array_vars)
    # Collect smart pointer variables (cannot be NULL)
    smart_ptr_vars: set[str] = set()
    # Collect C++ container variables (value types, cannot be NULL)
    container_vars: set[str] = set()
    re_cpp_container = re.compile(
        r"std::(?:array|vector|deque|list|set|map|unordered_set|unordered_map)[^>]*>\s*&?\s*([A-Za-z_]\w*)"
    )
    # Stack array declaration pattern: type variable_name[size]
    # Support standard C types + uppercase typedef style (such as CHAR, UCHAR, UINT, etc.)
    re_stack_array = re.compile(
        r"\b(char|int|long|short|void|unsigned|signed|float|double|size_t|ssize_t|uint\d*_t|int\d*_t|[A-Z][A-Z0-9_]*)\s+(?:\*\s*)*([A-Za-z_]\w*)\s*\["
    )
    for line in lines:
        m_static = re_static_global.search(line)
        if m_static:
            safe_vars.add(m_static.group(2))
        m_const = re_const_str.search(line)
        if m_const:
            safe_vars.add(m_const.group(1))
        # Detect stack array declaration
        m_array = re_stack_array.search(line)
        if m_array:
            stack_arrays.add(m_array.group(2))
        # Detect smart pointer declaration
        m_smart = re_smart_ptr.search(line)
        if m_smart:
            # Extract variable name: auto var = ... or std::unique_ptr<T> var
            m_var = re.search(r"\b([A-Za-z_]\w*)\s*=", line)
            if m_var:
                smart_ptr_vars.add(m_var.group(1))
            else:
                # Also extract smart pointer variable names in function parameters
                m_param = re.search(
                    r"std::(?:unique_ptr|shared_ptr|weak_ptr)[^>]*>\s*&?\s*([A-Za-z_]\w*)",
                    line,
                )
                if m_param:
                    smart_ptr_vars.add(m_param.group(1))
        # Detect C++ container variables (value types, cannot be NULL)
        m_container = re_cpp_container.search(line)
        if m_container:
            container_vars.add(m_container.group(1))
        # Detect delete[] statements, record the deleted variable
        m_delete = re_delete_stmt.search(line)
        if m_delete:
            # delete[] var is not a dereference, skip
            pass

    def _is_just_allocated(var: str, lines: Sequence[str], line_no: int) -> bool:
        """Check whether the variable was just successfully allocated (the previous 1-2 lines have allocation functions like malloc/new)"""
        for offset in range(1, 3):  # Check the previous 1-2 lines
            prev_idx = line_no - offset
            if prev_idx < 1 or prev_idx > len(lines):
                continue
            prev_line = lines[prev_idx - 1]
            # Check whether there is an allocation function call and the variable name appears on the left side of an assignment
            if re_malloc_like.search(prev_line):
                if re.search(rf"\b{re.escape(var)}\s*=", prev_line):
                    return True
        return False

    # Deduplication: report only the first occurrence of the same variable within the same file
    reported_vars: set[str] = set()

    for idx, s in enumerate(lines, start=1):
        vars_hit: List[str] = []
        # '->' access is almost certainly a dereference
        for m in re_arrow.finditer(s):
            vars_hit.append(m.group(1))
        # '*p': exclude type declaration lines; and filter multiplication usage by context
        if "*" in s and not type_kw.search(s):
            for m in re_star.finditer(s):
                star_pos = m.start(0)
                if not _is_deref_context(s, star_pos):
                    continue
                # Exclude *p = value write operations (not a dereference read, it is a write)
                after_star = s[m.end(0) :].lstrip()
                if (
                    after_star
                    and after_star[0] == "="
                    and (len(after_star) < 2 or after_star[1] != "=")
                ):
                    continue
                vars_hit.append(m.group(1))
        # Array access arr[...]: exclude array declarations
        for m in re_array_access.finditer(s):
            var = m.group(1)
            var_pos = m.start(1)
            # Exclude array declarations
            if _is_array_declaration(s, var_pos):
                continue
            # Exclude array access in template parameters (such as make_unique<int[]>)
            before_var = s[:var_pos]
            if "<" in before_var and ">" not in before_var:
                # Inside template parameters, skip
                continue
            # Exclude obvious array initialization (such as int arr[] = {...})
            if type_kw.search(before_var) and "=" in s[var_pos:]:
                # Check whether it is initialization syntax
                after_var = s[var_pos + len(var) :]
                if re.match(r"\s*\[[^\]]*\]\s*=", after_var):
                    continue
            vars_hit.append(var)
        _stack_array_filtered = 0
        for v in set(vars_hit):
            if v == "this":  # In C++ member functions this-> should generally not be treated as a null pointer
                continue
            # Skip static/global variables (usually already ensured non-null at initialization)
            if v in safe_vars:
                continue
            # Skip stack arrays (stack arrays cannot be NULL)
            if v in stack_arrays:
                _stack_array_filtered += 1
                continue
            # Query global array variables via database (arrays declared across files)
            if database is not None and v not in stack_arrays:
                try:
                    global_sym = database.get_symbol(v)
                    if global_sym and global_sym.get("type_name", "").endswith("[]"):
                        stack_arrays.add(v)  # Cache to avoid repeated queries
                        continue
                except Exception:
                    pass
            # Skip smart pointer variables (cannot be NULL)
            if v in smart_ptr_vars:
                continue
            # Skip C++ container variables (value types, cannot be NULL)
            if v in container_vars:
                continue
            # Skip function parameters (NULL checks for parameters should be at the caller)
            if v in func_params:
                continue
            # Skip delete/delete[] statements (not dereferences)
            if re_delete_stmt.search(s):
                continue
            # Deduplication: report only the first occurrence of the same variable within the same file
            if v in reported_vars:
                continue
            # Skip immediate use right after successful allocation (successful allocation usually means non-null)
            if _is_just_allocated(v, lines, idx):
                continue
            # Prefer database null_checks, otherwise fall back to regex detection
            has_null_check = False
            if db_null_checks and v in db_null_checks:
                # Check whether there is a null check before the current line
                for check_line in db_null_checks[v]:
                    if check_line < idx:
                        has_null_check = True
                        break
            # No preceding check found in database or variable not in database, fall back to heuristic detection
            if not has_null_check:
                has_null_check = _has_null_check_around(v, lines, idx, radius=10)
            if not has_null_check:
                reported_vars.add(v)
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="possible_null_deref",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Pointer {v} may have been dereferenced without a nearby NULL check, posing a null pointer dereference risk.",
                        suggestion="Perform a NULL check before using the pointer; ensure all return/assignment paths have performed validity checks.",
                        confidence=0.6,
                        severity="high",
                        var_name=v,
                    )
                )
    return issues


def _rule_uninitialized_ptr_use(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect wild pointer (uninitialized pointer) usage:
    - Use database's data_flow table to query variable definition and usage
    - Detect pointers that are used directly after def without assignment
    """
    issues: List[Issue] = []

    if database is None:
        # Skip regex fallback when there is no database (to avoid false positives)
        return issues

    # Get data_flow of the current file from database
    try:
        flow_nodes = database.get_data_flow_by_file(relpath)
    except Exception:
        return issues

    if not flow_nodes:
        return issues

    # Group by variable name, check whether there is an assignment after def
    var_flows: Dict[str, List[Dict[str, Any]]] = {}
    for node in flow_nodes:
        var_name = node.get("var_name", "")
        if var_name:
            if var_name not in var_flows:
                var_flows[var_name] = []
            var_flows[var_name].append(node)

    # Check the data flow of each variable
    for var_name, nodes in var_flows.items():
        # Sort by line number
        nodes.sort(key=lambda n: n.get("line", 0))

        # Find the def node
        def_line = None
        for node in nodes:
            if node.get("node_type") == "def":
                def_line = node.get("line", 0)
                break

        if not def_line:
            continue

        # Check whether there is an assignment after def (value_source is not empty) or param_in
        has_init = False
        first_use_line = None
        for node in nodes:
            line = node.get("line", 0)
            if line <= def_line:
                continue
            node_type = node.get("node_type", "")
            value_source = node.get("value_source", "")

            # Assignment or initialization
            if node_type == "def" and value_source:
                has_init = True
                break
            # Parameter input also counts as initialization
            if node_type == "param_in":
                has_init = True
                break
            # Use (dereference)
            if node_type == "use" and not value_source:
                first_use_line = line
                break

        if first_use_line and not has_init:
            # Get evidence line
            evidence = ""
            if 0 < first_use_line <= len(lines):
                evidence = _strip_line(lines[first_use_line - 1])

            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="wild_pointer_deref",
                    file=relpath,
                    line=first_use_line,
                    evidence=evidence,
                    description=f"Pointer {var_name} was dereferenced without initialization after declaration, possibly a wild pointer use.",
                    suggestion="Initialize the pointer to NULL immediately after declaration, and perform explicit assignment and validity verification before use.",
                    confidence=0.8,
                    severity="high",
                    var_name=var_name,
                )
            )

    return issues


def _rule_deadlock_patterns_from_calls(
    lines: Sequence[str], relpath: str, lock_calls: List[Dict[str, Any]]
) -> List[Issue]:
    """
    Deadlock detection Helper functions based on call_graph data.
    Detects double locking, missing unlock, lock order inversion.
    """
    issues: List[Issue] = []

    # Sort calls by line number
    lock_calls.sort(key=lambda c: c.get("caller_line", 0))

    # Helper functions to extract mutex names
    def extract_mutex_name(line_content: str) -> str:
        """Extract mutex name from a code line"""
        m = RE_PTHREAD_LOCK.search(line_content)
        if m:
            return m.group(1)
        m = RE_PTHREAD_UNLOCK.search(line_content)
        if m:
            return m.group(1)
        return ""

    lock_stack: list[str] = []
    order_pairs: dict[tuple[str, str], int] = {}
    last_func_boundary = 0  # Previous function boundary line number

    # Deduplication: call_graph may have duplicate entries, deduplicate by (callee_name, caller_line)
    seen_calls = set()
    unique_lock_calls = []
    for call in lock_calls:
        key = (call.get("callee_name", ""), call.get("caller_line", 0))
        if key not in seen_calls:
            seen_calls.add(key)
            unique_lock_calls.append(call)
    lock_calls = unique_lock_calls

    # Pre-scan all lines to find function boundary line numbers
    func_boundary_lines = []
    func_pattern = re.compile(
        r"^\s*(static\s+)?(void|int|char|unsigned|signed)\s*(\*\s*)?\w+\s*\([^)]*(\*\s*\w+)?[^)]*\)\s*{"
    )
    for line_idx, line_content in enumerate(lines, start=1):
        if func_pattern.search(line_content):
            func_boundary_lines.append(line_idx)

    # First scan: ordering and double locking
    for call in lock_calls:
        idx = call.get("caller_line", 0)
        callee_name = call.get("callee_name", "")
        if 0 < idx <= len(lines):
            s = lines[idx - 1]
        else:
            continue

        mtx = extract_mutex_name(s)
        if not mtx:
            continue

        # Check whether a function boundary was crossed
        for boundary in func_boundary_lines:
            if boundary > last_func_boundary and boundary < idx:
                lock_stack = []  # Reset lock stack for new function
                last_func_boundary = boundary
                break

        if callee_name == "pthread_mutex_lock":
            # Double locking detection
            if mtx in lock_stack:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="error_handling",
                        pattern="double_lock",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Mutex {mtx} was locked again without being unlocked, posing a deadlock risk.",
                        suggestion="Avoid locking the same mutex repeatedly; check code paths to ensure locking/unlocking match strictly.",
                        confidence=0.8,
                        severity="high",
                    )
                )
            # Lock order recording (only recorded within the same function)
            if lock_stack and lock_stack[-1] != mtx:
                pair = (lock_stack[-1], mtx)
                order_pairs.setdefault(pair, idx)
            lock_stack.append(mtx)
        elif callee_name == "pthread_mutex_unlock":
            # Remove the most recent identical lock from the stack
            if mtx in lock_stack:
                for k in range(len(lock_stack) - 1, -1, -1):
                    if lock_stack[k] == mtx:
                        del lock_stack[k]
                        break

    # Lock order inversion detection (cross-function detection)
    # Detect global lock order inversion: if both (A, B) and (B, A) orders exist, there is a deadlock risk
    for (a, b), line1 in list(order_pairs.items()):
        reverse_pair = (b, a)
        if reverse_pair in order_pairs:
            line2 = order_pairs[reverse_pair]
            issues.append(
                Issue(
                    language="c/cpp",
                    category="error_handling",
                    pattern="lock_order_inversion",
                    file=relpath,
                    line=min(line1, line2),
                    evidence=f"Lock order inversion: {a}→{b} (line {line1}) vs {b}→{a} (line {line2})",
                    description=f"Lock order inversion detected: both {a}→{b} and {b}→{a} locking orders exist, which may cause a deadlock.",
                    suggestion="Unify the locking order across all threads to avoid lock order inversion.",
                    confidence=0.7,
                    severity="high",
                )
            )
            # Avoid duplicate reporting
            del order_pairs[(a, b)]
            if reverse_pair in order_pairs:
                del order_pairs[reverse_pair]

    # Possible missing unlock: no corresponding unlock seen within the 50-line window after locking
    for call in lock_calls:
        if call.get("callee_name") != "pthread_mutex_lock":
            continue
        idx = call.get("caller_line", 0)
        if 0 < idx <= len(lines):
            s = lines[idx - 1]
        else:
            continue
        mtx = extract_mutex_name(s)
        if not mtx:
            continue

        end = min(len(lines), idx + 50)
        unlocked = False
        for j in range(idx + 1, end + 1):
            sj = _safe_line(lines, j)
            m_un = RE_PTHREAD_UNLOCK.search(sj)
            if m_un and m_un.group(1) == mtx:
                unlocked = True
                break
        if not unlocked:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="error_handling",
                    pattern="missing_unlock_suspect",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"No matching unlock detected within the adjacent window after locking {mtx}; there may be a risk of a missing unlock.",
                    suggestion="Ensure all locking paths have a paired unlock; consider using an RAII/DEFER style to avoid omissions.",
                    confidence=0.55,
                    severity="medium",
                )
            )

    return issues


def _rule_deadlock_patterns(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect common deadlock risks:
    - Double lock: the same mutex is locked again without being unlocked
    - Possible missing unlock: no corresponding unlock seen within the subsequent window after locking
    - Lock order inversion: both (A->B) and (B->A) locking orders exist
    The implementation is heuristic-based and may produce false positives.
    - Prefer database query for call_graph table; fall back to regex detection when there is no data
    """
    issues: List[Issue] = []
    import os

    # Set of mutex lock functions
    LOCK_FUNCS = {"pthread_mutex_lock", "pthread_mutex_unlock"}

    # Prefer using database query
    if database:
        try:
            call_graph = database.get_call_graph()
            lock_calls = []
            for call in call_graph:
                callee_name = call.get("callee_name", "")
                if callee_name in LOCK_FUNCS:
                    caller_file = call.get("caller_file", "")
                    if os.path.basename(caller_file) == os.path.basename(relpath):
                        lock_calls.append(call)

            # If there is data in the database, use the database results
            if lock_calls:
                return _rule_deadlock_patterns_from_calls(lines, relpath, lock_calls)
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_deadlock_patterns",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


# ---------------------------
# Other dangerous usage rules (new batch with low false positives)
# ---------------------------


def _rule_double_free_and_free_non_heap(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect:
    - double_free: the same pointer is freed repeatedly without being reassigned/nulled
    - free_non_heap: obviously non-heap memory releases such as free(&x) or free("literal")
    Note: prefer taint analysis, falling back to a heuristic implementation on failure.
    Cross-file analysis: use the database to track pointer state and detect cross-file Double Free risks.
    """
    issues: List[Issue] = []

    # Try taint analysis first
    try:
        import haijunbot.haijunbot_sec.taint_analyzer as taint_analyzer

        analyzer = taint_analyzer.TaintAnalyzerFactory.create("joern")
        if analyzer and analyzer.is_available():
            code = "\n".join(lines)
            rule = taint_analyzer.get_rule("double_free")
            if rule:
                taint_paths = rule.check(analyzer, code, relpath)
                for path in taint_paths:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="double_free",
                            file=relpath,
                            line=path.line_number,
                            evidence=path.code_snippet,
                            description=path.description,
                            suggestion="Set the pointer to NULL after free; ensure each block of memory is freed only once; clarify ownership and free paths.",
                            confidence=0.9,
                            severity="high",
                        )
                    )
            # Taint analysis succeeded; continue checking free_non_heap
        # Taint analysis unavailable; fall back to heuristic detection
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_sec.checkers.c_checker",
            function="_rule_double_free_and_free_non_heap",
        )
        pass
    last_free_line: dict[str, int] = {}
    last_assign_line: dict[str, int] = {}

    for idx, s in enumerate(lines, start=1):
        # Record simple assignments (used to determine whether there is a reassignment between frees)
        for m in RE_GENERIC_ASSIGN.finditer(s):
            var = m.group(1)
            last_assign_line[var] = idx

        # Handle free(...) calls
        for m in RE_FREE_CALL_ANY.finditer(s):
            arg = m.group(1).strip()

            # Ignore free(NULL)/free(0)
            if re.fullmatch(
                r"\(?\s*(NULL|0|\(void\s*\*\)\s*0)\s*\)?", arg, re.IGNORECASE
            ):
                continue

            # Obviously non-heap: &... or string literals
            if re.match(r"^\(?\s*&", arg) or arg.lstrip().startswith('"'):
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="free_non_heap",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="Detected a release of non-heap memory (such as &var or a string literal), which is undefined behavior.",
                        suggestion="Only free heap memory obtained from malloc/calloc/realloc/new/new[]; avoid calling free on stack addresses/literals.",
                        confidence=0.85,
                        severity="high",
                    )
                )
                continue

            # double_free: only detect when the argument is a single identifier
            if re.fullmatch(r"[A-Za-z_]\w*", arg):
                var = arg
                prev = last_free_line.get(var)
                if prev is not None:
                    assign_after_prev = last_assign_line.get(var, -1)
                    if assign_after_prev < prev:
                        # If it is freed again without reassignment/nulling after the previous free, double_free risk is considered high
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="memory_mgmt",
                                pattern="double_free",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description=f"Pointer {var} may be freed repeatedly without being reassigned/nulled (double free).",
                                suggestion="Set the pointer to NULL after free; ensure each block of memory is freed only once; clarify ownership and free paths.",
                                confidence=0.8,
                                severity="high",
                            )
                        )
                last_free_line[var] = idx

    # Cross-file Double Free detection: use the database to track pointer state
    if database is not None:
        cross_file_issues = _detect_cross_file_double_free(database, relpath, lines)
        issues.extend(cross_file_issues)

    return issues


def _rule_atoi_family(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect usage of atoi/atol/atoll/atof (lacking error and range checks, prone to parsing ambiguity).
    Recommend switching to strtol/strtoul/strtod and checking errno/the end pointer.
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    atoi_apis = ["atoi", "atol", "atoll", "atof"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in atoi_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    if 0 < line_num <= len(lines):
                        s = lines[line_num - 1]
                        if s.lstrip().startswith("#"):
                            continue
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="input_validation",
                            pattern="atoi_family",
                            file=relpath,
                            line=line_num,
                            evidence=f"{callee}() call",
                            description=f"Using {callee} lacks error and range checks, easily producing parsing errors or undefined behavior.",
                            suggestion="Use strtol/strtoul/strtod etc. and check errno and endptr; perform range and format validation.",
                            confidence=0.9,
                            severity="medium",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.checkers.c_checker", function="_rule_atoi_family"
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_rand_insecure(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect usage of rand/srand. If the context contains security-sensitive keywords, raise the risk.
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    rand_apis = ["rand", "srand", "random"]
    keywords = (
        "token",
        "nonce",
        "secret",
        "password",
        "passwd",
        "key",
        "auth",
        "salt",
        "session",
        "otp",
    )

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in rand_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    # Check whether the context contains security-sensitive keywords
                    conf = 0.7
                    if line_num > 0 and line_num <= len(lines):
                        start = max(0, line_num - 2)
                        end = min(len(lines), line_num + 2)
                        window_text = " ".join(lines[start:end]).lower()
                        if any(k in window_text for k in keywords):
                            conf = 0.85
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="crypto",
                            pattern="rand_insecure",
                            file=relpath,
                            line=line_num,
                            evidence=f"{callee}() call",
                            description=f"Detected {callee}; may be unsafe for security-sensitive scenarios and is easily predictable.",
                            suggestion="Use a system-level CSPRNG (such as getrandom/arc4random/openssl RAND_bytes); avoid using it for key/token generation.",
                            confidence=conf,
                            severity="high" if conf >= 0.8 else "medium",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_rand_insecure",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_strtok_nonreentrant(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect non-reentrant/thread-unsafe usage of strtok.
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    strtok_apis = ["strtok"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in strtok_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="thread_safety",
                            pattern="strtok_nonreentrant",
                            file=relpath,
                            line=call.get("caller_line", 0),
                            evidence=f"{callee}() call",
                            description="Using strtok is non-reentrant and thread-unsafe, which may cause races or data overwriting.",
                            suggestion="Use strtok_r (POSIX) or a reentrant/thread-safe splitting approach.",
                            confidence=0.85,
                            severity="medium",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_strtok_nonreentrant",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_open_permissive_perms(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect overly permissive file permissions:
    - open(..., O_CREAT, 0666/0777/...) directly grants overly permissive permissions
    - fopen(..., "w"/"w+") in security-sensitive contexts may prompt tightening permissions (keyword-based heuristic)
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    open_apis = ["open", "fopen"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in open_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    if line_num > 0 and line_num <= len(lines):
                        s = lines[line_num - 1]
                        # Check open permissions
                        m = RE_OPEN_PERMISSIVE.search(s)
                        if m:
                            mode = m.group(1)
                            try:
                                mode_val = int(mode, 8)
                                has_group_write = (mode_val & 0o020) != 0
                                has_other_write = (mode_val & 0o002) != 0
                                has_other_read = (mode_val & 0o004) != 0
                                is_permissive = (
                                    has_group_write or has_other_write or has_other_read
                                )
                                if not is_permissive:
                                    continue
                            except ValueError:
                                pass
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="insecure_permissions",
                                    pattern="open_permissive_perms",
                                    file=relpath,
                                    line=line_num,
                                    evidence=f"{callee}() permission {mode}",
                                    description=f"open uses O_CREAT with overly permissive mode {mode}, posing a risk of sensitive information disclosure.",
                                    suggestion="Explicitly use stricter permissions (such as 0600/0640), or set an appropriate umask before creating files.",
                                    confidence=0.85,
                                    severity="high",
                                )
                            )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_open_permissive_perms",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


# ---------------------------
# More dangerous usage rules (second batch)
# ---------------------------


def _rule_alloca_unbounded(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect alloca usage with non-constant/uncontrolled sizes, which may cause stack exhaustion or crashes.
    Warn only when the argument is not a pure numeric constant and does not contain sizeof.
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    alloca_apis = ["alloca", "__builtin_alloca"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in alloca_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    # Get call arguments for heuristic analysis
                    if line_num > 0 and line_num <= len(lines):
                        s = lines[line_num - 1]
                        m = RE_ALLOCA.search(s)
                        if m:
                            arg = m.group(1).strip()
                            # Pure numeric constants or containing sizeof are considered safer
                            if re.fullmatch(r"\d+\s*", arg) or "sizeof" in arg:
                                continue
                            if re.fullmatch(r"[A-Z_][A-Z0-9_]*", arg):
                                continue
                            # Constant propagation check: if arg is a variable name, search backward for whether it was assigned a constant expression
                            if re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", arg):
                                const_assigned = False
                                for prev_line_no in range(line_num - 2, -1, -1):
                                    prev_s = lines[prev_line_no]
                                    if prev_s.lstrip().startswith(
                                        ("//", "/*", "*", "#")
                                    ):
                                        continue
                                    m_assign = re.search(
                                        rf"\b{re.escape(arg)}\s*=\s*(.+?)\s*;", prev_s
                                    )
                                    if m_assign:
                                        rhs = m_assign.group(1).strip()
                                        # Recursively check whether variables in rhs originate from bounded functions
                                        _rhs_bounded = False
                                        _rhs_vars = set(
                                            re.findall(
                                                r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", rhs
                                            )
                                        )
                                        _rhs_vars.discard(arg)
                                        if _rhs_vars and not _rhs_bounded:
                                            for _rv in _rhs_vars:
                                                for _pl2 in range(
                                                    prev_line_no - 1, -1, -1
                                                ):
                                                    _ps2 = lines[_pl2]
                                                    if _ps2.lstrip().startswith(
                                                        ("//", "/*", "*", "#")
                                                    ):
                                                        continue
                                                    _m2 = re.search(
                                                        rf"\b{re.escape(_rv)}\s*=\s*(.+?)\s*;",
                                                        _ps2,
                                                    )
                                                    if _m2:
                                                        _rrhs = _m2.group(1).strip()
                                                        if re.search(
                                                            r"\w*(len|size|count|n|min|max|bound)\w*\s*\(",
                                                            _rrhs,
                                                            re.IGNORECASE,
                                                        ):
                                                            _rhs_bounded = True
                                                        break
                                                if _rhs_bounded:
                                                    break
                                        if _rhs_bounded:
                                            const_assigned = True
                                        elif (
                                            re.fullmatch(
                                                r"[\d\s\+\-\*\/\%\(\)\[\]\&\|\.\^\~\<\>\!\?\:\,]+",
                                                rhs,
                                            )
                                            or "sizeof" in rhs
                                        ):
                                            const_assigned = True
                                        # Function call return value recognition: return values of functions like len/size/count imply bounded
                                        if re.search(
                                            r"\w*(len|size|count|n|min|max|bound)\w*\s*\(",
                                            rhs,
                                            re.IGNORECASE,
                                        ):
                                            const_assigned = True
                                        break
                                if const_assigned:
                                    continue
                            conf = 0.75
                            if re.search(r"(len|size|count|n)\b", arg, re.IGNORECASE):
                                conf = 0.85
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="memory_mgmt",
                                    pattern="alloca_unbounded",
                                    file=relpath,
                                    line=line_num,
                                    evidence=f"{callee}({arg})",
                                    description="The size used by alloca is not a compile-time constant, which may lead to uncontrolled stack allocation and crash risks.",
                                    suggestion="Avoid using alloca; switch to heap allocation and perform upper-bound checks and error handling on the size.",
                                    confidence=conf,
                                    severity="high" if conf >= 0.8 else "medium",
                                )
                            )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_alloca_unbounded",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_vla_usage(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect variable-length array (VLA) usage: using a variable/expression as the array length in a declaration.
    Warn only when the length is not a pure numeric constant.
    """
    issues: List[Issue] = []
    type_prefix = re.compile(
        r"\b(typedef|struct|union|enum|class|const|volatile|static|register|signed|unsigned|char|int|long|short|void|float|double|size_t|ssize_t)\b"
    )
    for idx, s in enumerate(lines, start=1):
        if ";" not in s or "=" in s:
            continue
        if not type_prefix.search(s):
            continue
        m = RE_VLA_DECL.search(s)
        if not m:
            continue
        length_expr = m.group(1).strip()
        if re.fullmatch(r"\d+\s*", length_expr):
            continue
        # Macro constants (all uppercase + underscores/digits) are usually compile-time constants (not VLA), reducing false positives
        if re.fullmatch(r"[A-Z_][A-Z0-9_]*", length_expr):
            continue
        issues.append(
            Issue(
                language="c/cpp",
                category="memory_mgmt",
                pattern="vla_usage",
                file=relpath,
                line=idx,
                evidence=_strip_line(s),
                description="Detected a variable-length array (VLA) performing variable-size allocation on the stack, which may cause stack overflow/uncontrolled memory usage.",
                suggestion="Avoid VLAs; switch to heap allocation with upper-bound validation, or use static allocation with a fixed upper bound.",
                confidence=0.6,
                severity="medium",
            )
        )
    return issues


def _rule_pthread_returns_unchecked(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where the return values of common pthread interfaces are not checked (missing if/comparison judgment on the same/next line or two).
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    pthread_apis = [
        "pthread_create",
        "pthread_join",
        "pthread_mutex_lock",
        "pthread_mutex_unlock",
        "pthread_cond_wait",
        "pthread_cond_signal",
    ]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in pthread_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    # Check whether the return value is checked
                    if line_num > 0 and line_num <= len(lines):
                        nearby = " ".join(
                            _safe_line(lines, i)
                            for i in range(line_num, min(line_num + 2, len(lines)) + 1)
                        )
                        if not re.search(r"\bif\s*\(|>=|<=|==|!=|<|>", nearby):
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="error_handling",
                                    pattern="pthread_ret_unchecked",
                                    file=relpath,
                                    line=line_num,
                                    evidence=f"{callee}() call",
                                    description=f"The return value of pthread interface {callee} may be unchecked; missing error handling may cause deadlocks/resource leaks.",
                                    suggestion="Check the pthread interface return code and handle error paths; log and clean up resources when necessary.",
                                    confidence=0.75,
                                    severity="medium",
                                )
                            )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_pthread_returns_unchecked",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_cond_wait_no_loop(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect pthread_cond_wait used outside a while loop (to prevent spurious wakeups).
    Accuracy optimizations:
    - Support detecting the "while(predicate) pthread_cond_wait(...) on the same line as the call" pattern to avoid false positives
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    cond_wait_apis = ["pthread_cond_wait"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in cond_wait_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    line_num = call.get("caller_line", 0)
                    # Check whether the context has a while loop
                    if line_num > 0 and line_num <= len(lines):
                        s = lines[line_num - 1]
                        m = RE_PTHREAD_COND_WAIT.search(s)
                        if m:
                            # Look back within 2 lines for while( ... )
                            prev_text = " ".join(
                                _safe_line(lines, j)
                                for j in range(max(1, line_num - 2), line_num)
                            )
                            has_prev_while = (
                                re.search(r"\bwhile\s*\(", prev_text) is not None
                            )
                            # If the same line (the part before the call) contains while(...), it is also considered correct usage
                            same_line_before = s[: m.start()]
                            has_same_line_while = (
                                re.search(r"\bwhile\s*\(", same_line_before) is not None
                            )

                            if has_prev_while or has_same_line_while:
                                continue

                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="thread_safety",
                                    pattern="cond_wait_no_loop",
                                    file=relpath,
                                    line=line_num,
                                    evidence=f"{callee}() call",
                                    description="pthread_cond_wait should be placed in a while loop with a condition predicate to prevent spurious wakeups.",
                                    suggestion="Wrap the pthread_cond_wait call with while(predicate_not_satisfied) and recheck the condition after waking up.",
                                    confidence=0.75,
                                    severity="medium",
                                )
                            )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_cond_wait_no_loop",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_thread_leak_no_join_from_calls(
    lines: Sequence[str], relpath: str, thread_calls: List[Dict[str, Any]]
) -> List[Issue]:
    """
    Thread leak detection helper functions based on call_graph data.
    Detect whether there is a pthread_join/pthread_detach after pthread_create.
    """
    issues: List[Issue] = []

    # Sort calls by line number
    thread_calls.sort(key=lambda c: c.get("caller_line", 0))

    # Helper functions to extract thread IDs
    def extract_thread_id(line_content: str) -> str:
        """Extract the thread ID variable name from a code line"""
        m = RE_PTHREAD_CREATE.search(line_content)
        if m:
            return m.group(1)
        m = RE_PTHREAD_JOIN.search(line_content)
        if m:
            return m.group(1)
        m = RE_PTHREAD_DETACH.search(line_content)
        if m:
            return m.group(1)
        return ""

    # Detect whether there is a join/detach after pthread_create
    for call in thread_calls:
        if call.get("callee_name") != "pthread_create":
            continue

        idx = call.get("caller_line", 0)
        if 0 < idx <= len(lines):
            s = lines[idx - 1]
        else:
            continue

        tid = extract_thread_id(s)
        if not tid:
            continue

        # Detect join/detach within the subsequent 80-line window
        end = min(len(lines), idx + 80)
        joined_or_detached = False
        for j in range(idx + 1, end + 1):
            sj = _safe_line(lines, j)
            m_join = RE_PTHREAD_JOIN.search(sj)
            if m_join and m_join.group(1) == tid:
                joined_or_detached = True
                break
            m_detach = RE_PTHREAD_DETACH.search(sj)
            if m_detach and m_detach.group(1) == tid:
                joined_or_detached = True
                break

        if not joined_or_detached:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="resource_leak",
                    pattern="thread_leak_no_join",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"No join/detach detected within the adjacent window after pthread_create creates thread {tid}, which may cause thread leaks or resource occupation.",
                    suggestion="Ensure created threads are explicitly joined or detached; follow a unified thread lifecycle management strategy.",
                    confidence=0.6,
                    severity="medium",
                )
            )

    return issues


def _rule_thread_leak_no_join(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect possible thread leaks where a created thread is not joined/detached.
    Prefer database query for call_graph table; fall back to regex detection when there is no data.
    """
    issues: List[Issue] = []
    import os

    # Set of thread functions
    THREAD_FUNCS = {"pthread_create", "pthread_join", "pthread_detach"}

    # Prefer using database query
    if database:
        try:
            call_graph = database.get_call_graph()
            thread_calls = []
            for call in call_graph:
                callee_name = call.get("callee_name", "")
                if callee_name in THREAD_FUNCS:
                    caller_file = call.get("caller_file", "")
                    if os.path.basename(caller_file) == os.path.basename(relpath):
                        thread_calls.append(call)

            # If there is data in the database, use the database results
            if thread_calls:
                return _rule_thread_leak_no_join_from_calls(
                    lines, relpath, thread_calls
                )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_thread_leak_no_join",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_inet_legacy(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect usage of legacy interfaces such as inet_addr/inet_aton.
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    inet_apis = ["inet_addr", "inet_aton", "inet_ntoa"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in inet_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="network_api",
                            pattern="inet_legacy",
                            file=relpath,
                            line=call.get("caller_line", 0),
                            evidence=f"{callee}() call",
                            description=f"Using legacy interface {callee}; error semantics are ambiguous/inconsistent.",
                            suggestion="Use inet_pton/inet_ntop for address conversion; error handling is more reliable and IPv6 is supported.",
                            confidence=0.85,
                            severity="low",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.checkers.c_checker", function="_rule_inet_legacy"
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_time_apis_not_threadsafe(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect the non-thread-safe interfaces asctime/ctime/localtime/gmtime (not *_r).
    Note: Prefer database query for call_graph table; fall back to regex detection on failure.
    """
    issues: List[Issue] = []
    time_apis = ["asctime", "ctime", "localtime", "gmtime"]

    # Try database-driven detection first
    if database:
        try:
            import os

            basename = os.path.basename(relpath)
            calls = database.get_call_graph()
            for call in calls:
                callee = call.get("callee_name", "")
                if callee not in time_apis:
                    continue
                caller_file = call.get("caller_file", "")
                if basename == os.path.basename(caller_file):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="thread_safety",
                            pattern="time_api_not_threadsafe",
                            file=relpath,
                            line=call.get("caller_line", 0),
                            evidence=f"{callee}() call",
                            description=f"Using non-reentrant interface {callee}; thread safety is insufficient.",
                            suggestion="Switch to the *_r thread-safe versions (such as localtime_r/gmtime_r/ctime_r).",
                            confidence=0.85,
                            severity="medium",
                        )
                    )
            if issues:
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_time_apis_not_threadsafe",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


def _rule_getenv_unchecked(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect cases where the getenv return value is not checked.
    Note: prefer using the database to query null_checks, falling back to a heuristic implementation on failure.
    """
    issues: List[Issue] = []

    # Try database-driven detection first
    if database:
        try:
            from haijunbot.haijunbot_sec.data_flow_analyzer import DataFlowAnalyzer

            analyzer = DataFlowAnalyzer(database)
            code = "\n".join(lines)
            result = analyzer.analyze_code(
                code, is_cpp=False, database=database, file_path=relpath
            )

            if result:
                # Find getenv call sites
                for idx, s in enumerate(lines, start=1):
                    m = RE_GETENV.search(s)
                    if not m:
                        continue

                    # Get variable name (assignment pattern)
                    var_name = None
                    assign_match = re.search(r"\b([A-Za-z_]\w*)\s*=\s*getenv\s*\(", s)
                    if assign_match:
                        var_name = assign_match.group(1)

                    if var_name:
                        # Skip getenv in return statements (caller is responsible for checking)
                        if re.search(r"\breturn\s+", s):
                            continue
                        # Check whether there is a null_check
                        has_check = (
                            result.null_checks is not None
                            and var_name in result.null_checks
                        )
                        if not has_check:
                            # Use _has_null_check_around for a second confirmation
                            has_check = _has_null_check_around(
                                var_name, lines, idx, radius=5
                            )
                        if not has_check:
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="input_validation",
                                    pattern="getenv_unchecked",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(s),
                                    description=f"Environment variable {var_name} = getenv() return value is not checked for NULL.",
                                    suggestion="Read only whitelisted keys; validate the value's format/length/charset; avoid directly concatenating into commands/paths.",
                                    confidence=0.75,
                                    severity="medium",
                                )
                            )
                    else:
                        # False-negative fix: detect getenv passed directly as a function argument (not assigned to a variable)
                        # Pattern: func(getenv("KEY")) or func(..., getenv("KEY"), ...)
                        # But skip return statements (caller is responsible for checking)
                        if re.search(r"\breturn\s+", s):
                            continue
                        direct_call_match = re.search(
                            r"getenv\s*\(\s*\"[^\"]+\"\s*\)", s
                        )
                        if direct_call_match:
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="input_validation",
                                    pattern="getenv_unchecked",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(s),
                                    description="getenv() return value passed directly to a function without checking for NULL.",
                                    suggestion="First check whether the getenv return value is NULL, then use the environment variable value.",
                                    confidence=0.7,
                                    severity="medium",
                                )
                            )
                if issues:
                    return issues
                # No issues detected for database, return empty directly
                return issues
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_sec.checkers.c_checker",
                function="_rule_getenv_unchecked",
            )
            pass

    # Skip regex fallback when there is no database (to avoid false positives)
    return issues


# ---------------------------
# C++-specific check rules
# ---------------------------


def _rule_new_delete_mismatch(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect cross-API mismatches between new/delete and malloc/free:
    - new[] must be freed with delete[]
    - new must be freed with delete (cannot use delete[] or free)
    - malloc must be freed with free (cannot use delete)
    """
    issues: List[Issue] = []
    new_array_vars: dict[str, int] = {}  # var -> line_no
    new_vars: dict[str, int] = {}  # var -> line_no
    malloc_vars: dict[str, int] = {}  # var -> line_no

    # Collect new[] and new allocations
    for idx, s in enumerate(lines, start=1):
        # new[] allocation
        m = RE_NEW_ARRAY.search(s)
        if m:
            # Try to extract variable name (simple heuristic)
            assign_match = re.search(r"\b([A-Za-z_]\w*)\s*=\s*new\s+", s, re.IGNORECASE)
            if assign_match:
                var = assign_match.group(1)
                new_array_vars[var] = idx

        # new allocation (non-array)
        m_new = re.search(r"\b([A-Za-z_]\w*)\s*=\s*new\s+(?!.*\[)", s, re.IGNORECASE)
        if m_new:
            var = m_new.group(1)
            new_vars[var] = idx

        # malloc allocation
        m_malloc = RE_MALLOC_ASSIGN.search(s)
        if m_malloc:
            var = m_malloc.group(1)
            malloc_vars[var] = idx

    # Check usage of delete[], delete, free
    for idx, s in enumerate(lines, start=1):
        # delete[] usage
        if RE_DELETE_ARRAY.search(s):
            # Extract variable name
            m = re.search(r"delete\s*\[\s*\]\s*([A-Za-z_]\w*)", s, re.IGNORECASE)
            if m:
                var = m.group(1)
                if var in new_vars:
                    # Freed memory allocated by new using delete[]
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="new_delete_mismatch",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Using delete[] to free memory allocated by new (non-array), risking undefined behavior.",
                            suggestion="Memory allocated by new should be freed with delete; memory allocated by new[] should be freed with delete[].",
                            confidence=0.85,
                            severity="high",
                        )
                    )
                if var in malloc_vars:
                    # Freed memory allocated by malloc using delete[]
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="new_delete_mismatch",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Using delete[] to free memory allocated by malloc, risking undefined behavior.",
                            suggestion="Memory allocated by malloc should be freed with free; memory allocated by new should be freed with delete.",
                            confidence=0.85,
                            severity="high",
                        )
                    )

        # delete usage (non-array)
        if RE_DELETE.search(s):
            m = re.search(r"delete\s+([A-Za-z_]\w*)", s, re.IGNORECASE)
            if m:
                var = m.group(1)
                if var in new_array_vars:
                    # Freed memory allocated by new[] using delete
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="new_delete_mismatch",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Using delete to free array memory allocated by new[], risking undefined behavior.",
                            suggestion="Memory allocated by new[] should be freed with delete[]; memory allocated by new should be freed with delete.",
                            confidence=0.85,
                            severity="high",
                        )
                    )
                if var in malloc_vars:
                    # Freed memory allocated by malloc using delete
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="memory_mgmt",
                            pattern="new_delete_mismatch",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Using delete to free memory allocated by malloc, risking undefined behavior.",
                            suggestion="Memory allocated by malloc should be freed with free; memory allocated by new should be freed with delete.",
                            confidence=0.85,
                            severity="high",
                        )
                    )

        # free usage
        m_free = RE_FREE_VAR.search(s)
        if m_free:
            var = m_free.group(1)
            if var in new_vars:
                # Freed memory allocated by new using free
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="new_delete_mismatch",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="Using free to free memory allocated by new, risking undefined behavior.",
                        suggestion="Memory allocated by new should be freed with delete; memory allocated by malloc should be freed with free.",
                        confidence=0.85,
                        severity="high",
                    )
                )
            if var in new_array_vars:
                # Freed memory allocated by new[] using free
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="new_delete_mismatch",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="Using free to free array memory allocated by new[], risking undefined behavior.",
                        suggestion="Memory allocated by new[] should be freed with delete[]; memory allocated by malloc should be freed with free.",
                        confidence=0.85,
                        severity="high",
                    )
                )

    return issues


def _rule_reinterpret_cast_unsafe(lines: Sequence[str], relpath: str) -> List[Issue]:
    """
    Detect unsafe usage of reinterpret_cast (high-risk type conversion).
    """
    issues: List[Issue] = []
    for idx, s in enumerate(lines, start=1):
        if RE_REINTERPRET_CAST.search(s):
            conf = 0.7
            # Risk is higher if converting to a pointer type
            if "->" in s or "*" in s:
                conf += 0.1
            issues.append(
                Issue(
                    language="c/cpp",
                    category="type_safety",
                    pattern="reinterpret_cast_unsafe",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using reinterpret_cast for type conversion may cause undefined behavior or type safety issues.",
                    suggestion="Prefer static_cast or dynamic_cast; if reinterpret_cast must be used, ensure type layouts are compatible and add detailed comments explaining it.",
                    confidence=min(conf, 0.9),
                    severity="high",
                )
            )
    return issues


def _rule_const_cast_unsafe(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect unsafe usage of const_cast (removing the const qualifier may cause undefined behavior).
    """
    issues: List[Issue] = []
    for idx, s in enumerate(lines, start=1):
        if RE_CONST_CAST.search(s):
            conf = 0.65
            # Risk is higher if a const_cast modifies an object that was originally const
            if "=" in s and not re.search(r"const\s+[A-Za-z_]\w*\s*\*", s):
                conf += 0.1
            issues.append(
                Issue(
                    language="c/cpp",
                    category="type_safety",
                    pattern="const_cast_unsafe",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description="Using const_cast to remove the const qualifier may cause undefined behavior (e.g. modifying a constant object).",
                    suggestion="Avoid using const_cast; if it must be used, ensure it is only used to remove non-top-level const and the object itself is mutable.",
                    confidence=min(conf, 0.8),
                    severity="high",
                )
            )
    return issues


def _rule_vector_string_bounds_check(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect out-of-bounds access for vector and string (using [] instead of .at()).
    Heuristic: detect [] access; if no bounds check is seen nearby, flag the risk.
    """
    issues: List[Issue] = []
    vector_vars: set[str] = set()
    string_vars: set[str] = set()

    # First collect vector and string variables
    for idx, s in enumerate(lines, start=1):
        m = RE_VECTOR_VAR.search(s)
        if m:
            vector_vars.add(m.group(1))
        m = RE_STRING_VAR.search(s)
        if m:
            string_vars.add(m.group(1))

    for idx, s in enumerate(lines, start=1):
        # vector access: detect var[...] pattern
        for var in vector_vars:
            if re.search(rf"\b{re.escape(var)}\s*\[", s):
                # Check whether .at() (safe access) is used
                if not RE_AT_METHOD.search(s):
                    # Check whether there is a bounds check nearby
                    window_text = " ".join(
                        t for _, t in _window(lines, idx, before=2, after=2)
                    )
                    if not re.search(
                        rf"\b{re.escape(var)}\s*\.(size|length|empty|at)\s*\(",
                        window_text,
                        re.IGNORECASE,
                    ):
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="buffer_overflow",
                                pattern="vector_bounds_check",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description=f"vector {var} accessed with [] may go out of bounds; using .at() for bounds checking is recommended.",
                                suggestion="Use the .at() method for safe access, or explicitly check the index range before using [].",
                                confidence=0.6,
                                severity="medium",
                            )
                        )
                        break  # report only once per line

        # string access: detect var[...] pattern
        for var in string_vars:
            if re.search(rf"\b{re.escape(var)}\s*\[", s):
                if not RE_AT_METHOD.search(s):
                    window_text = " ".join(
                        t for _, t in _window(lines, idx, before=2, after=2)
                    )
                    if not re.search(
                        rf"\b{re.escape(var)}\s*\.(size|length|empty|at)\s*\(",
                        window_text,
                        re.IGNORECASE,
                    ):
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="buffer_overflow",
                                pattern="string_bounds_check",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description=f"string {var} accessed with [] may go out of bounds; using .at() for bounds checking is recommended.",
                                suggestion="Use the .at() method for safe access, or explicitly check the index range before using [].",
                                confidence=0.6,
                                severity="medium",
                            )
                        )
                        break  # report only once per line
    return issues


def _rule_missing_virtual_dtor(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect the issue of a base class missing a virtual destructor.
    Heuristic: detect class declarations; if virtual functions exist but the destructor is not virtual, flag it.
    """
    issues: List[Issue] = []
    classes: dict[
        str, dict[str, Any]
    ] = {}  # class_name -> {"line": int, "has_virtual": bool, "has_virtual_dtor": bool}
    current_class: Optional[str] = None
    in_class = False
    brace_depth = 0

    for idx, s in enumerate(lines, start=1):
        # Detect class declarations
        m_class = RE_CLASS_DECL.search(s)
        if m_class:
            class_name = m_class.group(1)
            classes[class_name] = {
                "line": idx,
                "has_virtual": False,
                "has_virtual_dtor": False,
            }
            current_class = class_name
            in_class = True
            brace_depth = s.count("{") - s.count("}")
            continue

        if in_class and current_class:
            brace_depth += s.count("{") - s.count("}")
            if brace_depth <= 0:
                in_class = False
                current_class = None
                continue

            # Detect virtual functions
            if re.search(r"\bvirtual\s+[^~]", s, re.IGNORECASE):
                classes[current_class]["has_virtual"] = True

            # Detect virtual destructors
            if RE_VIRTUAL_DTOR.search(s):
                classes[current_class]["has_virtual_dtor"] = True

    # Check classes that have virtual functions but no virtual destructor
    for class_name, info in classes.items():
        if info["has_virtual"] and not info["has_virtual_dtor"]:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="memory_mgmt",
                    pattern="missing_virtual_dtor",
                    file=relpath,
                    line=info["line"],
                    evidence=_strip_line(_safe_line(lines, info["line"])),
                    description=f"Class {class_name} contains virtual functions but its destructor is not virtual; deleting a derived-class object through a base-class pointer may cause undefined behavior.",
                    suggestion="Add a virtual destructor to the base class to ensure the derived-class destructor is correctly called when deleting a derived-class object through a base-class pointer.",
                    confidence=0.75,
                    severity="high",
                )
            )

    return issues


def _rule_move_after_use(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect use-after-move risk: an object is still used after being std::move'd.
    """
    issues: List[Issue] = []
    moved_vars: dict[str, int] = {}  # var -> line_no (the moved variable)

    for idx, s in enumerate(lines, start=1):
        # Detect std::move assignment: extract the moved variable (the argument in std::move(...))
        m = RE_MOVE_ASSIGN.search(s)
        if m:
            # Extract the moved variable name from std::move(...)
            move_match = re.search(
                r"std::move\s*\(\s*([A-Za-z_]\w*)\s*\)", s, re.IGNORECASE
            )
            if move_match:
                var = move_match.group(1)  # the moved variable
                moved_vars[var] = idx

        # Detect use after move
        vars_to_remove: set[str] = set()  # collect keys to remove, to avoid modifying the dict during iteration
        for var, move_line in moved_vars.items():
            if idx > move_line and idx <= move_line + 10:  # within 10 lines after the move
                # Detect variable usage (excluding reassignment)
                if re.search(rf"\b{re.escape(var)}\b", s) and not re.search(
                    rf"\b{re.escape(var)}\s*=", s
                ):
                    # Check whether it is a reassignment (resets the moved state)
                    if re.search(rf"\b{re.escape(var)}\s*=\s*(?!std::move)", s):
                        # Reassignment, remove the record
                        vars_to_remove.add(var)
                    else:
                        # Possibly a usage
                        if re.search(rf"\b{re.escape(var)}\s*(->|\[|\.|\(|,)", s):
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="memory_mgmt",
                                    pattern="move_after_use",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(s),
                                    description=f"Variable {var} is still used after std::move; the moved-from object is in a valid but unspecified state, which may cause undefined behavior.",
                                    suggestion="A moved-from object should not be used again unless reassigned; consider stopping use of the object immediately after applying move semantics.",
                                    confidence=0.7,
                                    severity="high",
                                )
                            )
                            # Remove the record to avoid duplicate reports
                            vars_to_remove.add(var)

        # Delete after the iteration ends
        for var in vars_to_remove:
            moved_vars.pop(var, None)

    return issues


def _rule_uncaught_exception(lines: Sequence[str], relpath: str) -> List[Issue]:
    """
    Detect potentially uncaught exceptions: no try-catch is seen near a throw statement.
    """
    issues: List[Issue] = []
    for idx, s in enumerate(lines, start=1):
        if RE_THROW.search(s):
            # Check whether there is a try-catch nearby
            window_text = " ".join(
                t for _, t in _window(lines, idx, before=10, after=10)
            )
            has_try = RE_TRY.search(window_text) is not None
            has_catch = RE_CATCH.search(window_text) is not None

            if not (has_try and has_catch):
                conf = 0.6
                # Risk is higher if an exception is thrown in a noexcept function
                prev_text = " ".join(
                    t for _, t in _window(lines, idx, before=5, after=0)
                )
                if RE_NOEXCEPT.search(prev_text):
                    conf += 0.2

                issues.append(
                    Issue(
                        language="c/cpp",
                        category="error_handling",
                        pattern="uncaught_exception",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="A throw statement was detected but no try-catch block is seen nearby, which may lead to an uncaught exception.",
                        suggestion="Ensure exceptions are caught in an appropriate scope; consider using RAII to ensure resources are correctly released during exceptions.",
                        confidence=min(conf, 0.85),
                        severity="high" if conf >= 0.8 else "medium",
                    )
                )
    return issues


def _rule_smart_ptr_cycle(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect possible cyclic reference issues with smart pointers (heuristic).
    Note: fully detecting cyclic references requires graph analysis; here only simple heuristic detection is performed.
    """
    issues: List[Issue] = []
    shared_ptr_vars: set[str] = set()

    for idx, s in enumerate(lines, start=1):
        # Collect shared_ptr variables
        if RE_SHARED_PTR.search(s):
            m = RE_SMART_PTR_ASSIGN.search(s)
            if m:
                var = m.group(1)
                shared_ptr_vars.add(var)

        # Detect mutual references between shared_ptrs (simple heuristic)
        if RE_SHARED_PTR.search(s) and shared_ptr_vars:
            # Check whether another shared_ptr is used in a shared_ptr initialization
            for var in shared_ptr_vars:
                if (
                    re.search(rf"\b{re.escape(var)}\b", s)
                    and "make_shared" in s.lower()
                ):
                    # Simple heuristic: if two shared_ptrs reference each other, a cycle may exist
                    # This is only a hint; more complex analysis is actually needed
                    pass

    # Detect usage of weak_ptr (usually used to break cyclic references)
    has_weak_ptr = False
    for idx, s in enumerate(lines, start=1):
        if RE_WEAK_PTR.search(s):
            has_weak_ptr = True
            break

    # If shared_ptr is heavily used but no weak_ptr is seen, flag possible cyclic reference risk
    if len(shared_ptr_vars) > 3 and not has_weak_ptr:
        # Flag at the first shared_ptr usage
        for idx, s in enumerate(lines, start=1):
            if RE_SHARED_PTR.search(s):
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="smart_ptr_cycle_risk",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description="Multiple shared_ptr usages were detected but no weak_ptr was seen; there may be a risk of memory leaks caused by cyclic references.",
                        suggestion="Check reference relationships between objects and use weak_ptr to break cyclic references when necessary; consider replacing shared_ptr with unique_ptr to clarify ownership.",
                        confidence=0.5,
                        severity="medium",
                    )
                )
                break

    return issues


def _rule_cpp_deadlock_patterns(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect deadlock risks related to the C++ standard library (std::mutex):
    - Double locking: the same mutex is locked again without being unlocked
    - Possibly missing unlock: no corresponding unlock() is seen in the following window after lock()
    - Lock order inversion: both (A->B) and (B->A) locking orders exist
    - Not using std::lock/scoped_lock: no deadlock-avoidance mechanism is used when manually locking multiple mutexes
    Implementation is heuristic-based and may produce false positives.
    """
    issues: List[Issue] = []
    lock_stack: list[str] = []  # stack of currently held locks
    order_pairs: dict[tuple[str, str], int] = {}  # locking order pair -> line number
    mutex_vars: set[str] = set()  # all mutex variable names

    # First collect all mutex variables
    for idx, s in enumerate(lines, start=1):
        m = RE_STD_MUTEX.search(s)
        if m:
            mutex_vars.add(m.group(1))

    # Scan lock/unlock operations
    for idx, s in enumerate(lines, start=1):
        # Detect lock() calls
        m_lock = RE_MUTEX_LOCK.search(s)
        if m_lock:
            mtx = m_lock.group(1)
            if mtx in mutex_vars:
                # Double-lock detection
                if mtx in lock_stack:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="error_handling",
                            pattern="cpp_double_lock",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description=f"mutex {mtx} is locked again without being unlocked, posing a deadlock risk.",
                            suggestion="Avoid locking the same mutex repeatedly; consider using std::recursive_mutex or refactoring the code to avoid nested locking.",
                            confidence=0.8,
                            severity="high",
                        )
                    )
                # Record lock order
                if lock_stack and lock_stack[-1] != mtx:
                    pair = (lock_stack[-1], mtx)
                    order_pairs.setdefault(pair, idx)
                lock_stack.append(mtx)

        # Detect unlock() calls
        m_unlock = RE_MUTEX_UNLOCK.search(s)
        if m_unlock:
            mtx = m_unlock.group(1)
            if mtx in mutex_vars and mtx in lock_stack:
                # Remove the most recent matching lock from the stack
                for k in range(len(lock_stack) - 1, -1, -1):
                    if lock_stack[k] == mtx:
                        del lock_stack[k]
                        break

        # Detect lock_guard/unique_lock (RAII, automatic unlock, usually safer)
        RE_LOCK_GUARD.search(s) or RE_UNIQUE_LOCK.search(s) or RE_SHARED_LOCK.search(s)

        # Detect std::lock or scoped_lock (deadlock-avoidance mechanism)
        has_safe_lock = RE_STD_LOCK.search(s) or RE_SCOPED_LOCK.search(s)

        # Roughly reset at scope end
        if "}" in s and not has_safe_lock:
            # If the scope ends while locks remain on the stack, it may be a problem (but it could be an RAII lock, so lower confidence)
            if lock_stack:
                # Not reporting an error here directly, since it may be an RAII lock
                pass

        # Detect manually locking multiple mutexes without using std::lock
        if m_lock and len(lock_stack) > 1 and not has_safe_lock:
            # When locking a second mutex, if a lock is already held and std::lock was not used, flag the risk
            if idx > 1:
                prev_text = " ".join(
                    _safe_line(lines, j) for j in range(max(1, idx - 3), idx)
                )
                if not RE_STD_LOCK.search(prev_text) and not RE_SCOPED_LOCK.search(
                    prev_text
                ):
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="error_handling",
                            pattern="cpp_multiple_lock_unsafe",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description="Manually locking multiple mutexes was detected without using std::lock or std::scoped_lock, posing a deadlock risk.",
                            suggestion="Use std::lock or std::scoped_lock to lock multiple mutexes simultaneously to avoid deadlock; or unify the locking order.",
                            confidence=0.65,
                            severity="high",
                        )
                    )

    # Lock order inversion detection
    for (a, b), ln in order_pairs.items():
        if (b, a) in order_pairs:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="error_handling",
                    pattern="cpp_lock_order_inversion",
                    file=relpath,
                    line=order_pairs[(b, a)],
                    evidence=_strip_line(_safe_line(lines, order_pairs[(b, a)])),
                    description=f"Mutex lock order inversion detected: ({a} -> {b}) and ({b} -> {a}), posing a deadlock risk.",
                    suggestion="Unify the acquisition order of multiple locks and establish a global lock hierarchy; or use std::lock/scoped_lock to avoid deadlock.",
                    confidence=0.7,
                    severity="high",
                )
            )

    # Possibly missing unlock: no corresponding unlock() is seen within a 50-line window after lock()
    for idx, s in enumerate(lines, start=1):
        m_lock = RE_MUTEX_LOCK.search(s)
        if not m_lock:
            continue
        mtx = m_lock.group(1)
        if mtx not in mutex_vars:
            continue

        # Check whether it is lock_guard/unique_lock (RAII, automatic unlock)
        window_text = " ".join(
            _safe_line(lines, j) for j in range(idx, min(idx + 3, len(lines)) + 1)
        )
        is_raii = (
            RE_LOCK_GUARD.search(window_text)
            or RE_UNIQUE_LOCK.search(window_text)
            or RE_SHARED_LOCK.search(window_text)
        )
        if is_raii:
            continue  # RAII locks auto-unlock, skip

        end = min(len(lines), idx + 50)
        unlocked = False
        for j in range(idx + 1, end + 1):
            sj = _safe_line(lines, j)
            m_un = RE_MUTEX_UNLOCK.search(sj)
            if m_un and m_un.group(1) == mtx:
                unlocked = True
                break
            # Check scope end (may be a RAII lock)
            if "}" in sj:
                # Check whether this is the scope of lock_guard/unique_lock
                prev_scope = " ".join(
                    _safe_line(lines, k) for k in range(max(1, j - 5), j)
                )
                if RE_LOCK_GUARD.search(prev_scope) or RE_UNIQUE_LOCK.search(
                    prev_scope
                ):
                    unlocked = True
                    break

        if not unlocked:
            issues.append(
                Issue(
                    language="c/cpp",
                    category="error_handling",
                    pattern="cpp_missing_unlock_suspect",
                    file=relpath,
                    line=idx,
                    evidence=_strip_line(s),
                    description=f"No matching unlock() detected within the nearby window after calling lock() on mutex {mtx}; there may be a risk of a missing unlock.",
                    suggestion="Ensure every lock() path has a paired unlock(); consider using std::lock_guard or std::unique_lock (RAII) to manage the lock lifetime automatically.",
                    confidence=0.55,
                    severity="medium",
                )
            )

    return issues


def _rule_data_race_suspect(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    Detect possible data race risks:
    - Shared variables (global/static variables) accessed unprotected in a multithreaded environment
    - Thread creation detected but no lock protection seen when shared variables are accessed
    - volatile misuse (volatile does not guarantee thread safety)
    - Shared variables not protected with atomic operations

    The implementation is heuristic-based and needs contextual analysis.
    """
    issues: List[Issue] = []
    shared_vars: set[str] = set()  # Set of shared variables
    thread_creation_lines: list[int] = []  # Thread creation line numbers
    atomic_vars: set[str] = set()  # Set of atomic variables
    volatile_vars: set[str] = set()  # Set of volatile variables

    # First pass scan: collect shared variables, thread creation, atomic variables
    for idx, s in enumerate(lines, start=1):
        # Collect global/static variables
        m_static = RE_STATIC_VAR.search(s)
        if m_static:
            var = m_static.group(1)
            # Exclude const variables (read-only, usually safe)
            if "const" not in s.lower():
                shared_vars.add(var)

        m_extern = RE_EXTERN_VAR.search(s)
        if m_extern:
            var = m_extern.group(1)
            if "const" not in s.lower():
                shared_vars.add(var)

        # Detect global variable declarations (file scope)
        # Improvement: check whether it is outside a function (no indentation at line start, and not inside a function body)
        # Simplified judgment: variable declarations with no leading spaces/tabs that are not function parameters
        if not s.startswith(" ") and not s.startswith("\t"):
            # May be a file-scope variable declaration
            m_global = re.search(r"^[A-Za-z_]\w*(?:\s+\*|\s+)+([A-Za-z_]\w*)\s*[=;]", s)
            if m_global and "const" not in s.lower() and "static" not in s.lower():
                # Exclude function declarations (check whether there are parentheses)
                if "(" not in s:
                    var = m_global.group(1)
                    shared_vars.add(var)

        # Detect thread creation
        if RE_PTHREAD_CREATE.search(s) or RE_STD_THREAD.search(s):
            thread_creation_lines.append(idx)

        # Collect atomic variables
        m_atomic = RE_ATOMIC.search(s)
        if m_atomic:
            var = m_atomic.group(1)
            atomic_vars.add(var)

        # Collect volatile variables
        m_volatile = RE_VOLATILE.search(s)
        if m_volatile:
            var = m_volatile.group(1)
            volatile_vars.add(var)

    # If there is no thread creation, there is usually no data race risk
    if not thread_creation_lines:
        return issues

    # Second pass scan: detect the protection status when shared variables are accessed
    for idx, s in enumerate(lines, start=1):
        # Detect access to shared variables (assignment or read)
        for var in shared_vars:
            if var in atomic_vars:
                continue  # Atomic variable, usually safe

            # Detect variable access (excluding declaration lines)
            var_pattern = re.compile(rf"\b{re.escape(var)}\b")
            if not var_pattern.search(s):
                continue

            # Exclude variable declaration lines (no indentation at line start and contains a type declaration)
            if not s.startswith(" ") and not s.startswith("\t"):
                # May be a variable declaration; check whether there is a type keyword
                if re.search(r"^[A-Za-z_]\w*(?:\s+\*|\s+)+[A-Za-z_]\w*\s*[=;]", s):
                    continue  # Skip variable declaration line

            # Check whether it is an assignment operation
            is_write = RE_VAR_ASSIGN.search(s) and var in s[: s.find("=")]

            # Check whether there is lock protection nearby
            window_text = " ".join(t for _, t in _window(lines, idx, before=5, after=5))
            has_lock = (
                RE_PTHREAD_LOCK.search(window_text) is not None
                or RE_MUTEX_LOCK.search(window_text) is not None
                or RE_LOCK_GUARD.search(window_text) is not None
                or RE_UNIQUE_LOCK.search(window_text) is not None
                or RE_SHARED_LOCK.search(window_text) is not None
            )

            # Check whether it is within the scope of a lock (simple heuristic)
            # Find the nearest lock
            lock_line = None
            for j in range(max(1, idx - 10), idx):
                sj = _safe_line(lines, j)
                if (
                    RE_PTHREAD_LOCK.search(sj)
                    or RE_MUTEX_LOCK.search(sj)
                    or RE_LOCK_GUARD.search(sj)
                    or RE_UNIQUE_LOCK.search(sj)
                ):
                    lock_line = j
                    break

            # Check whether the lock has been unlocked
            unlocked = False
            if lock_line:
                for j in range(lock_line + 1, idx):
                    sj = _safe_line(lines, j)
                    if RE_PTHREAD_UNLOCK.search(sj) or RE_MUTEX_UNLOCK.search(sj):
                        unlocked = True
                        break

            # If no lock protection is detected and it is a write operation, the risk is higher
            if not has_lock or (lock_line and unlocked):
                # Optimization: only report clear write operations; greatly lower the confidence for read operations
                if not is_write:
                    # A pure read operation has lower risk without a lock, skip reporting
                    # Unless it is a volatile variable (may be misused)
                    if var not in volatile_vars:
                        continue
                    conf = 0.4  # volatile read operation, low confidence
                else:
                    conf = 0.6
                    if var in volatile_vars:
                        # volatile does not guarantee thread safety, but may be misused
                        conf += 0.1

                # Check whether it is among function arguments (may be a local variable, lowers risk)
                if "(" in s and ")" in s:
                    # May be a function call argument, lower confidence
                    conf -= 0.1

                # Further lower confidence: if there is a lock nearby, even if not inside the critical section, there may be other protection mechanisms
                if has_lock and (lock_line and unlocked):
                    conf -= 0.15  # There is a lock but it is unlocked, may be intentional design

                # Only report issues with sufficiently high confidence
                if conf >= 0.5:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="concurrency",
                            pattern="data_race_suspect",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(s),
                            description=f"Shared variable {var} is accessed in a multithreaded environment without clear lock protection; there may be a data race risk.",
                            suggestion="Use a mutex to protect shared variable access; or use atomic operations (std::atomic) for lock-free programming; note that volatile does not guarantee thread safety.",
                            confidence=min(conf, 0.85),
                            severity="high" if conf >= 0.7 else "medium",
                        )
                    )

    # Detect misuse of volatile (volatile does not guarantee thread safety)
    for idx, s in enumerate(lines, start=1):
        for var in volatile_vars:
            if var in atomic_vars:
                continue  # If it is also an atomic variable, skip

            if re.search(rf"\b{re.escape(var)}\b", s):
                # Check whether volatile is used in a multithreaded context
                window_text = " ".join(
                    t for _, t in _window(lines, idx, before=3, after=3)
                )
                has_thread = (
                    RE_PTHREAD_CREATE.search(window_text) is not None
                    or RE_STD_THREAD.search(window_text) is not None
                    or any(abs(j - idx) < 20 for j in thread_creation_lines)
                )

                if has_thread:
                    # Check whether there is lock protection
                    has_lock = (
                        RE_PTHREAD_LOCK.search(window_text) is not None
                        or RE_MUTEX_LOCK.search(window_text) is not None
                        or RE_LOCK_GUARD.search(window_text) is not None
                    )

                    if not has_lock:
                        issues.append(
                            Issue(
                                language="c/cpp",
                                category="concurrency",
                                pattern="volatile_not_threadsafe",
                                file=relpath,
                                line=idx,
                                evidence=_strip_line(s),
                                description=f"volatile variable {var} is used in a multithreaded environment, but volatile does not guarantee thread safety; there may be a data race.",
                                suggestion="volatile only prevents compiler optimization and does not guarantee atomicity or memory visibility; use std::atomic or a mutex to protect shared variables.",
                                confidence=0.7,
                                severity="high",
                            )
                        )

    return issues


def _rule_smart_ptr_get_unsafe(
    lines: Sequence[str], relpath: str, database: Optional[ProjectDatabase] = None
) -> List[Issue]:
    """
    Detect unsafe use of the smart pointer .get() method (the returned raw pointer may dangle).
    """
    issues: List[Issue] = []
    smart_ptr_vars: set[str] = set()

    # First collect smart pointer variables
    for idx, s in enumerate(lines, start=1):
        m = RE_SMART_PTR_ASSIGN.search(s)
        if m:
            smart_ptr_vars.add(m.group(1))
        # Also detect declarations
        if RE_SHARED_PTR.search(s) or RE_UNIQUE_PTR.search(s) or RE_WEAK_PTR.search(s):
            m = re.search(r"\b([A-Za-z_]\w*)\s*(?:=|;)", s)
            if m:
                smart_ptr_vars.add(m.group(1))

    for idx, s in enumerate(lines, start=1):
        # Detect .get() calls
        for var in smart_ptr_vars:
            if re.search(rf"\b{re.escape(var)}\s*\.get\s*\(", s, re.IGNORECASE):
                conf = 0.65
                # If the result of .get() is stored or passed on, the risk is higher
                if "=" in s or re.search(r"\.get\s*\([^)]*\)\s*[=,\(]", s):
                    conf += 0.1

                issues.append(
                    Issue(
                        language="c/cpp",
                        category="memory_mgmt",
                        pattern="smart_ptr_get_unsafe",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(s),
                        description=f"Smart pointer {var} uses the .get() method to obtain a raw pointer; if the smart pointer's lifetime ends, the raw pointer will dangle.",
                        suggestion="Avoid storing the raw pointer returned by .get(); if it must be used, ensure the smart pointer's lifetime covers the usage period of the raw pointer.",
                        confidence=min(conf, 0.8),
                        severity="high",
                    )
                )
                break  # Report only once per line
    return issues


def _rule_deserialization(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-502: Deserialization of untrusted data detection
    Detection points:
    - Deserialization of untrusted data (pickle, yaml, json, etc.)
    - Missing type validation
    - Missing size limit
    """
    issues: List[Issue] = []

    # Deserialization function patterns
    deserialize_funcs = [
        "json_loads",
        "json_load",
        "yaml_load",
        "pickle_loads",
        "pickle_load",
        "protobuf_decode",
        "msgpack_unpack",
        "cbor_decode",
        "xml_parse",
        "unserialize",
        "deserialize",
        "decode",
    ]

    # Detect deserialization function calls
    for idx, line in enumerate(lines, start=1):
        # Detect deserialization function calls
        for func in deserialize_funcs:
            if re.search(rf"\b{func}\s*\(", line, re.IGNORECASE):
                # Check whether there is type validation (look back 5 lines and look ahead 10 lines)
                has_type_check = False
                lookback_lines = lines[max(0, idx - 6) : idx]
                lookahead_lines = lines[idx : min(len(lines), idx + 10)]

                # Check the preceding type validation
                for prev_line in lookback_lines:
                    if re.search(
                        r"\b(json_is_|validate|check|verify|whitelist|schema)",
                        prev_line,
                        re.IGNORECASE,
                    ):
                        has_type_check = True
                        break

                # Check the following type validation
                if not has_type_check:
                    for next_line in lookahead_lines:
                        if re.search(
                            r"\b(json_is_|validate|check|verify|whitelist|schema)",
                            next_line,
                            re.IGNORECASE,
                        ):
                            has_type_check = True
                            break

                # Check whether there is a size limit
                has_size_limit = False
                for prev_line in lookback_lines:
                    if re.search(
                        r"\b(max|limit|bound|size|depth)\b", prev_line, re.IGNORECASE
                    ):
                        has_size_limit = True
                        break

                # Check the following size limit
                if not has_size_limit:
                    for next_line in lookahead_lines:
                        if re.search(
                            r"\b(max|limit|bound|size|depth)\b",
                            next_line,
                            re.IGNORECASE,
                        ):
                            has_size_limit = True
                            break

                # If there is no type validation and no size limit, report the vulnerability
                if not has_type_check and not has_size_limit:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="deserialization",
                            pattern="deserialization_untrusted",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description=f"Deserialization function {func} call lacks type validation and size limit, which may lead to a deserialization vulnerability",
                            suggestion="Use a safe deserialization method, add type validation and size limits, and avoid deserializing untrusted data",
                            confidence=0.7,
                            severity="high",
                        )
                    )

    return issues


def _rule_ssrf(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-918: Server-Side Request Forgery (SSRF) detection
    Detection points:
    - User input used directly for URL construction
    - libcurl does not validate the target address
    - Missing URL whitelist validation
    """
    issues: List[Issue] = []

    # Detect curl_easy_setopt setting the URL
    for idx, line in enumerate(lines, start=1):
        # Detect CURLOPT_URL setting
        if re.search(r"CURLOPT_URL", line, re.IGNORECASE):
            # Check whether there is URL validation (look back 15 lines and look ahead 10 lines)
            has_url_validation = False
            lookback_lines = lines[max(0, idx - 16) : idx]
            lookahead_lines = lines[idx : min(len(lines), idx + 10)]

            # Check the preceding URL validation
            for prev_line in lookback_lines:
                if RE_SSRF_VALIDATE.search(prev_line):
                    has_url_validation = True
                    break

            # Check the following URL validation
            if not has_url_validation:
                for next_line in lookahead_lines:
                    if RE_SSRF_VALIDATE.search(next_line):
                        has_url_validation = True
                        break

            # If there is no URL validation, report the vulnerability
            if not has_url_validation:
                issues.append(
                    Issue(
                        language="c/cpp",
                        category="ssrf",
                        pattern="ssrf_url_validation",
                        file=relpath,
                        line=idx,
                        evidence=_strip_line(line),
                        description="curl_easy_setopt setting CURLOPT_URL lacks URL validation, which may lead to an SSRF vulnerability",
                        suggestion="Add URL whitelist validation, restrict the protocol to HTTPS, and forbid access to internal IP addresses",
                        confidence=0.7,
                        severity="high",
                    )
                )

        # Detect snprintf constructing a URL command
        if re.search(r"\b(snprintf|sprintf)\s*\(", line, re.IGNORECASE):
            # Check whether a wget/curl command is constructed
            if re.search(r"(wget|curl)\s+.*%s", line, re.IGNORECASE):
                # Check whether there is URL validation
                has_url_validation = False
                lookback_lines = lines[max(0, idx - 16) : idx]

                for prev_line in lookback_lines:
                    if RE_SSRF_VALIDATE.search(prev_line):
                        has_url_validation = True
                        break

                if not has_url_validation:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="ssrf",
                            pattern="ssrf_command_construction",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description="Using snprintf/sprintf to construct a URL command containing user input may lead to SSRF and command injection vulnerabilities",
                            suggestion="Avoid using snprintf/sprintf to construct URL commands; use a safe HTTP library and add URL validation",
                            confidence=0.8,
                            severity="critical",
                        )
                    )

        # Detect system/wget/popen executing a URL command
        if re.search(r"\b(system|popen)\s*\(", line, re.IGNORECASE):
            # Check whether it contains URL-related variables
            if re.search(r"(wget|curl|http|url)", line, re.IGNORECASE):
                # Check whether there is URL validation
                has_url_validation = False
                lookback_lines = lines[max(0, idx - 16) : idx]

                for prev_line in lookback_lines:
                    if RE_SSRF_VALIDATE.search(prev_line):
                        has_url_validation = True
                        break

                if not has_url_validation:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="ssrf",
                            pattern="ssrf_command_injection",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description="Using system/popen to execute a URL command containing user input may lead to SSRF and command injection vulnerabilities",
                            suggestion="Avoid using system/popen to execute URL commands; use a safe HTTP library and add URL validation",
                            confidence=0.8,
                            severity="critical",
                        )
                    )

    return issues


def _rule_resource_consumption(
    lines: Sequence[str], relpath: str, database: Optional["ProjectDatabase"] = None
) -> List[Issue]:
    """
    CWE-400: Uncontrolled resource consumption detection
    Detection points:
    - Loop count controlled by user input with no upper limit
    - Memory allocation size not validated
    - Unbounded recursion depth
    """
    issues: List[Issue] = []

    # Detect loop count controlled by user input
    for idx, line in enumerate(lines, start=1):
        # Detect for loops
        if re.search(r"\bfor\s*\(", line):
            # Check whether a user input variable controls the loop count
            if re.search(
                r"\bfor\s*\([^;]*;\s*[^<]*<\s*(count|size|n|num|len|length)\s*;",
                line,
                re.IGNORECASE,
            ):
                # Check whether there is an upper-limit check (look back 10 lines)
                has_limit_check = False
                lookback_lines = lines[max(0, idx - 11) : idx]

                for prev_line in lookback_lines:
                    if RE_RESOURCE_LIMIT.search(prev_line) or re.search(
                        r"\b(if|MAX|LIMIT|BOUND)\b", prev_line, re.IGNORECASE
                    ):
                        has_limit_check = True
                        break

                if not has_limit_check:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="resource_consumption",
                            pattern="unbounded_loop",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description="Loop count is controlled by user input with no upper-limit check, which may lead to a resource-exhaustion DoS attack",
                            suggestion="Add an upper-limit check for the loop count and limit the maximum number of iterations",
                            confidence=0.6,
                            severity="medium",
                        )
                    )

        # Detect memory allocation size not validated
        if RE_RESOURCE_API.search(line):
            # Check whether there is a size variable and whether the variable name implies user input or external source
            # Only detect variables explicitly coming from user input: user_input, input, argv, argc, req, request, etc.
            user_input_patterns = [
                r"\b(user_input|user_size|input_size|req_size|request_size)\s*\)",
                r"malloc\s*\(\s*(atoi|atol|strtol|strtoul)\s*\(",  # malloc(atoi(...))
                r"malloc\s*\(\s*\w+\s*\*\s*\w+\s*\)",  # malloc(n * size) multiplication
            ]
            is_user_controlled = False
            for pattern in user_input_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    is_user_controlled = True
                    break

            if is_user_controlled:
                # Check whether there is a size limit check (look back 10 lines)
                has_size_check = False
                lookback_lines = lines[max(0, idx - 11) : idx]

                for prev_line in lookback_lines:
                    if RE_RESOURCE_LIMIT.search(prev_line) or re.search(
                        r"\b(if|MAX|LIMIT|BOUND|size.*>|size.*<)\b",
                        prev_line,
                        re.IGNORECASE,
                    ):
                        has_size_check = True
                        break

                if not has_size_check:
                    issues.append(
                        Issue(
                            language="c/cpp",
                            category="resource_consumption",
                            pattern="unbounded_allocation",
                            file=relpath,
                            line=idx,
                            evidence=_strip_line(line),
                            description="Memory allocation size is controlled by user input with no upper-limit check, which may lead to a memory-exhaustion DoS attack",
                            suggestion="Add an upper-limit check for the allocation size and limit the maximum allocation size",
                            confidence=0.6,
                            severity="medium",
                        )
                    )

        # Detect unbounded recursion depth
        # Match function definitions: return type + function name + parameter list + {
        if re.search(
            r"\b(void|int|char|float|double|long|short|unsigned|signed|static|inline)\s+\w+\s*\([^)]*\)\s*\{",
            line,
        ):
            # Check whether the function name is called within the function body (recursion)
            func_match = re.search(r"\b(\w+)\s*\([^)]*\)\s*\{", line)
            if func_match:
                func_name = func_match.group(1)
                # Look ahead to see whether the function body contains a recursive call
                # Note: idx starts from 1, Python list indexing starts from 0
                # Use bracket matching to determine the function body extent
                brace_count = line.count("{") - line.count("}")
                func_body_lines = []
                for i in range(idx, min(len(lines), idx + 50)):
                    func_body_lines.append(lines[i])
                    brace_count += lines[i].count("{") - lines[i].count("}")
                    if brace_count == 0:
                        break

                # Only detect recursive calls within the function body
                for next_line in func_body_lines:
                    if re.search(rf"\b{func_name}\s*\(", next_line):
                        # Check whether there is a depth limit check
                        has_depth_check = False
                        lookback_lines = lines[max(0, idx - 11) : idx]

                        for prev_line in lookback_lines:
                            if RE_RESOURCE_LIMIT.search(prev_line) or re.search(
                                r"\b(depth|MAX|LIMIT)\b", prev_line, re.IGNORECASE
                            ):
                                has_depth_check = True
                                break

                        # Check whether there is a depth check within the function body
                        if not has_depth_check:
                            for check_line in func_body_lines:
                                if re.search(
                                    r"\b(depth|MAX|LIMIT)\b", check_line, re.IGNORECASE
                                ):
                                    has_depth_check = True
                                    break

                        if not has_depth_check:
                            issues.append(
                                Issue(
                                    language="c/cpp",
                                    category="resource_consumption",
                                    pattern="unbounded_recursion",
                                    file=relpath,
                                    line=idx,
                                    evidence=_strip_line(line),
                                    description="Recursive function lacks a depth limit, which may lead to a stack-overflow DoS attack",
                                    suggestion="Add a recursion depth limit, or switch to an iterative implementation",
                                    confidence=0.6,
                                    severity="medium",
                                )
                            )
                        break

    return issues


def analyze_c_cpp_text(
    relpath: str,
    text: str,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
    Perform C/C++ heuristic analysis based on the provided text.
    - Accuracy optimization: remove comments before heuristic matching (preserving string/character literals),
      to avoid false positives caused by API matches inside comments.
    - Accuracy optimization 2: use a "string content masked" copy for the generic API scan, to avoid treating fragments inside strings as code.
    - Accuracy optimization 3: use data flow analysis to filter false positives (set to NULL after free, if-condition protection, etc.).

    Args:
        relpath: relative file path
text: source code text
database: project database instance (optional)
    """
    pre_text = _strip_if0_blocks(text)
    clean_text = _remove_comments_preserve_strings(pre_text)
    masked_text = _mask_strings_preserve_len(clean_text)
# Raw lines: preserve string contents, for rules that need to parse literals (such as format strings, scanf widths, etc.)
    lines = clean_text.splitlines()
# Masked lines: string contents replaced by spaces, suitable for generic API/keyword matching, reducing false positives
    mlines = masked_text.splitlines()

# Data flow analysis (used for false positive filtering)
# If there is no database, create a temporary in-memory database and use DataCollector to collect data
    _temp_database = None
    _db_file_path = relpath  # File path used to query the database
    if database is None:
        try:
            from haijunbot.haijunbot_sec.project_database import ProjectDatabase
            from haijunbot.haijunbot_sec.data_collector import DataCollector

            _temp_database = ProjectDatabase(".", in_memory=True)
            collector = DataCollector(_temp_database)
            lang = "cpp" if _is_cpp_file(relpath) else "c"
# Write to a temporary file for DataCollector analysis
            import tempfile
            import os

            _tmp_dir = tempfile.mkdtemp(prefix="hsec_")
            _tmp_file = os.path.join(_tmp_dir, os.path.basename(relpath))
            with open(_tmp_file, "w", encoding="utf-8") as f:
                f.write(text)
            collector.analyze_file(_tmp_file, lang)
# Query the database using the full path of the temporary file
            _db_file_path = _tmp_file
            database = _temp_database
        except Exception:
             pass  # Continue using an empty database if creation fails
    else:
# When there is an external database, ensure the correct file path is used
# If relpath is an absolute path, use it directly; otherwise it needs to match a path in the database
        import os

        if os.path.isabs(relpath):
            _db_file_path = relpath

    data_flow_analyzer = DataFlowAnalyzer()
    data_flow_result = data_flow_analyzer.analyze_code(
        text, is_cpp=_is_cpp_file(relpath), database=database, file_path=_db_file_path
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
    issues.extend(_rule_unsafe_api(mlines, _db_file_path, database=database))
    issues.extend(_rule_boundary_funcs(mlines, _db_file_path, lines, database=database))
    issues.extend(_rule_realloc_assign_back(mlines, _db_file_path, database=database))
    issues.extend(_rule_malloc_no_null_check(mlines, _db_file_path, database=database))
    issues.extend(
        _rule_function_return_ptr_no_check(mlines, _db_file_path, database=database)
    )
    issues.extend(_rule_unchecked_io(mlines, _db_file_path, database=database))
# Rules that need string literal information (using raw lines)
    issues.extend(_rule_strncpy_no_nullterm(lines, _db_file_path, database=database))
    issues.extend(_rule_format_string(lines, _db_file_path, database=database))
    issues.extend(_rule_scanf_no_width(lines, _db_file_path, database=database))
# signal handler security check
    issues.extend(_rule_signal_handler_unsafe(lines, _db_file_path, database=database))
# Other rules
    issues.extend(_rule_insecure_tmpfile(mlines, _db_file_path, database=database))
    issues.extend(_rule_command_execution(mlines, _db_file_path, database=database))
# New rules: SQL injection, memory leak, path traversal
    issues.extend(_rule_sql_injection(lines, _db_file_path, database=database))
    issues.extend(_rule_memory_leak(lines, _db_file_path, database=database))
    issues.extend(_rule_path_traversal(lines, _db_file_path, database=database))
# New rules: integer overflow, hardcoded credentials, TOCTOU race
    issues.extend(_rule_integer_overflow(lines, _db_file_path, database=database))
    issues.extend(_rule_hardcoded_credentials(lines, _db_file_path, database=database))
    issues.extend(_rule_toctou_race(lines, _db_file_path, database=database))
    issues.extend(_rule_alloc_size_overflow(mlines, _db_file_path, database=database))
# P14 new rules: weak encryption, uninitialized variables, sign conversion, divide by zero, compiler optimization
    issues.extend(_rule_weak_crypto(lines, _db_file_path, database=database))
    issues.extend(_rule_uninitialized_var(lines, _db_file_path, database=database))
    issues.extend(_rule_signed_to_unsigned(lines, _db_file_path, database=database))
    issues.extend(_rule_divide_by_zero(lines, _db_file_path, database=database))
# Disabled: false positive rate too high, most code does not need volatile
    # issues.extend(_rule_compiler_security_check(lines, _db_file_path, database=database))
# P15 new rules: pointer arithmetic errors, deadlock risk, conditional assignment
    issues.extend(
        _rule_pointer_arithmetic_error(lines, _db_file_path, database=database)
    )
    issues.extend(_rule_deadlock_risk(lines, _db_file_path, database=database))
    issues.extend(
        _rule_assignment_in_condition(lines, _db_file_path, database=database)
    )
    issues.extend(
        _rule_double_free_and_free_non_heap(mlines, _db_file_path, database=database)
    )
    issues.extend(_rule_atoi_family(mlines, _db_file_path, database=database))
    issues.extend(_rule_rand_insecure(mlines, _db_file_path, database=database))
    issues.extend(_rule_strtok_nonreentrant(mlines, _db_file_path, database=database))
    issues.extend(_rule_open_permissive_perms(mlines, _db_file_path, database=database))
    issues.extend(_rule_alloca_unbounded(mlines, _db_file_path, database=database))
    issues.extend(_rule_vla_usage(mlines, _db_file_path, database=database))
    issues.extend(
        _rule_pthread_returns_unchecked(mlines, _db_file_path, database=database)
    )
    issues.extend(_rule_cond_wait_no_loop(mlines, _db_file_path, database=database))
    issues.extend(_rule_thread_leak_no_join(mlines, _db_file_path, database=database))
    issues.extend(_rule_inet_legacy(mlines, _db_file_path, database=database))
    issues.extend(
        _rule_time_apis_not_threadsafe(mlines, _db_file_path, database=database)
    )
    issues.extend(_rule_getenv_unchecked(mlines, _db_file_path, database=database))
# Complex semantics (use masked lines to avoid string interference)
    issues.extend(_rule_uaf_suspect(mlines, _db_file_path, database=database))
    issues.extend(_rule_possible_null_deref(mlines, _db_file_path, database=database))
    issues.extend(_rule_uninitialized_ptr_use(mlines, _db_file_path, database=database))
    issues.extend(_rule_deadlock_patterns(mlines, _db_file_path, database=database))
# C++ specific check rules
    issues.extend(_rule_new_delete_mismatch(mlines, _db_file_path, database=database))
    issues.extend(_rule_reinterpret_cast_unsafe(mlines, _db_file_path))
    issues.extend(_rule_const_cast_unsafe(mlines, _db_file_path, database=database))
    issues.extend(
        _rule_vector_string_bounds_check(mlines, _db_file_path, database=database)
    )
    issues.extend(_rule_missing_virtual_dtor(mlines, _db_file_path, database=database))
    issues.extend(_rule_move_after_use(mlines, _db_file_path, database=database))
    issues.extend(_rule_uncaught_exception(mlines, _db_file_path))
    issues.extend(_rule_smart_ptr_cycle(mlines, _db_file_path, database=database))
    issues.extend(_rule_smart_ptr_get_unsafe(mlines, _db_file_path, database=database))
# C++ deadlock detection
    issues.extend(_rule_cpp_deadlock_patterns(mlines, _db_file_path, database=database))
# Data race detection
    issues.extend(_rule_data_race_suspect(mlines, _db_file_path, database=database))
# CWE-502: deserialization vulnerability detection
    issues.extend(_rule_deserialization(lines, _db_file_path, database=database))
# CWE-918: SSRF vulnerability detection
    issues.extend(_rule_ssrf(lines, _db_file_path, database=database))
# CWE-400: uncontrolled resource consumption detection
    issues.extend(_rule_resource_consumption(lines, _db_file_path, database=database))

# Taint analysis (core functionality)
    try:
        analyzer = taint_analyzer.TaintAnalyzerFactory.create("joern")
        if analyzer is not None:
            taint_issues = analyzer.analyze(text, str(_db_file_path))
# Convert taint analysis results into Issue objects
            for taint_path in taint_issues:
                issue = Issue(
                    language="c/cpp",
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
# Silently ignore taint analysis failures, without affecting heuristic scanning
        pass
# Use data flow analysis to filter false positives
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
Use data flow analysis to filter false positives

    Args:
issues: list of problems found by heuristic scanning
analyzer: data flow analyzer
dataflow_result: data flow analysis result
lines: list of source code lines

    Returns:
List[Issue]: filtered list of problems
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
Determine whether a problem is a false positive

    Args:
issue: issue object
analyzer: data flow analyzer
dataflow_result: data flow analysis result
lines: list of source code lines

    Returns:
bool: whether it is a false positive
    """
    issue_type = issue.pattern

# UAF false positive filtering: safe pattern of setting NULL after free
    if issue_type in ["use_after_free_suspect", "use_after_free"]:
        return _is_uaf_false_positive(issue, analyzer, dataflow_result, lines)

# Double Free false positive filtering: check whether there is a protection mechanism
    if issue_type in ["double_free", "double_free_suspect"]:
        return _is_double_free_false_positive(issue, analyzer, dataflow_result, lines)

# Integer overflow false positive filtering: check whether there is an overflow check
    if issue_type == "integer_overflow":
        return _is_integer_overflow_false_positive(
            issue, analyzer, dataflow_result, lines
        )

# strcpy false positive filtering: check whether there is NULL check protection or dead code
    if issue_type in ["strcpy", "strncpy", "strcat", "strncat"]:
        return _is_strcpy_false_positive(issue, analyzer, dataflow_result, lines)

# SQL injection false positive filtering: check whether it is static SQL or a parameterized query
    if issue_type == "sql_injection":
        return _is_sql_injection_false_positive(issue, analyzer, dataflow_result, lines)

# Format string false positive filtering: check whether it is a constant format string
    if issue_type == "format_string":
        return _is_format_string_false_positive(issue, analyzer, dataflow_result, lines)

# memcpy false positive filtering: check whether there is length check protection
    if issue_type == "memcpy":
        return _is_memcpy_false_positive(issue, analyzer, dataflow_result, lines)

# memory_leak false positive filtering: check whether it is an ownership transfer
    if issue_type == "memory_leak":
        return _is_memory_leak_false_positive(issue, analyzer, dataflow_result, lines)

# possible_null_deref false positive filtering: check whether there is NULL check protection
    if issue_type == "possible_null_deref":
        return _is_null_deref_false_positive(issue, analyzer, dataflow_result, lines)

    return False


def _is_uaf_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether UAF is a false positive

Check logic:
1. Whether NULL is set after free
2. Whether there is NULL check protection
    """
    line_num = issue.line

# Extract the variable name from the issue message
    var_name = _extract_variable_name(issue)
    if not var_name:
        return False

# Check whether the variable access is safe
    if analyzer.is_safe_access(var_name, line_num, dataflow_result):
        return True

    return False


def _is_double_free_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether Double Free is a false positive

Check logic:
1. Whether NULL is set after the first free
2. Whether there is a NULL check before the second free
    """
    line_num = issue.line
    var_name = _extract_variable_name(issue)

    if not var_name:
        return False

# Check variable state
    if dataflow_result.pointer_states and var_name in dataflow_result.pointer_states:
        pointer_info = dataflow_result.pointer_states[var_name]

# If the variable is set to NULL, check whether there is a NULL check
        if pointer_info.state == PointerState.NULLIFIED:
            if dataflow_result.null_checks and var_name in dataflow_result.null_checks:
# Check whether the NULL check is before the current line
                for check_line in dataflow_result.null_checks[var_name]:
                    if check_line < line_num:
                        return True

    return False


def _is_integer_overflow_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether integer overflow is a false positive

Check logic:
1. Whether there is an overflow check (if condition)
2. Whether a safe function is used (such as calloc)
    """
    line_num = issue.line

# Check whether the following lines have an overflow check
    for i in range(line_num, min(line_num + 5, len(lines))):
        line = lines[i] if i < len(lines) else ""
# Check whether there is an overflow check
        if re.search(r"if\s*\(.*[<>].*\)", line):
            return True
# Check whether a safe function is used
        if "calloc" in line or "reallocarray" in line:
            return True

    return False


def _is_strcpy_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether strcpy-family functions are false positives

Check logic:
1. Whether it is a direct API call (macro wrapper calls do not apply NULL check protection)
2. Whether there is NULL check protection
3. Whether it is in dead code
    """
# Apply NULL check protection filtering only to direct API calls
# Macro wrapper calls (such as SAFE_COPY(dst, src)) internally call strcpy,
# but a NULL check (if (dst == NULL)) cannot eliminate the buffer overflow risk of strcpy
    pattern = getattr(issue, "pattern", None)
    if not pattern:
        return False
    if not issue.evidence.lstrip().startswith(pattern + "("):
        return False

    line_num = issue.line
    var_name = _extract_variable_name(issue)

    if not var_name:
        return False

# Check whether it is in dead code
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

# Check whether there is NULL check protection
    if dataflow_result.null_checks and var_name in dataflow_result.null_checks:
        for check_line in dataflow_result.null_checks[var_name]:
            if check_line < line_num:
                return True

    return False


def _is_sql_injection_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether SQL injection is a false positive

Check logic:
1. Whether it is static SQL (no variable concatenation)
2. Whether a parameterized query is used (%d, ?)
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    line = lines[line_num - 1]

# Check whether it is static SQL (string constant)
# Match strcpy(query, "SELECT ...") or snprintf(query, ..., "SELECT ...")
    if re.search(r'strcpy\s*\(\s*\w+\s*,\s*"[^"]*"\s*\)', line):
        return True

# Check whether a parameterized query is used (%d, ? etc.)
    if re.search(r"%[duifsc]", line) or "?" in line:
# But make sure it is not string concatenation (%s)
        if not re.search(r"sn?printf\s*\([^,]+,\s*[^,]+,\s*\w+\s*\)", line):
            return True

    return False


def _is_format_string_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether a format string vulnerability is a false positive

Check logic:
1. Whether it is a constant format string
    """
    line_num = issue.line
    if line_num <= 0 or line_num > len(lines):
        return False

    line = lines[line_num - 1]

# Check whether it is a constant format string
# Match printf("...", ...) or snprintf(buf, size, "...", ...)
    if re.search(r'(sn)?printf\s*\([^,]*,\s*"[^"]*"', line):
        return True

    return False


def _is_memcpy_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether memcpy is a false positive

Check logic:
1. Whether there is length check protection
    """
    line_num = issue.line

# Check whether the previous 5 lines have a length check
    for i in range(max(0, line_num - 5), line_num):
        if i < len(lines):
            line = lines[i]
# Check whether there is a length check (if (len < size))
            if re.search(r"if\s*\(.*[<>].*\)", line):
                return True

    return False


def _extract_variable_name(issue_or_msg: Issue | str) -> Optional[str]:
    """
Extract the variable name from an Issue object or issue message

    Args:
issue_or_msg: Issue object or issue message string

    Returns:
Optional[str]: variable name (if found)
    """
# If an Issue object is passed in, prefer the var_name field
    if isinstance(issue_or_msg, Issue):
        if issue_or_msg.var_name:
            return issue_or_msg.var_name
        msg = issue_or_msg.evidence
    else:
        msg = issue_or_msg

# Try to match common variable name patterns
    patterns = [
        r"variable\s+`(\w+)`",
        r"pointer\s+`(\w+)`",
        r"`(\w+)`\s+is",
        r"`(\w+)`\s+after",
    ]

    for pattern in patterns:
        match = re.search(pattern, msg)
        if match:
            return match.group(1)

# Try to extract the variable name from an assignment statement (such as: int *data = malloc(...))
    match = re.search(
        r"\b(\w+)\s*=\s*(?:\([^)]*\))?\s*(?:malloc|calloc|realloc)\s*\(", msg
    )
    if match:
        return match.group(1)

# Try to extract the variable name from an array access (such as: data[i] = ...)
    match = re.search(r"\b(\w+)\s*\[", msg)
    if match:
        return match.group(1)

# Try to extract the variable name from a pointer dereference (such as: *ptr = ...)
    match = re.search(r"\*\s*(\w+)", msg)
    if match:
        return match.group(1)

# Try to extract the variable name from the first argument of a function call (such as: strcpy(buf, ...), memcpy(data, ...))
    match = re.search(r"\b\w+\s*\(\s*(\w+)\s*,", msg)
    if match:
        return match.group(1)

    return None


def analyze_c_cpp_file(
    base: Path,
    relpath: Path,
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
Read a file from disk for analysis.

    Args:
base: base path
relpath: relative path
database: project database instance (optional)
    """
    try:
        text = (base / relpath).read_text(errors="ignore")
    except Exception:
        return []
    return analyze_c_cpp_text(str(relpath), text, database=database)


def analyze_files(
    base_path: str,
    files: Iterable[str],
    database: Optional["ProjectDatabase"] = None,
) -> List[Issue]:
    """
Batch-analyze files, with relative paths relative to base_path.

    Args:
base_path: base path
files: list of files
database: project database instance (optional)
    """
    base = Path(base_path).resolve()
    out: List[Issue] = []
    for f in files:
        rel = Path(f)
        out.extend(analyze_c_cpp_file(base, rel, database=database))
    return out


def _is_memory_leak_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether memory_leak is a false positive

Check logic:
1. Whether it is an ownership transfer (function returns malloc memory)
2. Whether it is freed within the same function

    Args:
issue: issue object
analyzer: data flow analyzer
dataflow_result: data flow analysis result
lines: list of source code lines

    Returns:
bool: whether it is a false positive
    """
    var_name = _extract_variable_name(issue)

    if not var_name:
        return False

# Check whether it is an ownership transfer
    if (
        dataflow_result.ownership_transfer
        and var_name in dataflow_result.ownership_transfer
    ):
        return True

    return False


def _is_null_deref_false_positive(
    issue: Issue,
    analyzer: DataFlowAnalyzer,
    dataflow_result: DataFlowResult,
    lines: List[str],
) -> bool:
    """
Determine whether possible_null_deref is a false positive

Check logic:
1. Whether there is NULL check protection
2. Whether it is a function parameter and has a NULL check
3. Whether it is in a dead code line

    Args:
issue: issue object
analyzer: data flow analyzer
dataflow_result: data flow analysis result
lines: list of source code lines

    Returns:
        bool: Whether it is a false positive
    """
    line_num = issue.line
    var_name = _extract_variable_name(issue)

    if not var_name:
        return False

    # Check whether it is in a dead code line
    if dataflow_result.dead_code_lines and line_num in dataflow_result.dead_code_lines:
        return True

    # Check whether there is NULL check protection
    if dataflow_result.null_checks and var_name in dataflow_result.null_checks:
        for check_line in dataflow_result.null_checks[var_name]:
            # NULL check is before the current line, and within the same function
            if check_line < line_num:
                # Check whether it is within the same function (simplified judgment: check that the line number difference does not exceed 50 lines)
                if line_num - check_line <= 50:
                    return True

    return False
