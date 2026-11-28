# -*- coding: utf-8 -*-
"""Model/platform switching responsibility module
The "model/platform switching" cluster of responsibilities extracted from the Agent class.
Design notes:
- Follows the existing splitting paradigm of the haijunbot_agent package (such as MemoryManager(self), HistoryCompressor(self)):
  this module holds an agent reference, and within its method bodies accesses the Agent's other capabilities via self.agent.xxx.
- The Agent side keeps thin delegating methods with the same names, ensuring the external interface (including reverse calls from run_loop / code_agent) remains completely unchanged.
- Circular dependencies are handled via TYPE_CHECKING.
"""

from typing import TYPE_CHECKING
from typing import Callable
from typing import List
from typing import Optional
from typing import Union
from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.output import PrettyOutput

if TYPE_CHECKING:
    from haijunbot.haijunbot_agent import Agent


class ModelSwitcher:
    """Model/platform switching responsibility implementation
    All methods are equivalent to the same-named methods formerly on the Agent class, only replacing self.xxx with self.agent.xxx.
    """

    def __init__(self, agent: "Agent") -> None:
        self.agent = agent

    def switch_model_by_difficulty(self, difficulty: str) -> None:
        """Switch the model based on task difficulty

        Args:
            difficulty: Task difficulty level (easy/medium/hard)
        """
        # If the user has manually switched models, disable automatic switching
        if getattr(self.agent, "_manual_model_switch", False):
            return

        # Mapping from difficulty to model type: only quality upgrades (hard->smart), no cheap downgrades,
        # to avoid a misjudged difficulty dumping a real task onto a cheap-tier model and sacrificing quality.
        difficulty_to_model_type = {
            "easy": "normal",
            "medium": "normal",
            "hard": "smart",
        }

        model_type = difficulty_to_model_type.get(difficulty, "normal")
        current_model_type = getattr(self.agent, "_model_type", "normal")

        # If the model type has not changed, no switch is needed
        if model_type == current_model_type:
            return

        # Lazy import to avoid circular dependencies
        from haijunbot.haijunbot_agent.builtin_input_handler import switch_platform_type

        # Use the generic switch_platform_type function to perform the switch
        success = switch_platform_type(
            self.agent, model_type, preserve_model_group=True
        )

        if success:
            # Update the model type marker
            self.agent._model_type = model_type

            # If there is a system prompt, set it on the new model
            if hasattr(self.agent, "system_prompt") and self.agent.system_prompt:
                # Use prompt_manager to rebuild the system prompt (including methodology, etc.)
                if hasattr(self.agent, "prompt_manager") and self.agent.prompt_manager:
                    prompt_text = self.agent.prompt_manager.build_system_prompt(
                        self.agent
                    )
                    self.agent.model.set_system_prompt(prompt_text)
                else:
                    self.agent.model.set_system_prompt(self.agent.system_prompt)

            # Output the switch information
            model_type_display = {
                "cheap": "Economy",
                "normal": "Standard",
                "smart": "Smart",
            }.get(model_type, model_type)
            PrettyOutput.auto_print(
                f"🔄 Switched model type based on task difficulty ({difficulty}): {model_type_display} ({model_type})"
            )

        else:
            PrettyOutput.auto_print("⚠️ Model switch failed; keeping the current model")

    def classify_and_switch_model(
        self,
        user_input: Union[str, List[ContentBlock]],
        classify_fn: Callable,
        get_prompt_fn: Callable,
    ) -> None:
        """Execute the unified flow of requirement classification, model switching, sampling temperature adaptation, and system prompt updating

        Args:
            user_input: The user's requirement description
            classify_fn: Classification function with signature (user_input) -> (scenario, difficulty, temperature)
            get_prompt_fn: Function to get the system prompt, with signature (scenario) -> str
        """
        try:
            scenario, difficulty, temperature = classify_fn(user_input)

            # Switch the model based on difficulty (may rebuild self.model)
            self.switch_model_by_difficulty(difficulty)

            # Adjust the sampling temperature based on the task nature (must be applied after a possible rebuild)
            self.apply_task_temperature(temperature)

            # Get the corresponding system prompt based on the classification result and update it
            scenario_system_prompt = get_prompt_fn(scenario)
            if scenario_system_prompt != self.agent.system_prompt:
                self.agent.system_prompt = scenario_system_prompt
                # Update the model's system prompt
                if self.agent.model:
                    # Use prompt_manager to rebuild the system prompt (including methodology, etc.)
                    if self.agent.prompt_manager:
                        prompt_text = self.agent.prompt_manager.build_system_prompt(
                            self.agent
                        )
                        self.agent.model.set_system_prompt(prompt_text)
                    else:
                        self.agent.model.set_system_prompt(self.agent.system_prompt)
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Requirement classification failed: {e}, using default configuration")

    def apply_task_temperature(self, temperature: Optional[float]) -> None:
        """Apply the recommended sampling temperature to the current model based on the task nature (with range protection).

        The temperature only changes the current Agent's own platform instance (registry creates a new one each time), without affecting other Agents.
        """
        try:
            model = getattr(self.agent, "model", None)
            if model is None:
                return
            if temperature is None:
                return
            # Respect the temperature explicitly locked by the user in llm_config: explicit configuration takes priority over automatic adjustment
            try:
                from haijunbot.haijunbot_utils.config import get_llm_config

                pinned = get_llm_config(getattr(model, "platform_type", "normal")).get(
                    "temperature"
                )
            except Exception:
                pinned = None
            if pinned is not None:
                return
            # Range protection: reject obviously abnormal values, to avoid pushing sampling to extremes
            try:
                temp = float(temperature)
            except (TypeError, ValueError):
                return
            temp = min(max(temp, 0.1), 1.5)
            if not hasattr(model, "temperature"):
                return
            model.temperature = temp
            PrettyOutput.auto_print(f"🌡️ Adjusted sampling temperature based on task nature: {temp}")
        except Exception:
            # A temperature adjustment failure does not affect the main flow
            pass

    def create_temp_model(
        self, system_prompt: str = "", force_model_type: Optional[str] = None
    ) -> BasePlatform:
        """Create a temporary model instance for executing one-off tasks, to avoid polluting the main session.

        By default, it uses the same model configuration as the caller, but the model type can also be forced.

        Args:
            system_prompt: System prompt, optional. If the caller will set a conversation history containing a system
                           message via set_messages, there is no need to pass this parameter (set_messages will override the system prompt set here).
            force_model_type: The model type to force (smart/normal/cheap), optional.
                              If specified, a model of that type will be used instead of the current model type.
        """
        # Determine the model type to use
        if force_model_type:
            # Use the forced model type
            platform_registry = PlatformRegistry()
            if force_model_type == "smart":
                temp_model = platform_registry.get_smart_platform()
            elif force_model_type == "cheap":
                temp_model = platform_registry.get_cheap_platform()
            else:  # normal
                temp_model = platform_registry.get_normal_platform()
        else:
            # Use the same model configuration as the caller
            temp_model = PlatformRegistry().create_platform(
                self.agent.model.platform_type
            )

        if not temp_model:
            raise RuntimeError("Failed to create the temporary model.")

        if system_prompt:
            temp_model.set_system_prompt(system_prompt)
        temp_model.set_suppress_output(False)  # Disable output suppression to show the compression process
        return temp_model
