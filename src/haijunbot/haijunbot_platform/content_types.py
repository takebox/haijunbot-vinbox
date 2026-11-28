# -*- coding: utf-8 -*-
"""
Multimodal content type definitions

Defines the data structures required to support multimodal input, including text, image, audio, video and other content block types.
"""

from typing import TypedDict, Union, Literal
from typing_extensions import NotRequired


class TextContent(TypedDict):
    """Text content block"""

    type: Literal["text"]
    text: str


class ImageURLContent(TypedDict):
    """Image content block"""

    type: Literal["image_url"]
    image_url: Union[str, dict]  # URL or base64 data
    detail: NotRequired[Literal["low", "high", "auto"]]  # Image resolution detail


# Content block union type
ContentBlock = Union[TextContent, ImageURLContent]


# Content type configuration
CONTENT_CONFIG = {
    "max_image_size": 20 * 1024 * 1024,  # 20MB
    "supported_image_formats": ["jpg", "jpeg", "png", "gif", "webp"],
    "image_detail_default": "auto",
}
