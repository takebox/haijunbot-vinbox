# -*- coding: utf-8 -*-
"""
Event topic and payload type definitions (haijunbot_agent.events)

Purpose:
- Unify event names to avoid drift caused by hardcoded strings throughout the code
- Provide type hints for event payloads to facilitate static checking and future documentation
- This file only provides constants and type definitions, does not change existing behavior
"""

from typing import Any
from typing import List
from typing import TypedDict

# Event topic constants
BEFORE_TOOL_CALL = "before_tool_call"
AFTER_TOOL_CALL = "after_tool_call"

# Session and task lifecycle related
TASK_STARTED = "task_started"
TASK_COMPLETED = "task_completed"

# Summary phase
BEFORE_SUMMARY = "before_summary"
AFTER_SUMMARY = "after_summary"

# Addon prompts
BEFORE_ADDON_PROMPT = "before_addon_prompt"
AFTER_ADDON_PROMPT = "after_addon_prompt"

# History cleanup
BEFORE_HISTORY_CLEAR = "before_history_clear"
AFTER_HISTORY_CLEAR = "after_history_clear"

# Model calls
BEFORE_MODEL_CALL = "before_model_call"
AFTER_MODEL_CALL = "after_model_call"

# Others
INTERRUPT_TRIGGERED = "interrupt_triggered"
BEFORE_TOOL_FILTER = "before_tool_filter"
TOOL_FILTERED = "tool_filtered"


# Event payload types (only for type hints)
class BeforeToolCallEvent(TypedDict, total=False):
    agent: Any
    current_response: str
    tool_name: str  # New: tool name
    tool_args: dict  # New: tool arguments


class AfterToolCallEvent(TypedDict, total=False):
    agent: Any
    current_response: str
    need_return: bool
    tool_prompt: str


# Task lifecycle
class TaskStartedEvent(TypedDict, total=False):
    agent: Any
    name: str
    description: str
    user_input: str


class TaskCompletedEvent(TypedDict, total=False):
    agent: Any
    auto_completed: bool
    need_summary: bool


# Summary phase
class BeforeSummaryEvent(TypedDict, total=False):
    agent: Any
    prompt: str
    auto_completed: bool
    need_summary: bool


class AfterSummaryEvent(TypedDict, total=False):
    agent: Any
    summary: str


# Addon prompts
class BeforeAddonPromptEvent(TypedDict, total=False):
    agent: Any
    need_complete: bool
    current_message: str
    has_session_addon: bool


class AfterAddonPromptEvent(TypedDict, total=False):
    agent: Any
    need_complete: bool
    addon_text: str
    final_message: str


# History cleanup
class BeforeHistoryClearEvent(TypedDict, total=False):
    agent: Any


class AfterHistoryClearEvent(TypedDict, total=False):
    agent: Any


# Model calls
class BeforeModelCallEvent(TypedDict, total=False):
    agent: Any
    message: str


class AfterModelCallEvent(TypedDict, total=False):
    agent: Any
    message: str
    response: str


# Interrupt
class InterruptTriggeredEvent(TypedDict, total=False):
    agent: Any
    current_response: str
    user_input: str


# Tool filtering
class BeforeToolFilterEvent(TypedDict, total=False):
    agent: Any
    task: str
    total_tools: int
    threshold: int


class ToolFilteredEvent(TypedDict, total=False):
    agent: Any
    task: str
    selected_tools: List[str]
    total_tools: int
    threshold: int


__all__ = [
    "BEFORE_TOOL_CALL",
    "AFTER_TOOL_CALL",
    "TASK_STARTED",
    "TASK_COMPLETED",
    "BEFORE_SUMMARY",
    "AFTER_SUMMARY",
    "BEFORE_ADDON_PROMPT",
    "AFTER_ADDON_PROMPT",
    "BEFORE_HISTORY_CLEAR",
    "AFTER_HISTORY_CLEAR",
    "BEFORE_MODEL_CALL",
    "AFTER_MODEL_CALL",
    "INTERRUPT_TRIGGERED",
    "BEFORE_TOOL_FILTER",
    "TOOL_FILTERED",
    "BeforeToolCallEvent",
    "AfterToolCallEvent",
    "TaskStartedEvent",
    "TaskCompletedEvent",
    "BeforeSummaryEvent",
    "AfterSummaryEvent",
    "BeforeAddonPromptEvent",
    "AfterAddonPromptEvent",
    "BeforeHistoryClearEvent",
    "AfterHistoryClearEvent",
    "BeforeModelCallEvent",
    "AfterModelCallEvent",
    "InterruptTriggeredEvent",
    "BeforeToolFilterEvent",
    "ToolFilteredEvent",
]
