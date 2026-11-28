"""
Tool for generating holdout scenarios (reserved acceptance scenarios).

Purpose:
- Generate hidden acceptance scenarios for the dark factory pipeline, for independent evaluators to test the produced code.
- Generated scenarios are marked as "invisible to the coding side" and strictly isolated from the coding agent.

Parameters:
- feature (str): Feature description.
- count (int): Number of scenarios to generate (default 5, range 1-20).

Returns:
- success (bool)
- stdout (str): JSON text containing the scenario list (each with id/description/verification method/hidden flag)
- stderr (str)
"""

import json
from typing import Any
from typing import Dict
from typing import List


class HoldoutGeneratorTool:
    # File name must match the tool name for automatic registry loading
    name = "holdout_generator"
    description = "Generate holdout scenarios (reserved acceptance scenarios), marked as invisible to the coding side, for independent evaluators to test the output."
    parameters = {
        "type": "object",
        "properties": {
            "feature": {
                "type": "string",
                "description": "Feature description, used to generate targeted acceptance scenarios",
            },
            "count": {
                "type": "integer",
                "description": "Number of scenarios to generate (default 5, range 1-20)",
            },
        },
        "required": ["feature"],
    }

    # Scenario type templates, covering functional/boundary/exceptional/performance/security
    _SCENARIO_TEMPLATES = [
        "Verify the core functionality of {feature} works correctly with normal input",
        "Verify {feature} behaves correctly with boundary input (null/extreme values/maximum length)",
        "Verify {feature} reports errors gracefully without crashing on invalid input",
        "Verify the interface contract of {feature} (parameter types/return structure/error codes) conforms to the spec",
        "Verify {feature} maintains consistency under concurrent/repeated calls",
        "Verify the performance of {feature} meets spec constraints (response time/throughput)",
        "Verify the security of {feature} (no injection/unauthorized access/key leakage)",
        "Verify the compatibility of {feature} with existing modules, without introducing regressions",
    ]

    @staticmethod
    def check() -> bool:
        """Tool is always available (pure logic generation, no external dependencies)."""
        return True

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            feature = args.get("feature")
            if not feature or not isinstance(feature, str):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Parameter error: feature must be a non-empty string",
                }

            count = args.get("count", 5)
            if not isinstance(count, int):
                count = 5
            count = max(1, min(count, 20))

            scenarios: List[Dict[str, Any]] = []
            for i in range(count):
                template = self._SCENARIO_TEMPLATES[i % len(self._SCENARIO_TEMPLATES)]
                scenarios.append(
                    {
                        "id": i + 1,
                        "description": template.format(feature=feature),
                        "verification": "Executed by an independent evaluator agent, recording pass/fail",
                        "hidden": True,  # Invisible to the coding side
                    }
                )

            output = {
                "feature": feature,
                "count": len(scenarios),
                "hidden": True,
                "warning": "These scenarios are holdout scenarios and must not be seen by the coding agent. For independent evaluator use only.",
                "scenarios": scenarios,
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
                "stderr": f"holdout_generator execution error: {e}",
            }