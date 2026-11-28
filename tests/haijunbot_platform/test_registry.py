# -*- coding: utf-8 -*-
"""haijunbot_platform.registry module unit tests"""

import os
from unittest.mock import patch, MagicMock

from haijunbot.haijunbot_platform.registry import PlatformRegistry
from haijunbot.haijunbot_platform.base import BasePlatform


class TestPlatformRegistry:
    """Test PlatformRegistry class"""

    @patch("haijunbot.haijunbot_platform.registry.get_data_dir")
    @patch("haijunbot.haijunbot_platform.registry.os.path.exists")
    @patch("haijunbot.haijunbot_platform.registry.os.makedirs")
    def test_get_platform_dir_existing(
        self, mock_makedirs, mock_exists, mock_get_data_dir
    ):
        """Test getting an existing platform directory"""
        mock_get_data_dir.return_value = "/test/data"
        mock_exists.return_value = True

        result = PlatformRegistry.get_platform_dir()
        assert result == os.path.join("/test/data", "models")
        mock_makedirs.assert_not_called()

    @patch("haijunbot.haijunbot_platform.registry.get_data_dir")
    @patch("haijunbot.haijunbot_platform.registry.os.path.exists")
    @patch("haijunbot.haijunbot_platform.registry.os.makedirs")
    @patch("builtins.open")
    def test_get_platform_dir_create(
        self, mock_open, mock_makedirs, mock_exists, mock_get_data_dir
    ):
        """Test creating platform directory"""
        mock_get_data_dir.return_value = "/test/data"
        mock_exists.return_value = False
        mock_open.return_value.__enter__ = MagicMock()
        mock_open.return_value.__exit__ = MagicMock(return_value=None)

        result = PlatformRegistry.get_platform_dir()
        assert result == os.path.join("/test/data", "models")
        mock_makedirs.assert_called_once()

    def test_check_platform_implementation_valid(self):
        """Test checking a valid platform implementation"""

        class ValidPlatform(BasePlatform):
            def chat(self, message: str):
                pass

            def name(self) -> str:
                return "test"

            def delete_chat(self) -> bool:
                return True

            def set_system_prompt(self, message: str):
                pass

            def set_model_name(self, model_name: str):
                pass

            def get_model_list(self):
                return []

            def upload_files(self, file_list):
                return True

            @classmethod
            def platform_name(cls) -> str:
                return "test_platform"

        result = PlatformRegistry.check_platform_implementation(ValidPlatform)
        assert result is True

    def test_check_platform_implementation_missing_method(self):
        """Test checking a platform implementation missing methods"""

        # Create a class that does not implement all required methods
        class InvalidPlatform:
            def chat(self, message: str):
                pass

            # Missing other required methods: name, delete_chat, set_system_prompt, set_model_name, get_model_list, upload_files

        result = PlatformRegistry.check_platform_implementation(InvalidPlatform)
        assert result is False

    def test_check_platform_implementation_wrong_params(self):
        """Test checking a platform implementation with mismatched parameters"""

        class WrongParamsPlatform(BasePlatform):
            def chat(self, message: str, extra_param: str):  # Parameter mismatch
                pass

            def name(self) -> str:
                return "test"

            def delete_chat(self) -> bool:
                return True

            def set_system_prompt(self, message: str):
                pass

            def set_model_name(self, model_name: str):
                pass

            def get_model_list(self):
                return []

            def upload_files(self, file_list):
                return True

            @classmethod
            def platform_name(cls) -> str:
                return "test_platform"

        result = PlatformRegistry.check_platform_implementation(WrongParamsPlatform)
        assert result is False

    def test_check_platform_implementation_non_callable(self):
        """Test checking a platform implementation with non-callable methods"""

        class NonCallablePlatform(BasePlatform):
            chat = "not a method"  # Not a callable object

            def name(self) -> str:
                return "test"

            def delete_chat(self) -> bool:
                return True

            def set_system_prompt(self, message: str):
                pass

            def set_model_name(self, model_name: str):
                pass

            def get_model_list(self):
                return []

            def upload_files(self, file_list):
                return True

            @classmethod
            def platform_name(cls) -> str:
                return "test_platform"

        result = PlatformRegistry.check_platform_implementation(NonCallablePlatform)
        assert result is False
