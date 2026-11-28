#!/usr/bin/env python3
"""
PlantUML Extraction and Write-Back Script

Features:
1. Extract PlantUML code blocks from Markdown files into separate .puml files
2. Write fixed .puml file content back to Markdown files

Usage:
    # Extract PlantUML code blocks
    python3 plantuml_fix.py extract <markdown_file> [-o output_dir]

    # Validate .puml files (call plantuml program)
    python3 plantuml_fix.py validate <puml_file_or_dir>

    # Write .puml file content back to Markdown file
    python3 plantuml_fix.py writeback <markdown_file> <puml_dir>

Workflow:
    1. extract: Extract PlantUML from MD to .puml files
    2. Use plantuml program to validate/edit .puml files
    3. writeback: Write fixed .puml back to MD
"""

import argparse
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


class PlantUMLBlock:
    """Represents a PlantUML code block"""

    def __init__(self, content: str, start_line: int, end_line: int, index: int):
        self.content = content
        self.start_line = start_line
        self.end_line = end_line
        self.index = index

    def __repr__(self):
        return f"PlantUMLBlock(index={self.index}, lines {self.start_line}-{self.end_line})"


class PlantUMLExtractor:
    """PlantUML code block extractor"""

    PLANTUML_PATTERN = re.compile(r"```plantuml\s*\n((?:.*\n)*?)\s*```", re.MULTILINE)

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[INFO] {message}")

    def _error(self, message: str):
        print(f"[ERROR] {message}", file=sys.stderr)

    def extract_blocks(self, content: str) -> List[PlantUMLBlock]:
        """Extract PlantUML code blocks from Markdown content"""
        blocks = []
        for i, match in enumerate(self.PLANTUML_PATTERN.finditer(content)):
            code = match.group(1)
            start_line = content[: match.start()].count("\n") + 1
            end_line = content[: match.end()].count("\n") + 1
            blocks.append(PlantUMLBlock(code, start_line, end_line, i))
        return blocks

    def extract_to_files(
        self, md_file: str, output_dir: Optional[str] = None
    ) -> List[str]:
        """Extract PlantUML code blocks from Markdown file to .puml files"""
        md_path = Path(md_file)
        if not md_path.exists():
            self._error(f"File does not exist: {md_file}")
            return []

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self._error(f"Cannot read file: {e}")
            return []

        blocks = self.extract_blocks(content)
        if not blocks:
            print(f"No PlantUML code blocks found in file {md_file}")
            return []

        if output_dir:
            out_dir = Path(output_dir)
        else:
            # Default to temp directory to avoid git tracking
            import tempfile

            out_dir = Path(tempfile.gettempdir()) / f"plantuml_{md_path.stem}"

        out_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        for block in blocks:
            puml_file = out_dir / f"{md_path.stem}_{block.index}.puml"
            content_to_write = block.content
            if "@startuml" not in content_to_write:
                content_to_write = "@startuml\n" + content_to_write
            if "@enduml" not in content_to_write:
                content_to_write = content_to_write.rstrip() + "\n@enduml"

            try:
                with open(puml_file, "w", encoding="utf-8") as f:
                    f.write(content_to_write)
                created_files.append(str(puml_file))
                self._log(f"Created: {puml_file}")
            except Exception as e:
                self._error(f"Cannot write {puml_file}: {e}")

        print(f"\nExtraction complete: Extracted {len(created_files)} PlantUML code blocks from {md_file}")
        print(f"Output directory: {out_dir}")
        print("\nNext step: Use plantuml program to validate these files:")
        print(f"  plantuml -checkonly {out_dir}/*.puml")

        return created_files


class PlantUMLValidator:
    """PlantUML validator"""

    def __init__(self, plantuml_cmd: str = "plantuml", verbose: bool = False):
        self.plantuml_cmd = plantuml_cmd
        self.verbose = verbose

    def validate_file(self, puml_path: str) -> Tuple[bool, Optional[str]]:
        """Validate a single .puml file"""
        try:
            # argv list + shell=False: plantuml dijalankan langsung, bukan lewat
            # cmd.exe/bash yang menafsirkan tanda kutip.
            cmd = shlex.split(self.plantuml_cmd) + ["-checkonly", str(puml_path)]
            result = subprocess.run(
                cmd, shell=False, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr or result.stdout
        except subprocess.TimeoutExpired:
            return False, "Validation timeout"
        except Exception as e:
            return False, str(e)

    def validate_directory(self, dir_path: str) -> dict:
        """Validate all .puml files in a directory"""
        dir_obj = Path(dir_path)
        if not dir_obj.is_dir():
            print(f"[ERROR] Directory does not exist: {dir_path}", file=sys.stderr)
            return {}

        puml_files = sorted(dir_obj.glob("*.puml"))
        if not puml_files:
            print(f"No .puml files found in directory {dir_path}")
            return {}

        print(f"\nValidating {len(puml_files)} .puml files...\n")
        results = {}
        for puml_file in puml_files:
            is_valid, error = self.validate_file(str(puml_file))
            results[str(puml_file)] = {"valid": is_valid, "error": error}
            status = "✓ Pass" if is_valid else "✗ Fail"
            print(f"{status}: {puml_file.name}")
            if error:
                print(
                    f"  Error: {error[:200]}"
                    if len(error) <= 200
                    else f"  Error: {error[:200]}..."
                )

        valid_count = sum(1 for r in results.values() if r["valid"])
        print(f"\nValidation complete: {valid_count}/{len(results)} passed")
        return results


class PlantUMLWriter:
    """Write .puml file content back to Markdown"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str):
        if self.verbose:
            print(f"[INFO] {message}")

    def _error(self, message: str):
        print(f"[ERROR] {message}", file=sys.stderr)

    def writeback(self, md_file: str, puml_dir: str, backup: bool = True) -> bool:
        """Write .puml file content back to Markdown file"""
        md_path = Path(md_file)
        puml_path = Path(puml_dir)

        if not md_path.exists():
            self._error(f"Markdown file does not exist: {md_file}")
            return False
        if not puml_path.is_dir():
            self._error(f".puml directory does not exist: {puml_dir}")
            return False

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            self._error(f"Cannot read MD file: {e}")
            return False

        puml_files = sorted(puml_path.glob(f"{md_path.stem}_*.puml"))
        if not puml_files:
            self._log(f"No matching .puml files found: {md_path.stem}_*.puml")
            return False

        puml_contents = {}
        for puml_file in puml_files:
            match = re.search(r"_(\d+)\.puml$", puml_file.name)
            if match:
                index = int(match.group(1))
                try:
                    with open(puml_file, "r", encoding="utf-8") as f:
                        puml_content = f.read()
                    # Keep @startuml/@enduml, need complete content for writeback
                    # puml_content = re.sub(r"^@startuml[^\n]*\n?", "", puml_content)
                    # puml_content = re.sub(r"\n?@enduml[^\n]*\n?$", "", puml_content)
                    puml_contents[index] = puml_content
                    self._log(f"Read: {puml_file.name}")
                except Exception as e:
                    self._error(f"Cannot read {puml_file}: {e}")

        pattern = re.compile(r"(```plantuml\s*\n)((?:.*\n)*?)(\s*```)", re.MULTILINE)
        new_content = content
        offset = 0

        for i, match in enumerate(pattern.finditer(content)):
            if i in puml_contents:
                # Ensure writeback content ends with newline to avoid content sticking to ```
                replacement = puml_contents[i]
                if not replacement.endswith("\n"):
                    replacement += "\n"
                start = match.start(2) + offset
                end = match.end(2) + offset
                new_content = new_content[:start] + replacement + new_content[end:]
                offset += len(replacement) - len(match.group(2))
                self._log(f"Updated code block {i}")

        if backup:
            backup_path = str(md_path) + ".bak"
            shutil.copy2(md_path, backup_path)
            self._log(f"Backup: {backup_path}")

        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"\nWriteback complete: {md_file}")
            print(f"Updated {len(puml_contents)} PlantUML code blocks")
            return True
        except Exception as e:
            self._error(f"Cannot write MD file: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="PlantUML Extraction, Validation and Write-Back Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  1. Extract: python3 plantuml_fix.py extract document.md
  2. Validate: plantuml -checkonly document_plantuml/*.puml
  3. Fix: Manually edit .puml files to fix errors
  4. Writeback: python3 plantuml_fix.py writeback document.md document_plantuml/

Examples:
  %(prog)s extract README.md                    # Extract to README_plantuml/ directory
  %(prog)s extract README.md -o uml/            # Extract to specified directory
  %(prog)s validate README_plantuml/            # Validate all .puml files
  %(prog)s writeback README.md README_plantuml/ # Write back fixed content
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommands")

    extract_parser = subparsers.add_parser(
        "extract", help="Extract PlantUML code blocks from Markdown"
    )
    extract_parser.add_argument("markdown_file", help="Markdown file path")
    extract_parser.add_argument("-o", "--output", help="Output directory")
    extract_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    validate_parser = subparsers.add_parser("validate", help="Validate .puml files")
    validate_parser.add_argument("path", help=".puml file or directory path")
    validate_parser.add_argument(
        "--plantuml", default="plantuml", help="plantuml program path"
    )

    writeback_parser = subparsers.add_parser(
        "writeback", help="Write .puml content back to Markdown"
    )
    writeback_parser.add_argument("markdown_file", help="Markdown file path")
    writeback_parser.add_argument("puml_dir", help=".puml file directory")
    writeback_parser.add_argument("--no-backup", action="store_true", help="Do not create backup")
    writeback_parser.add_argument(
        "-v", "--verbose", action="store_true", help="Verbose output"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "extract":
        extractor = PlantUMLExtractor(verbose=args.verbose)
        extractor.extract_to_files(args.markdown_file, args.output)

    elif args.command == "validate":
        validator = PlantUMLValidator(plantuml_cmd=args.plantuml)
        path = Path(args.path)
        if path.is_file():
            is_valid, error = validator.validate_file(str(path))
            if is_valid:
                print(f"✓ Pass: {path}")
            else:
                print(f"✗ Fail: {path}")
                print(f"  Error: {error}")
                sys.exit(1)
        elif path.is_dir():
            results = validator.validate_directory(str(path))
            if any(not r["valid"] for r in results.values()):
                sys.exit(1)
        else:
            print(f"[ERROR] Path does not exist: {args.path}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "writeback":
        writer = PlantUMLWriter(verbose=args.verbose)
        success = writer.writeback(
            args.markdown_file, args.puml_dir, backup=not args.no_backup
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()