# -*- coding: utf-8 -*-
"""System prompt optimization module

This module provides the ability to automatically optimize the system prompt based on user requirements.
"""

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.output import PrettyOutput


def optimize_system_prompt(
    current_system_prompt: str,
    user_requirement: str,
) -> str:
    """Optimize the system prompt based on user requirements

    Args:
        current_system_prompt: The current system prompt
        user_requirement: The description of the user's requirement

    Returns:
        str: The optimized system prompt
    """
    try:
        PrettyOutput.auto_print("🔄 Optimizing system prompt...")

        # Get the smart_llm platform (use the smart model for optimization)
        # get_smart_platform already sets model_name and llm_group internally, no need to set them again
        platform = PlatformRegistry().get_normal_platform()

        platform.set_suppress_output(False)

        # Build the optimization prompt
        optimization_prompt = f"""You are a professional system prompt optimization expert. Please optimize the system prompt in a targeted manner based on the current system prompt and the user's requirement.

<current_system_prompt>
{current_system_prompt}
</current_system_prompt>

<user_requirement>
{user_requirement}
</user_requirement>

[Optimization requirements]
1. Keep the core functionality and architecture of the original system prompt unchanged
2. Based on the user's requirement, enhance or adjust the descriptions of relevant parts in a targeted manner
3. Ensure the optimized prompt better fits the user's specific task scenario
4. Keep the prompt's structure clear and its logic complete
5. If the user's requirement involves a specific domain (such as code development, data analysis, etc.), appropriately emphasize the relevant best practices and cautions
6. The optimized prompt should help the AI better understand and execute the user's specific requirement

Please output the complete optimized system prompt directly, without including any explanation or descriptive text."""

        # Call the large model for optimization
        optimized_prompt = platform.chat_until_success(optimization_prompt)

        if optimized_prompt and optimized_prompt.strip():
            PrettyOutput.auto_print("✅ System prompt optimization complete")
            return optimized_prompt.strip()
        else:
            PrettyOutput.auto_print("⚠️ Optimization result is empty, using the original system prompt")
            return current_system_prompt

    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ System prompt optimization failed: {str(e)}, using the original system prompt")
        return current_system_prompt
