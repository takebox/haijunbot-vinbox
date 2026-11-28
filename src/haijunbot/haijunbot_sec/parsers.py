# -*- coding: utf-8 -*-
"""Parsing module - used to parse the JSON-formatted summaries returned by Agents"""

from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from haijunbot.haijunbot_utils.jsonnet_compat import loads as json_loads


def parse_clusters_from_text(
    text: str,
) -> tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Parse the clustering text, returning (parse result, error message)"""
    try:
        import re as _re

        # Use a regular expression for case-insensitive matching
        pattern = r"<CLUSTERS>([\s\S]*?)</CLUSTERS>"
        match = _re.search(pattern, text, flags=_re.IGNORECASE)
        if not match:
            # If the regex match fails, try a direct lookup (case-sensitive)
            start = text.find("<CLUSTERS>")
            end = text.find("</CLUSTERS>")
            if start == -1 or end == -1 or end <= start:
                return None, "Could not find the <CLUSTERS> or </CLUSTERS> tags, or the tag order is wrong"
            content = text[start + len("<CLUSTERS>") : end].strip()
        else:
            content = match.group(1).strip()

        if not content:
            return None, "JSON content is empty"
        try:
            data = json_loads(content)
        except Exception as json_err:
            error_msg = f"JSON parsing failed: {str(json_err)}"
            return None, error_msg
        if isinstance(data, list):
            return data, None
        return None, f"JSON parsing result is not an array, but {type(data).__name__}"
    except Exception as e:
        return None, f"An exception occurred during parsing: {str(e)}"


def try_parse_summary_report(text: str) -> tuple[Optional[object], Optional[str]]:
    """
    Extract the <REPORT>...</REPORT> content from the summary text and parse it into an object (dict or list, using JSON).
    Returns (parse result, error message)
    If parsing succeeds, returns (data, None)
    If parsing fails, returns (None, error message)
    """
    try:
        import re as _re

        # Use a regular expression for case-insensitive matching
        pattern = r"<REPORT>([\s\S]*?)</REPORT>"
        match = _re.search(pattern, text, flags=_re.IGNORECASE)
        if not match:
            # If the regex match fails, try a direct lookup (case-sensitive)
            start = text.find("<REPORT>")
            end = text.find("</REPORT>")
            if start == -1 or end == -1 or end <= start:
                return None, "Could not find the <REPORT> or </REPORT> tags, or the tag order is wrong"
            content = text[start + len("<REPORT>") : end].strip()
        else:
            content = match.group(1).strip()

        if not content:
            return None, "JSON content is empty"
        try:
            data = json_loads(content)
        except Exception as json_err:
            error_msg = f"JSON parsing failed: {str(json_err)}"
            return None, error_msg
        if isinstance(data, (dict, list)):
            return data, None
        return None, f"JSON parsing result is neither a dict nor an array, but {type(data).__name__}"
    except Exception as e:
        return None, f"An exception occurred during parsing: {str(e)}"
