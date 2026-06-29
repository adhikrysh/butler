#!/usr/bin/env bash
# Pull-based self-deploy. Run by butler-deploy.timer every 5 min (and manually).
# Idempotent: no-op when already on origin/main. See ARCHITECTURE.md Part 6.
set -uo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE="$HOME/.hermes/profiles/butler"
LOG="$PROFILE/logs/deploy.log"
LAST_BAD="$PROFILE/.deploy-last-bad"
cd "$REPO_DIR" || exit 1
mkdir -p "$PROFILE/logs"

log() { echo "[$(date -u +%FT%TZ)] $*" >> "$LOG"; }

notify() {  # Telegram sendMessage, reusing the profile bot token + chat id.
  local token chat
  token="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$PROFILE/.env" | cut -d= -f2-)"
  chat="$(grep -E '^TELEGRAM_ALLOWED_USERS=' "$PROFILE/.env" | cut -d= -f2- | cut -d, -f1)"
  [ -n "$token" ] && [ -n "$chat" ] && curl -sS --max-time 15 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=$1" >/dev/null 2>&1 || true
}

git fetch --quiet origin main || { log "fetch failed"; exit 1; }
LOCAL="$(git rev-parse HEAD)"; REMOTE="$(git rev-parse origin/main)"
[ "$LOCAL" = "$REMOTE" ] && exit 0   # up to date — the common case

if ! git diff --quiet || ! git diff --cached --quiet; then
  log "skip: dirty tree at $LOCAL"
  notify "⚠️ Butler deploy skipped: dirty working tree on the box. Reconcile before pushing."
  exit 0
fi

if [ -f "$LAST_BAD" ] && [ "$(cat "$LAST_BAD")" = "$REMOTE" ]; then exit 0; fi  # known-bad guard

OLD="$LOCAL"
if ! git merge --ff-only origin/main >/dev/null 2>&1; then
  log "ff-only failed (diverged)"; notify "❌ Butler deploy: fast-forward failed (history diverged on box)."; exit 1
fi
NEW="$(git rev-parse HEAD)"; log "pulled $OLD -> $NEW"

if ! bash "$REPO_DIR/bootstrap/run_tests.sh" >>"$LOG" 2>&1; then
  git reset --hard "$OLD" >/dev/null 2>&1
  echo "$NEW" > "$LAST_BAD"
  log "tests failed; rolled back to $OLD"
  notify "❌ Butler deploy failed tests — rolled back to ${OLD:0:8}. See deploy.log."
  exit 1
fi
rm -f "$LAST_BAD"

CHANGED="$(git diff --name-only "$OLD" "$NEW")"
restart=0; crons=0
echo "$CHANGED" | grep -q '^bootstrap/SOUL\.md$' && { cp "$REPO_DIR/bootstrap/SOUL.md" "$PROFILE/SOUL.md"; restart=1; }
echo "$CHANGED" | grep -qE 'modules/.*/SKILL\.md$' && restart=1
echo "$CHANGED" | grep -qE '(modules/.*/cron/deliver\.sh$|^bootstrap/register_cron\.sh$)' && crons=1
# Config reconcile: deep-merge repo-owned config keys onto the live profile
# config.yaml (GitOps for config — a config change ships via push, not SSH).
echo "$CHANGED" | grep -qE '^bootstrap/(config\.overrides\.yaml|apply_config_overrides\.py)$' && {
  if [ "$(uv run "$REPO_DIR/bootstrap/apply_config_overrides.py" "$REPO_DIR/bootstrap/config.overrides.yaml" "$PROFILE/config.yaml" 2>>"$LOG")" = changed ]; then
    log "config overrides reconciled"; restart=1
  fi
}

if [ "$crons" = 1 ]; then
  chat="$(grep -E '^TELEGRAM_ALLOWED_USERS=' "$PROFILE/.env" | cut -d= -f2- | cut -d, -f1)"
  TG_USER_ID="$chat" bash "$REPO_DIR/bootstrap/register_cron.sh" >>"$LOG" 2>&1 || log "register_cron failed"
fi
[ "$restart" = 1 ] && { hermes -p butler gateway restart >>"$LOG" 2>&1 || log "gateway restart failed"; }

log "deployed $NEW restart=$restart crons=$crons"
notify "✅ Butler deployed ${NEW:0:8} — restart=$restart crons=$crons"
