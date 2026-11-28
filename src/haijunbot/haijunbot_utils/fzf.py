# -*- coding: utf-8 -*-
"""FZF selector utility."""

import shutil
import subprocess
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Union
from typing import cast

from haijunbot.haijunbot_utils.utils import decode_output


def fzf_select(
    options: Union[List[str], List[Dict[str, Any]]],
    prompt: str = "SELECT> ",
    key: Optional[str] = None,
) -> Optional[str]:
    """
    Select an item from a list using fzf.

    Parameters:
        options: A list of strings or dictionaries to choose from.
        prompt: The prompt message displayed in fzf.
        key: If options is a list of dictionaries, this parameter specifies the key name to display.

    Returns:
        The selected item, or None if fzf is unavailable or the selection is cancelled.
    """
    if shutil.which("fzf") is None:
        return None

    if not options:
        return None

    if isinstance(options[0], dict):
        if key is None:
            raise ValueError("A key must be provided for a list of dicts.")
        input_lines = [str(cast(Dict[str, Any], item).get(key, "")) for item in options]
    else:
        input_lines = [str(item) for item in options]

    try:
        process = subprocess.run(
            [
                "fzf",
                "--prompt",
                prompt,
                "--height",
                "40%",
                "--border",
                "--layout=reverse",
            ],
            input="\n".join(input_lines).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        selected = decode_output(process.stdout).strip()
        return selected if selected else None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
