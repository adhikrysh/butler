# Module: sheet-backup

- **Type:** proactive (no-agent cron). **No `SKILL.md`** — this is a backup job, not an agent-invocable skill, so it's deliberately invisible to the agent.
- **What it does:** snapshots every tab of the `butler` spreadsheet to CSV, closing the one backup gap. The Sheet is the only app data that lives off the box (in Google's cloud), so the server's restic→B2 backup can't see it; this pulls it onto disk where restic does.
- **Where:** writes `state/backups/<tab>.csv` in the profile (fixed filenames, overwritten each run). restic provides the point-in-time versioning + off-site/encrypted copy, so the files aren't timestamped here. Garmin and steve-jobs runtime state already live in the profile, so they're already backed up — this only adds the Sheets.
- **Tools:** `scripts/snapshot.py` over the shared `../../../lib/sheets.py` (`tabs()` + `values()` give verbatim cell values per tab). Reuses `CRM_SHEET_ID` + `CRM_SA_KEY`.
- **Cron (no-agent):** `cron/deliver.sh` → `snapshot.py` (`0 8 * * *` UTC, ~1am PT). Registered in `bootstrap/register_cron.sh` as `daily-sheet-backup`. Silent on success; a failure prints to stdout so Hermes delivers the alert to Telegram (a silent backup failure is the dangerous kind).
- **Restore:** `restic restore` the CSVs from B2, then re-import each into a Sheet tab (CSV round-trips, including multi-line cells via standard quoting).
