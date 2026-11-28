# -*- coding: utf-8 -*-
"""
HaijunBot Security Evolution Suite - command-line entry point (Typer version)

Usage examples:
- Agent mode (single agent, analyzes each subtask individually)
  python -m haijunbot.haijunbot_sec.eli agent --path ./target_project
  python -m haijunbot.haijunbot_sec.eli agent  # analyzes the current directory by default

Optional arguments:

- --path, -p: root directory to analyze (defaults to the current directory)
- --output, -o: final report output path (defaults to ./report.md). If the suffix is .csv, the output is in CSV format; otherwise it is in Markdown format
"""

from __future__ import annotations

from haijunbot.haijunbot_utils.exception_utils import save_exception
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import typer

from haijunbot.haijunbot_sec.report import aggregate_issues
from haijunbot.haijunbot_sec.report import format_csv_report
from haijunbot.haijunbot_utils.output import PrettyOutput

# removed: set_config import (to avoid globally overriding the model group configuration)
from haijunbot.haijunbot_sec.workflow import direct_scan
from haijunbot.haijunbot_sec.workflow import (
    format_markdown_report as format_markdown_report_workflow,
)
from haijunbot.haijunbot_sec.workflow import run_with_agent
from haijunbot.haijunbot_utils.utils import init_env


# ---------------------------
# Constant definitions
# ---------------------------

HSEC_DIRNAME = "sec"
CONFIG_JSON = "config.json"


# ---------------------------
# Config file management
# ---------------------------


def _get_config_path() -> Path:
    """Get the config file path"""
    return Path(".") / ".haijunbot" / HSEC_DIRNAME / CONFIG_JSON


def _load_config() -> Dict[str, Any]:
    """
    Load the configuration from the config file.
    Returns a dictionary containing all config items, or the default config if the file does not exist or cannot be read.
    """
    import json

    config_path = _get_config_path()
    default_config = {
        "target": ".",
        "exclude_dirs": [
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
        ],
        "output": {"format": "markdown", "file": "report.md"},
        "analysis": {
            "cluster_limit": 50,
            "enable_verification": True,
            "force_save_memory": False,
        },
        "runtime": {"llm_group": None},
    }

    if not config_path.exists():
        return default_config

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                return default_config
            # Merge the default config to ensure all required keys exist
            return {
                "target": config.get("target", default_config["target"]),
                "languages": config.get("languages", default_config["languages"]),
                "exclude_dirs": config.get(
                    "exclude_dirs", default_config["exclude_dirs"]
                ),
                "output": config.get("output", default_config["output"]),
                "analysis": config.get("analysis", default_config["analysis"]),
                "runtime": config.get("runtime", default_config["runtime"]),
            }
    except Exception:
        return default_config


def _save_config(config: Dict[str, Any]) -> None:
    """Save the configuration to the file"""
    import json

    config_path = _get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [hsec-config] Failed to save config: {e}")
        raise


def _filter_result_by_file(result: Dict[str, Any], target_file: str) -> Dict[str, Any]:
    """Filter the scan results to keep only issues from the specified file"""
    target_file_normalized = str(Path(target_file).resolve())

    # Filter issues
    issues = result.get("issues", [])
    filtered_issues = [
        issue
        for issue in issues
        if str(Path(issue.get("file", "")).resolve()) == target_file_normalized
    ]

    # Update statistics
    result["issues"] = filtered_issues
    result["summary"]["total"] = len(filtered_issues)

    # Update top_risk_files (if present)
    if filtered_issues:
        result["summary"]["top_risk_files"] = [target_file_normalized]
    else:
        result["summary"]["top_risk_files"] = []

    return result


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="HaijunBot Security Evolution Suite (command-line tool)",
)


@app.command("config")
def config(
    target: Optional[str] = typer.Option(
        None, "--target", help="Scan target (file path or directory path)"
    ),
    languages: Optional[str] = typer.Option(
        None, "--languages", help="Language filter (comma-separated, e.g. c,cpp,rust)"
    ),
    exclude_dirs: Optional[str] = typer.Option(
        None, "--exclude-dirs", help="Exclude directories (comma-separated)"
    ),
    output_format: Optional[str] = typer.Option(
        None, "--output-format", help="Output format (csv/markdown)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output-file", help="Output file path"
    ),
    cluster_limit: Optional[int] = typer.Option(
        None, "--cluster-limit", help="Clustering limit (max warnings processed per batch)"
    ),
    enable_verification: Optional[bool] = typer.Option(
        None,
        "--enable-verification/--no-verification",
        help="Enable secondary verification",
    ),
    force_save_memory: Optional[bool] = typer.Option(
        None,
        "--force-save-memory/--no-force-save-memory",
        help="Force the use of memory",
    ),
    llm_group: Optional[str] = typer.Option(None, "--llm-group", help="Model group"),
    show: bool = typer.Option(False, "--show", help="Show the current config"),
    clear: bool = typer.Option(False, "--clear", help="Clear the config"),
) -> None:
    """
    Manage the security scan config file (.haijunbot/sec/config.json).

    Can set the scan target (file or directory), language filter, excluded directories, output format, analysis parameters, etc.
    These settings are automatically read and used by the scan command.

    Examples:
      # Set the scan target to the current directory
      hsec config --target .

      # Set the scan target to a specific file
      hsec config --target ./src/main.c

      # Set the language filter and output format
      hsec config --languages c,cpp,rust --output-format csv

      # Set the analysis parameters
      hsec config --cluster-limit 30 --enable-verification

      # View the current config
      hsec config --show

      # Clear the config
      hsec config --clear
    """
    # Read the existing config
    current_config = _load_config()

    # If just viewing the config
    if show:
        import json

        PrettyOutput.auto_print(f"📋 [hsec-config] Current config file: {_get_config_path()}")
        PrettyOutput.auto_print(
            json.dumps(current_config, ensure_ascii=False, indent=2)
        )
        return

    # If clearing the config
    if clear:
        import json

        default_config = {
            "target": ".",
            "languages": ["c", "cpp", "h", "hpp", "rs"],
            "exclude_dirs": [],
            "output": {"format": "markdown", "file": "report.md"},
            "analysis": {
                "cluster_limit": 50,
                "enable_verification": True,
                "force_save_memory": False,
            },
            "runtime": {"llm_group": None},
        }
        _save_config(default_config)
        PrettyOutput.auto_print(f"✅ [hsec-config] Config cleared: {_get_config_path()}")
        PrettyOutput.auto_print(
            json.dumps(default_config, ensure_ascii=False, indent=2)
        )
        return

    # Update the config
    updated = False

    # Update the scan target
    if target is not None:
        current_config["target"] = target
        updated = True
        PrettyOutput.auto_print(f"✅ [hsec-config] Scan target set: {target}")

    # Update the language filter
    if languages is not None:
        lang_list = [s.strip() for s in languages.split(",") if s.strip()]
        if lang_list:
            current_config["languages"] = lang_list
            updated = True
            PrettyOutput.auto_print(
                f"✅ [hsec-config] Language filter set: {', '.join(lang_list)}"
            )

    # Update the excluded directories
    if exclude_dirs is not None:
        exclude_list = [s.strip() for s in exclude_dirs.split(",") if s.strip()]
        if exclude_list:
            current_config["exclude_dirs"] = exclude_list
            updated = True
            PrettyOutput.auto_print(
                f"✅ [hsec-config] Excluded directories set: {', '.join(exclude_list)}"
            )

    # Update the output format
    if output_format is not None:
        if output_format not in ["csv", "markdown"]:
            PrettyOutput.auto_print(
                f"❌ [hsec-config] Invalid output-format: {output_format}, must be one of csv/markdown"
            )
            raise typer.Exit(code=1)
        current_config["output"]["format"] = output_format
        updated = True
        PrettyOutput.auto_print(f"✅ [hsec-config] Output format set: {output_format}")

    if output_file is not None:
        current_config["output"]["file"] = output_file
        updated = True
        PrettyOutput.auto_print(f"✅ [hsec-config] Output file set: {output_file}")

    # Update the analysis parameters
    if cluster_limit is not None:
        current_config["analysis"]["cluster_limit"] = cluster_limit
        updated = True
        PrettyOutput.auto_print(f"✅ [hsec-config] Clustering limit set: {cluster_limit}")

    if enable_verification is not None:
        current_config["analysis"]["enable_verification"] = enable_verification
        updated = True
        status = "enabled" if enable_verification else "disabled"
        PrettyOutput.auto_print(f"✅ [hsec-config] Secondary verification {status}")

    if force_save_memory is not None:
        current_config["analysis"]["force_save_memory"] = force_save_memory
        updated = True
        status = "enabled" if force_save_memory else "disabled"
        PrettyOutput.auto_print(f"✅ [hsec-config] Force memory {status}")

    # Update the runtime config
    if llm_group is not None:
        current_config["runtime"]["llm_group"] = llm_group
        updated = True
        PrettyOutput.auto_print(f"✅ [hsec-config] Model group set: {llm_group}")

    # If no arguments were provided, prompt the user
    if (
        not updated
        and target is None
        and languages is None
        and exclude_dirs is None
        and output_format is None
        and output_file is None
        and cluster_limit is None
        and enable_verification is None
        and force_save_memory is None
        and llm_group is None
    ):
        PrettyOutput.auto_print(
            "⚠️ [hsec-config] No arguments provided. Use --show to view the current config, or use --help to view help"
        )
        return

    # Save the config
    if updated:
        import json

        _save_config(current_config)
        PrettyOutput.auto_print(f"✅ [hsec-config] Config saved: {_get_config_path()}")
        PrettyOutput.auto_print(
            json.dumps(current_config, ensure_ascii=False, indent=2)
        )


@app.command("analyze", help="Analyze security issues from an external JSON file")
def analyze(
    input: str = typer.Argument(..., help="Path to the external JSON file (security issue list)"),
    output_format: Optional[str] = typer.Option(
        None, "--output-format", help="Output format (csv/markdown)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output-file", help="Output file path"
    ),
    cluster_limit: Optional[int] = typer.Option(
        None, "--cluster-limit", help="Clustering limit (max warnings processed per batch)"
    ),
    enable_verification: Optional[bool] = typer.Option(
        None,
        "--enable-verification/--no-verification",
        help="Enable secondary verification",
    ),
    force_save_memory: Optional[bool] = typer.Option(
        None,
        "--force-save-memory/--no-force-save-memory",
        help="Force the use of memory",
    ),
) -> None:
    """
    Analyze security issues from an external JSON file.

    Supports two modes:
    1. Standard format: analyzed directly
    2. Non-standard format: automatically creates an Agent learning format and converts it

    Standard format example:
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

    Or a direct array: [Issue, ...]

    Examples:
      # Analyze a standard-format file
      hsec analyze external_issues.json

      # Analyze a non-standard-format file (auto-converted)
      hsec analyze custom_tool_output.json

      # Specify the output format
      hsec analyze issues.json --output-format csv --output-file report.csv
    """
    # Initialize the environment
    try:
        init_env()
    except Exception as e:
        save_exception(e, module="haijunbot_sec.eli", function="analyze")
        pass

    from haijunbot.haijunbot_sec.workflow import analyze_from_json

    # Set default values
    if cluster_limit is None:
        cluster_limit = 50
    if enable_verification is None:
        enable_verification = True
    if force_save_memory is None:
        force_save_memory = False

    PrettyOutput.auto_print(f"📂 [hsec-analyze] Input file: {input}")

    try:
        # Execute the analysis
        result = analyze_from_json(
            input_file=input,
            cluster_limit=cluster_limit,
            enable_verification=enable_verification,
            force_save_memory=force_save_memory,
            output_file=output_file,
        )

        # Output the result
        if output_file:
            PrettyOutput.auto_print(
                f"✅ [hsec-analyze] Analysis complete, report saved to: {output_file}"
            )
        else:
            PrettyOutput.auto_print(result)

    except FileNotFoundError as e:
        PrettyOutput.auto_print(f"❌ [hsec-analyze] File not found: {e}")
        raise typer.Exit(code=1)
    except RuntimeError as e:
        PrettyOutput.auto_print(f"❌ [hsec-analyze] Analysis failed: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [hsec-analyze] Unknown error: {e}")
        raise typer.Exit(code=1)


def _parallel_analyze_file(args: Tuple[str, str, str]) -> List[Dict[str, Any]]:
    """Worker function for parallel analysis of a single file (used with ProcessPoolExecutor)"""
    file_path_str, target_path_str, db_path = args
    from pathlib import Path
    from haijunbot.haijunbot_sec.checkers.c_checker import analyze_c_cpp_file
    from haijunbot.haijunbot_sec.project_database import ProjectDatabase

    file_path = Path(file_path_str)
    target_path = Path(target_path_str)
    relpath = file_path.relative_to(target_path)

    # Each subprocess creates its own independent read-only database connection
    database = None
    if db_path:
        try:
            database = ProjectDatabase(
                str(target_path), db_path=db_path, in_memory=False
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_sec.eli", function="_parallel_analyze_file"
            )
            pass

    try:
        issues = analyze_c_cpp_file(target_path, relpath, database=database)
        return [
            {
                "language": issue.language,
                "category": issue.category,
                "pattern": issue.pattern,
                "file": str(file_path),
                "line": issue.line,
                "evidence": issue.evidence,
                "description": issue.description,
                "suggestion": issue.suggestion,
                "confidence": issue.confidence,
                "severity": issue.severity,
            }
            for issue in issues
        ]
    except Exception:
        return []


def _parallel_collect_file(args: Tuple[str, str]) -> Dict[str, Any]:
    """Worker function for parallel collection of a single file's symbol data"""
    file_path_str, lang = args
    from haijunbot.haijunbot_sec.project_database import ProjectDatabase
    from haijunbot.haijunbot_sec.data_collector import DataCollector

    # Each subprocess creates its own independent in-memory database
    database = ProjectDatabase("/tmp/parallel_collect", in_memory=True)
    database.begin_batch()
    collector = DataCollector(database)

    try:
        result = collector.analyze_file(file_path_str, lang)
        database.commit_batch()
        # Export the collected data (excluding the database object itself)
        return {
            "symbols": result.get("symbols", []),
            "call_relations": result.get("call_relations", []),
            "data_flow_nodes": result.get("data_flow_nodes", []),
            "pointer_states": result.get("pointer_states", []),
            "type_infos": result.get("type_infos", []),
        }
    except Exception:
        return {
            "symbols": [],
            "call_relations": [],
            "data_flow_nodes": [],
            "pointer_states": [],
            "type_infos": [],
        }


@app.command("heuristic", help="Heuristic scan (fast static analysis)")
def heuristic(
    target: Optional[str] = typer.Argument(
        None, help="Scan target (file or directory path, defaults to the value from the config file)"
    ),
    output_format: str = typer.Option(
        "json", "--format", "-f", help="Output format (json/markdown)"
    ),
    output_file: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output file path (defaults to printing to the terminal)"
    ),
    rules: Optional[str] = typer.Option(
        None,
        "--rules",
        "-r",
        help="Rule filter (comma-separated, e.g. unsafe_api,buffer_overflow)",
    ),
    workers: int = typer.Option(
        os.cpu_count() or 4, "--workers", "-w", help="Number of parallel worker processes (defaults to the CPU core count)"
    ),
) -> None:
    """
    Heuristic scan: fast static analysis that detects issues directly without the LLM.

    Features:
    - Fast: pure static analysis, no LLM calls required
    - Comprehensive: covers 38+ heuristic rules
    - Accurate: integrates taint analysis to reduce false positives

    Examples:
      # Scan a single file (JSON format)
      hsec heuristic ./src/main.c

      # Scan a directory (Markdown format)
      hsec heuristic ./src --format markdown

      # Scan and save to a file
      hsec heuristic ./src --output report.json

      # Specify a rule filter
      hsec heuristic ./src --rules unsafe_api,buffer_overflow
    """
    from pathlib import Path
    import json
    from haijunbot.haijunbot_sec.checkers.c_checker import analyze_c_cpp_file

    # If no target is specified, read it from the config file
    if target is None:
        config = _load_config()
        target = config.get("target", ".")
        PrettyOutput.auto_print(f"📋 [heuristic] Scan target read from config file: {target}")

    target_path = Path(target).resolve()

    # Collect all issues
    all_issues: List[Dict[str, Any]] = []

    # Determine whether the target is a file or a directory
    if target_path.is_file():
        # Scan a single file
        PrettyOutput.auto_print(f"📄 [heuristic] Scanning file: {target_path}")
        issues = analyze_c_cpp_file(target_path.parent, Path(target_path.name))
        for issue in issues:
            all_issues.append(
                {
                    "language": issue.language,
                    "category": issue.category,
                    "pattern": issue.pattern,
                    "file": str(Path(issue.file).resolve()),
                    "line": issue.line,
                    "evidence": issue.evidence,
                    "description": issue.description,
                    "suggestion": issue.suggestion,
                    "confidence": issue.confidence,
                    "severity": issue.severity,
                }
            )
    elif target_path.is_dir():
        # Scan a directory
        PrettyOutput.auto_print(f"📁 [heuristic] Scanning directory: {target_path}")

        # Supported file extensions
        extensions = {"c", "cpp", "cc", "cxx", "h", "hpp", "hxx", "c++", "h++"}

        # Collect all C/C++ files (to build the symbol table, without excluding any directory)
        all_files = []
        for ext in extensions:
            all_files.extend(target_path.rglob(f"*.{ext}"))

        # Exclude directory config (used for the issue detection phase)
        # Default excluded directories
        default_exclude_dirs = {
            ".git",
            "build",
            "out",
            "target",
            "dist",
            "bin",
            "obj",
            "third_party",
            "3rdparty",
            "vendor",
            "deps",
            "node_modules",
            "__tests__",
            "spec",
            "testdata",
        }
        # Read the excluded directories from the config file and merge them
        config = _load_config()
        config_exclude_dirs = set(config.get("exclude_dirs", []))
        exclude_dirs = default_exclude_dirs | config_exclude_dirs

        # Files scanned in the issue detection phase (excluding the configured directories)
        c_files = [
            f for f in all_files if not any(excl in f.parts for excl in exclude_dirs)
        ]

        PrettyOutput.auto_print(
            f"📊 [heuristic] Found {len(all_files)} C/C++ files (scanning {len(c_files)})"
        )

        # Use a rich progress bar to show the scan progress
        from rich.progress import (
            Progress,
            BarColumn,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )
        from rich.console import Console

        console = Console()

        # Phase 1+2: parallel collection of symbol data and call relations
        from haijunbot.haijunbot_sec.project_database import ProjectDatabase
        from haijunbot.haijunbot_sec.data_collector import DataCollector
        import sqlite3
        import tempfile

        database = ProjectDatabase(str(target_path), in_memory=True)
        database.begin_batch()
        collector = DataCollector(database)

        # Prepare the file argument list
        file_args = []
        for file_path in all_files:
            lang = (
                "cpp"
                if str(file_path).endswith(
                    (".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".c++", ".h++")
                )
                else "c"
            )
            file_args.append((str(file_path), lang))

        # Cumulative statistics
        total_symbols = 0
        total_calls = 0
        total_nodes = 0

        # Decide whether to use parallelism (serial is more efficient when there are fewer files than workers)
        use_parallel = len(all_files) > workers and workers > 1

        if use_parallel:
            # Parallel mode: use ProcessPoolExecutor
            actual_workers = min(workers, len(all_files))
            PrettyOutput.auto_print(
                f"⚡ [heuristic] Parallel mode: {actual_workers} worker processes"
            )

            with Progress(
                TextColumn("[bold cyan]Parallel data collection"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("{task.fields[filename]}"),
                TextColumn(
                    "[dim]Symbols:{task.fields[symbols]} Calls:{task.fields[calls]}"
                ),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "parallel_collect",
                    total=len(all_files),
                    filename="",
                    symbols=0,
                    calls=0,
                )

                with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                    futures = {
                        executor.submit(_parallel_collect_file, arg): arg[0]
                        for arg in file_args
                    }
                    for future in as_completed(futures):
                        file_path_str = futures[future]
                        try:
                            result = future.result()
                            # Merge into the main database
                            if result["symbols"]:
                                database.add_symbols_batch(result["symbols"])
                                total_symbols += len(result["symbols"])
                            if result["call_relations"]:
                                database.add_call_relations_batch(
                                    result["call_relations"]
                                )
                                total_calls += len(result["call_relations"])
                            if result["data_flow_nodes"]:
                                database.add_data_flow_nodes_batch(
                                    result["data_flow_nodes"]
                                )
                                total_nodes += len(result["data_flow_nodes"])
                            if result["pointer_states"]:
                                database.add_pointer_states_batch(
                                    result["pointer_states"]
                                )
                            if result["type_infos"]:
                                database.add_type_infos_batch(result["type_infos"])
                        except Exception as e:
                            save_exception(
                                e, module="haijunbot_sec.eli", function="heuristic"
                            )
                            pass
                        progress.update(
                            task,
                            filename=Path(file_path_str).name[:30],
                            symbols=total_symbols,
                            calls=total_calls,
                        )
                        progress.advance(task)
        else:
            # Serial mode: collect directly using the main process
            with Progress(
                TextColumn("[bold cyan]Collecting symbol definitions"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("{task.fields[filename]}"),
                TextColumn("[dim]Symbols:{task.fields[symbols]}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "symbols", total=len(all_files), filename="", symbols=0
                )
                for file_path in all_files:
                    relpath = file_path.relative_to(target_path)
                    progress.update(task, filename=str(relpath))
                    lang = (
                        "cpp"
                        if str(file_path).endswith(
                            (".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".c++", ".h++")
                        )
                        else "c"
                    )
                    try:
                        result = collector.analyze_file(str(file_path), lang)
                        total_symbols += len(result.get("symbols", []))
                        progress.update(task, symbols=total_symbols)
                    except Exception as e:
                        save_exception(e, module="haijunbot_sec.eli", function="heuristic")
                        pass
                    progress.advance(task)

            # Phase 2: analyze call relations (serial)
            with Progress(
                TextColumn("[bold cyan]Analyzing call relations"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("{task.fields[filename]}"),
                TextColumn("[dim]Calls:{task.fields[calls]} Nodes:{task.fields[nodes]}"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "calls", total=len(all_files), filename="", calls=0, nodes=0
                )
                for file_path in all_files:
                    relpath = file_path.relative_to(target_path)
                    progress.update(task, filename=str(relpath))
                    lang = (
                        "cpp"
                        if str(file_path).endswith(
                            (".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".c++", ".h++")
                        )
                        else "c"
                    )
                    try:
                        result = collector.analyze_file(str(file_path), lang)
                        total_calls += len(result.get("call_relations", []))
                        total_nodes += len(result.get("data_flow_nodes", []))
                        progress.update(task, calls=total_calls, nodes=total_nodes)
                    except Exception as e:
                        save_exception(e, module="haijunbot_sec.eli", function="heuristic")
                        pass
                    progress.advance(task)

        # Commit the batch operations
        database.commit_batch()

        PrettyOutput.auto_print(
            f"✅ [heuristic] Data collection complete: {total_symbols} symbols, {total_calls} calls, {total_nodes} data nodes"
        )

        # Phase 3: issue detection (parallel or serial)
        # Export the in-memory database to a temp file so subprocesses can read it
        db_temp_file = None
        if use_parallel and database._conn:
            # Export the in-memory database to a temp file
            db_temp_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
            db_temp_path = db_temp_file.name
            db_temp_file.close()
            # Export using the SQLite backup API
            dest_conn = sqlite3.connect(db_temp_path)
            database._conn.backup(dest_conn)
            dest_conn.close()
        else:
            db_temp_path = None

        try:
            if use_parallel and len(c_files) > workers:
                # Parallel issue detection
                analyze_args = [
                    (str(f), str(target_path), db_temp_path or "") for f in c_files
                ]

                with Progress(
                    TextColumn("[bold blue]Parallel issue detection"),
                    BarColumn(bar_width=40),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("{task.fields[filename]}"),
                    TextColumn("[dim]Issues:{task.fields[issues]}"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "parallel_scan", total=len(c_files), filename="", issues=0
                    )

                    with ProcessPoolExecutor(
                        max_workers=min(workers, len(c_files))
                    ) as executor:
                        futures = {
                            executor.submit(_parallel_analyze_file, arg): arg[0]
                            for arg in analyze_args
                        }
                        for future in as_completed(futures):
                            file_path_str = futures[future]
                            try:
                                issues = future.result()
                                all_issues.extend(issues)
                            except Exception as e:
                                save_exception(
                                    e, module="haijunbot_sec.eli", function="heuristic"
                                )
                                pass
                            progress.update(
                                task,
                                filename=Path(file_path_str).name[:30],
                                issues=len(all_issues),
                            )
                            progress.advance(task)
            else:
                # Serial issue detection
                with Progress(
                    TextColumn("[bold blue]Issue detection"),
                    BarColumn(bar_width=40),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    TextColumn("{task.fields[filename]}"),
                    TextColumn("[dim]Issues:{task.fields[issues]}"),
                    TimeElapsedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task(
                        "scan", total=len(c_files), filename="", issues=0
                    )
                    for file_path in c_files:
                        relpath = file_path.relative_to(target_path)
                        progress.update(task, filename=str(relpath))
                        issues = analyze_c_cpp_file(
                            target_path, relpath, database=database
                        )
                        for issue in issues:
                            all_issues.append(
                                {
                                    "language": issue.language,
                                    "category": issue.category,
                                    "pattern": issue.pattern,
                                    "file": str(file_path),
                                    "line": issue.line,
                                    "evidence": issue.evidence,
                                    "description": issue.description,
                                    "suggestion": issue.suggestion,
                                    "confidence": issue.confidence,
                                    "severity": issue.severity,
                                }
                            )
                        progress.update(task, issues=len(all_issues))
                        progress.advance(task)
        finally:
            # Clean up the temp database file
            if db_temp_file and db_temp_path and Path(db_temp_path).exists():
                Path(db_temp_path).unlink()

        PrettyOutput.auto_print(
            f"✅ [heuristic] Scan complete. Scanned {len(c_files)} files (symbol table includes {len(all_files)} files)"
        )
    else:
        PrettyOutput.auto_print(f"❌ [heuristic] Target does not exist: {target_path}")
        raise typer.Exit(code=1)

    # Rule filter
    if rules:
        rule_list = [r.strip() for r in rules.split(",") if r.strip()]
        all_issues = [issue for issue in all_issues if issue["pattern"] in rule_list]
        PrettyOutput.auto_print(f"🔍 [heuristic] After rule filtering: {len(all_issues)} issues")

    # Statistics
    stats = {
        "total": len(all_issues),
        "by_severity": {},
        "by_category": {},
        "by_pattern": {},
    }
    for issue in all_issues:
        severity = issue["severity"]
        category = issue["category"]
        pattern = issue["pattern"]
        stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
        stats["by_category"][category] = stats["by_category"].get(category, 0) + 1
        stats["by_pattern"][pattern] = stats["by_pattern"].get(pattern, 0) + 1

    # Output the result
    if output_format == "json":
        result = {
            "summary": stats,
            "issues": all_issues,
        }
        output_text = json.dumps(result, ensure_ascii=False, indent=2)
    else:  # markdown
        lines = ["# Heuristic scan report\n"]
        lines.append(f"**Scan target**: `{target_path}`\n")
        lines.append(f"**Total issues**: {stats['total']}\n")
        lines.append("\n## Statistics\n")
        lines.append("\n### By severity\n")
        for sev, count in sorted(stats["by_severity"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{sev}**: {count}")
        lines.append("\n### By category\n")
        for cat, count in sorted(stats["by_category"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{cat}**: {count}")
        lines.append("\n### By rule\n")
        for pattern, count in sorted(stats["by_pattern"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{pattern}**: {count}")
        lines.append("\n## Issue list\n")
        for i, issue in enumerate(all_issues, 1):
            lines.append(f"\n### {i}. {issue['pattern']}\n")
            lines.append(f"- **File**: `{issue['file']}:{issue['line']}`")
            lines.append(f"- **Severity**: {issue['severity']}")
            lines.append(f"- **Confidence**: {issue['confidence']:.2f}")
            lines.append(f"- **Description**: {issue['description']}")
            lines.append(f"- **Suggestion**: {issue['suggestion']}")
            lines.append(f"- **Evidence**: `{issue['evidence']}`")
        output_text = "\n".join(lines)

    # Output to a file or the terminal
    if output_file:
        Path(output_file).write_text(output_text, encoding="utf-8")
        PrettyOutput.auto_print(f"✅ [heuristic] Report saved to: {output_file}")
    else:
        PrettyOutput.auto_print(output_text)


@app.command("scan", help="Execute a security scan (reads from the config file)")
def scan() -> None:
    """
    Execute a security scan, reading all config from the config file (.haijunbot/sec/config.json).

    If the config file does not exist, a friendly message guides the user to use the config command.

    Supports scanning a specified file or directory:
    - File: scans the directory containing the file, then filters to keep only issues from that file
    - Directory: scans all files under the directory

    Examples:
      # First-time use: set the config first
      hsec config --target ./src

      # Execute the scan
      hsec scan

      # Scan a single file
      hsec config --target ./src/main.c
      hsec scan
    """
    # Initialize the environment
    try:
        init_env()
    except Exception:
        # If environment initialization fails, it should not block the basic ELI functions; continue
        pass

    # Load the config
    config = _load_config()
    config_path = _get_config_path()

    # Check whether the config file exists (using defaults means the file does not exist)
    if not config_path.exists():
        PrettyOutput.auto_print(f"❌ [hsec-scan] Config file not found: {config_path}")
        PrettyOutput.auto_print(
            "💡 [hsec-scan] Please set the scan config first with the 'hsec config' command"
        )
        PrettyOutput.auto_print(
            "💡 [hsec-scan] Example: hsec config --scope-type directory --target ./src"
        )
        raise typer.Exit(code=1)

    # Read the config parameters
    target = config.get("target", ".")
    languages = config.get("languages", None)
    exclude_dirs = config.get("exclude_dirs", None)
    output_config = config.get("output", {})
    output_format = output_config.get("format", "markdown")
    output_file = output_config.get("file", "report.md")
    analysis = config.get("analysis", {})
    cluster_limit = analysis.get("cluster_limit", 50)
    enable_verification = analysis.get("enable_verification", True)
    force_save_memory = analysis.get("force_save_memory", False)
    runtime = config.get("runtime", {})
    llm_group = runtime.get("llm_group", None)

    # Determine whether the target is a file or a directory
    target_path = Path(target)
    if target_path.exists() and target_path.is_file():
        # The target is a file: scan the directory containing the file, then filter
        scan_dir = str(target_path.parent)
        filter_file = str(target_path.resolve())
        PrettyOutput.auto_print(f"📄 [hsec-scan] Scanning file: {filter_file}")
    elif target_path.exists() and target_path.is_dir():
        # The target is a directory: scan the directory
        scan_dir = str(target_path)
        filter_file = None
        PrettyOutput.auto_print(f"📁 [hsec-scan] Scanning directory: {scan_dir}")
    else:
        # Default: scan the current directory
        scan_dir = "."
        filter_file = None
        PrettyOutput.auto_print(f"📁 [hsec-scan] Scanning directory: {scan_dir}")

    # Adjust the output_file suffix based on the output format
    if output_format == "csv" and not output_file.lower().endswith(".csv"):
        output_file = (
            output_file.rsplit(".", 1)[0] + ".csv"
            if "." in output_file
            else output_file + ".csv"
        )
    elif output_format == "markdown" and output_file.lower().endswith(".csv"):
        output_file = (
            output_file.rsplit(".", 1)[0] + ".md"
            if "." in output_file
            else output_file + ".md"
        )

    # Set the model group (if specified)
    if llm_group:
        from haijunbot.haijunbot_utils.config import set_llm_group

        set_llm_group(llm_group)

    # Execute the scan
    text: Optional[str] = None
    try:
        text = run_with_agent(
            scan_dir,
            languages=languages,
            cluster_limit=cluster_limit,
            enable_verification=enable_verification,
            force_save_memory=force_save_memory,
            exclude_dirs=exclude_dirs,
            output_file=output_file,
        )
    except Exception as e:
        try:
            PrettyOutput.auto_print(
                f"⚠️ [hsec-scan] Agent analysis failed, falling back to the direct scan baseline (fast): {e}"
            )
        except Exception as e:
            save_exception(e, module="haijunbot_sec.eli", function="scan")
            pass
        text = None

    if not text or not str(text).strip():
        try:
            PrettyOutput.auto_print(
                "⚠️ [hsec-scan] Agent produced no output. Falling back to the direct scan baseline (fast)."
            )
        except Exception as e:
            save_exception(e, module="haijunbot_sec.eli", function="scan")
            pass
        result = direct_scan(scan_dir, languages=languages, exclude_dirs=exclude_dirs)
        # If a file filter was specified, filter the results
        if filter_file:
            result = _filter_result_by_file(result, filter_file)
        # Select the format based on the output file suffix
        if output_file and output_file.lower().endswith(".csv"):
            # Use the function from report.py to format the CSV
            report_json = aggregate_issues(
                result.get("issues", []),
                scanned_root=result.get("summary", {}).get("scanned_root"),
                scanned_files=result.get("summary", {}).get("scanned_files"),
            )
            text = format_csv_report(report_json)
        else:
            # Use format_markdown_report from workflow.py (matches the direct_scan return structure)
            text = format_markdown_report_workflow(result)

    if output_file:
        try:
            md_text = text or ""
            try:
                lines = (text or "").splitlines()
                idx = -1
                for i, ln in enumerate(lines):
                    if ln.strip().startswith("# HaijunBot Security Issue Analysis Report (Direct Scan Baseline)"):
                        idx = i
                        break
                if idx >= 0:
                    md_text = "\n".join(lines[idx:])
            except Exception:
                md_text = text or ""
            p = Path(output_file)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(md_text, encoding="utf-8")
            try:
                PrettyOutput.auto_print(f"✅ [hsec-scan] Report written to: {p}")
            except Exception as e:
                save_exception(e, module="haijunbot_sec.eli", function="scan")
                pass
        except Exception as e:
            try:
                PrettyOutput.auto_print(f"❌ [hsec-scan] Failed to write report: {e}")
            except Exception as e:
                save_exception(e, module="haijunbot_sec.eli", function="scan")
                pass
    PrettyOutput.auto_print(text)


def main() -> int:
    app()
    return 0


if __name__ == "__main__":
    sys.exit(main())