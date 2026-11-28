# -*- coding: utf-8 -*-
"""Configuration editor module, responsible for editing configuration files"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer

from haijunbot.haijunbot_utils.output import PrettyOutput


class ConfigEditor:
    """Configuration file editor"""

    @staticmethod
    def get_default_editor() -> Optional[str]:
        """Get default editor based on operating system"""
        if platform.system() == "Windows":
            # Priority: terminal tools -> code editors -> general text editors
            editors = ["nvim", "vim", "nano", "code", "notepad++", "notepad"]
        else:
            # Priority: terminal tools -> code editors -> general text editors
            editors = ["nvim", "vim", "vi", "nano", "emacs", "code", "gedit", "kate"]

        return next((e for e in editors if shutil.which(e)), None)

    @staticmethod
    def edit_config(config_file: Optional[str] = None) -> None:
        """Edit configuration file"""
        config_file_path = (
            Path(config_file)
            if config_file
            else Path(os.path.expanduser("~/.haijunbot/config.yaml"))
        )

        editor = ConfigEditor.get_default_editor()

        if editor:
            try:
                # Editor dijalankan sebagai argv; tidak butuh cmd.exe.
                subprocess.run(
                    [editor, str(config_file_path)],
                    check=True,
                    shell=False,
                )
                raise typer.Exit(code=0)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                PrettyOutput.auto_print(f"❌ Failed to open editor: {e}")
                raise typer.Exit(code=1)
        else:
            PrettyOutput.auto_print(
                "❌ No suitable editor found. Please install one of: vim, nano, emacs, code"
            )
            raise typer.Exit(code=1)
