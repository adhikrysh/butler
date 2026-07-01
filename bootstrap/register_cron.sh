#!/usr/bin/env bash
# Register all module cron schedules. Idempotent (re-runnable).
# Usage: TG_USER_ID=<your telegram numeric id> ./register_cron.sh
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
: "${TG_USER_ID:?Set TG_USER_ID=<your telegram numeric id> before running}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_SCRIPTS="$HOME/.hermes/profiles/butler/scripts"
mkdir -p "$PROFILE_SCRIPTS"

# --- steve-jobs-letter -------------------------------------------------------
# NO-AGENT job: the script's stdout is delivered to Telegram VERBATIM (no LLM
# call, no tokens, no risk of the model altering the letter).
# 0 14 * * * UTC = 7am US Pacific (PDT). Cron runs on server time — see README
# for the DST caveat.
cp "$REPO_DIR/modules/daily/steve-jobs-letter/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/steve_jobs_letter.sh"
chmod +x "$PROFILE_SCRIPTS/steve_jobs_letter.sh"
hermes -p butler cron remove daily-steve-jobs-letter >/dev/null 2>&1 || true
hermes -p butler cron create "0 14 * * *" --no-agent --script steve_jobs_letter.sh \
  --deliver "telegram:${TG_USER_ID}" --name daily-steve-jobs-letter

# --- garmin-dashboard --------------------------------------------------------
# NO-AGENT job: garmin_pull.py hits Garmin's API (garminconnect, curl_cffi auth) using
# saved OAuth tokens — no browser, no captcha, no LLM, no TinyFish credits — and
# its stdout (a short stats summary) is delivered to Telegram VERBATIM.
# 0 4 * * * UTC = 9pm US Pacific (PDT). Cron runs on server time — DST caveat in README.
cp "$REPO_DIR/modules/daily/garmin-dashboard/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/garmin_dashboard.sh"
chmod +x "$PROFILE_SCRIPTS/garmin_dashboard.sh"
hermes -p butler cron remove daily-garmin-dashboard >/dev/null 2>&1 || true
hermes -p butler cron create "0 4 * * *" --no-agent --script garmin_dashboard.sh \
  --deliver "telegram:${TG_USER_ID}" --name daily-garmin-dashboard

# --- cold-outbounds follow-up digest -----------------------------------------
# NO-AGENT: outbound.py nudges prints outreach due for follow-up; stdout
# delivered VERBATIM (empty when nothing's due). 0 4 * * * UTC = 9pm US Pacific (PDT).
hermes -p butler cron remove daily-crm-nudge >/dev/null 2>&1 || true   # old name, pre-split
cp "$REPO_DIR/modules/tools/cold-outbounds/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/cold_outbounds_nudge.sh"
chmod +x "$PROFILE_SCRIPTS/cold_outbounds_nudge.sh"
hermes -p butler cron remove daily-cold-outbounds-nudge >/dev/null 2>&1 || true
hermes -p butler cron create "0 4 * * *" --no-agent --script cold_outbounds_nudge.sh \
  --deliver "telegram:${TG_USER_ID}" --name daily-cold-outbounds-nudge

# --- superforecasting: daily decision check-in -------------------------------
# NO-AGENT: forecast.py daily prints the check-in prompt + any decisions due for
# review; stdout delivered VERBATIM. 0 3 * * * UTC = 8pm US Pacific (PDT).
cp "$REPO_DIR/modules/tools/superforecasting/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/superforecasting_daily.sh"
chmod +x "$PROFILE_SCRIPTS/superforecasting_daily.sh"
hermes -p butler cron remove daily-superforecasting >/dev/null 2>&1 || true
hermes -p butler cron create "0 3 * * *" --no-agent --script superforecasting_daily.sh \
  --deliver "telegram:${TG_USER_ID}" --name daily-superforecasting

# --- superforecasting: weekly calibration ------------------------------------
# NO-AGENT: forecast.py calibration prints the hit-rate report. 30 3 * * 1 UTC =
# Sunday 8:30pm US Pacific (PDT).
cp "$REPO_DIR/modules/tools/superforecasting/cron/calibration.sh" \
   "$PROFILE_SCRIPTS/superforecasting_calibration.sh"
chmod +x "$PROFILE_SCRIPTS/superforecasting_calibration.sh"
hermes -p butler cron remove weekly-superforecasting-calibration >/dev/null 2>&1 || true
hermes -p butler cron create "30 3 * * 1" --no-agent --script superforecasting_calibration.sh \
  --deliver "telegram:${TG_USER_ID}" --name weekly-superforecasting-calibration

# --- sheet-backup: daily CSV snapshot of the spreadsheet ---------------------
# NO-AGENT: snapshot.py writes state/backups/<tab>.csv so the server's restic→B2
# backup captures the Sheet (the only app data living off the box). Silent on
# success; failures print to stdout → Telegram. 0 8 * * * UTC = ~1am US Pacific.
cp "$REPO_DIR/modules/tools/sheet-backup/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/sheet_backup.sh"
chmod +x "$PROFILE_SCRIPTS/sheet_backup.sh"
hermes -p butler cron remove daily-sheet-backup >/dev/null 2>&1 || true
hermes -p butler cron create "0 8 * * *" --no-agent --script sheet_backup.sh \
  --deliver "telegram:${TG_USER_ID}" --name daily-sheet-backup

# --- learnings: weekly review digest -----------------------------------------
# NO-AGENT: learn.py digest prints pending (med+high) learnings the agent
# captured; stdout delivered VERBATIM (empty → no message on a quiet week).
# 0 4 * * 1 UTC = Sunday 9pm US Pacific (PDT). (Shares the 04:00 slot with the
# daily jobs on Sundays — harmless; bump to 0 5 * * 1 if the pile-up annoys.)
cp "$REPO_DIR/modules/tools/learnings/cron/deliver.sh" \
   "$PROFILE_SCRIPTS/learnings_digest.sh"
chmod +x "$PROFILE_SCRIPTS/learnings_digest.sh"
hermes -p butler cron remove weekly-learnings-digest >/dev/null 2>&1 || true
hermes -p butler cron create "0 4 * * 1" --no-agent --script learnings_digest.sh \
  --deliver "telegram:${TG_USER_ID}" --name weekly-learnings-digest

hermes -p butler cron list
