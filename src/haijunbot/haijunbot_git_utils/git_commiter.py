# -*- coding: utf-8 -*-
import os
import re
import subprocess
import tempfile
from typing import Any
from typing import Dict
from typing import Optional

import typer
import yaml  # type: ignore[import-untyped]
from rich.console import Console
from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_utils.config import get_git_commit_prompt
from haijunbot.haijunbot_utils.git_utils import confirm_add_new_files
from haijunbot.haijunbot_utils.git_utils import find_git_root_and_cd
from haijunbot.haijunbot_utils.git_utils import has_uncommitted_changes
from haijunbot.haijunbot_utils.output import PrettyOutput
from haijunbot.haijunbot_utils.tag import ct
from haijunbot.haijunbot_utils.tag import ot
from haijunbot.haijunbot_utils.utils import decode_output
from haijunbot.haijunbot_utils.utils import init_env
from haijunbot.haijunbot_utils.utils import is_context_overflow
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.config import get_max_input_token_count

app = typer.Typer(help="Git commit tool")


class GitCommitTool:
    console = Console()
    name = "git_commit_agent"
    description = "Automatically generate and execute a Git commit based on code changes"
    labels = ["git", "version_control"]
    parameters = {
        "type": "object",
        "properties": {
            "root_dir": {
                "type": "string",
                "description": "Root directory path of the Git repository (optional)",
                "default": ".",
            },
            "prefix": {
                "type": "string",
                "description": "Commit message prefix (optional)",
                "default": "",
            },
            "suffix": {
                "type": "string",
                "description": "Commit message suffix (optional)",
                "default": "",
            },
        },
        "required": [],
    }

    def _extract_commit_message(self, message) -> Optional[str]:
        """Raw extraction preserving all characters"""
        r = re.search(
            r"(?i)" + ot("COMMIT_MESSAGE") + r"\s*([\s\S]*?)\s*" + ct("COMMIT_MESSAGE"),
            message,
        )
        if r:
            # Return the raw content directly, only trimming surrounding whitespace
            return r.group(1).strip()
        return None

    def _truncate_diff_for_commit(
        self,
        git_diff: str,
        base_prompt: str,
        platform: Optional[Any] = None,
        token_ratio: float = 0.5,
    ) -> str:
        """Truncate the git diff to fit the token limit (used for commit message generation)

        Args:
            git_diff: The original git diff content
            base_prompt: The base prompt content
            llm_group: Model group name (optional)
            platform: Platform instance (optional); if provided, the remaining token count is used to decide
            token_ratio: Token usage ratio (default 0.5, i.e. 50%, considering base_prompt and response space)

        Returns:
            str: The truncated git diff (if it exceeds the limit, it is truncated and a hint and file list are added)
        """
        if not git_diff or not git_diff.strip():
            return git_diff

        # Calculate the token count of base_prompt
        base_prompt_tokens = get_context_token_count(base_prompt)

        # Get the maximum input token count
        try:
            if platform is not None:
                # Prefer using the remaining token count (more accurate, considering conversation history)
                try:
                    remaining_tokens = platform.get_remaining_token_count()
                    if remaining_tokens > 0:
                        # Reserve 20% for the response, use 50% of the remaining tokens for the diff
                        max_diff_tokens = int(remaining_tokens * token_ratio)
                        # Ensure the diff does not exceed the remaining tokens minus base_prompt
                        max_diff_tokens = min(
                            max_diff_tokens,
                            remaining_tokens - base_prompt_tokens - 1000,
                        )
                        if max_diff_tokens <= 0:
                            # If the remaining tokens are insufficient, use the file-list strategy
                            return ""
                except Exception:
                    pass

            # Fallback approach: use the input window limit
            max_input_tokens = get_max_input_token_count()
            # Reserve part for base_prompt and the response, use the given ratio as the diff limit
            max_diff_tokens = int(max_input_tokens * token_ratio)
            # Ensure the diff does not exceed the input window minus base_prompt
            max_diff_tokens = min(
                max_diff_tokens, max_input_tokens - base_prompt_tokens - 2000
            )
            if max_diff_tokens <= 0:
                # If the input window is insufficient, use the file-list strategy
                return ""
        except Exception:
            # If retrieval fails, use the default value (about 50000 tokens)
            max_input_tokens = 50000
            max_diff_tokens = int(max_input_tokens * token_ratio)
            max_diff_tokens = min(
                max_diff_tokens, max_input_tokens - base_prompt_tokens - 2000
            )
            if max_diff_tokens <= 0:
                return ""

        # Calculate the token count of the diff
        diff_token_count = get_context_token_count(git_diff)

        if diff_token_count <= max_diff_tokens:
            return git_diff

        # If the diff content is too large, truncate it
        # First extract the list of modified files
        files = set()
        # Match the "diff --git a/path b/path" format
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
                # Add a truncation hint
                truncated_lines.append("")
                truncated_lines.append(
                    "# ⚠️ diff content too large; truncated for display (commit message generation needs more context)"
                )
                truncated_lines.append(
                    f"# Original diff: {len(lines)} lines, {diff_token_count} tokens"
                )
                truncated_lines.append(
                    f"# Showing first {len(truncated_lines)} lines, about {current_tokens} tokens"
                )
                truncated_lines.append(
                    f"# Limit: {max_diff_tokens} tokens ({token_ratio * 100:.0f}% of the input window, base_prompt already considered)"
                )

                # Add the complete list of modified files
                if modified_files:
                    truncated_lines.append("")
                    truncated_lines.append(
                        f"# Complete list of modified files ({len(modified_files)} files):"
                    )
                    for file_path in modified_files:
                        truncated_lines.append(f"#   - {file_path}")

                break

            truncated_lines.append(line)
            current_tokens += line_tokens

        return "\n".join(truncated_lines)

    def _get_last_commit_hash(self) -> str:
        process = subprocess.Popen(
            ["git", "log", "-1", "--pretty=%H"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = process.communicate()
        return decode_output(stdout).strip()

    def _prepare_git_environment(self, root_dir: str) -> Optional[str]:
        """Prepare git environment by changing directory and checking for changes"""
        original_dir = os.getcwd()
        os.chdir(root_dir)
        find_git_root_and_cd()
        if not has_uncommitted_changes():
            PrettyOutput.auto_print("✅ No uncommitted changes")
            return None
        return original_dir

    def _stage_changes(self) -> None:
        """Stage all changes for commit"""

        subprocess.Popen(
            ["git", "add", "-A"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).wait()

    def execute(self, args: Dict) -> Dict[str, Any]:
        """Execute automatic commit process with support for multi-line messages and special characters"""
        try:
            original_dir = os.getcwd()
            root_dir = args.get("root_dir", ".")
            prefix = args.get("prefix", "")
            suffix = args.get("suffix", "")

            # Prepare git environment
            result = self._prepare_git_environment(root_dir)
            if result is None:
                return {"success": True, "stdout": "No changes to commit", "stderr": ""}
            original_dir = result

            confirm_add_new_files()

            if not has_uncommitted_changes():
                return {"success": True, "stdout": "No changes to commit", "stderr": ""}

            # Before running git add ., record the files currently in the staging area (they may include files manually added by the user that are gitignored)
            process = subprocess.Popen(
                ["git", "diff", "--cached", "--name-only"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
            stdout_bytes, _ = process.communicate()
            staged_files_before_add = decode_output(stdout_bytes)
            manually_staged_files = [
                f.strip() for f in staged_files_before_add.split("\n") if f.strip()
            ]

            self._stage_changes()

            # After running git add ., re-add the files that were manually staged earlier and might be ignored by gitignore
            for file_path in manually_staged_files:
                if os.path.exists(file_path):
                    # Use the -f flag to force-add files ignored by .gitignore
                    subprocess.run(["git", "add", "-f", file_path], check=False)

            # Get the diff

            # Get the file list
            files_cmd = ["git", "diff", "--cached", "--name-only"]
            process = subprocess.Popen(
                files_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=False
            )
            stdout_bytes, _ = process.communicate()
            files_output = decode_output(stdout_bytes)
            files = [f.strip() for f in files_output.split("\n") if f.strip()]
            file_count = len(files)

            # Get the full diff
            process = subprocess.Popen(
                ["git", "diff", "--cached", "--exit-code"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
            diff_bytes, _ = process.communicate()
            diff = decode_output(diff_bytes)

            try:
                # Get platform based on llm_group (thinking mode removed)
                platform = PlatformRegistry().get_normal_platform()
                platform.set_suppress_output(False)

                # Generate the commit message

                # Prepare the prompt
                custom_prompt = get_git_commit_prompt()
                base_prompt = (
                    custom_prompt
                    if custom_prompt
                    else """Generate a commit message from the code diff:
Commit messages should be written in English
# Format template
The following format MUST be used:

[HaijunBot Code Agent commit] <type>(<scope>): <subject>

[Optional] Detailed description of the changes and the reason

# Format rules
1. Type: fix (bug fix), feat (new feature), docs (documentation), style (formatting), refactor (refactoring), test (testing), chore (other)
2. Scope indicates the module or component being changed (e.g. auth, database, ui)
3. The subject line is at most 72 characters, does not end with a period, and uses the imperative mood
4. If there is a detailed description, separate the subject and the description with a blank line
5. The description should explain "what" and "why", not "how"
6. Output only the commit message, nothing else
"""
                )
                base_prompt += f"""
# Output format
{ot("COMMIT_MESSAGE")}
commit message
{ct("COMMIT_MESSAGE")}
                """

                # Skip model availability validation:
                # To avoid noise logs from platforms/proxies that do not support the get_model_list endpoint (e.g. 404),
                # platform.get_model_list() is not called here by default for model availability validation.
                # If validation needs to be restored in the future, refer to the removed logic.
                # no-op

                # Ensure platform is not None
                if not platform:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "Error: unable to create platform instance",
                    }

                upload_success = False

                # Check if content is too large
                is_large_content = is_context_overflow(diff, platform)
                use_file_list = False

                # For large content, generate the commit message directly from the file list (file upload is no longer supported)
                if is_large_content:
                    PrettyOutput.auto_print(
                        "⚠️ Diff content too large; the commit message will be generated from the file list"
                    )
                    use_file_list = True

                # Even if is_large_content is False, the total length of base_prompt + diff still needs to be checked
                # Truncate the diff to make sure it does not exceed the context limit
                if not use_file_list:
                    truncated_diff = self._truncate_diff_for_commit(
                        diff, base_prompt, platform, token_ratio=0.5
                    )
                    if not truncated_diff or truncated_diff != diff:
                        if not truncated_diff:
                            # If the diff is empty after truncation, degrade to the file-list strategy
                            PrettyOutput.auto_print(
                                "⚠️ Diff content too large (after considering base_prompt); the commit message will be generated from the file list"
                            )
                            use_file_list = True
                        else:
                            # If it was truncated, use the truncated diff
                            diff = truncated_diff
                            PrettyOutput.auto_print("⚠️ Diff content truncated to fit the context limit")

                # Prepare the full prompt based on the upload status
                if is_large_content and not use_file_list:
                    max_files_to_show = 20
                    if file_count <= max_files_to_show:
                        files_list = "\n".join(f"- {f}" for f in files)
                    else:
                        files_list = "\n".join(
                            f"- {f}" for f in files[:max_files_to_show]
                        )
                        files_list += (
                            f"\n- ...and {file_count - max_files_to_show} more files"
                        )

                    prompt = (
                        base_prompt
                        + f"""
# Change overview
- Number of changed files: {file_count}
- A file containing the complete code diff has been uploaded

# List of changed files
{files_list}

Please analyze the uploaded code diff file in detail and generate a commit message conforming to the format above.
"""
                    )

                    # Use Status to show progress
                    commit_message = platform.chat_until_success(prompt)
                elif use_file_list:
                    # Degradation strategy: generate the commit message from the file list
                    # Format the file list, truncating it if it is too long
                    max_files_to_show = 20
                    if file_count <= max_files_to_show:
                        files_list = "\n".join(f"- {f}" for f in files)
                    else:
                        files_list = "\n".join(
                            f"- {f}" for f in files[:max_files_to_show]
                        )
                        files_list += (
                            f"\n- ...and {file_count - max_files_to_show} more files"
                        )

                    prompt = (
                        base_prompt
                        + f"""
# Change overview
- Number of changed files: {file_count}

# List of changed files
{files_list}

Please generate a commit message conforming to the format above based on the file list.
"""
                    )

                    commit_message = platform.chat_until_success(prompt)
                else:
                    # Normal case: use the diff content directly
                    prompt = (
                        base_prompt
                        + f"""
# Material for analysis
{diff}

Please generate a commit message conforming to the format above based on the diff.
"""
                    )

                    commit_message = platform.chat_until_success(prompt)

                while True:
                    # Re-fetch commit_message only in specific cases
                    if (
                        not upload_success
                        and not is_large_content
                        and not commit_message
                    ):
                        commit_message = platform.chat_until_success(prompt)
                    extracted_message = self._extract_commit_message(commit_message)
                    # If extraction succeeds, break out of the loop
                    if extracted_message:
                        commit_message = extracted_message
                        # Apply prefix and suffix
                        if prefix:
                            commit_message = f"{prefix} {commit_message}"
                        if suffix:
                            commit_message = f"{commit_message}\n{suffix}"
                        # Append a Co-Authored-By trailer to reflect the collaborative identity on GitHub
                        # (contribution is still attributed by author). Do not append if it already exists.
                        co_author = "HaijunBot-AI-42 <haijunbots@gmail.com>"
                        if "co-authored-by:" not in commit_message.lower():
                            commit_message = (
                                f"{commit_message}\n\nCo-Authored-By: {co_author}"
                            )
                        break
                    prompt = f"""The format is incorrect. Please regenerate the commit message in the following format:
                    {ot("COMMIT_MESSAGE")}
                    commit message
                    {ct("COMMIT_MESSAGE")}
                    """

                    commit_message = platform.chat_until_success(prompt)

                # Execute the commit

                # Windows compatibility: use delete=False to avoid permission errors
                tmp_file = tempfile.NamedTemporaryFile(
                    mode="w", delete=False, encoding="utf-8"
                )
                tmp_file_path = tmp_file.name
                try:
                    tmp_file.write(commit_message)
                    tmp_file.close()  # Windows requires the file to be closed before other processes can read it

                    commit_cmd = ["git", "commit", "-F", tmp_file_path]
                    process = subprocess.Popen(
                        commit_cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=False,
                    )
                    stdout_bytes, stderr_bytes = process.communicate()
                    _, stderr = decode_output(stdout_bytes), decode_output(stderr_bytes)

                    if process.returncode != 0:
                        # If the commit fails, reset the staging area
                        subprocess.run(["git", "reset", "HEAD"], check=False)

                        # After the reset, re-add the files that were manually staged earlier and might be gitignored
                        for file_path in manually_staged_files:
                            if os.path.exists(file_path):
                                # Use the -f flag to force-add files ignored by .gitignore
                                subprocess.run(
                                    ["git", "add", "-f", file_path], check=False
                                )

                        error_msg = (
                            stderr.strip() if stderr else "Unknown git commit error"
                        )
                        raise Exception(f"Git commit failed: {error_msg}")

                finally:
                    # Manually delete the temporary file
                    try:
                        os.unlink(tmp_file_path)
                    except Exception:
                        pass

                commit_hash = self._get_last_commit_hash()
            finally:
                pass

            PrettyOutput.auto_print(
                f"✅ Commit successful\n\nCommit hash: {commit_hash}\nCommit message:\n{commit_message}"
            )

            return {
                "success": True,
                "stdout": yaml.safe_dump(
                    {"commit_hash": commit_hash, "commit_message": commit_message},
                    allow_unicode=True,
                ),
                "stderr": "",
            }
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Commit failed\n\n{str(e)}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Commit failed: {str(e)}",
            }
        finally:
            # Always restore original directory
            os.chdir(original_dir)


@app.command()
def eli(
    root_dir: str = typer.Option(".", "--root-dir", help="Root directory path of the Git repository"),
    prefix: str = typer.Option(
        "",
        "--prefix",
        help="Commit message prefix (space-separated)",
    ),
    suffix: str = typer.Option(
        "",
        "--suffix",
        help="Commit message suffix (newline-separated)",
    ),
    llm_group: Optional[str] = typer.Option(
        None, "-g", "--llm-group", help="Model group to use, overriding the configuration file setting"
    ),
):
    init_env(llm_group=llm_group)
    tool = GitCommitTool()
    tool.execute(
        {
            "root_dir": root_dir,
            "prefix": prefix,
            "suffix": suffix,
        }
    )


def main():
    """Application entry point"""
    app()


if __name__ == "__main__":
    main()
