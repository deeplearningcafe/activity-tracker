"""Main entry point for the activity tracker agent.

Usage::

    python -m activity_tracker.agent
    # or, after installation:
    activity-agent
"""

import logging
import signal
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from activity_tracker.db import init_db, insert_activity
from activity_tracker.idle import get_idle_ms
from activity_tracker.input import get_and_reset_counters, start_listeners
from activity_tracker.x11 import get_active_window

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


def _handle_signal(
    signum: int, _frame: object, shutdown_event: threading.Event
) -> None:
    """Graceful shutdown handler for SIGTERM/SIGINT."""
    logger.info("Received signal %d — shutting down…", signum)
    shutdown_event.set()


def _poll_loop(
    conn,
    shutdown_event: threading.Event,
    tick_count: Optional[int] = None,
    sleep_func: Optional[Callable[[float], None]] = None,
) -> None:
    """Core polling loop: query X11 and write to the database every 5 seconds.

    Args:
        conn: An open SQLite connection to write activity records into.
        shutdown_event: A :class:`threading.Event` that, when set, causes the
            loop to exit gracefully after the current tick.
        tick_count: If set, exit after this many iterations (for testing).
        sleep_func: Callable used to wait between ticks; defaults to
            :func:`time.sleep`.  Override for testing to avoid real waits.
    """
    if sleep_func is None:
        sleep_func = time.sleep

    count = 0
    while True:
        try:
            # Query X11 for the active window
            win_info = get_active_window()
            if win_info is None:
                logger.warning("Could not determine active window (X11)")
                app_class = None
                window_title = None
            else:
                app_class = win_info.app_class
                window_title = win_info.window_title
                logger.debug(
                    "Active window: class=%s title=%s",
                    app_class,
                    window_title,
                )

            # UTC timestamp
            now_utc = datetime.now(timezone.utc).isoformat()

            # Query system idle time
            idle_ms = get_idle_ms()

            # Get and reset input counters
            keystrokes, clicks, distance = get_and_reset_counters()

            # Insert into DB
            row_id = insert_activity(
                conn,
                app_class=app_class,
                window_title=window_title,
                timestamp=now_utc,
                idle_ms=idle_ms,
                keystroke_count=keystrokes,
                mouse_click_count=clicks,
                mouse_distance=distance,
            )
            logger.info(
                "Logged activity #%d: class=%s title=%s",
                row_id,
                app_class,
                window_title,
            )

        except Exception as exc:
            logger.error("Error in polling loop: %s", exc, exc_info=True)

        count += 1

        # Exit if we've reached the requested tick count (testing only)
        if tick_count is not None and count >= tick_count:
            break

        # Wait for the next tick (interruptible via shutdown_event)
        shutdown_event.wait(timeout=POLL_INTERVAL)
        if shutdown_event.is_set():
            break


def main() -> None:
    """Initialize the database, wire up signals, and start the tracking loop."""
    shutdown_event = threading.Event()

    db_path = Path(__file__).resolve().parent.parent / "activity.db"
    logger.info("Initializing database at %s …", db_path)
    conn = init_db(db_path)
    logger.info("Database initialized successfully (WAL mode).")

    # Start input listeners
    kb_listener, mouse_listener = start_listeners()
    logger.info("Input listeners started.")

    # Register graceful shutdown on SIGTERM / SIGINT
    signal.signal(signal.SIGTERM, lambda s, f: _handle_signal(s, f, shutdown_event))
    signal.signal(signal.SIGINT, lambda s, f: _handle_signal(s, f, shutdown_event))

    logger.info("Starting 5-second polling loop (Ctrl+C to stop)…")
    try:
        _poll_loop(conn, shutdown_event)
    finally:
        logger.info("Polling loop ended. Closing database connection.")
        conn.close()
        kb_listener.stop()
        mouse_listener.stop()


if __name__ == "__main__":
    main()
