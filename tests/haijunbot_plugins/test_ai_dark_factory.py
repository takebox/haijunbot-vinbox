# -*- coding: utf-8 -*-
"""AI Dark Factory plugin (ai-dark-factory) tests.

Covers:
1. 3 tools (spec_validator / holdout_generator / gate_calculator) normal,
   boundary, and exception scenarios;
2. Orchestration template dark_factory_pipeline.yaml format (agents list, flow field, four elements complete);
3. config.yaml parseability and declaration completeness.

All tools are loaded directly from plugin source files using importlib, without depending on
global configuration loading, to avoid polluting the real environment.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

PLUGIN_DIR = (
    Path(__file__).resolve().parents[2]
    / "builtin"
    / "plugins"
    / "ai-dark-factory"
)
TOOLS_DIR = PLUGIN_DIR / "tools"


def _load_tool_class(module_name: str, filename: str):
    """Load plugin tool file using importlib, return the Tool class within it."""
    file_path = TOOLS_DIR / filename
    assert file_path.is_file(), f"Tool file does not exist: {file_path}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    for attr in dir(mod):
        if attr.endswith("Tool"):
            cls = getattr(mod, attr)
            if isinstance(cls, type):
                return cls
    raise AssertionError(f"No Tool class found in {filename}")


@pytest.fixture(scope="module")
def spec_validator():
    return _load_tool_class("df_spec_validator", "spec_validator.py")()


@pytest.fixture(scope="module")
def holdout_generator():
    return _load_tool_class("df_holdout_generator", "holdout_generator.py")()


@pytest.fixture(scope="module")
def gate_calculator():
    return _load_tool_class("df_gate_calculator", "gate_calculator.py")()


class TestToolInterface:
    """Tool interface completeness (name/description/parameters/check/execute)."""

    @pytest.mark.parametrize(
        "tool_name,filename",
        [
            ("spec_validator", "spec_validator.py"),
            ("holdout_generator", "holdout_generator.py"),
            ("gate_calculator", "gate_calculator.py"),
        ],
    )
    def test_interface_complete(self, tool_name, filename):
        cls = _load_tool_class(f"iface_{tool_name}", filename)
        tool = cls()
        assert tool.name == tool_name, f"{tool_name} name mismatch"
        assert tool.description
        assert isinstance(tool.parameters, dict)
        assert callable(tool.check)
        assert callable(tool.execute)
        assert tool.check() is True


class TestSpecValidator:
    """NLSpec four-element validation tool."""

    def test_valid_spec(self, spec_validator):
        r = spec_validator.execute(
            {
                "spec": (
                    "Goal: Build a calculator. Constraints: Must use Python, performance requirements. "
                    "Interface: Function add(a,b). Non-goals: No GUI."
                )
            }
        )
        assert r["success"] is True
        out = json.loads(r["stdout"])
        assert out["valid"] is True
        assert out["missing"] == []

    def test_missing_elements(self, spec_validator):
        r = spec_validator.execute({"spec": "Write something random"})
        assert r["success"] is True
        out = json.loads(r["stdout"])
        assert out["valid"] is False
        assert len(out["missing"]) >= 1

    def test_empty_spec(self, spec_validator):
        r = spec_validator.execute({"spec": ""})
        assert r["success"] is False
        assert "non-empty string" in r["stderr"]

    def test_missing_param(self, spec_validator):
        r = spec_validator.execute({})
        assert r["success"] is False

    def test_non_string_spec(self, spec_validator):
        r = spec_validator.execute({"spec": 123})
        assert r["success"] is False


class TestHoldoutGenerator:
    """Holdout scenarios generation tool."""

    def test_generate_default_count(self, holdout_generator):
        r = holdout_generator.execute({"feature": "calculator"})
        assert r["success"] is True
        out = json.loads(r["stdout"])
        assert out["count"] == 5
        assert len(out["scenarios"]) == 5
        # Each scenario must be marked hidden (invisible to coding side)
        assert all(s["hidden"] is True for s in out["scenarios"])

    def test_generate_specific_count(self, holdout_generator):
        r = holdout_generator.execute({"feature": "calculator", "count": 3})
        out = json.loads(r["stdout"])
        assert out["count"] == 3
        assert len(out["scenarios"]) == 3

    def test_count_clamped_upper(self, holdout_generator):
        r = holdout_generator.execute({"feature": "x", "count": 999})
        out = json.loads(r["stdout"])
        assert out["count"] == 20

    def test_count_clamped_lower(self, holdout_generator):
        r = holdout_generator.execute({"feature": "x", "count": 0})
        out = json.loads(r["stdout"])
        assert out["count"] == 1

    def test_missing_feature(self, holdout_generator):
        r = holdout_generator.execute({})
        assert r["success"] is False


class TestGateCalculator:
    """Gate metrics calculation tool."""

    def test_pass_rate_above_threshold(self, gate_calculator):
        r = gate_calculator.execute(
            {"results": [{"id": 1, "pass": True}, {"id": 2, "pass": True}, {"id": 3, "pass": True}]}
        )
        out = json.loads(r["stdout"])
        assert out["pass_rate"] == 1.0
        assert out["meets_threshold"] is True
        assert "Recommend passing" in out["decision"]

    def test_pass_rate_below_threshold(self, gate_calculator):
        r = gate_calculator.execute(
            {"results": [{"id": 1, "pass": True}, {"id": 2, "pass": True}, {"id": 3, "pass": False}]}
        )
        out = json.loads(r["stdout"])
        # Tool rounds pass_rate to 4 decimal places
        assert out["pass_rate"] == pytest.approx(2 / 3, abs=0.0001)
        assert out["meets_threshold"] is False

    def test_caution_high_false_positive(self, gate_calculator):
        r = gate_calculator.execute(
            {
                "results": [{"id": 1, "pass": True}, {"id": 2, "pass": True}],
                "false_positives": 2,
            }
        )
        out = json.loads(r["stdout"])
        assert out["caution"] is True

    def test_empty_results(self, gate_calculator):
        r = gate_calculator.execute({"results": []})
        assert r["success"] is False

    def test_missing_results(self, gate_calculator):
        r = gate_calculator.execute({})
        assert r["success"] is False


class TestOrchestrationTemplate:
    """Preset orchestration template dark_factory_pipeline.yaml format."""

    def _load(self):
        path = PLUGIN_DIR / "orchestration" / "dark_factory_pipeline.yaml"
        assert path.is_file(), "Orchestration template does not exist"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_has_all_layer_agents(self):
        data = self._load()
        assert "agents" in data
        agents = data["agents"]
        assert len(agents) == 6
        names = [a["name"] for a in agents]
        # Architecture: planner / holdout / generator / validator / regression / orchestrator
        assert "df_planner" in names
        assert "df_holdout" in names
        assert "df_generator" in names
        assert "df_validator" in names
        assert "df_regression" in names
        assert "df_orchestrator" in names

    def test_each_agent_has_required_fields(self):
        """Each agent must declare name / working_dir / task (without type).

        The orchestration system ignores the stage type field; stage Agents are always
        created as type: agent -> hjb, so template agents do not need to declare type.
        """
        data = self._load()
        for a in data["agents"]:
            assert a.get("name"), "agent missing name"
            assert a.get("working_dir"), "agent missing working_dir"
            assert a.get("task"), "agent missing task"

    def test_orchestrator_not_auto_merge(self):
        """Orchestrator should emphasize manual approval, not auto-merge (not fully unattended)."""
        data = self._load()
        orch = next(a for a in data["agents"] if a["name"] == "df_orchestrator")
        task = orch["task"]
        assert "manual approval" in task or "no auto-merge" in task or "approval" in task

    def test_has_flow_field(self):
        """Orchestration template declares flow (for pipeline_runner to drive)."""
        data = self._load()
        assert "flow" in data, "Orchestration template missing flow field"
        assert isinstance(data["flow"], list) and data["flow"]
        stages = [s["stage"] for s in data["flow"]]
        # In order: planner -> holdout -> generator -> validator -> regression -> orchestrator
        assert stages == [
            "planner",
            "holdout",
            "generator",
            "validator",
            "regression",
            "orchestrator",
        ]

    def test_flow_agents_referenced(self):
        """Each agent referenced by a flow stage must exist in agents."""
        data = self._load()
        names = {a["name"] for a in data["agents"]}
        for s in data["flow"]:
            assert s.get("agent") in names, f"flow references undefined agent: {s.get('agent')}"

    def test_orchestrator_is_gate(self):
        """Orchestrator stage should be a gate (gate: true), stopping for manual approval."""
        data = self._load()
        orch_stage = next(s for s in data["flow"] if s["stage"] == "orchestrator")
        assert orch_stage.get("gate") is True

    def test_generator_no_isolated_output(self):
        """Generator stage should have no isolated code directory output (modify directly in existing codebase)."""
        data = self._load()
        gen_stage = next(s for s in data["flow"] if s["stage"] == "generator")
        assert "output" not in gen_stage, "generator should not have isolated output directory"
        assert gen_stage.get("input") == ".df/plan.md"

    def test_holdout_stage_exists(self):
        """Holdout stage generates hidden acceptance scenarios, output .df/holdout.json."""
        data = self._load()
        ho = next(s for s in data["flow"] if s["stage"] == "holdout")
        assert ho.get("output") == ".df/holdout.json"
        assert ho.get("agent") == "df_holdout"

    def test_holdout_isolated_from_generator(self):
        """Holdout output is only passed to validator, never injected into generator (isolation discipline)."""
        data = self._load()
        gen_stage = next(s for s in data["flow"] if s["stage"] == "generator")
        gen_inputs = gen_stage.get("input")
        gen_inputs = gen_inputs if isinstance(gen_inputs, list) else [gen_inputs]
        assert ".df/holdout.json" not in gen_inputs, "holdout must not be injected into generator"
        val_stage = next(s for s in data["flow"] if s["stage"] == "validator")
        val_inputs = val_stage.get("input")
        val_inputs = val_inputs if isinstance(val_inputs, list) else [val_inputs]
        assert ".df/holdout.json" in val_inputs, "validator should consume holdout scenarios"

    def test_regression_stage_exists(self):
        """Regression stage runs existing tests to prevent regressions, aborts on failure."""
        data = self._load()
        reg = next(s for s in data["flow"] if s["stage"] == "regression")
        assert reg.get("agent") == "df_regression"
        assert reg.get("output") == ".df/regression.json"
        assert reg.get("on_error") == "abort"


class TestPluginConfig:
    """Plugin config.yaml declaration completeness."""

    def _load(self):
        path = PLUGIN_DIR / "config.yaml"
        assert path.is_file(), "config.yaml does not exist"
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)

    def test_metadata_complete(self):
        cfg = self._load()
        assert cfg.get("name") == "ai-dark-factory"
        assert cfg.get("description")
        assert cfg.get("version")
        assert cfg.get("builtin") is True

    def test_declares_rules_and_tools_dirs(self):
        cfg = self._load()
        assert cfg.get("rules_load_dirs"), "missing rules_load_dirs"
        assert cfg.get("tool_load_dirs"), "missing tool_load_dirs"

    def test_declares_orchestration(self):
        cfg = self._load()
        orch = cfg.get("orchestration")
        assert isinstance(orch, list) and orch
        entry = orch[0]
        assert entry.get("name") == "dark-factory-pipeline"
        assert entry.get("file")

    def test_declares_replace_map(self):
        cfg = self._load()
        rm = cfg.get("replace_map")
        assert isinstance(rm, dict)
        assert "dark-factory/issue" in rm
        assert "dark-factory/pr" in rm
