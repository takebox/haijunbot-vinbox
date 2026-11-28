# -*- coding: utf-8 -*-
"""
Symbol dependency query tool

Purpose:
- Query symbol information (by name/file path)
- Query symbol dependencies (callers/callees)
- Query a file's symbol list
- Graph traversal (BFS/DFS)

Arguments:
- action (str): Operation: find_symbol looks up a symbol definition/reference location by name, get_file_symbols lists all symbols in a file, find_references finds who references the symbol, find_dependencies finds module/symbol dependencies, traverse traverses the dependency graph. Supports:
  - "find_symbol": Find a symbol
  - "get_file_symbols": Get a file's symbol list
  - "find_references": Find symbol references
  - "find_dependencies": Find symbol dependencies
  - "traverse": Graph traversal
- project_path (str): Project root directory path
- symbol_name (str): Symbol name (needed by find_symbol/find_references/find_dependencies)
- file_path (str): File path (needed by find_symbol/get_file_symbols)
- kind (str): Symbol type filter (optional)
- direction (str): Traversal direction, "forward"/"backward" (needed by traverse)
- max_depth (int): Maximum traversal depth (needed by traverse, default 10)

Returns:
- success (bool)
- stdout (str): JSON text containing the query results
- stderr (str)
"""

import json
import os
from typing import Any, Dict, List, Optional

from haijunbot.haijunbot_code_agent.code_analyzer.symbol_table_db import SymbolTableDB
from haijunbot.haijunbot_code_agent.code_analyzer.db.data_types import Node


class SymbolDependencyTool:
    """Symbol dependency query tool"""

    # The file name must match the tool name so the registry can auto-load it
    name = "symbol_dependency"
    description = "Query the definitions and references of code symbols (functions/classes/variables): look up by name, find references, find dependencies, list file symbols, or draw a dependency graph; used to locate call chains and perform impact analysis."

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "Operation: find_symbol looks up a symbol definition/reference location by name, get_file_symbols lists all symbols in a file, find_references finds who references the symbol, find_dependencies finds module/symbol dependencies, traverse traverses the dependency graph",
                "enum": [
                    "find_symbol",
                    "get_file_symbols",
                    "find_references",
                    "find_dependencies",
                    "traverse",
                ],
            },
            "project_path": {"type": "string", "description": "Project root directory path"},
            "symbol_name": {
                "type": "string",
                "description": "Symbol name (needed by find_symbol/find_references/find_dependencies)",
            },
            "file_path": {
                "type": "string",
                "description": "File path (needed by find_symbol/get_file_symbols)",
            },
            "kind": {
                "type": "string",
                "description": "Symbol type filter (optional)",
                "enum": [
                    "function",
                    "class",
                    "method",
                    "variable",
                    "constant",
                    "module",
                    "interface",
                    "type",
                    "enum",
                    "struct",
                    "trait",
                    "impl",
                    "namespace",
                    "import",
                ],
            },
            "direction": {
                "type": "string",
                "description": "Traversal direction (needed by traverse)",
                "enum": ["forward", "backward"],
            },
            "max_depth": {
                "type": "integer",
                "description": "Maximum traversal depth (needed by traverse, default 10)",
                "default": 10,
            },
        },
        "required": ["action", "project_path"],
    }

    def __init__(self):
        self._db_cache: Dict[str, SymbolTableDB] = {}

    def _get_db(self, project_path: str) -> SymbolTableDB:
        """Get or create a SymbolTableDB instance"""
        project_path = os.path.abspath(project_path)
        if project_path not in self._db_cache:
            cache_dir = os.path.join(project_path, ".haijunbot", "symbol_cache")
            os.makedirs(cache_dir, exist_ok=True)
            self._db_cache[project_path] = SymbolTableDB(cache_dir)
        return self._db_cache[project_path]

    def _node_to_dict(self, node: Node) -> Dict[str, Any]:
        """Convert a Node object to a dictionary"""
        return {
            "id": node.id,
            "name": node.name,
            "qualified_name": node.qualified_name,
            "kind": node.kind.value if hasattr(node.kind, "value") else str(node.kind),
            "file_path": node.file_path,
            "language": node.language,
            "start_line": node.start_line,
            "end_line": node.end_line,
            "start_column": node.start_column,
            "end_column": node.end_column,
            "signature": node.signature,
            "docstring": node.docstring,
            "parent_id": node.parent_id,
            "visibility": node.visibility,
            "is_exported": node.is_exported,
            "is_async": node.is_async,
            "is_static": node.is_static,
        }

    def _find_symbol(
        self,
        db: SymbolTableDB,
        symbol_name: str,
        file_path: Optional[str] = None,
        kind: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Find a symbol"""
        results = []

        # Use the find_symbol method; the second argument is file_path
        nodes = db.find_symbol(symbol_name, file_path)

        for node in nodes:
            # Filter by kind
            if (
                kind is None
                or (hasattr(node.kind, "value") and node.kind.value == kind)
                or str(node.kind) == kind
            ):
                results.append(self._node_to_dict(node))

        return results

    def _get_file_symbols(
        self, db: SymbolTableDB, file_path: str, kind: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get a file's symbol list"""
        symbols = db.get_file_symbols(file_path)
        results = []

        for sym in symbols:
            if (
                kind is None
                or (hasattr(sym.kind, "value") and sym.kind.value == kind)
                or str(sym.kind) == kind
            ):
                results.append(self._node_to_dict(sym))

        return results

    def _find_references(
        self, db: SymbolTableDB, symbol_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find symbol references"""
        # First find the symbol
        symbols = self._find_symbol(db, symbol_name, file_path)
        if not symbols:
            return []

        results = []
        for sym_info in symbols:
            node_id = sym_info["id"]
            # Find the edges referencing this symbol (incoming edges)
            edges = db.queries.get_incoming_edges(node_id)
            for edge in edges:
                # Get the details of the referrer
                ref_node = db.queries.get_node_by_id(edge.source)
                if ref_node:
                    results.append(
                        {
                            "reference": self._node_to_dict(ref_node),
                            "edge_kind": edge.kind.value
                            if hasattr(edge.kind, "value")
                            else str(edge.kind),
                            "symbol": sym_info,
                        }
                    )

        return results

    def _find_dependencies(
        self, db: SymbolTableDB, symbol_name: str, file_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find symbol dependencies"""
        # First find the symbol
        symbols = self._find_symbol(db, symbol_name, file_path)
        if not symbols:
            return []

        results = []
        for sym_info in symbols:
            node_id = sym_info["id"]
            # Find the edges this symbol depends on (outgoing edges)
            edges = db.queries.get_outgoing_edges(node_id)
            for edge in edges:
                # Get the details of the dependency
                dep_node = db.queries.get_node_by_id(edge.target)
                if dep_node:
                    results.append(
                        {
                            "dependency": self._node_to_dict(dep_node),
                            "edge_kind": edge.kind.value
                            if hasattr(edge.kind, "value")
                            else str(edge.kind),
                            "symbol": sym_info,
                        }
                    )

        return results

    def _traverse(
        self,
        db: SymbolTableDB,
        symbol_name: str,
        file_path: Optional[str] = None,
        direction: str = "forward",
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """Graph traversal"""
        # First find the symbol
        symbols = self._find_symbol(db, symbol_name, file_path)
        if not symbols:
            return {"nodes": [], "edges": []}

        traverser = db.get_traverser()
        start_node_id = symbols[0]["id"]

        # direction: forward=forward traversal(outgoing), backward=reverse traversal(incoming)
        traverse_direction = "outgoing" if direction == "forward" else "incoming"
        subgraph = traverser.traverse_bfs(
            start_node_id, max_depth=max_depth, direction=traverse_direction
        )

        # Convert the result
        nodes = [self._node_to_dict(node) for node in subgraph.nodes]
        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "kind": edge.kind.value
                if hasattr(edge.kind, "value")
                else str(edge.kind),
            }
            for edge in subgraph.edges
        ]

        return {"nodes": nodes, "edges": edges}

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool"""
        try:
            action = args.get("action")
            project_path = args.get("project_path")

            if not action:
                return {"success": False, "stdout": "", "stderr": "Missing action argument"}

            if not project_path:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "Missing project_path argument",
                }

            if not os.path.isdir(project_path):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Project path does not exist: {project_path}",
                }

            db = self._get_db(project_path)

            symbol_name = args.get("symbol_name")
            file_path = args.get("file_path")
            kind = args.get("kind")

            if action == "find_symbol":
                if not symbol_name and not file_path:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "find_symbol needs the symbol_name or file_path argument",
                    }
                results = self._find_symbol(db, symbol_name or "", file_path, kind)
                return {
                    "success": True,
                    "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            elif action == "get_file_symbols":
                if not file_path:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "get_file_symbols needs the file_path argument",
                    }
                results = self._get_file_symbols(db, file_path, kind)
                return {
                    "success": True,
                    "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            elif action == "find_references":
                if not symbol_name:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "find_references needs the symbol_name argument",
                    }
                results = self._find_references(db, symbol_name, file_path)
                return {
                    "success": True,
                    "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            elif action == "find_dependencies":
                if not symbol_name:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "find_dependencies needs the symbol_name argument",
                    }
                results = self._find_dependencies(db, symbol_name, file_path)
                return {
                    "success": True,
                    "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            elif action == "traverse":
                if not symbol_name:
                    return {
                        "success": False,
                        "stdout": "",
                        "stderr": "traverse needs the symbol_name argument",
                    }
                direction = args.get("direction", "forward")
                max_depth = args.get("max_depth", 10)
                results = self._traverse(
                    db, symbol_name, file_path, direction, max_depth
                )
                return {
                    "success": True,
                    "stdout": json.dumps(results, ensure_ascii=False, indent=2),
                    "stderr": "",
                }

            else:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Unsupported operation: {action}",
                }

        except Exception as e:
            return {"success": False, "stdout": "", "stderr": f"Tool execution failed: {str(e)}"}
