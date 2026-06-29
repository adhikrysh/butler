#!/usr/bin/env bash
# No-agent cron entrypoint for the outreach follow-up digest. Prints the
# cold-outbounds rows due for a nudge; Hermes delivers stdout to Telegram
# verbatim. Empty stdout (nothing due) => Hermes sends nothing.
export PATH="$HOME/.local/bin:$PATH"
# No-agent crons run under HOME=<profile>/home (sandboxed); source the profile
# .env by ABSOLUTE path so CRM_SHEET_ID + CRM_SA_KEY are present.
set -a; . /home/drc/.hermes/profiles/butler/.env 2>/dev/null || true; set +a
exec uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py nudges
