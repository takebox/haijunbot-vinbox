# -*- coding: utf-8 -*-
"""
HaijunBot Security Analysis Suite -- Workflow (includes a reproducible direct scan baseline)

Goal:
- Identify security issues in the specified modules (memory management, buffer operations, error handling, etc.), with a target detection rate of >= 60%.
- Provide a "reproducible, offline" direct scan baseline (direct scan) without relying on external services.
- The current approach uses "first direct-scan to split subtasks, then a single Agent analyzes each one"; the interfaces are retained for future switching.

This module provides:
- direct_scan(entry_path, languages=None, exclude_dirs=None) -> Dict: pure Python + regex/command-line assisted scanning, producing structured results
- format_markdown_report(result_json: Dict) -> str: converts the structured result into a readable Markdown report

- run_with_agent(entry_path, languages=None) -> str: uses the single-Agent per-subtask analysis mode (reusing the implementation in haijunbot.haijunbot_sec.__init__)
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.input import get_single_line_input
from haijunbot.haijunbot_sec.checkers import analyze_c_files
from haijunbot.haijunbot_sec.checkers import analyze_rust_files
from haijunbot.haijunbot_sec.types import Issue
from haijunbot.haijunbot_sec.project_database import ProjectDatabase

# ---------------------------
# Data structures
# ---------------------------

# Issue dataclass is provided by haijunbot.haijunbot_sec.types to avoid circular imports


# ---------------------------
# Utility functions
# ---------------------------


def _iter_source_files(
    entry_path: str,
    languages: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
) -> Iterable[Path]:
    """
    Recursively enumerate source files, supporting filtering by extension and directory exclusion.
    Default language extensions: c, cpp, h, hpp, rs
    """
    entry = Path(entry_path)
    if not entry.exists():
        return

    exts = set((languages or ["c", "cpp", "h", "hpp", "rs"]))
    excludes = set(
        exclude_dirs
        or [
            ".git",
            "build",
            "out",
            "target",
            "dist",
            "bin",
            "obj",
            "third_party",
            "vendor",
            "deps",
            "dependencies",
            "libs",
            "libraries",
            "external",
            "node_modules",
            "test",
            "tests",
            "__tests__",
            "spec",
            "testsuite",
            "testdata",
            "benchmark",
            "benchmarks",
            "perf",
            "performance",
            "bench",
            "benches",
            "profiling",
            "profiler",
            "example",
            "examples",
            "tmp",
            "temp",
            "cache",
            ".cache",
            "docs",
            "doc",
            "documentation",
            "generated",
            "gen",
            "mocks",
            "fixtures",
            "samples",
            "sample",
            "playground",
            "sandbox",
        ]
    )

    for p in entry.rglob("*"):
        if not p.is_file():
            continue
        # Directory exclusion (only exclude directories inside the project entry directory)
        skip = False
        for parent in p.parents:
            # Only check directories inside the project entry directory; do not exclude external paths such as system temp directories
            if parent == entry:
                break  # Reached the project entry directory; stop checking
            if parent.name in excludes:
                skip = True
                break
        if skip:
            continue

        suf = p.suffix.lstrip(".").lower()
        if suf in exts:
            yield p.relative_to(entry)


# ---------------------------
# Summary and report
# ---------------------------


def direct_scan(
    entry_path: str,
    languages: Optional[List[str]] = None,
    exclude_dirs: Optional[List[str]] = None,
    build_database: bool = True,
) -> Dict[str, Any]:
    """
    Direct scan baseline: perform a heuristic scan on C/C++/Rust and output structured JSON.
    - Improvement: delegated to the modular checker (oh_sec.checkers), unifying rules and the confidence model.
    - New: builds a project-level database, supporting cross-file analysis.

    Args:
        entry_path: Project root directory path
        languages: Language list (default c, cpp, h, hpp, rs)
        exclude_dirs: Exclusion directory list
        build_database: Whether to build the database (default True)
    """
    base = Path(entry_path).resolve()
    # Compute the actual exclusion directory list to use
    default_excludes = [
        ".git",
        "build",
        "out",
        "target",
        "dist",
        "bin",
        "obj",
        "third_party",
        "vendor",
        "deps",
        "dependencies",
        "libs",
        "libraries",
        "external",
        "node_modules",
        "test",
        "tests",
        "__tests__",
        "spec",
        "testsuite",
        "testdata",
        "benchmark",
        "benchmarks",
        "perf",
        "performance",
        "bench",
        "benches",
        "profiling",
        "profiler",
        "example",
        "examples",
        "tmp",
        "temp",
        "cache",
        ".cache",
        "docs",
        "doc",
        "documentation",
        "generated",
        "gen",
        "mocks",
        "fixtures",
        "samples",
        "sample",
        "playground",
        "sandbox",
    ]
    actual_excludes = exclude_dirs if exclude_dirs is not None else default_excludes

    # Check the exclusion directories that actually exist in the codebase
    excludes_set = set(actual_excludes)
    actual_excluded_dirs = []
    for item in base.rglob("*"):
        if item.is_dir() and item.name in excludes_set:
            rel_path = item.relative_to(base)
            if str(rel_path) not in actual_excluded_dirs:
                actual_excluded_dirs.append(str(rel_path))

    if actual_excluded_dirs:
        PrettyOutput.auto_print("[haijunbot-sec] Actually excluded directories:")
        for dir_path in sorted(actual_excluded_dirs):
            PrettyOutput.auto_print(f"  - {dir_path}")
    else:
        PrettyOutput.auto_print(
            f"[haijunbot-sec] No directories requiring exclusion were found (configured exclusion directories: {', '.join(sorted(actual_excludes))})"
        )

    # Collect all files (used to build the symbol table; directories are not excluded)
    all_source_files = list(
        _iter_source_files(entry_path, languages, exclude_dirs=None)
    )

    # Files scanned during the issue detection phase (with specified directories excluded)
    files = list(_iter_source_files(entry_path, languages, exclude_dirs))

    # Group by language
    c_like_exts = {".c", ".cpp", ".h", ".hpp"}
    rust_exts = {".rs"}
    c_files: List[Path] = [p for p in files if p.suffix.lower() in c_like_exts]
    r_files: List[Path] = [p for p in files if p.suffix.lower() in rust_exts]

    # Build the project-level database (supports incremental updates)
    database = None
    if build_database:
        try:
            PrettyOutput.auto_print("[haijunbot-sec] Starting to build the project-level database...")
            database = ProjectDatabase(str(base))

            # Prepare the file list (file_path, language) - use all files to build the symbol table
            all_files = []
            for p in all_source_files:
                if p.suffix.lower() in c_like_exts:
                    lang = "cpp" if p.suffix.lower() in {".cpp", ".hpp"} else "c"
                    all_files.append((str(base / p), lang))
                elif p.suffix.lower() in rust_exts:
                    all_files.append((str(base / p), "rust"))

            # Use the incremental update mechanism
            sync_result = database.sync_files(all_files)

            # Print the database statistics
            stats = database.get_statistics()
            PrettyOutput.auto_print(
                f"[haijunbot-sec] Database build completed: "
                f"{stats['files_count']} files, "
                f"{stats['symbols_count']} symbols, "
                f"{stats['call_relations_count']} call relations, "
                f"{stats['data_flow_nodes_count']} data flow nodes"
            )
            PrettyOutput.auto_print(
                f"[haijunbot-sec] Incremental update statistics: "
                f"updated {sync_result['updated_count']}, "
                f"skipped {sync_result['skipped_count']}, "
                f"deleted {sync_result['deleted_count']}"
            )
        except Exception as e:
            PrettyOutput.auto_print(f"[haijunbot-sec] Database build failed: {e}")
            database = None

    # Call the checkers (keep relative paths, resolved based on base_path)
    # Pass the database instance to support cross-file analysis
    issues_c = (
        analyze_c_files(str(base), [str(p) for p in c_files], database=database)
        if c_files
        else []
    )
    issues_r = (
        analyze_rust_files(str(base), [str(p) for p in r_files], database=database)
        if r_files
        else []
    )
    issues: List[Issue] = issues_c + issues_r

    summary: Dict[str, Any] = {
        "total": len(issues),
        "by_language": {"c/cpp": 0, "rust": 0},
        "by_category": {},
        "top_risk_files": [],
        "scanned_files": len(files),
        "scanned_root": str(base),
    }
    file_score: Dict[str, int] = {}
    # Safely update language/category counts with explicit typing
    lang_counts = summary["by_language"]
    cat_counts = summary["by_category"]
    for it in issues:
        lang_counts[it.language] = lang_counts.get(it.language, 0) + 1
        cat_counts[it.category] = cat_counts.get(it.category, 0) + 1
        file_score[it.file] = file_score.get(it.file, 0) + 1
    # Top risk files
    summary["top_risk_files"] = [
        f for f, _ in sorted(file_score.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    result = {
        "summary": summary,
        "issues": [asdict(i) for i in issues],
        "database_stats": database.get_statistics() if database else None,
    }
    return result


def format_markdown_report(result_json: Dict[str, Any]) -> str:
    """
    Convert the structured JSON into a readable Markdown report.
    """
    s = result_json.get("summary", {})
    issues: List[Dict[str, Any]] = result_json.get("issues", [])
    md: List[str] = []
    md.append("# HaijunBot Security Issue Analysis Report (Direct Scan Baseline)")
    md.append("")
    md.append(f"- Scanned root directory: {s.get('scanned_root', '')}")
    md.append(f"- Number of scanned files: {s.get('scanned_files', 0)}")
    md.append(f"- Total number of issues detected: {s.get('total', 0)}")
    md.append("")
    md.append("## Statistics Overview")
    by_lang = s.get("by_language", {})
    md.append(
        f"- By language: c/cpp={by_lang.get('c/cpp', 0)}, rust={by_lang.get('rust', 0)}"
    )
    md.append("- By category:")
    for k, v in s.get("by_category", {}).items():
        md.append(f"  - {k}: {v}")
    if s.get("top_risk_files"):
        md.append("- Top risk files:")
        for f in s["top_risk_files"]:
            md.append(f"  - {f}")
    md.append("")
    md.append("## Detailed Issues")
    for i, it in enumerate(issues, start=1):
        md.append(
            f"### [{i}] {it.get('file')}:{it.get('line')} ({it.get('language')}, {it.get('category')})"
        )
        md.append(f"- Pattern: {it.get('pattern')}")
        md.append(f"- Evidence: `{it.get('evidence')}`")
        md.append(f"- Description: {it.get('description')}")
        md.append(f"- Suggestion: {it.get('suggestion')}")
        md.append(f"- Confidence: {it.get('confidence')}, Severity: {it.get('severity')}")
        md.append("")
    return "\n".join(md)


def run_with_agent(
    entry_path: str,
    languages: Optional[List[str]] = None,
    report_file: Optional[str] = None,
    cluster_limit: int = 50,
    exclude_dirs: Optional[List[str]] = None,
    enable_verification: bool = True,
    force_save_memory: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """
    Run using the single-Agent per-subtask analysis mode (consistent with haijunbot.haijunbot_sec.__init__).
    - First perform a local direct scan to generate candidate issues
    - Create an ordinary Agent task for each candidate to perform analysis and verification
    - Aggregate into the final report (JSON + Markdown) and return it

    Others:
    - report_file: JSONL report file path (optional, passed through)
    - cluster_limit: Maximum number of warnings processed per batch during clustering (default 50); when a single file has too many warnings, clustering is done in batches
    - exclude_dirs: List of directories to exclude (optional); by default it already includes build artifacts (build, out, target, dist, bin, obj), dependency directories (third_party, vendor, deps, dependencies, libs, libraries, external, node_modules), test directories (test, tests, __tests__, spec, testsuite, testdata), benchmark directories (benchmark, benchmarks, perf, performance, bench, benches, profiling, profiler), example directories (example, examples), temporary/cache (tmp, temp, cache, .cache), documentation (docs, doc, documentation), generated code (generated, gen), and others (mocks, fixtures, samples, sample, playground, sandbox)
    - enable_verification: Whether to enable secondary verification (default True); when disabled, issues confirmed by the analysis Agent are written directly to the report
    """
    from haijunbot.haijunbot_sec import run_security_analysis  # Lazy import, to avoid circular imports

    return run_security_analysis(
        entry_path,
        languages=languages,
        report_file=report_file,
        cluster_limit=cluster_limit,
        exclude_dirs=exclude_dirs,
        enable_verification=enable_verification,
        force_save_memory=force_save_memory,
        output_file=output_file,
    )


# ---------------------------
# External format analysis support
# ---------------------------


def _validate_format(data: Any) -> bool:
    """
    Validate whether external data conforms to the standard Issue format.

    Standard format:
    {
        "issues": [
            {
                "language": "c",
                "category": "memory",
                "pattern": "strcpy",
                "file": "src/main.c",
                "line": 42,
                "evidence": "strcpy(dest, src)",
                "description": "Unsafe string copy",
                "suggestion": "Use strncpy instead",
                "confidence": 0.8,
                "severity": "high"
            }
        ]
    }

    Or it may directly be an array: [Issue, ...]
    """
    if isinstance(data, list):
        # Directly in array format
        if not data:
            return False
        item = data[0]
        return isinstance(item, dict) and all(
            k in item
            for k in [
                "language",
                "category",
                "pattern",
                "file",
                "line",
                "evidence",
                "description",
                "suggestion",
                "confidence",
            ]
        )
    elif isinstance(data, dict):
        # Object format; check whether it has an "issues" field
        if "issues" not in data:
            return False
        issues = data["issues"]
        if not isinstance(issues, list) or not issues:
            return False
        item = issues[0]
        return isinstance(item, dict) and all(
            k in item
            for k in [
                "language",
                "category",
                "pattern",
                "file",
                "line",
                "evidence",
                "description",
                "suggestion",
                "confidence",
            ]
        )
    return False


def _create_conversion_agent(
    input_file: str,
    output_file: str,
) -> Any:
    """
    Create a conversion Agent that learns the external file format and generates a conversion script.

    Parameters:
    - input_file: External JSON file path
    - output_file: Output standard-format JSON file path

    Returns:
    - The converted standard-format data (dict)

    Exceptions:
    - Raises RuntimeError if the conversion fails
    """
    import json
    import tempfile

    from haijunbot.haijunbot_agent import Agent
    from haijunbot.haijunbot_utils.output import PrettyOutput

    # Read the external file sample
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"The input file does not exist: {input_file}")

    with input_path.open("r", encoding="utf-8") as f:
        external_data = json.load(f)

    # Build the conversion prompt
    conversion_prompt = f"""# Task: format conversion script generation

## Goal
You need to analyze the JSON format of the external scanning tool and write a Python script to convert it into the standard security issue format.

## External data sample
```json
{json.dumps(external_data, indent=2, ensure_ascii=False)[:5000]}
```

## Standard format
```json
{{
    "issues": [
        {{
            "language": "c",
            "category": "memory",
            "pattern": "strcpy",
            "file": "src/main.c",
            "line": 42,
            "evidence": "strcpy(dest, src)",
            "description": "Unsafe string copy",
            "suggestion": "Use strncpy instead",
            "confidence": 0.8,
            "severity": "high"
        }}
    ]
}}
```

## Field mapping description
- language: programming language (c/cpp/rust, etc.)
- category: issue category (memory/buffer/error_handling, etc.)
- pattern: detection pattern (function name, API call, etc.)
- file: source code file path
- line: code line number (integer)
- evidence: issue evidence (code snippet)
- description: issue description
- suggestion: remediation suggestion
- confidence: confidence level (a float from 0 to 1)
- severity: severity level (low/medium/high/critical, optional, default medium)

## Requirements
1. Write a Python script that reads `{input_file}`, converts it to the standard format, and outputs to `{output_file}`
2. The script must use the json library to handle JSON files
3. If some fields are missing from the external data, use reasonable default values:
   - severity: "medium"
   - confidence: 0.5
   - language: infer from the file extension (.c/.h -> c, .cpp/.hpp -> cpp, .rs -> rust)
4. The script must have error handling (try-except)
5. Output the complete executable Python script code; do not include any explanatory text

## Output format
Output only the Python script code; do not include markdown markers or any other explanation.
"""

    PrettyOutput.auto_print("📝 [haijunbot-sec] Learning the external file format and generating a conversion script...")

    # Create the Agent
    agent = Agent(
        system_prompt="""You are a security scan format conversion expert.
Your task is to analyze the JSON format of the external scanning tool and generate a Python conversion script to convert it into the standard security issue format.
""",
        name="format_converter",
        description="Security scan format conversion expert",
        use_tools=["read_code", "execute_script"],
        quick_mode=True,
    )

    # Execute the conversion
    try:
        response = agent.run(conversion_prompt)

        # Extract the script code (remove any markdown markers)
        script = response.strip()
        if script.startswith("```python"):
            script = script[9:]
        if script.startswith("```"):
            script = script[3:]
        if script.endswith("```"):
            script = script[:-3]
        script = script.strip()

        # Save the conversion script to a temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            script_file = f.name
            f.write(script)

        PrettyOutput.auto_print(f"🔧 [haijunbot-sec] Conversion script generated: {script_file}")

        # Execute the conversion script
        import subprocess

        result = subprocess.run(
            ["python3", script_file],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up the temporary script file
        try:
            Path(script_file).unlink()
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.workflow", function="_create_conversion_agent"
            )
            pass

        if result.returncode != 0:
            raise RuntimeError(f"Failed to execute the conversion script: {result.stderr}")

        PrettyOutput.auto_print(f"✅ [haijunbot-sec] Format conversion succeeded: {output_file}")

        # Read the converted data
        output_path = Path(output_file)
        with output_path.open("r", encoding="utf-8") as f:
            converted_data = json.load(f)

        return converted_data

    except Exception as e:
        raise RuntimeError(f"Format conversion failed: {e}") from e


def analyze_from_json(
    input_file: str,
    cluster_limit: int = 50,
    enable_verification: bool = True,
    force_save_memory: bool = False,
    output_file: Optional[str] = None,
) -> str:
    """
    Analyze security issues from an external JSON file.

    Supports two modes:
    1. Standard format: analyze directly
    2. Non-standard format: automatically create an Agent to learn the format and convert it

    Parameters:
    - input_file: External JSON file path
    - cluster_limit: Maximum number of warnings processed per batch during clustering (default 50)
    - enable_verification: Whether to enable secondary verification (default True)
    - force_save_memory: Whether to force memory saving (default False)
    - output_file: Output report file path (optional)
    - max_retries: Maximum number of retries for format conversion (default 3)

    Returns:
    - The final report (string)

    Exceptions:
    - Raises RuntimeError when the conversion fails more than the maximum number of retries
    """
    import json
    import tempfile

    from haijunbot.haijunbot_utils.output import PrettyOutput

    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"The input file does not exist: {input_file}")

    # Read the external data
    with input_path.open("r", encoding="utf-8") as f:
        external_data = json.load(f)

    # Check the format
    if _validate_format(external_data):
        PrettyOutput.auto_print("✅ [haijunbot-sec] Standard format detected, analyzing directly")
        candidates = (
            external_data
            if isinstance(external_data, list)
            else external_data["issues"]
        )
    else:
        PrettyOutput.auto_print("⚠️  [haijunbot-sec] Non-standard format detected, starting smart conversion")

        # Attempt the format conversion (retry forever until the user cancels)
        retries = 0
        converted_data = None

        while True:
            try:
                # Create a temporary output file
                temp_output = ""
                with tempfile.NamedTemporaryFile(  # type: ignore[assignment]
                    mode="w", suffix=".json", delete=False, encoding="utf-8"
                ) as f:
                    temp_output = f.name

                # Execute the conversion
                converted_data = _create_conversion_agent(str(input_path), temp_output)

                # Validate the conversion result
                if not _validate_format(converted_data):
                    raise RuntimeError("The converted format still does not conform to the standard")

                # Extract the candidates list
                if isinstance(converted_data, list):
                    candidates = converted_data
                else:
                    candidates = converted_data.get("issues", [])

                # Save the converted file for later use
                converted_output = (
                    input_path.parent / f"{input_path.stem}_converted.json"
                )
                with Path(converted_output).open("w", encoding="utf-8") as f:
                    json.dump(converted_data, f, indent=2, ensure_ascii=False)
                PrettyOutput.auto_print(
                    f"💾 [haijunbot-sec] Conversion result saved: {converted_output}"
                )

                break

            except Exception as e:
                retries += 1
                PrettyOutput.auto_print(
                    f"❌ [haijunbot-sec] Format conversion failed (attempt {retries}): {e}"
                )

                # Ask the user whether to retry
                PrettyOutput.auto_print("🤔 [haijunbot-sec] Format conversion failed; do you want to retry?")
                user_input = get_single_line_input(
                    "Enter 'y' to retry, or any other key to cancel: "
                )

                if user_input.lower() != "y":
                    PrettyOutput.auto_print("❌ [haijunbot-sec] User cancelled the operation")
                    raise RuntimeError("User cancelled the format conversion") from e

                PrettyOutput.auto_print("🔄 [haijunbot-sec] Retrying...")

    # Import the necessary modules
    from haijunbot.haijunbot_sec.utils import prepare_candidates as _prepare_candidates
    from haijunbot.haijunbot_sec.clustering import (  # type: ignore[attr-defined]
        process_clustering_phase as _process_clustering_phase,
    )
    from haijunbot.haijunbot_sec.verification import (
        process_verification_phase as _process_verification_phase,
    )
    from haijunbot.haijunbot_sec.file_manager import save_candidates
    from haijunbot.haijunbot_sec.report import build_json_and_markdown

    # Create a temporary analysis directory
    with tempfile.TemporaryDirectory() as temp_dir:
        sec_dir = Path(temp_dir)

        # Save the candidates to candidates.jsonl
        compact_candidates = _prepare_candidates(candidates)
        save_candidates(sec_dir, compact_candidates)

        PrettyOutput.auto_print(
            f"📊 [haijunbot-sec] Loaded {len(compact_candidates)} security issues"
        )

        # Create a status manager (empty implementation)
        class DummyStatusManager:
            def update_clustering(self, **kwargs: Any) -> None:
                pass

            def update_verification(self, **kwargs: Any) -> None:
                pass

        status_mgr = DummyStatusManager()

        # Progress callback (empty implementation)
        def _progress_append(event: Any) -> None:
            pass

        # Report writer function
        def _append_report(record: Any) -> None:
            pass

        # Clustering phase
        cluster_batches, invalid_clusters = _process_clustering_phase(
            compact_candidates,
            ".",  # entry_path (may not be a real path)
            [],  # languages
            cluster_limit,
            sec_dir,
            status_mgr,
            _progress_append,
            force_save_memory=force_save_memory,
        )

        # Verification phase
        all_issues = _process_verification_phase(
            cluster_batches,
            ".",
            [],
            sec_dir,
            status_mgr,
            _progress_append,
            _append_report,
            enable_verification=enable_verification,
            force_save_memory=force_save_memory,
        )

        # Generate the final report
        result = build_json_and_markdown(all_issues, str(sec_dir))  # ty: ignore[invalid-argument-type]

        # Save to the output file (if specified)
        if output_file:
            output_path = Path(output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as f:
                f.write(result)
            PrettyOutput.auto_print(f"📄 [haijunbot-sec] Report saved: {output_file}")

        return result


__all__ = [
    "Issue",
    "direct_scan",
    "format_markdown_report",
    "run_with_agent",
    "analyze_from_json",
]