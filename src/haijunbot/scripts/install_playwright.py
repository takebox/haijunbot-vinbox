# -*- coding: utf-8 -*-
"""Playwright browser driver installation utility

Provides a convenient command-line tool to install the Playwright browser driver.
"""

import subprocess
import sys

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import init_env


def install_chromium() -> None:
    """Install the Playwright Chromium browser driver"""
    init_env("")
    PrettyOutput.auto_print("🔧 Installing Playwright Chromium browser driver...")
    PrettyOutput.auto_print("This may take a few minutes, please wait patiently...")
    PrettyOutput.auto_print("")

    try:
        # Use sys.executable to ensure the correct Python interpreter is used
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
        )

        PrettyOutput.auto_print("✅ Playwright Chromium browser driver installed successfully!")
        if result.stdout:
            PrettyOutput.auto_print(result.stdout)

    except subprocess.CalledProcessError as e:
        PrettyOutput.auto_print(f"❌ Installation failed, return code: {e.returncode}")
        if e.stderr:
            PrettyOutput.auto_print(f"Error message: {e.stderr}")
        sys.exit(1)
    except Exception as e:
        PrettyOutput.auto_print(f"❌ An error occurred during installation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    install_chromium()
