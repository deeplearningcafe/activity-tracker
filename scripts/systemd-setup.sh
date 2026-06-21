#!/usr/bin/env bash
# systemd-setup.sh — Manage the activity-agent systemd user service.
#
# Usage:
#   ./scripts/systemd-setup.sh install    # Enable and start the service
#   ./scripts/systemd-setup.sh start      # Start the service (already installed)
#   ./scripts/systemd-setup.sh stop       # Stop the service
#   ./scripts/systemd-setup.sh enable     # Enable auto-start on login
#   ./scripts/systemd-setup.sh disable    # Disable auto-start (keep running)
#   ./scripts/systemd-setup.sh uninstall  # Stop, disable, and remove the service
#   ./scripts/systemd-setup.sh status     # Show service status
#   ./scripts/systemd-setup.sh logs       # Follow journald logs
#   ./scripts/systemd-setup.sh help       # Show this help message
#
# Requirements:
#   - systemd user manager running (standard on Pop!_OS / GNOME)
#   - The virtual environment exists at .venv/
#   - DISPLAY is set for X11 access

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="activity-agent"
UNIT_FILE="${HOME}/.config/systemd/user/${SERVICE_NAME}.service"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command>

Commands:
  install    Enable and start the service (one-shot setup)
  start      Start the service (requires install first)
  stop       Stop the running service
  enable     Enable auto-start on user login
  disable    Disable auto-start (does not stop a running service)
  uninstall  Stop, disable, and remove all traces of the service
  status     Show current service status
  logs       Follow journald logs in real time
  help       Show this help message

Examples:
  # First-time setup
  $(basename "$0") install

  # View live logs
  $(basename "$0") logs

  # Remove the service entirely
  $(basename "$0") uninstall
EOF
}

cmd_install() {
  echo "→ Creating systemd user directory if it doesn't exist..."
  mkdir -p "$(dirname "$UNIT_FILE")"

  # inject the current X11 display environment variables.
  echo "→ Generating systemd unit file at ${UNIT_FILE}..."
  cat <<EOF >"$UNIT_FILE"
[Unit]
Description=Activity Tracker Agent (Privacy-First Local Time Tracker)
After=graphical-session.target
PartOf=graphical-session.target

[Service]
Type=simple
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/.venv/bin/python -m activity_tracker.agent
Restart=on-failure
RestartSec=5

# Required for python-xlib, pynput, and xprintidle to connect to the X server.
# Captures the current DISPLAY during install, defaults to :0
Environment=DISPLAY=${DISPLAY:-:0}
Environment=XAUTHORITY=%h/.Xauthority

[Install]
WantedBy=default.target
EOF

  echo "→ Reloading systemd user manager…"
  systemctl --user daemon-reload
  echo "→ Enabling ${SERVICE_NAME} service…"
  systemctl --user enable "${SERVICE_NAME}.service"
  echo "→ Starting ${SERVICE_NAME} service…"
  systemctl --user start "${SERVICE_NAME}.service"
  echo "✓ ${SERVICE_NAME} is installed, enabled, and running."
  echo ""
  echo "  View logs:  journalctl --user -u ${SERVICE_NAME} -f"
  echo "  Stop it:    systemctl --user stop ${SERVICE_NAME}"
  echo "  Remove it:  $(basename "$0") uninstall"
}

cmd_start() {
  systemctl --user start "${SERVICE_NAME}.service"
  echo "✓ ${SERVICE_NAME} started."
}

cmd_stop() {
  systemctl --user stop "${SERVICE_NAME}.service"
  echo "✓ ${SERVICE_NAME} stopped."
}

cmd_enable() {
  systemctl --user enable "${SERVICE_NAME}.service"
  echo "✓ ${SERVICE_NAME} enabled (auto-starts on login)."
}

cmd_disable() {
  systemctl --user disable "${SERVICE_NAME}.service"
  echo "✓ ${SERVICE_NAME} disabled (will not start on next login)."
}

cmd_uninstall() {
  echo "→ Stopping ${SERVICE_NAME} service…"
  systemctl --user stop "${SERVICE_NAME}.service" 2>/dev/null || true
  echo "→ Disabling ${SERVICE_NAME} service…"
  systemctl --user disable "${SERVICE_NAME}.service" 2>/dev/null || true

  echo "→ Removing unit file…"
  rm -f "$UNIT_FILE"

  echo "→ Reloading systemd user manager…"
  systemctl --user daemon-reload
  echo "✓ ${SERVICE_NAME} uninstalled. No residue remains."
}

cmd_status() {
  systemctl --user status "${SERVICE_NAME}.service"
}

cmd_logs() {
  journalctl --user -u "${SERVICE_NAME}" -f --no-pager
}

case "${1:-help}" in
install) cmd_install ;;
start) cmd_start ;;
stop) cmd_stop ;;
enable) cmd_enable ;;
disable) cmd_disable ;;
uninstall) cmd_uninstall ;;
status) cmd_status ;;
logs) cmd_logs ;;
help | --help | -h) usage ;;
*)
  echo "Error: unknown command '${1}'" >&2
  echo ""
  usage >&2
  exit 1
  ;;
esac
