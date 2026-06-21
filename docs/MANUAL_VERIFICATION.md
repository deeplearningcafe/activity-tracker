# Manual Verification Guide

> Run the live tracking loop on a Pop!_OS (X11) system and verify
> the database records window transitions accurately.

## Prerequisites

- Pop!_OS or any Linux distribution running **X11** (not Wayland)
- `xprintidle` installed (`sudo apt install xprintidle`)
- The agent is installed in the project's virtual environment

```bash
cd ~/projects/activity-tracker
source .venv/bin/activate
```

## Running the Agent

Start the tracking daemon. It writes to `activity.db` in the project root:

```bash
python -m activity_tracker.agent
```

The agent prints a log line every 5 seconds:

```
2026-06-17 14:30:05 [INFO] Logged activity #1: class=kitty title=main.py
2026-06-17 14:30:10 [INFO] Logged activity #2: class=google-chrome title=Reddit
```

Press **Ctrl+C** to stop the agent cleanly.

## Manual Action Sequence

1. **Start the agent** (above).
2. **Switch to your terminal** (e.g. `kitty`) and wait ~10 seconds.
   You should see 2–3 entries with `app_class=kitty`.
3. **Switch to your browser** (e.g. `google-chrome`) and wait ~10 seconds.
   You should see entries with `app_class=google-chrome`.
4. **Switch back to the terminal** and wait ~10 seconds.
5. **Stop the agent** with Ctrl+C.

## Querying the Database

Open the SQLite database with the CLI:

```bash
cd ~/projects/activity-tracker
python
import sqlite3
conn = sqlite3.connect('activity.db')
cur = conn.cursor()
print(cur.execute('select * from activity_log').fetchall())
```

### 1. View all records in chronological order

```sql
SELECT id, timestamp, app_class, window_title
FROM activity_log
ORDER BY id ASC;
```

**Expected output:** Rows ordered by `id`, with `app_class` alternating
between your terminal and browser as you switched windows.

### 2. Filter by a specific window class

```sql
SELECT id, timestamp, window_title
FROM activity_log
WHERE app_class = 'google-chrome'
ORDER BY id ASC;
```

**Expected output:** Only the rows recorded while Chrome was the active
window.

### 3. Count records per application

```sql
SELECT app_class, COUNT(*) AS record_count
FROM activity_log
GROUP BY app_class
ORDER BY record_count DESC;
```

**Expected output:** A tally showing how many 5-second samples were
captured for each application.

### 4. Detect window transitions

```sql
SELECT
    id,
    timestamp,
    app_class,
    window_title,
    LAG(app_class) OVER (ORDER BY id) AS prev_app_class
FROM activity_log
WHERE app_class != LAG(app_class) OVER (ORDER BY id)
   OR LAG(app_class) OVER (ORDER BY id) IS NULL;
```

**Expected output:** Only the rows where the `app_class` changed from
the previous tick — i.e., the exact moments you switched windows.

### 5. Verify UTC timestamps

```sql
SELECT id, timestamp
FROM activity_log
ORDER BY id DESC
LIMIT 5;
```

**Expected output:** Timestamps ending in `+00:00` or `Z`, indicating
UTC. Example: `2026-06-17T14:32:10.123456+00:00`.

### 6. Check WAL mode is active

```sql
PRAGMA journal_mode;
```

**Expected output:** `wal`

### 7. Verify idle/input metrics are zero (Phase 1)

```sql
SELECT id, idle_ms, keystroke_count, mouse_click_count, mouse_distance
FROM activity_log
ORDER BY id DESC
LIMIT 5;
```

**Expected output:** All four metric columns are `0` — these counters
are populated by Tickets 4–7, not this phase.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No rows appear in the DB | Agent crashed; check with `journalctl --user -u activity-agent -n 50` |
| `app_class` is always `None` | X11 display not available; ensure `DISPLAY` is set |
| `PRAGMA journal_mode` returns `truncate` | WAL not enabled; re-run `init_db` or execute `PRAGMA journal_mode=WAL;` manually |
| Agent won't start on headless SSH | X11 is required; set up a virtual X display (`Xvfb`) for remote testing |
