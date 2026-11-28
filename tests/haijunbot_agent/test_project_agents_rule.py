# -*- coding: utf-8 -*-
"""RulesManager project-level AGENTS.md/HAIJUN.md compatible loading unit tests"""

import os
import tempfile
from unittest.mock import patch

from haijunbot.haijunbot_agent.rules_manager import RulesManager


def _make_mgr(root_dir):
    return RulesManager(root_dir)


def test_agents_md_loaded():
    """Auto-load AGENTS.md as project:agents rule when present at repo root"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# AGENTS\n\nThis project uses Python.\n")
        mgr = _make_mgr(d)
        assert "project:agents" in mgr.loaded_rules
        content = mgr.get_loaded_rules_content()
        assert "This project uses Python" in content


def test_haijun_md_fallback():
    """Fall back to reading HAIJUN.md when AGENTS.md is absent"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "HAIJUN.md"), "w", encoding="utf-8") as f:
            f.write("# HAIJUN\n\nUse TDD.\n")
        mgr = _make_mgr(d)
        assert "project:agents" in mgr.loaded_rules
        assert "Use TDD" in mgr.get_loaded_rules_content()


def test_agents_precedence_over_haijun():
    """AGENTS.md takes priority when both AGENTS.md and HAIJUN.md exist"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("AGENTS content")
        with open(os.path.join(d, "HAIJUN.md"), "w", encoding="utf-8") as f:
            f.write("HAIJUN content")
        mgr = _make_mgr(d)
        content = mgr.get_loaded_rules_content()
        assert "AGENTS content" in content
        assert "HAIJUN content" not in content


def test_no_file_not_loaded():
    """Do not load project:agents when AGENTS.md/HAIJUN.md are absent at repo root"""
    with tempfile.TemporaryDirectory() as d:
        mgr = _make_mgr(d)
        assert "project:agents" not in mgr.loaded_rules


def test_coexist_with_rule_md():
    """Both merge and inject when coexisting with .haijunbot/rules/rule.md, no conflict"""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".haijunbot", "rules"))
        with open(
            os.path.join(d, ".haijunbot", "rules", "rule.md"), "w", encoding="utf-8"
        ) as f:
            f.write("Project rule.md content")
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("AGENTS content")
        mgr = _make_mgr(d)
        content = mgr.get_loaded_rules_content()
        assert "Project rule.md content" in content
        assert "AGENTS content" in content


def test_rule_file_path_agents():
    """get_rule_file_path returns actual AGENTS.md path for project:agents"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("content")
        mgr = _make_mgr(d)
        path = mgr.get_rule_file_path("project:agents")
        assert path.endswith("AGENTS.md")


def test_rule_file_path_agents_fallback_haijun():
    """get_rule_file_path returns HAIJUN.md path when AGENTS.md is absent"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "HAIJUN.md"), "w", encoding="utf-8") as f:
            f.write("content")
        mgr = _make_mgr(d)
        path = mgr.get_rule_file_path("project:agents")
        assert path.endswith("HAIJUN.md")


def test_large_agents_truncated_by_token_budget():
    """Oversized AGENTS.md is truncated by 80% budget of model max input tokens"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("# AGENTS\n\n" + "x" * 20000 + "\nEND")
        with patch(
            "haijunbot.haijunbot_utils.config.get_max_input_token_count", return_value=1000
        ):
            mgr = _make_mgr(d)
        content = mgr.get_loaded_rules_content()
        assert "truncated by token budget" in content


def test_injectable_content():
    """get_injectable_rules_content can inject AGENTS.md body"""
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "AGENTS.md"), "w", encoding="utf-8") as f:
            f.write("## Specifications\n\nFollow TDD.\n")
        mgr = _make_mgr(d)
        inj = mgr.get_injectable_rules_content()
        assert "Follow TDD" in inj
