# -*- coding: utf-8 -*-
"""Security test configuration"""

import pytest


def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line("markers", "security: marks tests as security tests")


@pytest.fixture(scope="session")
def security_thresholds():
    """Security threshold configuration"""
    return {
        "max_severity": "medium",  # Maximum severity level
        "max_issues": 0,  # Maximum number of security issues
    }
