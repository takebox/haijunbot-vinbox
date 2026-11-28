# -*- coding: utf-8 -*-
"""load_rule tool module

Provides the functionality to read rule files and render jinja2 templates.
Supported built-in variables:
- current_dir: Current working directory
- haijunbot_data_dir: HaijunBot data directory
- haijunbot_src_dir: HaijunBot source directory
- git_root_dir: Git root directory
- rule_file_dir: Directory containing the rule file
"""

import os
from typing import Any, Dict

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.template_utils import render_rule_template


class LoadRuleTool:
    """Load a rule file and render the jinja2 template"""

    name = "load_rule"
    description = (
        "Read the contents of a rule file and render its template variables with jinja2."
        "Supported variables: current_dir, git_root_dir, haijunbot_src_dir, haijunbot_data_dir, rule_file_dir."
        "Use the 'hri' command to view the full list of rules."
    )
    parameters = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Rule file path (supports relative and absolute paths)",
            }
        },
        "required": ["file_path"],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute rule file loading and rendering

        Args:
            args (Dict): Dictionary containing the file_path argument

        Returns:
            Dict[str, Any]: Dictionary containing success status, rendered content, and error information
        """
        try:
            # Get the file path
            file_path = args.get("file_path", "").strip()
            if not file_path:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "File path cannot be empty",
                }

            # Expand the path and get the absolute path
            expanded_path = os.path.expanduser(file_path)
            abs_path = os.path.abspath(expanded_path)

            # Check whether the file exists
            if not os.path.exists(abs_path):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"File does not exist: {abs_path}",
                }

            # Check whether it is a file
            if not os.path.isfile(abs_path):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Path is not a file: {abs_path}",
                }

            # Read the file contents
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if not content:
                return {
                    "success": True,
                    "stdout": f"File {abs_path} is empty",
                    "stderr": "",
                }

            # Get the directory containing the file
            file_dir = os.path.dirname(abs_path)

            # Render the template
            rendered_content = render_rule_template(content, file_dir, abs_path)

            # Return the rendered result
            return {
                "success": True,
                "stdout": rendered_content,
                "stderr": "",
            }

        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Failed to load rule file: {str(e)}",
            }
