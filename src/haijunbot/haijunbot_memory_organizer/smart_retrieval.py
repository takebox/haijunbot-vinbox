"""Smart retrieval enhancement module

This module provides knowledge retrieval enhancement features, including:
- Semantic search: smart retrieval based on query intent and keywords
- Knowledge recommendation: knowledge recommendation based on task context
- Related knowledge association: find knowledge related to the specified memory
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import jieba

from haijunbot.haijunbot_utils.config import get_data_dir


@dataclass
class Memory:
    """Memory data class

    Stores the basic information of a memory.

    Uses two orthogonal fields:
    - memory_type (scope): project / global
    - nature (kind): long_term / procedural / episodic
    """

    id: str = ""
    memory_type: str = ""
    nature: str = ""
    tags: List[str] = field(default_factory=list)
    content: str = ""
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Create a Memory object from a dict"""
        return cls(
            id=data.get("id", ""),
            memory_type=data.get("memory_type", ""),
            nature=data.get("nature", ""),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a dict"""
        return {
            "id": self.id,
            "memory_type": self.memory_type,
            "nature": self.nature,
            "tags": self.tags,
            "content": self.content,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class SemanticQuery:
    """Semantic query data class

    Stores the result of a query analysis.
    """

    query_text: str = ""  # Original query text
    extracted_keywords: List[str] = field(default_factory=list)  # Extracted keywords
    expanded_tags: List[str] = field(default_factory=list)  # Expanded tags
    intent: str = ""  # Query intent
    context: Optional[str] = None  # Context information


@dataclass
class RecommendationContext:
    """Recommendation context data class

    Stores the context information for task execution, used for knowledge recommendation.
    """

    task_description: str = ""  # Task description
    current_step: str = ""  # Current step
    tool_calls: List[str] = field(default_factory=list)  # Tool call list
    errors: List[str] = field(default_factory=list)  # Error list


@dataclass
class RelevanceScore:
    """Relevance score data class

    Stores the relevance scores for each dimension.
    """

    tag_match: float = 0.0  # Tag match (30%)
    content_similarity: float = 0.0  # Content semantic similarity (40%)
    time_freshness: float = 0.0  # Time freshness (15%)
    usage_frequency: float = 0.0  # Usage frequency (15%)

    @property
    def total(self) -> float:
        """Calculate the weighted total score"""
        return (
            self.tag_match * 0.3
            + self.content_similarity * 0.4
            + self.time_freshness * 0.15
            + self.usage_frequency * 0.15
        )


class SmartRetriever:
    """Smart retriever

    Provides semantic search, knowledge recommendation, and related knowledge association.
    """

    # Mapping of common keywords to tags
    KEYWORD_TAG_MAPPING: Dict[str, List[str]] = {
        "code": ["code", "coding", "programming"],
        "test": ["test", "testing", "pytest"],
        "refactoring": ["refactoring", "refactor"],
        "architecture": ["architecture", "design"],
        "config": ["config", "configuration"],
        "deploy": ["deploy", "deployment"],
        "doc": ["doc", "documentation"],
        "security": ["security"],
        "performance": ["performance"],
        "error": ["error", "bug", "fix"],
        "memory": ["memory"],
        "rule": ["rule"],
    }

    def __init__(self):
        """Initialize the smart retriever"""
        self.project_memory_dir = Path(".haijunbot/memory")
        self.global_memory_dir = Path(get_data_dir()) / "memory"
        self._usage_stats: Dict[str, int] = {}  # Memory usage statistics

    def semantic_search(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        natures: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Memory]:
        """Semantic search

        Smart retrieval based on query intent and keywords.

        Args:
            query: The query text
            memory_types: The list of scopes to search (project/global); defaults to all scopes
            natures: The list of natures to search (long_term/procedural/episodic); defaults to all natures
            limit: The maximum number of results to return

        Returns:
            The list of memories sorted by relevance
        """
        # 1. Analyze the query
        semantic_query = self._analyze_query(query)

        # 2. Determine the retrieval types
        if memory_types is None:
            memory_types = ["project", "global"]
        if natures is None:
            natures = ["long_term", "procedural", "episodic"]

        # 3. Retrieve candidate memories
        candidates = self._retrieve_candidates(
            semantic_query.expanded_tags, memory_types, natures
        )

        # 4. Load all memories to build a corpus
        all_memories = self._load_all_memories(memory_types, natures)
        corpus = [memory.content for memory in all_memories]

        # 5. Calculate relevance scores and sort
        scored_memories = []
        for memory in candidates:
            # Use BM25 to compute the content similarity
            content_similarity = self._calculate_bm25_score(
                query, memory.content, corpus
            )

            # Compute the scores for the other dimensions
            tag_match = self._calculate_tag_match(memory, semantic_query)
            time_freshness = self._calculate_time_freshness(memory.created_at)
            usage_frequency = self._calculate_usage_frequency(memory.id)

            # Combined score (weights: content 40%, tags 30%, time 15%, usage frequency 15%)
            total_score = (
                content_similarity * 0.4
                + tag_match * 0.3
                + time_freshness * 0.15
                + usage_frequency * 0.15
            )

            # Nature boost: procedural memories match task-type (how_to) queries; episodic memories match recall queries
            nature_boost = self._nature_boost(semantic_query.intent, memory.nature)
            total_score *= nature_boost

            scored_memories.append((memory, total_score))

        # 6. Sort by score
        scored_memories.sort(key=lambda x: x[1], reverse=True)

        # 7. Return the top N results
        result = [m for m, _ in scored_memories[:limit]]

        # Update the usage statistics
        for memory in result:
            self._update_usage_stats(memory.id)

        return result

    def recommend_knowledge(
        self,
        context: RecommendationContext,
        limit: int = 5,
    ) -> List[Memory]:
        """Knowledge recommendation

        Recommends related knowledge based on task context.

        Args:
            context: The recommendation context
            limit: The maximum number of results to return

        Returns:
            The recommended memory list
        """
        # 1. Extract keywords from the context
        keywords = self._extract_keywords_from_context(context)

        # 2. Expand the tags
        expanded_tags = self._expand_tags(keywords)

        # 3. Retrieve candidate memories
        candidates = self._retrieve_candidates(
            expanded_tags,
            ["project", "global"],
            ["long_term", "procedural", "episodic"],
        )

        # 4. Calculate the recommendation score
        scored_memories = []
        for memory in candidates:
            score = self._calculate_recommendation_score(memory, context, keywords)
            scored_memories.append((memory, score))

        # 5. Sort by score
        scored_memories.sort(key=lambda x: x[1], reverse=True)

        # 6. Return the top N results
        return [m for m, _ in scored_memories[:limit]]

    def find_related_knowledge(
        self,
        memory_id: str,
        limit: int = 5,
    ) -> List[Memory]:
        """Find related knowledge

        Finds other knowledge related to the specified memory.

        Args:
            memory_id: The memory ID
            limit: The maximum number of results to return

        Returns:
            The related memory list
        """
        # 1. Load the target memory
        target_memory = self._load_memory_by_id(memory_id)
        if target_memory is None:
            return []

        # 2. Load all memories
        all_memories = self._load_all_memories(
            ["project", "global"], ["long_term", "procedural", "episodic"]
        )

        # 3. Calculate the association score
        related_memories = []
        for memory in all_memories:
            if memory.id == memory_id:
                continue

            # Compute the tag overlap
            tag_overlap = len(set(target_memory.tags) & set(memory.tags))

            # Compute the content similarity
            content_similarity = self._calculate_bm25_score(
                target_memory.content, memory.content
            )

            # Combined score: tag overlap (50%) + content similarity (50%)
            score = tag_overlap * 0.5 + content_similarity * 0.5

            # Keep only memories with some association (at least 2 shared tags or similarity >= 0.3)
            if tag_overlap >= 2 or content_similarity >= 0.3:
                related_memories.append((memory, score))

        # 4. Sort by score
        related_memories.sort(key=lambda x: x[1], reverse=True)

        # 5. Return the top N results
        return [m for m, _ in related_memories[:limit]]

    def _analyze_query(self, query: str) -> SemanticQuery:
        """Analyze the query text

        Extract keywords, expand tags, and identify the intent.
        """
        # Extract keywords
        keywords = self._extract_keywords(query)

        # Expand tags
        expanded_tags = self._expand_tags(keywords)

        # Identify the intent
        intent = self._identify_intent(query)

        return SemanticQuery(
            query_text=query,
            extracted_keywords=keywords,
            expanded_tags=expanded_tags,
            intent=intent,
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Use jieba for word segmentation
        words = jieba.cut(text)
        keywords = []

        # Filter out stop words and short words
        stop_words = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "have",
            "has",
            "had",
            "do",
            "does",
            "did",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "must",
            "can",
            "to",
            "of",
            "in",
            "for",
            "on",
            "with",
            "at",
            "by",
            "from",
            "as",
            "into",
            "through",
            "during",
            "before",
            "after",
            "above",
            "below",
            "between",
            "under",
            "again",
            "further",
            "then",
            "once",
            "here",
            "there",
            "when",
            "where",
            "why",
            "how",
            "all",
            "each",
            "few",
            "more",
            "most",
            "other",
            "some",
            "such",
            "no",
            "nor",
            "not",
            "only",
            "own",
            "same",
            "so",
            "than",
            "too",
            "very",
            "just",
            "and",
            "but",
            "if",
            "or",
            "because",
            "until",
            "while",
        }

        for word in words:
            word_lower = word.lower()
            if len(word) >= 2 and word_lower not in stop_words:
                keywords.append(word_lower)

        return list(set(keywords))

    def _expand_tags(self, keywords: List[str]) -> List[str]:
        """Expand keywords into tags"""
        expanded_tags = set(keywords)

        for keyword in keywords:
            # Check the keyword mapping
            for key, tags in self.KEYWORD_TAG_MAPPING.items():
                if keyword in key or key in keyword:
                    expanded_tags.update(tags)

        return list(expanded_tags)

    def _identify_intent(self, query: str) -> str:
        """Identify the query intent

        Use the eval platform to classify the query; fall back to the cheap platform when no eval platform is configured.
        Return "general" when neither platform is available or both calls fail (no hardcoded guessing).
        """
        try:
            from haijunbot.haijunbot_platform.registry import PlatformRegistry

            registry = PlatformRegistry.get_global_platform_registry()
            platform = registry.get_eval_platform()
            if platform is None:
                platform = registry.get_cheap_platform()
            if platform is None:
                return "general"

            categories = "how_to, definition, reason, troubleshooting, recommendation, recall, general"
            prompt = (
                "Classify the following user query into the single best-matching intent category. "
                f"Available categories: {categories}.\n"
                "Category meanings:\n"
                "- how_to: asks how to do something (methods, steps, procedures)\n"
                "- definition: asks for the definition or explanation of a concept/term\n"
                "- reason: asks for the reason/why\n"
                "- troubleshooting: diagnose/fix errors, bugs, problems\n"
                "- recommendation: seeks a recommendation/best approach/advice\n"
                "- recall: recall/find something that happened in the past (last time, before, then)\n"
                "- general: none of the above matches\n"
                "Output only one category name, nothing else.\n\n"
                f"User query: {query}"
            )
            result = platform.complete(prompt)
            if not result or result == "<output interrupted by user>":
                return "general"
            result = result.strip().lower()
            if result == "<output interrupted by user>":
                return "general"
            for cat in (
                "how_to",
                "definition",
                "reason",
                "troubleshooting",
                "recommendation",
                "recall",
                "general",
            ):
                if cat in result:
                    return cat
            return "general"
        except Exception:
            return "general"

    def _nature_boost(self, intent: str, nature: str) -> float:
        """Apply a weighted boost to the memory nature based on the query intent.

        Procedural memories match task-type queries: boosted for the how_to intent;
        episodic memories match recall queries: boosted for the recall / troubleshooting intents.
        Otherwise return 1.0 (leaving the original score unchanged).

        Args:
            intent: The query intent (how_to/definition/reason/troubleshooting/recommendation/recall/general)
            nature: The memory nature (long_term/procedural/episodic)

        Returns:
            float: The weighting factor
        """
        if intent == "how_to" and nature == "procedural":
            return 1.5
        if intent in ("recall", "troubleshooting") and nature == "episodic":
            return 1.5
        return 1.0

    def _retrieve_candidates(
        self, tags: List[str], memory_types: List[str], natures: List[str]
    ) -> List[Memory]:
        """Retrieve candidate memories"""
        candidates = []

        for memory_type in memory_types:
            for nature in natures:
                memories = self._load_memories_by_type(memory_type, nature)
                for memory in memories:
                    # Check the tag match
                    if tags:
                        memory_tags_lower = [t.lower() for t in memory.tags]
                        tags_lower = [t.lower() for t in tags]
                        if any(tag in memory_tags_lower for tag in tags_lower):
                            candidates.append(memory)
                    else:
                        candidates.append(memory)

        return candidates

    def _load_memories_by_type(self, memory_type: str, nature: str) -> List[Memory]:
        """Load all memories of the specified scope and nature"""
        memories: List[Memory] = []

        memory_dir = self._get_type_dir(memory_type, nature)
        if memory_dir is None or not memory_dir.exists():
            return memories

        for memory_file in memory_dir.glob("*.json"):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    memories.append(Memory.from_dict(data))
            except Exception:
                continue

        return memories

    def _get_type_dir(self, memory_type: str, nature: str) -> Optional[Path]:
        """Return the storage directory for the scope and nature (keep consistent with MemoryTool._get_memory_dir)"""
        if memory_type == "project":
            if nature == "long_term":
                return self.project_memory_dir
            elif nature == "procedural":
                return self.project_memory_dir / "procedural"
            elif nature == "episodic":
                return self.project_memory_dir / "episodic"
        elif memory_type == "global":
            if nature == "long_term":
                return self.global_memory_dir / "global_long_term"
            elif nature == "procedural":
                return self.global_memory_dir / "procedural"
            elif nature == "episodic":
                return self.global_memory_dir / "episodic"
        return None

    def _load_all_memories(
        self, memory_types: List[str], natures: List[str]
    ) -> List[Memory]:
        """Load all memories of the specified scopes and natures"""
        all_memories = []
        for memory_type in memory_types:
            for nature in natures:
                all_memories.extend(self._load_memories_by_type(memory_type, nature))
        return all_memories

    def _load_memory_by_id(self, memory_id: str) -> Optional[Memory]:
        """Load a memory by ID"""
        # Search in the project memories
        for memory_type in ["project", "global"]:
            for nature in ["long_term", "procedural", "episodic"]:
                memory_dir = self._get_type_dir(memory_type, nature)
                if memory_dir is None:
                    continue
                memory_file = memory_dir / f"{memory_id}.json"
                if memory_file.exists():
                    try:
                        with open(memory_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            return Memory.from_dict(data)
                    except Exception:
                        pass

        return None

    def _calculate_tag_match(self, memory: Memory, query: SemanticQuery) -> float:
        """Calculate the tag match score (0-100)"""
        if not query.expanded_tags:
            return 0.0

        memory_tags_lower = [t.lower() for t in memory.tags]
        query_tags_lower = [t.lower() for t in query.expanded_tags]
        matched_tags = sum(1 for tag in query_tags_lower if tag in memory_tags_lower)
        return min(100.0, matched_tags * 20.0)  # 20 points per matched tag

    def _calculate_relevance_score(
        self, memory: Memory, query: SemanticQuery
    ) -> RelevanceScore:
        """Calculate the relevance score"""
        score = RelevanceScore()

        # 1. Tag match (0-100)
        score.tag_match = self._calculate_tag_match(memory, query)

        # 2. Content semantic similarity (0-100)
        score.content_similarity = (
            self._calculate_bm25_score(query.query_text, memory.content) * 100
        )

        # 3. Time freshness (0-100)
        score.time_freshness = self._calculate_time_freshness(memory.created_at)

        # 4. Usage frequency (0-100)
        score.usage_frequency = self._calculate_usage_frequency(memory.id)

        return score

    def _calculate_bm25_score(
        self, text1: str, text2: str, corpus: Optional[List[str]] = None
    ) -> float:
        """Calculate the content similarity (using the BM25 algorithm)"""
        if not text1 or not text2:
            return 0.0

        # If the texts are identical, return 1.0 directly
        if text1 == text2:
            return 1.0

        # Extract keywords
        keywords1 = self._extract_keywords(text1)
        keywords2 = self._extract_keywords(text2)

        if not keywords1 or not keywords2:
            return 0.0

        # Compute the term frequency (TF)
        tf1 = {}
        tf2 = {}
        for word in keywords1:
            tf1[word] = tf1.get(word, 0) + 1
        for word in keywords2:
            tf2[word] = tf2.get(word, 0) + 1

        # BM25 parameters
        k1 = 1.5
        b = 0.75

        # Compute the average document length
        avgdl = (len(keywords1) + len(keywords2)) / 2

        # Compute the BM25 score
        score = 0.0

        # Iterate over all words in the query document (text1)
        for word in set(keywords1):
            if word in tf2:
                # Term frequency
                tf = tf2[word]
                # Document length
                dl = len(keywords2)

                # The TF component of BM25
                tf_component = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avgdl))

                # Simplified IDF (assuming only two documents)
                # If the word appears in both documents, the IDF is lower
                # If the word appears in only one document, the IDF is higher
                if word in tf1:
                    idf = 0.5  # Appears in both documents
                else:
                    idf = 1.0  # Appears in only one document

                score += idf * tf_component

        # Normalize to the 0-1 range
        # Normalize using the maximum possible score
        max_possible_score = len(set(keywords1)) * 1.0 * (k1 + 1) / (k1 * (1 - b))
        if max_possible_score > 0:
            normalized_score = score / max_possible_score
        else:
            normalized_score = 0.0

        return min(1.0, max(0.0, normalized_score))

    def _calculate_time_freshness(self, created_at: str) -> float:
        """Calculate the time freshness (0-100)"""
        if not created_at:
            return 50.0  # Default to medium freshness

        try:
            # Parse the time
            created_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            now = (
                datetime.now(created_time.tzinfo)
                if created_time.tzinfo
                else datetime.now()
            )

            # Compute the day difference
            days_diff = (now - created_time).days

            # Freshness decay: 100 within 7 days, then minus 10 every 7 days, minimum 10
            if days_diff <= 7:
                return 100.0
            else:
                freshness = 100.0 - ((days_diff - 7) / 7) * 10
                return max(10.0, freshness)
        except Exception:
            return 50.0

    def _calculate_usage_frequency(self, memory_id: str) -> float:
        """Calculate the usage frequency score (0-100)"""
        usage_count = self._usage_stats.get(memory_id, 0)

        # More uses yield a higher score, capped at 100
        # Each use adds 10 points, capped at 100
        return min(100.0, usage_count * 10)

    def _update_usage_stats(self, memory_id: str) -> None:
        """Update the usage statistics"""
        self._usage_stats[memory_id] = self._usage_stats.get(memory_id, 0) + 1

    def _extract_keywords_from_context(
        self, context: RecommendationContext
    ) -> List[str]:
        """Extract keywords from the recommendation context"""
        keywords = []

        # Extract from the task description
        if context.task_description:
            keywords.extend(self._extract_keywords(context.task_description))

        # Extract from the current step
        if context.current_step:
            keywords.extend(self._extract_keywords(context.current_step))

        # Extract from the tool calls
        for tool_call in context.tool_calls:
            keywords.extend(self._extract_keywords(tool_call))

        # Extract from the error messages
        for error in context.errors:
            keywords.extend(self._extract_keywords(error))

        return list(set(keywords))

    def _calculate_recommendation_score(
        self,
        memory: Memory,
        context: RecommendationContext,
        keywords: List[str],
    ) -> float:
        """Calculate the recommendation score"""
        # 1. Tag match (30%)
        expanded_tags = self._expand_tags(keywords)
        memory_tags_lower = [t.lower() for t in memory.tags]
        tags_lower = [t.lower() for t in expanded_tags]
        matched_tags = sum(1 for tag in tags_lower if tag in memory_tags_lower)
        tag_score = min(100, matched_tags * 20)

        # 2. Content similarity (40%)
        combined_text = f"{context.task_description} {context.current_step}"
        content_score = self._calculate_bm25_score(combined_text, memory.content) * 100

        # 3. Time freshness (15%)
        time_score = self._calculate_time_freshness(memory.created_at)

        # 4. Usage frequency (15%)
        usage_score = self._calculate_usage_frequency(memory.id)

        # Weighted total score
        return (
            tag_score * 0.3
            + content_score * 0.4
            + time_score * 0.15
            + usage_score * 0.15
        )
