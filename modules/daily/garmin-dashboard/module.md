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
  Garmin's real API using the `garminconnect` library (v0.3+, which does its own
  SSO/OAuth login on `curl_cffi` — **not** garth): authenticate **once**, reuse saved
  OAuth tokens (auto-refresh), no browser, no captcha. (TinyFish MCP stays installed
  for genuinely API-less web tasks.)
- **Auth / tokens:** `scripts/garmin_pull.py` resumes OAuth tokens from
  `~/.hermes/profiles/butler/garmin_tokens/` (mode 700, **not** in git). If they're
  missing/expired it falls back to a credentials login using `GARMIN_EMAIL` /
  `GARMIN_PASSWORD` from the profile `.env` and re-saves tokens. First run mints them.
- **Interactive path:** `SKILL.md` is used when adhi asks Butler in chat ("my Garmin
  stats" / "how did I sleep"). The agent runs the script and relays the numbers. The
  script's JSON output (default, no `--telegram`) feeds that path.
- **Metrics captured** (8 endpoints/day, for yesterday + today): steps (+goal),
  resting/min/max HR, calories, floors, intensity minutes, Body Battery (recent/high/low
  + charged/drained), stress (avg/max), sleep (duration + score), HRV, training readiness
  (+level, recovery time), VO₂max, training status, respiration (waking/sleep/low/high),
  SpO₂. Missing metric -> `null` (watch not worn, sensor off, or not synced).
- **Freshness / can we sync?** No — the API only *reads* Garmin's cloud; it can't make the
  watch upload. Data reaches the cloud when the Garmin Connect **phone app** syncs the
  watch over Bluetooth (or the watch's own **Wi-Fi auto-upload**, on supported models). So
  `today` is usually partial at 8am, which is why the summary **headlines the last
  fully-synced day (yesterday)**. The summary footer shows `📡 Watch last synced Xh ago`
  (from `get_device_last_used` → `lastUsedDeviceUploadTime`) so staleness is always visible;
  the record also stores `last_sync_utc` + `device`. `request_reload(date)` only nudges
  Garmin to reprocess *already-uploaded* data (backfilling old dates) — it can't fetch new
  data off the watch.
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
