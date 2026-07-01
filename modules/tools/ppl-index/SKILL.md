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

## Behavior — the fragment is a seed, not the record
Whatever the user gives you is a **starting point for your own research, not the data to store.** A bare name is enough. His job ends at "I met Jane from Acme"; *your* job is to turn that seed into a full, sourced row by going and finding everything yourself. Assume he wants you to know far more about this person than he just told you. Drive his input-and-check time to zero — act, don't interrogate, don't wait for a second pass.

1. **Save first, never block.** The instant he names a person, `contacts.py add` what he gave. The row must exist before you enrich or reply. Then go.

2. **Search on your own — be exhaustive, go down every avenue.** Don't stop at one lookup; the first hit is where you start, not where you stop. Treat every fragment — name, company, title, place, a LinkedIn URL, a message thread — as a lead and pull every thread until the avenues run dry:
   - **Find their profiles yourself, even when he gave none — via the tinyfish MCP.** Start with tinyfish `search` (free) on `"<name>" <company / role / where-met>` to locate LinkedIn / X / GitHub / personal site / talks. Read pages with `fetch_content` (free, markdown). When a page is JS- or auth-walled (LinkedIn and X almost always are), **first mine the free `search` snippets** — a LinkedIn/X result's headline, current role, and even a project mention are usually sitting right in the snippet, no fetch needed; note the snippet as your source. Only when the snippet isn't enough do you escalate to `run_web_automation`, which renders and clicks through what a plain fetch can't (it spends automation credits — reserve it for the pages that need it). **Always check LinkedIn** — it's the highest-signal source; walled is not an excuse to skip it, snippets first, then `run_web_automation`. Several people at once → `batch_create`.
   - **Chase every avenue.** Company team/about pages, GitHub, personal site, conference talks, podcasts, papers, press, funding/company databases, their own posts. When one source names something new — a cofounder, a former employer, a school, a project — follow it. Cross-reference across sources until the picture is consistent. You are done when the leads are exhausted, not when the first one pays out.
   - **Hunt the email hard.** Same tools across the profile, company team/about pages, GitHub commits, personal site, talks. Record a real address you actually find — with *where you found it* in `notes`. A company pattern (`first.last@company.com`) is stored **only flagged as a guess** (`notes: "email inferred — unverified"`); never pass a guess off as confirmed. A wrong email is real-world damage.

3. **Only enrich when you're sure it's the right person — this is a hard gate.** Enrichment is gated on identity. Before you write a single enriched field, confirm it's *this* person and not a namesake — company, role, location, and how-he-met must line up across your sources. If two people can't be told apart and you have nothing to disambiguate, **write nothing enriched, leave those fields blank, and say so.** A confidently-wrong row is worse than a sparse one; never guess at identity to fill a cell.

4. **Fill every column you can stand behind** via `update --match '{"name":"…"}'`: `title`, `company`, `location`, `linkedin`, `twitter`, `email`, and a tight 1–2-line `notes` (what they do, why they matter, + your sources). Relationship facts come from the user — `met_where`, `met_date`, `referred_by` — don't invent those. If he already gave the relationship context in prose, normalize it into `met_where` instead of leaving it only in `notes`.

5. **Close the loop in ONE message.** Tell him what you filled and your sources (so he audits at a glance), and ask at most one short question — only for what genuinely can't be found. If he already supplied the material in prose, don't ask for it again. Acting beats asking.

**Columns are dynamic** — read the header row; write any column that exists; never invent columns or assume positions.
