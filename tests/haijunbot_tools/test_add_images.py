# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_tools.add_images module"""

import base64
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from haijunbot.haijunbot_tools.add_images import AddImagesTool


class TestAddImagesTool:
    """Tests for AddImagesTool class"""

    @pytest.fixture
    def tool(self):
        """Create test AddImagesTool instance"""
        return AddImagesTool()

    @pytest.fixture
    def mock_agent(self):
        """Create mock Agent instance"""
        agent = MagicMock()
        agent.add_multimodal_content = MagicMock()
        return agent

    @pytest.fixture
    def sample_image(self):
        """Create sample image file"""
        # Create a simple 1x1 pixel PNG image
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        )
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(png_data)
            filepath = f.name

        yield filepath

        # Cleanup
        if os.path.exists(filepath):
            os.unlink(filepath)

    @pytest.fixture
    def sample_jpg_image(self):
        """Create sample JPG image file"""
        # Create a simple JPG image (actually a text file, but for testing format validation)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jpg", delete=False) as f:
            f.write("fake jpg content")
            filepath = f.name

        yield filepath

        # Cleanup
        if os.path.exists(filepath):
            os.unlink(filepath)

    def test_add_single_local_image(self, tool, mock_agent, sample_image):
        """Test adding a single local image"""
        args = {
            "images": [{"path": sample_image}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        assert mock_agent.add_multimodal_content.called
        # Verify content passed to agent
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        assert len(call_args) == 2  # prompt + image
        assert call_args[0]["type"] == "text"
        assert call_args[1]["type"] == "image_url"

    def test_add_multiple_local_images(self, tool, mock_agent, sample_image):
        """Test adding multiple local images"""
        args = {
            "images": [
                {"path": sample_image, "description": "Image 1"},
                {"path": sample_image, "description": "Image 2"},
            ],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        assert mock_agent.add_multimodal_content.called
        # Verify content passed to agent
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        assert len(call_args) == 5  # prompt + (desc + image) * 2

    def test_add_image_with_description(self, tool, mock_agent, sample_image):
        """Test adding image with description"""
        args = {
            "images": [{"path": sample_image, "description": "This is a test image"}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        # Verify description was added
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        # Should have: prompt, description, image
        assert len(call_args) == 3
        assert call_args[1]["type"] == "text"
        assert "This is a test image" in call_args[1]["text"]

    def test_add_image_with_custom_prompt(self, tool, mock_agent, sample_image):
        """Test using custom prompt when adding image"""
        args = {
            "images": [{"path": sample_image}],
            "prompt": "Please describe this image in detail:",
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        # Verify custom prompt was used
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        assert call_args[0]["text"] == "Please describe this image in detail:"

    def test_add_url_image(self, tool, mock_agent):
        """Test adding URL image"""
        args = {
            "images": [{"path": "https://example.com/image.png"}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        # Verify URL was used directly
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        assert call_args[1]["image_url"] == "https://example.com/image.png"

    def test_add_nonexistent_image(self, tool, mock_agent):
        """Test adding nonexistent image"""
        args = {
            "images": [{"path": "/nonexistent/image.png"}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is False
        assert not mock_agent.add_multimodal_content.called

    def test_add_unsupported_format(self, tool, mock_agent):
        """Test adding unsupported format"""
        # Create a .txt file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("not an image")
            txt_file = f.name

        try:
            args = {
                "images": [{"path": txt_file}],
                "agent": mock_agent,
            }

            result = tool.execute(args)

            assert result["success"] is False
            assert not mock_agent.add_multimodal_content.called
        finally:
            if os.path.exists(txt_file):
                os.unlink(txt_file)

    def test_add_empty_images_list(self, tool, mock_agent):
        """Test empty image list"""
        args = {
            "images": [],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is False
        assert not mock_agent.add_multimodal_content.called

    def test_add_image_without_path(self, tool, mock_agent):
        """Test image missing path parameter"""
        args = {
            "images": [{"description": "Image without path"}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is False
        assert not mock_agent.add_multimodal_content.called

    def test_add_image_without_agent(self, tool, sample_image):
        """Test not providing agent parameter"""
        args = {
            "images": [{"path": sample_image}],
        }

        result = tool.execute(args)

        # Should still succeed, just does not call agent
        assert result["success"] is True

    def test_partial_success(self, tool, mock_agent, sample_image):
        """Test partial success scenario"""
        args = {
            "images": [
                {"path": sample_image},  # Valid
                {"path": "/nonexistent/image.png"},  # Invalid
            ],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        assert mock_agent.add_multimodal_content.called

    def test_validate_image_format(self, tool, sample_image):
        """Test image format validation"""
        # Valid PNG format
        assert tool._validate_image_format(sample_image) is True

        # Valid JPG format
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            jpg_file = f.name
        try:
            assert tool._validate_image_format(jpg_file) is True
        finally:
            if os.path.exists(jpg_file):
                os.unlink(jpg_file)

        # Invalid format
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            txt_file = f.name
        try:
            assert tool._validate_image_format(txt_file) is False
        finally:
            if os.path.exists(txt_file):
                os.unlink(txt_file)

        # URL should always return True
        assert tool._validate_image_format("https://example.com/image.png") is True
        assert tool._validate_image_format("data:image/png;base64,...") is True

    def test_validate_image_size(self, tool, sample_image):
        """Test image size validation"""
        # Small image should pass
        assert tool._validate_image_size(sample_image) is True

        # URL should always return True
        assert tool._validate_image_size("https://example.com/image.png") is True

        # Nonexistent file should return False
        assert tool._validate_image_size("/nonexistent/image.png") is False

    def test_encode_image_to_base64(self, tool, sample_image):
        """Test image base64 encoding"""
        encoded = tool._encode_image_to_base64(sample_image)

        assert encoded is not None
        assert encoded.startswith("data:image/png;base64,")

        # URL should be returned directly
        url = "https://example.com/image.png"
        assert tool._encode_image_to_base64(url) == url

        # Nonexistent file should return None
        assert tool._encode_image_to_base64("/nonexistent/image.png") is None

    def test_image_with_detail_parameter(self, tool, mock_agent, sample_image):
        """Test image detail parameter"""
        args = {
            "images": [{"path": sample_image, "detail": "high"}],
            "agent": mock_agent,
        }

        result = tool.execute(args)

        assert result["success"] is True
        # Verify detail parameter was passed
        call_args = mock_agent.add_multimodal_content.call_args[0][0]
        image_content = call_args[1]
        assert image_content["detail"] == "high"

    def test_expand_user_path(self, tool, mock_agent):
        """Test user path expansion (~)"""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(b"fake image")
            temp_path = f.name

        try:
            # Use ~ path (if possible)
            home_dir = os.path.expanduser("~")
            if temp_path.startswith(home_dir):
                relative_path = temp_path[len(home_dir):].lstrip("/")
                tilde_path = f"~/{relative_path}"

                args = {
                    "images": [{"path": tilde_path}],
                    "agent": mock_agent,
                }

                result = tool.execute(args)

                # Path should be resolved correctly
                assert result["success"] is True
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
