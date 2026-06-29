---
name: cold-outbounds
description: the user's outreach log (the `cold-outbounds` tab of his `butler` Google Sheet) — cold outreach + reply tracking + follow-up nudges. Use WHENEVER the user says he emailed / DMed / messaged / cold-reached someone, asks about follow-ups or an outreach's status, or wants to drop/snooze a thread. (People he simply *knows* live in the separate `ppl-index` skill.)
---

# Cold outbounds

the user's outreach pipeline is the `cold-outbounds` tab of his `butler` Google Sheet. You operate it through the `outbound.py` CLI. (Who he *knows* is the separate `ppl-index` skill.)

## ⚠️ The one rule that matters
**The sheet is the ONLY durable store.** When the user logs an outreach or a decision about one, your **FIRST action — before you reply — is to run the matching `outbound.py` command.** Never say "noted" without having just run it. Answer status questions only from what `find`/`dump` prints.

## Commands
```
uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py find "<name or company>"
uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py dump
uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py add --json '{"name":"Bob","platform":"li","reason":"internship","message":"<gist>","replied":"no reply","sent_date":"2026-06-25"}'
uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py update --match '{"name":"Bob"}' --json '{"status":"dropped","last comment":"2026-06-25 — not pursuing"}'
uv run /home/drc/butler/modules/tools/cold-outbounds/scripts/outbound.py nudges
```

## Behavior
- **Logging an outreach → `add` with the tracking fields.** When the user says he emailed/DMed/messaged someone, set `platform` (`mail`/`li`/`x`), `replied`: `"no reply"`, and `sent_date` to today (YYYY-MM-DD) — those drive the follow-up nudges. Don't leave them blank.
- **A decision about a thread (drop / snooze / a note) → `update` immediately, before replying.** First `find "<name>"` to locate the row, then `update --match '{"name":"X"}' --json '{"status":"dropped","last comment":"<date> — <reason>"}'`. `status`: `dropped` (forget) or `snoozed`.
- **Follow-up nudges.** `nudges` prints cold, unreplied, active outreach (≥7 days old, parseable `sent_date`). A digest is delivered automatically each evening; you can also run it on request.
- **Email sync.** `sync` (dry-run unless `--apply`) reads Sent+Inbox over IMAP and refreshes reply-status on `mail` rows; it also surfaces new outbound contacts it found (`new_candidates`) — report those to the user rather than writing them blindly.
- **Quote-heavy messages → build the JSON in Python and `shell_quote` it** before calling `outbound.py`; don't hand-nest quotes in the shell.
- **Columns are dynamic** — read the header row; write any column that exists; never invent columns or assume positions.

## Remembering what you learn
The repo here is **read-only to you** — your shell runs in a sandbox that mounts the code read-only, so you physically cannot edit this SKILL, a script, or a module (a write returns `Read-only file system`). That's intended. Short lessons → your built-in **memory** (auto-loads each session); longer notes → `/home/drc/.hermes/profiles/butler/state/learned/` (writable). To change code, suggest the improvement to the user — a human makes the change and ships it. Never print the service-account key.
