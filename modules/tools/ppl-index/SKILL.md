---
name: ppl-index
description: the user's people index (the `ppl-index` tab of his `butler` Google Sheet — the durable store of people he knows). Use WHENEVER the user mentions a person he's met or knows — who they are, where they work, how/where he met them — or asks who he knows or a contact's details. Plain statements like "I met X" MUST trigger it, not only questions. (Outreach he *sends* lives in the separate `cold-outbounds` skill.)
---

# People index

the user's contact store is the `ppl-index` tab of his `butler` Google Sheet. You operate it through the `contacts.py` CLI. (Outreach + reply tracking is a separate skill: `cold-outbounds`.)

## ⚠️ The one rule that matters
**You have NO durable memory. The sheet is the ONLY place a contact survives.** Your chat memory is wiped when context compacts. So:
- When the user tells you about a person, your **FIRST action — before you reply — is to run `contacts.py add`** to write it.
- **NEVER** say "noted" / "I'll remember" *without having just run the command* — if you didn't run it, it's gone.
- "Who do I know…" → run `contacts.py find`/`dump` and answer ONLY from what it prints, never from chat memory.

## Support files (read when relevant)
- `references/bulk-contact-intake.md` — batching several people at once.
- `references/safe-json-shelling.md` — build `contacts.py` JSON safely when a note has quotes/parens.
- `references/thread-enrichment.md` — turning a LinkedIn URL + message thread into `title`, `company`, `met_where`, and `notes`.

## Commands
```
uv run /home/drc/butler/modules/tools/ppl-index/scripts/contacts.py find "<name or company>"
uv run /home/drc/butler/modules/tools/ppl-index/scripts/contacts.py dump
uv run /home/drc/butler/modules/tools/ppl-index/scripts/contacts.py add --json '{"name":"Jane Doe","company":"Acme"}'
uv run /home/drc/butler/modules/tools/ppl-index/scripts/contacts.py update --match '{"name":"Jane Doe"}' --json '{"email":"jane@example.com"}'
```

## Behavior — add immediately, then go find everything yourself
This is the whole point: the user drops a fragment, *you* do the research and the row fills itself. The aim is to drive his input-and-check time to zero — act, don't interrogate.

### Fast-path on user-supplied context
If the user gives you a LinkedIn URL, a company, a title, a place, or a message thread, **use it right away** — don't leave those fields blank waiting for a second pass. First save the row, then enrich from the provided clues.

First `add` what he gave (never block the save). Then, unprompted, run the contact down:

- **Find their profiles even when he didn't give them — via the tinyfish MCP.** Start with tinyfish `search` (free) on `"<name>" <company / role / where-met>` to locate LinkedIn / X / GitHub / site, then read pages with `fetch_content` (free, markdown). When a page is JS- or auth-walled (LinkedIn and X almost always are), escalate to `run_web_automation`, which renders and clicks through what a plain fetch can't (it spends automation credits — reserve it for pages that need it). Several people at once → `batch_create`.
- **Hunt the email.** tinyfish `search` + `fetch_content` across the profile, company team/about pages, GitHub, personal site, talks; escalate to `run_web_automation` if walled. Record a real address you actually find — with *where you found it* in `notes`. If the best you can do is infer a company pattern (`first.last@company.com`), store it **only flagged as a guess** (`notes: "email inferred — unverified"`); never pass a guess off as confirmed. A wrong email is real-world damage.
- **Fill every column you can stand behind** via `update --match '{"name":"…"}'`: `title`, `company`, `location`, `linkedin`, `twitter`, `email`, and a tight 1–2-line `notes` (what they do, why they matter, + your sources). Relationship facts come from the user — `met_where`, `met_date`, `referred_by` — don't invent those. If the user already gave the relationship context in prose, normalize it into `met_where` instead of leaving it only in `notes`.
- **Right-person check.** Confirm each fact is *this* person, not a namesake — match company / role / location. Ambiguous with nothing to disambiguate → leave it and say so.
- **Close the loop in ONE message.** Tell the user what you filled and your sources (so he audits at a glance), and ask at most one short question — only for what truly can't be found. If the user already supplied the source material in prose, don't ask for it again. Acting beats asking.

**Columns are dynamic** — read the header row; write any column that exists; never invent columns or assume positions.

## Remembering what you learn
The repo here is **read-only to you** — your shell runs in a sandbox that mounts the code read-only, so you physically cannot edit this SKILL, a script, or a module (a write returns `Read-only file system`). That's intended. Short lessons → your built-in **memory** (auto-loads each session); longer notes → `/home/drc/.hermes/profiles/butler/state/learned/` (writable). To change code, suggest the improvement to the user — a human makes the change and ships it. Never print the service-account key.
