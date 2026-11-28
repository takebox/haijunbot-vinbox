# -*- coding: utf-8 -*-
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from haijunbot.haijunbot_utils.config import (
    calculate_token_limit,
    detect_file_encoding,
    get_max_input_token_count,
    read_text_file,
    save_exception,
)
from haijunbot.haijunbot_utils.embedding import get_context_token_count
from haijunbot.haijunbot_utils.output import PrettyOutput


class ReadCodeTool:
    name = "read_code"
    description = "Read source code files: read a specified line range via path + start_line/end_line; output includes line numbers for easy location and review."

    def _get_preferred_encodings(self) -> List[str]:
        """Get the tool-level preferred encoding order. Windows prefers gbk; other platforms prefer utf-8."""
        if sys.platform == "win32":
            return ["gbk", "utf-8"]
        return ["utf-8", "gbk"]

    def _read_text_with_preferred_encoding(self, file_path: str) -> Tuple[str, str]:
        """Use detect_file_encoding to directly detect the encoding and read the text file.

        Returns:
            Tuple[str, str]: (file content, encoding)
        """
        detected_encoding = detect_file_encoding(file_path)
        if detected_encoding:
            try:
                content = read_text_file(
                    file_path,
                    encoding=detected_encoding,
                    detect_encoding=False,
                    errors="strict",
                )
                return content, detected_encoding
            except (UnicodeDecodeError, LookupError):
                pass

        # Fall back to the default reading method
        content = read_text_file(file_path)
        return content, "utf-8"

    parameters = {
        "properties": {
            "files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "number", "default": 1},
                        "end_line": {"type": "number", "default": -1},
                    },
                    "required": ["path"],
                },
                "description": "The list of files to read; each file can specify a line range (start_line to end_line; -1 means the end of the file).",
            }
        },
        "required": ["files"],
    }

    def _get_max_token_limit(self, agent: Optional[Any] = None) -> int:
        """Get the token limit based on the number of remaining tokens

        Args:
            agent: the Agent instance, used to get the model and the number of remaining tokens

        Returns:
            int: the maximum number of tokens allowed (2/3 of the remaining tokens, or at least keep 1/3 of the remaining tokens)
        """
        try:
            # Prefer using the number of remaining tokens
            if agent and hasattr(agent, "model"):
                try:
                    remaining_tokens = agent.model.get_remaining_token_count()
                    # Use 2/3 of the remaining tokens or the minimum of 64k
                    limit_tokens = calculate_token_limit(remaining_tokens)
                    # Ensure at least a reasonable value is returned
                    if limit_tokens > 0:
                        return limit_tokens
                except Exception as e:
                    save_exception(
                        e,
                        module="haijunbot_tools.read_code",
                        function="_get_max_token_limit",
                    )
                    pass

            # Fallback: use 2/3 of the input window
            max_input_tokens = get_max_input_token_count()
            # Calculate the token count for a 1/2 limit
            limit_tokens = int(max_input_tokens * 1 / 2)
            return limit_tokens
        except Exception:
            # If fetching fails, use a safe fallback value
            return 33333  # noqa: conservative fallback value, roughly equal to assuming 1/3 of 100k tokens

    @staticmethod
    def _normalize_line_range(
        start_line: int, end_line: int, total_lines: int
    ) -> Tuple[int, int]:
        """Normalize possibly negative or -1 line numbers into a valid range."""
        if end_line == -1:
            end_line = total_lines
        else:
            end_line = (
                max(1, min(end_line, total_lines))
                if end_line >= 0
                else total_lines + end_line + 1
            )
        start_line = (
            max(1, min(start_line, total_lines))
            if start_line >= 0
            else total_lines + start_line + 1
        )
        return start_line, end_line

    @staticmethod
    def _format_numbered_lines(lines: List[str], start_line: int) -> str:
        """Add line numbers to each line and concatenate into a string."""
        numbered = []
        for i, line in enumerate(lines, start=start_line):
            numbered.append(f"{i:4d}:{line.rstrip(chr(10) + chr(13))}")
        return "\n".join(numbered)

    def _handle_single_file(
        self,
        filepath: str,
        start_line: int = 1,
        end_line: int = -1,
        agent: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Handle the read operation for a single file

        Args:
            filepath (str): file path
            start_line (int): start line number, defaults to 1
            end_line (int): end line number, defaults to -1 meaning the end of the file
            agent: the Agent instance, used to get the token limit

        Returns:
            Dict[str, Any]: a dict containing the success status, output content, and error information
        """
        abs_path = ""  # Pre-initialize to ensure the except branch can access it (ty inference limitation)
        try:
            expanded_path = os.path.expanduser(filepath)
            abs_path = os.path.abspath(expanded_path)

            # File existence check
            if not os.path.exists(abs_path):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"File does not exist: {abs_path}",
                }

            # File size limit check (10MB)
            if os.path.getsize(abs_path) > 10 * 1024 * 1024:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "File too large (>10MB)",
                }

            # Read the file content using the same preferred-encoding strategy as edit_file
            content, file_encoding = self._read_text_with_preferred_encoding(abs_path)
            lines = content.splitlines()

            total_lines = len(lines)

            # Handle the empty file case
            if total_lines == 0:
                return {
                    "success": True,
                    "stdout": f"\n🔍 File: {abs_path}\n📄 File is empty (0 lines)\n",
                    "stderr": "",
                }

            start_line, end_line = self._normalize_line_range(
                start_line, end_line, total_lines
            )

            if start_line > end_line:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"Invalid line range [{start_line}-{end_line}] (total lines: {total_lines})",
                }

            # Read the content of the specified line range
            selected_lines = lines[start_line - 1 : end_line]
            output_content = self._format_numbered_lines(selected_lines, start_line)

            # Estimate the token count
            content_tokens = get_context_token_count(output_content)
            max_token_limit = self._get_max_token_limit(agent)

            # Check whether the token count exceeds the limit
            if content_tokens > max_token_limit:
                read_lines = end_line - start_line + 1

                # Calculate the safe number of lines to read (scaled down proportionally)
                safe_lines = int((max_token_limit / content_tokens) * read_lines)
                safe_lines = max(1, min(safe_lines, read_lines))
                safe_end_line = start_line + safe_lines - 1

                # Read the content within the safe range
                safe_selected_lines = lines[start_line - 1 : safe_end_line]
                partial_content = self._format_numbered_lines(
                    safe_selected_lines, start_line
                )

                return {
                    "success": True,
                    "stdout": (
                        f"⚠️ Warning: only the first {safe_lines} lines were read (out of {read_lines} lines) because the content exceeds the limit\n"
                        f"📊 Actual read range: {start_line}-{safe_end_line} (original requested range: {start_line}-{end_line})\n\n"
                        f"{partial_content}\n\n"
                        f"💡 Suggestions:\n"
                        f"   1. To continue reading, use:\n"
                        f"      start_line={safe_end_line + 1}&end_line={end_line}\n"
                        f"   2. Need to read all content? Please narrow the line range or read in batches"
                    ),
                    "stderr": (
                        f"Original requested range {start_line}-{end_line} exceeds the token limit "
                        f"({content_tokens}/{max_token_limit} tokens)"
                    ),
                }

            # Build the complete output
            read_lines = end_line - start_line + 1
            output = f"\n🔍 File: {abs_path}\n📄 Total lines: {total_lines}\n📊 Read range: {start_line}-{end_line}\n📈 Lines read: {read_lines}\n🔤 Encoding: {file_encoding}\n"
            output += "=" * 80 + "\n"
            output += output_content
            output += "\n" + "=" * 80 + "\n"

            # Try to get and append context information
            context_info = self._get_file_context(abs_path, start_line, end_line, agent)
            if context_info:
                output += context_info

            # Detect whether it is a rule file and add a hint
            normalized_path = os.path.normpath(abs_path).replace(os.sep, "/")
            if "/rules/" in normalized_path or normalized_path.endswith("/rules"):
                output += (
                    "\n💡 Hint: the path of this file contains 'rules'; this may be a rule file."
                )
                output += (
                    "\n   It is recommended to use the `load_rule` tool to load the fully rendered rule content.\n"
                )

            if agent:
                files = agent.get_user_data("files")
                if files:
                    files.append(abs_path)
                else:
                    files = [abs_path]
                agent.set_user_data("files", files)

            return {
                "success": True,
                "stdout": output,
                "stderr": "",
                "actual_start_line": start_line,
                "actual_end_line": end_line,
                "total_lines": total_lines,
                "file_encoding": file_encoding,
            }

        except UnicodeDecodeError as e:
            error_msg = (
                f"File decoding failed: {str(e)}. "
                f"Consider using sed to read the raw characters directly, e.g.: sed -n '{start_line},{end_line if end_line != -1 else '$'}p' '{abs_path}'"
            )
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {"success": False, "stdout": "", "stderr": error_msg}
        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {"success": False, "stdout": "", "stderr": f"File read failed: {str(e)}"}

    def _get_file_context(
        self, filepath: str, start_line: int, end_line: int, agent: Optional[Any] = None
    ) -> str:
        """Get the context information of a file

        Args:
            filepath: file path
            start_line: start line number
            end_line: end line number
            agent: the Agent instance

        Returns:
            A formatted context information string, or an empty string if it cannot be obtained
        """
        try:
            # Try to get the CodeAgent instance from the Agent
            if not agent:
                return ""

            # Get the CodeAgent instance through the agent
            # CodeAgent associates itself with the agent during initialization
            code_agent = getattr(agent, "_code_agent", None)
            if not code_agent:
                return ""

            # Get the context manager
            context_manager = getattr(code_agent, "context_manager", None)
            if not context_manager:
                return ""

            # Context-aware logging has been removed

            # Ensure the file is updated in the context manager
            # If the file content is already cached, use it directly; otherwise read and update
            if (
                not hasattr(context_manager, "_file_cache")
                or filepath not in context_manager._file_cache
            ):
                try:
                    content, _ = self._read_text_with_preferred_encoding(filepath)
                    context_manager.update_context_for_file(filepath, content)
                except Exception:
                    # If reading fails, try to get the existing context
                    pass

            # Get the edit context
            edit_context = context_manager.get_edit_context(
                filepath, start_line, end_line
            )

            # Build the context information
            if (
                not edit_context.context_summary
                or edit_context.context_summary == "No context available"
            ):
                return ""

            # Format the context information
            context_lines = ["\n📋 Code context information:"]
            context_lines.append("─" * 60)

            if edit_context.current_scope:
                scope_info = f"📍 Current scope: {edit_context.current_scope.kind} `{edit_context.current_scope.name}`"
                if edit_context.current_scope.signature:
                    scope_info += (
                        f"\n   └─ Signature: {edit_context.current_scope.signature}"
                    )
                context_lines.append(scope_info)

            if edit_context.used_symbols:
                # Deduplicate symbols (based on name + file_path + line_start)
                seen_symbols = set()
                unique_symbols = []
                for s in edit_context.used_symbols:
                    key = (
                        s.name,
                        getattr(s, "file_path", ""),
                        getattr(s, "line_start", 0),
                    )
                    if key not in seen_symbols:
                        seen_symbols.add(key)
                        unique_symbols.append(s)

                # Distinguish definitions from calls and show definition location information
                definitions = []
                calls = []
                for symbol in unique_symbols[:10]:
                    is_def = getattr(symbol, "is_definition", False)
                    if is_def:
                        definitions.append(symbol)
                    else:
                        calls.append(symbol)

                # Show definitions
                if definitions:
                    def_names = [f"`{s.name}`" for s in definitions]
                    context_lines.append(f"📝 Defined symbols: {', '.join(def_names)}")

                # Show calls (with definition location information)
                if calls:
                    call_info = []
                    for symbol in calls:
                        def_loc = getattr(symbol, "definition_location", None)
                        if def_loc:
                            def_file = os.path.basename(def_loc.file_path)
                            def_line = def_loc.line_start
                            call_info.append(f"`{symbol.name}` → {def_file}:{def_line}")
                        else:
                            call_info.append(f"`{symbol.name}`")
                    context_lines.append(f"🔗 Called symbols: {', '.join(call_info)}")

                # If there are more symbols
                more = len(edit_context.used_symbols) - 10
                if more > 0:
                    context_lines.append(f"   ... {more} more symbol(s)")

            if edit_context.relevant_files:
                # Deduplicate relevant files
                unique_files = list(dict.fromkeys(edit_context.relevant_files))
                rel_files = unique_files[:10]
                files_str = "\n   ".join(
                    f"• {os.path.relpath(f, context_manager.project_root)}"
                    for f in rel_files
                )
                more = len(unique_files) - 10
                if more > 0:
                    files_str += f"\n   ... {more} more related file(s)"
                context_lines.append(
                    f"📁 Related files ({len(unique_files)}):\n   {files_str}"
                )

            context_lines.append("─" * 60)
            context_lines.append("")  # Empty line

            # The context-aware result has been removed and is no longer printed to the console
            context_output = "\n".join(context_lines)
            return context_output

        except Exception:
            # Fail silently without affecting file reading
            return ""

    def _handle_merged_ranges(
        self, filepath: str, requests: List[Dict[str, Any]], agent: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Handle multiple range requests for the same file, merging and deduplicating them

        Args:
            filepath: absolute file path
            requests: the list of range requests; each request contains start_line, end_line
            agent: the Agent instance

        Returns:
            Dict[str, Any]: a dict containing the success status, output content, and error information
        """
        try:
            # File existence check
            if not os.path.exists(filepath):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"File does not exist: {filepath}",
                }

            # Strictly read the file content; return an error directly on decoding failure
            content, _ = self._read_text_with_preferred_encoding(filepath)
            lines = content.splitlines()

            total_lines = len(lines)
            if total_lines == 0:
                return {
                    "success": True,
                    "stdout": f"\n🔍 File: {filepath}\n📄 File is empty (0 lines)\n",
                    "stderr": "",
                }

            # Merge all ranges and compute the minimum start line and maximum end line
            min_start = float("inf")
            max_end = 0
            for req in requests:
                start_line, end_line = self._normalize_line_range(
                    req.get("start_line", 1),
                    req.get("end_line", -1),
                    total_lines,
                )
                min_start = min(min_start, start_line)
                max_end = max(max_end, end_line)

            # Read once using the merged range, which naturally deduplicates
            return self._handle_single_file(
                filepath, int(min_start), int(max_end), agent
            )

        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Merged range read failed: {str(e)}",
            }

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the code read operation

        Args:
            args (Dict): the argument dict containing the file list

        Returns:
            Dict[str, Any]: a dict containing the success status, output content, and error information
        """
        try:
            agent = args.get("agent", None)
            if "files" not in args or not isinstance(args["files"], list):
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "The arguments must contain a file list",
                }

            if len(args["files"]) == 0:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "The file list cannot be empty",
                }

            all_outputs = []
            overall_success = True
            status_lines = []
            total_tokens = 0  # Accumulated number of tokens read
            max_token_limit = self._get_max_token_limit(agent)

            # First pass: check whether the accumulated token count of all files exceeds the limit
            file_read_info = []  # Store the information to read for each file
            for file_info in args["files"]:
                if not isinstance(file_info, dict) or "path" not in file_info:
                    continue

                filepath = file_info["path"].strip()
                start_line = file_info.get("start_line", 1)
                end_line = file_info.get("end_line", -1)

                # Check whether the file exists and calculate the number of tokens to read
                expanded_path = os.path.expanduser(filepath)
                abs_path = os.path.abspath(expanded_path)
                if not os.path.exists(abs_path):
                    continue

                try:
                    # Strictly read the file content; return an error directly on decoding failure
                    content, _ = self._read_text_with_preferred_encoding(abs_path)
                    lines = content.splitlines()

                    total_lines = len(lines)

                    if total_lines == 0:
                        continue

                    actual_start_line, actual_end_line = self._normalize_line_range(
                        start_line, end_line, total_lines
                    )

                    if actual_start_line <= actual_end_line:
                        # Read the content of the specified line range
                        selected_lines = lines[actual_start_line - 1 : actual_end_line]
                        output_content = self._format_numbered_lines(
                            selected_lines, actual_start_line
                        )
                        content_tokens = get_context_token_count(output_content)

                        file_read_info.append(
                            {
                                "filepath": filepath,
                                "start_line": actual_start_line,
                                "end_line": actual_end_line,
                                "read_lines": actual_end_line - actual_start_line + 1,
                                "tokens": content_tokens,
                                "file_info": file_info,
                            }
                        )
                        total_tokens += content_tokens
                except Exception as e:
                    save_exception(
                        e, module="haijunbot_tools.read_code", function="execute"
                    )
                    continue

            # Check whether the accumulated token count exceeds the limit
            if total_tokens > max_token_limit:
                file_list = "\n   ".join(
                    f"• {info['filepath']}: {info['tokens']} tokens ({info['read_lines']} lines, range: {info['start_line']}-{info['end_line']})"
                    for info in file_read_info[:10]
                )
                more_files = len(file_read_info) - 10
                if more_files > 0:
                    file_list += f"\n   ... {more_files} more file(s)"

                return {
                    "success": False,
                    "stdout": "",
                    "stderr": (
                        f"⚠️ Accumulated read range too large: the requested accumulated content is about {total_tokens} tokens, exceeding the limit ({max_token_limit} tokens, about 2/3 of the maximum window)\n"
                        f"📋 File list ({len(file_read_info)} files):\n   {file_list}\n"
                        f"💡 Suggestions:\n"
                        f"   1. Read in batches: split the files into multiple batches, each with accumulated content not exceeding {max_token_limit} tokens\n"
                        f"   2. Locate first: use search or analysis tools to locate the key code positions, then read specific ranges\n"
                        f"   3. Narrow the range: specify a more precise line range for each file"
                    ),
                }

            # Second pass: actually read the files (group by file, merge multiple range requests for the same file to avoid block duplication)
            # Group by file path
            file_requests = defaultdict(list)
            for file_info in args["files"]:
                if not isinstance(file_info, dict) or "path" not in file_info:
                    continue
                expanded_path = os.path.expanduser(file_info["path"].strip())
                abs_path = os.path.abspath(expanded_path)
                file_requests[abs_path].append(file_info)

            # Process by file, merging multiple range requests for the same file
            for abs_path, requests in file_requests.items():
                if len(requests) == 1:
                    # Single range request; process directly
                    file_info = requests[0]
                    result = self._handle_single_file(
                        file_info["path"].strip(),
                        file_info.get("start_line", 1),
                        file_info.get("end_line", -1),
                        agent,
                    )
                    if result["success"]:
                        all_outputs.append(result["stdout"])
                        actual_start = result.get("actual_start_line")
                        actual_end = result.get("actual_end_line")
                        if actual_start is not None and actual_end is not None:
                            encoding = result.get("file_encoding", "utf-8")
                            status_lines.append(
                                f"✅ {file_info['path']} file read successfully (actual range: {actual_start}-{actual_end}, 🔤 encoding: {encoding})"
                            )
                        else:
                            encoding = result.get("file_encoding", "utf-8")
                            status_lines.append(
                                f"✅ {file_info['path']} file read successfully (requested range: {file_info.get('start_line', 1)}-{file_info.get('end_line', -1)}, 🔤 encoding: {encoding})"
                            )
                    else:
                        all_outputs.append(
                            f"❌ {file_info['path']}: {result['stderr']}"
                        )
                        status_lines.append(f"❌ {file_info['path']} file read failed")
                        overall_success = False
                else:
                    # Multiple range requests; merge and deduplicate
                    merged_result = self._handle_merged_ranges(
                        abs_path, requests, agent
                    )
                    display_path = requests[0]["path"]
                    if merged_result["success"]:
                        all_outputs.append(merged_result["stdout"])
                        actual_start = merged_result.get("actual_start_line")
                        actual_end = merged_result.get("actual_end_line")
                        if actual_start is not None and actual_end is not None:
                            encoding = merged_result.get("file_encoding", "utf-8")
                            status_lines.append(
                                f"✅ {display_path} file read successfully (merged {len(requests)} range requests, deduplicated, actual range: {actual_start}-{actual_end}, 🔤 encoding: {encoding})"
                            )
                        else:
                            encoding = merged_result.get("file_encoding", "utf-8")
                            min_start = min(
                                req.get("start_line", 1) for req in requests
                            )
                            max_end = max(req.get("end_line", -1) for req in requests)
                            status_lines.append(
                                f"✅ {display_path} file read successfully (merged {len(requests)} range requests, deduplicated, requested range: {min_start}-{max_end}, 🔤 encoding: {encoding})"
                            )
                    else:
                        all_outputs.append(
                            f"❌ {display_path}: {merged_result['stderr']}"
                        )
                        status_lines.append(f"❌ {display_path} file read failed")
                        overall_success = False

            stdout_text = "\n".join(all_outputs)
            # Only print the read status of each file, not the specific content
            try:
                if status_lines:
                    PrettyOutput.auto_print("\n".join(status_lines))
            except Exception as e:
                save_exception(e, module="haijunbot_tools.read_code", function="execute")
                pass
            return {
                "success": overall_success,
                "stdout": stdout_text,
                "stderr": "",
            }

        except Exception as e:
            PrettyOutput.auto_print(f"❌ {str(e)}")
            return {"success": False, "stdout": "", "stderr": f"Code read failed: {str(e)}"}
