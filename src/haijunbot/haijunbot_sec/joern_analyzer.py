"""
Joern taint analyzer - a taint analysis implementation based on Joern CPG

Joern is an open-source (Apache 2.0 licensed) code analysis platform that supports
multiple languages such as C/C++.
It performs taint propagation analysis by generating a code property graph (CPG).
"""

import subprocess
import tempfile
import os
from typing import List, Optional, TYPE_CHECKING

from .taint_analyzer import (
    TaintAnalyzer,
    TaintPath,
    TaintSource,
    TaintSink,
    TaintAnalyzerFactory,
)

if TYPE_CHECKING:
    from haijunbot.haijunbot_sec.project_database import ProjectDatabase


class JoernAnalyzer(TaintAnalyzer):
    """
    A Joern-based taint analyzer implementation

    Joern is an open-source code analysis platform that performs taint propagation
    analysis by generating a code property graph (CPG).
    It supports multiple languages such as C/C++.
    """

    def __init__(
        self, joern_path: str = "joern", database: Optional["ProjectDatabase"] = None
    ):
        """
        Initialize the Joern analyzer

        Args:
            joern_path: Path to the Joern CLI tool; defaults to "joern" (assumed to be in PATH)
            database: Project database instance (optional)
        """
        self.joern_path = joern_path
        self.database = database
        self._check_joern_available()

    def _check_joern_available(self) -> bool:
        """
        Check whether Joern is available

        Returns:
            bool: Whether Joern is available
        """
        try:
            result = subprocess.run(
                [self.joern_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def is_available(self) -> bool:
        """
        Check whether the analyzer is available

        Returns:
            bool: True if Joern is installed and available
        """
        return self._check_joern_available()

    def get_name(self) -> str:
        """
        Get the analyzer name

        Returns:
            str: Analyzer name
        """
        return "Joern"

    def get_version(self) -> str:
        """
        Get the analyzer version

        Returns:
            str: Analyzer version number
        """
        try:
            result = subprocess.run(
                [self.joern_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                # Parse the version number
                import re

                match = re.search(r"(\d+\.\d+\.\d+)", result.stdout)
                if match:
                    return match.group(1)
            return "unknown"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return "unknown"

    def analyze_file(self, file_path: str) -> List[TaintPath]:
        """
        Analyze a file

        Args:
            file_path: File path

        Returns:
            List[TaintPath]: List of taint propagation paths
        """
        try:
            with open(file_path, "r") as f:
                source_code = f.read()
            return self.analyze(source_code, file_path)
        except (IOError, OSError):
            return []

    def analyze(
        self,
        source_code: str,
        file_path: str = "",
        database: Optional["ProjectDatabase"] = None,
    ) -> List[TaintPath]:
        """
        Analyze taint propagation paths in the source code

        Args:
            source_code: Source code content
            file_path: Source code file path
            database: Project database instance (optional, overrides the setting at initialization)

        Returns:
            List[TaintPath]: List of detected taint propagation paths
        """
        # Use the passed-in database or the database from initialization
        db = database or self.database
        # Create a temporary working directory
        with tempfile.TemporaryDirectory() as tmpdir:
            # Write the source code file
            src_file = os.path.join(tmpdir, os.path.basename(file_path))
            with open(src_file, "w") as f:
                f.write(source_code)

            # Generate the CPG
            cpg_file = os.path.join(tmpdir, "cpg.bin")
            try:
                subprocess.run(
                    [
                        self.joern_path,
                        "--script",
                        "create-cpg",
                        "--param",
                        f"inputPath={src_file}",
                        "--param",
                        f"outputPath={cpg_file}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=True,
                )
            except subprocess.CalledProcessError:
                return []
            except subprocess.TimeoutExpired:
                return []

            # Execute the taint analysis
            paths = self._run_taint_analysis(cpg_file, self.sources, self.sinks)

            # If a database is provided, enhance the taint analysis results
            if db is not None and file_path:
                paths = self._enhance_with_database(paths, db, file_path)

            return paths

    def _run_taint_analysis(
        self, cpg_file: str, sources: List[TaintSource], sinks: List[TaintSink]
    ) -> List[TaintPath]:
        """
        Execute the taint analysis

        Args:
            cpg_file: CPG file path
            sources: List of taint sources
            sinks: List of taint sinks

        Returns:
            List[TaintPath]: List of detected taint propagation paths
        """
        taint_paths = []

        # Generate a query for each taint source and sink
        for source in sources:
            for sink in sinks:
                # Generate the Joern query script
                query_script = self._generate_taint_query(source, sink)

                # Execute the query
                try:
                    result = subprocess.run(
                        [
                            self.joern_path,
                            "--script",
                            "query",
                            "--param",
                            f"cpgFile={cpg_file}",
                            "--param",
                            f"query={query_script}",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

                    if result.returncode == 0:
                        # Parse the result
                        paths = self._parse_joern_output(result.stdout, source, sink)
                        taint_paths.extend(paths)

                except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                    # On query failure, continue with the next one
                    continue

        return taint_paths

    def _generate_taint_query(self, source: TaintSource, sink: TaintSink) -> str:
        """
        Generate the Joern taint analysis query script

        Args:
            source: Taint source
            sink: Taint sink

        Returns:
            str: Joern query script
        """
        # Build the source query (match function calls or arguments)
        source_patterns = "|".join(source.patterns)
        source_query = f'cpg.call.name("{source_patterns}").argument'

        # Build the sink query (match function calls)
        sink_patterns = "|".join(sink.patterns)
        sink_query = f'cpg.call.name("{sink_patterns}").argument'

        # Generate the reachableByFlows query
        query = f"""def source = {source_query}
def sink = {sink_query}
sink.reachableByFlows(source).l"""

        return query

    def _parse_joern_output(
        self, output: str, source: TaintSource, sink: TaintSink
    ) -> List[TaintPath]:
        """
        Parse the Joern output result

        Args:
            output: Joern output string
            source: Taint source
            sink: Taint sink

        Returns:
            List[TaintPath]: List of parsed taint paths
        """
        paths = []

        # Joern output format example:
        # ┌─────────────────┬────────────────────────────┬──────────┬──────┬─────┐
        # │nodeType         │tracked                     │lineNumber│method│file │
        # ├─────────────────┼────────────────────────────┼──────────┼──────┼─────┤
        # │MethodParameterIn│main(int argc, char *argv[])│5         │main  │X42.c│
        # │Call             │strcmp(argv[1], "42")       │6         │main  │X42.c│
        # └─────────────────┴────────────────────────────┴──────────┴──────┴─────┘

        # Simple parsing: find lines containing lineNumber
        lines = output.split("\n")
        for line in lines:
            if "lineNumber" in line or "line" in line.lower():
                # Try to extract the line number
                import re

                line_match = re.search(r"lineNumber[=\s]+(\d+)", line)
                if line_match:
                    line_number = int(line_match.group(1))

                    # Create a taint path
                    path = TaintPath(
                        source=source.name,
                        sink=sink.name,
                        path=[source.name, sink.name],
                        confidence=0.8,  # Confidence based on Joern analysis
                        severity=sink.severity,
                        description=f"Taint propagates from {source.name} to {sink.name}",
                        line_number=line_number,
                    )
                    paths.append(path)

        return paths

    def _enhance_with_database(
        self,
        paths: List[TaintPath],
        database: "ProjectDatabase",
        file_path: str,
    ) -> List[TaintPath]:
        """
        Enhance the taint analysis results using the database

        Args:
            paths: List of original taint paths
            database: Project database instance
            file_path: Current file path

        Returns:
            List[TaintPath]: List of enhanced taint paths
        """
        if not paths:
            return paths

        try:
            # Get the complete call graph (the method takes no arguments)
            call_graph = database.get_call_graph()

            # Get the data flow nodes of the current file
            data_flow_nodes = database.get_data_flow_by_file(file_path)

            # Enhance each taint path
            enhanced_paths = []
            for path in paths:
                enhanced_path = path

                # If there is call graph information, try to extend the taint path
                if call_graph:
                    for call_info in call_graph:
                        # Check whether the taint path passes through this call site
                        if self._path_involves_call(path, call_info):
                            # Extend the taint path, adding cross-function information
                            enhanced_path = self._extend_path_with_call(
                                enhanced_path, call_info, database
                            )

                # If there are data flow nodes, try to extend the taint path
                if data_flow_nodes:
                    for node in data_flow_nodes:
                        if self._path_involves_data_node(path, node):
                            enhanced_path = self._extend_path_with_data_node(
                                enhanced_path, node
                            )

                enhanced_paths.append(enhanced_path)

            return enhanced_paths

        except Exception:
            # On database query failure, return the original paths
            return paths

    def _path_involves_call(self, path: TaintPath, call_info: dict) -> bool:
        """Check whether the taint path involves a certain call site"""
        # Simple implementation: check whether the called function name is in the path
        caller_func = call_info.get("caller_function", "")
        callee_func = call_info.get("callee_function", "")
        return caller_func in path.path or callee_func in path.path

    def _extend_path_with_call(
        self, path: TaintPath, call_info: dict, database: "ProjectDatabase"
    ) -> TaintPath:
        """Extend the taint path, adding cross-function call information"""
        # Create a new path list
        new_path = list(path.path)

        # Add a cross-function call node
        callee_file = call_info.get("callee_file", "")
        callee_func = call_info.get("callee_function", "")
        if callee_file and callee_func:
            cross_file_node = f"{callee_file}:{callee_func}"
            if cross_file_node not in new_path:
                new_path.append(cross_file_node)

        # Update the description
        new_description = path.description
        if callee_file:
            new_description += f" (Cross-function call: {callee_func}@{callee_file})"

        return TaintPath(
            source=path.source,
            sink=path.sink,
            path=new_path,
            confidence=min(path.confidence + 0.1, 1.0),  # Increase confidence
            severity=path.severity,
            description=new_description,
            line_number=path.line_number,
        )

    def _path_involves_data_node(self, path: TaintPath, node: dict) -> bool:
        """Check whether the taint path involves a certain data flow node"""
        var_name = node.get("var_name", "")
        return var_name in path.path

    def _extend_path_with_data_node(self, path: TaintPath, node: dict) -> TaintPath:
        """Extend the taint path, adding data flow node information"""
        new_path = list(path.path)

        # Add data flow node information
        var_name = node.get("var_name", "")
        node_file = node.get("file_path", "")
        node_line = node.get("line", 0)
        node_type = node.get("node_type", "")

        if node_file and var_name:
            data_node = f"{node_file}:{var_name}@{node_type}"
            if data_node not in new_path:
                new_path.append(data_node)

        # Update the description
        new_description = path.description
        if node_file and var_name:
            new_description += f" (Data flow: {var_name}@{node_file}:{node_line})"

        return TaintPath(
            source=path.source,
            sink=path.sink,
            path=new_path,
            confidence=min(path.confidence + 0.15, 1.0),  # Increase confidence
            severity=path.severity,
            description=new_description,
            line_number=path.line_number,
        )


# Register with the factory
TaintAnalyzerFactory.register("joern", JoernAnalyzer)
