# Module: ppl-index

- **Type:** interactive (agent-invoked). No cron.
- **What it does:** the durable store of people the user knows. He drops a fragment; the agent adds the row, then runs the person down itself (LinkedIn/X/email) via the tinyfish MCP and fills what it can stand behind — driving his input/check time toward zero.
- **Sheet:** the `ppl-index` tab of the `butler` spreadsheet (12 cols: name, email, company, title, met_where, met_date, location, linkedin, twitter, referred_by, notes, added_date). Header row = schema, read live. Reuses `CRM_SHEET_ID` + `CRM_SA_KEY`.
- **Tools:** `scripts/contacts.py` CLI — `find / dump / add / update` — over the shared `../../../lib/sheets.py`. `SKILL.md` carries the enrichment + persistence behavior; `references/` holds the bulk-intake + safe-JSON-shelling patterns.
- **Enrichment:** tinyfish `search`/`fetch_content` (free) → `run_web_automation` for JS/auth-walled pages (LinkedIn/X) → `batch_create` for bulk. Sources noted in `notes`; email guesses flagged unverified.
- **Tests:** none of its own (thin CLI); the shared sheet helpers are tested in `modules/lib/tests/`.
- **Split note:** was the people half of the old `crm` module; outreach is now the separate `cold-outbounds` module, and `sheets.py` moved to the shared `modules/lib/`.
