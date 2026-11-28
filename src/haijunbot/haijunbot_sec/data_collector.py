# -*- coding: utf-8 -*-
"""
Data collector - extracts project-level analysis data based on tree-sitter

Core features:
1. Symbol extraction (functions, variables, type definitions)
2. Call relationship extraction (function calls, argument passing)
3. Data flow extraction (variable definition, usage, argument passing)
4. Pointer state extraction (malloc, free, NULL assignment)
5. Type information extraction (struct, union, enum, typedef)

Output persists to ProjectDatabase
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from haijunbot.haijunbot_utils.output import PrettyOutput

# tree-sitter dependency
try:
    import tree_sitter_c as tsc
    import tree_sitter_cpp as tscpp
    from tree_sitter import Language, Parser, Node

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    Node = None  # type fallback  # ty: ignore[invalid-assignment]

# Rust parser
try:
    import tree_sitter_rust as tsrust

    TREE_SITTER_RUST_AVAILABLE = True
except ImportError:
    TREE_SITTER_RUST_AVAILABLE = False

from .project_database import (
    ProjectDatabase,
    SymbolInfo,
    CallRelation,
    DataFlowNode,
    PointerStateRecord,
    TypeInfo,
    create_file_info,
)


# ============================================================================
# Data collector
# ============================================================================


class DataCollector:
    """Data collector - extracts analysis data based on tree-sitter"""

    def __init__(self, database: ProjectDatabase):
        """
        Initialize the data collector

        Args:
            database: project database instance
        """
        self.database = database

        if not TREE_SITTER_AVAILABLE:
            PrettyOutput.auto_print(
                "[DataCollector] tree-sitter unavailable, falling back to regex-based extraction"
            )
            self.c_parser = None
            self.cpp_parser = None
            self.rust_parser = None
            return

        # Initialize the C and C++ parsers
        try:
            self.c_language = Language(tsc.language())
            self.c_parser = Parser(self.c_language)
        except Exception as e:
            PrettyOutput.auto_print(f"[DataCollector] C parser initialization failed: {e}")
            self.c_parser = None

        try:
            self.cpp_language = Language(tscpp.language())
            self.cpp_parser = Parser(self.cpp_language)
        except Exception as e:
            PrettyOutput.auto_print(f"[DataCollector] C++ parser initialization failed: {e}")
            self.cpp_parser = None

        # Initialize the Rust parser
        if TREE_SITTER_RUST_AVAILABLE:
            try:
                self.rust_language = Language(tsrust.language())
                self.rust_parser = Parser(self.rust_language)
            except Exception as e:
                PrettyOutput.auto_print(f"[DataCollector] Rust parser initialization failed: {e}")
                self.rust_parser = None
        else:
            self.rust_parser = None

    # ============================================================================
    # File analysis entry
    # ============================================================================

    def analyze_file(self, file_path: str, language: str) -> Dict[str, Any]:
        """
        Analyze a single file and extract all data

        Args:
            file_path: file path
            language: language type (c, cpp, rust)

        Returns:
            analysis result dictionary
        """
        result = {
            "symbols": [],
            "call_relations": [],
            "data_flow_nodes": [],
            "pointer_states": [],
            "type_infos": [],
        }

        # Check whether the file exists
        if not Path(file_path).exists():
            PrettyOutput.auto_print(f"[DataCollector] File not found: {file_path}")
            return result

        # Read the file content
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
        except Exception as e:
            PrettyOutput.auto_print(f"[DataCollector] Failed to read file: {e}")
            return result

        # Create file info
        file_info = create_file_info(file_path, language)
        self.database.add_file(file_info)

        # Select the parser based on the language
        if language == "rust":
            return self._analyze_rust_file(file_path, code, result)

        # Use tree-sitter to parse C/C++
        if TREE_SITTER_AVAILABLE and (self.c_parser or self.cpp_parser):
            parser = self.cpp_parser if language in ["cpp", "c++"] else self.c_parser
            if parser:
                try:
                    tree = parser.parse(bytes(code, "utf8"))
                    self._extract_from_ast(tree.root_node, code, file_path, result)
                except Exception as e:
                    PrettyOutput.auto_print(f"[DataCollector] AST parsing failed: {e}")
                    # Fall back to regex extraction
                    self._extract_with_regex(code, file_path, result)
            else:
                # Parser unavailable, use regex extraction
                self._extract_with_regex(code, file_path, result)
        else:
            # tree-sitter unavailable, use regex extraction
            self._extract_with_regex(code, file_path, result)

        # Save to the database
        self._save_to_database(file_path, result)

        return result

    def analyze_files_batch(
        self, file_paths: List[str], language: str
    ) -> Dict[str, Any]:
        """
        Analyze files in batch

        Args:
            file_paths: list of file paths
            language: language type

        Returns:
            overall analysis result
        """
        total_result = {
            "total_files": len(file_paths),
            "total_symbols": 0,
            "total_call_relations": 0,
            "total_data_flow_nodes": 0,
            "total_pointer_states": 0,
            "total_type_infos": 0,
            "failed_files": [],
        }

        for file_path in file_paths:
            try:
                result = self.analyze_file(file_path, language)
                total_result["total_symbols"] += len(result["symbols"])
                total_result["total_call_relations"] += len(result["call_relations"])
                total_result["total_data_flow_nodes"] += len(result["data_flow_nodes"])
                total_result["total_pointer_states"] += len(result["pointer_states"])
                total_result["total_type_infos"] += len(result["type_infos"])
            except Exception as e:
                total_result["failed_files"].append(
                    {"file": file_path, "error": str(e)}
                )

        PrettyOutput.auto_print(
            f"[DataCollector] Batch analysis completed: {total_result['total_files']} files, "
            f"{total_result['total_symbols']} symbols, "
            f"{total_result['total_call_relations']} call relations"
        )

        return total_result

    # ============================================================================
    # Rust AST extraction methods
    # ============================================================================

    def _analyze_rust_file(
        self, file_path: str, code: str, result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze a Rust file

        Args:
            file_path: file path
            code: source code
            result: result dictionary

        Returns:
            analysis result dictionary
        """
        if not self.rust_parser:
            PrettyOutput.auto_print("[DataCollector] Rust parser unavailable")
            return result

        try:
            tree = self.rust_parser.parse(bytes(code, "utf8"))
            self._extract_rust_from_ast(tree.root_node, code, file_path, result)
        except Exception as e:
            PrettyOutput.auto_print(f"[DataCollector] Rust AST parsing failed: {e}")

        # Save to the database
        self._save_to_database(file_path, result)

        return result

    def _extract_rust_from_ast(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Extract data from the Rust AST

        Args:
            node: AST root node
            code: source code
            file_path: file path
            result: result dictionary
        """
        if node is None:
            return

        self._traverse_rust_ast(node, code, file_path, result)

    def _traverse_rust_ast(
        self,
        node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str = "global",
    ):
        """
        Recursively traverse the Rust AST

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        if node is None or node.type is None:
            return

        node_type = node.type

        # Handle function definitions
        if node_type == "function_item":
            self._handle_rust_function_definition(node, code, file_path, result)
            # Enter the function scope
            func_name = self._get_rust_function_name(node, code)
            new_scope = func_name if func_name else scope
            # Note: the body is not traversed separately; it is handled uniformly by the final for child loop
            # But new_scope must be passed to child nodes
            for child in node.children:
                self._traverse_rust_ast(child, code, file_path, result, new_scope)
            return  # children already recursed, skip the final for child loop

        # Handle struct definitions
        elif node_type == "struct_item":
            self._handle_rust_struct_definition(node, code, file_path, result)

        # Handle enum definitions
        elif node_type == "enum_item":
            self._handle_rust_enum_definition(node, code, file_path, result)

        # Handle impl blocks
        elif node_type == "impl_item":
            self._handle_rust_impl_block(node, code, file_path, result)

        # Handle extern blocks
        elif node_type == "extern_mod":
            self._handle_rust_extern_block(node, code, file_path, result)

        # Handle unsafe blocks
        elif node_type == "unsafe_block":
            self._handle_rust_unsafe_block(node, code, file_path, result, scope)

        # Handle let declarations (variable bindings)
        elif node_type == "let_declaration":
            self._handle_rust_let_declaration(node, code, file_path, result, scope)

        # Handle function calls
        elif node_type == "call_expression":
            self._handle_rust_call_expression(node, code, file_path, result, scope)

        # Handle method calls
        elif node_type == "method_call_expression":
            self._handle_rust_method_call(node, code, file_path, result, scope)

        # Handle macro invocations
        elif node_type == "macro_invocation":
            self._handle_rust_macro_invocation(node, code, file_path, result, scope)

        # Recursively process child nodes
        for child in node.children:
            self._traverse_rust_ast(child, code, file_path, result, scope)

    # ============================================================================
    # AST extraction methods
    # ============================================================================

    def _extract_from_ast(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Extract data from the AST

        Args:
            node: AST root node
            code: source code
            file_path: file path
            result: result dictionary
        """
        if node is None:
            return

        self._traverse_ast(node, code, file_path, result)

    def _traverse_ast(
        self,
        node: Node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str = "global",
    ):
        """
        Recursively traverse the AST

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        if node is None or node.type is None:
            return

        node_type = node.type

        # Handle function definitions
        if node_type == "function_definition":
            self._handle_function_definition(node, code, file_path, result)
            # Enter the function scope
            func_name = self._get_function_name(node, code)
            new_scope = func_name if func_name else scope
            # Traverse the function body
            body_node = node.child_by_field_name("body")
            if body_node:
                self._traverse_ast(body_node, code, file_path, result, new_scope)

        # Handle type definitions
        elif node_type in [
            "struct_specifier",
            "union_specifier",
            "enum_specifier",
            "type_definition",
        ]:
            self._handle_type_definition(node, code, file_path, result)

        # Handle variable declarations
        elif node_type == "declaration":
            self._handle_declaration(node, code, file_path, result, scope)

        # Handle function calls
        elif node_type == "call_expression":
            self._handle_call_expression(node, code, file_path, result, scope)

        # Handle assignment expressions
        elif node_type == "assignment_expression":
            self._handle_assignment(node, code, file_path, result, scope)

        # Handle pointer-related operations
        elif node_type in ["malloc_call", "calloc_call", "realloc_call", "free_call"]:
            self._handle_memory_operation(node, code, file_path, result, scope)

        # Handle if statements (extract variable usage in conditions)
        elif node_type == "if_statement":
            self._handle_if_statement(node, code, file_path, result, scope)

        # Handle while/for loops (extract variable usage in conditions)
        elif node_type in ["while_statement", "for_statement"]:
            self._handle_loop_statement(node, code, file_path, result, scope)

        # Handle return statements (detect ownership transfer)
        elif node_type == "return_statement":
            self._handle_return_statement(node, code, file_path, result, scope)

        # Recursively process child nodes
        for child in node.children:
            self._traverse_ast(child, code, file_path, result, scope)

    def _handle_function_definition(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a function definition

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
        """
        # Get the function name
        func_name = self._get_function_name(node, code)
        if not func_name:
            return

        # Get the function signature
        signature = self._get_node_text(node, code)

        # Get the line number range
        line_start = node.start_point[0] + 1  # tree-sitter line numbers start at 0
        line_end = node.end_point[0] + 1

        # Extract parameters
        params = self._extract_function_params(node, code)

        # Create symbol info
        symbol = SymbolInfo(
            name=func_name,
            kind="function",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            signature=signature,
            scope="global",
            is_external=False,
        )
        result["symbols"].append(symbol)

        # Create data flow nodes for parameters
        for param in params:
            param_node = DataFlowNode(
                var_name=param,
                file_path=file_path,
                line=line_start,
                node_type="param_in",
                scope=func_name,
                value_source="parameter",
            )
            result["data_flow_nodes"].append(param_node)

    def _handle_type_definition(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a type definition

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
        """
        type_name = None
        kind: str = ""
        members = []

        if node.type == "struct_specifier":
            kind = "struct"
            # Get the struct name
            name_node = node.child_by_field_name("name")
            if name_node:
                type_name = self._get_node_text(name_node, code)
        elif node.type == "union_specifier":
            kind = "union"
            name_node = node.child_by_field_name("name")
            if name_node:
                type_name = self._get_node_text(name_node, code)
        elif node.type == "enum_specifier":
            kind = "enum"
            name_node = node.child_by_field_name("name")
            if name_node:
                type_name = self._get_node_text(name_node, code)
        elif node.type == "type_definition":
            kind = "typedef"
            # The typedef alias is in the last identifier
            identifiers = [
                child for child in node.children if child.type == "type_identifier"
            ]
            if identifiers:
                type_name = self._get_node_text(identifiers[-1], code)

        if not type_name:
            return

        # Extract members (for struct/union)
        if kind in ["struct", "union"]:
            body_node = node.child_by_field_name("body")
            if body_node:
                members = self._extract_struct_members(body_node, code)

        # Get the definition text
        definition = self._get_node_text(node, code)
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        type_info = TypeInfo(
            type_name=type_name,
            kind=kind,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            definition=definition,
            members=members,
        )
        result["type_infos"].append(type_info)

    def _handle_declaration(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a variable declaration

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Extract variable name and type
        decls = self._extract_declarators(node, code)
        for var_name, type_name in decls:
            line = node.start_point[0] + 1

            # Create symbol info
            symbol = SymbolInfo(
                name=var_name,
                kind="variable",
                file_path=file_path,
                line_start=line,
                line_end=line,
                type_name=type_name,
                scope=scope,
                is_external=False,
            )
            result["symbols"].append(symbol)

            # Create data flow node (definition)
            data_flow_node = DataFlowNode(
                var_name=var_name,
                file_path=file_path,
                line=line,
                node_type="def",
                scope=scope,
                value_source="declaration",
            )
            result["data_flow_nodes"].append(data_flow_node)

        # Check whether the declaration contains a memory allocation call (e.g. char *p = malloc(100))
        self._check_init_declarator_for_allocation(node, code, file_path, result, scope)

        # Check whether this is a C++ stream object constructor declaration (e.g. std::ifstream ifs(path))
        # This needs to be recognized as a call relation
        type_node = node.child_by_field_name("type")
        if type_node:
            type_text = self._get_node_text(type_node, code)
            # Check whether it is std::ifstream/std::ofstream/std::fstream
            if type_text in [
                "std::ifstream",
                "std::ofstream",
                "std::fstream",
                "ifstream",
                "ofstream",
                "fstream",
            ]:
                # Get the variable name and arguments
                declarator_node = node.child_by_field_name("declarator")
                if declarator_node:
                    # Get the variable name
                    var_name = None
                    for child in declarator_node.children:
                        if child.type == "identifier":
                            var_name = self._get_node_text(child, code)
                            break

                    if var_name:
                        line = node.start_point[0] + 1
                        # Create a call relation (treat constructor declarations as calls)
                        call_relation = CallRelation(
                            caller_name=scope if scope != "global" else "unknown",
                            caller_file=file_path,
                            caller_line=line,
                            callee_name=type_text.split("::")[-1]
                            if "::" in type_text
                            else type_text,  # extract the base name
                            callee_file=None,
                            callee_line=None,
                            call_type="constructor",
                        )
                        result["call_relations"].append(call_relation)

    def _handle_call_expression(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a function call

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Get the callee function name
        callee_name = self._get_call_target(node, code)
        if not callee_name:
            return

        line = node.start_point[0] + 1

        # Create a call relation
        call_relation = CallRelation(
            caller_name=scope if scope != "global" else "unknown",
            caller_file=file_path,
            caller_line=line,
            callee_name=callee_name,
            callee_file=None,  # external function, file unknown
            callee_line=None,
            call_type="direct",
        )
        result["call_relations"].append(call_relation)

        # Handle free calls
        if callee_name == "free":
            args_node = node.child_by_field_name("arguments")
            if args_node:
                # Get the free() argument (variable name)
                for child in args_node.children:
                    if (
                        child.type == "identifier"
                        or child.type == "expression_statement"
                    ):
                        var_name = self._get_node_text(child, code)
                        pointer_state = PointerStateRecord(
                            var_name=var_name,
                            file_path=file_path,
                            line=line,
                            state="FREED",
                            scope=scope,
                            allocator=None,
                            deallocator="free",
                        )
                        result["pointer_states"].append(pointer_state)
                        break

        # Extract variable usage from arguments
        args_node = node.child_by_field_name("arguments")
        if args_node:
            self._extract_call_arguments(
                args_node, code, file_path, result, scope, line
            )

    def _handle_assignment(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle an assignment expression

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Get the left-hand side variable name
        left_node = node.child_by_field_name("left")
        if not left_node:
            return

        var_name = self._get_node_text(left_node, code)
        line = node.start_point[0] + 1

        # Check whether it is a memory allocation
        right_node = node.child_by_field_name("right")
        if right_node and right_node.type == "call_expression":
            call_name = self._get_call_target(right_node, code)
            if call_name in ["malloc", "calloc", "realloc"]:
                # Create a pointer state record
                pointer_state = PointerStateRecord(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    state="ALLOCATED",
                    scope=scope,
                    allocator=call_name,
                    deallocator=None,
                )
                result["pointer_states"].append(pointer_state)

                # Create a data flow node (definition)
                data_flow_node = DataFlowNode(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    node_type="def",
                    scope=scope,
                    value_source=call_name,
                )
                result["data_flow_nodes"].append(data_flow_node)
            else:
                # Normal assignment, create a data flow node (definition)
                data_flow_node = DataFlowNode(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    node_type="def",
                    scope=scope,
                    value_source="assignment",
                )
                result["data_flow_nodes"].append(data_flow_node)

        # Check whether it is a NULL assignment
        right_text = self._get_node_text(right_node, code) if right_node else ""
        if right_text in ["NULL", "nullptr", "0"]:
            pointer_state = PointerStateRecord(
                var_name=var_name,
                file_path=file_path,
                line=line,
                state="NULLIFIED",
                scope=scope,
                allocator=None,
                deallocator=None,
            )
            result["pointer_states"].append(pointer_state)

    def _handle_memory_operation(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle memory operations (malloc, free, etc.)

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # This method mainly handles standalone memory operation calls
        # Actual malloc/free calls are usually handled in assignment expressions
        pass

    def _handle_if_statement(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle an if statement, extract variable usage in the condition, and record protected calls in the consequence block

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Get the condition expression (parenthesized_expression)
        condition_node = node.child_by_field_name("condition")
        if not condition_node:
            return

        line = node.start_point[0] + 1

        # Recursively extract all identifiers from the condition
        self._extract_identifiers_from_condition(
            condition_node, code, file_path, result, scope, line
        )

        # Extract calls in the consequence block, marked as condition_protected
        consequence_node = node.child_by_field_name("consequence")
        if consequence_node:
            self._extract_protected_calls(
                consequence_node, code, file_path, result, scope
            )

    def _handle_loop_statement(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle while/for loops, extract variable usage in the condition, and record protected calls in the body block

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Get the condition expression
        condition_node = node.child_by_field_name("condition")
        if not condition_node:
            return

        line = node.start_point[0] + 1

        # Recursively extract all identifiers from the condition
        self._extract_identifiers_from_condition(
            condition_node, code, file_path, result, scope, line
        )

        # Extract calls in the body block, marked as condition_protected
        body_node = node.child_by_field_name("body")
        if body_node:
            self._extract_protected_calls(body_node, code, file_path, result, scope)

    def _handle_return_statement(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a return statement and detect ownership transfer

        Detected patterns:
        - return malloc_ptr;  // function returns allocated memory, ownership transfers to the caller
        - return ptr;         // returns a pointer variable

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        line = node.start_point[0] + 1

        # Find identifiers in the return statement
        for child in node.children:
            if child.type == "identifier":
                var_name = self._get_node_text(child, code)
                # Create a data flow node of type ownership_transfer
                data_flow_node = DataFlowNode(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    node_type="use",
                    scope=scope,
                    value_source="return",
                    use_type="ownership_transfer",
                )
                result["data_flow_nodes"].append(data_flow_node)
            elif child.type == "call_expression":
                # return malloc(...); returns the allocation result directly
                call_name = self._get_call_target(child, code)
                if call_name in ["malloc", "calloc", "realloc"]:
                    # Returns the allocation result, ownership transferred
                    data_flow_node = DataFlowNode(
                        var_name=f"__return_{call_name}",
                        file_path=file_path,
                        line=line,
                        node_type="use",
                        scope=scope,
                        value_source="return",
                        use_type="ownership_transfer",
                    )
                    result["data_flow_nodes"].append(data_flow_node)

    def _extract_identifiers_from_condition(
        self,
        node: Node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str,
        line: int,
    ):
        """
        Recursively extract all identifiers (variable usage) from the condition expression and detect NULL check patterns

        Detected NULL check patterns:
        - if (ptr != NULL) / if (ptr != nullptr)
        - if (ptr == NULL) / if (ptr == nullptr)
        - if (ptr) / if (!ptr)
        - if (ptr != NULL && ...) / if (ptr == NULL || ...)

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
            line: line number
        """
        if node is None:
            return

        # Detect NULL check patterns: detect ptr == NULL / ptr != NULL in binary expressions
        if node.type == "binary_expression":
            self._detect_null_check_in_binary(
                node, code, file_path, result, scope, line
            )
        # Detect the unary negation pattern: !ptr
        elif node.type == "unary_expression":
            op_node = node.child_by_field_name("operator")
            if op_node and self._get_node_text(op_node, code) == "!":
                arg_node = node.child_by_field_name("argument")
                if arg_node and arg_node.type == "identifier":
                    var_name = self._get_node_text(arg_node, code)
                    self._add_null_check_node(var_name, file_path, line, scope, result)
        # Detect a standalone identifier as the condition: if (ptr)
        # Note: an identifier is only a NULL check when it directly forms the entire condition
        # For example, if (ptr) is a NULL check, but idx in if (idx >= 0) is not
        elif node.type == "identifier":
            var_name = self._get_node_text(node, code)
            # Exclude common non-variable identifiers
            if var_name not in [
                "NULL",
                "nullptr",
                "true",
                "false",
                "size_t",
                "int",
                "char",
                "void",
                "long",
                "short",
                "float",
                "double",
                "unsigned",
                "signed",
            ]:
                # Check the parent node type to determine whether it is a real NULL check
                # Only when the identifier directly forms the condition (a direct child of parenthesized_expression or condition_clause)
                # is it a NULL check
                parent = node.parent
                if parent and parent.type in [
                    "parenthesized_expression",
                    "condition_clause",
                ]:
                    # Check whether the grandparent node is an if/while condition
                    grandparent = parent.parent
                    if grandparent and grandparent.type in [
                        "if_statement",
                        "while_statement",
                    ]:
                        # The identifier directly forms the condition, so it is a NULL check
                        data_flow_node = DataFlowNode(
                            var_name=var_name,
                            file_path=file_path,
                            line=line,
                            node_type="use",
                            scope=scope,
                            value_source="condition",
                            use_type="null_check",
                        )
                        result["data_flow_nodes"].append(data_flow_node)
                # Other cases (e.g. idx in idx >= 0) are not marked as null_check
                # to avoid false positives
            return

        # Recursively process child nodes
        for child in node.children:
            self._extract_identifiers_from_condition(
                child, code, file_path, result, scope, line
            )

    def _detect_null_check_in_binary(
        self,
        node: Node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str,
        line: int,
    ):
        """Detect NULL check and value check patterns in binary expressions

        NULL check: ptr == NULL, ptr != NULL
        Value check: fd >= 0, fd > -1, fd != -1, fd < 0, etc.
        """
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        op_node = node.child_by_field_name("operator")

        if not left or not right or not op_node:
            return

        op = self._get_node_text(op_node, code)
        left_text = self._get_node_text(left, code).strip()
        right_text = self._get_node_text(right, code).strip()

        # Detect ptr == NULL / ptr != NULL
        null_literals = {"NULL", "nullptr", "0"}
        if op in ("==", "!="):
            if right_text in null_literals and left.type == "identifier":
                var_name = left_text
                self._add_null_check_node(var_name, file_path, line, scope, result)
            elif left_text in null_literals and right.type == "identifier":
                var_name = right_text
                self._add_null_check_node(var_name, file_path, line, scope, result)

        # Detect value checks: var >= 0, var > -1, var != -1, var < 0, etc.
        # These are validity checks on IO return values / error codes
        value_check_ops = {">=", "<=", "!=", "==", "<", ">"}
        value_check_constants = {"0", "-1", "1", "EOF"}
        if op in value_check_ops:
            if right_text in value_check_constants and left.type == "identifier":
                var_name = left_text
                self._add_value_check_node(var_name, file_path, line, scope, result)
            elif left_text in value_check_constants and right.type == "identifier":
                var_name = right_text
                self._add_value_check_node(var_name, file_path, line, scope, result)

    def _add_null_check_node(
        self,
        var_name: str,
        file_path: str,
        line: int,
        scope: str,
        result: Dict[str, Any],
    ):
        """Add a data flow node of type null_check"""
        data_flow_node = DataFlowNode(
            var_name=var_name,
            file_path=file_path,
            line=line,
            node_type="use",
            scope=scope,
            value_source="condition",
            use_type="null_check",
        )
        result["data_flow_nodes"].append(data_flow_node)

    def _add_value_check_node(
        self,
        var_name: str,
        file_path: str,
        line: int,
        scope: str,
        result: Dict[str, Any],
    ):
        """Add a data flow node of type value_check (e.g. fd >= 0, fd != -1, etc.)"""
        data_flow_node = DataFlowNode(
            var_name=var_name,
            file_path=file_path,
            line=line,
            node_type="use",
            scope=scope,
            value_source="condition",
            use_type="value_check",
        )
        result["data_flow_nodes"].append(data_flow_node)

    def _extract_protected_calls(
        self,
        block_node: Node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str,
    ):
        """Extract calls in the consequence/body block of if/while/for and mark them as condition_protected

        These calls are condition-protected and can be excluded during false positive filtering.
        Recording method: create a data_flow_node for each call with use_type="condition_protected".
        """

        def _find_calls(node: Node, calls: list):
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                if func_node:
                    func_name = self._get_node_text(func_node, code)
                    call_line = node.start_point[0] + 1
                    calls.append((func_name, call_line))
            for child in node.children:
                _find_calls(child, calls)

        calls = []
        _find_calls(block_node, calls)
        for func_name, call_line in calls:
            data_flow_node = DataFlowNode(
                var_name=func_name,
                file_path=file_path,
                line=call_line,
                node_type="use",
                scope=scope,
                value_source="condition_protected",
                use_type="condition_protected",
            )
            result["data_flow_nodes"].append(data_flow_node)

    # ============================================================================
    # Regex fallback scheme
    # ============================================================================

    def _extract_with_regex(self, code: str, file_path: str, result: Dict[str, Any]):
        """
        Extract data using regular expressions (fallback when tree-sitter is unavailable)

        Args:
            code: source code
            file_path: file path
            result: result dictionary
        """
        lines = code.split("\n")

        # Extract function definitions
        func_pattern = re.compile(
            r"^(?:static\s+)?(?:inline\s+)?(?:const\s+)?(?:struct\s+)?(?:enum\s+)?(?:union\s+)?(?:\w+\s+\*?\s*)?(\w+)\s*\([^)]*\)\s*\{"
        )
        for i, line in enumerate(lines, 1):
            match = func_pattern.match(line.strip())
            if match:
                func_name = match.group(1)
                # Roughly estimate the function end line (find the next function or end of file)
                line_end = i
                for j in range(i, len(lines)):
                    if func_pattern.match(lines[j].strip()) and j > i:
                        line_end = j
                        break
                line_end = min(line_end, len(lines))

                symbol = SymbolInfo(
                    name=func_name,
                    kind="function",
                    file_path=file_path,
                    line_start=i,
                    line_end=line_end,
                    signature=line.strip(),
                    scope="global",
                    is_external=False,
                )
                result["symbols"].append(symbol)

        # Extract function calls
        call_pattern = re.compile(r"(\w+)\s*\([^)]*\)")
        for i, line in enumerate(lines, 1):
            # Skip function definition lines
            if func_pattern.match(line.strip()):
                continue
            for match in call_pattern.finditer(line):
                callee_name = match.group(1)
                # Exclude common keywords
                if callee_name in [
                    "if",
                    "while",
                    "for",
                    "switch",
                    "return",
                    "sizeof",
                    "typeof",
                ]:
                    continue

                call_relation = CallRelation(
                    caller_name="unknown",
                    caller_file=file_path,
                    caller_line=i,
                    callee_name=callee_name,
                    callee_file=None,
                    callee_line=None,
                    call_type="direct",
                )
                result["call_relations"].append(call_relation)

        # Extract malloc/free calls
        malloc_pattern = re.compile(
            r"(\w+)\s*=\s*(?:\([^)]*\))?\s*(malloc|calloc|realloc)\s*\("
        )
        free_pattern = re.compile(r"free\s*\(\s*(\w+)\s*\)")
        null_pattern = re.compile(r"(\w+)\s*=\s*(NULL|nullptr|0)")

        for i, line in enumerate(lines, 1):
            # malloc/calloc/realloc
            match = malloc_pattern.search(line)
            if match:
                var_name = match.group(1)
                allocator = match.group(2)
                pointer_state = PointerStateRecord(
                    var_name=var_name,
                    file_path=file_path,
                    line=i,
                    state="ALLOCATED",
                    scope="unknown",
                    allocator=allocator,
                    deallocator=None,
                )
                result["pointer_states"].append(pointer_state)

            # free
            match = free_pattern.search(line)
            if match:
                var_name = match.group(1)
                pointer_state = PointerStateRecord(
                    var_name=var_name,
                    file_path=file_path,
                    line=i,
                    state="FREED",
                    scope="unknown",
                    allocator=None,
                    deallocator="free",
                )
                result["pointer_states"].append(pointer_state)

            # NULL assignment
            match = null_pattern.search(line)
            if match:
                var_name = match.group(1)
                pointer_state = PointerStateRecord(
                    var_name=var_name,
                    file_path=file_path,
                    line=i,
                    state="NULLIFIED",
                    scope="unknown",
                    allocator=None,
                    deallocator=None,
                )
                result["pointer_states"].append(pointer_state)

        # Extract struct/union/enum definitions
        struct_pattern = re.compile(r"(struct|union|enum)\s+(\w+)\s*\{")
        typedef_pattern = re.compile(r"typedef\s+.*\s+(\w+)\s*;")

        for i, line in enumerate(lines, 1):
            match = struct_pattern.search(line)
            if match:
                kind = match.group(1)
                type_name = match.group(2)
                # Roughly estimate the end line
                line_end = i
                brace_count = line.count("{") - line.count("}")
                for j in range(i, len(lines)):
                    brace_count += lines[j].count("{") - lines[j].count("}")
                    if brace_count <= 0:
                        line_end = j + 1
                        break

                type_info = TypeInfo(
                    type_name=type_name,
                    kind=kind,
                    file_path=file_path,
                    line_start=i,
                    line_end=line_end,
                    definition="",
                    members=[],
                )
                result["type_infos"].append(type_info)

            match = typedef_pattern.search(line)
            if match:
                type_name = match.group(1)
                type_info = TypeInfo(
                    type_name=type_name,
                    kind="typedef",
                    file_path=file_path,
                    line_start=i,
                    line_end=i,
                    definition=line.strip(),
                    members=[],
                )
                result["type_infos"].append(type_info)

    # ============================================================================
    # Helper methods
    # ============================================================================

    def _get_node_text(self, node: Node, code: str) -> str:
        """
        Get the node text

        Args:
            node: AST node
            code: source code

        Returns:
            node text
        """
        if node is None:
            return ""
        start_byte = node.start_byte
        end_byte = node.end_byte
        # Use byte indexing, then decode
        code_bytes = bytes(code, "utf-8")
        return code_bytes[start_byte:end_byte].decode("utf-8", errors="replace")

    def _get_function_name(self, node: Node, code: str) -> Optional[str]:
        """
        Get the function name

        Args:
            node: function definition node
            code: source code

        Returns:
            function name
        """
        # The function name is usually in the declarator
        declarator = node.child_by_field_name("declarator")
        if declarator:
            # Handle pointer functions (e.g. int (*func)(int))
            if declarator.type == "pointer_declarator":
                declarator = declarator.child_by_field_name("declarator")

            if declarator and declarator.type == "function_declarator":
                # The function name is in the first identifier child node
                for child in declarator.children:
                    if child.type == "identifier":
                        return self._get_node_text(child, code)
                    elif child.type == "parenthesized_declarator":
                        # Handle complex declarations
                        for subchild in child.children:
                            if subchild.type == "pointer_declarator":
                                for subsubchild in subchild.children:
                                    if subsubchild.type == "identifier":
                                        return self._get_node_text(subsubchild, code)
        return None

    def _extract_function_params(self, node: Node, code: str) -> List[str]:
        """
        Extract function parameter names

        Args:
            node: function definition node
            code: source code

        Returns:
            list of parameter names
        """
        params = []
        declarator = node.child_by_field_name("declarator")
        if declarator and declarator.type == "function_declarator":
            params_node = declarator.child_by_field_name("parameters")
            if params_node:
                for child in params_node.children:
                    if child.type == "parameter_declaration":
                        # Extract the parameter name
                        param_declarator = child.child_by_field_name("declarator")
                        if param_declarator:
                            if param_declarator.type == "identifier":
                                params.append(
                                    self._get_node_text(param_declarator, code)
                                )
                            elif param_declarator.type == "pointer_declarator":
                                # Pointer parameter
                                for subchild in param_declarator.children:
                                    if subchild.type == "identifier":
                                        params.append(
                                            self._get_node_text(subchild, code)
                                        )
        return params

    def _extract_declarators(self, node: Node, code: str) -> List[Tuple[str, str]]:
        """
        Extract variable names and types from a declaration

        Args:
            node: declaration node
            code: source code

        Returns:
            list of (variable name, type name)
        """
        decls = []
        type_node = node.child_by_field_name("type")
        if not type_node:
            return decls

        type_name = self._get_node_text(type_node, code)

        # Handle declarators
        for child in node.children:
            if child.type in ["init_declarator", "declarator"]:
                if child.type == "init_declarator":
                    declarator = child.child_by_field_name("declarator")
                else:
                    declarator = child

                if declarator:
                    if declarator.type == "identifier":
                        decls.append((self._get_node_text(declarator, code), type_name))
                    elif declarator.type == "pointer_declarator":
                        for subchild in declarator.children:
                            if subchild.type == "identifier":
                                decls.append(
                                    (
                                        self._get_node_text(subchild, code),
                                        type_name + "*",
                                    )
                                )
                    elif declarator.type == "array_declarator":
                        for subchild in declarator.children:
                            if subchild.type == "identifier":
                                decls.append(
                                    (
                                        self._get_node_text(subchild, code),
                                        type_name + "[]",
                                    )
                                )

        return decls

    def _get_call_target(self, node: Node, code: str) -> Optional[str]:
        """
        Get the target function name of a function call

        Args:
            node: call expression node
            code: source code

        Returns:
            target function name
        """
        func_node = node.child_by_field_name("function")
        if func_node:
            if func_node.type == "identifier":
                return self._get_node_text(func_node, code)
            elif func_node.type == "field_expression":
                # Member function call (e.g. obj.method())
                field_node = func_node.child_by_field_name("field")
                if field_node:
                    return self._get_node_text(field_node, code)
        return None

    def _extract_call_arguments(
        self,
        args_node: Node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str,
        line: int,
    ):
        """
        Extract variable usage from function call arguments

        Args:
            args_node: argument list node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
            line: call line number
        """
        for child in args_node.children:
            if child.type == "identifier":
                var_name = self._get_node_text(child, code)
                # Create a data flow node (use)
                data_flow_node = DataFlowNode(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    node_type="use",
                    scope=scope,
                    value_source="call_argument",
                )
                result["data_flow_nodes"].append(data_flow_node)

    def _extract_struct_members(
        self, body_node: Node, code: str
    ) -> List[Dict[str, Any]]:
        """
        Extract struct/union members

        Args:
            body_node: struct body node
            code: source code

        Returns:
            member list
        """
        members = []
        for child in body_node.children:
            if child.type == "field_declaration":
                # Extract member name and type
                type_node = child.child_by_field_name("type")
                declarator_node = child.child_by_field_name("declarator")

                if type_node and declarator_node:
                    type_name = self._get_node_text(type_node, code)
                    member_name = self._get_node_text(declarator_node, code)
                    members.append(
                        {
                            "name": member_name,
                            "type": type_name,
                        }
                    )
        return members

    # ============================================================================
    # Data saving
    # ============================================================================

    def _save_to_database(self, file_path: str, result: Dict[str, Any]):
        """
        Save the analysis result to the database

        Args:
            file_path: file path
            result: analysis result dictionary
        """
        # Batch save symbols
        if result["symbols"]:
            self.database.add_symbols_batch(result["symbols"])

        # Batch save call relations
        if result["call_relations"]:
            self.database.add_call_relations_batch(result["call_relations"])

        # Batch save data flow nodes
        if result["data_flow_nodes"]:
            self.database.add_data_flow_nodes_batch(result["data_flow_nodes"])

        # Batch save pointer states
        if result["pointer_states"]:
            self.database.add_pointer_states_batch(result["pointer_states"])

        # Batch save type information
        if result["type_infos"]:
            self.database.add_type_infos_batch(result["type_infos"])

        # Silent log output to avoid interfering with the progress bar display
        # PrettyOutput.auto_print(
        #     f"[DataCollector] Data saved: {len(result['symbols'])} symbols, "
        #     f"{len(result['call_relations'])} call relations, "
        #     f"{len(result['data_flow_nodes'])} data flow nodes"
        # )

    def _check_init_declarator_for_allocation(
        self, node: Node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Check whether the declaration contains a memory allocation call (e.g. char *p = malloc(100))

        Args:
            node: AST node
            code: source code
            file_path: file path
            result: result dictionary
            scope: current scope
        """
        # Traverse the declaration node's children to find init_declarator
        for child in node.children:
            if child.type == "init_declarator":
                # Get the declared variable name
                declarator = child.child_by_field_name("declarator")
                if not declarator:
                    continue

                # Handle pointer declarators (e.g. char *p)
                var_name = None
                if declarator.type == "pointer_declarator":
                    for subchild in declarator.children:
                        if subchild.type == "identifier":
                            var_name = self._get_node_text(subchild, code)
                            break
                elif declarator.type == "identifier":
                    var_name = self._get_node_text(declarator, code)

                if not var_name:
                    continue

                # Check whether the initializer is a function call
                init_value = child.child_by_field_name("value")
                if init_value and init_value.type == "call_expression":
                    call_name = self._get_call_target(init_value, code)
                    line = node.start_point[0] + 1

                    # Check whether it is a memory allocation function
                    if call_name in ["malloc", "calloc", "realloc", "new"]:
                        pointer_state = PointerStateRecord(
                            var_name=var_name,
                            file_path=file_path,
                            line=line,
                            state="ALLOCATED",
                            scope=scope,
                            allocator=call_name,
                            deallocator=None,
                        )
                        result["pointer_states"].append(pointer_state)
                    else:
                        # Non-allocation function call, recorded as UNKNOWN state
                        pointer_state = PointerStateRecord(
                            var_name=var_name,
                            file_path=file_path,
                            line=line,
                            state="UNKNOWN",
                            scope=scope,
                            allocator=None,
                            deallocator=None,
                        )
                        result["pointer_states"].append(pointer_state)

    # ============================================================================
    # Rust AST handling methods
    # ============================================================================

    def _handle_rust_function_definition(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a Rust function definition
        """
        func_name = self._get_rust_function_name(node, code)
        if not func_name:
            return

        signature = self._get_node_text(node, code)
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        # Check whether it is an unsafe function
        is_unsafe = False
        for child in node.children:
            if child.type == "unsafe" or (
                child.type == "identifier"
                and self._get_node_text(child, code) == "unsafe"
            ):
                is_unsafe = True
                break

        symbol = SymbolInfo(
            name=func_name,
            kind="function",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            signature=signature,
            scope="global",
            is_external=False,
        )
        result["symbols"].append(symbol)

        if is_unsafe:
            unsafe_symbol = SymbolInfo(
                name=f"__unsafe_fn__{func_name}",
                kind="unsafe_block",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                signature=f"unsafe fn {func_name}",
                scope="global",
                is_external=False,
            )
            result["symbols"].append(unsafe_symbol)

        params = self._extract_rust_function_params(node, code)
        for param in params:
            param_node = DataFlowNode(
                var_name=param,
                file_path=file_path,
                line=line_start,
                node_type="param_in",
                scope=func_name,
                value_source="parameter",
            )
            result["data_flow_nodes"].append(param_node)

    def _handle_rust_struct_definition(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a Rust struct definition
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        struct_name = self._get_node_text(name_node, code)
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        members = []
        body_node = node.child_by_field_name("body")
        if body_node:
            for child in body_node.children:
                if child.type == "field_declaration":
                    field_name_node = child.child_by_field_name("name")
                    field_type_node = child.child_by_field_name("type")
                    if field_name_node and field_type_node:
                        members.append(
                            {
                                "name": self._get_node_text(field_name_node, code),
                                "type": self._get_node_text(field_type_node, code),
                            }
                        )

        type_info = TypeInfo(
            type_name=struct_name,
            kind="struct",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            definition=self._get_node_text(node, code),
            members=members,
        )
        result["type_infos"].append(type_info)

    def _handle_rust_enum_definition(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a Rust enum definition
        """
        name_node = node.child_by_field_name("name")
        if not name_node:
            return

        enum_name = self._get_node_text(name_node, code)
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        type_info = TypeInfo(
            type_name=enum_name,
            kind="enum",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            definition=self._get_node_text(node, code),
            members=[],
        )
        result["type_infos"].append(type_info)

    def _handle_rust_impl_block(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a Rust impl block
        """
        is_unsafe = False
        for child in node.children:
            if child.type == "unsafe" or (
                child.type == "identifier"
                and self._get_node_text(child, code) == "unsafe"
            ):
                is_unsafe = True
                break

        if is_unsafe:
            line_start = node.start_point[0] + 1
            line_end = node.end_point[0] + 1
            type_node = node.child_by_field_name("type")
            type_name = self._get_node_text(type_node, code) if type_node else "unknown"

            unsafe_symbol = SymbolInfo(
                name=f"__unsafe_impl__{type_name}",
                kind="unsafe_block",
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                signature=f"unsafe impl {type_name}",
                scope="global",
                is_external=False,
            )
            result["symbols"].append(unsafe_symbol)

    def _handle_rust_extern_block(
        self, node, code: str, file_path: str, result: Dict[str, Any]
    ):
        """
        Handle a Rust extern block
        """
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        abi = "C"
        for child in node.children:
            if child.type == "string_literal":
                abi = self._get_node_text(child, code).strip('"')
                break

        extern_symbol = SymbolInfo(
            name=f"__extern_block__{abi}",
            kind="extern_block",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            signature=f'extern "{abi}"',
            scope="global",
            is_external=True,
        )
        result["symbols"].append(extern_symbol)

    def _handle_rust_unsafe_block(
        self, node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a Rust unsafe block
        """
        line_start = node.start_point[0] + 1
        line_end = node.end_point[0] + 1

        unsafe_symbol = SymbolInfo(
            name=f"__unsafe_block__{line_start}",
            kind="unsafe_block",
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            signature="unsafe { ... }",
            scope=scope,
            is_external=False,
        )
        result["symbols"].append(unsafe_symbol)

    def _handle_rust_let_declaration(
        self, node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a Rust let declaration
        """
        # In tree-sitter-rust, the variable name of a let_declaration is not the "name" field,
        # but rather an identifier child node (after the mutable_specifier)
        name_node = node.child_by_field_name("name")
        if not name_node:
            # Fallback: look for an identifier child node (skip let/mutable_specifier)
            for child in node.children:
                if child.type == "identifier":
                    name_node = child
                    break
        if not name_node:
            return

        var_name = self._get_node_text(name_node, code)
        line = node.start_point[0] + 1

        type_node = node.child_by_field_name("type")
        type_name = self._get_node_text(type_node, code) if type_node else None

        symbol = SymbolInfo(
            name=var_name,
            kind="variable",
            file_path=file_path,
            line_start=line,
            line_end=line,
            type_name=type_name,
            scope=scope,
            is_external=False,
        )
        result["symbols"].append(symbol)

        data_flow_node = DataFlowNode(
            var_name=var_name,
            file_path=file_path,
            line=line,
            node_type="def",
            scope=scope,
            value_source="let_binding",
        )
        result["data_flow_nodes"].append(data_flow_node)

        if type_name and ("*mut" in type_name or "*const" in type_name):
            pointer_state = PointerStateRecord(
                var_name=var_name,
                file_path=file_path,
                line=line,
                state="RAW_POINTER",
                scope=scope,
                allocator=None,
                deallocator=None,
            )
            result["pointer_states"].append(pointer_state)

        # Detect the pointer_type in a type_cast_expression (e.g. &mut num as *mut i32)
        if not type_name or ("*mut" not in type_name and "*const" not in type_name):
            value_node = node.child_by_field_name("value")
            if value_node and value_node.type == "type_cast_expression":
                # Traverse type_cast_expression children to find pointer_type
                for child in value_node.children:
                    if child.type == "pointer_type":
                        pointer_state = PointerStateRecord(
                            var_name=var_name,
                            file_path=file_path,
                            line=line,
                            state="RAW_POINTER",
                            scope=scope,
                            allocator=None,
                            deallocator=None,
                        )
                        result["pointer_states"].append(pointer_state)
                        break

        value_node = node.child_by_field_name("value")
        if value_node and value_node.type == "call_expression":
            call_name = self._get_rust_call_target(value_node, code)
            if call_name:
                call_relation = CallRelation(
                    caller_name=scope if scope != "global" else "unknown",
                    caller_file=file_path,
                    caller_line=line,
                    callee_name=call_name,
                    callee_file=None,
                    callee_line=None,
                    call_type="direct",
                )
                result["call_relations"].append(call_relation)

    def _handle_rust_call_expression(
        self, node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a Rust function call
        """
        callee_name = self._get_rust_call_target(node, code)
        if not callee_name:
            return

        line = node.start_point[0] + 1

        call_relation = CallRelation(
            caller_name=scope if scope != "global" else "unknown",
            caller_file=file_path,
            caller_line=line,
            callee_name=callee_name,
            callee_file=None,
            callee_line=None,
            call_type="direct",
        )
        result["call_relations"].append(call_relation)

        args_node = node.child_by_field_name("arguments")
        if args_node:
            self._extract_rust_call_arguments(
                args_node, code, file_path, result, scope, line
            )

    def _handle_rust_method_call(
        self, node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a Rust method call
        """
        method_node = node.child_by_field_name("method")
        if not method_node:
            return

        method_name = self._get_node_text(method_node, code)
        line = node.start_point[0] + 1

        object_node = node.child_by_field_name("object")
        object_name = self._get_node_text(object_node, code) if object_node else None

        call_relation = CallRelation(
            caller_name=scope if scope != "global" else "unknown",
            caller_file=file_path,
            caller_line=line,
            callee_name=method_name,
            callee_file=None,
            callee_line=None,
            call_type="method",
        )
        result["call_relations"].append(call_relation)

        if method_name in ["unwrap", "expect"]:
            data_flow_node = DataFlowNode(
                var_name=object_name if object_name else "__unknown__",
                file_path=file_path,
                line=line,
                node_type="use",
                scope=scope,
                value_source="method_call",
                use_type="unwrap",
            )
            result["data_flow_nodes"].append(data_flow_node)

    def _handle_rust_macro_invocation(
        self, node, code: str, file_path: str, result: Dict[str, Any], scope: str
    ):
        """
        Handle a Rust macro invocation
        """
        # In tree-sitter-rust, the macro name of a macro_invocation is not the "name" field,
        # but rather the first identifier child node
        macro_name_node = node.child_by_field_name("name")
        if not macro_name_node:
            # Fallback: find the first identifier child node
            for child in node.children:
                if child.type == "identifier":
                    macro_name_node = child
                    break
        if not macro_name_node:
            return

        macro_name = self._get_node_text(macro_name_node, code)
        line = node.start_point[0] + 1

        call_relation = CallRelation(
            caller_name=scope if scope != "global" else "unknown",
            caller_file=file_path,
            caller_line=line,
            callee_name=f"{macro_name}!",
            callee_file=None,
            callee_line=None,
            call_type="macro",
        )
        result["call_relations"].append(call_relation)

        if macro_name in ["panic", "unreachable"]:
            data_flow_node = DataFlowNode(
                var_name=macro_name,
                file_path=file_path,
                line=line,
                node_type="use",
                scope=scope,
                value_source="macro",
                use_type="panic",
            )
            result["data_flow_nodes"].append(data_flow_node)

    # ============================================================================
    # Rust helper methods
    # ============================================================================

    def _get_rust_function_name(self, node, code: str) -> Optional[str]:
        """
        Get the Rust function name
        """
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._get_node_text(name_node, code)
        return None

    def _extract_rust_function_params(self, node, code: str) -> List[str]:
        """
        Extract Rust function parameter names
        """
        params = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "parameter":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        params.append(self._get_node_text(name_node, code))
                elif child.type == "self_parameter":
                    params.append("self")
        return params

    def _get_rust_call_target(self, node, code: str) -> Optional[str]:
        """
        Get the target function name of a Rust function call
        """
        func_node = node.child_by_field_name("function")
        if func_node:
            if func_node.type == "identifier":
                return self._get_node_text(func_node, code)
            elif func_node.type == "scoped_identifier":
                return self._get_node_text(func_node, code)
            elif func_node.type == "field_expression":
                field_node = func_node.child_by_field_name("field")
                if field_node:
                    return self._get_node_text(field_node, code)
        return None

    def _extract_rust_call_arguments(
        self,
        args_node,
        code: str,
        file_path: str,
        result: Dict[str, Any],
        scope: str,
        line: int,
    ):
        """
        Extract variable usage from Rust function call arguments
        """
        for child in args_node.children:
            if child.type == "identifier":
                var_name = self._get_node_text(child, code)
                data_flow_node = DataFlowNode(
                    var_name=var_name,
                    file_path=file_path,
                    line=line,
                    node_type="use",
                    scope=scope,
                    value_source="call_argument",
                )
                result["data_flow_nodes"].append(data_flow_node)