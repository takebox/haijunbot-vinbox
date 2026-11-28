# -*- coding: utf-8 -*-
"""Regression test configuration"""

import pytest


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "regression: marks tests as regression tests")


@pytest.fixture(scope="session")
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
