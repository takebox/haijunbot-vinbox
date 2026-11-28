# -*- coding: utf-8 -*-
"""Agent runtime config reporting (Issue #115 Agent side) unit tests.

Covers _report_agent_config_change in builtin_input_handler.py and three call sites:
1. perform_switch success reports {"llm_group": new_model_group}
2. switch_proxy_node clearing proxy reports {"proxy_node": ""}
3. switch_proxy_node setting proxy reports {"proxy_node": new_node}
4. <SetConfig> modifying llm_group / proxy_node then reports
5. guard: silently skip when agent_id / master_url not set
"""
import importlib.util
from unittest.mock import Mock

import pytest

# The name builtin_input_handler is shadowed by a function of the same name in the package (re-export),
# so direct import gets the function not the module; here we use importlib to load the real module from source path.
_SPEC = importlib.util.spec_from_file_location(
    "bih_under_test", "src/haijunbot/haijunbot_agent/builtin_input_handler.py"
)
assert _SPEC is not None and _SPEC.loader is not None
_BIH = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_BIH)


@pytest.fixture
def bih():
    """Return builtin_input_handler module object."""
    return _BIH


@pytest.fixture
def fake_jglobals(monkeypatch, bih):
    """Construct jglobals with agent_id / master_url, and patch into module."""
    import haijunbot.haijunbot_utils.globals as jglobals

    jglobals.agent_id = "agent-test-1"
    jglobals.master_url = "http://127.0.0.1:8000"
    yield jglobals
    # Restore to avoid polluting other tests
    jglobals.agent_id = None
    jglobals.master_url = None


def _patch_gateway(monkeypatch, bih, result=None):
    """Patch lazily imported GatewayManagerTool, returning a mock of its _request_gateway.

    Both _report_agent_config_change and switch_proxy_node use
    `from haijunbot.haijunbot_tools.gateway_manager import GatewayManagerTool` lazy import,
    so the patch target is GatewayManagerTool inside the gateway_manager module.

    GatewayManagerTool.check() is a static method call (called directly on the class), while
    GatewayManagerTool() returns an instance; therefore use a class that supports both.
    """
    import haijunbot.haijunbot_tools.gateway_manager as gm

    class _FakeGateway:
        _instance = None

        def __new__(cls):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

        def __init__(self):
            if not hasattr(self, "_request_gateway"):
                self._request_gateway = Mock(
                    return_value=result or {"success": True}
                )
            if not hasattr(self, "_list_nodes"):
                self._list_nodes = Mock(
                    return_value={
                        "success": True,
                        "stdout": '{"nodes": []}',
                    }
                )

        @staticmethod
        def check():
            return True

    fake_tool = _FakeGateway()
    monkeypatch.setattr(gm, "GatewayManagerTool", _FakeGateway)
    return fake_tool


class TestReportAgentConfigChange:
    def test_skips_when_agent_id_missing(self, bih, monkeypatch):
        """Silently return when agent_id is not set, no request made."""
        import haijunbot.haijunbot_utils.globals as jglobals

        jglobals.agent_id = None
        jglobals.master_url = "http://127.0.0.1:8000"
        fake_tool = _patch_gateway(monkeypatch, bih)
        bih._report_agent_config_change({"llm_group": "g"})
        fake_tool._request_gateway.assert_not_called()
        jglobals.agent_id = None
        jglobals.master_url = None

    def test_skips_when_master_url_missing(self, bih, monkeypatch):
        """Silently return when master_url is not set, no request made."""
        import haijunbot.haijunbot_utils.globals as jglobals

        jglobals.agent_id = "agent-test-1"
        jglobals.master_url = None
        fake_tool = _patch_gateway(monkeypatch, bih)
        bih._report_agent_config_change({"llm_group": "g"})
        fake_tool._request_gateway.assert_not_called()
        jglobals.agent_id = None

    def test_skips_when_updates_empty(self, bih, monkeypatch, fake_jglobals):
        """Silently return when updates is empty."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        bih._report_agent_config_change({})
        fake_tool._request_gateway.assert_not_called()

    def test_sends_patch_with_updates(self, bih, monkeypatch, fake_jglobals):
        """Normally reports PATCH /api/agents/{id}, body is updates."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        bih._report_agent_config_change({"llm_group": "new_group"})
        fake_tool._request_gateway.assert_called_once()
        args, kwargs = fake_tool._request_gateway.call_args
        assert args[0] == "PATCH"
        assert args[1] == "/api/agents/agent-test-1"
        assert kwargs["json_data"] == {"llm_group": "new_group"}

    def test_failure_is_silent(self, bih, monkeypatch, fake_jglobals):
        """Reporting failure does not raise exception (silent degradation)."""
        _patch_gateway(
            monkeypatch, bih, result={"success": False, "error": "boom"}
        )
        bih._report_agent_config_change({"llm_group": "g"})  # Should not raise


class TestPerformSwitchReports:
    def test_reports_llm_group_on_success(self, bih, monkeypatch, fake_jglobals):
        """perform_switch reports new model group on success."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        agent = Mock()
        agent.model = Mock()
        agent.session = Mock()
        agent.model.get_messages.return_value = []
        # switch_platform_type success
        monkeypatch.setattr(bih, "switch_platform_type", lambda *a, **k: True)
        # set_llm_group from haijunbot_utils.config needs patching
        from haijunbot.haijunbot_utils import config as config_module

        monkeypatch.setattr(config_module, "set_llm_group", lambda g: None)
        assert bih.perform_switch(agent, "new_group") is True
        fake_tool._request_gateway.assert_called_once()
        args, kwargs = fake_tool._request_gateway.call_args
        assert kwargs["json_data"] == {"llm_group": "new_group"}

    def test_no_report_on_failure(self, bih, monkeypatch, fake_jglobals):
        """perform_switch does not report on failure."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        agent = Mock()
        agent.model = Mock()
        agent.session = Mock()
        agent.model.get_messages.return_value = []
        monkeypatch.setattr(bih, "switch_platform_type", lambda *a, **k: False)
        from haijunbot.haijunbot_utils import config as config_module

        monkeypatch.setattr(config_module, "set_llm_group", lambda g: None)
        assert bih.perform_switch(agent, "new_group") is False
        fake_tool._request_gateway.assert_not_called()


class TestSwitchProxyNodeReports:
    def test_reports_clear_proxy(self, bih, monkeypatch, fake_jglobals):
        """Reports {"proxy_node": ""} after clearing proxy."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        import haijunbot.haijunbot_utils.globals as jglobals

        jglobals.proxy_node = "node-1"
        monkeypatch.setattr(bih, "switch_platform_type", lambda *a, **k: True)
        monkeypatch.setattr(
            bih, "get_single_line_input", lambda prompt: ""
        )
        monkeypatch.setattr(
            bih, "get_platform_type_from_agent", lambda a: "normal"
        )
        agent = Mock()
        assert bih.switch_proxy_node(agent) is True
        fake_tool._request_gateway.assert_called_once()
        args, kwargs = fake_tool._request_gateway.call_args
        assert kwargs["json_data"] == {"proxy_node": ""}
        jglobals.proxy_node = None

    def test_reports_set_proxy(self, bih, monkeypatch, fake_jglobals):
        """Reports {"proxy_node": new_node} after setting proxy."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        import haijunbot.haijunbot_utils.globals as jglobals

        jglobals.proxy_node = None
        # Make _list_nodes return a node, user inputs index 1
        fake_tool._list_nodes.return_value = {
            "success": True,
            "stdout": '{"nodes": [{"node_id": "node-2"}]}',
        }
        monkeypatch.setattr(bih, "switch_platform_type", lambda *a, **k: True)
        monkeypatch.setattr(
            bih, "get_single_line_input", lambda prompt: "1"
        )
        monkeypatch.setattr(
            bih, "get_platform_type_from_agent", lambda a: "normal"
        )
        agent = Mock()
        assert bih.switch_proxy_node(agent) is True
        fake_tool._request_gateway.assert_called_once()
        args, kwargs = fake_tool._request_gateway.call_args
        assert kwargs["json_data"] == {"proxy_node": "node-2"}
        jglobals.proxy_node = None


class TestSetConfigReports:
    def test_setconfig_reports_llm_group(self, bih, monkeypatch, fake_jglobals):
        """Reports after <SetConfig> modifies llm_group."""
        fake_tool = _patch_gateway(monkeypatch, bih)
        config = {}
        monkeypatch.setattr(bih, "get_global_config_data", lambda: config)
        # _set_nested_config real implementation writes to config
        result = bih._set_nested_config(config, "llm_group", "new_group")
        assert result[0] is True
        # Simulate the call from SetConfig branch inside builtin_input_handler
        bih._report_agent_config_change({"llm_group": "new_group"})
        fake_tool._request_gateway.assert_called_once()
        args, kwargs = fake_tool._request_gateway.call_args
        assert kwargs["json_data"] == {"llm_group": "new_group"}
