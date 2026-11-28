# -*- coding: utf-8 -*-
"""Task List Manager dependency validation feature tests"""

import pytest
from unittest.mock import Mock
from haijunbot.haijunbot_agent.task_list import TaskStatus
from haijunbot.haijunbot_tools.task_list_manager import (
    task_list_manager,
    DependencyNotFoundError,
    DependencyNotCompletedError,
    DependencyFailedError,
)


class TestDependencyValidation:
    """Tests for dependency validation feature"""

    def setup_method(self):
        """Set up test environment"""
        self.tool = task_list_manager()
        self.mock_agent = Mock()
        self.mock_task_list_manager = Mock()
        self.mock_agent.task_list_manager = self.mock_task_list_manager
        self.mock_agent.name = "test_agent"

        # Set default user_data behavior
        self.mock_agent.get_user_data.return_value = None
        self.mock_agent.set_user_data.return_value = None

    def test_validate_dependencies_status_no_dependencies(self):
        """Test task with no dependencies"""
        # Create task without dependencies
        mock_task = Mock()
        mock_task.dependencies = []

        # Should return normally without raising exception
        self.tool._validate_dependencies_status(
            task_list_manager=self.mock_task_list_manager,
            task_list_id="test_list_id",
            task=mock_task,
            agent_id="test_agent",
            is_main_agent=True,
        )

    def test_validate_dependencies_status_completed_dependency(self):
        """Test when dependency task is completed"""
        # Create completed dependency task
        mock_task = Mock()
        mock_task.dependencies = ["dep_task_1"]

        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.COMPLETED

        self.mock_task_list_manager.get_task_detail.return_value = (
            mock_dep_task,
            True,
            None,
        )

        # Should return normally without raising exception
        self.tool._validate_dependencies_status(
            task_list_manager=self.mock_task_list_manager,
            task_list_id="test_list_id",
            task=mock_task,
            agent_id="test_agent",
            is_main_agent=True,
        )

    def test_validate_dependencies_status_dependency_not_found(self):
        """Test when dependency task does not exist"""
        mock_task = Mock()
        mock_task.dependencies = ["non_existent_task"]

        self.mock_task_list_manager.get_task_detail.return_value = (
            None,
            False,
            "Task does not exist",
        )

        # Should raise DependencyNotFoundError
        with pytest.raises(DependencyNotFoundError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        assert "Dependency task 'non_existent_task' does not exist" in str(exc_info.value)

    def test_validate_dependencies_status_dependency_failed(self):
        """Test when dependency task has failed"""
        mock_task = Mock()
        mock_task.dependencies = ["failed_task"]

        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.FAILED
        mock_dep_task.task_name = "Failed task"

        self.mock_task_list_manager.get_task_detail.return_value = (
            mock_dep_task,
            True,
            None,
        )

        # Should raise DependencyFailedError
        with pytest.raises(DependencyFailedError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        assert "Dependency task 'failed_task' failed; cannot execute" in str(exc_info.value)

    def test_validate_dependencies_status_dependency_abandoned(self):
        """Test when dependency task is abandoned"""
        mock_task = Mock()
        mock_task.dependencies = ["abandoned_task"]

        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.ABANDONED
        mock_dep_task.task_name = "Abandoned task"

        self.mock_task_list_manager.get_task_detail.return_value = (
            mock_dep_task,
            True,
            None,
        )

        # Should raise DependencyFailedError
        with pytest.raises(DependencyFailedError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        assert "Dependency task 'abandoned_task' has been abandoned" in str(exc_info.value)

    def test_validate_dependencies_status_dependency_pending(self):
        """Test when dependency task has not started"""
        mock_task = Mock()
        mock_task.dependencies = ["pending_task"]

        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.PENDING
        mock_dep_task.task_name = "Pending task"

        self.mock_task_list_manager.get_task_detail.return_value = (
            mock_dep_task,
            True,
            None,
        )

        # Should raise DependencyNotCompletedError
        with pytest.raises(DependencyNotCompletedError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        assert "Dependency task 'pending_task' has not started yet; cannot execute" in str(exc_info.value)

    def test_validate_dependencies_status_dependency_running(self):
        """Test when dependency task is in progress"""
        mock_task = Mock()
        mock_task.dependencies = ["running_task"]

        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.RUNNING
        mock_dep_task.task_name = "Running task"

        self.mock_task_list_manager.get_task_detail.return_value = (
            mock_dep_task,
            True,
            None,
        )

        # Should raise DependencyNotCompletedError
        with pytest.raises(DependencyNotCompletedError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        assert "Dependency task 'running_task' is currently executing; cannot execute" in str(exc_info.value)

    def test_validate_dependencies_status_multiple_dependencies(self):
        """Test multiple dependency tasks"""
        mock_task = Mock()
        mock_task.dependencies = ["dep1", "dep2", "dep3"]

        # Set different dependency statuses
        def mock_get_task_detail(task_list_id, task_id, **kwargs):
            mock_dep_task = Mock()
            if task_id == "dep1":
                mock_dep_task.status = TaskStatus.COMPLETED
                return mock_dep_task, True, None
            elif task_id == "dep2":
                mock_dep_task.status = TaskStatus.FAILED
                mock_dep_task.task_name = "Failed task"
                return mock_dep_task, True, None
            elif task_id == "dep3":
                mock_dep_task.status = TaskStatus.PENDING
                mock_dep_task.task_name = "Pending task"
                return mock_dep_task, True, None
            return None, False, "Task does not exist"

        self.mock_task_list_manager.get_task_detail.side_effect = mock_get_task_detail

        # Should raise an exception because dep2 failed and dep3 is not completed
        with pytest.raises(DependencyFailedError) as exc_info:
            self.tool._validate_dependencies_status(
                task_list_manager=self.mock_task_list_manager,
                task_list_id="test_list_id",
                task=mock_task,
                agent_id="test_agent",
                is_main_agent=True,
            )

        # Should find the first failed dependency
        assert "Dependency task 'dep2' failed; cannot execute" in str(exc_info.value)


class TestDependencyValidationIntegration:
    """Tests for dependency validation integration scenarios"""

    def setup_method(self):
        """Set up test environment"""
        self.tool = task_list_manager()
        self.mock_agent = Mock()
        self.mock_task_list_manager = Mock()
        self.mock_agent.task_list_manager = self.mock_task_list_manager
        self.mock_agent.name = "test_agent"

        # Set default user_data behavior
        self.mock_agent.get_user_data.return_value = "test_list_id"
        self.mock_agent.set_user_data.return_value = None

    def test_execute_task_with_invalid_dependencies(self):
        """Test executing a task with invalid dependencies"""
        # Create task in pending state
        mock_task = Mock()
        mock_task.task_id = "task_1"
        mock_task.status = TaskStatus.PENDING
        mock_task.dependencies = ["failed_dep"]
        mock_task.agent_type.value = "main"
        mock_task.task_name = "Test task"
        mock_task.task_desc = "Task description"
        mock_task.expected_output = "Expected output"

        # Dependency task has failed
        mock_dep_task = Mock()
        mock_dep_task.status = TaskStatus.FAILED
        mock_dep_task.task_name = "Failed task"

        def mock_get_task_detail(task_list_id, task_id, **kwargs):
            if task_id == "task_1":
                return mock_task, True, None
            elif task_id == "failed_dep":
                return mock_dep_task, True, None
            return None, False, "Task does not exist"

        self.mock_task_list_manager.get_task_detail.side_effect = mock_get_task_detail

        args = {
            "action": "execute_task",
            "task_id": "task_1",
            "additional_info": "Test executing task with invalid dependencies",
            "agent": self.mock_agent,
        }

        result = self.tool.execute(args)

        # Verify dependency validation failed, task cannot be executed
        assert result["success"] is False
        assert "Dependency task 'failed_dep' failed; cannot execute" in result["stderr"]
