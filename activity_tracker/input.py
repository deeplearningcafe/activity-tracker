"""User input event tracking via pynput.

Registers background listeners for keyboard and mouse events.
Counts keystrokes, mouse clicks, and cumulative mouse movement distance.
Privacy: raw key values and coordinate traces are never logged.
"""

import math
import threading
from typing import Callable, Optional

_lock = threading.Lock()
_keystroke_count = 0
_click_count = 0
_last_mouse_pos: Optional[tuple[float, float]] = None
_distance = 0.0


def _on_press(_key) -> None:
    """Increment keystroke counter on key press."""
    global _keystroke_count
    with _lock:
        _keystroke_count += 1


def _on_click(_x: int, _y: int, _button, _pressed: bool) -> bool:
    """Increment click counter on mouse button press."""
    global _click_count
    if _pressed:
        with _lock:
            _click_count += 1
    return True


def _on_move(x: int, y: int) -> None:
    """Accumulate Euclidean distance on mouse movement."""
    global _distance, _last_mouse_pos
    if _last_mouse_pos is not None:
        dx = x - _last_mouse_pos[0]
        dy = y - _last_mouse_pos[1]
        with _lock:
            _distance += math.sqrt(dx * dx + dy * dy)
    _last_mouse_pos = (float(x), float(y))


def start_listeners() -> tuple:
    """Start keyboard and mouse event listeners.

    Returns:
        A tuple of (keyboard.Listener, mouse.Listener) instances.
    """
    from pynput import keyboard, mouse

    kb_listener = keyboard.Listener(on_press=_on_press)
    kb_listener.start()

    mouse_listener = mouse.Listener(
        on_click=_on_click, on_move=_on_move
    )
    mouse_listener.start()

    return kb_listener, mouse_listener


def get_and_reset_counters() -> tuple[int, int, float]:
    """Retrieve and reset input counters atomically.

    Returns:
        A tuple of (keystroke_count, click_count, distance) for the
        current interval, then resets all counters to zero.
    """
    global _keystroke_count, _click_count, _distance, _last_mouse_pos
    with _lock:
        keystrokes = _keystroke_count
        clicks = _click_count
        distance = _distance
        _keystroke_count = 0
        _click_count = 0
        _distance = 0.0
        _last_mouse_pos = None
    return keystrokes, clicks, distance
