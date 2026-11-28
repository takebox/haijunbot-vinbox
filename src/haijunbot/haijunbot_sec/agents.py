# -*- coding: utf-8 -*-
"""Agent creation and subscription module"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from typing import Any, Dict

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_sec.prompts import build_summary_prompt
from haijunbot.haijunbot_sec.prompts import get_cluster_summary_prompt
from haijunbot.haijunbot_sec.prompts import get_cluster_system_prompt
from haijunbot.haijunbot_sec.prompts import get_review_summary_prompt
from haijunbot.haijunbot_sec.prompts import get_review_system_prompt
from haijunbot.haijunbot_tools.registry import ToolRegistry
from haijunbot.haijunbot_utils.tag import ot


def subscribe_summary_event(agent: Agent) -> Dict[str, str]:
    """Subscribe to the Agent summary event"""
    summary_container: Dict[str, str] = {"text": ""}
    try:
        from haijunbot.haijunbot_agent.events import AFTER_SUMMARY as _AFTER_SUMMARY
    except Exception:
        _AFTER_SUMMARY = None  # type: ignore

    if _AFTER_SUMMARY:

        def _on_after_summary(**kwargs: Any) -> None:
            try:
                summary_container["text"] = str(kwargs.get("summary", "") or "")
            except Exception:
                summary_container["text"] = ""

        try:
            agent.event_bus.subscribe(_AFTER_SUMMARY, _on_after_summary)
        except Exception as e:
            save_exception(e, module="haijunbot_sec.agents", function="_on_after_summary")
            pass
    return summary_container


def create_analysis_agent(task_id: str, force_save_memory: bool = False) -> Agent:
    """Create the analysis Agent"""
    system_prompt = f"""
# Single-Agent security analysis constraints
- Your core task is to evaluate the security issues in the code. Goal: for the current candidate issue, verify the evidence, assess the risk, and supplement remediation suggestions; find the vulnerability trigger path and confirm that it triggers under certain conditions; use this to judge whether it is a vulnerability.
- **Call path derivation is mandatory**:
  - For each candidate issue, you must explicitly derive the complete call path from a controllable input to the defective code.
  - The call path derivation must include:
    1. Identify the source of the controllable input (e.g., user input, network data, file reads, command-line arguments, etc.)
    2. Trace the data flow: starting from the input source, progressively trace how the data is passed to the location of the defective code
    3. Identify the call chain: explicitly list the entire sequence of function calls from the entry function to the defective code (e.g., main() -> parse_input() -> process_data() -> vulnerable_function())
    4. Analyze the data validation at each call site: check whether each function validates, bounds-checks, or safety-checks the input
    5. Confirm the trigger condition: explicitly state under what conditions an unvalidated or malicious input can reach the location of the defective code
  - If a complete call path cannot be derived, or all call paths have adequate protective measures, it should be judged a false positive.
  - The call path derivation must be explicitly shown during the analysis and must not be omitted or assumed.
- Tools first: use read_code to read the source code near the target file (about ~50 lines before and after the line number); when necessary, use execute_script to assist with retrieval.
- **Call path tracing requirements**:
  - You must trace upward to all possible callers and examine the complete call path to confirm whether the risk truly exists.
  - Use the read_code and execute_script tools to find the callers of a function (e.g., use grep to search for the function name and find all locations that call it).
  - For each caller, you must check whether it validates the input.
  - If you find any call path without validation, you must explicitly record that path.
  - For example: if a function has a null-pointer dereference risk, you must check all callers. If all callers can ensure the passed pointer is non-null, then the risk may not actually trigger in the current codebase; but if any caller does not validate, then the risk truly exists.
- If multiple warnings are in the same file and their line numbers are not far apart, you may read the shared context in one pass and perform a joint analysis and judgment on these adjacent warnings; but still avoid irrelevant expansion and large-scale traversal.
- It is forbidden to modify any file or execute write-operation commands (rm/mv/cp/echo >, sed -i, git, patch, chmod, chown, etc.); only read-only analysis and reading.
- Perform only one operation at a time; wait for the tool result before proceeding to the next step.
- **Memory usage**:
  - During the analysis, make good use of the memory tool (action=retrieve) to retrieve existing memories, especially memories related to the function currently being analyzed.
  - If necessary, use the memory tool (action=save) to save the key analysis points of each function, using the function name as the tag (e.g., function name, file name, etc.).
  - Examples of memory content: a certain function's pointer has been null-checked, a certain function already has input validation, the call path analysis result of a certain function, etc.
  - This avoids repeated analysis, improves efficiency, and maintains consistency in the analysis.
- After completing the judgment of the candidate issues in this batch, the main output should print only the terminator {ot("!!!COMPLETE!!!")} and nothing else. The task summary will be given in a subsequent interaction.
""".strip()

    agent_kwargs: Dict[str, Any] = dict(
        system_prompt=system_prompt,
        name=task_id,
        auto_complete=True,
        need_summary=True,
        summary_prompt=build_summary_prompt(),
        non_interactive=True,
        in_multi_agent=False,
        use_methodology=False,
        use_analysis=False,
        output_handler=[ToolRegistry()],
        force_save_memory=force_save_memory,
        use_tools=["read_code", "execute_script", "memory"],
        quick_mode=True,
    )
    return Agent(**agent_kwargs)


def create_review_agent(
    current_review_num: int,
) -> Agent:
    """Create the review Agent"""
    review_system_prompt = get_review_system_prompt()
    review_summary_prompt = get_review_summary_prompt()

    review_task_id = f"HAIJUNBOT-SEC-Review-Batch-{current_review_num}"
    review_agent_kwargs: Dict[str, Any] = dict(
        system_prompt=review_system_prompt,
        name=review_task_id,
        auto_complete=True,
        need_summary=True,
        summary_prompt=review_summary_prompt,
        non_interactive=True,
        in_multi_agent=False,
        use_methodology=False,
        use_analysis=False,
        output_handler=[ToolRegistry()],
        use_tools=["read_code", "execute_script", "memory"],
        quick_mode=True,
    )
    return Agent(**review_agent_kwargs)


def create_cluster_agent(
    file: str,
    chunk_idx: int,
    force_save_memory: bool = False,
) -> Agent:
    """Create the clustering Agent"""
    cluster_system_prompt = get_cluster_system_prompt()
    cluster_summary_prompt = get_cluster_summary_prompt()

    agent_kwargs_cluster: Dict[str, Any] = dict(
        system_prompt=cluster_system_prompt,
        name=f"HAIJUNBOT-SEC-Cluster::{file}::batch{chunk_idx}",
        auto_complete=True,
        need_summary=True,
        summary_prompt=cluster_summary_prompt,
        non_interactive=True,
        in_multi_agent=False,
        use_methodology=False,
        use_analysis=False,
        output_handler=[ToolRegistry()],
        force_save_memory=force_save_memory,
        use_tools=["read_code", "execute_script", "memory"],
        quick_mode=True,
    )
    return Agent(**agent_kwargs_cluster)
