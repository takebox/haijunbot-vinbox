"""
Multimodal functionality tests

Tests the Platform module's multimodal support functionality
"""

import pytest
from typing import Dict, List, Tuple, Union


from haijunbot.haijunbot_platform.content_types import (
    TextContent,
    ImageURLContent,
    ContentBlock,
)
from haijunbot.haijunbot_platform.content_processor import ContentProcessor
from haijunbot.haijunbot_platform.base import BasePlatform


class TestContentTypes:
    """Test content type definitions"""

    def test_text_content(self):
        """Test text content type"""
        content: TextContent = {"type": "text", "text": "Hello, world!"}
        assert content["type"] == "text"
        assert content["text"] == "Hello, world!"

    def test_image_content(self):
        """Test image content type"""
        content: ImageURLContent = {
            "type": "image_url",
            "image_url": "https://example.com/image.jpg",
            "detail": "high",
        }
        assert content["type"] == "image_url"
        assert content["image_url"] == "https://example.com/image.jpg"
        assert content["detail"] == "high"


class TestContentProcessor:
    """Test content processor"""

    def setup_method(self):
        """Prepare before test"""
        self.processor = ContentProcessor()

    def test_process_string_input(self):
        """Test processing string input"""
        result = self.processor.process_message("Hello, world!")
        assert len(result) == 1
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello, world!"

    def test_process_list_input(self):
        """Test processing list input"""
        content_list: List[ContentBlock] = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world!"},
        ]
        result = self.processor.process_message(content_list)
        assert len(result) == 2
        # Use type assertion to handle union types
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Hello"
        assert result[1]["type"] == "text"
        assert result[1]["text"] == "world!"

    def test_validate_text_content(self):
        """Test validating text content"""
        content: TextContent = {"type": "text", "text": "Hello"}
        assert self.processor.validate_content(content) is True

    def test_validate_image_content(self):
        """Test validating image content"""
        content: ImageURLContent = {
            "type": "image_url",
            "image_url": "https://example.com/image.jpg",
        }
        assert self.processor.validate_content(content) is True

    def test_validate_invalid_content(self):
        """Test validating invalid content"""
        content = {"type": "invalid", "data": "test"}
        with pytest.raises(ValueError):
            self.processor.validate_content(content)  # type: ignore


class TestBasePlatformMultimodal:
    """Test BasePlatform multimodal support"""

    def setup_method(self):
        """Prepare before test"""

        # Create a concrete BasePlatform subclass for testing
        class TestPlatform(BasePlatform):
            def chat(self, message: Union[str, List[ContentBlock]]):
                # Process multimodal messages
                from haijunbot.haijunbot_platform.content_processor import ContentProcessor

                processed = ContentProcessor.process_message(message)
                # Return processed content
                yield "content", f"Processed: {len(processed)} content blocks"

            def name(self) -> str:
                return "TestPlatform"

            @classmethod
            def platform_name(cls) -> str:
                return "test"

            def delete_chat(self) -> bool:
                return True

            def set_messages(self, messages: List[Dict[str, str]]) -> None:
                pass

            def get_messages(self) -> List[Dict[str, str]]:
                return []

            def set_model_name(self, model_name: str):
                pass

            def set_system_prompt(self, message: str):
                pass

            def get_model_list(self) -> List[Tuple[str, str]]:
                return []

            @classmethod
            def get_required_env_keys(cls) -> List[str]:
                return []

            def trim_messages(self) -> bool:
                return True

        self.platform = TestPlatform()

    def test_chat_with_string(self):
        """Test calling chat method with a string"""
        result = list(self.platform.chat("Hello, world!"))
        assert len(result) == 1
        assert result[0][0] == "content"
        assert "Processed: 1 content blocks" in result[0][1]

    def test_chat_with_multimodal(self):
        """Test calling chat method with multimodal content"""
        content_list: List[ContentBlock] = [
            {"type": "text", "text": "Hello"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ]
        result = list(self.platform.chat(content_list))
        assert len(result) == 1
        assert result[0][0] == "content"
        assert "Processed: 2 content blocks" in result[0][1]

    def test_process_multimodal_content(self):
        """Test processing multimodal content"""
        from haijunbot.haijunbot_platform.content_processor import ContentProcessor

        # Test string input
        result1 = ContentProcessor.process_message("Hello")
        assert len(result1) == 1
        assert result1[0]["type"] == "text"

        # Test list input
        content_list: List[ContentBlock] = [
            {"type": "text", "text": "Hello"},
            {"type": "text", "text": "world!"},
        ]
        result2 = ContentProcessor.process_message(content_list)
        assert len(result2) == 2
        assert result2[0]["type"] == "text"
        assert result2[0]["text"] == "Hello"
        assert result2[1]["type"] == "text"
        assert result2[1]["text"] == "world!"

    def test_validate_content(self):
        """Test validating content"""
        from haijunbot.haijunbot_platform.content_processor import ContentProcessor

        # Test valid content
        valid_content: TextContent = {"type": "text", "text": "Hello"}
        assert ContentProcessor.validate_content(valid_content) is True

        # Test invalid content
        invalid_content = {"type": "invalid", "data": "test"}
        with pytest.raises(ValueError):
            ContentProcessor.validate_content(invalid_content)  # type: ignore


class TestMultimodalIntegration:
    """Test multimodal integration functionality"""

    def test_mixed_content_processing(self):
        """Test mixed content processing"""
        processor = ContentProcessor()

        # Create mixed content
        mixed_content: List[ContentBlock] = [
            {"type": "text", "text": "Look at this image:"},
            {
                "type": "image_url",
                "image_url": "https://example.com/image.jpg",
                "detail": "high",
            },
            {"type": "text", "text": "And look at this image again:"},
            {
                "type": "image_url",
                "image_url": "https://example.com/image2.jpg",
            },
        ]

        # Process mixed content
        result = processor.process_message(mixed_content)

        # Verify results
        assert len(result) == 4
        assert result[0]["type"] == "text"
        assert result[0]["text"] == "Look at this image:"
        assert result[1]["type"] == "image_url"
        assert result[1]["image_url"] == "https://example.com/image.jpg"
        assert result[2]["type"] == "text"
        assert result[2]["text"] == "And look at this image again:"
        assert result[3]["type"] == "image_url"
        assert result[3]["image_url"] == "https://example.com/image2.jpg"

    def test_backward_compatibility(self):
        """Test backward compatibility"""
        processor = ContentProcessor()

        # Test plain text messages
        text_result = processor.process_message("Hello, world!")
        assert len(text_result) == 1
        assert text_result[0]["type"] == "text"
        assert text_result[0]["text"] == "Hello, world!"

        # Test empty string
        empty_result = processor.process_message("")
        assert len(empty_result) == 1
        assert empty_result[0]["type"] == "text"
        assert empty_result[0]["text"] == ""

    def test_content_validation(self):
        """Test content validation"""
        processor = ContentProcessor()

        # Test valid content
        valid_contents = [
            {"type": "text", "text": "Hello"},
            {"type": "image_url", "image_url": "https://example.com/image.jpg"},
        ]

        for content in valid_contents:
            assert processor.validate_content(content) is True  # type: ignore

        # Test invalid content
        invalid_contents = [
            {"type": "invalid"},
            {"type": "text"},  # Missing text field
            {"type": "image_url"},  # Missing image_url field
        ]

        for content in invalid_contents:
            with pytest.raises(ValueError):
                processor.validate_content(content)  # type: ignore


class TestMultimodalConfig:
    """Test multimodal configuration items"""

    def test_supports_multimodal_default(self):
        """Test that supports_multimodal defaults to False"""
        from haijunbot.haijunbot_platform.base import BasePlatform
        from unittest.mock import patch

        # Mock get_llm_config returning an empty dict
        with patch("haijunbot.haijunbot_platform.base.get_llm_config", return_value={}):
            # Create a concrete subclass to test
            class TestPlatform(BasePlatform):
                def chat(self, message):
                    yield ("content", "test")

                def delete_chat(self):
                    pass

                def get_messages(self):
                    return []

                def get_model_list(self):
                    return []

                def get_required_env_keys(self):
                    return []

                def name(self):
                    return "test"

                def platform_name(self):
                    return "test"

                def set_messages(self, messages):
                    pass

                def set_model_name(self, model_name):
                    pass

                def set_system_prompt(self, message):
                    pass

                def trim_messages(self) -> bool:
                    return True

            platform = TestPlatform()
            assert platform.supports_multimodal() is False

    def test_supports_multimodal_enabled(self):
        """Test supports_multimodal set to True"""
        from haijunbot.haijunbot_platform.base import BasePlatform
        from unittest.mock import patch

        # Mock get_llm_config returning supports_multimodal: True
        with patch(
            "haijunbot.haijunbot_platform.base.get_llm_config",
            return_value={"supports_multimodal": True},
        ):

            class TestPlatform(BasePlatform):
                def chat(self, message):
                    yield ("content", "test")

                def delete_chat(self):
                    pass

                def get_messages(self):
                    return []

                def get_model_list(self):
                    return []

                def get_required_env_keys(self):
                    return []

                def name(self):
                    return "test"

                def platform_name(self):
                    return "test"

                def set_messages(self, messages):
                    pass

                def set_model_name(self, model_name):
                    pass

                def set_system_prompt(self, message):
                    pass

                def trim_messages(self) -> bool:
                    return True

            platform = TestPlatform()
            assert platform.supports_multimodal() is True

    def test_openai_rejects_multimodal_if_not_supported(self):
        """Test OpenAIModel silently degrades to plain text when multimodal is not supported"""
        from haijunbot.haijunbot_platform.openai import OpenAIModel
        from haijunbot.haijunbot_platform.content_types import (
            TextContent,
            ImageURLContent,
            ContentBlock,
        )
        from unittest.mock import patch, MagicMock

        # Mock get_llm_config returning supports_multimodal: False
        with patch(
            "haijunbot.haijunbot_platform.base.get_llm_config",
            return_value={"supports_multimodal": False},
        ):
            # Mock OpenAI client
            mock_client = MagicMock()
            # Mock API response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "This is a test response"
            mock_client.chat.completions.create.return_value = mock_response

            with patch(
                "haijunbot.haijunbot_platform.openai.OpenAI", return_value=mock_client
            ):
                platform = OpenAIModel()

                # Construct multimodal message
                text_content: TextContent = {
                    "type": "text",
                    "text": "What is in this image?",
                }
                image_content: ImageURLContent = {
                    "type": "image_url",
                    "image_url": "https://example.com/image.jpg",
                }
                multimodal_message: List[ContentBlock] = [text_content, image_content]

                # Verify no exception is raised, but silently degrades
                # Trigger chat method, since it's a generator, need to iterate
                responses = list(platform.chat(multimodal_message))

                # Verify there is response content
                assert len(responses) > 0
                # Verify API was called (may be called multiple times due to streaming degradation logic)
                assert mock_client.chat.completions.create.call_count >= 1
                # Get the parameters of the last call
                call_args = mock_client.chat.completions.create.call_args
                messages = call_args.kwargs.get(
                    "messages", call_args[1].get("messages", [])
                )
                # Verify user message is in plain text format
                user_msg = (
                    messages[-2] if len(messages) >= 2 else messages[-1]
                )  # Second to last is the user message
                assert user_msg["role"] == "user"
                assert isinstance(user_msg["content"], str)
                assert "What is in this image?" in user_msg["content"]

    def test_haijun_rejects_multimodal_if_not_supported(self):
        """Test HaijunModel silently degrades to plain text when multimodal is not supported"""
        from haijunbot.haijunbot_platform.haijun import HaijunModel
        from haijunbot.haijunbot_platform.content_types import (
            TextContent,
            ImageURLContent,
            ContentBlock,
        )
        from unittest.mock import patch, MagicMock

        # Mock get_llm_config returning supports_multimodal: False
        with patch(
            "haijunbot.haijunbot_platform.base.get_llm_config",
            return_value={"supports_multimodal": False},
        ):
            # Mock Juglow client
            mock_client = MagicMock()
            # Mock stream context manager
            mock_stream = MagicMock()
            mock_stream.text_stream = ["This is a test response"]
            mock_stream.__enter__ = MagicMock(return_value=mock_stream)
            mock_stream.__exit__ = MagicMock(return_value=False)
            mock_client.messages.stream.return_value = mock_stream

            with patch(
                "haijunbot.haijunbot_platform.haijun.Juglow", return_value=mock_client
            ):
                platform = HaijunModel()

                # Construct multimodal message
                text_content: TextContent = {
                    "type": "text",
                    "text": "What is in this image?",
                }
                image_content: ImageURLContent = {
                    "type": "image_url",
                    "image_url": "https://example.com/image.jpg",
                }
                multimodal_message: List[ContentBlock] = [text_content, image_content]

                # Verify no exception is raised, but silently degrades
                responses = list(platform.chat(multimodal_message))

                # Verify there is response content
                assert len(responses) > 0
                # Verify API was called
                mock_client.messages.stream.assert_called_once()
                call_args = mock_client.messages.stream.call_args
                messages = call_args.kwargs.get(
                    "messages", call_args[1].get("messages", [])
                )
                # Verify user message is in plain text format
                user_msg = messages[-1]
                assert user_msg["role"] == "user"
                assert isinstance(user_msg["content"], str)
                assert "What is in this image?" in user_msg["content"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
