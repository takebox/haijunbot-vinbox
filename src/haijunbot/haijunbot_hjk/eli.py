# -*- coding: utf-8 -*-
"""HaijunBot Check - hjk ELI command interface

Provides a Execution Line Interface (ELI) for checking the installation status of system tools.
"""

import sys
import subprocess
import json
from typing import Optional

import typer
from typer import confirm

from haijunbot.haijunbot_hjk.core import ToolChecker
from haijunbot.haijunbot_utils.output import PrettyOutput

# Create the typer application
app = typer.Typer(help="HaijunBot Check - Check the installation status of system tools and provide friendly installation suggestions")


def _format_tool_result(result: dict) -> str:
    """Format the check result of a single tool

    Args:
        result: Tool check result dictionary

    Returns:
        The formatted string
    """
    name = result["name"]
    description = result["description"]
    found = result["found"]
    version = result["version"]

    # Status icon
    status_icon = "✅" if found else "❌"

    # Tool name and description
    lines = [f"{status_icon} {name} - {description}"]

    # Version information
    if found and version:
        lines.append(f"   Version: {version}")

    # Installation suggestion
    if not found:
        install_hint = result["install_hint"]
        lines.append("   💡 Installation suggestion:")
        for hint_line in install_hint.strip().split("\n"):
            lines.append(f"      {hint_line}")

    return "\n".join(lines)


def _install_missing_tools(results: list) -> None:
    """Install the tools that are not installed

    Args:
        results: List of tool check results
    """
    # Find all tools that are not installed
    missing_tools = [r for r in results if not r["found"]]

    if not missing_tools:
        return

    # Build the list of tool names (for display to the user)
    tool_names = [r["name"] for r in missing_tools]
    tool_names_str = ", ".join(tool_names)

    # Ask the user whether to install automatically
    PrettyOutput.auto_print(
        f"⚠️  Detected {len(missing_tools)} tools not installed: {tool_names_str}"
    )
    if not confirm("Do you want to install these tools automatically?", default=True):
        PrettyOutput.auto_print("ℹ️  Skipping automatic installation")
        return

    # Install tools in batch
    PrettyOutput.auto_print("🚀 Starting automatic tool installation...")

    # Build a description containing the full tool configuration

    # Build structured tool information for easy understanding by LLMs
    tools_info = []
    for tool in missing_tools:
        tools_info.append(
            {
                "name": tool["name"],
                "description": tool["description"],
                "install_hint": tool["install_hint"],
            }
        )

    # Format the tool information into a clear description
    tools_json = json.dumps(tools_info, ensure_ascii=False, indent=2)
    combined_description = (
        f"Please help me install the following {len(missing_tools)} tools:\n\n"
        f"Tool information:\n"
        f"```json\n"
        f"{tools_json}\n"
        f"```\n\n"
        f"Please execute the installation command based on each tool's install_hint information."
    )

    try:
        # Use the hjb -T command to install tools in batch, passing the full tool configuration information
        import shutil
        import sys
        from pathlib import Path

        hjb_path = shutil.which("hjb")
        if hjb_path is None:
            # Use bash to load the user environment for lookup (overrides the user's shell PATH)
            try:
                result = subprocess.run(
                    ["bash", "-lc", "which hjb"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    hjb_path = result.stdout.strip()
            except Exception:
                pass
        if hjb_path is None:
            for candidate in [
                Path.home() / ".local" / "bin" / "hjb",
                Path(sys.executable).parent / "hjb",
            ]:
                if candidate.exists():
                    hjb_path = str(candidate)
                    break
        if hjb_path is None:
            hjb_path = "hjb"
        cmd = [hjb_path, "-T", combined_description]
        subprocess.run(cmd)

    except FileNotFoundError:
        # The hjb command does not exist, cannot continue installation
        PrettyOutput.auto_print("❌ Cannot find the 'hjb' command, unable to continue tool installation")
        PrettyOutput.auto_print("   Please make sure haijunbot is installed correctly and try again")
    except Exception as e:
        # Other exceptions
        PrettyOutput.auto_print(f"❌ Error during batch installation: {e}")

    PrettyOutput.auto_print("🔍 Re-checking tool installation status...")


def _print_results(results: list, summary: dict) -> None:
    """Print the check results

    Args:
        results: List of tool check results
        summary: Summary statistics
    """
    # Title
    PrettyOutput.auto_print("🔍 HaijunBot Check - Tool check results")

    # Separator line
    PrettyOutput.auto_print("=" * 60)

    # Summary
    total = summary["total"]
    found = summary["found"]
    missing = summary["missing"]

    PrettyOutput.auto_print(f"Total: {total} | Installed: {found} | Missing: {missing}")

    # Separator line
    PrettyOutput.auto_print("=" * 60)

    # Result for each tool
    for result in results:
        formatted = _format_tool_result(result)
        PrettyOutput.auto_print(formatted)

    # Conclusion
    if missing > 0:
        PrettyOutput.auto_print(
            f"⚠️  Found {missing} tools not installed; installing them is recommended for a better user experience"
        )
    else:
        PrettyOutput.auto_print("✨ All tools are installed!")


def _perform_check(
    checker: ToolChecker,
    tool_name: Optional[str],
    check_lint: bool,
    check_build: bool,
) -> tuple:
    """Perform the tool check

    Args:
        checker: ToolChecker instance
        tool_name: Name of the tool to check
        check_lint: Whether to check lint tools
        check_build: Whether to check build tools

    Returns:
        A (results, summary) tuple
    """
    if tool_name:
        # Check a single tool (takes precedence over other options)
        result = checker.check_single_tool(tool_name)
        results = [result]
    elif check_lint:
        # Check lint tools
        results = checker.check_lint_tools()
    elif check_build:
        # Check build tools
        results = checker.check_build_tools()
    else:
        # Check all tools (default behavior)
        results = checker.check_all_tools()

    summary = checker.get_summary(results)
    return results, summary


@app.command()
def check(
    tool_name: Optional[str] = typer.Argument(
        None, help="Name of the tool to check (optional); if unspecified, all tools are checked"
    ),
    as_json: bool = typer.Option(False, "--json", "-j", help="Output the result in JSON format"),
    check_lint: bool = typer.Option(False, "--check-lint", "-l", help="Check lint tools"),
    check_build: bool = typer.Option(False, "--check-build", "-b", help="Check build tools"),
) -> None:
    """Check tool installation status

    When no tool name is specified, all tools are checked; when specified, only a single tool is checked.
    """
    checker = ToolChecker()

    # Mutually exclusive check options
    check_flags = [check_lint, check_build]
    active_flags = sum(check_flags)
    if active_flags > 1:
        PrettyOutput.auto_print(
            "❌ Error: --check-lint and --check-build options cannot be used at the same time"
        )
        sys.exit(1)

    # Perform the initial check
    results, summary = _perform_check(checker, tool_name, check_lint, check_build)

    if as_json:
        # JSON format output: do not ask about installation, output the result directly

        output = {
            "summary": summary,
            "results": results,
        }
        PrettyOutput.auto_print(
            "📝 " + json.dumps(output, ensure_ascii=False, indent=2),
            lang="json",
        )
    else:
        # Friendly text output
        # If there are uninstalled tools, ask whether to install automatically
        if summary["missing"] > 0:
            _install_missing_tools(results)
            # Re-check tool status (use the same check logic to ensure consistency)
            results, summary = _perform_check(
                checker, tool_name, check_lint, check_build
            )

        # Output the final result
        _print_results(results, summary)

    # If there are uninstalled tools, return a non-zero exit code
    if summary["missing"] > 0:
        sys.exit(1)


def main() -> None:
    """Main entry function"""
    app()


if __name__ == "__main__":
    main()
