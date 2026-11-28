# -*- coding: utf-8 -*-
"""pytest configuration file"""

import sys
import os
import pytest
from unittest.mock import Mock

# Add project root directory to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


@pytest.fixture(scope="session")
def test_data_dir():
    """Test data directory"""
    return os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture(scope="function")
def temp_dir(tmp_path):
    """Temporary directory fixture, each test function gets a new temp directory"""
    return tmp_path


@pytest.fixture(autouse=True)
def reset_globals():
    """Automatically reset global state to prevent interference between tests"""

    yield

    # Clean up global state after test
    # Handle global variables or singletons that need resetting here


@pytest.fixture(scope="function")
def sample_code_file():
    """Sample code file fixture"""
    return """
def hello_world():
    print("Hello, World!")
    return True


class Calculator:
    def add(self, a, b):
        return a + b
"""


@pytest.fixture(scope="function")
def sample_project_structure():
    """Sample project structure fixture"""
    return {
        "src": {"main.py": "print('Hello')", "utils.py": "def helper(): pass"},
        "tests": {"test_main.py": "def test_main(): pass"},
    }


@pytest.fixture(scope="function")
def mock_openai_response():
    """Mock OpenAI response"""

    def _create_mock_response(content: str = "Test response"):
        mock = Mock()
        mock.choices = [Mock(message=Mock(content=content))]
        return mock

    return _create_mock_response


@pytest.fixture(scope="function")
def mock_juglow_response():
    """Mock Juglow response"""

    def _create_mock_response(content: str = "Test response"):
        mock = Mock()
        mock.content = [Mock(type="text", text=content)]
        return mock

    return _create_mock_response


@pytest.fixture(scope="function")
def performance_thresholds():
    """Performance threshold configuration"""
    return {
        "code_generation_max_time": 5.0,  # seconds
        "code_analysis_max_time": 3.0,  # seconds
        "max_memory_mb": 100,  # MB
    }


@pytest.fixture(scope="function")
def regression_test_data():
    """Regression test data"""
    return {
        "critical_functions": [
            "haijunbot_agent",
            "code_agent",
            "git_utils",
        ],
        "api_endpoints": [
            "/api/agent/chat",
            "/api/code/analyze",
        ],
    }
