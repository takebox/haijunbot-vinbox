# -*- coding: utf-8 -*-
"""pipeline_runner tool: a built-in multi-Agent orchestration execution engine (general infrastructure).

After parsing the orchestration file (containing the `agents` definitions and an optional `flow` order), according to the stages declared by `flow`
it builds a DAG (directed acyclic graph), uses a resident `hjb` Agent to schedule each stage in parallel, and through
`status_file` synchronously awaits completion of each stage, validates that artifacts are written to disk, and passes the previous stage's artifact paths into
the next stage, implementing automatic orchestration of multi-Agent pipelines such as "plan → generate → verify → gate".

Design orientation (see docs/design/ai-dark-factory-orchestration-engine.md for details):
- **Coordinate only, do not execute** (sw-controller mode): this tool does not write code or test; it is only responsible for
  scheduling and artifact passing based on dependencies; the specific stages/artifacts/gates are declared by the user's orchestration file.
- **Generality**: does not depend on any plugin business. Any plugin/user can use it to define their own multi-Agent
  pipeline; the dark factory is just one of its users.
- **DAG orchestration**: `flow` supports `depends_on`/`input` (multiple inputs)/`when` (condition)/
  `on_error` (failure strategy)/`retry` (retry); the parallelism `max_workers` defaults to 4.
- **Reuse existing mechanisms**: stage Agents are uniformly resident `hjb` Agents (no repository file locks, can run in parallel),
  and completion is awaited synchronously via `send_to_agent(wait=true, status_file=...)`.
- **Keep manual approval gates**: stages with `gate: true` stop after completion; by default `approve=false`,
  and manual confirmation is required before proceeding (not fully unattended).

The `flow` field in the orchestration file is optional; when there is no `flow`, this tool reports an error prompt (in this case it should be handled by
`@OrganizeAgents`, which is responsible for only creating agents; behavior is unchanged).
"""

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool
from haijunbot.haijunbot_tools.orchestration_loader import load_orchestration
from haijunbot.haijunbot_tools.pipeline_events import emit_remote
from haijunbot.haijunbot_tools.pipeline_events import get_event_bus
from haijunbot.haijunbot_tools.pipeline_events import is_local_pump_active
from haijunbot.haijunbot_utils.output import PrettyOutput

# Status file polling interval (seconds)
_POLL_INTERVAL = 2.0
# Default timeout per stage (seconds): 30 minutes
_DEFAULT_STAGE_TIMEOUT = 30 * 60
# Work artifact directory name (relative to working_dir, collected into the .haijunbot hidden directory for unified management)
_ARTIFACT_DIR = ".haijunbot/artifacts"
# Default parallelism
_DEFAULT_MAX_WORKERS = 4


class PipelineRunnerTool:
    """Built-in multi-Agent orchestration execution engine.

    Reads the orchestration file (agents + flow), parses flow into a DAG, and uses resident hjb Agents to
    schedule each stage in parallel, polls status_file to await completion, passes artifacts, and stops at gates.
    """

    name = "pipeline_runner"
    description = (
        "Built-in multi-Agent orchestration execution engine: reads the orchestration file (YAML or .flow Python DSL,"
        "containing agents + flow), and according to what flow declares"
        "builds a DAG from dependencies, uses resident hjb Agents to drive each stage in parallel, synchronously awaits completion of each stage,"
        "validates that artifacts are written to disk, passes the previous stage's artifact paths into the next stage, and implements automatic orchestration of multi-Agent pipelines."
        "Supports parallelism (max_workers defaults to 4), multiple inputs (input list), conditions (when), failure"
        "strategies (on_error: abort/continue/skip_dependents), and retries (retry). Gate stages"
        "(gate: true) stop after completion; by default approve=false, and manual approval confirmation is required before proceeding."
        "Note: orchestration with flow does not support cross-node; node_id/proxy_node in agent definitions will be"
        "rejected (stages must share a filesystem); to create Agents across nodes, please use @OrganizeAgents."
        "The .flow DSL also supports the runtime loop primitive loop(name, body, until, max_iterations):"
        "body is a subgraph composed of declared stage names; the whole segment is rerun until until is satisfied or the limit is reached; until "
        "can use the whitelisted functions file(path) (reads the artifact body within work_dir) and contains(text, substr)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "orchestration_file": {
                "type": "string",
                "description": "Orchestration file path (.yaml/.yml or .flow, containing agents definitions and optional flow order)",
            },
            "working_dir": {
                "type": "string",
                "description": "Working directory (defaults to the current directory); artifacts are created in .haijunbot/artifacts/ within it",
            },
            "approve": {
                "type": "boolean",
                "description": "Whether gate stages have obtained manual approval (default false, manual confirmation required)",
            },
            "max_workers": {
                "type": "integer",
                "description": "Parallelism upper limit (default 4), limiting the number of stage Agents executing simultaneously",
            },
            "dry_run": {
                "type": "boolean",
                "description": (
                    "Only rehearse the orchestration plan (default false): parse + validate + topological sort, output the"
                    "DAG to be executed (stages/dependencies/parallel batches/artifacts/gates/conditions/retries/failure strategies),"
                    "without creating Agents or dispatching tasks. Used to validate dynamically generated orchestration files."
                ),
            },
        },
        "required": ["orchestration_file"],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Drive a multi-Agent pipeline (DAG scheduling) according to the orchestration file flow."""
        args = args or {}
        orchestration_file = str(args.get("orchestration_file") or "").strip()
        working_dir = str(args.get("working_dir") or "").strip() or "."
        approve = bool(args.get("approve", False))
        dry_run = bool(args.get("dry_run", False))
        max_workers = int(
            args.get("max_workers", _DEFAULT_MAX_WORKERS) or _DEFAULT_MAX_WORKERS
        )

        # 1. Validate parameters
        if not orchestration_file:
            return self._error("Missing required parameter orchestration_file (orchestration YAML path)")

        orch_path = Path(orchestration_file)
        if not orch_path.exists() or not orch_path.is_file():
            return self._error(f"Orchestration file does not exist: {orchestration_file}")

        work_dir = Path(working_dir).resolve()
        if not work_dir.is_dir():
            return self._error(f"Working directory does not exist: {working_dir}")

        if max_workers < 1:
            max_workers = 1

        # 2. Read the orchestration file (unified loader: dispatch YAML / Python DSL by suffix)
        try:
            orch = load_orchestration(orch_path)
        except Exception as e:  # pylint: disable=broad-except
            return self._error(f"Failed to parse orchestration file: {e}")

        agents = orch.get("agents") or []
        flow = orch.get("flow") or []
        if not agents:
            return self._error("Orchestration file is missing agents definitions")
        if not flow:
            return self._error(
                "Orchestration file is missing the flow field (stage order). When there is no flow, please use @OrganizeAgents "
                "to only create agents; this tool only drives pipelines that have a flow."
            )

        agents_by_name = {a.get("name"): a for a in agents if a.get("name")}

        # Orchestration with flow does not support cross-node: inter-stage artifact paths and status_file are all based on work_dir,
        # and filesystems cannot be shared across nodes. node_id/proxy_node in agent definitions will be silently ignored;
        # here we explicitly raise an error rather than silently swallowing it, to avoid users mistakenly thinking the orchestration really executed across nodes.
        for _agent in agents:
            if _agent.get("node_id") or _agent.get("proxy_node"):
                return self._error(
                    "Orchestration with flow does not support cross-node: node_id/proxy_node in agent definitions "
                    "will be ignored, because stages must share a filesystem (artifacts and status files are all based on work_dir)."
                    "To create Agents across nodes, please use @OrganizeAgents (orchestration without flow)."
                )

        default_on_error = str(orch.get("default_on_error") or "abort").strip()

        # 3. Initialize the artifact directory (isolated by pipeline_id, to avoid conflicts when multiple pipelines share a directory)
        pipeline_id = self._make_pipeline_id(orchestration_file)
        if dry_run:
            # dry-run only rehearses without writing to disk; using a common directory for display is sufficient
            artifact_dir = work_dir / _ARTIFACT_DIR
        else:
            artifact_dir = work_dir / _ARTIFACT_DIR / pipeline_id
        try:
            artifact_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:  # pylint: disable=broad-except
            return self._error(f"Unable to create artifact directory {artifact_dir}: {e}")

        # 4. Build the DAG (parse + validate + cycle detection)
        dag_build = self._build_dag(flow, agents_by_name, default_on_error)
        if not dag_build["success"]:
            return self._error(dag_build["error"])
        nodes = dag_build["nodes"]

        # Read the top-level spec field of the orchestration file as background for each stage (optional; not injected if absent)
        inline_spec = orch.get("spec")
        spec_summary = (
            str(inline_spec).strip()
            if isinstance(inline_spec, str) and str(inline_spec).strip()
            else ""
        )

        # 4.5 dry-run: only rehearse the orchestration plan, without creating Agents or dispatching tasks
        if dry_run:
            return self._dry_run_plan(
                nodes=nodes,
                agents_by_name=agents_by_name,
                default_on_error=default_on_error,
                max_workers=max_workers,
                approve=approve,
                artifact_dir=artifact_dir,
            )

        # 4.6 Broadcast the start event (for frontend visualization); pipeline_id has already been generated in step 3
        self._emit(
            pipeline_id,
            "pipeline_start",
            orchestration_file=str(orch_path),
            working_dir=str(work_dir),
            max_workers=max_workers,
            approve=approve,
            default_on_error=default_on_error,
            nodes=[self._node_event_payload(n) for n in nodes],
        )

        # 5. Create resident hjb Agents (one per stage)
        agent_created = self._create_stage_agents(
            nodes, agents_by_name, work_dir, pipeline_id
        )
        if not agent_created["success"]:
            # Clean up the partially created Agents to avoid leftovers
            self._cleanup_agents(agent_created.get("agent_map") or {})
            self._emit(
                pipeline_id, "pipeline_done", success=False, final_status="failed"
            )
            return self._error(agent_created["error"])
        agent_map = agent_created["agent_map"]

        # 5.1 Broadcast the stage → agent_id mapping
        self._emit(pipeline_id, "pipeline_agents", agent_map=dict(agent_map))

        # 6. Schedule execution (parallel DAG)
        return self._schedule(
            nodes=nodes,
            agent_map=agent_map,
            agents_by_name=agents_by_name,
            work_dir=work_dir,
            artifact_dir=artifact_dir,
            spec_summary=spec_summary,
            approve=approve,
            max_workers=max_workers,
            pipeline_id=pipeline_id,
        )

    # ------------------------------------------------------------------
    # Progress events (for frontend visualization, pure side effects, does not affect execution semantics)
    # ------------------------------------------------------------------
    def _emit(self, pipeline_id: str, event_type: str, **fields: Any) -> None:
        """Write a pipeline progress event to the global event bus.

        Pure side effect: any exception is swallowed and never affects pipeline execution.

        pipeline_runner may run inside the web_gateway process (e.g. the frontend's "Run pipeline"),
        or it may run inside an Agent process (e.g. a user-dialogue Agent calling this tool). The event pump
        (which drains and broadcasts to the frontend) only exists in the web_gateway process, therefore:
        - if the local event pump is active (this process is web_gateway): only write to the local in-process bus;
        - otherwise (Agent process): besides writing to the local bus, also report to the master gateway over HTTP,
          where the gateway-side /api/pipeline-events writes to the gateway process bus, so that it can be read by the event pump.
        """
        try:
            event: Dict[str, Any] = {"pipeline_id": pipeline_id, "type": event_type}
            event.update(fields)
            get_event_bus().emit(event)
            if not is_local_pump_active():
                emit_remote(event)
        except Exception:  # pylint: disable=broad-except
            pass

    @staticmethod
    def _node_event_payload(n: Dict[str, Any]) -> Dict[str, Any]:
        """Convert DAG nodes into event payloads (including loop composite node fields, for frontend visualization)."""
        payload: Dict[str, Any] = {
            "stage": n["stage"],
            "agent": n["agent"],
            "depends_on": list(n["depends_on"]),
            "input": list(n["input"]),
            "output": n["output"],
            "gate": n["gate"],
            "when": n["when"],
            "retry": n["retry"],
            "on_error": n["on_error"],
        }
        if n.get("kind") == "loop":
            payload["kind"] = "loop"
            payload["until"] = n.get("until", "")
            payload["max_iterations"] = n.get("max_iterations", 0)
            payload["body_stages"] = [
                b["stage"] for b in n.get("body_stages", [])
            ]
        return payload

    def _emit_approval(
        self,
        pipeline_id: str,
        action: str,
        approver: str = "",
        note: str = "",
        gate_stage: str = "",
        approval_path: str = "",
    ) -> None:
        """Broadcast a gate manual approval event (pipeline_approval).

        Pure side effect (same as _emit): any exception is swallowed and never affects pipeline execution.
        Event fields: pipeline_id / type=pipeline_approval / action / approver /
        note / gate_stage / approval_path / ts (timestamp).
        action values: pending (gate stopped awaiting approval), approve, reject, retry.
        """
        self._emit(
            pipeline_id,
            "pipeline_approval",
            action=action,
            approver=str(approver or ""),
            note=str(note or ""),
            gate_stage=str(gate_stage or ""),
            approval_path=str(approval_path or ""),
            ts=time.time(),
        )

    def record_approval(
        self,
        pipeline_id: str,
        action: str,
        approver: str = "",
        note: str = "",
    ) -> Dict[str, Any]:
        """Record a gate manual approval decision and broadcast an approval event (for frontend/API calls).

        After a gate stops, a human makes an approve/reject/retry decision on the gate stage
        decision. This method is only responsible for **recording the decision and broadcasting an audit event** (who, when, action, note),
        and does not directly drive the pipeline to continue -- approval/retry is accomplished by the caller rerunning the pipeline with approve=true,
        while rejection terminates the pipeline. Pure recording and event broadcasting: idempotent, no side effects, does not raise exceptions.

        Args:
            pipeline_id: target pipeline ID (the pipeline_id in the gate_blocked event).
            action: approval action, must be one of APPROVAL_ACTIONS.
            approver: the approver (display_name/username/user_id, may be empty).
            note: approval note (may be empty).

        Returns:
            {"success": True, "data": {...}} or {"success": False, "error": str}
        """
        try:
            from haijunbot.haijunbot_tools.pipeline_events import APPROVAL_ACTIONS

            action = str(action or "").strip().lower()
            if action not in APPROVAL_ACTIONS:
                return {
                    "success": False,
                    "error": (
                        f"Invalid approval action '{action}', must be one of {', '.join(APPROVAL_ACTIONS)}"
                    ),
                }
            if not str(pipeline_id or "").strip():
                return {"success": False, "error": "Missing required parameter pipeline_id"}
            self._emit_approval(
                pipeline_id,
                action=action,
                approver=approver,
                note=note,
            )
            return {
                "success": True,
                "data": {
                    "pipeline_id": str(pipeline_id).strip(),
                    "action": action,
                    "approver": str(approver or ""),
                    "note": str(note or ""),
                    "ts": time.time(),
                },
            }
        except Exception as e:  # pylint: disable=broad-except
            return {"success": False, "error": f"Failed to record approval: {e}"}

    @staticmethod
    def _make_pipeline_id(orchestration_file: str) -> str:
        """Generate a stable and unique pipeline_id: <orchestration file name>-<timestamp>-<short random>."""
        stem = Path(orchestration_file).stem or "pipeline"
        return f"{stem}-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    # ------------------------------------------------------------------
    # DAG construction
    # ------------------------------------------------------------------
    def _build_dag(
        self,
        flow: List[Dict[str, Any]],
        agents_by_name: Dict[str, Any],
        default_on_error: str = "abort",
    ) -> Dict[str, Any]:
        """Parse flow into a DAG node list, complete depends_on/input, and perform cycle detection.

        - `depends_on` defaults to the previous stage (linear compatibility).
        - a single-string `input` is automatically converted to a single-element list.
        - `on_error` defaults back to the orchestration file's top-level `default_on_error`, then defaults to abort.
        - validate agent references, duplicate stage names, output uniqueness, and cycle detection.

        Returns:
            {"success": True, "nodes": [...]} or {"success": False, "error": str}
        """
        if default_on_error not in ("abort", "continue", "skip_dependents"):
            default_on_error = "abort"

        # First expand loop items into a plain stage list, and record loop membership.
        # A loop item looks like {"loop": name, "body": [stage names...], "until": expr,
        #             "max_iterations": n, "on_error": ...}
        flat_flow: List[Dict[str, Any]] = []
        loop_defs: Dict[str, Dict[str, Any]] = {}
        stage_to_loop: Dict[str, str] = {}
        for idx, item in enumerate(flow):
            if not isinstance(item, dict):
                return {"success": False, "error": f"flow item {idx + 1} is not an object"}
            loop_name = str(item.get("loop") or "").strip()
            if not loop_name:
                flat_flow.append(item)
                continue
            if loop_name in loop_defs:
                return {
                    "success": False,
                    "error": f"Duplicate loop name in flow: {loop_name}",
                }
            body = item.get("body")
            if isinstance(body, str):
                body = [body]
            body = [str(b).strip() for b in (body or []) if str(b).strip()]
            if not body:
                return {
                    "success": False,
                    "error": f"The body of loop '{loop_name}' cannot be empty",
                }
            until = str(item.get("until") or "").strip()
            if not until:
                return {
                    "success": False,
                    "error": f"loop '{loop_name}' is missing the until condition",
                }
            try:
                max_iterations = int(item.get("max_iterations", 5))
            except (TypeError, ValueError):
                max_iterations = 0
            if max_iterations < 1:
                return {
                    "success": False,
                    "error": f"max_iterations of loop '{loop_name}' must be a positive integer",
                }
            loop_defs[loop_name] = {
                "until": until,
                "max_iterations": max_iterations,
                "body": body,
                "on_error": item.get("on_error"),
            }

        nodes: List[Dict[str, Any]] = []
        stage_names: List[str] = []
        output_owners: Dict[str, str] = {}
        for idx, stage in enumerate(flat_flow):
            stage_name = str(stage.get("stage") or f"stage_{idx}").strip()
            if not stage_name:
                return {"success": False, "error": f"flow item {idx + 1} is missing a stage name"}
            if stage_name in stage_names:
                return {
                    "success": False,
                    "error": f"Duplicate stage name in flow: {stage_name}",
                }
            if stage_name in loop_defs:
                return {
                    "success": False,
                    "error": f"Stage name '{stage_name}' conflicts with a loop name",
                }
            stage_names.append(stage_name)

            agent_name = str(stage.get("agent") or "").strip()
            if agent_name not in agents_by_name:
                return {
                    "success": False,
                    "error": f"flow stage '{stage_name}' references an undefined agent '{agent_name}'",
                }

            # depends_on defaults to the previous stage
            depends_on = stage.get("depends_on")
            if depends_on is None:
                depends_on = [stage_names[idx - 1]] if idx > 0 else []
            elif isinstance(depends_on, str):
                depends_on = [depends_on]
            depends_on = [str(d).strip() for d in (depends_on or [])]
            for d in depends_on:
                if d not in stage_names:
                    return {
                        "success": False,
                        "error": f"flow stage '{stage_name}' depends on a nonexistent stage '{d}'",
                    }

            # a single-string input is automatically converted to a single-element list
            input_ref = stage.get("input")
            if input_ref is None:
                input_list: List[str] = []
            elif isinstance(input_ref, str):
                input_list = [input_ref.strip()] if input_ref.strip() else []
            elif isinstance(input_ref, list):
                input_list = [str(i).strip() for i in input_ref if str(i).strip()]
            else:
                input_list = []

            on_error = str(stage.get("on_error") or default_on_error).strip()
            if on_error not in ("abort", "continue", "skip_dependents"):
                on_error = default_on_error

            output = str(stage.get("output") or "").strip()
            if output:
                if output in output_owners:
                    return {
                        "success": False,
                        "error": (
                            f"flow stage '{stage_name}' and '{output_owners[output]}' "
                            f"declare the same artifact path '{output}' (artifacts must be unique)"
                        ),
                    }
                output_owners[output] = stage_name

            nodes.append(
                {
                    "stage": stage_name,
                    "agent": agent_name,
                    "depends_on": depends_on,
                    "input": input_list,
                    "output": output,
                    "gate": bool(stage.get("gate", False)),
                    "when": str(stage.get("when") or "").strip() or None,
                    "retry": int(stage.get("retry", 0) or 0),
                    "on_error": on_error,
                }
            )
            for lname, ldef in loop_defs.items():
                if stage_name in ldef["body"]:
                    stage_to_loop[stage_name] = lname

        if loop_defs:
            result = self._fold_loops_into_dag(nodes, loop_defs, stage_to_loop)
            if not result["success"]:
                return result
            nodes = result["nodes"]

        # Cycle detection (Kahn topological sort; returns None if there is a cycle)
        if self._topo_sort(nodes) is None:
            return {
                "success": False,
                "error": "flow dependencies contain a cycle and cannot be executed (please check depends_on)",
            }
        return {"success": True, "nodes": nodes}

    def _fold_loops_into_dag(
        self,
        nodes: List[Dict[str, Any]],
        loop_defs: Dict[str, Dict[str, Any]],
        stage_to_loop: Dict[str, str],
    ) -> Dict[str, Any]:
        """Fold body stages into loop composite nodes, returning a list of top-level nodes without body stages.

        - stages inside body are removed from the top level and retained as the loop node's ``body_stages``.
        - loop node ``depends_on`` = the union of dependencies of body stages on external (non-body) stages.
        - if other top-level stages depend on a stage inside body, they are rewritten to depend on the corresponding loop node.
        - mutual dependencies between stages inside body are allowed (executed sequentially within the loop), but body stages
          must not depend on stages outside body (otherwise the rerun semantics are unclear), nor span across loops.
        """
        node_by_stage = {n["stage"]: n for n in nodes}

        # Validate that body references exist and do not span across loops
        for lname, ldef in loop_defs.items():
            for b in ldef["body"]:
                if b not in node_by_stage:
                    return {
                        "success": False,
                        "error": f"The body of loop '{lname}' references a nonexistent stage '{b}'",
                    }
                owner = stage_to_loop.get(b)
                if owner != lname:
                    return {
                        "success": False,
                        "error": (
                            f"stage '{b}' in the body of loop '{lname}' "
                            f"does not belong to this loop (it may be referenced by multiple loops)"
                        ),
                    }

        folded: List[Dict[str, Any]] = []
        for lname, ldef in loop_defs.items():
            body = ldef["body"]
            body_set = set(body)
            external_deps: List[str] = []
            for b in body:
                for d in node_by_stage[b]["depends_on"]:
                    if d in body_set:
                        continue
                    if d in stage_to_loop:
                        return {
                            "success": False,
                            "error": (
                                f"body stage '{b}' of loop '{lname}' "
                                f"depends on stage '{d}' of another loop '{stage_to_loop[d]}'"
                            ),
                        }
                    if d not in external_deps:
                        external_deps.append(d)
            body_stages = [node_by_stage[b] for b in body]
            # The depends_on of body stages keeps only references within body (used when executing inside the loop)
            for bs in body_stages:
                bs["depends_on"] = [d for d in bs["depends_on"] if d in body_set]
            loop_node = {
                "stage": lname,
                "kind": "loop",
                "agent": None,
                "depends_on": external_deps,
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": str(ldef.get("on_error") or "abort").strip()
                if str(ldef.get("on_error") or "abort").strip()
                in ("abort", "continue", "skip_dependents")
                else "abort",
                "until": ldef["until"],
                "max_iterations": ldef["max_iterations"],
                "body_stages": body_stages,
            }
            folded.append(loop_node)

        # Top-level stages: remove body stages, rewrite dependencies to loop nodes
        stage_to_loop_node = {b: lname for lname, ldef in loop_defs.items() for b in ldef["body"]}
        for n in nodes:
            if n["stage"] in stage_to_loop_node:
                continue
            new_deps: List[str] = []
            for d in n["depends_on"]:
                mapped = stage_to_loop_node.get(d, d)
                if mapped not in new_deps:
                    new_deps.append(mapped)
            n["depends_on"] = new_deps
            folded.append(n)

        return {"success": True, "nodes": folded}

    def _topo_sort(self, nodes: List[Dict[str, Any]]) -> Optional[List[Dict[str, Any]]]:
        """Kahn topological sort; returns None if there is a cycle."""
        by_stage = {n["stage"]: n for n in nodes}
        indegree = {n["stage"]: len(n["depends_on"]) for n in nodes}
        dependents: Dict[str, List[str]] = {n["stage"]: [] for n in nodes}
        for n in nodes:
            for d in n["depends_on"]:
                dependents[d].append(n["stage"])

        queue = [s for s, deg in indegree.items() if deg == 0]
        order: List[str] = []
        while queue:
            s = queue.pop(0)
            order.append(s)
            for child in dependents[s]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(order) != len(nodes):
            return None
        return [by_stage[s] for s in order]

    # ------------------------------------------------------------------
    # dry-run rehearsal
    # ------------------------------------------------------------------
    def _dry_run_plan(
        self,
        nodes: List[Dict[str, Any]],
        agents_by_name: Dict[str, Any],
        default_on_error: str,
        max_workers: int,
        approve: bool,
        artifact_dir: Path,
    ) -> Dict[str, Any]:
        """Only rehearse the orchestration plan: output the DAG execution plan, without creating Agents or dispatching tasks.

        Used to validate dynamically generated orchestration files: parse + validate + topological sort + batching,
        printing stages/dependencies/parallel batches/artifacts/gates/conditions/retries/failure strategies.
        """
        lines: List[str] = []
        lines.append("🧪 dry-run: orchestration plan rehearsal (does not create Agents or dispatch tasks)")
        lines.append(f"  Artifact directory: {artifact_dir}")
        lines.append(f"  Parallelism upper limit: {max_workers}")
        lines.append(f"  Top-level default_on_error: {default_on_error}")
        lines.append(f"  Gate approve: {approve}")
        lines.append(f"  Total stages: {len(nodes)}")

        # Topological sort (_build_dag already did cycle detection; here we take the order once more)
        order = self._topo_sort(nodes)
        if order is None:
            return self._error("dry-run failed: orchestration contains a cycle and cannot be topologically sorted")

        # Batch by "dependency level": each batch is a set of stages that can execute in parallel
        batches = self._plan_batches(nodes)
        lines.append("")
        lines.append("📋 Execution plan (by parallel batch):")
        for i, batch in enumerate(batches, 1):
            parallel = len(batch) > 1
            tag = "parallel" if parallel else "serial"
            lines.append(f"  Batch {i} [{tag}] ({len(batch)} stages):")
            for n in batch:
                lines.append(self._format_stage_plan(n, agents_by_name))

        # Stage list (topological order)
        lines.append("")
        lines.append("🔗 Topological order: " + " → ".join(n["stage"] for n in order))

        gate_stages = [n["stage"] for n in nodes if n["gate"]]
        if gate_stages:
            lines.append(
                f"🚧 Gate stages: {', '.join(gate_stages)} (halt after completion and wait for manual approval)"
            )

        return {"success": True, "stdout": "\n".join(lines), "stderr": ""}

    def _plan_batches(self, nodes: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Batch nodes by dependency level (same batch can run in parallel), used for dry-run display.

        Consistent with the ready batch semantics of `_schedule`: each batch = nodes whose dependencies are all completed in earlier batches.
        """
        by_stage = {n["stage"]: n for n in nodes}
        remaining = {n["stage"]: set(n["depends_on"]) for n in nodes}
        done: set = set()
        batches: List[List[Dict[str, Any]]] = []
        while remaining:
            ready = [s for s, deps in remaining.items() if deps.issubset(done)]
            if not ready:
                break  # _build_dag already intercepts cycles; this is only defensive
            batch = [by_stage[s] for s in ready]
            batches.append(batch)
            for s in ready:
                done.add(s)
                del remaining[s]
        return batches

    def _format_stage_plan(
        self, node: Dict[str, Any], agents_by_name: Dict[str, Any]
    ) -> str:
        """Format the plan line for a single stage."""
        agent_def = agents_by_name.get(node["agent"], {})
        working_dir = agent_def.get("working_dir") or "."
        parts = [f"    - {node['stage']} (agent={node['agent']}, dir={working_dir})"]
        if node["depends_on"]:
            parts.append(f"deps={','.join(node['depends_on'])}")
        if node["input"]:
            parts.append(f"input={','.join(node['input'])}")
        parts.append(f"output={node['output'] or '(none)'}")
        if node["gate"]:
            parts.append("gate")
        if node["when"]:
            parts.append(f"when={node['when']}")
        if node["retry"]:
            parts.append(f"retry={node['retry']}")
        parts.append(f"on_error={node['on_error']}")
        return "  ".join(parts)

    # ------------------------------------------------------------------
    # Persistent Agent creation
    # ------------------------------------------------------------------
    def _iter_agent_nodes(
        self, nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Expand the node list into "nodes that need an Agent created": regular stages + body stages of loops.

        A loop composite node itself has no agent; its body_stages are the nodes that actually execute tasks.
        """
        out: List[Dict[str, Any]] = []
        for n in nodes:
            if n.get("kind") == "loop":
                out.extend(n.get("body_stages", []))
            else:
                out.append(n)
        return out

    def _create_stage_agents(
        self,
        nodes: List[Dict[str, Any]],
        agents_by_name: Dict[str, Any],
        work_dir: Path,
        pipeline_id: str = "",
    ) -> Dict[str, Any]:
        """Create a persistent hjb Agent for each stage (type: agent).

        Returns:
            {"success": True, "agent_map": {stage: agent_id}} or an error
        """
        gw = GatewayManagerTool()
        agent_map: Dict[str, str] = {}
        for node in self._iter_agent_nodes(nodes):
            stage_name = node["stage"]
            agent_def = agents_by_name[node["agent"]]
            working_dir = str(agent_def.get("working_dir") or str(work_dir))
            agent_id, last_error = self._create_agent_with_retry(
                gw, stage_name, working_dir, pipeline_id=pipeline_id
            )
            if not agent_id:
                return {
                    "success": False,
                    "error": (
                        f"Failed to create persistent Agent for stage [{stage_name}] (retried): "
                        f"{last_error}"
                    ),
                    "agent_map": agent_map,
                }
            # Record created Agents first, for cleanup on failure (including ready-timeout scenarios)
            agent_map[stage_name] = agent_id
            # After creating an Agent the process has just started and the web-gateway port is not yet listening; dispatching a task immediately returns 502;
            # Here we wait for the Agent to be ready (able to respond to /status) before entering scheduling.
            ready, ready_err = self._wait_agent_ready(gw, agent_id)
            if not ready:
                return {
                    "success": False,
                    "error": (
                        f"Timed out waiting for persistent Agent of stage [{stage_name}] to be ready: {ready_err}"
                    ),
                    "agent_map": agent_map,
                }
            PrettyOutput.auto_print(
                f"  🛠 Persistent Agent for stage [{stage_name}] ready: {agent_id}"
            )
        return {"success": True, "agent_map": agent_map}

    def _wait_agent_ready(
        self, gw: Any, agent_id: str, timeout: float = 60.0, poll_interval: float = 0.5
    ) -> tuple:
        """Wait for the Agent's web-gateway to be ready (able to respond to /status requests).

        After creating an Agent the process has just started and the port is not yet listening; gateway proxy requests return 502;
        Here we poll /api/agent/{id}/status until the gateway proxy succeeds (non-502) which is considered ready.

        Returns:
            (ok, error): ok=True means ready, otherwise False with an error message.
        """
        # The test stub (FakeGW) may not implement _request_gateway; treat as ready directly
        request_gateway = getattr(gw, "_request_gateway", None)
        if request_gateway is None:
            return True, ""
        deadline = time.time() + timeout
        last_err = ""
        while time.time() < deadline:
            result = request_gateway(
                method="GET",
                path=f"/api/agent/{agent_id}/status",
                error_prefix=f"Failed to query status of agent {agent_id}",
            )
            if result["success"]:
                return True, ""
            last_err = str(result.get("error") or "")
            time.sleep(poll_interval)
        return False, f"Timed out waiting for Agent to be ready (>{int(timeout)} seconds): {last_err}"

    def _create_agent_with_retry(
        self,
        gw: Any,
        stage_name: str,
        working_dir: str,
        pipeline_id: str = "",
        max_attempts: int = 3,
    ) -> tuple:
        """Create a persistent Agent, retrying on failure (with increasing interval).

        Returns:
            (agent_id, error): a non-empty agent_id means success; on failure agent_id is an empty string,
            and error is the last error message.
        """
        last_error = ""
        # Prefix the Agent name with pipeline_id to avoid name conflicts when multiple pipelines create same-named Agents in the same directory
        agent_name = (
            f"df_{pipeline_id}_{stage_name}" if pipeline_id else f"df_{stage_name}"
        )
        for attempt in range(1, max_attempts + 1):
            create_result = gw._create_agent(
                agent_type="agent",
                working_dir=working_dir,
                name=agent_name,
            )
            if create_result.get("success"):
                try:
                    agent_info = json.loads(create_result["stdout"])
                    agent_id = str(agent_info.get("agent_id") or "")
                except (json.JSONDecodeError, AttributeError, TypeError):
                    agent_id = ""
                if agent_id:
                    if attempt > 1:
                        PrettyOutput.auto_print(
                            f"  ♻️ Stage [{stage_name}] created Agent successfully on attempt {attempt}"
                        )
                    return agent_id, ""
                last_error = "creation succeeded but could not obtain agent_id"
            else:
                last_error = str(create_result.get("stderr") or "unknown error")
            if attempt < max_attempts:
                PrettyOutput.auto_print(
                    f"  ⚠️ Failed to create Agent for stage [{stage_name}]"
                    f" (attempt {attempt}/{max_attempts}): {last_error},"
                    f"retrying in {attempt} seconds"
                )
                time.sleep(attempt)
        return "", last_error

    # ------------------------------------------------------------------
    # Single-stage execution
    # ------------------------------------------------------------------
    def _run_stage(
        self,
        node: Dict[str, Any],
        agent_id: str,
        agents_by_name: Dict[str, Any],
        work_dir: Path,
        artifact_dir: Path,
        spec_summary: str,
        approve: bool,
    ) -> Dict[str, Any]:
        """Execute a single stage: assemble task message → send_to_agent(wait=true, status_file) → validate output.

        Returns:
            {
              "stage": str, "status": "completed"|"failed",
              "output": str, "result": {...}, "error": str,
              "gate_blocked": bool, "approval_path": str,
            }
        """
        stage_name = node["stage"]
        agent_def = agents_by_name[node["agent"]]
        task_desc = str(agent_def.get("task") or agent_def.get("task_desc") or "")
        output = node["output"]
        input_list = node["input"]

        suffix = str(node.get("_status_suffix") or "").strip()
        status_file = artifact_dir / (
            f"{stage_name}.{suffix}.status" if suffix else f"{stage_name}.status"
        )
        # Clear old status_file (to support retries)
        if status_file.exists():
            try:
                status_file.unlink()
            except OSError:
                pass

        # Assemble task message
        message = self._build_stage_message(
            task_desc=task_desc,
            stage=stage_name,
            input_list=input_list,
            output=output,
            spec_summary=spec_summary,
            status_file=str(status_file),
        )

        PrettyOutput.auto_print(
            f"▶ Stage [{stage_name}] agent={node['agent']} started (send_to_agent wait)"
        )

        gw = GatewayManagerTool()
        send_result = gw._send_to_agent(
            agent_id=agent_id,
            message=message,
            wait=True,
            status_file=str(status_file),
        )

        if not send_result["success"]:
            return {
                "stage": stage_name,
                "status": "failed",
                "output": output,
                "result": {},
                "error": send_result["stderr"] or "stage Agent task failed",
                "gate_blocked": False,
                "approval_path": "",
            }

        # Read status_file content as the structured result (for reference by when expressions)
        result = self._read_status(status_file)

        # Validate output written to disk
        if output:
            output_path = work_dir / output
            if not output_path.exists():
                return {
                    "stage": stage_name,
                    "status": "failed",
                    "output": output,
                    "result": result,
                    "error": f"stage [{stage_name}] declared output {output} was not written to disk",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            # If the output is JSON, read its fields and merge them into result (status_file fields take precedence),
            # for downstream when expressions to reference the output content (e.g. report.pass_rate).
            artifact_json = self._read_artifact_json(output_path)
            if artifact_json:
                merged = dict(artifact_json)
                merged.update(result)
                result = merged

        # Gate: halt and wait for manual approval
        if node["gate"]:
            if not approve:
                approval_path = work_dir / (output or f"{stage_name}.approval.md")
                return {
                    "stage": stage_name,
                    "status": "completed",
                    "output": output,
                    "result": result,
                    "error": "",
                    "gate_blocked": True,
                    "approval_path": str(approval_path),
                }
            return {
                "stage": stage_name,
                "status": "completed",
                "output": output,
                "result": result,
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        return {
            "stage": stage_name,
            "status": "completed",
            "output": output,
            "result": result,
            "error": "",
            "gate_blocked": False,
            "approval_path": "",
        }

    def _run_loop(
        self,
        node: Dict[str, Any],
        agent_map: Dict[str, str],
        agents_by_name: Dict[str, Any],
        work_dir: Path,
        artifact_dir: Path,
        spec_summary: str,
        approve: bool,
        pipeline_id: str = "",
    ) -> Dict[str, Any]:
        """Execute a loop composite node: rerun body_stages as a whole until until is satisfied or the limit is reached.

        Stages within body execute in their internal dependency order; until is evaluated at the end of each iteration (can read output files).
        Returns a stage_result isomorphic to `_run_stage` (stage=loop name).
        """
        loop_name = node["stage"]
        body_stages: List[Dict[str, Any]] = node.get("body_stages", [])
        until = node.get("until", "")
        max_iterations = int(node.get("max_iterations", 5) or 5)
        order = self._topo_sort(body_stages) or body_stages

        last_results: Dict[str, Dict[str, Any]] = {}
        for iteration in range(1, max_iterations + 1):
            self._emit(
                pipeline_id,
                "loop_iteration",
                stage=loop_name,
                iteration=iteration,
                max_iterations=max_iterations,
            )
            PrettyOutput.auto_print(
                f"🔁 loop [{loop_name}] iteration {iteration}/{max_iterations}"
            )
            iter_results: Dict[str, Dict[str, Any]] = {}
            for bs in order:
                bs_name = bs["stage"]
                agent_id = agent_map.get(bs_name, "")
                # Use a separate status_file per iteration to avoid interference from the previous iteration's result
                bs_run = dict(bs)
                bs_run["_status_suffix"] = f"iter{iteration}"
                stage_result = self._run_stage(
                    bs_run,
                    agent_id,
                    agents_by_name,
                    work_dir,
                    artifact_dir,
                    spec_summary,
                    approve,
                )
                iter_results[bs_name] = stage_result
                self._emit(
                    pipeline_id,
                    "stage_update",
                    stage=bs_name,
                    status=stage_result["status"],
                    agent_id=agent_id,
                    output=bs["output"],
                    artifact=stage_result.get("output", ""),
                    loop=loop_name,
                    iteration=iteration,
                )
                if stage_result["status"] != "completed":
                    # A stage within body failed: decide according to the loop's on_error
                    return {
                        "stage": loop_name,
                        "status": "failed",
                        "output": "",
                        "result": {"iterations": iteration},
                        "error": (
                            f"loop [{loop_name}] iteration {iteration} stage "
                            f"[{bs_name}] failed: {stage_result.get('error', '')}"
                        ),
                        "gate_blocked": False,
                        "approval_path": "",
                    }
            last_results = iter_results
            ok, err = self._eval_until(until, iter_results, work_dir)
            if ok:
                PrettyOutput.auto_print(
                    f"🔁 loop [{loop_name}] iteration {iteration} satisfied until, ending loop"
                )
                return {
                    "stage": loop_name,
                    "status": "completed",
                    "output": "",
                    "result": {
                        "iterations": iteration,
                        "until_satisfied": True,
                    },
                    "error": "",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            if err:
                PrettyOutput.auto_print(f"⚠ loop [{loop_name}] until evaluation error: {err}")

        # Reached the limit without satisfying until: treat as complete (no more infinite loop), but mark as unsatisfied
        PrettyOutput.auto_print(
            f"🔁 loop [{loop_name}] reached maximum iterations {max_iterations}, until not satisfied"
        )
        return {
            "stage": loop_name,
            "status": "completed",
            "output": "",
            "result": {
                "iterations": max_iterations,
                "until_satisfied": False,
                "body_results": {
                    k: {"status": v.get("status")} for k, v in last_results.items()
                },
            },
            "error": "",
            "gate_blocked": False,
            "approval_path": "",
        }

    def _build_stage_message(
        self,
        task_desc: str,
        stage: str,
        input_list: List[str],
        output: str,
        spec_summary: str,
        status_file: str,
    ) -> str:
        """Assemble this stage's task message (including the completion instruction to write status_file)."""
        parts: List[str] = []
        task = task_desc.strip()
        if task:
            parts.append(task)
        if spec_summary:
            parts.append(f"Pipeline background:\n{spec_summary}")
        if input_list:
            parts.append("Inputs to this stage:\n" + "\n".join(f"- {i}" for i in input_list))
        parts.append(
            f"After completing this stage's responsibilities, write the output to {output or '(no output required for this stage)'}."
            f"When done, write the result to the status file {status_file}, with JSON content:"
            f'{{"status": "completed", "output": "<output path>"}};'
            f'if it fails write {{"status": "failed", "error": "<reason>"}}.'
        )
        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Parallel scheduling
    # ------------------------------------------------------------------
    def _schedule(
        self,
        nodes: List[Dict[str, Any]],
        agent_map: Dict[str, str],
        agents_by_name: Dict[str, Any],
        work_dir: Path,
        artifact_dir: Path,
        spec_summary: str,
        approve: bool,
        max_workers: int,
        pipeline_id: str = "",
    ) -> Dict[str, Any]:
        """Parallel DAG scheduling: each round collects ready nodes whose dependencies are satisfied, executed concurrently via a thread pool.

        Handles when (conditional skip), on_error (failure policy), retry (retry), and gates.
        """
        state: Dict[str, str] = {n["stage"]: "pending" for n in nodes}
        results: Dict[str, Dict[str, Any]] = {}
        stdout_lines: List[str] = []
        gate_blocked_stage: Optional[str] = None
        gate_approval_path = ""

        def _deps_satisfied(n: Dict[str, Any]) -> bool:
            for d in n["depends_on"]:
                if state.get(d) != "completed":
                    return False
            return True

        def _deps_blocked(n: Dict[str, Any]) -> bool:
            # If any dependency failed/skipped, the node cannot execute
            return any(state.get(d) in ("failed", "skipped") for d in n["depends_on"])

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while True:
                # Nodes whose dependencies are blocked are skipped directly
                for n in nodes:
                    if state[n["stage"]] == "pending" and _deps_blocked(n):
                        state[n["stage"]] = "skipped"
                        results[n["stage"]] = {
                            "stage": n["stage"],
                            "status": "skipped",
                            "output": n["output"],
                            "result": {},
                            "error": "dependency failed/skipped, this stage was skipped",
                        }
                        stdout_lines.append(f"  ⏭ Stage [{n['stage']}] skipped due to dependency failure")
                        self._emit(
                            pipeline_id,
                            "stage_update",
                            stage=n["stage"],
                            status="skipped",
                            agent_id=agent_map.get(n["stage"], ""),
                            output=n["output"],
                            error="dependency failed/skipped, this stage was skipped",
                        )

                # Collect ready nodes
                ready = [
                    n
                    for n in nodes
                    if state[n["stage"]] == "pending"
                    and _deps_satisfied(n)
                    and not _deps_blocked(n)
                ]

                if not ready:
                    # No ready nodes: check whether all are finished
                    if all(
                        s in ("completed", "failed", "skipped") for s in state.values()
                    ):
                        break
                    # Has pending but no ready and no running: deadlock protection
                    if all(s != "running" for s in state.values()):
                        break
                    continue

                # when condition evaluation (nodes not satisfied are marked skipped)
                effective_ready: List[Dict[str, Any]] = []
                for n in ready:
                    if n["when"]:
                        ok, err = self._eval_when(n["when"], results)
                        if not ok:
                            state[n["stage"]] = "skipped"
                            results[n["stage"]] = {
                                "stage": n["stage"],
                                "status": "skipped",
                                "output": n["output"],
                                "result": {},
                                "error": (
                                    f"when condition not satisfied: {n['when']}"
                                    + (f"({err})" if err else "")
                                ),
                            }
                            stdout_lines.append(
                                f"  ⏭ Stage [{n['stage']}] skipped because when condition not satisfied"
                            )
                            self._emit(
                                pipeline_id,
                                "stage_update",
                                stage=n["stage"],
                                status="skipped",
                                agent_id=agent_map.get(n["stage"], ""),
                                output=n["output"],
                                error=f"when condition not satisfied: {n['when']}",
                            )
                            continue
                    effective_ready.append(n)

                if not effective_ready:
                    continue

                # Execute ready nodes concurrently
                futures = {}
                for n in effective_ready:
                    state[n["stage"]] = "running"
                    agent_id = agent_map.get(n["stage"], "")
                    self._emit(
                        pipeline_id,
                        "stage_update",
                        stage=n["stage"],
                        status="running",
                        agent_id=agent_id,
                        output=n["output"],
                    )
                    if n.get("kind") == "loop":
                        futures[
                            pool.submit(
                                self._run_loop,
                                n,
                                agent_map,
                                agents_by_name,
                                work_dir,
                                artifact_dir,
                                spec_summary,
                                approve,
                                pipeline_id,
                            )
                        ] = n
                    else:
                        futures[
                            pool.submit(
                                self._run_stage,
                                n,
                                agent_id,
                                agents_by_name,
                                work_dir,
                                artifact_dir,
                                spec_summary,
                                approve,
                            )
                        ] = n

                for fut in as_completed(futures):
                    n = futures[fut]
                    try:
                        stage_result = fut.result()
                    except Exception as e:  # pylint: disable=broad-except
                        stage_result = {
                            "stage": n["stage"],
                            "status": "failed",
                            "output": n["output"],
                            "result": {},
                            "error": f"stage execution exception: {e}",
                            "gate_blocked": False,
                            "approval_path": "",
                        }
                    self._handle_stage_result(
                        n=n,
                        stage_result=stage_result,
                        state=state,
                        results=results,
                        stdout_lines=stdout_lines,
                        work_dir=work_dir,
                        pipeline_id=pipeline_id,
                    )
                    # Gate halt
                    if stage_result.get("gate_blocked"):
                        gate_blocked_stage = n["stage"]
                        gate_approval_path = stage_result.get("approval_path", "")
                    # abort termination (only when the stage ultimately fails; no termination during retries)
                    if state[n["stage"]] == "failed" and n["on_error"] == "abort":
                        self._emit(
                            pipeline_id,
                            "pipeline_done",
                            success=False,
                            final_status="aborted",
                            failed_stage=n["stage"],
                        )
                        # Clean up created persistent Agents to avoid leftovers
                        self._cleanup_agents(agent_map)
                        return self._abort_result(
                            stage_name=n["stage"],
                            error=str(stage_result.get("error", "") or ""),
                            stdout_lines=stdout_lines,
                            artifact_dir=artifact_dir,
                        )

        # All scheduling complete
        if gate_blocked_stage:
            stdout_lines.append(
                f"  ⛔ Gate stage [{gate_blocked_stage}] produced an approval report: {gate_approval_path}"
            )
            stdout_lines.append(
                "  ⛔ Awaiting manual approval: please confirm the approval report, then rerun gate confirmation with approve=true."
            )
            self._emit(
                pipeline_id,
                "pipeline_done",
                success=True,
                final_status="gate_blocked",
                gate_stage=gate_blocked_stage,
                approval_path=gate_approval_path,
            )
            # Broadcast an "awaiting approval" event for the frontend to show an approval overlay (approve/reject/retry)
            self._emit_approval(
                pipeline_id,
                action="pending",
                gate_stage=gate_blocked_stage,
                approval_path=str(gate_approval_path or ""),
            )
            return {
                "success": True,
                "stdout": "\n".join(stdout_lines),
                "stderr": "",
            }

        # Check whether there are any failed stages
        failed = [s for s, st in state.items() if st == "failed"]
        if failed:
            errs = [results[s].get("error", "") for s in failed if results.get(s)]
            stdout_lines.append("❌ Pipeline has failed stages")
            self._emit(
                pipeline_id,
                "pipeline_done",
                success=False,
                final_status="failed",
                failed_stages=failed,
            )
            # Clean up created persistent Agents to avoid leftovers
            self._cleanup_agents(agent_map)
            return {
                "success": False,
                "stdout": "\n".join(stdout_lines),
                "stderr": (
                    "Failed stages: "
                    + ", ".join(failed)
                    + ";"
                    + ";".join(e for e in errs if e)
                ),
            }

        stdout_lines.append("🏁 All pipeline stages complete")
        self._emit(
            pipeline_id,
            "pipeline_done",
            success=True,
            final_status="completed",
        )
        return {"success": True, "stdout": "\n".join(stdout_lines), "stderr": ""}

    def _handle_stage_result(
        self,
        n: Dict[str, Any],
        stage_result: Dict[str, Any],
        state: Dict[str, str],
        results: Dict[str, Dict[str, Any]],
        stdout_lines: List[str],
        work_dir: Path,
        pipeline_id: str = "",
    ) -> None:
        """Handle the execution result of a single stage (including retry)."""
        stage_name = n["stage"]
        status = stage_result["status"]

        if status == "completed":
            state[stage_name] = "completed"
            results[stage_name] = stage_result
            if stage_result.get("output"):
                stdout_lines.append(
                    f"  ✅ Stage [{stage_name}] complete, output: {stage_result['output']}"
                )
            else:
                stdout_lines.append(f"  ✅ Stage [{stage_name}] complete")
            self._emit(
                pipeline_id,
                "stage_update",
                stage=stage_name,
                status="completed",
                output=n["output"],
                artifact=stage_result.get("output", ""),
            )
            return

        # failed: handle retry
        retry = n["retry"]
        if retry > 0:
            retry_count = results.get(stage_name, {}).get("_retry_count", 0) + 1
            if retry_count <= retry:
                stage_result["_retry_count"] = retry_count
                results[stage_name] = stage_result
                state[stage_name] = "pending"
                stdout_lines.append(
                    f"  🔁 Stage [{stage_name}] failed, retry {retry_count}/{retry}"
                )
                self._emit(
                    pipeline_id,
                    "stage_update",
                    stage=stage_name,
                    status="retry",
                    output=n["output"],
                    retry_count=retry_count,
                    retry_max=retry,
                    error=str(stage_result.get("error", "") or ""),
                )
                return
            # Retries exhausted, handle as failure
            state[stage_name] = "failed"
            results[stage_name] = stage_result
            stdout_lines.append(
                f"  ❌ Stage [{stage_name}] failed (retries exhausted): "
                f"{stage_result.get('error', '')}"
            )
            self._emit(
                pipeline_id,
                "stage_update",
                stage=stage_name,
                status="failed",
                output=n["output"],
                error=str(stage_result.get("error", "") or ""),
            )
            return

        # No retry, fail directly
        state[stage_name] = "failed"
        results[stage_name] = stage_result
        stdout_lines.append(
            f"  ❌ Stage [{stage_name}] failed: {stage_result.get('error', '')}"
        )
        self._emit(
            pipeline_id,
            "stage_update",
            stage=stage_name,
            status="failed",
            output=n["output"],
            error=str(stage_result.get("error", "") or ""),
        )
        # on_error=skip_dependents/continue: fail but do not terminate,
        # nodes depending on it will be skipped by _deps_blocked in the next round.

    def _cleanup_agents(self, agent_map: Dict[str, str]) -> None:
        """Clean up created persistent Agents when the pipeline fails/terminates (best-effort, idempotent).

        Iterate over agent_map to delete the Agents created for each stage, avoiding leftover processes consuming resources.
        - Idempotent: repeatedly deleting an Agent that no longer exists does not error;
        - Best-effort: any exception/failure is swallowed and never affects the pipeline result;
        - Only Agents are deleted, not outputs (artifacts are retained).
        Whether to clean up is controlled by the config is_pipeline_cleanup_on_failure().
        """
        try:
            from haijunbot.haijunbot_utils.config import is_pipeline_cleanup_on_failure

            if not is_pipeline_cleanup_on_failure():
                return
        except Exception:  # pylint: disable=broad-except
            return

        agent_ids = [str(aid) for aid in agent_map.values() if aid]
        if not agent_ids:
            return
        try:
            gw = GatewayManagerTool()
            # The test stub (FakeGW) may not implement _delete_agent; skip directly
            delete_agent = getattr(gw, "_delete_agent", None)
            if delete_agent is None:
                return
            delete_agent(agent_id=agent_ids)
        except Exception:  # pylint: disable=broad-except
            pass

    def _abort_result(
        self,
        stage_name: str,
        error: str,
        stdout_lines: List[str],
        artifact_dir: Path,
    ) -> Dict[str, Any]:
        """Construct an abort termination result."""
        stdout_lines.append(
            f"⛔ Pipeline terminated because stage [{stage_name}] failed (on_error=abort)"
        )
        return {
            "success": False,
            "stdout": "\n".join(stdout_lines),
            "stderr": (
                f"Stage [{stage_name}] failed: {error}."
                f"Outputs retained at {artifact_dir} for troubleshooting."
            ),
        }

    # ------------------------------------------------------------------
    # when restricted expression parsing
    # ------------------------------------------------------------------
    def _eval_when(self, expr: str, results: Dict[str, Dict[str, Any]]) -> tuple:
        """Evaluate a restricted expression (whitelist, no eval of arbitrary code).

        Supported syntax: `stage.field` references a status_file field of an upstream stage;
        comparisons `==`/`!=`/`>=`/`<=`/`>`/`<`; logic `&&`/`||`/`!`; literal numbers/strings/booleans.

        Returns:
            (ok, error): ok=True means the condition is satisfied, otherwise False with an error message
        """
        try:
            substituted = self._substitute_refs(expr, results)
            value = self._eval_boolean(substituted)
            return bool(value), ""
        except Exception as e:  # pylint: disable=broad-except
            return False, f"when expression parsing failed: {e}"

    def _eval_until(
        self,
        expr: str,
        results: Dict[str, Dict[str, Any]],
        work_dir: Optional[Path] = None,
    ) -> tuple:
        """Evaluate a loop's until condition (adds file()/contains() on top of _eval_when).

        Whitelisted functions:
        - `file("relative output path")`: reads the body of an output file under work_dir (restricted to within work_dir, ≤1MB,
          returns empty string if absent). **Lazy evaluation**: reads only during comparison/contains, and does not splice the file body
          into the expression string (to avoid large files slowing parsing).
        - `contains(text, substr)`: whether text contains substr (case-sensitive).

        Returns:
            (ok, error): ok=True means the condition is satisfied.
        """
        try:
            substituted = self._substitute_refs(expr, results)
            value = self._eval_boolean(substituted, work_dir=work_dir)
            return bool(value), ""
        except Exception as e:  # pylint: disable=broad-except
            return False, f"until expression parsing failed: {e}"

    def _read_artifact_text(
        self, rel_path: str, work_dir: Optional[Path], max_bytes: int = 1024 * 1024
    ) -> str:
        """Read the body of an output file under work_dir; restricted to within the directory and by size, returns empty string on exception."""
        if work_dir is None or not rel_path:
            return ""
        try:
            base = Path(work_dir).resolve()
            target = (base / rel_path).resolve()
            # Prevent escape: the target must be located within work_dir
            if base != target and base not in target.parents:
                return ""
            if not target.is_file():
                return ""
            with open(target, "rb") as fh:
                data = fh.read(max_bytes)
            return data.decode("utf-8", errors="replace")
        except (OSError, ValueError):
            return ""

    def _substitute_refs(self, expr: str, results: Dict[str, Dict[str, Any]]) -> str:
        """Replace `stage.field` references with the field value from the corresponding stage result (as a string).

        Skip content inside quotes (e.g. the path literal in `file("report.md")` should not be treated as a stage reference).
        """

        def _lookup(match: "re.Match") -> str:
            stage_name = match.group(1)
            field = match.group(2)
            stage_result = results.get(stage_name, {})
            result_data = stage_result.get("result") or {}
            value = result_data.get(field)
            if value is None:
                return "None"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            return json.dumps(str(value), ensure_ascii=False)

        # First split by quotes; only replace segments outside quotes
        segments = re.split(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')', expr)
        for i in range(0, len(segments), 2):
            segments[i] = re.sub(
                r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)",
                _lookup,
                segments[i],
            )
        return "".join(segments)

    def _eval_boolean(self, expr: str, work_dir: Optional[Path] = None) -> Any:
        """Safely evaluate a boolean expression (only comparisons, logic, and literals; no eval of arbitrary code)."""
        expr = expr.strip()
        # Handle ||
        parts = self._split_top_level(expr, "||")
        if len(parts) > 1:
            return any(self._eval_boolean(p, work_dir=work_dir) for p in parts)
        # Handle &&
        parts = self._split_top_level(expr, "&&")
        if len(parts) > 1:
            return all(self._eval_boolean(p, work_dir=work_dir) for p in parts)
        e = parts[0].strip()
        if e.startswith("!"):
            return not self._eval_boolean(e[1:], work_dir=work_dir)
        if e.startswith("(") and e.endswith(")"):
            return self._eval_boolean(e[1:-1], work_dir=work_dir)
        # Whitelisted function contains(text, substr)
        contains_val = self._eval_contains(e, work_dir=work_dir)
        if contains_val is not None:
            return contains_val
        # Comparison expression
        return self._eval_comparison(e, work_dir=work_dir)

    def _eval_contains(self, e: str, work_dir: Optional[Path] = None) -> Optional[bool]:
        """Evaluate `contains(text, substr)`; returns None if not in this form."""
        e = e.strip()
        if not e.startswith("contains(") or not e.endswith(")"):
            return None
        inner = e[len("contains(") : -1]
        args = self._split_top_level(inner, ",")
        if len(args) != 2:
            raise ValueError(f"contains() requires 2 arguments: {e}")
        text = self._coerce(args[0].strip(), work_dir=work_dir)
        sub = self._coerce(args[1].strip(), work_dir=work_dir)
        return str(sub) in str(text)

    def _split_top_level(self, expr: str, op: str) -> List[str]:
        """Split by top-level operator (ignoring those inside parentheses and quotes)."""
        parts: List[str] = []
        depth = 0
        in_quote: Optional[str] = None
        current = ""
        i = 0
        while i < len(expr):
            ch = expr[i]
            if in_quote:
                current += ch
                if ch == in_quote:
                    in_quote = None
                i += 1
                continue
            if ch in ("'", '"'):
                in_quote = ch
                current += ch
                i += 1
                continue
            if ch == "(":
                depth += 1
                current += ch
                i += 1
                continue
            if ch == ")":
                depth -= 1
                current += ch
                i += 1
                continue
            if depth == 0 and expr[i : i + len(op)] == op:
                parts.append(current)
                current = ""
                i += len(op)
                continue
            current += ch
            i += 1
        parts.append(current)
        return parts

    def _find_top_level_op(self, expr: str, op: str) -> int:
        """Find the operator position at the top level (ignoring inside parentheses and quotes); returns -1 if not found."""
        depth = 0
        in_quote: Optional[str] = None
        i = 0
        while i < len(expr):
            ch = expr[i]
            if in_quote:
                if ch == in_quote:
                    in_quote = None
                i += 1
                continue
            if ch in ("'", '"'):
                in_quote = ch
                i += 1
                continue
            if ch == "(":
                depth += 1
                i += 1
                continue
            if ch == ")":
                depth -= 1
                i += 1
                continue
            if depth == 0 and expr[i : i + len(op)] == op:
                return i
            i += 1
        return -1

    def _eval_comparison(self, e: str, work_dir: Optional[Path] = None) -> bool:
        """Evaluate a single comparison expression (or boolean/numeric literal)."""
        e = e.strip()
        if e in ("true", "True"):
            return True
        if e in ("false", "False"):
            return False
        if e == "None":
            return False
        # Numeric/string comparison
        for op in ("==", "!=", ">=", "<=", ">", "<"):
            idx = self._find_top_level_op(e, op)
            if idx >= 0:
                left_s = e[:idx].strip()
                right_s = e[idx + len(op) :].strip()
                left = self._coerce(left_s, work_dir=work_dir)
                right = self._coerce(right_s, work_dir=work_dir)
                if op == "==":
                    return left == right
                if op == "!=":
                    return left != right
                if op == ">=":
                    return left >= right
                if op == "<=":
                    return left <= right
                if op == ">":
                    return left > right
                if op == "<":
                    return left < right
        # No comparison operator: try numeric/boolean literal
        num = self._coerce(e, work_dir=work_dir)
        if isinstance(num, bool):
            return num
        if isinstance(num, (int, float)):
            return num != 0
        return bool(num)

    def _coerce(self, s: str, work_dir: Optional[Path] = None) -> Any:
        """Convert a literal string to a number/boolean/string (for comparison).

        Additionally supports the whitelisted function `file("relative output path")`: lazily reads the output body under work_dir.
        """
        s = s.strip()
        if s in ("true", "True"):
            return True
        if s in ("false", "False"):
            return False
        if s == "None":
            return None
        # Whitelisted function file("...")
        file_match = re.fullmatch(r'file\(\s*"([^"]*)"\s*\)', s)
        if file_match:
            return self._read_artifact_text(file_match.group(1), work_dir)
        # Quoted string
        if (s.startswith('"') and s.endswith('"')) or (
            s.startswith("'") and s.endswith("'")
        ):
            return s[1:-1]
        # Numeric
        try:
            if "." in s:
                return float(s)
            return int(s)
        except ValueError:
            return s

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------
    def _read_status(self, status_file: Path) -> Dict[str, Any]:
        """Read the contents of status_file (JSON); return an empty dict on failure."""
        try:
            if status_file.exists():
                data = json.loads(status_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (json.JSONDecodeError, OSError):
            pass
        return {}

    def _read_artifact_json(self, artifact_path: Path) -> Dict[str, Any]:
        """If the artifact is a JSON object, read its contents; otherwise return an empty dict.

        Only accepts JSON whose top level is a dict, for when expressions to reference artifact fields.
        """
        try:
            if artifact_path.suffix.lower() != ".json":
                return {}
            data = json.loads(artifact_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        return {}

    def _error(self, msg: str) -> Dict[str, Any]:
        """Construct an error return."""
        return {"success": False, "stdout": "", "stderr": msg}
