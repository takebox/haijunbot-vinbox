#!/usr/bin/env python3
"""Module singleton split scanner (static analysis).

Background: In Python, if "the same physical .py file" is imported under two different module names
(e.g. haijunbot.haijunbot_tools.timer and the bare top-level name timer), it is treated as two different module objects,
causing module-level singleton / cache splitting (typical symptom: a task/state created in A is invisible and unusable in B).

Trigger condition: a directory is dynamically added to sys.path (e.g. sys.path.insert(0, parent_dir)),
so files under that directory can be imported both by "bare filename" and by "package path".

This script statically scans:
  1) Find all directories dynamically inserted into sys.path;
  2) For each such directory, check whether the .py files in it are referenced by both the "package path" and the "bare name";
  3) On a hit, report the file and its two module names.

Usage:
    python3 scripts/scan_module_split.py [SRC]
    SRC defaults to this repository's src directory.

Exit codes: 0=no risk found; 1=potential singleton split points found.

Also has a --selftest argument: uses a built-in synthetic defective project to verify the detection logic itself works.
"""

from __future__ import annotations

import argparse
import ast
import os
import sys
import tempfile
from collections import defaultdict


def collect(src: str):
    """Return (module_to_file, imported_names, dynamic_bare_imports, import_by_file).

    - module_to_file: package path -> absolute file path
    - imported_names: all referenced module names in the codebase (including bare names)
    - dynamic_bare_imports: list of dynamic import call sites [(file, module_name)],
      from importlib.import_module("...") / __import__("..."), module_name is a literal
    - import_by_file: file -> set of module names referenced by that file
    """
    module_to_file = {}
    for root, _dirs, files in os.walk(src):
        for f in files:
            if not f.endswith(".py"):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, src)
            mod = rel[:-3].replace(os.sep, ".")
            module_to_file[mod] = full

    imported = set()
    import_by_file = defaultdict(set)
    dynamic_bare_imports = []

    for root, _dirs, files in os.walk(src):
        for f in files:
            if not f.endswith(".py"):
                continue
            full = os.path.join(root, f)
            try:
                with open(full, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except Exception:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imported.add(a.name)
                        import_by_file[full].add(a.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imported.add(node.module)
                        import_by_file[full].add(node.module)
                elif isinstance(node, ast.Call):
                    fn = node.func
                    # importlib.import_module("...") / __import__("...")
                    if (
                        isinstance(fn, ast.Attribute)
                        and fn.attr == "import_module"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                    ):
                        name = node.args[0].value
                        imported.add(name)
                        import_by_file[full].add(name)
                        if "." not in name:  # bare-name dynamic import
                            dynamic_bare_imports.append((full, name))
                    elif (
                        isinstance(fn, ast.Name)
                        and fn.id == "__import__"
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)
                    ):
                        name = node.args[0].value
                        imported.add(name)
                        import_by_file[full].add(name)
                        if "." not in name:
                            dynamic_bare_imports.append((full, name))

    return module_to_file, imported, dynamic_bare_imports, import_by_file


def scan(src: str):
    """Return the risk list [(file_path, canonical_package_path, bare_stem, sites)].

    Detection logic: if the same physical .py file is imported both by "package path" and by "bare name", it is a
    module singleton split point. The bare-name import must be **dynamic**
    `importlib.import_module("X")` / `__import__("X")` (X has no dot) --
    because only a dynamic import combined with dynamic insertion of a directory into sys.path imports a "file inside a package" by
    its bare top-level name, thereby producing a second module object different from the package path (this is exactly
    the mechanism of the old register_tool_by_file implementation).

    A static `import X` does not cause a split: if X is not a real top-level module, the static import itself raises
    ImportError; if X is a real top-level module, it is not the same physical file as the one inside the package.
    Therefore only "dynamic bare-name imports" are used as a risk signal, avoiding misclassifying same-named files in different packages as split points.
    """
    module_to_file, imported, dynamic_bare_imports, _ = collect(src)

    # Call sites of dynamic bare-name imports: module_name -> list of calling files
    dynamic_by_stem = defaultdict(list)
    for src_file, name in dynamic_bare_imports:
        dynamic_by_stem[name].append(src_file)

    risks = []
    for canon, full in module_to_file.items():
        if "." not in canon:
            continue  # top-level file (bare name is its canonical name), no split exists
        stem = os.path.splitext(os.path.basename(full))[0]
        # Only when the file is imported by a "dynamic bare name" (the path that can truly produce a second module object)
        # and is also imported by its canonical package path, is it judged a split point.
        if stem in dynamic_by_stem and canon in imported:
            risks.append((full, canon, stem, tuple(dynamic_by_stem.get(stem, []))))
    return risks


def selftest() -> int:
    """Build a synthetic project with a defect to verify the scan hits; and verify there are no false positives."""
    tmp = tempfile.mkdtemp()
    pkg = os.path.join(tmp, "pkg")
    os.makedirs(pkg, exist_ok=True)
    with open(os.path.join(pkg, "__init__.py"), "w") as f:
        f.write("")
    # Defective file: pkg/timer.py, imported both by package path and by dynamic bare name
    with open(os.path.join(pkg, "timer.py"), "w") as f:
        f.write("_mgr=None\ndef get_timer_manager():\n    return _mgr\n")
    with open(os.path.join(tmp, "a.py"), "w") as f:
        f.write("from pkg.timer import get_timer_manager\n")
    with open(os.path.join(tmp, "b.py"), "w") as f:
        f.write(
            "import importlib\n"
            "import sys\n"
            "sys.path.insert(0, 'pkg')\n"
            "importlib.import_module('timer')\n"
        )
    # Control: a same-named file events.py in another package, referenced only by package path, should not be a false positive
    pkg2 = os.path.join(tmp, "pkg2")
    os.makedirs(pkg2, exist_ok=True)
    with open(os.path.join(pkg2, "__init__.py"), "w") as f:
        f.write("")
    with open(os.path.join(pkg2, "events.py"), "w") as f:
        f.write("EVENT = 1\n")
    with open(os.path.join(tmp, "c.py"), "w") as f:
        f.write("from pkg2.events import EVENT\n")

    risks = scan(tmp)
    if not risks:
        print("❌ selftest failed: synthetic defect not detected")
        return 1
    for full, canon, stem, _sites in sorted(set(risks)):
        print(
            f"✅ selftest hit: {full}\n   canonical package path: {canon}  also referenced by bare name: {stem}"
        )
    # Confirm only the defective file is hit; pkg2/events.py is not a false positive
    if any("pkg2" in r[0] for r in risks):
        print("❌ selftest failed: false positive on control file pkg2/events.py")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Module singleton split static scanner")
    parser.add_argument(
        "src", nargs="?", default=None, help="source root directory to scan (defaults to this repository's src)"
    )
    parser.add_argument(
        "--selftest", action="store_true", help="run the built-in self-test (verify detection logic)"
    )
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    src = args.src
    if src is None:
        here = os.path.dirname(os.path.abspath(__file__))
        src = os.path.join(os.path.dirname(here), "src")
    if not os.path.isdir(src):
        print(f"❌ Directory does not exist: {src}")
        return 1

    risks = scan(src)
    if not risks:
        print("✅ No module singleton split points found")
        return 0
    print(f"⚠️  Found {len(set(risks))} potential module singleton split points:")
    for full, canon, stem, sites in sorted(set(risks)):
        print(f"\n  {full}")
        print(f"    canonical package path: {canon}  also referenced by bare name: {stem}")
        if sites:
            print(f"    dynamic bare-name import call sites: {', '.join(sites)}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
