# -*- coding: utf-8 -*-
"""rules_manager strong-trigger cheap determination unit tests"""

from unittest.mock import patch

from haijunbot.haijunbot_agent.rules_manager import RulesManager, _preselect_rules


class _FakeCheap:
    def __init__(self, response):
        self.response = response
        self.suppressed = None

    def set_suppress_output(self, v):
        self.suppressed = v

    def chat_until_success(self, prompt):
        return self.response


def test_match_task_cheap_uses_catalog_and_parses(monkeypatch):
    from haijunbot.haijunbot_platform.registry import PlatformRegistry

    mgr = object.__new__(RulesManager)
    mgr._catalog_cache = [
        ["builtin:security.md", "Security review"],
        ["builtin:tdd.md", "Test-driven development"],
    ]
    cheap = _FakeCheap("<NUM>2,1</NUM>")

    class _Reg:
        def create_platform(self, platform_type="cheap"):
            return cheap

    monkeypatch.setattr(
        PlatformRegistry, "get_global_platform_registry", lambda: _Reg()
    )
    out = mgr.match_task_cheap("Help me do a security code review", max_rules=3)
    assert out == ["builtin:tdd.md", "builtin:security.md"]


def test_match_task_cheap_no_cheap_returns_empty(monkeypatch):
    from haijunbot.haijunbot_platform.registry import PlatformRegistry

    mgr = object.__new__(RulesManager)
    mgr._catalog_cache = [["builtin:security.md", "Security review"]]

    class _NoCheap:
        def create_platform(self, platform_type="cheap"):
            return None

    monkeypatch.setattr(
        PlatformRegistry, "get_global_platform_registry", lambda: _NoCheap()
    )
    assert mgr.match_task_cheap("Hello") == []


def test_match_task_cheap_none_answer_returns_empty(monkeypatch):
    from haijunbot.haijunbot_platform.registry import PlatformRegistry

    mgr = object.__new__(RulesManager)
    mgr._catalog_cache = [["builtin:security.md", "Security review"]]
    cheap = _FakeCheap("<NUM>none</NUM>")

    class _Reg:
        def create_platform(self, platform_type="cheap"):
            return cheap

    monkeypatch.setattr(
        PlatformRegistry, "get_global_platform_registry", lambda: _Reg()
    )
    assert mgr.match_task_cheap("The weather is nice today") == []


class TestPreselectRules:
    """Tests for _preselect_rules pre-filter function"""

    def _make_rules(self):
        rules = [
            "builtin:security.md",
            "builtin:tdd.md",
            "builtin:deploy.md",
            "builtin:refactor.md",
        ]
        desc = {
            "builtin:security.md": "Security code review",
            "builtin:tdd.md": "Test-driven development",
            "builtin:deploy.md": "Deploy to production",
            "builtin:refactor.md": "Legacy code refactoring",
        }
        return rules, desc

    def test_match_relevant_rules(self):
        """Keywords should match relevant rules (name+description), filter out irrelevant rules"""
        rules, desc = self._make_rules()
        result = _preselect_rules("Help me do a security code review", rules, desc)
        assert "builtin:security.md" in result
        assert "builtin:tdd.md" not in result  # Irrelevant rule filtered out

    def test_match_by_description(self):
        """Should also match when keywords hit description rather than rule name"""
        rules, desc = self._make_rules()
        # "deploy" only appears in deploy's description, not in rule name
        result = _preselect_rules("I want to deploy to production", rules, desc)
        assert "builtin:deploy.md" in result

    def test_no_match_returns_all(self):
        """Fall back to full set when no matches, avoid missing selections"""
        rules, desc = self._make_rules()
        result = _preselect_rules("Completely unrelated random words xyz", rules, desc)
        assert result == rules

    def test_no_keywords_returns_all(self):
        """Fall back to full set when task description has no valid keywords"""
        rules, desc = self._make_rules()
        result = _preselect_rules("the a is", rules, desc)
        assert result == rules

    def test_top_n_truncation(self):
        """Truncate to top_n when exceeding"""
        rules = [f"builtin:rule{i}.md" for i in range(100)]
        desc = {r: f"topic{i}" for i, r in enumerate(rules)}
        result = _preselect_rules("topic", rules, desc, top_n=10)
        assert len(result) == 10

    def test_exception_returns_all(self):
        """Fall back to full set on exception, ensuring no change to existing behavior"""
        rules, desc = self._make_rules()
        with patch(
            "haijunbot.haijunbot_agent.rules_manager._RULE_PRESELECT_STOP_WORDS",
            new=None,  # Trigger exception
        ):
            result = _preselect_rules("deploy", rules, desc)
            assert result == rules


class TestSelectRuleByTaskPreselect:
    """Tests for select_rule_task integration with pre-filter: candidates passed to LLM should be pre-filtered subset"""

    def _make_mgr(self, monkeypatch):
        mgr = object.__new__(RulesManager)
        mgr._catalog_cache = []

        # Full rule set: 4 entries, only security is related to "security review"
        all_rules = {
            "builtin": ["builtin:security.md", "builtin:tdd.md"],
            "files": ["project:deploy.md", "project:refactor.md"],
        }
        desc = {
            "builtin:security.md": "Security code review",
            "builtin:tdd.md": "Test-driven development",
            "project:deploy.md": "Deploy to production",
            "project:refactor.md": "Legacy code refactoring",
        }

        monkeypatch.setattr(mgr, "get_all_available_rule_names", lambda: all_rules)
        monkeypatch.setattr(mgr, "get_rule_file_path", lambda name: "--")
        monkeypatch.setattr(mgr, "_extract_rule_description", lambda path: "")
        monkeypatch.setattr(mgr, "get_rule_preview", lambda name: desc.get(name, "--"))
        return mgr, desc

    def test_prescreen_reduces_candidates_to_llm(self, monkeypatch):
        """Candidates passed to decide_choice after pre-filtering should only contain relevant rules"""
        mgr, desc = self._make_mgr(monkeypatch)

        captured = {}

        def fake_decide_choice(task, candidates, fallback, *, max_select=3):
            captured["candidates"] = candidates
            return ["builtin:security.md"]

        monkeypatch.setattr(
            "haijunbot.haijunbot_agent.rules_manager.decide_choice",
            fake_decide_choice,
        )

        result = mgr.select_rule_by_task("Help me do a security code review")

        assert result == ["builtin:security.md"]
        # Candidates should be reduced after pre-filtering and contain relevant rules
        assert "builtin:security.md" in captured["candidates"]
        assert len(captured["candidates"]) < 4  # Reduced from 4 entries

    def test_no_match_falls_back_to_all(self, monkeypatch):
        """Fall back to full set when no matches, candidates not reduced"""
        mgr, desc = self._make_mgr(monkeypatch)

        captured = {}

        def fake_decide_choice(task, candidates, fallback, *, max_select=3):
            captured["candidates"] = candidates
            return ["builtin:security.md"]

        monkeypatch.setattr(
            "haijunbot.haijunbot_agent.rules_manager.decide_choice",
            fake_decide_choice,
        )

        mgr.select_rule_by_task("Completely unrelated random words xyz")

        # No match falls back to full set, all 4 candidates preserved
        assert len(captured["candidates"]) == 4
