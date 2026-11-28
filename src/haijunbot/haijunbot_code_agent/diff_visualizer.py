# -*- coding: utf-8 -*-
"""Improved Diff visualization tool

Provides multiple diff visualization methods to improve the readability of code changes.
"""

import difflib
from typing import List
from typing import Optional
from typing import Union

from rich import box
from rich.color import Color
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from haijunbot.haijunbot_utils.output import emit_output, OutputType


class CustomSyntax(Syntax):
    """Custom Syntax class that overrides the line number color to grey58"""

    def _get_line_numbers_color(self, blend: float = 0.3) -> Color:
        """Returns the fixed grey58 color, consistent with the timestamp color"""
        return Color.parse("grey58")


LANGUAGE_EXTENSION_MAPPING = {
    "py": "python",
    "js": "javascript",
    "ts": "typescript",
    "java": "java",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "c": "c",
    "h": "c",
    "hpp": "cpp",
    "rs": "rust",
    "go": "go",
    "sh": "bash",
    "bash": "bash",
    "zsh": "zsh",
    "html": "html",
    "css": "css",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "xml": "xml",
    "md": "markdown",
    "markdown": "markdown",
    "toml": "toml",
    "dockerfile": "dockerfile",
    "ps1": "powershell",
    "ini": "ini",
    "make": "makefile",
    "mk": "makefile",
}


class DiffVisualizer:
    """Improved Diff visualization tool"""

    def __init__(self, console: Optional[Console] = None):
        """Initialize the visualizer

        Args:
            console: a Rich Console instance, or create a new one if None
        """
        self.console = console or Console()

    def _get_language_by_extension(self, file_path: str) -> str:
        """Infer the programming language from the file extension

        Args:
            file_path: the file path

        Returns:
            The programming language name (for Syntax highlighting)
        """
        if not file_path:
            return "text"

        ext = file_path.lower().split(".")[-1] if "." in file_path else ""
        return LANGUAGE_EXTENSION_MAPPING.get(ext, "text")

    def visualize_unified_diff(
        self,
        diff_text: str,
        file_path: str = "",
        show_line_numbers: bool = True,
        context_lines: int = 3,
    ) -> None:
        """Visualize a unified-format diff (improved version)

        Args:
            diff_text: the git diff output text
            file_path: the file path (used for the title)
            show_line_numbers: whether to show line numbers
            context_lines: the number of context lines
        """
        if not diff_text.strip():
            return

        lines = diff_text.split("\n")

        # Create the table for display
        table = Table(
            show_header=False,
            header_style="bold magenta",
            box=None,  # No border, cleaner look
            padding=(0, 1),
        )

        if show_line_numbers:
            table.add_column("", style="red", width=8, justify="right", overflow="fold")
            table.add_column(
                "", style="green", width=8, justify="right", overflow="fold"
            )
        table.add_column("", width=4, justify="center", overflow="fold")
        table.add_column("", style="white", overflow="fold")

        old_line_num = 0
        new_line_num = 0
        in_hunk = False
        hunk_lines: list = []  # Stores all lines in the current hunk (including context and changes)

        def flush_hunk_context() -> None:
            """Flush the current hunk, showing only context_lines lines of context"""
            nonlocal hunk_lines
            if not hunk_lines:
                return

            # Find the indexes of all changed lines
            change_indices = []
            for idx, (line_type, _, _, _) in enumerate(hunk_lines):
                if line_type in ("-", "+"):
                    change_indices.append(idx)

            if not change_indices:
                # No changes, show only the last context_lines lines of context
                for line_type, old_ln, new_ln, content in hunk_lines[-context_lines:]:
                    if show_line_numbers:
                        table.add_row(
                            str(old_ln),
                            str(new_ln),
                            " ",
                            f"{content}",
                        )
                    else:
                        table.add_row("", " ", f"{content}")
            else:
                # Has changes, show only the context before and after the changes
                first_change_idx = change_indices[0]
                last_change_idx = change_indices[-1]

                # Show the context before the changes (up to context_lines lines)
                pre_context_start = max(0, first_change_idx - context_lines)
                for idx in range(pre_context_start, first_change_idx):
                    _, old_ln, new_ln, content = hunk_lines[idx]
                    if show_line_numbers:
                        table.add_row(
                            str(old_ln),
                            str(new_ln),
                            " ",
                            f"{content}",
                        )
                    else:
                        table.add_row("", " ", f"{content}")

                # Show all changed lines
                for idx in range(first_change_idx, last_change_idx + 1):
                    line_type, old_ln, new_ln, content = hunk_lines[idx]
                    if line_type == "-":
                        if show_line_numbers:
                            table.add_row(
                                str(old_ln) if old_ln else "",
                                "",
                                "[bold red]-[/bold red]",
                                f"[bright_red]{content}[/bright_red]",
                            )
                        else:
                            table.add_row(
                                "",
                                "[bold red]-[/bold red]",
                                f"[bright_red]{content}[/bright_red]",
                            )
                    elif line_type == "+":
                        if show_line_numbers:
                            table.add_row(
                                "",
                                str(new_ln) if new_ln else "",
                                "[bold green]+[/bold green]",
                                f"[bright_green]{content}[/bright_green]",
                            )
                        else:
                            table.add_row(
                                "",
                                "[bold green]+[/bold green]",
                                f"[bright_green]{content}[/bright_green]",
                            )

                # Show the context after the changes (up to context_lines lines)
                post_context_end = min(
                    len(hunk_lines), last_change_idx + 1 + context_lines
                )
                for idx in range(last_change_idx + 1, post_context_end):
                    _, old_ln, new_ln, content = hunk_lines[idx]
                    if show_line_numbers:
                        table.add_row(
                            str(old_ln),
                            str(new_ln),
                            " ",
                            f"{content}",
                        )
                    else:
                        table.add_row("", " ", f"{content}")

            hunk_lines = []

        for line in lines:
            if line.startswith("diff --git") or line.startswith("index"):
                # Skip the diff header
                continue
            elif line.startswith("---"):
                # Old file path
                old_path = line[4:].strip()
                if not file_path and old_path != "/dev/null":
                    file_path = old_path
            elif line.startswith("+++"):
                # New file path
                new_path = line[4:].strip()
                if new_path != "/dev/null":
                    file_path = new_path
            elif line.startswith("@@"):
                # Hunk header - flush the previous hunk
                if in_hunk:
                    flush_hunk_context()

                in_hunk = True
                # Parse the line number info
                parts = line.split("@@")
                if len(parts) >= 2:
                    hunk_info = parts[1].strip()
                    if hunk_info:
                        # Parse format: -old_start,old_count +new_start,new_count
                        old_part = ""
                        new_part = ""
                        for token in hunk_info.split():
                            if token.startswith("-"):
                                old_part = token[1:].split(",")[0]
                            elif token.startswith("+"):
                                new_part = token[1:].split(",")[0]

                        if old_part:
                            try:
                                old_line_num = int(old_part)
                            except ValueError:
                                pass
                        if new_part:
                            try:
                                new_line_num = int(new_part)
                            except ValueError:
                                pass

                # Show the hunk header
                hunk_text = Text(f"[bright_cyan]{line}[/bright_cyan]", style="cyan")
                if show_line_numbers:
                    table.add_row("", "", "", hunk_text)
                else:
                    table.add_row("", "", hunk_text)
            elif in_hunk:
                if line.startswith("-"):
                    # Deleted lines
                    content = line[1:] if len(line) > 1 else ""
                    hunk_lines.append(("-", old_line_num, None, content))
                    old_line_num += 1
                elif line.startswith("+"):
                    # Added lines
                    content = line[1:] if len(line) > 1 else ""
                    hunk_lines.append(("+", None, new_line_num, content))
                    new_line_num += 1
                elif line.startswith(" "):
                    # Unchanged lines (context)
                    content = line[1:] if len(line) > 1 else ""
                    hunk_lines.append((" ", old_line_num, new_line_num, content))
                    old_line_num += 1
                    new_line_num += 1
                elif line.strip() == "\\":
                    # Newline difference at end of file
                    if show_line_numbers:
                        table.add_row(
                            "",
                            "",
                            "",
                            "[bright_yellow]\\ No newline at end of file[/bright_yellow]",
                        )
                    else:
                        table.add_row(
                            "",
                            "",
                            "[bright_yellow]\\ No newline at end of file[/bright_yellow]",
                        )

        # Flush the last hunk
        if in_hunk:
            flush_hunk_context()

        # Show the diff table (wrapped in a Panel)
        if table.rows:
            title = f"📝 {file_path}" if file_path else "Diff"
            panel = Panel(
                table,
                title=title,
                border_style="cyan",
                box=box.HORIZONTALS,
                padding=(0, 1),
            )
            self.console.print(panel)

            # Send to the frontend
            try:
                from haijunbot.haijunbot_utils.output import OutputEvent

                emit_output(
                    OutputEvent(
                        text=diff_text,
                        output_type=OutputType.CODE,
                        lang="diff",
                        timestamp=None,
                        context={
                            "file_path": file_path,
                            "_gateway_skip": True,  # Do not print Gateway-specific data in the terminal
                        },
                    )
                )
            except Exception:
                # Ignore output errors, they do not affect the console display
                pass

    def visualize_statistics(
        self, file_path: str, additions: int, deletions: int, total_changes: int = 0
    ) -> None:
        """Show file change statistics

        Args:
            file_path: the file path
            additions: the number of added lines
            deletions: the number of deleted lines
            total_changes: the total number of changed lines (automatically computed if 0)
        """
        if total_changes == 0:
            total_changes = additions + deletions

        # Create the statistics text
        stats_text = Text()
        stats_text.append(f"📊 {file_path}\n", style="bold cyan")
        stats_text.append("  ", style="bright_white")
        stats_text.append("➕ Additions: ", style="green")
        stats_text.append(f"{additions} lines", style="bold green")
        stats_text.append("  |  ", style="bright_white")
        stats_text.append("➖ Deletions: ", style="red")
        stats_text.append(f"{deletions} lines", style="bold red")
        if total_changes > 0:
            stats_text.append("  |  ", style="bright_white")
            stats_text.append("📈 Total: ", style="cyan")
            stats_text.append(f"{total_changes} lines", style="bold cyan")

        panel = Panel(
            stats_text, border_style="cyan", box=box.HORIZONTALS, padding=(1, 2)
        )
        self.console.print(panel)

    def visualize_syntax_highlighted(
        self, diff_text: str, file_path: str = "", theme: str = "monokai"
    ) -> None:
        """Display the diff with syntax highlighting (keeps the original style but improves it)

        Args:
            diff_text: the git diff output text
            file_path: the file path
            theme: the syntax highlighting theme
        """
        if not diff_text.strip():
            return

        # Use the custom Syntax class with grey58 line numbers
        syntax = CustomSyntax(
            diff_text,
            "diff",
            theme=theme,
            line_numbers=True,
            word_wrap=True,
            background_color="default",
        )

        if file_path:
            panel = Panel(
                syntax,
                title=f"📝 {file_path}",
                border_style="cyan",
                box=box.HORIZONTALS,
                padding=(0, 1),
            )
            self.console.print(panel)
        else:
            self.console.print(syntax)

        # Send to the frontend
        try:
            from haijunbot.haijunbot_utils.output import OutputEvent

            emit_output(
                OutputEvent(
                    text=diff_text,
                    output_type=OutputType.CODE,
                    lang="diff",
                    timestamp=None,
                    context={
                        "file_path": file_path,
                        "_gateway_skip": True,  # Do not print Gateway-specific data in the terminal
                    },
                )
            )
        except Exception:
            # Ignore output errors, they do not affect the console display
            pass

    def visualize_compact(
        self,
        diff_text: str,
        file_path: str = "",
        max_lines: int = 50,
    ) -> None:
        """Compact diff display (suitable for quick previews)

        Args:
            diff_text: the git diff output text
            file_path: the file path
            max_lines: the maximum number of lines to display
        """
        if not diff_text.strip():
            return

        lines = diff_text.split("\n")
        display_lines = lines[:max_lines]

        # Statistics
        additions = sum(
            1
            for line in display_lines
            if line.startswith("+") and not line.startswith("+++")
        )
        deletions = sum(
            1
            for line in display_lines
            if line.startswith("-") and not line.startswith("---")
        )

        # Display the diff (with syntax highlighting, wrapped in a Panel)
        if len(lines) > max_lines:
            remaining = len(lines) - max_lines
            display_text = "\n".join(display_lines)
            display_text += f"\n... ({remaining} lines omitted)"
        else:
            display_text = "\n".join(display_lines)

        syntax = Syntax(
            display_text,
            "diff",
            theme="monokai",
            line_numbers=False,
            word_wrap=True,
        )

        # Build the title (including statistics)
        title = f"📝 {file_path}" if file_path else "Diff"
        if additions > 0 or deletions > 0:
            title += f"  [green]+{additions}[/green] / [red]-{deletions}[/red]"

        panel = Panel(
            syntax,
            title=title,
            border_style="cyan",
            box=box.HORIZONTALS,
            padding=(0, 1),
        )
        self.console.print(panel)

        # Send to the frontend
        try:
            from haijunbot.haijunbot_utils.output import OutputEvent

            emit_output(
                OutputEvent(
                    text=diff_text,
                    output_type=OutputType.CODE,
                    lang="diff",
                    timestamp=None,
                    context={
                        "file_path": file_path,
                        "_gateway_skip": True,  # Do not print Gateway-specific data in the terminal
                    },
                )
            )
        except Exception:
            # Ignore output errors, they do not affect the console display
            pass

    def visualize_side_by_side_summary(
        self,
        old_lines: List[str],
        new_lines: List[str],
        file_path: str = "",
        context_lines: int = 3,
        old_line_map: Optional[List[int]] = None,
        new_line_map: Optional[List[int]] = None,
    ) -> None:
        """Side-by-side summary display (shows only the changed parts, with smart pairing)

        Args:
            old_lines: the list of old file lines
            new_lines: the list of new file lines
            file_path: the file path
            context_lines: the number of context lines
            old_line_map: the old file line number mapping (index corresponds to old_lines index, value is the absolute line number in the file)
            new_line_map: the new file line number mapping (index corresponds to new_lines index, value is the absolute line number in the file)
        """
        # Use difflib.SequenceMatcher for more precise matching
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = matcher.get_opcodes()

        # If no line number mapping is provided, use index+1 as the line number (backward compatibility)
        if old_line_map is None:
            old_line_map = [i + 1 for i in range(len(old_lines))]
        if new_line_map is None:
            new_line_map = [i + 1 for i in range(len(new_lines))]

        # Get the language type for syntax highlighting
        language = self._get_language_by_extension(file_path)

        # Create the side-by-side table - use maximum available width
        table = Table(
            show_header=True,
            header_style="bold magenta",
            box=None,
            padding=(0, 0),  # Remove the internal padding to make the content more compact
            expand=True,  # Make the table fill the available width
        )
        table.add_column(
            "", style="bright_cyan", width=6, justify="right", overflow="fold"
        )
        table.add_column(
            "", style="bright_white", overflow="fold", ratio=10, no_wrap=False
        )  # Enable automatic wrapping, increase the ratio value to get more space
        table.add_column(
            "", style="bright_cyan", width=6, justify="right", overflow="fold"
        )
        table.add_column(
            "", style="bright_white", overflow="fold", ratio=10, no_wrap=False
        )  # Enable automatic wrapping, increase the ratio value to get more space

        additions = 0
        deletions = 0
        has_changes = False

        # Collect data for the frontend display
        diff_rows = []

        for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
            if tag == "equal":
                # Display unchanged lines (grey/dim style), but only up to the context line count
                equal_chunk = old_lines[i1:i2]
                equal_len = len(equal_chunk)

                # Show only the last context_lines lines as context
                if equal_len > context_lines * 2:
                    # If the equal block is too long, show only the beginning and end context
                    if idx > 0:  # Not the first block
                        # Show the beginning context_lines lines
                        for k in range(min(context_lines, equal_len)):
                            old_line_num = (
                                old_line_map[i1 + k]
                                if i1 + k < len(old_line_map)
                                else i1 + k + 1
                            )
                            new_line_num = (
                                new_line_map[j1 + k]
                                if j1 + k < len(new_line_map)
                                else j1 + k + 1
                            )
                            old_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            new_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            table.add_row(
                                f"[bright_cyan]{old_line_num}[/bright_cyan]",
                                old_syntax,
                                f"[bright_cyan]{new_line_num}[/bright_cyan]",
                                new_syntax,
                            )
                            # Collect the data for the frontend
                            diff_rows.append(
                                {
                                    "type": "equal",
                                    "old_line_num": old_line_num,
                                    "old_line": equal_chunk[k],
                                    "new_line_num": new_line_num,
                                    "new_line": equal_chunk[k],
                                }
                            )
                        # If any lines are omitted, show an omission marker
                        if equal_len > context_lines * 2:
                            table.add_row(
                                "",
                                "[bright_yellow]... ({0} lines omitted) ...[/bright_yellow]".format(
                                    equal_len - context_lines * 2
                                ),
                                "",
                                "",
                            )
                            # Add a separator (dynamically adapts to the terminal width)
                            # Subtract some margins to fit the table border and padding
                            separator_width = max(20, self.console.width - 20)
                            table.add_row(
                                "",
                                f"[dim]{'─' * separator_width}[/dim]",
                                "",
                                "",
                            )
                        # Show the ending context_lines lines
                        for k in range(max(0, equal_len - context_lines), equal_len):
                            old_line_num = (
                                old_line_map[i1 + k]
                                if i1 + k < len(old_line_map)
                                else i1 + k + 1
                            )
                            new_line_num = (
                                new_line_map[j1 + k]
                                if j1 + k < len(new_line_map)
                                else j1 + k + 1
                            )
                            old_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            new_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            table.add_row(
                                f"[bright_cyan]{old_line_num}[/bright_cyan]",
                                old_syntax,
                                f"[bright_cyan]{new_line_num}[/bright_cyan]",
                                new_syntax,
                            )
                            # Collect the data for the frontend
                            diff_rows.append(
                                {
                                    "type": "equal",
                                    "old_line_num": old_line_num,
                                    "old_line": equal_chunk[k],
                                    "new_line_num": new_line_num,
                                    "new_line": equal_chunk[k],
                                }
                            )
                    else:
                        # The first block, show only the ending context
                        start_idx = max(0, equal_len - context_lines)
                        for k in range(start_idx, equal_len):
                            old_line_num = (
                                old_line_map[i1 + k]
                                if i1 + k < len(old_line_map)
                                else i1 + k + 1
                            )
                            new_line_num = (
                                new_line_map[j1 + k]
                                if j1 + k < len(new_line_map)
                                else j1 + k + 1
                            )
                            old_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            new_syntax = Syntax(
                                equal_chunk[k],
                                language,
                                theme="monokai",
                                background_color="default",
                                word_wrap=True,
                            )
                            table.add_row(
                                f"[bright_cyan]{old_line_num}[/bright_cyan]",
                                old_syntax,
                                f"[bright_cyan]{new_line_num}[/bright_cyan]",
                                new_syntax,
                            )
                            # Collect the data for the frontend
                            diff_rows.append(
                                {
                                    "type": "equal",
                                    "old_line_num": old_line_num,
                                    "old_line": equal_chunk[k],
                                    "new_line_num": new_line_num,
                                    "new_line": equal_chunk[k],
                                }
                            )
                else:
                    # If the equal block is not long, show all lines
                    for k, line in enumerate(equal_chunk):
                        old_line_num = (
                            old_line_map[i1 + k]
                            if i1 + k < len(old_line_map)
                            else i1 + k + 1
                        )
                        new_line_num = (
                            new_line_map[j1 + k]
                            if j1 + k < len(new_line_map)
                            else j1 + k + 1
                        )
                        old_syntax = Syntax(
                            line,
                            language,
                            theme="monokai",
                            background_color="default",
                            word_wrap=True,
                        )
                        new_syntax = Syntax(
                            line,
                            language,
                            theme="monokai",
                            background_color="default",
                            word_wrap=True,
                        )
                        table.add_row(
                            f"[bright_cyan]{old_line_num}[/bright_cyan]",
                            old_syntax,
                            f"[bright_cyan]{new_line_num}[/bright_cyan]",
                            new_syntax,
                        )
                        # Collect the data for the frontend
                        diff_rows.append(
                            {
                                "type": "equal",
                                "old_line_num": old_line_num,
                                "old_line": line,
                                "new_line_num": new_line_num,
                                "new_line": line,
                            }
                        )
                continue
            elif tag == "replace":
                # Replace: the deleted lines and added lines are displayed in pairs
                old_chunk = old_lines[i1:i2]
                new_chunk = new_lines[j1:j2]
                deletions += len(old_chunk)
                additions += len(new_chunk)
                has_changes = True

                # Show them in pairs
                max_len = max(len(old_chunk), len(new_chunk))
                for k in range(max_len):
                    # The absolute line number in the file
                    if k < len(old_chunk):
                        old_line_num_actual: Union[int, str] = (
                            old_line_map[i1 + k]
                            if i1 + k < len(old_line_map)
                            else i1 + k + 1
                        )
                        old_replace_syntax: Union[Syntax, str] = Syntax(
                            old_chunk[k],
                            language,
                            theme="monokai",
                            background_color="#5c0000",
                            word_wrap=True,
                        )
                    else:
                        old_line_num_actual = ""
                        old_replace_syntax = ""

                    if k < len(new_chunk):
                        new_line_num_actual: Union[int, str] = (
                            new_line_map[j1 + k]
                            if j1 + k < len(new_line_map)
                            else j1 + k + 1
                        )
                        new_replace_syntax: Union[Syntax, str] = Syntax(
                            new_chunk[k],
                            language,
                            theme="monokai",
                            background_color="#004d00",
                            word_wrap=True,
                        )
                    else:
                        new_line_num_actual = ""
                        new_replace_syntax = ""

                    table.add_row(
                        str(old_line_num_actual),
                        old_replace_syntax,
                        str(new_line_num_actual),
                        new_replace_syntax,
                    )
                    # Collect the data for the frontend
                    diff_rows.append(
                        {
                            "type": "replace",
                            "old_line_num": old_line_num_actual
                            if old_line_num_actual
                            else None,
                            "old_line": old_chunk[k] if k < len(old_chunk) else None,
                            "new_line_num": new_line_num_actual
                            if new_line_num_actual
                            else None,
                            "new_line": new_chunk[k] if k < len(new_chunk) else None,
                        }
                    )
            elif tag == "delete":
                # Delete only
                old_chunk = old_lines[i1:i2]
                deletions += len(old_chunk)
                has_changes = True
                for k, line in enumerate(old_chunk):
                    # The absolute line number in the file
                    old_line_num = (
                        old_line_map[i1 + k]
                        if i1 + k < len(old_line_map)
                        else i1 + k + 1
                    )
                    old_delete_syntax: Union[Syntax, str] = Syntax(
                        line,
                        language,
                        theme="monokai",
                        background_color="#5c0000",
                        word_wrap=True,
                    )
                    table.add_row(
                        str(old_line_num),
                        old_delete_syntax,
                        "",
                        "",
                    )
                    # Collect the data for the frontend
                    diff_rows.append(
                        {
                            "type": "delete",
                            "old_line_num": old_line_num,
                            "old_line": line,
                            "new_line_num": None,
                            "new_line": None,
                        }
                    )
            elif tag == "insert":
                # Insert only
                new_chunk = new_lines[j1:j2]
                additions += len(new_chunk)
                has_changes = True
                for k, line in enumerate(new_chunk):
                    # The absolute line number in the file
                    new_line_num = (
                        new_line_map[j1 + k]
                        if j1 + k < len(new_line_map)
                        else j1 + k + 1
                    )
                    new_insert_syntax: Union[Syntax, str] = Syntax(
                        line,
                        language,
                        theme="monokai",
                        background_color="#004d00",
                        word_wrap=True,
                    )
                    table.add_row(
                        "",
                        "",
                        str(new_line_num),
                        new_insert_syntax,
                    )
                    # Collect the data for the frontend
                    diff_rows.append(
                        {
                            "type": "insert",
                            "old_line_num": None,
                            "old_line": None,
                            "new_line_num": new_line_num,
                            "new_line": line,
                        }
                    )

        # If there are no changes, show a prompt
        if not has_changes:
            self.console.print("[dim](No changes)[/dim]")
            return

        # Build the title (including statistics)
        title = f"📝 {file_path}" if file_path else "Side-by-Side Diff"
        title += f"  [bright_green]+{additions}[/bright_green] / [bright_red]-{deletions}[/bright_red]"

        # Wrap in a Panel for display - minimize padding to maximize the content area
        panel = Panel(
            table,
            title=title,
            border_style="bright_cyan",
            box=box.HORIZONTALS,
            padding=(0, 0),
        )
        self.console.print(panel)

        # Send to the frontend (send the side-by-side structured data)
        try:
            import json
            from haijunbot.haijunbot_utils.output import OutputEvent
            from haijunbot.haijunbot_utils.output import OutputType

            # Build the side-by-side data structure
            side_by_side_data = {
                "file_path": file_path,
                "additions": additions,
                "deletions": deletions,
                "diff_type": "side_by_side",
                "rows": diff_rows,
            }

            # Send as a JSON string
            diff_text = json.dumps(side_by_side_data, ensure_ascii=False, indent=2)

            emit_output(
                OutputEvent(
                    text=diff_text,
                    output_type=OutputType.DIFF,  # Use the dedicated DIFF type
                    timestamp=None,
                    context={
                        "file_path": file_path,
                        "additions": additions,
                        "deletions": deletions,
                        "diff_type": "side_by_side",
                        "_gateway_skip": True,  # Do not print Gateway-specific data in the terminal
                    },
                )
            )
        except Exception:
            # Ignore output errors, they do not affect the console display
            pass


def _split_diff_by_files(diff_text: str) -> List[tuple]:
    """Split a diff text containing multiple files into per-file diffs

    Args:
        diff_text: the git diff output text (may contain multiple files)

    Returns:
        List[tuple]: a list of [(file_path, single_file_diff), ...]
    """
    files = []
    lines = diff_text.splitlines()
    current_file_path = ""
    current_file_lines: list = []

    i = 0
    while i < len(lines):
        line = lines[i]

        if line.startswith("diff --git"):
            # If a file is already being processed, save it first
            if current_file_lines:
                files.append((current_file_path, "\n".join(current_file_lines)))

            # Start a new file
            current_file_lines = [line]
            # Try to extract the file path from the diff --git line
            # Format: diff --git a/path b/path
            parts = line.split()
            if len(parts) >= 4:
                # Take the b/path part and remove the b/ prefix
                path_part = parts[3]
                if path_part.startswith("b/"):
                    current_file_path = path_part[2:]
                else:
                    current_file_path = path_part
            else:
                current_file_path = ""
        elif line.startswith("---") or line.startswith("+++"):
            # Update the file path (prefer the path from the +++ line)
            current_file_lines.append(line)
            if line.startswith("+++"):
                path_part = line[4:].strip()
                if path_part != "/dev/null":
                    # Remove the a/ or b/ prefix
                    if path_part.startswith("b/"):
                        current_file_path = path_part[2:]
                    elif path_part.startswith("a/"):
                        current_file_path = path_part[2:]
                    else:
                        current_file_path = path_part
        else:
            # Other lines are added to the current file
            current_file_lines.append(line)

        i += 1

    # Save the last file
    if current_file_lines:
        files.append((current_file_path, "\n".join(current_file_lines)))

    # If no file separator was found, treat the whole diff as a single file
    if not files:
        # Try to extract the file path from the --- or +++ lines
        file_path = ""
        for line in lines:
            if line.startswith("+++"):
                path_part = line[4:].strip()
                if path_part != "/dev/null":
                    if path_part.startswith("b/"):
                        file_path = path_part[2:]
                    elif path_part.startswith("a/"):
                        file_path = path_part[2:]
                    else:
                        file_path = path_part
                    break

        files.append((file_path, diff_text))

    return files


def _parse_diff_to_lines(diff_text: str) -> tuple:
    """Parse the old and new file line lists (with line number info) from the git diff text

    Args:
        diff_text: the git diff output text

    Returns:
        (old_lines, new_lines, old_line_map, new_line_map):
        The old file line list, the new file line list, the old file line number mapping, the new file line number mapping
        The line number mapping is a list whose index corresponds to the line list index; the value is the absolute line number in the file
    """
    old_lines = []
    new_lines = []
    old_line_map = []  # Maps the old_lines index to the absolute line number in the file
    new_line_map = []  # Maps the new_lines index to the absolute line number in the file

    old_line_num = 0
    new_line_num = 0

    for line in diff_text.splitlines():
        if line.startswith("@@"):
            # Parse the hunk header to get the starting line number
            parts = line.split("@@")
            if len(parts) >= 2:
                hunk_info = parts[1].strip()
                if hunk_info:
                    for token in hunk_info.split():
                        if token.startswith("-"):
                            try:
                                old_line_num = int(token[1:].split(",")[0])
                            except ValueError:
                                pass
                        elif token.startswith("+"):
                            try:
                                new_line_num = int(token[1:].split(",")[0])
                            except ValueError:
                                pass
            continue
        elif line.startswith("---") or line.startswith("+++"):
            # Skip the file headers
            continue
        elif line.startswith("diff ") or line.startswith("index "):
            # Skip the diff metadata
            continue
        elif line.startswith("-"):
            # Deleted lines
            old_lines.append(line[1:])
            old_line_map.append(old_line_num)
            old_line_num += 1
        elif line.startswith("+"):
            # Added lines
            new_lines.append(line[1:])
            new_line_map.append(new_line_num)
            new_line_num += 1
        elif line.startswith(" "):
            # Unchanged lines
            old_lines.append(line[1:])
            new_lines.append(line[1:])
            old_line_map.append(old_line_num)
            new_line_map.append(new_line_num)
            old_line_num += 1
            new_line_num += 1
        else:
            # Skip unrecognized lines (such as '\ No newline at end of file', empty lines, etc.)
            # These lines are not part of the diff content and should be ignored
            pass

    return old_lines, new_lines, old_line_map, new_line_map


def parse_diff_to_structured_data(
    diff_text: str,
    file_path: str = "",
) -> List[dict]:
    """Parse the git diff text into structured data (public function)

    Args:
        diff_text: the git diff output text
        file_path: the file path (used for display)

    Returns:
        List[dict]: a list of structured data, each element contains:
            - file_path: the file path
            - additions: the number of added lines
            - deletions: the number of deleted lines
            - rows: a list of line data, each line contains:
                - type: the line type (equal/insert/delete/replace)
                - old_line_num: the old file line number
                - old_line: the old file line content
                - new_line_num: the new file line number
                - new_line: the new file line content
    """
    import difflib

    # Split the diffs of multiple files
    file_diffs = _split_diff_by_files(diff_text)
    result = []

    for single_file_path, single_file_diff in file_diffs:
        # Parse the diff into line lists
        old_lines, new_lines, old_line_map, new_line_map = _parse_diff_to_lines(
            single_file_diff
        )

        # Use SequenceMatcher for matching
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        opcodes = matcher.get_opcodes()

        # Generate the line data
        diff_rows = []
        additions = 0
        deletions = 0

        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for k in range(i2 - i1):
                    old_idx = i1 + k
                    new_idx = j1 + k
                    diff_rows.append(
                        {
                            "type": "equal",
                            "old_line_num": old_line_map[old_idx]
                            if old_idx < len(old_line_map)
                            else None,
                            "old_line": old_lines[old_idx]
                            if old_idx < len(old_lines)
                            else None,
                            "new_line_num": new_line_map[new_idx]
                            if new_idx < len(new_line_map)
                            else None,
                            "new_line": new_lines[new_idx]
                            if new_idx < len(new_lines)
                            else None,
                        }
                    )
            elif tag == "delete":
                deletions += i2 - i1
                for k in range(i2 - i1):
                    old_idx = i1 + k
                    diff_rows.append(
                        {
                            "type": "delete",
                            "old_line_num": old_line_map[old_idx]
                            if old_idx < len(old_line_map)
                            else None,
                            "old_line": old_lines[old_idx]
                            if old_idx < len(old_lines)
                            else None,
                            "new_line_num": None,
                            "new_line": None,
                        }
                    )
            elif tag == "insert":
                additions += j2 - j1
                for k in range(j2 - j1):
                    new_idx = j1 + k
                    diff_rows.append(
                        {
                            "type": "insert",
                            "old_line_num": None,
                            "old_line": None,
                            "new_line_num": new_line_map[new_idx]
                            if new_idx < len(new_line_map)
                            else None,
                            "new_line": new_lines[new_idx]
                            if new_idx < len(new_lines)
                            else None,
                        }
                    )
            elif tag == "replace":
                old_len = i2 - i1
                new_len = j2 - j1
                deletions += old_len
                additions += new_len
                max_len = max(old_len, new_len)
                for k in range(max_len):
                    old_idx = i1 + k if k < old_len else None
                    new_idx = j1 + k if k < new_len else None
                    diff_rows.append(
                        {
                            "type": "replace",
                            "old_line_num": old_line_map[old_idx]
                            if old_idx is not None and old_idx < len(old_line_map)
                            else None,
                            "old_line": old_lines[old_idx]
                            if old_idx is not None and old_idx < len(old_lines)
                            else None,
                            "new_line_num": new_line_map[new_idx]
                            if new_idx is not None and new_idx < len(new_line_map)
                            else None,
                            "new_line": new_lines[new_idx]
                            if new_idx is not None and new_idx < len(new_lines)
                            else None,
                        }
                    )

        # Validate and normalize the rows data
        validated_rows = []
        for row in diff_rows:
            # Ensure each row has the necessary fields
            validated_row = {
                "type": row.get("type", "equal"),
                "old_line_num": row.get("old_line_num"),
                "old_line": row.get("old_line"),
                "new_line_num": row.get("new_line_num"),
                "new_line": row.get("new_line"),
            }
            # Validate the type field
            if validated_row["type"] not in ("equal", "insert", "delete", "replace"):
                validated_row["type"] = "equal"
            validated_rows.append(validated_row)

        result.append(
            {
                "file_path": single_file_path if single_file_path else file_path,
                "additions": additions,
                "deletions": deletions,
                "rows": validated_rows,
            }
        )

    return result


def visualize_diff_enhanced(
    diff_text: str,
    file_path: str = "",
    mode: str = "unified",
    show_line_numbers: bool = True,
    context_lines: int = 3,
) -> None:
    """Enhanced diff visualization function (convenience interface)

    Args:
        diff_text: the git diff output text
        file_path: the file path
        mode: the visualization mode ("unified" | "syntax" | "compact" | "side_by_side" | "statistics")
        show_line_numbers: whether to show line numbers
        context_lines: the number of context lines
    """
    visualizer = DiffVisualizer()

    if mode == "unified":
        visualizer.visualize_unified_diff(
            diff_text,
            file_path,
            show_line_numbers=show_line_numbers,
            context_lines=context_lines,
        )
    elif mode == "syntax":
        visualizer.visualize_syntax_highlighted(diff_text, file_path)
    elif mode == "compact":
        visualizer.visualize_compact(diff_text, file_path)
    elif mode == "side_by_side":
        # Check whether there are multiple files
        file_diffs = _split_diff_by_files(diff_text)

        if len(file_diffs) >= 1:
            # Process all files (including the single file case)
            for single_file_path, single_file_diff in file_diffs:
                old_lines, new_lines, old_line_map, new_line_map = _parse_diff_to_lines(
                    single_file_diff
                )
                visualizer.visualize_side_by_side_summary(
                    old_lines,
                    new_lines,
                    single_file_path if single_file_path else file_path,
                    context_lines=context_lines,
                    old_line_map=old_line_map,
                    new_line_map=new_line_map,
                )
        else:
            # No file was parsed, use the original logic
            old_lines, new_lines, old_line_map, new_line_map = _parse_diff_to_lines(
                diff_text
            )
            visualizer.visualize_side_by_side_summary(
                old_lines,
                new_lines,
                file_path,
                context_lines=context_lines,
                old_line_map=old_line_map,
                new_line_map=new_line_map,
            )
    else:
        # Default to syntax highlighting
        visualizer.visualize_syntax_highlighted(diff_text, file_path)
