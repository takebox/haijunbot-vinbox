#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dialogue Recorder Unit Tests

Test all public methods and functionality of the DialogueRecorder class
"""

import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

from src.haijunbot.haijunbot_utils.dialogue_recorder import DialogueRecorder


class TestDialogueRecorder:
    """Test suite for DialogueRecorder class"""

    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    @pytest.fixture
    def recorder(self, temp_data_dir):
        """Create DialogueRecorder instance with temporary data directory"""
        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)
            yield DialogueRecorder()

    def test_init_without_session_id(self, temp_data_dir):
        """Test initialization without session ID"""
        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)
            recorder = DialogueRecorder()

            assert recorder.session_id is not None
            assert len(recorder.session_id) > 0
            assert (temp_data_dir / "dialogues").exists()

    def test_init_with_session_id(self, temp_data_dir):
        """Test initialization with specified session ID"""
        session_id = "test-session-123"
        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)
            recorder = DialogueRecorder(session_id=session_id)

            assert recorder.session_id == session_id
            assert (temp_data_dir / "dialogues").exists()

    def test_start_recording(self, recorder):
        """Test starting a new dialogue recording"""
        new_session_id = recorder.start_recording()

        assert new_session_id is not None
        assert len(new_session_id) > 0
        # Verify it's a valid UUID format
        try:
            uuid.UUID(new_session_id)
        except ValueError:
            pytest.fail("start_recording should return a valid UUID")

    def test_record_message(self, recorder, temp_data_dir):
        """Test recording a message"""
        role = "user"
        content = "Hello, world!"
        metadata = {"test": True, "version": "1.0"}

        recorder.record_message(role, content, metadata)

        # Verify file was created
        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        assert session_file.exists()

        # Verify content
        with open(session_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1

            record = json.loads(lines[0])
            assert record["role"] == role
            assert record["content"] == content
            assert record["metadata"] == metadata
            assert "timestamp" in record
            assert isinstance(record["timestamp"], str)

    def test_record_message_without_metadata(self, recorder, temp_data_dir):
        """Test recording a message (without metadata)"""
        role = "assistant"
        content = "How can I help you?"

        recorder.record_message(role, content)

        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
            assert record["role"] == role
            assert record["content"] == content
            assert record["metadata"] == {}

    def test_get_session_file_path(self, recorder, temp_data_dir):
        """Test getting session file path"""
        expected_path = str(
            temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        )
        actual_path = recorder.get_session_file_path()

        assert actual_path == expected_path

    def test_get_all_sessions_empty(self, recorder):
        """Test getting all sessions (empty)"""
        sessions = recorder.get_all_sessions()
        assert sessions == []

    def test_get_all_sessions_with_files(self, recorder, temp_data_dir):
        """Test getting all sessions (with files)"""
        # Create test session files
        dialogues_dir = temp_data_dir / "dialogues"
        dialogues_dir.mkdir(exist_ok=True)

        session_ids = ["session1", "session2", "session3"]
        for session_id in session_ids:
            file_path = dialogues_dir / f"{session_id}.jsonl"
            file_path.touch()

        sessions = recorder.get_all_sessions()
        assert len(sessions) == 3
        assert set(sessions) == set(session_ids)

    def test_read_session_empty(self, recorder):
        """Test reading empty session"""
        non_existent_session = "non-existent-session"
        messages = recorder.read_session(non_existent_session)
        assert messages == []

    def test_read_session_with_content(self, recorder, temp_data_dir):
        """Test reading session with content"""
        # Create test data
        test_messages = [
            {
                "timestamp": "2024-01-01T00:00:00",
                "role": "user",
                "content": "Hi",
                "metadata": {},
            },
            {
                "timestamp": "2024-01-01T00:00:01",
                "role": "assistant",
                "content": "Hello",
                "metadata": {"type": "greeting"},
            },
        ]

        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "w", encoding="utf-8") as f:
            for msg in test_messages:
                json.dump(msg, f)
                f.write("\n")

        messages = recorder.read_session(recorder.session_id)
        assert len(messages) == 2
        assert messages == test_messages

    def test_read_session_with_invalid_json(self, recorder, temp_data_dir):
        """Test reading session containing invalid JSON"""
        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "w", encoding="utf-8") as f:
            f.write('{"valid": "json"}\n')
            f.write("invalid json line\n")
            f.write('{"another": "valid"}\n')

        messages = recorder.read_session(recorder.session_id)
        assert len(messages) == 2  # Only valid JSON lines were read

    def test_cleanup_session(self, recorder, temp_data_dir):
        """Test cleaning up specified session"""
        # Create session file
        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        session_file.touch()
        assert session_file.exists()

        recorder.cleanup_session()
        assert not session_file.exists()

    def test_cleanup_session_specific(self, recorder, temp_data_dir):
        """Test cleaning up a specific session"""
        target_session = "specific-session"
        target_file = temp_data_dir / "dialogues" / f"{target_session}.jsonl"
        target_file.touch()
        assert target_file.exists()

        # Create other session files
        other_file = temp_data_dir / "dialogues" / "other-session.jsonl"
        other_file.touch()

        recorder.cleanup_session(target_session)
        assert not target_file.exists()
        assert other_file.exists()  # Other files are not affected

    def test_cleanup_all_sessions(self, recorder, temp_data_dir):
        """Test cleaning up all sessions"""
        # Create multiple session files
        dialogues_dir = temp_data_dir / "dialogues"
        dialogues_dir.mkdir(exist_ok=True)

        session_files = [
            dialogues_dir / "session1.jsonl",
            dialogues_dir / "session2.jsonl",
            dialogues_dir / "session3.jsonl",
        ]

        for file_path in session_files:
            file_path.touch()
            assert file_path.exists()

        recorder.cleanup_all_sessions()

        for file_path in session_files:
            assert not file_path.exists()

    def test_get_session_count_empty(self, recorder):
        """Test getting session count (empty)"""
        assert recorder.get_session_count() == 0

    def test_get_session_count_with_sessions(self, recorder, temp_data_dir):
        """Test getting session count (with sessions)"""
        # Create test session files
        dialogues_dir = temp_data_dir / "dialogues"
        dialogues_dir.mkdir(exist_ok=True)

        for i in range(3):
            (dialogues_dir / f"session{i}.jsonl").touch()

        assert recorder.get_session_count() == 3

    def test_multiple_messages_in_session(self, recorder, temp_data_dir):
        """Test multiple messages in one session"""
        messages = [
            ("user", "Hello"),
            ("assistant", "Hi there!"),
            ("user", "How are you?"),
            ("assistant", "I'm doing well, thank you!"),
        ]

        for role, content in messages:
            recorder.record_message(role, content)

        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 4

            for i, line in enumerate(lines):
                record = json.loads(line)
                expected_role, expected_content = messages[i]
                assert record["role"] == expected_role
                assert record["content"] == expected_content

    def test_session_persistence(self, temp_data_dir):
        """Test session persistence"""
        session_id = "persistent-session"

        # First recorder records message
        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)
            recorder1 = DialogueRecorder(session_id)
            recorder1.record_message("user", "Persistent message")

        # Second recorder reads message
        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)
            recorder2 = DialogueRecorder(session_id)
            messages = recorder2.read_session(session_id)

        assert len(messages) == 1
        assert messages[0]["content"] == "Persistent message"

    def test_unicode_content(self, recorder, temp_data_dir):
        """Test Unicode content handling"""
        unicode_content = "Hello, World! Earth Korean"

        recorder.record_message("user", unicode_content)

        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
            assert record["content"] == unicode_content

    def test_large_metadata(self, recorder, temp_data_dir):
        """Test large metadata handling"""
        large_metadata = {
            "nested": {"deep": {"very": {"deep": "structure"}}},
            "list": [1, 2, 3, "string", {"nested": True}],
            "null_value": None,
            "boolean": True,
        }

        recorder.record_message("system", "Test", large_metadata)

        session_file = temp_data_dir / "dialogues" / f"{recorder.session_id}.jsonl"
        with open(session_file, "r", encoding="utf-8") as f:
            record = json.loads(f.readline())
            assert record["metadata"] == large_metadata

    def test_cleanup_hook_registration(self, temp_data_dir):
        """Test cleanup hook registration"""

        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)

            # Create recorder instance
            recorder = DialogueRecorder()

            # Verify cleanup hook is registered
            assert hasattr(recorder, "_cleanup_registered")
            assert recorder._cleanup_registered is True

    def test_cleanup_on_exit(self, temp_data_dir):
        """Test cleanup on process exit"""
        session_id = "cleanup-test-session"

        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)

            # Create recorder and record message
            recorder = DialogueRecorder(session_id)
            recorder.record_message("user", "test message")

            # Verify file was created
            session_file = temp_data_dir / "dialogues" / f"{session_id}.jsonl"
            assert session_file.exists()

            # Manually call cleanup function (simulate process exit)
            recorder._cleanup_on_exit()

            # Verify file has been cleaned up
            assert not session_file.exists()

    def test_cleanup_error_handling(self, temp_data_dir):
        """Test exception handling during cleanup"""
        import io
        import sys

        session_id = "exception-test-session"

        with patch(
            "src.haijunbot.haijunbot_utils.dialogue_recorder.get_data_dir"
        ) as mock_get_data_dir:
            mock_get_data_dir.return_value = str(temp_data_dir)

            recorder = DialogueRecorder(session_id)

            # Redirect stdout to capture error messages
            captured_output = io.StringIO()
            sys_stdout_backup = sys.stdout
            sys.stdout = captured_output

            try:
                # Create session file
                session_file = temp_data_dir / "dialogues" / f"{session_id}.jsonl"
                session_file.touch()
                assert session_file.exists()

                # Manually call cleanup function, should handle normally
                recorder._cleanup_on_exit()

                # Restore stdout
                sys.stdout = sys_stdout_backup

                # Verify file has been cleaned up
                assert not session_file.exists()

            finally:
                # Ensure stdout is restored
                sys.stdout = sys_stdout_backup
