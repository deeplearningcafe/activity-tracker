"""Database initialization and connection management for the activity tracker.

Handles SQLite database creation, WAL mode configuration, and schema setup.
All timestamps are stored in UTC.
"""

import sqlite3
from pathlib import Path
from typing import Optional

DB_NAME = "activity.db"

SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS activity_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       DATETIME NOT NULL,
    app_class       TEXT,
    window_title    TEXT,
    idle_ms         INTEGER NOT NULL DEFAULT 0,
    keystroke_count INTEGER NOT NULL DEFAULT 0,
    mouse_click_count INTEGER NOT NULL DEFAULT 0,
    mouse_distance  INTEGER NOT NULL DEFAULT 0
);
"""


def get_db_path() -> Path:
    """Return the path to the database file, relative to the project root."""
    return Path(__file__).resolve().parent.parent / DB_NAME


def init_db(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Initialize the database: create file, enable WAL mode, create schema.

    This function is idempotent — running it multiple times is safe and will
    not raise errors if the database file and tables already exist.

    Args:
        db_path: Optional explicit path to the database. Uses the default
                 location (``activity.db`` next to this module's parent) if
                 omitted.

    Returns:
        An open :class:`sqlite3.Connection` with WAL mode enabled.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open (or reuse) a connection to the database.

    For long-running processes the agent should call :func:`init_db` once at
    startup and reuse the returned connection.  This helper is provided for
    convenience in scripts and tests that only need a single connection.

    Args:
        db_path: Optional explicit path to the database.

    Returns:
        An open :class:`sqlite3.Connection` with WAL mode enabled.
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    # PRAGMA journal_mode is per-connection; ensure it is set even on
    # subsequent calls.
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def insert_activity(
    conn: sqlite3.Connection,
    app_class: Optional[str],
    window_title: Optional[str],
    timestamp: str,
    idle_ms: int = 0,
    keystroke_count: int = 0,
    mouse_click_count: int = 0,
    mouse_distance: int = 0,
) -> int:
    """Insert a single activity record into the database.

    Args:
        conn: An open SQLite connection (WAL mode should already be enabled).
        app_class: The X11 window class (e.g. ``google-chrome``, ``kitty``).
        window_title: The human-readable window title.
        timestamp: A UTC timestamp string in ISO-8601 format.
        idle_ms: User idle time in milliseconds.
        keystroke_count: Number of keystrokes in the interval.
        mouse_click_count: Number of mouse clicks in the interval.
        mouse_distance: Cumulative mouse movement in pixels.

    Returns:
        The row id of the newly inserted record.
    """
    cursor = conn.execute(
        """\
        INSERT INTO activity_log
            (timestamp, app_class, window_title, idle_ms,
             keystroke_count, mouse_click_count, mouse_distance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            timestamp,
            app_class,
            window_title,
            idle_ms,
            keystroke_count,
            mouse_click_count,
            mouse_distance,
        ),
    )
    conn.commit()
    return cursor.lastrowid
