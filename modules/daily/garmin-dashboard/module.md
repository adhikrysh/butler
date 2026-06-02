# Module: garmin-dashboard

- **Type:** proactive (scheduled extraction)
- **Schedule:** `0 15 * * *` UTC = 8:00am US Pacific (PDT). Cron runs on server time —
  see README for the DST caveat (this becomes 7am in PST).
- **AGENT job — needs the LLM.** Unlike the Steve Jobs letter (which is `--no-agent`),
  this job *must* run the agent: only the agent can call the **tinyfish** MCP
  `run_web_automation` tool that logs into Garmin and reads the dashboard.
  - Cron entrypoint: an agent run with the `garmin-dashboard` skill attached
    (`hermes -p butler cron create "<prompt>" --skill garmin-dashboard`).
  - Registered by `bootstrap/register_cron.sh` as `daily-garmin-dashboard`.
- **What it does:** logs in (async — `run_web_automation_async` + poll, so a slow morning
  can't time out the run), clicks through every dashboard widget, **extracts** all visible
  stats, **saves** them to `state/`, and **sends adhi a Telegram summary** of the numbers
  (`--deliver telegram:<id>`). The interactive "show me now" path may use synchronous
  `run_web_automation` for speed.
- **Credentials:** `GARMIN_EMAIL` / `GARMIN_PASSWORD` in `~/.hermes/profiles/butler/.env`
  (mode 600, git-ignored). The agent reads them via the shell and never prints the password.
- **Output / state (git-ignored, `**/state/`):**
  - `state/<YYYY-MM-DD>.json` — one pretty JSON object per day.
  - `state/history.jsonl` — same object appended as one compact line per run (the trend log).
- **Memory:** none. Runtime state only (the `state/` files above).
- **Cron registration (run once, or via `bootstrap/register_cron.sh`):**
  ```bash
  hermes -p butler cron remove daily-garmin-dashboard >/dev/null 2>&1 || true
  hermes -p butler cron create "0 15 * * *" \
    "Run the daily Garmin dashboard extraction (see the garmin-dashboard skill)." \
    --skill garmin-dashboard --name daily-garmin-dashboard --deliver "telegram:<your-id>"
  ```
- **Manual test (one run now):**
  ```bash
  hermes -p butler cron run daily-garmin-dashboard      # trigger the registered job, or:
  hermes -p butler --skills garmin-dashboard -z "Run the daily Garmin dashboard extraction."
  ```
  Then check `state/<today>.json` exists and contains real numbers.
