# -*- coding: utf-8 -*-
"""
HaijunBot C2Rust toolkit.

Core data:
- Unified symbol table (JSONL): <project_root>/.haijunbot/c2rust/symbols.jsonl (main input for subsequent stages)
- Raw symbol table (JSONL): <project_root>/.haijunbot/c2rust/symbols_raw.jsonl
- Other artifacts: translation_order.jsonl, library_replacements.jsonl, progress.json, config.json, symbol_map.jsonl, etc.

Recommended usage (CLI):
  - Configuration management: haijunbot-c2rust config --files <hdrs...> [--root-list-syms ...] [--disabled-libs ...]
  - Scan:             haijunbot-c2rust scan
  - Library replacement evaluation: haijunbot-c2rust lib-replace [-g <llm-group>]
  - Planning/persist: haijunbot-c2rust prepare [-g <llm-group>]
  - Transpile:        haijunbot-c2rust transpile [-g <llm-group>] [-m <max-retries>] (checkpoint resume is always enabled by default)
  - Code optimization: haijunbot-c2rust optimize [--crate-dir ...] [--unsafe/--no-unsafe] [--structure/--no-structure] [--visibility/--no-visibility] [--doc/--no-doc] [-m N] [--dry-run]
  - One-click pipeline: haijunbot-c2rust run [-g <llm-group>] [-m <max-retries>]

Or (module mode):
  python -m haijunbot.haijunbot_c2rust.eli <subcommand>

Notes:
- All paths are recommended to use the standard file names under <project_root>/.haijunbot/c2rust, to facilitate checkpoint resume and reuse.
"""

__all__ = ["scanner", "optimizer"]
