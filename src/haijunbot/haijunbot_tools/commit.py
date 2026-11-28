# -*- coding: utf-8 -*-
"""Commit tool: squashes the CheckPoint temporary commits produced by CodeAgent into one formal commit.

While CodeAgent is modifying code, each change automatically generates a temporary commit starting with "CheckPoint #N"
(see haijunbot_utils.git_utils.handle_commit_workflow). These temporary
commits are only used for process rollback and should not enter history directly. When a requirement is truly complete, call this tool:

1. Find the most recent non-CheckPoint commit as the squash starting point;
2. If there are CheckPoint temporary commits after the starting point, use `git reset --soft <start>` to squash them
   all into the staging area;
3. Reuse GitCommitTool to generate a formal commit message with the LLM based on the staging area diff and commit.

The optional prefix / suffix arguments add a prefix/suffix to the commit message.
"""

import subprocess
from typing import Any
from typing import Dict

from haijunbot.haijunbot_git_utils.git_commiter import GitCommitTool
from haijunbot.haijunbot_utils.git_utils import find_recent_non_checkout_commit
from haijunbot.haijunbot_utils.git_utils import get_latest_commit_hash
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.utils import decode_output


class CommitTool:
    """Commit tool

    Squashes the CheckPoint temporary commits produced by CodeAgent into one formal commit.
    """

    name = "commit"
    description = (
        "Generate a real Git commit. While CodeAgent is modifying code, each change generates a "
        "CheckPoint temporary commit (only used for process rollback); when a requirement is truly complete, call this tool, "
        "and it will automatically squash these CheckPoint temporary commits into one formal commit (generating the commit message with the LLM)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "prefix": {
                "type": "string",
                "description": "Commit message prefix (optional). This prefix is prepended to the formal commit message (the LLM-generated subject line); leave it empty unless there is a special requirement, to avoid affecting the standardization and readability of the commit message.",
            },
            "suffix": {
                "type": "string",
                "description": "Commit message suffix (optional, appended after the generated message)",
            },
        },
        "required": [],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Squash checkpoints and generate a formal commit."""
        prefix = str((args or {}).get("prefix") or "").strip()
        suffix = str((args or {}).get("suffix") or "").strip()
        agent = (args or {}).get("agent")
        skip_review = bool((args or {}).get("skip_review", False))

        try:
            # In non-interactive mode, works in tandem with review: when review is not disabled and not explicitly skipped, review first and then commit.
            # Only commit if the review passes; if the review finds issues, return an error and do not commit.
            if (
                not skip_review
                and agent is not None
                and getattr(agent, "non_interactive", False)
                and not getattr(agent, "disable_review", False)
            ):
                review_result = self._run_review(agent)
                if not review_result.get("ok", True):
                    issues = review_result.get("issues", []) or []
                    issues_text = "\n".join(
                        f"{i + 1}. [{issue.get('type', 'unknown')}] {issue.get('description', 'no description')}"
                        f"\n   Location: {issue.get('location', 'unknown')}"
                        f"\n   Suggestion: {issue.get('suggestion', 'no suggestion')}"
                        for i, issue in enumerate(issues)
                    )
                    stderr = f"Code review did not pass; commit canceled:\n{issues_text}"
                    if review_result.get("summary"):
                        stderr += f"\n\nReview summary: {review_result['summary']}"
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": stderr,
                    }

            # 1. Find the squash starting point: the most recent non-CheckPoint commit
            start = find_recent_non_checkout_commit()
            current_head = get_latest_commit_hash()

            if not start:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Unable to determine the squash starting point (no non-CheckPoint commit was found)",
                }

            # 2. If there are CheckPoint temporary commits after the starting point, squash them into the staging area
            if start != current_head:
                PrettyOutput.auto_print(
                    f"ℹ️ CheckPoint temporary commits detected, squashing to {start[:7]} ..."
                )
                result = subprocess.run(
                    ["git", "reset", "--soft", start],
                    capture_output=True,
                    text=False,
                    check=False,
                )
                if result.returncode != 0:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": f"Failed to squash checkpoints: {decode_output(result.stderr)}",
                    }

            # 3. Reuse GitCommitTool to generate the formal commit (based on the staging area/working tree diff)
            git_commiter = GitCommitTool()
            commit_args: Dict[str, Any] = {}
            if prefix:
                commit_args["prefix"] = prefix
            if suffix:
                commit_args["suffix"] = suffix
            commit_result = git_commiter.execute(commit_args)

            # 4. After a successful commit, automatically save the current session for later recovery
            if commit_result.get("success"):
                self._save_session_after_commit(args)

            return commit_result

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Commit failed\n\n{str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Commit failed: {str(e)}",
            }

    def _run_review(self, agent: Any) -> Dict[str, Any]:
        """Non-interactive tandem: perform a single code review (reusing CodeReviewer.run_single_review).

        Returns:
            dict: Review result, containing the ok/issues/summary fields
        """
        try:
            from haijunbot.haijunbot_code_agent.code_reviewer import CodeReviewer

            reviewer = CodeReviewer(
                model=getattr(agent, "model", None),
                start_commit=getattr(agent, "start_commit", None),
                non_interactive=getattr(agent, "non_interactive", True),
                quick_mode=getattr(agent, "quick_mode", False),
            )
            return reviewer.run_single_review()
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Tandem review failed\n\n{str(e)}")
            return {"ok": False, "issues": [], "summary": f"Tandem review failed: {str(e)}"}

    def _save_session_after_commit(self, args: Dict[str, Any]) -> None:
        """Automatically save the current session after a successful commit; a failure does not affect the commit result."""
        try:
            agent = (args or {}).get("agent")
            if agent is None or not hasattr(agent, "save_session"):
                return
            if agent.save_session():
                PrettyOutput.auto_print("💾 Session saved automatically")
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Failed to auto-save session: {e}")
