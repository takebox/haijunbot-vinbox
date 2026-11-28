# -*- coding: utf-8 -*-
"""
C2Rust transpiler constant definitions
"""

from typing import Set

# Data file constants
C2RUST_DIRNAME = ".haijunbot/c2rust"

SYMBOLS_JSONL = "symbols.jsonl"
ORDER_JSONL = "translation_order.jsonl"
PROGRESS_JSON = "progress.json"
CONFIG_JSON = "config.json"
SYMBOL_MAP_JSONL = "symbol_map.jsonl"

# Configuration constants
ERROR_SUMMARY_MAX_LENGTH = 2000  # Maximum length of the error message summary
DEFAULT_PLAN_MAX_RETRIES = 0  # Default max retries for the planning stage (0 means unlimited retries)
DEFAULT_REVIEW_MAX_ITERATIONS = 0  # Max iterations for the review stage (0 means unlimited retries)
DEFAULT_CHECK_MAX_RETRIES = 0  # Default max retries for the cargo check stage (0 means unlimited retries)
DEFAULT_TEST_MAX_RETRIES = 0  # Default max retries for the cargo test stage (0 means unlimited retries)

# Rollback and retry constants
CONSECUTIVE_FIX_FAILURE_THRESHOLD = 10  # Threshold of consecutive fix failures; reaching this value triggers a rollback
MAX_FUNCTION_RETRIES = 10  # Maximum number of times a function can be restarted
DEFAULT_PLAN_MAX_RETRIES_ENTRY = 5  # Default value of plan_max_retries for the run_transpile entry function

# File extension constants
SOURCE_EXTS: Set[str] = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".C",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
}
HEADER_EXTS = {".h", ".hh", ".hpp", ".hxx"}

# AST node type constants
TYPE_KINDS: Set[str] = {
    "STRUCT_DECL",
    "UNION_DECL",
    "ENUM_DECL",
    "CXX_RECORD_DECL",  # C++ class/struct/union
    "TYPEDEF_DECL",
    "TYPE_ALIAS_DECL",
}

# Run state file
RUN_STATE_JSON = "run_state.json"

# Library Replacer related constants
# LLM evaluation retry configuration
MAX_LLM_RETRIES = 3  # Maximum retries for LLM evaluation

# Source snippet reading configuration
DEFAULT_SOURCE_SNIPPET_MAX_LINES = 200  # Default maximum number of lines for a source snippet
SUBTREE_SOURCE_SNIPPET_MAX_LINES = 120  # Maximum number of lines for a source snippet in a subtree prompt

# Subtree prompt construction configuration
MAX_SUBTREE_NODES_META = 200  # Maximum length of the subtree node metadata list
MAX_SUBTREE_EDGES = 400  # Maximum length of the subtree edge list
MAX_DOT_EDGES = 200  # DOT graph edge threshold (no DOT is generated above this value)
MAX_CHILD_SAMPLES = 2  # Number of child node samples
MAX_SOURCE_SAMPLES = 3  # Maximum number of representative source samples (comment note)

# Display configuration
MAX_NOTES_DISPLAY_LENGTH = 200  # Maximum length for displaying notes

# Output file path configuration
DEFAULT_SYMBOLS_OUTPUT = "symbols_library_pruned.jsonl"  # Default symbol table output file name
DEFAULT_MAPPING_OUTPUT = "library_replacements.jsonl"  # Default replacement mapping output file name
SYMBOLS_PRUNE_OUTPUT = "symbols_prune.jsonl"  # Compatibility symbol table output file name
ORDER_PRUNE_OUTPUT = "translation_order_prune.jsonl"  # Translation order output file name for the pruning stage
ORDER_ALIAS_OUTPUT = "translation_order.jsonl"  # General translation order output file name
DEFAULT_CHECKPOINT_FILE = "library_replacer_checkpoint.json"  # Default checkpoint file name

# Checkpoint configuration
DEFAULT_CHECKPOINT_INTERVAL = 1  # Default checkpoint save interval (save once every N evaluated nodes)

# JSON formatting configuration
JSON_INDENT = 2  # Number of indentation spaces for JSON formatting
