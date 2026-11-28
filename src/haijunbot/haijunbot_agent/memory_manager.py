# -*- coding: utf-8 -*-
"""
Memory manager module
Responsible for handling the Agent's memory saving and retrieval functionality
"""

from typing import Any
from typing import Optional

from haijunbot.haijunbot_agent.events import BEFORE_HISTORY_CLEAR
from haijunbot.haijunbot_agent.events import TASK_COMPLETED
from haijunbot.haijunbot_agent.events import TASK_STARTED
from haijunbot.haijunbot_utils.globals import get_all_memory_tags
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.exception_utils import save_exception


class MemoryManager:
    """Memory manager, responsible for handling memory-related functionality"""

    def __init__(self, agent: Any) -> None:
        """
        Initialize the memory manager

        Args:
            agent: Agent instance
        """
        self.agent = agent
        # Flag for whether a memory save prompt/handling has already occurred in this task round, used for event deduplication
        self._memory_prompted = False
        # Subscribe to Agent events (side-channel integration; failure does not affect the main flow)
        try:
            self._subscribe_events()
        except Exception as e:
            save_exception(e, module="haijunbot_agent.memory_manager", function="__init__")
            pass

    def prepare_memory_tags_prompt(self) -> str:
        """Prepare the memory tags prompt"""
        memory_tags = get_all_memory_tags()
        memory_tags_prompt = ""

        # Check whether the memory tool is available
        if self._has_memory_tool():
            memory_tags_prompt = "\n\n💡 Tip: before analyzing the task, it is recommended to use the memory tool (action=save) to record key information for later retrieval and reuse."

        # Build the memory tag list
        if any(tags for tags in memory_tags.values()):
            memory_tags_prompt += self._format_memory_tags(memory_tags)

        return memory_tags_prompt

    def _has_memory_tool(self) -> bool:
        """Check whether the memory tool is available"""
        tool_registry = self.agent.get_tool_registry()
        if tool_registry:
            tool_names = [tool.name for tool in tool_registry.tools.values()]
            return "memory" in tool_names
        return False

    def prepare_memory_context_prompt(
        self, user_input: str, retrieval_budget: Optional[int] = None
    ) -> str:
        """Proactively retrieve historical memories related to the current task and inject them into the context

        Unlike prepare_memory_tags_prompt, this method directly performs semantic retrieval,
        injecting the most relevant memory content into the session context rather than merely listing tags for the model to retrieve on its own.

        Args:
            user_input: The user input text of the current task
            retrieval_budget: The token upper limit injected by a single retrieval; when None, uses the
                configured get_context_memory_retrieval_budget(). Callers may pass it dynamically
                based on the layered context budget.

        Returns:
            str: The formatted relevant memory prompt, or an empty string if there is no relevant memory
        """
        if not user_input or not user_input.strip():
            return ""

        # Only perform retrieval when a memory directory exists and contains memory files, to avoid needless overhead
        try:
            from pathlib import Path

            from haijunbot.haijunbot_utils.config import get_data_dir

            # Check whether the project memory directory and global memory directory exist
            project_dir = Path(".haijunbot/memory")
            global_dir = Path(get_data_dir()) / "memory"
            if not project_dir.exists() and not global_dir.exists():
                return ""
        except Exception:
            return ""

        try:
            from haijunbot.haijunbot_memory_organizer.smart_retrieval import SmartRetriever

            retriever = SmartRetriever()
            memories = retriever.semantic_search(
                query=user_input,
                memory_types=["project", "global"],
                natures=["long_term"],
                limit=5,
            )
            if not memories:
                return ""

            # Retrieval budget: truncate once the accumulated tokens exceed the limit, to prevent retrieval results from crowding the context
            from haijunbot.haijunbot_utils.config import get_context_memory_retrieval_budget
            from haijunbot.haijunbot_utils.embedding import get_context_token_count

            if retrieval_budget is None:
                retrieval_budget = get_context_memory_retrieval_budget()

            # Format the retrieval results
            prompt = "\n\n📚 The following relevant historical memories were automatically retrieved based on the current task (for reference):"
            used_tokens = 0
            for i, memory in enumerate(memories):
                content = (memory.content or "").strip()
                if not content:
                    continue
                # Limit the length of a single memory entry, to avoid blowing up the context
                if len(content) > 500:
                    content = content[:500] + "..."
                tags_str = "/".join(memory.tags) if memory.tags else "no tags"
                entry = (
                    f"\n\n[{i + 1}] "
                    f"({memory.memory_type}/{memory.nature} | {tags_str})\n{content}"
                )
                # Cumulative token budget truncation
                try:
                    entry_tokens = get_context_token_count(entry)
                except Exception:
                    entry_tokens = len(entry) // 2
                if used_tokens + entry_tokens > retrieval_budget:
                    break
                used_tokens += entry_tokens
                prompt += entry

            return prompt
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.memory_manager",
                function="prepare_memory_context_prompt",
            )
            return ""

    def _format_memory_tags(self, memory_tags: dict[str, Any]) -> str:
        """Format the memory tags"""
        prompt = "\n\nThe following memory tags exist in the system; you can use the memory tool (action=retrieve) to retrieve relevant memories:"

        type_names = {
            "short_term": "short-term memory",
            "project_long_term": "project long-term memory (project/long_term)",
            "global_long_term": "global long-term memory (global/long_term)",
        }

        for memory_type, tags in memory_tags.items():
            if tags:
                type_name = type_names.get(memory_type, memory_type)
                prompt += f"\n- {type_name}: {', '.join(tags)}"

        return prompt

    def prompt_memory_save(self) -> None:
        """Let the large model automatically decide and save information worth remembering"""
        # Check whether memory-related tools are available
        tool_registry = self.agent.get_tool_registry()
        if not tool_registry:
            return

        tool_names = [tool.name for tool in tool_registry.tools.values()]
        if "memory" not in tool_names:
            return

        # Build the prompt so the large model can decide and save memories on its own
        prompt = """Review this task and judge whether there is information worth remembering. Use the memory tool (action=save) to save:
- Scope memory_type: project / global / short_term
- Nature nature: long_term / procedural (how-to/pitfalls) / episodic (episodic archive)
If there is no information worth remembering, just say so."""

        # Handle memory saving
        try:
            # Clear this round's execution markers, to accurately judge whether the memory tool was called
            try:
                self.agent.set_user_data("__last_executed_tool__", "")
                self.agent.set_user_data("__executed_tools__", [])
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.memory_manager",
                    function="prompt_memory_save",
                )
                pass

            if self.agent._native_active():
                # Native: the model calls the memory tool directly (executed by the internal native loop), no text JSON parsing needed
                self.agent._run_native_until_content(prompt)
            else:
                response = self.agent.model.chat_until_success(prompt)
                # Execute tool calls (if any)
                need_return, result = self.agent._call_tools(response)

            # Judge whether a memory was saved based on the tools actually executed
            saved = False
            try:
                last_tool = self.agent.get_user_data("__last_executed_tool__")
                saved = last_tool == "memory"
            except Exception:
                saved = False

            if saved:
                PrettyOutput.auto_print("✅ Valuable information has been automatically saved to the memory system")
            else:
                PrettyOutput.auto_print("ℹ️ This task has no information that especially needs to be remembered")

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Memory analysis failed: {str(e)}")
        finally:
            # Set the memory prompt completion flag, to avoid repeated handling triggered by events
            self._memory_prompted = True
            try:
                self.agent.set_user_data("__memory_save_prompted__", True)
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_agent.memory_manager",
                    function="prompt_memory_save",
                )
                pass

    def add_memory_prompts_to_addon(self, addon_prompt: str, tool_registry: Any) -> str:
        """Add memory-related prompts to the addon prompt"""
        memory_prompts = ""

        if tool_registry:
            tool_names = [tool.name for tool in tool_registry.tools.values()]

            # If the memory tool is available, add the relevant prompts (one line each for save and retrieve)
            if "memory" in tool_names:
                memory_prompts += (
                    "\n    - When there is key information to consolidate, save it with memory(action=save), "
                    "specifying the scope with memory_type (project/global/short_term) and "
                    "the nature with nature (long_term/procedural/episodic): "
                    "project+long_term stores project-related information (architecture decisions, key configs, implementation conventions), "
                    "global+long_term stores general experience and user preferences, and short_term stores temporary information for the current task"
                )
                memory_prompts += "\n    - When past context or solutions are needed, use memory(action=retrieve) to retrieve relevant memories"

        return memory_prompts

    # -----------------------
    # Event subscription and handling (side channel)
    # -----------------------
    def _subscribe_events(self) -> None:
        bus = self.agent.get_event_bus()
        # Reset the deduplication flag when a task starts
        bus.subscribe(TASK_STARTED, self._on_task_started)
        # Try to save memory before clearing history (if force-save is enabled and not yet handled)
        bus.subscribe(BEFORE_HISTORY_CLEAR, self._ensure_memory_prompt)
        # Try once more as a fallback when the task completes
        bus.subscribe(TASK_COMPLETED, self._ensure_memory_prompt)

    def _on_task_started(self, **payload: Any) -> None:
        self._memory_prompted = False
        try:
            self.agent.set_user_data("__memory_save_prompted__", False)
        except Exception as e:
            save_exception(
                e, module="haijunbot_agent.memory_manager", function="_on_task_started"
            )
            pass

    def _ensure_memory_prompt(self, **payload: Any) -> None:
        # Only enabled when force-save memory is on
        if not getattr(self.agent, "force_save_memory", False):
            return
        # Avoid repeated prompting/handling within the same task
        if self._memory_prompted:
            return
        try:
            already = bool(self.agent.get_user_data("__memory_save_prompted__"))
            if already:
                self._memory_prompted = True
                return
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_agent.memory_manager",
                function="_ensure_memory_prompt",
            )
            pass
        # Execute the save logic silently; failure does not affect the main flow
        try:
            self.prompt_memory_save()
        except Exception:
            # Ignore exceptions to keep the main flow stable
            self._memory_prompted = True
