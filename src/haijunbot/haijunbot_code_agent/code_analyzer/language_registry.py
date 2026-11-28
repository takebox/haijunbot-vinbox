"""Language registry.

Manages the registration and discovery mechanism for all language support.
"""

from haijunbot.haijunbot_utils.output import PrettyOutput

import os
from typing import Dict
from typing import Optional
from typing import Set

from .base_language import BaseLanguageSupport
from .dependency_analyzer import DependencyAnalyzer
from .symbol_extractor import SymbolExtractor


class LanguageRegistry:
    """Language support registry.

    Manages all registered language support and provides language detection and factory methods.
    """

    def __init__(self) -> None:
        self._languages: Dict[str, BaseLanguageSupport] = {}
        self._extension_map: Dict[str, str] = {}  # extension -> language_name

    def register(self, language_support: BaseLanguageSupport) -> None:
        """Register a language support.

        Args:
            language_support: the language support instance
        """
        lang_name = language_support.language_name
        self._languages[lang_name] = language_support

        # Register the file extension mapping
        for ext in language_support.file_extensions:
            # If the extension already exists, log a warning but do not overwrite (keep the first one registered)
            if ext in self._extension_map and self._extension_map[ext] != lang_name:
                PrettyOutput.auto_print(
                    f"Warning: Extension {ext} already registered for "
                    f"{self._extension_map[ext]}, ignoring registration for {lang_name}"
                )
            else:
                self._extension_map[ext] = lang_name

    def unregister(self, language_name: str) -> None:
        """Unregister a language support.

        Args:
            language_name: the language name
        """
        if language_name in self._languages:
            self._languages.pop(language_name)
            # Remove the extension mapping
            extensions_to_remove = [
                ext
                for ext, lang in self._extension_map.items()
                if lang == language_name
            ]
            for ext in extensions_to_remove:
                del self._extension_map[ext]

    def detect_language(self, file_path: str) -> Optional[str]:
        """Detect the programming language based on the file path.

        Args:
            file_path: the file path

        Returns:
            The language name, or None if it cannot be detected
        """
        _, ext = os.path.splitext(file_path)
        return self._extension_map.get(ext)

    def get_language_support(self, language_name: str) -> Optional[BaseLanguageSupport]:
        """Get the support instance for the given language.

        Args:
            language_name: the language name

        Returns:
            The language support instance, or None if it is not registered
        """
        return self._languages.get(language_name)

    def get_symbol_extractor(self, language_name: str) -> Optional[SymbolExtractor]:
        """Get the symbol extractor for the given language.

        Args:
            language_name: the language name

        Returns:
            A SymbolExtractor instance, or None if not supported
        """
        lang_support = self.get_language_support(language_name)
        if lang_support:
            return lang_support.create_symbol_extractor()
        return None

    def get_dependency_analyzer(
        self, language_name: str
    ) -> Optional[DependencyAnalyzer]:
        """Get the dependency analyzer for the given language.

        Args:
            language_name: the language name

        Returns:
            A DependencyAnalyzer instance, or None if not supported
        """
        lang_support = self.get_language_support(language_name)
        if lang_support:
            return lang_support.create_dependency_analyzer()
        return None

    def get_supported_languages(self) -> Set[str]:
        """Get the set of all registered language names.

        Returns:
            The set of language names
        """
        return set(self._languages.keys())

    def is_supported(self, file_path: str) -> bool:
        """Check whether the file is supported.

        Args:
            file_path: the file path

        Returns:
            True if the file is supported, otherwise False
        """
        return self.detect_language(file_path) is not None


# Global registry instance
_registry = LanguageRegistry()


def get_registry() -> LanguageRegistry:
    """Get the global language registry instance.

    Returns:
        The global LanguageRegistry instance
    """
    return _registry


def register_language(language_support: BaseLanguageSupport) -> None:
    """Register a language support (convenience function).

    Args:
        language_support: the language support instance
    """
    _registry.register(language_support)


def detect_language(file_path: str) -> Optional[str]:
    """Detect the language of the file (convenience function).

    Args:
        file_path: the file path

    Returns:
        The language name, or None if it cannot be detected
    """
    return _registry.detect_language(file_path)


def get_symbol_extractor(language: str) -> Optional[SymbolExtractor]:
    """Get the symbol extractor for the given language (convenience function).

    Args:
        language: the language name

    Returns:
        A SymbolExtractor instance, or None if not supported
    """
    return _registry.get_symbol_extractor(language)


def get_dependency_analyzer(language: str) -> Optional[DependencyAnalyzer]:
    """Get the dependency analyzer for the given language (convenience function).

    Args:
        language: the language name

    Returns:
        A DependencyAnalyzer instance, or None if not supported
    """
    return _registry.get_dependency_analyzer(language)
