"""Edit impact scope analysis module.

Provides code edit impact scope analysis functionality to identify files, functions, tests, etc. that may be affected.
"""

import ast
import os
import re
import subprocess
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from typing import Dict
from typing import List
from typing import Optional
from typing import Set
from typing import Tuple

from haijunbot.haijunbot_utils.config import read_text_file
from haijunbot.haijunbot_utils.exception_utils import save_exception
from haijunbot.haijunbot_utils.utils import decode_output

from .context_manager import ContextManager
from .db import GraphTraverser
from .file_ignore import filter_walk_dirs
from .symbol_extractor import Symbol
from .symbol_table_db import SymbolTableDB


class ImpactType(Enum):
    """Impact type enum"""

    REFERENCE = "reference"  # Symbol reference
    DEPENDENT = "dependent"  # Dependent symbols
    TEST = "test"  # Test file
    INTERFACE_CHANGE = "interface_change"  # Interface change
    DEPENDENCY_CHAIN = "dependency_chain"  # Dependency chain


class RiskLevel(Enum):
    """Risk level enum"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Impact:
    """Represents an impact item"""

    impact_type: ImpactType
    target: str  # The affected target (file path, symbol name, etc.)
    description: str = ""
    line: Optional[int] = None
    severity: RiskLevel = RiskLevel.LOW


@dataclass
class InterfaceChange:
    """Represents an interface change"""

    symbol_name: str
    change_type: str  # 'signature', 'return_type', 'parameter', 'removed', 'added'
    file_path: str
    line: int
    before: Optional[str] = None
    after: Optional[str] = None
    description: str = ""


@dataclass
class ImpactReport:
    """Impact analysis report"""

    affected_files: List[str] = field(default_factory=list)
    affected_symbols: List[Symbol] = field(default_factory=list)
    affected_tests: List[str] = field(default_factory=list)
    interface_changes: List[InterfaceChange] = field(default_factory=list)
    impacts: List[Impact] = field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    recommendations: List[str] = field(default_factory=list)

    def to_string(self, project_root: str = "") -> str:
        """Generate a readable impact report string"""
        lines = []
        lines.append("=" * 60)
        lines.append("Edit Impact Scope Analysis Report")
        lines.append("=" * 60)

        # Risk level
        risk_emoji = {RiskLevel.LOW: "🟢", RiskLevel.MEDIUM: "🟡", RiskLevel.HIGH: "🔴"}
        lines.append(
            f"\nRisk level: {risk_emoji.get(self.risk_level, '⚪')} {self.risk_level.value.upper()}"
        )

        # Affected files
        if self.affected_files:
            lines.append(f"\nAffected files ({len(self.affected_files)}):")
            for file_path in self.affected_files[:10]:
                rel_path = (
                    os.path.relpath(file_path, project_root)
                    if project_root
                    else file_path
                )
                lines.append(f"  - {rel_path}")
            if len(self.affected_files) > 10:
                lines.append(f"  ... and {len(self.affected_files) - 10} more files")

        # Affected symbols
        if self.affected_symbols:
            lines.append(f"\nAffected symbols ({len(self.affected_symbols)}):")
            for symbol in self.affected_symbols[:10]:
                lines.append(
                    f"  - {symbol.kind} {symbol.name} ({os.path.basename(symbol.file_path)}:{symbol.line_start})"
                )
            if len(self.affected_symbols) > 10:
                lines.append(f"  ... and {len(self.affected_symbols) - 10} more symbols")

        # Affected tests
        if self.affected_tests:
            lines.append(f"\nAffected tests ({len(self.affected_tests)}):")
            for test_file in self.affected_tests[:10]:
                rel_path = (
                    os.path.relpath(test_file, project_root)
                    if project_root
                    else test_file
                )
                lines.append(f"  - {rel_path}")
            if len(self.affected_tests) > 10:
                lines.append(f"  ... and {len(self.affected_tests) - 10} more test files")

        # Interface changes
        if self.interface_changes:
            lines.append(f"\nInterface changes ({len(self.interface_changes)}):")
            for change in self.interface_changes[:10]:
                lines.append(f"  - {change.symbol_name}: {change.change_type}")
                if change.description:
                    lines.append(f"    {change.description}")
            if len(self.interface_changes) > 10:
                lines.append(
                    f"  ... and {len(self.interface_changes) - 10} more interface changes"
                )

        # Recommendations
        if self.recommendations:
            lines.append("\nRecommendations:")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.append("\n" + "=" * 60)
        return "\n".join(lines)


@dataclass
class Edit:
    """Represents an edit operation"""

    file_path: str
    line_start: int
    line_end: int
    before: str = ""
    after: str = ""
    edit_type: str = "modify"  # 'modify', 'add', 'delete'


class TestDiscoverer:
    """Test file discoverer"""

    # Test file naming patterns
    TEST_PATTERNS = {
        "python": [
            r"test_.*\.py$",
            r".*_test\.py$",
        ],
        "javascript": [
            r".*\.test\.(js|ts|jsx|tsx)$",
            r".*\.spec\.(js|ts|jsx|tsx)$",
        ],
        "rust": [
            r".*_test\.rs$",
        ],
        "java": [
            r".*Test\.java$",
            r".*Tests\.java$",
        ],
        "go": [
            r".*_test\.go$",
        ],
    }

    def __init__(self, project_root: str):
        self.project_root = project_root

    def find_test_files(self, file_path: str) -> List[str]:
        """Find test files related to the given file"""
        test_files: List[str] = []

        # Detect the language
        language = self._detect_language(file_path)
        if not language:
            return test_files

        # Get the test file patterns
        patterns = self.TEST_PATTERNS.get(language, [])
        if not patterns:
            return test_files

        # Get the base name of the file (without extension)
        base_name = os.path.splitext(os.path.basename(file_path))[0]

        # Search for test files under the project root
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories and common ignore directories
            dirs[:] = filter_walk_dirs(dirs)

            for file in files:
                file_path_full = os.path.join(root, file)

                # Check whether it matches the test file patterns
                for pattern in patterns:
                    if re.match(pattern, file, re.IGNORECASE):
                        # Check whether the test file might test the target file
                        if self._might_test_file(file_path_full, file_path, base_name):
                            test_files.append(file_path_full)
                        break

        return list(set(test_files))

    def _might_test_file(
        self, test_file: str, target_file: str, base_name: str
    ) -> bool:
        """Determine whether the test file might test the target file"""
        # Read the test file content to look for references to the target file
        try:
            content = read_text_file(test_file, errors="replace")

            # Check whether it imports or references the target file
            # Simple heuristic: check the file name, module name, etc.
            target_base = os.path.splitext(os.path.basename(target_file))[0]

            # Check import statements
            import_patterns = [
                rf"import\s+.*{re.escape(target_base)}",
                rf"from\s+.*{re.escape(target_base)}",
                rf"use\s+.*{re.escape(target_base)}",  # Rust
            ]

            for pattern in import_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return True

            # Check whether the file name appears in the test file
            if target_base.lower() in content.lower():
                return True

        except Exception as e:
            save_exception(
                e,
                module="haijunbot_code_agent.code_analyzer.impact_analyzer",
                function="_might_test_file",
            )
            pass

        return False

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect the language of the file"""
        ext = os.path.splitext(file_path)[1].lower()
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "javascript",
            ".jsx": "javascript",
            ".tsx": "javascript",
            ".rs": "rust",
            ".java": "java",
            ".go": "go",
        }
        return ext_map.get(ext)


class ImpactAnalyzer:
    """Edit impact scope analyzer"""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager
        self.project_root = context_manager.project_root
        self.test_discoverer = TestDiscoverer(self.project_root)

        # Use the graph traverser (if the symbol_table is a SymbolTableDB)
        self._traverser: Optional[GraphTraverser] = None
        if isinstance(context_manager.symbol_table, SymbolTableDB):
            self._traverser = context_manager.symbol_table.get_traverser()

    def analyze_edit_impact(self, file_path: str, edits: List[Edit]) -> ImpactReport:
        """Analyze the impact scope of edits

        Args:
            file_path: the path of the edited file
            edits: the list of edit operations

        Returns:
            ImpactReport: the impact analysis report
        """
        impacts: List[Impact] = []
        # Use a dict to deduplicate Symbol objects (since Symbol is unhashable)
        affected_symbols_map: Dict[Tuple[str, str, int], Symbol] = {}
        affected_files: Set[str] = {file_path}
        interface_changes: List[InterfaceChange] = []

        # 1. Analyze the impact of each edit
        for edit in edits:
            # Analyze the symbol impact
            symbols_in_edit = self._find_symbols_in_edit(file_path, edit)
            for symbol in symbols_in_edit:
                # Use a tuple as the key to deduplicate Symbol objects
                symbol_key = (symbol.file_path, symbol.name, symbol.line_start)
                if symbol_key not in affected_symbols_map:
                    affected_symbols_map[symbol_key] = symbol
                symbol_impacts = self._analyze_symbol_impact(symbol, edit)
                impacts.extend(symbol_impacts)

                # Collect the affected files
                for impact in symbol_impacts:
                    if impact.impact_type == ImpactType.REFERENCE:
                        affected_files.add(impact.target)
                    elif impact.impact_type == ImpactType.DEPENDENT:
                        affected_files.add(impact.target)

        # 2. Analyze the dependency chain impact
        dependency_impacts = self._analyze_dependency_chain(file_path)
        impacts.extend(dependency_impacts)
        for impact in dependency_impacts:
            affected_files.add(impact.target)

        # 3. Detect interface changes
        if edits:
            # Need to read the file content to compare
            interface_changes = self._detect_interface_changes(file_path, edits)
            for change in interface_changes:
                affected_files.add(change.file_path)

        # 4. Find related tests
        test_files = self.test_discoverer.find_test_files(file_path)
        for test_file in test_files:
            impacts.append(
                Impact(
                    impact_type=ImpactType.TEST,
                    target=test_file,
                    description=f"Test file that may test {os.path.basename(file_path)}",
                )
            )
            affected_files.add(test_file)

        # 5. Assess the risk level
        risk_level = self._assess_risk(impacts, interface_changes)

        # 6. Generate recommendations
        recommendations = self._generate_recommendations(
            impacts, interface_changes, affected_files, test_files
        )

        return ImpactReport(
            affected_files=list(affected_files),
            affected_symbols=list(affected_symbols_map.values()),
            affected_tests=test_files,
            interface_changes=interface_changes,
            impacts=impacts,
            risk_level=risk_level,
            recommendations=recommendations,
        )

    def _find_symbols_in_edit(self, file_path: str, edit: Edit) -> List[Symbol]:
        """Find the symbols within the edit region"""
        symbols = self.context_manager.symbol_table.get_file_symbols(file_path)

        # Find symbols within the edit range
        affected_symbols = []
        for symbol in symbols:
            # Handle both Node and Symbol types
            line_start = getattr(symbol, "start_line", None) or getattr(
                symbol, "line_start", None
            )
            line_end = getattr(symbol, "end_line", None) or getattr(
                symbol, "line_end", None
            )

            if line_start is None or line_end is None:
                continue

            # Check whether the symbol overlaps the edit region
            if line_start <= edit.line_end and line_end >= edit.line_start:
                # Convert to a Symbol type
                if isinstance(symbol, Symbol):
                    affected_symbols.append(symbol)
                else:
                    # Convert the Node to a Symbol
                    affected_symbols.append(
                        Symbol(
                            name=symbol.name,
                            kind=symbol.kind.value
                            if hasattr(symbol.kind, "value")
                            else str(symbol.kind),
                            file_path=symbol.file_path,
                            line_start=symbol.start_line,
                            line_end=symbol.end_line,
                            signature=getattr(symbol, "signature", None),
                            docstring=getattr(symbol, "docstring", None),
                            parent=getattr(symbol, "parent_id", None),
                        )
                    )

        return affected_symbols

    def _analyze_symbol_impact(self, symbol: Symbol, edit: Edit) -> List[Impact]:
        """Analyze the impact of editing a symbol"""
        impacts = []

        # 1. Find all the locations that reference this symbol
        references = self.context_manager.find_references(symbol.name, symbol.file_path)
        for ref in references:
            impacts.append(
                Impact(
                    impact_type=ImpactType.REFERENCE,
                    target=ref.file_path,
                    description=f"References symbol {symbol.name}",
                    line=ref.line,
                    severity=RiskLevel.MEDIUM
                    if symbol.kind in ("function", "class")
                    else RiskLevel.LOW,
                )
            )

        # 2. Find other symbols that depend on this symbol (in the same file)
        if symbol.kind in ("function", "class"):
            dependents = self._find_dependent_symbols(symbol)
            for dep in dependents:
                impacts.append(
                    Impact(
                        impact_type=ImpactType.DEPENDENT,
                        target=dep.file_path,
                        description=f"Depends on symbol {symbol.name}",
                        line=dep.line_start,
                        severity=RiskLevel.MEDIUM,
                    )
                )

        return impacts

    def _find_dependent_symbols(self, symbol: Symbol) -> List[Symbol]:
        """Find other symbols that depend on this symbol"""
        dependents = []

        # Get all the symbols in the same file
        file_symbols = self.context_manager.symbol_table.get_file_symbols(
            symbol.file_path
        )

        # Get the line range of the current symbol
        symbol_line_start = getattr(symbol, "start_line", None) or getattr(
            symbol, "line_start", None
        )
        symbol_line_end = getattr(symbol, "end_line", None) or getattr(
            symbol, "line_end", None
        )

        if symbol_line_start is None or symbol_line_end is None:
            return dependents

        # Find symbols defined after this symbol (which may use it)
        for other_symbol in file_symbols:
            # Handle both Node and Symbol types
            other_line_start = getattr(other_symbol, "start_line", None) or getattr(
                other_symbol, "line_start", None
            )
            other_line_end = getattr(other_symbol, "end_line", None) or getattr(
                other_symbol, "line_end", None
            )

            if other_line_start is None or other_line_end is None:
                continue

            if other_line_start > symbol_line_end and other_symbol.name != symbol.name:
                # Simple check: if the symbol name appears in the other symbol's range, it may depend on it
                # Here we use a simple heuristic
                content = self.context_manager._get_file_content(symbol.file_path)
                if content:
                    # Extract the code region of the other symbol
                    lines = content.split("\n")
                    if other_line_start <= len(lines) and other_line_end <= len(lines):
                        region = "\n".join(lines[other_line_start - 1 : other_line_end])
                        if symbol.name in region:
                            # Convert to a Symbol type
                            if isinstance(other_symbol, Symbol):
                                dependents.append(other_symbol)
                            else:
                                dependents.append(
                                    Symbol(
                                        name=other_symbol.name,
                                        kind=other_symbol.kind.value
                                        if hasattr(other_symbol.kind, "value")
                                        else str(other_symbol.kind),
                                        file_path=other_symbol.file_path,
                                        line_start=other_symbol.start_line,
                                        line_end=other_symbol.end_line,
                                        signature=getattr(
                                            other_symbol, "signature", None
                                        ),
                                        docstring=getattr(
                                            other_symbol, "docstring", None
                                        ),
                                        parent=getattr(other_symbol, "parent_id", None),
                                    )
                                )

        return dependents

    def _analyze_dependency_chain(self, file_path: str) -> List[Impact]:
        """Analyze the dependency chain to find all files that may be affected"""
        impacts = []

        # Get all files that depend on this file (transitive closure)
        visited = set()
        to_process = [file_path]

        while to_process:
            current = to_process.pop(0)
            if current in visited:
                continue
            visited.add(current)

            dependents = self.context_manager.dependency_graph.get_dependents(current)
            for dependent in dependents:
                if dependent not in visited:
                    impacts.append(
                        Impact(
                            impact_type=ImpactType.DEPENDENCY_CHAIN,
                            target=dependent,
                            description=f"Indirectly depends on {os.path.basename(file_path)}",
                            severity=RiskLevel.LOW,
                        )
                    )
                    to_process.append(dependent)

        return impacts

    def _detect_interface_changes(
        self, file_path: str, edits: List[Edit]
    ) -> List[InterfaceChange]:
        """Detect interface changes (function signatures, class definitions, etc.)"""
        changes: List[InterfaceChange] = []

        # Read the file content
        content_before = self._get_file_content_before_edit(file_path, edits)
        content_after = self._get_file_content_after_edit(file_path, edits)

        if not content_before or not content_after:
            return changes

        # Parse the AST and compare
        try:
            tree_before = ast.parse(content_before, filename=file_path)
            tree_after = ast.parse(content_after, filename=file_path)

            # Extract function and class definitions
            defs_before = self._extract_definitions(tree_before)
            defs_after = self._extract_definitions(tree_after)

            # Compare the definitions
            for name, def_before in defs_before.items():
                if name in defs_after:
                    def_after = defs_after[name]
                    change = self._compare_definition(
                        name, def_before, def_after, file_path
                    )
                    if change:
                        changes.append(change)
                else:
                    # The definition was removed
                    changes.append(
                        InterfaceChange(
                            symbol_name=name,
                            change_type="removed",
                            file_path=file_path,
                            line=def_before["line"],
                            description=f"Symbol {name} was removed",
                        )
                    )

            # Check for newly added definitions
            for name, def_after in defs_after.items():
                if name not in defs_before:
                    changes.append(
                        InterfaceChange(
                            symbol_name=name,
                            change_type="added",
                            file_path=file_path,
                            line=def_after["line"],
                            description=f"New symbol {name} added",
                        )
                    )

        except SyntaxError:
            # Skip interface change detection if parsing fails
            pass

        return changes

    def _extract_definitions(self, tree: ast.AST) -> Dict[str, Dict]:
        """Extract function and class definitions from the AST"""
        definitions = {}

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Extract the function signature
                args = [arg.arg for arg in node.args.args]
                signature = f"{node.name}({', '.join(args)})"
                definitions[node.name] = {
                    "type": "function",
                    "line": node.lineno,
                    "signature": signature,
                    "args": args,
                    "node": node,
                }
            elif isinstance(node, ast.ClassDef):
                definitions[node.name] = {
                    "type": "class",
                    "line": node.lineno,
                    "signature": node.name,
                    "node": node,
                }

        return definitions

    def _compare_definition(
        self, name: str, def_before: Dict, def_after: Dict, file_path: str
    ) -> Optional[InterfaceChange]:
        """Compare two definitions and detect interface changes"""
        if def_before["type"] != def_after["type"]:
            return InterfaceChange(
                symbol_name=name,
                change_type="signature",
                file_path=file_path,
                line=def_after["line"],
                before=def_before["signature"],
                after=def_after["signature"],
                description=f"Symbol {name} changed type from {def_before['type']} to {def_after['type']}",
            )

        if def_before["type"] == "function":
            # Compare the function parameters
            args_before = def_before.get("args", [])
            args_after = def_after.get("args", [])

            if args_before != args_after:
                return InterfaceChange(
                    symbol_name=name,
                    change_type="signature",
                    file_path=file_path,
                    line=def_after["line"],
                    before=def_before["signature"],
                    after=def_after["signature"],
                    description=f"Function {name} changed parameters from ({', '.join(args_before)}) to ({', '.join(args_after)})",
                )

        return None

    def _get_file_content_before_edit(
        self, file_path: str, edits: List[Edit]
    ) -> Optional[str]:
        """Get the file content before the edits"""
        try:
            return read_text_file(file_path, errors="replace")
        except Exception:
            return None

    def _get_file_content_after_edit(
        self, file_path: str, edits: List[Edit]
    ) -> Optional[str]:
        """Get the file content after the edits (simulated)"""
        # This should simulate the content after applying the edits
        # For simplicity, we directly read the current file content
        # In actual use, we should apply the changes based on the edits
        try:
            return read_text_file(file_path, errors="replace")
        except Exception:
            return None

    def _assess_risk(
        self, impacts: List[Impact], interface_changes: List[InterfaceChange]
    ) -> RiskLevel:
        """Assess the risk level of the edits"""
        # Count high risk factors
        high_risk_count = 0
        medium_risk_count = 0

        # Interface changes are usually high risk
        if interface_changes:
            high_risk_count += len(interface_changes)

        # Count the number of impacts
        reference_count = sum(
            1 for i in impacts if i.impact_type == ImpactType.REFERENCE
        )
        if reference_count > 10:
            high_risk_count += 1
        elif reference_count > 5:
            medium_risk_count += 1

        # Check for high risk impacts
        for impact in impacts:
            if impact.severity == RiskLevel.HIGH:
                high_risk_count += 1
            elif impact.severity == RiskLevel.MEDIUM:
                medium_risk_count += 1

        # Assess the risk level
        if high_risk_count > 0 or medium_risk_count > 3:
            return RiskLevel.HIGH
        elif medium_risk_count > 0 or len(impacts) > 5:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_recommendations(
        self,
        impacts: List[Impact],
        interface_changes: List[InterfaceChange],
        affected_files: Set[str],
        test_files: List[str],
    ) -> List[str]:
        """Generate fix recommendations"""
        recommendations = []

        # If there are interface changes, recommend checking all call sites
        if interface_changes:
            recommendations.append(
                f"Detected {len(interface_changes)} interface changes, please check all call sites and update the related code"
            )

        # If there are test files, recommend running the tests
        if test_files:
            recommendations.append(
                f"Found {len(test_files)} related test files, recommend running the tests to ensure everything works"
            )

        # If many files are affected, recommend incremental testing
        if len(affected_files) > 5:
            recommendations.append(
                f"The edits affect {len(affected_files)} files, recommend incremental testing"
            )

        # If there are many references, recommend a code review
        reference_count = sum(
            1 for i in impacts if i.impact_type == ImpactType.REFERENCE
        )
        if reference_count > 10:
            recommendations.append(
                f"Detected {reference_count} symbol references, recommend a code review"
            )

        if not recommendations:
            recommendations.append("The edit impact is small, recommend basic testing")

        return recommendations


def parse_git_diff_to_edits(file_path: str, project_root: str) -> List[Edit]:
    """Parse edit operations from a git diff

    Args:
        file_path: file path
        project_root: project root directory

    Returns:
        List[Edit]: the list of edit operations
    """
    edits: List[Edit] = []

    try:
        # Get the git diff of the file
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return edits

        # Check whether there is a git repository
        try:
            subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                cwd=project_root,
                check=True,
                capture_output=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Not a git repository or git is unavailable, return an empty list
            return edits

        # Get the hash of HEAD
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
                capture_output=True,
                text=False,
                check=False,
            )
            stdout = decode_output(result.stdout)
            head_exists = result.returncode == 0 and stdout.strip()
        except Exception:
            head_exists = False

        # Temporarily add the file to the git index (if it is a new file)
        subprocess.run(
            ["git", "add", "-N", "--", abs_path],
            cwd=project_root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Get the diff
            cmd = ["git", "diff"] + (["HEAD"] if head_exists else []) + ["--", abs_path]
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=False,
                check=False,
            )
            diff_stdout = decode_output(result.stdout)

            if result.returncode != 0 or not diff_stdout:
                return edits

            diff_text = diff_stdout

            # Parse the diff text
            lines = diff_text.split("\n")
            current_hunk_start = None
            current_line_num: Optional[int] = None
            before_lines: List[str] = []
            after_lines: List[str] = []
            in_hunk = False

            for line in lines:
                # Parse the hunk header: @@ -start,count +start,count @@
                if line.startswith("@@"):
                    # Save the previous hunk
                    if in_hunk and current_hunk_start is not None:
                        if before_lines or after_lines:
                            edits.append(
                                Edit(
                                    file_path=abs_path,
                                    line_start=current_hunk_start,
                                    line_end=current_hunk_start + len(after_lines) - 1
                                    if after_lines
                                    else current_hunk_start,
                                    before="\n".join(before_lines),
                                    after="\n".join(after_lines),
                                    edit_type="modify"
                                    if before_lines and after_lines
                                    else ("delete" if before_lines else "add"),
                                )
                            )

                    # Parse the new hunk
                    match = re.search(
                        r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
                    )
                    if match:
                        old_start = int(match.group(1))
                        new_start = int(match.group(3))

                        current_hunk_start = new_start
                        current_line_num = old_start
                        before_lines = []
                        after_lines = []
                        in_hunk = True
                    continue

                if not in_hunk:
                    continue

                # Parse the diff lines
                if line.startswith("-") and not line.startswith("---"):
                    # Deleted lines
                    before_lines.append(line[1:])
                    if current_line_num is not None:
                        current_line_num += 1
                elif line.startswith("+") and not line.startswith("+++"):
                    # Added lines
                    after_lines.append(line[1:])
                elif line.startswith(" "):
                    # Unchanged lines
                    before_lines.append(line[1:])
                    after_lines.append(line[1:])
                    if current_line_num is not None:
                        current_line_num += 1

            # Save the last hunk
            if in_hunk and current_hunk_start is not None:
                if before_lines or after_lines:
                    edits.append(
                        Edit(
                            file_path=abs_path,
                            line_start=current_hunk_start,
                            line_end=current_hunk_start + len(after_lines) - 1
                            if after_lines
                            else current_hunk_start,
                            before="\n".join(before_lines),
                            after="\n".join(after_lines),
                            edit_type="modify"
                            if before_lines and after_lines
                            else ("delete" if before_lines else "add"),
                        )
                    )

        finally:
            # Clean up the temporarily added file
            subprocess.run(
                ["git", "reset", "--", abs_path],
                cwd=project_root,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

    except Exception:
        # Return an empty list if parsing fails
        pass

    return edits
