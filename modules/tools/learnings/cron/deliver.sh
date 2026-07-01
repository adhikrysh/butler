#!/usr/bin/env bash
# No-agent cron: weekly digest of pending (med+high) learnings the agent has
# captured. learn.py digest prints the formatted list — empty output on a quiet
# week means no Telegram message. No secrets needed; the store path defaults to
# the absolute profile path, which resolves the same host-side and in-sandbox.
export PATH="$HOME/.local/bin:$PATH"
exec uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py digest
