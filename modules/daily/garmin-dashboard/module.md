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
- **Deterministic "sync-gate" (optional, off unless `GARMIN_SYNC_CMD` or `--sync`).** To
  pull *provably fresh* data instead of yesterday's, the script records the watch's current
  cloud-upload time, fires a sync trigger, and **polls `get_device_last_used()` until the
  upload time advances** (proof a fresh upload landed) or `GARMIN_SYNC_TIMEOUT` (default
  180s) elapses — *only then* does it pull. `synced_fresh` (true/false/null) is stored in
  the record; an unconfirmed sync adds a `⚠️ sync not confirmed` note to the summary.

  The sync must go through the **iPhone 15** — the watch is paired to it, so only it can
  push the watch's data to Garmin's cloud (the tailnet Pixel can't sync a watch it isn't
  paired to; ADB/`monkey` is Android-only and N/A). Trigger options:
  - **Phone-side, time-based (simplest):** an **Apple Shortcuts** Personal Automation at
    ~7:55am → *Open App → Garmin Connect* (toggle **Run Without Asking**). Then run the pull
    in **gate-only** mode — pass `--sync` with no `GARMIN_SYNC_CMD`, so butler skips the
    trigger and just polls until the fresh upload lands. No server→phone path needed.
  - **Server-triggered (butler drives it):** install **Pushcut** on the iPhone, make a
    Pushcut automation that opens Garmin Connect, and set
    `GARMIN_SYNC_CMD="curl -s -X POST https://api.pushcut.io/<token>/notifications/<name>"`.
    Butler fires it right before polling.
  Either way the **gate** is what guarantees freshness; the trigger only kicks it off. iOS
  may need the phone awake for the app to foreground, so pick a time you're up — and the
  gate falls back gracefully (headline last-complete-day + the ⚠️ note) on timeout. Without
  `GARMIN_SYNC_CMD`/`--sync`, the job just pulls whatever the cloud already has.
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
