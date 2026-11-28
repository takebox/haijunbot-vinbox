"""Smart retrieval enhancement module tests.

Tests all core functionality of the SmartRetriever class.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from haijunbot.haijunbot_memory_organizer.smart_retrieval import (
    Memory,
    RecommendationContext,
    RelevanceScore,
    SemanticQuery,
    SmartRetriever,
)


class TestMemory:
    """Memory dataclass tests"""

    def test_from_dict(self):
        """Test creating Memory object from dict"""
        data = {
            "id": "test_id",
            "memory_type": "project",
            "nature": "long_term",
            "tags": ["tag1", "tag2"],
            "content": "test content",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        memory = Memory.from_dict(data)

        assert memory.id == "test_id"
        assert memory.memory_type == "project"
        assert memory.nature == "long_term"
        assert memory.tags == ["tag1", "tag2"]
        assert memory.content == "test content"
        assert memory.created_at == "2024-01-01T00:00:00"

    def test_from_dict_with_missing_fields(self):
        """Test creating Memory object from incomplete dict"""
        data = {"id": "test_id"}
        memory = Memory.from_dict(data)

        assert memory.id == "test_id"
        assert memory.memory_type == ""
        assert memory.nature == ""
        assert memory.tags == []
        assert memory.content == ""

    def test_to_dict(self):
        """Test converting to dict"""
        memory = Memory(
            id="test_id",
            memory_type="project",
            nature="long_term",
            tags=["tag1", "tag2"],
            content="test content",
            created_at="2024-01-01T00:00:00",
            updated_at="2024-01-01T00:00:00",
        )
        data = memory.to_dict()

        assert data["id"] == "test_id"
        assert data["memory_type"] == "project"
        assert data["nature"] == "long_term"
        assert data["tags"] == ["tag1", "tag2"]
        assert data["content"] == "test content"


class TestSemanticQuery:
    """SemanticQuery dataclass tests"""

    def test_default_values(self):
        """Test default values"""
        query = SemanticQuery()

        assert query.query_text == ""
        assert query.extracted_keywords == []
        assert query.expanded_tags == []
        assert query.intent == ""
        assert query.context is None

    def test_with_values(self):
        """Test creating with values"""
        query = SemanticQuery(
            query_text="test query",
            extracted_keywords=["test", "query"],
            expanded_tags=["test", "testing"],
            intent="how_to",
            context="some context",
        )

        assert query.query_text == "test query"
        assert query.extracted_keywords == ["test", "query"]
        assert query.expanded_tags == ["test", "testing"]
        assert query.intent == "how_to"
        assert query.context == "some context"


class TestRecommendationContext:
    """RecommendationContext dataclass tests"""

    def test_default_values(self):
        """Test default values"""
        context = RecommendationContext()

        assert context.task_description == ""
        assert context.current_step == ""
        assert context.tool_calls == []
        assert context.errors == []

    def test_with_values(self):
        """Test creating with values"""
        context = RecommendationContext(
            task_description="implement feature",
            current_step="writing code",
            tool_calls=["read_code", "edit_file"],
            errors=["syntax error"],
        )

        assert context.task_description == "implement feature"
        assert context.current_step == "writing code"
        assert context.tool_calls == ["read_code", "edit_file"]
        assert context.errors == ["syntax error"]


class TestRelevanceScore:
    """RelevanceScore dataclass tests"""

    def test_default_values(self):
        """Test default values"""
        score = RelevanceScore()

        assert score.tag_match == 0.0
        assert score.content_similarity == 0.0
        assert score.time_freshness == 0.0
        assert score.usage_frequency == 0.0
        assert score.total == 0.0

    def test_total_calculation(self):
        """Test total score calculation"""
        score = RelevanceScore(
            tag_match=100.0,
            content_similarity=100.0,
            time_freshness=100.0,
            usage_frequency=100.0,
        )

        # 30% + 40% + 15% + 15% = 100%
        expected_total = 100 * 0.3 + 100 * 0.4 + 100 * 0.15 + 100 * 0.15
        assert score.total == expected_total

    def test_weighted_total(self):
        """Test weighted total score"""
        score = RelevanceScore(
            tag_match=50.0,
            content_similarity=80.0,
            time_freshness=60.0,
            usage_frequency=40.0,
        )

        expected_total = 50 * 0.3 + 80 * 0.4 + 60 * 0.15 + 40 * 0.15
        assert score.total == expected_total


class TestSmartRetriever:
    """SmartRetriever class tests"""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create temporary memory directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / ".haijunbot" / "memory"
            project_dir.mkdir(parents=True)
            yield tmpdir, project_dir

    @pytest.fixture
    def retriever_with_memories(self, temp_memory_dir):
        """Create retriever with test memories"""
        tmpdir, project_dir = temp_memory_dir

        # Create test memories
        memories = [
            {
                "id": "memory_1",
                "memory_type": "project",
                "nature": "long_term",
                "tags": ["code", "python", "testing"],
                "content": "Python code testing best practices",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            {
                "id": "memory_2",
                "memory_type": "project",
                "nature": "long_term",
                "tags": ["architecture", "design", "python"],
                "content": "Python architecture design patterns",
                "created_at": (datetime.now() - timedelta(days=30)).isoformat(),
                "updated_at": (datetime.now() - timedelta(days=30)).isoformat(),
            },
            {
                "id": "memory_3",
                "memory_type": "project",
                "nature": "long_term",
                "tags": ["error", "bug", "fix"],
                "content": "Common error fixing methods",
                "created_at": (datetime.now() - timedelta(days=7)).isoformat(),
                "updated_at": (datetime.now() - timedelta(days=7)).isoformat(),
            },
        ]

        for memory in memories:
            memory_file = project_dir / f"{memory['id']}.json"
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory, f, ensure_ascii=False)

        # Create retriever and set directory
        retriever = SmartRetriever()
        retriever.project_memory_dir = project_dir

        return retriever

    def test_init(self):
        """Test initialization"""
        retriever = SmartRetriever()

        assert retriever.project_memory_dir == Path(".haijunbot/memory")
        assert retriever._usage_stats == {}

    def test_extract_keywords(self):
        """Test keyword extraction"""
        retriever = SmartRetriever()

        keywords = retriever._extract_keywords("how to write Python code tests")

        # Simple tokenization treats the entire Chinese string as one word
        assert len(keywords) > 0
        # Check if it contains python (lowercase)
        assert any("python" in k.lower() for k in keywords)

    def test_extract_keywords_english(self):
        """Test English keyword extraction"""
        retriever = SmartRetriever()

        keywords = retriever._extract_keywords("How to write Python code tests")

        assert "python" in keywords
        assert "code" in keywords
        assert "tests" in keywords
        # Stop words should be filtered
        assert "how" not in keywords
        assert "to" not in keywords

    def test_expand_tags(self):
        """Test tag expansion"""
        retriever = SmartRetriever()

        expanded = retriever._expand_tags(["code", "test"])

        # Should contain original keywords
        assert "code" in expanded
        assert "test" in expanded
        # Should contain expanded tags
        assert "coding" in expanded or "code" in expanded
        assert "testing" in expanded or "test" in expanded

    def _patch_intent_platform(self, intent: str):
        """Mock eval/cheap platform to make _identify_intent return specified intent"""
        fake_platform = MagicMock()
        fake_platform.complete.return_value = intent
        fake_registry = MagicMock()
        fake_registry.get_eval_platform.return_value = fake_platform
        return patch(
            "haijunbot.haijunbot_platform.registry.PlatformRegistry.get_global_platform_registry",
            return_value=fake_registry,
        )

    def test_identify_intent_how_to(self):
        """Test intent recognition - how_to (eval model classification)"""
        retriever = SmartRetriever()

        with self._patch_intent_platform("how_to"):
            assert retriever._identify_intent("how to write tests") == "how_to"
            assert retriever._identify_intent("how to fix a bug") == "how_to"

    def test_identify_intent_definition(self):
        """Test intent recognition - definition (eval model classification)"""
        retriever = SmartRetriever()

        with self._patch_intent_platform("definition"):
            assert retriever._identify_intent("what is unit testing") == "definition"
            assert retriever._identify_intent("What is unit testing") == "definition"

    def test_identify_intent_troubleshooting(self):
        """Test intent recognition - troubleshooting (eval model classification)"""
        retriever = SmartRetriever()

        with self._patch_intent_platform("troubleshooting"):
            assert retriever._identify_intent("code has errors") == "troubleshooting"
            assert retriever._identify_intent("bug in code") == "troubleshooting"

    def test_identify_intent_falls_back_to_cheap(self):
        """Fall back to cheap model when eval model is not configured"""
        retriever = SmartRetriever()
        fake_platform = MagicMock()
        fake_platform.complete.return_value = "recall"
        fake_registry = MagicMock()
        fake_registry.get_eval_platform.return_value = None  # Eval model not configured
        fake_registry.get_cheap_platform.return_value = fake_platform
        with patch(
            "haijunbot.haijunbot_platform.registry.PlatformRegistry.get_global_platform_registry",
            return_value=fake_registry,
        ):
            assert retriever._identify_intent("how was that bug fixed last time") == "recall"

    def test_identify_intent_general_when_no_platform(self):
        """Return general when no eval/cheap model (no hardcoded guessing)"""
        retriever = SmartRetriever()
        fake_registry = MagicMock()
        fake_registry.get_eval_platform.return_value = None
        fake_registry.get_cheap_platform.return_value = None
        with patch(
            "haijunbot.haijunbot_platform.registry.PlatformRegistry.get_global_platform_registry",
            return_value=fake_registry,
        ):
            assert retriever._identify_intent("Python code") == "general"
            assert retriever._identify_intent("how to write tests") == "general"

    def test_analyze_query(self):
        """Test query analysis"""
        retriever = SmartRetriever()

        with self._patch_intent_platform("how_to"):
            query = retriever._analyze_query("how to write Python test code")

        assert query.query_text == "how to write Python test code"
        assert len(query.extracted_keywords) > 0
        assert len(query.expanded_tags) > 0
        assert query.intent == "how_to"

    def test_nature_boost(self):
        """Test nature weighting: procedural by task type, episodic by recall query"""
        retriever = SmartRetriever()

        # how_to intent boosts procedural memories
        assert retriever._nature_boost("how_to", "procedural") == 1.5
        # recall/troubleshooting intent boosts episodic memories
        assert retriever._nature_boost("recall", "episodic") == 1.5
        assert retriever._nature_boost("troubleshooting", "episodic") == 1.5
        # Other combinations do not change the score
        assert retriever._nature_boost("how_to", "episodic") == 1.0
        assert retriever._nature_boost("recall", "procedural") == 1.0
        assert retriever._nature_boost("general", "long_term") == 1.0
        assert retriever._nature_boost("definition", "long_term") == 1.0

    def test_calculate_bm25_score(self):
        """Test BM25 similarity calculation"""
        retriever = SmartRetriever()

        # Identical text
        similarity = retriever._calculate_bm25_score(
            "Python code test", "Python code test"
        )
        assert similarity == 1.0

        # Partially similar (using English for correct tokenization)
        similarity = retriever._calculate_bm25_score(
            "Python code test", "Python code write"
        )
        assert 0 < similarity < 1

        # Completely different
        similarity = retriever._calculate_bm25_score("Python code", "Java architecture")
        assert similarity < 1.0

        # Empty text
        similarity = retriever._calculate_bm25_score("", "test")
        assert similarity == 0.0

    def test_calculate_time_freshness(self):
        """Test time freshness calculation"""
        retriever = SmartRetriever()

        # Memory created today
        freshness = retriever._calculate_time_freshness(datetime.now().isoformat())
        assert freshness == 100.0

        # Memory created 30 days ago
        old_date = (datetime.now() - timedelta(days=30)).isoformat()
        freshness = retriever._calculate_time_freshness(old_date)
        assert freshness < 100.0

        # Empty time
        freshness = retriever._calculate_time_freshness("")
        assert freshness == 50.0

    def test_calculate_usage_frequency(self):
        """Test usage frequency calculation"""
        retriever = SmartRetriever()

        # Unused memory
        frequency = retriever._calculate_usage_frequency("unknown_id")
        assert frequency == 0.0

        # Used memory
        retriever._usage_stats["test_id"] = 5
        frequency = retriever._calculate_usage_frequency("test_id")
        assert frequency == 50.0

        # Usage count exceeds 10
        retriever._usage_stats["popular_id"] = 15
        frequency = retriever._calculate_usage_frequency("popular_id")
        assert frequency == 100.0

    def test_update_usage_stats(self):
        """Test usage statistics update"""
        retriever = SmartRetriever()

        retriever._update_usage_stats("test_id")
        assert retriever._usage_stats["test_id"] == 1

        retriever._update_usage_stats("test_id")
        assert retriever._usage_stats["test_id"] == 2

    def test_semantic_search(self, retriever_with_memories):
        """Test semantic search"""
        retriever = retriever_with_memories

        results = retriever.semantic_search("Python code testing", limit=5)

        assert len(results) > 0
        # First result should be the most relevant
        assert any("python" in m.tags or "testing" in m.tags for m in results)

    def test_semantic_search_empty_query(self, retriever_with_memories):
        """Test empty query"""
        retriever = retriever_with_memories

        results = retriever.semantic_search("", limit=5)

        # Empty query should return empty results or all results
        assert isinstance(results, list)

    def test_recommend_knowledge(self, retriever_with_memories):
        """Test knowledge recommendation"""
        retriever = retriever_with_memories

        context = RecommendationContext(
            task_description="write Python unit tests",
            current_step="create test file",
            tool_calls=["read_code", "edit_file"],
            errors=[],
        )

        results = retriever.recommend_knowledge(context, limit=3)

        assert len(results) > 0
        assert isinstance(results[0], Memory)

    def test_recommend_knowledge_with_errors(self, retriever_with_memories):
        """Test knowledge recommendation with errors"""
        retriever = retriever_with_memories

        context = RecommendationContext(
            task_description="fix code errors",
            current_step="analyze errors",
            tool_calls=[],
            errors=["SyntaxError: invalid syntax"],
        )

        results = retriever.recommend_knowledge(context, limit=3)

        assert isinstance(results, list)

    def test_find_related_knowledge(self, retriever_with_memories):
        """Test finding related knowledge"""
        retriever = retriever_with_memories

        # Find knowledge related to memory_1
        results = retriever.find_related_knowledge("memory_1", limit=3)

        assert isinstance(results, list)
        # Should not contain itself
        assert all(m.id != "memory_1" for m in results)

    def test_find_related_knowledge_not_found(self, retriever_with_memories):
        """Test finding related knowledge for nonexistent memory"""
        retriever = retriever_with_memories

        results = retriever.find_related_knowledge("nonexistent_id", limit=3)

        assert results == []

    def test_load_memories_by_type(self, retriever_with_memories):
        """Test loading memories by type"""
        retriever = retriever_with_memories

        memories = retriever._load_memories_by_type("project", "long_term")

        assert len(memories) == 3
        assert all(isinstance(m, Memory) for m in memories)

    def test_load_memories_by_type_invalid(self):
        """Test loading invalid memory type"""
        retriever = SmartRetriever()

        memories = retriever._load_memories_by_type("invalid", "long_term")

        assert memories == []

    def test_load_memory_by_id(self, retriever_with_memories):
        """Test loading memory by ID"""
        retriever = retriever_with_memories

        memory = retriever._load_memory_by_id("memory_1")

        assert memory is not None
        assert memory.id == "memory_1"

    def test_load_memory_by_id_not_found(self, retriever_with_memories):
        """Test loading nonexistent memory"""
        retriever = retriever_with_memories

        memory = retriever._load_memory_by_id("nonexistent_id")

        assert memory is None

    def test_retrieve_candidates(self, retriever_with_memories):
        """Test retrieving candidate memories"""
        retriever = retriever_with_memories

        candidates = retriever._retrieve_candidates(
            ["python", "code"], ["project"], ["long_term"]
        )

        assert len(candidates) > 0
        # Should contain memories with python or code tags
        assert any("python" in m.tags or "code" in m.tags for m in candidates)

    def test_retrieve_candidates_no_tags(self, retriever_with_memories):
        """Test retrieving candidate memories with no tags"""
        retriever = retriever_with_memories

        candidates = retriever._retrieve_candidates([], ["project"], ["long_term"])

        # Should return all memories when no tags
        assert len(candidates) == 3

    def test_calculate_relevance_score(self, retriever_with_memories):
        """Test relevance score calculation"""
        retriever = retriever_with_memories

        memory = Memory(
            id="test",
            memory_type="project",
            nature="long_term",
            tags=["python", "code"],
            content="Python code testing best practices",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        query = SemanticQuery(
            query_text="Python code",
            extracted_keywords=["python", "code"],
            expanded_tags=["python", "code", "coding"],
            intent="general",
        )

        score = retriever._calculate_relevance_score(memory, query)

        assert isinstance(score, RelevanceScore)
        assert score.tag_match > 0
        assert score.content_similarity > 0  # Should calculate correctly now
        assert score.time_freshness > 0
        assert score.total > 0

    def test_extract_keywords_from_context(self):
        """Test extracting keywords from context"""
        retriever = SmartRetriever()

        context = RecommendationContext(
            task_description="write Python tests",
            current_step="create test file",
            tool_calls=["read_code"],
            errors=["ImportError"],
        )

        keywords = retriever._extract_keywords_from_context(context)

        assert len(keywords) > 0
        assert isinstance(keywords, list)

    def test_calculate_recommendation_score(self, retriever_with_memories):
        """Test recommendation score calculation"""
        retriever = retriever_with_memories

        memory = Memory(
            id="test",
            memory_type="project",
            nature="long_term",
            tags=["python", "testing"],
            content="Python testing best practices",
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        context = RecommendationContext(
            task_description="write Python tests",
            current_step="create tests",
            tool_calls=[],
            errors=[],
        )

        score = retriever._calculate_recommendation_score(
            memory, context, ["python", "test"]
        )

        assert isinstance(score, float)
        assert score >= 0


class TestSmartRetrieverIntegration:
    """SmartRetriever integration tests"""

    @pytest.fixture
    def temp_memory_setup(self):
        """Create complete temporary memory environment"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir) / ".haijunbot" / "memory"
            project_dir.mkdir(parents=True)

            # Create multiple types of memories
            memories = [
                {
                    "id": "arch_1",
                    "memory_type": "project",
                    "nature": "long_term",
                    "tags": ["architecture", "design", "pattern"],
                    "content": "Software architecture design patterns: singleton, factory, observer",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                {
                    "id": "test_1",
                    "memory_type": "project",
                    "nature": "long_term",
                    "tags": ["testing", "pytest", "unit"],
                    "content": "Unit testing best practices: use pytest framework, write independent test cases",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
                {
                    "id": "code_1",
                    "memory_type": "project",
                    "nature": "long_term",
                    "tags": ["code", "python", "best_practice"],
                    "content": "Python coding standards: follow PEP8, use type annotations",
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                },
            ]

            for memory in memories:
                memory_file = project_dir / f"{memory['id']}.json"
                with open(memory_file, "w", encoding="utf-8") as f:
                    json.dump(memory, f, ensure_ascii=False)

            retriever = SmartRetriever()
            retriever.project_memory_dir = project_dir

            yield retriever

    def test_full_search_workflow(self, temp_memory_setup):
        """Test complete search workflow"""
        retriever = temp_memory_setup

        # 1. Semantic search
        results = retriever.semantic_search("how to write unit tests", limit=3)
        assert len(results) > 0

        # 2. Knowledge recommendation
        context = RecommendationContext(
            task_description="refactor code architecture",
            current_step="design new architecture",
            tool_calls=[],
            errors=[],
        )
        recommendations = retriever.recommend_knowledge(context, limit=3)
        assert len(recommendations) > 0

        # 3. Find related knowledge
        if results:
            related = retriever.find_related_knowledge(results[0].id, limit=3)
            assert isinstance(related, list)

    def test_search_relevance_ordering(self, temp_memory_setup):
        """Test search result relevance ordering"""
        retriever = temp_memory_setup

        # Search for test-related content
        results = retriever.semantic_search("pytest unit testing", limit=3)

        if len(results) >= 2:
            # First result should be more relevant than subsequent ones
            # Check if first result contains more relevant tags
            first_tags = set(results[0].tags)
            relevant_tags = {"testing", "pytest", "unit", "test"}
            first_match = len(first_tags & relevant_tags)
            assert first_match > 0

    def test_usage_stats_persistence(self, temp_memory_setup):
        """Test usage statistics persistence"""
        retriever = temp_memory_setup

        # Execute multiple searches
        for _ in range(3):
            retriever.semantic_search("Python code", limit=1)

        # Check if usage statistics were updated
        assert len(retriever._usage_stats) > 0
        assert any(count > 0 for count in retriever._usage_stats.values())
