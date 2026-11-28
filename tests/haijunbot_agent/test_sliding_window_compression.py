# -*- coding: utf-8 -*-
"""Sliding window compression feature tests"""

from unittest.mock import Mock
import pytest

from haijunbot.haijunbot_agent import Agent


class TestSlidingWindowCompression:
    """Tests for sliding window compression feature"""

    @pytest.fixture
    def mock_model(self):
        """Create mock model object"""
        model = Mock()
        model.messages = []
        model.get_messages = Mock(return_value=[])
        model.get_remaining_token_count = Mock(return_value=1000)
        model.chat_until_success = Mock(
            return_value="This is a sufficiently long compressed summary content for passing length validation."
        )

        # Add set_messages method to actually modify messages attribute
        def set_messages_impl(messages):
            model.messages = messages

        model.set_messages = Mock(side_effect=set_messages_impl)

        return model

    @pytest.fixture
    def agent(self, mock_model):
        """Create Agent instance"""
        # Use Mock to create Agent, avoiding complex initialization
        ag = Mock(spec=Agent)
        ag.model = mock_model
        ag.pin_content = ""
        ag.original_user_input = ""
        ag.recent_memories = []
        ag.task_list_manager = Mock()
        ag.task_list_manager.task_lists = {}
        ag.task_list_manager.get_task_list_summary = Mock(return_value=None)
        ag._agent_run_loop = None
        ag.start_commit = None

        # Mock _create_temp_model method
        temp_model = Mock()
        temp_model.chat_until_success = Mock(
            return_value="This is a sufficiently long compressed summary content for passing length validation."
        )
        ag._create_temp_model = Mock(return_value=temp_model)

        # Mock _format_compressed_summary method
        ag._format_compressed_summary = Mock(side_effect=lambda x: f"[History Summary] {x}")

        # Mock _validate_summary method, default returns validation passed
        ag._validate_summary = Mock(return_value=(True, []))

        # Mock _print_compression_summary method
        ag._print_compression_summary = Mock()

        # Bind actual _sliding_window_compression method to mock object
        from haijunbot.haijunbot_agent import Agent as RealAgent

        ag._sliding_window_compression = RealAgent._sliding_window_compression.__get__(
            ag, Mock
        )

        # After refactoring _sliding_window_compression delegates to self._history_compressor,
        # need to complete this attribute when binding real method to mock
        from haijunbot.haijunbot_agent.history_compressor import HistoryCompressor

        ag._history_compressor = HistoryCompressor(ag)

        return ag

    def _create_messages(
        self, user_count: int, assistant_count: int, system_count: int = 1
    ):
        """Create test message list"""
        messages = []

        # Add system messages
        for i in range(system_count):
            messages.append({"role": "system", "content": f"System prompt {i}"})

        # Add alternating user and assistant messages
        for i in range(max(user_count, assistant_count)):
            if i < user_count:
                messages.append({"role": "user", "content": f"Content of user{i + 1}"})
            if i < assistant_count:
                messages.append(
                    {"role": "assistant", "content": f"Content of assistant{i + 1}"}
                )

        return messages

    def test_compression_basic(self, agent, mock_model):
        """Test basic compression: 21 messages compressed to 11 (1 system + 1 summary + 9 recent)"""
        # Prepare messages: 1 system + 10 user + 10 assistant = 21
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        # Verify result: after compression should be 1 system + 1 summary + 9 recent = 11
        assert result is True
        assert len(mock_model.messages) == 11  # 1 system + 1 summary + 9 recent

        # Verify system message preserved
        assert mock_model.messages[0]["role"] == "system"

        # Verify compressed summary inserted
        assert mock_model.messages[1]["role"] == "user"
        assert "[History Summary]" in mock_model.messages[1]["content"]

        # Verify last 9 messages preserved (from assistant6 to assistant10)
        recent_messages = mock_model.messages[2:]
        assert len(recent_messages) == 9

        # Verify message order: assistant6, user7, assistant7, ..., user10, assistant10
        assert recent_messages[0]["role"] == "assistant"
        assert recent_messages[0]["content"] == "Content of assistant6"
        assert recent_messages[-1]["role"] == "assistant"
        assert recent_messages[-1]["content"] == "Content of assistant10"

    def test_compression_no_consecutive_user(self, agent, mock_model):
        """Test that compression does not produce consecutive user messages"""
        # Prepare messages: 1 system + 10 user + 10 assistant = 21
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True

        # Verify user message does not follow compressed summary (should be assistant)
        compressed_msg = mock_model.messages[1]
        first_recent_msg = mock_model.messages[2]

        assert compressed_msg["role"] == "user"
        assert first_recent_msg["role"] == "assistant"  # Should be assistant6, not user7

    def test_compression_insufficient_messages(self, agent, mock_model):
        """Test no compression when message count is insufficient"""
        # Prepare messages: 1 system + 5 user + 5 assistant = 11 (other_messages=10, less than window_size=9)
        messages = self._create_messages(
            user_count=5, assistant_count=5, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        # Should return False, because other_messages only has 10, less than window_size=9
        assert result is False
        assert len(mock_model.messages) == 11  # Messages unchanged

    def test_compression_exact_window_size(self, agent, mock_model):
        """Test no compression when message count equals exactly 2x window size"""
        # Prepare messages: 1 system + 9 user + 9 assistant = 19 (other_messages=18, exactly 9*2)
        messages = self._create_messages(
            user_count=9, assistant_count=9, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        # Should return False, because other_messages=18, exactly window_size*2=18 (condition: <= window_size * 2)
        assert result is False
        assert len(mock_model.messages) == 19  # Messages unchanged

    def test_compression_multiple_system_messages(self, agent, mock_model):
        """Test all system messages are preserved with multiple system messages"""
        # Prepare messages: 3 system + 10 user + 10 assistant = 23
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=3
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True

        # Verify all system messages preserved
        system_messages = [
            msg for msg in mock_model.messages if msg["role"] == "system"
        ]
        assert len(system_messages) == 3

    def test_compression_with_tool_messages(self, agent, mock_model):
        """Test case including tool messages"""
        # Prepare messages: 1 system + 10 user + 10 assistant + 1 tool = 22
        # other_messages has 21 (10 user + 10 assistant + 1 tool)
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        messages.append({"role": "tool", "content": "Content returned by tool"})
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True

        # Verify tool message is in the 9 preserved messages
        recent_messages = mock_model.messages[2:]  # Skip system and compressed summary
        assert len(recent_messages) == 9

        # Tool message is last, should be in preserved 9
        assert recent_messages[-1]["role"] == "tool"
        assert recent_messages[-1]["content"] == "Content returned by tool"

    def test_compression_message_order(self, agent, mock_model):
        """Test message order is correct after compression"""
        # Prepare messages: 1 system + 10 user + 10 assistant = 21
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True

        # Verify message order: system -> compressed summary -> last 9 messages
        assert mock_model.messages[0]["role"] == "system"
        assert mock_model.messages[1]["role"] == "user"
        assert "[History Summary]" in mock_model.messages[1]["content"]

        # Verify order of last 9 messages
        recent_messages = mock_model.messages[2:]
        # Should be: assistant6, user7, assistant7, user8, assistant8, user9, assistant9, user10, assistant10
        assert recent_messages[0]["role"] == "assistant"
        assert recent_messages[0]["content"] == "Content of assistant6"
        assert recent_messages[1]["role"] == "user"
        assert recent_messages[1]["content"] == "Content of user7"
        assert recent_messages[-1]["role"] == "assistant"
        assert recent_messages[-1]["content"] == "Content of assistant10"

    def test_compression_old_messages_count(self, agent, mock_model):
        """Test compressed message count is correct: 21 messages compressed to 11"""
        # Prepare messages: 1 system + 10 user + 10 assistant = 21
        # other_messages has 20 (index 0-19)
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True

        # Verify compressed message count
        # other_messages has 20, preserve last 9 (index 11-19), compress first 11 (index 0-10)
        # Compressed: user1, assistant1, user2, assistant2, user3, assistant3, user4, assistant4, user5, assistant5, user6 (11 entries)
        # Preserved: assistant6, user7, assistant7, user8, assistant8, user9, assistant9, user10, assistant10 (9 entries)

        # Verify final message count: 21 before compression -> 1 system + 1 summary + 9 recent = 11
        assert len(mock_model.messages) == 11

    def test_compression_empty_summary(self, agent, mock_model):
        """Test returning False when compressed summary is empty"""
        # Prepare messages
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Simulate temp model returning empty summary
        temp_model = agent._create_temp_model.return_value
        temp_model.chat_until_success.return_value = ""

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        # Should return False
        assert result is False
        assert len(mock_model.messages) == 21  # Messages unchanged

    def test_compression_custom_window_size(self, agent, mock_model):
        """Test custom window size"""
        # Prepare messages: 1 system + 15 user + 15 assistant = 31
        messages = self._create_messages(
            user_count=15, assistant_count=15, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression with custom window size 5
        result = agent._sliding_window_compression(window_size=5)

        assert result is True

        # Verify preserved message count
        recent_messages = mock_model.messages[2:]  # Skip system and compressed summary
        assert len(recent_messages) == 5

    def test_compression_uses_temp_model(self, agent, mock_model):
        """Test compression uses temp model"""
        # Prepare messages
        messages = self._create_messages(
            user_count=10, assistant_count=10, system_count=1
        )
        mock_model.get_messages.return_value = messages
        mock_model.messages = messages.copy()

        # Execute compression
        result = agent._sliding_window_compression(window_size=9)

        assert result is True
        # Verify temp model was used
        agent._create_temp_model.assert_called_once()
        temp_model = agent._create_temp_model.return_value
        temp_model.chat_until_success.assert_called_once()

    def _is_alternating_roles(self, messages: list) -> bool:
        """Verify message list roles are alternating

        Alternating pattern definition:
        - system can be at the beginning (multiple systems also allowed)
        - After that, user and assistant must alternate
        - No consecutive same roles allowed (except system)
        """
        if not messages:
            return True

        roles = [msg.get("role", "").lower() for msg in messages]

        # Find index of first non-system message
        first_non_system = 0
        for i, role in enumerate(roles):
            if role != "system":
                first_non_system = i
                break
        else:
            return True

        # Check if non-system messages are alternating
        non_system_roles = roles[first_non_system:]

        for i in range(len(non_system_roles) - 1):
            current_role = non_system_roles[i]
            next_role = non_system_roles[i + 1]

            if current_role == next_role:
                return False

            if current_role not in ["user", "assistant"]:
                return False
            if next_role not in ["user", "assistant"]:
                return False

        return True

    def _simulate_compression_slice(self, messages: list, window_size: int) -> dict:
        """Simulate sliding window compression slicing logic"""
        # Find end position of system messages
        system_end_idx = 0
        for i, msg in enumerate(messages):
            if msg.get("role", "").lower() != "system":
                system_end_idx = i
                break
        else:
            return {
                "system_messages": messages,
                "old_messages": [],
                "recent_messages": [],
            }

        # Separate system and non-system messages
        system_messages = messages[:system_end_idx]
        non_system_messages = messages[system_end_idx:]

        # Extract recent messages
        recent_messages = non_system_messages[-window_size:]

        # Separate earlier messages (extract one more)
        old_messages = non_system_messages[: -window_size + 1]

        return {
            "system_messages": system_messages,
            "old_messages": old_messages,
            "recent_messages": recent_messages,
        }

    def test_first_set_messages_alternating_roles(self):
        """Verify first set_messages call (system_messages + old_messages) satisfies alternating pattern"""
        for window_size in [3, 5, 7, 9]:
            messages = self._create_messages(
                user_count=20, assistant_count=20, system_count=1
            )
            slices = self._simulate_compression_slice(messages, window_size)
            first_set_messages = slices["system_messages"] + slices["old_messages"]
            assert self._is_alternating_roles(first_set_messages), (
                f"window_size={window_size}: First set_messages does not satisfy alternating pattern\n"
                f"roles: {[msg['role'] for msg in first_set_messages]}"
            )

    def test_second_set_messages_alternating_roles(self):
        """Verify second set_messages call (system_messages + compressed_msg + recent_messages) satisfies alternating pattern"""
        for window_size in [3, 5, 7, 9]:
            messages = self._create_messages(
                user_count=20, assistant_count=20, system_count=1
            )
            slices = self._simulate_compression_slice(messages, window_size)
            compressed_msg = {"role": "user", "content": "[Compressed Summary]"}
            second_set_messages = (
                slices["system_messages"] + [compressed_msg] + slices["recent_messages"]
            )
            assert self._is_alternating_roles(second_set_messages), (
                f"window_size={window_size}: Second set_messages does not satisfy alternating pattern\n"
                f"roles: {[msg['role'] for msg in second_set_messages]}"
            )

    def test_compressed_msg_not_consecutive_with_recent(self):
        """Verify compressed_msg (role=user) and recent_messages[0] are not consecutive"""
        for window_size in [3, 5, 7, 9]:
            messages = self._create_messages(
                user_count=20, assistant_count=20, system_count=1
            )
            slices = self._simulate_compression_slice(messages, window_size)
            if slices["recent_messages"]:
                first_recent_role = slices["recent_messages"][0]["role"]
                assert first_recent_role == "assistant", (
                    f"window_size={window_size}: recent_messages[0] should be assistant, "
                    f"actually {first_recent_role}"
                )

    def test_multiple_system_messages_alternating_roles(self):
        """Verify set_messages calls still satisfy alternating pattern with multiple system messages"""
        for window_size in [3, 5, 7, 9]:
            for system_count in [1, 2, 3]:
                messages = self._create_messages(
                    user_count=20, assistant_count=20, system_count=system_count
                )
                slices = self._simulate_compression_slice(messages, window_size)

                # First set_messages
                first_set_messages = slices["system_messages"] + slices["old_messages"]
                assert self._is_alternating_roles(first_set_messages), (
                    f"system_count={system_count}, window_size={window_size}: "
                    f"First set_messages does not satisfy alternating pattern"
                )

                # Second set_messages
                compressed_msg = {"role": "user", "content": "[Compressed Summary]"}
                second_set_messages = (
                    slices["system_messages"]
                    + [compressed_msg]
                    + slices["recent_messages"]
                )
                assert self._is_alternating_roles(second_set_messages), (
                    f"system_count={system_count}, window_size={window_size}: "
                    f"Second set_messages does not satisfy alternating pattern"
                )
