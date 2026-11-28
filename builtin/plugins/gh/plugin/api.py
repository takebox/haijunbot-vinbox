"""
gh plugin private function layer (runs in gateway, called by frontend proxy; not exposed to Agent).

Provides all gh plugin business logic as pure functions:
- list_issues / list_prs / get_issue / get_pr: read operations (anonymous access OK)
- merge_pr / comment / close_issue: write operations (require logged-in token, reuse gh CLI login state)
- resolve_repo: resolve repository corresponding to current working directory

Each function returns dict: {"success": bool, "data": .../ "message": .../ "error": ...}.
This module is not declared in tool_load_dirs, so it won't be loaded by ToolRegistry, invisible to Agent;
gateway dynamically loads this module via plugin function proxy endpoint and calls it.
"""

import os
import subprocess
import sys
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

# Ensure we can import gh_common from same directory (plugin/ not in sys.path when gateway dynamically loads this file)
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import gh_common  # noqa: E402


def _require_repo(repo: Optional[str]) -> tuple:
    """Validate and return repo name. Returns (repo, error); error is non-empty when repo is empty."""
    repo = (repo or "").strip()
    if not repo:
        return "", "No repo specified (current directory is not a git repo or missing origin remote)"
    return repo, ""


# Max items per page (GitHub REST API limit is 100)
_MAX_PER_PAGE = 100


def _normalize_paging(page: Any, per_page: Any) -> tuple:
    """Normalize pagination params, returns (page, per_page).

    Page starts at 1; per_page limited to [1, 100]. Invalid values fall back to defaults.
    """
    try:
        page_num = int(page)
    except (TypeError, ValueError):
        page_num = 1
    if page_num < 1:
        page_num = 1
    try:
        per_page_num = int(per_page)
    except (TypeError, ValueError):
        per_page_num = _MAX_PER_PAGE
    if per_page_num < 1:
        per_page_num = _MAX_PER_PAGE
    if per_page_num > _MAX_PER_PAGE:
        per_page_num = _MAX_PER_PAGE
    return page_num, per_page_num


def _paging_meta(headers: dict, page: int, per_page: int, count: int) -> dict:
    """Build pagination metadata from response headers and current page info.

    Returns {"total": int, "has_more": bool, "page": int, "per_page": int}.
    Total inferred from Link header rel="last" page (GitHub list APIs don't return total directly),
    falls back to "loaded count" when not inferable.
    """
    last_page = gh_common.parse_link_last_page(headers)
    has_more = bool(gh_common.parse_link_next(headers))
    if last_page > 0:
        # Last page may have fewer than per_page items, estimate with (last_page-1)*per_page + current page count
        if has_more:
            total = last_page * per_page
        else:
            total = (last_page - 1) * per_page + count
    else:
        total = (page - 1) * per_page + count
    return {"total": total, "has_more": has_more, "page": page, "per_page": per_page}


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------
def list_issues(
    repo: Optional[str] = None,
    state: str = "open",
    page: Any = 1,
    per_page: Any = _MAX_PER_PAGE,
) -> Dict[str, Any]:
    """List repository Issues (excluding PRs), with pagination.

    Returns data as current page issue list, plus total/has_more/page/per_page pagination metadata.
    """
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    state = (state or "open").strip()
    if state not in ("open", "closed", "all"):
        return {"success": False, "error": f"Invalid state: {state}"}
    page, per_page = _normalize_paging(page, per_page)
    resp = gh_common.api_request(
        "GET",
        f"/repos/{repo}/issues?state={state}&per_page={per_page}&page={page}",
        token=gh_common.get_token(),
    )
    if not resp["success"]:
        return {"success": False, "error": resp["error"]}
    issues = resp["data"]
    if not isinstance(issues, list):
        return {"success": False, "error": "Unexpected response format"}
    result = []
    for issue in issues:
        if issue.get("pull_request"):
            continue
        result.append(
            {
                "number": issue.get("number"),
                "title": issue.get("title"),
                "state": issue.get("state"),
                "user": (issue.get("user") or {}).get("login"),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "comments": issue.get("comments"),
                "html_url": issue.get("html_url"),
            }
        )
    meta = _paging_meta(resp.get("headers", {}), page, per_page, len(result))
    return {
        "success": True,
        "data": result,
        "repo": repo,
        "state": state,
        **meta,
    }


def list_prs(
    repo: Optional[str] = None,
    state: str = "open",
    page: Any = 1,
    per_page: Any = _MAX_PER_PAGE,
) -> Dict[str, Any]:
    """List repository Pull Requests, with pagination.

    Returns data as current page PR list, plus total/has_more/page/per_page pagination metadata.
    """
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    state = (state or "open").strip()
    if state not in ("open", "closed", "all"):
        return {"success": False, "error": f"Invalid state: {state}"}
    page, per_page = _normalize_paging(page, per_page)
    resp = gh_common.api_request(
        "GET",
        f"/repos/{repo}/pulls?state={state}&per_page={per_page}&page={page}",
        token=gh_common.get_token(),
    )
    if not resp["success"]:
        return {"success": False, "error": resp["error"]}
    prs = resp["data"]
    if not isinstance(prs, list):
        return {"success": False, "error": "Unexpected response format"}
    result = []
    for pr in prs:
        result.append(
            {
                "number": pr.get("number"),
                "title": pr.get("title"),
                "state": pr.get("state"),
                "user": (pr.get("user") or {}).get("login"),
                "created_at": pr.get("created_at"),
                "updated_at": pr.get("updated_at"),
                "html_url": pr.get("html_url"),
            }
        )
    meta = _paging_meta(resp.get("headers", {}), page, per_page, len(result))
    return {
        "success": True,
        "data": result,
        "repo": repo,
        "state": state,
        **meta,
    }


def get_issue(
    repo: Optional[str] = None, number: Optional[int] = None
) -> Dict[str, Any]:
    """View single Issue details."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (issue number)"}
    resp = gh_common.api_request(
        "GET", f"/repos/{repo}/issues/{number}", token=gh_common.get_token()
    )
    if not resp["success"]:
        return {"success": False, "error": resp["error"]}
    issue = resp["data"]
    if not isinstance(issue, dict):
        return {"success": False, "error": "Unexpected response format"}
    result = {
        "number": issue.get("number"),
        "title": issue.get("title"),
        "state": issue.get("state"),
        "user": (issue.get("user") or {}).get("login"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "comments": issue.get("comments"),
        "labels": [label.get("name") for label in (issue.get("labels") or [])],
        "body": issue.get("body"),
        "html_url": issue.get("html_url"),
    }
    return {"success": True, "data": result}


def get_pr(repo: Optional[str] = None, number: Optional[int] = None) -> Dict[str, Any]:
    """View single Pull Request details."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (PR number)"}
    resp = gh_common.api_request(
        "GET", f"/repos/{repo}/pulls/{number}", token=gh_common.get_token()
    )
    if not resp["success"]:
        return {"success": False, "error": resp["error"]}
    pr = resp["data"]
    if not isinstance(pr, dict):
        return {"success": False, "error": "Unexpected response format"}
    result = {
        "number": pr.get("number"),
        "title": pr.get("title"),
        "state": pr.get("state"),
        "user": (pr.get("user") or {}).get("login"),
        "created_at": pr.get("created_at"),
        "updated_at": pr.get("updated_at"),
        "merged": pr.get("merged"),
        "mergeable": pr.get("mergeable"),
        "head": (pr.get("head") or {}).get("ref"),
        "base": (pr.get("base") or {}).get("ref"),
        "body": pr.get("body"),
        "html_url": pr.get("html_url"),
    }
    return {"success": True, "data": result}


def list_comments(
    repo: Optional[str] = None, number: Optional[int] = None
) -> Dict[str, Any]:
    """List comments for an Issue or PR."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (issue/PR number)"}
    resp = gh_common.api_request(
        "GET",
        f"/repos/{repo}/issues/{number}/comments?per_page=100",
        token=gh_common.get_token(),
    )
    if not resp["success"]:
        return {"success": False, "error": resp["error"]}
    comments = resp["data"]
    if not isinstance(comments, list):
        return {"success": False, "error": "Unexpected response format"}
    result = []
    for c in comments:
        result.append(
            {
                "user": (c.get("user") or {}).get("login"),
                "body": c.get("body"),
                "created_at": c.get("created_at"),
                "html_url": c.get("html_url"),
            }
        )
    return {"success": True, "data": result}


# ---------------------------------------------------------------------------
# Write operations (require logged-in token)
# ---------------------------------------------------------------------------
def merge_pr(
    repo: Optional[str] = None,
    number: Optional[int] = None,
    merge_method: str = "merge",
) -> Dict[str, Any]:
    """Merge a Pull Request."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (PR number)"}
    token = gh_common.get_token()
    if not token:
        return {
            "success": False,
            "error": "Merging PR requires login. Please run gh auth login in terminal to log in to GitHub first.",
        }
    merge_method = (merge_method or "merge").strip()
    resp = gh_common.api_request(
        "PUT",
        f"/repos/{repo}/pulls/{number}/merge",
        token=token,
        data={"merge_method": merge_method},
    )
    if not resp["success"]:
        hint = gh_common.auth_error_hint(resp["status"])
        return {"success": False, "error": resp["error"] + (" " + hint if hint else "")}
    return {"success": True, "message": f"PR #{number} merged successfully ({merge_method})"}


def comment(
    repo: Optional[str] = None,
    number: Optional[int] = None,
    body: Optional[str] = None,
) -> Dict[str, Any]:
    """Post a comment on an Issue or PR."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (issue/PR number)"}
    body = (body or "").strip()
    if not body:
        return {"success": False, "error": "Please provide body (comment content)"}
    token = gh_common.get_token()
    if not token:
        return {
            "success": False,
            "error": "Posting comment requires login. Please run gh auth login in terminal to log in to GitHub first.",
        }
    resp = gh_common.api_request(
        "POST",
        f"/repos/{repo}/issues/{number}/comments",
        token=token,
        data={"body": body},
    )
    if not resp["success"]:
        hint = gh_common.auth_error_hint(resp["status"])
        return {"success": False, "error": resp["error"] + (" " + hint if hint else "")}
    return {"success": True, "message": f"Comment posted to #{number}"}


def close_issue(
    repo: Optional[str] = None, number: Optional[int] = None
) -> Dict[str, Any]:
    """Close an Issue."""
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    if number is None:
        return {"success": False, "error": "Please provide number (issue number)"}
    token = gh_common.get_token()
    if not token:
        return {
            "success": False,
            "error": "Closing issue requires login. Please run gh auth login in terminal to log in to GitHub first.",
        }
    resp = gh_common.api_request(
        "PATCH",
        f"/repos/{repo}/issues/{number}",
        token=token,
        data={"state": "closed"},
    )
    if not resp["success"]:
        hint = gh_common.auth_error_hint(resp["status"])
        return {"success": False, "error": resp["error"] + (" " + hint if hint else "")}
    return {"success": True, "message": f"Issue #{number} closed"}


# ---------------------------------------------------------------------------
# Fork / Clone (require logged-in token)
# ---------------------------------------------------------------------------
def _run_command(args: List[str], cwd: Optional[str] = None, timeout: int = 300) -> Dict[str, Any]:
    """Execute external command with args (no shell concatenation, avoids injection).

    Returns {"success": bool, "stdout": str, "stderr": str, "returncode": int}.
    Returns success=False with error when command not found or times out.
    """
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Command not found: {args[0]} (please verify it's installed)",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "error": f"Command timed out (>{timeout}s): {' '.join(args)}",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "",
            "error": str(e),
        }
    return {
        "success": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": (result.stdout or "").strip(),
        "stderr": (result.stderr or "").strip(),
        "error": "",
    }


def _current_login() -> str:
    """Get current gh logged-in username; returns empty string if not logged in."""
    res = _run_command(["gh", "api", "user", "--jq", ".login"], timeout=15)
    if not res["success"]:
        return ""
    return res["stdout"].strip()


def fork_repo(repo: Optional[str] = None) -> Dict[str, Any]:
    """Fork specified repo to current logged-in account.

    Reuses existing same-name fork (no duplicate fork). Returns:
    {"success": True, "fork_repo": "owner/repo", "message": str}.
    Returns {"success": False, "error": str} if not logged in or fork fails.
    """
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}

    login = _current_login()
    if not login:
        return {
            "success": False,
            "error": "Forking repo requires login. Please run gh auth login in terminal to log in to GitHub first.",
        }

    # Target fork name = current logged-in user / original repo name
    repo_name = repo.split("/", 1)[1]
    fork_repo = f"{login}/{repo_name}"

    # Reuse existing same-name fork
    existing = gh_common.api_request(
        "GET", f"/repos/{fork_repo}", token=gh_common.get_token()
    )
    if existing["success"]:
        return {
            "success": True,
            "fork_repo": fork_repo,
            "message": f"Same-name fork already exists, reusing: {fork_repo}",
        }

    res = _run_command(["gh", "repo", "fork", repo, "--clone=false"])
    if not res["success"]:
        detail = res["stderr"] or res["error"] or "Unknown error"
        return {"success": False, "error": f"Fork failed: {detail}"}
    return {
        "success": True,
        "fork_repo": fork_repo,
        "message": f"Forked to {fork_repo}",
    }


def clone_repo(
    repo: Optional[str] = None, target_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Clone repo into target_dir (as same-name subdirectory).

    - Reuses existing same-name subdir if it's the same repo (origin matches), no duplicate clone.
    - Errors if same-name subdir exists but origin doesn't match (different repo), to avoid overwriting user data.
    Returns {"success": True, "local_dir": str}.
    """
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}
    target_dir = (target_dir or "").strip()
    if not target_dir:
        return {"success": False, "error": "Please provide target_dir (clone target directory)"}
    if not os.path.isdir(target_dir):
        return {"success": False, "error": f"Target directory does not exist: {target_dir}"}

    repo_name = repo.split("/", 1)[1]
    local_dir = os.path.join(target_dir, repo_name)

    if os.path.exists(local_dir):
        if not os.path.isdir(local_dir):
            return {"success": False, "error": f"Target path exists and is not a directory: {local_dir}"}
        # Exists: verify it's the same repo
        existing_repo = gh_common.resolve_repo_from_dir(local_dir)
        if existing_repo == repo:
            return {
                "success": True,
                "local_dir": local_dir,
                "message": f"Directory already exists for same repo, reusing: {local_dir}",
            }
        if existing_repo:
            return {
                "success": False,
                "error": (
                    f"Target directory already exists and belongs to another repo ({existing_repo}): {local_dir}, "
                    "please choose a different target directory or remove the existing one first."
                ),
            }
        return {
            "success": False,
            "error": f"Target directory exists and is not a git repo: {local_dir}, please choose a different target directory.",
        }

    res = _run_command(["git", "clone", f"https://github.com/{repo}.git", local_dir])
    if not res["success"]:
        detail = res["stderr"] or res["error"] or "Unknown error"
        return {"success": False, "error": f"Clone failed: {detail}"}
    return {
        "success": True,
        "local_dir": local_dir,
        "message": f"Cloned to {local_dir}",
    }


def prepare_issue_repo(
    repo: Optional[str] = None, target_dir: Optional[str] = None
) -> Dict[str, Any]:
    """Combined operation: fork original repo, then clone fork to target_dir,
    and configure upstream remote pointing to original repo.

    Used for "Fork and create CodeAgent to handle" flow for custom repo Issues.
    Returns {"success": True, "fork_repo": str, "local_dir": str, "message": str}.
    """
    repo, _repo_err = _require_repo(repo)
    if _repo_err:
        return {"success": False, "error": _repo_err}

    fork_result = fork_repo(repo)
    if not fork_result.get("success"):
        return {"success": False, "error": fork_result.get("error", "Fork failed")}
    fork_repo_name = fork_result["fork_repo"]

    clone_result = clone_repo(fork_repo_name, target_dir)
    if not clone_result.get("success"):
        return {
            "success": False,
            "error": clone_result.get("error", "Clone failed"),
            "fork_repo": fork_repo_name,
        }
    local_dir = clone_result["local_dir"]

    # Set upstream to point to original repo, enabling subsequent git fetch upstream / gh pr create
    upstream_url = f"https://github.com/{repo}.git"
    upstream_msg = _ensure_upstream_remote(local_dir, upstream_url)
    return {
        "success": True,
        "fork_repo": fork_repo_name,
        "local_dir": local_dir,
        "message": f"Forked and cloned to {local_dir}; {upstream_msg}",
    }


def _ensure_upstream_remote(local_dir: str, upstream_url: str) -> str:
    """Ensure local repo has upstream remote pointing to original repo (idempotent).

    Skips if upstream with same URL already exists; updates if points to different URL.
    Returns description (for message concatenation).
    """
    existing = _run_command(
        ["git", "remote", "get-url", "upstream"], cwd=local_dir, timeout=15
    )
    if existing["success"]:
        if existing["stdout"].strip() == upstream_url:
            return "upstream already points to original repo"
        _run_command(
            ["git", "remote", "set-url", "upstream", upstream_url],
            cwd=local_dir,
            timeout=15,
        )
        return f"upstream updated to point to original repo {upstream_url}"
    res = _run_command(
        ["git", "remote", "add", "upstream", upstream_url],
        cwd=local_dir,
        timeout=15,
    )
    if not res["success"]:
        detail = res["stderr"] or res["error"] or "Unknown error"
        return f"Failed to set upstream: {detail}"
    return f"upstream now points to original repo {upstream_url}"


# ---------------------------------------------------------------------------
# Repository resolution
# ---------------------------------------------------------------------------
def resolve_repo(working_dir: Optional[str] = None) -> Dict[str, Any]:
    """Resolve GitHub repo (owner/repo) for given working directory.

    Reads git remote origin from that directory; returns empty repo for non-git
    directories or missing origin (no fallback to default repo, to avoid other
    users seeing a fixed repo after plugin release).
    Used by frontend sidebar to follow current agent's repo.
    """
    repo = gh_common.resolve_repo_from_dir(working_dir or "")
    return {"success": True, "repo": repo, "working_dir": working_dir or ""}


# Allowlist of functions callable via gateway proxy (prevents arbitrary function calls)
PUBLIC_FUNCTIONS: List[str] = [
    "list_issues",
    "list_prs",
    "get_issue",
    "get_pr",
    "list_comments",
    "merge_pr",
    "comment",
    "close_issue",
    "resolve_repo",
    "fork_repo",
    "clone_repo",
    "prepare_issue_repo",
]
