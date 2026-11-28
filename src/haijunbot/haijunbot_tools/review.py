# -*- coding: utf-8 -*-
"""Review tool: performs a single code review of the current code changes.

While CodeAgent is modifying code, the LLM can proactively call this tool during task execution to perform a code review.
This tool performs a **single review** (reusing CodeReviewer.run_single_review) and **does not run a fix loop**:
when issues are found it returns an error result directly, and the Agent (LLM) fixes them before calling again.

In non-interactive mode it works in tandem with the commit tool: after the review tool is called and the review passes, it automatically proceeds to commit.
In interactive mode there is no tandem behavior; only the review is performed.
"""

from typing import Any
from typing import Dict

from haijunbot.haijunbot_utils.output import PrettyOutput


class ReviewTool:
    """Review tool

    Performs a single code review of the current code changes; when issues are found it returns an error result for the Agent to fix on its own.
    """

    name = "review"
    description = (
        "Perform a single code review of the current code changes. If the review passes, return success; if issues are found, return failure"
        "(including the issue list); after fixing according to the issues, call this tool again. In non-interactive mode, once the review passes"
        "it will automatically proceed to commit the code."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform a single code review (tool entry point)."""
        agent = (args or {}).get("agent")

        # When disable_review is enabled, disable directly
        if agent is not None and getattr(agent, "disable_review", False):
            return {
                "success": False,
                "stdout": "",
                "stderr": "Code review is disabled (disable_review configuration is enabled), skipping review.",
            }

        try:
            result = self.run_review(agent)

            ok = bool(result.get("ok", True))
            issues = result.get("issues", []) or []
            summary = result.get("summary", "") or ""

            if ok:
                # Review passed: in non-interactive mode automatically proceed to commit (tandem)
                if agent is not None and getattr(agent, "non_interactive", False):
                    self._auto_commit(agent)
                return {
                    "success": True,
                    "stdout": summary or "Code review passed",
                    "stderr": "",
                }

            # Review found issues: return an error result for the Agent to fix on its own
            issues_text = "\n".join(
                f"{i + 1}. [{issue.get('type', 'unknown')}] {issue.get('description', 'no description')}"
                f"\n   Location: {issue.get('location', 'unknown')}"
                f"\n   Suggestion: {issue.get('suggestion', 'no suggestion')}"
                for i, issue in enumerate(issues)
            )
            stderr = f"Code review found issues:\n{issues_text}"
            if summary:
                stderr += f"\n\nReview summary: {summary}"
            return {
                "success": False,
                "stdout": "",
                "stderr": stderr,
            }

        except Exception as e:
            PrettyOutput.auto_print(f"❌ Review failed\n\n{str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Review failed: {str(e)}",
            }

    def run_review(self, agent: Any) -> Dict[str, Any]:
        """Perform a single code review and return a structured result (reused by execute and the <Review> command).

        Returns:
            dict: Review result, containing the ok/issues/summary fields
        """
        from haijunbot.haijunbot_code_agent.code_reviewer import CodeReviewer

        # Construct CodeReviewer (reusing the agent's model and starting commit)
        reviewer = CodeReviewer(
            model=getattr(agent, "model", None),
            start_commit=getattr(agent, "start_commit", None),
            non_interactive=getattr(agent, "non_interactive", True),
            quick_mode=getattr(agent, "quick_mode", False),
        )
        return reviewer.run_single_review()

    def _auto_commit(self, agent: Any) -> None:
        """In non-interactive mode, automatically commit after the review passes (tandem).

        Reuses CommitTool's compressed checkpoint + formal commit logic.
        Passing skip_review=True skips the duplicate review inside commit (this tool just passed the review).
        """
        try:
            from haijunbot.haijunbot_tools.commit import CommitTool

            commit_tool = CommitTool()
            commit_result = commit_tool.execute({"agent": agent, "skip_review": True})
            if commit_result.get("success"):
                PrettyOutput.auto_print("✅ Review passed, code automatically committed")
            else:
                PrettyOutput.auto_print(
                    f"⚠️ Review passed but auto-commit failed: {commit_result.get('stderr', '')}"
                )
        except Exception as e:
            PrettyOutput.auto_print(f"⚠️ Review passed but auto-commit raised an exception: {e}")
