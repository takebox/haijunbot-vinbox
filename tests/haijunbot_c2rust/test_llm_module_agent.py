# -*- coding: utf-8 -*-
"""haijunbot_c2rust.llm_module_agent module unit tests"""

from haijunbot.haijunbot_c2rust.llm_module_agent_types import sanitize_mod_name


class TestSanitizeModName:
    """Test sanitize_mod_name function"""

    def test_simple_name(self):
        """Test simple name"""
        result = sanitize_mod_name("test")
        assert result == "test"

    def test_name_with_colons(self):
        """Test name with double colons"""
        result = sanitize_mod_name("test::module::name")
        assert result == "test__module__name"

    def test_name_with_special_chars(self):
        """Test name with special characters"""
        result = sanitize_mod_name("test-module@name")
        assert result == "test_module_name"

    def test_name_with_spaces(self):
        """Test name with spaces"""
        result = sanitize_mod_name("test module name")
        assert result == "test_module_name"

    def test_uppercase_name(self):
        """Test uppercase name (should convert to lowercase)"""
        result = sanitize_mod_name("TEST_MODULE")
        assert result == "test_module"

    def test_mixed_case_name(self):
        """Test mixed case name"""
        result = sanitize_mod_name("TestModuleName")
        assert result == "testmodulename"

    def test_name_with_numbers(self):
        """Test name with numbers"""
        result = sanitize_mod_name("test123module")
        assert result == "test123module"

    def test_name_with_leading_underscores(self):
        """Test leading underscores (should be removed)"""
        result = sanitize_mod_name("___test")
        assert result == "test"

    def test_name_with_trailing_underscores(self):
        """Test trailing underscores (should be removed)"""
        result = sanitize_mod_name("test___")
        assert result == "test"

    def test_name_with_both_underscores(self):
        """Test underscores on both sides"""
        result = sanitize_mod_name("___test___")
        assert result == "test"

    def test_empty_string(self):
        """Test empty string (should return 'mod')"""
        result = sanitize_mod_name("")
        assert result == "mod"

    def test_none(self):
        """Test None (should return 'mod')"""
        result = sanitize_mod_name(None)
        assert result == "mod"

    def test_long_name(self):
        """Test overly long name (should truncate to 80 characters)"""
        long_name = "a" * 100
        result = sanitize_mod_name(long_name)
        assert len(result) == 80
        assert result == "a" * 80

    def test_long_name_with_special_chars(self):
        """Test overly long name with special characters"""
        long_name = "test-" * 30  # 150 characters
        result = sanitize_mod_name(long_name)
        assert len(result) <= 80
        # Special characters are replaced with underscores, so result is test_test_test_...
        assert result.startswith("test")

    def test_only_special_chars(self):
        """Test only special characters (should return 'mod')"""
        result = sanitize_mod_name("---")
        assert result == "mod"

    def test_only_underscores(self):
        """Test only underscores (should return 'mod')"""
        result = sanitize_mod_name("___")
        assert result == "mod"

    def test_complex_name(self):
        """Test complex name"""
        result = sanitize_mod_name("MyModule::SubModule::Function123")
        assert result == "mymodule__submodule__function123"

    def test_name_with_unicode(self):
        """Test name with Unicode characters"""
        result = sanitize_mod_name("test module")
        # Unicode characters' isalnum() returns True, so they are preserved and converted to lowercase
        # If all characters are Unicode, the result may be preserved as-is or become "mod"
        assert isinstance(result, str)
        assert len(result) > 0
