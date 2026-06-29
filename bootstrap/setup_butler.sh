#!/usr/bin/env bash
# Reproduce the Butler profile on a fresh box. Run AFTER installing Hermes:
#   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
# Secrets are PROMPTED, never stored in git.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_HOME="$HOME/.hermes/profiles/butler"

hermes profile create butler 2>/dev/null || true
mkdir -p "$PROFILE_HOME" "$PROFILE_HOME/state"

# config.yaml — OpenAI key via an OpenAI-compatible "custom" provider.
cat > "$PROFILE_HOME/config.yaml" <<YAML
model:
  default: "gpt-5.4-mini"
  provider: "custom"
  base_url: "https://api.openai.com/v1"

agent:
  disabled_toolsets:
    - file            # host-side file tool bypasses the read-only sandbox — force file I/O through the terminal

terminal:
  # Write-protection sandbox: the agent's shell runs in a docker container that
  # mounts the repo READ-ONLY (runs code, can't edit it) + profile state/ read-write.
  # Code changes go only through git. Gotcha: container_persistent reuses the
  # container, so after changing volumes/forward_env below, remove the stale one:
  #   docker ps -aq --filter ancestor=python:3.11-slim | xargs -r docker rm -f
  # (Hermes ignores docker_extra_args/--env-file; docker_forward_env is the cred path.
  #  Requires uv installed at \$HOME/.local/bin/uv — the slim image has none.)
  backend: "docker"
  docker_image: "python:3.11-slim"
  container_persistent: true
  cwd: "."
  timeout: 180
  docker_volumes:
    - $REPO_DIR:$REPO_DIR:ro
    - $PROFILE_HOME/state:$PROFILE_HOME/state:rw
    - $PROFILE_HOME/crm_google_sa.json:$PROFILE_HOME/crm_google_sa.json:ro
    - $HOME/.local/bin/uv:/usr/local/bin/uv:ro
  docker_forward_env:
    - OPENAI_API_KEY
    - TELEGRAM_BOT_TOKEN
    - TELEGRAM_ALLOWED_USERS
    - CRM_SHEET_ID
    - CRM_SA_KEY
    - CRM_ALIASES
    - GMAIL_ADDR
    - GMAIL_APP_PW
    - ICLOUD_ADDR
    - ICLOUD_APP_PW
    - CARTESIA_API_KEY
    - CARTESIA_VOICE_ID
    - GARMIN_EMAIL
    - GARMIN_PASSWORD
    - BUTLER_GARMIN_STATE
    - BUTLER_LETTER_STATE

skills:
  external_dirs:
    - $REPO_DIR/modules

# Deliver cron/no-agent output to Telegram raw — no "Job ID" + metadata
# header/footer wrapper (Hermes wraps by default).
cron:
  wrap_response: false

# MCP servers. tinyfish (web agent) authenticates with OAuth 2.1 — tokens are
# acquired interactively on first connect, NOT stored here. After bootstrap, run:
#   hermes -p butler mcp login tinyfish   # opens browser / paste-back over SSH
mcp_servers:
  tinyfish:
    url: "https://agent.tinyfish.ai/mcp"
    auth: oauth
    connect_timeout: 300   # headroom for the interactive OAuth approve step
    timeout: 300
YAML

cp "$REPO_DIR/bootstrap/SOUL.md" "$PROFILE_HOME/SOUL.md"

# Secrets + Telegram allowlist (default-deny: only this ID may talk to Butler).
umask 077
read -rsp 'OPENAI_API_KEY: ' OPENAI_API_KEY; echo
read -rsp 'TELEGRAM_BOT_TOKEN: ' TELEGRAM_BOT_TOKEN; echo
read -rp  'Your Telegram numeric user ID (allowlist): ' TG_USER_ID
{
  printf 'OPENAI_API_KEY=%s\n' "$OPENAI_API_KEY"
  printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN"
  printf 'TELEGRAM_ALLOWED_USERS=%s\n' "$TG_USER_ID"
} > "$PROFILE_HOME/.env"
chmod 600 "$PROFILE_HOME/.env"

echo
echo "Profile 'butler' configured. Next steps:"
echo "  TG_USER_ID=$TG_USER_ID $REPO_DIR/bootstrap/register_cron.sh   # register schedules"
echo "  hermes -p butler gateway install                              # install 24/7 service (answer Y)"
echo "  loginctl enable-linger \"\$USER\"                               # survive logout/reboot"
