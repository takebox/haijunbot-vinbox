# -*- coding: utf-8 -*-
"""
Multimodal content processor

Provides validation, encoding, compression and other functions for multimodal content.
"""

import base64
import os
from typing import List, Union

from haijunbot.haijunbot_platform.content_types import (
    ContentBlock,
    CONTENT_CONFIG,
)
from haijunbot.haijunbot_utils.output import PrettyOutput


class ContentProcessor:
    """Multimodal content processor"""

    @staticmethod
    def process_message(message: Union[str, List[ContentBlock]]) -> List[ContentBlock]:
        """
        Uniformly process multimodal input, converting a string into a list of ContentBlock

        Args:
            message: The user's input message

        Returns:
            List[ContentBlock]: The normalized content block list

        Raises:
            ValueError: Invalid content format
            TypeError: Unsupported content type
        """
        # If it is a string, convert it to a text content block
        if isinstance(message, str):
            return [{"type": "text", "text": message}]

        # If it is a list, validate and process each content block
        if isinstance(message, list):
            processed_blocks: List[ContentBlock] = []
            for block in message:
                if not isinstance(block, dict):
                    raise TypeError(f"Content block must be a dictionary, actual type: {type(block)}")

                # Validate the content block
                ContentProcessor.validate_content(block)

                # Process the file path
                processed_block = ContentProcessor._process_file_path(block)
                processed_blocks.append(processed_block)

            return processed_blocks

        raise TypeError(f"Unsupported message type: {type(message)}")

    @staticmethod
    def validate_content(content: ContentBlock) -> bool:
        """
        Validate the legitimacy of a content block

        Args:
            content: The content block to validate

        Returns:
            bool: Whether validation passed

        Raises:
            ValueError: The reason validation failed
        """
        if not isinstance(content, dict):
            raise ValueError("Content block must be a dictionary")

        content_type = content.get("type")
        if not content_type:
            raise ValueError("Content block must contain the 'type' field")

        # Validate text content
        if content_type == "text":
            text_value = content.get("text")
            if text_value is None:
                raise ValueError("Text content block must contain the 'text' field")
            if not isinstance(text_value, str):
                raise ValueError("The text field must be a string")
            return True

        # Validate image content
        if content_type == "image_url":
            image_url = content.get("image_url")
            if image_url is None:
                raise ValueError("Image content block must contain the 'image_url' field")

            # Enhanced validation: check the image_url type
            if isinstance(image_url, str):
                # Check whether it is a valid URL or base64 data
                if not (
                    image_url.startswith("http") or image_url.startswith("data:image")
                ):
                    # If it is neither a URL nor base64, it may be a file path; allow it through (handled later)
                    pass
            elif isinstance(image_url, dict):
                # If it is a dictionary, check whether it contains the url field
                if "url" not in image_url:
                    raise ValueError("Image content block dictionary must contain the 'url' field")
            else:
                raise ValueError("The image_url field must be a string or dictionary")

            return True

        raise ValueError(f"Unsupported content type: {content_type}")

    @staticmethod
    def _process_file_path(block: ContentBlock) -> ContentBlock:
        """
        Process the file path, converting a local file path to base64 encoding

        Args:
            block: Content block

        Returns:
            ContentBlock: The processed content block
        """
        content_type = block.get("type")

        # Process the image file path
        if content_type == "image_url":
            image_url = block.get("image_url")
            if isinstance(image_url, str) and os.path.exists(image_url):
                # Read the file and convert it to base64
                base64_data = ContentProcessor._encode_file_to_base64(
                    image_url, "image"
                )
                if base64_data:
                    # Create a new content block to avoid modifying the original data
                    new_block: dict = dict(block)
                    new_block["image_url"] = base64_data
                    return new_block  # type: ignore

        return block

    @staticmethod
    def _encode_file_to_base64(file_path: str, file_type: str) -> Union[str, None]:
        """
        Encode a file as a base64 string

        Args:
            file_path: File path
            file_type: File type (image)

        Returns:
            Union[str, None]: base64-encoded string, or None on failure
        """
        try:
            # Check the file size
            file_size = os.path.getsize(file_path)
            max_size_key = f"max_{file_type}_size"
            max_size = CONTENT_CONFIG.get(max_size_key, 50 * 1024 * 1024)  # Default 50MB
            # Ensure max_size is an integer
            if not isinstance(max_size, int):
                max_size = 50 * 1024 * 1024

            if file_size > max_size:
                PrettyOutput.auto_print(f"⚠️ File too large: {file_path} ({file_size} bytes)")
                return None

            # Read the file and encode it
            with open(file_path, "rb") as f:
                file_data = f.read()
                base64_data = base64.b64encode(file_data).decode("utf-8")

                # Get the MIME type
                mime_type = ContentProcessor._get_mime_type(file_path, file_type)
                return f"data:{mime_type};base64,{base64_data}"

        except Exception as e:
            PrettyOutput.auto_print(f"❌ File encoding failed: {file_path} - {e}")
            return None

    @staticmethod
    def _get_mime_type(file_path: str, file_type: str) -> str:
        """
        Get the MIME type of a file

        Args:
            file_path: File path
            file_type: File type

        Returns:
            str: MIME type
        """
        ext = os.path.splitext(file_path)[1].lower().lstrip(".")

        mime_map = {
            "image": {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
            }
        }

        return mime_map.get(file_type, {}).get(ext, "application/octet-stream")
