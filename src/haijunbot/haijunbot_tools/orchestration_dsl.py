# -*- coding: utf-8 -*-
"""Orchestration Python DSL (layer 1: structure generation).

Let users write orchestration in Python, but Python **only generates the DAG structure** and does not take part in runtime scheduling.
After the script runs, the structure exported by the `Pipeline` object (agents/flow/spec_text/default_on_error)
is **isomorphic** to the structure parsed from a YAML orchestration file, and can be handed directly to pipeline_runner's `_build_dag`
for consumption, so the execution engine, scheduling, events, frontend visualization, and cross-node distribution all stay unchanged.

Design orientation (see docs/design/orchestration-python-dsl.md for details):
- **Pure library, no side effects**: this module only provides constructors; it does not dispatch tasks, write files, or depend on the engine.
- **Declare structure only**: when the script finishes executing you get the DAG data; preview = execute the script to get the structure, without running the Agent.
- **Isomorphic with YAML**: flow item fields are consistent with YAML `flow`
  (stage/agent/depends_on/input/output/gate/when/retry/on_error),
  and agents item fields are consistent with YAML `agents` (name/working_dir/task, etc.).
- **Loops are expanded at compile time**: use Python's for/if to decide the set of stages at generation time;
  runtime dynamic loops (the loop primitive) are out of scope for this layer.

Usage (orchestration scripts use the top-level variable `pipeline` by convention):

    from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage

    pipeline = Pipeline()
    pipeline.spec("Pipeline background...")
    pipeline.agent("planner", working_dir=".", task="You are the planner...")
    pipeline.add(stage("plan", agent="planner", output=".df/plan.md"))
"""

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Fields allowed in a flow item (consistent with the keys read by pipeline_runner._build_dag)
_FLOW_KEYS = (
    "stage",
    "agent",
    "depends_on",
    "input",
    "output",
    "gate",
    "when",
    "retry",
    "on_error",
)

# Fields allowed in an agents item (consistent with YAML agents items)
_AGENT_KEYS = (
    "name",
    "working_dir",
    "task",
    "llm_group",
    "tool_group",
    "node_id",
    "proxy_node",
    "quick_mode",
    "restore_session",
    "no_interaction_mode",
    "access_acl",
    "additional_args",
)

# Fields allowed in a loop item (layer 2: runtime loop primitive)
_LOOP_KEYS = (
    "loop",
    "body",
    "until",
    "max_iterations",
    "on_error",
)


def stage(
    name: str,
    agent: str,
    depends_on: Optional[Any] = None,
    input: Optional[Any] = None,  # noqa: A002 - keep consistent with the YAML field name
    output: str = "",
    gate: bool = False,
    when: Optional[str] = None,
    retry: int = 0,
    on_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Declare a pipeline stage (corresponding to an item in YAML `flow`).

    The parameters map one-to-one to the YAML `flow` item fields; this function only performs **normalization and validation**,
    and does not fill in `depends_on` (the semantics of default = previous stage are handled by `_build_dag`,
    to guarantee complete consistency with YAML behavior).

    Parameters:
        name: stage name (unique; used for referencing by depends_on/when).
        agent: the referenced agent name (must be defined in Pipeline.agent()).
        depends_on: dependent stage name(s) (string or list); None/empty means it is left to `_build_dag`
            to apply the "previous stage" default.
        input: upstream artifact path(s) (string or list).
        output: this stage's artifact path (globally unique when non-empty).
        gate: whether it is a gate (when True, approve=false pauses for manual approval).
        when: restricted condition expression (same semantics as YAML, evaluated by the engine).
        retry: number of retries on failure.
        on_error: failure policy (abort/continue/skip_dependents); None means it is left to
            `_build_dag` to fall back to the top-level default_on_error.

    Returns:
        the flow item dict (containing only explicitly declared keys; default keys are not written, and are handled by `_build_dag`).
    """
    if not str(name or "").strip():
        raise ValueError("stage is missing name")
    if not str(agent or "").strip():
        raise ValueError(f"stage '{name}' is missing agent")

    item: Dict[str, Any] = {
        "stage": str(name).strip(),
        "agent": str(agent).strip(),
    }
    if depends_on is not None:
        item["depends_on"] = depends_on
    if input is not None:
        item["input"] = input
    if output:
        item["output"] = str(output).strip()
    if gate:
        item["gate"] = True
    if when:
        item["when"] = str(when).strip()
    if retry:
        item["retry"] = int(retry)
    if on_error:
        item["on_error"] = str(on_error).strip()
    return item


def loop(
    name: str,
    body: Any,
    until: str,
    max_iterations: int = 5,
    on_error: Optional[str] = None,
) -> Dict[str, Any]:
    """Declare a runtime loop node (layer 2: subgraph loop).

    The loop body `body` is a set of already-declared stage names (a subgraph); when the engine executes it, it runs the entire body section
    once according to dependencies, then evaluates `until`; if not satisfied, it resets the stages in body and reruns,
    until satisfied or `max_iterations` is reached.

    Parameters:
        name: loop node name (unique; used for referencing by depends_on).
        body: loop body stage name(s) (string or list); must be non-empty and reference declared stages.
        until: exit condition expression (evaluated at runtime, reusing the when evaluator; supports
            `stage.field` references and `file(path)`/`contains(text, substr)`).
        max_iterations: maximum number of iterations (positive integer, to prevent infinite loops).
        on_error: failure policy (abort/continue/skip_dependents); None lets the engine
            fall back to the top-level default_on_error.

    Returns:
        the loop item dict (for Pipeline.add to append).

    Raises:
        ValueError: name/until is empty, body is empty, or max_iterations is not a positive integer.
    """
    loop_name = str(name or "").strip()
    if not loop_name:
        raise ValueError("loop is missing name")

    if body is None:
        body_list: List[str] = []
    elif isinstance(body, str):
        body_list = [body.strip()] if body.strip() else []
    elif isinstance(body, (list, tuple)):
        body_list = [str(b).strip() for b in body if str(b).strip()]
    else:
        raise ValueError(f"loop '{loop_name}' body must be a string or a list")
    if not body_list:
        raise ValueError(f"loop '{loop_name}' body cannot be empty")

    until_expr = str(until or "").strip()
    if not until_expr:
        raise ValueError(f"loop '{loop_name}' is missing the until exit condition")

    try:
        max_iter = int(max_iterations)
    except (TypeError, ValueError):
        raise ValueError(f"loop '{loop_name}' max_iterations must be a positive integer") from None
    if max_iter < 1:
        raise ValueError(f"loop '{loop_name}' max_iterations must be a positive integer")

    item: Dict[str, Any] = {
        "loop": loop_name,
        "body": body_list,
        "until": until_expr,
        "max_iterations": max_iter,
    }
    if on_error:
        item["on_error"] = str(on_error).strip()
    return item


class Pipeline:
    """Orchestration container: accumulates agents and flow declarations and exports a structure isomorphic with YAML.

    After the script finishes executing, the convention is to assign the `Pipeline` instance to the top-level variable `pipeline`,
    for orchestration_loader to read and export the structure.
    """

    def __init__(self) -> None:
        self._agents: List[Dict[str, Any]] = []
        self._flow: List[Dict[str, Any]] = []
        self._agent_names: set = set()
        self._stage_names: set = set()
        self._loop_names: set = set()
        self._spec_text: str = ""
        self._default_on_error: str = ""

    # ------------------------------------------------------------------
    # Declarations
    # ------------------------------------------------------------------
    def add(self, stage_item: Dict[str, Any]) -> "Pipeline":
        """Append a stage or loop node (constructed by `stage()` / `loop()`).

        - stage item: named by the `stage` field, with uniqueness validated.
        - loop item (layer 2): named by the `loop` field, with uniqueness validated; the
          stages referenced in body must already be declared.

        Returns self to support chaining.
        """
        if not isinstance(stage_item, dict):
            raise TypeError("add() requires the dict returned by stage()/loop()")
        if "loop" in stage_item:
            loop_name = str(stage_item.get("loop") or "").strip()
            if not loop_name:
                raise ValueError("loop item is missing the loop name")
            if loop_name in self._loop_names:
                raise ValueError(f"Duplicate loop name: {loop_name}")
            if loop_name in self._stage_names:
                raise ValueError(f"loop name conflicts with a stage name: {loop_name}")
            for b in stage_item.get("body") or []:
                if b not in self._stage_names:
                    raise ValueError(
                        f"loop '{loop_name}' body references an undeclared stage '{b}'"
                    )
            self._loop_names.add(loop_name)
            self._flow.append(stage_item)
            return self

        name = str(stage_item.get("stage") or "").strip()
        if name in self._stage_names:
            raise ValueError(f"Duplicate stage name: {name}")
        if name in self._loop_names:
            raise ValueError(f"stage name conflicts with a loop name: {name}")
        self._stage_names.add(name)
        self._flow.append(stage_item)
        return self

    def agent(self, name: str, **fields: Any) -> "Pipeline":
        """Declare an agent (corresponding to an item in YAML `agents`).

        Parameters:
            name: agent name (unique).
            **fields: the remaining agent fields (working_dir/task/llm_group/tool_group/
                node_id/proxy_node/quick_mode/restore_session/no_interaction_mode/
                access_acl/additional_args). Unknown fields are ignored and retained with a warning.
        """
        agent_name = str(name or "").strip()
        if not agent_name:
            raise ValueError("agent is missing name")
        if agent_name in self._agent_names:
            raise ValueError(f"Duplicate agent name: {agent_name}")
        self._agent_names.add(agent_name)
        item: Dict[str, Any] = {"name": agent_name}
        for key, value in fields.items():
            if key in _AGENT_KEYS and key != "name":
                item[key] = value
        self._agents.append(item)
        return self

    def spec(self, text: str) -> "Pipeline":
        """Set the pipeline background (corresponding to the YAML top-level `spec` field)."""
        self._spec_text = str(text or "")
        return self

    def default_on_error(self, mode: str) -> "Pipeline":
        """Set the top-level default failure policy (corresponding to the YAML top-level `default_on_error`)."""
        self._default_on_error = str(mode or "").strip()
        return self

    # ------------------------------------------------------------------
    # Export (for orchestration_loader to read)
    # ------------------------------------------------------------------
    @property
    def agents(self) -> List[Dict[str, Any]]:
        """List of agent definitions (isomorphic with YAML `agents`)."""
        return list(self._agents)

    @property
    def flow(self) -> List[Dict[str, Any]]:
        """List of stages (isomorphic with YAML `flow`)."""
        return list(self._flow)

    @property
    def spec_text(self) -> str:
        """Pipeline background text (corresponding to the YAML top-level `spec`)."""
        return self._spec_text

    @property
    def default_on_error_value(self) -> str:
        """Top-level default failure policy (corresponding to the YAML top-level `default_on_error`)."""
        return self._default_on_error

    def to_dict(self) -> Dict[str, Any]:
        """Export as a dict isomorphic with the parsed result of a YAML orchestration file.

        Returns:
            {"agents": [...], "flow": [...], "spec": str, "default_on_error": str}
            containing only non-empty optional fields (spec/default_on_error are not written when empty).
        """
        data: Dict[str, Any] = {
            "agents": list(self._agents),
            "flow": list(self._flow),
        }
        if self._spec_text:
            data["spec"] = self._spec_text
        if self._default_on_error:
            data["default_on_error"] = self._default_on_error
        return data
