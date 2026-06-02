#!/usr/bin/env bash
# No-agent cron entrypoint for the daily Garmin dashboard pull.
# Hermes runs this with `--no-agent --script` and delivers its stdout VERBATIM
# (no LLM, no tokens). Sources the profile .env so the credentials fallback
# (GARMIN_EMAIL / GARMIN_PASSWORD) and any overrides are in the environment.
# Canonical copy lives here in the repo; bootstrap copies it to
# ~/.hermes/profiles/butler/scripts/garmin_dashboard.sh (where `cron --script` resolves names).
export PATH="$HOME/.local/bin:$PATH"
set -a; . "$HOME/.hermes/profiles/butler/.env" 2>/dev/null || true; set +a
exec uv run /home/drc/butler/modules/daily/garmin-dashboard/scripts/garmin_pull.py --telegram
