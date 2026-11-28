#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import subprocess
from typing import Optional
from typing import Tuple

import typer

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.config import get_shell_name, read_text_file
from haijunbot.haijunbot_utils.config import set_config
from haijunbot.haijunbot_utils.input import get_multiline_input
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env
from haijunbot.haijunbot_utils import vinbox_runtime

app = typer.Typer(
    help="Convert natural language requests into shell commands",
    epilog="""
Example:
  hss request "Find all Python files in the current directory"
  hss install
""",
)


def execute_command(command: str, should_run: bool) -> None:
    """Print command without execution"""
    print(command)
    if should_run:
        # Core functionality: execute the shell command (provided by the user).
        # Inside Vinbox the command runs with Vinbox's own shell (pwsh), its
        # File Manager working directory and its environment, exactly like a
        # command typed in the Vinbox terminal. No second shell is invented.
        if vinbox_runtime.is_vinbox():
            subprocess.run(  # nosec B603,B607 - Vinbox's own pwsh, no user shell
                [vinbox_runtime.shell_path(), "-NoProfile", "-Command", command],
                cwd=vinbox_runtime.working_dir(),
                env=vinbox_runtime.process_env(),
                check=False,
            )
            return
        os.system(command)  # nosec B605


def _get_config_file() -> str:
    """Get fish config file path

    Returns:
        str: Path to fish config file
    """
    return os.path.expanduser("~/.config/fish/config.fish")


def _get_markers() -> Tuple[str, str]:
    """Get start and end markers for JSS completion

    Returns:
        Tuple[str, str]: (start_marker, end_marker)
    """
    return (
        "# ===== HAIJUNBOT JSS FISH COMPLETION START =====",
        "# ===== HAIJUNBOT JSS FISH COMPLETION END =====",
    )


def _check_bash_shell() -> bool:
    """Check if current shell is bash

    Returns:
        bool: True if bash shell, False otherwise
    """
    return get_shell_name() == "bash"


def _get_bash_config_file() -> str:
    """Get bash config file path

    Returns:
        str: Path to bash config file (~/.bashrc)
    """
    return os.path.expanduser("~/.bashrc")


def _get_bash_markers() -> Tuple[str, str]:
    """Get start and end markers for JSS completion in bash

    Returns:
        Tuple[str, str]: (start_marker, end_marker)
    """
    return (
        "# ===== HAIJUNBOT JSS BASH COMPLETION START =====",
        "# ===== HAIJUNBOT JSS BASH COMPLETION END =====",
    )


def _check_zsh_shell() -> bool:
    """Check if current shell is zsh

    Returns:
        bool: True if zsh shell, False otherwise
    """
    return get_shell_name() == "zsh"


def _get_zsh_config_file() -> str:
    """Get zsh config file path

    Returns:
        str: Path to zsh config file (~/.zshrc)
    """
    return os.path.expanduser("~/.zshrc")


def _get_zsh_markers() -> Tuple[str, str]:
    """Get start and end markers for JSS completion in zsh

    Returns:
        Tuple[str, str]: (start_marker, end_marker)
    """
    return (
        "# ===== HAIJUNBOT JSS ZSH COMPLETION START =====",
        "# ===== HAIJUNBOT JSS ZSH COMPLETION END =====",
    )


def _get_pwsh_config_file() -> str:
    """PowerShell profile belonging to Vinbox's own pwsh.

    Inside Vinbox the terminal is PowerShell Core (``app/terminal_pwsh.py``),
    so the smart shell has to install into that profile, not into a POSIX
    rc file the Vinbox terminal never reads.
    """
    if os.name == "nt":
        return os.path.join(
            os.path.expanduser("~/Documents"),
            "PowerShell",
            "Microsoft.PowerShell_profile.ps1",
        )
    return os.path.expanduser(
        "~/.config/powershell/Microsoft.PowerShell_profile.ps1"
    )


def _get_pwsh_markers() -> Tuple[str, str]:
    """Get start and end markers for JSS completion in pwsh

    Returns:
        Tuple[str, str]: (start_marker, end_marker)
    """
    return (
        "# ===== HAIJUNBOT JSS PWSH COMPLETION START =====",
        "# ===== HAIJUNBOT JSS PWSH COMPLETION END =====",
    )


def _install_pwsh_completion() -> None:
    """Write the JSS handler into Vinbox's pwsh profile."""
    config_file = _get_pwsh_config_file()
    start_marker, end_marker = _get_pwsh_markers()

    if not os.path.exists(config_file):
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, "w", encoding="utf-8") as f:
            f.write("")

    content = read_text_file(config_file)
    if start_marker in content:
        PrettyOutput.auto_print(
            "✅ JSS pwsh completion already installed, restart the Vinbox terminal"
        )
        return

    with open(config_file, "a", encoding="utf-8") as f:
        f.write(
            f"""
{start_marker}
# HaijunBot smart shell for the Vinbox PowerShell terminal.
# Unknown commands longer than 10 characters get a suggested replacement.
$ExecutionContext.InvokeCommand.CommandNotFoundAction = {{
    param($Name, $Lookup)
    if ($Name.Length -lt 10) {{ return }}
    $line = $Lookup.CommandLine
    if (-not $line) {{ $line = $Name }}
    $suggestion = (& hss request "$line")
    if ($suggestion) {{
        Write-Host "💡 $suggestion" -ForegroundColor Cyan
    }}
}}
{end_marker}
"""
        )
    PrettyOutput.auto_print(
        "✅ JSS pwsh completion installed, restart the Vinbox terminal"
    )


def _uninstall_pwsh_completion() -> None:
    """Remove the JSS handler from Vinbox's pwsh profile."""
    config_file = _get_pwsh_config_file()
    start_marker, end_marker = _get_pwsh_markers()

    if not os.path.exists(config_file):
        PrettyOutput.auto_print(
            "ℹ️ JSS pwsh completion configuration not found, nothing to uninstall"
        )
        return

    content = read_text_file(config_file)
    if start_marker not in content or end_marker not in content:
        PrettyOutput.auto_print(
            "ℹ️ JSS pwsh completion configuration not found, nothing to uninstall"
        )
        return

    new_content = content.split(start_marker)[0] + content.split(end_marker)[-1]
    with open(config_file, "w", encoding="utf-8") as f:
        f.write(new_content)

    PrettyOutput.auto_print(
        "✅ JSS pwsh completion uninstalled, restart the Vinbox terminal"
    )


@app.command("install")
def install_jss_completion(
    shell: Optional[str] = typer.Option(
        None,
        help="Shell type (fish, bash, zsh, pwsh). Inside Vinbox the default is pwsh.",
    ),
) -> None:
    """Install the 'command not found' handler for the specified shell to enable natural language command suggestions"""
    if not shell:
        shell = "pwsh" if vinbox_runtime.is_vinbox() else "fish"
    shell = shell.lower()
    if shell not in ("fish", "bash", "zsh", "pwsh"):
        PrettyOutput.auto_print(
            f"❌ Error: unsupported shell type: {shell}, only fish, bash, zsh, pwsh are supported"
        )
        raise typer.Exit(code=1)

    if shell == "pwsh":
        _install_pwsh_completion()
        return

    if shell == "fish":
        config_file = _get_config_file()
        start_marker, end_marker = _get_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ config.fish not found, a new file will be created")
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, "w") as f:
                f.write("")

        content = read_text_file(config_file)

        if start_marker in content:
            PrettyOutput.auto_print(
                "✅ JSS fish completion installed, run: source ~/.config/fish/config.fish"
            )
            return

        with open(config_file, "a") as f:
            f.write(
                f"""
{start_marker}
function fish_command_not_found
    if test (string length "$argv") -lt 10
        return
    end
    commandline -r (hss request "$argv")
end

function __fish_command_not_found_handler --on-event fish_command_not_found
    fish_command_not_found "$argv"
end
{end_marker}
"""
            )
        PrettyOutput.auto_print(
            "✅ JSS fish completion installed, run: source ~/.config/fish/config.fish"
        )
    elif shell == "bash":
        config_file = _get_bash_config_file()
        start_marker, end_marker = _get_bash_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ ~/.bashrc not found, a new file will be created")
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, "w") as f:
                f.write("")

        content = read_text_file(config_file)

        if start_marker in content:
            PrettyOutput.auto_print(
                "✅ JSS bash completion installed, run: source ~/.bashrc"
            )
            return
        else:
            with open(config_file, "a") as f:
                f.write(
                    f"""
{start_marker}
# Bash 'command not found' handler for JSS
# Behavior:
# - generate an editable suggested command; the user can edit it and press Enter to execute
# - in non-interactive mode, only print the suggestion
command_not_found_handle() {{
    local cmd="$1"
    shift || true
    local text="$cmd $*"

    # Keep behavior consistent with fish: do not handle overly short input
    if [ ${{#text}} -lt 10 ]; then
        return 127
    fi

    local suggestion edited
    suggestion=$(hss request "$text")
    if [ -n "$suggestion" ]; then
        # Interactive mode: prefill the command with readline; the user can press Enter to execute or edit it
        if [[ $- == *i* ]]; then
            edited="$suggestion"
            # -e enables readline; -i prefills the default value; no prompt prefix, making the experience closer to fish's "replace command line"
            read -e -i "$edited" edited
            if [ -n "$edited" ]; then
                eval "$edited"
                return $?
            fi
        else
            # Non-interactive mode: only print the suggestion
            printf '%s\n' "$suggestion"
        fi
    fi
    return 127
}}
{end_marker}
"""
                )
            PrettyOutput.auto_print(
                "✅ JSS bash completion installed, run: source ~/.bashrc"
            )
    elif shell == "zsh":
        config_file = _get_zsh_config_file()
        start_marker, end_marker = _get_zsh_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ ~/.zshrc not found, a new file will be created")
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            with open(config_file, "w") as f:
                f.write("")

        content = read_text_file(config_file)

        if start_marker in content:
            PrettyOutput.auto_print(
                "✅ JSS zsh completion installed, run: source ~/.zshrc"
            )
            return

        with open(config_file, "a") as f:
            f.write(
                f"""
{start_marker}
# Zsh 'command not found' handler for JSS
# Behavior:
# - generate an editable suggested command; the user can edit it and press Enter to execute
# - in non-interactive mode, only print the suggestion
command_not_found_handler() {{
    local cmd="$1"
    shift || true
    local text="$cmd $*"

    # Keep behavior consistent with fish: do not handle overly short input
    if [ ${{#text}} -lt 10 ]; then
        return 127
    fi

    local suggestion edited
    suggestion=$(hss request "$text")
    if [ -n "$suggestion" ]; then
        if [[ -o interactive ]]; then
            local editor="${{VISUAL:-${{EDITOR:-vi}}}}"
            local tmpfile edited
            tmpfile="$(mktemp -t hss-edit-XXXXXX)"
            printf '%s\n' "$suggestion" > "$tmpfile"
            "$editor" "$tmpfile"
            edited="$(sed -n '/./{{p;q;}}' "$tmpfile" | tr -d '\r')"
            rm -f "$tmpfile"
            if [ -z "$edited" ]; then
                edited="$suggestion"
            fi
            eval "$edited"
            return $?
        else
            # Non-interactive mode: only print the suggestion
            print -r -- "$suggestion"
        fi
    fi
    return 127
}}
{end_marker}
"""
            )
        PrettyOutput.auto_print("✅ JSS zsh completion installed, run: source ~/.zshrc")
        return


@app.command("uninstall")
def uninstall_jss_completion(
    shell: Optional[str] = typer.Option(
        None,
        help="Shell type (fish, bash, zsh, pwsh). Inside Vinbox the default is pwsh.",
    ),
) -> None:
    """Uninstall the JSS shell 'command not found' handler"""
    if not shell:
        shell = "pwsh" if vinbox_runtime.is_vinbox() else "fish"
    shell = shell.lower()
    if shell not in ("fish", "bash", "zsh", "pwsh"):
        PrettyOutput.auto_print(
            f"❌ Error: unsupported shell type: {shell}, only fish, bash, zsh, pwsh are supported"
        )
        raise typer.Exit(code=1)

    if shell == "pwsh":
        _uninstall_pwsh_completion()
        return

    if shell == "fish":
        config_file = _get_config_file()
        start_marker, end_marker = _get_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ JSS fish completion configuration not found, nothing to uninstall")
            return

        content = read_text_file(config_file)

        if start_marker not in content:
            PrettyOutput.auto_print("ℹ️ JSS fish completion configuration not found, nothing to uninstall")
            return

        new_content = content.split(start_marker)[0] + content.split(end_marker)[-1]

        with open(config_file, "w") as f:
            f.write(new_content)

        PrettyOutput.auto_print(
            "✅ JSS fish completion uninstalled, run: source ~/.config/fish/config.fish"
        )
    elif shell == "bash":
        config_file = _get_bash_config_file()
        start_marker, end_marker = _get_bash_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ JSS bash completion configuration not found, nothing to uninstall")
            return

        content = read_text_file(config_file)

        if start_marker not in content:
            PrettyOutput.auto_print("ℹ️ JSS bash completion configuration not found, nothing to uninstall")
            return

        new_content = content.split(start_marker)[0] + content.split(end_marker)[-1]

        with open(config_file, "w") as f:
            f.write(new_content)

        PrettyOutput.auto_print(
            "✅ JSS bash completion uninstalled, run: source ~/.bashrc"
        )
    elif shell == "zsh":
        config_file = _get_zsh_config_file()
        start_marker, end_marker = _get_zsh_markers()

        if not os.path.exists(config_file):
            PrettyOutput.auto_print("ℹ️ JSS zsh completion configuration not found, nothing to uninstall")
            return

        content = read_text_file(config_file)

        if start_marker not in content:
            PrettyOutput.auto_print("ℹ️ JSS zsh completion configuration not found, nothing to uninstall")
            return

        new_content = content.split(start_marker)[0] + content.split(end_marker)[-1]

        with open(config_file, "w") as f:
            f.write(new_content)

        PrettyOutput.auto_print("✅ JSS zsh completion uninstalled, run: source ~/.zshrc")


def process_request(request: str) -> Optional[str]:
    """Process user request and return corresponding shell command

    Args:
        request: User's natural language request

    Returns:
        Optional[str]: Corresponding shell command, return None if processing fails
    """
    try:
        # Get language model instance
        # Use the normal platform; smart shell command generation is a general task
        model = PlatformRegistry.get_global_platform_registry().get_normal_platform()
        # Suppress verbose output from the LLM interaction
        model.set_suppress_output(True)

        shell = get_shell_name()
        current_path = os.getcwd()
        # Inside Vinbox the suggestion must match the real terminal: pwsh in
        # the File Manager, not the POSIX shell of the host running the agent.
        if vinbox_runtime.is_vinbox():
            shell = os.path.basename(vinbox_runtime.shell_path()) or "pwsh"
            current_path = vinbox_runtime.working_dir()

        # Set system prompt
        system_message = """
# Role
Convert natural language into shell commands

# Rules
1. Output only the command
2. Do not output anything other than the command
3. Output on a single line
4. Join multiple commands with &&

# Examples
Input: "show the contents of the current directory"
Output: ls -la
"""
        model.set_system_prompt(system_message)

        prefix = f"Current path: {current_path}\n"
        prefix += f"Current shell: {shell}\n"

        result = model.chat_until_success(prefix + request)

        # Extract the command
        if result and isinstance(result, str):
            command = result.strip()
            return command

        return None

    except Exception:
        return None


@app.command("request")
def request_command(
    request: Optional[str] = typer.Argument(
None, help="Describe the operation you want to perform (in natural language); read from standard input if not provided"
    ),
    ):
    """Describe the operation you want to perform (in natural language)"""
    # Set the environment variable to skip the terminal nesting check (JSS may be invoked by a shell handler)
    os.environ["terminal"] = "0"
    should_run = False
    if not request:
        # Check whether running in an interactive terminal
        request = get_multiline_input(tip="Enter the operation you want to perform")
        should_run = True

    # Process the request
    command = process_request(request)

    # Output the result
    if command:
        execute_command(command, should_run)  # Display and execute the command
    else:
        raise typer.Exit(code=1)


def eli():
    """Typer application entry point"""
    init_env("", auto_upgrade=False)
    set_config("print_prompt", "false")
    app()


def main():
    """Main entry point for the script"""
    eli()


if __name__ == "__main__":
    main()
