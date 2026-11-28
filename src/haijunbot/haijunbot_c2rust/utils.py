# -*- coding: utf-8 -*-
"""
C2Rust transpiler utility functions
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
from haijunbot.haijunbot_c2rust.constants import ORDER_JSONL
from haijunbot.haijunbot_c2rust.scanner import compute_translation_order_jsonl
from haijunbot.haijunbot_utils.config import (
    calculate_token_limit,
    get_max_input_token_count,
    save_exception,
)
from haijunbot.haijunbot_utils.git_utils import get_diff
from haijunbot.haijunbot_utils.git_utils import get_diff_file_list
from haijunbot.haijunbot_utils.jsonnet_compat import loads as json5_loads


def ensure_order_file(project_root: Path) -> Path:
    """Ensure translation_order.jsonl exists and contains valid steps; generated solely from symbols.jsonl, without any fallback."""
    data_dir = project_root / C2RUST_DIRNAME
    order_path = data_dir / ORDER_JSONL
    PrettyOutput.auto_print(f"📋 [c2rust-transpiler][order] Target order file: {order_path}")

    def _has_steps(p: Path) -> bool:
        try:
            steps = iter_order_steps(p)
            return bool(steps)
        except Exception:
            return False

    # If it already exists, validate whether it has steps
    PrettyOutput.auto_print(
        f"🔍 [c2rust-transpiler][order] Checking validity of existing order file: {order_path}"
    )
    if order_path.exists():
        if _has_steps(order_path):
            PrettyOutput.auto_print(
                f"✅ [c2rust-transpiler][order] Existing order file is valid; using {order_path}"
            )
            return order_path
        # Empty or unreadable: recompute based on the standard path (symbols.jsonl only)
        PrettyOutput.auto_print(
            "⚠️ [c2rust-transpiler][order] Existing order file is empty/invalid; recomputing based on symbols.jsonl"
        )
        try:
            compute_translation_order_jsonl(data_dir, out_path=order_path)
        except Exception as e:
            raise RuntimeError(f"Failed to recompute the translation order: {e}")
        return order_path

    # Does not exist: generate to the fixed file name along the standard path (symbols.jsonl only)
    try:
        compute_translation_order_jsonl(data_dir, out_path=order_path)
    except Exception as e:
        raise RuntimeError(f"Failed to compute the translation order: {e}")

    PrettyOutput.auto_print(
        f"📋 [c2rust-transpiler][order] Generated order file: {order_path} (exists={order_path.exists()})"
    )
    if not order_path.exists():
        raise FileNotFoundError(f"translation_order.jsonl not found after computation: {order_path}")

    # Final validation: if there are still no valid steps, raise an error and hint to run scan first or check symbols.jsonl
    if not _has_steps(order_path):
        raise RuntimeError(
            "translation_order.jsonl has no valid steps. Please run 'haijunbot-c2rust scan' first to generate symbols.jsonl and retry."
        )

    return order_path


def iter_order_steps(order_jsonl: Path) -> List[List[int]]:
    """
    Read the translation order (compatible with old and new formats) and return a list of function id sequences grouped by step.
    New format: each line contains "ids": [int, ...] and "items": [full symbol objects, ...].
    The old format is no longer supported (the "records"/"symbols" keys are not supported).
    """
    # The old format has been removed: the name->id mapping based on symbols.jsonl is no longer needed

    steps: List[List[int]] = []
    with order_jsonl.open("r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_c2rust.utils", function="iter_order_steps"
                )
                continue

            ids = obj.get("ids")
            if isinstance(ids, list) and ids:
                # New format: only ids are supported
                try:
                    ids_int = [
                        int(x)
                        for x in ids
                        if isinstance(x, (int, str)) and str(x).strip()
                    ]
                except Exception:
                    ids_int = []
                if ids_int:
                    steps.append(ids_int)
                continue
            # The old format is not supported (skip the line if there are no ids)
    return steps


def dir_tree(root: Path) -> str:
    """Format the crate directory structure (filter out some common directories)"""
    lines: List[str] = []
    exclude = {".git", "target", ".haijunbot"}
    if not root.exists():
        return ""
    for p in sorted(root.rglob("*")):
        if any(part in exclude for part in p.parts):
            continue
        rel = p.relative_to(root)
        depth = len(rel.parts) - 1
        indent = "  " * depth
        name = rel.name + ("/" if p.is_dir() else "")
        lines.append(f"{indent}- {name}")
    return "\n".join(lines)


def default_crate_dir(project_root: Path) -> Path:
    """Follow llm_module_agent's default crate directory selection: <parent>/<cwd.name>_rs (sibling of the current directory) when the input is '.'"""
    try:
        cwd = Path(".").resolve()
        if project_root.resolve() == cwd:
            return cwd.parent / f"{cwd.name}_rs"
        else:
            return project_root
    except Exception:
        return project_root


def read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        save_exception(e, module="haijunbot_c2rust.utils", function="read_json")
        pass
    return default


def write_json(path: Path, obj: Any) -> None:
    """Atomically write a JSON file: write to a temporary file first, then rename"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # Use a temporary file to ensure atomicity
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # Atomic rename
        temp_path.replace(path)
    except Exception:
        # If the atomic write fails, fall back to a direct write
        try:
            path.write_text(
                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            save_exception(e, module="haijunbot_c2rust.utils", function="write_json")
            pass


def extract_json_from_summary(text: str) -> Tuple[Dict[str, Any], Optional[str]]:
    """
    Extract structured data from the Agent summary (using JSON format):
    - Only search within the <SUMMARY>...</SUMMARY> block;
    - Directly parse the content inside the <SUMMARY> block as a JSON object (no extra <json> tag is needed);
    - Parse with jsonnet, which supports more lenient JSON syntax (such as trailing commas, comments, etc.);
    Return (parse result, error message)
    If parsing succeeds, return (data, None)
    If parsing fails, return ({}, error message)
    """
    if not isinstance(text, str) or not text.strip():
        return {}, "Summary text is empty"

    # Extract the <SUMMARY> block
    m = re.search(r"<SUMMARY>([\s\S]*?)</SUMMARY>", text, flags=re.IGNORECASE)
    block = (m.group(1) if m else text).strip()

    if not block:
        return {}, "No <SUMMARY> or </SUMMARY> tag found, or the tag content is empty"

    try:
        try:
            obj = json5_loads(block)
        except Exception as json_err:
            error_msg = f"JSON parsing failed: {str(json_err)}"
            return {}, error_msg
        if isinstance(obj, dict):
            return obj, None
        return {}, f"JSON parse result is not a dict but {type(obj).__name__}"
    except Exception as e:
        return {}, f"An exception occurred during parsing: {str(e)}"


def detect_test_deletion(log_prefix: str = "[c2rust]") -> Optional[Dict[str, Any]]:
    """
    Detect whether #[test] or #[cfg(test)] was mistakenly deleted.

    Parameters:
        log_prefix: log prefix (such as "[c2rust-transpiler]" or "[c2rust-optimizer]")

    Returns:
        If a deletion is detected, return a dict containing 'diff', 'files', 'deleted_tests'; otherwise return None
    """
    try:
        diff = get_diff()
        if not diff:
            return None

        # Check whether the diff contains a deleted #[test] or #[cfg(test)]
        test_patterns = [
            r"^-\s*#\[test\]",
            r"^-\s*#\[cfg\(test\)\]",
            r"^-\s*#\[cfg\(test\)",
        ]

        deleted_tests = []
        lines = diff.split("\n")
        current_file = None

        for i, line in enumerate(lines):
            # Detect the file path
            if (
                line.startswith("diff --git")
                or line.startswith("---")
                or line.startswith("+++")
            ):
                # Try to extract the file name from the diff line
                if line.startswith("---"):
                    parts = line.split()
                    if len(parts) > 1:
                        current_file = parts[1].lstrip("a/").lstrip("b/")
                elif line.startswith("+++"):
                    parts = line.split()
                    if len(parts) > 1:
                        current_file = parts[1].lstrip("a/").lstrip("b/")
                continue

            # Check whether a deleted test marker matches
            for pattern in test_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Check the context to confirm it is a deletion rather than a modification
                    if i > 0 and lines[i - 1].startswith("-"):
                        # It may be part of a deletion
                        deleted_tests.append(
                            {
                                "file": current_file or "unknown",
                                "line": line,
                                "line_number": i + 1,
                            }
                        )
                    elif not (i < len(lines) - 1 and lines[i + 1].startswith("+")):
                        # The next line is not an addition, which means it is a deletion
                        deleted_tests.append(
                            {
                                "file": current_file or "unknown",
                                "line": line,
                                "line_number": i + 1,
                            }
                        )
                    break

        if deleted_tests:
            modified_files = get_diff_file_list()
            return {
                "diff": diff,
                "files": modified_files,
                "deleted_tests": deleted_tests,
            }
        return None
    except Exception as e:
        PrettyOutput.auto_print(
            f"⚠️ {log_prefix}[test-detection] An exception occurred while detecting test deletion: {e}"
        )
        return None


def ask_llm_about_test_deletion(
    detection_result: Dict[str, Any], agent: Any, log_prefix: str = "[c2rust]"
) -> bool:
    """
    Ask the LLM whether test code was mistakenly deleted.

    Parameters:
        detection_result: the detection result dict, containing 'diff', 'files', 'deleted_tests'
        agent: the code generation or fix agent instance; its model is used for the query
        log_prefix: log prefix (such as "[c2rust-transpiler]" or "[c2rust-optimizer]")

    Returns:
        bool: returns True if the LLM considers the deletion unreasonable (a rollback is needed), otherwise False
    """
    if not agent or not hasattr(agent, "model"):
        # If there is no agent or the agent has no model, assume there is a problem by default (conservative strategy)
        return True

    try:
        deleted_tests = detection_result.get("deleted_tests", [])
        diff = detection_result.get("diff", "")
        files = detection_result.get("files", [])

        # Build the preview (length-limited)
        preview_lines = []
        preview_lines.append("Potentially mistaken deletion of test code markers detected:")
        preview_lines.append("")
        for item in deleted_tests[:10]:  # show at most 10
            preview_lines.append(f"- file: {item.get('file', 'unknown')}")
            preview_lines.append(f"  line: {item.get('line', '')}")
        if len(deleted_tests) > 10:
            preview_lines.append(f"... {len(deleted_tests) - 10} more deleted test markers")

        # Limit the diff length
        diff_preview = diff[:5000] if len(diff) > 5000 else diff
        if len(diff) > 5000:
            diff_preview += "\n... (diff content too long, truncated)"

        prompt = f"""Potentially mistaken deletion of test code markers (#[test] or #[cfg(test)]) was detected in the code changes; please judge whether it is reasonable:

Statistics of deleted test markers:
- Number of deleted test markers: {len(deleted_tests)}
- Files involved: {", ".join(files[:5])}{" ..." if len(files) > 5 else ""}

Details of deleted test markers:
{chr(10).join(preview_lines)}

Code change preview (diff):
{diff_preview}

Please carefully analyze the above code changes and judge whether the deletion of these test code markers is reasonable. Possible cases include:
1. Refactoring code by moving the test code elsewhere (in this case a corresponding addition should be visible)
2. Deleting outdated or duplicated test code
3. Mistakenly deleting important test code markers, causing tests unable to run

Please answer using the following protocol (must contain exactly one of the following markers):
- If you consider these deletions reasonable (the test code was correctly moved or indeed needed deletion), answer: <!!!YES!!!>
- If you consider these deletions unreasonable or risky (test code may have been mistakenly deleted), answer: <!!!NO!!!>

Please answer strictly in the protocol format and do not add anything else.
"""

        PrettyOutput.auto_print(
            f"🤔 {log_prefix}[test-detection] Asking the LLM to judge whether the test code deletion is reasonable..."
        )
        response = agent.model.chat_until_success(prompt)
        response_str = str(response or "")

        # Parse the answer using the fixed protocol markers
        if "<!!!NO!!!>" in response_str:
            PrettyOutput.auto_print("❌ LLM confirmed: the test code deletion is unreasonable and a rollback is needed")
            return True  # a rollback is needed
        elif "<!!!YES!!!>" in response_str:
            PrettyOutput.auto_print("✅ LLM confirmed: the test code deletion is reasonable")
            return False  # no rollback needed
        else:
            # If no protocol marker is found, assume there is a problem by default (conservative strategy)
            PrettyOutput.auto_print(
                f"⚠️ No protocol marker found; assuming there is a problem by default. Response content: {response_str[:200]}"
            )
            return True  # conservative strategy: roll back by default
    except Exception as e:
        # If the query fails, assume there is a problem by default (conservative strategy)
        PrettyOutput.auto_print(f"⚠️ Failed to query the LLM: {str(e)}; assuming there is a problem by default")
        return True  # conservative strategy: roll back by default


def check_and_handle_test_deletion(
    before_commit: Optional[str],
    agent: Any,
    reset_to_commit_fn: Callable[[str], bool],
    log_prefix: str = "[c2rust]",
) -> bool:
    """
    Detect and handle test code deletion.

    Parameters:
        before_commit: the commit hash before the agent ran
        agent: the code generation or fix agent instance; its model is used for the query
        reset_to_commit_fn: the function that rolls back to the specified commit; it takes a commit hash as an argument and returns whether it succeeded
        log_prefix: log prefix (such as "[c2rust-transpiler]" or "[c2rust-optimizer]")

    Returns:
        bool: returns True if a problem was detected and a rollback was performed; otherwise False
    """
    if not before_commit:
        # No commit was recorded; a rollback is not possible
        return False

    detection_result = detect_test_deletion(log_prefix)
    if not detection_result:
        # No deletion detected
        return False

    PrettyOutput.auto_print(
        f"⚠️ {log_prefix}[test-detection] Potentially mistaken deletion of test code markers detected"
    )

    # Ask the LLM (using the passed-in agent's model)
    need_reset = ask_llm_about_test_deletion(detection_result, agent, log_prefix)

    if need_reset:
        PrettyOutput.auto_print(
            f"❌ {log_prefix}[test-detection] LLM confirmed the deletion is unreasonable; rolling back to commit: {before_commit}"
        )
        if reset_to_commit_fn(before_commit):
            PrettyOutput.auto_print(
                f"✅ {log_prefix}[test-detection] Rolled back to the previous commit"
            )
            return True
        else:
            PrettyOutput.auto_print(f"❌ {log_prefix}[test-detection] Rollback failed")
            return False

    return False


def extract_files_from_git_diff(git_diff: str) -> List[str]:
    """
    Extract the list of all modified files from a git diff string.

    Parameters:
        git_diff: git diff content

    Returns:
        List[str]: the list of modified file paths (deduplicated)
    """
    if not git_diff or not git_diff.strip():
        return []

    files = set()
    # Match the "diff --git a/path b/path" format
    # Standard git diff format: diff --git a/path b/path
    pattern = r"^diff --git a/([^\s]+) b/([^\s]+)$"
    for line in git_diff.split("\n"):
        match = re.match(pattern, line)
        if match:
            # Usually a/path and b/path are the same, but they may differ when handling renames
            file_a = match.group(1)
            file_b = match.group(2)
            # Prefer the b path (the new path); if it differs, add both
            files.add(file_b)
            if file_a != file_b:
                files.add(file_a)

    return sorted(list(files))


def get_modified_files_from_git(
    base_commit: Optional[str], crate_dir: Optional[Path]
) -> List[str]:
    """
    Use the git command to get the list of modified files.

    Parameters:
        base_commit: the base commit (if None, compare against HEAD)
        crate_dir: the crate root directory (if None, use the current directory)

    Returns:
        List[str]: the list of modified file paths
    """
    if not crate_dir:
        return []

    try:
        # Build the git diff command
        if base_commit:
            cmd = ["git", "diff", "--name-only", base_commit]
        else:
            cmd = ["git", "diff", "--name-only", "HEAD"]

        result = subprocess.run(
            cmd,
            cwd=crate_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
            return sorted(files)
        else:
            # If the command fails, return an empty list
            return []
    except Exception:
        # If any exception occurs, return an empty list
        return []


def truncate_git_diff_with_context_limit(
    git_diff: str,
    agent: Optional[Any] = None,
    token_ratio: float = 0.3,
    base_commit: Optional[str] = None,
    crate_dir: Optional[Path] = None,
) -> str:
    """
    Limit the length of the git diff to avoid an oversized context.

    Parameters:
        git_diff: the original git diff content
        agent: optional agent instance used to get the remaining token count (more accurate, accounting for dialogue history)
        llm_group: optional LLM group name used to get the input window limit (used when the agent is unavailable)
        token_ratio: the token usage ratio (default 0.3, i.e. 30%)
        base_commit: optional base commit; if provided, use the git command to get the file list
        crate_dir: optional crate root directory; if provided, use the git command to get the file list

    Returns:
        str: the length-limited git diff (if it exceeds the limit, truncate it and add a hint and the file list)
    """
    if not git_diff or not git_diff.strip():
        return git_diff

    max_diff_chars = None

    # Prefer using the agent to get the remaining tokens (more accurate, includes dialogue history)
    if agent:
        try:
            remaining_tokens = agent.get_remaining_token_count()
            if remaining_tokens > 0:
                # Use 2/3 of the remaining tokens or the minimum of 64k, then convert to a character count
                max_diff_chars = int(
                    calculate_token_limit(remaining_tokens) * token_ratio * 4
                )
                if max_diff_chars <= 0:
                    max_diff_chars = None
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.utils",
                function="truncate_git_diff_with_context_limit",
            )
            pass

    # Fallback: convert the specified ratio of the input window to a character count
    if max_diff_chars is None:
        try:
            max_input_tokens = get_max_input_token_count()
            max_diff_chars = int(max_input_tokens * token_ratio * 4)
        except Exception:
            # If retrieval fails, use the default value (about 10000 characters)
            max_diff_chars = 10000

    # Apply the length limit
    if len(git_diff) > max_diff_chars:
        # Prefer using the git command to get the file list (more reliable)
        if base_commit is not None and crate_dir:
            modified_files = get_modified_files_from_git(base_commit, crate_dir)
        else:
            # Fall back to extracting from the diff content
            modified_files = extract_files_from_git_diff(git_diff)

        truncated_diff = git_diff[:max_diff_chars] + "\n... (diff content too long, truncated)"

        # If there are modified files, add the file list
        if modified_files:
            truncated_diff += "\n\n**List of modified files ({} files in total):**\n".format(
                len(modified_files)
            )
            for file_path in modified_files:
                truncated_diff += f"  - {file_path}\n"

        return truncated_diff

    return git_diff
