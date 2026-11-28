# -*- coding: utf-8 -*-
"""Orchestration Python DSL (orchestration_dsl) and unified loader (orchestration_loader) tests.

Coverage:
1. DSL construction: stage() normalization/validation, Pipeline.add/agent/spec/default_on_error,
   to_dict export structure isomorphic to YAML;
2. Equivalence: DAG built from DSL-produced structure via pipeline_runner._build_dag,
   field-by-field identical to equivalent YAML structure via _build_dag (key invariant);
3. Loader: .yaml and .flow return isomorphic structures, error paths (nonexistent/unsupported suffix/
   missing pipeline variable/syntax error) raise clear ValueError.
"""
import textwrap
from typing import cast

import pytest

from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline
from haijunbot.haijunbot_tools.orchestration_dsl import loop
from haijunbot.haijunbot_tools.orchestration_dsl import stage
from haijunbot.haijunbot_tools.orchestration_loader import load_orchestration
from haijunbot.haijunbot_tools.pipeline_runner import PipelineRunnerTool


@pytest.fixture
def tool():
    return PipelineRunnerTool()


# ---------------------------------------------------------------------------
# DSL construction
# ---------------------------------------------------------------------------
class TestStage:
    def test_minimal(self):
        item = stage("plan", agent="planner")
        assert item == {"stage": "plan", "agent": "planner"}

    def test_full_fields(self):
        item = stage(
            "gen",
            agent="generator",
            depends_on=["plan"],
            input=["a.md", "b.md"],
            output="out.md",
            gate=True,
            when="plan.ok == true",
            retry=2,
            on_error="continue",
        )
        assert item["stage"] == "gen"
        assert item["agent"] == "generator"
        assert item["depends_on"] == ["plan"]
        assert item["input"] == ["a.md", "b.md"]
        assert item["output"] == "out.md"
        assert item["gate"] is True
        assert item["when"] == "plan.ok == true"
        assert item["retry"] == 2
        assert item["on_error"] == "continue"

    def test_missing_name(self):
        with pytest.raises(ValueError):
            stage("", agent="a")

    def test_missing_agent(self):
        with pytest.raises(ValueError):
            stage("s", agent="")


class TestPipeline:
    def test_to_dict_minimal(self):
        p = Pipeline()
        p.agent("a1")
        p.add(stage("s1", agent="a1"))
        data = p.to_dict()
        assert set(data.keys()) == {"agents", "flow"}
        assert data["agents"] == [{"name": "a1"}]
        assert data["flow"] == [{"stage": "s1", "agent": "a1"}]

    def test_to_dict_with_spec_and_default(self):
        p = Pipeline()
        p.spec("Background")
        p.default_on_error("continue")
        p.agent("a1", working_dir=".", task="Do work")
        p.add(stage("s1", agent="a1"))
        data = p.to_dict()
        assert data["spec"] == "Background"
        assert data["default_on_error"] == "continue"
        assert data["agents"] == [{"name": "a1", "working_dir": ".", "task": "Do work"}]

    def test_duplicate_stage(self):
        p = Pipeline()
        p.add(stage("s1", agent="a1"))
        with pytest.raises(ValueError):
            p.add(stage("s1", agent="a1"))

    def test_duplicate_agent(self):
        p = Pipeline()
        p.agent("a1")
        with pytest.raises(ValueError):
            p.agent("a1")

    def test_unknown_agent_field_ignored(self):
        p = Pipeline()
        p.agent("a1", unknown_field="x")
        assert p.to_dict()["agents"] == [{"name": "a1"}]

    def test_add_requires_dict(self):
        p = Pipeline()
        bad = cast("dict", "not-a-dict")
        with pytest.raises(TypeError):
            p.add(bad)


class TestLoop:
    def test_minimal(self):
        item = loop("fix", body=["translate", "compile"], until="compile.ok == true")
        assert item == {
            "loop": "fix",
            "body": ["translate", "compile"],
            "until": "compile.ok == true",
            "max_iterations": 5,
        }

    def test_body_str_and_on_error(self):
        item = loop("fix", body="compile", until="compile.ok == true",
                    max_iterations=3, on_error="continue")
        assert item["body"] == ["compile"]
        assert item["max_iterations"] == 3
        assert item["on_error"] == "continue"

    def test_missing_name(self):
        with pytest.raises(ValueError):
            loop("", body=["s"], until="s.ok == true")

    def test_empty_body(self):
        with pytest.raises(ValueError):
            loop("fix", body=[], until="s.ok == true")

    def test_missing_until(self):
        with pytest.raises(ValueError):
            loop("fix", body=["s"], until="")

    def test_bad_max_iterations(self):
        with pytest.raises(ValueError):
            loop("fix", body=["s"], until="s.ok == true", max_iterations=0)

    def test_add_loop_ok(self):
        p = Pipeline()
        p.agent("a1")
        p.add(stage("translate", agent="a1"))
        p.add(stage("compile", agent="a1"))
        p.add(loop("fix", body=["translate", "compile"], until="compile.ok == true"))
        data = p.to_dict()
        assert data["flow"][-1]["loop"] == "fix"

    def test_add_loop_body_unknown_stage(self):
        p = Pipeline()
        p.agent("a1")
        p.add(stage("translate", agent="a1"))
        with pytest.raises(ValueError):
            p.add(loop("fix", body=["translate", "nope"], until="x.ok == true"))

    def test_duplicate_loop(self):
        p = Pipeline()
        p.agent("a1")
        p.add(stage("s", agent="a1"))
        p.add(loop("fix", body=["s"], until="s.ok == true"))
        with pytest.raises(ValueError):
            p.add(loop("fix", body=["s"], until="s.ok == true"))

    def test_loop_name_conflicts_with_stage(self):
        p = Pipeline()
        p.agent("a1")
        p.add(stage("s", agent="a1"))
        p.add(loop("fix", body=["s"], until="s.ok == true"))
        with pytest.raises(ValueError):
            p.add(stage("fix", agent="a1"))


# ---------------------------------------------------------------------------
# Key invariant: DSL structure and equivalent YAML produce identical results via _build_dag
# ---------------------------------------------------------------------------
class TestDslEquivalentToYaml:
    def test_build_dag_equivalence(self, tool):
        # YAML equivalent structure
        yaml_orch = {
            "agents": [
                {"name": "planner", "working_dir": ".", "task": "Planning"},
                {"name": "generator", "working_dir": ".", "task": "Generation"},
            ],
            "flow": [
                {"stage": "plan", "agent": "planner", "output": "plan.md"},
                {"stage": "gen", "agent": "generator", "input": "plan.md"},
            ],
            "default_on_error": "abort",
        }

        # DSL equivalent structure
        p = Pipeline()
        p.default_on_error("abort")
        p.agent("planner", working_dir=".", task="Planning")
        p.agent("generator", working_dir=".", task="Generation")
        p.add(stage("plan", agent="planner", output="plan.md"))
        p.add(stage("gen", agent="generator", input="plan.md"))
        dsl_orch = p.to_dict()

        agents_by_name = {a["name"]: a for a in yaml_orch["agents"]}
        r_yaml = tool._build_dag(
            yaml_orch["flow"], agents_by_name, yaml_orch["default_on_error"]
        )
        r_dsl = tool._build_dag(
            dsl_orch["flow"], agents_by_name, dsl_orch["default_on_error"]
        )

        assert r_yaml.get("success") is True
        assert r_dsl.get("success") is True
        assert r_dsl["nodes"] == r_yaml["nodes"]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
class TestLoader:
    def _write(self, tmp_path, name, content):
        f = tmp_path / name
        f.write_text(textwrap.dedent(content), encoding="utf-8")
        return f

    def test_load_yaml(self, tmp_path):
        f = self._write(
            tmp_path,
            "orch.yaml",
            """
            agents:
              - name: a1
            flow:
              - stage: s1
                agent: a1
            """,
        )
        data = load_orchestration(f)
        assert data["agents"] == [{"name": "a1"}]
        assert data["flow"] == [{"stage": "s1", "agent": "a1"}]

    def test_load_flow(self, tmp_path):
        f = self._write(
            tmp_path,
            "orch.flow",
            """
            from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage
            pipeline = Pipeline()
            pipeline.agent("a1")
            pipeline.add(stage("s1", agent="a1"))
            """,
        )
        data = load_orchestration(f)
        assert set(data.keys()) == {"agents", "flow"}
        assert data["agents"] == [{"name": "a1"}]
        assert data["flow"] == [{"stage": "s1", "agent": "a1"}]

    def test_yaml_and_flow_isomorphic(self, tmp_path):
        yaml_f = self._write(
            tmp_path,
            "a.yaml",
            """
            agents:
              - name: a1
            flow:
              - stage: s1
                agent: a1
            """,
        )
        flow_f = self._write(
            tmp_path,
            "a.flow",
            """
            from haijunbot.haijunbot_tools.orchestration_dsl import Pipeline, stage
            pipeline = Pipeline()
            pipeline.agent("a1")
            pipeline.add(stage("s1", agent="a1"))
            """,
        )
        assert load_orchestration(yaml_f) == load_orchestration(flow_f)

    def test_missing_file(self, tmp_path):
        with pytest.raises(ValueError):
            load_orchestration(tmp_path / "nope.yaml")

    def test_unsupported_suffix(self, tmp_path):
        f = self._write(tmp_path, "x.txt", "hello")
        with pytest.raises(ValueError):
            load_orchestration(f)

    def test_flow_missing_pipeline_var(self, tmp_path):
        f = self._write(
            tmp_path,
            "bad.flow",
            """
            x = 1
            """,
        )
        with pytest.raises(ValueError):
            load_orchestration(f)

    def test_flow_syntax_error(self, tmp_path):
        f = self._write(tmp_path, "syn.flow", "def (:\n")
        with pytest.raises(ValueError):
            load_orchestration(f)
