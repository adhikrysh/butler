---
name: garmin-dashboard
description: Report adhi's Garmin Connect stats (steps, resting HR, sleep, Body Battery, stress, HRV). Use when adhi asks how he slept / his steps / his Garmin or recovery stats, or when the daily 8am job runs.
version: 0.2.0
metadata:
  hermes:
    tags: [daily, health, garmin]
    category: daily
    requires_toolsets: [terminal]
---

# Garmin Dashboard

> The scheduled daily 8am push is handled by a **no-agent** cron script (verbatim,
> no LLM) — `cron/deliver.sh`. This skill is for **interactive** requests only —
> when adhi asks about his stats in chat.

Data comes from Garmin's API via the `garminconnect` library — v0.3+ does its own
SSO/OAuth login on `curl_cffi` (not garth), with token resume. No browser, no captcha.

When adhi asks for his Garmin / sleep / steps / recovery stats:

1. Run the pull script (absolute path, works from any directory):

   ```
   uv run /home/drc/butler/modules/daily/garmin-dashboard/scripts/garmin_pull.py
   ```

   It prints ONE JSON record: `{captured_at, source, headline_date, stats:{<date>:{...}}}`,
   where each day's `stats` has steps, resting_hr_bpm, sleep_seconds, sleep_score,
   body_battery_recent, stress_avg, intensity_minutes, hrv_last_night_ms, etc.
   (`null` = not synced / watch not worn). It also saves today's record to `state/`.

   If it exits non-zero (auth/token problem, network), tell adhi you couldn't reach
   Garmin and stop — do NOT invent numbers. A persistent auth failure means the saved
   tokens expired; the fix is to re-run the script once with `GARMIN_EMAIL` /
   `GARMIN_PASSWORD` in the environment so it re-mints tokens.

2. Answer his actual question conversationally from the data — usually the
   `headline_date` (last complete day), or whichever day/metric he asked about.
   Keep it plain text, no markdown tables. Convert `sleep_seconds` to `Xh Ym`.

3. Never print credentials or token contents.
