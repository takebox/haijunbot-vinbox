# -*- coding: utf-8 -*-
"""Agent task list save and restore feature tests"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_agent.task_list import AgentType


class TestAgentTaskLists:
    """Tests for Agent class task list save and restore functionality"""

    def setup_method(self):
        """Set up test environment"""
        # Create a Mock model
        self.mock_model = Mock()
        self.mock_model.platform_name.return_value = "test_platform"
        self.mock_model.name.return_value = "test_model"
        self.mock_model.set_system_prompt = Mock()
        self.mock_model.get_remaining_token_count = Mock(return_value=1000)

        # Use temporary directory as working directory
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Create an Agent instance with task list for testing
        with (
            patch(
                "haijunbot.haijunbot_platform.registry.PlatformRegistry.get_normal_platform",
                return_value=self.mock_model,
            ),
            patch(
                "haijunbot.haijunbot_platform.registry.PlatformRegistry.create_platform",
                return_value=self.mock_model,
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_normal_model_name",
                return_value="test_model",
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_normal_platform_name",
                return_value="test_platform",
            ),
            patch(
                "haijunbot.haijunbot_utils.config.get_data_dir",
                return_value=os.path.join(self.temp_dir, "data"),
            ),
        ):
            self.agent = Agent(system_prompt="Test system prompt", name="test_agent")

    def teardown_method(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        # Clean up temporary directory
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_task_lists_no_tasks(self):
        """Test save functionality when there are no task lists"""
        # Ensure no task lists
        self.agent.task_list_manager.task_lists.clear()

        # Call save method
        result = self.agent.session._save_task_lists()

        # Verify return value
        assert result is True

    def test_save_and_restore_task_lists(self):
        """Test task list save and restore functionality"""
        # Create a task list
        task_list_id, success, error = self.agent.task_list_manager.create_task_list(
            main_goal="Test main goal", agent_id="test_agent"
        )
        assert success is True

        # Add a task
        task_info = {
            "task_name": "Test Task",
            "task_desc": "Test task description",
            "expected_output": "Test expected output",
            "agent_type": "main",
        }
        task_id, success, error = self.agent.task_list_manager.add_task(
            task_list_id=task_list_id, task_info=task_info, agent_id="test_agent"
        )
        assert success is True

        # Verify task was added
        task_list = self.agent.task_list_manager.get_task_list(task_list_id)
        assert task_list is not None
        assert len(task_list.tasks) == 1

        # Save task lists
        save_result = self.agent.session._save_task_lists()
        assert save_result is True

        # Verify save file exists
        session_dir = os.path.join(self.temp_dir, ".haijunbot", "sessions")
        tasklist_file = os.path.join(
            session_dir,
            f"saved_session_{self.agent.name}_tasklist.json",
        )

        assert os.path.exists(tasklist_file) is True

        # Verify saved file content
        with open(tasklist_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert "task_lists" in saved_data
        assert task_list_id in saved_data["task_lists"]

        # Clear current task lists
        self.agent.task_list_manager.task_lists.clear()
        assert len(self.agent.task_list_manager.task_lists) == 0

        # Restore task lists
        restore_result = self.agent.session._restore_task_lists()
        assert restore_result is True

        # Verify task lists were restored
        assert len(self.agent.task_list_manager.task_lists) == 1
        assert task_list_id in self.agent.task_list_manager.task_lists

        restored_task_list = self.agent.task_list_manager.task_lists[task_list_id]
        assert restored_task_list.main_goal == "Test main goal"
        assert len(restored_task_list.tasks) == 1

        restored_task = list(restored_task_list.tasks.values())[0]
        assert restored_task.task_name == "Test Task"
        assert restored_task.task_desc == "Test task description"
        assert restored_task.expected_output == "Test expected output"
        assert restored_task.agent_type == AgentType.MAIN

    def test_restore_task_lists_file_not_exists(self):
        """Test case when file does not exist during task list restore"""
        # Ensure no task list file was saved
        result = self.agent.session._restore_task_lists()

        # Should return True (no file is also considered success)
        assert result is True

    def test_restore_task_lists_with_multiple_task_lists(self):
        """Test restoring multiple task lists"""
        # Create first task list
        task_list_id1, success, error = self.agent.task_list_manager.create_task_list(
            main_goal="Test main goal 1", agent_id="test_agent"
        )
        assert success is True

        # Add first task
        task_info1 = {
            "task_name": "Test Task 1",
            "task_desc": "Test task description 1",
            "expected_output": "Test expected output 1",
            "agent_type": "main",
        }
        self.agent.task_list_manager.add_task(
            task_list_id=task_list_id1, task_info=task_info1, agent_id="test_agent"
        )

        # Create second task list
        task_list_id2, success, error = self.agent.task_list_manager.create_task_list(
            main_goal="Test main goal 2", agent_id="test_agent"
        )
        assert success is True

        # Add second task
        task_info2 = {
            "task_name": "Test Task 2",
            "task_desc": "Test task description 2",
            "expected_output": "Test expected output 2",
            "agent_type": "sub",
        }
        self.agent.task_list_manager.add_task(
            task_list_id=task_list_id2, task_info=task_info2, agent_id="test_agent"
        )

        # Save task lists
        save_result = self.agent.session._save_task_lists()
        assert save_result is True

        # Verify saved file content
        session_dir = os.path.join(self.temp_dir, ".haijunbot", "sessions")
        tasklist_file = os.path.join(
            session_dir,
            f"saved_session_{self.agent.name}_tasklist.json",
        )

        with open(tasklist_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        assert len(saved_data["task_lists"]) == 2
        assert task_list_id1 in saved_data["task_lists"]
        assert task_list_id2 in saved_data["task_lists"]

        # Clear current task lists
        self.agent.task_list_manager.task_lists.clear()
        assert len(self.agent.task_list_manager.task_lists) == 0

        # Restore task lists
        restore_result = self.agent.session._restore_task_lists()
        assert restore_result is True

        # Verify both task lists were restored
        assert len(self.agent.task_list_manager.task_lists) == 2
        assert task_list_id1 in self.agent.task_list_manager.task_lists
        assert task_list_id2 in self.agent.task_list_manager.task_lists

        # Verify first task list
        restored_task_list1 = self.agent.task_list_manager.task_lists[task_list_id1]
        assert restored_task_list1.main_goal == "Test main goal 1"
        assert len(restored_task_list1.tasks) == 1

        # Verify second task list
        restored_task_list2 = self.agent.task_list_manager.task_lists[task_list_id2]
        assert restored_task_list2.main_goal == "Test main goal 2"
        assert len(restored_task_list2.tasks) == 1

    def test_restore_task_lists_with_task_dependencies(self):
        """Test restoring task lists with dependencies"""
        # Create a task list
        task_list_id, success, error = self.agent.task_list_manager.create_task_list(
            main_goal="Test main goal with dependencies", agent_id="test_agent"
        )
        assert success is True

        # Add two tasks, second depends on first
        task_info1 = {
            "task_name": "Test Task 1",
            "task_desc": "Test task description 1",
            "expected_output": "Test expected output 1",
            "agent_type": "main",
        }
        task_id1, success, error = self.agent.task_list_manager.add_task(
            task_list_id=task_list_id, task_info=task_info1, agent_id="test_agent"
        )
        assert success is True

        # Add second task, depends on first task
        task_info2 = {
            "task_name": "Test Task 2",
            "task_desc": "Test task description 2",
            "expected_output": "Test expected output 2",
            "agent_type": "main",
            "dependencies": [task_id1],
        }
        task_id2, success, error = self.agent.task_list_manager.add_task(
            task_list_id=task_list_id, task_info=task_info2, agent_id="test_agent"
        )
        assert success is True

        # Save task lists
        save_result = self.agent.session._save_task_lists()
        assert save_result is True

        # Verify saved file content
        session_dir = os.path.join(self.temp_dir, ".haijunbot", "sessions")
        tasklist_file = os.path.join(
            session_dir,
            f"saved_session_{self.agent.name}_tasklist.json",
        )

        with open(tasklist_file, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        # Verify dependencies were saved correctly
        task_list_data = saved_data["task_lists"][task_list_id]
        assert task_id1 in task_list_data["tasks"]
        assert task_id2 in task_list_data["tasks"]

        # Clear current task lists
        self.agent.task_list_manager.task_lists.clear()
        assert len(self.agent.task_list_manager.task_lists) == 0

        # Restore task lists
        restore_result = self.agent.session._restore_task_lists()
        assert restore_result is True

        # Verify dependencies still exist after restore
        restored_task_list = self.agent.task_list_manager.task_lists[task_list_id]
        assert len(restored_task_list.tasks) == 2

        restored_task2 = restored_task_list.tasks[task_id2]
        assert task_id1 in restored_task_list.tasks
        assert task_id2 in restored_task_list.tasks
        assert restored_task2.dependencies == [task_id1]

    def test_save_task_lists_with_empty_task_list(self):
        """Test saving empty task list"""
        # Ensure task list manager has no task lists
        self.agent.task_list_manager.task_lists.clear()

        # Save task lists (should succeed even with no tasks)
        save_result = self.agent.session._save_task_lists()
        assert save_result is True

        # Verify no file is created
        session_dir = os.path.join(self.temp_dir, ".haijunbot", "sessions")
        tasklist_file = os.path.join(
            session_dir,
            f"saved_session_{self.agent.name}_tasklist.json",
        )

        # File should not exist because there are no task lists
        assert os.path.exists(tasklist_file) is False

    def test_restore_session_calls_restore_task_lists(self):
        """Test whether restore_session method calls _restore_task_lists"""
        # Create a task list to ensure save file is created
        task_list_id, success, error = self.agent.task_list_manager.create_task_list(
            main_goal="Test main goal", agent_id="test_agent"
        )
        assert success is True

        # Add a task
        task_info = {
            "task_name": "Test Task",
            "task_desc": "Test task description",
            "expected_output": "Test expected output",
            "agent_type": "main",
        }
        task_id, success, error = self.agent.task_list_manager.add_task(
            task_list_id=task_list_id, task_info=task_info, agent_id="test_agent"
        )
        assert success is True

        # Save task lists
        save_result = self.agent.session._save_task_lists()
        assert save_result is True

        # Clear current task lists
        self.agent.task_list_manager.task_lists.clear()
        assert len(self.agent.task_list_manager.task_lists) == 0

        # Save session to create session file
        with patch.object(self.agent.session, "save_session", return_value=True):
            session_saved = self.agent.save_session()
            assert session_saved is True

        # Mock restore_session dependencies so it can execute fully
        with patch.object(
            self.agent.session,
            "_parse_session_files",
            return_value=[("fake_session.json", "20240101_120000", None, "consistent")],
        ):
            with patch.object(
                self.agent.session, "_check_commit_consistency", return_value=True
            ):
                with patch.object(
                    self.agent.session.model, "restore", return_value=True
                ):
                    with patch.object(self.agent.session, "_restore_agent_state"):
                        with patch.object(
                            self.agent.session, "_restore_start_commit_info"
                        ):
                            with patch.object(
                                self.agent.session, "_restore_task_lists"
                            ) as mock_restore_task_lists:
                                # Execute restore_session
                                result = self.agent.restore_session(True)

                                # Verify restore_session returns True
                                assert result is True

                                # Verify _restore_task_lists was called (now called by SessionManager)
                                mock_restore_task_lists.assert_called_once()
