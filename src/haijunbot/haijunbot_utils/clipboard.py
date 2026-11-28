# -*- coding: utf-8 -*-
import platform
import subprocess

from haijunbot.haijunbot_utils.output import PrettyOutput


def copy_to_clipboard(text: str) -> None:
    """Copy text to the clipboard, supporting Windows, macOS, and Linux

    Parameters:
        text: The text to copy
    """
    PrettyOutput.auto_print("ℹ️ --- Clipboard content start ---")
    PrettyOutput.auto_print(text)
    PrettyOutput.auto_print("ℹ️ --- Clipboard content end ---")

    system = platform.system()

    # Windows system
    if system == "Windows":
        try:
            # clip.exe dijalankan langsung sebagai argv; tidak lewat cmd.exe.
            process = subprocess.Popen(
                ["clip"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
            if process.stdin:
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
            return
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Error using the Windows clip command: {e}")

    # macOS system
    elif system == "Darwin":
        try:
            process = subprocess.Popen(
                ["pbcopy"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if process.stdin:
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
            return
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Error using the macOS pbcopy command: {e}")

    # Linux system
    else:
        # Try using xsel
        try:
            process = subprocess.Popen(
                ["xsel", "-b", "-i"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if process.stdin:
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
            return
        except FileNotFoundError:
            pass  # xsel is not installed, continue trying the next one
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Error using xsel: {e}")

        # Try using xclip
        try:
            process = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if process.stdin:
                process.stdin.write(text.encode("utf-8"))
                process.stdin.close()
            return
        except FileNotFoundError:
            PrettyOutput.auto_print("⚠️ Neither xsel nor xclip is installed, cannot copy to clipboard")
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Error using xclip: {e}")
