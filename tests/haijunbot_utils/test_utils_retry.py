# -*- coding: utf-8 -*-
"""Unit tests for haijunbot_utils.utils retry functions"""

import pytest
from unittest.mock import patch

from haijunbot.haijunbot_utils.utils import while_success, while_true, _reset_retry_count


class TestWhileSuccess:
    """Tests for while_success function"""

    def setup_method(self):
        """Reset retry counter before each test"""
        _reset_retry_count()

    def test_success_on_first_try(self):
        """Test success on first try"""

        def test_func():
            return "success"

        result = while_success(test_func)
        assert result == "success"

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_success_after_retries(self, mock_sleep):
        """Test success after retries"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Not ready yet")
            return "success"

        result = while_success(test_func)
        assert result == "success"
        assert call_count[0] == 3

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep):
        """Test exceeding maximum retry count"""

        def test_func():
            raise ValueError("Always fails")

        with pytest.raises(ValueError, match="Always fails"):
            while_success(test_func)

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_sleep_between_retries(self, mock_sleep):
        """Test sleep between retries uses exponential backoff"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Not ready")
            return "success"

        result = while_success(test_func)
        assert result == "success"
        # Should sleep once (after first failure), wait time is 2^(1-1) = 1s
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1.0)

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        """Test exponential backoff mechanism"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ValueError("Not ready")
            return "success"

        result = while_success(test_func)
        assert result == "success"
        # After 1st failure wait 2^(1-1) = 1s
        # After 2nd failure wait 2^(2-1) = 2s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1.0  # First wait 1s
        assert mock_sleep.call_args_list[1][0][0] == 2.0  # Second wait 2s


class TestWhileTrue:
    """Tests for while_true function"""

    def setup_method(self):
        """Reset retry counter before each test"""
        _reset_retry_count()

    def test_true_on_first_try(self):
        """Test returning True on first try"""

        def test_func():
            return True

        result = while_true(test_func)
        assert result is True

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_true_after_retries(self, mock_sleep):
        """Test returning True after retries"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            return call_count[0] >= 3

        result = while_true(test_func)
        assert result is True
        assert call_count[0] == 3

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_false_after_max_retries(self, mock_sleep):
        """Test returning False after exceeding maximum retry count"""

        def test_func():
            return False

        result = while_true(test_func)
        assert result is False

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_sleep_between_retries(self, mock_sleep):
        """Test sleep between retries uses exponential backoff"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            return call_count[0] >= 2

        result = while_true(test_func)
        assert result is True
        # Should sleep once (after first False return), wait time is 2^(1-1) = 1s
        assert mock_sleep.call_count == 1
        mock_sleep.assert_called_with(1.0)

    def test_exception_propagates(self):
        """Test exceptions propagate (not caught)"""

        def test_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            while_true(test_func)

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_exponential_backoff(self, mock_sleep):
        """Test exponential backoff mechanism"""
        call_count = [0]

        def test_func():
            call_count[0] += 1
            return call_count[0] >= 3

        result = while_true(test_func)
        assert result is True
        # After 1st False return wait 2^(1-1) = 1s
        # After 2nd False return wait 2^(2-1) = 2s
        assert mock_sleep.call_count == 2
        assert mock_sleep.call_args_list[0][0][0] == 1.0  # First wait 1s
        assert mock_sleep.call_args_list[1][0][0] == 2.0  # Second wait 2s


class TestSharedRetryCounter:
    """Tests for shared retry counter between two functions"""

    def setup_method(self):
        """Reset retry counter before each test"""
        _reset_retry_count()

    @patch("haijunbot.haijunbot_utils.utils.time.sleep")
    def test_shared_counter_between_functions(self, mock_sleep):
        """Test while_true and while_success share retry counter"""
        call_count = [0]

        def inner_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("Not ready")
            return "success"

        def outer_func():
            # After while_success fails 2 times, counter is 2
            # When while_true fails again, counter continues to increment
            result = while_success(inner_func)
            return result is not None

        # First call to while_success fails once, then succeeds
        # Counter gets reset
        result = while_true(outer_func)
        assert result is True
