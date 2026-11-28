"""
Tool for evaluating gate calculation.

Purpose:
- Based on the pass/fail results of each holdout scenario, calculate gate metrics: scenario pass rate, false positive rate, human override rate.
- Determine whether the gate standard is met (scenario pass rate >= 90%).

Parameters:
- results (List[Dict]): Evaluation results for each scenario, in the form [{"id": 1, "pass": true}, ...].
- false_positives (int, optional): Number of scenarios that the evaluator incorrectly judged as passing but actually had issues.
- human_overrides (int, optional): Number of times humans overrode the evaluator's judgment.
- total_human_reviews (int, optional): Total number of human reviews (used to calculate override rate).

Returns:
- success (bool)
- stdout (str): JSON text containing each metric, whether the standard is met, and recommendations
- stderr (str)
"""

import json
from typing import Any
from typing import Dict


class GateCalculatorTool:
    # File name must match the tool name for automatic registry loading
    name = "gate_calculator"
    description = "Calculate dark factory evaluation gate metrics (scenario pass rate / false positive rate / human override rate) and determine whether the standard is met (>=90%)."
    parameters = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {"type": "object"},
                "description": 'Evaluation results for each scenario, in the form [{"id": 1, "pass": true}, ...]',
            },
            "false_positives": {
                "type": "integer",
                "description": "Number of scenarios that the evaluator incorrectly judged as passing but actually had issues (default 0)",
            },
            "human_overrides": {
                "type": "integer",
                "description": "Number of times humans overrode the evaluator's judgment (default 0)",
            },
            "total_human_reviews": {
                "type": "integer",
                "description": "Total number of human reviews (default 0, used to calculate override rate)",
            },
        },
        "required": ["results"],
    }

    _PASS_THRESHOLD = 0.9  # Scenario pass rate gate standard

    @staticmethod
    def check() -> bool:
        """Tool is always available (pure calculation, no external dependencies)."""
        return True

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            results = args.get("results")
            if not isinstance(results, list) or not results:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": 'Parameter error: results must be a non-empty list, in the form [{"id": 1, "pass": true}]',
                }

            total = len(results)
            passed = sum(1 for r in results if isinstance(r, dict) and r.get("pass"))
            pass_rate = passed / total

            false_positives = args.get("false_positives", 0) or 0
            human_overrides = args.get("human_overrides", 0) or 0
            total_human_reviews = args.get("total_human_reviews", 0) or 0

            false_positive_rate = false_positives / passed if passed > 0 else 0.0
            human_override_rate = (
                human_overrides / total_human_reviews
                if total_human_reviews > 0
                else None
            )

            meets_threshold = pass_rate >= self._PASS_THRESHOLD
            # When false positive rate is too high or human override rate is too high, recommend manual intervention even if pass rate meets the standard
            caution = false_positive_rate >= 0.05 or (
                human_override_rate is not None and human_override_rate >= 0.10
            )

            if meets_threshold and not caution:
                decision = "Recommend passing the gate (scenario pass rate meets the standard with no high false positive/high override rate)."
            elif meets_threshold and caution:
                decision = (
                    "Pass rate meets the standard, but there is a high false positive rate or high human override rate. Recommend manual review."
                )
            else:
                decision = "Gate standard not met (scenario pass rate < 90%), recommend retry or manual review."
                if not meets_threshold:
                    decision += " Refer to holdout_discipline rules: <90% is considered not meeting the standard."

            output = {
                "total_scenarios": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round(pass_rate, 4),
                "pass_threshold": self._PASS_THRESHOLD,
                "meets_threshold": meets_threshold,
                "false_positive_rate": round(false_positive_rate, 4),
                "human_override_rate": (
                    round(human_override_rate, 4)
                    if human_override_rate is not None
                    else None
                ),
                "caution": caution,
                "decision": decision,
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
                "stderr": f"gate_calculator execution error: {e}",
            }