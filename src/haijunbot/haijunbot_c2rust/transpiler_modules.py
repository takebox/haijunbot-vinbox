# -*- coding: utf-8 -*-
"""
Module management module
"""

from haijunbot.haijunbot_utils.exception_utils import save_exception
import re
from pathlib import Path
from typing import Optional

from haijunbot.haijunbot_utils.output import PrettyOutput


class ModuleManager:
    """Module manager"""

    def __init__(self, crate_dir: Path) -> None:
        self.crate_dir = crate_dir

    def ensure_cargo_toml_cdylib(self) -> None:
        """
        Ensure that a [lib] configuration exists in Cargo.toml and that crate-type includes "cdylib".
        If [lib] does not exist, create it; if it exists but has no crate-type, add it; if it exists but crate-type does not include "cdylib", add it.
        Note: "cdylib" and "rlib" may both be included, as long as "cdylib" is included.
        """
        try:
            cargo_path = (self.crate_dir / "Cargo.toml").resolve()
            if not cargo_path.exists():
                # If Cargo.toml does not exist, create a minimal configuration
                pkg_name = self.crate_dir.name
                content = (
                    f'[package]\nname = "{pkg_name}"\nversion = "0.1.0"\nedition = "2021"\n\n'
                    '[lib]\npath = "src/lib.rs"\ncrate-type = ["cdylib", "rlib"]\n\n'
                )
                cargo_path.write_text(content, encoding="utf-8")
                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][cargo] Created Cargo.toml and set cdylib and rlib: {cargo_path}"
                )
                return

            # Read the existing content
            txt = cargo_path.read_text(encoding="utf-8", errors="replace")

            # Check whether a [lib] block exists
            lib_match = re.search(r"(?m)^\s*\[lib\]\s*$", txt)
            if not lib_match:
                # No [lib] block exists; add one
                # Prefer adding after [package]
                pkg_match = re.search(r"(?m)^\s*\[package\]\s*$", txt)
                deps_match = re.search(r"(?m)^\s*\[dependencies\]\s*$", txt)
                if pkg_match:
                    # Add after the [package] block
                    insert_pos = txt.find("\n", pkg_match.end())
                    if insert_pos == -1:
                        insert_pos = len(txt)
                    # Find the end position of the [package] block
                    next_section = re.search(r"(?m)^\s*\[", txt[insert_pos:])
                    if next_section:
                        insert_pos = insert_pos + next_section.start()
                    lib_config = '\n[lib]\npath = "src/lib.rs"\ncrate-type = ["cdylib", "rlib"]\n'
                    new_txt = txt[:insert_pos] + lib_config + txt[insert_pos:]
                elif deps_match:
                    # Add before [dependencies]
                    insert_pos = deps_match.start()
                    lib_config = '\n[lib]\npath = "src/lib.rs"\ncrate-type = ["cdylib", "rlib"]\n'
                    new_txt = txt[:insert_pos] + lib_config + txt[insert_pos:]
                else:
                    # Add at the end of the file
                    lib_config = '\n[lib]\npath = "src/lib.rs"\ncrate-type = ["cdylib", "rlib"]\n'
                    new_txt = txt.rstrip() + lib_config
                cargo_path.write_text(new_txt, encoding="utf-8")
                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][cargo] Added [lib] configuration in Cargo.toml and set cdylib and rlib: {cargo_path}"
                )
                return

            # A [lib] block exists; check crate-type
            lib_start = lib_match.start()
            # Find the end position of the [lib] block (the next [ or the end of the file)
            lib_end_match = re.search(r"(?m)^\s*\[", txt[lib_match.end() :])
            if lib_end_match:
                lib_end = lib_match.end() + lib_end_match.start()
            else:
                lib_end = len(txt)

            lib_block = txt[lib_start:lib_end]

            # Check whether crate-type already exists
            crate_type_match = re.search(
                r"crate-type\s*=\s*\[([^\]]+)\]", lib_block, re.MULTILINE
            )
            if crate_type_match:
                # crate-type already exists; check whether it includes "cdylib"
                crate_types_str = crate_type_match.group(1)
                crate_types = [
                    t.strip().strip('"').strip("'") for t in crate_types_str.split(",")
                ]
                if "cdylib" not in crate_types:
                    # Add "cdylib" (keep existing types such as rlib)
                    crate_types.append("cdylib")
                    new_crate_types_str = ", ".join(f'"{ct}"' for ct in crate_types)
                    new_lib_block = lib_block.replace(
                        crate_type_match.group(0),
                        f"crate-type = [{new_crate_types_str}]",
                    )
                    new_txt = txt[:lib_start] + new_lib_block + txt[lib_end:]
                    cargo_path.write_text(new_txt, encoding="utf-8")
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][cargo] Added cdylib in the [lib] of Cargo.toml (keeping existing types): {cargo_path}"
                    )
            else:
                # No crate-type; add one
                # Add crate-type at the end of the [lib] block (after path)
                path_match = re.search(r'path\s*=\s*["\'][^"\']+["\']', lib_block)
                if path_match:
                    # Add after path
                    insert_pos_in_block = path_match.end()
                    new_lib_block = (
                        lib_block[:insert_pos_in_block]
                        + '\ncrate-type = ["cdylib", "rlib"]'
                        + lib_block[insert_pos_in_block:]
                    )
                else:
                    # No path; add directly after [lib]
                    new_lib_block = (
                        lib_block.rstrip() + '\ncrate-type = ["cdylib", "rlib"]\n'
                    )
                new_txt = txt[:lib_start] + new_lib_block + txt[lib_end:]
                cargo_path.write_text(new_txt, encoding="utf-8")
                PrettyOutput.auto_print(
                    f'✅ [c2rust-transpiler][cargo] Added crate-type = ["cdylib", "rlib"] in the [lib] of Cargo.toml: {cargo_path}'
                )
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][cargo] Failed to update Cargo.toml to add cdylib: {e}"
            )

    def ensure_cargo_toml_bin(
        self, bin_path: str, bin_name: Optional[str] = None
    ) -> None:
        """
        Ensure that a [[bin]] configuration exists in Cargo.toml.
        - bin_path: path of the binary file, relative to the crate root (such as "src/bin/main.rs" or "src/bin/app.rs")
        - bin_name: binary name; if None, derived from bin_path
        """
        try:
            cargo_path = (self.crate_dir / "Cargo.toml").resolve()
            if not cargo_path.exists():
                # If Cargo.toml does not exist, create a minimal configuration
                pkg_name = self.crate_dir.name
                content = (
                    f'[package]\nname = "{pkg_name}"\nversion = "0.1.0"\nedition = "2021"\n\n'
                    '[lib]\npath = "src/lib.rs"\n\n'
                )
                cargo_path.write_text(content, encoding="utf-8")
                PrettyOutput.auto_print(
                    f"✅ [c2rust-transpiler][cargo] Created Cargo.toml: {cargo_path}"
                )

            # Read the existing content
            txt = cargo_path.read_text(encoding="utf-8", errors="replace")

            # Derive bin_name from bin_path
            if bin_name is None:
                # Extract the file name from the path (remove the .rs suffix)
                bin_path_clean = bin_path.replace("\\", "/")
                if bin_path_clean.startswith("src/bin/"):
                    bin_name = bin_path_clean[len("src/bin/") :]
                    if bin_name.endswith(".rs"):
                        bin_name = bin_name[:-3]
                else:
                    # If the path is not in src/bin/ format, use the default name
                    bin_name = self.crate_dir.name

            # Check whether an identical [[bin]] configuration already exists
            # Match [[bin]] blocks and look up name and path
            bin_pattern = re.compile(
                r"\[\[bin\]\]\s*\n(?:[^\[]*(?:\n[^\[]*)*?)(?=\[\[bin\]\]|\[\[|\[|$)",
                re.MULTILINE,
            )
            existing_bins = bin_pattern.findall(txt)

            # Check whether a bin with the same path already exists
            for bin_block in existing_bins:
                # Check the path field
                path_match = re.search(r'path\s*=\s*["\']([^"\']+)["\']', bin_block)
                if path_match and path_match.group(1) == bin_path:
                    # A bin configuration with the same path already exists
                    return
                # Check the name field
                name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', bin_block)
                if name_match and name_match.group(1) == bin_name:
                    # A bin with the same name already exists; check whether the path is the same
                    if path_match and path_match.group(1) == bin_path:
                        # Identical configuration; no need to add
                        return
                    # The name is the same but the path differs; it may need updating, but to be safe we still add a new configuration
                    # (since there may be multiple bins with the same name but different paths)

            # Add the [[bin]] configuration
            bin_config = f'\n[[bin]]\nname = "{bin_name}"\npath = "{bin_path}"\n'

            # Add at the end of the file (if other configuration exists, insert at an appropriate position)
            # Prefer adding after [lib]; if it does not exist, add before [dependencies]
            lib_match = re.search(r"(?m)^\s*\[lib\]\s*$", txt)
            deps_match = re.search(r"(?m)^\s*\[dependencies\]\s*$", txt)

            if lib_match:
                # Add after the [lib] block
                insert_pos = txt.find("\n", lib_match.end())
                if insert_pos == -1:
                    insert_pos = len(txt)
                # Find the end position of the [lib] block
                next_section = re.search(r"(?m)^\s*\[", txt[insert_pos:])
                if next_section:
                    insert_pos = insert_pos + next_section.start()
                new_txt = txt[:insert_pos] + bin_config + txt[insert_pos:]
            elif deps_match:
                # Add before [dependencies]
                insert_pos = deps_match.start()
                new_txt = txt[:insert_pos] + bin_config + txt[insert_pos:]
            else:
                # Add at the end of the file
                new_txt = txt.rstrip() + bin_config

            cargo_path.write_text(new_txt, encoding="utf-8")
            PrettyOutput.auto_print(
                f"✅ [c2rust-transpiler][cargo] Added [[bin]] configuration in Cargo.toml: name={bin_name}, path={bin_path}"
            )
        except Exception as e:
            PrettyOutput.auto_print(
                f"⚠️ [c2rust-transpiler][cargo] Failed to update Cargo.toml: {e}"
            )

    def ensure_top_level_pub_mod(self, mod_name: str) -> None:
        """
        Ensure that `pub mod <mod_name>;` exists in src/lib.rs
        - If `pub mod` already exists, make no changes
        - If `mod <mod_name>;` exists, upgrade it to `pub mod <mod_name>;`
        - If neither exists, append a line `pub mod <mod_name>;` at the end of the file
        - Minimal changes; do not overwrite other content
        """
        try:
            if not mod_name or mod_name in ("lib", "main", "mod", "bin"):
                return
            lib_rs = (self.crate_dir / "src" / "lib.rs").resolve()
            lib_rs.parent.mkdir(parents=True, exist_ok=True)
            if not lib_rs.exists():
                try:
                    lib_rs.write_text(
                        "// Auto-generated by c2rust transpiler\n", encoding="utf-8"
                    )
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][mod] Created src/lib.rs: {lib_rs}"
                    )
                except Exception:
                    return
            txt = lib_rs.read_text(encoding="utf-8", errors="replace")
            pub_pat = re.compile(rf"(?m)^\s*pub\s+mod\s+{re.escape(mod_name)}\s*;\s*$")
            mod_pat = re.compile(rf"(?m)^\s*mod\s+{re.escape(mod_name)}\s*;\s*$")
            if pub_pat.search(txt):
                return
            if mod_pat.search(txt):
                # Upgrade to pub mod (keep the original indentation)
                def _repl(m: re.Match) -> str:
                    line = m.group(0)
                    match = re.match(r"^(\s*)", line)
                    ws = match.group(1) if match else ""
                    return f"{ws}pub mod {mod_name};"

                new_txt = mod_pat.sub(_repl, txt, count=1)
            else:
                new_txt = txt.rstrip() + f"\npub mod {mod_name};\n"
            lib_rs.write_text(new_txt, encoding="utf-8")
            PrettyOutput.auto_print(
                f"✅ [c2rust-transpiler][mod] updated src/lib.rs: ensured pub mod {mod_name}"
            )
        except Exception:
            # Stay robust; a failure does not block the main flow
            pass

    def ensure_mod_rs_decl(self, dir_path: Path, child_mod: str) -> None:
        """
        Ensure that `pub mod <child_mod>;` exists in dir_path/mod.rs
        - If `mod <child_mod>;` exists, upgrade it to `pub mod <child_mod>;`
        - If neither exists, append `pub mod <child_mod>;` at the end of the file
        - Minimal changes; do not overwrite other content
        """
        try:
            if not child_mod or child_mod in ("lib", "main", "mod", "bin"):
                return
            mod_rs = (dir_path / "mod.rs").resolve()
            mod_rs.parent.mkdir(parents=True, exist_ok=True)
            if not mod_rs.exists():
                try:
                    mod_rs.write_text(
                        "// Auto-generated by c2rust transpiler\n", encoding="utf-8"
                    )
                    PrettyOutput.auto_print(
                        f"✅ [c2rust-transpiler][mod] Created {mod_rs}"
                    )
                except Exception:
                    return
            txt = mod_rs.read_text(encoding="utf-8", errors="replace")
            pub_pat = re.compile(rf"(?m)^\s*pub\s+mod\s+{re.escape(child_mod)}\s*;\s*$")
            mod_pat = re.compile(rf"(?m)^\s*mod\s+{re.escape(child_mod)}\s*;\s*$")
            if pub_pat.search(txt):
                return
            if mod_pat.search(txt):
                # Upgrade to pub mod (keep the original indentation)
                def _repl(m: re.Match) -> str:
                    line = m.group(0)
                    match = re.match(r"^(\s*)", line)
                    ws = match.group(1) if match else ""
                    return f"{ws}pub mod {child_mod};"

                new_txt = mod_pat.sub(_repl, txt, count=1)
            else:
                new_txt = txt.rstrip() + f"\npub mod {child_mod};\n"
            mod_rs.write_text(new_txt, encoding="utf-8")
            PrettyOutput.auto_print(
                f"✅ [c2rust-transpiler][mod] updated {mod_rs}: ensured pub mod {child_mod}"
            )
        except Exception as e:
            save_exception(
                e, module="haijunbot_c2rust.transpiler_modules", function="_repl"
            )
            pass

    def ensure_mod_chain_for_module(self, module: str) -> None:
        """
        Based on the target module file, complete the mod.rs declaration chain upward from the file's directory:
        - For src/foo/bar.rs: ensure `pub mod bar;` in src/foo/mod.rs,
          and in the upper level src/mod.rs (unmodified), instead ensure `pub mod foo;` in src/lib.rs (handled by the top-level function)
        - For src/foo/bar/mod.rs: ensure `pub mod bar;` in src/foo/mod.rs
        - For multi-level directories, ensure `pub mod <child>;` for the subdirectory in the upper-level mod.rs level by level
        """
        try:
            mp = Path(module)
            base = mp
            if not mp.is_absolute():
                base = (self.crate_dir / module).resolve()
            crate_root = self.crate_dir.resolve()
            # Must be under crate/src
            rel = base.relative_to(crate_root)
            rel_s = str(rel).replace("\\", "/")
            if not rel_s.startswith("src/"):
                return
            # Compute the starting directory and the first submodule name
            inside = rel_s[len("src/") :].strip("/")
            if not inside:
                return
            parts = [p for p in inside.split("/") if p]  # Filter out empty strings
            # Special handling: if the path contains bin/, do not generate a mod declaration
            if "bin" in parts:
                return
            if parts[-1].endswith(".rs"):
                if parts[-1] in ("lib.rs", "main.rs"):
                    return
                child = parts[-1][:-3]  # Remove .rs
                # Filter out the "mod" and "bin" keywords
                if child in ("mod", "bin"):
                    return
                if len(parts) > 1:
                    start_dir = crate_root / "src" / "/".join(parts[:-1])
                else:
                    start_dir = crate_root / "src"
                # Ensure start_dir is under crate/src
                try:
                    start_dir_rel = start_dir.relative_to(crate_root)
                    if not str(start_dir_rel).replace("\\", "/").startswith("src/"):
                        return
                except ValueError:
                    return
                # Ensure pub mod <child> in the mod.rs of the current directory
                if start_dir.name != "src":
                    self.ensure_mod_rs_decl(start_dir, child)
                # Level by level ensure the parent directory's pub mod declaration for the current directory
                cur_dir = start_dir
            else:
                # The end is a directory (mod.rs case): ensure the parent directory's pub mod for that directory
                if parts:
                    cur_dir = crate_root / "src" / "/".join(parts)
                    # Ensure cur_dir is under crate/src
                    try:
                        cur_dir_rel = cur_dir.relative_to(crate_root)
                        if not str(cur_dir_rel).replace("\\", "/").startswith("src/"):
                            return
                    except ValueError:
                        return
                else:
                    return
            # Level by level up to the src root (do not modify src/mod.rs; the top level is exposed by lib.rs)
            while True:
                parent = cur_dir.parent
                if not parent.exists():
                    break
                # Ensure it does not go above the crate root directory
                try:
                    parent.relative_to(crate_root)
                except ValueError:
                    # parent is not under crate_root; stop traversing upward
                    break
                if parent.name == "src":
                    # The top level is handled by _ensure_top_level_pub_mod
                    break
                # Ensure pub mod <cur_dir.name> in parent/mod.rs
                # Ensure parent is under crate/src
                # Filter out the "mod" and "bin" keywords
                if cur_dir.name in ("mod", "bin"):
                    cur_dir = parent
                    continue
                try:
                    parent_rel = parent.relative_to(crate_root)
                    if str(parent_rel).replace("\\", "/").startswith("src/"):
                        self.ensure_mod_rs_decl(parent, cur_dir.name)
                except (ValueError, Exception):
                    # parent is not under crate/src; skip
                    break
                cur_dir = parent
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_modules",
                function="ensure_mod_chain_for_module",
            )
            pass

    def module_file_to_crate_path(self, module: str) -> str:
        """
        Convert a module file path to a crate path prefix:
        - src/lib.rs -> crate
        - src/foo/mod.rs -> crate::foo
        - src/foo/bar.rs -> crate::foo::bar
        Supports absolute paths: if module is an absolute path located under the crate root, it is automatically converted to a relative path before parsing;
        others (paths that cannot be resolved under crate/src) uniformly return 'crate'
        """
        mod = str(module).strip()
        # If an absolute path under crate_dir is passed in, convert it to a relative path so it can later be parsed by the src/ prefix
        try:
            mp = Path(mod)
            if mp.is_absolute():
                try:
                    rel = mp.resolve().relative_to(self.crate_dir.resolve())
                    mod = str(rel).replace("\\", "/")
                except Exception:
                    # The absolute path is not under crate_dir; keep it as is
                    pass
        except Exception as e:
            save_exception(
                e,
                module="haijunbot_c2rust.transpiler_modules",
                function="module_file_to_crate_path",
            )
            pass
        # Normalize the ./ prefix
        if mod.startswith("./"):
            mod = mod[2:]
        # Only handle module files located under src/
        if not mod.startswith("src/"):
            return "crate"
        p = mod[len("src/") :]
        if p.endswith("mod.rs"):
            p = p[: -len("mod.rs")]
        elif p.endswith(".rs"):
            p = p[: -len(".rs")]
        p = p.strip("/")
        return "crate" if not p else "crate::" + p.replace("/", "::")
