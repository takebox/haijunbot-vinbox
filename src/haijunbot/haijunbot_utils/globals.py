# -*- coding: utf-8 -*-
"""
Global variables and configuration module
This module manages the global state and configuration of the HaijunBot system.
It includes:
- Global agent management
- Console configuration with a custom theme
- Environment initialization
"""

import os

# Global variable: store the message history
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

message_history: List[str] = []

# Global input buffer: when frontend input is received but the system is not currently waiting for input, it is stored in this buffer first
# The messages in the buffer will be consumed in a single batch during each agent loop iteration
input_buffer: List[str] = []
MAX_INPUT_BUFFER_SIZE = 100

MAX_HISTORY_SIZE = 50

# Short-term memory storage
short_term_memories: List[Dict[str, Any]] = []
MAX_SHORT_TERM_MEMORIES = 100

import colorama  # noqa: E402
from rich.console import Console  # noqa: E402
from rich.theme import Theme  # noqa: E402

# Initialize colorama to support cross-platform colored text
colorama.init()
# Disable tokenizers parallelism to avoid multiprocessing issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Global agent management
global_agents: Dict[str, Any] = {}

# Proxy node: the target node ID to which HTTP proxy requests are forwarded; empty by default (handled locally)
proxy_node: Optional[str] = None
# Master node URL: used to forward HTTP proxy requests to the master node
master_url: Optional[str] = None
# Agent ID: a unique identifier assigned by the Web Gateway's AgentManager, passed in via the --agent-id argument
agent_id: Optional[str] = None
# Input injection callback: when the Agent is waiting for input, this callback can be used to inject messages directly into the input stream
# Set as Callable[[str], None], receiving the message text; None when not waiting for input
input_inject_callback: Optional[Any] = None
# Use a stack structure to track the nested running state of agents, supporting scenarios where an agent calls other agents
running_agent_stack: List[str] = []  # The stack of running agents (the topmost is the currently running agent)
# Represents the depth of interaction with the large model (>0 means interaction is in progress)
g_in_chat: int = 0
# Represents whether an interrupt signal has been received
g_interrupt: int = 0
# The PID of the currently running script process
current_script_pid: Optional[int] = None


# Configure the rich console with a custom theme
custom_theme = Theme(
    {
        "INFO": "yellow",
        "WARNING": "yellow",
        "ERROR": "red",
        "SUCCESS": "green",
        "SYSTEM": "cyan",
        "CODE": "green",
        "RESULT": "blue",
        "PLANNING": "magenta",
        "PROGRESS": "white",
        "DEBUG": "blue",
        "USER": "green",
        "TOOL": "yellow",
    }
)
console = Console(theme=custom_theme)


def make_agent_name(agent_name: str) -> str:
    """
    Generate a unique agent name based on the existing global_agents.

    Convention:
    - If the name is not yet taken, return the original name directly;
    - If an Agent with the same name already exists, search for an available name in the form `name_1`, `name_2`, ... in order;
    - Existing suffixed names are also taken into account, e.g. if `name`, `name_1`, `name_3` already exist, return `name_2`.

    Parameters:
        agent_name: The base agent name

    Returns:
        str: The unique agent name
    """
    # If the name is not taken, return the original name directly
    if agent_name not in global_agents:
        return agent_name

    # An Agent with the same name already exists; search for the first unoccupied name in the form name_1, name_2...
    index = 1
    while True:
        candidate = f"{agent_name}_{index}"
        if candidate not in global_agents:
            return candidate
        index += 1


def get_agent(agent_name: str) -> Any:
    """
    Get the agent instance with the specified name.

    Parameters:
        agent_name: The agent name

    Returns:
        Any: The agent instance, or None if it does not exist
    """
    return global_agents.get(agent_name)


def get_current_agent() -> Any:
    """
    Get the currently running agent instance.

    Important: only returns a running agent, ensuring that a completed agent is never returned.
    This guarantees that the returned agent is definitely running, and its internal state can be safely modified.

    If there is no running agent, return None (it may be empty, but it must never be wrong).

    Returns:
        Any: The running agent instance, or None if there is no running agent
    """
    # Only return a running agent, ensuring that a completed agent is never returned
    global running_agent_stack
    if running_agent_stack:
        current_agent_name = running_agent_stack[-1]
        if current_agent_name in global_agents:
            return global_agents.get(current_agent_name)
    return None


def get_current_agent_name() -> str:
    """
    Get the current agent name (the last agent to start running, which may have completed).
    Note: this returns the "last agent to start running", which may have already finished running.

    Returns:
        str: The current agent name, or an empty string if it does not exist
    """
    agent = get_current_agent()
    if agent:
        name = getattr(agent, "name", None)
        if isinstance(name, str):
            return name
    return ""


def set_current_agent(agent_name: str, agent: Any) -> None:
    """
    Set the name of the currently running agent (push onto the stack).
    Should be called when the agent starts running.
    Supports nested calls: when an agent calls other agents, the state is correctly saved.

    Note: the same agent can run multiple times (non-nested), and each run is pushed onto the stack independently.

    Parameters:
        agent_name: The agent name
    """
    global running_agent_stack, global_agents
    global_agents[agent_name] = agent
    running_agent_stack.append(agent_name)


def clear_current_agent() -> None:
    """
    Clear the running agent name (pop from the stack).
    Should be called when the agent finishes running.
    Supports nested calls: when a child agent finishes, the parent agent's running state is restored.

    Important: only remove the agent from the top of the stack, ensuring the correctness of nested calls.
    If the agent is not at the top of the stack, the state is inconsistent (possibly a duplicate call or an exception);
    a warning will be logged but the stack will not be modified, to avoid breaking the nested structure.

    Parameters:
        agent_name: The agent name to clear (used for validation, ensuring the correct agent is cleared)
    """
    global running_agent_stack
    if not running_agent_stack:
        # The stack is empty; this may be a duplicate clear call or an inconsistent state
        return
    current_agent_name = running_agent_stack.pop()
    if current_agent_name in global_agents:
        del global_agents[current_agent_name]


def get_agent_list() -> str:
    """
    Get a formatted string representing the current agent state.

    Returns:
        str: A formatted string containing the agent count and current agent names
    """
    global global_agents
    if not global_agents:
        return ""
    return "[" + str(len(global_agents)) + "]" + ", ".join(global_agents.keys())


def set_in_chat(status: bool) -> None:
    """
    Set the interaction state with the large model.

    Parameters:
        status: True means increase the interaction depth, False means decrease
    """
    global g_in_chat
    if status:
        g_in_chat += 1
    else:
        g_in_chat = max(0, g_in_chat - 1)


def get_in_chat() -> bool:
    """
    Get whether the system is currently interacting with the large model.

    Returns:
        bool: The current interaction state (>0 means interaction is in progress)
    """
    return g_in_chat > 0


def set_interrupt(status: bool) -> None:
    """
    Set the interrupt signal state.

    Parameters:
        status: The interrupt state
    """
    global g_interrupt
    if status:
        g_interrupt += 1
    else:
        g_interrupt = 0


def get_interrupt() -> int:
    """
    Get the current interrupt signal state.

    Returns:
        int: The current interrupt count
    """
    return g_interrupt


def set_script_pid(pid: Optional[int]) -> None:
    """
    Set the PID of the currently running script process.

    Parameters:
        pid: The process PID; None means clear it
    """
    global current_script_pid
    current_script_pid = pid


def get_script_pid() -> Optional[int]:
    """
    Get the PID of the currently running script process.

    Returns:
        Optional[int]: The current script process PID, or None if no script is running
    """
    global current_script_pid
    return current_script_pid


def clear_script_pid() -> None:
    """
    Clear the PID of the currently running script process.
    Should be called after the script finishes executing.
    """
    global current_script_pid
    current_script_pid = None


def set_last_message(message: str) -> None:
    """
    Add a message to the history.

    Parameters:
        message: The message to save
    """
    global message_history
    if message:
        # Avoid duplicate additions
        if not message_history or message_history[-1] != message:
            message_history.append(message)
            if len(message_history) > MAX_HISTORY_SIZE:
                message_history.pop(0)


def get_last_message() -> str:
    """
    Get the last message.

    Returns:
        str: The last message, or an empty string if the history is empty
    """
    global message_history
    if message_history:
        return message_history[-1]
    return ""


def get_message_history() -> List[str]:
    """
    Get the complete message history.

    Returns:
        List[str]: The message history list
    """
    global message_history
    return message_history


def add_short_term_memory(memory_data: Dict[str, Any]) -> None:
    """
    Add a short-term memory to the global storage.

    Parameters:
        memory_data: A dictionary containing the memory information
    """
    global short_term_memories
    short_term_memories.append(memory_data)
    # If the maximum count is exceeded, delete the oldest memory
    if len(short_term_memories) > MAX_SHORT_TERM_MEMORIES:
        short_term_memories.pop(0)


def get_short_term_memories(tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Get short-term memories, optionally filtered by tags.

    Parameters:
        tags: The list of tags used for filtering (optional)

    Returns:
        List[Dict[str, Any]]: The list of matching short-term memories, sorted in descending order by creation time
    """
    global short_term_memories

    # Get a copy of the memories
    memories_copy = short_term_memories.copy()

    # Filter by tags (if tags are provided)
    if tags:
        filtered_memories = []
        for memory in memories_copy:
            memory_tags = memory.get("tags", [])
            if any(tag in memory_tags for tag in tags):
                filtered_memories.append(memory)
        memories_copy = filtered_memories

    # Sort by creation time (newest first)
    memories_copy.sort(key=lambda x: x.get("created_at", ""), reverse=True)

    return memories_copy


def clear_short_term_memories() -> None:
    """
    Clear all short-term memories.
    """
    global short_term_memories
    short_term_memories.clear()


def add_input_buffer(message: str) -> None:
    """
    Add a message to the global input buffer.

    Parameters:
        message: The message to add
    """
    global input_buffer
    if message:
        input_buffer.append(message)
        # If the maximum count is exceeded, delete the oldest message
        if len(input_buffer) > MAX_INPUT_BUFFER_SIZE:
            input_buffer.pop(0)


def get_input_buffer() -> List[str]:
    """
    Get all messages in the global input buffer and clear the buffer.

    Returns:
        List[str]: The list of messages in the buffer
    """
    global input_buffer
    messages = input_buffer.copy()
    input_buffer.clear()
    return messages


def peek_input_buffer() -> List[str]:
    """
    View all messages in the global input buffer without clearing the buffer.

    Returns:
        List[str]: The list of messages in the buffer (a copy)
    """
    global input_buffer
    return input_buffer.copy()


def clear_input_buffer() -> None:
    """
    Clear the global input buffer.
    """
    global input_buffer
    input_buffer.clear()


def get_all_memory_tags() -> Dict[str, List[str]]:
    """
    Get the set of tags across all memory types.
    Each type returns at most 200 tags. When the number of tags exceeds 200, a hybrid strategy is used:
    - About 100 tags are extracted from the most recent memories (sorted by creation time)
    - The remaining about 100 tags are randomly extracted from the rest of the memories
    - After merging, the first 200 tags are returned

    Returns:
        Dict[str, List[str]]: A list of tags grouped by memory type
    """
    import json
    import random
    from pathlib import Path

    from haijunbot.haijunbot_utils.config import get_data_dir
    from haijunbot.haijunbot_utils.exception_utils import save_exception

    tags_by_type: Dict[str, List[str]] = {
        "short_term": [],
        "project_long_term": [],
        "global_long_term": [],
    }

    MAX_TAGS_PER_TYPE = 200

    # Get short-term memory tags
    short_term_tags = set()
    for memory in short_term_memories:
        short_term_tags.update(memory.get("tags", []))
    short_term_tags_list = sorted(list(short_term_tags))
    if len(short_term_tags_list) > MAX_TAGS_PER_TYPE:
        # Hybrid strategy: half extracted from the most recent memories, the other half randomly
        # Sort the memories by creation time (newest first)
        sorted_memories = sorted(
            short_term_memories, key=lambda x: x.get("created_at", ""), reverse=True
        )
        half_count = MAX_TAGS_PER_TYPE // 2

        # Extract tags from the first half of the memories (most recently used)
        recent_tags = set()
        for memory in sorted_memories[: len(sorted_memories) // 2]:
            recent_tags.update(memory.get("tags", []))
            if len(recent_tags) >= half_count:
                break

        # Extract tags from the remaining memories (randomly)
        remaining_memories = sorted_memories[len(sorted_memories) // 2 :]
        random_tags = set()
        for memory in random.sample(
            remaining_memories, min(len(remaining_memories), MAX_TAGS_PER_TYPE)
        ):
            random_tags.update(memory.get("tags", []))
            if len(recent_tags) + len(random_tags) >= MAX_TAGS_PER_TYPE:
                break

        # Merge the tags and return the first 200
        mixed_tags = list(recent_tags | random_tags)
        tags_by_type["short_term"] = sorted(mixed_tags)[:MAX_TAGS_PER_TYPE]
    else:
        tags_by_type["short_term"] = short_term_tags_list

    # Get project long-term memory tags
    project_memory_dir = Path(".haijunbot/memory")
    if project_memory_dir.exists():
        project_memories = []
        for memory_file in project_memory_dir.glob("*.json"):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)
                    project_memories.append(memory_data)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.globals", function="get_all_memory_tags"
                )
                pass

        # Collect all tags
        project_tags = set()
        for memory in project_memories:
            project_tags.update(memory.get("tags", []))
        project_tags_list = sorted(list(project_tags))

        if len(project_tags_list) > MAX_TAGS_PER_TYPE:
            # Hybrid strategy: half extracted from the most recent memories, the other half randomly
            # Sort the memories by creation time (newest first)
            sorted_memories = sorted(
                project_memories, key=lambda x: x.get("created_at", ""), reverse=True
            )
            half_count = MAX_TAGS_PER_TYPE // 2

            # Extract tags from the first half of the memories (most recently used)
            recent_tags = set()
            for memory in sorted_memories[: len(sorted_memories) // 2]:
                recent_tags.update(memory.get("tags", []))
                if len(recent_tags) >= half_count:
                    break

            # Extract tags from the remaining memories (randomly)
            remaining_memories = sorted_memories[len(sorted_memories) // 2 :]
            random_tags = set()
            sample_size = min(len(remaining_memories), MAX_TAGS_PER_TYPE)
            if sample_size > 0:
                for memory in random.sample(remaining_memories, sample_size):
                    random_tags.update(memory.get("tags", []))
                    if len(recent_tags) + len(random_tags) >= MAX_TAGS_PER_TYPE:
                        break

            # Merge the tags and return the first 200
            mixed_tags = list(recent_tags | random_tags)
            tags_by_type["project_long_term"] = sorted(mixed_tags)[:MAX_TAGS_PER_TYPE]
        else:
            tags_by_type["project_long_term"] = project_tags_list

    # Get global long-term memory tags
    global_memory_dir = Path(get_data_dir()) / "memory" / "global_long_term"
    if global_memory_dir.exists():
        global_memories = []
        for memory_file in global_memory_dir.glob("*.json"):
            try:
                with open(memory_file, "r", encoding="utf-8") as f:
                    memory_data = json.load(f)
                    global_memories.append(memory_data)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_utils.globals", function="get_all_memory_tags"
                )
                pass

        # Collect all tags
        global_tags = set()
        for memory in global_memories:
            global_tags.update(memory.get("tags", []))
        global_tags_list = sorted(list(global_tags))

        if len(global_tags_list) > MAX_TAGS_PER_TYPE:
            # Hybrid strategy: half extracted from the most recent memories, the other half randomly
            # Sort the memories by creation time (newest first)
            sorted_memories = sorted(
                global_memories, key=lambda x: x.get("created_at", ""), reverse=True
            )
            half_count = MAX_TAGS_PER_TYPE // 2

            # Extract tags from the first half of the memories (most recently used)
            recent_tags = set()
            for memory in sorted_memories[: len(sorted_memories) // 2]:
                recent_tags.update(memory.get("tags", []))
                if len(recent_tags) >= half_count:
                    break

            # Extract tags from the remaining memories (randomly)
            remaining_memories = sorted_memories[len(sorted_memories) // 2 :]
            random_tags = set()
            sample_size = min(len(remaining_memories), MAX_TAGS_PER_TYPE)
            if sample_size > 0:
                for memory in random.sample(remaining_memories, sample_size):
                    random_tags.update(memory.get("tags", []))
                    if len(recent_tags) + len(random_tags) >= MAX_TAGS_PER_TYPE:
                        break

            # Merge the tags and return the first 200
            mixed_tags = list(recent_tags | random_tags)
            tags_by_type["global_long_term"] = sorted(mixed_tags)[:MAX_TAGS_PER_TYPE]
        else:
            tags_by_type["global_long_term"] = global_tags_list

    return tags_by_type
