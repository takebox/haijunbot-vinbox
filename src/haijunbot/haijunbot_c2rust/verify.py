# -*- coding: utf-8 -*-
"""
C2Rust functional alignment verification module

Objectives:
- Check whether the c2rust transpilation is complete
- Analyze the functional alignment between the transpiled Rust code and the original C code
- Support iterative optimization until the Agent considers there are no issues

Usage:
- Invoke the verify subcommand from the ELI
- Automatically switch to the target crate directory
- Use task_list_manager to split into subtasks for analysis
- Generate a structured alignment report
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict

from haijunbot.haijunbot_c2rust.constants import CONFIG_JSON
from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
from haijunbot.haijunbot_c2rust.constants import RUN_STATE_JSON
from haijunbot.haijunbot_utils.output import PrettyOutput


def check_transpile_completed(project_root: Path) -> bool:
    """
    Check whether the transpilation is complete.

    Read run_state.json and check whether both the transpile and optimize phases are complete.
    """
    state_path = project_root / C2RUST_DIRNAME / RUN_STATE_JSON
    if not state_path.exists():
        return False

    try:
        with state_path.open("r", encoding="utf-8") as f:
            state = json.load(f)

        transpile_completed: bool = state.get("transpile", {}).get("completed", False)
        optimize_completed: bool = state.get("optimize", {}).get("completed", False)

        return transpile_completed and optimize_completed
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  [verify] Failed to read status file: {e}")
        return False


def load_config(project_root: Path) -> Dict[str, Any]:
    """
    Load the c2rust configuration.

    Return a dictionary containing root_symbols, disabled_libraries and additional_notes.
    """
    config_path = project_root / C2RUST_DIRNAME / CONFIG_JSON
    default_config = {
        "root_symbols": [],
        "disabled_libraries": [],
        "additional_notes": "",
    }

    if not config_path.exists():
        return default_config

    try:
        with config_path.open("r", encoding="utf-8") as f:
            config = json.load(f)
            if not isinstance(config, dict):
                return default_config
            return {
                "root_symbols": config.get("root_symbols", []),
                "disabled_libraries": config.get("disabled_libraries", []),
                "additional_notes": config.get("additional_notes", ""),
            }
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  [verify] Failed to read config file: {e}")
        return default_config


def run_verify(
    project_root: Path,
    max_iterations: int = 10,
    non_interactive: bool = True,
    quick_mode: bool = False,
) -> None:
    """
    Execute functional alignment verification.

    Parameters:
        project_root: project root directory
        max_iterations: maximum number of iterations
        non_interactive: whether to use non-interactive mode
        quick_mode: quick mode, disables methodology, rule loading etc.
    """
    from haijunbot.haijunbot_c2rust.utils import default_crate_dir

    # Step 1: Check whether the transpilation is complete
    PrettyOutput.auto_print("🔍 [verify] Checking transpilation status...")
    if not check_transpile_completed(project_root):
        PrettyOutput.auto_print(
            "❌ [verify] Transpilation is incomplete, please run 'haijunbot-c2rust run' first to complete the transpilation process"
        )
        return
    PrettyOutput.auto_print("✅ [verify] Transpilation is complete")

    # Determine the crate directory
    crate_dir = default_crate_dir(project_root)
    PrettyOutput.auto_print(f"📁 [verify] Target crate directory: {crate_dir}")

    if not crate_dir.exists():
        PrettyOutput.auto_print(f"❌ [verify] crate directory does not exist: {crate_dir}")
        return

    # Load configuration
    config = load_config(project_root)
    PrettyOutput.auto_print(
        f"📋 [verify] Number of root symbols: {len(config.get('root_symbols', []))}, "
        f"Number of disabled libraries: {len(config.get('disabled_libraries', []))}"
    )

    # Step 2: Switch to the crate directory and start verification
    PrettyOutput.auto_print("🚀 [verify] Starting functional alignment verification...")

    import os

    original_cwd = os.getcwd()
    try:
        os.chdir(str(crate_dir))

        # Use task_list_manager to create subtasks for analysis
        PrettyOutput.auto_print(
            "📋 [verify] Creating analysis task list (splitting into subtasks for detailed analysis)..."
        )

        # Execute functional alignment analysis
        alignment_result = _run_alignment_analysis(
            crate_dir=crate_dir,
            project_root=project_root,
            config=config,
            non_interactive=non_interactive,
            quick_mode=quick_mode,
        )

        # Step 3: Check whether iterative optimization is needed
        iteration = 0
        while iteration < max_iterations:
            is_aligned = alignment_result.get("is_aligned", False)

            if is_aligned:
                PrettyOutput.auto_print("✅ [verify] Functional alignment verification passed!")
                PrettyOutput.auto_print(
                    f"📊 [verify] Verification result: {alignment_result.get('summary', 'OK')}"
                )
                break

            iteration += 1
            if iteration >= max_iterations:
                PrettyOutput.auto_print(
                    f"⚠️  [verify] Reached maximum number of iterations ({max_iterations}), stopping optimization"
                )
                PrettyOutput.auto_print(
                    f"📊 [verify] Final verification result: {alignment_result.get('summary', 'NOT OK')}"
                )
                break

            PrettyOutput.auto_print(f"🔄 [verify] Iteration {iteration} optimization...")

            # Execute optimization
            _run_optimization(
                crate_dir=crate_dir,
                project_root=project_root,
                report=alignment_result.get("report", ""),
                config=config,
                non_interactive=non_interactive,
                quick_mode=quick_mode,
            )

            # Re-verify
            PrettyOutput.auto_print("🔍 [verify] Re-verifying functional alignment...")
            alignment_result = _run_alignment_analysis(
                crate_dir=crate_dir,
                project_root=project_root,
                config=config,
                non_interactive=non_interactive,
                quick_mode=quick_mode,
            )
    finally:
        os.chdir(original_cwd)


def _run_alignment_analysis(
    crate_dir: Path,
    project_root: Path,
    config: Dict[str, Any],
    non_interactive: bool,
    quick_mode: bool = False,
) -> Dict[str, Any]:
    """
    Run functional alignment analysis.

    Use task_list_manager to split into subtasks for analysis.
    Subtasks record inconsistencies to files, and the final summary is generated based on these files.
    Return a dictionary containing is_aligned and summary.
    """
    from haijunbot.haijunbot_c2rust.agent_factory import create_agent

    # Define the report file path (saved to the crate root directory)
    report_file = crate_dir / "alignment_report.md"

    # Create the analysis Agent
    # System prompt: introduces a clear workflow (supports large-scale code)
    system_prompt = f"""
You are a functional alignment verification expert for C to Rust code transpilation.

## Core Responsibilities
Analyze the functional alignment between the transpiled Rust code and the original C code, identify inconsistencies and generate a detailed report.

**Core principle: focus on functional consistency, not function interface consistency.** The function signatures, parameter types, and return value types of the Rust code can differ from the C code (for example, using Result instead of error codes, using Option instead of null pointers), as long as the final functional behavior is consistent with the original C code. Do not misjudge differences in interface form as functional inconsistency.

## Clear Workflow (must be executed strictly in order, supports large-scale code analysis)

### Phase 1: Preparation (must be completed first)
1. **Read project configuration**
   - Read the project root directory and crate directory information
   - Understand the root symbol list (root_symbols) and the Disabled library list (disabled_libraries)
   - View additional notes (additional_notes)

2. **Explore code structure and identify file mappings**
   - List all C source code file locations (use glob or list_dir Tool)
   - List all transpiled Rust code file locations
   - **Establish the correspondence between C files and Rust files** (this is a key step)
   - Estimate the size of each file (number of lines); if a single file exceeds 2000 lines, consider further splitting

### Phase 2: Create task list by file (must use task_list_manager)
3. **Use task_list_manager.add_tasks to create the task list**
   - main_goal: "C2Rust functional alignment verification: analyze the functional alignment between the transpiled Rust code and the original C code by file"
   - tasks_info: **split tasks by file**, one subtask per file:
     * Create a task for each C-Rust file pair, task name format: "Verify file: <file name>"
     * Each file task needs to complete all of the following analysis dimensions:
       - Functional behavior consistency comparison (core: verify whether the Rust code implements the same logical functionality as the C code, rather than whether the interface form is consistent)
       - Function logic and algorithm implementation comparison
       - Error handling mechanism verification (focus on whether the functional results of error handling are consistent, rather than whether the implementation approach is the same)
       - Memory safety verification
       - Data structure and layout alignment verification
     * The last summary task: "Summarize all file reports and generate the final alignment report"
   - **important**: file tasks can be executed in parallel (no dependencies), only the summary task depends on all file tasks

### Phase 3: Execute file-level tasks (execute one by one or in parallel)
4. **Use task_list_manager.execute_task to execute each file task**
   - For each file task, provide detailed additional_info:
     * c_file_path: C source code file path
     * rust_file_path: corresponding Rust code file path
     * root_symbols_in_file: list of root symbols to verify in that file
     * analysis_dimensions: list of dimensions to analyze (functional behavior consistency, logic, error handling, memory safety, layout alignment)
   
   - When each file task executes:
     * Read and analyze the C code file (if the file is very large, you can read the key parts in chunks)
     * Read and analyze the corresponding Rust code file
     * **Perform a detailed comparison for each analysis dimension**:
       - **Functional behavior consistency comparison** (core dimension): verify whether the Rust code implements the same logical functionality as the C code. Differences in function signatures, parameter types, and return value types do not count as inconsistencies; as long as the functional behavior is equivalent, it is fine (for example: C returns error codes vs Rust returns Result, C uses pointer parameters vs Rust uses references; these are reasonable transpilation adaptations)
       - Function logic and algorithm implementation comparison
       - Error handling mechanism verification (focus on functional results: whether all error scenarios are covered, whether error propagation is equivalent)
       - Memory safety verification
       - Data structure and layout alignment verification
     * Record the problems found (format: function name, problem description, severity, code comparison)
     * **Immediately generate the partial report for that file**, save it to a temporary file: `{{crate_dir}}/alignment_reports/{{filename}}_report.md`
     * Record the problem statistics (number of problems, severity distribution) in the task result

### Phase 4: Summary and report generation (the last task)
5. **Execute the "Summarize all file reports and generate the final alignment report" task**
   - Read the results and partial report files of all completed file tasks
   - Aggregate the problem statistics of all files
   - Classify by severity (High/Medium/Low)
   - Generate a complete Markdown report, containing:
     * **Overall conclusion** (consistent/inconsistent/partially consistent)
     * **Statistics**: total number of files, number of files analyzed, total number of problems, High/Medium/Low counts
     * **Problem list grouped by file**: problem summary for each file (number of problems, severity distribution)
     * **Detailed list of key problems**: aggregate all High and Medium level problems (each problem includes: file name, function name, problem description, severity, code comparison)
     * **Improvement suggestions**: propose specific fix suggestions for the problems found
   - Write the report to the specified file: {report_file}

### Phase 5: Output verification results (final step)
6. **Output verification results**
   - Read the generated report file: {report_file}
   - Determine the verification result based on the report content:
     * If all problems are Low level or there are no problems → is_aligned: true
     * If there are High or Medium level problems → is_aligned: false
   - Generate a concise summary description (for example: "fully consistent", "High level problems exist", "partially consistent, mainly Low level problems")
   - **Final output requirements**: After the task is completed, the system will ask you to generate a final summary. In the final summary, you must output the verification result strictly according to the following JSON format:
```json
{{
  "is_aligned": true/false,
  "summary": "Overall conclusion (consistent/inconsistent/partially consistent)",
  "report_path": "{report_file}"
}}
```

## important constraints
- **Must strictly execute in the order of the above 5 phases; no phase may be skipped**
- **Must use the task_list_manager Tool; analysis must not be executed directly**
- **Must split tasks by file, not by analysis dimension** (this is what enables support for large-scale code)
- **Immediately generate the partial report for each file after its task is completed** (supports incremental progress viewing)
- **Each subtask must provide detailed additional_info**
- **The problem record format must be unified, including: file name, function name, problem description, severity, code comparison**
- **Must finally output a valid JSON formatted result**

## Large-Scale Code Handling Strategy
- **File splitting principle**: if a single file exceeds 2000 lines, consider further splitting by function group or module
- **Incremental reports**: immediately generate a partial report after each file analysis is completed, to facilitate progress tracking
- **Parallel execution**: file tasks have no dependencies and can be executed in parallel to improve efficiency
- **Memory optimization**: for large files, only read the key parts that need analysis, avoiding loading all content at once
"""

    # Summary prompt: constrains the conclusion result (this prompt is automatically invoked after the Agent completes all tasks)
    summary_prompt = f"""
Based on the analysis results of the functional alignment verification, strictly output the final conclusion according to the following JSON format:

```json
{{
  "is_aligned": true/false,
  "summary": "Overall conclusion (consistent/inconsistent/partially consistent)",
  "report_path": "{report_file}"
}}
```

Requirements:
- Must output the complete JSON format; do not include any other text
- is_aligned: true means fully aligned (all problems are Low level or there are no problems); false means there are High or Medium level inconsistency problems
- summary: concisely describe the overall conclusion, for example: "fully consistent", "High level problems exist", "partially consistent, mainly Low level problems"
- report_path: the path of the generated report file (must be: {report_file})

First read the report file {report_file}, determine the value of is_aligned based on the report content, then output the JSON.
"""

    agent = create_agent(
        name="C2Rust-VerificationAgent",
        non_interactive=non_interactive,
        system_prompt=system_prompt,
        summary_prompt=summary_prompt,
        model_type="smart",
        enable_auto_rule_select=False,
        quick_mode=quick_mode,
    )

    # Build the analysis task
    analysis_task = f"""
You are a functional alignment verification expert for C to Rust code transpilation.

## Task Objective
Analyze the functional alignment between the transpiled Rust code and the original C code, identify inconsistencies and generate a detailed alignment report.

**Core principle: focus on functional consistency, not function interface consistency.** The function signatures, parameter types, and return value types of the Rust code can differ from the C code (for example, using Result instead of error codes, using Option instead of null pointers), as long as the final functional behavior is consistent with the original C code. Do not misjudge differences in interface form as functional inconsistency.

## Project Information
- Project root directory: {project_root}
- Rust crate directory: {crate_dir}
- Root symbol list: {config.get("root_symbols", [])}
- Disabled library list: {config.get("disabled_libraries", [])}
- Additional notes: {config.get("additional_notes", "")}

## Output file
- Alignment summary report: {report_file}
- partial report directory: {crate_dir}/alignment_reports/ (analysis report for each file)

## Execution steps (strictly follow the workflow in the system prompt, supports large-scale code)

### Step 1: Preparation (explore code structure)
1. **Explore C source code locations**
   - Use list_dir or glob Tool to find all C source code files (usually in some subdirectory of the project root directory)
   - Record the full paths of all C files

2. **Explore Rust code structure**
   - Confirm the Rust crate directory structure (current directory: {crate_dir})
   - Use list_dir or glob Tool to find all Rust source code files
   - Record the full paths of all Rust files

3. **Establish file mapping relationships**
   - Establish the correspondence between C files and Rust files (usually file names or path structures are similar)
   - For each file pair, identify the root symbols contained in them
   - Estimate the size of each file (number of lines); if it exceeds 2000 lines, consider further splitting

4. **Create the partial report directory**
   - Create directory: {crate_dir}/alignment_reports/ (if it does not exist)

### Step 2: Create task list by file
**Must immediately use task_list_manager.add_tasks to create the task list**

**important: must split by file, not by analysis dimension!**

Call example (assuming there are two file pairs file1.c/file1.rs, file2.c/file2.rs):
```python
task_list_manager(
    action="add_tasks",
    main_goal="C2Rust functional alignment verification: analyze the functional alignment between the transpiled Rust code and the original C code by file",
    tasks_info=[
        {{
            "name": "Verify file: file1.c",
            "description": "Analyze the functional alignment between file1.c and file1.rs, focus on functional behavior consistency (rather than interface form consistency), including functional behavior, logic, error handling, memory safety, layout alignment and all other dimensions",
            "dependencies": []
        }},
        {{
            "name": "Verify file: file2.c",
            "description": "Analyze the functional alignment between file2.c and file2.rs, focus on functional behavior consistency (rather than interface form consistency), including functional behavior, logic, error handling, memory safety, layout alignment and all other dimensions",
            "dependencies": []
        }},
        # ... create a task for each file pair
        {{
            "name": "Aggregate all file reports and generate the final alignment report",
            "description": "Aggregate the analysis results of all file tasks and generate a complete alignment report",
            "dependencies": ["verify file: file1.c", "verify file: file2.c", ...]  # depends on all file tasks
        }}
    ]
)
```

**Key points:**
- Each file is an independent task; there are no dependencies between file tasks (they can be executed in parallel)
- Each file task needs to complete all analysis dimensions (functional behavior consistency, logic, Error handling, Memory safety, layout alignment)
- The last aggregation task depends on all file tasks

### Step 3: Execute file-level tasks
**For each file task, execute using task_list_manager.execute_task**

When executing each file task, you Must provide detailed additional_info:

**Example: additional_info for the verify file file1.c task**
```json
{{
    "c_file_path": "/path/to/file1.c",
    "rust_file_path": "/path/to/file1.rs",
    "root_symbols_in_file": ["function1", "function2", "Struct1"],
    "analysis_dimensions": [
        "Functional behavior consistency comparison (core: verify functional behavior equivalence rather than interface form consistency)",
        "function logic and algorithm implementation comparison",
        "Error handling mechanism verification (focus on whether functional results are equivalent)",
        "Memory safety verification",
        "Data structure and layout alignment verification"
    ],
    "output_file": "{crate_dir}/alignment_reports/file1_report.md"
}}
```

**Execution steps for each file task:**
1. Read the C code file (if the file is very large, you can read key parts in chunks)
2. Read the corresponding Rust code file
3. **Perform a detailed comparison for each analysis dimension**:
   - **Functional behavior consistency comparison** (core dimension): Verify whether the Rust code implements the same logical functionality as the C code. Differences in function signatures, parameter types, and return value types do not count as inconsistency, as long as the functional behavior is equivalent. For example: C returns an int error code vs Rust returns Result<T,E>, C uses pointer output parameters vs Rust uses return value tuples, C uses NULL to indicate failure vs Rust uses Option -- these are all reasonable translation adaptations and should not be marked as inconsistent
   - **function logic and algorithm implementation comparison**: Compare whether the core logic flow, algorithm behavior, and boundary condition handling are equivalent
   - **Error handling mechanism verification**: Verify whether the coverage of error scenarios and the functional results of error propagation are equivalent (C's error codes/errno and Rust's Result/Option just need to have consistent functional results)
   - **Memory safety verification**: Check unsafe code blocks, memory management, and pointer operation safety
   - **Data structure and layout alignment verification**: Verify struct field order, memory layout alignment, and endianness handling
4. Record all found issues (see format below)
5. **Immediately generate the partial report for that file**, save to: `{crate_dir}/alignment_reports/{{filename}}_report.md`
6. Record issue statistics in the task result (number of issues, severity distribution)

**Issue recording format (each file task must follow):**
```
### [Severity] file name: function name/type name

**Issue description**: Describe the issue in detail

**C code**:
```c
// C code snippet (including file path and line number)
```

**Rust code**:
```rust
// Rust code snippet (including file path and line number)
```

**Impact analysis**: Explain the possible impact of this issue

**Analysis dimension**: function signature/logic/Error handling/Memory safety/layout alignment
```

**Partial report format (generate immediately after each file task completes):**
```markdown
# file alignment report: file1.c / file1.rs

## file information
- C file: /path/to/file1.c
- Rust file: /path/to/file1.rs
- Root symbol count: 3

## Issue statistics
- Total issue count: 5
- High: 1
- Medium: 2
- Low: 2

## Issue list
[List all issues in the above format]

## Analysis dimension summary
- Functional behavior consistency: 1 issue
- function logic and algorithm implementation: 2 issues
- Error handling mechanism: 1 issue
- Memory safety: 1 issue
- Data structure and layout alignment: 0 issues
```

**Severity classification:**
- **High**: Issues that severely affect functionality or safety (e.g.: logic errors, inconsistent functional behavior, Memory safety issues, missing functionality)
- **Medium**: Issues with moderate impact (e.g.: different error handling approaches but consistent functional results, boundary condition handling differences)
- **Low**: Minor issues or issues that do not affect functionality (e.g.: function signature style differences, naming style differences, missing comments)

**Important**: Differences that are only in the form of function signatures, parameter types, and return value types (but with equivalent functional behavior) should not be marked as issues of any severity. Only when the functional behavior is truly inconsistent should it be marked as an issue.

### Step 4: Aggregate report
**Execute the "Aggregate all file reports and generate the final alignment report" task**

This task needs to:
1. Read the results of all completed file tasks
2. Read all partial report files (`{crate_dir}/alignment_reports/*_report.md`)
3. Aggregate the issue statistics of all files
4. Classify by severity (High/Medium/Low)
5. Generate a complete Markdown report containing the following sections:
   - **Overall conclusion**: consistent/inconsistent/partially consistent
   - **Statistics**:
     * Total file count, analyzed file count
     * Total issue count, High/Medium/Low counts
     * Issue distribution per file
   - **Issue summary grouped by file**: number of issues per file, severity distribution, overview of key issues
   - **Detailed list of key issues**: Aggregate detailed information for all High and Medium severity issues (including file name, function name, issue description, severity, code comparison)
   - **Improvement suggestions**: Propose specific fix suggestions for the found issues
6. Write the report to file: {report_file}

### Step 5: Output verification results
**Finally, when all tasks are completed, the system will ask you to generate a final summary**

In the final summary, you need to:
1. Read the generated report file: {report_file}
2. Determine is_aligned based on the report content:
   - If all issues are Low severity or there are no issues -> is_aligned: true
   - If there exist High or Medium severity issues -> is_aligned: false
3. Generate a concise summary description
4. **You must output the verification result strictly in the following JSON format**:
```json
{{
  "is_aligned": true/false,
  "summary": "Overall conclusion (consistent/inconsistent/partially consistent)",
  "report_path": "{report_file}"
}}
```

**Important**: The final summary must output the complete JSON format and must not include other text.

## Important reminders
- **You must strictly execute in the order of the above 5 steps**
- **Tasks must be split by file, not by analysis dimension** (this way large-scale code can be supported)
- **Create the task list immediately after completing step 1; do not start the analysis directly**
- **Generate the partial report immediately after each file task completes** (supports incremental progress viewing)
- **Each subtask Must provide detailed additional_info**
- **The issue recording format must be uniform, including file name, function name, issue description, severity, and code comparison**
- **A valid JSON format result must be output in the end**

## Large-scale code handling tips
- **File splitting**: If a single file exceeds 2000 lines, you can further split by function group
- **Incremental reports**: Generate the partial report immediately after each file analysis completes, to facilitate progress tracking
- **Parallel execution**: There are no dependencies between file tasks, so they can be executed in parallel to improve efficiency
- **Memory optimization**: For large files, only read the key parts that need analysis (based on the root symbol list)
"""

    try:
        result = agent.run(analysis_task)
        # Try to extract structured data from the result
        if isinstance(result, dict):
            return result
        # If the returned value is a string, try to parse JSON
        if isinstance(result, str):
            try:
                parsed: Dict[str, Any] = json.loads(result)
                return parsed
            except json.JSONDecodeError:
                # Try to extract the JSON object from the text (handling cases such as markdown code block wrapping)
                from haijunbot.haijunbot_utils.utils import extract_json_from_text

                json_str, _ = extract_json_from_text(result)
                if json_str:
                    try:
                        parsed = json.loads(json_str)
                        return parsed
                    except json.JSONDecodeError:
                        pass
        # Default return (parse failure is treated as not aligned, triggering optimization)
        return {
            "is_aligned": False,
            "summary": "Verification complete (unable to parse detailed results)",
            "report_path": str(report_file),
        }
    except Exception as e:
        PrettyOutput.auto_print(f"❌ [verify] Error during analysis: {e}")
        return {
            "is_aligned": False,
            "summary": "Analysis failed",
            "report_path": str(report_file),
        }


def _run_optimization(
    crate_dir: Path,
    project_root: Path,
    report: str,
    config: Dict[str, Any],
    non_interactive: bool,
    quick_mode: bool = False,
) -> None:
    """
    Run code optimization.

    Use CodeAgent to optimize the Rust code based on the alignment report.
    """
    from haijunbot.haijunbot_c2rust.agent_factory import create_code_agent
    from haijunbot.haijunbot_c2rust.constants import C2RUST_DIRNAME
    from haijunbot.haijunbot_c2rust.constants import SYMBOLS_JSONL

    # Determine the symbols.jsonl file path
    symbols_path = project_root / C2RUST_DIRNAME / SYMBOLS_JSONL

    # Create the optimization CodeAgent and add the read_symbols Tool
    agent = create_code_agent(
        name="C2Rust-OptimizationAgent",
        need_summary=False,
        non_interactive=non_interactive,
        append_tools="read_symbols",  # Add the read_symbols Tool for reading C symbol information
        model_type="smart",
        quick_mode=quick_mode,
    )

    optimization_task = f"""
You are an optimization expert for C to Rust code translation, specifically responsible for fixing issues found in functional alignment verification.

## Task objective
Based on the functional alignment verification report, optimize the Rust code to fix inconsistent issues, ensuring that the translated Rust code is fully functionally aligned with the original C code.

**Core principle: Focus on Functional consistency, not function interface consistency.** The goal of fixing is to make the functional behavior of the Rust code equivalent to the C code, rather than making the function signatures, parameter types, and return value types consistent with the C code. Rust's idiomatic style (such as Result instead of error codes, Option instead of null pointers, references instead of pointers) is reasonable and should not be broken for interface consistency. Fixing is only needed when the functional behavior is truly inconsistent.

## Alignment report
{report}

## Project information
- Project root directory: {project_root}
- Rust crate directory: {crate_dir}
- Root symbol list: {config.get("root_symbols", [])}
- Disabled library list: {config.get("disabled_libraries", [])}
- Additional notes: {config.get("additional_notes", "")}

## Available Tools
1. **read_symbols**: Read C symbol information (used to compare against C code)
   - Symbol table file: {symbols_path}
   - Usage example: `read_symbols({{"symbols_file": "{symbols_path}", "symbols": ["function name"]}})`
2. **read_code**: Read C source code or Rust code files
   - When reading a Rust file, use a path relative to the crate root (such as `src/xxx.rs`) or an absolute path
   - When reading a C file, use the full path of the C source file
3. **edit_file**: Modify Rust code files (find and replace)
4. **edit_file_by_line**: Replace Rust code files by line number range
5. **write_file**: Overwrite the entire Rust code file
6. **execute_script**: Execute compilation and test commands (such as `cargo check`, `cargo test`)

## Optimization workflow

### Step 1: Analyze the issues (ANALYZE)
1. Carefully read the alignment report and understand for each issue:
   - Issue type (functional behavior inconsistency, logic, Error handling, Memory safety, layout alignment)
   - **Filter false positives**: If an issue is only a formal difference in function signatures, parameter types, and return value types but the functional behavior is equivalent, then no fix is needed
   - Severity (High/Medium/Low)
   - Specific location (file name, function name)
   - Differences between the C code and Rust code

### Step 2: Collect information (COLLECT)
2. For each issue that needs fixing:
   - Use `read_code` to read the relevant Rust code file
   - Use `read_symbols` to read the corresponding C symbol information (if you need to compare against the C implementation)
   - Use `read_code` to read the C source file (if a detailed comparison is needed)

### Step 3: Propose a plan (HYPOTHESIZE)
3. Design a fix plan for each issue:
   - Analyze the root cause of the issue
   - Design a fix plan with minimal changes
   - Consider the impact of the fix on other code
   - Ensure the fix plan conforms to Rust best practices

### Step 4: Execute the fix (EXECUTE)
4. Fix the issues one by one:
   - Use the `edit_file` Tool to modify the Rust code (use `write_file` for large-scale rewrites, use `edit_file_by_line` for line-number replacement)
   - After each modification, use `execute_script` to run `cargo check` to verify compilation
   - If the report contains test cases, run `cargo test` to verify functionality
   - Ensure the fixed code can compile successfully

### Step 5: Reflect (REVIEW)
5. After completing the fixes, perform a comprehensive reflection:
   - Review code quality (syntax/functionality/style)
   - Check whether the functionality is complete and verify that all issues have been fixed
   - Check whether all affected code has been considered
   - Confirm whether there are accompanying changes (such as documentation, tests, configuration, etc.)
   - Ensure the code can compile successfully
   - Run relevant tests to ensure the functionality is correct
   - Check whether new issues have been introduced
   - Assess the impact scope and potential risks

## Optimization requirements
1. **Priority**: Fix High severity issues first, then Medium severity issues
2. **Minimal changes**: Only modify the necessary parts; do not perform unrelated refactoring
3. **Functional alignment**: Ensure the functional behavior of the fixed Rust code is equivalent to the original C code (rather than interface form consistency). Rust's idiomatic style (Result, Option, references, etc.) is reasonable and does not need to be changed to an interface form consistent with C
4. **Code quality**:
   - Maintain code style and project conventions
   - Use Rust best practices (such as the Result type for error handling and the ownership system for memory management); do not give up Rust idioms for interface consistency with C
   - Add necessary comments explaining the reason for the fix
5. **Verification**: After each modification you must verify that compilation succeeds; do not accumulate multiple modifications and then verify
6. **Do not break existing functionality**: When fixing issues, ensure that other code that already works normally is not affected

## Notes
- **C code comparison**: If you need to compare against the C implementation, use the `read_symbols` Tool to read symbol information, or use `read_code` to read the C source file
- **Rust file path**: When reading a Rust file, use a path relative to the crate root (such as `src/xxx.rs`)
- **Compilation verification**: After each modification, immediately run `cargo check` to verify compilation; do not wait until the end to verify
- **Test verification**: If the alignment report mentions test cases, run the relevant tests to ensure the functionality is correct

Please start the optimization and fix the issues step by step according to the workflow above.
"""

    try:
        agent.run(optimization_task)
        PrettyOutput.auto_print("✅ [verify] Optimization complete")
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  [verify] Error during optimization: {e}")
