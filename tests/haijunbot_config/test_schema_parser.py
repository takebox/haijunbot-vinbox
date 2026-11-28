# -*- coding: utf-8 -*-
"""SchemaParser module unit tests"""

import pytest

from haijunbot.haijunbot_config.schema_parser import SchemaParser


class TestSchemaParser:
    """Test SchemaParser class"""

    def test_schema_initialization(self, parser_with_schema):
        """Test Schema initialization"""
        assert parser_with_schema is not None
        assert isinstance(parser_with_schema, SchemaParser)
        assert parser_with_schema.schema_path is not None

    def test_get_title(self, parser_with_schema):
        """Test getting Schema title"""
        title = parser_with_schema.get_title()
        assert title == "Test Configuration"

    def test_get_description(self, parser_with_schema):
        """Test getting Schema description"""
        description = parser_with_schema.get_description()
        assert description == "Configuration Schema for testing"

    def test_get_schema(self, parser_with_schema):
        """Test getting Schema object"""
        schema = parser_with_schema.get_schema()
        assert isinstance(schema, dict)
        assert "title" in schema
        assert "properties" in schema

    def test_get_properties(self, parser_with_schema):
        """Test getting top-level properties"""
        properties = parser_with_schema.get_properties()
        assert isinstance(properties, dict)
        assert "name" in properties
        assert "count" in properties
        assert "enabled" in properties
        assert "tags" in properties
        assert "metadata" in properties

    def test_get_required(self, parser_with_schema):
        """Test getting required properties list"""
        required = parser_with_schema.get_required()
        assert isinstance(required, list)
        assert "name" in required
        assert "count" in required
        assert "enabled" not in required

    def test_get_property_schema(self, parser_with_schema):
        """Test getting property Schema"""
        prop_schema = parser_with_schema.get_property_schema("name")
        assert prop_schema["type"] == "string"
        assert "minLength" in prop_schema

    def test_get_property_schema_not_found(self, parser_with_schema):
        """Test getting nonexistent property Schema"""
        with pytest.raises(ValueError, match="Property 'unknown' not found"):
            parser_with_schema.get_property_schema("unknown")

    def test_get_default_value(self, parser_with_schema):
        """Test getting property default value"""
        assert parser_with_schema.get_default_value("name") == "test"
        assert parser_with_schema.get_default_value("count") == 1
        assert parser_with_schema.get_default_value("enabled") is True
        assert parser_with_schema.get_default_value("tags") == []

    def test_get_default_value_not_exist(self, parser_with_schema):
        """Test getting nonexistent property default value"""
        with pytest.raises(ValueError):
            parser_with_schema.get_default_value("unknown")

    def test_validate_valid_config(self, parser_with_schema, valid_config_data):
        """Test validating valid configuration"""
        errors = parser_with_schema.validate_config(valid_config_data)
        assert len(errors) == 0

    def test_validate_missing_required_field(self, parser_with_schema):
        """Test validation with missing required field"""
        config = {
            "count": 10
            # Missing required field 'name'
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("Required field 'name' is missing" in str(e) for e in errors)

    def test_validate_string_min_length(self, parser_with_schema):
        """Test string minLength constraint"""
        config = {
            "name": "",  # Violates minLength: 1
            "count": 10,
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("less than minimum" in str(e).lower() for e in errors)

    def test_validate_string_max_length(self, parser_with_schema):
        """Test string maxLength constraint"""
        config = {
            "name": "x" * 101,  # Violates maxLength: 100
            "count": 10,
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("exceeds maximum" in str(e).lower() for e in errors)

    def test_validate_integer_minimum(self, parser_with_schema):
        """Test integer minimum constraint"""
        config = {
            "name": "test",
            "count": -1,  # Violates minimum: 0
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("less than minimum" in str(e).lower() for e in errors)

    def test_validate_integer_maximum(self, parser_with_schema):
        """Test integer maximum constraint"""
        config = {
            "name": "test",
            "count": 101,  # Violates maximum: 100
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("exceeds maximum" in str(e).lower() for e in errors)

    def test_validate_number_minimum(self, parser_with_schema):
        """Test float minimum constraint"""
        config = {
            "name": "test",
            "count": 10,
            "rate": -0.1,  # Violates minimum: 0.0
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("less than minimum" in str(e).lower() for e in errors)

    def test_validate_number_maximum(self, parser_with_schema):
        """Test float maximum constraint"""
        config = {
            "name": "test",
            "count": 10,
            "rate": 1.5,  # Violates maximum: 1.0
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("exceeds maximum" in str(e).lower() for e in errors)

    def test_validate_enum(self, parser_with_schema):
        """Test enum constraint"""
        config = {
            "name": "test",
            "count": 10,
            "status": "invalid_status",  # Not in enum
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("not in enum" in str(e).lower() for e in errors)

    def test_validate_boolean_type(self, parser_with_schema):
        """Test boolean type validation"""
        config = {
            "name": "test",
            "count": 10,
            "enabled": "not-a-boolean",  # Type error
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("Expected type boolean" in str(e) for e in errors)

    def test_validate_array_min_items(self, parser_with_schema):
        """Test array minItems constraint"""
        config = {"name": "test", "count": 10}
        # tags is optional, if provided must meet constraints
        # Test empty array (minItems: 0)
        config["tags"] = []
        errors = parser_with_schema.validate_config(config)
        # Empty array should pass since minItems is 0
        assert len([e for e in errors if "tags" in e.path]) == 0

    def test_validate_array_max_items(self, parser_with_schema):
        """Test array maxItems constraint"""
        config = {
            "name": "test",
            "count": 10,
            "tags": [f"tag{i}" for i in range(11)],  # Violates maxItems: 10
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        assert any("exceeds maximum" in str(e).lower() for e in errors)

    def test_validate_nested_object(self, parser_with_schema):
        """Test nested object validation"""
        config = {
            "name": "test",
            "count": 10,
            "metadata": {
                "key1": "value",
                "key2": "not-an-integer",  # Type error
            },
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        # Check if there are errors about metadata.key2
        metadata_errors = [e for e in errors if "metadata" in e.path]
        assert len(metadata_errors) > 0

    def test_validate_valid_nested_object(self, parser_with_schema):
        """Test valid nested object"""
        config = {
            "name": "test",
            "count": 10,
            "metadata": {"key1": "value1", "key2": 42},
        }
        errors = parser_with_schema.validate_config(config)
        assert len(errors) == 0

    def test_validation_error_path(self, parser_with_schema):
        """Test that validation errors contain path information"""
        config = {"name": "test", "count": -1}
        errors = parser_with_schema.validate_config(config)
        assert len(errors) > 0
        # Check if errors contain path information
        count_errors = [e for e in errors if "count" in e.path]
        assert len(count_errors) > 0

    def test_static_load_schema(self, sample_schema_file):
        """Test static method load_schema"""
        schema = SchemaParser.load_schema(sample_schema_file)
        assert isinstance(schema, dict)
        assert schema["title"] == "Test Configuration"
