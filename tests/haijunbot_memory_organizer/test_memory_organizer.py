# -*- coding: utf-8 -*-
"""haijunbot_memory_organizer.memory_organizer module unit tests"""

import pytest
import json
from unittest.mock import patch

from haijunbot.haijunbot_memory_organizer.memory_organizer import MemoryOrganizer


class TestMemoryOrganizer:
    """Test MemoryOrganizer class"""

    @pytest.fixture
    def organizer(self):
        """Create MemoryOrganizer instance for testing"""
        with patch("haijunbot.haijunbot_memory_organizer.memory_organizer.PlatformRegistry"):
            return MemoryOrganizer()

    def test_get_memory_files_project_type(self, organizer, temp_dir):
        """Test getting project long-term memory files"""
        # Create project memory directory
        project_memory_dir = temp_dir / ".haijunbot" / "memory"
        project_memory_dir.mkdir(parents=True)

        # Create test files
        (project_memory_dir / "memory1.json").write_text('{"test": "data"}')
        (project_memory_dir / "memory2.json").write_text('{"test": "data2"}')

        with patch.object(organizer, "project_memory_dir", project_memory_dir):
            result = organizer._get_memory_files("project_long_term")
            assert len(result) == 2
            assert all(f.suffix == ".json" for f in result)

    def test_get_memory_files_global_type(self, organizer, temp_dir):
        """Test getting global long-term memory files"""
        # Create global memory directory
        global_memory_dir = temp_dir / "memory" / "global_long_term"
        global_memory_dir.mkdir(parents=True)

        # Create test files
        (global_memory_dir / "memory1.json").write_text('{"test": "data"}')

        with patch.object(organizer, "global_memory_dir", temp_dir / "memory"):
            result = organizer._get_memory_files("global_long_term")
            assert len(result) >= 1
            assert all(f.suffix == ".json" for f in result)

    def test_get_memory_files_invalid_type(self, organizer):
        """Test invalid memory type"""
        with pytest.raises(ValueError, match="Unsupported memory type"):
            organizer._get_memory_files("invalid_type")

    def test_get_memory_files_nonexistent_dir(self, organizer, temp_dir):
        """Test nonexistent directory"""
        with patch.object(organizer, "project_memory_dir", temp_dir / "nonexistent"):
            result = organizer._get_memory_files("project_long_term")
            assert result == []

    def test_load_memories_success(self, organizer, temp_dir):
        """Test successful memory loading"""
        memory_dir = temp_dir / "memory"
        memory_dir.mkdir(parents=True)

        # Create test memory files
        memory1 = memory_dir / "memory1.json"
        memory1.write_text(
            json.dumps(
                {
                    "content": "Test memory 1",
                    "tags": ["test", "memory"],
                    "created_at": "2024-01-01",
                }
            )
        )

        memory2 = memory_dir / "memory2.json"
        memory2.write_text(
            json.dumps(
                {
                    "content": "Test memory 2",
                    "tags": ["test"],
                    "created_at": "2024-01-02",
                }
            )
        )

        with patch.object(
            organizer, "_get_memory_files", return_value=[memory1, memory2]
        ):
            result = organizer._load_memories("project_long_term")
            assert len(result) == 2
            assert result[0]["content"] == "Test memory 1"
            assert result[1]["content"] == "Test memory 2"

    def test_load_memories_invalid_json(self, organizer, temp_dir):
        """Test loading invalid JSON file"""
        memory_dir = temp_dir / "memory"
        memory_dir.mkdir(parents=True)

        invalid_file = memory_dir / "invalid.json"
        invalid_file.write_text("invalid json content")

        with patch.object(organizer, "_get_memory_files", return_value=[invalid_file]):
            result = organizer._load_memories("project_long_term")
            # Should skip invalid files
            assert len(result) == 0

    def test_find_overlapping_memories_basic(self, organizer):
        """Test finding overlapping memories (basic)"""
        memories = [
            {"tags": ["python", "api", "test"]},
            {"tags": ["python", "api", "web"]},
            {"tags": ["java", "api"]},
        ]

        result = organizer._find_overlapping_memories(memories, min_overlap=2)
        assert isinstance(result, dict)
        # First two memories have 2 overlapping tags (python, api)
        assert 2 in result

    def test_find_overlapping_memories_no_overlap(self, organizer):
        """Test memories with no overlap"""
        memories = [
            {"tags": ["python"]},
            {"tags": ["java"]},
            {"tags": ["rust"]},
        ]

        result = organizer._find_overlapping_memories(memories, min_overlap=2)
        # Not enough overlap
        assert len(result) == 0 or all(len(groups) == 0 for groups in result.values())

    def test_find_overlapping_memories_high_overlap(self, organizer):
        """Test high overlap memories"""
        memories = [
            {"tags": ["python", "api", "web", "test"]},
            {"tags": ["python", "api", "web", "frontend"]},
            {"tags": ["python", "api", "web", "backend"]},
        ]

        result = organizer._find_overlapping_memories(memories, min_overlap=3)
        # Three memories have 3 overlapping tags (python, api, web)
        assert 3 in result or 4 in result

    def test_find_overlapping_memories_empty_tags(self, organizer):
        """Test memories with empty tags"""
        memories = [
            {"tags": []},
            {"tags": []},
        ]

        result = organizer._find_overlapping_memories(memories, min_overlap=2)
        # No tags, should have no overlap
        assert len(result) == 0 or all(len(groups) == 0 for groups in result.values())

    def test_find_overlapping_memories_no_tags_key(self, organizer):
        """Test memories without tags key"""
        memories = [
            {"content": "test"},
            {"content": "test2"},
        ]

        result = organizer._find_overlapping_memories(memories, min_overlap=2)
        # No tags, should have no overlap
        assert len(result) == 0 or all(len(groups) == 0 for groups in result.values())
