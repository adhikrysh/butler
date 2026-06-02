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
- **Metrics captured — everything.** Each run hits **~24 per-day endpoints** (user summary,
  sleep + stages, HRV, stress, respiration, SpO₂, intraday + resting HR, intraday steps,
  floors, intensity minutes, hydration, Body Battery + events, training readiness, training
  status, max metrics, endurance score, hill score, fitness age, running tolerance,
  activities, body composition, blood pressure) plus **3 account snapshots** (race
  predictions, lactate threshold, personal records), for yesterday + today. Each endpoint's
  **raw response is archived verbatim** (no field lost — for future downstream use cases);
  a flat curated `stats` subset is derived from that raw (no extra API calls) for the
  summary + history log. The registry lives in `scripts/garmin_pull.py` (`_DAILY`,
  `_ACCOUNT`) — add a line to capture more. Missing metric -> `null`.
- **Freshness / can we sync?** No — the API only *reads* Garmin's cloud; it can't make the
  watch upload. Data reaches the cloud when the Garmin Connect **phone app** syncs the
  watch over Bluetooth (or the watch's own **Wi-Fi auto-upload**, on supported models). So
  `today` is usually partial at 8am, which is why the summary **headlines the last
  fully-synced day (yesterday)**. The summary footer shows `📡 Watch last synced Xh ago`
  (from `get_device_last_used` → `lastUsedDeviceUploadTime`) so staleness is always visible;
  the record also stores `last_sync_utc` + `device`. `request_reload(date)` only nudges
  Garmin to reprocess *already-uploaded* data (backfilling old dates) — it can't fetch new
  data off the watch.
- **Deterministic "sync-gate" (ACTIVE — `cron/deliver.sh` passes `--sync`).** The script
  polls `get_device_last_used()` and only pulls once a fresh upload is confirmed:
  - **gate-only mode** (`--sync`, the current setup): confirms the last upload is *recent*
    — within `GARMIN_SYNC_MAX_AGE` (default 1200s / 20 min). Pairs with the iPhone Shortcut
    below that syncs the watch at 07:55, ~5 min before the 08:00 run.
  - **trigger mode** (`GARMIN_SYNC_CMD` set): butler itself fires a trigger, then waits for
    the upload time to *advance* past baseline.
  On `GARMIN_SYNC_TIMEOUT` (180s) it pulls anyway and flags `⚠️ sync not confirmed`;
  `synced_fresh` (true/false/null) is stored in the record.

  The sync must go through the **iPhone 15** — the watch is paired to it, so only it can
  push the watch's data to Garmin's cloud (the tailnet Pixel can't sync a watch it isn't
  paired to; ADB/`monkey` is Android-only and N/A). Trigger options:
  - **Phone-side, time-based (CHOSEN):** an **Apple Shortcuts** Personal Automation at
    **07:55** daily → *Open App → Garmin Connect* (Run Without Asking). Opening the app is
    what makes Garmin Connect BLE-sync the watch to the cloud; the gate then confirms it.
  - **Server-triggered (alternative):** install **Pushcut** on the iPhone, make an
    automation that opens Garmin Connect, and set
    `GARMIN_SYNC_CMD="curl -s -X POST https://api.pushcut.io/<token>/notifications/<name>"`.
  iOS may need the phone awake for the app to foreground (a known iOS limit; if 07:55-locked
  proves unreliable, switch the Shortcut trigger to "When my alarm stops"). The gate falls
  back gracefully on timeout.
- **Output / state (git-ignored, `**/state/`):**
  - `state/<YYYY-MM-DD>.json` — the **FULL** record incl. every endpoint's raw response
    (~1 MB/day with intraday arrays). The complete archive for downstream use cases.
  - `state/history.jsonl` — the **curated** flat record per run (~2 KB/line) — the lean,
    queryable trend log. (Default stdout + the interactive skill also get curated-only, so
    the agent context isn't flooded with raw intraday arrays.)
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
