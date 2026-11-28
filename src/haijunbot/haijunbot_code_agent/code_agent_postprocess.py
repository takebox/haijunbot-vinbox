"""CodeAgent post-processing module"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import os
import subprocess

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import List

from haijunbot.haijunbot_code_agent.after_change import get_after_change_commands_for_files
from haijunbot.haijunbot_utils.vinbox_runtime import pwsh_argv


class PostProcessManager:
    """Post-processing manager"""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir

    def post_process_modified_files(self, modified_files: List[str]) -> None:
        """File post-processing (including formatting, auto-fixing, etc.)

        Args:
            modified_files: list of modified files
        """
        # Get post-change processing commands
        after_change_commands = get_after_change_commands_for_files(
            modified_files, self.root_dir
        )
        if not after_change_commands:
            return

        # Execute post-change processing commands
        processed_files = set()
        for file_path, command in after_change_commands:
            # Extract the tool name (first word) from the command for logging
            tool_name = command.split()[0] if command.split() else "unknown"
            try:
                # Check whether the file exists
                abs_file_path = (
                    os.path.join(self.root_dir, file_path)
                    if not os.path.isabs(file_path)
                    else file_path
                )
                if not os.path.exists(abs_file_path):
                    continue

                # Execute the post-change processing command (command comes from the config file)
                # Dijalankan lewat pwsh dengan argv list, bukan shell=True.
                result = subprocess.run(
                    pwsh_argv(command),
                    shell=False,
                    cwd=self.root_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,  # 300 second timeout
                )

                if result.returncode == 0:
                    processed_files.add(file_path)
                    PrettyOutput.auto_print(
                        f"✅ Processed: {os.path.basename(file_path)} ({tool_name})"
                    )
                else:
                    # Processing failed, record but do not interrupt the flow
                    error_msg = (result.stderr or result.stdout or "").strip()
                    if error_msg:
                        PrettyOutput.auto_print(
                            f"⚠️ Processing failed ({os.path.basename(file_path)}, {tool_name}): {error_msg[:200]}"
                        )
            except subprocess.TimeoutExpired:
                PrettyOutput.auto_print(
                    f"⚠️ Processing timed out: {os.path.basename(file_path)} ({tool_name})"
                )
            except FileNotFoundError:
                # Tool not installed, skip
                continue
            except Exception as e:
                # Other errors, record but continue
                PrettyOutput.auto_print(
                    f"⚠️ Processing failed ({os.path.basename(file_path)}, {tool_name}): {str(e)[:100]}"
                )
                continue

        if processed_files:
            PrettyOutput.auto_print(f"✅ Processed {len(processed_files)} files")
            # Stage the processed files
            try:
                for file_path in processed_files:
                    abs_file_path = (
                        os.path.join(self.root_dir, file_path)
                        if not os.path.isabs(file_path)
                        else file_path
                    )
                    if os.path.exists(abs_file_path):
                        subprocess.run(
                            ["git", "add", file_path],
                            cwd=self.root_dir,
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_code_agent.code_agent_postprocess",
                    function="post_process_modified_files",
                )
                pass
