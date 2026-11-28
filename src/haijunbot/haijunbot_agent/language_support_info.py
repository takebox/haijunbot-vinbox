# -*- coding: utf-8 -*-
"""Language feature support information module

Provides functionality to collect and display language feature support status.
"""

from typing import Any

from haijunbot.haijunbot_utils.exception_utils import save_exception


def _collect_language_support_info() -> dict[str, dict[str, Any]]:
    """Collect the feature support information for all languages"""
    info: dict[str, dict[str, Any]] = {}

    # Ensure the language support module is loaded (triggers automatic registration)
    try:
        pass
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_agent.language_support_info",
            function="_collect_language_support_info",
        )
        pass

    # Get language support from code_analyzer
    try:
        from haijunbot.haijunbot_code_agent.code_analyzer.language_registry import (
            get_registry,
        )

        registry = get_registry()

        for lang_name in registry.get_supported_languages():
            lang_support = registry.get_language_support(lang_name)
            if lang_support:
                if lang_name not in info:
                    info[lang_name] = {}

                # Check symbol extraction support
                try:
                    extractor = lang_support.create_symbol_extractor()
                    info[lang_name]["Symbol Extraction"] = extractor is not None
                except Exception:
                    # If creation fails, mark as False first; the extractor in file_context_handler will be checked later
                    info[lang_name]["Symbol Extraction"] = False

                # Check dependency analysis support
                try:
                    analyzer = lang_support.create_dependency_analyzer()
                    info[lang_name]["Dependency Analysis"] = analyzer is not None
                except Exception:
                    info[lang_name]["Dependency Analysis"] = False

    except Exception as e:
        save_exception(
            e,
            module="haijunbot_agent.language_support_info",
            function="_collect_language_support_info",
        )
        pass

    # Get context extraction support from file_context_handler, also used to supplement symbol extraction support
    try:
        from haijunbot.haijunbot_agent.file_context_handler import _LANGUAGE_EXTRACTORS

        # Mapping from extension to language name
        lang_name_map = {
            ".py": "python",
            ".pyw": "python",
            ".rs": "rust",
            ".go": "go",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hxx": "cpp",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
        }

        for ext, factory in _LANGUAGE_EXTRACTORS.items():
            try:
                # Try to create the extractor; only mark as supported if creation succeeds
                extractor = factory()
                if extractor is not None:
                    lang_name = lang_name_map.get(
                        ext, ext[1:] if ext.startswith(".") else ext
                    )

                    if lang_name not in info:
                        info[lang_name] = {}

                    # Context extraction support (supported only if creation succeeds)
                    info[lang_name]["Context Extraction"] = True

                    # If symbol extraction is not supported in code_analyzer but an extractor can be created successfully in file_context_handler, mark it as supported too
                    if (
                        "Symbol Extraction" not in info[lang_name]
                        or not info[lang_name]["Symbol Extraction"]
                    ):
                        info[lang_name]["Symbol Extraction"] = True
            except Exception:
                # Fail silently without logging the error (to avoid excessive debug output)
                pass
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_agent.language_support_info",
            function="_collect_language_support_info",
        )
        pass

    # Check build validation support (automatically discover all build validators)
    try:
        import haijunbot.haijunbot_code_agent.code_analyzer.build_validator as build_validator_module
        from haijunbot.haijunbot_code_agent.code_analyzer.build_validator import __all__
        from haijunbot.haijunbot_code_agent.code_analyzer.build_validator.base import (
            BuildValidatorBase,
        )

        # Automatically discover all build validator classes (excluding base and utility classes)
        validator_classes = []
        exclude_classes = {
            "BuildValidatorBase",
            "BuildSystemDetector",
            "BuildValidator",
            "BuildSystem",
            "BuildResult",
        }

        for name in __all__:
            if name not in exclude_classes and name.endswith("BuildValidator"):
                try:
                    validator_class = getattr(build_validator_module, name)
                    # Check whether it is a subclass of BuildValidatorBase
                    if (
                        issubclass(validator_class, BuildValidatorBase)
                        and validator_class != BuildValidatorBase
                    ):
                        validator_classes.append(validator_class)
                except (AttributeError, TypeError, Exception):
                    continue

        # Collect the supported build system names for each language
        lang_to_build_systems: dict[str, list[str]] = {}

        for validator_class in validator_classes:
            try:
                # Check whether the class has BUILD_SYSTEM_NAME and SUPPORTED_LANGUAGES
                build_system_name = getattr(validator_class, "BUILD_SYSTEM_NAME", "")
                supported_languages = getattr(
                    validator_class, "SUPPORTED_LANGUAGES", []
                )

                if build_system_name and supported_languages:
                    for lang in supported_languages:
                        if lang not in lang_to_build_systems:
                            lang_to_build_systems[lang] = []
                        if build_system_name not in lang_to_build_systems[lang]:
                            lang_to_build_systems[lang].append(build_system_name)
            except (AttributeError, Exception):
                continue

        # Add the build system information to info
        for lang_name, build_systems in lang_to_build_systems.items():
            if lang_name not in info:
                info[lang_name] = {}
            if build_systems:
                # Store the build system name list (for display)
                info[lang_name]["Build Validation"] = ", ".join(sorted(build_systems))
            else:
                info[lang_name]["Build Validation"] = False

    except (ImportError, Exception):
        pass

    # Check static check support (obtained from lint.py)
    try:
        from haijunbot.haijunbot_code_agent.lint import LINT_COMMAND_TEMPLATES_BY_FILE

        # Mapping from extension to language name
        ext_to_lang_for_lint = {
            ".py": "python",
            ".pyw": "python",
            ".pyi": "python",
            ".rs": "rust",
            ".go": "go",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".hxx": "cpp",
            ".js": "javascript",
            ".jsx": "javascript",
            ".mjs": "javascript",
            ".cjs": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".cts": "typescript",
            ".mts": "typescript",
            ".java": "java",
        }

        # Check whether each language has a corresponding lint tool
        for ext, lang_name in ext_to_lang_for_lint.items():
            if lang_name not in info:
                info[lang_name] = {}
            if (
                ext in LINT_COMMAND_TEMPLATES_BY_FILE
                and LINT_COMMAND_TEMPLATES_BY_FILE.get(ext)
            ):
                info[lang_name]["Static Check"] = True
    except Exception as e:
        save_exception(
            e,
            module="haijunbot_agent.language_support_info",
            function="_collect_language_support_info",
        )
        pass

    # Ensure all known languages are in info (even if some features are unsupported)
    # This way the table shows all languages, even if some features are unsupported
    known_languages = [
        "python",
        "c",
        "cpp",
        "rust",
        "go",
        "javascript",
        "typescript",
        "java",
    ]
    for lang_name in known_languages:
        if lang_name not in info:
            info[lang_name] = {}
        # Ensure all feature fields exist
        for feature in [
            "Symbol Extraction",
            "Dependency Analysis",
            "Context Extraction",
            "Build Validation",
            "Static Check",
        ]:
            if feature not in info[lang_name]:
                # For context extraction, check whether there is a corresponding extractor
                if feature == "Context Extraction":
                    try:
                        from haijunbot.haijunbot_agent.file_context_handler import (
                            _LANGUAGE_EXTRACTORS,
                        )

                        ext_map = {
                            "python": [".py", ".pyw"],
                            "rust": [".rs"],
                            "go": [".go"],
                            "c": [".c", ".h"],
                            "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
                            "javascript": [".js", ".jsx"],
                            "typescript": [".ts", ".tsx"],
                            "java": [".java"],
                        }
                        exts = ext_map.get(lang_name, [])
                        # Try to create the extractor; consider it supported only if creation succeeds (tree-sitter must be installed)
                        has_extractor = False
                        for ext in exts:
                            if ext in _LANGUAGE_EXTRACTORS:
                                try:
                                    factory = _LANGUAGE_EXTRACTORS[ext]
                                    extractor = factory()
                                    if extractor:
                                        has_extractor = True
                                        break
                                except Exception as e:
                                    save_exception(
                                        e,
                                        module="haijunbot_agent.language_support_info",
                                        function="_collect_language_support_info",
                                    )
                                    continue
                        info[lang_name][feature] = has_extractor
                    except Exception:
                        info[lang_name][feature] = False
                elif feature == "Symbol Extraction":
                    # If it was not set before or was False, check the extractor in file_context_handler again
                    # Mark as supported only if the extractor can be created successfully (tree-sitter must be installed)
                    if (
                        "Symbol Extraction" not in info[lang_name]
                        or not info[lang_name]["Symbol Extraction"]
                    ):
                        try:
                            from haijunbot.haijunbot_agent.file_context_handler import (
                                _LANGUAGE_EXTRACTORS,
                            )

                            ext_map = {
                                "python": [".py", ".pyw"],
                                "rust": [".rs"],
                                "go": [".go"],
                                "c": [".c", ".h"],
                                "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
                                "javascript": [".js", ".jsx"],
                                "typescript": [".ts", ".tsx"],
                            }
                            exts = ext_map.get(lang_name, [])
                            # Try to create the extractor; consider it supported only if creation succeeds
                            has_extractor = False
                            for ext in exts:
                                if ext in _LANGUAGE_EXTRACTORS:
                                    try:
                                        factory = _LANGUAGE_EXTRACTORS[ext]
                                        extractor = factory()
                                        if extractor:
                                            has_extractor = True
                                            break
                                    except Exception as e:
                                        save_exception(
                                            e,
                                            module="haijunbot_agent.language_support_info",
                                            function="_collect_language_support_info",
                                        )
                                        continue
                            info[lang_name][feature] = has_extractor
                        except Exception:
                            info[lang_name][feature] = False
                elif feature == "Build Validation":
                    # Defaults to False, already checked above (may be a string or False)
                    if feature not in info[lang_name]:
                        info[lang_name][feature] = False
                elif feature == "Static Check":
                    # Defaults to False, already checked above
                    info[lang_name][feature] = info[lang_name].get(feature, False)
                else:
                    info[lang_name][feature] = False

    # Ensure all known languages are in info (even if some features are unsupported)
    # This way the table shows all languages, even if some features are unsupported
    known_languages = [
        "python",
        "c",
        "cpp",
        "rust",
        "go",
        "javascript",
        "typescript",
        "java",
    ]
    for lang_name in known_languages:
        if lang_name not in info:
            info[lang_name] = {}
        # Ensure all feature fields exist
        for feature in [
            "Symbol Extraction",
            "Dependency Analysis",
            "Context Extraction",
            "Build Validation",
            "Static Check",
        ]:
            if feature not in info[lang_name]:
                # For context extraction, check whether there is a corresponding extractor
                if feature == "Context Extraction":
                    try:
                        from haijunbot.haijunbot_agent.file_context_handler import (
                            _LANGUAGE_EXTRACTORS,
                        )

                        ext_map = {
                            "python": [".py", ".pyw"],
                            "rust": [".rs"],
                            "go": [".go"],
                            "c": [".c", ".h"],
                            "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
                            "javascript": [".js", ".jsx"],
                            "typescript": [".ts", ".tsx"],
                            "java": [".java"],
                        }
                        exts = ext_map.get(lang_name, [])
                        # Try to create the extractor; consider it supported only if creation succeeds (tree-sitter must be installed)
                        has_extractor = False
                        for ext in exts:
                            if ext in _LANGUAGE_EXTRACTORS:
                                try:
                                    factory = _LANGUAGE_EXTRACTORS[ext]
                                    extractor = factory()
                                    if extractor:
                                        has_extractor = True
                                        break
                                except Exception as e:
                                    save_exception(
                                        e,
                                        module="haijunbot_agent.language_support_info",
                                        function="_collect_language_support_info",
                                    )
                                    continue
                        info[lang_name][feature] = has_extractor
                    except Exception:
                        info[lang_name][feature] = False
                elif feature == "Symbol Extraction":
                    # If it was not set before or was False, check the extractor in file_context_handler again
                    # Mark as supported only if the extractor can be created successfully (tree-sitter must be installed)
                    if (
                        "Symbol Extraction" not in info[lang_name]
                        or not info[lang_name]["Symbol Extraction"]
                    ):
                        try:
                            from haijunbot.haijunbot_agent.file_context_handler import (
                                _LANGUAGE_EXTRACTORS,
                            )

                            ext_map = {
                                "python": [".py", ".pyw"],
                                "rust": [".rs"],
                                "go": [".go"],
                                "c": [".c", ".h"],
                                "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hxx"],
                                "javascript": [".js", ".jsx"],
                                "typescript": [".ts", ".tsx"],
                            }
                            exts = ext_map.get(lang_name, [])
                            # Try to create the extractor; consider it supported only if creation succeeds
                            has_extractor = False
                            for ext in exts:
                                if ext in _LANGUAGE_EXTRACTORS:
                                    try:
                                        factory = _LANGUAGE_EXTRACTORS[ext]
                                        extractor = factory()
                                        if extractor:
                                            has_extractor = True
                                            break
                                    except Exception as e:
                                        save_exception(
                                            e,
                                            module="haijunbot_agent.language_support_info",
                                            function="_collect_language_support_info",
                                        )
                                        continue
                            info[lang_name][feature] = has_extractor
                        except Exception:
                            info[lang_name][feature] = False
                elif feature == "Build Validation":
                    # Defaults to False, already checked above (may be a string or False)
                    if feature not in info[lang_name]:
                        info[lang_name][feature] = False
                elif feature == "Static Check":
                    # Defaults to False, already checked above
                    info[lang_name][feature] = info[lang_name].get(feature, False)
                else:
                    info[lang_name][feature] = False

    return info


def print_language_support_table() -> None:
    """Print the language feature support table"""
    from haijunbot.haijunbot_utils.output import PrettyOutput

    info = _collect_language_support_info()

    if not info:
        return

    # Define the feature list
    features = [
        "Symbol Extraction",
        "Dependency Analysis",
        "Context Extraction",
        "Build Validation",
        "Static Check",
    ]

    # Define the language display name mapping
    lang_display_names = {
        "python": "Python",
        "rust": "Rust",
        "go": "Go",
        "c": "C",
        "cpp": "C++",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "java": "Java",
    }

    # Get all languages (in a fixed order, prioritizing C, C++, Rust, Go)
    priority_languages = ["c", "cpp", "rust", "go"]
    other_languages = ["python", "javascript", "typescript", "java"]
    all_languages = priority_languages + [
        lang for lang in other_languages if lang not in priority_languages
    ]
    # Show all known languages, even if some features are unsupported (as long as they are recorded in info)
    languages = [lang for lang in all_languages if lang in info]

    # If there is no language at all, try to show all languages in info
    if not languages:
        languages = list(info.keys())
        # Sort by priority
        languages = sorted(
            languages,
            key=lambda x: (
                0 if x in priority_languages else 1,
                priority_languages.index(x) if x in priority_languages else 999,
                x,
            ),
        )

    if not languages:
        return

    # Build the Markdown table
    md_lines = ["## Programming Language Feature Support", ""]
    md_lines.append("| Language | " + " | ".join(features) + " |")
    md_lines.append("|------|" + "-|" * len(features))

    # Add the language rows
    for lang in languages:
        display_name = lang_display_names.get(lang, lang.capitalize())
        row = [display_name]
        for feature in features:
            supported = info.get(lang, {}).get(feature, False)
            if supported:
                # If it is build validation, show the build system name
                if feature == "Build Validation" and isinstance(supported, str):
                    row.append(f"**{supported}**")
                else:
                    row.append("**✓**")
            else:
                row.append("**✗**")
        md_lines.append("| " + " | ".join(row) + " |")

    # Print the table
    md_table = "\n".join(md_lines)
    PrettyOutput.print_markdown(md_table)
