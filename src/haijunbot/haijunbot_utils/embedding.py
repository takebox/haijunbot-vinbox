# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import List

from haijunbot.haijunbot_utils.output import PrettyOutput

# Set the tiktoken cache directory
script_dir = Path(__file__).parent
tiktoken_cache_dir = script_dir / "../haijunbot_data/tiktoken"
os.makedirs(tiktoken_cache_dir, exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"] = str(tiktoken_cache_dir.absolute())


def get_context_token_count(text: str) -> int:
    """Use tiktoken to get the number of tokens in the text.

    Parameters:
        text: The input text for which to count tokens

    Returns:
        int: The number of tokens in the text
    """
    # Defensive check: return 0 directly when the input is None or an empty string
    if text is None or text == "":
        return 0
    try:
        import tiktoken

        encoding = tiktoken.get_encoding("cl100k_base")
        # Adjust the token count to 10/7 of the original
        return int(len(encoding.encode(text)) * 10 / 7)
    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Failed to count tokens: {str(e)}")
        return int(
            len(text) // 4 * 10 / 7
        )  # Rough estimate of about 4 characters per token, adjusted to 10/7


def split_text_into_chunks(
    text: str, max_length: int = 512, min_length: int = 50
) -> List[str]:
    """Split text into chunks, cutting based on the number of tokens.

    Parameters:
        text: The input text to split
        max_length: The maximum number of tokens per chunk
        min_length: The minimum number of tokens per chunk (except the last chunk, which may be shorter)

    Returns:
        List[str]: A list of text chunks, where each chunk has no more than max_length tokens and no fewer than min_length
    """
    if not text:
        return []

    try:
        chunks = []
        current_chunk = ""
        current_tokens = 0

        # Process the text in larger chunks to avoid breaking token boundaries
        chunk_size = 50  # Process 50 characters at a time
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            chunk_tokens = get_context_token_count(chunk)

            # If adding the new chunk to the current one would exceed the maximum length, and the current chunk has already reached the minimum length, save the current chunk
            if (
                current_tokens + chunk_tokens > max_length
                and current_tokens >= min_length
            ):
                chunks.append(current_chunk)
                current_chunk = chunk
                current_tokens = chunk_tokens
            else:
                current_chunk += chunk
                current_tokens += chunk_tokens

        # Handle the last chunk, adding it regardless of its length
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    except Exception as e:
        PrettyOutput.auto_print(f"⚠️ Text splitting failed: {str(e)}")
        # Fall back to simple character splitting on error
        return [text[i : i + max_length] for i in range(0, len(text), max_length)]


def get_multimodal_token_count(content) -> int:
    """
    Calculate the number of tokens in multimodal content

    Args:
        content: Can be a string or a list of multimodal content

    Returns:
        int: The number of tokens
    """
    if isinstance(content, str):
        return get_context_token_count(content)

    if not isinstance(content, list):
        return 0

    total_tokens = 0
    for block in content:
        if not isinstance(block, dict):
            continue

        block_type = block.get("type")

        if block_type == "text":
            # Text content: calculate using tiktoken
            text = block.get("text", "")
            total_tokens += get_context_token_count(text)

        elif block_type == "image_url":
            # Image content: estimate tokens based on resolution
            total_tokens += _estimate_image_tokens(block)

        else:
            # Unknown type: basic token estimate
            total_tokens += 50

    return total_tokens


def _estimate_image_tokens(image_block: dict) -> int:
    """
    Estimate the number of tokens for an image

    Based on OpenAI and Haijun image token calculation rules:
    - OpenAI: based on a tile system, a 512x512 tile is about 170 tokens + a base of 85 tokens
    - Haijun: based on resolution, about 1,380 tokens/megapixel

    Args:
        image_block: The image content block

    Returns:
        int: The estimated number of tokens
    """
    # Default token estimate (when resolution cannot be obtained)
    default_tokens = 85  # OpenAI base tokens

    try:
        # Try to get image information from the base64 data
        image_url = image_block.get("image_url", {})
        if isinstance(image_url, dict):
            url = image_url.get("url", "")
        else:
            url = str(image_url)

        # If it is base64 data, try to parse the image header information
        if url.startswith("data:image/"):
            # Extract the base64 data from the data URL
            header, data = url.split(",", 1)
            # The image dimensions could be parsed further here, but that requires libraries such as PIL
            # For now, return the default value
            return default_tokens

        # If it is a URL, the dimensions cannot be obtained directly, return the default value
        return default_tokens

    except Exception:
        return default_tokens
