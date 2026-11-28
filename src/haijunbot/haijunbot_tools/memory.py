# -*- coding: utf-8 -*-
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.config import (
    calculate_token_limit,
    get_data_dir,
    get_max_input_token_count,
    get_memory_compress_threshold,
    is_enable_memory_compress,
    is_enable_memory_value_filter,
    save_exception,
)
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.globals import (
    add_short_term_memory,
    clear_short_term_memories,
    get_short_term_memories,
    short_term_memories,
)
from haijunbot.haijunbot_utils.output import PrettyOutput

# Lazy import of SmartRetriever to avoid circular dependency
_smart_retriever = None


def _get_smart_retriever():
    """Lazily get SmartRetriever instance"""
    global _smart_retriever
    if _smart_retriever is None:
        from haijunbot.haijunbot_memory_organizer.smart_retrieval import SmartRetriever

        _smart_retriever = SmartRetriever()
    return _smart_retriever


class MemoryTool:
    """Unified memory management tool supporting save, retrieve, and clear operations"""

    name = "memory"
    description = """Unified memory management tool supporting three operations (only one per call, parameters vary by operation):

1. **save**: Store information in the memory library (supports batch). Memory has two orthogonal dimensions: memory_type=scope (project/global/short_term), nature=type (long_term/procedural how-to/episodic archive). For example, project+long_term=project long-term, global+procedural=global procedural. Optional importance annotation (high/medium/low, defaults to heuristic value filtering), optional source annotation.

2. **retrieve**: Retrieve information from the memory library, supports filtering by scope (memory_type), type (nature), and tags, with optional semantic search

3. **clear**: Clear specified memories by type/tag/ID. Note: clearing is irreversible

**Key points**:
- Only one operation can be executed per call (save/retrieve/clear)
- Parameters vary by operation type
- During save, the system automatically performs write-time value filtering and over-length compression: content without explicit importance annotation that lacks value (too short/purely polite) is automatically filtered; over-length content is summarized and compressed, with the full original content preserved in original_content. These are automatic mechanisms requiring no Agent intervention."""

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["save", "retrieve", "clear"],
                "description": "Operation to execute: save / retrieve / clear",
            },
            # Parameters for save operation
            "memories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "memory_type": {
                            "type": "string",
                            "enum": ["project", "global", "short_term"],
                            "description": "Memory scope: project / global / short_term",
                        },
                        "nature": {
                            "type": "string",
                            "enum": ["long_term", "procedural", "episodic"],
                            "description": "Memory type: long_term / procedural (how-to/pitfall experience) / episodic (historical archive)",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Associated tags (used for retrieval filtering)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Memory content to save",
                        },
                        "importance": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "Importance annotation (optional, defaults to heuristic value filtering)",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source annotation (optional, e.g. task name/session ID)",
                        },
                    },
                    "required": ["memory_type", "tags", "content"],
                },
                "description": "Array of memories to save (only used by save operation)",
            },
            # Parameters for retrieve operation
            "memory_types": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["project", "global", "short_term", "all"],
                },
                "description": "Filter memories by scope (only used by retrieve; all means all scopes)",
            },
            "natures": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["long_term", "procedural", "episodic", "all"],
                },
                "description": "Filter memories by type (optional, only used by retrieve; all means all types)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by tags (optional, used by retrieve and clear operations)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results to return (optional, only used by retrieve operation)",
                "minimum": 1,
            },
            "smart_search": {
                "type": "boolean",
                "description": "Whether to enable semantic search (optional, only used by retrieve operation)",
                "default": False,
            },
            "query": {
                "type": "string",
                "description": "Query text for semantic search (used when smart_search=True and operation is retrieve)",
            },
            # Parameters for clear operation
            "memory_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of memory IDs to clear (optional, only used by clear)",
            },
            "confirm": {
                "type": "boolean",
                "description": "Confirm clear operation (only used by clear; must be true to execute deletion)",
                "default": False,
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        """Initialize memory management tool"""
        self.project_memory_dir = Path(".haijunbot/memory")
        self.global_memory_dir = Path(get_data_dir()) / "memory"

    def _get_memory_dir(self, memory_type: str, nature: str = "long_term") -> Path:
        """Get storage directory based on scope (memory_type) and type (nature)

        Scope: project / global; Type: long_term / procedural / episodic.
        short_term is stored in memory not on disk; a placeholder directory is returned here (handled by the caller).
        """
        if memory_type == "project":
            if nature == "long_term":
                return Path(self.project_memory_dir)
            elif nature == "procedural":
                return Path(self.project_memory_dir) / "procedural"
            elif nature == "episodic":
                return Path(self.project_memory_dir) / "episodic"
        elif memory_type == "global":
            if nature == "long_term":
                return Path(self.global_memory_dir) / "global_long_term"
            elif nature == "procedural":
                return Path(self.global_memory_dir) / "procedural"
            elif nature == "episodic":
                return Path(self.global_memory_dir) / "episodic"
        elif memory_type == "short_term":
            return Path(self.global_memory_dir) / "short_term"
        raise ValueError(f"Unknown memory type: memory_type={memory_type}, nature={nature}")

    def _generate_memory_id(self) -> str:
        """Generate unique memory ID"""
        # Add microsecond timestamp to ensure uniqueness
        time.sleep(0.001)  # Ensure different memories have different timestamps
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    # ========== Methods for save operation ==========

    # Polite/placeholder content with no informational value, discarded during heuristic filtering
    _LOW_VALUE_PHRASES = (
        "ok",
        "okay",
        "understood",
        "got it",
        "understood",
        "hmm",
        "oh",
        "ok",
        "okay",
        "ok, understood",
        "understood",
        "ok, got it",
        "no problem",
        "can do",
        "sure",
        "ok",
        "thanks",
        "thank you",
        "you're welcome",
        "goodbye",
        "hello",
        "hello",
        "hi",
        "thanks",
        "done",
        "completed",
        "ok ok",
        "mmhmm",
        "yes",
        "right",
        "correct",
    )

    def _should_store_memory(self, memory_data: Dict[str, Any]) -> bool:
        """Write-time memory value filtering: determine whether a memory is worth storing.

        Rules:
        1. User explicitly annotated importance (high/medium/low) -> always keep (respect explicit intent).
        2. No explicit annotation -> heuristic judgment:
            - Content too short after stripping whitespace (< 8 chars) -> discard
            - Purely polite/placeholder content (matches _LOW_VALUE_PHRASES) -> discard
            - Other content is conservatively kept (avoid mistakenly deleting valuable information).
        3. Filtering only applies to disk/memory storage, does not affect side effects like tags already collected by the caller.
        """
        # Respect user's explicit importance annotation
        if "importance" in memory_data:
            return True

        content = (memory_data.get("content") or "").strip()
        if not content:
            return False

        # Too short content has no informational value
        if len(content) < 8:
            return False

        # Purely polite/placeholder content
        lowered = content.lower()
        if lowered in self._LOW_VALUE_PHRASES:
            return False
        for phrase in self._LOW_VALUE_PHRASES:
            if phrase and lowered == phrase:
                return False

        return True

    # High-signal keywords: sentences containing these words are prioritized during rule-based compression
    _HIGH_SIGNAL_KEYWORDS = (
        "decision",
        "conclusion",
        "decision",
        "choice",
        "preference",
        "reason",
        "because",
        "so",
        "therefore",
        "user",
        "fix",
        "issue",
        "solution",
        "config",
        "version",
        "address",
        "path",
        "command",
        "bug",
        "bug",
        "error",
        "error",
        "note",
        "important",
        "must",
        "forbidden",
        "recommend",
        "success",
        "failure",
        "step",
        "process",
        "result",
        "goal",
        "implement",
        "added",
        "delete",
    )

    def _compress_memory_content(self, content: str) -> str:
        """Rule-based summary compression: extractive compression for over-length memory content.

        Strategy (preserve key information, control volume):
        1. Use token estimation to determine if compression threshold is exceeded; return as-is if not exceeded.
        2. When threshold is exceeded:
            - Keep the first few sentences (background/context)
            - Extract sentences containing high-signal keywords (decisions/conclusions/preferences/facts etc.)
            - Keep the last few sentences (conclusions/summary)
            - Deduplicate before joining to avoid repeated sentences.
        3. Character-level truncation as fallback when compressed result is still too long.

        Returns:
            str: Compressed content; returns original content if under threshold.
        """
        text = (content or "").strip()
        if not text:
            return text

        try:
            if get_context_token_count(text) <= get_memory_compress_threshold():
                return text
        except Exception:
            # Fall back to character length judgment when token estimation fails
            if len(text) <= get_memory_compress_threshold() * 2:
                return text

        # Split by sentences
        import re

        sentences = [
            s.strip()
            for s in re.split(r"[。！？!?\n]+\.?(?=\s|[A-Z])|\.(?=\s|[A-Z])", text)
            if s.strip()
        ]

        # Keep first 3 and last 3 sentences (shorter texts still keep their conclusion)
        if len(sentences) > 6:
            head = sentences[:3]
            tail = sentences[-3:]
            middle = sentences[3:-3]
        else:
            head = sentences[:2]
            tail = sentences[-1:] if len(sentences) > 2 else []
            middle = sentences[2:-1] if len(sentences) > 2 else []

        # Extract sentences containing high-signal keywords
        signal = []
        for s in middle:
            lowered = s.lower()
            if any(kw in lowered for kw in self._HIGH_SIGNAL_KEYWORDS):
                signal.append(s)

        # Deduplicate (preserve order)
        seen = set()
        merged = []
        for s in head + signal + tail:
            key = s[:20]
            if key not in seen:
                seen.add(key)
                merged.append(s)

        compressed = "；".join(merged)
        # Character-level fallback truncation to prevent extreme over-length
        max_chars = max(600, int(len(text) * 0.6))
        if len(compressed) > max_chars:
            compressed = compressed[:max_chars]
        return compressed

    def _save_single_memory(
        self, memory_data: Dict[str, Any], agent: Any = None
    ) -> Dict[str, Any]:
        """Save a single memory"""
        memory_type = memory_data["memory_type"]  # Scope: project/global/short_term
        nature = memory_data.get(
            "nature", "long_term"
        )  # Type: long_term/procedural/episodic
        tags = memory_data.get("tags", [])
        content = memory_data.get("content", "")

        # Write-time memory value filtering: discard when no explicit importance annotation and content has no value
        if is_enable_memory_value_filter() and not self._should_store_memory(
            memory_data
        ):
            return {
                "memory_id": None,
                "memory_type": memory_type,
                "nature": nature,
                "tags": tags,
                "storage": "filtered",
                "message": "Memory content has insufficient value, filtered and not saved",
            }

        # Pre-storage compression: rule-based summary for over-length content, original content preserved in original_content
        original_content = content
        if is_enable_memory_compress() and content:
            try:
                compressed = self._compress_memory_content(content)
                if compressed != content:
                    content = compressed
            except Exception:
                # Compression failure does not affect saving, keep original text
                content = original_content

        # Collect memory tags to agent's memory_tags attribute
        if agent and hasattr(agent, "add_memory_tags") and tags:
            try:
                agent.add_memory_tags(tags)
            except Exception:
                # Tag addition failure does not affect main memory saving functionality
                pass

        # Generate memory ID
        memory_id = self._generate_memory_id()

        # Create memory object
        memory_obj = {
            "id": memory_id,
            "memory_type": memory_type,
            "nature": nature,
            "tags": tags,
            "content": content,
            "importance": memory_data.get("importance", "medium"),
            "source": memory_data.get("source", ""),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        # Preserve original full content for compressed entries for future reference
        if content != original_content:
            memory_obj["original_content"] = original_content

        if memory_type == "short_term":
            # Short-term memory saved to global variable
            add_short_term_memory(memory_obj)

            # Add content to agent's recent_memories list
            if agent and hasattr(agent, "recent_memories"):
                # Filter empty content
                if content and content.strip():
                    agent.recent_memories.append(content.strip())
                    # Maintain max 10 entries limit
                    if len(agent.recent_memories) > agent.MAX_RECENT_MEMORIES:
                        agent.recent_memories.pop(0)

            result = {
                "memory_id": memory_id,
                "memory_type": memory_type,
                "nature": nature,
                "tags": tags,
                "storage": "memory",
                "message": f"Short-term memory saved to memory successfully, ID: {memory_id}",
            }
        else:
            # Long-term memory saved to file
            # Get storage directory and ensure it exists
            memory_dir = self._get_memory_dir(memory_type, nature)
            memory_dir.mkdir(parents=True, exist_ok=True)

            # Save memory file
            memory_file = memory_dir / f"{memory_id}.json"
            with open(memory_file, "w", encoding="utf-8") as f:
                json.dump(memory_obj, f, ensure_ascii=False, indent=2)

            # Add content to agent's recent_memories list
            if agent and hasattr(agent, "recent_memories"):
                # Filter empty content
                if content and content.strip():
                    agent.recent_memories.append(content.strip())
                    # Maintain max 10 entries limit
                    if len(agent.recent_memories) > agent.MAX_RECENT_MEMORIES:
                        agent.recent_memories.pop(0)

            result = {
                "memory_id": memory_id,
                "memory_type": memory_type,
                "nature": nature,
                "tags": tags,
                "file_path": str(memory_file),
                "message": f"Memory saved successfully, ID: {memory_id}",
            }

        return result

    def _execute_save(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory save operation"""
        try:
            # Get agent instance (injected via arguments in v1.0 protocol)
            agent = args.get("agent")
            memories = args.get("memories", [])

            if not memories:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "No memories provided to save",
                }

            results = []
            success_count = 0
            failed_count = 0

            # Save each memory
            for i, memory_data in enumerate(memories):
                try:
                    result = self._save_single_memory(memory_data, agent)
                    results.append(result)
                    success_count += 1

                    memory_data["memory_type"]
                    memory_data.get("tags", [])

                except Exception as e:
                    failed_count += 1
                    error_msg = f"Failed to save memory {i + 1}: {str(e)}"
                    PrettyOutput.auto_print(f"❌ {error_msg}")
                    results.append(
                        {
                            "error": error_msg,
                            "memory_type": memory_data.get("memory_type", "unknown"),
                            "tags": memory_data.get("tags", []),
                        }
                    )

            # Print summary info pinned to pin_content
            if (
                agent
                and hasattr(agent, "pin_content")
                and agent.pin_content
                and success_count > 0
            ):
                PrettyOutput.auto_print(f"📌 Pinned {success_count} memory entries")

            # Generate summary report
            output = {
                "total": len(memories),
                "success": success_count,
                "failed": failed_count,
                "results": results,
            }

            return {
                "success": True,
                "stdout": json.dumps(output, ensure_ascii=False, indent=2),
                "stderr": "",
            }

        except Exception as e:
            error_msg = f"Failed to save memory: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}

    # ========== Methods for retrieve operation ==========

    def _retrieve_from_type(
        self,
        memory_type: str,
        tags: Optional[List[str]] = None,
        natures: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve memories from specified scope (memory_type) and types (natures)"""
        memories: List[Dict[str, Any]] = []

        if memory_type == "short_term":
            # Get short-term memories from global variable
            memories = get_short_term_memories(tags)
        else:
            # Get memories from file system (read separately by type)
            nature_list = natures or ["long_term", "procedural", "episodic"]
            for nature in nature_list:
                memory_dir = self._get_memory_dir(memory_type, nature)
                if not memory_dir.exists():
                    continue

                # Iterate over memory files
                for memory_file in memory_dir.glob("*.json"):
                    try:
                        with open(memory_file, "r", encoding="utf-8") as f:
                            memory_data = json.load(f)

                        # If tags specified, check for match
                        if tags:
                            memory_tags = memory_data.get("tags", [])
                            if not any(tag in memory_tags for tag in tags):
                                continue

                        memories.append(memory_data)
                    except Exception as e:
                        PrettyOutput.auto_print(
                            f"⚠️ Failed to read memory file {memory_file}: {str(e)}"
                        )

        return memories

    def _execute_retrieve(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory retrieve operation"""
        try:
            memory_types = args.get("memory_types", [])  # Scope filter
            natures = args.get("natures", [])  # Type filter
            tags = args.get("tags", [])
            limit = args.get("limit", None)
            smart_search = args.get("smart_search", False)
            query = args.get("query", "")

            # If smart search mode is enabled
            if smart_search:
                return self._execute_smart_search(
                    args, memory_types, query, limit, natures
                )

            # Determine scopes to search
            if not memory_types or "all" in memory_types:
                types_to_search = ["project", "global", "short_term"]
            else:
                types_to_search = memory_types

            # Determine types to search
            if not natures or "all" in natures:
                natures_to_search = ["long_term", "procedural", "episodic"]
            else:
                natures_to_search = natures

            # Retrieve memories from each scope+type combination
            all_memories = []
            for memory_type in types_to_search:
                memories = self._retrieve_from_type(
                    memory_type, tags, natures_to_search
                )
                all_memories.extend(memories)

            # Sort by creation time (newest first)
            all_memories.sort(key=lambda x: x.get("created_at", ""), reverse=True)

            # Prefer using remaining token count, fall back to input window limit
            memory_token_limit = None
            agent = args.get("agent")
            if agent and hasattr(agent, "model"):
                try:
                    remaining_tokens = agent.model.get_remaining_token_count()
                    # Use the lesser of 2/3 of remaining tokens or 64k
                    memory_token_limit = calculate_token_limit(remaining_tokens)
                    if memory_token_limit <= 0:
                        memory_token_limit = None
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_tools.memory", function="_execute_retrieve"
                    )
                    pass

            # Fallback: use 2/3 of input window
            if memory_token_limit is None:
                max_input_tokens = get_max_input_token_count()
                memory_token_limit = int(max_input_tokens * 2 / 3)

            # Filter memories based on token limit and count limit
            filtered_memories: List[Dict[str, Any]] = []
            total_tokens = 0

            for memory in all_memories:
                # Calculate token count for current memory
                memory_content = json.dumps(memory, ensure_ascii=False)
                memory_tokens = get_context_token_count(memory_content)

                # Check if token limit is exceeded
                if total_tokens + memory_tokens > memory_token_limit:
                    break

                # Check if 50-item limit is exceeded
                if len(filtered_memories) >= 50:
                    break

                filtered_memories.append(memory)
                total_tokens += memory_tokens

            all_memories = filtered_memories

            # If additional limit specified, return only first N
            if limit and len(all_memories) > limit:
                all_memories = all_memories[:limit]

            # Format as Markdown output
            markdown_output = "# Memory Retrieval Results\n\n"
            markdown_output += f"**Retrieved {len(all_memories)} memories**\n\n"

            if tags:
                markdown_output += f"**Filtered by tags**: {', '.join(tags)}\n\n"

            markdown_output += f"**Scope**: {', '.join(types_to_search)}\n\n"

            markdown_output += "---\n\n"

            # Output all memories
            for i, memory in enumerate(all_memories):
                markdown_output += f"## {i + 1}. {memory.get('id', 'Unknown ID')}\n\n"
                markdown_output += (
                    f"**Scope**: {memory.get('memory_type', 'Unknown')}\n\n"
                )
                markdown_output += f"**Type**: {memory.get('nature', 'Unknown')}\n\n"
                markdown_output += f"**Tags**: {', '.join(memory.get('tags', []))}\n\n"
                markdown_output += (
                    f"**Created**: {memory.get('created_at', 'Unknown time')}\n\n"
                )

                # Content section
                content = memory.get("content", "")
                if content:
                    markdown_output += f"**Content**:\n\n{content}\n\n"

                # If there is additional metadata
                metadata = {
                    k: v
                    for k, v in memory.items()
                    if k
                    not in [
                        "id",
                        "memory_type",
                        "nature",
                        "tags",
                        "created_at",
                        "content",
                    ]
                }
                if metadata:
                    markdown_output += "**Other info**:\n"
                    for key, value in metadata.items():
                        markdown_output += f"- {key}: {value}\n"
                    markdown_output += "\n"

                markdown_output += "---\n\n"

            return {
                "success": True,
                "stdout": markdown_output,
                "stderr": "",
            }

        except Exception as e:
            error_msg = f"Failed to retrieve memories: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}

    def _execute_smart_search(
        self,
        args: Dict[str, Any],
        memory_types: List[str],
        query: str,
        limit: Optional[int],
        natures: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute smart semantic search"""
        try:
            if not query:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Smart search mode requires query parameter",
                }

            # Determine scopes to search (smart search does not support short_term)
            if not memory_types or "all" in memory_types:
                types_to_search = ["project", "global"]
            else:
                types_to_search = [
                    t for t in memory_types if t in ["project", "global"]
                ]

            if not types_to_search:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Smart search mode only supports project and global scopes",
                }

            # Determine types to search
            if not natures or "all" in natures:
                natures_to_search = ["long_term", "procedural", "episodic"]
            else:
                natures_to_search = natures

            # Use SmartRetriever for semantic search
            retriever = _get_smart_retriever()
            search_limit = limit if limit else 10
            memories = retriever.semantic_search(
                query=query,
                memory_types=types_to_search,
                natures=natures_to_search,
                limit=search_limit,
            )

            # Filter returned memories based on token budget to prevent a single over-length memory from consuming the entire context
            # (Consistent with the token limit logic in regular retrieval _execute_retrieve)
            memory_token_limit = None
            agent = args.get("agent")
            if agent and hasattr(agent, "model"):
                try:
                    remaining_tokens = agent.model.get_remaining_token_count()
                    memory_token_limit = calculate_token_limit(remaining_tokens)
                    if memory_token_limit <= 0:
                        memory_token_limit = None
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.memory",
                        function="_execute_smart_search",
                    )
                    pass

            # Fallback: use 2/3 of input window
            if memory_token_limit is None:
                max_input_tokens = get_max_input_token_count()
                memory_token_limit = int(max_input_tokens * 2 / 3)

            filtered_memories = []
            total_tokens = 0
            for memory in memories:
                memory_content = memory.content or ""
                memory_tokens = get_context_token_count(memory_content)
                if total_tokens + memory_tokens > memory_token_limit:
                    break
                if len(filtered_memories) >= 50:
                    break
                filtered_memories.append(memory)
                total_tokens += memory_tokens
            memories = filtered_memories

            # Format as Markdown output
            markdown_output = "# Smart Semantic Search Results\n\n"
            markdown_output += f"**Query**: {query}\n\n"
            markdown_output += f"**Retrieved {len(memories)} relevant memories**\n\n"
            markdown_output += f"**Scope**: {', '.join(types_to_search)}\n\n"
            markdown_output += f"**Types**: {', '.join(natures_to_search)}\n\n"
            markdown_output += "---\n\n"

            # Output all memories
            for i, memory in enumerate(memories):
                markdown_output += f"## {i + 1}. {memory.id}\n\n"
                markdown_output += (
                    f"**Type**: {memory.memory_type} / {memory.nature}\n\n"
                )
                markdown_output += f"**Tags**: {', '.join(memory.tags)}\n\n"
                markdown_output += f"**Created**: {memory.created_at}\n\n"

                # Content section
                if memory.content:
                    markdown_output += f"**Content**:\n\n{memory.content}\n\n"

                markdown_output += "---\n\n"

            return {
                "success": True,
                "stdout": markdown_output,
                "stderr": "",
            }

        except Exception as e:
            error_msg = f"Smart search failed: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}

    # ========== Methods for clear operation ==========

    def _clear_short_term_memories(
        self, tags: Optional[List[str]] = None, memory_ids: Optional[List[str]] = None
    ) -> Dict[str, int]:
        """Clear short-term memories"""
        global short_term_memories

        initial_count = len(short_term_memories)
        removed_count = 0

        if memory_ids:
            # Clear by ID
            new_memories = []
            for memory in short_term_memories:
                if memory.get("id") not in memory_ids:
                    new_memories.append(memory)
                else:
                    removed_count += 1
            short_term_memories[:] = new_memories
        elif tags:
            # Clear by tags
            new_memories = []
            for memory in short_term_memories:
                memory_tags = memory.get("tags", [])
                if not any(tag in memory_tags for tag in tags):
                    new_memories.append(memory)
                else:
                    removed_count += 1
            short_term_memories[:] = new_memories
        else:
            # Clear all
            clear_short_term_memories()
            removed_count = initial_count

        return {"total": initial_count, "removed": removed_count}

    def _clear_long_term_memories(
        self,
        memory_type: str,
        nature: str,
        tags: Optional[List[str]] = None,
        memory_ids: Optional[List[str]] = None,
    ) -> Dict[str, int]:
        """Clear long-term memories (specified scope + type)"""
        memory_dir = self._get_memory_dir(memory_type, nature)

        if not memory_dir.exists():
            return {"total": 0, "removed": 0}

        total_count = 0
        removed_count = 0

        # Get all memory files
        memory_files = list(memory_dir.glob("*.json"))
        total_count = len(memory_files)

        for memory_file in memory_files:
            try:
                # Read memory content
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)

                should_remove = False

                if memory_ids:
                    # Check by ID
                    if memory_data.get("id") in memory_ids:
                        should_remove = True
                elif tags:
                    # Check by tags
                    memory_tags = memory_data.get("tags", [])
                    if any(tag in memory_tags for tag in tags):
                        should_remove = True
                else:
                    # Clear all
                    should_remove = True

                if should_remove:
                    memory_file.unlink()
                    removed_count += 1

            except Exception as e:
                PrettyOutput.auto_print(
                    f"⚠️ Error processing memory file {memory_file}: {str(e)}"
                )

                # If directory is empty, remove it
                if not any(memory_dir.iterdir()) and memory_dir != self.project_memory_dir:
                    memory_dir.rmdir()

        return {"total": total_count, "removed": removed_count}

    def _execute_clear(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory clear operation"""
        try:
            memory_types = args.get("memory_types", [])  # Scope
            natures = args.get("natures", [])  # Type
            tags = args.get("tags", [])
            memory_ids = args.get("memory_ids", [])
            confirm = args.get("confirm", False)

            if not confirm:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Must set confirm=true to execute clear operation",
                }

            # Determine scopes to clear
            if not memory_types or "all" in memory_types:
                types_to_clear = ["project", "global", "short_term"]
            else:
                types_to_clear = memory_types

            # Determine types to clear
            if not natures or "all" in natures:
                natures_to_clear = ["long_term", "procedural", "episodic"]
            else:
                natures_to_clear = natures

            # Compile results
            results = {}
            total_removed = 0

            # Clear memories for each scope+type
            for memory_type in types_to_clear:
                if memory_type == "short_term":
                    result = self._clear_short_term_memories(tags, memory_ids)
                    results[memory_type] = result
                    total_removed += result["removed"]
                else:
                    for nature in natures_to_clear:
                        result = self._clear_long_term_memories(
                            memory_type, nature, tags, memory_ids
                        )
                        key = f"{memory_type}/{nature}"
                        results[key] = result
                        total_removed += result["removed"]

            # Generate result report
            report = "# Memory Clear Report\n\n"
            report += f"**Total cleared**: {total_removed} memories\n\n"

            if tags:
                report += f"**Filtered by tags**: {', '.join(tags)}\n\n"

            if memory_ids:
                report += f"**Specified memory IDs**: {', '.join(memory_ids)}\n\n"

            report += "## Detailed Results\n\n"

            for memory_type, result in results.items():
                report += f"### {memory_type}\n"
                report += f"- Original memories: {result['total']}\n"
                report += f"- Cleared: {result['removed']}\n"
                report += f"- Remaining: {result['total'] - result['removed']}\n\n"

            return {
                "success": True,
                "stdout": report,
                "stderr": "",
            }

        except Exception as e:
            error_msg = f"Failed to clear memories: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}

    # ========== Main entry method ==========

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute memory operation"""
        try:
            action = args.get("action", "")

            if not action:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Must specify operation type (save/retrieve/clear)",
                }

            # Route to appropriate method based on operation type
            if action == "save":
                return self._execute_save(args)
            elif action == "retrieve":
                return self._execute_retrieve(args)
            elif action == "clear":
                return self._execute_clear(args)
            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Unknown operation type: {action}, supported types: save/retrieve/clear",
                }

        except Exception as e:
            error_msg = f"Failed to execute memory operation: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}
