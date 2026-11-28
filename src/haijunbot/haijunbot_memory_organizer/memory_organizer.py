"""
Memory organizer tool - merges memories with similar tags

This tool finds memories whose tags overlap heavily and uses a large model to merge them into a new memory.
"""

import json
from collections import defaultdict
from pathlib import Path

from haijunbot.haijunbot_utils.output import PrettyOutput

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

import typer

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.config import (
    get_data_dir,
    set_llm_group,
    get_max_input_token_count,
)
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.utils import init_env


class MemoryOrganizer:
    """Memory organizer, used to merge memories with similar tags"""

    def __init__(self):
        """Initialize the memory organizer"""
        self.project_memory_dir = Path(".haijunbot/memory")
        self.global_memory_dir = Path(get_data_dir()) / "memory"

        # Get the currently configured platform instance
        registry = PlatformRegistry.get_global_platform_registry()
        self.platform = registry.get_normal_platform()

    def _resolve_memory_dir(self, memory_type: str) -> Path:
        """Resolve a memory type name to its storage directory (supports flat names and two-field names)

        Supported:
        - Flat names: project_long_term / global_long_term / project_procedural ...
        - Two-field names: project/long_term / global/procedural ...
        - Scope only: project / global (defaults to long_term)
        """
        if "/" in memory_type:
            scope, nature = memory_type.split("/", 1)
        elif "_" in memory_type:
            scope, nature = memory_type.split("_", 1)
        else:
            scope, nature = memory_type, "long_term"

        if scope == "project":
            if nature == "long_term":
                return self.project_memory_dir
            return self.project_memory_dir / nature
        elif scope == "global":
            if nature == "long_term":
                return self.global_memory_dir / "global_long_term"
            return self.global_memory_dir / nature
        raise ValueError(f"Unsupported memory type: {memory_type}")

    def _get_memory_files(self, memory_type: str) -> List[Path]:
        """Get all memory files of the specified type"""
        memory_dir = self._resolve_memory_dir(memory_type)

        if not memory_dir.exists():
            return []

        return list(memory_dir.glob("*.json"))

    def _load_memories(self, memory_type: str) -> List[Dict[str, Any]]:
        """Load all memories of the specified type"""
        memories = []
        memory_files = self._get_memory_files(memory_type)
        error_lines: List[str] = []

        for memory_file in memory_files:
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)
                    memory_data["file_path"] = str(memory_file)
                    memories.append(memory_data)
            except Exception as e:
                error_lines.append(f"Failed to read memory file {memory_file}: {str(e)}")

        if error_lines:
            joined_errors = "\n".join(error_lines)
            PrettyOutput.auto_print(f"⚠️ {joined_errors}")

        return memories

    def _find_overlapping_memories(
        self, memories: List[Dict[str, Any]], min_overlap: int
    ) -> Dict[int, List[Set[int]]]:
        """
        Find memory groups with overlapping tags

        Returns: {overlap_count: [list of memory index sets]}

        Performance note: the original implementation used O(n²) pairwise comparisons plus
        O(n³) group expansion, which is very slow when there are many memories (e.g. thousands).
        1. A tag index is used to generate only candidate memory pairs that share ">= min_overlap tags",
           avoiding the full O(n²) pairwise comparison (candidate pairs are usually far fewer);
        2. Group expansion only looks at candidate neighbors instead of scanning all memories.
        Semantics stay the same: any two memories in a group share >= min_overlap tags.
        """
        # Precompute the tag set of each memory
        tags_of = [set(memory.get("tags", [])) for memory in memories]

        # Build the mapping from tags to memory indices
        tag_to_memories = defaultdict(set)
        for i, tags in enumerate(tags_of):
            for tag in tags:
                tag_to_memories[tag].add(i)

        # Generate candidate edges: memory pairs sharing >= min_overlap tags (i < j)
        candidate_edges = set()
        visited_pairs = set()
        for memset in tag_to_memories.values():
            lst = sorted(memset)
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    i, j = lst[a], lst[b]
                    key = (i, j) if i < j else (j, i)
                    if key in visited_pairs:
                        continue
                    visited_pairs.add(key)
                    if len(tags_of[i] & tags_of[j]) >= min_overlap:
                        candidate_edges.add(key)

        # Candidate neighbor table: other memories sharing >= min_overlap tags with a memory
        candidate_adj = defaultdict(set)
        for i, j in candidate_edges:
            candidate_adj[i].add(j)
            candidate_adj[j].add(i)

        # Find memory groups with common tags (clique semantics: pairwise overlap within group >= min_overlap)
        overlap_groups = defaultdict(list)
        processed_groups = set()

        for i, j in sorted(candidate_edges):
            group = {i, j}

            # Expand the group with all memories that overlap enough with the group
            changed = True
            while changed:
                changed = False
                # Only look for joinable memories among candidate neighbors (far fewer than all memories)
                candidates = set()
                for m in group:
                    candidates |= candidate_adj[m]
                for k in candidates:
                    if k not in group:
                        # Check the minimum overlap with all memories in the group
                        min_overlap_with_group = min(
                            len(tags_of[k] & tags_of[m]) for m in group
                        )
                        if min_overlap_with_group >= min_overlap:
                            group.add(k)
                            changed = True

            # Convert the group to a sorted tuple for deduplication
            group_tuple = tuple(sorted(group))
            if group_tuple not in processed_groups:
                processed_groups.add(group_tuple)
                overlap_groups[min_overlap].append(set(group_tuple))

        return overlap_groups

    def _merge_memories_with_llm(
        self, memories: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Merge multiple memories using the large model"""
        # Prepare the merge prompt
        memory_contents = []
        all_tags = set()

        # Sort by creation time, newest first
        sorted_memories = sorted(
            memories, key=lambda m: m.get("created_at", ""), reverse=True
        )

        for memory in sorted_memories:
            memory_contents.append(
                f"Memory ID: {memory.get('id', 'unknown')}\n"
                f"Creation time: {memory.get('created_at', 'unknown')}\n"
                f"Tags: {', '.join(memory.get('tags', []))}\n"
                f"Content:\n{memory.get('content', '')}"
            )
            all_tags.update(memory.get("tags", []))

        memory_contents_str = (("=" * 50) + "\n").join(memory_contents)

        prompt = f"""Please merge the following {len(memories)} related memories into one comprehensive memory.

Original memories (sorted from newest to oldest):
{"=" * 50}
{memory_contents_str}
{"=" * 50}

Original tag set: {", ".join(sorted(all_tags))}

Please complete the following tasks:
1. Analyze the common themes and key information of these memories
2. Merge them into one coherent, complete memory
3. Generate a new tag list (keep important tags, remove redundant ones, and you may add new summarizing tags)
4. Make sure the merged memory preserves all important information
5. **Important**: more recent memories carry more weight; prioritize the information from the newest memories

Put the merged result inside the <merged_memory> tag, using JSON format:

<merged_memory>
{{
  "content": "The content of the merged memory, may be multi-line text",
  "tags": ["tag1", "tag2", "tag3"]
}}
</merged_memory>

Notes:
- The content should be comprehensive but concise
- The tags should accurately reflect the content's theme
- Keep a professional and objective tone
- More recent memory information has higher priority
- Only output the content inside the <merged_memory> tag, without any other explanations
- The JSON format must be valid; use \\n for newlines inside strings
"""

        try:
            if self.platform is None:
                raise ValueError("Platform is not initialized")

            # Call the large model - collect the full response
            response_parts = []
            for chunk_type, chunk_content in self.platform.chat(prompt):
                # Only collect content-type chunks
                if chunk_type == "content":
                    response_parts.append(chunk_content)
            response = "".join(response_parts)

            # Parse the response
            import re

            from haijunbot.haijunbot_utils.jsonnet_compat import loads as json5_loads

            # Extract the content inside the <merged_memory> tag
            json_match = re.search(
                r"<merged_memory>(.*?)</merged_memory>",
                response,
                re.DOTALL | re.IGNORECASE,
            )

            if json_match:
                json_content = json_match.group(1).strip()
                try:
                    result = json5_loads(json_content)
                    return {
                        "content": result.get("content", ""),
                        "tags": result.get("tags", []),
                        "type": memories[0].get("type", "unknown"),
                        "merged_from": [m.get("id", "") for m in memories],
                    }
                except (ValueError, Exception) as e:
                    raise ValueError(f"Unable to parse JSON content: {str(e)}")
            else:
                raise ValueError("Unable to extract the <merged_memory> tag content from the model response")

        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to merge memories via the large model: {str(e)}")
            # Returning None means the merge failed; skip this memory group
            return None

    def _merge_memories_batch_with_llm(
        self, groups: List[List[Dict[str, Any]]]
    ) -> List[Optional[Dict[str, Any]]]:
        """Merge multiple memory groups in a batch using the large model.

        Multiple independent small groups are packed into a single LLM call; the model outputs one
        <merged_memory> block per group, greatly reducing the number of calls for small-group merging
        (saving the per-call fixed overhead). Returns a list of merge results aligned with the input
        groups; a failed group has None in its position.
        """
        # Prepare each group's input content
        group_inputs = []
        for idx, memories in enumerate(groups, start=1):
            sorted_memories = sorted(
                memories, key=lambda m: m.get("created_at", ""), reverse=True
            )
            parts = []
            all_tags = set()
            for mem in sorted_memories:
                parts.append(
                    f"Memory ID: {mem.get('id', 'unknown')}\n"
                    f"Creation time: {mem.get('created_at', 'unknown')}\n"
                    f"Tags: {', '.join(mem.get('tags', []))}\n"
                    f"Content:\n{mem.get('content', '')}"
                )
                all_tags.update(mem.get("tags", []))
            group_inputs.append(
                {
                    "idx": idx,
                    "contents": (("=" * 50) + "\n").join(parts),
                    "tags": ", ".join(sorted(all_tags)),
                    "count": len(memories),
                }
            )

        # Build the batch prompt
        prompt_lines = [
            f"Please merge the following {len(groups)} groups of related memories separately, each group independently into one comprehensive memory.",
            "",
        ]
        for gi in group_inputs:
            prompt_lines.append(f"[Group {gi['idx']}] ({gi['count']} memories in total)")
            prompt_lines.append("Original memories (sorted from newest to oldest):")
            prompt_lines.append("=" * 50)
            prompt_lines.append(gi["contents"])
            prompt_lines.append("=" * 50)
            prompt_lines.append(f"Original tag set: {gi['tags']}")
            prompt_lines.append("")
        prompt_lines.extend(
            [
                "Complete the following tasks separately for each group:",
                "1. Analyze the common themes and key information of that group's memories",
                "2. Merge them into one coherent, complete memory",
                "3. Generate a new tag list (keep important tags, remove redundant ones, and you may add new summarizing tags)",
                "4. Make sure the merged memory preserves all important information",
                "5. **Important**: more recent memories carry more weight; prioritize the information from the newest memories",
                "",
                "Put each group's result inside the corresponding <merged_memory> tag, using JSON format, and distinguish them with the group number:",
                "",
                "<merged_memory>",
                "{",
                '  "group": 1,',
                '  "content": "The content of group 1 merged memory, may be multi-line text",',
                '  "tags": ["tag1", "tag2", "tag3"]',
                "}",
                "</merged_memory>",
                "",
                "<merged_memory>",
                "{",
                '  "group": 2,',
                '  "content": "The content of group 2 merged memory",',
                '  "tags": ["tag1", "tag2"]',
                "}",
                "</merged_memory>",
                "",
                "Notes:",
                "- Each group's content should be comprehensive but concise",
                "- The tags should accurately reflect the content's theme",
                "- Keep a professional and objective tone",
                "- More recent memory information has higher priority",
                "- You must output one <merged_memory> block per group, with the group field matching the group number",
                "- Only output the content inside the <merged_memory> tags, without any other explanations",
                "- The JSON format must be valid; use \\n for newlines inside strings",
            ]
        )
        prompt = "\n".join(prompt_lines)

        results: List[Optional[Dict[str, Any]]] = [None] * len(groups)
        try:
            if self.platform is None:
                raise ValueError("Platform is not initialized")

            # Call the large model - collect the full response
            response_parts = []
            for chunk_type, chunk_content in self.platform.chat(prompt):
                if chunk_type == "content":
                    response_parts.append(chunk_content)
            response = "".join(response_parts)

            # Parse the response: extract all <merged_memory> blocks
            import re

            from haijunbot.haijunbot_utils.jsonnet_compat import loads as json5_loads

            blocks = re.findall(
                r"<merged_memory>(.*?)</merged_memory>",
                response,
                re.DOTALL | re.IGNORECASE,
            )
            for block in blocks:
                try:
                    result = json5_loads(block.strip())
                    group_idx = result.get("group")
                    if group_idx is None:
                        continue
                    # The group number is 1-based; convert to a 0-based index
                    pos = int(group_idx) - 1
                    if 0 <= pos < len(groups):
                        results[pos] = {
                            "content": result.get("content", ""),
                            "tags": result.get("tags", []),
                            "type": groups[pos][0].get("type", "unknown"),
                            "merged_from": [m.get("id", "") for m in groups[pos]],
                        }
                except (ValueError, Exception):
                    continue
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to batch-merge memories via the large model: {str(e)}")

        return results

    def organize_memories(
        self,
        memory_type: str,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Organize the memories of the specified type

        Args:
            memory_type: The memory type
            dry_run: Whether to run only a simulation

        Returns:
            Organizing result statistics
        """
        PrettyOutput.auto_print(f"ℹ️ Starting to organize {memory_type} memories, minimum overlapping tags: 2")

        # Load the memories
        memories = self._load_memories(memory_type)
        if not memories:
            PrettyOutput.auto_print("ℹ️ No memories found to organize")
            return {"processed": 0, "merged": 0}

        PrettyOutput.auto_print(f"ℹ️ Loaded {len(memories)} memories")

        # Statistics
        stats = {
            "total_memories": len(memories),
            "processed_groups": 0,
            "merged_memories": 0,
            "created_memories": 0,
        }

        # Use the fixed minimum overlap count of 2
        # Create a set to mark deleted memories
        deleted_indices = set()

        # Filter out deleted memories
        active_memories = [
            (i, mem) for i, mem in enumerate(memories) if i not in deleted_indices
        ]
        if active_memories:
            # Create an index mapping: original index -> active index
            active_memory_list = [mem for _, mem in active_memories]

            overlap_groups = self._find_overlapping_memories(active_memory_list, 2)

            if 2 in overlap_groups:
                groups = overlap_groups[2]
                PrettyOutput.auto_print(
                    f"ℹ️ Found {len(groups)} memory groups with 2 overlapping tags"
                )

                # Batch merge params: small groups (<= 4 items) are packed into batch calls, large groups are called individually
                # Max small groups per batch (to prevent overly long single-batch output)
                BATCH_MAX_GROUPS = 5
                BATCH_MAX_GROUP_SIZE = 4

                # Dynamic batching based on token budget: reserve 20% for output, avoid exceeding the model input limit
                try:
                    max_input_tokens = get_max_input_token_count()
                except Exception:
                    max_input_tokens = 0
                batch_token_budget = (
                    int(max_input_tokens * 0.8) if max_input_tokens > 0 else 0
                )

                # Preprocess all groups: greedy dedup in original order (skip groups containing deleted memories), and convert indices
                pending_groups = []  # (original_indices, group_memories)
                pre_deleted = set()
                for group in groups:
                    original_indices = set()
                    for active_idx in group:
                        original_idx = active_memories[active_idx][0]
                        original_indices.add(original_idx)
                    # Greedy dedup: if any memory in the group is already deleted, skip it
                    if pre_deleted & original_indices:
                        continue
                    group_memories = [memories[i] for i in original_indices]
                    pending_groups.append((original_indices, group_memories))
                    pre_deleted.update(original_indices)

                # Split: small groups go into batches, large groups are handled individually
                small_groups = [
                    pg for pg in pending_groups if len(pg[1]) <= BATCH_MAX_GROUP_SIZE
                ]
                large_groups = [
                    pg for pg in pending_groups if len(pg[1]) > BATCH_MAX_GROUP_SIZE
                ]

                # Batch-merge small groups: dynamically batch by token budget (also constrained by the max groups per batch)
                batches = []
                current_batch = []
                current_tokens = 0
                for pg in small_groups:
                    # Estimate the input tokens for this group
                    group_text = "\n".join(
                        f"Memory ID: {m.get('id', '')}\nTags: {','.join(m.get('tags', []))}\nContent:{m.get('content', '')}"
                        for m in pg[1]
                    )
                    group_tokens = get_context_token_count(group_text)
                    # Start a new batch when reaching the max groups or the token budget
                    if current_batch and (
                        len(current_batch) >= BATCH_MAX_GROUPS
                        or (
                            batch_token_budget > 0
                            and current_tokens + group_tokens > batch_token_budget
                        )
                    ):
                        batches.append(current_batch)
                        current_batch = []
                        current_tokens = 0
                    current_batch.append(pg)
                    current_tokens += group_tokens
                if current_batch:
                    batches.append(current_batch)

                for batch in batches:
                    batch_memories = [pg[1] for pg in batch]

                    # Show the memories about to be merged
                    for original_indices, group_memories in batch:
                        lines = ["", f"About to merge {len(group_memories)} memories:"]
                        for mem in group_memories:
                            lines.append(
                                f"  - ID: {mem.get('id', 'unknown')}, "
                                f"tags: {', '.join(mem.get('tags', []))[:50]}..."
                            )
                        PrettyOutput.auto_print(f"ℹ️ {'\n'.join(lines)}")

                    if not dry_run:
                        merged_results = self._merge_memories_batch_with_llm(
                            batch_memories
                        )
                        for (original_indices, group_memories), merged_memory in zip(
                            batch, merged_results
                        ):
                            if merged_memory is None:
                                PrettyOutput.auto_print("  ⚠️ Skipping the merge of this memory group")
                                continue
                            self._save_merged_memory(
                                merged_memory,
                                memory_type,
                                [memories[i] for i in original_indices],
                            )
                            stats["processed_groups"] += 1
                            stats["merged_memories"] += len(original_indices)
                            stats["created_memories"] += 1
                            deleted_indices.update(original_indices)
                    else:
                        PrettyOutput.auto_print("  ℹ️ [dry run] Skipping the actual merge")

                # Merge large groups individually
                for original_indices, group_memories in large_groups:
                    lines = ["", f"About to merge {len(group_memories)} memories:"]
                    for mem in group_memories:
                        lines.append(
                            f"  - ID: {mem.get('id', 'unknown')}, "
                            f"tags: {', '.join(mem.get('tags', []))[:50]}..."
                        )
                    PrettyOutput.auto_print(f"ℹ️ {'\n'.join(lines)}")

                    if not dry_run:
                        merged_memory = self._merge_memories_with_llm(group_memories)
                        if merged_memory is None:
                            PrettyOutput.auto_print("  ⚠️ Skipping the merge of this memory group")
                            continue
                        self._save_merged_memory(
                            merged_memory,
                            memory_type,
                            [memories[i] for i in original_indices],
                        )
                        stats["processed_groups"] += 1
                        stats["merged_memories"] += len(original_indices)
                        stats["created_memories"] += 1
                        deleted_indices.update(original_indices)
                    else:
                        PrettyOutput.auto_print("  ℹ️ [dry run] Skipping the actual merge")

        # Show the statistics
        PrettyOutput.auto_print("✅ Organizing complete!")
        PrettyOutput.auto_print(f"ℹ️ Total memories: {stats['total_memories']}")
        PrettyOutput.auto_print(f"ℹ️ Processed groups: {stats['processed_groups']}")
        PrettyOutput.auto_print(f"ℹ️ Merged memories: {stats['merged_memories']}")
        PrettyOutput.auto_print(f"ℹ️ New memories created: {stats['created_memories']}")

        return stats

    def _save_merged_memory(
        self,
        memory: Dict[str, Any],
        memory_type: str,
        original_memories: List[Dict[str, Any]],
    ):
        """Save the merged memory and delete the original memories"""
        import uuid
        from datetime import datetime

        # Generate a new memory ID
        memory["id"] = f"merged_{uuid.uuid4().hex[:8]}"
        memory["created_at"] = datetime.now().isoformat()
        memory["updated_at"] = datetime.now().isoformat()
        # Record the scope and nature (compatible with flat-name resolution)
        if "/" in memory_type:
            scope, nature = memory_type.split("/", 1)
        elif "_" in memory_type:
            scope, nature = memory_type.split("_", 1)
        else:
            scope, nature = memory_type, "long_term"
        memory["memory_type"] = scope
        memory["nature"] = nature

        # Determine the save path
        memory_dir = self._resolve_memory_dir(memory_type)

        memory_dir.mkdir(parents=True, exist_ok=True)

        # Save the new memory
        new_file = memory_dir / f"{memory['id']}.json"
        with open(new_file, "w", encoding="utf-8") as f:
            json.dump(memory, f, ensure_ascii=False, indent=2)

        PrettyOutput.auto_print(
            f"✅ Created a new memory: {memory['id']} (tags: {', '.join(memory['tags'][:3])}...)"
        )

        # Delete the original memory files (collect the logs first, print them together at the end)
        info_lines: List[str] = []
        warn_lines: List[str] = []
        for orig_memory in original_memories:
            if "file_path" in orig_memory:
                try:
                    file_path = Path(orig_memory["file_path"])
                    if file_path.exists():
                        file_path.unlink()
                        info_lines.append(
                            f"Deleted original memory: {orig_memory.get('id', 'unknown')}"
                        )
                    else:
                        info_lines.append(
                            f"Original memory file no longer exists, skipping deletion: {orig_memory.get('id', 'unknown')}"
                        )
                except Exception as e:
                    warn_lines.append(
                        f"Failed to delete memory file {orig_memory.get('file_path', '')}: {str(e)}"
                    )
        if info_lines:
            joined_info = "\n".join(info_lines)
            PrettyOutput.auto_print(f"ℹ️ {joined_info}")
        if warn_lines:
            joined_warn = "\n".join(warn_lines)
            PrettyOutput.auto_print(f"⚠️ {joined_warn}")

    def export_memories(
        self,
        memory_types: List[str],
        output_file: Path,
        tags: Optional[List[str]] = None,
    ) -> int:
        """
        Export the memories of the specified types to a file

        Args:
            memory_types: The list of memory types to export
            output_file: The output file path
            tags: The optional tag filter

        Returns:
            The number of exported memories
        """
        all_memories = []
        progress_lines: List[str] = []

        for memory_type in memory_types:
            progress_lines.append(f"Exporting {memory_type} memories...")
            memories = self._load_memories(memory_type)

            # If tags are specified, filter by them
            if tags:
                filtered_memories = []
                for memory in memories:
                    memory_tags = set(memory.get("tags", []))
                    if any(tag in memory_tags for tag in tags):
                        filtered_memories.append(memory)
                memories = filtered_memories

            # Add the memory type info and remove the file path
            for memory in memories:
                if "/" in memory_type:
                    scope, nature = memory_type.split("/", 1)
                elif "_" in memory_type:
                    scope, nature = memory_type.split("_", 1)
                else:
                    scope, nature = memory_type, "long_term"
                memory["memory_type"] = scope
                memory["nature"] = nature
                memory.pop("file_path", None)

            all_memories.extend(memories)
            progress_lines.append(f"Exported {len(memories)} memories from {memory_type}")

        # Show the export progress logs together
        if progress_lines:
            joined_progress = "\n".join(progress_lines)
            PrettyOutput.auto_print(f"ℹ️ {joined_progress}")

        # Save to file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_memories, f, ensure_ascii=False, indent=2)

        PrettyOutput.auto_print(
            f"✅ Successfully exported {len(all_memories)} memories to {output_file}"
        )

        return len(all_memories)

    def import_memories(
        self,
        input_file: Path,
        overwrite: bool = False,
    ) -> Dict[str, int]:
        """
        Import memories from a file

        Args:
            input_file: The input file path
            overwrite: Whether to overwrite existing memories

        Returns:
            Import statistics {memory_type: count}
        """
        # Read the memory file
        if not input_file.exists():
            raise FileNotFoundError(f"Import file does not exist: {input_file}")

        with open(input_file, "r", encoding="utf-8") as f:
            memories = json.load(f)

        if not isinstance(memories, list):
            raise ValueError("Invalid import file format; expected a list of memories")

        PrettyOutput.auto_print(f"ℹ️ About to import {len(memories)} memories")

        # Statistics for the import result
        import_stats: Dict[str, int] = defaultdict(int)
        skipped_count = 0

        for memory in memories:
            memory_type = memory.get("memory_type", memory.get("type"))
            if not memory_type:
                skipped_count += 1
                continue

            # Assemble the type name used for directory resolution (prefer scope/nature combination)
            nature = memory.get("nature")
            resolve_type = f"{memory_type}/{nature}" if nature else memory_type

            # Determine the save path
            try:
                memory_dir = self._resolve_memory_dir(resolve_type)
            except ValueError:
                PrettyOutput.auto_print(f"⚠️ Skipping unsupported memory type: {memory_type}")
                skipped_count += 1
                continue

            memory_dir.mkdir(parents=True, exist_ok=True)

            # Check whether it already exists
            memory_id = memory.get("id")
            if not memory_id:
                import uuid

                memory_id = f"imported_{uuid.uuid4().hex[:8]}"
                memory["id"] = memory_id

            memory_file = memory_dir / f"{memory_id}.json"

            if memory_file.exists() and not overwrite:
                PrettyOutput.auto_print(f"ℹ️ Skipping already-existing memory: {memory_id}")
                skipped_count += 1
                continue

            # Save the memory
            with open(memory_file, "w", encoding="utf-8") as f:
                # Clean up the memory data
                if "/" in resolve_type:
                    scope, nature = resolve_type.split("/", 1)
                elif "_" in resolve_type:
                    scope, nature = resolve_type.split("_", 1)
                else:
                    scope, nature = resolve_type, "long_term"
                clean_memory = {
                    "id": memory["id"],
                    "memory_type": scope,
                    "nature": nature,
                    "tags": memory.get("tags", []),
                    "content": memory.get("content", ""),
                    "created_at": memory.get("created_at", ""),
                }
                if "merged_from" in memory:
                    clean_memory["merged_from"] = memory["merged_from"]

                json.dump(clean_memory, f, ensure_ascii=False, indent=2)

            import_stats[memory_type] += 1

        # Show the import result
        PrettyOutput.auto_print("✅ Import complete!")
        if import_stats:
            lines = [
                f"{memory_type}: imported {count} memories"
                for memory_type, count in import_stats.items()
            ]
            joined_lines = "\n".join(lines)
            PrettyOutput.auto_print(f"ℹ️ {joined_lines}")

        if skipped_count > 0:
            PrettyOutput.auto_print(f"⚠️ Skipped {skipped_count} memories")

        return dict(import_stats)


app = typer.Typer(help="Memory organizer tool - merges memories with similar tags")


@app.command("organize")
def organize(
    memory_type: str = typer.Option(
        "project_long_term",
        "--type",
        help="The memory type to organize (project_long_term or global_long_term)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Dry run: only show the operations that would be performed without actually executing them",
    ),
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="The model group to use, overriding the config file settings"
    ),
):
    """
    Organize and merge memories with similar tags.

    Examples:

    # Organize the project long-term memories
    haijunbot-memory-organizer organize --type project_long_term

    # Organize the global long-term memories as a dry run
    haijunbot-memory-organizer organize --type global_long_term --dry-run

    # Organize the project memories with default settings
    haijunbot-memory-organizer organize
    """
    # Validate the arguments
    set_llm_group(llm_group)
    try:
        organizer = MemoryOrganizer()
        organizer._resolve_memory_dir(memory_type)
    except ValueError:
        PrettyOutput.auto_print(
            f"❌ Error: unsupported memory type '{memory_type}'; "
            "supported types include project_long_term / global_long_term / project/long_term"
        )
        raise typer.Exit(1)

    # Create the organizer and run it
    try:
        organizer = MemoryOrganizer()
        stats = organizer.organize_memories(memory_type=memory_type, dry_run=dry_run)

        # Return the appropriate exit code based on the result
        if stats.get("processed_groups", 0) > 0 or dry_run:
            raise typer.Exit(0)
        else:
            raise typer.Exit(0)  # Normal exit even when nothing was processed

    except typer.Exit:
        # typer.Exit is the normal way to exit; propagate it
        raise
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Memory organizing failed: {str(e)}")
        raise typer.Exit(1)


@app.command("export")
def export(
    output: Path = typer.Argument(
        ...,
        help="Export file path (JSON format)",
    ),
    memory_types: List[str] = typer.Option(
        ["project_long_term", "global_long_term"],
        "--type",
        "-t",
        help="The memory types to export (can be specified multiple times)",
    ),
    tags: Optional[List[str]] = typer.Option(
        None,
        "--tag",
        help="Filter by tags (can be specified multiple times)",
    ),
):
    """
    Export memories to a file.

    Examples:

    # Export all memories to a file
    haijunbot-memory-organizer export memories.json

    # Export only the project long-term memories
    haijunbot-memory-organizer export project_memories.json -t project_long_term

    # Export memories with specific tags
    haijunbot-memory-organizer export tagged_memories.json --tag Python --tag API
    """
    try:
        organizer = MemoryOrganizer()

        # Validate the memory types (collect invalid types first, print them once)
        invalid_types = []
        for mt in memory_types:
            try:
                organizer._resolve_memory_dir(mt)
            except ValueError:
                invalid_types.append(mt)
        if invalid_types:
            invalid_str = ", ".join(f"'{mt}'" for mt in invalid_types)
            PrettyOutput.auto_print(f"❌ Error: unsupported memory types: {invalid_str}")
            raise typer.Exit(1)

        count = organizer.export_memories(
            memory_types=memory_types,
            output_file=output,
            tags=tags,
        )

        if count > 0:
            raise typer.Exit(0)
        else:
            PrettyOutput.auto_print("⚠️ No memories found to export")
            raise typer.Exit(0)

    except Exception as e:
        PrettyOutput.auto_print(f"❌ Export failed: {str(e)}")
        raise typer.Exit(1)


@app.command("import")
def import_memories(
    input: Path = typer.Argument(
        ...,
        help="Import file path (JSON format)",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-o",
        help="Overwrite existing memories",
    ),
):
    """
    Import memories from a file.

    Examples:

    # Import a memory file
    haijunbot-memory-organizer import memories.json

    # Import and overwrite existing memories
    haijunbot-memory-organizer import memories.json --overwrite
    """
    try:
        organizer = MemoryOrganizer()

        stats = organizer.import_memories(
            input_file=input,
            overwrite=overwrite,
        )

        total_imported = sum(stats.values())
        if total_imported > 0:
            raise typer.Exit(0)
        else:
            PrettyOutput.auto_print("⚠️ No memories were imported")
            raise typer.Exit(0)

    except FileNotFoundError as e:
        PrettyOutput.auto_print(f"❌ {str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Import failed: {str(e)}")
        raise typer.Exit(1)


def main():
    """Application entry point"""
    # Initialize the environment
    init_env()
    app()


if __name__ == "__main__":
    main()
