"""LSP server manager tests"""

import asyncio
import os
import sys

# Add project path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from haijunbot.haijunbot_lsp.server_manager import LSPServerManager, LSPServerInstance
import pytest


@pytest.mark.asyncio
async def test_server_instance_creation():
    """Test server instance creation"""
    project_path = os.getcwd()
    server = LSPServerInstance(language="python", project_path=project_path)

    assert server.language == "python"
    assert server.project_path == project_path
    assert server.status == "stopped"
    assert server.process is None
    assert server.client is None


@pytest.mark.asyncio
async def test_server_manager_singleton():
    """Test server manager singleton pattern"""
    manager1 = LSPServerManager()
    manager2 = LSPServerManager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_server_start():
    """Test server start"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    server = await manager.get_server("python", project_path)

    assert server.status == "running"
    assert server.is_alive()
    assert server.process is not None
    assert server.client is not None
    assert server.process.pid > 0

    # Cleanup
    await manager.stop_all()


@pytest.mark.asyncio
async def test_server_reuse():
    """Test server reuse"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    # First acquisition
    server1 = await manager.get_server("python", project_path)
    pid1 = server1.process.pid

    # Second acquisition (should reuse)
    server2 = await manager.get_server("python", project_path)
    pid2 = server2.process.pid

    assert server1 is server2
    assert pid1 == pid2

    # Cleanup
    await manager.stop_all()


@pytest.mark.asyncio
async def test_server_stop():
    """Test server stop"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    # Start server
    server = await manager.get_server("python", project_path)

    # Stop server
    await manager.stop_server("python", project_path)

    # Verify server has stopped
    assert not server.is_alive()
    assert server.status == "stopped"


@pytest.mark.asyncio
async def test_stop_all():
    """Test stopping all servers"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    # Start server
    await manager.get_server("python", project_path)

    # Stop all
    await manager.stop_all()

    # Verify all servers have stopped
    status = manager.get_status()
    assert len(status) == 0


@pytest.mark.asyncio
async def test_get_status():
    """Test getting status"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    # Initial state
    status = manager.get_status()
    assert len(status) == 0

    # Start server
    await manager.get_server("python", project_path)

    # Get status
    status = manager.get_status()
    assert len(status) == 1
    key = "python:" + project_path
    assert key in status
    assert status[key]["language"] == "python"
    assert status[key]["status"] == "running"
    assert status[key]["is_alive"] is True

    # Cleanup
    await manager.stop_all()


@pytest.mark.asyncio
async def test_different_projects():
    """Test that different projects use different servers"""
    project_path1 = os.getcwd()
    project_path2 = "/tmp"
    manager = LSPServerManager()

    # Start servers for two different projects
    server1 = await manager.get_server("python", project_path1)
    server2 = await manager.get_server("python", project_path2)

    # Verify they are different instances
    assert server1 is not server2
    assert server1.process.pid != server2.process.pid

    # Cleanup
    await manager.stop_all()


@pytest.mark.asyncio
async def test_update_activity():
    """Test activity time update"""
    project_path = os.getcwd()
    manager = LSPServerManager()

    server = await manager.get_server("python", project_path)

    # Get initial activity time
    initial_activity = server.last_activity

    # Wait a short time
    await asyncio.sleep(0.1)

    # Update activity time
    await manager.get_server("python", project_path)

    # Verify activity time has been updated
    assert server.last_activity > initial_activity

    # Cleanup
    await manager.stop_all()


@pytest.mark.asyncio
async def test_is_expired():
    """Test timeout check"""
    server = LSPServerInstance(language="python", project_path=".")

    # Initial state (stopped status does not count as expired)
    assert not server.is_expired(timeout=30.0)

    # Set to running status
    server.status = "running"

    # Modify activity time to the past
    import time

    server.last_activity = time.time() - 100

    # Check timeout
    assert server.is_expired(timeout=30.0)
    assert not server.is_expired(timeout=200.0)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
