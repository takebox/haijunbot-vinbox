# -*- coding: utf-8 -*-
"""haijunbot_config module test fixtures"""

import json
import pytest

from haijunbot.haijunbot_config.schema_parser import SchemaParser


@pytest.fixture(scope="function")
def sample_schema_file(tmp_path):
    """Create a JSON Schema file for testing.

    Contains multiple field types and constraints.
    """
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Test Configuration",
        "description": "Configuration Schema for testing",
        "type": "object",
        "required": ["name", "count"],
        "properties": {
            "name": {
                "type": "string",
                "description": "Name field",
                "minLength": 1,
                "maxLength": 100,
                "default": "test",
            },
            "count": {
                "type": "integer",
                "description": "Count field",
                "minimum": 0,
                "maximum": 100,
                "default": 1,
            },
            "rate": {
                "type": "number",
                "description": "Rate field",
                "minimum": 0.0,
                "maximum": 1.0,
                "default": 0.5,
            },
            "enabled": {"type": "boolean", "description": "Whether enabled", "default": True},
            "status": {
                "type": "string",
                "enum": ["active", "inactive", "pending"],
                "description": "Status enum",
                "default": "pending",
            },
            "tags": {
                "type": "array",
                "description": "Tags array",
                "items": {"type": "string"},
                "minItems": 0,
                "maxItems": 10,
                "default": [],
            },
            "metadata": {
                "type": "object",
                "description": "Metadata object",
                "properties": {
                    "key1": {"type": "string", "default": "value1"},
                    "key2": {"type": "integer", "default": 42},
                },
                "default": {},
            },
        },
    }

    schema_path = tmp_path / "test_schema.json"
    with open(schema_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    return schema_path


@pytest.fixture(scope="function")
def parser_with_schema(sample_schema_file):
    """SchemaParser instance initialized with the test Schema"""
    return SchemaParser(sample_schema_file)


@pytest.fixture(scope="function")
def valid_config_data():
    """Valid configuration data for testing"""
    return {
        "name": "test-config",
        "count": 10,
        "rate": 0.75,
        "enabled": True,
        "status": "active",
        "tags": ["tag1", "tag2"],
        "metadata": {"key1": "custom-value", "key2": 100},
    }


@pytest.fixture(scope="function")
def invalid_config_data():
    """Invalid configuration data for testing validation logic"""
    return {
        "name": "",  # Violates minLength: 1
        "count": -1,  # Violates minimum: 0
        "rate": 2.0,  # Violates maximum: 1.0
        "status": "invalid",  # Not in enum
        "enabled": "not-a-boolean",  # Type error
    }
