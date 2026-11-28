# -*- coding: utf-8 -*-
"""
Standalone command-line entry point for C2Rust.

Provides a grouped ELI:
  - haijunbot-c2rust run: execute the full transpilation pipeline (scan -> lib-replace -> prepare -> transpile -> optimize), supporting resumable runs
  - haijunbot-c2rust config: manage the transpilation config file (root symbol list, disabled library list, additional notes, etc)

Implementation strategy:
- Use a Typer grouped structure to make it easier to add more subcommands later (such as analyze/export, etc).
- The run command supports resumable runs, automatically skipping completed stages based on the state file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List
from typing import Optional
from typing import cast

import typer
from haijunbot.haijunbot_utils.config import set_llm_group
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.library_replacer import (
    apply_library_replacement as _apply_library_replacement,
)
from haijunbot.haijunbot_c2rust.llm_module_agent import execute_llm_plan as _execute_llm_plan
from haijunbot.haijunbot_c2rust.scanner import run_scan as _run_scan
from haijunbot.haijunbot_c2rust.verify import run_verify as _run_verify
from haijunbot.haijunbot_utils.utils import init_env


def _check_optimize_completed(crate_dir: Path) -> bool:
    """
    Check whether optimization is truly complete.
    Need to check whether all necessary steps in optimize_progress.json are complete.
    Especially clippy_elimination: if there are warnings, it must be completed; if there are no warnings, it can be skipped.
    """
    import json

    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME

    progress_path = crate_dir / C2RUST_DIRNAME / "optimize_progress.json"
    if not progress_path.exists():
        # If there is no progress file, it means it has not started yet, so it is not considered complete
        return False

    try:
        with progress_path.open("r", encoding="utf-8") as f:
            progress = json.load(f)

        steps_completed = set(progress.get("steps_completed", []))

        # Check whether there are clippy warnings
        # Directly call the function in the optimizer module (although it is a private function, we need it for the check)
        import subprocess

        try:
            res = subprocess.run(
                ["cargo", "clippy", "--", "-W", "clippy::all"],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(crate_dir),
            )
            stderr_output = (res.stderr or "").strip()
            stdout_output = (res.stdout or "").strip()
            output = (
                (stderr_output + "\n" + stdout_output).strip()
                if (stderr_output and stdout_output)
                else (stderr_output or stdout_output or "").strip()
            )
            output_lower = output.lower()
            has_warnings = (
                "warning:" in output_lower
                or "warn(" in output_lower
                or ("clippy::" in output_lower and res.returncode != 0)
            )
        except Exception:
            # If the check fails, conservatively assume there are warnings (needs completion)
            has_warnings = True

        # If there are warnings, clippy_elimination must be in steps_completed
        if has_warnings:
            if "clippy_elimination" not in steps_completed:
                return False

        # Check other necessary steps (based on the enable_* options, but here we assume they are all enabled)
        # Note: here we only check clippy_elimination; other steps (unsafe_cleanup, visibility_opt, doc_opt)
        # may not be executed due to the enable_* options, so they are not required

        return True
    except Exception:
        # If reading fails, conservatively consider it incomplete
        return False


app = typer.Typer(help="C2Rust command-line tool")


# Explicitly define the root callback to ensure it is a command group rather than a single-function entry point
@app.callback()
def _root() -> None:
    """
    C2Rust command-line tool
    """
    # Set an environment variable to indicate that we are currently running in the c2rust environment
    os.environ["c2rust_enabled"] = "1"
    # Do nothing; it only serves as a placeholder for the command group so that 'scan' appears as a subcommand
    init_env("")
    pass


def _load_config() -> dict:
    """
    Load the configuration from the config file.
    Return a dictionary containing root_symbols, disabled_libraries, additional_notes, and enable_ffi_export_validation.
    """
    import json

    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
    from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON

    data_dir = Path(".") / C2RUST_DIRNAME
    config_path = data_dir / CONFIG_JSON
    default_config = {
        "root_symbols": [],
        "disabled_libraries": [],
        "additional_notes": "",
        "enable_ffi_export_validation": False,
    }

    if not config_path.exists():
        return default_config

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                return default_config
            # Ensure all required keys are present
            return {
                "root_symbols": config.get("root_symbols", []),
                "disabled_libraries": config.get("disabled_libraries", []),
                "additional_notes": config.get("additional_notes", ""),
                "enable_ffi_export_validation": config.get(
                    "enable_ffi_export_validation", False
                ),
            }
    except Exception:
        return default_config


def _get_run_state_path() -> Path:
    """Get the run state file path"""
    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
    from haijunbot.haijunbot_c2rust.constants import RUN_STATE_JSON

    data_dir = Path(".") / C2RUST_DIRNAME
    return data_dir / RUN_STATE_JSON


def _load_run_state() -> dict:
    """Load the run state file"""
    import json

    state_path = _get_run_state_path()
    default_state = {
        "scan": {"completed": False, "timestamp": None},
        "lib_replace": {"completed": False, "timestamp": None},
        "prepare": {"completed": False, "timestamp": None},
        "transpile": {"completed": False, "timestamp": None},
        "optimize": {"completed": False, "timestamp": None},
    }

    if not state_path.exists():
        return default_state

    try:
        with state_path.open("r", encoding="utf-8") as f:
            state = json.load(f)
            if not isinstance(state, dict):
                return default_state
            # Ensure all required stages are present
            for stage in ["scan", "lib_replace", "prepare", "transpile", "optimize"]:
                if stage not in state:
                    state[stage] = {"completed": False, "timestamp": None}
            return state
    except Exception:
        return default_state


def _save_run_state(stage: str, completed: bool = True) -> None:
    """Save the run state file"""
    import json
    import time

    state_path = _get_run_state_path()
    state = _load_run_state()

    state[stage] = {
        "completed": completed,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())
        if completed
        else None,
    }

    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with state_path.open("w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ [c2rust-run] Failed to save state file: {e}")


@app.command("config")
def config(
    files: Optional[List[Path]] = typer.Option(
        None,
        "--files",
        help="Header file (.h/.hh/.hpp/.hxx) or a function name list file (one function name per line; ignores blank lines and comments starting with #)",
    ),
    root_list_syms: Optional[str] = typer.Option(
        None, "--root-list-syms", help="Inline root symbol list (comma-separated)"
    ),
    disabled_libs: Optional[str] = typer.Option(
        None, "--disabled-libs", help="Disabled library list (comma-separated)"
    ),
    additional_notes: Optional[str] = typer.Option(
        None, "--additional-notes", help="Additional notes (appended to the hint of all agents)"
    ),
    enable_ffi_export_validation: Optional[bool] = typer.Option(
        None,
        "--enable-ffi-export-validation",
        "--disable-ffi-export-validation",
        help="Enable/disable FFI export validation (disabled by default)",
    ),
    show: bool = typer.Option(False, "--show", help="Show the current configuration content"),
    clear: bool = typer.Option(False, "--clear", help="Clear the configuration (reset to defaults)"),
) -> None:
    """
    Manage the transpilation config file (.haijunbot/c2rust/config.json).

    You can set the root symbol list (root_symbols), disabled library list (disabled_libraries), and additional notes (additional_notes).
    These configurations are automatically read and used by the transpile command.

    Example:
      # Automatically extract function names from a header file and set the root symbol list
      haijunbot-c2rust config --files bzlib.h

      # Extract function names from multiple header files
      haijunbot-c2rust config --files a.h b.hpp c.hxx

      # Set the root symbol list from a function name list file
      haijunbot-c2rust config --files roots.txt

      # Set the root symbol list from the command line
      haijunbot-c2rust config --root-list-syms "func1,func2,func3"

      # Set the disabled library list
      haijunbot-c2rust config --disabled-libs "libc,libm"

      # Set additional notes (appended to the hint of all agents)
      haijunbot-c2rust config --additional-notes "Note: all functions must handle error cases and avoid panics"

      # Set multiple parameters together as well
      haijunbot-c2rust config --files bzlib.h --disabled-libs "libc" --additional-notes "Special requirement notes"

      # View the current configuration
      haijunbot-c2rust config --show

      # Clear the configuration
      haijunbot-c2rust config --clear
    """
    import json

    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
    from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON

    data_dir = Path(".") / C2RUST_DIRNAME
    config_path = data_dir / CONFIG_JSON
    data_dir.mkdir(parents=True, exist_ok=True)

    # Read the existing configuration
    default_config = {
        "root_symbols": [],
        "disabled_libraries": [],
        "additional_notes": "",
        "enable_ffi_export_validation": False,
    }
    current_config = default_config.copy()

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as f:
                current_config = json.load(f)
                if not isinstance(current_config, dict):
                    current_config = default_config.copy()
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-config] Failed to read the existing configuration: {e}, will use defaults"
            )
            current_config = default_config.copy()

    # If we are only showing the configuration
    if show:
        PrettyOutput.auto_print(f"📋 [c2rust-config] Current config file: {config_path}")
        PrettyOutput.auto_print(
            json.dumps(current_config, ensure_ascii=False, indent=2)
        )
        return

    # If clearing the configuration
    if clear:
        current_config = default_config.copy()
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        PrettyOutput.auto_print(f"✅ [c2rust-config] Configuration cleared: {config_path}")
        return

    # Handle the FFI export validation option
    if enable_ffi_export_validation is not None:
        current_config["enable_ffi_export_validation"] = enable_ffi_export_validation
        status = "enabled" if enable_ffi_export_validation else "disabled"
        PrettyOutput.auto_print(f"✅ [c2rust-config] FFI export validation {status}")

    # Read the root symbol list (start from the existing configuration so we append rather than replace)
    root_symbols: List[str] = cast(
        List[str], current_config.get("root_symbols", []) or []
    )
    header_exts = {".h", ".hh", ".hpp", ".hxx", ".c", ".cxx", ".cpp"}

    if files:
        for file_path in files:
            try:
                file_path = Path(file_path).resolve()
                if not file_path.exists():
                    PrettyOutput.auto_print(
                        f"⚠️ [c2rust-config] Warning: file does not exist, skipping: {file_path}"
                    )
                    continue

                # Check whether it is a header file
                if file_path.suffix.lower() in header_exts:
                    # Extract function names from the header file
                    PrettyOutput.auto_print(
                        f"📋 [c2rust-config] Extracting function names from header file: {file_path}"
                    )
                    try:
                        # Use a temporary file to store the extracted function names
                        import tempfile

                        from haijunbot.haijunbot_c2rust.collector import (
                            collect_function_names as _collect_fn_names,
                        )

                        with tempfile.NamedTemporaryFile(
                            mode="w", suffix=".txt", delete=False, encoding="utf-8"
                        ) as tmp:
                            tmp_path = Path(tmp.name)
                        _collect_fn_names(
                            files=[file_path],
                            out_path=tmp_path,
                            compile_commands_root=None,
                        )
                        # Read the extracted function names
                        txt = tmp_path.read_text(encoding="utf-8")
                        collected = [
                            ln.strip() for ln in txt.splitlines() if ln.strip()
                        ]
                        root_symbols.extend(collected)
                        PrettyOutput.auto_print(
                            f"✅ [c2rust-config] Extracted {len(collected)} function names from header file {file_path.name}"
                        )
                        # Clean up the temporary file
                        try:
                            tmp_path.unlink()
                        except Exception as e:
                            save_exception(
                                e, module="haijunbot_c2rust.eli", function="config"
                            )
                            pass
                    except Exception as e:
                        PrettyOutput.auto_print(
                            f"❌ [c2rust-config] Failed to extract function names from header file: {file_path}: {e}"
                        )
                        raise typer.Exit(code=1)
                else:
                    # Only .txt files are allowed as symbol list files
                    if file_path.suffix.lower() != ".txt":
                        PrettyOutput.auto_print(
                            f"⚠️ [c2rust-config] Warning: unsupported file type {file_path.suffix}, skipping: {file_path}"
                        )
                        PrettyOutput.auto_print(
                            "💡 [c2rust-config] hint: use a header/source file (.h/.hh/.hpp/.hxx/.c/.cxx/.cpp) to extract function names, or use a .txt file to provide the symbol list"
                        )
                        continue
                    # Read the function name list file (one function name per line)
                    txt = file_path.read_text(encoding="utf-8")
                    collected = [
                        ln.strip()
                        for ln in txt.splitlines()
                        if ln.strip() and not ln.strip().startswith("#")
                    ]
                    root_symbols.extend(collected)
                    PrettyOutput.auto_print(
                        f"📋 [c2rust-config] Read {len(collected)} root symbols from file {file_path.name}"
                    )
            except typer.Exit:
                raise
            except Exception as e:
                PrettyOutput.auto_print(
                    f"❌ [c2rust-config] Failed to process file: {file_path}: {e}"
                )
                raise typer.Exit(code=1)

    # Flag whether root_list_syms was processed, so that the configuration is updated even if the result is empty
    processed_root_list_syms = False
    if isinstance(root_list_syms, str) and root_list_syms.strip():
        parts = [
            s.strip() for s in root_list_syms.replace("\n", ",").split(",") if s.strip()
        ]
        root_symbols.extend(parts)
        processed_root_list_syms = True
        PrettyOutput.auto_print(
            f"📋 [c2rust-config] Read root symbols from the command line: {len(parts)}"
        )

    # Deduplicate the root symbol list (if files or root_list_syms was processed, or root_symbols is non-empty, update the configuration)
    if files or processed_root_list_syms or root_symbols:
        try:
            root_symbols = list(dict.fromkeys(root_symbols))
        except Exception:
            root_symbols = sorted(list(set(root_symbols)))
        current_config["root_symbols"] = root_symbols
        PrettyOutput.auto_print(
            f"✅ [c2rust-config] Root symbol list set: {len(root_symbols)}"
        )

    # Read the disabled library list
    if isinstance(disabled_libs, str) and disabled_libs.strip():
        disabled_list = [
            s.strip() for s in disabled_libs.replace("\n", ",").split(",") if s.strip()
        ]
        if disabled_list:
            current_config["disabled_libraries"] = disabled_list
            PrettyOutput.auto_print(
                f"✅ [c2rust-config] Disabled library list set: {', '.join(disabled_list)}"
            )

    # Read additional notes
    if isinstance(additional_notes, str):
        current_config["additional_notes"] = additional_notes.strip()
        if additional_notes.strip():
            PrettyOutput.auto_print(
                f"✅ [c2rust-config] Additional notes set: {len(additional_notes.strip())} characters"
            )
        else:
            PrettyOutput.auto_print("✅ [c2rust-config] Additional notes cleared")

    # If no arguments were provided, show a hint to the user
    if (
        not files
        and not root_list_syms
        and not disabled_libs
        and additional_notes is None
        and enable_ffi_export_validation is None
    ):
        PrettyOutput.auto_print(
            "⚠️ [c2rust-config] No arguments provided; use --show to view the current configuration, or use --help for help"
        )
        return

    # Save the configuration
    try:
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(current_config, f, ensure_ascii=False, indent=2)
        PrettyOutput.auto_print(f"✅ [c2rust-config] Configuration saved: {config_path}")
        PrettyOutput.auto_print(
            json.dumps(current_config, ensure_ascii=False, indent=2)
        )
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [c2rust-config] Failed to save configuration: {e}")
        raise typer.Exit(code=1)


@app.command("run")
def run(
    llm_group: Optional[str] = typer.Option(
        None,
        "-g",
        "--llm-group",
        help="Model group used for LLM-related stages (lib-replace/prepare/transpile/optimize)",
    ),
    max_retries: int = typer.Option(
        0,
        "-m",
        "--max-retries",
        help="Maximum number of retries for transpile build/fix and review (0 means unlimited)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Enable interactive mode (non-interactive by default)",
    ),
    reset: bool = typer.Option(
        False,
        "--reset",
        help="Reset the state and execute all stages from the beginning",
    ),
    quick_mode: bool = typer.Option(
        False,
        "--quick-mode",
        help="Quick mode; disables methodology, rule loading, etc",
    ),
) -> None:
    """
    Execute the pipeline in sequence: scan -> lib-replace -> prepare -> transpile -> optimize

    Supports resumable runs: automatically skip completed stages based on the state file (.haijunbot/c2rust/run_state.json).

    Constraints:

    - The root symbol list and disabled library list are read from the config file (.haijunbot/c2rust/config.json)
      Use the haijunbot-c2rust config command to set these configurations (for example: haijunbot-c2rust config --files bzlib.h)

    - Use --reset to reset the state and execute all stages from the beginning

    - prepare/transpile will use the model group specified by --llm-group

    - The optimize stage uses the default optimization configuration, automatically detects the crate root directory, and performs conservative optimization (unsafe cleanup, structure optimization, visibility optimization, documentation supplementation)
    """

    try:
        set_llm_group(llm_group)
        # Load the state file
        if reset:
            # Reset the state
            state_path = _get_run_state_path()
            if state_path.exists():
                state_path.unlink()
                PrettyOutput.auto_print("⚠️ [c2rust-run] State reset; will execute from the beginning")
            state = _load_run_state()
        else:
            state = _load_run_state()
            # Show the current state
            completed_stages = [
                s for s, info in state.items() if info.get("completed", False)
            ]
            if completed_stages:
                PrettyOutput.auto_print(
                    f"🚀 [c2rust-run] Detected completed stages: {', '.join(completed_stages)}; continuing from the checkpoint"
                )

        # Step 1: scan
        if not state.get("scan", {}).get("completed", False):
            PrettyOutput.auto_print("🚀 [c2rust-run] scan: start")
            _run_scan(
                dot=None,
                only_dot=False,
                subgraphs_dir=None,
                only_subgraphs=False,
                png=False,
                non_interactive=True,
            )
            PrettyOutput.auto_print("✅ [c2rust-run] scan: complete")
            # Save the state (since _run_scan is called directly, the state must be saved manually)
            _save_run_state("scan", completed=True)
        else:
            PrettyOutput.auto_print("🚀 [c2rust-run] scan: already completed, skipping")

        # Step 2: lib-replace (read the root list and disabled library list from the config file)
        if not state.get("lib_replace", {}).get("completed", False):
            # Read the base configuration from the config file
            config = _load_config()
            root_names: List[str] = list(config.get("root_symbols", []))
            disabled_list: Optional[List[str]] = (
                config.get("disabled_libraries", []) or None
            )

            # Deduplicate and validate (fall back to the automatic root set when allowed to be empty)
            if root_names:
                try:
                    root_names = list(dict.fromkeys(root_names))
                except Exception:
                    root_names = sorted(list(set(root_names)))

            candidates_list: Optional[List[str]] = root_names if root_names else None
            if not candidates_list:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-run] lib-replace: root list is empty; falling back to the automatically detected root set (based on scan results)"
                )

            if disabled_list:
                PrettyOutput.auto_print(
                    f"📋 [c2rust-run] lib-replace: read disabled libraries from config file: {', '.join(disabled_list)}"
                )

            # Execute lib-replace (default library std)
            library = "std"
            root_count_str = (
                str(len(candidates_list)) if candidates_list is not None else "auto"
            )
            PrettyOutput.auto_print(
                f"🚀 [c2rust-run] lib-replace: start (library: {library}, root count: {root_count_str})"
            )
            ret = _apply_library_replacement(
                db_path=Path("."),
                library_name=library,
                candidates=candidates_list,  # None means automatically detect all roots
                out_symbols_path=None,
                out_mapping_path=None,
                max_funcs=None,
                disabled_libraries=disabled_list,
                non_interactive=not interactive,
            )
            try:
                order_msg = (
                    f"\n[c2rust-run] lib-replace: transpilation order: {ret['order']}"
                    if "order" in ret
                    else ""
                )
                PrettyOutput.auto_print(
                    f"✅ [c2rust-run] lib-replace: replacement mapping: {ret['mapping']}\n"
                    f"✅ [c2rust-run] lib-replace: new symbol table: {ret['symbols']}"
                    + order_msg
                )
            except Exception as _e:
                PrettyOutput.auto_print(
                    f"⚠️ [c2rust-run] lib-replace: a non-fatal error occurred while outputting the result: {_e}"
                )
            # Save the state (since _apply_library_replacement is called directly, the state must be saved manually)
            _save_run_state("lib_replace", completed=True)
        else:
            PrettyOutput.auto_print("🚀 [c2rust-run] lib-replace: already completed, skipping")

        # Step 3: prepare
        if not state.get("prepare", {}).get("completed", False):
            PrettyOutput.auto_print("🚀 [c2rust-run] prepare: start")
            # Read the FFI export validation setting from the config file
            config = _load_config()
            enable_ffi_export_validation = config.get(
                "enable_ffi_export_validation", False
            )
            _execute_llm_plan(
                apply=True,
                non_interactive=not interactive,
                enable_ffi_export_validation=enable_ffi_export_validation,
            )
            PrettyOutput.auto_print("✅ [c2rust-run] prepare: complete")
            # Save the state (since _execute_llm_plan is called directly, the state must be saved manually)
            _save_run_state("prepare", completed=True)
        else:
            PrettyOutput.auto_print("🚀 [c2rust-run] prepare: already completed, skipping")

        # Step 4: transpile
        if not state.get("transpile", {}).get("completed", False):
            PrettyOutput.auto_print("🚀 [c2rust-run] transpile: start")
            from haijunbot.haijunbot_c2rust.transpiler import run_transpile as _run_transpile

            # Read the configuration from the config file
            config = _load_config()
            enable_ffi_export_validation = config.get(
                "enable_ffi_export_validation", False
            )
            _run_transpile(
                project_root=Path("."),
                crate_dir=None,
                max_retries=max_retries,
                disabled_libraries=None,  # Restore from the config file
                root_symbols=None,  # Restore from the config file
                non_interactive=not interactive,
                enable_ffi_export_validation=enable_ffi_export_validation,
                quick_mode=quick_mode,
            )
            PrettyOutput.auto_print("✅ [c2rust-run] transpile: complete")
            # Save the state (since _run_transpile is called directly, the state must be saved manually)
            _save_run_state("transpile", completed=True)
        else:
            PrettyOutput.auto_print("🚀 [c2rust-run] transpile: already completed, skipping")

        # Step 5: optimize
        if not state.get("optimize", {}).get("completed", False):
            try:
                PrettyOutput.auto_print("🚀 [c2rust-run] optimize: start")
                from haijunbot.haijunbot_c2rust.optimizer import (
                    optimize_project as _optimize_project,
                )
                from haijunbot.haijunbot_c2rust.utils import default_crate_dir

                # Use the same logic as transpile to determine the project root directory and crate directory
                project_root = Path(".")
                crate_dir = default_crate_dir(project_root)
                PrettyOutput.auto_print(
                    f"📋 [c2rust-run] optimize: using project root directory: {project_root}, crate directory: {crate_dir}"
                )
                res = _optimize_project(
                    project_root=project_root,
                    crate_dir=crate_dir,
                    non_interactive=not interactive,
                    quick_mode=quick_mode,
                )
                summary = (
                    f"[c2rust-run] optimize: result summary:\n"
                    f"  files_scanned: {res.get('files_scanned')}\n"
                    f"  unsafe_removed: {res.get('unsafe_removed')}\n"
                    f"  unsafe_annotated: {res.get('unsafe_annotated')}\n"
                    f"  visibility_downgraded: {res.get('visibility_downgraded')}\n"
                    f"  docs_added: {res.get('docs_added')}\n"
                    f"  cargo_checks: {res.get('cargo_checks')}\n"
                )
                PrettyOutput.auto_print(summary)

                # Check whether optimization is truly complete (all steps completed, including clippy warning fixes)
                optimize_truly_completed = _check_optimize_completed(crate_dir)
                if optimize_truly_completed:
                    PrettyOutput.auto_print("✅ [c2rust-run] optimize: complete")
                    # Save the state (since _optimize_project is called directly, the state must be saved manually)
                    _save_run_state("optimize", completed=True)
                else:
                    PrettyOutput.auto_print(
                        "⚠️ [c2rust-run] optimize: some steps are not complete (such as clippy warnings not fully fixed); will continue next time"
                    )
                    # Do not save the state; optimization will continue when resuming next time
            except Exception as _e:
                PrettyOutput.auto_print(f"❌ [c2rust-run] optimize: error: {_e}")
                raise
        else:
            PrettyOutput.auto_print("🚀 [c2rust-run] optimize: already completed, skipping")

        # All stages completed
        PrettyOutput.auto_print("🎉 [c2rust-run] All stages completed! ")
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [c2rust-run] error: {e}")
        raise typer.Exit(code=1)


@app.command("verify")
def verify(
    llm_group: Optional[str] = typer.Option(
        None,
        "-g",
        "--llm-group",
        help="Model group used for LLM analysis and optimization",
    ),
    max_iterations: int = typer.Option(
        10,
        "-i",
        "--max-iterations",
        help="Maximum number of iterations (default 10)",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Enable interactive mode (non-interactive by default)",
    ),
    quick_mode: bool = typer.Option(
        False,
        "--quick-mode",
        help="Quick mode; disables methodology, rule loading, etc",
    ),
) -> None:
    """
    Verify the functional alignment between the transpiled Rust code and the original C code, and support iterative optimization.

    Workflow:

    1. Check whether the c2rust transpilation is complete (transpile and optimize stages); if not, show a hint and exit

    2. Switch to the target crate directory and create an Agent for functional alignment analysis (forcibly split into subtasks):
       - Read and analyze the C code and Rust code
       - Compare function signatures and type definitions
       - Analyze function logic and edge cases
       - Check error handling and memory safety
       - Generate a structured alignment conclusion

    3. If there is inconsistency, create a CodeAgent to optimize the code based on the report, then re-analyze until the Agent considers there are no problems or the maximum number of iterations is reached

    Example:

      # Verify functional alignment
      haijunbot-c2rust verify

      # Specify the model group and maximum number of iterations
      haijunbot-c2rust verify --llm-group gpt-4 --max-iterations 5

    Constraints:

    - 'haijunbot-c2rust run' must be completed before verification can be performed

    - The verification process automatically switches to the crate directory for analysis and optimization

    - All analysis tasks are forcibly split into subtasks to ensure comprehensiveness
    """
    try:
        _run_verify(
            project_root=Path("."),
            max_iterations=max_iterations,
            non_interactive=not interactive,
            quick_mode=quick_mode,
        )
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [c2rust-verify] error: {e}")
        raise typer.Exit(code=1)


def main() -> None:
    """Main entry point"""
    app()


if __name__ == "__main__":
    main()
