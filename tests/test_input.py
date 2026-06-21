"""Tests for the user input event tracking module.

Pynput is imported lazily (only when start_listeners is called),
so we can test the counter logic without an X11 display.
"""

from unittest.mock import MagicMock, patch

import pytest

from activity_tracker.input import (
    _click_count,
    _distance,
    _keystroke_count,
    _last_mouse_pos,
    _on_click,
    _on_move,
    _on_press,
    get_and_reset_counters,
)


@pytest.fixture(autouse=True)
def reset_counters() -> None:
    """Reset module-level counters before each test."""
    import activity_tracker.input as input_module

    input_module._keystroke_count = _keystroke_count
    input_module._click_count = _click_count
    input_module._distance = _distance
    input_module._last_mouse_pos = _last_mouse_pos
    yield


class TestInputCounters:
    """Verify input counter aggregation and reset behavior."""

    def test_keystroke_counter_increments(self) -> None:
        """Each key press should increment the counter."""
        _on_press("a")
        _on_press("b")
        _on_press("c")
        keystrokes, clicks, distance = get_and_reset_counters()
        assert keystrokes == 3
        assert clicks == 0
        assert distance == 0.0

    def test_click_counter_increments_on_press(self) -> None:
        """Mouse button press should increment the click counter."""
        _on_click(100, 100, MagicMock(), True)
        _on_click(100, 100, MagicMock(), True)
        keystrokes, clicks, distance = get_and_reset_counters()
        assert keystrokes == 0
        assert clicks == 2
        assert distance == 0.0

    def test_click_counter_does_not_increment_on_release(self) -> None:
        """Mouse button release should not increment the click counter."""
        _on_click(100, 100, MagicMock(), True)
        _on_click(100, 100, MagicMock(), False)
        keystrokes, clicks, distance = get_and_reset_counters()
        assert clicks == 1

    def test_mouse_distance_accumulates(self) -> None:
        """Mouse movement should accumulate Euclidean distance."""
        _on_move(0, 0)
        _on_move(3, 4)  # distance = 5
        _on_move(6, 4)  # distance = 3
        keystrokes, clicks, distance = get_and_reset_counters()
        assert round(distance, 6) == 8.0

    def test_mouse_distance_starts_after_first_position(self) -> None:
        """No distance should be recorded for the first movement."""
        _on_move(100, 100)
        _on_move(105, 105)  # First actual movement
        keystrokes, clicks, distance = get_and_reset_counters()
        assert round(distance, 6) == pytest.approx(7.071068)

    def test_counters_reset_after_read(self) -> None:
        """Counter values should be zeroed after get_and_reset_counters()."""
        _on_press("x")
        _on_click(0, 0, MagicMock(), True)
        _on_move(0, 0)
        _on_move(10, 0)

        get_and_reset_counters()

        # After reset, counters should be zero
        keystrokes, clicks, distance = get_and_reset_counters()
        assert keystrokes == 0
        assert clicks == 0
        assert distance == 0.0

    def test_thread_safety(self) -> None:
        """Multiple threads should be able to update counters safely."""
        import threading

        def press_keys(n: int) -> None:
            for _ in range(n):
                _on_press("a")

        def click_mouse(n: int) -> None:
            for _ in range(n):
                _on_click(0, 0, MagicMock(), True)

        threads = [
            threading.Thread(target=press_keys, args=(100,)),
            threading.Thread(target=click_mouse, args=(50,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        keystrokes, clicks, _ = get_and_reset_counters()
        assert keystrokes == 100
        assert clicks == 50

    def test_get_and_reset_is_atomic(self) -> None:
        """Read and reset should happen atomically."""
        _on_press("a")
        _on_press("b")
        _on_press("c")

        # First read should get all 3
        k1, _, _ = get_and_reset_counters()
        assert k1 == 3

        # Second read should get 0
        k2, _, _ = get_and_reset_counters()
        assert k2 == 0


class TestStartListeners:
    """Verify listener startup with mocked pynput."""

    def test_returns_listener_tuple(self) -> None:
        """start_listeners should return a tuple of two listeners."""
        import sys

        # Prevent pynput from being imported by replacing it in sys.modules
        mock_kb = MagicMock()
        mock_mouse = MagicMock()
        kb_inst = MagicMock()
        mouse_inst = MagicMock()
        mock_kb.Listener = MagicMock(return_value=kb_inst)
        mock_mouse.Listener = MagicMock(return_value=mouse_inst)

        mock_pynput = MagicMock()
        mock_pynput.keyboard = mock_kb
        mock_pynput.mouse = mock_mouse

        sys.modules["pynput"] = mock_pynput
        sys.modules["pynput.keyboard"] = mock_kb
        sys.modules["pynput.mouse"] = mock_mouse

        try:
            from activity_tracker.input import start_listeners

            kb, mouse = start_listeners()

            assert kb is kb_inst
            assert mouse is mouse_inst
            mock_kb.Listener.assert_called_once_with(
                on_press=_on_press
            )
            mock_mouse.Listener.assert_called_once_with(
                on_click=_on_click, on_move=_on_move
            )
            kb_inst.start.assert_called_once()
            mouse_inst.start.assert_called_once()
        finally:
            # Restore original modules
            for key in ("pynput", "pynput.keyboard", "pynput.mouse"):
                sys.modules.pop(key, None)
