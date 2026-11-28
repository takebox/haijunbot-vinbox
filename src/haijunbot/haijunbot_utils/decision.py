# -*- coding: utf-8 -*-
"""Unified entry point for decision calls.

The project contains many decision scenarios of the form "give the model a batch of candidates + a task description, and let the model make a choice/score".
By default these scenarios go through their own existing flows (normal/cheap models + text protocol + regex parsing).

When a structured evaluation model (eval_llm in llm_groups) is configured in the model group, these scenarios
can be routed to that model instead, to obtain more stable structured output.

This module provides a unified entry point, avoiding the scattering of "whether an evaluation model is configured" checks across business code:

- get_eval_platform(): get the structured evaluation model instance, returning None when not configured
- decide(): use the evaluation model if present, otherwise execute the fallback, ensuring zero behavior change when not configured
"""

from typing import Any, Callable, Dict, Optional

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.config import is_eval_model_configured
from haijunbot.haijunbot_utils.output import PrettyOutput


def get_eval_platform() -> Optional[BasePlatform]:
    """Get the structured evaluation model instance.

    Returns None when eval_llm is not configured or its creation fails, and the caller falls back to the existing flow accordingly.

    Returns:
        Optional[BasePlatform]: The evaluation model instance, or None when not configured
    """
    if not is_eval_model_configured():
        return None
    try:
        registry = PlatformRegistry.get_global_platform_registry()
        return registry.get_eval_platform()
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Failed to create structured evaluation model, falling back to the existing flow: {e}")
        return None


def decide(
    prompt: str,
    fallback: Callable[[], Any],
    *,
    suppress_output: bool = True,
) -> Any:
    """Execute a single decision call.

    When a structured evaluation model is configured, use that model to execute the prompt and return its text response;
    otherwise call fallback to go through the existing flow.

    Parameters:
        prompt: The decision prompt
        fallback: The existing flow executed when no evaluation model is configured, returning any result
        suppress_output: Whether to suppress output when using the evaluation model (suppressed by default)

    Returns:
        Any: The evaluation model's text response (str), or the fallback's return value
    """
    platform = get_eval_platform()
    if platform is None:
        return fallback()

    try:
        platform.set_suppress_output(suppress_output)
        response = platform.chat_until_success(prompt).strip()
        if not response:
            PrettyOutput.auto_print("⚠️  Structured evaluation model returned empty, falling back to the existing flow")
            return fallback()
        return response
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Structured evaluation model call failed, falling back to the existing flow: {e}")
        return fallback()
    finally:
        try:
            platform.delete_chat()
        except Exception:
            pass


def decide_json(
    prompt: str,
    fallback: Callable[[], Any],
    *,
    suppress_output: bool = True,
) -> Any:
    """Execute a single decision call and parse the JSON result.

    Same as decide, but parses the model response into a JSON object; falls back to the existing flow on parse failure.

    Parameters:
        prompt: The decision prompt (should require the model to output JSON)
        fallback: The existing flow executed when no evaluation model is configured or parsing fails
        suppress_output: Whether to suppress output when using the evaluation model (suppressed by default)

    Returns:
        Any: The parsed JSON object, or the fallback's return value
    """
    import json

    from haijunbot.haijunbot_utils.utils import extract_json_from_text

    platform = get_eval_platform()
    if platform is None:
        return fallback()

    try:
        platform.set_suppress_output(suppress_output)
        response = platform.chat_until_success(prompt).strip()
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Structured evaluation model call failed, falling back to the existing flow: {e}")
        return fallback()
    finally:
        try:
            platform.delete_chat()
        except Exception:
            pass

    if not response:
        PrettyOutput.auto_print("⚠️  Structured evaluation model returned empty, falling back to the existing flow")
        return fallback()

    json_str, _ = extract_json_from_text(response)
    if not json_str:
        PrettyOutput.auto_print("⚠️  Structured evaluation model did not return valid JSON, falling back to the existing flow")
        return fallback()

    try:
        return json.loads(json_str)
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Failed to parse structured evaluation result, falling back to the existing flow: {e}")
        return fallback()


def decide_choice(
    task: str,
    candidates: Dict[str, str],
    fallback: Callable[[], Any],
    *,
    max_select: int = 3,
    min_confidence: float = 0.5,
) -> Any:
    """Select the several items from a batch of candidates most relevant to the task.

    Structured evaluation models (such as Jev) only accept the JSON protocol and return structured answers, and cannot directly consume
    natural-language prompts. This function is responsible for translating the "candidate list + task description" into a
    structured question that the model can understand, and then translating the answer back into a list of candidate IDs, so that decision scenarios can truly use the evaluation model.

    Implementation: construct a noul (yes/no) question for each candidate, obtain the relevance
    probability of all candidates in a single request, and then take the top max_select in descending order of probability.

    Parameters:
        task: The task description
        candidates: The candidate mapping {candidate ID: candidate description}; the ID is returned to the caller as-is
        fallback: The existing flow executed when no evaluation model is configured or the call fails
        max_select: The maximum number of candidates to return (default 3)
        min_confidence: The relevance probability threshold; candidates below it are not returned (default 0.5)

    Returns:
        Any: The selected list of candidate IDs (List[str]), or the fallback's return value
    """
    import json

    platform = get_eval_platform()
    if platform is None or not candidates:
        return fallback()

    # Construct a noul question for each candidate, using the candidate ID directly as the question ID
    questions: Dict[str, Any] = {}
    for cid, desc in candidates.items():
        questions[str(cid)] = {
            "type": "noul",
            "instructions": (
                f"Is the following candidate highly relevant to the task and should it be selected? Candidate description: {desc}"
            ),
        }

    payload = {
        "state": f"Task description: {task}",
        "questions": questions,
    }

    try:
        platform.set_suppress_output(True)
        response = platform.chat_until_success(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️  Structured evaluation model call failed, falling back to the existing flow: {e}")
        return fallback()
    finally:
        try:
            platform.delete_chat()
        except Exception:
            pass

    if not response:
        PrettyOutput.auto_print("⚠️  Structured evaluation model returned empty, falling back to the existing flow")
        return fallback()

    # Parse the noul probability of each candidate from the readable text
    scores = _parse_noul_scores(response)
    if not scores:
        PrettyOutput.auto_print("⚠️  Failed to parse structured evaluation result, falling back to the existing flow")
        return fallback()

    # Take the top max_select in descending order of probability, and filter out candidates below the threshold
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    picked = [cid for cid, score in ranked[:max_select] if score >= min_confidence]
    if not picked:
        PrettyOutput.auto_print("⚠️  Structured evaluation selected no candidates, falling back to the existing flow")
        return fallback()
    return picked


def _parse_noul_scores(response: str) -> Dict[str, float]:
    """Parse the noul probability of each question from Jev's readable answer text.

    The answer text looks like:
        - <candidate ID> [noul]: 0.96
        - <candidate ID> [noul]: 0.03

    Parameters:
        response: The readable answer text returned by Jev

    Returns:
        Dict[str, float]: {candidate ID: probability}, or an empty dictionary on parse failure
    """
    import re

    pattern = re.compile(r"^-\s*(.+?)\s*\[noul\]:\s*([0-9]*\.?[0-9]+)\s*$")
    scores: Dict[str, float] = {}
    for line in response.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        try:
            scores[match.group(1)] = float(match.group(2))
        except ValueError:
            continue
    return scores
