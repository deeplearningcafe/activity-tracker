"""X11 active window detection using python-xlib.

Queries the X11 display server for the currently focused window's class and
title via the EWMH (_NET_ACTIVE_WINDOW) protocol.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from Xlib import X, display

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WindowInfo:
    """Snapshot of the currently focused X11 window."""

    app_class: Optional[str]
    window_title: Optional[str]


def _get_atom(d: display.Display, name: str) -> Optional[int]:
    """Resolve an atom name to its numeric ID.

    Args:
        d: An open X11 display connection.
        name: The atom name (e.g. ``_NET_ACTIVE_WINDOW``).

    Returns:
        The atom ID integer, or ``None`` on failure.
    """
    try:
        return d.intern_atom(name)
    except Exception:
        return None


def _get_window_title(d: display.Display, win) -> Optional[str]:
    """Extract the window title from a window.

    Tries ``_NET_WM_NAME`` (UTF-8, EWMH standard) first, then falls back
    to ``WM_NAME`` (legacy ISO-8859-1).

    Args:
        d: An open X11 display connection.
        win: An ``Xlib.xobject.Window`` object.

    Returns:
        The window title string, or ``None`` on failure.
    """
    for atom_name in ("_NET_WM_NAME", "WM_NAME"):
        atom = _get_atom(d, atom_name)
        if atom is None:
            continue
        try:
            prop = win.get_full_property(atom, X.AnyPropertyType)
            if prop and prop.value:
                title = prop.value
                if isinstance(title, bytes):
                    title = title.decode("utf-8", errors="replace")
                return title.split("\x00")[0]
        except Exception:
            continue
    return None


def get_active_window() -> Optional[WindowInfo]:
    """Query the X11 server for the currently focused window.

    Uses the EWMH ``_NET_ACTIVE_WINDOW`` property on the root window to find
    the focused window, then reads its ``WM_CLASS`` and ``_NET_WM_NAME``.

    Returns:
        A :class:`WindowInfo` with the app class and title, or ``None`` if
        the active window cannot be determined (e.g. no focused window, X11
        error).
    """
    try:
        d = display.Display()
    except Exception as exc:
        logger.warning("Could not open X11 display: %s", exc)
        return None

    try:
        root = d.screen().root

        active_atom = _get_atom(d, "_NET_ACTIVE_WINDOW")
        if active_atom is None:
            logger.warning("_NET_ACTIVE_WINDOW atom not available")
            return None

        prop = root.get_full_property(active_atom, X.AnyPropertyType)
        if not prop or not prop.value:
            logger.debug("No active window reported by _NET_ACTIVE_WINDOW")
            return None

        active_win_id = prop.value[0]

        win = d.create_resource_object("window", active_win_id)
        app_class = win.get_wm_class()
        if app_class and len(app_class) >= 1:
            app_class = app_class[0]
        else:
            app_class = None

        window_title = _get_window_title(d, win)

        return WindowInfo(app_class=app_class, window_title=window_title)

    except Exception as exc:
        logger.warning(
            "Error querying active window: %s (%s)",
            type(exc).__name__,
            exc,
        )
        return None
    finally:
        d.close()
