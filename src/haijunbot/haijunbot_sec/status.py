# -*- coding: utf-8 -*-
"""
Progress status management module

Provides a structured progress status file that accurately reflects the current
stage and progress.
Status file format: JSON, containing the current stage, progress percentage,
completed/total counts, and other information.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional
from typing import cast


class StatusManager:
    """Progress status manager"""

    def __init__(self, entry_path: str):
        """
        Initialize the status manager

        Args:
            entry_path: Root directory path to be analyzed (can be the project root directory or the .haijunbot/sec directory)
        """
        self.entry_path = Path(entry_path)
        # Check whether entry_path is already the .haijunbot/sec directory
        if self.entry_path.name == "sec" and self.entry_path.parent.name == ".haijunbot":
            sec_dir = self.entry_path
        else:
            sec_dir = self.entry_path / ".haijunbot" / "sec"
        self.status_path = sec_dir / "status.json"
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the status file directory exists"""
        self.status_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_status(self) -> Dict[str, Any]:
        """Read the current status"""
        if not self.status_path.exists():
            return {}
        try:
            with self.status_path.open("r", encoding="utf-8") as f:
                return cast(Dict[str, Any], json.load(f))
        except Exception:
            return {}

    def _write_status(self, status: Dict[str, Any]) -> None:
        """Write the status file"""
        try:
            status["last_updated"] = (
                datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"
            )
            with self.status_path.open("w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception:
            # A failure to write the status file does not affect the main flow
            pass

    def update_stage(
        self,
        stage: str,
        progress: Optional[float] = None,
        current: Optional[int] = None,
        total: Optional[int] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update the current stage and progress

        Args:
            stage: Stage name (pre_scan, clustering, verification, completed, error)
            progress: Progress percentage (0-100); if None, computed from current/total
            current: Number of items completed so far
            total: Total number of items
            message: Status message
            details: Additional detailed information
        """
        status = self._read_status()

        # Compute the progress percentage
        if progress is None and current is not None and total is not None and total > 0:
            progress = (current / total) * 100

        # Update the status
        status["stage"] = stage
        if progress is not None:
            status["progress"] = round(progress, 2)
        if current is not None:
            status["current"] = current
        if total is not None:
            status["total"] = total
        if message:
            status["message"] = message
        if details:
            status["details"] = details

        # Set the stage start time (if this is a new stage)
        if "stage_history" not in status:
            status["stage_history"] = []

        # Check whether this is a stage switch
        last_stage = status.get("stage")
        if last_stage != stage:
            status["stage_history"].append(
                {
                    "stage": stage,
                    "started_at": datetime.now(timezone.utc)
                    .replace(tzinfo=None)
                    .isoformat()
                    + "Z",
                }
            )

        self._write_status(status)

    def update_pre_scan(
        self,
        current_files: Optional[int] = None,
        total_files: Optional[int] = None,
        issues_found: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update the heuristic scan stage status"""
        details = {}
        if issues_found is not None:
            details["issues_found"] = issues_found

        progress = None
        if current_files is not None and total_files is not None and total_files > 0:
            progress = (current_files / total_files) * 100

        self.update_stage(
            stage="pre_scan",
            progress=progress,
            current=current_files,
            total=total_files,
            message=message or "Performing heuristic scan...",
            details=details,
        )

    def update_clustering(
        self,
        current_file: Optional[int] = None,
        total_files: Optional[int] = None,
        current_batch: Optional[int] = None,
        total_batches: Optional[int] = None,
        file_name: Optional[str] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update the clustering stage status"""
        details: Dict[str, Any] = {}
        if file_name:
            details["current_file"] = file_name
        if current_batch is not None:
            details["current_batch"] = current_batch
        if total_batches is not None:
            details["total_batches"] = total_batches

        # Compute overall progress (file level)
        progress = None
        if current_file is not None and total_files is not None and total_files > 0:
            progress = (current_file / total_files) * 100

        self.update_stage(
            stage="clustering",
            progress=progress,
            current=current_file,
            total=total_files,
            message=message or "Performing cluster analysis...",
            details=details,
        )

    def update_review(
        self,
        current_review: Optional[int] = None,
        total_reviews: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update the review stage status"""
        details: Dict[str, Any] = {}

        # Compute overall progress
        progress = None
        if (
            current_review is not None
            and total_reviews is not None
            and total_reviews > 0
        ):
            progress = (current_review / total_reviews) * 100

        self.update_stage(
            stage="review",
            progress=progress,
            current=current_review,
            total=total_reviews,
            message=message or "Reviewing invalid clusters...",
            details=details,
        )

    def update_verification(
        self,
        current_batch: Optional[int] = None,
        total_batches: Optional[int] = None,
        current_task: Optional[int] = None,
        total_tasks: Optional[int] = None,
        batch_id: Optional[str] = None,
        file_name: Optional[str] = None,
        issues_found: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Update the verification stage status"""
        details: Dict[str, Any] = {}
        if batch_id:
            details["batch_id"] = batch_id
        if file_name:
            details["file"] = file_name
        if issues_found is not None:
            details["issues_found"] = issues_found

        # Compute overall progress (batch level)
        progress = None
        if (
            current_batch is not None
            and total_batches is not None
            and total_batches > 0
        ):
            progress = (current_batch / total_batches) * 100

        self.update_stage(
            stage="verification",
            progress=progress,
            current=current_batch,
            total=total_batches,
            message=message or "Performing security verification...",
            details=details,
        )

    def mark_completed(
        self,
        total_issues: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        """Mark the analysis as completed"""
        details = {}
        if total_issues is not None:
            details["total_issues"] = total_issues

        self.update_stage(
            stage="completed",
            progress=100.0,
            message=message or "Security analysis completed",
            details=details,
        )

    def mark_error(
        self,
        error_message: str,
        error_type: Optional[str] = None,
    ) -> None:
        """Mark an error status"""
        details = {"error_message": error_message}
        if error_type:
            details["error_type"] = error_type

        self.update_stage(
            stage="error",
            message=f"An error occurred: {error_message}",
            details=details,
        )

    def get_status(self) -> Dict[str, Any]:
        """Get the current status"""
        return self._read_status()


__all__ = ["StatusManager"]
