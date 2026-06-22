# Module: garmin-dashboard

- **Type:** proactive (scheduled push) + interactive.
- **Schedule:** `0 4 * * *` UTC = 9:00pm US Pacific (PDT) → Telegram. Cron runs on
  server time — see README for the DST caveat (becomes 8pm in PST).
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
- **Metrics captured (lean).** Each run calls only the **13 endpoints** that feed the
  curated daily stats — user summary, sleep (+ stages), HRV, respiration, SpO₂, Body
  Battery, training readiness, training status (VO₂max), hydration, fitness age, endurance
  score, body composition (weight), activities — for yesterday + today, flattened into one
  record (steps, RHR, calories, floors, intensity, stress, sleep, HRV, readiness, recovery,
  respiration, weight, …). We deliberately do **not** archive raw intraday firehoses
  (per-2-min HR/stress, minute-by-minute sleep): Garmin retains that history, so backfill a
  specific day on demand if a use-case ever needs it — cheaper than photocopying ~900 KB
  every morning. Registry: `_DAILY` in `scripts/garmin_pull.py` — add a line to capture
  more. Missing metric -> `null`.
- **Freshness / can we sync?** No — the API only *reads* Garmin's cloud; it can't make the
  watch upload. Data reaches the cloud when the Garmin Connect **phone app** syncs the
  watch over Bluetooth (or the watch's own **Wi-Fi auto-upload**, on supported models). So
  `today` is essentially complete by the **9pm** slot, which is why the summary
  **headlines today** (`head = today_s`). The summary footer shows `📡 Watch last synced Xh ago`
  (from `get_device_last_used` → `lastUsedDeviceUploadTime`) so staleness is always visible;
  the record also stores `last_sync_utc` + `device`. `request_reload(date)` only nudges
  Garmin to reprocess *already-uploaded* data (backfilling old dates) — it can't fetch new
  data off the watch.
- **Deterministic "sync-gate" (ACTIVE — `cron/deliver.sh` passes `--sync`).** The script
  polls `get_device_last_used()` and only pulls once a fresh upload is confirmed:
  - **gate-only mode** (`--sync`, the current setup): confirms the last upload is *recent*
    — within `GARMIN_SYNC_MAX_AGE` (default 1200s / 20 min). Pairs with the iPhone Shortcut
    below that syncs the watch at 20:55, ~5 min before the 21:00 run.
  - **trigger mode** (`GARMIN_SYNC_CMD` set): butler itself fires a trigger, then waits for
    the upload time to *advance* past baseline.
  On `GARMIN_SYNC_TIMEOUT` (180s) it pulls anyway and flags `⚠️ sync not confirmed`;
  `synced_fresh` (true/false/null) is stored in the record.

  The sync must go through the **iPhone 15** — the watch is paired to it, so only it can
  push the watch's data to Garmin's cloud (the tailnet Pixel can't sync a watch it isn't
  paired to; ADB/`monkey` is Android-only and N/A). Trigger options:
  - **Phone-side, time-based (CHOSEN):** an **Apple Shortcuts** Personal Automation at
    **20:55** daily → *Open App → Garmin Connect* (Run Without Asking). Opening the app is
    what makes Garmin Connect BLE-sync the watch to the cloud; the gate then confirms it.
  - **Server-triggered (alternative):** install **Pushcut** on the iPhone, make an
    automation that opens Garmin Connect, and set
    `GARMIN_SYNC_CMD="curl -s -X POST https://api.pushcut.io/<token>/notifications/<name>"`.
  iOS may need the phone awake for the app to foreground (a known iOS limit; if 20:55-locked
  proves unreliable, trigger it off a reliable evening event — e.g. arriving home or putting
  the phone on the charger). The gate falls back gracefully on timeout.
- **Output / state (git-ignored, `**/state/`):**
  - `state/history.jsonl` — one curated record appended per run (~2 KB/line). The single
    store / trend log. No per-day raw files (dropped — Garmin is the raw store of record).
- **Memory:** none. Runtime state only (the `state/` files + the token dir).
- **Cron registration (run once, or via `bootstrap/register_cron.sh`):**
  ```bash
  cp cron/deliver.sh ~/.hermes/profiles/butler/scripts/garmin_dashboard.sh
  hermes -p butler cron create "0 4 * * *" --no-agent --script garmin_dashboard.sh \
    --deliver telegram:<your-id> --name daily-garmin-dashboard
  ```
- **Manual test (one run now):**
  ```bash
  # mints tokens on first run, then prints the verbatim Telegram summary:
  uv run modules/daily/garmin-dashboard/scripts/garmin_pull.py --telegram
  # or the full JSON record:
  uv run modules/daily/garmin-dashboard/scripts/garmin_pull.py
  ```
