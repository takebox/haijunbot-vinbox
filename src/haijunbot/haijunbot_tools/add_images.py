# -*- coding: utf-8 -*-
"""
Add images tool

Allows the LLM to proactively add images to the current conversation context, for image analysis scenarios.
"""

import base64
import os
from typing import Any, Dict, List, Optional

from haijunbot.haijunbot_platform.content_types import (
    ContentBlock,
    ImageURLContent,
    TextContent,
    CONTENT_CONFIG,
)
from haijunbot.haijunbot_utils.output import PrettyOutput


class AddImagesTool:
    """Tool for adding images to the conversation context"""

    name = "add_images"
    description = "Add images (local paths or URLs) to the current conversation context for the model to recognize; use when a task requires analyzing screenshots/interfaces/charts."

    parameters = {
        "type": "object",
        "properties": {
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Image file path (local path or URL)",
                        },
                        "description": {
                            "type": "string",
                            "description": "Image description (optional)",
                            "default": "",
                        },
                        "detail": {
                            "type": "string",
                            "enum": ["low", "high", "auto"],
                            "description": "Image parsing detail",
                            "default": "auto",
                        },
                    },
                    "required": ["path"],
                },
                "description": "Image list",
            },
            "prompt": {
                "type": "string",
                "description": "Prompt text after adding images (optional)",
                "default": "Please analyze the following image content:",
            },
        },
        "required": ["images"],
    }

    def _validate_image_format(self, path: str) -> bool:
        """Validate the image format

        Args:
            path: Image path

        Returns:
            bool: Whether the format is supported
        """
        # If it is a URL or base64, assume the format is correct
        if path.startswith(("http://", "https://", "data:")):
            return True

        # Check the file extension
        supported_formats = CONTENT_CONFIG.get(
            "supported_image_formats", ["jpg", "jpeg", "png", "gif", "webp"]
        )
        # Ensure supported_formats is a list
        if not isinstance(supported_formats, list):
            supported_formats = ["jpg", "jpeg", "png", "gif", "webp"]

        ext = os.path.splitext(path)[1].lower().lstrip(".")
        return ext in supported_formats

    def _validate_image_size(self, path: str) -> bool:
        """Validate the image size

        Args:
            path: Image path

        Returns:
            bool: Whether the size is within the limit
        """
        # If it is a URL or base64, skip the size check
        if path.startswith(("http://", "https://", "data:")):
            return True

        try:
            max_size = CONTENT_CONFIG.get("max_image_size", 20 * 1024 * 1024)
            # Ensure max_size is an integer
            if not isinstance(max_size, int):
                max_size = 20 * 1024 * 1024

            file_size = os.path.getsize(path)
            return file_size <= max_size
        except OSError:
            return False

    def _encode_image_to_base64(self, path: str) -> Optional[str]:
        """Encode the image as base64

        Args:
            path: Image path

        Returns:
            Optional[str]: base64-encoded string, or None on failure
        """
        try:
            # If it is already a URL or base64, return directly
            if path.startswith(("http://", "https://", "data:")):
                return path

            # Read the file and encode it
            with open(path, "rb") as f:
                image_data = f.read()
                base64_data = base64.b64encode(image_data).decode("utf-8")

                # Get the MIME type
                ext = os.path.splitext(path)[1].lower().lstrip(".")
                mime_map = {
                    "jpg": "image/jpeg",
                    "jpeg": "image/jpeg",
                    "png": "image/png",
                    "gif": "image/gif",
                    "webp": "image/webp",
                }
                mime_type = mime_map.get(ext, "application/octet-stream")

                return f"data:{mime_type};base64,{base64_data}"
        except Exception as e:
            PrettyOutput.auto_print(f"❌ Image encoding failed: {path} - {e}")
            return None

    def execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the add-images operation

        Args:
            args: Tool arguments

        Returns:
            Dict[str, Any]: Execution result
        """
        try:
            # Check whether multimodal is supported
            agent = args.get("agent")
            if agent and hasattr(agent, "platform"):
                if not agent.platform.supports_multimodal():
                    warning_msg = "⚠️ The current model does not support multimodal input; image addition was skipped. To use multimodal features, set supports_multimodal: true in llm_config"
                    PrettyOutput.auto_print(warning_msg)
                    return {
                        "success": True,
                        "stdout": warning_msg,
                        "stderr": "",
                        "skipped": True,
                    }

            images = args.get("images", [])
            prompt = args.get("prompt", "Please analyze the following image content:")

            if not images:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": "The image list cannot be empty",
                }

            # Validate and process each image
            processed_images: List[ContentBlock] = []
            errors = []

            for i, image_info in enumerate(images):
                try:
                    # Validate the image path
                    path = image_info.get("path")
                    if not path:
                        errors.append(f"Image #{i + 1} is missing the path argument")
                        continue

                    # Check whether the image exists (local file)
                    if not path.startswith(("http://", "https://", "data:")):
                        expanded_path = os.path.expanduser(path)
                        abs_path = os.path.abspath(expanded_path)
                        if not os.path.exists(abs_path):
                            errors.append(f"Image #{i + 1} does not exist: {path}")
                            continue
                        path = abs_path

                    # Validate the image format
                    if not self._validate_image_format(path):
                        errors.append(f"Image #{i + 1} format is not supported: {path}")
                        continue

                    # Validate the image size
                    if not self._validate_image_size(path):
                        errors.append(f"Image #{i + 1} size exceeds the limit: {path}")
                        continue

                    # Encode the image
                    encoded_image = self._encode_image_to_base64(path)
                    if not encoded_image:
                        errors.append(f"Image #{i + 1} encoding failed: {path}")
                        continue

                    # Add the description (if any)
                    description = image_info.get("description", "")
                    if description:
                        text_content: TextContent = {
                            "type": "text",
                            "text": description,
                        }
                        processed_images.append(text_content)

                    # Create the image content block
                    image_content: ImageURLContent = {
                        "type": "image_url",
                        "image_url": encoded_image,
                        "detail": image_info.get("detail", "auto"),
                    }
                    processed_images.append(image_content)

                except Exception as e:
                    errors.append(f"Failed to process image #{i + 1}: {str(e)}")

            if not processed_images:
                return {
                    "success": False,
                    "stdout": "",
                    "stderr": f"No valid images. Errors: {'; '.join(errors)}",
                }

            # Build the final message content
            final_content: List[ContentBlock] = []
            if prompt:
                final_content.append({"type": "text", "text": prompt})
            final_content.extend(processed_images)

            # Add the images to the current conversation context
            agent = args.get("agent")
            if agent and hasattr(agent, "add_multimodal_content"):
                agent.add_multimodal_content(final_content)

            # Build the return result
            success_count = len(
                [b for b in processed_images if b.get("type") == "image_url"]
            )
            result_msg = f"✅ Successfully added {success_count} images to the conversation context"
            if errors:
                result_msg += f"\n⚠ Some errors: {'; '.join(errors)}"

            PrettyOutput.auto_print(result_msg)

            return {
                "success": True,
                "stdout": result_msg,
                "stderr": "",
                "processed_images": final_content,
            }

        except Exception as e:
            error_msg = f"Failed to add images: {str(e)}"
            PrettyOutput.auto_print(f"❌ {error_msg}")
            return {
                "success": False,
                "stdout": "",
                "stderr": error_msg,
            }
