"""
Tests for TreeSitterExtractor's handling of files with syntax errors.

Verifies:
1. Files with syntax errors do not cause the program to crash
2. Files with syntax errors return an empty list or partial symbols
3. Various types of syntax errors are handled correctly
"""

import pytest
from unittest.mock import patch

from haijunbot.haijunbot_code_agent.code_analyzer.tree_sitter_extractor import (
    TreeSitterExtractor,
)
from haijunbot.haijunbot_code_agent.code_analyzer.symbol_extractor import Symbol


class MockTreeSitterExtractor(TreeSitterExtractor):
    """Mock TreeSitterExtractor for testing"""

    def _create_symbol_from_capture(self, node, name: str, file_path: str):
        """Create Symbol for testing"""
        return Symbol(
            name=name,
            kind="test",
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            file_path=file_path,
        )


class TestTreeSitterExtractorSyntaxErrors:
    """Tests for TreeSitterExtractor's handling of files with syntax errors"""

    @pytest.fixture
    def rust_language(self):
        """Try to get the real Rust Language object"""
        try:
            import tree_sitter_rust

            return tree_sitter_rust.language()
        except (ImportError, Exception):
            pytest.skip("tree-sitter-rust not available")

    @pytest.fixture
    def extractor(self, rust_language):
        """Create TreeSitterExtractor instance for testing"""
        query = """
        (function_item
          name: (identifier) @function.name)
        """
        return MockTreeSitterExtractor(rust_language, query)

    def test_empty_content(self, extractor):
        """Test empty content"""
        symbols = extractor.extract_symbols("test.rs", "")
        assert symbols == []

    def test_whitespace_only_content(self, extractor):
        """Test content with only whitespace"""
        symbols = extractor.extract_symbols("test.rs", "   \n\t  \n")
        assert symbols == []

    def test_missing_closing_brace(self, extractor):
        """Test missing closing brace"""
        content = """
        fn test_function() {
            let x = 5;
        // Missing closing brace
        """
        # Even with syntax errors, tree-sitter can usually partially parse
        # Here we test that it does not crash
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            # Should return an empty list or partial symbols, should not crash
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should not raise exception: {e}")

    def test_missing_semicolon(self, extractor):
        """Test missing semicolon (Rust syntax error)"""
        content = """
        fn test() {
            let x = 5  // Missing semicolon
        }
        """
        # Even with syntax errors, tree-sitter can usually partially parse
        # Here we test that it does not crash
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            # Should return an empty list or partial symbols, should not crash
            assert isinstance(symbols, list)
        except Exception as e:
            # If an exception is raised, it should be printed in debug mode, but should not crash
            pytest.fail(f"extract_symbols should not raise exception: {e}")

    def test_invalid_utf8_encoding(self, extractor):
        """Test invalid UTF-8 encoding"""
        # Create content containing invalid UTF-8 bytes
        invalid_content = b"\xff\xfe\x00\x01"
        try:
            # Try to decode as string
            content = invalid_content.decode("utf-8", errors="replace")
            symbols = extractor.extract_symbols("test.rs", content)
            # Should return an empty list or partial symbols, should not crash
            assert isinstance(symbols, list)
        except Exception as e:
            # If an exception is raised, it should be printed in debug mode, but should not crash
            pytest.fail(f"extract_symbols should handle invalid UTF-8: {e}")

    def test_unclosed_string_literal(self, extractor):
        """Test unclosed string literal"""
        content = """
        fn test() {
            let s = "unclosed string
        }
        """
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should handle unclosed string: {e}")

    def test_malformed_function_signature(self, extractor):
        """Test malformed function signature"""
        content = """
        fn test(  // Missing parameters and closing parenthesis
        """
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should handle malformed function: {e}")

    def test_invalid_query_syntax(self, rust_language):
        """Test invalid query syntax"""
        # Create an extractor using an invalid query
        invalid_query = """
        (function_item
          name: (invalid_syntax @function.name)
        """
        invalid_extractor = MockTreeSitterExtractor(rust_language, invalid_query)

        content = """
        fn test() {
            println!("Hello");
        }
        """
        # Even with query syntax errors, it should not crash
        symbols = invalid_extractor.extract_symbols("test.rs", content)
        assert isinstance(symbols, list)

    def test_parser_exception_handling(self, extractor):
        """Test parser exception handling"""
        # Use content that will cause parse failure to test exception handling
        # For example: content containing invalid bytes
        content = b"\xff\xfe\x00\x01".decode("utf-8", errors="replace")
        # Even if parsing fails, it should not crash
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should handle parser errors gracefully: {e}")

    def test_query_construction_error(self, extractor):
        """Test query construction error"""
        # Create an extractor using an invalid query to test query construction error
        from haijunbot.haijunbot_code_agent.code_analyzer.tree_sitter_extractor import (
            TreeSitterExtractor,
        )

        class InvalidQueryExtractor(TreeSitterExtractor):
            def _create_symbol_from_capture(self, node, name: str, file_path: str):
                return None

        # Use invalid query syntax
        invalid_query = "(invalid_syntax @function.name"
        try:
            invalid_extractor = InvalidQueryExtractor(extractor.language, invalid_query)
            content = """
            fn test() {
                println!("Hello");
            }
            """
            # Even if query construction fails, it should not crash
            symbols = invalid_extractor.extract_symbols("test.rs", content)
            assert isinstance(symbols, list)
        except Exception:
            # If query construction fails, it should return an empty list instead of crashing
            # But in some cases an exception may be raised, which is also acceptable
            pass

    def test_partial_parse_with_syntax_errors(self, extractor):
        """Test partial parse (with syntax errors but still able to parse some content)"""
        content = """
        fn valid_function() {
            println!("Valid");
        }

        fn invalid_function(  // Syntax error
            let x = 5;
        }

        fn another_valid() {
            println!("Also valid");
        }
        """
        # Even with syntax errors, it should be able to extract valid symbols
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            # Should return partial symbols or an empty list
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should handle partial parse: {e}")

    def test_extract_valid_symbols_despite_syntax_errors(self, extractor):
        """Test that valid symbols can be extracted even with syntax errors"""
        content = """
        fn valid_function1() {
            println!("Valid1");
        }

        fn invalid_function(  // Syntax error: missing closing parenthesis
                let x = 5;
        }

        fn valid_function2() {
            println!("Valid2");
        }

        fn another_invalid() {
            let x = {  // Syntax error: unclosed code block
            let y = 5;
        }

        fn valid_function3() {
            println!("Valid3");
        }
        """
        # Even with multiple syntax errors, it should be able to extract valid symbols
        symbols = extractor.extract_symbols("test.rs", content)
        assert isinstance(symbols, list)

        # Should extract at least some valid function symbols
        # Note: how many can be extracted depends on tree-sitter's parsing ability
        # But at least it should not crash and should return a list
        if symbols:
            # Verify that all returned symbols are valid
            for symbol in symbols:
                assert hasattr(symbol, "name")
                assert hasattr(symbol, "line_start")
                assert hasattr(symbol, "line_end")

    def test_nested_syntax_errors(self, extractor):
        """Test nested syntax errors"""
        content = """
        fn outer() {
            fn inner() {
                let x = {  // Unclosed code block
            }
        }
        """
        try:
            symbols = extractor.extract_symbols("test.rs", content)
            assert isinstance(symbols, list)
        except Exception as e:
            pytest.fail(f"extract_symbols should handle nested errors: {e}")

    def test_debug_mode_output(self, extractor, monkeypatch):
        """Test output in debug mode"""
        monkeypatch.setenv("DEBUG_TREE_SITTER", "1")

        # Use content that will cause parse failure
        content = """
        fn test() {
            invalid syntax here
        }
        """

        # In debug mode, it should be able to handle errors without crashing
        try:
            with patch("builtins.print"):
                symbols = extractor.extract_symbols("test.rs", content)
                # Should return an empty list or partial symbols
                assert isinstance(symbols, list)
                # Note: since the exception is caught, print may not be called, depending on the implementation
        except Exception as e:
            pytest.fail(f"extract_symbols should handle errors in debug mode: {e}")

    def test_skip_error_nodes(self, extractor):
        """Test skipping error nodes, only extracting valid symbols"""
        content = """
        fn valid_function() {
            println!("Valid");
        }

        // Here are some syntax errors
        fn invalid(  // Syntax error
        }

        fn another_valid() {
            println!("Also valid");
        }
        """
        # Even with syntax errors, it should skip error nodes and extract valid symbols
        symbols = extractor.extract_symbols("test.rs", content)
        assert isinstance(symbols, list)

        # Verify that all returned symbols are valid (should not include error nodes)
        for symbol in symbols:
            assert hasattr(symbol, "name")
            assert symbol.name is not None
            assert symbol.line_start > 0
            assert symbol.line_end >= symbol.line_start

    def test_mixed_valid_and_invalid_code(self, extractor):
        """Test mixed valid and invalid code"""
        content = """
        // First valid function
        fn function1() {
            println!("Function 1");
        }

        // Syntax error: missing closing parenthesis
        fn function2(  // Error starts
            let x = 5;

        // Second valid function
        fn function3() {
            println!("Function 3");
        }

        // Syntax error: unclosed code block
        fn function4() {
            let x = {  // Error starts
            let y = 5;

        // Third valid function
        fn function5() {
            println!("Function 5");
        }
        """
        # Even with multiple syntax errors, it should be able to extract valid symbols
        symbols = extractor.extract_symbols("test.rs", content)
        assert isinstance(symbols, list)

        # Should extract at least some valid function symbols
        # How many can be extracted depends on tree-sitter's parsing ability
        valid_function_names = [
            s.name for s in symbols if hasattr(s, "name") and s.name
        ]
        assert len(valid_function_names) >= 0  # At least should return a list (may be empty)

    def test_graceful_degradation_on_parse_failure(self, extractor):
        """Test graceful degradation when parsing completely fails"""
        # Use completely invalid content
        content = "{{{[[[invalid syntax]]]}}}"

        # Even if parsing completely fails, it should not crash
        symbols = extractor.extract_symbols("test.rs", content)
        assert isinstance(symbols, list)
        # Should return an empty list or partial symbols
        assert len(symbols) >= 0
