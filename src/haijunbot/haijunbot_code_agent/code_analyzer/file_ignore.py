"""File ignore utility module.

Provides unified file/directory ignore logic for code analysis, dependency analysis, and other scenarios.
"""

from pathlib import Path
from typing import Callable
from typing import List
from typing import Optional
from typing import Set


class FileIgnorePatterns:
    """File ignore pattern collection.

    Defines various common file and directory patterns that need to be ignored.
    """

    # Hidden directories/files (starting with .)
    HIDDEN_PATTERNS: Set[str] = {".git", ".svn", ".hg", ".bzr"}

    # Version control directories
    VCS_DIRS: Set[str] = {".git", ".svn", ".hg", ".bzr", ".gitignore"}

    # Python related
    PYTHON_DIRS: Set[str] = {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".coverage",
        "htmlcov",
        ".hypothesis",
        ".ipynb_checkpoints",
        ".pyre",
        ".pytype",
        "develop-eggs",
        "downloads",
        "eggs",
        ".eggs",
        "lib",
        "lib64",
        "parts",
        "sdist",
        "var",
        "wheels",
        "pip-wheel-metadata",
        "share",
        "*.egg-info",
        ".installed.cfg",
        "MANIFEST",
    }
    PYTHON_VENV_DIRS: Set[str] = {"venv", "env", ".venv", "virtualenv", "ENV"}

    # Rust related
    RUST_DIRS: Set[str] = {"target"}

    # Go related
    GO_DIRS: Set[str] = {"vendor", "bin", "coverage.out"}

    # Node.js related
    NODE_DIRS: Set[str] = {
        "node_modules",
        ".npm",
        ".yarn",
        ".pnpm",
        ".turbo",
        ".next",
        ".nuxt",
        "out",
        "dist",
        "coverage",
        "build",
    }

    # Java related
    JAVA_DIRS: Set[str] = {"target", ".gradle", "build", "out", "*.class"}

    # C/C++ related
    C_CPP_DIRS: Set[str] = {
        "build",
        "cmake-build-*",
        "out",
        "bin",
        "obj",
        "*.o",
        "*.a",
        "*.so",
        "*.obj",
        "*.dll",
        "*.dylib",
        "*.exe",
        "*.pdb",
    }

    # .NET related
    DOTNET_DIRS: Set[str] = {"bin", "obj", "packages"}

    # Build output directories (general)
    BUILD_DIRS: Set[str] = {
        "build",
        "out",
        "target",
        "dist",
        "bin",
        "obj",
        "cmake-build-*",
    }

    # Dependency directories (general)
    DEPENDENCY_DIRS: Set[str] = {
        "third_party",
        "vendor",
        "deps",
        "dependencies",
        "libs",
        "libraries",
        "external",
        "node_modules",
        "packages",
    }

    # Test directories
    TEST_DIRS: Set[str] = {
        "test",
        "tests",
        "__tests__",
        "spec",
        "testsuite",
        "testdata",
        "test_data",
        "testdata",
        "fixtures",
        "mocks",
    }

    # Performance test directories
    BENCHMARK_DIRS: Set[str] = {
        "benchmark",
        "benchmarks",
        "perf",
        "performance",
        "bench",
        "benches",
        "profiling",
        "profiler",
    }

    # Example directories
    EXAMPLE_DIRS: Set[str] = {
        "example",
        "examples",
        "samples",
        "sample",
        "demo",
        "demos",
    }

    # Temporary/cache directories
    TEMP_DIRS: Set[str] = {
        "tmp",
        "temp",
        "cache",
        ".cache",
        "*.tmp",
        "*.log",
        "*.swp",
        "*.swo",
    }

    # Documentation directories
    DOC_DIRS: Set[str] = {"docs", "doc", "documentation"}

    # Generated code directories
    GENERATED_DIRS: Set[str] = {"generated", "gen", "auto-generated"}

    # Others
    OTHER_DIRS: Set[str] = {
        "playground",
        "sandbox",
        ".idea",
        ".vscode",
        ".DS_Store",
        "Thumbs.db",
    }

    # HaijunBot specific
    dirs: Set[str] = {".haijunbot"}

    @classmethod
    def get_all_ignore_dirs(cls) -> Set[str]:
        """Get the set of all directory names that need to be ignored.

        Returns:
            The set of all ignored directory names
        """
        return (
            cls.VCS_DIRS
            | cls.PYTHON_DIRS
            | cls.PYTHON_VENV_DIRS
            | cls.RUST_DIRS
            | cls.GO_DIRS
            | cls.NODE_DIRS
            | cls.JAVA_DIRS
            | cls.C_CPP_DIRS
            | cls.DOTNET_DIRS
            | cls.BUILD_DIRS
            | cls.DEPENDENCY_DIRS
            | cls.TEST_DIRS
            | cls.BENCHMARK_DIRS
            | cls.EXAMPLE_DIRS
            | cls.TEMP_DIRS
            | cls.DOC_DIRS
            | cls.GENERATED_DIRS
            | cls.OTHER_DIRS
            | cls.dirs
        )

    @classmethod
    def get_code_analysis_ignore_dirs(cls) -> Set[str]:
        """Get the directories that should be ignored in code analysis (excluding test directories).

        Returns:
            The set of directories ignored in code analysis
        """
        return (
            cls.VCS_DIRS
            | cls.PYTHON_DIRS
            | cls.PYTHON_VENV_DIRS
            | cls.RUST_DIRS
            | cls.GO_DIRS
            | cls.NODE_DIRS
            | cls.JAVA_DIRS
            | cls.C_CPP_DIRS
            | cls.DOTNET_DIRS
            | cls.BUILD_DIRS
            | cls.DEPENDENCY_DIRS
            | cls.BENCHMARK_DIRS
            | cls.EXAMPLE_DIRS
            | cls.TEMP_DIRS
            | cls.DOC_DIRS
            | cls.GENERATED_DIRS
            | cls.OTHER_DIRS
            | cls.dirs
        )

    @classmethod
    def get_dependency_analysis_ignore_dirs(cls) -> Set[str]:
        """Get the directories that should be ignored in dependency analysis.

        Returns:
            The set of directories ignored in dependency analysis
        """
        return (
            cls.VCS_DIRS
            | cls.BUILD_DIRS
            | cls.DEPENDENCY_DIRS
            | cls.TEST_DIRS
            | cls.BENCHMARK_DIRS
            | cls.EXAMPLE_DIRS
            | cls.TEMP_DIRS
            | cls.DOC_DIRS
            | cls.GENERATED_DIRS
            | cls.OTHER_DIRS
            | cls.dirs
        )


class FileIgnoreFilter:
    """File ignore filter.

    Provides unified file/directory filtering logic.
    """

    def __init__(
        self,
        ignore_dirs: Optional[Set[str]] = None,
        ignore_hidden: bool = True,
        custom_filter: Optional[Callable[[str], bool]] = None,
    ):
        """Initialize the file ignore filter.

        Args:
            ignore_dirs: the set of directory names to ignore, or the default set if None
            ignore_hidden: whether to ignore hidden directories (starting with .)
            custom_filter: custom filter function, receives a directory name and returns True to ignore
        """
        if ignore_dirs is None:
            ignore_dirs = FileIgnorePatterns.get_code_analysis_ignore_dirs()

        self.ignore_dirs = ignore_dirs
        self.ignore_hidden = ignore_hidden
        self.custom_filter = custom_filter

    def should_ignore_dir(self, dir_name: str) -> bool:
        """Determine whether a directory should be ignored.

        Args:
            dir_name: directory name (without path)

        Returns:
            True if it should be ignored, otherwise False
        """
        # Check hidden directories
        if self.ignore_hidden and dir_name.startswith("."):
            return True

        # Check the ignored directory set
        if dir_name in self.ignore_dirs:
            return True

        # Check the custom filter
        if self.custom_filter and self.custom_filter(dir_name):
            return True

        return False

    def should_ignore_path(self, path: str) -> bool:
        """Determine whether a path (file or directory) should be ignored.

        Args:
            path: file or directory path

        Returns:
            True if it should be ignored, otherwise False
        """
        path_obj = Path(path)

        # Check whether any part of the path should be ignored
        for part in path_obj.parts:
            if self.should_ignore_dir(part):
                return True

        return False

    def filter_dirs(self, dirs: List[str]) -> List[str]:
        """Filter a directory list, removing directories that should be ignored.

        This method can be used directly to modify the dirs list of os.walk:
        dirs[:] = filter.filter_dirs(dirs)

        Args:
            dirs: the list of directory names

        Returns:
            The filtered directory list
        """
        return [d for d in dirs if not self.should_ignore_dir(d)]

    def filter_paths(self, paths: List[str]) -> List[str]:
        """Filter a path list, removing paths that should be ignored.

        Args:
            paths: the list of paths

        Returns:
            The filtered path list
        """
        return [p for p in paths if not self.should_ignore_path(p)]


# Predefined filter instances
DEFAULT_FILTER = FileIgnoreFilter()
CODE_ANALYSIS_FILTER = FileIgnoreFilter(
    ignore_dirs=FileIgnorePatterns.get_code_analysis_ignore_dirs()
)
DEPENDENCY_ANALYSIS_FILTER = FileIgnoreFilter(
    ignore_dirs=FileIgnorePatterns.get_dependency_analysis_ignore_dirs()
)
ALL_IGNORE_FILTER = FileIgnoreFilter(
    ignore_dirs=FileIgnorePatterns.get_all_ignore_dirs()
)


def should_ignore_dir(dir_name: str, ignore_dirs: Optional[Set[str]] = None) -> bool:
    """Convenience function: determine whether a directory should be ignored.

    Args:
        dir_name: directory name
        ignore_dirs: the set of ignored directories, or the default set if None

    Returns:
        True if it should be ignored
    """
    if ignore_dirs is None:
        ignore_dirs = FileIgnorePatterns.get_code_analysis_ignore_dirs()

    # Hidden directories
    if dir_name.startswith("."):
        return True

    # The ignored directory set
    return dir_name in ignore_dirs


def filter_walk_dirs(
    dirs: List[str], ignore_dirs: Optional[Set[str]] = None
) -> List[str]:
    """Convenience function: filter the dirs list of os.walk.

    Usage:
        for root, dirs, files in os.walk(path):
            dirs[:] = filter_walk_dirs(dirs)

    Args:
        dirs: the directory list returned by os.walk
        ignore_dirs: the set of ignored directories, or the default set if None

    Returns:
        The filtered directory list
    """
    if ignore_dirs is None:
        ignore_dirs = FileIgnorePatterns.get_code_analysis_ignore_dirs()

    return [d for d in dirs if not (d.startswith(".") or d in ignore_dirs)]
