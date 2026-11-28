"""
Shared helper module for the gh plugin (no tool classes, for import reuse by various tools).

Provides:
- Reading GitHub token (reusing GitHub official gh CLI login state, `gh auth token`)
- GitHub REST API request wrapper (urllib, no requests dependency)
- Default repository constant
"""

import json
import subprocess
import urllib.error
import urllib.request
from typing import Optional

# GitHub REST API base URL
API_BASE = "https://api.github.com"
# Default repository (current HaijunBot GitHub repository)
DEFAULT_REPO = "takebox/HaijunBot"


def get_token() -> str:
    """Read GitHub token (reusing GitHub official gh CLI login state).

    Gets the token for the currently logged-in account via `gh auth token`; returns
    an empty string when the gh CLI is not installed or not logged in. The gh plugin
    itself does not provide login authentication; authentication is handled by the gh CLI.
    """
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _build_headers(token: str) -> dict:
    """Build request headers. Add Authorization when token is present."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "HaijunBot-gh-plugin",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def api_request(
    method: str,
    path: str,
    token: str = "",
    data: Optional[dict] = None,
    timeout: int = 30,
) -> dict:
    """Call GitHub REST API.

    Parameters:
        method: HTTP method (GET/POST/PUT/PATCH/DELETE)
        path: API path, e.g. "/repos/takebox/HaijunBot/pulls"
        token: GitHub token (required for write operations)
        data: Request body dict (optional)
        timeout: Timeout in seconds

    Returns:
        dict: {"success": bool, "status": int, "data": dict|list|None,
               "headers": dict, "error": str}
        headers are response headers (keys normalized to lowercase), for upper layers
        to parse pagination Link headers.
    """
    url = API_BASE + path
    body = None
    headers = _build_headers(token)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw) if raw else None
            except Exception:
                parsed = raw
            return {
                "success": True,
                "status": status,
                "data": parsed,
                "headers": resp_headers,
                "error": "",
            }
    except urllib.error.HTTPError as e:
        status = e.code
        resp_headers = {k.lower(): v for k, v in (e.headers or {}).items()}
        raw = e.read().decode("utf-8", errors="replace")
        message = ""
        try:
            err_data = json.loads(raw)
            message = err_data.get("message", "")
        except Exception:
            message = raw
        return {
            "success": False,
            "status": status,
            "data": None,
            "headers": resp_headers,
            "error": f"GitHub API {status}: {message}",
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "status": 0,
            "data": None,
            "headers": {},
            "error": f"Network error: {e.reason}",
        }
    except Exception as e:
        return {"success": False, "status": 0, "data": None, "headers": {}, "error": str(e)}


def parse_link_next(headers: dict) -> str:
    """Parse the rel="next" URL from the response Link header; return empty string if not present.

    GitHub pagination returns adjacent page URLs via the Link header, in the form:
      <https://api.github.com/...&page=2>; rel="next", <...&page=5>; rel="last"
    """
    link = (headers or {}).get("link", "")
    if not link:
        return ""
    for part in link.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        for seg in segments[1:]:
            if seg.strip() == 'rel="next"':
                return url
    return ""


def parse_link_last_page(headers: dict) -> int:
    """Parse the page parameter from rel="last" in the response Link header; return 0 if not present."""
    link = (headers or {}).get("link", "")
    if not link:
        return 0
    for part in link.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        is_last = any(seg.strip() == 'rel="last"' for seg in segments[1:])
        if not is_last:
            continue
        # Extract the page parameter from the URL query string
        if "?" not in url:
            return 0
        query = url.split("?", 1)[1]
        for kv in query.split("&"):
            if kv.startswith("page="):
                try:
                    return int(kv.split("=", 1)[1])
                except ValueError:
                    return 0
    return 0


def parse_remote_repo(remote_url: str) -> str:
    """Parse 'owner/repo' from a git remote URL (without .git suffix).

    Supports common formats:
      https://github.com/owner/repo.git
      https://github.com/owner/repo
      git@github.com:owner/repo.git
      ssh://git@github.com/owner/repo.git
    Returns an empty string on parse failure.
    """
    url = (remote_url or "").strip()
    if not url:
        return ""
    # Remove .git suffix
    if url.endswith(".git"):
        url = url[: -len(".git")]
    # Remove trailing slash
    url = url.rstrip("/")
    # ssh style: git@github.com:owner/repo
    if "://" not in url and ":" in url:
        url = url.split(":", 1)[1]
    else:
        # https/ssh:// style: take the path portion
        url = url.split("://", 1)[-1]
        # Remove the host portion (before the first /)
        if "/" in url:
            url = url.split("/", 1)[1]
    # Remove possible username/port prefixes, take owner/repo
    parts = [p for p in url.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-2]}/{parts[-1]}"
    return ""


def resolve_repo_from_dir(working_dir: str) -> str:
    """Execute git remote get-url origin in the specified directory and parse 'owner/repo'.

    Returns an empty string for non-git repositories or when no origin remote exists.
    """
    import subprocess

    working_dir = (working_dir or "").strip()
    if not working_dir:
        return ""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return parse_remote_repo(result.stdout.strip())


def auth_error_hint(status: int) -> str:
    """Provide authentication hints based on HTTP status code."""
    if status in (401, 403):
        return (
            "Authentication failed (token missing or invalid). Please run gh auth login in the terminal to log in to GitHub first, "
            "or use gh auth status to check the login state."
        )
    return ""