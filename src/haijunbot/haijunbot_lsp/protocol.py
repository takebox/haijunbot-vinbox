"""LSP protocol module

This module provides the protocol definitions for LSP (Language Server Protocol) and
JSON-RPC message encode/decode functionality.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LSPRequest:
    """LSP request data class

    Attributes:
        jsonrpc: JSON-RPC version, fixed to "2.0"
        id: The request ID
        method: The method name
        params: The request parameters
    """

    jsonrpc: str
    id: int
    method: str
    params: Optional[Dict[str, Any]]


@dataclass
class LSPResponse:
    """LSP response data class

    Attributes:
        jsonrpc: JSON-RPC version, fixed to "2.0"
        id: The request ID
        result: The response result
        error: The error information
    """

    jsonrpc: str
    id: Optional[int]
    result: Optional[Any]
    error: Optional[Dict[str, Any]]


@dataclass
class HoverInfo:
    """Symbol hover information

    Contains semantic information about a symbol such as its comments, type, parameter descriptions, docstring, etc.
    Used to provide the LLM with semantic information about the code without parsing the raw source.

    Attributes:
        contents: The hover content (Markdown or plain text format)
        range: The position range of the symbol (optional)
        file_path: The file path
        line: The line number of the symbol (0-based)
        character: The column number of the symbol (0-based)
    """

    contents: str
    range: Optional[
        tuple[int, int, int, int]
    ]  # (start_line, start_char, end_line, end_char)
    file_path: str
    line: int
    character: int


@dataclass
class FoldingRangeInfo:
    """Code folding range information

    Represents foldable regions in the code, such as functions, classes, if statements, etc.
    This helps the LLM identify the boundaries of code blocks.

    Attributes:
        start_line: The start line number (0-based)
        start_character: The start column number (0-based)
        end_line: The end line number (0-based, inclusive)
        end_character: The end column number (0-based, inclusive)
        kind: The folding range type (e.g. comment, region, imports, etc.)
        collapsed_text: The text displayed when collapsed (optional)
    """

    start_line: int
    start_character: int
    end_line: int
    end_character: int
    kind: Optional[str] = None
    collapsed_text: Optional[str] = None


@dataclass
class LSPNotification:
    """LSP notification data class

    Attributes:
        jsonrpc: JSON-RPC version, fixed to "2.0"
        method: The method name
        params: The notification parameters
    """

    jsonrpc: str
    method: str
    params: Optional[Dict[str, Any]]


class LSPMessageCodec:
    """LSP message codec

    Handles JSON-RPC message encode/decode for the LSP protocol, including
    handling of the Content-Length header.
    """

    CONTENT_LENGTH_HEADER = "Content-Length"

    @staticmethod
    def encode_request(request: LSPRequest) -> bytes:
        """Encode an LSP request

        Args:
            request: The LSP request object

        Returns:
            The encoded byte data
        """
        content = json.dumps(
            {
                "jsonrpc": request.jsonrpc,
                "id": request.id,
                "method": request.method,
                "params": request.params,
            },
            ensure_ascii=False,
        )
        return LSPMessageCodec._encode_content(content)

    @staticmethod
    def encode_response(response: LSPResponse) -> bytes:
        """Encode an LSP response

        Args:
            response: The LSP response object

        Returns:
            The encoded byte data
        """
        content = json.dumps(
            {
                "jsonrpc": response.jsonrpc,
                "id": response.id,
                "result": response.result,
                "error": response.error,
            },
            ensure_ascii=False,
        )
        return LSPMessageCodec._encode_content(content)

    @staticmethod
    def encode_notification(notification: LSPNotification) -> bytes:
        """Encode an LSP notification

        Args:
            notification: The LSP notification object

        Returns:
            The encoded byte data
        """
        content = json.dumps(
            {
                "jsonrpc": notification.jsonrpc,
                "method": notification.method,
                "params": notification.params,
            },
            ensure_ascii=False,
        )
        return LSPMessageCodec._encode_content(content)

    @staticmethod
    def _encode_content(content: str) -> bytes:
        """Encode the message content

        Args:
            content: The JSON string

        Returns:
            Byte data containing the Content-Length header and the content
        """
        content_bytes = content.encode("utf-8")
        header = (
            f"{LSPMessageCodec.CONTENT_LENGTH_HEADER}: {len(content_bytes)}\r\n"
            f"Content-Type: application/vscode-jsonrpc; charset=utf8\r\n\r\n"
        )
        return header.encode("utf-8") + content_bytes

    @staticmethod
    def decode_message(data: bytes) -> LSPResponse:
        """Decode an LSP message

        Args:
            data: The received byte data

        Returns:
            An LSP response object

        Raises:
            ValueError: Invalid message format
        """
        # Strip any leading empty lines
        data = data.lstrip(b"\r\n")

        # Parse the Content-Length header
        try:
            headers, content = data.split(b"\r\n\r\n", 1)
            header_lines = headers.decode("utf-8").split("\r\n")
            content_length = None
            for line in header_lines:
                if line.startswith(f"{LSPMessageCodec.CONTENT_LENGTH_HEADER}:"):
                    content_length = int(line.split(":", 1)[1].strip())
                    break

            if content_length is None:
                raise ValueError("Missing Content-Length header")

            content_str = content.decode("utf-8")
            message_dict = json.loads(content_str)

            # Distinguish between a response and a notification
            if "id" in message_dict:
                return LSPResponse(
                    jsonrpc=message_dict.get("jsonrpc", "2.0"),
                    id=message_dict["id"],
                    result=message_dict.get("result"),
                    error=message_dict.get("error"),
                )
            else:
                # Notification: handle it simply by returning a response object
                return LSPResponse(
                    jsonrpc=message_dict.get("jsonrpc", "2.0"),
                    id=None,
                    result=message_dict.get("params"),
                    error=None,
                )

        except (ValueError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to decode LSP message: {e}") from e


@dataclass
class DiagnosticInfo:
    """Code diagnostic information

    Contains syntax errors, lint warnings, type errors, code style issues, etc.
    Used to provide the LLM with code quality check information.

    Attributes:
        range: The position range of the issue (start_line, start_char, end_line, end_char)
        severity: The severity level (Error=1, Warning=2, Info=3, Hint=4)
        code: The error code (optional)
        source: The diagnostic source (pylint, ty, pyflakes, etc.)
        message: The error message
    """

    range: tuple[int, int, int, int]  # (start_line, start_char, end_line, end_char)
    severity: int  # 1=Error, 2=Warning, 3=Info, 4=Hint
    code: Optional[str]
    source: str
    message: str


@dataclass
class CodeActionInfo:
    """Code action information

    Contains executable fix actions, such as fixing errors, refactoring, optimizing, etc.
    Used to provide the LLM with code fix suggestions.

    Attributes:
        title: The action title
        kind: The action type (quickfix/refactor/rename/source.organizeImports, etc.)
        is_preferred: Whether it is the preferred action
    """

    title: str
    kind: str
    is_preferred: bool
