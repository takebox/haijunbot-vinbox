"""Base language support abstract class.

Defines the interfaces that all language supports need to implement, to facilitate extending new language support.
"""

from abc import ABC
from abc import abstractmethod
from typing import Optional
from typing import Set

from .dependency_analyzer import DependencyAnalyzer
from .symbol_extractor import SymbolExtractor


class BaseLanguageSupport(ABC):
    """Base abstract class for language support.

    All language support classes should inherit from this class and implement the required methods.
    """

    @property
    @abstractmethod
    def language_name(self) -> str:
        """Return the language name (e.g. 'python', 'rust', 'go')."""
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> Set[str]:
        """Return the set of file extensions supported by this language (e.g. {'.py', '.pyw'})."""
        pass

    @abstractmethod
    def create_symbol_extractor(self) -> Optional[SymbolExtractor]:
        """Create and return a symbol extractor instance for this language.

        Returns:
            A SymbolExtractor instance, or None if symbol extraction is not supported
        """
        pass

    @abstractmethod
    def create_dependency_analyzer(self) -> Optional[DependencyAnalyzer]:
        """Create and return a dependency analyzer instance for this language.

        Returns:
            A DependencyAnalyzer instance, or None if dependency analysis is not supported
        """
        pass

    def is_source_file(self, file_path: str) -> bool:
        """Check whether a file is a source file of this language.

        Args:
            file_path: file path

        Returns:
            True if it is a source file of this language, otherwise False
        """
        import os

        _, ext = os.path.splitext(file_path)
        return ext in self.file_extensions

    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect whether a file belongs to this language.

        Args:
            file_path: file path

        Returns:
            Returns language_name if it belongs to this language, otherwise None
        """
        if self.is_source_file(file_path):
            return self.language_name
        return None
