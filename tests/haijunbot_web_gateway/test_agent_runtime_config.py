# -*- coding: utf-8 -*-
"""Agent runtime configuration update (update_agent_runtime_config) unit tests.

Covers the gateway-side implementation for Issue #115:
1. Update model group (llm_group) and persist
2. Update proxy node (proxy_node) and persist
3. Clear proxy node (proxy_node="") so frontend shows no proxy in use
4. Nonexistent Agent raises KeyError
5. When updating only one field, the other remains unchanged
"""
import json

import pytest

from haijunbot.haijunbot_web_gateway.agent_manager import AgentInfo, AgentManager


def _make_manager(tmp_path, monkeypatch) -> AgentManager:
    """Construct an AgentManager with isolated data directory and inject an AgentInfo."""
    data_dir = tmp_path / "haijunbot_data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(data_dir))
    monkeypatch.setattr(
        AgentManager,
        "PERSISTENCE_FILE",
        data_dir / "gateway" / ".haijunbot_agents.json",
    )
    manager = AgentManager()
    agent = AgentInfo(
        agent_id="agent-test-1",
        agent_type="agent",
        pid=0,
        port=10000,
        working_dir=str(tmp_path),
        process=None,
        name="test-agent",
        llm_group="default",
        proxy_node=None,
    )
    manager._agents[agent.agent_id] = agent
    return manager


def test_update_llm_group(tmp_path, monkeypatch):
    """After updating model group, both in-memory and persisted file should reflect the change."""
    manager = _make_manager(tmp_path, monkeypatch)
    result = manager.update_agent_runtime_config(
        "agent-test-1", llm_group="new_group"
    )
    assert result["llm_group"] == "new_group"
    assert manager._agents["agent-test-1"].llm_group == "new_group"
    # Persisted file has been written
    saved = json.loads(AgentManager.PERSISTENCE_FILE.read_text(encoding="utf-8"))
    assert saved[0]["llm_group"] == "new_group"


def test_update_proxy_node(tmp_path, monkeypatch):
    """After updating proxy node, both in-memory and persisted file should reflect the change."""
    manager = _make_manager(tmp_path, monkeypatch)
    result = manager.update_agent_runtime_config(
        "agent-test-1", proxy_node="node-2"
    )
    assert result["proxy_node"] == "node-2"
    assert manager._agents["agent-test-1"].proxy_node == "node-2"
    saved = json.loads(AgentManager.PERSISTENCE_FILE.read_text(encoding="utf-8"))
    assert saved[0]["proxy_node"] == "node-2"


def test_clear_proxy_node(tmp_path, monkeypatch):
    """After clearing proxy node (proxy_node=""), frontend v-if treats it as no proxy in use."""
    manager = _make_manager(tmp_path, monkeypatch)
    manager._agents["agent-test-1"].proxy_node = "node-1"
    result = manager.update_agent_runtime_config("agent-test-1", proxy_node="")
    assert result["proxy_node"] == ""
    assert manager._agents["agent-test-1"].proxy_node == ""
    saved = json.loads(AgentManager.PERSISTENCE_FILE.read_text(encoding="utf-8"))
    assert saved[0]["proxy_node"] == ""
    # Frontend AgentSidebar.vue uses v-if="agent.proxy_node", empty string is not displayed
    assert not saved[0]["proxy_node"]


def test_update_only_one_field_preserves_other(tmp_path, monkeypatch):
    """When updating only llm_group, proxy_node remains unchanged."""
    manager = _make_manager(tmp_path, monkeypatch)
    manager._agents["agent-test-1"].proxy_node = "node-1"
    result = manager.update_agent_runtime_config(
        "agent-test-1", llm_group="new_group"
    )
    assert result["llm_group"] == "new_group"
    assert result["proxy_node"] == "node-1"


def test_update_nonexistent_agent_raises_keyerror(tmp_path, monkeypatch):
    """Updating a nonexistent Agent should raise KeyError."""
    manager = _make_manager(tmp_path, monkeypatch)
    with pytest.raises(KeyError):
        manager.update_agent_runtime_config("agent-not-exist", llm_group="x")
