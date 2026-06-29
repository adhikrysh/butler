#!/usr/bin/env bash
# No-agent cron: weekly calibration report (stated confidence vs actual hit rate).
# stdout delivered to Telegram verbatim.
export PATH="$HOME/.local/bin:$PATH"
set -a; . /home/drc/.hermes/profiles/butler/.env 2>/dev/null || true; set +a
exec uv run /home/drc/butler/modules/tools/superforecasting/scripts/forecast.py calibration
