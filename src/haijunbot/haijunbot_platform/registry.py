# -*- coding: utf-8 -*-
import importlib
import inspect
import os
import sys
from typing import Dict
from typing import List
from typing import Optional
from typing import Type

from haijunbot.haijunbot_platform.base import BasePlatform
from haijunbot.haijunbot_utils.config import get_cheap_platform_name
from haijunbot.haijunbot_utils.config import get_data_dir
from haijunbot.haijunbot_utils.config import get_eval_platform_name
from haijunbot.haijunbot_utils.config import get_normal_platform_name
from haijunbot.haijunbot_utils.config import get_smart_platform_name
from haijunbot.haijunbot_utils.config import is_eval_model_configured
from haijunbot.haijunbot_utils.output import PrettyOutput

REQUIRED_METHODS = [
    ("chat", ["message"]),  # Method names and parameter lists
    ("name", []),
    ("delete_chat", []),
    ("set_system_prompt", ["message"]),
    ("set_model_name", ["model_name"]),
    ("get_model_list", []),
]


class PlatformRegistry:
    """Platform registry"""

    global_platform_name: str = "openai"
    global_platform_registry: Optional["PlatformRegistry"] = None

    @staticmethod
    def get_platform_dir() -> str:
        user_platform_dir = os.path.join(get_data_dir(), "models")
        if not os.path.exists(user_platform_dir):
            try:
                os.makedirs(user_platform_dir)
                # Create __init__.py to make it a Python package
                with open(
                    os.path.join(user_platform_dir, "__init__.py"), "w", errors="ignore"
                ):
                    pass
            except Exception as e:
                PrettyOutput.auto_print(f"❌ Failed to create platform directory: {str(e)}")
                return ""
        return user_platform_dir

    @staticmethod
    def check_platform_implementation(platform_class: Type[BasePlatform]) -> bool:
        """Check if the platform class implements all necessary methods

        Args:
            platform_class: The platform class to check

        Returns:
            bool: Whether all necessary methods are implemented
        """
        missing_methods = []

        for method_name, params in REQUIRED_METHODS:
            if not hasattr(platform_class, method_name):
                missing_methods.append(method_name)
                continue

            method = getattr(platform_class, method_name)
            if not callable(method):
                missing_methods.append(method_name)
                continue

            # Check method parameters
            import inspect

            sig = inspect.signature(method)
            method_params = [p for p in sig.parameters if p != "self"]
            if len(method_params) != len(params):
                missing_methods.append(f"{method_name}(parameter mismatch)")

        if missing_methods:
            PrettyOutput.auto_print(
                f"⚠️ Platform {platform_class.__name__} is missing required methods: {', '.join(missing_methods)}"
            )
            return False

        return True

    @staticmethod
    def load_platform_from_dir(directory: str) -> Dict[str, Type[BasePlatform]]:
        """Load platforms from specified directory

        Args:
            directory: Platform directory path

        Returns:
            Dict[str, Type[BasePlatform]]: Platform name to platform class mapping
        """
        platforms: Dict[str, Type[BasePlatform]] = {}

        # Ensure the directory exists
        if not os.path.exists(directory):
            PrettyOutput.auto_print(f"⚠️ Platform directory does not exist: {directory}")
            return platforms

        # Get the package name of the directory
        package_name = None
        if directory == os.path.dirname(__file__):
            package_name = "haijunbot.haijunbot_platform"

        # Add the directory to the Python path
        if directory not in sys.path:
            sys.path.append(directory)

        error_lines = []
        # Iterate over all .py files in the directory
        for filename in os.listdir(directory):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name = filename[:-3]  # Remove the .py suffix
                try:
                    # Import the module
                    if package_name:
                        module = importlib.import_module(
                            f"{package_name}.{module_name}"
                        )
                    else:
                        module = importlib.import_module(module_name)

                    # Iterate over all classes in the module
                    for _, obj in inspect.getmembers(module):
                        # Check if it is a subclass of BasePlatform but not BasePlatform itself
                        if (
                            inspect.isclass(obj)
                            and issubclass(obj, BasePlatform)
                            and obj != BasePlatform
                        ):
                            # Check the platform implementation
                            if not PlatformRegistry.check_platform_implementation(obj):
                                continue
                            try:
                                # Call the class method platform_name
                                platform_name = obj.platform_name()
                                platforms[platform_name] = obj
                            except Exception as e:
                                error_lines.append(
                                    f"Failed to instantiate or register platform {obj.__name__}: {str(e)}"
                                )
                            break
                except Exception as e:
                    error_lines.append(f"Failed to load platform {module_name}: {str(e)}")

        if error_lines:
            joined_errors = "\n".join(error_lines)
            PrettyOutput.auto_print(f"❌ {joined_errors}")
        return platforms

    @staticmethod
    def get_global_platform_registry() -> "PlatformRegistry":
        """Get global platform registry"""
        if PlatformRegistry.global_platform_registry is None:
            PlatformRegistry.global_platform_registry = PlatformRegistry()
        return PlatformRegistry.global_platform_registry

    def __init__(self) -> None:
        """Initialize platform registry"""
        self.platforms: Dict[str, Type[BasePlatform]] = {}
        # Load additional platforms from the user platform directory
        platform_dir = PlatformRegistry.get_platform_dir()
        if platform_dir and os.path.exists(platform_dir):
            for (
                platform_name,
                platform_class,
            ) in PlatformRegistry.load_platform_from_dir(platform_dir).items():
                self.register_platform(platform_name, platform_class)
        platform_dir = os.path.dirname(__file__)
        if platform_dir and os.path.exists(platform_dir):
            for (
                platform_name,
                platform_class,
            ) in PlatformRegistry.load_platform_from_dir(platform_dir).items():
                self.register_platform(platform_name, platform_class)

    def get_normal_platform(self) -> BasePlatform:
        """Get the platform instance for normal operations"""
        platform_name = get_normal_platform_name()

        # Use silent=True to avoid duplicate error messages, since an exception is raised on failure
        platform = self.create_platform(
            platform_type="normal",
            silent=True,
        )
        if platform is None:
            raise RuntimeError(
                f"Unable to create platform instance: platform '{platform_name}' failed to create, please check the configuration (such as API key, etc.)."
            )
        return platform

    def get_cheap_platform(self) -> BasePlatform:
        """Get the platform instance for cheap operations"""
        platform_name = get_cheap_platform_name()

        # Use silent=True to avoid duplicate error messages, since an exception is raised on failure
        platform = self.create_platform(
            platform_type="cheap",
            silent=True,
        )
        if platform is None:
            raise RuntimeError(
                f"Unable to create platform instance: platform '{platform_name}' failed to create, please check the configuration (such as API key, etc.)"
            )
        return platform

    def get_smart_platform(self) -> BasePlatform:
        """Get the platform instance for smart operations"""
        platform_name = get_smart_platform_name()

        # Use silent=True to avoid duplicate error messages, since an exception is raised on failure
        platform = self.create_platform(
            platform_type="smart",
            silent=True,
        )
        if platform is None:
            raise RuntimeError(
                f"Unable to create platform instance: platform '{platform_name}' failed to create, please check the configuration (such as API key, etc.)"
            )
        return platform

    def get_eval_platform(self) -> Optional[BasePlatform]:
        """Get the platform instance for the structured evaluation model.

        Returns None when eval_llm is not configured (the caller falls back to the existing flow based on this), without raising an exception.
        """
        if not is_eval_model_configured():
            return None
        return self.create_platform(
            platform_type="eval",
            silent=True,
        )

    def register_platform(self, name: str, platform_class: Type[BasePlatform]) -> None:
        """Register platform class

        Args:
            name: Platform name
            model_class: Platform class
        """
        self.platforms[name] = platform_class

    def create_platform(
        self,
        platform_type: str = "normal",
        silent: bool = False,
    ) -> Optional[BasePlatform]:
        """Create platform instance

        Args:
            name: Platform name
            platform_type: Platform type, with possible values 'normal', 'cheap', 'smart' or 'eval'
            silent: If True, do not print error messages on failure (default False, kept for backward compatibility)

        Returns:
            BasePlatform: Platform instance
        """
        if platform_type == "smart":
            name = get_smart_platform_name()
        elif platform_type == "cheap":
            name = get_cheap_platform_name()
        elif platform_type == "eval":
            name = get_eval_platform_name()
        else:
            name = get_normal_platform_name()

        try:
            platform = self.platforms[name](platform_type=platform_type)
            return platform
        except Exception as e:
            if not silent:
                PrettyOutput.auto_print(f"❌ Failed to create platform: {str(e)}")
            return None

    def get_available_platforms(self) -> List[str]:
        """Get available platform list"""
        return list(self.platforms.keys())
