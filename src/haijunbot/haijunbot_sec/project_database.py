# -*- coding: utf-8 -*-
"""
Project-level database manager - persistent storage supporting cross-file analysis

Core functionality:
1. Symbol table storage (functions, variables, type definitions)
2. Call relation graph storage
3. Data flow graph storage (Def-Use chains)
4. Pointer state tracking
5. Type information storage
6. File metadata management
7. Analysis result caching

Database Schema design:
- files: file metadata (path, hash, modification time)
- symbols: symbol table (functions, variables, types)
- call_graph: call relation graph
- data_flow: data flow graph (Def-Use chains)
- pointer_states: pointer state tracking
- type_info: type information
- analysis_cache: analysis result cache
"""

import sqlite3
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from contextlib import contextmanager

from haijunbot.haijunbot_utils.output import PrettyOutput


# ============================================================================
# Data structure definitions
# ============================================================================


@dataclass
class FileInfo:
    """File information"""

    path: str
    hash: str  # File content hash
    last_modified: datetime
    language: str  # c, cpp, rust, etc.
    line_count: int


@dataclass
class SymbolInfo:
    """Symbol information"""

    name: str
    kind: str  # function, variable, type, parameter, etc.
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None  # Function signature
    type_name: Optional[str] = None  # Variable type
    scope: Optional[str] = None  # Scope (function name or global)
    is_external: bool = False  # Whether it is an external symbol


@dataclass
class CallRelation:
    """Call relation"""

    caller_name: str
    caller_file: str
    caller_line: int
    callee_name: str
    callee_file: Optional[str] = None  # An external function may have no file
    callee_line: Optional[int] = None
    call_type: str = "direct"  # direct, virtual, function_pointer


@dataclass
class DataFlowNode:
    """Data flow node"""

    var_name: str
    file_path: str
    line: int
    node_type: str  # def, use, param_in, param_out, return
    scope: str  # Scope (function name)
    value_source: Optional[str] = None  # Value provenance (e.g. malloc, parameters, etc.)
    use_type: Optional[str] = (
        None  # Use type (null_check, ownership_transfer, condition, etc.)
    )


@dataclass
class PointerStateRecord:
    """Pointer state record"""

    var_name: str
    file_path: str
    line: int
    state: str  # ALLOCATED, FREED, NULLIFIED, UNKNOWN
    scope: str
    allocator: Optional[str] = None  # Allocation function (malloc, calloc, etc.)
    deallocator: Optional[str] = None  # Deallocation function (free, etc.)


@dataclass
class TypeInfo:
    """Type information"""

    type_name: str
    kind: str  # struct, union, enum, typedef, class
    file_path: str
    line_start: int
    line_end: int
    definition: Optional[str] = None  # Type definition text
    members: Optional[List[Dict[str, Any]]] = None  # Member list


# ============================================================================
# Database manager
# ============================================================================


class ProjectDatabase:
    """Project-level database manager"""

    def __init__(
        self, project_path: str, db_path: Optional[str] = None, in_memory: bool = False
    ):
        """
        Initialize the database manager

        Args:
            project_path: Project root directory path
            db_path: Database file path (defaults to .haijunbot/hsec/analysis.db under the project root)
            in_memory: Whether to use an in-memory database (for single-file temporary analysis)
        """
        self.project_path = Path(project_path).resolve()
        self._in_memory = in_memory

        if in_memory:
            self.db_path = Path(":memory:")
        else:
            self.db_path = (
                Path(db_path)
                if db_path
                else self.project_path / ".haijunbot" / "hsec" / "analysis.db"
            )

        # Ensure the database directory exists (in non-memory mode)
        if not in_memory:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize the database connection
        self._conn: Optional[sqlite3.Connection] = None
        self._batch_mode = False  # Batch commit mode
        self._init_database()

    def _init_database(self):
        """Initialize the database Schema"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Create the file metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    hash TEXT NOT NULL,
                    last_modified TIMESTAMP NOT NULL,
                    language TEXT NOT NULL,
                    line_count INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create the symbol table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    signature TEXT,
                    type_name TEXT,
                    scope TEXT,
                    is_external BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_path) REFERENCES files(path)
                )
            """)

            # Create the call relation graph
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS call_graph (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    caller_name TEXT NOT NULL,
                    caller_file TEXT NOT NULL,
                    caller_line INTEGER NOT NULL,
                    callee_name TEXT NOT NULL,
                    callee_file TEXT,
                    callee_line INTEGER,
                    call_type TEXT DEFAULT 'direct',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (caller_file) REFERENCES files(path),
                    FOREIGN KEY (callee_file) REFERENCES files(path)
                )
            """)

            # Create the data flow graph
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    var_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    node_type TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    value_source TEXT,
                    use_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_path) REFERENCES files(path)
                )
            """)

            # Create the pointer state tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pointer_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    var_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    allocator TEXT,
                    deallocator TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_path) REFERENCES files(path)
                )
            """)

            # Create the type information table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS type_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type_name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    line_start INTEGER NOT NULL,
                    line_end INTEGER NOT NULL,
                    definition TEXT,
                    members TEXT,  -- Member list stored in JSON format
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_path) REFERENCES files(path)
                )
            """)

            # Create the analysis result cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    analysis_type TEXT NOT NULL,
                    result TEXT NOT NULL,  -- Result stored in JSON format
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (file_path) REFERENCES files(path),
                    UNIQUE(file_path, analysis_type)
                )
            """)

            # Create indexes to optimize query performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_symbols_file ON symbols(file_path)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_symbols_kind ON symbols(kind)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_graph_caller ON call_graph(caller_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_graph_callee ON call_graph(callee_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_call_graph_caller_file ON call_graph(caller_file)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_data_flow_var ON data_flow(var_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_data_flow_file ON data_flow(file_path)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pointer_states_var ON pointer_states(var_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_pointer_states_file ON pointer_states(file_path)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_type_info_name ON type_info(type_name)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_type_info_file ON type_info(file_path)"
            )

            # Database migration: check and add missing columns
            # Migration 1: add the use_type column to the data_flow table
            cursor.execute(
                "SELECT name FROM pragma_table_info('data_flow') WHERE name='use_type'"
            )
            if not cursor.fetchone():
                cursor.execute("ALTER TABLE data_flow ADD COLUMN use_type TEXT")

            conn.commit()
            # Silent log output to avoid interfering with the progress bar display
            # PrettyOutput.auto_print(
            #     f"[ProjectDatabase] Database initialized: {self.db_path}"
            # )

    @contextmanager
    def _get_connection(self):
        """Get the database connection (context manager)"""
        if self._in_memory:
            # An in-memory database needs to keep the same connection, otherwise data is lost
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:")
                self._conn.row_factory = sqlite3.Row
            yield self._conn
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            try:
                yield conn
            finally:
                conn.close()

    # ============================================================================
    # File management
    # ============================================================================

    def add_file(self, file_info: FileInfo) -> int:
        """Add a file record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO files (path, hash, last_modified, language, line_count)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    file_info.path,
                    file_info.hash,
                    file_info.last_modified,
                    file_info.language,
                    file_info.line_count,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get a file record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files WHERE path = ?", (file_path,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_files(self) -> List[Dict[str, Any]]:
        """Get all file records"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM files ORDER BY path")
            return [dict(row) for row in cursor.fetchall()]

    def delete_file(self, file_path: str) -> bool:
        """Delete a file record and its associated data"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete the associated data
            cursor.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            cursor.execute(
                "DELETE FROM call_graph WHERE caller_file = ? OR callee_file = ?",
                (file_path, file_path),
            )
            cursor.execute("DELETE FROM data_flow WHERE file_path = ?", (file_path,))
            cursor.execute(
                "DELETE FROM pointer_states WHERE file_path = ?", (file_path,)
            )
            cursor.execute("DELETE FROM type_info WHERE file_path = ?", (file_path,))
            cursor.execute(
                "DELETE FROM analysis_cache WHERE file_path = ?", (file_path,)
            )
            cursor.execute("DELETE FROM files WHERE path = ?", (file_path,))
            conn.commit()
            return True

    def file_exists(self, file_path: str) -> bool:
        """Check whether the file exists"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM files WHERE path = ?", (file_path,))
            return cursor.fetchone() is not None

    def file_hash_changed(self, file_path: str, new_hash: str) -> bool:
        """Check whether the file hash has changed"""
        file_record = self.get_file(file_path)
        if not file_record:
            return True  # The file does not exist; treated as changed
        return file_record["hash"] != new_hash

    # ============================================================================
    # Batch commit mode
    # ============================================================================

    def begin_batch(self):
        """Start batch commit mode; defer commit to improve performance"""
        self._batch_mode = True

    def commit_batch(self):
        """Commit the batch operations and exit batch mode"""
        if self._conn:
            self._conn.commit()
        self._batch_mode = False

    # ============================================================================
    # Symbol management
    # ============================================================================

    def add_symbol(self, symbol: SymbolInfo) -> int:
        """Add a symbol record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO symbols (name, kind, file_path, line_start, line_end, signature, type_name, scope, is_external)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    symbol.name,
                    symbol.kind,
                    symbol.file_path,
                    symbol.line_start,
                    symbol.line_end,
                    symbol.signature,
                    symbol.type_name,
                    symbol.scope,
                    symbol.is_external,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def add_symbols_batch(self, symbols: List[SymbolInfo]) -> int:
        """Batch add symbol records"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO symbols (name, kind, file_path, line_start, line_end, signature, type_name, scope, is_external)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        s.name,
                        s.kind,
                        s.file_path,
                        s.line_start,
                        s.line_end,
                        s.signature,
                        s.type_name,
                        s.scope,
                        s.is_external,
                    )
                    for s in symbols
                ],
            )
            if not self._batch_mode:
                conn.commit()
            return len(symbols)

    def get_symbol(
        self, name: str, file_path: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get a symbol record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_path:
                cursor.execute(
                    "SELECT * FROM symbols WHERE name = ? AND file_path = ?",
                    (name, file_path),
                )
            else:
                cursor.execute("SELECT * FROM symbols WHERE name = ? LIMIT 1", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_symbols_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all symbols of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM symbols WHERE file_path = ? ORDER BY line_start",
                (file_path,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_symbols_by_kind(self, kind: str) -> List[Dict[str, Any]]:
        """Get all symbols of the specified kind"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM symbols WHERE kind = ? ORDER BY name", (kind,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_functions(self) -> List[Dict[str, Any]]:
        """Get all function symbols"""
        return self.get_symbols_by_kind("function")

    def get_variables(self) -> List[Dict[str, Any]]:
        """Get all variable symbols"""
        return self.get_symbols_by_kind("variable")

    def delete_symbols_by_file(self, file_path: str) -> int:
        """Delete all symbols of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM symbols WHERE file_path = ?", (file_path,))
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Call relation management
    # ============================================================================

    def add_call_relation(self, call: CallRelation) -> int:
        """Add a call relation"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO call_graph (caller_name, caller_file, caller_line, callee_name, callee_file, callee_line, call_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    call.caller_name,
                    call.caller_file,
                    call.caller_line,
                    call.callee_name,
                    call.callee_file,
                    call.callee_line,
                    call.call_type,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def add_call_relations_batch(self, calls: List[CallRelation]) -> int:
        """Batch add call relations"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO call_graph (caller_name, caller_file, caller_line, callee_name, callee_file, callee_line, call_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        c.caller_name,
                        c.caller_file,
                        c.caller_line,
                        c.callee_name,
                        c.callee_file,
                        c.callee_line,
                        c.call_type,
                    )
                    for c in calls
                ],
            )
            if not self._batch_mode:
                conn.commit()
            return len(calls)

    def get_callers(self, callee_name: str) -> List[Dict[str, Any]]:
        """Get all callers of the specified function"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM call_graph WHERE callee_name = ? ORDER BY caller_file, caller_line
            """,
                (callee_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_callees(
        self, caller_name: str, caller_file: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all functions called by the specified function"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if caller_file:
                cursor.execute(
                    """
                    SELECT * FROM call_graph WHERE caller_name = ? AND caller_file = ? ORDER BY caller_line
                """,
                    (caller_name, caller_file),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM call_graph WHERE caller_name = ? ORDER BY caller_file, caller_line
                """,
                    (caller_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_call_graph(self) -> List[Dict[str, Any]]:
        """Get the complete call graph"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM call_graph ORDER BY caller_file, caller_line")
            return [dict(row) for row in cursor.fetchall()]

    def delete_call_relations_by_file(self, file_path: str) -> int:
        """Delete all call relations of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM call_graph WHERE caller_file = ?", (file_path,))
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Data flow management
    # ============================================================================

    def add_data_flow_node(self, node: DataFlowNode) -> int:
        """Add a data flow node"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO data_flow (var_name, file_path, line, node_type, scope, value_source, use_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    node.var_name,
                    node.file_path,
                    node.line,
                    node.node_type,
                    node.scope,
                    node.value_source,
                    node.use_type,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def add_data_flow_nodes_batch(self, nodes: List[DataFlowNode]) -> int:
        """Batch add data flow nodes"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO data_flow (var_name, file_path, line, node_type, scope, value_source, use_type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        n.var_name,
                        n.file_path,
                        n.line,
                        n.node_type,
                        n.scope,
                        n.value_source,
                        n.use_type,
                    )
                    for n in nodes
                ],
            )
            if not self._batch_mode:
                conn.commit()
            return len(nodes)

    def get_def_sites(
        self, var_name: str, scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get the definition positions of a variable"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if scope:
                cursor.execute(
                    """
                    SELECT * FROM data_flow WHERE var_name = ? AND node_type = 'def' AND scope = ?
                    ORDER BY file_path, line
                """,
                    (var_name, scope),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM data_flow WHERE var_name = ? AND node_type = 'def'
                    ORDER BY file_path, line
                """,
                    (var_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_use_sites(
        self, var_name: str, scope: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get the use positions of a variable"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if scope:
                cursor.execute(
                    """
                    SELECT * FROM data_flow WHERE var_name = ? AND node_type = 'use' AND scope = ?
                    ORDER BY file_path, line
                """,
                    (var_name, scope),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM data_flow WHERE var_name = ? AND node_type = 'use'
                    ORDER BY file_path, line
                """,
                    (var_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_data_flow_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all data flow nodes of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM data_flow WHERE file_path = ? ORDER BY line",
                (file_path,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_data_flow_by_file(self, file_path: str) -> int:
        """Delete all data flow nodes of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM data_flow WHERE file_path = ?", (file_path,))
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Pointer state management
    # ============================================================================

    def add_pointer_state(self, state: PointerStateRecord) -> int:
        """Add a pointer state record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pointer_states (var_name, file_path, line, state, scope, allocator, deallocator)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    state.var_name,
                    state.file_path,
                    state.line,
                    state.state,
                    state.scope,
                    state.allocator,
                    state.deallocator,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def add_pointer_states_batch(self, states: List[PointerStateRecord]) -> int:
        """Batch add pointer state records"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(
                """
                INSERT INTO pointer_states (var_name, file_path, line, state, scope, allocator, deallocator)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                [
                    (
                        s.var_name,
                        s.file_path,
                        s.line,
                        s.state,
                        s.scope,
                        s.allocator,
                        s.deallocator,
                    )
                    for s in states
                ],
            )
            if not self._batch_mode:
                conn.commit()
            return len(states)

    def get_pointer_states(
        self, var_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get the state history of a pointer"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_path:
                cursor.execute(
                    """
                    SELECT * FROM pointer_states WHERE var_name = ? AND file_path = ?
                    ORDER BY line
                """,
                    (var_name, file_path),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM pointer_states WHERE var_name = ? ORDER BY file_path, line
                """,
                    (var_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def get_pointer_states_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all pointer states of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pointer_states WHERE file_path = ? ORDER BY line",
                (file_path,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_pointer_states_by_file(self, file_path: str) -> int:
        """Delete all pointer states of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pointer_states WHERE file_path = ?", (file_path,)
            )
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Type information management
    # ============================================================================

    def add_type_info(self, type_info: TypeInfo) -> int:
        """Add type information"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            members_json = json.dumps(type_info.members) if type_info.members else None
            cursor.execute(
                """
                INSERT INTO type_info (type_name, kind, file_path, line_start, line_end, definition, members)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    type_info.type_name,
                    type_info.kind,
                    type_info.file_path,
                    type_info.line_start,
                    type_info.line_end,
                    type_info.definition,
                    members_json,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def add_type_infos_batch(self, type_infos: List[TypeInfo]) -> int:
        """Batch add type information"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            data = [
                (
                    t.type_name,
                    t.kind,
                    t.file_path,
                    t.line_start,
                    t.line_end,
                    t.definition,
                    json.dumps(t.members) if t.members else None,
                )
                for t in type_infos
            ]
            cursor.executemany(
                """
                INSERT INTO type_info (type_name, kind, file_path, line_start, line_end, definition, members)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                data,
            )
            if not self._batch_mode:
                conn.commit()
            return len(type_infos)

    def get_type_info(self, type_name: str) -> Optional[Dict[str, Any]]:
        """Get type information"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM type_info WHERE type_name = ? LIMIT 1", (type_name,)
            )
            row = cursor.fetchone()
            if row:
                result = dict(row)
                if result["members"]:
                    result["members"] = json.loads(result["members"])
                return result
            return None

    def get_type_infos_by_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Get all type information of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM type_info WHERE file_path = ? ORDER BY line_start",
                (file_path,),
            )
            results = []
            for row in cursor.fetchall():
                result = dict(row)
                if result["members"]:
                    result["members"] = json.loads(result["members"])
                results.append(result)
            return results

    def delete_type_infos_by_file(self, file_path: str) -> int:
        """Delete all type information of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM type_info WHERE file_path = ?", (file_path,))
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Analysis cache management
    # ============================================================================

    def cache_analysis_result(
        self, file_path: str, analysis_type: str, result: Dict[str, Any]
    ) -> int:
        """Cache an analysis result"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            result_json = json.dumps(result)
            cursor.execute(
                """
                INSERT OR REPLACE INTO analysis_cache (file_path, analysis_type, result, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
                (file_path, analysis_type, result_json),
            )
            conn.commit()
            return cursor.lastrowid

    def get_cached_analysis(
        self, file_path: str, analysis_type: str
    ) -> Optional[Dict[str, Any]]:
        """Get a cached analysis result"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT result, updated_at FROM analysis_cache WHERE file_path = ? AND analysis_type = ?
            """,
                (file_path, analysis_type),
            )
            row = cursor.fetchone()
            if row:
                return {
                    "result": json.loads(row["result"]),
                    "updated_at": row["updated_at"],
                }
            return None

    def delete_cached_analysis(self, file_path: str) -> int:
        """Delete all cached analysis results of a file"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM analysis_cache WHERE file_path = ?", (file_path,)
            )
            conn.commit()
            return cursor.rowcount

    # ============================================================================
    # Statistics and queries
    # ============================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """Get the database statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            stats = {}

            # File statistics
            cursor.execute("SELECT COUNT(*) FROM files")
            stats["files_count"] = cursor.fetchone()[0]

            # Symbol statistics
            cursor.execute("SELECT COUNT(*) FROM symbols")
            stats["symbols_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT kind, COUNT(*) FROM symbols GROUP BY kind")
            stats["symbols_by_kind"] = {row[0]: row[1] for row in cursor.fetchall()}

            # Call relation statistics
            cursor.execute("SELECT COUNT(*) FROM call_graph")
            stats["call_relations_count"] = cursor.fetchone()[0]

            # Data flow statistics
            cursor.execute("SELECT COUNT(*) FROM data_flow")
            stats["data_flow_nodes_count"] = cursor.fetchone()[0]

            # Pointer state statistics
            cursor.execute("SELECT COUNT(*) FROM pointer_states")
            stats["pointer_states_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT state, COUNT(*) FROM pointer_states GROUP BY state")
            stats["pointer_states_by_state"] = {
                row[0]: row[1] for row in cursor.fetchall()
            }

            # Type information statistics
            cursor.execute("SELECT COUNT(*) FROM type_info")
            stats["type_infos_count"] = cursor.fetchone()[0]
            cursor.execute("SELECT kind, COUNT(*) FROM type_info GROUP BY kind")
            stats["type_infos_by_kind"] = {row[0]: row[1] for row in cursor.fetchall()}

            return stats

    def clear_all(self):
        """Clear all data in the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_cache")
            cursor.execute("DELETE FROM pointer_states")
            cursor.execute("DELETE FROM data_flow")
            cursor.execute("DELETE FROM call_graph")
            cursor.execute("DELETE FROM type_info")
            cursor.execute("DELETE FROM symbols")
            cursor.execute("DELETE FROM files")
            conn.commit()
            PrettyOutput.auto_print("[ProjectDatabase] database has been cleared")

    # ============================================================================
    # Incremental update mechanism
    # ============================================================================

    def update_file(
        self, file_path: str, language: str, collector: Optional[Any] = None
    ) -> bool:
        """
        Incrementally update the data of a single file

        Args:
            file_path: File path
            language: Language type (c, cpp, rust)
            collector: Data collector instance (optional; if not provided, one is created automatically)

        Returns:
            Whether the update succeeded
        """
        from .data_collector import DataCollector

        # Compute the new hash
        new_hash = compute_file_hash(file_path)

        # Check whether an update is needed
        if not self.file_hash_changed(file_path, new_hash):
            PrettyOutput.auto_print(
                f"[ProjectDatabase] file unchanged, skipping update: {file_path}"
            )
            return False

        # Delete the old data
        self.delete_file(file_path)

        # Create the data collector (if not provided)
        if collector is None:
            collector = DataCollector(self)

        # Collect the new data
        try:
            result = collector.analyze_file(file_path, language)

            # Add the file record
            file_info = create_file_info(file_path, language)
            self.add_file(file_info)

            # Batch insert the data
            if result["symbols"]:
                self.add_symbols_batch(result["symbols"])
            if result["call_relations"]:
                self.add_call_relations_batch(result["call_relations"])
            if result["data_flow_nodes"]:
                self.add_data_flow_nodes_batch(result["data_flow_nodes"])
            if result["pointer_states"]:
                self.add_pointer_states_batch(result["pointer_states"])
            if result["type_infos"]:
                self.add_type_infos_batch(result["type_infos"])

            PrettyOutput.auto_print(f"[ProjectDatabase] file updated successfully: {file_path}")
            return True

        except Exception as e:
            PrettyOutput.auto_print(
                f"[ProjectDatabase] file update failed: {file_path}, error: {e}"
            )
            return False

    def update_files_batch(self, file_paths: List[Tuple[str, str]]) -> Dict[str, bool]:
        """
        Batch incrementally update multiple files

        Args:
            file_paths: List of file paths, each element is (file_path, language)

        Returns:
            Update result dictionary {file_path: success}
        """
        from .data_collector import DataCollector

        # Create a shared data collector
        collector = DataCollector(self)

        results = {}
        for file_path, language in file_paths:
            results[file_path] = self.update_file(file_path, language, collector)

        return results

    def sync_files(self, current_files: List[Tuple[str, str]]) -> Dict[str, Any]:
        """
        Synchronize the file list: delete non-existent files and update changed files

        Args:
            current_files: Current file list, each element is (file_path, language)

        Returns:
            Synchronization result statistics
        """
        # Get all files in the database
        db_files = self.get_all_files()
        db_file_paths = {f["path"] for f in db_files}

        # Current file path set
        current_file_paths = {fp for fp, _ in current_files}

        # Files to delete (in the database but not currently present)
        deleted_files = db_file_paths - current_file_paths
        deleted_count = 0
        for file_path in deleted_files:
            self.delete_file(file_path)
            deleted_count += 1

        if deleted_count > 0:
            PrettyOutput.auto_print(
                f"[ProjectDatabase] deleted {deleted_count} non-existent files"
            )

        # Files to update
        update_results = self.update_files_batch(current_files)
        updated_count = sum(1 for success in update_results.values() if success)
        skipped_count = len(current_files) - updated_count

        PrettyOutput.auto_print(
            f"[ProjectDatabase] sync complete: updated {updated_count} files, skipped {skipped_count} files, deleted {deleted_count} files"
        )

        return {
            "deleted_count": deleted_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "total_files": len(current_files),
        }

    # ============================================================================
    # Cross-file analysis query interface
    # ============================================================================

    def find_symbol_definition(self, name: str) -> List[Dict[str, Any]]:
        """
        Find all definition positions of a symbol

        Args:
            name: Symbol name

        Returns:
            Symbol definition list
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM symbols 
                WHERE name = ? AND kind IN ('function', 'variable', 'type')
                ORDER BY file_path, line_start
                """,
                (name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_symbol_references(self, name: str) -> List[Dict[str, Any]]:
        """
        Find all reference positions of a symbol

        Args:
            name: Symbol name

        Returns:
            Symbol reference list (including definitions and uses)
        """
        results = []

        # Find the symbol definitions
        definitions = self.find_symbol_definition(name)
        results.extend(definitions)

        # Find the references in call relations
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # As a caller
            cursor.execute(
                """
                SELECT caller_name, caller_file, caller_line, 'caller' as ref_type
                FROM call_graph WHERE callee_name = ?
                """,
                (name,),
            )
            results.extend([dict(row) for row in cursor.fetchall()])

            # As a callee
            cursor.execute(
                """
                SELECT callee_name, callee_file, callee_line, 'callee' as ref_type
                FROM call_graph WHERE caller_name = ?
                """,
                (name,),
            )
            results.extend([dict(row) for row in cursor.fetchall()])

        return results

    def find_callers(self, function_name: str) -> List[Dict[str, Any]]:
        """
        Find all callers of a function (cross-file)

        Args:
            function_name: Function name

        Returns:
            Caller list
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT caller_name, caller_file, caller_line, call_type
                FROM call_graph 
                WHERE callee_name = ?
                ORDER BY caller_file, caller_line
                """,
                (function_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def find_callees(
        self, function_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find all functions called by a function (cross-file)

        Args:
            function_name: Function name
            file_path: File path (optional, used to distinguish functions with the same name)

        Returns:
            Callee function list
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_path:
                cursor.execute(
                    """
                    SELECT callee_name, callee_file, callee_line, call_type
                    FROM call_graph 
                    WHERE caller_name = ? AND caller_file = ?
                    ORDER BY caller_line
                    """,
                    (function_name, file_path),
                )
            else:
                cursor.execute(
                    """
                    SELECT callee_name, callee_file, callee_line, call_type
                    FROM call_graph 
                    WHERE caller_name = ?
                    ORDER BY caller_file, caller_line
                    """,
                    (function_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def trace_pointer_state(
        self, var_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Trace pointer state changes (cross-file)

        Args:
            var_name: Variable name
            file_path: File path (optional, used to restrict the scope)

        Returns:
            Pointer state change list
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_path:
                cursor.execute(
                    """
                    SELECT var_name, file_path, line, state, scope, allocator, deallocator
                    FROM pointer_states 
                    WHERE var_name = ? AND file_path = ?
                    ORDER BY line
                    """,
                    (var_name, file_path),
                )
            else:
                cursor.execute(
                    """
                    SELECT var_name, file_path, line, state, scope, allocator, deallocator
                    FROM pointer_states 
                    WHERE var_name = ?
                    ORDER BY file_path, line
                    """,
                    (var_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def find_data_flow(
        self, var_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Find the data flow of a variable (definition-use chain)

        Args:
            var_name: Variable name
            file_path: File path (optional, used to restrict the scope)

        Returns:
            Data flow node list
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if file_path:
                cursor.execute(
                    """
                    SELECT var_name, file_path, line, node_type, scope, value_source
                    FROM data_flow 
                    WHERE var_name = ? AND file_path = ?
                    ORDER BY line
                    """,
                    (var_name, file_path),
                )
            else:
                cursor.execute(
                    """
                    SELECT var_name, file_path, line, node_type, scope, value_source
                    FROM data_flow 
                    WHERE var_name = ?
                    ORDER BY file_path, line
                    """,
                    (var_name,),
                )
            return [dict(row) for row in cursor.fetchall()]

    def analyze_cross_file_uaf(self, var_name: str) -> Dict[str, Any]:
        """
        Cross-file UAF analysis

        Args:
            var_name: Variable name

        Returns:
            UAF analysis result
        """
        # Trace the pointer states
        states = self.trace_pointer_state(var_name)

        # Find the data flow
        data_flow = self.find_data_flow(var_name)

        # Analyze the UAF risk
        freed_locations = [s for s in states if s["state"] == "FREED"]
        use_locations = [df for df in data_flow if df["node_type"] == "use"]

        # Detect UAF: use after free
        uaf_risks = []
        for freed in freed_locations:
            for use in use_locations:
                # Simple heuristic: in the same file, the free line number < the use line number
                if (
                    freed["file_path"] == use["file_path"]
                    and freed["line"] < use["line"]
                ):
                    uaf_risks.append(
                        {
                            "var_name": var_name,
                            "freed_file": freed["file_path"],
                            "freed_line": freed["line"],
                            "use_file": use["file_path"],
                            "use_line": use["line"],
                            "risk_type": "use_after_free",
                        }
                    )

        return {
            "var_name": var_name,
            "states": states,
            "data_flow": data_flow,
            "uaf_risks": uaf_risks,
            "has_risk": len(uaf_risks) > 0,
        }

    def analyze_cross_file_data_flow(self, var_name: str) -> Dict[str, Any]:
        """
        Cross-file data flow analysis

        Args:
            var_name: Variable name

        Returns:
            Data flow analysis result
        """
        # Get the data flow nodes
        nodes = self.find_data_flow(var_name)

        # Group by file
        by_file = {}
        for node in nodes:
            file_path = node["file_path"]
            if file_path not in by_file:
                by_file[file_path] = []
            by_file[file_path].append(node)

        # Build the data flow graph
        flow_graph = []
        def_nodes = [n for n in nodes if n["node_type"] == "def"]
        use_nodes = [n for n in nodes if n["node_type"] == "use"]

        for def_node in def_nodes:
            for use_node in use_nodes:
                # Simple heuristic: within the same scope, the definition line number < the use line number
                if (
                    def_node["file_path"] == use_node["file_path"]
                    and def_node["scope"] == use_node["scope"]
                    and def_node["line"] < use_node["line"]
                ):
                    flow_graph.append(
                        {
                            "from": def_node,
                            "to": use_node,
                            "type": "def-use",
                        }
                    )

        return {
            "var_name": var_name,
            "nodes": nodes,
            "by_file": by_file,
            "flow_graph": flow_graph,
            "def_count": len(def_nodes),
            "use_count": len(use_nodes),
        }

    def close(self):
        """Close the database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None


# ============================================================================
# Helper functions
# ============================================================================


def compute_file_hash(file_path: str) -> str:
    """Compute the file content hash"""
    with open(file_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def create_file_info(file_path: str, language: str) -> FileInfo:
    """Create a file information object"""
    path_obj = Path(file_path)
    hash_value = compute_file_hash(file_path)
    last_modified = datetime.fromtimestamp(path_obj.stat().st_mtime)

    # Count the number of lines
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        line_count = sum(1 for _ in f)

    return FileInfo(
        path=str(path_obj.resolve()),
        hash=hash_value,
        last_modified=last_modified,
        language=language,
        line_count=line_count,
    )