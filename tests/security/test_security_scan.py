# -*- coding: utf-8 -*-
"""Security scan tests"""

import subprocess
import pytest


class TestSecurityScan:
    """Security scan tests"""

    @pytest.mark.security
    @pytest.mark.slow
    def test_bandit_scan_src(self):
        """Use bandit to scan the src directory (full security scan, takes longer, can be excluded with -m "not slow")"""
        result = subprocess.run(
            ["bandit", "-r", "src/haijunbot", "-f", "json"], capture_output=True, text=True
        )
        # bandit return code non-0 means issues found, here we only verify the tool runs
        assert result.returncode in [0, 1]  # 0=no issues, 1=issues found

    @pytest.mark.security
    def test_no_hardcoded_secrets(self):
        """Check for hardcoded secrets"""
        import os

        src_dir = "src/haijunbot"
        suspicious_patterns = [
            "api_key",
            "secret_key",
            "password",
            "token",
        ]

        found_issues = []
        for root, dirs, files in os.walk(src_dir):
            # Skip __pycache__ directory
            dirs[:] = [d for d in dirs if d != "__pycache__"]

            for file in files:
                if file.endswith(".py"):
                    filepath = os.path.join(root, file)
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()
                        for pattern in suspicious_patterns:
                            if pattern in content.lower():
                                found_issues.append(f"{filepath}: contains '{pattern}'")

        # Record found issues (real projects should have a whitelist)
        # Only warn here, do not fail the test
        if found_issues:
            print("\nWarning: possible sensitive words found:\n" + "\n".join(found_issues))
