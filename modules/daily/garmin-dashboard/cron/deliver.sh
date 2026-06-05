#!/usr/bin/env bash
# No-agent cron entrypoint for the daily Garmin dashboard pull.
# Hermes runs this with `--no-agent --script` and delivers its stdout VERBATIM
# (no LLM, no tokens). Sources the profile .env so the credentials fallback
# (GARMIN_EMAIL / GARMIN_PASSWORD) and any overrides are in the environment.
# Canonical copy lives here in the repo; bootstrap copies it to
# ~/.hermes/profiles/butler/scripts/garmin_dashboard.sh (where `cron --script` resolves names).
export PATH="$HOME/.local/bin:$PATH"
set -a; . "$HOME/.hermes/profiles/butler/.env" 2>/dev/null || true; set +a
# --sync gates the pull on a fresh upload: pair with the iPhone Shortcut that opens
# Garmin Connect at 07:55 (5 min before this 08:00 run). Gate confirms the upload is
# recent; on timeout it pulls anyway and flags "⚠️ sync not confirmed".
#
# CRITICAL: Hermes kills a no-agent cron script at 120s. The gate's wait MUST fit inside
# that budget (gate + ~20s fetch < 120s), or the cron times out and never delivers. So cap
# the gate well under it. (In gate-only mode the 07:55 sync has either already landed by
# 08:00 or it hasn't — polling longer doesn't help — so a short window is correct.)
export GARMIN_SYNC_TIMEOUT="${GARMIN_SYNC_TIMEOUT:-45}"
export GARMIN_SYNC_POLL="${GARMIN_SYNC_POLL:-10}"
exec uv run /home/drc/butler/modules/daily/garmin-dashboard/scripts/garmin_pull.py --telegram --sync
