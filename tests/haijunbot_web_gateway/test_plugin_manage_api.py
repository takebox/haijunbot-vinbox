# -*- coding: utf-8 -*-
"""Plugin management HTTP API integration tests (master local node)."""

import json
import os
from pathlib import Path

# Must set environment variables before importing haijunbot modules to avoid triggering interactive configuration
os.environ["HAIJUNBOT_SKIP_INTERACTIVE_CONFIG"] = "1"

import pytest
from fastapi.testclient import TestClient

from haijunbot.haijunbot_web_gateway.app import create_app

TEST_AUTH_TOKEN = "test-token-for-unit-tests"
os.environ["HAIJUNBOT_AUTH_TOKEN"] = TEST_AUTH_TOKEN


@pytest.fixture()
def isolated_data_dir(tmp_path, monkeypatch):
    """Point HAIJUNBOT_DATA_DIR to a temporary directory to isolate plugin installation side effects."""
    data_dir = tmp_path / "haijunbot-data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HAIJUNBOT_DATA_DIR", str(data_dir))
    return data_dir


@pytest.fixture()
def client(isolated_data_dir):
    app = create_app()
    return TestClient(app)


def _auth_headers(token: str = TEST_AUTH_TOKEN):
    return {"Authorization": f"Bearer {token}"}


def _make_plugin(plugin_dir: Path, name: str, version: str = "1.0.0") -> None:
    """Construct a minimal plugin directory (with config.yaml + frontend assets)."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "config.yaml").write_text(
        json.dumps(
            {
                "name": name,
                "version": version,
                "description": "test plugin",
                "frontend": {
                    "admin_tabs": [
                        {
                            "id": "my-tab",
                            "label": "My Tab",
                            "entry": "admin.js",
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    (plugin_dir / "admin.js").write_text(
        "window.__pluginTest__ = true;", encoding="utf-8"
    )


def test_list_plugins_empty(client):
    """When there are no external plugins, list only returns built-in plugins (all builtin are True)."""
    resp = client.get("/api/plugins", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    plugins = body["data"]["plugins"]
    assert len(plugins) >= 1
    assert all(p["builtin"] is True for p in plugins)


def test_list_plugins_with_installed(client, isolated_data_dir):
    """When plugins are installed, list returns structured information (including built-in plugins)."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "my-plugin", "my-plugin", "2.1.0")

    resp = client.get("/api/plugins", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    plugins = {p["name"]: p for p in body["data"]["plugins"]}
    assert plugins["my-plugin"]["name"] == "my-plugin"
    assert plugins["my-plugin"]["version"] == "2.1.0"
    assert plugins["my-plugin"]["installed"] is True
    assert plugins["my-plugin"]["builtin"] is False
    assert plugins["my-plugin"]["frontend"]["admin_tabs"][0]["id"] == "my-tab"


def test_list_plugins_node_id_query(client, isolated_data_dir):
    """list supports node_id query parameter (master local node)."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "p1", "p1")

    resp = client.get("/api/plugins?node_id=master", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["node_id"] == "master"
    names = {p["name"] for p in body["data"]["plugins"]}
    assert "p1" in names


def test_install_plugin(client, isolated_data_dir):
    """install installs a plugin from a local directory."""
    source = Path(isolated_data_dir) / "src-plugin"
    _make_plugin(source, "installed-plugin", "1.0.0")

    resp = client.post(
        "/api/plugins/install",
        json={"node_id": "master", "source": str(source)},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True

    installed = Path(isolated_data_dir) / "plugins" / "installed-plugin"
    assert installed.exists()
    assert (installed / "config.yaml").exists()


def test_install_plugin_missing_source(client):
    """install returns INVALID_REQUEST when source is missing."""
    resp = client.post(
        "/api/plugins/install",
        json={"node_id": "master", "source": ""},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_REQUEST"


def test_uninstall_plugin(client, isolated_data_dir):
    """uninstall removes an installed plugin."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "to-remove", "to-remove")

    resp = client.post(
        "/api/plugins/to-remove/uninstall",
        json={"node_id": "master"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert not (plugins_dir / "to-remove").exists()


def test_uninstall_nonexistent_plugin(client):
    """Uninstalling a nonexistent plugin returns failure."""
    resp = client.post(
        "/api/plugins/nope/uninstall",
        json={"node_id": "master"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False


def test_serve_plugin_frontend(client, isolated_data_dir):
    """serve_frontend reads plugin frontend assets."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "fe-plugin", "fe-plugin")

    resp = client.get(
        "/api/plugins/master/fe-plugin/frontend/admin.js",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["content"] == "window.__pluginTest__ = true;"
    assert body["data"]["content_type"] == "application/javascript"


def test_serve_plugin_frontend_not_found(client, isolated_data_dir):
    """serve_frontend returns failure when requesting a nonexistent file."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "fe-plugin", "fe-plugin")

    resp = client.get(
        "/api/plugins/master/fe-plugin/frontend/missing.js",
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False


def test_permission_denied_for_non_admin(client, isolated_data_dir):
    """Non-admin users are denied access to the plugin management API."""
    resp = client.get("/api/plugins", headers=_auth_headers("wrong-token"))
    assert resp.status_code == 401


def _make_builtin_plugin(plugin_dir: Path, name: str) -> None:
    """Construct a built-in plugin directory (config.yaml contains builtin: true + capabilities)."""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "config.yaml").write_text(
        json.dumps(
            {
                "name": name,
                "version": "1.0.0",
                "description": "builtin plugin",
                "builtin": True,
                "rules_load_dirs": ["{{plugin_dir}}/rules"],
                "capabilities": [
                    {"name": "event hook on_task_start", "description": "Triggered on task start"},
                    {"name": "@mycmd", "description": "Built-in command"},
                ],
            }
        ),
        encoding="utf-8",
    )


def test_list_plugins_builtin_flag(client, isolated_data_dir):
    """list returns the builtin flag and capabilities manifest."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin(plugins_dir / "normal", "normal")
    _make_builtin_plugin(plugins_dir / "builtin-p", "builtin-p")

    resp = client.get("/api/plugins", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    plugins = {p["name"]: p for p in body["data"]["plugins"]}

    assert plugins["normal"]["builtin"] is False
    assert plugins["builtin-p"]["builtin"] is True
    caps = plugins["builtin-p"]["capabilities"]
    assert any(c["type"] == "rules" for c in caps)
    assert any(c["type"] == "custom" and c["name"] == "@mycmd" for c in caps)


def test_uninstall_builtin_plugin_rejected(client, isolated_data_dir):
    """Uninstalling a built-in plugin is rejected, directory is retained."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_builtin_plugin(plugins_dir / "builtin-p", "builtin-p")

    resp = client.post(
        "/api/plugins/builtin-p/uninstall",
        json={"node_id": "master"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert (plugins_dir / "builtin-p").exists()


def test_upgrade_builtin_plugin_rejected(client, isolated_data_dir):
    """Upgrading a built-in plugin is rejected."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_builtin_plugin(plugins_dir / "builtin-p", "builtin-p")

    resp = client.post(
        "/api/plugins/builtin-p/upgrade",
        json={"node_id": "master"},
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert (plugins_dir / "builtin-p").exists()


def _make_plugin_with_api(plugin_dir: Path, name: str) -> None:
    """Construct a plugin with a plugin/api.py private function layer."""
    _make_plugin(plugin_dir, name)
    api_dir = plugin_dir / "plugin"
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "api.py").write_text(
        """def hello(name="world"):
    return {"success": True, "message": f"hello {name}"}

def secret():
    return {"success": True, "message": "secret"}

PUBLIC_FUNCTIONS = ["hello"]
""",
        encoding="utf-8",
    )


def test_list_plugin_functions(client, isolated_data_dir):
    """List plugin private functions (PUBLIC_FUNCTIONS whitelist)."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin_with_api(plugins_dir / "fn-plugin", "fn-plugin")

    resp = client.get("/api/plugins/master/functions", headers=_auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    plugins = body["data"]["plugins"]
    fn_plugin = next((p for p in plugins if p["plugin"] == "fn-plugin"), None)
    assert fn_plugin is not None
    assert "hello" in fn_plugin["functions"]
    assert "secret" not in fn_plugin["functions"]


def test_call_plugin_function(client, isolated_data_dir):
    """Call plugin private functions (within whitelist)."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin_with_api(plugins_dir / "fn-plugin", "fn-plugin")

    resp = client.post(
        "/api/plugins/master/function-call",
        json={
            "plugin": "fn-plugin",
            "function": "hello",
            "arguments": {"name": "haijunbot"},
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["success"] is True
    assert body["result"]["message"] == "hello haijunbot"


def test_call_plugin_function_not_in_whitelist(client, isolated_data_dir):
    """Calling a function not in the whitelist is rejected."""
    plugins_dir = Path(isolated_data_dir) / "plugins"
    _make_plugin_with_api(plugins_dir / "fn-plugin", "fn-plugin")

    resp = client.post(
        "/api/plugins/master/function-call",
        json={
            "plugin": "fn-plugin",
            "function": "secret",
            "arguments": {},
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FUNCTION_NOT_ALLOWED"


def test_call_plugin_function_plugin_not_found(client, isolated_data_dir):
    """Calling a function on a nonexistent plugin returns failure."""
    resp = client.post(
        "/api/plugins/master/function-call",
        json={
            "plugin": "no-such-plugin",
            "function": "hello",
            "arguments": {},
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "FUNCTION_API_NOT_FOUND"
