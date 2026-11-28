# -*- coding: utf-8 -*-
"""Exception logging utility module.

Provides a unified exception information logging feature, saving exception details to the ~/.haijunbot/exceptions/ directory,
for subsequent analysis and optimization. On save failure it is silently ignored, without affecting the main flow.
"""

import os


def save_exception(
    exception: Exception,
    context: str = "",
    module: str = "",
    function: str = "",
) -> None:
    """Record exception information to the data directory, for subsequent analysis and optimization.

    Exception records are saved under the ~/.haijunbot/exceptions/ directory,
    with the filename format {YYYYMMDD_HHMMSS}_{module}_{function}.json.
    On save failure it is silently ignored, without affecting the main flow.

    Parameters:
        exception: The caught exception object
        context: Optional context description, explaining the business scenario when the exception occurred
        module: Optional module name, such as "haijunbot_tools"
        function: Optional function name, such as "_extract_tool_calls"
    """
    try:
        import json
        import re
        import time
        import traceback

        from haijunbot.haijunbot_utils.config import get_data_dir

        # Create the save directory
        exception_dir = os.path.join(get_data_dir(), "exceptions")
        os.makedirs(exception_dir, exist_ok=True)

        # Get the exception's traceback information
        tb_str = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        tb_text = "".join(tb_str)

        # Desensitization: remove potentially sensitive information such as API keys
        safe_tb = tb_text
        safe_context = context or ""
        sensitive_patterns = [
            r"sk-[a-zA-Z0-9]{20,}",
            r'key["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
            r'token["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
            r'password["\s:=]+["\']?[a-zA-Z0-9]{20,}["\']?',
        ]
        for pattern in sensitive_patterns:
            safe_tb = re.sub(pattern, "[REDACTED]", safe_tb)
            safe_context = re.sub(pattern, "[REDACTED]", safe_context)

        # Build the data to save
        error_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "exception_type": type(exception).__name__,
            "exception_msg": str(exception),
            "traceback": safe_tb,
            "context": safe_context,
            "module": module,
            "function": function,
        }

        # Save the file: timestamp_module_function.json
        safe_module = (
            module.replace("/", "_").replace("\\", "_") if module else "unknown"
        )
        safe_function = (
            function.replace("/", "_").replace("\\", "_") if function else "unknown"
        )
        filename = (
            f"{time.strftime('%Y%m%d_%H%M%S')}_{safe_module}_{safe_function}.json"
        )
        filepath = os.path.join(exception_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(error_data, f, ensure_ascii=False, indent=2)
    except Exception:
        # Save failure does not affect the main flow, silently ignore
        pass
