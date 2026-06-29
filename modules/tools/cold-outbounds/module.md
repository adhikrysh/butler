# Module: cold-outbounds

- **Type:** interactive (agent-invoked) + proactive (no-agent cron).
- **What it does:** the outreach engine — log cold outreach, track replies, get follow-up nudges, and (gated) auto-maintain `mail` rows from IMAP.
- **Sheet:** the `cold-outbounds` tab of the `butler` spreadsheet. Header row = schema, read live. Reuses `CRM_SHEET_ID` + `CRM_SA_KEY`.
- **Tools:** `scripts/outbound.py` CLI — `find / dump / add / update / nudges / sync` — over the shared `../../../lib/sheets.py`, `scripts/outboundcore.py` (pure: select_nudges / classify / derive-status / thread-build), and `scripts/mailsource.py` (read-only IMAP, BODY.PEEK).
- **Cron (no-agent):** `cron/deliver.sh` → `outbound.py nudges` (`0 4 * * *` UTC, 9pm PT — cold/unreplied digest; silent when nothing's due). Registered in `bootstrap/register_cron.sh` as `daily-cold-outbounds-nudge`.
- **Tests:** `tests/test_outboundcore.py` (pure functions, fixture-based). Run: `cd modules/tools/cold-outbounds && PYTHONPATH=scripts uv run --with pytest pytest tests/ -q`. Wired into `bootstrap/run_tests.sh`.
- **Email sync:** `sync` needs `GMAIL_ADDR/_APP_PW`, `ICLOUD_ADDR/_APP_PW` in `.env`; not yet scheduled (manual/agent-run).
- **Split note:** was the outreach half of the old `crm` module; the people store is now the separate `ppl-index` module, and `sheets.py` moved to the shared `modules/lib/`.
