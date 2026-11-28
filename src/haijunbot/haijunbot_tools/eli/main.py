import json
from typing import Optional

import typer

from haijunbot.haijunbot_tools.registry import ToolRegistry
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env

app = typer.Typer(help="HaijunBot tool system Execution Line Interface (ELI)")


@app.command("list")
def list_tools(
    as_json: bool = typer.Option(False, "--json", help="Output in JSON format"),
    detailed: bool = typer.Option(False, "--detailed", help="Show detailed information"),
) -> None:
    """List all available tools"""
    registry = ToolRegistry()
    tools = registry.get_all_tools()

    if as_json:
        if detailed:
            PrettyOutput.auto_print(
                "📝 " + json.dumps(tools, indent=2, ensure_ascii=False),
                lang="json",
            )
        else:
            simple_tools = [
                {"name": t["name"], "description": t["description"]} for t in tools
            ]
            PrettyOutput.auto_print(
                "📝 " + json.dumps(simple_tools, indent=2, ensure_ascii=False),
                lang="json",
            )
    else:
        PrettyOutput.auto_print("📋 List of available tools")
        # To avoid PrettyOutput boxing each line and making the information sparse, concatenate the strings first and print them together
        lines = []
        import json as _json  # local import to ensure available

        for tool in tools:
            lines.append(f"\n{tool['name']}")
            lines.append(f"   Description: {tool['description']}")
            if detailed:
                lines.append("   Parameters:")
                # Display parameters uniformly using a Markdown code block
                lines.append("```json")
                try:
                    lines.append(
                        _json.dumps(tool["parameters"], ensure_ascii=False, indent=2)
                    )
                except Exception:
                    lines.append(str(tool.get("parameters")))
                lines.append("```")
        PrettyOutput.auto_print("📝 " + "\n".join(lines), lang="markdown")


@app.command("call")
def call_tool(
    tool_name: str = typer.Argument(..., help="Name of the tool to call"),
    args: Optional[str] = typer.Option(None, "--args", help="Tool arguments (JSON format)"),
    args_file: Optional[str] = typer.Option(
        None, "--args-file", help="Load tool arguments from a file (JSON format)"
    ),
) -> None:
    """Call the specified tool"""
    registry = ToolRegistry()
    tool_obj = registry.get_tool(tool_name)

    if not tool_obj:
        PrettyOutput.auto_print(f"❌ Error: tool '{tool_name}' does not exist")
        available_tools = ", ".join([t["name"] for t in registry.get_all_tools()])
        PrettyOutput.auto_print(f"ℹ️ Available tools: {available_tools}")
        raise typer.Exit(code=1)

    tool_args = {}
    if args:
        try:
            tool_args = json.loads(args)
        except Exception:
            PrettyOutput.auto_print("❌ Error: arguments must be valid JSON format")
            raise typer.Exit(code=1)
    elif args_file:
        try:
            with open(args_file, "r", encoding="utf-8") as f:
                tool_args = json.load(f)
        except (Exception, FileNotFoundError) as e:
            PrettyOutput.auto_print(f"❌ Error: unable to load arguments from file: {str(e)}")
            raise typer.Exit(code=1)

    required_params = tool_obj.parameters.get("required", [])
    missing_params = [p for p in required_params if p not in tool_args]

    if missing_params:
        # Concatenate the prompt and argument descriptions first, then print them together, avoiding printing one by one inside the loop
        params = tool_obj.parameters.get("properties", {})
        lines = [
            f"Error: missing required arguments: {', '.join(missing_params)}",
            "",
            "Argument descriptions:",
        ]
        for param_name in required_params:
            param_info = params.get(param_name, {})
            desc = param_info.get("description", "no description")
            lines.append(f"  - {param_name}: {desc}")
        PrettyOutput.auto_print("❌ " + "\n❌ ".join(lines))
        raise typer.Exit(code=1)

    result = registry.execute_tool(tool_name, tool_args)

    if result["success"]:
        PrettyOutput.auto_print(f"✅ Tool {tool_name} executed successfully")
    else:
        PrettyOutput.auto_print(f"❌ Tool {tool_name} execution failed")

    if result.get("stdout"):
        PrettyOutput.auto_print("📤 Output:")
        PrettyOutput.auto_print("📝 " + result["stdout"], lang="text")

    if result.get("stderr"):
        PrettyOutput.auto_print("❌ Error:")
        PrettyOutput.auto_print("📝 " + result["stderr"], lang="text")

    if not result["success"]:
        raise typer.Exit(code=1)


@app.command("show")
def show_tool(
    tool_name: str = typer.Argument(..., help="Name of the tool to view"),
    as_json: bool = typer.Option(False, "--json", help="Output in JSON format"),
) -> None:
    """Show detailed information about the specified tool"""
    registry = ToolRegistry()
    # Look up from _all_tools so that all loaded tools (including filtered ones) can be shown
    tool_obj = registry._all_tools.get(tool_name)

    if not tool_obj:
        PrettyOutput.auto_print(f"❌ Error: tool '{tool_name}' does not exist")
        available_tools = ", ".join([t["name"] for t in registry.get_all_tools()])
        PrettyOutput.auto_print(f"ℹ️ Available tools: {available_tools}")
        raise typer.Exit(code=1)

    if as_json:
        # Output complete tool information in JSON format
        tool_dict = tool_obj.to_dict()
        PrettyOutput.auto_print(
            "📝 " + json.dumps(tool_dict, indent=2, ensure_ascii=False),
            lang="json",
        )
    else:
        # Display in readable format
        lines = [
            f"📦 Tool name: {tool_obj.name}",
            f"📝 Description: {tool_obj.description}",
            f"🔧 Protocol version: {getattr(tool_obj, 'protocol_version', '1.0')}",
            "",
            "📋 Parameters:",
        ]

        # Display parameter information
        params = tool_obj.parameters
        properties = params.get("properties", {})

        if properties:
            lines.append("```json")
            lines.append(json.dumps(params, indent=2, ensure_ascii=False))
            lines.append("```")
        else:
            lines.append("   No parameters")

        PrettyOutput.auto_print("📝 " + "\n".join(lines), lang="markdown")


def eli() -> None:
    """Typer application entry point"""
    init_env()
    app()


def main() -> None:
    """Main entry point for the script"""
    eli()


if __name__ == "__main__":
    main()
