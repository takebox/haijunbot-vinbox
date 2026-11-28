# -*- coding: utf-8 -*-
import os
from typing import Any
from typing import Optional

import typer
import yaml  # type: ignore[import-untyped]

from haijunbot.haijunbot_agent import Agent
from haijunbot.haijunbot_utils.config import set_llm_group
from haijunbot.haijunbot_utils.input import get_multiline_input
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env

app = typer.Typer(help="HaijunBot AI assistant")


def load_config(config_path: str) -> dict[str, Any]:
    """Load configuration from a YAML file

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        dict: Configuration dictionary
    """
    # Expand the ~ symbol in the path
    config_path = os.path.expanduser(config_path)

    if not os.path.exists(config_path):
        PrettyOutput.auto_print(f"⚠️ Configuration file does not exist: {config_path}")
        return {}

    with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
        try:
            config = yaml.safe_load(f)
            return config if config else {}
        except yaml.YAMLError as e:
            PrettyOutput.auto_print(f"❌ Failed to parse configuration file: {str(e)}")
            return {}


@app.command()
def eli(
    config_file: Optional[str] = typer.Option(
        None, "-f", "--config", help="Path to the agent configuration file"
    ),
    agent_definition: Optional[str] = typer.Option(
        None, "-c", "--agent-definition", help="Path to the agent definition file"
    ),
    task: Optional[str] = typer.Option(None, "-T", "--task", help="Initial task content"),
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="The model group to use, overriding the setting in the configuration file"
    ),
    non_interactive: bool = typer.Option(
        False,
        "-n",
        "--non-interactive",
        help="Enable non-interactive mode: the user cannot interact with the command, and the script execution timeout is limited to 5 minutes",
    ),
    restore_session: Optional[str] = typer.Option(
        None,
        "-r",
        "--restore-session",
        help="Path to the main file for restoring a session",
    ),
) -> None:
    """Main entry point for HaijunBot agent"""
    # Non-interactive mode requires the task to be passed from the command line
    if non_interactive and not (task and str(task).strip()):
        PrettyOutput.auto_print(
            "❌ Non-interactive mode is enabled: the task content must be passed via --task, because multiline input is unavailable."
        )
        raise typer.Exit(code=2)
    # Initialize the environment (pass in llm_group to ensure the welcome panel shows the correct model group)
    init_env(
        """Welcome to the HaijunBot AI assistant; your intelligent assistant is ready!""",
        config_file=config_file,
        llm_group=llm_group,
    )
    # After initializing the environment, sync the CLI options to the global config to avoid being overwritten by init_env
    try:
        if llm_group:
            set_llm_group(str(llm_group))
    except Exception:
        # Silently ignore sync exceptions; do not affect the main flow
        pass

    # Load configuration
    config = load_config(agent_definition) if agent_definition else {}

    # Override config with command-line arguments if provided
    if llm_group:
        config["llm_group"] = llm_group

    # Create and run agent
    try:
        # Pass the non_interactive flag to the Agent, ensuring it takes effect only within this Agent instance
        if non_interactive:
            config["non_interactive"] = True
        agent = Agent(**config)

        # Session restore logic
        if restore_session is not None:
            # Expand the ~ symbol in the path
            restore_session = os.path.expanduser(restore_session)
            # Check whether the file exists
            if not os.path.exists(restore_session):
                PrettyOutput.auto_print(f"❌ Session file does not exist: {restore_session}")
                raise typer.Exit(code=1)
            # Call the session restore method
            try:
                agent.session.restore_session_from_file(restore_session)
                PrettyOutput.auto_print(f"✅ Session restored from file: {restore_session}")
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Session restore failed: {str(e)}")
                raise typer.Exit(code=1)

        # Run agent with initial task if specified
        if task:
            PrettyOutput.auto_print(f"ℹ️ Executing initial task: {task}")
            agent.run(task)
            return

        try:
            user_input = get_multiline_input("Please enter your task (Ctrl+C to exit)")
            if not user_input:
                return
            agent.set_addon_prompt(
                "If needed, first define an action plan, then execute it step by step according to the plan. If the task is too complex, you may split it into sub-agents to execute; the split sub-agents must possess all the necessary task information, otherwise they cannot execute."
            )
            agent.run(user_input)
        except KeyboardInterrupt:
            # The user actively cancelled input; exit normally
            return
        except typer.Exit:
            # Normal exit from the input flow
            return
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Error: {str(e)}")

    except typer.Exit:
        return
    except Exception as e:
        PrettyOutput.auto_print(f"❌ Initialization error: {str(e)}")
        raise typer.Exit(code=1)


def main() -> None:
    """Application entry point."""
    app()


if __name__ == "__main__":
    main()
