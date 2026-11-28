# -*- coding: utf-8 -*-
"""pipeline_runner (built-in multi-Agent orchestration execution engine) tests.

Coverage:
1. DAG construction: linear compatibility (depends_on default = previous stage), input single string to list,
   parallel dependencies, duplicate stage names, undefined agent, cycle detection;
2. when restricted expression parsing: comparison, logic, referencing upstream fields, invalid expressions;
3. Parallel scheduling: execute only when dependencies are ready, three on_error strategies (abort/continue/skip_dependents),
   retry, gate blocking.

Does not depend on real gateway/agent: mocks GatewayManagerTool and status_file.
"""

import json
from pathlib import Path

import pytest

from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool
from haijunbot.haijunbot_tools.pipeline_runner import PipelineRunnerTool


@pytest.fixture
def tool():
    return PipelineRunnerTool()


# ---------------------------------------------------------------------------
# DAG construction
# ---------------------------------------------------------------------------
class TestBuildDag:
    def test_linear_backward_compat(self, tool):
        """depends_on default = previous stage (old linear orchestration zero changes)."""
        flow = [
            {"stage": "planner", "agent": "a1", "output": "plan.md"},
            {"stage": "generator", "agent": "a2", "input": "plan.md"},
            {"stage": "validator", "agent": "a3", "input": "plan.md"},
        ]
        agents = {"a1": {}, "a2": {}, "a3": {}}
        r = tool._build_dag(flow, agents)
        assert r["success"] is True
        nodes = r["nodes"]
        assert nodes[0]["depends_on"] == []
        assert nodes[1]["depends_on"] == ["planner"]
        assert nodes[2]["depends_on"] == ["generator"]

    def test_input_string_to_list(self, tool):
        """input single string automatically converted to single-element list."""
        flow = [{"stage": "s1", "agent": "a1", "input": ".df/plan.md"}]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["nodes"][0]["input"] == [".df/plan.md"]

    def test_input_list_preserved(self, tool):
        """input multi-input list preserved."""
        flow = [
            {"stage": "s1", "agent": "a1", "input": ["a.md", "b.md"]},
        ]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["nodes"][0]["input"] == ["a.md", "b.md"]

    def test_parallel_dependencies(self, tool):
        """Parallel DAG: multiple nodes depend on same upstream."""
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"stage": "s2", "agent": "a2", "depends_on": ["s1"]},
            {"stage": "s3", "agent": "a3", "depends_on": ["s1"]},
            {"stage": "s4", "agent": "a4", "depends_on": ["s2", "s3"]},
        ]
        agents = {"a1": {}, "a2": {}, "a3": {}, "a4": {}}
        r = tool._build_dag(flow, agents)
        assert r["success"] is True
        nodes = {n["stage"]: n for n in r["nodes"]}
        assert nodes["s1"]["depends_on"] == []
        assert nodes["s2"]["depends_on"] == ["s1"]
        assert nodes["s3"]["depends_on"] == ["s1"]
        assert sorted(nodes["s4"]["depends_on"]) == ["s2", "s3"]

    def test_duplicate_stage_name(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"stage": "s1", "agent": "a2"},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is False
        assert "Duplicate" in r["error"]

    def test_undefined_agent(self, tool):
        flow = [{"stage": "s1", "agent": "ghost"}]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["success"] is False
        assert "undefined" in r["error"]

    def test_dependency_not_exist(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"stage": "s2", "agent": "a2", "depends_on": ["nope"]},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is False
        assert "nonexistent" in r["error"]

    def test_cycle_detected(self, tool):
        """Cycle detection: Kahn topological sort detects cycle."""
        # Directly construct parsed nodes (bypassing depends_on forward reference validation), verify _topo_sort cycle detection
        nodes = [
            {
                "stage": "y",
                "agent": "a1",
                "depends_on": ["x"],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "x",
                "agent": "a2",
                "depends_on": ["y"],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
        ]
        assert tool._topo_sort(nodes) is None

    def test_topo_sort_order(self, tool):
        """Topological sort: dependencies come first."""
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"stage": "s2", "agent": "a2", "depends_on": ["s1"]},
            {"stage": "s3", "agent": "a3", "depends_on": ["s1"]},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}, "a3": {}})
        order = tool._topo_sort(r["nodes"])
        assert order is not None
        assert order[0]["stage"] == "s1"
        assert set(order[1]["stage"]) == {"s2", "s3"} or {
            order[1]["stage"],
            order[2]["stage"],
        } == {"s2", "s3"}

    def test_default_on_error(self, tool):
        """on_error default falls back to orchestration file top-level default_on_error."""
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"stage": "s2", "agent": "a2", "on_error": "continue"},
        ]
        r = tool._build_dag(
            flow, {"a1": {}, "a2": {}}, default_on_error="skip_dependents"
        )
        nodes = {n["stage"]: n for n in r["nodes"]}
        assert nodes["s1"]["on_error"] == "skip_dependents"  # Falls back to global default
        assert nodes["s2"]["on_error"] == "continue"  # Stage-level override

    def test_default_on_error_invalid_falls_back_abort(self, tool):
        """Invalid default_on_error falls back to abort."""
        flow = [{"stage": "s1", "agent": "a1"}]
        r = tool._build_dag(flow, {"a1": {}}, default_on_error="bogus")
        assert r["nodes"][0]["on_error"] == "abort"

    def test_duplicate_output_rejected(self, tool):
        """Multiple stages declaring same artifact path -> error."""
        flow = [
            {"stage": "s1", "agent": "a1", "output": ".df/x.md"},
            {"stage": "s2", "agent": "a2", "output": ".df/x.md"},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is False
        assert "unique" in r["error"] or "same" in r["error"]

    def test_unique_output_ok(self, tool):
        """Different artifact paths pass normally."""
        flow = [
            {"stage": "s1", "agent": "a1", "output": ".df/a.md"},
            {"stage": "s2", "agent": "a2", "output": ".df/b.md"},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is True


# ---------------------------------------------------------------------------
# loop folded into DAG
# ---------------------------------------------------------------------------
class TestBuildDagLoop:
    def test_loop_folds_body_stages(self, tool):
        """Stages in body folded into loop node, no longer appear separately at top level."""
        flow = [
            {"stage": "setup", "agent": "a1", "output": ".df/setup.md"},
            {"stage": "write", "agent": "a2", "depends_on": ["setup"]},
            {"stage": "check", "agent": "a3", "depends_on": ["write"]},
            {
                "loop": "refine",
                "body": ["write", "check"],
                "until": 'contains(file("check.md"), "OK")',
                "max_iterations": 3,
            },
        ]
        agents = {"a1": {}, "a2": {}, "a3": {}}
        r = tool._build_dag(flow, agents)
        assert r["success"] is True
        stages = {n["stage"] for n in r["nodes"]}
        assert stages == {"setup", "refine"}
        loop_node = next(n for n in r["nodes"] if n["stage"] == "refine")
        assert loop_node["kind"] == "loop"
        assert loop_node["depends_on"] == ["setup"]
        assert loop_node["until"] == 'contains(file("check.md"), "OK")'
        assert loop_node["max_iterations"] == 3
        assert [b["stage"] for b in loop_node["body_stages"]] == ["write", "check"]

    def test_loop_body_internal_dep_kept(self, tool):
        """Dependencies between stages in body preserved within body_stages."""
        flow = [
            {"stage": "write", "agent": "a1"},
            {"stage": "check", "agent": "a2", "depends_on": ["write"]},
            {"loop": "L", "body": ["write", "check"], "until": "x", "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        loop_node = next(n for n in r["nodes"] if n["stage"] == "L")
        body = {b["stage"]: b for b in loop_node["body_stages"]}
        assert body["write"]["depends_on"] == []
        assert body["check"]["depends_on"] == ["write"]

    def test_downstream_rewritten_to_loop(self, tool):
        """Top-level stage depends on stage in body -> rewritten to depend on loop node."""
        flow = [
            {"stage": "write", "agent": "a1"},
            {"stage": "check", "agent": "a2", "depends_on": ["write"]},
            {"loop": "L", "body": ["write", "check"], "until": "x", "max_iterations": 2},
            {"stage": "publish", "agent": "a3", "depends_on": ["check"]},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}, "a3": {}})
        assert r["success"] is True
        pub = next(n for n in r["nodes"] if n["stage"] == "publish")
        assert pub["depends_on"] == ["L"]

    def test_body_unknown_stage(self, tool):
        flow = [{"loop": "L", "body": ["ghost"], "until": "x", "max_iterations": 2}]
        r = tool._build_dag(flow, {})
        assert r["success"] is False
        assert "nonexistent" in r["error"]

    def test_body_stage_depends_outside_rejected(self, tool):
        """Stage in body depends on stage outside body -> loop node inherits that external dependency."""
        flow = [
            {"stage": "setup", "agent": "a1"},
            {"stage": "write", "agent": "a2", "depends_on": ["setup"]},
            {"loop": "L", "body": ["write"], "until": "x", "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is True
        loop_node = next(n for n in r["nodes"] if n["stage"] == "L")
        assert loop_node["depends_on"] == ["setup"]

    def test_body_stage_depends_other_loop_rejected(self, tool):
        """Stage in body depends on stage of another loop -> error."""
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"loop": "L1", "body": ["s1"], "until": "x", "max_iterations": 2},
            {"stage": "s2", "agent": "a2", "depends_on": ["s1"]},
            {"loop": "L2", "body": ["s2"], "until": "y", "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is False
        assert "other loop" in r["error"]

    def test_loop_name_conflicts_with_stage(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"loop": "s1", "body": ["s1"], "until": "x", "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["success"] is False
        assert "conflict" in r["error"] or "duplicate" in r["error"]

    def test_duplicate_loop_name(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"loop": "L", "body": ["s1"], "until": "x", "max_iterations": 2},
            {"loop": "L", "body": ["s1"], "until": "y", "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["success"] is False
        assert "Duplicate" in r["error"]

    def test_loop_missing_until(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"loop": "L", "body": ["s1"], "max_iterations": 2},
        ]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["success"] is False
        assert "until" in r["error"]

    def test_loop_bad_max_iterations(self, tool):
        flow = [
            {"stage": "s1", "agent": "a1"},
            {"loop": "L", "body": ["s1"], "until": "x", "max_iterations": 0},
        ]
        r = tool._build_dag(flow, {"a1": {}})
        assert r["success"] is False
        assert "max_iterations" in r["error"]

    def test_no_loop_output_unchanged(self, tool):
        """When there is no loop, node fields are identical to before changes (no kind or other extra fields)."""
        flow = [
            {"stage": "s1", "agent": "a1", "output": ".df/a.md"},
            {"stage": "s2", "agent": "a2", "depends_on": ["s1"]},
        ]
        r = tool._build_dag(flow, {"a1": {}, "a2": {}})
        assert r["success"] is True
        for n in r["nodes"]:
            assert set(n.keys()) == {
                "stage",
                "agent",
                "depends_on",
                "input",
                "output",
                "gate",
                "when",
                "retry",
                "on_error",
            }


# ---------------------------------------------------------------------------
# when restricted expression parsing
# ---------------------------------------------------------------------------
class TestEvalWhen:
    def _results(self):
        return {
            "prev": {"result": {"status": "completed", "score": 5, "ok": True}},
        }

    def test_eq(self, tool):
        assert tool._eval_when('prev.status == "completed"', self._results())[0] is True
        assert tool._eval_when('prev.status == "failed"', self._results())[0] is False

    def test_ne(self, tool):
        assert tool._eval_when('prev.status != "failed"', self._results())[0] is True

    def test_numeric_compare(self, tool):
        assert tool._eval_when("prev.score >= 5", self._results())[0] is True
        assert tool._eval_when("prev.score > 5", self._results())[0] is False
        assert tool._eval_when("prev.score < 10", self._results())[0] is True

    def test_and_or(self, tool):
        assert (
            tool._eval_when(
                'prev.score >= 5 && prev.status != "failed"', self._results()
            )[0]
            is True
        )
        assert (
            tool._eval_when(
                'prev.score < 5 || prev.status == "completed"', self._results()
            )[0]
            is True
        )

    def test_not(self, tool):
        assert tool._eval_when("!false", self._results())[0] is True
        assert tool._eval_when("!true", self._results())[0] is False

    def test_boolean_field(self, tool):
        assert tool._eval_when("prev.ok", self._results())[0] is True

    def test_invalid_expr(self, tool):
        ok, err = tool._eval_when("prev.score >", self._results())
        assert ok is False
        assert err


# ---------------------------------------------------------------------------
# Parallel scheduling (mock _run_stage)
# ---------------------------------------------------------------------------
class TestSchedule:
    def _nodes(self):
        return [
            {
                "stage": "s1",
                "agent": "a1",
                "depends_on": [],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "s2",
                "agent": "a2",
                "depends_on": ["s1"],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
        ]

    def _base_kwargs(self, tool, nodes):
        return dict(
            nodes=nodes,
            agent_map={n["stage"]: f"id_{n['stage']}" for n in nodes},
            agents_by_name={"a1": {}, "a2": {}},
            work_dir=Path("."),
            artifact_dir=Path(".df"),
            spec_summary="",
            approve=False,
            max_workers=4,
        )

    def test_all_completed(self, tool, monkeypatch):
        calls = []

        def fake_run_stage(
            node,
            agent_id,
            agents_by_name,
            work_dir,
            artifact_dir,
            spec_summary,
            approve,
        ):
            calls.append(node["stage"])
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is True
        assert calls[0] == "s1"  # s1 executes first
        assert set(calls) == {"s1", "s2"}

    def test_abort_on_failure(self, tool, monkeypatch):
        """on_error=abort: abort immediately on any failure."""

        def fake_run_stage(node, *args, **kwargs):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "failed",
                    "output": "",
                    "result": {},
                    "error": "boom",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is False
        assert "s1" in r["stderr"]

    def test_continue_on_failure(self, tool, monkeypatch):
        """on_error=continue: fail but do not abort, dependent nodes are skipped."""
        nodes = self._nodes()
        nodes[0]["on_error"] = "continue"
        nodes[1]["on_error"] = "continue"

        def fake_run_stage(node, *args, **kwargs):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "failed",
                    "output": "",
                    "result": {},
                    "error": "boom",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            raise AssertionError("s2 should not execute (dependency failed)")

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is False
        assert "s1" in r["stderr"]

    def test_skip_dependents(self, tool, monkeypatch):
        """on_error=skip_dependents: dependent nodes are skipped after failure."""
        nodes = self._nodes()
        nodes[0]["on_error"] = "skip_dependents"
        nodes[1]["on_error"] = "skip_dependents"

        def fake_run_stage(node, *args, **kwargs):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "failed",
                    "output": "",
                    "result": {},
                    "error": "boom",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            raise AssertionError("s2 should not execute (dependency failed)")

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is False

    def test_retry(self, tool, monkeypatch):
        """retry: retry after failure, complete if retry succeeds."""
        nodes = self._nodes()
        nodes[0]["retry"] = 2
        attempt = {"n": 0}

        def fake_run_stage(node, *args, **kwargs):
            if node["stage"] == "s1":
                attempt["n"] += 1
                if attempt["n"] < 2:
                    return {
                        "stage": "s1",
                        "status": "failed",
                        "output": "",
                        "result": {},
                        "error": "transient",
                        "gate_blocked": False,
                        "approval_path": "",
                    }
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is True
        assert attempt["n"] == 2

    def test_gate_blocks(self, tool, monkeypatch):
        """Gate: stops and returns approval path when approve=false."""
        nodes = self._nodes()
        nodes[1]["gate"] = True

        def fake_run_stage(node, *args, **kwargs):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "completed",
                    "output": "",
                    "result": {},
                    "error": "",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            return {
                "stage": "s2",
                "status": "completed",
                "output": "report.md",
                "result": {},
                "error": "",
                "gate_blocked": True,
                "approval_path": "report.md",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is True
        assert "manual approval" in r["stdout"]

    def test_when_skip(self, tool, monkeypatch):
        """Skip node when when condition is not satisfied."""
        nodes = self._nodes()
        nodes[1]["when"] = "prev.score < 0"  # No prev result, considered unsatisfied
        executed = []

        def fake_run_stage(node, *args, **kwargs):
            executed.append(node["stage"])
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        r = tool._schedule(**self._base_kwargs(tool, nodes))
        assert r["success"] is True
        assert executed == ["s1"]  # s2 skipped because when condition unsatisfied


# ---------------------------------------------------------------------------
# loop execution and until evaluation
# ---------------------------------------------------------------------------
class TestLoop:
    def _loop_node(self, body, until, max_iterations=5, on_error="abort"):
        return {
            "stage": "L",
            "kind": "loop",
            "agent": None,
            "depends_on": [],
            "input": [],
            "output": "",
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": on_error,
            "until": until,
            "max_iterations": max_iterations,
            "body_stages": body,
        }

    def _body(self, name, output=""):
        return {
            "stage": name,
            "agent": "a1",
            "depends_on": [],
            "input": [],
            "output": output,
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": "abort",
        }

    def _kwargs(self, node):
        return dict(
            node=node,
            agent_map={"b1": "id_b1", "b2": "id_b2"},
            agents_by_name={"a1": {}},
            work_dir=Path("."),
            artifact_dir=Path(".df"),
            spec_summary="",
            approve=False,
            pipeline_id="p1",
        )

    def test_until_satisfied_first_iteration(self, tool, monkeypatch):
        """until satisfied on first iteration -> only run one round."""
        runs = []

        def fake_run_stage(node, *args, **kwargs):
            runs.append(node["stage"])
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {"ok": True},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        node = self._loop_node([self._body("b1")], "b1.ok == true", max_iterations=3)
        r = tool._run_loop(**self._kwargs(node))
        assert r["status"] == "completed"
        assert r["result"]["iterations"] == 1
        assert r["result"]["until_satisfied"] is True
        assert runs == ["b1"]

    def test_until_satisfied_after_iterations(self, tool, monkeypatch):
        """until only satisfied on 3rd iteration -> run 3 rounds."""
        counter = {"n": 0}

        def fake_run_stage(node, *args, **kwargs):
            counter["n"] += 1
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {"count": counter["n"]},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        node = self._loop_node([self._body("b1")], "b1.count >= 3", max_iterations=5)
        r = tool._run_loop(**self._kwargs(node))
        assert r["status"] == "completed"
        assert r["result"]["iterations"] == 3
        assert r["result"]["until_satisfied"] is True

    def test_max_iterations_reached(self, tool, monkeypatch):
        """until never satisfied -> run to limit, mark unsatisfied."""

        def fake_run_stage(node, *args, **kwargs):
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {"ok": False},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        node = self._loop_node([self._body("b1")], "b1.ok == true", max_iterations=3)
        r = tool._run_loop(**self._kwargs(node))
        assert r["status"] == "completed"
        assert r["result"]["iterations"] == 3
        assert r["result"]["until_satisfied"] is False

    def test_body_stage_failure(self, tool, monkeypatch):
        """Stage failure in body -> loop fails."""

        def fake_run_stage(node, *args, **kwargs):
            return {
                "stage": node["stage"],
                "status": "failed",
                "output": "",
                "result": {},
                "error": "boom",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        node = self._loop_node([self._body("b1")], "b1.ok == true", max_iterations=3)
        r = tool._run_loop(**self._kwargs(node))
        assert r["status"] == "failed"
        assert "boom" in r["error"]

    def test_body_internal_order(self, tool, monkeypatch):
        """Internal dependency order in body: b1 before b2."""
        order = []

        def fake_run_stage(node, *args, **kwargs):
            order.append(node["stage"])
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {"ok": True},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        b1 = self._body("b1")
        b2 = self._body("b2")
        b2["depends_on"] = ["b1"]
        node = self._loop_node([b2, b1], "b1.ok == true", max_iterations=1)
        tool._run_loop(**self._kwargs(node))
        assert order == ["b1", "b2"]

    def test_schedule_dispatches_loop(self, tool, monkeypatch):
        """_schedule calls _run_loop instead of _run_stage for loop nodes."""
        called = {"loop": 0, "stage": 0}

        def fake_run_loop(*args, **kwargs):
            called["loop"] += 1
            return {
                "stage": "L",
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        def fake_run_stage(*args, **kwargs):
            called["stage"] += 1
            return {
                "stage": "s1",
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_loop", fake_run_loop)
        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = [self._loop_node([self._body("b1")], "b1.ok == true")]
        r = tool._schedule(
            nodes=nodes,
            agent_map={"b1": "id_b1"},
            agents_by_name={"a1": {}},
            work_dir=Path("."),
            artifact_dir=Path(".df"),
            spec_summary="",
            approve=False,
            max_workers=2,
        )
        assert r["success"] is True
        assert called["loop"] == 1
        assert called["stage"] == 0


class TestEvalUntil:
    def test_file_contains_true(self, tool, tmp_path):
        (tmp_path / "report.md").write_text("all tests PASS", encoding="utf-8")
        ok, err = tool._eval_until('contains(file("report.md"), "PASS")', {}, tmp_path)
        assert ok is True
        assert err == ""

    def test_file_contains_false(self, tool, tmp_path):
        (tmp_path / "report.md").write_text("FAIL", encoding="utf-8")
        ok, _ = tool._eval_until('contains(file("report.md"), "PASS")', {}, tmp_path)
        assert ok is False

    def test_file_missing_empty(self, tool, tmp_path):
        ok, _ = tool._eval_until('contains(file("nope.md"), "PASS")', {}, tmp_path)
        assert ok is False

    def test_file_path_traversal_blocked(self, tool, tmp_path):
        """Out-of-bounds path (../) read fails, returns empty string."""
        secret = tmp_path.parent / "secret_until.txt"
        secret.write_text("PASS", encoding="utf-8")
        ok, _ = tool._eval_until(
            'contains(file("../secret_until.txt"), "PASS")', {}, tmp_path
        )
        assert ok is False

    def test_until_stage_ref(self, tool, tmp_path):
        results = {"b1": {"result": {"pass_rate": 0.95}}}
        ok, _ = tool._eval_until("b1.pass_rate >= 0.9", results, tmp_path)
        assert ok is True

    def test_contains_with_stage_ref(self, tool, tmp_path):
        results = {"b1": {"result": {"verdict": "OK"}}}
        ok, _ = tool._eval_until('contains(b1.verdict, "OK")', results, tmp_path)
        assert ok is True

    def test_file_size_capped(self, tool, tmp_path):
        """Oversized file read is truncated, still returns content (does not raise)."""
        (tmp_path / "big.md").write_text("x" * (1024 * 1024 + 100), encoding="utf-8")
        ok, err = tool._eval_until('contains(file("big.md"), "x")', {}, tmp_path)
        assert ok is True
        assert err == ""


# ---------------------------------------------------------------------------
# _run_stage (mock send_to_agent and status_file)
# ---------------------------------------------------------------------------
class TestRunStage:
    def test_success_with_output(self, tool, monkeypatch, tmp_path):
        """Success and artifact written to disk."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()
        (work_dir / "plan.md").write_text("plan", encoding="utf-8")

        node = {
            "stage": "s1",
            "agent": "a1",
            "depends_on": [],
            "input": [],
            "output": "plan.md",
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": "abort",
        }
        agents_by_name = {"a1": {"task": "Planning"}}

        class FakeGW:
            def _send_to_agent(
                self, agent_id, message, wait=False, status_file: str = ""
            ):
                # Simulate stage Agent writing status_file
                Path(status_file).write_text(
                    json.dumps({"status": "completed", "output": "plan.md"}),
                    encoding="utf-8",
                )
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            node, "id_s1", agents_by_name, work_dir, artifact_dir, "", False
        )
        assert r["status"] == "completed"
        assert r["output"] == "plan.md"

    def test_output_missing(self, tool, monkeypatch, tmp_path):
        """Declared artifact not written to disk -> failed."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()

        node = {
            "stage": "s1",
            "agent": "a1",
            "depends_on": [],
            "input": [],
            "output": "missing.md",
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": "abort",
        }
        agents_by_name = {"a1": {"task": "Planning"}}

        class FakeGW:
            def _send_to_agent(
                self, agent_id, message, wait=False, status_file: str = ""
            ):
                Path(status_file).write_text(
                    json.dumps({"status": "completed", "output": "missing.md"}),
                    encoding="utf-8",
                )
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            node, "id_s1", agents_by_name, work_dir, artifact_dir, "", False
        )
        assert r["status"] == "failed"
        assert "not written to disk" in r["error"]

    def test_send_failure(self, tool, monkeypatch, tmp_path):
        """send_to_agent failure -> failed."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()

        node = {
            "stage": "s1",
            "agent": "a1",
            "depends_on": [],
            "input": [],
            "output": "",
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": "abort",
        }
        agents_by_name = {"a1": {"task": "Planning"}}

        class FakeGW:
            def _send_to_agent(self, agent_id, message, wait=False, status_file=None):
                return {"success": False, "stdout": "", "stderr": "gateway down"}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            node, "id_s1", agents_by_name, work_dir, artifact_dir, "", False
        )
        assert r["status"] == "failed"
        assert "gateway down" in r["error"]


# ---------------------------------------------------------------------------
# Artifact JSON reference (when can read artifact content)
# ---------------------------------------------------------------------------
class TestArtifactJson:
    def _node(self, output):
        return {
            "stage": "s1",
            "agent": "a1",
            "depends_on": [],
            "input": [],
            "output": output,
            "gate": False,
            "when": None,
            "retry": 0,
            "on_error": "abort",
        }

    def test_read_artifact_json_dict(self, tool, tmp_path):
        """JSON artifact with dict at top level is read."""
        p = tmp_path / "report.json"
        p.write_text(json.dumps({"pass_rate": 0.9, "ok": True}), encoding="utf-8")
        assert tool._read_artifact_json(p) == {"pass_rate": 0.9, "ok": True}

    def test_read_artifact_json_non_json_ext(self, tool, tmp_path):
        """Non-.json extension not read."""
        p = tmp_path / "report.md"
        p.write_text(json.dumps({"a": 1}), encoding="utf-8")
        assert tool._read_artifact_json(p) == {}

    def test_read_artifact_json_non_dict(self, tool, tmp_path):
        """Non-dict at top level returns empty."""
        p = tmp_path / "list.json"
        p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert tool._read_artifact_json(p) == {}

    def test_read_artifact_json_invalid(self, tool, tmp_path):
        """Invalid JSON returns empty and does not raise."""
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert tool._read_artifact_json(p) == {}

    def test_read_artifact_json_missing(self, tool, tmp_path):
        """Nonexistent file returns empty."""
        assert tool._read_artifact_json(tmp_path / "nope.json") == {}

    def test_run_stage_merges_artifact_json(self, tool, monkeypatch, tmp_path):
        """Artifact JSON fields merged into result for downstream when reference."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()
        (work_dir / "report.json").write_text(
            json.dumps({"pass_rate": 0.9, "verdict": "pass"}), encoding="utf-8"
        )

        class FakeGW:
            def _send_to_agent(
                self, agent_id, message, wait=False, status_file: str = ""
            ):
                Path(status_file).write_text(
                    json.dumps({"status": "completed"}), encoding="utf-8"
                )
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            self._node("report.json"),
            "id_s1",
            {"a1": {"task": "Audit"}},
            work_dir,
            artifact_dir,
            "",
            False,
        )
        assert r["status"] == "completed"
        assert r["result"]["pass_rate"] == 0.9
        assert r["result"]["verdict"] == "pass"
        assert r["result"]["status"] == "completed"

    def test_run_stage_status_file_wins(self, tool, monkeypatch, tmp_path):
        """status_file fields take priority over same-name fields in artifact JSON."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()
        (work_dir / "report.json").write_text(
            json.dumps({"status": "artifact-status"}), encoding="utf-8"
        )

        class FakeGW:
            def _send_to_agent(
                self, agent_id, message, wait=False, status_file: str = ""
            ):
                Path(status_file).write_text(
                    json.dumps({"status": "completed"}), encoding="utf-8"
                )
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            self._node("report.json"),
            "id_s1",
            {"a1": {"task": "Audit"}},
            work_dir,
            artifact_dir,
            "",
            False,
        )
        assert r["result"]["status"] == "completed"

    def test_run_stage_non_json_output_not_merged(self, tool, monkeypatch, tmp_path):
        """Non-JSON artifact not merged, result only contains status_file content."""
        work_dir = tmp_path
        artifact_dir = work_dir / ".df"
        artifact_dir.mkdir()
        (work_dir / "plan.md").write_text("hello", encoding="utf-8")

        class FakeGW:
            def _send_to_agent(
                self, agent_id, message, wait=False, status_file: str = ""
            ):
                Path(status_file).write_text(
                    json.dumps({"status": "completed"}), encoding="utf-8"
                )
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            GatewayManagerTool, "_send_to_agent", FakeGW()._send_to_agent
        )
        r = tool._run_stage(
            self._node("plan.md"),
            "id_s1",
            {"a1": {"task": "Planning"}},
            work_dir,
            artifact_dir,
            "",
            False,
        )
        assert r["status"] == "completed"
        assert r["result"] == {"status": "completed"}


# ---------------------------------------------------------------------------
# Resident Agent creation failure retry
# ---------------------------------------------------------------------------
class TestCreateAgentRetry:
    def _nodes(self):
        return [
            {
                "stage": "s1",
                "agent": "a1",
                "depends_on": [],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            }
        ]

    def test_retry_then_success(self, tool, monkeypatch):
        """First two fail, third succeeds -> returns agent_id."""
        calls = {"n": 0}

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                calls["n"] += 1
                if calls["n"] < 3:
                    return {"success": False, "stdout": "", "stderr": "busy"}
                return {
                    "success": True,
                    "stdout": json.dumps({"agent_id": "id_x"}),
                    "stderr": "",
                }

        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        agent_id, err = tool._create_agent_with_retry(FakeGW(), "s1", ".")
        assert agent_id == "id_x"
        assert err == ""
        assert calls["n"] == 3

    def test_all_attempts_fail(self, tool, monkeypatch):
        """All fail -> returns empty id and last error."""
        calls = {"n": 0}

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                calls["n"] += 1
                return {"success": False, "stdout": "", "stderr": f"err{calls['n']}"}

        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        agent_id, err = tool._create_agent_with_retry(FakeGW(), "s1", ".")
        assert agent_id == ""
        assert err == "err3"
        assert calls["n"] == 3

    def test_success_without_agent_id_retries(self, tool, monkeypatch):
        """Creation succeeds but no agent_id -> treated as failure and retried."""
        calls = {"n": 0}

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                calls["n"] += 1
                if calls["n"] < 2:
                    return {"success": True, "stdout": "{}", "stderr": ""}
                return {
                    "success": True,
                    "stdout": json.dumps({"agent_id": "id_y"}),
                    "stderr": "",
                }

        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        agent_id, err = tool._create_agent_with_retry(FakeGW(), "s1", ".")
        assert agent_id == "id_y"
        assert calls["n"] == 2

    def test_create_stage_agents_uses_retry(self, tool, monkeypatch, tmp_path):
        """_create_stage_agents follows retry logic, successfully builds map."""
        calls = {"n": 0}

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                calls["n"] += 1
                if calls["n"] < 2:
                    return {"success": False, "stdout": "", "stderr": "busy"}
                return {
                    "success": True,
                    "stdout": json.dumps({"agent_id": f"id_{name}"}),
                    "stderr": "",
                }

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        r = tool._create_stage_agents(self._nodes(), {"a1": {}}, tmp_path)
        assert r["success"] is True
        assert r["agent_map"]["s1"] == "id_df_s1"

    def test_create_stage_agents_fail_after_retry(self, tool, monkeypatch, tmp_path):
        """Retry exhausted -> returns failure with error attached."""

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                return {"success": False, "stdout": "", "stderr": "down"}

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        monkeypatch.setattr("time.sleep", lambda *a, **k: None)
        r = tool._create_stage_agents(self._nodes(), {"a1": {}}, tmp_path)
        assert r["success"] is False
        assert "down" in r["error"]

    def test_wait_agent_ready_polls_until_ready(self, tool):
        """_wait_agent_ready polls /status until gateway proxy succeeds (non-502)."""
        calls = {"n": 0}

        class FakeGW:
            def _request_gateway(self, method, path, error_prefix):
                calls["n"] += 1
                if calls["n"] < 3:
                    return {"success": False, "error": "HTTP 502"}
                return {"success": True, "data": {}}

        ok, err = tool._wait_agent_ready(
            FakeGW(), "agent_1", timeout=10, poll_interval=0
        )
        assert ok is True
        assert err == ""
        assert calls["n"] == 3

    def test_wait_agent_ready_timeout(self, tool):
        """_wait_agent_ready times out when 502 persists."""

        class FakeGW:
            def _request_gateway(self, method, path, error_prefix):
                return {"success": False, "error": "HTTP 502"}

        ok, err = tool._wait_agent_ready(
            FakeGW(), "agent_1", timeout=0.2, poll_interval=0
        )
        assert ok is False
        assert "Timed out" in err

    def test_wait_agent_ready_skips_without_request_gateway(self, tool):
        """Test stub without _request_gateway is considered ready directly."""

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                return {"success": True, "stdout": json.dumps({"agent_id": "x"})}

        ok, err = tool._wait_agent_ready(FakeGW(), "agent_1")
        assert ok is True
        assert err == ""


# ---------------------------------------------------------------------------
# Cleanup of resident Agents on failure/abort (task-22 orchestration reliability)
# ---------------------------------------------------------------------------
class TestCleanupAgents:
    def test_cleanup_deletes_all_agents(self, tool, monkeypatch):
        """_cleanup_agents deletes all Agents in agent_map."""
        deleted = []

        class FakeGW:
            def _delete_agent(self, agent_id):
                deleted.extend(agent_id if isinstance(agent_id, list) else [agent_id])
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        tool._cleanup_agents({"s1": "id_a", "s2": "id_b"})
        assert set(deleted) == {"id_a", "id_b"}

    def test_cleanup_skips_when_disabled(self, tool, monkeypatch):
        """No deletion when config disables cleanup."""
        from haijunbot.haijunbot_utils.config import GLOBAL_CONFIG_DATA

        deleted = []

        class FakeGW:
            def _delete_agent(self, agent_id):
                deleted.append(agent_id)
                return {"success": True, "stdout": "", "stderr": ""}

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        key = "pipeline_cleanup_on_failure"
        original = GLOBAL_CONFIG_DATA.get(key)
        try:
            GLOBAL_CONFIG_DATA[key] = False
            tool._cleanup_agents({"s1": "id_a"})
        finally:
            if original is None:
                GLOBAL_CONFIG_DATA.pop(key, None)
            else:
                GLOBAL_CONFIG_DATA[key] = original
        assert deleted == []

    def test_cleanup_skips_without_delete_agent(self, tool, monkeypatch):
        """Skip directly when test stub has no _delete_agent, no error."""

        class FakeGW:
            def _create_agent(self, agent_type, working_dir, name):
                return {"success": True, "stdout": "{}"}

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        # Should not raise
        tool._cleanup_agents({"s1": "id_a"})

    def test_cleanup_empty_map(self, tool, monkeypatch):
        """Empty agent_map does not call delete."""
        called = {"n": 0}

        class FakeGW:
            def _delete_agent(self, agent_id):
                called["n"] += 1
                return {"success": True}

        monkeypatch.setattr(
            "haijunbot.haijunbot_tools.pipeline_runner.GatewayManagerTool",
            lambda: FakeGW(),
        )
        tool._cleanup_agents({})
        assert called["n"] == 0

    def test_abort_calls_cleanup(self, tool, monkeypatch):
        """Calls _cleanup_agents on abort with on_error=abort."""
        cleaned = {"n": 0}

        def fake_run_stage(node, *args, **kwargs):
            return {
                "stage": node["stage"],
                "status": "failed" if node["stage"] == "s1" else "completed",
                "output": "",
                "result": {},
                "error": "boom",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        monkeypatch.setattr(
            tool,
            "_cleanup_agents",
            lambda agent_map: cleaned.__setitem__("n", cleaned["n"] + 1),
        )
        # Use TestSchedule's nodes
        r = tool._schedule(**TestSchedule()._base_kwargs(tool, TestSchedule()._nodes()))
        assert r["success"] is False
        assert cleaned["n"] == 1

    def test_failure_calls_cleanup(self, tool, monkeypatch):
        """Calls _cleanup_agents when pipeline has failed stages."""
        cleaned = {"n": 0}

        def fake_run_stage(node, *args, **kwargs):
            return {
                "stage": node["stage"],
                "status": "failed",
                "output": "",
                "result": {},
                "error": "boom",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        monkeypatch.setattr(
            tool,
            "_cleanup_agents",
            lambda agent_map: cleaned.__setitem__("n", cleaned["n"] + 1),
        )
        nodes = TestSchedule()._nodes()
        nodes[0]["on_error"] = "continue"
        nodes[1]["on_error"] = "continue"
        r = tool._schedule(**TestSchedule()._base_kwargs(tool, nodes))
        assert r["success"] is False
        assert cleaned["n"] == 1


# ---------------------------------------------------------------------------
# dry-run preview (approach 1: only validate orchestration plan, do not create Agent)
# ---------------------------------------------------------------------------
class TestDryRun:
    def _write(self, tmp_path, flow_yaml):
        orch = tmp_path / "p.yaml"
        orch.write_text(flow_yaml, encoding="utf-8")
        return orch

    def test_dry_run_no_agent_created(self, tool, monkeypatch, tmp_path):
        """dry-run does not create Agent or dispatch tasks."""
        orch = self._write(
            tmp_path,
            """
agents:
  - name: a1
    working_dir: .
    task: t
flow:
  - stage: s1
    agent: a1
    output: .df/x.md
""",
        )

        def boom(*a, **k):
            raise AssertionError("dry-run should not create Agent")

        monkeypatch.setattr(GatewayManagerTool, "_create_agent", boom)
        monkeypatch.setattr(GatewayManagerTool, "_send_to_agent", boom)
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "dry-run" in r["stdout"]
        assert "s1" in r["stdout"]

    def test_dry_run_shows_parallel_batches(self, tool, tmp_path):
        """dry-run correctly marks parallel and serial batches."""
        orch = self._write(
            tmp_path,
            """
agents:
  - name: a1
    working_dir: .
    task: t
  - name: a2
    working_dir: .
    task: t
  - name: a3
    working_dir: .
    task: t
flow:
  - stage: plan
    agent: a1
    output: .df/plan.md
  - stage: gen_a
    agent: a2
    depends_on: [plan]
    output: .df/a.txt
  - stage: gen_b
    agent: a3
    depends_on: [plan]
    output: .df/b.txt
""",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "Batch 1 [serial]" in r["stdout"]
        assert "Batch 2 [parallel]" in r["stdout"]

    def test_dry_run_invalid_flow_reports_error(self, tool, tmp_path):
        """dry-run reports error for invalid orchestration (duplicate stage)."""
        orch = self._write(
            tmp_path,
            """
agents:
  - name: a1
    working_dir: .
    task: t
flow:
  - stage: s1
    agent: a1
  - stage: s1
    agent: a1
""",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is False
        assert "Duplicate" in r["stderr"]

    def test_dry_run_shows_gate_and_when(self, tool, tmp_path):
        """dry-run displays gate and when information."""
        orch = self._write(
            tmp_path,
            """
agents:
  - name: a1
    working_dir: .
    task: t
  - name: a2
    working_dir: .
    task: t
flow:
  - stage: verify
    agent: a1
    output: .df/report.json
  - stage: audit
    agent: a2
    depends_on: [verify]
    when: "verify.pass_rate >= 0.9"
    output: .df/approval.md
    gate: true
""",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "Gate stages: audit" in r["stdout"]
        assert "when=verify.pass_rate >= 0.9" in r["stdout"]

    def test_dry_run_inline_spec_without_spec_file(self, tool, tmp_path):
        """Read top-level spec field from orchestration file as background for each stage (normal orchestration does not need separate spec file)."""
        orch = tmp_path / "p.yaml"
        orch.write_text(
            """
spec: |
   Pipeline background description embedded in the orchestration file.
agents:
  - name: a1
    working_dir: .
    task: t
flow:
  - stage: s1
    agent: a1
    output: .df/x.md
""",
            encoding="utf-8",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "dry-run" in r["stdout"]
        assert "s1" in r["stdout"]

    def test_dry_run_no_spec_at_all(self, tool, tmp_path):
        """Orchestration file has neither spec field nor separate spec file passed: still runnable, each stage uses its own task description."""
        orch = tmp_path / "p.yaml"
        orch.write_text(
            """
agents:
  - name: a1
    working_dir: .
    task: t
flow:
  - stage: s1
    agent: a1
    output: .df/x.md
""",
            encoding="utf-8",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "s1" in r["stdout"]

    def test_plan_batches_order(self, tool):
        """_plan_batches: correct dependency-level batching."""
        nodes = [
            {
                "stage": "a",
                "depends_on": [],
                "agent": "x",
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "b",
                "depends_on": ["a"],
                "agent": "x",
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "c",
                "depends_on": ["a"],
                "agent": "x",
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "d",
                "depends_on": ["b", "c"],
                "agent": "x",
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
        ]
        batches = tool._plan_batches(nodes)
        assert [n["stage"] for n in batches[0]] == ["a"]
        assert sorted(n["stage"] for n in batches[1]) == ["b", "c"]
        assert [n["stage"] for n in batches[2]] == ["d"]


# ---------------------------------------------------------------------------
# Cross-node validation (orchestration with flow does not support cross-node)
# ---------------------------------------------------------------------------
class TestCrossNodeValidation:
    def _write(self, tmp_path, agents_yaml):
        orch = tmp_path / "p.yaml"
        orch.write_text(
            "agents:\n" + agents_yaml + "flow:\n  - stage: s1\n    agent: a1\n    output: .df/x.md\n",
            encoding="utf-8",
        )
        return orch

    def test_node_id_rejected(self, tool, tmp_path):
        """Explicit error when agent definition has node_id, rather than silently ignoring."""
        orch = self._write(
            tmp_path,
            "  - name: a1\n    working_dir: .\n    task: t\n    node_id: worker-1\n",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is False
        assert "does not support cross-node" in r["stderr"]

    def test_proxy_node_rejected(self, tool, tmp_path):
        """Explicit error when agent definition has proxy_node."""
        orch = self._write(
            tmp_path,
            "  - name: a1\n    working_dir: .\n    task: t\n    proxy_node: proxy-1\n",
        )
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is False
        assert "does not support cross-node" in r["stderr"]

    def test_without_node_fields_ok(self, tool, tmp_path):
        """Orchestration without node_id/proxy_node executes normally (dry-run)."""
        orch = self._write(tmp_path, "  - name: a1\n    working_dir: .\n    task: t\n")
        r = tool.execute(
            {
                "orchestration_file": str(orch),
                "working_dir": str(tmp_path),
                "dry_run": True,
            }
        )
        assert r["success"] is True
        assert "s1" in r["stdout"]


# ---------------------------------------------------------------------------
# Progress event instrumentation (_schedule state transitions -> event bus)
# ---------------------------------------------------------------------------
class TestPipelineEventEmit:
    """Verify _schedule writes correct stage_update /
    pipeline_done events to event bus at each state transition point, and that
    instrumentation is a pure side effect (does not affect return values/state machine semantics).
    """

    def _nodes(self):
        return [
            {
                "stage": "s1",
                "agent": "a1",
                "depends_on": [],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
            {
                "stage": "s2",
                "agent": "a2",
                "depends_on": ["s1"],
                "input": [],
                "output": "",
                "gate": False,
                "when": None,
                "retry": 0,
                "on_error": "abort",
            },
        ]

    def _base_kwargs(self, nodes, pipeline_id="pl-test"):
        return dict(
            nodes=nodes,
            agent_map={n["stage"]: f"id_{n['stage']}" for n in nodes},
            agents_by_name={"a1": {}, "a2": {}},
            work_dir=Path("."),
            artifact_dir=Path(".df"),
            spec_summary="",
            approve=False,
            max_workers=4,
            pipeline_id=pipeline_id,
        )

    def _completed(self, node):
        return {
            "stage": node["stage"],
            "status": "completed",
            "output": "",
            "result": {},
            "error": "",
            "gate_blocked": False,
            "approval_path": "",
        }

    def _drain(self):
        from haijunbot.haijunbot_tools.pipeline_events import get_event_bus

        return get_event_bus().drain()

    def test_all_completed_emits_running_and_done(self, tool, monkeypatch):
        """All completed: each stage has running+completed, ends with pipeline_done=completed."""
        self._drain()  # Clear leftover events
        monkeypatch.setattr(
            tool, "_run_stage", lambda node, *a, **k: self._completed(node)
        )
        nodes = self._nodes()
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is True

        events = self._drain()
        assert all(e["pipeline_id"] == "pl-test" for e in events)
        stage_events = [e for e in events if e["type"] == "stage_update"]
        # s1/s2 each have running and completed
        for stage in ("s1", "s2"):
            statuses = [e["status"] for e in stage_events if e["stage"] == stage]
            assert statuses.count("running") == 1
            assert statuses.count("completed") == 1
        done = [e for e in events if e["type"] == "pipeline_done"]
        assert len(done) == 1
        assert done[0]["success"] is True
        assert done[0]["final_status"] == "completed"

    def test_failed_emits_pipeline_done_failed(self, tool, monkeypatch):
        """Failed: failed stage has failed event, ends with pipeline_done=failed."""
        self._drain()

        def fake_run_stage(node, *a, **k):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "failed",
                    "output": "",
                    "result": {},
                    "error": "boom",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            return self._completed(node)

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        # on_error=continue: failure does not abort, takes "has failed stages" exit
        nodes[0]["on_error"] = "continue"
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is False

        events = self._drain()
        failed = [
            e for e in events if e["type"] == "stage_update" and e["status"] == "failed"
        ]
        assert any(e["stage"] == "s1" for e in failed)
        done = [e for e in events if e["type"] == "pipeline_done"]
        assert len(done) == 1
        assert done[0]["success"] is False
        assert done[0]["final_status"] == "failed"

    def test_abort_emits_pipeline_done_aborted(self, tool, monkeypatch):
        """on_error=abort: abort immediately on failure, pipeline_done=aborted."""
        self._drain()

        def fake_run_stage(node, *a, **k):
            return {
                "stage": node["stage"],
                "status": "failed",
                "output": "",
                "result": {},
                "error": "boom",
                "gate_blocked": False,
                "approval_path": "",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is False

        events = self._drain()
        done = [e for e in events if e["type"] == "pipeline_done"]
        assert len(done) == 1
        assert done[0]["success"] is False
        assert done[0]["final_status"] == "aborted"

    def test_skipped_emits_skipped_event(self, tool, monkeypatch):
        """Skipped due to dependency failure: s2 has skipped event."""
        self._drain()

        def fake_run_stage(node, *a, **k):
            if node["stage"] == "s1":
                return {
                    "stage": "s1",
                    "status": "failed",
                    "output": "",
                    "result": {},
                    "error": "boom",
                    "gate_blocked": False,
                    "approval_path": "",
                }
            return self._completed(node)

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        # on_error=skip_dependents: s2 skipped after s1 failure
        nodes[0]["on_error"] = "skip_dependents"
        tool._schedule(**self._base_kwargs(nodes))

        events = self._drain()
        skipped = [
            e
            for e in events
            if e["type"] == "stage_update" and e["status"] == "skipped"
        ]
        assert any(e["stage"] == "s2" for e in skipped)

    def test_retry_emits_retry_event(self, tool, monkeypatch):
        """retry: emits retry event on first failure, completed after successful retry."""
        self._drain()
        attempts = {"s1": 0}

        def fake_run_stage(node, *a, **k):
            if node["stage"] == "s1":
                attempts["s1"] += 1
                if attempts["s1"] == 1:
                    return {
                        "stage": "s1",
                        "status": "failed",
                        "output": "",
                        "result": {},
                        "error": "flaky",
                        "gate_blocked": False,
                        "approval_path": "",
                    }
            return self._completed(node)

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        nodes[0]["retry"] = 1
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is True

        events = self._drain()
        retries = [
            e for e in events if e["type"] == "stage_update" and e["status"] == "retry"
        ]
        assert len(retries) == 1
        assert retries[0]["stage"] == "s1"
        assert retries[0]["retry_count"] == 1

    def test_gate_blocked_emits_gate_status(self, tool, monkeypatch):
        """Gate blocking: pipeline_done=gate_blocked with gate_stage."""
        self._drain()

        def fake_run_stage(node, *a, **k):
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": node["stage"] == "s1",
                "approval_path": "/tmp/approval.md",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        nodes[0]["gate"] = True
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is True

        events = self._drain()
        done = [e for e in events if e["type"] == "pipeline_done"]
        assert len(done) == 1
        assert done[0]["final_status"] == "gate_blocked"
        assert done[0]["gate_stage"] == "s1"

    def test_gate_blocked_emits_pending_approval(self, tool, monkeypatch):
        """Gate blocking: additionally broadcasts a pipeline_approval action=pending event."""
        self._drain()

        def fake_run_stage(node, *a, **k):
            return {
                "stage": node["stage"],
                "status": "completed",
                "output": "",
                "result": {},
                "error": "",
                "gate_blocked": node["stage"] == "s1",
                "approval_path": "/tmp/approval.md",
            }

        monkeypatch.setattr(tool, "_run_stage", fake_run_stage)
        nodes = self._nodes()
        nodes[0]["gate"] = True
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is True

        events = self._drain()
        approvals = [e for e in events if e["type"] == "pipeline_approval"]
        assert len(approvals) == 1
        assert approvals[0]["action"] == "pending"
        assert approvals[0]["gate_stage"] == "s1"
        assert approvals[0]["approval_path"] == "/tmp/approval.md"
        assert "ts" in approvals[0]

    def test_emit_is_pure_side_effect(self, tool, monkeypatch):
        """Event bus exception does not affect execution result (pure side effect)."""
        self._drain()

        class _BoomBus:
            def emit(self, event):
                raise RuntimeError("bus down")

        import haijunbot.haijunbot_tools.pipeline_events as pe

        monkeypatch.setattr(pe, "get_event_bus", lambda: _BoomBus())
        monkeypatch.setattr(
            tool, "_run_stage", lambda node, *a, **k: self._completed(node)
        )
        nodes = self._nodes()
        r = tool._schedule(**self._base_kwargs(nodes))
        assert r["success"] is True
        assert "All pipeline stages complete" in r["stdout"]


# ---------------------------------------------------------------------------
# Gate manual approval recording (record_approval)
# ---------------------------------------------------------------------------
class TestRecordApproval:
    """Verify record_approval records approval decision and broadcasts pipeline_approval event."""

    def _drain(self):
        from haijunbot.haijunbot_tools.pipeline_events import get_event_bus

        return get_event_bus().drain()

    def test_approve_records_and_emits(self, tool):
        """Approve: returns success and broadcasts action=approve event (with approver/note/time)."""
        self._drain()
        r = tool.record_approval(
            pipeline_id="pl-1", action="approve", approver="alice", note="ok"
        )
        assert r["success"] is True
        assert r["data"]["action"] == "approve"
        assert r["data"]["approver"] == "alice"
        assert r["data"]["note"] == "ok"
        events = self._drain()
        appr = [e for e in events if e["type"] == "pipeline_approval"]
        assert len(appr) == 1
        assert appr[0]["action"] == "approve"
        assert appr[0]["approver"] == "alice"
        assert appr[0]["note"] == "ok"
        assert appr[0]["pipeline_id"] == "pl-1"
        assert "ts" in appr[0]

    def test_reject_and_retry_actions(self, tool):
        """Reject/retry: both successfully broadcast corresponding action."""
        for action in ("reject", "retry"):
            self._drain()
            r = tool.record_approval(pipeline_id="pl-1", action=action)
            assert r["success"] is True
            assert r["data"]["action"] == action
            events = self._drain()
            appr = [e for e in events if e["type"] == "pipeline_approval"]
            assert len(appr) == 1
            assert appr[0]["action"] == action

    def test_invalid_action_rejected(self, tool):
        """Invalid action: returns failure and does not broadcast event."""
        self._drain()
        r = tool.record_approval(pipeline_id="pl-1", action="banana")
        assert r["success"] is False
        assert "Invalid approval action" in r["error"]
        events = self._drain()
        assert not [e for e in events if e["type"] == "pipeline_approval"]

    def test_missing_pipeline_id_rejected(self, tool):
        """Missing pipeline_id: returns failure."""
        r = tool.record_approval(pipeline_id="", action="approve")
        assert r["success"] is False
        assert "pipeline_id" in r["error"]

    def test_action_case_insensitive(self, tool):
        """Action case-insensitive: Approve normalized to approve."""
        self._drain()
        r = tool.record_approval(pipeline_id="pl-1", action="Approve")
        assert r["success"] is True
        assert r["data"]["action"] == "approve"
