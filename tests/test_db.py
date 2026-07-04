"""Tests for database initialization and schema setup."""

import sqlite3
from pathlib import Path

import pytest

from activity_tracker.db import (
    SCHEMA_SQL,
    DB_NAME,
    get_db_path,
    get_connection,
    init_db,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Path:
    """Return a temporary path for a fresh database file."""
    return tmp_path / DB_NAME


class TestDatabaseInit:
    """Verify database creation, schema, and WAL mode."""

    def test_creates_database_file(self, temp_db: Path) -> None:
        """The database file should be created on first init."""
        assert not temp_db.exists()
        conn = init_db(temp_db)
        conn.close()
        assert temp_db.exists()

    def test_wal_mode_enabled(self, temp_db: Path) -> None:
        """journal_mode should be WAL after initialization."""
        conn = init_db(temp_db)
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_activity_log_table_exists(self, temp_db: Path) -> None:
        """The activity_log table should exist after init."""
        conn = init_db(temp_db)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='activity_log';"
        ).fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "activity_log"

    def test_schema_columns(self, temp_db: Path) -> None:
        """All required columns should be present in the activity_log table."""
        conn = init_db(temp_db)
        rows = conn.execute("PRAGMA table_info(activity_log);").fetchall()
        conn.close()

        columns = {row[1] for row in rows}
        expected = {
            "id",
            "timestamp",
            "app_class",
            "window_title",
            "idle_ms",
            "keystroke_count",
            "mouse_click_count",
            "mouse_distance",
        }
        assert columns == expected

    def test_column_types_and_constraints(self, temp_db: Path) -> None:
        """Verify column types and NOT NULL constraints."""
        conn = init_db(temp_db)
        rows = conn.execute("PRAGMA table_info(activity_log);").fetchall()
        conn.close()

        col_map = {row[1]: row for row in rows}

        # id is the primary key
        assert col_map["id"][5] == 1  # pk column

        # timestamp is NOT NULL
        assert col_map["timestamp"][3] == 1

        # counters default to 0 and are NOT NULL
        for col_name in (
            "idle_ms",
            "keystroke_count",
            "mouse_click_count",
            "mouse_distance",
        ):
            assert col_map[col_name][3] == 1  # notnull
            assert int(col_map[col_name][4]) == 0  # dflt_value

    def test_idempotent_init(self, temp_db: Path) -> None:
        """Running init_db multiple times must not raise."""
        conn1 = init_db(temp_db)
        conn1.close()
        conn2 = init_db(temp_db)  # should succeed without error
        conn2.close()

        # Schema should still be correct
        conn3 = init_db(temp_db)
        tables = conn3.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        conn3.close()
        table_names = {t[0] for t in tables}
        assert "activity_log" in table_names
        # Should only have one activity_log table, not duplicates
        assert table_names == {"activity_log"} or "activity_log" in table_names


class TestGetConnection:
    """Verify get_connection helper works on existing databases."""

    def test_returns_wal_connection(self, temp_db: Path) -> None:
        """get_connection should return a connection with WAL mode."""
        # First initialize the DB
        init_db(temp_db)
        # Now open via get_connection
        conn = get_connection(temp_db)
        mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        conn.close()
        assert mode == "wal"

    def test_no_duplicate_table(self, temp_db: Path) -> None:
        """Calling get_connection multiple times should not duplicate tables."""
        init_db(temp_db)
        get_connection(temp_db)
        get_connection(temp_db)
        conn = get_connection(temp_db)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()
        conn.close()
        assert len([t for t in tables if t[0] == "activity_log"]) == 1


class TestDefaultDBPath:
    """Verify the default database path resolution."""

    def test_default_path_is_activity_db(self) -> None:
        """get_db_path should resolve to activity.db in the project root."""
        path = get_db_path()
        assert path.name == DB_NAME
        assert path.is_absolute()
