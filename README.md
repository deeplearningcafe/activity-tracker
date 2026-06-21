# Activity Tracker

Privacy-first, local-only time tracking for Linux (X11). Captures active
window details, idle time, keystrokes, and mouse activity into a local
SQLite database — no data ever leaves the machine.

## Quick Start

```bash
cd ~/projects/activity-tracker
uv sync
uv run python -m activity_tracker.agent
```

## Manual Verification

After running the agent, verify the database records window transitions
accurately using the SQL queries in:

[docs/MANUAL_VERIFICATION.md](docs/MANUAL_VERIFICATION.md)

## Project Structure

```
activity-tracker/
├── activity_tracker/
│   ├── __init__.py
│   ├── agent.py          # Polling loop & entry point
│   ├── db.py             # SQLite init, WAL mode, inserts
│   ├── idle.py           # System idle time (xprintidle)
│   ├── input.py          # Keystroke & mouse event listeners
│   └── x11.py            # X11 active window detection
├── scripts/
│   └── systemd-setup.sh  # Service management helper
├── tests/
│   ├── test_agent.py     # Polling loop & transition tests
│   ├── test_db.py        # Schema, WAL mode, idempotency
│   ├── test_idle.py      # Idle time reporting
│   ├── test_input.py     # Input counter tracking
│   └── test_x11.py       # Window class & title parsing
├── docs/
│   └── MANUAL_VERIFICATION.md
├── pyproject.toml
└── uv.lock
```

## Systemd User Service (Background Deployment)

Run the tracker unobtrusively as a background service that starts on login,
restarts on crash, and logs to journald — no `sudo` required.

### Quick Deploy

```bash
cd ~/projects/activity-tracker
./scripts/systemd-setup.sh install
```

### Service Commands

```bash
# View live logs
./scripts/systemd-setup.sh logs

# Stop the service
./scripts/systemd-setup.sh stop

# Disable auto-start (keep running until next reboot)
./scripts/systemd-setup.sh disable

# Remove the service entirely (clean teardown)
./scripts/systemd-setup.sh uninstall
```

### Direct systemctl Commands

```bash
# Start / stop / restart
systemctl --user start activity-agent
systemctl --user stop activity-agent
systemctl --user restart activity-agent

# Enable / disable auto-start on login
systemctl --user enable activity-agent
systemctl --user disable activity-agent

# Check status
systemctl --user status activity-agent

# View logs
journalctl --user -u activity-agent -f
```

### Unit File

The service unit is installed at:

```
~/.config/systemd/user/activity-agent.service
```

Key configuration:
- **Python**: Uses the `uv`-managed virtual environment (`./.venv/bin/python`)
- **Restart policy**: `on-failure` with 5-second backoff
- **Logging**: stdout and stderr routed to journald
- **Auto-start**: Enabled via `WantedBy=default.target`

## Testing

```bash
uv run pytest tests/ -v
```

## Author

[aipracticecafe](https://github.com/deeplearningcafe)
[aipracticecafe-codeberg](https://codeberg.org/aipracticecafe)

## License

This project is licensed under the MIT License. Details are available in the [LICENSE](LICENSE.txt) file.
