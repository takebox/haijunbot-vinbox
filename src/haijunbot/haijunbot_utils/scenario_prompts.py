# -*- coding: utf-8 -*-
"""Common module for scenario prompts

Provides scenario classification, difficulty assessment, and system prompt loading.
Supports loading from both the builtin directory and the data directory (~/.haijunbot/prompts/),
where user extension files can override builtin files with the same name.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml  # type: ignore[import-untyped]

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_platform.content_types import ContentBlock
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.config import get_data_dir


# builtin prompt root directory (4 levels up from haijunbot_utils to reach the project root)
_BUILTIN_PROMPTS_ROOT = (
    Path(__file__).parent.parent.parent.parent / "builtin" / "prompts"
)


def _get_prompt_dirs(scenario_subdir: str) -> List[Path]:
    """Get the list of prompt file directories (in descending order of priority)

    The data directory has higher priority than the builtin directory, so user extension files can override built-in files.

    Parameters:
        scenario_subdir: The scenario subdirectory name, such as "agent_system" or "code_agent_system"

    Returns:
        List[Path]: A list of directory paths, in descending order of priority
    """
    dirs = []
    # Data directory (user extensions, high priority)
    data_dir = Path(get_data_dir()) / "prompts" / scenario_subdir
    if data_dir.is_dir():
        dirs.append(data_dir)
    # builtin directory (built-in, low priority)
    builtin_dir = _BUILTIN_PROMPTS_ROOT / scenario_subdir
    if builtin_dir.is_dir():
        dirs.append(builtin_dir)
    return dirs


def _load_scenario_types(scenario_subdir: str) -> Dict[str, Dict[str, str]]:
    """Load scenario type definitions from the YAML front matter of md files

    Loaded from the data directory with priority, and files with the same name override builtin.

    Parameters:
        scenario_subdir: The scenario subdirectory name

    Returns:
        Dict[str, Dict[str, str]]: The scenario type dictionary
    """
    prompt_dirs = _get_prompt_dirs(scenario_subdir)
    if not prompt_dirs:
        raise FileNotFoundError(
            f"Prompt directory does not exist: {scenario_subdir} was not found in either the builtin or data directories"
        )

    scenarios = {}

    # Load in ascending order of priority (builtin first, data directory after),
    # so that files with the same name in the data directory override those in builtin
    for prompt_dir in reversed(prompt_dirs):
        try:
            for md_file in prompt_dir.glob("*.md"):
                if md_file.name.lower() == "readme.md":
                    continue

                scenario_id = md_file.stem

                try:
                    with open(md_file, "r", encoding="utf-8") as f:
                        content = f.read()

                    front_matter = None
                    if content.startswith("---"):
                        end_marker = content.find("\n---", 4)
                        if end_marker != -1:
                            front_matter_text = content[4:end_marker]
                            front_matter = yaml.safe_load(front_matter_text)

                    if front_matter is None:
                        raise ValueError(
                            f"File '{md_file.name}' is missing the YAML front matter or its format is incorrect"
                        )

                    if not isinstance(front_matter, dict):
                        raise ValueError(
                            f"The front matter of file '{md_file.name}' is not a valid dictionary"
                        )

                    if "name" not in front_matter or "description" not in front_matter:
                        raise ValueError(
                            f"The front matter of file '{md_file.name}' is missing the required field 'name' or 'description'"
                        )

                    scenarios[scenario_id] = {
                        "name": front_matter["name"],
                        "description": front_matter["description"],
                    }

                except yaml.YAMLError as e:
                    raise IOError(
                        f"Failed to parse the YAML front matter of file '{md_file.name}': {e}"
                    ) from e
                except ValueError:
                    raise
                except Exception as e:
                    raise IOError(f"Failed to load file '{md_file.name}': {e}") from e
        except (FileNotFoundError, ValueError):
            raise
        except Exception as e:
            raise IOError(f"Failed to load scenario type definitions: {e}") from e

    if not scenarios:
        raise FileNotFoundError(f"No valid prompt files found in directory {prompt_dirs}")

    return scenarios


def _get_scenario_types(scenario_subdir: str) -> Dict[str, str]:
    """Get the scenario type name dictionary

    Parameters:
        scenario_subdir: The scenario subdirectory name

    Returns:
        Dict[str, str]: {scenario_id: scenario_name}
    """
    scenarios = _load_scenario_types(scenario_subdir)
    return {
        scenario_id: scenario_info["name"]
        for scenario_id, scenario_info in scenarios.items()
    }


def _load_prompt_from_file(scenario: str, scenario_subdir: str) -> str:
    """Load a prompt from a file

    Loaded from the data directory with priority, and files with the same name override builtin.

    Parameters:
        scenario: The scenario type
        scenario_subdir: The scenario subdirectory name

    Returns:
        str: The prompt content (excluding the YAML front matter)
    """
    prompt_dirs = _get_prompt_dirs(scenario_subdir)

    # Search in descending order of priority (data directory first)
    for prompt_dir in prompt_dirs:
        prompt_file = prompt_dir / f"{scenario}.md"
        if prompt_file.exists():
            try:
                with open(prompt_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Skip the YAML front matter
                if content.startswith("---"):
                    end_marker = content.find("\n---", 4)
                    if end_marker != -1:
                        content = content[end_marker + 4 :]

                content = content.strip()
                if not content:
                    raise ValueError(f"Prompt file is empty: {prompt_file}")
                return content
            except Exception as e:
                raise IOError(f"Failed to load prompt file ({prompt_file}): {e}") from e

    raise FileNotFoundError(
        f"Prompt file does not exist: {scenario}.md. Please ensure the file exists in the {prompt_dirs} directory."
    )


def classify_user_request(
    user_input: Union[str, List[ContentBlock]],
    scenario_subdir: str,
    default_scenario_name: str = "General task",
    classification_context: str = "scenario type",
    difficulty_descriptions: Dict[str, str] | None = None,
) -> Tuple[str, str, float]:
    """Use normal_llm to classify the user's request

    Parameters:
        user_input: The user's request description
        scenario_subdir: The scenario subdirectory name
        default_scenario_name: The default scenario name (used for display)
        classification_context: The classification context description (such as "scenario type" or "development scenario type")
        difficulty_descriptions: The difficulty level description dictionary

    Returns:
        Tuple[str, str, float]: (scenario type, difficulty level, recommended sampling temperature)
    """
    # Task nature → temperature tier (only let the classification model choose the tier; the numeric values are mapped in code with range protection).
    # The tier is based on "whether determinism or creativity is needed" rather than difficulty: code changes/bug fixes lean low, creativity/openness lean high.
    temperature_descriptions = {
        "low": "Requires precision, rule-following, and predictable results: precise edits, bug fixes, refactoring, changes that strictly follow specifications/rules",
        "medium": "Routine multi-step tasks, general development and Q&A (default)",
        "high": "Requires creativity and divergence: creative writing, copy polishing, brainstorming, open-ended solution exploration",
    }
    # Tier → sampling temperature (deliberately avoiding too-low values, to avoid falling into large repetitive passages)
    temperature_map = {"low": 0.5, "medium": 0.7, "high": 1.0}

    if difficulty_descriptions is None:
        difficulty_descriptions = {
            "easy": "Simple Q&A, single-step operations, clear small tasks (for those involving code changes, the difficulty is at least medium and must not be rated easy)",
            "medium": "Requires multi-step operations, must understand context, has a certain degree of complexity",
            "hard": "Requires deep analysis, multi-dimensional synthesis, relies on specialized knowledge and deep thought",
        }

    # If user_input is multimodal content, extract the text within it
    if isinstance(user_input, list):
        text_parts = []
        for block in user_input:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        user_input = "\n".join(text_parts) if text_parts else "[Multimodal content]"

    # Prefer using the structured evaluation model (eval_llm, such as Jev) for classification: it only accepts the JSON protocol
    # and returns structured answers, and cannot consume natural-language prompts, so a dedicated protocol conversion is used;
    # when no evaluation model is configured or the call fails, fall back to the cheap/normal text model flow.
    eval_result = _classify_with_eval_model(
        user_input,
        scenario_subdir,
        classification_context,
        difficulty_descriptions,
        temperature_descriptions,
        temperature_map,
    )
    if eval_result is not None:
        scenario, difficulty, temperature = eval_result
        _print_classification_result(
            scenario_subdir, scenario, difficulty, temperature, default_scenario_name
        )
        return scenario, difficulty, temperature

    try:
        # When eval is not configured: prefer the cheap tier to save cost; fall back to normal when cheap is not configured
        registry = PlatformRegistry()
        try:
            platform = registry.get_cheap_platform()
        except Exception:
            platform = registry.get_normal_platform()
        platform.set_suppress_output(False)

        scenarios = _load_scenario_types(scenario_subdir)

        scenarios_list = []
        scenario_ids = []
        for idx, (scenario_id, scenario_info) in enumerate(scenarios.items(), 1):
            scenario_name = scenario_info["name"]
            scenario_desc = scenario_info["description"]
            scenarios_list.append(
                f"{idx}. {scenario_id} ({scenario_name}): {scenario_desc}"
            )
            scenario_ids.append(scenario_id)

        scenarios_text = "\n".join(scenarios_list)

        difficulty_text = "\n".join(
            f"- {k} ({'Easy' if k == 'easy' else 'Medium' if k == 'medium' else 'Hard'}): {v}"
            for k, v in difficulty_descriptions.items()
        )

        temperature_text = "\n".join(
            f"- {k} ({'Precise' if k == 'low' else 'Balanced' if k == 'medium' else 'Creative'}): {v}"
            for k, v in temperature_descriptions.items()
        )

        classification_prompt = f"""Analyze the user's request, determine which {classification_context} it belongs to, assess the task's difficulty, and choose the required temperature tier.

The user's request:
{user_input}

Available scenarios:
{scenarios_text}

Difficulty levels:
{difficulty_text}

Required temperature tier (chosen based on task nature rather than difficulty):
{temperature_text}

Please answer in the following format (only these three lines, without mixing in any other content):
scenario: <scenario>
difficulty: <difficulty>
temperature: <tier>

If the scenario is hard to determine, return default for scenario.
If the difficulty is hard to determine, return medium for difficulty.
If the temperature is hard to determine, return medium for temperature.
"""

        response = platform.chat_until_success(classification_prompt)
        response = response.strip().lower()

        scenario = "default"
        difficulty = "medium"
        temperature = 0.7

        # Get the current scenario type list for validation
        current_scenario_types = _get_scenario_types(scenario_subdir)

        lines = response.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("scenario:"):
                scenario_value = line.split(":", 1)[1].strip()
                for scenario_type in current_scenario_types.keys():
                    if (
                        scenario_type in scenario_value
                        or scenario_value == scenario_type
                    ):
                        scenario = scenario_type
                        break
            elif line.startswith("difficulty:"):
                difficulty_value = line.split(":", 1)[1].strip()
                if difficulty_value in ["easy", "medium", "hard"]:
                    difficulty = difficulty_value
            elif line.startswith("temperature:"):
                temperature_value = line.split(":", 1)[1].strip()
                if temperature_value in temperature_map:
                    temperature = temperature_map[temperature_value]

        _print_classification_result(
            scenario_subdir, scenario, difficulty, temperature, default_scenario_name
        )
        return scenario, difficulty, temperature

    except Exception:
        PrettyOutput.auto_print("⚠")
        return "default", "medium", 0.7


def _print_classification_result(
    scenario_subdir: str,
    scenario: str,
    difficulty: str,
    temperature: float,
    default_scenario_name: str,
) -> None:
    """Print the request classification result (scenario/difficulty/temperature).

    Parameters:
        scenario_subdir: The scenario subdirectory name
        scenario: The scenario type ID
        difficulty: The difficulty level (easy/medium/hard)
        temperature: The sampling temperature value
        default_scenario_name: The default scenario name (used for display)
    """
    try:
        current_scenario_types = _get_scenario_types(scenario_subdir)
    except Exception:
        current_scenario_types = {}
    difficulty_display = {"easy": "Easy", "medium": "Medium", "hard": "Hard"}.get(
        difficulty, difficulty
    )
    temperature_display = {0.5: "Precise", 0.7: "Balanced", 1.0: "Creative"}.get(
        temperature, temperature
    )
    PrettyOutput.auto_print(
        f"📋 Request classification result: {current_scenario_types.get(scenario, default_scenario_name)} ({scenario}) | Difficulty: {difficulty_display} ({difficulty}) | Temperature: {temperature_display} ({temperature})"
    )


def _classify_with_eval_model(
    user_input: str,
    scenario_subdir: str,
    classification_context: str,
    difficulty_descriptions: Dict[str, str],
    temperature_descriptions: Dict[str, str],
    temperature_map: Dict[str, float],
) -> Optional[Tuple[str, str, float]]:
    """Use the structured evaluation model (eval_llm, such as Jev) to classify the user's request.

    The structured evaluation model only accepts the JSON protocol (state + questions) and cannot consume natural-language
    prompts, so here "scenario/difficulty/temperature" is translated into three choice questions, and then its returned
    readable answer text is parsed. When no evaluation model is configured, the call fails, or parsing fails, None is returned, and the caller
    falls back to the text model flow.

    Parameters:
        user_input: The user's request description (already converted to plain text)
        scenario_subdir: The scenario subdirectory name
        classification_context: The classification context description
        difficulty_descriptions: The difficulty level description dictionary
        temperature_descriptions: The temperature tier description dictionary
        temperature_map: The temperature tier → numeric value mapping

    Returns:
        Optional[Tuple[str, str, float]]: (scenario type, difficulty level, sampling temperature),
        or None when no evaluation model is configured or on failure
    """
    from haijunbot.haijunbot_utils.decision import get_eval_platform

    platform = get_eval_platform()
    if platform is None:
        return None

    try:
        scenarios = _load_scenario_types(scenario_subdir)
        current_scenario_types = {
            scenario_id: scenario_info["name"]
            for scenario_id, scenario_info in scenarios.items()
        }

        # Scenario candidates: use scenario_id as the criteria key, with the name + description as the explanation
        scenario_criteria: Dict[str, str] = {}
        for scenario_id, scenario_info in scenarios.items():
            scenario_criteria[scenario_id] = (
                f"{scenario_info['name']}: {scenario_info['description']}"
            )

        # Difficulty candidates: easy/medium/hard
        difficulty_criteria = {
            k: f"{'Easy' if k == 'easy' else 'Medium' if k == 'medium' else 'Hard'}: {v}"
            for k, v in difficulty_descriptions.items()
        }

        # Temperature tier candidates: low/medium/high
        temperature_criteria = {
            k: f"{'Precise' if k == 'low' else 'Balanced' if k == 'medium' else 'Creative'}: {v}"
            for k, v in temperature_descriptions.items()
        }

        payload = {
            "state": f"The user's request:\n{user_input}",
            "questions": {
                "scenario": {
                    "type": "choice",
                    "instructions": (
                        f"Determine which {classification_context} the user's request belongs to. "
                        "If it is hard to determine, choose default."
                    ),
                    "criteria": scenario_criteria,
                },
                "difficulty": {
                    "type": "choice",
                    "instructions": "Assess the difficulty level of this task. If it is hard to determine, choose medium.",
                    "criteria": difficulty_criteria,
                },
                "temperature": {
                    "type": "choice",
                    "instructions": (
                        "Based on the task nature (whether precision or creativity is needed, rather than difficulty), "
                        "choose the required sampling temperature tier. If it is hard to determine, choose medium."
                    ),
                    "criteria": temperature_criteria,
                },
            },
        }

        import json

        platform.set_suppress_output(True)
        try:
            response = platform.chat_until_success(
                json.dumps(payload, ensure_ascii=False)
            )
        finally:
            try:
                platform.delete_chat()
            except Exception:
                pass

        if not response:
            PrettyOutput.auto_print("⚠️ Structured evaluation model returned empty, falling back to text model classification")
            return None

        answers = _parse_choice_answers(response)
        if not answers:
            PrettyOutput.auto_print("⚠️ Failed to parse the structured evaluation result, falling back to text model classification")
            return None

        scenario = "default"
        scenario_value = answers.get("scenario", "")
        for scenario_type in current_scenario_types.keys():
            if scenario_type in scenario_value or scenario_value == scenario_type:
                scenario = scenario_type
                break

        difficulty = "medium"
        difficulty_value = answers.get("difficulty", "")
        if difficulty_value in ("easy", "medium", "hard"):
            difficulty = difficulty_value

        temperature = 0.7
        temperature_value = answers.get("temperature", "")
        if temperature_value in temperature_map:
            temperature = temperature_map[temperature_value]

        return scenario, difficulty, temperature
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Structured evaluation model classification failed, falling back to text model classification: {e}")
        return None


def _parse_choice_answers(response: str) -> Dict[str, str]:
    """Parse the value of each choice question from the structured evaluation model's readable answer text.

    The answer text looks like:
        - scenario [choice]: general development
        - difficulty [choice]: medium
        - temperature [choice]: low

    Parameters:
        response: The readable answer text returned by the structured evaluation model

    Returns:
        Dict[str, str]: {question ID: option value}, or an empty dictionary on parse failure
    """
    import re

    pattern = re.compile(r"^-\s*(.+?)\s*\[choice\]:\s*(.+?)\s*$")
    answers: Dict[str, str] = {}
    for line in response.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        answers[match.group(1)] = match.group(2)
    return answers


def _front_matter_dict(
    prompt_dirs: List[Path], scenario: str
) -> Optional[Dict[str, Any]]:
    """Read the first existing scenario file and parse its front matter

    Used to detect whether a scenario file declares inheritance of the shared core of default (inherit_core: true).

    Parameters:
        prompt_dirs: The list of prompt directories (in descending order of priority)
        scenario: The scenario file name (without the .md suffix)

    Returns:
        Optional[Dict]: The front matter dictionary; returns None if the file does not exist or parsing fails
    """
    for prompt_dir in prompt_dirs:
        prompt_file = prompt_dir / f"{scenario}.md"
        if prompt_file.exists():
            try:
                content = prompt_file.read_text(encoding="utf-8")
                if content.startswith("---"):
                    end_marker = content.find("\n---", 4)
                    if end_marker != -1:
                        front_matter = yaml.safe_load(content[4:end_marker])
                        if isinstance(front_matter, dict):
                            return front_matter
            except Exception:
                pass
            return {}
    return None


def get_system_prompt(
    scenario: str = "default", scenario_subdir: str = "agent_system"
) -> str:
    """Get the corresponding system prompt according to the scenario type

    - Scenario files that do not declare inheritance: return as-is (backward compatible, user-defined files are unaffected).
    - Scenario files that declare ``inherit_core: true``: return "scenario body + shared core of the default scenario",
      so that common paragraphs are maintained in only one place (default), avoiding copy drift across scenarios.

    Parameters:
        scenario: The scenario type
        scenario_subdir: The scenario subdirectory name

    Returns:
        str: The complete system prompt for the corresponding scenario
    """
    content = _load_prompt_from_file(scenario, scenario_subdir)
    if scenario == "default":
        return content

    prompt_dirs = _get_prompt_dirs(scenario_subdir)
    front_matter = _front_matter_dict(prompt_dirs, scenario)
    if not (front_matter and front_matter.get("inherit_core", False)):
        return content

    # The shared core starts from the core_marker section of the default body (see the default file's front matter).
    # When there is no core_marker, it degrades to taking the first "## " section of the default body.
    base = _load_prompt_from_file("default", scenario_subdir)
    default_fm = _front_matter_dict(prompt_dirs, "default") or {}
    marker = default_fm.get("core_marker")
    if marker and marker in base:
        core = base[base.find(marker) :]
    else:
        idx = base.find("\n## ")
        core = base[idx + 1 :] if idx != -1 else base
    return content.rstrip() + "\n\n" + core
