"""CodeAgent impact analysis module"""

from typing import Any
from typing import Dict

from haijunbot.haijunbot_utils.output import PrettyOutput

# -*- coding: utf-8 -*-
from typing import List
from typing import Optional
from typing import Tuple

from haijunbot.haijunbot_code_agent.code_analyzer import ContextManager
from haijunbot.haijunbot_code_agent.code_analyzer import ImpactAnalyzer
from haijunbot.haijunbot_code_agent.code_analyzer import parse_git_diff_to_edits
from haijunbot.haijunbot_code_agent.code_analyzer.impact_analyzer import Edit
from haijunbot.haijunbot_utils.config import is_enable_impact_analysis, read_text_file


class ImpactManager:
    """Impact analysis manager"""

    def __init__(self, root_dir: str, context_manager: ContextManager):
        self.root_dir = root_dir
        self.context_manager = context_manager

    def update_context_for_modified_files(self, modified_files: List[str]) -> None:
        """Update the context manager: after a file is modified, update the symbol table and dependency graph"""
        if not modified_files:
            return
        PrettyOutput.auto_print("🔄 Updating code context...")
        for file_path in modified_files:
            import os

            if os.path.exists(file_path):
                try:
                    content = read_text_file(file_path, errors="replace")
                    self.context_manager.update_context_for_file(file_path, content)
                except Exception:
                    # If reading the file fails, skip the update
                    pass

    def analyze_edit_impact(self, modified_files: List[str]) -> Optional[Any]:
        """Perform impact scope analysis (if enabled)

        Returns:
            ImpactReport: impact analysis report, or None if not enabled or failed
        """
        if not is_enable_impact_analysis():
            return None

        PrettyOutput.auto_print("🔍 Performing change impact analysis...")
        try:
            impact_analyzer = ImpactAnalyzer(self.context_manager)
            all_edits = []
            import os

            for file_path in modified_files:
                if os.path.exists(file_path):
                    edits = parse_git_diff_to_edits(file_path, self.root_dir)
                    all_edits.extend(edits)

            if not all_edits:
                return None

            # Group edits by file
            edits_by_file: Dict[str, List[Edit]] = {}
            for edit in all_edits:
                if edit.file_path not in edits_by_file:
                    edits_by_file[edit.file_path] = []
                edits_by_file[edit.file_path].append(edit)

            # Perform impact analysis on each file
            impact_report = None
            for file_path, edits in edits_by_file.items():
                report = impact_analyzer.analyze_edit_impact(file_path, edits)
                if report:
                    # Merge reports
                    if impact_report is None:
                        impact_report = report
                    else:
                        # Merge multiple reports, deduplicating
                        impact_report.affected_files = list(
                            set(impact_report.affected_files + report.affected_files)
                        )

                        # Merge symbols (deduplicate based on file path and name)
                        symbol_map: Dict[Tuple[str, str, str], Any] = {}
                        for symbol in (
                            impact_report.affected_symbols + report.affected_symbols
                        ):
                            key = (
                                symbol.file_path,
                                symbol.name,
                                str(symbol.line_start),
                            )
                            if key not in symbol_map:
                                symbol_map[key] = symbol
                        impact_report.affected_symbols = list(symbol_map.values())

                        impact_report.affected_tests = list(
                            set(impact_report.affected_tests + report.affected_tests)
                        )

                        # Merge interface changes (deduplicate based on symbol name and file path)
                        interface_map: Dict[Tuple[str, str, str], Any] = {}
                        for change in (
                            impact_report.interface_changes + report.interface_changes
                        ):
                            key = (
                                change.file_path,
                                change.symbol_name,
                                str(change.change_type),
                            )
                            if key not in interface_map:
                                interface_map[key] = change
                        impact_report.interface_changes = list(interface_map.values())

                        impact_report.impacts.extend(report.impacts)

                        # Merge recommendations
                        impact_report.recommendations = list(
                            set(impact_report.recommendations + report.recommendations)
                        )

                        # Use the higher risk level
                        if (
                            report.risk_level.value == "high"
                            or impact_report.risk_level.value == "high"
                        ):
                            impact_report.risk_level = (
                                report.risk_level
                                if report.risk_level.value == "high"
                                else impact_report.risk_level
                            )
                        elif report.risk_level.value == "medium":
                            impact_report.risk_level = report.risk_level

            return impact_report
        except Exception as e:
            # Impact analysis failure should not affect the main flow, only log it
            PrettyOutput.auto_print(f"⚠️ Impact scope analysis failed: {e}")
            return None

    def handle_impact_report(
        self, impact_report: Optional[Any], agent: Any, final_ret: str
    ) -> str:
        """Handle the impact scope analysis report

        Args:
            impact_report: impact analysis report
            agent: Agent instance
            final_ret: current result string

        Returns:
            The updated result string
        """
        if not impact_report:
            return final_ret

        impact_summary = impact_report.to_string(self.root_dir)
        final_ret += f"\n\n{impact_summary}\n"

        # If it is high risk, remind in the prompt
        if impact_report.risk_level.value == "high":
            agent.set_addon_prompt(
                f"{agent.get_addon_prompt() or ''}\n\n"
                f"⚠️ High-risk edit warning:\n"
                f"This edit was detected as a high-risk operation, please carefully check the following:\n"
                f"- Affected files: {len(impact_report.affected_files)}\n"
                f"- Interface changes: {len(impact_report.interface_changes)}\n"
                f"- Related tests: {len(impact_report.affected_tests)}\n"
                f"It is recommended to run the related tests and check all affected files."
            )

        return final_ret
