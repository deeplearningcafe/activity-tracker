
# Privacy-First Local Activity Tracker

> A lightweight, privacy-focused background agent for tracking your active
> windows, idle states, and peripheral input activity on Linux (X11).

This application runs entirely on your local machine. It collects window context
and input metrics, saving them directly to a local SQLite database. This
architecture ensures complete data ownership while collecting high-resolution
productivity metrics—perfect for developers wanting to analyze their coding habits
(such as active time inside LazyVim) without transmitting private data.

## ✨ Features

#### Core Metrics Collection
* **Active Window Detection**: Queries the X11 display server every 5 seconds to
  identify the focused window's application class and title.
* **Idle Time Tracking**: Uses `xprintidle` to monitor user inactivity in
  milliseconds, letting you isolate true working blocks from unattended time.
* **Input Activity Density**: Captures keyboard keystrokes, mouse clicks, and
  cumulative mouse cursor travel (in pixels) using low-overhead listeners.
* **Privacy by Design**: Counts are strictly aggregated every 5 seconds. Absolute
  keystrokes or spatial mouse coordinates are never monitored or saved.

#### Architecture & Storage
* **SQLite WAL (Write-Ahead Logging)**: Configures SQLite to operate in WAL mode
  to allow simultaneous writes from the agent and reads from any visualization
  dashboard without lockouts.
* **Timezone Agnostic**: Standardizes all stored metrics with UTC ISO-8601
  timestamps, ready to be rendered in your local timezone downstream.
* **Service Integration**: Features a zero-privilege systemd user service wrapper
  to run seamlessly in the background.

## 🚀 Technology Stack

* **Language**: Python 3.11+ managed using the modern `uv` package manager.
* **API communication**: `python-xlib` for native X11 protocol integration.
* **Input Monitoring**: `pynput` for non-elevated global hardware event listening.
* **Inactivity Monitor**: `xprintidle` executed cleanly via managed subprocesses.
* **Database**: Local SQLite 3 instance configured with concurrent WAL journals.

## 📁 Project Structure

```
activity-tracker/
├── activity_tracker/
│   ├── __init__.py
│   ├── agent.py          # Core polling loop & thread coordination
│   ├── db.py             # SQLite WAL configuration & inserts
│   ├── idle.py           # Inactivity polling wrapper
│   ├── input.py          # Atomic keystroke/mouse tracking
│   └── x11.py            # Focused window title/class extraction
├── scripts/
│   └── systemd-setup.sh  # Automated systemd user service manager
├── tests/
│   ├── test_agent.py     # Resilient loop and concurrency tests
│   ├── test_db.py        # Database integration tests
│   ├── test_idle.py      # Subprocess handling tests
│   ├── test_input.py     # Thread-safe listener tests
│   └── test_x11.py       # Window query pipeline tests
├── pyproject.toml        # Dependency declarations
└── uv.lock               # Deterministic dependency lock
```

## ⚙️ Getting Started

### Prerequisites

* Linux environment running **X11** (not Wayland).
* `xprintidle` installed:
  ```bash
  sudo apt install xprintidle
  ```
* Python 3.11+ and the `uv` package manager.

### Installation & Execution

1. Sync dependencies and set up the virtual environment:
   ```bash
   uv sync
   ```
2. Launch the agent manually in the foreground to verify functionality:
   ```bash
   uv run python -m activity_tracker.agent
   ```

### Running Tests

Execute the unit tests using `pytest` to verify loop logic and mock-up states:
```bash
uv run pytest tests/ -v
```

## ⚙️ Systemd User Service Integration

Run the tracker in the background. It will start automatically upon login
and restart automatically on failures—all without root or `sudo` privileges.

### Manage Service Life Cycle
```bash
# Install and start the service
./scripts/systemd-setup.sh install

# Monitor live agent logs via journald
./scripts/systemd-setup.sh logs

# Stop the running service
./scripts/systemd-setup.sh stop

# Remove all service traces and configurations
./scripts/systemd-setup.sh uninstall
```

---

## 📊 Database Verification

Use Python's built-in `sqlite3` shell to inspect the local database state
and verify collected metrics.

```bash
# Open Python in the project root
uv run python
```

Once inside the interactive interpreter, paste the code blocks below:

### 1. Basic Connection & WAL Mode Verification
Ensure the database schema initialized correctly and WAL journaling is enabled:
```python
import sqlite3

conn = sqlite3.connect("activity.db")
cur = conn.cursor()

# Verify Journal Mode is WAL
mode = cur.execute("PRAGMA journal_mode;").fetchone()[0]
print(f"Journal Mode: {mode}")  # Expected: wal
```

### 2. View Chronological Activity Records
Examine the recorded active application transitions:
```python
query = """
SELECT id, timestamp, app_class, window_title
FROM activity_log
ORDER BY id ASC
LIMIT 5;
"""
for row in cur.execute(query).fetchall():
    print(row)
```

### 3. Check Metric Counter Accuracy
Inspect physical inputs, mouse distances, and idle records:
```python
query = """
SELECT id, idle_ms, keystroke_count, mouse_click_count, mouse_distance
FROM activity_log
ORDER BY id DESC
LIMIT 5;
"""
for row in cur.execute(query).fetchall():
    print(
        f"ID: {row[0]} | "
        f"Idle: {row[1]}ms | "
        f"Keys: {row[2]} | "
        f"Clicks: {row[3]} | "
        f"Dist: {row[4]:.1f}px"
    )
```

### 4. Fetch Transition Events
Review your application context changes over time:
```python
query = """
SELECT
    id,
    timestamp,
    app_class,
    LAG(app_class) OVER (ORDER BY id) AS previous_app
FROM activity_log
LIMIT 10;
"""
for r in cur.execute(query).fetchall():
    if r[2] != r[3] or r[3] is None:
        print(f"[{r[1]}] Switched to: {r[2]}")
```

```python
# Clean up connection
conn.close()
```

---

## 🛠️ Troubleshooting

| Symptom | Cause & Solution |
| :--- | :--- |
| `app_class` is always `None` | X11 displays cannot be resolved. Ensure `DISPLAY` is exported. |
| Subprocess crashes on headless SSH | Active X Server session is missing; run via `Xvfb` if testing. |
| DB locks on concurrent reads | Database is running in fallback mode. Run `PRAGMA journal_mode=WAL;` |



## Author

[aipracticecafe](https://github.com/deeplearningcafe)
[aipracticecafe-codeberg](https://codeberg.org/aipracticecafe)

## License

This project is licensed under the MIT License. Details are available in the [LICENSE](LICENSE.txt) file.
