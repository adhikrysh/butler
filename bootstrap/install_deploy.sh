#!/usr/bin/env bash
# One-time: install + enable the self-deploy timer (run on the box).
set -euo pipefail
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR" "$HOME/.hermes/profiles/butler/logs"
chmod +x "$REPO_DIR/bootstrap/deploy.sh" "$REPO_DIR/bootstrap/run_tests.sh"
cp "$REPO_DIR/bootstrap/systemd/butler-deploy.service" "$UNIT_DIR/"
cp "$REPO_DIR/bootstrap/systemd/butler-deploy.timer"   "$UNIT_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now butler-deploy.timer
systemctl --user list-timers butler-deploy.timer --no-pager
echo "Installed. deploy.sh runs every 5 min."
