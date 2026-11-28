# -*- coding: utf-8 -*-
"""
HaijunBot Security Evolution Multi-Agent Suite -- Checkers package initialization

Description:
- Uniformly export the public interfaces of the C/C++ and Rust heuristic checkers, making it convenient for upper-layer workflows to call them on demand.
- Keep dependencies minimal; do not execute any scanning logic here, only perform imports and alias exposure.
"""

from haijunbot.haijunbot_sec.checkers.c_checker import analyze_c_cpp_file
from haijunbot.haijunbot_sec.checkers.c_checker import analyze_c_cpp_text
from haijunbot.haijunbot_sec.checkers.c_checker import analyze_files as analyze_c_files
from haijunbot.haijunbot_sec.checkers.rust_checker import analyze_rust_file
from haijunbot.haijunbot_sec.checkers.rust_checker import analyze_rust_files
from haijunbot.haijunbot_sec.checkers.rust_checker import analyze_rust_text

__all__ = [
    # C/C++
    "analyze_c_files",
    "analyze_c_cpp_file",
    "analyze_c_cpp_text",
    # Rust
    "analyze_rust_files",
    "analyze_rust_file",
    "analyze_rust_text",
]
