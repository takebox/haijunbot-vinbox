# -*- coding: utf-8 -*-
"""
HaijunBot utility module
This module provides various utility functions and classes used in the HaijunBot system.
It includes a variety of helper functions, configuration management, and common operations.
This module is organized into the following submodules:
- config: configuration management
- dialogue_recorder: dialogue recorder
- embedding: text embedding utility
- git_utils: Git repository operations
- input: user input handling
- output: output formatting
- utils: general utilities
"""

import os

import colorama
from rich.traceback import install as install_rich_traceback

# Re-export from the new module
# These imports are required for project functionality and may be used dynamically
from .dialogue_recorder import DialogueRecorder as DialogueRecorder

# Initialize colorama to support cross-platform colored text
colorama.init()
# Disable tokenizers parallelism to avoid multiprocessing issues
os.environ["TOKENIZERS_PARALLELISM"] = "false"
# Install the rich traceback handler for better error information
install_rich_traceback()
