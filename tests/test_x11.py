"""Tests for the X11 active window detection module."""

from unittest.mock import MagicMock, patch

import pytest

from activity_tracker.x11 import (
    WindowInfo,
    _get_atom,
    _get_window_title,
    get_active_window,
)


class TestGetAtom:
    """Verify atom resolution."""

    def test_returns_atom_id(self) -> None:
        """Should return the numeric atom ID."""
        d = MagicMock()
        d.intern_atom.return_value = 42
        result = _get_atom(d, "_NET_ACTIVE_WINDOW")
        assert result == 42

    def test_returns_none_on_exception(self) -> None:
        """Should return None if atom resolution fails."""
        d = MagicMock()
        d.intern_atom.side_effect = Exception("X11 error")
        result = _get_atom(d, "_NET_ACTIVE_WINDOW")
        assert result is None


class TestGetWindowTitle:
    """Verify window title retrieval from _NET_WM_NAME / WM_NAME."""

    def test_prefers_net_wm_name(self) -> None:
        """_NET_WM_NAME should be tried before WM_NAME."""
        d = MagicMock()
        win = MagicMock()
        d.intern_atom.side_effect = [42, 43]
        mock_prop = MagicMock()
        mock_prop.value = "My Window – Firefox".encode("utf-8")
        win.get_full_property.return_value = mock_prop
        result = _get_window_title(d, win)
        assert result == "My Window – Firefox"
        # Only _NET_WM_NAME queried, WM_NAME not needed
        assert d.intern_atom.call_count == 1

    def test_falls_back_to_wm_name(self) -> None:
        """Should fall back to WM_NAME if _NET_WM_NAME is None."""
        d = MagicMock()
        win = MagicMock()
        d.intern_atom.side_effect = [42, 43]
        win.get_full_property.side_effect = [None, MagicMock(value=b"Legacy Title")]
        result = _get_window_title(d, win)
        assert result == "Legacy Title"

    def test_strips_null_bytes(self) -> None:
        """Null bytes in titles should be stripped."""
        d = MagicMock()
        win = MagicMock()
        d.intern_atom.return_value = 42
        mock_prop = MagicMock()
        mock_prop.value = "Title\x00Extra".encode("utf-8")
        win.get_full_property.return_value = mock_prop
        result = _get_window_title(d, win)
        assert result == "Title"

    def test_handles_bytes_decode(self) -> None:
        """String titles (not bytes) should work."""
        d = MagicMock()
        win = MagicMock()
        d.intern_atom.return_value = 42
        mock_prop = MagicMock()
        mock_prop.value = "Plain Title"
        win.get_full_property.return_value = mock_prop
        result = _get_window_title(d, win)
        assert result == "Plain Title"

    def test_returns_none_on_all_failures(self) -> None:
        """Should return None if all title reads fail."""
        d = MagicMock()
        win = MagicMock()
        d.intern_atom.side_effect = Exception("X11 error")
        result = _get_window_title(d, win)
        assert result is None


class TestGetActiveWindow:
    """Verify the full active window query pipeline."""

    @patch("activity_tracker.x11.display.Display")
    def test_returns_window_info(self, mock_display_cls) -> None:
        """Should return a WindowInfo with class and title."""
        mock_d = MagicMock()
        mock_display_cls.return_value = mock_d

        mock_root = MagicMock()
        mock_d.screen.return_value.root = mock_root

        mock_prop = MagicMock()
        mock_prop.value = (12345,)
        mock_root.get_full_property.return_value = mock_prop

        mock_win = MagicMock()
        mock_d.create_resource_object.return_value = mock_win
        mock_win.get_wm_class.return_value = ("kitty", "Kitty")
        mock_title_prop = MagicMock()
        mock_title_prop.value = "main.py — neovim".encode("utf-8")
        mock_win.get_full_property.return_value = mock_title_prop

        result = get_active_window()

        assert result is not None
        assert result.app_class == "kitty"
        assert result.window_title == "main.py — neovim"
        mock_display_cls.assert_called_once()
        mock_d.close.assert_called_once()

    @patch("activity_tracker.x11.display.Display")
    def test_returns_none_on_display_failure(self, mock_display_cls) -> None:
        """Should return None if the X11 display cannot be opened."""
        mock_display_cls.side_effect = Exception("Cannot open display")
        result = get_active_window()
        assert result is None

    @patch("activity_tracker.x11.display.Display")
    def test_returns_none_on_no_active_window(self, mock_display_cls) -> None:
        """Should return None if _NET_ACTIVE_WINDOW has no value."""
        mock_d = MagicMock()
        mock_display_cls.return_value = mock_d
        mock_d.screen.return_value.root.get_full_property.return_value = None
        result = get_active_window()
        assert result is None

    @patch("activity_tracker.x11.display.Display")
    def test_cleans_up_connection_on_error(self, mock_display_cls) -> None:
        """Connection should always be closed, even on errors."""
        mock_d = MagicMock()
        mock_display_cls.return_value = mock_d
        mock_d.screen.return_value.root.get_full_property.side_effect = Exception("X11 error")
        result = get_active_window()
        assert result is None
        mock_d.close.assert_called_once()

    @patch("activity_tracker.x11.display.Display")
    def test_returns_none_when_atom_unavailable(self, mock_display_cls) -> None:
        """Should return None if _NET_ACTIVE_WINDOW atom is missing."""
        mock_d = MagicMock()
        mock_display_cls.return_value = mock_d
        mock_d.intern_atom.return_value = None
        result = get_active_window()
        assert result is None

    @patch("activity_tracker.x11.display.Display")
    def test_handles_none_wm_class(self, mock_display_cls) -> None:
        """Should handle windows with no WM_CLASS gracefully."""
        mock_d = MagicMock()
        mock_display_cls.return_value = mock_d

        mock_root = MagicMock()
        mock_d.screen.return_value.root = mock_root

        mock_prop = MagicMock()
        mock_prop.value = (12345,)
        mock_root.get_full_property.return_value = mock_prop

        mock_win = MagicMock()
        mock_d.create_resource_object.return_value = mock_win
        mock_win.get_wm_class.return_value = None

        result = get_active_window()

        assert result is not None
        assert result.app_class is None
