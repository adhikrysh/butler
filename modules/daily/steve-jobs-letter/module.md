# Module: steve-jobs-letter

- **Type:** proactive (scheduled push)
- **Schedule:** `0 7 * * *` (07:00 local) → Telegram (home channel)
- **Tools:** terminal (runs `scripts/fetch_letter.py` via `uv`)
- **Memory:** none read/written. Runtime state only: `state/served.json` (gitignored,
  tracks which letters were already sent; auto-resets once all are exhausted).
- **Script ↔ skill contract (stdout JSON):**
  `{ "id", "title", "author", "date", "url", "text" }`
- **Cron registration (run once, or via `bootstrap/register_cron.sh`):**
  ```bash
  butler cron create "0 7 * * *" \
    "Run the steve-jobs-letter skill and deliver today's letter to Telegram." \
    --skill steve-jobs-letter --name daily-steve-jobs-letter
  ```
- **Tests:**
  ```bash
  cd modules/daily/steve-jobs-letter
  PYTHONPATH=scripts uv run --with beautifulsoup4 --with requests --with pytest pytest tests/ -q
  ```
