# -*- coding: utf-8 -*-
"""Unit tests for builtin_rules entry scanning"""

import pytest

from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rule_entries
from haijunbot.haijunbot_agent.builtin_rules import list_builtin_rules


def test_entries_are_subset_of_full_rules():
    full = {n.lower() for n in list_builtin_rules()}
    if not full:
        pytest.skip("builtin rules data directory is not present in this checkout")
    entries = list_builtin_rule_entries()
    if not entries:
        pytest.skip("no builtin rule entries with front matter in this checkout")
    assert all(e.lower() in full for e in entries)


def test_removed_noise_categories_not_listed():
    entries = list_builtin_rule_entries()
    # Cleaned-up low-value/inert directories should no longer be auto-selection candidates
    for marker in ("superpowers", "agent_personality", "investment_analysis", "technical_analysis"):
        assert not any(marker in e for e in entries), marker
