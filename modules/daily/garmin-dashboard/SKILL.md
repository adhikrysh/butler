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

2. **Drive the browser** with the tinyfish **async** automation (the Agent capability —
   `fetch_content` is read-only and won't do a login). Async is used on purpose: this is an
   unattended, multi-step job, so a slow morning must not time out a single long call.
   - Call `run_web_automation_async` pointed at `https://connect.garmin.com/app/home`,
     instructing it to log in with the email + password, then open / click into each
     dashboard tile and read every stat shown. It returns a run ID.
   - **Poll** `poll_status` (or `get_run`) with that run ID until the run finishes — be
     patient, complex runs take a minute or more; don't give up after one poll.
   - When complete, read the extracted data from the run result (`get_run` / `get_steps`).
   Capture whatever Garmin shows, for today and the most recent fully-synced day, e.g.:
   steps, distance, calories, floors climbed, intensity minutes, resting heart rate, Body
   Battery, stress, sleep (duration, stages, score), HRV, SpO₂, respiration, training
   status/readiness, hydration, weight. Record the **date each value belongs to**, and only
   record what is actually displayed — never invent or estimate a value.
   - *(Interactive "show me my stats now" requests may use the synchronous
     `run_web_automation` instead, for a faster reply.)*

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

## Reply (this message is delivered to adhi on Telegram)
After saving, send a short plain-text summary of what you extracted — this IS the morning
message adhi sees, so make it the actual data, not a "saved ✓" note. A few lines, no
markdown tables. Example shape:

```
🏃 Garmin — 2026-06-01
Steps 9,673 · Resting HR 55 bpm
Sleep 7h12m (score 82) · Body Battery 64
Stress 28 · Intensity 45 min
```

Include whatever metrics were actually present; pull completed metrics from the most recent
fully-synced day and note if today isn't synced yet. Never include the password.
On failure: send one line saying the extraction failed and why — do not fabricate stats.
