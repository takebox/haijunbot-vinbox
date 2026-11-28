# -*- coding: utf-8 -*-
"""auto_select_rule tool module

Provides the functionality to automatically select and load rules based on the task description.
This tool receives a user intent string and outputs the content of the selected rules.
"""

from typing import Any, Dict

from haijunbot.haijunbot_utils.output import PrettyOutput


class AutoSelectRuleTool:
    """Automatically select and load rules based on the task description"""

    name = "auto_select_rule"
    description = (
        "Automatically select the most suitable rules (up to 5) based on the task description and load their content."
        "This tool analyzes the task intent and picks the most relevant ones from the available rules to load."
        "Suitable for scenarios that need to automatically match best practices and conventions by task type."
    )
    parameters = {
        "type": "object",
        "properties": {
            "task_description": {
                "type": "string",
                "description": "Task description or user intent string, used to match the most suitable rules",
            }
        },
        "required": ["task_description"],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform automatic rule selection and loading

        Args:
            args (Dict): Dictionary containing the task_description argument; RulesManager can be obtained via agent

        Returns:
            Dict[str, Any]: Dictionary containing success status, selected rule content, and error information
        """
        try:
            task_description = args.get("task_description", "").strip()
            if not task_description:
                return {"success": False, "stdout": "", "stderr": "Task description cannot be empty"}

            agent = args.get("agent")
            if not agent:
                return {"success": False, "stdout": "", "stderr": "Unable to obtain the agent instance"}

            rules_manager = getattr(agent, "rules_manager", None)
            if not rules_manager:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "agent has no rules_manager attribute",
                }

            # Use match_rules_to_task to support local + remote search
            selected_rules = rules_manager.match_rules_to_task(task_description)

            if not selected_rules:
                return {
                    "success": True,
                    "stdout": "No rules related to the task were found",
                    "stderr": "",
                    "selected_rules": [],
                }

            if selected_rules == ["__NO_RULES_NEEDED__"]:
                return {
                    "success": True,
                    "stdout": "The task is simple and can be completed without specific rules",
                    "stderr": "",
                    "selected_rules": [],
                    "no_rules_needed": True,
                }

            rule_contents = []
            for rule_name in selected_rules:
                # Use the load_rule() method to load the rule, which updates the loaded_rules state
                success = rules_manager.load_rule(rule_name)
                if success:
                    # Get the loaded rule content from the cache
                    rule_content = rules_manager._loaded_rules.get(rule_name)
                    if rule_content:
                        # Also provide the full path of the rule file, so it can later be loaded by path with the load_rule tool
                        rule_path = rules_manager.get_rule_file_path(rule_name)
                        rule_contents.append(
                            {
                                "name": rule_name,
                                "path": (
                                    rule_path
                                    if rule_path and rule_path != "--"
                                    else rule_name
                                ),
                                "content": rule_content,
                            }
                        )

            output_lines = [f"Selected {len(rule_contents)} rules for the task:", ""]
            for rule_info in rule_contents:
                output_lines.append(f"## Rule: {rule_info['name']}")
                output_lines.append(f"Rule file path: {rule_info['path']}")
                output_lines.append("")
                output_lines.append(rule_info["content"])
                output_lines.append("")
                output_lines.append("---")
                output_lines.append("")

            return {
                "success": True,
                "stdout": "\n".join(output_lines),
                "stderr": "",
                "selected_rules": [r["name"] for r in rule_contents],
                "rule_paths": [r["path"] for r in rule_contents],
                "rule_contents": rule_contents,
            }

        except Exception as e:
            PrettyOutput.auto_print(f"Automatic rule selection failed: {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Automatic rule selection failed: {str(e)}",
            }
