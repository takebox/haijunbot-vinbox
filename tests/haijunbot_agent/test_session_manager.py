# -*- coding: utf-8 -*-
"""SessionManager unit tests"""

from unittest.mock import Mock, patch
import os
import pytest

from haijunbot.haijunbot_agent.session_manager import SessionManager


class TestSessionManager:
    """Tests for SessionManager class"""

    @pytest.fixture
    def mock_model(self):
        """Create mock BasePlatform object"""
        model = Mock()
        model.platform_name.return_value = "test_platform"
        model.name.return_value = "test_model"
        model.reset = Mock()
        model.save = Mock(return_value=True)
        model.restore = Mock(return_value=True)
        return model

    @pytest.fixture
    def session_manager(self, mock_model):
        """Create SessionManager instance"""
        return SessionManager(mock_model, "test_agent")

    def test_init(self, session_manager, mock_model):
        """Test initialization"""
        assert session_manager.model == mock_model
        assert session_manager.agent_name == "test_agent"
        assert session_manager.prompt == ""
        assert session_manager.conversation_length == 0
        assert session_manager.user_data == {}
        assert session_manager.addon_prompt == ""

    def test_set_get_user_data(self, session_manager):
        """Test setting and getting user data"""
        # Set data
        session_manager.set_user_data("key1", "value1")
        session_manager.set_user_data("key2", 123)

        # Get data
        assert session_manager.get_user_data("key1") == "value1"
        assert session_manager.get_user_data("key2") == 123
        assert session_manager.get_user_data("non_existent") is None

    def test_set_addon_prompt(self, session_manager):
        """Test setting addon prompt"""
        test_prompt = "This is an addon prompt"
        session_manager.set_addon_prompt(test_prompt)
        assert session_manager.addon_prompt == test_prompt

    def test_clear(self, session_manager, mock_model):
        """Test clearing session"""
        # Set some data
        session_manager.prompt = "test prompt"
        session_manager.conversation_length = 5
        session_manager.set_user_data("key", "value")

        # Clear session
        session_manager.clear()

        # Verify state
        assert session_manager.prompt == ""
        assert session_manager.conversation_length == 0
        assert session_manager.user_data == {"key": "value"}  # user_data is not cleared
        mock_model.reset.assert_called_once()

    def test_clear_history(self, session_manager, mock_model):
        """Test clearing history"""
        # Set some data
        session_manager.prompt = "test prompt"
        session_manager.conversation_length = 5

        # Clear history
        session_manager.clear_history()

        # Verify state
        assert session_manager.prompt == ""
        assert session_manager.conversation_length == 0
        mock_model.reset.assert_called_once()

    @patch("os.makedirs")
    def test_save_session_success(self, mock_makedirs, session_manager, mock_model):
        """Test successful session save"""
        import re

        with patch("os.getcwd", return_value="/test/dir"):
            result = session_manager.save_session()

            # Verify result
            assert result is True
            mock_makedirs.assert_called_once_with(
                os.path.join("/test/dir", ".haijunbot", "sessions"), exist_ok=True
            )

            # Verify save path format (filename includes timestamp)
            actual_path = mock_model.save.call_args[0][0]
            actual_path = actual_path.replace(os.sep, "/")
            # Filename may include session name prefix (e.g.: Unnamed session)
            expected_pattern = r"/test/dir/\.haijunbot/sessions/[^_]*_saved_session_test_agent_\d{8}_\d{6}\.json$"
            assert re.match(expected_pattern, actual_path), (
                f"Path format mismatch: {actual_path}"
            )

    @patch("os.makedirs")
    def test_save_session_with_special_chars(
        self, mock_makedirs, session_manager, mock_model
    ):
        """Test model name with special characters"""
        import re

        mock_model.name.return_value = "test/model\\name"

        with patch("os.getcwd", return_value="/test/dir"):
            session_manager.save_session()

            # Verify special characters are replaced and filename includes timestamp
            actual_path = mock_model.save.call_args[0][0]
            actual_path = actual_path.replace(os.sep, "/")
            # Filename may include session name prefix (e.g.: Unnamed session)
            expected_pattern = r"/test/dir/\.haijunbot/sessions/[^_]*_saved_session_test_agent_\d{8}_\d{6}\.json$"
            assert re.match(expected_pattern, actual_path), (
                f"Path format mismatch: {actual_path}"
            )

    @patch("os.path.exists")
    def test_restore_session_file_not_exists(self, mock_exists, session_manager):
        """Test case when session file does not exist"""
        mock_exists.return_value = False

        with patch("os.getcwd", return_value="/test/dir"):
            result = session_manager.restore_session()

            assert result is False

    def test_generate_session_name_empty_conversation(
        self, session_manager, mock_model
    ):
        """Return default name when conversation history is empty"""
        mock_model.get_messages.return_value = []
        assert session_manager._generate_session_name() == "Unnamed Session"

    def test_generate_session_name_llm_success(self, session_manager, mock_model):
        """LLM successfully generates session name"""
        mock_model.get_messages.return_value = [
            {"role": "user", "content": "Help me analyze the performance issues in this code"},
            {"role": "assistant", "content": "OK, let me analyze the performance bottlenecks"},
        ]
        mock_model.complete.return_value = "Code performance analysis"

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            assert session_manager._generate_session_name() == "Code performance analysis"

    def test_generate_session_name_llm_cleans_special_chars(
        self, session_manager, mock_model
    ):
        """LLM-returned name has special characters cleaned and length limited"""
        mock_model.get_messages.return_value = [
            {"role": "user", "content": "Help me write a Python script"}
        ]
        mock_model.complete.return_value = "Python script writing guide!"

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            name = session_manager._generate_session_name()
            # Special characters cleaned, keeping only alphanumeric and basic punctuation
            assert name == "Python script writing guide"

    def test_generate_session_name_all_platforms_fail(
        self, session_manager, mock_model
    ):
        """Return default name when all platforms fail"""
        mock_model.get_messages.return_value = [
            {"role": "user", "content": "Help me analyze code"}
        ]
        mock_model.complete.side_effect = Exception("LLM call failed")

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            assert session_manager._generate_session_name() == "Unnamed Session"

    def test_generate_session_name_llm_empty_result(self, session_manager, mock_model):
        """Fall back to default name when LLM returns empty result"""
        mock_model.get_messages.return_value = [
            {"role": "user", "content": "Help me analyze code"}
        ]
        mock_model.complete.return_value = ""

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            assert session_manager._generate_session_name() == "Unnamed Session"

    def test_generate_session_name_skips_compressed_summary(
        self, session_manager, mock_model
    ):
        """Compressed summary messages (containing code change stats and other meta info) are skipped, do not pollute session topic determination"""
        compressed_summary = (
            "[History Summary] ## Task condensed context\n\n"
            "**Current goal**: Fix all ty warnings\n\n"
            "## Code change stats\n```\n3 files changed, 278 insertions\n```\n"
            "## Task list status\n- Completed: 5\n"
        )
        mock_model.get_messages.return_value = [
            {"role": "user", "content": compressed_summary},
            {"role": "assistant", "content": "OK, let me analyze the performance bottlenecks in this code"},
            {"role": "user", "content": "Help me optimize this sorting algorithm"},
        ]
        mock_model.complete.return_value = "Algorithm optimization"

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            name = session_manager._generate_session_name()
            assert name == "Algorithm optimization"
            # Verify prompt passed to LLM does not contain compressed summary meta info
            prompt_arg = mock_model.complete.call_args[0][0]
            assert "Code change stats" not in prompt_arg
            assert "Task list status" not in prompt_arg
            assert "Help me optimize this sorting algorithm" in prompt_arg

    def test_generate_session_name_only_compressed_summary(
        self, session_manager, mock_model
    ):
        """Return default name when history only contains compressed summary (no real conversation)"""
        mock_model.get_messages.return_value = [
            {
                "role": "user",
                "content": "[History Summary] ## Task condensed context\n\n**Current goal**: Fix ty warnings",
            }
        ]

        with patch.object(
            session_manager, "_iter_name_platforms", return_value=[mock_model]
        ):
            assert session_manager._generate_session_name() == "Unnamed Session"

    def test_is_compressed_summary_msg(self, session_manager):
        """_is_compressed_summary_msg correctly identifies compressed summary messages"""
        assert session_manager._is_compressed_summary_msg(
            {"role": "user", "content": "[History Summary] Summary content"}
        )
        assert session_manager._is_compressed_summary_msg(
            {"role": "user", "content": "  [History Summary] With leading spaces"}
        )
        # Normal user messages are not compressed summaries
        assert not session_manager._is_compressed_summary_msg(
            {"role": "user", "content": "Help me analyze code"}
        )
        # assistant messages starting with [History Summary] don't count (compressed summaries are always user role)
        assert not session_manager._is_compressed_summary_msg(
            {"role": "assistant", "content": "[History Summary] Not a compressed summary"}
        )
        # Empty content is not a compressed summary
        assert not session_manager._is_compressed_summary_msg(
            {"role": "user", "content": ""}
        )
