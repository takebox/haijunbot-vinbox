"""Language support implementation module.

Contains support implementations for various programming languages.
"""

# Import all language support classes so they are automatically registered
# Use try-except so that a failure to import one language support does not affect the others

from .python_language import PythonLanguageSupport

__all__ = ["PythonLanguageSupport"]

# Attempt to import the tree-sitter related language support
try:
    from .rust_language import RustLanguageSupport  # noqa: F401

    __all__.append("RustLanguageSupport")
except (ImportError, RuntimeError):
    pass

try:
    from .go_language import GoLanguageSupport  # noqa: F401

    __all__.append("GoLanguageSupport")
except (ImportError, RuntimeError):
    pass

try:
    from .c_cpp_language import CLanguageSupport  # noqa: F401
    from .c_cpp_language import CppLanguageSupport  # noqa: F401

    __all__.extend(["CLanguageSupport", "CppLanguageSupport"])
except (ImportError, RuntimeError):
    pass

try:
    from .javascript_language import JavaScriptLanguageSupport  # noqa: F401

    __all__.append("JavaScriptLanguageSupport")
except (ImportError, RuntimeError):
    pass

try:
    from .typescript_language import TypeScriptLanguageSupport  # noqa: F401

    __all__.append("TypeScriptLanguageSupport")
except (ImportError, RuntimeError):
    pass

try:
    from .java_language import JavaLanguageSupport  # noqa: F401

    __all__.append("JavaLanguageSupport")
except (ImportError, RuntimeError):
    pass
