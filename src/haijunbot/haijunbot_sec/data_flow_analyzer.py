# -*- coding: utf-8 -*-
"""Built-in data flow analyzer - data flow analysis based on ProjectDatabase

Does not depend on external tools (Joern, etc.); directly uses the data collected by DataCollector for taint propagation analysis.
Data sources:
- data_flow table: definition and use positions of variables
- call_graph table: function call relationships
- pointer_states table: pointer state tracking

Core algorithm:
1. Start from the taint sources and identify tainted variables
2. Propagate along the data flow, tracking the use of tainted variables
3. Check whether a taint sink is reached
4. Check whether a sanitizer was applied along the way
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass

from haijunbot.haijunbot_sec.taint_analyzer import (
    TaintAnalyzer,
    TaintPath,
    TaintSource,
    TaintSink,
    TaintSeverity,
    TaintAnalyzerFactory,
)
from haijunbot.haijunbot_sec.project_database import ProjectDatabase


@dataclass
class TaintState:
    """Taint state tracking"""

    var_name: str
    source: str
    file_path: str
    line: int
    scope: str
    sanitized: bool = False


class BuiltinDataFlowAnalyzer(TaintAnalyzer):
    """Built-in data flow analyzer - based on ProjectDatabase"""

    def __init__(
        self,
        database: Optional[ProjectDatabase] = None,
        project_path: Optional[str] = None,
    ):
        super().__init__()
        self.database = database
        self.project_path = project_path
        self._taint_states: Dict[str, List[TaintState]] = {}  # var_name -> states
        self._visited: Set[Tuple[str, str, int]] = set()  # (var_name, file, line)

    def is_available(self) -> bool:
        """Always available; does not depend on external tools"""
        return True

    def get_name(self) -> str:
        return "builtin"

    def get_version(self) -> str:
        return "1.0.0"

    def analyze(self, source_code: str, file_path: str = "") -> List[TaintPath]:
        """Analyze the taint propagation paths in the source code

        Args:
            source_code: Source code content
            file_path: File path

        Returns:
            List of taint propagation paths
        """
        if not self.database:
            # Try to create a database connection from project_path
            if self.project_path:
                db_path = Path(self.project_path) / ".haijunbot" / "hsec" / "analysis.db"
                if db_path.exists():
                    self.database = ProjectDatabase(
                        self.project_path, db_path=str(db_path)
                    )
            else:
                return []

        if not self.database:
            return []

        # Clear state
        self._taint_states.clear()
        self._visited.clear()

        # Execute the taint analysis
        paths = self._analyze_taint_flow(file_path)
        return paths

    def analyze_file(self, file_path: str) -> List[TaintPath]:
        """Analyze a single file"""
        if not self.database:
            return []

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            source_code = f.read()

        rel_path = self._get_relative_path(file_path)
        return self.analyze(source_code, rel_path)

    def _get_relative_path(self, file_path: str) -> str:
        """Get the relative path"""
        if self.project_path:
            try:
                return str(Path(file_path).relative_to(self.project_path))
            except ValueError:
                pass
        return file_path

    def _analyze_taint_flow(self, file_path: str) -> List[TaintPath]:
        """Perform the taint flow analysis

        Core algorithm:
        1. Identify the taint sources
        2. Propagate the taint along the data flow
        3. Check whether a taint sink is reached
        4. Check whether a sanitizer was applied along the way
        """
        paths = []

        # 1. Identify the taint sources
        source_vars = self._identify_sources(file_path)

        # 2. Propagate the taint
        for var_name, source_info in source_vars.items():
            self._propagate_taint(var_name, source_info)

        # 3. Check the taint sinks
        for var_name, states in self._taint_states.items():
            for state in states:
                if state.sanitized:
                    continue
                sink_hits = self._check_sinks(var_name, state)
                for sink_info in sink_hits:
                    path = TaintPath(
                        source=state.source,
                        sink=sink_info["sink"],
                        path=[var_name],
                        confidence=0.8,
                        severity=TaintSeverity.HIGH,
                        description=f"taint propagates from {state.source} to {sink_info['sink']}",
                        file_path=sink_info["file_path"],
                        line_number=sink_info["line"],
                        code_snippet=sink_info.get("code", ""),
                    )
                    paths.append(path)

        return paths

    def _identify_sources(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        """Identify the taint source variables

        Query the data_flow table to find variables whose value provenance is a taint source
        """
        source_vars = {}

        if not self.database:
            return source_vars

        # Get the data flow nodes of the file
        flow_nodes = self.database.get_data_flow_by_file(file_path)

        # Check whether each definition node originates from a taint source
        for node in flow_nodes:
            if node["node_type"] != "def":
                continue

            var_name = node["var_name"]
            value_source = node.get("value_source", "")

            # Check whether value_source matches a configured taint source
            for source in self.sources:
                for pattern in source.patterns:
                    if pattern in value_source or value_source == pattern:
                        source_vars[var_name] = {
                            "source": source.name,
                            "file_path": node["file_path"],
                            "line": node["line"],
                            "scope": node["scope"],
                        }
                        break

        # Also check function parameters (param_in)
        for node in flow_nodes:
            if node["node_type"] == "param_in":
                var_name = node["var_name"]
                # Parameters may come from external callers; treat them as potential taint sources
                for source in self.sources:
                    if source.category in ("user_input", "network", "environment"):
                        # Check whether the callers come from an external input function
                        if not self.database:
                            continue
                        callers = self.database.get_callers(node["scope"])
                        for caller in callers:
                            caller_name = caller["caller_name"]
                            for src in self.sources:
                                if caller_name in src.patterns:
                                    source_vars[var_name] = {
                                        "source": src.name,
                                        "file_path": node["file_path"],
                                        "line": node["line"],
                                        "scope": node["scope"],
                                    }

        return source_vars

    def _propagate_taint(self, var_name: str, source_info: Dict[str, Any]):
        """Propagate the taint along the data flow

        Start from the taint source variable and track its use and propagation
        """
        if not self.database:
            return

        # Initial taint state
        initial_state = TaintState(
            var_name=var_name,
            source=source_info["source"],
            file_path=source_info["file_path"],
            line=source_info["line"],
            scope=source_info["scope"],
        )
        self._taint_states[var_name] = [initial_state]
        self._visited.add((var_name, source_info["file_path"], source_info["line"]))

        # Get the use positions of the variable
        use_sites = self.database.get_use_sites(var_name, source_info["scope"])

        for use in use_sites:
            key = (var_name, use["file_path"], use["line"])
            if key in self._visited:
                continue
            self._visited.add(key)

            # Check whether a sanitizer was applied
            sanitized = self._check_sanitization(use)

            # Add the taint state
            state = TaintState(
                var_name=var_name,
                source=source_info["source"],
                file_path=use["file_path"],
                line=use["line"],
                scope=use["scope"],
                sanitized=sanitized,
            )
            if var_name not in self._taint_states:
                self._taint_states[var_name] = []
            self._taint_states[var_name].append(state)

            # Continue propagating (assignment to other variables)
            self._propagate_assignment(var_name, source_info, use)

    def _propagate_assignment(
        self, source_var: str, source_info: Dict[str, Any], use_site: Dict[str, Any]
    ):
        """Propagate the taint to the assignment target variables

        For example: char* p = user_input; then p is also tainted
        """
        if not self.database:
            return

        # Get the definition nodes within the same scope and check whether any variable is assigned source_var
        flow_nodes = self.database.get_data_flow_by_file(use_site["file_path"])

        for node in flow_nodes:
            if node["node_type"] != "def":
                continue
            if node["scope"] != use_site["scope"]:
                continue
            if node["line"] <= source_info["line"]:
                continue

            # Check whether value_source contains source_var
            value_source = node.get("value_source", "")
            if source_var in value_source:
                target_var = node["var_name"]
                key = (target_var, node["file_path"], node["line"])
                if key in self._visited:
                    continue

                # Propagate the taint to the target variable
                self._propagate_taint(
                    target_var,
                    {
                        "source": source_info["source"],
                        "file_path": node["file_path"],
                        "line": node["line"],
                        "scope": node["scope"],
                    },
                )

    def _check_sanitization(self, use_site: Dict[str, Any]) -> bool:
        """Check whether a sanitizer function was applied"""
        if not self.database:
            return False

        # Get the call relations and check whether a sanitizer function was called
        callees = self.database.get_callees(use_site["scope"], use_site["file_path"])

        for callee in callees:
            callee_name = callee["callee_name"]
            if callee_name in self.sanitizers:
                return True

        return False

    def _check_sinks(self, var_name: str, state: TaintState) -> List[Dict[str, Any]]:
        """Check whether the tainted variable reaches a taint sink"""
        sink_hits = []

        if not self.database:
            return sink_hits

        # Get the use positions of the variable
        use_sites = self.database.get_use_sites(var_name, state.scope)

        for use in use_sites:
            # Check whether the use position matches a taint sink
            for sink in self.sinks:
                for pattern in sink.patterns:
                    # Check whether it is used as an argument of the sink function
                    if self._is_sink_use(use, pattern, var_name):
                        sink_hits.append(
                            {
                                "sink": sink.name,
                                "file_path": use["file_path"],
                                "line": use["line"],
                                "code": f"{var_name} used in {sink.name}",
                            }
                        )

        return sink_hits

    def _is_sink_use(
        self, use_site: Dict[str, Any], sink_pattern: str, var_name: str
    ) -> bool:
        """Check whether the use position is a taint sink

        sink_pattern may be a function name (such as system) or an operator (such as ->, *)
        """
        if not self.database:
            return False

        # Get the call relations
        callees = self.database.get_callees(use_site["scope"], use_site["file_path"])

        for callee in callees:
            if callee["callee_name"] == sink_pattern:
                # Check whether the call line is near use_site
                if abs(callee["caller_line"] - use_site["line"]) <= 2:
                    return True

        # For operator-type sinks (such as dereference), check use_site itself
        if sink_pattern in ("->", "*", "[]"):  # Dereference operations
            # Check whether it is a dereference use
            # This requires finer-grained AST analysis; use a heuristic for now
            return True  # Simplified handling

        return False


# Register the analyzer
TaintAnalyzerFactory.register("builtin", BuiltinDataFlowAnalyzer)


# ---------------------------
# Data flow analysis related classes (compatible with c_checker imports)
# ---------------------------


@dataclass
class PointerState:
    """Pointer state tracking"""

    # Pointer state constants
    ALLOCATED = "ALLOCATED"
    FREED = "FREED"
    NULLIFIED = "NULLIFIED"
    UNKNOWN = "UNKNOWN"

    var_name: str
    points_to: List[str]  # Pointed-to variables/memory locations
    state: str = "UNKNOWN"  # ALLOCATED/FREED/NULLIFIED/UNKNOWN
    is_null: bool = False  # Whether it may be NULL
    is_freed: bool = False  # Whether it has been freed
    is_tainted: bool = False  # Whether it is tainted
    file_path: str = ""
    line: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "var_name": self.var_name,
            "points_to": self.points_to,
            "state": self.state,
            "is_null": self.is_null,
            "is_freed": self.is_freed,
            "is_tainted": self.is_tainted,
            "file_path": self.file_path,
            "line": self.line,
        }


@dataclass
class DataFlowResult:
    """Data flow analysis result"""

    var_name: str
    def_sites: List[Dict[str, Any]]  # Definition position list
    use_sites: List[Dict[str, Any]]  # Use position list
    flows_to: List[str]  # List of variables it flows to
    tainted: bool = False  # Whether it is tainted
    ownership_transfer: Optional[List[str]] = None  # Variables with transferred ownership
    freed_vars: Optional[List[str]] = None  # Freed variables
    null_checked_vars: Optional[List[str]] = None  # Variables checked for NULL
    dead_code_lines: Optional[List[int]] = None  # Dead code line numbers
    null_checks: Optional[Dict[str, List[int]]] = None  # var_name -> [check_lines]
    pointer_states: Optional[Dict[str, PointerState]] = None  # var_name -> PointerState

    def __post_init__(self):
        if self.ownership_transfer is None:
            self.ownership_transfer = []
        if self.freed_vars is None:
            self.freed_vars = []
        if self.null_checked_vars is None:
            self.null_checked_vars = []
        if self.dead_code_lines is None:
            self.dead_code_lines = []
        if self.null_checks is None:
            self.null_checks = {}
        if self.pointer_states is None:
            self.pointer_states = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "var_name": self.var_name,
            "def_sites": self.def_sites,
            "use_sites": self.use_sites,
            "flows_to": self.flows_to,
            "tainted": self.tainted,
            "ownership_transfer": self.ownership_transfer,
            "freed_vars": self.freed_vars,
            "null_checked_vars": self.null_checked_vars,
            "dead_code_lines": self.dead_code_lines,
            "null_checks": self.null_checks,
            "pointer_states": {k: v.to_dict() for k, v in self.pointer_states.items()}
            if self.pointer_states
            else {},
        }


class DataFlowAnalyzer:
    """Data flow analyzer - high-level interface

    Provides richer data flow analysis functionality, including pointer analysis, taint propagation, etc.
    This is a high-level wrapper around BuiltinDataFlowAnalyzer.
    """

    def __init__(
        self,
        database: Optional[ProjectDatabase] = None,
        project_path: Optional[str] = None,
    ):
        self._analyzer = BuiltinDataFlowAnalyzer(
            database=database, project_path=project_path
        )
        self.database = database
        self.project_path = project_path
        self._pointer_states: Dict[str, PointerState] = {}

    def analyze(self, source_code: str, file_path: str = "") -> List[TaintPath]:
        """Execute the taint analysis"""
        return self._analyzer.analyze(source_code, file_path)

    def analyze_file(self, file_path: str) -> List[TaintPath]:
        """Analyze a single file"""
        return self._analyzer.analyze_file(file_path)

    def analyze_code(
        self,
        source_code: str,
        is_cpp: bool = False,
        database: Optional[ProjectDatabase] = None,
        file_path: str = "",
    ) -> "DataFlowResult":
        """Analyze the data flow of the source code

        Compatible with the c_checker call interface.
        Provides precise data flow analysis results based on the database.

        Args:
            source_code: Source code content
            is_cpp: Whether it is C++ code
            database: Project database
            file_path: File path

        Returns:
            A DataFlowResult object
        """
        # Update the database reference
        if database:
            self.database = database
            self._analyzer.database = database

        # Execute the taint analysis
        taint_paths = self._analyzer.analyze(source_code, file_path)

        # If a database is available, build a more complete result
        if self.database and file_path:
            # Get all data flow nodes of the file from the database
            flow_nodes = self.database.get_data_flow_by_file(file_path)

            # Collect all variable names
            all_vars = set()
            for node in flow_nodes:
                all_vars.add(node.get("var_name", ""))

            # Build def_sites and use_sites
            def_sites = [n for n in flow_nodes if n.get("node_type") == "def"]
            use_sites = [n for n in flow_nodes if n.get("node_type") == "use"]

            # Build flows_to
            flows_to = []
            for use in use_sites:
                target = use.get("target_var")
                if target and target not in flows_to:
                    flows_to.append(target)

            # Build pointer_states (collect from all variables)
            pointer_states: Dict[str, PointerState] = {}
            for var in all_vars:
                if not var:
                    continue
                ps = self._build_pointer_states(var)
                pointer_states.update(ps)

            # Build null_checks
            null_checks: Dict[str, List[int]] = {}
            for var in all_vars:
                if not var:
                    continue
                nc = self._build_null_checks(var)
                for k, v in nc.items():
                    if k not in null_checks:
                        null_checks[k] = []
                    null_checks[k].extend(v)

            # Collect freed_vars and null_checked_vars
            freed_vars = [v for v, ps in pointer_states.items() if ps.is_freed]
            null_checked_vars = list(null_checks.keys())

            # Collect ownership_transfer
            ownership_transfer = []
            for use in use_sites:
                if use.get("use_type") == "ownership_transfer":
                    target = use.get("var_name", "")
                    if target and target not in ownership_transfer:
                        ownership_transfer.append(target)

            return DataFlowResult(
                var_name="",
                def_sites=def_sites,
                use_sites=use_sites,
                flows_to=flows_to,
                tainted=len(taint_paths) > 0,
                ownership_transfer=ownership_transfer,
                freed_vars=freed_vars,
                null_checked_vars=null_checked_vars,
                null_checks=null_checks,
                pointer_states=pointer_states,
            )

        # Return the basic result without a database
        return DataFlowResult(
            var_name="",
            def_sites=[],
            use_sites=[],
            flows_to=[],
            tainted=len(taint_paths) > 0,
        )

    def get_data_flow_result(
        self, var_name: str, scope: str = ""
    ) -> Optional[DataFlowResult]:
        """Get the data flow analysis result of a variable

        Args:
            var_name: Variable name
            scope: Scope (function name)

        Returns:
            A DataFlowResult or None
        """
        if not self.database:
            return None

        def_sites = self.database.get_def_sites(var_name, scope)
        use_sites = self.database.get_use_sites(var_name, scope)

        if not def_sites and not use_sites:
            return None

        # Analyze the flow direction
        flows_to = []
        for use in use_sites:
            target = use.get("target_var")
            if target and target not in flows_to:
                flows_to.append(target)

        # Get the pointer states from the database
        pointer_states = self._build_pointer_states(var_name, scope)

        # Get the NULL check information from the database
        null_checks = self._build_null_checks(var_name, scope)

        # Check whether it is tainted
        tainted = self.is_tainted(var_name, scope)

        return DataFlowResult(
            var_name=var_name,
            def_sites=def_sites,
            use_sites=use_sites,
            flows_to=flows_to,
            tainted=tainted,
            pointer_states=pointer_states,
            null_checks=null_checks,
        )

    def _build_pointer_states(
        self, var_name: str, scope: str = ""
    ) -> Dict[str, PointerState]:
        """Build the pointer state mapping from the database"""
        pointer_states: Dict[str, PointerState] = {}

        if not self.database:
            return pointer_states

        try:
            # Query the pointer_states table
            ptr_records = self.database.get_pointer_states(var_name)
            for record in ptr_records:
                pv = record.get("var_name", var_name)
                state_str = record.get("state", PointerState.UNKNOWN)
                pointer_states[pv] = PointerState(
                    var_name=pv,
                    points_to=[],
                    state=state_str,
                    is_null=state_str == PointerState.NULLIFIED,
                    is_freed=state_str == PointerState.FREED,
                    file_path=record.get("file_path", ""),
                    line=record.get("line", 0),
                )
        except (AttributeError, Exception):
            pass

        return pointer_states

    def _build_null_checks(
        self, var_name: str, scope: str = ""
    ) -> Dict[str, List[int]]:
        """Build the NULL check mapping from the database"""
        null_checks: Dict[str, List[int]] = {}

        if not self.database:
            return null_checks

        try:
            # Query the NULL check patterns in use_sites
            use_sites = self.database.get_use_sites(var_name, scope)
            for use in use_sites:
                # Check whether it is a NULL check (if (ptr != NULL), etc.)
                if use.get("use_type") == "null_check":
                    pv = use.get("var_name", var_name)
                    if pv not in null_checks:
                        null_checks[pv] = []
                    null_checks[pv].append(use.get("line", 0))
        except (AttributeError, Exception):
            pass

        return null_checks

    def get_pointer_state(
        self, var_name: str, file_path: str = "", line: int = 0
    ) -> Optional[PointerState]:
        """Get the pointer state

        Args:
            var_name: Pointer variable name
            file_path: File path
            line: Line number

        Returns:
            A PointerState or None
        """
        # Check the cache
        cache_key = f"{var_name}@{file_path}:{line}"
        if cache_key in self._pointer_states:
            return self._pointer_states[cache_key]

        if not self.database:
            return None

        # Query the pointer state from the database
        # TODO: implement a query based on the pointer_states table
        state = PointerState(
            var_name=var_name,
            points_to=[],
            is_null=False,
            is_freed=False,
            is_tainted=False,
            file_path=file_path,
            line=line,
        )

        self._pointer_states[cache_key] = state
        return state

    def is_tainted(self, var_name: str, scope: str = "") -> bool:
        """Check whether the variable is tainted"""
        result = self.get_data_flow_result(var_name, scope)
        if result:
            return result.tainted
        return False

    def is_safe_access(
        self,
        var_name: str,
        line: int,
        dataflow_result: Optional["DataFlowResult"] = None,
    ) -> bool:
        """Check whether a variable access is safe (used for UAF false-positive filtering)

        Check logic:
        1. Whether it is set to NULL after free (NULLIFIED state)
        2. Whether it is protected by a NULL check before access

        Args:
            var_name: Variable name
            line: Access line number
            dataflow_result: Data flow analysis result

        Returns:
            True means the access is safe (false positive), False means it may be unsafe
        """
        if not dataflow_result:
            return False

        # Check the pointer state: if it is set to NULL after free, there should be a NULL check before access
        if (
            dataflow_result.pointer_states
            and var_name in dataflow_result.pointer_states
        ):
            ptr_state = dataflow_result.pointer_states[var_name]
            if ptr_state.state == PointerState.NULLIFIED:
                # Set to NULL after free; check whether there is a NULL check protection
                if (
                    dataflow_result.null_checks
                    and var_name in dataflow_result.null_checks
                ):
                    for check_line in dataflow_result.null_checks[var_name]:
                        if check_line < line:
                            return True  # Protected by a NULL check, safe

        return False

    def configure_sources(self, sources: List[TaintSource]):
        """Configure the taint sources"""
        self._analyzer.configure_sources(sources)

    def configure_sinks(self, sinks: List[TaintSink]):
        """Configure the taint sinks"""
        self._analyzer.configure_sinks(sinks)

    def configure_sanitizers(self, sanitizers: List[str]):
        """Configure the sanitizer functions"""
        self._analyzer.configure_sanitizers(sanitizers)


# Helper function: create an analyzer instance
def create_builtin_analyzer(
    project_path: str, database: Optional[ProjectDatabase] = None
) -> BuiltinDataFlowAnalyzer:
    """Create a built-in data flow analyzer instance"""
    return BuiltinDataFlowAnalyzer(database=database, project_path=project_path)


# Helper function: use the built-in analyzer to perform taint analysis
def analyze_taint_builtin(
    project_path: str,
    file_path: str,
    sources: List[TaintSource],
    sinks: List[TaintSink],
    sanitizers: Optional[List[str]] = None,
    database: Optional[ProjectDatabase] = None,
) -> List[TaintPath]:
    """Use the built-in analyzer to perform taint analysis"""
    analyzer = create_builtin_analyzer(project_path, database)
    analyzer.configure_sources(sources)
    analyzer.configure_sinks(sinks)
    if sanitizers:
        analyzer.configure_sanitizers(sanitizers)

    return analyzer.analyze_file(file_path)