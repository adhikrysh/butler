#!/usr/bin/env python3
"""Pre-tool-call hook — hard-block `skill_manage` so skills are READ-ONLY to the agent.

Butler's skills live in the repo (`skills.external_dirs = /home/drc/butler/modules`).
Hermes' `skill_manage` tool edits skills *wherever they live*, host-side, outside the
docker sandbox — so an agent "improving its own skill" writes into the repo working
tree, which jams the pull-based deploy (it skips on a dirty tree) and, worse, buries
the learning inside a skill instead of the reviewable learnings lane.

This hook fires before every tool call. Registered in config.yaml under
`hooks.pre_tool_call` with `matcher: "skill_manage"` (Hermes matches tool names with
`fullmatch`, so it scopes to the writer only — `skill_view` / `skills_list` still work).
We re-check `tool_name` here too, defensively, and no-op for anything else.

Wire protocol (see hermes-agent/agent/shell_hooks.py):
  stdin  : {"hook_event_name": "pre_tool_call", "tool_name": "...", "tool_input": {...}, ...}
  stdout : {"action": "block", "message": "..."}  → reject the call
           <no output>                            → allow (silent no-op)

The block message redirects the agent to its persistent, reviewable learnings lane.
The user promotes good learnings into a skill deliberately, via git. See ARCHITECTURE.md.
"""
import json
import sys

BLOCK_MESSAGE = (
    "skill_manage is disabled — skills are READ-ONLY to you. Do not create, edit, "
    "patch, or delete skills; you cannot change your own instructions. If you learned "
    "something worth keeping, write it to your memory (persists across sessions) or a "
    "note under state/learned/. The user reviews those and promotes the good ones into "
    "the skill via git. Capture the learning there and continue the task."
)


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    # Defense in depth: only block the writer, even if the config matcher drifts.
    if isinstance(data, dict) and data.get("tool_name") == "skill_manage":
        json.dump({"action": "block", "message": BLOCK_MESSAGE}, sys.stdout)
    # else: emit nothing → allow the call.
    return 0


if __name__ == "__main__":
    sys.exit(main())
