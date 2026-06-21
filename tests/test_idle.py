"""Tests for the idle time tracking module."""

from unittest.mock import MagicMock, patch

import pytest

from activity_tracker.idle import get_idle_ms


class TestGetIdleMs:
    """Verify idle time query via xprintidle subprocess."""

    def test_returns_idle_milliseconds(self) -> None:
        """Should return the idle time from xprintidle output."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="12345\n"),
        ):
            result = get_idle_ms()
            assert result == 12345

    def test_returns_zero_on_missing_binary(self) -> None:
        """Should return 0 if xprintidle is not in PATH."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            side_effect=FileNotFoundError("xprintidle not found"),
        ):
            result = get_idle_ms()
            assert result == 0

    def test_returns_zero_on_timeout(self) -> None:
        """Should return 0 if xprintidle times out."""
        import subprocess as sp

        with patch(
            "activity_tracker.idle.subprocess.run",
            side_effect=sp.TimeoutExpired(cmd="xprintidle", timeout=5),
        ):
            result = get_idle_ms()
            assert result == 0

    def test_returns_zero_on_nonzero_return_code(self) -> None:
        """Should return 0 if xprintidle exits with a non-zero code."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ):
            result = get_idle_ms()
            assert result == 0

    def test_returns_zero_on_invalid_output(self) -> None:
        """Should return 0 if xprintidle output is not a valid integer."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="not_a_number"),
        ):
            result = get_idle_ms()
            assert result == 0

    def test_returns_zero_on_empty_output(self) -> None:
        """Should return 0 if xprintidle output is empty."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            return_value=MagicMock(returncode=0, stdout=""),
        ):
            result = get_idle_ms()
            assert result == 0

    def test_handles_whitespace_in_output(self) -> None:
        """Should strip whitespace from xprintidle output."""
        with patch(
            "activity_tracker.idle.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="  42  \n"),
        ):
            result = get_idle_ms()
            assert result == 42
