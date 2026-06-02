# Module: garmin-dashboard

- **Type:** proactive (scheduled push) + interactive.
- **Schedule:** `0 15 * * *` UTC = 8:00am US Pacific (PDT) → Telegram. Cron runs on
  server time — see README for the DST caveat (becomes 7am in PST).
- **Daily push = NO LLM.** Runs in `--no-agent` mode: the script pulls stats and its
  stdout (a short summary) is delivered to Telegram **verbatim**. Zero tokens, zero
  TinyFish credits, robust.
  - Cron entrypoint: `cron/deliver.sh` → `scripts/garmin_pull.py --telegram`.
  - `deliver.sh` is copied to `~/.hermes/profiles/butler/scripts/garmin_dashboard.sh`
    by `bootstrap/register_cron.sh` (that's where `cron --script` resolves names).
- **Why not the browser/tinyfish?** Garmin's anti-bot throws a captcha at repeated
  automated *logins*, so daily browser automation is flaky. This pulls data through
  Garmin's real API (`garth`/`garminconnect`): authenticate **once**, reuse saved
  OAuth tokens forever (auto-refresh), no browser, no captcha. (TinyFish MCP stays
  installed for genuinely API-less web tasks.)
- **Auth / tokens:** `scripts/garmin_pull.py` resumes OAuth tokens from
  `~/.hermes/profiles/butler/garmin_tokens/` (mode 700, **not** in git). If they're
  missing/expired it falls back to a credentials login using `GARMIN_EMAIL` /
  `GARMIN_PASSWORD` from the profile `.env` and re-saves tokens. First run mints them.
- **Interactive path:** `SKILL.md` is used when adhi asks Butler in chat ("my Garmin
  stats" / "how did I sleep"). The agent runs the script and relays the numbers. The
  script's JSON output (default, no `--telegram`) feeds that path.
- **Output / state (git-ignored, `**/state/`):**
  - `state/<YYYY-MM-DD>.json` — one pretty record per day (yesterday + today).
  - `state/history.jsonl` — same record appended as one line per run (the trend log).
- **Memory:** none. Runtime state only (the `state/` files + the token dir).
- **Cron registration (run once, or via `bootstrap/register_cron.sh`):**
  ```bash
  cp cron/deliver.sh ~/.hermes/profiles/butler/scripts/garmin_dashboard.sh
  hermes -p butler cron create "0 15 * * *" --no-agent --script garmin_dashboard.sh \
    --deliver telegram:<your-id> --name daily-garmin-dashboard
  ```
- **Manual test (one run now):**
  ```bash
  # mints tokens on first run, then prints the verbatim Telegram summary:
  uv run modules/daily/garmin-dashboard/scripts/garmin_pull.py --telegram
  # or the full JSON record:
  uv run modules/daily/garmin-dashboard/scripts/garmin_pull.py
  ```
