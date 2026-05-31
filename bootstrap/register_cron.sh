#!/usr/bin/env bash
# Register all module cron schedules. Idempotent: removes a same-named job first.
# Usage: TG_USER_ID=<your telegram id> ./register_cron.sh
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
: "${TG_USER_ID:?Set TG_USER_ID=<your telegram numeric id> before running}"

create() { # name schedule prompt skill
  hermes -p butler cron remove "$1" >/dev/null 2>&1 || true
  hermes -p butler cron create "$2" "$3" \
    --skill "$4" --name "$1" --deliver "telegram:${TG_USER_ID}"
}

create daily-steve-jobs-letter "0 7 * * *" \
  "Run the steve-jobs-letter skill and deliver today's letter — the full letter text with the author and the source URL — to me." \
  steve-jobs-letter

hermes -p butler cron list
