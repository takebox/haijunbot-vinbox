# -*- coding: utf-8 -*-
"""Web API integration tests"""

import json

import yaml
from fastapi.testclient import TestClient

from haijunbot.haijunbot_config.web_app import create_app


class TestWebApp:
    """Test FastAPI application"""

    def test_create_app(self, sample_schema_file, tmp_path):
        """Test application creation"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        assert app is not None
        assert app.title == "HaijunBot Configuration Tool"

    def test_get_schema_endpoint(self, sample_schema_file, tmp_path):
        """Test GET /api/schema endpoint"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        response = client.get("/api/schema")
        assert response.status_code == 200

        data = response.json()
        assert "title" in data
        assert "description" in data
        assert "properties" in data
        assert "required" in data
        assert data["title"] == "Test Configuration"

    def test_get_schema_endpoint_with_meta(self, sample_schema_file, tmp_path):
        """Test that /api/schema returned properties contain _meta information"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        response = client.get("/api/schema")
        assert response.status_code == 200

        data = response.json()
        properties = data["properties"]

        # Check name property _meta information
        assert "_meta" in properties["name"]
        assert properties["name"]["_meta"]["description"] == "Name field"
        assert properties["name"]["_meta"]["default"] == "test"
        assert properties["name"]["_meta"]["required"] is True

        # Check count property _meta information
        assert "_meta" in properties["count"]
        assert properties["count"]["_meta"]["required"] is True

        # Check enabled property _meta information (not required)
        assert "_meta" in properties["enabled"]
        assert properties["enabled"]["_meta"]["required"] is False

    def test_post_save_endpoint_success(self, sample_schema_file, tmp_path):
        """Test POST /api/save endpoint - successful save"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {
            "name": "test-config",
            "count": 10,
            "rate": 0.75,
            "enabled": True,
            "status": "active",
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is True
        assert "message" in result
        assert "path" in result

        # Check if file was saved
        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            saved_config = json.load(f)
        assert saved_config == config_data

    def test_post_save_endpoint_validation_error(self, sample_schema_file, tmp_path):
        """Test POST /api/save endpoint - validation failure"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        # Provide invalid configuration data
        config_data = {
            "name": "",  # Violates minLength: 1
            "count": -1,  # Violates minimum: 0
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0

    def test_post_save_endpoint_enum_validation(self, sample_schema_file, tmp_path):
        """Test POST /api/save endpoint - enum validation"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {
            "name": "test",
            "count": 10,
            "status": "invalid_status",  # Not in enum
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is False
        assert "errors" in result
        assert any("not in enum" in str(err).lower() for err in result["errors"])

    def test_post_save_endpoint_type_error(self, sample_schema_file, tmp_path):
        """Test POST /api/save endpoint - type error"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {
            "name": "test",
            "count": 10,
            "enabled": "not-a-boolean",  # Type error
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is False
        assert "errors" in result
        assert any("Expected type boolean" in str(err) for err in result["errors"])

    def test_post_save_endpoint_missing_required(self, sample_schema_file, tmp_path):
        """Test POST /api/save endpoint - missing required field"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {
            "count": 10  # Missing required field 'name'
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200

        result = response.json()
        assert result["success"] is False
        assert "errors" in result
        assert any("Required field" in str(err) for err in result["errors"])

    def test_get_health_endpoint(self, sample_schema_file, tmp_path):
        """Test GET /api/health health check endpoint"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        response = client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"

    def test_get_root_endpoint(self, sample_schema_file, tmp_path):
        """Test GET / endpoint returns HTML"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!DOCTYPE html>" in response.text

    def test_save_creates_output_directory(self, sample_schema_file, tmp_path):
        """Test that saving configuration auto-creates output directory"""
        output_dir = tmp_path / "subdir" / "nested"
        output_file = output_dir / "config.json"

        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {"name": "test", "count": 5}

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Check if directory and file were created
        assert output_dir.exists()
        assert output_file.exists()

    def test_nested_object_validation(self, sample_schema_file, tmp_path):
        """Test nested object validation and saving"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        # Valid nested object
        config_data = {
            "name": "test",
            "count": 10,
            "metadata": {"key1": "value1", "key2": 42},
        }

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Invalid nested object (type error)
        config_data_invalid = {
            "name": "test",
            "count": 10,
            "metadata": {"key1": "value1", "key2": "not-an-integer"},
        }

        response = client.post("/api/save", json={"config": config_data_invalid})
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_array_validation(self, sample_schema_file, tmp_path):
        """Test array validation and saving"""
        output_file = tmp_path / "config.json"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        # Valid array
        config_data = {"name": "test", "count": 10, "tags": ["tag1", "tag2", "tag3"]}

        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Invalid array (exceeds maximum items)
        config_data_invalid = {
            "name": "test",
            "count": 10,
            "tags": [f"tag{i}" for i in range(11)],
        }

        response = client.post("/api/save", json={"config": config_data_invalid})
        assert response.status_code == 200
        assert response.json()["success"] is False

    def test_yaml_save_and_load(self, sample_schema_file, tmp_path):
        """Test YAML format save and load"""
        output_file = tmp_path / "config.yaml"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        # Save configuration as YAML
        config_data = {
            "name": "test",
            "count": 42,
            "enabled": True,
            "tags": ["tag1", "tag2"],
        }
        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify file exists and is valid YAML
        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
        assert loaded_config == config_data

        # Recreate application, verify it can correctly load YAML configuration
        app2 = create_app(sample_schema_file, output_file)
        client2 = TestClient(app2)
        response2 = client2.get("/api/schema")
        assert response2.status_code == 200
        schema_data = response2.json()
        # Verify default values have been overridden by YAML configuration
        assert schema_data["properties"]["name"]["_meta"]["default"] == "test"
        assert schema_data["properties"]["count"]["_meta"]["default"] == 42

    def test_yml_extension(self, sample_schema_file, tmp_path):
        """Test .yml extension support"""
        output_file = tmp_path / "config.yml"
        app = create_app(sample_schema_file, output_file)
        client = TestClient(app)

        config_data = {"name": "test", "count": 10}
        response = client.post("/api/save", json={"config": config_data})
        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify file is valid YAML
        with open(output_file, "r", encoding="utf-8") as f:
            loaded_config = yaml.safe_load(f)
        assert loaded_config == config_data
