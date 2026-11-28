"""Dependency analyzer base module.

Provides the base classes and interfaces for dependency analysis; language-specific implementations should be in their respective language support modules.
"""

import os
from dataclasses import dataclass
from typing import Dict
from typing import List
from typing import Optional
from typing import Set

from haijunbot.haijunbot_utils.config import read_text_file

from .file_ignore import filter_walk_dirs


@dataclass
class Dependency:
    """Represents an import dependency."""

    from_module: str
    imported_symbol: Optional[str] = None  # None means import entire module
    file_path: str = ""
    line: int = 0


class DependencyGraph:
    """Represents the dependency graph of a project."""

    def __init__(self) -> None:
        # file_path -> set of file_paths it depends on
        self.dependencies: Dict[str, Set[str]] = {}
        # file_path -> set of file_paths that depend on it
        self.dependents: Dict[str, Set[str]] = {}

    def add_dependency(self, file_path: str, dependency_path: str) -> None:
        """Adds a dependency from file_path to dependency_path."""
        if file_path not in self.dependencies:
            self.dependencies[file_path] = set()
        self.dependencies[file_path].add(dependency_path)

        if dependency_path not in self.dependents:
            self.dependents[dependency_path] = set()
        self.dependents[dependency_path].add(file_path)

    def get_dependencies(self, file_path: str) -> List[str]:
        """Gets the list of files that file_path depends on."""
        return list(self.dependencies.get(file_path, set()))

    def get_dependents(self, file_path: str) -> List[str]:
        """Gets the list of files that depend on file_path."""
        return list(self.dependents.get(file_path, set()))

    def clear_file_dependencies(self, file_path: str) -> None:
        """Removes all dependency information for a specific file."""
        if file_path in self.dependencies:
            # Remove this file's dependencies on others
            deps_to_remove = self.dependencies.pop(file_path)
            for dep in deps_to_remove:
                if dep in self.dependents and file_path in self.dependents[dep]:
                    self.dependents[dep].remove(file_path)
                    if not self.dependents[dep]:
                        del self.dependents[dep]

        # Remove other files' dependencies on this file
        if file_path in self.dependents:
            dependents_to_remove = self.dependents.pop(file_path)
            for dep_file in dependents_to_remove:
                if (
                    dep_file in self.dependencies
                    and file_path in self.dependencies[dep_file]
                ):
                    self.dependencies[dep_file].remove(file_path)
                    if not self.dependencies[dep_file]:
                        del self.dependencies[dep_file]


class DependencyAnalyzer:
    """Analyzes import dependencies in a source code file.

    This is the base class of the dependency analyzer; language-specific implementations should be in their respective language support modules.
    For example: PythonDependencyAnalyzer is in languages/python_language.py.
    """

    def analyze_imports(self, file_path: str, content: str) -> List[Dependency]:
        """
        Analyzes the import statements in the code.
        This method should be implemented by language-specific subclasses.

        Args:
            file_path: file path
            content: file content

        Returns:
            The list of dependencies
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def build_dependency_graph(self, project_root: str) -> DependencyGraph:
        """
        Builds a dependency graph for the entire project.
        This would involve iterating over all source files.

        Args:
            project_root: project root directory

        Returns:
            The dependency graph
        """
        graph = DependencyGraph()

        # Walk through all source files in the project
        for root, dirs, files in os.walk(project_root):
            # Skip hidden directories and common ignore patterns
            dirs[:] = filter_walk_dirs(dirs)

            for file in files:
                file_path = os.path.join(root, file)
                if not self._is_source_file(file_path):
                    continue

                try:
                    content = read_text_file(file_path, errors="replace")
                    dependencies = self.analyze_imports(file_path, content)
                    for dep in dependencies:
                        # Resolve dependency path (this should be done by language-specific analyzer)
                        # For now, we'll just store the module name
                        pass
                except Exception:
                    # Skip files that can't be read or parsed
                    continue

        return graph

    def _is_source_file(self, file_path: str) -> bool:
        """Check if a file is a source file that should be analyzed.

        This should be overridden by subclasses.
        """
        return False
