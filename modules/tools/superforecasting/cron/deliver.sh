#!/usr/bin/env bash
# No-agent cron: daily decision-journal check-in + any decisions due for review.
# forecast.py daily always prints the prompt; Hermes delivers stdout to Telegram
# verbatim. the user's reply is handled by the agent via SKILL.md.
export PATH="$HOME/.local/bin:$PATH"
# No-agent crons run under HOME=<profile>/home (sandboxed); source the profile
# .env by ABSOLUTE path so CRM_SHEET_ID + CRM_SA_KEY are present.
set -a; . /home/drc/.hermes/profiles/butler/.env 2>/dev/null || true; set +a
exec uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py daily
