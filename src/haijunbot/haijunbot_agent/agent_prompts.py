# -*- coding: utf-8 -*-
"""Generic Agent system prompt module

Provides scenario classification, difficulty assessment, and system prompt loading.
Scenario prompt files are located in the builtin/prompts/agent_system/ directory,
and user extension files can be placed in the ~/.haijunbot/prompts/agent_system/ directory.
"""

from typing import Dict, List, Tuple, Union

from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.scenario_prompts import (
    _get_scenario_types,
    classify_user_request as _classify_user_request_impl,
    get_system_prompt as _get_system_prompt_impl,
)


# Scenario subdirectory name
_SCENARIO_SUBDIR = "agent_system"

# Scenario type definitions (backward compatible, actually loaded from files)
SCENARIO_TYPES: Dict[str, str] = _get_scenario_types(_SCENARIO_SUBDIR)


def classify_user_request(
    user_input: Union[str, List[ContentBlock]],
) -> Tuple[str, str, float]:
    """Classify the user's request using normal_llm

    Args:
        user_input: The user's request description (supports plain text or multimodal content)

    Returns:
        Tuple[str, str, float]: (scenario type, difficulty level, recommended sampling temperature)
    """
    return _classify_user_request_impl(
        user_input,
        scenario_subdir=_SCENARIO_SUBDIR,
        default_scenario_name="General task",
        classification_context="scenario type",
        difficulty_descriptions={
            "easy": "Simple Q&A, single-step operations, clear small tasks",
            "medium": "Requires multiple steps, needs context understanding, involves some complexity",
            "hard": "Requires deep analysis, multi-dimensional synthesis, needs professional knowledge and deep thinking",
        },
    )


def get_system_prompt(scenario: str = "default") -> str:
    """Get the corresponding system prompt by scenario type

    Args:
        scenario: Scenario type

    Returns:
        str: The complete system prompt for the corresponding scenario
    """
    return _get_system_prompt_impl(scenario, scenario_subdir=_SCENARIO_SUBDIR)
