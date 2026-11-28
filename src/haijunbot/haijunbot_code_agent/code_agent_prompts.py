# -*- coding: utf-8 -*-
"""CodeAgent system prompt module

Scenario prompt files are located in the builtin/prompts/code_agent_system/ directory,
and user extension files can be placed in the ~/.haijunbot/prompts/code_agent_system/ directory.
"""

from typing import Dict, List, Tuple, Union

from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.scenario_prompts import (
    _get_scenario_types,
    classify_user_request as _classify_user_request_impl,
    get_system_prompt as _get_system_prompt_impl,
)


# Scenario subdirectory name
_SCENARIO_SUBDIR = "code_agent_system"

# Scenario type definitions (backward compatible, actually loaded from files)
SCENARIO_TYPES: Dict[str, str] = _get_scenario_types(_SCENARIO_SUBDIR)


def classify_user_request(
    user_input: Union[str, List[ContentBlock]],
) -> Tuple[str, str, float]:
    """Classify the user request using normal_llm

    Args:
        user_input: the user's request description (plain text or multimodal)

    Returns:
        Tuple[str, str, float]: (scenario type, difficulty level, recommended sampling temperature)
    """
    return _classify_user_request_impl(
        user_input,
        scenario_subdir=_SCENARIO_SUBDIR,
        default_scenario_name="General development",
        classification_context="development scenario type",
        difficulty_descriptions={
            "easy": "Changes to a single file, simple configuration adjustments, clearly small changes",
            "medium": "Changes across multiple files, requires understanding business logic, involves a certain degree of complexity",
            "hard": "Architecture-level changes, complex refactoring, requires deep analysis and detailed design",
        },
    )


def get_system_prompt(scenario: str = "default") -> str:
    """Get the corresponding system prompt based on the scenario

    Args:
        scenario: scenario type

    Returns:
        str: the complete system prompt for the corresponding scenario
    """
    return _get_system_prompt_impl(scenario, scenario_subdir=_SCENARIO_SUBDIR)
