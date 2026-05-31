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

hermes -p butler cron list
