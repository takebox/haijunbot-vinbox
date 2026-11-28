# -*- coding: utf-8 -*-
"""Jinja2 template rendering utility module

Provides unified jinja2 template rendering functionality, supporting the use of built-in variables within templates.
The built-in variables include:
- current_dir: current working directory
- script_dir: the directory where the script resides
- haijunbot_data_dir: HaijunBot data directory
- haijunbot_src_dir: HaijunBot source directory
- git_root_dir: Git root directory
- rule_file_dir: the directory where the rule file resides
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Optional

from haijunbot.haijunbot_utils.exception_utils import save_exception
import jinja2
from jinja2 import TemplateError, TemplateSyntaxError

from haijunbot.haijunbot_utils.output import PrettyOutput


def render_rule_template(
    rule_content: str, rule_file_dir: str, file_path: str | None = None
) -> str:
    """Render a rule template using jinja2

    Parameters:
        rule_content: The raw content of the rule
        rule_file_dir: The directory where the rule file resides
        file_path: The full path of the rule file (optional, used to print a load-success message and add a path comment)

    Returns:
        str: The rendered content, or the original content if rendering fails
    """
    if not rule_content:
        return rule_content

    # Build the jinja2 context variables
    context: dict[str, Any] = {
        "current_dir": Path.cwd().as_posix(),
        "script_dir": Path(__file__).parent.as_posix(),  # The directory where the current script resides
        "haijunbot_data_dir": _get_haijunbot_data_dir(),
        "haijunbot_src_dir": get_haijunbot_src_dir(),
        "git_root_dir": get_git_root(),
        "rule_file_dir": rule_file_dir,  # The directory where the current rule file resides
    }

    # If file_path is provided, add rule_file_path to the context
    if file_path:
        context["rule_file_path"] = (
            os.path.abspath(file_path) if not os.path.isabs(file_path) else file_path
        )

    # Render the template using jinja2
    try:
        template = jinja2.Template(rule_content)
        result = template.render(**context).strip()
        # Rendering succeeded, print a load-success message
        if file_path:
            rule_name = Path(file_path).stem
            PrettyOutput.auto_print(f"✅ Successfully loaded {rule_name} rule")
        return result
    except (TemplateError, TemplateSyntaxError):
        # Return the original content on rendering failure (backward compatible)
        return rule_content.strip()
    except Exception:
        # Other exceptions (such as memory errors) also return the original content
        return rule_content.strip()


def render_main_config_template(config_content: str, config_file_dir: str) -> str:
    """Render the main configuration file template using jinja2

    Parameters:
        config_content: The raw content of the configuration file
        config_file_dir: The directory where the configuration file resides

    Returns:
        str: The rendered content, or the original content if rendering fails
    """
    if not config_content:
        return config_content

    # Build the jinja2 context variables
    context: dict[str, Any] = {
        "current_dir": Path.cwd().as_posix(),
        "script_dir": Path(__file__).parent.as_posix(),
        "haijunbot_data_dir": _get_haijunbot_data_dir(),
        "haijunbot_src_dir": get_haijunbot_src_dir(),
        "git_root_dir": get_git_root(),
        "config_file_dir": config_file_dir,
    }

    # Render the template using jinja2
    try:
        template = jinja2.Template(config_content)
        result = template.render(**context).strip()
        return result
    except (TemplateError, TemplateSyntaxError):
        # Return the original content on rendering failure (backward compatible)
        return config_content.strip()
    except Exception:
        # Other exceptions also return the original content
        return config_content.strip()


def render_plugin_config_template(config_content: str, plugin_dir: str) -> str:
    """Render a plugin configuration template using jinja2

    Parameters:
        config_content: The raw plugin configuration content
        plugin_dir: The plugin directory path

    Returns:
        str: The rendered content, or the original content if rendering fails
    """
    if not config_content:
        return config_content

    # Build the jinja2 context variables
    context: dict[str, Any] = {
        "plugin_dir": plugin_dir,  # The current plugin directory
    }

    # Render the template using jinja2
    try:
        template = jinja2.Template(config_content)
        result = template.render(**context).strip()
        return result
    except (TemplateError, TemplateSyntaxError):
        # Return the original content on rendering failure (backward compatible)
        return config_content.strip()
    except Exception:
        # Other exceptions (such as memory errors) also return the original content
        return config_content.strip()


def get_git_root() -> str:
    """Get the git root directory

    If the current directory is not in a git repository, the current working directory is returned as a fallback.

    Returns:
        str: The absolute path of the git root directory (or the current working directory if not in a git repository)
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    # Not in a git repository, return the current working directory
    return os.getcwd()


def is_haijunbot_git_repo() -> bool:
    """Determine whether the current HaijunBot source is a Git repository

    Returns:
        bool: True if it is a Git repository, otherwise False
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def get_haijunbot_branch() -> Optional[str]:
    """Get the current Git branch name of the HaijunBot source

    Returns:
        Optional[str]: The current branch name, or None if not in a Git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        return None
    except (FileNotFoundError, subprocess.SubprocessError):
        return None


def checkout_haijunbot_branch(branch_name: str) -> tuple[bool, str]:
    """Switch the HaijunBot source to the specified branch or Tag

    Parameters:
        branch_name: The branch name or Tag name

    Returns:
        tuple[bool, str]: (True on successful switch, False on failure, error details)
    """
    try:
        # Get the HaijunBot source directory
        src_dir = get_haijunbot_src_dir()

        # Execute the git checkout command
        result = subprocess.run(
            ["git", "checkout", branch_name],
            cwd=src_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            return True, ""
        error_msg = (
            result.stderr.strip()
            or result.stdout.strip()
            or f"git checkout {branch_name} failed"
        )
        return False, error_msg
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        return False, str(e)


def pull_haijunbot_code() -> tuple[bool, str]:
    """Pull the latest updates of the HaijunBot source

    Returns:
        tuple[bool, str]: (True on successful pull, False on failure, error details)
    """
    try:
        # Get the HaijunBot source directory
        src_dir = get_haijunbot_src_dir()

        PrettyOutput.auto_print("🔄 Pulling HaijunBot source updates...")

        # Execute the git pull command
        result = subprocess.run(
            ["git", "pull"],
            cwd=src_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            PrettyOutput.auto_print("✅ HaijunBot source pulled successfully")
            return True, ""
        else:
            error_msg = (
                result.stderr.strip() or result.stdout.strip() or "git pull failed"
            )
            PrettyOutput.auto_print(f"❌ Failed to pull HaijunBot source: {error_msg}")
            return False, error_msg
    except (FileNotFoundError, subprocess.SubprocessError) as e:
        PrettyOutput.auto_print(f"❌ Failed to pull HaijunBot source: {str(e)}")
        return False, str(e)


def get_haijunbot_src_dir() -> str:
    """Get the haijunbot source directory

    Returns:
        str: The absolute path of the haijunbot source directory
    """
    # Locate the project root directory upward from the current file location
    # src/haijunbot/haijunbot_utils/template_utils.py -> project root directory
    return str(Path(__file__).parent.parent.parent.parent.resolve())


def _get_builtin_dir() -> Path | None:
    """Get the builtin directory path

    This function attempts to find the builtin directory from multiple locations:
    1. From the installed package location (if installed using a tool such as uv tool install)
    2. From the source location (development environment)

    Returns:
        Path: The path of the builtin directory, or None if not found
    """
    # Method 1: Try to find the builtin directory upward from the current file location
    # This works for development environments and certain installation methods
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        builtin_dir = parent / "builtin"
        if builtin_dir.exists() and builtin_dir.is_dir():
            return builtin_dir

    # Method 2: Try to find it from the haijunbot package installation location
    # If uv tool install is used, builtin may be installed into the package data directory
    try:
        import importlib.resources

        # Try to find the builtin directory from the haijunbot package
        try:
            # Check whether builtin exists as package data
            with importlib.resources.path("haijunbot", "__init__.py") as haijunbot_init:
                haijunbot_pkg_dir = haijunbot_init.parent
                # Try to find builtin in the parent directory of the package directory
                for parent in haijunbot_pkg_dir.parents:
                    builtin_dir = parent / "builtin"
                    if builtin_dir.exists() and builtin_dir.is_dir():
                        return builtin_dir
        except (ImportError, ModuleNotFoundError, TypeError):
            pass
    except ImportError:
        pass

    # Method 3: Try to find it from the project root directory (via git or upward traversal)
    try:
        git_root = get_git_root()
        if git_root:
            builtin_dir = Path(git_root) / "builtin"
            if builtin_dir.exists() and builtin_dir.is_dir():
                return builtin_dir
    except Exception as e:
        save_exception(
            e, module="haijunbot_utils.template_utils", function="_get_builtin_dir"
        )
        pass

    return None


def _get_haijunbot_data_dir() -> str:
    """Get the haijunbot data directory

    Returns:
        str: The haijunbot data directory path
    """
    try:
        from haijunbot.haijunbot_utils.config import get_data_dir

        return get_data_dir()
    except ImportError:
        # If the import fails, return the default path
        return os.path.expanduser("~/.haijunbot")
