#!/usr/bin/env bash
# No-agent cron entrypoint for the daily Steve Jobs letter.
# Hermes runs this with `--no-agent --script` and delivers its stdout VERBATIM
# (no LLM). Canonical copy lives here in the repo; bootstrap copies it to
# ~/.hermes/scripts/steve_jobs_letter.sh (where `cron --script` resolves names).
export PATH="$HOME/.local/bin:$PATH"
exec uv run /home/drc/butler/modules/daily/steve-jobs-letter/scripts/fetch_letter.py --telegram
