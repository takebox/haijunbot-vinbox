# -*- coding: utf-8 -*-
"""Optimizer options and statistics data structures."""

from dataclasses import dataclass
from typing import List
from typing import Optional


@dataclass
class OptimizeOptions:
    """Optimizer options configuration."""

    enable_unsafe_cleanup: bool = True
    enable_visibility_opt: bool = True
    enable_doc_opt: bool = True
    max_checks: int = 0  # 0 means unlimited; used to limit the number of cargo check runs (to prevent slowness)
    dry_run: bool = False
    # Batch optimization control for large projects
    include_patterns: Optional[str] = (
        None  # Comma-separated globs, relative to the crate root (supports src/**.rs)
    )
    exclude_patterns: Optional[str] = None  # Comma-separated globs
    max_files: int = 0  # Maximum number of files to process this run (0 = unlimited)
    resume: bool = True  # Checkpoint resume: skip already-processed files
    reset_progress: bool = False  # Reset progress (clear the processed list)
    build_fix_retries: int = 3  # Number of fix retries when the build fails
    # Git protection: snapshot commit before optimization, auto reset to the snapshot on failure
    git_guard: bool = True
    cargo_test_timeout: int = 300  # cargo test timeout (seconds)
    non_interactive: bool = True
    quick_mode: bool = False  # Quick mode: disable methodology, analysis, and rule loading


@dataclass
class OptimizeStats:
    """Optimization statistics."""

    files_scanned: int = 0
    unsafe_removed: int = 0
    unsafe_annotated: int = 0
    visibility_downgraded: int = 0
    docs_added: int = 0
    cargo_checks: int = 0
    errors: Optional[List[str]] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []
