# -*- coding: utf-8 -*-
"""Code review module.

Extract the review-related logic from CodeAgent,
Support triggering a single code review via the built-in @Review command.
"""

import json
import re
from typing import Any, Optional

from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.git_utils import (
    get_diff,
    get_diff_between_commits,
    get_latest_commit_hash,
)


class CodeReviewer:
    """Standalone code reviewer.

    Review logic extracted from CodeAgent, supporting single review and review+fix loops.
    A single review can be triggered via the @Review command, or the full review loop can be invoked internally by CodeAgent.
    """

    def __init__(
        self,
        model: Any = None,
        start_commit: Optional[str] = None,
        non_interactive: Optional[bool] = True,
        quick_mode: bool = False,
    ) -> None:
        """Initialize the code reviewer.

        Args:
            model: Model instance (used for generating review objectives)
            start_commit: Starting commit hash
            non_interactive: Whether in non-interactive mode
            quick_mode: Whether in quick mode
        """
        self.model = model
        self.start_commit = start_commit
        self.non_interactive = non_interactive
        self.quick_mode = quick_mode

    def truncate_diff_for_review(self, git_diff: str, token_ratio: float = 0.4) -> str:
        """Truncate git diff to fit the token limit (used for review)."""
        if not git_diff or not git_diff.strip():
            return git_diff

        from haijunbot.haijunbot_utils.embedding import get_context_token_count
        from haijunbot.haijunbot_utils.config import get_max_input_token_count

        max_input_tokens = get_max_input_token_count()
        max_diff_tokens = int(max_input_tokens * token_ratio)
        diff_token_count = get_context_token_count(git_diff)

        if diff_token_count <= max_diff_tokens:
            return git_diff

        files = set()
        pattern = r"^diff --git a/([^\s]+) b/([^\s]+)$"
        for line in git_diff.split("\n"):
            match = re.match(pattern, line)
            if match:
                file_a = match.group(1)
                file_b = match.group(2)
                files.add(file_b)
                if file_a != file_b:
                    files.add(file_a)
        modified_files = sorted(list(files))

        lines = git_diff.split("\n")
        truncated_lines = []
        current_tokens = 0

        for line in lines:
            line_tokens = get_context_token_count(line)
            if current_tokens + line_tokens > max_diff_tokens:
                truncated_lines.append("")
                truncated_lines.append(
                    "# ⚠️ Diff content is too large, display has been truncated. To view the full content, please use the git diff command."
                )
                truncated_lines.append(
                    f"# Original diff has {len(lines)} lines in total, {diff_token_count} tokens"
                )
                truncated_lines.append(
                    f"# Showing first {len(truncated_lines) - 3} lines, about {current_tokens} tokens"
                )
                truncated_lines.append(
                    f"# Limit: {max_diff_tokens} tokens ({token_ratio * 100:.0f}% of the input window)"
                )

                if self.start_commit:
                    truncated_lines.append("")
                    truncated_lines.append(f"# Starting Commit ID: {self.start_commit}")

                if modified_files:
                    truncated_lines.append("")
                    truncated_lines.append(
                        f"# Complete list of modified files ({len(modified_files)} files in total):"
                    )
                    for file_path in modified_files:
                        truncated_lines.append(f"#   - {file_path}")

                break

            truncated_lines.append(line)
            current_tokens += line_tokens

        return "\n".join(truncated_lines)

    def get_modified_files_list(self) -> Optional[str]:
        """Extract the modified file list from the changes between start_commit and HEAD.

        Returns a formatted file list string, without specific diff content,
        to avoid inducing the model to generate acceptance criteria tailored to the code based on the diff.
        """
        if self.start_commit:
            git_diff = get_diff_between_commits(self.start_commit)
        else:
            git_diff = self.check_and_get_git_diff()

        if not git_diff:
            return None

        files = set()
        pattern = r"^diff --git a/([^\s]+) b/([^\s]+)$"
        for line in git_diff.split("\n"):
            match = re.match(pattern, line)
            if match:
                file_a = match.group(1)
                file_b = match.group(2)
                files.add(file_b)
                if file_a != file_b:
                    files.add(file_a)

        if not files:
            return None

        return "\n".join(f"  - {f}" for f in sorted(files))

    def generate_review_target(self, max_retries: int = 3) -> str:
        """Generate the objectives and acceptance criteria for the code review.

        Note: This method only passes in the modified file list rather than the full diff,
        to avoid the model generating misleading acceptance criteria based on specific code changes.
        Acceptance criteria should be generated independently based on the conversation history, with the file list serving only as a reference for locating.
        """
        from haijunbot.haijunbot_platform.registry import PlatformRegistry

        if self.model is None:
            PrettyOutput.auto_print("⚠ Model instance does not exist, cannot generate review objectives")
            return "Task objective: Complete user requirements\nAcceptance criteria: Code changes should correctly complete user requirements"

        messages = self.model.get_messages()
        if not messages:
            PrettyOutput.auto_print("⚠ No history messages, cannot generate review objectives")
            return "Task objective: Complete user requirements\nAcceptance criteria: Code changes should correctly complete user requirements"

        try:
            new_model = PlatformRegistry().get_smart_platform()
        except Exception as e:
            PrettyOutput.auto_print(f"⚠ Failed to create model instance: {e}")
            return "Task objective: Complete user requirements\nAcceptance criteria: Code changes should correctly complete user requirements"

        new_model.set_messages(messages)
        new_model.set_suppress_output(False)

        # Only obtain the modified file list, do not pass the full diff, to avoid misleading acceptance criteria
        modified_files = self.get_modified_files_list()

        prompt = """Please, based on the conversation history, summarize the task objectives and acceptance criteria that this code review should focus on.

[Important Notes]
- **Only focus on the currently uncommitted code changes**: If the conversation history contains multiple fix iterations, please only focus on the final current code state
- **Ignore already committed code**: Do not include code that has already been committed in the conversation history into the acceptance criteria
- **Generate acceptance criteria independently**: Acceptance criteria should be generated independently based on the user requirements in the conversation history, and should not be misled by specific code implementation details. Below only the modified file list is provided as a reference for locating, without specific code change content

Please ensure the output contains the following four key parts (these keywords must be included):
1. Task objective - Explain what this code modification should accomplish
2. Acceptance criteria - Specific, verifiable criteria used to judge whether the code modification is correctly completed
3. Key change points - The key change points involved in this modification
4. Key information navigation - Provide the key information locations to focus on during review, including:
   - Key file paths: The complete paths of the files involved in this modification
   - Key function/class locations: The function names, class names involved in the modification, and their files and line number ranges
   - Key dependencies: The upstream and downstream modules or interfaces affected by the modification
   - Key configurations/constants: The configuration items involved and the locations of constant definitions

Please do not suppress the model's output, summarize as detailed and complete as possible. No need to output in JSON format.

**Important: Your output must include the following 4 keywords verbatim (they cannot be omitted or replaced with synonyms), otherwise validation will fail:**
- "Task objective"
- "Acceptance criteria"
- "Key change points"
- "Key information navigation"""

        # Only pass in the modified file list, do not pass the full diff
        if modified_files:
            prompt += f"\n\n[Modified file list]\n{modified_files}"

        # If there is a start_commit, append a hint to the prompt to only review code after that commit
        if self.start_commit:
            prompt += (
                f"\n\n<start_commit_context>\n"
                f"The initial Git Commit for this task is: `{self.start_commit}`\n"
                f"Please only review code changes after this commit,"
                f"there is no need to review code that already existed before this commit.\n"
                f"</start_commit_context>"
            )

        required_keywords = ["Task objective", "Acceptance criteria", "Key change points", "Key information navigation"]

        for retry in range(max_retries):
            try:
                if retry == 0:
                    PrettyOutput.auto_print("🎯 Generating code review objectives...")
                else:
                    PrettyOutput.auto_print(
                        f"🔧 Retry {retry + 1}/{max_retries} generating review objectives..."
                    )

                response = new_model.chat_until_success(prompt)
                if not response:
                    continue

                response_str = str(response)

                missing_keywords = [
                    kw for kw in required_keywords if kw not in response_str
                ]
                if missing_keywords:
                    PrettyOutput.auto_print(
                        f"⚠ Review objectives are missing keywords: {', '.join(missing_keywords)}"
                    )
                    prompt += f"\n\nYour last output was as follows:\n```\n{response_str}\n```\n\nNote: The last output is missing the following keywords: {', '.join(missing_keywords)}, please complete it based on the last output, ensuring all keywords appear."
                    continue

                PrettyOutput.auto_print("✅ Review objectives generated successfully")
                PrettyOutput.print_markdown(response_str, title="📋 Code review objectives")
                return response_str

            except Exception as e:
                PrettyOutput.auto_print(f"⚠ Error occurred while generating review objectives: {e}")
                continue

        user_input = ""
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                user_input = msg["content"]
                break

        if user_input:
            PrettyOutput.auto_print("⚠ All retries failed, falling back to the user's original requirements")
            return f"Task objective: {user_input}\nAcceptance criteria: Code changes should correctly complete user requirements"
        else:
            PrettyOutput.auto_print("⚠ All retries failed, using default review objectives")
            return "Task objective: Complete user requirements\nAcceptance criteria: Code changes should correctly complete user requirements"

    def build_review_prompts(
        self,
        review_target: str,
        git_diff: str,
        modification_history: Optional[str] = None,
        start_commit: Optional[str] = None,
    ) -> tuple:
        """Build the prompts for the review Agent."""
        system_prompt = """You are a code review expert. Your task is to review whether the code changes correctly complete the user's requirements.

Review standards:
1. Functional completeness: Does the code change fully implement all feature points of the user's requirements?
2. Code correctness: Is the logic of the modified code correct, are there any obvious bugs or errors?
3. Code quality: Does the code conform to best practices, are there any obvious code smells?
4. Potential risks: Could the modification introduce new problems or break existing functionality?

Review requirements:
- Carefully read the user's requirements, code generation summary (summary), and code changes (git diff)
- **Fully verify the key information in the code generation summary**: Do not blindly trust the summary; you must verify it item by item against the git diff and the actual code
- If you need to understand more context, you must use the read_code tool to read the relevant files to verify whether the behavior/location/file mentioned in the summary actually exists and matches the description
- Conduct the review based on the actual code, do not make assumptions out of thin air
- If the code generation summary is inconsistent with the actual code, the actual code shall prevail, and the inconsistency should be recorded as an issue
- Only focus on issues related to this modification, do not review unrelated code
- **Respect the user's original requirements**: If the user explicitly supports a certain approach or implementation in the requirements, it should not be judged as a risk or issue, unless the approach has obvious errors or violates security principles"""

        commit_info = f"[Starting Commit]\n{start_commit}\n\n" if start_commit else ""
        user_prompt = f"""Please review whether the following code changes correctly complete the user's requirements.

[Task objectives and acceptance criteria]
{review_target}

{commit_info}[Complete modification history]
{modification_history if modification_history else "No modification history (if empty, it means the main Agent did not generate a summary or did not perform fixes)"}

[Code changes (Git Diff)]
```diff
{git_diff}

```

Please carefully review the code changes, and pay special attention to:

- The modification history includes summaries of the initial generation and all fix stages
- Do not directly trust the descriptions in the summary, but treat them as "statements to be verified"
- For each key modification point mentioned in the summary (such as function/file/behavior changes), corresponding evidence should be found in the git diff or the actual code
- If the summary is found to be inconsistent with the actual code, it must be pointed out in the review result

If needed, you can use the read_code tool to view more context.

If the review is complete, directly output {ot("!!!COMPLETE!!!")}, do not output anything else.
"""

        summary_prompt = """Please output the review result in JSON format, the format is as follows:

```json
{
  "ok": true/false,
  "issues": [
    {
      "type": "Issue type",
      "description": "Issue description",
      "location": "Issue location (file:line number)",
      "suggestion": "Fix suggestion"
    }
  ],
  "summary": "Review summary"
}
```

Note:
- If the code changes fully satisfy the user's requirements and there are no obvious problems, set ok to true
- If there are problems that need fixing, set ok to false, and list all problems in issues
- Each problem should provide specific fix suggestions"""

        return system_prompt, user_prompt, summary_prompt

    def _try_parse_json(self, content: str) -> tuple:
        """Try to parse JSON, return (success, result, json string)"""
        # First try to match the ```json ... ``` code block
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try to match a bare JSON object
            json_match = re.search(r'\{[\s\S]*"ok"[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group(0)
            else:
                return False, None, None

        try:
            result = json.loads(json_str)
            if isinstance(result, dict):
                return True, result, json_str
            else:
                return False, None, json_str
        except json.JSONDecodeError:
            return False, None, json_str

    def parse_review_result(
        self,
        review_result: str,
        review_agent: Optional[Any] = None,
        max_retries: int = 3,
    ) -> dict:
        """Parse the review result, supporting format repair.

        Args:
            review_result: The output of the review Agent
            review_agent: review Agent instance, used for format repair (optional)
            max_retries: Maximum number of retries

        Returns:
            dict: The parsed review result, containing the ok/issues/summary fields
        """
        default_result = {"ok": True, "issues": [], "summary": "Review complete"}

        if not review_result or not review_result.strip():
            return default_result

        # First parse attempt
        success, result, json_str = self._try_parse_json(review_result)
        if success and result is not None:
            return {
                "ok": result.get("ok", True),
                "issues": result.get("issues", []),
                "summary": result.get("summary", ""),
            }

        # If review_agent is not provided, repair is not possible, fall back to simple parsing
        if review_agent is None:
            # Try to extract JSON from the result (compatible with legacy logic)
            json_pattern = r"```json\s*\n([\s\S]*?)\n\s*```"
            json_matches = re.findall(json_pattern, review_result)

            if json_matches:
                for json_str in reversed(json_matches):
                    try:
                        result = json.loads(json_str.strip())
                        if isinstance(result, dict) and "ok" in result:
                            return result
                    except json.JSONDecodeError:
                        continue

            # Try to directly parse the entire result
            try:
                result = json.loads(review_result.strip())
                if isinstance(result, dict) and "ok" in result:
                    return result
            except json.JSONDecodeError:
                pass

            # Try to find JSON surrounded by curly braces
            brace_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
            brace_matches = re.findall(brace_pattern, review_result)
            if brace_matches:
                for match in reversed(brace_matches):
                    try:
                        result = json.loads(match)
                        if isinstance(result, dict) and "ok" in result:
                            return result
                    except json.JSONDecodeError:
                        continue

            # If it cannot be parsed as JSON, check whether it contains pass/fail keywords
            result_lower = review_result.lower()
            if any(
                kw in result_lower
                for kw in ["pass", "pass", "ok", "no issue", "no problem", "no problem"]
            ):
                return default_result

            if any(
                kw in result_lower
                for kw in [
                    "issue",
                    "issue",
                    "bug",
                    "error",
                    "risk",
                    "risk",
                    "failure",
                    "fail",
                ]
            ):
                return {
                    "ok": False,
                    "issues": [
                        {
                            "type": "Unresolved",
                            "description": review_result,
                            "location": "Unknown",
                            "suggestion": "Please check manually",
                        }
                    ],
                    "summary": "The review found possible issues but could not automatically parse the detailed results",
                }

            return default_result

        # Try to fix the format
        summary = review_result
        for retry in range(max_retries):
            PrettyOutput.auto_print(
                f"🔧 Attempt {retry + 1}/{max_retries} to fix JSON format..."
            )

            fix_prompt = f"""
The previous review reply had an incorrect format and could not be parsed as valid JSON.

Original reply content:
```
{summary}
```

Please reorganize your reply strictly according to the following JSON format:

```json
{{
    "ok": true/false,  // indicates whether the code passed the review
    "summary": "Overall assessment and suggestions",  // brief summary
    "issues": [  // list of issues, an empty array if there are no issues
        {{
            "type": "issue type",  // e.g.: bug, style, performance, security, etc.
            "description": "issue description",
            "location": "issue location",  // file name and line number
            "suggestion": "fix suggestion"
        }}
    ]
}}
```

Ensure the reply contains only the above JSON format and no other explanation or text."""

            try:
                # Use review_agent's underlying model for repair, keeping review_agent's dedicated configuration and system prompt
                fixed_summary = review_agent.model.chat_until_success(fix_prompt)
                if fixed_summary:
                    success, result, _ = self._try_parse_json(str(fixed_summary))
                    if success and result is not None:
                        PrettyOutput.auto_print(
                            f"✅ JSON format fixed successfully (attempt {retry + 1})"
                        )
                        return {
                            "ok": result.get("ok", True),
                            "issues": result.get("issues", []),
                            "summary": result.get("summary", ""),
                        }
                    else:
                        PrettyOutput.auto_print("⚠ The fixed JSON still cannot be parsed")
                        summary = str(fixed_summary)  # Continue trying with the fixed content
                else:
                    PrettyOutput.auto_print("⚠ Repair returned no result")
            except Exception as e:
                PrettyOutput.auto_print(f"⚠ Error while fixing JSON format: {e}")

        # All 3 repair attempts failed, mark as needing a re-review
        PrettyOutput.auto_print("❌ JSON format repair failed, a re-review is needed")
        return {
            "ok": False,
            "issues": [],
            "summary": "JSON_FORMAT_ERROR",
            "need_re_review": True,
        }

    def check_and_get_git_diff(self) -> Optional[str]:
        """Check and obtain git diff."""
        try:
            if self.start_commit:
                latest_commit = get_latest_commit_hash()
                if latest_commit and self.start_commit != latest_commit:
                    git_diff = get_diff_between_commits(
                        self.start_commit, latest_commit
                    )
                else:
                    git_diff = get_diff()
            else:
                git_diff = get_diff()
        except Exception as e:
            PrettyOutput.auto_print(f"⚠ Failed to obtain git diff: {e}")
            return None

        if not git_diff or not git_diff.strip():
            return None

        return git_diff

    def run_single_review(
        self,
        review_target: Optional[str] = None,
        modification_history: Optional[str] = None,
        use_tools: Optional[list] = None,
        non_interactive: Optional[bool] = None,
        quick_mode: Optional[bool] = None,
    ) -> dict:
        """Execute a single code review (without the fix loop).

        Called by the @Review command, it executes one review and returns the result.

        Args:
            review_target: review target (auto-generated if None)
            modification_history: modification history
            use_tools: list of tools used by the Agent (defaults to None, using the built-in default)
            non_interactive: whether in non-interactive mode (defaults to the setting at initialization)
            quick_mode: whether in quick mode (defaults to the setting at initialization)

        Returns:
            dict: review result containing the ok/issues/summary fields
        """
        # 1. Obtain git diff
        git_diff = self.check_and_get_git_diff()
        if not git_diff:
            PrettyOutput.auto_print("⚠ No code changes detected, no review needed")
            return {"ok": True, "issues": [], "summary": "No code changes to review"}

        # 2. Truncate diff
        git_diff = self.truncate_diff_for_review(git_diff)

        # 3. Generate review target (if not provided)
        if not review_target:
            review_target = self.generate_review_target()

        # 4. Build prompts
        system_prompt, user_prompt, summary_prompt = self.build_review_prompts(
            review_target=review_target,
            git_diff=git_diff,
            modification_history=modification_history,
            start_commit=self.start_commit,
        )

        # 5. Create the review Agent and execute
        from haijunbot.haijunbot_platform.registry import PlatformRegistry
        from haijunbot.haijunbot_agent import Agent

        try:
            review_model = PlatformRegistry().get_smart_platform()
        except Exception as e:
            PrettyOutput.auto_print(f"⚠ Failed to create review model: {e}")
            return {"ok": True, "issues": [], "summary": f"Failed to create review model: {e}"}

        # Use the passed-in parameters or the settings at initialization
        effective_non_interactive = (
            non_interactive if non_interactive is not None else self.non_interactive
        )
        effective_quick_mode = quick_mode if quick_mode is not None else self.quick_mode

        if use_tools is not None:
            review_agent = Agent(
                model=review_model,
                system_prompt=system_prompt,
                name="Code Reviewer",
                need_summary=True,
                summary_prompt=summary_prompt,
                use_methodology=False,
                use_analysis=False,
                non_interactive=effective_non_interactive,
                quick_mode=effective_quick_mode,
                use_tools=use_tools,
            )
        else:
            review_agent = Agent(
                model=review_model,
                system_prompt=system_prompt,
                name="Code Reviewer",
                need_summary=True,
                summary_prompt=summary_prompt,
                use_methodology=False,
                use_analysis=False,
                non_interactive=effective_non_interactive,
                quick_mode=effective_quick_mode,
            )

        PrettyOutput.auto_print("🔍 Performing code review...")
        review_result = review_agent.run(user_prompt)

        # 6. Parse the review result
        if not review_result:
            return {"ok": True, "issues": [], "summary": "Review returned no result"}

        parsed_result = self.parse_review_result(
            str(review_result), review_agent=review_agent
        )

        # 7. Display the review result
        if parsed_result.get("ok", True):
            PrettyOutput.auto_print("✅ Code review passed")
            if parsed_result.get("summary"):
                PrettyOutput.print_markdown(
                    parsed_result["summary"], title="📋 Review Summary"
                )
        else:
            PrettyOutput.auto_print("❌ Code review found issues")
            issues = parsed_result.get("issues", [])
            if issues:
                issues_text = "\n".join(
                    f"  {i + 1}. [{issue.get('type', 'Unknown')}] {issue.get('description', 'No description')}"
                    f"\n     Location: {issue.get('location', 'Unknown')}"
                    f"\n     Suggestion: {issue.get('suggestion', 'No suggestion')}"
                    for i, issue in enumerate(issues)
                )
                PrettyOutput.print_markdown(
                    f"Found {len(issues)} issues:\n{issues_text}",
                    title="⚠️ Review Issue List",
                )
            if parsed_result.get("summary"):
                PrettyOutput.print_markdown(
                    parsed_result["summary"], title="📋 Review Summary"
                )

        return parsed_result

    @staticmethod
    def build_review_fix_prompt(review_result: dict) -> str:
        """Build a fix prompt based on the review result

        Args:
            review_result: the review result dict returned by run_single_review(), containing the ok/issues/summary fields

        Returns:
            A structured fix prompt string, or an empty string if there are no issues
        """
        issues = review_result.get("issues", [])
        if not issues:
            return ""

        issues_text = "\n".join(
            f"  {i + 1}. [{issue.get('type', 'Unknown')}] {issue.get('description', 'No description')}"
            f"\n     Location: {issue.get('location', 'Unknown')}"
            f"\n     Suggestion: {issue.get('suggestion', 'No suggestion')}"
            for i, issue in enumerate(issues)
        )

        prompt = f"""The code review found the following issues, which should be fixed:

[Review Result]
{review_result.get("summary", "")}

[Issue List]
{issues_text}

Please fix according to the above issues and ensure the code correctly implements the user's requirements."""
        return prompt

    def run_review_with_fix(
        self,
        modification_history: str = "",
        max_iterations: int = 3,
        use_tools: Optional[list] = None,
        non_interactive: Optional[bool] = None,
        quick_mode: Optional[bool] = None,
        on_fix: Optional[Any] = None,
        on_generate_fix_summary: Optional[Any] = None,
        on_handle_uncommitted_changes: Optional[Any] = None,
    ) -> None:
        """Execute the review + fix loop.

        After each round of review finds issues, call the on_fix callback to fix them, then continue to the next review round,
        until the review passes or the maximum number of iterations is reached.

        Args:
            modification_history: initial modification history
            max_iterations: maximum number of review rounds (0 means unlimited)
            use_tools: list of tools used by the Agent
            non_interactive: whether in non-interactive mode
            quick_mode: whether in quick mode
            on_fix: fix callback function that receives the fix_prompt string and is used to perform the fix
            on_generate_fix_summary: callback function that generates the fix summary, returns a string
            on_handle_uncommitted_changes: callback function that handles uncommitted changes
        """
        from haijunbot.haijunbot_utils.input import user_confirm

        iteration = 0
        # If max_iterations is 0, it means unlimited review
        is_infinite = max_iterations == 0

        while is_infinite or iteration < max_iterations:
            iteration += 1

            # Ask the user before each review round starts
            effective_non_interactive = (
                non_interactive if non_interactive is not None else self.non_interactive
            )
            if not user_confirm(
                f"Proceed with code review round {iteration}?",
                default=True if effective_non_interactive else False,
            ):
                PrettyOutput.auto_print(f"ℹ️ User skipped code review round {iteration}")
                break

            # Obtain git diff
            git_diff = self.check_and_get_git_diff()
            if git_diff is None:
                return

            # Display clear prompt information before each review round starts
            if is_infinite:
                PrettyOutput.auto_print(
                    f"🔄 Code review loop - round {iteration} (unlimited mode)"
                )
            else:
                PrettyOutput.auto_print(
                    f"🔄 Code review loop - round {iteration}/{max_iterations}"
                )

            if is_infinite:
                PrettyOutput.auto_print(
                    f"🔍 Starting code review round {iteration}... (unlimited mode)"
                )
            else:
                PrettyOutput.auto_print(
                    f"🔍 Starting code review round {iteration}/{max_iterations}..."
                )

            # Apply token limit processing to git diff
            truncated_git_diff = self.truncate_diff_for_review(
                git_diff, token_ratio=0.4
            )
            if truncated_git_diff != git_diff:
                PrettyOutput.auto_print("⚠️ git diff too long, truncated to fit the token limit")

            # Generate review target
            review_target = self.generate_review_target()

            # Build review prompts
            sys_prompt, usr_prompt, sum_prompt = self.build_review_prompts(
                review_target,
                truncated_git_diff,
                modification_history,
                self.start_commit,
            )

            # Create and run the review agent
            from haijunbot.haijunbot_agent import Agent

            effective_quick_mode = (
                quick_mode if quick_mode is not None else self.quick_mode
            )

            if use_tools is not None:
                review_agent = Agent(
                    system_prompt=sys_prompt,
                    name=f"CodeReview-Agent-{iteration}",
                    summary_prompt=sum_prompt,
                    need_summary=True,
                    auto_complete=True,
                    use_tools=use_tools,
                    non_interactive=effective_non_interactive,
                    use_methodology=False,
                    use_analysis=False,
                    quick_mode=effective_quick_mode,
                )
            else:
                review_agent = Agent(
                    system_prompt=sys_prompt,
                    name=f"CodeReview-Agent-{iteration}",
                    summary_prompt=sum_prompt,
                    need_summary=True,
                    auto_complete=True,
                    non_interactive=effective_non_interactive,
                    use_methodology=False,
                    use_analysis=False,
                    quick_mode=effective_quick_mode,
                )

            # Run review
            summary = review_agent.run(usr_prompt)

            # Parse the review result, supporting format repair and re-review
            result = self.parse_review_result(
                str(summary) if summary else "", review_agent=review_agent
            )

            # Check whether a re-review is needed (3 failed attempts to fix JSON format errors)
            if result.get("need_re_review", False):
                PrettyOutput.auto_print(
                    f"🔄 JSON format repair failed, redoing code review (round {iteration})"
                )
                # Skip the current iteration and restart the review process
                continue

            if result["ok"]:
                PrettyOutput.auto_print(f"✅ Code review passed (round {iteration})")
                if result.get("summary"):
                    PrettyOutput.auto_print(f"   {result['summary']}")
                return

            # Review did not pass, a fix is needed
            PrettyOutput.auto_print(f"⚠️ Code review found issues (round {iteration})")
            for i, issue in enumerate(result.get("issues", []), 1):
                issue_type = issue.get("type", "Unknown")
                description = issue.get("description", "No description")
                location = issue.get("location", "Unknown location")
                suggestion = issue.get("suggestion", "No suggestion")
                PrettyOutput.auto_print(f"   {i}. [{issue_type}] {description}")
                PrettyOutput.auto_print(f"      Location: {location}")
                PrettyOutput.auto_print(f"      Suggestion: {suggestion}")

            # Only check whether the maximum number of iterations has been reached in non-unlimited mode
            if not is_infinite and iteration >= max_iterations:
                PrettyOutput.auto_print(
                    f"⚠️ Maximum number of review rounds reached ({max_iterations} rounds), stopping review"
                )
                return

            # Build the fix prompt
            fix_prompt = self.build_review_fix_prompt(result)

            PrettyOutput.auto_print("🔧 Starting to fix issues...")

            # Call the fix callback
            if on_fix:
                try:
                    on_fix(fix_prompt)
                except RuntimeError as e:
                    PrettyOutput.auto_print(f"⚠️ Error during fix process: {e}")
                    return

            # Handle uncommitted changes
            if on_handle_uncommitted_changes:
                on_handle_uncommitted_changes()

            # Generate a fix summary and append it to the modification history
            if on_generate_fix_summary:
                try:
                    fix_summary = on_generate_fix_summary()
                except KeyboardInterrupt:
                    PrettyOutput.auto_print("ℹ User interrupted, exiting the code review loop")
                    return
                PrettyOutput.auto_print(f"🔍 Fix summary: {fix_summary}")
                if fix_summary:
                    modification_history += (
                        f"\n\n[Fix Summary for Round {iteration}]\n{fix_summary}"
                    )
