"""Tests for the agent polling loop.

X11 and database interactions are mocked so tests run on any platform
(including headless CI).
"""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from activity_tracker.db import init_db
from activity_tracker.x11 import WindowInfo


@pytest.fixture
def agent_db(tmp_path: Path) -> sqlite3.Connection:
    """A fresh test database."""
    return init_db(tmp_path / "test_activity.db")


@pytest.fixture
def shutdown_event() -> Generator[threading.Event, None, None]:
    """A fresh shutdown event for each test. Sets the event on teardown to prevent thread leaks."""
    event = threading.Event()
    yield event
    # Teardown: ensure any background threads are signaled to stop when the test finishes
    event.set()


@pytest.fixture(autouse=True)
def mock_external_deps() -> Generator[None, None, None]:
    """Mock external dependencies to prevent rogue threads and delays.

    This ensures that get_idle_ms doesn't block for 5 seconds waiting for xprintidle,
    and provides stable default metrics (0) for tests that don't explicitly mock them.
    """
    with (
        patch("activity_tracker.agent.get_idle_ms", return_value=0),
        patch(
            "activity_tracker.agent.get_and_reset_counters", return_value=(0, 0, 0.0)
        ),
    ):
        yield


class TestPollLoop:
    """Verify that the polling loop queries X11 and writes to DB."""

    @patch("activity_tracker.agent.get_active_window")
    def test_writes_record_per_tick(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Each tick should produce exactly one row in the database."""
        mock_get_window.return_value = WindowInfo(
            app_class="google-chrome", window_title="Reddit"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1  # speed up for tests

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2)

        rows = agent_db.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        assert rows >= 1
        shutdown_event.set()  # stop background thread

    @patch("activity_tracker.agent.get_active_window")
    def test_stores_utc_timestamp(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Timestamps should be valid UTC datetimes."""
        mock_get_window.return_value = WindowInfo(
            app_class="kitty", window_title="test.py"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1  # speed up for tests

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2)

        from datetime import datetime

        row = agent_db.execute(
            "SELECT timestamp FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        ts = datetime.fromisoformat(row[0])
        assert ts.tzinfo is not None
        shutdown_event.set()  # stop background thread

    @patch("activity_tracker.agent.get_active_window", return_value=None)
    def test_handles_missing_window(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Should still insert a row when X11 returns None."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1  # speed up for tests

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2)

        row = agent_db.execute(
            "SELECT app_class, window_title FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] is None
        assert row[1] is None
        shutdown_event.set()  # stop background thread

    @patch("activity_tracker.agent.get_active_window")
    def test_stores_window_class_and_title(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Window class and title should be stored correctly."""
        mock_get_window.return_value = WindowInfo(
            app_class="firefox", window_title="GitHub – pull requests"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1  # speed up for tests

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2)

        row = agent_db.execute(
            "SELECT app_class, window_title FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == "firefox"
        assert row[1] == "GitHub – pull requests"
        shutdown_event.set()  # stop background thread

    @patch("activity_tracker.agent.get_active_window")
    def test_default_metrics_are_zero(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Idle and input metrics should default to 0 in this phase."""
        mock_get_window.return_value = WindowInfo(
            app_class="kitty", window_title="main.py"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1  # speed up for tests

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=2)

        row = agent_db.execute(
            "SELECT idle_ms, keystroke_count, mouse_click_count, mouse_distance "
            "FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert row[1] == 0
        assert row[2] == 0
        assert row[3] == 0
        shutdown_event.set()  # stop background thread

    @patch("activity_tracker.agent.get_active_window")
    def test_shutdown_event_stops_loop(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Setting the shutdown event should cause the loop to exit."""
        mock_get_window.return_value = WindowInfo(
            app_class="kitty", window_title="main.py"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 5  # long interval — we want to interrupt it

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()

        # Wait for first record, then signal shutdown
        thread.join(timeout=2)
        shutdown_event.set()
        thread.join(timeout=2)

        # Thread should have exited
        assert not thread.is_alive()

    @patch("activity_tracker.agent.get_active_window")
    def test_loop_continues_after_first_tick(
        self,
        mock_get_window: MagicMock,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Multiple ticks should produce multiple records."""
        mock_get_window.return_value = WindowInfo(
            app_class="kitty", window_title="main.py"
        )

        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.2  # short enough to get 2+ ticks

        thread = threading.Thread(
            target=agent_module._poll_loop,
            args=(agent_db, shutdown_event),
        )
        thread.start()
        thread.join(timeout=3)

        count = agent_db.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        assert count >= 2
        shutdown_event.set()  # stop background thread


class TestWindowTransitions:
    """Verify that window changes between ticks are detected and recorded."""

    def _run_with_windows(
        self,
        db: sqlite3.Connection,
        event: threading.Event,
        window_sequence: list[WindowInfo],
        tick_count: int = 5,
    ) -> list[WindowInfo]:
        """Run the polling loop with a sequence of window results.

        Each tick, pop the next WindowInfo from the sequence.
        Returns the list of WindowInfos that were actually returned.
        """
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1
        sequence_index = [0]
        returned = []

        def side_effect():
            if sequence_index[0] < len(window_sequence):
                result = window_sequence[sequence_index[0]]
                sequence_index[0] += 1
                returned.append(result)
                return result
            return None

        with patch("activity_tracker.agent.get_active_window", side_effect=side_effect):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(db, event),
                kwargs={"tick_count": tick_count},
            )
            thread.start()
            thread.join(timeout=5)

        return returned

    @pytest.fixture
    def agent_db(self, tmp_path: Path) -> sqlite3.Connection:
        return init_db(tmp_path / "test_transitions.db")

    @pytest.fixture
    def shutdown_event(self) -> threading.Event:
        return threading.Event()

    def test_window_change_detected(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Switching from terminal to browser should produce two different rows."""
        windows = [
            WindowInfo(app_class="kitty", window_title="main.py"),
            WindowInfo(app_class="google-chrome", window_title="Reddit"),
        ]
        self._run_with_windows(agent_db, shutdown_event, windows, tick_count=2)

        rows = agent_db.execute(
            "SELECT app_class, window_title FROM activity_log ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][0] == "kitty"
        assert rows[0][1] == "main.py"
        assert rows[1][0] == "google-chrome"
        assert rows[1][1] == "Reddit"

    def test_same_window_stays_constant(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Staying on the same window should produce identical app_class rows."""
        windows = [
            WindowInfo(app_class="kitty", window_title="main.py"),
            WindowInfo(app_class="kitty", window_title="main.py"),
            WindowInfo(app_class="kitty", window_title="main.py"),
        ]
        self._run_with_windows(agent_db, shutdown_event, windows, tick_count=3)

        rows = agent_db.execute(
            "SELECT app_class FROM activity_log ORDER BY id"
        ).fetchall()
        assert all(r[0] == "kitty" for r in rows)

    def test_rapid_window_switches(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Rapid switching between three apps should be fully recorded."""
        windows = [
            WindowInfo(app_class="kitty", window_title="a.py"),
            WindowInfo(app_class="google-chrome", window_title="Stack Overflow"),
            WindowInfo(app_class="code", window_title="src/index.ts"),
            WindowInfo(app_class="kitty", window_title="b.py"),
        ]
        self._run_with_windows(agent_db, shutdown_event, windows, tick_count=4)

        rows = agent_db.execute(
            "SELECT app_class, window_title FROM activity_log ORDER BY id"
        ).fetchall()
        assert len(rows) == 4
        for (ac, wt), expected in zip(rows, windows):
            assert ac == expected.app_class
            assert wt == expected.window_title

    def test_chronological_ordering(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Records should be stored in strictly increasing chronological order."""
        windows = [
            WindowInfo(app_class="kitty", window_title="file1.py"),
            WindowInfo(app_class="kitty", window_title="file2.py"),
            WindowInfo(app_class="kitty", window_title="file3.py"),
        ]
        self._run_with_windows(agent_db, shutdown_event, windows, tick_count=3)

        rows = agent_db.execute(
            "SELECT id, timestamp FROM activity_log ORDER BY id"
        ).fetchall()
        timestamps = [r[1] for r in rows]
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1], (
                f"Timestamp {i} ({timestamps[i]}) is not after {i - 1} "
                f"({timestamps[i - 1]})"
            )


class TestConcurrentAccess:
    """Verify WAL mode allows concurrent reads without blocking writes."""

    @pytest.fixture
    def agent_db(self, tmp_path: Path) -> sqlite3.Connection:
        return init_db(tmp_path / "test_concurrent.db")

    @pytest.fixture
    def shutdown_event(self) -> threading.Event:
        return threading.Event()

    def test_read_does_not_block_write(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """A reader thread should be able to query the DB while the agent writes."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1
        read_errors = []

        def reader():
            try:
                for _ in range(10):
                    agent_db.execute("SELECT COUNT(*) FROM activity_log").fetchone()
                    time.sleep(0.05)
            except Exception as exc:
                read_errors.append(exc)

        with patch(
            "activity_tracker.agent.get_active_window",
            return_value=WindowInfo(app_class="kitty", window_title="test.py"),
        ):
            writer_thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 5},
            )
            reader_thread = threading.Thread(target=reader)
            writer_thread.start()
            reader_thread.start()
            writer_thread.join(timeout=5)
            reader_thread.join(timeout=5)

        assert not read_errors, f"Reader encountered errors: {read_errors}"

        # Verify writer produced records
        count = agent_db.execute("SELECT COUNT(*) FROM activity_log").fetchone()[0]
        assert count >= 1

    def test_wal_mode_enabled(
        self,
        agent_db: sqlite3.Connection,
    ) -> None:
        """Database should be in WAL mode to support concurrent access."""
        mode = agent_db.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode == "wal"


class TestIdleIntegration:
    """Verify idle time tracking is integrated into the polling loop."""

    @pytest.fixture
    def agent_db(self, tmp_path: Path) -> sqlite3.Connection:
        return init_db(tmp_path / "test_idle.db")

    @pytest.fixture
    def shutdown_event(self) -> threading.Event:
        return threading.Event()

    def test_idle_ms_written_to_db(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Idle time from xprintidle should be stored in idle_ms column."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=42000),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 2},
            )
            thread.start()
            thread.join(timeout=3)

        rows = agent_db.execute(
            "SELECT idle_ms FROM activity_log ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        assert all(r[0] == 42000 for r in rows)

    def test_idle_ms_varies_per_tick(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Idle time should increase as time passes between ticks."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1
        idle_values = [1000, 2000, 3000]
        index = [0]

        def side_effect():
            val = idle_values[index[0]]
            index[0] = min(index[0] + 1, len(idle_values) - 1)
            return val

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", side_effect=side_effect),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 3},
            )
            thread.start()
            thread.join(timeout=3)

        rows = agent_db.execute(
            "SELECT idle_ms FROM activity_log ORDER BY id"
        ).fetchall()
        assert len(rows) == 3
        assert rows[0][0] == 1000
        assert rows[1][0] == 2000
        assert rows[2][0] == 3000

    def test_idle_fallback_on_subprocess_failure(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Should fall back to idle_ms=0 when xprintidle fails."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=0),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 2},
            )
            thread.start()
            thread.join(timeout=3)

        rows = agent_db.execute(
            "SELECT idle_ms FROM activity_log ORDER BY id"
        ).fetchall()
        assert len(rows) == 2
        assert all(r[0] == 0 for r in rows)


class TestInputMetrics:
    """Verify input metrics are captured and stored correctly."""

    @pytest.fixture
    def agent_db(self, tmp_path: Path) -> sqlite3.Connection:
        return init_db(tmp_path / "test_input_metrics.db")

    @pytest.fixture
    def shutdown_event(self) -> threading.Event:
        return threading.Event()

    def test_keystrokes_stored_in_db(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Keystroke count should be stored in keystroke_count column."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=0),
            patch(
                "activity_tracker.agent.get_and_reset_counters",
                return_value=(5, 0, 0.0),
            ),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 1},
            )
            thread.start()
            thread.join(timeout=3)

        row = agent_db.execute(
            "SELECT keystroke_count, mouse_click_count, mouse_distance "
            "FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 5
        assert row[1] == 0
        assert row[2] == 0.0

    def test_mouse_clicks_stored_in_db(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Mouse click count should be stored in mouse_click_count column."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=0),
            patch(
                "activity_tracker.agent.get_and_reset_counters",
                return_value=(0, 3, 0.0),
            ),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 1},
            )
            thread.start()
            thread.join(timeout=3)

        row = agent_db.execute(
            "SELECT keystroke_count, mouse_click_count, mouse_distance "
            "FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert row[1] == 3
        assert row[2] == 0.0

    def test_mouse_distance_stored_in_db(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """Mouse distance should be stored in mouse_distance column."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=0),
            patch(
                "activity_tracker.agent.get_and_reset_counters",
                return_value=(0, 0, 150.5),
            ),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 1},
            )
            thread.start()
            thread.join(timeout=3)

        row = agent_db.execute(
            "SELECT keystroke_count, mouse_click_count, mouse_distance "
            "FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 0
        assert row[1] == 0
        assert row[2] == 150.5

    def test_all_metrics_stored_together(
        self,
        agent_db: sqlite3.Connection,
        shutdown_event: threading.Event,
    ) -> None:
        """All metrics should be stored together in a single row."""
        import activity_tracker.agent as agent_module

        agent_module.POLL_INTERVAL = 0.1

        with (
            patch(
                "activity_tracker.agent.get_active_window",
                return_value=WindowInfo(app_class="kitty", window_title="test.py"),
            ),
            patch("activity_tracker.agent.get_idle_ms", return_value=42000),
            patch(
                "activity_tracker.agent.get_and_reset_counters",
                return_value=(10, 5, 200.0),
            ),
        ):
            thread = threading.Thread(
                target=agent_module._poll_loop,
                args=(agent_db, shutdown_event),
                kwargs={"tick_count": 1},
            )
            thread.start()
            thread.join(timeout=3)

        row = agent_db.execute(
            "SELECT idle_ms, keystroke_count, mouse_click_count, mouse_distance "
            "FROM activity_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        assert row[0] == 42000
        assert row[1] == 10
        assert row[2] == 5
        assert row[3] == 200.0
