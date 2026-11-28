# -*- coding: utf-8 -*-
"""Unit tests for the haijunbot_utils.http module"""

from unittest.mock import patch, MagicMock
import requests

from haijunbot.haijunbot_utils.http import (
    get_requests_session,
    post,
    get,
    put,
    delete,
    stream_post,
)


class TestGetRequestsSession:
    """Tests for get_requests_session function"""

    def test_returns_session(self):
        """Test returning Session object"""
        session = get_requests_session()
        assert isinstance(session, requests.Session)

    def test_session_has_user_agent(self):
        """Test Session includes User-Agent"""
        session = get_requests_session()
        assert "User-Agent" in session.headers
        assert "Mozilla" in session.headers["User-Agent"]


class TestPost:
    """Tests for post function"""

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_post_request(self, mock_get_session):
        """Test POST request"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = post("http://example.com", json={"key": "value"})

        mock_session.post.assert_called_once()
        assert result == mock_response

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_post_with_data(self, mock_get_session):
        """Test POST request with data"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.post.return_value = mock_response
        mock_get_session.return_value = mock_session

        post("http://example.com", data="test data")

        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs.get("data") == "test data"
        assert call_kwargs.get("timeout") is None


class TestGet:
    """Tests for get function"""

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_get_request(self, mock_get_session):
        """Test GET request"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.get.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = get("http://example.com")

        mock_session.get.assert_called_once_with(url="http://example.com", timeout=None)
        assert result == mock_response


class TestPut:
    """Tests for put function"""

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_put_request(self, mock_get_session):
        """Test PUT request"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.put.return_value = mock_response
        mock_get_session.return_value = mock_session

        put("http://example.com", data="test data")

        call_kwargs = mock_session.put.call_args[1]
        assert call_kwargs.get("data") == "test data"
        assert call_kwargs.get("timeout") is None


class TestDelete:
    """Tests for delete function"""

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_delete_request(self, mock_get_session):
        """Test DELETE request"""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.delete.return_value = mock_response
        mock_get_session.return_value = mock_session

        result = delete("http://example.com")

        mock_session.delete.assert_called_once_with(
            url="http://example.com", timeout=None
        )
        assert result == mock_response


class TestStreamPost:
    """Tests for stream_post function"""

    @patch("haijunbot.haijunbot_utils.http.get_requests_session")
    def test_stream_post(self, mock_get_session):
        """Test streaming POST request"""
        # Create mock session and response
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # iter_lines returns an iterator, chunk_size=1
        mock_response.iter_lines.return_value = iter([b"line1\n", b"line2\n"])

        # Context manager returned by post
        mock_post_context = MagicMock()
        mock_post_context.__enter__ = MagicMock(return_value=mock_response)
        mock_post_context.__exit__ = MagicMock(return_value=None)
        mock_session.post.return_value = mock_post_context

        # Session as context manager
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_get_session.return_value = mock_session

        result = list(stream_post("http://example.com", json={"key": "value"}))

        # Verify post was called with stream=True
        assert mock_session.post.called
        call_kwargs = mock_session.post.call_args[1]
        assert call_kwargs.get("stream") is True
        # Verify result
        assert len(result) == 2
        assert result[0] == "line1\n"
        assert result[1] == "line2\n"
