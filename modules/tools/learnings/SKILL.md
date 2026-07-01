---
name: learnings
description: the agent's queue of proposed skill improvements (a JSONL under state/learned). Use WHENEVER you discover, mid-task, something that would make a skill better — a wrong assumption baked into a skill, a cheaper/better method, a recurring friction — INSTEAD of trying to edit the skill (you can't; skill_manage is blocked). Also use when the user says he promoted or wants to dismiss a learning.
---

# Learnings — propose, don't self-edit

You cannot change your own skills. When you learn something that would improve one, you **log it here**; the user reviews and promotes it into the skill via git. This is the sanctioned path the skill-edit block points you to. The store is a local JSONL on the writable `state/` mount — never the repo.

## When to log (and at what importance)
- **high** — would change how a skill works: a wrong assumption in a skill, a materially better/cheaper method, a recurring friction that wasted real effort. Also say it in one line in your reply, now.
- **med** — a genuine refinement worth folding eventually, not urgent. Goes in the weekly digest.
- **low** — a one-off, or already covered by the skill. Logged for completeness; never pushed at the user. When in doubt it's `low` — don't inflate importance to get attention.

Log the moment you notice it, before you reply — your chat context is wiped between sessions, so an unlogged learning is lost.

## Commands
Log a learning (dedups automatically against anything already logged):
```
uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py add --json '{"skill":"ppl-index","insight":"mine free LinkedIn search snippets before spending run_web_automation credits","why":"the headline/role is usually in the snippet","importance":"high"}'
```
See what's pending / browse everything:
```
uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py pending
uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py list --skill ppl-index
```
Mark one after the user acts on it (this stops it resurfacing):
```
uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py review --id L-a1b2c3 --status promoted
uv run /home/drc/butler/modules/tools/learnings/scripts/learn.py review --id L-a1b2c3 --status dismissed
```

## Behavior
- **Learned something skill-relevant → `add` it immediately, before replying.** Tag `skill` (which skill it's about) and `importance`. `insight` is the change you'd make, in one line; `why` is the mechanism/evidence so review is fast.
- **High importance → also surface inline.** One line in your reply: "💡 logged a possible `<skill>` improvement: `<insight>` — for your review." Then continue the task. Never derail for med/low.
- **Don't edit skills.** `skill_manage` is blocked by design. Logging here *is* the correct action — not a fallback.
- **User promoted / dismissed one → `review` it.** When he says "promoted the ppl-index one" or "dismiss L-a1b2c3", run `review` so the weekly digest stops showing it. If he references it loosely, `list` to find the id first.
- **Quote-heavy insight → build the JSON in Python and `shell_quote` it** before calling `learn.py`; don't hand-nest quotes in the shell.
