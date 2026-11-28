"""
Taint analysis framework - unified taint analyzer abstract interface and data structures

Supports multiple analyzer backends (Joern, PhASAR, SVF), providing an extensible rule configuration mechanism.
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class TaintSeverity(Enum):
    """Severity of a taint issue"""

    CRITICAL = "critical"  # Critical vulnerabilities (command injection, SQL injection, etc.)
    HIGH = "high"  # High-severity vulnerabilities (path traversal, format string, etc.)
    MEDIUM = "medium"  # Medium-severity vulnerabilities (information disclosure, etc.)
    LOW = "low"  # Low-severity issues


@dataclass
class TaintPath:
    """Taint propagation path"""

    source: str  # Taint source (e.g., getenv, read, recv)
    sink: str  # Taint sink (e.g., system, exec, sprintf)
    path: List[str] = field(default_factory=list)  # Propagation path (node list)
    confidence: float = 1.0  # Confidence (0.0-1.0)
    severity: TaintSeverity = TaintSeverity.HIGH  # Severity
    description: str = ""  # Issue description
    file_path: str = ""  # File path
    line_number: int = 0  # Line number
    code_snippet: str = ""  # Code snippet

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format"""
        return {
            "source": self.source,
            "sink": self.sink,
            "path": self.path,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "code_snippet": self.code_snippet,
        }


@dataclass
class TaintSource:
    """Taint source definition"""

    name: str  # Taint source name (e.g., getenv)
    category: str  # Category (e.g., user_input, environment, network)
    description: str = ""  # Description
    patterns: List[str] = field(default_factory=list)  # Match patterns (function names, variable names, etc.)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "patterns": self.patterns,
        }


@dataclass
class TaintSink:
    """Taint sink definition"""

    name: str  # Taint sink name (e.g., system)
    category: str  # Category (e.g., command_execution, file_operation)
    severity: TaintSeverity = TaintSeverity.HIGH  # Severity
    description: str = ""  # Description
    patterns: List[str] = field(default_factory=list)  # Match patterns

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "severity": self.severity.value,
            "description": self.description,
            "patterns": self.patterns,
        }


class TaintAnalyzer(ABC):
    """Abstract base class for taint analyzers"""

    def __init__(self):
        self.sources: List[TaintSource] = []
        self.sinks: List[TaintSink] = []
        self.sanitizers: List[str] = []  # Sanitizer function list

    @abstractmethod
    def analyze(self, source_code: str, file_path: str = "") -> List[TaintPath]:
        """
        Execute the taint analysis

        Args:
            source_code: Source code content
            file_path: File path (optional)

        Returns:
            List of taint propagation paths
        """
        pass

    @abstractmethod
    def analyze_file(self, file_path: str) -> List[TaintPath]:
        """
        Analyze a file

        Args:
            file_path: File path

        Returns:
            List of taint propagation paths
        """
        pass

    def configure_sources(self, sources: List[TaintSource]):
        """Configure the taint sources"""
        self.sources = sources

    def configure_sinks(self, sinks: List[TaintSink]):
        """Configure the taint sinks"""
        self.sinks = sinks

    def configure_sanitizers(self, sanitizers: List[str]):
        """Configure the sanitizer functions"""
        self.sanitizers = sanitizers

    def add_source(self, source: TaintSource):
        """Add a taint source"""
        self.sources.append(source)

    def add_sink(self, sink: TaintSink):
        """Add a taint sink"""
        self.sinks.append(sink)

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check whether the analyzer is available

        Returns:
            True if the analyzer is installed and available
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the analyzer name"""
        pass

    @abstractmethod
    def get_version(self) -> str:
        """Get the analyzer version"""
        pass


class TaintRule:
    """Taint analysis rule"""

    def __init__(
        self,
        name: str,
        sources: List[TaintSource],
        sinks: List[TaintSink],
        sanitizers: Optional[List[str]] = None,
        severity: TaintSeverity = TaintSeverity.HIGH,
        description: str = "",
    ):
        self.name = name
        self.sources = sources
        self.sinks = sinks
        self.sanitizers = sanitizers or []
        self.severity = severity
        self.description = description

    def check(
        self, analyzer: TaintAnalyzer, code: str, file_path: str = ""
    ) -> List[TaintPath]:
        """
        Check the rule using the taint analyzer

        Args:
            analyzer: Taint analyzer instance
            code: Source code
            file_path: File path

        Returns:
            List of taint paths
        """
        # Configure the analyzer
        analyzer.configure_sources(self.sources)
        analyzer.configure_sinks(self.sinks)
        analyzer.configure_sanitizers(self.sanitizers)

        # Execute the analysis
        paths = analyzer.analyze(code, file_path)

        # Set the severity and description
        for path in paths:
            path.severity = self.severity
            if not path.description:
                path.description = (
                    f"{self.name}: taint propagates from {path.source} to {path.sink}"
                )

        return paths

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict format"""
        return {
            "name": self.name,
            "sources": [s.to_dict() for s in self.sources],
            "sinks": [s.to_dict() for s in self.sinks],
            "sanitizers": self.sanitizers,
            "severity": self.severity.value,
            "description": self.description,
        }


# ============================================================================
# Predefined taint sources
# ============================================================================

# User input
USER_INPUT_SOURCES = [
    TaintSource("getenv", "environment", "Obtain data from an environment variable", ["getenv"]),
    TaintSource("read", "user_input", "Read from a file descriptor", ["read", "recv", "recvfrom"]),
    TaintSource("scanf", "user_input", "Read from standard input", ["scanf", "fscanf", "sscanf"]),
    TaintSource("gets", "user_input", "Read a string from standard input", ["gets", "fgets"]),
    TaintSource("argv", "command_line", "Command-line arguments", ["argv", "argc"]),
]

# Network input
NETWORK_SOURCES = [
    TaintSource("recv", "network", "Receive data from the network", ["recv", "recvfrom", "recvmsg"]),
    TaintSource("accept", "network", "Accept a network connection", ["accept", "accept4"]),
]

# File input
FILE_SOURCES = [
    TaintSource("fread", "file", "Read from a file", ["fread", "fgets", "fgetc"]),
    TaintSource("mmap", "file", "Memory-map a file", ["mmap", "mmap64"]),
]

# ============================================================================
# Predefined taint sinks
# ============================================================================

# Command execution
COMMAND_SINKS = [
    TaintSink(
        "system",
        "command_execution",
        TaintSeverity.CRITICAL,
        "Execute a system command",
        ["system", "popen"],
    ),
    TaintSink(
        "execve",
        "command_execution",
        TaintSeverity.CRITICAL,
        "Execute a program",
        ["execve", "execl", "execlp", "execvp", "execv"],
    ),
]

# File operations
FILE_SINKS = [
    TaintSink(
        "open", "file_operation", TaintSeverity.HIGH, "Open a file", ["open", "openat"]
    ),
    TaintSink(
        "fopen",
        "file_operation",
        TaintSeverity.HIGH,
        "Open a file stream",
        ["fopen", "freopen"],
    ),
    TaintSink(
        "access",
        "file_operation",
        TaintSeverity.MEDIUM,
        "Check file permissions",
        ["access", "faccessat"],
    ),
]

# Format strings
FORMAT_SINKS = [
    TaintSink(
        "printf",
        "format_string",
        TaintSeverity.HIGH,
        "Formatted output",
        ["printf", "fprintf", "sprintf", "snprintf"],
    ),
]

# SQL operations
SQL_SINKS = [
    TaintSink(
        "sqlite3_exec",
        "sql_injection",
        TaintSeverity.CRITICAL,
        "Execute an SQL statement",
        ["sqlite3_exec", "mysql_query"],
    ),
]

# Memory operations
MEMORY_SINKS = [
    TaintSink(
        "memcpy",
        "memory_operation",
        TaintSeverity.MEDIUM,
        "Memory copy",
        ["memcpy", "memmove"],
    ),
    TaintSink(
        "strcpy",
        "memory_operation",
        TaintSeverity.HIGH,
        "String copy",
        ["strcpy", "strcat"],
    ),
]

# Memory free (UAF source)
FREE_SOURCES = [
    TaintSource("free", "memory_free", "Free memory", ["free"]),
    TaintSource("delete", "memory_free", "Delete an object", ["delete"]),
]

# Pointer dereference (UAF sink)
DEREF_SINKS = [
    TaintSink(
        "pointer_deref",
        "pointer_access",
        TaintSeverity.CRITICAL,
        "Pointer dereference",
        ["->", "*", "[]"],
    ),
]

# Double free sink
FREE_SINKS = [
    TaintSink(
        "free",
        "memory_free",
        TaintSeverity.CRITICAL,
        "Free memory",
        ["free"],
    ),
]

# Memory allocation sources (malloc_null_check)
ALLOC_SOURCES = [
    TaintSource("malloc", "memory_alloc", "Allocate memory", ["malloc"]),
    TaintSource("calloc", "memory_alloc", "Allocate memory", ["calloc"]),
    TaintSource("realloc", "memory_alloc", "Reallocate memory", ["realloc"]),
    TaintSource("new", "memory_alloc", "Create an object", ["new"]),
]

# NULL check sinks (used to detect whether there is a NULL check after malloc)
NULL_CHECK_SINKS = [
    TaintSink(
        "null_check",
        "null_check",
        TaintSeverity.LOW,
        "NULL check",
        ["if", "while", "?"],
    ),
]

# realloc return value sinks (used to detect whether the realloc return value is used)
REALLOC_USE_SINKS = [
    TaintSink(
        "realloc_use",
        "realloc_use",
        TaintSeverity.HIGH,
        "realloc return value usage",
        ["=", "return"],
    ),
]

# IO return value check sinks (used to detect whether IO function return values are checked)
IO_CHECK_SINKS = [
    TaintSink(
        "io_check",
        "io_check",
        TaintSeverity.LOW,
        "IO return value check",
        ["if", "while", "<", ">", "==", "!=", "<=", ">="],
    ),
]

# getenv return value check sinks (used to detect whether the getenv return value is NULL-checked)
GETENV_CHECK_SINKS = [
    TaintSink(
        "getenv_check",
        "getenv_check",
        TaintSeverity.LOW,
        "getenv return value check",
        ["if", "while", "NULL", "0"],
    ),
]

# realloc sources (realloc return value)
REALLOC_SOURCES = [
    TaintSource("realloc", "realloc_return", "realloc return value", ["realloc"]),
]

# IO function sources (IO return values)
IO_SOURCES = [
    TaintSource("read", "io_return", "Read return value", ["read", "fread", "recv"]),
    TaintSource("write", "io_return", "Write return value", ["write", "fwrite", "send"]),
    TaintSource("fopen", "io_return", "File open return value", ["fopen", "open"]),
]

# getenv sources (getenv return value)
GETENV_SOURCES = [
    TaintSource("getenv", "getenv_return", "getenv return value", ["getenv"]),
]

# ============================================================================
# Rust-specific taint sources
# ============================================================================

# Rust user input sources
RUST_USER_INPUT_SOURCES = [
    TaintSource(
        "stdin",
        "user_input",
        "Read from standard input",
        ["stdin", "io::stdin", "std::io::stdin"],
    ),
    TaintSource(
        "read_line", "user_input", "Read a line of input", ["read_line", "read_to_string"]
    ),
    TaintSource(
        "args", "command_line", "Command-line arguments", ["args", "env::args", "std::env::args"]
    ),
    TaintSource("var", "environment", "Environment variable", ["var", "env::var", "std::env::var"]),
    TaintSource(
        "vars", "environment", "All environment variables", ["vars", "env::vars", "std::env::vars"]
    ),
]

# Rust network input sources
RUST_NETWORK_SOURCES = [
    TaintSource(
        "tcp_read", "network", "TCP read", ["TcpStream::read", "read", "read_exact"]
    ),
    TaintSource("udp_recv", "network", "UDP receive", ["recv", "recv_from"]),
    TaintSource(
        "http_request", "network", "HTTP request body", ["body", "into_body", "bytes"]
    ),
]

# Rust file input sources
RUST_FILE_SOURCES = [
    TaintSource(
        "file_read", "file", "File read", ["File::open", "read_to_string", "read_to_end"]
    ),
    TaintSource("fs_read", "file", "File system read", ["fs::read", "fs::read_to_string"]),
]

# Rust FFI input sources (data passed in from C code)
RUST_FFI_SOURCES = [
    TaintSource(
        "ffi_ptr",
        "ffi",
        "FFI pointer data",
        ["from_raw", "from_raw_parts", "CStr::from_ptr"],
    ),
    TaintSource(
        "ffi_cstring", "ffi", "FFI string", ["CString::from_raw", "CStr::from_ptr"]
    ),
]

# Rust unsafe block output sources
RUST_UNSAFE_SOURCES = [
    TaintSource("unsafe_deref", "unsafe_op", "unsafe dereference", ["deref", "*"]),
    TaintSource(
        "unsafe_cast", "unsafe_op", "unsafe type conversion", ["transmute", "from_raw_parts"]
    ),
]

# ============================================================================
# Rust-specific taint sinks
# ============================================================================

# Rust command execution sinks
RUST_COMMAND_SINKS = [
    TaintSink(
        "Command::new",
        "command_execution",
        TaintSeverity.CRITICAL,
        "Execute a system command",
        ["Command::new", "process::Command", "std::process::Command"],
    ),
    TaintSink(
        "output",
        "command_execution",
        TaintSeverity.CRITICAL,
        "Obtain the command output",
        ["output", "status", "spawn"],
    ),
]

# Rust file operation sinks
RUST_FILE_SINKS = [
    TaintSink(
        "File::create",
        "file_operation",
        TaintSeverity.HIGH,
        "Create a file",
        ["File::create", "OpenOptions::new", "fs::write"],
    ),
    TaintSink(
        "fs::remove",
        "file_operation",
        TaintSeverity.HIGH,
        "Delete a file",
        ["fs::remove_file", "fs::remove_dir"],
    ),
    TaintSink(
        "fs::copy",
        "file_operation",
        TaintSeverity.MEDIUM,
        "Copy a file",
        ["fs::copy", "fs::rename"],
    ),
]

# Rust memory operation sinks
RUST_MEMORY_SINKS = [
    TaintSink(
        "write",
        "memory_operation",
        TaintSeverity.HIGH,
        "Memory write",
        ["write", "write_bytes", "copy", "copy_nonoverlapping"],
    ),
    TaintSink(
        "from_raw_parts",
        "memory_operation",
        TaintSeverity.HIGH,
        "Construct from a raw pointer",
        ["from_raw_parts", "from_raw_parts_mut", "from_raw"],
    ),
]

# Rust format string sinks
RUST_FORMAT_SINKS = [
    TaintSink(
        "format!",
        "format_string",
        TaintSeverity.MEDIUM,
        "Format string",
        ["format!", "print!", "println!", "eprint!", "eprintln!"],
    ),
]

# Rust panic sinks (may cause inconsistent state)
RUST_PANIC_SINKS = [
    TaintSink(
        "panic!",
        "panic",
        TaintSeverity.MEDIUM,
        "Panic terminates the program",
        ["panic!", "unreachable!", "todo!", "unimplemented!"],
    ),
]

# Rust error ignore sinks (let _ = ...)
RUST_ERROR_IGNORE_SINKS = [
    TaintSink(
        "let _",
        "error_ignore",
        TaintSeverity.MEDIUM,
        "Ignore an error result",
        ["let _", "drop"],
    ),
]

# ============================================================================
# Predefined rule library
# ============================================================================

TAINT_RULES: Dict[str, TaintRule] = {
    "command_injection": TaintRule(
        "command_injection",
        USER_INPUT_SOURCES + NETWORK_SOURCES,
        COMMAND_SINKS,
        ["escapeshellarg", "escapeshellcmd"],
        TaintSeverity.CRITICAL,
        "Command injection: user input is used directly to execute system commands",
    ),
    "format_string": TaintRule(
        "format_string",
        USER_INPUT_SOURCES,
        FORMAT_SINKS,
        [],
        TaintSeverity.HIGH,
        "Format string vulnerability: user input is used as a format string",
    ),
    "path_traversal": TaintRule(
        "path_traversal",
        USER_INPUT_SOURCES + NETWORK_SOURCES,
        FILE_SINKS,
        ["realpath", "basename", "dirname"],
        TaintSeverity.HIGH,
        "Path traversal: user input is used in file path operations",
    ),
    "sql_injection": TaintRule(
        "sql_injection",
        USER_INPUT_SOURCES,
        SQL_SINKS,
        ["sqlite3_prepare_v2", "mysql_real_escape_string"],
        TaintSeverity.CRITICAL,
        "SQL injection: user input is directly concatenated into an SQL statement",
    ),
    "buffer_overflow": TaintRule(
        "buffer_overflow",
        USER_INPUT_SOURCES + NETWORK_SOURCES,
        MEMORY_SINKS,
        ["strncpy", "snprintf"],
        TaintSeverity.HIGH,
        "Buffer overflow: user input is used in unsafe memory operations",
    ),
    "use_after_free": TaintRule(
        "use_after_free",
        FREE_SOURCES,
        DEREF_SINKS,
        [],  # No sanitizer functions
        TaintSeverity.CRITICAL,
        "Use-After-Free: freed memory is dereferenced and used",
    ),
    "double_free": TaintRule(
        "double_free",
        FREE_SOURCES,
        FREE_SINKS,
        [],  # No sanitizer functions
        TaintSeverity.CRITICAL,
        "Double Free: the same memory is freed repeatedly",
    ),
    "malloc_null_check": TaintRule(
        "malloc_null_check",
        ALLOC_SOURCES,
        DEREF_SINKS,  # Dereferenced directly after allocation without a NULL check
        ["if", "while", "?"],  # NULL check acts as a sanitizer
        TaintSeverity.HIGH,
        "No NULL check after memory allocation: the allocation result is used directly without checking whether it succeeded",
    ),
    "null_deref": TaintRule(
        "null_deref",
        USER_INPUT_SOURCES + ALLOC_SOURCES,
        DEREF_SINKS,
        ["if", "while", "?"],  # NULL check acts as a sanitizer
        TaintSeverity.HIGH,
        "Null pointer dereference: a pointer that may be NULL is dereferenced directly",
    ),
    "realloc_assign_back": TaintRule(
        "realloc_assign_back",
        REALLOC_SOURCES,
        REALLOC_USE_SINKS,
        [],  # No sanitizer functions
        TaintSeverity.HIGH,
        "realloc return value not used: not assigning the realloc return value back to the original pointer may cause a memory leak",
    ),
    "unchecked_io": TaintRule(
        "unchecked_io",
        IO_SOURCES,
        IO_CHECK_SINKS,
        [],  # No sanitizer functions
        TaintSeverity.MEDIUM,
        "IO return value not checked: not checking the IO function return value may lead to missing error handling",
    ),
    "getenv_unchecked": TaintRule(
        "getenv_unchecked",
        GETENV_SOURCES,
        GETENV_CHECK_SINKS,
        [],  # No sanitizer functions
        TaintSeverity.MEDIUM,
        "getenv return value not checked: not NULL-checking the getenv return value may cause a null pointer dereference",
    ),
    # ============================================================================
    # Rust-specific taint rules
    # ============================================================================
    "rust_command_injection": TaintRule(
        "rust_command_injection",
        RUST_USER_INPUT_SOURCES + RUST_NETWORK_SOURCES,
        RUST_COMMAND_SINKS,
        ["shlex::split", "shell_words::split"],  # Rust command sanitizers
        TaintSeverity.CRITICAL,
        "Rust command injection: user input is used directly to execute system commands",
    ),
    "rust_path_traversal": TaintRule(
        "rust_path_traversal",
        RUST_USER_INPUT_SOURCES + RUST_NETWORK_SOURCES,
        RUST_FILE_SINKS,
        ["Path::canonicalize", "PathBuf::canonicalize"],  # Rust path sanitizers
        TaintSeverity.HIGH,
        "Rust path traversal: user input is used in file path operations",
    ),
    "rust_format_string": TaintRule(
        "rust_format_string",
        RUST_USER_INPUT_SOURCES,
        RUST_FORMAT_SINKS,
        [],
        TaintSeverity.MEDIUM,
        "Rust format string: user input is used as a format string",
    ),
    "rust_memory_safety": TaintRule(
        "rust_memory_safety",
        RUST_FFI_SOURCES + RUST_UNSAFE_SOURCES,
        RUST_MEMORY_SINKS,
        [],
        TaintSeverity.HIGH,
        "Rust memory safety: FFI/unsafe data is used in memory operations",
    ),
    "rust_panic_usage": TaintRule(
        "rust_panic_usage",
        RUST_USER_INPUT_SOURCES,
        RUST_PANIC_SINKS,
        [],
        TaintSeverity.MEDIUM,
        "Rust panic usage: user input may cause a panic",
    ),
    "rust_error_ignore": TaintRule(
        "rust_error_ignore",
        RUST_USER_INPUT_SOURCES + RUST_NETWORK_SOURCES,
        RUST_ERROR_IGNORE_SINKS,
        [],
        TaintSeverity.MEDIUM,
        "Rust error ignore: a possible error result may be ignored",
    ),
}


def get_rule(name: str) -> Optional[TaintRule]:
    """Get the rule with the specified name"""
    return TAINT_RULES.get(name)


def get_all_rules() -> List[TaintRule]:
    """Get all rules"""
    return list(TAINT_RULES.values())


def register_rule(rule: TaintRule):
    """Register a custom rule"""
    TAINT_RULES[rule.name] = rule


# ============================================================================
# Analyzer factory
# ============================================================================


class TaintAnalyzerFactory:
    """Taint analyzer factory"""

    _analyzers: Dict[str, type] = {}

    @classmethod
    def register(cls, name: str, analyzer_class: type):
        """Register an analyzer"""
        cls._analyzers[name] = analyzer_class

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[TaintAnalyzer]:
        """Create an analyzer instance"""
        analyzer_class = cls._analyzers.get(name)
        if analyzer_class:
            return analyzer_class(**kwargs)
        return None

    @classmethod
    def list_available(cls) -> List[str]:
        """List all available analyzers"""
        available = []
        for name, analyzer_class in cls._analyzers.items():
            try:
                analyzer = analyzer_class()
                if analyzer.is_available():
                    available.append(name)
            except Exception as e:
                save_exception(
                    e, module="haijunbot_sec.taint_analyzer", function="list_available"
                )
                pass
        return available


# ============================================================================
# Helper functions
# ============================================================================


def analyze_with_best_analyzer(
    code: str,
    rules: Optional[List[str]] = None,
    file_path: str = "",
    database: Optional[Any] = None,
) -> List[TaintPath]:
    """
    Analyze using the best available analyzer

    Args:
        code: Source code
        rules: List of rule names to check (None means all rules)
        file_path: File path
        database: Project database instance (optional, passed to the builtin analyzer)

    Returns:
        List of taint paths
    """
    # Get the available analyzers
    available = TaintAnalyzerFactory.list_available()
    if not available:
        return []

    # Select the first available analyzer, passing the database parameter
    analyzer = TaintAnalyzerFactory.create(available[0], database=database)
    if not analyzer:
        return []

    # Get the rules to check
    if rules:
        rule_objects = [get_rule(r) for r in rules if get_rule(r)]
    else:
        rule_objects = get_all_rules()

    # Execute the checks
    all_paths = []
    for rule in rule_objects:
        if rule:  # Ensure the rule is not None
            paths = rule.check(analyzer, code, file_path)
            all_paths.extend(paths)

    return all_paths