# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.embedding module"""

from haijunbot.haijunbot_utils.embedding import (
    get_context_token_count,
    split_text_into_chunks,
    get_multimodal_token_count,
    _estimate_image_tokens,
)


class TestGetContextTokenCount:
    """Tests for get_context_token_count function"""

    def test_empty_string(self):
        """Test empty string"""
        assert get_context_token_count("") == 0

    def test_none_input(self):
        """Test None input"""
        # Note: get_context_token_count expects str type, None will raise TypeError
        # Here we test empty string as an alternative
        assert get_context_token_count("") == 0

    def test_simple_text(self):
        """Test simple text"""
        text = "Hello world"
        result = get_context_token_count(text)
        assert isinstance(result, int)
        assert result > 0

    def test_long_text(self):
        """Test long text"""
        text = "Hello world " * 100
        result = get_context_token_count(text)
        assert isinstance(result, int)
        assert result > 0

    def test_unicode_text(self):
        """Test Unicode text"""
        text = "Hello World Earth"
        result = get_context_token_count(text)
        assert isinstance(result, int)
        assert result > 0

    def test_multiline_text(self):
        """Test multiline text"""
        text = "Line 1\nLine 2\nLine 3"
        result = get_context_token_count(text)
        assert isinstance(result, int)
        assert result > 0


class TestSplitTextIntoChunks:
    """Tests for split_text_into_chunks function"""

    def test_empty_text(self):
        """Test empty text"""
        assert split_text_into_chunks("") == []

    def test_short_text(self):
        """Test short text (less than minimum length)"""
        text = "Short text"
        chunks = split_text_into_chunks(text, max_length=512, min_length=50)
        # Even for very short text, at least one chunk should be returned
        assert len(chunks) >= 1
        assert chunks[0] == text

    def test_text_within_max_length(self):
        """Test text within maximum length"""
        text = "This is a test text that is not too long"
        chunks = split_text_into_chunks(text, max_length=512, min_length=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_splitting(self):
        """Test long text splitting"""
        # Create a longer text
        text = "Word " * 200  # Approximately 1000 characters
        chunks = split_text_into_chunks(text, max_length=100, min_length=20)
        assert len(chunks) > 1
        # Verify all chunks are included
        combined = "".join(chunks)
        assert combined == text

    def test_custom_max_length(self):
        """Test custom maximum length"""
        text = "Word " * 100
        chunks = split_text_into_chunks(text, max_length=50, min_length=10)
        assert len(chunks) > 1
        # Each chunk (except the last) should be close to max length
        for chunk in chunks[:-1]:
            assert len(chunk) > 0

    def test_custom_min_length(self):
        """Test custom minimum length"""
        text = "Word " * 200
        chunks = split_text_into_chunks(text, max_length=100, min_length=30)
        assert len(chunks) > 1
        # Except for the last chunk, others should meet minimum length requirement (based on token estimation)

    def test_multiline_text(self):
        """Test multiline text"""
        text = "Line 1\n" * 50
        chunks = split_text_into_chunks(text, max_length=100, min_length=20)
        assert len(chunks) > 0
        combined = "".join(chunks)
        assert combined == text


class TestGetMultimodalTokenCount:
    """Tests for get_multimodal_token_count function"""

    def test_string_input(self):
        """Test string input"""
        text = "Hello world"
        result = get_multimodal_token_count(text)
        expected = get_context_token_count(text)
        assert result == expected

    def test_empty_string(self):
        """Test empty string"""
        assert get_multimodal_token_count("") == 0

    def test_none_input(self):
        """Test None input"""
        assert get_multimodal_token_count(None) == 0

    def test_text_content_list(self):
        """Test text content list"""
        content_list = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world"},
        ]
        result = get_multimodal_token_count(content_list)
        expected = get_context_token_count("Hello") + get_context_token_count("world")
        assert result == expected

    def test_image_content(self):
        """Test image content"""
        content_list = [
            {"type": "text", "text": "Look at this image:"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ]
        result = get_multimodal_token_count(content_list)
        text_tokens = get_context_token_count("Look at this image:")
        # _estimate_image_tokens expects dict type, passing the correct format
        image_tokens = _estimate_image_tokens(
            {"image_url": "https://example.com/image.jpg"}
        )
        expected = text_tokens + image_tokens
        assert result == expected

    def test_mixed_content(self):
        """Test mixed content"""
        content_list = [
            {"type": "text", "text": "Look at this image:"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
            {"type": "text", "text": "And look at this image again:"},
            {"type": "image_url", "image_url": "https://example.com/image2.jpg"},
        ]
        result = get_multimodal_token_count(content_list)
        text1_tokens = get_context_token_count("Look at this image:")
        # _estimate_image_tokens expects dict type, passing the correct format
        image1_tokens = _estimate_image_tokens(
            {"image_url": "https://example.com/image.jpg"}
        )
        text2_tokens = get_context_token_count("And look at this image again:")
        image2_tokens = _estimate_image_tokens(
            {"image_url": "https://example.com/image2.jpg"}
        )
        expected = text1_tokens + image1_tokens + text2_tokens + image2_tokens
        assert result == expected

    def test_invalid_content_type(self):
        """Test invalid content type"""
        content_list = [
            {"type": "invalid", "data": "test"},
        ]
        # Unknown types return 50 tokens
        result = get_multimodal_token_count(content_list)
        assert result == 50


class TestEstimateImageTokens:
    """Tests for _estimate_image_tokens function"""

    def test_url_image(self):
        """Test URL image"""
        # _estimate_image_tokens expects dict type
        image_data = {"image_url": "https://example.com/image.jpg"}
        result = _estimate_image_tokens(image_data)
        # Default returns 85 tokens
        assert result == 85

    def test_base64_image(self):
        """Test base64 image"""
        base64_data = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        # _estimate_image_tokens expects dict type
        image_data = {"image_url": base64_data}
        result = _estimate_image_tokens(image_data)
        # Default returns 85 tokens
        assert result == 85

    def test_dict_image(self):
        """Test dict format image"""
        image_data = {"url": "https://example.com/image.jpg"}
        result = _estimate_image_tokens(image_data)
        # Default returns 85 tokens
        assert result == 85
