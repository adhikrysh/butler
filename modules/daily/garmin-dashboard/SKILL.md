---
name: garmin-dashboard
description: Log into Garmin Connect and extract the dashboard stats via the tinyfish web agent. Use when adhi asks for his Garmin stats / dashboard, or when the daily 8am extraction job runs.
version: 0.1.0
metadata:
  hermes:
    tags: [daily, health, garmin]
    category: daily
    requires_toolsets: [terminal, tinyfish]
---

# Garmin Dashboard Extraction

Goal: log into Garmin Connect, click through the dashboard, and **extract every stat
shown**, then **save** it. For now this is capture-only — don't summarize, message, or act
on the data unless adhi asked interactively. Persisting the data is the whole job.

## Steps

1. **Read credentials** from the profile `.env` with the shell — never echo the password:
   ```bash
   set -a; . /home/drc/.hermes/profiles/butler/.env; set +a
   echo "user=$GARMIN_EMAIL"   # ok to show the email; NEVER print $GARMIN_PASSWORD
   ```

2. **Drive the browser** with the tinyfish `run_web_automation` tool (the Agent capability —
   `fetch_content` is read-only and won't do a login). Point it at
   `https://connect.garmin.com/app/home` and instruct it to:
   - Log in with the email + password.
   - Open / click into each dashboard tile and read **all** stats present, for today and
     for the most recent fully-synced day. Capture whatever Garmin shows, e.g.: steps,
     distance, calories, floors climbed, intensity minutes, resting heart rate, Body
     Battery, stress, sleep (duration, stages, score), HRV, SpO₂, respiration, training
     status/readiness, hydration, weight. Record the **date each value belongs to**.
   - Only record what is actually displayed — never invent or estimate a value.

3. **Save the result.** Use today's server date (`date +%F`). Write the state dir if needed:
   ```bash
   D=/home/drc/butler/modules/daily/garmin-dashboard/state
   mkdir -p "$D"
   ```
   Write a single JSON object to `"$D/$(date +%F).json"` (pretty-printed) **and** append the
   same object as one compact line to `"$D/history.jsonl"`. Shape:
   ```json
   {
     "captured_at": "2026-06-02T15:00:11Z",
     "source": "connect.garmin.com",
     "stats": { "2026-06-01": { "steps": 9673, "resting_hr_bpm": 55, "...": "..." },
                "2026-06-02": { "steps": null, "...": "..." } }
   }
   ```
   Use `null` for tiles that aren't synced yet. Keep keys snake_case and stable run-to-run.

4. **On failure** (login rejected, site unreachable, captcha): write nothing, say plainly
   that the extraction failed and why, and stop. Do NOT fabricate stats.

5. **Never** put the password in any file, log, or reply.

## Reply
- **Cron run:** one line, e.g. `Saved Garmin stats for 2026-06-02 ✓` (or the failure reason).
- **Interactive (adhi asked):** save as above, then give him the key numbers in plain text.
