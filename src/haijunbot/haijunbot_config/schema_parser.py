# -*- coding: utf-8 -*-
"""
JSON Schema parser and validator

Supports the basic features of the JSON Schema Draft-07 specification
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast


class ValidationError(Exception):
    """Schema validation error"""

    def __init__(self, message: str, path: str = ""):
        self.message = message
        self.path = path
        super().__init__(f"{path}: {message}" if path else message)


class SchemaParser:
    """JSON Schema parser and validator

    Supports common features of JSON Schema Draft-07:
    - Basic types: string, number, integer, boolean, array, object
    - Constraints: enum, default, minimum, maximum, minLength, maxLength, pattern, required
    - Complex structures: oneOf, anyOf, nested objects and arrays
    """

    def __init__(self, schema_path: Union[str, Path]):
        """Initialize the parser

        Args:
            schema_path: JSON Schema file path
        """
        self.schema_path = Path(schema_path)
        self.schema: Dict[str, Any] = self._load_schema()

    def _load_schema(self) -> Dict[str, Any]:
        """Load the JSON Schema file"""
        with open(self.schema_path, "r", encoding="utf-8") as f:
            return cast(Dict[str, Any], json.load(f))

    @staticmethod
    def load_schema(path: Union[str, Path]) -> Dict[str, Any]:
        """Static method: load the JSON Schema file

        Args:
            path: Schema file path

        Returns:
            Schema dictionary
        """
        with open(Path(path), "r", encoding="utf-8") as f:
            return cast(Dict[str, Any], json.load(f))

    def get_schema(self) -> Dict[str, Any]:
        """Get the Schema object

        Returns:
            Schema dictionary
        """
        return self.schema

    def get_title(self) -> str:
        """Get the Schema title"""
        return cast(str, self.schema.get("title", "Configuration"))

    def get_description(self) -> str:
        """Get the Schema description"""
        return cast(str, self.schema.get("description", ""))

    def get_properties(self) -> Dict[str, Any]:
        """Get the top-level properties"""
        return cast(Dict[str, Any], self.schema.get("properties", {}))

    def get_property_schema(self, property_name: str) -> Dict[str, Any]:
        """Get the Schema of a property

        Args:
            property_name: Property name

        Returns:
            The property's Schema definition
        """
        properties = self.get_properties()
        if property_name not in properties:
            raise ValueError(f"Property '{property_name}' not found in schema")
        return cast(Dict[str, Any], properties[property_name])

    def get_required(self) -> List[str]:
        """Get the list of required properties"""
        return cast(List[str], self.schema.get("required", []))

    def get_default_value(self, property_name: str) -> Any:
        """Get the default value of a property

        Args:
            property_name: Property name

        Returns:
            The default value, or None if there is none
        """
        prop_schema = self.get_property_schema(property_name)
        return prop_schema.get("default")

    def get_type(self, property_name: str) -> str:
        """Get the property type

        Args:
            property_name: Property name

        Returns:
            Type string
        """
        prop_schema = self.get_property_schema(property_name)
        return cast(str, prop_schema.get("type", "string"))

    def get_enum(self, property_name: str) -> Optional[List[Any]]:
        """Get the enum values of a property

        Args:
            property_name: Property name

        Returns:
            List of enum values, or None if there are none
        """
        prop_schema = self.get_property_schema(property_name)
        enum_val = prop_schema.get("enum")
        return cast(Optional[List[Any]], enum_val)

    def get_description_for_property(self, property_name: str) -> str:
        """Get the description of a property

        Args:
            property_name: Property name

        Returns:
            Description string
        """
        prop_schema = self.get_property_schema(property_name)
        return cast(str, prop_schema.get("description", ""))

    def validate_config(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate whether the configuration conforms to the Schema

        Args:
            config: Configuration dictionary

        Returns:
            List of validation errors; empty means validation passed
        """
        errors: List[ValidationError] = []
        self._validate_against_schema(config, self.schema, "", errors)

        # If validation passes, perform type conversion
        if not errors:
            self._convert_types(config, self.schema, "")

        return errors

    def _validate_against_schema(
        self,
        value: Any,
        schema: Dict[str, Any],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Recursively validate whether the value conforms to the Schema

        Args:
            value: The value to validate
            schema: Schema definition
            path: Current validation path (used for error messages)
            errors: Error list (accumulated)
        """
        # Handle oneOf
        if "oneOf" in schema:
            one_of_errors: List[ValidationError] = []
            matched = False
            for i, sub_schema in enumerate(schema["oneOf"]):
                sub_errors: List[ValidationError] = []
                self._validate_against_schema(value, sub_schema, path, sub_errors)
                if not sub_errors:
                    matched = True
                    break
                one_of_errors.extend(sub_errors)
            if not matched:
                errors.append(
                    ValidationError("Value does not match any schema in oneOf", path)
                )
            return

        # Handle anyOf
        if "anyOf" in schema:
            for sub_schema in schema["anyOf"]:
                any_sub_errors: List[ValidationError] = []
                self._validate_against_schema(value, sub_schema, path, any_sub_errors)
                if not any_sub_errors:
                    return  # Match at least one
            errors.append(
                ValidationError("Value does not match any schema in anyOf", path)
            )
            return

        # Validate the type
        if "type" in schema:
            type_errors = self._validate_type(value, schema["type"], path)
            if type_errors:
                errors.extend(type_errors)
                return

        # Validate the enum
        if "enum" in schema:
            if value not in schema["enum"]:
                errors.append(
                    ValidationError(
                        f"Value '{value}' not in enum: {schema['enum']}", path
                    )
                )
            return

        # Perform specific validation based on the type
        if isinstance(value, str):
            self._validate_string(value, schema, path, errors)
        elif isinstance(value, (int, float)):
            self._validate_number(value, schema, path, errors)
        elif isinstance(value, list):
            self._validate_array(value, schema, path, errors)
        elif isinstance(value, dict):
            self._validate_object(value, schema, path, errors)

    def _validate_type(
        self, value: Any, expected_type: Union[str, List[str]], path: str
    ) -> List[ValidationError]:
        """Validate the value type

        Args:
            value: The value to validate
            expected_type: Expected type(s) (may be a string or a list)
            path: Current path

        Returns:
            Error list
        """
        if isinstance(expected_type, list):
            for t in expected_type:
                errors = self._validate_type(value, t, path)
                if not errors:
                    return []  # Matching one type is sufficient
            return [
                ValidationError(
                    f"Expected type one of {expected_type}, got {type(value).__name__}",
                    path,
                )
            ]

        type_map: Dict[str, Any] = {
            "string": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        if expected_type not in type_map:
            return []  # Unknown type, skip validation

        expected_python_type = type_map[expected_type]
        if not isinstance(value, expected_python_type):
            return [
                ValidationError(
                    f"Expected type {expected_type}, got {type(value).__name__}", path
                )
            ]

        # integer must be an integer, not a float
        if expected_type == "integer" and isinstance(value, bool):
            return [ValidationError("Expected integer, got boolean", path)]

        return []

    def _validate_string(
        self,
        value: str,
        schema: Dict[str, Any],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Validate string constraints

        Args:
            value: String value
            schema: Schema definition
            path: Current path
            errors: Error list
        """
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                ValidationError(
                    f"String length {len(value)} is less than minimum {schema['minLength']}",
                    path,
                )
            )

        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(
                ValidationError(
                    f"String length {len(value)} exceeds maximum {schema['maxLength']}",
                    path,
                )
            )

        if "pattern" in schema:
            try:
                if not re.match(schema["pattern"], value):
                    errors.append(
                        ValidationError(
                            f"String '{value}' does not match pattern '{schema['pattern']}'",
                            path,
                        )
                    )
            except re.error as e:
                errors.append(ValidationError(f"Invalid pattern: {e}", path))

        if "format" in schema:
            format_value = schema["format"]
            if format_value == "uri" and not value.startswith(
                ("http://", "https://", "/")
            ):
                errors.append(ValidationError(f"Invalid URI format: {value}", path))

    def _validate_number(
        self,
        value: Union[int, float],
        schema: Dict[str, Any],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Validate numeric constraints

        Args:
            value: Numeric value
            schema: Schema definition
            path: Current path
            errors: Error list
        """
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(
                ValidationError(
                    f"Value {value} is less than minimum {schema['minimum']}", path
                )
            )

        if "maximum" in schema and value > schema["maximum"]:
            errors.append(
                ValidationError(
                    f"Value {value} exceeds maximum {schema['maximum']}", path
                )
            )

        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(
                ValidationError(
                    f"Value {value} must be greater than {schema['exclusiveMinimum']}",
                    path,
                )
            )

        if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
            errors.append(
                ValidationError(
                    f"Value {value} must be less than {schema['exclusiveMaximum']}",
                    path,
                )
            )

    def _validate_array(
        self,
        value: List[Any],
        schema: Dict[str, Any],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Validate array constraints

        Args:
            value: Array value
            schema: Schema definition
            path: Current path
            errors: Error list
        """
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                ValidationError(
                    f"Array length {len(value)} is less than minimum {schema['minItems']}",
                    path,
                )
            )

        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(
                ValidationError(
                    f"Array length {len(value)} exceeds maximum {schema['maxItems']}",
                    path,
                )
            )

        # Validate array items
        if "items" in schema and isinstance(schema["items"], dict):
            for i, item in enumerate(value):
                item_path = f"{path}[{i}]"
                self._validate_against_schema(item, schema["items"], item_path, errors)

    def _validate_object(
        self,
        value: Dict[str, Any],
        schema: Dict[str, Any],
        path: str,
        errors: List[ValidationError],
    ) -> None:
        """Validate object constraints

        Args:
            value: Object value
            schema: Schema definition
            path: Current path
            errors: Error list
        """
        # Validate required fields
        required = schema.get("required", [])
        for field in required:
            if field not in value:
                errors.append(
                    ValidationError(f"Required field '{field}' is missing", path)
                )

        # Validate properties
        properties = schema.get("properties", {})
        for field, field_value in value.items():
            if field in properties:
                field_path = f"{path}.{field}" if path else field
                self._validate_against_schema(
                    field_value, properties[field], field_path, errors
                )
            elif not schema.get("additionalProperties", True):
                errors.append(
                    ValidationError(f"Additional property '{field}' not allowed", path)
                )

    def _convert_types(self, value: Any, schema: Dict[str, Any], path: str) -> None:
        """Convert the value's type according to the Schema

        Args:
            value: The value to convert (modified in place)
            schema: Schema definition
            path: Current path
        """
        # Handle oneOf/anyOf: find the matching schema and convert
        if "oneOf" in schema:
            for sub_schema in schema["oneOf"]:
                sub_errors: List[ValidationError] = []
                self._validate_against_schema(value, sub_schema, path, sub_errors)
                if not sub_errors:
                    self._convert_types(value, sub_schema, path)
                    return
            return

        if "anyOf" in schema:
            for sub_schema in schema["anyOf"]:
                sub_errors_anyof: List[ValidationError] = []
                self._validate_against_schema(value, sub_schema, path, sub_errors_anyof)
                if not sub_errors_anyof:
                    self._convert_types(value, sub_schema, path)
                    return
            return

        # Convert basic types
        # Note: basic types (scalars) cannot be modified in place, so no top-level scalar conversion is done here.
        # Scalar conversion only applies to elements/fields within writable containers (list/dict) (see the recursive handling below).
        # Top-level scalars are converted by the caller at the assignment site. The previous top-level conversion logic was dead code (converted was discarded).

        # Recursively handle arrays and objects
        if isinstance(value, list) and "items" in schema:
            item_schema = schema["items"]
            for i, item in enumerate(value):
                # Convert array elements
                converted = self._try_convert(item, item_schema.get("type"))
                if converted is not None and converted is not item:
                    value[i] = converted
                    item = converted
                # Recursively handle nested structures
                self._convert_types(item, item_schema, f"{path}[{i}]")

        if isinstance(value, dict):
            # Handle directly defined properties
            if "properties" in schema:
                properties = schema["properties"]
                for field, field_value in value.items():
                    if field in properties:
                        field_path = f"{path}.{field}" if path else field
                        # Convert the field value
                        converted = self._try_convert(
                            field_value, properties[field].get("type")
                        )
                        if converted is not None and converted is not field_value:
                            value[field] = converted
                            field_value = converted
                        # Recursively handle nested structures
                        self._convert_types(field_value, properties[field], field_path)
            # Handle additionalProperties
            elif "additionalProperties" in schema:
                additional_schema = schema["additionalProperties"]
                if isinstance(additional_schema, dict):
                    for field, field_value in value.items():
                        field_path = f"{path}.{field}" if path else field
                        # Convert the field value
                        type_value = additional_schema.get("type")
                        converted = self._try_convert(
                            field_value,
                            type_value if type_value is not None else "string",
                        )
                        if converted is not None and converted is not field_value:
                            value[field] = converted
                            field_value = converted
                        # Recursively handle nested structures
                        self._convert_types(field_value, additional_schema, field_path)

    def _try_convert(self, value: Any, target_type: str) -> Any:
        """Attempt to convert the value to the target type

        Args:
            value: The value to convert
            target_type: Target type (string, number, integer, boolean)

        Returns:
            The converted value, or None if conversion is not possible
        """
        if value is None:
            return None

        # Already the correct type, return directly
        if target_type == "string" and isinstance(value, str):
            return None
        if target_type == "number" and isinstance(value, (int, float)):
            return None
        if (
            target_type == "integer"
            and isinstance(value, int)
            and not isinstance(value, bool)
        ):
            return None
        if target_type == "boolean" and isinstance(value, bool):
            return None

        # Try to convert from a string
        if isinstance(value, str):
            try:
                if target_type == "number":
                    # Try converting to an integer first, then to a float
                    if "." in value or "e" in value.lower():
                        return float(value)
                    else:
                        return int(value)
                elif target_type == "integer":
                    return int(value)
                elif target_type == "boolean":
                    if value.lower() in ("true", "1", "yes", "on"):
                        return True
                    elif value.lower() in ("false", "0", "no", "off"):
                        return False
                elif target_type == "string":
                    return str(value)
            except (ValueError, TypeError):
                pass

        # Try to convert from a number
        if isinstance(value, (int, float)):
            if target_type == "string":
                return str(value)
            elif (
                target_type == "integer"
                and isinstance(value, float)
                and value.is_integer()
            ):
                return int(value)
            elif target_type == "boolean":
                return bool(value)

        # Try to convert from a boolean
        if isinstance(value, bool):
            if target_type == "string":
                return "true" if value else "false"
            elif target_type in ("number", "integer"):
                return 1 if value else 0

        return None
