# -*- coding: utf-8 -*-
"""Unit tests for CaseInsensitiveDict

Tests all functionality of the CaseInsensitiveDict class, including edge cases and exception handling.
"""

import pytest

from haijunbot.haijunbot_utils.collections import CaseInsensitiveDict


class TestCaseInsensitiveDict:
    """Tests for CaseInsensitiveDict class"""

    def test_initialization_empty(self):
        """Test empty dictionary initialization"""
        d = CaseInsensitiveDict()
        assert len(d) == 0
        assert not d

    def test_initialization_with_dict(self):
        """Test initialization with a regular dictionary"""
        data = {"Content-Type": "text/plain", "Accept": "application/json"}
        d = CaseInsensitiveDict(data)
        assert len(d) == 2
        assert d["content-type"] == "text/plain"
        assert d["ACCEPT"] == "application/json"

    def test_initialization_with_case_insensitive_dict(self):
        """Test initialization with another CaseInsensitiveDict"""
        original = CaseInsensitiveDict({"Test-Key": "test-value"})
        copied = CaseInsensitiveDict(original)
        assert copied["test-key"] == "test-value"
        assert copied is not original

    def test_getitem_case_insensitive(self):
        """Test case-insensitive key access"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})
        assert d["content-type"] == "text/plain"
        assert d["Content-Type"] == "text/plain"
        assert d["CONTENT-TYPE"] == "text/plain"
        assert d["Content-type"] == "text/plain"

    def test_setitem_case_insensitive(self):
        """Test case-insensitive key setting"""
        d = CaseInsensitiveDict()
        d["Content-Type"] = "text/plain"
        assert d["content-type"] == "text/plain"
        assert d["CONTENT-TYPE"] == "text/plain"

        # Setting the same key (different case) overwrites the original value
        d["CONTENT-TYPE"] = "application/json"
        assert d["content-type"] == "application/json"
        assert len(d) == 1

    def test_delitem_case_insensitive(self):
        """Test case-insensitive key deletion"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain", "Accept": "json"})
        del d["content-type"]
        assert len(d) == 1
        assert "Content-Type" not in d
        assert "Accept" in d

        # Test deleting non-existent key
        with pytest.raises(KeyError):
            del d["non-existent-key"]

    def test_contains_case_insensitive(self):
        """Test case-insensitive key existence check"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})
        assert "content-type" in d
        assert "Content-Type" in d
        assert "CONTENT-TYPE" in d
        assert "non-existent" not in d

        # Test non-string keys
        assert 123 not in d
        assert None not in d

    def test_iteration(self):
        """Test iteration"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain", "Accept": "json"})
        keys = list(d.keys())
        assert "Content-Type" in keys
        assert "Accept" in keys
        assert len(keys) == 2

    def test_len_and_bool(self):
        """Test length and boolean value check"""
        d = CaseInsensitiveDict()
        assert len(d) == 0
        assert not d

        d["key"] = "value"
        assert len(d) == 1
        assert d

    def test_repr(self):
        """Test string representation"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})
        repr_str = repr(d)
        assert "CaseInsensitiveDict" in repr_str
        assert "Content-Type" in repr_str
        assert "text/plain" in repr_str

    def test_equality(self):
        """Test equality comparison"""
        d1 = CaseInsensitiveDict({"Content-Type": "text/plain"})
        d2 = CaseInsensitiveDict({"content-type": "text/plain"})
        d3 = CaseInsensitiveDict({"Content-Type": "application/json"})

        assert d1 == d2
        assert d1 != d3
        assert d1 != "not a dict"

    def test_copy(self):
        """Test copy functionality"""
        original = CaseInsensitiveDict({"key": "value"})
        copied = original.copy()

        assert copied == original
        assert copied is not original

        # Verify modifications to the copy do not affect the original
        copied["new-key"] = "new-value"
        assert len(copied) == 2
        assert len(original) == 1

    def test_get_method(self):
        """Test get method"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})

        assert d.get("content-type") == "text/plain"
        assert d.get("non-existent") is None
        assert d.get("non-existent", "default") == "default"

    def test_pop_method(self):
        """Test pop method"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain", "Accept": "json"})

        value = d.pop("content-type")
        assert value == "text/plain"
        assert len(d) == 1

        # Test default value
        default_value = d.pop("non-existent", "default")
        assert default_value == "default"

        # Test key does not exist and no default value
        with pytest.raises(KeyError):
            d.pop("non-existent")

    def test_popitem_method(self):
        """Test popitem method"""
        d = CaseInsensitiveDict({"key1": "value1", "key2": "value2"})

        original_len = len(d)
        key, value = d.popitem()
        assert len(d) == original_len - 1
        assert key in ["key1", "key2"]
        assert value in ["value1", "value2"]

        # Test empty dictionary
        empty = CaseInsensitiveDict()
        with pytest.raises(KeyError):
            empty.popitem()

    def test_setdefault_method(self):
        """Test setdefault method"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})

        # Key already exists
        value = d.setdefault("content-type", "new-value")
        assert value == "text/plain"
        assert d["Content-Type"] == "text/plain"
        assert len(d) == 1

        # Key does not exist
        new_value = d.setdefault("New-Key", "new-value")
        assert new_value == "new-value"
        assert d["new-key"] == "new-value"
        assert len(d) == 2

    def test_update_method(self):
        """Test update method"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain"})

        # Update using dictionary
        d.update({"Accept": "application/json"})
        assert d["accept"] == "application/json"
        assert len(d) == 2

        # Update using keyword arguments
        d.update(User_Agent="Mozilla/5.0")
        assert d["user-agent"] == "Mozilla/5.0"
        assert len(d) == 3

        # Update using iterable
        d.update([("cache-control", "no-cache")])
        assert d["cache-control"] == "no-cache"
        assert len(d) == 4

        # Test overwriting existing key
        d.update({"content-type": "application/xml"})
        assert d["Content-Type"] == "application/xml"
        assert len(d) == 4

    def test_clear_method(self):
        """Test clear method"""
        d = CaseInsensitiveDict({"key1": "value1", "key2": "value2"})
        assert len(d) == 2

        d.clear()
        assert len(d) == 0
        assert not d

    def test_lower_keys_method(self):
        """Test lower_keys method"""
        d = CaseInsensitiveDict({"Content-Type": "text/plain", "Accept": "json"})
        lower_keys = list(d.lower_keys())
        assert "content-type" in lower_keys
        assert "accept" in lower_keys
        assert len(lower_keys) == 2

    def test_error_handling(self):
        """Test error handling"""
        d = CaseInsensitiveDict({"key": "value"})

        # Test non-string keys
        with pytest.raises(TypeError, match="Key must be a string type"):
            d[123] = "value"

        with pytest.raises(TypeError, match="Key must be a string type"):
            d[None] = "value"

        with pytest.raises(TypeError, match="Key must be a string type"):
            del d[123]

        with pytest.raises(TypeError, match="Key must be a string type"):
            d.get(123)

        with pytest.raises(TypeError, match="Key must be a string type"):
            d.pop(123)

    def test_edge_cases(self):
        """Test edge cases"""
        # Empty string key
        d = CaseInsensitiveDict({"": "empty"})
        assert d[""] == "empty"
        assert d[""] == "empty"

        # Special character key
        d = CaseInsensitiveDict({"Content-Type-With-Dashes": "value"})
        assert d["content-type-with-dashes"] == "value"

        # Mixed case alphanumeric key
        d = CaseInsensitiveDict({"API-Key-123": "value"})
        assert d["api-key-123"] == "value"
        assert d["API-KEY-123"] == "value"

    def test_nested_dict_behavior(self):
        """Test nested dictionary behavior"""
        d = CaseInsensitiveDict(
            {
                "headers": CaseInsensitiveDict({"Content-Type": "text/plain"}),
                "config": CaseInsensitiveDict({"timeout": 30}),
            }
        )

        assert isinstance(d["headers"], CaseInsensitiveDict)
        assert d["headers"]["content-type"] == "text/plain"

    def test_with_python_dict_conversion(self):
        """Test conversion with Python dictionary"""
        original = {"Content-Type": "text/plain", "ACCEPT": "json"}
        case_insensitive = CaseInsensitiveDict(original)

        # Convert to regular dictionary
        converted = dict(case_insensitive)
        assert "Content-Type" in converted or "content-type" in converted
        assert len(converted) == 2

    def test_key_order_preservation(self):
        """Test key order preservation"""
        # Key order provided at creation should be preserved
        original = CaseInsensitiveDict(
            {"Z-Last": "last", "A-First": "first", "M-Middle": "middle"}
        )

        keys = list(original.keys())
        assert keys == ["Z-Last", "A-First", "M-Middle"]

        # Update should not change original key order
        original["z-last"] = "updated"
        keys = list(original.keys())
        assert keys == ["Z-Last", "A-First", "M-Middle"]


class TestCaseInsensitiveDictIntegration:
    """Test CaseInsensitiveDict integration usage scenarios"""

    def test_config_usage_simulation(self):
        """Simulate configuration file usage scenario"""
        config = CaseInsensitiveDict(
            {
                "DATABASE_URL": "postgresql://localhost:5432/mydb",
                "API_KEY": "secret123",
                "TIMEOUT": 30,
                "DEBUG": True,
            }
        )

        # Access with various cases should all work
        assert config["database_url"] == "postgresql://localhost:5432/mydb"
        assert config["API_KEY"] == "secret123"
        assert config["timeout"] == 30
        assert config["debug"] is True

        # Update config
        config["timeout"] = 60
        assert config["TIMEOUT"] == 60
        assert len(config) == 4

    def test_http_headers_simulation(self):
        """Simulate HTTP headers usage scenario"""
        headers = CaseInsensitiveDict(
            {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0",
                "Authorization": "Bearer token123",
            }
        )

        # HTTP clients typically use header names with different cases
        assert headers["content-type"] == "application/json"
        assert headers["USER-AGENT"] == "Mozilla/5.0"
        assert headers["authorization"] == "Bearer token123"

        # Add new header
        headers["Accept"] = "application/json"
        assert headers["ACCEPT"] == "application/json"

    def test_environment_variables_simulation(self):
        """Simulate environment variable usage scenario"""
        env = CaseInsensitiveDict(
            {
                "PATH": "/usr/local/bin:/usr/bin",
                "HOME": "/home/user",
                "USER": "username",
            }
        )

        # Environment variables are typically case-insensitive
        assert env["path"] == "/usr/local/bin:/usr/bin"
        assert env["HOME"] == "/home/user"
        assert env["user"] == "username"


if __name__ == "__main__":
    pytest.main([__file__])
