# -*- coding: utf-8 -*-
"""Optimizer progress management module."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import cast

from haijunbot.haijunbot_utils.output import PrettyOutput

from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeOptions
from haijunbot.haijunbot_c2rust.optimizer_utils import git_head_commit
from haijunbot.haijunbot_c2rust.optimizer_utils import git_reset_hard
from haijunbot.haijunbot_c2rust.optimizer_utils import git_toplevel


class ProgressManager:
    """Progress manager, responsible for loading/saving progress and Git management."""

    def __init__(
        self,
        crate_dir: Path,
        options: OptimizeOptions,
        progress_path: Path,
    ):
        self.crate_dir = crate_dir
        self.options = options
        self.progress_path = progress_path
        self.processed: Set[str] = set()
        self.steps_completed: Set[str] = set()
        self._step_commits: Dict[str, str] = {}
        self._last_snapshot_commit: Optional[str] = None
        self._agent_before_commits: Dict[str, Optional[str]] = {}

    def load_or_reset_progress(self) -> None:
        """Load or reset progress."""
        if self.options.reset_progress:
            try:
                self.progress_path.write_text(
                    json.dumps(
                        {"processed": [], "steps_completed": []},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            except Exception as e:
                save_exception(
                    e,
                    module="haijunbot_c2rust.optimizer_progress",
                    function="load_or_reset_progress",
                )
                pass
            self.processed = set()
            if not hasattr(self, "steps_completed"):
                self.steps_completed = set()
            if not hasattr(self, "_step_commits"):
                self._step_commits = {}
            return
        try:
            if self.progress_path.exists():
                obj = json.loads(self.progress_path.read_text(encoding="utf-8"))
                if isinstance(obj, dict):
                    arr = obj.get("processed") or []
                    if isinstance(arr, list):
                        self.processed = {str(x) for x in arr if isinstance(x, str)}
                    else:
                        self.processed = set()
                    # Load completed steps
                    steps = obj.get("steps_completed") or []
                    if isinstance(steps, list):
                        self.steps_completed = {
                            str(x) for x in steps if isinstance(x, str)
                        }
                    else:
                        self.steps_completed = set()
                    # Load step commit ids
                    step_commits = obj.get("step_commits") or {}
                    if isinstance(step_commits, dict):
                        self._step_commits = {
                            str(k): str(v)
                            for k, v in step_commits.items()
                            if isinstance(k, str) and isinstance(v, str)
                        }
                    else:
                        self._step_commits = {}

                    # On resume, reset to the commit id of the last step
                    if self.options.resume and self._step_commits:
                        last_commit = None
                        # Find the commit of the last completed step according to step order
                        step_order = [
                            "clippy_elimination",
                            "unsafe_cleanup",
                            "visibility_opt",
                            "doc_opt",
                        ]
                        for step in reversed(step_order):
                            if (
                                step in self.steps_completed
                                and step in self._step_commits
                            ):
                                last_commit = self._step_commits[step]
                                break

                        if last_commit:
                            current_commit = self.get_crate_commit_hash()
                            if current_commit != last_commit:
                                PrettyOutput.auto_print(
                                    f"🔧 [c2rust-optimizer][resume] Detected inconsistent code state; resetting to the commit of the last step: {last_commit}",
                                )
                                if self.reset_to_commit(last_commit):
                                    PrettyOutput.auto_print(
                                        f"✅ [c2rust-optimizer][resume] Reset to commit: {last_commit}",
                                    )
                                else:
                                    PrettyOutput.auto_print(
                                        "⚠️ [c2rust-optimizer][resume] Reset failed; continuing with the current code state",
                                    )
                            else:
                                PrettyOutput.auto_print(
                                    "ℹ️ [c2rust-optimizer][resume] Code state is consistent; no reset needed",
                                )
                else:
                    self.processed = set()
                    self.steps_completed = set()
                    self._step_commits = {}
            else:
                self.processed = set()
                self.steps_completed = set()
                self._step_commits = {}
        except Exception:
            self.processed = set()
            self.steps_completed = set()
            self._step_commits = {}

    def get_crate_commit_hash(self) -> Optional[str]:
        """Get the current commit id of the crate directory."""
        try:
            repo_root = git_toplevel(self.crate_dir)
            if repo_root is None:
                return None
            return git_head_commit(repo_root)
        except Exception:
            return None

    def reset_to_commit(self, commit_hash: str) -> bool:
        """Roll the crate directory back to the specified commit."""
        try:
            repo_root = git_toplevel(self.crate_dir)
            if repo_root is None:
                return False
            return git_reset_hard(repo_root, commit_hash)
        except Exception:
            return False

    def snapshot_commit(self) -> None:
        """
        When git_guard is enabled, record the current HEAD commit (record only; do not commit unstaged changes).
        Run git commands uniformly at the repository root to avoid surprises caused by subdirectories.
        """
        if not self.options.git_guard:
            return
        try:
            repo_root = git_toplevel(self.crate_dir)
            if repo_root is None:
                return
            head = git_head_commit(repo_root)
            if head:
                self._last_snapshot_commit = head
        except Exception:
            # Ignore snapshot failures; do not block the flow
            pass

    def reset_to_snapshot(self) -> bool:
        """
        When git_guard is enabled and a snapshot exists, reset --hard the working tree back to the snapshot.
        Run git commands uniformly at the repository root to avoid surprises caused by subdirectories.
        Returns whether the reset succeeded.
        """
        if not self.options.git_guard:
            return False
        snap = getattr(self, "_last_snapshot_commit", None)
        if not snap:
            return False
        repo_root = git_toplevel(self.crate_dir)
        if repo_root is None:
            return False
        ok = git_reset_hard(repo_root, snap)
        return ok

    def save_progress_for_batch(self, files: List[Path]) -> None:
        """Save file processing progress."""
        try:
            rels = []
            for p in files:
                try:
                    rel = p.resolve().relative_to(self.crate_dir.resolve()).as_posix()
                except Exception:
                    rel = str(p)
                rels.append(rel)
            self.processed.update(rels)

            # Get the current commit id and record it
            current_commit = self.get_crate_commit_hash()

            data: Dict[str, Any] = {
                "processed": sorted(self.processed),
                "steps_completed": sorted(self.steps_completed),
            }
            if current_commit:
                data["last_commit"] = current_commit
                PrettyOutput.auto_print(
                    f"ℹ️ [c2rust-optimizer][progress] Recorded current commit: {current_commit}",
                )

            self.progress_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.optimizer_progress",
                function="save_progress_for_batch",
            )
            pass

    def save_fix_progress(
        self, step_name: str, fix_key: str, files: Optional[List[Path]] = None
    ) -> None:
        """
        Save the progress of a single fix (including the commit id).

        Args:
            step_name: step name (such as "clippy_elimination", "unsafe_cleanup")
            fix_key: unique identifier of the fix (such as "warning-1", "file_path.rs")
            files: list of modified files (optional)
        """
        try:
            # Get the current commit id
            current_commit = self.get_crate_commit_hash()
            if not current_commit:
                PrettyOutput.auto_print(
                    "⚠️ [c2rust-optimizer][progress] Unable to obtain commit id; skipping progress recording",
                )
                return

            # Load existing progress
            if self.progress_path.exists():
                try:
                    obj = json.loads(self.progress_path.read_text(encoding="utf-8"))
                except Exception:
                    obj = {}
            else:
                obj = {}

            # Initialize the fix progress structure
            if "fix_progress" not in obj:
                obj["fix_progress"] = {}
            if step_name not in obj["fix_progress"]:
                obj["fix_progress"][step_name] = {}

            # Record fix progress
            obj["fix_progress"][step_name][fix_key] = {
                "commit": current_commit,
                "timestamp": None,  # a timestamp can be added if needed
            }

            # Update the processed files list
            if files:
                rels = []
                for p in files:
                    try:
                        rel = (
                            p.resolve().relative_to(self.crate_dir.resolve()).as_posix()
                        )
                    except Exception:
                        rel = str(p)
                    rels.append(rel)
                self.processed.update(rels)
                obj["processed"] = sorted(self.processed)

            # Update last_commit
            obj["last_commit"] = current_commit

            # Save progress
            self.progress_path.write_text(
                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            PrettyOutput.auto_print(
                f"ℹ️ [c2rust-optimizer][progress] Recorded fix progress: {step_name}/{fix_key} -> commit {current_commit[:8]}"
            )
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ ⚠️ [c2rust-optimizer] Failed to save fix progress (non-fatal): {e}"
            )

    def save_step_progress(self, step_name: str, files: List[Path]) -> None:
        """Save step progress: mark the step as complete and update the files list."""
        try:
            # Mark the step as completed
            self.steps_completed.add(step_name)
            # Update the processed files list
            rels = []
            for p in files:
                try:
                    rel = p.resolve().relative_to(self.crate_dir.resolve()).as_posix()
                except Exception:
                    rel = str(p)
                rels.append(rel)
            self.processed.update(rels)

            # Get the current commit id and record it
            current_commit = self.get_crate_commit_hash()

            # Save progress
            data: Dict[str, Any] = {
                "processed": sorted(self.processed),
                "steps_completed": sorted(self.steps_completed),
            }
            if current_commit:
                # Record the commit id of each step
                step_commits = getattr(self, "_step_commits", {})
                step_commits[step_name] = current_commit
                self._step_commits = step_commits
                data["step_commits"] = cast(Dict[str, str], step_commits)
                data["last_commit"] = current_commit
                PrettyOutput.auto_print(
                    f"ℹ️ [c2rust-optimizer][progress] Recorded commit for step '{step_name}': {current_commit}",
                )

            self.progress_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            PrettyOutput.auto_print(
                "ℹ️ [c2rust-optimizer] Step progress saved",
            )
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-optimizer] Failed to save step progress (non-fatal): {e}",
            )

    def on_before_tool_call(
        self, agent: Any, current_response: Optional[Any] = None, **kwargs: Any
    ) -> None:
        """
        Event handler before a tool call, used to record the commit id before the tool call.

        Records the current commit before each tool call so that it can be rolled back if a problem is detected after the tool call.
        """
        try:
            # Only focus on tools that may modify code
            # Note: at BEFORE_TOOL_CALL, the tool has not executed yet, so the tool name cannot be obtained
            # But we can check the tool name at AFTER_TOOL_CALL; here we just record the commit
            agent_id = id(agent)
            agent_key = f"agent_{agent_id}"
            current_commit = self.get_crate_commit_hash()
            if current_commit:
                # Record the commit before the tool call (if not recorded before, or the commit has changed)
                if (
                    agent_key not in self._agent_before_commits
                    or self._agent_before_commits[agent_key] != current_commit
                ):
                    self._agent_before_commits[agent_key] = current_commit
        except Exception as e:
            # Event handler exceptions should not affect the main flow
            PrettyOutput.auto_print(
                f"⚠️ ⚠️ [c2rust-optimizer][test-detection] BEFORE_TOOL_CALL event handler exception: {e}"
            )

    def on_after_tool_call(
        self,
        agent: Any,
        current_response: Optional[Any] = None,
        need_return: Optional[bool] = None,
        tool_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """
        Event handler after a tool call, used for fine-grained detection of test code deletion.

        Detects immediately after each tool call; if test code is found to have been incorrectly deleted, rolls back immediately.
        """
        try:
            # Only detect tool calls that edit files
            last_tool = (
                agent.get_user_data("__last_executed_tool__")
                if hasattr(agent, "get_user_data")
                else None
            )
            if not last_tool:
                return

            # Only focus on tools that may modify code
            edit_tools = {
                "edit_file",
                "edit_file_by_line",
                "write_file",
                "apply_patch",
            }
            if last_tool not in edit_tools:
                return

            # Get the commit id before the tool call for this Agent
            agent_id = id(agent)
            agent_key = f"agent_{agent_id}"
            before_commit = self._agent_before_commits.get(agent_key)

            # If there is no commit information, detection is not possible
            if not before_commit:
                return

            # Detect test code deletion
            from haijunbot.haijunbot_c2rust.utils import ask_llm_about_test_deletion
            from haijunbot.haijunbot_c2rust.utils import detect_test_deletion

            detection_result = detect_test_deletion("[c2rust-optimizer]")
            if not detection_result:
                # No deletion detected; update the commit record
                current_commit = self.get_crate_commit_hash()
                if current_commit and current_commit != before_commit:
                    self._agent_before_commits[agent_key] = current_commit
                return

            PrettyOutput.auto_print(
                "⚠️ ⚠️ [c2rust-optimizer][test-detection] Detected a possibly erroneous deletion of test code markers (detected after the tool call)"
            )

            # Ask the LLM whether it is reasonable
            need_reset = ask_llm_about_test_deletion(
                detection_result, agent, "[c2rust-optimizer]"
            )

            if need_reset:
                PrettyOutput.auto_print(
                    f"❌ ❌ [c2rust-optimizer][test-detection] The LLM confirmed the deletion is unreasonable; rolling back to commit: {before_commit}"
                )
                if self.reset_to_commit(before_commit):
                    PrettyOutput.auto_print(
                        "✅ ✅ [c2rust-optimizer][test-detection] Rolled back to the previous commit (detected after the tool call)"
                    )
                    # After rolling back, keep the previous commit record
                    self._agent_before_commits[agent_key] = before_commit
                    # Add a hint to the agent's session informing it that the changes were reverted
                    if hasattr(agent, "session") and hasattr(agent.session, "prompt"):
                        agent.session.prompt += "\n\n⚠️ Changes reverted: test code was detected as incorrectly deleted, rolled back to the previous version.\n"
                else:
                    PrettyOutput.auto_print(
                        "❌ ❌ [c2rust-optimizer][test-detection] Rollback failed"
                    )
            else:
                # The LLM considers the deletion reasonable; update the commit record
                current_commit = self.get_crate_commit_hash()
                if current_commit and current_commit != before_commit:
                    self._agent_before_commits[agent_key] = current_commit
        except Exception as e:
            # Event handler exceptions should not affect the main flow
            PrettyOutput.auto_print(
                f"⚠️ ⚠️ [c2rust-optimizer][test-detection] AFTER_TOOL_CALL event handler exception: {e}"
            )

    def check_and_handle_test_deletion(
        self, before_commit: Optional[str], agent: Any
    ) -> bool:
        """
        Detect and handle test code deletion.

        Args:
            before_commit: the commit hash before the agent ran
            agent: the code optimization or fix agent instance; its model is used for the query

        Returns:
            bool: True if a problem was detected and a rollback occurred; otherwise False
        """
        from haijunbot.haijunbot_c2rust.utils import check_and_handle_test_deletion

        return check_and_handle_test_deletion(
            before_commit, agent, self.reset_to_commit, "[c2rust-optimizer]"
        )
