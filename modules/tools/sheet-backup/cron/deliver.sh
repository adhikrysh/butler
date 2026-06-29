#!/usr/bin/env bash
# No-agent cron: snapshot the butler spreadsheet tabs to CSV in the profile so the
# server's restic→B2 backup captures them. Silent on success; failures → Telegram.
export PATH="$HOME/.local/bin:$PATH"
# No-agent crons run under HOME=<profile>/home (sandboxed); source the profile .env
# by ABSOLUTE path so CRM_SHEET_ID + CRM_SA_KEY are present.
set -a; . /home/drc/.hermes/profiles/butler/.env 2>/dev/null || true; set +a
exec uv run /home/drc/butler/modules/tools/sheet-backup/scripts/snapshot.py
