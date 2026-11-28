"""
Tool for validating the completeness of NLSpec (Natural Language Specification).

Purpose:
- Check whether an NLSpec contains the four required elements of the dark factory: Goal / Constraints / Interfaces / Non-goals.
- Return missing elements and hints to help write a qualified spec.

Parameters:
- spec (str): The NLSpec text to validate.

Returns:
- success (bool)
- stdout (str): JSON text containing the hit status of the four elements, missing items, and whether it is qualified
- stderr (str)
"""

import json
from typing import Any
from typing import Dict


class SpecValidatorTool:
    # File name must match the tool name for automatic registry loading
    name = "spec_validator"
    description = "Validate whether NLSpec (Natural Language Specification) contains the four elements: Goal/Constraints/Interfaces/Non-goals."
    parameters = {
        "type": "object",
        "properties": {
            "spec": {
                "type": "string",
                "description": "The NLSpec text to validate",
            },
        },
        "required": ["spec"],
    }

    # Keywords for the four elements (English), used for heuristic detection
    _KEYWORDS = {
        "Goal": ["goal", "objective", "purpose", "build", "implement", "create"],
        "Constraints": [
            "constraint",
            "limit",
            "must",
            "must not",
            "forbidden",
            "prohibited",
            "tech stack",
            "performance",
        ],
        "Interfaces": [
            "interface",
            "api",
            "function signature",
            "endpoint",
            "data structure",
            "input output",
            "return",
        ],
        "Non-goals": [
            "non-goal",
            "not do",
            "not include",
            "not implement",
            "out of scope",
        ],
    }


    @staticmethod
    def check() -> bool:
        """Tool is always available (pure text validation, no external dependencies)."""
        return True


    @staticmethod
    def _detect(text_lower: str, keywords: list) -> bool:
        """Detect whether the text hits any keyword."""
        return any(kw in text_lower for kw in keywords)


    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            spec = args.get("spec")
            if not spec or not isinstance(spec, str):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Parameter error: spec must be a non-empty string",
                }

            text_lower = spec.lower()
            results = {}
            missing = []
            for element, keywords in self._KEYWORDS.items():
                hit = self._detect(text_lower, keywords)
                results[element] = hit
                if not hit:
                    missing.append(element)


            valid = len(missing) == 0
            output = {
                "valid": valid,
                "elements": results,
                "missing": missing,
                "hint": (
                    "NLSpec is qualified, containing all four elements."
                    if valid
                    else f"NLSpec is incomplete, missing elements: {', '.join(missing)}. Please add the corresponding sections."
                ),
            }
            return {
                "success": True,
                "stdout": json.dumps(output, ensure_ascii=False, indent=2),
                "stderr": "",
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"spec_validator execution error: {e}",
            }