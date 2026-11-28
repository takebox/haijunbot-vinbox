# -*- coding: utf-8 -*-
"""Optimizer report management module."""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import json
from dataclasses import asdict
from pathlib import Path

from haijunbot.haijunbot_c2rust.optimizer_options import OptimizeStats
from haijunbot.haijunbot_c2rust.optimizer_utils import write_file


def get_report_display_path(
    report_path: Path, project_root: Path, crate_dir: Path
) -> str:
    """
    Get the display path of the report file (prefer relative paths).

    Args:
        report_path: Absolute path of the report file
        project_root: Project root directory
        crate_dir: crate root directory

    Returns:
        The display path string
    """
    try:
        return str(report_path.relative_to(project_root))
    except ValueError:
        try:
            return str(report_path.relative_to(crate_dir))
        except ValueError:
            try:
                return str(report_path.relative_to(Path.cwd()))
            except ValueError:
                return str(report_path)


def write_final_report(report_path: Path, stats: OptimizeStats) -> None:
    """
    Write the final optimization report.

    Args:
        report_path: Report file path
        stats: Optimization statistics
    """
    try:
        write_file(
            report_path,
            json.dumps(asdict(stats), ensure_ascii=False, indent=2),
        )
    except Exception as e:
        save_exception(
            e, module="haijunbot_c2rust.optimizer_report", function="write_final_report"
        )
        pass
